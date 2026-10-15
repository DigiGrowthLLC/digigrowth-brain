# Deep Research Skill

Build a voice-of-customer and market research dossier for one client's niche and the target
segment(s) they want to reach. AI does the collecting and the first-pass analysis across Reddit,
Google reviews, YouTube, TikTok, Amazon, forums and the client's own lead conversations. Dylan
steers and approves at three gates. The output is the raw material every ad hook, callout and angle
is written from: real phrases from real people, never an AI summary of "what patients want."

Why this exists: "How to make Meta Ad Creatives in 2026" (Creative Don, 2026-10-08, in
`context/ad-creative-principles.md`). The best lines ("made for spitters, not quitters") come from
reading how the avatar actually talks, not from a generic deep-research prompt. So this skill keeps
**verbatim quotes with sources** as its main product, and its analysis always points back to them.

---

## Trigger

"Deep research", "research the niche / segment / avatar", "voice of customer", "what are <segment>
saying", or step 3 of `build-campaign-plan`. Standalone or inside a campaign build.

---

## How this skill runs: interactive, three gates

Dylan wants to be looped in, not handed a finished black box. At each **GATE**:
1. Show a short summary in chat (what was done, what was found, what's proposed next).
2. Ask with `AskUserQuestion`: **Approve** / **Edit** (he says what to change) / **Dig deeper or
   redo** (he says where). Put concrete options in the question where they help, e.g. which
   subreddits to add.
3. **Stop and wait.** Never run past a gate on an assumption, and never combine two gates into one
   question. Skip a gate only if Dylan says so in this conversation ("run the research end to
   end").

Keep `outputs/research-<client-slug>-<YYYY-MM-DD>/progress.md` updated with each gate's status and
Dylan's decisions, so a later session can pick up where this one stopped.

---

## Inputs Needed

Ask if not already given:
1. **Client** (slug). Read `clients/<slug>/client-context.md` first. Its rules (e.g. lead with
   in-clinic, patients up to 60 only) define the segment boundaries.
2. **Target segment(s)**: who the client wants more of (e.g. "runners 30-55 in Austin with nagging
   knee issues", "desk workers with neck/shoulder tension"). Pull the client's own words from the
   dashboard: `onboarding.ideal_patient.answers` (via `doppler run`, same call as
   `build-campaign-plan` step 1). Max 3 segments per run. More segments means thinner research.
3. **Geo** (for local competitor reviews) and the **service(s) to lead with**.

---

## Steps

### 1. Draft the research brief → GATE R1

Write `outputs/research-<slug>-<date>/brief.md`:
- **Segment definitions**: who, age range, life situation, the trigger that makes them look for
  help *now*, what's out of scope.
- **Questions to answer** (8-12), e.g. "What have they already tried before PT, and why did they
  quit it?" "What do they call their problem in their own words?" "What makes them distrust PT
  clinics?" "What does 'fixed' look like to them: a race, a full night's sleep, picking up a kid?"
- **Source plan**, per platform: the exact subreddits, search queries, competitor clinics (names +
  Maps links), YouTube search terms, Amazon products and TikTok searches you intend to use (see
  step 2 for how to pick them).

**GATE R1:** show the brief. Dylan approves the segment, the questions and the source list before
any collecting starts. He knows the client and often knows the right communities.

### 2. Collect, platform by platform

Save raw findings to `outputs/research-<slug>-<date>/raw/<platform>.md`. One entry per quote:

```
- "<verbatim quote, typos kept>"
  source: <permalink>  | date: <YYYY-MM> | platform: reddit | segment: runners | theme: tried-before
```

**Collection rules:**
- **Verbatim only.** Never paraphrase in the raw files. Keep typos, slang and swearing. That's the
  language worth having.
- **Patients' voice vs. clinicians' voice.** Tag clinician posts `voice: clinician`. They help with
  the mechanism, but they are not customer language. (`r/physicaltherapy` is mostly PTs. The patient
  voice lives in the activity and condition subs.)
- Read the **comments, not just the post titles**. The best lines are usually replies.
- Prefer the last 3 years. Mark anything older.
- No usernames or reviewer names in the files. A link is enough.
- **Target:** 150+ quotes across 4+ platforms, with no single platform over 50%. If one platform is
  blocked, say so and lean harder on the others. Never pad with invented or paraphrased quotes.

**Per platform:**

1. **The client's own leads and patients (start here, it's the closest match):**
   - SMS threads with past ad leads: `GET /api/clients/{id}/sms-messages` (via `doppler run`).
     Leads' own replies are the exact words of people who already responded to an ad.
   - Portal testimonials and their reviews on the client's own Google Business Profile. Run a
     **golden-nugget pass** over all of them: which lines would work best as ad proof or
     headlines (specific, emotional, about a real outcome or moment)? Tag those `golden: true`
     in the raw file, so `generate-ad` picks proof from them first.
   - `onboarding.ideal_patient.answers` (the client's view of the patient, tagged
     `voice: client`).
2. **Reddit:** find threads with `WebSearch` (`site:reddit.com "<segment phrase>" <situation>`,
   e.g. `site:reddit.com runner knee "physical therapy" waste of money`). Read them with
   `WebFetch` on the `old.reddit.com` URL, or the `playwright` browser if WebFetch is blocked.
   Optional, for more volume: PullPush comment search,
   `https://api.pullpush.io/reddit/search/comment/?q=<query>&subreddit=<sub>&size=100`. Both Reddit
   and PullPush rate-limit (403/429). Back off and switch method rather than hammering. Good
   patient-voice subs for PT: r/running, r/AdvancedRunning, r/Fitness, r/weightroom, r/Pickleball,
   r/golf, r/backpain, r/Sciatica, r/KneeInjuries, r/Posture, r/AskDocs, r/Mommit, plus the
   client's city sub (e.g. r/Austin) for "any good PT recommendations?" threads.
3. **Google reviews of local competitors:** use the `playwright` browser on Google Maps (the same
   free approach `leadgen-agent` uses; no Places API). Take the 5-8 top clinics in the client's
   geo. For each one, sort reviews by **Lowest** (what they hate, i.e. gaps the client can own)
   and **Newest** (what they praise now). The Places API (`PLACES_API_KEY` in Doppler) is only a
   fallback: it's metered and returns 5 reviews per place.
4. **YouTube comments:** find 5-10 popular videos on the segment's problem ("runner's knee fix",
   "is physical therapy worth it", "desk neck stretches"). Pull the comments with yt-dlp:
   ```bash
   PYTHONIOENCODING=utf-8 python -m yt_dlp --skip-download --write-comments \
     --extractor-args "youtube:max_comments=300,all,0,0" -o "<scratch>/yt/%(id)s.%(ext)s" "<url>"
   ```
   The comments are in `<id>.info.json` under `comments[].text`. Work in the scratchpad, and only
   copy the selected quotes into `raw/youtube.md`.
5. **TikTok:** `playwright` search for the segment's problem. Read the comments where they're
   visible without logging in. If there's a login wall, note it and move on. Don't log in.
6. **Amazon reviews** of what the segment buys when it tries to fix the problem alone (knee braces,
   foam rollers, posture correctors, TENS units, back stretchers). The 1-3 star reviews show "what
   I tried that didn't work", which is a ready-made "you've tried X" hook. Use `playwright` on the
   product page. If it's login-limited, take what's visible.
7. **Competitor ad comments and forums:** public comments under competitor PT ads (find the ads via
   `research-competitors` / the Ad Library and open the post if it's public), and public
   Facebook-group, Quora or forum threads found with `WebSearch`. Best-effort only. Don't log in
   anywhere.

### 3. Raw findings checkpoint → GATE R2

Post in chat:
- quote counts per platform and per segment, and what was blocked or thin
- the 3-5 strongest quotes per theme (pains, tried-before, objections, dream outcome, insider words)
- your early read: the 3 things that came up most, and anything surprising

**GATE R2:** Dylan flags anything off-target (wrong segment, clinician noise, out-of-area) and
points where to dig deeper. Loop collect → checkpoint until he approves the raw set.

### 4. Synthesize the dossier → GATE R3

Write `outputs/research-<slug>-<date>/deep-research.md`. **Every claim cites 2+ quotes** (by link)
from the raw files. No claim without evidence. Sections:

1. **Segment snapshot**: who they are, a day in their life, the trigger moment that makes them
   look for help *now*.
2. **Pains, ranked** by how often and how intensely they come up. 2-3 verbatim quotes each.
3. **What they've already tried, and why it failed** (rest, YouTube stretches, chiro, braces, a
   previous PT who "just gave me a sheet of exercises").
4. **The dream outcome in their words** (the race, the full night's sleep, the kid lifted without
   thinking).
5. **Objections and fears** (cost, insurance, time off work, "PT didn't work last time", fear of
   surgery or of being told to stop running).
6. **Language bank**:
   - *Self-labels* they actually use (feeds the callout rule)
   - *Insider words / in-jokes* (feeds Connection)
   - *Phrases to lift as-is* for hooks
   - *Stock phrases to avoid*: what every clinic says and readers have gone blind to ("root cause",
     "get back to doing what you love")
7. **Competitor gaps from reviews**: what people praise and complain about at local clinics, and
   which complaint the client can credibly own (checked against `client-context.md` and the
   onboarding voice rules).
8. **Emotional register**: which of Attention / Curiosity / Emotion / Connection to lead with for
   this segment, and dark (frustration, self-blame, fear) vs. light (humor, identity), with the
   evidence.
9. **Angle candidates (8-12)**: each tagged with its **awareness stage** (unaware → most aware)
   and its **sub-problem avatar** (e.g. "runner, knee flares after long runs" vs. "runner, back
   tightens on hills": different people, per the personification rule in the AdsMastery 2027
   section), with the lead element, the core emotion, 2+ supporting quotes
   and a draft hook that passes Meta's personal-attributes rule (about a situation, never asserting
   the viewer's condition) and the no-emoji, plain-writing rules.
10. **Confidence and gaps**: thin or blocked sources, and what to verify with the client.

**GATE R3:** Dylan reviews the dossier, especially the angles and the language bank. Revise until
he approves.

### 5. Finalize

Once Dylan approves:
- Copy the dossier to `clients/<slug>/deep-research.md` (one current dossier per client. When a
  segment is re-researched, update its sections in place).
- Write `clients/<slug>/customer-language.md`: the curated quote bank (the best 60-100 quotes,
  grouped by segment and theme, with source links). `generate-ad` lifts hooks and callouts from
  here.
- Delete `outputs/research-<slug>-<date>/` once both files are confirmed in `clients/<slug>/` (the
  finalized-only folder convention in `CLAUDE.md`).
- Add any finding that generalizes beyond this one client (e.g. a hook pattern that works across PT
  segments) to `context/ad-creative-principles.md` as a short dated lesson. Client-specific findings
  stay in the client folder.

---

## Guardrails

- **Never put a real person's quote in an ad as a testimonial.** Research quotes are *language
  input*: rewrite or adapt them into hooks. Only the client's own patients' reviews can appear as
  attributed proof, and then with first names only.
- No health details tied to an identifiable person in any file. Strip anything identifying from
  SMS-thread quotes (names, addresses, phone numbers).
- No logging in to any platform, no bypassing paywalls or CAPTCHAs, no automated mass scraping. Read
  what a normal visitor can see, at a human pace.
- Price objections and price sensitivity are key inputs for `build-offer`, so log them carefully.
  Client funnels push the free consult (or the client's approved offer), so price objections get logged as
  research, not answered with a price in an ad.
