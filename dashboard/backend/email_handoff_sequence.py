"""Email handoff — fires once, immediately, the moment a contact's status is
set to "email-handoff" (e.g. a gatekeeper redirects outreach to a specific
inbox instead of a phone number). Mirrors HANDOFF_STATUS/_fire_handoff for
the SMS channel exactly — same status-transition sites in routers/crm.py
(PATCH /contacts/{id}, POST /contacts/{id}/disposition via the "Email
Handoff" DISPOSITION_TO_STATUS entry, bulk set_status, and contact
create/import), just calling _fire_email_handoff instead of _fire_handoff.
Sends a single opening email built from this module's own template store —
copied once from the SMS "Free Offer V.1.3" sequence's steps (2026-09-01) as
a starting point, but stored completely separately (dialer_settings keys
below, not sms_sequences), so editing it here never touches — and is never
overwritten by — the SMS sequence.

Mirrors onboarding_sequence.py's single-touch send_kickoff() pattern and
routers/sms.py's send_opening_message(), but for the email channel. Uses
merge_fields.apply_merge_fields (matching the [Name]/{{business}} tokens
already used in the SMS content this was copied from), not
onboarding_sequence.py's {first_name}-only convention.

Editable from Business Resources -> Outreach Templates -> Email Handoff
(GET/PUT /api/dialer/email-handoff-template in routers/dialer.py).
"""
import asyncio

import integrations
from db import get_pool
from merge_fields import apply_merge_fields

_SUBJECT_DEFAULT = "Quick question, {{business}}"
_GATEKEEPER_DEFAULT = (
    "Hey, no worries. I'm reaching out because I'm actually running a small case-study cohort "
    "right now - offering our services completely free to a few independent PT practices in "
    "exchange for a testimonial once we hit results. Figured [Name] would want to know before "
    "the spots fill. Would you mind passing along my number, or letting me know the best way to "
    "reach them?"
)
_CURIOSITY_OPENER_DEFAULT = (
    "What's going on [Name], my name is Dylan. I'm reaching out because I'm currently running a "
    "small case study cohort helping practices like yours book in 10 discovery visits completely "
    "free with people in your area looking for physical therapy. I see [custom opener] and "
    "thought you'd be a great fit. Made a personalized video for you explaining how mind if I "
    "send it over?"
)
_RELEVANCE_DEFAULT = " [Loom link] Shoot me a \U0001F44D once you've watched it"
_GUARANTEE_DEFAULT = (
    "Glad it landed. We've only got 2 spots left this cycle — worth grabbing 10 min to see how "
    "it'd work for {{business}}? No pressure if it's not a fit right now."
)
_ASK_DEFAULT = (
    "Perfect. I've got a couple spots open this week for a quick call to show you exactly how "
    "it'd work for your practice — zero pressure, just walk you through it and you decide if it "
    "makes sense. Does [Day] at [time] or [Day] at [time] work better for you?"
)
_CTA_DEFAULT = "https://calendly.com/dylanrg-digigrowthllc/30min?month=2026-07&date=2026-07-14"

# dialer_settings key -> hardcoded fallback, shared by GET/PUT
# /dialer/email-handoff-template and send_handoff_email() below.
TEMPLATE_DEFAULTS = {
    "email_handoff_subject": _SUBJECT_DEFAULT,
    "email_handoff_gatekeeper": _GATEKEEPER_DEFAULT,
    "email_handoff_curiosity_opener": _CURIOSITY_OPENER_DEFAULT,
    "email_handoff_relevance": _RELEVANCE_DEFAULT,
    "email_handoff_guarantee": _GUARANTEE_DEFAULT,
    "email_handoff_ask": _ASK_DEFAULT,
    "email_handoff_cta": _CTA_DEFAULT,
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


async def send_handoff_email(contact: dict) -> bool:
    """Sends only the opening step (email_handoff_curiosity_opener) — the
    other copied steps (gatekeeper/relevance/guarantee/ask/cta) are stored
    for reference and future manual use, not auto-sent, same as how the SMS
    sequence's later steps are sent manually from the inbox. Always reads
    current template values fresh at send time, same as every other
    sequence module here."""
    email = (contact.get("email") or "").strip()
    if not email:
        print(f"[email_handoff_sequence] no email on file for contact {contact.get('id')} — skipping")
        return False

    templates = await _get_templates()
    subject_template = templates["email_handoff_subject"]
    body_template = templates["email_handoff_curiosity_opener"]
    if not subject_template.strip() or not body_template.strip():
        print("[email_handoff_sequence] subject/opener template is blank — skipping")
        return False

    subject = apply_merge_fields(subject_template, contact)
    body = apply_merge_fields(body_template, contact)

    try:
        result = await asyncio.to_thread(integrations.gmail_send, email, subject, body, track=True, is_automated=True)
    except Exception as e:
        print(f"[email_handoff_sequence] send failed for {email}: {e}")
        return False

    if not result.startswith("Sent email"):
        print(f"[email_handoff_sequence] email to {email} did not send: {result}")
        return False

    return True
