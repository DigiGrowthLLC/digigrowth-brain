# Weekly Cleanup — 2026-07-15

## Auto-Fixed
- apptset-agent/notion_log.py: Removed unused `import os` (grep confirmed `os` appears only on the import line, never referenced); verified with py_compile.

## Needs Approval
- apptset-agent/notion_log.py (`read_queue`): No Python callers found, but the module docstring documents it as the queue-flush primitive consumed by the EA's SMS skill (an agent/MCP consumer that a code grep cannot detect). Deleting it could break the documented flush behavior — recommend leaving it; confirm with Dylan whether the EA SMS skill still flushes this queue before removing.
- content-agent/CLAUDE.md (`outputs/email-sequence-cold-outreach.md`, `outputs/ad-copy-vet-lead-gen.md`): These are illustrative file-naming examples under "Name files clearly" (with "etc."), not references to files expected to exist — the `outputs/` dir is empty because the agent is pre-revenue. Flagged as false positives; recommend no change (leave as naming guidance).
- executive-assistant/.claude/skills/add-managed-agent/SKILL.md (`executive-assistant/.claude/settings.json`): The file doesn't exist yet, but the skill's entire purpose is to create/update this file when onboarding an external agent (Step 2 only writes it for agents outside the repo, hence none created yet). This is a managed target, not a broken link — recommend no change.

## Archived
Archived executive-assistant/reports/daily-briefing-2026-06-11.md -> executive-assistant/archives/reports-2026-06/daily-briefing-2026-06-11.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/daily-briefing-2026-06-12.md -> executive-assistant/archives/reports-2026-06/daily-briefing-2026-06-12.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/daily-briefing-2026-06-13.md -> executive-assistant/archives/reports-2026-06/daily-briefing-2026-06-13.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/daily-briefing-2026-06-14.md -> executive-assistant/archives/reports-2026-06/daily-briefing-2026-06-14.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/daily-briefing-2026-06-15.md -> executive-assistant/archives/reports-2026-06/daily-briefing-2026-06-15.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/daily-briefing-2026-06-16.md -> executive-assistant/archives/reports-2026-06/daily-briefing-2026-06-16.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/daily-briefing-2026-06-17.md -> executive-assistant/archives/reports-2026-06/daily-briefing-2026-06-17.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/daily-briefing-2026-06-18.md -> executive-assistant/archives/reports-2026-06/daily-briefing-2026-06-18.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/daily-briefing-2026-06-19.md -> executive-assistant/archives/reports-2026-06/daily-briefing-2026-06-19.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/daily-briefing-2026-06-20.md -> executive-assistant/archives/reports-2026-06/daily-briefing-2026-06-20.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/daily-briefing-2026-06-21.md -> executive-assistant/archives/reports-2026-06/daily-briefing-2026-06-21.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/daily-briefing-2026-06-22.md -> executive-assistant/archives/reports-2026-06/daily-briefing-2026-06-22.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/daily-briefing-2026-06-23.md -> executive-assistant/archives/reports-2026-06/daily-briefing-2026-06-23.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/daily-briefing-2026-06-24.md -> executive-assistant/archives/reports-2026-06/daily-briefing-2026-06-24.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/daily-briefing-2026-06-25.md -> executive-assistant/archives/reports-2026-06/daily-briefing-2026-06-25.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/daily-briefing-2026-06-26.md -> executive-assistant/archives/reports-2026-06/daily-briefing-2026-06-26.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/daily-briefing-2026-06-27.md -> executive-assistant/archives/reports-2026-06/daily-briefing-2026-06-27.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/daily-briefing-2026-06-28.md -> executive-assistant/archives/reports-2026-06/daily-briefing-2026-06-28.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/daily-briefing-2026-06-29.md -> executive-assistant/archives/reports-2026-06/daily-briefing-2026-06-29.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/daily-briefing-2026-06-30.md -> executive-assistant/archives/reports-2026-06/daily-briefing-2026-06-30.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/daily-briefing-2026-07-01.md -> executive-assistant/archives/reports-2026-07/daily-briefing-2026-07-01.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/sheets-digest-2025-06-09.md -> executive-assistant/archives/reports-2025-06/sheets-digest-2025-06-09.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/sheets-digest-2025-06-10.md -> executive-assistant/archives/reports-2025-06/sheets-digest-2025-06-10.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/sheets-digest-2025-06-11.md -> executive-assistant/archives/reports-2025-06/sheets-digest-2025-06-11.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/sheets-digest-2026-06-13.md -> executive-assistant/archives/reports-2026-06/sheets-digest-2026-06-13.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/sheets-digest-2026-06-14.md -> executive-assistant/archives/reports-2026-06/sheets-digest-2026-06-14.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/sheets-digest-2026-06-15.md -> executive-assistant/archives/reports-2026-06/sheets-digest-2026-06-15.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/sheets-digest-2026-06-16.md -> executive-assistant/archives/reports-2026-06/sheets-digest-2026-06-16.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/sheets-digest-2026-06-17.md -> executive-assistant/archives/reports-2026-06/sheets-digest-2026-06-17.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/sheets-digest-2026-06-18.md -> executive-assistant/archives/reports-2026-06/sheets-digest-2026-06-18.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/sheets-digest-2026-06-19.md -> executive-assistant/archives/reports-2026-06/sheets-digest-2026-06-19.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/sheets-digest-2026-06-20.md -> executive-assistant/archives/reports-2026-06/sheets-digest-2026-06-20.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/sheets-digest-2026-06-21.md -> executive-assistant/archives/reports-2026-06/sheets-digest-2026-06-21.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/sheets-digest-2026-06-22.md -> executive-assistant/archives/reports-2026-06/sheets-digest-2026-06-22.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/sheets-digest-2026-06-23.md -> executive-assistant/archives/reports-2026-06/sheets-digest-2026-06-23.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/sheets-digest-2026-06-24.md -> executive-assistant/archives/reports-2026-06/sheets-digest-2026-06-24.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/sheets-digest-2026-06-25.md -> executive-assistant/archives/reports-2026-06/sheets-digest-2026-06-25.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/sheets-digest-2026-06-26.md -> executive-assistant/archives/reports-2026-06/sheets-digest-2026-06-26.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/sheets-digest-2026-06-27.md -> executive-assistant/archives/reports-2026-06/sheets-digest-2026-06-27.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/sheets-digest-2026-06-28.md -> executive-assistant/archives/reports-2026-06/sheets-digest-2026-06-28.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/sheets-digest-2026-06-29.md -> executive-assistant/archives/reports-2026-06/sheets-digest-2026-06-29.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/sheets-digest-2026-06-30.md -> executive-assistant/archives/reports-2026-06/sheets-digest-2026-06-30.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/sheets-digest-2026-07-01.md -> executive-assistant/archives/reports-2026-07/sheets-digest-2026-07-01.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/sheets-digest-2026-07-02.md -> executive-assistant/archives/reports-2026-07/sheets-digest-2026-07-02.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/sheets-digest-2026-07-04.md -> executive-assistant/archives/reports-2026-07/sheets-digest-2026-07-04.md (write: committed and pushed, delete: committed and pushed)

## Flagged Stale Projects
ai-process-integration — no activity in 67 days (last: 2026-05-08)
