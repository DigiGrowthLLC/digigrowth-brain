"""Booking Links → "Auto-fill from client info": drafts a clinic's booking
setup (hours, appointment type, price, address, timezone) from everything
the client already gave us, for Dylan to review before anything is saved.

Sources, in order of how much they're trusted:
  1. Their existing Calendly event type + availability schedule, if a
     Calendly token/event link is on file (real, structured settings).
  2. The clinic's Google Calendar time zone (booking_settings.calendar_id).
  3. Portal intake answers (client_onboarding_responses): address, specials.
  4. The client's AI text agent notes (response_ai_context / _rules), which
     usually spell out hours and the patient offer.
  5. Their funnel landing page text (the live patient offer).

Claude extracts a proposal via a forced tool call; it's told to leave a
field empty rather than guess, and to list every guess in `notes`.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from html import unescape

import anthropic
import httpx

from db import get_pool

_MODEL = os.environ.get("BOOKING_AUTOFILL_MODEL", "claude-sonnet-5-5")

_TOOL = {
    "name": "propose_booking_setup",
    "description": "Return the proposed booking setup for this clinic.",
    "input_schema": {
        "type": "object",
        "properties": {
            "timezone": {"type": ["string", "null"], "description": "IANA time zone of the clinic, e.g. America/Chicago. Null if unknown."},
            "hours": {
                "type": "array",
                "description": "Weekly windows when NEW PATIENTS can be booked. Empty if the sources don't say.",
                "items": {
                    "type": "object",
                    "properties": {
                        "weekday": {"type": "integer", "description": "0=Monday ... 6=Sunday"},
                        "start": {"type": "string", "description": "HH:MM 24h, clinic local time"},
                        "end": {"type": "string", "description": "HH:MM 24h, clinic local time"},
                    },
                    "required": ["weekday", "start", "end"],
                },
            },
            "hours_source": {"type": "string", "description": "Where the hours came from, in a few words."},
            "event_type": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Patient-facing visit name, e.g. 'New Patient Assessment' or 'Free Consultation'."},
                    "duration_min": {"type": "integer"},
                    "location_type": {"type": "string", "enum": ["in_person", "google_meet", "phone"]},
                    "location_text": {"type": ["string", "null"], "description": "Full clinic street address for in_person, else null."},
                    "price_cents": {"type": "integer", "description": "What the patient pays online when booking, in cents. 0 if free."},
                    "anchor_price_cents": {"type": ["integer", "null"], "description": "'Normally $X' price in cents, only if the offer states one."},
                    "spots_per_month": {"type": ["integer", "null"], "description": "Scarcity line ('only N spots per month') only if the offer states one."},
                    "ask_question": {"type": ["string", "null"], "description": "One short question to ask when booking, e.g. 'What brings you in?'"},
                    "description": {"type": ["string", "null"], "description": "1-2 short patient-facing sentences about the visit, from the sources. No claims the sources don't make."},
                },
                "required": ["name", "duration_min", "location_type", "price_cents"],
            },
            "notes": {
                "type": "array", "items": {"type": "string"},
                "description": "Anything missing, conflicting, or guessed that Dylan should check. Plain sentences.",
            },
        },
        "required": ["hours", "hours_source", "event_type", "notes"],
    },
}

_SYSTEM = """You set up an online booking page for a physical therapy clinic's NEW PATIENT visits, using only what the clinic and its marketing agency already wrote down. Your output is a draft that a human reviews before saving.

Rules:
- Never invent facts. If hours, price, address or length aren't in the sources, leave hours empty / use the defaults below and say so in notes.
- Hours = when new patients can book, in the clinic's local time. Prefer an existing Calendly availability schedule over prose. If only general business hours are given, use those and note it.
- Price: what the patient pays online at booking. The agency's offers are usually either a FREE consultation/screen (price 0) or a PAID assessment (often $49, shown as 'normally $150' with 'only 10 spots per month'). Use whichever the sources describe as the CURRENT patient offer. If a paid $49 offer is described but no 'normally' price or spots are given, use anchor 15000 and spots 10 and add a note saying you applied the agency's default.
- If sources conflict (e.g. intake says one special, the funnel page another), prefer the funnel page / agent notes (most recent), and note the conflict.
- Defaults when unstated: duration 60 for an assessment/evaluation, 20 for a free phone/video consult; location in_person with the clinic address if they treat in clinic; ask_question 'What brings you in?'.
- Visit name should match the offer's own wording where possible.
- Keep notes short and specific."""


def _strip_html(html: str, limit: int) -> str:
    html = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", html or "")
    text = unescape(re.sub(r"(?s)<[^>]+>", " ", html))
    return re.sub(r"\s+", " ", text).strip()[:limit]


async def _calendly_source(token: str | None, event_url: str | None) -> str | None:
    if not token or not event_url:
        return None
    import calendly_integration as ci
    try:
        async with httpx.AsyncClient(timeout=20) as http:
            ev = await ci._get_matching_event_type(http, token, event_url)
            lines = []
            if ev:
                lines.append(json.dumps({k: ev.get(k) for k in (
                    "name", "duration", "kind", "description_plain", "locations", "is_paid", "scheduling_url",
                )}, default=str)[:3000])
            user_uri = await ci.get_user_uri(token)
            r = await http.get("https://api.calendly.com/user_availability_schedules",
                               params={"user": user_uri}, headers=ci._headers(token))
            if r.status_code == 200:
                for sch in r.json().get("collection", []):
                    lines.append("Availability schedule " + json.dumps({
                        "name": sch.get("name"), "default": sch.get("default"), "timezone": sch.get("timezone"),
                        "rules": [x for x in sch.get("rules", []) if x.get("type") == "wday"],
                    })[:3000])
            return "\n".join(lines) or None
    except Exception as e:
        return f"(Couldn't read their Calendly: {e})"


async def gather_sources(client_id: int) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        client = await conn.fetchrow("SELECT name, email, phone FROM clients WHERE id = $1", client_id)
        if not client:
            raise ValueError("client not found")
        onboarding = await conn.fetch(
            "SELECT section, answers FROM client_onboarding_responses WHERE client_id = $1 ORDER BY section", client_id,
        )
        cfg = await conn.fetchrow(
            "SELECT response_ai_context, response_ai_rules, calendly_api_token, calendly_event_type_url "
            "FROM client_marketing_config WHERE client_id = $1", client_id,
        )
        page = await conn.fetchrow(
            "SELECT slug, html FROM landing_pages WHERE client_id = $1 ORDER BY created_at DESC LIMIT 1", client_id,
        )
        settings = await conn.fetchrow("SELECT calendar_id, timezone FROM booking_settings WHERE client_id = $1", client_id)
        anchor = await conn.fetchrow(
            "SELECT city, state FROM contacts WHERE client_id = $1 AND is_client_anchor LIMIT 1", client_id,
        )

    sources: dict[str, str] = {"Clinic": f"{client['name']}" + (f" ({anchor['city']}, {anchor['state']})" if anchor and anchor["city"] else "")}

    if settings and settings["timezone"]:
        sources["Clinic Google Calendar time zone"] = settings["timezone"]
    elif settings and settings["calendar_id"]:
        import booking_engine as be
        g = await be.google_status()
        tz = next((c.get("time_zone") for c in g.get("calendars", []) if c["id"] == settings["calendar_id"]), None)
        if tz:
            sources["Clinic Google Calendar time zone"] = tz

    cal = await _calendly_source(cfg["calendly_api_token"] if cfg else None, cfg["calendly_event_type_url"] if cfg else None)
    if cal:
        sources["Their existing Calendly booking (event type + availability)"] = cal

    answers = []
    for row in onboarding:
        a = row["answers"]
        a = json.loads(a) if isinstance(a, str) else (a or {})
        for k, v in a.items():
            if v and str(v).strip():
                answers.append(f"{k}: {str(v).strip()}")
    if answers:
        sources["Client portal intake answers"] = "\n".join(answers)[:8000]

    if cfg and (cfg["response_ai_context"] or "").strip():
        sources["AI text agent notes (business info, hours, offer)"] = cfg["response_ai_context"][:10000]
    if cfg and (cfg["response_ai_rules"] or "").strip():
        sources["AI text agent rules"] = cfg["response_ai_rules"][:3000]
    if page and page["html"]:
        sources[f"Funnel landing page text (/lp/{page['slug']})"] = _strip_html(page["html"], 6000)
    return sources


async def propose(client_id: int) -> dict:
    sources = await gather_sources(client_id)
    body = "\n\n".join(f"=== {k} ===\n{v}" for k, v in sources.items())
    api = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    resp = await api.messages.create(
        model=_MODEL, max_tokens=2000, system=_SYSTEM, tools=[_TOOL],
        tool_choice={"type": "tool", "name": "propose_booking_setup"},
        messages=[{"role": "user", "content": "Sources:\n\n" + body + "\n\nPropose the booking setup."}],
    )
    result = next((b.input for b in resp.content if b.type == "tool_use"), None)
    if not result:
        raise RuntimeError("Claude didn't return a proposal")
    result["sources_used"] = list(sources.keys())
    return result
