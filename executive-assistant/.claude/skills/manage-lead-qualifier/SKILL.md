# Manage Lead Qualifier

Gives the EA direct control over the Lead Qualifier agent — read its state, update its config, and trigger runs.

**Agent location:** `leadgen-agent/` in the `digigrowth-brain` repo.

---

## File Map

| File | What it controls |
|---|---|
| `config.json` | `daily_lead_limit`, `model`, `max_website_text_words`, `enabled`, `anthropic_api_key_env` |
| `memory.txt` | Blacklist, niche definition, target markets, opener criteria and examples |
| `prompt.txt` | Qualification rules, grading criteria (A/B/C/D), opener rules, output format |
| `role.txt` | Agent persona — rarely needs changing |
| `progress.json` | Current state/city/search term position — read to see where it left off |
| `scraped_ids.json` | All processed place IDs — count to see total scraped |

Secrets (`ANTHROPIC_API_KEY`, `PLACES_API_KEY`, `DASHBOARD_URL`, `DASHBOARD_PASSWORD`) live in the shared `digigrowth` Doppler vault (config `prd`), not a local `.env` file — never read aloud, never edit directly.

---

## Run Commands

**Run the full pipeline:**
```bash
cd "$(git rev-parse --show-toplevel)/leadgen-agent" && doppler run -- python run.py
```

**Append to agent memory (updates memory.txt):**
```bash
cd "$(git rev-parse --show-toplevel)/leadgen-agent" && doppler run -- python run.py remember "blacklist a new corporate PT chain — not the right niche"
```

Runs are skipped automatically on weekends (the script checks `weekday()`).

---

## Common Tasks

### Add something to the blacklist
1. Edit `memory.txt` — find `CHAIN / FRANCHISE BLACKLIST:` and append the name
2. Also add the lowercase version to the `CHAIN_KEYWORDS` list in `run.py` so the pre-filter catches it before an API call is made

### Change the daily lead limit
Edit `config.json` → `daily_lead_limit`. Current default: 10.

### Change the model
Edit `config.json` → `model`. Currently `claude-sonnet-4-6`.

### Pause the agent
Edit `config.json` → set `enabled` to `false`. `run.py` checks this at the top of `run_pipeline()` and skips the run entirely (no API calls made). Set back to `true` to resume.

### Focus on a specific state
Edit `progress.json` → set `current_state_index` to the index of the target state.
States are listed alphabetically in `run.py`'s `US_STATES` dict (Alabama = 0, Alaska = 1, etc.).
To reset to the very beginning: set all three index fields to 0.

### Update qualification criteria
- Edit `memory.txt` for persistent rules the agent reads every run
- Edit `prompt.txt` to change the actual qualification logic (grading, disqualify rules, opener format)
Both files are read fresh on each run — changes take effect immediately.

### Check last run status
- Read `progress.json` — shows current state, city, and search term position
- Count entries in `scraped_ids.json` — total unique businesses processed

---

## Current Standing Directives

*Dylan updates this section to give ongoing orders to the EA about this agent.*

- Run on weekdays — currently triggered manually by Dylan or EA
- Default lead limit is 10/day — only change if Dylan asks

---

## Notes

- The agent resumes mid-state via `progress.json` — no need to restart from scratch after an interruption
- To fully reset (start over from Alabama): delete `progress.json` or set all index fields to 0
- A typical run takes 5–15 minutes depending on rate limits and site scraping speed
- Qualified leads are pushed to the DigiGrowth OS CRM sorted A → B → C → D grade automatically (tagged `mobile-pt`, status defaults to `dialer-lead`)
