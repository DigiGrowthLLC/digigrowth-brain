"""Client "you just got a booking" notification — one-shot SMS to the
CLIENT (business owner, e.g. "Brandon" at a PT practice) the moment a NEW
appointment is booked for one of their leads, via internal CRM or the
client portal's self-booking (both funnel through
routers/appointments.py's create_appointment(), the single insert point
for appointment_reminders — see that module's docstring).

Unrelated to reminder_engine.py's 24h/6h/1h reminder sequence, which texts
the LEAD/prospect before their appointment — this fires once, to the
CLIENT, the moment the booking happens. Do not confuse the two.

Fires synchronously (awaited, try/except-wrapped, never raises) from the
bottom of create_appointment() — same one-shot-at-mutation shape as
reminder_engine.send_reschedule_confirmation(). No scheduler/poller.

Editable from Business Resources -> Outreach Templates -> "Client Booking
Alert" (dialer_settings-backed, same pattern as every other automated
message here — see routers/dialer.py's GET/PUT /dialer/client-booking-template).
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from db import get_pool
from merge_fields import first_name_from_owner

_DEFAULT_SMS = (
    "Hey {client_first_name}, we just booked you an appointment with "
    "{lead_name} for {when}."
)

TEMPLATE_DEFAULTS = {
    "client_booking_notification_sms": _DEFAULT_SMS,
}


async def _get_templates() -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT key, value FROM dialer_settings WHERE key = ANY($1)",
            list(TEMPLATE_DEFAULTS.keys()),
        )
    values = {r["key"]: r["value"] for r in rows if r["value"]}
    return {key: values.get(key, default) for key, default in TEMPLATE_DEFAULTS.items()}


def _format_when(appointment_at: datetime, tz_name: str) -> str:
    """"2:00 PM on Thursday, September 4th" — a heads-up to the client in
    their own head, not a countdown they need to double check the timezone
    on, so no timezone abbreviation (unlike reminder_engine's lead-facing
    reminder copy)."""
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("America/New_York")
    local = appointment_at.astimezone(tz)
    day = local.day
    suffix = "th" if 11 <= day % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return local.strftime(f"%-I:%M %p on %A, %B {day}{suffix}")


def _fill(template: str, client_first_name: str, lead_name: str, when: str) -> str:
    return (
        template
        .replace("{client_first_name}", client_first_name)
        .replace("{lead_name}", lead_name)
        .replace("{when}", when)
    )


async def _resolve_client(conn, contact_id) -> dict | None:
    """contact_id -> contacts.client_id -> clients row, preferring
    clients.phone and falling back to the anchor contact's own phone if
    clients.phone is empty. Returns None (never raises) if no client can
    be resolved at all — callers treat that as a silent no-op, same
    pattern as onboarding_sequence._portal_link_for_appointment()."""
    if not contact_id:
        return None
    row = await conn.fetchrow(
        """
        SELECT cl.id, cl.contact_name, cl.phone AS client_phone,
               cl.booking_notification_enabled,
               anchor.phone AS anchor_phone
        FROM contacts c
        JOIN clients cl ON cl.id = c.client_id
        LEFT JOIN contacts anchor ON anchor.client_id = cl.id AND anchor.is_client_anchor
        WHERE c.id = $1
        """,
        contact_id,
    )
    return dict(row) if row else None


async def send_booking_notification(row: dict):
    """One-shot SMS to the client the moment a new appointment is booked
    for one of their leads. `row` is the freshly-inserted
    appointment_reminders row (contact_id, prospect_name, prospect_phone,
    appointment_at, prospect_timezone, id). Always stamps
    client_booking_notification_sent_at, even on skip, so a permanently
    unresolvable client (e.g. manual booking with no contact_id) is never
    retried. Never raises — callers must not let a notification bug block
    the booking itself."""
    from routers import sms as sms_router

    pool = await get_pool()
    async with pool.acquire() as conn:
        client = await _resolve_client(conn, row.get("contact_id"))

        if not client:
            print(f"[client_booking_notification] no client resolvable for appointment {row.get('id')} — skipping")
        elif not client["booking_notification_enabled"]:
            print(f"[client_booking_notification] client {client['id']} has notifications disabled — skipping")
        else:
            phone = (client["client_phone"] or client["anchor_phone"] or "").strip()
            if not phone:
                print(f"[client_booking_notification] client {client['id']} has no phone on file (own or anchor contact) — skipping")
            else:
                templates = await _get_templates()
                sms_template = templates["client_booking_notification_sms"]
                if sms_template.strip():
                    try:
                        client_first_name = first_name_from_owner(client["contact_name"])
                        lead_name = (row.get("prospect_name") or "").strip() or "your lead"
                        when = _format_when(row["appointment_at"], row["prospect_timezone"])
                        text = _fill(sms_template, client_first_name, lead_name, when)
                        # Deliberately NOT sms_router._store_message /
                        # _get_or_create_conversation — those write into
                        # sms_conversations/sms_messages, which are shaped
                        # for PROSPECT threads (read by the Inbox + Analytics
                        # as outreach conversations). Sending to the client's
                        # own number through them would create a phantom
                        # "prospect conversation" with the client, polluting
                        # the Inbox and skewing outreach analytics. Send
                        # directly instead; client_booking_notification_sent_at
                        # is this feature's own audit trail.
                        sms_router._send_twilio(phone, text)
                    except Exception as e:
                        print(f"[client_booking_notification] SMS failed for client {client['id']} ({phone}): {e}")

        await conn.execute(
            "UPDATE appointment_reminders SET client_booking_notification_sent_at = now() WHERE id = $1",
            row["id"],
        )
