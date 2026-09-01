"""
Admin-side client management — CRUD for agency clients (e.g. independent PT
practices), their portal access tokens, and the shared onboarding-video
library. Mounted with require_auth like every other admin router; the
client-facing counterpart (token-scoped, no auth) lives in client_portal.py.
"""
import os
import secrets

from fastapi import APIRouter, HTTPException

from db import get_pool
from models import (
    ClientCreate, ClientUpdate, OnboardingVideoCreate, OnboardingVideoUpdate,
    ActionItemCreate, ActionItemUpdate, ONBOARDING_SECTIONS,
)

router = APIRouter()

_DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "https://digigrowth-brain-production.up.railway.app").rstrip("/")


def _portal_url(token: str) -> str:
    return f"{_DASHBOARD_URL}/portal/{token}"


@router.get("/clients")
async def list_clients():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT c.*, COUNT(cor.id) FILTER (WHERE cor.completed_at IS NOT NULL) AS sections_completed
            FROM clients c
            LEFT JOIN client_onboarding_responses cor ON cor.client_id = c.id
            GROUP BY c.id
            ORDER BY c.created_at DESC
            """
        )
    out = []
    for r in rows:
        d = dict(r)
        d["onboarding_progress"] = f"{d.pop('sections_completed')}/{len(ONBOARDING_SECTIONS)}"
        d["portal_url"] = _portal_url(d["portal_token"])
        out.append(d)
    return out


@router.post("/clients")
async def create_client(body: ClientCreate):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="name required")
    token = secrets.token_urlsafe(24)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO clients (name, contact_name, email, phone, notes, portal_token)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING *
            """,
            name, body.contact_name, body.email, body.phone, body.notes, token,
        )
    d = dict(row)
    d["portal_url"] = _portal_url(d["portal_token"])
    return d


@router.get("/clients/{client_id}")
async def get_client(client_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        client = await conn.fetchrow("SELECT * FROM clients WHERE id = $1", client_id)
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        responses = await conn.fetch(
            "SELECT * FROM client_onboarding_responses WHERE client_id = $1", client_id
        )
        contacts_count = await conn.fetchval(
            "SELECT count(*) FROM contacts WHERE client_id = $1", client_id
        )
    d = dict(client)
    d["portal_url"] = _portal_url(d["portal_token"])
    d["onboarding"] = {r["section"]: dict(r) for r in responses}
    d["contacts_count"] = contacts_count
    return d


@router.patch("/clients/{client_id}")
async def update_client(client_id: int, body: ClientUpdate):
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="no fields to update")
    pool = await get_pool()
    async with pool.acquire() as conn:
        set_clauses = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(fields))
        row = await conn.fetchrow(
            f"UPDATE clients SET {set_clauses}, updated_at = now() WHERE id = $1 RETURNING *",
            client_id, *fields.values(),
        )
    if not row:
        raise HTTPException(status_code=404, detail="Client not found")
    d = dict(row)
    d["portal_url"] = _portal_url(d["portal_token"])
    return d


@router.post("/clients/{client_id}/regenerate-token")
async def regenerate_token(client_id: int):
    token = secrets.token_urlsafe(24)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE clients SET portal_token = $2, token_revoked_at = NULL, updated_at = now() "
            "WHERE id = $1 RETURNING *",
            client_id, token,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Client not found")
    d = dict(row)
    d["portal_url"] = _portal_url(d["portal_token"])
    return d


@router.post("/clients/{client_id}/revoke-token")
async def revoke_token(client_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE clients SET token_revoked_at = now(), updated_at = now() WHERE id = $1 RETURNING *",
            client_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Client not found")
    return dict(row)


@router.delete("/clients/{client_id}")
async def delete_client(client_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("DELETE FROM clients WHERE id = $1 RETURNING id", client_id)
    if not row:
        raise HTTPException(status_code=404, detail="Client not found")
    return {"ok": True}


# ---------------- Onboarding video library (shared across all clients) ----------------

@router.get("/onboarding-videos")
async def list_onboarding_videos():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM onboarding_videos ORDER BY sort_order, id")
    return [dict(r) for r in rows]


@router.post("/onboarding-videos")
async def create_onboarding_video(body: OnboardingVideoCreate):
    title = body.title.strip()
    embed_url = body.embed_url.strip()
    if not title or not embed_url:
        raise HTTPException(status_code=400, detail="title and embed_url required")
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO onboarding_videos (title, description, embed_url, sort_order)
            VALUES ($1, $2, $3, $4) RETURNING *
            """,
            title, body.description, embed_url, body.sort_order,
        )
    return dict(row)


@router.patch("/onboarding-videos/{video_id}")
async def update_onboarding_video(video_id: int, body: OnboardingVideoUpdate):
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="no fields to update")
    pool = await get_pool()
    async with pool.acquire() as conn:
        set_clauses = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(fields))
        row = await conn.fetchrow(
            f"UPDATE onboarding_videos SET {set_clauses} WHERE id = $1 RETURNING *",
            video_id, *fields.values(),
        )
    if not row:
        raise HTTPException(status_code=404, detail="Video not found")
    return dict(row)


@router.delete("/onboarding-videos/{video_id}")
async def delete_onboarding_video(video_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("DELETE FROM onboarding_videos WHERE id = $1 RETURNING id", video_id)
    if not row:
        raise HTTPException(status_code=404, detail="Video not found")
    return {"ok": True}


# ---------------- Onboarding "Next Steps" action items (shared across all clients) ----------------

@router.get("/action-items")
async def list_action_items():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM onboarding_action_items ORDER BY sort_order, id")
    return [dict(r) for r in rows]


@router.post("/action-items")
async def create_action_item(body: ActionItemCreate):
    title = body.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="title required")
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO onboarding_action_items (title, description, link_tab, link_url, sort_order) "
            "VALUES ($1, $2, $3, $4, $5) RETURNING *",
            title, body.description, body.link_tab, body.link_url, body.sort_order,
        )
    return dict(row)


@router.patch("/action-items/{item_id}")
async def update_action_item(item_id: int, body: ActionItemUpdate):
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="no fields to update")
    pool = await get_pool()
    async with pool.acquire() as conn:
        set_clauses = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(fields))
        row = await conn.fetchrow(
            f"UPDATE onboarding_action_items SET {set_clauses} WHERE id = $1 RETURNING *",
            item_id, *fields.values(),
        )
    if not row:
        raise HTTPException(status_code=404, detail="Action item not found")
    return dict(row)


@router.delete("/action-items/{item_id}")
async def delete_action_item(item_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("DELETE FROM onboarding_action_items WHERE id = $1 RETURNING id", item_id)
    if not row:
        raise HTTPException(status_code=404, detail="Action item not found")
    return {"ok": True}
