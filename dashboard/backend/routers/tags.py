from fastapi import APIRouter, HTTPException
from db import get_pool
from models import TagCreate, TagUpdate

router = APIRouter()


@router.get("/tags")
async def list_tags():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM tags ORDER BY name")
    return [dict(r) for r in rows]


@router.post("/tags")
async def create_tag(body: TagCreate):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="name required")
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO tags (name, color) VALUES ($1, $2) "
            "ON CONFLICT (name) DO UPDATE SET color = EXCLUDED.color "
            "RETURNING *",
            name, body.color or "#3a7bd5",
        )
    return dict(row)


@router.patch("/tags/{tag_id}")
async def update_tag(tag_id: int, body: TagUpdate):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE tags SET color = COALESCE($2, color) WHERE id = $1 RETURNING *",
            tag_id, body.color,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Tag not found")
    return dict(row)


@router.delete("/tags/{tag_id}")
async def delete_tag(tag_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("DELETE FROM tags WHERE id = $1 RETURNING name", tag_id)
        if not row:
            raise HTTPException(status_code=404, detail="Tag not found")
        await conn.execute(
            "UPDATE contacts SET tags = array_remove(tags, $1), updated_at = now() WHERE $1 = ANY(tags)",
            row["name"],
        )
    return {"ok": True}
