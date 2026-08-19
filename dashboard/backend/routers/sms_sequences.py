"""
SMS Sequences — named, multi-step SMS outreach sequences editable from
Business Resources -> Outreach Templates. Exactly one sequence may be
"active" (is_active=true) at a time, enforced by the partial unique index
idx_sms_sequences_one_active (db.py); the active sequence is what populates
the SMS Inbox's SEQUENCE dropdown (see routers/sms.py get_sequence()).

Endpoints (all under /api):
  GET    /sms-sequences               — list all, active first
  POST   /sms-sequences               — create a new sequence (starts inactive)
  PATCH  /sms-sequences/{id}          — update name/category/steps
  DELETE /sms-sequences/{id}          — delete (rejected if currently active)
  POST   /sms-sequences/{id}/activate — make this the one active sequence
"""

import json

from fastapi import APIRouter, HTTPException

from db import get_pool
from routers.sms import SEQUENCE_STEPS

router = APIRouter()

_STEP_KEYS = {key for key, _ in SEQUENCE_STEPS}


def _row_to_dict(r) -> dict:
    steps = r["steps"]
    if isinstance(steps, str):
        steps = json.loads(steps)
    return {
        "id": r["id"],
        "name": r["name"],
        "category": r["category"],
        "steps": steps or {},
        "is_active": r["is_active"],
        "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
    }


def _clean_steps(steps: dict) -> dict:
    # Only persist known step keys so a stale/future frontend payload can't
    # pollute the JSONB column with orphaned keys.
    return {k: (steps or {}).get(k, "") for k in _STEP_KEYS}


@router.get("/sms-sequences")
async def list_sequences():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM sms_sequences ORDER BY is_active DESC, name ASC")
    return [_row_to_dict(r) for r in rows]


@router.post("/sms-sequences")
async def create_sequence(body: dict):
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    category = (body.get("category") or "General").strip() or "General"
    steps = _clean_steps(body.get("steps") or {})
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO sms_sequences (name, category, steps, is_active)
            VALUES ($1, $2, $3::jsonb, false)
            RETURNING *
            """,
            name, category, json.dumps(steps),
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
        if "steps" in body:
            steps = _clean_steps(body["steps"])
        else:
            existing_steps = existing["steps"]
            steps = json.loads(existing_steps) if isinstance(existing_steps, str) else existing_steps
        row = await conn.fetchrow(
            """
            UPDATE sms_sequences
            SET name = $1, category = $2, steps = $3::jsonb, updated_at = now()
            WHERE id = $4
            RETURNING *
            """,
            name, category, json.dumps(steps), sequence_id,
        )
    return _row_to_dict(row)


@router.delete("/sms-sequences/{sequence_id}")
async def delete_sequence(sequence_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT is_active FROM sms_sequences WHERE id = $1", sequence_id)
        if not row:
            raise HTTPException(status_code=404, detail="Sequence not found")
        if row["is_active"]:
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
            # Flip the old active row off before the new one on — the two
            # UPDATEs never leave two rows true at once, so the partial
            # unique index (idx_sms_sequences_one_active) is never violated.
            await conn.execute(
                "UPDATE sms_sequences SET is_active = false WHERE is_active = true AND id != $1",
                sequence_id,
            )
            row = await conn.fetchrow(
                "UPDATE sms_sequences SET is_active = true, updated_at = now() WHERE id = $1 RETURNING *",
                sequence_id,
            )
    return _row_to_dict(row)
