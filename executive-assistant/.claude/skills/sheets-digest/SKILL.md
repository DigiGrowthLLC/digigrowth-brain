# Skill: Sheets Digest

**Trigger:** Daily at 6AM EST (in parallel with daily-briefing), or on-demand
**Purpose:** Read Dylan's two target sheet types, extract outreach and sales metrics, and write them period-bucketed into the OS via `update_os_stats`.

---

## Steps

1. Call `drive_search` with query `"DigiGrowth Sales Performance Tracker"` — get the Sales Performance Tracker (always read this regardless of when it was last opened)
2. Call `drive_list_recent` with `days=1, max_results=20` — get files opened or modified in the last 24 hours
3. From the recent list, keep only spreadsheets whose name matches the pattern **`[Month Year] DigiGrowth Cold Calling Metrics`** (e.g. "June 2026 DigiGrowth Cold Calling Metrics"). Ignore all other files.
4. Call `drive_read_file` on the Sales Performance Tracker + any matching Cold Calling Metrics sheets from step 3
5. For each Cold Calling sheet, calculate three totals per metric using the date column:
   - **7D**: sum rows where date is within last 7 days
   - **30D**: sum rows where date is within last 30 days
   - **All-time**: sum all rows
6. Call `update_os_stats` with all found values — **always call it, even if nothing changed**
7. End with the completion message

**Only use `drive_search`, `drive_list_recent`, `drive_read_file`, and `update_os_stats`. No other tools.**

**Period calculation rules:**
- Today's date is in the system prompt. Use it to determine what falls within 7 and 30 days.
- The Sales Performance Tracker has no date column — its data goes to all-time fields only.
- Pass period fields separately: `calls_made` (all-time), `calls_made_30d`, `calls_made_7d` — never merge them.

---

## Target Sheets

| Sheet | When to read | What it holds |
|---|---|---|
| `DigiGrowth Sales Performance Tracker` | Always — search by name | shows, closes, discovery_calls, total_revenue |
| `[Month Year] DigiGrowth Cold Calling Metrics` | Only if opened in last 24h | calls_made, calls_answered, contacts_reached, appointments_booked |

**Ignore everything else** — habit trackers, goal trackers, lead lists, input trackers, etc.

---

## Data Mapping

| What to look for in sheet | Tool field | Period variants |
|---|---|---|
| Calls made / dials | `calls_made` | `calls_made_7d`, `calls_made_30d` |
| **Calls answered** (exact column name) | `calls_answered` | `calls_answered_7d`, `calls_answered_30d` |
| Contacts reached / pitched | `contacts_reached` | `contacts_reached_7d`, `contacts_reached_30d` |
| Appointments booked / bookings | `appointments_booked` | `appointments_booked_7d`, `appointments_booked_30d` |
| Shows / showed up | `shows` | all-time only |
| Closes / won / signed | `closes` | all-time only |
| Discovery calls / booked calls | `discovery_calls` | all-time only |
| Revenue | `total_revenue` | all-time only |

**`calls_answered` and `contacts_reached` are SEPARATE fields — never merge them.**
- `calls_answered` = raw pickups (the "Calls answered" column)
- `contacts_reached` = people actually spoken to and pitched

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
