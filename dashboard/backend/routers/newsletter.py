from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from db import get_pool

router = APIRouter()

_PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>Unsubscribed - DigiGrowth</title>
<style>body{{font-family:sans-serif;background:#090f26;color:#e8edf8;display:flex;
align-items:center;justify-content:center;height:100vh;margin:0;text-align:center;}}
div{{max-width:420px;padding:24px;}}</style></head>
<body><div><h2>{heading}</h2><p>{message}</p></div></body></html>"""


@router.get("/newsletter/unsubscribe/{contact_id}", response_class=HTMLResponse)
async def unsubscribe(contact_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Contacts can land in the newsletter send list via the `newsletter`
        # boolean OR a 'Newsletter' tag (see approvals.py::_enqueue_newsletter),
        # so both have to be cleared or a tagged contact would still get queued
        # again next send even after unsubscribing.
        result = await conn.execute(
            """UPDATE contacts
               SET newsletter = false,
                   newsletter_opted_out_at = now(),
                   tags = array_remove(tags, 'Newsletter')
               WHERE id = $1""",
            contact_id,
        )
    if result == "UPDATE 0":
        return _PAGE.format(heading="Nothing to do", message="That link isn't tied to an active subscription.")
    return _PAGE.format(heading="You're unsubscribed", message="You won't receive any further newsletter emails from DigiGrowth.")
