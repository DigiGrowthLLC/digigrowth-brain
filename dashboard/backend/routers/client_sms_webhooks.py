"""
Public Twilio webhook for inbound SMS to a REAL client's OWN provisioned
number (see client_sms.py). The client_id is encoded directly in the
webhook URL Twilio calls (set as sms_url when the number was purchased),
so each inbound message is unambiguously scoped to one client and stored
in client_sms_messages — never sms_messages, which is DigiGrowth's own.

If client_marketing_config.response_ai_enabled is set, the self-built AI
agent (response_ai.py) handles the reply. Otherwise the message just stays
logged here for manual review, same as any other unconnected channel.
"""
from datetime import datetime, timedelta, timezone as dt_timezone

from fastapi import APIRouter, Request, Response

import client_appointment_sequence
import response_ai
import scheduler_registry
from db import get_pool

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
            "SELECT c.id, cmc.response_ai_enabled, cmc.response_ai_min_delay_seconds FROM clients c "
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

    await client_appointment_sequence.stop_sequence_for_reply(phone=from_phone)

    if client["response_ai_enabled"]:
        delay = client["response_ai_min_delay_seconds"] or 0
        sched = scheduler_registry.get_scheduler()
        if delay > 0 and sched:
            # Deferred via the app's own scheduler (same mechanism every
            # other scheduled job in this codebase uses) rather than
            # sleeping inline — sleeping here would hold the Twilio webhook
            # open for the full delay and risk a timeout/retry, and a plain
            # background thread can't safely reuse db.py's asyncpg pool
            # (bound to the main event loop) — see response_ai.py and
            # scheduler_registry.py's docstrings.
            run_at = datetime.now(dt_timezone.utc) + timedelta(seconds=delay)
            sched.add_job(
                response_ai.handle_inbound_sms, "date", run_date=run_at,
                args=[client_id, from_phone, body],
                id=f"response-ai-{client_id}-{twilio_sid or run_at.timestamp()}",
                replace_existing=True,
            )
        else:
            await response_ai.handle_inbound_sms(client_id, from_phone, body)
    # else: response_ai disabled — message just stays logged for manual review.
    return Response(content="", media_type="text/plain")
