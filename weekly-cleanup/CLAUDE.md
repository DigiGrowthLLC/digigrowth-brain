# Weekly Cleanup Agent

Runs every Sunday at ~8:04pm ET. Scans the whole repo for dead code, redundant/conflicting instructions, and stale reports; auto-fixes anything it can verify is safe without changing behavior; anything needing judgment goes into the weekly report's "Needs Approval" section for Dylan to review in Monday's daily briefing.

**Managed by:** Dylan's Executive Assistant surfaces its output — see `executive-assistant/.claude/skills/daily-briefing/SKILL.md` Step 4.6 in the `digigrowth-brain` repo.

**Run via:** a Claude Code cloud routine ("EA Weekly Cleanup", `claude.ai/code/routines`) — runs under Dylan's Claude subscription rather than the metered Anthropic API. The routine's prompt reuses the pure-Python detection (`run_detection`), retention (`archive_old_reports`), and stale-project (`flag_stale_projects`) helpers in this directory's `run.py`, and does the judgment/fix phase itself with its own native tools instead of a separate scripted API call. `run.py` is now an import-only helper library — no `import anthropic`, no `main()`/CLI, so there is no script to run manually; trigger a run via the routines UI ("Run now") instead.

## File Roles

| File | Purpose |
|---|---|
| `run.py` | Import-only helper library — the pure-Python detection/retention/stale-project functions the routine imports (`from run import run_detection, archive_old_reports, flag_stale_projects, load_last_run_sha`). No `main()`/CLI; the judgment/fix phase lives in the routine itself. |
| `last_run.json` | Tracks the git SHA of the last run, so the next run only diffs what changed since (written by the routine directly via `git`) |

## Safety Model

Unlike the old script (which had a code-enforced narrow tool set — no raw Bash, 15-file/40-tool-call hard caps), the cloud routine runs with full Claude Code tool access (Bash, Edit, Write, etc.) under prompted — not code-enforced — restrictions. Dylan's explicit call: it may make any edit it judges improves quality, efficiency, cost-effectiveness, or security, as long as it (a) does not change how anything currently built actually behaves, and (b) never touches or exposes secrets, credentials, or other sensitive information (`.env`, `credentials.json`, `settings.local.json` are off-limits — all real secrets live in the shared `digigrowth` Doppler vault, not in this repo). Anything outside high confidence goes to the "Needs Approval" section of the report instead of being touched directly.

## Delivery

The routine commits its report to `executive-assistant/reports/weekly-cleanup-YYYY-MM-DD.md` and pushes — it cannot reach Railway directly (sandboxed network). A Railway-side job (`_post_weekly_cleanup_report` in `dashboard/backend/main.py`) picks the report up from GitHub ~30 minutes later and posts an activity-feed line — no LLM call involved on that side.

## Posting a Review Card (Approve/Decline)

In addition to the markdown report, the routine drops one `kind: "cleanup"` pending-approval
**request file** so Dylan gets an inline Approve/Decline card in the OS chat — the same relay
mechanism the newsletter and blog-post skills use (`apptset-agent/.claude/skills/newsletter/SKILL.md`
Step 6) — instead of only a wall of report text, and instead of needing Dylan to open Claude Code
or a terminal to apply anything himself.

**Do not call the dashboard's `/api/approvals` endpoint directly** — this routine's sandbox sits
behind a network egress proxy that rejects outbound connections to Railway before any response
comes back, the same reason `_export_sms_outreach_stats`/`_export_newsletter_contacts` in
`dashboard/backend/main.py` exist. A direct curl here fails silently in the same way every time,
which is why Dylan previously never actually got a working button — write the request file instead
and let Railway's own relay job make the call from its side, where it can reach itself.

Build `payload` from this run's own results:

- `payload.auto_fixed`: one entry per item already fixed this run (the "Auto-Fixed" section) —
  `{"file": "path/in/repo", "summary": "<one-line description>", "diff": "<unified diff, e.g. from `git show <sha> -- <file>` or `git diff HEAD~1 -- <file>` right after committing it>"}`.
  Display-only — approving/declining the card never touches these again.
- `payload.changes`: one entry per judgment-call item that would otherwise go in "Needs Approval" —
  `{"file": "path/in/repo", "action": "write" | "delete", "content": "<full proposed file text, only for action=write>", "summary": "<why>", "diff": "<unified diff of current vs proposed>"}`.
  These are **not** applied by the routine — approving the card is what applies them (via the
  Contents API against `digigrowth-brain`, same pattern as blog-post publishing). If a run has no
  judgment calls, omit `payload.changes` (or leave it `[]`) and skip writing a request file entirely
  if `auto_fixed` is also empty.

Write the file directly rather than inlining it in a shell one-liner — diffs contain quotes and
backticks that are painful and error-prone to shell-escape inline:

```bash
mkdir -p weekly-cleanup/pending_approvals
cat > weekly-cleanup/pending_approvals/cleanup-YYYY-MM-DD.json <<'JSONEOF'
{
  "title": "Weekly Cleanup — YYYY-MM-DD",
  "summary": "<N auto-fixed, M needing approval>",
  "payload": {"auto_fixed": [...], "changes": [...]}
}
JSONEOF
```

Push `weekly-cleanup/pending_approvals/cleanup-YYYY-MM-DD.json` to GitHub (`push_file()` from
`shared/github_sync.py`, or `git add`/`commit`/`push` directly). A Railway-side job
(`process_pending_approval("weekly-cleanup", "cleanup", ...)` in `pending_approvals_relay.py`,
polled Sunday ~8:20pm ET — 15 minutes after this routine's own 8:04pm run) picks it up, creates
the real `pending_approvals` row, and posts the live card into the OS chat as its own message —
no marker to embed in the report itself, same async pattern as the newsletter/blog cards. The
report's `## Needs Approval` section (read by Step 4.7 of
`executive-assistant/.claude/skills/daily-briefing/SKILL.md` on the following Monday) should just
summarize what's pending in plain text — it no longer needs to carry a `[[APPROVAL:<id>]]` marker,
since the card will already have gone out Sunday night, separately from Monday's briefing.
Declining leaves every file untouched; approving pushes each `changes` item straight to GitHub.
