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
  "engine_headline": "...",   # optional; short (default: "Every lead runs into one agent. Nothing leaks.")
  "engine_intro": "...",      # ONE sentence. The page is presented on a call, not read: every intro is a
                              # single line, the detail lives in "keys" and the visuals.
  "engine_keys": [{"big": "< 1 min", "small": "every lead answered"}],   # 3-4 key points, big type
  # ads / funnel / agent / voice / reactivation / social each take the same optional "keys" list
  # (recovery renders inside the reactivation section, under its own sub-heading, no keys).
  # Keys and "points" are optional: Dylan (2026-11-22) cut them from overview/ads/funnel/agent/voice.
  # voice.demo (default true): the live in-browser call with the demo voice agent (dashboard/backend/blueprint_voice.py).
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
  "reactivation": {"headline": "...", "intro": "...", "sms_when": "...",   # SMS only since 2026-10-28
      "sms": [{"from": "practice", "text": "..."}, {"from": "lead", "text": "..."}],
      "sms2_label": "...", "sms2_when": "...", "sms2": [...]},           # optional later touch
      # (a legacy "email_when" + "email" pair in an older blueprint is ignored)
  # agent may also carry "scenarios": [{"key": "website"|"meta_lead"|"reactivation"|"missed_call",
  #   "label", "icon", "status", "note", "opener", "chips": [...]}] -> tabs above the live chat
  "voice": {"headline", "intro", "points": [...], "flow_title", "flow_sub",        # optional section
            "steps": [{"t": "0:00", "title", "text", "sms": true?}]},
  "social": {"headline", "intro", "handle", "bio", "button", "note" (**bold**),     # optional section
             "cards": [{"icon", "title", "text"}], "grid": [{"image", "reel"?} | {"quote", "attr"}],
             "dm_label", "dm_when", "dm": [{"from", "text"}]},
  "results": {"headline", "intro", "items": [{"client", "period", "kpis": [{"k", "v", "hl"?}], "note"}
             | {"client", "period", "image", "note"}]},                          # optional, VERIFIED numbers only
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
DG_WORDMARK = pathlib.Path(__file__).resolve().parents[2] / "dashboard" / "frontend" / "src" / "assets" / "logo-wordmark.png"
GSM7_BAD = re.compile(r"[–—‘’“”…]|[\U0001F000-\U0001FFFF]")

# Line icons (Lucide-style, 24px grid, stroke = currentColor). The page uses
# these instead of emoji (Dylan, 2026-10-08: emoji read generic, not technical).
# The template references them as {{ICON_<NAME>}}; blueprint.json "icon"
# fields may name one of these keys, anything else falls back to the default.
ICONS = {
    "calendar": '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4"/><path d="M8 2v4"/><path d="M3 10h18"/><path d="m9 16 2 2 4-4"/>',
    "star": '<path d="m12 2 3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>',
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
    "call": '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.8 19.8 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.8 19.8 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.13.96.36 1.9.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.9.34 1.85.57 2.81.7A2 2 0 0 1 22 16.92z"/>',
    "instagram": '<rect x="2" y="2" width="20" height="20" rx="5"/><circle cx="12" cy="12" r="4"/><path d="M17.5 6.5h.01"/>',
    "grid": '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    "chart": '<path d="M3 3v18h18"/><path d="m7 15 4-4 3 3 5-6"/>',
}


def icon(name: str) -> str:
    return (f'<svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONS[name]}</svg>')


def pick_icon(name, default: str) -> str:
    return icon(name if name in ICONS else default)


# The live voice demo's "what hurts" choices; keys must match blueprint_voice.ISSUES.
VOICE_ISSUES = [("back", "Lower back pain"), ("knee", "Knee pain"), ("shoulder", "Shoulder pain"),
                ("neck", "Neck pain"), ("hip", "Hip pain"), ("sciatica", "Sciatica")]

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

    # A wide wordmark is unreadable in the round avatars; "logo_mark" (just the symbol) goes there instead.
    mark = logo_src(d.get("logo_mark"), base)
    avatar_img = f'<img src="{mark}" alt="{esc(business)}">' if mark else logo_img
    ad_avatar = avatar_img or esc(initials(business))

    def ad_card(ad, media_html):
        return f"""<div class="reveal"><div class="ad">
  <div class="ad-top"><div class="ad-av">{ad_avatar}</div><div><div class="ad-name">{esc(business)}</div><div class="ad-sp">Sponsored · {icon("globe")}</div></div></div>
  <div class="ad-copy{" clamp" if len(ad["primary_text"]) > 150 else ""}">{esc(ad["primary_text"])}</div>{'<div class="ad-more">See more</div>' if len(ad["primary_text"]) > 150 else ""}
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

    def sms_bubbles(msgs, where):
        out = []
        for m in msgs:
            if GSM7_BAD.search(m["text"]):
                warnings.append(f'non-GSM-7 character in {where}: {m["text"][:50]}...')
            if m.get("from") == "event":  # a step between texts, e.g. "Next day the voice agent calls"
                out.append(f'<div class="sms-ev">{icon("call")}{esc(m["text"])}</div>')
                continue
            cls = "sms in" if m.get("from") == "lead" else "sms"
            out.append(f'<div class="{cls}">{esc(m["text"])}</div>')
        return "".join(out)

    # Reactivation is SMS only (Dylan, 2026-10-28: no more email campaigns).
    # A second thread ("sms2") shows a later touch; an "email" key left in an
    # older blueprint's JSON is ignored.
    react = d["reactivation"]
    react_cards = [f'<div class="rc card reveal"><div class="lab"><span class="ib amb">{icon("message")}</span>'
                   f'{esc(react.get("sms_label") or "SMS campaign")}</div><div class="trig"><span class="k">SEND</span>'
                   f'{esc(react.get("sms_when"))}</div>{sms_bubbles(react["sms"], "reactivation SMS")}</div>']
    if react.get("sms2"):
        react_cards.append(f'<div class="rc card reveal"><div class="lab"><span class="ib amb">{icon("refresh")}</span>'
                           f'{esc(react.get("sms2_label") or "Follow-up text")}</div><div class="trig"><span class="k">SEND</span>'
                           f'{esc(react.get("sms2_when"))}</div>{sms_bubbles(react["sms2"], "reactivation SMS 2")}</div>')

    # Optional sections (growth package): voice agent, social media, client results.
    voice_d, social_d, results_d = d.get("voice"), d.get("social"), d.get("results")
    voice_steps = "".join(
        f'<div class="vs{" hand" if st.get("sms") else ""}"><div class="dot2">{i + 1}</div><div><div class="t">{esc(st.get("t"))}</div>'
        f'<h4>{esc(st["title"])}</h4><p>{esc(st["text"])}</p></div></div>'
        for i, st in enumerate((voice_d or {}).get("steps") or []))
    # Live voice demo: talk to the voice agent in the browser (blueprint_voice.py).
    voice_demo = ""
    if voice_d and voice_d.get("demo", True):
        opts = "".join(f'<option value="{k}">{v}</option>' for k, v in VOICE_ISSUES)
        voice_demo = (f'<div class="vdemo card" id="vdemo" data-slug="{esc(d["slug"])}">'
                      f'<div class="vd-top"><span class="live"><i></i>LIVE DEMO · TALK TO IT</span></div>'
                      f'<div class="vd-orb">{icon("call")}</div>'
                      f'<div class="vd-st" id="vdSt">You just filled out the ad form.</div>'
                      f'<div class="vd-sub" id="vdSub">The agent calls you, right here in the browser.</div>'
                      f'<div class="vd-form"><label>Your first name<input id="vdName" value="Jordan" maxlength="20" autocomplete="off"></label>'
                      f'<label>What hurts<select id="vdIssue">{opts}</select></label></div>'
                      f'<button type="button" class="vd-btn" id="vdBtn">{icon("call")}Call me now</button>'
                      f'<div class="vd-note">Uses your microphone. Booking is simulated: nothing hits a calendar.</div></div>')

    soc_defaults = ["grid", "message", "usercheck"]
    social_cards = "".join(
        f'<div class="card reveal"><div class="top"><span class="ib">{pick_icon(c.get("icon"), soc_defaults[i % 3])}</span>'
        f'<span class="no">{i + 1:02d}</span></div><h4>{esc(c["title"])}</h4><p>{esc(c["text"])}</p></div>'
        for i, c in enumerate((social_d or {}).get("cards") or []))
    grid = []
    for g in (social_d or {}).get("grid") or []:
        if g.get("quote"):
            grid.append(f'<div class="q">{esc(g["quote"])}<small>{esc(g.get("attr"))}</small></div>')
        else:
            grid.append(f'<div class="{"rl" if g.get("reel") else ""}"><img src="{image_data_uri(base / g["image"], width=260, quality=72)}" alt=""></div>')
    social_dm = sms_bubbles((social_d or {}).get("dm") or [], "social DM")

    results_html = ""
    for r in (results_d or {}).get("items") or []:
        if r.get("image"):
            results_html += (f'<div class="card reveal"><div class="rh"><b>{esc(r.get("client"))}</b><span>{esc(r.get("period"))}</span></div>'
                             f'<img class="res-img" src="{image_data_uri(base / r["image"], width=1100, quality=80)}" alt="{esc(r.get("client"))} results">'
                             + (f'<p class="rn">{esc(r["note"])}</p>' if r.get("note") else "") + '</div>')
            continue
        kpis = "".join(f'<div class="kpi{" hl" if k.get("hl") else ""}"><div class="k">{esc(k["k"])}</div><div class="v">{esc(k["v"])}</div></div>'
                       for k in r.get("kpis") or [])
        results_html += (f'<div class="card reveal"><div class="rh"><b>{esc(r["client"])}</b><span>{esc(r.get("period"))}</span></div>'
                         f'<div class="kpis">{kpis}</div>' + (f'<p class="rn">{esc(r["note"])}</p>' if r.get("note") else "") + '</div>')

    # Live chat scenarios (optional): agent.scenarios = [{key, label, icon, status, note, opener, chips}].
    # Keys must be ones blueprint_chat._SCENARIOS knows (website, meta_lead, reactivation, missed_call).
    scen = (d.get("agent") or {}).get("scenarios") or []
    for s in scen:
        if s.get("key") not in ("website", "meta_lead", "reactivation", "missed_call"):
            warnings.append(f'agent scenario key {s.get("key")!r} is unknown to blueprint_chat.py (falls back to website)')
        if s.get("key") == "website":
            warnings.append("agent scenario 'website': DigiGrowth doesn't offer a website chat (Dylan, 2026-11-22); drop this tab")
        if s.get("key") != "website" and GSM7_BAD.search(s.get("opener", "")):
            warnings.append(f'non-GSM-7 character in SMS scenario opener "{s.get("label")}"')
    scen_html = ""
    if scen:
        scen_html = ('<div class="scen" role="tablist">' + "".join(
            f'<button type="button" class="{"on" if i == 0 else ""}">{pick_icon(s.get("icon"), "message")}{esc(s["label"])}</button>'
            for i, s in enumerate(scen)) + '</div><div class="scen-note" id="scenNote"></div>')

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
        steps = ([("ads", "megaphone", "", "Ads bring in new patients"), ("funnel", "funnel", "", "A funnel built to book"),
                  ("agent", "bot", "", "The AI agent books the visit")]
                 + ([("voice", "call", "", "The voice agent calls new leads")] if voice_d else [])
                 + [("reactivation", "database", "amb", "Reactivation + follow-up")]
                 + ([("social", "instagram", "", "Social media backs up the ads")] if social_d else []))
    else:
        steps = ([("funnel", "funnel", "", (d.get("funnel") or {}).get("step_title") or "A booking page built to convert")] if has_funnel else []) + [
                 ("agent", "bot", "", "The AI text agent replies to every inquiry"), ("reactivation", "database", "amb", "Reactivation + follow-up")]
    # Reactivation and recovery were two steps before 2026-11-22; an older json's two blurbs are joined.
    ri = [sid for sid, *_ in steps].index("reactivation")
    if len(blurbs) == len(steps) + 1:
        blurbs = blurbs[:ri] + [blurbs[ri].rstrip(". ") + ". " + blurbs[ri + 1]] + blurbs[ri + 2:]
    if len(blurbs) != len(steps):
        warnings.append(f"step_blurbs has {len(blurbs)} entries, the {package} package needs {len(steps)}")
    map_steps = "".join(
        f'<a class="ms card reveal" href="#{sid}"><div class="ib {cls}">{icon(ic)}</div><div><h4>{esc(title)}</h4>'
        f'<p>{esc(blurbs[i] if i < len(blurbs) else "")}</p></div><span class="no">{i + 1:02d}</span></a>'
        for i, (sid, ic, cls, title) in enumerate(steps))

    # Sections present, in page order; numbered 01.. after the 00 overview.
    math_d = d.get("math")
    present = ((["ads"] if growth else []) + (["funnel"] if has_funnel else []) + ["agent"]
               + (["voice"] if voice_d else []) + ["reactivation"]  # recovery lives inside it (Dylan 2026-11-22)
               + (["social"] if social_d else []) + (["results"] if results_d else [])
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

    # Booking page we build for them (DigiGrowth Booking, dashboard/backend/booking_page.py), rendered live
    # in the funnel section with the practice's details and simulated open times. Nothing is booked.
    booking_html = ""
    bk = d.get("booking")
    if bk:
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "dashboard" / "backend"))
        import booking_page  # noqa: E402
        def asset(v, w=480):
            if not v or str(v).startswith(("data:", "http")):
                return v
            return image_data_uri(base / v, width=w, quality=86)
        prof = dict(bk.get("profile") or {})
        for k in ("photo_url", "logo_url"):
            prof[k] = asset(prof.get(k))
        info = {"clinic": d["business"], "timezone": bk.get("timezone") or "America/Los_Angeles", "profile": prof,
                "event_types": [{"id": 1, "slug": "assessment", "max_days_ahead": 14, "location_type": "in_person", **bk["event"]}]}
        stub = ("<script>(function(){var INFO=" + json.dumps(info).replace("</", "<\\/") + ";"
                "Element.prototype.scrollIntoView=function(){};"
                "function days(start,n){var out=[],d=new Date(start+'T12:00:00Z');for(var i=0;i<n;i++){var wd=d.getUTCDay(),ds=d.toISOString().slice(0,10),sl=[];"
                "if(wd>0&&wd<6){for(var h=8;h<18;h++){var k=(d.getUTCDate()*7+h*3)%5;if(k<2)continue;sl.push(ds+'T'+(h<10?'0':'')+h+':00:00-08:00');}}"
                "out.push({date:ds,slots:sl});d.setUTCDate(d.getUTCDate()+1);}return out;}"
                "function res(b,st){return Promise.resolve(new Response(JSON.stringify(b),{status:st||200,headers:{'Content-Type':'application/json'}}));}"
                "window.fetch=function(u){u=String(u);var p=u.split('/api/')[1]||'';"
                "if(p.indexOf('info')===0)return res(INFO);"
                "if(p.indexOf('slots')===0){var q=new URLSearchParams(p.split('?')[1]||'');return res({days:days(q.get('start')||new Date().toISOString().slice(0,10),+q.get('days')||14)});}"
                "if(p.indexOf('reserve')===0)return res({detail:" + json.dumps(bk.get("demo_note") or "Demo only. On the live page this goes to secure payment, then a confirmation text.") + "},400);"
                "return res({ok:true});};})();</script>")
        page = booking_page.render_page("book", d["business"], bk.get("accent") or d["brand"]["primary"])
        page = page.replace("<script>", stub + "<script>", 1)
        bens = "".join(f'<div class="bk-b"><span class="ib">{pick_icon(b.get("icon"), "check")}</span><div><h4>{esc(b["title"])}</h4><p>{esc(b["text"])}</p></div></div>'
                       for b in bk.get("benefits") or [])
        booking_html = (f'<div class="subh reveal" id="booking"><span class="ib">{icon("calendar")}</span>'
                        f'<div><h3>{esc(bk.get("headline") or "Then a booking page we build for you")}</h3><p>{esc(bk.get("intro") or "")}</p></div></div>'
                        f'<div class="bk-grid reveal"><div class="bk-bens">{bens}</div>'
                        f'<div class="browser bk-br"><div class="bar3"><i></i><i></i><i></i><span class="url">{esc(bk.get("url") or "booking.digigrowthllc.com")}</span></div>'
                        f'<iframe class="bk-frame" title="Booking page preview for {esc(d["business"])}" loading="lazy" srcdoc="{html.escape(page, quote=True)}"></iframe></div></div>')

    price_html = ""
    if inc.get("price"):
        price_html = (f'<div class="price reveal"><div class="amt">{esc(inc["price"])}<span>{esc(inc.get("price_unit") or "/month")}</span></div>'
                      f'<div class="anchor">{rich_b(inc.get("price_note"))}</div></div>')

    def keys_html(lst, amb=False):
        if not lst:
            return ""
        return '<div class="keys reveal">' + "".join(
            f'<div class="key{" amb" if amb else ""}"><b>{esc(k["big"])}</b><span>{esc(k["small"])}</span></div>' for k in lst) + "</div>"

    nav_names = {"ads": "Ads", "funnel": funnel_d.get("label") or "Funnel", "agent": "Text agent", "voice": "Voice agent",
                 "reactivation": "Reactivation + follow-up", "social": "Social", "results": "Results",
                 "math": (math_d or {}).get("label") or "The math", "guarantee": "Guarantee", "included": "Package"}
    # Section selector band between the hero and section 00 (Dylan 2026-11-22): full-width, every section with
    # its page number, each a link. Replaced the plan-at-a-glance row and the offer strip.
    bar_icons = {"engine": "grid", "ads": "megaphone", "funnel": "funnel", "agent": "message", "voice": "call",
                 "reactivation": "refresh", "social": "instagram", "results": "chart", "math": "chart",
                 "guarantee": "shield", "included": "card"}
    bar_names = {**nav_names, "reactivation": "Reactivation"}
    secbar = ('<nav class="secbar" aria-label="Sections"><div class="sb-row">'
              + "".join(f'<a class="sb-it" href="#{sid}"><span class="sb-ic">{icon(bar_icons.get(sid, "check"))}</span>'
                        f'<span class="sb-tx"><span class="sb-n">{n:02d}</span><span class="sb-l">{esc(nm)}</span></span></a>'
                        for n, (sid, nm) in enumerate([("engine", "Overview")] + [(x, bar_names.get(x, x)) for x in present]))
              + '</div></nav>')
    nav_html = '<a href="#engine"><span>00</span>Overview</a>' + "".join(
        f'<a href="#{sid}"><span>{i + 1:02d}</span>{esc(nav_names.get(sid, sid))}</a>' for i, sid in enumerate(present))

    fills = {
        "MAP_STEPS": map_steps, **idx,
        "NAV_HTML": nav_html,
        "ENGINE_HEADLINE": esc(d.get("engine_headline") or "Every lead runs into one agent. Nothing leaks."),
        "KEYS_ENGINE": keys_html(d.get("engine_keys")),
        "KEYS_ADS": keys_html((ads_d or {}).get("keys")),
        "KEYS_FUNNEL": keys_html(funnel_d.get("keys")),
        "KEYS_AGENT": keys_html(d["agent"].get("keys")),
        "KEYS_VOICE": keys_html((voice_d or {}).get("keys")),
        "KEYS_REACT": keys_html(react.get("keys"), amb=True),
        "KEYS_SOCIAL": keys_html((social_d or {}).get("keys")),
        "VOICE_DEMO_HTML": voice_demo,
        "MATH_LABEL": esc((math_d or {}).get("label") or "The math"),
        "MATH_HEADLINE": rich((math_d or {}).get("headline")), "MATH_INTRO": esc((math_d or {}).get("intro")),
        "MATH_BODY": math_body, "MATH_NOTE": esc((math_d or {}).get("note")),
        "MATH_PKG": esc(inc.get("package_name") or "the program"), "MATH_JSON": math_json,
        "INCLUDED_PRICE_HTML": price_html,
        "SPEC_TARGET_K": "Target" if growth else "Package",
        "SPEC_TARGET_V": "7-10 paid assessments in 30 days" if growth else esc(inc.get("package_name") or "Foundations"),
        "SPEC_MODULES": ("Ads · Funnel · Agent" + (" · Voice" if voice_d else "") + " · Reactivation · Recovery"
                         + (" · Social" if social_d else "")) if growth else (
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
        # Top header = the client portal lockup: clinic logo × DigiGrowth wordmark (Dylan 2026-11-22).
        "DG_WORDMARK": "data:image/png;base64," + base64.b64encode(DG_WORDMARK.read_bytes()).decode(),
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
        "BOOKING_HTML": booking_html,
        "SECBAR": secbar,
        "FUNNEL_SRCDOC": html.escape(funnel_doc, quote=True),
        "AGENT_HEADLINE": esc(d["agent"]["headline"]), "AGENT_INTRO": esc(d["agent"]["intro"]),
        "AGENT_POINTS": li(d["agent"].get("points") or []),
        "CHAT_AVATAR": ad_avatar,
        "CHAT_CHIPS": "".join(f'<button type="button" class="chip">{esc(c)}</button>' for c in d["agent"]["chips"]),
        "RECOVERY_HEADLINE": esc(d["recovery"]["headline"]), "RECOVERY_INTRO": esc(d["recovery"]["intro"]),
        "RECOVERY_HTML": "".join(rec_html),
        "REACT_HEADLINE": esc(react["headline"]), "REACT_INTRO": esc(react["intro"]),
        "REACT_CARDS_HTML": "".join(react_cards),
        "NODE_AGENT_CHANNELS": esc(d.get("agent_channels") or (
            "SMS + voice + DMs → books it" if voice_d and social_d else "SMS + voice → books it" if voice_d
            else "SMS → books it")),
        "CHAT_SCENARIOS_HTML": scen_html, "CHAT_SCENARIOS_JSON": js(scen),
        "VOICE_HEADLINE": esc((voice_d or {}).get("headline")), "VOICE_INTRO": esc((voice_d or {}).get("intro")),
        "VOICE_POINTS": li((voice_d or {}).get("points") or []),
        "VOICE_FLOW_TITLE": esc((voice_d or {}).get("flow_title") or "New Meta lead"),
        "VOICE_FLOW_SUB": esc((voice_d or {}).get("flow_sub") or "voice + SMS, one handoff"),
        "VOICE_STEPS_HTML": voice_steps,
        "SOCIAL_HEADLINE": rich((social_d or {}).get("headline")), "SOCIAL_INTRO": esc((social_d or {}).get("intro")),
        "SOCIAL_CARDS_HTML": social_cards, "SOCIAL_GRID_HTML": "".join(grid),
        "SOCIAL_HANDLE": esc((social_d or {}).get("handle") or short),
        "SOCIAL_BIO": esc((social_d or {}).get("bio")), "SOCIAL_BTN": esc((social_d or {}).get("button") or "Book now"),
        "SOCIAL_DM_LABEL": esc((social_d or {}).get("dm_label") or "AI agent in the DMs"),
        "SOCIAL_DM_WHEN": esc((social_d or {}).get("dm_when")), "SOCIAL_DM_HTML": social_dm,
        "SOCIAL_NOTE": rich_b((social_d or {}).get("note")),
        "RESULTS_HEADLINE": rich((results_d or {}).get("headline")), "RESULTS_INTRO": esc((results_d or {}).get("intro")),
        "RESULTS_HTML": results_html,
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
    for sid in ("ads", "funnel", "voice", "social", "results", "math", "guarantee", "included"):
        keep = sid in present
        page = re.sub(rf"<!--BLOCK:{sid}-->(.*?)<!--/BLOCK:{sid}-->", (lambda m: m.group(1)) if keep else "",
                      page, flags=re.S)
    # Alternate section backgrounds in page order (optional sections shift it).
    for i, sid in enumerate(present):
        alt = ' class="alt"' if i % 2 == 0 else ""
        page = re.sub(rf'<section id="{sid}"( class="alt")?>', f'<section id="{sid}"{alt}>', page)
    page = re.sub(r"\{\{([A-Z0-9_]+)\}\}", lambda m: fills.get(m.group(1), m.group(0)), page)
    page = re.sub(r'<ul class="pts[^"]*"></ul>', "", page)  # no points given: no empty chip row
    page = page.replace('<p class="soc-note reveal"></p>', "")  # no social note given
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
