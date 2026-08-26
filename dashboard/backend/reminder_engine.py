"""Appointment reminder sender — scheduled from main.py's APScheduler job.

Sends SMS (via routers/sms.py's Twilio helper) + email (via integrations.gmail_send)
at 24h/6h/1h before each scheduled appointment, in the prospect's own timezone,
plus a reschedule notice (send_reschedule_confirmation(), called from
routers/appointments.py's edit endpoint). There is no immediate booking-confirmation
send — booking a call only schedules the 24h/6h/1h reminders.

Each message instance (24h, 6h, 1h, reschedule) has its own SMS text, email
subject, and email body — independently editable from Business Resources →
Outreach Templates (stored in dialer_settings, same store as
the "Send Info" templates — see routers/dialer.py's GET/PUT /dialer/reminder-template).
SMS Sequence templates moved to their own sms_sequences table, see
routers/sms_sequences.py. Falls back to the DEFAULT_* constants below if a key
has never been saved. Templates support {first_name}, {when}, and
{Meeting_Link} placeholders — the last one is resolved fresh at send time via
integrations.find_appointment_meeting_link() (looks up the real Calendly-
generated join link from Dylan's synced Google Calendar; falls back to the
generic Calendly URL if no matching calendar event/link is found).
"""

import asyncio
from datetime import datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

from db import get_pool
from merge_fields import first_name_from_owner
from routers import sms as sms_router
import integrations

# (window label, sent-at column, hours before appointment, template instance key)
_WINDOWS = [
    ("24h", "reminder_24h_sent_at", 24, "24h"),
    ("6h",  "reminder_6h_sent_at", 6,  "6h"),
    ("1h",  "reminder_1h_sent_at", 1,  "1h"),
]

_24H_SMS_DEFAULT = "Hey {first_name}, quick reminder — your call with DigiGrowth is tomorrow ({when}). Talk soon!"
_6H_SMS_DEFAULT  = "Hey {first_name}, quick reminder — your call with DigiGrowth is in a few hours ({when}). Talk soon!"
_1H_SMS_DEFAULT  = "Hey {first_name}, quick reminder — your call with DigiGrowth is in about an hour ({when}). Talk soon!"
_REMINDER_SUBJECT_DEFAULT = "Reminder: your upcoming call with DigiGrowth"

_RESCHEDULE_SMS_DEFAULT = "Hey {first_name}, heads up — your call with DigiGrowth has been rescheduled to {when}. See you then!"
_RESCHEDULE_EMAIL_BODY_DEFAULT = _RESCHEDULE_SMS_DEFAULT
_RESCHEDULE_SUBJECT_DEFAULT = "Your appointment has been rescheduled — DigiGrowth"

# Each of the 5 message instances gets its own sms/email_subject/email_body —
# key prefix -> (sms default, email subject default, email body default).
# dialer.py's GET/PUT /dialer/reminder-template iterate this dict generically,
# so adding/renaming an instance here is the only change needed on the backend.
TEMPLATE_INSTANCES = {
    "24h":          (_24H_SMS_DEFAULT, _REMINDER_SUBJECT_DEFAULT, _24H_SMS_DEFAULT),
    "6h":           (_6H_SMS_DEFAULT, _REMINDER_SUBJECT_DEFAULT, _6H_SMS_DEFAULT),
    "1h":           (_1H_SMS_DEFAULT, _REMINDER_SUBJECT_DEFAULT, _1H_SMS_DEFAULT),
    "reschedule":   (_RESCHEDULE_SMS_DEFAULT, _RESCHEDULE_SUBJECT_DEFAULT, _RESCHEDULE_EMAIL_BODY_DEFAULT),
}

# dialer_settings key -> hardcoded fallback, for GET /dialer/reminder-template
# and the templated sends below to share one source of truth.
TEMPLATE_DEFAULTS = {}
for _instance, (_sms, _subject, _body) in TEMPLATE_INSTANCES.items():
    TEMPLATE_DEFAULTS[f"reminder_{_instance}_sms"] = _sms
    TEMPLATE_DEFAULTS[f"reminder_{_instance}_email_subject"] = _subject
    TEMPLATE_DEFAULTS[f"reminder_{_instance}_email_body"] = _body


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


def _fill(template: str, row: dict, meeting_link: str) -> str:
    first_name = first_name_from_owner(row.get("prospect_name"))
    when = _format_local(row["appointment_at"], row["prospect_timezone"])
    return (
        template
        .replace("{first_name}", first_name)
        .replace("{when}", when)
        .replace("{Meeting_Link}", meeting_link)
    )


async def _send_instance(row: dict, instance: str, templates: dict, stage: str):
    """Send one template instance (24h/6h/1h/reschedule) — SMS uses
    its own text, email uses its own subject + body, independently editable."""
    # Blocking Google API call, hence to_thread — same pattern as gmail_send
    # below. Looked up once per send rather than once per template field.
    meeting_link = await asyncio.to_thread(
        integrations.find_appointment_meeting_link, row["appointment_at"], row.get("prospect_email"),
    ) or integrations.CALENDLY_URL

    sms_text    = _fill(templates[f"reminder_{instance}_sms"], row, meeting_link)
    subject     = _fill(templates[f"reminder_{instance}_email_subject"], row, meeting_link)
    email_body  = _fill(templates[f"reminder_{instance}_email_body"], row, meeting_link)

    phone = (row.get("prospect_phone") or "").strip()
    if phone:
        try:
            sms_router._send_twilio(phone, sms_text)
            pool = await get_pool()
            async with pool.acquire() as conn:
                await sms_router._get_or_create_conversation(conn, phone)
                await sms_router._store_message(conn, phone, "assistant", sms_text, stage=stage, is_automated=True)
        except Exception as e:
            print(f"[reminder_engine] SMS failed for {phone}: {e}")

    email = (row.get("prospect_email") or "").strip()
    if email:
        try:
            result = await asyncio.to_thread(integrations.gmail_send, email, subject, email_body, is_automated=True)
            if not result.startswith("Sent email"):
                print(f"[reminder_engine] email to {email} did not send: {result}")
        except Exception as e:
            print(f"[reminder_engine] email failed for {email}: {e}")


async def send_reschedule_confirmation(row: dict):
    """Immediate notice sent when routers/appointments.py's edit endpoint
    changes an appointment's date/time/timezone. Doesn't touch sent-at
    columns itself — the caller already reset the 24h/6h/1h flags."""
    templates = await _get_templates()
    await _send_instance(row, "reschedule", templates, "reschedule_confirmation")


async def send_due_reminders():
    """Poll for scheduled appointments that have crossed a 24h/6h/1h window
    without that window's reminder having gone out yet, and send it.

    A window is only sent if there was ever genuine lead time for it —
    measured from reminders_armed_at (booking time, or the moment it was
    last rescheduled — see routers/appointments.py's update_appointment)
    to appointment_at. Without this check, booking (or rescheduling) an
    appointment for e.g. 4 hours out would fire the 24h AND 6h reminders
    immediately on the very next poll, since "now" is already past both of
    those thresholds — instead, a window whose lead time was never actually
    available is permanently skipped, and only windows that still make
    sense (e.g. just the 1h one, in that example) go out on schedule."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM appointment_reminders WHERE status = 'scheduled' AND appointment_at > now() "
            "AND reminders_stopped_at IS NULL"
        )
    if not rows:
        return

    templates = await _get_templates()
    now = datetime.now(dt_timezone.utc)
    for record in rows:
        row = dict(record)
        lead_time = row["appointment_at"] - row["reminders_armed_at"]
        for window_label, sent_col, hours_before, instance in _WINDOWS:
            if row[sent_col] is not None:
                continue
            if lead_time < timedelta(hours=hours_before):
                continue
            if now >= row["appointment_at"] - timedelta(hours=hours_before):
                await _send_instance(row, instance, templates, f"reminder_{window_label}")
                pool = await get_pool()
                async with pool.acquire() as conn:
                    await conn.execute(
                        f"UPDATE appointment_reminders SET {sent_col} = now() WHERE id = $1", row["id"],
                    )
