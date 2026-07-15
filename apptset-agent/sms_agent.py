"""
SMS Appointment Setting Agent — DM Conversion System

Behavioural conversion funnel: opening → primed → engaged → cta → booking → closed_booked
Messages fetched live from Notion before every send (never cached).
Intent classified by Claude Haiku (10 tokens). Objections handled free-form (80 tokens).
Outbound: Mon-Fri only. Inbound replies: 24/7.
"""

import io
import json
import os
import re
import sqlite3
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import anthropic
from dotenv import load_dotenv

import notion_log

# Only redirect stdout when running as a standalone script, not when imported by server.py
if __name__ == "__main__" or sys.stdout.encoding.lower().replace("-", "") != "utf8":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
    except Exception:
        pass

load_dotenv()

_db_lock = threading.Lock()
DB_PATH  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sms_conversations.db")

_claude = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

EST = ZoneInfo("America/New_York")

# ── Stage machine ─────────────────────────────────────────────────────────────

STAGE_TRANSITIONS = {
    # (current_stage, intent) → next_stage
    ("opening",  "CONFIRMS"):       "primed",
    ("primed",   "INTERESTED"):     "engaged",
    ("engaged",  "AGREES"):         "cta",
    ("engaged",  "THUMBS_UP"):      "cta",
    ("cta",      "YES_VIDEO"):      "booking",
    ("cta",      "AGREES"):         "booking",
    ("cta",      "THUMBS_UP"):      "booking",
    ("booking",  "BOOKED_CONFIRM"): "closed_booked",
    ("cta",      "BOOKED_CONFIRM"): "closed_booked",
}

# Intents that close the conversation as dead
DEAD_INTENTS = {"NOT_INTERESTED"}

# All valid intent labels
INTENT_LABELS = {
    "CONFIRMS", "INTERESTED", "OBJECTION", "NOT_INTERESTED",
    "YES_VIDEO", "THUMBS_UP", "AGREES", "BOOKED_CONFIRM",
}

# ── Claude prompts ────────────────────────────────────────────────────────────

CLASSIFY_SYSTEM = """\
You are an intent classifier for a sales SMS conversation.
Classify the prospect's reply with exactly one label from this list:
CONFIRMS, INTERESTED, OBJECTION, NOT_INTERESTED, YES_VIDEO, THUMBS_UP, AGREES, BOOKED_CONFIRM

Definitions:
- CONFIRMS: they verify their identity ("yes", "yep", "that's me") — ONLY use this at the opening stage when they are confirming who they are. Do NOT use this at any other stage.
- INTERESTED: curiosity, questions, or requests for more info — "how does that work?", "tell me more", "what exactly do you do?", "how do you get those results?", "sounds interesting, how?" — use this when they want to know more before committing
- OBJECTION: pushback, hesitation, or concern but not a hard no — "I already have someone", "not sure about the price", "we're pretty busy"
- NOT_INTERESTED: explicit disinterest or a hard no — "not interested", "stop texting me", "we're good"
- YES_VIDEO: they agreed to watch a video or loom link
- THUMBS_UP: 👍 or equivalent one-tap positive reaction
- AGREES: explicit willingness to move forward — "sure", "sounds good", "let's do it", "yes I'd be open to a call", "that's worth a conversation", "yeah let's chat", "yes that sounds good", "it's worth a quick chat"
- BOOKED_CONFIRM: they confirm they've booked a call or appointment

Stage context matters:
- At "opening": a plain "yes" or "yep" = CONFIRMS (identity check)
- At "primed": "yes we do", "yes", "yeah" = INTERESTED (confirming the question is relevant)
- At "engaged": if they express agreement AND ask a question ("definitely worth a conversation, how does it work?"), classify as AGREES — the agreement is the stronger signal; pure questions with no agreement = INTERESTED
- At "cta": "sure", "sounds good", "yes" = AGREES (agreeing to a call)

Reply with the label only. No explanation, no punctuation."""

OBJECTION_SYSTEM = """\
You are Dylan from DigiGrowth texting a fitness studio owner in a cold outreach conversation.
The prospect asked a question or raised a concern.

Core rule: ALWAYS talk about results, never explain the process. The HOW is for the call.
- Wrong: "We use paid ads and AI automation to book leads"
- Right: "Studios like yours are adding 5-15k a month — that's what we're talking about here"

Rules:
- 1 sentence only — use the reference document language as closely as possible
- Sound like a real person texting — casual, confident, no corporate tone
- No filler openers ("Great question", "Absolutely", "Totally get that")
- No emojis
- If they ask HOW it works: talk about the result, not the mechanism — "We've been able to generate studios like yours 5-15k a month" not "we run paid ads"
- If they ask WHAT the call is about: one sentence — it's a quick chat to walk through whether it applies to them
- If they raise a price concern: reframe around what the result is worth, no numbers
- If they're skeptical about results: anchor to the guarantee or a specific outcome from the reference
- Do NOT add any closing question or CTA — just the one-sentence answer, nothing more"""

NOT_INTERESTED_REPLY = (
    "No worries at all — I appreciate you being straight with me. "
    "If anything changes down the road, feel free to reach back out. Take care!"
)

BOOKED_REPLY = (
    "Awesome — looking forward to it! Check your email for the confirmation. "
    "Talk soon."
)

# ── Message sending helpers ───────────────────────────────────────────────────

def _split_sentences(text, max_per_chunk=1):
    """
    Split a message into SMS-sized chunks of max_per_chunk sentences (default 1).
    1. Split on explicit 'Message N:' labels Dylan uses in Notion
    2. For each part: collapse newlines into spaces (Notion soft returns are mid-sentence),
       then split on sentence-ending punctuation
    3. Group sentences into chunks of max_per_chunk
    """
    # Step 1: split on explicit Message N: / Message #N: labels
    parts = re.split(r'(?i)\bMessage\s*#?\d+\s*:\s*', text)
    parts = [p.strip() for p in parts if p.strip()]

    sentences = []
    for part in parts:
        # Step 2: collapse newlines into spaces, then split on sentence boundaries
        flat = " ".join(l.strip() for l in part.split('\n') if l.strip())
        sents = re.split(r'(?<=[.!?])\s+', flat)
        sentences.extend(s.strip() for s in sents if s.strip())

    # Step 3: group into max 2-sentence chunks
    final = []
    for i in range(0, len(sentences), max_per_chunk):
        chunk = " ".join(sentences[i:i + max_per_chunk])
        if chunk:
            final.append(chunk)

    return final if final else [text]


def _send_sms_parts(config, contact_id, text, delay=10):
    """
    Split text into per-sentence chunks and send each with a delay between them.
    Always waits `delay` seconds before the first send to simulate natural typing.
    """
    import ghl as ghl_mod
    chunks = _split_sentences(text)
    for chunk in chunks:
        time.sleep(delay)
        ghl_mod.send_sms(config, contact_id, chunk)


# ── Database ──────────────────────────────────────────────────────────────────

def _init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                phone              TEXT PRIMARY KEY,
                contact_id         TEXT,
                lead_json          TEXT,
                messages           TEXT DEFAULT '[]',
                status             TEXT DEFAULT 'active',
                stage              TEXT DEFAULT 'opening',
                follow_up_count    INTEGER DEFAULT 0,
                follow_up_due_at   TEXT,
                last_inbound_at    TEXT,
                created_at         TEXT,
                updated_at         TEXT
            )
        """)
        # Migrate existing tables that may be missing the new columns
        for col, definition in [
            ("stage",            "TEXT DEFAULT 'opening'"),
            ("follow_up_count",  "INTEGER DEFAULT 0"),
            ("follow_up_due_at", "TEXT"),
            ("last_inbound_at",  "TEXT"),
        ]:
            try:
                conn.execute(f"ALTER TABLE conversations ADD COLUMN {col} {definition}")
            except Exception:
                pass
        conn.commit()


def _load_convo(phone):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("""
            SELECT contact_id, lead_json, messages, status,
                   stage, follow_up_count, follow_up_due_at, last_inbound_at
            FROM conversations WHERE phone = ?
        """, (phone,)).fetchone()
    if not row:
        return None
    return {
        "contact_id":      row[0],
        "lead":            json.loads(row[1]),
        "messages":        json.loads(row[2]),
        "status":          row[3],
        "stage":           row[4] or "opening",
        "follow_up_count": row[5] or 0,
        "follow_up_due_at": row[6],
        "last_inbound_at": row[7],
    }


def _save_convo(phone, contact_id, lead, messages, status, stage,
                follow_up_count=0, follow_up_due_at=None, last_inbound_at=None):
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO conversations
                (phone, contact_id, lead_json, messages, status, stage,
                 follow_up_count, follow_up_due_at, last_inbound_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(phone) DO UPDATE SET
                messages         = excluded.messages,
                status           = excluded.status,
                stage            = excluded.stage,
                follow_up_count  = excluded.follow_up_count,
                follow_up_due_at = excluded.follow_up_due_at,
                last_inbound_at  = excluded.last_inbound_at,
                updated_at       = excluded.updated_at
        """, (
            phone, contact_id, json.dumps(lead), json.dumps(messages),
            status, stage, follow_up_count, follow_up_due_at, last_inbound_at, now, now,
        ))
        conn.commit()


# ── Follow-up timing ──────────────────────────────────────────────────────────

def _next_9am_est():
    """Return the next 9:00 AM EST as a UTC ISO string (skip weekends)."""
    now_est = datetime.now(EST)
    candidate = now_est.replace(hour=9, minute=0, second=0, microsecond=0)
    if now_est >= candidate:
        candidate += timedelta(days=1)
    # Skip weekends (Mon=0 … Sun=6)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate.astimezone(timezone.utc).isoformat()


def _followup_due_at(follow_up_count, created_at_iso):
    """
    Return the UTC ISO timestamp when the next follow-up should fire.
    count 1 (first follow-up)  → now + 3h
    count 2 (second follow-up) → next 9am EST weekday
    count 3 (third follow-up)  → created_at + 48h
    """
    now_utc = datetime.now(timezone.utc)
    if follow_up_count == 1:
        return (now_utc + timedelta(hours=3)).isoformat()
    if follow_up_count == 2:
        return _next_9am_est()
    # count == 3
    created = datetime.fromisoformat(created_at_iso)
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return (created + timedelta(hours=48)).isoformat()


def _is_weekday():
    return datetime.now(EST).weekday() < 5


# ── Claude helpers ────────────────────────────────────────────────────────────

def _classify_intent(message, stage, config):
    """Classify a prospect reply into one of INTENT_LABELS. Returns the label string."""
    prompt = (
        f"Current stage: {stage}\n"
        f"Prospect reply: {message}\n\n"
        "Classify with one label."
    )
    try:
        resp = _claude.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            system=[{"type": "text", "text": CLASSIFY_SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": prompt}],
        )
        label = resp.content[0].text.strip().upper()
        return label if label in INTENT_LABELS else "INTERESTED"
    except Exception as e:
        print(f"  ⚠️  Intent classification failed: {e}")
        return "INTERESTED"


_CTA_KEYWORDS = (
    "quick call", "hop on", "jump on a call", "book a call", "discovery call",
    "worth a call", "worth a chat", "schedule a", "chat about it", "apply to",
    "walk through it on", "happy to jump", "happy to chat",
)

def _strip_call_cta(text):
    """Remove any trailing sentence that pushes toward a call or booking."""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    filtered = [s for s in sentences if not any(kw in s.lower() for kw in _CTA_KEYWORDS)]
    return " ".join(filtered).strip() if filtered else text



def _handle_objection(message, lead, stage, config):
    """Generate a 1-2 sentence empathetic objection response."""
    from notion_messages import fetch_reference
    first_name = (lead.get("owner") or "there").split()[0]
    business   = lead.get("business") or "your studio"
    reference  = fetch_reference(config.get("sms_agent", {}).get("reference_page_ids", []))
    ref_section = (
        f"\n\nReference document (Dylan's own words — use this as your primary source, "
        f"closely match the tone and language here):\n{reference}"
    ) if reference else ""
    prompt = (
        f"Prospect: {first_name} ({business})\n"
        f"Stage: {stage}\n"
        f"Their message: {message}\n"
        f"{ref_section}\n\n"
        f"Write a 1-sentence reply that handles this using the reference document above."
    )
    try:
        resp = _claude.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=80,
            system=[{"type": "text", "text": OBJECTION_SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        return _strip_call_cta(text)
    except Exception as e:
        print(f"  ⚠️  Objection handler failed: {e}")
        return "Totally get that — no pressure at all. Happy to circle back whenever the timing feels right."


def _naturalize_opener(template, lead):
    """
    If the lead has an opener that appears verbatim in the template (from [custom opener]
    substitution), use Claude to rewrite the surrounding sentence so it reads naturally.
    Falls back to the template unchanged if Claude fails or opener is absent.
    """
    opener = (lead.get("opener") or "").strip()
    if not opener or opener not in template:
        return template
    prompt = (
        f"This SMS message has an opener detail inserted that may not read naturally:\n\n"
        f"{template}\n\n"
        f"Opener detail: \"{opener}\"\n\n"
        "Rewrite only the part of the sentence where the opener appears so it flows naturally. "
        "Keep everything else word-for-word. Output only the final message text."
    )
    try:
        resp = _claude.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        result = resp.content[0].text.strip()
        return result if result else template
    except Exception as e:
        print(f"  ⚠️  Opener naturalization failed: {e}")
        return template


# ── Outbound send ─────────────────────────────────────────────────────────────

def send_outbound(config, contact_id, lead):
    """
    Send the opening SMS to a new prospect.
    Only fires Mon-Fri. Creates the DB row and schedules follow-up 1 for +3h.
    """
    import ghl as ghl_mod
    from notion_messages import fetch_messages, get_message

    if not _is_weekday():
        print(f"  ⏭  send_outbound skipped (weekend) for {lead.get('phone')}")
        return

    _init_db()
    phone = lead.get("phone", "")

    # Don't double-send if already active
    with _db_lock:
        existing = _load_convo(phone)
    if existing and existing["status"] == "active":
        print(f"  ⏭  send_outbound skipped — active conversation already exists for {phone}")
        return

    try:
        messages  = fetch_messages()
        text      = get_message("opening", messages, lead)
    except Exception as e:
        print(f"  ⚠️  Could not fetch opening message from Notion: {e}")
        return

    if lead.get("opener"):
        text = _naturalize_opener(text, lead)

    try:
        _send_sms_parts(config, contact_id, text)
    except Exception as e:
        print(f"  ⚠️  GHL SMS send failed for {phone}: {e}")
        return

    fup_due = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()

    with _db_lock:
        _save_convo(
            phone, contact_id, lead, [],
            status="active",
            stage="opening",
            follow_up_count=0,
            follow_up_due_at=fup_due,
        )

    notion_log.log_event("OUTBOUND_SENT", lead=lead, extra={"stage": "opening"})
    print(f"  ✅ Opening SMS sent to {phone} | follow-up 1 due at {fup_due}")


# ── Inbound reply handler ─────────────────────────────────────────────────────

def handle_reply(from_phone, body, config):
    """
    Handle an inbound SMS reply. Active 24/7.
    Classifies intent, advances stage machine, sends next message.
    """
    import ghl as ghl_mod
    from notion_messages import fetch_messages, get_message

    _init_db()

    with _db_lock:
        convo = _load_convo(from_phone)

    if convo and convo["status"] != "active":
        print(f"  📱 SMS from {from_phone} — conversation {convo['status']}, ignoring")
        return

    if not convo:
        # Unknown number or no active conversation — look up via GHL
        contact = ghl_mod.get_contact_by_phone(config, from_phone)
        if not contact:
            print(f"  📱 SMS from unknown number {from_phone} — no GHL contact, ignoring")
            return
        tags = [t.lower() for t in (contact.get("tags") or [])]
        if "sms-handoff" not in tags:
            print(f"  📱 SMS from {from_phone} — no sms-handoff tag, ignoring")
            return
        contact_id = contact.get("id", "")
        lead = ghl_mod.contact_to_lead(contact)
        stage = "opening"
        follow_up_count = 0
        messages = []
    else:
        contact_id      = convo["contact_id"]
        lead            = convo["lead"]
        stage           = convo["stage"]
        follow_up_count = convo["follow_up_count"]
        messages        = convo["messages"]

    phone = from_phone
    notion_log.log_event("REPLY_RECEIVED", lead=lead, extra={"stage": stage, "body": body[:200]})

    # Classify intent
    intent = _classify_intent(body, stage, config)
    print(f"  🔍 Intent: {intent} (stage={stage}) | {body[:80]}")

    now_utc = datetime.now(timezone.utc).isoformat()

    # Hard no — close gracefully
    if intent in DEAD_INTENTS:
        try:
            _send_sms_parts(config, contact_id, NOT_INTERESTED_REPLY)
        except Exception as e:
            print(f"  ⚠️  GHL SMS send failed: {e}")
        ghl_mod.add_tag(config, contact_id, "sms-no-response")
        with _db_lock:
            _save_convo(phone, contact_id, lead, messages, "closed_dead", stage,
                        follow_up_count=follow_up_count, last_inbound_at=now_utc)
        notion_log.log_event("CLOSED_DEAD", lead=lead, extra={"stage": stage, "reason": "NOT_INTERESTED"})
        print(f"  ❌ Closed dead (NOT_INTERESTED): {phone}")
        return

    # Objection — handle and hold stage
    if intent == "OBJECTION":
        reply = _handle_objection(body, lead, stage, config)
        try:
            _send_sms_parts(config, contact_id, reply)
        except Exception as e:
            print(f"  ⚠️  GHL SMS send failed: {e}")
        messages.append({"role": "user", "content": body})
        messages.append({"role": "assistant", "content": reply})
        with _db_lock:
            _save_convo(phone, contact_id, lead, messages, "active", stage,
                        follow_up_count=follow_up_count, follow_up_due_at=None,
                        last_inbound_at=now_utc)
        return

    # Check for stage transition
    next_stage = STAGE_TRANSITIONS.get((stage, intent))

    if next_stage == "closed_booked":
        try:
            _send_sms_parts(config, contact_id, BOOKED_REPLY)
        except Exception as e:
            print(f"  ⚠️  GHL SMS send failed: {e}")
        ghl_mod.remove_tag(config, contact_id, "sms-handoff")
        ghl_mod.add_tag(config, contact_id, "appointment-booked")
        messages.append({"role": "user", "content": body})
        messages.append({"role": "assistant", "content": BOOKED_REPLY})
        with _db_lock:
            _save_convo(phone, contact_id, lead, messages, "closed_booked", "closed_booked",
                        follow_up_count=follow_up_count, last_inbound_at=now_utc)
        notion_log.log_event("BOOKED", lead=lead)
        business = lead.get("business") or lead.get("owner") or phone
        print(f"  🎉 Appointment booked: {business} ({phone})")
        return

    if next_stage:
        # Fetch template from Notion, then adapt it to the prospect's reply
        try:
            notion_msgs = fetch_messages()
            template    = get_message(next_stage, notion_msgs, lead)
        except KeyError as e:
            print(f"  ⚠️  Missing Notion message for stage '{next_stage}': {e}")
            return
        except Exception as e:
            print(f"  ⚠️  Notion fetch failed: {e}")
            return

        # Split template into chunks and send verbatim (opener naturalization still applies).
        chunks = _split_sentences(template)
        print(f"  📋 Template split into {len(chunks)} chunk(s): {chunks}")
        sent_parts = []
        for i, chunk in enumerate(chunks, 1):
            try:
                adapted = chunk
                # Naturalize opener per-chunk (only on chunks that contain it)
                if lead.get("opener") and lead["opener"] in adapted:
                    adapted = _naturalize_opener(adapted, lead)
                print(f"  🔤 Chunk {i}: '{adapted[:100]}'")
                time.sleep(10)
                ghl_mod.send_sms(config, contact_id, adapted)
                sent_parts.append(adapted)
                print(f"  📤 Sent chunk {i}/{len(chunks)}: {adapted[:80]}")
            except Exception as e:
                print(f"  ⚠️  Chunk {i} failed: {e} — skipping")

        reply = " ".join(sent_parts)
        if body:  # may already be logged if a pre-answer was sent
            messages.append({"role": "user", "content": body})
        messages.append({"role": "assistant", "content": reply})
        with _db_lock:
            _save_convo(phone, contact_id, lead, messages, "active", next_stage,
                        follow_up_count=0, follow_up_due_at=None,
                        last_inbound_at=now_utc)
        notion_log.log_event("STAGE_ADVANCED", lead=lead,
                             extra={"from_stage": stage, "to_stage": next_stage})
        print(f"  ➡️  Stage advanced: {stage} → {next_stage} ({phone})")
    else:
        # No stage transition — prospect asked a question or expressed vague interest.
        # At engaged/cta stages, answer using reference pages and hold the stage.
        if stage in ("opening", "primed", "engaged", "cta") and intent in ("INTERESTED", "OBJECTION"):
            reply = _handle_objection(body, lead, stage, config)
            if reply:
                reply_chunks = _split_sentences(reply)
                sent_reply_parts = []
                for chunk in reply_chunks:
                    try:
                        time.sleep(10)
                        ghl_mod.send_sms(config, contact_id, chunk)
                        sent_reply_parts.append(chunk)
                        print(f"  💬 Reference reply chunk: {chunk[:80]}")
                    except Exception as e:
                        print(f"  ⚠️  Reference reply chunk failed: {e}")
                full_reply = " ".join(sent_reply_parts)
                messages.append({"role": "user", "content": body})
                messages.append({"role": "assistant", "content": full_reply})

            with _db_lock:
                _save_convo(phone, contact_id, lead, messages, "active", stage,
                            follow_up_count=follow_up_count, follow_up_due_at=None,
                            last_inbound_at=now_utc)
        else:
            print(f"  ℹ️  No transition for ({stage}, {intent}) — holding stage")
            with _db_lock:
                _save_convo(phone, contact_id, lead, messages, "active", stage,
                            follow_up_count=follow_up_count, follow_up_due_at=None,
                            last_inbound_at=now_utc)


# ── Follow-up scheduler ───────────────────────────────────────────────────────

def check_followups(config):
    """
    Scan DB for overdue follow-ups and send them.
    Follow-up messages: Mon-Fri only. Checking: runs 24/7.
    Called every 15 min by server.py background thread.
    """
    import ghl as ghl_mod
    from notion_messages import fetch_messages, get_message

    _init_db()

    if not _is_weekday():
        return

    now_utc = datetime.now(timezone.utc)
    max_followups = config.get("sms_agent", {}).get("max_followups", 3)

    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("""
            SELECT phone, contact_id, lead_json, stage, follow_up_count, created_at
            FROM conversations
            WHERE status = 'active'
              AND follow_up_due_at IS NOT NULL
              AND follow_up_due_at <= ?
        """, (now_utc.isoformat(),)).fetchall()

    if not rows:
        return

    print(f"  ⏰ check_followups: {len(rows)} overdue row(s)")

    for phone, contact_id, lead_json, stage, follow_up_count, created_at in rows:
        lead = json.loads(lead_json)
        new_count = follow_up_count + 1

        if new_count > max_followups:
            # Max follow-ups reached — close as dead
            ghl_mod.add_tag(config, contact_id, "sms-no-response")
            with _db_lock:
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute("""
                        UPDATE conversations
                        SET status='closed_dead', follow_up_due_at=NULL,
                            updated_at=?
                        WHERE phone=?
                    """, (now_utc.isoformat(), phone))
                    conn.commit()
            notion_log.log_event("CLOSED_DEAD", lead=lead,
                                 extra={"stage": stage, "reason": "no_response_max_followups"})
            business = lead.get("business") or lead.get("owner") or phone
            print(f"  ❌ Closed dead (max follow-ups): {business} ({phone})")
            continue

        # Fetch follow-up message from Notion
        fup_stage = f"followup_{new_count}"
        try:
            notion_msgs = fetch_messages()
            text        = get_message(fup_stage, notion_msgs, lead)
        except KeyError:
            print(f"  ⚠️  No Notion page for '{fup_stage}' — skipping {phone}")
            continue
        except Exception as e:
            print(f"  ⚠️  Notion fetch failed for follow-up {new_count}: {e}")
            continue

        try:
            _send_sms_parts(config, contact_id, text)
        except Exception as e:
            print(f"  ⚠️  GHL SMS send failed for follow-up {new_count} to {phone}: {e}")
            continue

        # Schedule next follow-up or clear if this was the last
        if new_count < max_followups:
            next_due = _followup_due_at(new_count + 1, created_at)
        else:
            next_due = None

        with _db_lock:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("""
                    UPDATE conversations
                    SET follow_up_count=?, follow_up_due_at=?, updated_at=?
                    WHERE phone=?
                """, (new_count, next_due, now_utc.isoformat(), phone))
                conn.commit()

        notion_log.log_event("FOLLOWUP_SENT", lead=lead,
                             extra={"stage": stage, "follow_up_count": new_count})
        business = lead.get("business") or lead.get("owner") or phone
        print(f"  📲 Follow-up {new_count} sent to {business} ({phone}) | next due: {next_due or 'none'}")
