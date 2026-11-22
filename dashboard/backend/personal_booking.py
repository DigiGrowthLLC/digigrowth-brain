"""Dylan's own booking page (2026-11-21): booking.digigrowthllc.com/discovery-call (was /strategy-call, redirected),
DigiGrowth's replacement for his Calendly links.

Separate from booking_engine.py (which is built around a clinic: client_id,
the clinic's Twilio number, Stripe, client reminders) but the same idea:
  - Hours: personal_booking_settings.hours (Eastern by default), every slot
    minus busy time on BOTH of Dylan's Google accounts: the business calendar
    (dylanrg@digigrowthllc.com) and every calendar he owns on his personal
    account (dylangroenendijk@gmail.com: school, Discount Tire shifts...).
  - Call types: personal_booking_types (Discovery Call, slug discovery-call; Onboarding
    Call, Launch Call). Only `listed` types show on the bare link; the others
    are reached with ?type=<slug> (sent to clients only).
  - A booking puts a Google Meet event on his personal primary calendar with
    the prospect as attendee (Google emails them the invite), exactly like the
    SMS setter's auto-booking (integrations.calendar_create_meet_event), so
    reminder_engine's Meet-link lookup finds it. Then
    calendly_webhooks.record_booking(client_id=None) runs the same CRM
    contact match/create, appointment row, reminders and Analytics credit a
    Calendly booking gets. calendly_event_uri = "dgme:<booking id>".
  - Prospects reschedule/cancel at .../discovery-call/manage/<token>; an OS
    cancel mirrors back via on_appointment_cancelled().
Routes: routers/personal_booking.py. Page: personal_booking_page.py.
"""
from __future__ import annotations

import asyncio
import json
import secrets
import time as _time
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from db import get_pool

SLUG = "discovery-call"
OLD_SLUGS = ("strategy-call",)  # renamed 2026-11-22; routers/personal_booking.py redirects these
LOCK_KEY = 7_301_118_201  # pg_advisory_xact_lock key for personal bookings

DEFAULT_HOURS = {str(d): [["08:00", "22:00"]] for d in range(7)}  # Mon=0 .. Sun=6
DEFAULT_TYPES = [
    # slug, name, minutes, call_type, listed, description
    ("discovery-call", "Discovery Call", 30, "discovery", True,
     "A quick call to see where your clinic is at and whether we can help you fill your schedule with new patients."),
    ("onboarding-call", "Onboarding Call", 45, "onboarding", False,
     "We walk through your setup together so your campaign can go live."),
    ("launch-call", "Launch Call", 30, "launch", False,
     "We go over your campaign before it goes live and answer your questions."),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS personal_booking_settings (
    id              INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    timezone        TEXT NOT NULL DEFAULT 'America/New_York',
    hours           JSONB NOT NULL,
    min_notice_min  INTEGER NOT NULL DEFAULT 120,
    max_days_ahead  INTEGER NOT NULL DEFAULT 30,
    slot_step_min   INTEGER NOT NULL DEFAULT 30,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS personal_booking_types (
    id            SERIAL PRIMARY KEY,
    slug          TEXT UNIQUE NOT NULL,
    name          TEXT NOT NULL,
    description   TEXT,
    duration_min  INTEGER NOT NULL DEFAULT 30,
    buffer_min    INTEGER NOT NULL DEFAULT 0,
    call_type     TEXT NOT NULL DEFAULT 'discovery',
    listed        BOOLEAN NOT NULL DEFAULT false,
    active        BOOLEAN NOT NULL DEFAULT true,
    sort_order    INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS personal_bookings (
    id              SERIAL PRIMARY KEY,
    type_id         INTEGER NOT NULL REFERENCES personal_booking_types(id),
    status          TEXT NOT NULL DEFAULT 'confirmed',
    start_at        TIMESTAMPTZ NOT NULL,
    end_at          TIMESTAMPTZ NOT NULL,
    name            TEXT NOT NULL,
    email           TEXT NOT NULL,
    phone           TEXT,
    business        TEXT,
    note            TEXT,
    timezone        TEXT,
    sms_consent     BOOLEAN NOT NULL DEFAULT false,
    utm_source      TEXT,
    utm_content     TEXT,
    excluded        BOOLEAN NOT NULL DEFAULT false,
    manage_token    TEXT UNIQUE NOT NULL,
    google_event_id TEXT,
    meet_link       TEXT,
    calendar_error  TEXT,
    appointment_id  INTEGER,
    cancelled_at    TIMESTAMPTZ,
    cancelled_by    TEXT,
    cancel_reason   TEXT,
    rescheduled_at  TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_personal_bookings_start ON personal_bookings(start_at) WHERE status = 'confirmed';
-- Booking-link analytics (2026-11-22): one row per page view ('view') and per
-- picked time ('time'), keyed by a browser visitor id; bookings carry the same
-- id so Analytics -> Booking link can work out conversion per channel.
CREATE TABLE IF NOT EXISTS personal_booking_events (
    id          BIGSERIAL PRIMARY KEY,
    visitor_id  TEXT NOT NULL,
    step        TEXT NOT NULL,
    type_slug   TEXT,
    channel     TEXT NOT NULL,
    utm_source  TEXT,
    utm_content TEXT,
    referrer    TEXT,
    excluded    BOOLEAN NOT NULL DEFAULT false,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_pb_events_created ON personal_booking_events(created_at);
CREATE INDEX IF NOT EXISTS idx_pb_events_visitor ON personal_booking_events(visitor_id);
ALTER TABLE personal_bookings ADD COLUMN IF NOT EXISTS visitor_id TEXT;
ALTER TABLE personal_bookings ADD COLUMN IF NOT EXISTS channel TEXT;
"""


class BookingError(Exception):
    """Shown to the person booking as-is."""


async def ensure_seeded(conn) -> None:
    await conn.execute(SCHEMA)
    await conn.execute(
        "INSERT INTO personal_booking_settings (id, hours) VALUES (1, $1::jsonb) ON CONFLICT (id) DO NOTHING",
        json.dumps(DEFAULT_HOURS))
    # 2026-11-22: the discovery type's slug moved strategy-call -> discovery-call (same row, same bookings).
    await conn.execute(
        """UPDATE personal_booking_types SET slug = 'discovery-call' WHERE slug = 'strategy-call'
           AND NOT EXISTS (SELECT 1 FROM personal_booking_types WHERE slug = 'discovery-call')""")
    for i, (slug, name, mins, call_type, listed, desc) in enumerate(DEFAULT_TYPES):
        await conn.execute(
            """INSERT INTO personal_booking_types (slug, name, description, duration_min, call_type, listed, sort_order)
               VALUES ($1, $2, $3, $4, $5, $6, $7) ON CONFLICT (slug) DO NOTHING""",
            slug, name, desc, mins, call_type, listed, i)


# ── URLs ─────────────────────────────────────────────────────────────────────

def page_url(type_slug: str | None = None) -> str:
    import booking_engine
    base = f"{booking_engine.BOOKING_BASE}/{SLUG}"
    return f"{base}?type={type_slug}" if type_slug and type_slug != SLUG else base


def manage_url(token: str) -> str:
    import booking_engine
    return f"{booking_engine.BOOKING_BASE}/{SLUG}/manage/{token}"


# ── Data ─────────────────────────────────────────────────────────────────────

def _hours(settings: dict) -> dict:
    h = settings["hours"]
    return json.loads(h) if isinstance(h, str) else h


async def get_settings(conn) -> dict:
    return dict(await conn.fetchrow("SELECT * FROM personal_booking_settings WHERE id = 1"))


async def public_types() -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM personal_booking_types WHERE active ORDER BY sort_order, id")
    return [{k: r[k] for k in ("id", "slug", "name", "description", "duration_min", "listed")} for r in rows]


# ── Busy time on both Google accounts ────────────────────────────────────────

_busy_cache: dict = {"at": 0.0, "range": None, "busy": []}
_BUSY_TTL = 45


def _personal_calendar_ids(svc) -> list[str]:
    ids, page = [], None
    while True:
        res = svc.calendarList().list(pageToken=page, maxResults=250).execute()
        for c in res.get("items", []):
            cid = c["id"]
            if c.get("accessRole") not in ("owner", "writer"):
                continue
            if any(x in cid for x in ("#holiday", "#contacts", "#weather")):
                continue
            ids.append(cid)
        page = res.get("nextPageToken")
        if not page:
            return ids


def _freebusy(svc, ids: list[str], start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    res = svc.freebusy().query(body={
        "timeMin": start.astimezone(timezone.utc).isoformat(),
        "timeMax": end.astimezone(timezone.utc).isoformat(),
        "items": [{"id": i} for i in ids],
    }).execute()
    out = []
    for cid, cal in (res.get("calendars") or {}).items():
        if cal.get("errors"):
            raise BookingError("Online booking is temporarily unavailable. Please try again shortly.")
        for b in cal.get("busy", []):
            out.append((datetime.fromisoformat(b["start"].replace("Z", "+00:00")),
                        datetime.fromisoformat(b["end"].replace("Z", "+00:00"))))
    return out


def _google_busy_sync(start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    from googleapiclient.discovery import build
    import integrations
    personal = build("calendar", "v3", credentials=integrations._personal_creds(), cache_discovery=False)
    business = build("calendar", "v3", credentials=integrations._business_creds(), cache_discovery=False)
    busy = _freebusy(personal, _personal_calendar_ids(personal), start, end)
    busy += _freebusy(business, ["primary"], start, end)
    return busy


async def _busy(start: datetime, end: datetime, fresh: bool = False) -> list[tuple[datetime, datetime]]:
    c = _busy_cache
    if (not fresh and c["range"] and c["range"][0] <= start and c["range"][1] >= end
            and _time.time() - c["at"] < _BUSY_TTL):
        google = c["busy"]
    else:
        try:
            google = await asyncio.to_thread(_google_busy_sync, start, end)
        except BookingError:
            raise
        except Exception as e:
            print(f"[personal-booking] calendar read failed: {e}")
            raise BookingError("Online booking is temporarily unavailable. Please try again shortly.")
        c.update(at=_time.time(), range=(start, end), busy=google)
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT start_at, end_at FROM personal_bookings WHERE status = 'confirmed' AND start_at < $2 AND end_at > $1",
            start, end)
    return google + [(r["start_at"], r["end_at"]) for r in rows]


# ── Slots ────────────────────────────────────────────────────────────────────

def _overlaps(a0, a1, b0, b1) -> bool:
    return a0 < b1 and b0 < a1


# Prospects can only book (or reschedule into) the next 5 weekdays; anything later is kept for
# Dylan and the AI setters, which book through their own paths, not this page (Dylan, 2026-11-22).
PROSPECT_MAX_WEEKDAYS = 5


def _weekdays_ahead(today: date, n: int) -> date:
    """The n-th weekday after today (Sunday + 5 -> Friday, Monday + 5 -> next Monday)."""
    day = today
    while n > 0:
        day += timedelta(days=1)
        if day.weekday() < 5:
            n -= 1
    return day


async def get_slots(type_id: int, start_day: date | None = None, days: int = 31,
                    exclude_booking_id: int | None = None, prospect: bool = True) -> list[str]:
    """Open start times (UTC ISO). prospect=False lifts the 5-weekday cap
    (the AI setters book further out than the public page offers)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        s = await get_settings(conn)
        ev = await conn.fetchrow("SELECT * FROM personal_booking_types WHERE id = $1 AND active", type_id)
        own = None
        if exclude_booking_id:
            own = await conn.fetchrow("SELECT start_at, end_at FROM personal_bookings WHERE id = $1", exclude_booking_id)
    if not ev:
        raise BookingError("This call type isn't available.")
    tz = ZoneInfo(s["timezone"])
    now = datetime.now(timezone.utc)
    earliest = now + timedelta(minutes=s["min_notice_min"])
    today = now.astimezone(tz).date()
    first = max(start_day or today, today)
    last = min(first + timedelta(days=max(1, min(days, 62)) - 1), today + timedelta(days=s["max_days_ahead"]))
    if prospect:
        last = min(last, _weekdays_ahead(today, PROSPECT_MAX_WEEKDAYS))
    if last < first:
        return []
    range_start = datetime.combine(first, datetime.min.time(), tz)
    range_end = datetime.combine(last + timedelta(days=1), datetime.min.time(), tz)
    busy = await _busy(range_start, range_end)
    if own:  # rescheduling: the booking's own time isn't "busy" for itself
        o0, o1, kept = own["start_at"], own["end_at"], []
        for b0, b1 in busy:  # Google merges touching blocks, so cut it out
            if not _overlaps(b0, b1, o0, o1):
                kept.append((b0, b1))
                continue
            if b0 < o0:
                kept.append((b0, o0))
            if b1 > o1:
                kept.append((o1, b1))
        busy = kept
    dur, pad, step = timedelta(minutes=ev["duration_min"]), timedelta(minutes=ev["buffer_min"]), timedelta(minutes=s["slot_step_min"])
    hours = _hours(s)
    out = []
    day = first
    while day <= last:
        for w0, w1 in hours.get(str(day.weekday()), []):
            t = datetime.combine(day, datetime.strptime(w0, "%H:%M").time(), tz)
            end_w = datetime.combine(day, datetime.strptime(w1, "%H:%M").time(), tz)
            while t + dur <= end_w:
                if t >= earliest and not any(_overlaps(t - pad, t + dur + pad, b0, b1) for b0, b1 in busy):
                    out.append(t.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"))
                t += step
        day += timedelta(days=1)
    return out


def _parse_start(start_iso: str) -> datetime:
    try:
        dt = datetime.fromisoformat((start_iso or "").replace("Z", "+00:00"))
    except ValueError:
        raise BookingError("That time isn't valid. Please pick another.")
    if dt.tzinfo is None:
        raise BookingError("That time isn't valid. Please pick another.")
    return dt.astimezone(timezone.utc)


async def _assert_open(type_id: int, start: datetime, exclude_booking_id: int | None = None,
                       prospect: bool = True) -> None:
    iso = start.isoformat().replace("+00:00", "Z")
    _busy_cache["at"] = 0.0  # re-read the calendars right before committing
    slots = await get_slots(type_id, start.astimezone(ZoneInfo("America/New_York")).date() - timedelta(days=1), 3,
                            exclude_booking_id, prospect)
    if iso not in slots:
        raise BookingError("Sorry, that time was just taken. Please pick another.")


# ── Booking ──────────────────────────────────────────────────────────────────

def _valid_tz(name: str | None, fallback: str) -> str:
    try:
        ZoneInfo(name or "")
        return name
    except Exception:
        return fallback


async def reserve(type_id: int, start_iso: str, name: str, email: str, phone: str, business: str | None,
                  note: str | None, tz_name: str | None, sms_consent: bool, utm_source: str | None,
                  utm_content: str | None, excluded: bool, prospect: bool = True, visitor_id: str | None = None,
                  referrer: str | None = None) -> dict:
    name, email, phone = (name or "").strip(), (email or "").strip().lower(), (phone or "").strip()
    if not name or len(name) > 120:
        raise BookingError("Please enter your name.")
    if "@" not in email or "." not in email.split("@")[-1] or len(email) > 200:
        raise BookingError("Please enter a valid email. Your video link goes there.")
    if prospect and len("".join(c for c in phone if c.isdigit())) < 10:
        raise BookingError("Please enter a valid mobile number.")
    start = _parse_start(start_iso)
    pool = await get_pool()
    async with pool.acquire() as conn:
        ev = await conn.fetchrow("SELECT * FROM personal_booking_types WHERE id = $1 AND active", type_id)
        s = await get_settings(conn)
    if not ev:
        raise BookingError("This call type isn't available.")
    ev = dict(ev)
    tz_name = _valid_tz(tz_name, s["timezone"])
    await _assert_open(type_id, start, prospect=prospect)
    end = start + timedelta(minutes=ev["duration_min"])
    token = secrets.token_urlsafe(18)
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("SELECT pg_advisory_xact_lock($1)", LOCK_KEY)
            if await conn.fetchval(
                    "SELECT 1 FROM personal_bookings WHERE status = 'confirmed' AND start_at < $2 AND end_at > $1",
                    start, end):
                raise BookingError("Sorry, that time was just taken. Please pick another.")
            bid = await conn.fetchval(
                """INSERT INTO personal_bookings (type_id, start_at, end_at, name, email, phone, business, note,
                       timezone, sms_consent, utm_source, utm_content, excluded, manage_token, visitor_id, channel)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16) RETURNING id""",
                type_id, start, end, name, email, phone or None, (business or "").strip()[:160] or None,
                (note or "").strip()[:1000] or None, tz_name, sms_consent, utm_source, utm_content, excluded, token,
                (visitor_id or "")[:64] or None,
                "ai_setter" if utm_source == "ai_setter" else channel_for(utm_source, referrer))
    _busy_cache["at"] = 0.0
    await _finalize(bid)
    return {"status": "confirmed", "manage_url": manage_url(token)}


# ── Booking-link analytics ───────────────────────────────────────────────────
# Which channel a visit came from: the link's own tag first (?utm_source= on
# the website, ?via= on links the OS sends: see integrations.booking_link),
# then the referring site. Website links are rel="noreferrer", so they rely on
# their tag.

CHANNELS = {  # key -> label, in display order
    "email": "Email", "sms": "Text (SMS)", "website": "Website", "social": "Social media",
    "video": "Video pages", "pages": "Landing pages", "other": "Other links", "direct": "Direct / untagged",
}
ALWAYS_SHOWN = ("email", "sms", "website", "social")
_SOCIAL_TAGS = {"social", "instagram", "ig", "facebook", "fb", "meta", "linkedin", "li", "tiktok", "youtube", "yt",
                "twitter", "x", "threads", "dm", "bio"}
_SOCIAL_HOSTS = ("instagram.com", "facebook.com", "fb.com", "fb.me", "messenger.com", "linkedin.com", "lnkd.in",
                 "tiktok.com", "youtube.com", "youtu.be", "t.co", "twitter.com", "x.com", "threads.net")
_MAIL_HOSTS = ("mail.google.com", "outlook.live.com", "outlook.office.com", "outlook.office365.com", "mail.yahoo.com",
               "mail.aol.com", "icloud.com")


def channel_for(utm_source: str | None, referrer: str | None) -> str:
    from urllib.parse import urlparse
    tag = (utm_source or "").strip().lower()
    if tag:
        if tag.startswith("email") or tag in ("cold-email", "newsletter", "gmail"):
            return "email"
        if tag in ("sms", "text", "txt"):
            return "sms"
        if tag in ("website", "site", "web", "contact-vsl"):
            return "website"
        if tag in _SOCIAL_TAGS:
            return "social"
        if tag in ("video", "loom", "vsl", "watch"):
            return "video"
        return "other"
    try:
        host = (urlparse(referrer or "").hostname or "").lower()
    except ValueError:
        host = ""
    host = host[4:] if host.startswith("www.") else host
    if not host or host == "booking.digigrowthllc.com":
        return "direct"

    def match(hosts):
        return any(host == h or host.endswith("." + h) for h in hosts)

    if host.startswith("loom.") and host.endswith("digigrowthllc.com"):
        return "video"
    if host == "pages.digigrowthllc.com":
        return "pages"
    if host == "digigrowthllc.com":
        return "website"
    if match(_MAIL_HOSTS):
        return "email"
    if match(_SOCIAL_HOSTS):
        return "social"
    return "other"


async def log_event(visitor_id: str, step: str, type_slug: str | None, utm_source: str | None,
                    utm_content: str | None, referrer: str | None, excluded: bool) -> None:
    if step not in ("view", "time") or not visitor_id:
        return
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO personal_booking_events (visitor_id, step, type_slug, channel, utm_source, utm_content,
                       referrer, excluded) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)""",
                visitor_id[:64], step, (type_slug or "")[:60] or None, channel_for(utm_source, referrer),
                (utm_source or "")[:80] or None, (utm_content or "")[:80] or None, (referrer or "")[:500] or None,
                excluded)
    except Exception as e:
        print(f"[personal-booking] event log failed: {e}")


async def link_analytics(since: datetime | None, until: datetime | None) -> dict:
    """Discovery Call link only (the Onboarding/Launch links go to clients, not
    prospects). Each visitor counts once, under the channel of their first
    visit in the window. Dylan's visits are dropped: any view from an excluded
    IP, every visit from a browser that ever had one (his phone on a carrier
    IP), and bookings on the test number."""
    import tracking_exclusion
    since = since or datetime(2000, 1, 1, tzinfo=timezone.utc)
    until = until or datetime.now(timezone.utc) + timedelta(minutes=1)
    test = [f"%{d}" for d in tracking_exclusion.TEST_PHONE_DIGITS]
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """WITH dylan AS (SELECT DISTINCT visitor_id FROM personal_booking_events WHERE excluded),
               ev AS (SELECT * FROM personal_booking_events
                      WHERE created_at >= $1 AND created_at < $2 AND NOT excluded
                        AND COALESCE(type_slug, 'discovery-call') = 'discovery-call'
                        AND visitor_id NOT IN (SELECT visitor_id FROM dylan)),
               v AS (SELECT DISTINCT ON (visitor_id) visitor_id, channel FROM ev WHERE step = 'view'
                     ORDER BY visitor_id, created_at),
               t AS (SELECT DISTINCT visitor_id FROM ev WHERE step = 'time'),
               b AS (SELECT DISTINCT b.visitor_id FROM personal_bookings b
                     JOIN personal_booking_types ty ON ty.id = b.type_id
                     WHERE b.visitor_id IS NOT NULL AND NOT b.excluded AND ty.call_type = 'discovery'
                       AND b.created_at >= $1 AND b.created_at < $2
                       AND NOT (regexp_replace(COALESCE(b.phone, ''), '[^0-9]', '', 'g') LIKE ANY($3::text[])))
               SELECT v.channel, count(*) AS visitors, count(t.visitor_id) AS picked, count(b.visitor_id) AS booked
               FROM v LEFT JOIN t USING (visitor_id) LEFT JOIN b USING (visitor_id)
               GROUP BY v.channel""", since, until, test)
        ai_booked = await conn.fetchval(
            """SELECT count(*) FROM personal_bookings
               WHERE utm_source = 'ai_setter' AND created_at >= $1 AND created_at < $2""", since, until)
        first = await conn.fetchval("SELECT min(created_at) FROM personal_booking_events")
    by = {r["channel"]: dict(r) for r in rows}

    def rate(n, d):
        return round(n * 100 / d, 1) if d else None

    channels = []
    for key, label in CHANNELS.items():
        r = by.get(key) or {"visitors": 0, "picked": 0, "booked": 0}
        if not r["visitors"] and key not in ALWAYS_SHOWN:
            continue
        channels.append({"key": key, "label": label, "visitors": r["visitors"], "picked": r["picked"],
                         "booked": r["booked"], "pick_rate": rate(r["picked"], r["visitors"]),
                         "conversion_rate": rate(r["booked"], r["visitors"])})
    tot = {k: sum(r[k] for r in by.values()) for k in ("visitors", "picked", "booked")}
    return {"total": {**tot, "pick_rate": rate(tot["picked"], tot["visitors"]),
                      "conversion_rate": rate(tot["booked"], tot["visitors"])},
            "channels": channels, "ai_booked": ai_booked or 0,
            "tracking_since": first.isoformat() if first else None}


# ── AI setters (SMS + email) ─────────────────────────────────────────────────
# Since 2026-11-22 the setters read openings from and book into this page
# instead of Dylan's Calendly, so every discovery call lands in one place.

async def discovery_type_id() -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        tid = await conn.fetchval("SELECT id FROM personal_booking_types WHERE slug = $1 AND active", SLUG)
    if not tid:
        raise BookingError("The Discovery Call type is turned off.")
    return tid


async def ai_open_slots(days: int) -> list[datetime]:
    """Discovery Call openings for the next `days` days (no 5-weekday cap)."""
    tid = await discovery_type_id()
    slots = await get_slots(tid, None, days, prospect=False)
    return [_parse_start(x) for x in slots]


async def ai_slot_open(start: datetime) -> bool:
    try:
        await _assert_open(await discovery_type_id(), start.astimezone(timezone.utc), prospect=False)
        return True
    except BookingError:
        return False


async def ai_book(start: datetime, name: str, email: str, phone: str | None, business: str | None,
                  note: str, tz_name: str) -> dict:
    """Books a Discovery Call for a setter-booked prospect: same Meet invite,
    appointment row (adopts the one the setter made first) and reminders as
    the public page. Raises BookingError if the slot is gone."""
    return await reserve(
        await discovery_type_id(), start.astimezone(timezone.utc).isoformat(), name, email, phone or "", business,
        note, tz_name, bool(phone), "ai_setter", None, False, prospect=False,
    )


async def _finalize(booking_id: int) -> None:
    """Calendar event + invite, then the same pipeline a Calendly booking runs.
    Each step logs its own failure: the person already has the booking."""
    from routers.calendly_webhooks import record_booking
    import integrations

    pool = await get_pool()
    async with pool.acquire() as conn:
        b = dict(await conn.fetchrow("SELECT * FROM personal_bookings WHERE id = $1", booking_id))
        ev = dict(await conn.fetchrow("SELECT * FROM personal_booking_types WHERE id = $1", b["type_id"]))
    who = f"{b['name']} ({b['business']})" if b["business"] else b["name"]
    desc = "\n".join(x for x in [
        f"Phone: {b['phone']}" if b["phone"] else None, f"Email: {b['email']}",
        f"Practice: {b['business']}" if b["business"] else None,
        f"Wants to cover: {b['note']}" if b["note"] else None,
        "", f"Need to reschedule or cancel? {manage_url(b['manage_token'])}",
    ] if x is not None)
    try:
        created = await asyncio.to_thread(
            integrations.calendar_create_meet_event,
            f"DigiGrowth {ev['name']}: {who}", b["start_at"], b["end_at"], b["email"], desc)
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE personal_bookings SET google_event_id = $2, meet_link = $3, calendar_error = NULL WHERE id = $1",
                booking_id, created["id"], created.get("meet_link"))
    except Exception as e:
        print(f"[personal-booking] calendar insert failed for booking {booking_id}: {e}")
        async with pool.acquire() as conn:
            await conn.execute("UPDATE personal_bookings SET calendar_error = $2 WHERE id = $1", booking_id, str(e)[:500])
    try:
        appt = await record_booking(
            name=b["name"], email=b["email"], phone=b["phone"], start_utc=b["start_at"], tz_name=b["timezone"],
            tracking={"utm_source": b["utm_source"], "utm_content": b["utm_content"]},
            event_uri=f"dgme:{booking_id}", client_id=None, call_type=ev["call_type"],
        )
        async with pool.acquire() as conn:
            await conn.execute("UPDATE personal_bookings SET appointment_id = $2 WHERE id = $1", booking_id, appt["id"])
            if b["business"] and appt.get("contact_id"):
                await conn.execute(
                    "UPDATE contacts SET business = $2, updated_at = now() WHERE id = $1 AND coalesce(business, '') = ''",
                    appt["contact_id"], b["business"])
    except Exception as e:
        print(f"[personal-booking] record_booking failed for booking {booking_id}: {e}")


async def get_by_token(token: str) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        b = await conn.fetchrow(
            """SELECT b.*, t.name AS type_name, t.duration_min, t.slug AS type_slug, t.description
               FROM personal_bookings b JOIN personal_booking_types t ON t.id = b.type_id
               WHERE b.manage_token = $1""", token)
    return dict(b) if b else None


def _event_call_sync(fn: str, event_id: str, **kw) -> None:
    import integrations
    svc = integrations._calendar_service()
    if fn == "delete":
        try:
            svc.events().delete(calendarId="primary", eventId=event_id, sendUpdates="all").execute()
        except Exception as e:
            if "410" not in str(e) and "404" not in str(e):
                raise
    else:
        svc.events().patch(calendarId="primary", eventId=event_id, sendUpdates="all", body={
            "start": {"dateTime": kw["start"].isoformat()}, "end": {"dateTime": kw["end"].isoformat()},
        }).execute()


async def cancel(booking_id: int, by_prospect: bool, reason: str | None = None, touch_appointment: bool = True) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        b = await conn.fetchrow(
            """UPDATE personal_bookings SET status = 'cancelled', cancelled_at = now(), cancelled_by = $2,
                   cancel_reason = $3 WHERE id = $1 AND status = 'confirmed' RETURNING *""",
            booking_id, "prospect" if by_prospect else "dylan", (reason or "").strip()[:500] or None)
        call_type = await conn.fetchval(
            "SELECT t.call_type FROM personal_booking_types t JOIN personal_bookings b ON b.type_id = t.id WHERE b.id = $1",
            booking_id)
    if not b:
        raise BookingError("This booking is no longer active.")
    _busy_cache["at"] = 0.0
    if b["google_event_id"]:
        try:
            await asyncio.to_thread(_event_call_sync, "delete", b["google_event_id"])
        except Exception as e:
            print(f"[personal-booking] calendar delete failed for booking {booking_id}: {e}")
    if touch_appointment and b["appointment_id"]:
        from fastapi import HTTPException
        from routers.appointments import cancel_appointment
        try:
            # Same rule as a Calendly invitee cancel: only a prospect dropping
            # their own discovery call gets the recovery drip.
            await cancel_appointment(b["appointment_id"], notify=by_prospect and call_type == "discovery")
        except HTTPException:
            pass


async def reschedule(booking_id: int, new_start_iso: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        b = await conn.fetchrow("SELECT * FROM personal_bookings WHERE id = $1", booking_id)
        ev = await conn.fetchrow("SELECT * FROM personal_booking_types WHERE id = $1", b["type_id"]) if b else None
    if not b or b["status"] != "confirmed":
        raise BookingError("This booking is no longer active.")
    start = _parse_start(new_start_iso)
    await _assert_open(b["type_id"], start, exclude_booking_id=booking_id)
    end = start + timedelta(minutes=ev["duration_min"])
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("SELECT pg_advisory_xact_lock($1)", LOCK_KEY)
            if await conn.fetchval(
                    "SELECT 1 FROM personal_bookings WHERE status = 'confirmed' AND id <> $3 AND start_at < $2 AND end_at > $1",
                    start, end, booking_id):
                raise BookingError("Sorry, that time was just taken. Please pick another.")
            await conn.execute(
                "UPDATE personal_bookings SET start_at = $2, end_at = $3, rescheduled_at = now() WHERE id = $1",
                booking_id, start, end)
            if b["appointment_id"]:
                # Same reset booking_engine.reschedule_booking does: fresh
                # reminder windows for the new time.
                await conn.execute(
                    "UPDATE appointment_reminders SET appointment_at = $2, status = 'scheduled', "
                    "reminder_24h_sent_at = NULL, reminder_6h_sent_at = NULL, reminder_1h_sent_at = NULL, "
                    "reminder_steps_sent = '{}'::jsonb, reminders_armed_at = now() WHERE id = $1",
                    b["appointment_id"], start)
    _busy_cache["at"] = 0.0
    if b["google_event_id"]:
        try:
            await asyncio.to_thread(_event_call_sync, "patch", b["google_event_id"], start=start, end=end)
        except Exception as e:
            print(f"[personal-booking] calendar move failed for booking {booking_id}: {e}")


async def on_appointment_cancelled(appointment_id: int) -> None:
    """routers/appointments.py cancel_appointment hook for dgme: rows."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        bid = await conn.fetchval(
            "SELECT id FROM personal_bookings WHERE appointment_id = $1 AND status = 'confirmed'", appointment_id)
    if bid:
        try:
            await cancel(bid, by_prospect=False, reason="Canceled in DigiGrowth", touch_appointment=False)
        except BookingError:
            pass
