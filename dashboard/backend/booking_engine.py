"""DigiGrowth Booking: our own replacement for Calendly on client funnels.

How it fits together:
  - The clinic shares its Google Calendar with the Google account the server
    already holds a token for: dylanrg@digigrowthllc.com via
    GOOGLE_REFRESH_TOKEN (the business account), or a dedicated
    BOOKING_GOOGLE_REFRESH_TOKEN if set, with "Make changes to events".
    Deliberately NOT the personal-calendar token (dylangroenendijk@gmail.com):
    clinics should see the business address. No per-client OAuth, so no Google app verification.
  - booking_settings / booking_event_types / booking_hours /
    booking_date_overrides (db.py) describe when and what a patient can book.
  - get_slots() = weekly hours (or a date override) minus Google free/busy
    minus our own active bookings, padded by the event type's buffers, after
    minimum notice, within max_days_ahead, under the daily cap.
  - reserve() takes a per-client advisory lock, re-checks overlap, and
    inserts the bookings row. Free events confirm immediately; paid events
    hold the slot (status pending_payment) and hand back a Stripe Checkout
    URL on the CLINIC's own connected Stripe account (direct charge, no
    platform fee: 100% goes to the clinic).
  - _finalize() is the one place a booking becomes real: the event goes on
    the clinic's calendar, and calendly_webhooks.record_booking() runs the
    exact same contact match/create, lead tagging, appointment_reminders row
    (so the existing 24h/6h/1h reminders, no-show and cancellation drips and
    the client's booking alert all fire unchanged) and funnel conversion
    that a Calendly booking runs. The appointment row's calendly_event_uri
    is "dgbook:<booking id>" so cancels can find the booking again.
  - Patients get a manage link (/booking/<manage_token>) to reschedule or
    cancel. A cancel from the OS/portal (routers/appointments.py's
    cancel_appointment) calls on_appointment_cancelled() so the calendar
    event is removed there too.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import secrets
import time as _time
import uuid
from datetime import date, datetime, time, timedelta, timezone
from urllib.parse import quote, urlencode
from zoneinfo import ZoneInfo

import httpx

from db import get_pool

ACTIVE_STATUSES = ("pending_payment", "confirmed")
HOLD_MINUTES = 32          # Stripe Checkout's minimum expiry is 30 minutes
_BUSY_CACHE_SECONDS = 45
_busy_cache: dict[tuple, tuple[float, list[tuple[datetime, datetime]]]] = {}


class BookingError(Exception):
    """A problem worth showing the patient/admin as-is (slot taken, etc.)."""


# ── URLs ─────────────────────────────────────────────────────────────────────

def public_base() -> str:
    return (os.environ.get("LANDING_PAGES_URL") or os.environ.get("DASHBOARD_URL")
            or "https://digigrowth-brain-production.up.railway.app").rstrip("/")


def booking_page_url(booking_slug: str) -> str:
    return f"{public_base()}/book/{booking_slug}"


def manage_url(token: str) -> str:
    return f"{public_base()}/booking/{token}"


# ── Google Calendar (sync client, always called via asyncio.to_thread) ─────

def _gcal():
    from googleapiclient.discovery import build
    import integrations
    if os.environ.get("BOOKING_GOOGLE_REFRESH_TOKEN"):
        creds = integrations._make_creds(
            "BOOKING_GOOGLE_REFRESH_TOKEN", "Set BOOKING_GOOGLE_REFRESH_TOKEN for the booking calendar account.",
        )
    else:
        creds = integrations._business_creds()  # dylanrg@digigrowthllc.com
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _gcal_account_and_calendars() -> dict:
    svc = _gcal()
    items, page = [], None
    while True:
        res = svc.calendarList().list(pageToken=page, maxResults=250).execute()
        items += res.get("items", [])
        page = res.get("nextPageToken")
        if not page:
            break
    account = next((c["id"] for c in items if c.get("primary")), None)
    return {
        "account": account,
        "calendars": [
            {"id": c["id"], "name": c.get("summaryOverride") or c.get("summary") or c["id"],
             "access_role": c.get("accessRole"), "primary": bool(c.get("primary")),
             "time_zone": c.get("timeZone")}
            for c in items
        ],
    }


def _gcal_busy(calendar_ids: list[str], start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    svc = _gcal()
    res = svc.freebusy().query(body={
        "timeMin": start.astimezone(timezone.utc).isoformat(),
        "timeMax": end.astimezone(timezone.utc).isoformat(),
        "items": [{"id": cid} for cid in calendar_ids],
    }).execute()
    busy = []
    for cid, cal in (res.get("calendars") or {}).items():
        if cal.get("errors"):
            # notFound = not shared with us (any more). Never offer times we
            # can't actually check.
            reasons = ", ".join(e.get("reason", "?") for e in cal["errors"])
            raise BookingError(f"Can't read calendar {cid} ({reasons}). Is it still shared with us?")
        for b in cal.get("busy", []):
            busy.append((datetime.fromisoformat(b["start"].replace("Z", "+00:00")),
                         datetime.fromisoformat(b["end"].replace("Z", "+00:00"))))
    return busy


def _gcal_insert(calendar_id: str, body: dict, with_meet: bool) -> dict:
    svc = _gcal()
    body = {k: v for k, v in body.items() if v is not None}
    if with_meet:
        body = {**body, "conferenceData": {"createRequest": {
            "requestId": uuid.uuid4().hex, "conferenceSolutionKey": {"type": "hangoutsMeet"},
        }}}
    ev = svc.events().insert(
        calendarId=calendar_id, body=body, conferenceDataVersion=1 if with_meet else 0, sendUpdates="none",
    ).execute()
    meet = ev.get("hangoutLink")
    if not meet:
        for ep in (ev.get("conferenceData") or {}).get("entryPoints", []):
            if ep.get("entryPointType") == "video":
                meet = ep.get("uri")
    return {"id": ev["id"], "meet_link": meet}


def _gcal_move(calendar_id: str, event_id: str, start: datetime, end: datetime) -> None:
    svc = _gcal()
    svc.events().patch(calendarId=calendar_id, eventId=event_id, sendUpdates="none", body={
        "start": {"dateTime": start.isoformat()}, "end": {"dateTime": end.isoformat()},
    }).execute()


def _gcal_delete(calendar_id: str, event_id: str) -> None:
    svc = _gcal()
    try:
        svc.events().delete(calendarId=calendar_id, eventId=event_id, sendUpdates="none").execute()
    except Exception as e:
        if "410" in str(e) or "404" in str(e):  # already gone
            return
        raise


async def google_status() -> dict:
    """Which Google account clinics should share with, and every calendar
    it can currently see (the Booking tab's calendar picker)."""
    try:
        return {"ok": True, **(await asyncio.to_thread(_gcal_account_and_calendars))}
    except Exception as e:
        return {"ok": False, "error": str(e), "account": None, "calendars": []}


# ── Stripe (platform key; every booking call acts on the clinic's account) ──

_STRIPE = "https://api.stripe.com/v1"


def stripe_configured() -> bool:
    return bool(os.environ.get("STRIPE_SECRET_KEY"))


def _flatten(prefix: str, value, out: list):
    if isinstance(value, dict):
        for k, v in value.items():
            _flatten(f"{prefix}[{k}]" if prefix else k, v, out)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            _flatten(f"{prefix}[{i}]", v, out)
    elif value is not None:
        out.append((prefix, "true" if value is True else "false" if value is False else str(value)))


async def _stripe(method: str, path: str, data: dict | None = None, account: str | None = None) -> dict:
    key = os.environ.get("STRIPE_SECRET_KEY")
    if not key:
        raise BookingError("Stripe isn't set up yet (STRIPE_SECRET_KEY missing).")
    headers = {"Stripe-Account": account} if account else {}
    form: list = []
    if data:
        _flatten("", data, form)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.request(method, f"{_STRIPE}{path}", auth=(key, ""), headers=headers,
                                 data=form if method != "GET" else None,
                                 params=form if method == "GET" else None)
    body = r.json()
    if r.status_code >= 400:
        raise BookingError(f"Stripe: {(body.get('error') or {}).get('message') or r.text}")
    return body


async def stripe_onboarding_link(client_id: int, return_url: str, refresh_url: str | None = None) -> str:
    """Creates the clinic's Standard connected account on first use, then a
    fresh onboarding link (they're single-use and short-lived)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        s = await conn.fetchrow("SELECT stripe_account_id FROM booking_settings WHERE client_id = $1", client_id)
        email = await conn.fetchval("SELECT email FROM clients WHERE id = $1", client_id)
    acct = s["stripe_account_id"] if s else None
    if not acct:
        created = await _stripe("POST", "/accounts", {"type": "standard", "email": email or None,
                                                      "metadata": {"digigrowth_client_id": client_id}})
        acct = created["id"]
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE booking_settings SET stripe_account_id = $2, updated_at = now() WHERE client_id = $1",
                client_id, acct,
            )
    link = await _stripe("POST", "/account_links", {
        "account": acct, "type": "account_onboarding",
        "refresh_url": refresh_url or return_url, "return_url": return_url,
    })
    return link["url"]


async def stripe_refresh_status(client_id: int) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        acct = await conn.fetchval("SELECT stripe_account_id FROM booking_settings WHERE client_id = $1", client_id)
    if not acct:
        return {"connected": False, "charges_enabled": False}
    a = await _stripe("GET", f"/accounts/{acct}")
    enabled = bool(a.get("charges_enabled"))
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE booking_settings SET stripe_charges_enabled = $2, updated_at = now() WHERE client_id = $1",
            client_id, enabled,
        )
    return {"connected": True, "account_id": acct, "charges_enabled": enabled,
            "details_submitted": bool(a.get("details_submitted")),
            "business_name": (a.get("business_profile") or {}).get("name")}


def verify_stripe_signature(payload: bytes, header: str, secret: str, tolerance: int = 300) -> bool:
    try:
        parts = dict(p.split("=", 1) for p in header.split(",") if "=" in p)
        ts = int(parts["t"])
        sigs = [p.split("=", 1)[1] for p in header.split(",") if p.startswith("v1=")]
    except Exception:
        return False
    if abs(_time.time() - ts) > tolerance:
        return False
    expected = hmac.new(secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, s) for s in sigs)


# ── Settings / lookup ────────────────────────────────────────────────────────

async def client_timezone(conn, client_id: int, settings) -> str:
    if settings and settings["timezone"]:
        return settings["timezone"]
    from timezone_lookup import clinic_timezone
    return await clinic_timezone(conn, client_id)


async def resolve_public(key: str, via_landing_page: bool) -> dict | None:
    """booking_slug (/book/<key>) or a landing page slug (/lp/<key>/book)
    -> enabled booking settings + clinic name, or None."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if via_landing_page:
            client_id = await conn.fetchval("SELECT client_id FROM landing_pages WHERE slug = $1", key)
            if client_id is None:
                return None
            s = await conn.fetchrow("SELECT * FROM booking_settings WHERE client_id = $1 AND enabled", client_id)
        else:
            s = await conn.fetchrow("SELECT * FROM booking_settings WHERE booking_slug = $1 AND enabled", key)
        if not s:
            return None
        name = await conn.fetchval("SELECT name FROM clients WHERE id = $1", s["client_id"])
        tz = await client_timezone(conn, s["client_id"], s)
    return {"settings": dict(s), "client_name": name, "timezone": tz}


async def is_enabled_for_landing_page(slug: str) -> bool:
    return (await resolve_public(slug, True)) is not None


async def public_event_types(client_id: int) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM booking_event_types WHERE client_id = $1 AND active ORDER BY sort_order, id", client_id,
        )
    return [_public_event(dict(r)) for r in rows]


def _public_event(e: dict) -> dict:
    return {k: e[k] for k in (
        "id", "slug", "name", "description", "duration_min", "location_type", "location_text",
        "price_cents", "anchor_price_cents", "spots_per_month", "ask_question", "max_days_ahead",
    )}


# ── Availability ─────────────────────────────────────────────────────────────

def _overlaps(a0, a1, b0, b1) -> bool:
    return a0 < b1 and b0 < a1


async def _busy(conn, client_id: int, settings: dict, start: datetime, end: datetime,
                exclude_booking_id: int | None, use_cache: bool) -> list[tuple[datetime, datetime]]:
    cal_ids = [c for c in [settings.get("calendar_id"), *(settings.get("busy_calendar_ids") or [])] if c]
    if not cal_ids:
        raise BookingError("No calendar is connected for this clinic yet.")
    ck = (client_id, tuple(cal_ids), start.isoformat(), end.isoformat())
    hit = _busy_cache.get(ck)
    if use_cache and hit and _time.time() - hit[0] < _BUSY_CACHE_SECONDS:
        google = hit[1]
    else:
        google = await asyncio.to_thread(_gcal_busy, cal_ids, start, end)
        _busy_cache[ck] = (_time.time(), google)

    exclude = None
    rows = await conn.fetch(
        """SELECT id, start_at, end_at FROM bookings
           WHERE client_id = $1 AND start_at < $3 AND end_at > $2
             AND (status = 'confirmed' OR (status = 'pending_payment' AND hold_expires_at > now()))""",
        client_id, start, end,
    )
    ours = []
    for r in rows:
        if r["id"] == exclude_booking_id:
            exclude = (r["start_at"], r["end_at"])
            continue
        ours.append((r["start_at"], r["end_at"]))
    # A rescheduling booking's own calendar event shows as busy at Google:
    # drop that exact interval so the patient can shift by less than its length.
    if exclude:
        google = [b for b in google if not (b[0] == exclude[0] and b[1] == exclude[1])]
    return google + ours


def _windows_for(day: date, hours: list, overrides: dict, tz: ZoneInfo) -> list[tuple[datetime, datetime]]:
    if day in overrides:
        spans = [(o["start_time"], o["end_time"]) for o in overrides[day] if not o["closed"] and o["start_time"]]
    else:
        spans = [(h["start_time"], h["end_time"]) for h in hours if h["weekday"] == day.weekday()]
    out = []
    for s, e in spans:
        if s and e and e > s:
            out.append((datetime.combine(day, s, tzinfo=tz), datetime.combine(day, e, tzinfo=tz)))
    return out


def compute_days(ev: dict, hours: list, overrides: dict, busy: list, per_day_count: dict, tz: ZoneInfo,
                 first: date, last: date, earliest: datetime) -> list[dict]:
    """Pure slot math (unit-tested in tests/test_booking_slots.py)."""
    dur = timedelta(minutes=ev["duration_min"])
    step = timedelta(minutes=ev["slot_interval_min"] or ev["duration_min"])
    pre, post = timedelta(minutes=ev["buffer_before_min"]), timedelta(minutes=ev["buffer_after_min"])
    out_days = []
    day = first
    while day <= last:
        slots = []
        if not (ev["daily_cap"] and per_day_count.get(day, 0) >= ev["daily_cap"]):
            for w0, w1 in _windows_for(day, hours, overrides, tz):
                t = w0
                while t + dur <= w1:
                    if t >= earliest and not any(_overlaps(t - pre, t + dur + post, b0, b1) for b0, b1 in busy):
                        slots.append(t.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"))
                    t += step
        out_days.append({"date": day.isoformat(), "slots": sorted(set(slots))})
        day += timedelta(days=1)
    return out_days


async def get_slots(client_id: int, event_type_id: int, from_day: date | None = None, days: int = 14,
                    exclude_booking_id: int | None = None, use_cache: bool = True) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        settings = await conn.fetchrow("SELECT * FROM booking_settings WHERE client_id = $1", client_id)
        ev = await conn.fetchrow(
            "SELECT * FROM booking_event_types WHERE id = $1 AND client_id = $2", event_type_id, client_id,
        )
        if not settings or not ev:
            raise BookingError("This booking page isn't set up yet.")
        settings, ev = dict(settings), dict(ev)
        tz_name = await client_timezone(conn, client_id, settings)
        tz = ZoneInfo(tz_name)
        hours = [dict(h) for h in await conn.fetch("SELECT * FROM booking_hours WHERE client_id = $1", client_id)]
        overrides: dict[date, list] = {}
        for o in await conn.fetch("SELECT * FROM booking_date_overrides WHERE client_id = $1", client_id):
            overrides.setdefault(o["date"], []).append(dict(o))

        now = datetime.now(timezone.utc)
        today = now.astimezone(tz).date()
        first = max(from_day or today, today)
        last_allowed = today + timedelta(days=ev["max_days_ahead"])
        last = min(first + timedelta(days=days - 1), last_allowed)
        earliest = now + timedelta(hours=ev["min_notice_hours"])
        if last < first:
            return {"timezone": tz_name, "days": []}

        range_start = datetime.combine(first, time.min, tzinfo=tz)
        range_end = datetime.combine(last + timedelta(days=1), time.min, tzinfo=tz)
        busy = await _busy(conn, client_id, settings, range_start - timedelta(hours=4),
                           range_end + timedelta(hours=4), exclude_booking_id, use_cache)

        per_day_count: dict[date, int] = {}
        if ev["daily_cap"]:
            for r in await conn.fetch(
                """SELECT start_at FROM bookings WHERE client_id = $1 AND event_type_id = $2
                     AND start_at >= $3 AND start_at < $4 AND id IS DISTINCT FROM $5
                     AND (status = 'confirmed' OR (status = 'pending_payment' AND hold_expires_at > now()))""",
                client_id, event_type_id, range_start, range_end, exclude_booking_id,
            ):
                d = r["start_at"].astimezone(tz).date()
                per_day_count[d] = per_day_count.get(d, 0) + 1

    out_days = compute_days(ev, hours, overrides, busy, per_day_count, tz, first, last, earliest)
    return {"timezone": tz_name, "days": out_days}


# ── Booking lifecycle ────────────────────────────────────────────────────────

def _lock_key(client_id: int) -> int:
    return int(hashlib.sha1(f"booking:{client_id}".encode()).hexdigest()[:15], 16)


async def expire_stale_holds() -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        res = await conn.execute(
            "UPDATE bookings SET status = 'expired' WHERE status = 'pending_payment' AND hold_expires_at < now()"
        )
    return int(res.split()[-1])


def _parse_start(start_iso: str) -> datetime:
    try:
        dt = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
    except ValueError:
        raise BookingError("Invalid time.")
    if dt.tzinfo is None:
        raise BookingError("Invalid time.")
    return dt.astimezone(timezone.utc)


async def _assert_slot_open(client_id: int, ev: dict, start: datetime, exclude_booking_id: int | None = None):
    # Fresh (uncached) check of the days around the requested start; a
    # +-1 day window covers any clinic timezone offset from UTC.
    tz_days = await get_slots(client_id, ev["id"], from_day=(start - timedelta(days=1)).date(), days=3,
                              exclude_booking_id=exclude_booking_id, use_cache=False)
    want = start.isoformat().replace("+00:00", "Z")
    if not any(want in d["slots"] for d in tz_days["days"]):
        raise BookingError("Sorry, that time was just taken. Please pick another.")


async def reserve(client_id: int, event_type_id: int, start_iso: str, name: str, phone: str, email: str | None,
                  answer: str | None, utm_source: str | None, utm_content: str | None,
                  return_base: str, session_id: str | None = None) -> dict:
    # Name + mobile only (Dylan, 2026-11-06): texts are how patients are
    # reached; email is optional (Stripe collects one for paid receipts).
    name, phone, email = (name or "").strip(), (phone or "").strip(), (email or "").strip() or None
    if not name or len(name) > 120:
        raise BookingError("Please enter your name.")
    if len("".join(c for c in phone if c.isdigit())) < 10:
        raise BookingError("Please enter a valid mobile number.")
    if email and ("@" not in email or len(email) > 200):
        raise BookingError("That email doesn't look right. Fix it or leave it blank.")
    session_id = (session_id or "").strip()[:64] or None
    start = _parse_start(start_iso)

    pool = await get_pool()
    async with pool.acquire() as conn:
        ev = await conn.fetchrow(
            "SELECT * FROM booking_event_types WHERE id = $1 AND client_id = $2 AND active", event_type_id, client_id,
        )
        settings = await conn.fetchrow("SELECT * FROM booking_settings WHERE client_id = $1 AND enabled", client_id)
    if not ev or not settings:
        raise BookingError("This booking page isn't available.")
    ev, settings = dict(ev), dict(settings)
    paid = ev["price_cents"] > 0
    if paid and not (settings["stripe_account_id"] and settings["stripe_charges_enabled"] and stripe_configured()):
        raise BookingError("Online payment isn't set up for this clinic yet. Please call the clinic to book.")

    await _assert_slot_open(client_id, ev, start)
    end = start + timedelta(minutes=ev["duration_min"])
    token = secrets.token_urlsafe(18)

    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("SELECT pg_advisory_xact_lock($1)", _lock_key(client_id))
            clash = await conn.fetchval(
                """SELECT 1 FROM bookings WHERE client_id = $1 AND start_at < $3 AND end_at > $2
                     AND (status = 'confirmed' OR (status = 'pending_payment' AND hold_expires_at > now()))""",
                client_id, start, end,
            )
            if clash:
                raise BookingError("Sorry, that time was just taken. Please pick another.")
            booking = await conn.fetchrow(
                """INSERT INTO bookings (client_id, event_type_id, status, start_at, end_at, name, phone, email,
                       answer, utm_source, utm_content, manage_token, price_cents, hold_expires_at, session_id)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15) RETURNING *""",
                client_id, event_type_id, "pending_payment" if paid else "confirmed", start, end, name, phone,
                email, (answer or "").strip()[:1000] or None, utm_source, utm_content, token, ev["price_cents"],
                datetime.now(timezone.utc) + timedelta(minutes=HOLD_MINUTES) if paid else None, session_id,
            )
    booking = dict(booking)
    import booking_conversion
    await booking_conversion.link_partial(client_id, session_id, phone, booking["id"])
    await booking_conversion.log_step(client_id, session_id, "submit", event_type_id, utm_source, utm_content)

    if not paid:
        await _finalize(booking["id"])
        await booking_conversion.log_step(client_id, session_id, "booked", event_type_id, utm_source, utm_content)
        return {"status": "confirmed", "manage_url": manage_url(token), "token": token}

    try:
        session = await _stripe("POST", "/checkout/sessions", {
            "mode": "payment",
            "customer_email": email,
            "line_items": [{"quantity": 1, "price_data": {
                "currency": "usd", "unit_amount": ev["price_cents"],
                "product_data": {"name": ev["name"]},
            }}],
            "metadata": {"digigrowth_booking_id": booking["id"]},
            "payment_intent_data": {"metadata": {"digigrowth_booking_id": booking["id"]}},
            "expires_at": int(_time.time()) + 31 * 60,
            "success_url": f"{return_base}/return?b={token}&session_id={{CHECKOUT_SESSION_ID}}",
            "cancel_url": f"{return_base}?cancelled={token}",
        }, account=settings["stripe_account_id"])
    except Exception:
        async with pool.acquire() as conn:
            await conn.execute("UPDATE bookings SET status = 'expired' WHERE id = $1", booking["id"])
        raise
    async with pool.acquire() as conn:
        await conn.execute("UPDATE bookings SET stripe_session_id = $2 WHERE id = $1", booking["id"], session["id"])
    return {"status": "pending_payment", "checkout_url": session["url"], "token": token}


async def release_hold(token: str) -> None:
    """Patient backed out of Stripe Checkout: free the slot right away."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE bookings SET status = 'expired' WHERE manage_token = $1 AND status = 'pending_payment'", token,
        )


async def confirm_payment(booking_id: int, session: dict) -> str:
    """Stripe says this booking's checkout is paid. Confirms it, even if the
    hold lapsed, as long as nobody else took the time meanwhile; otherwise
    refunds. Idempotent (webhook + success redirect both call it)."""
    if session.get("payment_status") != "paid":
        return "unpaid"
    pool = await get_pool()
    async with pool.acquire() as conn:
        b = await conn.fetchrow("SELECT * FROM bookings WHERE id = $1", booking_id)
        if not b:
            return "missing"
        if b["status"] == "confirmed" or b["paid_at"]:
            return "already"
        acct = await conn.fetchval("SELECT stripe_account_id FROM booking_settings WHERE client_id = $1", b["client_id"])
        async with conn.transaction():
            await conn.execute("SELECT pg_advisory_xact_lock($1)", _lock_key(b["client_id"]))
            clash = await conn.fetchval(
                """SELECT 1 FROM bookings WHERE client_id = $1 AND id <> $4 AND start_at < $3 AND end_at > $2
                     AND (status = 'confirmed' OR (status = 'pending_payment' AND hold_expires_at > now()))""",
                b["client_id"], b["start_at"], b["end_at"], booking_id,
            )
            if not clash:
                await conn.execute(
                    "UPDATE bookings SET status = 'confirmed', paid_at = now(), stripe_payment_intent = $2, "
                    "hold_expires_at = NULL WHERE id = $1",
                    booking_id, session.get("payment_intent"),
                )
    if clash:
        try:
            await _stripe("POST", "/refunds", {"payment_intent": session.get("payment_intent")}, account=acct)
            refunded = True
        except Exception as e:
            print(f"[booking] refund after lost slot failed for booking {booking_id}: {e}")
            refunded = False
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE bookings SET status = 'cancelled', cancelled_at = now(), paid_at = now(), "
                "stripe_payment_intent = $2, refunded_at = CASE WHEN $3 THEN now() END, "
                "cancel_reason = 'Slot was taken while paying; payment refunded' WHERE id = $1",
                booking_id, session.get("payment_intent"), refunded,
            )
        return "refunded"
    await _finalize(booking_id)
    import booking_conversion
    await booking_conversion.log_step(b["client_id"], b["session_id"], "booked", b["event_type_id"],
                                      b["utm_source"], b["utm_content"])
    return "confirmed"


async def confirm_from_return(token: str, session_id: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        b = await conn.fetchrow(
            "SELECT b.id, b.stripe_session_id, s.stripe_account_id FROM bookings b "
            "JOIN booking_settings s ON s.client_id = b.client_id WHERE b.manage_token = $1", token,
        )
    if not b or b["stripe_session_id"] != session_id:
        return
    session = await _stripe("GET", f"/checkout/sessions/{session_id}", account=b["stripe_account_id"])
    await confirm_payment(b["id"], session)


async def handle_stripe_event(event: dict) -> None:
    obj = (event.get("data") or {}).get("object") or {}
    booking_id = (obj.get("metadata") or {}).get("digigrowth_booking_id")
    if not booking_id:
        return
    if event.get("type") in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        await confirm_payment(int(booking_id), obj)
    elif event.get("type") == "checkout.session.expired":
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE bookings SET status = 'expired' WHERE id = $1 AND status = 'pending_payment'", int(booking_id),
            )


def _fmt_local(dt: datetime, tz: ZoneInfo) -> tuple[str, str]:
    local = dt.astimezone(tz)
    return local.strftime("%A, %B ") + str(local.day), local.strftime("%I:%M %p").lstrip("0")


async def _context(conn, booking_id: int) -> tuple[dict, dict, dict, str, str]:
    b = dict(await conn.fetchrow("SELECT * FROM bookings WHERE id = $1", booking_id))
    ev = dict(await conn.fetchrow("SELECT * FROM booking_event_types WHERE id = $1", b["event_type_id"]))
    s = dict(await conn.fetchrow("SELECT * FROM booking_settings WHERE client_id = $1", b["client_id"]))
    clinic = await conn.fetchval("SELECT name FROM clients WHERE id = $1", b["client_id"]) or "the clinic"
    tz = await client_timezone(conn, b["client_id"], s)
    return b, ev, s, clinic, tz


def _location_line(ev: dict, meet_link: str | None) -> str:
    if ev["location_type"] == "google_meet":
        return f"Join here: {meet_link}" if meet_link else "We'll send your video link."
    if ev["location_type"] == "phone":
        return "We'll call you at this number."
    return f"Location: {ev['location_text']}" if ev.get("location_text") else ""


async def _finalize(booking_id: int) -> None:
    """A confirmed booking becomes real: calendar event, CRM + appointment
    row (reminders etc.), patient confirmation text. Each step logs its own
    failure instead of undoing the booking: the patient already has it."""
    from routers.calendly_webhooks import record_booking

    pool = await get_pool()
    async with pool.acquire() as conn:
        b, ev, s, clinic, tz_name = await _context(conn, booking_id)
    tz = ZoneInfo(tz_name)

    if not b["google_event_id"] and s.get("calendar_id"):
        desc = "\n".join(x for x in [
            f"Phone: {b['phone']}", f"Email: {b['email']}",
            f"Note: {b['answer']}" if b["answer"] else None,
            f"Paid online: ${b['price_cents'] / 100:.2f}" if b["paid_at"] else None,
            f"Source: {'Facebook/Instagram ad' if b['utm_content'] == 'meta' else 'Ad funnel' if b['utm_source'] == 'paid_ad' else 'Booking page'}",
            "", "Booked through DigiGrowth. To reschedule or cancel, use the DigiGrowth portal.",
        ] if x is not None)
        try:
            created = await asyncio.to_thread(_gcal_insert, s["calendar_id"], {
                "summary": f"{ev['name']}: {b['name']}",
                "description": desc,
                "location": ev["location_text"] if ev["location_type"] == "in_person" else None,
                "start": {"dateTime": b["start_at"].isoformat()},
                "end": {"dateTime": b["end_at"].isoformat()},
                "extendedProperties": {"private": {"digigrowth_booking_id": str(booking_id)}},
            }, ev["location_type"] == "google_meet")
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE bookings SET google_event_id = $2, meet_link = $3, calendar_error = NULL WHERE id = $1",
                    booking_id, created["id"], created["meet_link"],
                )
            b["meet_link"] = created["meet_link"]
            _busy_cache.clear()
        except Exception as e:
            print(f"[booking] calendar insert failed for booking {booking_id}: {e}")
            async with pool.acquire() as conn:
                await conn.execute("UPDATE bookings SET calendar_error = $2 WHERE id = $1", booking_id, str(e)[:500])

    if not b["appointment_id"]:
        try:
            appt = await record_booking(
                name=b["name"], email=b["email"], phone=b["phone"], start_utc=b["start_at"], tz_name=tz_name,
                tracking={"utm_source": b["utm_source"], "utm_content": b["utm_content"]},
                event_uri=f"dgbook:{booking_id}", client_id=b["client_id"], call_type="discovery",
            )
            async with pool.acquire() as conn:
                await conn.execute("UPDATE bookings SET appointment_id = $2 WHERE id = $1", booking_id, appt["id"])
        except Exception as e:
            print(f"[booking] record_booking failed for booking {booking_id}: {e}")

    day, at = _fmt_local(b["start_at"], tz)
    first = (b["name"] or "").split()[0] if b["name"] else "there"
    text = " ".join(x for x in [
        f"Hi {first}, you're booked with {clinic} on {day} at {at}.",
        _location_line(ev, b.get("meet_link")),
        f"Need to reschedule or cancel? {manage_url(b['manage_token'])}",
    ] if x)
    await _text_patient(b["client_id"], b["phone"], text, "booking_confirmation")


async def _text_patient(client_id: int, phone: str | None, text: str, stage: str) -> None:
    if not phone:
        return
    try:
        import client_sms
        pool = await get_pool()
        async with pool.acquire() as conn:
            has_number = await conn.fetchval(
                "SELECT twilio_number FROM client_marketing_config WHERE client_id = $1", client_id,
            )
        if has_number:
            await client_sms.send_client_sms(client_id, phone, text, stage=stage)
    except Exception as e:
        print(f"[booking] patient text failed for client {client_id}: {e}")


async def get_by_token(token: str) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        bid = await conn.fetchval("SELECT id FROM bookings WHERE manage_token = $1", token)
        if not bid:
            return None
        b, ev, s, clinic, tz = await _context(conn, bid)
    return {"booking": b, "event": ev, "settings": s, "clinic": clinic, "timezone": tz}


async def _refund_if_policy(b: dict, s: dict, by_patient: bool) -> bool:
    if not (b["paid_at"] and b["stripe_payment_intent"] and not b["refunded_at"]):
        return False
    policy = s.get("refund_policy") or "none"
    hours_left = (b["start_at"] - datetime.now(timezone.utc)).total_seconds() / 3600
    should = (not by_patient) or policy == "always" or (policy == "24h" and hours_left >= 24)
    if not should:
        return False
    try:
        await _stripe("POST", "/refunds", {"payment_intent": b["stripe_payment_intent"]},
                      account=s["stripe_account_id"])
    except Exception as e:
        print(f"[booking] refund failed for booking {b['id']}: {e}")
        return False
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE bookings SET refunded_at = now() WHERE id = $1", b["id"])
    return True


async def cancel_booking(booking_id: int, by_patient: bool, reason: str | None = None,
                         touch_appointment: bool = True) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        b, ev, s, clinic, tz = await _context(conn, booking_id)
        if b["status"] != "confirmed":
            raise BookingError("This booking is no longer active.")
        await conn.execute(
            "UPDATE bookings SET status = 'cancelled', cancelled_at = now(), cancelled_by = $2, cancel_reason = $3 "
            "WHERE id = $1",
            booking_id, "patient" if by_patient else "staff", (reason or "").strip()[:500] or None,
        )
    _busy_cache.clear()
    if b["google_event_id"] and s.get("calendar_id"):
        try:
            await asyncio.to_thread(_gcal_delete, s["calendar_id"], b["google_event_id"])
        except Exception as e:
            print(f"[booking] calendar delete failed for booking {booking_id}: {e}")
    if touch_appointment and b["appointment_id"]:
        from fastapi import HTTPException
        from routers.appointments import cancel_appointment
        try:
            # Patient canceled themselves -> recovery drip, same as a Calendly
            # invitee cancel. Staff cancels stay silent.
            await cancel_appointment(b["appointment_id"], notify=by_patient)
        except HTTPException:
            pass
    refunded = await _refund_if_policy(b, s, by_patient)
    return {"ok": True, "refunded": refunded}


async def on_appointment_cancelled(appointment_id: int) -> None:
    """Hook from routers/appointments.py: a booking-backed appointment was
    canceled in the OS/portal. Mirror it without re-entering cancel_appointment."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        bid = await conn.fetchval(
            "SELECT id FROM bookings WHERE appointment_id = $1 AND status = 'confirmed'", appointment_id,
        )
    if bid:
        try:
            await cancel_booking(bid, by_patient=False, reason="Canceled in DigiGrowth", touch_appointment=False)
        except BookingError:
            pass


async def reschedule_booking(booking_id: int, new_start_iso: str) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        b, ev, s, clinic, tz_name = await _context(conn, booking_id)
    if b["status"] != "confirmed":
        raise BookingError("This booking is no longer active.")
    start = _parse_start(new_start_iso)
    await _assert_slot_open(b["client_id"], ev, start, exclude_booking_id=booking_id)
    end = start + timedelta(minutes=ev["duration_min"])
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("SELECT pg_advisory_xact_lock($1)", _lock_key(b["client_id"]))
            clash = await conn.fetchval(
                """SELECT 1 FROM bookings WHERE client_id = $1 AND id <> $4 AND start_at < $3 AND end_at > $2
                     AND (status = 'confirmed' OR (status = 'pending_payment' AND hold_expires_at > now()))""",
                b["client_id"], start, end, booking_id,
            )
            if clash:
                raise BookingError("Sorry, that time was just taken. Please pick another.")
            await conn.execute(
                "UPDATE bookings SET start_at = $2, end_at = $3, rescheduled_at = now(), "
                "reschedule_count = reschedule_count + 1 WHERE id = $1",
                booking_id, start, end,
            )
            if b["appointment_id"]:
                # Same reset as routers/appointments.py's reschedule, minus its
                # DigiGrowth-branded reschedule notice (wrong for a patient):
                # fresh reminder windows for the new time.
                await conn.execute(
                    "UPDATE appointment_reminders SET appointment_at = $2, status = 'scheduled', "
                    "reminder_24h_sent_at = NULL, reminder_6h_sent_at = NULL, reminder_1h_sent_at = NULL, "
                    "reminder_steps_sent = '{}'::jsonb, reminders_armed_at = now() WHERE id = $1",
                    b["appointment_id"], start,
                )
    _busy_cache.clear()
    if b["google_event_id"] and s.get("calendar_id"):
        try:
            await asyncio.to_thread(_gcal_move, s["calendar_id"], b["google_event_id"], start, end)
        except Exception as e:
            print(f"[booking] calendar move failed for booking {booking_id}: {e}")
    tz = ZoneInfo(tz_name)
    day, at = _fmt_local(start, tz)
    first = (b["name"] or "").split()[0] if b["name"] else "there"
    await _text_patient(
        b["client_id"], b["phone"],
        f"Hi {first}, your appointment with {clinic} is now {day} at {at}. "
        f"Need to change it again? {manage_url(b['manage_token'])}",
        "booking_rescheduled",
    )
    return {"ok": True}


def google_calendar_add_link(title: str, start: datetime, end: datetime, details: str, location: str) -> str:
    f = "%Y%m%dT%H%M%SZ"
    return "https://calendar.google.com/calendar/render?" + urlencode({
        "action": "TEMPLATE", "text": title,
        "dates": f"{start.astimezone(timezone.utc).strftime(f)}/{end.astimezone(timezone.utc).strftime(f)}",
        "details": details, "location": location or "",
    }, quote_via=quote)
