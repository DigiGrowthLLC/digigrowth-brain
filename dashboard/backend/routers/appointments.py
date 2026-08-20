"""Appointment reminders — manual booking capture (rep enters date/time/timezone
when dispositioning a call "Appointment Booked") + status list for the
Upcoming Appointments panel. Actual reminder sends are handled by
reminder_engine.send_due_reminders(), scheduled from main.py.
"""

from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, HTTPException, Query

from db import get_pool
from timezone_lookup import guess_timezone, US_TIMEZONES
import integrations
import reminder_engine
from routers import sms as sms_router

router = APIRouter()


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
    # `channel: "sms"|"email"` — see InboxPanel.jsx's replyChannel), close
    # *that* channel's conversation with disposition='booked'. This is what
    # Analytics' Booked counts (sms_conversations.disposition /
    # email_conversations.disposition) and the Pipeline by-grade Booked
    # count (contacts.status) actually read — without it, a booking made
    # from the Inbox or CRM never showed up anywhere in Analytics.
    #
    # Deliberately channel-scoped rather than closing both threads: a
    # contact can have an active SMS conversation and an active email
    # conversation at once, but a single booking only ever happened through
    # one of them (or neither, e.g. a Dialer/CRM booking with no channel
    # context) — closing both as 'booked' double-counts the win on a
    # channel that had nothing to do with it. Swallow errors so a DB hiccup
    # here never blocks the booking itself from having saved.
    contact_id = payload.get("contact_id")
    channel = payload.get("channel")
    if contact_id:
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                if channel == "sms":
                    await conn.execute(
                        "UPDATE sms_conversations SET status = 'closed', disposition = 'booked', updated_at = now() "
                        "WHERE contact_id = $1 AND status != 'closed'",
                        contact_id,
                    )
                elif channel == "email":
                    await conn.execute(
                        "UPDATE email_conversations SET status = 'closed', disposition = 'booked', updated_at = now() "
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

    if not updates:
        return {"ok": True, "id": appointment_id}

    set_clauses = [f"{k} = ${i}" for i, k in enumerate(updates, start=1)]
    params = list(updates.values())
    if time_changed:
        set_clauses += [
            "reminder_24h_sent_at = NULL", "reminder_6h_sent_at = NULL", "reminder_1h_sent_at = NULL",
            "status = 'scheduled'",
        ]
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

    # No Show: text and email the prospect letting them know they missed the
    # call and can rebook. Fires every time a rep marks outcome_show =
    # 'no_show' from the Appointments tab — independent sends, one failing
    # shouldn't block the other. Editable from Business Resources → Outreach
    # Templates → No Show, same pattern as the "Send Info" disposition.
    if updates.get("outcome_show") == "no_show" and updated:
        try:
            await sms_router.send_no_show_message(dict(updated))
        except Exception as e:
            print(f"no-show SMS failed for appointment {appointment_id}: {e}")
        if updated["prospect_email"]:
            try:
                result = await integrations.send_no_show_email(updated["prospect_email"], updated["prospect_name"])
                if not result.startswith("Sent email"):
                    print(f"no-show email to {updated['prospect_email']} did not send: {result}")
            except Exception as e:
                print(f"no-show email failed for appointment {appointment_id}: {e}")

    return {"ok": True, "id": appointment_id}


@router.post("/appointment-reminders/{appointment_id}/cancel")
async def cancel_appointment(appointment_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE appointment_reminders SET status = 'canceled' WHERE id = $1 AND status = 'scheduled'",
            appointment_id,
        )
    if result == "UPDATE 0":
        raise HTTPException(404, "appointment not found or already resolved")
    return {"ok": True}
