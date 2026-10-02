"""DM Reach follow-up sequence — scheduled from main.py's APScheduler job.

Nudges a prospect who's gone quiet mid-conversation after being manually
enrolled from the Inbox (POST /inbox/contact/{contact_id}/dm-followup — see
that endpoint's docstring), or automatically the moment an AI setter reply
is sent on the thread (routers/sms.py's manual_send), or by this module's
own auto_enroll() each poll for any quiet campaign thread whose last text
was waiting on an answer (see enroll_eligible). Never while the SMS
setter has its own check-in scheduled on the thread (ai_followup_due_at —
the prospect said "check back later"; see sms_setter_ai.schedule_follow_up):
that replaces this sequence rather than running alongside it. Nor after a
front desk said they'd pass the message on, or gave an email for the owner
(those are to-dos for Dylan, not nudges to the front desk). Touches go out
only 9am-7pm prospect time, at most MAX_SENDS_PER_POLL per poll. SMS-only:
there's no email equivalent today.

Enrollment (dm_followup_enrolled_at) is INTENTIONALLY independent of
sms_conversations.stage_dm_reached, the "DM Reached" analytics checkbox —
they used to be the same action (checking/unchecking DM Reached was the only
way to start/stop this sequence), which meant the only way to stop an
unwanted cycle was to uncheck DM Reached and corrupt the DM-Reached-rate
analytics that checkbox feeds (analytics.py's _sms_metrics). Fixed
2026-09-22: dm_followup_enrolled_at is now the sole "is this cycle live"
signal this module (and dialer.py's dm-followup-active queue) checks —
whether stage_dm_reached is also checked is irrelevant to whether the
sequence runs, in both directions.

Unlike no_show_sequence.py/cancel_sequence.py, this sequence has NO explicit
reply-stop hook wired into the inbound webhook. Its stop/restart behavior is
entirely derived, each poll, from live sms_messages timestamps — simpler and
self-correcting, since (unlike an appointment outcome) "did they reply" is
naturally re-derivable every time from the message log itself:

  1. For each eligible conversation (status != 'closed', disposition IS NULL
     — the latter covers both the "Not Interested" stop and the "booked"
     stop, since both set disposition via existing paths in
     email_inbox.py's stage-set handler and routers/appointments.py's
     create_appointment() — AND dm_followup_enrolled_at IS NOT NULL),
     compute live: last_outbound_at = MAX(sent_at) FROM sms_messages WHERE
     direction='outbound', last_inbound_at = same for 'inbound'.

  Both "Not Interested" and a booked appointment also hard-clear
  dm_followup_enrolled_at itself the moment they're set (not just rely on
  this disposition filter) — see email_inbox.py's not_interested branch and
  routers/appointments.py's create_appointment_row() — and the enrollment
  endpoint refuses to re-enroll anyone with a disposition already set. So a
  Not Interested or booked prospect can neither still be mid-cycle nor be
  re-added into one, deliberately or by a stale state.
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
  4. Send whichever touch is next due. Touch 1 waits 24h from
     dm_followup_anchor_at; Touch 2 waits 48h from Touch 1's actual send;
     Touch 3 waits 4 days from Touch 2's actual send (24h/48h/4d chains to
     the intended 24h/72h/7d-from-anchor cadence when each touch sends right
     on schedule). Sending a touch becomes the new "last_outbound_at" on the
     NEXT poll, but since it's never newer than the anchor/touch timestamp we
     just recorded, step 3 correctly treats it as "still the same cycle" —
     Touch 2/3 stay anchored to real send times instead of restarting every
     time this sequence itself sends something.

     Chaining each touch off the PREVIOUS touch's real send (rather than off
     a single fixed anchor) matters for prospects who were already DM-Reached
     and silent before this sequence existed: their anchor backfills to
     whatever their last real outbound message was, which can be weeks old.
     Anchored-from-a-single-point timing would find all three delays already
     satisfied simultaneously and fire Touch 1/2/3 back-to-back within
     minutes on the first poll after deploy. Chaining from real sends means
     Touch 1 can fire immediately (it genuinely is overdue), but Touch 2/3
     still each wait their full interval from there — so it can never
     produce a burst.

Dialer escalation: 24h after Touch 2 sends with still no reply, the
prospect's contacts.status flips to 'dialer-lead' so they land in the
internal dialer queue for a phone follow-up — this is purely additive, not
a stop condition. The SMS sequence
keeps running as normal alongside it: Touch 3 still sends on schedule unless
they reply (step 2 above), get marked Not Interested (sets disposition,
which excludes the row from step 1's WHERE clause), or a rep manually
un-enrolls them from the Inbox's SEQUENCES panel (clears
dm_followup_enrolled_at and the whole cycle — see email_inbox.py's
set_dm_followup_active()).

Each touch's SMS text is independently editable from Business Resources →
Outreach Templates → DM Follow-Up. Templates support {first_name} and
{link} — {link} always resolves to integrations.CALENDLY_URL.
"""

import re
from datetime import datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

import integrations
from db import get_pool
from merge_fields import first_name_from_owner
from timezone_lookup import guess_timezone

# Touches only go out in the prospect's daytime, and at most this many per
# 5-minute poll — enrolling a backlog would otherwise fire every overdue
# Touch 1 in the same minute.
SEND_HOURS = (9, 19)          # prospect's local time, [start, end)
MAX_SENDS_PER_POLL = 12

# Auto-enroll (see auto_enroll): a thread where the prospect has replied at
# least once and our text is the last word gets the sequence, as long as
# that last text was actually waiting on an answer.
_PITCH_STAGES = {"gatekeeper", "curiosity_opener", "relevance", "guarantee", "ask", "cta"}
_BOILERPLATE = re.compile(r"(reply|text)\s+stop\s+to\s+\w+(\s+\w+)?", re.I)
_OPTED_OUT = re.compile(
    r"\b(stop|unsubscribe|remove (me|us|this)|take (me|us) off|not interested|no thanks?|no thank you|"
    r"(don'?t|do not|please don'?t) (text|message|contact)|wrong number)\b",
    re.I,
)
# One of Dylan's own texts that closes the exchange rather than waiting on
# an answer: a thanks, a sign-off, a promise to come back later, a typo fix.
_SIGN_OFF = re.compile(
    r"^\s*(thank|thanks|thx|appreciate|i appreciate|all good|sounds good|no worries|sorry|you too|have a)\b"
    r"|close this out|reach out in|check back|let me know if you change",
    re.I,
)

# (touch number, sent-at column, reference column to count the delay from —
# None means "the anchor"; otherwise the previous touch's own sent-at column
# — see module docstring for why chaining off real sends, not the anchor,
# matters for prospects who were already silent before this sequence existed)
_TOUCHES = [
    (1, "dm_followup_touch1_sent_at", None, timedelta(hours=24)),
    (2, "dm_followup_touch2_sent_at", "dm_followup_touch1_sent_at", timedelta(hours=48)),
    (3, "dm_followup_touch3_sent_at", "dm_followup_touch2_sent_at", timedelta(days=4)),
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
    return (
        template.replace("{first_name}", first_name)
        .replace("{link}", integrations.CALENDLY_URL)
        .replace("{vsl_link}", integrations.vsl_link(row.get("contact_id")))
    )


async def _send_touch(conn, row: dict, instance: str, templates: dict, stage: str):
    from routers import sms as sms_router

    sms_text = _fill(templates[f"dm_followup_{instance}_sms"], row)
    phone = row["phone"]
    if sms_text.strip():
        try:
            sms_router._send_twilio(phone, sms_text)
            await sms_router._store_message(conn, phone, "assistant", sms_text, stage=stage, is_automated=True)
        except Exception as e:
            print(f"[dm_followup_sequence] SMS failed for {phone}: {e}")


def enroll_eligible(row: dict) -> bool:
    """Whether a quiet thread (prospect replied before, our text is last)
    should be auto-enrolled. Only when that last text was waiting on an
    answer: a sequence pitch step, an AI setter reply that isn't a hand-off
    (relay / email / check-in / close), or one of Dylan's own texts that
    isn't a sign-off or a thank-you. Never when the sequence already ran
    on this silence, or the prospect has ever said stop / not interested."""
    import sms_setter_ai

    stage = row.get("last_stage") or ""
    inbound = _BOILERPLATE.sub(" ", row.get("inbound_text") or "")
    if _OPTED_OUT.search(inbound):
        return False
    if stage.startswith("dm_followup"):
        return False
    if stage in _PITCH_STAGES:
        return True
    if stage == "ai_setter":
        return row.get("last_ai_action") not in sms_setter_ai.NO_DM_FOLLOWUP_ACTIONS
    if not stage:
        body = (row.get("last_body") or "").strip()
        return len(body) >= 15 and not _SIGN_OFF.search(body)
    return False


async def auto_enroll(conn) -> int:
    """Puts every eligible quiet campaign thread into the sequence. AI
    setter sends have enrolled their thread since 2026-09-29, but threads
    Dylan worked by hand, and everything the setter touched before that,
    never were — so prospects went quiet with no follow-up at all. Runs
    each poll; a thread Dylan switched off in the Inbox
    (dm_followup_stopped_at) is never re-added."""
    rows = await conn.fetch(
        """
        SELECT sc.id, lo.stage AS last_stage, lo.body AS last_body,
               (SELECT action FROM sms_ai_drafts d WHERE d.phone = sc.phone AND d.status IN ('sent', 'auto_sent')
                ORDER BY d.decided_at DESC NULLS LAST, d.created_at DESC LIMIT 1) AS last_ai_action,
               (SELECT string_agg(body, ' || ') FROM sms_messages m
                WHERE m.phone = sc.phone AND m.direction = 'inbound') AS inbound_text
        FROM sms_conversations sc
        LEFT JOIN contacts c ON c.id = sc.contact_id
        CROSS JOIN LATERAL (
            SELECT stage, body, sent_at FROM sms_messages m
            WHERE m.phone = sc.phone AND m.direction = 'outbound' ORDER BY m.sent_at DESC LIMIT 1
        ) lo
        CROSS JOIN LATERAL (
            SELECT max(sent_at) AS sent_at FROM sms_messages m WHERE m.phone = sc.phone AND m.direction = 'inbound'
        ) li
        WHERE sc.campaign_id IS NOT NULL AND sc.status <> 'closed' AND sc.disposition IS NULL
          AND sc.dm_followup_enrolled_at IS NULL AND sc.dm_followup_stopped_at IS NULL
          AND sc.ai_followup_due_at IS NULL
          AND c.client_id IS NULL
          AND li.sent_at IS NOT NULL AND lo.sent_at > li.sent_at
        """
    )
    ids = [r["id"] for r in rows if enroll_eligible(dict(r))]
    if ids:
        await conn.execute(
            "UPDATE sms_conversations SET dm_followup_enrolled_at = now() WHERE id = ANY($1::int[])", ids,
        )
    return len(ids)


async def _setter_judgment(conn, phone: str, last_inbound_at) -> str | None:
    """The SMS setter's action for the prospect's latest text, or None if it
    hasn't drafted one (yet). "none" means it read the text and decided it
    needs no answer — an auto-reply ("we'll get back to you shortly") or a
    bare reaction. That isn't the prospect responding, so it doesn't stop
    the sequence the way a real reply does."""
    return await conn.fetchval(
        """
        SELECT action FROM sms_ai_drafts
        WHERE phone = $1 AND last_inbound_at >= $2 - interval '1 second'
        ORDER BY created_at DESC LIMIT 1
        """,
        phone, last_inbound_at,
    )


def _in_send_hours(phone: str, city: str | None, state: str | None, now: datetime) -> bool:
    try:
        hour = now.astimezone(ZoneInfo(guess_timezone(phone, city, state))).hour
    except Exception:
        hour = now.astimezone(ZoneInfo("America/New_York")).hour
    return SEND_HOURS[0] <= hour < SEND_HOURS[1]


async def send_due_touches():
    """Poll DM-Reached conversations and, per conversation, either reset for
    a new silence cycle, clear because the ball's back in Dylan's court, or
    send whichever touch is next due — at most one state change per row per
    poll. See module docstring for the full algorithm."""
    pool = await get_pool()
    now = datetime.now(dt_timezone.utc)
    sent_this_poll = 0
    async with pool.acquire() as conn:
        await auto_enroll(conn)
        rows = await conn.fetch(
            """
            SELECT sc.*, c.owner, c.city, c.state FROM sms_conversations sc
            LEFT JOIN contacts c ON c.id = sc.contact_id
            WHERE sc.status != 'closed' AND sc.disposition IS NULL
            AND sc.dm_followup_enrolled_at IS NOT NULL
            -- The SMS setter's own scheduled check-in (the prospect said
            -- when to come back) replaces this sequence while it's set.
            AND sc.ai_followup_due_at IS NULL
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

            judgment = None
            if last_inbound_at is not None and last_inbound_at >= last_outbound_at:
                judgment = await _setter_judgment(conn, phone, last_inbound_at)
            if last_inbound_at is not None and last_inbound_at >= last_outbound_at and judgment != "none":
                # Ball in Dylan's court — they just replied. Clear any active
                # cycle so nothing sends until he messages again. Not until
                # the setter has looked at the text, though: an auto-reply
                # landing seconds after a touch would otherwise wipe the
                # cycle and the same touch would go out again tomorrow.
                # (Uncleared is harmless — nothing sends while the ball is
                # in Dylan's court, and his next text starts a new cycle.)
                if judgment is not None and row["dm_followup_anchor_at"] is not None:
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

            # Dialer escalation: 24h after Touch 2 sends with still no reply,
            # hand this prospect to the dialer for a phone follow-up — don't
            # wait for the sequence to finish. The SMS sequence keeps running
            # as normal alongside this (Touch 3 still sends on its own
            # schedule unless they reply, get marked Not Interested, or get
            # manually un-enrolled) — this is purely an additive "also queue
            # them for a call" side effect, not a stop condition. No extra
            # "still silent" check needed here: a reply already clears
            # dm_followup_touch2_sent_at back to NULL via the "ball in
            # Dylan's court" branch above, so if this column is still set
            # 24h later, they haven't replied. Idempotent (skips if already
            # dialer-lead) so a fresh silence cycle after a reply-then-quiet-
            # again doesn't clobber a rep's own more specific disposition of
            # that contact in between.
            touch2_at = row["dm_followup_touch2_sent_at"]
            if touch2_at is not None and now >= touch2_at + timedelta(hours=24) and row["contact_id"]:
                current_status = await conn.fetchval(
                    "SELECT status FROM contacts WHERE id = $1", row["contact_id"],
                )
                if current_status != "dialer-lead":
                    await conn.execute(
                        "UPDATE contacts SET status = 'dialer-lead', updated_at = now() WHERE id = $1",
                        row["contact_id"],
                    )

            anchor = row["dm_followup_anchor_at"]
            for touch_num, sent_col, ref_col, delay in _TOUCHES:
                if row[sent_col] is not None:
                    continue
                reference = anchor if ref_col is None else row[ref_col]
                # reference is None here only if the previous touch hasn't
                # sent yet — nothing to do this poll, wait for it.
                if (reference is not None and now >= reference + delay
                        and sent_this_poll < MAX_SENDS_PER_POLL and _in_send_hours(phone, row["city"], row["state"], now)):
                    await _send_touch(conn, row, f"touch{touch_num}", templates, f"dm_followup_touch{touch_num}")
                    await conn.execute(
                        f"UPDATE sms_conversations SET {sent_col} = now() WHERE id = $1", row["id"],
                    )
                    sent_this_poll += 1
                break
