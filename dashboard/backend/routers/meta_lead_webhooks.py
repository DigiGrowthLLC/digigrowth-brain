"""
Public webhook for Meta (Facebook/Instagram) Lead Ads form submissions.
Unlike this codebase's Twilio webhooks (client_sms_webhooks.py, sms.py),
which carry no signature verification, this endpoint IS on the open
internet with no unguessable token in its URL — every POST must be
verified via Meta's X-Hub-Signature-256 HMAC before it's trusted.

Flow: Meta calls the leadgen change → resolve page_id to a client via
client_marketing_config.meta_page_id → fetch the lead's field data via
Graph API using META_SYSTEM_USER_TOKEN (the same one shared System User
token meta_ads.py uses — see that module's docstring for the Business
Manager structure) → create/claim a contacts row using the EXACT same
ownership contract as routers/client_portal.py's portal_create_lead
(never reimplemented separately) → hand off to
response_ai.initiate_conversation() for a genuinely new/claimed contact.

Meta App Review gates all of this on real traffic (leads_retrieval to read
form data, plus whatever page permission is required to subscribe a Page
to the leadgen field) — until that's approved this endpoint still exists
and verifies correctly, it just never receives real traffic yet.
"""
import hashlib
import hmac
import os
import uuid

import httpx
from fastapi import APIRouter, Request, Response

import response_ai
from db import get_pool

router = APIRouter()  # public — no auth, mounted with no prefix in main.py

_GRAPH_BASE = "https://graph.facebook.com/v21.0"

# Meta's Lead Ads standard fields use a few different aliases across form
# templates/API versions — checking several known ones rather than trusting
# exactly one. Flagged as an assumption to verify against Meta's current
# docs once real leads start arriving.
_PHONE_FIELD_NAMES = {"phone_number", "phone"}
_EMAIL_FIELD_NAMES = {"email"}
_NAME_FIELD_NAMES = {"full_name", "name"}


@router.get("/webhooks/meta-leadgen")
async def meta_leadgen_verify(request: Request):
    params = request.query_params
    if (
        params.get("hub.mode") == "subscribe"
        and params.get("hub.verify_token") == os.environ.get("META_WEBHOOK_VERIFY_TOKEN")
    ):
        return Response(content=params.get("hub.challenge", ""), media_type="text/plain")
    return Response(status_code=403)


def _verify_signature(raw_body: bytes, signature_header: str | None) -> bool:
    secret = os.environ.get("META_APP_SECRET")
    if not secret or not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header.removeprefix("sha256="))


def _extract_field(field_data: list[dict], names: set[str]) -> str | None:
    for f in field_data or []:
        if (f.get("name") or "").lower() in names:
            values = f.get("values") or []
            if values:
                return str(values[0]).strip() or None
    return None


async def _fetch_lead_fields(leadgen_id: str, token: str) -> list[dict]:
    async with httpx.AsyncClient() as http:
        resp = await http.get(
            f"{_GRAPH_BASE}/{leadgen_id}",
            params={"access_token": token, "fields": "field_data"},
            timeout=30,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Meta Graph API returned {resp.status_code}: {resp.text.strip()[:300]}")
        return resp.json().get("field_data", [])


async def _process_lead(client_id: int | None, leadgen_id: str, token: str) -> None:
    """client_id=None means this form belongs to Dylan's OWN Facebook Page
    (see dylan_meta_page_id in the caller below), not a client's — mirrors
    routers/calendly_webhooks.py's Dylan's-own-pipeline branch: still
    creates/claims a contacts row from the submitted form data so the lead
    lands in the internal CRM, it just never touches client_marketing_config
    or fires response_ai (a client-only SMS auto-response feature — there's
    no equivalent for DigiGrowth's own inbound leads here)."""
    try:
        field_data = await _fetch_lead_fields(leadgen_id, token)
    except Exception as e:
        print(f"[meta_lead_webhooks] failed to fetch lead {leadgen_id} for client={client_id}: {e}")
        return

    phone = _extract_field(field_data, _PHONE_FIELD_NAMES)
    if not phone:
        print(f"[meta_lead_webhooks] lead {leadgen_id} for client={client_id} has no phone — skipping")
        return
    email = _extract_field(field_data, _EMAIL_FIELD_NAMES)
    name = _extract_field(field_data, _NAME_FIELD_NAMES)

    pool = await get_pool()
    async with pool.acquire() as conn:
        # Exact same ownership contract as client_portal.py's
        # portal_create_lead — never claim an anchor contact or another
        # client's already-owned lead just because it shares a phone
        # number; an unowned contact is fair game. For Dylan's own pipeline
        # (client_id is None), an anchor contact IS fair game too — that's
        # just this business's own sales contact, legitimate to link.
        existing = await conn.fetchrow(
            "SELECT id, client_id, is_client_anchor, tags FROM contacts WHERE phone = $1", phone,
        )
        if existing and existing["is_client_anchor"] and client_id is not None:
            print(f"[meta_lead_webhooks] lead {leadgen_id} phone matches the anchor contact — skipping")
            return
        if existing and existing["client_id"] is not None and existing["client_id"] != client_id:
            print(f"[meta_lead_webhooks] lead {leadgen_id} phone already belongs to another client — skipping")
            return
        is_new_or_claimed = not existing or existing["client_id"] is None

        row = await conn.fetchrow(
            """
            INSERT INTO contacts (id, business, owner, phone, email, status, client_id, tags)
            VALUES ($1, NULL, $2, $3, $4, 'new', $5, ARRAY['meta_lead'])
            ON CONFLICT (phone) DO UPDATE SET
                owner      = COALESCE(EXCLUDED.owner, contacts.owner),
                email      = COALESCE(EXCLUDED.email, contacts.email),
                client_id  = COALESCE(contacts.client_id, EXCLUDED.client_id),
                tags       = CASE WHEN 'meta_lead' = ANY(contacts.tags) THEN contacts.tags
                                   ELSE array_append(contacts.tags, 'meta_lead') END,
                updated_at = now()
            RETURNING *
            """,
            str(uuid.uuid4()), name, phone, email, client_id,
        )

    if is_new_or_claimed and client_id is not None:
        await response_ai.initiate_conversation(client_id, row["phone"], lead_name=name)


@router.post("/webhooks/meta-leadgen")
async def meta_leadgen_inbound(request: Request):
    raw_body = await request.body()
    if not _verify_signature(raw_body, request.headers.get("X-Hub-Signature-256")):
        return Response(status_code=403)

    token = os.environ.get("META_SYSTEM_USER_TOKEN")
    payload = await request.json()

    pool = await get_pool()
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "leadgen":
                continue
            value = change.get("value", {})
            leadgen_id = value.get("leadgen_id")
            page_id = value.get("page_id")
            if not leadgen_id or not page_id:
                continue
            async with pool.acquire() as conn:
                mapped = await conn.fetchrow(
                    "SELECT client_id FROM client_marketing_config WHERE meta_page_id = $1", str(page_id),
                )
                resolved_client_id = mapped["client_id"] if mapped else None
                if not mapped:
                    # Not a client's page — check whether it's Dylan's own
                    # (dialer_settings key 'dylan_meta_page_id', set the same
                    # way as his own Calendly token — see calendly_admin.py).
                    dylan_page = await conn.fetchrow(
                        "SELECT value FROM dialer_settings WHERE key = 'dylan_meta_page_id'",
                    )
                    if not dylan_page or dylan_page["value"] != str(page_id):
                        print(f"[meta_lead_webhooks] no client or Dylan's own page mapped to page_id={page_id} — skipping lead {leadgen_id}")
                        continue
                    resolved_client_id = None
            if not token:
                print(f"[meta_lead_webhooks] META_SYSTEM_USER_TOKEN not set — skipping lead {leadgen_id}")
                continue
            await _process_lead(resolved_client_id, leadgen_id, token)

    return Response(content="", media_type="text/plain")
