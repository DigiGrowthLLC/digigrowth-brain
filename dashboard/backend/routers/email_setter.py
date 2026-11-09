"""
Email setter endpoints (see email_setter_ai.py for how the pieces fit).

Inbox:
  GET  /api/email-setter/mode                — {"mode", "worker_online", "worker_last_seen"}
  POST /api/email-setter/mode                — {"mode": "off" | "draft" | "auto"}
  GET  /api/email-setter/draft?contact_id=   — latest pending draft on any of the contact's email threads
  POST /api/email-setter/draft/regenerate    — {"thread_id"} ask the worker for a fresh draft
  POST /api/email-setter/draft/{id}/dismiss
  POST /api/email-setter/draft/{id}/book     — BOOK IT for a "book" draft (Meet invite + appointment)

Local worker (apptset-agent/sms_setter_worker.py — one worker serves both setters):
  GET  /api/email-setter/worker/queue        — system prompt, schema, threads to draft
  POST /api/email-setter/worker/submit       — {"thread_id", "last_inbound_at", "result", "model"}
  POST /api/email-setter/worker/flush        — retry auto-sends held for hours / reply delay

Using a draft from the Inbox goes through the normal POST /api/email/send
with ai_draft_id (routers/email_inbox.py), which records what was sent.
"""
import json

from fastapi import APIRouter, HTTPException

import email_setter_ai
import sms_setter_ai
from db import get_pool

router = APIRouter()


def _row_to_draft(row) -> dict:
    d = dict(row)
    if isinstance(d.get("details"), str):
        d["details"] = json.loads(d["details"])
    return d


@router.get("/email-setter/mode")
async def get_mode():
    pool = await get_pool()
    async with pool.acquire() as conn:
        return {"mode": await email_setter_ai.get_mode(conn), **(await sms_setter_ai.worker_status(conn))}


@router.post("/email-setter/mode")
async def set_mode(payload: dict):
    mode = payload.get("mode")
    if mode not in ("off", "draft", "auto"):
        raise HTTPException(400, "mode must be off, draft or auto")
    pool = await get_pool()
    async with pool.acquire() as conn:
        await email_setter_ai.set_mode(conn, mode)
        return {"mode": mode, **(await sms_setter_ai.worker_status(conn))}


@router.get("/email-setter/draft")
async def get_draft(contact_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, thread_id, action, reply, details, rationale, created_at
            FROM email_ai_drafts WHERE contact_id = $1 AND status = 'pending'
            ORDER BY created_at DESC LIMIT 1
            """,
            contact_id,
        )
        threads = await conn.fetch("SELECT thread_id FROM email_conversations WHERE contact_id = $1", contact_id)
        regen = set(await email_setter_ai.regen_list(conn))
    return {
        "draft": _row_to_draft(row) if row else None,
        "regenerating": any(t["thread_id"] in regen for t in threads),
    }


@router.post("/email-setter/draft/regenerate")
async def regenerate(payload: dict):
    thread_id = (payload.get("thread_id") or "").strip()
    pool = await get_pool()
    async with pool.acquire() as conn:
        if not thread_id and payload.get("contact_id"):
            thread_id = await conn.fetchval(
                """
                SELECT ec.thread_id FROM email_conversations ec
                WHERE ec.contact_id = $1
                ORDER BY (SELECT max(sent_at) FROM email_messages em WHERE em.thread_id = ec.thread_id) DESC NULLS LAST
                LIMIT 1
                """,
                payload["contact_id"],
            )
        if not thread_id:
            raise HTTPException(400, "no email thread for this contact")
        threads = await email_setter_ai.regen_list(conn)
        if thread_id not in threads:
            threads.append(thread_id)
        await sms_setter_ai._set_setting(conn, email_setter_ai.REGEN_KEY, json.dumps(threads))
        status = await sms_setter_ai.worker_status(conn)
    return {"ok": True, "thread_id": thread_id, **status}


@router.post("/email-setter/draft/{draft_id}/dismiss")
async def dismiss(draft_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE email_ai_drafts SET status = 'dismissed', decided_at = now() WHERE id = $1 AND status = 'pending'",
            draft_id,
        )
    return {"ok": True}


@router.post("/email-setter/draft/{draft_id}/book")
async def book(draft_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await email_setter_ai.book_draft(conn, draft_id)
    if result != "booked":
        raise HTTPException(422, result)
    return {"ok": True}


@router.get("/email-setter/worker/queue")
async def worker_queue():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await sms_setter_ai.record_heartbeat(conn)
        mode = await email_setter_ai.get_mode(conn)
        items = await email_setter_ai.build_queue(conn)
    return {
        "mode": mode,
        "system_prompt": email_setter_ai.system_prompt() if items else "",
        "schema": email_setter_ai.DRAFT_SCHEMA,
        "items": items,
    }


@router.post("/email-setter/worker/submit")
async def worker_submit(payload: dict):
    thread_id = (payload.get("thread_id") or "").strip()
    result = payload.get("result")
    if not thread_id or not isinstance(result, dict):
        raise HTTPException(400, "thread_id and result required")
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await email_setter_ai.submit_draft(
            conn, thread_id, payload.get("last_inbound_at"), result, payload.get("model"),
        )


@router.post("/email-setter/worker/flush")
async def worker_flush():
    pool = await get_pool()
    async with pool.acquire() as conn:
        return {"sent": await email_setter_ai.flush_pending(conn)}
