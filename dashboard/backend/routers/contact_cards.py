"""OS contact cards: find a prospect's contact from wherever their name
shows up, and their patient intake (patient_intake.py). Under
/contact-cards/ so nothing collides with crm.py's /contacts/{id}."""
from typing import Optional

from fastapi import APIRouter, HTTPException

import patient_intake
from db import get_pool

router = APIRouter()

_LAST10 = r"right(regexp_replace({col}, '\D', '', 'g'), 10)"


@router.get("/contact-cards/resolve")
async def resolve_contact(phone: Optional[str] = None, email: Optional[str] = None, client_id: Optional[int] = None):
    """The contact behind a name that's only known by phone/email (a
    booking, a voice call, a DM). Prefers the client's own lead."""
    if not phone and not email:
        raise HTTPException(400, "phone or email required")
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = None
        if phone:
            row = await conn.fetchrow(
                f"""SELECT id FROM contacts WHERE {_LAST10.format(col='phone')} = {_LAST10.format(col='$1')}
                    AND length(regexp_replace($1, '\\D', '', 'g')) >= 10
                    ORDER BY (client_id IS NOT DISTINCT FROM $2::int) DESC, is_client_anchor, created_at DESC LIMIT 1""",
                phone, client_id)
        if not row and email:
            row = await conn.fetchrow(
                """SELECT id FROM contacts WHERE lower(email) = lower($1)
                   ORDER BY (client_id IS NOT DISTINCT FROM $2::int) DESC, is_client_anchor, created_at DESC LIMIT 1""",
                email.strip(), client_id)
    if not row:
        raise HTTPException(404, "No contact found")
    return {"id": row["id"]}


async def _client_lead(contact_id: str) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        cid = await conn.fetchval(
            "SELECT client_id FROM contacts WHERE id = $1 AND client_id IS NOT NULL AND NOT is_client_anchor", contact_id)
    if cid is None:
        raise HTTPException(404, "Not a client's prospect")
    return cid


@router.get("/contact-cards/{contact_id}/intake")
async def get_intake(contact_id: str):
    await _client_lead(contact_id)
    return await patient_intake.get(contact_id)


@router.put("/contact-cards/{contact_id}/intake")
async def save_intake(contact_id: str, body: dict):
    client_id = await _client_lead(contact_id)
    return await patient_intake.save_manual(contact_id, client_id, body or {})


@router.post("/contact-cards/{contact_id}/intake/refresh")
async def refresh_intake(contact_id: str):
    await _client_lead(contact_id)
    return await patient_intake.refresh(contact_id)
