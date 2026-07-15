"""
Shared dialer session state and Twilio API helpers.
Imported by both dialer_webhooks (public Twilio callbacks) and dialer router (auth'd browser API).
No FastAPI routes here — pure state + helpers.
"""

import asyncio
import os
import threading


# ── In-process session state ───────────────────────────────────────────────────

_session = {
    "active":               False,
    "id":                   None,
    "config":               {},
    "call_sids":            {},      # phone → call_sid for current batch
    "bridged":              False,
    "bridged_sid":          None,
    "bridged_phone":        None,
    "dylan_sid":            None,
    "pending":              None,    # current lead being classified
    "show_classification":  False,
    "total_leads":          0,
    "connected_at":         None,
    # Ring-time tracking
    "ring_start":           {},      # norm_phone → float (unix time when dialed)
    "ring_accum":           {},      # norm_phone → float (total seconds ringing)
    "dial_count":           {},      # norm_phone → int (times dialed this session)
    "needs_retry":          set(),   # norm_phones with < 30s ring, need re-dial
    "gatekeeper_pending":   None,    # {"sid", "phone", "lead"} — held call
    "batch_had_answer":     False,
    "max_lines":            5,
    "end_requested":        False,
    "eligible_leads":       [],      # leads yet to be dialed (mutable queue)
    "leads_by_phone":       {},      # norm_phone → lead dict (for retry lookups)
    "stats":                {"calls_made": 0, "dms_reached": 0},
    "lock":                 threading.Lock(),
}


def _norm(phone: str) -> str:
    return phone.replace("+", "").replace(" ", "").replace("-", "")


# ── Twilio REST helpers ────────────────────────────────────────────────────────

def _client():
    from twilio.rest import Client
    from twilio.http.http_client import TwilioHttpClient
    return Client(
        os.environ["TWILIO_ACCOUNT_SID"],
        os.environ["TWILIO_AUTH_TOKEN"],
        http_client=TwilioHttpClient(timeout=15),
    )


def hangup_call(sid: str) -> None:
    try:
        _client().calls(sid).update(status="completed")
    except Exception as e:
        print(f"  dialer: could not hang up {sid}: {e}")


def redirect_call(sid: str, url: str) -> None:
    try:
        _client().calls(sid).update(url=url, method="POST")
    except Exception as e:
        print(f"  dialer: could not redirect {sid}: {e}")


def cancel_overflow_calls(call_sids: dict, answered_sid: str) -> None:
    client = _client()
    for phone, sid in call_sids.items():
        if sid == answered_sid:
            continue
        try:
            call = client.calls(sid).fetch()
            if call.status in ("queued", "ringing", "in-progress"):
                client.calls(sid).update(status="canceled")
                print(f"  dialer: canceled overflow call to {phone}")
        except Exception as e:
            print(f"  dialer: could not cancel {sid}: {e}")


def _to_e164(phone: str) -> str:
    """Normalize a US phone number to E.164 format (+1XXXXXXXXXX)."""
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    return phone  # already E.164 or non-US; pass through


def _dial_lead_sync(phone: str, session_id: str, base_url: str, config: dict):
    """Synchronous outbound call. Returns (phone, sid_or_None, error_or_None)."""
    if not phone or not phone.strip():
        return (phone, None, "skipped: phone number is empty")
    from_num = os.environ.get("TWILIO_PHONE_NUMBER") or config.get("twilio_phone_number", "")
    base = base_url.rstrip("/")
    if not base:
        err = "base_url is empty — RAILWAY_PUBLIC_DOMAIN not set?"
        print(f"  dialer: {err}")
        return (phone, None, err)
    if not from_num:
        err = "TWILIO_PHONE_NUMBER not set and not in config.json"
        print(f"  dialer: {err}")
        return (phone, None, err)
    to_num = _to_e164(phone)
    print(f"  dialer: dialing {phone} → {to_num} (from {from_num})")
    try:
        call = _client().calls.create(
            to=to_num,
            from_=from_num,
            url=f"{base}/dialer/voice/lead-answered?session_id={session_id}",
            status_callback=f"{base}/dialer/voice/status?session_id={session_id}&phone={phone}",
            status_callback_event=["no-answer", "busy", "failed", "completed", "canceled"],
            status_callback_method="POST",
            timeout=config.get("call_timeout_seconds", 30),
            machine_detection="Enable",
            async_amd=True,
            async_amd_status_callback=f"{base}/dialer/voice/amd-result?session_id={session_id}&phone={phone}",
            async_amd_status_callback_method="POST",
            machine_detection_speech_threshold=1000,
            machine_detection_speech_end_threshold=500,
        )
        print(f"  dialer: placed call to {to_num} — SID {call.sid}")
        return (phone, call.sid, None)
    except Exception as e:
        print(f"  dialer: failed to dial {phone}: {e}")
        return (phone, None, str(e))


async def dial_batch(phones: list, session_id: str, base_url: str, config: dict) -> tuple:
    """Async parallel dial — runs Twilio REST calls in thread pool.
    Returns ({phone: sid}, [error_strings])."""
    loop = asyncio.get_event_loop()
    tasks = [
        loop.run_in_executor(None, _dial_lead_sync, phone, session_id, base_url, config)
        for phone in phones
    ]
    results = await asyncio.gather(*tasks)
    sids   = {phone: sid for phone, sid, err in results if sid}
    errors = [err         for phone, sid, err in results if err]
    return sids, errors


# ── Session lifecycle ──────────────────────────────────────────────────────────

def init_session(session_id: str, config_data: dict, leads: list) -> None:
    with _session["lock"]:
        _session["active"]              = True
        _session["id"]                  = session_id
        _session["config"]              = config_data
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
        _session["gatekeeper_pending"]  = None
        _session["batch_had_answer"]    = False
        _session["stats"]               = {"calls_made": 0, "dms_reached": 0}
        _session["eligible_leads"]      = list(leads)
        _session["leads_by_phone"]      = {_norm(l["phone"]): l for l in leads if l.get("phone")}
        _session["total_leads"]         = len(leads)
        _session["max_lines"]           = config_data.get("max_parallel_lines", 5)
        _session["end_requested"]       = False
        _session["auto_dialed"]         = False


def close_session() -> None:
    with _session["lock"]:
        dylan_sid   = _session.get("dylan_sid")
        bridged_sid = _session.get("bridged_sid")
        call_sids   = dict(_session.get("call_sids", {}))

        _session["active"]              = False
        _session["bridged"]             = False
        _session["bridged_phone"]       = None
        _session["bridged_sid"]         = None
        _session["call_sids"]           = {}
        _session["dylan_sid"]           = None
        _session["pending"]             = None
        _session["show_classification"] = False
        _session["connected_at"]        = None
        _session["ring_start"]          = {}
        _session["ring_accum"]          = {}
        _session["dial_count"]          = {}
        _session["needs_retry"]         = set()
        _session["gatekeeper_pending"]  = None
        _session["batch_had_answer"]    = False

    # Hang up all active Twilio legs in a background thread so we don't block
    # the async endpoint. Covers ringing leads (call_sids) + agent conference leg.
    to_hangup = set(call_sids.values())
    if bridged_sid:
        to_hangup.add(bridged_sid)
    if dylan_sid:
        to_hangup.add(dylan_sid)

    def _hangup_all():
        for sid in to_hangup:
            if sid:
                hangup_call(sid)

    if to_hangup:
        threading.Thread(target=_hangup_all, daemon=True).start()


def base_url() -> str:
    """Derive the public Railway URL for Twilio callback construction."""
    domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "")
    if domain:
        return f"https://{domain}"
    return os.environ.get("WEBHOOK_BASE_URL", "")
