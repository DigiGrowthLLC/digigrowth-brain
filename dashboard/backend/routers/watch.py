"""
Public video watch pages — no auth required.
A prospect clicks a texted link (https://<dashboard>/watch/<slug>) and gets an
inline video player with Open Graph video tags for SMS/iMessage rich previews.
Upload is authenticated (mounted under /api with require_auth in main.py);
serving is public, scoped only by an unguessable slug — same pattern as
routers/client_portal.py.
"""
import base64
import html
import json
import os
import time
import urllib.error
import urllib.request

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, Response

from db import get_pool

router = APIRouter()          # public: /watch/{slug}, /watch/{slug}/file
admin_router = APIRouter()    # authenticated: /watch-videos (upload)

_GITHUB_REPO = os.environ.get("GITHUB_REPO", "dylangroenendijk-sys/digigrowth-brain")
_DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "https://digigrowth-brain-production.up.railway.app").rstrip("/")
_MAX_UPLOAD_BYTES = 95 * 1024 * 1024  # under GitHub's 100 MB Contents API limit

# In-memory cache of fetched video bytes, keyed by slug — video players issue
# many Range requests while seeking; without this every seek would re-hit the
# GitHub API for the full file. Process-lifetime only, not persistence.
_video_cache: dict[str, bytes] = {}


def _gh_push(path: str, data: bytes, message: str) -> None:
    token = os.environ.get("GIT_TOKEN", "")
    if not token:
        raise HTTPException(status_code=500, detail="GIT_TOKEN not configured")
    url = f"https://api.github.com/repos/{_GITHUB_REPO}/contents/{path}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }
    sha = None
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            sha = json.loads(resp.read()).get("sha")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise HTTPException(status_code=502, detail=f"GitHub error: {e}")
    payload: dict = {"message": message, "content": base64.b64encode(data).decode()}
    if sha:
        payload["sha"] = sha
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=60):
            pass
    except urllib.error.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"GitHub push failed: {e}")


def _gh_fetch(path: str) -> bytes:
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


@admin_router.post("/watch-videos")
async def upload_watch_video(
    file: UploadFile = File(...),
    slug: str = Form(...),
    title: str = Form(""),
):
    data = await file.read()
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 95 MB limit")

    safe_slug = "".join(c if c.isalnum() or c in "-_" else "-" for c in slug.strip().lower())
    if not safe_slug:
        raise HTTPException(status_code=400, detail="Invalid slug")

    file_type = file.content_type or "video/mp4"
    file_size = len(data)
    github_path = f"dashboard/backend/watch_uploads/{safe_slug}.mp4"
    _gh_push(github_path, data, f"Outreach video: {safe_slug}")

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO watch_videos (slug, title, github_path, file_type, file_size)
               VALUES ($1, $2, $3, $4, $5)
               ON CONFLICT (slug) DO UPDATE
                 SET title = $2, github_path = $3, file_type = $4, file_size = $5
               RETURNING slug, title, github_path, file_type, file_size, created_at""",
            safe_slug, title.strip() or safe_slug, github_path, file_type, file_size,
        )
    _video_cache.pop(safe_slug, None)
    return {
        "slug": row["slug"],
        "watch_url": f"{_DASHBOARD_URL}/watch/{row['slug']}",
        "file_url": f"{_DASHBOARD_URL}/watch/{row['slug']}/file",
    }


@router.get("/watch/{slug}", response_class=HTMLResponse, include_in_schema=False)
async def watch_page(slug: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT title FROM watch_videos WHERE slug = $1", slug)
    if not row:
        raise HTTPException(status_code=404, detail="Video not found")

    title = html.escape(row["title"] or "A video for you")
    video_url = f"{_DASHBOARD_URL}/watch/{slug}/file"
    page_url = f"{_DASHBOARD_URL}/watch/{slug}"

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
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
  html, body {{ margin: 0; padding: 0; background: #090f26; height: 100%; }}
  body {{ display: flex; align-items: center; justify-content: center; }}
  video {{ max-width: 100vw; max-height: 100vh; width: 100%; }}
</style>
</head>
<body>
<video src="{video_url}" controls playsinline></video>
</body>
</html>""")


@router.get("/watch/{slug}/file", include_in_schema=False)
async def watch_file(slug: str, request: Request):
    content = _video_cache.get(slug)
    file_type = "video/mp4"
    if content is None:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT github_path, file_type FROM watch_videos WHERE slug = $1", slug
            )
        if not row:
            raise HTTPException(status_code=404, detail="Video not found")
        file_type = row["file_type"] or "video/mp4"
        content = _gh_fetch(row["github_path"])
        _video_cache[slug] = content

    file_size = len(content)
    range_header = request.headers.get("range")

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
