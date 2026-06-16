"""
Flask webhook server — handles all Twilio call events + serves the agent UI.

Start with: python run.py  (run.py starts this in a background thread)
Requires a public URL (ngrok in dev): ngrok http 5000
Set webhook_base_url in config.json to your ngrok URL.
"""

import json
import os
import threading

import requests
from flask import Flask, request, Response, send_file, jsonify
from twilio.twiml.voice_response import VoiceResponse, Dial, Conference, Gather, Say

import leads as leads_mod
import dialer as dialer_mod

_OS_URL  = os.environ.get("OS_API_URL", "").rstrip("/")
_OS_PASS = os.environ.get("OS_API_PASSWORD", "")


def _os_post(path, data):
    """Fire-and-forget POST to the DigiGrowth OS backend. Silently ignores failures."""
    if not _OS_URL:
        return
    try:
        requests.post(
            f"{_OS_URL}{path}",
            json=data,
            auth=("dialer", _OS_PASS),
            timeout=5,
        )
    except Exception as e:
        print(f"  ⚠️  OS API post failed ({path}): {e}")


def _norm(phone):
    """Strip +, spaces, dashes for phone number comparison."""
    return phone.replace("+", "").replace(" ", "").replace("-", "")

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

app = Flask(__name__)

# ── Shared session state (in-memory, lives for the duration of a run) ────────
_session = {
    "active":              False,
    "id":                  None,
    "config":              {},
    "call_sids":           {},    # phone → call_sid for current batch
    "bridged":             False,
    "bridged_sid":         None,
    "bridged_phone":       None,
    "dylan_sid":           None,
    "pending":             None,
    "show_classification": False,
    "total_leads":         0,
    "connected_at":        None,
    # Ring-time tracking
    "ring_start":          {},    # norm_phone → float (unix time when dialed)
    "ring_accum":          {},    # norm_phone → float (total seconds of ring time)
    "dial_count":          {},    # norm_phone → int (times dialed this session)
    "needs_retry":         set(), # norm_phones with < 30s ring time, need re-dial
    "machine_detected":    set(), # norm_phones where Twilio detected an automated system
    "gatekeeper_pending":  None,  # {"sid", "phone", "lead"} — held call awaiting connect/decline
    "batch_had_answer":    False, # True once any lead in the current batch answered
    "max_lines":           10,    # overridable from browser dropdown
    "end_requested":       False, # set by browser End Session button
    # In-session stats (OS CRM is the source of truth; these are for the end-of-session print)
    "stats": {"calls_made": 0, "dms_reached": 0},
    "lock":                threading.Lock(),
}


def init_session(config, session_id):
    with _session["lock"]:
        _session["active"]              = True
        _session["id"]                  = session_id
        _session["config"]              = config
        _session["call_sids"]           = {}
        _session["bridged"]             = False
        _session["bridged_sid"]         = None
        _session["bridged_phone"]       = None
        _session["dylan_sid"]           = None
        _session["pending"]             = None
        _session["show_classification"] = False
        _session["connected_at"]        = None
        _session["ring_start"]          = {}
        _session["ring_accum"]          = {}
        _session["dial_count"]          = {}
        _session["needs_retry"]         = set()
        _session["machine_detected"]    = set()
        _session["gatekeeper_pending"]  = None
        _session["batch_had_answer"]    = False
        _session["stats"]               = {"calls_made": 0, "dms_reached": 0}
        _session["eligible_leads"]      = []
        _session["max_lines"]           = config.get("max_parallel_lines", 10)
        _session["end_requested"]       = False
    threading.Thread(
        target=_os_post,
        args=("/api/dialer/session/start", {"session_id": session_id}),
        daemon=True,
    ).start()


def close_session():
    with _session["lock"]:
        _session["active"]              = False
        _session["bridged"]             = False
        _session["bridged_phone"]       = None
        _session["call_sids"]           = {}
        _session["dylan_sid"]           = None
        _session["pending"]             = None
        _session["show_classification"] = False
        _session["connected_at"]        = None
        _session["ring_start"]          = {}
        _session["ring_accum"]          = {}
        _session["dial_count"]          = {}
        _session["needs_retry"]         = set()
        _session["machine_detected"]    = set()
        _session["gatekeeper_pending"]  = None
        _session["batch_had_answer"]    = False
        # keep stats intact so run.py can print them after close_session()
    with _session["lock"]:
        stats = dict(_session.get("stats", {}))
    summary = (
        f"Session ended — {stats.get('calls_made', 0)} calls made, "
        f"{stats.get('dms_reached', 0)} DMs reached."
    )
    threading.Thread(
        target=_os_post,
        args=("/api/dialer/session/end", {}),
        daemon=True,
    ).start()
    threading.Thread(
        target=_os_post,
        args=("/api/dashboard/agent-messages", {"agent": "dialer", "message": summary}),
        daemon=True,
    ).start()


def set_total_leads(count):
    with _session["lock"]:
        _session["total_leads"] = count
    threading.Thread(
        target=_os_post,
        args=("/api/dialer/heartbeat", {"total_leads": count}),
        daemon=True,
    ).start()


def set_eligible_leads(leads):
    with _session["lock"]:
        _session["eligible_leads"] = list(leads)


def register_call_sids(sids_dict):
    """Called by run.py after dialing a batch to track active call SIDs."""
    with _session["lock"]:
        _session["call_sids"].update(sids_dict)


def register_batch_start(phones, start_time):
    """
    Record when a batch started ringing. Call this immediately before dial_batch.
    Increments dial_count so we know how many times each lead has been dialed.
    """
    with _session["lock"]:
        _session["batch_had_answer"] = False
        for phone in phones:
            norm = _norm(phone)
            _session["ring_start"][norm]  = start_time
            _session["dial_count"][norm]  = _session["dial_count"].get(norm, 0) + 1


def get_and_clear_retry():
    """Return and clear the set of norm_phones that need a retry dial."""
    with _session["lock"]:
        retry = set(_session["needs_retry"])
        _session["needs_retry"] = set()
        return retry


# ════════════════════════════════════════════════════════════════════════════
#  AGENT UI
# ════════════════════════════════════════════════════════════════════════════

@app.route("/agent", methods=["GET"])
def agent_ui():
    path = os.path.join(BASE_DIR, "agent.html")
    with open(path, encoding="utf-8") as f:
        html = f.read()
    calendly_url = _session.get("config", {}).get("calendly_url", "")
    html = html.replace("__CALENDLY_URL__", calendly_url)
    return Response(html, mimetype="text/html")


@app.route("/voicemail-audio", methods=["GET"])
def voicemail_audio():
    """Serve voicemail.mp3 from the project directory so Twilio gets clean audio."""
    path = os.path.join(BASE_DIR, "voicemail.mp3")
    if os.path.exists(path):
        return send_file(path, mimetype="audio/mpeg")
    return "", 404


# ════════════════════════════════════════════════════════════════════════════
#  TWILIO ACCESS TOKEN (for browser client)
# ════════════════════════════════════════════════════════════════════════════

@app.route("/token", methods=["GET"])
def get_token():
    from twilio.jwt.access_token import AccessToken
    from twilio.jwt.access_token.grants import VoiceGrant

    account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    api_key     = os.environ.get("TWILIO_API_KEY_SID", "")
    api_secret  = os.environ.get("TWILIO_API_KEY_SECRET", "")
    app_sid     = os.environ.get("TWILIO_TWIML_APP_SID", "")

    if not all([account_sid, api_key, api_secret, app_sid]):
        return jsonify({"error": "Missing Twilio credentials — check .env for TWILIO_API_KEY_SID, TWILIO_API_KEY_SECRET, TWILIO_TWIML_APP_SID"}), 500

    token = AccessToken(account_sid, api_key, api_secret, identity="agent", ttl=3600)
    grant = VoiceGrant(outgoing_application_sid=app_sid, incoming_allow=True)
    token.add_grant(grant)

    return jsonify({"token": token.to_jwt()})


# ════════════════════════════════════════════════════════════════════════════
#  BROWSER AGENT JOINS CONFERENCE
# ════════════════════════════════════════════════════════════════════════════

@app.route("/voice/agent-join", methods=["POST"])
def agent_join():
    """
    Called by Twilio when the browser client connects.
    Puts the agent (Dylan) into the conference room with hold music.
    Leads that answer will join the same conference automatically.
    """
    session_id = request.form.get("session_id") or _session.get("id")
    call_sid   = request.form.get("CallSid", "")

    with _session["lock"]:
        _session["dylan_sid"] = call_sid

    response = VoiceResponse()
    dial     = response.dial()
    dial.conference(
        f"dialer-{session_id}",
        start_conference_on_enter=True,
        end_conference_on_exit=True,
        beep=False,
    )
    return Response(str(response), mimetype="text/xml")


# ════════════════════════════════════════════════════════════════════════════
#  SESSION STATE API (polled by browser)
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/session", methods=["GET"])
def api_session():
    with _session["lock"]:
        pending      = _session.get("pending")
        show_cls     = _session.get("show_classification", False)
        active       = _session.get("active")
        bridged      = _session.get("bridged")
        connected_at = _session.get("connected_at")
        session_id   = _session.get("id")
        stats        = dict(_session.get("stats", {}))
        total        = _session.get("total_leads", 0)
        gk           = _session.get("gatekeeper_pending")

    calls_made  = stats.get("calls_made", 0)
    dms_reached = stats.get("dms_reached", 0)
    remaining   = max(0, total - calls_made)

    if bridged:
        status = "connected"
    elif show_cls:
        status = "classify"
    elif active:
        status = "waiting"
    else:
        status = "idle"

    return jsonify({
        "active":              active,
        "session_id":          session_id,
        "status":              status,
        "show_classification": show_cls,
        "current_lead":        pending,
        "connected_at":        connected_at,
        "gatekeeper":          gk["lead"] if gk else None,
        "stats": {
            "calls_made":  calls_made,
            "remaining":   remaining,
            "dms_reached": dms_reached,
            "total":       total,
        },
    })


# ════════════════════════════════════════════════════════════════════════════
#  CLASSIFICATION API (called by browser button click)
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/end-call", methods=["POST"])
def api_end_call():
    """
    Hang up the lead's call and show classification UI.
    Sets show_classification=True immediately so _wait_for_batch keeps looping
    (avoids race with the Twilio status callback arriving a second later).
    bridged_phone/bridged_sid are kept so call_status can recognise this as the
    bridged lead's completed call and not double-count.
    """
    with _session["lock"]:
        bridged_sid                    = _session.get("bridged_sid")
        _session["bridged"]            = False
        _session["show_classification"] = True
    if bridged_sid:
        dialer_mod.hangup_call(bridged_sid)
    return jsonify({"ok": True})


@app.route("/api/classify", methods=["POST"])
def api_classify():
    data        = request.get_json(force=True) or {}
    disposition = data.get("disposition", "No Answer")
    notes       = data.get("notes", "")

    with _session["lock"]:
        pending                        = _session.get("pending")
        connected_at                   = _session.get("connected_at")
        _session["show_classification"] = False
        _session["pending"]            = None
        _session["connected_at"]       = None

    if pending:
        name = pending.get("business") or pending.get("owner") or pending.get("phone", "unknown")
        threading.Thread(
            target=_os_post,
            args=("/api/dialer/disposition", {
                "phone":       pending.get("phone", ""),
                "disposition": disposition,
                "notes":       notes,
            }),
            daemon=True,
        ).start()
        print(f"  ✅ OS updated: {name} → {disposition}")

        # Update in-session stats
        with _session["lock"]:
            _session["stats"]["calls_made"] += 1
            if disposition in ("Appointment Booked", "Follow Up", "Send Info"):
                _session["stats"]["dms_reached"] += 1

        with _session["lock"]:
            stats = dict(_session["stats"])
            total = _session["total_leads"]
        threading.Thread(
            target=_os_post,
            args=("/api/dialer/heartbeat", {
                "calls_made":  stats["calls_made"],
                "dms_reached": stats["dms_reached"],
                "total_leads": total,
            }),
            daemon=True,
        ).start()

    return jsonify({"ok": True})


# ════════════════════════════════════════════════════════════════════════════
#  HEALTH
# ════════════════════════════════════════════════════════════════════════════

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "session_active": _session["active"]})


@app.route("/api/set-lines", methods=["POST"])
def api_set_lines():
    data  = request.get_json(force=True) or {}
    lines = max(1, int(data.get("lines", 10)))
    with _session["lock"]:
        _session["max_lines"] = lines
    print(f"  🔢 Parallel lines set to {lines}")
    return jsonify({"ok": True, "max_lines": lines})


@app.route("/api/end-session", methods=["POST"])
def api_end_session():
    with _session["lock"]:
        _session["end_requested"] = True
    print("  ⏹️  End session requested from browser")
    return jsonify({"ok": True})


# ════════════════════════════════════════════════════════════════════════════
#  LEAD ANSWERED
# ════════════════════════════════════════════════════════════════════════════

@app.route("/voice/lead-answered", methods=["POST"])
def lead_answered():
    """
    Twilio calls this when a lead picks up.
    - Confirmed voicemail / fax (machine_end_*): drop immediately, GHL updated via call_status.
    - machine_start (IVR / gatekeeper): bridge to Dylan so he can navigate to the owner.
    - Already bridged or session inactive: play "sorry wrong number" and hang up.
    - Human: add lead directly to the conference (Dylan is already there).
    """
    from datetime import datetime, timezone

    try:
      return _lead_answered_inner()
    except Exception as exc:
        import traceback
        print(f"  ❌ lead_answered exception: {exc}")
        traceback.print_exc()
        r = VoiceResponse(); r.hangup()
        return Response(str(r), mimetype="text/xml")


def _lead_answered_inner():
    from datetime import datetime, timezone

    answered_sid = request.form.get("CallSid", "")
    phone        = request.form.get("To", "")
    answered_by  = request.form.get("AnsweredBy", "")

    response = VoiceResponse()

    # Confirmed voicemail or fax — full greeting played, nobody coming. Drop immediately.
    if answered_by in ("machine_end_beep", "machine_end_silence", "machine_end_other", "fax"):
        norm = _norm(phone)
        with _session["lock"]:
            _session["machine_detected"].add(norm)
        response.hangup()
        return Response(str(response), mimetype="text/xml")

    # machine_start = possible IVR/gatekeeper — hold the call silently and show
    # a popup so Dylan can choose to connect or decline before committing a line.
    if answered_by == "machine_start":
        with _session["lock"]:
            if not _session["active"] or _session["bridged"]:
                response.hangup()
                return Response(str(response), mimetype="text/xml")
            norm_phone = _norm(phone)
            lead_data  = next(
                (l for l in _session.get("eligible_leads", []) if _norm(l.get("phone", "")) == norm_phone),
                {}
            )
            old_gk = _session.get("gatekeeper_pending")
            _session["gatekeeper_pending"] = {"sid": answered_sid, "phone": phone, "lead": {**lead_data, "phone": phone}}

        if old_gk and old_gk.get("sid") != answered_sid:
            dialer_mod.hangup_call(old_gk["sid"])

        # Hold the call silently for up to 60 s — user connects or declines via popup
        response.pause(length=60)
        response.hangup()
        return Response(str(response), mimetype="text/xml")

    # Human answered — bridge immediately
    with _session["lock"]:
        if not _session["active"] or _session["bridged"]:
            response.say(
                "Sorry about that, we accidentally dialed you. Have a great day!",
                voice="Polly.Matthew"
            )
            response.hangup()
            return Response(str(response), mimetype="text/xml")

        _session["bridged"]             = True
        _session["bridged_sid"]         = answered_sid
        _session["bridged_phone"]       = _norm(phone)
        _session["show_classification"] = False
        _session["connected_at"]        = datetime.now(timezone.utc).isoformat()
        _session["batch_had_answer"]    = True
        session_id = _session["id"]

        norm_phone = _norm(phone)
        lead_data  = next(
            (l for l in _session.get("eligible_leads", []) if _norm(l.get("phone", "")) == norm_phone),
            {}
        )
        _session["pending"] = {**lead_data, "phone": phone}

        # Cancel any pending gatekeeper when a real human answers
        gk_to_cancel = _session.get("gatekeeper_pending")
        _session["gatekeeper_pending"] = None
        overflow = {p: s for p, s in _session["call_sids"].items() if s != answered_sid}

    if gk_to_cancel and gk_to_cancel.get("sid") and gk_to_cancel["sid"] != answered_sid:
        dialer_mod.hangup_call(gk_to_cancel["sid"])

    if overflow:
        dialer_mod.cancel_overflow_calls(overflow, answered_sid)

    dial = response.dial()
    dial.conference(
        f"dialer-{session_id}",
        start_conference_on_enter=True,
        end_conference_on_exit=False,
        beep=False,
    )
    return Response(str(response), mimetype="text/xml")


# ════════════════════════════════════════════════════════════════════════════
#  OVERFLOW LEAD ANSWERED (when parallel batch >1 picks up)
# ════════════════════════════════════════════════════════════════════════════

@app.route("/voice/lead-overflow", methods=["POST"])
def lead_overflow():
    response = VoiceResponse()
    response.say("Sorry, I dialed the wrong number. Have a great day!", voice="Polly.Matthew")
    response.hangup()
    return Response(str(response), mimetype="text/xml")


# ════════════════════════════════════════════════════════════════════════════
#  CALL STATUS CALLBACK
# ════════════════════════════════════════════════════════════════════════════

@app.route("/voice/status", methods=["POST"])
def call_status():
    """
    Twilio fires this for every status change on outbound lead calls.

    A call only counts as a dial when the lead reaches either:
      - 30 seconds of total accumulated ring time across all dials, OR
      - 2 total dials (regardless of ring time)

    - canceled: dropped when another answered. Accumulate actual ring time.
                If threshold not met → queue for retry.
    - no-answer: rang for the full 30s timeout → threshold met → count.
    - busy/failed: fires quickly (low ring time). Apply threshold; retry if not met.
    - completed (bridged lead): real conversation. api_classify handles GHL.
    - completed (overflow): they answered → always count (threshold is irrelevant).
    """
    import time as _time

    status   = request.form.get("CallStatus", "")
    call_sid = request.form.get("CallSid", "")
    phone    = request.args.get("phone", request.form.get("To", ""))

    if not phone or status not in ("no-answer", "busy", "failed", "completed", "canceled"):
        return "", 204

    # If the gatekeeper hold call ended (timed out or declined), clear the popup
    with _session["lock"]:
        gk = _session.get("gatekeeper_pending")
        if gk and gk.get("sid") == call_sid:
            _session["gatekeeper_pending"] = None

    norm         = _norm(phone)
    now          = _time.time()
    should_count = False

    with _session["lock"]:
        bridged_phone   = _session.get("bridged_phone", "") or ""
        is_bridged_lead = norm == _norm(bridged_phone)
        ring_start      = _session["ring_start"].get(norm, now)
        dial_count      = _session["dial_count"].get(norm, 1)
        config          = _session.get("config", {})

        if status == "canceled":
            ring_duration = max(0.0, now - ring_start)
            _session["ring_accum"][norm] = _session["ring_accum"].get(norm, 0.0) + ring_duration
            ring_total = _session["ring_accum"][norm]

            if ring_total < 30 and dial_count < 2:
                _session["needs_retry"].add(norm)
                should_count = False
            else:
                _session["needs_retry"].discard(norm)
                should_count = True

        elif is_bridged_lead and status == "completed":
            # Real conversation — api_classify handles GHL, just show the UI
            _session["bridged"]             = False
            _session["bridged_phone"]       = None
            _session["bridged_sid"]         = None
            _session["show_classification"] = True
            should_count = False

        else:
            ring_duration = max(0.0, now - ring_start)
            _session["ring_accum"][norm] = _session["ring_accum"].get(norm, 0.0) + ring_duration
            ring_total    = _session["ring_accum"][norm]
            is_machine    = norm in _session["machine_detected"]

            if is_machine:
                # Automated system — drop immediately, remove needs-call tag, no retry
                _session["needs_retry"].discard(norm)
                _session["machine_detected"].discard(norm)
                should_count = True
            elif status == "completed":
                # Overflow human — answered briefly, always count
                _session["needs_retry"].discard(norm)
                should_count = True
            elif ring_total < 30 and dial_count < 2:
                _session["needs_retry"].add(norm)
                should_count = False
            else:
                _session["needs_retry"].discard(norm)
                should_count = True

        lead_state = {"phone": phone}

    if should_count:
        with _session["lock"]:
            _session["stats"]["calls_made"] += 1

        threading.Thread(
            target=_os_post,
            args=("/api/dialer/disposition", {
                "phone":       phone,
                "disposition": "No Answer",
            }),
            daemon=True,
        ).start()

    return "", 204


# ════════════════════════════════════════════════════════════════════════════
#  GATEKEEPER — CONNECT / DECLINE / JOIN
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/gatekeeper/connect", methods=["POST"])
def api_gatekeeper_connect():
    """Dylan clicked Connect on the gatekeeper popup — redirect the held call into the conference."""
    from datetime import datetime, timezone

    with _session["lock"]:
        gk = _session.get("gatekeeper_pending")
        if not gk or _session.get("bridged"):
            return jsonify({"ok": False})

        _session["bridged"]             = True
        _session["bridged_sid"]         = gk["sid"]
        _session["bridged_phone"]       = _norm(gk["phone"])
        _session["show_classification"] = False
        _session["connected_at"]        = datetime.now(timezone.utc).isoformat()
        _session["batch_had_answer"]    = True
        _session["pending"]             = {**gk["lead"], "gatekeeper": True}
        _session["gatekeeper_pending"]  = None
        session_id = _session["id"]
        base_url   = _session["config"].get("webhook_base_url", "").rstrip("/")

    dialer_mod.redirect_call(gk["sid"], f"{base_url}/voice/gatekeeper-join?session_id={session_id}")
    return jsonify({"ok": True})


@app.route("/api/gatekeeper/decline", methods=["POST"])
def api_gatekeeper_decline():
    """Dylan clicked Decline — hang up the held call, count it as no-answer."""
    with _session["lock"]:
        gk = _session.get("gatekeeper_pending")
        _session["gatekeeper_pending"] = None

    if gk and gk.get("sid"):
        dialer_mod.hangup_call(gk["sid"])
    return jsonify({"ok": True})


@app.route("/voice/gatekeeper-join", methods=["POST"])
def gatekeeper_join():
    """TwiML endpoint that connects the redirected gatekeeper call into the conference."""
    session_id = request.args.get("session_id") or _session.get("id")
    response   = VoiceResponse()
    dial = response.dial()
    dial.conference(
        f"dialer-{session_id}",
        start_conference_on_enter=True,
        end_conference_on_exit=False,
        beep=False,
    )
    return Response(str(response), mimetype="text/xml")


# ════════════════════════════════════════════════════════════════════════════
#  SERVER START
# ════════════════════════════════════════════════════════════════════════════

def start_server(config, port=None):
    port = port or config.get("webhook_port", 5000)
    print(f"🌐 Webhook server starting on port {port}")
    print(f"   Public URL: {config.get('webhook_base_url', '(not set)')}")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
