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


def _stat_is_stale(iso_ts: str, days: int) -> bool:
    try:
        last_changed = datetime.fromisoformat(iso_ts)
        if last_changed.tzinfo is None:
            last_changed = last_changed.replace(tzinfo=timezone.utc)
    except ValueError:
        return True
    return datetime.now(timezone.utc) - last_changed > timedelta(days=days)


# Cold-calling fields the Sheets Digest breaks out per-day in
# sales_stats.json["daily"] (see _calling_metrics_for_campaign) — the only
# granularity fine enough to answer "how many today", since the digest's
# other buckets are fixed 7d/30d/all-time snapshots.
_DAILY_FIELD_MAP = {
    "sheet_calls_made":          "calls_made",
    "sheet_calls_answered":      "calls_answered",
    "sheet_contacts_reached":    "contacts_reached",
    "sheet_resonations":         "resonations",
    "sheet_appointments_booked": "appointments_booked",
}


def _sheet_stat(stats: dict, base_key: str, days: int) -> int:
    """Return the right period bucket from sales_stats.json.
    days=0 → all-time (base_key)
    days=1 → today's entry in the per-day breakdown (base_key in
             _DAILY_FIELD_MAP only — there's no base_key_1d bucket)
    days=7 → base_key_7d, falling back to 0
    days=30 → base_key_30d, falling back to 0

    Cold-calling ("sheet_"-prefixed) period buckets are a snapshot from
    whenever the Cold Calling Metrics Google Sheet was last actually read —
    sheets-digest only re-reads it when it's been edited in the last 24h
    (see executive-assistant/.claude/skills/sheets-digest/SKILL.md), so an
    idle sheet leaves these numbers frozen indefinitely rather than rolling
    forward. Without this guard, a bucket computed once (e.g. "30 calls in
    the last 7 days" as of the sheet's last edit) keeps getting served as
    "last 7 days" forever, long after those calls have aged out of the real
    window — that's exactly the bug that produced a stale "30" on a genuine
    0-call week. Once the snapshot is older than the window itself, none of
    the calls it counted can still fall inside that window, so it decays to
    0 instead of displaying stale data as if it were current. See
    `sheet_data_last_changed`, set in routers/agents.py's update_os_stats
    handler only when fresh sheet_* data actually comes in (unlike
    `last_sheet_sync`, which bumps on every digest run including no-ops).
    """
    if days == 0:
        return stats.get(base_key, 0) or 0
    if days == 1 and base_key in _DAILY_FIELD_MAP:
        today_key = datetime.now(timezone.utc).date().isoformat()
        day_fields = (stats.get("daily") or {}).get(today_key) or {}
        return day_fields.get(_DAILY_FIELD_MAP[base_key], 0) or 0
    if base_key.startswith("sheet_"):
        last_changed = stats.get("sheet_data_last_changed")
        if not last_changed or _stat_is_stale(last_changed, days):
            return 0
    suffix = f"_{days}d"
    return stats.get(f"{base_key}{suffix}", 0) or 0


def _pct(num, denom) -> float:
    if not denom:
        return 0.0
    return round(num / denom * 100, 1)


# contacts.state is free text pulled from whatever a given lead-source scrape
# wrote — the same state ends up stored as both a full name ("Florida") and
# an abbreviation ("FL") depending on which run touched it, which used to
# split one state's count into two separate Top States rows. Normalize both
# forms to the full name before aggregating (see _normalize_state below).
_US_STATE_ABBR = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri",
    "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
    "DC": "District of Columbia",
}


def _normalize_state(raw: str) -> str:
    s = (raw or "").strip()
    return _US_STATE_ABBR.get(s.upper(), s)


def _last_sheet_sync(stats: dict):
    ts = stats.get("last_sheet_sync")
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


async def _app_booked_count(conn, stats: dict, days: int) -> int:
    """
    Appointments booked through the app itself (routers/appointments.py's
    POST /appointment-reminders — Inbox/CRM/Dialer bookings) that aren't yet
    reflected in the manually-synced Sales Performance Tracker Sheet
    (sales_stats.json's discovery_calls). Added on top of that sheet figure
    everywhere "Booked" is a cross-channel total, so a booking made in the
    app shows up immediately instead of waiting for (or risking a double
    count against) the next manual sheet sync.

    Only counts app bookings created *after* the sheet was last synced —
    anything before that point may already be reflected in discovery_calls,
    since the sheet is manually maintained and could include app-sourced
    bookings a rep also logged there by hand. Canceled appointments never
    count as a win.
    """
    cutoff = _last_sheet_sync(stats) or datetime.min.replace(tzinfo=timezone.utc)
    if days:
        cutoff = max(cutoff, _since(days))
    return await conn.fetchval(
        "SELECT COUNT(*) FROM appointment_reminders WHERE status != 'canceled' AND created_at >= $1",
        cutoff,
    ) or 0


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


def _calling_metrics_for_campaign(stats: dict, periods: list, since=None) -> dict:
    """
    Same source and formulas as _calling_metrics(), but summed over the
    campaign's active date range(s) from the Sheets Digest's per-day
    breakdown (`sales_stats.json["daily"]`) instead of the fixed 7d/30d/
    all-time buckets — a reactivated campaign can have multiple periods, so
    this sums every day that falls inside ANY of them (each `ended_at is
    None` period treated as "through today"), correctly excluding days
    another campaign was active in between.

    `since`, when given, further narrows to days on/after it (the Analytics
    tab's Today/7D/30D/All Time toggle, applied on top of the campaign's own
    date range) — unlike the SMS/email campaign metrics, this data is
    already day-granular, so unlike stage-boolean SMS metrics there's no
    accuracy gap here.
    """
    daily = stats.get("daily") or {}
    today = datetime.now(timezone.utc).date()
    since_date = since.date() if since else None

    def _in_any_period(day) -> bool:
        if since_date and day < since_date:
            return False
        for started_at, ended_at in periods:
            start_date = started_at.date() if hasattr(started_at, "date") else started_at
            end_date = (ended_at.date() if hasattr(ended_at, "date") else ended_at) if ended_at else today
            if start_date <= day <= end_date:
                return True
        return False

    totals = {"calls_made": 0, "calls_answered": 0, "contacts_reached": 0, "resonations": 0, "appointments_booked": 0}
    for date_key, day_fields in daily.items():
        try:
            day = datetime.strptime(date_key, "%Y-%m-%d").date()
        except ValueError:
            continue
        if not isinstance(day_fields, dict) or not _in_any_period(day):
            continue
        for key in totals:
            totals[key] += day_fields.get(key, 0) or 0

    return {
        "total":           totals["calls_made"],
        "answer_rate":     _pct(totals["calls_answered"], totals["calls_made"]),
        "pitch_rate":      _pct(totals["contacts_reached"], totals["calls_made"]),
        "resonation_rate": _pct(totals["resonations"], totals["contacts_reached"]),
        "pitches":         totals["contacts_reached"],
        "resonations":     totals["resonations"],
        "abr":             _pct(totals["appointments_booked"], totals["calls_made"]),
        "booked":          totals["appointments_booked"],
    }


async def _sms_metrics(conn, since=None, campaign_id=None) -> dict:
    """
    Return SMS funnel metrics. If since is None, returns all-time. If
    campaign_id is given, a campaign is already its own time boundary (see
    campaigns.py) — since further narrows within it (the Analytics tab's
    Today/7D/30D/All Time toggle, applied on top of the campaign's own
    date range).

    Replied/Primed/Engaged/Interested are read straight off sms_conversations'
    checkboxes — NOT recomputed from message counts here. Replied is auto-set
    the moment any inbound reply lands (sms.py::_recompute_stage_flags);
    Primed/Engaged/Interested/DM Reached are exclusively manual. Any of them
    can be corrected by hand from the Inbox (POST /inbox/contact/{contact_id}
    /stage in email_inbox.py) — once touched manually, the checkbox is
    authoritative and stops tracking the raw reply count. Whenever a
    checkbox is actually set, its stage_{x}_at column is stamped at the same
    time (see db.py's migration comment) — `since` narrows Replied/Primed/
    Engaged/Interested using that column, not the boolean alone, so it's an
    accurate answer to "how many became this stage in this period", not a
    proxy. A conversation whose flag was set before these timestamp columns
    existed (or via the auto-reply path before this was added) simply won't
    match a period filter, which is the correct behavior — there's no
    accurate historical "when" to recover for those.

    DM Reached is the one stage that also counts by activity, not just by
    when it was first flagged: a conversation reached on an earlier day
    still counts toward this period if it got fresh SMS activity (either
    direction) within it. Most of a rep's day-to-day SMS work is following
    up with people already flagged reached, not freshly flagging new ones —
    narrowing DM Reached to stage_dm_reached_at alone would only answer "how
    many became newly reached today", undercounting what "Total Reached"
    actually means for a working day of outreach.

    Total Outreach counts each prospect's FIRST-EVER non-automated outbound
    message only — MIN(sent_at) per phone across all history, not every
    message in the conversation. A rep's later sequence steps
    (curiosity_opener/relevance/guarantee/ask/cta only fire after the
    phone's first message already got a reply, per sms.py's docstring) and
    Inbox replies to an ongoing conversation are real activity but not new
    outreach — they'd otherwise double (or 5x-, for a full sequence) count
    the same prospect as if each step were a new person contacted. `since`
    narrows to prospects whose first-ever message fell in this window,
    still excluding is_automated (no_show/cancel/dm_followup/reminder
    sequence touches, which are follow-up on an existing relationship, not
    fresh outreach, and shouldn't set anyone's "first contact" moment
    anyway). Contacted stays the broader "distinct phones touched at all in
    this window" — used as the denominator for reply/DM-reached/etc. rates,
    where every touch in the window is a legitimate opportunity to reply,
    not just the first one.

    Booked/Not Interested are windowed by sms_conversations.updated_at
    (bumped when disposition is set) — an approximation, since updated_at
    bumps on other edits too, not just a disposition change, but a
    disposition set is rare enough after the fact that this is close enough.
    """
    if campaign_id is not None:
        contacted_row = await conn.fetchrow(
            """
            SELECT COUNT(DISTINCT sm.phone) FILTER (WHERE sm.direction = 'outbound') AS contacted
            FROM sms_messages sm
            JOIN sms_conversations sc ON sc.phone = sm.phone
            WHERE sc.campaign_id = $1 AND NOT sm.is_automated
            """ + (" AND sm.sent_at >= $2" if since else ""),
            *([campaign_id, since] if since else [campaign_id]),
        )
        # Total Outreach — each phone's first-ever non-automated outbound
        # message in this campaign only, not every message (see
        # _sms_metrics' module docstring for why).
        total_outreach = await conn.fetchval(
            """
            SELECT COUNT(*) FROM (
                SELECT sm.phone, MIN(sm.sent_at) AS first_sent
                FROM sms_messages sm
                JOIN sms_conversations sc ON sc.phone = sm.phone
                WHERE sc.campaign_id = $1 AND sm.direction = 'outbound' AND NOT sm.is_automated
                GROUP BY sm.phone
            ) first_touch
            WHERE $2::timestamptz IS NULL OR first_sent >= $2
            """,
            campaign_id, since,
        )
        # Narrowed by stage_{x}_at, now that it exists (stamped in
        # email_inbox.py's set_contact_stage()) — pre-existing conversations
        # set before these timestamp columns existed just won't match a
        # period filter, which is correct (no accurate historical "when" for
        # those). $2::timestamptz IS NULL means "no period filter" (All Time).
        #
        # DM Reached and Replied are the two exceptions to the "narrow to
        # stage_{x}_at" rule: they also count a conversation that first
        # reached that milestone on an earlier day but has fresh matching
        # activity in this period. stage_{x}_at alone answers "newly reached
        # this milestone in this period", which undercounts what these two
        # actually mean day to day — most of a rep's SMS work on a given day
        # is following up with (or getting replies from) people already
        # past this milestone, not freshly reaching it for the first time,
        # and that ongoing activity is still real in the period. Replied
        # specifically needs a fresh INBOUND message (not just any
        # activity) — stage_replied_at only ever stamps on someone's FIRST
        # reply ever (see sms.py::_recompute_stage_flags), so without this
        # fallback, anyone who'd already replied on an earlier day showed 0
        # replies today no matter how many times they replied again today.
        #
        # Primed/Engaged/Interested need the same fallback for a different
        # reason: stage_{x}_at only started getting stamped the moment that
        # tracking shipped (see email_inbox.py::set_contact_stage) — every
        # one of these flags set by hand BEFORE that (which, for any
        # campaign older than a few hours, is effectively all of them) has
        # stage_{x}_at = NULL forever, since there's no way to recover when
        # it actually happened. Without the fallback, a campaign's real
        # Primed/Engaged/Interested activity was invisible under every
        # period filter except All Time — confirmed live: a 30-day window
        # covering virtually the whole campaign's history still showed 0%
        # for both. Any SMS activity on the conversation in the period is
        # "this milestone is still current" evidence, same reasoning as
        # DM Reached.
        stage_row = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE stage_replied      AND ($2::timestamptz IS NULL
                                                                OR stage_replied_at    >= $2
                                                                OR EXISTS (SELECT 1 FROM sms_messages sm WHERE sm.phone = sc.phone AND sm.direction = 'inbound' AND sm.sent_at >= $2))) AS replied,
                COUNT(*) FILTER (WHERE stage_dm_reached   AND ($2::timestamptz IS NULL
                                                                OR stage_dm_reached_at >= $2
                                                                OR EXISTS (SELECT 1 FROM sms_messages sm WHERE sm.phone = sc.phone AND sm.sent_at >= $2))) AS dm_reached,
                COUNT(*) FILTER (WHERE stage_primed       AND ($2::timestamptz IS NULL
                                                                OR stage_primed_at     >= $2
                                                                OR EXISTS (SELECT 1 FROM sms_messages sm WHERE sm.phone = sc.phone AND sm.sent_at >= $2))) AS primed,
                COUNT(*) FILTER (WHERE stage_engaged      AND ($2::timestamptz IS NULL
                                                                OR stage_engaged_at    >= $2
                                                                OR EXISTS (SELECT 1 FROM sms_messages sm WHERE sm.phone = sc.phone AND sm.sent_at >= $2))) AS engaged,
                COUNT(*) FILTER (WHERE stage_interested   AND ($2::timestamptz IS NULL
                                                                OR stage_interested_at >= $2
                                                                OR EXISTS (SELECT 1 FROM sms_messages sm WHERE sm.phone = sc.phone AND sm.sent_at >= $2))) AS interested,
                COUNT(*) FILTER (WHERE disposition = 'booked'         AND ($2::timestamptz IS NULL OR updated_at >= $2)) AS booked,
                COUNT(*) FILTER (WHERE disposition = 'not_interested' AND ($2::timestamptz IS NULL OR updated_at >= $2)) AS not_interested
            FROM sms_conversations sc
            WHERE campaign_id = $1
            """,
            campaign_id, since,
        )
        contacted = contacted_row["contacted"]
        replied, primed, engaged, interested = stage_row["replied"], stage_row["primed"], stage_row["engaged"], stage_row["interested"]
        dm_reached = stage_row["dm_reached"]
        booked, not_interested = stage_row["booked"], stage_row["not_interested"]
        return {
            "total_outreach":     total_outreach or 0,
            "contacted":          contacted or 0,
            "replied":            replied or 0,
            "reply_rate":         _pct(replied, contacted),
            "dm_reached":         dm_reached or 0,
            "dm_reached_rate":    _pct(dm_reached, contacted),
            "primed":             primed or 0,
            "primed_rate":        _pct(primed, contacted),
            "engaged":            engaged or 0,
            "engaged_rate":       _pct(engaged, contacted),
            "interested":         interested or 0,
            "interested_rate":    _pct(interested, contacted),
            "booked":             booked or 0,
            "abr":                _pct(booked, contacted),
            "not_interested":     not_interested or 0,
            "not_interested_rate": _pct(not_interested, contacted),
        }

    # AND NOT is_automated excludes no_show/cancel/dm_followup/reminder
    # sequence sends from outreach-volume metrics — those are follow-up on
    # an existing relationship, not fresh outreach (see
    # routers/sms.py::_store_message).
    msg_filter = "AND NOT is_automated" + (" AND sent_at >= $1" if since else "")
    params = [since] if since else []

    # Windowed by updated_at (bumped when disposition is set), not created_at
    # (when the conversation first started) — same fix as _email_metrics
    # below, whose comment explains why: a booking that lands in this period
    # must show up even if the contact was first texted before the window
    # started. Using created_at here meant a booking on a conversation that
    # started outside the window never counted, no matter how recent the
    # booking itself was.
    booked_filter = "AND updated_at >= $1" if since else ""

    # Total Outreach — each phone's first-ever non-automated outbound
    # message only (MIN(sent_at) across all history), not every message —
    # see module docstring for why. $1::timestamptz IS NULL means "no
    # period filter" (All Time — every phone that's ever gotten a first
    # message counts).
    total_outreach = await conn.fetchval(
        """
        SELECT COUNT(*) FROM (
            SELECT phone, MIN(sent_at) AS first_sent
            FROM sms_messages
            WHERE direction='outbound' AND NOT is_automated
            GROUP BY phone
        ) first_touch
        WHERE $1::timestamptz IS NULL OR first_sent >= $1
        """,
        since,
    )

    contacted = await conn.fetchval(
        f"SELECT COUNT(DISTINCT phone) FROM sms_messages WHERE direction='outbound' {msg_filter}",
        *params,
    )

    # Narrowed by stage_{x}_at (stamped in email_inbox.py's
    # set_contact_stage() the moment each checkbox is set — see db.py's
    # migration comment), with an activity fallback for the reasons
    # explained at each metric below.
    # Replied also counts a conversation whose FIRST-ever reply was on an
    # earlier day but got a fresh INBOUND message in this period —
    # stage_replied_at only ever stamps once, on someone's first reply ever
    # (see sms.py::_recompute_stage_flags), so without this fallback anyone
    # who'd already replied before showed 0 replies today no matter how
    # many times they replied again today.
    if since:
        replied = await conn.fetchval(
            """
            SELECT COUNT(*) FROM sms_conversations sc
            WHERE stage_replied
              AND (stage_replied_at >= $1
                   OR EXISTS (SELECT 1 FROM sms_messages sm WHERE sm.phone = sc.phone AND sm.direction = 'inbound' AND sm.sent_at >= $1))
            """,
            since,
        )
    else:
        replied = await conn.fetchval("SELECT COUNT(*) FROM sms_conversations WHERE stage_replied")
    # DM Reached also counts a conversation reached on an earlier day that
    # got fresh SMS activity (either direction) in this period — most of a
    # rep's day-to-day SMS work is following up with people already flagged
    # reached, not freshly flagging new ones, and that follow-up is still a
    # real "reach" in the period. stage_dm_reached_at alone only answers
    # "newly reached this period", which undercounts what Total Reached
    # means for an active day of outreach.
    if since:
        dm_reached = await conn.fetchval(
            """
            SELECT COUNT(*) FROM sms_conversations sc
            WHERE stage_dm_reached
              AND (stage_dm_reached_at >= $1
                   OR EXISTS (SELECT 1 FROM sms_messages sm WHERE sm.phone = sc.phone AND sm.sent_at >= $1))
            """,
            since,
        )
    else:
        dm_reached = await conn.fetchval("SELECT COUNT(*) FROM sms_conversations WHERE stage_dm_reached")

    # Primed/Engaged/Interested need the same fallback as DM Reached, for a
    # different reason: stage_{x}_at only started getting stamped the
    # moment that tracking shipped (see email_inbox.py::set_contact_stage)
    # — every one of these flags set by hand before that has stage_{x}_at =
    # NULL forever, with no way to recover when it actually happened.
    # Without this fallback, real Primed/Engaged/Interested activity was
    # invisible under every period filter except All Time — confirmed live:
    # a 30-day window covering virtually a whole campaign's history still
    # showed 0% for both. Any SMS activity on the conversation in the
    # period is "this milestone is still current" evidence.
    async def _stage_count_with_activity_fallback(column: str):
        if not since:
            return await conn.fetchval(f"SELECT COUNT(*) FROM sms_conversations WHERE {column}")
        return await conn.fetchval(
            f"""
            SELECT COUNT(*) FROM sms_conversations sc
            WHERE {column}
              AND ({column}_at >= $1
                   OR EXISTS (SELECT 1 FROM sms_messages sm WHERE sm.phone = sc.phone AND sm.sent_at >= $1))
            """,
            since,
        )

    primed      = await _stage_count_with_activity_fallback("stage_primed")
    engaged     = await _stage_count_with_activity_fallback("stage_engaged")
    interested  = await _stage_count_with_activity_fallback("stage_interested")

    booked = await conn.fetchval(
        f"SELECT COUNT(*) FROM sms_conversations WHERE disposition='booked' {booked_filter}",
        *params,
    )

    not_interested = await conn.fetchval(
        f"SELECT COUNT(*) FROM sms_conversations WHERE disposition='not_interested' {booked_filter}",
        *params,
    )

    return {
        "total_outreach":     total_outreach or 0,
        "contacted":          contacted or 0,
        "replied":            replied or 0,
        "reply_rate":         _pct(replied, contacted),
        "dm_reached":         dm_reached or 0,
        "dm_reached_rate":    _pct(dm_reached, contacted),
        "primed":             primed or 0,
        "primed_rate":        _pct(primed, contacted),
        "engaged":            engaged or 0,
        "engaged_rate":       _pct(engaged, contacted),
        "interested":         interested or 0,
        "interested_rate":    _pct(interested, contacted),
        "booked":             booked or 0,
        "abr":                _pct(booked, contacted),
        "not_interested":     not_interested or 0,
        "not_interested_rate": _pct(not_interested, contacted),
    }


async def _email_metrics(conn, since=None, campaign_id=None) -> dict:
    """
    Email funnel metrics — sent / reply rate / booked.
    Unlike SMS, email has no stage sequence (no equivalent of auto_opener →
    curiosity_opener → ... → cta), so this only tracks what the data
    actually supports: outbound sends, whether the contact replied, and
    conversations marked booked.

    If campaign_id is given, a campaign is already its own time boundary,
    same as _sms_metrics — since further narrows within it (the Analytics
    tab's Today/7D/30D/All Time toggle, applied on top of the campaign's own
    date range). Unlike SMS, every one of these metrics is genuinely
    timestamped (email_messages.sent_at, email_conversations.updated_at),
    so since narrows all of them accurately — no boolean-with-no-history
    limitation here. Sent/reply/open/bounce counts are scoped by
    email_messages.campaign_id (tagged per message at send time — see
    email_inbox.py/integrations.py), not by thread, so a thread with send
    history predating the campaign doesn't inflate its counts. Booked stays
    scoped by the conversation-level tag (email_conversations.campaign_id),
    same as SMS.
    """
    if campaign_id is not None:
        msg_filter = "AND NOT is_test AND NOT is_automated AND campaign_id = $1" + (" AND sent_at >= $2" if since else "")
        params = [campaign_id, since] if since else [campaign_id]
        booked_filter = "AND campaign_id = $1" + (" AND updated_at >= $2" if since else "")
        unsub_filter = ""  # unsubscribes are tracked on contacts, not per-conversation — no clean campaign scope
        unsub_params = []
    else:
        # is_test excludes diagnostic sends (e.g. /newsletter/test-send, used to
        # verify the open-tracking pixel end-to-end) — those are self-opened by
        # whoever ran the test, which skews open rate badly against a real
        # campaign's small early denominator if left in. is_automated excludes
        # no_show/cancel/reminder sequence sends — follow-up on an existing
        # relationship, not fresh outreach.
        msg_filter = "AND NOT is_test AND NOT is_automated" + (" AND sent_at >= $1" if since else "")
        params = [since] if since else []
        booked_filter = "AND updated_at >= $1" if since else ""
        unsub_filter = "AND opted_out_at >= $1" if since else ""
        unsub_params = params

    total_sent = await conn.fetchval(
        f"SELECT COUNT(*) FROM email_messages WHERE direction='outbound' {msg_filter}",
        *params,
    )

    initial_sent = await conn.fetchval(
        f"SELECT COUNT(DISTINCT email) FROM email_messages WHERE direction='outbound' {msg_filter}",
        *params,
    )

    # "Total Outreach" equivalent — each recipient's first-ever non-test,
    # non-automated outbound email only (MIN(sent_at) across all history),
    # not every email sent to them in this window. Same principle as
    # _sms_metrics' total_outreach — see that docstring for why: a
    # follow-up/newsletter send to someone already emailed before isn't a
    # new prospect reached. initial_sent above stays the broader "distinct
    # recipients touched at all in this window" — still used as the rate
    # denominator, since a reply/open in this window is a legitimate
    # outcome of ANY email sent then, not just their first ever.
    first_contact_filter = "AND campaign_id = $1" if campaign_id is not None else ""
    first_contact_params = [campaign_id] if campaign_id is not None else []
    total_outreach = await conn.fetchval(
        f"""
        SELECT COUNT(*) FROM (
            SELECT email, MIN(sent_at) AS first_sent
            FROM email_messages
            WHERE direction='outbound' AND NOT is_test AND NOT is_automated {first_contact_filter}
            GROUP BY email
        ) first_touch
        WHERE $%d::timestamptz IS NULL OR first_sent >= $%d
        """ % (len(first_contact_params) + 1, len(first_contact_params) + 1),
        *first_contact_params, since,
    )

    # Replied: distinct contacts who received an outbound email in this
    # window AND have at least one inbound message on the same thread in
    # this same window. The inbound side used to have no date bound at
    # all, so an outbound sent this window to a thread that got any inbound
    # reply at any point in its history — even months earlier, unrelated to
    # this send — counted as "replied", inflating reply_rate for narrow
    # periods. Bounded to match msg_filter's outbound-side window, same
    # principle as _sms_metrics' equivalent check above.
    replied = await conn.fetchval(
        f"""
        SELECT COUNT(DISTINCT out.email)
        FROM email_messages out
        WHERE out.direction='outbound' {msg_filter.replace('sent_at', 'out.sent_at')}
        AND EXISTS (
            SELECT 1 FROM email_messages inb
            WHERE inb.thread_id = out.thread_id AND inb.direction='inbound'
            {" AND inb.sent_at >= $1" if since else ""}
        )
        """,
        *params,
    )

    # Windowed by updated_at (bumped when disposition is set — see
    # email_inbox.py's close-conversation handler), not created_at (when the
    # thread first started), so a booking that lands in this period shows up
    # here even if the contact was first emailed before the window started.
    booked_total = await conn.fetchval(
        f"SELECT COUNT(*) FROM email_conversations WHERE disposition='booked' {booked_filter}",
        *params,
    )

    not_interested = await conn.fetchval(
        f"SELECT COUNT(*) FROM email_conversations WHERE disposition='not_interested' {booked_filter}",
        *params,
    )

    # Opened (confirmed): only counting a pixel fire more than 2
    # minutes after send. Apple Mail Privacy Protection fetches every
    # tracking pixel within seconds of delivery regardless of whether a
    # human ever reads the email, so a very fast open is far more likely an
    # auto-prefetch than a real read. Heuristic, not a guarantee — a
    # genuinely fast human open gets miscounted as prefetch, and a slow
    # prefetch could still land here — but it's a meaningfully better human-
    # read signal than the raw pixel-fired count alone.
    confirmed_opened = await conn.fetchval(
        f"""
        SELECT COUNT(DISTINCT email) FROM email_messages
        WHERE direction='outbound' AND opened_at IS NOT NULL
        AND opened_at - sent_at > interval '2 minutes' {msg_filter}
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
    unsubscribed = await conn.fetchval(
        f"""
        SELECT COUNT(*) FROM (
            SELECT GREATEST(email_opted_out_at, newsletter_opted_out_at) AS opted_out_at
            FROM contacts
            WHERE email_opted_out = true OR newsletter_opted_out_at IS NOT NULL
        ) opted_out
        WHERE opted_out_at IS NOT NULL {unsub_filter}
        """,
        *unsub_params,
    )

    return {
        "total_sent":       total_sent   or 0,
        "initial_sent":     initial_sent or 0,
        "total_outreach":   total_outreach or 0,
        "replied":          replied or 0,
        "reply_rate":       _pct(replied, initial_sent),
        "abr":              _pct(booked_total, initial_sent),
        "booked":           booked_total or 0,
        "not_interested":      not_interested or 0,
        "not_interested_rate": _pct(not_interested, initial_sent),
        "opened":           confirmed_opened or 0,
        "open_rate":        _pct(confirmed_opened, initial_sent),
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
        # Funnel's total_leads was previously an unconditional COUNT(*) --
        # ignored the period toggle entirely, so "Today" showed the same
        # lifetime total as "All Time". Scope it to leads created within the
        # selected window, same pattern as new_week/new_month below.
        total_leads = await conn.fetchval(
            "SELECT COUNT(*) FROM contacts" if all_time
            else "SELECT COUNT(*) FROM contacts WHERE created_at >= $1",
            *([] if all_time else [_since(days)]),
        )
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
        # Raw GROUP BY state used to split the same state into two rows
        # whenever it was stored inconsistently (e.g. "Florida" from one
        # scrape vs "FL" from another) — fetch every distinct value
        # ungrouped-by-abbreviation and normalize in Python below instead of
        # a giant SQL CASE expression.
        state_rows_raw = await conn.fetch(
            """
            SELECT state, COUNT(*) AS cnt
            FROM contacts
            WHERE state IS NOT NULL AND state != ''
            GROUP BY state
            """
        )
        app_booked = await _app_booked_count(conn, sales, days)

    by_grade = [
        {"grade": r["grade"], "cnt": r["cnt"], "booked": r["booked"], "book_rate": _pct(r["booked"], r["cnt"])}
        for r in grade_rows
    ]

    state_counts: dict[str, int] = {}
    for r in state_rows_raw:
        norm = _normalize_state(r["state"])
        state_counts[norm] = state_counts.get(norm, 0) + r["cnt"]
    top_states = sorted(
        ({"state": s, "cnt": c} for s, c in state_counts.items()),
        key=lambda x: x["cnt"], reverse=True,
    )[:8]

    # Funnel is channel-agnostic — cold calling (sheets) + SMS (DB) + email
    # (DB) combined at every stage, not cold-calling-only. Shows/closes are
    # already cross-channel (logged manually in the Sales Performance
    # Tracker regardless of source), so those two are untouched.
    #
    # "Pitched" (the reached stage) sums calls reached + SMS's own DM
    # Reached stage — not the later Engaged stage, which undercounts what
    # "reached" means — + confirmed email opens. Same fix as
    # dashboard.py::summary's total_reached.
    #
    # "Booked" is the one stage that can't just be calling+SMS summed: some
    # booked appointments come from channels this OS doesn't track at all
    # (e.g. DM campaigns), so a bottom-up sum would under-count. discovery_calls
    # is the manually-logged, authoritative cross-channel total from the Sales
    # Performance Tracker — same source Sales Statistics' "Appointments Booked"
    # already uses — so use that as the base, plus app_booked (bookings made
    # in the app itself, not yet reflected in that sheet — see
    # _app_booked_count) instead of sheet_appointments_booked + sms.booked.
    # "Dialed" (labeled "Total Outreach" in the funnel UI) uses SMS/email's
    # total_outreach — each prospect's first-ever message only, not
    # sms["contacted"]/email["initial_sent"] (every distinct recipient
    # touched in the window, including follow-ups) — see
    # _sms_metrics'/_email_metrics' docstrings for why that distinction
    # matters: a rep's later sequence steps or a newsletter to an existing
    # contact aren't new prospects reached.
    dialed   = _sheet_stat(sales, "sheet_calls_made",       days) + sms["total_outreach"] + email["total_outreach"]
    answered = _sheet_stat(sales, "sheet_calls_answered",   days) + sms["replied"]      + email["replied"]
    pitched  = _sheet_stat(sales, "sheet_contacts_reached", days) + sms["dm_reached"] + email["opened"]
    booked   = _sheet_stat(sales, "discovery_calls",        days) + app_booked

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
        "top_states":     top_states,
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
        # Closed ÷ shows (who actually showed up), not ÷ discovery calls
        # booked — a booked call that no-shows was never a chance to close,
        # so counting it in the denominator understated the real close
        # rate. Matches the funnel widget's own close-rate math elsewhere
        # in AnalyticsPanel.jsx, which already divides by shows.
        "close_rate":        _pct(closes, shows),
        "total_revenue":     revenue,
        "avg_deal_size":     round(revenue / closes) if closes else 0,
        "shows":             shows,
        "sheet_sync":        sheet_sync,
    }


@router.get("/analytics/campaign/{campaign_id}")
async def campaign_analytics(campaign_id: int, days: int = 0):
    """`days` narrows the campaign's own metrics with the Analytics tab's
    Today/7D/30D/All Time toggle (days=0 means no narrowing — the whole
    campaign). See _sms_metrics/_email_metrics/_calling_metrics_for_campaign
    docstrings for what can and can't be narrowed accurately per channel."""
    since = _since(days) if days else None
    pool = await get_pool()
    async with pool.acquire() as conn:
        campaign = await conn.fetchrow("SELECT * FROM campaigns WHERE id = $1", campaign_id)
        if not campaign:
            return {"error": "Campaign not found"}
        period_rows = await conn.fetch(
            "SELECT started_at, ended_at FROM campaign_periods WHERE campaign_id = $1 ORDER BY started_at",
            campaign_id,
        )
        periods = [{"started_at": p["started_at"], "ended_at": p["ended_at"]} for p in period_rows]

        if campaign["channel"] == "sms":
            metrics = await _sms_metrics(conn, since=since, campaign_id=campaign_id)
        elif campaign["channel"] == "email":
            metrics = await _email_metrics(conn, since=since, campaign_id=campaign_id)
        else:
            sales = _load_sales_stats()
            metrics = _calling_metrics_for_campaign(
                sales, [(p["started_at"], p["ended_at"]) for p in period_rows], since=since,
            )

    return {
        "campaign": {
            "id": campaign["id"], "name": campaign["name"], "channel": campaign["channel"],
            "created_at": campaign["created_at"],
            "is_active": any(p["ended_at"] is None for p in periods),
        },
        "periods": periods,
        "metrics": metrics,
    }




