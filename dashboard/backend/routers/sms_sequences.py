"""
SMS Sequences — named, multi-step SMS outreach sequences editable from
Business Resources -> Outreach Templates. Exactly one sequence may be
"default" (is_default=true) at a time, enforced by the partial unique index
idx_sms_sequences_single_default (db.py); the default sequence is what
populates the SMS Inbox's SEQUENCE dropdown (see routers/sms.py get_sequence()).

Each of the 5 fixed steps (see routers/sms.py SEQUENCE_STEPS for the
canonical key/label/order) is its own TEXT column on sms_sequences rather
than a JSONB blob, matching how the table was originally built.

Endpoints (all under /api):
  GET    /sms-sequences               — list all, default first
  POST   /sms-sequences               — create a new sequence (starts non-default)
  PATCH  /sms-sequences/{id}          — update name/category/steps
  DELETE /sms-sequences/{id}          — delete (rejected if currently default)
  POST   /sms-sequences/{id}/activate — make this the one default sequence
"""

from fastapi import APIRouter, HTTPException

from db import get_pool
from routers.sms import SEQUENCE_STEPS

router = APIRouter()

_STEP_KEYS = [key for key, _ in SEQUENCE_STEPS]


def _row_to_dict(r) -> dict:
    return {
        "id": r["id"],
        "name": r["name"],
        "category": r["category"],
        "steps": {k: r[k] or "" for k in _STEP_KEYS},
        "is_active": r["is_default"],
        "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
    }


@router.get("/sms-sequences")
async def list_sequences():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM sms_sequences ORDER BY is_default DESC, name ASC")
    return [_row_to_dict(r) for r in rows]


@router.post("/sms-sequences")
async def create_sequence(body: dict):
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    category = (body.get("category") or "General").strip() or "General"
    steps = body.get("steps") or {}
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO sms_sequences
                (name, category, is_default, curiosity_opener, relevance, guarantee, ask, cta)
            VALUES ($1, $2, false, $3, $4, $5, $6, $7)
            RETURNING *
            """,
            name, category,
            steps.get("curiosity_opener", ""), steps.get("relevance", ""),
            steps.get("guarantee", ""), steps.get("ask", ""), steps.get("cta", ""),
        )
    return _row_to_dict(row)


@router.patch("/sms-sequences/{sequence_id}")
async def update_sequence(sequence_id: int, body: dict):
    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT * FROM sms_sequences WHERE id = $1", sequence_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Sequence not found")
        name = ((body.get("name") if "name" in body else existing["name"]) or existing["name"]).strip()
        category = ((body.get("category") if "category" in body else existing["category"]) or "General").strip() or "General"
        steps = body.get("steps") if "steps" in body else {k: existing[k] for k in _STEP_KEYS}
        row = await conn.fetchrow(
            """
            UPDATE sms_sequences
            SET name = $1, category = $2,
                curiosity_opener = $3, relevance = $4, guarantee = $5, ask = $6, cta = $7,
                updated_at = now()
            WHERE id = $8
            RETURNING *
            """,
            name, category,
            steps.get("curiosity_opener", ""), steps.get("relevance", ""),
            steps.get("guarantee", ""), steps.get("ask", ""), steps.get("cta", ""),
            sequence_id,
        )
    return _row_to_dict(row)


@router.delete("/sms-sequences/{sequence_id}")
async def delete_sequence(sequence_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT is_default FROM sms_sequences WHERE id = $1", sequence_id)
        if not row:
            raise HTTPException(status_code=404, detail="Sequence not found")
        if row["is_default"]:
            raise HTTPException(
                status_code=400,
                detail="Can't delete the default sequence — set a different sequence as default first.",
            )
        await conn.execute("DELETE FROM sms_sequences WHERE id = $1", sequence_id)
    return {"ok": True}


@router.post("/sms-sequences/{sequence_id}/activate")
async def activate_sequence(sequence_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            exists = await conn.fetchval("SELECT 1 FROM sms_sequences WHERE id = $1", sequence_id)
            if not exists:
                raise HTTPException(status_code=404, detail="Sequence not found")
            # Flip the old default row off before the new one on — the two
            # UPDATEs never leave two rows true at once, so the partial
            # unique index (idx_sms_sequences_single_default) is never
            # violated.
            await conn.execute(
                "UPDATE sms_sequences SET is_default = false WHERE is_default = true AND id != $1",
                sequence_id,
            )
            row = await conn.fetchrow(
                "UPDATE sms_sequences SET is_default = true, updated_at = now() WHERE id = $1 RETURNING *",
                sequence_id,
            )
    return _row_to_dict(row)
