"""
Cold Call Scripts — named, multi-section dialer scripts editable from
Business Resources -> Outreach Templates. Exactly one script may be
"default" (is_default=true) at a time, enforced by the partial unique index
idx_cold_call_scripts_single_default (db.py); the default script is what
DialerPanel.jsx displays/fills during a live call (see GET /dialer/script
in routers/dialer.py).

Each script has 4 fixed sections — opener, intro, main_body, close — each
its own TEXT column, matching how the table was originally built.

Endpoints (all under /api):
  GET    /cold-call-scripts               — list all, default first
  POST   /cold-call-scripts               — create a new script (starts non-default)
  PATCH  /cold-call-scripts/{id}          — update name/category/sections
  DELETE /cold-call-scripts/{id}          — delete (rejected if currently default)
  POST   /cold-call-scripts/{id}/activate — make this the one default script
"""

from fastapi import APIRouter, HTTPException

from db import get_pool

router = APIRouter()

SECTION_KEYS = [
    ("opener", "Opener"),
    ("intro", "Intro"),
    ("main_body", "Main Body"),
    ("close", "Close"),
]
_SECTION_KEYS = [key for key, _ in SECTION_KEYS]


def _row_to_dict(r) -> dict:
    return {
        "id": r["id"],
        "name": r["name"],
        "category": r["category"],
        "sections": {k: r[k] or "" for k in _SECTION_KEYS},
        "is_active": r["is_default"],
        "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
    }


@router.get("/cold-call-scripts")
async def list_scripts():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM cold_call_scripts ORDER BY is_default DESC, name ASC")
    return [_row_to_dict(r) for r in rows]


@router.post("/cold-call-scripts")
async def create_script(body: dict):
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    category = (body.get("category") or "General").strip() or "General"
    sections = body.get("sections") or {}
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO cold_call_scripts
                (name, category, is_default, opener, intro, main_body, close)
            VALUES ($1, $2, false, $3, $4, $5, $6)
            RETURNING *
            """,
            name, category,
            sections.get("opener", ""), sections.get("intro", ""),
            sections.get("main_body", ""), sections.get("close", ""),
        )
    return _row_to_dict(row)


@router.patch("/cold-call-scripts/{script_id}")
async def update_script(script_id: int, body: dict):
    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT * FROM cold_call_scripts WHERE id = $1", script_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Script not found")
        name = ((body.get("name") if "name" in body else existing["name"]) or existing["name"]).strip()
        category = ((body.get("category") if "category" in body else existing["category"]) or "General").strip() or "General"
        sections = body.get("sections") if "sections" in body else {k: existing[k] for k in _SECTION_KEYS}
        row = await conn.fetchrow(
            """
            UPDATE cold_call_scripts
            SET name = $1, category = $2,
                opener = $3, intro = $4, main_body = $5, close = $6,
                updated_at = now()
            WHERE id = $7
            RETURNING *
            """,
            name, category,
            sections.get("opener", ""), sections.get("intro", ""),
            sections.get("main_body", ""), sections.get("close", ""),
            script_id,
        )
    return _row_to_dict(row)


@router.delete("/cold-call-scripts/{script_id}")
async def delete_script(script_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT is_default FROM cold_call_scripts WHERE id = $1", script_id)
        if not row:
            raise HTTPException(status_code=404, detail="Script not found")
        if row["is_default"]:
            raise HTTPException(
                status_code=400,
                detail="Can't delete the default script — set a different script as default first.",
            )
        await conn.execute("DELETE FROM cold_call_scripts WHERE id = $1", script_id)
    return {"ok": True}


@router.post("/cold-call-scripts/{script_id}/activate")
async def activate_script(script_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            exists = await conn.fetchval("SELECT 1 FROM cold_call_scripts WHERE id = $1", script_id)
            if not exists:
                raise HTTPException(status_code=404, detail="Script not found")
            # Flip the old default row off before the new one on — the two
            # UPDATEs never leave two rows true at once, so the partial
            # unique index (idx_cold_call_scripts_single_default) is never
            # violated.
            await conn.execute(
                "UPDATE cold_call_scripts SET is_default = false WHERE is_default = true AND id != $1",
                script_id,
            )
            row = await conn.fetchrow(
                "UPDATE cold_call_scripts SET is_default = true, updated_at = now() WHERE id = $1 RETURNING *",
                script_id,
            )
    return _row_to_dict(row)
