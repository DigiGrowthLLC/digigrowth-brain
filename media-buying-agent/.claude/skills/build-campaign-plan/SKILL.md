# Build Campaign Plan Skill

Produce a full Meta campaign plan for a client — offer, avatar, budget/campaign settings, ad
concepts, and measurement plan — grounded in that client's real portal files, their live ad
account's actual results, and live Meta Ad Library research, not generic advice. This is the one
place in this agent where budget/targeting/campaign-structure recommendations are in scope as a
written plan for Dylan to enter into Ads Manager. The Meta Ads MCP connector is used to **read** the
account (step 2); creating or editing live campaigns stays manual (see `CLAUDE.md`).

---

## Trigger

A request for a media buying plan, campaign plan, or "everything I need to launch ads" for a
specific client — as opposed to a single ad (`generate-ad` skill) or a principles-extraction task.

---

## Inputs Needed

Ask if not already given:
1. **Which client** (by name — match against the dashboard's Clients list, not guesswork).
2. **Budget and timeframe.**
3. **The success metric** (e.g. "10 booked consults in 4 weeks") — this is what the whole plan
   optimizes toward, not CPL or CTR in isolation.

---

## Steps

### 0. Read the client's own context file first

If `clients/<client-slug>/client-context.md` exists, read it before anything else. It holds rules
that are specific to that one client (e.g. which service to lead with, age limits, how their leads
flow), and they override this skill's general defaults wherever the two disagree. Don't copy
client-specific rules into this skill; add new ones to that client's file instead.

### 1. Pull the client's real record and portal uploads

Never build a plan from the funnel page alone — the client portal almost always has more (a full
testimonial library beyond what's on the page, raw video, professional photos, education content).

Fetch via the dashboard API using `doppler run` so the password is never typed or echoed literally
in a command (materializing a raw secret string gets blocked by the permission classifier):

```bash
doppler run --project digigrowth --config prd -- bash -c \
  'curl -s -u "admin:$DASHBOARD_PASSWORD" "$DASHBOARD_URL/api/clients"'
```

Find the client's `id`, then:
- `GET /api/clients/{id}` — full record, and **read the whole `onboarding` object, not just
  `linked_contact`** (`linked_contact.business` can reveal geo info not stated elsewhere, like a
  "| Austin" suffix, but the real payload is in `onboarding`: `differentiation_voice.answers.avoid`
  is the client's own brand-voice rules — banned claims, tone, formatting quirks like "no em
  dashes" — and is binding on every line of ad copy written afterward; `ideal_patient.answers` gives
  the avatar in the client's own words plus the real reason people drop off (often cost, not
  interest); `offer_economics.answers` gives real pricing/LTV context worth citing to Dylan even if
  it never appears in the ad copy itself). Skipping this and building only from the deployed page +
  uploads list produces copy that can violate the client's own stated rules.
- `GET /api/clients/{id}/websites` and `GET /api/clients/{id}/marketing-config` — check
  `landing_page_url` / the websites list before assuming a funnel isn't live; a page can go from
  "pending deploy" to live between one session and the next.
- `GET /api/clients/{id}/uploads` — list every file (`id`, `file_name`, `file_type`, `file_size`).
- `GET /api/clients/{id}/uploads/{upload_id}/download` — returns `{"url": "<presigned R2 URL>"}` —
  note the path is `/download`, not `/download-url`. Download docs directly from that URL with curl.
- If a funnel URL turns up, `WebFetch` it to confirm it's actually live and check what the real CTA
  points to (a booking link can change between sessions too) — don't take a prior session's "pending
  deploy" note as still true.

Route Windows paths through the session's scratchpad directory, not `/tmp` (Git Bash's `/tmp` isn't
visible to the Windows Python interpreter used for parsing JSON/docx — use the Windows-style path
for anything Python touches).

**Extract text from any `.docx` without installing a dependency** — it's a zip of XML:
```python
import zipfile, re
with zipfile.ZipFile(path) as z:
    xml = z.read('word/document.xml').decode('utf-8')
text = re.sub('<[^>]+>', '', xml.replace('</w:p>', '\n'))
```

Read every testimonial/education doc found this way — the full set is usually much richer than
what's already been surfaced in a previous deployed page or prior output, and often reveals avatar
segments (occupations, recurring differentiators like "he comes to your home") that weren't visible
anywhere else.

**Check what any raw video actually is before treating it as ad-ready.** Real client-portal footage
is a strong asset, but "real footage exists" isn't the same as "real ad exists" — a clip of the
practitioner explaining a topic to camera is educational content, not an ad, if it has no hook, no
on-screen offer, no testimonial, and no CTA. Don't default video to the launch creative just because
it's authentic; if it's raw/educational, plan static image + text-overlay ads (real photo + a real
attributed testimonial quote + a condition checklist + one CTA) as the fast, genuinely ad-shaped
launch creative, and note the video as a Phase 2 item that needs an edit pass (title-card hook +
checklist + closing CTA card, via `talking-head-recut` or `embedded-captions`) before it's usable.

### 2. Pull the live ad account's real results (required when the client has any spend history)

A plan revision written without this repeats the last campaign's mistakes. Use the Meta Ads MCP
connector (`mcp__meta-ads__*`, load via ToolSearch). Find the account with `ads_get_ad_accounts` if
it isn't in the client's context file, then pull, all with `date_preset: "maximum"`:

1. **Per ad** (`ads_get_ad_entities`, `level: "ad"`): spend, impressions, reach, frequency, clicks,
   CTR, CPC, CPM, results, cost per result, status. Which ad and which angle actually produced
   results, not just clicks?
2. **Per ad set** (`level: "adset"`, plus `targeting`, `optimization_goal`, `daily_budget`): what was
   really set. Check whether age/gender are hard limits or Advantage+ *suggestions*
   (`targeting_automation.individual_setting`); a suggestion lets Meta spend outside the range.
3. **Breakdowns** at `level: "campaign"`: `["age", "gender"]` and
   `["publisher_platform", "platform_position"]`. Look for spend going to an age group the client
   can't serve, and for junk placements (Audience Network inflating cheap clicks, a placement eating
   a large share of budget with zero results).
4. **Daily trend** (`object_ids` = the campaign, `time_increment: "1"`): is CPM climbing as a small
   audience wears out? When did results actually happen?
5. **Tracking sanity check:** clicks with zero results on a website-conversion campaign usually
   means the pixel/lead event isn't firing, not that nobody converted. Say which it is.
6. **Lead quality, not just lead count:** for Instant Form leads, read what actually happened after
   the form. Pull the client's SMS threads (`GET /api/clients/{id}/sms-messages`, via `doppler run`
   as in step 1) and check how many leads replied, booked, asked about insurance, or were out of
   area. A cheap lead that can't book isn't a win.

Follow any `next_actions` the connector returns before moving on. Summarize this as a "what went
wrong / what's working" section at the top of the plan, with the numbers.

### 3. Research the live Meta Ad Library for the vertical

Run the `research-competitors` skill for this client's vertical + geo (pass the client so it can
cross-check findings against their `onboarding.differentiation_voice` rules). **It must return at
least 10 proven ads** (still active, running 6+ months) with their verbatim copy, saved to
`context/proven-ads/<vertical-slug>.md` as P1, P2, ... Don't move on to writing concepts with fewer
than 10; if research-competitors reports it couldn't find 10, tell Dylan before continuing. It browses the live Ad
Library via `playwright`, cross-checks with `WebSearch`, and separates structural patterns worth
borrowing from tone that needs to match the client — don't duplicate that process here.

### 4. Findings are already appended to `context/ad-creative-principles.md`

`research-competitors` handles this as part of its own step 4 — confirm the new dated section landed
before moving on, don't re-append.

### 5. Write the plan

Save to `outputs/campaign-<client-slug>-<YYYY-MM-DD>/campaign-plan.md` while drafting/revising.
**Once Dylan approves the plan**, copy it to `clients/<client-slug>/campaign-plan.md` (overwrite in
place — this is the one current plan, not a version history) and delete the working
`outputs/campaign-<client-slug>-<YYYY-MM-DD>/` folder. See `CLAUDE.md`'s "Output Files" section — the
same finalize-then-delete convention `generate-ad` uses for creative applies here. Structure that's
worked:

0. What the live account data shows (from step 2): what went wrong, what's working, with numbers.
   Skip only for a client with no spend history.
1. What's in the portal (asset inventory — this changes what's possible, e.g. real video means no
   AI-image fallback is needed).
2. What the full source material adds beyond what was already known (richer avatar segments).
3. Ad Library findings and how they apply (with the tone/structure caveat from step 3): the 10+
   proven ads as a table (P#, advertiser, months running, format, hook, copy structure), then the
   patterns they share.
4. Blockers to clear before spending anything (undeployed landing page, missing Meta Pixel, missing
   Conversions API, no Meta Business Portfolio set up, geo unknown) — see the "Meta Ads Beginner
   Fundamentals" source in `ad-creative-principles.md` for why each of these has to be confirmed
   before the first ad, not fixed after spend has already started.
5. Budget-reality math: check the requested budget/timeframe against the house format's **$25/day
   minimum** (see 6). If the client's budget can't sustain $25/day for the whole timeframe, say so
   explicitly and give the trade-off (run $25/day and finish early, or extend the timeframe) rather
   than quietly dropping below the minimum. Then do the actual arithmetic (budget ÷ target CPL ÷
   assumed lead→result conversion rate) to show whether the stated goal is realistic, tight, or a
   stretch on the stated budget.
6. Campaign settings table (objective, budget, ad set, audience, geo, placements, ad count). **House
   format (Dylan, 2026-10-06), the default for every client:**
   - **1 campaign, 1 ad set, 10 ads.** Budget on the campaign or ad set (same thing with one ad
     set), **minimum $25/day**. Meta's delivery decides which of the 10 get spend; don't split into
     per-format or per-audience ad sets.
   - **Heavily video:** at least 7 of the 10 ads are video (AI UGC via `generate-ad`'s "AI UGC Video
     Ads" loop, or edited client footage); statics fill the rest. This deliberately overrides the
     older "segment statics and video into separate ad sets" and "ad set trio" guidance in
     `ad-creative-principles.md`: with statics kept to a small minority, the risk of cheap-CPM images
     starving the videos is small, and one ad set concentrates learning instead of splitting it.
   - Audience broad within the client's hard limits (geo, and any age/gender rules in their
     `client-context.md`), set as hard limits, not Advantage+ suggestions.
   - Note the format explicitly in the plan rather than assuming the reader knows why.
7. Ad concepts — **exactly 10, and every one a genuinely different concept or a very different
   variation**: a different avatar, angle/reason to buy, format (UGC selfie, talking-head, POV text,
   static quote card, etc.), actor, or hook + script. A new headline or thumbnail on the same ad does
   not count as one of the 10. **Each concept is built on one proven ad** from step 3: it borrows
   that ad's structure (hook type, copy flow, format, proof style) and adapts it to the client's
   real offer, avatar and assets. Use a different proven ad for each concept where possible, and
   never base two concepts on the same one with only cosmetic changes. Lay them out as a table
   (concept, proven reference P#, what's borrowed from it, format, avatar, angle, hook) so the
   spread is visible, and flag any two that are too close. Each names which actual client file or
   generated asset it uses (video/photo filename, specific testimonial), not a hypothetical asset.
   Check every line of copy
   against the client's own brand-voice rules from `onboarding.differentiation_voice` before
   finalizing (banned claims, tone, formatting quirks) — attribute strong testimonial outcomes as a
   direct quote from the patient rather than restating them as the business's own promise, which is
   usually how a "no guarantees" rule gets violated by accident.
8. Measurement plan (north-star metric, target cost/result, weekly checkpoint questions).
9. Concrete next steps for Dylan, in priority order.

### 6. Publish as a Claude Artifact

Use the `Artifact` tool to publish the plan as a designed HTML page (load `artifact-design` first)
so Dylan can view and save it outside the terminal — this is the primary deliverable for this skill,
not the markdown file (the markdown file is the working save; the artifact is what gets handed over).

---

## After Delivering

Ask whether to (a) generate the actual ad creative for the approved concepts (`generate-ad` writes
3 copy variations per ad, each modeled on a proven ad's copy from `context/proven-ads/`) (hand off to
`generate-ad` for anything needing an AI image, or to `content-agent`'s `embedded-captions` skill if
overlaying captions/CTA text onto existing raw client video), or (b) wait for a blocker (landing
page deploy, geo confirmation) to clear first.
