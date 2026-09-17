"""
Single-lead "Call Now" for the client portal — a client clicks Call on one
of their own leads, their browser rings in, and the lead is dialed from the
client's own Twilio number/subaccount. Deliberately NOT a rewrite or
extension of dialer_engine.py: that module is a single, process-global
session shared by the internal Dialer panel's parallel/batch calling — a
client-portal call must never collide with Dylan running the internal
Dialer, or with another client calling at the same time.

In-memory dict keyed by a per-call `call_id` (uuid4 hex) instead of a
singleton, one shared lock guarding it — same "in-process state, single
uvicorn worker" assumption dialer_engine.py already makes, just keyed
instead of global. Each call gets its own Twilio conference name
(`client-call-{call_id}`), so concurrent calls — across different clients,
or the same client calling twice — never share a conference.

No batch/retry/gatekeeper/AMD machinery here — a client-portal call is
exactly one lead, dialed once, right when the client's browser joins.
"""

import os
import threading
import uuid
from datetime import datetime, timezone

from db import get_pool

_calls: dict[str, dict] = {}
_lock = threading.Lock()


def _master_client():
    from twilio.rest import Client as TwilioClient
    return TwilioClient(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])


def _dashboard_url() -> str:
    return os.environ.get("DASHBOARD_URL", "").rstrip("/")


async def _client_config(client_id: int) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT twilio_subaccount_sid, twilio_number, twilio_twiml_app_sid, "
            "twilio_api_key_sid, twilio_api_key_secret FROM client_marketing_config WHERE client_id = $1",
            client_id,
        )
    return dict(row) if row else None


def _to_e164(phone: str) -> str:
    """Same normalization as dialer_engine.py's own helper — CRM numbers
    can come in as "(754) 291-5582" rather than E.164."""
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    return phone


def _subaccount_client(subaccount_sid: str):
    from twilio.rest import Client as TwilioClient
    master = _master_client()
    return TwilioClient(subaccount_sid, master.api.accounts(subaccount_sid).fetch().auth_token)


async def is_voice_ready(client_id: int) -> bool:
    config = await _client_config(client_id)
    return bool(
        config and config["twilio_subaccount_sid"] and config["twilio_number"]
        and config["twilio_twiml_app_sid"] and config["twilio_api_key_sid"] and config["twilio_api_key_secret"]
    )


def create_call(client_id: int, contact_id: str, phone: str, prospect_name: str | None) -> str:
    call_id = uuid.uuid4().hex[:12]
    with _lock:
        _calls[call_id] = {
            "client_id": client_id,
            "contact_id": contact_id,
            "phone": phone,
            "prospect_name": prospect_name,
            "agent_sid": None,
            "lead_sid": None,
            "bridged": False,
            "status": "ringing",
            "created_at": datetime.now(timezone.utc),
        }
    return call_id


async def get_access_token(client_id: int) -> str:
    from twilio.jwt.access_token import AccessToken
    from twilio.jwt.access_token.grants import VoiceGrant

    config = await _client_config(client_id)
    if not config or not (config["twilio_twiml_app_sid"] and config["twilio_api_key_sid"] and config["twilio_api_key_secret"]):
        raise RuntimeError(f"Client {client_id} has no Voice calling provisioned yet")

    token = AccessToken(
        config["twilio_subaccount_sid"], config["twilio_api_key_sid"], config["twilio_api_key_secret"],
        identity=f"client-{client_id}", ttl=3600,
    )
    token.add_grant(VoiceGrant(outgoing_application_sid=config["twilio_twiml_app_sid"]))
    return token.to_jwt()


def _dial_lead_sync(call_id: str, client_id: int, subaccount_sid: str, from_number: str, to_number: str) -> None:
    base = _dashboard_url()
    if not base:
        print(f"[client_dialer] {call_id}: DASHBOARD_URL not set — cannot build callback URLs")
        return
    try:
        call = _subaccount_client(subaccount_sid).calls.create(
            to=_to_e164(to_number), from_=from_number,
            url=f"{base}/webhooks/client-voice/{client_id}/lead-answered?call_id={call_id}",
            status_callback=f"{base}/webhooks/client-voice/{client_id}/status?call_id={call_id}",
            status_callback_event=["no-answer", "busy", "failed", "completed", "canceled"],
            status_callback_method="POST",
            timeout=30,
        )
        with _lock:
            if call_id in _calls:
                _calls[call_id]["lead_sid"] = call.sid
    except Exception as e:
        print(f"[client_dialer] {call_id}: failed to dial {to_number}: {e}")
        with _lock:
            if call_id in _calls:
                _calls[call_id]["status"] = "ended"


async def agent_join(client_id: int, call_id: str, agent_call_sid: str) -> str:
    """Returns TwiML: puts the client's browser into a 2-party conference
    for this call, and kicks off dialing the lead in a background thread —
    same conference-then-background-dial shape as dialer_webhooks.agent_join,
    minus the batch/retry logic that doesn't apply to a single lead."""
    from twilio.twiml.voice_response import VoiceResponse

    with _lock:
        call = _calls.get(call_id)
        if call:
            call["agent_sid"] = agent_call_sid

    response = VoiceResponse()
    dial = response.dial()
    dial.conference(
        f"client-call-{call_id}",
        start_conference_on_enter=True,
        end_conference_on_exit=True,
        beep=False,
        wait_url="http://twimlets.com/holdmusic?Bucket=com.twilio.music.ambient",
    )

    if call:
        config = await _client_config(client_id)
        if config and config["twilio_subaccount_sid"] and config["twilio_number"]:
            threading.Thread(
                target=_dial_lead_sync,
                args=(call_id, client_id, config["twilio_subaccount_sid"], config["twilio_number"], call["phone"]),
                daemon=True,
            ).start()

    return str(response)


def lead_answered(call_id: str) -> str:
    from twilio.twiml.voice_response import VoiceResponse

    response = VoiceResponse()
    with _lock:
        call = _calls.get(call_id)
        if not call or call["status"] == "ended":
            response.say("Sorry about that, we accidentally dialed you. Have a great day!", voice="alice")
            response.hangup()
            return str(response)
        call["bridged"] = True
        call["status"] = "connected"

    dial = response.dial()
    dial.conference(f"client-call-{call_id}", start_conference_on_enter=True, end_conference_on_exit=False, beep=False)
    return str(response)


def call_status(call_id: str, status: str) -> None:
    if status not in ("no-answer", "busy", "failed", "completed", "canceled"):
        return
    with _lock:
        call = _calls.get(call_id)
        if call:
            call["bridged"] = False
            call["status"] = "ended"


def get_status(call_id: str) -> dict:
    with _lock:
        call = _calls.get(call_id)
    if not call:
        return {"status": "ended"}
    return {"status": call["status"], "bridged": call["bridged"]}


async def end_call(call_id: str) -> None:
    with _lock:
        call = _calls.get(call_id)
        if call:
            call["bridged"] = False
            call["status"] = "ended"
            sids = [s for s in (call.get("agent_sid"), call.get("lead_sid")) if s]
            client_id = call["client_id"]
        else:
            sids = []
            client_id = None
    if not sids or client_id is None:
        return

    # DB read happens here, on the caller's event loop — get_pool()'s
    # asyncpg pool is bound to the main event loop, so a background thread
    # must never touch it directly (same rule no_show_sequence.py's
    # _send_touch() follows: release the connection before any thread/
    # network I/O). The spawned thread below only ever makes plain Twilio
    # REST calls, no DB access.
    config = await _client_config(client_id)
    if not config or not config["twilio_subaccount_sid"]:
        return
    subaccount_sid = config["twilio_subaccount_sid"]

    def _hangup_all():
        client = _subaccount_client(subaccount_sid)
        for sid in sids:
            try:
                client.calls(sid).update(status="completed")
            except Exception as e:
                print(f"[client_dialer] could not hang up {sid}: {e}")

    threading.Thread(target=_hangup_all, daemon=True).start()
