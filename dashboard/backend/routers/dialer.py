"""
Dialer router — receives events from the local parallel-dialer and serves
live + historical stats to the DialerPanel.

The local dialer (parallel-dialer/webhook.py) POSTs here instead of GHL.
The dashboard polls GET /api/dialer/stats for live + historical data.
"""

import asyncio
import json
import pathlib

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from db import get_pool
from models import DISPOSITION_TO_STATUS

router = APIRouter()

_DIALER_DIR = (pathlib.Path(__file__).parent.parent.parent.parent / "parallel-dialer").resolve()


# ── Terminal exec ─────────────────────────────────────────────────────────────

@router.post("/dialer/exec")
async def exec_dialer_command(body: dict):
    """Run a shell command in parallel-dialer/. Streams stdout+stderr as SSE."""
    command = (body.get("command") or "").strip()
    if not command:
        raise HTTPException(status_code=400, detail="command required")

    async def _stream():
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=str(_DIALER_DIR),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            async for line in proc.stdout:
                yield f"data: {json.dumps({'type': 'output', 'text': line.decode(errors='replace')})}\n\n"
            await proc.wait()
            yield f"data: {json.dumps({'type': 'done', 'code': proc.returncode})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
            updated = await conn.fetchrow(
                """
                UPDATE contacts SET
                    call_attempts    = call_attempts + 1,
                    last_disposition = $1,
                    last_called_at   = now(),
                    status           = COALESCE($2, status),
                    updated_at       = now()
                WHERE id = $3
                RETURNING call_attempts, phone, owner
                """,
                disposition, new_status, contact_id,
            )

            if updated and disposition == "No Answer" and updated["call_attempts"] >= 3:
                await conn.execute(
                    "UPDATE contacts SET status='sms-handoff' WHERE id=$1",
                    contact_id,
                )
                from routers.sms import _send_twilio
                owner = updated["owner"] or "there"
                msg = (
                    f"Hey {owner}, this is Dylan from DigiGrowth — "
                    "I tried reaching you a few times. Wanted to connect about growing "
                    "your business online. Reply back if you'd like to chat!"
                )
                try:
                    _send_twilio(updated["phone"], msg)
                except Exception:
                    pass

    return {"ok": True}


@router.get("/dialer/leads")
async def dialer_leads(limit: int = 500):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, phone, business, owner, grade, opener, email, call_attempts
            FROM contacts
            WHERE phone IS NOT NULL
              AND status NOT IN ('appointment-booked', 'not-interested', 'sms-handoff', 'dnc')
              AND (last_called_at IS NULL
                   OR last_called_at < now() - interval '4 hours')
            ORDER BY
              CASE grade WHEN 'A' THEN 1 WHEN 'B' THEN 2
                         WHEN 'C' THEN 3 WHEN 'D' THEN 4 ELSE 5 END,
              call_attempts ASC
            LIMIT $1
            """,
            limit,
        )
    return {
        "leads": [
            {
                "contact_id": str(r["id"]),
                "phone":      r["phone"],
                "business":   r["business"] or "",
                "owner":      r["owner"] or "",
                "grade":      r["grade"] or "",
                "opener":     r["opener"] or "",
                "email":      r["email"] or "",
                "attempts":   r["call_attempts"],
            }
            for r in rows
        ]
    }


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
