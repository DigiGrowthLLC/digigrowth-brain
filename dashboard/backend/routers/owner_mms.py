"""Owner MMS inbox — pictures Dylan texts to the OS number from his own phone.

Built for the executive-assistant morning planner (calendar-management skill):
his boss texts the Discount Tire schedule photo every Wednesday, Dylan forwards
it to the OS Twilio number, and the planner reads it from here.

Only MMS **with media** from Dylan's own phone (the `dylan_alert_phone` setting /
DYLAN_ALERT_PHONE / the setter default) is diverted. His plain texts still go
through the normal SMS inbox, because the same number is the default test phone
for leads and the AI setter.

Routes (authenticated, mounted under /api):
  GET  /owner-mms?unprocessed=true         list (newest first, no image bytes)
  GET  /owner-mms/{id}/image               raw image bytes
  POST /owner-mms/{id}/processed  {note}   mark handled so it isn't re-read
"""
import os

import httpx
from fastapi import APIRouter, HTTPException, Response

from db import get_pool

router = APIRouter()

ALERT_PHONE_KEY = "dylan_alert_phone"   # same setting sms_setter_ai uses
_DEFAULT_OWNER_PHONE = "+17542485326"
_MAX_BYTES = 10 * 1024 * 1024


def _last10(phone: str) -> str:
    return "".join(c for c in (phone or "") if c.isdigit())[-10:]


async def _owner_phone(conn) -> str:
    row = await conn.fetchrow("SELECT value FROM dialer_settings WHERE key = $1", ALERT_PHONE_KEY)
    return (row["value"] if row and row["value"] else None) or os.environ.get("DYLAN_ALERT_PHONE") or _DEFAULT_OWNER_PHONE


async def capture_if_owner(form) -> bool:
    """Called first thing by the inbound SMS webhook. Returns True if this was an
    owner picture text and it has been stored (the webhook should then stop)."""
    try:
        num_media = int(form.get("NumMedia") or 0)
    except ValueError:
        num_media = 0
    from_phone = form.get("From", "")
    if not num_media or not from_phone:
        return False

    pool = await get_pool()
    async with pool.acquire() as conn:
        if _last10(from_phone) != _last10(await _owner_phone(conn)):
            return False

        body = (form.get("Body") or "").strip()
        auth = (os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
        stored = 0
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as http:
            for i in range(num_media):
                url = form.get(f"MediaUrl{i}")
                ctype = form.get(f"MediaContentType{i}") or "application/octet-stream"
                if not url:
                    continue
                try:
                    r = await http.get(url, auth=auth)
                    r.raise_for_status()
                    data = r.content
                except Exception as e:  # keep the row so the failure is visible
                    print(f"owner_mms: media download failed ({url}): {e}")
                    data = None
                if data is not None and len(data) > _MAX_BYTES:
                    data = None
                await conn.execute(
                    """INSERT INTO owner_mms (from_phone, body, content_type, media_url, data)
                       VALUES ($1, $2, $3, $4, $5)""",
                    from_phone, body, ctype, url, data,
                )
                stored += 1
    return stored > 0


@router.get("/owner-mms")
async def list_owner_mms(unprocessed: bool = False, limit: int = 20):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""SELECT id, received_at, body, content_type, octet_length(data) AS size,
                       processed_at, note
                FROM owner_mms {"WHERE processed_at IS NULL" if unprocessed else ""}
                ORDER BY received_at DESC LIMIT $1""",
            min(max(limit, 1), 100),
        )
    return [dict(r) for r in rows]


@router.get("/owner-mms/{mms_id}/image")
async def owner_mms_image(mms_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT content_type, data FROM owner_mms WHERE id = $1", mms_id)
    if not row or row["data"] is None:
        raise HTTPException(404, "No image stored for this message")
    return Response(content=bytes(row["data"]), media_type=row["content_type"])


@router.post("/owner-mms/{mms_id}/processed")
async def mark_owner_mms_processed(mms_id: int, payload: dict | None = None):
    note = ((payload or {}).get("note") or "")[:500]
    pool = await get_pool()
    async with pool.acquire() as conn:
        res = await conn.execute(
            "UPDATE owner_mms SET processed_at = now(), note = $2 WHERE id = $1", mms_id, note,
        )
    if res.endswith(" 0"):
        raise HTTPException(404, "Not found")
    return {"ok": True}
