"""
Self-built, per-client AI appointment-setting agent. Called from
routers/client_sms_webhooks.py for every inbound SMS to a client's own
Twilio number, gated by client_marketing_config.response_ai_enabled (a
client with the flag off just gets logged for manual reply instead).

Same underlying mechanism as routers/agents.py's chat loop (plain Anthropic
Messages API, a system prompt assembled from stored text, a small tool
loop) — just narrower: no file/bash/integration tools, one client-specific
context string instead of a whole directory of files, and no attended chat
UI. Every helper this module calls (client_sms.send_client_sms,
create_appointment_row) goes through db.py's single global asyncpg pool,
which is bound to the main event loop, so handle_inbound_sms() must always
run ON that loop — either awaited directly from the webhook, or as an
APScheduler job (scheduler_registry.py), never on a raw background thread
(a separate thread would need its own event loop, and asyncpg
connections/pools can't cross event loops).

Per-client config also drives:
- response_ai_sequence — an ordered list of short stage descriptions (the
  admin UI's "first text" through "fifth text") woven into the system
  prompt as a loose conversational arc, not a rigid script.
- response_ai_max_chars — an SMS length cap, enforced both as a prompt
  instruction and a hard truncation fallback in handle_inbound_sms().
- response_ai_min_delay_seconds — client_sms_webhooks.py defers the actual
  handle_inbound_sms() call via scheduler_registry when this is set, rather
  than sleeping inline (which would hold the Twilio webhook open and risk
  a timeout/retry).

V1 scope: SMS only. When a client has connected a Personal Access Token
(client_marketing_config.calendly_api_token, client_marketing_config.
calendly_event_type_url), check_availability (calendly_integration.py)
looks up real open slots so the agent never proposes an already-taken
time. propose_appointment always logs the appointment internally
(create_appointment_row, same trust level as a rep noting a booked time)
and, when it was able to collect the lead's name/email/reason, ALSO
creates a genuinely confirmed booking straight on Calendly via its
Scheduling API (calendly_integration.create_booking — found live
2026-09-14; requires a paid Calendly plan) — no click needed from the
lead. Missing any of those falls back to texting a direct one-tap link
to the exact slot instead. A client with no token connected just gets
asked for their preferred day/time as before (check_availability says so
and the model falls back).

Meta Lead Ads ingestion: routers/meta_lead_webhooks.py verifies Meta's
webhook challenge/signature, pulls lead data via Graph API, resolves the
lead to a client via client_marketing_config.meta_page_id, creates/claims
the contacts row via client_portal.py's exact ownership contract, and — for
a genuinely new/claimed contact — calls initiate_conversation() below to
proactively send the first outbound message. Distinct from
handle_inbound_sms(), which only ever reacts to an inbound message and
never starts a thread on its own.
"""
import asyncio
import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import anthropic

import calendly_integration
import client_sms
import lead_flags
import scheduler_registry
from db import get_pool
from routers.appointments import create_appointment_row
from sms_text import gsm7_safe
from timezone_lookup import guess_timezone

_MAX_TOOL_ITERATIONS = 4
_HISTORY_LIMIT = 20

_SYSTEM_PREAMBLE = """You are an AI appointment-setting assistant texting on behalf of a real \
local business. You are replying by SMS to a real lead who reached out — respond like a helpful \
staff member, not a chatbot. Keep replies short (SMS-length, 1-3 sentences).

This prompt ends with a MANDATORY RULES section (and, if set, a conversation arc to follow). \
Those are not style suggestions — they are hard constraints from the business owner. Before you \
finalize any reply, check it against every rule listed there. If a draft reply breaks one, rewrite \
it before responding. This matters more than sounding natural or being thorough.

Baseline behavior (the mandatory rules below can add to this, never loosen it):
- Only state facts, pricing, offers, or guarantees that are explicitly given to you in the \
business info below. Never invent or guess at anything you weren't told.
- The moment the lead wants to book, call check_availability — don't wait for them to name a day \
first, and don't ask them to pick one blind. It searches forward on its own and returns real \
open times on the earliest available day, which may be a while out — offer exactly what it gives \
you as a simple either/or (or just the one time, on a day with only one opening), never a \
day/time you made up yourself and never more than what you were given. If it says the calendar \
isn't connected, ask for their preferred day and time instead. Once they agree to a specific time, \
call propose_appointment to book it, then confirm it back — never ask for their name or email \
up front, that's looked up automatically from their info on file (only ask if propose_appointment \
says one is missing). Pass the reason for their call too if you already know it.
- If the lead can't make the time(s) you offered, call check_availability again with after_date \
set to the day AFTER the day you just offered — never re-offer the same day, and never repeat the \
exact same times you already gave them.
- If the lead asks for something outside what you were told, seems upset, asks for a refund or \
files a complaint, or you're not confident how to respond, call escalate_to_human and let them \
know a team member will follow up.
- Never claim an appointment is booked unless propose_appointment confirmed it in this same turn. \
Never send the lead a booking link — you book it for them.
- If it becomes clear the lead can't be a client — they live outside the area the business serves, \
need something the business doesn't offer, or fail a requirement in the business info or rules below \
(e.g. they say they'll only go somewhere that bills their insurance) — call mark_unqualified with the \
reason and send one short, polite closing text. Only do this on a clear answer from the lead, never on \
a guess or a first hesitation, and never for a price question alone.
"""

_TOOLS = [
    {
        "name": "check_availability",
        "description": (
            "Finds REAL open appointment times on the business's calendar, if connected. Searches "
            "forward automatically (up to a month out) and returns the EARLIEST real day's opening "
            "and closing slot (its two most spread-apart times, or just the one slot on a day with "
            "only one) — call this as soon as the lead wants to book, even before they've named a "
            "day, rather than asking them to pick a date first. If the lead already named a day, "
            "pass it as after_date so the search starts there instead of today. If the lead just "
            "rejected the times you already offered, call this again with after_date set to the "
            "day after that one, so you don't hand back the same day/times again."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "after_date": {"type": "string", "description": "YYYY-MM-DD to start searching from. Omit to search from today."},
            },
        },
    },
    {
        "name": "propose_appointment",
        "description": (
            "Book this lead's appointment once they've agreed to one of the specific times you "
            "offered. Their name/email are looked up automatically from their info on file — never "
            "ask for them up front. With a connected calendar this books a REAL confirmed "
            "appointment straight onto it, no link and no further action from the lead. Only if this "
            "tool's result says their name or email is missing, ask for just that and call it again "
            "with lead_name/lead_email."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "YYYY-MM-DD"},
                "time": {"type": "string", "description": "HH:MM in 24h format"},
                "reason": {"type": "string", "description": "One short line on why they're reaching out, from earlier in this conversation."},
                "notes": {"type": "string", "description": "Anything worth noting for the business, e.g. what the lead is coming in for."},
                "lead_name": {"type": "string", "description": "ONLY when a previous propose_appointment result said the name is missing — the name the lead just gave you."},
                "lead_email": {"type": "string", "description": "ONLY when a previous propose_appointment result said the email is missing — the email the lead just gave you."},
            },
            "required": ["date", "time"],
        },
    },
    {
        "name": "escalate_to_human",
        "description": "Hand this conversation off to a human team member instead of continuing to auto-respond.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string"},
            },
            "required": ["reason"],
        },
    },
    {
        "name": "mark_unqualified",
        "description": (
            "Tag this lead Unqualified once they've clearly shown they can't be a client (e.g. they live "
            "outside the service area). Your closing text in this same turn still goes out, but after "
            "that they get no more automated texts or emails of any kind."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Short reason, e.g. 'Lives in Chicago, outside Austin service area'."},
            },
            "required": ["reason"],
        },
    },
]

# mark_unqualified is applied only AFTER that turn's reply has been sent,
# because the Unqualified tag blocks every automated send (lead_flags.py) —
# applying it mid-turn would swallow the polite closing text. Keyed by
# (client_id, phone); filled by _execute_tool, drained by
# _apply_pending_unqualified once the reply segments are out.
_pending_unqualified: dict[tuple[int, str], str] = {}


async def _apply_pending_unqualified(client_id: int, phone: str) -> None:
    reason = _pending_unqualified.pop((client_id, phone), None)
    if reason is None:
        return
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                rf"""
                UPDATE contacts c SET
                    tags = CASE WHEN {lead_flags.UNQUALIFIED_SQL} THEN c.tags
                                ELSE array_append(coalesce(c.tags, '{{}}'), $3) END,
                    client_followup_enrolled_at = NULL, client_followup_anchor_at = NULL,
                    client_followup_touch1_sent_at = NULL, client_followup_touch2_sent_at = NULL,
                    client_followup_touch3_sent_at = NULL, client_followup_touch4_sent_at = NULL,
                    updated_at = now()
                WHERE c.client_id = $1 AND NOT c.is_client_anchor
                  AND coalesce(c.phone, '') != ''
                  AND right(regexp_replace(c.phone, '\D', '', 'g'), 10) = right(regexp_replace($2, '\D', '', 'g'), 10)
                """,
                client_id, phone, lead_flags.UNQUALIFIED_TAG,
            )
            await conn.execute(
                "UPDATE client_lead_conversations SET status = 'unqualified' WHERE client_id = $1 AND phone = $2",
                client_id, phone,
            )
        print(f"[response_ai] {phone} (client={client_id}) marked Unqualified: {reason}")
    except Exception as e:
        print(f"[response_ai] failed to mark {phone} (client={client_id}) Unqualified: {e}")


async def _get_or_create_conversation(conn, client_id: int, phone: str) -> dict:
    row = await conn.fetchrow(
        """
        INSERT INTO client_lead_conversations (client_id, phone, status, last_message_at)
        VALUES ($1, $2, 'ai_active', now())
        ON CONFLICT (client_id, phone) DO UPDATE SET last_message_at = now()
        RETURNING *
        """,
        client_id, phone,
    )
    return dict(row)


async def _get_or_create_contact(conn, client_id: int, phone: str) -> dict | None:
    """Same ownership rules as client_portal.py's portal_create_lead() —
    never claim a phone number that's already someone else's anchor contact
    or another client's lead. Returns None (rather than raising) if the
    phone is already claimed elsewhere, so a booking still succeeds with
    contact_id=None rather than blocking the lead's reply over an edge case.

    Matches on the last 10 digits rather than an exact string (same
    normalization dialer_webhooks.py and the reset-test endpoint already
    use) — contacts can be stored as bare 10-digit numbers, with a leading
    1, or full E.164 depending on where they were entered, while an
    inbound Twilio webhook's From is always E.164. An exact-string match
    was silently missing existing leads already in the CRM and creating a
    duplicate contact for the same real person instead of reusing theirs.

    Returns {id, owner, email} rather than just an id — when the phone
    matches an existing lead (e.g. one that came in earlier through Meta
    Lead Ads or was added manually) their name/email is already on file,
    and propose_appointment uses it to pre-fill the Calendly link instead
    of sending the lead a blank form to fill out again."""
    existing = await conn.fetchrow(
        "SELECT id, client_id, is_client_anchor, owner, email FROM contacts "
        "WHERE right(regexp_replace(phone, '\\D', '', 'g'), 10) = right(regexp_replace($1, '\\D', '', 'g'), 10) "
        "ORDER BY (client_id = $2) DESC, created_at ASC LIMIT 1",
        phone, client_id,
    )
    if existing:
        if existing["is_client_anchor"] or (existing["client_id"] is not None and existing["client_id"] != client_id):
            return None
        return {"id": existing["id"], "owner": existing["owner"], "email": existing["email"]}
    row = await conn.fetchrow(
        "INSERT INTO contacts (id, phone, status, client_id) VALUES ($1, $2, 'new', $3) RETURNING id",
        str(uuid.uuid4()), phone, client_id,
    )
    return {"id": row["id"], "owner": None, "email": None}


async def _load_recent_messages(conn, client_id: int, phone: str) -> list[dict]:
    rows = await conn.fetch(
        """
        SELECT direction, body FROM client_sms_messages
        WHERE client_id = $1 AND (from_number = $2 OR to_number = $2)
        ORDER BY created_at DESC LIMIT $3
        """,
        client_id, phone, _HISTORY_LIMIT,
    )
    return [
        {"role": "user" if r["direction"] == "inbound" else "assistant", "content": r["body"]}
        for r in reversed(rows)
    ]


def _split_into_sms_segments(text: str, max_words: int | None) -> list[str]:
    """Splits a reply into multiple SMS-sized segments instead of
    truncating it — a reply that runs past max_words used to just get cut
    off mid-thought, silently dropping whatever came after the limit.
    Breaks at sentence boundaries so each segment reads naturally on its
    own; only hard-splits mid-sentence as a last resort, if one sentence by
    itself is longer than the whole limit. Segments are sent in order as
    separate texts (see handle_inbound_sms). A line break the model wrote
    is always a text boundary — the conversation arc asks for some replies
    as two texts (an empathy line, then the call offer)."""
    if not max_words:
        return [text]

    lines = [line for line in text.strip().split("\n") if line.strip()]
    if len(lines) > 1:
        return [seg for line in lines for seg in _split_into_sms_segments(line, max_words)]

    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    segments: list[str] = []
    current: list[str] = []

    def flush():
        if current:
            segments.append(" ".join(current))

    for sentence in sentences:
        sentence_words = sentence.split()
        if not sentence_words:
            continue
        if len(sentence_words) > max_words:
            flush()
            current.clear()
            for i in range(0, len(sentence_words), max_words):
                segments.append(" ".join(sentence_words[i:i + max_words]))
            continue
        if len(current) + len(sentence_words) > max_words:
            flush()
            current = list(sentence_words)
        else:
            current.extend(sentence_words)
    flush()
    return segments or [text]


def _today_str(tz_name: str) -> str:
    """"Tuesday, September 29, 2026" in the lead's timezone (portable — no %-d)."""
    now = datetime.now(ZoneInfo(tz_name))
    return f"{now:%A, %B} {now.day}, {now.year}"


def _build_system_prompt(
    business_name: str, context: str, sequence: list[str], max_words: int | None, rules: str,
    today_str: str, booked_for: str | None = None,
) -> str:
    # Order matters here: business context and the conversation arc come
    # first (background the model reasons with), and the mandatory rules
    # come LAST, right before the model has to actually generate a reply —
    # instructions placed at the end of a long system prompt get more
    # weight than ones sandwiched in the middle, and repeating the "these
    # are mandatory" framing right here (on top of _SYSTEM_PREAMBLE's
    # opening mention) is deliberate reinforcement, not redundancy.
    parts = [
        _SYSTEM_PREAMBLE,
        f"\nToday is {today_str} (the lead's local date/day of week). Use this to resolve "
        "relative dates like \"tomorrow\" or \"next Tuesday\" into an actual YYYY-MM-DD yourself — "
        "never ask the lead to spell out a date they already gave you in relative terms.\n",
        f"\n--- Business: {business_name} ---\n{context.strip()}\n",
    ]

    if sequence:
        steps = "\n".join(f"{i+1}. {step}" for i, step in enumerate(sequence) if step and step.strip())
        parts.append(
            "\n--- Conversation arc to aim for ---\n"
            "Loose guidance, not a script — always answer the lead's own questions first, then "
            f"steer back toward whichever of these is next:\n{steps}\n"
            "\nIf a step above mentions several things worth asking about, that's a menu, not a "
            "checklist to work through at once — pick the single most natural one for THIS text and "
            "save the rest for a later message. Two things joined with \"and\" is still two "
            "questions in one text, whether or not each one ends in a question mark.\n"
        )

    if booked_for:
        # The lead booked on the client's Calendly themselves (e.g. from the
        # Meta lead form's booking step) — without this the arc above keeps
        # pushing them to book a call they already have.
        parts.append(
            f"\n--- This lead is ALREADY BOOKED ---\nThey have an appointment on {booked_for}. "
            "Skip the conversation arc's booking steps entirely: never offer or propose another time "
            "unless they ask to reschedule. Confirm the appointment if it's relevant, answer their "
            "questions, and help them show up prepared.\n"
        )

    if max_words or (rules and rules.strip()):
        parts.append(
            "\n=== MANDATORY RULES ===\n"
            "Check your reply against every rule below before sending it. These override your own "
            "instincts about phrasing, length, or style — if a draft breaks one, rewrite it.\n"
        )
        if max_words:
            parts.append(f"- Every reply must be {max_words} words or fewer.\n")
        if rules and rules.strip():
            parts.append(f"{rules.strip()}\n")

    return "".join(parts)


async def handle_inbound_sms(client_id: int, from_phone: str, body: str) -> None:
    """Entry point — called directly from client_sms_webhooks.py when a
    client has no reply-delay configured, or as a scheduler_registry-backed
    deferred job when response_ai_min_delay_seconds > 0. Never raises — a
    bug here must never break the webhook (or the scheduler) that runs it.
    `body` isn't used directly (the inbound row is already inserted into
    client_sms_messages by the caller before this runs, so
    _load_recent_messages already picks it up) — kept as a parameter for
    logging/clarity at the call site."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT cmc.response_ai_context, cmc.response_ai_sequence, cmc.response_ai_max_words, "
                "cmc.response_ai_rules, c.name FROM client_marketing_config cmc "
                "JOIN clients c ON c.id = cmc.client_id WHERE cmc.client_id = $1",
                client_id,
            )
            if not row:
                return

            conversation = await _get_or_create_conversation(conn, client_id, from_phone)
            # Every inbound lead needs a contacts row to show up in the
            # client portal's inbox at all (it lists threads by contact,
            # not by client_sms_messages directly) — this used to only
            # happen inside propose_appointment, so any conversation that
            # never reached a booking (a question, an objection, an
            # escalation) was invisible in the portal even though the AI
            # was actively replying. Create it up front instead, for every
            # message, not just a booked one.
            contact = await _get_or_create_contact(conn, client_id, from_phone)
            if conversation["status"] == "escalated":
                return  # a human has taken over this thread — stay silent
            if await lead_flags.is_unqualified(client_id, phone=from_phone):
                # Tagged Unqualified — no automated replies (the client can
                # still reply by hand). Checks the tag, not the 'unqualified'
                # conversation status, so removing the tag re-enables the AI.
                return

            messages = await _load_recent_messages(conn, client_id, from_phone)
            booking = await _upcoming_booking(conn, from_phone, (contact or {}).get("email"))

        # asyncpg has no JSONB codec registered on this pool (matches
        # client_marketing.py's _decode_config) — comes back as a raw string.
        sequence = row["response_ai_sequence"]
        if isinstance(sequence, str):
            sequence = json.loads(sequence)
        max_words = row["response_ai_max_words"]

        tz_name = guess_timezone(from_phone)
        today_str = _today_str(tz_name)

        system_prompt = _build_system_prompt(
            row["name"], row["response_ai_context"] or "", sequence or [], max_words, row["response_ai_rules"] or "",
            today_str, booked_for=_format_booking(booking) if booking else None,
        )
        reply_text = await _run_agent_turn(client_id, from_phone, system_prompt, messages)
        if reply_text:
            # Belt-and-suspenders, same as the word-count cap below: a "no
            # em dashes" rule in response_ai_rules is a prompt instruction
            # the model can still ignore. gsm7_safe() normalizes em/en
            # dashes, curly quotes, and ellipses to their plain-ASCII
            # equivalents (it already exists purely to stop stray
            # typographic characters from silently doubling Twilio's
            # per-segment billing — this reuses it as a content guardrail
            # too) BEFORE the reply is stored, so client_sms_messages and
            # what the lead actually receives always match.
            reply_text = gsm7_safe(reply_text)
            # Belt-and-suspenders, same reasoning as the em-dash fix above —
            # the prompt already instructs the word limit, this guarantees
            # it even if the model runs long. Split into multiple texts
            # instead of truncating (which was silently dropping the tail
            # of the reply) — sent in order, each its own SMS.
            segments = _split_into_sms_segments(reply_text, max_words)
            for i, segment in enumerate(segments):
                if i > 0:
                    # A multi-text reply landing all at once reads as
                    # obviously automated — a real person typing a second
                    # text takes a beat. Every client configured with the
                    # existing response_ai_min_delay_seconds rule (meant to
                    # be 15s+) already reaches this via the scheduler, off
                    # the Twilio request path, so this sleep is safe there.
                    # Only a client explicitly configured with a 0-second
                    # min delay hits this inline on the webhook response —
                    # an edge case, but worth knowing about if Twilio ever
                    # times out a reply on such a client.
                    await asyncio.sleep(10)
                await client_sms.send_client_sms(client_id, from_phone, segment)
        await _apply_pending_unqualified(client_id, from_phone)
    except Exception as e:
        print(f"[response_ai] handle_inbound_sms failed for client={client_id} phone={from_phone}: {e}")


_PROACTIVE_PREAMBLE_ADDITION = (
    "\nYou are OPENING this conversation, not replying to one — the lead just submitted this "
    "business's lead form (e.g. a Facebook/Instagram ad) and hasn't heard from you yet. There is no "
    "real message from them to react to, only the system note below. Send a warm, on-brand first "
    "text that acknowledges they reached out, briefly says what the business can help with, and "
    "invites them to book or share what they're looking for — never answer a question they never "
    "asked, and never reference the system note itself.\n"
)


# A Meta lead form can send the prospect straight on to the client's
# Calendly from its completion screen. The opener waits this long to give
# them time to book, then is skipped if they did (see _upcoming_booking).
META_LEAD_BOOKING_GRACE_SECONDS = 60


async def _upcoming_booking(conn, phone: str, email: str | None):
    """The lead's next scheduled appointment, or None. A booking made through
    Calendly lands as an appointment_reminders row (routers/calendly_webhooks.py),
    linked to the same contact by phone, email, or name — so match the
    contact's phone as well as the booking's own phone/email, since
    Calendly's form may not ask for a phone at all."""
    digits = re.sub(r"\D", "", phone)[-10:]
    return await conn.fetchrow(
        r"""
        SELECT a.appointment_at, a.prospect_timezone
        FROM appointment_reminders a LEFT JOIN contacts c ON c.id = a.contact_id
        WHERE a.status = 'scheduled' AND a.appointment_at > now()
          AND (right(regexp_replace(coalesce(c.phone, ''), '\D', '', 'g'), 10) = $1
               OR right(regexp_replace(coalesce(a.prospect_phone, ''), '\D', '', 'g'), 10) = $1
               OR ($2::text IS NOT NULL AND lower(a.prospect_email) = lower($2)))
        ORDER BY a.appointment_at LIMIT 1
        """,
        digits, email,
    )


def _format_booking(booking) -> str:
    """e.g. "Thursday, October 2 at 2:00 PM CDT" in the lead's own timezone."""
    try:
        tz = ZoneInfo(booking["prospect_timezone"])
    except Exception:
        tz = ZoneInfo("UTC")
    local = booking["appointment_at"].astimezone(tz)
    return f"{local:%A, %B} {local.day} at {local:%I:%M %p}".replace(" 0", " ") + f" {local:%Z}"


# Queued openers older than this are dropped rather than sent — after a long
# outage, a "thanks for reaching out" text half a day late does more harm
# than good.
_OPENER_MAX_AGE = timedelta(hours=12)


async def initiate_conversation(
    client_id: int, phone: str, lead_name: str | None = None, lead_email: str | None = None,
) -> None:
    """Proactive entry point — the only caller is routers/meta_lead_webhooks.py, for a fresh Meta
    Lead Ads submission. Queues the opener in meta_lead_openers instead of an in-memory APScheduler
    job, so a deploy or restart during the booking grace period can't silently drop it;
    send_due_openers (main.py, every 20s) sends it once due. Never raises — same contract as
    handle_inbound_sms."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT response_ai_enabled, response_ai_min_delay_seconds "
                "FROM client_marketing_config WHERE client_id = $1",
                client_id,
            )
            if not row or not row["response_ai_enabled"]:
                return  # agent disabled for this client — Meta lead falls back to manual, same as SMS
            # Always deferred — a text landing the same second someone submits a
            # Facebook form reads unmistakably as a bot, and the form's booking
            # step needs time to finish (META_LEAD_BOOKING_GRACE_SECONDS).
            delay = max(row["response_ai_min_delay_seconds"] or 0, META_LEAD_BOOKING_GRACE_SECONDS)
            await conn.execute(
                "INSERT INTO meta_lead_openers (client_id, phone, lead_name, lead_email, run_at) "
                "VALUES ($1, $2, $3, $4, now() + make_interval(secs => $5))",
                client_id, phone, lead_name, lead_email, delay,
            )
    except Exception as e:
        print(f"[response_ai] initiate_conversation failed for client={client_id} phone={phone}: {e}")


async def send_due_openers() -> None:
    """Scheduler job: claims due meta_lead_openers rows (SKIP LOCKED, so an
    overlapping run can't double-send) and opens each conversation."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            UPDATE meta_lead_openers SET status = 'sending', processed_at = now()
            WHERE id IN (
                SELECT id FROM meta_lead_openers
                WHERE status = 'pending' AND run_at <= now()
                ORDER BY run_at LIMIT 10 FOR UPDATE SKIP LOCKED
            )
            RETURNING *
            """
        )
    for r in rows:
        if datetime.now(timezone.utc) - r["run_at"] > _OPENER_MAX_AGE:
            status = "expired"
        else:
            status = await _open_conversation(r["client_id"], r["phone"], r["lead_name"], r["lead_email"])
        async with pool.acquire() as conn:
            await conn.execute("UPDATE meta_lead_openers SET status = $2 WHERE id = $1", r["id"], status)


async def _open_conversation(client_id: int, phone: str, lead_name: str | None, lead_email: str | None) -> str:
    """Builds the opener prompt from the client's CURRENT agent config (so an
    edit made during the grace period applies) and sends it. Returns the
    final meta_lead_openers status."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT cmc.response_ai_enabled, cmc.response_ai_context, cmc.response_ai_sequence, "
                "cmc.response_ai_max_words, cmc.response_ai_rules, "
                "c.name FROM client_marketing_config cmc JOIN clients c ON c.id = cmc.client_id "
                "WHERE cmc.client_id = $1",
                client_id,
            )
        if not row or not row["response_ai_enabled"]:
            return "skipped_disabled"

        sequence = row["response_ai_sequence"]
        if isinstance(sequence, str):
            sequence = json.loads(sequence)
        max_words = row["response_ai_max_words"]

        tz_name = guess_timezone(phone)
        today_str = _today_str(tz_name)

        system_prompt = _build_system_prompt(
            row["name"], row["response_ai_context"] or "", sequence or [], max_words, row["response_ai_rules"] or "",
            today_str,
        ) + _PROACTIVE_PREAMBLE_ADDITION

        note = (
            f"[System note: {lead_name.strip() if lead_name else 'A new lead'} just submitted this "
            "business's Facebook/Instagram lead form and hasn't heard from you yet. Send the opening text.]"
        )
        messages = [{"role": "user", "content": note}]
        return await _send_initial_message(client_id, phone, system_prompt, messages, max_words, lead_email)
    except Exception as e:
        print(f"[response_ai] _open_conversation failed for client={client_id} phone={phone}: {e}")
        return "failed"


async def _send_initial_message(
    client_id: int, phone: str, system_prompt: str, messages: list[dict], max_words: int | None,
    lead_email: str | None = None,
) -> str:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            if await _upcoming_booking(conn, phone, lead_email):
                print(f"[response_ai] meta lead {phone} (client={client_id}) already booked — skipping opener")
                return "skipped_booked"
        if await lead_flags.is_unqualified(client_id, phone=phone, email=lead_email):
            return "skipped_unqualified"
        async with pool.acquire() as conn:
            # Creates the client_lead_conversations row right before the
            # first text goes out, so the thread shows up in the portal
            # inbox from message one, same as handle_inbound_sms does for
            # a reactive thread.
            await _get_or_create_conversation(conn, client_id, phone)

        reply_text = await _run_agent_turn(client_id, phone, system_prompt, messages)
        if not reply_text:
            return "no_reply"
        reply_text = gsm7_safe(reply_text)
        segments = _split_into_sms_segments(reply_text, max_words)
        for i, segment in enumerate(segments):
            if i > 0:
                await asyncio.sleep(10)
            await client_sms.send_client_sms(client_id, phone, segment, stage="meta_lead_opener")
        await _apply_pending_unqualified(client_id, phone)
        return "sent"
    except Exception as e:
        print(f"[response_ai] _send_initial_message failed for client={client_id} phone={phone}: {e}")
        return "failed"


_FOLLOWUP_PREAMBLE_ADDITION = (
    "\nThe lead has NOT replied to your last text, and it's time for a follow-up nudge. Write ONE "
    "short text that picks up exactly where this conversation left off:\n"
    "- If they told you what's bothering them, refer to it in their own words (\"is the knee still "
    "giving you trouble?\"). If they never said, make it easy to answer (\"is it your back, neck, knee "
    "or something else?\").\n"
    "- If you had offered specific times, mention those same times again and ask which works. You "
    "can't book anything in this text, so never say they're booked.\n"
    "- Never repeat wording you already used in this thread, never say \"just following up\" or "
    "\"checking you got my message\", never invent urgency or scarcity, and never send a link.\n"
    "Reply with only the text itself, nothing else.\n"
)


async def write_followup_text(client_id: int, phone: str, intent: str, final: bool = False) -> str | None:
    """A no-reply follow-up written from the actual thread, for
    client_followup_sequence.py — so the nudge mentions the lead's own pain or
    the times they were offered instead of a generic template. `intent` is
    the client's template for this touch (filled), used as the brief.
    Returns None whenever it can't produce a usable text (agent off, no
    thread, API error, runaway length) so the caller sends the template
    unchanged. No tools: a nudge never books or tags anything."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT cmc.response_ai_enabled, cmc.response_ai_context, cmc.response_ai_sequence, "
                "cmc.response_ai_max_words, cmc.response_ai_rules, c.name FROM client_marketing_config cmc "
                "JOIN clients c ON c.id = cmc.client_id WHERE cmc.client_id = $1",
                client_id,
            )
            if not row or not row["response_ai_enabled"]:
                return None
            messages = await _load_recent_messages(conn, client_id, phone)
        if not messages:
            return None

        sequence = row["response_ai_sequence"]
        if isinstance(sequence, str):
            sequence = json.loads(sequence)
        max_words = row["response_ai_max_words"]

        system_prompt = _build_system_prompt(
            row["name"], row["response_ai_context"] or "", sequence or [], max_words, row["response_ai_rules"] or "",
            _today_str(guess_timezone(phone)),
        ) + _FOLLOWUP_PREAMBLE_ADDITION
        goal = (
            "This is the LAST follow-up: say you'll stop texting so you're not a pest, and end by asking "
            "if you should close this out for now."
            if final else "End with exactly one easy question."
        )
        messages.append({"role": "user", "content": (
            f"[System note: the lead hasn't replied. Write the follow-up text now. {goal} "
            f"The business's template for this follow-up, as a guide to its purpose: \"{intent}\"]"
        )})

        api_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        model = os.environ.get("AGENTS_CLAUDE_MODEL", "claude-sonnet-5")
        response = await asyncio.to_thread(
            api_client.messages.create,
            model=model, max_tokens=300, system=system_prompt, messages=messages,
        )
        text = gsm7_safe("".join(b.text for b in response.content if b.type == "text").strip())
        # One nudge is one text: a reply far past the word cap means the
        # model went off-script, so fall back to the template.
        if not text or (max_words and len(text.split()) > max_words + 10):
            return None
        return text
    except Exception as e:
        print(f"[response_ai] write_followup_text failed for client={client_id} phone={phone}: {e}")
        return None


async def _run_agent_turn(client_id: int, from_phone: str, system_prompt: str, messages: list[dict]) -> str | None:
    api_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.environ.get("AGENTS_CLAUDE_MODEL", "claude-sonnet-5")
    text_parts: list[str] = []

    for _ in range(_MAX_TOOL_ITERATIONS):
        response = await asyncio.to_thread(
            api_client.messages.create,
            model=model, max_tokens=1024, system=system_prompt, tools=_TOOLS, messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})
        text_parts = [b.text for b in response.content if b.type == "text"]
        tool_uses = [b for b in response.content if b.type == "tool_use"]

        if not tool_uses:
            return "\n".join(text_parts).strip() or None

        tool_results = []
        for tool_use in tool_uses:
            result = await _execute_tool(client_id, from_phone, tool_use.name, tool_use.input)
            tool_results.append({"type": "tool_result", "tool_use_id": tool_use.id, "content": result})
        messages.append({"role": "user", "content": tool_results})

    return "\n".join(text_parts).strip() or None


async def _execute_tool(client_id: int, from_phone: str, tool_name: str, tool_input: dict) -> str:
    pool = await get_pool()

    if tool_name == "check_availability":
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT calendly_api_token, calendly_event_type_url FROM client_marketing_config "
                "WHERE client_id = $1", client_id,
            )
        token = row["calendly_api_token"] if row else None
        event_type_url = row["calendly_event_type_url"] if row else None
        if not token or not event_type_url:
            return "Calendar isn't connected for this business — ask the lead for their preferred day and time instead."
        after_date = (tool_input.get("after_date") or "").strip()
        try:
            tz_name = guess_timezone(from_phone)
            tz = ZoneInfo(tz_name)
            # Calendly requires start_time to be strictly in the future at
            # the moment IT processes the request, not when this code reads
            # the clock — a timestamp that's "now" here can already be past
            # by the time it arrives (network latency, the model's own
            # tool-call round trip), and even today's 00:00Z boundary is
            # already in the past by any afternoon call. Both were hit as
            # real "start_time must be in the future" 400s in testing
            # 2026-09-14. A 15-minute forward buffer clears that race with
            # room to spare while still capturing same-day openings.
            if after_date:
                start_iso = f"{after_date}T00:00:00Z"
            else:
                start_iso = (datetime.now(timezone.utc) + timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%SZ")
            slots = await calendly_integration.find_earliest_available_times(
                token, event_type_url, start_iso, max_days=30,
            )
            if not slots:
                return (
                    "No open times found in the next 30 days — this calendar likely hasn't had "
                    "availability set further out yet. Let the lead know you'll follow up once a "
                    "slot opens, or offer to have a human confirm timing with them."
                )
            # Only offer options from the single earliest day — a longer
            # list (multiple days) reads as decision paralysis over SMS.
            # Within that day, offer the EARLIEST and LATEST slot rather
            # than the first two chronologically: two options 30 minutes
            # apart aren't a real choice (if the lead can't make 3:00,
            # they probably can't make 3:30 either), while the day's
            # opening and closing slots actually differentiate. Falls back
            # to the single slot itself when that's all there is.
            earliest_day = None
            day_times: list[datetime] = []
            for s in slots:
                local = datetime.fromisoformat(s["start_time"].replace("Z", "+00:00")).astimezone(tz)
                day_label = local.strftime("%A, %B %-d")
                if earliest_day is None:
                    earliest_day = day_label
                if day_label != earliest_day:
                    break
                day_times.append(local)
            if len(day_times) >= 2:
                times = [day_times[0].strftime("%-I:%M %p"), day_times[-1].strftime("%-I:%M %p")]
            else:
                times = [day_times[0].strftime("%-I:%M %p")]
            return f"Earliest real openings (lead's local time): {earliest_day} at {' or '.join(times)}"
        except Exception as e:
            # This failure was previously silent to Dylan — the model just
            # got a graceful fallback string and asked for a day instead,
            # which looks identical to "no calendar connected" from the
            # outside. Logging it is what actually surfaces a bad/under-
            # scoped token (e.g. Calendly's "Insufficient scope" 403) as
            # something diagnosable instead of an unexplained behavior gap.
            print(f"[response_ai] check_availability failed for client={client_id}: {e}", flush=True)
            return f"Couldn't check the calendar ({e}) — ask for their preferred day and time instead."

    if tool_name == "propose_appointment":
        try:
            async with pool.acquire() as conn:
                contact = await _get_or_create_contact(conn, client_id, from_phone)
            contact_id = contact["id"] if contact else None
            tz_name = guess_timezone(from_phone)
            tz = ZoneInfo(tz_name)

            async def _mark_booked():
                async with pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE client_lead_conversations SET status = 'booked' WHERE client_id = $1 AND phone = $2",
                        client_id, from_phone,
                    )

            async def _log_internally():
                # create_appointment_row acquires its own connection (it's
                # shared with the manual-booking HTTP route) — none held here.
                return await create_appointment_row({
                    "contact_id": contact_id,
                    "prospect_phone": from_phone,
                    "date": tool_input.get("date"),
                    "time": tool_input.get("time"),
                    "timezone": tz_name,
                })

            async with pool.acquire() as conn:
                cal_row = await conn.fetchrow(
                    "SELECT calendly_api_token, calendly_event_type_url FROM client_marketing_config "
                    "WHERE client_id = $1", client_id,
                )
            token = cal_row["calendly_api_token"] if cal_row else None
            event_type_url = cal_row["calendly_event_type_url"] if cal_row else None

            # Name/email come from the matched CRM contact (a Meta lead has
            # both from the form). Only when one is genuinely missing does
            # the model collect it and pass it back in — saved onto the
            # contact so it's on file from then on.
            name = (contact.get("owner") if contact else None) or (tool_input.get("lead_name") or "").strip() or None
            email = (contact.get("email") if contact else None) or (tool_input.get("lead_email") or "").strip() or None
            reason = (tool_input.get("reason") or "").strip() or "Consultation"
            if contact_id and (tool_input.get("lead_name") or tool_input.get("lead_email")):
                async with pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE contacts SET owner = COALESCE(owner, $2), email = COALESCE(email, $3), "
                        "updated_at = now() WHERE id = $1",
                        contact_id, name, email,
                    )

            if token and event_type_url:
                # Calendar connected: book straight onto it, never a tap-to-
                # confirm link. Calendly is the source of truth — its
                # invitee.created webhook (routers/calendly_webhooks.py)
                # creates the appointment row (reminders, the client's
                # booking alert), so nothing is logged internally here;
                # doing so duplicated every booking.
                missing = [label for label, value in (("name", name), ("email", email)) if not value]
                if missing:
                    return (
                        f"Not booked yet — the calendar needs the lead's {' and '.join(missing)}, which "
                        "isn't on file. Ask them for just that in one short message (keep the time they "
                        "picked), then call propose_appointment again with the same date/time plus "
                        + " and ".join(f"lead_{m}" for m in missing) + "."
                    )
                try:
                    await calendly_integration.create_booking(
                        token, event_type_url, tool_input.get("date"), tool_input.get("time"), tz,
                        name, email, from_phone, reason,
                    )
                except Exception as e:
                    print(f"[response_ai] create_booking failed for client={client_id}: {e}", flush=True)
                    return (
                        f"Couldn't book {tool_input.get('date')} {tool_input.get('time')} — the calendar "
                        "rejected it (most likely that slot was just taken). Don't tell them they're booked. "
                        "Call check_availability again and offer them the next open times instead."
                    )
                await _mark_booked()
                return (
                    f"Confirmed on the calendar for {tool_input.get('date')} {tool_input.get('time')} "
                    f"({tz_name}) — they'll get a calendar confirmation by email. Tell them they're all set."
                )

            # No calendar connected: the internal log IS the booking, same as
            # a rep noting a booked time.
            row = await _log_internally()
            await _mark_booked()
            return f"Booked appointment id={row['id']} for {tool_input.get('date')} {tool_input.get('time')} ({tz_name})."
        except ValueError as e:
            return f"Booking failed: {e}"

    if tool_name == "escalate_to_human":
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE client_lead_conversations SET status = 'escalated' WHERE client_id = $1 AND phone = $2",
                client_id, from_phone,
            )
        return "Escalated to a human team member."

    if tool_name == "mark_unqualified":
        _pending_unqualified[(client_id, from_phone)] = (tool_input.get("reason") or "").strip() or "Not a fit"
        return ("Marked Unqualified. Send one short, polite closing text now; after this turn they get no "
                "further automated messages.")

    return f"Unknown tool: {tool_name}"
