# Decision Log

Append-only. When a meaningful decision is made, log it here.

Format: [YYYY-MM-DD] DECISION: ... | REASONING: ... | CONTEXT: ...

---

[2026-05-03] DECISION: Built daily-briefing skill delivered via email (not WhatsApp) as Phase 1 | REASONING: Email is immediately available via Gmail MCP with no extra setup; WhatsApp requires Twilio account + webhook server + custom MCP tool — deferred to Phase 2 | CONTEXT: Dylan wants a 6AM EST daily brief covering business emails, calendar, cold calling/SMS outreach data from Google Drive, and time management suggestions

[2026-05-03] DECISION: Cold calling/SMS outreach section uses dynamic Google Drive search (keywords: cold call, outreach, calls, SMS, leads, GHL, tracking) rather than a hardcoded file path | REASONING: Dylan confirmed data is in Google Sheets in Drive but exact file name unknown; dynamic search picks it up automatically as long as file name contains recognizable keywords | CONTEXT: GHL has no MCP — data must be exported to Drive to appear in the brief

[2026-05-03] DECISION: EA manages Lead Qualifier via additionalDirectories + skill file (no central orchestration layer) | REASONING: Simplest correct approach — EA edits config files directly and triggers python run.py via Bash; no queues, no APIs, no wrappers needed; scales to multiple agents by repeating the same pattern | CONTEXT: Dylan wants EA to act as manager over all his agents; Lead Qualifier is a standalone Python script with prompt.txt, memory.txt, config.json as its control surface

[2026-05-04] DECISION: GitHub sync test #2 — added this line to decisions/log.md | REASONING: Dylan requested a repeat file change to confirm whether edits persist or push to GitHub | CONTEXT: First test showed the file reverted — persistence is not working between sessions

[2026-05-17] DECISION: Built sheets-digest skill to scan Google Sheets modified in last 24hrs and extract DigiGrowth KPIs into context/digigrowth-stats.md | REASONING: Dylan wants automated daily stats pulled from active sheets and fed back into the OS so the assistant always has current business metrics | CONTEXT: Stats categories cover outreach, pipeline, Meta ads, client delivery, and revenue — aligned with DigiGrowth's $10k MRR goal

[2026-08-31] DECISION: Added onboarding-agent to EA management via skill file (in-repo, no additionalDirectories entry needed) | REASONING: Dylan signed his first client and wants an automatic welcome email (next steps + Onboarding Call booking link) the moment a discovery call is marked Closed, and wants this built as a proper registered agent rather than a one-off script since he plans to expand it (client dashboard, contracts, kickoff docs) over time | CONTEXT: Logic lives in dashboard/backend/onboarding_sequence.py, hooked into routers/appointments.py's PATCH /appointment-reminders/{id} handler on the outcome_close -> 'closed' transition; editable email copy via dialer_settings and a new Business Resources -> Outreach Templates -> Onboarding Kickoff editor; ONBOARDING_CALENDLY_URL ships as a blank placeholder in integrations.py pending Dylan creating the 1-hour Calendly event type. v1 is email-only — SMS and an intake form were scoped out of the first pass.
