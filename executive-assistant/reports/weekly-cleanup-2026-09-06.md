# Weekly Cleanup — 2026-09-06

## Auto-Fixed
- `content-agent/tools/lookup_lead.py`: Removed the unused `from urllib.parse import quote` import (line 4). Verified with grep that `quote` is never referenced anywhere in the file — the only occurrence was the import itself. Behavior-neutral; `py_compile` passes.

## Needs Approval
- `content-agent/tools/{lookup_lead,publish_to_watch,send_outreach_sms}.py`: Byte-identical `doppler_secret()` helper duplicated across all three. Could be consolidated into one shared helper, **but** these are standalone CLI scripts invoked individually (`python <tool>.py ...`); introducing a shared-module import adds `sys.path`/cwd fragility that doesn't exist today. Recommendation: leave self-contained unless a deliberate `content-agent/tools/_common.py` refactor is desired — not a behavior-neutral drop-in, so not auto-applied.
- `dashboard/backend/{client_booking_notification,cancel_sequence,email_handoff_sequence,dm_followup_sequence,no_show_sequence,onboarding_sequence}.py`: `_get_templates()` has a byte-identical body in all six, but each closes over a **different module-local `TEMPLATE_DEFAULTS`**. Consolidating would require passing `TEMPLATE_DEFAULTS` as a parameter and rewiring every call site — a real refactor that changes signatures, not a safe drop-in. Recommendation: extract a shared `_load_templates(defaults)` helper only as an intentional, separately-reviewed change.
- `dashboard/backend/{cancel_sequence,no_show_sequence}.py`: `_fill()` is identical in both but depends on module-local `integrations` / `first_name_from_owner` imports. Same story as above — consolidation is a deliberate refactor, not behavior-neutral. Left untouched.

Investigated and confirmed NOT actionable (static-scan false positives, no change needed):
- `content-agent/CLAUDE.md` refs to `outputs/ad-copy-vet-lead-gen.md` / `outputs/email-sequence-cold-outreach.md` — these are naming-convention *examples* in the "Output Files" section, not references to files that must exist.
- `content-agent/memory.md` refs to `pending_approvals/blog-*.json` — historical log entries recording where past drafts were saved, not live references.
- `content-agent/.claude/skills/video-overlay/SKILL.md` ref to `public/index.html` — an output artifact the skill *produces*, not a pre-existing file.
- `content-agent/.claude/skills/{video-overlay,outreach-video}/SKILL.md` refs to `*.mp4` under `content-agent/projects/` and `content-agent/raw/` — both directories are `.gitignore`'d (local-only video artifacts / user-provided inputs); the outreach-video skill already handles the missing-file case explicitly.
- `content-agent/.claude/skills/weekly-ai-blog/SKILL.md` ref to `src/content/blog-posts.json` — lives in the separate `digigrowth-website` repo, not this one.
- All `executive-assistant/archives/**` broken-reference hits — historical report snapshots, intentionally left as written.

## Archived
Archived executive-assistant/reports/cold-calling-resync-2026-08-24.md -> executive-assistant/archives/reports-2026-08/cold-calling-resync-2026-08-24.md
Archived executive-assistant/reports/daily-briefing-2026-08-24.md -> executive-assistant/archives/reports-2026-08/daily-briefing-2026-08-24.md
Archived executive-assistant/reports/daily-briefing-2026-08-25.md -> executive-assistant/archives/reports-2026-08/daily-briefing-2026-08-25.md
Archived executive-assistant/reports/daily-briefing-2026-08-26.md -> executive-assistant/archives/reports-2026-08/daily-briefing-2026-08-26.md
Archived executive-assistant/reports/daily-briefing-2026-08-27.md -> executive-assistant/archives/reports-2026-08/daily-briefing-2026-08-27.md
Archived executive-assistant/reports/daily-briefing-2026-08-28.md -> executive-assistant/archives/reports-2026-08/daily-briefing-2026-08-28.md
Archived executive-assistant/reports/sheets-digest-2026-08-24.md -> executive-assistant/archives/reports-2026-08/sheets-digest-2026-08-24.md
Archived executive-assistant/reports/sheets-digest-2026-08-25.md -> executive-assistant/archives/reports-2026-08/sheets-digest-2026-08-25.md
Archived executive-assistant/reports/sheets-digest-2026-08-26.md -> executive-assistant/archives/reports-2026-08/sheets-digest-2026-08-26.md
Archived executive-assistant/reports/sheets-digest-2026-08-27.md -> executive-assistant/archives/reports-2026-08/sheets-digest-2026-08-27.md
Archived executive-assistant/reports/sheets-digest-2026-08-28.md -> executive-assistant/archives/reports-2026-08/sheets-digest-2026-08-28.md
Archived executive-assistant/reports/weekly-cleanup-2026-08-30.md -> executive-assistant/archives/reports-2026-08/weekly-cleanup-2026-08-30.md

(Note: these moves were already reflected in the committed repo history from a prior retention pass — the helper ran idempotently, so no new archive delta was produced this run. `reports/` now holds nothing older than the 7-day cutoff.)

## Flagged Stale Projects
Nothing flagged this week.
