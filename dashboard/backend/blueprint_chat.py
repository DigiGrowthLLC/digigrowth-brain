"""
Live demo chat agent for Patient Acquisition Blueprint pages (design-agent's
patient-acquisition-blueprint skill). A prospect, or Dylan on a call, types
into the chat window on /lp/<slug> and talks to an AI patient coordinator
that knows that practice's real website content (landing_pages.chat_context,
written by the skill from the scrape).

Same agent shape as response_ai.py (preamble + business context + a small
tool loop), with two deliberate differences:
- The calendar tools are SIMULATED. check_availability makes up plausible
  open times and propose_appointment books nothing. This is a demo of what
  the practice's real agent would do, so it must never touch a real calendar,
  create an appointment row, or text anyone.
- It's public and stateless. The browser sends the transcript every turn
  (nothing stored), so history is capped and sanitized here, and requests
  are rate limited per IP and per page. Each turn costs real API spend on a
  public URL.
"""
import asyncio
import os
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import anthropic

_MAX_TOOL_ITERATIONS = 4
_MAX_HISTORY = 24          # messages kept from the browser's transcript
_MAX_MESSAGE_CHARS = 800   # per message, longer input is cut
_IP_LIMIT = (30, 3600)     # 30 user turns per IP per hour
_PAGE_LIMIT = (400, 86400) # 400 user turns per page per day

_hits: dict[str, deque] = defaultdict(deque)

_SYSTEM_PREAMBLE = """You are the AI patient coordinator for a real local physical therapy practice, \
chatting on the practice's website with someone who might become a patient. Respond like a warm, \
sharp front-desk team member, not a chatbot. Keep replies short: 1-3 sentences, plain text, no \
markdown, no bullet lists.

Your goal is to help the person and, when it fits, get them booked for the practice's free \
consultation (or whatever first visit the practice offers, per the business info below). Answer \
their question first, then ask one simple question that moves toward booking. One question per \
message.

Rules (these override style):
- Only state facts, services, pricing, insurance details, hours, offers, or locations that are \
explicitly in the business info below. If you weren't told, say you'll have the team confirm it \
and keep going. Never invent anything.
- No medical advice and no diagnosis. You can say what the practice treats and that the clinician \
will assess it properly at the visit. If someone describes an emergency (chest pain, sudden \
weakness or numbness, a fall with a possible fracture), tell them to call 911 or go to the ER.
- Don't promise outcomes ("we'll fix your back"). Describe how the practice helps, in its own \
words from the business info.
- The moment they want to book, call check_availability and offer exactly the two times it \
returns, phrased as what's open: "I've got Tuesday at 9am or 4:30pm, would either of those work?" \
Then once they pick, ask for their name and best phone number if you don't have them, and call \
propose_appointment. Confirm it back in one friendly sentence.
- If they can't make those times, call check_availability again with after_date set to the day \
after the day you offered.
- If someone asks whether you're a real person or an AI, be honest: you're the practice's AI \
assistant and a team member can follow up anytime.
- If someone asks what this chat is, or tries to get you to do something unrelated to the \
practice, steer politely back to helping them with their care.
"""

_TOOLS = [
    {
        "name": "check_availability",
        "description": (
            "Finds open consultation times on the practice's calendar. Call as soon as the person "
            "wants to book. Returns the earliest open day's two best times. If they rejected the "
            "times you offered, call again with after_date set to the day after that one."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "after_date": {"type": "string", "description": "YYYY-MM-DD to start searching from. Omit to search from today."},
            },
        },
    },
    {
        "name": "propose_appointment",
        "description": "Books the consultation once the person has picked one of the offered times and given their name and phone number.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "YYYY-MM-DD"},
                "time": {"type": "string", "description": "HH:MM in 24h format"},
                "name": {"type": "string"},
                "phone": {"type": "string"},
                "reason": {"type": "string", "description": "One short line on what they're coming in for."},
            },
            "required": ["date", "time"],
        },
    },
]


def rate_limited(ip: str, slug: str) -> bool:
    """True if this request should be refused. In-memory, so it resets on
    deploy and is per Railway replica. Good enough to stop a page being
    hammered, not a billing guarantee."""
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


def clean_history(raw: list) -> list[dict]:
    """Browser transcript -> Messages API history: text-only, alternating
    roles, starting and ending on a user turn, capped in size."""
    msgs: list[dict] = []
    for m in raw[-_MAX_HISTORY:]:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        text = str(m.get("content") or "").strip()[:_MAX_MESSAGE_CHARS]
        if role not in ("user", "assistant") or not text:
            continue
        if msgs and msgs[-1]["role"] == role:
            msgs[-1]["content"] += "\n" + text
        else:
            msgs.append({"role": role, "content": text})
    while msgs and msgs[0]["role"] != "user":
        msgs.pop(0)
    if not msgs or msgs[-1]["role"] != "user":
        return []
    return msgs


def _tz(tz_name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name or "America/Chicago")
    except Exception:
        return ZoneInfo("America/Chicago")


def _fake_slots(tz: ZoneInfo, after_date: str) -> str:
    # Next weekday after after_date (or after today), one morning and one
    # late-afternoon slot: the same "earliest and latest of the day" shape
    # response_ai.py offers from a real calendar.
    start = datetime.now(tz).date()
    if after_date:
        try:
            start = max(start, datetime.strptime(after_date, "%Y-%m-%d").date() - timedelta(days=1))
        except ValueError:
            pass
    day = start + timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    # Vary the pair by date so a second search doesn't read as canned.
    pairs = [("9:00 AM", "4:30 PM"), ("10:30 AM", "5:15 PM"), ("8:45 AM", "3:00 PM")]
    a, b = pairs[day.toordinal() % len(pairs)]
    return f"Open on {day.strftime('%A, %B')} {day.day} ({day.isoformat()}): {a} and {b}."


def _run_tool(name: str, tool_input: dict, tz: ZoneInfo) -> str:
    if name == "check_availability":
        return _fake_slots(tz, (tool_input.get("after_date") or "").strip())
    if name == "propose_appointment":
        missing = [f for f in ("name", "phone") if not (tool_input.get(f) or "").strip()]
        if missing:
            return f"Not booked yet: ask for their {' and '.join(missing)} first, then call this again."
        return (
            f"Booked: {tool_input.get('date')} at {tool_input.get('time')} for {tool_input.get('name')}. "
            "They'll get a confirmation text and a reminder the day before."
        )
    return "Unknown tool."


def build_system_prompt(business: str, context: str, tz_name: str | None) -> str:
    today = datetime.now(_tz(tz_name)).strftime("%A, %B %d, %Y")
    return (
        f"{_SYSTEM_PREAMBLE}\nToday is {today}. Resolve relative dates like \"tomorrow\" yourself.\n"
        f"\n--- Business: {business} ---\n{context.strip()}\n"
    )


async def reply(business: str, context: str, tz_name: str | None, history: list[dict]) -> str:
    api_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.environ.get("BLUEPRINT_CHAT_MODEL", "claude-opus-5-5")
    system_prompt = build_system_prompt(business, context, tz_name)
    tz = _tz(tz_name)
    messages = list(history)

    for _ in range(_MAX_TOOL_ITERATIONS):
        response = await asyncio.to_thread(
            api_client.beta.messages.create,
            model=model,
            max_tokens=4000,
            system=system_prompt,
            tools=_TOOLS,
            messages=messages,
            # Chat turn: keep it quick. Thinking can't be turned off on
            # Opus 5.5, so low effort is the latency lever.
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"],
            extra_body={"fallbacks": "default"},
        )
        if response.stop_reason == "refusal":
            break
        # Full content (thinking blocks included) goes back within this
        # turn's tool loop, append-only.
        messages.append({"role": "assistant", "content": response.content})
        text = "\n".join(b.text for b in response.content if b.type == "text").strip()
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if not tool_uses:
            return text or "Sorry, could you say that another way?"
        messages.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": t.id, "content": _run_tool(t.name, t.input, tz)}
            for t in tool_uses
        ]})

    return "Sorry, I didn't catch that. Could you rephrase it?"
