"""
SMS Inbox router — Twilio inbound webhooks + AI auto-reply + manual send.

Endpoints (all under /api except the public webhook):
  POST /webhooks/sms           — Twilio posts inbound SMS here (no auth)
  GET  /api/sms/conversations  — list all threads
  GET  /api/sms/conversations/{phone} — thread messages
  POST /api/sms/send           — manual outbound send
  POST /api/sms/conversations/{phone}/close — mark closed / booked
"""

import json
import os
from datetime import datetime, timezone

import anthropic
from fastapi import APIRouter, Request, Response
from twilio.rest import Client as TwilioClient

from db import get_pool

router         = APIRouter()   # authenticated API routes
webhook_router = APIRouter()  # public Twilio webhook

_claude = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

SYSTEM_PROMPT = """\
You are a professional appointment setter texting on behalf of Dylan from Digigrowth \
— a digital marketing agency that helps local businesses grow online and get more customers.

You're texting a business owner who was cold-called but couldn't be reached. Your goal is to \
warm them up, answer questions, handle objections, and book a 15-minute discovery call.

Rules:
- Keep replies SHORT (1-3 sentences). This is SMS, not email.
- Be conversational, friendly, and human — never sound like a bot.
- Don't push too hard. If they say no, acknowledge it gracefully.
- When the prospect agrees to a call, share the booking link and confirm they received it.

After every reply, output a JSON status line on its own line at the very end:
{"status": "ongoing"}   — conversation is still open
{"status": "APPOINTMENT_BOOKED"}  — prospect has clearly agreed and received the booking link

Only use APPOINTMENT_BOOKED after you've shared the link and they've acknowledged it.\
"""

BOOKING_LINK = os.environ.get(
    "BOOKING_LINK",
    "https://link.digigrowthllc.com/widget/booking/tydZBa2ehjdSRZopOMrn",
)


def _twilio():
    return TwilioClient(
        os.environ["TWILIO_ACCOUNT_SID"],
        os.environ["TWILIO_AUTH_TOKEN"],
    )


def _send_twilio(to: str, body: str):
    _twilio().messages.create(
        to=to,
        from_=os.environ["TWILIO_PHONE_NUMBER"],
        body=body,
    )


def _call_claude(messages: list, contact: dict) -> tuple[str, str]:
    """Return (reply_text, status). Status is 'ongoing' or 'APPOINTMENT_BOOKED'."""
    context = (
        f"Prospect info:\n"
        f"- Name: {contact.get('owner') or 'there'}\n"
        f"- Business: {contact.get('business') or 'their business'}\n"
        f"- City: {contact.get('city') or ''}\n"
        f"- Lead grade: {contact.get('grade') or 'C'} (A = highest priority)\n"
        f"- Opener note: {contact.get('opener') or ''}\n\n"
        f"Booking link: {BOOKING_LINK}\n\n"
        "Keep replies under 160 characters when possible. "
        "Always end with the JSON status line on its own line."
    )

    claude_messages = [
        {"role": "user",      "content": f"[Session context]\n{context}"},
        {"role": "assistant", "content": "Understood. I'll respond as the appointment setter."},
    ] + messages

    response = _claude.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=claude_messages,
    )

    full_text = response.content[0].text.strip()
    lines = full_text.splitlines()
    status = "ongoing"
    reply = full_text

    for i in range(len(lines) - 1, -1, -1):
        stripped = lines[i].strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                parsed = json.loads(stripped)
                status = parsed.get("status", "ongoing")
                reply = "\n".join(lines[:i]).strip()
                break
            except json.JSONDecodeError:
                pass

    return reply, status


async def _get_or_create_conversation(conn, phone: str) -> dict:
    row = await conn.fetchrow(
        "SELECT * FROM sms_conversations WHERE phone = $1", phone
    )
    if row:
        return dict(row)

    contact = await conn.fetchrow(
        "SELECT id, business, owner, city, grade, opener FROM contacts WHERE phone = $1",
        phone,
    )
    contact_id = contact["id"] if contact else None

    await conn.execute(
        """
        INSERT INTO sms_conversations (contact_id, phone, messages, status)
        VALUES ($1, $2, '[]', 'active')
        """,
        contact_id,
        phone,
    )
    return {
        "contact_id": contact_id,
        "phone": phone,
        "messages": "[]",
        "status": "active",
    }


async def _store_message(conn, phone: str, role: str, body: str):
    conv = await conn.fetchrow(
        "SELECT messages FROM sms_conversations WHERE phone = $1", phone
    )
    msgs = json.loads(conv["messages"]) if conv else []
    msgs.append({"role": role, "content": body, "ts": datetime.now(timezone.utc).isoformat()})

    await conn.execute(
        "UPDATE sms_conversations SET messages = $1, updated_at = now() WHERE phone = $2",
        json.dumps(msgs),
        phone,
    )

    direction = "inbound" if role == "user" else "outbound"
    contact_row = await conn.fetchrow(
        "SELECT id FROM contacts WHERE phone = $1", phone
    )
    contact_id = contact_row["id"] if contact_row else None

    await conn.execute(
        """
        INSERT INTO sms_messages (contact_id, phone, direction, body)
        VALUES ($1, $2, $3, $4)
        """,
        contact_id,
        phone,
        direction,
        body,
    )


# ── Public Twilio webhook (no auth) ──────────────────────────────────────────

@webhook_router.post("/webhooks/sms")
async def twilio_inbound(request: Request):
    form = await request.form()
    from_phone = form.get("From", "")
    body       = (form.get("Body") or "").strip()

    if not from_phone or not body:
        return Response(content="", media_type="text/plain")

    pool = await get_pool()
    async with pool.acquire() as conn:
        conv = await _get_or_create_conversation(conn, from_phone)

        if conv["status"] == "closed":
            return Response(content="", media_type="text/plain")

        await _store_message(conn, from_phone, "user", body)

        messages = json.loads(conv["messages"] if isinstance(conv["messages"], str) else "[]")
        messages.append({"role": "user", "content": body})

        contact = {}
        if conv["contact_id"]:
            row = await conn.fetchrow(
                "SELECT business, owner, city, grade, opener FROM contacts WHERE id = $1",
                conv["contact_id"],
            )
            if row:
                contact = dict(row)

        try:
            reply, ai_status = _call_claude(messages, contact)
        except Exception as e:
            print(f"Claude error for {from_phone}: {e}")
            return Response(content="", media_type="text/plain")

        await _store_message(conn, from_phone, "assistant", reply)

        if ai_status == "APPOINTMENT_BOOKED":
            await conn.execute(
                "UPDATE sms_conversations SET status = 'closed' WHERE phone = $1",
                from_phone,
            )
            if conv["contact_id"]:
                await conn.execute(
                    "UPDATE contacts SET status = 'appointment-booked', updated_at = now() WHERE id = $1",
                    conv["contact_id"],
                )

    try:
        _send_twilio(from_phone, reply)
    except Exception as e:
        print(f"Twilio send error for {from_phone}: {e}")

    return Response(content="", media_type="text/plain")


# ── Authenticated API endpoints ───────────────────────────────────────────────

@router.get("/sms/conversations")
async def list_conversations():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT sc.id, sc.phone, sc.status, sc.updated_at,
                   c.business, c.owner,
                   (SELECT body FROM sms_messages
                    WHERE phone = sc.phone
                    ORDER BY sent_at DESC LIMIT 1) AS last_message
            FROM sms_conversations sc
            LEFT JOIN contacts c ON c.id = sc.contact_id
            ORDER BY sc.updated_at DESC NULLS LAST
            """
        )
    return [dict(r) for r in rows]


@router.get("/sms/conversations/{phone}")
async def get_conversation(phone: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        conv = await conn.fetchrow(
            """
            SELECT sc.*, c.business, c.owner, c.grade, c.opener
            FROM sms_conversations sc
            LEFT JOIN contacts c ON c.id = sc.contact_id
            WHERE sc.phone = $1
            """,
            phone,
        )
        if not conv:
            return {"phone": phone, "messages": [], "status": "active"}

        msgs_raw = await conn.fetch(
            "SELECT direction, body, sent_at FROM sms_messages WHERE phone = $1 ORDER BY sent_at",
            phone,
        )

    return {
        "phone": phone,
        "status": conv["status"],
        "business": conv["business"],
        "owner": conv["owner"],
        "grade": conv["grade"],
        "messages": [dict(m) for m in msgs_raw],
    }


@router.post("/sms/send")
async def manual_send(payload: dict):
    phone = payload.get("phone", "").strip()
    body  = payload.get("body", "").strip()
    if not phone or not body:
        return {"ok": False, "error": "phone and body required"}

    try:
        _send_twilio(phone, body)
    except Exception as e:
        return {"ok": False, "error": str(e)}

    pool = await get_pool()
    async with pool.acquire() as conn:
        await _get_or_create_conversation(conn, phone)
        await _store_message(conn, phone, "assistant", body)

    return {"ok": True}


@router.post("/sms/conversations/{phone}/close")
async def close_conversation(phone: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE sms_conversations SET status = 'closed', updated_at = now() WHERE phone = $1",
            phone,
        )
        row = await conn.fetchrow(
            "SELECT contact_id FROM sms_conversations WHERE phone = $1", phone
        )
        if row and row["contact_id"]:
            await conn.execute(
                "UPDATE contacts SET status = 'appointment-booked', updated_at = now() WHERE id = $1",
                row["contact_id"],
            )
    return {"ok": True}
