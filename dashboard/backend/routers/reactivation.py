"""Admin API for a client's database reactivation campaigns
(client_reactivation.py) — backs the Clients panel's Agents tab →
Database Reactivation Agent."""
import json
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import client_reactivation
from db import get_pool

router = APIRouter()


class CampaignBody(BaseModel):
    name: Optional[str] = None
    audience_sources: Optional[list[str]] = None
    audience_tags: Optional[list[str]] = None
    angle: Optional[str] = None
    touches: Optional[list[dict]] = None
    daily_cap: Optional[int] = None


class AudienceBody(BaseModel):
    audience_sources: list[str] = []
    audience_tags: list[str] = []


def _clean_touches(touches: list[dict]) -> list[dict]:
    out = []
    for t in touches:
        body = (t.get("body") or "").strip()
        if not body:
            continue
        try:
            day = max(0, int(t.get("day") or 0))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Each touch's day must be a number")
        out.append({"day": day, "body": body})
    days = [t["day"] for t in out]
    if days != sorted(days):
        raise HTTPException(status_code=400, detail="Touch days must go up in order")
    return out


def _row(r, stats: dict | None = None) -> dict:
    d = dict(r)
    if isinstance(d.get("touches"), str):
        d["touches"] = json.loads(d["touches"])
    if stats is not None:
        d["stats"] = stats
    return d


async def _campaign(conn, client_id: int, campaign_id: int):
    row = await conn.fetchrow(
        "SELECT * FROM reactivation_campaigns WHERE id = $1 AND client_id = $2", campaign_id, client_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return row


@router.get("/clients/{client_id}/reactivation/options")
async def reactivation_options(client_id: int):
    """What an audience can be built from: lead sources and tags, each with
    how many of this client's leads carry it, plus the default touches."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        sources = await conn.fetch(
            "SELECT lead_source, count(*) AS n FROM contacts WHERE client_id = $1 AND NOT is_client_anchor "
            "AND lead_source IS NOT NULL GROUP BY lead_source",
            client_id,
        )
        tags = await conn.fetch(
            "SELECT t AS tag, count(*) AS n FROM contacts, unnest(coalesce(tags, '{}')) t "
            "WHERE client_id = $1 AND NOT is_client_anchor GROUP BY t ORDER BY n DESC",
            client_id,
        )
    counts = {r["lead_source"]: r["n"] for r in sources}
    return {
        "sources": [{"source": s, "count": counts.get(s, 0)} for s in client_reactivation.AUDIENCE_SOURCES],
        "tags": [{"tag": r["tag"], "count": r["n"]} for r in tags],
        "default_touches": client_reactivation.DEFAULT_TOUCHES,
    }


@router.post("/clients/{client_id}/reactivation/preview")
async def preview_audience(client_id: int, body: AudienceBody):
    """How many leads an audience would text if started now, with a sample."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await client_reactivation.eligible_contacts(conn, client_id, body.audience_sources, body.audience_tags)
    return {
        "count": len(rows),
        "sample": [
            {"name": r["owner"] or r["phone"], "phone": r["phone"], "lead_source": r["lead_source"],
             "source_detail": r["source_detail"]}
            for r in rows[:10]
        ],
    }


@router.get("/clients/{client_id}/reactivation/campaigns")
async def list_campaigns(client_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM reactivation_campaigns WHERE client_id = $1 ORDER BY created_at DESC", client_id,
        )
        return [_row(r, await client_reactivation.campaign_stats(conn, r["id"])) for r in rows]


@router.post("/clients/{client_id}/reactivation/campaigns")
async def create_campaign(client_id: int, body: CampaignBody):
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    touches = _clean_touches(body.touches) if body.touches is not None else client_reactivation.DEFAULT_TOUCHES
    if not touches:
        raise HTTPException(status_code=400, detail="Add at least one touch")
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO reactivation_campaigns (client_id, name, audience_sources, audience_tags, angle, touches, daily_cap)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7) RETURNING *
            """,
            client_id, name, body.audience_sources or [], body.audience_tags or [], (body.angle or "").strip(),
            json.dumps(touches), max(1, body.daily_cap or 30),
        )
        return _row(row, await client_reactivation.campaign_stats(conn, row["id"]))


@router.put("/clients/{client_id}/reactivation/campaigns/{campaign_id}")
async def update_campaign(client_id: int, campaign_id: int, body: CampaignBody):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _campaign(conn, client_id, campaign_id)
        fields = {}
        if body.name is not None:
            if not body.name.strip():
                raise HTTPException(status_code=400, detail="Name is required")
            fields["name"] = body.name.strip()
        if body.audience_sources is not None:
            fields["audience_sources"] = body.audience_sources
        if body.audience_tags is not None:
            fields["audience_tags"] = body.audience_tags
        if body.angle is not None:
            fields["angle"] = body.angle.strip()
        if body.touches is not None:
            touches = _clean_touches(body.touches)
            if not touches:
                raise HTTPException(status_code=400, detail="Add at least one touch")
            fields["touches"] = json.dumps(touches)
        if body.daily_cap is not None:
            fields["daily_cap"] = max(1, body.daily_cap)
        if fields:
            sets = ", ".join(
                f"{k} = ${i + 2}::jsonb" if k == "touches" else f"{k} = ${i + 2}" for i, k in enumerate(fields)
            )
            await conn.execute(f"UPDATE reactivation_campaigns SET {sets} WHERE id = $1", campaign_id, *fields.values())
        row = await _campaign(conn, client_id, campaign_id)
        return _row(row, await client_reactivation.campaign_stats(conn, campaign_id))


@router.post("/clients/{client_id}/reactivation/campaigns/{campaign_id}/start")
async def start_campaign(client_id: int, campaign_id: int):
    """Start (or resume, or top up with newly eligible leads) a campaign."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        campaign = await _campaign(conn, client_id, campaign_id)
        config = await conn.fetchrow(
            "SELECT twilio_number FROM client_marketing_config WHERE client_id = $1", client_id,
        )
    if not config or not config["twilio_number"]:
        raise HTTPException(status_code=400, detail="This client has no Twilio number yet")
    if not client_reactivation.touches_of(campaign):
        raise HTTPException(status_code=400, detail="Add at least one touch first")
    added = await client_reactivation.start_campaign(campaign_id)
    return {"ok": True, "added": added}


@router.post("/clients/{client_id}/reactivation/campaigns/{campaign_id}/pause")
async def pause_campaign(client_id: int, campaign_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _campaign(conn, client_id, campaign_id)
        await conn.execute(
            "UPDATE reactivation_campaigns SET status = 'paused' WHERE id = $1 AND status = 'active'", campaign_id,
        )
    return {"ok": True}


@router.delete("/clients/{client_id}/reactivation/campaigns/{campaign_id}")
async def delete_campaign(client_id: int, campaign_id: int):
    """Only a campaign that never texted anyone can be deleted; otherwise
    pause it, so its history stays."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _campaign(conn, client_id, campaign_id)
        texted = await conn.fetchval(
            "SELECT count(*) FROM reactivation_enrollments WHERE campaign_id = $1 AND touches_sent > 0", campaign_id,
        )
        if texted:
            raise HTTPException(status_code=409, detail="This campaign already texted people. Pause it instead.")
        await conn.execute("DELETE FROM reactivation_campaigns WHERE id = $1", campaign_id)
    return {"ok": True}


@router.get("/clients/{client_id}/reactivation/campaigns/{campaign_id}/enrollments")
async def list_enrollments(client_id: int, campaign_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _campaign(conn, client_id, campaign_id)
        rows = await conn.fetch(
            """
            SELECT re.id, re.status, re.touches_sent, re.first_touch_at, re.last_touch_at, re.end_reason,
                   c.id AS contact_id, c.owner, c.phone, c.lead_source, c.source_detail
            FROM reactivation_enrollments re JOIN contacts c ON c.id = re.contact_id
            WHERE re.campaign_id = $1
            ORDER BY (re.status IN ('replied', 'booked')) DESC, re.last_touch_at DESC NULLS LAST, re.id
            """,
            campaign_id,
        )
    return [dict(r) for r in rows]
