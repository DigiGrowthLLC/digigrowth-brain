"""
Admin-side management of each REAL client's OWN marketing infrastructure —
their Twilio number, their email-sending domain, their self-built AI
response agent (response_ai.py), their landing page, and their ad
creatives. Deliberately separate
from crm.py/sms.py/sms_sequences.py (DigiGrowth's own outreach) — nothing
here ever touches DigiGrowth's shared Twilio/Gmail credentials or the
internal sms_messages/email_messages/campaigns tables.

Mounted with require_auth like clients.py — this is agency-internal admin
tooling (Dylan provisioning a client's stack), not the client-facing portal.

Also owns the email warm-up ramp's global settings (GET/PUT
/marketing-config/email-warmup-settings — the seed address list + optional
custom schedule shared by every client's warm-up, see email_warmup.py) and
the per-client start/status endpoints (start-warmup, warmup-status) below.
"""
import json

from fastapi import APIRouter, HTTPException, Query

import calendly_integration
import client_autosetup
import client_email
import client_sms
import context_gen
import dialer_engine
import email_warmup
import make_leadgen
import meta_ads
from db import get_pool
from models import ClientMarketingConfigUpdate, ClientSmsSequenceUpdate, ClientTestEmail

router = APIRouter()

# asyncpg has no JSONB codec registered on this pool (matches client_portal.py's
# _decode_response_row) — a JSONB column comes back as a raw JSON string.
_JSONB_FIELDS = ("ad_creative_status", "guide_progress", "response_ai_sequence", "autosetup")


def _decode_config(row) -> dict:
    d = dict(row)
    for key in _JSONB_FIELDS:
        if isinstance(d.get(key), str):
            d[key] = json.loads(d[key])
    return d


async def _get_or_create_config(conn, client_id: int) -> dict:
    row = await conn.fetchrow(
        "SELECT * FROM client_marketing_config WHERE client_id = $1", client_id
    )
    if row:
        return _decode_config(row)
    row = await conn.fetchrow(
        "INSERT INTO client_marketing_config (client_id) VALUES ($1) RETURNING *",
        client_id,
    )
    return _decode_config(row)


@router.get("/clients/{client_id}/marketing-config")
async def get_marketing_config(client_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        client = await conn.fetchrow("SELECT id FROM clients WHERE id = $1", client_id)
        if not client:
            raise HTTPException(404, "Client not found")
        return await _get_or_create_config(conn, client_id)


@router.put("/clients/{client_id}/marketing-config")
async def update_marketing_config(client_id: int, body: ClientMarketingConfigUpdate):
    pool = await get_pool()
    async with pool.acquire() as conn:
        client = await conn.fetchrow("SELECT id FROM clients WHERE id = $1", client_id)
        if not client:
            raise HTTPException(404, "Client not found")
        await _get_or_create_config(conn, client_id)

        fields = body.model_dump(exclude_unset=True)
        if not fields:
            return await _get_or_create_config(conn, client_id)

        set_clauses = []
        values = []
        for i, (key, value) in enumerate(fields.items(), start=1):
            set_clauses.append(f"{key} = ${i}")
            values.append(json.dumps(value) if isinstance(value, (dict, list)) else value)
        values.append(client_id)
        query = (
            f"UPDATE client_marketing_config SET {', '.join(set_clauses)}, updated_at = now() "
            f"WHERE client_id = ${len(values)} RETURNING *"
        )
        row = await conn.fetchrow(query, *values)

    # Saving a new Meta Page ID wires up its Lead Ads relay automatically.
    # A failure here (usually Page access not granted yet) never fails the
    # save — it lands in lead_ads_error for the guide to show, with a
    # Connect button to retry once the manual steps are done.
    if fields.get("meta_page_id") and fields["meta_page_id"] != row["lead_ads_connected_page_id"]:
        await _connect_lead_ads(client_id)
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM client_marketing_config WHERE client_id = $1", client_id)
    # Same for a newly saved Calendly token: register the booking webhook
    # right away (booking alerts, reminders, and the Meta opener's
    # already-booked skip all depend on it). Failure lands in
    # calendly_webhook_error; the CONNECT WEBHOOK button retries.
    if fields.get("calendly_api_token"):
        await _connect_calendly_webhook(client_id)
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM client_marketing_config WHERE client_id = $1", client_id)
    return _decode_config(row)


async def _connect_lead_ads(client_id: int) -> str | None:
    """Runs make_leadgen.connect_page for this client's saved Page and records
    the outcome. Returns the error message, or None on success."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT cmc.meta_page_id, c.name FROM client_marketing_config cmc "
            "JOIN clients c ON c.id = cmc.client_id WHERE cmc.client_id = $1",
            client_id,
        )
    page_id = (row["meta_page_id"] or "").strip() if row else ""
    if not page_id:
        return "No Meta Page ID saved for this client yet — add it in the Paid Ad Creatives step."
    try:
        result = await make_leadgen.connect_page(page_id, row["name"])
    except Exception as e:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE client_marketing_config SET lead_ads_error = $2, updated_at = now() WHERE client_id = $1",
                client_id, str(e),
            )
        return str(e)
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE client_marketing_config SET make_hook_id = $2, make_scenario_id = $3, "
            "lead_ads_connected_page_id = $4, lead_ads_error = NULL, updated_at = now() WHERE client_id = $1",
            client_id, result["hook_id"], result["scenario_id"], page_id,
        )
    return None


@router.post("/clients/{client_id}/marketing-config/connect-lead-ads")
async def connect_client_lead_ads(client_id: int):
    """Builds (or refreshes) this client's Make.com Facebook Lead Ads relay —
    see make_leadgen.py. Safe to re-click: an existing webhook/scenario for
    the Page is reused, never duplicated."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        client = await conn.fetchrow("SELECT id FROM clients WHERE id = $1", client_id)
        if not client:
            raise HTTPException(404, "Client not found")
        await _get_or_create_config(conn, client_id)
    error = await _connect_lead_ads(client_id)
    if error:
        raise HTTPException(400, error)
    return {"ok": True}


@router.post("/clients/{client_id}/marketing-config/provision-sms")
async def provision_sms_number(client_id: int, area_code: str | None = None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        client = await conn.fetchrow("SELECT id FROM clients WHERE id = $1", client_id)
        if not client:
            raise HTTPException(404, "Client not found")
    try:
        return await client_sms.provision_client_number(client_id, area_code=area_code)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))


@router.post("/clients/{client_id}/marketing-config/test-email")
async def send_test_email(client_id: int, body: ClientTestEmail):
    pool = await get_pool()
    async with pool.acquire() as conn:
        client = await conn.fetchrow("SELECT id FROM clients WHERE id = $1", client_id)
        if not client:
            raise HTTPException(404, "Client not found")
    try:
        result = await client_email.send_client_email(
            client_id, body.to, "Test email from your DigiGrowth setup",
            "This is a test send confirming your connected mailbox is working.",
            manual=True,
        )
        return {"detail": result}
    except RuntimeError as e:
        raise HTTPException(400, str(e))


@router.post("/clients/{client_id}/marketing-config/sync-email")
async def sync_client_email_now(client_id: int):
    """Manual trigger for testing/verification — same code path as the
    scheduled client-mailbox poll (client_email.sync_client_email_job),
    just scoped to one client so a reply shows up immediately instead of
    waiting for the next scheduled tick."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        config = await conn.fetchrow(
            "SELECT gmail_refresh_token, email_sync_last_ts FROM client_marketing_config WHERE client_id = $1",
            client_id,
        )
        if not config or not config["gmail_refresh_token"]:
            raise HTTPException(400, f"Client {client_id} has no connected Gmail mailbox yet")
        last_ts = config["email_sync_last_ts"] or 0
        try:
            newest_ts = await client_email._sync_one_mailbox(conn, client_id, config["gmail_refresh_token"], last_ts)
        except Exception as e:
            raise HTTPException(400, str(e))
        if newest_ts > last_ts:
            await conn.execute(
                "UPDATE client_marketing_config SET email_sync_last_ts = $2 WHERE client_id = $1",
                client_id, newest_ts,
            )
    return {"ok": True}


@router.post("/clients/{client_id}/marketing-config/sync-meta-ads")
async def sync_client_meta_ads_now(client_id: int, days_back: int = 3):
    """Manual trigger for testing/verification — same code path as the
    scheduled daily sync (meta_ads.sync_meta_ad_stats), scoped to one client
    and surfacing the specific reason it didn't work (no token yet, no ad
    account id saved, or the Graph API's own error) instead of that only
    ever reaching Railway's logs.

    days_back defaults to the daily job's normal 3-day trailing window, but
    can be widened (e.g. ?days_back=30) for a one-time historical backfill —
    the daily job never fills in days from before it started running for a
    given client, so a client whose ads predate this pipeline going live
    needs one manual wider-window sync to pull in that history."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        client = await conn.fetchrow("SELECT id FROM clients WHERE id = $1", client_id)
        if not client:
            raise HTTPException(404, "Client not found")
    try:
        days_synced = await meta_ads.sync_one_client_now(client_id, days_back=days_back)
    except Exception as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "days_synced": days_synced}


@router.post("/clients/{client_id}/marketing-config/connect-calendly-webhook")
async def connect_client_calendly_webhook(client_id: int):
    """Registers (or re-registers) this client's Calendly webhook — real
    bookings on their Calendly link then automatically create the
    appointment_reminders row that drives their No Show reminder sequence
    (client_appointment_reminders.py), instead of a rep entering it
    manually. Requires calendly_api_token already saved (Marketing Setup's
    Response AI step). See routers/calendly_webhooks.py for the receiving
    side."""
    error = await _connect_calendly_webhook(client_id)
    if error:
        raise HTTPException(400, error)
    return {"ok": True}


async def _connect_calendly_webhook(client_id: int) -> str | None:
    """Registers the client's Calendly webhook and records the outcome
    (calendly_webhook_uri/signing_key, or calendly_webhook_error). Returns
    the error message, or None on success."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        config = await conn.fetchrow(
            "SELECT calendly_api_token FROM client_marketing_config WHERE client_id = $1", client_id,
        )
    token = config["calendly_api_token"] if config else None
    error = None
    if not token:
        error = "No Calendly API token saved for this client yet — add one first."
    base = dialer_engine.base_url()
    if not error and not base:
        error = "DASHBOARD_URL not set — can't build a callback URL."
    result = None
    if not error:
        try:
            org_uri = await calendly_integration.get_organization_uri(token)
            result = await calendly_integration.register_webhook(
                token, f"{base}/webhooks/calendly/client/{client_id}", org_uri,
            )
        except Exception as e:
            error = str(e)

    async with pool.acquire() as conn:
        if result:
            await conn.execute(
                "UPDATE client_marketing_config SET calendly_webhook_uri = $2, "
                "calendly_webhook_signing_key = $3, calendly_webhook_error = NULL, updated_at = now() "
                "WHERE client_id = $1",
                client_id, result["uri"], result["signing_key"],
            )
        else:
            await conn.execute(
                "UPDATE client_marketing_config SET calendly_webhook_error = $2, updated_at = now() WHERE client_id = $1",
                client_id, error,
            )
    return error


@router.post("/clients/{client_id}/marketing-config/start-warmup")
async def start_email_warmup(client_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        client = await conn.fetchrow("SELECT id FROM clients WHERE id = $1", client_id)
        if not client:
            raise HTTPException(404, "Client not found")
    try:
        return await email_warmup.start_warmup(client_id)
    except RuntimeError as e:
        raise HTTPException(400, str(e))


@router.get("/clients/{client_id}/marketing-config/warmup-status")
async def get_email_warmup_status(client_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        client = await conn.fetchrow("SELECT id FROM clients WHERE id = $1", client_id)
        if not client:
            raise HTTPException(404, "Client not found")
    return await email_warmup.get_status(client_id)


@router.post("/clients/{client_id}/response-ai/reset-test")
async def reset_response_ai_test(client_id: int, phone: str = Query(...)):
    """Testing convenience: wipes the client_lead_conversations row and that
    phone's client_sms_messages history for this client, so re-texting the
    number starts response_ai.py fresh — no escalated/booked state or prior
    message context carried over from an earlier test run. Matches on the
    last 10 digits (same normalization dialer_webhooks.py uses for phone
    lookups) rather than an exact string, since client_lead_conversations
    stores E.164 (+1...) but someone testing this might paste the number
    with or without the country code/formatting — an exact-match miss here
    silently "succeeds" with messages_deleted=0, which looks like nothing
    happened."""
    digits = "".join(c for c in phone if c.isdigit())[-10:]
    if not digits:
        raise HTTPException(400, "phone must contain at least 10 digits")

    pool = await get_pool()
    async with pool.acquire() as conn:
        client = await conn.fetchrow("SELECT id FROM clients WHERE id = $1", client_id)
        if not client:
            raise HTTPException(404, "Client not found")
        await conn.execute(
            "DELETE FROM client_lead_conversations WHERE client_id = $1 "
            "AND right(regexp_replace(phone, '\\D', '', 'g'), 10) = $2",
            client_id, digits,
        )
        deleted = await conn.fetchval(
            "WITH d AS (DELETE FROM client_sms_messages WHERE client_id = $1 "
            "AND (right(regexp_replace(from_number, '\\D', '', 'g'), 10) = $2 "
            "OR right(regexp_replace(to_number, '\\D', '', 'g'), 10) = $2) RETURNING id) "
            "SELECT count(*) FROM d",
            client_id, digits,
        )
    return {"ok": True, "messages_deleted": deleted}


@router.post("/clients/{client_id}/marketing-config/generate-response-ai-context")
async def generate_response_ai_context(client_id: int):
    """Drafts a response_ai_context suggestion from everything already on
    file for this client (onboarding answers, linked contact info, uploaded
    PDFs/docx) — see context_gen.py. Returns the draft only; nothing is
    saved here, the admin reviews/edits it in the UI before saving via the
    existing PUT /marketing-config."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        client = await conn.fetchrow("SELECT id FROM clients WHERE id = $1", client_id)
        if not client:
            raise HTTPException(404, "Client not found")
    try:
        context = await context_gen.generate_context(client_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"context": context}


@router.post("/clients/{client_id}/marketing-config/autosetup")
async def run_marketing_autosetup(client_id: int):
    """Re-runs the automatic Marketing Setup that fires on Closed
    (client_autosetup.py) in the background. Only fills what's still empty;
    poll GET /marketing-config for progress in its `autosetup` field."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        client = await conn.fetchrow("SELECT id FROM clients WHERE id = $1", client_id)
        if not client:
            raise HTTPException(404, "Client not found")
    client_autosetup.kick_off(client_id, force=True)
    return {"ok": True}


@router.get("/marketing-config/email-warmup-settings")
async def get_email_warmup_settings():
    """Global (not per-client) config for email_warmup.py's ramp — the seed
    address list every client's warm-up sends to, and the optional custom
    day-by-day volume schedule. Same dialer_settings key/value store used by
    every other outreach template editor in routers/dialer.py."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT key, value FROM dialer_settings WHERE key IN ('warmup_seed_emails', 'warmup_schedule')"
        )
    values = {r["key"]: r["value"] for r in rows if r["value"]}
    return {
        "seed_emails": values.get("warmup_seed_emails", ""),
        "schedule": values.get("warmup_schedule", json.dumps(email_warmup._DEFAULT_SCHEDULE)),
    }


@router.put("/marketing-config/email-warmup-settings")
async def save_email_warmup_settings(body: dict):
    pool = await get_pool()
    async with pool.acquire() as conn:
        for key, value in (
            ("warmup_seed_emails", body.get("seed_emails")),
            ("warmup_schedule", body.get("schedule")),
        ):
            if value is None:
                continue
            await conn.execute(
                """
                INSERT INTO dialer_settings (key, value, updated_at) VALUES ($1, $2, now())
                ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = now()
                """,
                key, value,
            )
    return {"ok": True}


@router.get("/clients/{client_id}/sms-sequence")
async def get_client_sms_sequence(client_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        client = await conn.fetchrow("SELECT id FROM clients WHERE id = $1", client_id)
        if not client:
            raise HTTPException(404, "Client not found")
        row = await conn.fetchrow(
            "SELECT * FROM client_sms_sequences WHERE client_id = $1", client_id
        )
        if row:
            return dict(row)
        row = await conn.fetchrow(
            "INSERT INTO client_sms_sequences (client_id) VALUES ($1) RETURNING *",
            client_id,
        )
        return dict(row)


@router.put("/clients/{client_id}/sms-sequence")
async def update_client_sms_sequence(client_id: int, body: ClientSmsSequenceUpdate):
    pool = await get_pool()
    async with pool.acquire() as conn:
        client = await conn.fetchrow("SELECT id FROM clients WHERE id = $1", client_id)
        if not client:
            raise HTTPException(404, "Client not found")
        await conn.execute(
            "INSERT INTO client_sms_sequences (client_id) VALUES ($1) "
            "ON CONFLICT (client_id) DO NOTHING",
            client_id,
        )

        fields = body.model_dump(exclude_unset=True)
        if not fields:
            row = await conn.fetchrow(
                "SELECT * FROM client_sms_sequences WHERE client_id = $1", client_id
            )
            return dict(row)

        set_clauses = []
        values = []
        for i, (key, value) in enumerate(fields.items(), start=1):
            set_clauses.append(f"{key} = ${i}")
            values.append(value)
        values.append(client_id)
        query = (
            f"UPDATE client_sms_sequences SET {', '.join(set_clauses)}, updated_at = now() "
            f"WHERE client_id = ${len(values)} RETURNING *"
        )
        row = await conn.fetchrow(query, *values)
        return dict(row)


@router.get("/clients/{client_id}/sms-messages")
async def list_client_sms_messages(client_id: int, limit: int = 200):
    pool = await get_pool()
    async with pool.acquire() as conn:
        client = await conn.fetchrow("SELECT id FROM clients WHERE id = $1", client_id)
        if not client:
            raise HTTPException(404, "Client not found")
        rows = await conn.fetch(
            "SELECT * FROM client_sms_messages WHERE client_id = $1 "
            "ORDER BY created_at DESC LIMIT $2",
            client_id, limit,
        )
        return [dict(r) for r in rows]
