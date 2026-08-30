# Lead Qualifier Agent

Scrapes small, independent, single-location physical therapy practices from Google Maps, qualifies them, and pushes qualified leads into the DigiGrowth OS CRM (`/api/contacts`, tagged `independent-pt`) for the dialer to work.

**Free pipeline** — no Google Places API, no Anthropic API billing. Google Maps is driven directly by Claude Code via the Playwright MCP browser tools; qualification/grading/opener-writing is Claude Code reasoning over the same rules the old paid pipeline used, not a metered API call. Runs entirely on the existing Claude subscription.

**Managed by:** Dylan's Executive Assistant — see `.claude/skills/manage-lead-qualifier/SKILL.md` in the `digigrowth-brain` repo
**Run via:** the `scrape-leads` Claude Code skill (`.claude/skills/scrape-leads/SKILL.md`) — invoke it directly, via `/loop`, or on a recurring local schedule (Windows Task Scheduler running `claude -p "run the scrape-leads skill"`, since the browser/MCP tooling only exists in a local Claude Code session, not on Railway).

## File Roles

| File | Purpose |
|---|---|
| `.claude/skills/scrape-leads/SKILL.md` | The pipeline itself — scrape (Playwright MCP), filter, qualify (Claude Code reasoning), push |
| `lib.py` | Free helper functions/CLI: website scraping, owner extraction, progress tracking, OS push — no AI, no paid API |
| `config.json` | Operational settings: `daily_lead_target` (checked after every search term, up to 5 cities per session — once met, the current city's remaining search terms still finish before the session stops; a city is never abandoned mid-term-list), `max_website_text_words`, `enabled` |
| `memory.txt` | Agent memory: blacklist, niche rules, opener criteria — read by Claude Code as instructions, unchanged from the old pipeline |
| `prompt.txt` | Qualification prompt template — same rules, now read directly instead of sent to an API |
| `role.txt` | Agent persona — same, now read directly |
| `progress.json` | Scraping cursor: `{state, city, term_index}` (auto-generated/updated) |
| `scraped_ids.json` | Dedup store, keyed `"<name>|<city>|<state>"` (auto-generated) |
| `run.py` | Retired — see its docstring. The old Places API + Batches API pipeline got too expensive at current volume. |

Secrets (`DASHBOARD_URL`, `DASHBOARD_PASSWORD`) live in the shared `digigrowth` Doppler vault (config `prd`), not a local `.env` file. `PLACES_API_KEY`/`ANTHROPIC_API_KEY` are no longer needed by this agent.

## Qualification Rules

- A lead is **not pushed** to the OS if it has no usable custom opener — better to drop a cold/generic lead here than hand it to the dialer with nothing personalized to open with.

## Security

Secrets live in Doppler, not in this repo. Never write them to a local `.env` file or commit them.
