"""Admin API for a client's social media conversation agent
(client_dm_agent.py) — backs the Clients panel's Agents tab → Social Media
Conversation Agent."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import client_dm_agent
from db import get_pool

router = APIRouter()


class TestChatBody(BaseModel):
    platform: str = "instagram"
    messages: list[dict] = []
    phone: str | None = None


@router.post("/clients/{client_id}/dm-agent/connect")
async def connect_dm_agent(client_id: int):
    """Subscribe the client's Page to DMs and find its linked Instagram
    account. Safe to re-run."""
    return await client_dm_agent.connect(client_id)


@router.get("/clients/{client_id}/dm-agent/threads")
async def list_threads(client_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT t.*,
                   (SELECT body FROM client_dm_messages m WHERE m.thread_id = t.id ORDER BY created_at DESC, id DESC LIMIT 1) AS last_body,
                   (SELECT count(*) FROM client_dm_messages m WHERE m.thread_id = t.id) AS message_count
            FROM client_dm_threads t WHERE t.client_id = $1
            ORDER BY greatest(t.last_inbound_at, t.last_outbound_at) DESC NULLS LAST
            LIMIT 100
            """,
            client_id,
        )
    return [dict(r) for r in rows]


@router.get("/clients/{client_id}/dm-agent/threads/{thread_id}/messages")
async def thread_messages(client_id: int, thread_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        if not await conn.fetchval("SELECT 1 FROM client_dm_threads WHERE id = $1 AND client_id = $2", thread_id, client_id):
            raise HTTPException(status_code=404, detail="Thread not found")
        rows = await conn.fetch(
            "SELECT id, direction, sender, body, created_at FROM client_dm_messages WHERE thread_id = $1 ORDER BY created_at, id",
            thread_id,
        )
    return [dict(r) for r in rows]


@router.post("/clients/{client_id}/dm-agent/threads/{thread_id}/hand-back")
async def hand_back(client_id: int, thread_id: int):
    """Give an escalated / human-handled thread back to the agent."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE client_dm_threads SET status = 'ai_active', status_reason = NULL, human_last_at = NULL "
            "WHERE id = $1 AND client_id = $2 RETURNING id",
            thread_id, client_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Thread not found")
    return {"ok": True}


@router.post("/clients/{client_id}/dm-agent/test")
async def test_chat(client_id: int, body: TestChatBody):
    """Talk to the agent as a DM lead would, without Meta: it reads the real
    calendar but saves, books and escalates nothing."""
    if body.platform not in client_dm_agent.PLATFORM_LABEL:
        raise HTTPException(status_code=400, detail="platform must be instagram or facebook")
    messages = [
        {"role": "user" if m.get("role") == "user" else "assistant", "content": str(m.get("content") or "")}
        for m in body.messages if (m.get("content") or "").strip()
    ]
    if not messages or messages[-1]["role"] != "user":
        raise HTTPException(status_code=400, detail="End with a message from the lead")
    pool = await get_pool()
    async with pool.acquire() as conn:
        clinic_phone = await conn.fetchval("SELECT twilio_number FROM client_marketing_config WHERE client_id = $1", client_id)
    thread = {"id": 0, "platform": body.platform, "sender_name": None, "phone": body.phone, "contact_id": None}
    reply = await client_dm_agent.run_agent(client_id, thread, messages, clinic_phone, dry_run=True)
    return {"reply": reply or "", "phone": thread.get("phone")}
