"""Client retention: did a client stay with us after their campaign?

One `client_renewals` row per finished campaign (client_id + campaign_launched_at).
It opens as `pending` the moment that campaign's final report is sent (or marked
sent by hand), and Dylan records the outcome: renewed / churned / paused, with a
reason for churn, the plan they continue on and what it's worth per month
(Clients -> client -> Agents -> Client Success Manager -> "Did they stay?").

Daily (run_daily, after the CSM jobs):
  - a new campaign launched for the client after the decision opened -> renewed
    automatically (decided_by = 'auto');
  - the client clicked "Yes, let's talk about the next campaign" on the final
    report -> a suggestion shown next to the buttons (never decides on its own);
  - still pending REMIND_AFTER_DAYS after the final report -> one To-Do.

summary() feeds the Retention section of the Analytics page: churn and renewal
rates over decided campaigns, reasons, revenue kept/lost, and renewal rate split
by the signals we have at campaign end (goal hit, health band, report opened,
"wants next" clicked, testimonial, outcomes marked, package, cost per booking).
Counts ride along with every rate because the sample is small.

Dylan 2026-11-21: trigger = final report sent; track fees; Advantage Therapy
backfilled as churned.
"""
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from db import get_pool

STATUSES = ("pending", "renewed", "churned", "paused")
REASONS = {
    "results": "Results",
    "price": "Price / budget",
    "timing": "Timing / capacity",
    "in_house": "Went in-house / another agency",
    "no_reply": "Stopped replying",
    "other": "Other",
}
REMIND_AFTER_DAYS = 14
SHOW_TARGET = 75   # same show-rate target as the client funnel / reports

SCHEMA = """
CREATE TABLE IF NOT EXISTS client_renewals (
    id                   SERIAL PRIMARY KEY,
    client_id            INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    campaign_launched_at TIMESTAMPTZ,
    final_report_id      INTEGER REFERENCES client_reports(id) ON DELETE SET NULL,
    opened_at            TIMESTAMPTZ NOT NULL DEFAULT now(),   -- final report sent
    status               TEXT NOT NULL DEFAULT 'pending',      -- pending | renewed | churned | paused
    reason               TEXT,                                 -- REASONS key (churned / paused)
    notes                TEXT,
    plan                 TEXT,                                 -- what they continue on (or were on)
    monthly_value        NUMERIC,                              -- $/month kept (renewed) or lost (churned)
    decided_at           TIMESTAMPTZ,
    decided_by           TEXT,                                 -- dylan | auto
    suggestion           TEXT,                                 -- e.g. "Clicked 'let's talk about the next campaign'"
    reminded_at          TIMESTAMPTZ,
    signals              JSONB NOT NULL DEFAULT '{}',          -- snapshot at campaign end
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_client_renewals_campaign ON client_renewals(client_id, campaign_launched_at);
"""


def _j(v):
    return json.loads(v) if isinstance(v, str) else (v or {})


async def _signals(conn, report: dict) -> dict:
    """What we knew when the campaign ended: results from the final report's
    stored numbers, the latest health score, and the package."""
    data = _j(report.get("data"))
    kpis = ((data.get("to_date") or {}).get("kpis")) or {}
    pace = data.get("pace") or {}
    goal = pace.get("goal")
    if goal is None:
        goal = await conn.fetchval("SELECT campaign_booking_goal FROM client_marketing_config WHERE client_id = $1",
                                   report["client_id"])
    booked = kpis.get("booked")
    health = await conn.fetchrow("SELECT score, band FROM client_health WHERE client_id = $1 "
                                 "ORDER BY computed_at DESC LIMIT 1", report["client_id"])
    package = await conn.fetchval("SELECT service_package FROM clients WHERE id = $1", report["client_id"])
    return {
        "goal": goal, "booked": booked,
        "goal_hit": (booked >= goal) if (goal and booked is not None) else None,
        "leads": kpis.get("leads"), "spend": kpis.get("spend"), "cost_per_booking": kpis.get("cost_per_booking"),
        "health_score": health["score"] if health else None, "health_band": health["band"] if health else None,
        "package": package,
    }


async def open_for_report(conn, report_id: int) -> None:
    """A final report just went to the client: start its renewal decision. Idempotent."""
    rep = await conn.fetchrow("SELECT id, client_id, kind, campaign_launched_at, data, sent_at FROM client_reports "
                              "WHERE id = $1", report_id)
    if not rep or rep["kind"] != "final" or not rep["sent_at"]:
        return
    if await conn.fetchval("SELECT coalesce(is_test, false) FROM clients WHERE id = $1", rep["client_id"]):
        return
    sig = await _signals(conn, dict(rep))
    await conn.execute(
        """INSERT INTO client_renewals (client_id, campaign_launched_at, final_report_id, opened_at, signals, plan)
           VALUES ($1, $2, $3, $4, $5::jsonb, $6)
           ON CONFLICT (client_id, campaign_launched_at) DO UPDATE
             SET final_report_id = coalesce(client_renewals.final_report_id, EXCLUDED.final_report_id)""",
        rep["client_id"], rep["campaign_launched_at"], rep["id"], rep["sent_at"], json.dumps(sig, default=str),
        sig.get("package"))


async def set_outcome(renewal_id: int, body: dict) -> dict:
    status = body.get("status")
    if status not in STATUSES:
        raise ValueError("status must be one of " + ", ".join(STATUSES))
    reason = body.get("reason") if body.get("reason") in REASONS else None
    value = body.get("monthly_value")
    value = Decimal(str(float(value))) if value not in (None, "") else None
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """UPDATE client_renewals SET status = $2, reason = $3,
                   notes = coalesce($4, notes), plan = coalesce($5, plan), monthly_value = coalesce($6, monthly_value),
                   decided_at = CASE WHEN $2 = 'pending' THEN NULL ELSE coalesce(decided_at, now()) END,
                   decided_by = CASE WHEN $2 = 'pending' THEN NULL ELSE 'dylan' END
               WHERE id = $1 RETURNING *""",
            renewal_id, status, reason if status in ("churned", "paused") else None,
            body.get("notes"), body.get("plan"), value)
        if row and status != "pending":
            name = await conn.fetchval("SELECT name FROM clients WHERE id = $1", row["client_id"])
            await conn.execute("UPDATE todos SET done = TRUE WHERE NOT done AND text = $1", f"Did {name} renew?")
    return _row(row) if row else {}


def _row(r) -> dict:
    d = dict(r)
    d["signals"] = _j(d.get("signals"))
    if d.get("monthly_value") is not None:
        d["monthly_value"] = float(d["monthly_value"])
    return d


async def for_client(client_id: int) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM client_renewals WHERE client_id = $1 ORDER BY opened_at DESC", client_id)
    return [_row(r) for r in rows]


async def run_daily() -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Backfill: final reports already sent without a decision row.
        for rid in await conn.fetch(
                """SELECT r.id FROM client_reports r WHERE r.kind = 'final' AND r.sent_at IS NOT NULL
                     AND NOT EXISTS (SELECT 1 FROM client_renewals n WHERE n.client_id = r.client_id
                                     AND n.campaign_launched_at IS NOT DISTINCT FROM r.campaign_launched_at)"""):
            await open_for_report(conn, rid["id"])
        pending = await conn.fetch(
            """SELECT n.*, c.name, m.campaign_launched_at AS current_launch
               FROM client_renewals n JOIN clients c ON c.id = n.client_id
               LEFT JOIN client_marketing_config m ON m.client_id = n.client_id
               WHERE n.status = 'pending'""")
        for n in pending:
            # A newer campaign launched: they stayed.
            if n["current_launch"] and n["campaign_launched_at"] and n["current_launch"] > n["campaign_launched_at"]:
                await conn.execute("UPDATE client_renewals SET status = 'renewed', decided_at = now(), decided_by = 'auto', "
                                   "suggestion = 'A new campaign launched' WHERE id = $1", n["id"])
                await conn.execute("UPDATE todos SET done = TRUE WHERE NOT done AND text = $1", f"Did {n['name']} renew?")
                continue
            wants = await conn.fetchval(
                "SELECT 1 FROM client_report_feedback WHERE client_id = $1 AND wants_next AND created_at >= $2 - interval '1 day'",
                n["client_id"], n["opened_at"])
            if wants and not n["suggestion"]:
                await conn.execute("UPDATE client_renewals SET suggestion = $2 WHERE id = $1", n["id"],
                                   "Clicked \"Yes, let's talk about the next campaign\" on the final report")
            if not n["reminded_at"] and datetime.now(timezone.utc) - n["opened_at"] > timedelta(days=REMIND_AFTER_DAYS):
                text = f"Did {n['name']} renew?"
                if not await conn.fetchval("SELECT 1 FROM todos WHERE NOT done AND text = $1", text):
                    await conn.execute(
                        "INSERT INTO todos (text, description, due_date) VALUES ($1, $2, $3)", text,
                        f"Their final report went out {n['opened_at']:%b %d}. Record whether they renewed, churned or paused "
                        "(and what it's worth per month) in Clients -> client -> Agents -> Client Success Manager -> "
                        "Did they stay?", datetime.now(timezone.utc).date())
                await conn.execute("UPDATE client_renewals SET reminded_at = now() WHERE id = $1", n["id"])


# ---------------------------------------------------------------- analytics

def _rate(part: int, whole: int):
    return round(part / whole * 100) if whole else None


def _split(rows: list[dict], key, labels: dict) -> list[dict]:
    """Renewal rate per bucket of one signal, over decided (renewed/churned) campaigns."""
    out = []
    for val, label in labels.items():
        sub = [r for r in rows if key(r) == val]
        ren = sum(1 for r in sub if r["status"] == "renewed")
        out.append({"label": label, "renewed": ren, "total": len(sub), "rate": _rate(ren, len(sub))})
    return [o for o in out if o["total"]]


async def summary(start: datetime | None = None, end: datetime | None = None) -> dict:
    """Retention over campaigns whose final report went out in [start, end)
    (the Analytics period toggle / picked day); no bounds = all time."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """WITH appts AS (
                   SELECT n.id AS renewal_id,
                          count(*) FILTER (WHERE a.outcome_show IS NOT NULL) AS outcomes_marked,
                          count(*) FILTER (WHERE a.outcome_show = 'show') AS shows,
                          count(*) FILTER (WHERE a.outcome_show = 'no_show') AS no_shows,
                          count(*) FILTER (WHERE a.outcome_close = 'closed') AS patients
                   FROM client_renewals n
                   JOIN contacts ct ON ct.client_id = n.client_id
                   JOIN appointment_reminders a ON a.contact_id = ct.id
                   WHERE a.appointment_at >= coalesce(n.campaign_launched_at, n.opened_at - interval '60 days')
                     AND a.appointment_at <= n.opened_at
                   GROUP BY n.id)
               SELECT n.*, c.name AS client_name, r.view_count,
                      coalesce(ap.outcomes_marked, 0) AS outcomes_marked, coalesce(ap.shows, 0) AS shows,
                      coalesce(ap.no_shows, 0) AS no_shows, coalesce(ap.patients, 0) AS patients,
                      EXISTS (SELECT 1 FROM client_report_feedback f WHERE f.client_id = n.client_id AND f.wants_next
                              AND f.created_at >= n.opened_at - interval '1 day') AS wants_next,
                      EXISTS (SELECT 1 FROM client_report_feedback f WHERE f.client_id = n.client_id AND f.kind = 'testimonial'
                              AND f.created_at >= n.opened_at - interval '1 day') AS testimonial,
                      (SELECT max(f.rating) FROM client_report_feedback f WHERE f.report_id = n.final_report_id) AS rating
               FROM client_renewals n JOIN clients c ON c.id = n.client_id
               LEFT JOIN client_reports r ON r.id = n.final_report_id
               LEFT JOIN appts ap ON ap.renewal_id = n.id
               WHERE NOT coalesce(c.is_test, false)
                 AND ($1::timestamptz IS NULL OR n.opened_at >= $1)
                 AND ($2::timestamptz IS NULL OR n.opened_at < $2)
               ORDER BY n.opened_at DESC""", start, end)
        active = await conn.fetchval("SELECT count(*) FROM clients WHERE status = 'active' AND NOT coalesce(is_test, false)")
    items = []
    for r in rows:
        d = _row(r)
        d["opened_report"] = (r["view_count"] or 0) > 0
        # Appointment quality, live from what the clinic marked (None until they mark any).
        marked = (d["shows"] or 0) + (d["no_shows"] or 0)
        d["show_rate"] = round(d["shows"] / marked * 100) if marked else None
        d["patients"] = d["patients"] if d["outcomes_marked"] else None
        items.append(d)

    decided = [d for d in items if d["status"] in ("renewed", "churned")]
    renewed = [d for d in decided if d["status"] == "renewed"]
    churned = [d for d in decided if d["status"] == "churned"]
    days_to_decide = [(d["decided_at"] - d["opened_at"]).days for d in items if d["decided_at"]]
    money = lambda lst: round(sum(d["monthly_value"] or 0 for d in lst), 2)
    reasons = {}
    for d in churned:
        k = d["reason"] or "other"
        reasons[k] = reasons.get(k, 0) + 1
    # Campaigns per client: how many times clients have come back.
    per_client = {}
    for d in items:
        per_client[d["client_id"]] = per_client.get(d["client_id"], 0) + 1

    sig = lambda name: (lambda d: d["signals"].get(name))
    cpb_values = sorted(d["signals"]["cost_per_booking"] for d in decided if d["signals"].get("cost_per_booking") is not None)
    cpb_mid = cpb_values[len(cpb_values) // 2] if cpb_values else None
    correlations = [
        {"key": "goal_hit", "title": "Hit the campaign goal", "buckets": _split(decided, sig("goal_hit"), {True: "Goal hit", False: "Goal missed"})},
        {"key": "health", "title": "Health at campaign end", "buckets": _split(decided, sig("health_band"), {"green": "Green", "yellow": "Yellow", "red": "Red"})},
        {"key": "opened", "title": "Opened the final report", "buckets": _split(decided, lambda d: d["opened_report"], {True: "Opened", False: "Not opened"})},
        {"key": "wants_next", "title": "Asked about a next campaign", "buckets": _split(decided, lambda d: d["wants_next"], {True: "Clicked yes", False: "Didn't"})},
        {"key": "testimonial", "title": "Left a testimonial", "buckets": _split(decided, lambda d: d["testimonial"], {True: "Yes", False: "No"})},
        {"key": "show_rate", "title": "Show rate (visits the clinic marked)", "buckets": _split(decided, lambda d: None if d["show_rate"] is None else d["show_rate"] >= SHOW_TARGET, {True: f"{SHOW_TARGET}% or better", False: f"Under {SHOW_TARGET}%"})},
        {"key": "patients", "title": "New patients from the campaign", "buckets": _split(decided, lambda d: None if d["patients"] is None else ("0" if d["patients"] == 0 else "1-2" if d["patients"] <= 2 else "3+"), {"0": "None", "1-2": "1-2", "3+": "3 or more"})},
        {"key": "outcomes", "title": "Marked show-ups in the portal", "buckets": _split(decided, lambda d: (d["outcomes_marked"] or 0) > 0, {True: "Marked outcomes", False: "Marked none"})},
        {"key": "package", "title": "Package", "buckets": _split(decided, sig("package"), {"growth": "Growth", "foundations": "Foundations"})},
    ]
    if cpb_mid is not None and len(cpb_values) >= 2:
        correlations.append({"key": "cpb", "title": f"Cost per booking (split at ${cpb_mid:,.0f})",
                             "buckets": _split(decided, lambda d: None if d["signals"].get("cost_per_booking") is None
                                               else d["signals"]["cost_per_booking"] <= cpb_mid,
                                               {True: f"${cpb_mid:,.0f} or less", False: f"Over ${cpb_mid:,.0f}"})})

    return {
        "totals": {
            "campaigns_ended": len(items), "decided": len(decided),
            "renewed": len(renewed), "churned": len(churned),
            "paused": sum(1 for d in items if d["status"] == "paused"),
            "pending": sum(1 for d in items if d["status"] == "pending"),
            "churn_rate": _rate(len(churned), len(decided)), "renewal_rate": _rate(len(renewed), len(decided)),
            "avg_days_to_decide": round(sum(days_to_decide) / len(days_to_decide)) if days_to_decide else None,
            "active_clients": active,
            "mrr_kept": money(renewed), "mrr_lost": money(churned),
            "repeat_clients": sum(1 for v in per_client.values() if v > 1), "clients": len(per_client),
        },
        "reasons": [{"key": k, "label": REASONS.get(k, k), "count": v} for k, v in sorted(reasons.items(), key=lambda x: -x[1])],
        "correlations": [c for c in correlations if c["buckets"]],
        "campaigns": [{
            "id": d["id"], "client_id": d["client_id"], "client_name": d["client_name"], "status": d["status"],
            "reason": d["reason"], "reason_label": REASONS.get(d["reason"]) if d["reason"] else None,
            "notes": d["notes"], "plan": d["plan"], "monthly_value": d["monthly_value"],
            "opened_at": d["opened_at"], "decided_at": d["decided_at"], "decided_by": d["decided_by"],
            "suggestion": d["suggestion"], "signals": d["signals"], "opened_report": d["opened_report"],
            "wants_next": d["wants_next"], "testimonial": d["testimonial"], "rating": d["rating"],
            "outcomes_marked": d["outcomes_marked"], "show_rate": d["show_rate"], "patients": d["patients"],
        } for d in items],
    }
