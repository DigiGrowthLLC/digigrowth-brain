from fastapi import APIRouter
from db import get_pool

router = APIRouter()


@router.get("/public/sops")
async def list_public_sops():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM sops WHERE visibility = 'public' ORDER BY category, sort_order, id"
        )
    return [dict(r) for r in rows]
