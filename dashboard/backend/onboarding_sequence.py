"""Onboarding sequence — two touches, both keyed off an appointment's outcome
being marked "Closed" (won) in the dialer UI.

1. **Welcome email** — fires immediately, synchronously from
   routers/appointments.py's PATCH handler the moment outcome_close
   transitions to 'closed' (that handler also stamps outcome_close_at =
   now() and clears onboarding_kickoff_sent_at/onboarding_followup_sent_at
   on that same transition). Just a warm welcome + a heads-up that the form
   and booking link are coming tomorrow — deliberately does NOT include
   either link itself (see send_kickoff()).

2. **Onboarding email + SMS** — the actual form link + booking link. Fires
   the *next calendar morning* after the close, regardless of what time of
   day the deal actually closed (close at 11pm today still sends tomorrow
   morning, not "+24h" which would land at 11pm) — send_followup_touches()
   is polled once daily at 8:00am ET (main.py's scheduler) rather than a
   fixed-delay timer like no_show_sequence.py's touches, since "the morning
   after" is a calendar-day condition, not an elapsed-time one.

Editable from Business Resources → Outreach Templates → Onboarding Kickoff,
same dialer_settings-backed pattern as every other sequence module here (see
no_show_sequence.py's module docstring for the shared mechanism). Templates
support {first_name}, {link} (always integrations.ONBOARDING_CALENDLY_URL),
and {form_link} (always integrations.ONBOARDING_FORM_URL).

This is v1 of a broader onboarding agent Dylan plans to keep building out
(a client-facing dashboard, contracts, kickoff docs, etc.) — see
onboarding-agent/CLAUDE.md.
"""

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import integrations
from db import get_pool
from merge_fields import first_name_from_owner

_WELCOME_SUBJECT_DEFAULT = "Welcome to DigiGrowth, {first_name}!"
_WELCOME_BODY_DEFAULT = (
    "Hey {first_name},\n\n"
    "Welcome aboard — we're excited to have you! Here's what happens next:\n\n"
    "1. We'll get on a call to map out your onboarding, set up your campaigns, "
    "and make sure everything's dialed in for your practice.\n"
    "2. From there, we handle the setup end-to-end and keep you posted as things go live.\n\n"
    "Keep an eye out tomorrow morning — you'll get an email with a short form to fill out "
    "(so we have everything we need) and a link to book your Onboarding Call.\n\n"
    "Talk soon,\nDylan"
)

_FOLLOWUP_SUBJECT_DEFAULT = "Your onboarding form + call link, {first_name}"
_FOLLOWUP_BODY_DEFAULT = (
    "Hey {first_name},\n\n"
    "As promised — two quick things to get you fully set up:\n\n"
    "1. Fill out this short intake form so we have everything on your practice: {form_link}\n"
    "2. Grab a time for your Onboarding Call: {link}\n\n"
    "Talk soon,\nDylan"
)
_FOLLOWUP_SMS_DEFAULT = (
    "Hey {first_name} — two quick things: fill out this form so we're all set "
    "{form_link} and grab your Onboarding Call time {link}"
)

# dialer_settings key -> hardcoded fallback, shared by GET/PUT
# /dialer/onboarding-template and the templated sends below.
TEMPLATE_DEFAULTS = {
    "onboarding_welcome_email_subject": _WELCOME_SUBJECT_DEFAULT,
    "onboarding_welcome_email_body": _WELCOME_BODY_DEFAULT,
    "onboarding_followup_email_subject": _FOLLOWUP_SUBJECT_DEFAULT,
    "onboarding_followup_email_body": _FOLLOWUP_BODY_DEFAULT,
    "onboarding_followup_sms": _FOLLOWUP_SMS_DEFAULT,
}


async def _get_templates() -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT key, value FROM dialer_settings WHERE key = ANY($1)",
            list(TEMPLATE_DEFAULTS.keys()),
        )
    values = {r["key"]: r["value"] for r in rows if r["value"]}
    return {key: values.get(key, default) for key, default in TEMPLATE_DEFAULTS.items()}


def _fill(template: str, row: dict) -> str:
    first_name = first_name_from_owner(row.get("prospect_name"))
    return (
        template
        .replace("{first_name}", first_name)
        .replace("{form_link}", integrations.ONBOARDING_FORM_URL)
        .replace("{link}", integrations.ONBOARDING_CALENDLY_URL)
    )


async def send_kickoff(row: dict):
    """Send the welcome email immediately — called synchronously from
    appointments.py's PATCH handler the moment a rep marks an appointment
    'Closed'. Doesn't reference either link (see module docstring), so it
    only needs an email address on file, not the form/booking links being
    filled in yet. Always stamps onboarding_kickoff_sent_at so a skip never
    retries forever."""
    templates = await _get_templates()

    email = (row.get("prospect_email") or "").strip()
    subject_template = templates["onboarding_welcome_email_subject"]
    body_template = templates["onboarding_welcome_email_body"]

    if email and subject_template.strip() and body_template.strip():
        try:
            subject = _fill(subject_template, row)
            body = _fill(body_template, row)
            result = await asyncio.to_thread(integrations.gmail_send, email, subject, body, is_automated=True)
            if not result.startswith("Sent email"):
                print(f"[onboarding_sequence] welcome email to {email} did not send: {result}")
        except Exception as e:
            print(f"[onboarding_sequence] welcome email failed for {email}: {e}")
    else:
        print(f"[onboarding_sequence] no prospect_email on appointment {row.get('id')} — skipping welcome email")

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE appointment_reminders SET onboarding_kickoff_sent_at = now() WHERE id = $1",
            row["id"],
        )


async def _send_followup(row: dict, templates: dict):
    """SMS + email carrying the actual form link and booking link. Each
    channel independently skipped (logged, not raised) if its contact field
    or backing URL is missing, so shipping ahead of Dylan filling in
    ONBOARDING_FORM_URL is safe."""
    from routers import sms as sms_router

    phone = (row.get("prospect_phone") or "").strip()
    sms_template = templates["onboarding_followup_sms"]
    if not integrations.ONBOARDING_FORM_URL:
        print(f"[onboarding_sequence] ONBOARDING_FORM_URL not set — skipping follow-up SMS for appointment {row.get('id')}")
    elif phone and sms_template.strip():
        try:
            sms_text = _fill(sms_template, row)
            sms_router._send_twilio(phone, sms_text)
            pool = await get_pool()
            async with pool.acquire() as conn:
                await sms_router._get_or_create_conversation(conn, phone)
                await sms_router._store_message(conn, phone, "assistant", sms_text, stage="onboarding_followup", is_automated=True)
        except Exception as e:
            print(f"[onboarding_sequence] follow-up SMS failed for {phone}: {e}")

    email = (row.get("prospect_email") or "").strip()
    subject_template = templates["onboarding_followup_email_subject"]
    body_template = templates["onboarding_followup_email_body"]
    if not integrations.ONBOARDING_FORM_URL:
        print(f"[onboarding_sequence] ONBOARDING_FORM_URL not set — skipping follow-up email for appointment {row.get('id')}")
    elif email and subject_template.strip() and body_template.strip():
        try:
            subject = _fill(subject_template, row)
            body = _fill(body_template, row)
            result = await asyncio.to_thread(integrations.gmail_send, email, subject, body, is_automated=True)
            if not result.startswith("Sent email"):
                print(f"[onboarding_sequence] follow-up email to {email} did not send: {result}")
        except Exception as e:
            print(f"[onboarding_sequence] follow-up email failed for {email}: {e}")


async def send_followup_touches():
    """Polled once daily at 8:00am ET (main.py's scheduler) — sends the
    onboarding email+SMS to every closed appointment from a previous
    calendar day (ET) that hasn't gotten its follow-up yet. Batched as a
    calendar-day condition rather than a fixed-delay timer so "the morning
    after" is correct no matter what time of day the deal actually closed."""
    today_start_et = datetime.now(ZoneInfo("America/New_York")).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM appointment_reminders
            WHERE outcome_close = 'closed'
              AND outcome_close_at IS NOT NULL
              AND outcome_close_at < $1
              AND onboarding_followup_sent_at IS NULL
            """,
            today_start_et,
        )
    if not rows:
        return

    templates = await _get_templates()
    for record in rows:
        row = dict(record)
        await _send_followup(row, templates)
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE appointment_reminders SET onboarding_followup_sent_at = now() WHERE id = $1",
                row["id"],
            )
