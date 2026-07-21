"""
SMS Inbox router — Twilio inbound webhooks + opening-message handoff + manual send.

Endpoints (all under /api except the public webhook):
  POST /webhooks/sms           — Twilio posts inbound SMS here (no auth)
  GET  /api/sms/conversations  — list all threads
  GET  /api/sms/conversations/{phone} — thread messages
  POST /api/sms/send           — manual outbound send
  POST /api/sms/conversations/{phone}/close — mark closed / booked

No AI auto-reply: once a contact enters "sms-handoff" status, send_opening_message()
sends a single opener. All further replies land in the inbox for manual response only.
"""

import json
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Response
from twilio.rest import Client as TwilioClient

from db import get_pool

router         = APIRouter()   # authenticated API routes
webhook_router = APIRouter()  # public Twilio webhook

OPENING_MESSAGE = "Hey is this {first_name}?"

INFO_MESSAGE = (
    "Hey {first_name}, here's that info — https://digigrowthllc.com. "
    "Take a look and let me know what stands out. If it makes sense to chat more, "
    "I'll follow up in a couple days."
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
    """Store the inbound reply for manual review in the SMS panel. No auto-reply."""
    form = await request.form()
    from_phone = form.get("From", "")
    body       = (form.get("Body") or "").strip()

    if not from_phone or not body:
        return Response(content="", media_type="text/plain")

    pool = await get_pool()
    async with pool.acquire() as conn:
        conv = await _get_or_create_conversation(conn, from_phone)
        if conv["status"] != "closed":
            await _store_message(conn, from_phone, "user", body)

    return Response(content="", media_type="text/plain")


# ── Opening-message handoff (called from crm.py when status → sms-handoff) ──

async def send_opening_message(contact: dict) -> bool:
    """
    Send the one-time opener to a lead that just entered sms-handoff status.
    contact needs at least "phone"; "owner" is used for the first-name greeting.
    Returns True if the message was sent.
    """
    phone = (contact.get("phone") or "").strip()
    if not phone:
        return False

    first_name = (contact.get("owner") or "").split()[0] if contact.get("owner") else "there"
    body = OPENING_MESSAGE.format(first_name=first_name)

    pool = await get_pool()
    async with pool.acquire() as conn:
        conv = await _get_or_create_conversation(conn, phone)
        if conv["status"] == "closed":
            return False
        try:
            _send_twilio(phone, body)
        except Exception as e:
            print(f"Twilio send error (opening message) for {phone}: {e}")
            return False
        await _store_message(conn, phone, "assistant", body)

    return True


async def send_info_message(contact: dict) -> bool:
    """
    Send the "Send Info" text — website + a one-line pitch. Unlike the sms-handoff
    opener, this doesn't require sms-handoff status; it fires for any contact the
    dialer disposition "Send Info" is logged against. Returns True if sent.
    """
    phone = (contact.get("phone") or "").strip()
    if not phone:
        return False

    first_name = (contact.get("owner") or "").split()[0] if contact.get("owner") else "there"
    body = INFO_MESSAGE.format(first_name=first_name)

    pool = await get_pool()
    async with pool.acquire() as conn:
        conv = await _get_or_create_conversation(conn, phone)
        if conv["status"] == "closed":
            return False
        try:
            _send_twilio(phone, body)
        except Exception as e:
            print(f"Twilio send error (info message) for {phone}: {e}")
            return False
        await _store_message(conn, phone, "assistant", body)

    return True


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
        "phone":      phone,
        "contact_id": conv["contact_id"],
        "status":     conv["status"],
        "business":   conv["business"],
        "owner":      conv["owner"],
        "grade":      conv["grade"],
        "messages":   [dict(m) for m in msgs_raw],
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


@router.delete("/sms/conversations/{phone}")
async def delete_conversation(phone: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM sms_messages WHERE phone = $1", phone)
        await conn.execute("DELETE FROM sms_conversations WHERE phone = $1", phone)
    return {"ok": True}
