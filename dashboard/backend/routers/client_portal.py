"""
Public, client-facing portal endpoints — no HTTPBasic auth. Every route takes
an unguessable `token` path param that resolves to a client_id via
get_client_from_token(); no endpoint ever accepts client_id directly from the
request, so one client can never address another client's data. Same
"separate unauthenticated router + DB-scoped filter" shape as public_sops.py,
just with a per-request resolved scope instead of a static visibility column.

Stats are intentionally basic for now — real SMS/email totals scoped by
client_id, and an empty Facebook/Meta ads array (see meta_ads.py for the
integration that will eventually populate ad_campaign_stats). Not reusing
analytics.py's _sms_metrics/_email_metrics here: those functions are tuned
for the internal Analytics tab's campaign/stage funnel with a lot of
carefully-commented edge-case handling, and bolting a third scope dimension
onto them risked breaking that. This is a simpler, self-contained rollup
purpose-built for the portal's basic infrastructure pass.
"""
import uuid

from fastapi import APIRouter, HTTPException

from db import get_pool
from models import OnboardingSectionSave, ONBOARDING_SECTIONS
import cancel_sequence
import no_show_sequence
import onboarding_sequence

router = APIRouter(prefix="/portal-api")


def _pct(num, denom) -> float:
    if not denom:
        return 0.0
    return round(num / denom * 100, 1)


async def get_client_from_token(token: str) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM clients WHERE portal_token = $1 AND token_revoked_at IS NULL",
            token,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Invalid or revoked portal link")
    return dict(row)


@router.get("/{token}")
async def portal_home(token: str):
    client = await get_client_from_token(token)
    return {"id": client["id"], "name": client["name"], "status": client["status"]}


@router.get("/{token}/onboarding")
async def get_onboarding(token: str):
    client = await get_client_from_token(token)
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM client_onboarding_responses WHERE client_id = $1", client["id"]
        )
    by_section = {r["section"]: dict(r) for r in rows}
    return {
        "sections": ONBOARDING_SECTIONS,
        "responses": by_section,
        "progress": f"{len(by_section)}/{len(ONBOARDING_SECTIONS)}",
    }


@router.put("/{token}/onboarding/{section}")
async def save_onboarding_section(token: str, section: str, body: OnboardingSectionSave):
    if section not in ONBOARDING_SECTIONS:
        raise HTTPException(status_code=400, detail="Unknown onboarding section")
    client = await get_client_from_token(token)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO client_onboarding_responses (client_id, section, answers, completed_at)
            VALUES ($1, $2, $3, CASE WHEN $4 THEN now() ELSE NULL END)
            ON CONFLICT (client_id, section) DO UPDATE SET
                answers = EXCLUDED.answers,
                completed_at = CASE WHEN $4 THEN now() ELSE client_onboarding_responses.completed_at END,
                updated_at = now()
            RETURNING *
            """,
            client["id"], section, body.answers, body.completed,
        )
    return dict(row)


@router.get("/{token}/videos")
async def portal_videos(token: str):
    await get_client_from_token(token)
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, title, description, embed_url, sort_order FROM onboarding_videos "
            "WHERE active ORDER BY sort_order, id"
        )
    return [dict(r) for r in rows]


@router.get("/{token}/stats")
async def portal_stats(token: str):
    client = await get_client_from_token(token)
    pool = await get_pool()
    async with pool.acquire() as conn:
        sms_row = await conn.fetchrow(
            """
            SELECT
                COUNT(DISTINCT sc.id) AS conversations,
                COALESCE(SUM((sm.direction = 'outbound')::int), 0) AS sent,
                COALESCE(SUM((sm.direction = 'inbound')::int), 0) AS replies
            FROM sms_conversations sc
            LEFT JOIN sms_messages sm ON sm.contact_id = sc.contact_id
            WHERE sc.client_id = $1
            """,
            client["id"],
        )
        email_row = await conn.fetchrow(
            """
            SELECT
                COUNT(DISTINCT ec.id) AS conversations,
                COALESCE(SUM((em.direction = 'outbound')::int), 0) AS sent,
                COALESCE(SUM((em.direction = 'inbound')::int), 0) AS replies
            FROM email_conversations ec
            LEFT JOIN email_messages em ON em.contact_id = ec.contact_id
            WHERE ec.client_id = $1
            """,
            client["id"],
        )
        ad_rows = await conn.fetch(
            "SELECT * FROM ad_campaign_stats WHERE client_id = $1 AND platform = 'meta' "
            "ORDER BY stat_date DESC LIMIT 30",
            client["id"],
        )
        leads_total = await conn.fetchval(
            "SELECT count(*) FROM contacts WHERE client_id = $1", client["id"]
        )
        appt_row = await conn.fetchrow(
            """
            SELECT
                count(*) AS total,
                count(*) FILTER (WHERE ar.status = 'scheduled' AND ar.appointment_at > now()) AS upcoming,
                count(*) FILTER (WHERE ar.outcome_show = 'show') AS shows,
                count(*) FILTER (WHERE ar.outcome_show = 'no_show') AS no_shows,
                count(*) FILTER (WHERE ar.outcome_close = 'closed') AS closed,
                count(*) FILTER (WHERE ar.outcome_close = 'not_closed') AS not_closed
            FROM appointment_reminders ar
            JOIN contacts c ON c.id = ar.contact_id
            WHERE c.client_id = $1
            """,
            client["id"],
        )
    appt = dict(appt_row)
    return {
        "sms": dict(sms_row),
        "email": dict(email_row),
        "ads": {
            "platform": "meta",
            "status": "coming_soon",
            "days": [dict(r) for r in ad_rows],
        },
        "leads": {"total": leads_total},
        "appointments": {
            "total": appt["total"],
            "upcoming": appt["upcoming"],
            "shows": appt["shows"],
            "no_shows": appt["no_shows"],
            "show_rate": _pct(appt["shows"], appt["shows"] + appt["no_shows"]),
            "closed": appt["closed"],
            "not_closed": appt["not_closed"],
            "close_rate": _pct(appt["closed"], appt["closed"] + appt["not_closed"]),
        },
    }


# ---------------- Appointments (scoped via contacts.client_id) ----------------

@router.get("/{token}/appointments")
async def portal_appointments(token: str, status: str = "scheduled"):
    """Mirrors GET /api/appointment-reminders' contract (status=scheduled by
    default; 'all' returns everything) so the portal's Upcoming/Past/Canceled
    tabs can reuse the same client-side time-split as AppointmentsPanel.jsx."""
    client = await get_client_from_token(token)
    conditions = ["c.client_id = $1"]
    params = [client["id"]]
    if status != "all":
        params.append(status)
        conditions.append(f"ar.status = ${len(params)}")
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT ar.*, c.business, c.owner FROM appointment_reminders ar
            JOIN contacts c ON c.id = ar.contact_id
            WHERE {' AND '.join(conditions)}
            ORDER BY ar.appointment_at ASC
            """,
            *params,
        )
    return [dict(r) for r in rows]


@router.patch("/{token}/appointments/{appointment_id}")
async def portal_update_appointment_outcome(token: str, appointment_id: int, body: dict):
    """Client-facing outcome marking only (outcome_show/outcome_close) — no
    reschedule/cancel from the portal. Mirrors the outcome-only branch of
    routers/appointments.py's PATCH handler, including its side effects
    (No Show sequence touch 1, onboarding kickoff on Closed), scoped to
    appointments that actually belong to this client."""
    client = await get_client_from_token(token)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT ar.* FROM appointment_reminders ar
            JOIN contacts c ON c.id = ar.contact_id
            WHERE ar.id = $1 AND c.client_id = $2
            """,
            appointment_id, client["id"],
        )
    if not row:
        raise HTTPException(status_code=404, detail="Appointment not found")

    updates: dict = {}
    if "outcome_show" in body:
        value = body["outcome_show"]
        if value not in (None, "show", "no_show"):
            raise HTTPException(status_code=400, detail="outcome_show must be 'show', 'no_show', or null")
        updates["outcome_show"] = value
    if "outcome_close" in body:
        value = body["outcome_close"]
        if value not in (None, "closed", "not_closed"):
            raise HTTPException(status_code=400, detail="outcome_close must be 'closed', 'not_closed', or null")
        updates["outcome_close"] = value
    if not updates:
        return dict(row)

    set_clauses = [f"{k} = ${i+2}" for i, k in enumerate(updates)]
    params = [appointment_id, *updates.values()]
    if updates.get("outcome_show") == "no_show":
        set_clauses += [
            "outcome_show_at = now()",
            "no_show_touch1_sent_at = NULL", "no_show_touch2_sent_at = NULL",
            "no_show_touch3_sent_at = NULL", "no_show_touch4_sent_at = NULL",
            "no_show_sequence_stopped_at = NULL",
        ]
    elif "outcome_show" in updates:
        set_clauses += ["outcome_show_at = NULL"]
    if updates.get("outcome_close") == "closed":
        set_clauses += [
            "outcome_close_at = now()",
            "onboarding_kickoff_sent_at = NULL",
            "onboarding_followup_sent_at = NULL",
        ]
    elif "outcome_close" in updates:
        set_clauses += ["outcome_close_at = NULL"]

    pool = await get_pool()
    async with pool.acquire() as conn:
        updated = await conn.fetchrow(
            f"UPDATE appointment_reminders SET {', '.join(set_clauses)} WHERE id = $1 RETURNING *",
            *params,
        )

    if updates.get("outcome_show") == "no_show":
        try:
            await no_show_sequence.send_first_touch(dict(updated))
        except Exception as e:
            print(f"[client_portal] no-show touch 1 failed for {appointment_id}: {e}")
    if updates.get("outcome_close") == "closed":
        try:
            await onboarding_sequence.send_kickoff(dict(updated))
        except Exception as e:
            print(f"[client_portal] onboarding kickoff failed for {appointment_id}: {e}")

    return dict(updated)


# ---------------- Leads / CRM (scoped via contacts.client_id) ----------------

_LEAD_FIELDS = ("business", "owner", "phone", "email", "website", "city", "state", "notes")


@router.get("/{token}/leads")
async def portal_list_leads(token: str):
    client = await get_client_from_token(token)
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM contacts WHERE client_id = $1 ORDER BY created_at DESC",
            client["id"],
        )
    return [dict(r) for r in rows]


@router.post("/{token}/leads")
async def portal_create_lead(token: str, body: dict):
    client = await get_client_from_token(token)
    phone = (body.get("phone") or "").strip()
    if not phone:
        raise HTTPException(status_code=400, detail="phone is required")

    pool = await get_pool()
    async with pool.acquire() as conn:
        # contacts.phone is globally unique — never silently claim a lead
        # that already belongs to someone else (another client, or an
        # unattributed internal DigiGrowth lead) just because it shares a
        # phone number. Only update if it's already this client's own row.
        existing = await conn.fetchrow("SELECT client_id FROM contacts WHERE phone = $1", phone)
        if existing and existing["client_id"] != client["id"]:
            raise HTTPException(status_code=409, detail="A lead with this phone number already exists")

        row = await conn.fetchrow(
            """
            INSERT INTO contacts (id, business, owner, phone, email, website, city, state, notes, status, client_id)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,'new',$10)
            ON CONFLICT (phone) DO UPDATE SET
                business = COALESCE(EXCLUDED.business, contacts.business),
                owner    = COALESCE(EXCLUDED.owner, contacts.owner),
                email    = COALESCE(EXCLUDED.email, contacts.email),
                website  = COALESCE(EXCLUDED.website, contacts.website),
                city     = COALESCE(EXCLUDED.city, contacts.city),
                state    = COALESCE(EXCLUDED.state, contacts.state),
                notes    = COALESCE(EXCLUDED.notes, contacts.notes),
                updated_at = now()
            RETURNING *
            """,
            str(uuid.uuid4()),
            (body.get("business") or "").strip() or None,
            (body.get("owner") or "").strip() or None,
            phone,
            (body.get("email") or "").strip() or None,
            (body.get("website") or "").strip() or None,
            (body.get("city") or "").strip() or None,
            (body.get("state") or "").strip() or None,
            (body.get("notes") or "").strip() or None,
            client["id"],
        )
    return dict(row)


@router.post("/{token}/leads/import")
async def portal_import_leads(token: str, body: dict):
    """Bulk import — mirrors POST /api/contacts/import's contract (a JSON
    array the frontend produces by parsing a CSV client-side), scoped to
    this client and guarded against claiming another client's/DigiGrowth's
    existing lead on a phone collision (see portal_create_lead above)."""
    client = await get_client_from_token(token)
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
            existing = await conn.fetchrow("SELECT client_id FROM contacts WHERE phone = $1", phone)
            if existing and existing["client_id"] != client["id"]:
                skipped += 1
                continue

            result = await conn.fetchrow(
                """
                INSERT INTO contacts (id, business, owner, phone, email, website, city, state, notes, status, client_id)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,'new',$10)
                ON CONFLICT (phone) DO UPDATE SET
                    business = COALESCE(EXCLUDED.business, contacts.business),
                    owner    = COALESCE(EXCLUDED.owner, contacts.owner),
                    email    = COALESCE(EXCLUDED.email, contacts.email),
                    website  = COALESCE(EXCLUDED.website, contacts.website),
                    city     = COALESCE(EXCLUDED.city, contacts.city),
                    state    = COALESCE(EXCLUDED.state, contacts.state),
                    notes    = COALESCE(EXCLUDED.notes, contacts.notes),
                    updated_at = now()
                RETURNING (xmax = 0) AS was_inserted
                """,
                str(uuid.uuid4()),
                (c.get("business") or "").strip() or None,
                (c.get("owner") or "").strip() or None,
                phone,
                (c.get("email") or "").strip() or None,
                (c.get("website") or "").strip() or None,
                (c.get("city") or "").strip() or None,
                (c.get("state") or "").strip() or None,
                (c.get("notes") or "").strip() or None,
                client["id"],
            )
            if result["was_inserted"]:
                inserted += 1
            else:
                updated += 1

    return {"inserted": inserted, "updated": updated, "skipped": skipped}
