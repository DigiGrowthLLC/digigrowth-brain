# Lead Qualifier Agent

Scrapes independent mobile/in-home physical therapy practices from Google Maps, qualifies them using Claude AI, and pushes qualified leads into the DigiGrowth OS CRM (`/api/contacts`, tagged `mobile-pt`) for the dialer to work.

**Managed by:** Dylan's Executive Assistant — see `.claude/skills/manage-lead-qualifier/SKILL.md` in the `digigrowth-brain` repo
**Run via:** `doppler run -- python run.py`

## File Roles

| File | Purpose |
|---|---|
| `run.py` | Main pipeline — scrape, qualify, push to CRM |
| `config.json` | Operational settings: `daily_lead_limit`, `model`, `max_website_text_words`, `enabled` |
| `memory.txt` | Agent memory: blacklist, niche rules, opener criteria |
| `prompt.txt` | Qualification prompt template |
| `role.txt` | Agent persona |
| `progress.json` | Scraping state (auto-generated) |
| `scraped_ids.json` | Deduplication store (auto-generated) |

Secrets (`ANTHROPIC_API_KEY`, `PLACES_API_KEY`, `DASHBOARD_URL`, `DASHBOARD_PASSWORD`) live in the shared `digigrowth` Doppler vault (config `prd`), not a local `.env` file.

## Qualification Rules

- A lead is **not pushed** to the OS if it has no usable custom opener (`run.py`, `run_pipeline()`) — better to drop a cold/generic lead here than hand it to the dialer with nothing personalized to open with.

## Security

Secrets live in Doppler, not in this repo. Never write them to a local `.env` file or commit them.
