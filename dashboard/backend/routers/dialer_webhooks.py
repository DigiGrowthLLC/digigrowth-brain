"""
Public Twilio voice webhook router — no auth required.
Twilio posts here for every call event. Ported from parallel-dialer/webhook.py.

Mounted at root (no /api prefix) so URLs match what Twilio expects:
  POST /dialer/voice/agent-join
  POST /dialer/voice/lead-answered
  POST /dialer/voice/lead-overflow
  POST /dialer/voice/status
  POST /dialer/voice/gatekeeper-join
"""

import logging
import sys
import threading
import time as _time
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import Response
from twilio.twiml.voice_response import VoiceResponse

import dialer_engine as engine

_log = logging.getLogger(__name__)

router = APIRouter()


# ── Agent (Dylan's browser) joins the conference ───────────────────────────────

@router.post("/dialer/voice/agent-join")
async def agent_join(request: Request):
    form       = await request.form()
    session_id = form.get("session_id") or request.query_params.get("session_id") or engine._session.get("id")
    call_sid   = form.get("CallSid", "")

    with engine._session["lock"]:
        engine._session["dylan_sid"] = call_sid

    # Diagnostic: verify Railway captures output before the thread starts
    print(f"  dialer: agent_join — session={session_id} sid={call_sid}", flush=True)
    sys.stdout.flush()
    _log.info(f"dialer: agent_join — session={session_id}")

    response = VoiceResponse()
    dial     = response.dial()
    dial.conference(
        f"dialer-{session_id}",
        start_conference_on_enter=True,
        end_conference_on_exit=True,
        beep=False,
    )
    # Use a plain daemon thread — asyncio.create_task and BackgroundTask both
    # silently fail in this Starlette/uvicorn context. threading.Thread is
    # independent of the event loop and guaranteed to execute.
    threading.Thread(target=_auto_first_dial_sync, args=(session_id,), daemon=True).start()
    return Response(str(response), media_type="text/xml")


def _auto_first_dial_sync(session_id: str):
    """Fire the first dial-batch synchronously in a background thread."""
    # Claim auto_dialed immediately so the frontend's dial-batch guard fires first
    # and doesn't race this thread for the eligible_leads queue.
    engine._session["auto_dialed"] = True
    print(f"  dialer: _auto_first_dial_sync STARTED session={session_id}", flush=True)
    _log.info(f"dialer: _auto_first_dial_sync STARTED session={session_id}")
    try:
        _time.sleep(0.05)  # 50ms — enough for conference to initialise
        print("  dialer: _auto_first_dial_sync AFTER SLEEP — acquiring lock", flush=True)

        active       = engine._session.get("active")
        current_id   = engine._session.get("id")
        print(f"  dialer: _auto_first_dial_sync — active={active} id={current_id}", flush=True)

        if not active:
            print("  dialer: auto_first_dial — session not active", flush=True)
            return
        if current_id != session_id:
            print(f"  dialer: auto_first_dial — session changed ({current_id} != {session_id})", flush=True)
            return

        with engine._session["lock"]:
            print("  dialer: _auto_first_dial_sync — LOCK ACQUIRED", flush=True)
            max_lines = engine._session.get("max_lines", 5)
            batch     = engine._session["eligible_leads"][:max_lines]
            engine._session["eligible_leads"] = engine._session["eligible_leads"][max_lines:]

            if not batch:
                print("  dialer: auto_first_dial — no eligible leads", flush=True)
                return

            now = _time.time()
            engine._session["batch_had_answer"] = False
            for lead in batch:
                norm = engine._norm(lead["phone"])
                engine._session["ring_start"][norm]  = now
                engine._session["dial_count"][norm]  = engine._session["dial_count"].get(norm, 0) + 1

            s_id   = engine._session["id"]
            config = engine._session["config"]

        base = engine.base_url()
        if not base:
            print("  dialer: auto_first_dial — base_url empty", flush=True)
            return

        phones = [l["phone"] for l in batch]
        print(f"  dialer: auto_first_dial — dialing {len(phones)} leads: {phones}", flush=True)

        sids = {}
        errors = []
        for phone in phones:
            _, sid, err = engine._dial_lead_sync(phone, s_id, base, config)
            if sid:
                sids[phone] = sid
            if err:
                errors.append(err)

        with engine._session["lock"]:
            engine._session["call_sids"].update(sids)

        print(f"  dialer: auto_first_dial — placed {len(sids)} calls, errors: {errors}", flush=True)

    except Exception as e:
        import traceback
        print(f"  dialer: auto_first_dial failed: {e}", flush=True)
        traceback.print_exc()


# ── Lead picks up ─────────────────────────────────────────────────────────────

@router.post("/dialer/voice/lead-answered")
async def lead_answered(request: Request):
    try:
        return await _lead_answered_inner(request)
    except Exception as exc:
        import traceback
        print(f"  dialer: lead_answered exception: {exc}")
        traceback.print_exc()
        r = VoiceResponse()
        r.hangup()
        return Response(str(r), media_type="text/xml")


async def _lead_answered_inner(request: Request):
    form        = await request.form()
    answered_sid = form.get("CallSid", "")
    phone        = form.get("To", "")
    answered_by  = form.get("AnsweredBy", "")

    response = VoiceResponse()

    # Bridge into conference immediately — no AMD delay
    with engine._session["lock"]:
        if not engine._session["active"] or engine._session["bridged"]:
            response.say(
                "Sorry about that, we accidentally dialed you. Have a great day!",
                voice="Polly.Matthew",
            )
            response.hangup()
            return Response(str(response), media_type="text/xml")

        engine._session["bridged"]             = True
        engine._session["bridged_sid"]         = answered_sid
        engine._session["bridged_phone"]       = engine._norm(phone)
        engine._session["show_classification"] = False
        engine._session["connected_at"]        = datetime.now(timezone.utc).isoformat()
        engine._session["batch_had_answer"]    = True
        session_id = engine._session["id"]

        norm_phone = engine._norm(phone)
        lead_data  = next(
            (l for l in engine._session.get("eligible_leads", [])
             if engine._norm(l.get("phone", "")) == norm_phone),
            engine._session["leads_by_phone"].get(norm_phone, {}),
        )
        engine._session["pending"] = {**lead_data, "phone": phone}

        gk_to_cancel = engine._session.get("gatekeeper_pending")
        engine._session["gatekeeper_pending"] = None
        overflow = {p: s for p, s in engine._session["call_sids"].items() if s != answered_sid}

    if gk_to_cancel and gk_to_cancel.get("sid") and gk_to_cancel["sid"] != answered_sid:
        engine.hangup_call(gk_to_cancel["sid"])

    if overflow:
        engine.cancel_overflow_calls(overflow, answered_sid)

    dial = response.dial()
    dial.conference(
        f"dialer-{session_id}",
        start_conference_on_enter=True,
        end_conference_on_exit=False,
        beep=False,
    )
    return Response(str(response), media_type="text/xml")


# ── Overflow — extra pickup while already bridged ─────────────────────────────

@router.post("/dialer/voice/lead-overflow")
async def lead_overflow():
    response = VoiceResponse()
    response.say("Sorry, I dialed the wrong number. Have a great day!", voice="Polly.Matthew")
    response.hangup()
    return Response(str(response), media_type="text/xml")


# ── Call status callback ───────────────────────────────────────────────────────

@router.post("/dialer/voice/status")
async def call_status(request: Request):
    form     = await request.form()
    status   = form.get("CallStatus", "")
    call_sid = form.get("CallSid", "")
    phone    = request.query_params.get("phone") or form.get("To", "")

    if not phone or status not in ("no-answer", "busy", "failed", "completed", "canceled"):
        return Response("", status_code=204)

    if status == "failed":
        print(f"  dialer: CALL FAILED to {phone} (sid={call_sid}) — check Twilio console for error code")

    # Clear gatekeeper popup if the held call timed out
    with engine._session["lock"]:
        gk = engine._session.get("gatekeeper_pending")
        if gk and gk.get("sid") == call_sid:
            engine._session["gatekeeper_pending"] = None

    norm         = engine._norm(phone)
    now          = _time.time()
    should_count = False

    with engine._session["lock"]:
        bridged_phone   = engine._session.get("bridged_phone", "") or ""
        # Use last-10-digit match: status callback phone may lack the +1 prefix
        # that Twilio's To field includes (e.g. "7542485326" vs "17542485326")
        is_bridged_lead = norm[-10:] == engine._norm(bridged_phone)[-10:]
        ring_start      = engine._session["ring_start"].get(norm, now)
        dial_count      = engine._session["dial_count"].get(norm, 1)

        if status == "canceled":
            ring_duration = max(0.0, now - ring_start)
            engine._session["ring_accum"][norm] = (
                engine._session["ring_accum"].get(norm, 0.0) + ring_duration
            )
            ring_total = engine._session["ring_accum"][norm]

            if ring_total < 30 and dial_count < 2:
                engine._session["needs_retry"].add(norm)
                should_count = False
            else:
                engine._session["needs_retry"].discard(norm)
                should_count = True

        elif is_bridged_lead and status == "completed":
            engine._session["bridged"]             = False
            engine._session["bridged_phone"]       = None
            engine._session["bridged_sid"]         = None
            engine._session["show_classification"] = True
            should_count = False

        else:
            ring_duration = max(0.0, now - ring_start)
            engine._session["ring_accum"][norm] = (
                engine._session["ring_accum"].get(norm, 0.0) + ring_duration
            )
            ring_total = engine._session["ring_accum"][norm]

            if status == "completed":
                engine._session["needs_retry"].discard(norm)
                should_count = True
            elif ring_total < 30 and dial_count < 2:
                engine._session["needs_retry"].add(norm)
                should_count = False
            else:
                engine._session["needs_retry"].discard(norm)
                should_count = True

    if should_count:
        with engine._session["lock"]:
            engine._session["stats"]["calls_made"] += 1

        # Log no-answer to DB asynchronously
        import asyncio
        asyncio.create_task(_log_no_answer(phone))

    return Response("", status_code=204)


async def _log_no_answer(phone: str):
    try:
        from db import get_pool
        from models import DISPOSITION_TO_STATUS
        pool = await get_pool()
        async with pool.acquire() as conn:
            contact = await conn.fetchrow("SELECT id FROM contacts WHERE phone = $1", phone)
            contact_id = contact["id"] if contact else None
            await conn.execute(
                "INSERT INTO call_logs (contact_id, disposition) VALUES ($1, $2)",
                contact_id, "No Answer",
            )
            if contact_id:
                new_status = DISPOSITION_TO_STATUS.get("No Answer")
                updated = await conn.fetchrow(
                    """
                    UPDATE contacts SET
                        call_attempts  = call_attempts + 1,
                        last_disposition = $1,
                        last_called_at = now(),
                        status         = COALESCE($2, status),
                        updated_at     = now()
                    WHERE id = $3
                    RETURNING call_attempts, phone, owner
                    """,
                    "No Answer", new_status, contact_id,
                )
                if updated and updated["call_attempts"] >= 3:
                    await conn.execute(
                        "UPDATE contacts SET status='sms-handoff' WHERE id=$1", contact_id,
                    )
                    from routers.sms import _send_twilio
                    owner = updated["owner"] or "there"
                    msg = (
                        f"Hey {owner}, this is Dylan from DigiGrowth — "
                        "I tried reaching you a few times. Wanted to connect about growing "
                        "your business online. Reply back if you'd like to chat!"
                    )
                    try:
                        _send_twilio(updated["phone"], msg)
                    except Exception:
                        pass
    except Exception as e:
        print(f"  dialer: _log_no_answer failed for {phone}: {e}")


# ── Gatekeeper redirected into conference ────────────────────────────────────

@router.post("/dialer/voice/amd-result")
async def amd_result(request: Request):
    """Async AMD callback — fires ~2-3s after answer with human/machine verdict."""
    form        = await request.form()
    answered_by = form.get("AnsweredBy", "")
    call_sid    = form.get("CallSid", "")
    phone       = request.query_params.get("phone") or form.get("To", "")

    machines = ("machine_end_beep", "machine_end_silence", "machine_end_other", "fax")
    if answered_by not in machines:
        return Response("", status_code=204)

    # Machine detected — hang up and unbridge if this call was already bridged
    with engine._session["lock"]:
        is_bridged = engine._session.get("bridged_sid") == call_sid

    engine.hangup_call(call_sid)
    print(f"  dialer: AMD — machine detected ({answered_by}) on {phone}, hanging up", flush=True)

    if is_bridged:
        with engine._session["lock"]:
            engine._session["bridged"]             = False
            engine._session["bridged_sid"]         = None
            engine._session["bridged_phone"]       = None
            engine._session["show_classification"] = True

    return Response("", status_code=204)


@router.post("/dialer/voice/gatekeeper-join")
async def gatekeeper_join(request: Request):
    session_id = request.query_params.get("session_id") or engine._session.get("id")
    response   = VoiceResponse()
    dial       = response.dial()
    dial.conference(
        f"dialer-{session_id}",
        start_conference_on_enter=True,
        end_conference_on_exit=False,
        beep=False,
    )
    return Response(str(response), media_type="text/xml")
