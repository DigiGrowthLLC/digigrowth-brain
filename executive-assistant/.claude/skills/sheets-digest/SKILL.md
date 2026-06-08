# Skill: Sheets Digest

**Trigger:** Daily (recommended: same time as daily-briefing, e.g. 6AM EST) or on-demand
**Purpose:** Scan all Google Sheets opened/modified in the last 24 hours, extract DigiGrowth-relevant stats, and write them back to the OS (context files, decision log, or a dedicated stats file).

---

## What This Skill Does

1. **Discovers** recently active Google Sheets via Google Drive (modified in last 24hrs)
2. **Reads** each sheet for DigiGrowth-relevant data (see: Stat Categories below)
3. **Extracts** key numbers and summarizes them
4. **Writes** the stats to `context/digigrowth-stats.md` (auto-created/updated)
5. **Flags** anything notable — spikes, drops, missing data, action items

---

## Stat Categories to Look For

When scanning sheets, look for any of these DigiGrowth KPIs:

### Outreach & Sales
- Calls made / answered / booked
- Follow-ups sent / completed
- Leads contacted (total, today, this week)
- Conversations started
- Demo / discovery calls scheduled
- Proposals sent
- Closes / signed clients

### Pipeline
- Leads in pipeline (by stage if available)
- Lead source breakdown
- Cold leads / warm leads / hot leads counts

### Ad Performance (Meta)
- Ad spend (daily / total)
- Impressions / reach
- Click-through rate (CTR)
- Cost per lead (CPL)
- Leads generated

### Client Delivery (once clients exist)
- Intro sessions booked per client
- Show rate
- Consultations completed

### Revenue
- MRR (current)
- Target vs. actual
- Invoices sent / paid / outstanding

---

## Execution Steps

```
1. Call Google Drive API — list files where:
   - mimeType = 'application/vnd.google-apps.spreadsheet'
   - modifiedTime > now - 24h

2. For each sheet returned:
   a. Open via Google Sheets API
   b. Read all tabs / visible data
   c. Match against Stat Categories above
   d. Extract values with labels and tab/cell references

3. Compile into a structured summary (see Output Format below)

4. Write summary to context/digigrowth-stats.md (overwrite with latest)

5. If any stat is missing expected data or shows a significant change:
   - Surface it as a FLAG in the summary
   - Optionally append a note to decisions/log.md if a threshold is crossed
```

---

## Output Format

Written to `context/digigrowth-stats.md`:

```markdown
# DigiGrowth Stats Snapshot
*Last updated: [YYYY-MM-DD HH:MM] EST*
*Source sheets: [list of sheet names scanned]*

## Outreach
- Calls made today: X
- Follow-ups sent: X
- Leads in pipeline: X

## Pipeline
- ...

## Ads
- ...

## Revenue
- MRR: $X / $10,000 target

## Flags 🚩
- [Any anomalies, gaps, or action items]

## Raw Sheet References
- [Sheet name] → [Tab] → [Stat]: [Value]
```

---

## Invocation

**On-demand:**
> "Run the sheets digest"
> "Pull my DigiGrowth stats from sheets"
> "What do my sheets say today?"

**Daily automation:** Pair with `daily-briefing` skill — append the stats snapshot to the morning email brief.

---

## Notes

- Skip sheets with no DigiGrowth-relevant data (personal finance, unrelated trackers, etc.)
- If a sheet is ambiguous, include it and flag it for Dylan to confirm relevance
- Over time, build a known-sheets registry in `context/known-sheets.md` to speed up scanning and avoid false positives
- GHL data must be exported to Sheets to be picked up here (no direct GHL MCP)
