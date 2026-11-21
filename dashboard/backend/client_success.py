"""AI Client Success Manager (CSM): weekly campaign reports + one final
report per client, sent automatically, each with a questions/suggestions
form so the client feels involved.

Lifecycle (run_daily(), every day 10:00 ET from main.py). Weekly reports are
auto-sent; the FINAL report is built as a draft and waits for Dylan's
approval (To-Do + "Approve & send" in the OS). It carries two extra sections:
"Your next campaign" (Claude's plan from the real results, renewal ask) and
"Share your experience" (testimonial ask).
  - A client is "in campaign" from client_marketing_config.campaign_launched_at
    (first day with ad spend, meta_ads.py) until campaign_ended_at (set by
    hand) or launched + campaign_length_days (default 30).
  - Mondays, while in campaign and at least 5 days since launch: one WEEKLY
    report per campaign week (week number = weeks since launch).
  - The first run after the campaign ends: one FINAL report for the whole
    campaign. No weekly reports after that.
  - Skipped: test clients, inactive clients, csm_reports_enabled = false,
    or the global switch (Outreach Templates -> Client Success Reports) off.

Each report is a public page at <pages domain>/report/<slug> (unguessable
slug, no login, same hosting as /lp pages), stored in client_reports with the
numbers it was built from (data JSONB) so next week can compare and the
final report can chart every week. The written analysis (what's on target,
what isn't, what we'll improve) comes from Claude via the API, given only
the real numbers; if that call fails the report still goes out with a
plain rule-based write-up.

Delivery: email by default (plain text with the link). SMS is a separate
switch and OFF by default: Dylan's rule is to text clients only when it's
necessary. Every report is also listed in the client's portal.

Client questions/suggestions (client_report_feedback) land on Dylan's
To-Do list. His answers can be emailed back from the OS and are shown at
the top of the next report ("You asked, we answered").

Editable from Business Resources -> Outreach Templates -> "Client Success
Reports" (dialer_settings keys below + per-client settings).
"""

from __future__ import annotations

import asyncio
import html
import json
import math
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from db import get_pool
from merge_fields import first_name_from_owner

ET = ZoneInfo("America/New_York")

TEMPLATE_DEFAULTS = {
    "csm_enabled": "on",
    "csm_send_email": "on",
    "csm_send_sms": "off",
    "csm_weekly_email_subject": "{clinic}: your week {week} campaign report",
    "csm_weekly_email_body": (
        "Hi {first_name},\n\n"
        "Your week {week} campaign report is ready: {link}\n\n"
        "It covers how the campaign performed this week, what's on target, what isn't yet, "
        "and what we're changing next. At the bottom there's a box for any questions or "
        "suggestions. I read every one and answer it before the next report.\n\n"
        "Dylan\nDigiGrowth"
    ),
    "csm_weekly_sms": "Hi {first_name}, your week {week} campaign report is ready: {link} Any questions or ideas, there's a box at the bottom.",
    "csm_final_email_subject": "{clinic}: your final campaign report",
    "csm_final_email_body": (
        "Hi {first_name},\n\n"
        "Your campaign wrapped up, and here's the full report on how it performed from start "
        "to finish: {link}\n\n"
        "It has the totals, how each week went, what worked best, and what I'd recommend next. "
        "I'd really value your feedback at the bottom of the page.\n\n"
        "Dylan\nDigiGrowth"
    ),
    "csm_final_sms": "Hi {first_name}, your final campaign report is ready: {link} I'd love your feedback at the bottom.",
    "csm_ai_brief": (
        "Write like Dylan, the owner of DigiGrowth, talking to a clinic owner he respects: "
        "warm, direct, plain English, no marketing jargon (say 'cost per booking', not 'CPA'). "
        "Lead with what matters most to them: booked patients. Be honest about anything behind "
        "target and always pair it with what we're doing about it. Never blame the clinic. "
        "Where their team affects results (answering texts fast, showing patients up, telling "
        "us lead quality), ask for it as a partner, not a complaint."
    ),
    "csm_category": "Client Success",
    # Milestones (csm_extras.py): sms | email | off. Texts: plain characters only (GSM-7).
    "csm_milestones_channel": "sms",
    "csm_ms_first_lead": "Hi {first_name}, your campaign is live and the first lead just came in. Your AI assistant is already texting them. Dylan, DigiGrowth",
    "csm_ms_halfway": "Hi {first_name}, quick win: {booked} of your {goal} booked so far. We're halfway there. Dylan, DigiGrowth",
    "csm_ms_goal_hit": "Hi {first_name}, we hit the goal: {booked} patients booked, {goal} promised. Everything from here is extra. Thank you for trusting us! Dylan, DigiGrowth",
    # Onboarding check-ins (day 1, 3, 7 until launch)
    "csm_checkins_enabled": "on",
    "csm_checkin_subject": "{clinic}: setup update",
    "csm_checkin_body": (
        "Hi {first_name},\n\n"
        "Quick update on getting {clinic} live: {done} of {total} setup steps are done.\n\n"
        "What we still need from you:\n{needs}\n\n"
        "Everything else is on our side. You can see progress any time in your portal: {portal_link}\n\n"
        "Reply here if anything's unclear and I'll help.\n\nDylan\nDigiGrowth"
    ),
    # Final report: the "Share your experience" section ({review_link_line} = Google review ask
    # when DIGIGROWTH_REVIEW_URL is set, else empty).
    "csm_final_testimonial_text": (
        "If the campaign made a difference for {clinic}, would you share a couple of sentences about working with us? "
        "Write whatever comes to mind in the box below: what it was like before, and what changed. "
        "A short phone video works too if you're up for it (just reply to the report email with it). {review_link_line}"
    ),
}

DEFAULT_LENGTH_DAYS = 30


# ---------------------------------------------------------------- settings

async def get_settings(conn=None) -> dict:
    async def _read(c):
        rows = await c.fetch("SELECT key, value FROM dialer_settings WHERE key = ANY($1)",
                             list(TEMPLATE_DEFAULTS.keys()))
        vals = {r["key"]: r["value"] for r in rows if r["value"] is not None}
        return {k: vals.get(k, d) for k, d in TEMPLATE_DEFAULTS.items()}
    if conn is not None:
        return await _read(conn)
    pool = await get_pool()
    async with pool.acquire() as c:
        return await _read(c)


async def save_settings(body: dict) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        for key in TEMPLATE_DEFAULTS:
            if key in body and body[key] is not None:
                await conn.execute(
                    """INSERT INTO dialer_settings (key, value, updated_at) VALUES ($1, $2, now())
                       ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = now()""",
                    key, str(body[key]))


def _on(v) -> bool:
    return str(v or "").strip().lower() in ("on", "true", "1", "yes")


def public_base() -> str:
    return (os.environ.get("LANDING_PAGES_URL") or os.environ.get("DASHBOARD_URL") or "").rstrip("/")


def report_url(slug: str) -> str:
    return f"{public_base()}/report/{slug}"


# ---------------------------------------------------------------- campaign window

async def campaign_window(conn, client_id: int) -> dict:
    """The current campaign's window. A campaign ends at the first of:
    campaign_ended_at (set by hand), the ad spend cap being reached
    (ad_spend_caps.cap_reached_at, Dylan 2026-11-17: "the campaign is over
    when the ad budget is spent"), or launch + campaign_length_days. With a
    cap and no length set it runs until the budget is spent. `budget` gives
    spend vs cap, which also drives the goal pace."""
    row = await conn.fetchrow(
        """SELECT m.campaign_launched_at, m.campaign_ended_at, m.campaign_length_days,
                  m.campaign_booking_goal, m.campaign_goal_label, coalesce(m.csm_reports_enabled, true) AS enabled,
                  c.cap, c.last_spend, c.enabled AS cap_on, c.cap_reached_at, c.last_checked_at
           FROM client_marketing_config m LEFT JOIN ad_spend_caps c ON c.client_id = m.client_id
           WHERE m.client_id = $1""",
        client_id)
    goal = row["campaign_booking_goal"] if row else None
    label = ((row["campaign_goal_label"] if row else None) or "bookings").strip() or "bookings"
    budget = None
    if row and row["cap_on"] and row["cap"]:
        cap, spent = float(row["cap"]), float(row["last_spend"] or 0)
        budget = {"cap": cap, "spent": round(spent, 2), "pct": min(100, round(spent / cap * 100)), "reached": spent >= cap}
    length = int(row["campaign_length_days"]) if row and row["campaign_length_days"] else None
    base = {"goal": goal, "goal_label": label, "enabled": row["enabled"] if row else True, "budget": budget,
            "length_days": length or (None if budget else DEFAULT_LENGTH_DAYS)}
    if not row or not row["campaign_launched_at"]:
        return {**base, "launched_at": None, "ends_at": None, "state": "not_launched"}
    launched = row["campaign_launched_at"]
    now = datetime.now(timezone.utc)
    candidates = []
    if row["campaign_ended_at"]:
        candidates.append(row["campaign_ended_at"])
    if budget and budget["reached"]:
        candidates.append(row["cap_reached_at"] or row["last_checked_at"] or now)
    if length or not budget:
        candidates.append(launched + timedelta(days=length or DEFAULT_LENGTH_DAYS))
    ends = min(candidates) if candidates else None
    ended = bool(ends and now >= ends)
    upto = min(now, ends) if ends else now
    return {
        **base, "launched_at": launched, "ends_at": ends,
        "state": "ended" if ended else "running",
        "days_elapsed": max(0, (upto - launched).days),
        "week": max(1, math.ceil(max(1, (upto - launched).days) / 7)),
    }


# ---------------------------------------------------------------- data

async def _ai_agent_stats(client_id: int, days: int | None) -> dict | None:
    try:
        from routers.client_marketing import response_ai_stats
        return dict(await response_ai_stats(client_id, days))
    except Exception as e:
        print(f"[client_success] ai stats failed for {client_id}: {e}")
        return None


_ANSWERED = "('answered', 'booked', 'not_interested')"


async def _comms_stats(client_id: int, since: datetime) -> dict | None:
    """Texts and AI calls for the report's "Texts and calls" section (Dylan,
    2026-11-19), from `since` on. Test numbers and test calls are left out.
    Texts are grouped by their stage (who/what sent them)."""
    from client_funnel import _not_test
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            lead = "(CASE WHEN direction = 'outbound' THEN to_number ELSE from_number END)"
            t = await conn.fetchrow(
                rf"""SELECT
                       count(*) FILTER (WHERE direction = 'outbound') AS sent,
                       count(*) FILTER (WHERE direction = 'inbound') AS received,
                       count(DISTINCT right(regexp_replace({lead}, '\D', '', 'g'), 10)) FILTER (WHERE direction = 'outbound') AS people_texted,
                       count(DISTINCT right(regexp_replace({lead}, '\D', '', 'g'), 10)) FILTER (WHERE direction = 'inbound') AS people_replied,
                       count(*) FILTER (WHERE direction = 'outbound' AND (stage IN ('ai_reply', 'dm_handoff') OR stage LIKE '%opener%')) AS by_ai,
                       count(*) FILTER (WHERE direction = 'outbound' AND (stage = 'manual_reply' OR stage IS NULL)) AS by_team,
                       count(*) FILTER (WHERE direction = 'outbound' AND (stage LIKE 'prospect_followup%' OR stage LIKE '%abandon%')) AS followups,
                       count(*) FILTER (WHERE direction = 'outbound' AND stage LIKE 'reactivation%') AS reactivation,
                       count(*) FILTER (WHERE direction = 'outbound' AND (stage LIKE 'appointment_reminder%' OR stage LIKE '%no_show%'
                                        OR stage LIKE '%cancel%' OR stage LIKE 'booking%' OR stage LIKE 'reschedule%')) AS appointment
                     FROM client_sms_messages
                     WHERE client_id = $1 AND created_at >= $2 AND {_not_test(lead)}""",
                client_id, since)
            calls = await conn.fetch(
                f"""SELECT coalesce(agent_kind, 'ads') AS kind,
                       count(*) FILTER (WHERE dialed_at IS NOT NULL) AS placed,
                       count(DISTINCT phone) FILTER (WHERE dialed_at IS NOT NULL) AS people,
                       count(DISTINCT phone) FILTER (WHERE outcome IN {_ANSWERED}) AS reached,
                       count(*) FILTER (WHERE outcome = 'voicemail') AS voicemails,
                       count(*) FILTER (WHERE outcome = 'no_answer') AS no_answer,
                       count(DISTINCT phone) FILTER (WHERE outcome = 'booked') AS booked,
                       coalesce(sum(duration_ms) FILTER (WHERE outcome IN {_ANSWERED}), 0) AS talk_ms
                    FROM client_voice_calls
                    WHERE client_id = $1 AND source != 'test' AND coalesce(dialed_at, run_at) >= $2 AND {_not_test('phone')}
                    GROUP BY 1""",
                client_id, since)
        texts = dict(t)
        texts["reply_rate"] = round(texts["people_replied"] / texts["people_texted"] * 100) if texts["people_texted"] else None
        by_kind = {r["kind"]: dict(r) for r in calls}
        total = {k: sum((r[k] or 0) for r in by_kind.values())
                 for k in ("placed", "people", "reached", "voicemails", "no_answer", "booked", "talk_ms")}
        total["talk_minutes"] = round(total.pop("talk_ms") / 60000)
        for r in by_kind.values():
            r["talk_minutes"] = round(r.pop("talk_ms") / 60000)
        total["reach_rate"] = round(total["reached"] / total["people"] * 100) if total["people"] else None
        return {"since": since.isoformat(), "texts": texts,
                "calls": {"total": total, "ad_leads": by_kind.get("ads"), "reactivation": by_kind.get("react")}}
    except Exception as e:
        print(f"[client_success] comms stats failed for {client_id}: {e}")
        return None


def _for_prompt(data: dict) -> dict:
    """The report data minus the per-path journey (the page's layout data;
    the flat `stages` list already gives Claude the same numbers)."""
    out = dict(data)
    for key in ("week", "to_date"):
        if isinstance(out.get(key), dict):
            out[key] = {k: v for k, v in out[key].items() if k != "paths"}
    return out


def _slim_funnel(f: dict) -> dict:
    """The parts of client_funnel.build_funnel the report uses."""
    stages = []
    for p in f.get("paths", []):
        for s in p.get("stages", []):
            if not s.get("available", True):
                continue
            stages.append({"path": p.get("label"), "label": s.get("label"), "count": s.get("value"),
                           "rate": s.get("rate"), "status": s.get("status"),
                           "target": (s.get("target") or {}).get("good")})
    # Per-path journey for the report page (laid out like the portal's Results tab).
    paths = [{"key": p.get("key"), "label": p.get("label"),
              "stages": [{k: s.get(k) for k in ("key", "label", "value", "rate", "rate_basis", "status", "note", "available")}
                         | {"target": (s.get("target") or {}).get("good")} for s in p.get("stages", [])]}
             for p in f.get("paths", [])]
    return {"kpis": f.get("kpis", {}), "stages": stages, "paths": paths, "biggest_leak": f.get("biggest_leak"),
            "meta_connected": (f.get("meta") or {}).get("connected"), "paid_offer": f.get("paid_offer")}


async def gather(client_id: int, kind: str) -> dict:
    """Every number a report needs, as a JSON-able dict."""
    from client_funnel import build_funnel

    pool = await get_pool()
    async with pool.acquire() as conn:
        client = dict(await conn.fetchrow(
            "SELECT id, name, contact_name, email, phone, booking_notification_name FROM clients WHERE id = $1",
            client_id))
        # Clinic logo for the report's "clinic x DigiGrowth" lockup (same one the booking page uses).
        try:
            logo_url = await conn.fetchval("SELECT logo_url FROM booking_settings WHERE client_id = $1", client_id)
        except Exception:
            logo_url = None
        win = await campaign_window(conn, client_id)
        prev = await conn.fetch(
            """SELECT kind, week_number, period_start, period_end, data FROM client_reports
               WHERE client_id = $1 AND campaign_launched_at = $2 AND kind = 'weekly'
               ORDER BY week_number""",
            client_id, win["launched_at"])
        open_fb = await conn.fetch(
            """SELECT kind, message, answer, rating, created_at FROM client_report_feedback
               WHERE client_id = $1 AND created_at > now() - interval '45 days'
               ORDER BY created_at""", client_id)

    total = _slim_funnel(await build_funnel(client_id, "all"))
    data = {
        "client": {"id": client["id"], "name": client["name"], "logo_url": logo_url,
                   "first_name": (client.get("booking_notification_name") or "").split()[0]
                   if (client.get("booking_notification_name") or "").strip()
                   else first_name_from_owner(client.get("contact_name"))},
        "kind": kind,
        "campaign": {
            "launched_at": win["launched_at"].isoformat() if win["launched_at"] else None,
            "ends_at": win["ends_at"].isoformat() if win["ends_at"] else None,
            "length_days": win["length_days"], "days_elapsed": win.get("days_elapsed"),
            "week": win.get("week"), "goal": win["goal"], "goal_label": win["goal_label"], "budget": win.get("budget"),
        },
        "to_date": total,
        "ai_agent_to_date": await _ai_agent_stats(client_id, None),
        "weeks": [{"week": r["week_number"], "kpis": (json.loads(r["data"]) if isinstance(r["data"], str) else r["data"]).get("week", {}).get("kpis", {})}
                  for r in prev],
        "client_feedback": [{"kind": r["kind"], "message": r["message"], "answer": r["answer"], "rating": r["rating"]}
                            for r in open_fb],
    }
    try:
        import csm_extras
        async with pool.acquire() as conn:
            data["lead_quality"] = await csm_extras.lead_quality_summary(conn, client_id)
    except Exception as e:
        print(f"[client_success] lead quality summary failed for {client_id}: {e}")
    launched = win["launched_at"] or (datetime.now(timezone.utc) - timedelta(days=90))
    data["comms_to_date"] = await _comms_stats(client_id, launched)
    if kind == "weekly":
        data["week"] = _slim_funnel(await build_funnel(client_id, "week"))
        data["ai_agent_week"] = await _ai_agent_stats(client_id, 7)
        data["comms_week"] = await _comms_stats(client_id, max(launched, datetime.now(timezone.utc) - timedelta(days=7)))
        data["last_week"] = data["weeks"][-1] if data["weeks"] else None

    goal = win["goal"]
    booked = (total["kpis"] or {}).get("booked") or 0
    if goal and (win.get("budget") or win.get("length_days")):
        # Pace by budget spent when there's a cap, else by days elapsed.
        frac = (win["budget"]["spent"] / win["budget"]["cap"]) if win.get("budget") else \
            (win.get("days_elapsed") or 0) / win["length_days"]
        expected = goal * min(1.0, frac)
        data["pace"] = {"goal": goal, "booked": booked, "expected_by_now": round(expected, 1),
                        "on_pace": booked >= math.floor(expected), "pct_of_goal": round(booked / goal * 100)}
    return data


# ---------------------------------------------------------------- AI write-up

_SCHEMA_HINT = """Return ONLY a JSON object, no prose around it:
{
  "headline": "the single most important takeaway in 10 words or fewer, one short clause, no client name (e.g. '11 consultations booked, beating the goal of 10.')",
  "summary": "2-4 sentences, plain English",
  "on_target": ["short bullet", ...],          // 1-4 things going well, with the number
  "off_target": ["short bullet", ...],         // 0-4 things behind target, with the number and why it matters
  "next_steps": ["short bullet", ...],         // 2-4 concrete things DigiGrowth will do next week (final: recommendations for what's next)
  "client_asks": ["short bullet", ...],        // 0-2 things the clinic's team can do that help results (fast replies, show-ups, feedback on lead quality)
  "questions_for_client": ["question", ...]    // 1-2 specific questions inviting their input (e.g. lead quality, which patients they want more of)
}
FINAL report only, also include:
  "next_campaign": {
    "intro": "1-2 sentences: what the results so far set up for a next campaign",
    "plan": ["short bullet", ...],             // 3 specific things the next campaign would do better or scale, drawn from the data
    "ask": "one sentence inviting them to a 15-minute call about the next campaign"
  }
  (never quote prices, packages, budgets or offer terms here)"""


def _system_prompt(brief: str, kind: str) -> str:
    what = ("a WEEKLY campaign report (this week vs. last week and campaign-to-date)"
            if kind == "weekly" else
            "the FINAL report for a campaign that just ended (whole-campaign results, week-by-week trend, "
            "what worked, lessons, and recommendations for what comes next)")
    return (
        "You are DigiGrowth's client success manager. DigiGrowth runs Meta ads, a booking funnel, and "
        "an AI text agent that books new patients for physical therapy and similar clinics. You are writing "
        f"the analysis section of {what} for the clinic owner.\n\n"
        f"Voice and tone:\n{brief}\n\n"
        "Hard rules:\n"
        "- Use ONLY the numbers in the data. Never invent, estimate, or round a number into something it isn't. "
        "If a metric is null or marked low data, say it's too early to read rather than guessing.\n"
        "- Targets: each funnel stage has a 'target' (good-at-or-above %). 'status' good/ok/poor/low_data is already computed; trust it.\n"
        "- 'pace' (if present) compares bookings to the campaign goal; mention it near the top. The goal counts "
        "campaign.goal_label (e.g. 'consultations', 'assessments'): use that word, not 'bookings'. "
        "campaign.budget (if present) is ad spend vs the ad budget; the campaign ends when it's spent.\n"
        "- Never quote prices or offer terms unless they appear in the data. No em dashes.\n"
        "- If the client asked questions or left suggestions, acknowledge them where relevant.\n"
        "- 'lead_quality' (if present) is the clinic's own rating of booked patients (good fit / not a fit + notes). "
        "Treat it as the most important signal about targeting: thank them for rating, and turn 'not a fit' notes into "
        "a concrete next step. If 'unrated' > 0, one client_asks bullet should ask them to answer 'good fit?' for those "
        "patients when marking appointments in their portal.\n"
        "- The quick read (on_target, off_target, next_steps, client_asks) is scanned in seconds by a busy owner: "
        "at most 3 bullets per list (client_asks at most 2), each one plain sentence under 15 words, one idea each, "
        "no jargon (say 'people who clicked', not 'CTR'). Don't repeat the same point across lists; leave a list "
        "short rather than padding it.\n"
        + ("- The campaign is OVER: write the headline, summary, on_target and off_target in the past tense "
           "('the ads brought in 31 leads', 'fewer people showed up than we wanted'). next_steps are recommendations "
           "for the next campaign.\n" if kind == "final" else "")
        + "- 'comms_to_date' / 'comms_week' are the texts and AI phone calls (texts by who sent them; calls split into "
        "new ad leads and reactivation, with people reached, voicemails and bookings). When calls were made, give them "
        "a line in the quick read (e.g. how many people the AI reached and booked by phone).\n"
        + "- The standard flow is ad -> funnel page -> booking page (path 'page'). An 'Instant Form ads' path means the "
        "campaign used Meta's Instant Forms instead; describe only the paths in the data and never invent a funnel "
        "page step that isn't there.\n\n"
        + _SCHEMA_HINT
    )


def _extract_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON in model output")
    return json.loads(m.group(0))


async def write_analysis(data: dict, brief: str) -> tuple[dict, str]:
    """(analysis, source) where source is 'ai' or 'rules'."""
    try:
        import anthropic
        api = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        resp = await asyncio.to_thread(
            api.messages.create,
            model=os.environ.get("CSM_MODEL", "claude-opus-5-5"),
            max_tokens=16000,
            system=_system_prompt(brief, data["kind"]),
            messages=[{"role": "user", "content": "Report data:\n" + json.dumps(_for_prompt(data), default=str, indent=1)}],
        )
        text = "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text")
        out = _extract_json(text)
        for k in ("on_target", "off_target", "next_steps", "client_asks", "questions_for_client"):
            out[k] = [str(x) for x in (out.get(k) or [])][:5]
        nc = out.get("next_campaign") if isinstance(out.get("next_campaign"), dict) else None
        out["next_campaign"] = {"intro": str(nc.get("intro") or ""), "plan": [str(x) for x in (nc.get("plan") or [])][:4],
                                "ask": str(nc.get("ask") or "")} if nc else None
        out["headline"] = str(out.get("headline") or "")
        out["summary"] = str(out.get("summary") or "")
        return out, "ai"
    except Exception as e:
        print(f"[client_success] AI write-up failed, using rules: {e}")
        return _rules_analysis(data), "rules"


def _rules_analysis(data: dict) -> dict:
    scope = data.get("week") or data["to_date"]
    k = scope.get("kpis") or {}
    on, off = [], []
    for s in scope.get("stages", []):
        if s["status"] == "good":
            on.append(f"{s['label']}: {s['rate']}% (target {s['target']}%)")
        elif s["status"] == "poor":
            off.append(f"{s['label']}: {s['rate']}% (target {s['target']}%)")
    leak = scope.get("biggest_leak")
    steps = [f"Focus on {leak['label'].lower()}, the step furthest below target."] if leak else []
    steps.append("Keep testing new ad creative to find the next winner.")
    when = "this week" if data["kind"] == "weekly" else "this campaign"
    return {
        "headline": f"{k.get('booked') or 0} booked {when} from {k.get('leads') or 0} leads.",
        "summary": "Here's where the campaign stands. Full numbers are below.",
        "on_target": on[:4], "off_target": off[:4], "next_steps": steps, "client_asks": [],
        "questions_for_client": ["How has the quality of the patients coming in felt to you so far?"],
        "next_campaign": None if data["kind"] == "weekly" else {
            "intro": "The ads now know who your patients are, so a next campaign starts from a much stronger place than this one did.",
            "plan": ["Start from the best-performing ads instead of from scratch", f"Fix {leak['label'].lower()}" if leak else "Test fresh creative",
                     "Bring back past patients with a reactivation round"],
            "ask": "Do you have 15 minutes this week to talk about the next campaign?"},
    }


# ---------------------------------------------------------------- HTML

# The page itself lives in client_report_html.py (redesigned 2026-11-17).
from client_report_html import render_html  # noqa: E402,F401


# ---------------------------------------------------------------- create + send

def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (name or "client").lower()).strip("-")[:40] or "client"


async def create_report(client_id: int, kind: str, send: bool = True) -> dict:
    """Builds (and by default sends) one report. Returns the stored row."""
    if kind not in ("weekly", "final"):
        raise ValueError("kind must be weekly or final")
    settings = await get_settings()
    data = await gather(client_id, kind)
    analysis, source = await write_analysis(data, settings["csm_ai_brief"])

    camp = data["campaign"]
    now = datetime.now(timezone.utc)
    if kind == "weekly":
        period_start = max(datetime.fromisoformat(camp["launched_at"]), now - timedelta(days=7)) if camp["launched_at"] else now - timedelta(days=7)
        week_number = camp.get("week") or 1
    else:
        period_start = datetime.fromisoformat(camp["launched_at"]) if camp["launched_at"] else now
        week_number = None
    period_end = min(now, datetime.fromisoformat(camp["ends_at"])) if camp["ends_at"] else now

    slug = f"{_slugify(data['client']['name'])}-{'w%d' % week_number if kind == 'weekly' else 'final'}-{secrets.token_hex(5)}"
    report = {"kind": kind, "week_number": week_number, "data": data, "analysis": analysis,
              "testimonial_text": settings.get("csm_final_testimonial_text") or TEMPLATE_DEFAULTS["csm_final_testimonial_text"],
              "period_start": period_start.isoformat(), "period_end": period_end.isoformat()}
    page = render_html(report)

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO client_reports (client_id, kind, week_number, campaign_launched_at, period_start, period_end,
                   slug, html, data, analysis, analysis_source)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10::jsonb,$11) RETURNING *""",
            client_id, kind, week_number,
            datetime.fromisoformat(camp["launched_at"]) if camp["launched_at"] else None,
            period_start, period_end, slug, page,
            json.dumps({"week": data.get("week"), "to_date": data["to_date"], "pace": data.get("pace")}, default=str),
            json.dumps(analysis), source)
    out = dict(row)
    if send:
        out.update(await send_report(out["id"]))
    return out


def _fill(tpl: str, ctx: dict) -> str:
    for k, v in ctx.items():
        tpl = tpl.replace("{" + k + "}", str(v))
    return tpl


async def send_report(report_id: int) -> dict:
    """Emails (and optionally texts) the report link to the client. Never
    raises; problems become a To-Do for Dylan."""
    from routers import sms as sms_router
    import integrations

    settings = await get_settings()
    pool = await get_pool()
    async with pool.acquire() as conn:
        r = await conn.fetchrow(
            """SELECT r.*, c.name, c.contact_name, c.email, c.phone, c.booking_notification_name,
                      anchor.phone AS anchor_phone, anchor.email AS anchor_email
               FROM client_reports r JOIN clients c ON c.id = r.client_id
               LEFT JOIN contacts anchor ON anchor.client_id = c.id AND anchor.is_client_anchor
               WHERE r.id = $1""", report_id)
        if not r:
            return {"sent": False}
        first = ((r["booking_notification_name"] or "").split() or [None])[0] or first_name_from_owner(r["contact_name"]) or "there"
        ctx = {"first_name": first, "clinic": r["name"], "week": r["week_number"] or "", "link": report_url(r["slug"])}
        pre = "csm_weekly" if r["kind"] == "weekly" else "csm_final"
        channels, problems = [], []

        email = (r["email"] or r["anchor_email"] or "").strip()
        if _on(settings["csm_send_email"]):
            if email:
                try:
                    await asyncio.to_thread(integrations.gmail_send, email,
                                            _fill(settings[f"{pre}_email_subject"], ctx),
                                            _fill(settings[f"{pre}_email_body"], ctx), is_automated=True)
                    channels.append("email")
                except Exception as e:
                    problems.append(f"email failed: {e}")
            else:
                problems.append("no email on file")
        phone = (r["phone"] or r["anchor_phone"] or "").strip()
        if _on(settings["csm_send_sms"]):
            if phone:
                try:
                    sms_router._send_twilio(phone, _fill(settings[f"{pre}_sms"], ctx))
                    channels.append("sms")
                except Exception as e:
                    problems.append(f"SMS failed: {e}")
            else:
                problems.append("no phone on file")

        await conn.execute("UPDATE client_reports SET sent_at = CASE WHEN $2 THEN now() ELSE sent_at END, "
                           "sent_channels = $3, send_error = $4 WHERE id = $1",
                           report_id, bool(channels), channels, "; ".join(problems) or None)
        if channels and r["kind"] == "final":
            # The campaign's over and the client has the results: start the "did they stay?" decision.
            try:
                import client_retention
                await client_retention.open_for_report(conn, report_id)
            except Exception as e:
                print(f"[client_success] renewal decision not opened for report {report_id}: {e}")
        if problems:
            label = "weekly" if r["kind"] == "weekly" else "final"
            await _todo_once(conn, f"Send {r['name']}'s {label} report by hand",
                             f"Auto-send hit a problem ({'; '.join(problems)}). Report: {report_url(r['slug'])}")
    return {"sent_channels": channels, "send_error": "; ".join(problems) or None}


async def _todo_once(conn, text: str, description: str) -> None:
    if await conn.fetchval("SELECT 1 FROM todos WHERE NOT done AND text = $1", text):
        return
    await conn.execute("INSERT INTO todos (text, description, due_date) VALUES ($1, $2, $3)",
                       text, description, datetime.now(ET).date())


async def add_feedback(slug: str, body: dict) -> bool:
    msg = str(body.get("message") or "").strip()[:4000]
    kind = body.get("kind") if body.get("kind") in ("question", "suggestion", "feedback", "testimonial") else "feedback"
    rating = body.get("rating")
    rating = int(rating) if isinstance(rating, (int, float)) and 0 <= rating <= 10 else None
    pool = await get_pool()
    async with pool.acquire() as conn:
        r = await conn.fetchrow("SELECT r.id, r.client_id, r.kind, c.name FROM client_reports r "
                                "JOIN clients c ON c.id = r.client_id WHERE r.slug = $1", slug)
        if not r:
            return False
        await conn.execute(
            """INSERT INTO client_report_feedback (report_id, client_id, kind, message, rating, testimonial_ok, wants_next)
               VALUES ($1,$2,$3,$4,$5,$6,$7)""",
            r["id"], r["client_id"], kind, msg, rating, bool(body.get("testimonial_ok")), bool(body.get("wants_next")))
        bits = []
        if rating is not None:
            bits.append(f"rated {rating}/5" + (" stars for their experience" if kind == "testimonial" else ""))
        if body.get("wants_next"):
            bits.append("WANTS TO TALK ABOUT THE NEXT CAMPAIGN")
        if body.get("testimonial_ok"):
            bits.append("OK to use as testimonial")
        verb = {"question": "asked a question", "suggestion": "left a suggestion", "testimonial": "left a testimonial"}.get(kind, "left feedback")
        # Both ratings are out of 5 now (weekly check-in, final "would you recommend" stars).
        low = rating is not None and rating <= 2
        text = f"{'⚠ ' if low else ''}{r['name']} {verb if msg else 'responded'} on their report"
        await conn.execute("INSERT INTO todos (text, description, due_date) VALUES ($1, $2, $3)",
                           text, f"{'; '.join(bits)}\n\n{msg}\n\nAnswer it: Business Resources -> Outreach Templates -> Client Success Reports.",
                           datetime.now(ET).date())
    return True


async def answer_feedback(feedback_id: int, answer: str, email_it: bool) -> dict:
    import integrations
    pool = await get_pool()
    async with pool.acquire() as conn:
        f = await conn.fetchrow(
            """UPDATE client_report_feedback SET answer = $2, answered_at = now() WHERE id = $1
               RETURNING *""", feedback_id, answer.strip())
        if not f:
            return {"ok": False}
        c = await conn.fetchrow(
            """SELECT c.name, c.contact_name, c.email, anchor.email AS anchor_email FROM clients c
               LEFT JOIN contacts anchor ON anchor.client_id = c.id AND anchor.is_client_anchor WHERE c.id = $1""",
            f["client_id"])
    emailed = False
    email = (c["email"] or c["anchor_email"] or "").strip() if c else ""
    if email_it and email and f["message"]:
        body = (f"Hi {first_name_from_owner(c['contact_name']) or 'there'},\n\n"
                f"You asked on your campaign report:\n\"{f['message']}\"\n\n{answer.strip()}\n\nDylan\nDigiGrowth")
        await asyncio.to_thread(integrations.gmail_send, email, f"Re: your question on the {c['name']} report",
                                body, is_automated=True)
        emailed = True
    return {"ok": True, "emailed": emailed}


async def draft_final(client_id: int, why: str = "") -> dict | None:
    """Build the final report as a draft (never sent) + a To-Do to approve it.
    Once per campaign. Called by run_daily and the moment the ad budget is
    spent (ad_spend_caps -> on_budget_spent)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        win = await campaign_window(conn, client_id)
        if not win["launched_at"] or not win["enabled"]:
            return None
        if await conn.fetchval("SELECT 1 FROM client_reports WHERE client_id = $1 AND kind = 'final' "
                               "AND campaign_launched_at = $2", client_id, win["launched_at"]):
            return None
        name = await conn.fetchval("SELECT name FROM clients WHERE id = $1", client_id)
    r = await create_report(client_id, "final", send=False)
    async with pool.acquire() as conn:
        await _todo_once(conn, f"Approve {name}'s final campaign report",
                         f"{why + ' ' if why else ''}Draft: {report_url(r['slug'])}\n\nIncludes the next-campaign plan and "
                         "testimonial ask. Ask Claude to publish it as an Artifact to review or change it, then Approve & send "
                         "in Clients -> client -> Agents -> Client Success Manager.")
    print(f"[client_success] final report drafted for client {client_id}: {report_url(r['slug'])}")
    return r


async def on_budget_spent(client_id: int, spend: float, cap: float) -> None:
    """ad_spend_caps: the cap was just reached -> the campaign is over, draft the final report now."""
    try:
        settings = await get_settings()
        if not _on(settings["csm_enabled"]):
            return
        pool = await get_pool()
        async with pool.acquire() as conn:
            test = await conn.fetchval("SELECT coalesce(is_test, false) FROM clients WHERE id = $1", client_id)
        if test:
            return
        await draft_final(client_id, f"The ${cap:,.0f} ad budget is spent (${spend:,.2f}), so the campaign is over.")
    except Exception as e:
        print(f"[client_success] final report on budget spent failed for {client_id}: {e}")


# ---------------------------------------------------------------- scheduler

async def run_daily() -> None:
    """10:00 ET daily: finals any day once a campaign ends, weeklies on Mondays."""
    settings = await get_settings()
    if not _on(settings["csm_enabled"]):
        return
    is_monday = datetime.now(ET).weekday() == 0
    pool = await get_pool()
    async with pool.acquire() as conn:
        clients = await conn.fetch(
            """SELECT c.id FROM clients c JOIN client_marketing_config m ON m.client_id = c.id
               WHERE c.status = 'active' AND NOT coalesce(c.is_test, false)
                 AND m.campaign_launched_at IS NOT NULL AND coalesce(m.csm_reports_enabled, true)""")
    for c in clients:
        cid = c["id"]
        try:
            async with pool.acquire() as conn:
                win = await campaign_window(conn, cid)
                if win["state"] == "ended":
                    done = await conn.fetchval("SELECT 1 FROM client_reports WHERE client_id = $1 AND kind = 'final' "
                                               "AND campaign_launched_at = $2", cid, win["launched_at"])
                    # Don't send finals for campaigns that ended long before this feature existed.
                    stale = datetime.now(timezone.utc) - win["ends_at"] > timedelta(days=14)
                    kind = None if (done or stale) else "final"
                elif is_monday and (datetime.now(timezone.utc) - win["launched_at"]).days >= 5:
                    done = await conn.fetchval("SELECT 1 FROM client_reports WHERE client_id = $1 AND kind = 'weekly' "
                                               "AND campaign_launched_at = $2 AND week_number = $3",
                                               cid, win["launched_at"], win["week"])
                    kind = None if done else "weekly"
                else:
                    kind = None
            if kind == "weekly":
                r = await create_report(cid, kind, send=True)
                print(f"[client_success] weekly report for client {cid}: {report_url(r['slug'])} sent={r.get('sent_channels')}")
            elif kind == "final":
                # Final reports wait for Dylan: they carry the renewal + testimonial asks.
                await draft_final(cid)
        except Exception as e:
            print(f"[client_success] client {cid} failed: {e}")
