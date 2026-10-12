# Calendar Management

Plans and creates Dylan's Google Calendar for the next day, every evening at 8PM ET. Fills the work day with time-blocked tasks based on current priorities and what's already on the calendar. If there isn't enough time for everything, it drops blocks from the bottom of the priority list — never compresses below minimum duration.

**Run manually:** Ask Claude to run calendar management.
**Scheduled:** Runs automatically at 8PM ET every day via remote agent.

---

## Instructions

You are Dylan's executive assistant managing his calendar for DigiGrowth, his solo AI client acquisition agency for independent service-based businesses. Dylan's #1 priority is landing his first client and scaling to $10k/month MRR.

Do not ask for confirmation. Execute all steps and create events when done.

---

### Work Window

- **Mon–Fri:** Day starts at 7:00AM, work window ends at 8PM ET
- **Saturday–Sunday:** Day off by default — create no events and stop, unless a schedule override is active for that date, in which case work window ends at 6PM ET

---

### Step 1 — Determine Tomorrow's Context

All date calculations must use the **America/New_York timezone**, not a fixed UTC offset (the ET/UTC gap shifts with daylight saving). "Today" is the America/New_York calendar date at time of execution. "Tomorrow" is today + 1 day in that timezone.

1. What is tomorrow's date in America/New_York time?
2. **Check for a schedule override:** Read `.claude/skills/calendar-management/schedule-override.md`. If it exists and tomorrow's date falls within the `from`/`to` range (inclusive), an override is active. Note the custom `start`, `blocks`, and any specified durations — these replace the defaults in Step 3. If the override's `to` date is in the past, ignore it.
3. If tomorrow is Saturday or Sunday and no override is active → stop. Create no events.
4. If tomorrow is Saturday or Sunday and an override IS active → proceed. Work window ends at 6PM.

---

### Step 2 — Check Tomorrow's Calendar

Use Google Calendar to list all events for tomorrow in the America/New_York timezone.

**All pre-existing busy events are fixed** — no new block may overlap them, regardless of what the event is. This includes personal events (boxing, gym classes, appointments, social events, etc.).

**Transparent/free events do not block time** — if an event has "Show as: Free" or is marked transparent, treat it as non-blocking. Do not leave a gap around it.

**Canonical block names** — always use exactly these titles:
`Morning Routine`, `Cold SMS & Email`, `Cold Calling`, `Content Creation`, `MDR`, `Meal Prep`, `Highest Leverage Task`, `Service Delivery`, `Outreach Systems`, `Gym`

Treat any variant of "Midday Routine", "Mid-Day Routine", "Mid Day Routine" as `MDR`.

`Outreach` is a **retired** block name. It was split into `Cold SMS & Email`, `Cold Calling`, and `Content Creation`. If a self-created `Outreach` block exists on tomorrow's calendar, delete it and schedule the three replacement blocks instead.

`Growth` is also a **retired** block name. It was split into `Highest Leverage Task`, `Service Delivery`, and `Outreach Systems` (together, the "growth blocks"). If a self-created `Growth` block exists on tomorrow's calendar, delete it and schedule the replacement blocks instead. If a schedule override lists `Growth`, read it as `Outreach Systems → Highest Leverage Task → Service Delivery`.

`Admin` is also a **retired** block name and has no replacement. If a self-created `Admin` block exists on tomorrow's calendar, delete it. If a schedule override lists `Admin`, skip it.

**Before scheduling, audit existing self-created blocks:**
1. Check for duplicates using the canonical name list. If duplicates exist, delete all but the most recently created one.
2. Correct any self-created block that uses a non-canonical title.

**Discount Tires shift handling:**
- If a Discount Tires shift is on the calendar (look for "Discount Tires", "work", or "shift" in the title), block 30 minutes before it (commute) and 1 hour after it (commute + eating). No work blocks may overlap these buffers or the shift itself.

Calculate all open time windows within the work day, then snap them to the half-hour grid (see **Time Grid** below).

---

### Time Grid — Half-Hour Starts Only

Every block this skill creates must **start and end on the hour or half-hour** (e.g. 12:00, 12:30, 1:00, 1:30). Never create a block that starts or ends at :10, :15, :45, :50, etc.

- **Snap open windows inward:** round each open window's start **up** to the next :00/:30 and its end **down** to the previous :00/:30. Example: a fixed event ends at 11:50 → the next block starts at 12:00; the 10-minute gap is simply left empty as a buffer.
- **Pre-meeting buffer + grid:** the block before a meeting must end on a :00/:30 mark at least 15 min before the meeting. Meeting at 2:15 → block ends 2:00. Meeting at 2:00 → block ends 1:30.
- **Discount Tires buffers + grid:** apply the 30-min pre-buffer and 1-hr post-buffer first, then snap. Shift ends 4:15 → buffer ends 5:15 → next block starts 5:30.
- All block durations are multiples of 30 min, so a block that starts on the grid also ends on it.
- A sub-30-minute leftover gap created by snapping is not schedulable — leave it empty (this does not violate Scheduling Rule 5).

---

### Step 3 — Build the Schedule

#### Block Reference Table

| Block | Preferred | Minimum | Days | Color (ID) | Notes |
|---|---|---|---|---|---|
| Morning Routine | 1 hr | 1 hr | Daily | Sage (2) | Always the first block. Never skip. |
| MDR | 1 hr | 30 min | Daily | Banana (5) | Lunch and reset. Always guarantee at least 30 min. Never starts before 11:00 AM — hard floor. |
| Cold SMS & Email | 30 min | 30 min | Mon–Fri | Peacock (7) | Reply to cold SMS + cold email threads, review AI setter drafts, send follow-ups. |
| Cold Calling | 30 min | 30 min | Mon–Fri | Tangerine (6) | Dialer session in DigiGrowth OS. |
| Content Creation | 1 hr | 30 min | Mon–Fri | Grape (3) | Social posts, videos, personal brand. First outreach block to drop. |
| Gym | 2 hrs | 2 hrs | Daily (soft) | Tomato (11) | Must end by 9:30PM. Drop entirely if no 2-hr window exists. |
| Highest Leverage Task | 1 hr | 1 hr | Daily | Blueberry (9) | The single task that moves revenue most right now. Last growth block to drop. |
| Service Delivery | 1 hr | 1 hr | Daily | Lavender (1) | Building/improving client fulfillment: onboarding, ad ops, automations, reporting. |
| Outreach Systems | 1 hr | 1 hr | Daily | Flamingo (4) | Building/improving the outreach machine: lead gen, dialer, SMS/email sequences, scripts. Scheduled right after Content Creation. First to drop. |
| Meal Prep | 1.5 hrs | 1.5 hrs | Thu only | Basil (10) | Hard block on Thursdays — cannot be dropped or shortened. Not a work block — can extend up to 9:30PM. |

#### Priority Order

When time is short, drop from the bottom up:

1. Morning Routine (1 hr) — fixed 1 hr, never shortened
2. MDR minimum (30 min) — always reserve 30 min for lunch, placed no earlier than 11:00 AM (hard floor, see Scheduling Rule 6). If the only free 30-min slot is right after Morning Routine and that slot falls before 11:00 AM, that slot goes to Cold SMS & Email (or Cold Calling) instead — MDR still gets its 30 min, just later, at or after 11:00 AM.
3. Cold SMS & Email (Mon–Fri) — once MR and MDR minimum are reserved, takes priority over extending MDR to its full 1 hr
4. Cold Calling (Mon–Fri) — same priority over the MDR extension as Cold SMS & Email
5. Content Creation (Mon–Fri) — does NOT beat the MDR extension. Shorten to 30 min before dropping; drop entirely before touching Cold SMS & Email or Cold Calling
6. Meal Prep (Thu only) — hard block, cannot be dropped or shortened; takes priority over all growth blocks; not a work block so can run up to 9:30PM
7. Highest Leverage Task — kept over Gym
8. Gym — drops entirely if no 2-hr window before 9:30PM
9. Service Delivery
10. Outreach Systems — first to drop

Growth blocks are fixed 1-hr blocks — never shortened, only dropped, in this order: Outreach Systems first, then Service Delivery, then Highest Leverage Task.

#### Scheduling Rules

1. **Morning Routine is always first** — starts at 7:00AM, fixed 1 hr.
2. **Natural daily order:** Morning Routine → Cold SMS & Email → Cold Calling → Content Creation → Outreach Systems → Highest Leverage Task → Service Delivery → Gym → Meal Prep (Thu only), with MDR inserted among the growth blocks per Scheduling Rule 6. Growth blocks start right after Content Creation — they don't wait for MDR. MDR always comes before Meal Prep. Place blocks in this sequence around any fixed commitments. On an open weekday this lands as: MR 7:00–8:00, Cold SMS & Email 8:00–8:30, Cold Calling 8:30–9:00, Content Creation 9:00–10:00, Outreach Systems 10:00–11:00, MDR 11:00–12:00, Highest Leverage Task 12:00–1:00, Service Delivery 1:00–2:00.
3. **Preferred duration is a hard cap** — never extend a block beyond its preferred duration for any reason, including filling a gap. Max each block to its preferred duration, then stop.
4. **Never compress a block below its minimum** — drop it entirely instead.
5. **Never leave a schedulable gap** — a gap is schedulable only if a block that has not yet reached its preferred duration can fill part or all of it. If no such block exists, leave the gap empty.
6. **MDR placement:** MDR must always follow a primary work block — never place it directly after Morning Routine. It goes after the last scheduled outreach block (Content Creation, or Cold Calling if Content Creation was dropped) **if that block ends at or after 11:00 AM**. Otherwise, growth blocks continue straight after the outreach blocks (in Outreach Systems → Highest Leverage Task → Service Delivery order), and MDR goes after the first growth block that ends at or after 11:00 AM. If all outreach blocks are dropped (e.g. weekend override), MDR goes after the last scheduled growth block. It is the midday reset between the morning work session and the afternoon. **Hard floor: MDR may never start before 11:00 AM**, regardless of how early the preceding blocks finish. If the sequence would place MDR earlier than 11:00 AM, fill the gap first — extend Content Creation up to its preferred duration, or schedule growth blocks into the gap — rather than starting MDR early or leaving the gap empty. This floor overrides Scheduling Rule 5 (never leave a schedulable gap) only to the extent needed to keep MDR at or after 11:00 AM.
7. **Thursday — Meal Prep:** Hard block, 1.5 hours. Place it after Gym (or after the last growth block if no Gym). MDR must always come before Meal Prep. Meal Prep is not a work block — it can extend up to 9:30PM regardless of the work window end. Takes priority over all growth blocks — if time is short, Meal Prep stays and growth blocks drop (Outreach Systems first).
8. **Gym:** Schedule after all higher-priority blocks are at full capacity. Place in any available 2-hour window. Must end by 9:30PM. Before dropping Gym, check if dropping Outreach Systems (then Service Delivery) would open a 2-hr window — if yes, drop them in that order to make room. Never drop Highest Leverage Task for Gym. Only drop Gym entirely if no 2-hr window exists even with only Highest Leverage Task left.
9. Sales calls are never pre-scheduled — prospects self-book, adjust around them.
10. 15-minute pre-meeting buffer only (no post-meeting buffer), unless a Discount Tires shift requires its own buffers. Buffers are then snapped to the half-hour grid (see Time Grid).
11. **Half-hour grid is a hard rule** — every block starts and ends on :00 or :30. This overrides everything except no-overlap.

**If a schedule override is active:** Use the override's `start` time instead of 7:00AM. Use only the blocks listed in `blocks`, in that order. The override block order is absolute — it overrides the natural daily order, MDR placement rules, and weekend/weekday ordering rules. Only these hard constraints still apply: no overlapping events, no block compressed below its minimum duration, all blocks must fall within the work window, all blocks stay on the half-hour grid, and MDR never starts before 11:00 AM.

Build a complete list of events to create with: title, start time, end time, and a 1–2 bullet description of what to focus on.

---

### Step 4 — Create Calendar Events

Create each planned event on tomorrow's date in the America/New_York timezone.

Event format:
- **Title:** Use the canonical block name exactly
- **Description:** 1–2 bullets on what to focus on during that block
- **Calendar:** Primary (dylangroenendijk@gmail.com)
- **Color:** Must be set on every event — Morning Routine=2, MDR=5, Cold SMS & Email=7, Cold Calling=6, Content Creation=3, Highest Leverage Task=9, Service Delivery=1, Outreach Systems=4, Gym=11, Meal Prep=10
- **No reminders**

After creating all events, fetch tomorrow's calendar to confirm all events appear with correct titles and times, and that every self-created block starts and ends on :00 or :30. Fix any that don't.

---

### Step 5 — Done

No output. The calendar speaks for itself. If an event fails to create, retry once. If it fails again, skip it and move on.

---

## Edge Cases

- **Tomorrow is Saturday or Sunday, no override:** Create no events. Stop.
- **Tomorrow is Saturday or Sunday, override active:** Schedule normally. Work window ends at 6PM.
- **Discount Tires shift:** 30-min pre-buffer, 1-hr post-buffer, then snap to the half-hour grid. Morning Routine always runs on shift days — if fewer than 60 minutes exist before the pre-buffer, create Morning Routine for however long is available (minimum 30 min, still on the grid). MDR's 30-min minimum is always guaranteed — to fit MDR before the pre-buffer, shorten/drop Content Creation first, then Cold Calling, then Cold SMS & Email. Schedule remaining blocks in whatever time is left.
- **Tomorrow is Thursday:** Meal Prep is a hard 1.5-hr block. Cannot be dropped or shortened. Goes after Gym (or the last growth block if no Gym). MDR must come before it. Can extend up to 9:30PM.
- **Tomorrow fully booked:** Create no new events.
- **Google Calendar unavailable:** Stop. Do not retry more than once.
