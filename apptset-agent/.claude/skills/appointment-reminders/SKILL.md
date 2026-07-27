# Appointment Reminders

Texts (and emails) a booked prospect at 24h, 6h, and 1h before their appointment,
worded in *their own* timezone — so a rep cold-calling across the US doesn't have
to think about time zones when booking.

**Sending is fully automated.** A Railway-side backend job checks for due reminders
every 5 minutes and sends them via Twilio SMS + Gmail. **Capturing the booking is
manual** — Calendly is on the Free/Basic plan, which has no webhook/API access, so
there's no way to detect a booking automatically. Instead, the rep fills in a small
form (date, time, timezone) right when they disposition a call "Appointment Booked",
alongside the Calendly iframe they already use to book the call live. If Calendly is
ever upgraded to a paid plan, that manual form can be swapped for a real webhook
without touching anything downstream — same table, same sending job.

---

## How It Works End-to-End

1. Rep dispositions a call "Appointment Booked" in the Dialer panel or inbound
   CallScreen (`dashboard/frontend/src/panels/DialerPanel.jsx`,
   `dashboard/frontend/src/CallScreen.jsx`). This opens the existing Calendly
   iframe **and** a booking-capture form (`dashboard/frontend/src/BookingForm.jsx`)
   right below it.
2. The form's timezone dropdown defaults to a best guess from the prospect's phone
   area code (`dashboard/backend/timezone_lookup.py`) — the rep can override it if
   the guess looks wrong (some area codes span two timezones).
3. On submit, `POST /api/appointment-reminders` (`dashboard/backend/routers/appointments.py`)
   converts the local date/time + timezone to UTC, inserts a row into the
   `appointment_reminders` table, and immediately sends a thank-you confirmation
   SMS + email (`reminder_engine.send_booking_confirmation()`) — separate from the
   24h/6h/1h schedule, marked in `confirmation_sent_at`.
4. A scheduled job (`reminder_engine.send_due_reminders()`, registered in
   `dashboard/backend/main.py`'s `lifespan()`, runs every 5 minutes) checks every
   `scheduled` row for the 24h/6h/1h windows and sends an SMS (Twilio, via
   `routers/sms.py`) and email (Gmail, via `integrations.gmail_send`) once each
   window is crossed. Each send is marked in `reminder_24h_sent_at` /
   `reminder_6h_sent_at` / `reminder_1h_sent_at` so it's never sent twice.

---

## Checking Status

Dylan will ask things like "did the reminder go out for tomorrow's 2pm?" or "show
me upcoming appointments" — answer from the live data, don't guess:

```
GET /api/appointment-reminders?status=scheduled   # upcoming, default view
GET /api/appointment-reminders?status=all         # everything, including canceled
```

Each row has `appointment_at` (UTC), `prospect_timezone`, `prospect_name`,
`prospect_phone`, `prospect_email`, and the three `reminder_*_sent_at` timestamps
(null = not sent yet). The dashboard also has a dedicated **Appointments** nav tab
(`dashboard/frontend/src/panels/AppointmentsPanel.jsx`) showing the same data with
✓/pending badges per window — point Dylan there for a visual view.

## Canceling / Rescheduling

There's no webhook to auto-detect a Calendly-side cancel or reschedule — Dylan (or
a rep) has to say so. Two ways to manage an existing booking, both available from
the Appointments panel *and* from the Appointments section embedded directly in
every contact's card (`AppointmentsSection.jsx`, shown in `ContactCard.jsx` and the
CRM tab's contact drawer):

- **Cancel**: `POST /api/appointment-reminders/{id}/cancel` — stops any further
  reminders for that row. Used for a canceled appointment.
- **Reschedule / edit**: `PATCH /api/appointment-reminders/{id}` with any of
  `date`, `time`, `timezone`, `prospect_name`, `prospect_phone`, `prospect_email`.
  Changing the date/time/timezone resets the 24h/6h/1h `reminder_*_sent_at` flags
  (so the new time gets fresh reminders) and immediately sends a "you've been
  rescheduled" SMS/email (`reminder_engine.send_reschedule_confirmation()`).

`GET /api/appointment-reminders?contact_id={id}&status=all` returns every booking
(current, past, canceled) for one contact — that's what the contact-card section
uses to show upcoming vs. past appointments.

## Editing the Message Text

All five message instances (booking confirmation, 24h/6h/1h reminders, reschedule
notice) are editable from **Business Resources → Outreach Templates → Appointment
Reminders**, same place as the "Send Info" and SMS Sequence templates — backed by
`GET`/`PUT /api/dialer/reminder-template` (`dashboard/backend/routers/dialer.py`),
stored in the same `dialer_settings` key/value table. **Each instance has three
independently editable fields**: SMS message, email subject, and email body (SMS
and email are no longer forced to share the same wording). `reminder_engine.py`
reads these fresh from the DB on every send (`_get_templates()`), never a cached or
hardcoded value once Dylan has edited them — same "always live" pattern as
`sms.send_info_message()`. Templates support `{first_name}` and `{when}`
placeholders; `{when}` is the appointment time formatted in the prospect's own
timezone. If Dylan asks to change the wording of a reminder, point him at that
editor — don't hand-edit the DB directly.

---

## Edge Cases

- **A contact is missing a phone or email:** whichever channel is missing is
  silently skipped — the other still sends. Flag this to Dylan if he asks why only
  one reminder type went out for a given contact.
- **The rep skipped the booking form:** no row is ever created, so nothing reminds.
  This is the most common failure mode — if Dylan says a prospect wasn't reminded,
  first check whether a row exists at all for that appointment before looking
  anywhere else.
- **Wrong timezone guess:** the area-code table isn't perfect for split-timezone
  states (e.g. Texas, Michigan). If a reminder text shows the wrong local time,
  it means the rep didn't correct the pre-filled dropdown — nothing to fix in code,
  just a reminder to double-check next time.

## Future: Real Calendly Integration

If Dylan upgrades Calendly to a paid plan (Standard or higher, needed for
webhooks), the manual booking form can be replaced by a Calendly `invitee.created`
webhook that captures the exact booked time and the prospect's real browser
timezone automatically — no rep data entry at all. That would only change how rows
get into `appointment_reminders`; `reminder_engine.py` and everything downstream
stays the same.
