"""
Meta (Facebook) Ads spend sync — populates ad_campaign_stats so each real
client's own portal Analytics tab (routers/client_portal.py's portal_stats(),
"ads" section) shows real spend/impressions/clicks/leads instead of the
permanent "coming_soon" empty state. The portal side needs zero changes —
it already reads ad_campaign_stats and renders CTR/CPC/cost-per-lead/CAC
the moment real rows exist.

Auth: ONE shared System User access token (Business Manager structure is one
DigiGrowth-owned Business Manager with every client's ad account added as an
assigned asset — mirrors how a client's Twilio subaccount already sits under
DigiGrowth's own master Twilio account, see client_sms.py) — read from
META_SYSTEM_USER_TOKEN in the shared `digigrowth` Doppler vault, never a
per-client token/OAuth flow. Requires the `ads_management` or `ads_read`
permission, which requires Meta App Review + Business Verification — until
that's approved, every client is simply skipped (see sync_meta_ad_stats), not
an error.

Requires meta_ad_account_id set on a client's client_marketing_config
(entered via the Marketing Setup guide's "Create Paid Ad Creatives" step,
ClientsPanel.jsx) before that client is polled at all.
"""
import json
import os
from datetime import date, timedelta

import httpx

from db import get_pool

_GRAPH_BASE = "https://graph.facebook.com/v21.0"
_WINDOW_DAYS = 3  # trailing window re-synced every run so a transient
                  # failure or late-attributed conversion self-heals on the
                  # next run instead of needing a manual backfill — the
                  # (client_id, platform, stat_date) unique constraint makes
                  # re-upserting the same days idempotent and cheap.

# Meta's `actions` array entries use one of a few action_type strings for a
# Lead Ads result depending on API version/campaign objective — checking
# several known aliases rather than trusting exactly one. Flagged as an
# assumption to verify against Meta's current docs; add more here if a
# real client's leads count comes back as 0 despite having real Lead Ads
# activity.
_LEAD_ACTION_TYPES = {"lead", "onsite_conversion.lead_grouped", "leadgen.other"}


def _extract_lead_count(actions: list[dict] | None) -> int:
    if not actions:
        return 0
    return sum(
        int(float(a.get("value", 0)))
        for a in actions
        if a.get("action_type") in _LEAD_ACTION_TYPES
    )


async def _fetch_insights(http: httpx.AsyncClient, ad_account_id: str, token: str, since: date, until: date) -> list[dict]:
    resp = await http.get(
        f"{_GRAPH_BASE}/act_{ad_account_id}/insights",
        params={
            "access_token": token,
            "level": "account",
            "fields": "spend,impressions,clicks,actions,date_start,date_stop",
            "time_range": f'{{"since":"{since.isoformat()}","until":"{until.isoformat()}"}}',
            "time_increment": 1,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Meta Graph API returned {resp.status_code}: {resp.text.strip()[:300]}")
    return resp.json().get("data", [])


async def _upsert_days(conn, client_id: int, days: list[dict]) -> int:
    upserted = 0
    for day in days:
        try:
            stat_date = day.get("date_start")
            if not stat_date:
                continue
            await conn.execute(
                """
                INSERT INTO ad_campaign_stats
                    (client_id, platform, stat_date, spend, impressions, clicks, leads, raw, synced_at)
                VALUES ($1, 'meta', $2, $3, $4, $5, $6, $7, now())
                ON CONFLICT (client_id, platform, stat_date) DO UPDATE SET
                    spend = EXCLUDED.spend, impressions = EXCLUDED.impressions,
                    clicks = EXCLUDED.clicks, leads = EXCLUDED.leads,
                    raw = EXCLUDED.raw, synced_at = now()
                """,
                client_id, stat_date,
                float(day.get("spend", 0) or 0),
                int(float(day.get("impressions", 0) or 0)),
                int(float(day.get("clicks", 0) or 0)),
                _extract_lead_count(day.get("actions")),
                json.dumps(day),
            )
            upserted += 1
        except Exception as e:
            print(f"[meta_ads] failed to upsert day {day.get('date_start')} for client={client_id}: {e}")
    return upserted


async def sync_meta_ad_stats() -> None:
    """Scheduler job (main.py, once daily) — polls every client with a
    configured meta_ad_account_id and upserts the last _WINDOW_DAYS days of
    spend/impressions/clicks/leads into ad_campaign_stats. One client's
    missing token/revoked access/bad account id must never block every
    other client's sync — each client's block is fully isolated.

    Errors here only ever reach Railway's stdout logs — see
    sync_one_client_now() below for the manual-trigger path a rep can
    actually see the result of, from Business Resources → the client's
    Marketing Setup guide."""
    token = os.environ.get("META_SYSTEM_USER_TOKEN")
    if not token:
        print("[meta_ads] META_SYSTEM_USER_TOKEN not set — skipping sync entirely (Meta App Review likely not complete yet)")
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        clients = await conn.fetch(
            "SELECT client_id, meta_ad_account_id FROM client_marketing_config WHERE meta_ad_account_id IS NOT NULL"
        )
    if not clients:
        return

    until = date.today()
    since = until - timedelta(days=_WINDOW_DAYS)

    async with httpx.AsyncClient() as http:
        for row in clients:
            client_id = row["client_id"]
            ad_account_id = (row["meta_ad_account_id"] or "").strip().removeprefix("act_")
            if not ad_account_id:
                continue
            try:
                days = await _fetch_insights(http, ad_account_id, token, since, until)
            except Exception as e:
                print(f"[meta_ads] sync failed for client={client_id} (ad account {ad_account_id}): {e}")
                continue

            pool = await get_pool()
            async with pool.acquire() as conn:
                await _upsert_days(conn, client_id, days)


async def sync_one_client_now(client_id: int) -> int:
    """Manual trigger for testing/verification (routers/client_marketing.py's
    POST .../sync-meta-ads) — same code path as the scheduled daily sync,
    just scoped to one client and raising RuntimeError with a specific,
    user-facing reason instead of silently skipping/printing to logs.
    Returns the number of days upserted."""
    token = os.environ.get("META_SYSTEM_USER_TOKEN")
    if not token:
        raise RuntimeError(
            "META_SYSTEM_USER_TOKEN isn't set — this requires Meta App Review + "
            "Business Verification to be complete first (see meta_ads.py's module docstring)."
        )

    pool = await get_pool()
    async with pool.acquire() as conn:
        config = await conn.fetchrow(
            "SELECT meta_ad_account_id FROM client_marketing_config WHERE client_id = $1", client_id,
        )
    ad_account_id = ((config["meta_ad_account_id"] if config else None) or "").strip().removeprefix("act_")
    if not ad_account_id:
        raise RuntimeError("No Meta Ad Account ID saved for this client yet.")

    until = date.today()
    since = until - timedelta(days=_WINDOW_DAYS)
    async with httpx.AsyncClient() as http:
        days = await _fetch_insights(http, ad_account_id, token, since, until)

    pool = await get_pool()
    async with pool.acquire() as conn:
        return await _upsert_days(conn, client_id, days)
