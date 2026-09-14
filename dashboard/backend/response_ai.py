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

V1 scope: SMS only. Calendar availability is read-only, via Calendly's API
(calendly_integration.py) when a client has connected a Personal Access
Token (client_marketing_config.calendly_api_token) — the check_availability
tool looks up real open slots so the agent doesn't propose an already-taken
time, but booking still happens the same way it always has: logged
directly into this system (create_appointment_row), same trust level as a
rep manually noting a booked time today. Calendly's API has no endpoint to
create a CONFIRMED booking on someone else's behalf (an invitee always
completes that on Calendly's own page), so this is as far as automation
goes without a client-side click — confirmed scope as of 2026-09-14. A
client with no token connected just gets asked for their preferred
day/time as before (check_availability says so and the model falls back).

Phase 2 (not built): Meta Lead Ads ingestion, once Dylan has a Meta app +
page webhook access — a new POST /webhooks/meta-leadgen endpoint would
verify Meta's webhook challenge, pull lead data via Graph API using the
leadgen_id, resolve to a client via a new client_marketing_config column
(e.g. meta_page_id), create/upsone the contacts row the same way
_get_or_create_contact() below already does, and call a new
initiate_conversation() entry point to send the first outbound message
proactively — handle_inbound_sms() below only ever reacts to an inbound
message, it never starts a thread.
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
isn't connected, ask for their preferred day and time instead. Either way, confirm the agreed \
time back to them in one message, then call propose_appointment.
- If the lead can't make the time(s) you offered, call check_availability again with after_date \
set to the day AFTER the day you just offered — never re-offer the same day, and never repeat the \
exact same times you already gave them.
- If the lead asks for something outside what you were told, seems upset, asks for a refund or \
files a complaint, or you're not confident how to respond, call escalate_to_human and let them \
know a team member will follow up.
- Never claim an appointment is booked unless you actually called propose_appointment \
successfully in this same turn.
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
        "description": "Book a tentative appointment for this lead once they've agreed to a specific day and time.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "YYYY-MM-DD"},
                "time": {"type": "string", "description": "HH:MM in 24h format"},
                "notes": {"type": "string", "description": "Anything worth noting for the business, e.g. what the lead is coming in for."},
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
]


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


async def _get_or_create_contact(conn, client_id: int, phone: str) -> str | None:
    """Same ownership rules as client_portal.py's portal_create_lead() —
    never claim a phone number that's already someone else's anchor contact
    or another client's lead. Returns None (rather than raising) if the
    phone is already claimed elsewhere, so a booking still succeeds with
    contact_id=None rather than blocking the lead's reply over an edge case."""
    existing = await conn.fetchrow(
        "SELECT id, client_id, is_client_anchor FROM contacts WHERE phone = $1", phone,
    )
    if existing:
        if existing["is_client_anchor"] or (existing["client_id"] is not None and existing["client_id"] != client_id):
            return None
        return existing["id"]
    row = await conn.fetchrow(
        "INSERT INTO contacts (id, phone, status, client_id) VALUES ($1, $2, 'new', $3) RETURNING id",
        str(uuid.uuid4()), phone, client_id,
    )
    return row["id"]


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
    separate texts (see handle_inbound_sms)."""
    if not max_words:
        return [text]

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


def _build_system_prompt(
    business_name: str, context: str, sequence: list[str], max_words: int | None, rules: str,
    today_str: str,
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
            if conversation["status"] == "escalated":
                return  # a human has taken over this thread — stay silent

            messages = await _load_recent_messages(conn, client_id, from_phone)

        # asyncpg has no JSONB codec registered on this pool (matches
        # client_marketing.py's _decode_config) — comes back as a raw string.
        sequence = row["response_ai_sequence"]
        if isinstance(sequence, str):
            sequence = json.loads(sequence)
        max_words = row["response_ai_max_words"]

        tz_name = guess_timezone(from_phone)
        today_str = datetime.now(ZoneInfo(tz_name)).strftime("%A, %B %-d, %Y")

        system_prompt = _build_system_prompt(
            row["name"], row["response_ai_context"] or "", sequence or [], max_words, row["response_ai_rules"] or "",
            today_str,
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
    except Exception as e:
        print(f"[response_ai] handle_inbound_sms failed for client={client_id} phone={from_phone}: {e}")


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
                contact_id = await _get_or_create_contact(conn, client_id, from_phone)
            tz_name = guess_timezone(from_phone)
            # create_appointment_row acquires its own connection internally
            # (it's shared with the manual-booking HTTP route) — don't hold
            # one open across this call, just for the contact lookup above
            # and the status update below.
            row = await create_appointment_row({
                "contact_id": contact_id,
                "prospect_phone": from_phone,
                "date": tool_input.get("date"),
                "time": tool_input.get("time"),
                "timezone": tz_name,
            })
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE client_lead_conversations SET status = 'booked' WHERE client_id = $1 AND phone = $2",
                    client_id, from_phone,
                )
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

    return f"Unknown tool: {tool_name}"
