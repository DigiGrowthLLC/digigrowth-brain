"""No Show outreach sequence — scheduled from main.py's APScheduler job.

Fires a 4-touch SMS/email drip at a prospect after a rep marks an
appointment's outcome "No Show" in the Appointments tab
(routers/appointments.py's PATCH handler sets outcome_show_at = now() and
resets every touch/stop column below whenever outcome_show transitions to
'no_show').

Touch schedule (all offsets measured from outcome_show_at):
  Touch 1 —   0h:    SMS + email, blame-neutral "must've missed each other".
                      Sent synchronously from appointments.py's PATCH handler
                      the moment a rep clicks No Show (send_first_touch()) —
                      not left to wait for the next poll — but still counted
                      in _TOUCHES below as a zero-delay entry so the poller
                      picks it up as a fallback if that synchronous send
                      never ran (e.g. a mid-request crash).
  Touch 2 —   3h:    SMS only (no email — one channel per touch keeps this
                      from feeling like a barrage; email fields are blank by
                      default and any touch's email send is skipped if either
                      its subject or body template is blank).
  Touch 3 —  24h:    SMS + email, social-proof framing.
  Touch 4 —  72h:    SMS + email, the "breakup" touch — closes the loop.

Stops permanently the moment the prospect replies on either channel:
routers/sms.py's inbound Twilio webhook and routers/email_inbox.py's Gmail
sync both call stop_sequence_for_reply() the instant a matching inbound
message lands, which halts any appointment row still mid-sequence for that
phone/email — no further touches send after that.

Each touch's SMS text and email subject/body are independently editable from
Business Resources → Outreach Templates → No Show, same dialer_settings-
backed pattern as the appointment reminder pipeline (see reminder_engine.py).
Templates support {first_name} and {link} — {link} always resolves to
integrations.CALENDLY_URL (there's no specific meeting time to look up once
the original appointment's already been missed).
"""

import asyncio
from datetime import datetime, timedelta, timezone as dt_timezone

import integrations
from db import get_pool
from merge_fields import first_name_from_owner

# (touch number, sent-at column, delay after outcome_show_at)
_TOUCHES = [
    (1, "no_show_touch1_sent_at", timedelta(hours=0)),
    (2, "no_show_touch2_sent_at", timedelta(hours=3)),
    (3, "no_show_touch3_sent_at", timedelta(hours=24)),
    (4, "no_show_touch4_sent_at", timedelta(hours=72)),
]

_TOUCH1_SMS_DEFAULT = (
    "Hey {first_name}, must've missed each other — no worries! "
    "Grab a new time here: {link}"
)
_TOUCH1_SUBJECT_DEFAULT = "Missed you, {first_name}"
_TOUCH1_BODY_DEFAULT = (
    "Hey {first_name},\n\n"
    "Looks like the timing didn't work out today — happens to everyone. "
    "Whenever's good for you: {link}\n\n"
    "Talk soon,\nDylan"
)

_TOUCH2_SMS_DEFAULT = (
    "{first_name} — still want to show you how studios like yours are "
    "adding 15-20 sessions/month. 15 min, your call: {link}"
)
# Touch 2 is SMS-only by design — email subject/body default to empty so
# _send_touch() below skips the email channel entirely for this one.
_TOUCH2_SUBJECT_DEFAULT = ""
_TOUCH2_BODY_DEFAULT = ""

_TOUCH3_SMS_DEFAULT = (
    "{first_name}, happens to lots of folks — still open if you want to "
    "grab a new time: {link}"
)
_TOUCH3_SUBJECT_DEFAULT = "You're not the first"
_TOUCH3_BODY_DEFAULT = (
    "Hey {first_name},\n\n"
    "Discovery calls fall through the cracks all the time — you're in good "
    "company. If it's still worth 15 minutes to see if this fits, here's a "
    "new link: {link}\n\n"
    "If not, no hard feelings — just let me know and I'll close this out."
)

_TOUCH4_SMS_DEFAULT = (
    "{first_name} — going to close this out unless I hear back. "
    "No pressure either way, just let me know: {link}"
)
_TOUCH4_SUBJECT_DEFAULT = "Closing your file, {first_name}"
_TOUCH4_BODY_DEFAULT = (
    "Hey {first_name},\n\n"
    "Haven't heard back, so I'll close this out on my end unless I hear "
    "from you. If timing's just bad right now, no worries at all — reply "
    "here whenever it opens up.\n\nDylan"
)

# Each of the 4 touches gets its own sms/email_subject/email_body — key prefix
# -> (sms default, email subject default, email body default). dialer.py's
# GET/PUT /dialer/no-show-template iterates this dict generically, so
# adding/renaming a touch here is the only backend change needed.
TEMPLATE_INSTANCES = {
    "touch1": (_TOUCH1_SMS_DEFAULT, _TOUCH1_SUBJECT_DEFAULT, _TOUCH1_BODY_DEFAULT),
    "touch2": (_TOUCH2_SMS_DEFAULT, _TOUCH2_SUBJECT_DEFAULT, _TOUCH2_BODY_DEFAULT),
    "touch3": (_TOUCH3_SMS_DEFAULT, _TOUCH3_SUBJECT_DEFAULT, _TOUCH3_BODY_DEFAULT),
    "touch4": (_TOUCH4_SMS_DEFAULT, _TOUCH4_SUBJECT_DEFAULT, _TOUCH4_BODY_DEFAULT),
}

# dialer_settings key -> hardcoded fallback, shared by GET /dialer/no-show-template
# and the templated sends below.
TEMPLATE_DEFAULTS = {}
for _instance, (_sms, _subject, _body) in TEMPLATE_INSTANCES.items():
    TEMPLATE_DEFAULTS[f"no_show_{_instance}_sms"] = _sms
    TEMPLATE_DEFAULTS[f"no_show_{_instance}_email_subject"] = _subject
    TEMPLATE_DEFAULTS[f"no_show_{_instance}_email_body"] = _body


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
        template.replace("{first_name}", first_name)
        .replace("{link}", integrations.CALENDLY_URL)
        .replace("{vsl_link}", integrations.vsl_link(row.get("contact_id")))
    )


async def _send_touch(row: dict, instance: str, templates: dict, stage: str):
    from routers import sms as sms_router

    sms_text = _fill(templates[f"no_show_{instance}_sms"], row)
    subject_template = templates[f"no_show_{instance}_email_subject"]
    body_template = templates[f"no_show_{instance}_email_body"]

    phone = (row.get("prospect_phone") or "").strip()
    if phone and sms_text.strip():
        try:
            sms_router._send_twilio(phone, sms_text)
            pool = await get_pool()
            async with pool.acquire() as conn:
                await sms_router._get_or_create_conversation(conn, phone)
                await sms_router._store_message(conn, phone, "assistant", sms_text, stage=stage, is_automated=True)
        except Exception as e:
            print(f"[no_show_sequence] SMS failed for {phone}: {e}")

    email = (row.get("prospect_email") or "").strip()
    if email and subject_template.strip() and body_template.strip():
        try:
            subject = _fill(subject_template, row)
            body = _fill(body_template, row)
            result = await asyncio.to_thread(integrations.gmail_send, email, subject, body, is_automated=True)
            if not result.startswith("Sent email"):
                print(f"[no_show_sequence] email to {email} did not send: {result}")
        except Exception as e:
            print(f"[no_show_sequence] email failed for {email}: {e}")


async def send_due_touches():
    """Poll appointments marked No Show whose sequence hasn't been stopped
    (by a reply) and send whichever touch is now due — at most one touch per
    row per poll, in order, so a later touch can never fire before an
    earlier one."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM appointment_reminders WHERE outcome_show = 'no_show' "
            "AND no_show_sequence_stopped_at IS NULL AND outcome_show_at IS NOT NULL"
        )
    if not rows:
        return

    templates = await _get_templates()
    now = datetime.now(dt_timezone.utc)
    for record in rows:
        row = dict(record)
        for touch_num, sent_col, delay in _TOUCHES:
            if row[sent_col] is not None:
                continue
            if now >= row["outcome_show_at"] + delay:
                await _send_touch(row, f"touch{touch_num}", templates, f"no_show_touch{touch_num}")
                pool = await get_pool()
                async with pool.acquire() as conn:
                    await conn.execute(
                        f"UPDATE appointment_reminders SET {sent_col} = now() WHERE id = $1", row["id"],
                    )
            break


async def send_first_touch(row: dict):
    """Send Touch 1 immediately — called synchronously from appointments.py's
    PATCH handler right when a rep marks an appointment No Show, rather than
    waiting for the next 5-minute poll. Touches 2-4 still go through
    send_due_touches() on their normal schedule."""
    templates = await _get_templates()
    await _send_touch(row, "touch1", templates, "no_show_touch1")
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE appointment_reminders SET no_show_touch1_sent_at = now() WHERE id = $1", row["id"],
        )


async def stop_sequence_for_reply(phone: str | None = None, email: str | None = None):
    """Called from the SMS inbound webhook and the Gmail inbox sync the
    moment a reply lands from a phone/email — halts any active (not yet
    stopped) no-show sequence for that contact so no further touches send."""
    if not phone and not email:
        return

    from routers import sms as sms_router

    pool = await get_pool()
    async with pool.acquire() as conn:
        if phone:
            await conn.execute(
                f"""
                UPDATE appointment_reminders SET no_show_sequence_stopped_at = now()
                WHERE outcome_show = 'no_show' AND no_show_sequence_stopped_at IS NULL
                AND {sms_router._phone_match('prospect_phone', '$1')}
                """,
                phone,
            )
        if email:
            await conn.execute(
                """
                UPDATE appointment_reminders SET no_show_sequence_stopped_at = now()
                WHERE outcome_show = 'no_show' AND no_show_sequence_stopped_at IS NULL
                AND lower(prospect_email) = lower($1)
                """,
                email,
            )
