# Weekly Cleanup — 2026-08-23

## Auto-Fixed
- `leadgen-agent/lib.py`: Removed the dead `looks_like_chain_or_non_pt()` pre-filter and its two exclusive constants (`CHAIN_KEYWORDS`, `NON_PT_NAME_KEYWORDS`) — 30 lines total. Verified zero callers anywhere in the repo (only its own definition), it is not wired into the file's CLI dispatch, and the `scrape-leads` skill now does chain/non-PT filtering via Claude Code reasoning with its own inline institutional-keyword list + `memory.txt`'s blacklist (it never references this function or these constants). Leftover from the old paid Places-API pipeline. Behavior-neutral; `py_compile` passes.
- `copy-agent/.claude/skills/offer/SKILL.md`: Removed a broken "Sources" pointer to a transcript file (`content-agent/outputs/transcript-…-2026-07-30.txt`) that no longer exists anywhere in the repo. Kept the human-readable citation ("Jason Fladlin's 'How To Create Killer Offers — 8 Secrets'"). The skill's 8 levers are fully inlined in its body, so the file was only a citation and was never read at runtime — behavior-neutral.

## Needs Approval
Nothing pending. All other static-scan hits this week were verified false positives:
- `content-agent/CLAUDE.md` → `outputs/ad-copy-vet-lead-gen.md`, `outputs/email-sequence-cold-outreach.md`: illustrative file-naming examples under "Name files clearly:", not real references.
- `content-agent/.claude/skills/weekly-ai-blog/SKILL.md` + `executive-assistant/.claude/skills/manage-content-agent/SKILL.md` → `src/content/blog-posts.json` / `digigrowth-website/src/content/blog-posts.json`: valid cross-repo references to the separate `digigrowth-website` repo, not files in this repo.
- `executive-assistant/.claude/skills/add-managed-agent/SKILL.md` → `executive-assistant/.claude/settings.json`: the skill only creates/updates this file when registering an agent that lives *outside* the repo (not the normal case), so its absence is expected — the skill handles both the exists and not-exists paths.
- All other broken-reference hits were inside historical `reports/`/`archives/` files, which are point-in-time records and are never edited.

## Archived
Archived executive-assistant/reports/cold-calling-resync-2026-08-03.md -> executive-assistant/archives/reports-2026-08/cold-calling-resync-2026-08-03.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/daily-briefing-2026-07-27.md -> executive-assistant/archives/reports-2026-07/daily-briefing-2026-07-27.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/daily-briefing-2026-07-28.md -> executive-assistant/archives/reports-2026-07/daily-briefing-2026-07-28.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/daily-briefing-2026-07-29.md -> executive-assistant/archives/reports-2026-07/daily-briefing-2026-07-29.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/daily-briefing-2026-07-30.md -> executive-assistant/archives/reports-2026-07/daily-briefing-2026-07-30.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/daily-briefing-2026-07-31.md -> executive-assistant/archives/reports-2026-07/daily-briefing-2026-07-31.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/daily-briefing-2026-08-03.md -> executive-assistant/archives/reports-2026-08/daily-briefing-2026-08-03.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/daily-briefing-2026-08-04.md -> executive-assistant/archives/reports-2026-08/daily-briefing-2026-08-04.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/daily-briefing-2026-08-05.md -> executive-assistant/archives/reports-2026-08/daily-briefing-2026-08-05.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/sheets-digest-2026-07-27.md -> executive-assistant/archives/reports-2026-07/sheets-digest-2026-07-27.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/sheets-digest-2026-07-29.md -> executive-assistant/archives/reports-2026-07/sheets-digest-2026-07-29.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/sheets-digest-2026-07-30.md -> executive-assistant/archives/reports-2026-07/sheets-digest-2026-07-30.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/sheets-digest-2026-07-31.md -> executive-assistant/archives/reports-2026-07/sheets-digest-2026-07-31.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/sheets-digest-2026-08-03.md -> executive-assistant/archives/reports-2026-08/sheets-digest-2026-08-03.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/sheets-digest-2026-08-04.md -> executive-assistant/archives/reports-2026-08/sheets-digest-2026-08-04.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/weekly-cleanup-2026-08-02.md -> executive-assistant/archives/reports-2026-08/weekly-cleanup-2026-08-02.md (write: committed and pushed, delete: committed and pushed)

## Flagged Stale Projects
Nothing flagged this week.
