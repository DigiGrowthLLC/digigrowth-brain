# Weekly Cleanup — 2026-10-04

## Auto-Fixed
- Nothing auto-fixed this week. Every detection candidate was investigated individually and none cleared the "very high confidence + provably behavior-neutral + no secrets" bar for a direct fix. Details of what was checked are in Needs Approval below.

## Needs Approval
- `dashboard/backend/calendly_integration.py` — `unregister_webhook`: verified zero callers anywhere in the repo (grepped `.py`/`.jsx`/`.js`/`.md`). It is the clean symmetric counterpart to `register_webhook`, so it reads as a reserved operational/admin helper for Calendly webhook lifecycle rather than accidental dead code. Recurring finding (also raised 2026-09-20 and 2026-09-27). Recommendation: keep as a reserved utility unless Dylan confirms there is no planned manual/admin use, in which case it is safe to delete. Not auto-removed — feature-removal judgment call whose necessity cannot be proven zero.
- `media-buying-agent/tools/ad_overlays.py` — `lower_third`: zero callers (the only consumer, `assemble_ugc_ad.py`, calls `ov.hook_card`/`proof_card`/`end_card`/`font`/`chunk_words`/`write_ass` but not `lower_third`). It is one of a family of composable ad-overlay primitives in the module (several others — `set_palette`, `text_block`, `wrap` — are likewise not currently called), so it reads as an intentionally reserved creative primitive. Recommendation: keep unless the overlay toolkit is being deliberately trimmed. Not auto-removed — content/feature judgment call.
- `dashboard/backend/routers/watch.py` + `dashboard/backend/routers/landing_pages.py` — `_safe_slug`: byte-identical, fully self-contained slug validator duplicated in two routers. A clean consolidation into one shared helper is possible and would be behavior-neutral, but it introduces new cross-router import coupling for a ~4-line private validator. Recommendation: low priority; consolidate into a shared `routers` helper module if/when one is introduced. Deferred (architectural call), not auto-applied.
- `dashboard/backend/client_email.py` + `dashboard/backend/email_identities.py` — `_extract_email`: same situation as `_safe_slug` — byte-identical, self-contained 3-line regex helper duplicated across two backend modules. Consolidatable and behavior-neutral, but adds cross-module coupling for a trivial helper. Recommendation: low priority / defer unless a shared backend util module is introduced.

Duplicates deliberately NOT recommended for consolidation (noted here so they are not re-flagged as actionable):
- `doppler_secret` (8 files across `design-agent/tools/` and `content-agent/tools/`), `_client_creds`/`_identity_google_creds` (`client_email.py`/`email_identities.py`), and `_master_client`/`_twilio` (`client_sms.py`/`routers/sms.py`) all construct secrets/OAuth/Twilio credentials — off-limits per the secrets/auth rule.
- `_get_templates` (6 sequence modules) and `_fill`/`_set_setting` pairs have byte-identical bodies but each closes over a *different* module-level constant (e.g. each sequence's own `TEMPLATE_DEFAULTS`). Consolidating would require parameterizing and changing call signatures — i.e. it would not be behavior-neutral — so it is not a safe drop-in dedup.

Broken-doc-reference candidates (30 flagged by the static scan) were all investigated and are false positives or off-limits — nothing pending:
- Naming-convention examples (e.g. `content-agent/CLAUDE.md` "Name files clearly: `outputs/ad-copy-vet-lead-gen.md`").
- Runtime-generated / gitignored / cross-repo output paths documented correctly in skills (`src/content/blog-posts.json`, `public/index.html`, `public/assets/manifest.json`, `work/overland-park_t1.json`, `*.mp4` render outputs).
- Historical agent memory logs (`content-agent/memory.md` references to consumed `pending_approvals/blog-*.json`) and archived prior cleanup reports under `executive-assistant/archives/` — both are historical records that should not be edited.
- Client creative content (`media-buying-agent/clients/crosacore/...`) — business content.

## Archived
Retention (7-day) identified and archived the following from `executive-assistant/reports/` into `executive-assistant/archives/reports-2026-09/` (these moves were already committed and pushed to `main` ahead of this run — the retention pass confirmed the final state matches):
- daily-briefing-2026-09-21.md -> archives/reports-2026-09/daily-briefing-2026-09-21.md
- daily-briefing-2026-09-23.md -> archives/reports-2026-09/daily-briefing-2026-09-23.md
- daily-briefing-2026-09-25.md -> archives/reports-2026-09/daily-briefing-2026-09-25.md
- sheets-digest-2026-09-23.md -> archives/reports-2026-09/sheets-digest-2026-09-23.md
- sheets-digest-2026-09-24.md -> archives/reports-2026-09/sheets-digest-2026-09-24.md
- sheets-digest-2026-09-25.md -> archives/reports-2026-09/sheets-digest-2026-09-25.md
- weekly-cleanup-2026-09-27.md -> archives/reports-2026-09/weekly-cleanup-2026-09-27.md

## Flagged Stale Projects
Nothing flagged this week.
