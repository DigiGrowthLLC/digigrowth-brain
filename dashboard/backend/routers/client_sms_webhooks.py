"""
Public Twilio webhook for inbound SMS to a REAL client's OWN provisioned
number (see client_sms.py). The client_id is encoded directly in the
webhook URL Twilio calls (set as sms_url when the number was purchased),
so each inbound message is unambiguously scoped to one client and stored
in client_sms_messages — never sms_messages, which is DigiGrowth's own.

Every inbound message then goes to exactly one of two places, gated by
client_marketing_config.response_ai_enabled: the self-built AI agent
(response_ai.py) or the legacy Appointwise-forwarding stub
(routers/appointwise_webhooks.py) — never both, so migrating a client off
Appointwise is a single flag flip, reversible per client.
"""
from fastapi import APIRouter, Request, Response

import response_ai
from db import get_pool
from routers.appointwise_webhooks import forward_inbound_to_appointwise

router = APIRouter()  # public — no auth, mounted with no prefix in main.py


@router.post("/webhooks/client-sms/{client_id}")
async def client_sms_inbound(client_id: int, request: Request):
    form = await request.form()
    from_phone = form.get("From", "")
    to_phone   = form.get("To", "")
    body       = (form.get("Body") or "").strip()
    twilio_sid = form.get("MessageSid")

    if not from_phone or not body:
        return Response(content="", media_type="text/plain")

    pool = await get_pool()
    async with pool.acquire() as conn:
        client = await conn.fetchrow(
            "SELECT c.id, cmc.response_ai_enabled FROM clients c "
            "LEFT JOIN client_marketing_config cmc ON cmc.client_id = c.id WHERE c.id = $1",
            client_id,
        )
        if not client:
            return Response(content="", media_type="text/plain")

        await conn.execute(
            """
            INSERT INTO client_sms_messages (client_id, from_number, to_number, direction, body, twilio_sid)
            VALUES ($1, $2, $3, 'inbound', $4, $5)
            """,
            client_id, from_phone, to_phone, body, twilio_sid,
        )

    # response_ai_enabled is the per-client switch between the self-built
    # agent (response_ai.py) and the old Appointwise-forwarding path — never
    # both, so migrating a client off Appointwise is a single flag flip.
    if client["response_ai_enabled"]:
        await response_ai.handle_inbound_sms(client_id, from_phone, body)
    else:
        await forward_inbound_to_appointwise(client_id, from_phone, body)
    return Response(content="", media_type="text/plain")
