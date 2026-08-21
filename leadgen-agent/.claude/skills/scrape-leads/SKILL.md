---
name: scrape-leads
description: Scrape, qualify, grade, and push small independent single-location PT practice leads to the DigiGrowth OS — free pipeline using the Playwright MCP browser (Google Maps) and Claude Code's own reasoning (qualification), no paid APIs.
---

# Scrape Leads

Free replacement for the old `leadgen-agent/run.py` pipeline. No Google Places API, no Anthropic API billing — Google Maps is driven directly via the Playwright MCP browser tools, and qualification/grading/opener-writing is done by you (Claude Code), reading `role.txt` + `memory.txt` + `prompt.txt` as instructions, the same way you'd read any other skill.

Requires the `playwright` MCP server (configured in the repo's `.mcp.json`) — its browser tools (`browser_navigate`, `browser_snapshot`, `browser_click`, `browser_evaluate`, etc.) must be available in this session. If they aren't, tell the user to restart their Claude Code session so the MCP server loads.

Before starting, check `config.json` — if `"enabled": false`, stop and report that leadgen is paused.

## 1. Load state

Run `python lib.py progress-get` (from `leadgen-agent/`) to get the current `{state, city, term_index}` cursor, and read `scraped_ids.json` (or use `python lib.py scraped-has <id>`) for dedup — `<id>` is `"<business name>|<city>|<state>"` lowercased (no Places `place_id` available anymore).

## 2. Markets and search terms

Work through this list in order, resuming from the saved cursor (find the saved `state` in this list; if empty, start at the top).

**One run covers up to 5 cities.** For each city, work through its 4 search terms in order — that's what "covering the city's TAM" means here (each term surfaces a different, overlapping slice of the market; running all 4 is how you get to roughly 90%+ real coverage of what's actually out there, not a guess). `config.json`'s `daily_lead_target` is a **target, checked after every search term, not just after a city finishes**:
- After each search term's leads are qualified and pushed (steps 3-7), check the running total of leads qualified-and-pushed so far **this session** against `daily_lead_target`. If you've met or passed it, **stop immediately** — mid-city, mid-term-list, wherever you are. You do not need to finish the city's remaining terms once the target is hit.
- If the target isn't met yet and more terms remain in the current city, continue to the next term.
- If the target isn't met yet and the city's 4 terms are exhausted, check whether you've already done 5 cities this session — if so, stop regardless of the target (per-run cap, keeps sessions bounded and reviewable). Otherwise advance to the next city in the list (see step 8), reset to term index 0, and continue.

So a session is a sequence of search terms across up to 5 cities, checked after each one: term → check target → term → check target → ... → stop the moment the target is met, or after 5 cities' worth of terms are exhausted, whichever comes first.

Search terms (run each per city):
```
physical therapy
physical therapist
outpatient physical therapy
sports physical therapy
```

Sun Belt markets first (per `memory.txt`'s priority), then the rest:
```
Florida: Jacksonville, Miami, Tampa, Orlando, St. Petersburg
Texas: Houston, San Antonio, Dallas, Austin, Fort Worth
Georgia: Atlanta, Augusta, Columbus, Macon, Savannah
South Carolina: Columbia, Charleston, North Charleston
North Carolina: Charlotte, Raleigh, Greensboro, Durham
Arizona: Phoenix, Tucson, Scottsdale, Mesa
Tennessee: Nashville, Memphis, Knoxville, Chattanooga
Virginia: Virginia Beach, Norfolk, Chesapeake, Richmond
California: Los Angeles, San Diego, San Jose, San Francisco
New York: New York City, Buffalo, Rochester
... (continue through remaining US states/cities as needed once the above are exhausted — ask the user before expanding beyond Sun Belt markets if unsure)
```

## 3. Scrape Google Maps (Playwright MCP)

For each search term, for the current city:
1. `browser_navigate` to `https://www.google.com/maps/search/<term url-encoded> in <city>, <state>`
2. Take a `browser_snapshot` to confirm the results feed loaded.
3. Scroll the results feed to load all listings: use `browser_evaluate` with `document.querySelector('[role="feed"]').scrollTop = document.querySelector('[role="feed"]').scrollHeight`, wait ~3-4 seconds, `browser_snapshot` again, repeat until the listing count stops increasing or "You've reached the end of the list" appears. Don't scroll the map itself.
4. From the snapshot, extract each listing's business name, phone number, and website URL (click into a listing or read the feed panel detail as needed — address is a bonus, not required).

## 4. Free filters (no cost — do this before visiting any website)

Skip a listing immediately if any of these are true:
- Already scraped: `python lib.py scraped-has "<name>|<city>|<state>"` exits 0
- No phone number, or no website
- The name matches a chain/franchise or an obviously non-PT business — check against `memory.txt`'s `CHAIN / FRANCHISE BLACKLIST` and these institutional keywords: hospital, home health, nursing home, skilled nursing, hospice, urgent care, behavioral health, addiction, mental health, psychiatric, chiropractic, chiropractor, home care, va medical, rehabilitation hospital, assisted living, senior living, physical therapy school, university

For everything skipped, still run `python lib.py scraped-add "<name>|<city>|<state>"` so it isn't re-checked next run.

## 5. Website scrape (free — no browser needed here)

For each survivor: `python lib.py scrape-site <website_url>` — returns JSON `{owner_name, website_text}` (homepage + /about + /about-us, JSON-LD/regex owner extraction, already truncated to `max_website_text_words`). This is a plain HTTP fetch, not a Playwright call — no need to open it in the browser.

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
  "Business Name": "...", "Owner Name": "...", "Phone": "...", "Website": "...",
  "Grade": "A", "Grade Reason": "...", "Opener": "...", "City": "...", "State": "..."
}
```
Write it to a temp file and run `python lib.py push <path> [status]` — `status` defaults to `dialer-lead` (pass `sms-handoff` if the user says so). Sorts by grade and POSTs to `/api/contacts`, tagged `independent-pt`.

## 8. Update state

After **every search term** (not just at the end of a city), run `python lib.py progress-set '{"state": "...", "city": "...", "term_index": N}'` pointing at whatever comes next — the next term in the same city, or term 0 of the next city if this one's 4 terms are done — even if you're about to continue to it immediately in this same session. This keeps the cursor correct if the run stops right after this term (including because the target was just hit) or gets interrupted. `progress-set` and `scraped-add`/every `scraped-has` write already push their files to GitHub via `shared/github_sync.py` — no separate sync step needed.

Then apply the step 2 continuation check (target met → stop; else next term or next city, capped at 5 cities this session).

## 9. Report

Tell the user, **per city covered this session**: listings reviewed, disqualified (with a one-line reason breakdown), qualified with grades — note if a city was only partially covered (fewer than 4 terms) because the target was hit mid-city. Then give a session total: cities covered, combined qualified count, and confirm the push count against `daily_lead_target` (met/exceeded is a good outcome, not something to have avoided). Same shape as the old pipeline's console output, just delivered as a chat summary instead of logs.

**Also post this summary into the OS chat**, so results are visible from the dashboard even when this ran unattended (scheduled task) and nobody was watching this session. Track two running counts throughout the session: total listings reviewed (every listing that reached step 4's free filters, qualified or not — i.e. everything you called `scraped-add` on) and total qualified-and-pushed. At the end, write a short markdown message to a temp file with this shape:

```
## Lead gen run — <date>

**<City>, <ST>** (<N>/4 terms): <reviewed> reviewed → <qualified> qualified (<A count> A, <B count> B, <C count> C, <D count> D)
**<City 2>, <ST>** ...

**Session total:** <reviewed_total> reviewed → <qualified_total> qualified — qualification rate <qualified_total/reviewed_total as %>
Target: <daily_lead_target> — <met/exceeded by N / fell short by N>
```

Run `python lib.py post-chat <path>` to push it into the leadgen-agent's OS chat (dashboard → Agents → Lead Qualifier). Do this even if the target wasn't reached (e.g. ran out of cities) — the report should reflect what actually happened, not just successful runs.
