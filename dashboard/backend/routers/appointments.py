"""Appointment reminders — manual booking capture (rep enters date/time/timezone
when dispositioning a call "Appointment Booked") + status list for the
Upcoming Appointments panel. Actual reminder sends are handled by
reminder_engine.send_due_reminders(), scheduled from main.py.
"""

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, HTTPException, Query

from db import get_pool
from timezone_lookup import guess_timezone, US_TIMEZONES
import reminder_engine

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

    # Immediate thank-you + confirmation — separate from the 24h/6h/1h reminder
    # schedule, sent right away so the prospect gets confirmation the same
    # moment the rep books it. Swallow errors so a Twilio/Gmail hiccup never
    # blocks the booking itself from saving.
    try:
        await reminder_engine.send_booking_confirmation(dict(row))
    except Exception as e:
        print(f"[appointments] booking confirmation failed for appointment {row['id']}: {e}")

    return {"ok": True, "id": row["id"]}


@router.get("/appointment-reminders")
async def list_appointments(status: str = Query("scheduled")):
    pool = await get_pool()
    async with pool.acquire() as conn:
        if status == "all":
            rows = await conn.fetch(
                "SELECT ar.*, c.business, c.owner FROM appointment_reminders ar "
                "LEFT JOIN contacts c ON c.id = ar.contact_id "
                "ORDER BY ar.appointment_at ASC"
            )
        else:
            rows = await conn.fetch(
                "SELECT ar.*, c.business, c.owner FROM appointment_reminders ar "
                "LEFT JOIN contacts c ON c.id = ar.contact_id "
                "WHERE ar.status = $1 ORDER BY ar.appointment_at ASC",
                status,
            )
    return [dict(r) for r in rows]


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
