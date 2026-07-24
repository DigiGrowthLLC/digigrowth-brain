"""
SMS Inbox router — Twilio inbound webhooks + opening-message handoff + manual send.

Endpoints (all under /api except the public webhook):
  POST /webhooks/sms           — Twilio posts inbound SMS here (no auth)
  GET  /api/sms/conversations  — list all threads
  GET  /api/sms/conversations/{phone} — thread messages
  POST /api/sms/send           — manual outbound send
  POST /api/sms/conversations/{phone}/close — close thread ({"disposition": "booked"|"not_interested"})
  POST /sms/conversations/{phone}/interested — toggle the interested flag on an active thread

No AI auto-reply: once a contact enters "sms-handoff" status, send_opening_message()
sends a single opener. All further replies land in the inbox for manual response only.
"""

import json
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Request, Response
from twilio.rest import Client as TwilioClient

from db import get_pool
from merge_fields import apply_merge_fields

router         = APIRouter()   # authenticated API routes
webhook_router = APIRouter()  # public Twilio webhook

OPENING_MESSAGE = "Hey is this {first_name}?"

# Fixed SMS sequence steps, editable in Business Resources → Outreach
# Templates → SMS Sequence (dialer.py's /dialer/sequence-template
# GET/PUT). Each step's body is stored under dialer_settings key
# f"seq_{key}". Order here is the order shown in the SMS inbox's
# SEQUENCE dropdown (routers/sms.py get_sequence()).
SEQUENCE_STEPS = [
    ("curiosity_opener", "1. Initial Message"),
    ("relevance", "2. Primed Message"),
    ("guarantee", "3. Engaged Message"),
    ("ask", "4. Call To Action"),
    ("cta", "5. Booking Link"),
]

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


def _phone_match(col: str, param: str) -> str:
    """
    Normalized-phone match fragment (last 10 digits) — CRM numbers come in as
    "(754) 291-5582" (Google Places format) while Twilio's inbound webhook
    always reports E.164 "+17542915582". Same approach as dialer.py.
    `param` is the query's positional placeholder (e.g. "$1") holding the
    phone value to compare `col` against.
    """
    return (
        f"right(regexp_replace({col}, '\\D', '', 'g'), 10) = "
        f"right(regexp_replace({param}, '\\D', '', 'g'), 10)"
    )


async def _get_or_create_conversation(conn, phone: str) -> dict:
    """
    Resolve `phone` (any format) to its one canonical conversation, matching
    by normalized digits so an inbound E.164 reply lands in the same thread
    an outbound message created under the CRM's stored phone format.
    """
    row = await conn.fetchrow(
        f"SELECT * FROM sms_conversations WHERE {_phone_match('phone', '$1')}", phone
    )
    if row:
        return dict(row)

    contact = await conn.fetchrow(
        f"SELECT id, business, owner, city, grade, opener, phone FROM contacts "
        f"WHERE {_phone_match('phone', '$1')}",
        phone,
    )
    # Prefer the contact's own stored phone as the canonical key so any future
    # outbound send (which always uses contact.phone) matches this same row.
    canonical_phone = contact["phone"] if contact and contact["phone"] else phone
    contact_id = contact["id"] if contact else None

    await conn.execute(
        """
        INSERT INTO sms_conversations (contact_id, phone, messages, status)
        VALUES ($1, $2, '[]', 'active')
        """,
        contact_id,
        canonical_phone,
    )
    return {
        "contact_id": contact_id,
        "phone": canonical_phone,
        "messages": "[]",
        "status": "active",
    }


async def _store_message(conn, phone: str, role: str, body: str):
    conv = await conn.fetchrow(
        f"SELECT messages, phone FROM sms_conversations WHERE {_phone_match('phone', '$1')}", phone
    )
    msgs = json.loads(conv["messages"]) if conv else []
    msgs.append({"role": role, "content": body, "ts": datetime.now(timezone.utc).isoformat()})

    # Store against the conversation's own canonical phone (not necessarily
    # the format `phone` arrived in) if a conversation already exists.
    canonical_phone = conv["phone"] if conv else phone

    await conn.execute(
        f"UPDATE sms_conversations SET messages = $1, updated_at = now() WHERE {_phone_match('phone', '$2')}",
        json.dumps(msgs),
        canonical_phone,
    )

    direction = "inbound" if role == "user" else "outbound"
    contact_row = await conn.fetchrow(
        f"SELECT id FROM contacts WHERE {_phone_match('phone', '$1')}", canonical_phone
    )
    contact_id = contact_row["id"] if contact_row else None

    await conn.execute(
        """
        INSERT INTO sms_messages (contact_id, phone, direction, body)
        VALUES ($1, $2, $3, $4)
        """,
        contact_id,
        canonical_phone,
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

    pool = await get_pool()
    async with pool.acquire() as conn:
        template_row = await conn.fetchrow("SELECT value FROM dialer_settings WHERE key = 'info_sms'")
        template = template_row["value"] if template_row and template_row["value"] else INFO_MESSAGE
        body = template.replace("{first_name}", first_name)

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
            SELECT sc.id, sc.phone, sc.status, sc.disposition, sc.updated_at,
                   c.business, c.owner,
                   (SELECT body FROM sms_messages
                    WHERE phone = sc.phone
                    ORDER BY sent_at DESC LIMIT 1) AS last_message,
                   (SELECT direction FROM sms_messages
                    WHERE phone = sc.phone
                    ORDER BY sent_at DESC LIMIT 1) AS last_direction
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
            return {"phone": phone, "messages": [], "status": "active", "disposition": None}

        # Viewing the thread counts as reading it — clears it from the
        # dashboard's "Needs Reply" list (same read-tracking pattern as
        # Agent Activity's mark-read).
        await conn.execute(
            "UPDATE sms_conversations SET last_read_at = now() WHERE phone = $1", phone
        )

        msgs_raw = await conn.fetch(
            "SELECT direction, body, sent_at FROM sms_messages WHERE phone = $1 ORDER BY sent_at",
            phone,
        )

    return {
        "phone":       phone,
        "contact_id":  conv["contact_id"],
        "status":      conv["status"],
        "disposition": conv["disposition"],
        "business":    conv["business"],
        "owner":       conv["owner"],
        "grade":       conv["grade"],
        "messages":    [dict(m) for m in msgs_raw],
    }


@router.get("/sms/sequence/{phone}")
async def get_sequence(phone: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT key, value FROM dialer_settings WHERE key = ANY($1)",
            [f"seq_{key}" for key, _ in SEQUENCE_STEPS],
        )
        values = {r["key"]: r["value"] for r in rows}

        contact = await conn.fetchrow(
            f"SELECT owner, business, opener FROM contacts WHERE {_phone_match('phone', '$1')}",
            phone,
        )

    contact_dict = dict(contact) if contact else None
    steps = []
    for key, label in SEQUENCE_STEPS:
        body = (values.get(f"seq_{key}") or "").strip()
        if not body:
            continue
        steps.append({"label": label, "text": apply_merge_fields(body, contact_dict)})

    return {"ok": True, "sequence_title": "SMS Sequence", "steps": steps}


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


_CLOSE_DISPOSITION_TO_CONTACT_STATUS = {
    "booked":        "appointment-booked",
    "not_interested": "not-interested",
}


@router.post("/sms/conversations/{phone}/close")
async def close_conversation(phone: str, payload: Optional[dict] = None):
    """Close a thread. `disposition` is 'booked' (default) or 'not_interested' —
    determines both the closed-thread badge and the linked contact's status."""
    disposition = (payload or {}).get("disposition", "booked")
    if disposition not in _CLOSE_DISPOSITION_TO_CONTACT_STATUS:
        disposition = "booked"

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE sms_conversations SET status = 'closed', disposition = $2, updated_at = now() WHERE phone = $1",
            phone, disposition,
        )
        row = await conn.fetchrow(
            "SELECT contact_id FROM sms_conversations WHERE phone = $1", phone
        )
        if row and row["contact_id"]:
            await conn.execute(
                "UPDATE contacts SET status = $2, updated_at = now() WHERE id = $1",
                row["contact_id"], _CLOSE_DISPOSITION_TO_CONTACT_STATUS[disposition],
            )
    return {"ok": True}


@router.post("/sms/conversations/{phone}/interested")
async def toggle_interested(phone: str):
    """Toggle the 'interested' flag on an active (not yet closed) thread.
    Doesn't close the thread or touch the linked contact's status."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status, disposition FROM sms_conversations WHERE phone = $1", phone
        )
        if not row:
            return {"ok": False, "error": "conversation not found"}
        if row["status"] == "closed":
            return {"ok": False, "error": "conversation is closed"}

        new_disposition = None if row["disposition"] == "interested" else "interested"
        await conn.execute(
            "UPDATE sms_conversations SET disposition = $2, updated_at = now() WHERE phone = $1",
            phone, new_disposition,
        )
    return {"ok": True, "disposition": new_disposition}


@router.delete("/sms/conversations/{phone}")
async def delete_conversation(phone: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM sms_messages WHERE phone = $1", phone)
        await conn.execute("DELETE FROM sms_conversations WHERE phone = $1", phone)
    return {"ok": True}
