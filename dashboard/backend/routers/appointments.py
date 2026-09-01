"""Appointment reminders — manual booking capture (rep enters date/time/timezone
when dispositioning a call "Appointment Booked") + status list for the
Upcoming Appointments panel. Actual reminder sends are handled by
reminder_engine.send_due_reminders(), scheduled from main.py.

The PATCH handler below also drives the No Show outreach sequence: marking
an appointment's outcome_show = 'no_show' stamps outcome_show_at, resets its
touch/stop columns, and sends Touch 1 immediately — no_show_sequence.
send_due_touches() (also scheduled from main.py) picks up Touches 2-4 on
their normal schedule from there.

The /cancel endpoint below drives the same shape of sequence for
cancellations — cancel_sequence.py, see that module's docstring.

Marking an appointment's outcome_close = 'closed' (won) stamps
outcome_close_at and fires the onboarding welcome email immediately —
onboarding_sequence.py. Single touch, no drip/poller (contrast with the
No Show/Cancel sequences above).

GET  /appointment-reminders/sequence/{sequence} and the /add, /remove
sub-routes below (sequence in "no_show"/"cancel"/"reminder") back the
Outreach Templates tab's "View Active Prospects" queue for each of the three
sequence types — list who's currently mid-sequence with their progress, pull
someone out early, or manually (re-)enroll a specific appointment row. These
reuse the exact same columns/engines above; they don't introduce a new send
path, just manual control over the existing one.
"""

from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, HTTPException, Query

from db import get_pool
from timezone_lookup import guess_timezone, US_TIMEZONES
import cancel_sequence
import no_show_sequence
import onboarding_sequence
import reminder_engine

router = APIRouter()

# sequence key -> engine module + the columns that track its 4-touch drip,
# shared by the /sequence/{sequence} list/add/remove endpoints below. The
# "reminder" sequence isn't in here — it's a fixed 3-window (24h/6h/1h)
# countdown to appointment_at rather than a 4-touch drip from an anchor
# event, so it's handled separately in the endpoints below.
_SEQUENCE_CONFIG = {
    "no_show": {
        "module": no_show_sequence,
        "active_where": "ar.outcome_show = 'no_show' AND ar.no_show_sequence_stopped_at IS NULL",
        "anchor_col": "outcome_show_at",
        "touch_cols": [
            "no_show_touch1_sent_at", "no_show_touch2_sent_at",
            "no_show_touch3_sent_at", "no_show_touch4_sent_at",
        ],
        "touch_delays": [timedelta(hours=0), timedelta(hours=3), timedelta(hours=24), timedelta(hours=72)],
        "stopped_col": "no_show_sequence_stopped_at",
    },
    "cancel": {
        "module": cancel_sequence,
        "active_where": "ar.status = 'canceled' AND ar.cancel_sequence_stopped_at IS NULL",
        "anchor_col": "canceled_at",
        "touch_cols": [
            "cancel_touch1_sent_at", "cancel_touch2_sent_at",
            "cancel_touch3_sent_at", "cancel_touch4_sent_at",
        ],
        "touch_delays": [timedelta(hours=0), timedelta(hours=3), timedelta(hours=24), timedelta(hours=72)],
        "stopped_col": "cancel_sequence_stopped_at",
    },
}


def _touch_progress(row: dict, cfg: dict) -> dict:
    """4-touch-drip progress (no_show/cancel) — how many touches have gone
    out and when the next one is due, for display in the queue list."""
    anchor = row.get(cfg["anchor_col"])
    sent_count = sum(1 for c in cfg["touch_cols"] if row.get(c) is not None)
    total = len(cfg["touch_cols"])
    next_due = anchor + cfg["touch_delays"][sent_count] if anchor and sent_count < total else None
    return {
        "touches_sent": sent_count,
        "touches_total": total,
        "step_label": f"Touch {sent_count} of {total} sent" if sent_count else "Touch 1 pending",
        "next_touch_due_at": next_due,
    }


def _reminder_progress(row: dict) -> dict:
    """24h/6h/1h reminder-window progress, mirroring reminder_engine.py's
    own lead-time logic so the displayed 'next due' matches what will
    actually fire."""
    windows = [("24h", "reminder_24h_sent_at", 24), ("6h", "reminder_6h_sent_at", 6), ("1h", "reminder_1h_sent_at", 1)]
    sent_labels = [label for label, col, _ in windows if row.get(col) is not None]
    appt_at = row["appointment_at"]
    lead_time = appt_at - row["reminders_armed_at"]
    next_due = None
    for _label, col, hours in windows:
        if row.get(col) is not None or lead_time < timedelta(hours=hours):
            continue
        next_due = appt_at - timedelta(hours=hours)
        break
    return {
        "touches_sent": len(sent_labels),
        "touches_total": 3,
        "step_label": f"Sent: {', '.join(sent_labels)}" if sent_labels else "None sent yet",
        "next_touch_due_at": next_due,
    }


@router.get("/appointment-reminders/timezones")
async def list_timezones():
    """Static list for the booking form's timezone dropdown."""
    return US_TIMEZONES


@router.get("/appointment-reminders/guess-timezone")
async def guess_timezone_for_phone(phone: str = Query(...)):
    return {"timezone": guess_timezone(phone)}


@router.post("/appointment-reminders")
async def create_appointment(payload: dict):
    """Create a booking from the manual-entry form.
    Expects: contact_id (optional), prospect_name, prospect_phone, prospect_email,
    date ("YYYY-MM-DD"), time ("HH:MM", 24h), timezone (IANA name).
    """
    date_str = (payload.get("date") or "").strip()
    time_str = (payload.get("time") or "").strip()
    tz_name  = (payload.get("timezone") or "").strip()

    if not date_str or not time_str or not tz_name:
        raise HTTPException(400, "date, time, and timezone are required")

    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        raise HTTPException(400, f"Unknown timezone: {tz_name}")

    try:
        local_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=tz)
    except ValueError:
        raise HTTPException(400, "date must be YYYY-MM-DD and time must be HH:MM")

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO appointment_reminders
                (contact_id, prospect_name, prospect_phone, prospect_email, appointment_at, prospect_timezone)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING *
            """,
            payload.get("contact_id"),
            payload.get("prospect_name"),
            payload.get("prospect_phone"),
            payload.get("prospect_email"),
            local_dt,
            tz_name,
        )

    # Mark the win: flip contacts.status to 'appointment-booked' and, if the
    # booking was made from a specific channel's thread (the Inbox passes
    # `channel: "sms"|"email"` — see InboxPanel.jsx's replyChannel), tag
    # *that* channel's conversation with disposition='booked'. This is what
    # Analytics' Booked counts (sms_conversations.disposition /
    # email_conversations.disposition) and the Pipeline by-grade Booked
    # count (contacts.status) actually read — without it, a booking made
    # from the Inbox or CRM never showed up anywhere in Analytics.
    #
    # Deliberately channel-scoped rather than tagging both threads: a
    # contact can have an active SMS conversation and an active email
    # conversation at once, but a single booking only ever happened through
    # one of them (or neither, e.g. a Dialer/CRM booking with no channel
    # context) — tagging both as 'booked' double-counts the win on a
    # channel that had nothing to do with it. Swallow errors so a DB hiccup
    # here never blocks the booking itself from having saved.
    #
    # Deliberately does NOT set status='closed' — booking an appointment
    # should not close the conversation thread in the Inbox; the prospect
    # may still reply and the thread should stay open for that.
    contact_id = payload.get("contact_id")
    channel = payload.get("channel")
    if contact_id:
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                if channel == "sms":
                    await conn.execute(
                        "UPDATE sms_conversations SET disposition = 'booked', updated_at = now() "
                        "WHERE contact_id = $1 AND status != 'closed'",
                        contact_id,
                    )
                elif channel == "email":
                    await conn.execute(
                        "UPDATE email_conversations SET disposition = 'booked', updated_at = now() "
                        "WHERE contact_id = $1 AND status != 'closed'",
                        contact_id,
                    )
                await conn.execute(
                    "UPDATE contacts SET status = 'appointment-booked', updated_at = now() WHERE id = $1",
                    contact_id,
                )
        except Exception as e:
            print(f"[appointments] booked-disposition update failed for appointment {row['id']}: {e}")

    return {"ok": True, "id": row["id"]}


@router.get("/appointment-reminders")
async def list_appointments(status: str = Query("scheduled"), contact_id: Optional[str] = Query(None)):
    conditions = []
    params = []
    if status != "all":
        params.append(status)
        conditions.append(f"ar.status = ${len(params)}")
    if contact_id:
        params.append(contact_id)
        conditions.append(f"ar.contact_id = ${len(params)}")
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT ar.*, c.business, c.owner FROM appointment_reminders ar
            LEFT JOIN contacts c ON c.id = ar.contact_id
            {where}
            ORDER BY ar.appointment_at ASC
            """,
            *params,
        )
    return [dict(r) for r in rows]


@router.patch("/appointment-reminders/{appointment_id}")
async def update_appointment(appointment_id: int, payload: dict):
    """Edit prospect details and/or reschedule (date/time/timezone). Rescheduling
    resets the 24h/6h/1h reminder flags (so the new time gets fresh reminders) and
    sends an immediate "you've been rescheduled" notice."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM appointment_reminders WHERE id = $1", appointment_id)
    if not row:
        raise HTTPException(404, "appointment not found")
    row = dict(row)

    updates: dict = {}
    time_changed = False

    date_str = (payload.get("date") or "").strip()
    time_str = (payload.get("time") or "").strip()
    tz_name  = (payload.get("timezone") or "").strip()
    if date_str or time_str or tz_name:
        tz_name = tz_name or row["prospect_timezone"]
        try:
            tz = ZoneInfo(tz_name)
        except ZoneInfoNotFoundError:
            raise HTTPException(400, f"Unknown timezone: {tz_name}")

        existing_local = row["appointment_at"].astimezone(tz)
        date_str = date_str or existing_local.strftime("%Y-%m-%d")
        time_str = time_str or existing_local.strftime("%H:%M")
        try:
            new_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=tz)
        except ValueError:
            raise HTTPException(400, "date must be YYYY-MM-DD and time must be HH:MM")

        if new_dt != row["appointment_at"] or tz_name != row["prospect_timezone"]:
            time_changed = True
        updates["appointment_at"] = new_dt
        updates["prospect_timezone"] = tz_name

    for field in ("prospect_name", "prospect_phone", "prospect_email"):
        if field in payload:
            updates[field] = payload[field]

    # Outcome tracking — independent of the reminder/reschedule pipeline
    # above, so setting these never touches status/appointment_at or fires
    # a reschedule notice. Plain nullable TEXT (send null to clear), same
    # free-text-disposition convention as call_logs.disposition etc.
    if "outcome_show" in payload:
        value = payload["outcome_show"]
        if value not in (None, "show", "no_show"):
            raise HTTPException(400, "outcome_show must be 'show', 'no_show', or null")
        updates["outcome_show"] = value
    if "outcome_close" in payload:
        value = payload["outcome_close"]
        if value not in (None, "closed", "not_closed"):
            raise HTTPException(400, "outcome_close must be 'closed', 'not_closed', or null")
        updates["outcome_close"] = value
    if "outcome_notes" in payload:
        updates["outcome_notes"] = (payload["outcome_notes"] or "").strip() or None

    if not updates:
        return {"ok": True, "id": appointment_id}

    set_clauses = [f"{k} = ${i}" for i, k in enumerate(updates, start=1)]
    params = list(updates.values())
    if time_changed:
        set_clauses += [
            "reminder_24h_sent_at = NULL", "reminder_6h_sent_at = NULL", "reminder_1h_sent_at = NULL",
            "status = 'scheduled'",
            # Re-arm at reschedule time — reminder_engine.send_due_reminders()
            # uses this to skip any window (24h/6h) there's no longer
            # genuine lead time for, instead of firing it immediately on the
            # next poll just because "now" is already past that threshold.
            "reminders_armed_at = now()",
        ]
    # No Show sequence bookkeeping: entering 'no_show' stamps outcome_show_at
    # (the clock no_show_sequence.py's 4-touch drip counts its 20min/4h/24h/
    # 72h delays from) and resets every touch/stop column so re-marking a
    # previously-cleared no-show restarts the sequence from touch 1. Leaving
    # 'no_show' (cleared, or flipped to 'show') clears outcome_show_at, which
    # is what the poller's WHERE clause actually keys off to stop sending.
    if updates.get("outcome_show") == "no_show":
        set_clauses += [
            "outcome_show_at = now()",
            "no_show_touch1_sent_at = NULL", "no_show_touch2_sent_at = NULL",
            "no_show_touch3_sent_at = NULL", "no_show_touch4_sent_at = NULL",
            "no_show_sequence_stopped_at = NULL",
        ]
    elif "outcome_show" in updates:
        set_clauses += ["outcome_show_at = NULL"]
    # Onboarding kickoff bookkeeping: entering 'closed' (won) stamps
    # outcome_close_at and clears onboarding_kickoff_sent_at so re-closing a
    # previously-cleared appointment fires the welcome email again. Leaving
    # 'closed' clears outcome_close_at. Same shape as the outcome_show block
    # above — see onboarding_sequence.py.
    if updates.get("outcome_close") == "closed":
        set_clauses += [
            "outcome_close_at = now()",
            "onboarding_kickoff_sent_at = NULL",
            "onboarding_followup_sent_at = NULL",
        ]
    elif "outcome_close" in updates:
        set_clauses += ["outcome_close_at = NULL"]
    params.append(appointment_id)

    pool = await get_pool()
    async with pool.acquire() as conn:
        updated = await conn.fetchrow(
            f"UPDATE appointment_reminders SET {', '.join(set_clauses)} WHERE id = ${len(params)} RETURNING *",
            *params,
        )

    if time_changed:
        try:
            await reminder_engine.send_reschedule_confirmation(dict(updated))
        except Exception as e:
            print(f"[appointments] reschedule confirmation failed for {appointment_id}: {e}")

    if updates.get("outcome_show") == "no_show":
        try:
            await no_show_sequence.send_first_touch(dict(updated))
        except Exception as e:
            print(f"[appointments] no-show touch 1 failed for {appointment_id}: {e}")

    if updates.get("outcome_close") == "closed":
        try:
            await onboarding_sequence.send_kickoff(dict(updated))
        except Exception as e:
            print(f"[appointments] onboarding kickoff failed for {appointment_id}: {e}")

    return {"ok": True, "id": appointment_id}


@router.post("/appointment-reminders/{appointment_id}/cancel")
async def cancel_appointment(appointment_id: int):
    """Marks the appointment canceled and kicks off the cancellation-recovery
    drip (cancel_sequence.py) — stamps canceled_at, the clock that sequence's
    4-touch drip counts its 0h/3h/24h/72h delays from, and fires Touch 1
    immediately (same synchronous-send-then-poller-picks-up-the-rest pattern
    as no_show_sequence.send_first_touch, see routers/appointments.py's PATCH
    handler above)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            # Also halts any active No Show drip (no_show_sequence.py's poller
            # requires no_show_sequence_stopped_at IS NULL to send) so a
            # canceled appointment stops getting no-show touches.
            "UPDATE appointment_reminders SET status = 'canceled', canceled_at = now(), "
            "no_show_sequence_stopped_at = COALESCE(no_show_sequence_stopped_at, now()) "
            "WHERE id = $1 AND status = 'scheduled' RETURNING *",
            appointment_id,
        )
    if row is None:
        raise HTTPException(404, "appointment not found or already resolved")

    try:
        await cancel_sequence.send_first_touch(dict(row))
    except Exception as e:
        print(f"[appointments] cancel touch 1 failed for {appointment_id}: {e}")

    return {"ok": True}


def _validate_sequence(sequence: str):
    if sequence not in ("no_show", "cancel", "reminder"):
        raise HTTPException(400, "sequence must be 'no_show', 'cancel', or 'reminder'")


@router.get("/appointment-reminders/sequence/{sequence}")
async def list_sequence_active(sequence: str):
    """Everyone currently mid-sequence for the given type, with computed
    touch/window progress — backs the Outreach Templates tab's 'View Active
    Prospects' queue for No Show / Cancellation / Reminders."""
    _validate_sequence(sequence)
    where = (
        "ar.status = 'scheduled' AND ar.appointment_at > now() AND ar.reminders_stopped_at IS NULL"
        if sequence == "reminder" else _SEQUENCE_CONFIG[sequence]["active_where"]
    )

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT ar.*, c.business, c.owner FROM appointment_reminders ar
            LEFT JOIN contacts c ON c.id = ar.contact_id
            WHERE {where}
            ORDER BY ar.appointment_at ASC
            """
        )

    results = []
    for r in rows:
        row = dict(r)
        progress = _reminder_progress(row) if sequence == "reminder" else _touch_progress(row, _SEQUENCE_CONFIG[sequence])
        results.append({**row, **progress})
    return results


@router.post("/appointment-reminders/{appointment_id}/sequence/{sequence}/remove")
async def remove_from_sequence(appointment_id: int, sequence: str):
    """Pull one prospect out of an active sequence early — same effect as a
    reply triggering stop_sequence_for_reply(), just manual."""
    _validate_sequence(sequence)
    stopped_col = "reminders_stopped_at" if sequence == "reminder" else _SEQUENCE_CONFIG[sequence]["stopped_col"]

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"UPDATE appointment_reminders SET {stopped_col} = now() "
            f"WHERE id = $1 AND {stopped_col} IS NULL RETURNING id",
            appointment_id,
        )
    if row is None:
        raise HTTPException(404, "appointment not found or not currently active in that sequence")
    return {"ok": True}


@router.post("/appointment-reminders/{appointment_id}/sequence/{sequence}/add")
async def add_to_sequence(appointment_id: int, sequence: str):
    """Manually (re-)enroll an existing appointment row into a sequence —
    resets its touch/window columns and, for no_show/cancel, fires Touch 1
    immediately, same as the PATCH/cancel handlers above do when a rep
    triggers it from the Appointments tab."""
    _validate_sequence(sequence)

    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT * FROM appointment_reminders WHERE id = $1", appointment_id)
    if not existing:
        raise HTTPException(404, "appointment not found")
    existing = dict(existing)

    if sequence == "reminder":
        if existing["appointment_at"] <= datetime.now(dt_timezone.utc):
            raise HTTPException(400, "cannot enroll reminders for an appointment already in the past")
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE appointment_reminders SET status = 'scheduled', reminders_armed_at = now(), "
                "reminder_24h_sent_at = NULL, reminder_6h_sent_at = NULL, reminder_1h_sent_at = NULL, "
                "reminders_stopped_at = NULL WHERE id = $1",
                appointment_id,
            )
        return {"ok": True}

    cfg = _SEQUENCE_CONFIG[sequence]
    touch_resets = ", ".join(f"{c} = NULL" for c in cfg["touch_cols"])
    extra = ", status = 'canceled'" if sequence == "cancel" else ", outcome_show = 'no_show'"

    pool = await get_pool()
    async with pool.acquire() as conn:
        updated = await conn.fetchrow(
            f"UPDATE appointment_reminders SET {cfg['anchor_col']} = now(), {touch_resets}, "
            f"{cfg['stopped_col']} = NULL{extra} WHERE id = $1 RETURNING *",
            appointment_id,
        )

    try:
        await cfg["module"].send_first_touch(dict(updated))
    except Exception as e:
        print(f"[appointments] manual re-enroll ({sequence}) touch 1 failed for {appointment_id}: {e}")

    return {"ok": True}
