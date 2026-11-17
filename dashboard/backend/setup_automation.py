"""Automations behind Marketing Setup v2 (setup_steps.py), 2026-11-16.

- autosetup_booking(): Auto-Setup step. Drafts the DigiGrowth Booking setup
  (hours, appointment type, timezone) with booking_autofill.propose() and
  saves it, plus the booking page details and the patient-contact phone/email
  (the clinic's own listing phone/email from the anchor contact). Booking stays
  OFF: Dylan picks the calendar and turns it on. Never overwrites hours or an
  appointment type that already exist.
- autosetup_voice(): Auto-Setup step for Growth clients. Builds the Retell
  agent from the text agent (client_voice_agent.sync_agent). The voice agent
  stays switched off.
- create_instant_form(): builds the client's Meta Instant Form through the
  Graph API on their Page (needs the Page assigned to DigiGrowth's system
  user): full name, phone, email, the text + AI-call consent disclaimer, a
  privacy link to the clinic's hosted privacy page, thank-you button to their
  booking link. Saves meta_form_id.
- run_test() / cleanup_test(): the one-click end-to-end test on Dylan's test
  number (TEST_PHONE): a fake Meta lead through the real intake (opener text
  or voice call), then a DigiGrowth booking on the next open slot (free visit
  types only) so the confirmation text goes out. cleanup_test() cancels that
  booking (removes the calendar event), deletes the test lead and resets the
  funnel's view/conversion stats.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone

import httpx

from db import get_pool

TEST_PHONE = "+17542485326"  # Dylan's default test number (memory: default-test-phone-number)
_GRAPH = "https://graph.facebook.com/v21.0"


async def _cfg(conn, client_id: int) -> dict:
    row = await conn.fetchrow("SELECT * FROM client_marketing_config WHERE client_id = $1", client_id)
    return dict(row) if row else {}


# ---------------------------------------------------------------- booking

async def autosetup_booking(client_id: int) -> tuple[str, str]:
    import booking_autofill
    from routers import booking as booking_router

    pool = await get_pool()
    async with pool.acquire() as conn:
        await booking_router._ensure_settings(conn, client_id)
        has_hours = await conn.fetchval("SELECT 1 FROM booking_hours WHERE client_id = $1 LIMIT 1", client_id)
        has_event = await conn.fetchval("SELECT 1 FROM booking_event_types WHERE client_id = $1 LIMIT 1", client_id)
        anchor = await conn.fetchrow(
            "SELECT phone, email FROM contacts WHERE client_id = $1 AND is_client_anchor LIMIT 1", client_id)
        s = await conn.fetchrow("SELECT contact_phone, contact_email FROM booking_settings WHERE client_id = $1", client_id)
        contact = {}
        if anchor and not s["contact_phone"] and anchor["phone"]:
            contact["contact_phone"] = anchor["phone"]
        if anchor and not s["contact_email"] and anchor["email"]:
            contact["contact_email"] = anchor["email"]
        if contact:
            sets = ", ".join(f"{k} = ${i}" for i, k in enumerate(contact, start=2))
            await conn.execute(f"UPDATE booking_settings SET {sets} WHERE client_id = $1", client_id, *contact.values())

    done = []
    if contact:
        done.append("patient contact info")
    if not (has_hours and has_event):
        proposal = await booking_autofill.propose(client_id)
        payload = {"timezone": proposal.get("timezone")}
        if not has_hours and proposal.get("hours"):
            payload["hours"] = proposal["hours"]
            done.append(f"{len(proposal['hours'])} hour windows")
        if not has_event and proposal.get("event_type"):
            payload["event_type"] = proposal["event_type"]
            done.append(f"appointment type \"{proposal['event_type'].get('name')}\"")
        await booking_router.autofill_apply(client_id, payload)
        notes = proposal.get("notes") or []
    else:
        notes = []
    try:
        await booking_autofill.apply_page_details(client_id, overwrite=False)
        done.append("page details")
    except Exception as e:
        notes.append(f"page details: {e}")
    detail = ("Drafted " + ", ".join(done) if done else "Already set up") + \
        ". Still yours: pick their calendar and turn it on." + (" Check: " + " ".join(notes) if notes else "")
    return "done", detail


# ---------------------------------------------------------------- voice

async def autosetup_voice(client_id: int) -> tuple[str, str]:
    import client_voice_agent
    pool = await get_pool()
    async with pool.acquire() as conn:
        crow = await conn.fetchrow("SELECT service_package, services FROM clients WHERE id = $1", client_id)
        cfg = await _cfg(conn, client_id)
    import client_services
    if "ai_voice" not in client_services.effective(dict(crow) if crow else {}):
        return "skipped", "Voice agent isn't one of this client's services"
    if not os.environ.get("RETELL_API_KEY"):
        return "skipped", "RETELL_API_KEY isn't set on the server"
    if cfg.get("retell_agent_id"):
        return "skipped", "Voice agent already built"
    await client_voice_agent.sync_agent(client_id)
    return "done", "Voice agent built from the text agent (switched off until you turn it on)"


# ---------------------------------------------------------------- instant form

def _consent_text(practice: str) -> str:
    return (f"By submitting, you agree to be contacted by {practice} by phone, including automated calls, and by "
            f"text, about your request. Consent isn't required to receive care. Msg & data rates may apply. "
            f"Reply STOP to opt out.")


async def _graph(http: httpx.AsyncClient, method: str, path: str, token: str, **kw) -> dict:
    r = await http.request(method, f"{_GRAPH}/{path}", params={"access_token": token, **kw.pop("params", {})},
                           timeout=30, **kw)
    data = r.json() if r.content else {}
    if r.status_code >= 400 or (isinstance(data, dict) and data.get("error")):
        err = data.get("error", {}) if isinstance(data, dict) else {}
        raise RuntimeError(err.get("error_user_msg") or err.get("message") or f"HTTP {r.status_code}")
    return data


async def create_instant_form(client_id: int) -> dict:
    from client_dm_agent import _page_token
    from booking_engine import public_base

    pool = await get_pool()
    async with pool.acquire() as conn:
        cfg = await _cfg(conn, client_id)
        client = await conn.fetchrow("SELECT name, calendly_url FROM clients WHERE id = $1", client_id)
        lp = await conn.fetchval(
            "SELECT slug FROM landing_pages WHERE client_id = $1 ORDER BY created_at DESC LIMIT 1", client_id)
        bs = await conn.fetchrow("SELECT booking_slug, enabled FROM booking_settings WHERE client_id = $1", client_id)
    page_id = (cfg.get("meta_page_id") or "").strip()
    if not page_id:
        raise ValueError("Save the client's Meta Page ID first (Meta access step)")
    practice = client["name"]
    base = public_base()
    if cfg.get("funnel_domain"):
        site = f"https://{cfg['funnel_domain'].strip().removeprefix('https://').strip('/')}"
        book_url = f"{site}/book"
    elif lp:
        site = f"{base}/lp/{lp}"
        book_url = f"{site}/book"
    else:
        site = base
        book_url = (client["calendly_url"] or "").strip() or (f"{base}/book/{bs['booking_slug']}" if bs else base)
    privacy_url = f"{base}/privacy/{lp}" if lp else f"{base}/privacy"

    body = {
        "name": f"{practice} - New Patient (DigiGrowth {datetime.now().strftime('%Y-%m-%d')})",
        "locale": "en_US",
        "questions": json.dumps([{"type": "FULL_NAME"}, {"type": "PHONE"}, {"type": "EMAIL"}]),
        "privacy_policy": json.dumps({"url": privacy_url, "link_text": "Privacy Policy"}),
        "custom_disclaimer": json.dumps({"title": "Contact consent", "body": {"text": _consent_text(practice)}}),
        "thank_you_page": json.dumps({
            "title": "Thanks! Pick a time now",
            "body": "Grab a time that works for you. We'll also text you shortly.",
            "button_type": "VIEW_WEBSITE", "button_text": "Book my visit", "website_url": book_url,
        }),
        "follow_up_action_url": site,
        "block_display_for_non_targeted_viewer": "true",
    }
    async with httpx.AsyncClient() as http:
        token = await _page_token(page_id)
        form = await _graph(http, "POST", f"{page_id}/leadgen_forms", token, data=body)
    form_id = form.get("id")
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE client_marketing_config SET meta_form_id = $2, updated_at = now() WHERE client_id = $1",
            client_id, form_id)
    return {"ok": True, "form_id": form_id, "booking_url": book_url, "privacy_url": privacy_url}


# ---------------------------------------------------------------- test

async def _save_test(client_id: int, data: dict) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE client_marketing_config SET setup_test = $2::jsonb WHERE client_id = $1",
            client_id, json.dumps(data, default=str))


async def run_test(client_id: int) -> dict:
    import booking_engine
    from routers.meta_lead_webhooks import _ingest_lead

    steps: list[str] = []
    pool = await get_pool()
    async with pool.acquire() as conn:
        owner = await conn.fetchrow(
            "SELECT client_id, is_client_anchor FROM contacts WHERE phone = $1", TEST_PHONE)
        cfg = await _cfg(conn, client_id)
    if owner and owner["client_id"] not in (None, client_id):
        raise ValueError("The test number is a lead of another client. Run CLEAN UP on that client first.")
    if not cfg.get("twilio_number"):
        raise ValueError("This client has no Twilio number yet")

    status = await _ingest_lead(client_id, f"setup-test-{uuid.uuid4().hex[:8]}", [
        {"name": "full_name", "values": ["Setup Test"]},
        {"name": "phone_number", "values": [TEST_PHONE]},
    ])
    steps.append(f"Test lead sent through the Meta intake: {status}"
                 + (" (expect the voice agent's call first)" if cfg.get("voice_agent_enabled") else " (expect the opener text in about a minute)"))

    booking = None
    async with pool.acquire() as conn:
        bs = await conn.fetchrow("SELECT enabled FROM booking_settings WHERE client_id = $1", client_id)
        ev = await conn.fetchrow(
            "SELECT id, name FROM booking_event_types WHERE client_id = $1 AND active AND price_cents = 0 "
            "ORDER BY sort_order, id LIMIT 1", client_id)
    if bs and bs["enabled"] and ev:
        slots = await booking_engine.get_slots(client_id, ev["id"])
        start = next((s for d in slots.get("days", []) for s in d.get("slots", [])), None)
        if start:
            r = await booking_engine.reserve(client_id, ev["id"], start, "Setup Test", TEST_PHONE, None,
                                             "DigiGrowth setup test", None, None, booking_engine.public_base(),
                                             excluded=True)
            booking = {"token": r.get("token"), "start": start}
            steps.append(f"Booked \"{ev['name']}\" at {start}: the confirmation text should arrive now, and the "
                         f"visit shows on their calendar")
        else:
            steps.append("No open slot in the next 2 weeks to test booking")
    else:
        steps.append("Booking test skipped: DigiGrowth Booking isn't on, or the visit is paid (test that with Stripe test mode)")
    data = {"ran_at": datetime.now(timezone.utc).isoformat(), "steps": steps, "booking": booking, "cleaned_at": None}
    await _save_test(client_id, data)
    return data


async def cleanup_test(client_id: int) -> dict:
    import booking_engine
    done: list[str] = []
    pool = await get_pool()
    async with pool.acquire() as conn:
        bookings = await conn.fetch(
            "SELECT id FROM bookings WHERE client_id = $1 AND status = 'confirmed' "
            "AND regexp_replace(phone, '\\D', '', 'g') LIKE '%' || $2", client_id, TEST_PHONE[-10:])
    for b in bookings:
        try:
            await booking_engine.cancel_booking(b["id"], by_patient=False, reason="DigiGrowth setup test")
        except Exception as e:
            done.append(f"couldn't cancel booking {b['id']}: {e}")
    if bookings:
        done.append(f"cancelled {len(bookings)} test booking(s)")
    async with pool.acquire() as conn:
        res = await conn.execute(
            "DELETE FROM contacts WHERE client_id = $1 AND NOT is_client_anchor "
            "AND regexp_replace(phone, '\\D', '', 'g') LIKE '%' || $2", client_id, TEST_PHONE[-10:])
        n = int(res.split()[-1])
        done.append(f"deleted {n} test lead(s)")
        # Same reset as the Website tab's stats override, to zero.
        sites = await conn.fetch("SELECT id FROM client_websites WHERE client_id = $1", client_id)
        for s in sites:
            await conn.execute(
                "DELETE FROM content_view_events WHERE source = 'client_website' AND content_key = $1", str(s["id"]))
        if sites:
            done.append(f"reset stats on {len(sites)} funnel page(s)")
        await conn.execute(
            "DELETE FROM booking_partials WHERE client_id = $1 AND regexp_replace(phone, '\\D', '', 'g') LIKE '%' || $2",
            client_id, TEST_PHONE[-10:])
        row = await conn.fetchval("SELECT setup_test FROM client_marketing_config WHERE client_id = $1", client_id)
    data = json.loads(row) if isinstance(row, str) else dict(row or {})
    data["cleaned_at"] = datetime.now(timezone.utc).isoformat()
    data["cleanup"] = done
    await _save_test(client_id, data)
    return data
