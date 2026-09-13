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
UI. Runs as a normal awaited call on the request's own event loop (NOT
backgrounded onto a separate thread) — every helper this module calls
(client_sms.send_client_sms, create_appointment_row) goes through db.py's
single global asyncpg pool, which is bound to the main event loop; a
separate thread would need its own event loop, and asyncpg connections/pools
can't cross event loops. Keeping this synchronous-but-awaited, with a low
tool-iteration cap and modest max_tokens, keeps a turn fast enough to stay
well within Twilio's webhook response window (the same tradeoff the
existing Appointwise-forwarding call already makes, just usually faster).

V1 scope: SMS only, no live calendar-availability check (none exists
anywhere in this system) — the agent proposes/confirms a time and books it
directly, same trust level as a rep manually noting a booked time today.

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
import os
import uuid

import anthropic

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
- If the lead wants to book, get their preferred day and time, confirm it back to them in one \
message, then call propose_appointment.
- If the lead asks for something outside what you were told, seems upset, asks for a refund or \
files a complaint, or you're not confident how to respond, call escalate_to_human and let them \
know a team member will follow up.
- Never claim an appointment is booked unless you actually called propose_appointment \
successfully in this same turn.
"""

_TOOLS = [
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


def _build_system_prompt(business_name: str, context: str) -> str:
    return f"{_SYSTEM_PREAMBLE}\n--- Business: {business_name} ---\n{context.strip()}\n"


async def handle_inbound_sms(client_id: int, from_phone: str, body: str) -> None:
    """Entry point called from client_sms_webhooks.py for every inbound SMS
    to a client's own number, when that client has response_ai_enabled.
    Never raises — a bug here must never break the webhook it's called
    from. `body` isn't used directly (the inbound row is already inserted
    into client_sms_messages by the caller before this runs, so
    _load_recent_messages already picks it up) — kept as a parameter for
    logging/clarity at the call site."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT cmc.response_ai_context, c.name FROM client_marketing_config cmc "
                "JOIN clients c ON c.id = cmc.client_id WHERE cmc.client_id = $1",
                client_id,
            )
            if not row:
                return

            conversation = await _get_or_create_conversation(conn, client_id, from_phone)
            if conversation["status"] == "escalated":
                return  # a human has taken over this thread — stay silent

            messages = await _load_recent_messages(conn, client_id, from_phone)

        system_prompt = _build_system_prompt(row["name"], row["response_ai_context"] or "")
        reply_text = await _run_agent_turn(client_id, from_phone, system_prompt, messages)
        if reply_text:
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
