"""DigiGrowth Booking routes. Engine + design notes: booking_engine.py.

admin_router (mounted under /api with HTTPBasic):
  GET/PUT  /clients/{id}/booking                 settings + event types + hours + overrides + status
  POST     /clients/{id}/booking/event-types     create;  PUT/DELETE /clients/{id}/booking/event-types/{eid}
  PUT      /clients/{id}/booking/hours           replace weekly hours
  PUT      /clients/{id}/booking/overrides       replace date overrides
  GET      /clients/{id}/booking/slots           preview availability
  GET      /clients/{id}/booking/bookings        recent bookings
  POST     /clients/{id}/booking/bookings/{bid}/cancel
  POST     /clients/{id}/booking/stripe/connect  onboarding link for the clinic
  POST     /clients/{id}/booking/stripe/refresh
  GET      /booking/google                       which Google account clinics share with + its calendars

router (public, no auth):
  /book/{key}[...]            canonical booking page (key = booking_slug)
  /lp/{key}/book/[...]        same page on a funnel (key = landing page slug), so it works
                              behind the client-funnels Vercel proxy (/lp/:path*)
  /booking/{token}[...]       patient's manage page (reschedule / cancel)
  POST /webhooks/stripe/booking   Stripe Connect webhook (checkout.session.*)
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from decimal import Decimal
from urllib.parse import quote
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

import booking_conversion as bc
import booking_engine as be
from booking_page import render_page
from db import get_pool

admin_router = APIRouter()
router = APIRouter()

_LOCATION_TYPES = ("in_person", "google_meet", "phone")
_REFUND_POLICIES = ("none", "24h", "always")


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:60] or "book"


def _jsonable(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        if isinstance(v, (datetime, date, time)):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


async def _ensure_settings(conn, client_id: int) -> dict:
    s = await conn.fetchrow("SELECT * FROM booking_settings WHERE client_id = $1", client_id)
    if s:
        return dict(s)
    name = await conn.fetchval("SELECT name FROM clients WHERE id = $1", client_id)
    if name is None:
        raise HTTPException(404, "client not found")
    base = _slugify(name)
    slug, n = base, 1
    while await conn.fetchval("SELECT 1 FROM booking_settings WHERE booking_slug = $1", slug):
        n += 1
        slug = f"{base}-{n}"
    s = await conn.fetchrow(
        "INSERT INTO booking_settings (client_id, booking_slug) VALUES ($1, $2) RETURNING *", client_id, slug,
    )
    return dict(s)


async def _calendar_timezone(calendar_id: str | None) -> str | None:
    """The time zone set on the clinic's own Google Calendar (what Google
    shows the clinic its events in), or None if we can't read it."""
    if not calendar_id:
        return None
    g = await be.google_status()
    tz = next((c.get("time_zone") for c in g.get("calendars", []) if c["id"] == calendar_id), None)
    try:
        ZoneInfo(tz)
    except Exception:
        return None
    return tz


# ── Admin ────────────────────────────────────────────────────────────────────

@admin_router.get("/booking/google")
async def booking_google():
    return await be.google_status()


@admin_router.get("/booking/overview")
async def booking_overview():
    """The OS's Booking Links tab: every client with its booking status,
    plus the next upcoming bookings across all clients."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        clients = await conn.fetch(
            """
            SELECT c.id, c.name, c.status,
                   s.enabled, s.booking_slug, s.calendar_id, s.stripe_account_id, s.stripe_charges_enabled,
                   (SELECT count(*) FROM booking_event_types e WHERE e.client_id = c.id AND e.active) AS event_types,
                   (SELECT count(*) FROM booking_event_types e WHERE e.client_id = c.id AND e.active AND e.price_cents > 0) AS paid_types,
                   (SELECT count(*) FROM booking_hours h WHERE h.client_id = c.id) AS hour_blocks,
                   (SELECT count(*) FROM bookings b WHERE b.client_id = c.id AND b.status = 'confirmed' AND b.start_at > now()) AS upcoming,
                   (SELECT count(*) FROM bookings b WHERE b.client_id = c.id AND b.status = 'confirmed'
                      AND b.created_at > now() - interval '30 days') AS booked_30d,
                   (SELECT count(*) FROM bookings b WHERE b.client_id = c.id AND b.calendar_error IS NOT NULL
                      AND b.status = 'confirmed' AND b.start_at > now()) AS calendar_errors
            FROM clients c
            LEFT JOIN booking_settings s ON s.client_id = c.id
            ORDER BY (s.enabled IS TRUE) DESC, (c.status = 'active') DESC, c.name
            """
        )
        upcoming = await conn.fetch(
            """SELECT b.id, b.client_id, c.name AS client_name, b.name, b.phone, b.start_at, b.paid_at, b.price_cents,
                      e.name AS event_name, b.manage_token
               FROM bookings b JOIN clients c ON c.id = b.client_id
               JOIN booking_event_types e ON e.id = b.event_type_id
               WHERE b.status = 'confirmed' AND b.start_at > now()
               ORDER BY b.start_at LIMIT 25"""
        )
    rows = []
    for r in clients:
        d = _jsonable(dict(r))
        d["public_url"] = be.booking_page_url(r["booking_slug"]) if r["booking_slug"] else None
        missing = []
        if not r["calendar_id"]:
            missing.append("calendar")
        if not r["hour_blocks"]:
            missing.append("hours")
        if not r["event_types"]:
            missing.append("appointment type")
        if r["paid_types"] and not r["stripe_charges_enabled"]:
            missing.append("Stripe")
        d["missing"] = missing
        rows.append(d)
    up = []
    for u in upcoming:
        d = _jsonable(dict(u))
        d["manage_url"] = be.manage_url(u["manage_token"])
        d.pop("manage_token", None)
        up.append(d)
    stats = await bc.funnel_stats(None, 30)
    for d in rows:
        d["funnel"] = stats.get(d["id"])
    return {"clients": rows, "upcoming": up}


_page_autofill_running: set[int] = set()


async def _run_page_autofill(client_id: int) -> None:
    import booking_autofill
    try:
        await booking_autofill.apply_page_details(client_id, overwrite=False)
    except Exception as e:
        print(f"[booking] page auto-fill failed for client {client_id}: {e}")
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE booking_settings SET page_autofill_note = $2 WHERE client_id = $1",
                client_id, f"Auto-fill failed: {str(e)[:300]}",
            )
    finally:
        _page_autofill_running.discard(client_id)


@admin_router.get("/clients/{client_id}/booking")
async def get_booking(client_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        s = await _ensure_settings(conn, client_id)
        # Default since 2026-11-06: the first time a client's booking setup
        # is opened, Page details fill themselves from the portal, website
        # and funnel (booking_autofill.apply_page_details, empty fields only).
        if not s.get("page_autofilled_at") and client_id not in _page_autofill_running:
            _page_autofill_running.add(client_id)
            await conn.execute(
                "UPDATE booking_settings SET page_autofilled_at = now(), "
                "page_autofill_note = 'Filling from the portal, website and funnel...' WHERE client_id = $1",
                client_id,
            )
            s["page_autofilled_at"] = datetime.now(timezone.utc)
            s["page_autofill_note"] = "Filling from the portal, website and funnel..."
            asyncio.create_task(_run_page_autofill(client_id))
        # Clinic timezone fills itself from the clinic's Google Calendar the
        # first time we can read it (also covers calendars picked before this).
        if not s["timezone"] and s["calendar_id"]:
            tz = await _calendar_timezone(s["calendar_id"])
            if tz:
                await conn.execute(
                    "UPDATE booking_settings SET timezone = $2, updated_at = now() WHERE client_id = $1", client_id, tz,
                )
                s["timezone"] = tz
        events = await conn.fetch(
            "SELECT * FROM booking_event_types WHERE client_id = $1 ORDER BY sort_order, id", client_id,
        )
        hours = await conn.fetch(
            "SELECT weekday, start_time, end_time FROM booking_hours WHERE client_id = $1 ORDER BY weekday, start_time",
            client_id,
        )
        overrides = await conn.fetch(
            "SELECT date, closed, start_time, end_time FROM booking_date_overrides "
            "WHERE client_id = $1 AND date >= current_date - 1 ORDER BY date, start_time", client_id,
        )
        tz = await be.client_timezone(conn, client_id, s)
        landing = await conn.fetch(
            "SELECT slug FROM landing_pages WHERE client_id = $1 ORDER BY created_at", client_id,
        )
    return {
        "settings": _jsonable(s),
        "effective_timezone": tz,
        "event_types": [_jsonable(dict(e)) for e in events],
        "hours": [_jsonable(dict(h)) for h in hours],
        "overrides": [_jsonable(dict(o)) for o in overrides],
        "public_url": be.booking_page_url(s["booking_slug"]),
        "funnel_urls": [f"{be.public_base()}/lp/{r['slug']}/book" for r in landing],
        "stripe_platform_configured": be.stripe_configured(),
        "stripe_webhook_configured": bool(os.environ.get("STRIPE_CONNECT_WEBHOOK_SECRET")),
        "funnel": (await bc.funnel_stats(client_id, 30)).get(client_id),
        "places_configured": bool(os.environ.get("PLACES_API_KEY")),
        "page_autofill_running": client_id in _page_autofill_running,
    }


@admin_router.put("/clients/{client_id}/booking")
async def save_booking_settings(client_id: int, payload: dict):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _ensure_settings(conn, client_id)
        updates: dict = {}
        if "enabled" in payload:
            updates["enabled"] = bool(payload["enabled"])
        if "booking_slug" in payload:
            slug = _slugify(payload["booking_slug"])
            if await conn.fetchval(
                "SELECT 1 FROM booking_settings WHERE booking_slug = $1 AND client_id <> $2", slug, client_id,
            ):
                raise HTTPException(400, "That link name is taken.")
            updates["booking_slug"] = slug
        if "calendar_id" in payload:
            updates["calendar_id"] = (payload["calendar_id"] or "").strip() or None
        if "busy_calendar_ids" in payload:
            updates["busy_calendar_ids"] = [c.strip() for c in (payload["busy_calendar_ids"] or []) if c and c.strip()]
        if "timezone" in payload:
            tz = (payload["timezone"] or "").strip() or None
            if tz:
                try:
                    ZoneInfo(tz)
                except Exception:
                    raise HTTPException(400, f"Unknown timezone: {tz}")
            updates["timezone"] = tz
        if "accent_color" in payload:
            c = (payload["accent_color"] or "").strip()
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", c):
                raise HTTPException(400, "Color must look like #2f6fd6")
            updates["accent_color"] = c
        if "refund_policy" in payload:
            if payload["refund_policy"] not in _REFUND_POLICIES:
                raise HTTPException(400, "refund_policy must be none, 24h or always")
            updates["refund_policy"] = payload["refund_policy"]
        for f in ("provider_name", "provider_title", "photo_url", "logo_url", "what_to_expect"):
            if f in payload:
                updates[f] = (payload[f] or "").strip()[:2000] or None
        for f in ("photo_url", "logo_url"):
            if updates.get(f) and not re.match(r"^(https://|/lp/|/book-asset/)", updates[f]):
                raise HTTPException(400, "Photo and logo must be https:// links")
        if "abandon_followup" in payload:
            updates["abandon_followup"] = bool(payload["abandon_followup"])
        if "review_rating" in payload:
            v = payload["review_rating"]
            if v in (None, ""):
                updates["review_rating"] = None
            else:
                try:
                    v = round(float(v), 1)
                except (TypeError, ValueError):
                    raise HTTPException(400, "Rating must be a number like 4.8")
                if not 1 <= v <= 5:
                    raise HTTPException(400, "Rating must be between 1 and 5")
                updates["review_rating"] = Decimal(str(v))
        if "review_count" in payload:
            v = payload["review_count"]
            try:
                updates["review_count"] = None if v in (None, "") else max(0, int(float(v)))
            except (TypeError, ValueError):
                raise HTTPException(400, "Review count must be a whole number")
        if "reviews" in payload:
            items = []
            for r in (payload["reviews"] or [])[:3]:
                text = (r.get("text") or "").strip()[:400]
                if text:
                    items.append({"text": text, "author": (r.get("author") or "").strip()[:40]})
            updates["reviews"] = json.dumps(items)
        # Picking a calendar sets the clinic timezone from that calendar,
        # unless a timezone was sent in the same request.
        if updates.get("calendar_id") and "timezone" not in payload:
            tz = await _calendar_timezone(updates["calendar_id"])
            if tz:
                updates["timezone"] = tz
        if updates.get("enabled"):
            cur = dict(await conn.fetchrow("SELECT * FROM booking_settings WHERE client_id = $1", client_id))
            cur.update(updates)
            if not cur["calendar_id"]:
                raise HTTPException(400, "Pick the clinic's calendar before turning booking on.")
            if not await conn.fetchval(
                "SELECT 1 FROM booking_event_types WHERE client_id = $1 AND active", client_id,
            ):
                raise HTTPException(400, "Add an appointment type before turning booking on.")
            if not await conn.fetchval("SELECT 1 FROM booking_hours WHERE client_id = $1", client_id):
                raise HTTPException(400, "Set the clinic's hours before turning booking on.")
        if updates:
            sets = ", ".join(f"{k} = ${i}" + ("::jsonb" if k == "reviews" else "") for i, k in enumerate(updates, start=2))
            await conn.execute(
                f"UPDATE booking_settings SET {sets}, updated_at = now() WHERE client_id = $1",
                client_id, *updates.values(),
            )
    return await get_booking(client_id)


_EVENT_INT_FIELDS = ("duration_min", "price_cents", "anchor_price_cents", "spots_per_month", "buffer_before_min",
                     "buffer_after_min", "min_notice_hours", "max_days_ahead", "daily_cap", "slot_interval_min",
                     "sort_order")
_EVENT_TEXT_FIELDS = ("name", "description", "location_text", "ask_question")


def _clean_event(payload: dict, partial: bool) -> dict:
    out: dict = {}
    for f in _EVENT_TEXT_FIELDS:
        if f in payload:
            out[f] = (payload[f] or "").strip() or None
    for f in _EVENT_INT_FIELDS:
        if f in payload:
            v = payload[f]
            if v in (None, ""):
                out[f] = None
            else:
                try:
                    out[f] = int(v)
                except (TypeError, ValueError):
                    raise HTTPException(400, f"{f} must be a whole number")
                if out[f] < 0:
                    raise HTTPException(400, f"{f} can't be negative")
    for f in ("duration_min", "min_notice_hours", "max_days_ahead", "slot_interval_min", "price_cents",
              "buffer_before_min", "buffer_after_min", "sort_order"):
        if f in out and out[f] is None:
            raise HTTPException(400, f"{f} is required")
    if out.get("duration_min") == 0 or out.get("slot_interval_min") == 0:
        raise HTTPException(400, "Length and slot spacing must be more than 0 minutes")
    if out.get("price_cents") and out["price_cents"] < 100:
        raise HTTPException(400, "A paid appointment must cost at least $1")
    if "location_type" in payload:
        if payload["location_type"] not in _LOCATION_TYPES:
            raise HTTPException(400, "location_type must be in_person, google_meet or phone")
        out["location_type"] = payload["location_type"]
    if "active" in payload:
        out["active"] = bool(payload["active"])
    if "slug" in payload:
        out["slug"] = _slugify(payload["slug"])
    if not partial and not out.get("name"):
        raise HTTPException(400, "Give the appointment type a name")
    if "name" in out and not out["name"]:
        raise HTTPException(400, "Give the appointment type a name")
    return out


@admin_router.post("/clients/{client_id}/booking/event-types")
async def create_event_type(client_id: int, payload: dict):
    data = _clean_event(payload, partial=False)
    data.setdefault("slug", _slugify(data["name"]))
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _ensure_settings(conn, client_id)
        cols = ["client_id", *data.keys()]
        try:
            row = await conn.fetchrow(
                f"INSERT INTO booking_event_types ({', '.join(cols)}) "
                f"VALUES ({', '.join(f'${i}' for i in range(1, len(cols) + 1))}) RETURNING *",
                client_id, *data.values(),
            )
        except Exception as e:
            if "unique" in str(e).lower():
                raise HTTPException(400, "An appointment type with that link name already exists")
            raise
    return _jsonable(dict(row))


@admin_router.put("/clients/{client_id}/booking/event-types/{event_id}")
async def update_event_type(client_id: int, event_id: int, payload: dict):
    data = _clean_event(payload, partial=True)
    if not data:
        raise HTTPException(400, "nothing to update")
    pool = await get_pool()
    async with pool.acquire() as conn:
        sets = ", ".join(f"{k} = ${i}" for i, k in enumerate(data, start=3))
        row = await conn.fetchrow(
            f"UPDATE booking_event_types SET {sets} WHERE id = $1 AND client_id = $2 RETURNING *",
            event_id, client_id, *data.values(),
        )
    if not row:
        raise HTTPException(404, "appointment type not found")
    return _jsonable(dict(row))


@admin_router.delete("/clients/{client_id}/booking/event-types/{event_id}")
async def delete_event_type(client_id: int, event_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        used = await conn.fetchval("SELECT 1 FROM bookings WHERE event_type_id = $1 LIMIT 1", event_id)
        if used:
            # Keep history intact: bookings reference it. Just hide it.
            await conn.execute(
                "UPDATE booking_event_types SET active = false WHERE id = $1 AND client_id = $2", event_id, client_id,
            )
            return {"ok": True, "deactivated": True}
        await conn.execute("DELETE FROM booking_event_types WHERE id = $1 AND client_id = $2", event_id, client_id)
    return {"ok": True}


def _parse_time(v: str | None) -> time | None:
    if not v:
        return None
    try:
        return time.fromisoformat(v[:5])
    except ValueError:
        raise HTTPException(400, f"Bad time: {v} (use HH:MM)")


@admin_router.put("/clients/{client_id}/booking/hours")
async def save_hours(client_id: int, payload: dict):
    rows = []
    for h in payload.get("hours") or []:
        wd = int(h.get("weekday", -1))
        s, e = _parse_time(h.get("start_time")), _parse_time(h.get("end_time"))
        if wd not in range(7) or not s or not e or e <= s:
            raise HTTPException(400, "Each block needs a weekday and an end time after its start time")
        rows.append((wd, s, e))
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _ensure_settings(conn, client_id)
        async with conn.transaction():
            await conn.execute("DELETE FROM booking_hours WHERE client_id = $1", client_id)
            for wd, s, e in rows:
                await conn.execute(
                    "INSERT INTO booking_hours (client_id, weekday, start_time, end_time) VALUES ($1,$2,$3,$4)",
                    client_id, wd, s, e,
                )
    return await get_booking(client_id)


@admin_router.put("/clients/{client_id}/booking/overrides")
async def save_overrides(client_id: int, payload: dict):
    rows = []
    for o in payload.get("overrides") or []:
        try:
            d = date.fromisoformat(o.get("date") or "")
        except ValueError:
            raise HTTPException(400, "Each override needs a date (YYYY-MM-DD)")
        closed = bool(o.get("closed"))
        s, e = (None, None) if closed else (_parse_time(o.get("start_time")), _parse_time(o.get("end_time")))
        if not closed and (not s or not e or e <= s):
            raise HTTPException(400, f"{d}: set hours, or mark it closed")
        rows.append((d, closed, s, e))
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _ensure_settings(conn, client_id)
        async with conn.transaction():
            await conn.execute(
                "DELETE FROM booking_date_overrides WHERE client_id = $1 AND date >= current_date - 1", client_id,
            )
            for d, closed, s, e in rows:
                await conn.execute(
                    "INSERT INTO booking_date_overrides (client_id, date, closed, start_time, end_time) "
                    "VALUES ($1,$2,$3,$4,$5)",
                    client_id, d, closed, s, e,
                )
    return await get_booking(client_id)


@admin_router.post("/clients/{client_id}/booking/reviews/fetch")
async def fetch_reviews(client_id: int, payload: dict | None = None):
    try:
        found = await bc.fetch_google_reviews(client_id, (payload or {}).get("query") or None)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"found": found, **(await get_booking(client_id))}


@admin_router.post("/clients/{client_id}/booking/page-autofill")
async def page_autofill(client_id: int, payload: dict | None = None):
    """Re-pull Page details from the portal, website and funnel now.
    overwrite=true replaces what's there; otherwise fills only empty fields."""
    import booking_autofill
    try:
        result = await booking_autofill.apply_page_details(client_id, overwrite=bool((payload or {}).get("overwrite")))
    except Exception as e:
        raise HTTPException(502, f"Couldn't pull page details: {e}")
    return {"result": result, **(await get_booking(client_id))}


@admin_router.post("/clients/{client_id}/booking/page-autofill/preview")
async def page_autofill_preview(client_id: int):
    """Same extraction, nothing saved (for checking what it would pull)."""
    import booking_autofill
    try:
        return await booking_autofill.propose_page_details(client_id)
    except Exception as e:
        raise HTTPException(502, f"Couldn't pull page details: {e}")


@admin_router.post("/clients/{client_id}/booking/autofill/preview")
async def autofill_preview(client_id: int):
    """Draft hours / appointment type / timezone from the client's portal
    info (booking_autofill.py). Saves nothing."""
    import booking_autofill
    try:
        return await booking_autofill.propose(client_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        print(f"[booking] autofill preview failed for client {client_id}: {e}")
        raise HTTPException(502, f"Couldn't draft the setup: {e}")


@admin_router.post("/clients/{client_id}/booking/autofill/apply")
async def autofill_apply(client_id: int, payload: dict):
    """Saves the parts of a reviewed proposal Dylan ticked. payload:
    {timezone?, hours?: [{weekday,start,end}], event_type?: {...}, event_type_id?}
    event_type_id updates that appointment type; otherwise a new one is made."""
    if payload.get("timezone"):
        await save_booking_settings(client_id, {"timezone": payload["timezone"]})
    if payload.get("hours") is not None:
        await save_hours(client_id, {"hours": [
            {"weekday": h.get("weekday"), "start_time": h.get("start"), "end_time": h.get("end")}
            for h in payload["hours"]
        ]})
    ev = payload.get("event_type")
    if ev:
        fields = {k: ev.get(k) for k in ("name", "duration_min", "location_type", "location_text", "price_cents",
                                         "anchor_price_cents", "spots_per_month", "ask_question", "description")
                  if k in ev}
        if payload.get("event_type_id"):
            await update_event_type(client_id, int(payload["event_type_id"]), fields)
        else:
            await create_event_type(client_id, fields)
    return await get_booking(client_id)


@admin_router.get("/clients/{client_id}/booking/slots")
async def preview_slots(client_id: int, event_type_id: int, days: int = 14):
    try:
        return await be.get_slots(client_id, event_type_id, days=min(max(days, 1), 60), use_cache=False)
    except be.BookingError as e:
        raise HTTPException(400, str(e))


@admin_router.get("/clients/{client_id}/booking/bookings")
async def list_bookings(client_id: int, limit: int = 50):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT b.*, e.name AS event_name FROM bookings b
               JOIN booking_event_types e ON e.id = b.event_type_id
               WHERE b.client_id = $1 AND b.status <> 'expired'
               ORDER BY b.created_at DESC LIMIT $2""",
            client_id, min(max(limit, 1), 200),
        )
    out = []
    for r in rows:
        d = _jsonable(dict(r))
        d["manage_url"] = be.manage_url(r["manage_token"])
        d.pop("manage_token", None)
        out.append(d)
    return out


@admin_router.post("/clients/{client_id}/booking/bookings/{booking_id}/cancel")
async def admin_cancel_booking(client_id: int, booking_id: int, payload: dict | None = None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        ok = await conn.fetchval("SELECT 1 FROM bookings WHERE id = $1 AND client_id = $2", booking_id, client_id)
    if not ok:
        raise HTTPException(404, "booking not found")
    try:
        return await be.cancel_booking(booking_id, by_patient=False, reason=(payload or {}).get("reason"))
    except be.BookingError as e:
        raise HTTPException(400, str(e))


@admin_router.post("/clients/{client_id}/booking/stripe/connect")
async def stripe_connect(client_id: int, request: Request):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _ensure_settings(conn, client_id)
    return_url = f"{be.public_base()}/booking-stripe-done"
    try:
        return {"url": await be.stripe_onboarding_link(client_id, return_url)}
    except be.BookingError as e:
        raise HTTPException(400, str(e))


@admin_router.post("/clients/{client_id}/booking/stripe/disconnect")
async def stripe_disconnect(client_id: int):
    """Unlink the clinic's Stripe account (it stays in Stripe; live Standard
    accounts can't be deleted). Their next Connect click starts fresh."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        acct = await conn.fetchval("SELECT stripe_account_id FROM booking_settings WHERE client_id = $1", client_id)
    if acct:
        await be._forget_stripe_account(client_id, acct)
    return {"disconnected": acct}


@admin_router.post("/clients/{client_id}/booking/stripe/refresh")
async def stripe_refresh(client_id: int):
    try:
        return await be.stripe_refresh_status(client_id)
    except be.BookingError as e:
        raise HTTPException(400, str(e))


# ── Public ───────────────────────────────────────────────────────────────────

async def _resolve(request: Request, key: str) -> dict:
    via_lp = request.url.path.startswith("/lp/")
    ctx = await be.resolve_public(key, via_lp)
    if not ctx:
        raise HTTPException(404, "Booking isn't open yet")
    return ctx


@router.get("/book/{key}", include_in_schema=False)
async def public_booking_page(key: str, request: Request):
    ctx = await be.resolve_public(key, False)
    if not ctx:
        # A real link that just isn't switched on yet gets a friendly page,
        # not a bare JSON 404.
        pool = await get_pool()
        async with pool.acquire() as conn:
            clinic = await conn.fetchval(
                "SELECT c.name FROM booking_settings s JOIN clients c ON c.id = s.client_id WHERE s.booking_slug = $1", key,
            )
        if clinic is None:
            raise HTTPException(404, "Booking page not found")
        return HTMLResponse(_not_open_page(clinic), status_code=404)
    return HTMLResponse(render_page("book", ctx["client_name"], ctx["settings"]["accent_color"]))


def _not_open_page(clinic: str) -> str:
    import html as _html
    name = _html.escape(clinic or "")
    return (
        "<!doctype html><html lang=en><head><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'><meta name=robots content=noindex>"
        f"<title>Book with {name}</title></head>"
        "<body style='margin:0;background:#f6f8fb;color:#1d2433;font:15px/1.6 -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif'>"
        "<div style='max-width:520px;margin:0 auto;padding:64px 20px'>"
        f"<div style='font-size:13px;font-weight:600;color:#5b6478'>{name}</div>"
        "<h1 style='font-size:24px;margin:6px 0 10px'>Online booking isn't open yet</h1>"
        "<p style='color:#5b6478'>Please check back soon, or call the clinic to book your visit.</p>"
        "</div></body></html>"
    )


@router.get("/book/{key}/api/info", include_in_schema=False)
@router.get("/lp/{key}/book/api/info", include_in_schema=False)
async def public_info(key: str, request: Request):
    ctx = await _resolve(request, key)
    lp_slug = key if request.url.path.startswith("/lp/") else None
    return {"clinic": ctx["client_name"], "timezone": ctx["timezone"],
            "event_types": await be.public_event_types(ctx["settings"]["client_id"]),
            "profile": await bc.page_profile(ctx["settings"]["client_id"], ctx["settings"], lp_slug)}


@router.post("/book/{key}/api/event", include_in_schema=False)
@router.post("/lp/{key}/book/api/event", include_in_schema=False)
async def public_event(key: str, request: Request, payload: dict):
    ctx = await _resolve(request, key)
    await bc.log_step(ctx["settings"]["client_id"], payload.get("session"), payload.get("step") or "",
                      payload.get("event_type_id"), payload.get("utm_source"), payload.get("utm_content"))
    return {"ok": True}


@router.post("/book/{key}/api/partial", include_in_schema=False)
@router.post("/lp/{key}/book/api/partial", include_in_schema=False)
async def public_partial(key: str, request: Request, payload: dict):
    """Two-step capture: name + mobile saved as soon as they're typed."""
    ctx = await _resolve(request, key)
    await bc.save_partial(ctx["settings"]["client_id"], payload.get("session") or "", payload.get("name"),
                          payload.get("phone") or "", payload.get("event_type_id"), payload.get("start"),
                          payload.get("utm_source"), payload.get("utm_content"),
                          payload.get("sms_consent") is True)
    return {"ok": True}


@router.get("/book/{key}/api/resume", include_in_schema=False)
@router.get("/lp/{key}/book/api/resume", include_in_schema=False)
async def public_resume(key: str, request: Request, r: str):
    ctx = await _resolve(request, key)
    info = await bc.resume_info(ctx["settings"]["client_id"], r)
    if not info:
        raise HTTPException(404, "Link expired")
    return info


@router.get("/book/{key}/api/slots", include_in_schema=False)
@router.get("/lp/{key}/book/api/slots", include_in_schema=False)
async def public_slots(key: str, request: Request, event_type_id: int, start: str | None = None, days: int = 14):
    ctx = await _resolve(request, key)
    try:
        from_day = date.fromisoformat(start) if start else None
    except ValueError:
        from_day = None
    try:
        return await be.get_slots(ctx["settings"]["client_id"], event_type_id, from_day=from_day,
                                  days=min(max(days, 1), 31))
    except be.BookingError as e:
        raise HTTPException(400, str(e))


@router.post("/book/{key}/api/reserve", include_in_schema=False)
@router.post("/lp/{key}/book/api/reserve", include_in_schema=False)
async def public_reserve(key: str, request: Request, payload: dict):
    ctx = await _resolve(request, key)
    # Where Stripe sends the patient back: the same page they booked on.
    # On a funnel (/lp/...) that's the clinic's own domain when it came
    # through the Vercel proxy; always https.
    base_path = request.url.path.split("/api/reserve")[0]
    fwd_host = (request.headers.get("x-forwarded-host") or "").split(",")[0].strip()
    page_base = (f"https://{fwd_host}{base_path}" if fwd_host and base_path.startswith("/lp/")
                 else f"{be.public_base()}{base_path}")
    try:
        return await be.reserve(
            ctx["settings"]["client_id"], int(payload.get("event_type_id") or 0), payload.get("start") or "",
            payload.get("name"), payload.get("phone"), payload.get("email"), payload.get("answer"),
            payload.get("utm_source"), payload.get("utm_content"), page_base, payload.get("session"),
            sms_consent=payload.get("sms_consent") is True,
        )
    except be.BookingError as e:
        raise HTTPException(409, str(e))


@router.get("/book/{key}/return", include_in_schema=False)
@router.get("/lp/{key}/book/return", include_in_schema=False)
async def public_payment_return(key: str, b: str, session_id: str):
    try:
        await be.confirm_from_return(b, session_id)
    except Exception as e:
        print(f"[booking] return confirm failed for {b}: {e}")  # webhook will still confirm
    return RedirectResponse(be.manage_url(b) + "?paid=1", status_code=302)


@router.post("/book/{key}/api/release", include_in_schema=False)
@router.post("/lp/{key}/book/api/release", include_in_schema=False)
async def public_release(key: str, payload: dict):
    await be.release_hold(payload.get("token") or "")
    return {"ok": True}


def _manage_payload(ctx: dict) -> dict:
    b, ev = ctx["booking"], ctx["event"]
    tz = ZoneInfo(ctx["timezone"])
    loc = ev["location_text"] if ev["location_type"] == "in_person" else (
        b["meet_link"] or "Video call" if ev["location_type"] == "google_meet" else "Phone call")
    return {
        "clinic": ctx["clinic"], "timezone": ctx["timezone"], "status": b["status"],
        "event": be._public_event(ev), "name": b["name"],
        "start": b["start_at"].astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "end": b["end_at"].astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "meet_link": b["meet_link"], "paid": bool(b["paid_at"]), "refunded": bool(b["refunded_at"]),
        "cancel_reason": b["cancel_reason"] if b["status"] == "cancelled" else None,
        "can_change": b["status"] == "confirmed" and b["start_at"] > datetime.now(timezone.utc),
        "refund_policy": ctx["settings"]["refund_policy"] if b["paid_at"] else None,
        "add_to_calendar": be.google_calendar_add_link(
            f"{ev['name']} with {ctx['clinic']}", b["start_at"], b["end_at"],
            f"Manage your booking: {be.manage_url(b['manage_token'])}", loc or "",
        ),
        "event_type_id": ev["id"],
        "provider_name": ctx["settings"].get("provider_name"),
        "provider_title": ctx["settings"].get("provider_title"),
        "photo_url": ctx["settings"].get("photo_url"),
        "what_to_expect": [x.strip(" -\u2022\t") for x in (ctx["settings"].get("what_to_expect") or "").splitlines() if x.strip(" -\u2022\t")][:4],
        "map_url": ("https://www.google.com/maps/search/?api=1&query=" + quote(ev["location_text"]))
                   if ev["location_type"] == "in_person" and ev.get("location_text") else None,
    }


@router.get("/booking/{token}", include_in_schema=False)
async def manage_page(token: str):
    ctx = await be.get_by_token(token)
    if not ctx:
        raise HTTPException(404, "Booking not found")
    return HTMLResponse(render_page("manage", ctx["clinic"], ctx["settings"]["accent_color"]))


@router.get("/booking/{token}/api/info", include_in_schema=False)
async def manage_info(token: str):
    ctx = await be.get_by_token(token)
    if not ctx:
        raise HTTPException(404, "Booking not found")
    return _manage_payload(ctx)


@router.get("/booking/{token}/api/slots", include_in_schema=False)
async def manage_slots(token: str, start: str | None = None, days: int = 14):
    ctx = await be.get_by_token(token)
    if not ctx:
        raise HTTPException(404, "Booking not found")
    try:
        from_day = date.fromisoformat(start) if start else None
    except ValueError:
        from_day = None
    try:
        return await be.get_slots(ctx["booking"]["client_id"], ctx["event"]["id"], from_day=from_day,
                                  days=min(max(days, 1), 31), exclude_booking_id=ctx["booking"]["id"])
    except be.BookingError as e:
        raise HTTPException(400, str(e))


@router.post("/booking/{token}/api/reschedule", include_in_schema=False)
async def manage_reschedule(token: str, payload: dict):
    ctx = await be.get_by_token(token)
    if not ctx:
        raise HTTPException(404, "Booking not found")
    try:
        await be.reschedule_booking(ctx["booking"]["id"], payload.get("start") or "")
    except be.BookingError as e:
        raise HTTPException(409, str(e))
    return _manage_payload(await be.get_by_token(token))


@router.post("/booking/{token}/api/cancel", include_in_schema=False)
async def manage_cancel(token: str, payload: dict | None = None):
    ctx = await be.get_by_token(token)
    if not ctx:
        raise HTTPException(404, "Booking not found")
    if ctx["booking"]["start_at"] <= datetime.now(timezone.utc):
        raise HTTPException(409, "This appointment has already started.")
    try:
        await be.cancel_booking(ctx["booking"]["id"], by_patient=True, reason=(payload or {}).get("reason"))
    except be.BookingError as e:
        raise HTTPException(409, str(e))
    return _manage_payload(await be.get_by_token(token))


@router.get("/book-asset/{client_id}/{upload_id}", include_in_schema=False)
async def booking_asset(client_id: int, upload_id: int):
    """A client-portal upload shown on that client's booking page. Only the
    upload actually chosen as the page's photo or logo is served."""
    path = f"/book-asset/{client_id}/{upload_id}"
    pool = await get_pool()
    async with pool.acquire() as conn:
        key = await conn.fetchval(
            """SELECT u.r2_key FROM client_uploads u JOIN booking_settings s ON s.client_id = u.client_id
               WHERE u.id = $2 AND u.client_id = $1 AND (s.photo_url = $3 OR s.logo_url = $3)""",
            client_id, upload_id, path,
        )
    if not key:
        raise HTTPException(404, "Not found")
    import r2_storage
    return RedirectResponse(r2_storage.presign_get(key), status_code=302)


@router.get("/booking-stripe-done", include_in_schema=False)
async def stripe_done():
    return HTMLResponse(
        "<!doctype html><meta name=viewport content='width=device-width,initial-scale=1'>"
        "<body style='font-family:system-ui;max-width:520px;margin:80px auto;padding:0 20px;color:#1d2433'>"
        "<h2>Thanks, you're all set.</h2><p>Your Stripe account is connected to your booking page. "
        "You can close this tab. If Stripe asked for anything you skipped, it will remind you by email.</p>"
    )


@router.post("/webhooks/stripe/booking", include_in_schema=False)
async def stripe_webhook(request: Request):
    secret = (os.environ.get("STRIPE_CONNECT_WEBHOOK_SECRET") or "").strip()  # stray whitespace broke every signature check
    body = await request.body()
    if not secret or not be.verify_stripe_signature(body, request.headers.get("stripe-signature", ""), secret):
        return JSONResponse({"error": "bad signature"}, status_code=400)
    try:
        await be.handle_stripe_event(json.loads(body))
    except Exception as e:
        print(f"[booking] stripe webhook handling failed: {e}")
        return JSONResponse({"error": "handler failed"}, status_code=500)  # Stripe retries
    return {"ok": True}
