# DM Follow-Up Sequence

Fires a 3-touch SMS follow-up to a prospect who's reached the **DM Reach**
stage in the Inbox (`sms_conversations.stage_dm_reached`, a manual checkbox
— see `dashboard/backend/routers/sms.py`'s module docstring) but has gone
quiet mid-conversation. SMS-only — DM Reach has no email equivalent today.

---

## How It Works End-to-End

1. A rep checks **DM Reached** on a conversation in the Inbox.
2. **Only applies going forward.** Checking the box for the first time (a
   `false → true` transition) stamps `dm_followup_enrolled_at = now()` in
   `email_inbox.py`'s `set_contact_stage()` — this is the actual eligibility
   gate, not `stage_dm_reached` alone. Conversations that were already
   `stage_dm_reached = true` before this feature shipped are **not**
   backfilled and never got a chance to trigger that transition, so they're
   permanently excluded unless someone deliberately re-enrolls them (see
   below). This was a deliberate scope decision — Dylan didn't want every
   prospect he'd ever DM-Reached suddenly getting texted the day this
   shipped.
3. Every 5 minutes, `dm_followup_sequence.send_due_touches()` (registered in
   `dashboard/backend/main.py`'s `lifespan()`) scans every DM-Reached,
   **enrolled** conversation that isn't closed and has no `disposition` set
   (covers both stop conditions below), and for each one, derives its
   current state **live** from `sms_messages` timestamps — there's no
   separate "sequence active" flag to fall out of sync.
4. **Touch 1 fires 24h** after Dylan's last message goes unanswered.
   **Touch 2 fires 48h after Touch 1 actually sends**, **Touch 3 fires 4
   days after Touch 2 actually sends** — chained off real send times (not a
   single fixed anchor) specifically so that enrolling an old, long-silent
   conversation (see "Manually enrolling an old prospect" below) can't fire
   all three touches back-to-back in the same 5-minute polling window. Under
   normal conditions (each touch sends right on schedule) this chain works
   out to the same 24h/72h/7d cadence from the original silence event.
5. **Stops the instant they reply** — no hook, no delay beyond the next
   5-minute poll: the moment an inbound message is the most recent thing in
   the thread, the sequence's state clears itself.
6. **Restarts automatically** if, after that reply, Dylan sends another
   message and *that* one goes unanswered for 24h — a fresh 3-touch cycle
   begins from the new message.
7. **Stops permanently** if the conversation is marked **Not Interested**
   (`disposition = 'not_interested'`, set via `POST /inbox/contact/{id}/stage`
   in `email_inbox.py`) or the appointment gets **booked**
   (`disposition = 'booked'`, set by `routers/appointments.py`'s
   `create_appointment()` when the booking came from that SMS thread).

## Manually Enrolling an Old Prospect

Uncheck **DM Reached** in the Inbox, then check it again. That's a fresh
`false → true` transition, which re-stamps `dm_followup_enrolled_at = now()`
and enrolls the conversation starting from that moment — no separate
"enroll" button exists. If the conversation has been silent a while, Touch 1
can fire on the very next poll (it genuinely is overdue), but Touch 2/3
still each wait their own full interval from there per the chaining above,
so it never sends more than one touch in a burst.

## Why There's No Explicit "Stop on Reply" Hook

`no_show_sequence.py`/`cancel_sequence.py` need a synchronous hook in the
inbound Twilio webhook because their trigger event (a no-show, a
cancellation) is a one-time thing with no natural way to re-derive "did they
reply since." This sequence is different: whether the prospect has replied
is always re-computable from `sms_messages` alone, so instead of a stop
flag, `send_due_touches()` compares `MAX(sent_at) WHERE direction='outbound'`
against `MAX(sent_at) WHERE direction='inbound'` on every poll:

- **Inbound ≥ outbound** ("ball in Dylan's court," they just replied): clear
  `dm_followup_anchor_at` and all three touch-sent columns. Nothing sends
  until he messages again.
- **Outbound > inbound** ("ball in their court"): if the last outbound
  message is newer than everything already recorded for the current cycle
  (the anchor, and every touch already sent), that's a genuinely new human
  message — restart the cycle from there. Otherwise it's still the same
  cycle in progress — keep counting from the original anchor.

This also means the sequence's own touches don't accidentally reset
themselves: sending a touch makes it the new "last outbound" on the next
poll, but since it's never newer than the anchor/touch timestamp just
recorded, the poller correctly recognizes "still the same cycle" and lets
the next touch fire on its own schedule (chained off the previous touch's
real send — see the timing note above) instead of restarting.

## Current Copy (editable from the OS)

Live in **Business Resources → Outreach Templates → DM Follow-Up (SMS)**.

**Touch 1 — Still Around? (24h)**
> Hey {first_name}, didn't want this to fall through the cracks — still around if you want to keep chatting: {link}

**Touch 2 — Value Reminder (72h)**
> {first_name} — still happy to show you how businesses like yours are adding 15-20 sessions/month whenever you're free: {link}

**Touch 3 — Final / Breakup (7 days)**
> {first_name} — going to close this out unless I hear back. No pressure, just let me know: {link}

## Revising the Copy

Editable directly in the OS — no code change needed for wording tweaks. For
a real copy revision (not just a tweak), use `copy-agent`'s
`outbound-sequences` skill for the drafting/psychology work, then either
paste the result into the OS editor or update the defaults in
`dashboard/backend/dm_followup_sequence.py` (`_TOUCH*_SMS_DEFAULT`) if the
shipped default itself should change.

## Checking Status

```
SELECT phone, dm_followup_enrolled_at, dm_followup_anchor_at,
       dm_followup_touch1_sent_at, dm_followup_touch2_sent_at, dm_followup_touch3_sent_at
FROM sms_conversations
WHERE stage_dm_reached = true AND dm_followup_enrolled_at IS NOT NULL;
```

`dm_followup_enrolled_at` is null for any conversation the sequence will
never touch (not enrolled — most likely a pre-existing DM Reached
conversation from before this shipped). `dm_followup_anchor_at` is the
start of the current silence cycle for an enrolled conversation (null = no
active cycle right now, either never started or cleared by a reply). Each
`touch*_sent_at` is null until that touch actually sends.

## Scope Note — SMS Only

DM Reach exists only on `sms_conversations` today; `email_conversations` has
no stage-tracking columns at all. Extending this to email threads would need
new stage columns and a manual stage-set UI on the email side first — that's
a separate, larger piece of work, not a small extension of this one.
