"""Inbound Calendly webhooks — automatically create the appointment_reminders
row (which reminder_engine.py / client_appointment_reminders.py then run
their normal 24h/6h/1h no-show reminder sequence against) the moment someone
actually books a real slot on a Calendly link, instead of a rep having to
notice the booking and enter it manually through the OS.

Two callback URLs, one shared handler:
  POST /webhooks/calendly/dylan            — Dylan's own pipeline
  POST /webhooks/calendly/client/{client_id} — a specific client's leads

Each is registered (see routers/client_marketing.py's connect-calendly-webhook
and routers/calendly_admin.py's /calendly/connect) against that account's OWN
Calendly organization using that account's OWN Personal Access Token — but
the subscription itself is organization-scoped, so when Dylan is an admin on
a client's Calendly account (both sides sharing one org), EACH side's
webhook also receives the OTHER side's bookings. Both handlers below verify
the event's actual host (_resolve_host_uri) against their own account's user
URI before processing, and silently no-op otherwise — see calendly_webhook_
dylan's docstring comment for the incident this fixed.

Public/unauthenticated (mounted with no dependencies, same as every other
inbound webhook in this codebase — Twilio, Meta) since Calendly can't send
HTTPBasic credentials. Authenticity instead comes from verifying Calendly's
own HMAC signature against the signing_key handed back at subscription
creation (calendly_integration.verify_signature).
"""
import json
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, HTTPException, Request

import calendly_integration
from db import get_pool
from routers.appointments import cancel_appointment, create_appointment_row

router = APIRouter()  # public — mounted with no auth, see main.py


def _extract_phone(payload: dict) -> str | None:
    phone = (payload.get("text_reminder_number") or "").strip()
    if phone:
        return phone
    for qa in payload.get("questions_and_answers", []):
        if "phone" in (qa.get("question") or "").lower():
            answer = (qa.get("answer") or "").strip()
            if answer:
                return answer
    return None


async def _resolve_start_time(payload: dict, token: str) -> str:
    """The invitee.created payload embeds scheduled_event.start_time in
    current Calendly API versions, but fall back to fetching the event
    resource directly (payload['event'] is its URI) in case an older
    subscription or a future payload shape omits it — better than the
    whole booking silently failing to create a reminder."""
    embedded = payload.get("scheduled_event") or {}
    if embedded.get("start_time"):
        return embedded["start_time"]
    event_uri = payload.get("event")
    if not event_uri:
        raise HTTPException(400, "Calendly payload missing both scheduled_event and event")
    async with httpx.AsyncClient(timeout=10) as http:
        resp = await http.get(event_uri, headers={"Authorization": f"Bearer {token}"})
        resp.raise_for_status()
        return resp.json()["resource"]["start_time"]


async def _resolve_host_uri(payload: dict, token: str) -> str | None:
    """The Calendly user URI of whoever's calendar this booking actually
    landed on (the embedded scheduled_event's event_memberships), same
    embedded-first/fetch-fallback shape as _resolve_start_time above.
    Needed because Dylan's own webhook subscription is organization-scoped
    (see calendly_integration.register_webhook's docstring) and Dylan is
    also an admin on client Calendly accounts, so his subscription also
    receives every team member's bookings — not just his own. Returns None
    (never raises) if it can't be determined, so callers fail open rather
    than silently dropping a real booking."""
    embedded = payload.get("scheduled_event") or {}
    memberships = embedded.get("event_memberships")
    if not memberships:
        event_uri = payload.get("event")
        if not event_uri:
            return None
        try:
            async with httpx.AsyncClient(timeout=10) as http:
                resp = await http.get(event_uri, headers={"Authorization": f"Bearer {token}"})
                resp.raise_for_status()
                memberships = resp.json()["resource"].get("event_memberships") or []
        except Exception:
            return None
    return memberships[0]["user"] if memberships else None


async def _handle_invitee_created(payload: dict, token: str, client_id: int | None) -> dict:
    name = (payload.get("name") or "").strip() or None
    email = (payload.get("email") or "").strip() or None
    phone = _extract_phone(payload)
    tz_name = (payload.get("timezone") or "UTC").strip()
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("UTC")
        tz_name = "UTC"

    start_iso = await _resolve_start_time(payload, token)
    start_utc = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
    local = start_utc.astimezone(tz)

    contact_id = None
    pool = await get_pool()
    async with pool.acquire() as conn:
        if client_id is not None:
            # A client's own booking MUST be tied to a contact scoped to
            # that client_id — client_appointment_reminders.py's WHERE
            # clause requires it (an unscoped row would instead wrongly
            # fall into Dylan's own reminder_engine.py, whose WHERE treats
            # "no contact" as "ours"). Match existing by phone/email first
            # (contacts.phone is globally unique), else create a new lead —
            # same upsert shape as client_portal.py's portal_create_lead.
            existing = None
            if phone:
                existing = await conn.fetchrow(
                    "SELECT id, client_id FROM contacts WHERE phone = $1", phone,
                )
            if not existing and email:
                existing = await conn.fetchrow(
                    "SELECT id, client_id FROM contacts WHERE email = $1 AND client_id = $2", email, client_id,
                )
            if existing and existing["client_id"] in (None, client_id):
                contact_id = existing["id"]
                if existing["client_id"] is None:
                    await conn.execute(
                        "UPDATE contacts SET client_id = $1, updated_at = now() WHERE id = $2",
                        client_id, contact_id,
                    )
            elif not existing:
                row = await conn.fetchrow(
                    """
                    INSERT INTO contacts (id, owner, phone, email, status, client_id)
                    VALUES ($1, $2, $3, $4, 'new', $5)
                    RETURNING id
                    """,
                    str(uuid.uuid4()), name, phone, email, client_id,
                )
                contact_id = row["id"]
            # else: phone already belongs to a DIFFERENT client — leave
            # contact_id unset rather than misattributing someone else's
            # lead; the appointment still gets created (reminders still
            # send off prospect_name/phone/email directly) just without
            # client-portal visibility.

            # Auto-tag the lead by source: the ad-funnel landing page's
            # Calendly CTA carries ?utm_source=paid_ad (see design-agent's
            # funnel-building skill), which Calendly echoes back in this
            # payload's `tracking` object; the client's own real website's
            # link carries nothing, so it falls through to organic-lead.
            # Guarded to only fire once per contact — a repeat booking from
            # an already-tagged lead is left alone, and the client's own
            # manual re-tag in the portal is never silently overwritten.
            if contact_id is not None:
                tracking = payload.get("tracking") or {}
                lead_tag = "ads-lead" if tracking.get("utm_source") == "paid_ad" else "organic-lead"
                await conn.execute(
                    "UPDATE contacts SET tags = array_append(tags, $1), updated_at = now() "
                    "WHERE id = $2 AND NOT ('ads-lead' = ANY(tags)) AND NOT ('organic-lead' = ANY(tags))",
                    lead_tag, contact_id,
                )
        else:
            # Dylan's own pipeline — match an existing CRM contact by phone,
            # or create a new one from the Calendly invitee's own info
            # (name/phone/email) when none exists, same "create if missing"
            # behavior as the client branch above — a cold Calendly booking
            # with no prior contact should still land in the CRM with a real
            # contact card, not just float as prospect_name/phone/email on
            # the appointment row with nothing to click through to.
            if phone:
                existing = await conn.fetchrow(
                    "SELECT id, client_id, is_client_anchor FROM contacts WHERE phone = $1", phone,
                )
                if existing and (existing["client_id"] is None or existing["is_client_anchor"]):
                    contact_id = existing["id"]
                elif not existing:
                    row = await conn.fetchrow(
                        """
                        INSERT INTO contacts (id, owner, phone, email, status, tags)
                        VALUES ($1, $2, $3, $4, 'new', ARRAY['calendly_lead'])
                        RETURNING id
                        """,
                        str(uuid.uuid4()), name, phone, email,
                    )
                    contact_id = row["id"]
                # else: phone already belongs to another client's lead —
                # leave contact_id unset rather than misattributing it,
                # same non-claiming rule as the client branch above.

    appt_row = await create_appointment_row({
        "contact_id": contact_id,
        "prospect_name": name,
        "prospect_phone": phone,
        "prospect_email": email,
        "date": local.strftime("%Y-%m-%d"),
        "time": local.strftime("%H:%M"),
        "timezone": tz_name,
        "calendly_event_uri": payload.get("event"),
    })

    # "Consultation Requests" on a client's portal Website tab (see
    # client_portal.py's portal_websites()) now means a REAL booking, not
    # just a click on the page's CTA — only wired when the client has
    # exactly one tracked landing page, since a real Calendly booking event
    # carries no page-level attribution back to WHICH of several pages sent
    # them there (would need UTM params threaded through the CTA link and
    # echoed back in Calendly's `tracking` payload field — not built yet).
    if client_id is not None:
        async with pool.acquire() as conn:
            sites = await conn.fetch(
                "SELECT id FROM client_websites WHERE client_id = $1", client_id,
            )
            if len(sites) == 1:
                await conn.execute(
                    "INSERT INTO content_view_events (source, content_key, contact_id, event_type) "
                    "VALUES ('client_website', $1, $2, 'conversion')",
                    str(sites[0]["id"]), contact_id,
                )

    return appt_row


async def _handle_invitee_canceled(payload: dict) -> None:
    """Cancels the appointment_reminders row a Calendly invitee.canceled
    event corresponds to, via its stored calendly_event_uri, so a
    cancellation made directly in Calendly (rather than through the OS or
    client portal) doesn't have to be mirrored there by hand. A no-op if the
    event can't be matched (e.g. a booking made before calendly_event_uri
    existed) or the appointment's already resolved — cancel_appointment
    raises HTTPException in both cases, which this swallows since a webhook
    has no one to show that error to."""
    event_uri = payload.get("event")
    if not event_uri:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM appointment_reminders WHERE calendly_event_uri = $1 AND status = 'scheduled'",
            event_uri,
        )
    if not row:
        return
    try:
        await cancel_appointment(row["id"])
    except HTTPException:
        pass


async def _load_dylan_signing_key() -> str | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT value FROM dialer_settings WHERE key = 'dylan_calendly_webhook_signing_key'",
        )
    return row["value"] if row else None


@router.post("/webhooks/calendly/dylan")
async def calendly_webhook_dylan(request: Request):
    raw = await request.body()
    signing_key = await _load_dylan_signing_key()
    if not signing_key or not calendly_integration.verify_signature(
        raw, request.headers.get("Calendly-Webhook-Signature"), signing_key,
    ):
        raise HTTPException(401, "Invalid signature")

    body = json.loads(raw)
    if body.get("event") == "invitee.canceled":
        await _handle_invitee_canceled(body["payload"])
        return {"ok": True}
    if body.get("event") != "invitee.created":
        return {"ok": True}

    pool = await get_pool()
    async with pool.acquire() as conn:
        token_row = await conn.fetchrow(
            "SELECT value FROM dialer_settings WHERE key = 'dylan_calendly_api_token'",
        )
    token = token_row["value"] if token_row else None
    if not token:
        raise HTTPException(400, "No Calendly token saved for Dylan's account")

    # This subscription is organization-scoped (calendly_integration.
    # register_webhook), and Dylan is also an admin on client Calendly
    # accounts sharing the same org, so it also receives bookings made on a
    # CLIENT's own event type — those are already handled correctly by
    # that client's own /webhooks/calendly/client/{id} subscription. Only
    # process an event here if it's actually Dylan's own, or a client
    # patient booking lands unattributed (contact_id NULL) in Dylan's own
    # internal Appointments tab instead of that client's portal. Caught
    # live 2026-09-17: two of Crosacore's discovery-call bookings showed up
    # this way. Fails open (processes as before) if the host can't be
    # determined, rather than risk silently dropping a real booking.
    host_uri = await _resolve_host_uri(body["payload"], token)
    if host_uri:
        dylan_uri = await calendly_integration.get_user_uri(token)
        if host_uri != dylan_uri:
            return {"ok": True}

    await _handle_invitee_created(body["payload"], token, client_id=None)
    return {"ok": True}


@router.post("/webhooks/calendly/client/{client_id}")
async def calendly_webhook_client(client_id: int, request: Request):
    raw = await request.body()
    pool = await get_pool()
    async with pool.acquire() as conn:
        config = await conn.fetchrow(
            "SELECT calendly_api_token, calendly_webhook_signing_key FROM client_marketing_config WHERE client_id = $1",
            client_id,
        )
    if not config or not config["calendly_webhook_signing_key"]:
        raise HTTPException(404, "Calendly not connected for this client")
    if not calendly_integration.verify_signature(
        raw, request.headers.get("Calendly-Webhook-Signature"), config["calendly_webhook_signing_key"],
    ):
        raise HTTPException(401, "Invalid signature")

    body = json.loads(raw)
    if body.get("event") == "invitee.canceled":
        await _handle_invitee_canceled(body["payload"])
        return {"ok": True}
    if body.get("event") != "invitee.created":
        return {"ok": True}

    token = config["calendly_api_token"]
    if not token:
        raise HTTPException(400, "No Calendly token saved for this client")

    # Symmetric guard to calendly_webhook_dylan above — this org-scoped
    # subscription can equally receive a booking made on DYLAN's own event
    # type (or another client sharing the org) if the client's Calendly
    # account is on the same shared organization. Only process an event
    # that's actually this client's own, or one of Dylan's own sales-
    # pipeline prospects could get created as a "lead" inside this client's
    # portal instead. Fails open if the host can't be determined.
    host_uri = await _resolve_host_uri(body["payload"], token)
    if host_uri:
        client_user_uri = await calendly_integration.get_user_uri(token)
        if host_uri != client_user_uri:
            return {"ok": True}

    await _handle_invitee_created(body["payload"], token, client_id=client_id)
    return {"ok": True}
