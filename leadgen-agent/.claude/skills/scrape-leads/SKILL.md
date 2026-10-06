---
name: scrape-leads
description: Scrape, qualify, grade, and push small independent single-location PT practice leads to the DigiGrowth OS — free pipeline using the Playwright MCP browser (Google Maps) and Claude Code's own reasoning (qualification), no paid APIs.
---

# Scrape Leads

Free replacement for the old `leadgen-agent/run.py` pipeline. No Google Places API, no Anthropic API billing — Google Maps is driven directly via the Playwright MCP browser tools, and qualification/grading/opener-writing is done by you (Claude Code), reading `role.txt` + `memory.txt` + `prompt.txt` as instructions, the same way you'd read any other skill.

Requires the `playwright` MCP server (configured in the repo's `.mcp.json`) — its browser tools (`browser_navigate`, `browser_snapshot`, `browser_click`, `browser_evaluate`, etc.) must be available in this session. If they aren't, tell the user to restart their Claude Code session so the MCP server loads.

Before starting, check `config.json` — if `"enabled": false`, stop and report that leadgen is paused.

**Never background this work.** Do all scraping, qualification, and pushing synchronously in the current turn — never delegate any part of it to a background task/subagent, and never respond with something like "I'll wait for the background scrape to finish" or "I've kicked this off and will check back." This skill runs unattended via `claude -p` (see `run-scrape-leads.ps1`), which exits the instant a response is produced for the turn — a background task has no later turn to report back to, so backgrounding silently kills the whole run after only a few files get touched. If Playwright browser calls are slow, that's fine; just make them inline and keep going in the same turn until step 9's report is posted.

**This invocation keeps going city after city until `lead_target_per_run` is met — there is no city cap.** Each city gets all 4 terms before the next one starts. After each city is finished (step 7's `city-finish` done, step 9 report posted), check the `run_tally` that `city-finish` printed: if `qualified` has met `lead_target_per_run`, stop (the target landing mid-city still means that city's remaining terms finish first — see step 2). Also stop if `city-next` returns `{"done": true}`. Otherwise call `python lib.py city-next` for the next city and go back to step 1's output (skip re-reading the rules files — you already have them). **Keep context lean across cities:** Maps extractions and site scrapes go to files in `work/` (steps 3-5), and you only read the paged `digest`. Never dump snapshots or raw feed JSON into the conversation. **Exception — the unattended wrapper:** `run-scrape-leads.ps1` launches a fresh `claude -p` process per city (so each process starts with a clean context) and its prompt says to cover *exactly one city*. When the invoking prompt says one city, do exactly one city and stop; the wrapper decides between processes whether to launch another.

## 1. Load state

**The lead target is per run, not per day.** Every invocation of this skill is one run with its own `lead_target_per_run` (default 100, from `config.json`): a manual run and the nightly scheduled run each aim for 100, regardless of how many leads other runs pushed earlier that day. At the very start, get a run ID: if the invoking prompt gives you a `run_id` (the unattended wrapper does), use that and do **not** call `run-start`; otherwise run `python lib.py run-start manual` once and keep the `run_id` it prints for the whole invocation. Pass it to `city-finish` (step 7).

Run `python lib.py city-next` (from `leadgen-agent/`) — this is the **only** source of truth for which city to work on; don't reason about it yourself. It returns `{"city": ..., "state": ..., "term_index": N, "resuming": bool}`, or `{"done": true}` if nothing is due (extremely unlikely — the list covers 147 US cities plus a 90-day cooldown revisit cycle). `term_index` tells you which of the 4 search terms to start from (0 = first term; a nonzero value means this city was interrupted mid-run last time — `resuming: true`).

Never read `scraped_ids.json` (~1 MB) or `lib.py`'s source. Every command you need is listed below, and `city-prep` handles scraped-id dedup.

## 2. Markets and search terms

City selection is fully code-driven now (`city_coverage.json`, via `lib.py city-next`/`city-record-progress`) — it deterministically walks a fixed, population-ranked list of 147 US cities, tracks each city's status (`not_started` / `in_progress` / `covered`), and only revisits a `covered` city after a 90-day cooldown (catches new-business churn without re-treading the same ground). This replaced an earlier markdown-table-driven approach that caused the same cities to get re-picked across separate unattended sessions while others never got reached — see `leadgen-agent` memory notes if curious why this exists. You never need to pick a city yourself or ask the user which market comes next; `city-next` always has an answer.

**Each city gets all 4 search terms, in order** (that's what "covering the city's TAM" means here: each term surfaces a different, overlapping slice of the market, and running all 4, each scrolled to exhaustion per step 3, is how you get to roughly 90%+ real coverage of what's actually out there). **A city, once started, is never abandoned mid-term-list — all 4 terms always run**, even if `lead_target_per_run` gets hit partway through.

- After each city's leads are pushed, check the `run_tally` that step 7's `city-finish` prints (or `python lib.py run-tally <run_id>`): compare its `qualified` count against its `target` (`lead_target_per_run`). **Always use this tally — never track the target against your own in-session count.** One run spans several `claude -p` processes (the wrapper launches one per city; a session-limit resume is a fresh process), and an in-session tally would silently reset to zero and blow well past the target (this happened 2026-09-03: three resumes pushed 176 qualified leads against a target of 100). `run-tally` sums the per-term counts logged under this `run_id` in `runs.json`, so it's correct no matter how many processes this run has used. Don't use `daily-tally` for the target: it mixes in other runs from the same day (on 2026-09-30 a morning manual run made the 8pm scheduled run stop after one city).
- Once the city is finished, report (step 9). Then apply the multi-city check from the top of this skill: stop if the target is met (or if the invoking prompt said one city only); otherwise move on to the next city from `city-next`.

Search terms (run each per city):
```
physical therapy
physical therapist
outpatient physical therapy
sports physical therapy
```

## Working files and commands

All of a city's intermediate files go in `leadgen-agent/work/` (gitignored; create it if missing), named `<cityslug>_*` (e.g. `work/overland-park_t1.json`). Run every `lib.py` command from `leadgen-agent/`. **Use only these commands. Don't write your own helper scripts or batching wrappers, and don't read `lib.py` to figure out how they work.** Each one already does the batching/parallelism a hand-written helper would.

The flow per city: extract all remaining terms in the browser (step 3) → `city-prep` (step 4) → `scrape-batch` + `digest` (step 5) → qualify (step 6) → `city-finish` (step 7) → report (step 9).

## 3. Scrape Google Maps (Playwright MCP): 2 calls per term

For each remaining term of this city (from `term_index` to the 4th), in order:
1. `browser_navigate` to `https://www.google.com/maps/search/<term url-encoded> in <city>, <state>`.
2. One `browser_evaluate` with `filename: "leadgen-agent/work/<cityslug>_t<term number 1-4>.json"` and exactly this function. It scrolls the feed to the end and extracts every listing in the same call:
```js
async () => { const f = document.querySelector('[role="feed"]'); if (!f) return {feed:false, listings:[]}; let counts=[], stall=0, prev=-1, end=false; for (let i=0;i<40 && stall<3;i++){ for(let j=0;j<3;j++){ f.scrollTop=f.scrollHeight; await new Promise(r=>setTimeout(r,1500)); } const n=f.querySelectorAll('a.hfpxzc').length; counts.push(n); if(n===prev) stall++; else stall=0; prev=n; if(/reached the end of the list/i.test(f.innerText)){ end=true; break; } } const listings=[]; f.querySelectorAll('div.Nv2PK').forEach(c=>{ const a=c.querySelector('a.hfpxzc'); if(!a) return; const ph=c.querySelector('.UsdlK'); const w=c.querySelector('a[data-value="Website"]'); listings.push({name:a.getAttribute('aria-label'), phone: ph?ph.textContent.trim():'', website: w?w.href:''}); }); return {feed:true, end, counts, listings}; }
```
It stops only on the "end of the list" text or three consecutive scroll batches with no new listings, which is the full-coverage rule, so don't shorten it. Never use `browser_snapshot` unless this comes back `feed:false` or with 0 listings; then take one snapshot to see why (consent page, layout change), fix, and retry that term.

## 4. Free filters: `city-prep`

```
doppler run --project digigrowth --config prd -- python lib.py city-prep "<city>" "<state>" <term_index from city-next> work/<cityslug>_prep.json work/<cityslug>_t<N>.json ...
```
List the term files in term order, starting at the first term this process ran. In one pass it:
- dedupes listings across the city's terms
- drops everything already in the OS CRM (phone/website match). This is the real dedup: `scraped_ids.json` keys on name+city, so a clinic from a neighboring city's search would slip past it alone.
- drops already-scraped listings
- skips no-phone/no-website listings, `memory.txt`'s chain blacklist, and institutional keywords (hospital, home health, chiropractic, university, …)

It prints per-term counts, the skipped names, and the candidate list as `idx | name | domain | term`. It writes nothing to `scraped_ids.json`; `city-finish` does that. If it errors (network/auth on the CRM fetch), retry it. Never continue without it.

**Reviewed count** (recorded automatically): each business counts **once per city**, on the term where it first appeared, if it wasn't already in the CRM or already scraped. Don't compute your own.

## 5. Website scrape: `scrape-batch` + `digest`

First, look at the candidate list's names and domains alone and pick the candidates that are *obviously* disqualified: a named hospital/health system, a known multi-location group or chain not on the blacklist, or clearly not PT (massage, gym, chiropractor, pediatric-only by name). Only exclude when the name makes it certain. Anything plausibly an independent PT practice gets scraped. Then:
```
python lib.py scrape-batch work/<cityslug>_prep.json work/<cityslug>_sites.json --exclude "3:Baptist Health system;7:massage;12:Athletico"
```
It runs `scrape-site` on every non-excluded candidate in parallel and prints a short summary, including `empty_text_idx`. (`scrape-site` fetches homepage + /about + /about-us + /contact + /contact-us, extracts the owner via regex/JSON-LD, picks the best email, and truncates text to `max_website_text_words`.) Then read the results a page at a time:
```
python lib.py digest work/<cityslug>_prep.json work/<cityslug>_sites.json <start_idx> 12
```
Each page ends with the `start_idx` for the next page. Read every page. If a site is in `empty_text_idx` and looks like a plausible independent PT, you may open it with `browser_navigate` + one `browser_evaluate` returning `document.body.innerText.slice(0,2500)` to find the owner. Never use a snapshot for this.

`email` priority: owner-name match > `contact@`/`info@`/`hello@`/`office@`/`admin@` > anything else. Junk is pre-filtered. Empty is fine; never fabricate one.

## 6. Qualify, grade, verify owner, write opener: YOU do this now

For each candidate, apply `role.txt`, `memory.txt`, and `prompt.txt` in full: same disqualification rules, same A–D grading, same owner-verification requirement, same opener rules and priority order. Reason over the digest's business name/phone/website/owner/text exactly as `prompt.txt` instructs.

Guardrails (city-finish re-checks the first two and rejects failures, so get them right here):
- `Owner Name` must be a real 2-3 word person name verified on the practice's own site, otherwise disqualify. Titles like "Dr." and trailing credentials like ", DPT" are fine.
- Opener ≤15 words, no `?`.
- **No usable opener → don't push.**

## 7. Push + record: `city-finish`

Write the qualified leads to `work/<cityslug>_leads.json` as a list. Each lead must include the candidate's `idx` from the digest:
```json
{"idx": 4, "Business Name": "...", "Owner Name": "...", "Phone": "...", "Website": "...", "Email": "...",
 "Grade": "A", "Grade Reason": "...", "Opener": "...", "City": "...", "State": "..."}
```
Then run, once:
```
doppler run --project digigrowth --config prd -- python lib.py city-finish work/<cityslug>_prep.json work/<cityslug>_leads.json <run_id> [status]
```
`status` defaults to `new`; pass `sms-handoff` only if the user says so. In one call it:
- applies the guardrails
- POSTs to `/api/contacts` tagged `independent-pt`, re-checking a fresh CRM index and skipping existing contacts
- marks every listing this city reviewed as scraped
- runs `city-record-progress` for every term this process covered under `run_id` (reaching term 4 marks the city `covered`)
- prints the city's counts by term and grade, plus the `run_tally`

**`pushed_new` is the qualified count**, not the number of leads you wrote. It refuses to run twice on the same prep file. If it reports `failed` pushes, retry those leads once with `doppler run ... python lib.py push <file>`. Those leads won't be in the run tally; mention that in the report.

If you ever must stop mid-city (you shouldn't), don't call `city-finish` with partial data. The city stays at its previous `term_index` and gets redone cleanly by the next process.

## 8. Update state

Done by `city-finish`. The per-city flow no longer has a separate `scraped-add`/`city-record-progress` step. Those commands still exist for one-off manual fixes.

## 9. Report

After the city, tell the user about **that city**: listings reviewed, disqualified (a one-line reason breakdown), qualified with grades, and anything a human should double-check (non-owner contact, odd email domain, near-misses). Keep it short. Take the numbers from `city-finish`'s output rather than counting yourself.

**Also post the summary into the OS chat**, so unattended results are visible from the dashboard. Write a short markdown file in `work/` with this shape and run `doppler run --project digigrowth --config prd -- python lib.py post-chat <path>` (dashboard → Agents → Lead Qualifier). Do this even if the target wasn't reached.

```
## Lead gen run — <date>

**<City>, <ST>** (4/4 terms): <reviewed> reviewed → <qualified> qualified (<A count> A, <B count> B, <C count> C, <D count> D)

**This run's total:** <run_tally reviewed> reviewed → <run_tally qualified> qualified — qualification rate <qualified/reviewed as %>
Target: <lead_target_per_run> per run — <met/exceeded by N / fell short by N so far>
```

Leave `work/` alone. It's gitignored and the wrapper clears it, so don't spend turns deleting files.
