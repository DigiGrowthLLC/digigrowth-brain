"""
Analytics router — mirrors the Notion KPI structure.

GET /analytics/outreach?days=30  — per-channel table (calling + SMS + content), all-time + period
GET /analytics/pipeline           — 6-stage acquisition funnel + grade breakdown + top states
GET /analytics/sales              — sales statistics (reads sales_stats.json + DB)
"""

import json
import pathlib
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from db import get_pool

router = APIRouter()

_SALES_STATS_PATH   = pathlib.Path(__file__).parent.parent / "sales_stats.json"
_CONTENT_STATS_PATH = pathlib.Path(__file__).parent.parent / "content_stats.json"


def _since(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def _sheet_stat(stats: dict, base_key: str, days: int) -> int:
    """Return the right period bucket from sales_stats.json.
    days=0 → all-time (base_key)
    days=7 → base_key_7d, falling back to 0
    days=30 → base_key_30d, falling back to 0
    """
    if days == 0:
        return stats.get(base_key, 0) or 0
    suffix = f"_{days}d"
    return stats.get(f"{base_key}{suffix}", 0) or 0


def _pct(num, denom) -> float:
    if not denom:
        return 0.0
    return round(num / denom * 100, 1)


def _load_sales_stats() -> dict:
    try:
        return json.loads(_SALES_STATS_PATH.read_text())
    except Exception:
        return {"discovery_calls": 0, "strategy_sessions": 0, "closes": 0,
                "shows": 0, "total_revenue": 0, "avg_deal_size": 0}


def _load_content_stats() -> dict:
    try:
        return json.loads(_CONTENT_STATS_PATH.read_text())
    except Exception:
        return {
            "posts_published": 0, "posts_published_7d": 0, "posts_published_30d": 0,
            "videos_published": 0, "videos_published_7d": 0, "videos_published_30d": 0,
            "total_views": 0, "total_views_7d": 0, "total_views_30d": 0,
            "leads_from_content": 0, "leads_from_content_7d": 0, "leads_from_content_30d": 0,
        }


def _content_metrics(stats: dict, days: int) -> dict:
    return {
        "posts_published":    _sheet_stat(stats, "posts_published", days),
        "videos_published":   _sheet_stat(stats, "videos_published", days),
        "total_views":        _sheet_stat(stats, "total_views", days),
        "leads_from_content": _sheet_stat(stats, "leads_from_content", days),
    }


def _calling_metrics(stats: dict, days: int) -> dict:
    """Cold calling metrics — sourced from the daily Sheets Digest (sales_stats.json),
    not the dialer DB, since the sheets are the system of record for cold calling."""
    calls_made          = _sheet_stat(stats, "sheet_calls_made", days)
    calls_answered      = _sheet_stat(stats, "sheet_calls_answered", days)
    contacts_reached    = _sheet_stat(stats, "sheet_contacts_reached", days)
    appointments_booked = _sheet_stat(stats, "sheet_appointments_booked", days)
    return {
        "total":             calls_made,
        "answer_rate":       _pct(calls_answered, calls_made),
        "conversation_rate": _pct(contacts_reached, calls_answered),
        "abr":               _pct(appointments_booked, calls_made),
        "booked":            appointments_booked,
    }


async def _sms_metrics(conn, since=None) -> dict:
    """Return SMS funnel metrics. If since is None, returns all-time."""
    time_filter = "AND sc.created_at >= $1" if since else ""
    msg_filter  = "AND sent_at >= $1"       if since else ""
    params = [since] if since else []

    total_sent = await conn.fetchval(
        f"SELECT COUNT(*) FROM sms_messages WHERE direction='outbound' {msg_filter}", *params
    )
    total_convos = await conn.fetchval(
        f"SELECT COUNT(*) FROM sms_conversations sc WHERE true {time_filter}", *params
    )
    replied = await conn.fetchval(
        f"""
        SELECT COUNT(DISTINCT sc.id) FROM sms_conversations sc
        WHERE EXISTS (
            SELECT 1 FROM sms_messages sm
            WHERE sm.phone = sc.phone AND sm.direction='inbound'
            {('AND sm.sent_at >= $1' if since else '')}
        )
        {time_filter}
        """,
        *params,
    ) if since else await conn.fetchval(
        """
        SELECT COUNT(DISTINCT sc.id) FROM sms_conversations sc
        WHERE EXISTS (
            SELECT 1 FROM sms_messages sm WHERE sm.phone = sc.phone AND sm.direction='inbound'
        )
        """
    )
    engaged = await conn.fetchval(
        f"""
        SELECT COUNT(DISTINCT sc.id) FROM sms_conversations sc
        WHERE (
            SELECT COUNT(*) FROM sms_messages sm
            WHERE sm.phone = sc.phone AND sm.direction='inbound'
            {('AND sm.sent_at >= $1' if since else '')}
        ) >= 2
        {time_filter}
        """,
        *params,
    ) if since else await conn.fetchval(
        """
        SELECT COUNT(DISTINCT sc.id) FROM sms_conversations sc
        WHERE (SELECT COUNT(*) FROM sms_messages sm WHERE sm.phone = sc.phone AND sm.direction='inbound') >= 2
        """
    )
    booked = await conn.fetchval(
        f"SELECT COUNT(*) FROM sms_conversations sc WHERE disposition='booked' {time_filter}", *params
    )
    not_interested = await conn.fetchval(
        f"SELECT COUNT(*) FROM sms_conversations sc WHERE disposition='not_interested' {time_filter}", *params
    )
    interested = await conn.fetchval(
        f"SELECT COUNT(*) FROM sms_conversations sc WHERE disposition IN ('interested','booked') {time_filter}", *params
    )

    return {
        "total_sent":        total_sent   or 0,
        "reply_rate":        _pct(replied, total_convos),
        "conversation_rate": _pct(replied, total_convos),
        "engaged_rate":      _pct(engaged, total_convos),
        "interested":        interested or 0,
        "interested_rate":   _pct(interested, total_convos),
        "not_interested":    not_interested or 0,
        "abr":               _pct(booked, total_convos),
        "booked":            booked or 0,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/analytics/outreach")
async def outreach(days: int = 30):
    pool  = await get_pool()
    since = _since(days)
    cs    = _load_content_stats()
    sales = _load_sales_stats()

    async with pool.acquire() as conn:
        sms_all        = await _sms_metrics(conn)
        sms_period     = await _sms_metrics(conn, since)

    return {
        "period_days": days,
        "calling": {
            "all_time": _calling_metrics(sales, 0),
            "period":   _calling_metrics(sales, days),
        },
        "sms": {
            "all_time": sms_all,
            "period":   sms_period,
        },
        "content": {
            "all_time": _content_metrics(cs, 0),
            "period":   _content_metrics(cs, days),
        },
    }


@router.get("/analytics/pipeline")
async def pipeline(days: int = 0):
    pool  = await get_pool()
    sales = _load_sales_stats()
    all_time = (days == 0)
    week_ago  = _since(7)
    month_ago = _since(30)

    async with pool.acquire() as conn:
        total_leads = await conn.fetchval("SELECT COUNT(*) FROM contacts")
        new_week    = await conn.fetchval("SELECT COUNT(*) FROM contacts WHERE created_at >= $1", week_ago)
        new_month   = await conn.fetchval("SELECT COUNT(*) FROM contacts WHERE created_at >= $1", month_ago)
        grade_rows  = await conn.fetch(
            """
            SELECT grade,
                   COUNT(*) AS cnt,
                   COUNT(*) FILTER (WHERE status = 'appointment-booked') AS booked
            FROM contacts
            WHERE grade IS NOT NULL
            GROUP BY grade ORDER BY grade
            """
        )
        state_rows = await conn.fetch(
            """
            SELECT state, COUNT(*) AS cnt
            FROM contacts
            WHERE state IS NOT NULL AND state != ''
            GROUP BY state ORDER BY cnt DESC LIMIT 8
            """
        )

    by_grade = [
        {"grade": r["grade"], "cnt": r["cnt"], "booked": r["booked"], "book_rate": _pct(r["booked"], r["cnt"])}
        for r in grade_rows
    ]

    return {
        "funnel": {
            "total_leads": ((sales.get("sheet_calls_made") or 0) + (total_leads or 0)) if all_time else (total_leads or 0),
            "dialed":   _sheet_stat(sales, "sheet_calls_made",        days),
            "answered": _sheet_stat(sales, "sheet_calls_answered",    days),
            "pitched":  _sheet_stat(sales, "sheet_contacts_reached",  days),
            "booked":   _sheet_stat(sales, "sheet_appointments_booked", days),
            "shows":    sales.get("shows", 0) if all_time else 0,
            "closes":   sales.get("closes", 0) if all_time else 0,
        },
        "by_grade":       by_grade,
        "top_states":     [{"state": r["state"], "cnt": r["cnt"]} for r in state_rows],
        "new_this_week":  new_week  or 0,
        "new_this_month": new_month or 0,
    }


@router.get("/analytics/sales")
async def sales_stats():
    pool  = await get_pool()
    stats = _load_sales_stats()

    async with pool.acquire() as conn:
        total_leads = await conn.fetchval("SELECT COUNT(*) FROM contacts")

    discovery = stats.get("discovery_calls", 0)
    closes    = stats.get("closes", 0)

    sheet_sync = None
    if stats.get("last_sheet_sync"):
        sheet_sync = {
            "synced_at":           stats.get("last_sheet_sync"),
            "source_note":         stats.get("last_sheet_sync_note", ""),
            "calls_made":          stats.get("sheet_calls_made"),
            "contacts_reached":    stats.get("sheet_contacts_reached"),
            "appointments_booked": stats.get("sheet_appointments_booked"),
            "sms_sent":            stats.get("sheet_sms_sent"),
        }

    return {
        "total_leads":       total_leads or 0,
        "discovery_calls":   discovery,
        "strategy_sessions": stats.get("strategy_sessions", 0),
        "closes":            closes,
        "close_rate":        _pct(closes, discovery),
        "total_revenue":     stats.get("total_revenue", 0),
        "avg_deal_size":     stats.get("avg_deal_size", 0),
        "shows":             stats.get("shows", 0),
        "sheet_sync":        sheet_sync,
    }




