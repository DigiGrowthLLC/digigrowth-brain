"""Server-side personalized outreach video ("Loom") generator for the Email
Handoff sequence's {loom} merge field.

The outreach-video skill (content-agent/.claude/skills/outreach-video/) makes
the same video on Dylan's PC, which only works while that PC is on. This is
the always-on port, running inside the Railway container (ffmpeg + headless
Chromium are installed in dashboard/Dockerfile):

  1. Screenshot the prospect's website at 1920x1080, top of page. The skill's
     locked format is a STATIC top-of-page background (scrolling was scrapped),
     so a single screenshot looped for the clip's length renders the same as
     the skill's screen recording, at a fraction of the cost.
  2. ffmpeg: loop the screenshot as the background, overlay Dylan's headcam
     master clip as the same 320px circle bubble bottom-left (same filter as
     content-agent/tools/compose_outreach_video.py), headcam audio only.
  3. Upload to R2 and register a /watch/<slug> page tied to the contact, so
     it shows in the Loom Outreach analytics funnel like skill-made videos.

No website on file, or the site won't load/render: publish the headcam clip
alone (same rule as the skill's Send Info Queue Mode).

The headcam master lives in R2 at HEADCAM_R2_KEY (uploaded once from
content-agent/raw/headcam-master.mp4 — re-upload there if Dylan re-records),
cached on local disk per container.

Entry point: process_next() on an APScheduler interval (main.py). One video
at a time; email_handoff_sequence.py holds any touch that uses {loom} until
the prospect's loom_url is set (or LOOM_MAX_ATTEMPTS generations fail).
"""
import asyncio
import os
import re
import shutil
import tempfile
from datetime import date
from pathlib import Path

import r2_storage
from db import get_pool

HEADCAM_R2_KEY = "assets/headcam-master.mp4"
_HEADCAM_CACHE = Path(tempfile.gettempdir()) / "headcam-master.mp4"

WIDTH, HEIGHT = 1920, 1080
BUBBLE_SIZE = 320
MARGIN = 40
CROP_X_SHIFT = 0  # keep in sync with compose_outreach_video.py

# A claimed row whose run crashed mid-way (container restart) is retried
# after this long.
_CLAIM_TIMEOUT_MINUTES = 30

_lock = asyncio.Lock()


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:50] or "prospect"


async def _ensure_headcam() -> Path:
    if not _HEADCAM_CACHE.exists():
        tmp = _HEADCAM_CACHE.with_suffix(".part")
        await asyncio.to_thread(r2_storage.download_file, HEADCAM_R2_KEY, str(tmp))
        tmp.replace(_HEADCAM_CACHE)
    return _HEADCAM_CACHE


async def _run(*cmd: str, timeout: int) -> None:
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError(f"{cmd[0]} timed out after {timeout}s")
    if proc.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed: {stderr.decode(errors='replace')[-500:]}")


async def _duration(path: Path) -> float:
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
    )
    out, _ = await proc.communicate()
    return float(out.decode().strip())


async def _screenshot(url: str, out_png: Path) -> None:
    from playwright.async_api import async_playwright

    if not re.match(r"^https?://", url):
        url = f"https://{url}"
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            page = await browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
            await page.goto(url, wait_until="load", timeout=30000)
            try:
                await page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass  # chat widgets/polling never go idle — the settle buffer below covers it
            await page.wait_for_timeout(1500)
            await page.screenshot(path=str(out_png))
        finally:
            await browser.close()


async def _compose(headcam: Path, background_png: Path, out: Path) -> None:
    duration = await _duration(headcam)
    r = BUBBLE_SIZE // 2
    filter_complex = (
        f"[0:v]scale={WIDTH}:{HEIGHT},format=yuv420p[bg];"
        f"[1:v]scale={BUBBLE_SIZE}:{BUBBLE_SIZE}:force_original_aspect_ratio=increase,"
        f"crop={BUBBLE_SIZE}:{BUBBLE_SIZE}:(iw-{BUBBLE_SIZE})/2+{CROP_X_SHIFT}:(ih-{BUBBLE_SIZE})/2,"
        f"format=yuva420p,"
        f"geq=lum='p(X,Y)':a='if(gt(pow(X-{r},2)+pow(Y-{r},2),{r}*{r}),0,255)'[circle];"
        f"[bg][circle]overlay={MARGIN}:H-h-{MARGIN}[outv]"
    )
    await _run(
        "ffmpeg", "-y",
        "-loop", "1", "-framerate", "30", "-i", str(background_png),
        "-i", str(headcam),
        "-filter_complex", filter_complex,
        "-map", "[outv]", "-map", "1:a",
        "-t", f"{duration:.2f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
        "-threads", "2",
        "-c:a", "aac",
        "-movflags", "+faststart",
        str(out),
        timeout=900,
    )


async def generate(contact: dict, track: bool = True) -> tuple[str, str]:
    """Builds + publishes one prospect's video; returns (watch URL, mode) —
    mode is "site" (composited over their website) or "headcam-only" (no
    site on file, or the site capture/composite failed).
    Raises only if even the headcam-only fallback can't be published.
    track=False (test sends) gives the video a "-test" link so it never
    takes a real prospect's slug; it's still tied to the contact (for the
    personalized page), and test-status contacts are excluded from the Loom
    Outreach funnel (content_tracking.py)."""
    from routers.watch import register_watch_video

    headcam = await _ensure_headcam()
    workdir = Path(tempfile.mkdtemp(prefix="loom-"))
    try:
        video, mode = headcam, "headcam-only"  # fallback: headcam clip alone
        website = (contact.get("website") or "").strip()
        if website:
            try:
                png = workdir / "site.png"
                await _screenshot(website, png)
                composed = workdir / "video.mp4"
                await _compose(headcam, png, composed)
                video, mode = composed, "site"
            except Exception as e:
                print(f"[outreach_video] site composite failed for {website} ({e}) — using headcam-only fallback")

        slug = await _pick_slug(contact, track)
        r2_key = f"watch/{slug}.mp4"
        await asyncio.to_thread(r2_storage.upload_file, str(video), r2_key, "video/mp4")
        registered = await register_watch_video(
            slug, contact.get("business") or slug, r2_key, video.stat().st_size, "video/mp4",
            str(contact["id"]),
        )
        return registered["watch_url"], mode
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


# Paths the watch subdomain uses itself — never handed out as a prospect slug.
_RESERVED_SLUGS = {"track", "watch", "api", "assets", "robots-txt", "favicon-ico", "test"}


async def _pick_slug(contact: dict, track: bool) -> str:
    """Prospect-name link: watch.digigrowthllc.com/janice-bacak. Falls back
    to the business name when no owner is on file; on a clash with a
    different contact's video, adds the business, then a number. A contact
    re-generating keeps (overwrites) their own slug. Test sends get a
    "-test" suffix so they never take a real prospect's link."""
    import email_handoff_sequence as ehs_mod

    base = _slugify(ehs_mod.full_name(contact))
    if track is False:
        return f"{base}-test"
    candidates = [base, f"{base}-{_slugify(contact.get('business'))}"[:80]]
    candidates += [f"{base}-{n}" for n in range(2, 50)]
    pool = await get_pool()
    async with pool.acquire() as conn:
        for slug in candidates:
            if slug in _RESERVED_SLUGS:
                continue
            owner = await conn.fetchrow("SELECT contact_id FROM watch_videos WHERE slug = $1", slug)
            if owner is None or owner["contact_id"] == str(contact["id"]):
                return slug
    return f"{base}-{str(contact['id'])[:8]}"


def _needs_loom(row: dict, templates: dict) -> bool:
    import email_handoff_sequence as ehs_mod

    """Only build a video when a touch this prospect hasn't received yet
    actually uses {loom} — no point rendering for someone whose remaining
    touches never show it."""
    for instance, sent_col in (("touch1", "touch1_sent_at"), ("touch2", "touch2_sent_at"), ("touch3", "touch3_sent_at")):
        if row.get(sent_col) is None:
            text = templates[f"email_handoff_{instance}_subject"] + templates[f"email_handoff_{instance}_body"]
            if ehs_mod.uses_loom(text):
                return True
    return False


async def process_next() -> None:
    """APScheduler entrypoint — generates at most one pending video per run.
    Never raises (a bad run must not kill the scheduler)."""
    import email_handoff_sequence as ehs_mod

    if _lock.locked():
        return
    async with _lock:
        try:
            templates = await ehs_mod._get_templates()
            if not any(ehs_mod.uses_loom(v) for v in templates.values()):
                return
            pool = await get_pool()
            async with pool.acquire() as conn:
                candidates = await conn.fetch(
                    f"""
                    SELECT ehs.*, c.id, c.business, c.owner, c.website
                    FROM email_handoff_state ehs
                    JOIN contacts c ON c.id = ehs.contact_id
                    WHERE c.status = $1 AND NOT c.email_opted_out AND ehs.stopped_at IS NULL
                      AND ehs.touch3_sent_at IS NULL AND ehs.loom_url IS NULL
                      AND ehs.loom_attempts < $2
                      AND (ehs.loom_started_at IS NULL
                           OR ehs.loom_started_at < now() - interval '{_CLAIM_TIMEOUT_MINUTES} minutes')
                    ORDER BY ehs.enrolled_at
                    LIMIT 50
                    """,
                    ehs_mod.EMAIL_HANDOFF_STATUS, ehs_mod.LOOM_MAX_ATTEMPTS,
                )
                row = next((dict(r) for r in candidates if _needs_loom(dict(r), templates)), None)
                if not row:
                    return
                await conn.execute(
                    "UPDATE email_handoff_state SET loom_started_at = now() WHERE contact_id = $1",
                    row["contact_id"],
                )

            try:
                watch_url, mode = await generate(row)
            except Exception as e:
                async with pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE email_handoff_state SET loom_attempts = loom_attempts + 1, loom_error = $2, "
                        "loom_started_at = NULL WHERE contact_id = $1",
                        row["contact_id"], str(e)[:500],
                    )
                print(f"[outreach_video] generation failed for {row.get('business')}: {e}")
                return

            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE email_handoff_state SET loom_url = $2, loom_error = NULL WHERE contact_id = $1",
                    row["contact_id"], watch_url,
                )
            print(f"[outreach_video] ready ({mode}) for {row.get('business')}: {watch_url}")
        except Exception as e:
            print(f"[outreach_video] process_next error: {e}")
