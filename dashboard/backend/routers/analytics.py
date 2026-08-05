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
    not the dialer DB, since the sheets are the system of record for cold calling.

    Rate formulas match the KPI panel on the source "DigiGrowth Cold Calling
    Metrics" sheets exactly (verified against real sheet data):
      - Pitch Rate (PR)      = contacts_reached ÷ calls_made
                                (the sheet's own Totals row calls contacts_reached "Pitches")
      - Resonation Rate (RR) = resonations ÷ contacts_reached
    """
    calls_made          = _sheet_stat(stats, "sheet_calls_made", days)
    calls_answered      = _sheet_stat(stats, "sheet_calls_answered", days)
    contacts_reached    = _sheet_stat(stats, "sheet_contacts_reached", days)
    resonations         = _sheet_stat(stats, "sheet_resonations", days)
    appointments_booked = _sheet_stat(stats, "sheet_appointments_booked", days)
    return {
        "total":            calls_made,
        "answer_rate":      _pct(calls_answered, calls_made),
        "pitch_rate":       _pct(contacts_reached, calls_made),
        "resonation_rate":  _pct(resonations, contacts_reached),
        "pitches":          contacts_reached,
        "resonations":      resonations,
        "abr":              _pct(appointments_booked, calls_made),
        "booked":           appointments_booked,
    }


async def _sms_metrics(conn, since=None) -> dict:
    """
    Return SMS funnel metrics. If since is None, returns all-time.

    Replied/Engaged/Interested are read straight off sms_conversations'
    stage_replied/stage_engaged/stage_interested checkboxes — NOT recomputed
    from message counts here. Those checkboxes are auto-set from the
    prospect's inbound reply count (1+/2+/3+ respectively) by
    sms.py::_recompute_stage_flags() on every inbound message, but a rep can
    manually check/uncheck any of them from the Inbox (POST
    /inbox/contact/{contact_id}/stage in email_inbox.py) — once touched
    manually, the checkbox is authoritative and stops tracking the raw
    count. So this function always trusts the stored checkbox, by design.

    `contacted` (distinct phones sent an outbound message in the window) is
    the single denominator for every rate — matches the pattern
    _email_metrics() already uses for its own reply rate.
    """
    msg_filter = "AND sent_at >= $1" if since else ""
    params = [since] if since else []

    # Total Outreach — every outbound SMS sent, counted the moment it's sent.
    total_outreach = await conn.fetchval(
        f"SELECT COUNT(*) FROM sms_messages WHERE direction='outbound' {msg_filter}",
        *params,
    )

    contacted = await conn.fetchval(
        f"SELECT COUNT(DISTINCT phone) FROM sms_messages WHERE direction='outbound' {msg_filter}",
        *params,
    )

    stage_filter = "AND sc.phone = ANY($1)" if since else ""
    stage_params = params.copy()
    if since:
        contacted_phones = await conn.fetch(
            f"SELECT DISTINCT phone FROM sms_messages WHERE direction='outbound' {msg_filter}",
            *params,
        )
        stage_params = [[r["phone"] for r in contacted_phones]]

    replied = await conn.fetchval(
        f"SELECT COUNT(*) FROM sms_conversations sc WHERE stage_replied {stage_filter}",
        *stage_params,
    )
    engaged = await conn.fetchval(
        f"SELECT COUNT(*) FROM sms_conversations sc WHERE stage_engaged {stage_filter}",
        *stage_params,
    )
    interested = await conn.fetchval(
        f"SELECT COUNT(*) FROM sms_conversations sc WHERE stage_interested {stage_filter}",
        *stage_params,
    )

    booked = await conn.fetchval(
        f"SELECT COUNT(*) FROM sms_conversations WHERE disposition='booked' "
        f"{'AND created_at >= $1' if since else ''}",
        *params,
    )

    return {
        "total_outreach":  total_outreach or 0,
        "contacted":       contacted or 0,
        "replied":         replied or 0,
        "reply_rate":      _pct(replied, contacted),
        "engaged":         engaged or 0,
        "engaged_rate":    _pct(engaged, contacted),
        "interested":      interested or 0,
        "interested_rate": _pct(interested, contacted),
        "booked":          booked or 0,
        "abr":             _pct(booked, contacted),
    }


async def _email_metrics(conn, since=None) -> dict:
    """
    Email funnel metrics — sent / reply rate / booked.
    Unlike SMS, email has no stage sequence (no equivalent of auto_opener →
    curiosity_opener → ... → cta), so this only tracks what the data
    actually supports: outbound sends, whether the contact replied, and
    conversations marked booked.
    """
    # is_test excludes diagnostic sends (e.g. /newsletter/test-send, used to
    # verify the open-tracking pixel end-to-end) — those are self-opened by
    # whoever ran the test, which skews open rate badly against a real
    # campaign's small early denominator if left in.
    msg_filter = "AND NOT is_test" + (" AND sent_at >= $1" if since else "")
    params = [since] if since else []

    total_sent = await conn.fetchval(
        f"SELECT COUNT(*) FROM email_messages WHERE direction='outbound' {msg_filter}",
        *params,
    )

    initial_sent = await conn.fetchval(
        f"SELECT COUNT(DISTINCT email) FROM email_messages WHERE direction='outbound' {msg_filter}",
        *params,
    )

    # Replied: distinct contacts who received an outbound email in this
    # window AND have at least one inbound message on the same thread.
    replied = await conn.fetchval(
        f"""
        SELECT COUNT(DISTINCT out.email)
        FROM email_messages out
        WHERE out.direction='outbound' {msg_filter.replace('sent_at', 'out.sent_at')}
        AND EXISTS (
            SELECT 1 FROM email_messages inb
            WHERE inb.thread_id = out.thread_id AND inb.direction='inbound'
        )
        """,
        *params,
    )

    # Windowed by updated_at (bumped when disposition is set — see
    # email_inbox.py's close-conversation handler), not created_at (when the
    # thread first started), so a booking that lands in this period shows up
    # here even if the contact was first emailed before the window started.
    booked_total = await conn.fetchval(
        f"SELECT COUNT(*) FROM email_conversations WHERE disposition='booked' "
        f"{'AND updated_at >= $1' if since else ''}",
        *params,
    )

    # Opened: distinct contacts whose open-tracking pixel fired at least once.
    # Best-effort, not precise — Gmail/Apple both auto-prefetch images for
    # privacy reasons, which inflates this above true human opens.
    opened = await conn.fetchval(
        f"""
        SELECT COUNT(DISTINCT email) FROM email_messages
        WHERE direction='outbound' AND opened_at IS NOT NULL {msg_filter}
        """,
        *params,
    )

    # Bounced: outbound sends whose delivery-failure notice was detected by
    # the inbox sync (mailer-daemon pattern match — see email_inbox.py).
    bounced = await conn.fetchval(
        f"""
        SELECT COUNT(*) FROM email_messages
        WHERE direction='outbound' AND bounced_at IS NOT NULL {msg_filter}
        """,
        *params,
    )

    # Unsubscribed: contacts who clicked either unsubscribe link — the 1:1
    # outreach one (email_opted_out) or the newsletter one (contacts.newsletter
    # going false, tracked via newsletter_opted_out_at) — counted by when they
    # opted out (not when they were originally emailed). The two opt-out lists
    # stay independent for send-blocking purposes (see email_tracking.py), but
    # for this all-up "email channel" rate a click on either link counts.
    unsub_filter = "AND opted_out_at >= $1" if since else ""
    unsubscribed = await conn.fetchval(
        f"""
        SELECT COUNT(*) FROM (
            SELECT GREATEST(email_opted_out_at, newsletter_opted_out_at) AS opted_out_at
            FROM contacts
            WHERE email_opted_out = true OR newsletter_opted_out_at IS NOT NULL
        ) opted_out
        WHERE opted_out_at IS NOT NULL {unsub_filter}
        """,
        *params,
    )

    return {
        "total_sent":       total_sent   or 0,
        "initial_sent":     initial_sent or 0,
        "replied":          replied or 0,
        "reply_rate":       _pct(replied, initial_sent),
        "abr":              _pct(booked_total, initial_sent),
        "booked":           booked_total or 0,
        "opened":           opened or 0,
        "open_rate":        _pct(opened, initial_sent),
        "bounced":          bounced or 0,
        "bounce_rate":      _pct(bounced, total_sent),
        "unsubscribed":     unsubscribed or 0,
        "unsubscribe_rate": _pct(unsubscribed, initial_sent),
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
        email_all      = await _email_metrics(conn)
        email_period   = await _email_metrics(conn, since)

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
        "email": {
            "all_time": email_all,
            "period":   email_period,
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
        sms         = await _sms_metrics(conn, None if all_time else _since(days))
        email       = await _email_metrics(conn, None if all_time else _since(days))
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

    # Funnel is channel-agnostic — cold calling (sheets) + SMS (DB) combined
    # at every stage, not cold-calling-only. Shows/closes are already
    # cross-channel (logged manually in the Sales Performance Tracker
    # regardless of source), so those two are untouched.
    #
    # "Booked" is the one stage that can't just be calling+SMS summed: some
    # booked appointments come from channels this OS doesn't track at all
    # (e.g. DM campaigns), so a bottom-up sum would under-count. discovery_calls
    # is the manually-logged, authoritative cross-channel total from the Sales
    # Performance Tracker — same source Sales Statistics' "Appointments Booked"
    # already uses — so use that instead of sheet_appointments_booked + sms.booked.
    dialed   = _sheet_stat(sales, "sheet_calls_made",       days) + sms["contacted"] + email["initial_sent"]
    answered = _sheet_stat(sales, "sheet_calls_answered",   days) + sms["replied"]      + email["replied"]
    pitched  = _sheet_stat(sales, "sheet_contacts_reached", days) + sms["engaged"]
    booked   = _sheet_stat(sales, "discovery_calls",        days)

    return {
        "funnel": {
            "total_leads": ((sales.get("sheet_calls_made") or 0) + (total_leads or 0)) if all_time else (total_leads or 0),
            "dialed":   dialed,
            "answered": answered,
            "pitched":  pitched,
            "booked":   booked,
            "shows":    _sheet_stat(sales, "shows",  days),
            "closes":   _sheet_stat(sales, "closes", days),
        },
        "by_grade":       by_grade,
        "top_states":     [{"state": r["state"], "cnt": r["cnt"]} for r in state_rows],
        "new_this_week":  new_week  or 0,
        "new_this_month": new_month or 0,
    }


@router.get("/analytics/sales")
async def sales_stats(days: int = 0):
    pool  = await get_pool()
    stats = _load_sales_stats()

    async with pool.acquire() as conn:
        total_leads = await conn.fetchval("SELECT COUNT(*) FROM contacts")

    discovery = _sheet_stat(stats, "discovery_calls", days)
    closes    = _sheet_stat(stats, "closes",           days)
    revenue   = _sheet_stat(stats, "total_revenue",    days)
    shows     = _sheet_stat(stats, "shows",            days)

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
        "total_revenue":     revenue,
        "avg_deal_size":     round(revenue / closes) if closes else 0,
        "shows":             shows,
        "sheet_sync":        sheet_sync,
    }




