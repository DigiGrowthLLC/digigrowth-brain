"""
Fresh scrape of a prospect's real website for the landing-page-mockup skill.

Deliberately separate from leadgen-agent/lib.py's scrape_website_full: that
scrape exists only to produce one throwaway opener sentence and discards
everything else. This tool keeps the actual extracted text (services, hours,
about-page content, testimonials/reviews if the site has them) and adds real
visual material, since the landing page needs to be built FROM their actual
site — real copy, real colors, real photos, real reviews — not a wireframe
with their name pasted in.

What happens here (mechanical fetching only — Claude does the actual
reading/writing/design reasoning downstream, this script just gathers real
material):
  1. requests+BeautifulSoup text pass over the homepage + a few common
     subpages (about, services, contact) — broader than leadgen's pass,
     text is kept in full (not truncated to a handful of words), so real
     testimonials/reviews on the page survive into page_text.txt.
  2. A Playwright static screenshot of the homepage (held-frame, no scroll —
     same technique content-agent/tools/record_site_scroll.py uses for
     video, just a single screenshot() call instead of a video recording).
  3. Real brand color extraction from the actual COMPUTED CSS of the
     rendered page (button bg/text, header bg, heading color) — not a guess,
     not just <meta name="theme-color"> (rarely set).
  4. Real photo/logo capture — finds the logo plus a handful of real content
     photos (hero image, team/about photos) actually rendered on the page,
     downloads them, and embeds them as base64 data: URIs directly, so the
     generated page never hotlinks the prospect's CDN (fragile — some block
     hotlinking by referrer — and the Claude Artifact preview used for
     Dylan's approval step blocks external image loads outright via CSP).

Usage: python scrape_prospect_site.py <url> <output_dir>
Writes hero.png, page_text.txt, palette.json, and assets.json
(assets.json: {"logo": "data:...;base64,..." | null, "photos": ["data:...", ...]})
to <output_dir>, and prints a summary.
"""
import sys
import subprocess
import pathlib
import asyncio
import re
import json
import base64
import mimetypes

import requests
from bs4 import BeautifulSoup

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Installing playwright...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright"])
    subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
    from playwright.async_api import async_playwright

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; DigiGrowthDesignAgent/1.0)"}
_SUBPAGES = ["", "/about", "/about-us", "/services", "/contact"]
WIDTH, HEIGHT = 1440, 1600  # tall viewport — capture more of the page in one still, not just the fold
_MAX_PHOTOS = 4

# Runs in-page. Samples computed styles and real image URLs off currently-
# rendered elements rather than guessing from source CSS/markup — this is
# what the browser actually shows, colors and photos in hand.
_CAPTURE_JS = """
(maxPhotos) => {
  function rgb(el) {
    if (!el) return null;
    const cs = getComputedStyle(el);
    return { bg: cs.backgroundColor, color: cs.color };
  }
  function firstMatch(selectors) {
    for (const sel of selectors) {
      const el = document.querySelector(sel);
      if (el) return el;
    }
    return null;
  }
  const button = firstMatch([
    'a.button', 'a.btn', 'button', '[class*="button"]', '[class*="btn"]',
    'a[href*="book"]', 'a[href*="schedule"]', 'a[href*="appointment"]', 'a[href*="contact"]',
  ]);
  const header = firstMatch(['header', 'nav', '[class*="header"]', '[class*="nav"]']);
  const h1 = document.querySelector('h1');

  // A real logo is small (typically well under 100px tall) -- some
  // one-page marketing sites wrap the whole hero, background photo
  // included, in a semantic <header>, so "first img inside header" can
  // wrongly match a full-bleed hero photo instead of the actual wordmark.
  // Require logo-like dimensions; fall back to the unconstrained match
  // only if nothing reasonably-sized was found.
  function firstLogoMatch(selectors) {
    for (const sel of selectors) {
      for (const el of document.querySelectorAll(sel)) {
        const r = el.getBoundingClientRect();
        if (r.height > 0 && r.height < 100 && r.width < 400) return el;
      }
    }
    return firstMatch(selectors);
  }
  const logoImg = firstLogoMatch(['header img', 'nav img', '[class*="logo"] img', 'img[alt*="logo" i]']);
  const logoSrc = logoImg ? logoImg.src : null;

  // Real content photos: rendered reasonably large, visible, not the logo,
  // not obviously an icon/sprite. Dedup by src, cap at maxPhotos.
  const seen = new Set(logoSrc ? [logoSrc] : []);
  const photos = [];
  for (const img of document.querySelectorAll('img')) {
    if (photos.length >= maxPhotos) break;
    const src = img.currentSrc || img.src;
    if (!src || seen.has(src)) continue;
    const r = img.getBoundingClientRect();
    if (r.width < 240 || r.height < 160) continue;  // skip icons/thumbnails
    seen.add(src);
    photos.push(src);
  }

  return {
    body: rgb(document.body),
    button: rgb(button),
    header: rgb(header),
    h1: h1 ? getComputedStyle(h1).color : null,
    logo_src: logoSrc,
    photo_srcs: photos,
    theme_color: (document.querySelector('meta[name="theme-color"]') || {}).content || null,
  };
}
"""


def scrape_text(base_url: str) -> str:
    base_url = base_url.rstrip("/")
    seen_urls = set()
    all_text = []

    for suffix in _SUBPAGES:
        page_url = base_url + suffix
        if page_url in seen_urls:
            continue
        seen_urls.add(page_url)
        try:
            res = requests.get(page_url, headers=HEADERS, timeout=8)
            if res.status_code != 200:
                continue
        except requests.RequestException:
            continue

        soup = BeautifulSoup(res.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        text = re.sub(r"\s+", " ", text)
        if text:
            all_text.append(f"[{suffix or '/'}] {text}")

    return "\n\n".join(all_text)


async def capture(url: str, screenshot_path: pathlib.Path) -> dict:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
        try:
            await page.goto(url, wait_until="load", timeout=30000)
            try:
                await page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass  # some sites never go idle (chat widgets, polling) — good enough after the wait below
            await page.wait_for_timeout(500)
            await page.screenshot(path=str(screenshot_path))
            data = await page.evaluate(_CAPTURE_JS, _MAX_PHOTOS)
        finally:
            await browser.close()
    return data


_MAX_PHOTO_WIDTH = 1100  # resize down to this before embedding — real site photography
_JPEG_QUALITY = 78       # is frequently several MB at full resolution, way too heavy
                         # for a page that needs to load fast off a cold-SMS tap.


def _fetch_as_data_uri(url: str, compress: bool = False) -> str | None:
    if not url:
        return None
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.raise_for_status()
    except requests.RequestException:
        return None
    content_type = res.headers.get("content-type", "").split(";")[0].strip()
    if not content_type or not content_type.startswith("image/"):
        content_type = mimetypes.guess_type(url)[0] or "image/png"

    content = res.content
    if compress:
        try:
            from PIL import Image
            import io as _io
            im = Image.open(_io.BytesIO(content)).convert("RGB")
            if im.width > _MAX_PHOTO_WIDTH:
                ratio = _MAX_PHOTO_WIDTH / im.width
                im = im.resize((_MAX_PHOTO_WIDTH, int(im.height * ratio)), Image.LANCZOS)
            buf = _io.BytesIO()
            im.save(buf, format="JPEG", quality=_JPEG_QUALITY, optimize=True)
            content = buf.getvalue()
            content_type = "image/jpeg"
        except Exception as e:
            print(f"WARNING: photo compression failed, embedding original ({e})")

    b64 = base64.b64encode(content).decode("ascii")
    return f"data:{content_type};base64,{b64}"


def main():
    if len(sys.argv) < 3:
        print("Usage: python scrape_prospect_site.py <url> <output_dir>")
        sys.exit(1)

    url = sys.argv[1]
    if not url.startswith("http"):
        url = "https://" + url
    out_dir = pathlib.Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)

    text = scrape_text(url)
    text_path = out_dir / "page_text.txt"
    text_path.write_text(text, encoding="utf-8")

    hero_path = out_dir / "hero.png"
    data = {}
    screenshot_ok = True
    try:
        data = asyncio.run(capture(url, hero_path))
    except Exception as e:
        print(f"WARNING: capture failed: {e}")
        screenshot_ok = False

    palette_path = out_dir / "palette.json"
    palette_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    print("Downloading and embedding real images as data URIs...")
    logo_data_uri = _fetch_as_data_uri(data.get("logo_src"))  # logos: keep crisp, usually small already
    photo_data_uris = [d for d in (_fetch_as_data_uri(u, compress=True) for u in data.get("photo_srcs", [])) if d]

    assets = {"logo": logo_data_uri, "photos": photo_data_uris}
    assets_path = out_dir / "assets.json"
    assets_path.write_text(json.dumps(assets, indent=2), encoding="utf-8")

    print(f"TEXT_FILE: {text_path}")
    print(f"TEXT_CHARS: {len(text)}")
    print(f"SCREENSHOT: {hero_path if screenshot_ok else 'FAILED'}")
    print(f"PALETTE_FILE: {palette_path}")
    print("PALETTE:")
    print(f"  button:  bg={data.get('button', {}).get('bg') if data.get('button') else 'none'}  "
          f"text={data.get('button', {}).get('color') if data.get('button') else 'none'}")
    print(f"  header:  bg={data.get('header', {}).get('bg') if data.get('header') else 'none'}")
    print(f"  h1 text: {data.get('h1') or 'none'}")
    print(f"  body bg: {data.get('body', {}).get('bg') if data.get('body') else 'none'}")
    print(f"  theme-color meta: {data.get('theme_color') or 'none'}")
    print(f"ASSETS_FILE: {assets_path}")
    print(f"  logo embedded:   {'yes' if logo_data_uri else 'no'}")
    print(f"  photos embedded: {len(photo_data_uris)} (of {len(data.get('photo_srcs', []))} candidates found)")
    print("  -> read assets.json and splice these data URIs directly into <img src=\"...\"> — don't re-fetch or hotlink.")


if __name__ == "__main__":
    main()
