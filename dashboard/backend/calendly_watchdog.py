"""Keeps the Calendly webhooks alive, and backfills what they missed.

Calendly can drop a webhook subscription on its side (repeated delivery
failures, a plan change, a token rotated) without telling us, and the OS
only knew "a webhook URI is saved", so the Calendly card kept saying
CONNECTED. That happened around 2026-11-05: every booking after it was
silently missing from Appointments and Analytics until someone noticed
(Dr. Benjamin Stokes, booked from a cold email on 2026-11-09).

run_watchdog() (main.py, every 30 min and shortly after startup):
  1. Dylan's own subscription: is it still listed on Calendly and active?
     If not, re-register it exactly like the Connect button does
     (routers/calendly_admin.py) and save the new signing key.
  2. Every client with a saved Calendly webhook: same check, re-registered
     through routers/client_marketing.py's _connect_calendly_webhook, then
     that client's upcoming bookings are resynced.
  3. Dylan's upcoming bookings are resynced every run regardless
     (routers/calendly_webhooks.resync_dylan_bookings), so even a single
     dropped delivery is picked up within 30 minutes.
  If a re-register fails, a To-Do goes on Dylan's list (once, not every
  run), since only he can fix a token or a Calendly plan.

The last result for Dylan's account is kept in
dialer_settings['dylan_calendly_webhook_health'] for /api/calendly/my-status.
"""
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import httpx

import calendly_integration
from db import get_pool

HEALTH_KEY = "dylan_calendly_webhook_health"
_API = "https://api.calendly.com"


async def subscription_active(token: str, webhook_uri: str | None) -> bool | None:
    """True if `webhook_uri` is still a subscription on the token's
    organization and Calendly reports it active. None if Calendly couldn't
    be asked (network/permission error): callers then leave things alone
    rather than re-register on a guess."""
    if not webhook_uri:
        return False
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            me = await http.get(f"{_API}/users/me", headers=headers)
            me.raise_for_status()
            org = me.json()["resource"]["current_organization"]
            url, params = f"{_API}/webhook_subscriptions", {"organization": org, "scope": "organization", "count": 100}
            while url:
                resp = await http.get(url, headers=headers, params=params)
                resp.raise_for_status()
                page = resp.json()
                for sub in page.get("collection", []):
                    if sub.get("uri") == webhook_uri:
                        return sub.get("state") == "active"
                url, params = page.get("pagination", {}).get("next_page"), None
    except Exception as e:
        print(f"[calendly-watchdog] couldn't list subscriptions: {e}", flush=True)
        return None
    return False


async def _todo_once(conn, text: str, description: str) -> None:
    if await conn.fetchval("SELECT 1 FROM todos WHERE NOT done AND text = $1", text):
        return
    await conn.execute(
        "INSERT INTO todos (text, description, due_date) VALUES ($1, $2, $3)",
        text, description, datetime.now(ZoneInfo("America/New_York")).date(),
    )


async def _save_health(conn, health: dict) -> None:
    await conn.execute(
        """
        INSERT INTO dialer_settings (key, value, updated_at) VALUES ($1, $2, now())
        ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = now()
        """,
        HEALTH_KEY, json.dumps(health),
    )


async def check_dylan() -> dict:
    from routers import calendly_admin
    from routers.calendly_webhooks import resync_dylan_bookings

    pool = await get_pool()
    async with pool.acquire() as conn:
        token = await conn.fetchval("SELECT value FROM dialer_settings WHERE key = 'dylan_calendly_api_token'")
        webhook_uri = await conn.fetchval("SELECT value FROM dialer_settings WHERE key = 'dylan_calendly_webhook_uri'")
    if not token:
        return {"skipped": "no token"}

    health = {"checked_at": datetime.now(timezone.utc).isoformat()}
    active = await subscription_active(token, webhook_uri)
    health["live"] = active
    if active is False:
        try:
            await calendly_admin.connect_my_calendly_webhook()
            health.update(live=True, reconnected_at=health["checked_at"])
            print("[calendly-watchdog] Dylan's webhook was missing on Calendly, re-registered it", flush=True)
        except Exception as e:
            err = getattr(e, "detail", None) or str(e)
            health["error"] = err
            print(f"[calendly-watchdog] re-registering Dylan's webhook failed: {err}", flush=True)
            async with pool.acquire() as conn:
                await _todo_once(
                    conn, "Calendly bookings aren't syncing: reconnect Calendly",
                    "Calendly dropped your booking webhook and the OS couldn't re-create it automatically "
                    f"({err}). New bookings still get imported every 30 minutes by the backup sync, but "
                    "cancellations and instant reminders depend on the webhook. Fix: SOPs tab -> Your Calendly "
                    "Connection -> Reconnect (if it errors, check the Calendly plan still allows webhooks and "
                    "the API token is still valid).",
                )
    try:
        health["resync"] = await resync_dylan_bookings()
    except Exception as e:
        health["resync_error"] = str(e)
        print(f"[calendly-watchdog] Dylan resync failed: {e}", flush=True)
    async with pool.acquire() as conn:
        await _save_health(conn, health)
    return health


async def check_clients() -> list[dict]:
    from routers.calendly_webhooks import resync_client_bookings
    from routers.client_marketing import _connect_calendly_webhook

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT m.client_id, m.calendly_api_token, m.calendly_webhook_uri, m.calendly_event_type_url, c.name
            FROM client_marketing_config m JOIN clients c ON c.id = m.client_id
            WHERE COALESCE(m.calendly_api_token, '') <> '' AND COALESCE(m.calendly_webhook_uri, '') <> ''
            """
        )
    results = []
    for r in rows:
        active = await subscription_active(r["calendly_api_token"], r["calendly_webhook_uri"])
        if active is not False:
            continue
        error = await _connect_calendly_webhook(r["client_id"])
        result = {"client_id": r["client_id"], "client": r["name"], "reconnected": not error, "error": error}
        if error:
            async with pool.acquire() as conn:
                await _todo_once(
                    conn, f"{r['name']}: Calendly bookings aren't syncing",
                    f"Calendly dropped {r['name']}'s booking webhook and the OS couldn't re-create it ({error}). "
                    "Their new bookings won't reach the portal, reminders or the booking alert until it's fixed. "
                    "Fix: Clients -> Marketing Setup -> Calendly -> Connect webhook (check the token is still valid).",
                )
        elif r["calendly_event_type_url"]:
            try:
                result["resync"] = await resync_client_bookings(r["client_id"])
            except Exception as e:
                result["resync_error"] = getattr(e, "detail", None) or str(e)
        print(f"[calendly-watchdog] client {r['client_id']}: {result}", flush=True)
        results.append(result)
    return results


async def run_watchdog() -> None:
    """APScheduler entry point. Never raises."""
    try:
        dylan = await check_dylan()
        resync = dylan.get("resync") or {}
        if resync.get("imported") or resync.get("linked_manual_rows") or resync.get("canceled"):
            print(f"[calendly-watchdog] Dylan resync: {resync}", flush=True)
    except Exception as e:
        print(f"[calendly-watchdog] Dylan check failed: {e}", flush=True)
    try:
        await check_clients()
    except Exception as e:
        print(f"[calendly-watchdog] client check failed: {e}", flush=True)
