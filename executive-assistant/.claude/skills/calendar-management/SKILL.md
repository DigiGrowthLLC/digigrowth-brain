# Calendar Management

Plans and creates Dylan's Google Calendar for the next day, every evening at 8PM EST. Fills the work day with time-blocked tasks based on his current priorities and fixed daily structure. If there isn't enough time for everything, it cuts by priority — lower priority items get dropped entirely, never compressed below their minimum durations.

**Run manually:** Ask Claude to run calendar management.
**Scheduled:** Runs automatically at 8PM EST every day via remote agent.

---

## What This Skill Does

1. Determines what phase Dylan is in (Phase 1 or Phase 2) based on today's date
2. Checks Google Calendar for tomorrow's existing events (meetings, calls, shifts, locked blocks)
3. Calculates remaining open time in the work window
4. Builds a time-blocked schedule filling open slots by priority order
5. Creates all blocks as Google Calendar events for tomorrow

---

## Instructions

You are Dylan's executive assistant managing his calendar for DigiGrowth, his solo AI client acquisition agency for fitness studios. Dylan's #1 priority is landing his first client and scaling to $10k/month MRR.

Do not ask for confirmation. Execute all steps silently and create the events when done.

---

### Work Week Rules

- **Mon–Fri:** Day starts at 6:30AM, work window ends at 8PM EST
- **Saturday:** Day starts at 6:30AM, work window ends at 6PM EST
- **Sunday:** Day off — create no events
- **Exception (May 11–16, 2026):** Dylan is visiting family. Day starts at 8AM instead of 6:30AM. Morning Routine begins at 8AM and all subsequent blocks shift accordingly.

---

### Phase Logic

Check today's date to determine which phase applies for tomorrow:

- **Phase 1 (through May 18, 2026):** Systems and automation is the focus. Outreach block is NOT scheduled. Priority: MR → MDR → Admin → Growth Block → Gym.
- **Phase 2 (May 19, 2026 onward, Mon–Sat):** Active outreach phase. Full schedule applies. Priority: MR → MDR → Outreach → Admin → Gym → Growth Block.

---

### Step 1 — Determine Tomorrow's Context

**Important:** All date calculations must use the **America/New_York timezone**, not UTC. This skill runs at midnight UTC = 8PM EDT. "Today" is the EDT calendar date at the time of execution. "Tomorrow" is today + 1 day in EDT.

1. What is today's date in **America/New_York** time? Tomorrow = today + 1 day in that timezone.
2. If tomorrow is Sunday → stop. Create no events.
3. What phase applies (Phase 1 or Phase 2)?
4. Does the May 11–16 exception apply? If tomorrow falls in that range, day starts at 8AM — Morning Routine begins at 8AM, all subsequent blocks shift accordingly.
5. Are there any existing calendar events? (meetings, Discount Tires shifts, appointments)

---

### Step 2 — Check Tomorrow's Calendar

Use Google Calendar to list all events for tomorrow in the America/New_York timezone.

For each existing event, note:
- Start time and end time
- Title
- Whether it's a Discount Tires work shift (look for "Discount Tires", "work", or "shift" in the title)
- Whether it is a fixed commitment or a block Dylan created himself

**All pre-existing events are treated as fixed — no new block may overlap them, regardless of what the event is.** This includes personal events (gym classes, boxing, appointments, social events, etc.). Never place a block over any existing event.

**Canonical block names** — always use exactly these titles when creating or comparing blocks:
`Morning Routine`, `Admin`, `MDR`, `Growth`, `Gym`, `Meal Prep`
Treat "Midday Routine", "Mid-Day Routine", "Mid Day Routine", "Midday", "MDR" as all meaning `MDR`.

**Audit existing blocks before scheduling:**
1. Check Morning Routine's start time against the active rule (6:30AM normally; 8AM during May 11–16). If it starts at the wrong time, update it and cascade all subsequent self-created blocks to maintain correct spacing.
2. Scan for duplicate block types using the canonical name list above. If duplicates exist, delete all but the most recently created one and ensure the survivor uses the canonical name.
3. Any self-created block that violates an active rule must be corrected before adding new blocks.

**Discount Tires shift handling:**
- If a Discount Tires shift is on the calendar, block 30 minutes before it (commute) and 1 hour after it (commute + eating). No work blocks may overlap these buffers or the shift itself.
- During Phase 2, skip the Outreach block on days with a Discount Tires shift.

Calculate all open time windows within the work day (8AM–8PM Mon–Fri, 8AM–6PM Sat).

If tomorrow already has 10+ hours committed, note the day is nearly full and only schedule remaining open gaps of 30+ minutes.

---

### Step 3 — Build the Schedule

#### Block Reference Table

| Block | Preferred Duration | Minimum | Days | Time Anchor | Notes |
|---|---|---|---|---|---|
| Morning Routine | 1.5 hours | 1 hour | Daily | 6:30 AM (8AM May 11–16) | Mindset, movement, prep for the day. First block always. |
| Admin | 1 hour | 30 min | Daily | After Morning Routine | Email triage, Notion daily review, tool ops |
| Outreach | 2 hours | 1 hour | Mon–Fri | 9:00–11:00 AM | Phase 2 only. Skip on Discount Tires days. |
| Mid-Day Routine (MDR) | 1 hour | 30 min | Daily | After outreach / late morning | Lunch, reset, brief review. 30 min always guaranteed. |
| Meal Prep | 1 hour | 1 hour | Wed only | ~1:00–2:00 PM | Hard block — must happen, but time anchor is approximate (±30 min). Place it immediately after Growth Block finishes, not at a fixed 1PM. |
| Growth Block | 3 hours | 1 hour | Daily | Afternoon | Learning, content, system building. First to drop when time is short. |
| Gym | 2 hours | 2 hours | Daily (soft) | Any open window | Must end by 9:30PM. Drops entirely if no 2-hour window exists before 9:30PM. |

#### Priority Order (drop from bottom when time is short)
1. Morning Routine ← always schedule
2. Admin ← always schedule
3. MDR (minimum 30 min) ← always guarantee at least 30 min
4. Outreach (Phase 2 only)
5. Gym
6. Growth Block ← first to drop

**Wednesday exception:** Meal Prep (1–2PM) takes priority over Gym, Growth Block, and MDR. MDR minimum (30 min) is still guaranteed before Meal Prep.

#### Schedule Rules

1. Start from 6:30AM (or 8AM during May 11–16 exception) and work forward
2. Always schedule Morning Routine first (preferred 1.5hrs, min 1hr)
3. Always schedule Admin next

**Phase 1 block order (no Outreach):**
4. After Admin: place Growth Block — fill the mid-morning slot up to the next fixed anchor (Meal Prep on Wed, or MDR otherwise). Cap at 3hrs.
5. Place MDR after the largest mid-day anchor (after Meal Prep on Wed; or around noon on other days). MDR = lunch and reset — never schedule it before noon unless there is no other option.
6. On Wednesdays: hard-block Meal Prep 1–2PM. Growth Block fills the gap between Admin and Meal Prep. MDR follows Meal Prep.
7. Schedule Gym in the first available 2-hour window after MDR, must end by 9:30PM.

**Phase 2 block order (Outreach active):**
4. After Admin: place Outreach (or compress to 1hr as last resort). Skip on Discount Tires days.
5. Place MDR immediately after Outreach.
6. On Wednesdays: hard-block Meal Prep 1–2PM.
7. Fill remaining afternoon slots with Growth Block (up to 3hrs, min 1hr).
8. Schedule Gym in the first available 2-hour window, must end by 9:30PM.

**Always:**
- Always max every block to its preferred duration before moving to the next. Only after all blocks are maxed should a gap exist — and only if no remaining block meets its minimum duration in the remaining time.
- Never leave an unscheduled gap that a lower-priority block could fill — gaps are a scheduling failure
- MDR = lunch and reset. It must never be placed before noon unless no other slot exists for the whole day
- MDR should be placed as late as possible — ideally directly before the next fixed commitment (Boxing, Discount Tires shift, end of workday). This keeps maximum contiguous work time earlier in the day.
- After Meal Prep, resume Growth Block to fill all remaining time before MDR. Growth Block may appear in two segments in one day (before and after Meal Prep) — this is intentional and correct. Total across both segments should not exceed 4 hours.
- Sales calls are never pre-scheduled — prospects self-book, adjust around them
- Do not create more than 5 focus blocks in one day
- 15-minute pre-meeting buffer only (no post-meeting buffer) — unless a Discount Tires shift requires its own buffers
- Never compress a block below its minimum; drop it entirely instead

Build a complete list of events to create:
- Title
- Start time
- End time
- Description (1–2 bullets on what to focus on)

---

### Step 4 — Create Calendar Events

Use Google Calendar to create each event from Step 3 on tomorrow's date in the America/New_York timezone.

Event format:
- **Title:** Short and action-oriented (e.g., "Outreach — Cold Calls", "Admin + Inbox", "Growth Block", "Mid-Day Routine", "Gym", "Meal Prep")
- **Description:** 1–2 bullets on what specifically to focus on during that block
- **Calendar:** Primary calendar (dylangroenendijk@gmail.com)
- **No reminders needed**

After creating all events, fetch tomorrow's calendar and confirm all events appear correctly.

---

### Step 5 — Done

No output needed. The calendar speaks for itself. If any event fails to create, retry once. If it fails again, skip it and move on.

---

## Edge Cases

- **Tomorrow is Sunday:** Create no events. Stop.
- **Tomorrow is Saturday:** Work day ends at 6PM, not 8PM. Gym must end by 6PM or drop it.
- **Discount Tires shift on calendar:** Apply 30-min pre-buffer and 1-hour post-buffer. Skip Outreach if Phase 2.
- **Tomorrow is Wednesday:** Hard-block Meal Prep 1–2PM. Drop Growth Block if no room.
- **Tomorrow fully booked:** Create no new events. Do nothing.
- **Google Calendar unavailable:** Stop. Do not retry more than once.
- **Phase 1 (before May 19):** Do not schedule Outreach. Fill time with Admin, MDR, Growth Block, Gym.
