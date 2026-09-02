import re
import uuid
from typing import Optional

from fastapi import APIRouter, Query, HTTPException
import email_handoff_sequence
from db import get_pool
from models import (
    Contact, ContactUpdate, NoteAdd, DispositionUpdate, BulkAction, TagAssign,
    VALID_STATUSES, DISPOSITION_TO_STATUS, CustomStatusCreate, CustomStatusUpdate,
)
from routers import sms as sms_router

router = APIRouter()

HANDOFF_STATUS = "sms-handoff"
EMAIL_HANDOFF_TAG = "email-handoff"
NEWSLETTER_TAG = "Newsletter"
NEWSLETTER_TAG_DISPOSITIONS = {"Follow Up 30 Day", "Follow Up 90 Day"}


async def _custom_status_keys(conn) -> set:
    rows = await conn.fetch("SELECT key FROM crm_custom_statuses")
    return {r["key"] for r in rows}


async def _is_valid_status(conn, status: str) -> bool:
    """Built-in statuses (VALID_STATUSES) drive real automated behavior —
    dialer eligibility, no-show/cancel sequences, DISPOSITION_TO_STATUS —
    so that set stays fixed in code. Custom statuses (crm_custom_statuses)
    are purely user-defined pipeline stages for manual organization: never
    auto-assigned by the dialer/disposition system, just a status value a
    contact can be set to and filtered/grouped by in the CRM."""
    if status in VALID_STATUSES:
        return True
    return status in await _custom_status_keys(conn)


def _same_business(a: Optional[str], b: Optional[str]) -> bool:
    """Loose match on business name, ignoring case/punctuation — different
    scrapes of the same lead often vary in formatting (e.g. "Flourish
    Physical Therapy LLC" vs "Flourish Physical Therapy"), so containment
    counts as a match, not just exact equality. An empty name on either side
    is treated as "no conflict" (can't tell), not a match. Short names (<4
    normalized chars) skip the containment check so e.g. "PT" doesn't
    trivially match everything."""
    na = re.sub(r"[^a-z0-9]", "", (a or "").lower())
    nb = re.sub(r"[^a-z0-9]", "", (b or "").lower())
    if not na or not nb:
        return True
    if na == nb:
        return True
    if len(na) >= 4 and len(nb) >= 4 and (na in nb or nb in na):
        return True
    return False


async def _fire_handoff(contact: dict):
    """Fire the one-time SMS opener; swallow errors so a Twilio hiccup never breaks the caller's request."""
    try:
        await sms_router.send_opening_message(contact)
    except Exception as e:
        print(f"sms-handoff opener failed for {contact.get('phone')}: {e}")


async def _fire_email_handoff(contact: dict):
    """Fire the one-time email-handoff opener (tag == EMAIL_HANDOFF_TAG);
    swallow errors so a Gmail hiccup never breaks the caller's request."""
    try:
        await email_handoff_sequence.send_handoff_email(contact)
    except Exception as e:
        print(f"email-handoff opener failed for {contact.get('email')}: {e}")


@router.get("/contacts")
async def list_contacts(
    status: Optional[str] = Query(None),
    grade: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    newsletter: Optional[bool] = Query(None),
    tag: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
):
    pool = await get_pool()
    # Contacts owned by a client's own portal (client_id set, not the
    # anchor) belong to that client's own Leads tab, not DigiGrowth's
    # internal CRM — exclude them here so a client's lead-gen doesn't show
    # up mixed into Dylan's own list with no distinction. The anchor
    # contact (client_id set but is_client_anchor=true) is exempt: that's
    # Dylan's own sales-pipeline contact for that business.
    conditions = ["(client_id IS NULL OR is_client_anchor)"]
    params = []

    if status and status != "all":
        params.append(status)
        conditions.append(f"status = ${len(params)}")
    if grade:
        params.append(grade.upper())
        conditions.append(f"grade = ${len(params)}")
    if tag:
        params.append(tag)
        conditions.append(f"${len(params)} = ANY(tags)")
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

    set_parts = [f"{k} = ${i+2}" for i, k in enumerate(updates)]
    set_parts.append("updated_at = now()")
    sql = f"UPDATE contacts SET {', '.join(set_parts)} WHERE id = $1 RETURNING *"
    async with pool.acquire() as conn:
        if "status" in updates and not await _is_valid_status(conn, updates["status"]):
            raise HTTPException(status_code=400, detail=f"Invalid status: {updates['status']}")
        prev = await conn.fetchrow("SELECT status FROM contacts WHERE id = $1", contact_id)
        row = await conn.fetchrow(sql, contact_id, *updates.values())
        if not row:
            raise HTTPException(status_code=404, detail="Contact not found")
        # Re-entering the dialer queue: only clear follow_up_at (the cooldown
        # that would otherwise keep it out of the eligible-leads query) —
        # call_attempts/last_called_at are call history and must survive
        # being re-added to the queue, not reset to look like a fresh lead.
        if updates.get("status") == "dialer-lead":
            try:
                await conn.execute(
                    "UPDATE contacts SET follow_up_at = NULL WHERE id = $1",
                    contact_id,
                )
                row = await conn.fetchrow("SELECT * FROM contacts WHERE id = $1", contact_id)
            except Exception:
                pass

    if updates.get("status") == HANDOFF_STATUS and (not prev or prev["status"] != HANDOFF_STATUS):
        await _fire_handoff(dict(row))

    return dict(row)


@router.delete("/contacts/{contact_id}")
async def delete_contact(contact_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM contacts WHERE id = $1", contact_id)
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Contact not found")
    return {"ok": True}


@router.post("/contacts/bulk")
async def bulk_action(body: BulkAction):
    pool = await get_pool()

    async with pool.acquire() as conn:
        if body.select_all:
            conditions, params = [], []
            if body.filter_status and body.filter_status != "all":
                params.append(body.filter_status)
                conditions.append(f"status = ${len(params)}")
            if body.filter_search:
                params.append(f"%{body.filter_search}%")
                idx = len(params)
                conditions.append(f"(business ILIKE ${idx} OR owner ILIKE ${idx} OR phone ILIKE ${idx})")
            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            ids = [r["id"] for r in await conn.fetch(f"SELECT id FROM contacts {where}", *params)]
        else:
            ids = body.ids or []

        if not ids:
            return {"ok": True, "affected": 0}

        if body.action == "delete":
            result = await conn.execute("DELETE FROM contacts WHERE id = ANY($1::text[])", ids)
            affected = int(result.split()[-1])

        elif body.action == "add_tag":
            if not body.value:
                raise HTTPException(status_code=400, detail="value required for add_tag")
            rows = await conn.fetch(
                "UPDATE contacts SET tags = array_append(tags, $1), updated_at = now() "
                "WHERE id = ANY($2::text[]) AND NOT ($1 = ANY(tags)) "
                "RETURNING id, email, owner, business",
                body.value, ids,
            )
            affected = len(rows)
            if body.value == EMAIL_HANDOFF_TAG:
                for r in rows:
                    await _fire_email_handoff(dict(r))

        elif body.action == "remove_tag":
            if not body.value:
                raise HTTPException(status_code=400, detail="value required for remove_tag")
            result = await conn.execute(
                "UPDATE contacts SET tags = array_remove(tags, $1), updated_at = now() "
                "WHERE id = ANY($2::text[])",
                body.value, ids,
            )
            affected = int(result.split()[-1])

        elif body.action == "set_status":
            if not await _is_valid_status(conn, body.value):
                raise HTTPException(status_code=400, detail=f"Invalid status: {body.value}")
            rows = await conn.fetch(
                """
                UPDATE contacts SET status = $1, updated_at = now()
                WHERE id = ANY($2::text[]) AND status IS DISTINCT FROM $1
                RETURNING id, phone, owner
                """,
                body.value, ids,
            )
            affected = len(rows)
            if body.value == HANDOFF_STATUS:
                for r in rows:
                    await _fire_handoff(dict(r))

        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {body.action}")

    return {"ok": True, "affected": affected}


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


@router.post("/contacts/{contact_id}/tags")
async def add_contact_tag(contact_id: str, body: TagAssign):
    tag = body.tag.strip()
    if not tag:
        raise HTTPException(status_code=400, detail="tag required")
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE contacts SET tags = array_append(tags, $2), updated_at = now() "
            "WHERE id = $1 AND NOT ($2 = ANY(tags)) RETURNING *",
            contact_id, tag,
        )
        newly_added = row is not None
        if not row:
            row = await conn.fetchrow("SELECT * FROM contacts WHERE id = $1", contact_id)
    if not row:
        raise HTTPException(status_code=404, detail="Contact not found")
    if newly_added and tag == EMAIL_HANDOFF_TAG:
        await _fire_email_handoff(dict(row))
    return dict(row)


@router.delete("/contacts/{contact_id}/tags/{tag}")
async def remove_contact_tag(contact_id: str, tag: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE contacts SET tags = array_remove(tags, $2), updated_at = now() "
            "WHERE id = $1 RETURNING *",
            contact_id, tag,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Contact not found")
    return dict(row)


@router.post("/contacts/{contact_id}/disposition")
async def log_disposition(contact_id: str, body: DispositionUpdate):
    pool = await get_pool()
    new_status = DISPOSITION_TO_STATUS.get(body.disposition, "dialer-lead")
    async with pool.acquire() as conn:
        async with conn.transaction():
            contact = await conn.fetchrow("SELECT id, phone, owner FROM contacts WHERE id = $1", contact_id)
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
            # Follow Up 30/90 Day: opt the prospect into the newsletter.
            # Appointment Booked (once it lands them in appointment-booked
            # status): opt them back out — they're through the funnel.
            if body.disposition in NEWSLETTER_TAG_DISPOSITIONS:
                await conn.execute(
                    "UPDATE contacts SET tags = array_append(tags, $2) "
                    "WHERE id = $1 AND NOT ($2 = ANY(tags))",
                    contact_id, NEWSLETTER_TAG,
                )
            elif body.disposition == "Appointment Booked" and new_status == "appointment-booked":
                await conn.execute(
                    "UPDATE contacts SET tags = array_remove(tags, $2) WHERE id = $1",
                    contact_id, NEWSLETTER_TAG,
                )

    if new_status == HANDOFF_STATUS:
        await _fire_handoff(dict(contact))

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
    incoming_business = (body.business or "").strip() or None
    async with pool.acquire() as conn:
        # Two genuinely different businesses can share a phone number (a
        # franchise/shared front-desk line is the common case — see MovementX,
        # a multi-location PT brand). contacts.phone is UNIQUE, so without
        # this check a second lead's push would silently overwrite the first
        # lead's business/owner via ON CONFLICT — including after that first
        # lead already got a personalized SMS sent under its own name. Never
        # clobber a different business's identity; keep whichever lead is
        # already on record.
        existing = await conn.fetchrow("SELECT * FROM contacts WHERE phone = $1", body.phone)
        if existing and not _same_business(existing["business"], incoming_business):
            print(f"[contacts] phone conflict on {body.phone}: keeping "
                  f"'{existing['business']}', skipping incoming '{incoming_business}'", flush=True)
            return dict(existing)

        row = await conn.fetchrow(
            """
            INSERT INTO contacts
                (id, business, owner, phone, email, website, city, state,
                 grade, opener, status, notes, newsletter)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
            ON CONFLICT (phone) DO UPDATE SET
                business = COALESCE(EXCLUDED.business, contacts.business),
                owner = COALESCE(EXCLUDED.owner, contacts.owner),
                email = COALESCE(EXCLUDED.email, contacts.email),
                grade = COALESCE(EXCLUDED.grade, contacts.grade),
                opener = COALESCE(EXCLUDED.opener, contacts.opener),
                updated_at = now()
            RETURNING *, (xmax = 0) AS was_inserted
            """,
            contact_id,
            incoming_business,
            (body.owner or "").strip() or None,
            body.phone,
            (body.email or "").strip() or None,
            body.website, body.city, body.state,
            (body.grade or "").strip().upper() or None,
            (body.opener or "").strip() or None,
            body.status, body.notes, body.newsletter,
        )

    result = dict(row)
    was_inserted = result.pop("was_inserted")
    # Status is only ever set on insert here (conflict path doesn't touch status),
    # so a fresh sms-handoff row always means a lead that just needs its opener.
    if was_inserted and result.get("status") == HANDOFF_STATUS:
        await _fire_handoff(result)

    return result


@router.post("/contacts/import")
async def import_contacts(body: dict):
    rows = body.get("contacts", [])
    if not rows:
        raise HTTPException(status_code=400, detail="No contacts provided")

    default_status = (body.get("status") or "").strip() or None
    import_tags = [t.strip() for t in (body.get("tags") or []) if t and t.strip()]

    pool = await get_pool()
    inserted = updated = skipped = 0

    async with pool.acquire() as conn:
        if default_status and not await _is_valid_status(conn, default_status):
            raise HTTPException(status_code=400, detail=f"Invalid status: {default_status}")
        for c in rows:
            phone = (c.get("phone") or "").strip()
            if not phone:
                skipped += 1
                continue
            incoming_business = (c.get("business") or "").strip() or None

            # Same phone-collision guard as create_contact() — don't let a
            # different business silently overwrite an existing lead's
            # identity via ON CONFLICT just because they share a phone number.
            existing = await conn.fetchrow("SELECT business FROM contacts WHERE phone = $1", phone)
            if existing and not _same_business(existing["business"], incoming_business):
                print(f"[contacts/import] phone conflict on {phone}: keeping "
                      f"'{existing['business']}', skipping incoming '{incoming_business}'", flush=True)
                skipped += 1
                continue

            contact_id = str(uuid.uuid4())
            row_status = default_status or (c.get("status") or "new").strip() or "new"
            result = await conn.fetchrow(
                """
                INSERT INTO contacts
                    (id, business, owner, phone, email, website, city, state,
                     grade, opener, status, notes, newsletter, tags)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
                ON CONFLICT (phone) DO UPDATE SET
                    business   = COALESCE(EXCLUDED.business,   contacts.business),
                    owner      = COALESCE(EXCLUDED.owner,      contacts.owner),
                    email      = COALESCE(EXCLUDED.email,      contacts.email),
                    grade      = COALESCE(EXCLUDED.grade,      contacts.grade),
                    opener     = COALESCE(EXCLUDED.opener,     contacts.opener),
                    tags       = ARRAY(SELECT DISTINCT unnest(contacts.tags || EXCLUDED.tags)),
                    updated_at = now()
                RETURNING id, (xmax = 0) AS was_inserted
                """,
                contact_id,
                incoming_business,
                (c.get("owner") or "").strip() or None,
                phone,
                (c.get("email") or "").strip() or None,
                (c.get("website") or "").strip() or None,
                (c.get("city") or "").strip() or None,
                (c.get("state") or "").strip() or None,
                (c.get("grade") or "").strip().upper() or None,
                (c.get("opener") or "").strip() or None,
                row_status,
                (c.get("notes") or "").strip() or None,
                bool(c.get("newsletter", False)),
                import_tags,
            )
            if result["was_inserted"]:
                inserted += 1
                if row_status == HANDOFF_STATUS:
                    await _fire_handoff({"phone": phone, "owner": (c.get("owner") or "").strip()})
            else:
                updated += 1

    return {"inserted": inserted, "updated": updated, "skipped": skipped}


# ---------------- Custom CRM statuses ----------------
#
# Built-in statuses (VALID_STATUSES/DISPOSITION_TO_STATUS in models.py)
# drive real automated behavior — dialer queue eligibility, no-show/
# cancel sequences — and stay fixed in code. These are purely user-
# defined pipeline stages for manual organization: a contact can be set
# to one, filtered/grouped by it in the CRM, but nothing in the dialer
# or disposition system ever assigns one automatically.

_KEY_RE = re.compile(r"[^a-z0-9]+")


def _slugify_status_key(raw: str) -> str:
    return _KEY_RE.sub("-", raw.strip().lower()).strip("-")


@router.get("/crm/custom-statuses")
async def list_custom_statuses():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM crm_custom_statuses ORDER BY sort_order, id")
    return [dict(r) for r in rows]


@router.post("/crm/custom-statuses")
async def create_custom_status(body: CustomStatusCreate):
    label = body.label.strip()
    if not label:
        raise HTTPException(status_code=400, detail="label required")
    key = _slugify_status_key(body.key or label)
    if not key:
        raise HTTPException(status_code=400, detail="key required")
    if key in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"'{key}' is a built-in status and can't be redefined")
    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT id FROM crm_custom_statuses WHERE key = $1", key)
        if existing:
            raise HTTPException(status_code=409, detail=f"Status '{key}' already exists")
        max_sort = await conn.fetchval("SELECT COALESCE(MAX(sort_order), -1) FROM crm_custom_statuses")
        row = await conn.fetchrow(
            "INSERT INTO crm_custom_statuses (key, label, color, sort_order) "
            "VALUES ($1, $2, $3, $4) RETURNING *",
            key, label, body.color or "#3a7bd5", max_sort + 1,
        )
    return dict(row)


@router.patch("/crm/custom-statuses/{status_id}")
async def update_custom_status(status_id: int, body: CustomStatusUpdate):
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="no fields to update")
    pool = await get_pool()
    async with pool.acquire() as conn:
        set_clauses = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(fields))
        row = await conn.fetchrow(
            f"UPDATE crm_custom_statuses SET {set_clauses} WHERE id = $1 RETURNING *",
            status_id, *fields.values(),
        )
    if not row:
        raise HTTPException(status_code=404, detail="Status not found")
    return dict(row)


@router.delete("/crm/custom-statuses/{status_id}")
async def delete_custom_status(status_id: int):
    """Contacts currently on this status keep their status string as-is
    (not reset to 'new') — it just stops appearing as a selectable option
    going forward. Matches how deleting a tag/onboarding video doesn't
    retroactively touch rows that already reference it."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("DELETE FROM crm_custom_statuses WHERE id = $1 RETURNING id", status_id)
    if not row:
        raise HTTPException(status_code=404, detail="Status not found")
    return {"ok": True}
