"""No Show / Cancellation recovery — real 3-touch drips (0h/24h/72h) for a
CLIENT's own lead, sent from the CLIENT's own Twilio number / Gmail mailbox
using that client's own client_sequence_steps copy — never DigiGrowth's
shared Twilio/Gmail credentials and never Dylan's own no_show_sequence.py/
cancel_sequence.py copy (that copy is signed "Dylan" and links to Dylan's own
Calendly, which is wrong for a client's own patient).

Same touch cadence and step-pair-per-touch shape as no_show_sequence.py/
cancel_sequence.py (step_order 0-1 = Touch 1, 2-3 = Touch 3, 4-5 = Touch 4 —
each pair is one SMS step + one email step; see routers/clients.py's
_DEFAULT_SEQUENCE_STEPS), but progress is tracked generically via a JSONB map
(client_no_show_steps_sent / client_cancel_steps_sent on appointment_reminders,
keyed by step_order as a string) rather than fixed named columns — same
pattern as client_appointment_reminders.py's reminder_steps_sent, since a
client could in principle have a different number of steps.

Touch 1 fires synchronously the moment the outcome is recorded (send_first_touch,
called from routers/appointments.py's PATCH handler and cancel_appointment(),
routers/client_portal.py's portal_update_appointment_outcome()/
portal_cancel_appointment()) — never left to wait for the next poll. Touch 3/4
go out via send_due_touches(), scheduled from main.py on the same 5-minute
cadence as every other drip in this codebase.

Stops permanently the moment the prospect replies on either channel — routers/
client_sms_webhooks.py's inbound Twilio webhook and client_email.py's inbound
Gmail sync both call stop_sequence_for_reply() the instant a matching inbound
message lands. Reuses the SAME no_show_sequence_stopped_at/
cancel_sequence_stopped_at columns Dylan's own pipelines use — safe to share
since each engine's own query already scopes to its own leads (client leads
vs. Dylan's own), exactly like reminders_stopped_at is already shared between
reminder_engine.py and client_appointment_reminders.py.

Callers (routers/appointments.py's PATCH handler and cancel_appointment(),
routers/client_portal.py's portal_update_appointment_outcome()/
portal_cancel_appointment()) must call resolve_client_lead() first to decide
whether THIS module or the Dylan-branded no_show_sequence.py/cancel_sequence.py
should handle a given appointment — never both, and never neither.

list_active()/add()/remove() below back the client portal's Messaging tab
"View Active Prospects" queue — same shape as routers/appointments.py's
list_sequence_active()/add_to_sequence()/remove_from_sequence(), scoped to one
client's own leads.
"""

import json
from datetime import datetime, timedelta, timezone as dt_timezone

from db import get_pool
from merge_fields import first_name_from_owner

# appointment_reminders sequence key -> client_sequence_steps.sequence_key.
# client_sequence_steps also has "appointment_reminder", handled separately
# by client_appointment_reminders.py — not this module.
_SEQUENCE_KEYS = {
    "no_show": "no_show",
    "cancellation": "cancellation",
}

# (touch index, delay from anchor event) — touch 1 is index 0 (step_order 0-1),
# touch 3 is index 1 (step_order 2-3), touch 4 is index 2 (step_order 4-5). No
# index for "touch 2" — same numbering-gap convention as no_show_sequence.py/
# cancel_sequence.py (kept for historical stage-tag continuity, see those
# modules' docstrings).
_TOUCH_DELAYS = [timedelta(hours=0), timedelta(hours=24), timedelta(hours=72)]
_TOUCH_LABELS = ["Touch 1", "Touch 3", "Touch 4"]

_ANCHOR_COL = {"no_show": "outcome_show_at", "cancellation": "canceled_at"}
_ACTIVE_WHERE = {
    "no_show": "ar.outcome_show = 'no_show' AND ar.no_show_sequence_stopped_at IS NULL",
    "cancellation": "ar.status = 'canceled' AND ar.cancel_sequence_stopped_at IS NULL",
}
_STOPPED_COL = {"no_show": "no_show_sequence_stopped_at", "cancellation": "cancel_sequence_stopped_at"}
_STEPS_SENT_COL = {"no_show": "client_no_show_steps_sent", "cancellation": "client_cancel_steps_sent"}


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


def _decode_steps_sent(raw) -> dict:
    """asyncpg has no JSONB codec registered on this pool (same note as
    client_appointment_reminders.py's own decode) — comes back as a raw
    string, not a dict."""
    if isinstance(raw, str):
        return json.loads(raw)
    return dict(raw or {})


def _fill(template: str, prospect_name: str | None, client_name: str) -> str:
    return (
        (template or "")
        .replace("{first_name}", first_name_from_owner(prospect_name))
        .replace("{business}", client_name)
    )


async def _send_steps(conn_pool, client: dict, config, steps, row: dict, stage_prefix: str) -> bool:
    """Sends every step in `steps` (one touch's SMS + email pair) via the
    client's own Twilio/Gmail. Returns True if at least one channel was
    actually attempted and none of the attempted channels raised — used only
    to decide whether to record this touch as sent; a partial send (e.g.
    email configured but no Gmail mailbox connected yet) still counts as
    "sent" for the channel that DID have what it needed, mirroring
    client_appointment_reminders.py's per-channel-best-effort shape."""
    import client_email
    import client_sms

    phone = (row.get("prospect_phone") or "").strip()
    email = (row.get("prospect_email") or "").strip()
    attempted = False

    for step in steps:
        if step["channel"] == "sms":
            if not phone or not (step["body"] or "").strip():
                continue
            if not (config and config["twilio_number"]):
                print(f"[client_appointment_sequence] client {client['client_id']} has no Twilio number provisioned yet — skipping SMS")
                continue
            attempted = True
            try:
                text = _fill(step["body"], row.get("prospect_name"), client["client_name"])
                await client_sms.send_client_sms(client["client_id"], phone, text, stage=f"{stage_prefix}_sms")
            except Exception as e:
                print(f"[client_appointment_sequence] SMS failed for client {client['client_id']} ({phone}): {e}")
        elif step["channel"] == "email":
            if not email or not (step["subject"] or "").strip() or not (step["body"] or "").strip():
                continue
            if not (config and config["gmail_refresh_token"]):
                print(f"[client_appointment_sequence] client {client['client_id']} has no Gmail mailbox connected yet — skipping email")
                continue
            attempted = True
            try:
                subject = _fill(step["subject"], row.get("prospect_name"), client["client_name"])
                body = _fill(step["body"], row.get("prospect_name"), client["client_name"])
                await client_email.send_client_email(client["client_id"], email, subject, body)
            except Exception as e:
                print(f"[client_appointment_sequence] email failed for client {client['client_id']} ({email}): {e}")

    return attempted


async def send_first_touch(row: dict, sequence: str):
    """`row` is an appointment_reminders row (already updated with the new
    outcome). `sequence` is "no_show" or "cancellation". Never raises — a
    send failure here must never block the outcome update it's attached to.
    Sends Touch 1 (step_order 0-1) and records it into the JSONB progress
    map regardless of whether any channel actually sent (mirrors
    client_booking_notification.py's always-stamp behavior), so this only
    ever fires once per appointment."""
    sequence_key = _SEQUENCE_KEYS[sequence]
    steps_sent_col = _STEPS_SENT_COL[sequence]

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
            "SELECT step_order, channel, subject, body FROM client_sequence_steps "
            "WHERE client_id = $1 AND sequence_key = $2 AND step_order IN (0, 1) ORDER BY step_order",
            client["client_id"], sequence_key,
        )

    if not steps:
        print(f"[client_appointment_sequence] client {client['client_id']} has no {sequence} steps configured — skipping")
    else:
        await _send_steps(pool, dict(client), config, steps, row, f"{sequence}_touch1")

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            f"""
            UPDATE appointment_reminders SET {steps_sent_col} =
                {steps_sent_col} || jsonb_build_object('0', to_jsonb(now()), '1', to_jsonb(now()))
            WHERE id = $1
            """,
            row["id"],
        )


async def send_due_touches():
    """Poll client leads mid no_show/cancellation drip whose sequence hasn't
    been stopped and send whichever touch (3 or 4) is now due — at most one
    touch per row per poll, same shape as no_show_sequence.py/
    cancel_sequence.py's own pollers."""
    pool = await get_pool()
    now = datetime.now(dt_timezone.utc)

    for sequence, sequence_key in _SEQUENCE_KEYS.items():
        anchor_col = _ANCHOR_COL[sequence]
        steps_sent_col = _STEPS_SENT_COL[sequence]
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT ar.*, c.client_id AS lead_client_id, cl.name AS client_name
                FROM appointment_reminders ar
                JOIN contacts c ON c.id = ar.contact_id
                JOIN clients cl ON cl.id = c.client_id
                WHERE {_ACTIVE_WHERE[sequence]}
                AND ar.{anchor_col} IS NOT NULL
                AND c.client_id IS NOT NULL AND NOT c.is_client_anchor
                """
            )
        if not rows:
            continue

        for record in rows:
            row = dict(record)
            client_id = row["lead_client_id"]
            sent_map = _decode_steps_sent(row.get(steps_sent_col))
            anchor = row[anchor_col]

            for touch_idx, delay in enumerate(_TOUCH_DELAYS):
                step_order_pair = (touch_idx * 2, touch_idx * 2 + 1)
                already_sent = any(str(so) in sent_map for so in step_order_pair)
                if already_sent:
                    continue
                if now < anchor + delay:
                    break  # earlier touches must go first; not due yet either way
                async with pool.acquire() as conn:
                    steps = await conn.fetch(
                        "SELECT step_order, channel, subject, body FROM client_sequence_steps "
                        "WHERE client_id = $1 AND sequence_key = $2 AND step_order = ANY($3) ORDER BY step_order",
                        client_id, sequence_key, list(step_order_pair),
                    )
                    config = await conn.fetchrow(
                        "SELECT twilio_number, gmail_refresh_token FROM client_marketing_config WHERE client_id = $1",
                        client_id,
                    )
                if not steps:
                    print(f"[client_appointment_sequence] client {client_id} has no {_TOUCH_LABELS[touch_idx]} steps configured for {sequence} — skipping")
                    break
                await _send_steps(pool, {"client_id": client_id, "client_name": row["client_name"]}, config, steps, row, f"{sequence}_touch{touch_idx}")
                for so in step_order_pair:
                    sent_map[str(so)] = now.isoformat()
                async with pool.acquire() as conn:
                    await conn.execute(
                        f"UPDATE appointment_reminders SET {steps_sent_col} = $2 WHERE id = $1",
                        row["id"], json.dumps(sent_map),
                    )
                break


async def stop_sequence_for_reply(phone: str | None = None, email: str | None = None):
    """Called from routers/client_sms_webhooks.py's inbound Twilio webhook
    and client_email.py's inbound Gmail sync the moment a reply lands from a
    phone/email — halts any active (not yet stopped) client no-show/
    cancellation sequence for that contact so no further touches send.
    Scoped to client leads only via the contact join — never touches Dylan's
    own no_show_sequence.py/cancel_sequence.py rows."""
    if not phone and not email:
        return

    from routers import sms as sms_router

    pool = await get_pool()
    async with pool.acquire() as conn:
        for sequence in _SEQUENCE_KEYS:
            stopped_col = _STOPPED_COL[sequence]
            active_where = _ACTIVE_WHERE[sequence]
            if phone:
                await conn.execute(
                    f"""
                    UPDATE appointment_reminders ar SET {stopped_col} = now()
                    FROM contacts c
                    WHERE c.id = ar.contact_id AND c.client_id IS NOT NULL AND NOT c.is_client_anchor
                    AND {active_where}
                    AND {sms_router._phone_match('ar.prospect_phone', '$1')}
                    """,
                    phone,
                )
            if email:
                await conn.execute(
                    f"""
                    UPDATE appointment_reminders ar SET {stopped_col} = now()
                    FROM contacts c
                    WHERE c.id = ar.contact_id AND c.client_id IS NOT NULL AND NOT c.is_client_anchor
                    AND {active_where}
                    AND lower(ar.prospect_email) = lower($1)
                    """,
                    email,
                )


def _touch_progress(row: dict, sequence: str) -> dict:
    steps_sent_col = _STEPS_SENT_COL[sequence]
    sent_map = _decode_steps_sent(row.get(steps_sent_col))
    sent_touches = sum(1 for i in range(3) if str(i * 2) in sent_map or str(i * 2 + 1) in sent_map)
    anchor = row.get(_ANCHOR_COL[sequence])
    next_due = anchor + _TOUCH_DELAYS[sent_touches] if anchor and sent_touches < 3 else None
    return {
        "touches_sent": sent_touches,
        "touches_total": 3,
        "step_label": f"Touch {sent_touches} of 3 sent" if sent_touches else "Touch 1 pending",
        "next_touch_due_at": next_due,
    }


async def list_active(client_id: int, sequence: str) -> list[dict]:
    """Everyone currently mid-sequence for the given client — backs the
    client portal Messaging tab's 'View Active Prospects' queue."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT ar.*, c.business, c.owner FROM appointment_reminders ar
            JOIN contacts c ON c.id = ar.contact_id
            WHERE c.client_id = $1 AND NOT c.is_client_anchor
            AND {_ACTIVE_WHERE[sequence]}
            ORDER BY ar.{_ANCHOR_COL[sequence]} ASC
            """,
            client_id,
        )
    return [{**dict(r), **_touch_progress(dict(r), sequence)} for r in rows]


async def remove(client_id: int, appointment_id: int, sequence: str) -> bool:
    """Pull one prospect out of an active sequence early — same effect as a
    reply triggering stop_sequence_for_reply(), just manual. Returns False
    if the appointment doesn't belong to this client or isn't active."""
    stopped_col = _STOPPED_COL[sequence]
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            UPDATE appointment_reminders ar SET {stopped_col} = now()
            FROM contacts c
            WHERE ar.id = $1 AND c.id = ar.contact_id AND c.client_id = $2 AND NOT c.is_client_anchor
            AND ar.{stopped_col} IS NULL
            RETURNING ar.id
            """,
            appointment_id, client_id,
        )
    return row is not None


async def add(client_id: int, appointment_id: int, sequence: str) -> bool:
    """Manually (re-)enroll an existing appointment row into a sequence for
    this client — resets its progress map and fires Touch 1 immediately.
    Returns False if the appointment doesn't belong to this client."""
    sequence_key_col_extra = ", status = 'canceled'" if sequence == "cancellation" else ", outcome_show = 'no_show'"
    anchor_col = _ANCHOR_COL[sequence]
    steps_sent_col = _STEPS_SENT_COL[sequence]
    stopped_col = _STOPPED_COL[sequence]

    pool = await get_pool()
    async with pool.acquire() as conn:
        updated = await conn.fetchrow(
            f"""
            UPDATE appointment_reminders ar SET {anchor_col} = now(), {steps_sent_col} = '{{}}',
                {stopped_col} = NULL{sequence_key_col_extra}
            FROM contacts c
            WHERE ar.id = $1 AND c.id = ar.contact_id AND c.client_id = $2 AND NOT c.is_client_anchor
            RETURNING ar.*
            """,
            appointment_id, client_id,
        )
    if not updated:
        return False

    try:
        await send_first_touch(dict(updated), sequence)
    except Exception as e:
        print(f"[client_appointment_sequence] manual re-enroll ({sequence}) touch 1 failed for {appointment_id}: {e}")
    return True
