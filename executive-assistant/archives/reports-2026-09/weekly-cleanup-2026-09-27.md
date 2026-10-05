# Weekly Cleanup — 2026-09-27

## Auto-Fixed
- `dashboard/backend/outreach_video.py`: Removed two unused imports (`import os` and `from datetime import date`). Verified by grep that neither `os` nor `date` is referenced anywhere else in the file — both appeared only on their own import lines. Behavior-neutral (dead imports only); `py_compile` passes after the change.

## Needs Approval
- `content-agent/tools/generate_creative.py` (referenced by `media-buying-agent/CLAUDE.md` line 32, `media-buying-agent/context/ad-creative-principles.md`, and `media-buying-agent/.claude/skills/generate-ad/SKILL.md` step 78 as `python tools/generate_creative.py image ...`): the file does not exist anywhere in the repo, so the `generate-ad` skill is currently **non-functional**, not merely stale docs. Same finding as the 2026-09-20 run — still unresolved. Recommendation: decide whether to build `generate_creative.py` (the fal.ai image tool the docs describe) or repoint all three docs at whatever the real image-generation path is. Not auto-fixed because the correct resolution is a functional/business decision, not a behavior-neutral doc edit.
- `dashboard/backend/calendly_integration.py` — `unregister_webhook`: verified zero callers anywhere in the repo (grep across `.py`/`.jsx`/`.js`/`.md`). It is the clean symmetric counterpart to `register_webhook`, so it is plausibly a reserved operational/admin helper for Calendly webhook lifecycle rather than accidental dead code. Same finding as the 2026-09-20 run. Recommendation: safe to delete if there is no planned manual/admin use; otherwise leave as a reserved utility. Not auto-removed because its necessity cannot be proven to be zero (feature-removal judgment call).

## Archived
Archived executive-assistant/reports/cold-calling-resync-2026-09-14.md -> executive-assistant/archives/reports-2026-09/cold-calling-resync-2026-09-14.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/daily-briefing-2026-09-14.md -> executive-assistant/archives/reports-2026-09/daily-briefing-2026-09-14.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/daily-briefing-2026-09-18.md -> executive-assistant/archives/reports-2026-09/daily-briefing-2026-09-18.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/sheets-digest-2026-09-14.md -> executive-assistant/archives/reports-2026-09/sheets-digest-2026-09-14.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/sheets-digest-2026-09-16.md -> executive-assistant/archives/reports-2026-09/sheets-digest-2026-09-16.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/sheets-digest-2026-09-17.md -> executive-assistant/archives/reports-2026-09/sheets-digest-2026-09-17.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/sheets-digest-2026-09-18.md -> executive-assistant/archives/reports-2026-09/sheets-digest-2026-09-18.md (write: committed and pushed, delete: committed and pushed)
Archived executive-assistant/reports/weekly-cleanup-2026-09-20.md -> executive-assistant/archives/reports-2026-09/weekly-cleanup-2026-09-20.md (write: committed and pushed, delete: committed and pushed)

## Flagged Stale Projects
Nothing flagged this week.

---

### Detection candidates investigated and intentionally left untouched (false positives / not behavior-neutral)
- **Broken doc references (scanner false positives):** The remaining flagged references are legitimate and were left as-is: (a) archived-report snapshots under `executive-assistant/archives/` are immutable historical records; (b) `content-agent/CLAUDE.md`'s `outputs/ad-copy-vet-lead-gen.md` / `outputs/email-sequence-cold-outreach.md` are file-**naming-convention examples**, not real references; (c) `assets/headcam-master.mp4` is an R2 object key (`HEADCAM_R2_KEY`), and `content-agent/raw/headcam-master.mp4` / `.mp4` / `public/index.html` / `src/content/blog-posts.json` point at gitignored large media or the separate `digigrowth-website` repo — correct references, nothing broken; (d) `content-agent/memory.md`'s `blog-*.json` entries are historical log lines for pending-approval files consumed after publishing.
- **Duplicate helpers (intentional, not consolidated):** `doppler_secret` (8 standalone agent CLI tools in `content-agent/tools/` and `design-agent/tools/`) and `_get_templates` / `_fill` / `_extract_email` / `_master_client`/`_twilio` / `_client_creds`/`_identity_google_creds` / `_safe_slug` pairs. The agent tools are self-contained scripts run standalone (`python tools/xxx.py`) from their own directories with no shared package; consolidating would introduce cross-package imports that break standalone execution — a behavior change, not a neutral cleanup. Several also sit in secrets-adjacent (Doppler/Twilio/Google-creds) code. Left untouched by design.
