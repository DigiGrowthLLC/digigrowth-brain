"""Routes for Dylan's own booking page (personal_booking.py).

Public (no auth), at /book/strategy-call (booking.digigrowthllc.com/strategy-call
through the Cloudflare Worker). Mounted BEFORE routers/booking.py in main.py
so these fixed paths win over its /book/{key} clinic routes.
Admin (/api/personal-booking...): the OS Booking Links tab's "Personal booking
link" section.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

import personal_booking as pb
import tracking_exclusion
from db import get_pool
from personal_booking_page import render

router = APIRouter()
admin_router = APIRouter()
P = f"/book/{pb.SLUG}"


def _err(e: pb.BookingError):
    return HTTPException(status_code=400, detail=str(e))


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _day(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


@router.get(P, include_in_schema=False)
async def book_page():
    return HTMLResponse(render("book"), headers={"Cache-Control": "no-cache"})


@router.get(P + "/api/info", include_in_schema=False)
async def book_info():
    return {"types": await pb.public_types()}


@router.get(P + "/api/slots", include_in_schema=False)
async def book_slots(type_id: int, start: str | None = None, days: int = 31):
    try:
        return {"slots": await pb.get_slots(type_id, _day(start), days)}
    except pb.BookingError as e:
        raise _err(e)


@router.post(P + "/api/reserve", include_in_schema=False)
async def book_reserve(request: Request, payload: dict):
    try:
        return await pb.reserve(
            int(payload.get("type_id") or 0), payload.get("start") or "", payload.get("name"), payload.get("email"),
            payload.get("phone"), payload.get("business"), payload.get("note"), payload.get("timezone"),
            payload.get("sms_consent") is True, payload.get("utm_source"), payload.get("utm_content"),
            await tracking_exclusion.is_excluded(request))
    except pb.BookingError as e:
        raise _err(e)


async def _booking(token: str) -> dict:
    b = await pb.get_by_token(token)
    if not b:
        raise HTTPException(status_code=404, detail="We couldn't find that booking.")
    return b


def _public(b: dict) -> dict:
    f = "%Y%m%dT%H%M%SZ"
    add = "https://calendar.google.com/calendar/render?" + urlencode({
        "action": "TEMPLATE", "text": f"DigiGrowth {b['type_name']}",
        "dates": f"{b['start_at'].astimezone(timezone.utc).strftime(f)}/{b['end_at'].astimezone(timezone.utc).strftime(f)}",
        "details": f"Join: {b['meet_link'] or 'link in your invite'}", "location": b["meet_link"] or "Google Meet",
    })
    return {"status": b["status"], "start": _iso(b["start_at"]), "type_name": b["type_name"], "duration_min": b["duration_min"],
            "meet_link": b["meet_link"], "email": b["email"], "add_to_calendar": add,
            "book_url": pb.page_url(b["type_slug"])}


@router.get(P + "/manage/{token}", include_in_schema=False)
async def manage_page(token: str):
    await _booking(token)
    return HTMLResponse(render("manage"), headers={"Cache-Control": "no-cache"})


@router.get(P + "/manage/{token}/api/info", include_in_schema=False)
async def manage_info(token: str):
    return _public(await _booking(token))


@router.get(P + "/manage/{token}/api/slots", include_in_schema=False)
async def manage_slots(token: str, start: str | None = None, days: int = 31):
    b = await _booking(token)
    try:
        return {"slots": await pb.get_slots(b["type_id"], _day(start), days, exclude_booking_id=b["id"])}
    except pb.BookingError as e:
        raise _err(e)


@router.post(P + "/manage/{token}/api/cancel", include_in_schema=False)
async def manage_cancel(token: str, payload: dict):
    b = await _booking(token)
    try:
        await pb.cancel(b["id"], by_prospect=True, reason=payload.get("reason"))
    except pb.BookingError as e:
        raise _err(e)
    return _public(await _booking(token))


@router.post(P + "/manage/{token}/api/reschedule", include_in_schema=False)
async def manage_reschedule(token: str, payload: dict):
    b = await _booking(token)
    try:
        await pb.reschedule(b["id"], payload.get("start") or "")
    except pb.BookingError as e:
        raise _err(e)
    return _public(await _booking(token))


# ── OS (auth) ────────────────────────────────────────────────────────────────

@admin_router.get("/personal-booking")
async def overview():
    pool = await get_pool()
    async with pool.acquire() as conn:
        s = await pb.get_settings(conn)
        types = await conn.fetch("SELECT * FROM personal_booking_types ORDER BY sort_order, id")
        upcoming = await conn.fetch(
            """SELECT b.id, b.start_at, b.name, b.email, b.phone, b.business, b.meet_link, b.manage_token,
                      b.calendar_error, b.appointment_id, t.name AS type_name
               FROM personal_bookings b JOIN personal_booking_types t ON t.id = b.type_id
               WHERE b.status = 'confirmed' AND b.end_at > now() ORDER BY b.start_at LIMIT 25""")
        booked_30d = await conn.fetchval(
            "SELECT count(*) FROM personal_bookings WHERE created_at > now() - interval '30 days' AND NOT excluded")
    return {
        "url": pb.page_url(),
        "settings": {"timezone": s["timezone"], "hours": pb._hours(s), "min_notice_min": s["min_notice_min"],
                     "max_days_ahead": s["max_days_ahead"]},
        "types": [{**{k: t[k] for k in ("id", "slug", "name", "description", "duration_min", "call_type", "listed", "active")},
                   "url": pb.page_url(t["slug"])} for t in types],
        "upcoming": [{**dict(r), "start_at": _iso(r["start_at"]), "manage_url": pb.manage_url(r["manage_token"])}
                     for r in upcoming],
        "booked_30d": booked_30d,
    }


@admin_router.put("/personal-booking/settings")
async def save_settings(body: dict):
    hours = body.get("hours")
    if hours is not None:
        clean = {}
        for d in range(7):
            ranges = []
            for w in (hours.get(str(d)) or []):
                try:
                    a, b = datetime.strptime(w[0], "%H:%M"), datetime.strptime(w[1], "%H:%M")
                except (ValueError, TypeError, IndexError):
                    raise HTTPException(400, "Hours must look like 08:00")
                if b <= a:
                    raise HTTPException(400, "Each day's end time must be after its start time")
                ranges.append([w[0], w[1]])
            clean[str(d)] = ranges
        hours = clean
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """UPDATE personal_booking_settings SET
                 hours = COALESCE($1::jsonb, hours),
                 min_notice_min = COALESCE($2, min_notice_min),
                 max_days_ahead = COALESCE($3, max_days_ahead), updated_at = now() WHERE id = 1""",
            json.dumps(hours) if hours is not None else None,
            int(body["min_notice_min"]) if body.get("min_notice_min") is not None else None,
            int(body["max_days_ahead"]) if body.get("max_days_ahead") is not None else None)
    pb._busy_cache["at"] = 0.0
    return await overview()


@admin_router.patch("/personal-booking/types/{type_id}")
async def update_type(type_id: int, body: dict):
    fields = {k: body[k] for k in ("name", "description", "duration_min", "active", "listed") if k in body}
    if "duration_min" in fields and not (5 <= int(fields["duration_min"]) <= 240):
        raise HTTPException(400, "Length must be between 5 and 240 minutes")
    if not fields:
        raise HTTPException(400, "Nothing to update")
    sets = ", ".join(f"{k} = ${i + 2}" for i, k in enumerate(fields))
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(f"UPDATE personal_booking_types SET {sets} WHERE id = $1", type_id, *fields.values())
    return await overview()


@admin_router.post("/personal-booking/bookings/{booking_id}/cancel")
async def admin_cancel(booking_id: int):
    try:
        await pb.cancel(booking_id, by_prospect=False, reason="Canceled by Dylan")
    except pb.BookingError as e:
        raise _err(e)
    return await overview()
