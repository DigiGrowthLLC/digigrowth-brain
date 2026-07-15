# Weekly Cleanup Agent

Runs every Sunday at 8pm ET. Scans the whole repo for dead code, redundant/conflicting instructions, and stale reports; auto-fixes anything it can verify is safe without changing behavior; anything needing judgment goes into the weekly report's "Needs Approval" section for Dylan to review in Monday's daily briefing.

**Managed by:** Dylan's Executive Assistant surfaces its output — see `executive-assistant/.claude/skills/daily-briefing/SKILL.md` Step 4.6 in the `digigrowth-brain` repo. The script itself is not an EA skill (the EA's own tools are sandboxed to `executive-assistant/`; this runs as an independent process with full repo access).
**Run via:** triggered automatically by `dashboard/backend/main.py`'s scheduler (`weekly-cleanup` cron job, Sundays 8pm ET). Manual run: `doppler run -- python run.py` (add `--dry-run` to preview without writing or pushing anything).

## File Roles

| File | Purpose |
|---|---|
| `run.py` | Main script — detection (free static scan), judgment/fix (one bounded Opus session), report retention, and reporting |
| `requirements.txt` | Python dependency (`anthropic`) |
| `last_run.json` | Tracks the git SHA of the last run, so the next run can diff only what changed since (auto-generated) |

Secrets (`ANTHROPIC_API_KEY`, `GIT_TOKEN`, `DASHBOARD_PASSWORD`) are read directly from the Railway container's environment — no Doppler CLI wrapper needed there since it runs as a subprocess of the dashboard backend, not a manually-invoked local script. For local manual runs, use `doppler run --` (config `prd`) same as the other standalone agents.

## Safety Model

The judgment phase has a deliberately narrow tool set — `read_file`/`write_file`/`delete_file`/`list_files`/`grep`/`run_check` — no raw Bash, no arbitrary shell. `run_check` only accepts three exact allowlisted command forms (`py_compile <path>`, `npm_build`, `json_check <path>`). It never touches `.env`, `credentials.json`, or `settings.local.json` (blocked at the tool level), never deletes directories, and is capped at 15 files / 40 tool calls per run. Anything outside its "verified zero-risk" criteria goes to the "Needs Approval" section instead of being touched.

## Security

Secrets live in Doppler (`prd` config, for manual local runs) or Railway's own environment (for the scheduled container run) — never in a local `.env` file.
