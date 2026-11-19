"""AI voice agent for a CLIENT's new leads (Retell AI over the client's own
Twilio number). Growth package only; built 2026-11-15.

Call + text flow, as Dylan designed it (memory "voice-agent-call-text-flow"):
  - New Meta Instant Form lead -> AI call ~3 min later, NO text first.
    New funnel lead who left a mobile number but didn't book (booking_partials)
    -> AI call when the unfinished-booking text would have gone (10 min), and
    that text waits for the call.
  - No answer -> immediate double-dial. Still no answer -> voicemail on the
    double-dial, THEN the text agent's opener goes out (Meta) or the
    unfinished-booking text is released (funnel).
  - Retries: +2 hours, next day ~10:30, the day after ~16:30 (clinic time,
    calls only 8am-8pm). Then the normal SMS follow-up carries on.
  - Stops the moment they text back, book anywhere, opt out, get tagged
    Unqualified / Do Not Call, or the thread is escalated/closed.
  - Lead answers -> the call handles it (same booking tools as the text agent,
    response_ai._execute_tool). Answered but not booked -> one text written
    from the call so the text agent can carry on.
  - A lead that comes in after hours gets the opener text right away (so they
    don't wait all night) and call 1 at 9am.

Consent (TCPA, FCC 2024: an AI voice is an "artificial voice"): Meta leads are
only called if they came in after the client's Instant Form got the AI-call
consent line (voice_consent_meta_since, stamped from the Agents tab); funnel
leads only if they ticked the booking page's separate call-consent box
(booking_partials.call_consent).

Telephony: Retell "custom telephony". We dial the lead from the client's
Twilio number; when they pick up, Twilio asks /webhooks/voice-agent/answer,
which registers the call with Retell and returns <Dial><Sip> to
sip:{call_id}@sip.retellai.com. The number's own inbound routing (SMS AI,
call forwarding) is untouched. On this setup Retell can't transfer on our
number, so transfer_to_clinic redirects the live Twilio call ourselves.

State: one row per dial attempt in client_voice_calls; seq_id groups a lead's
attempts. process_due() (main.py, every 20s) dials due rows.

Two Retell agents per client (agent_kind on each call row):
  - 'ads': the agent above, for new Meta / funnel leads (voice_agent_enabled).
  - 'react': the DATABASE REACTIVATION voice agent (Dylan, 2026-11-17), its own
    Retell LLM + agent and its own switch (react_voice_enabled). It places the
    last_call playbook's call (client_reactivation._queue_last_call): "this is
    the final week of our <offer>, you filled out our form a couple weeks ago, wanted to
    let you know before it's gone". Same voice, name, consent rules, booking
    tools and calling hours as the ads agent.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx

import lead_flags
from db import get_pool

RETELL_BASE = "https://api.retellai.com"
RETELL_SIP_DOMAIN = "sip.retellai.com"

FIRST_CALL_DELAY = timedelta(minutes=3)
CALL_START_HOUR = 8          # never dial before 8am clinic time
CALL_LAST_START = (19, 45)   # or after 7:45pm (calls must end by 8pm)
MORNING_FIRST_CALL = (9, 0)  # an after-hours lead's first call
RETRY_2_AFTER = timedelta(hours=2)
RETRY_3_AT = (10, 30)        # next day
RETRY_4_AT = (16, 30)        # the day after
DO_NOT_CALL_TAG = "Do Not Call"
SEQ_DEDUPE_WINDOW = timedelta(days=3)
DEFAULT_VOICE_ID = "11labs-Kate"  # Dylan picked Kate after test calls, 2026-11-15
DEFAULT_VOICE_SPEED = 1.0  # 0.9 was too slow on the v3 model; Retell: 0.5-2.0, 1.0 = normal
# Naturalness defaults (research 2026-11-15: an expressive real-time ElevenLabs
# model, backchanneling, faint office ambience, slightly unhurried turn-taking).
ELEVEN_MODEL = "eleven_v3_conversational"
# Speech recognition boost: PT words callers say ("back pain" was heard as
# "back then" on test calls, 2026-11-15).
PT_KEYWORDS = [
    "back pain", "lower back", "neck pain", "sciatica", "herniated disc", "bulging disc", "pinched nerve",
    "shoulder", "rotator cuff", "frozen shoulder", "knee", "ACL", "meniscus", "hip", "hip replacement",
    "knee replacement", "plantar fasciitis", "ankle sprain", "tendonitis", "arthritis", "headaches",
    "posture", "chiropractor", "physical therapy", "physical therapist", "massage", "dry needling",
    "injections", "surgery", "MRI", "X-ray", "orthopedic", "sports injury", "car accident", "vertigo",
    "TMJ", "pelvic floor", "consult", "assessment",
]
NATURAL_SETTINGS = {
    "enable_backchannel": True,          # "mm-hm", "right" while they talk
    "backchannel_frequency": 0.9,
    "backchannel_words": ["mm-hmm", "yeah", "okay", "right", "uh-huh"],
    "ambient_sound": "call-center",      # quiet office bed, masks TTS edges
    "ambient_sound_volume": 0.4,
    "responsiveness": 1.0,               # normal (0.85 felt sluggish)
    "interruption_sensitivity": 0.8,
    # 1.2 sounded over-enthusiastic, 0.7 a bit flat; 0.9 = some mid-range variation (Dylan, 2026-11-16).
    "voice_temperature": 0.9,
    # Mid-call silence: give leads time to think before nudging. The quick
    # 2.5s nudge after a call screener hands off is note_transcript below.
    "reminder_trigger_ms": 8000,
    "reminder_max_count": 1,
}

# Voice style presets (Dylan, 2026-11-17: Retell's homepage "Kate" demo
# sounded better than ours). Retell doesn't publish the demo's config, so these
# let him A/B on test calls. Both of a client's agents use the same style.
#   tuned: the original settings above (v3 conversational, office ambience,
#          backchannel "mm-hmm"s, temperature 0.9).
#   stock: Retell's defaults, i.e. what a stock Kate agent sounds like: the
#          provider's default model, no background noise, no backchannel.
#   v4:    stock + ElevenLabs' newest model (eleven_v4).
_STOCK = {
    "ambient_sound": None, "enable_backchannel": False, "voice_temperature": 1.0,
    "responsiveness": 1.0, "interruption_sensitivity": 1.0,
    "reminder_trigger_ms": 8000, "reminder_max_count": 1,
}
VOICE_STYLES = {
    "tuned": {"label": "Tuned (original: office background, mm-hmms)", "voice_model": ELEVEN_MODEL, "settings": NATURAL_SETTINGS},
    "stock": {"label": "Retell stock (like the homepage demo)", "voice_model": None, "settings": _STOCK},
    "v4": {"label": "Retell stock + ElevenLabs v4", "voice_model": "eleven_v4", "settings": _STOCK},
}

# Retell disconnection reasons that mean no human conversation happened.
_NOT_CONNECTED = {
    "dial_busy", "dial_failed", "dial_no_answer", "invalid_destination", "user_declined",
    "registered_call_timeout", "error_user_not_joined", "marked_as_spam", "network_blocked",
    "telephony_provider_permission_denied", "telephony_provider_unavailable", "sip_routing_error",
}
_MACHINE = {"voicemail_reached", "ivr_reached"}


# ── Small helpers ────────────────────────────────────────────────────────────

def _api_key() -> str | None:
    return os.environ.get("RETELL_API_KEY") or None


def _base_url() -> str:
    return os.environ.get("DASHBOARD_URL", "").rstrip("/")


def e164(phone: str | None) -> str | None:
    digits = "".join(c for c in (phone or "") if c.isdigit())
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    return None


def _digits10(phone: str | None) -> str:
    return "".join(c for c in (phone or "") if c.isdigit())[-10:]


def _first(name: str | None) -> str:
    return (name or "").strip().split()[0].capitalize() if (name or "").strip() else ""


async def _tz(client_id: int, phone: str | None) -> ZoneInfo:
    import response_ai
    try:
        return ZoneInfo(await response_ai._clinic_tz(client_id, phone))
    except Exception:
        return ZoneInfo("America/Chicago")


def _in_window(local: datetime) -> bool:
    return CALL_START_HOUR <= local.hour and (local.hour, local.minute) <= CALL_LAST_START


def _next_window(local: datetime, at: tuple[int, int] = MORNING_FIRST_CALL) -> datetime:
    """`local` if it's inside calling hours, else the next morning at `at`."""
    if _in_window(local):
        return local
    day = local if local.hour < CALL_START_HOUR else local + timedelta(days=1)
    return day.replace(hour=at[0], minute=at[1], second=0, microsecond=0)


async def _retell(method: str, path: str, body: dict | None = None) -> dict:
    key = _api_key()
    if not key:
        raise RuntimeError("RETELL_API_KEY isn't set (Doppler + Railway)")
    async with httpx.AsyncClient(timeout=20) as http:
        r = await http.request(method, f"{RETELL_BASE}{path}", json=body,
                               headers={"Authorization": f"Bearer {key}"})
    if r.status_code >= 400:
        raise RuntimeError(f"Retell {method} {path} -> {r.status_code}: {r.text[:300]}")
    return r.json() if r.content else {}


# ── Call screener hand-off ───────────────────────────────────────────────────
# Once a call screener says "please stay on the line" nobody speaks first when
# the person picks up. We spot that line in Retell's transcript_updated
# webhook and, 2.5s later, make the agent say "Hi, is this <name>?" unless the
# person has spoken meanwhile. (Letting the LLM call a "wait" tool fired at the
# wrong moment, 2026-11-16.) In-memory: one Railway instance; a lost entry
# only means the agent's normal 8s silence reminder does it instead.
_HANDOFF_RE = re.compile(r"stay on the line|please hold|connecting you|putting you through|"
                         r"will be (right )?with you|be with you (in a moment|shortly)", re.I)
_PICKUP_WAIT: dict[str, int] = {}   # retell call_id -> user turns at hand-off
_HANDOFF_SEEN: set[str] = set()
# iPhone screening rings the person only after the hand-off, so they pick up
# anywhere from ~3 to 20s later and can't be detected until they speak. Keep
# greeting every 2.5s for ~20s so whenever they pick up they hear us within
# a couple of seconds (one greeting at 2.5s was missed twice, 2026-11-16).
# Gaps count from when we send the nudge; the agent takes ~1-1.5s to speak,
# so 2.5s left under 2s to answer. 5s gives a real pause between greetings.
PICKUP_NUDGES_S = (2.0,) + (5.0,) * 4


def _user_utts(call: dict) -> list[str]:
    items = call.get("transcript_with_tool_calls") or call.get("transcript_object") or []
    out = [u.get("content") or "" for u in items if u.get("role") == "user" and (u.get("content") or "").strip()]
    if not out and call.get("transcript"):
        out = [ln[5:].strip() for ln in call["transcript"].splitlines() if ln.startswith("User:") and ln[5:].strip()]
    return out


def note_transcript(call: dict) -> None:
    """transcript_updated webhook (every turn)."""
    cid = call.get("call_id")
    if not cid:
        return
    users = _user_utts(call)
    if cid in _PICKUP_WAIT:
        if len(users) > _PICKUP_WAIT[cid]:
            _PICKUP_WAIT.pop(cid, None)          # the person spoke: no nudge
        return
    if cid in _HANDOFF_SEEN or not users or not _HANDOFF_RE.search(users[-1]):
        return
    _HANDOFF_SEEN.add(cid)
    if len(_HANDOFF_SEEN) > 500:
        _HANDOFF_SEEN.clear()
    _PICKUP_WAIT[cid] = len(users)
    first = ((call.get("retell_llm_dynamic_variables") or {}).get("lead_first_name") or "").strip() or "there"
    asyncio.create_task(_pickup_nudge(cid, first))


async def _pickup_nudge(call_id: str, first_name: str) -> None:
    for i, delay in enumerate(PICKUP_NUDGES_S):
        await asyncio.sleep(delay)
        if call_id not in _PICKUP_WAIT:      # they spoke
            return
        line = f"Hi, is this {first_name}?" if i % 2 == 0 else "Hello?"
        try:
            await _retell("PATCH", f"/v2/update-live-call/{call_id}", {"call_control": {
                "trigger_response": True,
                "additional_context": f'The call screener handed the call over; the person may be picking up now '
                                      f'and has not spoken yet. Say only: "{line}"'}})
        except Exception as e:
            print(f"[voice_agent] pickup nudge failed for {call_id}: {e}", flush=True)
            break
    _PICKUP_WAIT.pop(call_id, None)


def verify_retell_signature(raw_body: bytes, header: str | None, max_age_ms: int = 300_000) -> bool:
    """X-Retell-Signature = "v=<ts_ms>,d=<hex>", d = HMAC-SHA256(api_key, body + ts)."""
    key = _api_key()
    m = re.match(r"v=(\d+),d=(.*)", header or "")
    if not key or not m:
        return False
    ts, digest = m.group(1), m.group(2).strip()
    if abs(int(time.time() * 1000) - int(ts)) > max_age_ms:
        return False
    expected = hmac.new(key.encode(), raw_body.decode("utf-8").encode() + ts.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, digest)


def _twilio_for(subaccount_sid: str):
    import client_dialer
    if subaccount_sid == os.environ.get("TWILIO_ACCOUNT_SID"):
        return client_dialer._master_client()
    return client_dialer._subaccount_client(subaccount_sid)


def _caller(cfg, row) -> tuple[str, str] | None:
    """(Twilio account SID, from number). The client's own number; a TEST
    call for a client without one uses DigiGrowth's OS number instead."""
    if cfg and cfg["twilio_subaccount_sid"] and cfg["twilio_number"]:
        return cfg["twilio_subaccount_sid"], cfg["twilio_number"]
    if row["source"] == "test" and os.environ.get("TWILIO_PHONE_NUMBER") and os.environ.get("TWILIO_ACCOUNT_SID"):
        return os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_PHONE_NUMBER"]
    return None


# ── Config ───────────────────────────────────────────────────────────────────

async def _config(conn, client_id: int):
    return await conn.fetchrow(
        """SELECT cmc.*, c.name AS client_name, c.phone AS client_phone
           FROM client_marketing_config cmc JOIN clients c ON c.id = cmc.client_id
           WHERE cmc.client_id = $1""",
        client_id,
    )


def _agent_id(cfg, kind: str = "ads") -> str | None:
    return cfg["react_retell_agent_id"] if kind == "react" else cfg["retell_agent_id"]


def _ready(cfg, kind: str = "ads") -> str | None:
    """None if this client's voice agent ('ads' or 'react') can place calls, else why not."""
    if not cfg:
        return "no marketing config"
    if not (cfg["react_voice_enabled"] if kind == "react" else cfg["voice_agent_enabled"]):
        return "reactivation voice agent off" if kind == "react" else "voice agent off"
    if not _api_key():
        return "RETELL_API_KEY not set"
    if not _agent_id(cfg, kind):
        return "Retell agent not created yet"
    if not (cfg["twilio_number"] and cfg["twilio_subaccount_sid"]):
        return "no Twilio number"
    return None


# ── Enqueueing ───────────────────────────────────────────────────────────────

async def _open_sequence(conn, client_id: int, phone: str) -> bool:
    return bool(await conn.fetchval(
        """SELECT 1 FROM client_voice_calls WHERE client_id = $1 AND phone = $2 AND source <> 'test'
             AND created_at > now() - make_interval(secs => $3)""",
        client_id, phone, SEQ_DEDUPE_WINDOW.total_seconds(),
    ))


async def _insert_attempt(conn, *, client_id: int, phone: str, run_at: datetime, source: str,
                          attempt: int, seq_id: int | None = None, double_dial: bool = False,
                          lead_name: str | None = None, lead_email: str | None = None,
                          partial_id: int | None = None, texted_first: bool = False,
                          note: str | None = None, agent_kind: str = "ads",
                          lead_since: datetime | None = None, form_info: str | None = None) -> int:
    row_id = await conn.fetchval(
        """INSERT INTO client_voice_calls (client_id, phone, lead_name, lead_email, source, partial_id,
               seq_id, attempt, double_dial, texted_first, run_at, token, note, agent_kind, lead_since, form_info)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16) RETURNING id""",
        client_id, phone, lead_name, lead_email, source, partial_id, seq_id, attempt, double_dial,
        texted_first, run_at, secrets.token_urlsafe(16), note, agent_kind, lead_since, form_info,
    )
    if seq_id is None:
        await conn.execute("UPDATE client_voice_calls SET seq_id = id WHERE id = $1", row_id)
    return row_id


async def start_for_meta_lead(client_id: int, phone: str, lead_name: str | None, lead_email: str | None) -> bool:
    """Called by response_ai.initiate_conversation for a fresh Meta lead.
    True = the voice agent owns first contact (caller must NOT queue the
    opener text now). False = carry on as before (opener text now); a call may
    still be queued for the morning. Never raises."""
    try:
        to = e164(phone)
        pool = await get_pool()
        async with pool.acquire() as conn:
            cfg = await _config(conn, client_id)
            if _ready(cfg) or not to:
                return False
            since = cfg["voice_consent_meta_since"]
            if not since or since > datetime.now(timezone.utc):
                return False  # consent line not on the form yet: text only
            if await _open_sequence(conn, client_id, to):
                return False
            tz = await _tz(client_id, to)
            due = (datetime.now(timezone.utc) + FIRST_CALL_DELAY).astimezone(tz)
            if _in_window(due):
                await _insert_attempt(conn, client_id=client_id, phone=to, run_at=due, source="meta",
                                      attempt=1, lead_name=lead_name, lead_email=lead_email,
                                      form_info=await _form_info(conn, client_id, to))
                return True
            await _insert_attempt(conn, client_id=client_id, phone=to, run_at=_next_window(due), source="meta",
                                  attempt=1, lead_name=lead_name, lead_email=lead_email, texted_first=True,
                                  form_info=await _form_info(conn, client_id, to))
            return False
    except Exception as e:
        print(f"[voice_agent] start_for_meta_lead failed client={client_id} phone={phone}: {e}", flush=True)
        return False


async def start_for_funnel_partial(client_id: int, session_id: str, run_at: datetime) -> None:
    """Called by booking_conversion.save_partial when the patient ticked the
    call-consent box. Holds the unfinished-booking text for the call (in
    calling hours). Never raises."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            p = await conn.fetchrow(
                "SELECT id, name, phone, call_consent, voice_hold, booking_id FROM booking_partials WHERE session_id = $1",
                session_id[:64],
            )
            if not p or p["call_consent"] is not True or p["voice_hold"] or p["booking_id"]:
                return
            to = e164(p["phone"])
            cfg = await _config(conn, client_id)
            if _ready(cfg) or not to or await _open_sequence(conn, client_id, to):
                return
            tz = await _tz(client_id, to)
            due = run_at.astimezone(tz)
            if _in_window(due):
                await _insert_attempt(conn, client_id=client_id, phone=to, run_at=due, source="funnel",
                                      attempt=1, lead_name=p["name"], partial_id=p["id"])
                await conn.execute("UPDATE booking_partials SET voice_hold = true WHERE id = $1", p["id"])
            else:
                await _insert_attempt(conn, client_id=client_id, phone=to, run_at=_next_window(due), source="funnel",
                                      attempt=1, lead_name=p["name"], partial_id=p["id"], texted_first=True)
    except Exception as e:
        print(f"[voice_agent] start_for_funnel_partial failed client={client_id}: {e}", flush=True)


async def queue_last_call(client_id: int, phone: str, lead_name: str | None, is_meta: bool,
                          lead_created_at: datetime | None, offer_note: str | None) -> bool:
    """Database reactivation's last_call playbook: the REACTIVATION voice
    agent calls an ad lead in the offer's final week. Only when they consented to calls (Meta form after the
    consent line went live, or the booking page's call box), unless Dylan turned on
    react_call_without_consent for the client, and we're in
    calling hours. One attempt + redial; no answer -> the last-day text
    (_release_text). True = queued; False = caller texts instead. Never raises."""
    try:
        to = e164(phone)
        pool = await get_pool()
        async with pool.acquire() as conn:
            cfg = await _config(conn, client_id)
            if _ready(cfg, "react") or not to:
                return False
            since = cfg["voice_consent_meta_since"]
            consent = bool(is_meta and since and lead_created_at and lead_created_at >= since)
            if not consent:
                consent = bool(await conn.fetchval(
                    """SELECT 1 FROM booking_partials WHERE client_id = $1 AND call_consent IS TRUE
                         AND right(regexp_replace(phone, '\\D', '', 'g'), 10) = $2 LIMIT 1""",
                    client_id, _digits10(to)))
            if not consent and not cfg["react_call_without_consent"]:
                return False
            if await conn.fetchval(
                "SELECT 1 FROM client_voice_calls WHERE client_id = $1 AND phone = $2 "
                "AND status IN ('pending', 'dialing', 'ringing', 'in_progress')", client_id, to):
                return False
            if not _in_window(datetime.now(await _tz(client_id, to))):
                return False
            await _insert_attempt(conn, client_id=client_id, phone=to, run_at=datetime.now(timezone.utc),
                                  source="lastcall", attempt=1, lead_name=lead_name, note=offer_note,
                                  agent_kind="react", lead_since=lead_created_at,
                                  form_info=await _form_info(conn, client_id, to))
            return True
    except Exception as e:
        print(f"[voice_agent] queue_last_call failed client={client_id} phone={phone}: {e}", flush=True)
        return False


async def retry_failed(client_id: int, kind: str, days: int = 3, dry_run: bool = True) -> dict:
    """Re-queue real calls that errored before dialing (e.g. the 2026-11-18
    SQL bug that failed all 14 of Advantage's last-call calls). Each goes back
    to 'pending' at the next calling-hours slot in the lead's time zone; the
    usual stop rules (booked, texted back, opted out ...) still run right
    before dialing. Skips anyone who already has a newer call row.
    dry_run=True only lists who would be retried."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT f.id, f.phone, f.lead_name, f.source FROM client_voice_calls f
               WHERE f.client_id = $1 AND coalesce(f.agent_kind, 'ads') = $2 AND f.source != 'test'
                 AND f.status = 'failed' AND f.outcome = 'error' AND f.dialed_at IS NULL
                 AND f.run_at > now() - make_interval(days => $3)
                 AND NOT EXISTS (SELECT 1 FROM client_voice_calls n WHERE n.client_id = f.client_id
                                 AND n.phone = f.phone AND n.id > f.id)
               ORDER BY f.id""", client_id, kind, days)
        out = []
        for r in rows:
            when = _next_window(datetime.now(await _tz(client_id, r["phone"]))).astimezone(timezone.utc)
            out.append({"id": r["id"], "lead_name": r["lead_name"], "source": r["source"], "run_at": when.isoformat()})
            if not dry_run:
                await conn.execute(
                    "UPDATE client_voice_calls SET status = 'pending', outcome = NULL, error = NULL, run_at = $2, "
                    "updated_at = now() WHERE id = $1 AND status = 'failed'", r["id"], when)
    return {"dry_run": dry_run, "count": len(out), "calls": out}


async def _form_info(conn, client_id: int, phone: str) -> str | None:
    """The lead's answers to the Meta form's own questions (contacts.form_answers),
    as "Question: answer; ..." for the reactivation call's opener."""
    rec = await conn.fetchrow(
        """SELECT form_answers, lead_platform FROM contacts WHERE client_id = $1
             AND (form_answers IS NOT NULL OR lead_platform IS NOT NULL)
             AND right(regexp_replace(phone, '\\D', '', 'g'), 10) = $2 ORDER BY created_at DESC LIMIT 1""",
        client_id, _digits10(phone))
    if not rec:
        return None
    raw = rec["form_answers"]
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            raw = None
    parts = [f"{a.get('question')}: {a.get('answer')}" for a in (raw or []) if isinstance(a, dict) and a.get("answer")]
    if rec["lead_platform"]:
        parts.insert(0, f"Filled out on: {rec['lead_platform'].capitalize()}")
    return "; ".join(parts)[:600] or None


async def queue_test_call(client_id: int, phone: str, lead_name: str | None, kind: str = "ads") -> int:
    to = e164(phone)
    if not to:
        raise ValueError("Enter a 10-digit US number")
    pool = await get_pool()
    async with pool.acquire() as conn:
        cfg = await _config(conn, client_id)
        if not cfg or not _agent_id(cfg, kind):
            raise ValueError("Create the Retell agent first (SYNC AGENT)")
        if not (cfg["twilio_number"] and cfg["twilio_subaccount_sid"]) and not os.environ.get("TWILIO_PHONE_NUMBER"):
            raise ValueError("This client has no Twilio number yet")
        return await _insert_attempt(conn, client_id=client_id, phone=to, run_at=datetime.now(timezone.utc),
                                     source="test", attempt=1, lead_name=lead_name or "Test Lead", agent_kind=kind,
                                     lead_since=(datetime.now(timezone.utc) - timedelta(days=21)) if kind == "react" else None,
                                     # A sample answer so the test opener sounds like a real lead's.
                                     form_info="Filled out on: Facebook; What are you dealing with?: Back pain")


# ── Stop rules ───────────────────────────────────────────────────────────────

async def _stop_reason(conn, row) -> str | None:
    import response_ai
    if row["source"] == "test":
        return None
    phone, client_id = row["phone"], row["client_id"]
    d10 = _digits10(phone)
    seq_start = await conn.fetchval("SELECT created_at FROM client_voice_calls WHERE id = $1", row["seq_id"]) or row["created_at"]

    if await response_ai._upcoming_booking(conn, phone, row["lead_email"]):
        return "booked"
    if await conn.fetchval(
        # $2 must be cast: with a bare "$2 - interval" Postgres types $2 as an
        # interval and the query fails (every real call errored on 2026-11-18).
        """SELECT 1 FROM bookings WHERE client_id = $1 AND created_at > $2::timestamptz - interval '1 hour'
             AND right(regexp_replace(phone, '\\D', '', 'g'), 10) = $3 AND status IN ('confirmed', 'pending_payment')""",
        client_id, seq_start, d10,
    ):
        return "booked"
    if await conn.fetchval(
        """SELECT 1 FROM client_sms_messages WHERE client_id = $1 AND direction = 'inbound' AND created_at > $2
             AND right(regexp_replace(from_number, '\\D', '', 'g'), 10) = $3""",
        client_id, seq_start, d10,
    ):
        return "texted back"
    status = await conn.fetchval(
        "SELECT status FROM client_lead_conversations WHERE client_id = $1 AND phone = $2", client_id, phone)
    if status in ("escalated", "closed", "booked"):
        return f"thread {status}"
    tags = await conn.fetchval(
        """SELECT array_agg(lower(regexp_replace(t, '[^A-Za-z]', '', 'g'))) FROM contacts c, unnest(coalesce(c.tags, '{}')) t
           WHERE c.client_id = $1 AND right(regexp_replace(c.phone, '\\D', '', 'g'), 10) = $2""",
        client_id, d10,
    ) or []
    if any(t in tags for t in ("dontcontact", "donotcontact", "dnc")):
        return "don't contact"
    if "donotcall" in tags:
        return "do not call"
    if "smsoptedout" in tags:
        return "opted out"
    if "unqualified" in tags:
        return "unqualified"
    return None


# ── Dialing ──────────────────────────────────────────────────────────────────

async def process_due() -> None:
    """Scheduler job: dial due attempts (SKIP LOCKED claim, restart-safe)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """UPDATE client_voice_calls SET status = 'dialing', updated_at = now()
               WHERE id IN (SELECT id FROM client_voice_calls WHERE status = 'pending' AND run_at <= now()
                            ORDER BY run_at LIMIT 10 FOR UPDATE SKIP LOCKED)
               RETURNING *"""
        )
    for row in rows:
        try:
            await _dial(row)
        except Exception as e:
            print(f"[voice_agent] dial failed for call row {row['id']}: {e}", flush=True)
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE client_voice_calls SET status = 'failed', outcome = 'error', error = $2, updated_at = now() WHERE id = $1",
                    row["id"], str(e)[:300])
    await _sweep_stuck()


async def _dial(row) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        cfg = await _config(conn, row["client_id"])
        kind = row["agent_kind"] or "ads"
        not_ready = _ready(cfg, kind) if row["source"] != "test" else (None if cfg and _agent_id(cfg, kind) else "no agent")
        stop = not_ready or await _stop_reason(conn, row)
        if stop:
            await conn.execute(
                "UPDATE client_voice_calls SET status = 'skipped', outcome = 'skipped', error = $2, updated_at = now() WHERE id = $1",
                row["id"], stop)
            await _cancel_rest(conn, row["seq_id"], stop)
            # Voice unavailable (switched off, no key...) or call-only block:
            # first contact falls back to text. Booked / texted back / closed
            # threads already have what they need, so no opener then.
            if not_ready or stop == "do not call":
                await _release_text(conn, row, after_call=False)
            return
        if row["source"] != "test":
            tz = await _tz(row["client_id"], row["phone"])
            now_local = datetime.now(tz)
            if not _in_window(now_local):
                await conn.execute(
                    "UPDATE client_voice_calls SET status = 'pending', run_at = $2, updated_at = now() WHERE id = $1",
                    row["id"], _next_window(now_local))
                return
    base = _base_url()
    if not base:
        raise RuntimeError("DASHBOARD_URL not set")
    q = f"id={row['id']}&t={row['token']}"
    caller = _caller(cfg, row)
    if not caller:
        raise RuntimeError("no Twilio number to call from")

    def _create():
        return _twilio_for(caller[0]).calls.create(
            to=row["phone"], from_=caller[1],
            url=f"{base}/webhooks/voice-agent/answer?{q}",
            status_callback=f"{base}/webhooks/voice-agent/status?{q}",
            status_callback_event=["completed"], status_callback_method="POST",
            timeout=25,
        )
    call = await asyncio.to_thread(_create)
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE client_voice_calls SET status = 'ringing', twilio_call_sid = $2, dialed_at = now(), updated_at = now() WHERE id = $1",
            row["id"], call.sid)


async def get_row(row_id: int, token: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM client_voice_calls WHERE id = $1", row_id)
    if not row or not hmac.compare_digest(row["token"] or "", token or ""):
        return None
    return row


async def _visit_info(client_id: int) -> dict | None:
    """The bookable visit on the clinic's DigiGrowth Booking calendar (the one
    the booking tool books), so the agent knows its length and price."""
    try:
        import booking_conversion
        got = await booking_conversion._ai_event(client_id)
    except Exception:
        return None
    if not got:
        return None
    ev = got[1]
    return {"name": ev.get("name"), "duration_min": ev.get("duration_min"), "price_cents": ev.get("price_cents") or 0}


def _visit_text(v: dict | None) -> str:
    if not v:
        return "not listed on the calendar; use the business info"
    price = f"${v['price_cents'] / 100:g}, paid when they book (the booking tool texts them a link to pay)" if v["price_cents"] else "free"
    return f"{v['name']}, {v['duration_min']} minutes, {price}"


def _ordinal(n: int) -> str:
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _dynamic_vars(row, cfg, tz: ZoneInfo) -> dict:
    now = datetime.now(tz)
    source = {
        "meta": "they just filled out the clinic's form on Facebook/Instagram",
        "funnel": "they started booking on the clinic's website but didn't finish",
        "callback": "they asked to be called back at this time",
        "lastcall": "they filled out the clinic's ad form a while back but never came in. This is the FINAL WEEK "
                    "of that offer, and you're calling so they don't miss it",
        # A test plays out exactly like a fresh Meta lead, so it sounds real.
        "test": "they just filled out the clinic's form on Facebook/Instagram",
    }.get(row["source"], "they reached out to the clinic")
    react = (row["agent_kind"] or "ads") == "react"
    if react and row["source"] in ("test", "callback"):
        source = ("they filled out the clinic's ad form a while back but never came in. This is the FINAL WEEK "
                  "of that offer, and you're calling so they don't miss it"
                  + ("; they asked to be called back at this time" if row["source"] == "callback" else ""))
    since = row["lead_since"]
    form_date = since.astimezone(tz).strftime("%B ") + _ordinal(since.astimezone(tz).day) if since else ""
    return {
        "form_date": form_date or "a few weeks back",
        "form_answers": row["form_info"] or "none on file",
        "lead_first_name": _first(row["lead_name"]) or "there",
        "lead_full_name": (row["lead_name"] or "").strip() or "unknown",
        "lead_context": source + (f". Note: {row['note']}" if row["note"] else ""),
        "clinic_name": cfg["client_name"] or "the clinic",
        "today": now.strftime("%A, %B %d, %Y") + f", {now.strftime('%I:%M %p').lstrip('0')} clinic time",
    }


async def answer_twiml(row) -> str:
    """Twilio fetched our URL = the lead (or their voicemail) picked up.
    Register with Retell and bridge over SIP."""
    from twilio.twiml.voice_response import VoiceResponse
    pool = await get_pool()
    async with pool.acquire() as conn:
        cfg = await _config(conn, row["client_id"])
    tz = await _tz(row["client_id"], row["phone"])
    # Voicemail: leave one only on the double-dial; every other attempt hangs up.
    vm = {"action": {"type": "hangup"}}
    react = (row["agent_kind"] or "ads") == "react"
    if react and (row["double_dial"] or row["source"] == "test"):
        vm = {"action": {"type": "prompt", "text": (
            "You reached voicemail. Leave one short, friendly message under 20 seconds: say your first name and "
            "that you're calling from {{clinic_name}} because this is the final week of the offer they filled out "
            "our form for, and you didn't want them to miss it. Say you'll send them a text in a moment and they "
            "can just reply there. Never ask them to call back and never give a phone number. Don't mention prices.")}}
    elif row["double_dial"] or row["source"] == "test":
        vm = {"action": {"type": "prompt", "text": (
            "You reached voicemail. Leave one short, friendly message under 20 seconds: say your first name and "
            "that you're calling from {{clinic_name}} about their request, that you'll send them a text in a "
            "moment, and they can just reply there whenever it suits them. Never ask them to call back and never "
            "give a phone number. Don't mention prices.")}}
    body = {
        "agent_id": _agent_id(cfg, "react" if react else "ads"),
        "from_number": (_caller(cfg, row) or (None, None))[1], "to_number": row["phone"], "direction": "outbound",
        "metadata": {"row_id": row["id"], "client_id": row["client_id"], "phone": row["phone"], "token": row["token"]},
        "retell_llm_dynamic_variables": {**_dynamic_vars(row, cfg, tz),
                                         "visit_info": _visit_text(await _visit_info(row["client_id"]))},
        # Boost the lead's own first name too: "this is Dylan" was heard as
        # "this is done" and the agent hung up (2026-11-16).
        "agent_override": {"agent": {**_voice_fields(cfg), "voicemail_option": vm,
                                     "boosted_keywords": _keywords(cfg, row["lead_name"])}},
        # The synced agent itself (sync_agent edits its latest version).
        "agent_version": "latest",
    }
    vr = VoiceResponse()
    try:
        try:
            reg = await _retell("POST", "/v2/register-phone-call", body)
        except RuntimeError as e:
            if "agent_override" not in str(e) and "agent_version" not in str(e) and "400" not in str(e):
                raise
            print(f"[voice_agent] register rejected for row {row['id']}, retrying simpler: {e}", flush=True)
            body.pop("agent_version", None)
            try:
                reg = await _retell("POST", "/v2/register-phone-call", body)
            except RuntimeError:
                body.pop("agent_override")  # last resort: the agent's own saved settings
                reg = await _retell("POST", "/v2/register-phone-call", body)
    except Exception as e:
        print(f"[voice_agent] Retell register failed for row {row['id']}: {e}", flush=True)
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE client_voice_calls SET status = 'failed', outcome = 'error', error = $2, updated_at = now() WHERE id = $1",
                row["id"], str(e)[:300])
        vr.hangup()
        return str(vr)
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE client_voice_calls SET status = 'in_progress', retell_call_id = $2, answered_at = now(), updated_at = now() WHERE id = $1",
            row["id"], reg["call_id"])
    dial = vr.dial(answer_on_bridge=True)
    dial.sip(f"sip:{reg['call_id']}@{RETELL_SIP_DOMAIN}")
    return str(vr)


async def twilio_status(row, call_status: str, duration: str | None) -> None:
    """Twilio's final status. Unanswered calls never reach Retell, so this is
    where no-answer/busy/failed are handled."""
    if call_status in ("no-answer", "busy", "failed", "canceled"):
        pool = await get_pool()
        async with pool.acquire() as conn:
            fresh = await conn.fetchrow("SELECT * FROM client_voice_calls WHERE id = $1", row["id"])
            if fresh["status"] in ("done", "failed", "skipped"):
                return
            await conn.execute(
                "UPDATE client_voice_calls SET status = 'done', outcome = 'no_answer', disconnection_reason = $2, updated_at = now() WHERE id = $1",
                row["id"], f"twilio_{call_status}")
        await _after_attempt(fresh, "no_answer")


async def _sweep_stuck() -> None:
    """A call whose Retell webhook never came: close it after 20 minutes so
    the sequence doesn't hang. Treated as answered (no more calls)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """UPDATE client_voice_calls SET status = 'done', outcome = coalesce(outcome, 'unknown'), updated_at = now()
               WHERE status IN ('ringing', 'in_progress') AND coalesce(dialed_at, updated_at) < now() - interval '20 minutes'
               RETURNING *""")
        for r in rows:
            await _cancel_rest(conn, r["seq_id"], "call outcome unknown")


# ── After a call ─────────────────────────────────────────────────────────────

def _classify(call: dict) -> str:
    reason = call.get("disconnection_reason") or ""
    analysis = call.get("call_analysis") or {}
    if reason in _NOT_CONNECTED:
        return "no_answer"
    if reason in _MACHINE or analysis.get("in_voicemail"):
        return "voicemail"
    user_spoke = any(t.get("role") == "user" and (t.get("content") or "").strip()
                     for t in (call.get("transcript_object") or []))
    if not user_spoke and (call.get("duration_ms") or 0) < 15000:
        return "no_answer"
    if reason == "user_requested_dnc":
        return "not_interested"
    return "answered"


async def retell_event(event: str, call: dict) -> None:
    meta = call.get("metadata") or {}
    row_id = meta.get("row_id")
    if not row_id:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM client_voice_calls WHERE id = $1", int(row_id))
        if not row or (row["retell_call_id"] and row["retell_call_id"] != call.get("call_id")):
            return
        analysis = call.get("call_analysis") or {}
        await conn.execute(
            """UPDATE client_voice_calls SET transcript = coalesce($2, transcript), recording_url = coalesce($3, recording_url),
                   disconnection_reason = coalesce($4, disconnection_reason), duration_ms = coalesce($5, duration_ms),
                   summary = coalesce($6, summary), updated_at = now() WHERE id = $1""",
            row["id"], call.get("transcript"), call.get("recording_url"), call.get("disconnection_reason"),
            call.get("duration_ms"), analysis.get("call_summary"),
        )
        if event != "call_ended" or row["status"] in ("done", "failed", "skipped"):
            return
        outcome = _classify(call)
        if outcome == "answered":
            import response_ai
            if row["not_interested"]:
                outcome = "not_interested"
            elif await response_ai._upcoming_booking(conn, row["phone"], row["lead_email"]):
                outcome = "booked"
        if call.get("disconnection_reason") == "user_requested_dnc" and row["source"] != "test":
            await _tag_dnc(conn, row["client_id"], row["phone"])
        await conn.execute(
            "UPDATE client_voice_calls SET status = 'done', outcome = $2, updated_at = now() WHERE id = $1",
            row["id"], outcome)
        row = await conn.fetchrow("SELECT * FROM client_voice_calls WHERE id = $1", row["id"])
    await _after_attempt(row, outcome)


async def _after_attempt(row, outcome: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        if row["source"] == "test":
            return
        if outcome in ("no_answer", "voicemail"):
            if row["attempt"] == 1 and not row["double_dial"]:
                await _insert_attempt(conn, client_id=row["client_id"], phone=row["phone"],
                                      run_at=datetime.now(timezone.utc) + timedelta(seconds=15), source=row["source"],
                                      attempt=1, seq_id=row["seq_id"], double_dial=True, lead_name=row["lead_name"],
                                      lead_email=row["lead_email"], partial_id=row["partial_id"],
                                      texted_first=row["texted_first"], note=row["note"],
                                      agent_kind=row["agent_kind"] or "ads", lead_since=row["lead_since"],
                                      form_info=row["form_info"])
                return
            if row["attempt"] == 1 or row["source"] == "callback":
                await _release_text(conn, row, after_call=False,
                                    voicemail=outcome == "voicemail")
            await _schedule_next(conn, row)
            return
        # A real conversation (or unknown): no more calls in this sequence.
        await _cancel_rest(conn, row["seq_id"], f"call {outcome}")
        if outcome == "answered" and not row["transferred"]:
            await _release_text(conn, row, after_call=True)
        elif row["partial_id"]:
            await conn.execute(
                "UPDATE booking_partials SET followup_skipped = coalesce(followup_skipped, $2) WHERE id = $1",
                row["partial_id"], f"voice call {outcome}")


async def _schedule_next(conn, row) -> None:
    if row["source"] in ("callback", "lastcall"):  # lastcall: the offer ends today, no retries
        return
    nxt = row["attempt"] + 1
    if nxt > 4:
        return
    if await conn.fetchval(
        "SELECT 1 FROM client_voice_calls WHERE seq_id = $1 AND attempt >= $2 AND status IN ('pending', 'dialing', 'ringing', 'in_progress')",
        row["seq_id"], nxt,
    ):
        return
    tz = await _tz(row["client_id"], row["phone"])
    first = await conn.fetchrow("SELECT run_at FROM client_voice_calls WHERE id = $1", row["seq_id"])
    anchor = first["run_at"].astimezone(tz)
    now = datetime.now(tz)
    run_at = None
    if nxt == 2:
        cand = now + RETRY_2_AFTER
        if _in_window(cand):
            run_at = cand
        else:
            nxt = 3
    if nxt == 3:
        cand = (anchor + timedelta(days=1)).replace(hour=RETRY_3_AT[0], minute=RETRY_3_AT[1], second=0, microsecond=0)
        while cand < now + timedelta(hours=2):
            cand += timedelta(days=1)
        run_at = cand
    if nxt == 4:
        cand = (anchor + timedelta(days=2)).replace(hour=RETRY_4_AT[0], minute=RETRY_4_AT[1], second=0, microsecond=0)
        while cand < now + timedelta(hours=12):
            cand += timedelta(days=1)
        run_at = cand
    await _insert_attempt(conn, client_id=row["client_id"], phone=row["phone"], run_at=run_at, source=row["source"],
                          attempt=nxt, seq_id=row["seq_id"], lead_name=row["lead_name"], lead_email=row["lead_email"],
                          partial_id=row["partial_id"], texted_first=True, note=row["note"],
                          agent_kind=row["agent_kind"] or "ads", lead_since=row["lead_since"], form_info=row["form_info"])


async def _cancel_rest(conn, seq_id: int | None, reason: str) -> None:
    if seq_id is None:
        return
    await conn.execute(
        "UPDATE client_voice_calls SET status = 'skipped', outcome = 'skipped', error = $2, updated_at = now() "
        "WHERE seq_id = $1 AND status = 'pending'", seq_id, reason)


async def _release_text(conn, row, after_call: bool, voicemail: bool = False) -> None:
    """Hand first contact to text once: the Meta opener (written from the call
    when there was one), or the funnel's unfinished-booking text."""
    if row["source"] == "test" or row["texted_first"]:
        return
    if await conn.fetchval("SELECT 1 FROM client_voice_calls WHERE seq_id = $1 AND text_released", row["seq_id"]):
        return
    await conn.execute("UPDATE client_voice_calls SET text_released = true WHERE id = $1", row["seq_id"])
    if row["partial_id"] and not after_call:
        await conn.execute("UPDATE booking_partials SET voice_released_at = now() WHERE id = $1", row["partial_id"])
        return
    if row["partial_id"]:
        await conn.execute(
            "UPDATE booking_partials SET followup_skipped = coalesce(followup_skipped, 'voice call answered') WHERE id = $1",
            row["partial_id"])
    if after_call:
        transcript = (await conn.fetchval("SELECT transcript FROM client_voice_calls WHERE id = $1", row["id"])) or ""
        note = ("You (the clinic's virtual assistant) just spoke with this lead on the phone, but they didn't book. "
                "Here's the call transcript:\n" + transcript[-3000:] +
                "\nSend ONE short text that picks up naturally from that call (don't re-introduce yourself or repeat "
                "what was said), making it easy to book whenever they're ready.")
    elif row["source"] == "lastcall":
        note = ("This is the FINAL WEEK of the clinic's offer this lead asked about a while back (they never came in"
                + (f"; {row['note']}" if row["note"] else "") + "). You just tried calling them twice"
                + (" and left a voicemail" if voicemail else "") + ". Send ONE short text: it's the final week for "
                "the offer, you didn't want them to miss it, and ask if they'd like you to grab them a time.")
    elif row["source"] == "funnel":
        note = ("This lead started booking on the clinic's website but didn't finish. You just tried calling them twice"
                + (" and left a voicemail" if voicemail else "") + ". Send the opening text: mention you just tried "
                "calling, and help them grab a time.")
    else:
        note = ("You just tried calling this lead twice" + (" and left a voicemail" if voicemail else "") +
                ". Send the opening text: mention you just tried calling, and continue by text.")
    await conn.execute(
        "INSERT INTO meta_lead_openers (client_id, phone, lead_name, lead_email, run_at, note) VALUES ($1,$2,$3,$4, now(), $5)",
        row["client_id"], row["phone"], row["lead_name"], row["lead_email"], note,
    )


async def _tag_dnc(conn, client_id: int, phone: str) -> None:
    cid = await conn.fetchval(
        "SELECT id FROM contacts WHERE client_id = $1 AND right(regexp_replace(phone, '\\D', '', 'g'), 10) = $2 LIMIT 1",
        client_id, _digits10(phone))
    await lead_flags.add_tag(cid, DO_NOT_CALL_TAG)


# ── Live-call functions (Retell custom tools) ────────────────────────────────

async def _clinic_open(client_id: int, phone: str) -> bool:
    now = datetime.now(await _tz(client_id, phone))
    return now.weekday() < 5 and 9 <= now.hour < 17


async def run_function(name: str, args: dict, call: dict) -> str:
    import response_ai
    meta = call.get("metadata") or {}
    row = await get_row(int(meta.get("row_id") or 0), meta.get("token") or "")
    if not row:
        return "Error: unknown call."
    client_id, phone = row["client_id"], row["phone"]
    pool = await get_pool()
    if row["source"] != "test":
        async with pool.acquire() as conn:
            await response_ai._get_or_create_conversation(conn, client_id, phone)

    if name == "check_availability":
        return await response_ai._execute_tool(client_id, phone, "check_availability", args)
    if name == "book_appointment":
        if row["source"] == "test":
            v = await _visit_info(client_id)
            if v and v["price_cents"]:
                return (f"(Test call: nothing was booked or texted.) Act exactly as for a real paid visit: tell them "
                        f"you've just texted them a link to lock in {args.get('date')} at {args.get('time')} and pay the "
                        f"${v['price_cents'] / 100:g} there, and that the spot is held for them while they do.")
            return f"(Test call: nothing was booked.) Pretend it worked: confirm {args.get('date')} at {args.get('time')}."
        return await response_ai._execute_tool(client_id, phone, "propose_appointment", args)
    if name == "mark_not_interested":
        async with pool.acquire() as conn:
            await conn.execute("UPDATE client_voice_calls SET not_interested = true WHERE id = $1", row["id"])
            if args.get("do_not_call") and row["source"] != "test":
                await _tag_dnc(conn, client_id, phone)
        if row["source"] != "test":
            await response_ai._execute_tool(client_id, phone, "close_conversation", {"reason": args.get("reason") or "Not interested (call)"})
        return "Done. Thank them warmly and end the call."
    if name == "mark_unqualified":
        if row["source"] != "test":
            await response_ai._execute_tool(client_id, phone, "mark_unqualified", args)
        return "Tagged. Close politely and end the call."
    if name == "escalate_to_human":
        if row["source"] == "test":
            return "(Test call: no escalation sent.) Tell them someone from the clinic will reach out."
        return await response_ai._execute_tool(client_id, phone, "escalate_to_human", args)
    if name == "schedule_callback":
        return await _schedule_callback(row, args)
    if name == "transfer_to_clinic":
        return await _transfer(row, args)
    return f"Unknown function {name}."


async def _schedule_callback(row, args: dict) -> str:
    tz = await _tz(row["client_id"], row["phone"])
    try:
        hh, mm = (args.get("time") or "10:00").split(":")[:2]
        when = datetime.strptime(args.get("date") or "", "%Y-%m-%d").replace(hour=int(hh), minute=int(mm), tzinfo=tz)
    except Exception:
        return "Couldn't read that. Use date YYYY-MM-DD and time HH:MM (24h, clinic time)."
    if when < datetime.now(tz) + timedelta(minutes=10):
        return "That time has passed. Ask for another."
    if not _in_window(when):
        return "Calls only go out 8am to 7:45pm clinic time. Ask for a time in that window."
    if row["source"] == "test":
        return f"(Test call: nothing scheduled.) Confirm you'll call {when.strftime('%A at %I:%M %p').replace(' 0', ' ')}."
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _cancel_rest(conn, row["seq_id"], "lead asked for a callback")
        await _insert_attempt(conn, client_id=row["client_id"], phone=row["phone"], run_at=when, source="callback",
                              attempt=1, seq_id=row["seq_id"], lead_name=row["lead_name"], lead_email=row["lead_email"],
                              texted_first=True, note=args.get("note"), agent_kind=row["agent_kind"] or "ads",
                              lead_since=row["lead_since"], form_info=row["form_info"])
    return f"Scheduled. Confirm you'll call them back {when.strftime('%A at %I:%M %p').replace(' 0', ' ')} and end the call."


async def _transfer(row, args: dict) -> str:
    """Redirect the live Twilio call to the clinic (Retell can't transfer on
    custom telephony). Business hours only."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        cfg = await _config(conn, row["client_id"])
    target = e164(cfg["call_forward_number"] or cfg["client_phone"]) if cfg else None
    caller = _caller(cfg, row)
    if not target or not row["twilio_call_sid"] or not caller:
        return "Transfer isn't available. Use escalate_to_human and tell them someone will call back."
    if row["source"] == "test":
        # Never ring a real clinic from a test call (it nearly did, 2026-11-15).
        open_now = await _clinic_open(row["client_id"], row["phone"])
        return ("(Test call: nothing was dialed.) Tell them "
                + ("you're connecting them to the team now." if open_now else
                   "the team is out right now and someone from the clinic will call them back during business hours."))
    if not await _clinic_open(row["client_id"], row["phone"]):
        return ("The clinic is closed right now, so you can't transfer. Use escalate_to_human and tell them "
                "someone from the clinic will call them back during business hours.")
    from twilio.twiml.voice_response import VoiceResponse
    base = _base_url()
    vr = VoiceResponse()
    dial = vr.dial(caller_id=caller[1], timeout=25, answer_on_bridge=True,
                   action=f"{base}/webhooks/voice-agent/transfer-done?id={row['id']}&t={row['token']}", method="POST")
    dial.number(target)
    twiml = str(vr)

    async def _later():
        await asyncio.sleep(4)  # let the agent finish "connecting you now"
        try:
            await asyncio.to_thread(lambda: _twilio_for(caller[0]).calls(row["twilio_call_sid"]).update(twiml=twiml))
        except Exception as e:
            print(f"[voice_agent] transfer failed for row {row['id']}: {e}", flush=True)
    asyncio.create_task(_later())
    async with pool.acquire() as conn:
        await conn.execute("UPDATE client_voice_calls SET transferred = true WHERE id = $1", row["id"])
    return "Transferring. Say one short line like 'Connecting you to the team now, one moment' and nothing else."


async def transfer_done_twiml(row, dial_status: str) -> str:
    from twilio.twiml.voice_response import VoiceResponse
    vr = VoiceResponse()
    if dial_status not in ("completed", "answered"):
        vr.say("Sorry, nobody could pick up right now. Someone from the clinic will call you back soon. Goodbye.")
        if row["source"] != "test":
            pool = await get_pool()
            async with pool.acquire() as conn:
                name = await conn.fetchval("SELECT name FROM clients WHERE id = $1", row["client_id"])
                await conn.execute(
                    "INSERT INTO todos (text, description, due_date) VALUES ($1, $2, $3)",
                    f"Call back {row['lead_name'] or row['phone']} ({name})",
                    f"The voice agent tried to transfer {row['phone']} to the clinic but nobody answered.",
                    datetime.now(timezone.utc).date(),
                )
    vr.hangup()
    return str(vr)


# ── Retell agent per client ──────────────────────────────────────────────────

_VOICE_RULES = """
You are on a live PHONE CALL, not texting. Your name is {{agent_name}} and you work at {{clinic_name}},
helping new patients get booked.
Who you're calling: {{lead_full_name}}. Why: {{lead_context}}. Right now it's {{today}}.
What they told us on the form: {{form_answers}}
The visit you book (from the clinic's calendar): {{visit_info}}. Never mention how long the visit is unless they
ask; then use this length.

How you sound: calm, low-key and matter-of-fact, like someone who makes these calls all day. Even,
level tone. Not bubbly, not salesy, never excited. Never use exclamation marks. Never say "perfect",
"awesome", "wonderful", "fantastic" or "great!" as a reaction. Don't narrate what you're doing ("I'm
going to go ahead and...", "let me just..."); just do the step and move on. A plain confirmation
("Okay.", "Okay, sounds good.", "Alright.") is all a step needs.

How the call goes:
- HOW THE OPENER SOUNDS: relaxed and a little offhand, like you're calling someone back, not reading a
  notice. Break it into short, easy phrases with a natural "so" or "um" in it, use "it's ... over at"
  instead of "this is ... from", and let the details trail in casually ("...something about some back
  pain?") instead of one long, tidy sentence. Say the offer's name lightly in passing, not announced.
- Open by checking you've got the right person, then introduce yourself by first name and the clinic and
  say how they reached you, naming the clinic's REAL offer from the business info below (the visit
  above). Form lead whose form answers name what they're dealing with: "Hey, it's {{agent_name}} over
  at {{clinic_name}}. So, um, I saw you filled out our <platform> form for <offer>, something about some
  <issue>. Is that right?" (<issue> in plain spoken words, e.g. "back pain"; <platform> = Facebook or Instagram from
  "Filled out on", else leave it out). WAIT for them to confirm (this checks you've got the right person
  and that they know what you're calling about). Once they say yes: "Okay. And how long has that been
  going on?", then skip the "how long" question below since you just asked it. If they say no or don't
  remember the form, use the form info anyway, never ask what's going on: "Oh, no problem, it was one of
  our Facebook ads. It says here you put down some <issue>. How long's that been going on?" Only if
  the form answers don't say what's wrong: "...I saw you filled out our form for <offer>. Is that
  right?", then after they confirm, "Okay. So what's been going on?" Website lead: "...I saw you started booking <offer> on our
  website..." Never use an offer name that isn't in the business info; if unclear, say "our form".
- Last-day call (the Why above says today is the last day of the offer): "This is {{agent_name}} from
  {{clinic_name}}. You filled out our form a few weeks back for <offer>, and I just wanted to let you
  know today's the last day for it. Is that still something you're dealing with?" If yes, carry on
  with the questions and pitch below as normal. If they're fine or not interested, say "Okay, no
  problem." and wrap up politely.
- Call screener (an automated voice asking your name and why you're calling): answer in one short
  sentence ("It's {{agent_name}} from {{clinic_name}}, following up on their form."). When it
  hands you off ("please stay on the line"), just say "Sure." and wait. When the person comes on
  or you're told to greet them, open with "Hi, is this {{lead_first_name}}?" and continue as
  normal. If the call simply starts with silence, open the same way.
- In the opening, a reply that doesn't quite make sense (e.g. "yes, this is done") is almost always
  speech recognition mishearing their name: treat it as "yes, this is me" and carry on with your intro.
  Never end the call before you've introduced yourself and they've clearly said they're not interested.
  Don't call yourself an assistant, AI or virtual anything. But if they sincerely ask whether you're a
  real person or an AI, never claim to be human: say lightly that you're the clinic's AI assistant and
  carry on helping.
- After they say what's going on, ask one at a time, with the filler: "Okay, and um, how long have you
  been dealing with that?" and "Gotcha. And uh, have you tried anything for it so far?"
  (never suggest what they tried was wrong). Skip one if they already told you.
- Then ONE last question before the pitch, every call: "Okay. And you live near <area>, correct?"
  <area> = the clinic's city or area from the business info below (e.g. "Las Vegas"). If yes, go to the
  pitch. If they're not nearby, tell them plainly where the clinic is and ask if that would work for them;
  if it clearly won't, call mark_unqualified, thank them and wrap up politely. Never skip this question,
  even if their area code looks local.
- Acknowledge each answer with a plain, neutral word or two ("Got it.", "Okay.", "Okay, gotcha.") and
  move on. Never add your own opinion or judgment about what they said (no "three months is a long
  time", "that must be hard", "that's great").
- The pitch (Dylan's wording, keep this shape): one short turn, right after the location answer:
  "Awesome. So if you're still interested, you do qualify for our <offer>. It's a call that goes over how
  we help solve things like <their problem>. Is that something you'd wanna get scheduled in?"
  <offer> = the offer's name from the business info (e.g. free "Why Does It Keep Coming Back?" call).
  <their problem> = their issue in their own plain words, with what they told you if it fits naturally
  (e.g. "back pain that keeps coming back"). Small wording changes so it doesn't sound recited are fine,
  but keep the order: "Awesome" -> you qualify for <offer> -> what the call goes over -> the ask.
  ("Awesome" is allowed here, as the one exception to the no-"awesome" rule.)
  - Everyday words only, nothing clinical or brochure-like ("addressing the root cause", "our approach").
  - Don't add perks or urgency ("free for a limited time") unless the rules below say so; mention "free"
    only if it's part of the offer's name or they ask about cost.
  - No restating their answers as a sentence, no "we've helped a lot of people", no extra selling points.
  - The ONLY question is the final "Is that something you'd wanna get scheduled in?"
  Never list the visit's contents ("history", "movement screen", "whether PT can help"), never read
  out the business info, never invent details, never state the visit length, and never knock what
  they tried.
- THE OFFER'S NAME: the first time you mention the offer, say its full name exactly as the business info
  names it (e.g. our free "Why Does It Keep Coming Back?" call). Never a generic "free phone call" or
  "consultation". After it's been said once (including in your opening), just say "the call" / "it".
- Lines the business info wants said at the invite (e.g. "free for a limited time"): keep them out of the
  pitch; say them only if they ask about cost or hesitate, once, casually.
- Only call check_availability AFTER they say yes to that offer. Never jump to the calendar right after
  they answer a question. Apart from the pitch, keep every turn short: one or two sentences.
- To book: call check_availability, then offer the two times as a full, natural question, e.g. "I've
  got Tuesday at nine in the morning or four thirty in the afternoon. Which works better for you?"
  When they pick one call
  book_appointment with that date and 24h time. Read the result and say exactly what it says happened
  (for a paid visit you text them a link to finish; say so). Never invent times or confirm a booking
  the tool didn't confirm.
- Busy right now -> offer to call back: schedule_callback with the time they give. Prefer text ->
  tell them you'll text them and end the call.
- Not interested, wrong number, or "stop calling" -> mark_not_interested (do_not_call true if they
  don't want calls), thank them, end the call.
- Clearly outside who the clinic can help (e.g. lives far outside the area) -> mark_unqualified.
- Wants a person, has a question you can't answer, or anything urgent/medical -> transfer_to_clinic.
  If that says it isn't available, use escalate_to_human and tell them the team will call back.
- Sound like a real person, not a script: contractions ("I'm", "you're"), short
  plain sentences under about 15 words, one question at a time, and vary how you start sentences.
  A natural "okay", "gotcha" or "so" now and then is good, never more than one per turn. Use small
  fillers like real phone talk: about every other turn, put one "um," "uh," or "so, uh," near the
  start (e.g. "Um, so you've had back pain..."). Never two in one sentence. No lists, no em dashes, no "certainly"
  or "absolutely", and don't parrot their exact sentence word for word (paraphrase it).
- Never give medical advice or diagnose. Never quote prices unless the business info below gives one
  and they ask. Spell nothing out letter by letter unless asked. Say times naturally ("ten thirty").
- After a booking goes through: confirm the day and time once, tell them a confirmation text is on its
  way, and ask if there's anything else you can help with. Then STOP and wait for their answer; never
  say goodbye in the same turn as that question. Only after they say they're done, say a short, plain
  goodbye ("Okay, see you Tuesday. Take care.") and call end_call. Never hang up right after confirming.
"""


# The database reactivation voice agent's call script (its own Retell LLM).
# Everything except the opening (tone, questions, pitch, booking) is the same
# as the ads agent, so those parts are reused from _VOICE_RULES.
_REACT_HEAD = """
You are on a live PHONE CALL, not texting. Your name is {{agent_name}} and you work at {{clinic_name}}.
This is a DATABASE REACTIVATION call: {{lead_full_name}} filled out the clinic's ad form on {{form_date}}
but never came in. Why you're calling: {{lead_context}}. Right now it's {{today}}.
The visit you book (from the clinic's calendar): {{visit_info}}. Never mention how long the visit is unless they
ask; then use this length.
"""
_REACT_OPENING = """
What they told us on the form: {{form_answers}}

The opening (open on THEIR issue from the form, not the offer):
- HOW THE OPENER SOUNDS: relaxed and a little offhand, like you're calling someone back, not reading a
  notice. Break it into short, easy phrases with a natural "so" or "um" in it, use "it's ... over at"
  instead of "this is ... from", and let the details trail in casually ("...something about some back
  pain?") instead of one long, tidy sentence. Say the offer's name lightly in passing, not announced.
- After they confirm it's them: "Hey {{lead_first_name}}, it's {{agent_name}} over at {{clinic_name}}. So, um, you
  filled out our <platform> form a couple weeks ago for our <offer>, something about some <issue>. Is that
  right?" Say "a couple weeks ago", never the exact date (Dylan, 2026-11-17); only give the date
  ({{form_date}}) if they ask when. Then WAIT for them to confirm (this checks you've got the right person and that they know what
  you're calling about). Once they say yes: "Okay. Is that still bothering you?"
  <platform> = "Facebook" or "Instagram", from "Filled out on" in the form answers. If that isn't there, leave the
  platform out: "You filled out our lead form a couple weeks ago...".
  <offer> = the offer's FULL NAME exactly as the business info below names it (e.g. free "Why Does It Keep Coming
  Back?" call), never a generic "free call" or "consultation"; never invent one. If unclear, leave "for our <offer>" out.
  <issue> = what they said they're dealing with on the form, in plain spoken words ("back pain", "knee pain",
  "shoulder pain", "sciatica"); lowercase, no form wording. If the form answers don't name an issue, end with
  "...for our <offer>. Is that right?", then after they confirm, "Okay. Are you still dealing with what was
  bothering you?"
- If they're still dealing with it: you already know WHAT it is, so skip "what's been going on" and go straight
  to "Okay, and um, how long have you been dealing with that?", then the rest of the questions, pitch and booking
  below as normal.
- This is the ONE call where the offer's final week is mentioned: once, folded into the pitch, e.g. "Awesome.
  So if you're still interested, you do qualify for our <offer>, and this is the last week we're doing those.
  It's a call that goes over how we help solve things like <their problem>. Is that something you'd wanna
  get scheduled in?"
- If they're fine now or not interested: "Okay, no problem. Glad you're doing better." and wrap up politely
  (mark_not_interested only if they say they don't want calls or aren't interested).
- If they say no or don't remember the form, use the form info anyway: "Oh, no problem, it was one of our
  Facebook ads a few weeks back. It says here you put down some <issue>. Is that still bothering you?"
- Never pressure.

Everything else about the call:
"""


def _react_rules() -> str:
    """Reactivation header + the ads agent's "How you sound" tone section
    (same delivery) + the reactivation opening + the ads agent's rules from
    'Call screener' on, so tone, questions, pitch and booking stay identical."""
    t0, t1 = _VOICE_RULES.index("How you sound"), _VOICE_RULES.index("How the call goes:")
    i = _VOICE_RULES.index("- Call screener")
    return (_REACT_HEAD + "\n" + _VOICE_RULES[t0:t1].rstrip() + "\n" + _REACT_OPENING
            + _VOICE_RULES[i:].replace("following up on their form", "following up on their request"))


def default_script(kind: str = "ads") -> str:
    """The built-in call script (what the Agents tab shows until it's edited)."""
    return (_react_rules() if kind == "react" else _VOICE_RULES).strip() + "\n"


def script_for(cfg, kind: str = "ads") -> str:
    """This client's script: Dylan's edited one if saved, else the default."""
    custom = (cfg[f"voice_script_{kind}"] or "").strip()
    return (custom + "\n") if custom else default_script(kind)


def agent_name(cfg) -> str:
    """The name the agent introduces itself by: set per client, else the
    voice's own name (retell-Cimo -> Cimo, 11labs-Marissa -> Marissa)."""
    if (cfg["voice_agent_name"] or "").strip():
        return cfg["voice_agent_name"].strip()
    vid = cfg["voice_id"] or DEFAULT_VOICE_ID
    return vid.split("-", 1)[-1].split("-")[0].capitalize()


def _llm_body(cfg, kind: str = "ads") -> dict:
    base = _base_url()
    fn_url = f"{base}/webhooks/retell/function"

    def custom(name, description, props, required=(), speak=False, msg=None, speak_after=True):
        tool = {"type": "custom", "name": name, "url": fn_url, "description": description,
                "parameters": {"type": "object", "properties": props, "required": list(required)},
                "speak_during_execution": speak, "speak_after_execution": speak_after, "timeout_ms": 30000}
        if msg:
            tool["execution_message_description"] = msg
        return tool

    tools = [
        {"type": "end_call", "name": "end_call", "description": "Hang up only after the conversation is really over (they said they're done, not interested, or asked you to stop) and you've said goodbye. Never during the opening."},
        custom("check_availability", "Find real open appointment times. Returns the earliest day's two options.",
               {"after_date": {"type": "string", "description": "YYYY-MM-DD to search from; omit for today"}},
               speak=True, msg="Say only 'One sec.' in a flat, casual tone."),
        custom("book_appointment", "Book the time the caller agreed to (one of the times you offered).",
               {"date": {"type": "string", "description": "YYYY-MM-DD"}, "time": {"type": "string", "description": "HH:MM 24h"},
                "reason": {"type": "string", "description": "Why they're coming in, one short line"},
                "lead_name": {"type": "string", "description": "ONLY if a previous result said the name is missing"},
                "reschedule": {"type": "boolean", "description": "ONLY if they already have a visit and want to move it"}},
               required=("date", "time"), speak=True, msg="Say only 'Okay.' in a flat, casual tone."),
        custom("schedule_callback", "Caller asked you to call back later; schedule it.",
               {"date": {"type": "string", "description": "YYYY-MM-DD clinic time"}, "time": {"type": "string", "description": "HH:MM 24h"},
                "note": {"type": "string", "description": "What to pick back up"}}, required=("date", "time")),
        custom("mark_not_interested", "Caller isn't interested, has the wrong number, or wants no more calls.",
               {"reason": {"type": "string"}, "do_not_call": {"type": "boolean", "description": "true if they asked not to be called"}},
               required=("reason",)),
        custom("mark_unqualified", "Caller clearly can't be a patient (e.g. outside the service area).",
               {"reason": {"type": "string"}}, required=("reason",)),
        custom("transfer_to_clinic", "Connect the caller to the clinic's team (business hours only).",
               {"reason": {"type": "string"}}, required=("reason",)),
        custom("escalate_to_human", "Flag this lead for the clinic's team to follow up by phone.",
               {"reason": {"type": "string"}, "urgent": {"type": "boolean"}}, required=("reason",)),
    ]
    business = (cfg["response_ai_context"] or "").strip()
    rules = (cfg["response_ai_rules"] or "").strip()
    prompt = (script_for(cfg, kind).replace("__AGENT_NAME__", "{{agent_name}}")
              + "\nBusiness info and rules (the same ones the clinic's text agent uses):\n" + business
              + (f"\n\nExtra rules from the clinic (ignore any about texting format):\n{rules}" if rules else ""))
    return {
        "general_prompt": prompt,
        "begin_message": "Hi, is this {{lead_first_name}}?",
        "start_speaker": "agent",
        "general_tools": tools,
        "default_dynamic_variables": {"agent_name": agent_name(cfg), "lead_first_name": "there", "lead_full_name": "unknown",
                                      "lead_context": "they reached out to the clinic",
                                      "clinic_name": cfg["client_name"] or "the clinic", "today": "",
                                      "visit_info": "use the business info", "form_date": "a few weeks back",
                                      "form_answers": "none on file"},
    }


def _keywords(cfg, lead_name: str | None = None) -> list[str]:
    first = (lead_name or "").strip().split(" ")[0]
    return [k for k in [first, cfg["client_name"], agent_name(cfg)] if k] + PT_KEYWORDS


def _style(cfg) -> dict:
    # Default = Retell stock (Dylan, 2026-11-17); "tuned" is the original preset.
    return VOICE_STYLES.get(cfg["voice_style"] or "stock", VOICE_STYLES["stock"])


def _voice_fields(cfg) -> dict:
    """The client's voice exactly as set in the admin view (voice, speed,
    style). Used for the agent sync AND sent with every call's override, so a
    live call can never sound different from the synced agent (Dylan,
    2026-11-19: real calls didn't sound like the admin view's voice)."""
    vid = cfg["voice_id"] or DEFAULT_VOICE_ID
    return {
        "voice_id": vid,
        "voice_speed": float(cfg["voice_speed"]) if cfg["voice_speed"] else DEFAULT_VOICE_SPEED,
        **({"voice_model": _style(cfg)["voice_model"]} if vid.startswith("11labs-") else {}),
        **_style(cfg)["settings"],
    }


def _agent_body(cfg, llm_id: str, kind: str = "ads") -> dict:
    return {
        "agent_name": f"{cfg['client_name']} - DigiGrowth " + ("reactivation voice agent" if kind == "react" else "voice agent"),
        "response_engine": {"type": "retell-llm", "llm_id": llm_id},
        **_voice_fields(cfg),
        "boosted_keywords": _keywords(cfg),
        "language": "en-US",
        "webhook_url": f"{_base_url()}/webhooks/retell",
        "webhook_events": ["call_ended", "call_analyzed", "transcript_updated"],
        "voicemail_option": {"action": {"type": "hangup"}},
        "end_call_after_silence_ms": 20000,
        "max_call_duration_ms": 900000,
        "post_call_analysis_data": [
            {"type": "system-presets", "name": "call_summary"},
            {"type": "system-presets", "name": "call_successful"},
            {"type": "system-presets", "name": "user_sentiment"},
        ],
    }


async def sync_all_agents() -> None:
    """Run once after each deploy: push the current default voice settings and
    prompt rules to every client that already has a Retell agent, so changes
    to the defaults reach all clients without clicking SYNC on each one."""
    if not _api_key():
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        ids = [r["client_id"] for r in await conn.fetch(
            "SELECT client_id FROM client_marketing_config WHERE coalesce(retell_agent_id, '') != ''")]
        react_ids = [r["client_id"] for r in await conn.fetch(
            "SELECT client_id FROM client_marketing_config WHERE coalesce(react_retell_agent_id, '') != ''")]
    for cid in ids:
        try:
            await sync_agent(cid)
        except Exception as e:
            print(f"[voice_agent] startup sync failed for client {cid}: {e}", flush=True)
    for cid in react_ids:
        try:
            await sync_agent(cid, "react")
        except Exception as e:
            print(f"[voice_agent] startup reactivation sync failed for client {cid}: {e}", flush=True)
    print(f"[voice_agent] startup sync done for {len(ids)} agent(s)", flush=True)


async def sync_agent(client_id: int, kind: str = "ads") -> dict:
    """Create or update this client's Retell LLM + agent ('ads' or the
    separate 'react' reactivation agent) from the text agent's current
    context/rules. Safe to re-run (do it after editing the context)."""
    p = "react_" if kind == "react" else ""
    pool = await get_pool()
    async with pool.acquire() as conn:
        cfg = await _config(conn, client_id)
    if not cfg:
        raise ValueError("Client not found")
    if not (cfg["response_ai_context"] or "").strip():
        raise ValueError("Write the Facebook Leads Agent's context first; the voice agent uses the same one")
    llm_col, agent_col = f"{p}retell_llm_id", f"{p}retell_agent_id"
    try:
        if cfg[llm_col]:
            await _retell("PATCH", f"/update-retell-llm/{cfg[llm_col]}", _llm_body(cfg, kind))
            llm_id = cfg[llm_col]
        else:
            llm_id = (await _retell("POST", "/create-retell-llm", _llm_body(cfg, kind)))["llm_id"]
        if cfg[agent_col]:
            await _retell("PATCH", f"/update-agent/{cfg[agent_col]}", _agent_body(cfg, llm_id, kind))
            agent_id = cfg[agent_col]
        else:
            agent_id = (await _retell("POST", "/create-agent", _agent_body(cfg, llm_id, kind)))["agent_id"]
    except Exception as e:
        async with pool.acquire() as conn:
            await conn.execute(f"UPDATE client_marketing_config SET {p}voice_sync_error = $2 WHERE client_id = $1",
                               client_id, str(e)[:400])
        raise
    async with pool.acquire() as conn:
        await conn.execute(
            f"""UPDATE client_marketing_config SET {llm_col} = $2, {agent_col} = $3, {p}voice_synced_at = now(),
                   {p}voice_sync_error = NULL, voice_id = coalesce(voice_id, $4) WHERE client_id = $1""",
            client_id, llm_id, agent_id, DEFAULT_VOICE_ID)
    # The reactivation agent shares the Facebook ads agent's voice settings:
    # re-syncing the ads agent re-syncs it too, so they never drift apart.
    if kind == "ads" and cfg["react_retell_agent_id"]:
        try:
            await sync_agent(client_id, "react")
        except Exception as e:
            print(f"[voice_agent] reactivation agent re-sync failed for client {client_id}: {e}", flush=True)
    return {"ok": True, "llm_id": llm_id, "agent_id": agent_id}


async def list_voices() -> list[dict]:
    voices = await _retell("GET", "/list-voices")
    return [{k: v.get(k) for k in ("voice_id", "voice_name", "provider", "gender", "accent", "age", "preview_audio_url")}
            for v in voices if isinstance(v, dict)]


async def status(client_id: int, kind: str = "ads") -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        cfg = await _config(conn, client_id)
        calls = await conn.fetch(
            """SELECT id, phone, lead_name, source, attempt, double_dial, status, outcome, error, run_at, dialed_at,
                      duration_ms, summary, recording_url, transcript, disconnection_reason, seq_id
               FROM client_voice_calls WHERE client_id = $1 AND agent_kind = $2
               ORDER BY coalesce(dialed_at, run_at) DESC LIMIT 60""",
            client_id, kind)
        stats = await conn.fetchrow(
            """SELECT count(DISTINCT seq_id) FILTER (WHERE source <> 'test') AS leads,
                      count(DISTINCT seq_id) FILTER (WHERE source <> 'test' AND outcome IN ('answered','booked','not_interested')) AS reached,
                      count(DISTINCT seq_id) FILTER (WHERE source <> 'test' AND outcome = 'booked') AS booked
               FROM client_voice_calls WHERE client_id = $1 AND agent_kind = $2
                 AND created_at > now() - interval '30 days'""",
            client_id, kind)
    return {
        "visit": await _visit_info(client_id),
        "ready_problem": _ready(cfg, kind) if cfg else "no config",
        "retell_key_set": bool(_api_key()),
        "stats_30d": dict(stats) if stats else {},
        "calls": [dict(c) for c in calls],
    }
