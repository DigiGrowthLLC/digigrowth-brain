"""
Marketing Setup auto-ticks that need the network, and the launch checklist sync.

Since Marketing Setup v2 (setup_steps.py, 2026-11-16) almost every step is
proven live from the database every time the checklist is read, so this only
handles what can't be checked cheaply on each read: the client's funnel domain
actually serving our funnel. Proofs are written to
client_marketing_config.guide_progress["v2"] and never unticked.

Runs inside client_resources_autofill's 10-minute job for every real client,
and on demand via POST /api/clients/{id}/marketing-config/autocheck (the
onboarding agent's service-delivery-setup skill calls it after each step).

sync_launch_checklist: once every Marketing Setup step behind a launch
checklist item is done, that item (the portal's read-only "To Do" tab) is
ticked too, so the client sees progress without Dylan checking things off twice.
"""
import re

import httpx

import setup_steps
from db import get_pool


async def _funnel_domain_live(domain: str | None) -> bool:
    """The client's funnel domain serves our funnel (main.py funnel_host_router):
    DNS, Railway's certificate and the host mapping are all in place."""
    host = re.sub(r"^https?://", "", (domain or "").strip()).split("/")[0]
    if not host:
        return False
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=True) as http:
            r = await http.get(f"https://{host}/")
        return r.status_code == 200 and "/track/view-event" in r.text
    except httpx.HTTPError:
        return False


async def sync_launch_checklist(client_id: int) -> list[str]:
    """Ticks each launch checklist item whose Marketing Setup steps are all
    done for this client. Never unticks. Returns the titles newly ticked."""
    done = await setup_steps.launch_checklist_done(client_id)
    pool = await get_pool()
    ticked = []
    async with pool.acquire() as conn:
        items = await conn.fetch(
            """SELECT li.id, li.title FROM launch_checklist_items li
               LEFT JOIN client_launch_checklist_status s ON s.item_id = li.id AND s.client_id = $1
               WHERE li.active AND s.completed_at IS NULL""",
            client_id,
        )
        for item in items:
            needed = setup_steps.LAUNCH_ITEM_STEPS.get(item["title"].strip().lower())
            if not needed or not all(n in done for n in needed):
                continue
            await conn.execute(
                """INSERT INTO client_launch_checklist_status (client_id, item_id, completed_at)
                   VALUES ($1, $2, now())
                   ON CONFLICT (client_id, item_id) DO UPDATE SET completed_at = now()""",
                client_id, item["id"],
            )
            ticked.append(item["title"])
    if ticked:
        print(f"[guide-autocheck] client {client_id}: launch checklist ticked {ticked}", flush=True)
    return ticked


async def autocheck(client_id: int) -> list[str]:
    """Writes the network-proven ticks for one client. Returns step ids newly ticked."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        cfg = await conn.fetchrow(
            "SELECT funnel_domain, guide_progress FROM client_marketing_config WHERE client_id = $1", client_id)
    if not cfg:
        return []
    progress = setup_steps._decode(cfg["guide_progress"], {})
    newly = []
    if not (progress.get("v2") or {}).get("dns") and await _funnel_domain_live(cfg["funnel_domain"]):
        await setup_steps.set_tick(client_id, "dns", True)
        newly.append("dns")
    if newly:
        print(f"[guide-autocheck] client {client_id}: ticked {newly}", flush=True)
    await sync_launch_checklist(client_id)
    return newly


async def autocheck_all() -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        ids = [r["id"] for r in await conn.fetch(
            "SELECT c.id FROM clients c JOIN client_marketing_config cmc ON cmc.client_id = c.id WHERE NOT c.is_test")]
    for client_id in ids:
        try:
            await setup_steps.status(client_id)  # runs the one-time v2 migration of old ticks
            await autocheck(client_id)
        except Exception as e:
            print(f"[guide-autocheck] client {client_id} failed: {e}", flush=True)
