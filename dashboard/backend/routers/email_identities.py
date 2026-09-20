"""Admin endpoints for the internal cold-outreach email identities
(email_send_identities) and their cross-provider warm-up state
(identity_warmup). Backs SOPsPanel.jsx's "Email Handoff" outreach-template
section and the IdentityWarmupModal.jsx sequence view.

  GET    /api/email-identities                  — list, joined with warm-up status
  POST   /api/email-identities                   — create (refresh token pasted in after
                                                    an out-of-band OAuth consent run)
  PATCH  /api/email-identities/{id}               — edit display name/status/token
  DELETE /api/email-identities/{id}               — remove (cascades warmup/log rows)
  POST   /api/email-identities/{id}/start-warmup  — start/restart the ramp
  POST   /api/email-identities/{id}/pause         — pause (excluded from sends + warm-up)
  POST   /api/email-identities/{id}/activate      — promote warming -> active
  GET    /api/email-identities/warmup-sequence    — sequence-view data
"""
from fastapi import APIRouter, HTTPException

import identity_warmup
from db import get_pool

router = APIRouter()


@router.get("/email-identities")
async def list_identities():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT s.id, s.provider, s.domain, s.mailbox_email, s.display_name, s.status,
                   s.activated_at, s.created_at,
                   w.status AS warmup_status, w.current_day, w.sent_today, w.replied_today,
                   w.last_sent_at, w.started_at, w.completed_at
            FROM email_send_identities s
            LEFT JOIN identity_warmup w ON w.identity_id = s.id
            ORDER BY s.created_at
            """
        )
    return [dict(r) for r in rows]


@router.post("/email-identities")
async def create_identity(body: dict):
    provider = (body.get("provider") or "").strip()
    if provider not in ("google", "microsoft"):
        raise HTTPException(status_code=400, detail="provider must be 'google' or 'microsoft'")
    mailbox_email = (body.get("mailbox_email") or "").strip()
    domain = (body.get("domain") or "").strip()
    if not mailbox_email or not domain:
        raise HTTPException(status_code=400, detail="mailbox_email and domain are required")

    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO email_send_identities
                    (provider, domain, mailbox_email, display_name, oauth_refresh_token, ms_tenant_id)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING *
                """,
                provider, domain, mailbox_email,
                (body.get("display_name") or "").strip() or None,
                (body.get("oauth_refresh_token") or "").strip() or None,
                (body.get("ms_tenant_id") or "").strip() or None,
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Could not create identity: {e}")
    return dict(row)


@router.patch("/email-identities/{identity_id}")
async def update_identity(identity_id: int, body: dict):
    fields, params = [], []
    for key in ("display_name", "status", "oauth_refresh_token", "ms_tenant_id"):
        if key in body:
            params.append(body[key])
            fields.append(f"{key} = ${len(params)}")
    if not fields:
        raise HTTPException(status_code=400, detail="no fields to update")
    if "status" in body and body["status"] not in ("warming", "active", "paused"):
        raise HTTPException(status_code=400, detail="status must be 'warming', 'active', or 'paused'")

    params.append(identity_id)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"UPDATE email_send_identities SET {', '.join(fields)}, updated_at = now() "
            f"WHERE id = ${len(params)} RETURNING *",
            *params,
        )
    if not row:
        raise HTTPException(status_code=404, detail="identity not found")
    return dict(row)


@router.delete("/email-identities/{identity_id}")
async def delete_identity(identity_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM email_send_identities WHERE id = $1", identity_id)
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="identity not found")
    return {"ok": True}


@router.post("/email-identities/{identity_id}/start-warmup")
async def start_warmup(identity_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        exists = await conn.fetchval("SELECT 1 FROM email_send_identities WHERE id = $1", identity_id)
    if not exists:
        raise HTTPException(status_code=404, detail="identity not found")
    await identity_warmup.start_warmup(identity_id)
    return {"ok": True}


@router.post("/email-identities/{identity_id}/pause")
async def pause_identity(identity_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE email_send_identities SET status = 'paused', updated_at = now() WHERE id = $1 RETURNING *",
            identity_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="identity not found")
    return dict(row)


@router.post("/email-identities/{identity_id}/activate")
async def activate_identity(identity_id: int):
    """Manually promote warming -> active, making this identity eligible
    for real lead sends (email_identities.pick_identity only selects
    status='active'). No auto-promotion — see identity_warmup.py's module
    docstring for why this stays a judgment call."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE email_send_identities SET status = 'active', activated_at = now(), updated_at = now() "
            "WHERE id = $1 RETURNING *",
            identity_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="identity not found")
    return dict(row)


@router.get("/email-identities/warmup-sequence")
async def warmup_sequence():
    """Feeds IdentityWarmupModal.jsx — one row per identity with ramp
    progress, same idea as GET /api/dialer/dm-followup-active but keyed by
    identity instead of contact."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT s.id, s.provider, s.mailbox_email, s.display_name, s.status AS identity_status,
                   w.status AS warmup_status, w.current_day, w.sent_today, w.replied_today,
                   w.last_sent_at, w.started_at, w.completed_at
            FROM email_send_identities s
            LEFT JOIN identity_warmup w ON w.identity_id = s.id
            ORDER BY s.created_at
            """
        )
    schedule = await identity_warmup.get_schedule()
    result = []
    for r in rows:
        row = dict(r)
        day = row["current_day"] or 1
        row["day_target"] = schedule[min(day, len(schedule)) - 1] if row["warmup_status"] else None
        row["total_days"] = len(schedule)
        result.append(row)
    return result
