# Lead Qualifier Agent

Scrapes independent mobile/in-home veterinary practices from Google Maps, qualifies them using Claude AI, and pushes qualified leads into the DigiGrowth OS CRM (`/api/contacts`, tagged `mobile-vet`) for the dialer to work.

**Managed by:** Dylan's Executive Assistant — see `.claude/skills/manage-lead-qualifier/SKILL.md` in the `digigrowth-brain` repo
**Run via:** `python run.py` or `run_agent.bat`

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
| `.env` | API keys — never commit |

## Security

`.env` and `credentials.json` are in `.gitignore`. Never commit them.
