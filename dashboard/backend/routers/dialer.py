"""
Dialer router — auth-protected endpoints for the DialerPanel UI.

  GET  /api/dialer/token         — Twilio access token for Twilio.Device
  GET  /api/dialer/session       — live session state (polled every 1s by frontend)
  POST /api/dialer/session/init  — start session, load leads into engine
  POST /api/dialer/dial-batch    — dial next batch of leads
  POST /api/dialer/classify      — log disposition after a call
  POST /api/dialer/end-call      — hang up the active bridged call
  POST /api/dialer/gatekeeper/connect  — redirect held gatekeeper into conference
  POST /api/dialer/gatekeeper/decline  — hang up held gatekeeper
  POST /api/dialer/set-lines     — update max parallel lines
  POST /api/dialer/end-session   — request session end
"""

import asyncio
import json
import os
import pathlib
import time as _time
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

import dialer_engine as engine
from db import get_pool
from models import DISPOSITION_TO_STATUS

router = APIRouter()

_DIALER_DIR = (pathlib.Path(__file__).parent.parent.parent.parent / "parallel-dialer").resolve()
_CONFIG_FILE = _DIALER_DIR / "config.json"


def _load_dialer_config() -> dict:
    try:
        with open(_CONFIG_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


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


# ── Twilio access token (browser Twilio.Device) ───────────────────────────────

@router.get("/dialer/token")
async def get_token():
    from twilio.jwt.access_token import AccessToken
    from twilio.jwt.access_token.grants import VoiceGrant

    account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    api_key     = os.environ.get("TWILIO_API_KEY_SID", "")
    api_secret  = os.environ.get("TWILIO_API_KEY_SECRET", "")
    app_sid     = os.environ.get("TWILIO_TWIML_APP_SID", "")

    if not all([account_sid, api_key, api_secret, app_sid]):
        raise HTTPException(
            status_code=500,
            detail="Missing Twilio env vars: TWILIO_API_KEY_SID, TWILIO_API_KEY_SECRET, TWILIO_TWIML_APP_SID",
        )

    token = AccessToken(account_sid, api_key, api_secret, identity="agent", ttl=3600)
    grant = VoiceGrant(outgoing_application_sid=app_sid, incoming_allow=True)
    token.add_grant(grant)
    return {"token": token.to_jwt()}


# ── Native OS session management ──────────────────────────────────────────────

@router.get("/dialer/session")
async def get_session():
    """Polled every 1s by DialerPanel to drive the calling UI state machine."""
    with engine._session["lock"]:
        active       = engine._session.get("active")
        bridged      = engine._session.get("bridged")
        show_cls     = engine._session.get("show_classification", False)
        connected_at = engine._session.get("connected_at")
        session_id   = engine._session.get("id")
        stats        = dict(engine._session.get("stats", {}))
        total        = engine._session.get("total_leads", 0)
        pending      = engine._session.get("pending")
        gk           = engine._session.get("gatekeeper_pending")
        end_req      = engine._session.get("end_requested", False)
        remaining    = max(0, len(engine._session.get("eligible_leads", [])))

    calls_made  = stats.get("calls_made", 0)
    dms_reached = stats.get("dms_reached", 0)

    if bridged:
        status = "connected"
    elif show_cls:
        status = "classify"
    elif active:
        status = "waiting"
    else:
        status = "idle"

    return {
        "active":        active,
        "session_id":    session_id,
        "status":        status,
        "current_lead":  pending,
        "connected_at":  connected_at,
        "gatekeeper":    gk["lead"] if gk else None,
        "end_requested": end_req,
        "stats": {
            "calls_made":  calls_made,
            "dms_reached": dms_reached,
            "remaining":   remaining,
            "total":       total,
        },
    }


@router.post("/dialer/session/init")
async def session_init():
    """Load eligible leads from DB and initialise the engine session."""
    config = _load_dialer_config()
    session_id = str(uuid.uuid4())[:8]

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, phone, business, owner, grade, opener, email,
                   website, city, state, call_attempts
            FROM contacts
            WHERE phone IS NOT NULL
              AND status = 'dialer-lead'
              AND (last_called_at IS NULL OR last_called_at < now() - interval '4 hours')
            ORDER BY
              CASE grade WHEN 'A' THEN 1 WHEN 'B' THEN 2
                         WHEN 'C' THEN 3 WHEN 'D' THEN 4 ELSE 5 END,
              call_attempts ASC
            LIMIT 500
            """,
        )

    leads = [
        {
            "contact_id": str(r["id"]),
            "phone":      r["phone"],
            "business":   r["business"] or "",
            "owner":      r["owner"] or "",
            "grade":      r["grade"] or "",
            "opener":     r["opener"] or "",
            "email":      r["email"] or "",
            "website":    r["website"] or "",
            "city":       r["city"] or "",
            "state":      r["state"] or "",
            "attempts":   r["call_attempts"],
        }
        for r in rows
    ]

    engine.init_session(session_id, config, leads)
    return {"ok": True, "session_id": session_id, "lead_count": len(leads)}


@router.post("/dialer/dial-batch")
async def dial_batch():
    """Dial the next batch of leads. Called by the frontend after each classification."""
    with engine._session["lock"]:
        if not engine._session.get("active"):
            raise HTTPException(status_code=400, detail="No active session")
        if engine._session.get("end_requested"):
            return {"ok": True, "dialed": 0, "done": True}

        # Prepend any retry phones to the queue
        retry_phones  = engine.get_and_clear_retry()
        retry_leads   = [
            engine._session["leads_by_phone"][p]
            for p in retry_phones
            if p in engine._session["leads_by_phone"]
        ]
        if retry_leads:
            engine._session["eligible_leads"] = retry_leads + engine._session["eligible_leads"]

        max_lines = engine._session.get("max_lines", 10)
        batch     = engine._session["eligible_leads"][:max_lines]
        engine._session["eligible_leads"] = engine._session["eligible_leads"][max_lines:]

        if not batch:
            return {"ok": True, "dialed": 0, "done": True}

        # Record ring start + dial count before dialing
        now = _time.time()
        engine._session["batch_had_answer"] = False
        for lead in batch:
            norm = engine._norm(lead["phone"])
            engine._session["ring_start"][norm]  = now
            engine._session["dial_count"][norm]  = engine._session["dial_count"].get(norm, 0) + 1

        session_id = engine._session["id"]
        config     = engine._session["config"]

    base = engine.base_url()
    if not base:
        return {
            "ok": False, "dialed": 0, "done": False, "errors":
            ["RAILWAY_PUBLIC_DOMAIN not set — Twilio callback URLs cannot be built. Set this env var on Railway."],
            "phones": [],
        }

    phones = [l["phone"] for l in batch]
    sids, errors = await engine.dial_batch(phones, session_id, base, config)

    with engine._session["lock"]:
        engine._session["call_sids"].update(sids)

    return {
        "ok":       True,
        "dialed":   len(sids),
        "done":     False,
        "errors":   errors,
        "phones":   list(sids.keys()),
        "base_url": base,
    }


@router.post("/dialer/classify")
async def classify(body: dict):
    """Log disposition for the current pending lead and clear classification state."""
    disposition = (body.get("disposition") or "No Answer").strip()
    notes       = (body.get("notes") or "").strip() or None

    with engine._session["lock"]:
        pending                              = engine._session.get("pending")
        engine._session["show_classification"] = False
        engine._session["pending"]           = None
        engine._session["connected_at"]      = None

    if pending:
        phone = pending.get("phone", "")

        # Write to DB directly (same logic as log_disposition)
        pool = await get_pool()
        async with pool.acquire() as conn:
            contact = await conn.fetchrow("SELECT id FROM contacts WHERE phone = $1", phone)
            contact_id = contact["id"] if contact else None

            await conn.execute(
                "INSERT INTO call_logs (contact_id, disposition, notes) VALUES ($1, $2, $3)",
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
                        "UPDATE contacts SET status='sms-handoff' WHERE id=$1", contact_id,
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

        # Update in-session stats
        with engine._session["lock"]:
            engine._session["stats"]["calls_made"] += 1
            if disposition in ("Appointment Booked", "Follow Up", "Send Info"):
                engine._session["stats"]["dms_reached"] += 1

    return {"ok": True}


@router.post("/dialer/end-call")
async def end_call():
    with engine._session["lock"]:
        bridged_sid                              = engine._session.get("bridged_sid")
        engine._session["bridged"]               = False
        engine._session["show_classification"]   = True
    if bridged_sid:
        engine.hangup_call(bridged_sid)
    return {"ok": True}


@router.post("/dialer/gatekeeper/connect")
async def gatekeeper_connect():
    from datetime import datetime, timezone
    with engine._session["lock"]:
        gk = engine._session.get("gatekeeper_pending")
        if not gk or engine._session.get("bridged"):
            return {"ok": False}

        engine._session["bridged"]             = True
        engine._session["bridged_sid"]         = gk["sid"]
        engine._session["bridged_phone"]       = engine._norm(gk["phone"])
        engine._session["show_classification"] = False
        engine._session["connected_at"]        = datetime.now(timezone.utc).isoformat()
        engine._session["batch_had_answer"]    = True
        engine._session["pending"]             = {**gk["lead"], "gatekeeper": True}
        engine._session["gatekeeper_pending"]  = None
        session_id = engine._session["id"]

    base = engine.base_url()
    engine.redirect_call(gk["sid"], f"{base}/dialer/voice/gatekeeper-join?session_id={session_id}")
    return {"ok": True}


@router.post("/dialer/gatekeeper/decline")
async def gatekeeper_decline():
    with engine._session["lock"]:
        gk = engine._session.get("gatekeeper_pending")
        engine._session["gatekeeper_pending"] = None
    if gk and gk.get("sid"):
        engine.hangup_call(gk["sid"])
    return {"ok": True}


@router.post("/dialer/set-lines")
async def set_lines(body: dict):
    lines = max(1, int(body.get("lines", 10)))
    with engine._session["lock"]:
        engine._session["max_lines"] = lines
    return {"ok": True, "max_lines": lines}


@router.post("/dialer/end-session")
async def end_session():
    with engine._session["lock"]:
        engine._session["end_requested"] = True
    engine.close_session()
    return {"ok": True}


@router.get("/dialer/debug")
async def debug_config():
    """Returns resolved config so you can verify Railway env vars without checking logs."""
    config = _load_dialer_config()
    base = engine.base_url()
    twilio_phone = os.environ.get("TWILIO_PHONE_NUMBER") or config.get("twilio_phone_number", "")
    account_sid  = os.environ.get("TWILIO_ACCOUNT_SID", "")
    twiml_app    = os.environ.get("TWILIO_TWIML_APP_SID", "")
    with engine._session["lock"]:
        sess_active = engine._session.get("active", False)
        sess_leads  = len(engine._session.get("eligible_leads", []))
    return {
        "base_url":        base or "(EMPTY — RAILWAY_PUBLIC_DOMAIN and WEBHOOK_BASE_URL both unset)",
        "twilio_phone":    twilio_phone or "(EMPTY — TWILIO_PHONE_NUMBER not set and not in config.json)",
        "account_sid_set": bool(account_sid),
        "twiml_app_set":   bool(twiml_app),
        "lead_answered_url": f"{base}/dialer/voice/lead-answered" if base else "(base_url empty)",
        "agent_join_url":    f"{base}/dialer/voice/agent-join" if base else "(base_url empty)",
        "session_active":  sess_active,
        "eligible_leads":  sess_leads,
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
        leads_ready = await conn.fetchval(
            """
            SELECT COUNT(*) FROM contacts
            WHERE phone IS NOT NULL
              AND status = 'dialer-lead'
              AND (last_called_at IS NULL OR last_called_at < now() - interval '4 hours')
            """
        )

    with engine._session["lock"]:
        active      = engine._session.get("active", False)
        session_id  = engine._session.get("id")
        eng_stats   = dict(engine._session.get("stats", {}))
        total_leads = engine._session.get("total_leads", 0)
        remaining   = len(engine._session.get("eligible_leads", []))

    calls_made  = eng_stats.get("calls_made", 0)
    dms_reached = eng_stats.get("dms_reached", 0)

    reach_rate = round(dms_reached / calls_made * 100, 1) if calls_made > 0 else 0

    return {
        "session": {
            "active":       active,
            "session_id":   session_id,
            "calls_made":   calls_made,
            "dms_reached":  dms_reached,
            "total_leads":  total_leads,
            "remaining":    remaining,
            "reach_rate":   reach_rate,
            "leads_ready":  leads_ready,
        },
        "history": {
            "total_calls":     total_calls,
            "total_booked":    booked,
            "total_reached":   reached,
            "by_disposition":  [dict(r) for r in by_disposition],
            "recent":          [dict(r) for r in recent],
        },
    }
