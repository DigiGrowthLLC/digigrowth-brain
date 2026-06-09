# Skill: Sheets Digest

**Trigger:** Daily at 6AM EST (in parallel with daily-briefing), or on-demand
**Purpose:** Read recent Google Sheets, extract any relevant outreach or sales metrics, and write them into the OS Dashboard and Analytics panel via `update_os_stats`. Always call `update_os_stats` with whatever you find — even if nothing changed since yesterday.

---

## Steps

1. `drive_list_recent` — get recently accessed files
2. Filter to `application/vnd.google-apps.spreadsheet` only
3. `drive_read_file` each sheet
4. For each sheet: scan all columns and rows for any of the metrics in the mapping table below
5. Compile the values across all sheets (use the most complete/recent numbers if multiple sheets have the same metric)
6. Call `update_os_stats` with everything you found — **always call it, even if the values are the same as last time**
7. End with the completion message

**Do not call Notion, Gmail, Calendar, or any other tool.**

---

## Data Mapping

Scan sheets for any data that matches these categories. Be liberal in interpretation — column names vary.

| What to look for in the sheet | Tool field | Where it shows in the OS |
|---|---|---|
| Calls made / dials / outbound calls | `calls_made` | Analytics · Input Tracker section |
| Contacts reached / answers / picked up | `contacts_reached` | Analytics · Input Tracker section |
| Appointments booked / intro sessions scheduled | `appointments_booked` | Analytics · Input Tracker section |
| SMS sent / texts sent | `sms_sent` | Analytics · Input Tracker section |
| Shows / prospects who showed up | `shows` | Sales Statistics · Daily Scoreboard |
| Closes / deals signed / clients won | `closes` | Sales Statistics · Daily Scoreboard · Funnel |
| Revenue / MRR / payments collected | `total_revenue` | Sales Statistics |
| Discovery calls / intro calls completed | `discovery_calls` | Sales Statistics |
| Strategy sessions / deep dives | `strategy_sessions` | Sales Statistics |

**Rules:**
- For **outreach fields** (calls, contacts, appointments, SMS): use the most recent period total you can find — weekly, monthly, or all available rows summed
- For **sales funnel fields** (shows, closes, revenue): use cumulative all-time totals
- Only include fields where real data exists — do not guess or default to zero
- If data is clearly from a past period only (nothing recent), still report it with a note in `source_note`

---

## Completion Message

```
✓ Sheets Digest complete — YYYY-MM-DD
Updated: [list every field written, e.g. "calls_made=45, contacts_reached=8, appointments_booked=2"]
Source: [sheet name(s) and period covered]
Visible in: [relevant OS sections]
```

If no data at all was found:
```
✓ Sheets Digest complete — YYYY-MM-DD
No metrics found in recent sheets. OS stats unchanged.
Sheets scanned: [list names]
```

---

## Invocation

> "Run the sheets digest"
> "Sync my sheets to the OS"
> "Pull my stats from sheets"
