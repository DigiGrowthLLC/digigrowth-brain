"""Automatic email-handoff trigger — the "SMS went quiet, fall back to
email" channel switch. Runs from main.py's APScheduler (5-min poller,
alongside dm-followup-sequence and the other sequence engines).

Does NOT send email itself. It only detects eligible leads and flips their
contacts.status to "email-handoff" via crm._fire_email_handoff — the exact
same hook every other status-transition site in routers/crm.py already
calls (PATCH /contacts/{id}, disposition, bulk set_status, create/import).
That hook enrolls the contact into email_handoff_sequence.py's 3-touch
sequence. This reuses the existing plumbing instead of duplicating a send
path here.

Eligibility ("3 days after the SMS handoff, if they never replied at all"):
  - A cold SMS was sent (sms_conversations row exists for this contact).
  - The contact's FIRST outbound SMS was sent 3+ days ago.
  - Zero inbound SMS has EVER been recorded for this contact — computed
    live against sms_messages, not trusted from sms_conversations.
    stage_replied, which a rep can manually clear for CRM hygiene without
    it meaning the lead never really replied (same reasoning
    dm_followup_sequence.py uses for its own live reply checks). A lead who
    replied at ANY point, no matter what stage they're at now, must never
    be enrolled here.
  - Not already resolved (sc.disposition IS NULL, sc.status != 'closed' —
    same two guard columns dm_followup_sequence.py uses).
  - Not already in (or past) email-handoff / closed — status NOT IN
    ('email-handoff', 'closed') avoids re-enrolling every poll.
"""
from db import get_pool

_ELIGIBLE_QUERY = """
    SELECT c.id, c.phone, c.owner, c.business, c.email
    FROM contacts c
    JOIN sms_conversations sc ON sc.contact_id = c.id
    WHERE c.status NOT IN ('email-handoff', 'closed')
      AND c.email IS NOT NULL AND c.email != ''
      AND c.email_opted_out = false
      AND sc.disposition IS NULL
      AND sc.status != 'closed'
      AND NOT EXISTS (
          SELECT 1 FROM sms_messages sm
          WHERE sm.contact_id = c.id AND sm.direction = 'inbound'
      )
      AND (
          SELECT MIN(sm2.sent_at) FROM sms_messages sm2
          WHERE sm2.contact_id = c.id AND sm2.direction = 'outbound'
      ) <= now() - interval '3 days'
"""


async def send_due_touches():
    """Named send_due_touches for consistency with the other sequence
    modules' APScheduler entrypoint, even though this one only transitions
    status rather than sending anything directly."""
    from routers.crm import _fire_email_handoff

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(_ELIGIBLE_QUERY)
        if not rows:
            return

        for record in rows:
            row = dict(record)
            contact_id = row["id"]
            try:
                await conn.execute(
                    "UPDATE contacts SET status = 'email-handoff', updated_at = now() WHERE id = $1",
                    contact_id,
                )
                await _fire_email_handoff(row)
            except Exception as e:
                print(f"[email_followup_trigger] failed to enroll contact {contact_id}: {e}")
