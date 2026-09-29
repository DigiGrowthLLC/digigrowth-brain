"""
Provisions a client's Facebook Lead Ads -> portal relay in Make.com, so a
new client's Meta leads start flowing without anyone building a scenario by
hand. Receiving side is routers/meta_lead_webhooks.py's POST
/webhooks/make-leadgen (see its docstring for why Make sits in the middle:
Make's own Meta app already has the leads_retrieval App Review ours lacks).

Per client Page, connect_page() makes sure there is:
  1. a Make "Facebook Lead Ads - New Lead" webhook on that Page, created with
     the shared Facebook connection (MAKE_FB_CONNECTION_ID) — creating it is
     what subscribes the Page to Make's app,
  2. a scenario on that webhook: New Lead -> HTTP POST (form-encoded) to
     /webhooks/make-leadgen with the X-Webhook-Secret header,
  3. that scenario switched on.
It's idempotent — an existing webhook for the Page (and the scenario it's
attached to) is reused and its blueprint refreshed, never duplicated, so
re-clicking Connect or adopting a hand-built scenario is safe.

What it can't do (see the Response AI guide in ClientsPanel.jsx): get
Dylan's Facebook profile access to the client's Page, tick that Page on the
Make connection's Facebook login, or unblock Make in the client's Leads
Access Manager. Webhook creation fails until the first two are done.

Env: MAKE_API_TOKEN, MAKE_ZONE (e.g. us2), MAKE_TEAM_ID,
MAKE_FB_CONNECTION_ID (optional — falls back to the newest Facebook Lead
Ads connection on the team), MAKE_LEADGEN_SECRET.
"""
import json
import os

import httpx

import dialer_engine

HOOK_TYPE = "facebook-lead-ads-new-event"
_FB_ACCOUNT = "facebook"

# Form question keys forwarded to the relay — Meta's standard Lead Ads
# fields. A custom question under another key won't be forwarded; the relay
# skips a lead with no phone and logs it.
_LEAD_FIELDS = ("full_name", "phone_number", "email")


def _env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is not set — add it in Doppler (project digigrowth, config prd).")
    return value


def _api_base() -> str:
    return f"https://{_env('MAKE_ZONE')}.make.com/api/v2"


def _headers() -> dict:
    return {"Authorization": f"Token {_env('MAKE_API_TOKEN')}"}


async def _call(http: httpx.AsyncClient, method: str, path: str, **kwargs) -> dict:
    resp = await http.request(method, f"{_api_base()}{path}", headers=_headers(), timeout=30, **kwargs)
    if resp.status_code >= 400:
        try:
            err = resp.json()
            detail = "; ".join(s.get("message", "") for s in err.get("suberrors") or []) or err.get("detail") or err.get("message")
        except ValueError:
            detail = resp.text.strip()[:300]
        raise RuntimeError(f"Make API {method} {path.split('?')[0]} failed ({resp.status_code}): {detail}")
    return resp.json() if resp.content else {}


async def _fb_connection_id(http: httpx.AsyncClient, team_id: str) -> int:
    configured = os.environ.get("MAKE_FB_CONNECTION_ID")
    if configured:
        return int(configured)
    conns = (await _call(http, "GET", f"/connections?teamId={team_id}")).get("connections", [])
    fb = [c for c in conns if c.get("accountName") == _FB_ACCOUNT]
    if not fb:
        raise RuntimeError("No Facebook connection in Make yet — create one (see the guide's Make step).")
    return max(c["id"] for c in fb)


def _blueprint(hook_id: int, client_name: str) -> dict:
    base = dialer_engine.base_url()
    if not base:
        raise RuntimeError("RAILWAY_PUBLIC_DOMAIN not set — can't build the relay URL.")
    fields = [{"key": "page_id", "value": "{{1.pageId}}"}, {"key": "leadgen_id", "value": "{{1.leadgenId}}"}]
    fields += [{"key": f, "value": "{{1.data.%s}}" % f} for f in _LEAD_FIELDS]
    return {
        "name": _scenario_name(client_name),
        "flow": [
            {
                "id": 1, "module": "facebook-lead-ads:NewLeadMultiple", "version": 2,
                "parameters": {"v": "2", "fields": [], "__IMTHOOK__": hook_id},
                "mapper": {}, "metadata": {"designer": {"x": 0, "y": 0}},
            },
            {
                "id": 2, "module": "http:ActionSendData", "version": 3,
                "parameters": {"handleErrors": False, "useNewZLibDeCompress": True},
                "mapper": {
                    "url": f"{base}/webhooks/make-leadgen", "serializeUrl": False, "method": "post",
                    "headers": [{"name": "X-Webhook-Secret", "value": _env("MAKE_LEADGEN_SECRET")}],
                    "qs": [], "bodyType": "x_www_form_urlencoded", "fields": fields,
                    "parseResponse": True, "allowRedirects": True, "stopOnHttpError": True,
                    "shareCookies": False, "rejectUnauthorized": True, "followRedirect": True,
                    "useQuerystring": False, "gzip": True, "useMtls": False, "timeout": "",
                },
                "metadata": {"designer": {"x": 300, "y": 0}},
            },
        ],
        "metadata": {
            "instant": True, "version": 1,
            "scenario": {
                "roundtrips": 1, "maxErrors": 3, "autoCommit": True, "autoCommitTriggerLast": True,
                "sequential": False, "confidential": False, "dataloss": False, "dlq": False,
                "freshVariables": False,
            },
            "designer": {"orphans": []},
        },
    }


def _scenario_name(client_name: str) -> str:
    return f"{client_name} Meta Leads -> Client Portal"


async def connect_page(page_id: str, client_name: str) -> dict:
    """Returns {"hook_id", "scenario_id", "active"}. Raises RuntimeError with
    a human-readable reason (surfaced in the Marketing Setup guide)."""
    team_id = _env("MAKE_TEAM_ID")
    async with httpx.AsyncClient() as http:
        hooks = (await _call(http, "GET", f"/hooks?teamId={team_id}")).get("hooks", [])
        hook = next(
            (h for h in hooks if h.get("typeName") == HOOK_TYPE and str((h.get("data") or {}).get("pageId")) == page_id),
            None,
        )
        if not hook:
            conn_id = await _fb_connection_id(http, team_id)
            try:
                hook = (await _call(http, "POST", "/hooks", json={
                    "name": f"{client_name} New Lead webhook", "teamId": int(team_id),
                    "typeName": HOOK_TYPE, "__IMTCONN__": conn_id, "pageId": page_id,
                })).get("hook", {})
            except RuntimeError as e:
                raise RuntimeError(
                    f"{e} — usually means Make's Facebook login can't see Page {page_id} yet: finish the "
                    "Page-access and Make-reauthorize steps above, then click Connect again."
                ) from e

        blueprint = json.dumps(_blueprint(hook["id"], client_name))
        scenario_id = hook.get("scenarioId")
        if scenario_id:
            await _call(http, "PATCH", f"/scenarios/{scenario_id}?confirmed=true", json={
                "name": _scenario_name(client_name), "blueprint": blueprint,
            })
        else:
            created = await _call(http, "POST", "/scenarios?confirmed=true", json={
                "teamId": int(team_id), "blueprint": blueprint,
                "scheduling": json.dumps({"type": "immediately"}),
            })
            scenario_id = created["scenario"]["id"]

        scenario = (await _call(http, "GET", f"/scenarios/{scenario_id}")).get("scenario", {})
        if not scenario.get("isActive"):
            try:
                await _call(http, "POST", f"/scenarios/{scenario_id}/start")
            except RuntimeError as e:
                raise RuntimeError(
                    f"Scenario built but couldn't be switched on: {e} — if Make says you've hit your plan's "
                    "active-scenario limit, upgrade the Make plan or turn off an unused scenario."
                ) from e

    return {"hook_id": hook["id"], "scenario_id": scenario_id, "active": True}
