"""
Public, client-facing portal endpoints — no HTTPBasic auth. Every route takes
an unguessable `token` path param that resolves to a client_id via
get_client_from_token(); no endpoint ever accepts client_id directly from the
request, so one client can never address another client's data. Same
"separate unauthenticated router + DB-scoped filter" shape as public_sops.py,
just with a per-request resolved scope instead of a static visibility column.

Stats are intentionally basic for now — real SMS/email totals scoped by
client_id, and an empty Facebook/Meta ads array (see meta_ads.py for the
integration that will eventually populate ad_campaign_stats). Not reusing
analytics.py's _sms_metrics/_email_metrics here: those functions are tuned
for the internal Analytics tab's campaign/stage funnel with a lot of
carefully-commented edge-case handling, and bolting a third scope dimension
onto them risked breaking that. This is a simpler, self-contained rollup
purpose-built for the portal's basic infrastructure pass.
"""
from fastapi import APIRouter, HTTPException

from db import get_pool
from models import OnboardingSectionSave, ONBOARDING_SECTIONS

router = APIRouter(prefix="/portal-api")


async def get_client_from_token(token: str) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM clients WHERE portal_token = $1 AND token_revoked_at IS NULL",
            token,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Invalid or revoked portal link")
    return dict(row)


@router.get("/{token}")
async def portal_home(token: str):
    client = await get_client_from_token(token)
    return {"id": client["id"], "name": client["name"], "status": client["status"]}


@router.get("/{token}/onboarding")
async def get_onboarding(token: str):
    client = await get_client_from_token(token)
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM client_onboarding_responses WHERE client_id = $1", client["id"]
        )
    by_section = {r["section"]: dict(r) for r in rows}
    return {
        "sections": ONBOARDING_SECTIONS,
        "responses": by_section,
        "progress": f"{len(by_section)}/{len(ONBOARDING_SECTIONS)}",
    }


@router.put("/{token}/onboarding/{section}")
async def save_onboarding_section(token: str, section: str, body: OnboardingSectionSave):
    if section not in ONBOARDING_SECTIONS:
        raise HTTPException(status_code=400, detail="Unknown onboarding section")
    client = await get_client_from_token(token)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO client_onboarding_responses (client_id, section, answers, completed_at)
            VALUES ($1, $2, $3, CASE WHEN $4 THEN now() ELSE NULL END)
            ON CONFLICT (client_id, section) DO UPDATE SET
                answers = EXCLUDED.answers,
                completed_at = CASE WHEN $4 THEN now() ELSE client_onboarding_responses.completed_at END,
                updated_at = now()
            RETURNING *
            """,
            client["id"], section, body.answers, body.completed,
        )
    return dict(row)


@router.get("/{token}/videos")
async def portal_videos(token: str):
    await get_client_from_token(token)
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, title, description, embed_url, sort_order FROM onboarding_videos "
            "WHERE active ORDER BY sort_order, id"
        )
    return [dict(r) for r in rows]


@router.get("/{token}/stats")
async def portal_stats(token: str):
    client = await get_client_from_token(token)
    pool = await get_pool()
    async with pool.acquire() as conn:
        sms_row = await conn.fetchrow(
            """
            SELECT
                COUNT(DISTINCT sc.id) AS conversations,
                COALESCE(SUM((sm.direction = 'outbound')::int), 0) AS sent,
                COALESCE(SUM((sm.direction = 'inbound')::int), 0) AS replies
            FROM sms_conversations sc
            LEFT JOIN sms_messages sm ON sm.contact_id = sc.contact_id
            WHERE sc.client_id = $1
            """,
            client["id"],
        )
        email_row = await conn.fetchrow(
            """
            SELECT
                COUNT(DISTINCT ec.id) AS conversations,
                COALESCE(SUM((em.direction = 'outbound')::int), 0) AS sent,
                COALESCE(SUM((em.direction = 'inbound')::int), 0) AS replies
            FROM email_conversations ec
            LEFT JOIN email_messages em ON em.contact_id = ec.contact_id
            WHERE ec.client_id = $1
            """,
            client["id"],
        )
        ad_rows = await conn.fetch(
            "SELECT * FROM ad_campaign_stats WHERE client_id = $1 AND platform = 'meta' "
            "ORDER BY stat_date DESC LIMIT 30",
            client["id"],
        )
    return {
        "sms": dict(sms_row),
        "email": dict(email_row),
        "ads": {
            "platform": "meta",
            "status": "coming_soon",
            "days": [dict(r) for r in ad_rows],
        },
    }
