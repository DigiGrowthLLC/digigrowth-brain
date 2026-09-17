"""
Send Info -> personalized Loom queue.

Setting a contact's disposition to "Send Info" used to fire a generic
templated SMS + email immediately (routers/crm.py, routers/dialer.py). Now
it enqueues a row here instead: the outreach-video skill's Send Info Queue
Mode (content-agent/.claude/skills/outreach-video/SKILL.md) needs local
Playwright + ffmpeg + Dylan's local headcam-master.mp4, none of which exist
on this Railway container, so the personalized video can't be generated
synchronously inside a request. A scheduled local Claude Code run drains
this queue (content-agent/run-send-info-queue.ps1, same shape as
leadgen-agent's scheduled scrape-leads run), calling complete()/fail() below
via the /api/send-info-queue endpoints in routers/dialer.py once each
video's ready (or has failed).

routers.sms and integrations are imported lazily inside functions to avoid
circular imports (both of those modules are imported by routers that in
turn get imported before this module in some call chains).
"""

from db import get_pool


async def enqueue(contact: dict) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO send_info_loom_queue (contact_id) VALUES ($1)",
            contact["id"],
        )


async def _send_now(contact: dict, loom_url: str | None) -> None:
    import integrations
    from routers import sms as sms_router

    try:
        await sms_router.send_info_message(contact, loom_url=loom_url)
    except Exception as e:
        print(f"send-info SMS failed for {contact.get('phone')}: {e}")
    if contact.get("email"):
        try:
            result = await integrations.send_info_email(
                contact["email"], contact.get("owner"), contact.get("business"), loom_url=loom_url,
            )
            if not result.startswith("Sent email"):
                print(f"send-info email to {contact['email']} did not send: {result}")
        except Exception as e:
            print(f"send-info email failed for {contact.get('email')}: {e}")


async def complete(queue_id: int, watch_url: str) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT q.*, c.id AS c_id, c.phone, c.email, c.owner, c.business "
            "FROM send_info_loom_queue q JOIN contacts c ON c.id = q.contact_id "
            "WHERE q.id = $1",
            queue_id,
        )
        if not row:
            raise ValueError(f"Queue entry {queue_id} not found")
        contact = {"id": row["c_id"], "phone": row["phone"], "email": row["email"],
                   "owner": row["owner"], "business": row["business"]}
        await _send_now(contact, loom_url=watch_url)
        updated = await conn.fetchrow(
            "UPDATE send_info_loom_queue SET status = 'done', watch_url = $2, completed_at = now() "
            "WHERE id = $1 RETURNING *",
            queue_id, watch_url,
        )
    return dict(updated)


async def fail(queue_id: int, error: str) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE send_info_loom_queue SET status = 'failed', error = $2, completed_at = now() "
            "WHERE id = $1 RETURNING *",
            queue_id, error,
        )
    if not row:
        raise ValueError(f"Queue entry {queue_id} not found")
    return dict(row)
