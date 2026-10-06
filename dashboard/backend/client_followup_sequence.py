"""Client prospect follow-up — a CLIENT's own 4-touch "gone quiet" nudge.

Client-portal port of dm_followup_sequence.py (Dylan's own DM Reach
follow-up), for a client's own leads: sends from the client's own Twilio
number (client_sms.py), reads the client's own SMS log (client_sms_messages),
and uses the client's own copy (client_sequence_steps, sequence_key
'prospect_followup' — an SMS + email pair per touch, step_order 0-1 = Touch 1,
2-3 = Touch 2, 4-5 = Touch 3, 6-7 = Touch 4, same pairing as the no-show/cancellation drips;
editable from the Clients admin panel, previewed on the portal's Sequences
tab). The email goes from the client's connected Gmail mailbox to the lead's
email on file, and is skipped when either is missing.
Never touches sms_conversations/sms_messages or Dylan's own templates.

State lives on the lead's contacts row (client_followup_* columns) since
client leads have no sms_conversations row.

Enrollment (client_followup_enrolled_at):
  - automatically, the moment the client's response AI texts the lead (the
    Meta lead opener or any AI reply) or the client replies manually from
    the portal inbox — see client_sms.send_client_sms's maybe_enroll() call.
    Same idea as Dylan's sequence auto-enrolling on an AI setter reply.
  - manually, from the portal Sequences tab's "View Active Prospects" queue
    (add()), and un-enrolled from the same queue (remove()).
  Neither path enrolls a lead who has booked (see _BOOKED_SQL).

Each poll, the stop/restart behavior is derived from live message
timestamps, exactly like dm_followup_sequence.py:
  1. Booked (any appointment on file, or the AI marked the conversation
     'booked'): hard-clear the enrollment and the whole cycle. Booked leads
     are handed to the reminder/no-show/cancellation sequences instead, and
     can't be re-enrolled.
  2. Ball in the client's court (last inbound text OR email from the lead
     >= last outbound text): clear the
     anchor and touch columns. This is "stops the moment they reply" — the
     response AI (or the client) answers them, and nothing sends until
     another outbound message goes unanswered.
  3. Ball in the prospect's court: if the last outbound is newer than the
     anchor and every touch already sent, it's a genuinely new silence cycle
     (a real message, not one of this sequence's own touches) — re-anchor
     on it and clear the touch columns.
  4. Send whichever touch is next due: Touch 1 3h after the anchor, Touch 2
     24h after Touch 1's actual send, Touch 3 3 days after Touch 2's, Touch 4
     7 days after Touch 3's —
     chained off real sends so a stale anchor can never fire a burst (see
     dm_followup_sequence.py's docstring for the full reasoning). A touch
     that comes due during quiet hours (9pm-8am in the lead's timezone, see
     lead_flags.py) waits for the morning.

Leads tagged Unqualified (lead_flags.py) are dropped from the sequence and
can't be enrolled, same as booked leads. A lead whose last touch goes out
with no reply is tagged "Database Reactivation".

Not ported: Dylan's dialer escalation (flip to 'dialer-lead' 24h after Touch
2) — clients have no dialer queue, only a per-lead Call button — and the
"Not Interested" stop, since the portal has no disposition control; a client
stops a prospect by removing them from the queue instead.

Templates support {first_name}, {business} (the client's name), and {link}
(the client's Calendly booking link, blank if none is connected).
"""

from datetime import datetime, timedelta, timezone as dt_timezone

import lead_flags
from db import get_pool
from merge_fields import first_name_from_owner
from timezone_lookup import guess_timezone

SEQUENCE_KEY = "prospect_followup"

# (touch number, sent-at column, reference column — None means the anchor,
# otherwise the previous touch's own sent-at column — and delay)
_TOUCHES = [
    (1, "client_followup_touch1_sent_at", None, timedelta(hours=3)),
    (2, "client_followup_touch2_sent_at", "client_followup_touch1_sent_at", timedelta(hours=24)),
    (3, "client_followup_touch3_sent_at", "client_followup_touch2_sent_at", timedelta(days=3)),
    (4, "client_followup_touch4_sent_at", "client_followup_touch3_sent_at", timedelta(days=7)),
]

_CLEAR_CYCLE = (
    "client_followup_anchor_at = NULL, client_followup_touch1_sent_at = NULL, "
    "client_followup_touch2_sent_at = NULL, client_followup_touch3_sent_at = NULL, "
    "client_followup_touch4_sent_at = NULL"
)

# A lead counts as booked if their status is 'appointment-booked' (what
# routers/appointments.py stamps on a booking) or 'client' (already
# converted), they carry a tag like "Appointment Booked"/"Booked" (any case
# or separator — clients make their own tags in the portal), any appointment
# is on file for them (matched by contact, phone, or email — a Calendly
# booking may carry only some of these, same matching as
# response_ai._upcoming_booking), or the response AI marked their
# conversation booked. `c` must be the contacts alias.
_BOOKED_SQL = r"""(
    c.status IN ('appointment-booked', 'client')
    OR EXISTS (
        SELECT 1 FROM unnest(coalesce(c.tags, '{}')) t
        WHERE lower(regexp_replace(t, '[^A-Za-z]', '', 'g')) IN ('appointmentbooked', 'booked')
    )
    OR EXISTS (
        SELECT 1 FROM appointment_reminders a
        WHERE a.contact_id = c.id
           OR (coalesce(c.phone, '') != '' AND right(regexp_replace(coalesce(a.prospect_phone, ''), '\D', '', 'g'), 10)
               = right(regexp_replace(c.phone, '\D', '', 'g'), 10))
           OR (coalesce(c.email, '') != '' AND lower(a.prospect_email) = lower(c.email))
    )
    OR EXISTS (
        SELECT 1 FROM client_lead_conversations clc
        WHERE clc.client_id = c.client_id AND clc.status = 'booked'
          AND right(regexp_replace(clc.phone, '\D', '', 'g'), 10) = right(regexp_replace(coalesce(c.phone, ''), '\D', '', 'g'), 10)
    )
)"""

# Inbound emails from contact `c` to its client's connected mailbox
# (client_email.py stores the sender in to_email for inbound rows).
_EMAIL_INBOUND_SQL = """
    FROM client_email_messages em
    WHERE em.client_id = c.client_id AND em.direction = 'inbound'
      AND coalesce(c.email, '') != '' AND lower(em.to_email) = lower(c.email)
"""

# client_sms_messages rows for contact `c`'s phone on its own client's number.
_THREAD_SQL = r"""
    FROM client_sms_messages m
    WHERE m.client_id = c.client_id AND m.direction = '{direction}'
      AND right(regexp_replace(CASE WHEN m.direction = 'outbound' THEN m.to_number ELSE m.from_number END, '\D', '', 'g'), 10)
          = right(regexp_replace(c.phone, '\D', '', 'g'), 10)
"""


def _fill(template: str, row: dict) -> str:
    text = (
        (template or "")
        .replace("{first_name}", first_name_from_owner(row.get("owner")))
        .replace("{business}", row.get("client_name") or "")
        .replace("{link}", row.get("booking_link") or "")
    )
    # No calendar connected: don't leave "...whenever you're free: " dangling.
    return text.rstrip(" :")


async def maybe_enroll(client_id: int, phone: str) -> None:
    """Called from client_sms.send_client_sms after a conversational send (a
    response AI text or a manual portal reply). Enrolls the matching lead if
    they aren't already enrolled and haven't booked. Never raises — a
    failure here must never fail the send it's attached to."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                rf"""
                UPDATE contacts c SET client_followup_enrolled_at = now()
                WHERE c.client_id = $1 AND NOT c.is_client_anchor
                  AND c.client_followup_enrolled_at IS NULL
                  AND coalesce(c.phone, '') != ''
                  AND right(regexp_replace(c.phone, '\D', '', 'g'), 10) = right(regexp_replace($2, '\D', '', 'g'), 10)
                  AND NOT {_BOOKED_SQL} AND NOT {lead_flags.UNQUALIFIED_SQL}
                """,
                client_id, phone,
            )
    except Exception as e:
        print(f"[client_followup_sequence] enroll failed for client={client_id} phone={phone}: {e}")


async def _send_touch(row: dict, touch_num: int, sms_step: dict | None, email_step: dict | None) -> None:
    """One touch = the SMS step and the email step for it, each best-effort
    and independent (a missing email address or unconnected mailbox only
    skips the email)."""
    import client_email
    import client_sms

    text = _fill((sms_step or {}).get("body"), row)
    if text.strip():
        try:
            await client_sms.send_client_sms(row["client_id"], row["phone"], text, stage=f"{SEQUENCE_KEY}_touch{touch_num}")
        except Exception as e:
            print(f"[client_followup_sequence] SMS failed for client={row['client_id']} phone={row['phone']}: {e}")

    email = (row.get("email") or "").strip()
    subject = _fill((email_step or {}).get("subject"), row)
    body = _fill((email_step or {}).get("body"), row)
    if email and subject.strip() and body.strip() and row.get("gmail_refresh_token"):
        try:
            await client_email.send_client_email(row["client_id"], email, subject, body)
        except Exception as e:
            print(f"[client_followup_sequence] email failed for client={row['client_id']} ({email}): {e}")


async def send_due_touches():
    """Poll enrolled client leads and, per lead, either clear (booked / they
    replied), start a new silence cycle, or send whichever touch is next due
    — at most one touch per lead per poll. See module docstring."""
    pool = await get_pool()
    now = datetime.now(dt_timezone.utc)
    async with pool.acquire() as conn:
        # Booked and Unqualified leads leave the sequence for good.
        await conn.execute(
            f"UPDATE contacts c SET client_followup_enrolled_at = NULL, {_CLEAR_CYCLE} "
            f"WHERE c.client_followup_enrolled_at IS NOT NULL AND ({_BOOKED_SQL} OR {lead_flags.UNQUALIFIED_SQL})"
        )
        rows = await conn.fetch(
            f"""
            SELECT c.*, cl.name AS client_name, cmc.gmail_refresh_token,
                   coalesce(nullif(cmc.calendly_event_type_url, ''), cl.calendly_url) AS booking_link,
                   (SELECT MAX(m.created_at) {_THREAD_SQL.format(direction='outbound')}) AS last_outbound_at,
                   GREATEST(
                       (SELECT MAX(m.created_at) {_THREAD_SQL.format(direction='inbound')}),
                       (SELECT MAX(em.created_at) {_EMAIL_INBOUND_SQL})
                   ) AS last_inbound_at
            FROM contacts c
            JOIN clients cl ON cl.id = c.client_id
            JOIN client_marketing_config cmc ON cmc.client_id = c.client_id
            WHERE c.client_followup_enrolled_at IS NOT NULL
              AND c.client_id IS NOT NULL AND NOT c.is_client_anchor
              AND coalesce(c.phone, '') != ''
              AND coalesce(cmc.twilio_number, '') != ''
            """
        )
        if not rows:
            return

        step_rows = await conn.fetch(
            "SELECT client_id, step_order, channel, subject, body FROM client_sequence_steps "
            "WHERE sequence_key = $1 AND client_id = ANY($2)",
            SEQUENCE_KEY, list({r["client_id"] for r in rows}),
        )
        steps = {(s["client_id"], s["step_order"], s["channel"]): dict(s) for s in step_rows}

        for record in rows:
            row = dict(record)
            last_outbound_at = row["last_outbound_at"]
            last_inbound_at = row["last_inbound_at"]
            if last_outbound_at is None:
                continue

            if last_inbound_at is not None and last_inbound_at >= last_outbound_at:
                # Ball in the client's court — they just replied.
                if row["client_followup_anchor_at"] is not None:
                    await conn.execute(f"UPDATE contacts SET {_CLEAR_CYCLE} WHERE id = $1", row["id"])
                continue

            known_times = [t for t in (
                row["client_followup_anchor_at"], row["client_followup_touch1_sent_at"],
                row["client_followup_touch2_sent_at"], row["client_followup_touch3_sent_at"],
                row["client_followup_touch4_sent_at"],
            ) if t is not None]
            if not known_times or last_outbound_at > max(known_times):
                await conn.execute(
                    "UPDATE contacts SET client_followup_anchor_at = $1, client_followup_touch1_sent_at = NULL, "
                    "client_followup_touch2_sent_at = NULL, client_followup_touch3_sent_at = NULL, "
                    "client_followup_touch4_sent_at = NULL WHERE id = $2",
                    last_outbound_at, row["id"],
                )
                row["client_followup_anchor_at"] = last_outbound_at
                row["client_followup_touch1_sent_at"] = None
                row["client_followup_touch2_sent_at"] = None
                row["client_followup_touch3_sent_at"] = None
                row["client_followup_touch4_sent_at"] = None

            anchor = row["client_followup_anchor_at"]
            for touch_num, sent_col, ref_col, delay in _TOUCHES:
                if row[sent_col] is not None:
                    continue
                reference = anchor if ref_col is None else row[ref_col]
                if reference is not None and now >= reference + delay:
                    if lead_flags.in_quiet_hours(guess_timezone(row["phone"]), now):
                        break  # due, but it's night where they are — send at 8am
                    pair = ((touch_num - 1) * 2, (touch_num - 1) * 2 + 1)
                    sms_step = steps.get((row["client_id"], pair[0], "sms"))
                    email_step = steps.get((row["client_id"], pair[1], "email"))
                    if sms_step or email_step:
                        await _send_touch(row, touch_num, sms_step, email_step)
                    # Stamped even when the client has no copy for this
                    # touch, so a blanked-out touch is skipped rather than
                    # stalling the rest of the sequence.
                    await conn.execute(f"UPDATE contacts SET {sent_col} = now() WHERE id = $1", row["id"])
                    if touch_num == len(_TOUCHES):
                        await lead_flags.add_tag(row["id"], lead_flags.REACTIVATION_TAG)
                break


def _progress(row: dict) -> dict:
    total = len(_TOUCHES)
    sent = sum(1 for _, col, _, _ in _TOUCHES if row.get(col) is not None)
    next_due = None
    if row.get("client_followup_anchor_at") and sent < total:
        _, _, ref_col, delay = _TOUCHES[sent]
        reference = row["client_followup_anchor_at"] if ref_col is None else row.get(ref_col)
        next_due = reference + delay if reference else None
    if row.get("client_followup_anchor_at") is None:
        # Either they replied last, or they were just enrolled and the next
        # poll hasn't anchored the cycle yet — same state either way.
        label = "Waiting for an unanswered text"
    elif sent == total:
        label = f"All {total} touches sent"
    elif sent:
        label = f"Touch {sent} of {total} sent"
    else:
        label = "Touch 1 pending"
    return {"touches_sent": sent, "touches_total": total, "step_label": label, "next_touch_due_at": next_due}


async def list_active(client_id: int) -> list[dict]:
    """Everyone enrolled for this client — backs the portal Sequences tab's
    'View Active Prospects' queue."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, owner, business, phone, client_followup_enrolled_at, client_followup_anchor_at,
                   client_followup_touch1_sent_at, client_followup_touch2_sent_at, client_followup_touch3_sent_at,
                   client_followup_touch4_sent_at
            FROM contacts
            WHERE client_id = $1 AND NOT is_client_anchor AND client_followup_enrolled_at IS NOT NULL
            ORDER BY client_followup_enrolled_at ASC
            """,
            client_id,
        )
    return [
        {
            "id": r["id"], "prospect_name": r["owner"] or r["business"] or r["phone"], "phone": r["phone"],
            **_progress(dict(r)),
        }
        for r in rows
    ]


async def add(client_id: int, contact_id: str) -> str | None:
    """Manually enroll one of this client's leads. Returns None on success,
    or an error message. The cycle starts from their thread's last outbound
    message on the next poll, same as an automatic enrollment."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"SELECT c.id, c.phone, {_BOOKED_SQL} AS booked, {lead_flags.UNQUALIFIED_SQL} AS unqualified FROM contacts c "
            "WHERE c.id = $1 AND c.client_id = $2 AND NOT c.is_client_anchor",
            contact_id, client_id,
        )
        if not row:
            return "Lead not found"
        if not (row["phone"] or "").strip():
            return "This lead has no phone number on file"
        if row["booked"]:
            return "This lead has already booked, so they get appointment reminders instead"
        if row["unqualified"]:
            return "This lead is tagged Unqualified, so they get no automated messages. Remove the tag first"
        await conn.execute(
            f"UPDATE contacts SET client_followup_enrolled_at = now(), {_CLEAR_CYCLE} WHERE id = $1",
            contact_id,
        )
    return None


async def remove(client_id: int, contact_id: str) -> bool:
    """Take one lead out of the sequence. They're re-enrolled automatically
    the next time the AI or the client texts them, same as a fresh lead."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"UPDATE contacts SET client_followup_enrolled_at = NULL, {_CLEAR_CYCLE} "
            "WHERE id = $1 AND client_id = $2 AND NOT is_client_anchor AND client_followup_enrolled_at IS NOT NULL "
            "RETURNING id",
            contact_id, client_id,
        )
    return row is not None
