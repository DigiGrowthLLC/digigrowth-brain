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

- **Mon–Fri:** Work day is 8AM–8PM EST
- **Saturday:** Work day is 8AM–6PM EST
- **Sunday:** Day off — create no events
- Morning Routine (6:30–8AM) is a personal block — never schedule over it, never create it as a calendar event

---

### Phase Logic

Check today's date to determine which phase applies for tomorrow:

- **Phase 1 (through May 18, 2026):** Systems and automation is the focus. Outreach block is NOT scheduled. Priority: MR → MDR → Admin → Growth Block → Gym.
- **Phase 2 (May 19, 2026 onward, Mon–Sat):** Active outreach phase. Full schedule applies. Priority: MR → MDR → Outreach → Admin → Gym → Growth Block.

---

### Step 1 — Determine Tomorrow's Context

1. What is tomorrow's date and day of the week?
2. If Sunday → stop. Create no events.
3. What phase applies (Phase 1 or Phase 2)?
4. Are there any existing calendar events? (meetings, Discount Tires shifts, appointments)

---

### Step 2 — Check Tomorrow's Calendar

Use Google Calendar to list all events for tomorrow in the America/New_York timezone.

For each existing event, note:
- Start time and end time
- Title
- Whether it's a Discount Tires work shift (look for "Discount Tires", "work", or "shift" in the title)
- Whether it is a fixed commitment or a block Dylan created himself

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
| Admin | 1 hour | 30 min | Daily | 8:00–9:00 AM | Email triage, Notion daily review, tool ops |
| Outreach | 2 hours | 1 hour | Mon–Fri | 9:00–11:00 AM | Phase 2 only. Skip on Discount Tires days. |
| Mid-Day Routine (MDR) | 1 hour | 30 min | Daily | After outreach / late morning | Lunch, reset, brief review. 30 min always guaranteed. |
| Meal Prep | 1 hour | 1 hour | Wed only | 1:00–2:00 PM | Hard block. Replaces Growth Block on Wednesdays. Takes priority over Gym, Growth, MDR on Wednesdays. |
| Growth Block | 3 hours | 1 hour | Daily | Afternoon | Learning, content, system building. First to drop when time is short. |
| Gym | 2 hours | 2 hours | Daily (soft) | Any open window | Must end by 9:30PM. Drops entirely if no 2-hour window exists before 9:30PM. |

#### Priority Order (drop from bottom when time is short)
1. Admin ← always schedule
2. MDR (minimum 30 min) ← always guarantee at least 30 min
3. Outreach (Phase 2 only)
4. Gym
5. Growth Block ← first to drop

**Wednesday exception:** Meal Prep (1–2PM) takes priority over Gym, Growth Block, and MDR. MDR minimum (30 min) is still guaranteed before Meal Prep.

#### Schedule Rules

1. Start from 8AM and work forward
2. Always schedule Admin first (8–9AM) if the slot is open
3. In Phase 2: place Outreach at 9–11AM (or compress to 9–10AM as last resort)
4. Always guarantee a minimum 30-min MDR block after Outreach (or late morning if no Outreach)
5. On Wednesdays: hard-block Meal Prep 1–2PM
6. Fill remaining afternoon slots with Growth Block (up to 3 hours, min 1 hour)
7. If a 2-hour Gym window is open before 9:30PM and doesn't displace higher-priority blocks, schedule it
8. Sales calls are never pre-scheduled — prospects self-book, adjust around them
9. Do not create more than 4 focus blocks in one day
10. 15-minute pre-meeting buffer only (no post-meeting buffer) — unless a Discount Tires shift requires its own buffers
11. Never compress a block below its minimum; drop it entirely instead

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
