# Skill: Sheets Digest

**Trigger:** Daily at 6AM EST (in parallel with daily-briefing), or on-demand
**Purpose:** Read every Google Sheet opened or modified in the last 7 days, extract outreach and sales metrics, and write them into the OS via `update_os_stats`.

---

## Steps

1. Call `drive_list_recent` with `days=7, max_results=30` — get all files active in the last 7 days
2. Filter the result to spreadsheets only (`application/vnd.google-apps.spreadsheet`)
3. Call `drive_read_file` on **every** spreadsheet in the list — do not skip any
4. For each sheet, scan all columns and rows for the metrics below
5. Compile values across all sheets — if the same metric appears in multiple sheets, use the most complete/recent number
6. Call `update_os_stats` with all found values — **always call it, even if nothing changed**
7. End with the completion message

**Only use `drive_list_recent`, `drive_read_file`, and `update_os_stats`. No other tools.**

---

## Known Sheets (check these first)

Dylan's key sheets — if found in the list, always read them:

| Sheet name contains | What it holds |
|---|---|
| `Cold Calling` / `cold calling` / `Cold Calling Metrics` | calls_made, calls_answered, contacts_reached, appointments_booked |
| `Sales Performance` / `Sales Tracker` | shows, closes, discovery_calls, total_revenue |
| `Input Tracker` / `Daily Input` | calls_made, contacts_reached, appointments_booked, sms_sent |
| `Goal Tracker` | context only — no stats to extract |

---

## Data Mapping

Be liberal — column names vary. Match on intent, not exact wording.

| What to look for | Tool field | Where it shows |
|---|---|---|
| Calls made / dials / outbound calls / calls placed | `calls_made` | Analytics · Input Tracker |
| **Calls answered** / answered / pickups / live answers | `calls_answered` | Analytics · Funnel (Answered stage) |
| Contacts reached / pitched / spoken to / stayed on line | `contacts_reached` | Analytics · Input Tracker + Funnel (Pitched stage) |
| Appointments booked / intro sessions / bookings | `appointments_booked` | Analytics · Input Tracker |
| SMS sent / texts sent / messages sent | `sms_sent` | Analytics · Input Tracker |
| Shows / showed up / showed / prospects who attended | `shows` | Sales Statistics · Daily Scoreboard |
| Closes / won / signed / clients closed | `closes` | Sales Statistics · Funnel |
| Revenue / MRR / collected / payments | `total_revenue` | Sales Statistics |
| Discovery calls / intro calls / first calls completed | `discovery_calls` | Sales Statistics |
| Strategy sessions / deep dives / follow-up calls | `strategy_sessions` | Sales Statistics |

**IMPORTANT — `calls_answered` vs `contacts_reached` are separate fields:**
- `calls_answered` = the "Calls answered" column — raw pickups (someone picked up the phone). Always pass this as its own field.
- `contacts_reached` = contacts actually spoken to / pitched (may be a different column). Do NOT merge these two into one.
- If you only find one of these columns, pass only that one — never substitute one for the other.

**Rules:**
- Outreach fields (calls, contacts, appointments, SMS): sum all months/rows for all-time totals
- Sales funnel fields (shows, closes, revenue): cumulative all-time totals only
- Never default to zero — only write a field if you found real data for it
- If data is from a past period with nothing recent, still include it with a note in `source_note`

---

## Completion Message

```
Sheets Digest complete — YYYY-MM-DD
Updated: [every field written, e.g. "calls_made=312, contacts_reached=45, shows=9"]
Source: [sheet name(s) and period covered]
```

If no data found:
```
Sheets Digest complete — YYYY-MM-DD
No metrics found. OS stats unchanged.
Sheets scanned: [list names]
```
