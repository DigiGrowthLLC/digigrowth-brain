# Calendar Management

Plans and creates Dylan's Google Calendar for **today**, run manually each morning while he's doing his morning routine. Asks one question first (any custom tasks for today?), then fills the rest of the work day — starting from the time it's run — with time-blocked tasks based on current priorities and what's already on the calendar. If there isn't enough time for everything, it drops blocks from the bottom of the priority list — never compresses below minimum duration.

**Run manually only:** Dylan says "run calendar management" (or similar) in the morning. There is no scheduled/nightly run — the old 8PM remote routine (`Calendar Management — Daily 8PM`) was disabled on 2026-10-20.

---

## Instructions

You are Dylan's executive assistant managing his calendar for DigiGrowth, his solo patient acquisition agency for independent PT practices. Dylan's #1 priority is client acquisition and scaling to $10k/month MRR.

Ask exactly one question (Step 0). After Dylan answers, do not ask for confirmation — execute all remaining steps and create the events.

---

### Step 0 — Ask for Today's Custom Blocks

Before touching the calendar, ask Dylan:

> Anything custom to add to today's schedule? Tasks or blocks that aren't part of the normal routine (give a time and/or duration if it matters).

Wait for his answer. If he says no / nothing, schedule the normal blocks only.

For each custom task he names:
- **Title:** his wording, short (e.g. `Call landlord`, `Edit CrosaCore ad`)
- **Fixed time given** ("at 2", "2–3pm") → treat it like a pre-existing fixed event: create it at that time, nothing may overlap it.
- **No time given** → it's a flexible custom block. Duration = what he said, rounded up to a multiple of 30 min; default 1 hr if he didn't say. By default it goes **last** — after every programmed block is done (Scheduling Rule 2) — unless Dylan says where it goes or gives it a higher priority.
- **Custom tasks are never dropped and never shortened.** They're last in *order*, not first to cut.
- **Color:** Graphite (8)
- **Description:** 1–2 bullets restating what he said needs to get done

---

### Work Window

- **Start:** the time the skill is run (America/New_York), rounded **up** to the next :00 or :30. Run at 8:12 → first block starts 8:30. Run at 9:00 → first block starts 9:00. Nothing is ever scheduled in the past.
- **End:** 8PM ET Mon–Fri. On Saturday/Sunday, Dylan running the skill means he wants a schedule — work window ends 6PM, and the Mon–Fri-only outreach blocks are skipped.
- **No Morning Routine block.** Dylan is already doing his morning routine when he runs this. Never create a `Morning Routine` event — start straight with the next block.

---

### Step 1 — Determine Today's Context

All date/time calculations must use the **America/New_York timezone**, not a fixed UTC offset. Get the current time with PowerShell: `[System.TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([DateTime]::UtcNow,'Eastern Standard Time').ToString('yyyy-MM-dd HH:mm dddd')`. Do **not** use `TZ=America/New_York date` on Dylan's Windows PC — Git Bash has no tz database, silently ignores `TZ` and returns UTC (4–5 hrs off).

1. What is today's date, weekday, and the current time? Compute the start time (round up to :00/:30).
2. **Check for a schedule override:** Read `.claude/skills/calendar-management/schedule-override.md`. If today's date falls within the `from`/`to` range (inclusive), an override is active — its `blocks` list replaces the defaults in Step 3. Its `start` is used only if it is later than the run-time start; otherwise start at run time. Skip `Morning Routine` if it's listed. If the override's `to` date is in the past, ignore it.

---

### Step 2 — Check Today's Calendar

Use Google Calendar to list all events for today in the America/New_York timezone.

**All pre-existing busy events are fixed** — no new block may overlap them, regardless of what the event is. This includes personal events (boxing, gym classes, appointments, social events, etc.) and any fixed-time custom tasks from Step 0.

**Transparent/free events do not block time** — if an event has "Show as: Free" or is marked transparent, treat it as non-blocking. Do not leave a gap around it.

**Canonical block names** — always use exactly these titles:
`Cold SMS & Email`, `Cold Calling`, `Content Creation`, `MDR`, `Highest Leverage Task`, `Service Delivery`, `Outreach Systems`, `Gym`

Treat any variant of "Midday Routine", "Mid-Day Routine", "Mid Day Routine" as `MDR`.

**Retired block names** (if a self-created one exists on today's calendar from now onward, delete it):
- `Morning Routine` — no longer scheduled by this skill. Leave one that's already in the past/in progress alone.
- `Outreach` — replaced by `Cold SMS & Email`, `Cold Calling`, `Content Creation`.
- `Growth` — replaced by `Outreach Systems`, `Highest Leverage Task`, `Service Delivery` (the "growth blocks"). If a schedule override lists `Growth`, read it as `Outreach Systems → Highest Leverage Task → Service Delivery`.
- `Admin` — no replacement. If an override lists `Admin`, skip it.

**Re-runs:** if self-created blocks (canonical names) already exist on today's calendar starting at or after the start time, delete them and re-plan from scratch — this keeps re-running the skill idempotent. Leave blocks that already started, and count them as done for today: don't schedule a second copy of a block that already started earlier today.

**Discount Tires shift handling:**
- If a Discount Tires shift is on the calendar (look for "Discount Tires", "work", or "shift" in the title), block 30 minutes before it (commute) and 1 hour after it (commute + eating). No work blocks may overlap these buffers or the shift itself.

Calculate all open time windows between the start time and the end of the work day, then snap them to the half-hour grid (see **Time Grid** below).

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
| MDR | 1 hr | 30 min | Daily | Banana (5) | Lunch and reset. Always guarantee at least 30 min. Never starts before 11:00 AM — hard floor. |
| Cold SMS & Email | 30 min | 30 min | Mon–Fri | Peacock (7) | Reply to cold SMS + cold email threads, review AI setter drafts, send follow-ups. |
| Cold Calling | 30 min | 30 min | Mon–Fri | Tangerine (6) | Dialer session in DigiGrowth OS. |
| Content Creation | 1 hr | 30 min | Mon–Fri | Grape (3) | Social posts, videos, personal brand. First outreach block to drop. |
| Custom (from Step 0) | as given | as given | Today | Graphite (8) | Dylan's one-off tasks for today. Scheduled last by default. Never shortened, never dropped. |
| Gym | 2 hrs | 2 hrs | Daily (soft) | Tomato (11) | Always the last block of the day (after custom tasks). Must end by 9:30PM. Drop entirely if no 2-hr window exists. |
| Highest Leverage Task | 1 hr | 1 hr | Daily | Blueberry (9) | The single task that moves revenue most right now. Last growth block to drop. |
| Service Delivery | 1 hr | 1 hr | Daily | Lavender (1) | Building/improving client fulfillment: onboarding, ad ops, automations, reporting. |
| Outreach Systems | 1 hr | 1 hr | Daily | Flamingo (4) | Building/improving the outreach machine: lead gen, dialer, SMS/email sequences, scripts. Scheduled right after Content Creation. First to drop. |

#### Priority Order

Nothing is dropped unless the day actually runs out — i.e. the blocks no longer fit before the 8PM work-window end (9:30PM for Gym). Only then, drop programmed blocks from the bottom up:

1. MDR minimum (30 min) — always reserve 30 min for lunch, placed no earlier than 11:00 AM (hard floor, see Scheduling Rule 6)
2. Cold SMS & Email (Mon–Fri) — takes priority over extending MDR to its full 1 hr
3. Cold Calling (Mon–Fri) — same priority over the MDR extension as Cold SMS & Email
4. Content Creation (Mon–Fri) — does NOT beat the MDR extension. Shorten to 30 min before dropping; drop entirely before touching Cold SMS & Email or Cold Calling
5. Highest Leverage Task — kept over Gym
6. Gym — drops entirely if no 2-hr window before 9:30PM (see Scheduling Rule 7)
7. Service Delivery
8. Outreach Systems — first to drop
9. Custom tasks (Step 0) — last in priority order, but **never dropped** (see below)

**Custom tasks are never dropped.** They're scheduled after all work blocks; if they don't fit before 8PM, drop work blocks from the bottom of this list (Outreach Systems first) until they do. Fixed-time custom tasks are fixed events and always stay at their time. If Dylan ranks a custom task higher ("chores first", "after lunch"), place it there instead.

**Gym is always the last block of the day in time order** — after custom tasks — even though it outranks Service Delivery and Outreach Systems for dropping.

Growth blocks are fixed 1-hr blocks — never shortened, only dropped, in this order: Outreach Systems first, then Service Delivery, then Highest Leverage Task.

#### Scheduling Rules

1. **Start at run time** — the first block starts at the rounded-up run time (see Work Window). No Morning Routine.
2. **Natural daily order:** Cold SMS & Email → Cold Calling → Content Creation → Outreach Systems → Highest Leverage Task → Service Delivery → flexible custom tasks (in the order Dylan listed them) → Gym, with MDR inserted per Scheduling Rule 6. Growth blocks start right after Content Creation — they don't wait for MDR. Place blocks in this sequence around any fixed commitments. Custom tasks must end by 8PM; Gym must end by 9:30PM. If Dylan said a custom task should go somewhere specific ("after lunch", "first thing"), honor that instead. Example — run at 8:05 on an open weekday with a 2-hr Chores task: Cold SMS & Email 8:30–9:00, Cold Calling 9:00–9:30, Content Creation 9:30–10:30, Outreach Systems 10:30–11:30, MDR 11:30–12:30, Highest Leverage Task 12:30–1:30, Service Delivery 1:30–2:30, Chores 2:30–4:30, Gym 4:30–6:30.
3. **Preferred duration is a hard cap** — never extend a block beyond its preferred duration for any reason, including filling a gap. Max each block to its preferred duration, then stop.
4. **Never compress a block below its minimum** — drop it entirely instead.
5. **Never leave a schedulable gap** — a gap is schedulable only if a block that has not yet reached its preferred duration can fill part or all of it. If no such block exists, leave the gap empty.
6. **MDR placement:** MDR must always follow a primary work block — never make it the first block of the day. It goes after the last scheduled outreach block (Content Creation, or Cold Calling if Content Creation was dropped) **if that block ends at or after 11:00 AM**. Otherwise, growth blocks continue straight after the outreach blocks (in Outreach Systems → Highest Leverage Task → Service Delivery order), and MDR goes after the first growth block that ends at or after 11:00 AM. If all outreach blocks are dropped (e.g. weekend), MDR goes after the first block that ends at or after 11:00 AM. If the skill is run so late that the start time is already past noon, MDR goes after the first scheduled block. **Hard floor: MDR may never start before 11:00 AM**, regardless of how early the preceding blocks finish. If the sequence would place MDR earlier than 11:00 AM, fill the gap first — extend Content Creation up to its preferred duration, or schedule growth blocks into the gap — rather than starting MDR early or leaving the gap empty. This floor overrides Scheduling Rule 5 only to the extent needed to keep MDR at or after 11:00 AM.
7. **Gym:** Always the last block of the day — placed after all work blocks and custom tasks. Must end by 9:30PM. If no 2-hr window is left before 9:30PM, check if dropping Outreach Systems (then Service Delivery) would open one — if yes, drop them in that order to make room (custom tasks shift earlier). Never drop Highest Leverage Task or a custom task for Gym. Only drop Gym entirely if no 2-hr window exists even with only Highest Leverage Task left.
8. Sales calls are never pre-scheduled — prospects self-book, adjust around them.
9. 15-minute pre-meeting buffer only (no post-meeting buffer), unless a Discount Tires shift requires its own buffers. Buffers are then snapped to the half-hour grid (see Time Grid).
10. **Half-hour grid is a hard rule** — every block starts and ends on :00 or :30. This overrides everything except no-overlap.

**If a schedule override is active:** Use only the blocks listed in `blocks` (minus `Morning Routine`), in that order, plus Dylan's custom tasks from Step 0. The override block order is absolute — it overrides the natural daily order, MDR placement rules, and weekend/weekday ordering rules. Only these hard constraints still apply: no overlapping events, nothing scheduled before the run-time start, no block compressed below its minimum duration, all blocks within the work window, all blocks on the half-hour grid, and MDR never starts before 11:00 AM.

Build a complete list of events to create with: title, start time, end time, and a 1–2 bullet description of what to focus on.

---

### Step 4 — Create Calendar Events

Create each planned event on today's date in the America/New_York timezone.

Event format:
- **Title:** Use the canonical block name exactly (custom tasks: Dylan's short wording)
- **Description:** 1–2 bullets on what to focus on during that block
- **Calendar:** Primary (dylangroenendijk@gmail.com)
- **Color:** Must be set on every event — MDR=5, Cold SMS & Email=7, Cold Calling=6, Content Creation=3, Highest Leverage Task=9, Service Delivery=1, Outreach Systems=4, Gym=11, custom tasks=8
- **No reminders**

After creating all events, fetch today's calendar to confirm all events appear with correct titles and times, and that every self-created block starts and ends on :00 or :30. Fix any that don't.

---

### Step 5 — Done

Reply with a short list of today's schedule (time — block), plus any blocks that were dropped for lack of time. If an event fails to create, retry once. If it fails again, skip it and mention it.

---

## Edge Cases

- **Saturday or Sunday:** Dylan ran it, so schedule. Work window ends 6PM. Outreach blocks (Mon–Fri only) are skipped.
- **Discount Tires shift:** 30-min pre-buffer, 1-hr post-buffer, then snap to the half-hour grid. MDR's 30-min minimum is always guaranteed — to fit MDR before the pre-buffer, shorten/drop Content Creation first, then Cold Calling, then Cold SMS & Email. Schedule remaining blocks in whatever time is left.
- **Run late in the day:** schedule whatever fits from the start time on, following the priority order. If nothing fits, create nothing and say so.
- **Rest of today fully booked:** Create no new events.
- **Google Calendar unavailable:** Stop. Do not retry more than once.
