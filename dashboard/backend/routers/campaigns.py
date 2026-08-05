"""
Campaign tracking — named, time-windowed tags for outreach per channel
(sms / email / calling). Creating a campaign for a channel activates it and
ends whichever campaign was previously active for that channel; a past
campaign can be reactivated later, which is why history lives in
`campaign_periods` (a set of on/off intervals per campaign) rather than a
single started_at/ended_at pair on `campaigns` itself.

SMS/email conversations get stamped with campaign_id at the moment they
first send outbound (see sms.py::_store_message, email_inbox.py::manual_email_send,
integrations.py::process_newsletter_queue). Calling campaigns are not tagged
in the DB — analytics.py sums the Sheets-digest daily buckets over the
campaign's periods instead (calling's system of record stays the sheet).
"""

from fastapi import APIRouter, HTTPException

from db import get_pool

router = APIRouter()

_CHANNELS = {"sms", "email", "calling"}


async def _activate(conn, campaign_id: int, channel: str):
    async with conn.transaction():
        await conn.execute(
            """
            UPDATE campaign_periods SET ended_at = now()
            WHERE ended_at IS NULL
              AND campaign_id IN (SELECT id FROM campaigns WHERE channel = $1)
            """,
            channel,
        )
        await conn.execute(
            "INSERT INTO campaign_periods (campaign_id) VALUES ($1)", campaign_id
        )


@router.get("/campaigns")
async def list_campaigns(channel: str):
    if channel not in _CHANNELS:
        raise HTTPException(status_code=400, detail="channel must be one of sms/email/calling")
    pool = await get_pool()
    async with pool.acquire() as conn:
        campaigns = await conn.fetch(
            "SELECT * FROM campaigns WHERE channel = $1 ORDER BY created_at DESC", channel
        )
        periods = await conn.fetch(
            """
            SELECT cp.* FROM campaign_periods cp
            JOIN campaigns c ON c.id = cp.campaign_id
            WHERE c.channel = $1
            ORDER BY cp.started_at
            """,
            channel,
        )
    by_campaign: dict[int, list[dict]] = {}
    for p in periods:
        by_campaign.setdefault(p["campaign_id"], []).append(
            {"started_at": p["started_at"], "ended_at": p["ended_at"]}
        )
    result = []
    for c in campaigns:
        c_periods = by_campaign.get(c["id"], [])
        result.append({
            **dict(c),
            "periods": c_periods,
            "is_active": any(p["ended_at"] is None for p in c_periods),
        })
    return result


@router.get("/campaigns/active")
async def get_active_campaign(channel: str):
    if channel not in _CHANNELS:
        raise HTTPException(status_code=400, detail="channel must be one of sms/email/calling")
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT c.* FROM campaigns c
            JOIN campaign_periods cp ON cp.campaign_id = c.id
            WHERE c.channel = $1 AND cp.ended_at IS NULL
            """,
            channel,
        )
    return dict(row) if row else None


@router.post("/campaigns")
async def create_campaign(payload: dict):
    channel = (payload or {}).get("channel", "")
    name = (payload or {}).get("name", "").strip()
    if channel not in _CHANNELS:
        raise HTTPException(status_code=400, detail="channel must be one of sms/email/calling")
    if not name:
        raise HTTPException(status_code=400, detail="name required")

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO campaigns (channel, name) VALUES ($1, $2) RETURNING *",
            channel, name,
        )
        await _activate(conn, row["id"], channel)
    return dict(row)


@router.post("/campaigns/{campaign_id}/activate")
async def activate_campaign(campaign_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM campaigns WHERE id = $1", campaign_id)
        if not row:
            raise HTTPException(status_code=404, detail="Campaign not found")
        await _activate(conn, campaign_id, row["channel"])
    return dict(row)
