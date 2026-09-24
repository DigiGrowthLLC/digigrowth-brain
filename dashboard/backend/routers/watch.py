"""
Public video watch pages — no auth required.
A prospect clicks a texted link (https://<dashboard>/watch/<slug>) and gets an
inline video player with Open Graph video tags for SMS/iMessage rich previews.
Upload is authenticated (mounted under /api with require_auth in main.py);
serving is public, scoped only by an unguessable slug — same pattern as
routers/client_portal.py.

Storage is Cloudflare R2 (see r2_storage.py) via a presigned-PUT flow: the
uploader (content-agent/tools/publish_to_watch.py) asks this backend for a
presigned URL, PUTs the video straight to R2 itself, then tells this backend
the upload is done. The video's bytes never pass through this FastAPI
process. This replaced an earlier GitHub-Contents-API approach (base64-
encoding the whole file into one in-memory JSON PUT) that OOM-crashed the
Railway container on anything much above ~30MB — see the railway deployment
history around 2026-09-04 for the crash-restart pattern this caused.
github_path/_gh_fetch below is legacy-read-only support for the handful of
videos published before this migration; every new upload uses r2_key.
"""
import html
import os

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import BaseModel

import r2_storage
from db import get_pool
from routers.campaigns import resolve_send_campaign

router = APIRouter()          # public: /watch/{slug}, /watch/{slug}/file
admin_router = APIRouter()    # authenticated: /watch-videos (upload)

_GITHUB_REPO = os.environ.get("GITHUB_REPO", "DigiGrowthLLC/digigrowth-brain")
_DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "https://digigrowth-brain-production.up.railway.app").rstrip("/")

# Branded video domain (e.g. https://watch.digigrowthllc.com) — a Railway
# custom domain on this same service. When set, watch links are
# <base>/<slug> (main.py's watch_host_router maps that host's /<slug> onto
# /watch/<slug>). Unset = links stay on DASHBOARD_URL/watch/<slug>.
PUBLIC_VIDEO_BASE = os.environ.get("PUBLIC_VIDEO_BASE", "").strip().rstrip("/")
WATCH_HOST = PUBLIC_VIDEO_BASE.split("://", 1)[-1].split("/", 1)[0].lower() if PUBLIC_VIDEO_BASE else ""


def public_watch_url(slug: str) -> str:
    return f"{PUBLIC_VIDEO_BASE}/{slug}" if PUBLIC_VIDEO_BASE else f"{_DASHBOARD_URL}/watch/{slug}"


def _is_watch_host(request: Request) -> bool:
    host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").split(":")[0].lower()
    return bool(WATCH_HOST) and host == WATCH_HOST

# In-memory cache of fetched video bytes, keyed by slug — only ever populated
# for legacy GitHub-backed rows (see _gh_fetch below); video players issue
# many Range requests while seeking and without this every seek would re-hit
# the GitHub API for the full file. R2-backed rows never touch this cache —
# they're served via a redirect straight to R2, which handles Range itself.
# Process-lifetime only, not persistence.
_video_cache: dict[str, bytes] = {}


def _safe_slug(slug: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in slug.strip().lower())
    if not safe:
        raise HTTPException(status_code=400, detail="Invalid slug")
    return safe


def _gh_fetch(path: str) -> bytes:
    """Legacy read path for the handful of videos uploaded before the R2
    migration (2026-09-04) — see this module's docstring. Nothing writes
    through this path anymore; new uploads always go to R2."""
    import base64
    import json
    import urllib.error
    import urllib.request

    token = os.environ.get("GIT_TOKEN", "")
    url = f"https://api.github.com/repos/{_GITHUB_REPO}/contents/{path}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
        if result.get("content"):
            return base64.b64decode(result["content"].replace("\n", ""))
        if result.get("download_url"):
            dl_req = urllib.request.Request(result["download_url"], headers={"Authorization": f"token {token}"})
            with urllib.request.urlopen(dl_req, timeout=60) as resp:
                return resp.read()
        raise HTTPException(status_code=404, detail="File content unavailable")
    except urllib.error.HTTPError as e:
        raise HTTPException(status_code=404 if e.code == 404 else 502, detail=f"GitHub error: {e}")


class PresignRequest(BaseModel):
    slug: str
    content_type: str = "video/mp4"


class CompleteRequest(BaseModel):
    slug: str
    title: str = ""
    contact_id: str | None = None
    r2_key: str
    file_size: int
    content_type: str = "video/mp4"


@admin_router.post("/watch-videos/presign")
async def presign_watch_video(body: PresignRequest):
    """Step 1 of publishing: hand back a presigned R2 PUT URL for this slug.
    The uploader (content-agent/tools/publish_to_watch.py) PUTs the video
    bytes straight to R2 with this URL — they never pass through this
    backend's memory, which is what used to OOM-crash the Railway container
    on anything much above ~30MB when this went through GitHub's Contents
    API instead (see module docstring)."""
    safe_slug = _safe_slug(body.slug)
    r2_key = f"watch/{safe_slug}.mp4"
    upload_url = r2_storage.presign_put(r2_key, body.content_type)
    return {"upload_url": upload_url, "r2_key": r2_key}


@admin_router.post("/watch-videos/complete")
async def complete_watch_video(body: CompleteRequest):
    """Step 2: called once the direct-to-R2 PUT above succeeds, to record
    the watch_videos row. `contact_id` is optional (some slugs — old ones,
    or future generic uses — may not have a known recipient) but is what
    lets the Loom Outreach analytics funnel (see content_tracking.py) know
    this video was sent to a specific prospect at all."""
    return await register_watch_video(
        body.slug, body.title, body.r2_key, body.file_size, body.content_type, body.contact_id,
    )


async def register_watch_video(slug: str, title: str, r2_key: str, file_size: int,
                               content_type: str = "video/mp4", contact_id: str | None = None) -> dict:
    """Records the watch_videos row for an object already in R2 and returns
    its public watch URL. Shared by the upload endpoint above and
    outreach_video.py's server-side generator."""
    safe_slug = _safe_slug(slug)
    contact_id = (contact_id or "").strip() or None
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Stamped once, at publish — this is the Loom Outreach funnel's
        # "Sent" cohort tag (see content_tracking.py::loom_outreach_funnel),
        # same "tag at send time" convention as SMS/email campaigns.
        campaign_id = await resolve_send_campaign(conn, "loom", contact_id)
        row = await conn.fetchrow(
            """INSERT INTO watch_videos (slug, title, github_path, r2_key, file_type, file_size, contact_id, campaign_id)
               VALUES ($1, $2, NULL, $3, $4, $5, $6, $7)
               ON CONFLICT (slug) DO UPDATE
                 SET title = $2, github_path = NULL, r2_key = $3, file_type = $4, file_size = $5, contact_id = $6
               RETURNING slug, title, r2_key, file_type, file_size, contact_id, created_at""",
            safe_slug, (title or "").strip() or safe_slug, r2_key, content_type, file_size, contact_id, campaign_id,
        )
    _video_cache.pop(safe_slug, None)
    return {
        "slug": row["slug"],
        "watch_url": public_watch_url(row["slug"]),
        "file_url": f"{_DASHBOARD_URL}/watch/{row['slug']}/file",
    }


async def _log_view_event(source: str, content_key: str, contact_id: str | None, event_type: str):
    """Direct insert (not an HTTP round-trip to /track/view-event) since
    this runs server-side, in the same request that already knows
    contact_id — see content_tracking.py's content_view_events table.
    Never raises; a tracking bug must never break serving the video."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO content_view_events (source, content_key, contact_id, event_type) "
                "VALUES ($1, $2, $3, $4)",
                source, content_key, contact_id, event_type,
            )
    except Exception as e:
        print(f"[watch] failed to log view event for {content_key}: {e}")


@router.get("/watch/{slug}", response_class=HTMLResponse, include_in_schema=False)
async def watch_page(slug: str, request: Request):
    import integrations
    from merge_fields import first_name_from_owner

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT w.title, w.contact_id, c.owner, c.business
               FROM watch_videos w LEFT JOIN contacts c ON c.id = w.contact_id
               WHERE w.slug = $1""",
            slug,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Video not found")

    await _log_view_event("outreach_video", slug, row["contact_id"], "view")

    title = html.escape(row["title"] or "A video for you")
    # Links on the page stay on whichever domain the prospect arrived on.
    if _is_watch_host(request):
        video_url, page_url = f"{PUBLIC_VIDEO_BASE}/{slug}/file", f"{PUBLIC_VIDEO_BASE}/{slug}"
    else:
        video_url, page_url = f"{_DASHBOARD_URL}/watch/{slug}/file", f"{_DASHBOARD_URL}/watch/{slug}"
    # Personalized header + booking button (only when the video is tied to a
    # contact — generic uploads keep the bare player).
    heading = ""
    if row["contact_id"] and (row["owner"] or row["business"]):
        first = html.escape(first_name_from_owner(row["owner"])) if row["owner"] else "there"
        biz = html.escape(row["business"] or "your practice")
        heading = f'<h1>Hey {first}, I made this for {biz}</h1>'
    book_url = html.escape(integrations.CALENDLY_URL)

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>{title}</title>
<meta property="og:type" content="video.other">
<meta property="og:title" content="{title}">
<meta property="og:url" content="{page_url}">
<meta property="og:video" content="{video_url}">
<meta property="og:video:secure_url" content="{video_url}">
<meta property="og:video:type" content="video/mp4">
<meta property="og:video:width" content="1920">
<meta property="og:video:height" content="1080">
<meta name="twitter:card" content="player">
<meta name="twitter:player:stream" content="{video_url}">
<style>
  html, body {{ margin: 0; padding: 0; background: #090f26; min-height: 100%; }}
  body {{ display: flex; flex-direction: column; align-items: center; justify-content: center;
          gap: 18px; padding: 24px 16px; box-sizing: border-box; min-height: 100vh;
          font-family: -apple-system, 'Segoe UI', Roboto, sans-serif; color: #f0f4ff; }}
  h1 {{ font-size: clamp(20px, 3.2vw, 30px); font-weight: 600; margin: 0; text-align: center; }}
  video {{ width: 100%; max-width: 1100px; max-height: 70vh; border-radius: 10px; background: #000; }}
  .book {{ display: inline-block; padding: 14px 28px; border-radius: 8px; font-weight: 600; font-size: 16px;
           color: #fff; text-decoration: none; background: linear-gradient(90deg, #2857a0, #3a7bd5); }}
</style>
</head>
<body>
{heading}
<video id="v" src="{video_url}" controls playsinline></video>
<a class="book" id="book" href="{book_url}" target="_blank" rel="noopener">Book a call</a>
<script>
(function() {{
  // Beacons play/25%/50%/75%/complete for this outreach video — same
  // event set and endpoint the website VSL reports into. Won't fire for
  // an SMS/iMessage inline preview that plays straight from the og:video
  // URL without ever loading this page — that's caught server-side
  // instead, see watch_file()'s own view log.
  var video = document.getElementById('v');
  var fired = {{}};
  function track(eventType) {{
    if (fired[eventType]) return;
    fired[eventType] = true;
    var payload = JSON.stringify({{source: 'outreach_video', content_key: '{slug}', event_type: eventType}});
    // A plain-string sendBeacon body defaults to Content-Type: text/plain,
    // which the backend's dict-body parsing rejected with a 422 — wrap it
    // in a Blob so the browser sends application/json instead.
    navigator.sendBeacon('/track/view-event', new Blob([payload], {{type: 'application/json'}}));
  }}
  video.addEventListener('play', function() {{ track('play'); }});
  video.addEventListener('timeupdate', function() {{
    if (!video.duration) return;
    var pct = video.currentTime / video.duration;
    if (pct >= 0.75) track('progress_75');
    else if (pct >= 0.5) track('progress_50');
    else if (pct >= 0.25) track('progress_25');
  }});
  video.addEventListener('ended', function() {{ track('complete'); }});
  document.getElementById('book').addEventListener('click', function() {{ track('book_click'); }});
}})();
</script>
</body>
</html>""")


@router.get("/watch/{slug}/file", include_in_schema=False)
async def watch_file(slug: str, request: Request):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT github_path, r2_key, file_type, contact_id FROM watch_videos WHERE slug = $1", slug
        )
    if not row:
        raise HTTPException(status_code=404, detail="Video not found")

    range_header = request.headers.get("range")

    # Catches the case where an SMS/iMessage rich preview plays straight
    # from the og:video URL without ever loading watch_page()'s HTML (so
    # that route's own view log never fires) — logged here instead, but
    # only on the initial fetch (no Range, or Range starting at byte 0),
    # not on every mid-playback seek chunk. Harmless if watch_page() ALSO
    # logged a view for this same visit — the funnel query counts DISTINCT
    # contacts, so a duplicate row here doesn't inflate anything.
    is_initial_request = not range_header or range_header.strip().split("=", 1)[-1].startswith("0-")
    if is_initial_request:
        await _log_view_event("outreach_video", slug, row["contact_id"], "view")

    if row["r2_key"]:
        # R2-backed (every upload since the 2026-09-04 migration — see this
        # module's docstring): redirect straight to a freshly presigned GET
        # URL and let R2 handle Range requests itself. This backend never
        # buffers the video bytes at all, which is the whole point — no more
        # OOM risk from large files. Presigned fresh on every request, so
        # its short expiry (r2_storage._PRESIGN_EXPIRES_SECONDS) never
        # matters — this /file URL itself is the permanent, stable link
        # that goes out in texts and og:video tags.
        get_url = r2_storage.presign_get(row["r2_key"])
        return RedirectResponse(get_url, status_code=302)

    # Legacy GitHub-backed row (published before the R2 migration).
    content = _video_cache.get(slug)
    file_type = row["file_type"] or "video/mp4"
    if content is None:
        content = _gh_fetch(row["github_path"])
        _video_cache[slug] = content
    file_size = len(content)

    if range_header:
        try:
            range_val = range_header.strip().split("=", 1)[1]
            start_str, end_str = range_val.split("-", 1)
            start = int(start_str) if start_str else 0
            end = int(end_str) if end_str else file_size - 1
            end = min(end, file_size - 1)
        except (IndexError, ValueError):
            start, end = 0, file_size - 1
        chunk = content[start:end + 1]
        return Response(
            content=chunk,
            status_code=206,
            media_type=file_type,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(len(chunk)),
            },
        )

    return Response(
        content=content,
        media_type=file_type,
        headers={"Accept-Ranges": "bytes", "Content-Length": str(file_size)},
    )
