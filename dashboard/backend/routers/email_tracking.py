"""
Public (no-auth) endpoints hit directly from recipients' email clients —
same reasoning as routers/newsletter.py's unsubscribe page: these are opened
by people who aren't logged into the dashboard, so they can't sit behind
HTTPBasic auth.

  GET /track/open/{token}.gif      — open-tracking pixel, embedded in outreach emails
  GET /email/unsubscribe/{contact_id} — outreach opt-out link, embedded in outreach emails

Distinct from the newsletter's own unsubscribe flow (contacts.newsletter),
which is a separate opt-in list — this one governs 1:1 outreach sends
(gmail_send/gmail_send_reply with track=True) via contacts.email_opted_out.
"""

from fastapi import APIRouter, Response
from fastapi.responses import HTMLResponse

from db import get_pool

router = APIRouter()

# 1x1 transparent GIF
_PIXEL = bytes.fromhex(
    "47494638396101000100800000000000ffffff21f90401000000002c00000000010001000002024401003b"
)

_PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>Unsubscribed - DigiGrowth</title>
<style>body{{font-family:sans-serif;background:#090f26;color:#e8edf8;display:flex;
align-items:center;justify-content:center;height:100vh;margin:0;text-align:center;}}
div{{max-width:420px;padding:24px;}}</style></head>
<body><div><h2>{heading}</h2><p>{message}</p></div></body></html>"""


@router.get("/track/open/{token}.gif")
async def track_open(token: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """UPDATE email_messages
               SET opened_at = COALESCE(opened_at, now()), open_count = open_count + 1
               WHERE tracking_token = $1""",
            token,
        )
    return Response(
        content=_PIXEL,
        media_type="image/gif",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"},
    )


@router.get("/email/unsubscribe/{contact_id}", response_class=HTMLResponse)
async def unsubscribe(contact_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE contacts SET email_opted_out = true, email_opted_out_at = now() WHERE id = $1",
            contact_id,
        )
    if result == "UPDATE 0":
        return _PAGE.format(heading="Nothing to do", message="That link isn't tied to an active contact.")
    return _PAGE.format(heading="You're unsubscribed", message="You won't receive any further outreach emails from DigiGrowth.")
