# Weekly Cleanup Agent

Runs every Sunday at ~8:04pm ET. Scans the whole repo for dead code, redundant/conflicting instructions, and stale reports; auto-fixes anything it can verify is safe without changing behavior; anything needing judgment goes into the weekly report's "Needs Approval" section for Dylan to review in Monday's daily briefing.

**Managed by:** Dylan's Executive Assistant surfaces its output — see `executive-assistant/.claude/skills/daily-briefing/SKILL.md` Step 4.6 in the `digigrowth-brain` repo.

**Run via:** a Claude Code cloud routine ("EA Weekly Cleanup", `claude.ai/code/routines`) — runs under Dylan's Claude subscription rather than the metered Anthropic API. The routine's prompt reuses the pure-Python detection (`run_detection`), retention (`archive_old_reports`), and stale-project (`flag_stale_projects`) helpers that used to live in this directory's `run.py`, and does the judgment/fix phase itself with its own native tools instead of a separate scripted API call. There is no local script to run manually anymore — trigger a run via the routines UI ("Run now") instead.

## File Roles

| File | Purpose |
|---|---|
| `last_run.json` | Tracks the git SHA of the last run, so the next run only diffs what changed since (written by the routine directly via `git`) |

## Safety Model

Unlike the old script (which had a code-enforced narrow tool set — no raw Bash, 15-file/40-tool-call hard caps), the cloud routine runs with full Claude Code tool access (Bash, Edit, Write, etc.) under prompted — not code-enforced — restrictions. Dylan's explicit call: it may make any edit it judges improves quality, efficiency, cost-effectiveness, or security, as long as it (a) does not change how anything currently built actually behaves, and (b) never touches or exposes secrets, credentials, or other sensitive information (`.env`, `credentials.json`, `settings.local.json` are off-limits — all real secrets live in the shared `digigrowth` Doppler vault, not in this repo). Anything outside high confidence goes to the "Needs Approval" section of the report instead of being touched directly.

## Delivery

The routine commits its report to `executive-assistant/reports/weekly-cleanup-YYYY-MM-DD.md` and pushes — it cannot reach Railway directly (sandboxed network). A Railway-side job (`_post_weekly_cleanup_report` in `dashboard/backend/main.py`) picks the report up from GitHub ~30 minutes later and posts an activity-feed line — no LLM call involved on that side.
