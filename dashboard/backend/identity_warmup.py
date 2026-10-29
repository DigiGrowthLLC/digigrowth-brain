"""Warm-up engine for email_send_identities (DigiGrowth's own cold-outreach
mailboxes), rebuilt 2026-10-29 to do what Instantly's warm-up does instead
of paying for it (Dylan's call). See context/cold-email-deliverability.md.

What Instantly does, and where it lives here:
  - A pool of mailboxes emailing each other: every non-paused identity
    (warming, active, and partner inboxes) is in the pool. Warming/active
    identities send openers on a ramp; partners send PARTNER_DAILY openers
    a day into the sending mailboxes for extra inbound volume. The pool is
    only as big as the mailboxes added to it: Instantly's edge is thousands
    of strangers' inboxes, so add partner inboxes on different providers.
  - Unique, human-looking conversations: every opener/reply is written by
    Claude (_write_opener/_write_reply, falling back to a local phrase bank)
    on a varied everyday topic. No links, no sales words.
  - A filter tag: each thread carries a 7-character code on the last line
    (Instantly's "warmup filter tag") that ties received mail to its thread.
  - Ramp: "start" openers/day on day 1, +"increase_per_day" each sending
    day, up to "daily_limit". Warm-up NEVER stops: once the ramp tops out
    (status 'complete') it keeps going at daily_limit, active or not.
  - Reply rate: each opener is answered with probability reply_rate (30%,
    or reply_rate_active = 40% when the sender is cold-sending), and an
    answered thread runs 2-4 messages, threaded properly under the original.
  - Receiving side: wherever a warm-up email landed (inbox, Promotions,
    spam) is recorded as its placement, then it's rescued (not-spam / moved
    to Primary), opened, marked important and filed under a grey "Warmup"
    label (email_identities.warmup_engage).
  - Health score: % of an identity's warm-up mail that did NOT land in spam
    over the last 7 days. run_health_check() (daily) pulls an active
    identity out of cold sending (back to 'warming') if it drops below
    HEALTH_FLOOR, or if its cold-send bounce rate tops BOUNCE_CEILING, and
    puts a To-Do on Dylan's list.
  - Human hours: everything that sends runs Mon-Fri 8am-6pm Eastern, spread
    randomly across the day rather than at fixed intervals.

Settings (all optional) are a JSON object in dialer_settings under
'identity_warmup_settings' — keys of _DEFAULT_SETTINGS.

Correctness-critical invariant: once an identity is 'active', its inbox
holds BOTH warm-up mail and real prospect replies. Only mail whose sender is
another row in email_send_identities is ever treated as warm-up; a real
lead's message is never engaged with or auto-replied to.
"""
import json
import random
import re
import secrets
import string
from datetime import date, datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

import email_identities
from db import get_pool

_TZ = ZoneInfo("America/New_York")
_DAY_START_HOUR, _DAY_END_HOUR = 8, 18
_OPENER_TICK_MINUTES = 20  # main.py's identity-warmup-touches interval

_DEFAULT_SETTINGS = {
    "start": 2,               # openers on day 1
    "increase_per_day": 1,    # the SOP's Instantly setting
    "daily_limit": 20,        # ramp ceiling, kept forever after
    "reply_rate": 30,         # % of openers that get a reply
    "reply_rate_active": 40,  # same, for identities that are cold-sending
    "partner_daily": 5,       # openers/day each partner inbox sends into the pool
}
# Never more than this per identity per day, whatever the settings say.
WARMUP_DAILY_MAX = 25

HEALTH_FLOOR = 90         # % — below this an active identity is pulled
MIN_HEALTH_SAMPLES = 10   # placements needed before the score counts
BOUNCE_CEILING = 8        # % — the SOP's max bounce rate
MIN_BOUNCE_SENDS = 20

# A backlog (e.g. after an outage) trickles out a few per tick rather than
# bursting — a burst from one mailbox is exactly what spam filters flag.
_MAX_REPLIES_PER_TICK = 3

_TAG_RE = re.compile(r"^\s*([A-Z0-9]{7})\s*$", re.M)
_LEGACY_TAG_RE = re.compile(r"\[warmup:([^\]]+)\]")

_MODEL = "claude-haiku-5-5"
_TOPICS = [
    "rescheduling a coffee catch-up", "a book recommendation", "notes from a conference talk",
    "feedback on a draft document", "planning a team lunch", "a question about a spreadsheet",
    "confirming a call time next week", "thanks for an introduction", "a podcast episode worth hearing",
    "moving a deadline by a couple of days", "sharing how a project went", "a restaurant suggestion",
    "asking for a contractor recommendation", "weekend plans and a hike", "updating a shared checklist",
    "a software tool that saved time", "checking in after a trip", "splitting tasks for a small project",
    "a quick favor: reviewing a few slides", "following up on a phone conversation",
    "a new gym or running route", "an article about productivity", "planning a workshop agenda",
    "a printer/office supply question", "comparing notes on a training course", "a parking change at the office",
    "booking a room for a meeting", "sharing a recipe someone asked for", "how a client meeting went",
    "a reminder about an upcoming event",
]
_SYSTEM = (
    "You write short everyday emails between two people who know each other professionally. "
    "Plain text only: no links, no emojis, no bullet points, no attachments mentioned, no prices, "
    "nothing promotional or salesy (avoid words like free, guarantee, offer, deal, discount, click). "
    "Sound like a real person typing quickly: natural, a little casual, varied sentence length. "
    "Greet without using the recipient's name. Sign off with the sender's first name only."
)
_FALLBACK_SUBJECTS = [
    "Quick question", "Next week", "Following up", "That article", "Thursday?", "Notes from today",
    "One more thing", "Re-check on the plan", "Thanks again", "Small update", "Got a minute?", "Catching up",
]
_FALLBACK_OPENERS = [
    "Hope your week is going well.", "Hey, hope things are good on your end.", "Hi, quick one for you.",
    "Hey there, been meaning to send this.", "Hi, hope you had a good weekend.",
]
_FALLBACK_MIDDLES = [
    "Are you still good to move our call to later in the week?",
    "I finally read that piece you mentioned and it was better than I expected.",
    "Could you take a look at the outline when you get a chance? No rush at all.",
    "We pushed the planning session back a few days, so there is a bit more time.",
    "Do you remember the name of the place we went last month? Trying to book it again.",
    "I tried the approach you suggested and it saved me a good hour.",
    "Wanted to check whether Tuesday or Wednesday works better for you.",
]
_FALLBACK_REPLIES = [
    "Thanks for the note. That works for me, let's go with that.",
    "Good to hear from you. Yes, I can take a look later today.",
    "Appreciate it. Wednesday is better on my end if that still works.",
    "Ha, I was just thinking about that. Sounds good to me.",
    "Thanks, that's helpful. I'll circle back once I've had a look.",
    "Makes sense. Let me check my calendar and confirm tomorrow.",
]


# ── Settings + ramp ─────────────────────────────────────────────────────────

async def get_settings() -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        raw = await conn.fetchval("SELECT value FROM dialer_settings WHERE key = 'identity_warmup_settings'")
    settings = dict(_DEFAULT_SETTINGS)
    if raw:
        try:
            parsed = json.loads(raw)
            settings.update({k: int(v) for k, v in parsed.items() if k in _DEFAULT_SETTINGS})
        except Exception:
            pass
    settings["daily_limit"] = min(settings["daily_limit"], WARMUP_DAILY_MAX)
    return settings


def day_target(current_day: int | None, settings: dict) -> int:
    day = max(current_day or 1, 1)
    return min(settings["start"] + settings["increase_per_day"] * (day - 1), settings["daily_limit"])


def ramp_days(settings: dict) -> int:
    """Sending days until the ramp reaches daily_limit."""
    step = max(settings["increase_per_day"], 1)
    return max(1, -(-(settings["daily_limit"] - settings["start"]) // step) + 1)


async def start_warmup(identity_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO identity_warmup (identity_id, status, started_at, current_day, sent_today, updated_at)
            VALUES ($1, 'running', now(), 1, 0, now())
            ON CONFLICT (identity_id) DO UPDATE SET
                status = 'running', started_at = now(), completed_at = NULL,
                current_day = 1, sent_today = 0, replied_today = 0,
                last_sent_date = NULL, updated_at = now()
            """,
            identity_id,
        )


async def get_status(identity_id: int) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM identity_warmup WHERE identity_id = $1", identity_id)
    return dict(row) if row else None


def _roll_day(row: dict) -> dict:
    """Advances current_day / resets the daily counters when the date has
    moved on since the last send."""
    if row["last_sent_date"] == date.today():
        return row
    row = dict(row)
    if row["last_sent_date"] is not None:
        row["current_day"] = (row["current_day"] or 0) + 1
    row["sent_today"] = 0
    row["replied_today"] = 0
    return row


def _within_business_hours() -> bool:
    """A mailbox sending at 3am every night looks automated regardless of
    content or volume. Real people mostly send Mon-Fri, business hours."""
    now = datetime.now(_TZ)
    return now.weekday() < 5 and _DAY_START_HOUR <= now.hour < _DAY_END_HOUR


def _should_send_now(remaining: int) -> bool:
    """Spreads the day's remaining sends randomly over the remaining ticks,
    instead of firing them at the top of the day on a fixed beat."""
    if remaining <= 0:
        return False
    now = datetime.now(_TZ)
    minutes_left = (_DAY_END_HOUR * 60) - (now.hour * 60 + now.minute)
    ticks_left = max(1, minutes_left // _OPENER_TICK_MINUTES)
    return random.random() < remaining / ticks_left


# ── Content ─────────────────────────────────────────────────────────────────

def _first_name(identity: dict) -> str:
    local = identity["mailbox_email"].split("@")[0].lower()
    return "Dylan" if "dylan" in local else re.sub(r"[^a-z]", "", local).title() or "Dylan"


def _new_thread_key() -> str:
    """Instantly-style 7-character filter tag: letters + at least one digit."""
    while True:
        key = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(7))
        if any(c.isdigit() for c in key) and any(c.isalpha() for c in key):
            return key


def _thread_key(body: str) -> str | None:
    legacy = _LEGACY_TAG_RE.search(body or "")
    if legacy:
        return legacy.group(1).strip()
    return next((k for k in _TAG_RE.findall(body or "")
                 if any(c.isdigit() for c in k) and any(c.isalpha() for c in k)), None)


async def _claude(prompt: str) -> str | None:
    try:
        import anthropic
        import os

        client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        response = await client.messages.create(
            model=_MODEL, max_tokens=400, system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        if response.stop_reason != "end_turn":
            return None
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        return text if "http" not in text.lower() else None
    except Exception as e:
        print(f"[identity_warmup] content generation failed, using phrase bank: {e}")
        return None


async def _write_opener(sender_name: str) -> tuple[str, str]:
    text = await _claude(
        f"Write a new email (not a reply) about: {random.choice(_TOPICS)}. "
        f"Sender's first name: {sender_name}. {random.randint(25, 80)} words. "
        "Sometimes end with a light question. Format exactly:\nSubject: <2-6 word subject>\n\n<body>"
    )
    if text and text.lower().startswith("subject:"):
        subject, _, body = text.partition("\n")
        subject = subject.split(":", 1)[1].strip().strip('"')
        if subject and body.strip():
            return subject, body.strip()
    body = f"{random.choice(_FALLBACK_OPENERS)} {random.choice(_FALLBACK_MIDDLES)}\n\n{sender_name}"
    return random.choice(_FALLBACK_SUBJECTS), body


async def _write_reply(history: list[str], sender_name: str) -> str:
    convo = "\n\n---\n\n".join(history[-3:])
    text = await _claude(
        f"Here is an email thread so far (oldest first):\n\n{convo}\n\n"
        f"Write {sender_name}'s reply to the latest message, {random.randint(15, 60)} words. "
        "Respond to what it actually says. Output only the reply body."
    )
    if text and not text.lower().startswith("subject:"):
        return text
    return f"{random.choice(_FALLBACK_REPLIES)}\n\n{sender_name}"


def _strip_tag(body: str) -> str:
    return _LEGACY_TAG_RE.sub("", _TAG_RE.sub("", body or "")).strip()


# ── Openers ─────────────────────────────────────────────────────────────────

async def _opens_today(conn, identity_id: int) -> int:
    midnight = datetime.now(_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    return await conn.fetchval(
        "SELECT count(*) FROM identity_warmup_log WHERE from_identity_id = $1 AND direction = 'opener' "
        "AND sent_at >= $2",
        identity_id, midnight,
    )


def _pick_recipient(sender: dict, pool_ids: list[dict], cursor: int) -> dict | None:
    """Rotate through the rest of the pool, other providers/domains first so
    traffic isn't one narrow A<->B pattern."""
    others = [i for i in pool_ids if i["id"] != sender["id"]]
    if sender["status"] == "partner":
        others = [i for i in others if i["status"] in ("warming", "active")]
    if not others:
        return None
    others.sort(key=lambda i: (i["domain"] == sender["domain"], i["id"]))
    return others[cursor % len(others)]


async def _send_opener(conn, sender: dict, recipient: dict, day_number: int, reply_rate: int) -> bool:
    key = _new_thread_key()
    subject, body = await _write_opener(_first_name(sender))
    planned = 1 if random.randint(1, 100) > reply_rate else random.choice([2, 2, 3, 4])
    try:
        message_id = await email_identities.send_from_identity(
            sender, recipient["mailbox_email"], subject, f"{body}\n\n{key}",
        )
    except Exception as e:
        print(f"[identity_warmup] opener failed {sender['mailbox_email']} -> {recipient['mailbox_email']}: {e}")
        return False
    await conn.execute(
        """
        INSERT INTO identity_warmup_log (from_identity_id, to_identity_id, day_number, direction, thread_key,
                                         provider_message_id, subject, body, turn, planned_turns)
        VALUES ($1, $2, $3, 'opener', $4, $5, $6, $7, 1, $8)
        """,
        sender["id"], recipient["id"], day_number, key, message_id, subject, body, planned,
    )
    return True


async def send_due_touches():
    """Opener job (main.py, every _OPENER_TICK_MINUTES): at most one opener
    per pool mailbox per tick, randomly spread to hit each one's daily
    target by end of business."""
    if not _within_business_hours():
        return
    settings = await get_settings()
    pool = await get_pool()
    async with pool.acquire() as conn:
        identities = [dict(r) for r in await conn.fetch(
            "SELECT * FROM email_send_identities WHERE status != 'paused' AND oauth_refresh_token IS NOT NULL"
        )]
        warmups = {r["identity_id"]: dict(r) for r in await conn.fetch("SELECT * FROM identity_warmup")}

        for sender in identities:
            if sender["status"] == "partner":
                remaining = settings["partner_daily"] - await _opens_today(conn, sender["id"])
                if not _should_send_now(remaining):
                    continue
                cursor = random.randint(0, 1000)
                recipient = _pick_recipient(sender, identities, cursor)
                if recipient:
                    await _send_opener(conn, sender, recipient, 0, settings["reply_rate"])
                continue

            row = warmups.get(sender["id"])
            if not row or row["status"] not in ("running", "complete"):
                continue  # warm-up never started for this identity
            row = _roll_day(row)
            target = day_target(row["current_day"], settings)
            if not _should_send_now(target - row["sent_today"]):
                continue
            recipient = _pick_recipient(sender, identities, row["partner_cursor"])
            if not recipient:
                continue
            rate = settings["reply_rate_active"] if sender["status"] == "active" else settings["reply_rate"]
            if not await _send_opener(conn, sender, recipient, row["current_day"], rate):
                continue
            status = "complete" if target >= settings["daily_limit"] else row["status"]
            await conn.execute(
                """
                UPDATE identity_warmup SET current_day = $2, sent_today = $3, replied_today = $4,
                    partner_cursor = partner_cursor + 1, status = $5,
                    completed_at = CASE WHEN $5 = 'complete' THEN coalesce(completed_at, now()) ELSE completed_at END,
                    last_sent_date = CURRENT_DATE, last_sent_at = now(), updated_at = now()
                WHERE identity_id = $1
                """,
                sender["id"], row["current_day"], row["sent_today"] + 1, row["replied_today"], status,
            )


# ── Receiving side + replies ────────────────────────────────────────────────

async def _record_received(conn, identity: dict, msg: dict, sender_id: int):
    """Match a received warm-up message to its log row, engage with it
    (rescue / open / important / label), and record where it landed."""
    if await conn.fetchval("SELECT 1 FROM identity_warmup_log WHERE received_message_id = $1", msg["message_id"]):
        return
    key = _thread_key(msg["body"])
    row = None
    if key:
        row = await conn.fetchrow(
            """SELECT id FROM identity_warmup_log
               WHERE thread_key = $1 AND from_identity_id = $2 AND to_identity_id = $3 AND received_at IS NULL
               ORDER BY turn LIMIT 1""",
            key, sender_id, identity["id"],
        )
    placement = msg["placement"]
    try:
        rescued = await email_identities.warmup_engage(identity, msg)
    except Exception as e:
        print(f"[identity_warmup] engage failed on {identity['mailbox_email']}: {e}")
        rescued = False
    if row:
        await conn.execute(
            "UPDATE identity_warmup_log SET placement = $2, received_at = now(), received_message_id = $3, "
            "rescued = $4 WHERE id = $1",
            row["id"], placement, msg["message_id"], rescued,
        )
    if placement != "inbox":
        print(f"[identity_warmup] {msg['from_addr']} -> {identity['mailbox_email']} landed in {placement}"
              f"{' (rescued)' if rescued else ''}")


async def _send_pending_replies(conn, identity: dict, by_id: dict, settings: dict) -> int:
    """Next turn of every thread this identity received a message in and is
    due to answer. Each reply waits a per-message 10-120 minutes after
    receipt so replies don't come back instantly."""
    rows = await conn.fetch(
        """
        SELECT l.*, o.planned_turns AS thread_turns
        FROM identity_warmup_log l
        JOIN identity_warmup_log o ON o.thread_key = l.thread_key AND o.direction = 'opener'
        WHERE l.to_identity_id = $1 AND l.received_message_id IS NOT NULL
          AND o.sent_at > now() - interval '7 days'
          AND l.turn < coalesce(o.planned_turns, 2)
          AND l.received_at < now() - make_interval(mins => 10 + (l.id * 37) % 110)
          AND NOT EXISTS (SELECT 1 FROM identity_warmup_log n
                          WHERE n.thread_key = l.thread_key AND n.turn = l.turn + 1)
        ORDER BY l.received_at
        LIMIT $2
        """,
        identity["id"], _MAX_REPLIES_PER_TICK,
    )
    sent = 0
    for row in rows:
        partner = by_id.get(row["from_identity_id"])
        if not partner:
            continue
        history = [
            _strip_tag(r["body"] or "") for r in await conn.fetch(
                "SELECT body FROM identity_warmup_log WHERE thread_key = $1 AND body IS NOT NULL ORDER BY turn",
                row["thread_key"],
            )
        ] or ["(a short friendly email)"]
        body = await _write_reply(history, _first_name(identity))
        try:
            message_id = await email_identities.warmup_reply(
                identity, row["received_message_id"], f"{body}\n\n{row['thread_key']}",
            )
        except Exception as e:
            print(f"[identity_warmup] reply failed for thread {row['thread_key']}: {e}")
            continue
        await conn.execute(
            """
            INSERT INTO identity_warmup_log (from_identity_id, to_identity_id, day_number, direction, thread_key,
                                             provider_message_id, subject, body, turn, planned_turns)
            VALUES ($1, $2, 0, 'reply', $3, $4, $5, $6, $7, $8)
            """,
            identity["id"], partner["id"], row["thread_key"], message_id,
            row["subject"] if (row["subject"] or "").lower().startswith("re:") else f"Re: {row['subject'] or ''}".strip(),
            body, row["turn"] + 1, row["thread_turns"] or 2,
        )
        await conn.execute(
            "UPDATE identity_warmup SET replied_today = replied_today + 1, updated_at = now() WHERE identity_id = $1",
            identity["id"],
        )
        sent += 1
    return sent


async def send_due_replies():
    """Every 10 min (main.py). For each non-paused identity:
      1. Inbox poll (email_identities.sync_identity_inbox) for real lead
         replies and bounces. Always runs, any hour: a lead's reply must
         stop the Email Handoff sequence promptly.
      2. Business hours only: archive newsletter/DMARC mail, find + engage
         with warm-up mail wherever it landed, and send due replies."""
    settings = await get_settings()
    in_hours = _within_business_hours()
    pool = await get_pool()
    async with pool.acquire() as conn:
        identities = [dict(r) for r in await conn.fetch(
            "SELECT * FROM email_send_identities WHERE status != 'paused' AND oauth_refresh_token IS NOT NULL"
        )]
    by_id = {i["id"]: i for i in identities}
    by_email = {i["mailbox_email"].lower(): i["id"] for i in identities}

    for identity in identities:
        try:
            await email_identities.sync_identity_inbox(identity)
        except Exception as e:
            print(f"[identity_warmup] inbox poll failed for {identity['mailbox_email']}: {e}")
        if not in_hours:
            continue

        if identity["status"] != "partner":
            try:
                await email_identities.archive_newsletters(identity)
            except Exception as e:
                print(f"[identity_warmup] newsletter archive failed for {identity['mailbox_email']}: {e}")

        senders = [e for e in by_email if e != identity["mailbox_email"].lower()]
        try:
            received = await email_identities.warmup_scan(identity, senders)
        except Exception as e:
            print(f"[identity_warmup] warm-up scan failed for {identity['mailbox_email']}: {e}")
            received = []
        async with pool.acquire() as conn:
            for msg in received:
                await _record_received(conn, identity, msg, by_email[msg["from_addr"]])
            await _send_pending_replies(conn, identity, by_id, settings)


# ── Daily health check ──────────────────────────────────────────────────────

async def _open_todo(conn, text: str, description: str):
    if await conn.fetchval("SELECT 1 FROM todos WHERE text = $1 AND NOT done", text):
        return
    await conn.execute(
        "INSERT INTO todos (text, description, due_date) VALUES ($1, $2, CURRENT_DATE)", text, description,
    )


async def run_health_check() -> list[dict]:
    """Daily (main.py, weekdays 5:30pm ET), also POST
    /api/email-identities/health-check. Per sending identity: warm-up
    health score (7 days), Promotions share, and cold-send bounce rate
    (14 days). An active identity below HEALTH_FLOOR or above
    BOUNCE_CEILING goes back to 'warming' (its pending follow-ups hold; new
    Touch 1s route to other active identities) and Dylan gets a To-Do.
    Domains on any blacklist also get a To-Do."""
    import domain_health

    pool = await get_pool()
    results = []
    async with pool.acquire() as conn:
        identities = await conn.fetch("SELECT * FROM email_send_identities WHERE status != 'partner'")
        for identity in identities:
            stats = await conn.fetchrow(
                """SELECT count(*) AS n,
                          count(*) FILTER (WHERE placement = 'spam') AS spam,
                          count(*) FILTER (WHERE placement = 'promotions') AS promo
                   FROM identity_warmup_log
                   WHERE from_identity_id = $1 AND placement IS NOT NULL AND received_at > now() - interval '7 days'""",
                identity["id"],
            )
            sends = await conn.fetchrow(
                """SELECT count(*) AS n, count(*) FILTER (WHERE bounced_at IS NOT NULL) AS bounced
                   FROM email_messages
                   WHERE direction = 'outbound' AND thread_id LIKE $1 AND sent_at > now() - interval '14 days'""",
                f"identity-{identity['id']}-%",
            )
            score = round(100 * (stats["n"] - stats["spam"]) / stats["n"], 1) if stats["n"] else None
            promo = round(100 * stats["promo"] / stats["n"], 1) if stats["n"] else None
            bounce = round(100 * sends["bounced"] / sends["n"], 1) if sends["n"] else None
            await conn.execute(
                """UPDATE email_send_identities SET health_score = $2, health_samples = $3, promotions_rate = $4,
                       bounce_rate = $5, health_checked_at = now() WHERE id = $1""",
                identity["id"], score, stats["n"], promo, bounce,
            )

            reasons = []
            if score is not None and stats["n"] >= MIN_HEALTH_SAMPLES and score < HEALTH_FLOOR:
                reasons.append(f"warm-up health {score}% (below {HEALTH_FLOOR}%)")
            if bounce is not None and sends["n"] >= MIN_BOUNCE_SENDS and bounce > BOUNCE_CEILING:
                reasons.append(f"bounce rate {bounce}% (above {BOUNCE_CEILING}%)")
            if reasons and identity["status"] == "active":
                reason = "; ".join(reasons)
                await conn.execute(
                    "UPDATE email_send_identities SET status = 'warming', demoted_at = now(), demoted_reason = $2, "
                    "updated_at = now() WHERE id = $1",
                    identity["id"], reason,
                )
                await _open_todo(
                    conn, f"Cold email: {identity['mailbox_email']} pulled from sending",
                    f"Auto-moved back to warm-up only: {reason}. Per the deliverability SOP, leave it warming and "
                    "activate a reserve mailbox (Email Identities). See context/cold-email-deliverability.md.",
                )
            results.append({"mailbox": identity["mailbox_email"], "health_score": score, "samples": stats["n"],
                            "promotions_rate": promo, "bounce_rate": bounce, "sends": sends["n"],
                            "demoted": bool(reasons and identity["status"] == "active")})

        domains = sorted({domain_health._org_domain(i["domain"].lower()) for i in identities})
        for domain in domains:
            listed = [name for name, hit in (await domain_health.check_blacklists(domain)).items() if hit]
            if listed:
                await _open_todo(
                    conn, f"Cold email: {domain} is blacklisted",
                    f"Listed on: {', '.join(listed)}. At 3+ lists the SOP says replace the domain and let it "
                    "cool off in warm-up. See context/cold-email-deliverability.md.",
                )
    return results
