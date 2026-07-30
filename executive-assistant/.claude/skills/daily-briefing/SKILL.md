# Daily Briefing

Generates Dylan's daily morning briefing, saves it as a dated archive file, and delivers the full briefing as a formatted markdown message in the OS chat window.

**Run manually:** Ask Claude to run the daily briefing.
**Scheduled:** Runs automatically at 6:03 AM ET, daily including weekends (cloud trigger `EA Daily Briefing`).
**Duplicate guard:** Before doing any work, the trigger checks git log for a same-day report committed in the last 3 hours — if found, it exits silently. Never re-run this skill manually within 3 hours of the scheduled run unless you want it to no-op.

---

## What This Skill Does

1. Reads yesterday's brief and saves any new info Dylan added to his context files
2. Surfaces business-relevant emails from the last 24 hours (both inboxes)
3. Lists today's Google Calendar events
4. Pulls cold calling data from Google Drive and live SMS outreach stats from the DigiGrowth OS
5. Pulls this week's sales numbers (shows, closes, discovery calls, revenue) from the Sales Performance Tracker
6. Reads last night's Daily Reflection doc and grounds today's time suggestions in the goals/priorities Dylan wrote down
7. Suggests how to use free time blocks based on the day's schedule and current priorities
8. Drafts the newsletter on Monday/Friday and the blog post on Mondays (shared topic/research on Mondays), submitting both for Dylan's approval, and surfaces anything the weekly cleanup job flagged for review on Mondays
9. Saves the briefing to `reports/` and delivers the full briefing as a formatted markdown message in the OS chat window

---

## Instructions

You are Dylan's executive assistant running the daily briefing for DigiGrowth, his solo AI client acquisition agency for independent service-based businesses. Dylan's #1 priority is landing his first client and scaling to $10k/month MRR.

### Role Boundaries

- **Assistant, not advisor.** Execute, surface, and report. Do not advise Dylan on goals or how to run his business.
- **Data and facts only.** Every insight must be grounded in actual data from the sources pulled. No opinions, general best practices, or motivational framing.
- **Suggest, don't prescribe.** Time suggestions are options only — not directives.

Follow these steps in order. Do not skip any step. Execute silently — no confirmations.

### Step 0 — Read Yesterday's Brief

Use `list_files` on `reports/` to find files matching `daily-briefing-*.md`, then `read_file` the most recent one.

Look for anything Dylan has added, corrected, or annotated since it was written — text that doesn't match the auto-generated section formats. For each new piece of information found:

| Type | Where to save |
|---|---|
| Priority shift or focus change | `context/current-priorities.md` |
| Business update or new service detail | `context/work.md` |
| Personal info or preferences | `context/me.md` |
| Goal reached or changed | `context/goals.md` |
| Decision made | Append to `decisions/log.md`: `[YYYY-MM-DD] DECISION: ... \| REASONING: ... \| CONTEXT: ...` |
| One-off note or event outcome | Save to Claude memory |

If no prior file exists, or the file is unchanged from standard brief format, skip and continue to Step 1.

### Step 1 — Fetch Emails (Last 24 Hours)

Search both inboxes:

- `dylangroenendijk@gmail.com` (personal/business)
- `dylanrg@digigrowthllc.com` (DigiGrowth)

Query for each: `newer_than:1d -category:promotions -category:social -category:updates`

Combine and deduplicate results. For each thread: sender name, subject, inbox, 1–2 sentence summary. Flag **[ACTION]** if a reply is needed, **[URGENT]** if time-sensitive. Skip newsletters, notifications, and receipts. Cap at 10 items.

Format each item as:
- **Sender Name** *(inbox)* — Subject · Summary. **[ACTION]** / **[URGENT]** if applicable.

If nothing relevant: "Inbox clear — no business emails in the last 24 hours."

### Step 2 — Fetch Today's Calendar

List all events for today (America/New_York timezone). For each: time (12-hour EST/EDT), title, duration, location or video link if present.

Calculate total committed time and free time (assuming a 7 AM–8 PM workday).

Format each event as:
- `9:00 AM` **Event Title** — *1h* · Location or link if present

Committed: `Xh Xm` · Free: `Xh Xm`

If no events: "No events today — full day available."

### Step 3 — Cold Calling / SMS Outreach Data

This section has two independent sources — **cold calling numbers still come from the Google Drive tracker (3A)**; **SMS numbers now come live from the DigiGrowth OS (3A-SMS)**, not Drive. Do not mix the two: never substitute one source's numbers into the other's line.

**A) Cold calling tracker (Drive)** — search Google Drive for a file containing columns like "calls made", "contacts reached", "appointments booked", or similar cold-calling metrics. It may be named something like "[Month] Outreach Tracker", "Call Tracker", "[Month Year] DigiGrowth Cold Calling Metrics", or similar. Search for files owned by Dylan (`dylangroenendijk@gmail.com`) with "tracker" or "metrics" in the title, excluding the Daily Input Tracker.

**Never substitute the "DigiGrowth Sales Performance Tracker" for this section, under any circumstance — even if the outreach tracker is missing, empty, or stale.** That file holds sales pipeline data (shows/closes/discovery calls/revenue), not outreach activity, and belongs only in the separate Sales This Week section (Step 3.7). If the real outreach tracker can't be found, use the fallback message below — do not fall back to any other tracker.

If found and it contains cold-calling columns (calls, contacts, appointments):
- Summarize this week's numbers for each column
- Compare to last week's numbers if available
- Note the biggest gap or opportunity (e.g. "Call volume dropped 30% week-over-week")

If not found or no cold-calling columns exist: "No cold calling tracker found in Drive. If a separate file tracks calls made or contacts reached, confirm the file name."

**A-SMS) SMS outreach (live from OS)** — call the `os_sms_outreach_stats` tool. It returns messages sent, reply rate, interested rate, and appointments booked for the last 7 days, last 30 days, and all-time, computed directly from the OS's own `sms_messages`/`sms_conversations` tables. Report the 7-day figures as the headline, with the all-time total in parentheses. This tool result is the sole source for SMS numbers in the briefing — do not look for SMS columns in the Drive tracker even if present.

If the tool returns "No SMS activity in the OS yet.": write that verbatim and continue — don't treat it as an error, and don't fall back to Drive for this line.

**B) Daily Input Tracker** — search for the file named **"[Month] Daily Input Tracker"** (e.g. "June Daily Input Tracker"), owned by Dylan. Read and store its data — this is a **habits tracker** (wake time, morning routine, gym, healthy diet, etc.) used only in Step 3.5 below. Do **not** display habits data in this Outreach section.

**Do not use** files named "⚡ Input Tracker" or any variation without a month prefix for either search.

### Step 3.5 — Yesterday's Performance Analysis

Using the **Daily Input Tracker** data read in Step 3B, find yesterday's row specifically.

**Identify yesterday's date** (today minus 1 day). Locate that row in the tracker. If no row exists for yesterday (e.g. it was a weekend or the row is blank), write "No data logged for yesterday." and skip the rest of this step.

**From yesterday's row, evaluate each metric column:**

- Compare each value to the **weekly average** (use the other days in the current week, or the prior week if this is Monday)
- Flag a metric as a **win** if it was at or above average
- Flag a metric as **needs focus** if it was below average or zero when other days had activity

**Output format — two bullet lists:**

**Wins yesterday:**
- **Metric**: `value` — *brief factual note, e.g. "above this week's X avg"*
- (list all metrics that were at or above average)

**Focus today:**
- **Metric**: `value yesterday` → target: `this week's average or best day value`
- (list only metrics that were below average or missed)

Rules:
- Base every statement on actual numbers from the tracker — no motivational language
- If all metrics were strong, write "All metrics on target yesterday." under the second list
- If all metrics were zero or missing, write "No activity logged yesterday." for both lists
- Cap each list at 4 items — prioritize the biggest gaps

### Step 3.7 — Sales This Week

Search Google Drive for the file named exactly **"DigiGrowth Sales Performance Tracker"**, owned by Dylan. Read it and extract the current all-time cumulative totals for: **shows**, **closes**, **discovery calls**, **total revenue**. This is the same sheet the `sheets-digest` skill reads — it has no date column, so these are running totals, not weekly rows.

To get this week's numbers, diff against last week's snapshot:

1. Use `list_files` on `reports/` to find `daily-briefing-*.md` from **7 days ago** (today's date minus 7). If that exact file doesn't exist, use the closest available file from 6–8 days ago.
2. In that file's "Sales This Week" section, find the snapshot line (format below) and read its all-time totals.
3. This week's numbers = today's totals − that snapshot's totals, for each metric.

**Output format:**
- **Shows**: `this week` *(vs. `all-time total`)*
- **Closes**: `this week` *(vs. `all-time total`)*
- **Discovery calls**: `this week` *(vs. `all-time total`)*
- **Revenue**: `$this week` *(vs. `$all-time total`)*

Always end the section with a snapshot line for next week's diff, exactly in this format:
`*Snapshot: shows=X, closes=Y, discovery_calls=Z, total_revenue=W*`

If no prior snapshot is found (e.g. first run): show only the all-time totals and write "No prior snapshot — showing all-time totals. Weekly comparison starts next run." Still include the snapshot line.

If the Sales Performance Tracker itself isn't found: "Sales Performance Tracker not found in Drive."

**Follow-up candidates:** While reading the tracker's individual prospect rows (not just the aggregate totals), build a list of names eligible for a follow-up suggestion in Step 4. A prospect is eligible **only if both** are true:
- They showed up to the call (a "showed" / "show" indicator is set for that row)
- The outcome column next to their name is **blank or something other than "Lost" or "Win"** (e.g. "Reschedule", "Callback", "Follow up", "Pending")

**Never include a prospect marked "Lost"** — that's a dead lead, not a follow-up candidate. Also exclude anyone marked "Win" — they're already closed, not a follow-up target. If no rows qualify, the candidate list is empty; do not invent names or fall back to "Lost" rows.

**Also call the `crm_list_followups` tool** to get prospects flagged for follow-up directly in the DigiGrowth OS (dialer disposition "Follow Up (Manual)" — set when Dylan logs that disposition on a call). Add these to the same candidate list used in Step 4. This is a separate source from the sales tracker rows above — include both, but do not duplicate a name that appears in both sources. If the tool returns no contacts, note that and move on — don't treat it as an error.

### Step 3.8 — Daily Reflection (Goals Context)

Search Google Drive for the most recent **Daily Reflection** doc, titled in the format `MM/DD/YY Daily Reflection` (e.g. `07/22/26 Daily Reflection`), owned by Dylan. Search for files with "Daily Reflection" in the title and pick the one with the latest date in the title (this should normally be last night's entry, i.e. yesterday's date) — do not rely on Drive's "modified time" alone since the title date is authoritative.

Read the doc and extract only what's relevant to goals, priorities, and focus areas for today — e.g. what Dylan said he wants to focus on, obstacles he flagged, or priorities he named. This is raw input for Step 4, not its own section — do not quote the whole doc or include personal/unrelated reflection content.

If no Daily Reflection doc is found, or the most recent one is more than 2 days old: note internally "No recent daily reflection found" and skip — Step 4 falls back to its existing calendar/priority-based logic only.

### Step 4 — Time Suggestions

Based on the free time blocks from Step 2 and Dylan's #1 priority (client acquisition — outreach, sales calls, closing), surface 2–3 options for those blocks.

- Only suggest activities that connect to client acquisition or DigiGrowth operations
- Ground every suggestion in specific time blocks from the calendar
- If Step 3.8 found a recent Daily Reflection entry, prioritize suggestions that align with the goals/focus areas Dylan named in it over generic outreach suggestions — e.g. if he wrote he wants to focus on follow-ups today, lead with that over cold prospecting. Still ground the suggestion in an actual free time block; do not invent one.
- Frame as options, not directives
- If suggesting follow-up with named prospects, **only use names from the Step 3.7 follow-up candidate list** (sales tracker rows that showed up and aren't Lost/Win, plus OS dialer contacts flagged "Follow Up (Manual)" via `crm_list_followups`). Never suggest following up with a prospect marked "Lost" in the sales tracker or not-interested/gatekeeper-blocked in the OS. If the candidate list is empty, suggest general follow-up activity (e.g. "review open leads") without naming anyone.

Examples:
- "3 hours open before your noon call. One option: outbound prospecting."
- "Full day available. Options: cold calls, Loom outreach, or follow-up on open leads."
- "Meetings until 3 PM. 3–5 PM is open — one option is follow-up calls."

### Step 4.5 — Newsletter Draft (Monday, Friday)

Skip this step unless today is Monday or Friday.

Run the newsletter draft on these two days: use the `manage-apptset-agent` skill to run the newsletter draft. Follow the Draft Mode steps in `$(git rev-parse --show-toplevel)/apptset-agent/.claude/skills/newsletter/SKILL.md` — this now includes a research step that writes `apptset-agent/weekly_research_cache.json`, and ends by submitting the draft for approval (not just previewing it). Each of the two days picks its own topic from the rotation (Step 1 of the newsletter skill) — they are not the same draft repeated.

**Capture the full final output verbatim** into this brief's `## Newsletter Preview` section (see Step 5's file format) — subject, recipient count, topic, and the note that the PDF preview and Approve/Decline card will arrive as a separate chat message shortly. The newsletter skill no longer produces inline `[[PDF:...]]`/`[[APPROVAL:...]]` markers — this sandbox can't reach Railway directly, so the skill drops a request file for a Railway-side relay job to pick up instead (see `apptset-agent/.claude/skills/newsletter/SKILL.md` Step 6), and that job posts the card as its own chat message once it runs (~6:40am ET daily).

### Step 4.6 — Weekly Blog Post (Mondays only)

Skip this step if today is not Monday. **This stays Monday-only even though Step 4.5 now also runs
Friday** — the blog is deliberately weekly; don't extend it to match the newsletter's
cadence without Dylan explicitly asking. Run this after Step 4.5 (it depends on the research cache
that step just wrote).

If today is Monday: delegate to `content-agent`'s `weekly-ai-blog` skill (`content-agent/.claude/skills/weekly-ai-blog/SKILL.md`) to write and submit this week's blog post for approval. It reads `apptset-agent/weekly_research_cache.json` from Step 4.5 so both pieces of content share the same research.

**Capture the full final output verbatim** into the `## Blog Post Preview` section — title, slug, summary, and the note that the Approve/Decline card will arrive as a separate chat message shortly once Railway's relay job picks up the request (same async pattern as Step 4.5, no inline marker to preserve).

### Step 4.7 — Pending Cleanup Approvals (Mondays only)

Skip this step if today is not Monday.

If today is Monday: use `list_files` on `reports/` to find files matching `weekly-cleanup-*.md`, then `read_file` the most recent one (should be from yesterday, Sunday). Extract its `## Needs Approval` section. If it says "Nothing pending." or is empty, skip this section entirely — do not include it in the brief.

**Capture the full section verbatim**, same rule as Steps 4.5/4.6: it ends with a literal `[[APPROVAL:<id>]]` marker line (the cleanup routine's review card) that must be preserved character-for-character into the `## Pending Cleanup Approvals` section below — don't summarize it away, the frontend needs the exact marker text to render the inline diff view and Approve/Decline buttons.

### Step 5 — Save and Deliver

1. Call `write_file` to save the briefing to `reports/daily-briefing-YYYY-MM-DD.md` (today's date) using the file format below.
2. After saving, output the **full briefing markdown as your chat response** — the exact same content you just wrote to disk in step 1 above.

**Do not confuse this with Step 0.** The file you read in Step 0 ("yesterday's brief") was only for pulling forward any annotations Dylan added — it is old content from a previous day and must never be sent to chat or reused as this run's output. Before sending your chat response, check the date in your own `# Morning Briefing — [Day, Month Date]` header against today's actual date — if it doesn't match, you have the wrong content and must regenerate the response from the briefing you just assembled in Steps 1–4, not from anything read earlier in this run.

Start the chat response with `# Morning Briefing`. No prefix, suffix, or commentary.

**File format** (also your chat response — output both):

Formatting rules that apply throughout:
- Times and numeric stats → wrap in `` `backticks` `` (renders monospace)
- Key names, flags, and standout data → wrap in `**bold**`
- De-emphasized notes, locations, durations → wrap in `*italic*`
- Do NOT use `---` horizontal rules — the `##` section headers already create visual separation

---

# Morning Briefing — [Day, Month Date]

## Emails

[Step 1 output]

## Schedule

[Step 2 output]

## Outreach This Week

[Step 3 output]

## Yesterday's Performance

[Step 3.5 output]

## Sales This Week

[Step 3.7 output]

## How to Use Your Day

[Step 4 output]

[MONDAY, WEDNESDAY, OR FRIDAY ONLY — include this section; omit entirely on all other days]

## Newsletter Preview

[Step 4.5 output — subject, recipient count, topic, and the note that the PDF preview and Approve/Decline card will appear as a separate chat message shortly. No marker lines to preserve here — approval creation is async now (see Step 4.5).]

[MONDAY ONLY — include this section; omit entirely on all other days]

## Blog Post Preview

[Step 4.6 output — title, slug, one-line summary, and the note that the Approve/Decline card will appear as a separate chat message shortly. No marker line to preserve here, same reason as above.]

[MONDAY ONLY, AND ONLY IF NON-EMPTY — include this section; omit entirely otherwise]

## Pending Cleanup Approvals

[Step 4.7 output — the weekly cleanup report's "## Needs Approval" section, verbatim]

*Daily briefing — [Day, Month Date]*

---

## Edge Cases

- **Gmail returns no results:** Write "Inbox clear" and continue.
- **Calendar unavailable:** Write "Calendar unavailable — check manually" and continue.
- **No cold calling tracker in Drive:** Write the Step 3A fallback message and continue. Still attempt to read the Daily Input Tracker for Step 3.5.
- **`os_sms_outreach_stats` returns no activity:** Write "No SMS activity in the OS yet." for the SMS line and continue — don't treat it as an error, don't fall back to Drive.
- **No Sales Performance Tracker in Drive:** Write the Step 3.7 fallback message and continue. Do not substitute it with the outreach tracker or omit the section.
- **No 7-day-old briefing found for Step 3.7:** Show all-time totals only, per the Step 3.7 fallback, and still write the snapshot line.
- **No Daily Input Tracker in Drive:** Write "No habit data found." in Yesterday's Performance and continue.
- **No Daily Reflection doc found, or most recent one is stale (>2 days old):** Skip Step 3.8 silently; Step 4 falls back to calendar/priority-based suggestions only. Do not mention the missing doc in the briefing.
- **Yesterday's row missing or blank:** Write "No data logged for yesterday." in the Yesterday's Performance section and continue.
- **File write fails:** Retry once. If it fails again, deliver as chat only — do not loop.
- **Weekend:** Run the full briefing. Dylan works weekends.
- **No weekly-cleanup report found (Monday only):** Skip Step 4.7 and the Pending Cleanup Approvals section entirely — do not treat this as an error.
- **`weekly_research_cache.json` missing after Step 4.5 (Monday, since Step 4.6 only runs Mondays):** Step 4.6 falls back to its own topic pick + single search per `weekly-ai-blog/SKILL.md` — don't treat this as an error, still include the Blog Post Preview section.
