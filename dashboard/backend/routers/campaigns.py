"""
Campaign tracking — named, time-windowed tags for outreach per channel
(sms / email / calling / vsl / loom). Creating a campaign for a channel
activates it and ends whichever campaign was previously active for that
channel; a past campaign can be reactivated later, which is why history
lives in `campaign_periods` (a set of on/off intervals per campaign) rather
than a single started_at/ended_at pair on `campaigns` itself.

SMS/email conversations get stamped with campaign_id at the moment they
first send outbound (see sms.py::_store_message, email_inbox.py::manual_email_send,
integrations.py::process_newsletter_queue). Calling campaigns are not tagged
in the DB — analytics.py sums the Sheets-digest daily buckets over the
campaign's periods instead (calling's system of record stays the sheet).

vsl/loom (content_tracking.py, watch.py) have no CRM contact row to pend a
campaign assignment on, so resolve_send_campaign below skips that step for
them entirely and just returns whichever campaign is currently active —
a VSL view is stamped with the active "vsl" campaign at the moment it's
logged (there's no per-contact "send" for a public page), while a Loom
outreach video is stamped with the active "loom" campaign at the moment
it's generated/published (its funnel's "Sent" cohort), same timing as
SMS/email's own stamp-at-send convention.
"""

from datetime import timedelta

from fastapi import APIRouter, HTTPException

from db import get_pool

router = APIRouter()

_CHANNELS = {"sms", "email", "calling", "vsl", "loom"}
_CHANNELS_MSG = "channel must be one of sms/email/calling/vsl/loom"


async def _activate(conn, campaign_id: int, channel: str):
    async with conn.transaction():
        already_active = await conn.fetchval(
            "SELECT 1 FROM campaign_periods WHERE campaign_id = $1 AND ended_at IS NULL",
            campaign_id,
        )
        if already_active:
            # No-op — a repeat click on "Reactivate"/create-for-already-active-
            # channel used to end the open period and immediately open a new
            # one, logging a spurious few-seconds-long period every time. See
            # collapse-periods below for cleaning up ones already logged.
            return
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

    vsl/loom have no pending_{channel}_campaign_id column on contacts (no
    CRM-side manual assignment exists for them) — skip straight to "whichever
    campaign is active" for those channels rather than probing a column that
    doesn't exist.
    """
    if contact_id and channel in ("sms", "email"):
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
        raise HTTPException(status_code=400, detail=_CHANNELS_MSG)
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
        raise HTTPException(status_code=400, detail=_CHANNELS_MSG)
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
        raise HTTPException(status_code=400, detail=_CHANNELS_MSG)
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


@router.post("/campaigns/{campaign_id}/collapse-periods")
async def collapse_campaign_periods(campaign_id: int, gap_seconds: int = 30):
    """Merges this campaign's own consecutive periods wherever the gap
    between one ending and the next starting is under `gap_seconds` —
    cleans up the spurious few-seconds-long on/off periods that used to get
    logged by repeat-clicking Reactivate/create before _activate became a
    no-op for an already-active campaign (see _activate above). A genuine
    gap (another campaign was active in between) is always preserved."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        campaign = await conn.fetchrow("SELECT * FROM campaigns WHERE id = $1", campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        periods = await conn.fetch(
            "SELECT id, started_at, ended_at FROM campaign_periods WHERE campaign_id = $1 ORDER BY started_at",
            campaign_id,
        )
        gap = timedelta(seconds=gap_seconds)
        merged = []
        for p in periods:
            prev = merged[-1] if merged else None
            touches_prev = prev is not None and prev["ended_at"] is not None and p["started_at"] <= prev["ended_at"] + gap
            if touches_prev:
                prev["ended_at"] = p["ended_at"]
                prev["ids"].append(p["id"])
            else:
                merged.append({"started_at": p["started_at"], "ended_at": p["ended_at"], "ids": [p["id"]]})

        removed = 0
        async with conn.transaction():
            for group in merged:
                keep_id = group["ids"][0]
                drop_ids = group["ids"][1:]
                await conn.execute(
                    "UPDATE campaign_periods SET started_at = $1, ended_at = $2 WHERE id = $3",
                    group["started_at"], group["ended_at"], keep_id,
                )
                if drop_ids:
                    await conn.execute("DELETE FROM campaign_periods WHERE id = ANY($1)", drop_ids)
                    removed += len(drop_ids)
    return {"ok": True, "periods_before": len(periods), "periods_after": len(merged), "removed": removed}


@router.post("/campaigns/{campaign_id}/backfill-history")
async def backfill_campaign_history(campaign_id: int):
    """One-time convenience for a freshly created vsl/loom campaign meant to
    represent "everything up to now" (e.g. a V.1.1 baseline created the day
    campaigning was turned on): attributes every pre-existing row that
    predates campaign tagging (campaign_id IS NULL) to this campaign, and
    backdates its currently-open period to the earliest such row's
    timestamp so the period range reflects real history instead of just
    "today". Only meaningful for vsl (content_view_events) and loom
    (watch_videos) — sms/email are tagged at send time with no backlog to
    backfill, and calling has no per-row campaign_id at all."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        campaign = await conn.fetchrow("SELECT * FROM campaigns WHERE id = $1", campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        channel = campaign["channel"]
        if channel == "vsl":
            earliest = await conn.fetchval(
                "SELECT min(occurred_at) FROM content_view_events WHERE source = 'vsl' AND campaign_id IS NULL"
            )
            n = await conn.fetchval(
                "WITH u AS (UPDATE content_view_events SET campaign_id = $1 "
                "WHERE source = 'vsl' AND campaign_id IS NULL RETURNING 1) SELECT count(*) FROM u",
                campaign_id,
            )
        elif channel == "loom":
            earliest = await conn.fetchval(
                "SELECT min(created_at) FROM watch_videos WHERE campaign_id IS NULL"
            )
            n = await conn.fetchval(
                "WITH u AS (UPDATE watch_videos SET campaign_id = $1 "
                "WHERE campaign_id IS NULL RETURNING 1) SELECT count(*) FROM u",
                campaign_id,
            )
        else:
            raise HTTPException(status_code=400, detail="backfill only supported for vsl/loom")
        if earliest:
            await conn.execute(
                "UPDATE campaign_periods SET started_at = $1 WHERE campaign_id = $2 AND ended_at IS NULL",
                earliest, campaign_id,
            )
    return {"ok": True, "rows_tagged": n, "backdated_to": earliest}


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
    """
    Manually tagging a contact with a campaign from the CRM is a retroactive
    claim, unlike the automatic per-message tagging that happens at send
    time (sms.py::_store_message, resolve_send_campaign) — a rep assigning
    "Free Offer Campaign" to a prospect they already texted last month wants
    that prior outreach/replies counted toward this campaign's stats, not
    just whatever gets sent going forward. So this backfills every existing
    outbound message for the contact into the campaign too, overriding
    whatever campaign (if any) those messages were previously tagged with.

    Clicking a campaign on the contact card is purely a tracking/analytics
    action, not a trigger for anything to actually send — it must count
    toward that campaign's stats the moment it's clicked, not sit in limbo
    until the contact happens to get texted. Previously, a contact with no
    sms_conversations row yet (never texted) only got pending_sms_campaign_id
    set on `contacts`, which analytics.py's _sms_metrics never reads at all
    (it only counts sms_conversations.campaign_id) — so an assignment made
    from the contact card stayed invisible to Analytics indefinitely,
    surfacing only as a confusing "(pending)" label with no indication it
    wasn't actually being tracked. Reported live 2026-09-22. Now creates the
    sms_conversations row immediately (empty message history — this is a
    tracking record, not an enrollment into any send sequence) with
    campaign_id already set, so it's counted right away. A real first
    outbound later just fills in that same row's messages — sms.py's
    UPDATE...campaign_id = COALESCE(campaign_id, ...) never overwrites the
    manual assignment. A contact with no phone on file at all has no channel
    to create this row against — SMS campaign assignment is refused outright
    for those rather than left silently pending forever.
    """
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
        contact = await conn.fetchrow("SELECT id, phone FROM contacts WHERE id = $1", contact_id)
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")

        if channel == "sms":
            conv = await conn.fetchrow("SELECT id FROM sms_conversations WHERE contact_id = $1", contact_id)
            if conv:
                await conn.execute(
                    "UPDATE sms_conversations SET campaign_id = $2, updated_at = now() WHERE contact_id = $1",
                    contact_id, campaign_id,
                )
                await conn.execute(
                    "UPDATE sms_messages SET campaign_id = $2 WHERE contact_id = $1 AND direction = 'outbound'",
                    contact_id, campaign_id,
                )
                await conn.execute("UPDATE contacts SET pending_sms_campaign_id = NULL WHERE id = $1", contact_id)
            elif contact["phone"]:
                await conn.execute(
                    """
                    INSERT INTO sms_conversations (contact_id, phone, campaign_id)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (phone) DO UPDATE SET campaign_id = $3, updated_at = now()
                    """,
                    contact_id, contact["phone"], campaign_id,
                )
                await conn.execute("UPDATE contacts SET pending_sms_campaign_id = NULL WHERE id = $1", contact_id)
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Contact has no phone number on file — add one before assigning an SMS campaign.",
                )
        else:
            conv = await conn.fetchrow(
                "SELECT id FROM email_conversations WHERE contact_id = $1 ORDER BY updated_at DESC LIMIT 1",
                contact_id,
            )
            if conv:
                await conn.execute(
                    "UPDATE email_conversations SET campaign_id = $2, updated_at = now() WHERE contact_id = $1",
                    contact_id, campaign_id,
                )
                await conn.execute(
                    "UPDATE email_messages SET campaign_id = $2 WHERE contact_id = $1 AND direction = 'outbound'",
                    contact_id, campaign_id,
                )
                await conn.execute("UPDATE contacts SET pending_email_campaign_id = NULL WHERE id = $1", contact_id)
            else:
                await conn.execute("UPDATE contacts SET pending_email_campaign_id = $2 WHERE id = $1", contact_id, campaign_id)

    return {"ok": True, "channel": channel, "campaign_id": campaign_id}


@router.delete("/contacts/{contact_id}/campaigns/{campaign_id}")
async def remove_contact_campaign(contact_id: str, campaign_id: int):
    """Undoes assign_contact_campaign's backfill symmetrically — clears the
    campaign tag from the contact's conversation, message history, and any
    still-unconsumed pending assignment."""
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
                "UPDATE sms_messages SET campaign_id = NULL WHERE contact_id = $1 AND campaign_id = $2",
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
                "UPDATE email_messages SET campaign_id = NULL WHERE contact_id = $1 AND campaign_id = $2",
                contact_id, campaign_id,
            )
            await conn.execute(
                "UPDATE contacts SET pending_email_campaign_id = NULL WHERE id = $1 AND pending_email_campaign_id = $2",
                contact_id, campaign_id,
            )
    return {"ok": True}
