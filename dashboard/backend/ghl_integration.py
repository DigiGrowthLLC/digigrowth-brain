"""
GoHighLevel calendar integration for response_ai.py — the GHL counterpart
of calendly_integration.py, for a client who books on a GHL calendar
instead of Calendly (Advantage Therapy, 2026-10-26). Looks up REAL open
slots (check_availability) and books a confirmed appointment straight onto
the calendar (propose_appointment), no link for the lead to tap.

Auth is a Private Integration token from the client's GHL sub-account
(Settings -> Private Integrations -> Create, scopes: View Calendars, Edit
Calendar Events, Edit Contacts), pasted into client_marketing_config.
ghl_api_token. The calendar is the one the client's booking link already
points at (clients.calendly_url = .../widget/booking/<calendarId>), the same
one routers/ghl_webhooks.py records bookings for, so there's nothing else
to configure.

create_appointment() leaves toNotify on, so the calendar's own confirmation
and the client's booking workflow both still fire. That workflow posts the booking back to ghl_webhooks.py,
which skips it as "already recorded" because response_ai.py records it
under the same ghl:<appointmentId> key first.
"""
import re
from datetime import datetime, timedelta, timezone

import httpx

_API_BASE = "https://services.leadconnectorhq.com"
_API_VERSION = "2021-04-15"
_MAX_RANGE_DAYS = 31  # GHL rejects a free-slots window longer than this


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Version": _API_VERSION,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def calendar_id_from_url(booking_url: str | None) -> str | None:
    m = re.search(r"/widget/booking/([\w-]+)", booking_url or "")
    return m.group(1) if m else None


def _raise_with_context(resp: httpx.Response) -> None:
    if resp.is_success:
        return
    raise RuntimeError(f"GHL {resp.request.method} {resp.request.url.path} -> {resp.status_code}: {resp.text[:300]}")


async def find_earliest_available_times(
    token: str, calendar_id: str, start: datetime, tz_name: str, max_days: int = 30,
) -> list[datetime]:
    """The earliest day's open slots from `start` on (timezone-aware, in
    tz_name), or [] if nothing is open within max_days."""
    end = start + timedelta(days=min(max_days, _MAX_RANGE_DAYS))
    async with httpx.AsyncClient(timeout=10) as http:
        resp = await http.get(
            f"{_API_BASE}/calendars/{calendar_id}/free-slots",
            headers=_headers(token),
            params={
                "startDate": int(start.timestamp() * 1000),
                "endDate": int(end.timestamp() * 1000),
                "timezone": tz_name,
            },
        )
    _raise_with_context(resp)
    # {"2026-10-27": {"slots": ["2026-10-27T09:00:00-07:00", ...]}, ..., "traceId": "..."}
    by_day = {k: v["slots"] for k, v in resp.json().items() if isinstance(v, dict) and v.get("slots")}
    for day in sorted(by_day):
        slots = sorted(datetime.fromisoformat(s) for s in by_day[day])
        slots = [s for s in slots if s > start]
        if slots:
            return slots
    return []


async def create_appointment(
    token: str, calendar_id: str, date_str: str, time_str: str, tz,
    name: str, email: str | None, phone: str, reason: str,
) -> dict:
    """Upserts the lead as a GHL contact and books them a confirmed
    appointment. GHL validates the slot itself, so a time that was just
    taken raises. Returns GHL's appointment object (its `id` is the
    booking's external id) plus `start_utc`."""
    local_start = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=tz)
    first, _, last = (name or "").strip().partition(" ")
    async with httpx.AsyncClient(timeout=15) as http:
        resp = await http.get(f"{_API_BASE}/calendars/{calendar_id}", headers=_headers(token))
        _raise_with_context(resp)
        location_id = resp.json()["calendar"]["locationId"]

        resp = await http.post(
            f"{_API_BASE}/contacts/upsert",
            headers={**_headers(token), "Version": "2021-07-28"},
            json={
                "locationId": location_id, "name": name, "firstName": first or None,
                "lastName": last or None, "email": email or None, "phone": phone, "source": "AI text agent",
            },
        )
        _raise_with_context(resp)
        contact_id = resp.json()["contact"]["id"]

        resp = await http.post(
            f"{_API_BASE}/calendars/events/appointments",
            headers=_headers(token),
            json={
                "calendarId": calendar_id,
                "locationId": location_id,
                "contactId": contact_id,
                "startTime": local_start.isoformat(),
                "title": f"Free consult: {name}",
                "description": reason,
                "appointmentStatus": "confirmed",
                "toNotify": True,
            },
        )
        _raise_with_context(resp)
    appt = resp.json()
    appt["start_utc"] = local_start.astimezone(timezone.utc)
    return appt
