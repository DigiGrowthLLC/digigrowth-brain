"""Database reactivation: a CLIENT's own AI outreach to people already in
their records. Each campaign runs one PLAYBOOK (Dylan, 2026-11-16), because
not every lead should get the same message:

- checkin: the clinic's own list (past patients, old inquiries, imports,
  people added by hand). Sent as the OWNER ("it's Brian from Pinnacle"), a
  familiar face. A check-in on the issue they're tagged with ("how's that
  shoulder been?"), never a pitch. Doing fine -> "awesome, reach out if it
  acts up" and the thread closes. Hurting -> a couple of relaxed questions,
  then "you'd qualify for our <offer>". 2 texts. Text only, never called.
  Then a fresh check-in every 90 days (CHECKIN_CYCLE) until they book,
  written to build on the last conversation, unless they said no (a
  not_interested close, STOP, Don't contact) or Dylan stops them from the
  queue. Starts by itself when the client's ads spend their first dollar.
- social: Instagram/Facebook DM leads that went quiet. Same relaxed,
  question-first approach, sent as the clinic's agent name. 2 texts.
- last_call: ad leads (Meta form / funnel) since the ad campaign launched who
  never had a real appointment (never booked, canceled, no-showed). Starts
  by itself when the client's ad budget (ad_spend_caps.py cap) is spent: a
  text right away, then 24h later, if they haven't replied, a voice call (if
  they consented to calls) that falls back to a text. No daily cap. Then
  every 30 days until they book, one offer-update text (OFFER_UPDATE_TOUCHES):
  "we're running <offer> again" if the offer is the same as the one they last
  heard about, "you missed our last offer, you qualify for our new <offer>"
  if it changed (enrollment.offer_sent vs the client's current offer).

Auto-start (Dylan, 2026-11-16): on_ad_spend(), called by the ad spend cap
watchdog every 30 min. First dollar spent -> ticks "Launch campaign" and
starts the check-in campaign (ticks "Launch database reactivation"). Cap
reached -> starts a last_call campaign (once per cap value).

The relaxed approach also drives the conversation once they reply: see
response_ai.GENTLE_ARC (and the DM agent, which uses it for every DM).

Starting a campaign snapshots who's eligible into reactivation_enrollments;
send_due() (main.py, every 5 minutes) works through them (an active check-in
campaign also picks up people who become eligible later, e.g. a new import).
Exclusions (all playbooks): Unqualified, SMS Opted Out, the client's own
"Don't contact"/DNC tag, an escalated thread or one closed in the last 90
days, already open in another campaign. checkin/social: an upcoming
appointment or one in the last 60 days, anyone in the prospect follow-up,
recent ad leads and anyone texted in the last 30 days. last_call: only an
upcoming appointment or one they actually came to. Re-checked before every
touch. queue() lists what's coming up for the OS's VIEW QUEUE.

Each touch is the campaign's template, rewritten for the person by
response_ai.write_reactivation_text (their tags, notes, source, old thread),
or sent as written when the text agent is off. A reply ends the outreach
and the text agent takes the conversation from there.

Touches go out 10am-6pm Monday-Saturday in the clinic's timezone.
"""

import json
import re
from datetime import date, datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

import lead_flags
from db import get_pool
from merge_fields import first_name_from_owner
from timezone_lookup import clinic_timezone

# Off switch (Dylan, 2026-11-16): reactivation stays OFF until he approves
# the playbooks below. While True, no campaign can start and nothing sends.
REACTIVATION_PAUSED = True

# Plain GSM-7 characters only. Placeholders: {first_name} {sender}
# {business} {checkin_question} {offer} {end_day}. "day" = days after the
# campaign reaches them (each touch waits for the gap since the last one, and
# only if they haven't replied). "call": true (last_call) means call first
# (consent permitting) and text only if they don't pick up.
PLAYBOOKS = {
    "checkin": {
        "label": "Check-in (clinic's own list)",
        "description": "Past patients, old inquiries and lists the clinic gave us. Texts as the owner, checks in on "
                       "their issue, and only offers a visit if something is bothering them.",
        "sender": "owner",
        "sources": ["past_patient", "old_inquiry", "import", "manual"],
        "angle": "A friendly check-in from the clinic on how they've been doing. Only bring up a visit if "
                 "something is bothering them.",
        "touches": [
            {"day": 0, "body": "Hey {first_name}, it's {sender} from {business}. Just reaching out, {checkin_question}"},
            {"day": 4, "body": "Hey {first_name}, just following up in case this got buried. No worries if you're "
                               "busy, {checkin_question}"},
        ],
    },
    "social": {
        "label": "Social media leads",
        "description": "People who messaged on Instagram or Facebook and went quiet. Same relaxed check-in, "
                       "sent as the clinic's agent.",
        "sender": "agent",
        "sources": ["ig_dm", "fb_dm"],
        "angle": "A relaxed check-in with someone who messaged the clinic on social media a while back. Only "
                 "bring up a visit if something is bothering them.",
        "touches": [
            {"day": 0, "body": "Hey {first_name}, it's {sender} from {business}. You messaged us a while back and "
                               "I wanted to check in, {checkin_question}"},
            {"day": 4, "body": "Hey {first_name}, just following up in case this got buried. {checkin_question}"},
        ],
    },
    "last_call": {
        "label": "Last call (ad leads who didn't book)",
        "description": "Meta form and funnel leads since the ads launched who never came in (never booked, canceled "
                       "or no-showed). Starts by itself when the ad budget is spent: a text, then a call 24 hours "
                       "later if they haven't replied (text if no answer or no call consent). Then an offer-update "
                       "text every 30 days until they book.",
        "sender": "agent",
        "sources": ["meta_form", "funnel"],
        "angle": "The ad offer they asked about is wrapping up: a last chance to get in at that offer.",
        "touches": [
            {"day": 0, "body": "Hey {first_name}, it's {sender} from {business}. Just a heads up, our "
                               "{offer}{offer_reminder} is wrapping up. Didn't want you to miss out."},
            {"day": 1, "call": True, "body": "Hey {first_name}, today's the last day for our {offer}{offer_reminder}. "
                                             "Didn't want you to miss out. Want me to grab you a time?"},
        ],
    },
}
# Check-in playbook: a fresh check-in this long after the last conversation,
# until they book (Dylan, 2026-11-16).
CYCLES = {"checkin": timedelta(days=90), "last_call": timedelta(days=30)}
CHECKIN_CYCLE = CYCLES["checkin"]
# last_call, every 30 days after the first round (Dylan, 2026-11-16): same
# offer as they last heard about -> "running it again"; changed -> "you
# qualify for our new one". The AI rewrites these from the thread.
OFFER_UPDATE_TOUCHES = {
    "same": "Hey {first_name}, it's {sender} from {business}. We're running our {offer}{offer_reminder} again, in "
            "case you didn't get the chance to book in last time.",
    "new": "Hey {first_name}, it's {sender} from {business}. Saw you missed out on our {previous_offer}. Just wanted "
           "to let you know we're running a new special: our {offer}{offer_reminder}.",
}
# Launch checklist items on_ad_spend() ticks (launch_checklist_items.title, lowercased).
_LAUNCH_ITEM = "launch campaign"
_REACTIVATION_ITEM = "launch database reactivation"
GENTLE_PLAYBOOKS = ("checkin", "social")
DEFAULT_PLAYBOOK = "checkin"
# Kept for callers that still read it.
DEFAULT_TOUCHES = PLAYBOOKS[DEFAULT_PLAYBOOK]["touches"]

# Sources an audience can be built from (contacts.lead_source).
AUDIENCE_SOURCES = ["past_patient", "old_inquiry", "import", "manual", "website", "inbound_sms",
                    "ig_dm", "fb_dm", "meta_form", "funnel"]
_FRESH_AD_SOURCES = ["meta_form", "funnel", "fb_dm", "ig_dm"]
_AD_TAGS = ["meta_lead", "ads-lead"]
# How far back a last_call campaign looks for ad leads (before ends_on).
LAST_CALL_LOOKBACK_DAYS = 60

SEND_START_HOUR = 10
SEND_END_HOUR = 18
# A reply this long after the last touch still counts as a reply to it.
_REPLY_GRACE = timedelta(days=3)
_STOP_LINE = "Reply STOP to opt out."

_PHONE_MATCH = r"right(regexp_replace({a}, '\D', '', 'g'), 10) = right(regexp_replace({b}, '\D', '', 'g'), 10)"

# Tags that say what a lead's issue is ("Shoulder", "Low Back Pain").
_ISSUE_RE = re.compile(
    r"pain|back|neck|shoulder|knee|hip|ankle|foot|feet|wrist|hand|elbow|sciatica|headache|migraine|"
    r"injur|arthritis|plantar|tendon|rotator|acl|tmj|posture|balance|vertigo|pelvic", re.I)


def _norm_tag(t: str) -> str:
    return re.sub(r"[^a-z]", "", (t or "").lower())


_SYSTEM_TAGS = {_norm_tag(t) for t in [
    lead_flags.REACTIVATION_TAG, "Previous Patient", lead_flags.INBOUND_TAG, lead_flags.SOCIAL_TAG,
    "meta_lead", "ads-lead", "organic-lead", lead_flags.OPTED_OUT_TAG, lead_flags.UNQUALIFIED_TAG,
    lead_flags.NO_SHOW_TAG, lead_flags.CANCELED_TAG, "Do Not Call", "Don't contact", "Do not contact", "DNC",
]}


def issue_tags(tags) -> list[str]:
    """The lead's tags that describe their problem (body part / condition)."""
    return [t for t in (tags or []) if _norm_tag(t) not in _SYSTEM_TAGS and _ISSUE_RE.search(t or "")]


def profile_tags(tags) -> list[str]:
    """Every tag the clinic added that isn't one of our automatic ones."""
    return [t for t in (tags or []) if _norm_tag(t) not in _SYSTEM_TAGS]


def checkin_question(tags) -> str:
    """'how's your shoulder been doing?' from their first issue tag, else a
    general check-in."""
    issues = issue_tags(tags)
    if not issues:
        return "how have you been feeling?"
    part = re.sub(r"\bpain\b", "", issues[0], flags=re.I).strip(" -/").lower() or issues[0].lower()
    return f"how's your {part} been doing?"


_APPT_MATCH = f"""(a.contact_id = c.id OR {_PHONE_MATCH.format(a="coalesce(a.prospect_phone, '')", b="c.phone")})"""


def _excluded_sql(playbook: str, per_enrollment: bool = False) -> str:
    """Exclusions that hold for every touch. `c` = contacts; with
    per_enrollment, `re` = their reactivation_enrollments row."""
    if playbook == "last_call":
        followup = ""
        # Anyone who never had a real appointment stays in: never booked,
        # canceled, or no-showed. Out: an upcoming visit or one they came to.
        appointment = f"""EXISTS (
        SELECT 1 FROM appointment_reminders a
        WHERE {_APPT_MATCH} AND a.status != 'canceled' AND coalesce(a.outcome_show, '') != 'no_show'
    )"""
    else:
        # A 90-day check-in (cycle 2+) only starts after 90 quiet days, so an
        # old prospect follow-up enrollment no longer counts against it.
        followup = ("OR (c.client_followup_enrolled_at IS NOT NULL AND re.cycle = 1)" if per_enrollment
                    else "OR c.client_followup_enrolled_at IS NOT NULL")
        appointment = f"""EXISTS (
        SELECT 1 FROM appointment_reminders a
        WHERE {_APPT_MATCH} AND a.appointment_at > now() - interval '60 days' AND a.status != 'canceled'
    )"""
    return rf"""(
    {lead_flags.UNQUALIFIED_SQL}
    OR {lead_flags.OPTED_OUT_SQL}
    OR {lead_flags.DONT_CONTACT_SQL}
    {followup}
    OR {appointment}
    -- A human has the thread, or they told the agent no in the last 90
    -- days. (A booking is covered by the appointment check above.)
    OR EXISTS (
        SELECT 1 FROM client_lead_conversations clc
        WHERE clc.client_id = c.client_id
          AND (clc.status = 'escalated'
               OR (clc.status = 'closed' AND coalesce(clc.last_message_at, clc.created_at) > now() - interval '90 days'))
          AND {_PHONE_MATCH.format(a="clc.phone", b="c.phone")}
    )
)"""


# checkin/social only, at enrollment and before the first touch (afterwards
# our own touches would trip the recent-text check).
_FIRST_TOUCH_EXCLUDED_SQL = rf"""(
    (c.lead_source = ANY(ARRAY{_FRESH_AD_SOURCES!r}::text[]) AND c.created_at > now() - interval '30 days')
    OR ((c.tags && ARRAY{_AD_TAGS!r}::text[]) AND c.created_at > now() - interval '30 days')
    OR EXISTS (
        SELECT 1 FROM client_sms_messages m
        WHERE m.client_id = c.client_id AND m.created_at > now() - interval '30 days'
          AND {_PHONE_MATCH.format(a="CASE WHEN m.direction = 'outbound' THEN m.to_number ELSE m.from_number END", b="c.phone")}
    )
)"""

_AUDIENCE_SQL = """(
    coalesce(c.lead_source, '') = ANY($2::text[])
    OR EXISTS (
        SELECT 1 FROM unnest(coalesce(c.tags, '{}')) t, unnest($3::text[]) want
        WHERE lower(t) = lower(want)
    )
)"""

# last_call: an ad lead (by source or tag) who came in since the ad campaign
# launched ($2), and wasn't already reached by an earlier last call.
_LAST_CALL_AUDIENCE_SQL = rf"""(
    (coalesce(c.lead_source, '') = ANY(ARRAY{_FRESH_AD_SOURCES[:2]!r}::text[]) OR c.tags && ARRAY{_AD_TAGS!r}::text[])
    AND c.created_at >= $2::timestamptz
    AND NOT EXISTS (
        SELECT 1 FROM reactivation_enrollments re3 JOIN reactivation_campaigns rc3 ON rc3.id = re3.campaign_id
        WHERE re3.contact_id = c.id AND rc3.playbook = 'last_call' AND re3.touches_sent > 0
    )
)"""

_OPEN_ELSEWHERE_SQL = """EXISTS (
    SELECT 1 FROM reactivation_enrollments re2 JOIN reactivation_campaigns rc2 ON rc2.id = re2.campaign_id
    WHERE re2.contact_id = c.id AND re2.status IN ('queued', 'active') AND rc2.status IN ('active', 'paused')
)"""


def normalize_phone(phone: str) -> str | None:
    """US numbers to E.164, so texts and the thread lookup use the same
    string Twilio's inbound webhook will (imports come in every format)."""
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 10:
        return "+1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    return None


def playbook_of(campaign) -> str:
    pb = (campaign.get("playbook") if hasattr(campaign, "get") else campaign["playbook"]) or DEFAULT_PLAYBOOK
    return pb if pb in PLAYBOOKS else DEFAULT_PLAYBOOK


def touches_of(campaign) -> list[dict]:
    touches = campaign["touches"]
    if isinstance(touches, str):
        touches = json.loads(touches)
    return [t for t in (touches or []) if (t.get("body") or "").strip()]


def _tz(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name or "America/Chicago")
    except Exception:
        return ZoneInfo("America/Chicago")


def in_send_window(tz_name: str, now: datetime) -> bool:
    local = now.astimezone(_tz(tz_name))
    return local.weekday() != 6 and SEND_START_HOUR <= local.hour < SEND_END_HOUR


async def last_call_since(conn, client_id: int) -> datetime:
    """Where a last call's audience starts: when the ad campaign launched,
    never more than LAST_CALL_LOOKBACK_DAYS back."""
    launched = await conn.fetchval(
        "SELECT campaign_launched_at FROM client_marketing_config WHERE client_id = $1", client_id)
    floor = datetime.now(dt_timezone.utc) - timedelta(days=LAST_CALL_LOOKBACK_DAYS)
    return max(launched, floor) if launched else floor


async def eligible_contacts(conn, client_id: int, sources: list[str], tags: list[str], campaign_id: int | None = None,
                            playbook: str = DEFAULT_PLAYBOOK, ends_on: date | None = None):
    """Who a campaign with this audience would reach if started now.
    (`ends_on` is accepted for old callers and no longer narrows anything.)"""
    if playbook == "last_call":
        since = await last_call_since(conn, client_id)
        audience, first_touch, params = _LAST_CALL_AUDIENCE_SQL, "false", [client_id, since]
    else:
        audience, first_touch, params = _AUDIENCE_SQL, _FIRST_TOUCH_EXCLUDED_SQL, [client_id, sources, tags]
    params.append(campaign_id or 0)
    return await conn.fetch(
        f"""
        SELECT c.id, c.owner, c.phone, c.lead_source, c.source_detail, c.tags FROM contacts c
        WHERE c.client_id = $1 AND NOT c.is_client_anchor AND coalesce(c.phone, '') != ''
          AND {audience}
          AND NOT {_excluded_sql(playbook)}
          AND NOT {first_touch}
          AND NOT {_OPEN_ELSEWHERE_SQL}
          AND NOT EXISTS (SELECT 1 FROM reactivation_enrollments re WHERE re.contact_id = c.id AND re.campaign_id = ${len(params)})
        ORDER BY c.created_at ASC
        """,
        *params,
    )


async def start_campaign(campaign_id: int) -> int:
    """Snapshot the audience into enrollments and set the campaign active.
    Re-runnable: starting again adds people who became eligible since.
    Returns how many were added."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        campaign = await conn.fetchrow("SELECT * FROM reactivation_campaigns WHERE id = $1", campaign_id)
        if not campaign:
            raise ValueError("Campaign not found")
        rows = await eligible_contacts(
            conn, campaign["client_id"], list(campaign["audience_sources"]), list(campaign["audience_tags"]), campaign_id,
            playbook_of(dict(campaign)), campaign["ends_on"],
        )
        async with conn.transaction():
            for r in rows:
                await conn.execute(
                    "INSERT INTO reactivation_enrollments (campaign_id, contact_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                    campaign_id, r["id"],
                )
            await conn.execute(
                "UPDATE reactivation_campaigns SET status = 'active', started_at = coalesce(started_at, now()) WHERE id = $1",
                campaign_id,
            )
    return len(rows)


async def sender_names(conn, client_id: int) -> dict:
    """{'owner': 'Brian', 'agent': 'Maddie'}: who the texts come from."""
    row = await conn.fetchrow(
        "SELECT c.contact_name, cmc.voice_agent_name, cmc.voice_id FROM clients c "
        "LEFT JOIN client_marketing_config cmc ON cmc.client_id = c.id WHERE c.id = $1",
        client_id,
    )
    if not row:
        return {"owner": "", "agent": ""}
    import client_voice_agent
    try:
        agent = client_voice_agent.agent_name(row)
    except Exception:
        agent = ""
    return {"owner": first_name_from_owner(row["contact_name"]) if row["contact_name"] else "", "agent": agent}


async def _campaign_context(conn, campaign: dict) -> dict:
    """Values for the template placeholders, the same for everyone in it."""
    import client_voice_agent
    names = await sender_names(conn, campaign["client_id"])
    sender = names["owner"] if PLAYBOOKS[playbook_of(campaign)]["sender"] == "owner" else names["agent"]
    offer = await current_offer(conn, campaign["client_id"])
    ends_on = campaign.get("ends_on")
    return {
        "sender": sender or names["agent"] or "the team",
        "business": campaign["client_name"] or "",
        "offer": offer["name"] or "special",
        "offer_detail": offer["detail"],
        "end_day": ends_on.strftime("%A") if ends_on else "soon",
    }


async def current_offer(conn, client_id: int) -> dict:
    """The offer the texts name: {"name", "detail", "auto"}. Set on the OS's
    Database Reactivation Agent (OFFER IN THESE TEXTS). Empty -> filled once
    from the client's agent context by the model (saved, auto=True, Dylan
    can edit), else the DigiGrowth Booking visit's name."""
    row = await conn.fetchrow(
        "SELECT reactivation_offer_name, reactivation_offer_detail, reactivation_offer_auto, response_ai_context "
        "FROM client_marketing_config WHERE client_id = $1", client_id)
    if row and (row["reactivation_offer_name"] or "").strip():
        return {"name": row["reactivation_offer_name"].strip(), "detail": (row["reactivation_offer_detail"] or "").strip(),
                "auto": bool(row["reactivation_offer_auto"])}
    if row and (row["response_ai_context"] or "").strip():
        got = await _extract_offer(row["response_ai_context"])
        if got and got.get("name"):
            await conn.execute(
                "UPDATE client_marketing_config SET reactivation_offer_name = $2, reactivation_offer_detail = $3, "
                "reactivation_offer_auto = TRUE WHERE client_id = $1 AND coalesce(reactivation_offer_name, '') = ''",
                client_id, got["name"][:80], (got.get("detail") or "")[:140])
            return {"name": got["name"][:80], "detail": (got.get("detail") or "")[:140], "auto": True}
    import client_voice_agent
    visit = await client_voice_agent._visit_info(client_id)
    return {"name": (visit or {}).get("name") or "", "detail": "", "auto": True}


async def _extract_offer(context: str) -> dict | None:
    """Name the clinic's current patient offer from its agent context, the
    way it'd read in a text: {"name": "Free Back Pain Discovery Call",
    "detail": "a free 20-minute call with a PT"}. None on any failure."""
    import asyncio
    import os
    import anthropic
    try:
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        r = await asyncio.to_thread(
            client.messages.create,
            model=os.environ.get("AGENTS_CLAUDE_MODEL", "claude-sonnet-5"), max_tokens=200,
            system=(
                "From a physical therapy clinic's business info, name the ONE offer its ads currently promote to new "
                "patients. Reply with JSON only: {\"name\": the offer's name as it would read after \"our\" in a "
                "text, Title Case, 2-6 words, e.g. \"Free Back Pain Discovery Call\" or \"$49 New Patient "
                "Assessment\"; \"detail\": what they get, 4-12 plain words starting lowercase, e.g. \"a free 20-minute "
                "call with a physical therapist\"}. Use only what the text says; if there's no clear offer, "
                "{\"name\": \"\", \"detail\": \"\"}. Plain ASCII, no em dashes."
            ),
            messages=[{"role": "user", "content": context[:12000]}],
        )
        text = "".join(b.text for b in r.content if b.type == "text").strip()
        text = text[text.find("{"):text.rfind("}") + 1]
        got = json.loads(text)
        return {"name": str(got.get("name") or "").strip(), "detail": str(got.get("detail") or "").strip()}
    except Exception as e:
        print(f"[client_reactivation] offer extraction failed: {e}", flush=True)
        return None


def fill(template: str, contact: dict, ctx: dict) -> str:
    out = (template or "")
    for key, val in {
        "{first_name}": first_name_from_owner(contact.get("owner")) or "there",
        "{sender}": ctx.get("sender") or "",
        "{business}": ctx.get("business") or "",
        "{offer}": ctx.get("offer") or "",
        "{offer_reminder}": f" ({ctx['offer_detail']})" if ctx.get("offer_detail") else "",
        "{previous_offer}": contact.get("offer_sent") or "last offer",
        "{end_day}": ctx.get("end_day") or "",
        "{checkin_question}": checkin_question(contact.get("tags")),
    }.items():
        out = out.replace(key, val)
    return re.sub(r"\s+", " ", out).strip()


async def _end(conn, enrollment_id: int, status: str, reason: str, playbook: str | None = None) -> None:
    """Close an enrollment. A check-in / last call that went unanswered or
    got a reply (and no booking) gets its next round CYCLES[playbook] out."""
    next_at = (datetime.now(dt_timezone.utc) + CYCLES[playbook]
               if playbook in CYCLES and status in ("completed", "replied") else None)
    await conn.execute(
        "UPDATE reactivation_enrollments SET status = $2, end_reason = $3, ended_at = now(), next_checkin_at = $4 "
        "WHERE id = $1",
        enrollment_id, status, reason, next_at,
    )


def offer_change(enrollment: dict, ctx: dict | None) -> str:
    """'new' if the client's offer now differs from the one this person last
    heard about, else 'same' (also when either is unknown)."""
    prev = (enrollment.get("offer_sent") or "").strip().lower()
    cur = ((ctx or {}).get("offer") or "").strip().lower()
    return "new" if prev and cur and cur != "special" and prev != cur else "same"


def touches_for(base: list[dict], playbook: str, enrollment: dict, ctx: dict | None) -> list[dict]:
    """The touches for this person's current round: a last call's later
    rounds are one offer-update text; everything else repeats the campaign's."""
    if playbook == "last_call" and int(enrollment.get("cycle") or 1) > 1:
        return [{"day": 0, "body": OFFER_UPDATE_TOUCHES[offer_change(enrollment, ctx)]}]
    return base


async def _send_touch(campaign: dict, enrollment: dict, touch_num: int, touches: list[dict], ctx: dict) -> str:
    """Returns 'sent', 'skipped' (the send was refused, e.g. opted out
    since) or 'failed'."""
    import client_sms
    import response_ai

    phone = normalize_phone(enrollment["phone"])
    template = fill(touches[touch_num - 1]["body"], enrollment, ctx)
    cycle = int(enrollment.get("cycle") or 1)
    text = await response_ai.write_reactivation_text(
        campaign["client_id"], phone, template, touch_num, len(touches), playbook=playbook_of(campaign),
        origin_extra={
            "playbook": playbook_of(campaign),
            "campaign_angle": campaign.get("angle"),
            "ends_on": f"{campaign['ends_on'].strftime('%A, %B')} {campaign['ends_on'].day}" if campaign.get("ends_on") else None,
            "owner_name": ctx["sender"] if PLAYBOOKS[playbook_of(campaign)]["sender"] == "owner" else None,
            "checkin_cycle": cycle if cycle > 1 else None,
            "offer_update": offer_change(enrollment, ctx) if cycle > 1 and playbook_of(campaign) == "last_call" else None,
            "previous_offer": enrollment.get("offer_sent") if cycle > 1 else None,
        },
    ) or template
    if not enrollment["touches_sent"] and cycle == 1 and "stop" not in text.lower():
        text = f"{text} {_STOP_LINE}"
    try:
        await client_sms.send_client_sms(campaign["client_id"], phone, text, stage=f"reactivation_touch{touch_num}")
    except Exception as e:
        # 21610: the number replied STOP to this sender at the carrier level.
        if "21610" in str(e):
            await lead_flags.set_opted_out(campaign["client_id"], phone, True)
            return "skipped"
        print(f"[client_reactivation] touch {touch_num} failed for campaign={campaign['id']} phone={phone}: {e}")
        return "failed"
    return "sent"


async def send_due() -> None:
    """One pass over every active campaign: close out enrollments that
    replied / booked / dropped out, restart 90-day check-ins that are due,
    then send whatever touch is due."""
    if REACTIVATION_PAUSED:
        return
    pool = await get_pool()
    now = datetime.now(dt_timezone.utc)
    async with pool.acquire() as conn:
        campaigns = await conn.fetch(
            """
            SELECT rc.*, cl.name AS client_name FROM reactivation_campaigns rc
            JOIN clients cl ON cl.id = rc.client_id
            JOIN client_marketing_config cmc ON cmc.client_id = rc.client_id
            WHERE rc.status = 'active' AND coalesce(cmc.twilio_number, '') != ''
            """
        )
    for campaign in campaigns:
        try:
            campaign = dict(campaign)
            if playbook_of(campaign) == "checkin":
                await _join_newly_eligible(campaign, now)
            if playbook_of(campaign) in CYCLES:
                await _restart_due_checkins(campaign)
            await _run_campaign(campaign, now)
        except Exception as e:
            print(f"[client_reactivation] campaign {campaign['id']} failed: {e}")


_last_join: dict[int, datetime] = {}


async def _join_newly_eligible(campaign: dict, now: datetime) -> None:
    """An active check-in campaign keeps taking in people who become
    eligible later (a list imported after launch). Hourly is plenty."""
    if now - _last_join.get(campaign["id"], datetime.min.replace(tzinfo=dt_timezone.utc)) < timedelta(hours=1):
        return
    _last_join[campaign["id"]] = now
    added = await start_campaign(campaign["id"])
    if added:
        print(f"[client_reactivation] campaign {campaign['id']}: {added} newly eligible joined", flush=True)


async def _restart_due_checkins(campaign: dict) -> None:
    """Check-in playbook: everyone whose next check-in (CHECKIN_CYCLE after
    the last one) is due starts a new cycle, unless they booked, said no, or
    have been talking with the clinic since (then it moves to 90 days after
    that conversation)."""
    cycle_len = CYCLES[playbook_of(campaign)]
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            rf"""
            SELECT re.id, re.cycle,
                   {lead_flags.OPTED_OUT_SQL} AS opted_out,
                   ({lead_flags.UNQUALIFIED_SQL} OR {lead_flags.DONT_CONTACT_SQL}) AS dont_contact,
                   EXISTS (
                       SELECT 1 FROM appointment_reminders a
                       WHERE {_APPT_MATCH} AND a.status != 'canceled' AND coalesce(a.outcome_show, '') != 'no_show'
                         AND (a.appointment_at > now() OR a.created_at > coalesce(re.first_touch_at, re.created_at))
                   ) AS booked,
                   (SELECT clc.status || ':' || coalesce(clc.closed_kind, '') FROM client_lead_conversations clc
                     WHERE clc.client_id = c.client_id AND {_PHONE_MATCH.format(a="clc.phone", b="c.phone")}
                     LIMIT 1) AS thread,
                   (SELECT max(m.created_at) FROM client_sms_messages m
                     WHERE m.client_id = c.client_id
                       AND {_PHONE_MATCH.format(a="CASE WHEN m.direction = 'outbound' THEN m.to_number ELSE m.from_number END", b="c.phone")}
                   ) AS last_message_at
            FROM reactivation_enrollments re JOIN contacts c ON c.id = re.contact_id
            WHERE re.campaign_id = $1 AND re.status IN ('completed', 'replied')
              AND re.next_checkin_at IS NOT NULL AND re.next_checkin_at <= now()
            """,
            campaign["id"],
        )
        for r in rows:
            thread_status, _, closed_kind = (r["thread"] or "").partition(":")
            stop = None
            if r["opted_out"]:
                stop = ("opted_out", "Opted out of texts")
            elif r["dont_contact"]:
                stop = ("stopped", "Tagged Don't contact / Unqualified")
            elif r["booked"]:
                stop = ("booked", "Booked an appointment")
            elif thread_status == "closed" and closed_kind != "doing_fine":
                stop = ("stopped", "Said they're not interested")
            if stop:
                await conn.execute(
                    "UPDATE reactivation_enrollments SET status = $2, end_reason = $3, next_checkin_at = NULL WHERE id = $1",
                    r["id"], *stop)
                continue
            if thread_status == "escalated":
                # A person at the clinic has the thread: look again in a month.
                await conn.execute(
                    "UPDATE reactivation_enrollments SET next_checkin_at = now() + interval '30 days' WHERE id = $1", r["id"])
                continue
            last = r["last_message_at"]
            if last and last + cycle_len > datetime.now(dt_timezone.utc):
                await conn.execute(
                    "UPDATE reactivation_enrollments SET next_checkin_at = $2 WHERE id = $1", r["id"], last + cycle_len)
                continue
            await conn.execute(
                """UPDATE reactivation_enrollments SET status = 'queued', cycle = cycle + 1, touches_sent = 0,
                       first_touch_at = NULL, last_touch_at = NULL, ended_at = NULL, end_reason = NULL,
                       next_checkin_at = NULL
                   WHERE id = $1""",
                r["id"],
            )


async def _run_campaign(campaign: dict, now: datetime) -> None:
    base_touches = touches_of(campaign)
    if not base_touches:
        return
    playbook = playbook_of(campaign)
    last_call = playbook == "last_call"
    pool = await get_pool()
    async with pool.acquire() as conn:
        ctx = await _campaign_context(conn, campaign)
        open_rows = await conn.fetch(
            rf"""
            SELECT re.*, c.owner, c.phone, c.tags, c.lead_source, c.created_at AS contact_created_at,
                   {lead_flags.OPTED_OUT_SQL} AS opted_out,
                   {_excluded_sql(playbook, per_enrollment=True)} AS excluded,
                   {"false" if last_call else _FIRST_TOUCH_EXCLUDED_SQL} AS fresh_excluded,
                   EXISTS (
                       SELECT 1 FROM client_sms_messages m
                       WHERE m.client_id = c.client_id AND m.direction = 'inbound'
                         AND re.first_touch_at IS NOT NULL AND m.created_at > re.first_touch_at
                         AND {_PHONE_MATCH.format(a="m.from_number", b="c.phone")}
                   ) AS replied,
                   EXISTS (
                       SELECT 1 FROM appointment_reminders a
                       WHERE {_APPT_MATCH}
                         AND re.first_touch_at IS NOT NULL AND a.created_at > re.first_touch_at
                   ) AS booked
            FROM reactivation_enrollments re
            JOIN contacts c ON c.id = re.contact_id
            WHERE re.campaign_id = $2 AND re.status IN ('queued', 'active') AND c.client_id = $1
            -- Due 90-day check-ins go ahead of first-timers in the daily cap.
            ORDER BY re.cycle DESC, re.id
            """,
            campaign["client_id"], campaign["id"],
        )
        first_touches_today = await conn.fetchval(
            "SELECT count(*) FROM reactivation_enrollments WHERE campaign_id = $1 AND first_touch_at > now() - interval '24 hours'",
            campaign["id"],
        )

        budget = 10 ** 6 if last_call else max(0, campaign["daily_cap"] - first_touches_today)
        for record in open_rows:
            e = dict(record)
            touches = touches_for(base_touches, playbook, e, ctx)
            if e["opted_out"]:
                await _end(conn, e["id"], "opted_out", "Opted out of texts")
                continue
            if e["booked"]:
                await _end(conn, e["id"], "booked", "Booked an appointment")
                continue
            if e["replied"]:
                await _end(conn, e["id"], "replied", "Replied; the AI agent has the conversation", playbook)
                continue
            if e["excluded"]:
                await _end(conn, e["id"], "excluded", "No longer eligible (booked, opted out, unqualified, don't contact or in another sequence)")
                continue
            if not normalize_phone(e["phone"]):
                await _end(conn, e["id"], "excluded", "Phone number isn't a valid US number")
                continue

            tz_name = await clinic_timezone(conn, campaign["client_id"], e["phone"])
            sent = e["touches_sent"]
            if sent >= len(touches):
                if e["last_touch_at"] and now > e["last_touch_at"] + _REPLY_GRACE:
                    await _end(conn, e["id"], "completed", "All touches sent, no reply", playbook)
                continue
            if sent == 0:
                if e["fresh_excluded"]:
                    await _end(conn, e["id"], "excluded", "Became an active lead before the first text")
                    continue
                if budget <= 0:
                    continue
            else:
                # The next touch waits its gap after the last one actually sent
                # (last_call: the call 24 hours after the text).
                gap = timedelta(days=max(0, int(touches[sent].get("day") or 0) - int(touches[sent - 1].get("day") or 0)))
                if now < e["last_touch_at"] + gap:
                    continue
            if not in_send_window(tz_name, now):
                continue
            if touches[sent].get("call") and await _queue_last_call(campaign, e, ctx):
                result = "sent"
            else:
                result = await _send_touch(campaign, e, sent + 1, touches, ctx)

            if result == "sent":
                await conn.execute(
                    "UPDATE reactivation_enrollments SET status = 'active', touches_sent = $2, "
                    "first_touch_at = coalesce(first_touch_at, now()), last_touch_at = now(), offer_sent = $3 WHERE id = $1",
                    e["id"], sent + 1, ctx.get("offer") if ctx.get("offer") != "special" else None,
                )
                if sent == 0:
                    budget -= 1
            elif result == "skipped":
                await _end(conn, e["id"], "opted_out", "Opted out of texts")
            # 'failed' stays open and is retried next pass.

        # Check-in and last call never finish: their 90 / 30-day rounds keep going.
        if playbook not in CYCLES:
            remaining = await conn.fetchval(
                "SELECT count(*) FROM reactivation_enrollments WHERE campaign_id = $1 AND status IN ('queued', 'active')",
                campaign["id"],
            )
            if remaining == 0:
                await conn.execute("UPDATE reactivation_campaigns SET status = 'done' WHERE id = $1", campaign["id"])


async def _queue_last_call(campaign: dict, e: dict, ctx: dict) -> bool:
    """The last-day call. True = the voice agent has it (it texts them itself
    if they don't pick up); False = send the text touch instead."""
    import client_voice_agent
    is_meta = e.get("lead_source") == "meta_form" or "meta_lead" in (e.get("tags") or [])
    return await client_voice_agent.queue_last_call(
        campaign["client_id"], e["phone"], e.get("owner"), is_meta, e.get("contact_created_at"),
        (f"the offer is our {ctx['offer']}" + (f", {ctx['offer_detail']}" if ctx.get("offer_detail") else ""))
        if ctx.get("offer") and ctx["offer"] != "special" else None,
    )


async def campaign_stats(conn, campaign_id: int) -> dict:
    rows = await conn.fetch(
        "SELECT status, count(*) AS n, count(*) FILTER (WHERE touches_sent > 0) AS texted "
        "FROM reactivation_enrollments WHERE campaign_id = $1 GROUP BY status",
        campaign_id,
    )
    by_status = {r["status"]: r["n"] for r in rows}
    texted = sum(r["texted"] for r in rows)
    return {
        "enrolled": sum(by_status.values()),
        "texted": texted,
        "queued": by_status.get("queued", 0),
        "active": by_status.get("active", 0),
        "replied": by_status.get("replied", 0) + by_status.get("booked", 0),
        "booked": by_status.get("booked", 0),
        "opted_out": by_status.get("opted_out", 0),
        "completed": by_status.get("completed", 0),
        "excluded": by_status.get("excluded", 0),
    }


# ---------------------------------------------------------------------------
# Auto-start from ad spend (Dylan, 2026-11-16)
# ---------------------------------------------------------------------------

async def _tick_launch_item(conn, client_id: int, title: str) -> None:
    """Tick one launch checklist item (the portal's To Do tab) by title."""
    await conn.execute(
        """INSERT INTO client_launch_checklist_status (client_id, item_id, completed_at)
           SELECT $1, li.id, now() FROM launch_checklist_items li WHERE li.active AND lower(li.title) = $2
           ON CONFLICT (client_id, item_id) DO UPDATE
             SET completed_at = coalesce(client_launch_checklist_status.completed_at, now())""",
        client_id, title,
    )


async def _create_campaign(conn, client_id: int, playbook: str, name: str, trigger: str) -> int:
    preset = PLAYBOOKS[playbook]
    return await conn.fetchval(
        """INSERT INTO reactivation_campaigns (client_id, name, audience_sources, audience_tags, angle, touches,
                                               daily_cap, playbook, auto_trigger)
           VALUES ($1, $2, $3, '{}', $4, $5::jsonb, 30, $6, $7) RETURNING id""",
        client_id, name, preset["sources"], preset["angle"], json.dumps(preset["touches"]), playbook, trigger,
    )


async def on_ad_spend(client_id: int, spend: float, cap: float | None) -> list[str]:
    """Called by ad_spend_caps after every spend check. Returns what it did.

    - First dollar spent: stamp it (and campaign_launched_at if unset), tick
      the "Launch campaign" checklist item, and start the check-in campaign
      (an existing draft one, else a new default one), ticking "Launch
      database reactivation".
    - Ad budget spent (spend >= cap): start a last_call campaign, once per
      cap value (raising the cap and spending that too runs another, which
      skips anyone an earlier last call already reached).
    While REACTIVATION_PAUSED only the stamps and "Launch campaign" happen;
    the campaigns start on the first check after the switch flips."""
    done: list[str] = []
    pool = await get_pool()
    async with pool.acquire() as conn:
        cfg = await conn.fetchrow(
            "SELECT ad_first_spend_at, react_checkin_auto_at, react_lastcall_auto_cap FROM client_marketing_config "
            "WHERE client_id = $1", client_id)
        if not cfg:
            return done
        first_spend = cfg["ad_first_spend_at"]
        if spend > 0 and not first_spend:
            first_spend = datetime.now(dt_timezone.utc)
            await conn.execute(
                "UPDATE client_marketing_config SET ad_first_spend_at = $2, "
                "campaign_launched_at = coalesce(campaign_launched_at, $2) WHERE client_id = $1",
                client_id, first_spend)
            await _tick_launch_item(conn, client_id, _LAUNCH_ITEM)
            done.append("first ad dollar spent: ticked Launch campaign")
        if REACTIVATION_PAUSED:
            return done

        if first_spend and not cfg["react_checkin_auto_at"]:
            existing = await conn.fetchrow(
                "SELECT id, status FROM reactivation_campaigns WHERE client_id = $1 AND playbook = 'checkin' "
                "AND status IN ('draft', 'active', 'paused') ORDER BY (status = 'active') DESC, id LIMIT 1", client_id)
            if existing and existing["status"] == "active":
                campaign_id = None
            elif existing and existing["status"] == "draft":
                campaign_id = existing["id"]
            elif existing:  # paused by hand: leave it paused
                campaign_id = None
            else:
                campaign_id = await _create_campaign(conn, client_id, "checkin", "Check-in (clinic's list)", "first_spend")
            await conn.execute(
                "UPDATE client_marketing_config SET react_checkin_auto_at = now() WHERE client_id = $1", client_id)
            await _tick_launch_item(conn, client_id, _REACTIVATION_ITEM)
        else:
            campaign_id = None

        lastcall_id = None
        if cap and spend >= cap and (cfg["react_lastcall_auto_cap"] is None or cap > float(cfg["react_lastcall_auto_cap"])):
            lastcall_id = await _create_campaign(
                conn, client_id, "last_call", f"Last call (ad budget of ${cap:,.0f} spent)", "budget_spent")
            await conn.execute(
                "UPDATE client_marketing_config SET react_lastcall_auto_cap = $2 WHERE client_id = $1", client_id, cap)

    if campaign_id:
        added = await start_campaign(campaign_id)
        done.append(f"started check-in campaign {campaign_id} ({added} people)")
    if lastcall_id:
        added = await start_campaign(lastcall_id)
        done.append(f"started last call {lastcall_id} ({added} people)")
    if done:
        print(f"[client_reactivation] client={client_id} ad spend {spend} / cap {cap}: {'; '.join(done)}", flush=True)
    return done


# ---------------------------------------------------------------------------
# Queue: who gets what next (OS → Database Reactivation Agent → VIEW QUEUE)
# ---------------------------------------------------------------------------

def _nth_send_day(local_now: datetime, n: int) -> date:
    """The date of the n-th send window from now (0 = the next one)."""
    d = local_now.date()
    if local_now.hour >= SEND_END_HOUR or d.weekday() == 6:
        d += timedelta(days=1)
    while d.weekday() == 6:
        d += timedelta(days=1)
    for _ in range(n):
        d += timedelta(days=1)
        while d.weekday() == 6:
            d += timedelta(days=1)
    return d


async def queue(client_id: int) -> list[dict]:
    """Everything scheduled to reach this client's leads: reactivation texts
    and calls (with when), 90-day check-ins, check-ins leads asked for
    (schedule_followup) and voice calls waiting to dial. Sorted by when."""
    pool = await get_pool()
    now = datetime.now(dt_timezone.utc)
    out: list[dict] = []
    async with pool.acquire() as conn:
        tz = _tz(await clinic_timezone(conn, client_id, None))
        local_now = now.astimezone(tz)
        rows = await conn.fetch(
            """SELECT re.id, re.status, re.touches_sent, re.last_touch_at, re.next_checkin_at, re.cycle, re.offer_sent,
                      rc.id AS campaign_id, rc.name AS campaign, rc.status AS campaign_status, rc.touches,
                      rc.daily_cap, rc.playbook, c.id AS contact_id, c.owner, c.phone
               FROM reactivation_enrollments re
               JOIN reactivation_campaigns rc ON rc.id = re.campaign_id
               JOIN contacts c ON c.id = re.contact_id
               WHERE rc.client_id = $1 AND rc.status IN ('active', 'paused', 'draft')
                 AND (re.status IN ('queued', 'active') OR re.next_checkin_at IS NOT NULL)
               ORDER BY re.cycle DESC, re.id""",
            client_id,
        )
        position: dict[int, int] = {}
        for r in rows:
            touches = touches_for(touches_of(r), r["playbook"], dict(r), None)
            later = "30-day offer update" if r["playbook"] == "last_call" else "90-day check-in"
            item = {"kind": "reactivation", "playbook": r["playbook"], "id": r["id"], "contact_id": r["contact_id"], "name": r["owner"],
                    "phone": r["phone"], "campaign": r["campaign"], "paused": r["campaign_status"] != "active"}
            label = later if (r["cycle"] or 1) > 1 else None
            if r["status"] == "queued":
                pos = position.get(r["campaign_id"], 0)
                position[r["campaign_id"]] = pos + 1
                per_day = 10 ** 6 if r["playbook"] == "last_call" else max(1, r["daily_cap"] or 30)
                item.update(due=_nth_send_day(local_now, pos // per_day).isoformat(), estimated=True,
                            what=label or "First text")
            elif r["status"] == "active":
                sent = r["touches_sent"]
                if sent >= len(touches):
                    continue  # all sent, waiting a few days for a reply
                gap = timedelta(days=max(0, int(touches[sent].get("day") or 0) - int(touches[sent - 1].get("day") or 0)))
                due = max(r["last_touch_at"] + gap, now)
                call = bool(touches[sent].get("call"))
                item.update(due=due.isoformat(), estimated=False,
                            what=("Call (text if no answer)" if call else f"Follow-up text {sent + 1}"))
            else:
                item.update(due=r["next_checkin_at"].isoformat(), estimated=False,
                            what=f"{later} #{r['cycle']}", stoppable=True)
            item["stoppable"] = True
            out.append(item)

        for r in await conn.fetch(
            """SELECT id, owner, phone, client_followup_snooze_until, client_followup_snooze_note FROM contacts
               WHERE client_id = $1 AND client_followup_snooze_until IS NOT NULL""", client_id):
            out.append({"kind": "asked_followup", "id": r["id"], "contact_id": r["id"], "name": r["owner"],
                        "phone": r["phone"], "campaign": "They asked to be texted then",
                        "what": "Check-in they asked for" + (f": {r['client_followup_snooze_note']}" if r["client_followup_snooze_note"] else ""),
                        "due": r["client_followup_snooze_until"].isoformat(), "estimated": False, "stoppable": True})

        for r in await conn.fetch(
            """SELECT id, phone, lead_name, source, run_at FROM client_voice_calls
               WHERE client_id = $1 AND status = 'pending' ORDER BY run_at""", client_id):
            what = {"callback": "Call back they asked for", "lastcall": "Last-call call", "meta": "First call (new lead)",
                    "funnel": "Call (unfinished booking)"}.get(r["source"], "Call")
            out.append({"kind": "voice_call", "id": r["id"], "name": r["lead_name"], "phone": r["phone"],
                        "campaign": "Voice agent", "what": what, "due": r["run_at"].isoformat(), "estimated": False,
                        "stoppable": False})
    out.sort(key=lambda i: i["due"])
    return out


async def stop_queued(client_id: int, kind: str, item_id) -> bool:
    """Dylan (or the owner via Dylan) says don't: stop this person's
    reactivation for good, or cancel a check-in they asked for."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if kind == "reactivation":
            res = await conn.execute(
                """UPDATE reactivation_enrollments re SET status = 'stopped', end_reason = 'Stopped by hand',
                       ended_at = now(), next_checkin_at = NULL
                   FROM reactivation_campaigns rc
                   WHERE rc.id = re.campaign_id AND rc.client_id = $1 AND re.id = $2""",
                client_id, int(item_id))
        elif kind == "asked_followup":
            res = await conn.execute(
                "UPDATE contacts SET client_followup_snooze_until = NULL, client_followup_snooze_note = NULL "
                "WHERE client_id = $1 AND id = $2", client_id, str(item_id))
        else:
            return False
    return not res.endswith(" 0")
