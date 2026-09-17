"""Dylan's OWN Calendly connection (DigiGrowth's own pipeline) — the
client-scoped equivalent of this lives on client_marketing_config
(calendly_api_token) with its own connect endpoint in client_marketing.py;
this is that same idea for the one account that isn't a "client". Credential
storage reuses dialer_settings (the app's existing generic key/value store)
rather than a dedicated table for three values.

Once connected, real bookings on Dylan's own Calendly link automatically
create the appointment_reminders row that drives reminder_engine.py's
24h/6h/1h no-show reminders — see routers/calendly_webhooks.py for the
receiving side.
"""
from fastapi import APIRouter, HTTPException

import calendly_integration
import dialer_engine
from db import get_pool

router = APIRouter()

_TOKEN_KEY = "dylan_calendly_api_token"
_WEBHOOK_URI_KEY = "dylan_calendly_webhook_uri"
_SIGNING_KEY_KEY = "dylan_calendly_webhook_signing_key"


async def _get_setting(conn, key: str) -> str | None:
    row = await conn.fetchrow("SELECT value FROM dialer_settings WHERE key = $1", key)
    return row["value"] if row else None


async def _set_setting(conn, key: str, value: str) -> None:
    await conn.execute(
        """
        INSERT INTO dialer_settings (key, value, updated_at) VALUES ($1, $2, now())
        ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = now()
        """,
        key, value,
    )


@router.get("/calendly/my-status")
async def get_my_calendly_status():
    pool = await get_pool()
    async with pool.acquire() as conn:
        token = await _get_setting(conn, _TOKEN_KEY)
        webhook_uri = await _get_setting(conn, _WEBHOOK_URI_KEY)
    return {"token_saved": bool(token), "webhook_connected": bool(webhook_uri)}


@router.post("/calendly/my-token")
async def save_my_calendly_token(body: dict):
    token = (body.get("token") or "").strip()
    if not token:
        raise HTTPException(400, "token is required")
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _set_setting(conn, _TOKEN_KEY, token)
    return {"ok": True}


@router.post("/calendly/connect")
async def connect_my_calendly_webhook():
    """Registers the webhook against Dylan's own Calendly organization —
    same idea as client_marketing.py's connect-calendly-webhook, just for
    the one account that isn't a client."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        token = await _get_setting(conn, _TOKEN_KEY)
    if not token:
        raise HTTPException(400, "Save a Calendly API token first.")

    base = dialer_engine.base_url()
    if not base:
        raise HTTPException(400, "RAILWAY_PUBLIC_DOMAIN not set — can't build a callback URL.")
    callback_url = f"{base}/webhooks/calendly/dylan"

    try:
        org_uri = await calendly_integration.get_organization_uri(token)
        result = await calendly_integration.register_webhook(token, callback_url, org_uri)
    except Exception as e:
        raise HTTPException(400, str(e))

    async with pool.acquire() as conn:
        await _set_setting(conn, _WEBHOOK_URI_KEY, result["uri"])
        await _set_setting(conn, _SIGNING_KEY_KEY, result["signing_key"])
    return {"ok": True}
