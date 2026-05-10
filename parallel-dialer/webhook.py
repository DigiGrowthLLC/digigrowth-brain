"""
Flask webhook server — handles all Twilio call events.

Start with: python run.py  (run.py starts this in a background thread)
Requires a public URL (ngrok in dev): ngrok http 5000
Set webhook_base_url in config.json to your ngrok URL.
"""

import json
import os
import threading

from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse, Dial, Conference, Gather, Say

import leads as leads_mod
import dialer as dialer_mod

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

app = Flask(__name__)

# ── Shared session state (in-memory, lives for the duration of a run) ────────
_session = {
    "active":      False,
    "id":          None,
    "config":      {},
    "call_sids":   {},   # phone → call_sid for current batch
    "bridged":     False,
    "bridged_sid": None,
    "pending":     None,  # lead dict currently being classified
    "lock":        threading.Lock(),
}


def init_session(config, session_id):
    with _session["lock"]:
        _session["active"]      = True
        _session["id"]          = session_id
        _session["config"]      = config
        _session["call_sids"]   = {}
        _session["bridged"]     = False
        _session["bridged_sid"] = None
        _session["pending"]     = None


def close_session():
    with _session["lock"]:
        _session["active"]    = False
        _session["bridged"]   = False
        _session["call_sids"] = {}
        _session["pending"]   = None


def register_call_sids(sids_dict):
    """Called by run.py after dialing a batch to track active call SIDs."""
    with _session["lock"]:
        _session["call_sids"].update(sids_dict)


# ════════════════════════════════════════════════════════════════════════════
#  HEALTH
# ════════════════════════════════════════════════════════════════════════════

@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok", "session_active": _session["active"]}


# ════════════════════════════════════════════════════════════════════════════
#  LEAD ANSWERED
# ════════════════════════════════════════════════════════════════════════════

@app.route("/voice/lead-answered", methods=["POST"])
def lead_answered():
    """
    Twilio calls this when a lead picks up.
    - If no active session or already bridged: hang up.
    - Otherwise: put lead in conference (waiting), call Dylan.
    """
    session_id   = request.args.get("session_id")
    answered_sid = request.form.get("CallSid", "")
    phone        = request.form.get("To", "")
    answered_by  = request.form.get("AnsweredBy", "")

    response = VoiceResponse()

    # Hang up if it's an answering machine
    if answered_by in ("machine_start", "machine_end_beep", "machine_end_silence", "machine_end_other", "fax"):
        response.hangup()
        return Response(str(response), mimetype="text/xml")

    with _session["lock"]:
        if not _session["active"] or _session["bridged"]:
            response.hangup()
            return Response(str(response), mimetype="text/xml")

        _session["bridged"]     = True
        _session["bridged_sid"] = answered_sid
        config = _session["config"]

        # Find lead data from state
        state = leads_mod.load_state()
        lead_data = state["leads"].get(phone, {"phone": phone, "business": ""})
        _session["pending"] = lead_data

        # Cancel other outbound calls in the batch
        overflow = {p: s for p, s in _session["call_sids"].items() if s != answered_sid}

    # Cancel overflow calls outside the lock
    if overflow:
        dialer_mod.cancel_overflow_calls(overflow, answered_sid)

    # Put lead in conference (start_conference_on_enter=False — waits for Dylan)
    base_url   = config["webhook_base_url"].rstrip("/")
    session_id = _session["id"]

    dial = response.dial()
    dial.conference(
        f"dialer-{session_id}",
        start_conference_on_enter=False,
        end_conference_on_exit=True,
        wait_url="http://twimlets.com/holdmusic?Bucket=com.twilio.music.classical",
        beep=False,
    )

    # Call Dylan in a background thread so TwiML returns immediately
    def _call_dylan():
        dialer_mod.dial_dylan(config, session_id)

    threading.Thread(target=_call_dylan, daemon=True).start()

    return Response(str(response), mimetype="text/xml")


# ════════════════════════════════════════════════════════════════════════════
#  OVERFLOW LEAD ANSWERED (parallel Phase 2)
# ════════════════════════════════════════════════════════════════════════════

@app.route("/voice/lead-overflow", methods=["POST"])
def lead_overflow():
    """
    Second (or later) lead in a parallel batch picks up after Dylan is
    already bridged. Play a short message and hang up.
    """
    response = VoiceResponse()
    response.say("Sorry, I dialed the wrong number. Have a great day!", voice="Polly.Matthew")
    response.hangup()
    return Response(str(response), mimetype="text/xml")


# ════════════════════════════════════════════════════════════════════════════
#  DYLAN JOINS
# ════════════════════════════════════════════════════════════════════════════

@app.route("/voice/dylan-join", methods=["POST"])
def dylan_join():
    """
    Dylan's phone rings. When he picks up, he joins the conference as
    moderator (startConferenceOnEnter=True), which releases the waiting lead
    into the live call.
    After the conference ends, redirect to classification prompt.
    """
    session_id = request.args.get("session_id")
    base_url   = _session["config"].get("webhook_base_url", "").rstrip("/")

    response = VoiceResponse()
    dial     = response.dial(
        action=f"{base_url}/voice/call-ended",
        method="POST"
    )
    dial.conference(
        f"dialer-{session_id}",
        start_conference_on_enter=True,
        end_conference_on_exit=True,
        beep=False,
    )
    return Response(str(response), mimetype="text/xml")


# ════════════════════════════════════════════════════════════════════════════
#  CALL ENDED → CLASSIFICATION
# ════════════════════════════════════════════════════════════════════════════

@app.route("/voice/call-ended", methods=["POST"])
def call_ended():
    """
    Called when Dylan's conference leg ends (he hung up).
    Present DTMF classification menu.
    """
    response = VoiceResponse()
    gather   = Gather(num_digits=1, action="/voice/classify", method="POST", timeout=30)
    gather.say(
        "Call ended. Press 1 — Appointment booked. "
        "Press 2 — Follow up. "
        "Press 3 — Not interested. "
        "Press 4 — Send info. "
        "Press 5 — No answer.",
        voice="Polly.Matthew"
    )
    response.append(gather)
    response.say("No input received. Call logged as no answer.", voice="Polly.Matthew")
    response.hangup()
    return Response(str(response), mimetype="text/xml")


# ════════════════════════════════════════════════════════════════════════════
#  CLASSIFICATION RESULT
# ════════════════════════════════════════════════════════════════════════════

DISPOSITION_MAP = {
    "1": "Appointment Booked",
    "2": "Follow Up",
    "3": "Not Interested",
    "4": "Send Info",
    "5": "No Answer",
}


@app.route("/voice/classify", methods=["POST"])
def classify():
    """Handle Dylan's DTMF keypress and save disposition to state.json."""
    digit       = request.form.get("Digits", "")
    disposition = DISPOSITION_MAP.get(digit, "No Answer")

    pending = _session.get("pending")
    if pending:
        phone = pending.get("phone")
        state = leads_mod.load_state()
        leads_mod.record_disposition(state, phone, disposition)
        leads_mod.save_state(state)

    response = VoiceResponse()
    response.say(f"Got it — logged as {disposition}. Goodbye.", voice="Polly.Matthew")
    response.hangup()
    return Response(str(response), mimetype="text/xml")


# ════════════════════════════════════════════════════════════════════════════
#  CALL STATUS CALLBACK (no-answer, busy, failed)
# ════════════════════════════════════════════════════════════════════════════

@app.route("/voice/status", methods=["POST"])
def call_status():
    """
    Twilio fires this for every status change on outbound lead calls.
    We only act on terminal non-answer statuses.
    """
    status = request.form.get("CallStatus", "")
    phone  = request.args.get("phone", request.form.get("To", ""))

    if status in ("no-answer", "busy", "failed") and phone:
        state = leads_mod.load_state()
        leads_mod.record_attempt(state, phone)
        leads_mod.save_state(state)

    return "", 204


# ════════════════════════════════════════════════════════════════════════════
#  SERVER START
# ════════════════════════════════════════════════════════════════════════════

def start_server(config, port=None):
    port = port or config.get("webhook_port", 5000)
    print(f"🌐 Webhook server starting on port {port}")
    print(f"   Public URL: {config.get('webhook_base_url', '(not set)')}")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
