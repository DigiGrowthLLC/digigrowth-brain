"""Appointment reminder sender — scheduled from main.py's APScheduler job.

Sends SMS (via routers/sms.py's Twilio helper) + email (via integrations.gmail_send)
at 24h/6h/1h before each scheduled appointment, in the prospect's own timezone,
plus an immediate thank-you confirmation right when the booking is captured
(send_booking_confirmation(), called synchronously from routers/appointments.py's
create endpoint) and a reschedule notice (send_reschedule_confirmation(), called
from routers/appointments.py's edit endpoint).

Message text is editable from Business Resources → Outreach Templates (stored in
dialer_settings, same store as the "Send Info" and SMS Sequence templates — see
routers/dialer.py's GET/PUT /dialer/reminder-template) — falls back to the
DEFAULT_* constants below if a key has never been saved. Templates support
{first_name} and {when} placeholders.
"""

import asyncio
from datetime import datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

from db import get_pool
from routers import sms as sms_router
import integrations

# (window label, sent-at column, hours before appointment, dialer_settings key)
_WINDOWS = [
    ("24h", "reminder_24h_sent_at", 24, "reminder_24h_sms"),
    ("6h",  "reminder_6h_sent_at", 6,  "reminder_6h_sms"),
    ("1h",  "reminder_1h_sent_at", 1,  "reminder_1h_sms"),
]

DEFAULT_CONFIRMATION_SMS = (
    "Hey {first_name}, thanks for booking a call with DigiGrowth! "
    "You're all set for {when}. We'll send a few reminders as it gets closer — talk soon!"
)
DEFAULT_CONFIRMATION_SUBJECT = "You're booked — DigiGrowth"

DEFAULT_24H_SMS = "Hey {first_name}, quick reminder — your call with DigiGrowth is tomorrow ({when}). Talk soon!"
DEFAULT_6H_SMS  = "Hey {first_name}, quick reminder — your call with DigiGrowth is in a few hours ({when}). Talk soon!"
DEFAULT_1H_SMS  = "Hey {first_name}, quick reminder — your call with DigiGrowth is in about an hour ({when}). Talk soon!"
DEFAULT_REMINDER_SUBJECT = "Reminder: your upcoming call with DigiGrowth"

DEFAULT_RESCHEDULE_SMS = "Hey {first_name}, heads up — your call with DigiGrowth has been rescheduled to {when}. See you then!"
DEFAULT_RESCHEDULE_SUBJECT = "Your appointment has been rescheduled — DigiGrowth"

# dialer_settings key -> hardcoded fallback, for GET /dialer/reminder-template
# and the templated sends below to share one source of truth.
TEMPLATE_DEFAULTS = {
    "reminder_confirmation_sms":     DEFAULT_CONFIRMATION_SMS,
    "reminder_confirmation_subject": DEFAULT_CONFIRMATION_SUBJECT,
    "reminder_24h_sms":              DEFAULT_24H_SMS,
    "reminder_6h_sms":               DEFAULT_6H_SMS,
    "reminder_1h_sms":               DEFAULT_1H_SMS,
    "reminder_subject":              DEFAULT_REMINDER_SUBJECT,
    "reminder_reschedule_sms":       DEFAULT_RESCHEDULE_SMS,
    "reminder_reschedule_subject":   DEFAULT_RESCHEDULE_SUBJECT,
}


async def _get_templates() -> dict:
    """Fresh read of every editable reminder template, falling back to
    TEMPLATE_DEFAULTS for any key never saved — same pattern as
    routers/sms.py send_info_message()."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT key, value FROM dialer_settings WHERE key = ANY($1)",
            list(TEMPLATE_DEFAULTS.keys()),
        )
    values = {r["key"]: r["value"] for r in rows if r["value"]}
    return {key: values.get(key, default) for key, default in TEMPLATE_DEFAULTS.items()}


def _format_local(appointment_at: datetime, tz_name: str) -> str:
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("America/New_York")
    local = appointment_at.astimezone(tz)
    return local.strftime("%A, %B %-d at %-I:%M %p %Z")


def _fill(template: str, row: dict) -> str:
    first_name = (row.get("prospect_name") or "").split()[0] if row.get("prospect_name") else "there"
    when = _format_local(row["appointment_at"], row["prospect_timezone"])
    return template.replace("{first_name}", first_name).replace("{when}", when)


async def _send_message(row: dict, message: str, subject: str, stage: str):
    """SMS + email send, best-effort on each channel independently."""
    phone = (row.get("prospect_phone") or "").strip()
    if phone:
        try:
            sms_router._send_twilio(phone, message)
            pool = await get_pool()
            async with pool.acquire() as conn:
                await sms_router._get_or_create_conversation(conn, phone)
                await sms_router._store_message(conn, phone, "assistant", message, stage=stage)
        except Exception as e:
            print(f"[reminder_engine] SMS failed for {phone}: {e}")

    email = (row.get("prospect_email") or "").strip()
    if email:
        try:
            result = await asyncio.to_thread(integrations.gmail_send, email, subject, message)
            if not result.startswith("Sent email"):
                print(f"[reminder_engine] email to {email} did not send: {result}")
        except Exception as e:
            print(f"[reminder_engine] email failed for {email}: {e}")


async def send_booking_confirmation(row: dict):
    """Immediate thank-you + appointment-time confirmation, sent right when the
    booking form is submitted — not gated by the 24h/6h/1h polling loop."""
    templates = await _get_templates()
    message = _fill(templates["reminder_confirmation_sms"], row)
    subject = _fill(templates["reminder_confirmation_subject"], row)
    await _send_message(row, message, subject, "booking_confirmation")

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE appointment_reminders SET confirmation_sent_at = now() WHERE id = $1", row["id"],
        )


async def send_reschedule_confirmation(row: dict):
    """Immediate notice sent when routers/appointments.py's edit endpoint
    changes an appointment's date/time/timezone. Doesn't touch sent-at
    columns itself — the caller already reset the 24h/6h/1h flags."""
    templates = await _get_templates()
    message = _fill(templates["reminder_reschedule_sms"], row)
    subject = _fill(templates["reminder_reschedule_subject"], row)
    await _send_message(row, message, subject, "reschedule_confirmation")


async def _send_reminder(row: dict, window_label: str, sent_col: str, sms_key: str, templates: dict):
    message = _fill(templates[sms_key], row)
    subject = _fill(templates["reminder_subject"], row)
    await _send_message(row, message, subject, f"reminder_{window_label}")

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            f"UPDATE appointment_reminders SET {sent_col} = now() WHERE id = $1", row["id"],
        )


async def send_due_reminders():
    """Poll for scheduled appointments that have crossed a 24h/6h/1h window
    without that window's reminder having gone out yet, and send it."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM appointment_reminders WHERE status = 'scheduled' AND appointment_at > now()"
        )
    if not rows:
        return

    templates = await _get_templates()
    now = datetime.now(dt_timezone.utc)
    for record in rows:
        row = dict(record)
        for window_label, sent_col, hours_before, sms_key in _WINDOWS:
            if row[sent_col] is not None:
                continue
            if now >= row["appointment_at"] - timedelta(hours=hours_before):
                await _send_reminder(row, window_label, sent_col, sms_key, templates)
