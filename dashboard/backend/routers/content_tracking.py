"""Unified view-tracking for prospect-facing video content:

  1. The website VSL (Vimeo-embedded, on digigrowth-website's /contact page)
  2. Outreach ("loom") videos — personalized cold-outreach clips self-hosted
     via routers/watch.py's /watch/{slug} pages

Both report into one table (content_view_events) via one public endpoint
below, so "is anyone engaging with what I send them" has a single answer
instead of two disconnected systems. The two GET endpoints below back the
internal Analytics tab's VSL funnel and Loom Outreach funnel cards.

POST /track/view-event is intentionally public/unauthenticated (mounted
with no dependencies, same as watch.router) — it's hit via
navigator.sendBeacon() from a fully public marketing site with no
DigiGrowth auth of its own, and from the public /watch/{slug} pages.

POST /content-analytics/exclude-my-ip (authenticated) lets Dylan exclude
his own IP from ever counting toward these stats — call it from your own
browser/device so checking a client's live funnel doesn't inflate their
real traffic numbers.
"""

import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request
from db import get_pool

router = APIRouter()          # public — mounted with no auth
admin_router = APIRouter()    # authenticated — mounted under /api

_VALID_SOURCES = {"vsl", "outreach_video", "landing_page", "client_website"}
_VALID_EVENTS = {"view", "play", "progress_25", "progress_50", "progress_75", "complete", "conversion"}

_EXCLUDED_IPS_KEY = "tracking_excluded_ips"


def _since(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def _client_ip(request: Request) -> str:
    """Railway sits in front of this app as a reverse proxy, so the real
    caller IP is the first hop in X-Forwarded-For, not request.client.host
    (that's Railway's own internal proxy IP)."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else ""


async def _excluded_ips(conn) -> list:
    row = await conn.fetchrow("SELECT value FROM dialer_settings WHERE key = $1", _EXCLUDED_IPS_KEY)
    return json.loads(row["value"]) if row and row["value"] else []


async def _save_excluded_ips(conn, ips: list) -> None:
    await conn.execute(
        "INSERT INTO dialer_settings (key, value, updated_at) VALUES ($1, $2, now()) "
        "ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = now()",
        _EXCLUDED_IPS_KEY, json.dumps(ips),
    )


@router.post("/track/view-event")
async def track_view_event(request: Request):
    """Fire-and-forget — always returns quickly, never raises. Malformed
    payloads are silently dropped rather than erroring, since the caller
    (sendBeacon) never reads the response anyway.

    Parses the raw body manually instead of declaring a `dict` parameter:
    FastAPI's automatic body-to-dict validation requires a
    `Content-Type: application/json` header, but `navigator.sendBeacon(url,
    aJsonString)` — as originally called from both digigrowth-website's
    tracking.js and watch.py's inline script — sends `text/plain` by
    default, which made every one of those calls fail with a 422 and
    silently drop the event server-side (confirmed live 2026-09-11: real
    beacons from the production contact page were 422ing). Both call sites
    were fixed to wrap the payload in a `Blob({type: 'application/json'})`,
    but parsing content-type-agnostically here is the actual fix — it holds
    even if a future call site (or a stale cached bundle) gets this wrong
    again."""
    try:
        body = json.loads(await request.body())
    except Exception:
        return {"ok": True}
    if not isinstance(body, dict):
        return {"ok": True}

    source = (body.get("source") or "").strip()
    event_type = (body.get("event_type") or "").strip()
    content_key = (body.get("content_key") or "").strip()
    if source not in _VALID_SOURCES or event_type not in _VALID_EVENTS or not content_key:
        return {"ok": True}

    lead = (body.get("lead") or "").strip() or None
    session_id = (body.get("session_id") or "").strip() or None
    # Only 'client_website' senders currently set this (fbclid param or a
    # facebook.com/instagram.com document.referrer, detected client-side —
    # see design-agent's funnel tracking snippet). Left NULL for every
    # other source/caller rather than defaulting to False, so "unknown" is
    # distinguishable from "confirmed not Meta" if that ever matters.
    from_meta = body.get("from_meta")
    from_meta = bool(from_meta) if isinstance(from_meta, bool) else None

    ip = _client_ip(request)

    pool = await get_pool()
    async with pool.acquire() as conn:
        # Self-view exclusion (routers/content_tracking.py's exclude_my_ip) —
        # checking your own funnel/VSL page from your own network otherwise
        # inflates a client's real traffic stats. Checked before anything
        # else so an excluded IP never even resolves a contact lookup.
        if ip and ip in await _excluded_ips(conn):
            return {"ok": True}

        contact_id = None
        if lead:
            row = await conn.fetchrow("SELECT id FROM contacts WHERE id = $1", lead)
            if row:
                contact_id = row["id"]
        try:
            await conn.execute(
                "INSERT INTO content_view_events (source, content_key, contact_id, session_id, event_type, from_meta) "
                "VALUES ($1, $2, $3, $4, $5, $6)",
                source, content_key, contact_id, session_id, event_type, from_meta,
            )
        except Exception as e:
            print(f"[content_tracking] failed to log view event: {e}")

    return {"ok": True}


@admin_router.get("/content-analytics/excluded-ips")
async def list_excluded_ips():
    pool = await get_pool()
    async with pool.acquire() as conn:
        return {"ips": await _excluded_ips(conn)}


@admin_router.post("/content-analytics/exclude-my-ip")
async def exclude_my_ip(request: Request):
    """Adds the CALLER's own resolved IP to the tracking exclusion list —
    call this from your own browser/device, never from a server-side
    script or a different network, since it excludes whatever IP actually
    made THIS request. Safe to call again later if your IP changes; it's
    a no-op if that IP's already excluded."""
    ip = _client_ip(request)
    if not ip:
        raise HTTPException(400, "Could not determine caller IP")
    pool = await get_pool()
    async with pool.acquire() as conn:
        ips = await _excluded_ips(conn)
        if ip not in ips:
            ips.append(ip)
            await _save_excluded_ips(conn, ips)
    return {"ok": True, "ip": ip, "excluded_ips": ips}


@admin_router.delete("/content-analytics/excluded-ips/{ip}")
async def remove_excluded_ip(ip: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        ips = [x for x in await _excluded_ips(conn) if x != ip]
        await _save_excluded_ips(conn, ips)
    return {"ok": True, "excluded_ips": ips}


@admin_router.delete("/content-analytics/vsl")
async def reset_vsl_stats():
    """Wipe VSL view history (source='vsl' rows only — never touches
    outreach_video rows, which are a separate real campaign history).
    Added 2026-09-11 to clear out test-generated events from verifying the
    /track/view-event content-type fix before real traffic starts counting
    against the newly-swapped contact-page VSL."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        deleted = await conn.fetchval(
            "WITH d AS (DELETE FROM content_view_events WHERE source = 'vsl' RETURNING 1) SELECT count(*) FROM d"
        )
    return {"deleted": deleted}


@admin_router.get("/content-analytics/vsl")
async def vsl_funnel(days: int = 0):
    """VSL funnel — deliberately NOT scoped to "who's a known lead" (that
    turned out to be more attribution than needed): counts every viewer,
    identified or anonymous, keyed by contact_id when a ?lead= link
    resolved one, else the anonymous session_id (see digigrowth-website's
    src/lib/tracking.js). Viewed -> Watched 50%+ -> Completed -> Booked,
    where Booked can only ever count identified viewers (an anonymous
    session has no contacts row to check appointment status against) —
    so booking_rate is a floor, not exact, by nature of anonymous traffic
    existing at all. `days=0` means all-time."""
    since = "AND occurred_at >= $1" if days else ""
    since_e = "AND e.occurred_at >= $1" if days else ""
    params = [_since(days)] if days else []

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            WITH viewed AS (
                SELECT DISTINCT COALESCE(contact_id::text, session_id) AS viewer
                FROM content_view_events
                WHERE source = 'vsl' AND event_type = 'view' {since}
            ),
            half AS (
                SELECT DISTINCT COALESCE(contact_id::text, session_id) AS viewer
                FROM content_view_events
                WHERE source = 'vsl' AND event_type IN ('progress_50', 'progress_75', 'complete') {since}
            ),
            done AS (
                SELECT DISTINCT COALESCE(contact_id::text, session_id) AS viewer
                FROM content_view_events
                WHERE source = 'vsl' AND event_type = 'complete' {since}
            ),
            booked AS (
                SELECT DISTINCT c.id FROM contacts c
                JOIN content_view_events e ON e.contact_id = c.id
                WHERE e.source = 'vsl' AND e.event_type = 'view' {since_e}
                AND c.status = 'appointment-booked'
            )
            SELECT
                (SELECT count(*) FROM viewed) AS viewed,
                (SELECT count(*) FROM half) AS watched_half,
                (SELECT count(*) FROM done) AS completed,
                (SELECT count(*) FROM booked) AS booked
            """,
            *params,
        )

    def _pct(num, denom):
        return round(num / denom * 100, 1) if denom else 0.0

    d = dict(row)
    d["booking_rate"] = _pct(d["booked"], d["viewed"])
    return d


@admin_router.get("/content-analytics/loom-outreach")
async def loom_outreach_funnel(days: int = 0):
    """Loom outreach funnel, cohort = ONLY contacts who were actually sent
    an outreach video (watch_videos.contact_id IS NOT NULL) — this card is
    deliberately hinged on that; a contact never sent a video never
    appears here at all, regardless of anything else they've done.
    Sent -> Viewed -> Completed -> Engaged -> Interested -> Booked.
    Completed reuses the same 'complete' event the video's own inline
    player script already fires (routers/watch.py's watch_page()) — no
    new tracking needed, just a new stage reading an event type that was
    already being logged. Engaged/Interested reuse the existing manual
    stage_engaged/stage_interested checkboxes already tracked on
    sms_conversations (routers/sms.py) rather than inventing a new stage
    concept."""
    sent_since = "AND wv.created_at >= $1" if days else ""
    params = [_since(days)] if days else []

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            WITH cohort AS (
                SELECT DISTINCT contact_id FROM watch_videos wv
                WHERE contact_id IS NOT NULL {sent_since}
            ),
            viewed AS (
                SELECT DISTINCT contact_id FROM content_view_events
                WHERE source = 'outreach_video' AND event_type = 'view'
                AND contact_id IN (SELECT contact_id FROM cohort)
            ),
            completed AS (
                SELECT DISTINCT contact_id FROM content_view_events
                WHERE source = 'outreach_video' AND event_type = 'complete'
                AND contact_id IN (SELECT contact_id FROM cohort)
            ),
            engaged AS (
                SELECT DISTINCT sc.contact_id FROM sms_conversations sc
                WHERE sc.contact_id IN (SELECT contact_id FROM cohort) AND sc.stage_engaged
            ),
            interested AS (
                SELECT DISTINCT sc.contact_id FROM sms_conversations sc
                WHERE sc.contact_id IN (SELECT contact_id FROM cohort) AND sc.stage_interested
            ),
            booked AS (
                SELECT id FROM contacts
                WHERE id IN (SELECT contact_id FROM cohort) AND status = 'appointment-booked'
            )
            SELECT
                (SELECT count(*) FROM cohort) AS sent,
                (SELECT count(*) FROM viewed) AS viewed,
                (SELECT count(*) FROM completed) AS completed,
                (SELECT count(*) FROM engaged) AS engaged,
                (SELECT count(*) FROM interested) AS interested,
                (SELECT count(*) FROM booked) AS booked
            """,
            *params,
        )
    return dict(row)
