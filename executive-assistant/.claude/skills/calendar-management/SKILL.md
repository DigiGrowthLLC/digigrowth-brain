# Calendar Management (Morning Planner)

Dylan's one morning planner. Run it manually while he's doing his morning routine ("run calendar management", "plan my day", "morning plan"). It:

1. **Gathers** today's inputs: Google Calendar (classes + shifts), Canvas (assignments + tests), his Discount Tire schedule photo, what his clients' service delivery still needs, and his DigiGrowth OS To-Do list.
2. **Asks** one short round of questions (Step 0B). Whatever he says must get done today outranks everything.
3. **Books** blocks on Google Calendar from the time it's run to the end of the day in his priority order: **his must-dos → school → service delivery → to-dos → outreach**, with MDR and Gym kept by their own rules.

**Run manually only.** No scheduled/nightly run (the old 8PM routine was disabled 2026-10-20).

Setup that rarely changes (Canvas URL, schedule-photo details, learned preferences) lives in `school-and-work.md` next to this file. Read it first every run.

---

## Instructions

You are Dylan's executive assistant. He runs DigiGrowth (solo patient acquisition agency for PT practices), studies at UCF (Canvas = Webcourses) and works shifts at Discount Tire.

Gather silently (Step 0A), ask **one** message of questions (Step 0B), then, once Dylan answers, don't ask for confirmation: plan (Steps 1–3) and create the events (Step 4).

---

### Step 0A — Gather (no questions yet, run in parallel)

1. **Time + override:** current NY time (Step 1) and `schedule-override.md`.
2. **Google Calendar:** today's events (Step 2), plus the next 7 days' shift events (`Work`, `Work - CC`, `Discount Tire Shift`, anything with "work"/"shift" in the title).
3. **Canvas (Dylan's logged-in Chrome; UCF blocks API tokens):** Claude in Chrome. Load the tools in one ToolSearch call (`tabs_context_mcp`, `tabs_create_mcp`, `navigate`, `javascript_tool`, `tabs_close_mcp`), call `tabs_context_mcp` first, work in a **new tab**, open the Canvas URL from `school-and-work.md`. Login/SSO/2FA page → **don't log in or type anything**: skip Canvas and say so in Step 0B. Otherwise run [canvas-pull.js](canvas-pull.js) with `javascript_tool` (keep its leading `await`). It returns compact lines: open work (submitted/completed already removed), missing work and Canvas calendar events, in NY time, looking 10 days ahead. Read only. Close your tab when done.
4. **Shifts (schedule photo from Dylan's boss):** the scheduler app is mobile-only; his boss texts a schedule picture every Wednesday and Dylan forwards it to the **DigiGrowth OS Twilio number**. Picture texts from his own phone land in the OS `owner_mms` inbox (kept out of the prospect inbox).
   - List unread pictures: `doppler run --project digigrowth --config prd -- bash -c 'curl -s -u "admin:$DASHBOARD_PASSWORD" "$DASHBOARD_URL/api/owner-mms?unprocessed=true"'`
   - Download each new one to the session scratchpad (never the repo) with `.../api/owner-mms/<id>/image -o "<scratchpad>/schedule-<id>.jpg"` and view it with Read. Not a schedule → skip, leave unprocessed, mention it in Step 5. `size` null = the download from Twilio failed; ask him to resend.
   - Find **Dylan's row** (name variants in `school-and-work.md`), read each day's start/end, and work out the dates from the week shown (no dates → assume the week starting the next Sunday after the text, and flag it). Unclear cell → a Step 0B question; never guess a shift time.
   - Fallbacks: a photo dropped into the chat; or Gmail on the connected account (dylanrg@digigrowthllc.com), `has:attachment newer_than:10d schedule`, skipping the "Last schedule photo processed" ID in `school-and-work.md`. A `.heic` that won't open → ask for a screenshot.
   - Nothing new → use the shift events already on the calendar. Wednesday–Friday with next week's shifts still missing → Step 0B: "Got this week's schedule? Text the picture to the OS number (or drop it here)."
5. **Service delivery (what clients still need):** list clients (`GET /api/clients`, skip `DigiGrowth Demo Clinic` and inactive ones), then for each run
   ```bash
   PYTHONUTF8=1 doppler run --project digigrowth --config prd -- /c/Python314/python -X utf8 onboarding-agent/scripts/service_delivery_status.py <client id> > "<scratchpad>/sd-<id>.txt"
   ```
   from the repo root (`PYTHONUTF8`/`-X utf8` are required: without them the script crashes on Windows when its output goes to a file). Keep only the open `[ ]` steps that **Dylan can do now**: Phase 1, Phase 4 steps whose earlier phases are done, and anything unblocked. Skip steps marked "Automated" or "Optional", and steps waiting on the client (list those separately as "waiting on client"). Also scan the dylanrg@ inbox (Gmail connector) for unanswered client emails from the last 3 days; each one is a service-delivery item.
6. **DigiGrowth To-Dos:** `doppler run --project digigrowth --config prd -- bash -c 'curl -s -u "admin:$DASHBOARD_PASSWORD" "$DASHBOARD_URL/api/dashboard/todos"'`. All open to-dos are candidates: overdue/due today first, then undated (oldest first). Never schedule a to-do titled `Morning Routine`. Never mark to-dos done or edit them.

Then build a **draft plan in your head** (Steps 1–3) so the questions can point at real conflicts.

### Step 0B — Ask Once (one message, short)

Open with a short snapshot (what's fixed today, the school items, service-delivery focus, to-dos), then ask:

> 1. Anything that **must** get done today that I didn't pick up? (These go first.)
> 2. Anything to skip or push to another day?
> 3. Estimates check: assignments at 15 min each, test study 2 hrs, service delivery <N> hrs on <clients/steps>. Anything off, or already done?
> 4. Any change to your availability (leaving early, plans tonight, a hard stop)?

Rules:
- Always ask **1 and 2**. Ask **3** when there's school work or service delivery. Ask **4** only if something is unclear.
- New schedule photo read → one line with the shifts you read ("Thu 9–5, Sat 8–4, Sun off; shout if wrong").
- No shift info at all for today → add "Are you working today, and what hours?" Canvas unreadable → say so and ask "anything due in the next 3 days, or a test coming up?"
- Max 5 questions. Nothing else before booking.

Apply his answer:
- **"Must get done" / anything he explicitly says needs to happen today** → a **Must-Do** (Priority 0). Duration = what he said, else your honest estimate rounded up to 15 min (default 1 hr). His time → fixed event at that time. Never dropped, never shortened.
- **Skip / push** → leave it out today (don't touch Canvas, the To-Do list or client checklists).
- **Done / started** → drop it or shorten it to what's left.
- **Estimate corrections** → use his number. If he corrects the same kind of item twice, add it under "Learned preferences" in `school-and-work.md`.

---

### Work Window + Time Grid

- **Start:** run time (America/New_York), rounded **up** to the next quarter hour. Nothing is scheduled in the past. No `Morning Routine` block, ever.
- **End:** 8PM Mon–Fri; 6PM Sat/Sun. Gym may run until 9:30PM.
- **15-minute grid:** every block starts and ends on :00, :15, :30 or :45, and every duration is a multiple of 15 min. Snap open windows inward (start up, end down); a leftover gap under 15 min stays empty.

### Step 1 — Today's Context

All times in **America/New_York**. Current time via PowerShell: `[System.TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([DateTime]::UtcNow,'Eastern Standard Time').ToString('yyyy-MM-dd HH:mm dddd')`. Never `TZ=America/New_York date` in Git Bash (no tz database, silently returns UTC).

**Override:** read `schedule-override.md`. If today is inside its `from`/`to` range, its `blocks` list replaces the DigiGrowth blocks (Priorities 2–4) for today, in that order. Must-Dos, school, MDR and Gym rules still apply. `Highest Leverage Task` in an override = a block for the To-Do list; `Growth` = `Service Delivery → To-Do → Outreach Systems`; `Admin` is skipped. Expired override → ignore.

### Step 2 — Fixed Events

- **Every busy calendar event is fixed**; nothing may overlap it. Free/transparent events don't block time.
- **Classes** are already on Google Calendar as recurring events (e.g. `FIN 3403 - Business Finance`, location BA1, UCF). One with a physical location gets a **30-min commute buffer** before and after.
- **Shifts:** the 7-day shift events plus the photo's shifts (applied **after** his Step 0B answer, so his corrections win). Create photo shifts that aren't on the calendar yet (the whole week, not just today): title `Discount Tire Shift`, color Sage (2), no reminders, description `From boss's schedule photo (<date>)`. A photo shift overlapping an existing `Work`/shift event that day is a duplicate: don't create it. A newer photo with different times → update the event. Never delete a shift, except a self-created one on a day the newer photo shows as off (say so in Step 5). Then mark the picture processed: `POST /api/owner-mms/<id>/processed` with `{"note": "shifts booked for week of <date>"}` (Gmail fallback: write the message ID to `school-and-work.md`).
- **Shift buffers:** 30 min before (commute), 1 hr after (commute + eating).
- **Meetings/calls:** 15-min buffer before. `HOLD: offered to …` events from the SMS setter are tentative but count as busy while they exist.
- **Re-runs:** delete self-created blocks (description starts with `Planned by morning planner`, or a canonical block name) that start at or after the start time, then re-plan. Never delete shifts, classes or other events. Blocks that already started count as done.

---

### Step 3 — Build the Schedule

#### Priority order (what gets a slot first; drop from the bottom when the day runs out)

| # | Tier | What goes in it | Size |
|---|---|---|---|
| 0 | **Must-Dos** | Anything Dylan says in Step 0B must get done today | His number / estimate. Never dropped. |
| 1 | **School** | (a) **Test study:** every test in the next 3 days gets a 2-hr study block **on each of the 3 days before it** (Canvas quiz with "exam/test/midterm/final" in the title, not "Study Tool", or any quiz ≥ 50 pts; also a test Dylan mentions, and any test under "Tests Dylan told me about" in `school-and-work.md`; when he mentions a new one, add it there so later runs keep studying for it). (b) **Assignments:** everything due within 3 days (due date ≤ today + 3), plus anything overdue/`missing`. He does assignments 3 days before they're due. | Test study: 2 hrs per test per day (≤ 2 hrs in one stretch). Assignments: **15 min each, one event each**, soonest due first. |
| 2 | **Service Delivery** | Today's do-now client steps from Step 0A item 5, plus client emails waiting on Dylan. Group steps by client; the client furthest from launch first, unless a live client has something broken. | 1-hr blocks, as many as the do-now list needs, **max 3 hrs a day** unless Dylan says otherwise. Title `Service Delivery: <Client>`; description = the exact steps (guide id + one line each). |
| 3 | **To-Dos** | Open To-Do list items: fixed `due_time` today → fixed event; then overdue/due today; then undated, oldest first | 1 hr each unless the text implies otherwise (min 30 min). Title = the to-do text, short. |
| 4 | **Outreach** | Only once every to-do has a slot: fill the remaining free time in this order: `Cold SMS & Email` (30 min) → `Cold Calling` (30 min–1 hr) → `Content Creation` (1 hr) → `Outreach Systems` (1-hr blocks until the time runs out) | First to drop. Cold SMS & Email, Cold Calling and Content Creation are Mon–Fri only. |

**MDR** (lunch + reset): 1 hr, may shrink to 30 min but is never dropped. Never starts before 11:00 AM and never as the first block of the day: it goes after the first block that ends at or after 11:00 (if the start time is past noon, after the first block). If MDR would start before 11:00, fill the gap with the next block in priority order first. On a shift day where the shift spans lunch, the 1-hr post-shift buffer counts as MDR.

**Gym:** 2 hrs, always the **last block of the day**, must end by 9:30PM. If there's no 2-hr window left, drop Outreach blocks (newest first) to open one. Never drop a Must-Do, school, service delivery or a to-do for Gym; if no window opens, skip Gym and say so.

#### Placement (time order)

1. Fixed events + buffers first (classes, shifts, meetings, fixed-time Must-Dos and to-dos).
2. Then fill the open windows from the start time in priority order: Must-Dos → School (test study before assignments; an item due today goes first and must end at least 30 min before its due time) → Service Delivery → To-Dos → Outreach, inserting MDR per its rule and Gym last.
3. Long stretches: no more than 2 hrs of the same kind in a row when something else can go between (e.g. split 3 hrs of service delivery around the to-dos).
4. Never extend a block past its size to fill a gap. Fill the gap with the next item in priority order instead; if nothing is left, leave it empty.
5. If the day runs out, drop from the bottom of the priority table (Outreach first, then To-Dos, then Service Delivery hours). School and Must-Dos are never dropped silently: if they don't fit, book what fits and list the rest under **at risk** in Step 5 with the best gap to use.

---

### Step 4 — Create Calendar Events

- **Calendar:** primary (dylangroenendijk@gmail.com), America/New_York, **no reminders**.
- **Description:** first line exactly `Planned by morning planner` (re-runs find blocks by it), then 1–3 bullets: what to do. School: course, due date/time, points. Service Delivery: the client's steps. To-Do: the to-do's description, if any.
- **Titles + colors:**

| Block | Title | Color (ID) |
|---|---|---|
| Must-Do | his wording, short | Graphite (8) |
| Test study | `Study: <Course> <test>` | Basil (10) |
| Assignment | `<Course>: <item>` (e.g. `MAR 3023: WSJ Quiz #11`) | Basil (10) |
| Service Delivery | `Service Delivery: <Client>` | Lavender (1) |
| To-Do | `To-Do: <text>` | Blueberry (9) |
| Cold SMS & Email / Cold Calling / Content Creation / Outreach Systems | canonical name | Peacock (7) / Tangerine (6) / Grape (3) / Flamingo (4) |
| MDR | `MDR` | Banana (5) |
| Gym | `Gym` | Tomato (11) |
| Discount Tire Shift | `Discount Tire Shift` | Sage (2) |

After creating, list today's calendar again and check every block is there, on the 15-min grid, with no overlaps. Fix anything off. Event failed → retry once, then skip and mention it.

### Step 5 — Done

Short reply: today's schedule (time — block), then:
- dropped for lack of time
- **at risk:** school that didn't fit, anything `missing` in Canvas
- service delivery **waiting on client** (one line per client: the exact ask)
- shifts added/updated from the photo
- heads-up: tests and big deadlines in the next 7 days (with the dates their study blocks will start)

---

## Edge Cases

- **Weekend:** window ends 6PM; Mon–Fri-only outreach blocks are skipped.
- **Shift day:** shift + buffers are fixed; fit everything else around them in priority order.
- **Run late:** schedule whatever fits from now on. Nothing fits → create nothing and say so.
- **Google Calendar unavailable:** stop; don't retry more than once.
- **Canvas logged out / Chrome not connected:** never type credentials. Plan without Canvas, ask what's due, tell Dylan to sign in to Canvas in Chrome before the next run.
- **Status script fails for a client:** plan service delivery from the clients that worked and say which one failed.
- **Schedule photo missing/unreadable:** ask about today's shift; never guess times.
