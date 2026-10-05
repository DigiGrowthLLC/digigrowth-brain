"""
Public personalized landing-page mockups — no auth required.
A prospect taps a texted link (https://<landing-pages-domain>/lp/<slug>) and
gets a hosted, personalized page (a mockup of their own booking flow + a
funnel/guarantee explainer) with Open Graph tags for a rich SMS/iMessage link
preview. Built by design-agent's landing-page-lead-magnet skill.

Same shape as routers/watch.py: creation/upload is authenticated (mounted
under /api with require_auth in main.py); serving is public, scoped only by
an unguessable slug.

Unlike watch.py, the page's HTML is stored directly in Postgres (a rendered
page is a few KB — nowhere near the size that made storing video bytes
in-process an OOM risk, see watch.py's docstring for that history). R2 is
still used for the hero screenshot/mockup image, since the rich link preview
needs a real og:image URL — same presigned-PUT flow as watch.py's video
upload, just for one image instead of an mp4.

The public route is served off a separate branded subdomain (e.g.
pages.digigrowthllc.com) pointed at this same Railway service via a custom
domain + CNAME — that's DNS/Railway-level routing, not app-level, so this
module doesn't need to know or care which domain a request arrived on.
"""
import html

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

import blueprint_chat
import r2_storage
from db import get_pool

router = APIRouter()          # public: /lp/{slug}, /lp/{slug}/hero-image, /lp/{slug}/chat, /lp/{slug}/a/{name}
admin_router = APIRouter()    # authenticated: /landing-pages (create/list/approve)


def _safe_slug(slug: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in slug.strip().lower())
    if not safe:
        raise HTTPException(status_code=400, detail="Invalid slug")
    return safe


class CreateRequest(BaseModel):
    slug: str
    business: str = ""
    contact_id: str | None = None
    html: str
    og_title: str = ""
    og_description: str = ""
    # Blueprint pages only: practice context for the live demo chat agent.
    # None leaves an existing value alone on re-publish.
    chat_context: str | None = None


class ChatRequest(BaseModel):
    messages: list = []
    timezone: str | None = None


class HeroPresignRequest(BaseModel):
    slug: str
    content_type: str = "image/png"


class AssetPresignRequest(BaseModel):
    name: str
    content_type: str = "video/mp4"


def _safe_asset_name(name: str) -> str:
    safe = "".join(c for c in name.strip() if c.isalnum() or c in "-_.")
    if not safe or safe.startswith(".") or ".." in safe:
        raise HTTPException(status_code=400, detail="Invalid asset name")
    return safe


class HeroCompleteRequest(BaseModel):
    slug: str
    r2_key: str


@admin_router.post("/landing-pages")
async def create_landing_page(body: CreateRequest):
    """Create (or replace) a draft row. Called only after Dylan has approved
    the page inside the Claude Code session — never called speculatively."""
    safe_slug = _safe_slug(body.slug)
    contact_id = (body.contact_id or "").strip() or None
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO landing_pages (slug, contact_id, business, html, status, chat_context)
               VALUES ($1, $2, $3, $4, 'draft', $5)
               ON CONFLICT (slug) DO UPDATE
                 SET contact_id = $2, business = $3, html = $4,
                     chat_context = COALESCE($5, landing_pages.chat_context)
               RETURNING slug, business, status, created_at""",
            safe_slug, contact_id, body.business.strip() or None, body.html,
            (body.chat_context or "").strip() or None,
        )
    return {
        "slug": row["slug"],
        "status": row["status"],
        "lp_path": f"/lp/{row['slug']}",
    }


@admin_router.post("/landing-pages/{slug}/hero-image/presign")
async def presign_hero_image(slug: str, body: HeroPresignRequest):
    safe_slug = _safe_slug(slug)
    r2_key = f"landing-pages/{safe_slug}/hero.png"
    upload_url = r2_storage.presign_put(r2_key, body.content_type)
    return {"upload_url": upload_url, "r2_key": r2_key}


@admin_router.post("/landing-pages/{slug}/hero-image/complete")
async def complete_hero_image(slug: str, body: HeroCompleteRequest):
    safe_slug = _safe_slug(slug)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE landing_pages SET hero_r2_key = $2 WHERE slug = $1 RETURNING slug",
            safe_slug, body.r2_key,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Landing page not found — create it first")
    return {"ok": True}


@admin_router.post("/landing-pages/{slug}/assets/presign")
async def presign_asset(slug: str, body: AssetPresignRequest):
    """Presigned PUT for a page asset too heavy to inline in the HTML (the
    Patient Acquisition Blueprint's video ads). Served back publicly via
    /lp/{slug}/a/{name}."""
    r2_key = f"landing-pages/{_safe_slug(slug)}/assets/{_safe_asset_name(body.name)}"
    return {"upload_url": r2_storage.presign_put(r2_key, body.content_type), "r2_key": r2_key}


@admin_router.post("/landing-pages/{slug}/approve")
async def approve_landing_page(slug: str):
    safe_slug = _safe_slug(slug)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE landing_pages SET status = 'approved', approved_at = now() "
            "WHERE slug = $1 RETURNING slug",
            safe_slug,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Landing page not found")
    return {"ok": True}


@admin_router.post("/landing-pages/{slug}/sent")
async def mark_landing_page_sent(slug: str):
    """Called once the outbound SMS with this page's link has actually sent
    successfully — lets a future funnel-cohort query distinguish drafted vs.
    actually-sent pages, same distinction watch_videos' contact_id linkage
    gives the Loom outreach funnel."""
    safe_slug = _safe_slug(slug)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE landing_pages SET status = 'sent', sent_at = now() "
            "WHERE slug = $1 RETURNING slug",
            safe_slug,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Landing page not found")
    return {"ok": True}


@admin_router.get("/landing-pages")
async def list_landing_pages():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT slug, business, status, created_at, approved_at, sent_at "
            "FROM landing_pages ORDER BY created_at DESC"
        )
    return [dict(r) for r in rows]


async def _log_view_event(content_key: str, contact_id: str | None, event_type: str):
    """Same fire-and-forget pattern as watch.py's _log_view_event — a
    tracking bug must never break serving the page."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO content_view_events (source, content_key, contact_id, event_type) "
                "VALUES ($1, $2, $3, $4)",
                "landing_page", content_key, contact_id, event_type,
            )
    except Exception as e:
        print(f"[landing_pages] failed to log view event for {content_key}: {e}")


_TRACKING_SNIPPET = """
<script>
(function() {
  var fired = {};
  function track(eventType) {
    if (fired[eventType]) return;
    fired[eventType] = true;
    var payload = JSON.stringify({source: 'landing_page', content_key: '%s', event_type: eventType});
    navigator.sendBeacon('/track/view-event', new Blob([payload], {type: 'application/json'}));
  }
  track('view');
  window.addEventListener('scroll', function() {
    var pct = (window.scrollY + window.innerHeight) / document.body.scrollHeight;
    if (pct >= 0.75) track('progress_75');
    else if (pct >= 0.5) track('progress_50');
    else if (pct >= 0.25) track('progress_25');
  });
})();
</script>
"""


@router.get("/lp/{slug}", response_class=HTMLResponse, include_in_schema=False)
async def landing_page(slug: str, request: Request):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT html, business, hero_r2_key, contact_id FROM landing_pages WHERE slug = $1", slug
        )
    if not row:
        raise HTTPException(status_code=404, detail="Page not found")

    await _log_view_event(slug, row["contact_id"], "view")

    # Built from the incoming request, not a hardcoded base URL — this page
    # is meant to be served from a branded subdomain the app itself doesn't
    # need to know about (DNS/Railway-level routing, see module docstring).
    # OG tags need an absolute URL, not a relative one, for link previews.
    # Railway terminates TLS at its edge and forwards to this app as plain
    # HTTP, so request.url.scheme reports "http" even over a real HTTPS
    # connection — trust X-Forwarded-Proto (set by Railway's proxy) instead,
    # falling back to https since every real deployment of this app sits
    # behind TLS-only custom domains.
    scheme = request.headers.get("x-forwarded-proto", "https")
    base_url = f"{scheme}://{request.url.netloc}"

    business = html.escape(row["business"] or "your practice")
    og_title = f"A quick mockup for {business}"
    og_image_tag = ""
    if row["hero_r2_key"]:
        image_url = f"{base_url}/lp/{slug}/hero-image"
        og_image_tag = f'<meta property="og:image" content="{image_url}">\n<meta name="twitter:card" content="summary_large_image">'

    og_head = (
        f'<meta property="og:type" content="website">\n'
        f'<meta property="og:title" content="{og_title}">\n'
        f'<meta property="og:url" content="{base_url}/lp/{slug}">\n'
        f"{og_image_tag}\n"
    )

    page_html = row["html"]
    # Inject OG tags right after <head> and the tracking snippet right before
    # </body> — the generator (design-agent) is expected to hand back a full
    # document with both those anchors present.
    if "<head>" in page_html:
        page_html = page_html.replace("<head>", f"<head>\n{og_head}", 1)
    if "</body>" in page_html:
        page_html = page_html.replace("</body>", f"{_TRACKING_SNIPPET % slug}\n</body>", 1)

    return HTMLResponse(page_html)


@router.get("/lp/{slug}/hero-image", include_in_schema=False)
async def landing_page_hero_image(slug: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT hero_r2_key FROM landing_pages WHERE slug = $1", slug)
    if not row or not row["hero_r2_key"]:
        raise HTTPException(status_code=404, detail="No hero image for this page")
    get_url = r2_storage.presign_get(row["hero_r2_key"])
    return RedirectResponse(get_url, status_code=302)


@router.post("/lp/{slug}/chat", include_in_schema=False)
async def landing_page_chat(slug: str, body: ChatRequest, request: Request):
    """Live demo chat on a Patient Acquisition Blueprint page. Public (the
    page itself is public), so it's rate limited and only answers for pages
    that were published with a chat_context. See blueprint_chat.py."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT business, chat_context FROM landing_pages WHERE slug = $1", slug
        )
    if not row or not row["chat_context"]:
        raise HTTPException(status_code=404, detail="No chat on this page")

    ip = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip() or (
        request.client.host if request.client else "unknown"
    )
    if blueprint_chat.rate_limited(ip, slug):
        raise HTTPException(status_code=429, detail="Too many messages, try again in a bit")

    history = blueprint_chat.clean_history(body.messages)
    if not history:
        raise HTTPException(status_code=400, detail="No message to reply to")

    try:
        text = await blueprint_chat.reply(
            row["business"] or "the practice", row["chat_context"], body.timezone, history,
        )
    except Exception as e:
        print(f"[landing_pages] chat failed for {slug}: {e}")
        raise HTTPException(status_code=502, detail="Chat is unavailable right now")
    # "replies" = the separate texts the agent wrote (answer, then the next
    # question); the page shows each as its own bubble. "reply" keeps the
    # joined text for the transcript the browser sends back next turn.
    return {"reply": text, "replies": blueprint_chat.split_texts(text)}


@router.get("/lp/{slug}/a/{name}", include_in_schema=False)
async def landing_page_asset(slug: str, name: str):
    """Same redirect-to-presigned-R2 pattern as the hero image, for assets
    uploaded via /landing-pages/{slug}/assets/presign."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        exists = await conn.fetchval("SELECT 1 FROM landing_pages WHERE slug = $1", slug)
    if not exists:
        raise HTTPException(status_code=404, detail="Page not found")
    key = f"landing-pages/{_safe_slug(slug)}/assets/{_safe_asset_name(name)}"
    return RedirectResponse(r2_storage.presign_get(key), status_code=302)
