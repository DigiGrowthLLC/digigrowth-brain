"""Onboarding kickoff — fires the moment a rep marks an appointment's outcome
"Closed" (won) in the dialer UI.

Sends the new client a welcome email: welcomes them to the company, gives a
brief outline of next steps, and includes a link to book their 1-hour
Onboarding Call. Single immediate touch, not a multi-day drip — fired
synchronously from routers/appointments.py's PATCH handler the moment
outcome_close transitions to 'closed' (that handler also stamps
outcome_close_at = now() and clears onboarding_kickoff_sent_at on that same
transition). No send_due_touches() poller, no main.py scheduler
registration needed — this is the entire sequence.

Editable from Business Resources → Outreach Templates → Onboarding Kickoff,
same dialer_settings-backed pattern as every other sequence module here (see
no_show_sequence.py's module docstring for the shared mechanism). The
template supports {first_name} and {link}; {link} always resolves to
integrations.ONBOARDING_CALENDLY_URL.

This is v1 of a broader onboarding agent Dylan plans to keep building out
(a client-facing dashboard, contracts, kickoff docs, etc.) — see
onboarding-agent/CLAUDE.md.
"""

import asyncio

import integrations
from db import get_pool
from merge_fields import first_name_from_owner

_WELCOME_SUBJECT_DEFAULT = "Welcome to DigiGrowth, {first_name}!"
_WELCOME_BODY_DEFAULT = (
    "Hey {first_name},\n\n"
    "Welcome aboard - excited to get started! Here's what happens next:\n\n"
    "1. We'll get on a call to map out your onboarding, set up your campaigns, "
    "and make sure everything's dialed in for your practice.\n"
    "2. From there, we handle the setup end-to-end and keep you posted as things go live.\n\n"
    "First step is grabbing a time for your Onboarding Call: {link}\n\n"
    "Talk soon,\nDylan"
)

# dialer_settings key -> hardcoded fallback, shared by GET/PUT
# /dialer/onboarding-template and the templated send below.
TEMPLATE_DEFAULTS = {
    "onboarding_welcome_email_subject": _WELCOME_SUBJECT_DEFAULT,
    "onboarding_welcome_email_body": _WELCOME_BODY_DEFAULT,
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
    return template.replace("{first_name}", first_name).replace("{link}", integrations.ONBOARDING_CALENDLY_URL)


async def send_kickoff(row: dict):
    """Send the welcome email immediately — called synchronously from
    appointments.py's PATCH handler the moment a rep marks an appointment
    'Closed'. Skips (logs, doesn't raise) if the Onboarding Call link hasn't
    been filled in yet or the appointment has no email on file, so it's safe
    to ship ahead of Dylan creating the real Calendly event. Always stamps
    onboarding_kickoff_sent_at so a blank-link skip never retries forever."""
    templates = await _get_templates()

    email = (row.get("prospect_email") or "").strip()
    subject_template = templates["onboarding_welcome_email_subject"]
    body_template = templates["onboarding_welcome_email_body"]

    if not integrations.ONBOARDING_CALENDLY_URL:
        print(f"[onboarding_sequence] ONBOARDING_CALENDLY_URL not set — skipping welcome email for appointment {row.get('id')}")
    elif email and subject_template.strip() and body_template.strip():
        try:
            subject = _fill(subject_template, row)
            body = _fill(body_template, row)
            result = await asyncio.to_thread(integrations.gmail_send, email, subject, body, is_automated=True)
            if not result.startswith("Sent email"):
                print(f"[onboarding_sequence] email to {email} did not send: {result}")
        except Exception as e:
            print(f"[onboarding_sequence] email failed for {email}: {e}")
    else:
        print(f"[onboarding_sequence] no prospect_email on appointment {row.get('id')} — skipping welcome email")

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE appointment_reminders SET onboarding_kickoff_sent_at = now() WHERE id = $1",
            row["id"],
        )
