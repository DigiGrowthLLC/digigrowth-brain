"""Marketing Setup v2 (2026-11-16): one repeatable checklist per client.

Replaces the nine index-keyed guides in ClientsPanel.jsx (MARKETING_GUIDES +
SETUP_ORDER_PHASES, ~70 steps). Steps have stable string ids, live here (the
OS tab, guide_autocheck.py and the onboarding agent's
service_delivery_status.py all read them through GET
/api/clients/{id}/setup), and most of them tick themselves from real data.

Progress: client_marketing_config.guide_progress["v2"] = {step_id: true} for
manual ticks and for proofs that need the network (guide_autocheck.py's
10-minute job: the funnel domain serving our funnel). Everything else is
computed live in signals(). A step is done when it's proven OR ticked.

Package: clients.service_package = 'growth' (ads, voice agent, DMs, organic)
or 'foundations' ($500/mo: text agent, reactivation, follow-up + booking
funnel; no ads). Since 2026-11-17 the steps shown follow the client's own
services (client_services.py, answered on their portal intake): a step
with "services" shows when the client has at least one of them. Clients who
never answered fall back to their package's defaults.
"""
from __future__ import annotations

import json
import os

import client_services
from client_services import BOOKING, META, TEXTING
from db import get_pool

PHASES = [
    {"id": "build", "title": "Built automatically",
     "note": "Auto-Setup runs the moment the deal is marked Closed. Review what it made."},
    {"id": "handover", "title": "Client handover",
     "note": "One batched ask on the onboarding call (COPY CLIENT ASK). Each item ticks itself when it lands."},
    {"id": "connect", "title": "Connect and switch on",
     "note": "Mostly buttons once the access above is in."},
    {"id": "ads", "title": "Ads and content",
     "note": "Campaign work stays step by step with your approval (media-buying agent)."},
    {"id": "launch", "title": "Test and launch", "note": ""},
]

# long_lead (Dylan, 2026-11-25) = the step needs someone else's approval or waits on
# time, so it can't be rushed last minute. The OS lists open ones first ("Start
# these first"), the service delivery skill does them first and the morning
# planner books them as the day's first block. The value says what it waits on.
# action = which button(s) the OS shows on the row (ClientSetup in ClientsPanel.jsx).
STEPS = [
    # ---- build
    {"id": "autobuild", "phase": "build", "package": "all", "title": "Auto-Setup built the basics",
     "how": "Client portal, funnel (from their site or the sales-call blueprint), Twilio number in their area code "
            "with call forwarding to the client's phone, text agent context/sequence/rules (switched on), every "
            "message's copy, the booking page details and (Growth) the voice agent. Re-run fills gaps only, never "
            "overwrites.",
     "action": "autosetup"},
    {"id": "review", "phase": "build", "package": "all", "title": "Review what the AI built",
     "how": "Open the funnel, then Agents & Messages: read the text agent's context and rules, and each message "
            "(confirmation, reminders, no-show, cancellation, follow-up). Turn off anything the client doesn't want "
            "and fix wording that doesn't match how they work (no \"give us a call\" if they don't take calls).",
     "action": "review", "legacy": [("automations", 5)]},

    # ---- handover
    {"id": "meta_access", "long_lead": "Waits on the client + Meta permissions (took Pinnacle weeks)", "services": META, "phase": "handover", "package": "growth", "title": "Meta access: Page, Instagram, ad account",
     "how": "Client: Business Settings → Partners → add DigiGrowth (business ID 695946576605909) with the Page, "
            "Instagram and ad account, Full control / Manage campaigns. You: accept the portfolio invite, then "
            "DigiGrowth Business Settings → System users → assign the ad account (Manage campaigns: the spend cap "
            "pauses through it) and the Page. Save both IDs below, then SYNC NOW must succeed. Pilot clients: ads "
            "run on Dylan's card, add it if the account has no payment method.",
     "link": "https://business.facebook.com/settings/partners", "linkLabel": "Business Settings → Partners",
     "fields": [{"key": "meta_ad_account_id", "label": "Ad account ID", "placeholder": "123456789012345"},
                {"key": "meta_page_id", "label": "Page ID", "placeholder": "987654321098765"}],
     "action": "meta_sync"},
    {"id": "calendar", "long_lead": "Waits on the client (calendar share, Stripe verification)", "services": BOOKING, "phase": "handover", "package": "all", "title": "Calendar shared (+ Stripe if the visit is paid)",
     "how": "Client shares the Google Calendar they book patients on with dylanrg@digigrowthllc.com, \"Make changes "
            "to events\" (their portal walks them through it). Paid visit: they click \"Connect Stripe to Get Paid\" "
            "in their portal. GoHighLevel/Calendly clients: see the Booking step instead.",
     "action": "booking"},
    {"id": "dns", "long_lead": "Waits on DNS access + propagation", "services": ["funnel"], "phase": "handover", "package": "all", "title": "Funnel on their own domain",
     "how": "Find where DNS is really edited (Resources shows the detected DNS host; often not the registrar). "
            "Get access there, or send the client the record: CNAME, host \"go\", value cname.vercel-dns.com. "
            "Never touch the root @ records. Save the domain below, then run deploy_client_funnels.py (the onboarding "
            "agent does it). Ticks itself once https://<domain>/ serves the funnel.",
     "fields": [{"key": "funnel_domain", "label": "Funnel domain", "placeholder": "go.clientdomain.com"}],
     "legacy": [("landing_page", 2)]},
    {"id": "booking_domain", "long_lead": "Waits on DNS access + propagation", "services": BOOKING, "phase": "handover", "package": "all",
     "title": "Booking link on their own domain",
     "how": "Same DNS access as the funnel step. Add a second record: CNAME, host \"book\", value "
            "cname.vercel-dns.com (never touch the root @ records). Save the domain below, then run "
            "deploy_client_funnels.py (the onboarding agent does it): it puts their booking page at the root of "
            "that host. Needs their booking page made first (the Booking step's AUTOFILL creates it). Then run "
            "the service delivery skill: it checks the domain once and ticks this step when "
            "https://<domain>/ serves their booking page. From then on every booking link we hand out (texts, AI "
            "agents, portal, Booking Links) uses it. It's not re-checked in the background: if the domain ever "
            "breaks, run the check again and links fall back to ours.",
     "fields": [{"key": "booking_domain", "label": "Booking domain", "placeholder": "book.clientdomain.com"}]},
    {"id": "a2p", "long_lead": "Twilio/carrier review takes days to weeks; a rejection restarts it", "services": TEXTING, "phase": "handover", "package": "all", "title": "A2P 10DLC registered (marketing use case)",
     "how": "Needs their legal business name + EIN (exactly as on the IRS letter). Register the Brand right away on "
            "the client's Twilio subaccount. Submit the Campaign (Low Volume Mixed, covers marketing) only AFTER the "
            "Instant Form with its consent disclaimer is published: the opt-in field must quote each consent line "
            "word for word and link a public screenshot of the form, or carriers reject it (error 30909). Tick "
            "\"embedded links\" if any sample has a link. Rejections arrive by email from a2p10dlc@twilio.com "
            "(the console can still say In progress). Full SOP: onboarding-agent/context/a2p-registration-sop.md.",
     "link": "https://console.twilio.com/us1/develop/sms/regulatory-compliance/brand-registrations",
     "linkLabel": "Twilio → Regulatory Compliance", "legacy": [("sms", 1)]},
    {"id": "lists", "long_lead": "Waits on the client's EHR exports", "services": ["reactivation"], "phase": "handover", "package": "all", "title": "Past patient + old inquiry lists imported",
     "how": "CSV exports from their EHR: past patients (discharged or dropped off) and old inquiries that never "
            "booked, with name, mobile, last visit + reason if they have it, minus anyone seen in the last 60 days. "
            "Import each in their portal (Leads → Import CSV) with its list type. Texts only, never voice-called.",
     "action": "portal"},

    # ---- connect
    {"id": "booking", "services": BOOKING, "phase": "connect", "package": "all", "title": "Booking live",
     "how": "AUTOFILL drafts hours, the appointment type and patient contact info from their site, offer and portal "
            "answers: check it, pick their calendar, then Turn on in Booking Links. The funnel, portal and agents "
            "switch to it on their own. Only for a client who books on GoHighLevel: paste the GHL booking link + "
            "Private Integration token under the agent's Calendar (GoHighLevel) and add the booking-sync workflow "
            "(webhook URL in the Agents tab).",
     "action": "booking_autofill", "legacy": [("response_ai", 5)]},
    {"id": "reviews", "services": BOOKING, "phase": "connect", "package": "all",
     "title": "Reviews loaded (every 5-star Google review)",
     "how": "Overload the booking page's social proof: every 5-star Google review the clinic has goes on it (the page "
            "shows one, the rest under \"View more reviews\"). Google's API only gives 5, so the onboarding agent copies "
            "the full list from Google Maps in Dylan's signed-in Chrome and runs import_google_reviews.py (service "
            "delivery skill). Website testimonials count too. Ticks itself at 20 reviews on file, or every review "
            "when the clinic has fewer than 20.",
     "action": "booking"},
    {"id": "lead_form", "long_lead": "A2P's Campaign can't be submitted until this form is published", "services": ["paid_ads"], "phase": "connect", "package": "growth", "title": "Instant Form + lead relay",
     "how": "CREATE FORM builds the Instant Form on their Page (full name, phone, email; the text + AI-call consent "
            "line; thank-you button to their booking link). The lead relay builds itself when the Page ID is saved; "
            "if it shows an error: Make → Credentials → \"DigiGrowth FB\" → Reauthorize with this Page ticked, and "
            "their Business Settings → Leads Access must allow Make. Point the ads at this form, then stamp "
            "CONSENT LINE IS LIVE so the voice agent may call new Meta leads.",
     "link": "https://us2.make.com/2119565/connections", "linkLabel": "Make → Credentials",
     "action": "lead_form", "legacy": [("response_ai", 11)]},
    {"id": "pixel", "services": ["paid_ads"], "phase": "connect", "package": "growth", "title": "Meta Pixel on the funnel",
     "how": "Create or open the client's pixel in Events Manager and save its ID. The funnel and booking pages load "
            "it automatically (PageView, plus Schedule when a booking completes). Check it fires with Pixel Helper.",
     "link": "https://business.facebook.com/events_manager2/list/pixel/", "linkLabel": "Events Manager",
     "fields": [{"key": "meta_pixel_id", "label": "Pixel ID", "placeholder": "1234567890123456"}]},
    {"id": "voice", "services": ["ai_voice"], "phase": "connect", "package": "growth", "title": "Voice agent on",
     "how": "Built automatically from the text agent. Agents → Voice Agent: TEST CALL to your number (it should "
            "confirm who it's talking to, offer two real times, handle a callback request, transfer to the clinic), "
            "then switch on \"Voice agent calls new leads\". Meta leads are only called after the consent stamp "
            "(Instant Form step). Tell the client to pick up when their own number calls.",
     "action": "agents"},
    {"id": "social", "services": ["dm_agent"], "phase": "connect", "package": "growth", "title": "DM agent on (Facebook + Instagram)",
     "how": "Instagram must be a Professional account linked to the Page. Agents → Social Media Conversation Agent → "
            "CONNECT DMS. Turn off Meta's own auto-replies (Business Suite → Inbox → Automations) and on Instagram "
            "allow Connected tools access to messages. TEST CHAT, then switch the agent on.",
     "link": "https://business.facebook.com/latest/inbox/automations", "linkLabel": "Inbox → Automations",
     "action": "agents"},
    {"id": "ad_cap", "services": ["paid_ads"], "phase": "connect", "package": "growth", "title": "Ad spend cap set",
     "how": "Cap = what they signed minus $100 for software (e.g. $600 → 500), start = launch day. Pauses the "
            "campaigns at the cap and times reactivation: first dollar starts check-ins, cap reached starts the "
            "last call. Needs the system user on the ad account with Manage campaigns.",
     "action": "ad_cap"},

    # ---- ads
    {"id": "campaign", "long_lead": "Meta ad review: upload at least 2 days before launch", "services": ["paid_ads"], "phase": "ads", "package": "growth", "title": "Campaign approved and uploaded",
     "how": "Media-buying agent: deep research → campaign plan → ads, each gated for your approval. Upload into the "
            "client's ad account with the Instant Form above, then publish when everything else is green.",
     "link": "https://business.facebook.com/adsmanager", "linkLabel": "Ads Manager", "legacy": [("ad_creatives", 5)]},
    {"id": "campaign_goal", "services": ["paid_ads"], "phase": "ads", "package": "growth", "title": "Campaign goal and length set",
     "how": "How many bookings this client was promised and how long the campaign runs (usually what was agreed on "
            "the sales call or in the Blueprint, e.g. 7 in 30 days). Drives the client's weekly report pace bar, the "
            "halfway and goal-hit milestone texts, the at-risk health score and when the final report (with the "
            "next-campaign plan) is drafted. The campaign ends when the ad spend cap is reached (set it in the Ad spend "
            "cap step); a length is only needed for a client without a cap.",
     "fields": [{"key": "campaign_booking_goal", "label": "Bookings goal", "placeholder": "7"},
                {"key": "campaign_goal_label", "label": "Goal counts", "placeholder": "assessments"},
                {"key": "campaign_length_days", "label": "Length in days (blank = ends at ad budget)", "placeholder": ""}]},
    {"id": "organic", "services": ["social_media"], "phase": "ads", "package": "growth", "title": "Organic posts scheduled",
     "how": "Tidy the Page and Instagram (images, bio, website = their funnel). Schedule the approved creatives in "
            "Planner, Facebook + Instagram together, one every 3 days for 30 days, mid-morning clinic time. Caption = "
            "the hook and story without ad-only urgency, soft CTA, 3-5 local hashtags.",
     "link": "https://business.facebook.com/latest/planner", "linkLabel": "Business Suite → Planner",
     "legacy": [("social", 6)]},

    # ---- launch
    {"id": "test", "phase": "launch", "package": "all", "title": "End-to-end test, then clean up",
     "how": "RUN TEST sends a test lead with your test number through the real flow: opener text (or the voice "
            "agent's call), and a booking on the next open slot so the confirmation text arrives. Check your phone, "
            "then CLEAN UP deletes the test lead, cancels the test booking and resets the funnel's stats. Turn the "
            "client's booking alert off first if you don't want them notified.",
     "action": "test", "legacy": [("response_ai", 15)]},
    {"id": "reactivation", "services": ["reactivation"], "phase": "launch", "package": "all", "title": "Database reactivation running",
     "how": "Growth: starts itself at the first ad dollar (check-ins) and the cap (last call). Foundations: START it by "
            "hand in Agents → Database Reactivation Agent once the lists are in and A2P is approved. VIEW QUEUE shows "
            "who's next.",
     "action": "agents"},
    {"id": "golive", "services": ["paid_ads"], "phase": "launch", "package": "growth", "title": "Ads live, client told",
     "how": "Publish the campaign. Tell the client what's live: texts and calls come from their own number, transfers "
            "reach them during business hours, results show in their portal. Ticks itself at the first ad dollar.",
     "legacy": [("client_portal", 6)]},
]

_BY_ID = {s["id"]: s for s in STEPS}

# Launch checklist item title (lowercased) -> v2 steps that must all be done.
LAUNCH_ITEM_STEPS = {
    "set up client portal": ["autobuild"],
    "set up sms marketing": ["autobuild", "a2p"],
    "set up response ai": ["review", "booking"],
    "create landing page": ["autobuild"],
    "create paid ad creatives": ["campaign"],
    "launch database reactivation": ["reactivation"],
}


def _decode(value, default):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return default
    return value if value is not None else default


def steps_for(services) -> list[dict]:
    return [s for s in STEPS if client_services.applies(s.get("services"), services)]


async def signals(conn, client_id: int) -> dict[str, str]:
    """{step_id: short proof} for every step real data proves done."""
    cfg = await conn.fetchrow("SELECT * FROM client_marketing_config WHERE client_id = $1", client_id)
    client = await conn.fetchrow("SELECT * FROM clients WHERE id = $1", client_id)
    if not cfg or not client:
        return {}
    cfg = dict(cfg)
    out: dict[str, str] = {}
    seq_count = await conn.fetchval("SELECT count(*) FROM client_sequence_steps WHERE client_id = $1", client_id)
    if cfg.get("landing_page_url") and cfg.get("twilio_number") and cfg.get("response_ai_context") and seq_count:
        out["autobuild"] = f"Funnel, {cfg['twilio_number']}, text agent and {seq_count} messages in place"

    if cfg.get("meta_ad_account_id") and cfg.get("meta_page_id"):
        out["meta_access"] = "Ad account and Page saved"
    bs = await conn.fetchrow("SELECT * FROM booking_settings WHERE client_id = $1", client_id)
    paid = await conn.fetchval(
        "SELECT 1 FROM booking_event_types WHERE client_id = $1 AND active AND price_cents > 0 LIMIT 1", client_id)
    booking_url = (client["calendly_url"] or cfg.get("calendly_event_type_url") or "").strip()
    on_ghl = "leadconnectorhq.com" in booking_url or "/widget/booking/" in booking_url or "msgsndr.com" in booking_url
    if bs and bs["calendar_id"] and (not paid or bs["stripe_charges_enabled"]):
        out["calendar"] = "Calendar picked" + (" and Stripe connected" if paid else "")
    elif on_ghl and cfg.get("ghl_api_token"):
        out["calendar"] = "Books on their GoHighLevel calendar"
    elif cfg.get("calendly_api_token") and cfg.get("calendly_event_type_url"):
        out["calendar"] = "Books on their Calendly"

    react = await conn.fetchval(
        """SELECT count(*) FROM contacts WHERE client_id = $1 AND NOT is_client_anchor
             AND (lead_source IN ('past_patient', 'old_inquiry', 'import') OR 'Previous Patient' = ANY(tags))""",
        client_id)
    if react:
        out["lists"] = f"{react} imported"

    dg_live = bool(bs and bs["enabled"] and bs["calendar_id"] and await conn.fetchval(
        "SELECT 1 FROM booking_event_types WHERE client_id = $1 AND active LIMIT 1", client_id))
    if dg_live:
        out["booking"] = "DigiGrowth Booking is on"
    elif on_ghl and cfg.get("ghl_last_webhook_at"):
        out["booking"] = "GoHighLevel bookings are syncing"
    elif cfg.get("calendly_api_token") and cfg.get("calendly_event_type_url"):
        out["booking"] = "Calendly connected"
    if bs:
        rv = bs["reviews"] or []
        if isinstance(rv, str):
            rv = _decode(rv, [])
        need = min(20, bs["review_count"]) if bs["review_count"] else 20
        if len(rv) >= max(1, need):
            out["reviews"] = f"{len(rv)} reviews on the booking page"

    if cfg.get("make_scenario_id") and not cfg.get("lead_ads_error") and cfg.get("meta_form_id"):
        out["lead_form"] = "Form built and relay connected"
    if cfg.get("campaign_booking_goal"):
        out["campaign_goal"] = (f"{cfg['campaign_booking_goal']} bookings in "
                                f"{cfg.get('campaign_length_days') or 30} days")
    if cfg.get("booking_domain") and cfg.get("booking_domain_live_at"):
        out["booking_domain"] = f"{cfg['booking_domain']} serves their booking page"
    if cfg.get("meta_pixel_id"):
        out["pixel"] = f"Pixel {cfg['meta_pixel_id']} loads on the funnel"
    if cfg.get("voice_agent_enabled"):
        out["voice"] = "Calling new leads"
    if cfg.get("dm_agent_enabled") and cfg.get("dm_connected_at") and not cfg.get("dm_connect_error"):
        out["social"] = "Replying to DMs"
    cap = await conn.fetchrow(
        "SELECT cap FROM ad_spend_caps WHERE client_id = $1 AND enabled AND cap > 0 "
        "AND last_checked_at IS NOT NULL AND last_error IS NULL", client_id)
    if cap:
        out["ad_cap"] = f"${cap['cap']:,.0f} cap, checked"

    test = _decode(cfg.get("setup_test"), {})
    if test.get("cleaned_at"):
        out["test"] = "Tested and cleaned up"
    started = await conn.fetchval(
        "SELECT 1 FROM reactivation_campaigns WHERE client_id = $1 AND started_at IS NOT NULL LIMIT 1", client_id)
    if started:
        out["reactivation"] = "A campaign is running"
    spend = await conn.fetchval(
        "SELECT 1 FROM ad_campaign_stats WHERE client_id = $1 AND spend > 0 LIMIT 1", client_id)
    if spend:
        out["golive"] = "Ads are spending"
    return out


def _migrate(progress: dict) -> dict:
    """First read after v2 shipped: carry old guide ticks over to the new ids."""
    v2: dict = {}
    for s in STEPS:
        for guide, idx in s.get("legacy", []):
            if (progress.get(guide) or {}).get(str(idx)):
                v2[s["id"]] = True
    return v2


async def status(client_id: int) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        client = await conn.fetchrow(
            "SELECT id, name, service_package, services, portal_intake, intake_required, intake_completed_at "
            "FROM clients WHERE id = $1", client_id)
        if not client:
            return {}
        row = await conn.fetchrow(
            "SELECT guide_progress, autosetup, setup_test, meta_form_id, voice_consent_meta_since, lead_ads_error "
            "FROM client_marketing_config WHERE client_id = $1", client_id)
        progress = _decode(row["guide_progress"] if row else None, {})
        if row and "v2" not in progress:
            progress["v2"] = _migrate(progress)
            await conn.execute(
                "UPDATE client_marketing_config SET guide_progress = $2::jsonb WHERE client_id = $1",
                client_id, json.dumps(progress))
        proven = await signals(conn, client_id)
    ticks = progress.get("v2") or {}
    package = client["service_package"] or "growth"
    services = client_services.effective(dict(client))
    steps = []
    for s in steps_for(services):
        auto = proven.get(s["id"])
        steps.append({**{k: v for k, v in s.items() if k != "legacy"},
                      "done": bool(auto or ticks.get(s["id"])), "proof": auto, "ticked": bool(ticks.get(s["id"]))})
    return {
        "package": package,
        "phases": PHASES,
        "steps": steps,
        "done": sum(1 for s in steps if s["done"]),
        "total": len(steps),
        "autosetup": _decode(row["autosetup"], {}) if row else {},
        "setup_test": _decode(row["setup_test"], {}) if row else {},
        "meta_form_id": row["meta_form_id"] if row else None,
        "consent_since": row["voice_consent_meta_since"].isoformat() if row and row["voice_consent_meta_since"] else None,
        "lead_ads_error": row["lead_ads_error"] if row else None,
        "client_ask": client_ask(client["name"], {s["id"] for s in steps},
                                 {s["id"] for s in steps if s["done"]}),
        "services": services,
        "services_from": "intake" if client["intake_completed_at"] else (
            "set by Dylan" if client["services"] is not None else "package"),
        "service_options": client_services.CHOICES,
        "services_shown": client_services.to_choices(services),
        "intake_pending": client_services.intake_pending(dict(client)),
        "intake_answers": _decode(client["portal_intake"], {}),
        "intake_questions": client_services.INTAKE_QUESTIONS,
    }


def client_ask(name: str, shown: set[str], done: set[str]) -> str:
    """The one batched handover message, listing only what's still missing
    (and only for steps that apply to this client's services)."""
    done = done | {s["id"] for s in STEPS if s["id"] not in shown}
    items = []
    if "meta_access" not in done:
        items.append("Facebook: in Business Settings → Partners, add DigiGrowth (business ID 695946576605909) with "
                     "your Page, Instagram and ad account (Full control / Manage campaigns).")
    if "calendar" not in done:
        items.append("Google Calendar: share the calendar you book patients on with dylanrg@digigrowthllc.com, "
                     "permission \"Make changes to events\" (your portal walks you through it). If the visit is "
                     "paid, also click \"Connect Stripe to Get Paid\" in your portal.")
    if "dns" not in done or "booking_domain" not in done:
        items.append("Website domain: access to wherever your domain's DNS is managed (or we'll send you the "
                     "records to add), so your landing page and booking link can live on your own web address "
                     "(go.<your domain> and book.<your domain>).")
    if "a2p" not in done:
        items.append("Your legal business name and EIN, for the texting registration carriers require.")
    if "lists" not in done:
        items.append("Two CSV exports from your patient system: past patients (discharged or dropped off) and old "
                     "inquiries who never booked, with name, mobile, and last visit + reason if you have it. "
                     "Leave out anyone seen in the last 60 days.")
    if not items:
        return ""
    lines = "\n".join(f"{i}. {t}" for i, t in enumerate(items, 1))
    return f"Hi! To get everything live for {name}, here's what we need from you:\n\n{lines}\n\nThanks!"


async def set_tick(client_id: int, step_id: str, value: bool) -> None:
    if step_id not in _BY_ID:
        raise ValueError("Unknown step")
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """UPDATE client_marketing_config
               SET guide_progress = jsonb_set(
                     CASE WHEN guide_progress ? 'v2' THEN guide_progress ELSE guide_progress || '{"v2": {}}'::jsonb END,
                     ARRAY['v2', $2::text], to_jsonb($3::boolean)),
                   updated_at = now()
               WHERE client_id = $1""",
            client_id, step_id, value)


async def launch_checklist_done(client_id: int) -> set[str]:
    """Step ids done for this client (proven or ticked), for the launch checklist
    sync. Steps that don't apply to their services count as done."""
    st = await status(client_id)
    shown = {s["id"] for s in st.get("steps", [])}
    return {s["id"] for s in st.get("steps", []) if s["done"]} | {s["id"] for s in STEPS if s["id"] not in shown}


def retell_configured() -> bool:
    return bool(os.environ.get("RETELL_API_KEY"))


async def set_services(client_id: int, services: list[str]) -> None:
    """Dylan's override from Marketing Setup (choice ids, as the intake ticks them)."""
    services = client_services.expand(services)
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE clients SET services = $2::jsonb, updated_at = now() WHERE id = $1",
                           client_id, json.dumps(services))


async def ask_intake_again(client_id: int, on: bool) -> None:
    """Gate (or un-gate) the client's portal behind the intake again."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE clients SET intake_required = $2, intake_completed_at = CASE WHEN $2 THEN NULL "
            "ELSE coalesce(intake_completed_at, now()) END, updated_at = now() WHERE id = $1", client_id, on)
