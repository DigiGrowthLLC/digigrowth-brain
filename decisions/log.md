# Decision Log

Append-only. When a meaningful decision is made, log it here.

Format: [YYYY-MM-DD] DECISION: ... | REASONING: ... | CONTEXT: ...

---

[2026-05-03] DECISION: Built daily-briefing skill delivered via email (not WhatsApp) as Phase 1 | REASONING: Email is immediately available via Gmail MCP with no extra setup; WhatsApp requires Twilio account + webhook server + custom MCP tool — deferred to Phase 2 | CONTEXT: Dylan wants a 6AM EST daily brief covering business emails, calendar, cold calling/SMS outreach data from Google Drive, and time management suggestions

[2026-05-03] DECISION: Cold calling/SMS outreach section uses dynamic Google Drive search (keywords: cold call, outreach, calls, SMS, leads, GHL, tracking) rather than a hardcoded file path | REASONING: Dylan confirmed data is in Google Sheets in Drive but exact file name unknown; dynamic search picks it up automatically as long as file name contains recognizable keywords | CONTEXT: GHL has no MCP — data must be exported to Drive to appear in the brief

[2026-05-03] DECISION: EA manages Lead Qualifier via additionalDirectories + skill file (no central orchestration layer) | REASONING: Simplest correct approach — EA edits config files directly and triggers python run.py via Bash; no queues, no APIs, no wrappers needed; scales to multiple agents by repeating the same pattern | CONTEXT: Dylan wants EA to act as manager over all his agents; Lead Qualifier is a standalone Python script with prompt.txt, memory.txt, config.json as its control surface
