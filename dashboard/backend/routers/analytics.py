"""
Analytics router — mirrors the Notion KPI structure.

GET /analytics/outreach?days=30  — per-channel table (calling + SMS + email), all-time + period
GET /analytics/pipeline           — 6-stage acquisition funnel + grade breakdown + top states
GET /analytics/sales              — sales statistics (reads sales_stats.json + DB)
GET /analytics/calls?days=30      — calling detail: daily trend + disposition breakdown
GET /analytics/sheets-digest      — most recent sheets-digest report file content + metadata
"""

import json
import pathlib
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from db import get_pool

router = APIRouter()

_SALES_STATS_PATH = pathlib.Path(__file__).parent.parent / "sales_stats.json"
_EA_REPORTS_DIR = pathlib.Path(__file__).parent.parent.parent.parent / "executive-assistant" / "reports"

POSITIVE_DISPOSITIONS = ("Appointment Booked", "Follow Up", "Send Info", "SMS Handoff", "Not Interested")
PITCHED_DISPOSITIONS  = ("Appointment Booked", "Follow Up", "Send Info", "SMS Handoff", "Not Interested")
NO_CONTACT_DISPOSITIONS = ("No Answer", "Voicemail")


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


async def _calling_metrics(conn, since=None) -> dict:
    """Return calling funnel metrics. If since is None, returns all-time."""
    where = "WHERE started_at >= $1" if since else ""
    params = [since] if since else []

    row = await conn.fetchrow(
        f"""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE disposition NOT IN ('No Answer','Voicemail')) AS answered,
            COUNT(*) FILTER (WHERE disposition IN {str(PITCHED_DISPOSITIONS).replace('[','(').replace(']',')')}) AS pitched,
            COUNT(*) FILTER (WHERE disposition = 'Appointment Booked') AS booked
        FROM call_logs {where}
        """,
        *params,
    )
    total   = row["total"]   or 0
    answered = row["answered"] or 0
    pitched  = row["pitched"]  or 0
    booked   = row["booked"]   or 0
    return {
        "total":             total,
        "answer_rate":       _pct(answered, total),
        "conversation_rate": _pct(pitched, answered),
        "pitch_rate":        _pct(pitched, answered),
        "abr":               _pct(booked, total),
        "booked":            booked,
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
    closed = await conn.fetchval(
        f"SELECT COUNT(*) FROM sms_conversations sc WHERE status='closed' {time_filter}", *params
    )

    return {
        "total_sent":        total_sent   or 0,
        "reply_rate":        _pct(replied, total_convos),
        "conversation_rate": _pct(replied, total_convos),
        "engaged_rate":      _pct(engaged, total_convos),
        "abr":               _pct(closed, total_convos),
        "booked":            closed or 0,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/analytics/outreach")
async def outreach(days: int = 30):
    pool = await get_pool()
    since = _since(days)

    async with pool.acquire() as conn:
        calling_all    = await _calling_metrics(conn)
        calling_period = await _calling_metrics(conn, since)
        sms_all        = await _sms_metrics(conn)
        sms_period     = await _sms_metrics(conn, since)
        newsletter_subs = await conn.fetchval(
            "SELECT COUNT(*) FROM contacts WHERE newsletter = true"
        )

    return {
        "period_days": days,
        "calling": {
            "all_time": calling_all,
            "period":   calling_period,
        },
        "sms": {
            "all_time": sms_all,
            "period":   sms_period,
        },
        "email": {
            "subscribers": newsletter_subs or 0,
            "note": "Open/click tracking requires GHL webhook integration.",
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


@router.get("/analytics/calls")
async def calls_detail(days: int = 0):
    pool      = await get_pool()
    all_time  = (days == 0)
    stats     = _load_sales_stats()
    since     = _since(days) if not all_time else _since(36500)

    async with pool.acquire() as conn:
        dispo_rows = await conn.fetch(
            """
            SELECT disposition, COUNT(*) AS cnt
            FROM call_logs WHERE started_at >= $1 AND disposition IS NOT NULL
            GROUP BY disposition ORDER BY cnt DESC
            """,
            since,
        )
        daily_rows = await conn.fetch(
            """
            SELECT DATE(started_at) AS day, COUNT(*) AS calls,
                   COUNT(*) FILTER (WHERE disposition NOT IN ('No Answer','Voicemail')) AS pickups
            FROM call_logs WHERE started_at >= $1
            GROUP BY DATE(started_at) ORDER BY day
            """,
            since,
        )

    return {
        "total_calls": _sheet_stat(stats, "sheet_calls_made",         days),
        "pickups":     _sheet_stat(stats, "sheet_calls_answered",     days),
        "booked":      _sheet_stat(stats, "sheet_appointments_booked",days),
        "by_disposition": [{"disposition": r["disposition"], "cnt": r["cnt"]} for r in dispo_rows],
        "daily":          [{"date": str(r["day"]), "calls": r["calls"], "pickups": r["pickups"]} for r in daily_rows],
    }


@router.get("/analytics/sheets-digest")
async def sheets_digest():
    """Return the most recent sheets-digest report file content and metadata."""
    if not _EA_REPORTS_DIR.exists():
        return {"date": None, "content": None, "sheets": []}

    files = sorted(_EA_REPORTS_DIR.glob("sheets-digest-*.md"), reverse=True)
    if not files:
        return {"date": None, "content": None, "sheets": []}

    latest = files[0]
    content = latest.read_text()

    # Extract date from filename: sheets-digest-YYYY-MM-DD.md
    m = re.search(r"sheets-digest-(\d{4}-\d{2}-\d{2})\.md$", latest.name)
    date = m.group(1) if m else None

    # Extract sheet names (lines starting with "## ")
    sheets = [line[3:].strip() for line in content.splitlines() if line.startswith("## ")]

    return {"date": date, "content": content, "sheets": sheets}
