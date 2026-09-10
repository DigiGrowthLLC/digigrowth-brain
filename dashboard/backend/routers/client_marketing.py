"""
Admin-side management of each REAL client's OWN marketing infrastructure —
their Twilio number, their email-sending domain, their Appointwise response
agent, their landing page, and their ad creatives. Deliberately separate
from crm.py/sms.py/sms_sequences.py (DigiGrowth's own outreach) — nothing
here ever touches DigiGrowth's shared Twilio/Gmail credentials or the
internal sms_messages/email_messages/campaigns tables.

Mounted with require_auth like clients.py — this is agency-internal admin
tooling (Dylan provisioning a client's stack), not the client-facing portal.
"""
from fastapi import APIRouter, HTTPException

import client_email
import client_sms
from db import get_pool
from models import ClientMarketingConfigUpdate, ClientSmsSequenceUpdate, ClientTestEmail

router = APIRouter()


async def _get_or_create_config(conn, client_id: int) -> dict:
    row = await conn.fetchrow(
        "SELECT * FROM client_marketing_config WHERE client_id = $1", client_id
    )
    if row:
        return dict(row)
    row = await conn.fetchrow(
        "INSERT INTO client_marketing_config (client_id) VALUES ($1) RETURNING *",
        client_id,
    )
    return dict(row)


@router.get("/clients/{client_id}/marketing-config")
async def get_marketing_config(client_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        client = await conn.fetchrow("SELECT id FROM clients WHERE id = $1", client_id)
        if not client:
            raise HTTPException(404, "Client not found")
        return await _get_or_create_config(conn, client_id)


@router.put("/clients/{client_id}/marketing-config")
async def update_marketing_config(client_id: int, body: ClientMarketingConfigUpdate):
    pool = await get_pool()
    async with pool.acquire() as conn:
        client = await conn.fetchrow("SELECT id FROM clients WHERE id = $1", client_id)
        if not client:
            raise HTTPException(404, "Client not found")
        await _get_or_create_config(conn, client_id)

        fields = body.model_dump(exclude_unset=True)
        if not fields:
            return await _get_or_create_config(conn, client_id)

        set_clauses = []
        values = []
        for i, (key, value) in enumerate(fields.items(), start=1):
            set_clauses.append(f"{key} = ${i}")
            values.append(value)
        values.append(client_id)
        query = (
            f"UPDATE client_marketing_config SET {', '.join(set_clauses)}, updated_at = now() "
            f"WHERE client_id = ${len(values)} RETURNING *"
        )
        row = await conn.fetchrow(query, *values)
        return dict(row)


@router.post("/clients/{client_id}/marketing-config/provision-sms")
async def provision_sms_number(client_id: int, area_code: str | None = None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        client = await conn.fetchrow("SELECT id FROM clients WHERE id = $1", client_id)
        if not client:
            raise HTTPException(404, "Client not found")
    try:
        return await client_sms.provision_client_number(client_id, area_code=area_code)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))


@router.post("/clients/{client_id}/marketing-config/test-email")
async def send_test_email(client_id: int, body: ClientTestEmail):
    pool = await get_pool()
    async with pool.acquire() as conn:
        client = await conn.fetchrow("SELECT id FROM clients WHERE id = $1", client_id)
        if not client:
            raise HTTPException(404, "Client not found")
    try:
        result = await client_email.send_client_email(
            client_id, body.to, "Test email from your DigiGrowth setup",
            "This is a test send confirming your connected mailbox is working.",
        )
        return {"detail": result}
    except RuntimeError as e:
        raise HTTPException(400, str(e))


@router.get("/clients/{client_id}/sms-sequence")
async def get_client_sms_sequence(client_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        client = await conn.fetchrow("SELECT id FROM clients WHERE id = $1", client_id)
        if not client:
            raise HTTPException(404, "Client not found")
        row = await conn.fetchrow(
            "SELECT * FROM client_sms_sequences WHERE client_id = $1", client_id
        )
        if row:
            return dict(row)
        row = await conn.fetchrow(
            "INSERT INTO client_sms_sequences (client_id) VALUES ($1) RETURNING *",
            client_id,
        )
        return dict(row)


@router.put("/clients/{client_id}/sms-sequence")
async def update_client_sms_sequence(client_id: int, body: ClientSmsSequenceUpdate):
    pool = await get_pool()
    async with pool.acquire() as conn:
        client = await conn.fetchrow("SELECT id FROM clients WHERE id = $1", client_id)
        if not client:
            raise HTTPException(404, "Client not found")
        await conn.execute(
            "INSERT INTO client_sms_sequences (client_id) VALUES ($1) "
            "ON CONFLICT (client_id) DO NOTHING",
            client_id,
        )

        fields = body.model_dump(exclude_unset=True)
        if not fields:
            row = await conn.fetchrow(
                "SELECT * FROM client_sms_sequences WHERE client_id = $1", client_id
            )
            return dict(row)

        set_clauses = []
        values = []
        for i, (key, value) in enumerate(fields.items(), start=1):
            set_clauses.append(f"{key} = ${i}")
            values.append(value)
        values.append(client_id)
        query = (
            f"UPDATE client_sms_sequences SET {', '.join(set_clauses)}, updated_at = now() "
            f"WHERE client_id = ${len(values)} RETURNING *"
        )
        row = await conn.fetchrow(query, *values)
        return dict(row)


@router.get("/clients/{client_id}/sms-messages")
async def list_client_sms_messages(client_id: int, limit: int = 200):
    pool = await get_pool()
    async with pool.acquire() as conn:
        client = await conn.fetchrow("SELECT id FROM clients WHERE id = $1", client_id)
        if not client:
            raise HTTPException(404, "Client not found")
        rows = await conn.fetch(
            "SELECT * FROM client_sms_messages WHERE client_id = $1 "
            "ORDER BY created_at DESC LIMIT $2",
            client_id, limit,
        )
        return [dict(r) for r in rows]
