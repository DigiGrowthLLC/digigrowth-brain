# Weekly Cleanup — 2026-10-11

## Auto-Fixed
- Nothing auto-fixed this week. The detection scan produced the same candidate set as last week (0 unused imports, 2 zero-caller functions, 30 broken-doc-reference flags, 8 duplicate-function groups) and no code files changed since the last run. Every candidate was re-investigated individually with grep/read and none cleared the "very high confidence + provably behavior-neutral + no secrets" bar for a direct fix — details below.

## Needs Approval
Recurring items (unchanged from prior weeks — repeated here only so they stay visible; no new action required unless Dylan wants to act):

- `dashboard/backend/calendly_integration.py` — `unregister_webhook`: re-verified zero callers anywhere in the repo (grepped `.py`/`.jsx`/`.js`/`.md`). Clean symmetric counterpart to `register_webhook`, so it reads as a reserved operational/admin helper for Calendly webhook lifecycle rather than dead code. Recurring (also 2026-09-20, 2026-09-27, 2026-10-04). Recommendation: keep as a reserved utility; safe to delete only if Dylan confirms no planned manual/admin use. Not auto-removed — feature-removal judgment call whose necessity cannot be proven zero.
- `media-buying-agent/tools/ad_overlays.py` — `lower_third`: zero callers (the only consumer, `assemble_ugc_ad.py`, uses `hook_card`/`proof_card`/`end_card`/`font`/`chunk_words`/`write_ass` but not `lower_third`). One of a family of composable ad-overlay primitives (`set_palette`, `text_block`, `wrap` are likewise uncalled), so it reads as an intentionally reserved creative primitive. Recurring. Recommendation: keep unless the overlay toolkit is being deliberately trimmed. Not auto-removed — content/feature judgment call.
- `dashboard/backend/routers/watch.py` + `dashboard/backend/routers/landing_pages.py` — `_safe_slug` (byte-identical ~4-line slug validator) and `dashboard/backend/client_email.py` + `dashboard/backend/email_identities.py` — `_extract_email` (byte-identical 3-line regex helper): each pair is consolidatable and behavior-neutral, but consolidating introduces new cross-module import coupling for a trivial private helper and there is no shared backend util module yet. Recommendation: low priority; defer until a shared `routers`/backend util module is introduced. Not auto-applied — architectural call.

Duplicates deliberately NOT recommended for consolidation (noted so they are not re-flagged as actionable):
- `doppler_secret` (8 files across `design-agent/tools/` and `content-agent/tools/`), `_client_creds`/`_identity_google_creds`, and `_master_client`/`_twilio` all construct secrets/OAuth/Twilio credentials — off-limits per the secrets/auth rule, and each is a deliberate self-contained per-agent CLI-tool copy.
- `_get_templates` (6 sequence modules) and the `_fill`/`_set_setting` pairs have byte-identical bodies but each closes over a *different* module-level constant (each sequence's own template defaults), so a drop-in dedup would change behavior — not behavior-neutral, not safe.

Broken-doc-reference candidates (30 flagged by the static scan) were all re-investigated and are false positives or off-limits — nothing pending:
- Naming-convention examples (e.g. `content-agent/CLAUDE.md` "Name files clearly: `outputs/ad-copy-vet-lead-gen.md`", `outputs/email-sequence-cold-outreach.md`, ending in "etc.").
- Runtime-generated / gitignored / cross-repo output paths documented correctly in skills (`out/page.html`, `dist/index.html`, `public/index.html`, `public/assets/manifest.json`, `work/overland-park_t1.json`, `src/content/blog-posts.json`, `*.mp4` render outputs).
- Historical agent memory logs (`content-agent/memory.md` references to already-consumed `pending_approvals/blog-*.json`) and archived prior cleanup reports under `executive-assistant/archives/` — both are historical records that must not be edited.
- Client creative content (`media-buying-agent/clients/crosacore/...`) — business content.

## Archived
Retention (7-day) archived the following from `executive-assistant/reports/` into `executive-assistant/archives/reports-YYYY-MM/` (each write + delete committed and pushed to `main`):
- cold-calling-resync-2026-09-28.md -> archives/reports-2026-09/cold-calling-resync-2026-09-28.md
- daily-briefing-2026-09-28.md -> archives/reports-2026-09/daily-briefing-2026-09-28.md
- daily-briefing-2026-09-29.md -> archives/reports-2026-09/daily-briefing-2026-09-29.md
- daily-briefing-2026-09-30.md -> archives/reports-2026-09/daily-briefing-2026-09-30.md
- daily-briefing-2026-10-01.md -> archives/reports-2026-10/daily-briefing-2026-10-01.md
- daily-briefing-2026-10-02.md -> archives/reports-2026-10/daily-briefing-2026-10-02.md
- sheets-digest-2026-09-28.md -> archives/reports-2026-09/sheets-digest-2026-09-28.md
- sheets-digest-2026-09-29.md -> archives/reports-2026-09/sheets-digest-2026-09-29.md
- sheets-digest-2026-09-30.md -> archives/reports-2026-09/sheets-digest-2026-09-30.md
- sheets-digest-2026-10-01.md -> archives/reports-2026-10/sheets-digest-2026-10-01.md
- sheets-digest-2026-10-02.md -> archives/reports-2026-10/sheets-digest-2026-10-02.md
- weekly-cleanup-2026-10-04.md -> archives/reports-2026-10/weekly-cleanup-2026-10-04.md

## Flagged Stale Projects
Nothing flagged this week. The only entry under `executive-assistant/projects/` (`ai-process-integration`) has git activity within the last 60 days.
