"""
Builds a Patient Acquisition Blueprint page (design-agent's
patient-acquisition-blueprint skill) from references/blueprint-template.html
plus a per-prospect blueprint.json that Claude writes during the skill run.

The template owns the fixed machinery (engine flow diagram, live chat widget,
layout, motion). This script only fills it: escapes text, compresses and
inlines the ad images and logo as data: URIs, and embeds the funnel preview
(a standalone HTML document) as an iframe srcdoc so its CSS can't collide
with the shell's.

Usage: python build_blueprint.py <blueprint.json> <out_dir>
Writes <out_dir>/page.html and <out_dir>/chat_context.txt, and prints a
summary plus any warnings (leftover placeholders, non-GSM-7 characters in the
SMS examples, page weight).

blueprint.json shape (paths are relative to the json file's folder):
{
  "slug": "peak-motion-pt-blueprint",
  "business": "Peak Motion Physical Therapy",
  "business_short": "Peak Motion",
  "brand": {"primary": "#0f766e", "primary_text": "#ffffff", "avatar_bg": "#ffffff"},
  "logo": "data:image/png;base64,..." | "logo.png" | null,
  "hero": {"headline": "... *gradient words* ...", "subhead": "..."},
  "engine_intro": "...",
  "step_blurbs": ["ads", "funnel", "agent", "recovery"],
  "ads": {"headline": "...", "intro": "...", "items": [
     {"image": "ads/ad1.png", "hook": "...", "primary_text": "...",
      "headline": "...", "cta": "Book Now", "angle": "Top of funnel: ..."}]},
  "funnel": {"headline": "...", "intro": "...", "points": ["..."], "html_file": "funnel.html"},
  "agent": {"headline": "...", "intro": "...", "points": ["..."],
            "greeting": "...", "chips": ["...", "...", "..."]},
  "recovery": {"headline": "...", "intro": "...", "items": [
     {"icon": "📞", "label": "Missed call text-back", "when": "...",
      "messages": [{"from": "practice", "text": "..."}, {"from": "lead", "text": "..."}]}]},
  "close_intro": "...",
  "chat_context": "facts the demo agent may use, from the scrape"
}
"""
import base64
import html
import io
import json
import pathlib
import re
import sys

from PIL import Image

TEMPLATE = pathlib.Path(__file__).resolve().parent.parent / "references" / "blueprint-template.html"
GSM7_BAD = re.compile(r"[–—‘’“”…]|[\U0001F000-\U0001FFFF]")


def esc(s) -> str:
    return html.escape(str(s or ""), quote=True)


def rich(s) -> str:
    """Escape, then turn *words* into the shell's gradient accent span."""
    return re.sub(r"\*(.+?)\*", r'<span class="grad">\1</span>', esc(s))


def image_data_uri(path: pathlib.Path, width: int = 720, quality: int = 80) -> str:
    im = Image.open(path).convert("RGB")
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=quality, optimize=True, progressive=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def logo_src(logo, base: pathlib.Path) -> str | None:
    if not logo:
        return None
    if str(logo).startswith("data:"):
        return logo
    p = base / logo
    mime = "image/svg+xml" if p.suffix.lower() == ".svg" else "image/png"
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()


def initials(name: str) -> str:
    return "".join(w[0] for w in name.split()[:2]).upper() or "PT"


def main():
    if len(sys.argv) != 3:
        print("Usage: python build_blueprint.py <blueprint.json> <out_dir>")
        sys.exit(1)
    src = pathlib.Path(sys.argv[1]).resolve()
    base = src.parent
    out = pathlib.Path(sys.argv[2]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    d = json.loads(src.read_text(encoding="utf-8"))
    warnings = []

    business = d["business"]
    short = d.get("business_short") or business
    logo = logo_src(d.get("logo"), base)
    logo_img = f'<img src="{logo}" alt="{esc(business)}">' if logo else ""

    ad_avatar = logo_img or esc(initials(business))
    ads_html = []
    for ad in d["ads"]["items"]:
        img = image_data_uri(base / ad["image"])
        hook = f'<div class="ad-hook">{esc(ad["hook"])}</div>' if ad.get("hook") else ""
        ads_html.append(f"""<div class="reveal"><div class="ad">
  <div class="ad-top"><div class="ad-av">{ad_avatar}</div><div><div class="ad-name">{esc(business)}</div><div class="ad-sp">Sponsored · 🌐</div></div></div>
  <div class="ad-copy">{esc(ad["primary_text"])}</div>
  <div class="ad-img"><img src="{img}" alt="">{hook}</div>
  <div class="ad-foot"><div><div class="u">{esc(d.get("domain") or short)}</div><div class="h">{esc(ad["headline"])}</div></div><div class="ad-btn">{esc(ad.get("cta") or "Book Now")}</div></div>
</div><div class="ad-angle">{esc(ad.get("angle_label") or "Angle")}: <b>{esc(ad.get("angle"))}</b></div></div>""")

    funnel_doc = (base / d["funnel"]["html_file"]).read_text(encoding="utf-8")

    rec_html = []
    for item in d["recovery"]["items"]:
        bubbles = []
        for m in item["messages"]:
            if GSM7_BAD.search(m["text"]):
                warnings.append(f'non-GSM-7 character in SMS example "{item["label"]}": {m["text"][:50]}...')
            cls = "sms in" if m.get("from") == "lead" else "sms"
            bubbles.append(f'<div class="{cls}">{esc(m["text"])}</div>')
        rec_html.append(f"""<div class="rc glass reveal"><div class="lab"><span class="ic">{esc(item.get("icon") or "↺")}</span>{esc(item["label"])}</div>
<div class="when">{esc(item.get("when"))}</div>{"".join(bubbles)}</div>""")

    li = lambda pts: "".join(f"<li>{esc(p)}</li>" for p in pts)
    blurbs = d["step_blurbs"]
    fills = {
        "BUSINESS": esc(business),
        "BUSINESS_SHORT": esc(short),
        "BRAND_PRIMARY": esc(d["brand"]["primary"]),
        "BRAND_PRIMARY_TEXT": esc(d["brand"].get("primary_text") or "#ffffff"),
        # Behind the logo in the round chat/ad avatars: match the logo's own
        # background (a logo cut from a dark header needs a dark circle).
        "BRAND_AVATAR_BG": esc(d["brand"].get("avatar_bg") or "#ffffff"),
        "LOGO_LOCKUP": logo_img or f'<span class="dg">{esc(business)}</span>',
        "HERO_HEADLINE": rich(d["hero"]["headline"]),
        "HERO_SUBHEAD": esc(d["hero"]["subhead"]),
        "ENGINE_INTRO": esc(d["engine_intro"]),
        "STEP1_BLURB": esc(blurbs[0]), "STEP2_BLURB": esc(blurbs[1]),
        "STEP3_BLURB": esc(blurbs[2]), "STEP4_BLURB": esc(blurbs[3]),
        "ADS_HEADLINE": esc(d["ads"]["headline"]), "ADS_INTRO": esc(d["ads"]["intro"]),
        "ADS_HTML": "".join(ads_html),
        "FUNNEL_HEADLINE": esc(d["funnel"]["headline"]), "FUNNEL_INTRO": esc(d["funnel"]["intro"]),
        "FUNNEL_POINTS": li(d["funnel"]["points"]),
        "FUNNEL_SRCDOC": html.escape(funnel_doc, quote=True),
        "AGENT_HEADLINE": esc(d["agent"]["headline"]), "AGENT_INTRO": esc(d["agent"]["intro"]),
        "AGENT_POINTS": li(d["agent"]["points"]),
        "CHAT_AVATAR": logo_img or esc(initials(business)),
        "CHAT_CHIPS": "".join(f'<button type="button" class="chip">{esc(c)}</button>' for c in d["agent"]["chips"]),
        "RECOVERY_HEADLINE": esc(d["recovery"]["headline"]), "RECOVERY_INTRO": esc(d["recovery"]["intro"]),
        "RECOVERY_HTML": "".join(rec_html),
        "CLOSE_INTRO": esc(d["close_intro"]),
        # JSON inside <script>: escape "</" so page text can't close the tag.
        "SLUG_JSON": json.dumps(d["slug"]).replace("</", "<\\/"),
        "CHAT_GREETING_JSON": json.dumps(d["agent"]["greeting"]).replace("</", "<\\/"),
    }

    page = TEMPLATE.read_text(encoding="utf-8")
    page = re.sub(r"\{\{([A-Z0-9_]+)\}\}", lambda m: fills.get(m.group(1), m.group(0)), page)
    left = sorted(set(re.findall(r"\{\{([A-Z0-9_]+)\}\}", page)))
    if left:
        warnings.append(f"unfilled placeholders: {', '.join(left)}")

    (out / "page.html").write_text(page, encoding="utf-8")
    (out / "chat_context.txt").write_text(d["chat_context"].strip() + "\n", encoding="utf-8")

    kb = len(page.encode("utf-8")) / 1024
    if kb > 2500:
        warnings.append(f"page is {kb:.0f} KB, heavy for a texted link; shrink the funnel's embedded photos")
    print(f"Built {out / 'page.html'} ({kb:.0f} KB), {len(ads_html)} ads, {len(rec_html)} recovery cards")
    print(f"Chat context: {out / 'chat_context.txt'} ({len(d['chat_context'])} chars)")
    for w in warnings:
        print(f"WARNING: {w}")


if __name__ == "__main__":
    main()
