"""
Flask webhook server — handles all Twilio call events + serves the agent UI.

Start with: python run.py  (run.py starts this in a background thread)
Requires a public URL (ngrok in dev): ngrok http 5000
Set webhook_base_url in config.json to your ngrok URL.
"""

import json
import os
import threading

from flask import Flask, request, Response, send_file, jsonify
from twilio.twiml.voice_response import VoiceResponse, Dial, Conference, Gather, Say

import leads as leads_mod
import dialer as dialer_mod

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
    "bridged_phone":       None,  # phone of lead currently on the call
    "dylan_sid":           None,  # browser client call SID
    "pending":             None,  # lead dict currently being classified
    "show_classification": False,
    "total_leads":         0,
    "connected_at":        None,  # ISO timestamp when lead connected
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


def set_total_leads(count):
    with _session["lock"]:
        _session["total_leads"] = count


def register_call_sids(sids_dict):
    """Called by run.py after dialing a batch to track active call SIDs."""
    with _session["lock"]:
        _session["call_sids"].update(sids_dict)


# ════════════════════════════════════════════════════════════════════════════
#  AGENT UI
# ════════════════════════════════════════════════════════════════════════════

@app.route("/agent", methods=["GET"])
def agent_ui():
    return send_file(os.path.join(BASE_DIR, "agent.html"))


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
        wait_url="http://twimlets.com/holdmusic?Bucket=com.twilio.music.classical",
        beep=False,
    )
    return Response(str(response), mimetype="text/xml")


# ════════════════════════════════════════════════════════════════════════════
#  SESSION STATE API (polled by browser)
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/session", methods=["GET"])
def api_session():
    try:
        state      = leads_mod.load_state()
        leads_data = state.get("leads", {})
    except Exception:
        leads_data = {}

    calls_made  = sum(1 for v in leads_data.values() if v.get("attempts", 0) > 0)
    dms_reached = sum(1 for v in leads_data.values()
                      if v.get("disposition") in ("Appointment Booked", "Follow Up", "Send Info"))
    total     = _session.get("total_leads", 0)
    remaining = max(0, total - calls_made)

    with _session["lock"]:
        pending      = _session.get("pending")
        show_cls     = _session.get("show_classification", False)
        active       = _session.get("active")
        bridged      = _session.get("bridged")
        connected_at = _session.get("connected_at")
        session_id   = _session.get("id")

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

@app.route("/api/classify", methods=["POST"])
def api_classify():
    data        = request.get_json(force=True) or {}
    disposition = data.get("disposition", "No Answer")
    notes       = data.get("notes", "")

    with _session["lock"]:
        pending                        = _session.get("pending")
        _session["show_classification"] = False
        _session["pending"]            = None
        _session["connected_at"]       = None

    if pending:
        phone = pending.get("phone")
        state = leads_mod.load_state()
        leads_mod.record_disposition(state, phone, disposition)
        leads_mod.save_state(state)

        # Add call note to GHL if notes provided
        if notes.strip():
            import ghl as ghl_mod
            config = _session.get("config", {})
            if config:
                try:
                    contact_id = ghl_mod.get_or_create_contact(config, pending)
                    if contact_id:
                        ghl_mod.add_note(config, contact_id, f"[{disposition}] {notes}")
                except Exception:
                    pass

    return jsonify({"ok": True})


# ════════════════════════════════════════════════════════════════════════════
#  HEALTH
# ════════════════════════════════════════════════════════════════════════════

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "session_active": _session["active"]})


# ════════════════════════════════════════════════════════════════════════════
#  LEAD ANSWERED
# ════════════════════════════════════════════════════════════════════════════

@app.route("/voice/lead-answered", methods=["POST"])
def lead_answered():
    """
    Twilio calls this when a lead picks up.
    - Machine detected: hang up.
    - Already bridged or session inactive: hang up.
    - Otherwise: add lead directly to the conference (Dylan is already there).
    """
    from datetime import datetime, timezone

    answered_sid = request.form.get("CallSid", "")
    phone        = request.form.get("To", "")
    answered_by  = request.form.get("AnsweredBy", "")

    response = VoiceResponse()

    if answered_by in ("machine_start", "machine_end_beep", "machine_end_silence", "machine_end_other", "fax"):
        response.hangup()
        return Response(str(response), mimetype="text/xml")

    with _session["lock"]:
        if not _session["active"] or _session["bridged"]:
            response.hangup()
            return Response(str(response), mimetype="text/xml")

        _session["bridged"]             = True
        _session["bridged_sid"]         = answered_sid
        _session["bridged_phone"]       = phone
        _session["show_classification"] = False
        _session["connected_at"]        = datetime.now(timezone.utc).isoformat()
        session_id = _session["id"]

        state     = leads_mod.load_state()
        lead_data = state["leads"].get(phone, {"phone": phone, "business": ""})
        _session["pending"] = lead_data

        overflow = {p: s for p, s in _session["call_sids"].items() if s != answered_sid}

    if overflow:
        dialer_mod.cancel_overflow_calls(overflow, answered_sid)

    # Add lead to conference — Dylan is already there, call starts immediately
    dial = response.dial()
    dial.conference(
        f"dialer-{session_id}",
        start_conference_on_enter=True,
        end_conference_on_exit=False,  # lead leaving doesn't end conference; Dylan stays on hold
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
    - no-answer/busy/failed: increment attempt count.
    - completed: if this was the bridged lead, show classification UI.
    """
    status = request.form.get("CallStatus", "")
    phone  = request.args.get("phone", request.form.get("To", ""))

    if status in ("no-answer", "busy", "failed") and phone:
        state = leads_mod.load_state()
        leads_mod.record_attempt(state, phone)
        leads_mod.save_state(state)

    if status == "completed" and phone:
        with _session["lock"]:
            if phone == _session.get("bridged_phone"):
                _session["bridged"]             = False
                _session["bridged_phone"]       = None
                _session["bridged_sid"]         = None
                _session["show_classification"] = True
                # Dylan stays in conference with hold music — page shows buttons

    return "", 204


# ════════════════════════════════════════════════════════════════════════════
#  SERVER START
# ════════════════════════════════════════════════════════════════════════════

def start_server(config, port=None):
    port = port or config.get("webhook_port", 5000)
    print(f"🌐 Webhook server starting on port {port}")
    print(f"   Public URL: {config.get('webhook_base_url', '(not set)')}")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
