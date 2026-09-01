"""
STUB — Meta/Facebook Graph API integration. Not implemented yet.

Nothing in this repo talks to the Meta Ads API today (no Graph API client, no
FB_/META_ env vars, no ad-account polling). This module is the intended home
for that integration once it's built.

When wiring the real thing:
- Poll each active client's Meta ad account on a schedule, mirroring the
  `_export_*` cron job pattern registered in main.py's lifespan() (see
  _export_sms_outreach_stats for the shape: a scheduler.add_job(...) calling
  an async function that queries an external source and persists the result).
- Upsert normalized rows into ad_campaign_stats, keyed on
  (client_id, platform, stat_date) via ON CONFLICT — spend/impressions/
  clicks/leads as typed columns, plus the full untouched API response in the
  `raw` JSONB column so nothing needs to be re-fetched if a new normalized
  field is needed later.
- Requires per-client Meta ad account IDs (add to the `clients` table or a
  new client_ad_accounts table) and app credentials — store FB_APP_ID /
  FB_APP_SECRET / any long-lived tokens in the shared `digigrowth` Doppler
  vault (see CLAUDE.md's Secrets convention), not in a local .env file.
- routers/client_portal.py's GET /portal-api/{token}/stats already reads
  from ad_campaign_stats and returns an empty array today — once this module
  populates that table, the portal stats endpoint needs no changes.
"""
