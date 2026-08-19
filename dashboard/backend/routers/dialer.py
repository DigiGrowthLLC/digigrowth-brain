"""
Dialer router — auth-protected endpoints for the DialerPanel UI.

  GET  /api/dialer/token         — Twilio access token for Twilio.Device
  GET  /api/dialer/session       — live session state (polled every 1s by frontend)
  POST /api/dialer/session/init  — start session, load leads into engine
  POST /api/dialer/dial-batch    — dial next batch of leads
  GET  /api/dialer/queue         — leads waiting in the current session's queue
  POST /api/dialer/classify      — log disposition after a call
  POST /api/dialer/end-call      — hang up the active bridged call
  POST /api/dialer/gatekeeper/connect  — redirect held gatekeeper into conference
  POST /api/dialer/gatekeeper/decline  — hang up held gatekeeper
  POST /api/dialer/set-lines     — update max parallel lines
  POST /api/dialer/end-session   — request session end
  GET  /api/dialer/script        — the default Call Script's text (read-only; see below)
  GET  /api/dialer/info-template — "Send Info" SMS/email templates
  PUT  /api/dialer/info-template — save "Send Info" SMS/email templates
  GET  /api/dialer/reminder-template — appointment reminder SMS/email templates
  PUT  /api/dialer/reminder-template — save appointment reminder templates

SMS outreach sequences moved to their own table/router — see
routers/sms_sequences.py (GET/POST/PATCH/DELETE /api/sms-sequences).
Cold Call Scripts moved to their own table/router the same way — see
routers/cold_call_scripts.py (GET/POST/PATCH/DELETE /api/cold-call-scripts).
"""

import json
import os
import pathlib
import time as _time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

import dialer_engine as engine
import integrations
import reminder_engine
from db import get_pool
from models import DISPOSITION_TO_STATUS
from routers import sms as sms_router

router = APIRouter()

_CONFIG_FILE = pathlib.Path(__file__).parent.parent / "dialer_config.json"

# Shared eligibility filter for the dialer queue: has a phone number, is
# actively a dialer lead (or a logged voicemail — still eligible, just gated
# by cooldown), isn't tagged not-qualified or not-interested (permanent
# exclusions regardless of status), and either past its 6h cooldown or its
# follow-up date has arrived.
_ELIGIBLE_WHERE = """
    phone IS NOT NULL
    AND phone <> ''
    AND status IN ('dialer-lead', 'voicemail')
    AND NOT (tags && ARRAY['not-qualified', 'not-interested'])
    AND (
      (follow_up_at IS NULL     AND (last_called_at IS NULL OR last_called_at < now() - interval '6 hours'))
      OR
      (follow_up_at IS NOT NULL AND follow_up_at <= now())
    )
"""


def _load_dialer_config() -> dict:
    try:
        with open(_CONFIG_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def _row_to_lead(r) -> dict:
    return {
        "contact_id": str(r["id"]),
        "phone":      r["phone"],
        "business":   r["business"] or "",
        "owner":      r["owner"] or "",
        "grade":      r["grade"] or "",
        "opener":     r["opener"] or "",
        "email":      r["email"] or "",
        "website":    r["website"] or "",
        "city":       r["city"] or "",
        "state":      r["state"] or "",
        "attempts":   r["call_attempts"],
        "notes":      r["notes"] or "",
    }


# ── Twilio access token (browser Twilio.Device) ───────────────────────────────

@router.get("/dialer/token")
async def get_token():
    from twilio.jwt.access_token import AccessToken
    from twilio.jwt.access_token.grants import VoiceGrant

    account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    api_key     = os.environ.get("TWILIO_API_KEY_SID", "")
    api_secret  = os.environ.get("TWILIO_API_KEY_SECRET", "")
    app_sid     = os.environ.get("TWILIO_TWIML_APP_SID", "")

    if not all([account_sid, api_key, api_secret, app_sid]):
        raise HTTPException(
            status_code=500,
            detail="Missing Twilio env vars: TWILIO_API_KEY_SID, TWILIO_API_KEY_SECRET, TWILIO_TWIML_APP_SID",
        )

    token = AccessToken(account_sid, api_key, api_secret, identity="agent", ttl=3600)
    grant = VoiceGrant(outgoing_application_sid=app_sid, incoming_allow=True)
    token.add_grant(grant)
    return {"token": token.to_jwt()}


# Call script is now editable from Business Resources → Outreach Templates
# as a list of named Cold Call Scripts (routers/cold_call_scripts.py); this
# endpoint stays as a read-only convenience for DialerPanel.jsx, which just
# needs the current default script's full text to fill and display during a
# live call — it never edits it directly.
@router.get("/dialer/script")
async def get_script():
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM cold_call_scripts WHERE is_default = true LIMIT 1")
    if not row:
        return {"script": "", "name": None}
    sections = [row["opener"], row["intro"], row["main_body"], row["close"]]
    script = "\n\n".join(s for s in sections if s and s.strip())
    return {"script": script, "name": row["name"]}


# ── "Send Info" disposition templates (edited from Business Resources ────────
# → Outreach Templates). Stored in the same key/value table as the call
# script; sms.send_info_message() and integrations.send_info_email() read
# these keys at send time, falling back to their hardcoded defaults if a key
# has never been saved.

@router.get("/dialer/info-template")
async def get_info_template():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT key, value FROM dialer_settings WHERE key IN "
            "('info_sms', 'info_email_subject', 'info_email_body', 'info_category')"
        )
    values = {r["key"]: r["value"] for r in rows}
    return {
        "sms":           values.get("info_sms", sms_router.INFO_MESSAGE),
        "email_subject": values.get("info_email_subject", integrations.INFO_EMAIL_SUBJECT),
        "email_body":    values.get("info_email_body", integrations.INFO_EMAIL_BODY),
        "category":      values.get("info_category") or "General",
    }


@router.put("/dialer/info-template")
async def save_info_template(body: dict):
    pool = await get_pool()
    async with pool.acquire() as conn:
        for key, value in (
            ("info_sms", body.get("sms", "")),
            ("info_email_subject", body.get("email_subject", "")),
            ("info_email_body", body.get("email_body", "")),
            ("info_category", body.get("category", "General")),
        ):
            await conn.execute(
                """
                INSERT INTO dialer_settings (key, value, updated_at) VALUES ($1, $2, now())
                ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = now()
                """,
                key, value,
            )
    return {"ok": True}


# ── Appointment reminder templates (Business Resources → Outreach Templates).
# Same key/value store as the two editors above; reminder_engine.py's
# send_booking_confirmation()/send_due_reminders()/send_reschedule_confirmation()
# read these keys fresh at send time via reminder_engine._get_templates().

@router.get("/dialer/reminder-template")
async def get_reminder_template():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT key, value FROM dialer_settings WHERE key = ANY($1)",
            list(reminder_engine.TEMPLATE_DEFAULTS.keys()) + ["reminder_category"],
        )
    values = {r["key"]: r["value"] for r in rows if r["value"]}
    result = {
        key: values.get(key, default)
        for key, default in reminder_engine.TEMPLATE_DEFAULTS.items()
    }
    result["category"] = values.get("reminder_category") or "General"
    return result


@router.put("/dialer/reminder-template")
async def save_reminder_template(body: dict):
    pool = await get_pool()
    async with pool.acquire() as conn:
        for key in reminder_engine.TEMPLATE_DEFAULTS:
            if key not in body:
                continue
            await conn.execute(
                """
                INSERT INTO dialer_settings (key, value, updated_at) VALUES ($1, $2, now())
                ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = now()
                """,
                key, body[key],
            )
        await conn.execute(
            """
            INSERT INTO dialer_settings (key, value, updated_at) VALUES ($1, $2, now())
            ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = now()
            """,
            "reminder_category", body.get("category", "General"),
        )
    return {"ok": True}


# ── Native OS session management ──────────────────────────────────────────────

@router.get("/dialer/session")
async def get_session():
    """Polled every 1s by DialerPanel to drive the calling UI state machine."""
    with engine._session["lock"]:
        active       = engine._session.get("active")
        bridged      = engine._session.get("bridged")
        show_cls     = engine._session.get("show_classification", False)
        connected_at = engine._session.get("connected_at")
        session_id   = engine._session.get("id")
        stats        = dict(engine._session.get("stats", {}))
        total        = engine._session.get("total_leads", 0)
        pending      = engine._session.get("pending")
        gk           = engine._session.get("gatekeeper_pending")
        end_req      = engine._session.get("end_requested", False)
        remaining    = max(0, len(engine._session.get("eligible_leads", [])))

    calls_made  = stats.get("calls_made", 0)
    dms_reached = stats.get("dms_reached", 0)

    if bridged:
        status = "connected"
    elif show_cls:
        status = "classify"
    elif active:
        status = "waiting"
    else:
        status = "idle"

    return {
        "active":        active,
        "session_id":    session_id,
        "status":        status,
        "current_lead":  pending,
        "connected_at":  connected_at,
        "gatekeeper":    gk["lead"] if gk else None,
        "end_requested": end_req,
        "stats": {
            "calls_made":  calls_made,
            "dms_reached": dms_reached,
            "remaining":   remaining,
            "total":       total,
        },
    }


@router.post("/dialer/session/init")
async def session_init():
    """Load eligible leads from DB and initialise the engine session."""
    config = _load_dialer_config()
    session_id = str(uuid.uuid4())[:8]

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT id, phone, business, owner, grade, opener, email,
                   website, city, state, call_attempts, notes
            FROM contacts
            WHERE {_ELIGIBLE_WHERE}
            ORDER BY
              CASE grade WHEN 'A' THEN 1 WHEN 'B' THEN 2
                         WHEN 'C' THEN 3 WHEN 'D' THEN 4 ELSE 5 END,
              call_attempts ASC
            LIMIT 500
            """,
        )

    leads = [_row_to_lead(r) for r in rows]

    engine.init_session(session_id, config, leads)
    return {"ok": True, "session_id": session_id, "lead_count": len(leads)}


async def _top_up_queue():
    """
    Pull more eligible leads from the CRM into the in-memory queue when it's
    running low, instead of letting the session just end once the leads
    fetched at session start are exhausted (newly-eligible leads and
    cooldown-expired leads get picked up this way).

    Dedup against what's actually in-flight right now (queued, ringing, or on
    the line) — NOT against leads_by_phone, which only ever grows for the
    whole session. A lead that got overflow-canceled and retried back into
    'dialer-lead' with its cooldown cleared is genuinely eligible again; if
    we excluded anyone ever seen this session, it would be permanently
    stranded — eligible in the CRM but never re-added to the dial queue.
    """
    with engine._session["lock"]:
        in_queue     = {engine._norm(l["phone"]) for l in engine._session["eligible_leads"]}
        in_flight    = {engine._norm(p) for p in engine._session.get("call_sids", {}).keys()}
        bridged      = engine._session.get("bridged_phone")
        dispositioned = set(engine._session.get("dispositioned", set()))
        exclude     = in_queue | in_flight | dispositioned | ({engine._norm(bridged)} if bridged else set())
        queue_len   = len(engine._session["eligible_leads"])
        max_lines   = engine._session.get("max_lines", 10)
    if queue_len >= max_lines:
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT id, phone, business, owner, grade, opener, email,
                   website, city, state, call_attempts, notes
            FROM contacts
            WHERE {_ELIGIBLE_WHERE}
            ORDER BY
              CASE grade WHEN 'A' THEN 1 WHEN 'B' THEN 2
                         WHEN 'C' THEN 3 WHEN 'D' THEN 4 ELSE 5 END,
              call_attempts ASC
            LIMIT 500
            """,
        )

    fresh = [_row_to_lead(r) for r in rows if engine._norm(r["phone"]) not in exclude]
    if not fresh:
        return

    with engine._session["lock"]:
        engine._session["eligible_leads"].extend(fresh)
        for lead in fresh:
            engine._session["leads_by_phone"][engine._norm(lead["phone"])] = lead
        engine._session["total_leads"] += len(fresh)


@router.get("/dialer/queue")
async def get_queue():
    """
    Leads currently eligible to be dialed, queried live from the CRM.
    Matches the "In Queue" stat tile exactly (same _ELIGIBLE_WHERE) — unlike
    the in-memory eligible_leads prefetch, which drops a lead the instant
    it's dialed, before its disposition (and CRM status) is even set.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT id, phone, business, owner, grade, opener, email,
                   website, city, state, call_attempts, notes
            FROM contacts
            WHERE {_ELIGIBLE_WHERE}
            ORDER BY
              CASE grade WHEN 'A' THEN 1 WHEN 'B' THEN 2
                         WHEN 'C' THEN 3 WHEN 'D' THEN 4 ELSE 5 END,
              call_attempts ASC
            LIMIT 500
            """,
        )
    leads = [_row_to_lead(r) for r in rows]
    return {"leads": leads, "count": len(leads)}


@router.get("/dialer/session/queue")
async def get_session_queue():
    """
    Leads still sitting in *this session's* in-memory prefetch batch, not
    yet dialed — matches the "Remaining" stat exactly (drops a lead the
    instant it's dialed, unlike /dialer/queue's live CRM count).
    """
    with engine._session["lock"]:
        leads = list(engine._session.get("eligible_leads", []))
    return {"leads": leads, "count": len(leads)}


@router.post("/dialer/dial-batch")
async def dial_batch():
    """Dial the next batch of leads. Called by the frontend after each classification."""
    with engine._session["lock"]:
        if not engine._session.get("active"):
            raise HTTPException(status_code=400, detail="No active session")
        if engine._session.get("end_requested"):
            return {"ok": True, "dialed": 0, "done": True}

        # Guard: if server-side auto_first_dial already claimed the first batch,
        # skip this frontend-initiated call (prevents double-dial at session start).
        # auto_dialed is reset to False at session init so it only blocks the
        # very first batch — subsequent batches (after classification) proceed normally.
        if engine._session.get("auto_dialed") and not engine._session.get("batch_had_answer"):
            return {"ok": True, "dialed": 0, "done": False, "note": "first batch auto-dialed"}

        # Guard: never start a new batch while a lead is currently bridged or
        # sitting in classify (awaiting a disposition click). Nothing else
        # enforces this — a stray/duplicate dial-batch call (e.g. a page
        # refresh re-triggering the connect flow) would otherwise dial 5 more
        # numbers on top of an already-live call.
        if engine._session.get("bridged") or engine._session.get("show_classification"):
            return {"ok": True, "dialed": 0, "done": False, "busy": True}

    # Top up the queue from the CRM before batching, so batches stay at full
    # strength instead of draining the leads fetched at session start.
    await _top_up_queue()

    with engine._session["lock"]:
        # Prepend any retry phones to the queue (inline to avoid nested lock deadlock)
        retry_phones  = set(engine._session.get("needs_retry", set()))
        engine._session["needs_retry"] = set()
        dispositioned = engine._session.get("dispositioned", set())
        retry_leads   = [
            engine._session["leads_by_phone"][p]
            for p in retry_phones
            if p in engine._session["leads_by_phone"] and p not in dispositioned
        ]
        if retry_leads:
            engine._session["eligible_leads"] = retry_leads + engine._session["eligible_leads"]

        max_lines = engine._session.get("max_lines", 10)
        batch     = engine._session["eligible_leads"][:max_lines]
        engine._session["eligible_leads"] = engine._session["eligible_leads"][max_lines:]

        if not batch:
            return {"ok": True, "dialed": 0, "done": True}

        # Record ring start + dial count before dialing
        now = _time.time()
        engine._session["batch_had_answer"] = False
        for lead in batch:
            norm = engine._norm(lead["phone"])
            engine._session["ring_start"][norm]  = now
            engine._session["dial_count"][norm]  = engine._session["dial_count"].get(norm, 0) + 1

        session_id = engine._session["id"]
        config     = engine._session["config"]

    base = engine.base_url()
    if not base:
        return {
            "ok": False, "dialed": 0, "done": False, "errors":
            ["RAILWAY_PUBLIC_DOMAIN not set — Twilio callback URLs cannot be built. Set this env var on Railway."],
            "phones": [],
        }

    phones = [l["phone"] for l in batch]
    sids, errors = await engine.dial_batch(phones, session_id, base, config)

    with engine._session["lock"]:
        engine._session["call_sids"].update(sids)

    return {
        "ok":       True,
        "dialed":   len(sids),
        "done":     False,
        "errors":   errors,
        "phones":   list(sids.keys()),
        "base_url": base,
    }


@router.post("/dialer/classify")
async def classify(body: dict):
    """Log disposition for the given lead and clear classification state."""
    disposition = (body.get("disposition") or "No Answer").strip()
    notes       = (body.get("notes") or "").strip() or None
    direction   = "inbound" if body.get("direction") == "inbound" else "outbound"

    with engine._session["lock"]:
        pending                              = engine._session.get("pending") or {}
        still_bridged                        = engine._session.get("bridged", False)
        engine._session["show_classification"] = False
        # Only clear the lead card / call timer if the call has actually ended.
        # A disposition can now be logged live mid-call (e.g. booking an
        # appointment without hanging up) — in that case the call is still
        # bridged and the UI should keep showing the lead and timer.
        if not still_bridged:
            engine._session["pending"]      = None
            engine._session["connected_at"] = None

    # Prefer the lead identity the client sent with the click over the
    # server's in-memory "pending" state — an unrelated session transition
    # (end/restart) can clear "pending" out from under a still-in-flight
    # classify request, which previously made it silently do nothing.
    contact_id = body.get("contact_id") or pending.get("contact_id")
    phone      = body.get("phone") or pending.get("phone", "")

    if contact_id or phone:
        # Write to DB directly (same logic as log_disposition)
        pool = await get_pool()
        async with pool.acquire() as conn:
            if not contact_id:
                # Fallback: match by normalized phone (Twilio's E.164 "To" vs.
                # the CRM's stored format, e.g. Google Places' "(754) 291-5582").
                contact = await conn.fetchrow(
                    "SELECT id FROM contacts WHERE right(regexp_replace(phone, '\\D', '', 'g'), 10) = $1",
                    engine._norm(phone),
                )
                contact_id = contact["id"] if contact else None

            await conn.execute(
                "INSERT INTO call_logs (contact_id, disposition, notes, direction, phone) VALUES ($1, $2, $3, $4, $5)",
                contact_id, disposition, notes, direction, phone or None,
            )

            if contact_id:
                new_status = DISPOSITION_TO_STATUS.get(disposition)
                updated = await conn.fetchrow(
                    """
                    UPDATE contacts SET
                        call_attempts    = call_attempts + 1,
                        last_disposition = $1,
                        last_called_at   = now(),
                        status           = COALESCE($2, status),
                        updated_at       = now()
                    WHERE id = $3
                    RETURNING call_attempts, phone, owner, email, business
                    """,
                    disposition, new_status, contact_id,
                )
                # Set follow_up_at for 30/90-day dispositions; clear it for all others
                # (manual follow-up carries no automatic re-dial date — Dylan follows
                # up himself).
                if disposition == "Follow Up 30 Day":
                    await conn.execute(
                        "UPDATE contacts SET call_attempts = 0, follow_up_at = now() + interval '30 days' WHERE id = $1",
                        contact_id,
                    )
                elif disposition == "Follow Up 90 Day":
                    await conn.execute(
                        "UPDATE contacts SET call_attempts = 0, follow_up_at = now() + interval '90 days' WHERE id = $1",
                        contact_id,
                    )
                else:
                    await conn.execute(
                        "UPDATE contacts SET follow_up_at = NULL WHERE id = $1",
                        contact_id,
                    )

                # Not Qualified / Not Interested: tag instead of relying only on the
                # status change, so the contact is excluded from the dial queue
                # (_ELIGIBLE_WHERE) permanently, even if status is ever reset
                # elsewhere (e.g. a manual CRM edit or bulk action).
                if disposition in ("Not Qualified", "Not Interested"):
                    tag = "not-qualified" if disposition == "Not Qualified" else "not-interested"
                    await conn.execute(
                        "UPDATE contacts SET tags = array_append(tags, $2), updated_at = now() "
                        "WHERE id = $1 AND NOT ($2 = ANY(tags))",
                        contact_id, tag,
                    )

                # SMS Handoff: fire the one-time Twilio opener immediately.
                if disposition == "SMS Handoff" and updated:
                    try:
                        await sms_router.send_opening_message(dict(updated))
                    except Exception as e:
                        print(f"sms-handoff opener failed for {updated['phone']}: {e}")

                # Send Info: text and email the prospect DigiGrowth's website and a
                # short company blurb. Independent sends — one failing shouldn't
                # block the other.
                if disposition == "Send Info" and updated:
                    try:
                        await sms_router.send_info_message(dict(updated))
                    except Exception as e:
                        print(f"send-info SMS failed for {updated['phone']}: {e}")
                    if updated.get("email"):
                        try:
                            result = await integrations.send_info_email(
                                updated["email"], updated.get("owner"), updated.get("business"),
                            )
                            if not result.startswith("Sent email"):
                                print(f"send-info email to {updated['email']} did not send: {result}")
                        except Exception as e:
                            print(f"send-info email failed for {updated['email']}: {e}")

                # Append call notes to the contact card (visible in CRM/dialer/SMS
                # panels), timestamped and tagged with the disposition for context.
                if notes:
                    entry = f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d')}] {disposition}: {notes}"
                    await conn.execute(
                        """
                        UPDATE contacts
                        SET notes = CASE WHEN notes IS NULL OR notes = '' THEN $2 ELSE notes || E'\\n' || $2 END,
                            updated_at = now()
                        WHERE id = $1
                        """,
                        contact_id, entry,
                    )

        # Update in-session stats
        with engine._session["lock"]:
            # Mark dispositioned so the short-ring retry queue and CRM top-up
            # can't re-add this phone later this session — both only look at
            # ring duration / DB cooldown timing, neither of which reflects a
            # disposition logged just now (last_called_at hasn't propagated
            # through their stale in-memory lead snapshot).
            engine._session["dispositioned"].add(engine._norm(phone))
            engine._session["needs_retry"].discard(engine._norm(phone))
            engine._session["stats"]["calls_made"] += 1
            if disposition in ("Appointment Booked", "Follow Up 30 Day", "Follow Up 90 Day", "Follow Up (Manual)", "Send Info", "Not Interested"):
                engine._session["stats"]["dms_reached"] += 1

    return {"ok": True}


@router.post("/dialer/end-call")
async def end_call():
    with engine._session["lock"]:
        bridged_sid                              = engine._session.get("bridged_sid")
        engine._session["bridged"]               = False
        engine._session["show_classification"]   = True
    if bridged_sid:
        engine.hangup_call(bridged_sid)
    return {"ok": True}


@router.post("/dialer/gatekeeper/connect")
async def gatekeeper_connect():
    from datetime import datetime, timezone
    with engine._session["lock"]:
        gk = engine._session.get("gatekeeper_pending")
        if not gk or engine._session.get("bridged"):
            return {"ok": False}

        engine._session["bridged"]             = True
        engine._session["bridged_sid"]         = gk["sid"]
        engine._session["bridged_phone"]       = engine._norm(gk["phone"])
        engine._session["show_classification"] = False
        engine._session["connected_at"]        = datetime.now(timezone.utc).isoformat()
        engine._session["batch_had_answer"]    = True
        engine._session["pending"]             = {**gk["lead"], "gatekeeper": True}
        engine._session["gatekeeper_pending"]  = None
        session_id = engine._session["id"]

    base = engine.base_url()
    engine.redirect_call(gk["sid"], f"{base}/dialer/voice/gatekeeper-join?session_id={session_id}")
    return {"ok": True}


@router.post("/dialer/gatekeeper/decline")
async def gatekeeper_decline():
    with engine._session["lock"]:
        gk = engine._session.get("gatekeeper_pending")
        engine._session["gatekeeper_pending"] = None
    if gk and gk.get("sid"):
        engine.hangup_call(gk["sid"])
    return {"ok": True}


@router.post("/dialer/set-lines")
async def set_lines(body: dict):
    lines = max(1, int(body.get("lines", 10)))
    with engine._session["lock"]:
        engine._session["max_lines"] = lines
    return {"ok": True, "max_lines": lines}


@router.post("/dialer/end-session")
async def end_session():
    with engine._session["lock"]:
        engine._session["end_requested"] = True
    engine.close_session()
    return {"ok": True}


@router.post("/dialer/call-single")
async def call_single(body: dict):
    """Init a one-lead session from the CRM panel for an individual callback."""
    contact_id = (body.get("contact_id") or "").strip()
    if not contact_id:
        raise HTTPException(status_code=400, detail="contact_id required")

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, phone, business, owner, grade, opener, email,
                   website, city, state, call_attempts, notes
            FROM contacts
            WHERE id = $1 AND phone IS NOT NULL
            """,
            contact_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Contact not found or has no phone")
        await conn.execute(
            "UPDATE contacts SET last_called_at = now(), updated_at = now() WHERE id = $1",
            contact_id,
        )

    config     = _load_dialer_config()
    session_id = str(uuid.uuid4())[:8]
    lead = _row_to_lead(row)
    engine.init_session(session_id, config, [lead])
    return {"ok": True, "session_id": session_id, "lead_count": 1}


@router.get("/dialer/session/calls")
async def get_session_calls():
    """Call log entries from the current (or most recently ended) session,
    for the 'Calls Made' stat's drill-down — matched by session start time
    since call_logs isn't itself keyed by session_id."""
    with engine._session["lock"]:
        start = engine._session.get("session_start_time")
    if not start:
        return {"calls": []}
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT cl.disposition, cl.notes, cl.started_at,
                   c.business, c.owner, c.phone, c.grade
            FROM call_logs cl
            LEFT JOIN contacts c ON c.id = cl.contact_id
            WHERE cl.started_at >= $1
            ORDER BY cl.started_at DESC
            """,
            start,
        )
    return {"calls": [dict(r) for r in rows]}


@router.get("/dialer/debug")
async def debug_config():
    """Returns resolved config so you can verify Railway env vars without checking logs."""
    config = _load_dialer_config()
    base = engine.base_url()
    twilio_phone = os.environ.get("TWILIO_PHONE_NUMBER") or config.get("twilio_phone_number", "")
    account_sid  = os.environ.get("TWILIO_ACCOUNT_SID", "")
    twiml_app    = os.environ.get("TWILIO_TWIML_APP_SID", "")
    with engine._session["lock"]:
        sess_active = engine._session.get("active", False)
        sess_leads  = len(engine._session.get("eligible_leads", []))
    return {
        "base_url":        base or "(EMPTY — RAILWAY_PUBLIC_DOMAIN and WEBHOOK_BASE_URL both unset)",
        "twilio_phone":    twilio_phone or "(EMPTY — TWILIO_PHONE_NUMBER not set and not in config.json)",
        "account_sid_set": bool(account_sid),
        "twiml_app_set":   bool(twiml_app),
        "lead_answered_url": f"{base}/dialer/voice/lead-answered" if base else "(base_url empty)",
        "agent_join_url":    f"{base}/dialer/voice/agent-join" if base else "(base_url empty)",
        "session_active":  sess_active,
        "eligible_leads":  sess_leads,
    }


_REACHED_DISPOSITIONS = ("Appointment Booked", "Follow Up 30 Day", "Follow Up 90 Day", "Follow Up (Manual)", "Send Info", "Not Interested")


@router.get("/dialer/history/booked")
async def get_history_booked():
    """Contacts behind the all-time 'Booked' stat."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, phone, business, owner, grade, opener, email,
                   website, city, state, call_attempts, notes
            FROM contacts
            WHERE status = 'appointment-booked'
            ORDER BY updated_at DESC
            LIMIT 200
            """,
        )
    return {"leads": [_row_to_lead(r) for r in rows]}


@router.get("/dialer/history/reached")
async def get_history_reached():
    """Contacts behind the all-time 'Reached' stat."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, phone, business, owner, grade, opener, email,
                   website, city, state, call_attempts, notes
            FROM contacts
            WHERE last_disposition = ANY($1::text[])
            ORDER BY updated_at DESC
            LIMIT 200
            """,
            list(_REACHED_DISPOSITIONS),
        )
    return {"leads": [_row_to_lead(r) for r in rows]}


@router.get("/dialer/incoming-calls")
async def get_incoming_calls(limit: int = 20):
    """Recent inbound callbacks — both missed and answered/dispositioned."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT cl.disposition, cl.notes, cl.started_at,
                   COALESCE(c.phone, cl.phone) AS phone,
                   c.business, c.owner, c.grade
            FROM call_logs cl
            LEFT JOIN contacts c ON c.id = cl.contact_id
            WHERE cl.direction = 'inbound'
            ORDER BY cl.started_at DESC NULLS LAST
            LIMIT $1
            """,
            limit,
        )
    return {"calls": [dict(r) for r in rows]}


@router.get("/dialer/history/by-disposition/{disposition}")
async def get_history_by_disposition(disposition: str):
    """Call log entries behind one row of the all-time breakdown."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT cl.disposition, cl.notes, cl.started_at,
                   c.business, c.owner, c.phone, c.grade
            FROM call_logs cl
            LEFT JOIN contacts c ON c.id = cl.contact_id
            WHERE cl.disposition = $1
            ORDER BY cl.started_at DESC NULLS LAST
            LIMIT 200
            """,
            disposition,
        )
    return {"calls": [dict(r) for r in rows]}


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/dialer/stats")
async def get_stats():
    pool = await get_pool()
    async with pool.acquire() as conn:
        total_calls = await conn.fetchval("SELECT COUNT(*) FROM call_logs")

        by_disposition = await conn.fetch(
            """
            SELECT disposition, COUNT(*) AS cnt
            FROM call_logs
            WHERE disposition IS NOT NULL
            GROUP BY disposition
            ORDER BY cnt DESC
            """
        )

        recent = await conn.fetch(
            """
            SELECT cl.disposition, cl.notes, cl.started_at,
                   c.business, c.owner, c.phone, c.grade
            FROM call_logs cl
            LEFT JOIN contacts c ON c.id = cl.contact_id
            ORDER BY cl.started_at DESC NULLS LAST
            LIMIT 20
            """
        )

        booked = await conn.fetchval(
            "SELECT COUNT(*) FROM contacts WHERE status = 'appointment-booked'"
        )
        reached = await conn.fetchval(
            "SELECT COUNT(*) FROM contacts WHERE last_disposition = ANY($1::text[])",
            list(_REACHED_DISPOSITIONS),
        )
        leads_ready = await conn.fetchval(
            f"SELECT COUNT(*) FROM contacts WHERE {_ELIGIBLE_WHERE}"
        )

    with engine._session["lock"]:
        active      = engine._session.get("active", False)
        session_id  = engine._session.get("id")
        eng_stats   = dict(engine._session.get("stats", {}))
        total_leads = engine._session.get("total_leads", 0)
        remaining   = len(engine._session.get("eligible_leads", []))

    calls_made  = eng_stats.get("calls_made", 0)
    dms_reached = eng_stats.get("dms_reached", 0)

    reach_rate = round(dms_reached / calls_made * 100, 1) if calls_made > 0 else 0

    return {
        "session": {
            "active":       active,
            "session_id":   session_id,
            "calls_made":   calls_made,
            "dms_reached":  dms_reached,
            "total_leads":  total_leads,
            "remaining":    remaining,
            "reach_rate":   reach_rate,
            "leads_ready":  leads_ready,
        },
        "history": {
            "total_calls":     total_calls,
            "total_booked":    booked,
            "total_reached":   reached,
            "by_disposition":  [dict(r) for r in by_disposition],
            "recent":          [dict(r) for r in recent],
        },
    }
