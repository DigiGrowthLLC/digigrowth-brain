"""AI Client Success Manager, part 2 (client_success.py is part 1: reports).

1. Health score: a daily 0-100 per client in a live (or just-ended) campaign,
   from results vs. pace, engagement with reports, the client's own ratings
   and whether their questions got answered. Falling into red puts an
   "at risk" To-Do on Dylan's list with the reasons.
2. Milestones: one short message when a campaign hits a moment worth
   celebrating (first lead, halfway to the goal, goal reached). Every 30 min,
   each sent once per campaign. Text by default (Dylan approved milestone
   texts 2026-11-17), switchable to email or off. Milestones a campaign
   already passed before this shipped are recorded silently, never sent late.
3. Onboarding check-ins: day 1, 3 and 7 after a client is added, until their
   campaign launches. DRAFTED with setup progress and exactly what's still
   needed from them (setup_steps.client_ask); Dylan approves each one in the
   OS before it's emailed. A newer check-in supersedes an unapproved older one.
   Only for clients added on or after CHECKIN_START.
4. Lead quality: when the clinic marks an appointment Showed + Closed in
   their portal, the outcome card asks whether the patient was a good fit
   (+ note). Ratings tag the CRM contact, feed the report's AI write-up, and
   "not a fit" lands on Dylan's To-Do so targeting can change.

Renewal ("your next campaign") and testimonial asks are sections of the
FINAL report (client_success.py), which waits for Dylan's approval.

All settings: Business Resources -> Outreach Templates -> Client Success Reports.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import datetime, timedelta, timezone

from db import get_pool
from merge_fields import first_name_from_owner

import client_success as cs

CHECKIN_START = datetime(2026, 11, 17, tzinfo=timezone.utc)
CHECKIN_DAYS = (1, 3, 7)
MILESTONES = ("first_lead", "halfway", "goal_hit")


# ---------------------------------------------------------------- shared

async def _client_contact(conn, client_id: int) -> dict:
    r = await conn.fetchrow(
        """SELECT c.id, c.name, c.contact_name, c.email, c.phone, c.portal_token, c.booking_notification_name,
                  anchor.phone AS anchor_phone, anchor.email AS anchor_email
           FROM clients c LEFT JOIN contacts anchor ON anchor.client_id = c.id AND anchor.is_client_anchor
           WHERE c.id = $1""", client_id)
    d = dict(r)
    name = (d.get("booking_notification_name") or "").strip()
    d["first_name"] = name.split()[0] if name else (first_name_from_owner(d.get("contact_name")) or "there")
    d["to_email"] = (d.get("email") or d.get("anchor_email") or "").strip()
    d["to_phone"] = (d.get("phone") or d.get("anchor_phone") or "").strip()
    base = (os.environ.get("DASHBOARD_URL") or "").rstrip("/")
    d["portal_link"] = f"{base}/portal/{d['portal_token']}" if d.get("portal_token") else ""
    return d


def _fill(tpl: str, ctx: dict) -> str:
    for k, v in ctx.items():
        tpl = tpl.replace("{" + k + "}", str(v))
    return tpl


async def _email(to: str, subject: str, body: str) -> None:
    import integrations
    await asyncio.to_thread(integrations.gmail_send, to, subject, body, is_automated=True)


# ---------------------------------------------------------------- 1. health score

def _band(score: int) -> str:
    return "green" if score >= 70 else "yellow" if score >= 45 else "red"


async def compute_health(conn, client_id: int) -> dict | None:
    from client_funnel import build_funnel

    win = await cs.campaign_window(conn, client_id)
    if not win["launched_at"]:
        return None
    if win["state"] == "ended" and datetime.now(timezone.utc) - win["ends_at"] > timedelta(days=14):
        return None
    factors, reasons = {}, []

    # Results (45)
    days = (min(datetime.now(timezone.utc), win["ends_at"]) - win["launched_at"]).days
    total = (await build_funnel(client_id, "all"))["kpis"]
    booked, leads = total.get("booked") or 0, total.get("leads") or 0
    if days < 5:
        pts = 35
    elif win["goal"]:
        expected = max(0.5, win["goal"] * min(days, win["length_days"]) / win["length_days"])
        ratio = booked / expected
        pts = round(min(1.0, ratio) * 45)
        if ratio < 0.6:
            reasons.append(f"Behind pace: {booked} booked vs about {expected:.0f} expected by day {days} (goal {win['goal']})")
    else:
        week = (await build_funnel(client_id, "week"))["kpis"]
        pts = 45 if (week.get("booked") or 0) > 0 else 22 if (week.get("leads") or 0) > 0 else 10
        if pts < 45:
            reasons.append("No bookings in the last 7 days" + ("" if week.get("leads") else " and no new leads"))
    factors["results"] = {"points": pts, "of": 45, "booked": booked, "leads": leads}

    # Engagement (25): opened the latest report, gave any input in 30 days
    last = await conn.fetchrow(
        "SELECT view_count, sent_at FROM client_reports WHERE client_id = $1 AND sent_at IS NOT NULL "
        "ORDER BY sent_at DESC LIMIT 1", client_id)
    inputs = await conn.fetchval(
        """SELECT (SELECT count(*) FROM client_report_feedback WHERE client_id = $1 AND created_at > now() - interval '30 days')
                + (SELECT count(*) FROM lead_quality_ratings WHERE client_id = $1 AND created_at > now() - interval '30 days')""",
        client_id)
    if not last:
        pts = 20
    else:
        opened = (last["view_count"] or 0) > 0
        pts = (15 if opened else 0) + (10 if inputs else 0)
        if not opened and datetime.now(timezone.utc) - last["sent_at"] > timedelta(days=2):
            reasons.append("Hasn't opened their latest report")
    factors["engagement"] = {"points": pts, "of": 25, "inputs_30d": inputs}

    # Sentiment (20): most recent rating
    rating = await conn.fetchrow(
        """SELECT f.rating, r.kind FROM client_report_feedback f JOIN client_reports r ON r.id = f.report_id
           WHERE f.client_id = $1 AND f.rating IS NOT NULL ORDER BY f.created_at DESC LIMIT 1""", client_id)
    if rating:
        scale = 10 if rating["kind"] == "final" else 5
        pts = round(rating["rating"] / scale * 20)
        if rating["rating"] / scale <= 0.5:
            reasons.append(f"Last rating was {rating['rating']}/{scale}")
    else:
        pts = 14
    not_fit = await conn.fetchval(
        "SELECT count(*) FROM lead_quality_ratings WHERE client_id = $1 AND rating = 'not_fit' "
        "AND created_at > now() - interval '14 days'", client_id)
    good = await conn.fetchval(
        "SELECT count(*) FROM lead_quality_ratings WHERE client_id = $1 AND rating = 'good' "
        "AND created_at > now() - interval '14 days'", client_id)
    if not_fit >= 2 and not_fit > good:
        pts = max(0, pts - 8)
        reasons.append(f"Rated {not_fit} recent patients 'not a fit'")
    factors["sentiment"] = {"points": pts, "of": 20, "last_rating": rating["rating"] if rating else None}

    # Service (10): their questions answered within 2 days
    waiting = await conn.fetchval(
        "SELECT count(*) FROM client_report_feedback WHERE client_id = $1 AND answer IS NULL AND message <> '' "
        "AND created_at < now() - interval '48 hours'", client_id)
    pts = 0 if waiting else 10
    if waiting:
        reasons.append(f"{waiting} question{'s' if waiting > 1 else ''} unanswered for 2+ days")
    factors["service"] = {"points": pts, "of": 10, "waiting": waiting}

    score = sum(f["points"] for f in factors.values())
    return {"score": score, "band": _band(score), "factors": factors, "reasons": reasons}


async def run_health() -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        ids = [r["id"] for r in await conn.fetch(
            """SELECT c.id FROM clients c JOIN client_marketing_config m ON m.client_id = c.id
               WHERE c.status = 'active' AND NOT coalesce(c.is_test, false) AND m.campaign_launched_at IS NOT NULL""")]
    for cid in ids:
        try:
            async with pool.acquire() as conn:
                h = await compute_health(conn, cid)
                if not h:
                    continue
                prev = await conn.fetchval(
                    "SELECT band FROM client_health WHERE client_id = $1 ORDER BY computed_at DESC LIMIT 1", cid)
                await conn.execute(
                    "INSERT INTO client_health (client_id, score, band, factors, reasons) VALUES ($1,$2,$3,$4::jsonb,$5)",
                    cid, h["score"], h["band"], json.dumps(h["factors"]), h["reasons"])
                if h["band"] == "red" and prev != "red":
                    name = await conn.fetchval("SELECT name FROM clients WHERE id = $1", cid)
                    await cs._todo_once(
                        conn, f"⚠ {name} is at risk (health {h['score']}/100)",
                        "Why:\n- " + "\n- ".join(h["reasons"] or ["Several small signals together"]) +
                        "\n\nSuggested: call them this week. Lead with what's working, own what isn't, and share the "
                        "plan. Details: Outreach Templates -> Client Success Reports -> Clients.")
        except Exception as e:
            print(f"[csm_extras] health failed for {cid}: {e}")


async def latest_health(conn) -> dict[int, dict]:
    rows = await conn.fetch(
        """SELECT DISTINCT ON (client_id) client_id, score, band, factors, reasons, computed_at
           FROM client_health ORDER BY client_id, computed_at DESC""")
    out = {}
    for r in rows:
        d = dict(r)
        d["factors"] = json.loads(d["factors"]) if isinstance(d["factors"], str) else d["factors"]
        out[r["client_id"]] = d
    return out


# ---------------------------------------------------------------- 2. milestones

def _reached(kpis: dict, goal: int | None) -> set[str]:
    out = set()
    booked = kpis.get("booked") or 0
    if (kpis.get("leads") or 0) >= 1:
        out.add("first_lead")
    if goal and goal >= 2 and booked >= -(-goal // 2) and booked < goal:
        out.add("halfway")
    if goal and booked >= goal:
        out.add("goal_hit")
    return out


async def run_milestones() -> None:
    from client_funnel import build_funnel
    from routers import sms as sms_router

    settings = await cs.get_settings()
    channel = (settings.get("csm_milestones_channel") or "sms").lower()
    if channel == "off":
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT c.id FROM clients c JOIN client_marketing_config m ON m.client_id = c.id
               WHERE c.status = 'active' AND NOT coalesce(c.is_test, false) AND m.campaign_launched_at IS NOT NULL
                 AND coalesce(m.csm_reports_enabled, true)""")
    for r in rows:
        cid = r["id"]
        try:
            async with pool.acquire() as conn:
                win = await cs.campaign_window(conn, cid)
                if win["state"] != "running":
                    continue
                kpis = (await build_funnel(cid, "all"))["kpis"]
                reached = _reached(kpis, win["goal"])
                if "goal_hit" in reached:
                    reached.discard("halfway")
                seen = {x["key"] for x in await conn.fetch(
                    "SELECT key FROM client_milestones WHERE client_id = $1 AND campaign_launched_at = $2",
                    cid, win["launched_at"])}
                if not seen:
                    # First look at this campaign: record what's already behind it, send nothing.
                    for key in reached | {"_seeded"}:
                        await conn.execute(
                            "INSERT INTO client_milestones (client_id, campaign_launched_at, key, sent_at) "
                            "VALUES ($1,$2,$3,NULL) ON CONFLICT DO NOTHING", cid, win["launched_at"], key)
                    if (datetime.now(timezone.utc) - win["launched_at"]) > timedelta(hours=6):
                        continue
                    reached = set()  # brand-new campaign: nothing reached yet anyway
                new = [k for k in MILESTONES if k in reached and k not in seen]
                if not new:
                    continue
                key = new[-1]  # the biggest one if several landed at once
                for k in new:
                    await conn.execute(
                        "INSERT INTO client_milestones (client_id, campaign_launched_at, key, sent_at) "
                        "VALUES ($1,$2,$3,$4) ON CONFLICT DO NOTHING",
                        cid, win["launched_at"], k, datetime.now(timezone.utc) if k == key else None)
                c = await _client_contact(conn, cid)
                ctx = {"first_name": c["first_name"], "clinic": c["name"], "booked": kpis.get("booked") or 0,
                       "goal": win["goal"] or "", "leads": kpis.get("leads") or 0}
                text = _fill(settings.get(f"csm_ms_{key}") or "", ctx).strip()
                if not text:
                    continue
                if channel == "sms" and c["to_phone"]:
                    sms_router._send_twilio(c["to_phone"], text)
                elif c["to_email"]:
                    await _email(c["to_email"], f"{c['name']}: campaign update", text + "\n\nDylan\nDigiGrowth")
                print(f"[csm_extras] milestone {key} sent to client {cid}")
        except Exception as e:
            print(f"[csm_extras] milestone check failed for {cid}: {e}")


# ---------------------------------------------------------------- 3. onboarding check-ins

def _needs_from_ask(ask: str) -> str:
    lines = [l for l in ask.splitlines() if re.match(r"^\d+\. ", l)]
    return "\n".join(lines) if lines else "Nothing right now. We're handling the rest."


async def run_checkins() -> None:
    """Drafts the due check-in for Dylan to approve (never emails on its own)."""
    import setup_steps
    settings = await cs.get_settings()
    if not cs._on(settings.get("csm_checkins_enabled", "on")):
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT c.id, c.created_at FROM clients c LEFT JOIN client_marketing_config m ON m.client_id = c.id
               WHERE c.status = 'active' AND NOT coalesce(c.is_test, false) AND c.created_at >= $1
                 AND m.campaign_launched_at IS NULL""", CHECKIN_START)
    now = datetime.now(timezone.utc)
    for r in rows:
        cid, age = r["id"], (now - r["created_at"]).days
        due = [d for d in CHECKIN_DAYS if age >= d]
        if not due:
            continue
        key = f"d{due[-1]}"
        try:
            async with pool.acquire() as conn:
                if await conn.fetchval("SELECT 1 FROM client_checkins WHERE client_id = $1 AND key = $2", cid, key):
                    continue
                c = await _client_contact(conn, cid)
            st = await setup_steps.status(cid)
            ctx = {"first_name": c["first_name"], "clinic": c["name"], "done": st.get("done", 0),
                   "total": st.get("total", 0), "needs": _needs_from_ask(st.get("client_ask") or ""),
                   "portal_link": c["portal_link"], "day": due[-1]}
            async with pool.acquire() as conn:
                # An older draft nobody approved is out of date now: this one replaces it.
                await conn.execute("UPDATE client_checkins SET status = 'dismissed' WHERE client_id = $1 AND status = 'draft'", cid)
                await conn.execute(
                    """INSERT INTO client_checkins (client_id, key, subject, body, status) VALUES ($1,$2,$3,$4,'draft')
                       ON CONFLICT DO NOTHING""",
                    cid, key, _fill(settings["csm_checkin_subject"], ctx), _fill(settings["csm_checkin_body"], ctx))
                await cs._todo_once(conn, f"Approve {c['name']}'s day {due[-1]} onboarding check-in",
                                    "Drafted with their live setup progress. Review, edit if needed and send: "
                                    "Outreach Templates -> Client Success Reports -> Onboarding Check-ins."
                                    + ("" if c["to_email"] else "\n\nNo email on file for this client yet."))
            print(f"[csm_extras] onboarding check-in {key} drafted for client {cid}")
        except Exception as e:
            print(f"[csm_extras] check-in failed for {cid}: {e}")


async def send_checkin(client_id: int, key: str, subject: str, body: str) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT status FROM client_checkins WHERE client_id = $1 AND key = $2", client_id, key)
        if not row:
            return {"ok": False, "error": "Check-in not found"}
        if row["status"] == "sent":
            return {"ok": False, "error": "Already sent"}
        c = await _client_contact(conn, client_id)
        if not c["to_email"]:
            return {"ok": False, "error": "No email on file for this client"}
        await _email(c["to_email"], subject, body)
        await conn.execute("UPDATE client_checkins SET subject = $3, body = $4, status = 'sent', sent_at = now() "
                           "WHERE client_id = $1 AND key = $2", client_id, key, subject, body)
    return {"ok": True}


# ---------------------------------------------------------------- 4. lead quality

async def booked_patients(conn, client_id: int, days: int = 45) -> list[dict]:
    launched = await conn.fetchval(
        "SELECT campaign_launched_at FROM client_marketing_config WHERE client_id = $1", client_id)
    rows = await conn.fetch(
        """SELECT a.id, a.prospect_name, a.appointment_at, a.status, a.outcome_show, a.outcome_close, a.created_at,
                  q.rating, q.note
           FROM appointment_reminders a JOIN contacts c ON c.id = a.contact_id
           LEFT JOIN lead_quality_ratings q ON q.appointment_id = a.id
           WHERE c.client_id = $1 AND NOT c.is_client_anchor
             AND a.created_at > now() - make_interval(days => $2)
             AND ($3::timestamptz IS NULL OR a.created_at >= $3)
             AND coalesce(c.lead_source, '') NOT IN ('past_patient', 'import')
           ORDER BY (q.rating IS NULL) DESC, a.appointment_at DESC LIMIT 60""",
        client_id, days, launched)
    out = []
    for r in rows:
        parts = (r["prospect_name"] or "Patient").split()
        name = parts[0] + (f" {parts[-1][0]}." if len(parts) > 1 else "")
        out.append({"appointment_id": r["id"], "name": name, "appointment_at": r["appointment_at"].isoformat(),
                    "status": r["status"], "showed": r["outcome_show"], "closed": r["outcome_close"],
                    "rating": r["rating"], "note": r["note"]})
    return out


async def rate_patient(client_id: int, appointment_id: int, rating: str, note: str) -> bool:
    if rating not in ("good", "not_fit"):
        raise ValueError("rating must be good or not_fit")
    note = (note or "").strip()[:1000]
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT a.id, a.contact_id, a.prospect_name FROM appointment_reminders a JOIN contacts c ON c.id = a.contact_id
               WHERE a.id = $1 AND c.client_id = $2""", appointment_id, client_id)
        if not row:
            return False
        await conn.execute(
            """INSERT INTO lead_quality_ratings (client_id, appointment_id, contact_id, rating, note)
               VALUES ($1,$2,$3,$4,$5)
               ON CONFLICT (appointment_id) DO UPDATE SET rating = $4, note = $5, created_at = now()""",
            client_id, appointment_id, row["contact_id"], rating, note or None)
        tag, other = ("Good Fit", "Not A Fit") if rating == "good" else ("Not A Fit", "Good Fit")
        await conn.execute(
            "UPDATE contacts SET tags = array_append(array_remove(coalesce(tags, '{}'), $2), $3) WHERE id = $1",
            row["contact_id"], other, tag)
        if rating == "not_fit":
            name = await conn.fetchval("SELECT name FROM clients WHERE id = $1", client_id)
            await cs._todo_once(
                conn, f"Lead quality: {name} flagged patients as not a fit",
                "Review their notes (Outreach Templates -> Client Success Reports -> Lead Quality) and adjust "
                f"targeting or ad copy.\n\nLatest: {row['prospect_name'] or 'a patient'}: {note or '(no note)'}")
    return True


async def lead_quality_summary(conn, client_id: int, days: int = 30) -> dict | None:
    rows = await conn.fetch(
        "SELECT rating, note FROM lead_quality_ratings WHERE client_id = $1 AND created_at > now() - make_interval(days => $2)",
        client_id, days)
    # Rated from the outcome card, which asks only once a patient is marked Showed + Closed.
    unrated = len([p for p in await booked_patients(conn, client_id, days)
                   if not p["rating"] and p["showed"] == "show" and p["closed"] == "closed"])
    if not rows and not unrated:
        return None
    return {"good": sum(1 for r in rows if r["rating"] == "good"),
            "not_fit": sum(1 for r in rows if r["rating"] == "not_fit"),
            "notes": [r["note"] for r in rows if r["note"]][:8], "unrated": unrated}


# ---------------------------------------------------------------- schedulers

async def run_daily() -> None:
    """10:05 ET, after the reports: health scores and onboarding check-in drafts."""
    await run_health()
    settings = await cs.get_settings()
    if cs._on(settings["csm_enabled"]):
        await run_checkins()
