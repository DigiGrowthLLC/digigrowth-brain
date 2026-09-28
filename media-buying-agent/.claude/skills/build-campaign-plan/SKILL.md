# Build Campaign Plan Skill

Produce a full Meta campaign plan for a client — offer, avatar, budget/campaign settings, ad
concepts, and measurement plan — grounded in that client's real portal files and live Meta Ad
Library research, not generic advice. This is the one place in this agent where budget/targeting/
campaign-structure recommendations are in scope as a written plan for Dylan to manually enter into
Ads Manager — it still never touches the Meta API or manages a live campaign (see `CLAUDE.md`).

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

### 2. Research the live Meta Ad Library for the vertical

Run the `research-competitors` skill for this client's vertical + geo (pass the client so it can
cross-check findings against their `onboarding.differentiation_voice` rules). It browses the live Ad
Library via `playwright`, cross-checks with `WebSearch`, and separates structural patterns worth
borrowing from tone that needs to match the client — don't duplicate that process here.

### 3. Findings are already appended to `context/ad-creative-principles.md`

`research-competitors` handles this as part of its own step 4 — confirm the new dated section landed
before moving on, don't re-append.

### 4. Write the plan

Save to `outputs/campaign-<client-slug>-<YYYY-MM-DD>/campaign-plan.md` while drafting/revising.
**Once Dylan approves the plan**, copy it to `clients/<client-slug>/campaign-plan.md` (overwrite in
place — this is the one current plan, not a version history) and delete the working
`outputs/campaign-<client-slug>-<YYYY-MM-DD>/` folder. See `CLAUDE.md`'s "Output Files" section — the
same finalize-then-delete convention `generate-ad` uses for creative applies here. Structure that's
worked:

1. What's in the portal (asset inventory — this changes what's possible, e.g. real video means no
   AI-image fallback is needed).
2. What the full source material adds beyond what was already known (richer avatar segments).
3. Ad Library findings and how they apply (with the tone/structure caveat from step 2).
4. Blockers to clear before spending anything (undeployed landing page, missing Meta Pixel, missing
   Conversions API, no Meta Business Portfolio set up, geo unknown) — see the "Meta Ads Beginner
   Fundamentals" source in `ad-creative-principles.md` for why each of these has to be confirmed
   before the first ad, not fixed after spend has already started.
5. Budget-reality math: check the requested budget/timeframe against this agent's own
   `ad-creative-principles.md` minimums (10-15 concepts, $10+/day/ad). If the budget is far under
   that (a common case), say so explicitly and scale down concept count / judgment windows rather
   than silently applying advice that doesn't fit — then do the actual arithmetic (budget ÷ target
   CPL ÷ assumed lead→result conversion rate) to show whether the stated goal is realistic, tight, or
   a stretch on the stated budget.
6. Campaign settings table (objective, budget type, ad sets, daily budget, audience, geo, placements).
   For a typical DigiGrowth local-service budget (~$30-35/day), default to the "ad set trio" structure
   from the "$30 A Day" source in `ad-creative-principles.md`: one ad set per creative **format**
   (static/UGC-video/carousel), 3 active ads per ad set, kept broad on audience/geo rather than
   segmented by demographic — note it explicitly as the default rather than assuming Dylan knows why.
7. Ad concepts — as many as real assets support, each naming which actual client file it uses
   (video/photo filename, specific testimonial), not a hypothetical asset. Check every line of copy
   against the client's own brand-voice rules from `onboarding.differentiation_voice` before
   finalizing (banned claims, tone, formatting quirks) — attribute strong testimonial outcomes as a
   direct quote from the patient rather than restating them as the business's own promise, which is
   usually how a "no guarantees" rule gets violated by accident.
8. Measurement plan (north-star metric, target cost/result, weekly checkpoint questions).
9. Concrete next steps for Dylan, in priority order.

### 5. Publish as a Claude Artifact

Use the `Artifact` tool to publish the plan as a designed HTML page (load `artifact-design` first)
so Dylan can view and save it outside the terminal — this is the primary deliverable for this skill,
not the markdown file (the markdown file is the working save; the artifact is what gets handed over).

---

## After Delivering

Ask whether to (a) generate the actual ad creative for the launch concepts (hand off to
`generate-ad` for anything needing an AI image, or to `content-agent`'s `embedded-captions` skill if
overlaying captions/CTA text onto existing raw client video), or (b) wait for a blocker (landing
page deploy, geo confirmation) to clear first.
