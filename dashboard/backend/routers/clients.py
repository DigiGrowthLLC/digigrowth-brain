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

import r2_storage
from db import get_pool
from models import (
    ClientCreate, ClientUpdate, ClientLinkContact, OnboardingVideoCreate, OnboardingVideoUpdate,
    ActionItemCreate, ActionItemUpdate, ONBOARDING_SECTIONS,
    LaunchChecklistItemCreate, LaunchChecklistItemUpdate, LaunchChecklistStatusUpdate,
    SequenceStepUpdate, ClientRequestUpdate,
)

router = APIRouter()

# Default PT-oriented sequence copy — same values as db.py's one-time
# backfill migration, duplicated here (not imported from db.py) so a
# brand-new client gets seeded immediately at creation instead of waiting
# for the next app restart's migration pass.
_DEFAULT_SEQUENCE_STEPS = [
    ("appointment_reminder", 0, "24 Hour Reminder", "sms", None,
     "Hi {first_name}, this is a friendly reminder about your physical therapy appointment tomorrow, {date} at {time}, with {business}. Reply CONFIRM to confirm or call us if you need to reschedule."),
    ("appointment_reminder", 1, "Day-Of Reminder", "sms", None,
     "Hi {first_name}, just a reminder — your appointment at {business} is today at {time}. We look forward to seeing you!"),
    ("no_show", 0, "Touch 1 (SMS)", "sms", None,
     "Hi {first_name}, we missed you at your appointment today at {business}. No worries — these things happen! Reply here or give us a call to get you rescheduled so we can keep your recovery on track."),
    ("no_show", 1, "Touch 1 (Email)", "email", "We missed you today",
     "Hi {first_name},\n\nWe noticed you weren't able to make your physical therapy appointment today. Consistency is a big part of recovery, so we'd love to get you back on the schedule as soon as possible.\n\nReply to this email or give us a call whenever works for you.\n\nTalk soon,\n{business}"),
    ("cancellation", 0, "Touch 1 (SMS)", "sms", None,
     "Hi {first_name}, we've canceled your appointment as requested. Whenever you're ready to get back to feeling better, just reply here or give us a call to grab a new time."),
    ("cancellation", 1, "Touch 1 (Email)", "email", "Your appointment has been canceled",
     "Hi {first_name},\n\nThis confirms your upcoming appointment with {business} has been canceled.\n\nIf you'd like to reschedule, just reply to this email or call us — we're happy to find a time that works for you.\n\nTake care,\n{business}"),
]


async def _seed_default_sequences(conn, client_id: int) -> None:
    for sequence_key, step_order, label, channel, subject, body in _DEFAULT_SEQUENCE_STEPS:
        await conn.execute(
            "INSERT INTO client_sequence_steps (client_id, sequence_key, step_order, label, channel, subject, body) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7)",
            client_id, sequence_key, step_order, label, channel, subject, body,
        )

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
            INSERT INTO clients (name, contact_name, email, phone, notes, portal_token, is_test, calendly_url, booking_notification_enabled)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING *
            """,
            name, body.contact_name, body.email, body.phone, body.notes, token, body.is_test, body.calendly_url,
            body.booking_notification_enabled,
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
        await _seed_default_sequences(conn, row["id"])
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


# ---------------- Launch checklist (agency-run "To Do" — shared catalog + per-client status) ----------------
#
# Separate from the "Next Steps" action items above: those are onboarding
# steps the CLIENT completes themselves. This checklist is DigiGrowth's own
# launch-readiness tasks (set up the portal, email/SMS marketing, response
# AI, landing page, ad creatives, etc.) — the client just watches progress
# on their portal's "To Do" tab while the agency checks items off here,
# per-client, as the work actually gets done.

@router.get("/launch-checklist-items")
async def list_launch_checklist_items():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM launch_checklist_items ORDER BY phase, sort_order, id")
    return [dict(r) for r in rows]


@router.post("/launch-checklist-items")
async def create_launch_checklist_item(body: LaunchChecklistItemCreate):
    title = body.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="title required")
    if body.phase not in ("prelaunch", "post_launch"):
        raise HTTPException(status_code=400, detail="phase must be 'prelaunch' or 'post_launch'")
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO launch_checklist_items (title, description, phase, sort_order) "
            "VALUES ($1, $2, $3, $4) RETURNING *",
            title, body.description, body.phase, body.sort_order,
        )
    return dict(row)


@router.patch("/launch-checklist-items/{item_id}")
async def update_launch_checklist_item(item_id: int, body: LaunchChecklistItemUpdate):
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="no fields to update")
    if fields.get("phase") not in (None, "prelaunch", "post_launch"):
        raise HTTPException(status_code=400, detail="phase must be 'prelaunch' or 'post_launch'")
    pool = await get_pool()
    async with pool.acquire() as conn:
        set_clauses = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(fields))
        row = await conn.fetchrow(
            f"UPDATE launch_checklist_items SET {set_clauses} WHERE id = $1 RETURNING *",
            item_id, *fields.values(),
        )
    if not row:
        raise HTTPException(status_code=404, detail="Checklist item not found")
    return dict(row)


@router.delete("/launch-checklist-items/{item_id}")
async def delete_launch_checklist_item(item_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("DELETE FROM launch_checklist_items WHERE id = $1 RETURNING id", item_id)
    if not row:
        raise HTTPException(status_code=404, detail="Checklist item not found")
    return {"ok": True}


@router.get("/clients/{client_id}/launch-checklist")
async def get_client_launch_checklist(client_id: int):
    """Full catalog + this client's per-item completion status — what the
    ClientRow's launch-checklist toggle panel renders."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT li.id, li.title, li.description, li.phase, li.sort_order, s.completed_at
            FROM launch_checklist_items li
            LEFT JOIN client_launch_checklist_status s
                ON s.item_id = li.id AND s.client_id = $1
            WHERE li.active
            ORDER BY li.phase, li.sort_order, li.id
            """,
            client_id,
        )
    return [dict(r) for r in rows]


@router.put("/clients/{client_id}/launch-checklist/{item_id}")
async def set_client_launch_checklist_status(client_id: int, item_id: int, body: LaunchChecklistStatusUpdate):
    pool = await get_pool()
    async with pool.acquire() as conn:
        item = await conn.fetchrow("SELECT id FROM launch_checklist_items WHERE id = $1", item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Checklist item not found")
        if body.completed:
            row = await conn.fetchrow(
                """
                INSERT INTO client_launch_checklist_status (client_id, item_id, completed_at)
                VALUES ($1, $2, now())
                ON CONFLICT (client_id, item_id) DO UPDATE SET completed_at = now()
                RETURNING completed_at
                """,
                client_id, item_id,
            )
            completed_at = row["completed_at"]
        else:
            await conn.execute(
                "DELETE FROM client_launch_checklist_status WHERE client_id = $1 AND item_id = $2",
                client_id, item_id,
            )
            completed_at = None
    return {"id": item_id, "completed_at": completed_at}


# ---------------- Sequences (admin-editable per-client outreach copy) ----------------
#
# Appointment Reminder / No Show / Cancellation copy, shown read-only on the
# client portal's Sequences tab (routers/client_portal.py). Not wired to any
# real SMS/email send yet — this is content prep for when per-client
# messaging/emailing gets built. Seeded with PT-oriented defaults at client
# creation (create_client() above) and, for clients that pre-date this
# feature, by a one-time backfill in db.py.

@router.get("/clients/{client_id}/sequences")
async def list_client_sequences(client_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM client_sequence_steps WHERE client_id = $1 ORDER BY sequence_key, step_order, id",
            client_id,
        )
    return [dict(r) for r in rows]


@router.patch("/clients/{client_id}/sequences/{step_id}")
async def update_client_sequence_step(client_id: int, step_id: int, body: SequenceStepUpdate):
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="no fields to update")
    if fields.get("channel") not in (None, "sms", "email"):
        raise HTTPException(status_code=400, detail="channel must be 'sms' or 'email'")
    pool = await get_pool()
    async with pool.acquire() as conn:
        set_clauses = ", ".join(f"{k} = ${i+3}" for i, k in enumerate(fields))
        row = await conn.fetchrow(
            f"UPDATE client_sequence_steps SET {set_clauses}, updated_at = now() "
            f"WHERE id = $1 AND client_id = $2 RETURNING *",
            step_id, client_id, *fields.values(),
        )
    if not row:
        raise HTTPException(status_code=404, detail="Sequence step not found")
    return dict(row)


# ---------------- Client requests ("something I want fixed/done") ----------------

@router.get("/clients/{client_id}/requests")
async def list_client_requests(client_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM client_requests WHERE client_id = $1 ORDER BY created_at DESC",
            client_id,
        )
    return [dict(r) for r in rows]


@router.patch("/clients/{client_id}/requests/{request_id}")
async def update_client_request(client_id: int, request_id: int, body: ClientRequestUpdate):
    if body.status not in ("open", "done"):
        raise HTTPException(status_code=400, detail="status must be 'open' or 'done'")
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE client_requests SET status = $3, resolved_at = CASE WHEN $3 = 'done' THEN now() ELSE NULL END "
            "WHERE id = $1 AND client_id = $2 RETURNING *",
            request_id, client_id, body.status,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Request not found")
    return dict(row)


# ---------------- Client uploads (files -> Cloudflare R2, metadata only here) ----------------

@router.get("/clients/{client_id}/uploads")
async def list_client_uploads(client_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM client_uploads WHERE client_id = $1 ORDER BY uploaded_at DESC",
            client_id,
        )
    return [dict(r) for r in rows]


@router.get("/clients/{client_id}/uploads/{upload_id}/download")
async def get_client_upload_download_url(client_id: int, upload_id: int):
    """Returns a short-lived presigned R2 URL rather than proxying the file
    through this backend — same "Railway never touches the bytes" principle
    as the upload side."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT r2_key, file_name FROM client_uploads WHERE id = $1 AND client_id = $2",
            upload_id, client_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Upload not found")
    if not r2_storage.is_configured():
        raise HTTPException(status_code=503, detail="File storage isn't connected yet")
    return {"url": r2_storage.presign_get(row["r2_key"], row["file_name"])}


@router.delete("/clients/{client_id}/uploads/{upload_id}")
async def delete_client_upload(client_id: int, upload_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "DELETE FROM client_uploads WHERE id = $1 AND client_id = $2 RETURNING r2_key",
            upload_id, client_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Upload not found")
    if r2_storage.is_configured():
        try:
            r2_storage.delete_object(row["r2_key"])
        except Exception as e:
            print(f"[clients] failed to delete R2 object {row['r2_key']}: {e}")
    return {"ok": True}
    return {"id": item_id, "completed_at": completed_at}
