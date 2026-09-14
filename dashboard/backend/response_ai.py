"""
Self-built, per-client AI appointment-setting agent — replacement for the
Appointwise stub (routers/appointwise_webhooks.py). Called from
routers/client_sms_webhooks.py for every inbound SMS to a client's own
Twilio number, gated by client_marketing_config.response_ai_enabled so
migration off Appointwise is reversible per client (a client with the flag
off still gets forwarded to Appointwise exactly as before).

Same underlying mechanism as routers/agents.py's chat loop (plain Anthropic
Messages API, a system prompt assembled from stored text, a small tool
loop) — just narrower: no file/bash/integration tools, one client-specific
context string instead of a whole directory of files, and no attended chat
UI. Every helper this module calls (client_sms.send_client_sms,
create_appointment_row) goes through db.py's single global asyncpg pool,
which is bound to the main event loop, so handle_inbound_sms() must always
run ON that loop — either awaited directly from the webhook, or as an
APScheduler job (scheduler_registry.py), never on a raw background thread
(a separate thread would need its own event loop, and asyncpg
connections/pools can't cross event loops).

Per-client config also drives:
- response_ai_sequence — an ordered list of short stage descriptions (the
  admin UI's "first text" through "fifth text") woven into the system
  prompt as a loose conversational arc, not a rigid script.
- response_ai_max_chars — an SMS length cap, enforced both as a prompt
  instruction and a hard truncation fallback in handle_inbound_sms().
- response_ai_min_delay_seconds — client_sms_webhooks.py defers the actual
  handle_inbound_sms() call via scheduler_registry when this is set, rather
  than sleeping inline (which would hold the Twilio webhook open and risk
  a timeout/retry).

V1 scope: SMS only. Calendar availability is read-only, via Calendly's API
(calendly_integration.py) when a client has connected a Personal Access
Token (client_marketing_config.calendly_api_token) — the check_availability
tool looks up real open slots so the agent doesn't propose an already-taken
time, but booking still happens the same way it always has: logged
directly into this system (create_appointment_row), same trust level as a
rep manually noting a booked time today. Calendly's API has no endpoint to
create a CONFIRMED booking on someone else's behalf (an invitee always
completes that on Calendly's own page), so this is as far as automation
goes without a client-side click — confirmed scope as of 2026-09-14. A
client with no token connected just gets asked for their preferred
day/time as before (check_availability says so and the model falls back).

Phase 2 (not built): Meta Lead Ads ingestion, once Dylan has a Meta app +
page webhook access — a new POST /webhooks/meta-leadgen endpoint would
verify Meta's webhook challenge, pull lead data via Graph API using the
leadgen_id, resolve to a client via a new client_marketing_config column
(e.g. meta_page_id), create/upsone the contacts row the same way
_get_or_create_contact() below already does, and call a new
initiate_conversation() entry point to send the first outbound message
proactively — handle_inbound_sms() below only ever reacts to an inbound
message, it never starts a thread.
"""
import asyncio
import json
import os
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import anthropic

import calendly_integration
import client_sms
from db import get_pool
from routers.appointments import create_appointment_row
from timezone_lookup import guess_timezone

_MAX_TOOL_ITERATIONS = 4
_HISTORY_LIMIT = 20

_SYSTEM_PREAMBLE = """You are an AI appointment-setting assistant texting on behalf of a real \
local business. You are replying by SMS to a real lead who reached out — respond like a helpful \
staff member, not a chatbot. Keep replies short (SMS-length, 1-3 sentences).

Rules:
- Only state facts, pricing, offers, or guarantees that are explicitly given to you in the \
business info below. Never invent or guess at anything you weren't told.
- If the lead wants to book, and a specific day is on the table, call check_availability for \
that day first — if it returns real open times, offer from those rather than asking blind. If it \
says the calendar isn't connected, just ask for their preferred day and time as usual. Either way, \
confirm the agreed time back to them in one message, then call propose_appointment.
- If the lead asks for something outside what you were told, seems upset, asks for a refund or \
files a complaint, or you're not confident how to respond, call escalate_to_human and let them \
know a team member will follow up.
- Never claim an appointment is booked unless you actually called propose_appointment \
successfully in this same turn.
"""

_TOOLS = [
    {
        "name": "check_availability",
        "description": "Look up REAL open appointment times on the business's calendar for one specific day, if their calendar is connected. Call this before offering a specific time whenever a day is already on the table.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["date"],
        },
    },
    {
        "name": "propose_appointment",
        "description": "Book a tentative appointment for this lead once they've agreed to a specific day and time.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "YYYY-MM-DD"},
                "time": {"type": "string", "description": "HH:MM in 24h format"},
                "notes": {"type": "string", "description": "Anything worth noting for the business, e.g. what the lead is coming in for."},
            },
            "required": ["date", "time"],
        },
    },
    {
        "name": "escalate_to_human",
        "description": "Hand this conversation off to a human team member instead of continuing to auto-respond.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string"},
            },
            "required": ["reason"],
        },
    },
]


async def _get_or_create_conversation(conn, client_id: int, phone: str) -> dict:
    row = await conn.fetchrow(
        """
        INSERT INTO client_lead_conversations (client_id, phone, status, last_message_at)
        VALUES ($1, $2, 'ai_active', now())
        ON CONFLICT (client_id, phone) DO UPDATE SET last_message_at = now()
        RETURNING *
        """,
        client_id, phone,
    )
    return dict(row)


async def _get_or_create_contact(conn, client_id: int, phone: str) -> str | None:
    """Same ownership rules as client_portal.py's portal_create_lead() —
    never claim a phone number that's already someone else's anchor contact
    or another client's lead. Returns None (rather than raising) if the
    phone is already claimed elsewhere, so a booking still succeeds with
    contact_id=None rather than blocking the lead's reply over an edge case."""
    existing = await conn.fetchrow(
        "SELECT id, client_id, is_client_anchor FROM contacts WHERE phone = $1", phone,
    )
    if existing:
        if existing["is_client_anchor"] or (existing["client_id"] is not None and existing["client_id"] != client_id):
            return None
        return existing["id"]
    row = await conn.fetchrow(
        "INSERT INTO contacts (id, phone, status, client_id) VALUES ($1, $2, 'new', $3) RETURNING id",
        str(uuid.uuid4()), phone, client_id,
    )
    return row["id"]


async def _load_recent_messages(conn, client_id: int, phone: str) -> list[dict]:
    rows = await conn.fetch(
        """
        SELECT direction, body FROM client_sms_messages
        WHERE client_id = $1 AND (from_number = $2 OR to_number = $2)
        ORDER BY created_at DESC LIMIT $3
        """,
        client_id, phone, _HISTORY_LIMIT,
    )
    return [
        {"role": "user" if r["direction"] == "inbound" else "assistant", "content": r["body"]}
        for r in reversed(rows)
    ]


def _build_system_prompt(
    business_name: str, context: str, sequence: list[str], max_words: int | None, rules: str,
) -> str:
    parts = [_SYSTEM_PREAMBLE]
    if sequence:
        steps = "\n".join(f"{i+1}. {step}" for i, step in enumerate(sequence) if step and step.strip())
        parts.append(
            "\nGeneral conversation arc to aim for (loose guidance, not a script — always answer "
            "the lead's own questions first, then steer back toward whichever of these is next):\n"
            f"{steps}\n"
        )
    if max_words:
        parts.append(f"\nHard limit: every reply must be {max_words} words or fewer.\n")
    if rules and rules.strip():
        parts.append(
            "\nRules — read these before every reply and make sure you follow them:\n"
            f"{rules.strip()}\n"
        )
    parts.append(f"\n--- Business: {business_name} ---\n{context.strip()}\n")
    return "".join(parts)


async def handle_inbound_sms(client_id: int, from_phone: str, body: str) -> None:
    """Entry point — called directly from client_sms_webhooks.py when a
    client has no reply-delay configured, or as a scheduler_registry-backed
    deferred job when response_ai_min_delay_seconds > 0. Never raises — a
    bug here must never break the webhook (or the scheduler) that runs it.
    `body` isn't used directly (the inbound row is already inserted into
    client_sms_messages by the caller before this runs, so
    _load_recent_messages already picks it up) — kept as a parameter for
    logging/clarity at the call site."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT cmc.response_ai_context, cmc.response_ai_sequence, cmc.response_ai_max_words, "
                "cmc.response_ai_rules, c.name FROM client_marketing_config cmc "
                "JOIN clients c ON c.id = cmc.client_id WHERE cmc.client_id = $1",
                client_id,
            )
            if not row:
                return

            conversation = await _get_or_create_conversation(conn, client_id, from_phone)
            if conversation["status"] == "escalated":
                return  # a human has taken over this thread — stay silent

            messages = await _load_recent_messages(conn, client_id, from_phone)

        # asyncpg has no JSONB codec registered on this pool (matches
        # client_marketing.py's _decode_config) — comes back as a raw string.
        sequence = row["response_ai_sequence"]
        if isinstance(sequence, str):
            sequence = json.loads(sequence)
        max_words = row["response_ai_max_words"]

        system_prompt = _build_system_prompt(
            row["name"], row["response_ai_context"] or "", sequence or [], max_words, row["response_ai_rules"] or "",
        )
        reply_text = await _run_agent_turn(client_id, from_phone, system_prompt, messages)
        if reply_text:
            words = reply_text.split()
            if max_words and len(words) > max_words:
                # Belt-and-suspenders — the prompt already instructs the
                # limit, this just guarantees it's never violated even if
                # the model ignores it.
                reply_text = " ".join(words[:max_words])
            await client_sms.send_client_sms(client_id, from_phone, reply_text)
    except Exception as e:
        print(f"[response_ai] handle_inbound_sms failed for client={client_id} phone={from_phone}: {e}")


async def _run_agent_turn(client_id: int, from_phone: str, system_prompt: str, messages: list[dict]) -> str | None:
    api_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.environ.get("AGENTS_CLAUDE_MODEL", "claude-sonnet-5")
    text_parts: list[str] = []

    for _ in range(_MAX_TOOL_ITERATIONS):
        response = await asyncio.to_thread(
            api_client.messages.create,
            model=model, max_tokens=1024, system=system_prompt, tools=_TOOLS, messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})
        text_parts = [b.text for b in response.content if b.type == "text"]
        tool_uses = [b for b in response.content if b.type == "tool_use"]

        if not tool_uses:
            return "\n".join(text_parts).strip() or None

        tool_results = []
        for tool_use in tool_uses:
            result = await _execute_tool(client_id, from_phone, tool_use.name, tool_use.input)
            tool_results.append({"type": "tool_result", "tool_use_id": tool_use.id, "content": result})
        messages.append({"role": "user", "content": tool_results})

    return "\n".join(text_parts).strip() or None


async def _execute_tool(client_id: int, from_phone: str, tool_name: str, tool_input: dict) -> str:
    pool = await get_pool()

    if tool_name == "check_availability":
        async with pool.acquire() as conn:
            token = await conn.fetchval(
                "SELECT calendly_api_token FROM client_marketing_config WHERE client_id = $1", client_id,
            )
        if not token:
            return "Calendar isn't connected for this business — ask the lead for their preferred day and time instead."
        date_str = (tool_input.get("date") or "").strip()
        try:
            tz_name = guess_timezone(from_phone)
            tz = ZoneInfo(tz_name)
            slots = await calendly_integration.get_available_times(
                token, f"{date_str}T00:00:00Z", f"{date_str}T23:59:59Z",
            )
            if not slots:
                return f"No open times found on {date_str}. Ask if another day works."
            times = ", ".join(
                datetime.fromisoformat(s["start_time"].replace("Z", "+00:00")).astimezone(tz).strftime("%-I:%M %p")
                for s in slots[:8]
            )
            return f"Real open times on {date_str} (lead's local time): {times}"
        except Exception as e:
            return f"Couldn't check the calendar ({e}) — ask for their preferred day and time instead."

    if tool_name == "propose_appointment":
        try:
            async with pool.acquire() as conn:
                contact_id = await _get_or_create_contact(conn, client_id, from_phone)
            tz_name = guess_timezone(from_phone)
            # create_appointment_row acquires its own connection internally
            # (it's shared with the manual-booking HTTP route) — don't hold
            # one open across this call, just for the contact lookup above
            # and the status update below.
            row = await create_appointment_row({
                "contact_id": contact_id,
                "prospect_phone": from_phone,
                "date": tool_input.get("date"),
                "time": tool_input.get("time"),
                "timezone": tz_name,
            })
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE client_lead_conversations SET status = 'booked' WHERE client_id = $1 AND phone = $2",
                    client_id, from_phone,
                )
            return f"Booked appointment id={row['id']} for {tool_input.get('date')} {tool_input.get('time')} ({tz_name})."
        except ValueError as e:
            return f"Booking failed: {e}"

    if tool_name == "escalate_to_human":
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE client_lead_conversations SET status = 'escalated' WHERE client_id = $1 AND phone = $2",
                client_id, from_phone,
            )
        return "Escalated to a human team member."

    return f"Unknown tool: {tool_name}"
