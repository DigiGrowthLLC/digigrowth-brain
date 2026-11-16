"""Scheduled appointment reminders (24h / 6h / 1h before) for a CLIENT's OWN
lead, sent from the CLIENT's own Twilio number using that client's own
client_sequence_steps sequence_key='appointment_reminder' copy — never
DigiGrowth's shared Twilio credentials and never
reminder_engine.py's Dylan-branded copy (that copy is hardcoded to say "your
call with DigiGrowth", wrong on every count for a client's own patient).
Companion to client_appointment_sequence.py's no-show/cancellation drips,
but this one runs a genuine scheduled poll (main.py's poller, same 5-minute
cadence as reminder_engine.py) since a lead can be booked anywhere from
minutes to weeks ahead of their appointment.

Steps keep the SMS + email pair numbering the no-show/cancellation drips use
(step_order 0-1 = 24h before, 2-3 = 6h before, 4-5 = 1h before,
_WINDOW_HOURS_BY_TOUCH), but only the SMS step ever sends: DigiGrowth stopped
offering client email (2026-10-28), so an email step is always skipped.
client_sequence_steps has no timing field, so this is a fixed convention; a step beyond the last window is
skipped (logged, not guessed at).

Per appointment, only the LATEST window that's currently due is sent; any
earlier unsent window is marked skipped, so a reminder held back (by quiet
hours, or by a booking made inside a window) never goes out back-to-back
with the next one. Windows the booking never had real lead time for are
permanently skipped, same as reminder_engine.py. The 24h and 6h windows wait
out quiet hours (9pm-8am in the clinic's timezone, lead_flags.py); the 1h
window always sends, since it's tied to an appointment the lead booked.
Leads tagged Unqualified get no reminders.

Booking Confirmation (step_order -2, "Right away"): one text the moment a NEW
appointment lands, from any source (DigiGrowth Booking, Calendly, GHL, the
CRM). DigiGrowth Booking sends it instantly from booking_engine._finalize via
send_confirmation() (with the location + reschedule link added); everything
else gets it on the next 5-minute poll. Only for appointment rows created in
the last _CONFIRM_FRESH (so a reschedule, a re-arm or an appointment that
predates this step never gets a "you're booked" text). Claimed atomically in
reminder_steps_sent["-2"] so it can't go out twice. Always sends, quiet hours
or not, since the patient just booked.
"""

import json
import re
from datetime import datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

import lead_flags
from db import get_pool
from merge_fields import first_name_from_owner
from timezone_lookup import clinic_timezone

_SEQUENCE_KEY = "appointment_reminder"
_WINDOW_HOURS_BY_TOUCH = [24, 6, 1]
_SKIPPED = "skipped"  # sent-map value for a window deliberately not sent
_CONFIRM_KEY = "-2"  # step_order of the Booking Confirmation text
_CONFIRM_FRESH = timedelta(minutes=30)


def _pretty_phone(phone: str) -> str:
    d = re.sub(r"\D", "", phone or "")
    if len(d) == 11 and d.startswith("1"):
        d = d[1:]
    return f"({d[:3]}) {d[3:6]}-{d[6:]}" if len(d) == 10 else (phone or "").strip()


async def contact_line(conn, client_id: int) -> str:
    """'Questions? Call (555) 123-4567 or email frontdesk@clinic.com.' from the
    Booking setup's patient contact fields, falling back to the client record.
    Empty when neither has anything."""
    c = await conn.fetchrow(
        """SELECT cl.email, cl.phone, bs.contact_email, bs.contact_phone FROM clients cl
           LEFT JOIN booking_settings bs ON bs.client_id = cl.id WHERE cl.id = $1""", client_id)
    if not c:
        return ""
    phone = (c["contact_phone"] or c["phone"] or "").strip()
    email = (c["contact_email"] or c["email"] or "").strip()
    if phone and email:
        return f"Questions? Call {_pretty_phone(phone)} or email {email}."
    if phone:
        return f"Questions? Call {_pretty_phone(phone)}."
    if email:
        return f"Questions? Email {email}."
    return ""


def _format_date_time(appointment_at: datetime, tz_name: str | None) -> tuple[str, str]:
    try:
        tz = ZoneInfo(tz_name or "America/New_York")
    except Exception:
        tz = ZoneInfo("America/New_York")
    local = appointment_at.astimezone(tz)
    return local.strftime("%A, %B %-d"), local.strftime("%-I:%M %p %Z")


def _fill(template: str, row: dict, client_name: str, contact: str = "") -> str:
    date_str, time_str = _format_date_time(row["appointment_at"], row.get("prospect_timezone"))
    text = (
        (template or "")
        .replace("{first_name}", first_name_from_owner(row.get("prospect_name")))
        .replace("{business}", client_name)
        .replace("{date}", date_str)
        .replace("{time}", time_str)
        .replace("{contact}", contact)
    )
    return re.sub(r"[ \t]{2,}", " ", text).strip()


async def _claim_confirmation(conn, ar_id: int, value: str) -> bool:
    """Stamp reminder_steps_sent["-2"] only if nothing has yet. True = we own it."""
    return bool(await conn.fetchval(
        """UPDATE appointment_reminders
           SET reminder_steps_sent = COALESCE(reminder_steps_sent, '{}'::jsonb) || jsonb_build_object($2::text, $3::text)
           WHERE id = $1 AND NOT (COALESCE(reminder_steps_sent, '{}'::jsonb) ? $2::text)
           RETURNING id""", ar_id, _CONFIRM_KEY, value))


async def _send_confirmation_row(row: dict, step, config, extra: str = "") -> bool:
    """Claim + send the Booking Confirmation for one appointment row."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if not await _claim_confirmation(conn, row["id"], datetime.now(dt_timezone.utc).isoformat()):
            return False
        contact = await contact_line(conn, row["lead_client_id"])
    text = _fill(step["body"], row, row["client_name"], contact)
    if extra:
        text = f"{text} {extra}".strip()
    ok = bool((step["body"] or "").strip()) and await _send_step(row["lead_client_id"], config, step, row, text)
    if not ok:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE appointment_reminders SET reminder_steps_sent = reminder_steps_sent || jsonb_build_object($2::text, $3::text) WHERE id = $1",
                row["id"], _CONFIRM_KEY, _SKIPPED)
    return ok


async def send_confirmation(appointment_id: int, extra: str = "") -> bool | None:
    """Send the Booking Confirmation for a just-created appointment now.
    None = this client has no enabled confirmation step (caller may send its
    own text); False = not sent (already sent, no phone/number, unqualified);
    True = sent. `extra` is appended (DigiGrowth Booking's location +
    reschedule link)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""SELECT ar.*, c.client_id AS lead_client_id, cl.name AS client_name, c.phone AS contact_phone,
                       {lead_flags.UNQUALIFIED_SQL} AS unqualified
                FROM appointment_reminders ar
                JOIN contacts c ON c.id = ar.contact_id
                JOIN clients cl ON cl.id = c.client_id
                WHERE ar.id = $1 AND c.client_id IS NOT NULL AND NOT c.is_client_anchor""", appointment_id)
        if not row:
            return None
        row = dict(row)
        step = await conn.fetchrow(
            "SELECT step_order, channel, subject, body FROM client_sequence_steps "
            "WHERE client_id = $1 AND sequence_key = $2 AND step_order < 0 AND enabled AND channel = 'sms' "
            "ORDER BY step_order LIMIT 1", row["lead_client_id"], _SEQUENCE_KEY)
        if not step:
            return None
        if row["unqualified"] or row["status"] != "scheduled" or row["appointment_at"] <= datetime.now(dt_timezone.utc):
            return False
        config = await conn.fetchrow(
            "SELECT twilio_number FROM client_marketing_config WHERE client_id = $1", row["lead_client_id"])
        row["prospect_timezone"] = await clinic_timezone(
            conn, row["lead_client_id"], row.get("prospect_phone") or row.get("contact_phone"))
    return await _send_confirmation_row(row, step, config, extra)


async def send_due_reminders():
    """Registered on the 5-minute poller alongside reminder_engine.py's own
    job. Only ever touches appointments belonging to a real client's own
    lead (client_id set AND NOT is_client_anchor) — the inverse of every
    exclusion elsewhere in this codebase (reminder_engine.py, no_show_
    sequence.py, cancel_sequence.py, call_reminders.py all exclude these
    same rows from Dylan's own pipeline)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT ar.*, c.client_id AS lead_client_id, cl.name AS client_name,
                   c.phone AS contact_phone
            FROM appointment_reminders ar
            JOIN contacts c ON c.id = ar.contact_id
            JOIN clients cl ON cl.id = c.client_id
            WHERE ar.status = 'scheduled' AND ar.appointment_at > now()
            AND ar.reminders_stopped_at IS NULL
            AND c.client_id IS NOT NULL AND NOT c.is_client_anchor
            AND NOT {lead_flags.UNQUALIFIED_SQL}
            """
        )
    if not rows:
        return

    now = datetime.now(dt_timezone.utc)
    for record in rows:
        row = dict(record)
        client_id = row["lead_client_id"]
        lead_time = row["appointment_at"] - row["reminders_armed_at"]
        # asyncpg has no JSONB codec registered on this pool (same note as
        # client_marketing.py's _decode_config) — comes back as a raw string.
        raw_sent = row.get("reminder_steps_sent")
        sent_map = json.loads(raw_sent) if isinstance(raw_sent, str) else dict(raw_sent or {})

        async with pool.acquire() as conn:
            steps = await conn.fetch(
                "SELECT step_order, channel, subject, body FROM client_sequence_steps "
                "WHERE client_id = $1 AND sequence_key = $2 AND enabled ORDER BY step_order",
                client_id, _SEQUENCE_KEY,
            )
            config = await conn.fetchrow(
                "SELECT twilio_number FROM client_marketing_config WHERE client_id = $1",
                client_id,
            )
            # The clinic's clock, never the patient's (Dylan, 2026-10-31):
            # both the {time} in the text and the quiet-hours check.
            row["prospect_timezone"] = await clinic_timezone(
                conn, client_id, row.get("prospect_phone") or row.get("contact_phone"),
            )

        # Booking Confirmation: only for a genuinely new appointment row.
        confirm = next((st for st in steps if st["step_order"] < 0 and st["channel"] == "sms"), None)
        if (confirm and _CONFIRM_KEY not in sent_map and row.get("created_at")
                and now - row["created_at"] <= _CONFIRM_FRESH):
            if await _send_confirmation_row(row, confirm, config):
                sent_map[_CONFIRM_KEY] = now.isoformat()
            else:
                sent_map[_CONFIRM_KEY] = _SKIPPED

        by_touch: dict[int, list] = {}
        for step in steps:
            if step["step_order"] < 0:
                continue
            touch = step["step_order"] // 2
            if touch >= len(_WINDOW_HOURS_BY_TOUCH):
                print(f"[client_appointment_reminders] client {client_id} step {step['step_order']} has no defined timing — skipping")
                continue
            by_touch.setdefault(touch, []).append(step)

        # Unsent windows that are due now (and had genuine lead time).
        due = [
            t for t in sorted(by_touch)
            if not all(str(st["step_order"]) in sent_map for st in by_touch[t])
            and lead_time >= timedelta(hours=_WINDOW_HOURS_BY_TOUCH[t])
            and now >= row["appointment_at"] - timedelta(hours=_WINDOW_HOURS_BY_TOUCH[t])
        ]
        if not due:
            continue
        latest = due[-1]
        changed = False
        for t in due[:-1]:  # superseded by a later window that's also due
            for st in by_touch[t]:
                sent_map.setdefault(str(st["step_order"]), _SKIPPED)
            changed = True

        tz_name = row["prospect_timezone"]
        is_last_window = latest == len(_WINDOW_HOURS_BY_TOUCH) - 1
        if not is_last_window and lead_flags.in_quiet_hours(tz_name, now):
            pass  # wait for 8am (or for the next window to supersede this one)
        else:
            for step in by_touch[latest]:
                idx = step["step_order"]
                if str(idx) in sent_map:
                    continue
                body = (step["body"] or "").strip()
                if body and await _send_step(client_id, config, step, row, _fill(body, row, row["client_name"])):
                    sent_map[str(idx)] = now.isoformat()
                else:
                    # Nothing to send on this channel (email step, no copy, no
                    # phone, no number provisioned) — record it so it isn't retried forever.
                    sent_map[str(idx)] = _SKIPPED
                changed = True

        if changed:
            async with pool.acquire() as conn:
                # Merge, never overwrite: send_confirmation() may have
                # stamped "-2" since this row was read.
                await conn.execute(
                    "UPDATE appointment_reminders SET reminder_steps_sent = reminder_steps_sent || $2::jsonb WHERE id = $1",
                    row["id"], json.dumps(sent_map),
                )


async def _send_step(client_id: int, config, step, row: dict, text: str) -> bool:
    """Send one reminder step. Only SMS steps send. Returns True only on a real send."""
    import client_sms

    # A Calendly booking's own phone can be blank (its form may not ask for
    # one) even when the linked lead has one on file from their Meta form —
    # fall back to the contact's.
    if step["channel"] == "sms":
        phone = (row.get("prospect_phone") or row.get("contact_phone") or "").strip()
        if not phone:
            return False
        if not (config and config["twilio_number"]):
            print(f"[client_appointment_reminders] client {client_id} has no Twilio number provisioned — skipping SMS")
            return False
        try:
            await client_sms.send_client_sms(client_id, phone, text, stage=f"appointment_reminder_{step['step_order']}")
            return True
        except Exception as e:
            print(f"[client_appointment_reminders] SMS failed for client {client_id} ({phone}): {e}")
            return False
    return False


def _progress(row: dict, touch_count: int) -> dict:
    raw_sent = row.get("reminder_steps_sent")
    sent_map = json.loads(raw_sent) if isinstance(raw_sent, str) else dict(raw_sent or {})
    appt_at = row["appointment_at"]
    lead_time = appt_at - row["reminders_armed_at"]
    touches = range(min(touch_count, len(_WINDOW_HOURS_BY_TOUCH)))
    sent = sum(1 for t in touches if any(
        sent_map.get(str(so)) not in (None, _SKIPPED) for so in (t * 2, t * 2 + 1)))
    next_due = None
    for t in touches:
        if str(t * 2) in sent_map or str(t * 2 + 1) in sent_map:
            continue
        hours_before = _WINDOW_HOURS_BY_TOUCH[t]
        if lead_time < timedelta(hours=hours_before):
            continue
        next_due = appt_at - timedelta(hours=hours_before)
        break
    return {
        "touches_sent": sent,
        "touches_total": touch_count,
        "step_label": f"{sent} of {touch_count} sent" if sent else "None sent yet",
        "next_touch_due_at": next_due,
    }


async def list_active(client_id: int) -> list[dict]:
    """Upcoming scheduled appointments for this client with reminders still
    active — backs the client portal Messaging tab's 'View Active Prospects'
    queue for Appointment Reminders."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT ar.*, c.business, c.owner FROM appointment_reminders ar
            JOIN contacts c ON c.id = ar.contact_id
            WHERE c.client_id = $1 AND NOT c.is_client_anchor
            AND ar.status = 'scheduled' AND ar.appointment_at > now() AND ar.reminders_stopped_at IS NULL
            AND NOT {lead_flags.UNQUALIFIED_SQL}
            ORDER BY ar.appointment_at ASC
            """,
            client_id,
        )
        touch_count = await conn.fetchval(
            "SELECT COUNT(DISTINCT step_order / 2) FROM client_sequence_steps WHERE client_id = $1 AND sequence_key = $2 AND step_order >= 0",
            client_id, _SEQUENCE_KEY,
        )
    touch_count = min(touch_count or len(_WINDOW_HOURS_BY_TOUCH), len(_WINDOW_HOURS_BY_TOUCH))
    return [{**dict(r), **_progress(dict(r), touch_count)} for r in rows]


async def remove(client_id: int, appointment_id: int) -> bool:
    """Stop future reminder windows for one of this client's appointments
    without canceling the appointment itself. Returns False if the
    appointment doesn't belong to this client or reminders are already
    stopped."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE appointment_reminders ar SET reminders_stopped_at = now()
            FROM contacts c
            WHERE ar.id = $1 AND c.id = ar.contact_id AND c.client_id = $2 AND NOT c.is_client_anchor
            AND ar.reminders_stopped_at IS NULL
            RETURNING ar.id
            """,
            appointment_id, client_id,
        )
    return row is not None


async def add(client_id: int, appointment_id: int) -> bool:
    """Re-arm reminders for one of this client's existing appointment rows —
    resets the window progress as if just booked. Returns False if the
    appointment doesn't belong to this client or is already in the past."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE appointment_reminders ar SET status = 'scheduled', reminders_armed_at = now(),
                reminder_steps_sent = '{}', reminders_stopped_at = NULL
            FROM contacts c
            WHERE ar.id = $1 AND c.id = ar.contact_id AND c.client_id = $2 AND NOT c.is_client_anchor
            AND ar.appointment_at > now()
            RETURNING ar.id
            """,
            appointment_id, client_id,
        )
    return row is not None
