"""Email warm-up ramp for a client's own connected mailbox — the final step
of the "Set Up Email Marketing" guide in ClientsPanel.jsx.

A brand-new Workspace mailbox (even on a subdomain with valid SPF/DKIM/MX)
needs to build sending reputation before real cold outreach starts, or the
whole subdomain risks getting spam-flagged. This ramps the mailbox's daily
send volume up over a short schedule by sending one-way, no-reply emails to
a fixed internal seed list, and tracks day-by-day progress for the guide
modal to display.

State lives on one row per client in client_email_warmup (not
client_email_messages — that table feeds the client portal's Inbox Activity
panel and dashboard/analytics stats, which warm-up noise to internal seed
addresses has no business appearing in).

Real outreach sent through the same mailbox (client_email.send_client_email)
must never be gated, delayed, or throttled by warm-up status — this module
never sits in that call path's way. It only counts a real send toward that
day's ramp target via record_real_send(), so starting outreach mid-warmup
doesn't stack redundant seed volume on top of real volume. record_real_send
is best-effort and never raises: a bug here must never break a real send.

Schedule/seed list are global config (not per-client) stored in the existing
generic key/value table dialer_settings, editable without a code deploy.
"""
import asyncio
import base64
import json
from datetime import datetime, timezone as dt_timezone
from email.mime.text import MIMEText

import client_email
from db import get_pool

_SCHEDULE_KEY = "warmup_schedule"
_SEEDS_KEY = "warmup_seed_emails"

# Roughly doubling every 1-2 days — a short ramp on the assumption the
# subdomain's DNS (SPF/DKIM/MX) is already valid from the earlier guide
# steps, so this is warming the mailbox's own sending history, not proving
# out fresh DNS. Tune via the warmup_schedule dialer_settings key.
_DEFAULT_SCHEDULE = [3, 5, 8, 12, 17, 23, 30, 38, 47, 60]

_SUBJECTS = [
    "Quick check-in",
    "Following up",
    "Touching base",
    "Quick note",
    "Circling back",
]
_BODY = (
    "Hey,\n\nJust checking in — nothing urgent, wanted to keep this thread moving.\n\n"
    "Talk soon."
)


async def _get_schedule(conn) -> list[int]:
    value = await conn.fetchval("SELECT value FROM dialer_settings WHERE key = $1", _SCHEDULE_KEY)
    if not value:
        return _DEFAULT_SCHEDULE
    try:
        parsed = json.loads(value)
        return [int(n) for n in parsed] if parsed else _DEFAULT_SCHEDULE
    except (ValueError, TypeError):
        return _DEFAULT_SCHEDULE


async def _get_seed_emails(conn) -> list[str]:
    value = await conn.fetchval("SELECT value FROM dialer_settings WHERE key = $1", _SEEDS_KEY)
    if not value:
        return []
    return [addr.strip() for addr in value.split(",") if addr.strip()]


def _current_day_number(started_at, now) -> int:
    return (now.date() - started_at.date()).days + 1


async def start_warmup(client_id: int) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        has_mailbox = await conn.fetchval(
            "SELECT gmail_refresh_token FROM client_marketing_config WHERE client_id = $1", client_id,
        )
        if not has_mailbox:
            raise RuntimeError(f"Client {client_id} has no connected Gmail mailbox yet")

        row = await conn.fetchrow(
            """
            INSERT INTO client_email_warmup (client_id, status, started_at, current_day, sent_today, seed_cursor)
            VALUES ($1, 'running', now(), 1, 0, 0)
            ON CONFLICT (client_id) DO UPDATE SET
                status = 'running', started_at = now(), completed_at = NULL,
                current_day = 1, sent_today = 0, last_sent_date = NULL,
                seed_cursor = 0, updated_at = now()
            RETURNING *
            """,
            client_id,
        )
        return dict(row)


async def _roll_day(conn, row: dict, schedule: list[int]) -> dict:
    """Given an already-fetched client_email_warmup row, advances current_day
    / resets sent_today if the calendar date has moved on since the row was
    last touched, and flips to 'complete' once past the schedule. Persists
    any change it makes and returns the (possibly updated) row."""
    if row["status"] != "running":
        return row

    now = datetime.now(dt_timezone.utc)
    day_number = _current_day_number(row["started_at"], now)

    if day_number > len(schedule):
        updated = await conn.fetchrow(
            "UPDATE client_email_warmup SET status = 'complete', completed_at = now(), "
            "current_day = $2, updated_at = now() WHERE client_id = $1 RETURNING *",
            row["client_id"], day_number,
        )
        return dict(updated)

    if day_number != row["current_day"]:
        updated = await conn.fetchrow(
            "UPDATE client_email_warmup SET current_day = $2, sent_today = 0, updated_at = now() "
            "WHERE client_id = $1 RETURNING *",
            row["client_id"], day_number,
        )
        return dict(updated)

    return row


async def record_real_send(client_id: int) -> None:
    """Best-effort hook called from client_email.send_client_email() after a
    REAL outbound send. Counts it toward that day's warm-up target so
    starting real outreach mid-ramp doesn't stack extra seed volume on top —
    never raises, since a bug here must never break a real send."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM client_email_warmup WHERE client_id = $1", client_id,
            )
            if not row or row["status"] != "running":
                return
            schedule = await _get_schedule(conn)
            row = await _roll_day(conn, dict(row), schedule)
            if row["status"] != "running":
                return
            await conn.execute(
                "UPDATE client_email_warmup SET sent_today = sent_today + 1, "
                "last_sent_at = now(), last_sent_date = now()::date, updated_at = now() "
                "WHERE client_id = $1",
                client_id,
            )
    except Exception as e:
        print(f"[email_warmup] record_real_send failed for client={client_id}: {e}", flush=True)


async def get_status(client_id: int) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM client_email_warmup WHERE client_id = $1", client_id)
        schedule = await _get_schedule(conn)

    total_days = len(schedule)
    if not row:
        return {"status": "not_started", "current_day": 0, "total_days": total_days, "sent_today": 0, "day_target": 0}

    if row["status"] == "complete":
        return {
            "status": "complete", "current_day": min(row["current_day"], total_days),
            "total_days": total_days, "sent_today": row["sent_today"],
            "day_target": schedule[-1] if schedule else 0,
        }

    now = datetime.now(dt_timezone.utc)
    day_number = _current_day_number(row["started_at"], now)
    if day_number > total_days:
        return {
            "status": "complete", "current_day": total_days, "total_days": total_days,
            "sent_today": row["sent_today"], "day_target": schedule[-1] if schedule else 0,
        }

    sent_today = row["sent_today"] if day_number == row["current_day"] else 0
    return {
        "status": "running", "current_day": day_number, "total_days": total_days,
        "sent_today": sent_today, "day_target": schedule[day_number - 1],
    }


def _build_raw_message(to: str, day_number: int, seed_cursor: int) -> str:
    subject = _SUBJECTS[seed_cursor % len(_SUBJECTS)]
    msg = MIMEText(_BODY)
    msg["to"] = to
    msg["subject"] = subject
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


async def send_due_touches():
    """APScheduler entrypoint (short interval — volume needs to trickle
    across the day, not burst all at once). Sends at most ONE warm-up email
    per running client per tick, so with a ~20min interval a client whose
    day_target is e.g. 30 naturally spreads those sends across the day
    instead of firing them all in one shot. Never raises."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT w.*, c.gmail_refresh_token FROM client_email_warmup w
                JOIN client_marketing_config c ON c.client_id = w.client_id
                WHERE w.status = 'running'
                """
            )
            if not rows:
                return
            schedule = await _get_schedule(conn)
            seeds = await _get_seed_emails(conn)

            for record in rows:
                row = dict(record)
                client_id = row["client_id"]
                try:
                    row = await _roll_day(conn, row, schedule)
                    if row["status"] != "running":
                        continue
                    day_target = schedule[row["current_day"] - 1]
                    if row["sent_today"] >= day_target:
                        continue
                    if not seeds:
                        print(f"[email_warmup] no seed addresses configured — skipping client={client_id}", flush=True)
                        continue
                    if not row["gmail_refresh_token"]:
                        continue

                    to_addr = seeds[row["seed_cursor"] % len(seeds)]
                    svc = client_email._client_gmail_service(row["gmail_refresh_token"])
                    raw = _build_raw_message(to_addr, row["current_day"], row["seed_cursor"])
                    sent = await asyncio.to_thread(
                        lambda: svc.users().messages().send(userId="me", body={"raw": raw}).execute()
                    )

                    await conn.execute(
                        "INSERT INTO client_email_warmup_log (client_id, day_number, to_email, gmail_message_id) "
                        "VALUES ($1, $2, $3, $4)",
                        client_id, row["current_day"], to_addr, sent.get("id"),
                    )
                    await conn.execute(
                        "UPDATE client_email_warmup SET sent_today = sent_today + 1, seed_cursor = seed_cursor + 1, "
                        "last_sent_at = now(), last_sent_date = now()::date, updated_at = now() WHERE client_id = $1",
                        client_id,
                    )
                except Exception as e:
                    print(f"[email_warmup] send failed for client={client_id}: {e}", flush=True)
    except Exception as e:
        print(f"[email_warmup] job error: {e}", flush=True)
