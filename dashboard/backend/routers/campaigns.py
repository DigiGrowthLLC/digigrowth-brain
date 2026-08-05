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


async def resolve_send_campaign(conn, channel: str, contact_id: str | None) -> int | None:
    """
    Determine which campaign an individual outbound send (SMS/email) should
    be tagged with. A CRM-assigned pending campaign for this contact
    (contacts.pending_{channel}_campaign_id — see crm.py's contact-campaign
    endpoints) takes priority and is consumed/cleared here, since it only
    ever applies to that contact's very first send. Otherwise falls back to
    whichever campaign is currently active for the channel, if any.
    """
    if contact_id:
        pending_col = f"pending_{channel}_campaign_id"
        pending_id = await conn.fetchval(
            f"SELECT {pending_col} FROM contacts WHERE id = $1", contact_id
        )
        if pending_id:
            await conn.execute(
                f"UPDATE contacts SET {pending_col} = NULL WHERE id = $1", contact_id
            )
            return pending_id
    return await conn.fetchval(
        """
        SELECT cp.campaign_id FROM campaign_periods cp
        JOIN campaigns c ON c.id = cp.campaign_id
        WHERE c.channel = $1 AND cp.ended_at IS NULL
        """,
        channel,
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


# ── CRM contact ↔ campaign assignment (sms/email only — calling has no ────────
# ── per-contact record to attach a campaign to) ────────────────────────────────

@router.get("/contacts/{contact_id}/campaigns")
async def get_contact_campaigns(contact_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        contact = await conn.fetchrow(
            "SELECT pending_sms_campaign_id, pending_email_campaign_id FROM contacts WHERE id = $1",
            contact_id,
        )
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        sms_conv = await conn.fetchrow(
            "SELECT campaign_id FROM sms_conversations WHERE contact_id = $1", contact_id
        )
        email_conv = await conn.fetchrow(
            "SELECT campaign_id FROM email_conversations WHERE contact_id = $1 "
            "ORDER BY updated_at DESC LIMIT 1",
            contact_id,
        )
        campaign_ids = [
            cid for cid in (
                (sms_conv["campaign_id"] if sms_conv else None),
                (email_conv["campaign_id"] if email_conv else None),
                contact["pending_sms_campaign_id"],
                contact["pending_email_campaign_id"],
            ) if cid
        ]
        campaigns = {}
        if campaign_ids:
            rows = await conn.fetch("SELECT * FROM campaigns WHERE id = ANY($1)", campaign_ids)
            campaigns = {r["id"]: dict(r) for r in rows}

    def _entry(campaign_id, pending):
        if not campaign_id:
            return None
        return {**campaigns[campaign_id], "pending": pending}

    return {
        "sms":   _entry(sms_conv["campaign_id"], False) if sms_conv and sms_conv["campaign_id"]
                 else _entry(contact["pending_sms_campaign_id"], True),
        "email": _entry(email_conv["campaign_id"], False) if email_conv and email_conv["campaign_id"]
                 else _entry(contact["pending_email_campaign_id"], True),
    }


@router.post("/contacts/{contact_id}/campaigns")
async def assign_contact_campaign(contact_id: str, payload: dict):
    campaign_id = (payload or {}).get("campaign_id")
    if not campaign_id:
        raise HTTPException(status_code=400, detail="campaign_id required")

    pool = await get_pool()
    async with pool.acquire() as conn:
        campaign = await conn.fetchrow("SELECT * FROM campaigns WHERE id = $1", campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        channel = campaign["channel"]
        if channel not in ("sms", "email"):
            raise HTTPException(status_code=400, detail="Only sms/email campaigns can be assigned from the CRM")
        contact = await conn.fetchrow("SELECT id FROM contacts WHERE id = $1", contact_id)
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")

        if channel == "sms":
            conv = await conn.fetchrow("SELECT id FROM sms_conversations WHERE contact_id = $1", contact_id)
            if conv:
                await conn.execute(
                    "UPDATE sms_conversations SET campaign_id = $2, updated_at = now() WHERE contact_id = $1",
                    contact_id, campaign_id,
                )
                await conn.execute("UPDATE contacts SET pending_sms_campaign_id = NULL WHERE id = $1", contact_id)
            else:
                await conn.execute("UPDATE contacts SET pending_sms_campaign_id = $2 WHERE id = $1", contact_id, campaign_id)
        else:
            conv = await conn.fetchrow(
                "SELECT id FROM email_conversations WHERE contact_id = $1 ORDER BY updated_at DESC LIMIT 1",
                contact_id,
            )
            if conv:
                await conn.execute(
                    "UPDATE email_conversations SET campaign_id = $2, updated_at = now() WHERE id = $1",
                    conv["id"], campaign_id,
                )
                await conn.execute("UPDATE contacts SET pending_email_campaign_id = NULL WHERE id = $1", contact_id)
            else:
                await conn.execute("UPDATE contacts SET pending_email_campaign_id = $2 WHERE id = $1", contact_id, campaign_id)

    return {"ok": True, "channel": channel, "campaign_id": campaign_id}


@router.delete("/contacts/{contact_id}/campaigns/{campaign_id}")
async def remove_contact_campaign(contact_id: str, campaign_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        campaign = await conn.fetchrow("SELECT * FROM campaigns WHERE id = $1", campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        channel = campaign["channel"]
        if channel == "sms":
            await conn.execute(
                "UPDATE sms_conversations SET campaign_id = NULL WHERE contact_id = $1 AND campaign_id = $2",
                contact_id, campaign_id,
            )
            await conn.execute(
                "UPDATE contacts SET pending_sms_campaign_id = NULL WHERE id = $1 AND pending_sms_campaign_id = $2",
                contact_id, campaign_id,
            )
        elif channel == "email":
            await conn.execute(
                "UPDATE email_conversations SET campaign_id = NULL WHERE contact_id = $1 AND campaign_id = $2",
                contact_id, campaign_id,
            )
            await conn.execute(
                "UPDATE contacts SET pending_email_campaign_id = NULL WHERE id = $1 AND pending_email_campaign_id = $2",
                contact_id, campaign_id,
            )
    return {"ok": True}
