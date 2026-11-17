"""Per-client services (2026-11-17): what DigiGrowth actually does for each
client, so their portal and Marketing Setup only show what applies.

A new client's portal opens on a short intake (routers/client_portal.py
/intake, IntakeGate in ClientPortal.jsx) before anything else: a checklist
of SERVICES plus a few INTAKE_QUESTIONS the Get Started questionnaire
doesn't ask. The answers land on clients.services (JSONB list of ids) and
clients.portal_intake, and filter:
  - the portal's Setup Steps (onboarding_action_items.services),
  - the portal's Launch Progress (launch_checklist_items.services),
  - the Get Started questionnaire sections (SECTION_SERVICES below),
  - the OS Marketing Setup steps (setup_steps.STEPS "services").
An item with no services listed applies to everyone; otherwise it shows
when the client has at least one of them.

clients.services NULL = never answered: falls back to the package
(service_package) defaults, which is how clients from before this shipped
keep their full checklist. clients.intake_required is false for those
clients (db.py migration) so they aren't gated; Dylan can re-ask any client
from Marketing Setup (ASK AGAIN), which clears intake_completed_at.
"""
from __future__ import annotations

import json

# Every service the checklists know about (step/item tags in the OS use these).
ALL_SERVICES = [
    {"id": "paid_ads", "label": "Paid ads on Facebook & Instagram",
     "hint": "We run ads that bring you new patient leads."},
    {"id": "social_media", "label": "Social media management",
     "hint": "We post to your Facebook and Instagram for you."},
    {"id": "funnel", "label": "Landing page / booking funnel (every client)",
     "hint": "A page on their own web address that turns visitors into booked visits."},
    {"id": "online_booking", "label": "Online booking page (every client)",
     "hint": "Patients pick a time themselves and it lands on their calendar."},
    {"id": "ai_text", "label": "AI appointment setter: texts",
     "hint": "Texts new leads within minutes, answers questions and books them."},
    {"id": "ai_voice", "label": "AI appointment setter: calls",
     "hint": "Calls new leads within minutes of them reaching out."},
    {"id": "dm_agent", "label": "AI replies to Facebook & Instagram DMs",
     "hint": "Answers your DMs and books the people who message you."},
    {"id": "reactivation", "label": "Past patient reactivation",
     "hint": "Texts your past patients and old inquiries to bring them back in."},
    {"id": "followup", "label": "Automatic reminders & follow-up texts",
     "hint": "Booking confirmations, reminders, and no-show / cancellation follow-ups."},
]
SERVICE_IDS = [s["id"] for s in ALL_SERVICES]

# Every client gets these; they're never asked about.
ALWAYS = ["funnel", "online_booking"]
# What the client (and Dylan's Services card) actually ticks. A choice can
# stand for several services: the AI agent is one box for texts + calls.
CHOICES = [
    {"id": "paid_ads", "label": "Paid ads on Facebook & Instagram",
     "hint": "We run ads that bring you new patient leads.", "services": ["paid_ads"]},
    {"id": "social_media", "label": "Social media management",
     "hint": "We post to your Facebook and Instagram for you.", "services": ["social_media"]},
    {"id": "ai_agent", "label": "AI appointment setter (texts + calls)",
     "hint": "Reaches new leads within minutes by text and phone, answers questions and books them.",
     "services": ["ai_text", "ai_voice"]},
    {"id": "dm_agent", "label": "AI replies to Facebook & Instagram DMs",
     "hint": "Answers your DMs and books the people who message you.", "services": ["dm_agent"]},
    {"id": "reactivation", "label": "Past patient reactivation",
     "hint": "Texts your past patients and old inquiries to bring them back in.", "services": ["reactivation"]},
    {"id": "followup", "label": "Automatic reminders & follow-up texts",
     "hint": "Booking confirmations, reminders, and no-show / cancellation follow-ups.", "services": ["followup"]},
]
SERVICES = CHOICES  # what the intake shows


def expand(choice_ids) -> list[str]:
    """Ticked choices -> the services they stand for, plus the ALWAYS ones."""
    out = list(ALWAYS)
    for c in CHOICES:
        if c["id"] in (choice_ids or []):
            out += [x for x in c["services"] if x not in out]
    return out


def to_choices(services) -> list[str]:
    return [c["id"] for c in CHOICES if set(c["services"]) & set(services or [])]

PACKAGE_DEFAULTS = {
    "growth": SERVICE_IDS,
    "foundations": ["funnel", "online_booking", "ai_text", "reactivation", "followup"],
}

# Anything that texts from the client's number needs A2P registration (the
# questionnaire's Legal section); anything that books needs their calendar.
TEXTING = ["ai_text", "ai_voice", "reactivation", "followup"]
BOOKING = ["online_booking", "funnel", "ai_text", "ai_voice"]
META = ["paid_ads", "social_media", "dm_agent"]

# Get Started questionnaire sections (frontend onboardingSections.js keys)
# that only apply to some services. Unlisted sections apply to everyone.
SECTION_SERVICES = {
    "legal": TEXTING,
    "current_marketing": ["paid_ads", "social_media", "funnel"],
}

# Extra intake questions (not already in the Get Started questionnaire).
# `services`: shown only when one of these is checked. `type`: choice
# (single pick), multi (checkboxes) or text.
INTAKE_QUESTIONS = [
    {"key": "meta_assets", "type": "multi", "services": META,
     "label": "Which of these do you already have?",
     "options": ["Facebook business Page", "Instagram account", "Meta (Facebook) ad account",
                 "Meta Business Portfolio (Business Manager)", "None of these yet"]},
]


def _decode(v):
    if isinstance(v, str):
        try:
            return json.loads(v)
        except ValueError:
            return None
    return v


def effective(client: dict) -> list[str]:
    """The client's services: their intake answer, else their package's defaults."""
    chosen = _decode(client.get("services"))
    if isinstance(chosen, list):
        return [s for s in chosen if s in SERVICE_IDS]
    return list(PACKAGE_DEFAULTS.get(client.get("service_package") or "growth", SERVICE_IDS))


def applies(needed, have) -> bool:
    """needed: None/empty = everyone; else at least one in common."""
    return not needed or bool(set(needed) & set(have))


def intake_pending(client: dict) -> bool:
    return bool(client.get("intake_required")) and not client.get("intake_completed_at")


def clean_answers(services: list[str], answers: dict) -> dict:
    """Keep only answers to questions that applied, as plain strings/lists."""
    out = {}
    for q in INTAKE_QUESTIONS:
        if not applies(q["services"], services):
            continue
        if q.get("show_if") and answers.get(q["show_if"][0]) != q["show_if"][1]:
            continue
        v = answers.get(q["key"])
        if q["type"] == "multi":
            v = [o for o in (v or []) if o in q["options"]]
        else:
            v = str(v or "").strip()[:2000]
        if v:
            out[q["key"]] = v
    return out


def labels(ids) -> list[str]:
    by = {s["id"]: s["label"] for s in CHOICES}
    return [by[i] for i in ids if i in by]
