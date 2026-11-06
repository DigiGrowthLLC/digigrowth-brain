"""DigiGrowth Booking: the conversion layer on top of booking_engine.py
(research + plan: "Booking Page Conversion Plan" artifact, 2026-11-06).

- log_step(): funnel tracking per page visit (view, time, details, submit,
  booked) for the Booking Links funnel view.
- save_partial()/link_partial(): two-step capture. Name + mobile are saved
  the moment the patient types them, before they finish.
- send_due_abandon_followups(): scheduler job. A partial that hasn't turned
  into a booking 10 minutes later gets one text from the clinic's number
  with a resume link (slot pre-picked if still free). Replies go to the
  clinic's AI text agent like any other lead text (response_ai.py).
- fetch_google_reviews(): Google rating, review count and top reviews via
  Places API (New), when PLACES_API_KEY is valid. Admins can also type them.
- page_profile(): the trust content the public page shows.
- funnel_stats(): step counts for the dashboard.
- ai_check_availability()/ai_book(): the client AI text agent books into
  DigiGrowth Booking when it's on (response_ai.py calls these).

No fake urgency anywhere: "times left this week" is counted from the real
calendar on the page, holds are real, reviews are real or not shown.
"""
from __future__ import annotations

import json
import os
from decimal import Decimal
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import httpx

from db import get_pool

STEPS = ("view", "time", "details", "submit", "booked")
ABANDON_DELAY_MINUTES = 10
ABANDON_MAX_AGE_HOURS = 20       # don't text about a visit older than this
MIN_REVIEW_RATING = 4.0
MIN_REVIEW_COUNT = 5


def _digits(phone: str | None) -> str:
    return "".join(c for c in (phone or "") if c.isdigit())[-10:]


# ── Step tracking ────────────────────────────────────────────────────────────

async def log_step(client_id: int, session_id: str | None, step: str, event_type_id: int | None = None,
                   utm_source: str | None = None, utm_content: str | None = None) -> None:
    if not session_id or step not in STEPS:
        return
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO booking_events (client_id, event_type_id, session_id, step, utm_source, utm_content) "
                "VALUES ($1,$2,$3,$4,$5,$6) ON CONFLICT (session_id, step) DO NOTHING",
                client_id, event_type_id, session_id[:64], step, (utm_source or None), (utm_content or None),
            )
    except Exception as e:
        print(f"[booking_conversion] log_step failed: {e}")


async def funnel_stats(client_id: int | None = None, days: int = 30) -> dict:
    """{client_id: {view, time, details, submit, booked}} distinct visits per step."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT client_id, step, count(DISTINCT session_id) AS n FROM booking_events
               WHERE created_at > now() - make_interval(days => $1) AND ($2::int IS NULL OR client_id = $2)
               GROUP BY client_id, step""",
            days, client_id,
        )
        recovered = await conn.fetch(
            """SELECT client_id, count(*) AS n FROM booking_partials
               WHERE followed_up_at IS NOT NULL AND created_at > now() - make_interval(days => $1)
                 AND ($2::int IS NULL OR client_id = $2)
                 AND EXISTS (SELECT 1 FROM bookings b WHERE b.client_id = booking_partials.client_id
                             AND b.status = 'confirmed' AND b.created_at > booking_partials.followed_up_at
                             AND right(regexp_replace(b.phone, '\\D', '', 'g'), 10)
                               = right(regexp_replace(booking_partials.phone, '\\D', '', 'g'), 10))
               GROUP BY client_id""",
            days, client_id,
        )
        texted = await conn.fetch(
            """SELECT client_id, count(*) AS n FROM booking_partials
               WHERE followed_up_at IS NOT NULL AND created_at > now() - make_interval(days => $1)
                 AND ($2::int IS NULL OR client_id = $2) GROUP BY client_id""",
            days, client_id,
        )
    out: dict = {}
    for r in rows:
        out.setdefault(r["client_id"], {s: 0 for s in STEPS})[r["step"]] = r["n"]
    for r in texted:
        out.setdefault(r["client_id"], {s: 0 for s in STEPS})["followups_sent"] = r["n"]
    for r in recovered:
        out.setdefault(r["client_id"], {s: 0 for s in STEPS})["recovered"] = r["n"]
    return out


# ── Two-step capture ─────────────────────────────────────────────────────────

async def save_partial(client_id: int, session_id: str, name: str | None, phone: str, event_type_id: int | None,
                       slot_start: str | None, utm_source: str | None, utm_content: str | None) -> None:
    if not session_id or len(_digits(phone)) < 10:
        return
    slot = None
    if slot_start:
        try:
            slot = datetime.fromisoformat(slot_start.replace("Z", "+00:00"))
        except ValueError:
            slot = None
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO booking_partials (client_id, event_type_id, session_id, resume_token, name, phone,
                   slot_start, utm_source, utm_content, followup_due_at)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9, now() + make_interval(mins => $10))
               ON CONFLICT (session_id) DO UPDATE SET name = EXCLUDED.name, phone = EXCLUDED.phone,
                   slot_start = COALESCE(EXCLUDED.slot_start, booking_partials.slot_start),
                   event_type_id = COALESCE(EXCLUDED.event_type_id, booking_partials.event_type_id),
                   followup_due_at = CASE WHEN booking_partials.followed_up_at IS NULL
                                          THEN EXCLUDED.followup_due_at ELSE booking_partials.followup_due_at END,
                   updated_at = now()""",
            client_id, event_type_id, session_id[:64], secrets.token_urlsafe(12), (name or "").strip()[:120] or None,
            phone.strip()[:40], slot, utm_source, utm_content, ABANDON_DELAY_MINUTES,
        )
    await log_step(client_id, session_id, "details", event_type_id, utm_source, utm_content)


async def link_partial(client_id: int, session_id: str | None, phone: str, booking_id: int) -> None:
    """A booking was made: mark this visit's partial (and any earlier
    unfinished one from the same number) as converted."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """UPDATE booking_partials SET booking_id = $3, updated_at = now()
                   WHERE client_id = $1 AND booking_id IS NULL
                     AND (session_id = $2 OR right(regexp_replace(phone, '\\D', '', 'g'), 10) = $4)""",
                client_id, session_id or "", booking_id, _digits(phone),
            )
    except Exception as e:
        print(f"[booking_conversion] link_partial failed: {e}")


async def resume_info(client_id: int, token: str) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        r = await conn.fetchrow(
            """SELECT p.name, p.phone, p.slot_start, e.slug FROM booking_partials p
               LEFT JOIN booking_event_types e ON e.id = p.event_type_id
               WHERE p.client_id = $1 AND p.resume_token = $2""",
            client_id, token,
        )
    if not r:
        return None
    return {"name": r["name"], "phone": r["phone"], "type": r["slug"],
            "slot": r["slot_start"].astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if r["slot_start"] else None}


# ── Unfinished-booking follow-up ─────────────────────────────────────────────

async def _ensure_contact(conn, client_id: int, phone: str, name: str | None, utm_source: str | None) -> str | None:
    """Same ownership rules as response_ai._get_or_create_contact, but tagged
    as a funnel/website lead (they came from the booking page)."""
    import lead_flags
    existing = await conn.fetchrow(
        "SELECT id, client_id, is_client_anchor FROM contacts "
        "WHERE right(regexp_replace(phone, '\\D', '', 'g'), 10) = $1 "
        "ORDER BY (client_id = $2) DESC, created_at ASC LIMIT 1",
        _digits(phone), client_id,
    )
    if existing:
        if existing["is_client_anchor"] or (existing["client_id"] not in (None, client_id)):
            return None
        await conn.execute(
            "UPDATE contacts SET owner = COALESCE(owner, $2), client_id = COALESCE(client_id, $3), updated_at = now() "
            "WHERE id = $1", existing["id"], name, client_id,
        )
        return existing["id"]
    source = "funnel" if utm_source == "paid_ad" else "website"
    row = await conn.fetchrow(
        "INSERT INTO contacts (id, owner, phone, status, client_id, lead_source, tags) "
        "VALUES ($1,$2,$3,'new',$4,$5,$6) RETURNING id",
        str(uuid.uuid4()), name, phone, client_id, source, lead_flags.SOURCE_TAGS[source],
    )
    return row["id"]


def _first(name: str | None) -> str:
    return (name or "").strip().split()[0].capitalize() if (name or "").strip() else "there"


async def send_due_abandon_followups() -> int:
    import booking_engine as be
    import client_sms
    import lead_flags

    pool = await get_pool()
    async with pool.acquire() as conn:
        due = await conn.fetch(
            """SELECT p.*, s.booking_slug, s.abandon_followup, s.enabled, c.name AS clinic, e.name AS event_name,
                      e.slug AS event_slug, cmc.twilio_number
               FROM booking_partials p
               JOIN booking_settings s ON s.client_id = p.client_id
               JOIN clients c ON c.id = p.client_id
               LEFT JOIN booking_event_types e ON e.id = p.event_type_id
               LEFT JOIN client_marketing_config cmc ON cmc.client_id = p.client_id
               WHERE p.booking_id IS NULL AND p.followed_up_at IS NULL AND p.followup_skipped IS NULL
                 AND p.followup_due_at < now()
               ORDER BY p.followup_due_at LIMIT 50"""
        )
    sent = 0
    for p in due:
        async def skip(reason: str):
            async with pool.acquire() as c2:
                await c2.execute("UPDATE booking_partials SET followup_skipped = $2 WHERE id = $1", p["id"], reason)

        if p["created_at"] < datetime.now(timezone.utc) - timedelta(hours=ABANDON_MAX_AGE_HOURS):
            await skip("too old")
            continue
        if not (p["enabled"] and p["abandon_followup"]):
            await skip("follow-up off")
            continue
        if not p["twilio_number"]:
            await skip("clinic has no texting number")
            continue
        async with pool.acquire() as conn:
            booked = await conn.fetchval(
                """SELECT 1 FROM bookings WHERE client_id = $1 AND created_at > $2 - interval '1 hour'
                     AND right(regexp_replace(phone, '\\D', '', 'g'), 10) = $3
                     AND (status = 'confirmed' OR (status = 'pending_payment' AND hold_expires_at > now()))""",
                p["client_id"], p["created_at"], _digits(p["phone"]),
            )
            upcoming = await conn.fetchval(
                """SELECT 1 FROM appointment_reminders ar JOIN contacts ct ON ct.id = ar.contact_id
                   WHERE ct.client_id = $1 AND ar.status = 'scheduled' AND ar.appointment_at > now()
                     AND right(regexp_replace(coalesce(ar.prospect_phone, ct.phone), '\\D', '', 'g'), 10) = $2""",
                p["client_id"], _digits(p["phone"]),
            )
            tz_name = await be.client_timezone(conn, p["client_id"],
                                               await conn.fetchrow("SELECT timezone FROM booking_settings WHERE client_id = $1", p["client_id"]))
        if booked or upcoming:
            await skip("already booked")
            continue
        if lead_flags.in_quiet_hours(tz_name, datetime.now(timezone.utc)):
            continue  # stays due; goes out after quiet hours (if still under the age limit)

        tz = ZoneInfo(tz_name)
        slot_text = ""
        if p["slot_start"] and p["slot_start"] > datetime.now(timezone.utc) + timedelta(hours=1):
            local = p["slot_start"].astimezone(tz)
            slot_text = f" for {local.strftime('%A')} at {local.strftime('%I:%M %p').lstrip('0')}"
        link = f"{be.booking_page_url(p['booking_slug'])}?{urlencode({'r': p['resume_token']})}"
        what = p["event_name"] or "your visit"
        body = (f"Hi {_first(p['name'])}, it's {p['clinic']}. Looks like you started booking {what}{slot_text} "
                f"but didn't get to finish. Want to grab it? It only takes a few seconds: {link}")
        try:
            async with pool.acquire() as conn:
                await _ensure_contact(conn, p["client_id"], p["phone"], p["name"], p["utm_source"])
            await client_sms.send_client_sms(p["client_id"], p["phone"], body, stage="booking_abandon_followup")
        except Exception as e:
            print(f"[booking_conversion] abandon text failed for partial {p['id']}: {e}")
            await skip(f"send failed: {str(e)[:120]}")
            continue
        async with pool.acquire() as conn:
            await conn.execute("UPDATE booking_partials SET followed_up_at = now() WHERE id = $1", p["id"])
        sent += 1
    return sent


# ── Reviews + page profile ───────────────────────────────────────────────────

async def fetch_google_reviews(client_id: int, query: str | None = None) -> dict:
    """Places API (New). Finds the clinic (stored place id, or a text search
    on `query` / clinic name + address) and stores rating, count and up to 3
    of its best recent reviews."""
    key = os.environ.get("PLACES_API_KEY")
    if not key:
        raise ValueError("PLACES_API_KEY isn't set on the server.")
    pool = await get_pool()
    async with pool.acquire() as conn:
        s = await conn.fetchrow("SELECT google_place_id FROM booking_settings WHERE client_id = $1", client_id)
        clinic = await conn.fetchval("SELECT name FROM clients WHERE id = $1", client_id)
        addr = await conn.fetchval(
            "SELECT location_text FROM booking_event_types WHERE client_id = $1 AND location_text IS NOT NULL "
            "ORDER BY sort_order, id LIMIT 1", client_id,
        )
    place_id = (s["google_place_id"] if s else None) if not query else None
    async with httpx.AsyncClient(timeout=20) as http:
        if not place_id:
            r = await http.post(
                "https://places.googleapis.com/v1/places:searchText",
                headers={"X-Goog-Api-Key": key, "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress"},
                json={"textQuery": query or f"{clinic} {addr or ''}".strip()},
            )
            data = r.json()
            if r.status_code >= 400:
                raise ValueError(f"Google: {(data.get('error') or {}).get('message') or r.text[:200]}")
            places = data.get("places") or []
            if not places:
                raise ValueError("Google couldn't find this clinic. Try the exact name and city.")
            place_id = places[0]["id"]
        r = await http.get(
            f"https://places.googleapis.com/v1/places/{place_id}",
            headers={"X-Goog-Api-Key": key,
                     "X-Goog-FieldMask": "id,displayName,formattedAddress,rating,userRatingCount,reviews,googleMapsUri"},
        )
        d = r.json()
        if r.status_code >= 400:
            raise ValueError(f"Google: {(d.get('error') or {}).get('message') or r.text[:200]}")
    reviews = []
    for rv in sorted(d.get("reviews") or [], key=lambda x: (-(x.get("rating") or 0), -len((x.get("text") or {}).get("text", "")))):
        text = ((rv.get("text") or {}).get("text") or "").strip()
        author = ((rv.get("authorAttribution") or {}).get("displayName") or "").strip()
        if (rv.get("rating") or 0) >= 5 and 20 <= len(text) <= 400:
            reviews.append({"text": text, "author": author.split()[0] if author else ""})
        if len(reviews) == 3:
            break
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE booking_settings SET google_place_id = $2, review_rating = $3, review_count = $4, reviews = $5::jsonb, "
            "reviews_fetched_at = now(), updated_at = now() WHERE client_id = $1",
            client_id, place_id, Decimal(str(round(d["rating"], 1))) if d.get("rating") is not None else None,
            d.get("userRatingCount"), json.dumps(reviews),
        )
    return {"place": (d.get("displayName") or {}).get("text"), "address": d.get("formattedAddress"),
            "rating": d.get("rating"), "count": d.get("userRatingCount"), "reviews": reviews}


async def page_profile(client_id: int, settings: dict, landing_slug: str | None = None) -> dict:
    """Trust content for the public page. Reviews only when they help
    (4.0+ average and 5+ reviews), per the Spiegel findings."""
    reviews = settings.get("reviews") or []
    if isinstance(reviews, str):
        reviews = json.loads(reviews)
    rating = float(settings["review_rating"]) if settings.get("review_rating") is not None else None
    count = settings.get("review_count")
    # Hide a weak rating (under 4.0, or under 5 reviews when the count is
    # known). Real testimonials still show when the count isn't published.
    rating_ok = bool(rating and rating >= MIN_REVIEW_RATING and (count is None or count >= MIN_REVIEW_COUNT))
    if not rating_ok:
        rating, count = None, None
    show_reviews = rating_ok or bool(reviews)
    photo = settings.get("photo_url")
    if not photo:
        pool = await get_pool()
        async with pool.acquire() as conn:
            slug = landing_slug or await conn.fetchval(
                "SELECT slug FROM landing_pages WHERE client_id = $1 AND hero_r2_key IS NOT NULL "
                "ORDER BY created_at DESC LIMIT 1", client_id,
            )
            if slug and await conn.fetchval("SELECT hero_r2_key IS NOT NULL FROM landing_pages WHERE slug = $1", slug):
                photo = f"/lp/{slug}/hero-image"
    refund = settings.get("refund_policy")
    return {
        "provider_name": settings.get("provider_name"),
        "provider_title": settings.get("provider_title"),
        "photo_url": photo,
        "logo_url": settings.get("logo_url"),
        "what_to_expect": [x.strip(" -•\t") for x in (settings.get("what_to_expect") or "").splitlines() if x.strip(" -•\t")][:4],
        "reviews": {"rating": rating, "count": count, "items": reviews[:3]} if show_reviews else None,
        "refund_policy": refund,
    }


# ── Client AI text agent hooks (response_ai.py) ──────────────────────────────

async def _ai_event(client_id: int) -> tuple[dict, dict] | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        s = await conn.fetchrow("SELECT * FROM booking_settings WHERE client_id = $1 AND enabled", client_id)
        if not s:
            return None
        ev = await conn.fetchrow(
            "SELECT * FROM booking_event_types WHERE client_id = $1 AND active ORDER BY sort_order, id LIMIT 1", client_id,
        )
    return (dict(s), dict(ev)) if ev else None


async def booking_enabled(client_id: int) -> bool:
    return (await _ai_event(client_id)) is not None


async def ai_check_availability(client_id: int, after_date: str | None) -> list[datetime] | None:
    """Earliest day's open times (clinic-local datetimes), or None if the
    client isn't on DigiGrowth Booking."""
    import booking_engine as be
    found = await _ai_event(client_id)
    if not found:
        return None
    _, ev = found
    from datetime import date as _date
    start = None
    if after_date:
        try:
            start = _date.fromisoformat(after_date)
        except ValueError:
            start = None
    out = await be.get_slots(client_id, ev["id"], from_day=start, days=min(ev["max_days_ahead"] + 1, 31))
    tz = ZoneInfo(out["timezone"])
    for d in out["days"]:
        if d["slots"]:
            return [datetime.fromisoformat(x.replace("Z", "+00:00")).astimezone(tz) for x in d["slots"]]
    return []


async def ai_book(client_id: int, phone: str, name: str | None, date_str: str, time_str: str) -> dict:
    """Books the AI agent's agreed slot. Free visit: books it and returns
    {"booked": True}. Paid visit: returns {"link": ...} to the page with the
    slot pre-picked, since the patient has to pay."""
    import booking_engine as be
    found = await _ai_event(client_id)
    if not found:
        raise be.BookingError("DigiGrowth Booking isn't on for this clinic.")
    s, ev = found
    pool = await get_pool()
    async with pool.acquire() as conn:
        tz_name = await be.client_timezone(conn, client_id, s)
    try:
        local = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo(tz_name))
    except ValueError:
        raise be.BookingError("Use date YYYY-MM-DD and time HH:MM (24h).")
    start_iso = local.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if ev["price_cents"] > 0:
        await be._assert_slot_open(client_id, ev, local.astimezone(timezone.utc))
        q = {"type": ev["slug"], "slot": start_iso, "phone": phone}
        if name:
            q["name"] = name
        return {"link": f"{be.booking_page_url(s['booking_slug'])}?{urlencode(q)}", "tz": tz_name}
    if not name:
        raise be.BookingError("NEED_NAME")
    await be.reserve(client_id, ev["id"], start_iso, name, phone, None, None, None, None, be.public_base())
    return {"booked": True, "tz": tz_name}
