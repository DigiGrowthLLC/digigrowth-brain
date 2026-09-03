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
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from db import get_pool

router = APIRouter()          # public — mounted with no auth
admin_router = APIRouter()    # authenticated — mounted under /api

_VALID_SOURCES = {"vsl", "outreach_video"}
_VALID_EVENTS = {"view", "play", "progress_25", "progress_50", "progress_75", "complete"}


def _since(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


@router.post("/track/view-event")
async def track_view_event(body: dict):
    """Fire-and-forget — always returns quickly, never raises. Malformed
    payloads are silently dropped rather than erroring, since the caller
    (sendBeacon) never reads the response anyway."""
    source = (body.get("source") or "").strip()
    event_type = (body.get("event_type") or "").strip()
    content_key = (body.get("content_key") or "").strip()
    if source not in _VALID_SOURCES or event_type not in _VALID_EVENTS or not content_key:
        return {"ok": True}

    lead = (body.get("lead") or "").strip() or None
    session_id = (body.get("session_id") or "").strip() or None

    pool = await get_pool()
    async with pool.acquire() as conn:
        contact_id = None
        if lead:
            row = await conn.fetchrow("SELECT id FROM contacts WHERE id = $1", lead)
            if row:
                contact_id = row["id"]
        try:
            await conn.execute(
                "INSERT INTO content_view_events (source, content_key, contact_id, session_id, event_type) "
                "VALUES ($1, $2, $3, $4, $5)",
                source, content_key, contact_id, session_id, event_type,
            )
        except Exception as e:
            print(f"[content_tracking] failed to log view event: {e}")

    return {"ok": True}


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
