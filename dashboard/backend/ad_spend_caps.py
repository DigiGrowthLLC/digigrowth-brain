"""Meta ad spend caps: pause a client's campaigns once they've spent their
ad budget.

Dylan signs a client for a marketing budget; $100 of it covers software and
the rest is the ad spend cap (e.g. $600 signed -> $500 cap). He does NOT
want Meta's own campaign spending limit (it ends the campaign); he wants the
campaign simply PAUSED, so if the client decides to keep going he raises the
cap here and switches the campaign back on in Ads Manager.

run_watchdog() (main.py, every 30 min):
  1. For every enabled row in ad_spend_caps, pull spend from the Meta
     Insights API with the shared System User token (META_SYSTEM_USER_TOKEN,
     needs ads_management, see meta_ads.py): the chosen campaigns, or the
     whole ad account if none were chosen, since start_date (all-time if
     none), counted in the ad account's own timezone.
  2. At 80% of the cap: one To-Do for Dylan.
  3. At the cap: every in-scope campaign whose status is ACTIVE is set to
     PAUSED, plus a To-Do. This repeats every run, so a campaign switched
     back on without raising the cap gets paused again within 30 minutes.
  4. Also at the cap: one text to Dylan's phone from the OS number
     (_text_dylan_once): "ads have been turned off" when it could pause them,
     or "has reached the ad budget" (go pause it yourself) when the system
     user can't. Once per cap value (texted_cap).
  Raising the cap (PUT /clients/{id}/ad-spend-cap) re-arms the warning, the
  text and clears the paused state.

Spend lags Meta's real spend a little and the check runs every 30 minutes,
so a campaign can overshoot by up to ~30 minutes of spend (well under $2 at
$25-30/day).
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx

from db import get_pool

_GRAPH = "https://graph.facebook.com/v21.0"
WARN_AT = 0.8
_ERROR_TODO_AFTER = timedelta(hours=3)


class CapError(Exception):
    """Shown to Dylan as-is (no token, no ad account, Meta's own error)."""


class CantPauseError(CapError):
    """Spend was read fine; only pausing isn't allowed. Has its own To-Do,
    so it doesn't also raise the "can't be checked" one."""


def _token() -> str:
    token = os.environ.get("META_SYSTEM_USER_TOKEN")
    if not token:
        raise CapError("META_SYSTEM_USER_TOKEN isn't set on the server, so spend can't be checked.")
    return token


def _clean_account(raw: str | None) -> str:
    return (raw or "").strip().removeprefix("act_")


async def _get(http: httpx.AsyncClient, url: str, params: dict) -> dict:
    resp = await http.get(url, params=params, timeout=30)
    if resp.status_code != 200:
        raise CapError(f"Meta returned {resp.status_code}: {resp.text.strip()[:300]}")
    return resp.json()


async def _account_info(http, token: str, account: str) -> dict:
    return await _get(http, f"{_GRAPH}/act_{account}", {"access_token": token, "fields": "name,currency,timezone_name,user_tasks"})


async def list_campaigns(account: str, http: httpx.AsyncClient | None = None) -> list[dict]:
    """Every campaign in the ad account: id, name, status (what Dylan set),
    effective_status (what Meta is actually doing)."""
    token = _token()
    own = http is None
    http = http or httpx.AsyncClient()
    try:
        out, url = [], f"{_GRAPH}/act_{account}/campaigns"
        params = {"access_token": token, "fields": "id,name,status,effective_status,start_time", "limit": 200}
        while url:
            page = await _get(http, url, params)
            out.extend(page.get("data", []))
            url, params = page.get("paging", {}).get("next"), {}
        return out
    finally:
        if own:
            await http.aclose()


async def _spend(http, token: str, account: str, campaign_ids: list[str], start: date | None, tz: str) -> float:
    params = {"access_token": token, "fields": "spend", "limit": 500}
    if start:
        today = datetime.now(ZoneInfo(tz or "America/New_York")).date()
        params["time_range"] = json.dumps({"since": start.isoformat(), "until": max(start, today).isoformat()})
    else:
        params["date_preset"] = "maximum"
    if campaign_ids:
        params["level"] = "campaign"
        params["filtering"] = json.dumps([{"field": "campaign.id", "operator": "IN", "value": campaign_ids}])
    else:
        params["level"] = "account"
    total, url = 0.0, f"{_GRAPH}/act_{account}/insights"
    while url:
        page = await _get(http, url, params)
        total += sum(float(r.get("spend") or 0) for r in page.get("data", []))
        url, params = page.get("paging", {}).get("next"), {}
    return round(total, 2)


async def _pause(http, token: str, campaign_id: str) -> None:
    resp = await http.post(f"{_GRAPH}/{campaign_id}", data={"access_token": token, "status": "PAUSED"}, timeout=30)
    if resp.status_code != 200:
        raise CapError(f"Meta refused to pause campaign {campaign_id}: {resp.text.strip()[:300]}")


async def _text_dylan_once(conn, row, cap: float, body: str) -> None:
    """Texts Dylan from the OS (DigiGrowth's Twilio number) once per cap
    value. Never raises: the cap check itself already did its job."""
    import asyncio
    from routers import sms as sms_router
    from sms_setter_ai import ALERT_PHONE_KEY, _DEFAULT_ALERT_PHONE, _setting
    claimed = await conn.fetchval(
        "UPDATE ad_spend_caps SET texted_cap = $2 WHERE client_id = $1 "
        "AND (texted_cap IS NULL OR texted_cap <> $2) RETURNING client_id",
        row["client_id"], cap)
    if not claimed:
        return
    try:
        to = await _setting(conn, ALERT_PHONE_KEY) or os.environ.get("DYLAN_ALERT_PHONE") or _DEFAULT_ALERT_PHONE
        await asyncio.to_thread(sms_router._send_twilio, to, body)
    except Exception as e:
        print(f"[ad-spend-caps] text to Dylan failed for client {row['client_id']}: {e}", flush=True)
        await conn.execute("UPDATE ad_spend_caps SET texted_cap = NULL WHERE client_id = $1", row["client_id"])


def _cant_check_text(name: str) -> str:
    return f"{name}: ad spend cap can't be checked"


def _cant_pause_text(name: str) -> str:
    return f"{name}: ad spend cap can't pause the ads"


async def _todo_once(conn, text: str, description: str, *, while_unresolved: bool = False) -> None:
    """One To-Do per text. With while_unresolved, a To-Do Dylan already
    checked off also counts, so an ongoing problem doesn't re-add itself
    every 30 minutes (it did, Dylan 2026-11-19). _rearm() clears those
    checked-off copies once the problem is fixed, so a later recurrence
    alerts again."""
    sql = ("SELECT 1 FROM todos WHERE text = $1" if while_unresolved
           else "SELECT 1 FROM todos WHERE NOT done AND text = $1")
    if await conn.fetchval(sql, text):
        return
    await conn.execute(
        "INSERT INTO todos (text, description, due_date) VALUES ($1, $2, $3)",
        text, description, datetime.now(ZoneInfo("America/New_York")).date(),
    )


async def _rearm(conn, *texts: str) -> None:
    """The problem behind these To-Dos is fixed: forget the checked-off
    copies so the next time it happens Dylan hears about it again."""
    await conn.execute("DELETE FROM todos WHERE done AND text = ANY($1::text[])", list(texts))


def _money(v: float, currency: str | None) -> str:
    return f"${v:,.2f}" if (currency or "USD") == "USD" else f"{v:,.2f} {currency}"


async def check_client(client_id: int) -> dict:
    """Check one client's cap now: refresh spend, warn, pause if over.
    Raises CapError on a problem Dylan has to fix; the error is also saved
    on the row so the OS card shows it."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT c.*, cl.name AS client_name, cmc.meta_ad_account_id
               FROM ad_spend_caps c JOIN clients cl ON cl.id = c.client_id
               LEFT JOIN client_marketing_config cmc ON cmc.client_id = c.client_id
               WHERE c.client_id = $1""",
            client_id,
        )
    if not row:
        raise CapError("No ad spend cap set for this client.")
    try:
        return await _check_row(row)
    except Exception as e:
        msg = str(e) if isinstance(e, CapError) else f"{type(e).__name__}: {e}"
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE ad_spend_caps SET last_error = $2 WHERE client_id = $1", client_id, msg[:500],
            )
            last_ok = row["last_checked_at"]
            if row["enabled"] and not isinstance(e, CantPauseError) and (last_ok is None or datetime.now(timezone.utc) - last_ok > _ERROR_TODO_AFTER):
                await _todo_once(
                    conn,
                    _cant_check_text(row["client_name"]),
                    f"The automatic ad budget check for {row['client_name']} has been failing, so their "
                    f"campaigns will NOT be paused at the cap until it's fixed. Error: {msg[:300]}",
                    while_unresolved=True,
                )
        raise CapError(msg) from e


async def _check_row(row) -> dict:
    token = _token()
    account = _clean_account(row["meta_ad_account_id"])
    if not account:
        raise CapError("No Meta Ad Account ID saved for this client (Marketing Setup).")
    cap = float(row["cap"])
    campaign_ids = list(row["campaign_ids"] or [])
    paused_now: list[dict] = []
    async with httpx.AsyncClient() as http:
        info = await _account_info(http, token, account)
        currency = info.get("currency")
        # Spend can be readable through a partner share while the system
        # user has no role on the account, and then pausing fails (Advantage,
        # 2026-11-16). Pausing needs ADVERTISE or MANAGE.
        can_pause = bool({"ADVERTISE", "MANAGE"} & set(info.get("user_tasks") or []))
        spend = await _spend(http, token, account, campaign_ids, row["start_date"], info.get("timezone_name"))
        over = row["enabled"] and spend >= cap
        if over and can_pause:
            for c in await list_campaigns(account, http):
                if campaign_ids and c["id"] not in campaign_ids:
                    continue
                if c.get("status") == "ACTIVE":
                    await _pause(http, token, c["id"])
                    paused_now.append({"id": c["id"], "name": c.get("name"), "at": datetime.now(timezone.utc).isoformat()})

    pool = await get_pool()
    async with pool.acquire() as conn:
        prior = json.loads(row["paused_campaigns"]) if isinstance(row["paused_campaigns"], str) else (row["paused_campaigns"] or [])
        newly_reached = bool(over) and not await conn.fetchval(
            "SELECT cap_reached_at FROM ad_spend_caps WHERE client_id = $1", row["client_id"])
        await conn.execute(
            """UPDATE ad_spend_caps SET last_spend = $2, currency = $3, last_checked_at = now(), last_error = NULL,
                   paused_at = CASE WHEN $4 THEN COALESCE(paused_at, now()) ELSE paused_at END,
                   paused_campaigns = $5::jsonb,
                   cap_reached_at = CASE WHEN $6 THEN COALESCE(cap_reached_at, now()) ELSE NULL END
               WHERE client_id = $1""",
            row["client_id"], spend, currency, bool(over and can_pause), json.dumps((prior + paused_now)[-50:]), bool(over),
        )
        name = row["client_name"]
        d = row["start_date"]
        since = f" since {d.strftime('%b')} {d.day}" if d else ""
        if row["enabled"] and spend >= cap * WARN_AT and not row["warned_at"] and not over:
            await _todo_once(
                conn,
                f"{name}: ads at {int(spend / cap * 100)}% of ad budget",
                f"{name} has spent {_money(spend, currency)} of their {_money(cap, currency)} ad budget{since}. "
                f"Campaigns pause automatically at {_money(cap, currency)}. If they're continuing, raise the cap "
                f"on their Marketing Setup tab (Meta ad spend cap) before then.",
            )
            await conn.execute("UPDATE ad_spend_caps SET warned_at = now() WHERE client_id = $1", row["client_id"])
        if over and can_pause:
            await _text_dylan_once(
                conn, row, cap,
                f"Hey, {name}'s ads have been turned off. They reached their {_money(cap, currency)} ad budget "
                f"({_money(spend, currency)} spent{since}).")
        elif over:
            await _text_dylan_once(
                conn, row, cap,
                f"Hey, {name} has reached their {_money(cap, currency)} ad budget ({_money(spend, currency)} "
                f"spent{since}). The OS couldn't turn the ads off, so pause them in Ads Manager.")
        if paused_now:
            names = ", ".join(c["name"] or c["id"] for c in paused_now)
            await _todo_once(
                conn,
                f"{name}: ads paused at {_money(cap, currency)} budget",
                f"{name} reached their ad budget ({_money(spend, currency)} spent{since}, cap {_money(cap, currency)}). "
                f"Paused: {names}. If they want to keep going: raise the cap on their Marketing Setup tab "
                f"(Meta ad spend cap) first, then switch the campaign back on in Ads Manager. Without a higher "
                f"cap it gets paused again within 30 minutes.",
            )
    # First dollar -> launch steps + check-in campaign; cap reached -> last
    # call to everyone who never came in (client_reactivation.on_ad_spend).
    if row["enabled"]:
        try:
            import client_reactivation
            await client_reactivation.on_ad_spend(row["client_id"], spend, cap)
        except Exception as e:
            print(f"[ad-spend-caps] client={row['client_id']} reactivation trigger failed: {e}", flush=True)
    # Ad budget spent = the campaign is over: the CSM drafts the final report
    # right away for Dylan's approval (client_success.on_budget_spent).
    if newly_reached:
        import client_success
        await client_success.on_budget_spent(row["client_id"], spend, cap)
    async with pool.acquire() as conn:
        if can_pause:
            await _rearm(conn, _cant_check_text(row["client_name"]), _cant_pause_text(row["client_name"]))
        else:
            # Spend was read, so the check itself works; only pausing doesn't.
            await _rearm(conn, _cant_check_text(row["client_name"]))
    if row["enabled"] and not can_pause:
        async with pool.acquire() as conn:
            await _todo_once(
                conn,
                _cant_pause_text(row["client_name"]),
                f"DigiGrowth's system user can read {row['client_name']}'s ad spend but has no role on their ad account, "
                f"so the campaigns will NOT pause at {_money(cap, currency)}. Fix: DigiGrowth Business Settings → Users → "
                f"System users → DigiGrowth OS Integration → Assign assets → Ad accounts → act_{account} → Manage "
                f"campaigns. Spent so far: {_money(spend, currency)}.",
                while_unresolved=True,
            )
        raise CantPauseError("Can read spend but can't pause: assign the ad account to DigiGrowth's system user with "
                       "Manage campaigns (Business Settings → System users → Assign assets).")
    return {"spend": spend, "cap": cap, "currency": currency, "paused": paused_now}


async def run_watchdog() -> None:
    if not os.environ.get("META_SYSTEM_USER_TOKEN"):
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        ids = [r["client_id"] for r in await conn.fetch("SELECT client_id FROM ad_spend_caps WHERE enabled")]
    for client_id in ids:
        try:
            result = await check_client(client_id)
            if result["paused"]:
                print(f"[ad-spend-caps] client={client_id} paused {len(result['paused'])} campaign(s) at "
                      f"{result['spend']} of {result['cap']}", flush=True)
        except Exception as e:
            print(f"[ad-spend-caps] client={client_id} check failed: {e}", flush=True)
