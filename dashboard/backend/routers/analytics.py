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
from routers.content_tracking import vsl_funnel, loom_outreach_funnel

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


def _os_sales_baseline(stats: dict) -> dict:
    """
    One-time carry-forward of everything the manually-maintained Sales
    Performance Tracker sheet had already logged before _os_sales_stats
    switched to computing these numbers natively from
    appointment_reminders. Without this, the switchover made discovery
    calls/shows/closes/revenue jump straight to whatever's in that table
    (which starts near-empty) and silently dropped months of pre-migration
    history. Captured once as sheet_baseline_* in sales_stats.json (see
    sheet_baseline_captured_at) and frozen forever after — sheets-digest
    no longer writes these fields, so nothing will bump the baseline again.
    Added only to all-time totals (days=0); the sheet's own historical
    figures were all-time-only too, so there's no meaningful "baseline in
    the last 7/30 days" to add to period-windowed totals.
    """
    return {
        "discovery_calls": stats.get("sheet_baseline_discovery_calls", 0) or 0,
        "shows":            stats.get("sheet_baseline_shows", 0) or 0,
        "closes":           stats.get("sheet_baseline_closes", 0) or 0,
        "total_revenue":    stats.get("sheet_baseline_total_revenue", 0) or 0,
    }


def _os_sales_baseline_cutoff(stats: dict):
    """
    The instant the frozen baseline (see _os_sales_baseline) was captured.
    Several of the sheet's last rows (e.g. Austin Treadwell, Brandon
    Crosdale, Louis Walker) were *also* re-entered natively in
    appointment_reminders once the disposition screen went live, so an
    unwindowed native count double-counts them on top of the baseline.
    Restricting the native, all-time query to rows created at/after this
    cutoff (see its use in _os_sales_stats) keeps every pre-baseline row
    on the sheet side of the ledger and every post-cutoff row (new
    bookings, and any outcome later marked on them) on the native side,
    with nothing counted twice.
    """
    ts = stats.get("sheet_baseline_captured_at")
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


async def _os_sales_stats(conn, days: int) -> dict:
    """
    OS-native sales KPIs computed straight from appointment_reminders —
    discovery_calls/shows/closes/total_revenue/avg_deal_size — replacing
    the Google-Sheet-sourced sales_stats.json fields of the same names
    (the sheets-digest skill no longer reports these; see
    executive-assistant/.claude/skills/sheets-digest/SKILL.md). All-time
    totals (days=0) get the pre-migration sheet history added back in —
    see _os_sales_baseline.

    Scoped exactly like the old _app_booked_count(): Dylan's own
    sales-pipeline appointments only — excludes a client's own lead
    appointments (booked through their portal) via the same
    (c.id IS NULL OR c.client_id IS NULL OR c.is_client_anchor) exclusion
    used elsewhere (appointments.py's list_appointments(), dialer.py's
    queue, the pipeline funnel above) — and excludes canceled appointments,
    which never count as a win or a booking.

    Each metric windows on the timestamp that actually reflects when that
    thing happened, not a single blanket cutoff: discovery_calls on
    created_at (when booked), shows on outcome_show_at (when marked),
    closes/revenue on outcome_close_at (when marked) — a close logged
    today on a call booked a month ago should count toward today's
    close-rate window, not get excluded because the booking itself is
    old. days=0 (all-time) uses _os_sales_baseline_cutoff instead of no
    window at all — the sheet's last few rows (e.g. Brandon Crosdale's
    close) were also re-entered natively once the disposition screen went
    live, so an unwindowed all-time query would double-count them on top
    of the frozen baseline; windowing on each row's own created_at/
    outcome_*_at against the cutoff naturally excludes exactly the rows
    the baseline already covers (their timestamps predate the cutoff)
    while still picking up any new booking or freshly-marked outcome.
    """
    stats = _load_sales_stats()
    since = _since(days) if days else _os_sales_baseline_cutoff(stats)
    where = (
        "ar.status != 'canceled' AND (c.id IS NULL OR c.client_id IS NULL OR c.is_client_anchor)"
    )
    join = "LEFT JOIN contacts c ON c.id = ar.contact_id"

    discovery_calls = await conn.fetchval(
        f"""
        SELECT COUNT(*) FROM appointment_reminders ar {join}
        WHERE {where}
        AND ($1::timestamptz IS NULL OR ar.created_at >= $1)
        """,
        since,
    ) or 0
    shows = await conn.fetchval(
        f"""
        SELECT COUNT(*) FROM appointment_reminders ar {join}
        WHERE {where} AND ar.outcome_show = 'show'
        AND ($1::timestamptz IS NULL OR ar.outcome_show_at >= $1)
        """,
        since,
    ) or 0
    close_row = await conn.fetchrow(
        f"""
        SELECT COUNT(*) AS closes, COALESCE(SUM(ar.pricing), 0) AS revenue
        FROM appointment_reminders ar {join}
        WHERE {where} AND ar.outcome_close = 'closed'
        AND ($1::timestamptz IS NULL OR ar.outcome_close_at >= $1)
        """,
        since,
    )
    closes  = close_row["closes"] or 0
    revenue = float(close_row["revenue"] or 0)

    if not days:
        baseline = _os_sales_baseline(stats)
        discovery_calls += baseline["discovery_calls"]
        shows           += baseline["shows"]
        closes          += baseline["closes"]
        revenue         += baseline["total_revenue"]

    return {
        "discovery_calls":   discovery_calls,
        "shows":             shows,
        "closes":            closes,
        "total_revenue":     revenue,
        "avg_deal_size":     round(revenue / closes) if closes else 0,
    }


def _load_sales_stats() -> dict:
    try:
        return json.loads(_SALES_STATS_PATH.read_text())
    except Exception:
        return {"discovery_calls": 0, "closes": 0,
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

    Booked is windowed by sms_conversations.booked_at — stamped once when a
    booking happens and never cleared, so a later disposition change (e.g.
    closing the thread as not_interested after a no-show ghosts) can't
    erase the booked credit. Not Interested still windows on updated_at
    (bumped when disposition is set) — an approximation, since updated_at
    bumps on other edits too, but a disposition set is rare enough after
    the fact that this is close enough.
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
                COUNT(*) FILTER (WHERE booked_at IS NOT NULL          AND ($2::timestamptz IS NULL OR booked_at >= $2)) AS booked,
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

    # Not Interested is windowed by updated_at (bumped when disposition is
    # set), not created_at (when the conversation first started) — same fix
    # as _email_metrics below, whose comment explains why: a disposition
    # change that lands in this period must show up even if the contact was
    # first texted before the window started. Using created_at here meant a
    # disposition change on a conversation that started outside the window
    # never counted, no matter how recent the change itself was. Booked
    # uses its own booked_at column instead (see _sms_metrics' docstring)
    # so it isn't affected by a later disposition change at all.
    booked_filter = "AND booked_at >= $1" if since else ""
    not_interested_filter = "AND updated_at >= $1" if since else ""

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
        f"SELECT COUNT(*) FROM sms_conversations WHERE booked_at IS NOT NULL {booked_filter}",
        *params,
    )

    not_interested = await conn.fetchval(
        f"SELECT COUNT(*) FROM sms_conversations WHERE disposition='not_interested' {not_interested_filter}",
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


# Contacts with a positive email reply: Email-channel stage Engaged or
# Interested, or an email conversation that booked / was marked Interested.
_POSITIVE_EMAIL_CONTACTS_SQL = """
    SELECT COUNT(*) FROM contacts c
    WHERE (
        EXISTS (SELECT 1 FROM email_contact_stages s
                WHERE s.contact_id = c.id AND (s.stage_engaged OR s.stage_interested))
        OR EXISTS (SELECT 1 FROM email_conversations ec
                   WHERE ec.contact_id = c.id AND (ec.disposition = 'interested' OR ec.booked_at IS NOT NULL))
    )
"""


async def _email_metrics(conn, since=None, campaign_id=None) -> dict:
    """
    Email funnel metrics — sent / reply rate / booked.
    Unlike SMS, email has no stage sequence (no equivalent of auto_opener →
    curiosity_opener → ... → cta), so this only tracks what the data
    actually supports: outbound sends, whether the contact replied, and
    conversations marked booked.

    Sent/opened/bounced/replied are all scoped to each recipient's ORIGINAL
    initial outbound message only (MIN(sent_at) per email address) —
    requested 2026-09-01 so a follow-up or later re-send in the same thread
    never counts as a second "sent", and an open/bounce/reply is only
    counted against that first message, not anything sent afterward. This
    replaced an earlier design where total_sent counted every outbound row
    and initial_sent/total_outreach were separate, looser figures — those
    three fields are now the same number by construction and kept for
    backward compatibility with existing callers.

    `since` is also clamped to the 'email_stats_reset_at' dialer_settings
    value (see db.py's one-time seed) — historical email data before that
    date is unreliable, so "All Time" here effectively means "since that
    date" now, not true all-time.

    If campaign_id is given, a campaign is already its own time boundary,
    same as _sms_metrics — since further narrows within it (the Analytics
    tab's Today/7D/30D/All Time toggle, applied on top of the campaign's own
    date range). Booked/not-interested stay scoped by the conversation-level
    tag (email_conversations.campaign_id/updated_at), same as SMS.
    """
    reset_at_raw = await conn.fetchval(
        "SELECT value FROM dialer_settings WHERE key = 'email_stats_reset_at'"
    )
    if reset_at_raw:
        reset_at = datetime.fromisoformat(reset_at_raw.replace("Z", "+00:00"))
        since = max(since, reset_at) if since else reset_at

    if campaign_id is not None:
        params = [campaign_id, since] if since else [campaign_id]
        booked_filter = "AND campaign_id = $1" + (" AND booked_at >= $2" if since else "")
        not_interested_filter = "AND campaign_id = $1" + (" AND updated_at >= $2" if since else "")
        unsub_filter = ""  # unsubscribes are tracked on contacts, not per-conversation — no clean campaign scope
        unsub_params = []
    else:
        params = [since] if since else []
        booked_filter = "AND booked_at >= $1" if since else ""
        not_interested_filter = "AND updated_at >= $1" if since else ""
        unsub_filter = "AND opted_out_at >= $1" if since else ""
        unsub_params = params

    # Each recipient's ORIGINAL initial outbound message only — the earliest
    # non-test, non-automated outbound row per email address, full stop.
    # Fetched once and filtered/aggregated in Python rather than repeating a
    # near-identical CTE five times: sent/opened/bounced/replied all derive
    # from this same fixed population, so a follow-up or later re-send in
    # the same thread can never be counted as a fresh "sent", nor can an
    # open/bounce/reply on a follow-up message count toward these rates.
    campaign_clause  = "AND campaign_id = $1" if campaign_id is not None else ""
    campaign_params  = [campaign_id] if campaign_id is not None else []
    initial_rows = await conn.fetch(
        f"""
        SELECT DISTINCT ON (email) email, contact_id, thread_id, sent_at, bounced_at
        FROM email_messages
        WHERE direction='outbound' AND NOT is_test AND NOT is_automated {campaign_clause}
        ORDER BY email, sent_at ASC
        """,
        *campaign_params,
    )
    if since:
        initial_rows = [r for r in initial_rows if r["sent_at"] >= since]

    total_sent = initial_sent = total_outreach = len(initial_rows)

    bounced = sum(1 for r in initial_rows if r["bounced_at"])

    # Replied: of those initial messages, how many threads got an inbound
    # reply at all. No separate date bound needed on the inbound side — a
    # reply necessarily comes after its initial message, which is already
    # within the window, so this can't pick up an unrelated historical
    # reply the way the old (pre-2026-09-01) all-outbound-rows version could.
    replied = 0
    replied_threads: set = set()
    thread_ids = [r["thread_id"] for r in initial_rows]
    if thread_ids:
        reply_rows = await conn.fetch(
            "SELECT DISTINCT thread_id FROM email_messages WHERE direction='inbound' AND thread_id = ANY($1)",
            thread_ids,
        )
        replied_threads = {r["thread_id"] for r in reply_rows}
        replied = sum(1 for r in initial_rows if r["thread_id"] in replied_threads)

    # Positive replies: prospects Dylan has ticked Engaged or Interested on
    # the Email channel's Inbox stages (email_contact_stages), or who booked
    # from an email conversation. Counted per prospect (contact), out of this
    # same initial-send population. Replaced open rate 2026-09-24 when the
    # tracking pixel was dropped.
    positive = 0
    initial_contacts = [r["contact_id"] for r in initial_rows if r["contact_id"]]
    if initial_contacts:
        positive = await conn.fetchval(
            _POSITIVE_EMAIL_CONTACTS_SQL + " AND c.id = ANY($1::text[])",
            initial_contacts,
        )

    # Booked is windowed by email_conversations.booked_at — stamped once
    # when a booking happens and never cleared, so a later disposition
    # change (e.g. closing the thread as not_interested) can't erase the
    # booked credit (same fix as _sms_metrics — see its docstring). Not
    # Interested still windows on updated_at (bumped when disposition is
    # set — see email_inbox.py's close-conversation handler), not
    # created_at (when the thread first started), so a disposition change
    # that lands in this period shows up even if the contact was first
    # emailed before the window started.
    booked_total = await conn.fetchval(
        f"SELECT COUNT(*) FROM email_conversations WHERE booked_at IS NOT NULL {booked_filter}",
        *params,
    )

    not_interested = await conn.fetchval(
        f"SELECT COUNT(*) FROM email_conversations WHERE disposition='not_interested' {not_interested_filter}",
        *params,
    )

    # confirmed_opened/bounced are computed above from initial_rows —
    # "Opened" only counts a pixel fire more than 2 minutes after send
    # (Apple Mail Privacy Protection fetches every tracking pixel within
    # seconds of delivery regardless of whether a human ever reads the
    # email, so a very fast open is far more likely an auto-prefetch than a
    # real read — heuristic, not a guarantee, but meaningfully better than
    # the raw pixel-fired count alone). "Bounced" counts a delivery-failure
    # notice detected by the inbox sync (mailer-daemon pattern match — see
    # email_inbox.py) on that same initial message.

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
        "positive_replied":     positive or 0,
        "positive_reply_rate":  _pct(positive, initial_sent),
        "abr":              _pct(booked_total, initial_sent),
        "booked":           booked_total or 0,
        "not_interested":      not_interested or 0,
        "not_interested_rate": _pct(not_interested, initial_sent),
        "bounced":          bounced or 0,
        "bounce_rate":      _pct(bounced, total_sent),
        "unsubscribed":     unsubscribed or 0,
        "unsubscribe_rate": _pct(unsubscribed, initial_sent),
    }


async def _email_handoff_metrics(conn, since=None) -> dict:
    """
    Email Handoff sequence funnel — enrolled / touch1-3 sent / replied, for
    contacts currently in "email-handoff" status. This is the stage
    breakdown a contact's Inbox checkboxes show INSTEAD of the SMS
    stage_primed/engaged/interested funnel once their status flips to
    "email-handoff" (see routers/email_inbox.py's set_contact_stage/
    get_contact_thread) — see email_handoff_sequence.py for the 3-touch
    engine itself. _email_metrics above already covers general email-channel
    volume (sent/opened/bounced/replied across ALL email activity, Email
    Handoff included); this is specifically the touch-by-touch progression,
    the email equivalent of _sms_metrics' stage funnel.

    Narrowed by each touch's own sent_at column, no activity-fallback
    needed (unlike _sms_metrics' stage columns) — Email Handoff is a
    one-shot sequence with no restart/re-enrollment cycle, so a touch's
    sent_at is always the complete, accurate history of when it happened.
    """
    contacted = await conn.fetchval("SELECT COUNT(*) FROM email_handoff_state")
    if since:
        enrolled  = await conn.fetchval("SELECT COUNT(*) FROM email_handoff_state WHERE enrolled_at >= $1", since)
        touch1    = await conn.fetchval("SELECT COUNT(*) FROM email_handoff_state WHERE touch1_sent_at >= $1", since)
        touch2    = await conn.fetchval("SELECT COUNT(*) FROM email_handoff_state WHERE touch2_sent_at >= $1", since)
        touch3    = await conn.fetchval("SELECT COUNT(*) FROM email_handoff_state WHERE touch3_sent_at >= $1", since)
        replied   = await conn.fetchval("SELECT COUNT(*) FROM email_handoff_state WHERE stage_replied AND stage_replied_at >= $1", since)
    else:
        enrolled  = contacted
        touch1    = await conn.fetchval("SELECT COUNT(*) FROM email_handoff_state WHERE touch1_sent_at IS NOT NULL")
        touch2    = await conn.fetchval("SELECT COUNT(*) FROM email_handoff_state WHERE touch2_sent_at IS NOT NULL")
        touch3    = await conn.fetchval("SELECT COUNT(*) FROM email_handoff_state WHERE touch3_sent_at IS NOT NULL")
        replied   = await conn.fetchval("SELECT COUNT(*) FROM email_handoff_state WHERE stage_replied")

    # Positive: enrolled prospects with a positive email reply (same
    # definition as _email_metrics — Email stage Engaged/Interested, or booked).
    positive = await conn.fetchval(
        _POSITIVE_EMAIL_CONTACTS_SQL
        + " AND EXISTS (SELECT 1 FROM email_handoff_state ehs WHERE ehs.contact_id = c.id"
        + (" AND ehs.enrolled_at >= $1)" if since else ")"),
        *([since] if since else []),
    )

    # Video plays: enrolled prospects who pressed play on their {loom} video
    # (the watch page's 'play' beacon — a real click in a browser, so email
    # link scanners that merely fetch the page don't count), out of those
    # who have a video and have been sent at least one touch.
    video_row = await conn.fetchrow(
        f"""
        SELECT COUNT(*) AS sent,
               COUNT(*) FILTER (WHERE EXISTS (
                   SELECT 1 FROM content_view_events v
                   JOIN watch_videos w ON w.slug = v.content_key
                   WHERE v.source = 'outreach_video' AND v.event_type = 'play'
                     AND w.contact_id = ehs.contact_id)) AS played
        FROM email_handoff_state ehs
        WHERE ehs.loom_url IS NOT NULL AND ehs.touch1_sent_at IS NOT NULL
          {"AND ehs.touch1_sent_at >= $1" if since else ""}
        """,
        *([since] if since else []),
    )

    return {
        "enrolled":     enrolled or 0,
        "videos_sent":      video_row["sent"] or 0,
        "video_plays":      video_row["played"] or 0,
        "video_play_rate":  _pct(video_row["played"], video_row["sent"]),
        "positive_replied":    positive or 0,
        "positive_reply_rate": _pct(positive, contacted),
        "touch1_sent":  touch1 or 0,
        "touch2_sent":  touch2 or 0,
        "touch3_sent":  touch3 or 0,
        "replied":      replied or 0,
        "reply_rate":   _pct(replied, contacted),
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
        email_handoff_all    = await _email_handoff_metrics(conn)
        email_handoff_period = await _email_handoff_metrics(conn, since)

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
        "email_handoff": {
            "all_time": email_handoff_all,
            "period":   email_handoff_period,
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
        # (client_id IS NULL OR is_client_anchor) everywhere below: a
        # client's own portal-managed leads (client_id set, not the anchor)
        # belong to that client's own Leads tab, not DigiGrowth's internal
        # analytics — excluding them keeps this funnel scoped to Dylan's
        # own lead-gen, same exclusion as crm.py's contact list and
        # dialer.py's queue.
        total_leads = await conn.fetchval(
            "SELECT COUNT(*) FROM contacts WHERE (client_id IS NULL OR is_client_anchor)" if all_time
            else "SELECT COUNT(*) FROM contacts WHERE created_at >= $1 AND (client_id IS NULL OR is_client_anchor)",
            *([] if all_time else [_since(days)]),
        )
        new_week    = await conn.fetchval("SELECT COUNT(*) FROM contacts WHERE created_at >= $1 AND (client_id IS NULL OR is_client_anchor)", week_ago)
        new_month   = await conn.fetchval("SELECT COUNT(*) FROM contacts WHERE created_at >= $1 AND (client_id IS NULL OR is_client_anchor)", month_ago)
        sms         = await _sms_metrics(conn, None if all_time else _since(days))
        email       = await _email_metrics(conn, None if all_time else _since(days))
        grade_rows  = await conn.fetch(
            """
            SELECT grade,
                   COUNT(*) AS cnt,
                   COUNT(*) FILTER (WHERE status = 'appointment-booked') AS booked
            FROM contacts
            WHERE grade IS NOT NULL AND (client_id IS NULL OR is_client_anchor)
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
            WHERE state IS NOT NULL AND state != '' AND (client_id IS NULL OR is_client_anchor)
            GROUP BY state
            """
        )
        os_sales = await _os_sales_stats(conn, days)

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
    # (DB) combined at every stage, not cold-calling-only.
    #
    # "Pitched" (the reached stage) sums calls reached + SMS's own DM
    # Reached stage — not the later Engaged stage, which undercounts what
    # "reached" means — + confirmed email opens. Same fix as
    # dashboard.py::summary's total_reached.
    #
    # "Booked" is OS-native now — appointment_reminders (Dylan's own
    # sales-pipeline bookings, any source: Inbox/CRM/Dialer/DM/etc.) is the
    # single system of record going forward, not a manually-synced sheet
    # total plus an app-bookings-not-yet-reflected patch (see
    # _os_sales_stats). "Shows"/"closes" are OS-native for the same reason —
    # they're read straight off outcome_show/outcome_close on the same
    # table (see AppointmentOutcomeCard.jsx / routers/appointments.py's PATCH
    # handler), not the old Sales Performance Tracker sheet.
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
    booked   = os_sales["discovery_calls"]

    return {
        "funnel": {
            "total_leads": ((sales.get("sheet_calls_made") or 0) + (total_leads or 0)) if all_time else (total_leads or 0),
            "dialed":   dialed,
            "answered": answered,
            "pitched":  pitched,
            "booked":   booked,
            "shows":    os_sales["shows"],
            "closes":   os_sales["closes"],
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
        total_leads = await conn.fetchval(
            "SELECT COUNT(*) FROM contacts WHERE (client_id IS NULL OR is_client_anchor)"
        )
        os_sales = await _os_sales_stats(conn, days)

    discovery = os_sales["discovery_calls"]
    closes    = os_sales["closes"]
    revenue   = os_sales["total_revenue"]
    shows     = os_sales["shows"]

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
        "closes":            closes,
        # Closed ÷ shows (who actually showed up), not ÷ discovery calls
        # booked — a booked call that no-shows was never a chance to close,
        # so counting it in the denominator understated the real close
        # rate. Matches the funnel widget's own close-rate math elsewhere
        # in AnalyticsPanel.jsx, which already divides by shows.
        "close_rate":        _pct(closes, shows),
        "total_revenue":     revenue,
        "avg_deal_size":     os_sales["avg_deal_size"],
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
        elif campaign["channel"] == "vsl":
            metrics = await vsl_funnel(campaign_id=campaign_id, since_override=since)
        elif campaign["channel"] == "loom":
            metrics = await loom_outreach_funnel(campaign_id=campaign_id, since_override=since)
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




