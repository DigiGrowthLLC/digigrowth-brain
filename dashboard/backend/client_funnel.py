"""Full-funnel breakdown for one client: Meta ad delivery → funnel page →
DigiGrowth Booking → appointment outcomes, with step-by-step conversion,
drop-off and cost KPIs. Backs the client portal's Analytics tab
(GET /portal-api/{token}/funnel) and the OS (GET /api/clients/{id}/funnel).

Two acquisition paths, chosen from the client's own data:
  - "form": Meta Instant Form ads. Impressions → link clicks (form opens) →
    leads (contacts.lead_source = 'meta_form') → replied to the clinic's
    texts → booked → showed → became a patient.
  - "page": ads to the client's funnel page. Impressions → link clicks →
    funnel page visits → booking page visits → started booking (name +
    mobile typed) → [went to payment, paid offers] → booked → showed →
    became a patient.
A client running both gets both; appointments are split by the contact's
lead_source so the two never double-count.

Accuracy rules:
  - Every stage is scoped to the same period (by when that stage happened).
  - Dylan's own visits/bookings are dropped (tracking_exclusion.py, plus the
    default test phone number).
  - Show/close rates divide by appointments with an outcome recorded, so an
    appointment that hasn't happened yet never reads as a no-show.
  - A stage with no data source for this client (no Meta access yet, no
    DigiGrowth Booking page) is flagged `available: false`, never a fake 0.
"""

from __future__ import annotations

import json

from db import get_pool
from tracking_exclusion import TEST_PHONE_DIGITS

PERIODS = {"today": ("1 day", 0), "week": ("7 days", 6), "month": ("30 days", 29), "all": (None, None)}

# DigiGrowth's targets per step: (good at or above, ok at or above), percent.
TARGETS = {
    "link_clicks":     (1.0, 0.6),    # link CTR
    "leads_form":      (10.0, 5.0),   # form opens → submitted
    "replied":         (40.0, 20.0),  # leads → replied to a text
    "booked_form":     (30.0, 15.0),  # replied → booked
    "funnel_visits":   (70.0, 50.0),  # link clicks → page actually loaded
    "booking_views":   (25.0, 12.0),  # funnel page → booking page
    "booking_started": (35.0, 20.0),  # booking page → typed name + mobile
    "checkout":        (60.0, 40.0),  # started → went to payment
    "booked_page":     (50.0, 30.0),  # started (or payment page) → booked
    "showed":          (75.0, 60.0),  # of appointments with an outcome
    "patient":         (60.0, 40.0),  # of shows with an outcome
}
MIN_BASE = 10        # below this many at the previous stage: "not enough data yet"
MIN_BASE_OUTCOME = 5


def _pct(n, d):
    return round(n / d * 100, 1) if d else None


def _status(rate, key, base, min_base=MIN_BASE):
    if rate is None or base < min_base or key not in TARGETS:
        return "low_data"
    good, ok = TARGETS[key]
    return "good" if rate >= good else "ok" if rate >= ok else "poor"


def _not_test(phone_col: str) -> str:
    digits = ",".join(f"'{d}'" for d in TEST_PHONE_DIGITS)
    return f"right(regexp_replace(coalesce({phone_col}, ''), '\\D', '', 'g'), 10) NOT IN ({digits})"


async def build_funnel(client_id: int, period: str = "month") -> dict:
    if period not in PERIODS:
        raise ValueError("period must be 'all', 'today', 'week' or 'month'")
    iv, day_offset = PERIODS[period]

    def since(col: str) -> str:
        return f"AND {col} >= now() - interval '{iv}'" if iv else ""

    stat_since = f"AND stat_date >= current_date - {day_offset}" if day_offset is not None else ""

    pool = await get_pool()
    async with pool.acquire() as conn:
        cfg = await conn.fetchrow(
            "SELECT meta_ad_account_id FROM client_marketing_config WHERE client_id = $1", client_id)
        ad_rows = await conn.fetch(
            f"SELECT spend, impressions, clicks, leads, raw FROM ad_campaign_stats "
            f"WHERE client_id = $1 AND platform = 'meta' {stat_since}", client_id)
        last_sync = await conn.fetchval(
            "SELECT max(synced_at) FROM ad_campaign_stats WHERE client_id = $1 AND platform = 'meta'", client_id)

        # Funnel page: the beacon on client funnels (source 'client_website',
        # browser-only, so no bots/link previews) wins; the server-side /lp
        # view log is the fallback for pages without the beacon.
        site_ids = [str(r["id"]) for r in await conn.fetch(
            "SELECT id FROM client_websites WHERE client_id = $1", client_id)]
        lp_slugs = [r["slug"] for r in await conn.fetch(
            "SELECT slug FROM landing_pages WHERE client_id = $1", client_id)]
        site_views = await conn.fetchval(
            f"SELECT count(*) FROM content_view_events WHERE source = 'client_website' AND event_type = 'view' "
            f"AND content_key = ANY($1::text[]) {since('occurred_at')}", site_ids) if site_ids else 0
        lp_views = await conn.fetchval(
            f"SELECT count(*) FROM content_view_events WHERE source = 'landing_page' AND event_type = 'view' "
            f"AND content_key = ANY($1::text[]) {since('occurred_at')}", lp_slugs) if lp_slugs else 0

        booking_on = bool(await conn.fetchval(
            "SELECT 1 FROM booking_settings WHERE client_id = $1 AND enabled", client_id))
        paid_offer = bool(await conn.fetchval(
            "SELECT 1 FROM booking_event_types WHERE client_id = $1 AND active AND price_cents > 0", client_id))
        steps = {r["step"]: r["n"] for r in await conn.fetch(
            f"SELECT step, count(DISTINCT session_id) AS n FROM booking_events "
            f"WHERE client_id = $1 {since('created_at')} GROUP BY step", client_id)}
        pay = await conn.fetchrow(
            f"""SELECT count(*) FILTER (WHERE paid_at IS NOT NULL AND refunded_at IS NULL) AS paid,
                       coalesce(sum(price_cents) FILTER (WHERE paid_at IS NOT NULL AND refunded_at IS NULL), 0) AS cents
                FROM bookings WHERE client_id = $1 AND NOT excluded AND {_not_test('phone')} {since('created_at')}""",
            client_id)

        leads = await conn.fetchrow(
            f"""SELECT count(*) AS total,
                       count(*) FILTER (WHERE lead_source = 'meta_form') AS form
                FROM contacts WHERE client_id = $1 AND NOT is_client_anchor AND {_not_test('phone')}
                {since('created_at')}""", client_id)
        # Form leads (from this period) who texted the clinic back, ever.
        replied = await conn.fetchval(
            f"""SELECT count(*) FROM contacts c
                WHERE c.client_id = $1 AND NOT c.is_client_anchor AND c.lead_source = 'meta_form'
                  AND {_not_test('c.phone')} {since('c.created_at')}
                  AND EXISTS (SELECT 1 FROM client_sms_messages m
                              WHERE m.client_id = $1 AND m.direction = 'inbound'
                                AND right(regexp_replace(m.from_number, '\\D', '', 'g'), 10)
                                  = right(regexp_replace(c.phone, '\\D', '', 'g'), 10))""", client_id)

        appt_rows = await conn.fetch(
            f"""SELECT (coalesce(c.lead_source, '') = 'meta_form') AS is_form,
                       count(*) FILTER (WHERE ar.status != 'canceled') AS booked,
                       count(*) FILTER (WHERE ar.status = 'canceled') AS canceled,
                       count(*) FILTER (WHERE ar.status != 'canceled' AND ar.appointment_at > now()) AS upcoming,
                       count(*) FILTER (WHERE ar.outcome_show = 'show') AS shows,
                       count(*) FILTER (WHERE ar.outcome_show = 'no_show') AS no_shows,
                       count(*) FILTER (WHERE ar.status != 'canceled' AND ar.appointment_at <= now()
                                        AND ar.outcome_show IS NULL) AS awaiting_show,
                       count(*) FILTER (WHERE ar.outcome_close = 'closed') AS closed,
                       count(*) FILTER (WHERE ar.outcome_close = 'not_closed') AS not_closed
                FROM appointment_reminders ar
                JOIN contacts c ON c.id = ar.contact_id
                WHERE c.client_id = $1 AND NOT c.is_client_anchor AND {_not_test('c.phone')}
                  AND NOT EXISTS (SELECT 1 FROM bookings b WHERE b.appointment_id = ar.id AND b.excluded)
                  {since('ar.created_at')}
                GROUP BY 1""", client_id)

    # ---- Meta
    spend = impressions = link_clicks = meta_form_leads = meta_lpv = 0
    for r in ad_rows:
        raw = r["raw"]
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception:
                raw = {}
        raw = raw or {}
        spend += float(r["spend"] or 0)
        impressions += int(r["impressions"] or 0)
        link_clicks += int(float(raw.get("inline_link_clicks") or r["clicks"] or 0))
        acts = {a.get("action_type"): int(float(a.get("value", 0))) for a in (raw.get("actions") or [])}
        meta_form_leads += acts.get("onsite_conversion.lead_grouped", 0) or acts.get("leadgen.other", 0)
        meta_lpv += acts.get("landing_page_view", 0)
    meta_connected = bool(cfg and cfg["meta_ad_account_id"]) and last_sync is not None
    meta_leads_total = sum(int(r["leads"] or 0) for r in ad_rows)

    funnel_views = site_views or lp_views
    appts = {True: None, False: None}
    for r in appt_rows:
        appts[bool(r["is_form"])] = dict(r)
    empty = {"booked": 0, "canceled": 0, "upcoming": 0, "shows": 0, "no_shows": 0,
             "awaiting_show": 0, "closed": 0, "not_closed": 0}

    def outcome_stages(a: dict, booked_key: str, booked_prev: int, booked_label: str) -> list[dict]:
        decided_show = a["shows"] + a["no_shows"]
        decided_close = a["closed"] + a["not_closed"]
        show_rate = _pct(a["shows"], decided_show)
        close_rate = _pct(a["closed"], decided_close)
        awaiting_close = max(a["shows"] - decided_close, 0)
        book_rate = _pct(a["booked"], booked_prev)
        return [
            {"key": "booked", "tkey": booked_key, "label": booked_label, "source": "booking", "value": a["booked"],
             "rate": book_rate, "status": _status(book_rate, booked_key, booked_prev),
             "note": " · ".join(x for x in [
                 f"{a['upcoming']} upcoming" if a["upcoming"] else "",
                 f"{a['canceled']} canceled (not counted)" if a["canceled"] else "",
             ] if x) or None},
            {"key": "showed", "label": "Showed up", "source": "outcomes", "value": a["shows"],
             "rate": show_rate, "rate_basis": "of appointments with an outcome", "drop_off": a["no_shows"],
             "status": _status(show_rate, "showed", decided_show, MIN_BASE_OUTCOME),
             "note": f"{a['awaiting_show']} past visit(s) still need show/no-show marked" if a["awaiting_show"] else None},
            {"key": "patient", "label": "Became a patient", "source": "outcomes", "value": a["closed"],
             "rate": close_rate, "rate_basis": "of shows with an outcome", "drop_off": a["not_closed"],
             "status": _status(close_rate, "patient", decided_close, MIN_BASE_OUTCOME),
             "note": f"{awaiting_close} show(s) still need an outcome" if awaiting_close else None},
        ]

    def ad_stages(third_key: str) -> list[dict]:
        ctr = _pct(link_clicks, impressions)
        return [
            {"key": "impressions", "label": "Ad impressions", "source": "meta", "value": impressions,
             "available": meta_connected, "rate": None, "status": None},
            {"key": "link_clicks", "label": "Link clicks" if third_key != "leads" else "Clicks (form opened)",
             "source": "meta", "value": link_clicks, "available": meta_connected,
             "rate": ctr, "rate_basis": "click-through rate", "status": _status(ctr, "link_clicks", impressions)},
        ]

    def chain(stages: list[dict]) -> list[dict]:
        top = next((s["value"] for s in stages if s.get("available", True) and s["value"]), 0)
        prev = None
        for s in stages:
            s.setdefault("available", True)
            if s["available"] and prev is not None and prev["available"] and s.get("rate") is None and s["key"] != "impressions":
                s["rate"] = _pct(s["value"], prev["value"])
            if "drop_off" not in s and s["available"] and prev is not None and prev["available"] and prev["value"]:
                s["drop_off"] = max(prev["value"] - s["value"], 0)
            s["pct_of_top"] = _pct(s["value"], top) if s["available"] else None
            prev = s
        return stages

    paths = []

    # ---- Instant Form path
    a_form = appts[True] or empty
    if leads["form"] or meta_form_leads or a_form["booked"]:
        st = ad_stages("leads")
        lead_rate = _pct(leads["form"], link_clicks) if meta_connected else None
        st.append({"key": "leads", "label": "Leads (form submitted)", "source": "funnel", "value": leads["form"],
                   "rate": lead_rate, "status": _status(lead_rate, "leads_form", link_clicks),
                   "note": f"Meta reports {meta_form_leads}" if meta_connected and meta_form_leads != leads["form"] else None})
        rr = _pct(replied, leads["form"])
        st.append({"key": "replied", "label": "Replied to a text", "source": "funnel", "value": replied,
                   "rate": rr, "status": _status(rr, "replied", leads["form"])})
        st += outcome_stages(a_form, "booked_form", replied, "Booked a visit")
        paths.append({"key": "form", "label": "Instant Form ads", "stages": chain(st), "leads": leads["form"],
                      "booked": a_form["booked"], "shows": a_form["shows"], "patients": a_form["closed"]})

    # ---- Funnel page path
    a_page = appts[False] or empty
    has_page = bool(site_ids or lp_slugs or booking_on)
    if funnel_views or steps or a_page["booked"] or (has_page and not paths):
        st = ad_stages("page")
        fv_rate = _pct(funnel_views, link_clicks) if meta_connected else None
        st.append({"key": "funnel_visits", "label": "Funnel page visits", "source": "funnel", "value": funnel_views,
                   "available": bool(site_ids or lp_slugs), "rate": fv_rate,
                   "status": _status(fv_rate, "funnel_visits", link_clicks)})
        prev_key_val = funnel_views
        if booking_on:
            bv, bs, sub = steps.get("view", 0), steps.get("details", 0), steps.get("submit", 0)
            r1 = _pct(bv, funnel_views)
            st.append({"key": "booking_views", "label": "Booking page visits", "source": "booking", "value": bv,
                       "rate": r1, "status": _status(r1, "booking_views", funnel_views)})
            r2 = _pct(bs, bv)
            st.append({"key": "booking_started", "label": "Started booking", "source": "booking", "value": bs,
                       "rate": r2, "status": _status(r2, "booking_started", bv),
                       "note": "typed their name + mobile"})
            prev_key_val = bs
            if paid_offer:
                r3 = _pct(sub, bs)
                st.append({"key": "checkout", "label": "Went to payment", "source": "booking", "value": sub,
                           "rate": r3, "status": _status(r3, "checkout", bs)})
                prev_key_val = sub
        # Without DigiGrowth Booking (e.g. Calendly) there's no booking-page
        # step to measure against, so funnel page → booked gets no target.
        st += outcome_stages(a_page, "booked_page" if booking_on else "booked_ext", prev_key_val,
                             "Booked & paid" if paid_offer else "Booked a visit")
        paths.append({"key": "page", "label": "Funnel page", "stages": chain(st), "leads": leads["total"] - leads["form"],
                      "booked": a_page["booked"], "shows": a_page["shows"], "patients": a_page["closed"]})

    # Meta reports delivery per ad account, so with both ad types running the
    # top two stages are the same combined numbers on each path.
    if len(paths) > 1:
        for p in paths:
            for s in p["stages"]:
                if s["source"] == "meta" and s["available"]:
                    s["note"] = "All ads combined (form + funnel page)"

    # ---- Totals + cost KPIs (all paths together)
    booked = sum(p["booked"] for p in paths)
    shows = sum(p["shows"] for p in paths)
    patients = sum(p["patients"] for p in paths)
    all_leads = leads["total"]

    def cost(n):
        return round(spend / n, 2) if meta_connected and n else None

    kpis = {
        "spend": round(spend, 2) if meta_connected else None,
        "impressions": impressions if meta_connected else None,
        "link_clicks": link_clicks if meta_connected else None,
        "cpm": round(spend / impressions * 1000, 2) if meta_connected and impressions else None,
        "ctr": _pct(link_clicks, impressions) if meta_connected else None,
        "cpc": cost(link_clicks),
        "leads": all_leads,
        "meta_reported_leads": meta_leads_total if meta_connected else None,
        "cost_per_lead": cost(all_leads),
        "booked": booked,
        "cost_per_booking": cost(booked),
        "shows": shows,
        "cost_per_show": cost(shows),
        "patients": patients,
        "cost_per_patient": cost(patients),
        "prepaid_revenue": round(pay["cents"] / 100, 2) if paid_offer else None,
        "prepaid_count": pay["paid"] if paid_offer else None,
        "lead_to_booking": _pct(booked, all_leads),
    }

    # Attach each step's target, then find the biggest leak: the step furthest
    # below its target that has enough data behind it.
    worst = None
    for p in paths:
        for s in p["stages"]:
            tkey = s.pop("tkey", None) or {"leads": "leads_form"}.get(s["key"], s["key"])
            if tkey in TARGETS:
                s["target"] = {"good": TARGETS[tkey][0], "ok": TARGETS[tkey][1]}
            if s.get("status") in ("poor", "ok") and s.get("target") and s.get("rate") is not None:
                good = s["target"]["good"]
                gap = (good - s["rate"]) / good
                if worst is None or gap > worst["gap"]:
                    worst = {"path": p["key"], "stage": s["key"], "label": s["label"], "rate": s["rate"],
                             "target": good, "gap": round(gap, 3)}

    return {
        "period": period,
        "meta": {"connected": meta_connected, "account_set": bool(cfg and cfg["meta_ad_account_id"]),
                 "last_sync": last_sync.isoformat() if last_sync else None,
                 "landing_page_views": meta_lpv if meta_connected else None},
        "booking_enabled": booking_on,
        "paid_offer": paid_offer,
        "paths": paths,
        "kpis": kpis,
        "biggest_leak": worst,
        "targets": {k: {"good": v[0], "ok": v[1]} for k, v in TARGETS.items()},
    }
