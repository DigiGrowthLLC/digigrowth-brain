"""
Inbound GoHighLevel bookings, for a client who books on a GHL calendar
instead of Calendly (Advantage Therapy, 2026-10-16). Same outcome as a
Calendly booking — routers/calendly_webhooks.py's record_booking() does the
contact match/create, ads-lead tag, appointment_reminders row (24h/6h/1h
reminders + the client's booking alert) and the funnel conversion.

GHL has no account-level booking webhook we can subscribe to with an API
key, so the client's GHL account runs a Workflow: trigger "Customer Booked
Appointment" (and "Appointment Status" -> Cancelled), action "Webhook" POSTing
to the URL from GET /api/clients/{id}/ghl-webhook-url. GHL's plain Webhook
action can't add headers, so the shared secret rides in the URL (?key=),
derived from DASHBOARD_PASSWORD per client — nothing to store, and only the
authenticated endpoint ever reveals it.

Only bookings on the calendar the client's booking link points at
(clients.calendly_url = .../widget/booking/<calendarId>) are recorded, so the
client's own paid-visit calendars never get free-consult reminders even if
the workflow's calendar filter is left off.
"""
import hashlib
import hmac
import json
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request

from db import get_pool
from routers.appointments import cancel_appointment
from routers.calendly_webhooks import record_booking

router = APIRouter()        # public: POST /webhooks/ghl/client/{client_id}
admin_router = APIRouter()  # authenticated: GET /clients/{client_id}/ghl-webhook-url

_DEFAULT_TZ = "America/Los_Angeles"
_START_FORMATS = ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M", "%A, %B %d, %Y %I:%M %p")


def _key(client_id: int) -> str:
    secret = os.environ.get("DASHBOARD_PASSWORD", "")
    return hmac.new(secret.encode(), f"ghl-booking:{client_id}".encode(), hashlib.sha256).hexdigest()[:32]


@admin_router.get("/clients/{client_id}/ghl-webhook-url")
async def ghl_webhook_url(client_id: int):
    base = os.environ.get("DASHBOARD_URL", "").rstrip("/")
    return {"url": f"{base}/webhooks/ghl/client/{client_id}?key={_key(client_id)}"}


def _parse_start(raw: str, tz_name: str) -> datetime:
    raw = (raw or "").strip()
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        for fmt in _START_FORMATS:
            try:
                dt = datetime.strptime(raw, fmt)
                break
            except ValueError:
                continue
        else:
            raise ValueError(f"unrecognized startTime {raw!r}")
    return dt if dt.tzinfo else dt.replace(tzinfo=ZoneInfo(tz_name))


def _tracking(body: dict) -> dict:
    """GHL puts UTM data in a few places depending on version (contact
    attributionSource, the booking page URL); the funnel only ever sets
    utm_source=paid_ad and utm_content=meta, so look for those anywhere."""
    blob = json.dumps(body)
    out = {}
    if "paid_ad" in blob:
        out["utm_source"] = "paid_ad"
    if re.search(r'utm_?content["\s:=]+"?meta\b', blob, re.I):
        out["utm_content"] = "meta"
    return out


@router.post("/webhooks/ghl/client/{client_id}")
async def ghl_booking_webhook(client_id: int, request: Request, key: str = ""):
    if not hmac.compare_digest(key, _key(client_id)):
        raise HTTPException(401, "Invalid key")
    body = await request.json()
    cal = body.get("calendar") or {}
    appt_id = cal.get("appointmentId") or body.get("appointmentId") or cal.get("id")
    status = (cal.get("appoinmentStatus") or cal.get("appointmentStatus") or cal.get("status") or "booked").lower()
    if not appt_id:
        print(f"[ghl] client {client_id}: payload without an appointment id, keys={list(body)}", flush=True)
        return {"ok": False, "error": "no appointment id"}
    event_uri = f"ghl:{appt_id}"

    pool = await get_pool()
    async with pool.acquire() as conn:
        booking_url = await conn.fetchval("SELECT calendly_url FROM clients WHERE id = $1", client_id)
        existing = await conn.fetchrow(
            "SELECT id, status, appointment_at FROM appointment_reminders WHERE calendly_event_uri = $1 "
            "ORDER BY created_at DESC LIMIT 1",
            event_uri,
        )
    m = re.search(r"/widget/booking/([\w-]+)", booking_url or "")
    calendar_id = cal.get("id") or cal.get("calendarId") or body.get("calendarId")
    if m and calendar_id and calendar_id != m.group(1):
        return {"ok": True, "skipped": "not the client's consult calendar"}

    if status in ("cancelled", "canceled", "invalid"):
        if existing and existing["status"] == "scheduled":
            try:
                # Silent, like a host-side Calendly cancel: GHL doesn't say
                # who canceled, and re-contacting someone who didn't is worse
                # than skipping a recovery text.
                await cancel_appointment(existing["id"], notify=False)
            except HTTPException:
                pass
        return {"ok": True}
    if status not in ("booked", "confirmed", "new"):
        return {"ok": True, "skipped": f"status {status}"}

    tz_name = cal.get("selectedTimezone") or body.get("timezone") or _DEFAULT_TZ
    try:
        ZoneInfo(tz_name)
    except Exception:
        tz_name = _DEFAULT_TZ
    try:
        start_utc = _parse_start(cal.get("startTime") or body.get("startTime"), tz_name)
    except ValueError as e:
        print(f"[ghl] client {client_id} appointment {appt_id}: {e}", flush=True)
        raise HTTPException(400, str(e))

    if existing and existing["status"] == "scheduled":
        if abs((existing["appointment_at"] - start_utc).total_seconds()) < 60:
            return {"ok": True, "skipped": "already recorded"}
        # Rescheduled in GHL: drop the old slot quietly, record the new one.
        try:
            await cancel_appointment(existing["id"], notify=False)
        except HTTPException:
            pass

    name = (body.get("full_name") or f"{body.get('first_name') or ''} {body.get('last_name') or ''}").strip() or None
    row = await record_booking(
        name=name, email=(body.get("email") or "").strip() or None, phone=(body.get("phone") or "").strip() or None,
        start_utc=start_utc, tz_name=tz_name, tracking=_tracking(body), event_uri=event_uri, client_id=client_id,
    )
    return {"ok": True, "appointment_id": row.get("id")}
