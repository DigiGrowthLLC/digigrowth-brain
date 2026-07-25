# Skill: Sheets Digest

**Trigger:** Weekdays at 5:57 AM ET (cloud trigger `EA Sheets Digest`, runs ~6 min before daily-briefing), or on-demand
**Purpose:** Read Dylan's two target sheet types, extract outreach and sales metrics, and write them period-bucketed into the OS via `update_os_stats`.
**Duplicate guard:** Before doing any work, the trigger checks git log for a same-day digest report committed in the last 3 hours — if found, it exits silently. Never re-run this skill manually within 3 hours of the scheduled run unless you want it to no-op.

---

## Steps

1. Call `drive_search` with query `"DigiGrowth Sales Performance Tracker"` — get the Sales Performance Tracker. Always read this file.
2. Call `drive_list_recent` with `days=1, max_results=20` — get files modified in the last 24 hours.
3. From the recent list, **only keep** files whose name matches **exactly** `[Month Year] DigiGrowth Cold Calling Metrics` (e.g. "June 2026 DigiGrowth Cold Calling Metrics"). **Discard every other file** — do not read habit trackers, input trackers, goal trackers, lead lists, financial trackers, DM trackers, SMS trackers, or any file not matching that exact pattern.
4. Call `drive_read_file` on: (a) the Sales Performance Tracker, and (b) any Cold Calling Metrics file from step 3 only.
5. Both the Sales Performance Tracker and each Cold Calling Metrics file have a date column. For each, calculate three totals per metric using that date column:
   - **7D**: sum rows where date is within last 7 days
   - **30D**: sum rows where date is within last 30 days
   - **All-time**: sum all rows
6. Call `update_os_stats` with all found values — **always call it, even if nothing changed**
7. Save the completion report to `reports/sheets-digest-YYYY-MM-DD.md` where YYYY-MM-DD is today's **full 4-digit year** date from the system prompt (e.g. 2026-06-12, never 2025).
8. End with the completion message.

**Only use `drive_search`, `drive_list_recent`, `drive_read_file`, and `update_os_stats`. No other tools.**

**Period calculation rules:**
- Today's date is in the system prompt. Use the full year (e.g. 2026) — never default to 2025.
- Pass period fields separately: `calls_made` (all-time), `calls_made_30d`, `calls_made_7d` — never merge them. Same pattern for the sales funnel: `shows`, `shows_30d`, `shows_7d`, etc.

---

## Target Sheets

| Sheet | When to read | What it holds |
|---|---|---|
| `DigiGrowth Sales Performance Tracker` | Always — search by name | shows, closes, discovery_calls, total_revenue (has a date column — bucket by period) |
| `[Month Year] DigiGrowth Cold Calling Metrics` | Only if opened in last 24h | calls_made, calls_answered, contacts_reached, appointments_booked, resonations |

**Ignore everything else** — habit trackers, goal trackers, lead lists, input trackers, etc.

---

## Data Mapping

| What to look for in sheet | Tool field | Period variants |
|---|---|---|
| Calls made / dials | `calls_made` | `calls_made_7d`, `calls_made_30d` |
| **Calls answered** (exact column name) | `calls_answered` | `calls_answered_7d`, `calls_answered_30d` |
| Contacts reached / pitched / **"DM's Reached"** column (same metric the sheet's own Totals row calls "Pitches") | `contacts_reached` | `contacts_reached_7d`, `contacts_reached_30d` |
| **Resonations** column (per-row count of prospects who resonated with the pitch) | `resonations` | `resonations_7d`, `resonations_30d` |
| Appointments booked / bookings | `appointments_booked` | `appointments_booked_7d`, `appointments_booked_30d` |
| Shows / showed up | `shows` | `shows_7d`, `shows_30d` |
| Closes / won / signed | `closes` | `closes_7d`, `closes_30d` |
| Discovery calls / booked calls | `discovery_calls` | `discovery_calls_7d`, `discovery_calls_30d` |
| Revenue | `total_revenue` | `total_revenue_7d`, `total_revenue_30d` |

**`calls_answered`, `contacts_reached`, and `resonations` are SEPARATE fields — never merge them.**
- `calls_answered` = raw pickups (the "Calls answered" column)
- `contacts_reached` = people actually spoken to and pitched — the sheet's own KPI panel calls this "Pitches" (used for Pitch Rate = contacts_reached ÷ calls_made)
- `resonations` = the "Resonations" column — prospects who responded positively to the pitch (used for Resonation Rate = resonations ÷ contacts_reached)

---

## Completion Message

```
Sheets Digest complete — YYYY-MM-DD
Updated: [fields written, e.g. "calls_made=45, calls_answered=12, contacts_reached=8"]
Source: [sheet names and period covered]
```

If no cold calling sheet was opened in the last 24h:
```
Sheets Digest complete — YYYY-MM-DD
No cold calling sheet opened today. Sales tracker updated only.
Updated: [sales fields]
```
