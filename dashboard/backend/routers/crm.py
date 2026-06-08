import uuid
from typing import Optional

from fastapi import APIRouter, Query, HTTPException
from db import get_pool
from models import Contact, ContactUpdate, NoteAdd, DispositionUpdate, VALID_STATUSES, DISPOSITION_TO_STATUS

router = APIRouter()


def _row_to_contact(row) -> dict:
    return dict(row)


@router.get("/contacts")
async def list_contacts(
    status: Optional[str] = Query(None),
    grade: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    newsletter: Optional[bool] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
):
    pool = await get_pool()
    conditions = []
    params = []

    if status and status != "all":
        params.append(status)
        conditions.append(f"status = ${len(params)}")
    if grade:
        params.append(grade.upper())
        conditions.append(f"grade = ${len(params)}")
    if newsletter is not None:
        params.append(newsletter)
        conditions.append(f"newsletter = ${len(params)}")
    if search:
        params.append(f"%{search}%")
        idx = len(params)
        conditions.append(
            f"(business ILIKE ${idx} OR owner ILIKE ${idx} OR phone ILIKE ${idx})"
        )

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params.extend([limit, offset])
    count_q = f"SELECT COUNT(*) FROM contacts {where}"
    data_q = (
        f"SELECT * FROM contacts {where} "
        f"ORDER BY updated_at DESC "
        f"LIMIT ${len(params)-1} OFFSET ${len(params)}"
    )

    async with pool.acquire() as conn:
        total = await conn.fetchval(count_q, *params[:-2])
        rows = await conn.fetch(data_q, *params)

    return {"total": total, "contacts": [dict(r) for r in rows]}


@router.get("/contacts/{contact_id}")
async def get_contact(contact_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM contacts WHERE id = $1", contact_id)
    if not row:
        raise HTTPException(status_code=404, detail="Contact not found")
    return dict(row)


@router.patch("/contacts/{contact_id}")
async def update_contact(contact_id: str, body: ContactUpdate):
    pool = await get_pool()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    if "status" in updates and updates["status"] not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status: {updates['status']}")

    set_parts = [f"{k} = ${i+2}" for i, k in enumerate(updates)]
    set_parts.append("updated_at = now()")
    sql = f"UPDATE contacts SET {', '.join(set_parts)} WHERE id = $1 RETURNING *"
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, contact_id, *updates.values())
    if not row:
        raise HTTPException(status_code=404, detail="Contact not found")
    return dict(row)


@router.post("/contacts/{contact_id}/note")
async def add_note(contact_id: str, body: NoteAdd):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE contacts
            SET notes = CASE WHEN notes IS NULL THEN $2 ELSE notes || E'\\n' || $2 END,
                updated_at = now()
            WHERE id = $1
            RETURNING id, notes
            """,
            contact_id, body.text,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Contact not found")
    return {"id": row["id"], "notes": row["notes"]}


@router.post("/contacts/{contact_id}/disposition")
async def log_disposition(contact_id: str, body: DispositionUpdate):
    pool = await get_pool()
    new_status = DISPOSITION_TO_STATUS.get(body.disposition, "dialer-lead")
    async with pool.acquire() as conn:
        async with conn.transaction():
            contact = await conn.fetchrow("SELECT id FROM contacts WHERE id = $1", contact_id)
            if not contact:
                raise HTTPException(status_code=404, detail="Contact not found")
            await conn.execute(
                """
                INSERT INTO call_logs (contact_id, duration_sec, disposition, notes)
                VALUES ($1, $2, $3, $4)
                """,
                contact_id, body.duration_sec, body.disposition, body.notes,
            )
            await conn.execute(
                """
                UPDATE contacts
                SET status = $2,
                    last_disposition = $3,
                    call_attempts = call_attempts + 1,
                    last_called_at = now(),
                    updated_at = now()
                WHERE id = $1
                """,
                contact_id, new_status, body.disposition,
            )
    return {"ok": True, "new_status": new_status}


@router.get("/contacts/{contact_id}/calls")
async def get_call_history(contact_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM call_logs WHERE contact_id = $1 ORDER BY started_at DESC",
            contact_id,
        )
    return [dict(r) for r in rows]


@router.post("/contacts")
async def create_contact(body: Contact):
    pool = await get_pool()
    contact_id = body.id or str(uuid.uuid4())
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO contacts
                (id, business, owner, phone, email, website, city, state,
                 grade, opener, status, notes, newsletter)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
            ON CONFLICT (phone) DO UPDATE SET
                business = EXCLUDED.business,
                owner = EXCLUDED.owner,
                email = EXCLUDED.email,
                grade = EXCLUDED.grade,
                opener = EXCLUDED.opener,
                updated_at = now()
            RETURNING *
            """,
            contact_id, body.business, body.owner, body.phone, body.email,
            body.website, body.city, body.state, body.grade, body.opener,
            body.status, body.notes, body.newsletter,
        )
    return dict(row)


@router.post("/contacts/import")
async def import_contacts(body: dict):
    rows = body.get("contacts", [])
    if not rows:
        raise HTTPException(status_code=400, detail="No contacts provided")

    pool = await get_pool()
    inserted = updated = skipped = 0

    async with pool.acquire() as conn:
        for c in rows:
            phone = (c.get("phone") or "").strip()
            if not phone:
                skipped += 1
                continue
            contact_id = str(uuid.uuid4())
            result = await conn.fetchrow(
                """
                INSERT INTO contacts
                    (id, business, owner, phone, email, website, city, state,
                     grade, opener, status, notes, newsletter)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
                ON CONFLICT (phone) DO UPDATE SET
                    business   = COALESCE(EXCLUDED.business,   contacts.business),
                    owner      = COALESCE(EXCLUDED.owner,      contacts.owner),
                    email      = COALESCE(EXCLUDED.email,      contacts.email),
                    grade      = COALESCE(EXCLUDED.grade,      contacts.grade),
                    opener     = COALESCE(EXCLUDED.opener,     contacts.opener),
                    updated_at = now()
                RETURNING (xmax = 0) AS was_inserted
                """,
                contact_id,
                (c.get("business") or "").strip() or None,
                (c.get("owner") or "").strip() or None,
                phone,
                (c.get("email") or "").strip() or None,
                (c.get("website") or "").strip() or None,
                (c.get("city") or "").strip() or None,
                (c.get("state") or "").strip() or None,
                (c.get("grade") or "").strip().upper() or None,
                (c.get("opener") or "").strip() or None,
                (c.get("status") or "new").strip() or "new",
                (c.get("notes") or "").strip() or None,
                bool(c.get("newsletter", False)),
            )
            if result["was_inserted"]:
                inserted += 1
            else:
                updated += 1

    return {"inserted": inserted, "updated": updated, "skipped": skipped}


@router.get("/stats/funnel")
async def funnel_stats():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT status, COUNT(*) as count FROM contacts GROUP BY status")
        total_calls = await conn.fetchval("SELECT COUNT(*) FROM call_logs")
        reached = await conn.fetchval(
            "SELECT COUNT(*) FROM call_logs WHERE disposition IN ('Appointment Booked','Follow Up','Send Info','SMS Handoff')"
        )
        booked = await conn.fetchval(
            "SELECT COUNT(*) FROM contacts WHERE status = 'appointment-booked'"
        )
        grade_rows = await conn.fetch("SELECT grade, COUNT(*) as count FROM contacts WHERE grade IS NOT NULL GROUP BY grade")
        newsletter_count = await conn.fetchval("SELECT COUNT(*) FROM contacts WHERE newsletter = true")

    status_counts = {r["status"]: r["count"] for r in rows}
    grade_counts = {r["grade"]: r["count"] for r in grade_rows}

    total = sum(status_counts.values())
    dialed = total_calls or 0
    reached_count = reached or 0

    return {
        "total_contacts": total,
        "by_status": status_counts,
        "by_grade": grade_counts,
        "funnel": {
            "qualified": total,
            "dialed": dialed,
            "reached": reached_count,
            "booked": booked or 0,
        },
        "newsletter_subscribers": newsletter_count or 0,
        "reach_rate": round(reached_count / dialed * 100, 1) if dialed else 0,
    }
