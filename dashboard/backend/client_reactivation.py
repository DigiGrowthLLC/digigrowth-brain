"""Database reactivation — a CLIENT's own AI text outreach to people already
in their records: past patients, old inquiries that never booked, and the
client's own leads that went quiet. Never fresh ad leads (those belong to
response_ai.py's opener + client_followup_sequence.py).

A campaign (reactivation_campaigns) is one audience of the client's leads,
picked by lead_source and/or tag, with its own 4 SMS touches (day 0 / 2 / 6
/ 14 by default) and a daily cap on first texts so bookings spread across
the clinic's real capacity and the number's reputation stays clean.
Starting a campaign snapshots who's eligible into reactivation_enrollments;
send_due() (main.py, every 5 minutes) works through them.

Eligible = the client's own lead with a phone, in the audience, and none
of: an upcoming appointment or one in the last 60 days, enrolled in the
prospect follow-up, a recent ad lead (Meta form / funnel / DM in the last
30 days), any text on the client's number in the last 30 days, tagged
Unqualified or SMS Opted Out, an escalated thread, or already open in
another reactivation campaign. Re-checked right before every touch.

Each touch is the campaign's template, rewritten for the person by
response_ai.write_reactivation_text (their lead_source, source_detail, the
campaign angle, any old thread), or sent as-is when the agent is off. Sent
with stage 'reactivation_touchN', which never enrolls anyone in the
prospect follow-up. The first touch always carries "Reply STOP to opt out".

A reply ends the outreach (status 'replied') and the response AI takes the
conversation from there, with the campaign's angle in its prompt
(response_ai._lead_origin). From then on it's an ordinary conversation:
the AI's replies enroll them in the normal gone-quiet follow-up.

Touches go out 10am-6pm Monday-Saturday in the lead's timezone.
"""

import json
import re
from datetime import datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

import lead_flags
from db import get_pool
from merge_fields import first_name_from_owner
from timezone_lookup import guess_timezone

# Offer-neutral starting copy (each client's offer differs; edit per
# campaign). Plain GSM-7 characters only.
DEFAULT_TOUCHES = [
    {"day": 0, "body": "Hi {first_name}, it's the team at {business}. It's been a while, how have you been feeling?"},
    {"day": 2, "body": "{first_name}, if anything has been bothering you again, we'd love to help you get back to "
                       "feeling your best. Want me to find you a time to come in?"},
    {"day": 6, "body": "Hi {first_name}, would it help if I sent over a couple of times that work this week?"},
    {"day": 14, "body": "{first_name}, I won't keep texting. Whenever you want to get back in, just reply here "
                        "and we'll take care of you."},
]

# Sources an audience can be built from (contacts.lead_source). Fresh ad
# sources are left out on purpose.
AUDIENCE_SOURCES = ["past_patient", "old_inquiry", "import", "manual", "website", "inbound_sms", "meta_form", "funnel"]
_FRESH_AD_SOURCES = ["meta_form", "funnel", "fb_dm", "ig_dm"]

SEND_START_HOUR = 10
SEND_END_HOUR = 18
# A reply this long after the last touch still counts as a reply to it.
_REPLY_GRACE = timedelta(days=3)
_STOP_LINE = "Reply STOP to opt out."

_PHONE_MATCH = r"right(regexp_replace({a}, '\D', '', 'g'), 10) = right(regexp_replace({b}, '\D', '', 'g'), 10)"

# Exclusions that hold for every touch. `c` = contacts. $1 = client_id.
_ALWAYS_EXCLUDED_SQL = rf"""(
    {lead_flags.UNQUALIFIED_SQL}
    OR {lead_flags.OPTED_OUT_SQL}
    OR c.client_followup_enrolled_at IS NOT NULL
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

# Extra exclusions checked at enrollment and before the first touch only
# (afterwards our own touches would trip the recent-text check).
_FIRST_TOUCH_EXCLUDED_SQL = rf"""(
    (c.lead_source = ANY(ARRAY{_FRESH_AD_SOURCES!r}::text[]) AND c.created_at > now() - interval '30 days')
    OR ((c.tags && ARRAY['meta_lead', 'ads-lead']) AND c.created_at > now() - interval '30 days')
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


def touches_of(campaign) -> list[dict]:
    touches = campaign["touches"]
    if isinstance(touches, str):
        touches = json.loads(touches)
    return [t for t in (touches or []) if (t.get("body") or "").strip()]


def in_send_window(phone: str, now: datetime) -> bool:
    try:
        tz = ZoneInfo(guess_timezone(phone) or "America/Chicago")
    except Exception:
        tz = ZoneInfo("America/Chicago")
    local = now.astimezone(tz)
    return local.weekday() != 6 and SEND_START_HOUR <= local.hour < SEND_END_HOUR


async def eligible_contacts(conn, client_id: int, sources: list[str], tags: list[str], campaign_id: int | None = None):
    """Who a campaign with this audience would text if started now."""
    return await conn.fetch(
        f"""
        SELECT c.id, c.owner, c.phone, c.lead_source, c.source_detail FROM contacts c
        WHERE c.client_id = $1 AND NOT c.is_client_anchor AND coalesce(c.phone, '') != ''
          AND {_AUDIENCE_SQL}
          AND NOT {_ALWAYS_EXCLUDED_SQL}
          AND NOT {_FIRST_TOUCH_EXCLUDED_SQL}
          AND NOT {_OPEN_ELSEWHERE_SQL}
          AND NOT EXISTS (SELECT 1 FROM reactivation_enrollments re WHERE re.contact_id = c.id AND re.campaign_id = $4)
        ORDER BY c.created_at ASC
        """,
        client_id, sources, tags, campaign_id or 0,
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


def _fill(template: str, contact: dict, business: str) -> str:
    return (
        (template or "")
        .replace("{first_name}", first_name_from_owner(contact.get("owner")))
        .replace("{business}", business or "")
        .strip()
    )


async def _end(conn, enrollment_id: int, status: str, reason: str) -> None:
    await conn.execute(
        "UPDATE reactivation_enrollments SET status = $2, end_reason = $3, ended_at = now() WHERE id = $1",
        enrollment_id, status, reason,
    )


async def _send_touch(campaign: dict, enrollment: dict, touch_num: int, touches: list[dict]) -> str:
    """Returns 'sent', 'skipped' (the send was refused, e.g. opted out
    since) or 'failed'."""
    import client_sms
    import response_ai

    phone = normalize_phone(enrollment["phone"])
    template = _fill(touches[touch_num - 1]["body"], enrollment, campaign["client_name"])
    text = await response_ai.write_reactivation_text(
        campaign["client_id"], phone, template, touch_num, len(touches),
    ) or template
    if touch_num == 1 and "stop" not in text.lower():
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
    replied / booked / dropped out, send follow-up touches that are due,
    then start new people up to the campaign's daily cap."""
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
    pool = await get_pool()
    async with pool.acquire() as conn:
        open_rows = await conn.fetch(
            rf"""
            SELECT re.*, c.owner, c.phone,
                   {lead_flags.OPTED_OUT_SQL} AS opted_out,
                   {_ALWAYS_EXCLUDED_SQL} AS excluded,
                   {_FIRST_TOUCH_EXCLUDED_SQL} AS fresh_excluded,
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
                   ) AS booked
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

        budget = max(0, campaign["daily_cap"] - first_touches_today)
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
                await _end(conn, e["id"], "excluded", "No longer eligible (booked, opted out, unqualified or in another sequence)")
                continue
            if not normalize_phone(e["phone"]):
                await _end(conn, e["id"], "excluded", "Phone number isn't a valid US number")
                continue

            sent = e["touches_sent"]
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
                gap = timedelta(days=max(0, touches[sent]["day"] - touches[sent - 1]["day"]))
                if now < e["last_touch_at"] + gap:
                    continue
            if not in_send_window(normalize_phone(e["phone"]), now):
                continue

            result = await _send_touch(campaign, e, sent + 1, touches)
            if result == "sent":
                await conn.execute(
                    "UPDATE reactivation_enrollments SET status = 'active', touches_sent = touches_sent + 1, "
                    "first_touch_at = coalesce(first_touch_at, now()), last_touch_at = now() WHERE id = $1",
                    e["id"],
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
