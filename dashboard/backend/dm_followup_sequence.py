"""DM Reach follow-up sequence — scheduled from main.py's APScheduler job.

Nudges a prospect who's reached the "DM Reach" stage (sms_conversations.
stage_dm_reached, a manual checkbox set in the Inbox — see routers/sms.py's
module docstring) but has gone quiet mid-conversation. SMS-only: there's no
email equivalent of DM Reach today.

Unlike no_show_sequence.py/cancel_sequence.py, this sequence has NO explicit
reply-stop hook wired into the inbound webhook. Its stop/restart behavior is
entirely derived, each poll, from live sms_messages timestamps — simpler and
self-correcting, since (unlike an appointment outcome) "did they reply" is
naturally re-derivable every time from the message log itself:

  1. For each eligible conversation (stage_dm_reached = true, status != 'closed',
     disposition IS NULL — the latter covers both the "Not Interested" stop and
     the "booked" stop, since both set disposition via existing paths in
     email_inbox.py's stage-set handler and routers/appointments.py's
     create_appointment()), compute live: last_outbound_at = MAX(sent_at)
     FROM sms_messages WHERE direction='outbound', last_inbound_at = same for
     'inbound'.
  2. Ball in Dylan's court (last_inbound_at >= last_outbound_at, i.e. they
     just replied, or no outbound has been sent yet): clear
     dm_followup_anchor_at and all three touch-sent columns to NULL. This IS
     the "stops the moment they reply" behavior — no hook needed, because the
     next poll simply won't find anything due to send.
  3. Ball in prospect's court (last_outbound_at > last_inbound_at): if
     last_outbound_at is newer than the current anchor AND newer than every
     touch we've already sent, this is a genuinely NEW silence cycle (a real
     human message — Dylan's own reply after they'd replied to us — not one
     of this sequence's own touches echoing back as "last outbound"). Set
     dm_followup_anchor_at = last_outbound_at and clear the touch columns —
     this IS the "restarts after a reply, if quiet again for 24h" behavior.
  4. Send whichever touch is next due against the fixed dm_followup_anchor_at
     (24h / 72h / 7d). Sending a touch becomes the new "last_outbound_at" on
     the NEXT poll, but since it's never newer than the anchor/touch
     timestamp we just recorded, step 3 correctly treats it as "still the
     same cycle" — Touch 2/3 stay anchored to the original silence event
     instead of restarting every time this sequence itself sends something.

Each touch's SMS text is independently editable from Business Resources →
Outreach Templates → DM Follow-Up. Templates support {first_name} and
{link} — {link} always resolves to integrations.CALENDLY_URL.
"""

from datetime import datetime, timedelta, timezone as dt_timezone

import integrations
from db import get_pool
from merge_fields import first_name_from_owner

# (touch number, sent-at column, delay after dm_followup_anchor_at)
_TOUCHES = [
    (1, "dm_followup_touch1_sent_at", timedelta(hours=24)),
    (2, "dm_followup_touch2_sent_at", timedelta(hours=72)),
    (3, "dm_followup_touch3_sent_at", timedelta(days=7)),
]

_TOUCH1_SMS_DEFAULT = (
    "Hey {first_name}, didn't want this to fall through the cracks — "
    "still around if you want to keep chatting: {link}"
)
_TOUCH2_SMS_DEFAULT = (
    "{first_name} — still happy to show you how businesses like yours are "
    "adding 15-20 sessions/month whenever you're free: {link}"
)
_TOUCH3_SMS_DEFAULT = (
    "{first_name} — going to close this out unless I hear back. "
    "No pressure, just let me know: {link}"
)

# instance -> sms default. dialer.py's GET/PUT /dialer/dm-followup-template
# iterates this dict generically, so adding/renaming a touch here is the
# only backend change needed.
TEMPLATE_INSTANCES = {
    "touch1": _TOUCH1_SMS_DEFAULT,
    "touch2": _TOUCH2_SMS_DEFAULT,
    "touch3": _TOUCH3_SMS_DEFAULT,
}

# dialer_settings key -> hardcoded fallback, shared by GET /dialer/dm-followup-template
# and the templated sends below.
TEMPLATE_DEFAULTS = {f"dm_followup_{instance}_sms": sms for instance, sms in TEMPLATE_INSTANCES.items()}


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
    first_name = first_name_from_owner(row.get("owner"))
    return template.replace("{first_name}", first_name).replace("{link}", integrations.CALENDLY_URL)


async def _send_touch(conn, row: dict, instance: str, templates: dict, stage: str):
    from routers import sms as sms_router

    sms_text = _fill(templates[f"dm_followup_{instance}_sms"], row)
    phone = row["phone"]
    if sms_text.strip():
        try:
            sms_router._send_twilio(phone, sms_text)
            await sms_router._store_message(conn, phone, "assistant", sms_text, stage=stage)
        except Exception as e:
            print(f"[dm_followup_sequence] SMS failed for {phone}: {e}")


async def send_due_touches():
    """Poll DM-Reached conversations and, per conversation, either reset for
    a new silence cycle, clear because the ball's back in Dylan's court, or
    send whichever touch is next due — at most one state change per row per
    poll. See module docstring for the full algorithm."""
    pool = await get_pool()
    now = datetime.now(dt_timezone.utc)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT sc.*, c.owner FROM sms_conversations sc
            LEFT JOIN contacts c ON c.id = sc.contact_id
            WHERE sc.stage_dm_reached = true AND sc.status != 'closed' AND sc.disposition IS NULL
            """
        )
        if not rows:
            return

        templates = await _get_templates()
        for record in rows:
            row = dict(record)
            phone = row["phone"]

            last_outbound_at = await conn.fetchval(
                "SELECT MAX(sent_at) FROM sms_messages WHERE phone = $1 AND direction = 'outbound'", phone,
            )
            last_inbound_at = await conn.fetchval(
                "SELECT MAX(sent_at) FROM sms_messages WHERE phone = $1 AND direction = 'inbound'", phone,
            )

            if last_outbound_at is None:
                continue

            if last_inbound_at is not None and last_inbound_at >= last_outbound_at:
                # Ball in Dylan's court — they just replied. Clear any active
                # cycle so nothing sends until he messages again.
                if row["dm_followup_anchor_at"] is not None:
                    await conn.execute(
                        "UPDATE sms_conversations SET dm_followup_anchor_at = NULL, "
                        "dm_followup_touch1_sent_at = NULL, dm_followup_touch2_sent_at = NULL, "
                        "dm_followup_touch3_sent_at = NULL WHERE id = $1",
                        row["id"],
                    )
                continue

            # Ball in the prospect's court. Detect a new silence cycle: the
            # last outbound message is newer than everything we've recorded
            # so far for the current cycle (the anchor and every touch sent).
            known_times = [t for t in (
                row["dm_followup_anchor_at"], row["dm_followup_touch1_sent_at"],
                row["dm_followup_touch2_sent_at"], row["dm_followup_touch3_sent_at"],
            ) if t is not None]
            is_new_cycle = not known_times or last_outbound_at > max(known_times)

            if is_new_cycle:
                await conn.execute(
                    "UPDATE sms_conversations SET dm_followup_anchor_at = $1, "
                    "dm_followup_touch1_sent_at = NULL, dm_followup_touch2_sent_at = NULL, "
                    "dm_followup_touch3_sent_at = NULL WHERE id = $2",
                    last_outbound_at, row["id"],
                )
                row["dm_followup_anchor_at"] = last_outbound_at
                row["dm_followup_touch1_sent_at"] = None
                row["dm_followup_touch2_sent_at"] = None
                row["dm_followup_touch3_sent_at"] = None

            anchor = row["dm_followup_anchor_at"]
            for touch_num, sent_col, delay in _TOUCHES:
                if row[sent_col] is not None:
                    continue
                if now >= anchor + delay:
                    await _send_touch(conn, row, f"touch{touch_num}", templates, f"dm_followup_touch{touch_num}")
                    await conn.execute(
                        f"UPDATE sms_conversations SET {sent_col} = now() WHERE id = $1", row["id"],
                    )
                break
