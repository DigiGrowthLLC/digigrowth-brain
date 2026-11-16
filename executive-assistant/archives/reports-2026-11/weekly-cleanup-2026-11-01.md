# Weekly Cleanup — 2026-11-01

## Auto-Fixed
- `dashboard/backend/identity_warmup.py`: removed unused imports `timedelta` and `timezone as dt_timezone` from the `datetime` import on line 48. Verified both names have zero references anywhere in the file (grep confirmed only the import line); `date` and `datetime` are still imported and still used. Pure dead-import removal, behavior-neutral. `py_compile` passes.
- `dashboard/backend/routers/client_portal.py`: removed the unused `import integrations` (line 38). Verified the name `integrations` is never referenced anywhere in the file. The `integrations` module has no import-time side effects (only function/class/constant definitions) and is still imported by `main.py` and ~15 other modules, so it still loads at app startup regardless — removing this one unused import changes nothing. `py_compile` passes.

## Needs Approval
- `media-buying-agent/tools/ad_overlays.py` — `lower_third()` has zero callers in the repo. **Not auto-removed**: this file is a renderer toolkit (`hook_card`, `lower_third`, `proof_card`, `end_card`) consumed by `assemble_ugc_ad.py` from a `spec.json`, so an unused renderer is plausibly an intentionally-available building block for a future ad spec rather than true dead code. Recommendation: leave it unless Dylan confirms the lower-third overlay is permanently out of the ad pipeline.
- `dashboard/backend/calendly_integration.py` — `unregister_webhook()` has zero callers. **Not auto-removed**: it's the teardown counterpart to `register_webhook()` and talks to the external Calendly API (webhook DELETE). Removing an external-API integration helper falls under the "external API" approval rule and could break future webhook cleanup. Recommendation: keep as part of the webhook API surface; remove only if Dylan confirms webhook teardown is handled elsewhere / never needed.
- Duplicated helper logic (consolidation opportunities, **not touched** — crosses module/agent boundaries, so consolidating would change structure and standalone-script execution, which isn't clearly behavior-neutral):
  - `doppler_secret()` is byte-identical across 8 agent tool scripts (`design-agent/tools/*.py` ×5, `content-agent/tools/*.py` ×3). Each agent's `tools/` scripts are designed to run standalone, so a shared import would couple them and risks breaking standalone execution unless packaged carefully.
  - `_get_templates()` is identical across 6 `dashboard/backend/*_sequence.py` files; `_fill()` across `cancel_sequence.py` + `no_show_sequence.py`; `_looks_like_bounce()` across `email_identities.py` + `routers/email_inbox.py`; `_set_setting()` across `sms_setter_ai.py` + `routers/calendly_admin.py`; `_safe_slug()` across `routers/watch.py` + `routers/landing_pages.py`. These are intentional per-module private helpers; consolidating into a shared util is a reasonable refactor but is an architecture decision, not a behavior-neutral cleanup.
  - (`client_sms.py:_master_client` vs `routers/sms.py:_twilio` was flagged by the body-hash scan but they are differently-named functions, not a true duplicate — no action.)
- Broken-doc-reference scan surfaced 30 candidates; all investigated and found to be **false positives** — no action. They fall into: (a) instructional example/placeholder paths inside `.claude/skills/*/SKILL.md` and `CLAUDE.md` files describing where an agent *writes* output at runtime (e.g. `out/page.html`, `raw/youtube.md`, `content-agent/CLAUDE.md`'s `outputs/ad-copy-vet-lead-gen.md` example filenames); (b) historical references inside generated `outputs/` artifacts and `memory.md` logs pointing to scratch/approval files that were legitimately processed and removed; (c) relative references inside per-client work products. None are stale references in active docs that contradict current code, so none qualify for auto-fix.

## Archived
Archived executive-assistant/reports/cold-calling-resync-2026-10-19.md -> executive-assistant/archives/reports-2026-10/cold-calling-resync-2026-10-19.md
Archived executive-assistant/reports/daily-briefing-2026-10-19.md -> executive-assistant/archives/reports-2026-10/daily-briefing-2026-10-19.md
Archived executive-assistant/reports/daily-briefing-2026-10-20.md -> executive-assistant/archives/reports-2026-10/daily-briefing-2026-10-20.md
Archived executive-assistant/reports/daily-briefing-2026-10-21.md -> executive-assistant/archives/reports-2026-10/daily-briefing-2026-10-21.md
Archived executive-assistant/reports/daily-briefing-2026-10-22.md -> executive-assistant/archives/reports-2026-10/daily-briefing-2026-10-22.md
Archived executive-assistant/reports/daily-briefing-2026-10-23.md -> executive-assistant/archives/reports-2026-10/daily-briefing-2026-10-23.md
Archived executive-assistant/reports/sheets-digest-2026-10-19.md -> executive-assistant/archives/reports-2026-10/sheets-digest-2026-10-19.md
Archived executive-assistant/reports/sheets-digest-2026-10-20.md -> executive-assistant/archives/reports-2026-10/sheets-digest-2026-10-20.md
Archived executive-assistant/reports/sheets-digest-2026-10-21.md -> executive-assistant/archives/reports-2026-10/sheets-digest-2026-10-21.md
Archived executive-assistant/reports/sheets-digest-2026-10-22.md -> executive-assistant/archives/reports-2026-10/sheets-digest-2026-10-22.md
Archived executive-assistant/reports/sheets-digest-2026-10-23.md -> executive-assistant/archives/reports-2026-10/sheets-digest-2026-10-23.md
Archived executive-assistant/reports/weekly-cleanup-2026-10-25.md -> executive-assistant/archives/reports-2026-10/weekly-cleanup-2026-10-25.md

Note: these 12 files were already present and committed at their `archives/reports-2026-10/` destinations from a prior run — the copies in `reports/` were untracked working-tree leftovers, so this pass cleaned them off disk but produced no net git change in the archive tree.

## Flagged Stale Projects
Nothing flagged this week.
