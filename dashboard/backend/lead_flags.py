"""Shared guards for a CLIENT's own lead messaging — the "Unqualified" stop
and the quiet-hours window — used by every automated client send
(client_sms.py, response_ai.py, client_followup_sequence.py,
client_appointment_reminders.py, client_appointment_sequence.py).

Unqualified: the client's response AI tags a lead "Unqualified"
(response_ai.py's mark_unqualified tool — e.g. they live outside the service
area) and from then on NO automated text reaches them: no AI
replies, no follow-up touches, no reminders, no no-show/cancellation drips.
The tag is the single source of truth, so a client who removes it in the
portal re-enables everything. Manual replies typed by the client in the
portal inbox still send (send_client_sms manual=True) —
a human deciding to reach out is never blocked.

Quiet hours: delayed automated touches never land outside 8am-9pm in the
lead's local time (TCPA's marketing-text window); they wait for the morning
instead. The one exception is the 1-hour appointment reminder (see
client_appointment_reminders.py), which is tied to an appointment the lead
booked themselves.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from db import get_pool

UNQUALIFIED_TAG = "Unqualified"
# Outcome/lifecycle tags stamped automatically on a client's own leads. The
# first two reuse the starter catalog names in db.py so imported and live
# leads share one tag each.
NO_SHOW_TAG = "No-Show History"
CANCELED_TAG = "Cancelled Appointment"
# A lead who reached the last touch of the prospect follow-up, no-show or
# cancellation sequence without replying: the pool for database reactivation.
REACTIVATION_TAG = "Database Reactivation"
# A lead who texted STOP (or another carrier opt-out keyword) to the
# client's number. Twilio already blocks texts to them at the carrier
# level; the tag keeps every automated send from even trying, and keeps
# them out of reactivation audiences. START/UNSTOP removes it.
OPTED_OUT_TAG = "SMS Opted Out"
OPT_OUT_KEYWORDS = {"stop", "stopall", "unsubscribe", "cancel", "end", "quit", "optout", "revoke"}
OPT_IN_KEYWORDS = {"start", "unstop", "yes"}
# Auto-tags by where a client's lead came from (contacts.lead_source), so
# every lead carries a tag agents can later be routed on. Applied when the
# lead is created (each entry point) and backfilled in db.py.
INBOUND_TAG = "Inbound Lead"
SOCIAL_TAG = "Social Media"
SOURCE_TAGS = {
    "meta_form": ["meta_lead"],
    "funnel": ["ads-lead"],
    "website": ["organic-lead"],
    "inbound_sms": [INBOUND_TAG],
    "ig_dm": [SOCIAL_TAG],
    "fb_dm": [SOCIAL_TAG],
    "manual": [REACTIVATION_TAG],
    "import": [REACTIVATION_TAG],
    "old_inquiry": [REACTIVATION_TAG],
    "past_patient": [REACTIVATION_TAG, "Previous Patient"],
}
QUIET_START_HOUR = 21  # 9pm local
QUIET_END_HOUR = 8     # 8am local

# True when contact alias `c` carries the Unqualified tag, any case or
# separator (clients make their own tags in the portal, same normalization
# as client_followup_sequence.py's booked-tag check).
UNQUALIFIED_SQL = r"""EXISTS (
    SELECT 1 FROM unnest(coalesce(c.tags, '{}')) ut
    WHERE lower(regexp_replace(ut, '[^A-Za-z]', '', 'g')) = 'unqualified'
)"""

OPTED_OUT_SQL = r"""EXISTS (
    SELECT 1 FROM unnest(coalesce(c.tags, '{}')) ot
    WHERE lower(regexp_replace(ot, '[^A-Za-z]', '', 'g')) = 'smsoptedout'
)"""


def opt_keyword(body: str) -> str | None:
    """'out' / 'in' when the whole text is a carrier opt-out / opt-in
    keyword ("STOP", "Stop.", "unstop"), else None. Only a bare keyword
    counts: "stop calling me at work" is a conversation, not an opt-out.
    "yes" only re-opts-in a lead who is currently opted out (the caller
    checks), since it's an ordinary reply everywhere else."""
    word = "".join(ch for ch in (body or "").lower() if ch.isalpha())
    if word in OPT_OUT_KEYWORDS:
        return "out"
    if word in OPT_IN_KEYWORDS:
        return "in"
    return None


async def set_opted_out(client_id: int, phone: str, opted_out: bool) -> None:
    """Tag (or untag) this client's lead with that phone as SMS Opted Out.
    Never raises."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            if opted_out:
                await conn.execute(
                    r"""
                    UPDATE contacts c SET tags = array_append(coalesce(c.tags, '{}'), $3), updated_at = now()
                    WHERE c.client_id = $1 AND NOT c.is_client_anchor AND coalesce(c.phone, '') != ''
                      AND right(regexp_replace(c.phone, '\D', '', 'g'), 10) = right(regexp_replace($2, '\D', '', 'g'), 10)
                      AND NOT """ + OPTED_OUT_SQL,
                    client_id, phone, OPTED_OUT_TAG,
                )
            else:
                await conn.execute(
                    r"""
                    UPDATE contacts c SET tags = array(
                        SELECT t FROM unnest(c.tags) t
                        WHERE lower(regexp_replace(t, '[^A-Za-z]', '', 'g')) != 'smsoptedout'
                    ), updated_at = now()
                    WHERE c.client_id = $1 AND NOT c.is_client_anchor AND coalesce(c.phone, '') != ''
                      AND right(regexp_replace(c.phone, '\D', '', 'g'), 10) = right(regexp_replace($2, '\D', '', 'g'), 10)
                      AND """ + OPTED_OUT_SQL,
                    client_id, phone,
                )
    except Exception as e:
        print(f"[lead_flags] opt-out update failed for client={client_id} phone={phone}: {e}")


async def is_opted_out(client_id: int, phone: str | None) -> bool:
    """Whether this client's lead with that phone texted STOP. Never raises
    (False on a lookup failure, same as is_unqualified)."""
    phone = (phone or "").strip()
    if not phone:
        return False
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            return bool(await conn.fetchval(
                rf"""
                SELECT EXISTS (
                    SELECT 1 FROM contacts c
                    WHERE c.client_id = $1 AND NOT c.is_client_anchor AND {OPTED_OUT_SQL}
                      AND coalesce(c.phone, '') != ''
                      AND right(regexp_replace(c.phone, '\D', '', 'g'), 10) = right(regexp_replace($2, '\D', '', 'g'), 10)
                )
                """,
                client_id, phone,
            ))
    except Exception as e:
        print(f"[lead_flags] opt-out lookup failed for client={client_id}: {e}")
        return False


async def is_unqualified(client_id: int, phone: str | None = None, email: str | None = None) -> bool:
    """Whether this client's lead with that phone (last 10 digits) or email
    is tagged Unqualified. Never raises — on a lookup failure it returns
    False so a DB hiccup can't silently swallow a legitimate send."""
    phone = (phone or "").strip()
    email = (email or "").strip()
    if not phone and not email:
        return False
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            return bool(await conn.fetchval(
                rf"""
                SELECT EXISTS (
                    SELECT 1 FROM contacts c
                    WHERE c.client_id = $1 AND NOT c.is_client_anchor AND {UNQUALIFIED_SQL}
                      AND (
                        ($2 != '' AND coalesce(c.phone, '') != ''
                         AND right(regexp_replace(c.phone, '\D', '', 'g'), 10) = right(regexp_replace($2, '\D', '', 'g'), 10))
                        OR ($3 != '' AND lower(coalesce(c.email, '')) = lower($3))
                      )
                )
                """,
                client_id, phone, email,
            ))
    except Exception as e:
        print(f"[lead_flags] unqualified lookup failed for client={client_id}: {e}")
        return False


async def add_tag(contact_id: str | None, tag: str) -> None:
    """Add `tag` to one client lead's contact row unless it's already there
    (case/separator-insensitive, like every tag check here). Client leads
    only, never the anchor contact or Dylan's own contacts. Never raises."""
    if not contact_id:
        return
    norm = "".join(ch for ch in tag.lower() if ch.isalpha())
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                r"""
                UPDATE contacts c SET tags = array_append(coalesce(c.tags, '{}'), $2), updated_at = now()
                WHERE c.id = $1 AND c.client_id IS NOT NULL AND NOT c.is_client_anchor
                  AND NOT EXISTS (
                      SELECT 1 FROM unnest(coalesce(c.tags, '{}')) t
                      WHERE lower(regexp_replace(t, '[^A-Za-z]', '', 'g')) = $3
                  )
                """,
                contact_id, tag, norm,
            )
    except Exception as e:
        print(f"[lead_flags] failed to tag {contact_id} {tag!r}: {e}")


def in_quiet_hours(tz_name: str | None, now: datetime) -> bool:
    try:
        tz = ZoneInfo(tz_name or "America/Chicago")
    except Exception:
        tz = ZoneInfo("America/Chicago")
    hour = now.astimezone(tz).hour
    return hour >= QUIET_START_HOUR or hour < QUIET_END_HOUR
