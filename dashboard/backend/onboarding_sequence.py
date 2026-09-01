"""Onboarding sequence — two touches, both keyed off an appointment's outcome
being marked "Closed" (won) in the dialer UI.

1. **Welcome email** — fires immediately, synchronously from
   routers/appointments.py's PATCH handler the moment outcome_close
   transitions to 'closed' (that handler also stamps outcome_close_at =
   now() and clears onboarding_kickoff_sent_at/onboarding_followup_sent_at
   on that same transition). Just a warm welcome + a heads-up that the form
   and booking link are coming tomorrow — deliberately does NOT include
   either link itself (see send_kickoff()).

2. **Onboarding email + SMS** — carries the client's portal link (their one
   hub for onboarding, stats, etc. — see client_portal.py), not raw form/
   booking links directly. Fires the *next calendar morning* after the
   close, regardless of what time of day the deal actually closed (close at
   11pm today still sends tomorrow morning, not "+24h" which would land at
   11pm) — send_followup_touches() is polled once daily at 8:00am ET
   (main.py's scheduler) rather than a fixed-delay timer like
   no_show_sequence.py's touches, since "the morning after" is a
   calendar-day condition, not an elapsed-time one.

   Resolving the portal link requires a `clients` row already linked to
   this appointment's contact (contacts.client_id -> clients.portal_token)
   — see _portal_link_for_appointment(). If Dylan hasn't created the client
   record yet by the time this fires, the touch is skipped (logged, not
   raised) and onboarding_followup_sent_at still gets stamped, so it never
   retries — create the client in the Clients tab right after closing, same
   day, so the link is ready for the next morning's send.

Editable from Business Resources → Outreach Templates → Onboarding Kickoff,
same dialer_settings-backed pattern as every other sequence module here (see
no_show_sequence.py's module docstring for the shared mechanism). Templates
support {first_name} and {portal_link}.

This is v1 of a broader onboarding agent Dylan plans to keep building out
(a client-facing dashboard, contracts, kickoff docs, etc.) — see
onboarding-agent/CLAUDE.md.
"""

import asyncio
import os
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

_FOLLOWUP_SUBJECT_DEFAULT = "Your DigiGrowth client portal, {first_name}"
_FOLLOWUP_BODY_DEFAULT = (
    "Hey {first_name},\n\n"
    "As promised — here's your client portal. Everything you need is in there: "
    "your intake form, booking your Onboarding Call, and tracking how your campaigns "
    "are performing once we're live.\n\n"
    "{portal_link}\n\n"
    "Talk soon,\nDylan"
)
_FOLLOWUP_SMS_DEFAULT = (
    "Hey {first_name} — here's your client portal, everything you need to get set up: {portal_link}"
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


def _fill(template: str, row: dict, portal_link: str = "") -> str:
    first_name = first_name_from_owner(row.get("prospect_name"))
    return (
        template
        .replace("{first_name}", first_name)
        .replace("{portal_link}", portal_link)
    )


_DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "https://digigrowth-brain-production.up.railway.app").rstrip("/")


async def _portal_link_for_appointment(conn, row: dict) -> str:
    """Resolve this appointment's client portal link via
    contact_id -> contacts.client_id -> clients.portal_token (same
    {DASHBOARD_URL}/portal/{token} shape as routers/clients.py's
    _portal_url()). Returns "" if no client record is linked yet —
    callers treat that as "not ready to send"."""
    contact_id = row.get("contact_id")
    if not contact_id:
        return ""
    client_row = await conn.fetchrow(
        "SELECT cl.portal_token FROM contacts c JOIN clients cl ON cl.id = c.client_id WHERE c.id = $1",
        contact_id,
    )
    if not client_row:
        return ""
    return f"{_DASHBOARD_URL}/portal/{client_row['portal_token']}"


async def send_kickoff(row: dict):
    """Send the welcome email immediately — called synchronously from
    appointments.py's PATCH handler the moment a rep marks an appointment
    'Closed'. Doesn't reference the portal link (see module docstring), so
    it only needs an email address on file — no dependency on a `clients`
    row existing yet, unlike the next-morning follow-up. Always stamps
    onboarding_kickoff_sent_at so a skip never retries forever."""
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


async def _send_followup(row: dict, templates: dict, portal_link: str):
    """SMS + email carrying the client's portal link. Each channel
    independently skipped (logged, not raised) if its contact field is
    missing; both are skipped entirely if portal_link is empty (no linked
    `clients` row yet — see _portal_link_for_appointment), so shipping ahead
    of Dylan creating the client record is safe."""
    from routers import sms as sms_router

    if not portal_link:
        print(f"[onboarding_sequence] no client portal link resolved for appointment {row.get('id')} — skipping follow-up SMS + email")
        return

    phone = (row.get("prospect_phone") or "").strip()
    sms_template = templates["onboarding_followup_sms"]
    if phone and sms_template.strip():
        try:
            sms_text = _fill(sms_template, row, portal_link)
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
    if email and subject_template.strip() and body_template.strip():
        try:
            subject = _fill(subject_template, row, portal_link)
            body = _fill(body_template, row, portal_link)
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
        pool = await get_pool()
        async with pool.acquire() as conn:
            portal_link = await _portal_link_for_appointment(conn, row)
        await _send_followup(row, templates, portal_link)
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE appointment_reminders SET onboarding_followup_sent_at = now() WHERE id = $1",
                row["id"],
            )
