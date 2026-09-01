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
import json
import uuid

from fastapi import APIRouter, HTTPException

from db import get_pool
from models import OnboardingSectionSave, ONBOARDING_SECTIONS, ActionItemComplete
import cancel_sequence
import no_show_sequence
import onboarding_sequence

router = APIRouter(prefix="/portal-api")


def _decode_response_row(r) -> dict:
    """asyncpg has no JSONB codec registered on this pool (matches the rest
    of the codebase, e.g. sms.py/agents.py — see their json.loads(row[...])
    calls), so a JSONB column comes back as a raw JSON string, not a dict."""
    d = dict(r)
    d["answers"] = json.loads(d["answers"]) if isinstance(d["answers"], str) else d["answers"]
    return d


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
    by_section = {r["section"]: _decode_response_row(r) for r in rows}
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
            client["id"], section, json.dumps(body.answers), body.completed,
        )
    return _decode_response_row(row)


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


@router.get("/{token}/action-items")
async def portal_action_items(token: str):
    client = await get_client_from_token(token)
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT ai.id, ai.title, ai.description, ai.link_tab, ai.link_url, ai.sort_order, c.completed_at
            FROM onboarding_action_items ai
            LEFT JOIN client_action_item_completions c
                ON c.action_item_id = ai.id AND c.client_id = $1
            WHERE ai.active
            ORDER BY ai.sort_order, ai.id
            """,
            client["id"],
        )
    return [dict(r) for r in rows]


@router.put("/{token}/action-items/{item_id}")
async def portal_set_action_item_complete(token: str, item_id: int, body: ActionItemComplete):
    client = await get_client_from_token(token)
    pool = await get_pool()
    async with pool.acquire() as conn:
        item = await conn.fetchrow("SELECT id FROM onboarding_action_items WHERE id = $1", item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Action item not found")
        if body.completed:
            row = await conn.fetchrow(
                """
                INSERT INTO client_action_item_completions (client_id, action_item_id)
                VALUES ($1, $2)
                ON CONFLICT (client_id, action_item_id) DO UPDATE SET completed_at = client_action_item_completions.completed_at
                RETURNING completed_at
                """,
                client["id"], item_id,
            )
            completed_at = row["completed_at"]
        else:
            await conn.execute(
                "DELETE FROM client_action_item_completions WHERE client_id = $1 AND action_item_id = $2",
                client["id"], item_id,
            )
            completed_at = None
    return {"id": item_id, "completed_at": completed_at}


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


# ---------------- Inbox (scoped via contacts/sms_conversations/email_conversations.client_id) ----------------
#
# Read side (list + thread + mark-read) is fully real, scoped the same way as
# every other portal endpoint. Sending is intentionally a stub for now — no
# client has their own Twilio number or email inbox connected yet, so a real
# send here would go out through DigiGrowth's own shared Twilio/Gmail
# credentials "as" the client, which is wrong the moment a second client
# exists and unsafe even for the first. portal_send_message below validates
# and responds, but never actually calls integrations.gmail_send_reply or a
# Twilio send — that wiring is future work, once per-client channel
# credentials exist (see meta_ads.py for the same "stub the parts that need
# real per-client credentials, build the rest now" shape).

@router.get("/{token}/inbox")
async def portal_inbox_list(token: str):
    client = await get_client_from_token(token)
    pool = await get_pool()
    async with pool.acquire() as conn:
        sms_rows = await conn.fetch(
            """
            SELECT c.id AS contact_id, c.business, c.owner, c.phone, c.email,
                   sc.updated_at,
                   (SELECT sm.body FROM sms_messages sm WHERE sm.contact_id = c.id
                        ORDER BY sm.sent_at DESC LIMIT 1) AS last_message,
                   (SELECT sm.sent_at FROM sms_messages sm WHERE sm.contact_id = c.id
                        ORDER BY sm.sent_at DESC LIMIT 1) AS last_message_at,
                   EXISTS(
                       SELECT 1 FROM sms_messages sm WHERE sm.contact_id = c.id
                       AND sm.direction = 'inbound'
                       AND sm.sent_at > COALESCE(sc.last_read_at, '-infinity'::timestamptz)
                   ) AS unread
            FROM sms_conversations sc
            JOIN contacts c ON c.id = sc.contact_id
            WHERE sc.client_id = $1
            """,
            client["id"],
        )
        email_rows = await conn.fetch(
            """
            SELECT c.id AS contact_id, c.business, c.owner, c.phone, c.email,
                   ec.updated_at,
                   (SELECT em.body FROM email_messages em WHERE em.contact_id = c.id
                        ORDER BY em.sent_at DESC LIMIT 1) AS last_message,
                   (SELECT em.sent_at FROM email_messages em WHERE em.contact_id = c.id
                        ORDER BY em.sent_at DESC LIMIT 1) AS last_message_at,
                   EXISTS(
                       SELECT 1 FROM email_messages em WHERE em.contact_id = c.id
                       AND em.direction = 'inbound'
                       AND em.sent_at > COALESCE(ec.last_read_at, '-infinity'::timestamptz)
                   ) AS unread
            FROM email_conversations ec
            JOIN contacts c ON c.id = ec.contact_id
            WHERE ec.client_id = $1
            """,
            client["id"],
        )

    by_contact: dict = {}
    for rows, channel in ((sms_rows, "sms"), (email_rows, "email")):
        for r in rows:
            d = dict(r)
            cid = d["contact_id"]
            entry = by_contact.setdefault(cid, {
                "contact_id": cid, "business": d["business"], "owner": d["owner"],
                "phone": d["phone"], "email": d["email"],
                "channels": [], "last_message": None, "last_message_at": None, "unread": False,
            })
            entry["channels"].append(channel)
            entry["unread"] = entry["unread"] or d["unread"]
            if d["last_message_at"] and (
                entry["last_message_at"] is None or d["last_message_at"] > entry["last_message_at"]
            ):
                entry["last_message"] = d["last_message"]
                entry["last_message_at"] = d["last_message_at"]

    return sorted(by_contact.values(), key=lambda e: e["last_message_at"] or "", reverse=True)


@router.get("/{token}/inbox/{contact_id}")
async def portal_inbox_thread(token: str, contact_id: str):
    client = await get_client_from_token(token)
    pool = await get_pool()
    async with pool.acquire() as conn:
        contact = await conn.fetchrow(
            "SELECT id, business, owner, phone, email FROM contacts WHERE id = $1 AND client_id = $2",
            contact_id, client["id"],
        )
        if not contact:
            raise HTTPException(status_code=404, detail="Conversation not found")

        sms_msgs = await conn.fetch(
            "SELECT direction, body, sent_at FROM sms_messages WHERE contact_id = $1 ORDER BY sent_at",
            contact_id,
        )
        email_msgs = await conn.fetch(
            "SELECT direction, body, subject, sent_at FROM email_messages WHERE contact_id = $1 ORDER BY sent_at",
            contact_id,
        )
        await conn.execute(
            "UPDATE sms_conversations SET last_read_at = now() WHERE contact_id = $1 AND client_id = $2",
            contact_id, client["id"],
        )
        await conn.execute(
            "UPDATE email_conversations SET last_read_at = now() WHERE contact_id = $1 AND client_id = $2",
            contact_id, client["id"],
        )

    messages = (
        [{"channel": "sms", "direction": m["direction"], "body": m["body"], "subject": None, "sent_at": m["sent_at"]} for m in sms_msgs]
        + [{"channel": "email", "direction": m["direction"], "body": m["body"], "subject": m["subject"], "sent_at": m["sent_at"]} for m in email_msgs]
    )
    messages.sort(key=lambda m: m["sent_at"])

    return {"contact": dict(contact), "messages": messages}


@router.post("/{token}/inbox/{contact_id}/send")
async def portal_send_message(token: str, contact_id: str, body: dict):
    client = await get_client_from_token(token)
    pool = await get_pool()
    async with pool.acquire() as conn:
        contact = await conn.fetchrow(
            "SELECT id FROM contacts WHERE id = $1 AND client_id = $2", contact_id, client["id"]
        )
    if not contact:
        raise HTTPException(status_code=404, detail="Conversation not found")

    channel = body.get("channel")
    if channel not in ("sms", "email"):
        raise HTTPException(status_code=400, detail="channel must be 'sms' or 'email'")

    # Deliberately does not send — see module note above. Returns 200 with
    # ok:false so the frontend shows this as an expected state, not an error.
    return {
        "ok": False,
        "status": "not_connected",
        "detail": "Your SMS/email account isn't connected yet — DigiGrowth is setting this up and will notify you once replies can be sent from here.",
    }
