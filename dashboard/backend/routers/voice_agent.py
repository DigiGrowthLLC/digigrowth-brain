"""AI voice agent (client_voice_agent.py).

admin_router (mounted under /api with auth): the Agents tab's Voice Agent row.
router (public, no /api prefix):
  POST /webhooks/voice-agent/answer         Twilio: lead picked up -> bridge to Retell (row token checked)
  POST /webhooks/voice-agent/status         Twilio: final call status (no-answer/busy/... handled here)
  POST /webhooks/voice-agent/transfer-done  Twilio: after a transfer to the clinic
  POST /webhooks/retell                     Retell: call_ended / call_analyzed (signature checked)
  POST /webhooks/retell/function            Retell: live-call tool calls (signature checked)
"""
import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

import client_voice_agent as va
from db import get_pool

router = APIRouter()
admin_router = APIRouter()

_HANGUP = '<?xml version="1.0" encoding="UTF-8"?><Response><Hangup/></Response>'


def _xml(body: str) -> Response:
    return Response(content=body, media_type="application/xml")


@router.post("/webhooks/voice-agent/answer", include_in_schema=False)
async def answer(id: int, t: str):
    row = await va.get_row(id, t)
    if not row:
        return _xml(_HANGUP)
    return _xml(await va.answer_twiml(row))


@router.post("/webhooks/voice-agent/status", include_in_schema=False)
async def status_cb(id: int, t: str, request: Request):
    row = await va.get_row(id, t)
    if row:
        form = await request.form()
        await va.twilio_status(row, form.get("CallStatus") or "", form.get("CallDuration"))
    return Response(status_code=204)


@router.post("/webhooks/voice-agent/transfer-done", include_in_schema=False)
async def transfer_done(id: int, t: str, request: Request):
    row = await va.get_row(id, t)
    if not row:
        return _xml(_HANGUP)
    form = await request.form()
    return _xml(await va.transfer_done_twiml(row, form.get("DialCallStatus") or ""))


async def _verified_json(request: Request) -> dict:
    raw = await request.body()
    if not va.verify_retell_signature(raw, request.headers.get("x-retell-signature")):
        raise HTTPException(401, "bad signature")
    return json.loads(raw or b"{}")


@router.post("/webhooks/retell", include_in_schema=False)
async def retell_webhook(request: Request):
    payload = await _verified_json(request)
    if payload.get("event") == "transcript_updated":   # fires every turn; only feeds the screener nudge
        # The live transcript may sit beside "call" rather than inside it.
        call = {**(payload.get("call") or {}), **{k: v for k, v in payload.items() if "transcript" in k}}
        va.note_transcript(call)
        return Response(status_code=204)
    try:
        await va.retell_event(payload.get("event") or "", payload.get("call") or {})
    except Exception as e:
        print(f"[voice_agent] retell webhook failed: {e}", flush=True)
    return Response(status_code=204)


@router.post("/webhooks/retell/function", include_in_schema=False)
async def retell_function(request: Request):
    payload = await _verified_json(request)
    try:
        result = await va.run_function(payload.get("name") or "", payload.get("args") or {}, payload.get("call") or {})
    except Exception as e:
        print(f"[voice_agent] function {payload.get('name')} failed: {e}", flush=True)
        result = "Something went wrong on our side. Offer to have the clinic follow up by text instead."
    return JSONResponse({"result": result})


# ── Admin ────────────────────────────────────────────────────────────────────

class TestCallBody(BaseModel):
    phone: str
    name: str | None = None


@admin_router.get("/clients/{client_id}/voice-agent")
async def get_status(client_id: int):
    return await va.status(client_id)


@admin_router.post("/clients/{client_id}/voice-agent/sync")
async def sync(client_id: int):
    try:
        return await va.sync_agent(client_id)
    except Exception as e:
        raise HTTPException(400, str(e))


@admin_router.post("/clients/{client_id}/voice-agent/test-call")
async def test_call(client_id: int, body: TestCallBody):
    try:
        row_id = await va.queue_test_call(client_id, body.phone, body.name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "row_id": row_id}


@admin_router.post("/clients/{client_id}/voice-agent/consent-live")
async def consent_live(client_id: int, live: bool = True):
    """Stamp the moment the AI-call consent line went live on the client's
    Meta Instant Form. Only leads after this are called."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE client_marketing_config SET voice_consent_meta_since = $2 WHERE client_id = $1",
            client_id, datetime.now(timezone.utc) if live else None)
    return {"ok": True}


# Database reactivation voice agent: its own Retell agent, same endpoints shape.
@admin_router.get("/clients/{client_id}/reactivation-voice")
async def react_status(client_id: int):
    return await va.status(client_id, "react")


@admin_router.post("/clients/{client_id}/reactivation-voice/sync")
async def react_sync(client_id: int):
    try:
        return await va.sync_agent(client_id, "react")
    except Exception as e:
        raise HTTPException(400, str(e))


@admin_router.post("/clients/{client_id}/reactivation-voice/test-call")
async def react_test_call(client_id: int, body: TestCallBody):
    try:
        row_id = await va.queue_test_call(client_id, body.phone, body.name, "react")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "row_id": row_id}


@admin_router.get("/voice-agent/voices")
async def voices():
    try:
        return await va.list_voices()
    except Exception as e:
        raise HTTPException(400, str(e))
