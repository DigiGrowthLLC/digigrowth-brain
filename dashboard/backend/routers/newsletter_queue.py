"""
Newsletter send queue — view/edit endpoints for newsletter_send_queue.

Rows are inserted by _enqueue_newsletter() in approvals.py (one per
newsletter-flagged contact, on Approve) and consumed by
integrations.process_newsletter_queue() (the ~25/day gradual sender). This
router just lets Dylan see what's queued and make manual adjustments —
remove a prospect, edit a queued email, or add a prospect who wasn't on the
list when the draft was approved.
"""

import json
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from db import get_pool

router = APIRouter()

_API_BASE = os.environ.get("DASHBOARD_URL", "https://digigrowth-brain-production.up.railway.app")


def _row(r) -> dict:
    d = dict(r)
    for k in ("queued_at", "sent_at"):
        if d.get(k) is not None:
            d[k] = d[k].isoformat()
    return d


@router.get("/newsletter/sender-check")
async def sender_check():
    """Which Gmail account outbound sends actually authenticate as right now
    (bypasses the process-lifetime cache) — see integrations.get_sender_identity."""
    import integrations
    return integrations.get_sender_identity(force=True)


@router.get("/newsletter/personal-account-check")
async def personal_account_check():
    """Which Google account drives Calendar/Drive/inbox-search right now —
    see integrations.get_personal_identity."""
    import integrations
    return integrations.get_personal_identity(force=True)


@router.get("/newsletter/queue/state")
async def get_queue_state():
    pool = await get_pool()
    paused = await pool.fetchval("SELECT paused FROM newsletter_queue_state WHERE id = true")
    return {"paused": bool(paused)}


class UpdateQueueState(BaseModel):
    paused: bool


@router.patch("/newsletter/queue/state")
async def update_queue_state(body: UpdateQueueState):
    """Pause/resume the ~25/day gradual sender (integrations.process_newsletter_queue).
    Paused just stops new sends from going out — items stay queued and pick
    back up on resume, nothing is lost or re-personalized."""
    pool = await get_pool()
    await pool.execute("UPDATE newsletter_queue_state SET paused = $1 WHERE id = true", body.paused)
    return {"paused": body.paused}


@router.get("/newsletter/queue")
async def list_queue(
    status: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
):
    pool = await get_pool()
    conditions, params = [], []
    if status:
        params.append(status)
        conditions.append(f"q.status = ${len(params)}")
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    async with pool.acquire() as conn:
        total = await conn.fetchval(f"SELECT COUNT(*) FROM newsletter_send_queue q {where}", *params)
        data_params = params + [limit, offset]
        rows = await conn.fetch(
            f"""
            SELECT q.id, q.approval_id, q.contact_id, q.email, q.subject, q.status, q.error,
                   q.queued_at, q.sent_at, c.owner, c.business
            FROM newsletter_send_queue q
            LEFT JOIN contacts c ON c.id = q.contact_id
            {where}
            ORDER BY q.queued_at DESC
            LIMIT ${len(data_params) - 1} OFFSET ${len(data_params)}
            """,
            *data_params,
        )
    return {"total": total, "queue": [_row(r) for r in rows]}


@router.get("/newsletter/queue/{queue_id}")
async def get_queue_item(queue_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT q.*, c.owner, c.business FROM newsletter_send_queue q
               LEFT JOIN contacts c ON c.id = q.contact_id WHERE q.id = $1""",
            queue_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="queue item not found")
    return _row(row)


class UpdateQueueItem(BaseModel):
    email: Optional[str] = None
    subject: Optional[str] = None
    html: Optional[str] = None
    status: Optional[str] = None  # only "queued" (e.g. retry a failed send)


@router.patch("/newsletter/queue/{queue_id}")
async def update_queue_item(queue_id: int, body: UpdateQueueItem):
    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT status FROM newsletter_send_queue WHERE id = $1", queue_id)
        if not existing:
            raise HTTPException(status_code=404, detail="queue item not found")
        if existing["status"] == "sent":
            raise HTTPException(status_code=400, detail="already sent — can't edit a sent item")

        fields, params = [], []
        for col, val in (("email", body.email), ("subject", body.subject), ("html", body.html)):
            if val is not None:
                params.append(val)
                fields.append(f"{col} = ${len(params)}")
        if body.status is not None:
            if body.status != "queued":
                raise HTTPException(status_code=400, detail="status can only be reset to 'queued'")
            params.append("queued")
            fields.append(f"status = ${len(params)}")
            fields.append("error = NULL")
        if not fields:
            raise HTTPException(status_code=400, detail="no fields to update")

        params.append(queue_id)
        row = await conn.fetchrow(
            f"""UPDATE newsletter_send_queue SET {', '.join(fields)} WHERE id = ${len(params)}
                RETURNING *""",
            *params,
        )
    return _row(row)


@router.delete("/newsletter/queue/{queue_id}")
async def delete_queue_item(queue_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT status FROM newsletter_send_queue WHERE id = $1", queue_id)
        if not existing:
            raise HTTPException(status_code=404, detail="queue item not found")
        if existing["status"] == "sent":
            raise HTTPException(status_code=400, detail="already sent — can't remove a sent item")
        await conn.execute("DELETE FROM newsletter_send_queue WHERE id = $1", queue_id)
    return {"ok": True}


class AddQueueItem(BaseModel):
    contact_id: str


@router.post("/newsletter/queue")
async def add_queue_item(body: AddQueueItem):
    """Add a prospect to the queue using the most recently approved
    newsletter draft as the template — same personalization _enqueue_newsletter
    applies on Approve, just for one contact added after the fact."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        contact = await conn.fetchrow(
            "SELECT id, owner, business, email FROM contacts WHERE id = $1", body.contact_id
        )
        if not contact:
            raise HTTPException(status_code=404, detail="contact not found")
        if not contact["email"]:
            raise HTTPException(status_code=400, detail="contact has no email on file")

        already = await conn.fetchval(
            "SELECT 1 FROM newsletter_send_queue WHERE contact_id = $1 AND status = 'queued'",
            body.contact_id,
        )
        if already:
            raise HTTPException(status_code=400, detail="this contact already has a queued newsletter send")

        template = await conn.fetchrow(
            """SELECT id, payload FROM pending_approvals
               WHERE kind = 'newsletter' AND status = 'approved'
               ORDER BY decided_at DESC LIMIT 1"""
        )
        if not template:
            raise HTTPException(status_code=400, detail="no approved newsletter draft found to use as a template")

        payload = json.loads(template["payload"]) if isinstance(template["payload"], str) else template["payload"]
        subject = payload.get("subject", "")
        html = payload.get("html", "")

        first_name = (contact["owner"] or "there").split(" ")[0]
        business_name = contact["business"] or "your business"
        unsubscribe_link = f"{_API_BASE}/api/newsletter/unsubscribe/{contact['id']}"

        personalized_subject = subject.replace("{{first_name}}", first_name).replace("{{business_name}}", business_name)
        personalized_html = (
            html.replace("{{first_name}}", first_name)
                .replace("{{business_name}}", business_name)
                .replace("{{unsubscribe_link}}", unsubscribe_link)
        )

        row = await conn.fetchrow(
            """INSERT INTO newsletter_send_queue (approval_id, contact_id, email, subject, html)
               VALUES ($1, $2, $3, $4, $5) RETURNING *""",
            template["id"], contact["id"], contact["email"], personalized_subject, personalized_html,
        )
    return _row(row)
