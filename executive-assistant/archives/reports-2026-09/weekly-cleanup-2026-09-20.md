# Weekly Cleanup — 2026-09-20

## Auto-Fixed
- `dashboard/backend/identity_warmup.py`: Removed unused `timedelta` from the `datetime` import (line 40). Verified with grep that `timedelta` appears nowhere else in the file (only on the import line itself); `date`, `datetime`, and `dt_timezone` remain and are still used. Behavior-neutral. `py_compile` passes.
- `dashboard/backend/routers/client_portal.py`: Removed the unused `from routers import dialer as dialer_router` import (line 44). Verified `dialer_router` had zero references anywhere in the file, and `dialer` is already imported and registered in `main.py`, so this import was dead/redundant (unlike `appointments_router` and `sms_router`, which are used). Behavior-neutral. `py_compile` passes.

## Needs Approval
- `dashboard/backend/calendly_integration.py` (`unregister_webhook`): Verified zero callers anywhere in the repo (grep across `.py`/`.jsx`/`.js`). It is the clean symmetric counterpart to `register_webhook`, so it is plausibly kept intentionally as an operational/admin helper for Calendly webhook lifecycle management rather than being accidental dead code. — Recommendation: safe to delete if there is no planned manual/admin use of it; otherwise leave as a reserved utility. Not auto-removed because its necessity cannot be proven to be zero (feature-removal judgment call).
- `media-buying-agent/CLAUDE.md` + `media-buying-agent/.claude/skills/generate-ad/SKILL.md`: Both reference `content-agent/tools/generate_creative.py` (CLAUDE.md line 32 says image generation "reuses" it; the `generate-ad` skill invokes `python tools/generate_creative.py image ...` at step 78). That file does **not** exist in `content-agent/tools/` (which contains only compose_outreach_video, lookup_lead, publish_to_watch, record_site_scroll, send_outreach_sms, transcribe), and it is referenced nowhere else in the repo. This means the `generate-ad` skill is currently non-functional, not merely stale docs. — Recommendation: decide whether to build `generate_creative.py` (the fal.ai image tool the docs describe) or to update both docs to point at whatever the real image-generation path is. Not auto-fixed because the correct resolution is a functional/business decision, not a behavior-neutral doc edit.
- Duplicated helper logic (consolidation opportunity, **not** auto-fixed — would risk behavior): The static scan flags several byte-identical helpers. The largest is `doppler_secret()` duplicated across 8 standalone agent tool scripts (`design-agent/tools/*` and `content-agent/tools/*`). These are deliberately self-contained scripts (each has `if __name__ == "__main__"` and is run from its own agent directory), so the duplication is the intended standalone pattern — consolidating into a shared module would introduce cross-directory import coupling that could break standalone execution. Backend-side duplicates (`_get_templates` across 6 `*_sequence.py` files, `_fill` in cancel/no_show sequences, `_extract_email` and the Google-creds helper across `client_email.py`/`email_identities.py`, `_safe_slug` in `watch.py`/`landing_pages.py`, `_master_client`/`_twilio` in `client_sms.py`/`routers/sms.py`) could in principle be consolidated within the backend package, but each is a multi-file refactor that changes module structure and the byte-identical bodies may be kept independent so they can diverge. — Recommendation: leave the standalone agent scripts as-is; treat any backend consolidation as an optional, separately-reviewed refactor.

_Investigated but no action needed (false positives from the static scan): the broken-doc-reference hits in `content-agent/CLAUDE.md` (`outputs/ad-copy-vet-lead-gen.md`, `outputs/email-sequence-cold-outreach.md`) are file-naming **examples**, not references to files that must exist; `content-agent/memory.md`'s `pending_approvals/blog-*.json` hits are accurate historical log entries about transient files consumed by the approval relay; the skill references (`output-v5-final.mp4`, `public/index.html`, `headcam-master.mp4`, `src/content/blog-posts.json`) are media assets, runtime-generated output paths, expected-to-be-supplied inputs, or files that live in the separate `digigrowth-website` repo. All hits under `executive-assistant/archives/` are immutable historical reports and were left untouched._

## Archived
Archived executive-assistant/reports/cold-calling-resync-2026-08-31.md -> executive-assistant/archives/reports-2026-08/cold-calling-resync-2026-08-31.md
Archived executive-assistant/reports/cold-calling-resync-2026-09-07.md -> executive-assistant/archives/reports-2026-09/cold-calling-resync-2026-09-07.md
Archived executive-assistant/reports/daily-briefing-2026-08-31.md -> executive-assistant/archives/reports-2026-08/daily-briefing-2026-08-31.md
Archived executive-assistant/reports/daily-briefing-2026-09-01.md -> executive-assistant/archives/reports-2026-09/daily-briefing-2026-09-01.md
Archived executive-assistant/reports/daily-briefing-2026-09-02.md -> executive-assistant/archives/reports-2026-09/daily-briefing-2026-09-02.md
Archived executive-assistant/reports/daily-briefing-2026-09-03.md -> executive-assistant/archives/reports-2026-09/daily-briefing-2026-09-03.md
Archived executive-assistant/reports/daily-briefing-2026-09-04.md -> executive-assistant/archives/reports-2026-09/daily-briefing-2026-09-04.md
Archived executive-assistant/reports/daily-briefing-2026-09-07.md -> executive-assistant/archives/reports-2026-09/daily-briefing-2026-09-07.md
Archived executive-assistant/reports/daily-briefing-2026-09-08.md -> executive-assistant/archives/reports-2026-09/daily-briefing-2026-09-08.md
Archived executive-assistant/reports/daily-briefing-2026-09-09.md -> executive-assistant/archives/reports-2026-09/daily-briefing-2026-09-09.md
Archived executive-assistant/reports/daily-briefing-2026-09-10.md -> executive-assistant/archives/reports-2026-09/daily-briefing-2026-09-10.md
Archived executive-assistant/reports/daily-briefing-2026-09-11.md -> executive-assistant/archives/reports-2026-09/daily-briefing-2026-09-11.md
Archived executive-assistant/reports/sheets-digest-2026-08-31.md -> executive-assistant/archives/reports-2026-08/sheets-digest-2026-08-31.md
Archived executive-assistant/reports/sheets-digest-2026-09-01.md -> executive-assistant/archives/reports-2026-09/sheets-digest-2026-09-01.md
Archived executive-assistant/reports/sheets-digest-2026-09-02.md -> executive-assistant/archives/reports-2026-09/sheets-digest-2026-09-02.md
Archived executive-assistant/reports/sheets-digest-2026-09-04.md -> executive-assistant/archives/reports-2026-09/sheets-digest-2026-09-04.md
Archived executive-assistant/reports/sheets-digest-2026-09-07.md -> executive-assistant/archives/reports-2026-09/sheets-digest-2026-09-07.md
Archived executive-assistant/reports/sheets-digest-2026-09-08.md -> executive-assistant/archives/reports-2026-09/sheets-digest-2026-09-08.md
Archived executive-assistant/reports/sheets-digest-2026-09-09.md -> executive-assistant/archives/reports-2026-09/sheets-digest-2026-09-09.md
Archived executive-assistant/reports/sheets-digest-2026-09-10.md -> executive-assistant/archives/reports-2026-09/sheets-digest-2026-09-10.md
Archived executive-assistant/reports/sheets-digest-2026-09-11.md -> executive-assistant/archives/reports-2026-09/sheets-digest-2026-09-11.md
Archived executive-assistant/reports/weekly-cleanup-2026-09-06.md -> executive-assistant/archives/reports-2026-09/weekly-cleanup-2026-09-06.md

## Flagged Stale Projects
Nothing flagged this week.
