"""
Read-only Calendly integration for response_ai.py's check_availability
tool — looks up a client's REAL open time slots via Calendly's API so the
agent proposes times that are actually open instead of guessing blind.

Auth is a Calendly Personal Access Token the client generates from their
own Calendly account (Integrations & Apps -> API & Webhooks -> Generate New
Token) — or Dylan's, once added as an admin on that client's account — and
pastes into their Marketing Setup (client_marketing_config.calendly_api_token).
Same "one credential per client, pasted in" pattern as the Gmail refresh
token.

Deliberately read-only: Calendly's public API has no endpoint to create a
CONFIRMED booking on someone else's behalf — an invitee always has to
complete the scheduling flow on Calendly's own page. Booking itself still
happens exactly as it always has in this system (routers/appointments.py's
create_appointment_row, called from response_ai.py's propose_appointment
tool) — this module just makes that a well-informed choice of time instead
of a blind guess, per confirmed scope (2026-09-14): check real availability,
still book internally.
"""
import httpx

_API_BASE = "https://api.calendly.com"


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


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
    resp.raise_for_status()


async def _get_first_event_type(http: httpx.AsyncClient, token: str) -> dict | None:
    """A client is expected to have one primary booking event type (their
    consultation) — takes the first active one rather than requiring the
    admin to pick a specific event type URI, to keep the connection step to
    "paste your token" and nothing more."""
    me = await http.get(f"{_API_BASE}/users/me", headers=_headers(token))
    _raise_with_context(me)
    user_uri = me.json()["resource"]["uri"]

    resp = await http.get(
        f"{_API_BASE}/event_types",
        headers=_headers(token),
        params={"user": user_uri, "active": "true", "count": 1},
    )
    _raise_with_context(resp)
    items = resp.json().get("collection", [])
    return items[0] if items else None


async def get_available_times(token: str, start_iso: str, end_iso: str) -> list[dict]:
    """start_iso/end_iso: RFC3339 timestamps bounding the query window —
    Calendly caps a single request to a 7-day span, well within a
    single-day lookup. Returns Calendly's raw slot objects (each has
    start_time in UTC) — empty list if nothing's open or nothing's
    connected/configured."""
    async with httpx.AsyncClient(timeout=10) as http:
        event_type = await _get_first_event_type(http, token)
        if not event_type:
            return []

        resp = await http.get(
            f"{_API_BASE}/event_type_available_times",
            headers=_headers(token),
            params={"event_type": event_type["uri"], "start_time": start_iso, "end_time": end_iso},
        )
        _raise_with_context(resp)
        return resp.json().get("collection", [])
