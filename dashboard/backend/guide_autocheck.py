"""
Ticks Marketing Setup guide steps (client_marketing_config.guide_progress)
that the dashboard's own data proves are done, so Dylan only checks off the
genuinely manual ones. Never unticks anything — a step Dylan marked done by
hand, or one done before its signal existed, stays done.

Step indexes mirror MARKETING_GUIDES in dashboard/frontend/src/panels/
ClientsPanel.jsx (guide_progress is keyed by guide key + step index). Those
guides are append-only, so an index here never changes meaning; when a step
is appended there and is provable from data, add its signal here.

Runs inside client_resources_autofill's 10-minute job for every real client,
and on demand via POST /api/clients/{id}/marketing-config/autocheck (the
onboarding agent's service-delivery-setup skill calls it after each step).
"""
import json
import re

from db import get_pool


def _decode(value, default):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return default
    return value if value is not None else default


async def _signals(conn, client_id: int) -> dict[str, list[int]]:
    """{guide_key: [step indexes proven done]} for one client."""
    cfg = await conn.fetchrow("SELECT * FROM client_marketing_config WHERE client_id = $1", client_id)
    client = await conn.fetchrow("SELECT * FROM clients WHERE id = $1", client_id)
    if not cfg or not client:
        return {}
    cfg = dict(cfg)
    inbound = await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM client_sms_messages WHERE client_id = $1 AND direction = 'inbound')", client_id)
    ai_replied = await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM client_sms_messages WHERE client_id = $1 AND stage = 'ai_reply')", client_id)
    anchor = await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM contacts WHERE client_id = $1 AND is_client_anchor)", client_id)
    sequences = await conn.fetchval("SELECT count(*) FROM client_sequence_steps WHERE client_id = $1", client_id)

    booking = (client["calendly_url"] or cfg.get("calendly_event_type_url") or "").strip()
    on_ghl = bool(re.search(r"leadconnectorhq\.com|msgsndr\.com|/widget/booking/", booking))
    on_calendly = bool(cfg.get("calendly_api_token") and cfg.get("calendly_event_type_url"))
    ghl_live = bool(cfg.get("ghl_last_webhook_at"))
    seq = _decode(cfg.get("response_ai_sequence"), [])

    done: dict[str, list[int]] = {}

    def mark(guide: str, *idx: int, when: bool = True):
        if when:
            done.setdefault(guide, []).extend(idx)

    number = bool(cfg.get("twilio_number"))
    # sms: 0 number bought, 2 webhook (set on purchase), 3/5 a text landed,
    # 4 AI uses this number, 6 call forwarding has a target, 7 number handover (n/a once a number exists)
    mark("sms", 0, 2, 7, when=number)
    mark("sms", 3, 5, when=number and inbound)
    mark("sms", 4, when=number and bool(cfg.get("response_ai_enabled")))
    mark("sms", 6, when=number and bool(cfg.get("call_forward_number") or client["phone"]))

    # email: 0 subdomain picked, 10 mailbox token saved
    mark("email", 0, when=bool(cfg.get("email_subdomain")))
    mark("email", 10, when=bool(cfg.get("gmail_refresh_token")))

    # response_ai: 0 number, 1-2 agent + context, 3 sequence, 4 rules,
    # 5 Calendly (the default) / 13-14 GHL (only when the client explicitly books
    # on GoHighLevel) — either path completes booking, the other is n/a,
    # 6 a real AI reply went out, 10 Lead Ads relay built, 15 GHL booking reached us
    mark("response_ai", 0, when=number)
    mark("response_ai", 1, 2, when=bool(cfg.get("response_ai_enabled") and cfg.get("response_ai_context")))
    mark("response_ai", 3, when=bool(seq))
    mark("response_ai", 4, when=bool(cfg.get("response_ai_rules") or cfg.get("response_ai_max_words")))
    mark("response_ai", 5, when=on_calendly or (on_ghl and ghl_live))
    mark("response_ai", 13, 14, when=on_calendly or (on_ghl and ghl_live))
    mark("response_ai", 6, when=ai_replied)
    mark("response_ai", 10, when=bool(cfg.get("make_scenario_id") and not cfg.get("lead_ads_error")))
    mark("response_ai", 15, when=on_ghl and ghl_live)

    # landing_page: 0 built, 3 live URL saved
    mark("landing_page", 0, 3, when=bool(cfg.get("landing_page_url")))

    # ad_creatives: 1 pixel ID saved, 3 ad account + Page saved, 6 ad account saved, 7 Page saved
    mark("ad_creatives", 1, when=bool(cfg.get("meta_pixel_id")))
    mark("ad_creatives", 3, when=bool(cfg.get("meta_ad_account_id") and cfg.get("meta_page_id")))
    mark("ad_creatives", 6, when=bool(cfg.get("meta_ad_account_id")))
    mark("ad_creatives", 7, when=bool(cfg.get("meta_page_id")))

    # client_portal: 0 booking link saved, 1 the client's own contact is linked
    mark("client_portal", 0, when=bool(booking))
    mark("client_portal", 1, when=anchor)

    # automations: 1 sequence copy seeded (review is still worth doing, but the copy exists)
    mark("automations", 1, when=sequences > 0)
    return done


async def autocheck(client_id: int) -> dict[str, list[int]]:
    """Ticks every proven step for one client. Returns {guide: [newly ticked indexes]}."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        proven = await _signals(conn, client_id)
        if not proven:
            return {}
        row = await conn.fetchrow("SELECT guide_progress FROM client_marketing_config WHERE client_id = $1", client_id)
        progress = _decode(row["guide_progress"] if row else None, {})
        newly: dict[str, list[int]] = {}
        for guide, idxs in proven.items():
            slot = progress.setdefault(guide, {})
            for i in sorted(set(idxs)):
                if not slot.get(str(i)):
                    slot[str(i)] = True
                    newly.setdefault(guide, []).append(i)
        if newly:
            await conn.execute(
                "UPDATE client_marketing_config SET guide_progress = $2::jsonb, updated_at = now() WHERE client_id = $1",
                client_id, json.dumps(progress),
            )
            print(f"[guide-autocheck] client {client_id}: ticked {newly}", flush=True)
    return newly


async def autocheck_all() -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        ids = [r["id"] for r in await conn.fetch(
            "SELECT c.id FROM clients c JOIN client_marketing_config cmc ON cmc.client_id = c.id WHERE NOT c.is_test")]
    for client_id in ids:
        await autocheck(client_id)
