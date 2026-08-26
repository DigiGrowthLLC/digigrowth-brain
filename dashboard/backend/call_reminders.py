"""Call-reminder to-do creation — scheduled from main.py's APScheduler job.

24 hours after a discovery call goes to No Show (no_show_sequence.py) or
gets Canceled (cancel_sequence.py), check whether the prospect has since
booked a NEW appointment. If not, drop a "Call <prospect name>" to-do into
the Dashboard's To-Do tab (todos table / DashboardPanel's To-Do widget) so
Dylan follows up personally — the automated SMS/email touches alone clearly
weren't enough by that point.

Deliberately decoupled from no_show_sequence_stopped_at / cancel_sequence_
stopped_at: those flags mean "the prospect replied", not "the prospect
rebooked" — a reply like "maybe next week" still leaves the call-reminder
worth creating. The only thing that matters here is whether a genuinely NEW
appointment_reminders row exists for the same contact/phone/email, created
after the no-show/cancellation happened. Runs once per appointment (gated by
the *_call_reminder_created_at columns) regardless of how the sequence
itself played out.
"""

from datetime import date, datetime, timedelta, timezone as dt_timezone

from db import get_pool

_DELAY = timedelta(hours=24)


async def _has_rebooked(conn, row: dict, reference_at: datetime) -> bool:
    """A genuinely new booking = a different appointment_reminders row for
    the same contact/phone/email, created after the no-show/cancellation."""
    contact_id = row.get("contact_id")
    phone = (row.get("prospect_phone") or "").strip() or None
    email = (row.get("prospect_email") or "").strip() or None
    if not contact_id and not phone and not email:
        return False
    result = await conn.fetchval(
        """
        SELECT 1 FROM appointment_reminders
        WHERE id != $1
        AND created_at > $2
        AND (
            ($3::text IS NOT NULL AND contact_id = $3)
            OR ($4::text IS NOT NULL AND prospect_phone = $4)
            OR ($5::text IS NOT NULL AND lower(prospect_email) = lower($5))
        )
        LIMIT 1
        """,
        row["id"], reference_at, contact_id, phone, email,
    )
    return result is not None


async def _create_call_todo(conn, row: dict, reason: str):
    name = (row.get("prospect_name") or "").strip() or "prospect"
    phone = (row.get("prospect_phone") or "").strip()
    description = reason + (f" — {phone}" if phone else "")
    await conn.execute(
        "INSERT INTO todos (text, description, due_date) VALUES ($1, $2, $3)",
        f"Call {name}", description, date.today(),
    )


async def _check(outcome_column_where: str, reference_column: str, created_flag_column: str, reason: str):
    pool = await get_pool()
    now = datetime.now(dt_timezone.utc)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT * FROM appointment_reminders WHERE {outcome_column_where} "
            f"AND {reference_column} IS NOT NULL AND {created_flag_column} IS NULL"
        )
        for record in rows:
            row = dict(record)
            reference_at = row[reference_column]
            if now < reference_at + _DELAY:
                continue
            if not await _has_rebooked(conn, row, reference_at):
                await _create_call_todo(conn, row, reason)
            await conn.execute(
                f"UPDATE appointment_reminders SET {created_flag_column} = now() WHERE id = $1", row["id"],
            )


async def check_all():
    """Registered on the 5-minute poller alongside the sequence jobs — cheap
    to re-check "has 24h passed yet" that often, and keeps the call-reminder
    close to the 24h mark instead of drifting on a slower schedule."""
    await _check(
        "outcome_show = 'no_show'", "outcome_show_at", "no_show_call_reminder_created_at",
        "No-showed a discovery call and hasn't rebooked after 24h",
    )
    await _check(
        "status = 'canceled'", "canceled_at", "cancel_call_reminder_created_at",
        "Canceled a discovery call and hasn't rebooked after 24h",
    )
