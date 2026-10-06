"""Scheduled appointment reminders (24h / 6h / 1h before) for a CLIENT's OWN
lead, sent from the CLIENT's own Twilio number / Gmail mailbox using that
client's own client_sequence_steps sequence_key='appointment_reminder' copy —
never DigiGrowth's shared Twilio/Gmail credentials and never
reminder_engine.py's Dylan-branded copy (that copy is hardcoded to say "your
call with DigiGrowth", wrong on every count for a client's own patient).
Companion to client_appointment_sequence.py's no-show/cancellation drips,
but this one runs a genuine scheduled poll (main.py's poller, same 5-minute
cadence as reminder_engine.py) since a lead can be booked anywhere from
minutes to weeks ahead of their appointment.

Steps are SMS + email pairs, one pair per reminder window, same pairing as
the no-show/cancellation drips: step_order 0-1 = 24h before, 2-3 = 6h before,
4-5 = 1h before (_WINDOW_HOURS_BY_TOUCH). client_sequence_steps has no
timing field, so this is a fixed convention; a step beyond the last window is
skipped (logged, not guessed at).

Per appointment, only the LATEST window that's currently due is sent; any
earlier unsent window is marked skipped, so a reminder held back (by quiet
hours, or by a booking made inside a window) never goes out back-to-back
with the next one. Windows the booking never had real lead time for are
permanently skipped, same as reminder_engine.py. The 24h and 6h windows wait
out quiet hours (9pm-8am in the lead's timezone, lead_flags.py); the 1h
window always sends, since it's tied to an appointment the lead booked.
Leads tagged Unqualified get no reminders.
"""

import json
from datetime import datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

import lead_flags
from db import get_pool
from merge_fields import first_name_from_owner
from timezone_lookup import guess_timezone

_SEQUENCE_KEY = "appointment_reminder"
_WINDOW_HOURS_BY_TOUCH = [24, 6, 1]
_SKIPPED = "skipped"  # sent-map value for a window deliberately not sent


def _format_date_time(appointment_at: datetime, tz_name: str | None) -> tuple[str, str]:
    try:
        tz = ZoneInfo(tz_name or "America/New_York")
    except Exception:
        tz = ZoneInfo("America/New_York")
    local = appointment_at.astimezone(tz)
    return local.strftime("%A, %B %-d"), local.strftime("%-I:%M %p %Z")


def _fill(template: str, row: dict, client_name: str) -> str:
    date_str, time_str = _format_date_time(row["appointment_at"], row.get("prospect_timezone"))
    return (
        (template or "")
        .replace("{first_name}", first_name_from_owner(row.get("prospect_name")))
        .replace("{business}", client_name)
        .replace("{date}", date_str)
        .replace("{time}", time_str)
    )


async def send_due_reminders():
    """Registered on the 5-minute poller alongside reminder_engine.py's own
    job. Only ever touches appointments belonging to a real client's own
    lead (client_id set AND NOT is_client_anchor) — the inverse of every
    exclusion elsewhere in this codebase (reminder_engine.py, no_show_
    sequence.py, cancel_sequence.py, call_reminders.py all exclude these
    same rows from Dylan's own pipeline)."""
    import client_email
    import client_sms

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT ar.*, c.client_id AS lead_client_id, cl.name AS client_name,
                   c.phone AS contact_phone, c.email AS contact_email
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
                "WHERE client_id = $1 AND sequence_key = $2 ORDER BY step_order",
                client_id, _SEQUENCE_KEY,
            )
            config = await conn.fetchrow(
                "SELECT twilio_number, gmail_refresh_token FROM client_marketing_config WHERE client_id = $1",
                client_id,
            )

        by_touch: dict[int, list] = {}
        for step in steps:
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

        tz_name = row.get("prospect_timezone") or guess_timezone(row.get("prospect_phone") or row.get("contact_phone"))
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
                    # Nothing to send on this channel (no copy, no phone/email,
                    # nothing connected) — record it so it isn't retried forever.
                    sent_map[str(idx)] = _SKIPPED
                changed = True

        if changed:
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE appointment_reminders SET reminder_steps_sent = $2 WHERE id = $1",
                    row["id"], json.dumps(sent_map),
                )


async def _send_step(client_id: int, config, step, row: dict, text: str) -> bool:
    """Send one reminder step on its channel. Returns True only on a real send."""
    import client_email
    import client_sms

    # A Calendly booking's own phone/email can be blank (its form may not ask
    # for a phone) even when the linked lead has one on file from their Meta
    # form — fall back to the contact's.
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
    if step["channel"] == "email":
        email = (row.get("prospect_email") or row.get("contact_email") or "").strip()
        if not email:
            return False
        if not (config and config["gmail_refresh_token"]):
            print(f"[client_appointment_reminders] client {client_id} has no Gmail mailbox connected — skipping email")
            return False
        try:
            subject = _fill((step["subject"] or "").strip() or "Appointment Reminder", row, row["client_name"])
            await client_email.send_client_email(client_id, email, subject, text)
            return True
        except Exception as e:
            print(f"[client_appointment_reminders] email failed for client {client_id} ({email}): {e}")
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
            "SELECT COUNT(DISTINCT step_order / 2) FROM client_sequence_steps WHERE client_id = $1 AND sequence_key = $2",
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
