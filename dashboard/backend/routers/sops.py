from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from db import get_pool

router = APIRouter()


class SOPCreate(BaseModel):
    title: str
    content: str = ""
    category: str = "General"
    visibility: str = "private"
    sort_order: int = 0
    doc_type: str = "sop"


class SOPUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    visibility: Optional[str] = None
    sort_order: Optional[int] = None
    doc_type: Optional[str] = None


@router.get("/sops")
async def list_sops(category: Optional[str] = Query(None), doc_type: Optional[str] = Query(None)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        if category and doc_type:
            rows = await conn.fetch(
                "SELECT * FROM sops WHERE category = $1 AND doc_type = $2 ORDER BY category, sort_order, id",
                category, doc_type,
            )
        elif category:
            rows = await conn.fetch(
                "SELECT * FROM sops WHERE category = $1 ORDER BY category, sort_order, id",
                category,
            )
        elif doc_type:
            rows = await conn.fetch(
                "SELECT * FROM sops WHERE doc_type = $1 ORDER BY category, sort_order, id",
                doc_type,
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM sops ORDER BY category, sort_order, id"
            )
    return [dict(r) for r in rows]


@router.post("/sops")
async def create_sop(body: SOPCreate):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO sops (title, content, category, visibility, sort_order, doc_type)
               VALUES ($1, $2, $3, $4, $5, $6) RETURNING *""",
            body.title, body.content, body.category, body.visibility, body.sort_order, body.doc_type,
        )
    return dict(row)


@router.patch("/sops/{sop_id}")
async def update_sop(sop_id: int, body: SOPUpdate):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    fields = ", ".join(f"{k} = ${i + 2}" for i, k in enumerate(updates))
    values = list(updates.values())

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"UPDATE sops SET {fields}, updated_at = now() WHERE id = $1 RETURNING *",
            sop_id, *values,
        )
    if not row:
        raise HTTPException(status_code=404, detail="SOP not found")
    return dict(row)


@router.delete("/sops/{sop_id}")
async def delete_sop(sop_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM sops WHERE id = $1", sop_id)
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="SOP not found")
    return {"ok": True}
