"""
Automatic Marketing Setup for a newly closed client: everything on the
Clients tab's Marketing Setup checklist that doesn't need something the
client has to hand over first.

Fired in the background by routers/appointments.py the moment a discovery
call's appointment is marked Closed (right after onboarding_sequence.py's
ensure_client_portal() builds the client + portal), and on demand from the
Marketing Setup tab's RUN AUTO-SETUP button (POST
/clients/{id}/marketing-config/autosetup). Each step runs on its own: a
failure is recorded and the rest still run.

1. Client portal: already built by ensure_client_portal(); recorded here.
2. Landing page: if a Patient Acquisition Blueprint was published for the
   client as a prospect, its funnel (the one they were shown on the sales
   call, offer, images and all) is reused as-is. Otherwise scrapes the
   practice's own site (design-agent's
   scrape_prospect_site.py: text, computed brand colors, logo, photos) and
   has Claude write a single-page free-consultation (Google Meet) booking funnel in
   their brand (no prices or other offers unless the client's onboarding
   answers name one),
   following design-agent's funnel-building references. Hosted on
   landing_pages at /lp/{slug} (the branded pages domain), registered as a
   client_websites row so the portal's Website tab tracks it. Every CTA
   points at /lp/{slug}/book, which redirects to the client's Calendly once
   it's connected (routers/landing_pages.py).
3. SMS marketing: buys the client's Twilio number (client_sms.py) in their
   own area code, with SMS + call-forward webhooks wired. A2P 10DLC
   registration still needs the client's EIN, so it stays manual.
4. Response AI: writes the agent's context from the scraped site + whatever
   is on file (context_gen.py), fills a default 5-stage sequence and rules,
   and switches the agent on.
5. SMS/Email automations: confirms the reminder / no-show / cancellation /
   follow-up copy seeded on client creation (routers/clients.py, already
   written around the free consultation) is in place; it sends from the
   client's own number/mailbox with no further wiring.

With a blueprint, the client's offer is whatever that funnel sells, so
_offer_copy() has Claude rewrite the free-consult wording in the Response
AI's sequence + price rule (step 4) and in every seeded message still at
its default text (step 5) around it, and the blueprint's verified practice
facts (its demo chat's context) go into the Response AI context.
6. Email marketing: picks the outreach subdomain (mail.<their domain>). The
   DNS records need the client's registrar, so the rest stays manual.

Paid ad creatives are left alone (they need the client's ad account).
Steps that already have a value (a number, a context, a URL) are skipped,
never overwritten, so a re-run only fills gaps. Progress lands in
client_marketing_config.autosetup and the matching guide_progress slots.
"""
import asyncio
import base64
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from html import escape, unescape
from pathlib import Path
from urllib.parse import urlparse

import anthropic

import client_sms
import context_gen
from db import get_pool

_REPO = Path(__file__).resolve().parents[2]
_DESIGN_TOOLS = _REPO / "design-agent" / "tools"
_DESIGN_REFS = _REPO / "design-agent" / "references"

_MODEL = os.environ.get("AUTOSETUP_CLAUDE_MODEL", "claude-opus-5-5")
_DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "https://digigrowth-brain-production.up.railway.app").rstrip("/")

# A run claimed longer ago than this is treated as dead (container restart
# mid-run), so RUN AUTO-SETUP can take it over.
_STALE_RUN_SECONDS = 30 * 60

# Strong refs so background tasks aren't garbage-collected mid-run.
_tasks: set[asyncio.Task] = set()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------- entry points

def kick_off(client_id: int, force: bool = False) -> None:
    task = asyncio.create_task(run(client_id, force=force))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def kick_off_for_contact(contact_id: str | None) -> None:
    """Called from appointments.py on Closed, after ensure_client_portal().
    Only the contact's own anchor client (the deal it closed), never a
    client whose lead this contact is."""
    if not contact_id:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        client_id = await conn.fetchval(
            "SELECT client_id FROM contacts WHERE id = $1 AND is_client_anchor", contact_id,
        )
    if client_id:
        kick_off(client_id)


async def _claim(client_id: int, force: bool) -> bool:
    """Marks the run started. Without force, a client that's already been
    auto-set-up (re-closing the same appointment) is left alone."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "INSERT INTO client_marketing_config (client_id) VALUES ($1) ON CONFLICT (client_id) DO NOTHING",
                client_id,
            )
            raw = await conn.fetchval(
                "SELECT autosetup FROM client_marketing_config WHERE client_id = $1 FOR UPDATE", client_id,
            )
            current = json.loads(raw) if isinstance(raw, str) else (raw or {})
            state = current.get("state")
            if state == "running":
                started = current.get("started_at")
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(started)).total_seconds() if started else 1e9
                if age < _STALE_RUN_SECONDS:
                    return False
            elif state and not force:
                return False
            await conn.execute(
                "UPDATE client_marketing_config SET autosetup = $2::jsonb, updated_at = now() WHERE client_id = $1",
                client_id, json.dumps({"state": "running", "started_at": _now(), "steps": current.get("steps", {})}),
            )
    return True


async def _record(client_id: int, **fields) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE client_marketing_config SET autosetup = autosetup || $2::jsonb, updated_at = now() WHERE client_id = $1",
            client_id, json.dumps(fields),
        )


async def _record_step(client_id: int, key: str, status: str, detail: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """UPDATE client_marketing_config
               SET autosetup = jsonb_set(
                     CASE WHEN autosetup ? 'steps' THEN autosetup ELSE autosetup || '{"steps": {}}'::jsonb END,
                     ARRAY['steps', $2::text], $3::jsonb),
                   updated_at = now()
               WHERE client_id = $1""",
            client_id, key, json.dumps({"status": status, "detail": detail[:600], "at": _now()}),
        )


async def _check_guide_steps(client_id: int, guide: str, indexes: list[int]) -> None:
    """Ticks guide_progress[guide][i] for steps this run actually did, the
    same slots the SET UP GUIDE checkboxes write."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """UPDATE client_marketing_config
               SET guide_progress = guide_progress || jsonb_build_object(
                     $2::text, COALESCE(guide_progress -> $2, '{}'::jsonb) || $3::jsonb)
               WHERE client_id = $1""",
            client_id, guide, json.dumps({str(i): True for i in indexes}),
        )


async def _set_config(client_id: int, **fields) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        sets = ", ".join(f"{k} = ${i}" for i, k in enumerate(fields, start=2))
        await conn.execute(
            f"UPDATE client_marketing_config SET {sets}, updated_at = now() WHERE client_id = $1",
            client_id, *[json.dumps(v) if isinstance(v, (dict, list)) else v for v in fields.values()],
        )


# ---------------------------------------------------------------- the run

async def run(client_id: int, force: bool = False) -> None:
    try:
        if not await _claim(client_id, force):
            print(f"[autosetup] client {client_id}: already ran or running, skipped")
            return
        ctx = await _load(client_id)
        print(f"[autosetup] client {client_id} ({ctx['business']}): starting")
        ctx["site"] = await _scrape(ctx["website"]) if ctx["website"] else None
        ctx["blueprint"] = await _blueprint(ctx["anchor"].get("id"))
        if ctx["blueprint"]:
            try:
                ctx["offer_copy"] = await _offer_copy(client_id, ctx)
            except Exception as e:
                ctx["offer_copy_error"] = f"{type(e).__name__}: {e}"
                print(f"[autosetup] client {client_id}: blueprint offer copy failed: {ctx['offer_copy_error']}")

        steps = [
            ("client_portal", _step_portal),
            ("landing_page", _step_landing_page),
            ("sms", _step_sms),
            ("response_ai", _step_response_ai),
            ("automations", _step_automations),
            ("email", _step_email),
        ]
        for key, fn in steps:
            try:
                status, detail = await fn(client_id, ctx)
            except Exception as e:
                status, detail = "error", f"{type(e).__name__}: {e}"
                print(f"[autosetup] client {client_id} step {key} failed: {detail}")
            await _record_step(client_id, key, status, detail)
        await _record(client_id, state="done", finished_at=_now())
        print(f"[autosetup] client {client_id}: done")
    except Exception as e:
        print(f"[autosetup] client {client_id} run failed: {e}")
        await _record(client_id, state="error", finished_at=_now(), error=str(e)[:600])


async def _load(client_id: int) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        client = await conn.fetchrow("SELECT * FROM clients WHERE id = $1", client_id)
        if not client:
            raise ValueError(f"client {client_id} not found")
        anchor = await conn.fetchrow(
            "SELECT id, business, owner, website, city, state, phone FROM contacts "
            "WHERE client_id = $1 AND is_client_anchor LIMIT 1",
            client_id,
        )
        cfg = await conn.fetchrow("SELECT * FROM client_marketing_config WHERE client_id = $1", client_id)
    anchor = dict(anchor) if anchor else {}
    website = (anchor.get("website") or "").strip()
    if website and not website.startswith("http"):
        website = "https://" + website
    return {
        "client": dict(client),
        "anchor": anchor,
        "cfg": dict(cfg),
        "business": (anchor.get("business") or client["name"] or "").strip(),
        "website": website,
        "city": ", ".join(x for x in [anchor.get("city"), anchor.get("state")] if x),
        "phone": client["phone"] or anchor.get("phone") or "",
    }


_SOCIAL_HOSTS = ("tiktok", "facebook", "instagram", "twitter", "linkedin", "youtube", "yelp", "google", "social", "x-logo")


def _full_res(src: str) -> str:
    """The rendered page's image URL is the size it's displayed at, often a
    few hundred px, which looks blurry once the funnel shows it bigger.
    Site builders serve the original from a predictable URL; the scraper's
    own compression then caps it at 1100px."""
    # Wix: static.wixstatic.com/media/<id>/v1/fill/w_310,.../<name> -> /media/<id>
    m = re.match(r"(https://static\.wixstatic\.com/media/[^/]+)/v1/", src or "")
    if m:
        return m.group(1)
    # Squarespace: images.squarespace-cdn.com/...?format=300w -> 1500w
    if "squarespace-cdn.com" in (src or ""):
        return re.sub(r"format=\d+w", "format=1500w", src) if "format=" in src else src + "?format=1500w"
    return src


async def _scrape(url: str) -> dict | None:
    """Reuses design-agent's scraper (same one the funnel-building skill
    runs locally): page text from requests+BS4, computed colors + logo +
    photos from a Playwright render, images embedded as data URIs."""
    if str(_DESIGN_TOOLS) not in sys.path:
        sys.path.insert(0, str(_DESIGN_TOOLS))
    import scrape_prospect_site as sps

    text = await asyncio.to_thread(sps.scrape_text, url)
    data: dict = {}
    try:
        with tempfile.TemporaryDirectory() as tmp:
            data = await asyncio.wait_for(sps.capture(url, Path(tmp) / "hero.png"), timeout=90)
    except Exception as e:
        print(f"[autosetup] browser capture failed for {url}: {e}")
    # The scraper's "first small image in the header" match can land on a
    # social icon (it picked a TikTok logo off advantagetherapy.vegas).
    logo_src = data.get("logo_src") or ""
    if any(n in logo_src.lower() for n in _SOCIAL_HOSTS):
        logo_src = ""
    logo = await asyncio.to_thread(sps._fetch_as_data_uri, logo_src) if logo_src else None
    photos = []
    for src in (data.get("photo_srcs") or [])[:4]:
        uri = await asyncio.to_thread(sps._fetch_as_data_uri, _full_res(src), True)
        if uri:
            photos.append(uri)
    palette = {k: data.get(k) for k in ("body", "button", "header", "h1", "theme_color")}
    return {"text": text, "palette": palette, "logo": logo, "photos": photos}


# ---------------------------------------------------------------- steps

async def _step_portal(client_id: int, ctx: dict) -> tuple[str, str]:
    return "done", f"Portal live: {_DASHBOARD_URL}/portal/{ctx['client']['portal_token']}"


def _area_code(phone: str) -> str | None:
    digits = re.sub(r"\D", "", phone or "")[-10:]
    return digits[:3] if len(digits) == 10 else None


async def _step_sms(client_id: int, ctx: dict) -> tuple[str, str]:
    if ctx["cfg"].get("twilio_number"):
        return "skipped", f"Already has {ctx['cfg']['twilio_number']}"
    area = _area_code(ctx["phone"])
    try:
        row = await client_sms.provision_client_number(client_id, area_code=area)
    except RuntimeError:
        # No numbers left in their area code: take any US local number.
        row = await client_sms.provision_client_number(client_id, area_code=None)
    ctx["cfg"]["twilio_number"] = row["twilio_number"]
    await _check_guide_steps(client_id, "sms", [0, 2])
    return "done", (
        f"Bought {row['twilio_number']} (calls forward to the client's phone). "
        "Still manual: A2P 10DLC registration with their legal name + EIN."
    )


_DEFAULT_SEQUENCE = [
    "Open by introducing yourself by first name, mention that you saw they filled out {business}'s form "
    "on Facebook, thank them for reaching out, and ask ONE question about what pain or issue got them "
    "looking into PT. Save follow-up details (how long, what they've tried) for a later message.",
    "Briefly validate what they shared and connect it to what {business} actually does for that exact "
    "situation, in plain language, without over-explaining or sounding like a sales pitch.",
    "Introduce the free consultation as the natural next step: a quick Google Meet video call to see if "
    "{business} is a good fit, framed as low-pressure, not a commitment.",
    "If they hesitate or raise a concern (cost, insurance, time, does this actually work), address it "
    "briefly and point back to the free consultation as the easiest way to get a real answer.",
    "Once they're ready, send the booking link so they can pick a time. When they confirm they booked, "
    "confirm it back in one message and set expectations for what happens next.",
]

_BASE_RULES = (
    "1. Keep every text to 30 words or fewer. Short, natural, and easy to read on a phone. If more needs "
    "to be said, send it as a natural follow-up text rather than one long message.\n"
    "2. Never use em dashes, curly quotes, or emoji.\n"
    "3. Never sound scripted or repeat the same phrasing twice in one conversation.\n"
    "4. Never ask two questions in one text.\n"
)
_DEFAULT_PRICE_RULE = (
    "5. Never quote prices or mention any discount or special. Steer pricing questions to the free "
    "consultation, where the team goes over specifics."
)
_DEFAULT_RULES = _BASE_RULES + _DEFAULT_PRICE_RULE


def _blueprint_note(ctx: dict) -> str:
    if ctx.get("offer_copy_error"):
        return (f" Rewriting it for their blueprint's offer failed ({ctx['offer_copy_error'][:200]}), so it's still "
                "the free-consult default: fix it by hand before it goes live.")
    return ""


async def _step_response_ai(client_id: int, ctx: dict) -> tuple[str, str]:
    cfg = ctx["cfg"]
    offer = ctx.get("offer_copy")
    done = []
    updates: dict = {}
    if not (cfg.get("response_ai_context") or "").strip():
        site_text = (ctx["site"] or {}).get("text")
        source_text = site_text
        if ctx.get("blueprint") and ctx["blueprint"]["chat_context"]:
            # First, so the website cap in context_gen never cuts it.
            source_text = (
                "Verified practice facts and offer (from their Patient Acquisition Blueprint):\n"
                f"{ctx['blueprint']['chat_context']}\n\n{site_text or ''}"
            )
        context = await context_gen.generate_context(client_id, website_text=source_text, auto=True)
        book_url = ctx.get("book_url")
        if book_url:
            context += (
                f"\n\n## Booking link\nSend this when they're ready to book their "
                f"{offer['offer_name'] if offer else 'free consultation'}: {book_url}"
            )
        updates["response_ai_context"] = context
        done.append("context written" + (" from their blueprint and website" if source_text != site_text
                                         else " from their website" if site_text else " (no website on file)"))
    seq = cfg.get("response_ai_sequence")
    if isinstance(seq, str):
        seq = json.loads(seq)
    if not seq:
        updates["response_ai_sequence"] = offer["sequence"] if offer else [
            s.replace("{business}", ctx["business"] or "the practice") for s in _DEFAULT_SEQUENCE
        ]
        done.append("5-stage sequence" + (f" for the {offer['offer_name']}" if offer else ""))
    if not (cfg.get("response_ai_rules") or "").strip():
        updates["response_ai_rules"] = _BASE_RULES + offer["price_rule"] if offer else _DEFAULT_RULES
        updates["response_ai_max_words"] = cfg.get("response_ai_max_words") or 30
        updates["response_ai_min_delay_seconds"] = cfg.get("response_ai_min_delay_seconds") or 15
        done.append("rules (30 words, 15s delay)")
    if cfg.get("twilio_number") and not cfg.get("response_ai_enabled"):
        updates["response_ai_enabled"] = True
        done.append("switched on")
    if not updates:
        return "skipped", "Already configured"
    await _set_config(client_id, **updates)
    await _check_guide_steps(client_id, "response_ai", [0, 2, 3, 4])
    note = "" if updates.get("response_ai_enabled") or cfg.get("response_ai_enabled") else " Not switched on: no SMS number yet."
    summary = ", ".join(done)
    return "done", summary[:1].upper() + summary[1:] + "." + note + _blueprint_note(ctx) + (
        " Still manual: connect their Calendly and Facebook Page (Lead Ads), then test."
    )


async def _step_email(client_id: int, ctx: dict) -> tuple[str, str]:
    if ctx["cfg"].get("email_subdomain"):
        return "skipped", f"Subdomain already set: {ctx['cfg']['email_subdomain']}"
    host = urlparse(ctx["website"]).hostname if ctx["website"] else None
    if not host:
        return "skipped", "No website on file to pick an outreach subdomain from"
    domain = host[4:] if host.startswith("www.") else host
    sub = f"mail.{domain}"
    await _set_config(client_id, email_subdomain=sub)
    await _check_guide_steps(client_id, "email", [0])
    return "done", (
        f"Outreach subdomain set to {sub}. Still manual: the DNS records at the client's registrar, "
        "the mailbox, and the refresh token."
    )


# ---------------------------------------------------------------- landing page

def _slugify(text: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", text.lower())).strip("-")[:48] or "practice"


def _tracking_snippet(website_id: int) -> str:
    """register_client_website.py's snippet, adapted: CTAs point at
    /lp/{slug}/book rather than calendly.com, and that redirect forwards
    utm_content to Calendly for the Meta attribution."""
    return f"""<script>
(function(){{
  var WEBSITE_ID = "{website_id}";
  function fromMeta(){{
    try {{
      if (new URLSearchParams(window.location.search).has("fbclid")) return true;
      var ref = (document.referrer || "").toLowerCase();
      return ["facebook.com","fb.com","instagram.com"].some(function(d){{ return ref.indexOf(d) !== -1; }});
    }} catch(e) {{ return false; }}
  }}
  var FROM_META = fromMeta();
  try {{
    navigator.sendBeacon("{_DASHBOARD_URL}/track/view-event",
      new Blob([JSON.stringify({{source:"client_website", event_type:"view", content_key:WEBSITE_ID, from_meta:FROM_META}})], {{type:"application/json"}}));
  }} catch(e) {{}}
  if (FROM_META) {{
    document.querySelectorAll('a[href*="/book"]').forEach(function(el){{
      try {{ var u = new URL(el.href, window.location.href); u.searchParams.set("utm_content", "meta"); el.href = u.toString(); }} catch(e) {{}}
    }});
  }}
}})();
</script>"""


_PAGE_SYSTEM = """You build single-page, conversion-optimized landing pages for independent physical \
therapy practices, for their Meta ad traffic. The page is 100% the practice's own brand talking to its \
own patients, driving one action: book a free consultation (a Google Meet video call). Follow the CRO rulebook and reuse the \
worked example's structure and CSS approach (token system, hero grid areas, review wall, trust bar, \
floating sticky mobile CTA), re-deriving every color, font pairing, and word for this practice. Never \
reuse the example's copy, testimonials, fonts, or colors.

Hard rules:
- Ground every specific claim in the material provided. Never invent a testimonial, statistic, \
credential, price, or urgency claim. Use real reviews only if they appear in the scraped text, quoted \
verbatim with first name or initial only. If there are none, leave the proof section to what is real \
(credentials, specialties, years, location) rather than fabricating.
- The offer is a free consultation held as a Google Meet video call, so patients can do it from \
home; say so on the page. Don't add any other offer, discount, special, intro price, or "limited \
spots" framing unless the onboarding answers name it, and don't quote prices. Don't state the call's \
length unless the material says. CTAs: \
"Book your free consultation" or close variants.
- Every CTA link is exactly href="{{BOOK_URL}}". No other link destinations, no nav menu, no footer link list.
- The {{LOGO}} image was auto-detected and can be wrong. Use it only if it clearly is this practice's own logo or wordmark; if it's a social media icon or anything else, set the practice name in type as the wordmark instead.
- Images: use src="{{LOGO}}" for the logo and src="{{PHOTO_1}}" ... for the photos listed as \
available. Use only the placeholders listed as available; never hotlink or invent image URLs.
- Brand: use the practice's real colors from the palette. Pick a real Google Fonts pairing that suits \
the brand.
- Mobile-first, one self-contained HTML document, inline CSS, vanilla JS only, fast to load. Copy \
must not use em dashes.

Return only the complete HTML document, starting with <!DOCTYPE html> and ending with </html>."""


def _read_ref(name: str) -> str:
    try:
        return (_DESIGN_REFS / name).read_text(encoding="utf-8")
    except OSError:
        return ""


def _image_block(data_uri: str) -> dict | None:
    m = re.match(r"data:(image/(?:jpeg|png|gif|webp));base64,(.+)", data_uri or "", re.S)
    if not m:
        return None
    return {"type": "image", "source": {"type": "base64", "media_type": m.group(1), "data": m.group(2)}}


async def _generate_page_html(ctx: dict) -> str:
    site = ctx["site"] or {}
    content: list[dict] = []
    available = []
    if site.get("logo"):
        block = _image_block(site["logo"])
        if block:
            content += [{"type": "text", "text": "{{LOGO}}:"}, block]
        available.append("{{LOGO}}")
    for i, uri in enumerate(site.get("photos") or [], start=1):
        block = _image_block(uri)
        if block:
            content += [{"type": "text", "text": f"{{{{PHOTO_{i}}}}}:"}, block]
            available.append(f"{{{{PHOTO_{i}}}}}")

    onboarding = ""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT section, answers FROM client_onboarding_responses WHERE client_id = $1 AND completed_at IS NOT NULL",
            ctx["client"]["id"],
        )
    if rows:
        onboarding = "\n\n".join(f"## {r['section']}\n{r['answers']}" for r in rows)

    brief = f"""Practice: {ctx['business']}
Owner: {ctx['anchor'].get('owner') or 'unknown'}
Location: {ctx['city'] or 'unknown'}
Website: {ctx['website']}
Phone: {ctx['phone'] or 'unknown'}

Available image placeholders (shown above): {', '.join(available) or 'none, build the page without photos'}

Computed brand colors from their live site:
{json.dumps(site.get('palette') or {}, indent=2)}

Onboarding answers:
{onboarding or '(none yet)'}

Scraped text from their website:
{(site.get('text') or '')[:30000]}

--- CRO rulebook (cro-funnel-principles.md) ---
{_read_ref('cro-funnel-principles.md')}

--- Worked example (example-client-funnel.html, structure and CSS only) ---
{_read_ref('example-client-funnel.html')}

Build the landing page now."""
    content.append({"type": "text", "text": brief})

    client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    async with client.messages.stream(
        model=_MODEL,
        max_tokens=64000,
        output_config={"effort": "high"},
        system=_PAGE_SYSTEM,
        messages=[{"role": "user", "content": content}],
    ) as stream:
        message = await stream.get_final_message()
    if message.stop_reason == "refusal":
        raise RuntimeError("Claude declined to write the page")
    text = "".join(b.text for b in message.content if b.type == "text")
    start = text.lower().find("<!doctype")
    end = text.lower().rfind("</html>")
    if start == -1 or end == -1:
        raise RuntimeError(f"No complete HTML document in the response (stop_reason={message.stop_reason})")
    return text[start:end + len("</html>")]


async def _blueprint(contact_id: str | None) -> dict | None:
    """The client's Patient Acquisition Blueprint, if one was published for
    them as a prospect: its funnel document (the phone preview iframe's
    srcdoc, build_blueprint.py) and its demo chat's practice facts. Blueprint
    rows are the ones published with a chat_context
    (publish_landing_page.py --chat-context)."""
    if not contact_id:
        return None
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT html, chat_context FROM landing_pages WHERE contact_id = $1 AND chat_context IS NOT NULL "
            "AND client_id IS NULL ORDER BY created_at DESC LIMIT 1",
            contact_id,
        )
    m = re.search(r'id="phoneFrame"[^>]*?srcdoc="([^"]*)"', row["html"] or "") if row else None
    return {"funnel": unescape(m.group(1)), "chat_context": row["chat_context"]} if m else None


_MERGE_FIELD = re.compile(r"\{[a-z_]+\}")

_OFFER_COPY_SYSTEM = """You adapt a physical therapy practice's patient-facing texts and emails to the offer \
its Meta ads funnel sells. The copy below was written around a default offer (a free consultation held as a \
Google Meet video call). The practice's real offer is in the material: its funnel page and the facts behind it. \
Rewrite only what's about the offer: what it's called, what it is, whether it's in person or a video call, where \
it happens, and its price if the material states one. Keep everything else (tone, length, structure, the job of \
each message) as it is.

Hard rules:
- Ground every fact in the material. Never invent a price, duration, address, policy (refunds, insurance, \
cancellations) or claim.
- Keep every merge field ({first_name}, {business}, {date}, {time}, {link}) exactly as written in each \
message; add none and drop none.
- No em dashes, en dashes, curly quotes or emoji anywhere. SMS bodies stay short and plain.
- Reminders for an in-person visit say where to come if the material gives the address, instead of a video link.

Return only a JSON object:
{"offer_name": "<what patients book, as the funnel names it, e.g. \\"$49 Discovery Visit\\">",
 "sequence": ["<the 5 conversation stages for the text agent, rewritten>"],
 "price_rule": "5. <rule 5 for the text agent, rewritten for this offer>",
 "steps": [{"id": <id>, "subject": "<email subject, or null for SMS>", "body": "<message>"}]}"""


def _plain(text: str) -> str:
    """No em/en dashes or curly quotes: in SMS they force UCS-2, doubling
    Twilio's per-segment cost."""
    text = re.sub(r"\s*[—–]\s*", ", ", text)
    return text.translate(str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'}))


async def _offer_copy(client_id: int, ctx: dict) -> dict:
    """Rewrites the free-consult defaults around the blueprint funnel's offer:
    the Response AI's sequence + price rule, and the seeded messages that are
    still exactly their default text (anything edited by hand is left alone)."""
    from routers.clients import _DEFAULT_SEQUENCE_STEPS

    defaults = {(key, order): body for key, order, _label, _channel, _subject, body in _DEFAULT_SEQUENCE_STEPS}
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, sequence_key, step_order, channel, subject, body FROM client_sequence_steps WHERE client_id = $1",
            client_id,
        )
    steps = {r["id"]: dict(r) for r in rows if defaults.get((r["sequence_key"], r["step_order"])) == r["body"]}

    funnel_text = re.sub(r"<(style|script)\b.*?</\1>", " ", ctx["blueprint"]["funnel"], flags=re.S | re.I)
    funnel_text = re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", funnel_text))).strip()
    business = ctx["business"] or "the practice"
    brief = f"""Practice: {business}

--- Practice facts and offer (verified) ---
{ctx['blueprint']['chat_context'] or '(none)'}

--- Funnel page text ---
{funnel_text[:15000]}

--- Text agent conversation stages (default) ---
{json.dumps([s.replace('{business}', business) for s in _DEFAULT_SEQUENCE], indent=1)}

--- Text agent rule 5 (default) ---
{_DEFAULT_PRICE_RULE}

--- Messages (default) ---
{json.dumps([{k: s[k] for k in ('id', 'sequence_key', 'channel', 'subject', 'body')} for s in steps.values()], indent=1)}"""

    client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    async with client.messages.stream(
        model=_MODEL,
        max_tokens=32000,
        output_config={"effort": "medium"},
        system=_OFFER_COPY_SYSTEM,
        messages=[{"role": "user", "content": brief}],
    ) as stream:
        message = await stream.get_final_message()
    text = "".join(b.text for b in message.content if b.type == "text")
    data = json.loads(text[text.find("{"):text.rfind("}") + 1])

    sequence = [_plain(s) for s in data.get("sequence") or [] if isinstance(s, str) and s.strip()]
    price_rule = _plain(data.get("price_rule") or "").strip()
    offer_name = _plain(data.get("offer_name") or "").strip()
    if len(sequence) != 5 or not price_rule.startswith("5.") or not offer_name:
        raise ValueError("Claude's offer copy was incomplete")
    rewritten = {}
    for s in data.get("steps") or []:
        orig = steps.get(s.get("id"))
        body = _plain(s.get("body") or "").strip()
        # A dropped or invented merge field would send broken text: keep the default.
        if not orig or not body or set(_MERGE_FIELD.findall(body)) != set(_MERGE_FIELD.findall(orig["body"])):
            continue
        subject = _plain(s.get("subject") or "").strip() if orig["channel"] == "email" else ""
        if not subject or set(_MERGE_FIELD.findall(subject)) != set(_MERGE_FIELD.findall(orig["subject"] or "")):
            subject = orig["subject"]
        rewritten[orig["id"]] = (subject, body)
    return {"offer_name": offer_name, "sequence": sequence, "price_rule": price_rule, "steps": rewritten}


_DEAD_LINK = re.compile(r'<a\b([^>]*?)\s*\bhref="#"([^>]*)>(.*?)</a>', re.S)


def _adapt_blueprint_funnel(doc: str, book_url: str, business: str) -> str:
    """The blueprint shows the funnel as a preview: its links go nowhere
    (href="#") and the scrollbar is hidden inside the phone frame. Points
    every booking button at /lp/{slug}/book, takes the href off any other
    dead link (e.g. an address chip), and gives it a <title>."""
    def relink(m: re.Match) -> str:
        before, after, inner = m.group(1), m.group(2), m.group(3)
        is_cta = re.search(r'class="[^"]*\b(btn|cta|button)', before + after) or re.search(r"\bbook", inner, re.I)
        href = f' href="{book_url}"' if is_cta else ""
        return f"<a{before}{href}{after}>{inner}</a>"

    doc = _DEAD_LINK.sub(relink, doc)
    doc = re.sub(r"html\{scrollbar-width:none\}|html::-webkit-scrollbar\{display:none\}", "", doc)
    if "<title>" not in doc:
        doc = doc.replace("<head>", f"<head><title>{escape(business)}</title>", 1)
    return doc


async def _step_landing_page(client_id: int, ctx: dict) -> tuple[str, str]:
    pages_base = (os.environ.get("LANDING_PAGES_URL") or _DASHBOARD_URL).rstrip("/")
    pool = await get_pool()
    async with pool.acquire() as conn:
        slug = await conn.fetchval("SELECT slug FROM landing_pages WHERE client_id = $1 ORDER BY created_at LIMIT 1", client_id)
    if slug:
        ctx["book_url"] = f"{pages_base}/lp/{slug}/book"
    if ctx["cfg"].get("landing_page_url"):
        return "skipped", f"Already set: {ctx['cfg']['landing_page_url']}"
    blueprint = (ctx.get("blueprint") or {}).get("funnel")
    if not blueprint and (not ctx["site"] or not (ctx["site"].get("text") or "").strip()):
        return "error", "No website on file (or it couldn't be read) to build the page from. Add it to the linked contact and re-run."

    slug = slug or f"{_slugify(ctx['business'])}-{client_id}"
    page_url = f"{pages_base}/lp/{slug}"
    ctx["book_url"] = f"{page_url}/book"

    if blueprint:
        html = _adapt_blueprint_funnel(blueprint, ctx["book_url"], ctx["business"])
        built = "Reused the funnel from their Patient Acquisition Blueprint, live"
    else:
        html = await _generate_page_html(ctx)
        site = ctx["site"]
        html = html.replace("{{BOOK_URL}}", ctx["book_url"])
        if site.get("logo"):
            html = html.replace("{{LOGO}}", site["logo"])
        for i, uri in enumerate(site.get("photos") or [], start=1):
            html = html.replace(f"{{{{PHOTO_{i}}}}}", uri)
        built = "Built and live"

    async with pool.acquire() as conn:
        async with conn.transaction():
            website_id = await conn.fetchval(
                "SELECT id FROM client_websites WHERE client_id = $1 AND url = $2", client_id, page_url,
            ) or await conn.fetchval(
                "INSERT INTO client_websites (client_id, label, url) VALUES ($1, $2, $3) RETURNING id",
                client_id, "Meta Ads Funnel", page_url,
            )
            snippet = _tracking_snippet(website_id)
            html = html.replace("</body>", f"{snippet}\n</body>", 1) if "</body>" in html else html + snippet
            await conn.execute(
                """INSERT INTO landing_pages (slug, contact_id, business, html, status, client_id)
                   VALUES ($1, $2, $3, $4, 'draft', $5)
                   ON CONFLICT (slug) DO UPDATE SET html = $4, business = $3, client_id = $5""",
                slug, ctx["anchor"].get("id"), ctx["business"] or None, html, client_id,
            )
            await conn.execute(
                "UPDATE client_marketing_config SET landing_page_url = $2, updated_at = now() WHERE client_id = $1",
                client_id, page_url,
            )
    await _check_guide_steps(client_id, "landing_page", [0, 3])
    booking = "" if (ctx["client"].get("calendly_url") or ctx["cfg"].get("calendly_event_type_url")) else (
        " Its book buttons go to their website until their Calendly is connected."
    )
    return "done", f"{built} at {page_url}. Review it before ads run.{booking}"


# ---------------------------------------------------------------- automations

async def _step_automations(client_id: int, ctx: dict) -> tuple[str, str]:
    """The seeded copy is already written around the free consultation, so
    without a blueprint there's nothing to rewrite: confirm it's there and
    tick the guide. With one, _offer_copy()'s rewrites for its offer go in."""
    offer = ctx.get("offer_copy")
    pool = await get_pool()
    async with pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT count(*) FROM client_sequence_steps WHERE client_id = $1", client_id,
        )
        if count and offer:
            for step_id, (subject, body) in offer["steps"].items():
                await conn.execute(
                    "UPDATE client_sequence_steps SET subject = $3, body = $4, updated_at = now() "
                    "WHERE id = $1 AND client_id = $2",
                    step_id, client_id, subject, body,
                )
    if not count:
        return "error", "No sequence copy found for this client (it's normally seeded when the client is created)"
    await _check_guide_steps(client_id, "automations", [1, 2])
    what = (f"{len(offer['steps'])} of {count} messages rewritten for their {offer['offer_name']}; "
            f"reminder / no-show / cancellation / follow-up copy" if offer
            else f"{count} free-consultation reminder / no-show / cancellation / follow-up messages")
    return "done", (
        f"{what} in place on the Sequences tab. They send from the client's own number now; email copy starts "
        "sending once the mailbox is connected." + _blueprint_note(ctx)
    )
