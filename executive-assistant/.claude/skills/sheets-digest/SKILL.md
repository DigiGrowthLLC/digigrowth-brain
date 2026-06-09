# Skill: sheets-digest

## Purpose
Scan Google Sheets opened in the last 24 hours. Write the stats to the OS dashboard and analytics page in Notion. Nothing else.

---

## Scope

| ✅ In scope | ❌ Out of scope |
|---|---|
| Sheets opened/modified in last 24h | Sheets outside the 24h window |
| Surface-level stats per sheet | Analysis, trends, or recommendations |
| Write stats block to Notion OS dashboard | Emails, notifications, or calendar events |
| Write stats block to Notion analytics page | Writing to local files or the decision log |

---

## Trigger
- **Daily** — run once per day
- **Manual** — "run sheets digest" or "update dashboard stats"

---

## Steps

### 1. Fetch recently opened Sheets
```
drive_list_recent(max_results=20)
→ filter to mimeType: "application/vnd.google-apps.spreadsheet"
→ filter to files opened/modified within last 24h
```

### 2. Read each qualifying sheet
```
drive_read_file(file_id) for each sheet
→ extract: sheet name + any visible key numbers/totals
→ no analysis — numbers and labels only
```

If no sheets qualify → skip to step 3, write the empty state message.

### 3. Update OS Dashboard (Notion)
```
notion_search("OS Dashboard")
→ append today's stats block to that page
```

### 4. Update Analytics Page (Notion)
```
notion_search("Analytics")
→ append the same stats block to that page
```

---

## Stats Block Format

```
## Sheets Digest — YYYY-MM-DD
- **[Sheet Name]**: [metric label]: [value] | [metric label]: [value]
- **[Sheet Name]**: [metric label]: [value]
```

If no sheets were opened in the last 24h:
```
## Sheets Digest — YYYY-MM-DD
_No sheets opened in the last 24 hours._
```

Numbers and labels only. No commentary, no flags, no action items.
