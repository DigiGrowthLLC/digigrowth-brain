"""One-shot No Show / Cancellation outreach to a CLIENT's own lead, sent from
the CLIENT's own Twilio number / Gmail mailbox using that client's own
client_sequence_steps copy — never DigiGrowth's shared Twilio/Gmail
credentials and never Dylan's own no_show_sequence.py/cancel_sequence.py
copy (that copy is signed "Dylan" and links to Dylan's own Calendly, which
is wrong for a client's own patient).

Distinct from no_show_sequence.py/cancel_sequence.py in shape too: those run
a scheduled 3-touch drip (0h/24h/72h) via main.py's poller. client_sequence_
steps only ever seeds a single touch per sequence (step_order 0 = SMS,
step_order 1 = email, both "Touch 1"), so this fires once, synchronously,
right when the outcome is recorded — same one-shot pattern as
client_booking_notification.py. No poller/scheduler entry needed.

Callers (routers/appointments.py's PATCH handler and cancel_appointment(),
routers/client_portal.py's portal_update_appointment_outcome()/
portal_cancel_appointment()) must call resolve_client_lead() first to decide
whether THIS module or the Dylan-branded no_show_sequence.py/cancel_sequence.py
should handle a given appointment — never both, and never neither.
"""

from db import get_pool
from merge_fields import first_name_from_owner

# appointment_reminders sequence key -> client_sequence_steps.sequence_key.
# client_sequence_steps also has "appointment_reminder", handled separately
# by reminder_engine.py — not this module.
_SEQUENCE_KEYS = {
    "no_show": "no_show",
    "cancellation": "cancellation",
}

_SENT_COLUMN = {
    "no_show": "client_no_show_sequence_sent_at",
    "cancellation": "client_cancel_sequence_sent_at",
}


async def resolve_client_lead(contact_id: str | None) -> dict | None:
    """contact_id -> the real client this lead belongs to, or None if this
    is Dylan's own sales-pipeline contact (no contact, no client_id, or the
    anchor contact — see call_reminders.py's identical exclusion). Callers
    use this to decide whether to route an outcome change to this module
    (a client's own lead) or to no_show_sequence.py/cancel_sequence.py
    (Dylan's own pipeline)."""
    if not contact_id:
        return None
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT cl.id AS client_id, cl.name AS client_name
            FROM contacts c
            JOIN clients cl ON cl.id = c.client_id
            WHERE c.id = $1 AND c.client_id IS NOT NULL AND NOT c.is_client_anchor
            """,
            contact_id,
        )
    return dict(row) if row else None


def _fill(template: str, prospect_name: str | None, client_name: str) -> str:
    return (
        (template or "")
        .replace("{first_name}", first_name_from_owner(prospect_name))
        .replace("{business}", client_name)
    )


async def send_first_touch(row: dict, sequence: str):
    """`row` is an appointment_reminders row (already updated with the new
    outcome). `sequence` is "no_show" or "cancellation". Never raises —
    a send failure here must never block the outcome update it's attached
    to. Always stamps the sent column, even on skip, so this only ever
    fires once per appointment (mirrors client_booking_notification.py's
    always-stamp behavior)."""
    import client_email
    import client_sms

    sent_col = _SENT_COLUMN[sequence]
    pool = await get_pool()
    async with pool.acquire() as conn:
        client = await conn.fetchrow(
            """
            SELECT cl.id AS client_id, cl.name AS client_name
            FROM contacts c
            JOIN clients cl ON cl.id = c.client_id
            WHERE c.id = $1 AND c.client_id IS NOT NULL AND NOT c.is_client_anchor
            """,
            row.get("contact_id"),
        )
        if not client:
            print(f"[client_appointment_sequence] appointment {row.get('id')} isn't a client lead — skipping")
            return

        config = await conn.fetchrow(
            "SELECT twilio_number, gmail_refresh_token FROM client_marketing_config WHERE client_id = $1",
            client["client_id"],
        )
        steps = await conn.fetch(
            "SELECT channel, subject, body FROM client_sequence_steps "
            "WHERE client_id = $1 AND sequence_key = $2 ORDER BY step_order",
            client["client_id"], _SEQUENCE_KEYS[sequence],
        )

    # Connection released above before the outbound Twilio/Gmail calls below
    # (each of which acquires its own connection internally) — same
    # release-before-network-I/O shape as no_show_sequence.py's
    # send_due_touches()/_send_touch().
    if not steps:
        print(f"[client_appointment_sequence] client {client['client_id']} has no {sequence} steps configured — skipping")
    else:
        phone = (row.get("prospect_phone") or "").strip()
        email = (row.get("prospect_email") or "").strip()
        for step in steps:
            if step["channel"] == "sms":
                if not phone or not (step["body"] or "").strip():
                    continue
                if not (config and config["twilio_number"]):
                    print(f"[client_appointment_sequence] client {client['client_id']} has no Twilio number provisioned yet — skipping SMS")
                    continue
                try:
                    text = _fill(step["body"], row.get("prospect_name"), client["client_name"])
                    await client_sms.send_client_sms(client["client_id"], phone, text, stage=f"{sequence}_touch1")
                except Exception as e:
                    print(f"[client_appointment_sequence] SMS failed for client {client['client_id']} ({phone}): {e}")
            elif step["channel"] == "email":
                if not email or not (step["subject"] or "").strip() or not (step["body"] or "").strip():
                    continue
                if not (config and config["gmail_refresh_token"]):
                    print(f"[client_appointment_sequence] client {client['client_id']} has no Gmail mailbox connected yet — skipping email")
                    continue
                try:
                    subject = _fill(step["subject"], row.get("prospect_name"), client["client_name"])
                    body = _fill(step["body"], row.get("prospect_name"), client["client_name"])
                    await client_email.send_client_email(client["client_id"], email, subject, body)
                except Exception as e:
                    print(f"[client_appointment_sequence] email failed for client {client['client_id']} ({email}): {e}")

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            f"UPDATE appointment_reminders SET {sent_col} = now() WHERE id = $1", row["id"],
        )
