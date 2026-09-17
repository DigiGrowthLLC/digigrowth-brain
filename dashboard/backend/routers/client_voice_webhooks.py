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
"""

from fastapi import APIRouter, Request
from fastapi.responses import Response

import client_dialer

router = APIRouter()


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
