# Weekly Cleanup — 2026-08-30

## Auto-Fixed
- Nothing auto-fixed this week. Detection returned no unused imports and no zero-caller functions. Every flagged "broken doc reference" was investigated with Grep/Read and confirmed to be a false positive, so nothing was safe to touch:
  - `content-agent/CLAUDE.md` (`outputs/ad-copy-vet-lead-gen.md`, `outputs/email-sequence-cold-outreach.md`) — these are illustrative filename-convention examples in the "Output Files" section, not references to real files.
  - `content-agent/.claude/skills/weekly-ai-blog/SKILL.md` (`src/content/blog-posts.json`) — refers to a file in the **external** `digigrowth-website` repo, not this one (the surrounding text names it correctly).
  - `content-agent/.claude/skills/video-overlay/SKILL.md` (`public/index.html`, `.../cant-code-video/output-v5-final.mp4`) — `public/index.html` is a runtime output the skill *creates*; the `.mp4` visual reference lives under `content-agent/projects/`, which is `.gitignore`'d (local-only artifact, intentionally uncommitted).
  - `content-agent/memory.md` (`content-agent/pending_approvals/blog-2026-08-26.json`) — a historical memory-log entry recording a past event, not a live reference.
  - The remaining broken-reference hits were all inside archived reports and prior cleanup/briefing reports under `executive-assistant/archives/` and `executive-assistant/reports/` — historical records, left untouched by design.

## Needs Approval
- `dashboard/backend/cancel_sequence.py`, `dashboard/backend/no_show_sequence.py`, `dashboard/backend/dm_followup_sequence.py` — **duplicated private helpers.** `_get_templates()` is byte-identical across all three files, and `_fill()` is byte-identical in `cancel_sequence.py` and `no_show_sequence.py`. They could be consolidated into one shared helper module (e.g. `dashboard/backend/sequence_common.py`), with `_get_templates(defaults)` taking each file's module-level `TEMPLATE_DEFAULTS` as a parameter (the bodies are identical but each reads a different `TEMPLATE_DEFAULTS`, so a straight lift needs that one signature change).
  - **Why this needs a human, not an auto-fix:** these are live, customer-facing SMS/email drip engines (cancellation recovery, no-show recovery, DM follow-up). Consolidation rewires imports across three production files and changes `_get_templates`'s signature — it cannot be runtime-verified against the production DB from this run, so it only clears the "byte-identical helper" safety bar on paper. The payoff is small (~15 lines removed) and the downside (a broken messaging engine) is real.
  - **Recommendation:** approve only alongside a manual smoke test of all three sequences after the refactor; otherwise leave as-is — the duplication is harmless. Deferring is the low-risk default.

## Archived
Archived executive-assistant/reports/daily-briefing-2026-08-19.md -> executive-assistant/archives/reports-2026-08/daily-briefing-2026-08-19.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/daily-briefing-2026-08-20.md -> executive-assistant/archives/reports-2026-08/daily-briefing-2026-08-20.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/daily-briefing-2026-08-21.md -> executive-assistant/archives/reports-2026-08/daily-briefing-2026-08-21.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/sheets-digest-2026-08-21.md -> executive-assistant/archives/reports-2026-08/sheets-digest-2026-08-21.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/weekly-cleanup-2026-08-23.md -> executive-assistant/archives/reports-2026-08/weekly-cleanup-2026-08-23.md (write: committed and pushed, delete: committed and pushed)

## Flagged Stale Projects
Nothing flagged this week.
