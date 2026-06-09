# Skill: Sheets Digest

**Trigger:** Daily at 6AM EST (in parallel with daily-briefing), or on-demand
**Purpose:** Read recent Google Sheets, identify sales and outreach metrics, and write them into the OS Dashboard and Analytics panel stat categories.

---

## What This Skill Does

1. Pull recent Drive files — `drive_list_recent`
2. Filter to spreadsheets only (`application/vnd.google-apps.spreadsheet`)
3. Read each sheet — `drive_read_file`
4. Analyze the content: identify any data related to calls, appointments, shows, closes, revenue, discovery calls, or strategy sessions
5. Map what you find to OS stat categories (see mapping below)
6. Call `update_os_stats` with the extracted values
7. End your response with a confirmation of what was updated

**Do not call Notion, Gmail, Calendar, or any other tool.**

---

## Data Mapping

When reading sheets, look for these types of data and map them as follows:

| What you find in the sheet | OS field | Where it appears in the OS |
|---|---|---|
| Shows / prospects who showed up | `shows` | Sales Statistics · Daily Scoreboard |
| Closes / deals signed / clients won | `closes` | Sales Statistics · Daily Scoreboard · Funnel |
| Total revenue / MRR / payments collected | `total_revenue` | Sales Statistics |
| Discovery calls / intro calls completed | `discovery_calls` | Sales Statistics |
| Strategy sessions / deep dives | `strategy_sessions` | Sales Statistics |
| Average deal value | `avg_deal_size` | Sales Statistics |

**Rules:**
- Use **cumulative all-time totals** — not daily increments — unless the sheet clearly tracks a single day only
- Only include fields where you found actual data. Do not guess or assume zeros.
- If a sheet tracks weekly or monthly data, use the most recent period's cumulative total
- If two sheets have conflicting numbers for the same metric, use the sheet that appears to be the primary tracker (more complete, more recent, or explicitly labeled as a tracker)

---

## Completion Message

End your response with:

```
✓ Sheets Digest complete — YYYY-MM-DD
Updated: [list the fields you wrote, e.g. "shows=2, closes=1, total_revenue=1500"]
Source: [sheet name(s) the data came from]
Visible in: Sales Statistics · Daily Scoreboard
```

If no relevant data was found in any sheet:

```
✓ Sheets Digest complete — YYYY-MM-DD
No sales or outreach metrics found in recent sheets. OS stats unchanged.
```

---

## Invocation

> "Run the sheets digest"
> "Sync my sheets to the OS"
> "Pull my stats from sheets"
