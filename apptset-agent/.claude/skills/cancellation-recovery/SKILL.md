# Cancellation Recovery

Fires a 4-touch SMS/email drip to win back a prospect after their discovery call
appointment gets marked canceled — same shape as the No Show sequence, different
copy, different trigger.

**Detection is manual.** Calendly is on the Free/Basic plan, which has no
webhook/API access, so there's no way to detect a Calendly-side cancellation
automatically — Dylan (or a rep) has to notice and click **Cancel** on the
appointment in the Appointments tab. From that click onward, everything below
is fully automatic. If Calendly is ever upgraded to a paid plan, the click can
be replaced with a real `invitee.canceled` webhook without touching anything
downstream — same table, same sequence, same sending job (same swap path
already documented for appointment-reminders' booking-capture form).

---

## How It Works End-to-End

1. A rep clicks **Cancel** on a `scheduled` appointment in the Appointments tab
   (`dashboard/frontend/src/panels/AppointmentsPanel.jsx`).
2. `POST /api/appointment-reminders/{id}/cancel`
   (`dashboard/backend/routers/appointments.py::cancel_appointment`) flips
   `status` to `'canceled'`, stamps `canceled_at = now()` — the clock the
   4-touch drip counts its delays from — and fires **Touch 1** synchronously
   (`cancel_sequence.send_first_touch()`), not left to wait for the next poll.
3. A scheduled job (`cancel_sequence.send_due_touches()`, registered in
   `dashboard/backend/main.py`'s `lifespan()`, runs every 5 minutes alongside
   the No Show poller) checks every canceled row and sends whichever touch is
   next due.
4. The sequence stops permanently the moment the prospect replies on either
   channel — `routers/sms.py`'s inbound Twilio webhook and
   `routers/email_inbox.py`'s Gmail sync both call
   `cancel_sequence.stop_sequence_for_reply()` the instant a matching inbound
   message lands.

Touch schedule (all offsets from `canceled_at`):

| Touch | Delay | Channels | Framing |
|---|---|---|---|
| 1 | 0h (immediate) | SMS + email | "No worries, plans change" — validates the decision, frictionless rebook |
| 2 | 3h | SMS only | Light nudge, value reminder |
| 3 | 24h | SMS + email | "Still worth 15 minutes?" — low-pressure reopen |
| 4 | 72h | SMS + email | The "breakup" — closes the loop unless they reply |

## Why the copy isn't a copy-paste of the No Show sequence

A no-show is a **passive miss** — nobody consciously chose it, so "must've
missed each other" fits. A cancellation is an **active, deliberate decision**
— the prospect made a call. Pretending it was accidental reads as tone-deaf.
Touch 1 here validates that plans change (no guilt-tripping, no pretending it
didn't happen) and makes rebooking frictionless, rather than assuming an
accident. See `dashboard/backend/cancel_sequence.py`'s module docstring for
the full rationale — read it before revising this sequence's copy.

## Current Copy (editable from the OS)

Live in **Business Resources → Outreach Templates → Cancellation** — this is
just the shipped default, source of truth is the OS once anyone edits it there.

**Touch 1 — No Worries** (SMS + email)
> SMS: Hey {first_name}, no worries at all — things come up. Whenever you're ready to grab a new time: {link}
>
> Email subject: No worries, {first_name}
>
> Email body: Hey {first_name}, Saw you had to cancel — totally understand, things come up. Whenever the timing's better, here's a new link: {link}. Talk soon, Dylan

**Touch 2 — Same-Day Follow-Up** (SMS only)
> Hey {first_name} — still happy to show you how studios like yours are adding 15-20 sessions/month whenever you're free. 15 min: {link}

**Touch 3 — Still Worth 15 Minutes** (SMS + email)
> SMS: {first_name}, if timing's just been off, still worth 15 minutes to see if this is a fit: {link}
>
> Email subject: Still worth 15 minutes?
>
> Email body: Hey {first_name}, Plans change, that's normal. If it's still worth exploring whether this could help book more sessions, here's a new link: {link}. If not, no hard feelings — just let me know and I'll close this out.

**Touch 4 — Final / Breakup** (SMS + email)
> SMS: {first_name} — going to close this out unless I hear back. No pressure either way, just let me know: {link}
>
> Email subject: Closing your file, {first_name}
>
> Email body: Hey {first_name}, Haven't heard back, so I'll close this out on my end unless I hear from you. If timing's just bad right now, no worries at all — reply here whenever it opens up. Dylan

## Revising the Copy

Editable directly in the OS (Business Resources → Outreach Templates →
Cancellation) — no code change needed for wording tweaks. If Dylan asks for a
copy revision, use `copy-agent`'s `outbound-sequences` skill for the actual
drafting/psychology work (it has the reference material on why prospects
cancel and what recovery copy should account for), then either walk Dylan
through pasting the new copy into the OS editor or update the defaults in
`dashboard/backend/cancel_sequence.py` (`_TOUCH*_SMS_DEFAULT` etc.) if the
shipped default itself should change.

## Checking Status

```
GET /api/appointment-reminders?status=canceled   # every canceled appointment
```

Each row has `canceled_at`, `cancel_touch1_sent_at` through
`cancel_touch4_sent_at` (null = not sent yet), and `cancel_sequence_stopped_at`
(set the moment the prospect replies — no further touches send after that).

## If Calendly Ever Goes Paid

Same upgrade path as `appointment-reminders`' manual booking-capture form: add
a `/webhooks/calendly` endpoint that receives `invitee.canceled`, have it call
the same `cancel_appointment()` logic (or POST to the existing endpoint) using
phone/email to match the Calendly invitee back to a `contacts`/
`appointment_reminders` row, and the manual Cancel-button click becomes
optional instead of required — everything downstream (the 4-touch drip, the
reply-stop hooks, the OS editor) needs zero changes.
