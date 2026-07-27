"""Appointment reminder sender — scheduled from main.py's APScheduler job.

Sends SMS (via routers/sms.py's Twilio helper) + email (via integrations.gmail_send)
at 24h/6h/1h before each scheduled appointment, in the prospect's own timezone,
plus an immediate thank-you confirmation right when the booking is captured
(send_booking_confirmation(), called synchronously from routers/appointments.py's
create endpoint — not on the polling schedule).
Booking rows come from routers/appointments.py's manual-entry form.
"""

import asyncio
from datetime import datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

from db import get_pool
from routers import sms as sms_router
import integrations

# (window label, sent-at column, hours before appointment)
_WINDOWS = [
    ("24h", "reminder_24h_sent_at", 24),
    ("6h",  "reminder_6h_sent_at", 6),
    ("1h",  "reminder_1h_sent_at", 1),
]

_PHRASE = {"24h": "tomorrow", "6h": "in a few hours", "1h": "in about an hour"}


def _format_local(appointment_at: datetime, tz_name: str) -> str:
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("America/New_York")
    local = appointment_at.astimezone(tz)
    return local.strftime("%A, %B %-d at %-I:%M %p %Z")


def _build_message(row: dict, window_label: str) -> str:
    first_name = (row.get("prospect_name") or "").split()[0] if row.get("prospect_name") else "there"
    when = _format_local(row["appointment_at"], row["prospect_timezone"])
    phrase = _PHRASE[window_label]
    return f"Hey {first_name}, quick reminder — your call with DigiGrowth is {phrase} ({when}). Talk soon!"


def _build_confirmation_message(row: dict) -> str:
    first_name = (row.get("prospect_name") or "").split()[0] if row.get("prospect_name") else "there"
    when = _format_local(row["appointment_at"], row["prospect_timezone"])
    return (
        f"Hey {first_name}, thanks for booking a call with DigiGrowth! "
        f"You're all set for {when}. We'll send a few reminders as it gets closer — talk soon!"
    )


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
    message = _build_confirmation_message(row)
    await _send_message(row, message, "You're booked — DigiGrowth", "booking_confirmation")

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE appointment_reminders SET confirmation_sent_at = now() WHERE id = $1", row["id"],
        )


async def _send_reminder(row: dict, window_label: str, sent_col: str):
    message = _build_message(row, window_label)
    await _send_message(row, message, "Reminder: your upcoming call with DigiGrowth", f"reminder_{window_label}")

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

    now = datetime.now(dt_timezone.utc)
    for record in rows:
        row = dict(record)
        for window_label, sent_col, hours_before in _WINDOWS:
            if row[sent_col] is not None:
                continue
            if now >= row["appointment_at"] - timedelta(hours=hours_before):
                await _send_reminder(row, window_label, sent_col)
