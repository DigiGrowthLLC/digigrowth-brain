"""Email Handoff — 3-touch email sequence, fired once a contact's status is
set to "email-handoff". Mirrors dm_followup_sequence.py's touch-chaining
shape (24h / +48h / +4d) but as a single ONE-SHOT sequence rather than a
restart-on-new-silence-cycle loop — a contact only ever gets enrolled once,
since "email-handoff" is a terminal channel switch (either the automatic
3-day-no-SMS-reply trigger in email_followup_trigger.py, or a rep manually
flipping status for a gatekeeper-redirect case), not something that resets.

Entry point: enroll() is called from routers/crm.py's _fire_email_handoff,
which fires at every status-transition site that sets EMAIL_HANDOFF_STATUS
(PATCH /contacts/{id}, disposition, bulk set_status, create/import) — same
sites HANDOFF_STATUS/sms-handoff already uses. enroll() used to send
immediately (a single opener email); it now just stamps
email_handoff_state.enrolled_at = now() and starts the 24h clock, matching
dm_followup_sequence's cadence. This is an intentional behavior change from
"send instantly" for the manual gatekeeper-flip case too.

send_due_touches() is the APScheduler entrypoint (main.py, 5-min poll):
  - Touch 1 fires 24h after enrolled_at.
  - Touch 2 fires 48h after touch1_sent_at (not the anchor) — chaining off
    the previous touch's real send, same reasoning as dm_followup_sequence.py
    (a touch that's slightly late due to poll cadence doesn't compress the
    remaining schedule).
  - Touch 3 fires 4 days after touch2_sent_at.
  - Reply detection is computed LIVE each poll from email_messages
    (direction='inbound' for this contact_id) rather than trusted from
    stage_replied alone — a rep manually clearing the checkbox must never
    fool this into sending to someone who genuinely replied. A reply at any
    point permanently stops all remaining touches (no restart — unlike
    DM Follow-Up, there's no "went quiet again" re-entry for this sequence).

Sending routes through email_identities.pick_identity() — MX-detects
whether the lead's domain is Google- or Microsoft-hosted (cached on
contacts.email_provider) and sends from a matching, warmed-up
email_send_identities row. Touch 1 picks whichever identity is chosen that
poll and stamps it on email_handoff_state.identity_id; touches 2/3 reuse
that same identity for thread continuity rather than re-picking each time.
If zero active identities exist for the matched provider (including no
active identities anywhere), the touch is skipped and retried next poll —
see email_identities.pick_identity()'s docstring.

Each touch's subject/body is independently editable from Business Resources
-> Outreach Templates -> Email Handoff. Templates support {first_name} and
{link} ({link} resolves to integrations.CALENDLY_URL), same convention as
dm_followup_sequence.py.
"""
from datetime import datetime, timedelta, timezone as dt_timezone

import email_identities
import integrations
from db import get_pool
from merge_fields import first_name_from_owner

EMAIL_HANDOFF_STATUS = "email-handoff"

# (touch number, sent-at column, reference column to count the delay from —
# None means "enrolled_at"; otherwise the previous touch's own sent-at
# column) — see module docstring for why chaining off real sends matters.
_TOUCHES = [
    (1, "touch1_sent_at", None, timedelta(hours=24)),
    (2, "touch2_sent_at", "touch1_sent_at", timedelta(hours=48)),
    (3, "touch3_sent_at", "touch2_sent_at", timedelta(days=4)),
]

_TOUCH1_SUBJECT_DEFAULT = "Quick question, {business}"
_TOUCH1_BODY_DEFAULT = (
    "Hey {first_name}, tried reaching you by text but figured I'd follow up here too. "
    "I'm running a small case-study cohort right now, offering our services free to a "
    "few independent practices in exchange for a testimonial once we hit results. "
    "Worth a quick look? {link}"
)
_TOUCH2_SUBJECT_DEFAULT = "Following up, {business}"
_TOUCH2_BODY_DEFAULT = (
    "{first_name} — still happy to walk you through how this would work for your "
    "practice, no pressure either way. Here's my calendar if you want to grab 10 "
    "minutes: {link}"
)
_TOUCH3_SUBJECT_DEFAULT = "Last check-in, {business}"
_TOUCH3_BODY_DEFAULT = (
    "{first_name} — going to close this out unless I hear back. No hard feelings, "
    "just didn't want it to fall through the cracks: {link}"
)

# instance -> (subject default, body default). dialer.py's GET/PUT
# /dialer/email-handoff-template iterates this dict generically, so
# adding/renaming a touch here is the only backend change needed.
TEMPLATE_INSTANCES = {
    "touch1": (_TOUCH1_SUBJECT_DEFAULT, _TOUCH1_BODY_DEFAULT),
    "touch2": (_TOUCH2_SUBJECT_DEFAULT, _TOUCH2_BODY_DEFAULT),
    "touch3": (_TOUCH3_SUBJECT_DEFAULT, _TOUCH3_BODY_DEFAULT),
}

# dialer_settings key -> hardcoded fallback, shared by GET /dialer/email-handoff-template
# and the templated sends below.
TEMPLATE_DEFAULTS = {}
for _instance, (_subject, _body) in TEMPLATE_INSTANCES.items():
    TEMPLATE_DEFAULTS[f"email_handoff_{_instance}_subject"] = _subject
    TEMPLATE_DEFAULTS[f"email_handoff_{_instance}_body"] = _body


async def _get_templates() -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT key, value FROM dialer_settings WHERE key = ANY($1)",
            list(TEMPLATE_DEFAULTS.keys()),
        )
    values = {r["key"]: r["value"] for r in rows if r["value"]}
    return {key: values.get(key, default) for key, default in TEMPLATE_DEFAULTS.items()}


def _fill(template: str, contact: dict) -> str:
    first_name = first_name_from_owner(contact.get("owner"))
    return (
        template.replace("{first_name}", first_name)
        .replace("{business}", (contact.get("business") or "").strip())
        .replace("{link}", integrations.CALENDLY_URL)
    )


async def enroll(contact: dict):
    """Called from routers/crm.py's _fire_email_handoff the moment a
    contact's status transitions to "email-handoff". Upserts the sequence
    state row and (re)stamps enrolled_at — a contact re-flipped to
    email-handoff after having been moved elsewhere restarts the 24h clock,
    same as re-checking DM Reached re-stamps dm_followup_enrolled_at."""
    contact_id = contact.get("id")
    if not contact_id:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO email_handoff_state (contact_id, enrolled_at, updated_at)
            VALUES ($1, now(), now())
            ON CONFLICT (contact_id) DO UPDATE SET
                enrolled_at = now(), touch1_sent_at = NULL, touch2_sent_at = NULL,
                touch3_sent_at = NULL, stage_replied = false, stage_replied_manual = false,
                stage_replied_at = NULL, updated_at = now()
            """,
            contact_id,
        )


async def _has_replied(conn, contact_id: str) -> bool:
    return bool(await conn.fetchval(
        "SELECT 1 FROM email_messages WHERE contact_id = $1 AND direction = 'inbound' LIMIT 1",
        contact_id,
    ))


async def _record_outbound(conn, contact_id: str, identity_id: int, email: str, subject: str, body: str, message_id: str):
    """Mirrors email_identities.sync_identity_inbox's thread_id scheme
    (identity-{identity_id}-{contact_id}) so an inbound reply later lands in
    the same conversation this outbound touch created."""
    thread_id = f"identity-{identity_id}-{contact_id}"
    conv = await conn.fetchrow("SELECT id FROM email_conversations WHERE thread_id = $1", thread_id)
    if not conv:
        await conn.execute(
            """INSERT INTO email_conversations (contact_id, thread_id, email, subject, status)
               VALUES ($1, $2, $3, $4, 'active')""",
            contact_id, thread_id, email, subject,
        )
    if not message_id:
        # Microsoft Graph's sendMail returns no message id synchronously
        # (unlike Gmail's send API) — synthesize a unique one so
        # gmail_message_id's UNIQUE NOT NULL constraint is always satisfied.
        import uuid
        message_id = f"graph-{uuid.uuid4().hex}"
    await conn.execute(
        """INSERT INTO email_messages (contact_id, thread_id, email, direction, subject, body, gmail_message_id, sent_at)
           VALUES ($1, $2, $3, 'outbound', $4, $5, $6, now())
           ON CONFLICT (gmail_message_id) DO NOTHING""",
        contact_id, thread_id, email, subject, body, message_id,
    )


async def _send_touch(conn, row: dict, instance: str, templates: dict) -> bool:
    email = (row.get("email") or "").strip()
    contact_id = row["contact_id"]
    if not email:
        print(f"[email_handoff_sequence] no email on file for contact {contact_id} — skipping")
        return False

    subject = _fill(templates[f"email_handoff_{instance}_subject"], row)
    body = _fill(templates[f"email_handoff_{instance}_body"], row)
    if not subject.strip() or not body.strip():
        print(f"[email_handoff_sequence] {instance} template is blank — skipping")
        return False

    identity_id = row.get("identity_id")
    if identity_id:
        identity = await conn.fetchrow("SELECT * FROM email_send_identities WHERE id = $1", identity_id)
        identity = dict(identity) if identity else None
    else:
        provider = await email_identities.get_cached_provider(conn, row)
        identity = await email_identities.pick_identity(conn, provider)

    if not identity:
        print(f"[email_handoff_sequence] no active identity available for {email} — will retry next poll")
        return False

    try:
        message_id = await email_identities.send_from_identity(identity, email, subject, body)
    except Exception as e:
        print(f"[email_handoff_sequence] send failed for {email} via {identity['mailbox_email']}: {e}")
        return False

    await _record_outbound(conn, contact_id, identity["id"], email, subject, body, message_id)
    if not row.get("identity_id"):
        await conn.execute(
            "UPDATE email_handoff_state SET identity_id = $2, updated_at = now() WHERE contact_id = $1",
            contact_id, identity["id"],
        )
    return True


async def send_due_touches():
    """Poll enrolled contacts and send whichever touch is next due — at most
    one send per contact per poll. See module docstring for the algorithm."""
    pool = await get_pool()
    now = datetime.now(dt_timezone.utc)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT ehs.*, c.id, c.email, c.owner, c.business, c.status,
                   c.email_provider, c.email_provider_checked_at
            FROM email_handoff_state ehs
            JOIN contacts c ON c.id = ehs.contact_id
            WHERE c.status = $1
            """,
            EMAIL_HANDOFF_STATUS,
        )
        if not rows:
            return

        templates = await _get_templates()
        for record in rows:
            row = dict(record)
            contact_id = row["contact_id"]

            if await _has_replied(conn, contact_id):
                if not row["stage_replied"]:
                    await conn.execute(
                        "UPDATE email_handoff_state SET stage_replied = true, stage_replied_at = now(), "
                        "updated_at = now() WHERE contact_id = $1",
                        contact_id,
                    )
                continue

            for touch_num, sent_col, ref_col, delay in _TOUCHES:
                if row[sent_col] is not None:
                    continue
                reference = row["enrolled_at"] if ref_col is None else row[ref_col]
                if reference is not None and now >= reference + delay:
                    sent = await _send_touch(conn, row, f"touch{touch_num}", templates)
                    if sent:
                        await conn.execute(
                            f"UPDATE email_handoff_state SET {sent_col} = now(), updated_at = now() "
                            "WHERE contact_id = $1",
                            contact_id,
                        )
                break
