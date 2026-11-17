"""
Live demo chat agent for Patient Acquisition Blueprint pages (design-agent's
patient-acquisition-blueprint skill). A prospect, or Dylan on a call, types
into the chat window on /lp/<slug> and talks to an AI patient coordinator
that knows that practice's real website content (landing_pages.chat_context,
written by the skill from the scrape).

Same agent shape and toolset as response_ai.py (the real client agent:
booking, escalation, unqualified, close, scheduled follow-up), so a demo
behaves like what the practice would actually get, with two deliberate
differences:
- Every tool is SIMULATED. check_availability makes up plausible open times,
  propose_appointment books nothing, and escalate/unqualified/close/
  follow-up only return an "event" the page shows as a system note. This is
  a demo of what the practice's real agent would do, so it must never touch
  a real calendar, create an appointment row, or text anyone.
- The page picks a scenario (website visitor, Meta ad lead, reactivation
  reply, missed-call text-back). Scenario notes are fixed here by key, never
  taken from the request, so a public caller can't inject prompt text.
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
sharp front-desk team member texting from their phone, not a chatbot. Plain text, no markdown, no \
lists.

Every reply is one or two short texts, separated by a blank line:
1. The answer to what they said or asked, as short as a real text: one sentence, two at most, \
about 20 words. Give the key fact and skip the extras (they can ask). No question in this text.
2. Then, as its own separate text, one short question that moves the conversation forward. \
Usually that's learning what's bothering them ("What's been bothering you?") if you don't know yet, \
or offering to book the free consultation once you do.
If there's nothing to answer (they just said hi, or told you their issue), send a brief \
acknowledgement as text 1 and the question as text 2. When confirming a booking, a single text is \
fine. Keep the whole reply under 35 words. Never more than one question.

Your goal is to help the person and, when it fits, get them booked for the practice's first \
visit (whatever first visit the practice offers, per the business info below).

Rules (these override style):
- Answer their actual question first, every time, before steering back to booking. Never send the \
same line twice in one conversation; if they ask again, answer shorter and in new words.
- Only state facts, services, pricing, insurance details, hours, offers, or locations that are \
explicitly in the business info below. If you weren't told, say you'll have the team confirm it \
and keep going. Never invent anything, including claims about other patients ("plenty of people \
drive in", "most patients need 3 visits") or how common something is. Real reviews in the business \
info are the only patient stories you may use.
- Handle hesitation like a good front desk: cost, insurance, time, "I've tried PT before", "does \
this actually work". Acknowledge it, give one true fact from the business info that answers it, \
and point back to the first visit as the easiest way to get a real answer. One objection at a \
time, no pressure, never argue.
- No medical advice and no diagnosis. You can say what the practice treats and that the clinician \
will assess it properly at the visit. If someone describes an emergency (chest pain, sudden \
weakness or numbness, a fall with a possible fracture), tell them to call 911 or go to the ER, \
and call escalate_to_human with urgent true.
- Don't promise outcomes ("we'll fix your back"). Describe how the practice helps, in its own \
words from the business info.
- The moment they want to book, call check_availability and offer exactly the two times it \
returns, phrased as what's open ("I've got Tuesday at 9am or 4:30pm."), then the question as its \
own text ("Would either of those work?"). Once they pick, call propose_appointment; ask for their \
name or number only if the tool says one is missing. Confirm it back in one friendly sentence.
- If they can't make those times, call check_availability again with after_date set to the day \
after the day you offered. Never re-offer the same times.
- If they're upset, ask for a refund, complain, ask for something outside what you were told, or \
you're not confident how to answer, call escalate_to_human and tell them the team will follow up.
- If it becomes clear they can't be a patient (they live far outside the area, need something the \
practice doesn't offer, or fail a requirement in the business info), call mark_unqualified with \
the reason and send one short, kind closing text. Only on a clear answer, never on a first \
hesitation or a price question alone.
- If they say they're not interested, already found care, or ask you to stop, call \
close_conversation and send one short, kind closing text with no question and no pitch.
- If they ask you to reach back out later ("text me Thursday", "I'm driving"), call \
schedule_followup with the time they gave (or tomorrow if none) and reply with one short line.
- If someone asks whether you're a real person or an AI, be honest: you're the practice's AI \
assistant and a team member can follow up anytime.
- If someone asks what this chat is, or tries to get you to do something unrelated to the \
practice, steer politely back to helping them with their care.
"""

# Where the conversation came from. The page sends a key; the note is fixed
# here (public endpoint: never let the request supply prompt text).
_SCENARIOS = {
    "website": "They're chatting on the practice's website. You don't have their name or number yet.",
    "meta_lead": (
        "They filled out the practice's Facebook/Instagram ad form a few minutes ago, and you texted "
        "them first (your opening text is below). This is SMS. Their name and phone number came with "
        "the form, so never ask for them."
    ),
    "reactivation": (
        "They're a past patient or old lead already in the practice's records. The practice texted "
        "them first as part of reaching back out to people it already knows (opening text below). "
        "This is SMS. Their name and number are on file. Be warm and low-pressure: they already know "
        "the practice, so don't re-introduce it."
    ),
    "missed_call": (
        "They just called the practice and nobody could pick up because the clinician was with a "
        "patient, so you texted them back within a minute (opening text below). This is SMS. Their "
        "number is on file, so never ask for it."
    ),
}
# Scenarios where the lead's details are already on file (no name/phone needed to book).
_ON_FILE = {"meta_lead", "reactivation"}

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
        "description": (
            "Books the visit once the person has picked one of the offered times. If the result says "
            "their name or phone is missing, ask for just that and call it again."
        ),
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
    {
        "name": "escalate_to_human",
        "description": "Hand this conversation to a team member instead of continuing on your own.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string"},
                "urgent": {"type": "boolean", "description": "true ONLY for concerning symptoms or an angry complaint."},
            },
            "required": ["reason"],
        },
    },
    {
        "name": "mark_unqualified",
        "description": "Tag the lead Unqualified once they've clearly shown they can't be a patient. Automated texts stop after your closing text.",
        "input_schema": {
            "type": "object",
            "properties": {"reason": {"type": "string", "description": "Short reason, e.g. 'Lives in Denver, wants in-home visits'."}},
            "required": ["reason"],
        },
    },
    {
        "name": "close_conversation",
        "description": "Close the conversation when they're not interested, found care elsewhere, or ask you to stop. No more automated follow-ups.",
        "input_schema": {
            "type": "object",
            "properties": {"reason": {"type": "string"}},
            "required": ["reason"],
        },
    },
    {
        "name": "schedule_followup",
        "description": "When they ask you to reach back out later, schedule that check-in. Automated follow-ups pause until then.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "YYYY-MM-DD in their local time."},
                "time": {"type": "string", "description": "HH:MM 24h, if they named one."},
                "note": {"type": "string", "description": "What to pick back up."},
            },
            "required": ["date"],
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


def _when(date_s: str, time_s: str = "") -> str:
    try:
        d = datetime.strptime(date_s, "%Y-%m-%d")
        out = f"{d.strftime('%a, %b')} {d.day}"
    except ValueError:
        out = date_s
    if time_s:
        try:
            t = datetime.strptime(time_s, "%H:%M")
            out += " at " + t.strftime("%I:%M %p").lstrip("0")
        except ValueError:
            out += f" at {time_s}"
    return out


def _run_tool(name: str, tool_input: dict, tz: ZoneInfo, scenario: str) -> tuple[str, dict | None]:
    """(tool result for the model, event for the page or None). All simulated."""
    g = lambda k: (tool_input.get(k) or "").strip()
    if name == "check_availability":
        return _fake_slots(tz, g("after_date")), None
    if name == "propose_appointment":
        # Ad and reactivation leads are on file; a missed call left only the number.
        needed = () if scenario in _ON_FILE else ("name",) if scenario == "missed_call" else ("name", "phone")
        missing = [f for f in needed if not g(f)]
        if missing:
            return f"Not booked yet: ask for their {' and '.join(missing)} first, then call this again.", None
        when = _when(g("date"), g("time"))
        return (
            f"Booked: {when}{' for ' + g('name') if g('name') else ''}. "
            "They'll get a confirmation text and a reminder the day before."
        ), {"type": "booked", "text": f"Booked {when}. Confirmation + reminder texts queued"}
    if name == "escalate_to_human":
        urgent = bool(tool_input.get("urgent"))
        return "Escalated. A team member will follow up.", {
            "type": "urgent" if urgent else "escalate",
            "text": ("Urgent alert sent to the team: " if urgent else "Handed to the team: ") + g("reason")}
    if name == "mark_unqualified":
        return "Tagged Unqualified. Send your one closing text.", {
            "type": "unqualified", "text": f"Tagged Unqualified ({g('reason')}). Automated texts stop"}
    if name == "close_conversation":
        return "Closed. Send your one closing text.", {
            "type": "closed", "text": f"Conversation closed ({g('reason')}). No more follow-ups"}
    if name == "schedule_followup":
        when = _when(g("date"), g("time") or "10:00")
        return f"Follow-up scheduled for {when}.", {
            "type": "followup", "text": f"Check-in scheduled for {when}" + (f": {g('note')}" if g("note") else "")}
    return "Unknown tool.", None


def opening_text(raw: list) -> str:
    """The agent's own first text(s) before the person's first message (the
    scenario opener). clean_history drops them, since the API history must
    start on a user turn, so they go into the system prompt instead."""
    out = []
    for m in raw[:4]:
        if not isinstance(m, dict) or m.get("role") != "assistant":
            break
        out.append(str(m.get("content") or "").strip()[:_MAX_MESSAGE_CHARS])
    return "\n".join(t for t in out if t)


def build_system_prompt(business: str, context: str, tz_name: str | None,
                        scenario: str = "website", opener: str = "") -> str:
    today = datetime.now(_tz(tz_name)).strftime("%A, %B %d, %Y")
    note = _SCENARIOS.get(scenario, _SCENARIOS["website"])
    if opener:
        note += f"\nYour opening text to them was: \"{opener}\""
    return (
        f"{_SYSTEM_PREAMBLE}\nToday is {today}. Resolve relative dates like \"tomorrow\" yourself.\n"
        f"\n--- Business: {business} ---\n{context.strip()}\n"
        f"\n--- Who this person is ---\n{note}\n"
    )


def split_texts(reply_text: str) -> list[str]:
    """One model reply -> the separate chat bubbles it was written as."""
    parts = [p.strip() for p in reply_text.replace("\r", "").split("\n\n")]
    return [p for p in parts if p] or [reply_text.strip()]


async def reply(business: str, context: str, tz_name: str | None, history: list[dict],
                scenario: str = "website", opener: str = "") -> tuple[str, list[dict]]:
    """(reply text, events). Events are the simulated tool actions the page
    shows as system notes (booked, handed to the team, follow-up set ...)."""
    api_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.environ.get("BLUEPRINT_CHAT_MODEL", "claude-opus-5-5")
    scenario = scenario if scenario in _SCENARIOS else "website"
    system_prompt = build_system_prompt(business, context, tz_name, scenario, opener)
    tz = _tz(tz_name)
    messages = list(history)
    events: list[dict] = []

    # Prompt caching: tools + system are identical across this tool loop and
    # the visitor's next message within 5 min. Replies are unchanged.
    cached_system = [{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}]
    for _ in range(_MAX_TOOL_ITERATIONS):
        response = await asyncio.to_thread(
            api_client.beta.messages.create,
            model=model,
            max_tokens=4000,
            system=cached_system,
            tools=_TOOLS,
            messages=messages,
            # Chat turn: keep it quick. Thinking can't be turned off on
            # Opus 5.5, so low effort is the latency lever.
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"],
            extra_body={"fallbacks": "default"},
        )
        try:
            u = response.usage
            print(f"[cache] blueprint_chat in={u.input_tokens} read={u.cache_read_input_tokens or 0} "
                  f"write={u.cache_creation_input_tokens or 0} out={u.output_tokens}", flush=True)
        except Exception:
            pass
        if response.stop_reason == "refusal":
            break
        # Full content (thinking blocks included) goes back within this
        # turn's tool loop, append-only.
        messages.append({"role": "assistant", "content": response.content})
        text = "\n".join(b.text for b in response.content if b.type == "text").strip()
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if not tool_uses:
            return text or "Sorry, could you say that another way?", events
        results = []
        for t in tool_uses:
            out, event = _run_tool(t.name, t.input, tz, scenario)
            if event:
                events.append(event)
            results.append({"type": "tool_result", "tool_use_id": t.id, "content": out})
        messages.append({"role": "user", "content": results})

    return "Sorry, I didn't catch that. Could you rephrase it?", events
