"""Patient intake: what a client's prospect has told us, in one place on
their contact card (OS + client portal). Dylan, 2026-11-19.

Fields (FIELDS below): injury/condition, where, how long, how it started,
pain level, what it stops them doing, what they've tried, goals, age,
insurance/payment, best times, other.

Sources, matched by client + phone (last 10 digits, like the portal inbox):
  - contacts.form_answers (Meta Instant Form questions), source_detail
  - bookings.answer (the booking page's optional question)
  - client_sms_messages (AI text agent + the clinic's own texts)
  - client_dm_messages (Instagram/Facebook DM agent)
  - client_voice_calls.transcript (AI voice agents)
  - contacts.notes (the clinic's / Dylan's own notes)

Claude reads all of it and fills the fields (extract()). It only runs when
the sources changed (sha1 fingerprint), so re-checking is free. A field
someone typed by hand (by = 'manual') is never overwritten by the AI.

run() every 10 min: prospects with any activity in the last 2 hours.
GET on a card that was never extracted kicks one off in the background.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from datetime import datetime, timezone

import anthropic

from db import get_pool

FIELDS = [
    ("concern", "Injury / condition"),
    ("body_area", "Where it hurts"),
    ("duration", "How long they've had it"),
    ("cause", "How it started"),
    ("pain_level", "Pain level"),
    ("impact", "What it's stopping them doing"),
    ("tried_before", "What they've already tried"),
    ("goals", "What they want to get back to"),
    ("age", "Age"),
    ("insurance", "Insurance / payment"),
    ("availability", "Best times for them"),
    ("other", "Other notes"),
]
FIELD_KEYS = [k for k, _ in FIELDS]
SOURCES = ["Lead form", "Booking form", "Text messages", "DMs", "Phone call", "Notes"]

_MODEL = os.environ.get("INTAKE_CLAUDE_MODEL", "claude-opus-5-5")
_LAST10 = r"right(regexp_replace({col}, '\D', '', 'g'), 10)"
_MAX_SOURCE_CHARS = 60_000


def field_defs() -> list[dict]:
    return [{"key": k, "label": label} for k, label in FIELDS]


def _phone_eq(col: str, param: str) -> str:
    return f"{_LAST10.format(col=col)} = {_LAST10.format(col=param)}"


def _decode(v, default):
    if v is None:
        return default
    if isinstance(v, str):
        try:
            return json.loads(v)
        except ValueError:
            return default
    return v


async def _gather(conn, contact) -> str:
    """Every source for this prospect as one labeled text block."""
    parts: list[str] = []
    cid, phone = contact["client_id"], contact["phone"]

    answers = _decode(contact["form_answers"], []) or []
    if answers:
        lines = [f"Q: {a.get('question')}\nA: {a.get('answer')}" for a in answers if a.get("answer")]
        if lines:
            parts.append("## Lead form\n" + "\n".join(lines))
    if contact["source_detail"]:
        parts.append(f"## Lead form\n(lead source detail) {contact['source_detail']}")

    if phone:
        rows = await conn.fetch(
            f"""SELECT b.answer, et.ask_question FROM bookings b
                LEFT JOIN booking_event_types et ON et.id = b.event_type_id
                WHERE b.client_id = $1 AND coalesce(b.answer, '') <> '' AND {_phone_eq('b.phone', '$2')}
                ORDER BY b.created_at""", cid, phone)
        if rows:
            parts.append("## Booking form\n" + "\n".join(
                f"Q: {r['ask_question'] or 'Anything we should know?'}\nA: {r['answer']}" for r in rows))

        rows = await conn.fetch(
            f"""SELECT direction, body, created_at FROM client_sms_messages
                WHERE client_id = $1 AND {_phone_eq("(CASE WHEN direction = 'outbound' THEN to_number ELSE from_number END)", '$2')}
                ORDER BY created_at""", cid, phone)
        if rows:
            parts.append("## Text messages\n" + "\n".join(
                f"{'Clinic' if r['direction'] == 'outbound' else 'Patient'}: {r['body']}" for r in rows))

        rows = await conn.fetch(
            f"""SELECT dialed_at, transcript, summary FROM client_voice_calls
                WHERE client_id = $1 AND dialed_at IS NOT NULL AND source <> 'test'
                  AND (coalesce(transcript, '') <> '' OR coalesce(summary, '') <> '')
                  AND {_phone_eq('phone', '$2')}
                ORDER BY dialed_at""", cid, phone)
        for r in rows:
            parts.append(f"## Phone call ({r['dialed_at']:%b %d})\n{r['transcript'] or r['summary']}")

    rows = await conn.fetch(
        f"""SELECT m.direction, m.body FROM client_dm_messages m
            JOIN client_dm_threads t ON t.id = m.thread_id
            WHERE t.client_id = $1 AND (t.contact_id = $2
                  OR ($3::text IS NOT NULL AND t.phone IS NOT NULL AND {_phone_eq('t.phone', '$3')}))
            ORDER BY m.created_at""", cid, contact["id"], phone)
    if rows:
        parts.append("## DMs\n" + "\n".join(
            f"{'Clinic' if r['direction'] == 'outbound' else 'Patient'}: {r['body']}" for r in rows))

    if contact["notes"]:
        parts.append(f"## Notes\n{contact['notes']}")

    text = "\n\n".join(parts)
    # Keep the most recent material if a thread is enormous.
    return text[-_MAX_SOURCE_CHARS:]


_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        **{k: {
            "type": "object",
            "properties": {
                "value": {"type": "string"},
                "source": {"type": "string", "enum": SOURCES + [""]},
            },
            "required": ["value", "source"],
            "additionalProperties": False,
        } for k in FIELD_KEYS},
    },
    "required": ["summary", *FIELD_KEYS],
    "additionalProperties": False,
}

_SYSTEM = """You fill in a physical therapy / healthcare clinic's intake card for one prospective patient, from everything they have told the clinic so far (lead form answers, booking form, texts, DMs, phone call transcripts, staff notes).

Fields:
- concern: the injury or condition, in plain words (e.g. "Lower back pain, sciatica down the left leg")
- body_area: where it hurts
- duration: how long they've been dealing with it
- cause: how it started (injury, surgery, gradual...)
- pain_level: pain level or severity as they described it
- impact: what it stops them doing (work, sleep, sport, kids...)
- tried_before: treatments they've already tried (chiro, meds, injections, other PT, nothing...)
- goals: what they want to get back to
- age: their age if stated
- insurance: insurance or payment details/preferences they mentioned
- availability: days/times that work for them
- other: anything else the clinician should know (other conditions, surgery dates, red flags, preferences)

Rules:
- Only record what the PATIENT (or staff notes) actually said. Never guess or infer. Unknown = empty value and empty source.
- Lines starting "Clinic:" are the clinic or its AI assistant talking; a question it asked is not an answer.
- Keep each value short (one line), in the patient's own terms. If later messages update an earlier answer, use the latest.
- source = the section the value came from (pick the most direct one).
- summary: 1-2 plain sentences a clinician can read in five seconds. Empty if there's nothing clinical yet.
- Fields listed under "Already filled by hand" are confirmed by staff: leave them empty in your output."""


async def _call_claude(source_text: str, manual: dict, client_id: int | None = None) -> dict:
    client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    known = "\n".join(f"- {k}: {v}" for k, v in manual.items()) or "(none)"
    resp = await client.messages.create(
        model=_MODEL,
        max_tokens=4000,
        system=_SYSTEM,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": _SCHEMA}},
        messages=[{"role": "user", "content": f"Already filled by hand:\n{known}\n\n# What we have on this prospect\n\n{source_text}"}],
    )
    import ai_usage
    await ai_usage.record(resp, "patient_intake", client_id)
    if resp.stop_reason == "refusal":
        raise RuntimeError("The model declined to read this conversation.")
    text = next((b.text for b in resp.content if b.type == "text"), "")
    return json.loads(text)


async def extract(contact_id: str, force: bool = False) -> dict | None:
    """Re-read this prospect's sources and update their intake. No-op when
    nothing changed since the last run (unless force)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        contact = await conn.fetchrow(
            "SELECT id, client_id, phone, notes, form_answers, source_detail FROM contacts "
            "WHERE id = $1 AND client_id IS NOT NULL AND NOT is_client_anchor", contact_id)
        if not contact:
            return None
        row = await conn.fetchrow("SELECT * FROM patient_intake WHERE contact_id = $1", contact_id)
        source_text = await _gather(conn, contact)
    fingerprint = hashlib.sha1(source_text.encode()).hexdigest()
    fields = _decode(row["fields"], {}) if row else {}
    if row and row["fingerprint"] == fingerprint and not force:
        return dict(row)
    if not source_text.strip():
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO patient_intake (contact_id, client_id, fingerprint, extracted_at)
                   VALUES ($1, $2, $3, now())
                   ON CONFLICT (contact_id) DO UPDATE SET fingerprint = $3, extracted_at = now(), error = NULL""",
                contact_id, contact["client_id"], fingerprint)
        return None

    manual = {k: v["value"] for k, v in fields.items() if v.get("by") == "manual" and v.get("value")}
    try:
        out = await _call_claude(source_text, manual, contact["client_id"])
    except Exception as e:
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO patient_intake (contact_id, client_id, error) VALUES ($1, $2, $3)
                   ON CONFLICT (contact_id) DO UPDATE SET error = $3""",
                contact_id, contact["client_id"], f"{type(e).__name__}: {e}"[:400])
        print(f"[patient-intake] {contact_id} extraction failed: {e}", flush=True)
        return None

    now = datetime.now(timezone.utc).isoformat()
    for k in FIELD_KEYS:
        if fields.get(k, {}).get("by") == "manual":
            continue
        got = out.get(k) or {}
        value = (got.get("value") or "").strip()
        if value:
            prev = fields.get(k) or {}
            fields[k] = {"value": value, "source": got.get("source") or "", "by": "ai",
                         "updated_at": prev.get("updated_at") if prev.get("value") == value else now}
        elif k in fields:
            fields.pop(k)
    async with pool.acquire() as conn:
        saved = await conn.fetchrow(
            """INSERT INTO patient_intake (contact_id, client_id, fields, summary, fingerprint, extracted_at, error, updated_at)
               VALUES ($1, $2, $3::jsonb, $4, $5, now(), NULL, now())
               ON CONFLICT (contact_id) DO UPDATE SET fields = $3::jsonb, summary = $4, fingerprint = $5,
                   extracted_at = now(), error = NULL, updated_at = now()
               RETURNING *""",
            contact_id, contact["client_id"], json.dumps(fields), (out.get("summary") or "").strip() or None, fingerprint)
    return dict(saved)


def _shape(row) -> dict:
    fields = _decode(row["fields"], {}) if row else {}
    return {
        "fields": fields,
        "summary": row["summary"] if row else None,
        "extracted_at": row["extracted_at"] if row else None,
        "error": row["error"] if row else None,
        "field_defs": field_defs(),
    }


_inflight: set[str] = set()


async def _background(contact_id: str) -> None:
    if contact_id in _inflight:
        return
    _inflight.add(contact_id)
    try:
        await extract(contact_id)
    finally:
        _inflight.discard(contact_id)


async def get(contact_id: str) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM patient_intake WHERE contact_id = $1", contact_id)
    data = _shape(row)
    if not row or row["extracted_at"] is None:
        asyncio.create_task(_background(contact_id))
        data["pending"] = True
    return data


async def refresh(contact_id: str) -> dict:
    await extract(contact_id, force=True)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM patient_intake WHERE contact_id = $1", contact_id)
    return _shape(row)


async def save_manual(contact_id: str, client_id: int, updates: dict) -> dict:
    """{key: value}: typed by the clinic or Dylan. An empty value clears
    the field and hands it back to the AI."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT fields FROM patient_intake WHERE contact_id = $1", contact_id)
        fields = _decode(row["fields"], {}) if row else {}
        now = datetime.now(timezone.utc).isoformat()
        for k, v in updates.items():
            if k not in FIELD_KEYS:
                continue
            v = (v or "").strip()
            if v:
                fields[k] = {"value": v[:1000], "source": "Entered by hand", "by": "manual", "updated_at": now}
            else:
                fields.pop(k, None)
        row = await conn.fetchrow(
            """INSERT INTO patient_intake (contact_id, client_id, fields, updated_at) VALUES ($1, $2, $3::jsonb, now())
               ON CONFLICT (contact_id) DO UPDATE SET fields = $3::jsonb, updated_at = now(),
                   fingerprint = CASE WHEN $4 THEN NULL ELSE patient_intake.fingerprint END
               RETURNING *""",
            contact_id, client_id, json.dumps(fields), any(not (v or "").strip() for v in updates.values()))
    return _shape(row)


async def run() -> None:
    """Every 10 min: re-check prospects with any activity in the last 2h."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        ids = [r["id"] for r in await conn.fetch(
            f"""
            WITH active AS (
                SELECT client_id, {_LAST10.format(col="CASE WHEN direction = 'outbound' THEN to_number ELSE from_number END")} AS p
                  FROM client_sms_messages WHERE created_at > now() - interval '2 hours'
                UNION SELECT client_id, {_LAST10.format(col='phone')} FROM client_voice_calls
                  WHERE updated_at > now() - interval '2 hours' AND coalesce(transcript, '') <> ''
                UNION SELECT client_id, {_LAST10.format(col='phone')} FROM bookings
                  WHERE created_at > now() - interval '2 hours' AND coalesce(answer, '') <> ''
            )
            SELECT DISTINCT c.id FROM contacts c
            LEFT JOIN active a ON a.client_id = c.client_id AND a.p = {_LAST10.format(col='c.phone')}
            WHERE c.client_id IS NOT NULL AND NOT c.is_client_anchor
              AND (a.p IS NOT NULL
                   OR c.updated_at > now() - interval '2 hours'
                   OR c.id IN (SELECT t.contact_id FROM client_dm_threads t JOIN client_dm_messages m ON m.thread_id = t.id
                               WHERE m.created_at > now() - interval '2 hours' AND t.contact_id IS NOT NULL))
            LIMIT 200
            """)]
    for cid in ids:
        try:
            await extract(cid)
        except Exception as e:
            print(f"[patient-intake] {cid}: {e}", flush=True)
