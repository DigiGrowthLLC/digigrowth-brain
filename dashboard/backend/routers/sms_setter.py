"""
SMS setter endpoints (see sms_setter_ai.py for how the pieces fit).

Inbox:
  GET  /api/sms-setter/draft?phone=...      — latest pending draft for a thread (or null)
  POST /api/sms-setter/draft/regenerate     — {"phone": ...} ask the worker for a fresh draft
  POST /api/sms-setter/draft/{id}/dismiss   — Dylan rejected it
  POST /api/sms-setter/draft/{id}/book      — BOOK IT: Meet invite + appointment for a "book" draft
  GET  /api/sms-setter/mode                 — {"mode", "worker_online", "worker_last_seen"}
  POST /api/sms-setter/mode                 — {"mode": "off" | "draft" | "auto"}
  GET  /api/sms-setter/stats                — per-action sent-unedited / edited / dismissed / auto-sent
  POST /api/sms-setter/revive               — {"threads": [{"phone", "note", "due"?}]} dropped threads → agent check-ins
  GET  /api/sms-setter/follow-ups           — every scheduled check-in, soonest first (Inbox FOLLOW-UPS view)
  POST /api/sms-setter/follow-ups/reschedule — {"phone", "date", "time"} prospect's local time
  POST /api/sms-setter/follow-ups/cancel    — {"phone"}
  POST /api/sms-setter/follow-ups/schedule  — {"phone", "date", "time", "note"?} Dylan books a check-in by hand
  GET  /api/sms-setter/lessons              — what the setter learned from Dylan's own replies
  POST /api/sms-setter/lessons/capture      — {"phone"} TEACH: learn from Dylan's latest reply on a thread
  PATCH  /api/sms-setter/lessons/{id}       — {"situation"?, "lesson"?, "status"?: "active" | "disabled"}
  DELETE /api/sms-setter/lessons/{id}

Local worker (apptset-agent/sms_setter_worker.py, on Dylan's PC):
  POST /api/sms-setter/worker/heartbeat
  GET  /api/sms-setter/worker/queue         — system prompt, output schema, and threads to draft
  POST /api/sms-setter/worker/submit        — {"phone", "last_inbound_at", "result", "model"}
  POST /api/sms-setter/worker/flush         — retry auto-sends held for business hours
  POST /api/sms-setter/worker/lesson        — {"id", "result"} a distilled lesson (see sms_setter_ai)

Marking a draft as sent from the Inbox happens in routers/sms.py's
manual_send (the Inbox passes ai_draft_id along with the text), so the
recorded sent_body is exactly what went out.
"""
import json

from fastapi import APIRouter, HTTPException

from timezone_lookup import guess_timezone, prospect_timezone

import sms_setter_ai
from db import get_pool

router = APIRouter()

_REGEN_KEY = "sms_ai_setter_regen"   # JSON list of phones the Inbox asked to redraft


def _row_to_draft(row) -> dict:
    d = dict(row)
    if isinstance(d.get("details"), str):
        d["details"] = json.loads(d["details"])
    return d


async def _regen_list(conn) -> list[str]:
    raw = await sms_setter_ai._setting(conn, _REGEN_KEY)
    return json.loads(raw) if raw else []


@router.get("/sms-setter/draft")
async def get_draft(phone: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, phone, action, reply, details, rationale, created_at
            FROM sms_ai_drafts
            WHERE right(regexp_replace(phone, '\\D', '', 'g'), 10) = right(regexp_replace($1, '\\D', '', 'g'), 10)
              AND status = 'pending'
            ORDER BY created_at DESC LIMIT 1
            """,
            phone,
        )
        regen_pending = sms_setter_ai._digits(phone) in {sms_setter_ai._digits(p) for p in await _regen_list(conn)}
    return {"draft": _row_to_draft(row) if row else None, "regenerating": regen_pending}


@router.post("/sms-setter/draft/regenerate")
async def regenerate_draft(payload: dict):
    """Queues the thread for the worker — drafting happens on Dylan's PC, so
    this returns immediately and the new draft shows up on the Inbox's next
    poll (if the worker is online)."""
    phone = (payload.get("phone") or "").strip()
    if not phone:
        raise HTTPException(400, "phone required")
    pool = await get_pool()
    async with pool.acquire() as conn:
        phones = await _regen_list(conn)
        if sms_setter_ai._digits(phone) not in {sms_setter_ai._digits(p) for p in phones}:
            phones.append(phone)
        await sms_setter_ai._set_setting(conn, _REGEN_KEY, json.dumps(phones))
        status = await sms_setter_ai.worker_status(conn)
    return {"ok": True, **status}


@router.post("/sms-setter/draft/{draft_id}/dismiss")
async def dismiss_draft(draft_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE sms_ai_drafts SET status = 'dismissed', decided_at = now() WHERE id = $1 AND status = 'pending' "
            "RETURNING phone, action",
            draft_id,
        )
        # Rejecting a "check back later" draft rejects the check-in it scheduled.
        if row and row["action"] == "follow_up":
            await sms_setter_ai.schedule_follow_up(conn, row["phone"], None)
    return {"ok": True}


@router.post("/sms-setter/draft/{draft_id}/book")
async def book_draft(draft_id: int):
    """Draft mode's BOOK IT: creates the Google Meet invite (emailed to the
    prospect) and the appointment row (reminders + Booked stage). Dylan
    still sends the confirmation text himself with USE."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await sms_setter_ai.book_draft(conn, draft_id)
    if result != "booked":
        raise HTTPException(422, result)
    return {"ok": True}


@router.post("/sms-setter/revive")
async def revive(payload: dict):
    """{"threads": [{"phone", "note", "due"?}]} — hand dropped threads back to
    the agent as scheduled check-ins (see sms_setter_ai.revive_threads)."""
    threads = payload.get("threads")
    if not isinstance(threads, list) or not threads:
        raise HTTPException(400, "threads required")
    pool = await get_pool()
    async with pool.acquire() as conn:
        return {"results": await sms_setter_ai.revive_threads(conn, threads)}


@router.get("/sms-setter/follow-ups")
async def list_follow_ups():
    """Every check-in the agent has scheduled ("busy, text me tomorrow"),
    soonest first: when it goes out (UTC + the prospect's timezone, so the
    Inbox can show both), the agent's reasoning, and their last text."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT sc.phone, sc.contact_id, sc.ai_followup_due_at, sc.ai_followup_set_at, sc.ai_followup_note,
                   sc.ai_followup_by, c.owner, c.business, c.city, c.state,
                   (SELECT body FROM sms_messages m WHERE m.phone = sc.phone AND m.direction = 'inbound'
                    ORDER BY m.sent_at DESC LIMIT 1) AS last_inbound
            FROM sms_conversations sc LEFT JOIN contacts c ON c.id = sc.contact_id
            WHERE sc.ai_followup_due_at IS NOT NULL AND sc.status <> 'closed'
              AND (sc.disposition IS NULL OR sc.ai_followup_by = 'dylan')
            ORDER BY sc.ai_followup_due_at
            """
        )
        status = await sms_setter_ai.worker_status(conn)
    return {
        "follow_ups": [
            {
                "phone": r["phone"], "contact_id": r["contact_id"], "owner": r["owner"], "business": r["business"],
                "due_at": r["ai_followup_due_at"].isoformat(),
                "set_at": r["ai_followup_set_at"].isoformat() if r["ai_followup_set_at"] else None,
                "timezone": guess_timezone(r["phone"], r["city"], r["state"]),
                "note": r["ai_followup_note"], "last_inbound": r["last_inbound"],
                "set_by": r["ai_followup_by"] or "agent",
            }
            for r in rows
        ],
        **status,
    }


@router.post("/sms-setter/follow-ups/reschedule")
async def reschedule_follow_up(payload: dict):
    """{"phone", "date": "YYYY-MM-DD", "time": "HH:MM"} in the PROSPECT's
    local time — the same way the agent picks it. Keeps the note and who
    set it."""
    phone = (payload.get("phone") or "").strip()
    pool = await get_pool()
    async with pool.acquire() as conn:
        due = await _due_from_payload(conn, phone, payload)
        cur = await conn.fetchrow("SELECT ai_followup_note, ai_followup_by FROM sms_conversations WHERE phone = $1", phone)
        await sms_setter_ai.schedule_follow_up(
            conn, phone, due, cur and cur["ai_followup_note"], (cur and cur["ai_followup_by"]) or "agent",
        )
    return {"ok": True, "due_at": due.isoformat()}


async def _due_from_payload(conn, phone: str, payload: dict):
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo

    tz_name = await prospect_timezone(conn, phone)
    try:
        due = datetime.strptime(f"{payload.get('date')} {payload.get('time') or '10:00'}", "%Y-%m-%d %H:%M").replace(
            tzinfo=ZoneInfo(tz_name))
    except (ValueError, TypeError):
        raise HTTPException(400, "date (YYYY-MM-DD) and time (HH:MM) required")
    if due <= datetime.now(timezone.utc):
        raise HTTPException(400, "pick a time in the future")
    return due


@router.post("/sms-setter/follow-ups/schedule")
async def schedule_follow_up(payload: dict):
    """Dylan books a check-in on a thread himself: {"phone", "date", "time"}
    in the prospect's local time, plus an optional "note" telling the agent
    what to say. When it's due the worker writes it (following the note)
    and auto mode sends it, exactly like one the agent scheduled. Replaces
    any check-in already set. Works on booked threads too (checking in
    after the discovery call is a main use) — the Booked disposition stays.
    A Not Interested mark is cleared (he's explicitly asking to follow up),
    and a closed thread is reopened, since a closed thread silently drops
    the reply the check-in is fishing for."""
    phone = (payload.get("phone") or "").strip()
    if not phone:
        raise HTTPException(400, "phone required")
    pool = await get_pool()
    async with pool.acquire() as conn:
        conv = await conn.fetchrow(
            "SELECT phone, status, disposition FROM sms_conversations "
            "WHERE right(regexp_replace(phone, '\\D', '', 'g'), 10) = $1",
            sms_setter_ai._digits(phone),
        )
        if not conv:
            raise HTTPException(404, "no SMS thread for that number")
        due = await _due_from_payload(conn, conv["phone"], payload)
        if conv["status"] == "closed" or conv["disposition"] == "not_interested":
            await conn.execute(
                "UPDATE sms_conversations SET status = 'active', updated_at = now(), "
                "disposition = CASE WHEN disposition = 'not_interested' THEN NULL ELSE disposition END "
                "WHERE phone = $1",
                conv["phone"],
            )
        await sms_setter_ai.schedule_follow_up(
            conn, conv["phone"], due, (payload.get("note") or "").strip() or None, by="dylan",
        )
    return {"ok": True, "due_at": due.isoformat()}


@router.post("/sms-setter/follow-ups/cancel")
async def cancel_follow_up(payload: dict):
    phone = (payload.get("phone") or "").strip()
    if not phone:
        raise HTTPException(400, "phone required")
    pool = await get_pool()
    async with pool.acquire() as conn:
        await sms_setter_ai.schedule_follow_up(conn, phone, None)
    return {"ok": True}


# ── Lessons (learning from Dylan's own replies) ───────────────────────────────

@router.get("/sms-setter/lessons")
async def list_lessons():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT l.id, l.phone, l.trigger, l.ai_action, l.ai_reply, l.ai_rationale, l.dylan_reply, l.situation,
                   l.lesson, l.status, l.analysis_note, l.created_at, l.analyzed_at,
                   sc.contact_id, c.owner, c.business
            FROM sms_setter_lessons l
            LEFT JOIN sms_conversations sc ON sc.phone = l.phone
            LEFT JOIN contacts c ON c.id = sc.contact_id
            WHERE l.status <> 'replaced'
            ORDER BY (l.status = 'collecting') DESC, l.created_at DESC
            LIMIT 300
            """
        )
        status = await sms_setter_ai.worker_status(conn)
    return {
        "lessons": [
            {**dict(r), "created_at": r["created_at"].isoformat(),
             "analyzed_at": r["analyzed_at"].isoformat() if r["analyzed_at"] else None}
            for r in rows
        ],
        **status,
    }


@router.post("/sms-setter/lessons/capture")
async def capture_lesson(payload: dict):
    """TEACH: learn from the texts Dylan sent himself after the prospect's
    latest message (sms_setter_ai.capture_from_thread)."""
    phone = (payload.get("phone") or "").strip()
    if not phone:
        raise HTTPException(400, "phone required")
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await sms_setter_ai.capture_from_thread(conn, phone)
        status = await sms_setter_ai.worker_status(conn)
    if not result["ok"]:
        raise HTTPException(400, result["error"])
    return {**result, **status}


@router.patch("/sms-setter/lessons/{lesson_id}")
async def update_lesson(lesson_id: int, payload: dict):
    """Dylan's edits. An edited lesson is active (it's his wording now)
    unless he's switching it off in the same call."""
    fields, args = [], [lesson_id]
    for key in ("situation", "lesson"):
        if isinstance(payload.get(key), str) and payload[key].strip():
            args.append(payload[key].strip())
            fields.append(f"{key} = ${len(args)}")
    status = payload.get("status")
    if status is not None and status not in ("active", "disabled"):
        raise HTTPException(400, "status must be 'active' or 'disabled'")
    if not (status or fields):
        raise HTTPException(400, "nothing to update")
    args.append(status or "active")
    fields.append(f"status = ${len(args)}")
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                f"UPDATE sms_setter_lessons SET {', '.join(fields)}, updated_at = now() "
                "WHERE id = $1 AND status <> 'collecting' RETURNING id, situation, lesson, status",
                *args,
            )
            if row and row["status"] == "active" and not (row["situation"] and row["lesson"]):
                raise HTTPException(400, "add a situation and lesson text before turning it on")
    if not row:
        raise HTTPException(404, "lesson not found (or still being analyzed)")
    return {"ok": True, **dict(row)}


@router.delete("/sms-setter/lessons/{lesson_id}")
async def delete_lesson(lesson_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM sms_setter_lessons WHERE id = $1", lesson_id)
    return {"ok": True}


@router.get("/sms-setter/mode")
async def get_mode():
    pool = await get_pool()
    async with pool.acquire() as conn:
        return {"mode": await sms_setter_ai.get_mode(conn), **await sms_setter_ai.worker_status(conn)}


@router.post("/sms-setter/mode")
async def set_mode(payload: dict):
    mode = payload.get("mode")
    if mode not in ("off", "draft", "auto"):
        raise HTTPException(400, "mode must be 'off', 'draft', or 'auto'")
    pool = await get_pool()
    async with pool.acquire() as conn:
        await sms_setter_ai.set_mode(conn, mode)
        return {"mode": mode, **await sms_setter_ai.worker_status(conn)}


@router.get("/sms-setter/stats")
async def stats():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT action,
                   COUNT(*) FILTER (WHERE status = 'sent' AND sent_body IN (reply, _with_second)) AS sent_unedited,
                   COUNT(*) FILTER (WHERE status = 'sent' AND sent_body NOT IN (reply, _with_second)) AS sent_edited,
                   COUNT(*) FILTER (WHERE status = 'dismissed')                  AS dismissed,
                   COUNT(*) FILTER (WHERE status = 'auto_sent')                  AS auto_sent,
                   COUNT(*) FILTER (WHERE status = 'pending')                    AS pending,
                   COUNT(*) FILTER (WHERE status = 'superseded')                 AS superseded
            FROM (
                -- A draft used with its second text (the Inbox's USE puts both
                -- in the reply box) still counts as unedited.
                SELECT *, reply || E'\n\n' || COALESCE(details->>'second_text', '') AS _with_second
                FROM sms_ai_drafts
            ) d
            GROUP BY action ORDER BY action
            """
        )
    return {"by_action": [dict(r) for r in rows]}


# ── Local worker ──────────────────────────────────────────────────────────────

@router.post("/sms-setter/worker/heartbeat")
async def worker_heartbeat():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await sms_setter_ai.record_heartbeat(conn)
        return {"mode": await sms_setter_ai.get_mode(conn)}


@router.get("/sms-setter/worker/queue")
async def worker_queue(limit: int = 5):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await sms_setter_ai.record_heartbeat(conn)
        mode = await sms_setter_ai.get_mode(conn)
        await sms_setter_ai.task_todos(conn)
        await sms_setter_ai.backfill_todo_links(conn)
        lessons = await sms_setter_ai.active_lessons(conn)
        lesson_items = await sms_setter_ai.lesson_queue(conn)
        items = []
        # Explicit REGENERATE requests first — they work even in "off" mode
        # (Dylan clicked the button himself).
        regen = await _regen_list(conn)
        for phone in regen:
            items.extend(await sms_setter_ai.build_queue(conn, phone=phone))
        if regen:
            await sms_setter_ai._set_setting(conn, _REGEN_KEY, "[]")
        if mode != "off":
            seen = {i["phone"] for i in items}
            items.extend(i for i in await sms_setter_ai.build_queue(conn, limit=limit) if i["phone"] not in seen)
    return {
        "mode": mode,
        "system_prompt": sms_setter_ai.system_prompt(lessons),
        "schema": sms_setter_ai.DRAFT_SCHEMA,
        "items": items,
        # Learning from Dylan: replies of his to distill into lessons. Not
        # gated on mode, since learning sends nothing.
        "lesson_system_prompt": sms_setter_ai.lesson_system_prompt(),
        "lesson_schema": sms_setter_ai.LESSON_SCHEMA,
        "lessons": lesson_items,
    }


@router.post("/sms-setter/worker/submit")
async def worker_submit(payload: dict):
    phone = (payload.get("phone") or "").strip()
    result = payload.get("result")
    if not phone or not isinstance(result, dict):
        raise HTTPException(400, "phone and result required")
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await sms_setter_ai.submit_draft(conn, phone, payload.get("last_inbound_at"), result, payload.get("model"))


@router.post("/sms-setter/worker/flush")
async def worker_flush():
    pool = await get_pool()
    async with pool.acquire() as conn:
        return {"sent": await sms_setter_ai.flush_pending(conn)}


@router.post("/sms-setter/worker/lesson")
async def worker_lesson(payload: dict):
    result = payload.get("result")
    if not payload.get("id") or not isinstance(result, dict):
        raise HTTPException(400, "id and result required")
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await sms_setter_ai.submit_lesson(conn, int(payload["id"]), result)
