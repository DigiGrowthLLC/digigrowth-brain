import sys
import subprocess
import pathlib
import asyncio
import time

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Installing playwright...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright"])
    subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
    from playwright.async_api import async_playwright

WIDTH, HEIGHT = 1920, 1080

# Static capture — holds the top of the page for the full duration. A prior
# auto-scrolling version was replaced per explicit feedback: the scroll motion
# read as unnatural. Do not reintroduce scrolling without being asked.


async def record(url, duration_seconds, out_dir):
    duration_ms = int(duration_seconds * 1000)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": WIDTH, "height": HEIGHT},
            record_video_dir=str(out_dir),
            record_video_size={"width": WIDTH, "height": HEIGHT},
        )
        page = await context.new_page()
        # Video recording starts the instant this page is created, before
        # goto() even begins — so the raw capture always opens on a blank
        # white frame while the page loads. Rather than fight Playwright to
        # not record that, measure how long it actually took and trim it off
        # in post (see main()) so the delivered clip opens on the loaded page.
        start = time.monotonic()
        await page.goto(url, wait_until="load", timeout=30000)
        try:
            await page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass  # some sites never go idle (chat widgets, polling) — settle buffer below covers it
        await page.wait_for_timeout(400)
        skip_seconds = time.monotonic() - start
        await page.wait_for_timeout(duration_ms)
        video = page.video
        await context.close()
        await browser.close()
        return await video.path(), skip_seconds


def main():
    if len(sys.argv) < 4:
        print("Usage: python record_site_scroll.py <url> <duration_seconds> <output.mp4>")
        sys.exit(1)

    url = sys.argv[1]
    duration = float(sys.argv[2])
    out_path = pathlib.Path(sys.argv[3])
    out_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_dir = out_path.parent / f".{out_path.stem}-raw"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    webm_path, skip_seconds = asyncio.run(record(url, duration, tmp_dir))

    # -ss after -i for accurate (not keyframe-snapped) seeking, since we need
    # the trim point exact — this is what cuts the blank loading frame(s) out.
    subprocess.check_call([
        "ffmpeg", "-y", "-i", webm_path,
        "-ss", f"{skip_seconds:.3f}", "-t", str(duration),
        "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
        "-an", str(out_path),
    ])

    print(f"Saved site-scroll capture: {out_path}")


if __name__ == "__main__":
    main()
