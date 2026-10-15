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
  "package": "growth" | "foundations",   # foundations = back-end only: no ads, funnel or guarantee;
                                         # leave out "ads"/"funnel"/"close_intro", give 3 step_blurbs
                                         # (agent, reactivation, recovery) and an "included" block:
  "included": {"package_name": "Foundations", "label": "What's included", "headline": "... *accent* ...",
               "intro": "...", "price": "$500", "price_unit": "/month", "price_note": "... **bold** ...",
               "items": [{"icon": "bot", "title": "...", "text": "..."}]},
  "math": {"label": "The math", "headline": "...", "intro": "...", "note": "...", "price": 500,
           "reminder_cut": 0.33,   # share of no-shows text reminders prevent (cite it in stats)
           "stats": [{"num": "7x", "label": "...", "source": "...", "url": "https://..."}],
           "inputs": [{"k": "inquiries", "label": "...", "hint": "...", "value": 30, "prefix": "$", "suffix": "min"}]},
           # or fixed "outcomes": [{"k": "Time back", "v": "7.5 hrs", "s": "...", "how": "the math, **bold**", "highlight": true}]
  # funnel may also carry "label" ("Website"), "step_title", and "pages" (multi-page SEO site, see pages_html).
  "business": "Peak Motion Physical Therapy",
  "business_short": "Peak Motion",
  "brand": {"primary": "#0f766e", "primary_text": "#ffffff", "avatar_bg": "#ffffff"},
  "logo": "data:image/png;base64,..." | "logo.png" | null,
  "hero": {"headline": "... *gradient words* ...", "subhead": "..."},
  "engine_intro": "...",
  "step_blurbs": ["ads", "funnel", "agent", "database reactivation", "nothing leaks"],
  "ads": {"headline": "...", "intro": "...", "items": [
     {"image": "ads/ad1.png", "hook": "...", "primary_text": "...",
      "headline": "...", "cta": "Book Now", "angle_label": "Top of funnel", "angle": "..."}],
   "video_items": [{"video": "social/cut1.mp4", "poster_at": 1.5, "primary_text": "...",
      "headline": "...", "cta": "Learn More", "angle_label": "...", "angle": "..."}]},
  "funnel": {"headline": "...", "intro": "...", "points": ["..."], "html_file": "funnel.html",
             "url": "advantagetherapy.vegas/free-consult",
             "why": [{"icon": "target", "title": "...", "text": "..."}]},
  "agent": {"headline": "...", "intro": "...", "points": ["..."],
            "greeting": "...", "chips": ["...", "...", "..."]},
  "recovery": {"headline": "...", "intro": "...", "items": [
     {"icon": "phone", "label": "Missed call text-back", "when": "...",
      "messages": [{"from": "practice", "text": "..."}, {"from": "lead", "text": "..."}]}]},
  "reactivation": {"headline": "...", "intro": "...", "sms_when": "...",
      "sms": [{"from": "practice", "text": "..."}, {"from": "lead", "text": "..."}],
      "email_when": "...", "email": {"subject": "...", "body": "..."}},
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
import shutil
import subprocess
import sys
from datetime import date

from PIL import Image

CALC_HTML = """    <div class="stats">{stats}</div>
    <div class="calc card reveal">
      <div class="calc-in"><div class="calc-h">Your numbers <span>example values · edit any of them</span></div>{inputs}</div>
      <div class="calc-out">
        <div class="o"><div class="k">Time back</div><div class="v" id="oHours"></div><div class="s" id="oHoursS"></div></div>
        <div class="o"><div class="k">Added revenue</div><div class="v" id="oRev"></div><div class="s" id="oRevS"></div></div>
        <div class="o"><div class="k">{pkg}</div><div class="v" id="oCost"></div><div class="s">per month</div></div>
        <div class="o"><div class="k">Value of time back</div><div class="v" id="oTime"></div><div class="s" id="oTimeS"></div></div>
        <div class="o big"><div class="k">Monthly return on {pkg}</div><div class="v grad" id="oRoi"></div><div class="s" id="oBe"></div></div>
      </div>
    </div>
"""

TEMPLATE = pathlib.Path(__file__).resolve().parent.parent / "references" / "blueprint-template.html"
GSM7_BAD = re.compile(r"[–—‘’“”…]|[\U0001F000-\U0001FFFF]")

# Line icons (Lucide-style, 24px grid, stroke = currentColor). The page uses
# these instead of emoji (Dylan, 2026-10-08: emoji read generic, not technical).
# The template references them as {{ICON_<NAME>}}; blueprint.json "icon"
# fields may name one of these keys, anything else falls back to the default.
ICONS = {
    "megaphone": '<path d="m3 11 18-5v12L3 14v-3z"/><path d="M11.6 16.8a3 3 0 1 1-5.8-1.6"/>',
    "funnel": '<path d="M22 3H2l8 9.46V19l4 2v-8.54L22 3z"/>',
    "bot": '<rect x="3" y="11" width="18" height="10" rx="2"/><circle cx="12" cy="5" r="2"/><path d="M12 7v4"/><path d="M8 16h.01"/><path d="M16 16h.01"/>',
    "database": '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/><path d="M3 12c0 1.66 4 3 9 3s9-1.34 9-3"/>',
    "refresh": '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
    "target": '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
    "ban": '<circle cx="12" cy="12" r="10"/><path d="m4.9 4.9 14.2 14.2"/>',
    "pointer": '<path d="m9 9 5 12 1.8-5.2L21 14Z"/><path d="M7.2 2.2 8 5.1"/><path d="m5.1 8-2.9-.8"/><path d="M14 4.1 12 6"/><path d="m6 12-1.9 2"/>',
    "phone": '<path d="m16 2 6 6"/><path d="m22 2-6 6"/><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.8 19.8 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.8 19.8 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.13.96.36 1.9.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.9.34 1.85.57 2.81.7A2 2 0 0 1 22 16.92z"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    "calendarx": '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4"/><path d="M8 2v4"/><path d="M3 10h18"/><path d="m10 14 4 4"/><path d="m14 14-4 4"/>',
    "message": '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    "mail": '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "send": '<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>',
    "volumex": '<path d="M11 5 6 9H2v6h4l5 4V5z"/><path d="m22 9-6 6"/><path d="m16 9 6 6"/>',
    "volume": '<path d="M11 5 6 9H2v6h4l5 4V5z"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>',
    "globe": '<circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
    "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
    "card": '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20"/>',
    "usercheck": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="m16 11 2 2 4-4"/>',
}


def icon(name: str) -> str:
    return (f'<svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONS[name]}</svg>')


def pick_icon(name, default: str) -> str:
    return icon(name if name in ICONS else default)


SND_MUTED = icon("volumex") + "Tap for sound"
SND_ON = icon("volume") + "Sound on"


def esc(s) -> str:
    return html.escape(str(s or ""), quote=True)


def rich_b(s) -> str:
    """Escape, then turn **words** into <b> (price anchor line)."""
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", esc(s))


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
    # "growth" (default): the full offer, ads + funnel + agent + reactivation +
    # recovery + the guarantee. "foundations": the back-end-only package (no ads,
    # no funnel, no guarantee): agent + reactivation + recovery + what's included.
    package = d.get("package") or "growth"
    growth = package != "foundations"
    has_funnel = growth or bool(d.get("funnel"))
    logo = logo_src(d.get("logo"), base)
    logo_img = f'<img src="{logo}" alt="{esc(business)}">' if logo else ""

    ad_avatar = logo_img or esc(initials(business))

    def ad_card(ad, media_html):
        return f"""<div class="reveal"><div class="ad">
  <div class="ad-top"><div class="ad-av">{ad_avatar}</div><div><div class="ad-name">{esc(business)}</div><div class="ad-sp">Sponsored · {icon("globe")}</div></div></div>
  <div class="ad-copy">{esc(ad["primary_text"])}</div>
  {media_html}
  <div class="ad-foot"><div><div class="u">{esc(d.get("domain") or short)}</div><div class="h">{esc(ad["headline"])}</div></div><div class="ad-btn">{esc(ad.get("cta") or "Book Now")}</div></div>
</div><div class="ad-angle"><span class="tag">{esc(ad.get("angle_label") or "Angle")}</span><span class="txt">{esc(ad.get("angle"))}</span></div></div>"""

    # Video ads (the prospect's own social videos, or AI UGC/POV videos) are
    # too heavy to inline: they're copied to out/assets/ and uploaded to R2 by
    # publish_landing_page.py --assets, then served from /lp/<slug>/a/<name>.
    # The poster frame IS inlined, so the card still looks right where the
    # video can't load (e.g. the Claude Artifact preview).
    assets = out / "assets"
    video_count = [0]

    def video_media(ad):
        video_count[0] += 1
        i = video_count[0]
        vsrc = base / ad["video"]
        assets.mkdir(exist_ok=True)
        name = f"video{i}.mp4"
        shutil.copyfile(vsrc, assets / name)
        poster_jpg = out / f"_poster{i}.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(ad.get("poster_at", 1)), "-i", str(vsrc),
                        "-frames:v", "1", str(poster_jpg)], check=True)
        poster = image_data_uri(poster_jpg, width=480, quality=70)
        poster_jpg.unlink()
        mb = vsrc.stat().st_size / 1e6
        if mb > 8:
            warnings.append(f"{vsrc.name} is {mb:.1f} MB; re-encode smaller for a phone-friendly page")
        src_url = f"/lp/{d['slug']}/a/{name}"
        return f'<div class="ad-img v"><video src="{src_url}" poster="{poster}" muted loop playsinline autoplay preload="metadata"></video><span class="snd">{SND_MUTED}</span></div>'

    ads_d = d.get("ads") if growth else None
    videos_html = [ad_card(ad, video_media(ad)) for ad in (ads_d or {}).get("video_items") or []]

    # The AI row can mix formats: an item with "video" (AI UGC, POV) renders
    # as a video card, an item with "image" as a static.
    ads_html = []
    for ad in (ads_d or {}).get("items") or []:
        if ad.get("video"):
            ads_html.append(ad_card(ad, video_media(ad)))
            continue
        img = image_data_uri(base / ad["image"])
        hook = f'<div class="ad-hook">{esc(ad["hook"])}</div>' if ad.get("hook") else ""
        ads_html.append(ad_card(ad, f'<div class="ad-img"><img src="{img}" alt="">{hook}</div>'))

    def row_label(text, n, cls=""):
        return f'<p class="row-label {cls} reveal">{esc(text)} <span class="c">/ {n:02d}</span></p>'

    videos_block = ""
    if videos_html:
        videos_block = (row_label(ads_d.get("video_label") or "Cut from your own videos", len(videos_html))
                        + f'<div class="ads">{"".join(videos_html)}</div>'
                        + row_label(ads_d.get("static_label") or "AI-generated concepts", len(ads_html), "second"))

    why_defaults = ["target", "ban", "pointer"]
    why_html = "".join(
        f'<div class="card reveal"><div class="top"><span class="ib">{pick_icon(w.get("icon"), why_defaults[i % 3])}</span>'
        f'<span class="no">{i + 1:02d}</span></div><h4>{esc(w["title"])}</h4><p>{esc(w["text"])}</p></div>'
        for i, w in enumerate((d.get("funnel") or {}).get("why") or []) if has_funnel)

    react = d["reactivation"]
    react_sms = []
    for m in react["sms"]:
        if GSM7_BAD.search(m["text"]):
            warnings.append(f'non-GSM-7 character in reactivation SMS: {m["text"][:50]}...')
        cls = "sms in" if m.get("from") == "lead" else "sms"
        react_sms.append(f'<div class="{cls}">{esc(m["text"])}</div>')

    funnel_d = (d.get("funnel") or {}) if has_funnel else {}
    funnel_doc = (base / funnel_d["html_file"]).read_text(encoding="utf-8") if has_funnel else ""

    rec_defaults = ["phone", "clock", "calendarx"]
    rec_html = []
    for n, item in enumerate(d["recovery"]["items"]):
        bubbles = []
        for m in item["messages"]:
            if GSM7_BAD.search(m["text"]):
                warnings.append(f'non-GSM-7 character in SMS example "{item["label"]}": {m["text"][:50]}...')
            cls = "sms in" if m.get("from") == "lead" else "sms"
            bubbles.append(f'<div class="{cls}">{esc(m["text"])}</div>')
        rec_html.append(f"""<div class="rc card reveal"><div class="lab"><span class="ib amb">{pick_icon(item.get("icon"), rec_defaults[n % 3])}</span>{esc(item["label"])}</div>
<div class="trig"><span class="k">TRIGGER</span>{esc(item.get("when"))}</div>{"".join(bubbles)}</div>""")

    li = lambda pts: "".join(f'<li><span class="ck">{icon("check")}</span><span>{esc(p)}</span></li>' for p in pts)
    js = lambda v: json.dumps(v).replace("</", "<\\/")
    blurbs = d["step_blurbs"]

    # Engine step cards, one per module, linking to its section.
    if growth:
        steps = [("ads", "megaphone", "", "Ads bring in new patients"), ("funnel", "funnel", "", "A funnel built to book"),
                 ("agent", "bot", "", "The AI agent books the visit"), ("reactivation", "database", "amb", "Database reactivation"),
                 ("recovery", "refresh", "amb", "Nothing leaks")]
    else:
        steps = ([("funnel", "funnel", "", (d.get("funnel") or {}).get("step_title") or "A booking page built to convert")] if has_funnel else []) + [
                 ("agent", "bot", "", "The AI text agent replies to every inquiry"), ("reactivation", "database", "amb", "Database reactivation"),
                 ("recovery", "refresh", "amb", "Nothing leaks")]
    if len(blurbs) != len(steps):
        warnings.append(f"step_blurbs has {len(blurbs)} entries, the {package} package needs {len(steps)}")
    map_steps = "".join(
        f'<a class="ms card reveal" href="#{sid}"><div class="ib {cls}">{icon(ic)}</div><div><h4>{esc(title)}</h4>'
        f'<p>{esc(blurbs[i] if i < len(blurbs) else "")}</p></div><span class="no">{i + 1:02d}</span></a>'
        for i, (sid, ic, cls, title) in enumerate(steps))

    # Sections present, in page order; numbered 01.. after the 00 overview.
    math_d = d.get("math")
    present = ((["ads"] if growth else []) + (["funnel"] if has_funnel else []) + ["agent", "reactivation", "recovery"]
               + (["math"] if math_d else []) + (["guarantee"] if growth else ["included"]))
    idx = {f"IDX_{sid.upper()}": f"{i + 1:02d}" for i, sid in enumerate(present)}

    inc = d.get("included") or {}
    inc_defaults = ["bot", "database", "phone", "clock", "calendarx", "message"]
    included_html = "".join(
        f'<div class="card"><div class="top"><span class="ib grn">{pick_icon(it.get("icon"), inc_defaults[i % 6])}</span>'
        f'<span class="no">{i + 1:02d}</span></div><h4>{esc(it["title"])}</h4><p>{esc(it["text"])}</p></div>'
        for i, it in enumerate(inc.get("items") or []))

    # Math close (optional): cited stats + a live calculator. Inputs are example
    # values Dylan edits on the call; keys used by the template's JS: inquiries,
    # minutes, extra_patients, patient_value, visits, noshow_rate, visit_value,
    # hourly_value. reminder_cut = share of no-shows text reminders prevent.
    math_stats = math_inputs = math_body = ""
    math_json = "null"
    if math_d:
        math_stats = "".join(
            f'<div class="stat card reveal"><div class="num grad">{esc(st["num"])}</div><div class="lab">{esc(st["label"])}</div>'
            + (f'<a class="src" href="{esc(st["url"])}" target="_blank" rel="noopener">{esc(st["source"])} ↗</a>' if st.get("url")
               else f'<span class="src">{esc(st["source"])}</span>') + '</div>'
            for st in math_d.get("stats") or [])
        rows = []
        for it in math_d.get("inputs") or []:
            k = esc(it["k"])
            hint = f'<small>{esc(it["hint"])}</small>' if it.get("hint") else ""
            pre = f'<span>{esc(it["prefix"])}</span>' if it.get("prefix") else ""
            suf = f'<span>{esc(it["suffix"])}</span>' if it.get("suffix") else ""
            rows.append(f'<div class="row-in"><label for="m_{k}">{esc(it["label"])}{hint}</label><div class="fld">{pre}'
                        f'<input id="m_{k}" data-k="{k}" type="number" inputmode="decimal" min="0" value="{esc(it["value"])}">{suf}</div></div>')
        math_inputs = "".join(rows)
        math_json = js({"price": float(math_d.get("price") or 0), "reminder_cut": float(math_d.get("reminder_cut") or 0)})
        pkg = esc(inc.get("package_name") or "the program")
        if math_d.get("outcomes"):
            # Fixed headline numbers (no inputs to fill in), with the research they rest on as linked chips.
            math_json = "null"
            outs = "".join(
                f'<div class="out card reveal{" hl" if o.get("highlight") else ""}"><div class="k">{esc(o["k"])}</div>'
                f'<div class="v{" grad" if o.get("highlight") else ""}">{esc(o["v"])}</div><div class="s">{esc(o["s"])}</div>'
                + (f'<div class="how"><span class="hk">How we estimated it</span>{rich_b(o["how"])}</div>' if o.get("how") else "")
                + '</div>'
                for o in math_d["outcomes"])
            explained = " explained" if any(o.get("how") for o in math_d["outcomes"]) else ""
            chips = "".join(
                (f'<a href="{esc(st["url"])}" target="_blank" rel="noopener">{esc(st["num"])} · {esc(st["source"])} ↗</a>' if st.get("url")
                 else f'<span class="b">{esc(st["num"])} · {esc(st["source"])}</span>')
                for st in math_d.get("stats") or [])
            math_body = f'<div class="outs{explained}">{outs}</div>' + (f'<div class="basis reveal">Based on {chips}</div>' if chips else "")
        else:
            math_body = CALC_HTML.format(stats=math_stats, inputs=math_inputs, pkg=pkg)

    # Multi-page website (optional): funnel.pages = [{route, path, title, description, keyword}];
    # html_file is then a hash-routed site (#/about ...) and each card opens its page in the preview.
    pages = funnel_d.get("pages") or []
    pages_html = ""
    if pages:
        pages_html = (f'<p class="seo-h reveal">SEO map · every page <span class="c">/ {len(pages):02d} pages</span></p><div class="seo">'
                      + "".join(f'<button type="button" class="pg card reveal" data-route="{esc(pg["route"])}"><div class="path">{esc(pg["path"])}<span>open ↗</span></div>'
                                f'<div class="tt">{esc(pg["title"])}</div><div class="md">{esc(pg["description"])}</div>'
                                f'<span class="kw">target: {esc(pg["keyword"])}</span></button>' for pg in pages)
                      + '</div>')

    price_html = ""
    if inc.get("price"):
        price_html = (f'<div class="price reveal"><div class="amt">{esc(inc["price"])}<span>{esc(inc.get("price_unit") or "/month")}</span></div>'
                      f'<div class="anchor">{rich_b(inc.get("price_note"))}</div></div>')

    fills = {
        "MAP_STEPS": map_steps, **idx,
        "MATH_LABEL": esc((math_d or {}).get("label") or "The math"),
        "MATH_HEADLINE": rich((math_d or {}).get("headline")), "MATH_INTRO": esc((math_d or {}).get("intro")),
        "MATH_BODY": math_body, "MATH_NOTE": esc((math_d or {}).get("note")),
        "MATH_PKG": esc(inc.get("package_name") or "the program"), "MATH_JSON": math_json,
        "INCLUDED_PRICE_HTML": price_html,
        "SPEC_TARGET_K": "Target" if growth else "Package",
        "SPEC_TARGET_V": "7-10 paid assessments in 6 weeks" if growth else esc(inc.get("package_name") or "Foundations"),
        "SPEC_MODULES": "Ads · Funnel · Agent · Reactivation · Recovery" if growth else (
            ("Funnel · " if has_funnel else "") + "AI Agent · Reactivation · Recovery"),
        "SRC2_T1": "New Leads" if growth else "New",
        "SRC2_T2": "from Ads" if growth else "Inquiries",
        "SRC2_S": "ads → funnel" if growth else "web, Google, referrals",
        "FLOW_BOOK_LBL": "books a consult" if growth else "books a visit",
        "NODE_BOOKED": esc(d.get("booked_node") or ("Booked Consult" if growth else "Booked Visit")),
        "INCLUDED_LABEL": esc(inc.get("label") or "What's included"),
        "INCLUDED_HEADLINE": rich(inc.get("headline")), "INCLUDED_INTRO": esc(inc.get("intro")),
        "INCLUDED_HTML": included_html,
        "BUSINESS": esc(business),
        "BUSINESS_SHORT": esc(short),
        "BRAND_PRIMARY": esc(d["brand"]["primary"]),
        "BRAND_PRIMARY_TEXT": esc(d["brand"].get("primary_text") or "#ffffff"),
        # Behind the logo in the round chat/ad avatars: match the logo's own
        # background (a logo cut from a dark header needs a dark circle).
        "BRAND_AVATAR_BG": esc(d["brand"].get("avatar_bg") or "#ffffff"),
        "LOGO_LOCKUP": logo_img or f'<span class="dg">{esc(business)}</span>',
        "HERO_HEADLINE": rich(d["hero"]["headline"]),
        "HERO_SUBHEAD": esc(d["hero"].get("subhead")),
        "ENGINE_INTRO": esc(d["engine_intro"]),
        "ADS_HEADLINE": esc((ads_d or {}).get("headline")), "ADS_INTRO": esc((ads_d or {}).get("intro")),
        "ADS_VIDEO_BLOCK": videos_block,
        "ADS_HTML": "".join(ads_html),
        "FUNNEL_WHY_HTML": why_html,
        "FUNNEL_URL": esc(funnel_d.get("url") or (d.get("domain") or "yourpractice.com") + "/free-consult"),
        "FUNNEL_HEADLINE": esc(funnel_d.get("headline")), "FUNNEL_INTRO": esc(funnel_d.get("intro")),
        "FUNNEL_POINTS": li(funnel_d.get("points") or []),
        "FUNNEL_LABEL": esc(funnel_d.get("label") or "Funnel"),
        "FUNNEL_PAGES_HTML": pages_html,
        "FUNNEL_SRCDOC": html.escape(funnel_doc, quote=True),
        "AGENT_HEADLINE": esc(d["agent"]["headline"]), "AGENT_INTRO": esc(d["agent"]["intro"]),
        "AGENT_POINTS": li(d["agent"]["points"]),
        "CHAT_AVATAR": logo_img or esc(initials(business)),
        "CHAT_CHIPS": "".join(f'<button type="button" class="chip">{esc(c)}</button>' for c in d["agent"]["chips"]),
        "RECOVERY_HEADLINE": esc(d["recovery"]["headline"]), "RECOVERY_INTRO": esc(d["recovery"]["intro"]),
        "RECOVERY_HTML": "".join(rec_html),
        "REACT_HEADLINE": esc(react["headline"]), "REACT_INTRO": esc(react["intro"]),
        "REACT_SMS_WHEN": esc(react.get("sms_when")), "REACT_SMS_HTML": "".join(react_sms),
        "REACT_EMAIL_WHEN": esc(react.get("email_when")),
        "REACT_EMAIL_SUBJECT": esc(react["email"]["subject"]), "REACT_EMAIL_BODY": esc(react["email"]["body"]),
        "CLOSE_INTRO": esc(d.get("close_intro")),
        "DOMAIN": esc(d.get("domain") or short),
        "BUILD_DATE": date.today().strftime("%b %d, %Y"),
        "SND_MUTED_JSON": js(SND_MUTED), "SND_ON_JSON": js(SND_ON),
        **{f"ICON_{k.upper()}": icon(k) for k in ICONS},
        # JSON inside <script>: escape "</" so page text can't close the tag.
        "SLUG_JSON": json.dumps(d["slug"]).replace("</", "<\\/"),
        "CHAT_GREETING_JSON": json.dumps(d["agent"]["greeting"]).replace("</", "<\\/"),
    }

    page = TEMPLATE.read_text(encoding="utf-8")
    # Drop the sections this package doesn't include, keep the rest unwrapped.
    for sid in ("ads", "funnel", "math", "guarantee", "included"):
        keep = sid in present
        page = re.sub(rf"<!--BLOCK:{sid}-->(.*?)<!--/BLOCK:{sid}-->", (lambda m: m.group(1)) if keep else "",
                      page, flags=re.S)
    page = re.sub(r"\{\{([A-Z0-9_]+)\}\}", lambda m: fills.get(m.group(1), m.group(0)), page)
    left = sorted(set(re.findall(r"\{\{([A-Z0-9_]+)\}\}", page)))
    if left:
        warnings.append(f"unfilled placeholders: {', '.join(left)}")

    (out / "page.html").write_text(page, encoding="utf-8")
    (out / "chat_context.txt").write_text(d["chat_context"].strip() + "\n", encoding="utf-8")

    kb = len(page.encode("utf-8")) / 1024
    if kb > 2500:
        warnings.append(f"page is {kb:.0f} KB, heavy for a texted link; shrink the funnel's embedded photos")
    print(f"Built {out / 'page.html'} ({kb:.0f} KB), {len(videos_html)} own-video ads, {len(ads_html)} AI ads ({video_count[0] - len(videos_html)} video), {len(rec_html)} recovery cards")
    if video_count[0]:
        print(f"Video assets: {assets} (publish with --assets {assets})")
    print(f"Chat context: {out / 'chat_context.txt'} ({len(d['chat_context'])} chars)")
    for w in warnings:
        print(f"WARNING: {w}")


if __name__ == "__main__":
    main()
