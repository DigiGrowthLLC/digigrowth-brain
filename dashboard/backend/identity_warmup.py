"""Cross-provider warm-up engine for email_send_identities — sibling to
email_warmup.py (the per-CLIENT, one-way, Gmail-only warm-up), not a
modification of it. This engine is keyed by identity_id, spans both Google
and Microsoft identities, and ramps reputation via REAL threaded
opener+reply exchanges between identities rather than one-way sends to a
fixed seed list.

Two independent, idempotent jobs (both registered in main.py) that converge
into full threads over a few polling cycles:

  send_due_touches() — for each 'warming' identity under its day's send
  target, pick a round-robin partner (any other identity, any status —
  receiving/replying doesn't cost reputation, only cold-sending to
  strangers does) and send a threaded "opener" with a generated thread_key.

  send_due_replies() — polls each identity's inbox (via
  email_identities.sync_identity_inbox) for inbound mail from another
  identity, and for anything matching an open thread_key this identity
  hasn't yet replied to, sends an auto-reply and logs it. No artificial
  delay is added — replying only on this job's own poll interval already
  means replies never land instantly, which is enough to avoid an
  obviously-bot cadence without blocking the shared scheduler loop.

Status gating: 'warming' identities are the only ones eligible to be picked
by email_identities.pick_identity() for real lead sends — that's enforced
there (status='active' only), not here. An identity is manually promoted
warming -> active once its ramp completes (no auto-promotion, same
philosophy as email_warmup.py: gating real-outreach eligibility stays a
judgment call). 'paused' identities are skipped by both jobs below.

Correctness-critical invariant: once an identity is 'active', its inbox
holds BOTH warm-up cross-thread mail and real prospect replies.
send_due_replies() only ever auto-replies to mail whose sender is another
row in email_send_identities (email_identities.sync_identity_inbox already
enforces this split before handing candidates here) — it must never
auto-reply to a real lead.
"""
import random
import uuid
from datetime import date, datetime, timezone as dt_timezone

import email_identities
from db import get_pool

# Capped at 40/day (lowered 2026-09-22 from an earlier 60), matching
# email_warmup.py's client-side ramp — see that module's comment for why:
# a single mailbox's sustainable volume tops out ~30-50/day regardless of
# warm status. Doubly true here early on with only 2-3 identities per
# provider: with few partners, all traffic is a narrow A<->B pattern, so
# keeping absolute volume conservative matters more, not less, until more
# identities exist to spread partner variety across.
_DEFAULT_SCHEDULE = [2, 3, 5, 8, 11, 15, 20, 25, 31, 40]

# How many backlog replies a single identity may send in ONE poll tick.
# Without this cap, a long outage (like the Graph auth bug that blocked
# Dylan MS for ~2 days) lets a huge backlog of unread opener threads queue
# up, and the very next successful poll fires ALL of them back-to-back —
# observed directly: 16 replies in one tick once that bug was fixed. A
# burst of near-simultaneous sends from one mailbox is exactly the kind of
# pattern spam/abuse heuristics (and the provider's own API rate limits)
# flag, regardless of how "warmed" the mailbox is. Trickling the backlog
# down at a few per tick keeps every send at the same natural pace as
# openers, even when catching up.
_MAX_REPLIES_PER_TICK = 3


def _within_business_hours() -> bool:
    """Same reasoning as email_warmup.py's _within_business_hours — a
    mailbox sending/replying at 3am every night looks automated regardless
    of content, volume, or warm-up status. Real humans mostly send Mon-Fri,
    business hours."""
    from zoneinfo import ZoneInfo

    now = datetime.now(ZoneInfo("America/New_York"))
    return now.weekday() < 5 and 8 <= now.hour < 18

_OPENER_SUBJECTS = [
    "Quick one for you",
    "Got a sec?",
    "Following up",
    "Question for you",
]
_OPENER_BODIES = [
    "Hey — hope your week's going well. Wanted to check in, anything new on your end?",
    "Hi there, just circling back on this. Let me know your thoughts when you get a chance.",
    "Hope you're doing well. Curious to hear how things have been going lately.",
]
_REPLY_BODIES = [
    "Thanks for reaching out — things have been good, staying busy. How about you?",
    "Appreciate you following up. All good here, talk soon.",
    "Good to hear from you. Everything's on track over here.",
]


async def get_schedule() -> list[int]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT value FROM dialer_settings WHERE key = 'identity_warmup_schedule'")
    if row and row["value"]:
        import json
        try:
            parsed = json.loads(row["value"])
            if isinstance(parsed, list) and all(isinstance(x, int) for x in parsed):
                return parsed
        except Exception:
            pass
    return _DEFAULT_SCHEDULE


async def start_warmup(identity_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO identity_warmup (identity_id, status, started_at, current_day, sent_today, updated_at)
            VALUES ($1, 'running', now(), 1, 0, now())
            ON CONFLICT (identity_id) DO UPDATE SET
                status = 'running', started_at = now(), completed_at = NULL,
                current_day = 1, sent_today = 0, replied_today = 0, updated_at = now()
            """,
            identity_id,
        )


async def get_status(identity_id: int) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM identity_warmup WHERE identity_id = $1", identity_id)
    return dict(row) if row else None


def _roll_day(row: dict, schedule: list[int]) -> dict:
    """Advances current_day/resets sent_today when the calendar date has
    moved on, and flips to 'complete' once past the schedule length —
    mirrors email_warmup.py's _roll_day exactly, re-keyed on identity_id."""
    today = date.today()
    if row["last_sent_date"] == today:
        return row
    row = dict(row)
    if row["last_sent_date"] is not None:
        row["current_day"] = (row["current_day"] or 0) + 1
    row["sent_today"] = 0
    row["replied_today"] = 0
    if row["current_day"] > len(schedule):
        row["status"] = "complete"
        row["completed_at"] = datetime.now(dt_timezone.utc)
    return row


async def send_due_touches():
    """Sends one warm-up opener per running identity per tick (short poll
    interval spreads volume across the day), if that identity is still
    under today's target."""
    if not _within_business_hours():
        return

    pool = await get_pool()
    schedule = await get_schedule()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT iw.*, s.provider, s.mailbox_email, s.status AS identity_status
            FROM identity_warmup iw
            JOIN email_send_identities s ON s.id = iw.identity_id
            WHERE iw.status = 'running' AND s.status != 'paused'
            """
        )
        if not rows:
            return

        all_identities = {r["id"]: dict(r) for r in await conn.fetch("SELECT * FROM email_send_identities")}

        for record in rows:
            row = _roll_day(dict(record), schedule)
            identity_id = row["identity_id"]

            if row["status"] == "complete":
                await conn.execute(
                    "UPDATE identity_warmup SET status = 'complete', completed_at = now(), updated_at = now() "
                    "WHERE identity_id = $1",
                    identity_id,
                )
                continue

            day_target = schedule[min(row["current_day"], len(schedule)) - 1]
            if row["sent_today"] >= day_target:
                continue

            candidates = [i for i in all_identities.values() if i["id"] != identity_id]
            if not candidates:
                continue
            partner = candidates[row["partner_cursor"] % len(candidates)]

            identity = all_identities[identity_id]
            thread_key = f"{identity_id}-{partner['id']}-{uuid.uuid4().hex[:8]}"
            subject = random.choice(_OPENER_SUBJECTS)
            body = f"{random.choice(_OPENER_BODIES)}\n\n[warmup:{thread_key}]"

            try:
                message_id = await email_identities.send_from_identity(identity, partner["mailbox_email"], subject, body)
            except Exception as e:
                print(f"[identity_warmup] opener failed {identity['mailbox_email']} -> {partner['mailbox_email']}: {e}")
                continue

            await conn.execute(
                """
                INSERT INTO identity_warmup_log (from_identity_id, to_identity_id, day_number, direction, thread_key, provider_message_id)
                VALUES ($1, $2, $3, 'opener', $4, $5)
                """,
                identity_id, partner["id"], row["current_day"], thread_key, message_id,
            )
            await conn.execute(
                """
                UPDATE identity_warmup SET current_day = $2, sent_today = $3, partner_cursor = partner_cursor + 1,
                    last_sent_date = CURRENT_DATE, last_sent_at = now(), updated_at = now()
                WHERE identity_id = $1
                """,
                identity_id, row["current_day"], row["sent_today"] + 1,
            )


async def send_due_replies():
    """Polls every non-paused identity's inbox for warm-up candidates
    (mail from a sibling identity) and auto-replies to any open thread this
    identity hasn't replied to yet — at most _MAX_REPLIES_PER_TICK per
    identity per tick, so a backlog (e.g. after an outage) trickles out at
    a natural pace instead of bursting all at once.

    The inbox poll itself (sync_identity_inbox) always runs regardless of
    business hours — a real lead's reply must be captured and recorded
    promptly whenever it arrives, since email_handoff_sequence.py's
    reply-stop check depends on it. Only the WARM-UP auto-reply SEND is
    gated to business hours; skipping it this tick is harmless and
    idempotent — nothing is marked replied until a reply actually sends, so
    it's simply retried next tick."""
    send_replies_allowed = _within_business_hours()

    pool = await get_pool()
    async with pool.acquire() as conn:
        identities = await conn.fetch("SELECT * FROM email_send_identities WHERE status != 'paused'")

    for record in identities:
        identity = dict(record)
        try:
            result = await email_identities.sync_identity_inbox(identity)
        except Exception as e:
            print(f"[identity_warmup] inbox poll failed for {identity['mailbox_email']}: {e}")
            continue

        if not send_replies_allowed:
            continue

        sent_this_tick = 0
        for msg in result["warmup_candidates"]:
            if sent_this_tick >= _MAX_REPLIES_PER_TICK:
                break
            thread_key = None
            for token in msg["body"].split("[warmup:"):
                if "]" in token:
                    thread_key = token.split("]")[0].strip()
                    break
            if not thread_key:
                continue

            pool = await get_pool()
            async with pool.acquire() as conn:
                already_replied = await conn.fetchval(
                    "SELECT 1 FROM identity_warmup_log WHERE thread_key = $1 AND direction = 'reply' "
                    "AND from_identity_id = $2",
                    thread_key, identity["id"],
                )
                if already_replied:
                    continue

                original = await conn.fetchrow(
                    "SELECT * FROM identity_warmup_log WHERE thread_key = $1 AND direction = 'opener' ORDER BY sent_at LIMIT 1",
                    thread_key,
                )
                if not original or original["to_identity_id"] != identity["id"]:
                    continue  # this thread isn't addressed to this identity

                opener_sender = await conn.fetchrow(
                    "SELECT * FROM email_send_identities WHERE id = $1", original["from_identity_id"],
                )
                if not opener_sender:
                    continue
            opener_sender = dict(opener_sender)

            # No artificial sleep here (would block the shared scheduler
            # loop for other jobs) — send_due_replies() itself only runs on
            # a fixed poll interval, so a reply landing "same tick" still
            # only ever appears within one poll interval of the opener,
            # which already reads as a natural, non-instant cadence.
            body = f"{random.choice(_REPLY_BODIES)}\n\n[warmup:{thread_key}]"
            try:
                message_id = await email_identities.send_from_identity(
                    identity, opener_sender["mailbox_email"], "Re: warmup", body,
                )
            except Exception as e:
                print(f"[identity_warmup] reply failed for thread {thread_key}: {e}")
                continue

            pool = await get_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO identity_warmup_log (from_identity_id, to_identity_id, day_number, direction, thread_key, provider_message_id)
                    VALUES ($1, $2, 0, 'reply', $3, $4)
                    """,
                    identity["id"], opener_sender["id"], thread_key, message_id,
                )
                await conn.execute(
                    "UPDATE identity_warmup SET replied_today = replied_today + 1, updated_at = now() WHERE identity_id = $1",
                    identity["id"],
                )
            sent_this_tick += 1
