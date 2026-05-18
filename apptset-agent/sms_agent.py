"""
AI SMS Appointment Setting Agent — core logic

Handles inbound SMS replies from prospects tagged 'sms-handoff' in GHL.
Uses Claude to hold a two-way conversation and book appointments.

The initial outbound SMS is sent by GHL's existing sms_handoff workflow.
This agent activates when the prospect replies.
"""

import json
import os
import sqlite3
import threading
from datetime import datetime

import anthropic
from dotenv import load_dotenv

load_dotenv()

_db_lock = threading.Lock()
DB_PATH  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sms_conversations.db")

MAX_MESSAGES_DEFAULT = 15

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


# ── Database ──────────────────────────────────────────────────────────────────

def _init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                phone       TEXT PRIMARY KEY,
                contact_id  TEXT,
                lead_json   TEXT,
                messages    TEXT DEFAULT '[]',
                status      TEXT DEFAULT 'active',
                created_at  TEXT,
                updated_at  TEXT
            )
        """)
        conn.commit()


def _load_conversation(phone):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT contact_id, lead_json, messages, status FROM conversations WHERE phone = ?",
            (phone,)
        ).fetchone()
    if not row:
        return None
    contact_id, lead_json, messages_json, status = row
    return {
        "contact_id": contact_id,
        "lead":       json.loads(lead_json),
        "messages":   json.loads(messages_json),
        "status":     status,
    }


def _save_conversation(phone, contact_id, lead, messages, status="active"):
    now = datetime.utcnow().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO conversations (phone, contact_id, lead_json, messages, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(phone) DO UPDATE SET
                messages   = excluded.messages,
                status     = excluded.status,
                updated_at = excluded.updated_at
        """, (phone, contact_id, json.dumps(lead), json.dumps(messages), status, now, now))
        conn.commit()


# ── Claude ────────────────────────────────────────────────────────────────────

def _call_claude(messages, lead, config):
    """Call Claude with full conversation history. Returns (reply_text, status)."""
    client       = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    persona      = config.get("sms_agent", {}).get("persona", "Dylan from Digigrowth")
    booking_link = config.get("sms_agent", {}).get("booking_link", "[booking link]")

    context = (
        f"Prospect info:\n"
        f"- Name: {lead.get('owner', 'there')}\n"
        f"- Business: {lead.get('business', 'their business')}\n"
        f"- City: {lead.get('city', '')}\n"
        f"- Lead grade: {lead.get('grade', 'C')} (A = highest priority)\n"
        f"- Opener note: {lead.get('opener', '')}\n\n"
        f"Your name: {persona}\n"
        f"Booking link: {booking_link}\n\n"
        "Keep replies under 160 characters when possible. "
        "Always end with the JSON status line on its own line."
    )

    claude_messages = [
        {"role": "user",      "content": f"[Session context]\n{context}"},
        {"role": "assistant", "content": "Understood. I'll respond as the appointment setter."},
    ] + messages

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=claude_messages,
    )

    full_text = response.content[0].text.strip()

    # Parse JSON status from the last non-empty line
    lines  = full_text.splitlines()
    status = "ongoing"
    reply  = full_text
    for i in range(len(lines) - 1, -1, -1):
        stripped = lines[i].strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                parsed = json.loads(stripped)
                status = parsed.get("status", "ongoing")
                reply  = "\n".join(lines[:i]).strip()
                break
            except json.JSONDecodeError:
                pass

    return reply, status


# ── GHL SMS send ──────────────────────────────────────────────────────────────

def _send_sms(contact_id, body, config):
    import ghl as ghl_mod
    return ghl_mod.send_sms(config, contact_id, body)


# ── Main inbound handler ──────────────────────────────────────────────────────

def handle_reply(from_phone, body, config):
    """
    Process an inbound SMS reply from a prospect.
    Only handles contacts tagged 'sms-handoff' in GHL (or with an active DB conversation).
    """
    import ghl as ghl_mod

    _init_db()

    # Check existing DB conversation first (avoids a GHL API call on every message)
    with _db_lock:
        convo = _load_conversation(from_phone)

    if convo and convo["status"] == "closed":
        print(f"  📱 SMS from {from_phone} — conversation closed (appointment booked), ignoring")
        return

    if convo:
        lead       = convo["lead"]
        messages   = convo["messages"]
        contact_id = convo["contact_id"]
    else:
        # First reply — look up in GHL and verify sms-handoff tag
        contact = ghl_mod.get_contact_by_phone(config, from_phone)
        if not contact:
            print(f"  📱 SMS from unknown number {from_phone} — no GHL contact, ignoring")
            return

        tags = [t.lower() for t in (contact.get("tags") or [])]
        if "sms-handoff" not in tags:
            print(f"  📱 SMS from {from_phone} — no 'sms-handoff' tag in GHL, ignoring")
            return

        contact_id = contact.get("id", "")
        lead = {
            **ghl_mod.contact_to_lead(contact),
            "city":  contact.get("city", ""),
            "state": contact.get("state", ""),
        }
        messages = []

    max_messages   = config.get("sms_agent", {}).get("max_messages", MAX_MESSAGES_DEFAULT)
    outbound_count = sum(1 for m in messages if m["role"] == "assistant")
    if outbound_count >= max_messages:
        print(f"  📱 SMS from {from_phone} — max messages ({max_messages}) reached, closing")
        ghl_mod.add_tag(config, contact_id, "sms-no-response")
        with _db_lock:
            _save_conversation(from_phone, contact_id, lead, messages, "closed")
        return

    # Append inbound message
    messages.append({"role": "user", "content": body})

    # Generate reply
    try:
        reply, status = _call_claude(messages, lead, config)
    except Exception as e:
        print(f"  ⚠️  Claude API error for {from_phone}: {e}")
        return

    # Append outbound message
    messages.append({"role": "assistant", "content": reply})

    # Persist before sending (state saved even if SMS fails)
    conv_status = "closed" if status == "APPOINTMENT_BOOKED" else "active"
    with _db_lock:
        _save_conversation(from_phone, contact_id, lead, messages, conv_status)

    # Send the reply
    try:
        _send_sms(contact_id, reply, config)
    except Exception as e:
        print(f"  ⚠️  GHL SMS send error to {from_phone}: {e}")
        return

    # Appointment booked — swap tags in GHL
    if status == "APPOINTMENT_BOOKED":
        business = lead.get("business") or lead.get("owner") or from_phone
        print(f"  🎉 Appointment booked via SMS: {business} ({from_phone})")
        try:
            ghl_mod.remove_tag(config, contact_id, "sms-handoff")
            ghl_mod.add_tag(config, contact_id, "appointment-booked")
        except Exception as e:
            print(f"  ⚠️  GHL tag update failed for {from_phone}: {e}")
