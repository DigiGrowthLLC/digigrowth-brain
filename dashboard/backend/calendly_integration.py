"""
Calendly integration for response_ai.py — looks up a client's REAL open
time slots (check_availability) and, since Calendly's Scheduling API
launched (found live 2026-09-14, superseding this module's original
read-only-only design), can create a genuinely CONFIRMED booking directly
(create_booking) without the lead having to tap through anything.

Auth is a Calendly Personal Access Token the client generates from their
own Calendly account (Integrations & Apps -> API & Webhooks -> Generate New
Token) — or Dylan's, once added as an admin on that client's account — and
pastes into their Marketing Setup (client_marketing_config.calendly_api_token).
Same "one credential per client, pasted in" pattern as the Gmail refresh
token. The Scheduling API (POST /invitees) requires the account be on a
paid Calendly plan and the token have scheduled_events:write scope.

create_booking() only ever answers a REQUIRED custom question on the
event type if it can clearly tell what it's asking for (phone number, or
the single other required question treated as "reason for the call") —
any other required question it doesn't recognize means it refuses to
guess and raises, so response_ai.py's propose_appointment can fall back
to texting the lead a direct link to finish it themselves instead of
submitting a wrong or incomplete answer.
"""
import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta, timezone

import httpx

_API_BASE = "https://api.calendly.com"
_CHUNK_DAYS = 7  # Calendly caps a single query window to 7 days


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


async def get_organization_uri(token: str) -> str:
    """The token owner's Calendly organization URI — needed to scope both
    event-type lookups (see _get_matching_event_type) and webhook
    subscriptions (register_webhook below) to the whole org rather than
    just the token owner's own user, same reasoning as that function's
    docstring."""
    async with httpx.AsyncClient(timeout=10) as http:
        me = await http.get(f"{_API_BASE}/users/me", headers=_headers(token))
        _raise_with_context(me)
        return me.json()["resource"]["current_organization"]


async def register_webhook(token: str, callback_url: str, org_uri: str) -> dict:
    """Creates (or, if one already exists at this exact URL, reuses) a
    Calendly webhook subscription for invitee.created events across the
    whole organization — reusing avoids piling up duplicate subscriptions
    on the same Calendly account every time a rep re-clicks "Connect
    Calendly". Returns {"uri": ..., "signing_key": ...}.

    Corrected 2026-09-17 (confirmed live against a real 400 error): Calendly's
    create-subscription response does NOT hand back a signing_key — WE supply
    one as part of the create request, and Calendly signs future payloads
    with it. The original version assumed Calendly generated and returned
    it, which raised KeyError on every real call."""
    signing_key = secrets.token_hex(32)
    async with httpx.AsyncClient(timeout=10) as http:
        existing = await http.get(
            f"{_API_BASE}/webhook_subscriptions",
            headers=_headers(token),
            params={"organization": org_uri, "scope": "organization"},
        )
        _raise_with_context(existing)
        for item in existing.json().get("collection", []):
            if item.get("callback_url") == callback_url:
                # An existing subscription at this URL was signed with
                # whatever key we generated when IT was created — that key
                # is gone (never persisted past that one register_webhook
                # call unless the caller saved it), so it must be deleted
                # and recreated with the new key we're about to generate,
                # never reused as-is.
                del_resp = await http.delete(item["uri"], headers=_headers(token))
                if del_resp.status_code not in (200, 204, 404):
                    _raise_with_context(del_resp)
                break

        resp = await http.post(
            f"{_API_BASE}/webhook_subscriptions",
            headers=_headers(token),
            json={
                "url": callback_url,
                "events": ["invitee.created"],
                "organization": org_uri,
                "scope": "organization",
                "signing_key": signing_key,
            },
        )
        _raise_with_context(resp)
        resource = resp.json()["resource"]
        return {"uri": resource["uri"], "signing_key": signing_key}


async def unregister_webhook(token: str, webhook_uri: str) -> None:
    async with httpx.AsyncClient(timeout=10) as http:
        resp = await http.delete(webhook_uri, headers=_headers(token))
        if resp.status_code not in (200, 204, 404):
            _raise_with_context(resp)


def verify_signature(raw_body: bytes, signature_header: str | None, signing_key: str) -> bool:
    """Calendly signs each webhook payload as `Calendly-Webhook-Signature:
    t=<unix ts>,v1=<hex hmac-sha256 of "t.<raw body>">`. Rejects a missing/
    malformed header, a signature mismatch, or a timestamp more than 5
    minutes old (replay protection) — same tolerance Stripe's docs
    recommend for the identical t=/v1= scheme."""
    if not signature_header:
        return False
    parts = dict(p.split("=", 1) for p in signature_header.split(",") if "=" in p)
    ts, sig = parts.get("t"), parts.get("v1")
    if not ts or not sig:
        return False
    try:
        if abs(time.time() - int(ts)) > 300:
            return False
    except ValueError:
        return False
    expected = hmac.new(
        signing_key.encode(), f"{ts}.{raw_body.decode()}".encode(), hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, sig)


def _raise_with_context(resp: httpx.Response) -> None:
    """httpx's default error message on a 403 is just the status line —
    unhelpful for the one failure mode we've actually hit in practice: a
    token generated with restricted OAuth scopes (e.g. missing users:read)
    instead of a plain Personal Access Token, which Calendly happily
    accepts as "valid" right up until the first API call. Surface the
    response body so the real reason (e.g. "Insufficient scope") ends up in
    logs instead of a bare "403 Forbidden"."""
    if resp.status_code == 403:
        raise RuntimeError(
            f"Calendly returned 403 Forbidden: {resp.text.strip()[:300]} — the token likely lacks "
            "read permissions. Regenerate it from Calendly's own account (not a third-party OAuth "
            "connection) via Integrations & Apps -> API & Webhooks -> Generate New Token."
        )
    if resp.status_code == 400:
        # create_booking's 400s are almost always something diagnosable
        # (a missing/mismatched required question, a slot that just got
        # taken) — httpx's default message is just "400 Bad Request" with
        # none of that, which was a real pain to debug live 2026-09-14.
        raise RuntimeError(f"Calendly returned 400 Bad Request: {resp.text.strip()[:300]}")
    resp.raise_for_status()


async def _get_matching_event_type(http: httpx.AsyncClient, token: str, scheduling_url: str) -> dict | None:
    """Resolves the client's configured scheduling_url to its Calendly
    event type object. Deliberately never guesses "whichever event type
    comes back first" — a Personal Access Token generated by an admin who
    manages multiple people's Calendly (Dylan's own real setup: one token
    sees both his own event types and a client's, since he's a team member
    on their account) can see OTHER people's event types too. "First
    result" happened to be the right one when this was first tested, purely
    by luck of Calendly's ordering that day — the next admin-managed client
    added, or a reordering on Calendly's side, could just as easily point
    this at someone else's calendar entirely. Matching on the exact
    scheduling_url the admin configured (their real public booking link,
    something they can visually verify) is the only safe way to do this.

    Queries by organization, not by the token owner's own user URI —
    ?user=<token's own uri> only reliably returns event types Calendly
    considers "owned" by that exact user, which excludes a teammate's
    event type under conditions that aren't fully predictable (confirmed
    live 2026-09-14: Brandon's own event type stopped appearing under
    Dylan's user-scoped query the moment Brandon renamed its URL slug,
    while the organization-scoped query kept seeing it the whole time).
    Organization scope reliably sees every team member's event types
    regardless of that, which is exactly what this admin-manages-clients
    setup needs."""
    me = await http.get(f"{_API_BASE}/users/me", headers=_headers(token))
    _raise_with_context(me)
    org_uri = me.json()["resource"]["current_organization"]

    target = scheduling_url.strip().rstrip("/")
    page_token = None
    while True:
        params = {"organization": org_uri, "active": "true", "count": 100}
        if page_token:
            params["page_token"] = page_token
        resp = await http.get(f"{_API_BASE}/event_types", headers=_headers(token), params=params)
        _raise_with_context(resp)
        data = resp.json()
        for item in data.get("collection", []):
            if item.get("scheduling_url", "").rstrip("/") == target:
                return item
        page_token = (data.get("pagination") or {}).get("next_page_token")
        if not page_token:
            return None


async def find_earliest_available_times(
    token: str, scheduling_url: str, start_iso: str, max_days: int = 30,
) -> list[dict]:
    """Searches forward from start_iso in 7-day windows (Calendly's own
    per-query cap) until it finds real open slots or exhausts max_days,
    returning the first day's worth found. A newly-active event type often
    has nothing open for the first week or two (the business hasn't set
    availability that far out yet, or the near term is already booked) —
    only ever checking one exact day and giving up the moment it's empty
    means the agent asks the lead to guess-and-check days one at a time
    instead of just finding the real earliest opening itself. Returns
    Calendly's raw slot objects (each has start_time in UTC) — empty list
    if genuinely nothing's open in the whole window, or the scheduling_url
    doesn't match any event type this token can see."""
    async with httpx.AsyncClient(timeout=10) as http:
        event_type = await _get_matching_event_type(http, token, scheduling_url)
        if not event_type:
            return []

        start = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        horizon = start + timedelta(days=max_days)

        window_start = start
        while window_start < horizon:
            window_end = min(window_start + timedelta(days=_CHUNK_DAYS), horizon)
            resp = await http.get(
                f"{_API_BASE}/event_type_available_times",
                headers=_headers(token),
                params={
                    "event_type": event_type["uri"],
                    "start_time": window_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "end_time": window_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )
            _raise_with_context(resp)
            slots = resp.json().get("collection", [])
            if slots:
                return slots
            window_start = window_end
        return []


async def find_slot_scheduling_url(
    token: str, scheduling_url: str, date_str: str, time_str: str, tz,
) -> str | None:
    """Looks up the direct, single-slot Calendly booking link for one
    exact local date/time (e.g. "2026-09-17" / "14:00") — each slot in
    Calendly's own available-times response already carries its own
    scheduling_url pointing straight at that time, one tap from a
    confirmed booking, no re-picking a day on Calendly's page needed.
    Used by propose_appointment as the fallback when create_booking can't
    complete the booking itself (missing email, an unrecognized required
    question, the slot got taken, etc.) — texting the lead this link lets
    them finish it themselves in one tap instead of the reply going out
    with no way to actually confirm anything. Returns None if the slot
    can't be re-matched (already taken, clock drift, bad date/time) —
    caller falls back to the internal-only booking message in that case."""
    async with httpx.AsyncClient(timeout=10) as http:
        event_type = await _get_matching_event_type(http, token, scheduling_url)
        if not event_type:
            return None

        local_day_start = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=tz)
        local_day_end = local_day_start + timedelta(days=1)
        resp = await http.get(
            f"{_API_BASE}/event_type_available_times",
            headers=_headers(token),
            params={
                "event_type": event_type["uri"],
                "start_time": local_day_start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end_time": local_day_end.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )
        _raise_with_context(resp)
        slots = resp.json().get("collection", [])

        target = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=tz)
        for s in slots:
            slot_local = datetime.fromisoformat(s["start_time"].replace("Z", "+00:00")).astimezone(tz)
            if abs((slot_local - target).total_seconds()) < 60:
                return s.get("scheduling_url")
        return None


class RequiredQuestionUnrecognized(Exception):
    """Raised when the event type has a required custom question
    create_booking can't confidently answer — better to refuse and let
    the caller fall back to the tap-to-confirm link than submit a wrong
    or made-up answer to Calendly's booking form."""


async def create_booking(
    token: str, scheduling_url: str, date_str: str, time_str: str, tz,
    name: str, email: str, phone: str, reason: str,
) -> dict:
    """Creates a REAL, immediately-confirmed booking via Calendly's
    Scheduling API (POST /invitees) — no invitee action needed, unlike
    everything else in this module. Requires the connected account be on
    a paid Calendly plan and the token have scheduled_events:write scope
    (verified live against a real event 2026-09-14, then canceled).

    Only supports the "outbound_call" and "inbound_call" location kinds
    (a phone consult, the common case for this system's clients) — any
    other kind (in-person, a conferencing app) raises, since building the
    right location payload for those isn't implemented, and the caller
    should fall back to the tap-to-confirm link instead of guessing.

    Every REQUIRED custom question on the event type must be answered or
    Calendly rejects the whole booking — a phone-number-looking one gets
    `phone`, and exactly one other non-phone required question gets
    `reason` (best guess: the "what brings you in" style question every
    intake form like this tends to have). More than one other required
    question raises RequiredQuestionUnrecognized rather than guessing
    which one `reason` belongs to."""
    async with httpx.AsyncClient(timeout=10) as http:
        event_type = await _get_matching_event_type(http, token, scheduling_url)
        if not event_type:
            raise RequiredQuestionUnrecognized("event type not found")

        locations = event_type.get("locations") or []
        kind = locations[0].get("kind") if locations else None
        if kind == "outbound_call":
            location = {"kind": "outbound_call", "location": phone}
        elif kind == "inbound_call":
            location = {"kind": "inbound_call"}
        else:
            raise RequiredQuestionUnrecognized(f"unsupported location kind: {kind}")

        questions_and_answers = []
        reason_used = False
        for q in event_type.get("custom_questions", []):
            if not q.get("required"):
                continue
            qname = (q.get("name") or "").lower()
            if "phone" in qname:
                answer = phone
            elif not reason_used:
                answer = reason
                reason_used = True
            else:
                raise RequiredQuestionUnrecognized(f"unrecognized required question: {q.get('name')!r}")
            questions_and_answers.append({"question": q["name"], "answer": answer, "position": q["position"]})

        local_start = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=tz)
        start_utc = local_start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        resp = await http.post(
            f"{_API_BASE}/invitees",
            headers=_headers(token),
            json={
                "event_type": event_type["uri"],
                "start_time": start_utc,
                "invitee": {"name": name, "email": email, "timezone": str(tz), "text_reminder_number": phone},
                "location": location,
                "questions_and_answers": questions_and_answers,
            },
        )
        _raise_with_context(resp)
        return resp.json()["resource"]
