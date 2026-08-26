"""
Dashboard router — homepage stats, agent messages, client messages, todos.

GET  /dashboard/summary?period=day|week|month|all — calling + SMS stats
GET  /dashboard/agent-messages                 — agent activity feed
POST /dashboard/agent-messages                 — post a message (called by agents)
POST /dashboard/agent-messages/{id}/read       — mark read
GET  /dashboard/client-messages                — SMS threads waiting for reply
GET  /dashboard/calendar                       — upcoming calendar events
GET  /dashboard/todos                          — all todos
POST /dashboard/todos                          — create todo
PATCH /dashboard/todos/{id}                    — update text or toggle done
DELETE /dashboard/todos/{id}                   — delete todo
"""

import asyncio
import json
import pathlib
import calendar as _calendar
from datetime import datetime, timedelta, timezone, date

from fastapi import APIRouter, HTTPException

from db import get_pool
from routers.analytics import _sms_metrics, _email_metrics, _app_booked_count

_SALES_STATS_PATH = pathlib.Path(__file__).parent.parent / "sales_stats.json"

router = APIRouter()

PERIOD_DELTA = {
    "day":   timedelta(days=1),
    "week":  timedelta(weeks=1),
    "month": timedelta(days=30),
    "all":   timedelta(days=36500),  # ~100 years — matches analytics.py's all-time lookback
}


def _period_start(period: str) -> datetime:
    delta = PERIOD_DELTA.get(period, timedelta(days=1))
    return datetime.now(timezone.utc) - delta


# ── Summary stats ─────────────────────────────────────────────────────────────

@router.get("/dashboard/summary")
async def summary(period: str = "day"):
    since = _period_start(period)
    pool  = await get_pool()

    try:
        stats = json.loads(_SALES_STATS_PATH.read_text())
    except Exception:
        stats = {}

    async with pool.acquire() as conn:
        sms_active = await conn.fetchval(
            "SELECT COUNT(*) FROM sms_conversations WHERE status = 'active'"
        )
        sms_booked = await conn.fetchval(
            "SELECT COUNT(*) FROM sms_conversations WHERE status = 'closed' AND updated_at >= $1", since,
        )
        sms_messages_period = await conn.fetchval(
            "SELECT COUNT(*) FROM sms_messages WHERE sent_at >= $1", since
        )
        total_contacts = await conn.fetchval("SELECT COUNT(*) FROM contacts")
        new_contacts   = await conn.fetchval(
            "SELECT COUNT(*) FROM contacts WHERE created_at >= $1", since
        )

        period_to_days = {"day": 1, "week": 7, "month": 30, "all": 0}
        p_days = period_to_days.get(period, 0)
        sms_funnel   = await _sms_metrics(conn, None if p_days == 0 else since)
        email_funnel = await _email_metrics(conn, None if p_days == 0 else since)
        app_booked   = await _app_booked_count(conn, stats, p_days)

    def _sheet(key):
        if p_days == 0:
            return stats.get(key, 0) or 0
        return stats.get(f"{key}_{p_days}d", 0) or 0

    calls_made     = _sheet("sheet_calls_made")
    calls_answered = _sheet("sheet_calls_answered")
    dms_reached    = _sheet("sheet_contacts_reached")
    booked         = _sheet("sheet_appointments_booked")
    reach_rate     = round(dms_reached / calls_made * 100, 1) if calls_made else 0

    # Channel-agnostic combined totals (calling + SMS + email), same
    # methodology as the Analytics tab's 6-Stage Acquisition Funnel: every
    # stage sums calling (sheets) + SMS (DB) + email (DB) where that stage
    # applies, except appointments, which uses the manually-logged
    # cross-channel total (discovery_calls) since some bookings come from
    # channels (e.g. DM campaigns) neither data source tracks, and a
    # bottom-up sum would under-count — plus app_booked (bookings made in
    # the app itself, not yet reflected in that sheet — see
    # analytics.py::_app_booked_count).
    # Reached = calls reached (dms_reached) + SMS DM Reached stage (the
    # "reached" equivalent for SMS, not the later Engaged stage) + email
    # opened (confirmed opens, not counting the tracking pixel's own
    # self-open — see analytics.py::_email_metrics).
    total_outreach     = calls_made + sms_funnel["contacted"]
    total_answered      = calls_answered + sms_funnel["replied"]
    total_reached       = dms_reached + sms_funnel["dm_reached"] + email_funnel["opened"]
    total_appointments  = _sheet("discovery_calls") + app_booked
    total_abr           = round(total_appointments / total_outreach * 100, 1) if total_outreach else 0

    return {
        "calling": {
            "calls_made":     calls_made,
            "calls_answered": calls_answered,
            "dms_reached":    dms_reached,
            "reach_rate":     reach_rate,
            "booked":         booked,
            "total_outreach":     total_outreach,
            "total_answered":     total_answered,
            "total_reached":      total_reached,
            "total_appointments": total_appointments,
            "total_abr":          total_abr,
        },
        "sms": {
            "active":   sms_active,
            "booked":   sms_booked,
            "messages": sms_messages_period,
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
    """
    Active SMS threads with an inbound message in the last 48 hours that
    hasn't been read yet — opening the thread in the SMS panel sets
    last_read_at, which drops it off this list, same as Agent Activity's
    read tracking.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT sc.phone,
                   c.business, c.owner, c.grade,
                   last_in.body AS last_message,
                   last_in.sent_at AS last_inbound_at
            FROM sms_conversations sc
            LEFT JOIN contacts c ON c.id = sc.contact_id
            LEFT JOIN LATERAL (
                SELECT body, sent_at FROM sms_messages
                WHERE phone = sc.phone AND direction = 'inbound'
                ORDER BY sent_at DESC LIMIT 1
            ) last_in ON true
            WHERE sc.status = 'active'
              AND last_in.sent_at >= now() - interval '48 hours'
              AND (sc.last_read_at IS NULL OR sc.last_read_at < last_in.sent_at)
            ORDER BY last_in.sent_at DESC
            """
        )
    return [dict(r) for r in rows]


# ── Calendar ─────────────────────────────────────────────────────────────────

@router.get("/dashboard/calendar")
async def get_calendar(days: int = 7):
    from integrations import calendar_events_structured
    try:
        events = await asyncio.to_thread(calendar_events_structured, days)
        return {"events": events}
    except RuntimeError as e:
        return {"events": [], "error": str(e)}
    except Exception as e:
        return {"events": [], "error": f"Calendar error: {e}"}


# ── Todos ─────────────────────────────────────────────────────────────────────

def _next_due(current: date, recurrence: str) -> date:
    if recurrence == "daily":
        return current + timedelta(days=1)
    if recurrence == "weekdays":
        d = current + timedelta(days=1)
        while d.weekday() >= 5:
            d += timedelta(days=1)
        return d
    if recurrence == "weekly":
        return current + timedelta(weeks=1)
    if recurrence == "monthly":
        month = current.month + 1 if current.month < 12 else 1
        year = current.year + (1 if current.month == 12 else 0)
        day = min(current.day, _calendar.monthrange(year, month)[1])
        return date(year, month, day)
    return current


@router.get("/dashboard/todos")
async def get_todos():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, text, done, due_date, recurrence, description, created_at
            FROM todos
            WHERE NOT done
            ORDER BY due_date ASC NULLS LAST, created_at DESC
            """
        )
    return [dict(r) for r in rows]


@router.post("/dashboard/todos")
async def create_todo(payload: dict):
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text required")

    due_date_raw = payload.get("due_date")
    recurrence = payload.get("recurrence") or None
    description = (payload.get("description") or "").strip() or None
    due_date = None
    if due_date_raw:
        try:
            due_date = date.fromisoformat(due_date_raw)
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid due_date")

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO todos (text, due_date, recurrence, description)
            VALUES ($1, $2, $3, $4)
            RETURNING id, text, done, due_date, recurrence, description, created_at
            """,
            text, due_date, recurrence, description,
        )
    return dict(row)


@router.patch("/dashboard/todos/{todo_id}")
async def update_todo(todo_id: int, payload: dict):
    pool = await get_pool()
    async with pool.acquire() as conn:
        if "done" in payload and payload["done"]:
            row = await conn.fetchrow(
                "SELECT due_date, recurrence FROM todos WHERE id = $1", todo_id
            )
            if row and row["recurrence"] and row["due_date"]:
                next_date = _next_due(row["due_date"], row["recurrence"])
                await conn.execute(
                    "UPDATE todos SET due_date = $1, done = false WHERE id = $2",
                    next_date, todo_id,
                )
            else:
                await conn.execute("DELETE FROM todos WHERE id = $1", todo_id)
        else:
            if "text" in payload:
                text = (payload["text"] or "").strip()
                if text:
                    await conn.execute(
                        "UPDATE todos SET text = $1 WHERE id = $2", text, todo_id
                    )
            if "due_date" in payload:
                due_date_raw = payload["due_date"]
                due_date = date.fromisoformat(due_date_raw) if due_date_raw else None
                await conn.execute(
                    "UPDATE todos SET due_date = $1 WHERE id = $2", due_date, todo_id
                )
            if "description" in payload:
                description = (payload["description"] or "").strip() or None
                await conn.execute(
                    "UPDATE todos SET description = $1 WHERE id = $2", description, todo_id
                )
    return {"ok": True}


@router.delete("/dashboard/todos/{todo_id}")
async def delete_todo(todo_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM todos WHERE id = $1", todo_id)
    return {"ok": True}
