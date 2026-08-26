---
name: outbound-sequences
description: Build or iterate SMS/email sequences tied to the appointment-booking lifecycle — cold outbound, reminders, no-shows, cancellations, general follow-ups — for DigiGrowth or client businesses.
---

# Outbound Sequences Skill

Write SMS and email copy for the messaging that surrounds booking an appointment: initial cold outbound, pre-appointment reminders, no-show recovery, cancellation/win-back, and general follow-up. Works for DigiGrowth itself or a client business (same any-business scope as the rest of `copy-agent`).

Sources:
- `references/no-show-psychology.md` — why no-shows actually happen (commitment/consistency research, healthcare no-show studies, temporal discounting, post-booking dissonance) and what it implies for recovery copy. Read this before drafting or revising **any no-show sequence** — it should drive the copy, not just tone.

## Trigger

Use this skill when Dylan asks to:
- Write or revise a cold SMS outreach sequence (the multi-step drip that runs before someone books)
- Write or revise appointment reminder copy (the touches that fire before a scheduled call)
- Write or revise a no-show follow-up sequence
- Write a cancellation / win-back sequence
- Get help with any other appointment-lifecycle messaging (general follow-up, reschedule notices, etc.)

## Ground truth: what actually exists in the DigiGrowth OS

Before drafting, know which real mechanism (if any) a sequence maps to — copy and mechanics are two different things, and Dylan may ask for one without realizing it implies a change to the other.

**1. Cold outbound — the 5-step SMS sequence** (`dashboard/backend/routers/sms_sequences.py`, `sms_sequences` table, editable from Business Resources → Outreach Templates → SMS Sequences). Fixed 5 steps, always in this order:
| Key | Label |
|---|---|
| `curiosity_opener` | 1. Initial Message |
| `relevance` | 2. Primed Message |
| `guarantee` | 3. Engaged Message |
| `ask` | 4. Call To Action |
| `cta` | 5. Booking Link |

Multiple named sequences can exist; exactly one is `is_default` at a time and populates the SMS Inbox's dropdown. This is SMS-only — no paired email. Note there's also a separate, earlier `auto_opener` stage (the true top-of-funnel message every lead gets automatically) — don't confuse the two; "Initial Message" here is a *manually-sent* step that only fires after `auto_opener` gets a reply.

**2. Appointment reminders** (`dashboard/backend/reminder_engine.py`). Fires at fixed windows before a scheduled appointment, SMS + email each: **24h, 6h, 1h**, plus a **reschedule** notice sent immediately when a time changes. Each of the 4 instances has independently editable SMS text + email subject + email body (Business Resources → Outreach Templates). Purely informational tone — no CTA needed beyond confirming the time, since the appointment is already booked.

**3. No-show recovery** (`dashboard/backend/no_show_sequence.py`). Fires after a rep marks an appointment's outcome "No Show." **4 touches**, all timed from the moment it's marked:
| Touch | Delay | Channel(s) | Intent |
|---|---|---|---|
| 1 | 0h | SMS + email | Blame-neutral, "must've missed each other" |
| 2 | 3h | SMS only | Re-pitch value, no email (deliberately one channel — avoids feeling like a barrage) |
| 3 | 24h | SMS + email | Social proof / normalize it |
| 4 | 72h | SMS + email | "Breakup" — close the loop, no pressure |

**4. Cancellation — no dedicated sequence exists yet.** `cancel_appointment()` in `routers/appointments.py` only sets `status = 'canceled'` and stops any pending no-show touches — there's no analogous `_TOUCHES` drip for cancellations in the backend today. If Dylan wants a real automated cancel/win-back sequence, say so explicitly: the copy alone won't run anywhere until a `cancel_sequence.py` engine (mirroring `no_show_sequence.py`'s pattern — touch schedule, template columns, stop-on-reply) gets built. Don't imply it already exists. It's fine to still write the copy now — just flag the gap and note it in the output file.

**Merge fields that actually resolve** — only use these unless building copy for something with no engine at all:
- `{first_name}` — from `merge_fields.first_name_from_owner`
- `{when}` — formatted local appointment time (reminders/reschedule only)
- `{Meeting_Link}` — real Calendly join link for the specific appointment, resolved at send time (reminders/reschedule only)
- `{link}` — generic `integrations.CALENDLY_URL` fallback (used where there's no specific meeting to look up, e.g. no-show touches)

## Design constraints baked into the shipped defaults

These aren't arbitrary style choices — they're patterns already proven in the live templates, so match them unless Dylan asks to break from them:
- **One channel per touch is often deliberate**, not an oversight (no-show Touch 2 is SMS-only specifically to avoid a same-moment SMS+email barrage). Don't automatically add the missing channel back in.
- **Every sequence stops dead the instant the prospect replies** on either channel (`stop_sequence_for_reply` / equivalent). Write each touch to stand on its own — never write a touch that only makes sense if the prior one was read and ignored, since you can't assume that.
- **Tone across all shipped defaults**: casual, first-name led, blame-neutral/low-pressure, one clear CTA per message, never guilt-trippy or salesy. SMS stays to 1-2 short sentences; email mirrors the same message with a touch more warmth, not a different pitch.
- **Later touches soften, not escalate.** The no-show progression goes disarm → re-pitch → normalize → close-the-loop, never ramps up pressure.

**No-show sequences specifically — apply `references/no-show-psychology.md`:**
- The shipped defaults above are blame-neutral and low-pressure, which is correct, but on their own they're still fairly generic ("must've missed each other," a bare `{link}`) — the research says generic reminders barely move reply/rebook rates while *specific* framing does. Sharpen, don't replace: keep the blame-neutral tone, but make at least one touch name the *specific* thing they lose by staying no-showed (the concrete pain/gap the offer solves for that business), not just "let's find a new time."
- A no-show happened because the original commitment was weak (a passive link click), so don't just offer another passive link on the reschedule ask — build in a small active step somewhere in the sequence (asking them to reply with a day/time that works, or confirm back "does Tuesday work?") rather than pure link-and-silence.
- The first touch must land same-day/immediately (this already matches the 0h timing of the shipped no-show engine) — the psychology behind that: dissonance hardens into a settled "not interested" story the longer it sits.
- At least one touch should reactivate the *original* pain that got them to book in the first place, not just process the logistics of the miss — the pain is decaying (temporal discounting) faster than the prospect's memory of agreeing to the call.
- Never add guilt or a confessional tone ("you missed your appointment") — shame increases avoidance, it doesn't reduce it.

## Workflow

1. **Clarify scope**: which lifecycle stage (cold outbound / reminder / no-show / cancellation / general follow-up / something custom), which business (DigiGrowth or a named client — don't assume DigiGrowth's voice/offer applies to a client), channel(s), and whether Dylan wants to match an existing engine's touch count/timing or design new mechanics.
2. **If it maps to an existing engine** (cold 5-step, reminders, no-show), match its real structure — same number of touches, same timing windows, same channel-per-touch pattern — unless Dylan explicitly asks to change the mechanics. If a copy request implies a mechanics change (e.g. "add a 5th no-show touch," "send the reminder at 48h too"), flag that it needs a backend change in the relevant `.py` file, not just a template edit — mention the file by name.
3. **Draft each touch**: SMS first (short, mobile-legible, one CTA, correct merge fields for that stage), then matching email subject + body only if the stage uses email. Vary phrasing touch-to-touch so a multi-touch sequence doesn't read like the same message resent.
4. **Save** to `outputs/sms-sequence-[stage]-[business]-YYYY-MM-DD.md`, laid out touch-by-touch with channel headers, e.g.:
   ```md
   ## Touch 1 — 0h (SMS + Email)
   **SMS:** ...
   **Email subject:** ...
   **Email body:** ...
   ```
   If the stage has no backend engine yet (cancellation), add a one-line note at the top of the file saying so.
5. **Point to where it's pasted in**: if the sequence maps to a real dashboard template, tell Dylan exactly which Business Resources → Outreach Templates row each touch goes into (e.g. "No Show → Touch 3 SMS").
6. **Confirm** what was saved and where, per `copy-agent` convention.

## Reminders

- Copy and mechanics are separate — never imply a sequence runs automatically if its engine doesn't exist.
- Only use merge fields that actually resolve for that stage; don't invent new placeholders.
- Match existing touch counts/timing/channel patterns unless asked to change them, and flag it clearly when a request needs a backend change.
- Every touch must stand alone — sequences stop on first reply, so don't chain logic across touches.
- Keep the tone consistent with the shipped defaults: casual, low-pressure, one CTA, softening (not escalating) over a sequence's later touches.
- No-show copy specifically: name a specific loss (not a vague "we missed you"), build in one active-commitment step rather than an all-link sequence, reactivate the original pain rather than just apologizing for the miss, and never add guilt.
