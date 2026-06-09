# Skill: Sheets Digest

**Trigger:** Daily at 6AM EST, or on-demand
**Parallel execution:** Runs concurrently with `daily-briefing` at 6AM EST — both fire as separate agent requests at the same time.
**Purpose:** Scan Google Sheets opened in the last 24 hours. Extract raw stats. Write a dated report file. Nothing else.

---

## What This Skill Does

1. `drive_list_recent` — get recently accessed files
2. Filter to `application/vnd.google-apps.spreadsheet` only
3. Filter to files accessed within the last 24 hours
4. `drive_read_file` each qualifying sheet — read raw numbers
5. `write_file` a dated stats block to `reports/sheets-digest-YYYY-MM-DD.md`
6. End your response with the completion message below — exactly as formatted

**Do not call Notion, Gmail, Calendar, or any other tool.**

---

## Output Format

Written to `reports/sheets-digest-YYYY-MM-DD.md`:

```
# Sheets Digest — YYYY-MM-DD

## [Sheet Name]
- [Label]: [Value]
- [Label]: [Value]

## [Sheet Name]
- [Label]: [Value]
```

Numbers and labels only. If no sheets were opened in last 24h:

```
# Sheets Digest — YYYY-MM-DD
_No sheets opened in the last 24 hours._
```

---

## Completion Message

After writing the report file, end your response with this exact line:

```
✓ Sheets Digest complete — YYYY-MM-DD. [N] sheet(s) scanned. Report saved to reports/sheets-digest-YYYY-MM-DD.md.
```

Replace `YYYY-MM-DD` with today's date and `[N]` with the number of sheets scanned (0 if none).

---

## Invocation

> "Run the sheets digest"
> "Pull my sheets stats"
> "What do my sheets say today?"
