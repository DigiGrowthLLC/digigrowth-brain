import os
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _client():
    return Client(
        os.environ["TWILIO_ACCOUNT_SID"],
        os.environ["TWILIO_AUTH_TOKEN"]
    )


# ════════════════════════════════════════════════════════════════════════════
#  OUTBOUND CALL — LEAD
# ════════════════════════════════════════════════════════════════════════════

def dial_lead(config, lead, session_id):
    """
    Place an outbound call to a lead.
    When they answer, Twilio POSTs to /voice/lead-answered which joins them
    to the conference and immediately calls Dylan.
    Returns the Twilio Call SID or None on failure.
    """
    base_url = config["webhook_base_url"].rstrip("/")
    try:
        call = _client().calls.create(
            to=lead["phone"],
            from_=config["twilio_phone_number"],
            url=f"{base_url}/voice/lead-answered?session_id={session_id}",
            status_callback=f"{base_url}/voice/status?session_id={session_id}&phone={lead['phone']}",
            status_callback_event=["no-answer", "busy", "failed", "completed", "canceled"],
            status_callback_method="POST",
            timeout=config.get("call_timeout_seconds", 30),
            machine_detection="Enable",
        )
        print(f"  📞 Dialing {lead['business']} ({lead['phone']}) — SID: {call.sid}")
        return call.sid
    except Exception as e:
        print(f"  ❌ Failed to dial {lead['phone']}: {e}")
        return None


def redirect_call(sid, url, method="POST"):
    """Redirect an active call to a new TwiML URL via Twilio REST API."""
    try:
        _client().calls(sid).update(url=url, method=method)
    except Exception as e:
        print(f"  ⚠️  Could not redirect call {sid}: {e}")


def hangup_call(sid):
    """Hang up an active call by SID."""
    try:
        _client().calls(sid).update(status="completed")
    except Exception as e:
        print(f"  ⚠️  Could not hang up call {sid}: {e}")


# ════════════════════════════════════════════════════════════════════════════
#  PARALLEL BATCH DIAL
# ════════════════════════════════════════════════════════════════════════════

def dial_batch(config, leads, session_id):
    """
    Dial up to max_parallel_lines leads simultaneously.
    All Twilio API calls fire in parallel so every lead starts ringing at the
    same time. First to answer bridges to Dylan; the rest get canceled.
    Returns dict of {phone: call_sid}.
    """
    from concurrent.futures import ThreadPoolExecutor
    max_lines = config.get("max_parallel_lines", 5)
    batch     = leads[:max_lines]
    call_sids = {}

    def _dial(lead):
        sid = dial_lead(config, lead, session_id)
        return (lead["phone"], sid)

    with ThreadPoolExecutor(max_workers=max_lines) as pool:
        for phone, sid in pool.map(_dial, batch):
            if sid:
                call_sids[phone] = sid

    return call_sids


# ════════════════════════════════════════════════════════════════════════════
#  CANCEL OVERFLOW CALLS
# ════════════════════════════════════════════════════════════════════════════

def cancel_overflow_calls(call_sids, answered_sid):
    """
    After a lead is bridged to Dylan, cancel all other in-progress outbound
    calls so prospects don't sit waiting on hold.
    Called from webhook.py when the first lead picks up.
    """
    client = _client()
    for phone, sid in call_sids.items():
        if sid == answered_sid:
            continue
        try:
            call = client.calls(sid).fetch()
            if call.status in ("queued", "ringing", "in-progress"):
                client.calls(sid).update(status="canceled")
                print(f"  🚫 Canceled overflow call to {phone}")
        except Exception as e:
            print(f"  ⚠️  Could not cancel {sid}: {e}")
