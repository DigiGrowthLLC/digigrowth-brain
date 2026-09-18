---
name: scrape-leads
description: Scrape, qualify, grade, and push small independent single-location PT practice leads to the DigiGrowth OS — free pipeline using the Playwright MCP browser (Google Maps) and Claude Code's own reasoning (qualification), no paid APIs.
---

# Scrape Leads

Free replacement for the old `leadgen-agent/run.py` pipeline. No Google Places API, no Anthropic API billing — Google Maps is driven directly via the Playwright MCP browser tools, and qualification/grading/opener-writing is done by you (Claude Code), reading `role.txt` + `memory.txt` + `prompt.txt` as instructions, the same way you'd read any other skill.

Requires the `playwright` MCP server (configured in the repo's `.mcp.json`) — its browser tools (`browser_navigate`, `browser_snapshot`, `browser_click`, `browser_evaluate`, etc.) must be available in this session. If they aren't, tell the user to restart their Claude Code session so the MCP server loads.

Before starting, check `config.json` — if `"enabled": false`, stop and report that leadgen is paused.

**Never background this work.** Do all scraping, qualification, and pushing synchronously in the current turn — never delegate any part of it to a background task/subagent, and never respond with something like "I'll wait for the background scrape to finish" or "I've kicked this off and will check back." This skill runs unattended via `claude -p` (see `run-scrape-leads.ps1`), which exits the instant a response is produced for the turn — a background task has no later turn to report back to, so backgrounding silently kills the whole run after only a few files get touched. If Playwright browser calls are slow, that's fine; just make them inline and keep going in the same turn until step 9's report is posted.

## 1. Load state

Run `python lib.py city-next` (from `leadgen-agent/`) — this is the **only** source of truth for which city to work on; don't reason about it yourself. It returns `{"city": ..., "state": ..., "term_index": N, "resuming": bool}`, or `{"done": true}` if nothing is due (extremely unlikely — the list covers 147 US cities plus a 90-day cooldown revisit cycle). `term_index` tells you which of the 4 search terms to start from (0 = first term; a nonzero value means this city was interrupted mid-run last time — `resuming: true`).

Also read `scraped_ids.json` (or use `python lib.py scraped-has <id>`) for dedup — `<id>` is `"<business name>|<city>|<state>"` lowercased (no Places `place_id` available anymore).

## 2. Markets and search terms

City selection is fully code-driven now (`city_coverage.json`, via `lib.py city-next`/`city-record-progress`) — it deterministically walks a fixed, population-ranked list of 147 US cities, tracks each city's status (`not_started` / `in_progress` / `covered`), and only revisits a `covered` city after a 90-day cooldown (catches new-business churn without re-treading the same ground). This replaced an earlier markdown-table-driven approach that caused the same cities to get re-picked across separate unattended sessions while others never got reached — see `leadgen-agent` memory notes if curious why this exists. You never need to pick a city yourself or ask the user which market comes next; `city-next` always has an answer.

**One run covers up to 10 cities.** For each city, work through its 4 search terms in order — that's what "covering the city's TAM" means here (each term surfaces a different, overlapping slice of the market; running all 4, each scrolled to exhaustion per step 3, is how you get to roughly 90%+ real coverage of what's actually out there). **A city, once started, is never abandoned mid-term-list — all 4 terms always run**, even if the target gets hit partway through. `config.json`'s `daily_lead_target` is a **target, checked after every search term, but it only stops the run at a city boundary, never mid-city**:
- After each search term's leads are qualified and pushed (steps 3-7), run `python lib.py daily-tally` and check its `qualified` count against `daily_lead_target`. **Always use this command — never track the target against your own in-session count.** An interrupted run (session limit, or the backgrounding bug) gets resumed as a brand-new `claude -p` process with no memory of earlier progress; an in-session tally would silently reset to zero and blow well past the target across resumes (this happened 2026-09-03: three resumes pushed 176 qualified leads against a target of 100). `daily-tally` sums every city touched today directly from `city_coverage.json`, so it's correct regardless of how many times this run has restarted today.
- If you've met or passed the target and more terms remain in the current city, **keep going anyway** — finish the current city's remaining terms before stopping. Note internally that the target's been met so you know to stop once the city wraps.
- If the target isn't met yet and more terms remain in the current city, continue to the next term (same as above — you're continuing either way).
- Once the current city's 4 terms are exhausted: if the target has been met or passed at any point during this city, **stop** — do not start a new city. If the target still isn't met, check whether you've already done 10 cities this session — if so, stop regardless of the target (per-run cap, keeps sessions bounded and reviewable). Otherwise call `python lib.py city-next` again for the next city (see step 8), and continue.

So a session is a sequence of search terms across up to 10 cities, checked after each one via `daily-tally`: term → check target → term → check target → ... → the moment the target is met, finish out the rest of the current city's terms, then stop — or stop after 10 cities' worth of terms are exhausted with the target still unmet, whichever comes first. **A state boundary is not a stopping point** — `city-next` may hand you cities in different states back to back; treat that exactly like moving to the next city on a single list, no different treatment, no waiting for confirmation.

Search terms (run each per city):
```
physical therapy
physical therapist
outpatient physical therapy
sports physical therapy
```

## 3. Scrape Google Maps (Playwright MCP)

For each search term, for the current city:
1. `browser_navigate` to `https://www.google.com/maps/search/<term url-encoded> in <city>, <state>`
2. Take a `browser_snapshot` to confirm the results feed loaded.
3. Scroll the results feed to load **every** listing — this is what makes the 4-terms-per-city coverage actually hit ~90%+ of real TAM; stopping early here undermines the whole point of running 4 terms. Use `browser_evaluate` with `document.querySelector('[role="feed"]').scrollTop = document.querySelector('[role="feed"]').scrollHeight`, wait ~3-4 seconds, `browser_snapshot` again, and count listings each time. **Do not stop just because growth has slowed** — Google Maps loads results in batches and a pause between batches is normal, not the end of the list. Only stop once you get **three consecutive scroll+wait cycles with zero new listings**, or the snapshot explicitly shows "You've reached the end of the list" / equivalent end-of-results text. If a batch is slow to load, wait longer (up to ~6-8 seconds) and try again before counting it toward the three-in-a-row — a slow batch is not a stalled one. Don't scroll the map itself.
4. From the snapshot, extract each listing's business name, phone number, and website URL (click into a listing or read the feed panel detail as needed — address is a bonus, not required).

## 4. Free filters (no cost — do this before visiting any website)

Skip a listing immediately if any of these are true:
- Already scraped: `python lib.py scraped-has "<name>|<city>|<state>"` exits 0
- No phone number, or no website
- The name matches a chain/franchise or an obviously non-PT business — check against `memory.txt`'s `CHAIN / FRANCHISE BLACKLIST` and these institutional keywords: hospital, home health, nursing home, skilled nursing, hospice, urgent care, behavioral health, addiction, mental health, psychiatric, chiropractic, chiropractor, home care, va medical, rehabilitation hospital, assisted living, senior living, physical therapy school, university

For everything skipped, still run `python lib.py scraped-add "<name>|<city>|<state>"` so it isn't re-checked next run.

## 5. Website scrape (free — no browser needed here)

For each survivor: `python lib.py scrape-site <website_url>` — returns JSON `{owner_name, website_text, email}` (homepage + /about + /about-us + /contact + /contact-us, JSON-LD/regex owner extraction, mailto:/regex email extraction, already truncated to `max_website_text_words`). This is a plain HTTP fetch, not a Playwright call — no need to open it in the browser.

`email` is picked in priority order: an address whose local part matches the verified owner's name (e.g. `sarah@...` for Sarah Jones) beats a generic `contact@`/`info@`/`hello@`/`office@`/`admin@` address, which beats whatever else was found on the page. Junk addresses (`noreply@`, image-file false-positives, page-builder placeholder domains) are filtered out before picking. It can come back empty — that's fine, it's a bonus field, not a disqualifier.

## 6. Qualify, grade, verify owner, write opener — YOU do this now

For each candidate, read and apply `role.txt`, `memory.txt`, and `prompt.txt` in full (they're unchanged from the old pipeline — same disqualification rules, same A–D grading, same owner-verification requirement, same opener rules and priority order). Fill in `prompt.txt`'s template fields with the scraped business name/phone/website/owner_name/website_text and reason through it exactly as instructed there, producing the same JSON shape: `qualified`, `grade`, `grade_reason`, `disqualify_reason`, `niche_confirmed`, `niche_notes`, `opener`, `verified_owner_name`.

Then apply these post-check guardrails (same as the old `run.py`):
- `verified_owner_name` must pass the "real 2-3 word person name, not a generic phrase" test described in `prompt.txt`'s OWNER VERIFICATION section — if it doesn't, disqualify.
- Opener must be ≤15 words and contain no `?` — if either check fails, null it out.
- **A lead with no usable opener does not get pushed** — drop it, don't hand off a generic/cold lead.

Mark every candidate processed (qualified or not) with `python lib.py scraped-add "<name>|<city>|<state>"`.

## 7. Push qualified leads

Build a JSON list of qualified leads in this shape (one object per lead):
```json
{
  "Business Name": "...", "Owner Name": "...", "Phone": "...", "Website": "...", "Email": "...",
  "Grade": "A", "Grade Reason": "...", "Opener": "...", "City": "...", "State": "..."
}
```
`Email` is whatever step 5 found (owner-name match preferred, else contact/info/hello-style) — pass `""` if none was found, never fabricate one.
Write it to a temp file and run `python lib.py push <path> [status]` — `status` defaults to `new` (pass `sms-handoff` if the user says so). Sorts by grade and POSTs to `/api/contacts`, tagged `independent-pt`.

## 8. Update state

After **every search term** (not just at the end of a city), run `python lib.py city-record-progress "<city>" "<state>" <term_index_just_completed_plus_1> <reviewed_delta> <qualified_delta>` — `term_index_just_completed_plus_1` is 1-4 (e.g. finishing the city's 2nd term reports `2`); `reviewed_delta`/`qualified_delta` are this term's counts (not running totals — the command accumulates them itself). Do this even if you're about to continue in the same session — it keeps the record correct if the run stops right after this term (including because the target was just hit) or gets interrupted. Reaching `term_index` 4 automatically marks the city `covered` with today's date; anything less leaves it `in_progress` so `city-next` resumes it correctly next time. This call, `scraped-add`, and every `scraped-has` already push their files to GitHub via `shared/github_sync.py` — no separate sync step needed.

Then apply the step 2 continuation check (target met mid-city → finish the city's remaining terms, then stop; target met at a city's 4th term → stop; target unmet → call `python lib.py city-next` for the next city, capped at 10 cities this session).

## 9. Report

Tell the user, **per city covered this session**: listings reviewed, disqualified (with a one-line reason breakdown), qualified with grades — every city in the report has all 4 terms covered (cities are never left partially covered). Then give a session total: cities covered, combined qualified count, and confirm the push count against `daily_lead_target` (met/exceeded is a good outcome, not something to have avoided). Same shape as the old pipeline's console output, just delivered as a chat summary instead of logs.

**Also post this summary into the OS chat**, so results are visible from the dashboard even when this ran unattended (scheduled task) and nobody was watching this session. For the per-city breakdown, track this session's own reviewed/qualified per city as you go (that part is fine to hold in-session — it only covers cities *this* process actually touched). For the **totals line, run `python lib.py daily-tally` one last time** rather than summing your own session numbers — if this run is a resume of an earlier interrupted attempt, the real day's total includes leads from those earlier sessions too, and the report needs to reflect what actually happened today, not just what this process did. At the end, write a short markdown message to a temp file with this shape:

```
## Lead gen run — <date>

**<City>, <ST>** (<N>/4 terms): <reviewed> reviewed → <qualified> qualified (<A count> A, <B count> B, <C count> C, <D count> D)
**<City 2>, <ST>** ...

**Today's total:** <daily-tally reviewed> reviewed → <daily-tally qualified> qualified — qualification rate <qualified/reviewed as %>
Target: <daily_lead_target> — <met/exceeded by N / fell short by N> (based on today's total, not just this session)
```

Run `python lib.py post-chat <path>` to push it into the leadgen-agent's OS chat (dashboard → Agents → Lead Qualifier). Do this even if the target wasn't reached (e.g. ran out of cities) — the report should reflect what actually happened, not just successful runs.
