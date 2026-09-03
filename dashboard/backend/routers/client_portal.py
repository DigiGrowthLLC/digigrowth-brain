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
import asyncio
import html
import json
import re
import uuid
from typing import Optional

import asyncpg
from fastapi import APIRouter, HTTPException

from db import get_pool
from models import OnboardingSectionSave, ONBOARDING_SECTIONS, ActionItemComplete, TagAssign
import cancel_sequence
import integrations
import no_show_sequence
import onboarding_sequence
from routers import dialer as dialer_router
from routers import appointments as appointments_router
from timezone_lookup import US_TIMEZONES

router = APIRouter(prefix="/portal-api")

# Shared "All Time / Month / Week / Today" bucket vocabulary — same string
# values across the period selector (portal_stats) and the inbox time
# filter (portal_inbox_list), mirroring the internal OS's two closest
# equivalents (AnalyticsPanel's numeric-days PeriodToggle and InboxPanel's
# string-bucket `since` filter) but unified into one scheme here since the
# client portal only needs one. "all" means no filter — not a key below.
_PERIOD_INTERVAL = {"today": "1 day", "week": "7 days", "month": "30 days"}


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


_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str | None) -> str:
    """Some outbound emails are composed as full HTML (gmail_send_html /
    the tracked-outreach wrapper in integrations.py's _wrap_outreach_html)
    and email_messages.body stores exactly what went out — showing that
    raw markup (`<div style="max-width:600px;...`) straight in the portal
    inbox is unreadable. Plain-text SMS bodies pass through unchanged
    (no tags to strip), so this is safe to apply universally rather than
    branching on channel."""
    if not text:
        return text
    stripped = _HTML_TAG_RE.sub(" ", text)
    stripped = html.unescape(stripped)
    return re.sub(r"\s+", " ", stripped).strip()


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


def _require_test_client(client: dict) -> None:
    """Hard gate on every endpoint that touches DigiGrowth's own shared
    Twilio/Gmail credentials (real calling, real SMS/email send) — those
    must never be reachable from a real client's portal, only the one
    client explicitly flagged is_test (see db.py's clients.is_test
    migration). Checked server-side, not just hidden in the frontend,
    since these routes are public/unauthenticated and reachable directly
    by anyone holding a real client's own portal token."""
    if not client.get("is_test"):
        raise HTTPException(status_code=403, detail="Not available for this client")


@router.get("/{token}")
async def portal_home(token: str):
    client = await get_client_from_token(token)
    return {
        "id": client["id"], "name": client["name"], "status": client["status"],
        # NULL for every real client until they connect their own Calendly
        # (see db.py's calendly_url migration note) — the portal's booking
        # UI shows "not connected" in place of the iframe when this is null.
        "calendly_url": client.get("calendly_url"),
    }


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


@router.get("/{token}/todo")
async def portal_todo(token: str):
    """The agency's own launch-readiness checklist (separate from
    /action-items above, which is the onboarding steps the CLIENT completes)
    — read-only here since DigiGrowth staff check these off from the admin
    Clients panel, not the client. The client's portal just watches
    progress toward launch."""
    client = await get_client_from_token(token)
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
            client["id"],
        )
    return [dict(r) for r in rows]


@router.get("/{token}/stats")
async def portal_stats(token: str, period: str = "all"):
    """period: "all" (default) | "today" | "week" | "month" — same bucket
    vocabulary as portal_inbox_list's `since` param. Scopes sms/email
    sent+replies to messages sent in that window, and leads to contacts
    created in that window. Appointments are real (all-time, not scoped to
    `period`) only for the is_test client, computed live from
    appointment_reminders.outcome_show/outcome_close — every other real
    client still gets the zeroed placeholder (see portal_appointments()
    below for why)."""
    if period != "all" and period not in _PERIOD_INTERVAL:
        raise HTTPException(status_code=400, detail="period must be 'all', 'today', 'week', or 'month'")
    interval = _PERIOD_INTERVAL.get(period)
    sms_since_clause   = f"AND sm.sent_at >= now() - interval '{interval}'" if interval else ""
    email_since_clause = f"AND em.sent_at >= now() - interval '{interval}'" if interval else ""
    leads_since_clause = f"AND created_at >= now() - interval '{interval}'" if interval else ""

    client = await get_client_from_token(token)
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Scoped via contacts.client_id (joined through contact_id), not
        # sms_conversations.client_id/email_conversations.client_id directly
        # — those two columns exist but nothing actually stamps them today;
        # the real, populated link is contacts.client_id, set by the admin
        # "link contact to client" action. Same fix applied to the inbox
        # list/thread endpoints below after this was caught live: a real
        # linked contact's SMS/email history was invisible in stats/inbox
        # list despite being reachable directly via the thread endpoint,
        # which already scoped correctly through contacts.
        #
        # `AND NOT c.is_client_anchor` everywhere below: the anchor contact
        # is Dylan's own internal sales-pipeline contact for this business
        # (the prospect who became this client) — its SMS/email history is
        # DigiGrowth's own cold-outreach conversation with them, not the
        # client's own patient-facing activity. Without this exclusion a
        # client's portal showed Dylan's personal outreach thread with them
        # back as if it were their own channel activity — confirmed live on
        # Brandon Crosdale's portal (11 sent/19 replies that were entirely
        # Dylan <-> Brandon's sales conversation, not anything Brandon's own
        # business had done). See clients.py's _linked_contact_summary for
        # the same anchor-vs-lead distinction on the admin side.
        sms_row = await conn.fetchrow(
            f"""
            SELECT
                COUNT(DISTINCT sc.id) AS conversations,
                COALESCE(SUM((sm.direction = 'outbound')::int), 0) AS sent,
                COALESCE(SUM((sm.direction = 'inbound')::int), 0) AS replies
            FROM sms_conversations sc
            JOIN contacts c ON c.id = sc.contact_id
            LEFT JOIN sms_messages sm ON sm.contact_id = sc.contact_id {sms_since_clause}
            WHERE c.client_id = $1 AND NOT c.is_client_anchor
            """,
            client["id"],
        )
        email_row = await conn.fetchrow(
            f"""
            SELECT
                COUNT(DISTINCT ec.id) AS conversations,
                COALESCE(SUM((em.direction = 'outbound')::int), 0) AS sent,
                COALESCE(SUM((em.direction = 'inbound')::int), 0) AS replies
            FROM email_conversations ec
            JOIN contacts c ON c.id = ec.contact_id
            LEFT JOIN email_messages em ON em.contact_id = ec.contact_id {email_since_clause}
            WHERE c.client_id = $1 AND NOT c.is_client_anchor
            """,
            client["id"],
        )
        ad_rows = await conn.fetch(
            "SELECT * FROM ad_campaign_stats WHERE client_id = $1 AND platform = 'meta' "
            "ORDER BY stat_date DESC LIMIT 30",
            client["id"],
        )
        leads_total = await conn.fetchval(
            f"SELECT count(*) FROM contacts WHERE client_id = $1 AND NOT is_client_anchor {leads_since_clause}",
            client["id"],
        )
        # appointment_reminders rows for this client's OWN LEADS (never the
        # anchor contact — see portal_appointments()'s docstring below for
        # why that's not a lead in their portal at all), excluding canceled
        # appointments from every count below — a canceled appointment never
        # happened, so it shouldn't count toward "total" or any outcome.
        # Real numbers here only for the is_test client, same gate as
        # portal_appointments()/portal_update_appointment_outcome(). Every
        # other real client keeps the zeroed placeholder below, unchanged.
        appt_row = None
        if client.get("is_test"):
            appt_row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) AS total,
                    COALESCE(SUM((ar.status = 'scheduled' AND ar.appointment_at > now())::int), 0) AS upcoming,
                    COALESCE(SUM((ar.outcome_show = 'show')::int), 0) AS shows,
                    COALESCE(SUM((ar.outcome_show = 'no_show')::int), 0) AS no_shows,
                    COALESCE(SUM((ar.outcome_close = 'closed')::int), 0) AS closed,
                    COALESCE(SUM((ar.outcome_close = 'not_closed')::int), 0) AS not_closed
                FROM appointment_reminders ar
                JOIN contacts c ON c.id = ar.contact_id
                WHERE c.client_id = $1 AND NOT c.is_client_anchor AND ar.status != 'canceled'
                """,
                client["id"],
            )
    if appt_row:
        shows, no_shows = appt_row["shows"], appt_row["no_shows"]
        closed, not_closed = appt_row["closed"], appt_row["not_closed"]
        appointments_out = {
            "total": appt_row["total"], "upcoming": appt_row["upcoming"],
            "shows": shows, "no_shows": no_shows,
            "show_rate": _pct(shows, shows + no_shows),
            "closed": closed, "not_closed": not_closed,
            # Divides by shows, not total appointments — matches
            # analytics.py's /analytics/sales close_rate convention (a deal
            # can only close among people who actually showed up).
            "close_rate": _pct(closed, shows),
        }
    else:
        appointments_out = {
            "total": 0, "upcoming": 0, "shows": 0, "no_shows": 0,
            "show_rate": 0.0, "closed": 0, "not_closed": 0, "close_rate": 0.0,
        }
    return {
        "sms": dict(sms_row),
        "email": dict(email_row),
        "ads": {
            "platform": "meta",
            "status": "coming_soon",
            "days": [dict(r) for r in ad_rows],
        },
        "leads": {"total": leads_total},
        "appointments": appointments_out,
    }


# ---------------- Appointments ----------------
#
# appointment_reminders originally held ONLY DigiGrowth's own sales-pipeline
# meetings (the discovery call before a business signed) — every row was a
# meeting between Dylan and the anchor contact, not a new-patient
# appointment the client's own campaign generated for them. Surfacing that
# table to a REAL client read as "Dylan's own appointment with himself" on
# their portal — confirmed live on Brandon Crosdale's portal.
#
# Since portal_book_appointment() below now lets a client book an
# appointment for one of their OWN LEADS (never the anchor contact — that's
# not a lead in their portal at all, it's DigiGrowth's own sales contact),
# appointment_reminders can hold real client-facing data now, scoped by
# `AND NOT c.is_client_anchor` everywhere below. contacts.client_id is also
# set in bulk by clients.py's link-all-unassigned admin action (built to
# give the test client's portal sample data), which is exactly why the
# anchor still has to be excluded — that action swept the anchor's own old
# test bookings in under this client's id too.
#
# Per Dylan's explicit call (2026-09-01): only the is_test client's portal
# can see/create real appointment data — every other real client keeps
# getting an empty list, same as before, until this is deliberately opened
# up. Gated the same way as the Twilio/Gmail endpoints above
# (_require_test_client), not just left stubbed by omission.

@router.get("/{token}/appointments")
async def portal_appointments(token: str, status: str = "scheduled"):
    client = await get_client_from_token(token)
    if not client.get("is_test"):
        return []
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT ar.* FROM appointment_reminders ar
            JOIN contacts c ON c.id = ar.contact_id
            WHERE c.client_id = $1 AND NOT c.is_client_anchor AND ar.status = $2
            ORDER BY ar.appointment_at ASC
            """,
            client["id"], status,
        )
    return [dict(r) for r in rows]


@router.get("/{token}/appointments/timezones")
async def portal_appointment_timezones(token: str):
    """Static list for the portal booking form's timezone dropdown — same
    US_TIMEZONES the internal OS's BookingForm.jsx uses. Not sensitive data,
    so no is_test gate; harmless for any client's portal to fetch."""
    await get_client_from_token(token)
    return US_TIMEZONES


@router.post("/{token}/leads/{contact_id}/book")
async def portal_book_appointment(token: str, contact_id: str, body: dict):
    """Client-facing appointment booking for one of the client's OWN LEADS
    (never the anchor contact — see module note above). Reuses
    routers/appointments.py's create_appointment() so the reminder
    pipeline (24h/6h/1h sends) picks this up exactly like an internally
    booked appointment. is_test-gated like every other real-data-writing
    portal endpoint."""
    client = await get_client_from_token(token)
    _require_test_client(client)
    pool = await get_pool()
    async with pool.acquire() as conn:
        contact = await conn.fetchrow(
            "SELECT id, business, owner, phone, email FROM contacts WHERE id = $1 AND client_id = $2 AND NOT is_client_anchor",
            contact_id, client["id"],
        )
    if not contact:
        raise HTTPException(status_code=404, detail="Lead not found")

    return await appointments_router.create_appointment({
        "contact_id": contact_id,
        "prospect_name": contact["owner"] or contact["business"],
        "prospect_phone": contact["phone"],
        "prospect_email": contact["email"],
        "date": body.get("date"),
        "time": body.get("time"),
        "timezone": body.get("timezone"),
    })


@router.patch("/{token}/appointments/{appointment_id}")
async def portal_update_appointment_outcome(token: str, appointment_id: int, body: dict):
    """Client-facing outcome marking only (outcome_show/outcome_close/
    outcome_notes) — no reschedule/cancel from the portal. Mirrors the
    outcome-only branch of routers/appointments.py's PATCH handler,
    including its side effects (No Show sequence touch 1, onboarding
    kickoff on Closed), scoped to appointments that actually belong to
    this client. is_test-gated like portal_appointments() above — a real
    client has nothing to click through to this from the UI, but the
    route itself must refuse it too (public/unauthenticated, reachable
    directly by anyone holding that client's own portal token)."""
    client = await get_client_from_token(token)
    _require_test_client(client)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT ar.* FROM appointment_reminders ar
            JOIN contacts c ON c.id = ar.contact_id
            WHERE ar.id = $1 AND c.client_id = $2 AND NOT c.is_client_anchor
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
    if "outcome_notes" in body:
        updates["outcome_notes"] = (body["outcome_notes"] or "").strip() or None
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
async def portal_list_leads(token: str, tag: Optional[str] = None):
    """Excludes the anchor contact (is_client_anchor) — that's Dylan's own
    internal sales-pipeline contact for this business (see portal_stats()'s
    comment), not a lead the client's own business generated. Without this
    exclusion a client's own business showed up as "1 lead" in their own
    Leads tab. `tag` mirrors the internal CRM's GET /contacts?tag= filter
    (see routers/crm.py) — same ANY(tags) match."""
    client = await get_client_from_token(token)
    conditions = ["client_id = $1", "NOT is_client_anchor"]
    params = [client["id"]]
    if tag:
        params.append(tag)
        conditions.append(f"${len(params)} = ANY(tags)")
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT * FROM contacts WHERE {' AND '.join(conditions)} ORDER BY created_at DESC",
            *params,
        )
    return [dict(r) for r in rows]


@router.get("/{token}/tags")
async def portal_list_tags(token: str):
    """Read-only view of the shared global tag catalog (same `tags` table
    the internal CRM uses — see routers/tags.py) so a client's tag picker
    offers the same names/colors Dylan already uses internally. Tags
    themselves aren't client-scoped (there's no per-client tag catalog),
    only which contacts a given tag is applied to is."""
    await get_client_from_token(token)
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM tags ORDER BY name")
    return [dict(r) for r in rows]


@router.post("/{token}/leads/{contact_id}/tags")
async def portal_add_lead_tag(token: str, contact_id: str, body: TagAssign):
    """Mirrors POST /contacts/{id}/tags (routers/crm.py) but scoped to this
    client's own leads — never the anchor contact, never another client's."""
    tag = body.tag.strip()
    if not tag:
        raise HTTPException(status_code=400, detail="tag required")
    client = await get_client_from_token(token)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE contacts SET tags = array_append(tags, $3), updated_at = now() "
            "WHERE id = $1 AND client_id = $2 AND NOT is_client_anchor AND NOT ($3 = ANY(tags)) "
            "RETURNING *",
            contact_id, client["id"], tag,
        )
        if not row:
            row = await conn.fetchrow(
                "SELECT * FROM contacts WHERE id = $1 AND client_id = $2 AND NOT is_client_anchor",
                contact_id, client["id"],
            )
    if not row:
        raise HTTPException(status_code=404, detail="Lead not found")
    return dict(row)


@router.delete("/{token}/leads/{contact_id}/tags/{tag}")
async def portal_remove_lead_tag(token: str, contact_id: str, tag: str):
    client = await get_client_from_token(token)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE contacts SET tags = array_remove(tags, $3), updated_at = now() "
            "WHERE id = $1 AND client_id = $2 AND NOT is_client_anchor RETURNING *",
            contact_id, client["id"], tag,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Lead not found")
    return dict(row)


@router.patch("/{token}/leads/{contact_id}")
async def portal_update_lead(token: str, contact_id: str, body: dict):
    """Edit a lead's own fields — mirrors PATCH /contacts/{id} (routers/crm.py)
    but restricted to _LEAD_FIELDS (no status/grade/campaign-assignment/etc.,
    which are DigiGrowth-internal sales-pipeline concepts, not something a
    client editing their own lead's contact info should touch) and scoped to
    this client's own leads only — never the anchor contact, never another
    client's, same guard as the tag endpoints above."""
    client = await get_client_from_token(token)
    updates = {k: (body[k] or None) for k in _LEAD_FIELDS if k in body}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clauses = [f"{k} = ${i + 3}" for i, k in enumerate(updates)]
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow(
                f"UPDATE contacts SET {', '.join(set_clauses)}, updated_at = now() "
                f"WHERE id = $1 AND client_id = $2 AND NOT is_client_anchor RETURNING *",
                contact_id, client["id"], *updates.values(),
            )
        except asyncpg.UniqueViolationError:
            raise HTTPException(status_code=409, detail="Another contact already uses that phone number")
    if not row:
        raise HTTPException(status_code=404, detail="Lead not found")
    return dict(row)


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
        # phone number. Only update if it's already this client's own row —
        # and never the anchor contact even if it is this client's own row
        # (that's Dylan's internal sales contact for this business, not a
        # lead the portal should ever create/overwrite).
        existing = await conn.fetchrow("SELECT client_id, is_client_anchor FROM contacts WHERE phone = $1", phone)
        if existing and (existing["client_id"] != client["id"] or existing["is_client_anchor"]):
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
            existing = await conn.fetchrow("SELECT client_id, is_client_anchor FROM contacts WHERE phone = $1", phone)
            if existing and (existing["client_id"] != client["id"] or existing["is_client_anchor"]):
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
async def portal_inbox_list(
    token: str,
    channel: str = "all",
    since: str = "all",
    tag: Optional[str] = None,
    status: Optional[str] = None,
):
    """Excludes the anchor contact (is_client_anchor) — same reasoning as
    portal_stats()'s SMS/email totals: that thread is Dylan's own cold-
    outreach conversation with this business, not something that belongs in
    their own portal inbox.

    Filters mirror the internal InboxPanel/email_inbox.py's GET
    /inbox/conversations shape: `channel` ("all"|"sms"|"email"), `since`
    ("all"|"today"|"week"|"month" — this portal's own bucket vocabulary,
    see _PERIOD_INTERVAL), `tag` (ANY(c.tags)), `status` (c.status, the
    contact's CRM pipeline status). `since` is applied post-merge in Python
    against each conversation's last_message_at rather than in SQL, since
    "still active in this window" is naturally a property of the merged
    per-contact thread, not either channel's query alone."""
    if since != "all" and since not in _PERIOD_INTERVAL:
        raise HTTPException(status_code=400, detail="since must be 'all', 'today', 'week', or 'month'")
    if channel not in ("all", "sms", "email"):
        raise HTTPException(status_code=400, detail="channel must be 'all', 'sms', or 'email'")

    client = await get_client_from_token(token)

    conditions = ["c.client_id = $1", "NOT c.is_client_anchor"]
    params = [client["id"]]
    if tag:
        params.append(tag)
        conditions.append(f"${len(params)} = ANY(c.tags)")
    if status:
        params.append(status)
        conditions.append(f"c.status = ${len(params)}")
    where = " AND ".join(conditions)

    pool = await get_pool()
    async with pool.acquire() as conn:
        sms_rows = []
        if channel in ("all", "sms"):
            sms_rows = await conn.fetch(
                f"""
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
                WHERE {where}
                """,
                *params,
            )
        email_rows = []
        if channel in ("all", "email"):
            email_rows = await conn.fetch(
                f"""
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
                WHERE {where}
                """,
                *params,
            )

    by_contact: dict = {}
    for rows, ch in ((sms_rows, "sms"), (email_rows, "email")):
        for r in rows:
            d = dict(r)
            cid = d["contact_id"]
            entry = by_contact.setdefault(cid, {
                "contact_id": cid, "business": d["business"], "owner": d["owner"],
                "phone": d["phone"], "email": d["email"],
                "channels": [], "last_message": None, "last_message_at": None, "unread": False,
            })
            # A contact can have more than one row in sms_conversations/
            # email_conversations over time (email_conversations especially
            # — one row per distinct Gmail thread_id, not per contact), so
            # without this dedup check the list showed "EMAIL" repeated
            # once per underlying thread row instead of once per contact.
            if ch not in entry["channels"]:
                entry["channels"].append(ch)
            entry["unread"] = entry["unread"] or d["unread"]
            if d["last_message_at"] and (
                entry["last_message_at"] is None or d["last_message_at"] > entry["last_message_at"]
            ):
                entry["last_message"] = _strip_html(d["last_message"])
                entry["last_message_at"] = d["last_message_at"]

    results = list(by_contact.values())
    if since != "all":
        from datetime import datetime, timedelta, timezone as dt_timezone
        cutoff_days = {"today": 1, "week": 7, "month": 30}[since]
        cutoff = datetime.now(dt_timezone.utc) - timedelta(days=cutoff_days)
        results = [e for e in results if e["last_message_at"] and e["last_message_at"] >= cutoff]

    return sorted(results, key=lambda e: e["last_message_at"] or "", reverse=True)


@router.get("/{token}/inbox/{contact_id}")
async def portal_inbox_thread(token: str, contact_id: str):
    """NOT is_client_anchor here too (not just in the list above) — a
    client can't reach their own anchor contact's thread by guessing/
    remembering its contact_id either."""
    client = await get_client_from_token(token)
    pool = await get_pool()
    async with pool.acquire() as conn:
        contact = await conn.fetchrow(
            "SELECT id, business, owner, phone, email FROM contacts WHERE id = $1 AND client_id = $2 AND NOT is_client_anchor",
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
        + [{"channel": "email", "direction": m["direction"], "body": _strip_html(m["body"]), "subject": m["subject"], "sent_at": m["sent_at"]} for m in email_msgs]
    )
    messages.sort(key=lambda m: m["sent_at"])

    return {"contact": dict(contact), "messages": messages}


@router.post("/{token}/inbox/{contact_id}/send")
async def portal_send_message(token: str, contact_id: str, body: dict):
    """Sends for real, through the same shared Twilio/Gmail credentials every
    other automated send in this codebase already uses — but ONLY for the
    is_test client (see _require_test_client). No per-client Twilio number
    or Gmail inbox exists yet, so a real client's portal must never be able
    to trigger a real send through DigiGrowth's own shared credentials
    (wrong sender identity, real cost/liability, and a genuine cross-tenant
    data/access leak). Every other real client gets the same friendly
    "not connected yet" stub this endpoint always returned before."""
    client = await get_client_from_token(token)
    pool = await get_pool()
    async with pool.acquire() as conn:
        contact = await conn.fetchrow(
            "SELECT id, phone, email FROM contacts WHERE id = $1 AND client_id = $2 AND NOT is_client_anchor",
            contact_id, client["id"],
        )
    if not contact:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if not client.get("is_test"):
        return {
            "ok": False,
            "status": "not_connected",
            "detail": "Your SMS/email account isn't connected yet — DigiGrowth is setting this up and will notify you once replies can be sent from here.",
        }

    channel = body.get("channel")
    if channel not in ("sms", "email"):
        raise HTTPException(status_code=400, detail="channel must be 'sms' or 'email'")
    text = (body.get("body") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="body required")

    # Both branches below are wrapped in asyncio.wait_for — a hung Gmail/
    # Twilio API call (bad/expired OAuth token needing a slow refresh
    # attempt, a network stall, etc.) previously held this request open
    # indefinitely, which the frontend has no timeout of its own for either
    # — reported live as the whole portal "freezing" on email send. This
    # turns a hang into a clean, fast error instead of an infinite wait on
    # both ends.
    _SEND_TIMEOUT_S = 20

    if channel == "sms":
        phone = (contact["phone"] or "").strip()
        if not phone:
            raise HTTPException(status_code=400, detail="This contact has no phone number on file")
        from routers import sms as sms_router
        try:
            await asyncio.wait_for(asyncio.to_thread(sms_router._send_twilio, phone, text), timeout=_SEND_TIMEOUT_S)
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail="SMS send timed out — check Twilio credentials/status and try again.")
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"SMS send failed: {e}")
        async with pool.acquire() as conn:
            await sms_router._get_or_create_conversation(conn, phone)
            await sms_router._store_message(conn, phone, "assistant", text, is_automated=False)
        return {"ok": True}

    # email — reuses the same subject as this contact's most recent email
    # (if any) so it reads as a continuation, not a random new thread;
    # gmail_send() below handles all the email_conversations/email_messages
    # bookkeeping itself (matched by contact.email), same as every other
    # direct gmail_send call in this codebase (see integrations.py's
    # _record_outbound_email) — no manual DB write needed here.
    email = (contact["email"] or "").strip()
    if not email:
        raise HTTPException(status_code=400, detail="This contact has no email on file")
    async with pool.acquire() as conn:
        last_subject = await conn.fetchval(
            "SELECT subject FROM email_messages WHERE contact_id = $1 ORDER BY sent_at DESC LIMIT 1",
            contact_id,
        )
    subject = last_subject or f"Message from {client['name']}"
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(integrations.gmail_send, email, subject, text, False, False),
            timeout=_SEND_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Email send timed out — check Gmail credentials/status and try again.")
    if not result.startswith("Sent email"):
        raise HTTPException(status_code=502, detail=result)
    return {"ok": True}


@router.post("/{token}/leads/{contact_id}/call")
async def portal_call_lead(token: str, contact_id: str):
    """Places a real single-dial call through DigiGrowth's existing shared
    Twilio setup (same dialer_engine/TwiML app as the internal OS dialer) —
    but ONLY for the is_test client (see _require_test_client's note on why:
    no per-client Twilio credentials exist yet, so any other client would be
    placing real calls through DigiGrowth's own shared line). Every other
    real client gets the same friendly "not connected yet" stub this
    endpoint always returned before. Validates the lead belongs to this
    client via the token, then (for the test client only) reuses
    dialer.call_single() (the same one-lead session entrypoint the internal
    CRM's "Call Now" button uses) to seed the dialer engine's single global
    session. The portal frontend then drives it exactly like DialerPanel
    does: fetch a Twilio token, connect the browser as the agent leg, and
    POST dial-batch once connected — see the /dialer/* proxy endpoints below.

    NOTE: dialer_engine's session is a single process-global session, not
    per-caller — the test client placing a call here will conflict with the
    admin running the internal Dialer panel at the same time. Acceptable for
    now (test-client-only use); would need real session isolation to
    support concurrent internal + portal dialing."""
    client = await get_client_from_token(token)
    pool = await get_pool()
    async with pool.acquire() as conn:
        contact = await conn.fetchrow(
            "SELECT id FROM contacts WHERE id = $1 AND client_id = $2 AND NOT is_client_anchor",
            contact_id, client["id"],
        )
    if not contact:
        raise HTTPException(status_code=404, detail="Lead not found")

    if not client.get("is_test"):
        return {
            "ok": False,
            "status": "not_connected",
            "detail": "Calling isn't connected for your account yet — DigiGrowth is setting this up and will notify you once you can call leads directly from here.",
        }

    return await dialer_router.call_single({"contact_id": contact_id})


@router.get("/{token}/dialer/token")
async def portal_dialer_token(token: str):
    """Twilio Voice JS SDK access token for the portal's browser Device —
    same shared TwiML app/credentials as the internal OS dialer (see
    dialer.get_token()); the portal user becomes the agent leg on the call.
    is_test-gated like every other endpoint below — see _require_test_client."""
    client = await get_client_from_token(token)
    _require_test_client(client)
    return await dialer_router.get_token()


@router.post("/{token}/dialer/dial-batch")
async def portal_dialer_dial_batch(token: str):
    client = await get_client_from_token(token)
    _require_test_client(client)
    return await dialer_router.dial_batch()


@router.get("/{token}/dialer/session")
async def portal_dialer_session(token: str):
    client = await get_client_from_token(token)
    _require_test_client(client)
    return await dialer_router.get_session()


@router.post("/{token}/dialer/end-call")
async def portal_dialer_end_call(token: str):
    client = await get_client_from_token(token)
    _require_test_client(client)
    return await dialer_router.end_call()


@router.post("/{token}/dialer/end-session")
async def portal_dialer_end_session(token: str):
    client = await get_client_from_token(token)
    _require_test_client(client)
    return await dialer_router.end_session()
