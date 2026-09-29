"""
Public Twilio voice webhooks for the client portal's single-lead "Call Now"
feature (client_dialer.py) — one router per call event, `client_id` and
`call_id` both carried in the URL/query string (same "no signature
verification, client_id in the path is the scoping mechanism" convention as
client_sms_webhooks.py and the internal dialer_webhooks.py; Twilio doesn't
sign these requests by default and this codebase doesn't verify them
anywhere else either).

Mounted at root (no /api prefix) so URLs match what Twilio expects:
  POST /webhooks/client-voice/{client_id}/agent-join
  POST /webhooks/client-voice/{client_id}/lead-answered
  POST /webhooks/client-voice/{client_id}/status
  POST /webhooks/client-voice/{client_id}/incoming       — a lead calling the client's number
  POST /webhooks/client-voice/{client_id}/incoming-done  — after that forward ends
"""

from fastapi import APIRouter, Request
from fastapi.responses import Response
from twilio.twiml.voice_response import VoiceResponse

import client_dialer
from db import get_pool

router = APIRouter()


def _e164(raw: str | None) -> str | None:
    digits = "".join(c for c in (raw or "") if c.isdigit())
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    return None


@router.post("/webhooks/client-voice/{client_id}/incoming")
async def incoming_call(client_id: int, request: Request):
    """The client's Twilio number is the one the AI agent texts leads from,
    so leads call it back. Forward to call_forward_number (falling back to
    the client's own phone), showing the lead's number as caller ID so the
    client knows who's calling."""
    form = await request.form()
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT cmc.call_forward_number, c.phone FROM clients c "
            "LEFT JOIN client_marketing_config cmc ON cmc.client_id = c.id WHERE c.id = $1",
            client_id,
        )
    target = _e164(row["call_forward_number"] or row["phone"]) if row else None
    vr = VoiceResponse()
    if target:
        dial = vr.dial(
            caller_id=form.get("From") or None, timeout=25, answer_on_bridge=True,
            action=f"/webhooks/client-voice/{client_id}/incoming-done", method="POST",
        )
        dial.number(target)
    else:
        print(f"[client_voice] client {client_id} has no forwarding number — incoming call dropped")
        vr.say("Sorry, we can't take your call right now. Please send us a text and we'll get right back to you.")
    return Response(str(vr), media_type="text/xml")


@router.post("/webhooks/client-voice/{client_id}/incoming-done")
async def incoming_call_done(client_id: int, request: Request):
    form = await request.form()
    vr = VoiceResponse()
    if form.get("DialCallStatus") != "completed":
        vr.say("Sorry we missed your call. Please send us a text, or try again shortly, and we'll get right back to you.")
    return Response(str(vr), media_type="text/xml")


@router.post("/webhooks/client-voice/{client_id}/agent-join")
async def agent_join(client_id: int, request: Request):
    form = await request.form()
    call_id = request.query_params.get("call_id", "")
    agent_call_sid = form.get("CallSid", "")
    twiml = await client_dialer.agent_join(client_id, call_id, agent_call_sid)
    return Response(twiml, media_type="text/xml")


@router.post("/webhooks/client-voice/{client_id}/lead-answered")
async def lead_answered(client_id: int, request: Request):
    call_id = request.query_params.get("call_id", "")
    twiml = client_dialer.lead_answered(call_id)
    return Response(twiml, media_type="text/xml")


@router.post("/webhooks/client-voice/{client_id}/status")
async def status(client_id: int, request: Request):
    form = await request.form()
    call_id = request.query_params.get("call_id", "")
    call_status = form.get("CallStatus", "")
    client_dialer.call_status(call_id, call_status)
    return Response("", status_code=204)
