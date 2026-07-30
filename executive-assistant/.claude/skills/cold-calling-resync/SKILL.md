# Skill: Cold Calling Resync

**Trigger:** Mondays only, as step 5 of the `EA Sheets Digest` cloud routine (`trig_01XCzSFbvwm3Npsrwr3YmFHb`, runs weekdays at 5:57 AM ET) — not its own standalone cloud trigger. That routine's guard already prevents same-day double-runs, and this add-on only fires when the weekday check resolves to Monday. Can also be run on-demand.
**Purpose:** Keep `copy-agent/.claude/skills/cold-calling-script/references/insights.md` current by pulling anything new since the last run from three sources — Google Drive cold-calling docs, this month's Cold Calling Metrics sheet, and the DigiGrowth OS dialer DB — and appending a short delta to its Update Log. Weekly, not daily, because call-review signal accumulates slower than sheet rows and daily runs would mostly be empty no-ops.
**Duplicate guard:** Inherited from the parent `EA Sheets Digest` run (its own guard already blocks same-day re-runs). If ever run standalone/manually, check `reports/` for a same-week `cold-calling-resync-*.md` already committed (within the last 3 days) before doing any work — if found, exit silently.

---

## Steps

1. Read `copy-agent/.claude/skills/cold-calling-script/references/insights.md` and note the `Last resync:` date near the top.
2. Call `drive_list_recent` with `days=8, max_results=30`. From the results, **only keep** files whose title matches one of these known cold-calling patterns — discard everything else (habit trackers, lead lists, unrelated docs):
   - `V.X Cold Calling Script` / `V.X Cold Calling Notes` (any version number)
   - `[Date] Cold Call Review` or `Cold Call Review`
   - `Weekly Cold Call & Outreach Analysis Log` (any date range)
   - `DigiGrowth Cold Call Rebuttal Vault`
   - `The DigiGrowth Sales Arsenal`
   - `Pre Cold Calling Playbook` / `Pre cold call playbook`
   - `Cold Calling Process`, `Cold Calling Critical Information`
   - Of these, **only read files whose `modifiedTime` is after the `Last resync` date** from step 1 — older matches are already reflected in the Baseline or a prior Update Log entry.
3. Call `drive_search` for `title contains 'DigiGrowth Cold Calling Metrics'`, find this calendar month's sheet (`[Month Year] DigiGrowth Cold Calling Metrics`), and read it if it exists. Extract this month's totals: calls made, pitches, resonations, appointments booked, and the booking rate (booked ÷ pitches).
4. Call `os_dialer_disposition_breakdown` — the OS dialer DB's own all-time disposition counts, independent of the Sheets tracker.
5. Call `os_dialer_recent_notes` with `limit=20` — the most recent calls that have free-text notes attached, i.e. live qualitative signal straight from logged calls.
6. **Synthesize a short delta — do not rewrite the file.** Compare what steps 2-5 found against the existing Baseline/Update Log in `insights.md`:
   - New or changed Drive docs: what's new, one sentence each.
   - This month's metrics: the current booking rate, and whether it's higher, lower, or roughly flat vs. the most recent number already in the doc (Baseline §7 or the latest Update Log entry).
   - OS dialer signal: anything the disposition breakdown or recent notes reveal that isn't already captured — a new recurring objection, a disposition pattern, a note worth flagging.
   - If nothing meaningfully new turned up in a given source, say so briefly rather than omitting it — the point is a trustworthy log, not padding.
7. Append the delta to `references/insights.md`'s `## Update Log` section, as a new entry at the **top** of the log (reverse-chronological), formatted:
   ```
   ### YYYY-MM-DD (automated resync)
   - **Drive:** ...
   - **Metrics:** ...
   - **OS dialer:** ...
   - **Changes the picture?** [yes/no — if yes, one sentence on what it supersedes or contradicts]
   ```
   Replace the `Last resync:` marker near the top of the file with today's date.
8. Save the completion report to `reports/cold-calling-resync-YYYY-MM-DD.md` (today's full 4-digit year — never default to 2025).
9. Commit the changes (both `insights.md` and the report) via git.
10. End with the completion message.

**Only use `drive_list_recent`, `drive_search`, `drive_read_file`, `os_dialer_disposition_breakdown`, `os_dialer_recent_notes`, `read_file`, and `write_file`. No other tools.**

---

## Edge Cases

- **No new Drive docs, flat metrics, no new OS signal:** still append an entry — just a short "nothing new this week" line per source — so the Update Log stays a reliable trail rather than silently skipping weeks.
- **Metrics sheet for this month doesn't exist yet:** note it and continue with the other two sources.
- **`os_dialer_disposition_breakdown` / `os_dialer_recent_notes` return "no calls logged yet":** write that verbatim for the OS dialer line — don't treat it as an error.
- **`insights.md` or the `cold-calling-script` skill directory is missing:** stop and report the problem — don't recreate the skill from scratch here, that's a one-time build task, not this skill's job.

---

## Completion Message

```
Cold Calling Resync complete — YYYY-MM-DD
Update Log entry added: [one-line summary of the delta]
Sources checked: Drive (N new docs), Metrics sheet ([found/not found]), OS dialer (N recent notes)
```

If nothing new was found anywhere:
```
Cold Calling Resync complete — YYYY-MM-DD
No new signal this week — logged a "nothing new" entry across all three sources.
```
