"""
Appointwise integration — STUB pending their actual API docs/credentials.
Appointwise plugs into a number/inbox WE provide (confirmed 2026-09-10),
i.e. the client's own Twilio number from client_sms.py, rather than
bringing its own number. Two directions:

  1. Forward inbound: client_sms_webhooks.py calls forward_inbound_to_appointwise()
     for every inbound message on a client's number, if that client has
     appointwise_webhook_url set. The exact payload shape below is a
     reasonable guess (client_id/from/body) and MUST be checked against
     Appointwise's real docs before relying on it.
  2. Callback to send: this router exposes a webhook Appointwise can call
     to have a reply sent from the client's own Twilio number. The route
     path/payload shape here is also a guess — confirm against their docs
     and adjust before pointing a real Appointwise agent at it.

Do not treat anything in this file as verified against Appointwise's real
API until their docs are in hand.
"""
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import client_sms
from db import get_pool

router = APIRouter()  # public — no auth, mounted with no prefix in main.py


async def forward_inbound_to_appointwise(client_id: int, from_number: str, body: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        webhook_url = await conn.fetchval(
            "SELECT appointwise_webhook_url FROM client_marketing_config WHERE client_id = $1",
            client_id,
        )
    if not webhook_url:
        return  # not connected yet — message just stays logged for manual reply

    try:
        async with httpx.AsyncClient(timeout=10) as http:
            await http.post(webhook_url, json={
                "client_id": client_id,
                "from": from_number,
                "body": body,
            })
    except httpx.HTTPError:
        # Best-effort only — the inbound message is already stored in
        # client_sms_messages regardless of whether Appointwise received it.
        pass


class AppointwiseSendRequest(BaseModel):
    client_id: int
    to: str
    body: str


@router.post("/webhooks/appointwise/send")
async def appointwise_send_callback(body: AppointwiseSendRequest):
    """Appointwise calls this to send a reply from the client's own Twilio number."""
    try:
        await client_sms.send_client_sms(body.client_id, body.to, body.body)
        return {"detail": "sent"}
    except RuntimeError as e:
        raise HTTPException(400, str(e))
