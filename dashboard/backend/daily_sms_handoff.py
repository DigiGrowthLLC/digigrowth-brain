"""
Weekday morning SMS handoff — every Monday-Friday at 8:00am Eastern, every
prospect still in status "new" (what leadgen-agent pushes scraped leads in
as) moves to "sms-handoff", the status that starts SMS outreach.

The status move and the opener text are deliberately split:

  move_new_to_handoff()  8:00am ET Mon-Fri (main.py CronTrigger). Flips status
                         and stamps contacts.auto_handoff_at. Sends nothing.
  send_due_openers()     every 2 minutes through the day. Sends the "Hey is
                         this {first_name}?" opener to contacts the move
                         stamped, OPENERS_PER_RUN at a time, OPENER_GAP_SECONDS
                         apart, and only 8am-8pm on a weekday in the
                         PROSPECT'S own time (timezone_lookup.guess_timezone).

Why split: 8am Eastern is 5am Pacific, and texting a prospect before 8am
their time runs into telemarketing quiet-hours rules. And ~100 identical
openers fired in the same second is exactly the pattern carriers filter as
spam (and would bring every reply back at once). Pacing them through
send_opening_message() — the same function the CRM's own sms-handoff status
change calls — keeps each one identical to a manual handoff, just spread out.

Openers only go out while the AI setter worker on Dylan's PC is online
(sms_setter_ai.worker_status), so replies get answered right away; with the
PC off, stamped contacts just wait and go out once it's back on.

contacts.auto_handoff_opener_at records each opener attempt, so a Railway
redeploy mid-morning resumes where it left off instead of dropping or
double-sending anyone. A contact moved out of sms-handoff by hand before its
opener went out is skipped.

On/off: dialer_settings["daily_sms_handoff_enabled"] ("false" turns it off;
default on).
"""
import asyncio
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from db import get_pool
from timezone_lookup import guess_timezone

ENABLED_KEY = "daily_sms_handoff_enabled"
OPENERS_PER_RUN = 4
OPENER_GAP_SECONDS = 25
LOCAL_SEND_HOURS = (8, 20)   # prospect's own time, [start, end)


async def _enabled(conn) -> bool:
    row = await conn.fetchrow("SELECT value FROM dialer_settings WHERE key = $1", ENABLED_KEY)
    return not (row and (row["value"] or "").strip().lower() in ("false", "0", "off"))


async def move_new_to_handoff() -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        if not await _enabled(conn):
            print("[daily-sms-handoff] disabled, skipping", flush=True)
            return 0
        # Same scope as the CRM list: never a client's own portal lead. No
        # phone = nothing to text; those stay "new" for Dylan to route.
        rows = await conn.fetch(
            """
            UPDATE contacts
            SET status = 'sms-handoff', auto_handoff_at = now(), auto_handoff_opener_at = NULL, updated_at = now()
            WHERE status = 'new'
              AND (client_id IS NULL OR is_client_anchor)
              AND COALESCE(TRIM(phone), '') <> ''
            RETURNING id
            """
        )
        skipped = await conn.fetchval(
            "SELECT COUNT(*) FROM contacts WHERE status = 'new' AND (client_id IS NULL OR is_client_anchor)"
        )
        if rows:
            await conn.execute(
                "INSERT INTO agent_messages (agent, message) VALUES ($1, $2)",
                "sms-handoff",
                f"Moved {len(rows)} new prospect(s) to SMS Handoff. Openers go out through the morning, "
                f"8am+ in each prospect's own time, while your PC's AI setter is online."
                + (f" {skipped} new prospect(s) have no phone number and were left as new." if skipped else ""),
            )
    print(f"[daily-sms-handoff] moved {len(rows)} new -> sms-handoff ({skipped} left without phone)", flush=True)
    return len(rows)


def _in_local_window(phone: str, city: str | None, state: str | None) -> bool:
    local = datetime.now(ZoneInfo(guess_timezone(phone, city, state)))
    return local.weekday() < 5 and LOCAL_SEND_HOURS[0] <= local.hour < LOCAL_SEND_HOURS[1]


async def send_due_openers() -> int:
    # Deferred import — routers.sms imports a lot of the app; keep this
    # module importable on its own (same pattern as sms.py's own deferred
    # imports).
    from routers import sms as sms_router

    import sms_setter_ai

    pool = await get_pool()
    async with pool.acquire() as conn:
        # Only while the AI setter on Dylan's PC is online, so every reply
        # to an opener gets answered in about a minute instead of sitting
        # unanswered all day. The 8am status move still happens regardless;
        # waiting openers go out once the PC is back.
        if not (await sms_setter_ai.worker_status(conn))["worker_online"]:
            return 0
        rows = await conn.fetch(
            """
            SELECT id, phone, owner, email, business, city, state FROM contacts
            WHERE status = 'sms-handoff' AND auto_handoff_at IS NOT NULL AND auto_handoff_opener_at IS NULL
            ORDER BY auto_handoff_at, id
            LIMIT 200
            """
        )
    due = [dict(r) for r in rows if _in_local_window(r["phone"], r["city"], r["state"])][:OPENERS_PER_RUN]
    sent = 0
    for i, contact in enumerate(due):
        if i:
            await asyncio.sleep(OPENER_GAP_SECONDS)
        async with pool.acquire() as conn:
            # Re-check: Dylan may have moved them by hand in the meantime.
            still_due = await conn.fetchval(
                "SELECT 1 FROM contacts WHERE id = $1 AND status = 'sms-handoff' AND auto_handoff_opener_at IS NULL",
                contact["id"],
            )
            if not still_due:
                continue
            # Stamp BEFORE sending: a crash mid-send must never lead to a
            # second opener on the next run.
            await conn.execute(
                "UPDATE contacts SET auto_handoff_opener_at = $2 WHERE id = $1",
                contact["id"], datetime.now(timezone.utc),
            )
        try:
            if await sms_router.send_opening_message(contact):
                sent += 1
        except Exception as e:
            print(f"[daily-sms-handoff] opener failed for {contact.get('phone')}: {e}", flush=True)
    if sent:
        print(f"[daily-sms-handoff] sent {sent} opener(s)", flush=True)
    return sent
