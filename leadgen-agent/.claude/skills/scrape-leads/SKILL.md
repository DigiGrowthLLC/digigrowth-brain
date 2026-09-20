---
name: scrape-leads
description: Scrape, qualify, grade, and push small independent single-location PT practice leads to the DigiGrowth OS — free pipeline using the Playwright MCP browser (Google Maps) and Claude Code's own reasoning (qualification), no paid APIs.
---

# Scrape Leads

Free replacement for the old `leadgen-agent/run.py` pipeline. No Google Places API, no Anthropic API billing — Google Maps is driven directly via the Playwright MCP browser tools, and qualification/grading/opener-writing is done by you (Claude Code), reading `role.txt` + `memory.txt` + `prompt.txt` as instructions, the same way you'd read any other skill.

Requires the `playwright` MCP server (configured in the repo's `.mcp.json`) — its browser tools (`browser_navigate`, `browser_snapshot`, `browser_click`, `browser_evaluate`, etc.) must be available in this session. If they aren't, tell the user to restart their Claude Code session so the MCP server loads.

Before starting, check `config.json` — if `"enabled": false`, stop and report that leadgen is paused.

**Never background this work.** Do all scraping, qualification, and pushing synchronously in the current turn — never delegate any part of it to a background task/subagent, and never respond with something like "I'll wait for the background scrape to finish" or "I've kicked this off and will check back." This skill runs unattended via `claude -p` (see `run-scrape-leads.ps1`), which exits the instant a response is produced for the turn — a background task has no later turn to report back to, so backgrounding silently kills the whole run after only a few files get touched. If Playwright browser calls are slow, that's fine; just make them inline and keep going in the same turn until step 9's report is posted.

**This invocation covers exactly one city, all 4 terms, then stops.** `run-scrape-leads.ps1` is a loop: it launches a fresh `claude -p` process per city and re-checks `city-next`/`daily-tally` between launches to decide whether to launch another (see the script for the exact stop conditions — target met, or 10-city cap reached). This used to be a single session working through up to 10 cities back to back; that meant every browser snapshot and every website-text blob from city #1 was still sitting in context by city #8, and the session would run out of tokens before finishing the night's work. One city per process means each process starts with a small, clean context and the token budget can't compound across cities. Don't try to loop to a second city yourself — finish this one city's 4 terms, record progress, report, and stop; the wrapper script handles what happens next.

## 1. Load state

Run `python lib.py city-next` (from `leadgen-agent/`) — this is the **only** source of truth for which city to work on; don't reason about it yourself. It returns `{"city": ..., "state": ..., "term_index": N, "resuming": bool}`, or `{"done": true}` if nothing is due (extremely unlikely — the list covers 147 US cities plus a 90-day cooldown revisit cycle). `term_index` tells you which of the 4 search terms to start from (0 = first term; a nonzero value means this city was interrupted mid-run last time — `resuming: true`).

Also read `scraped_ids.json` (or use `python lib.py scraped-has <id>`) for dedup — `<id>` is `"<business name>|<city>|<state>"` lowercased (no Places `place_id` available anymore).

## 2. Markets and search terms

City selection is fully code-driven now (`city_coverage.json`, via `lib.py city-next`/`city-record-progress`) — it deterministically walks a fixed, population-ranked list of 147 US cities, tracks each city's status (`not_started` / `in_progress` / `covered`), and only revisits a `covered` city after a 90-day cooldown (catches new-business churn without re-treading the same ground). This replaced an earlier markdown-table-driven approach that caused the same cities to get re-picked across separate unattended sessions while others never got reached — see `leadgen-agent` memory notes if curious why this exists. You never need to pick a city yourself or ask the user which market comes next; `city-next` always has an answer.

**This process covers exactly one city — all 4 search terms, in order** (that's what "covering the city's TAM" means here: each term surfaces a different, overlapping slice of the market, and running all 4, each scrolled to exhaustion per step 3, is how you get to roughly 90%+ real coverage of what's actually out there). **A city, once started, is never abandoned mid-term-list — all 4 terms always run**, even if `daily_lead_target` gets hit partway through.

- After each search term's leads are qualified and pushed (steps 3-7), run `python lib.py daily-tally` and check its `qualified` count against `daily_lead_target` from `config.json`. **Always use this command — never track the target against your own in-session count.** A resumed run (session limit, or the backgrounding bug) starts as a brand-new `claude -p` process with no memory of earlier progress; an in-session tally would silently reset to zero and blow well past the target across resumes (this happened 2026-09-03: three resumes pushed 176 qualified leads against a target of 100). `daily-tally` sums every city touched today directly from `city_coverage.json`, so it's correct regardless of how many processes have already run today.
- If you've met or passed the target and more terms remain in this city, **keep going anyway** — finish this city's remaining terms before stopping. Note internally that the target's been met so your step 9 report can say so.
- Once this city's 4 terms are exhausted, **stop** — record progress (step 8) and report (step 9). Do not call `city-next` again and do not start a second city yourself; whether another city gets picked up tonight is `run-scrape-leads.ps1`'s decision, made between processes, not yours.

Search terms (run each per city):
```
physical therapy
physical therapist
outpatient physical therapy
sports physical therapy
```

## 3. Scrape Google Maps (Playwright MCP)

**Prefer `browser_evaluate` over `browser_snapshot` for everything in this step.** A full `browser_snapshot` of the results feed dumps the entire accessibility tree — every ARIA role, every nested node — and that tree only grows as more listings load, so snapshotting after every scroll tick was the single biggest token cost in the whole pipeline (it's what caused runs to exhaust their budget mid-city). A `browser_evaluate` call that reads the feed's DOM directly and returns just `{name, phone, website}[]` as JSON gets the same data for a fraction of the tokens. Only fall back to `browser_snapshot` if a `browser_evaluate` extraction comes back empty/malformed and you need to see the actual page structure to fix the selector.

For each search term, for the current city:
1. `browser_navigate` to `https://www.google.com/maps/search/<term url-encoded> in <city>, <state>`.
2. Run one `browser_evaluate` that checks the feed rendered (e.g. `!!document.querySelector('[role="feed"]')`) — don't spend a full snapshot just to confirm the page loaded.
3. Scroll the results feed to load **every** listing — this is what makes the 4-terms-per-city coverage actually hit ~90%+ of real TAM; stopping early here undermines the whole point of running 4 terms. Do this in batches, not one scroll-and-check per tick: use a single `browser_evaluate` that scrolls the feed (`document.querySelector('[role="feed"]').scrollTop = document.querySelector('[role="feed"]').scrollHeight`) 2-3 times in a row with a short pause between each (all inside the one JS call), *then* evaluate the current listing count/end-of-list text once. **Do not stop just because growth has slowed** — Google Maps loads results in batches and a pause between batches is normal, not the end of the list. Only stop once you get **three consecutive batched-scroll cycles with zero new listings**, or the page explicitly shows "You've reached the end of the list" / equivalent end-of-results text. If a batch is slow to load, wait longer before counting it toward the three-in-a-row — a slow batch is not a stalled one. Don't scroll the map itself.
4. Once the feed is fully loaded, run one `browser_evaluate` extraction pass over the whole feed to pull every listing's business name, phone number, and website URL as JSON in a single call (address is a bonus, not required). Only click into an individual listing's detail pane as a fallback, when the feed panel itself doesn't expose the phone/website for that listing — clicking through every listing one at a time is far more expensive than one bulk DOM read.

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

Then apply the step 2 continuation check: finish this city's remaining terms regardless of target status, and once the 4th term wraps, stop — this process is done. Do not call `city-next` again here.

## 9. Report

Tell the user about **this city**: listings reviewed, disqualified (with a one-line reason breakdown), qualified with grades — all 4 terms covered (a city is never left partially covered by a single process; if it was interrupted, the next process resumes it via `term_index`).

**Also post this summary into the OS chat**, so results are visible from the dashboard even when this ran unattended (scheduled task) and nobody was watching. For the **totals line, run `python lib.py daily-tally`** rather than reporting just this city's numbers — the real day's total includes every other city any earlier or later process touched today, and the report needs to reflect what actually happened today, not just what this one process did. At the end, write a short markdown message to a temp file with this shape:

```
## Lead gen run — <date>

**<City>, <ST>** (4/4 terms): <reviewed> reviewed → <qualified> qualified (<A count> A, <B count> B, <C count> C, <D count> D)

**Today's total:** <daily-tally reviewed> reviewed → <daily-tally qualified> qualified — qualification rate <qualified/reviewed as %>
Target: <daily_lead_target> — <met/exceeded by N / fell short by N> (based on today's total across every city run today, not just this one)
```

Run `python lib.py post-chat <path>` to push it into the leadgen-agent's OS chat (dashboard → Agents → Lead Qualifier). Do this even if the target wasn't reached — the report should reflect what actually happened, not just successful runs.
