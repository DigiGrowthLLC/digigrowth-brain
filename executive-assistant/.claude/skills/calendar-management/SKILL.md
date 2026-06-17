# Calendar Management

Plans and creates Dylan's Google Calendar for the next day, every evening at 8PM EST. Fills the work day with time-blocked tasks based on current priorities and what's already on the calendar. If there isn't enough time for everything, it drops blocks from the bottom of the priority list — never compresses below minimum duration.

**Run manually:** Ask Claude to run calendar management.
**Scheduled:** Runs automatically at 8PM EST every day via remote agent.

---

## Instructions

You are Dylan's executive assistant managing his calendar for DigiGrowth, his solo AI client acquisition agency for fitness studios. Dylan's #1 priority is landing his first client and scaling to $10k/month MRR.

Do not ask for confirmation. Execute all steps and create events when done.

---

### Work Window

- **Mon–Fri:** Day starts at 8:30AM, work window ends at 8PM EST
- **Saturday–Sunday:** Day off by default — create no events and stop, unless a schedule override is active for that date, in which case work window ends at 6PM EST

---

### Step 1 — Determine Tomorrow's Context

All date calculations must use the **America/New_York timezone**, not UTC. This skill runs at midnight UTC = 8PM EDT. "Today" is the EDT calendar date at time of execution. "Tomorrow" is today + 1 day in that timezone.

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
`Morning Routine`, `Admin`, `Outreach`, `MDR`, `Meal Prep`, `Growth`, `Gym`

Treat any variant of "Midday Routine", "Mid-Day Routine", "Mid Day Routine" as `MDR`.

**Before scheduling, audit existing self-created blocks:**
1. Check for duplicates using the canonical name list. If duplicates exist, delete all but the most recently created one.
2. Correct any self-created block that uses a non-canonical title.

**Discount Tires shift handling:**
- If a Discount Tires shift is on the calendar (look for "Discount Tires", "work", or "shift" in the title), block 30 minutes before it (commute) and 1 hour after it (commute + eating). No work blocks may overlap these buffers or the shift itself.

Calculate all open time windows within the work day.

---

### Step 3 — Build the Schedule

#### Block Reference Table

| Block | Preferred | Minimum | Days | Color (ID) | Notes |
|---|---|---|---|---|---|
| Morning Routine | 1.5 hrs | 1 hr | Daily | Sage (2) | Always the first block. Never skip. |
| MDR | 1 hr | 30 min | Daily | Banana (5) | Lunch and reset. Always guarantee at least 30 min. |
| Outreach | 2 hrs | 1 hr | Mon–Fri | Tangerine (6) | |
| Admin | 30 min | 30 min | Daily | Graphite (8) | Email triage, Notion review, tool ops. |
| Gym | 2 hrs | 2 hrs | Daily (soft) | Tomato (11) | Must end by 9:30PM. Drop entirely if no 2-hr window exists. |
| Growth | 3 hrs | 1 hr | Daily | Blueberry (9) | Learning, content, system building. First to drop. |
| Meal Prep | 1.5 hrs | 1.5 hrs | Thu only | Basil (10) | Hard block on Thursdays — cannot be dropped or shortened. Not a work block — can extend up to 9:30PM. |

#### Priority Order

When time is short, drop from the bottom up:

1. Morning Routine minimum (1 hr) — never drop below 1 hr
2. MDR minimum (30 min) — always reserve 30 min for lunch; if there's only 30 min left after Morning Routine, give it to MDR over Outreach
3. Outreach — once MR and MDR minimums are reserved, Outreach takes priority over extending Morning Routine to 1.5 hrs or extending MDR to its full 1 hr; a full Outreach session beats a full Morning Routine or a full MDR
4. Admin
5. Meal Prep (Thu only) — hard block, cannot be dropped or shortened; takes priority over Growth; not a work block so can run up to 9:30PM
6. Gym — drops entirely if no 2-hr window before 9:30PM
7. Growth — first to drop

#### Scheduling Rules

1. **Morning Routine is always first** — starts at 8:30AM, 1 hr minimum. Preferred 1.5 hrs, but Outreach takes priority over the extra 30 min if time is tight.
2. **Natural daily order:** Morning Routine → Admin → Outreach → MDR → Growth → Gym → Meal Prep (Thu only). MDR always comes before Meal Prep. Place blocks in this sequence around any fixed commitments.
3. **Preferred duration is a hard cap** — never extend a block beyond its preferred duration for any reason, including filling a gap. Max each block to its preferred duration, then stop.
4. **Never compress a block below its minimum** — drop it entirely instead.
5. **Never leave a schedulable gap** — a gap is schedulable only if a block that has not yet reached its preferred duration can fill part or all of it. If no such block exists, leave the gap empty.
6. **MDR placement:** MDR must always follow a primary work block — never place it directly after Admin alone. It goes after Outreach. If Outreach is dropped entirely due to time constraints, MDR goes after Growth. It is the midday reset between the morning work session and the afternoon.
7. **Thursday — Meal Prep:** Hard block, 1.5 hours. Place it after Gym (or after Growth if no Gym). MDR must always come before Meal Prep. Meal Prep is not a work block — it can extend up to 9:30PM regardless of the work window end. Takes priority over Growth — if time is short, Meal Prep stays and Growth drops.
8. **Gym:** Schedule after all higher-priority blocks are at full capacity. Place in any available 2-hour window. Must end by 9:30PM. Before dropping Gym, check if shortening Growth below its preferred duration (but not below its 1-hr minimum) would open a 2-hr window — if yes, shorten Growth to make room. Only drop Gym entirely if no 2-hr window exists even with Growth at its minimum.
9. Sales calls are never pre-scheduled — prospects self-book, adjust around them.
10. 15-minute pre-meeting buffer only (no post-meeting buffer), unless a Discount Tires shift requires its own buffers.

**If a schedule override is active:** Use the override's `start` time instead of 8:30AM. Use only the blocks listed in `blocks`, in that order. The override block order is absolute — it overrides the natural daily order, MDR placement rules, and weekend/weekday ordering rules. Only these hard constraints still apply: no overlapping events, no block compressed below its minimum duration, all blocks must fall within the work window.

Build a complete list of events to create with: title, start time, end time, and a 1–2 bullet description of what to focus on.

---

### Step 4 — Create Calendar Events

Create each planned event on tomorrow's date in the America/New_York timezone.

Event format:
- **Title:** Use the canonical block name exactly
- **Description:** 1–2 bullets on what to focus on during that block
- **Calendar:** Primary (dylangroenendijk@gmail.com)
- **Color:** Must be set on every event — Morning Routine=2, MDR=5, Outreach=6, Admin=8, Gym=11, Growth=9, Meal Prep=10
- **No reminders**

After creating all events, fetch tomorrow's calendar to confirm all events appear with correct titles and times.

---

### Step 5 — Done

No output. The calendar speaks for itself. If an event fails to create, retry once. If it fails again, skip it and move on.

---

## Edge Cases

- **Tomorrow is Saturday or Sunday, no override:** Create no events. Stop.
- **Tomorrow is Saturday or Sunday, override active:** Schedule normally. Work window ends at 6PM.
- **Discount Tires shift:** 30-min pre-buffer, 1-hr post-buffer. Morning Routine always runs on shift days — if fewer than 60 minutes exist before the pre-buffer, create Morning Routine for however long is available (minimum 30 min). MDR's 30-min minimum is always guaranteed — shorten Outreach if needed to fit MDR before the pre-buffer starts. Schedule remaining blocks in whatever time is left.
- **Tomorrow is Thursday:** Meal Prep is a hard 1.5-hr block. Cannot be dropped or shortened. Goes after Gym (or Growth if no Gym). MDR must come before it. Can extend up to 9:30PM.
- **Tomorrow fully booked:** Create no new events.
- **Google Calendar unavailable:** Stop. Do not retry more than once.
