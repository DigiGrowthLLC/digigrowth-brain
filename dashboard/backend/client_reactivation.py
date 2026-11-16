"""Database reactivation: a CLIENT's own AI outreach to people already in
their records. Each campaign runs one PLAYBOOK (Dylan, 2026-11-16), because
not every lead should get the same message:

- checkin: the clinic's own list (past patients, old inquiries, imports,
  people added by hand). Sent as the OWNER ("it's Brian from Pinnacle"), a
  familiar face. A check-in on the issue they're tagged with ("how's that
  shoulder been?"), never a pitch. Doing fine -> "awesome, reach out if it
  acts up" and the thread closes. Hurting -> a couple of relaxed questions,
  then "you'd qualify for our <offer>". 2 texts.
- social: Instagram/Facebook DM leads that went quiet. Same relaxed,
  question-first approach, sent as the clinic's agent name. 2 texts.
- last_call: ad leads (Meta form / funnel) from the current campaign who never
  booked. Timed to the offer's last day (ends_on): a heads-up text 2 days
  before, then on the last day a voice call (if they consented to calls)
  that falls back to a last-day text. No daily cap: it's a deadline.

The relaxed approach also drives the conversation once they reply: see
response_ai.GENTLE_ARC (and the DM agent, which uses it for every DM).

Starting a campaign snapshots who's eligible into reactivation_enrollments;
send_due() (main.py, every 5 minutes) works through them. Exclusions (all
playbooks): an upcoming appointment or one in the last 60 days, Unqualified,
SMS Opted Out, the client's own "Don't contact"/DNC tag, an escalated thread
or one closed in the last 90 days, already open in another campaign.
checkin/social also skip anyone in the prospect follow-up, recent ad leads
and anyone texted in the last 30 days. Re-checked before every touch.

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
# {business} {checkin_question} {offer} {end_day}. For last_call, "day" is
# how many days BEFORE the offer ends the touch goes out, and "call": true
# means call first (consent permitting) and text only if they don't pick up.
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
        "description": "Meta form and funnel leads from the current campaign who never booked. A heads-up 2 days "
                       "before the offer ends, then a call on the last day (text if no answer or no call consent).",
        "sender": "agent",
        "sources": ["meta_form", "funnel"],
        "angle": "The ad offer they asked about is ending: a last chance to get in at that offer.",
        "touches": [
            {"day": 2, "body": "Hey {first_name}, it's {sender} from {business}. Just a heads up, our {offer} offer "
                               "ends {end_day}. Didn't want you to miss out if that pain is still bugging you."},
            {"day": 0, "call": True, "body": "Hey {first_name}, today's the last day for our {offer}. Just didn't "
                                             "want you to miss out. Want me to grab you a time?"},
        ],
    },
}
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


def _excluded_sql(playbook: str) -> str:
    """Exclusions that hold for every touch. `c` = contacts."""
    followup = "" if playbook == "last_call" else "OR c.client_followup_enrolled_at IS NOT NULL"
    return rf"""(
    {lead_flags.UNQUALIFIED_SQL}
    OR {lead_flags.OPTED_OUT_SQL}
    OR {lead_flags.DONT_CONTACT_SQL}
    {followup}
    OR EXISTS (
        SELECT 1 FROM appointment_reminders a
        WHERE (a.contact_id = c.id OR {_PHONE_MATCH.format(a="coalesce(a.prospect_phone, '')", b="c.phone")})
          AND a.appointment_at > now() - interval '60 days'
          AND a.status != 'canceled'
    )
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

# last_call: an ad lead (by source or tag) who came in during this campaign.
# $2 = ends_on.
_LAST_CALL_AUDIENCE_SQL = rf"""(
    (coalesce(c.lead_source, '') = ANY(ARRAY{_FRESH_AD_SOURCES[:2]!r}::text[]) OR c.tags && ARRAY{_AD_TAGS!r}::text[])
    AND c.created_at >= ($2::date - {LAST_CALL_LOOKBACK_DAYS})
    AND c.created_at < ($2::date + 1)
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


async def eligible_contacts(conn, client_id: int, sources: list[str], tags: list[str], campaign_id: int | None = None,
                            playbook: str = DEFAULT_PLAYBOOK, ends_on: date | None = None):
    """Who a campaign with this audience would reach if started now."""
    if playbook == "last_call":
        if not ends_on:
            return []
        audience, first_touch, params = _LAST_CALL_AUDIENCE_SQL, "false", [client_id, ends_on]
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
    visit = await client_voice_agent._visit_info(campaign["client_id"])
    ends_on = campaign.get("ends_on")
    return {
        "sender": sender or names["agent"] or "the team",
        "business": campaign["client_name"] or "",
        "offer": (visit or {}).get("name") or "special",
        "end_day": ends_on.strftime("%A") if ends_on else "soon",
    }


def fill(template: str, contact: dict, ctx: dict) -> str:
    out = (template or "")
    for key, val in {
        "{first_name}": first_name_from_owner(contact.get("owner")) or "there",
        "{sender}": ctx.get("sender") or "",
        "{business}": ctx.get("business") or "",
        "{offer}": ctx.get("offer") or "",
        "{end_day}": ctx.get("end_day") or "",
        "{checkin_question}": checkin_question(contact.get("tags")),
    }.items():
        out = out.replace(key, val)
    return re.sub(r"\s+", " ", out).strip()


async def _end(conn, enrollment_id: int, status: str, reason: str) -> None:
    await conn.execute(
        "UPDATE reactivation_enrollments SET status = $2, end_reason = $3, ended_at = now() WHERE id = $1",
        enrollment_id, status, reason,
    )


async def _send_touch(campaign: dict, enrollment: dict, touch_num: int, touches: list[dict], ctx: dict) -> str:
    """Returns 'sent', 'skipped' (the send was refused, e.g. opted out
    since) or 'failed'."""
    import client_sms
    import response_ai

    phone = normalize_phone(enrollment["phone"])
    template = fill(touches[touch_num - 1]["body"], enrollment, ctx)
    text = await response_ai.write_reactivation_text(
        campaign["client_id"], phone, template, touch_num, len(touches), playbook=playbook_of(campaign),
        origin_extra={
            "playbook": playbook_of(campaign),
            "campaign_angle": campaign.get("angle"),
            "ends_on": f"{campaign['ends_on'].strftime('%A, %B')} {campaign['ends_on'].day}" if campaign.get("ends_on") else None,
            "owner_name": ctx["sender"] if PLAYBOOKS[playbook_of(campaign)]["sender"] == "owner" else None,
        },
    ) or template
    if not enrollment["touches_sent"] and "stop" not in text.lower():
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
    replied / booked / dropped out, then send whatever touch is due."""
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
            await _run_campaign(dict(campaign), now)
        except Exception as e:
            print(f"[client_reactivation] campaign {campaign['id']} failed: {e}")


async def _run_campaign(campaign: dict, now: datetime) -> None:
    touches = touches_of(campaign)
    if not touches:
        return
    playbook = playbook_of(campaign)
    last_call = playbook == "last_call"
    if last_call and not campaign.get("ends_on"):
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        ctx = await _campaign_context(conn, campaign)
        open_rows = await conn.fetch(
            rf"""
            SELECT re.*, c.owner, c.phone, c.tags, c.lead_source, c.created_at AS contact_created_at,
                   {lead_flags.OPTED_OUT_SQL} AS opted_out,
                   {_excluded_sql(playbook)} AS excluded,
                   {"false" if last_call else _FIRST_TOUCH_EXCLUDED_SQL} AS fresh_excluded,
                   EXISTS (
                       SELECT 1 FROM client_sms_messages m
                       WHERE m.client_id = c.client_id AND m.direction = 'inbound'
                         AND re.first_touch_at IS NOT NULL AND m.created_at > re.first_touch_at
                         AND {_PHONE_MATCH.format(a="m.from_number", b="c.phone")}
                   ) AS replied,
                   EXISTS (
                       SELECT 1 FROM appointment_reminders a
                       WHERE (a.contact_id = c.id OR {_PHONE_MATCH.format(a="coalesce(a.prospect_phone, '')", b="c.phone")})
                         AND re.first_touch_at IS NOT NULL AND a.created_at > re.first_touch_at
                   ) AS booked,
                   -- last_call: they're mid-conversation, or texted in the last day: hold this touch.
                   EXISTS (
                       SELECT 1 FROM client_sms_messages m
                       WHERE m.client_id = c.client_id
                         AND ((m.direction = 'inbound' AND m.created_at > now() - interval '3 days')
                              OR (m.direction = 'outbound' AND m.created_at > now() - interval '20 hours'))
                         AND {_PHONE_MATCH.format(a="CASE WHEN m.direction = 'outbound' THEN m.to_number ELSE m.from_number END", b="c.phone")}
                   ) AS busy_thread
            FROM reactivation_enrollments re
            JOIN contacts c ON c.id = re.contact_id
            WHERE re.campaign_id = $2 AND re.status IN ('queued', 'active') AND c.client_id = $1
            ORDER BY re.id
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
            if e["opted_out"]:
                await _end(conn, e["id"], "opted_out", "Opted out of texts")
                continue
            if e["booked"]:
                await _end(conn, e["id"], "booked", "Booked an appointment")
                continue
            if e["replied"]:
                await _end(conn, e["id"], "replied", "Replied; the AI agent has the conversation")
                continue
            if e["excluded"]:
                await _end(conn, e["id"], "excluded", "No longer eligible (booked, opted out, unqualified, don't contact or in another sequence)")
                continue
            if not normalize_phone(e["phone"]):
                await _end(conn, e["id"], "excluded", "Phone number isn't a valid US number")
                continue

            tz_name = await clinic_timezone(conn, campaign["client_id"], e["phone"])
            sent = e["touches_sent"]

            if last_call:
                today = now.astimezone(_tz(tz_name)).date()
                if today > campaign["ends_on"]:
                    await _end(conn, e["id"], "completed", "The offer ended")
                    continue
                # The latest touch that's due by today (a late start skips
                # straight to it), one touch a day at most.
                due = None
                for i in range(sent, len(touches)):
                    if campaign["ends_on"] - timedelta(days=int(touches[i].get("day") or 0)) <= today:
                        due = i
                if due is None or e["busy_thread"]:
                    continue
                if e["last_touch_at"] and e["last_touch_at"].astimezone(_tz(tz_name)).date() == today:
                    continue
                if not in_send_window(tz_name, now):
                    continue
                if touches[due].get("call") and await _queue_last_call(campaign, e, ctx):
                    result = "sent"
                else:
                    result = await _send_touch(campaign, e, due + 1, touches, ctx)
                new_count = due + 1
            else:
                if sent >= len(touches):
                    if e["last_touch_at"] and now > e["last_touch_at"] + _REPLY_GRACE:
                        await _end(conn, e["id"], "completed", "All touches sent, no reply")
                    continue
                if sent == 0:
                    if e["fresh_excluded"]:
                        await _end(conn, e["id"], "excluded", "Became an active lead before the first text")
                        continue
                    if budget <= 0:
                        continue
                else:
                    gap = timedelta(days=max(0, int(touches[sent]["day"]) - int(touches[sent - 1]["day"])))
                    if now < e["last_touch_at"] + gap:
                        continue
                if not in_send_window(tz_name, now):
                    continue
                result = await _send_touch(campaign, e, sent + 1, touches, ctx)
                new_count = sent + 1

            if result == "sent":
                await conn.execute(
                    "UPDATE reactivation_enrollments SET status = 'active', touches_sent = $2, "
                    "first_touch_at = coalesce(first_touch_at, now()), last_touch_at = now() WHERE id = $1",
                    e["id"], new_count,
                )
                if sent == 0:
                    budget -= 1
            elif result == "skipped":
                await _end(conn, e["id"], "opted_out", "Opted out of texts")
            # 'failed' stays open and is retried next pass.

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
        f"the offer is our {ctx['offer']}" if ctx.get("offer") and ctx["offer"] != "special" else None,
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
