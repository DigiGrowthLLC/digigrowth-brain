"""
Admin-side client management — CRUD for agency clients (e.g. independent PT
practices), their portal access tokens, and the shared onboarding-video
library. Mounted with require_auth like every other admin router; the
client-facing counterpart (token-scoped, no auth) lives in client_portal.py.
"""
import json
import os
import secrets

from fastapi import APIRouter, HTTPException

from db import get_pool
from models import (
    ClientCreate, ClientUpdate, ClientLinkContact, OnboardingVideoCreate, OnboardingVideoUpdate,
    ActionItemCreate, ActionItemUpdate, ONBOARDING_SECTIONS,
)

router = APIRouter()

_DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "https://digigrowth-brain-production.up.railway.app").rstrip("/")


def _portal_url(token: str) -> str:
    return f"{_DASHBOARD_URL}/portal/{token}"


async def _linked_contact_summary(conn, client_id: int) -> dict | None:
    """The anchor contact — the specific prospect this client's deal came
    from — for display in the Clients list, e.g. "Linked to: Erin Morley —
    More Physical Therapy". Filtered on is_client_anchor=true specifically
    (not just any contact with this client_id) because contacts.client_id
    is also used for a completely different thing: leads the client's own
    campaign generates, added via their portal (portal_create_lead) or a
    future real integration. Those are the client's own business activity
    and must never be confused with the one internal DigiGrowth contact
    used to resolve the portal link — see client_portal.py's module note on
    why mixing the two showed a client's own sales-pipeline history back at
    them as if it were their own patient activity."""
    row = await conn.fetchrow(
        "SELECT id, business, owner FROM contacts WHERE client_id = $1 AND is_client_anchor LIMIT 1",
        client_id,
    )
    return dict(row) if row else None


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
            d["linked_contact"] = await _linked_contact_summary(conn, d["id"])
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
            INSERT INTO clients (name, contact_name, email, phone, notes, portal_token, is_test, calendly_url)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING *
            """,
            name, body.contact_name, body.email, body.phone, body.notes, token, body.is_test, body.calendly_url,
        )
        # Links the specific prospect/contact whose deal this client came
        # from — this is what onboarding_sequence.py's next-morning
        # follow-up resolves (contact -> contacts.client_id -> this row's
        # portal_token) to know which portal link to send. Without this,
        # the client record exists but no contact ever points back at it,
        # so the follow-up send has nothing to resolve and skips forever.
        if body.contact_id:
            await conn.execute(
                "UPDATE contacts SET client_id = $1, is_client_anchor = true, updated_at = now() WHERE id = $2",
                row["id"], body.contact_id,
            )
        d = dict(row)
        d["linked_contact"] = await _linked_contact_summary(conn, d["id"])
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
        linked_contact = await _linked_contact_summary(conn, client_id)
    d = dict(client)
    d["portal_url"] = _portal_url(d["portal_token"])
    def _decode(r):
        row = dict(r)
        row["answers"] = json.loads(row["answers"]) if isinstance(row["answers"], str) else row["answers"]
        return row
    d["onboarding"] = {r["section"]: _decode(r) for r in responses}
    d["contacts_count"] = contacts_count
    d["linked_contact"] = linked_contact
    return d


@router.post("/clients/{client_id}/link-contact")
async def link_contact(client_id: int, body: ClientLinkContact):
    """Point a contact at this client (contacts.client_id), or clear it if
    contact_id is null. This is what onboarding_sequence.py's next-morning
    follow-up resolves to find a client's portal link — use this to fix a
    client created without picking a contact, or to relink after a mistake."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        client = await conn.fetchrow("SELECT id FROM clients WHERE id = $1", client_id)
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        if body.contact_id:
            contact = await conn.fetchrow("SELECT id FROM contacts WHERE id = $1", body.contact_id)
            if not contact:
                raise HTTPException(status_code=404, detail="Contact not found")
            # Clear anchor status off any previous anchor for this client
            # first — there should only ever be one, and relinking is how a
            # mistake gets fixed.
            await conn.execute(
                "UPDATE contacts SET is_client_anchor = false, updated_at = now() WHERE client_id = $1 AND is_client_anchor",
                client_id,
            )
            await conn.execute(
                "UPDATE contacts SET client_id = $1, is_client_anchor = true, updated_at = now() WHERE id = $2",
                client_id, body.contact_id,
            )
        else:
            # Unlink every contact currently pointed at this client (leads
            # the client's own portal generated keep their client_id — only
            # the anchor gets fully cleared here, since "unlink" means "this
            # client has no anchor contact anymore").
            await conn.execute(
                "UPDATE contacts SET client_id = NULL, is_client_anchor = false, updated_at = now() "
                "WHERE client_id = $1 AND is_client_anchor",
                client_id,
            )
        linked_contact = await _linked_contact_summary(conn, client_id)
    return {"ok": True, "linked_contact": linked_contact}


@router.post("/clients/{client_id}/link-all-unassigned")
async def link_all_unassigned(client_id: int):
    """Bulk-assigns every contact with no client_id at all (client_id IS
    NULL — never touches a contact already linked to a different client, so
    Brandon Crosdale's client_id stays exactly as-is) to this client.

    Built for the "DigiGrowth Test" self-client case: linking every one of
    Dylan's own real, unclaimed leads/SMS/email history to a client he owns
    himself, so the portal has real end-to-end data to verify against
    instead of a synthetic empty shell. Only ever touches unclaimed rows —
    running it twice, or against a client that already has real leads
    assigned some other way, is safe and idempotent."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        client = await conn.fetchrow("SELECT id FROM clients WHERE id = $1", client_id)
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        rows = await conn.fetch(
            "UPDATE contacts SET client_id = $1, updated_at = now() "
            "WHERE client_id IS NULL RETURNING id",
            client_id,
        )
    return {"ok": True, "linked_count": len(rows)}


@router.post("/clients/{client_id}/unlink-all-leads")
async def unlink_all_leads(client_id: int):
    """Reverse of link_all_unassigned above: clears client_id on every
    contact linked to this client EXCEPT the anchor (never touches
    is_client_anchor=true — that's the one real prospect-turned-client
    contact, not a bulk-assigned lead). Sets those contacts back to
    client_id = NULL, restoring them to the internal OS's CRM/Dialer/
    Inbox/Analytics (which now exclude any contact with a client_id, per
    the 2026-09-01 CRM-isolation fix) instead of the client's own portal
    Leads tab. Built to undo a link_all_unassigned run that swept up real
    working leads Dylan still needed internally."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        client = await conn.fetchrow("SELECT id FROM clients WHERE id = $1", client_id)
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        rows = await conn.fetch(
            "UPDATE contacts SET client_id = NULL, updated_at = now() "
            "WHERE client_id = $1 AND NOT is_client_anchor RETURNING id",
            client_id,
        )
    return {"ok": True, "unlinked_count": len(rows)}


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
