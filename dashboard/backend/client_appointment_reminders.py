"""Scheduled 24h/day-of appointment reminders for a CLIENT's OWN lead, sent
from the CLIENT's own Twilio number / Gmail mailbox using that client's own
client_sequence_steps sequence_key='appointment_reminder' copy — never
DigiGrowth's shared Twilio/Gmail credentials and never reminder_engine.py's
Dylan-branded copy (that copy is hardcoded to say "your call with
DigiGrowth", wrong on every count for a client's own patient). Companion to
client_appointment_sequence.py's one-shot no-show/cancellation touches, but
this one runs a genuine scheduled poll (main.py's poller, same 5-minute
cadence as reminder_engine.py) since a lead can be booked anywhere from
minutes to weeks ahead of their appointment.

step_order -> hours-before-appointment mapping: client_sequence_steps has no
explicit timing field (label text like "24 Hour Reminder"/"Day-Of Reminder"
is just a human-readable name, not a real schedule), so this is a fixed
convention, not yet admin-configurable: step 0 fires ~24h before, step 1
fires ~2h before ("day of"). A client with only 1 step just gets that one;
a step beyond index 1 is skipped (logged, not guessed at) until this ever
needs a real per-step timing field.
"""

import json
from datetime import datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

from db import get_pool
from merge_fields import first_name_from_owner

_SEQUENCE_KEY = "appointment_reminder"
_WINDOW_HOURS_BY_STEP = [24, 2]


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
            """
            SELECT ar.*, c.client_id AS lead_client_id, cl.name AS client_name
            FROM appointment_reminders ar
            JOIN contacts c ON c.id = ar.contact_id
            JOIN clients cl ON cl.id = c.client_id
            WHERE ar.status = 'scheduled' AND ar.appointment_at > now()
            AND ar.reminders_stopped_at IS NULL
            AND c.client_id IS NOT NULL AND NOT c.is_client_anchor
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

        for step in steps:
            idx = step["step_order"]
            if idx >= len(_WINDOW_HOURS_BY_STEP):
                print(f"[client_appointment_reminders] client {client_id} step {idx} has no defined timing yet — skipping")
                continue
            if str(idx) in sent_map:
                continue
            hours_before = _WINDOW_HOURS_BY_STEP[idx]
            if lead_time < timedelta(hours=hours_before):
                continue  # never had genuine lead time for this window — permanently skipped, same as reminder_engine.py
            if now < row["appointment_at"] - timedelta(hours=hours_before):
                continue  # not due yet

            body = (step["body"] or "").strip()
            if not body:
                continue
            text = _fill(body, row, row["client_name"])
            sent_ok = False

            if step["channel"] == "sms":
                phone = (row.get("prospect_phone") or "").strip()
                if not phone:
                    continue
                if not (config and config["twilio_number"]):
                    print(f"[client_appointment_reminders] client {client_id} has no Twilio number provisioned — skipping SMS")
                    continue
                try:
                    await client_sms.send_client_sms(client_id, phone, text, stage=f"appointment_reminder_{idx}")
                    sent_ok = True
                except Exception as e:
                    print(f"[client_appointment_reminders] SMS failed for client {client_id} ({phone}): {e}")
            elif step["channel"] == "email":
                email = (row.get("prospect_email") or "").strip()
                if not email:
                    continue
                if not (config and config["gmail_refresh_token"]):
                    print(f"[client_appointment_reminders] client {client_id} has no Gmail mailbox connected — skipping email")
                    continue
                try:
                    subject = _fill((step["subject"] or "").strip() or "Appointment Reminder", row, row["client_name"])
                    await client_email.send_client_email(client_id, email, subject, text)
                    sent_ok = True
                except Exception as e:
                    print(f"[client_appointment_reminders] email failed for client {client_id} ({email}): {e}")

            if sent_ok:
                sent_map[str(idx)] = now.isoformat()
                async with pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE appointment_reminders SET reminder_steps_sent = $2 WHERE id = $1",
                        row["id"], json.dumps(sent_map),
                    )
