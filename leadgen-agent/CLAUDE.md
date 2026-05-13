# Lead Qualifier Agent

Scrapes fitness businesses from Google Maps, qualifies them using Claude AI, and exports results to a Google Sheet.

**Managed by:** Dylan's Executive Assistant — see `.claude/skills/manage-lead-qualifier/SKILL.md` in the `digigrowth-brain` repo
**Run via:** `python run.py` or `run_agent.bat`

## File Roles

| File | Purpose |
|---|---|
| `run.py` | Main pipeline — scrape, qualify, export |
| `config.json` | Operational settings: daily limit, model, sheet ID |
| `memory.txt` | Agent memory: blacklist, niche rules, opener criteria |
| `prompt.txt` | Qualification prompt template |
| `role.txt` | Agent persona |
| `progress.json` | Scraping state (auto-generated) |
| `scraped_ids.json` | Deduplication store (auto-generated) |
| `.env` | API keys — never commit |
| `credentials.json` | Google service account key — never commit |

## Security

`.env` and `credentials.json` are in `.gitignore`. Never commit them.
