# Manage Lead Qualifier

Gives the EA direct control over the Lead Qualifier agent — read its state, update its config, and trigger runs.

**Agent location:** `leadgen-agent/` in the `digigrowth-brain` repo.

---

## File Map

| File | What it controls |
|---|---|
| `.claude/skills/scrape-leads/SKILL.md` | The pipeline itself — free, runs via Claude Code + Playwright MCP instead of paid APIs |
| `lib.py` | Free helper CLI: website scraping, progress tracking, OS push |
| `config.json` | `daily_lead_limit`, `max_website_text_words`, `enabled` |
| `memory.txt` | Blacklist, niche definition, target markets, opener criteria and examples |
| `prompt.txt` | Qualification rules, grading criteria (A/B/C/D), opener rules, output format |
| `role.txt` | Agent persona — rarely needs changing |
| `progress.json` | Current state/city/search-term-index position — read to see where it left off |
| `scraped_ids.json` | All processed leads, keyed `"<name>|<city>|<state>"` — count to see total scraped |

Secrets (`DASHBOARD_URL`, `DASHBOARD_PASSWORD`) live in the shared `digigrowth` Doppler vault (config `prd`), not a local `.env` file — never read aloud, never edit directly. `PLACES_API_KEY`/`ANTHROPIC_API_KEY` are no longer used by this agent (the old paid pipeline was retired — too expensive at current volume).

---

## Run Commands

**Run the pipeline:** invoke the `scrape-leads` skill in a local Claude Code session (it needs the Playwright MCP browser tools from this repo's `.mcp.json`, which only load locally — not on Railway):
```
/scrape-leads
```

**Append to agent memory:** edit `memory.txt` directly (see "Update qualification criteria" below) — there's no longer a `remember` CLI subcommand since there's no standalone script driving the pipeline.

There's no automatic Railway cron for this anymore (the old `leadgen-daily` job was removed along with the paid pipeline it drove) — runs are manual, `/loop`, or a local Windows Task Scheduler entry calling `claude -p "run the scrape-leads skill"`.

---

## Common Tasks

### Add something to the blacklist
Edit `memory.txt` — find `CHAIN / FRANCHISE BLACKLIST:` and append the name. `scrape-leads/SKILL.md` reads this list fresh every run, so no code change needed.

### Change the daily lead limit
Edit `config.json` → `daily_lead_limit`. Current default: 30. Each `scrape-leads` run covers up to 3 cities (stopping early once the limit is hit) — multiple runs may still be needed if a market is sparse or the limit is set high.

### Pause the agent
Edit `config.json` → set `enabled` to `false`. The `scrape-leads` skill checks this first and stops immediately if disabled. Set back to `true` to resume.

### Focus on a specific market
Edit `progress.json` → set `state`/`city` to the target market, `term_index` to `0`.
To reset to the very beginning: set `state`/`city` back to `""`.

### Update qualification criteria
- Edit `memory.txt` for persistent rules the agent reads every run
- Edit `prompt.txt` to change the actual qualification logic (grading, disqualify rules, opener format)
Both files are read fresh on each run by Claude Code — changes take effect immediately.

### Check last run status
- Read `progress.json` — shows current state, city, and search-term-index position
- Count entries in `scraped_ids.json` — total unique businesses processed

---

## Current Standing Directives

*Dylan updates this section to give ongoing orders to the EA about this agent.*

- Runs are free (Claude subscription only, no paid API) — driven by Claude Code + Playwright MCP locally, no Railway cron
- Currently triggered manually by Dylan or EA; ask before setting up recurring local scheduling
- Default lead limit is 10/day — only change if Dylan asks

---

## Notes

- The agent resumes via `progress.json` (`state`/`city`/`term_index`) — no need to restart from scratch after an interruption
- To fully reset (start over from the top of the Sun Belt priority list): set `state`/`city` back to `""` in `progress.json`
- Each `scrape-leads` run covers one city × all 4 search terms at a time, continuing to the next city in the queue (up to 3 cities per run) as long as `daily_lead_limit` hasn't been reached yet — run it again (or loop it) if more is still needed after that
- Qualified leads are pushed to the DigiGrowth OS CRM sorted A → B → C → D grade automatically (tagged `independent-pt`, status defaults to `dialer-lead`)
