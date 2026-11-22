"""
Live AI voice agent demo on a Patient Acquisition Blueprint page.

The prospect (or Dylan, presenting) clicks "Call me" on the blueprint and talks
to the voice agent in the browser, no phone needed. It is the SAME agent the
clients run (client_voice_agent.py): Dylan's default call script
(default_script("ads")), the default voice and voice style, plus the page's
chat_context as the business info. Only the tools differ: every action is
simulated here (made-up open times, nothing booked, nobody texted).

How the call starts (Retell web calls, SDK v3): the page's RetellClient is
given a `fetch` that sends its /v3/create-web-call request to
POST /lp/<slug>/voice-call instead of Retell. That route (routers/landing_pages.py)
ignores whatever agent the browser asked for, makes sure this page's demo
agent exists and is current, creates the web call with our server key, and
returns Retell's answer (call_id + access_token). Audio then flows straight
between the browser and Retell. The Retell API key never reaches the page.

One Retell LLM + agent per page, ids on the landing_pages row
(voice_llm_id, voice_agent_id). voice_ctx_hash = hash of everything the agent
is built from, so editing the chat context, the default script or the voice
defaults re-syncs the demo agent on its next call.

Demo calls carry no row_id in their metadata, so the real voice agent's
webhooks (client_voice_agent.retell_event / run_function) ignore them.
"""
import hashlib
import json
import time
from collections import defaultdict, deque
from datetime import datetime
from zoneinfo import ZoneInfo

import blueprint_chat
import client_voice_agent as va
from db import get_pool

DEMO_VERSION = "2026-11-22.2"  # bump to force every demo agent to re-sync
MAX_CALL_MS = 6 * 60 * 1000

_IP_LIMIT = (4, 3600)     # 4 demo calls per IP per hour
_PAGE_LIMIT = (40, 86400)  # 40 per page per day
_hits: dict[str, deque] = defaultdict(deque)

# A demo has no client yet, so it copies Advantage Therapy's live voice agent
# (Dylan, 2026-11-22: the demo "doesn't sound anything like the original";
# Advantage = client 4's client_marketing_config: 11labs-Kate, speed 1.2, tuned style, "Jamie").
_DEMO_CFG = {"voice_id": "11labs-Kate", "voice_speed": 1.2, "voice_style": "tuned", "voice_agent_name": "Jamie"}

ISSUES = {
    "back": "lower back pain", "knee": "knee pain", "shoulder": "shoulder pain",
    "neck": "neck pain", "hip": "hip pain", "sciatica": "sciatica",
}

_DEMO_NOTE = """
THIS IS A LIVE DEMO, shown to the clinic's owner on a sales call. Play the call exactly as you would a real
new Meta lead. Every tool is simulated: the results tell you what would have happened. Never mention that it's a
demo unless they ask; if they do, say yes, this is a demo of how the clinic's leads get called, and carry on.
"""


def rate_limited(ip: str, slug: str) -> bool:
    now = time.time()
    for key, (limit, window) in ((f"ip:{ip}", _IP_LIMIT), (f"page:{slug}", _PAGE_LIMIT)):
        q = _hits[key]
        while q and q[0] < now - window:
            q.popleft()
        if len(q) >= limit:
            return True
    _hits[f"ip:{ip}"].append(now)
    _hits[f"page:{slug}"].append(now)
    return False


def _fn_url(slug: str) -> str:
    return f"{va._base_url()}/lp/{slug}/voice-fn"


def _llm_body(slug: str, business: str, context: str) -> dict:
    url = _fn_url(slug)

    def custom(name, description, props, required=(), speak=False, msg=None):
        tool = {"type": "custom", "name": name, "url": url, "description": description,
                "parameters": {"type": "object", "properties": props, "required": list(required)},
                "speak_during_execution": speak, "speak_after_execution": True, "timeout_ms": 15000}
        if msg:
            tool["execution_message_description"] = msg
        return tool

    tools = [
        {"type": "end_call", "name": "end_call", "description": "Hang up only after the conversation is really over and you've said goodbye. Never during the opening."},
        custom("check_availability", "Find open appointment times. Returns the earliest day's two options.",
               {"after_date": {"type": "string", "description": "YYYY-MM-DD to search from; omit for today"}},
               speak=True, msg="Say only 'One sec.' in a flat, casual tone."),
        custom("book_appointment", "Book the time the caller agreed to (one of the times you offered).",
               {"date": {"type": "string", "description": "YYYY-MM-DD"}, "time": {"type": "string", "description": "HH:MM 24h"},
                "reason": {"type": "string"}}, required=("date", "time"), speak=True, msg="Say only 'Okay.' in a flat, casual tone."),
        custom("schedule_callback", "Caller asked you to call back later; schedule it.",
               {"date": {"type": "string"}, "time": {"type": "string"}, "note": {"type": "string"}}, required=("date", "time")),
        custom("mark_not_interested", "Caller isn't interested, has the wrong number, or wants no more calls.",
               {"reason": {"type": "string"}, "do_not_call": {"type": "boolean"}}, required=("reason",)),
        custom("mark_unqualified", "Caller clearly can't be a patient (e.g. outside the service area).",
               {"reason": {"type": "string"}}, required=("reason",)),
        custom("transfer_to_clinic", "Connect the caller to the clinic's team (business hours only).",
               {"reason": {"type": "string"}}, required=("reason",)),
        custom("escalate_to_human", "Flag this lead for the clinic's team to follow up by phone.",
               {"reason": {"type": "string"}, "urgent": {"type": "boolean"}}, required=("reason",)),
    ]
    prompt = (va.default_script("ads").replace("__AGENT_NAME__", "{{agent_name}}")
              + "\nBusiness info and rules (the same ones the clinic's text agent uses):\n" + context.strip()
              + "\n" + _DEMO_NOTE)
    return {
        "general_prompt": prompt,
        "begin_message": "Hi, is this {{lead_first_name}}?",
        "start_speaker": "agent",
        "general_tools": tools,
        "default_dynamic_variables": {
            "agent_name": va.agent_name(_DEMO_CFG), "lead_first_name": "there", "lead_full_name": "unknown",
            "lead_context": "they filled out the clinic's Facebook ad form a few minutes ago",
            "clinic_name": business, "today": "", "visit_info": "use the business info",
            "form_date": "a few weeks back", "form_answers": "none on file"},
    }


def _agent_body(slug: str, business: str, llm_id: str) -> dict:
    return {
        "agent_name": f"{business} - DigiGrowth blueprint voice demo ({slug})",
        "response_engine": {"type": "retell-llm", "llm_id": llm_id},
        **va._voice_fields(_DEMO_CFG),
        "boosted_keywords": [business, va.agent_name(_DEMO_CFG)] + va.PT_KEYWORDS,
        "language": "en-US",
        "end_call_after_silence_ms": 20000,
        "max_call_duration_ms": MAX_CALL_MS,
    }


def _hash(slug: str, business: str, context: str) -> str:
    src = json.dumps([DEMO_VERSION, _llm_body(slug, business, context), _agent_body(slug, business, "x")], sort_keys=True)
    return hashlib.sha256(src.encode()).hexdigest()[:24]


async def ensure_agent(slug: str) -> tuple[str, str]:
    """(agent_id, business short name) for this page's demo agent, creating
    or re-syncing it first when anything it's built from changed."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT business, chat_context, voice_llm_id, voice_agent_id, voice_ctx_hash FROM landing_pages WHERE slug = $1", slug)
    if not row or not (row["chat_context"] or "").strip():
        raise LookupError("No voice demo on this page")
    business = (row["business"] or "the clinic").strip()
    h = _hash(slug, business, row["chat_context"])
    if row["voice_agent_id"] and row["voice_ctx_hash"] == h:
        return row["voice_agent_id"], business
    llm_body = _llm_body(slug, business, row["chat_context"])
    if row["voice_llm_id"]:
        await va._retell("PATCH", f"/update-retell-llm/{row['voice_llm_id']}", llm_body)
        llm_id = row["voice_llm_id"]
    else:
        llm_id = (await va._retell("POST", "/create-retell-llm", llm_body))["llm_id"]
    agent_body = _agent_body(slug, business, llm_id)
    if row["voice_agent_id"]:
        await va._retell("PATCH", f"/update-agent/{row['voice_agent_id']}", agent_body)
        agent_id = row["voice_agent_id"]
    else:
        agent_id = (await va._retell("POST", "/create-agent", agent_body))["agent_id"]
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE landing_pages SET voice_llm_id = $2, voice_agent_id = $3, voice_ctx_hash = $4 WHERE slug = $1",
            slug, llm_id, agent_id, h)
    return agent_id, business


def _clean(s, n=40) -> str:
    return "".join(c for c in str(s or "") if c.isalnum() or c in " '-").strip()[:n]


async def create_web_call(slug: str, requested: dict) -> dict:
    """Create the web call for the page. `requested` is the SDK's request body;
    only the demo's own dynamic variables (lead name, issue, timezone) are
    read from it, and only from a fixed set of values."""
    agent_id, business = await ensure_agent(slug)
    dv = requested.get("retell_llm_dynamic_variables") or {}
    first = _clean(dv.get("lead_first_name"), 30) or "Jordan"
    issue = ISSUES.get(str(dv.get("issue") or ""), "lower back pain")
    tz_name = str(dv.get("timezone") or "")
    tz = blueprint_chat._tz(tz_name)
    now = datetime.now(tz)
    body = {
        "agent_id": agent_id,
        "metadata": {"blueprint": slug, "tz": tz.key},
        "retell_llm_dynamic_variables": {
            "agent_name": va.agent_name(_DEMO_CFG),
            "clinic_name": business,
            "lead_first_name": first, "lead_full_name": first,
            "lead_context": "they filled out the clinic's Facebook ad form a few minutes ago",
            "form_answers": f"Filled out on: Facebook. What's going on: {issue}.",
            "visit_info": "the first visit named in the business info",
            "today": f"{now.strftime('%A, %B')} {now.day}, {now.year}, {now.strftime('%I:%M %p').lstrip('0')}",
        },
    }
    return await va._retell("POST", "/v3/create-web-call", body)


def run_function(name: str, args: dict, call: dict) -> str:
    """Simulated results for the demo agent's tools."""
    g = lambda k: str(args.get(k) or "").strip()
    tz = blueprint_chat._tz((call.get("metadata") or {}).get("tz"))
    if name == "check_availability":
        return blueprint_chat._fake_slots(tz, g("after_date"))
    if name == "book_appointment":
        when = blueprint_chat._when(g("date"), g("time"))
        return (f"Booked {when}. It's a paid visit, so a text is on its way now with a link to pay and lock in the "
                "spot. Tell them that.")
    if name == "schedule_callback":
        return f"Callback scheduled for {blueprint_chat._when(g('date'), g('time'))}."
    if name == "mark_not_interested":
        return "Marked not interested. No more calls. Thank them and wrap up."
    if name == "mark_unqualified":
        return "Marked unqualified. Thank them and wrap up politely."
    if name == "transfer_to_clinic":
        return "Nobody can pick up right now. Use escalate_to_human instead."
    if name == "escalate_to_human":
        return "Flagged for the clinic's team. Tell them someone from the clinic will call them back soon."
    return "Unknown action."
