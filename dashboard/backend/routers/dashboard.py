"""
Dashboard router — homepage stats, agent messages, client messages, todos.

GET  /dashboard/summary?period=day|week|month  — calling + SMS stats
GET  /dashboard/agent-messages                 — agent activity feed
POST /dashboard/agent-messages                 — post a message (called by agents)
POST /dashboard/agent-messages/{id}/read       — mark read
GET  /dashboard/client-messages                — SMS threads waiting for reply
GET  /dashboard/todos                          — all todos
POST /dashboard/todos                          — create todo
PATCH /dashboard/todos/{id}                    — update text or toggle done
DELETE /dashboard/todos/{id}                   — delete todo
"""

from datetime import datetime, timedelta, timezone, date

from fastapi import APIRouter, HTTPException

from db import get_pool

router = APIRouter()

PERIOD_DELTA = {
    "day":   timedelta(days=1),
    "week":  timedelta(weeks=1),
    "month": timedelta(days=30),
}


def _period_start(period: str) -> datetime:
    delta = PERIOD_DELTA.get(period, timedelta(days=1))
    return datetime.now(timezone.utc) - delta


# ── Summary stats ─────────────────────────────────────────────────────────────

@router.get("/dashboard/summary")
async def summary(period: str = "day"):
    since = _period_start(period)
    pool  = await get_pool()

    async with pool.acquire() as conn:
        calls_made = await conn.fetchval(
            "SELECT COUNT(*) FROM call_logs WHERE started_at >= $1", since
        )
        dms_reached = await conn.fetchval(
            """
            SELECT COUNT(*) FROM call_logs
            WHERE started_at >= $1
            AND disposition IN ('Appointment Booked', 'Follow Up', 'Send Info')
            """,
            since,
        )
        calls_booked = await conn.fetchval(
            """
            SELECT COUNT(*) FROM call_logs
            WHERE started_at >= $1 AND disposition = 'Appointment Booked'
            """,
            since,
        )

        sms_active = await conn.fetchval(
            "SELECT COUNT(*) FROM sms_conversations WHERE status = 'active'"
        )
        sms_booked = await conn.fetchval(
            """
            SELECT COUNT(*) FROM sms_conversations
            WHERE status = 'closed' AND updated_at >= $1
            """,
            since,
        )
        sms_messages_period = await conn.fetchval(
            "SELECT COUNT(*) FROM sms_messages WHERE sent_at >= $1", since
        )

        total_contacts = await conn.fetchval("SELECT COUNT(*) FROM contacts")
        new_contacts   = await conn.fetchval(
            "SELECT COUNT(*) FROM contacts WHERE created_at >= $1", since
        )

    reach_rate = round(dms_reached / calls_made * 100, 1) if calls_made else 0

    return {
        "calling": {
            "calls_made":  calls_made,
            "dms_reached": dms_reached,
            "reach_rate":  reach_rate,
            "booked":      calls_booked,
        },
        "sms": {
            "active":       sms_active,
            "booked":       sms_booked,
            "messages":     sms_messages_period,
        },
        "contacts": {
            "total": total_contacts,
            "new":   new_contacts,
        },
    }


# ── Agent messages ────────────────────────────────────────────────────────────

@router.get("/dashboard/agent-messages")
async def get_agent_messages():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, agent, message, read, created_at
            FROM agent_messages
            ORDER BY created_at DESC
            LIMIT 50
            """
        )
    return [dict(r) for r in rows]


@router.post("/dashboard/agent-messages")
async def post_agent_message(payload: dict):
    agent   = (payload.get("agent") or "system").strip()
    message = (payload.get("message") or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="message required")

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO agent_messages (agent, message) VALUES ($1, $2) RETURNING id",
            agent, message,
        )
    return {"id": row["id"]}


@router.post("/dashboard/agent-messages/{msg_id}/read")
async def mark_read(msg_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE agent_messages SET read = true WHERE id = $1", msg_id
        )
    return {"ok": True}


# ── Client messages needing reply ─────────────────────────────────────────────

@router.get("/dashboard/client-messages")
async def client_messages():
    """Active SMS threads where the last message was inbound (client is waiting)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT sc.phone, sc.updated_at,
                   c.business, c.owner, c.grade,
                   (
                     SELECT body FROM sms_messages
                     WHERE phone = sc.phone
                     ORDER BY sent_at DESC LIMIT 1
                   ) AS last_message,
                   (
                     SELECT direction FROM sms_messages
                     WHERE phone = sc.phone
                     ORDER BY sent_at DESC LIMIT 1
                   ) AS last_direction
            FROM sms_conversations sc
            LEFT JOIN contacts c ON c.id = sc.contact_id
            WHERE sc.status = 'active'
            ORDER BY sc.updated_at DESC
            """
        )
    return [
        dict(r) for r in rows
        if r["last_direction"] == "inbound"
    ]


# ── Chart data ───────────────────────────────────────────────────────────────

@router.get("/dashboard/chart/calls")
async def chart_calls(days: int = 30):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    pool  = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DATE(started_at) AS day,
                   COUNT(*) AS calls,
                   COUNT(*) FILTER (
                       WHERE disposition IN ('Appointment Booked','Follow Up','Send Info')
                   ) AS reached
            FROM call_logs
            WHERE started_at >= $1
            GROUP BY DATE(started_at)
            ORDER BY day
            """,
            since,
        )
    return [
        {"date": str(r["day"]), "calls": r["calls"], "reached": r["reached"]}
        for r in rows
    ]


# ── Todos ─────────────────────────────────────────────────────────────────────

@router.get("/dashboard/todos")
async def get_todos():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, text, done, created_at FROM todos ORDER BY done, created_at DESC"
        )
    return [dict(r) for r in rows]


@router.post("/dashboard/todos")
async def create_todo(payload: dict):
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text required")

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO todos (text) VALUES ($1) RETURNING id, text, done, created_at",
            text,
        )
    return dict(row)


@router.patch("/dashboard/todos/{todo_id}")
async def update_todo(todo_id: int, payload: dict):
    pool = await get_pool()
    async with pool.acquire() as conn:
        if "done" in payload:
            await conn.execute(
                "UPDATE todos SET done = $1 WHERE id = $2",
                bool(payload["done"]), todo_id,
            )
        if "text" in payload:
            text = (payload["text"] or "").strip()
            if text:
                await conn.execute(
                    "UPDATE todos SET text = $1 WHERE id = $2",
                    text, todo_id,
                )
    return {"ok": True}


@router.delete("/dashboard/todos/{todo_id}")
async def delete_todo(todo_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM todos WHERE id = $1", todo_id)
    return {"ok": True}
