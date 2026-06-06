"""
Dialer router — receives events from the local parallel-dialer and serves
live + historical stats to the DialerPanel.

The local dialer (parallel-dialer/webhook.py) POSTs here instead of GHL.
The dashboard polls GET /api/dialer/stats for live + historical data.
"""

from fastapi import APIRouter

from db import get_pool
from models import DISPOSITION_TO_STATUS

router = APIRouter()

# ── In-memory live session state (reset on session start) ─────────────────────

_live = {
    "active":      False,
    "session_id":  None,
    "started_at":  None,
    "calls_made":  0,
    "dms_reached": 0,
    "total_leads": 0,
}


# ── Session lifecycle ─────────────────────────────────────────────────────────

@router.post("/dialer/session/start")
async def session_start(payload: dict):
    _live["active"]      = True
    _live["session_id"]  = payload.get("session_id")
    _live["started_at"]  = payload.get("started_at")
    _live["calls_made"]  = 0
    _live["dms_reached"] = 0
    _live["total_leads"] = payload.get("total_leads", 0)
    return {"ok": True}


@router.post("/dialer/session/end")
async def session_end(payload: dict):
    _live["active"] = False
    return {"ok": True}


@router.post("/dialer/heartbeat")
async def heartbeat(payload: dict):
    if payload.get("total_leads") is not None:
        _live["total_leads"] = payload["total_leads"]
    if payload.get("calls_made") is not None:
        _live["calls_made"] = payload["calls_made"]
    if payload.get("dms_reached") is not None:
        _live["dms_reached"] = payload["dms_reached"]
    return {"ok": True}


# ── Disposition event (replaces GHL handle_disposition) ──────────────────────

@router.post("/dialer/disposition")
async def log_disposition(payload: dict):
    phone       = (payload.get("phone") or "").strip()
    disposition = (payload.get("disposition") or "No Answer").strip()
    notes       = (payload.get("notes") or "").strip() or None

    pool = await get_pool()
    async with pool.acquire() as conn:
        contact = await conn.fetchrow(
            "SELECT id FROM contacts WHERE phone = $1", phone
        )
        contact_id = contact["id"] if contact else None

        await conn.execute(
            """
            INSERT INTO call_logs (contact_id, disposition, notes)
            VALUES ($1, $2, $3)
            """,
            contact_id, disposition, notes,
        )

        if contact_id:
            new_status = DISPOSITION_TO_STATUS.get(disposition)
            await conn.execute(
                """
                UPDATE contacts SET
                    call_attempts    = call_attempts + 1,
                    last_disposition = $1,
                    last_called_at   = now(),
                    status           = COALESCE($2, status),
                    updated_at       = now()
                WHERE id = $3
                """,
                disposition, new_status, contact_id,
            )

    return {"ok": True}


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/dialer/stats")
async def get_stats():
    pool = await get_pool()
    async with pool.acquire() as conn:
        total_calls = await conn.fetchval("SELECT COUNT(*) FROM call_logs")

        by_disposition = await conn.fetch(
            """
            SELECT disposition, COUNT(*) AS cnt
            FROM call_logs
            WHERE disposition IS NOT NULL
            GROUP BY disposition
            ORDER BY cnt DESC
            """
        )

        recent = await conn.fetch(
            """
            SELECT cl.disposition, cl.notes, cl.started_at,
                   c.business, c.owner, c.phone, c.grade
            FROM call_logs cl
            LEFT JOIN contacts c ON c.id = cl.contact_id
            ORDER BY cl.started_at DESC NULLS LAST
            LIMIT 20
            """
        )

        booked = await conn.fetchval(
            "SELECT COUNT(*) FROM contacts WHERE status = 'appointment-booked'"
        )
        reached = await conn.fetchval(
            "SELECT COUNT(*) FROM contacts WHERE last_disposition IN "
            "('Appointment Booked', 'Follow Up', 'Send Info')"
        )

    reach_rate = round(_live["dms_reached"] / _live["calls_made"] * 100, 1) \
        if _live["calls_made"] > 0 else 0

    return {
        "session": {
            "active":      _live["active"],
            "session_id":  _live["session_id"],
            "calls_made":  _live["calls_made"],
            "dms_reached": _live["dms_reached"],
            "total_leads": _live["total_leads"],
            "remaining":   max(0, _live["total_leads"] - _live["calls_made"]),
            "reach_rate":  reach_rate,
        },
        "history": {
            "total_calls":     total_calls,
            "total_booked":    booked,
            "total_reached":   reached,
            "by_disposition":  [dict(r) for r in by_disposition],
            "recent":          [dict(r) for r in recent],
        },
    }
