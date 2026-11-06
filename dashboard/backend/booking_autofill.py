"""Booking Links → "Auto-fill from client info": drafts a clinic's booking
setup (hours, appointment type, price, address, timezone) from everything
the client already gave us, for Dylan to review before anything is saved.

Sources, in order of how much they're trusted:
  1. Their existing Calendly event type + availability schedule, if a
     Calendly token/event link is on file (real, structured settings).
  2. The clinic's Google Calendar time zone (booking_settings.calendar_id).
  3. Portal intake answers (client_onboarding_responses): address, specials.
  4. The client's AI text agent notes (response_ai_context / _rules), which
     usually spell out hours and the patient offer.
  5. Their funnel landing page text (the live patient offer).

Claude extracts a proposal via a forced tool call; it's told to leave a
field empty rather than guess, and to list every guess in `notes`.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from html import unescape

import anthropic
import httpx

from db import get_pool

_MODEL = os.environ.get("BOOKING_AUTOFILL_MODEL", "claude-sonnet-5-5")

_TOOL = {
    "name": "propose_booking_setup",
    "description": "Return the proposed booking setup for this clinic.",
    "input_schema": {
        "type": "object",
        "properties": {
            "timezone": {"type": ["string", "null"], "description": "IANA time zone of the clinic, e.g. America/Chicago. Null if unknown."},
            "hours": {
                "type": "array",
                "description": "Weekly windows when NEW PATIENTS can be booked. Empty if the sources don't say.",
                "items": {
                    "type": "object",
                    "properties": {
                        "weekday": {"type": "integer", "description": "0=Monday ... 6=Sunday"},
                        "start": {"type": "string", "description": "HH:MM 24h, clinic local time"},
                        "end": {"type": "string", "description": "HH:MM 24h, clinic local time"},
                    },
                    "required": ["weekday", "start", "end"],
                },
            },
            "hours_source": {"type": "string", "description": "Where the hours came from, in a few words."},
            "event_type": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Patient-facing visit name, e.g. 'New Patient Assessment' or 'Free Consultation'."},
                    "duration_min": {"type": "integer"},
                    "location_type": {"type": "string", "enum": ["in_person", "google_meet", "phone"]},
                    "location_text": {"type": ["string", "null"], "description": "Full clinic street address for in_person, else null."},
                    "price_cents": {"type": "integer", "description": "What the patient pays online when booking, in cents. 0 if free."},
                    "anchor_price_cents": {"type": ["integer", "null"], "description": "'Normally $X' price in cents, only if the offer states one."},
                    "spots_per_month": {"type": ["integer", "null"], "description": "Scarcity line ('only N spots per month') only if the offer states one."},
                    "ask_question": {"type": ["string", "null"], "description": "One short question to ask when booking, e.g. 'What brings you in?'"},
                    "description": {"type": ["string", "null"], "description": "1-2 short patient-facing sentences about the visit, from the sources. No claims the sources don't make."},
                },
                "required": ["name", "duration_min", "location_type", "price_cents"],
            },
            "notes": {
                "type": "array", "items": {"type": "string"},
                "description": "Anything missing, conflicting, or guessed that Dylan should check. Plain sentences.",
            },
        },
        "required": ["hours", "hours_source", "event_type", "notes"],
    },
}

_SYSTEM = """You set up an online booking page for a physical therapy clinic's NEW PATIENT visits, using only what the clinic and its marketing agency already wrote down. Your output is a draft that a human reviews before saving.

Always answer by calling the propose_booking_setup tool, once.

Rules:
- Never invent facts. If hours, price, address or length aren't in the sources, leave hours empty / use the defaults below and say so in notes.
- Hours = when new patients can book, in the clinic's local time. Prefer an existing Calendly availability schedule over prose. If only general business hours are given, use those and note it.
- Price: what the patient pays online at booking. The agency's offers are usually either a FREE consultation/screen (price 0) or a PAID assessment (often $49, shown as 'normally $150' with 'only 10 spots per month'). Use whichever the sources describe as the CURRENT patient offer. If a paid $49 offer is described but no 'normally' price or spots are given, use anchor 15000 and spots 10 and add a note saying you applied the agency's default.
- If sources conflict (e.g. intake says one special, the funnel page another), prefer the funnel page / agent notes (most recent), and note the conflict.
- Defaults when unstated: duration 60 for an assessment/evaluation, 20 for a free phone/video consult; location in_person with the clinic address if they treat in clinic; ask_question 'What brings you in?'.
- Visit name should match the offer's own wording where possible.
- Keep notes short and specific."""


def _strip_html(html: str, limit: int) -> str:
    html = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", html or "")
    text = unescape(re.sub(r"(?s)<[^>]+>", " ", html))
    return re.sub(r"\s+", " ", text).strip()[:limit]


async def _calendly_source(token: str | None, event_url: str | None) -> str | None:
    if not token or not event_url:
        return None
    import calendly_integration as ci
    try:
        async with httpx.AsyncClient(timeout=20) as http:
            ev = await ci._get_matching_event_type(http, token, event_url)
            lines = []
            if ev:
                lines.append(json.dumps({k: ev.get(k) for k in (
                    "name", "duration", "kind", "description_plain", "locations", "is_paid", "scheduling_url",
                )}, default=str)[:3000])
            user_uri = await ci.get_user_uri(token)
            r = await http.get("https://api.calendly.com/user_availability_schedules",
                               params={"user": user_uri}, headers=ci._headers(token))
            if r.status_code == 200:
                for sch in r.json().get("collection", []):
                    lines.append("Availability schedule " + json.dumps({
                        "name": sch.get("name"), "default": sch.get("default"), "timezone": sch.get("timezone"),
                        "rules": [x for x in sch.get("rules", []) if x.get("type") == "wday"],
                    })[:3000])
            return "\n".join(lines) or None
    except Exception as e:
        return f"(Couldn't read their Calendly: {e})"


async def gather_sources(client_id: int) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        client = await conn.fetchrow("SELECT name, email, phone FROM clients WHERE id = $1", client_id)
        if not client:
            raise ValueError("client not found")
        onboarding = await conn.fetch(
            "SELECT section, answers FROM client_onboarding_responses WHERE client_id = $1 ORDER BY section", client_id,
        )
        cfg = await conn.fetchrow(
            "SELECT response_ai_context, response_ai_rules, calendly_api_token, calendly_event_type_url "
            "FROM client_marketing_config WHERE client_id = $1", client_id,
        )
        page = await conn.fetchrow(
            "SELECT slug, html FROM landing_pages WHERE client_id = $1 ORDER BY created_at DESC LIMIT 1", client_id,
        )
        settings = await conn.fetchrow("SELECT calendar_id, timezone FROM booking_settings WHERE client_id = $1", client_id)
        anchor = await conn.fetchrow(
            "SELECT city, state FROM contacts WHERE client_id = $1 AND is_client_anchor LIMIT 1", client_id,
        )

    sources: dict[str, str] = {"Clinic": f"{client['name']}" + (f" ({anchor['city']}, {anchor['state']})" if anchor and anchor["city"] else "")}

    if settings and settings["timezone"]:
        sources["Clinic Google Calendar time zone"] = settings["timezone"]
    elif settings and settings["calendar_id"]:
        import booking_engine as be
        g = await be.google_status()
        tz = next((c.get("time_zone") for c in g.get("calendars", []) if c["id"] == settings["calendar_id"]), None)
        if tz:
            sources["Clinic Google Calendar time zone"] = tz

    cal = await _calendly_source(cfg["calendly_api_token"] if cfg else None, cfg["calendly_event_type_url"] if cfg else None)
    if cal:
        sources["Their existing Calendly booking (event type + availability)"] = cal

    answers = []
    for row in onboarding:
        a = row["answers"]
        a = json.loads(a) if isinstance(a, str) else (a or {})
        for k, v in a.items():
            if v and str(v).strip():
                answers.append(f"{k}: {str(v).strip()}")
    if answers:
        sources["Client portal intake answers"] = "\n".join(answers)[:8000]

    if cfg and (cfg["response_ai_context"] or "").strip():
        sources["AI text agent notes (business info, hours, offer)"] = cfg["response_ai_context"][:10000]
    if cfg and (cfg["response_ai_rules"] or "").strip():
        sources["AI text agent rules"] = cfg["response_ai_rules"][:3000]
    if page and page["html"]:
        sources[f"Funnel landing page text (/lp/{page['slug']})"] = _strip_html(page["html"], 6000)
    return sources


async def propose(client_id: int) -> dict:
    sources = await gather_sources(client_id)
    body = "\n\n".join(f"=== {k} ===\n{v}" for k, v in sources.items())
    api = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    resp = await api.messages.create(
        model=_MODEL, max_tokens=4000, system=_SYSTEM, tools=[_TOOL],
        # Forced tool_choice ("tool"/"any") isn't supported on current models: ask for it.
        tool_choice={"type": "auto"},
        messages=[{"role": "user", "content": "Sources:\n\n" + body
                   + "\n\nPropose the booking setup by calling propose_booking_setup. Reply with only that tool call."}],
    )
    result = next((b.input for b in resp.content if b.type == "tool_use"), None)
    if not result:
        raise RuntimeError("Claude didn't return a proposal")
    result["sources_used"] = list(sources.keys())
    return result


# ── Page details (trust content) from portal, website and funnel ─────────────
# Dylan, 2026-11-06: "get the reviews and all material from existing sources
# inside the client portal, their website, custom funnel and make that the
# default going forwards". Runs automatically the first time a client's
# booking setup is opened (routers/booking.py get_booking) and on demand.
# Nothing is invented: every review must appear word for word in a source,
# and the rating/count numbers must appear in the source text too.

_PAGE_HINTS = ("review", "testimonial", "about", "team", "staff", "meet", "provider", "our-story", "doctor", "therapist")
_UA = {"User-Agent": "Mozilla/5.0 (compatible; DigiGrowthBot/1.0; booking page setup)"}

_PAGE_TOOL = {
    "name": "propose_page_details",
    "description": "Return the booking page's trust content, copied from the sources.",
    "input_schema": {
        "type": "object",
        "properties": {
            "provider_name": {"type": ["string", "null"], "description": "The main physical therapist patients will see (full name as written), else null."},
            "provider_title": {"type": ["string", "null"], "description": "Their credentials as written, e.g. 'PT, DPT', else null."},
            "photo_index": {"type": ["integer", "null"], "description": "Index into the IMAGES list of the best photo of that therapist (a headshot beats a group shot; or the team/clinic if none). Null if no suitable real photo."},
            "logo_index": {"type": ["integer", "null"], "description": "Index into IMAGES of the clinic's own logo that reads well on a WHITE background (never a white-text or light logo, never a social icon). Null if none."},
            "accent_color": {"type": ["string", "null"], "description": "The clinic's main brand color as one of the hex codes in BRAND COLORS (the color its buttons/headings use), dark enough for white button text. Null if unsure."},
            "what_to_expect": {"type": "array", "items": {"type": "string"},
                               "description": "2-4 short lines (max ~60 chars each) on what happens at the first visit, based on what the sources say. Plain, patient-facing."},
            "review_rating": {"type": ["number", "null"], "description": "Average star rating ONLY if a source states it (e.g. '4.9 stars'), else null."},
            "review_count": {"type": ["integer", "null"], "description": "Number of reviews ONLY if a source states it, else null."},
            "reviews": {
                "type": "array",
                "description": "Up to 3 real patient reviews/testimonials COPIED EXACTLY from the sources (you may cut to whole sentences, never reword). Best first: specific outcome, 1-3 sentences.",
                "items": {"type": "object", "properties": {
                    "text": {"type": "string"},
                    "author": {"type": "string", "description": "First name only as written in the source, or empty."}},
                    "required": ["text", "author"]},
            },
            "notes": {"type": "array", "items": {"type": "string"}, "description": "What was missing or uncertain, short."},
        },
        "required": ["what_to_expect", "reviews", "notes"],
    },
}

_PAGE_SYSTEM = """You fill in the trust section of a physical therapy clinic's online booking page from material the clinic already published or gave its agency. Always answer by calling propose_page_details once.

Rules:
- Copy, never invent. Reviews must be exact text from the sources (you may shorten to whole sentences). If there are no real patient reviews in the sources, return an empty list.
- Rating and review count only if a source states the numbers.
- Pick the therapist the clinic presents as its lead/owner provider.
- Photo: only an image that is clearly a real photo of the therapist, team or clinic (judge by its alt text, file name and page). Never a logo, icon, stock-looking banner or social image. Null if unsure.
- Logo: only the clinic's own logo/wordmark that works on white. Uploads from the client portal are the most trustworthy images.
- Brand color: pick from BRAND COLORS only, the one the funnel uses for its buttons/accents.
- What to expect: plain lines about the first visit (what happens, what they leave with), grounded in the sources. No medical claims, no prices."""


def _norm(t: str) -> str:
    t = unescape(t or "").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", t).strip().lower()


async def _fetch(http: httpx.AsyncClient, url: str) -> str | None:
    # Identifies itself honestly. Sites that block bots are skipped (noted),
    # never worked around: the funnel page already carries their content.
    try:
        r = await http.get(url, headers=_UA, follow_redirects=True, timeout=15)
        if r.status_code == 200 and "html" in r.headers.get("content-type", ""):
            return r.text
    except Exception:
        pass
    return None


def _images(html: str, base: str) -> list[dict]:
    from urllib.parse import urljoin
    out = []
    for m in re.finditer(r"<img\b[^>]*>", html or "", flags=re.I):
        tag = m.group(0)
        src = re.search(r"\s(?:data-src|src)=[\"']([^\"']+)[\"']", tag, flags=re.I)
        if not src or src.group(1).startswith("data:"):
            continue
        alt = re.search(r"\salt=[\"']([^\"']*)[\"']", tag, flags=re.I)
        url = urljoin(base, src.group(1).strip())
        if not url.startswith("https://") or re.search(r"\.svg(\?|$)|logo|icon|sprite|pixel|badge", url, flags=re.I):
            continue
        out.append({"url": url, "alt": (alt.group(1).strip() if alt else "")[:120]})
    return out


async def _website_sources(website: str) -> tuple[dict, list]:
    from urllib.parse import urljoin, urlparse
    texts: dict = {}
    images: list = []
    if not website:
        return texts, images
    if not website.startswith("http"):
        website = "https://" + website
    host = urlparse(website).netloc
    async with httpx.AsyncClient() as http:
        home = await _fetch(http, website)
        if not home:
            texts["_note"] = f"Their website ({website}) blocks automated reading, so it was skipped."
            return texts, images
        texts[f"Clinic website home page ({website})"] = _strip_html(home, 7000)
        images += [dict(i, page="home") for i in _images(home, website)]
        links = []
        for href in re.findall(r"href=[\"']([^\"'#]+)[\"']", home, flags=re.I):
            u = urljoin(website, href)
            if urlparse(u).netloc == host and any(h in u.lower() for h in _PAGE_HINTS) and u not in links:
                links.append(u)
        for u in links[:4]:
            page = await _fetch(http, u)
            if page:
                texts[f"Clinic website page ({u})"] = _strip_html(page, 6000)
                images += [dict(i, page=u) for i in _images(page, u)]
    seen, uniq = set(), []
    for i in images:
        if i["url"] not in seen:
            seen.add(i["url"])
            uniq.append(i)
    return texts, uniq[:40]


async def _client_website(client_id: int) -> str:
    pool = await get_pool()
    async with pool.acquire() as conn:
        w = await conn.fetchval(
            "SELECT website FROM contacts WHERE client_id = $1 AND is_client_anchor AND coalesce(website, '') <> '' LIMIT 1",
            client_id,
        )
        if not w:
            rows = await conn.fetch("SELECT answers FROM client_onboarding_responses WHERE client_id = $1", client_id)
            for r in rows:
                a = r["answers"]
                a = json.loads(a) if isinstance(a, str) else (a or {})
                for k in ("business_website_url", "name_website"):
                    m = re.search(r"(https?://)?([a-z0-9-]+\.)+[a-z]{2,}(/\S*)?", str(a.get(k) or ""), flags=re.I)
                    if m:
                        w = m.group(0)
                        break
                if w:
                    break
    return (w or "").strip()


def _luminance(hex_color: str) -> float:
    try:
        r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    except (ValueError, IndexError):
        return 1.0
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def _brand_colors(html: str) -> list[str]:
    """Saturated hex colors in the funnel's CSS, most used first (greys,
    near-white and near-black dropped)."""
    import colorsys
    counts: dict[str, int] = {}
    for m in re.finditer(r"#([0-9a-fA-F]{6})\b", html or ""):
        h = "#" + m.group(1).lower()
        r_, g_, b_ = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
        _, l_, s_ = colorsys.rgb_to_hls(r_, g_, b_)
        if s_ < 0.25 or l_ < 0.12 or l_ > 0.9:
            continue
        counts[h] = counts.get(h, 0) + 1
    return [c for c, _ in sorted(counts.items(), key=lambda x: -x[1])][:8]


async def propose_page_details(client_id: int) -> dict:
    base = await gather_sources(client_id)
    base.pop("Their existing Calendly booking (event type + availability)", None)
    site_texts, images = await _website_sources(await _client_website(client_id))
    site_note = site_texts.pop("_note", None)
    # The funnel page was built from their site: full text (testimonials sit
    # low on the page) and its real photos.
    pool = await get_pool()
    async with pool.acquire() as conn:
        lp = await conn.fetchrow(
            "SELECT slug, html, hero_r2_key FROM landing_pages WHERE client_id = $1 ORDER BY created_at DESC LIMIT 1", client_id,
        )
    if lp and lp["html"]:
        for k in [k for k in base if k.startswith("Funnel landing page text")]:
            base.pop(k)
        base[f"Funnel landing page text (/lp/{lp['slug']})"] = _strip_html(lp["html"], 14000)
        if lp["hero_r2_key"]:
            images.insert(0, {"url": f"/lp/{lp['slug']}/hero-image", "alt": "funnel hero photo (from their site)", "page": "funnel"})
        brand_colors = _brand_colors(lp["html"])
        for m in re.finditer(r"<img\b[^>]*>", lp["html"], flags=re.I):
            src = re.search(r"\ssrc=[\"']([^\"']+)[\"']", m.group(0), flags=re.I)
            alt = re.search(r"\salt=[\"']([^\"']*)[\"']", m.group(0), flags=re.I)
            url = src.group(1).strip() if src else ""
            if url.startswith("/lp/") or (url.startswith("https://") and not re.search(r"icon|\.svg", url, flags=re.I)):
                images.append({"url": url, "alt": (alt.group(1) if alt else "")[:120], "page": "funnel"})
    else:
        brand_colors = []
    # Photos and logos the client uploaded in their portal (what the ads used).
    async with pool.acquire() as conn:
        ups = await conn.fetch(
            "SELECT id, file_name, notes FROM client_uploads WHERE client_id = $1 "
            "AND (file_type LIKE 'image/%' OR file_name ~* '\\.(jpe?g|png|webp)$') ORDER BY uploaded_at DESC LIMIT 25",
            client_id,
        )
    images = [{"url": f"/book-asset/{client_id}/{u['id']}", "alt": f"portal upload: {u['file_name']}" + (f" ({u['notes']})" if u["notes"] else ""),
               "page": "client portal upload"} for u in ups] + images
    sources = {**base, **site_texts}
    if ups:
        sources["Client portal uploads"] = f"{len(ups)} image(s) the clinic uploaded (listed in IMAGES)"
    body = "\n\n".join(f"=== {k} ===\n{v}" for k, v in sources.items())
    img_list = "\n".join(f"[{i}] {im['url']}  alt=\"{im['alt']}\"  (on {im['page']})" for i, im in enumerate(images)) or "(none)"
    api = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    resp = await api.messages.create(
        model=_MODEL, max_tokens=3000, system=_PAGE_SYSTEM, tools=[_PAGE_TOOL], tool_choice={"type": "auto"},
        messages=[{"role": "user", "content": f"SOURCES:\n\n{body}\n\nIMAGES:\n{img_list}\n\n"
                   f"BRAND COLORS (from their funnel, most used first): {', '.join(brand_colors) or '(none)'}\n\n"
                   "Fill in the booking page's trust section by calling propose_page_details. Reply with only that tool call."}],
    )
    r = next((b.input for b in resp.content if b.type == "tool_use"), None)
    if not r:
        raise RuntimeError("Claude didn't return page details")

    # Verify against the sources: drop anything not actually there.
    corpus = _norm(body)
    notes = list(r.get("notes") or [])
    reviews = []
    for rv in (r.get("reviews") or [])[:3]:
        text = (rv.get("text") or "").strip().strip("\"“”")
        if len(text) >= 20 and _norm(text) in corpus:
            author = (rv.get("author") or "").strip().split(" ")[0]
            reviews.append({"text": text[:400], "author": author if author and _norm(author) in corpus else ""})
        elif text:
            notes.append("Dropped a review that didn't match the source word for word.")
    rating, count = r.get("review_rating"), r.get("review_count")
    if rating is not None:
        rs = f"{float(rating):.1f}"
        if not (1 <= float(rating) <= 5 and (rs in body or rs.rstrip("0").rstrip(".") + " star" in body.lower())):
            rating = None
    if count is not None and str(int(count)) not in body:
        count = None
    def _pick(key):
        i = r.get(key)
        return images[i]["url"] if isinstance(i, int) and 0 <= i < len(images) else None
    photo, logo = _pick("photo_index"), _pick("logo_index")
    if logo and logo == photo:
        logo = None
    # Brand color: the funnel's most-used color that still reads with white
    # button text (deterministic; the model's pick drifted to off-brand shades).
    accent = next((c for c in brand_colors if _luminance(c) <= 0.45), None)
    # Logo isn't auto-filled: the model can't see image quality (it picked a
    # blurry newsletter JPG for Pinnacle). Set it by hand in Page details.
    logo = None
    name = (r.get("provider_name") or "").strip() or None
    if name and _norm(name.split()[-1]) not in corpus:
        name = None
    return {
        "provider_name": name,
        "provider_title": (r.get("provider_title") or "").strip() or None,
        "photo_url": photo, "logo_url": logo, "accent_color": accent,
        "what_to_expect": [x.strip()[:80] for x in (r.get("what_to_expect") or []) if x.strip()][:4],
        "review_rating": rating, "review_count": count, "reviews": reviews,
        "notes": notes + ([site_note] if site_note else []), "sources_used": list(sources.keys()),
    }


async def apply_page_details(client_id: int, overwrite: bool = False) -> dict:
    """Fills Page details from propose_page_details(). Only empty fields
    unless overwrite. Records when and from what."""
    from decimal import Decimal
    p = await propose_page_details(client_id)
    pool = await get_pool()
    async with pool.acquire() as conn:
        s = await conn.fetchrow("SELECT * FROM booking_settings WHERE client_id = $1", client_id)
        if not s:
            raise ValueError("booking settings not created yet")
        cur_reviews = s["reviews"]
        cur_reviews = json.loads(cur_reviews) if isinstance(cur_reviews, str) else (cur_reviews or [])
        new = {
            "provider_name": p["provider_name"], "provider_title": p["provider_title"], "photo_url": p["photo_url"],
            "logo_url": p["logo_url"],
            "what_to_expect": "\n".join(p["what_to_expect"]) or None,
            "review_rating": Decimal(f"{float(p['review_rating']):.1f}") if p["review_rating"] is not None else None,
            "review_count": p["review_count"],
        }
        updates = {k: v for k, v in new.items() if v not in (None, "") and (overwrite or s[k] in (None, ""))}
        if p["reviews"] and (overwrite or not cur_reviews):
            updates["reviews"] = json.dumps(p["reviews"])
        # Brand color replaces the stock blue (or anything, on overwrite).
        if p["accent_color"] and (overwrite or (s["accent_color"] or "").lower() in ("", "#2f6fd6")):
            updates["accent_color"] = p["accent_color"]
        filled = list(updates)
        note = (("Filled: " + ", ".join(filled) if filled else "Nothing new found")
                + ". From: " + ", ".join(p["sources_used"])
                + ("." if not p["notes"] else ". Notes: " + " ".join(p["notes"][:4])))
        updates["page_autofill_note"] = note[:1500]
        sets = ", ".join(f"{k} = ${i}" + ("::jsonb" if k == "reviews" else "") for i, k in enumerate(updates, start=2))
        await conn.execute(
            f"UPDATE booking_settings SET {sets}, page_autofilled_at = now(), updated_at = now() WHERE client_id = $1",
            client_id, *updates.values(),
        )
    return {"filled": filled, "notes": p["notes"], "sources_used": p["sources_used"]}
