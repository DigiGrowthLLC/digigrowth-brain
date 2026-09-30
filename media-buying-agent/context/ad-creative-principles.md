# Ad Creative Principles

Reference knowledge for what makes Meta (Facebook/Instagram) ad creative actually work. Distilled
from study of paid-ads strategy content — first source: a 2026 breakdown of Alex Hormozi's Facebook
ads approach (via "The Moonlighters," an agency running 100+ brands) covering Meta's Andromeda
algorithm and creative-scaling strategy. Add new sources as their own dated section below as more
research comes in — don't overwrite prior sections.

---

## Source: Hormozi / Andromeda Ads Breakdown (2026-09-13)

### The Core Shift: Content IS Targeting Now

- Meta's "Andromeda" algorithm optimizes the news feed by matching **concepts** (not audiences) to
  people. A concept = an **avatar** (who the ad is for) + a **template/angle** (how it's presented).
- Practical result: **who/what you show and talk about in the ad determines who it gets shown to** —
  more than interest-based targeting does. "Put a chicken in the ad, you get more chicks. Put an old
  guy in the ad, you get more old guys." Message-match beats manual targeting.
- You don't need to lean as hard on audience/interest targeting anymore. Lean on **making the
  creative itself unmistakably FOR one specific avatar** — value delivered fast, plus a clear slice
  of who it's for.

### The Framework: Problem → Mechanism → Concept → Iteration

1. **Define the problem** — the specific pain point one avatar has.
2. **Define the mechanism** — why your product/offer solves it (the "how it works" story).
3. **Build the concept** — avatar + template/angle combined into one ad.
4. **Create iterations** — once a concept works, produce variations of it (see below), not
   unrelated new ideas.

One product can carry multiple totally separate concepts/angles at once (e.g. same supplement
marketed as "better digestion" to one avatar and "thicker hair" to a completely different avatar) —
these are independent campaigns, not competing messages.

### Go Niche, Then Go Deep (Iteration Strategy)

- Don't make one broad ad for a category (e.g. "plumbers") — make many ads for narrow slices of that
  category (e.g. 10 ads for 10 different kinds of plumbing situations/plumbers). Niching down lowers
  cost per result, but requires more total ad volume to cover the space.
- When an angle/avatar wins, **go horizontal on that specific thing** — don't pivot to a random new
  angle. Vary style, tone, proof, format, or presentation *within* the winning avatar/angle. Iterating
  on a winner beats hunting for a new winner from scratch.
- Winning brands (example: Grooms) run **thousands** of iterations within a handful of proven
  angles — this is the norm at scale, not overkill.

### Efficiency Is Per-Angle, Not Portfolio-Wide

- Different avatars/angles have different scalability ceilings — one might do 5x ROAS at $100/day,
  another 2x ROAS at $10k/day. These are **independent of each other**, not in competition.
- Don't over-index on chasing the single highest-ROAS angle. Instead: **keep any angle running as
  long as it clears your minimum efficiency bar** (e.g. 2x ROAS or whatever the business needs),
  regardless of how it compares to your best performer. Stack multiple angles that each individually
  clear the bar — this is how the biggest ad accounts scale total spend.

### The Organic-to-Paid Creative Flywheel

- Instead of only creating new ads from scratch or copying competitors' winning ads, mine your own
  **organic content** for pieces that already performed well, then repurpose the best ones directly
  into paid — often with nothing more than a simple CTA overlay/banner added on top.
- Organic winners are pre-validated by real audience engagement before they ever cost ad spend —
  they're a shortcut past the "create → wait → analyze → repeat" cold-testing cycle.
- Guardrail: set minimum spend so every new creative gets a fair testing budget, and set a maximum so
  organic-viral content doesn't hog ad account spend it hasn't actually earned through ad performance.

### Volume Is the Cost of Scaling

- More niche targeting means more required ad volume — this is a trade, not a downside to avoid.
- AI-assisted creative production is what makes "hyper-personalization at scale" (many avatar/angle
  permutations, produced fast) practical — this is the entire justification for this agent existing:
  produce a high volume of on-concept creative variations quickly, not one "perfect" ad.

---

## Source: Post-Andromeda Media Buying Live Q&A (2026-09-13)

A working media buyer's live Q&A on how creative strategy changed after Meta's 2026 "Andromeda" ad-
retrieval update. This is a deeper, more tactical layer underneath the Hormozi section above — same
underlying shift (creative volume + Andromeda), but with the actual mechanics and numbers.

### Why Andromeda Exists

- AI made ad-creative production (copy, images, video) so cheap and fast that the supply of creatives
  entering Meta's ad auction exploded over the last ~12 months.
- The old retrieval system graded every individual creative one by one — it couldn't sustain that
  volume. Andromeda's fix: **group all iterations/variations of the same concept into one "container"
  and grade the container as a whole**, instead of scoring each creative separately.
- This is the mechanical reason behind the "content is targeting" shift — Andromeda is specifically
  about the **ad retrieval** step (step 1 of Meta's 4-step ad-serving pipeline: retrieval → heavy
  sorting → light sorting → ranking), which narrows ~10M+ daily ads down to a few thousand candidates
  per user in under 200ms.

### New Concept vs. Iteration — the central distinction

- **Iteration** = a small variation of an already-proven concept: a different hook/headline, a
  different thumbnail, a minor copy tweak. Andromeda buckets these together and treats them as
  basically one ad.
- **New concept** = something Andromeda will treat as genuinely different. Any of these alone counts:
  - **New format** — long-form VSL vs. mini VSL vs. static vs. UGC vs. native/advertorial vs.
    interview-style vs. podcast-style. Same script, new format = still a new concept.
  - **New archetype/angle** — a different reason a different kind of customer buys, even for the same
    problem (e.g. "the doctor dismissed my pain" vs. "I fixed it myself" are different archetypes for
    the same foot-pain product). Angle and archetype are effectively the same lever.
  - Changing the **mass desire** itself (the core problem/outcome) is NOT a new concept — that's
    launching a different product/business line. Stay within one mass desire; vary format/archetype
    around it.

### The Ratio Flip

- **Pre-Andromeda:** ~80% iterations / 20% new concepts (test lots of hook variants on what's working).
- **Post-Andromeda:** flip it — **~80% new concepts / 20% iterations**. Only start iterating on small
  variations *after* a new concept has proven itself; don't lead with micro-testing.

### "Quantum Leaps" — how to break a scaling plateau

- Everyone hits a spend ceiling (could be $1k/day or $100k/day). Micro-variations (a new hook, a new
  thumbnail) will not break through it — they produce small, incremental gains at best.
- Breaking a plateau requires **drastic, new-concept-level swings** — a genuinely different format or
  archetype, not a 30th hook variant on the same ad. Ask: "if I only had 15 chances to make a winning
  ad, would I spend them on 15 tiny hook variants of one idea, or 15 completely different concepts?"
  Always the latter.

### Launch Volume & Budget Minimums

- Recommended: **10-15 genuinely distinct new concepts** per new ad account or new creative batch —
  not the old 3-5.
- On a lower budget (~$60/day total), scale that down to **~5** concepts instead.
- Target roughly **$10+/day of spend per ad** minimum for the algorithm to gather enough data to
  judge it fairly — going lower rarely produces a real signal.
- New-concept testing is inherently uncontrolled (you're changing format + archetype + copy all at
  once) — that's expected and fine; it's not meant to be a clean scientific A/B test.

### Where to Split-Test What

- **Small changes** (headline, minor copy) → test inside your funnel/landing-page software (e.g.
  Funnelish, CheckoutChamp), not as a Meta-level split test.
- **Big swings** (an entirely new advertorial/page/story) → test at the ad set or campaign level
  inside Meta, since that's a new concept, not a minor iteration.

### Segment by Creative Type

- Don't mix static images and video in the same ad set/campaign — Meta tends to favor images' lower
  CPMs within a shared container, which starves video of spend even if the video would perform well
  on its own. Run statics and videos as separate ad sets/campaigns.

### Campaign Structure Post-Andromeda

- **"Creative is the targeting."** Interest-based targeting is largely unnecessary now — one broad
  Meta Advantage+ audience per campaign is enough. Only set demographics that are truly required
  (e.g. gender/age if the offer genuinely only applies to one group); leave everything else broad.
- **ABO (ad set budget optimization)** is generally preferred for creative testing — it lets you
  control exactly how much budget each test concept gets. **CBO (campaign budget optimization)** /
  ASC (Advantage+ Shopping/Sales Campaigns) is fine once a concept is proven and you're scaling —
  some of the largest ad accounts run pure broad CBO/ASC successfully, so this is a testing-phase
  default, not an absolute rule.
- Keep **geo targeting broad** — stack same-language countries together in one ad set (e.g. all
  English-speaking "Big 5" countries) rather than splitting by individual country, unless running a
  genuinely different language or funnel per country.

### Evaluation Window

- Judge ad performance over **7+ days**, not day-to-day swings — "when in doubt, zoom out." Meta's
  algorithm needs accumulated spend/data over time to optimize; daily ROAS/CPA volatility is normal
  and not a reliable signal on its own.

### The Golden Rule

- **If an ad is profitable, don't touch it or turn it off** — even if its soft metrics (CTR, CPC)
  look weak. A low-CTR, high-qualification ad can still be one of the most profitable ads in an
  account. Profitability overrides vanity metrics every time.

### Manual Bidding Basics (for context, not core to creative generation)

- **Cost cap** — the max cost-per-result you're willing to pay; set too low and Meta may simply
  refuse to spend because it can't find that cheap a result.
- **Bid cap** — a max multiplier on your bid in the live auction, rather than a target cost.
- Both are manual alternatives to Meta's default auto-bidding.

### Universality

- This entire framework (new concept vs. iteration, the ratio flip, campaign structure) is stated to
  apply regardless of niche — e-commerce, SaaS, info products, lead gen. The algorithm doesn't
  differentiate by vertical.

---

## Source: Meta Ad Library Field Scan — Pain/PT/Chiro/Ortho Vertical (2026-09-13)

Live-browsed `facebook.com/ads/library`, sorted by total impressions, filtered to pain/physical-therapy/chiropractic/orthopedic advertisers in the US. These are ads real competitors are still paying to run (several since early-to-mid 2025) — per the "golden rule," an ad still running a year later is a validated winner, not a guess. Findings are specific to this vertical, not universal.

### The dominant winning template in this vertical
The single most repeated structure across unrelated advertisers (chiropractors, wave/shockwave-therapy clinics, orthopedic surgeons) is close to identical:
1. **Direct city/neighborhood callout** opening line — "Hey Phoenix!" / "Hey West Jefferson, London & Surrounding areas!" / "Hey Wesley Chapel & Nearby Areas!" — this out-performs a generic opener because it's an instant, unmissable relevance signal before the reader even processes the offer.
2. **A named low-friction intro offer**, often with a specific dollar price and an artificial scarcity number ("30 vouchers... for just $49").
3. **A bullet/emoji checklist of specific conditions treated** — ✅ Knee Pain ✅ Shoulder Pain ✅ Back Pain ✅ Neck Pain, etc. — lets the reader self-identify in under a second rather than reading prose.
4. **"Without medicine or surgery"** or similar non-invasive framing shows up repeatedly as the core value prop for the pain-avoidant avatar.
5. **Address + "Learn more" CTA** into a dedicated offer landing page (not the clinic's homepage).
6. Native-feeling **talking-head video (60-90 sec)**, not polished production — the practitioner or clinic owner speaking straight to camera dominates the highest-impression ads in this vertical over static images.

### Orthopedic/surgeon-tier ads skew softer and more relational
Ads from named physicians (e.g., spine surgeons) lead less with urgency/discount and more with **removing intimidation and pressure**: "consultations should feel like real conversations... without pressure," "the next step can feel intimidating." This is closer to CrosaCore's actual brand voice (calm, credentialed, non-hypey) than the voucher-scarcity template above — worth blending: borrow the *structure* (city callout, condition checklist, low-friction CTA), not the hype tone, for a premium/individualized cash-pay positioning.

### Applicability note
Don't copy the "$49 voucher, only 30 spots" scarcity mechanic onto a practice whose actual positioning is unhurried/individualized/non-mill — it would contradict the brand promise on the landing page itself (CrosaCore explicitly says "not a generic program," "no pressure," one-on-one). Use the proven *structural* elements (geo callout, symptom checklist, real-practitioner talking-head video, low-friction single CTA) and keep the tone matched to the actual offer.

---

## Lesson: raw client footage still needs an ad structure (2026-09-13)

Caught by Dylan on the CrosaCore plan: the client portal had real talking-head video of the
practitioner, and the first draft of the plan treated it as launch-ready ad creative because it was
real/organic/on-brand. It wasn't — it was educational content (Brandon explaining a pain topic to
camera) with **no hook, no on-screen offer, no testimonial, no CTA**. The "organic-to-paid flywheel"
principle above (mine raw content for what already performed) only applies to content that already
has an ad's bones — a hook, a payoff, something that already stopped a scroll. Purely educational
raw footage needs an edit pass (title card hook, condition checklist, closing testimonial + CTA)
before it's usable as an ad, not zero editing. Default to **static image + text overlay** as the
fast, genuinely ad-shaped launch creative when the available video is raw/educational, and treat an
edited video version as a follow-on once a concept proves itself — not the Week 1 asset.

## Lesson: pull the full onboarding record, not just the deployed landing page (2026-09-13)

The CrosaCore plan's first draft was built from the funnel page + testimonial library alone and
missed the client's own onboarding answers (`GET /api/clients/{id}` → `onboarding` object), which
carry the actual **brand voice rules** (Brandon's: no guarantees/absolute claims, no attacking prior
providers, no hype, no em dashes), **ideal patient description in his own words**, **real drop-off
objection** (cost, for a cash-pay practice), and **economics** (avg. patient value, visit count).
These are load-bearing for ad copy, not optional color — always pull the full client record's
`onboarding` section before writing copy, not just the deployed page and uploads list.

---

## Source: Alex Hormozi Landing Page Value Equation Breakdown (2026-09-13)

Transcribed from a YouTube breakdown of Alex Hormozi's landing page strategy. The source is about
landing pages, not ad creative directly — but the "above the fold" section he describes (headline,
sub-headline, CTA, hero image) is functionally the same object as a Meta ad (headline + image +
CTA), so the value-equation and visual-proof principles below transfer directly to what `generate-ad`
produces. Skipped: AB-testing cadence and CRO-traffic-threshold advice, which is landing-page/traffic-
specific and doesn't apply to single ad-creative generation.

### The Value Equation, applied to one ad

Every ad's copy + image pairing should hit all four of these, not just "hook → problem → solution":

1. **Dream outcome** — state the end result the avatar wants, not what the product/service *is*.
   Use the **"so that" principle** to convert a feature into an outcome: "we offer X **so that** you
   get Y **so that** you can Z" — chain it until you hit the actual emotional payoff. A solar-cleaning
   business rewriting "exterior cleaning services" as "clean solar panels so your energy bill drops so
   you know your system is actually working" saw a 64% lift — that's the size of gain available just
   from restating the same offer as an outcome.
2. **Perceived likelihood of success** — via (a) visual social proof and (b) risk reversal (see below).
3. **Time delay** — name a specific timeframe in the hook/headline if the offer has one ("in 30 days,"
   "in just 2 weeks") — closes the gap between "I want this" and "when do I get it."
4. **Effort/sacrifice** — the copy should make the offer feel effortless, not list everything required
   of the customer. If a process has to be shown, cap it at 3-4 steps — more than that reads as more
   effort even if it's factually accurate.

### The image should show the outcome, not the product

"Most landing pages suck. Here's how to have them suck less. The hero image should add proof to the
headline." Directly actionable for `generate_creative.py` image prompts: don't default to a generic
product/lifestyle shot — the image prompt should depict **the dream outcome itself** (the result the
avatar gets), matched to whatever the headline promises. If the headline promises a specific visual
result (a look, a space, a physical state), the image must show that exact thing, not an approximation
or a stock-style stand-in.

### Visual proof beats text proof — stack it, don't just state it

- Plain text reviews are overused and now largely ignored ("people don't trust it on its own
  anymore"). Prioritize **visual proof formats** over quote-in-a-box testimonials whenever an image
  concept includes proof: a before/after, a screenshot-style result, a photo of the outcome — visual
  beats text, video beats photo. Reported lift from this alone: 50-70%.
- Where multiple proof points exist, show volume ("wall of love" — many reviews/results shown at once,
  never hidden in a single rotating carousel) rather than a single cherry-picked quote — overwhelming
  volume of proof reads as more credible than one polished testimonial.

### Risk reversal directly under the CTA

Put a specific risk-reversal element (guarantee, warranty, free trial, "cancel anytime," etc.) as a
short badge/line **directly under the CTA button/text** — reported as a 30% conversion lift in
isolation on one client. For `generate-ad` output: when the offer has a real guarantee or no-risk
term, it belongs in the ad copy immediately after the CTA, and can be rendered as a small badge/tag in
the image itself (via the `text-creative`/Ideogram path in `creative-gen`) rather than left out of the
visual entirely.

### Headline is still ~80% of the ad's effect

"Once you've written your headline, you've spent 80 cents of your advertising dollar" (Ogilvy, cited
approvingly). Practical test for any headline/hook this skill writes: if the avatar reads *only* the
headline and nothing else, is the outcome, and who it's for, already unmistakably clear? If the
headline needs the body copy to make sense, rewrite the headline, not the body.

---

## Source: "The Only 2 Ad Creative Formats You Need" — The Moonlighters (2026-09-13)

Same agency/channel as the earlier Andromeda breakdown above ($500M+ managed Facebook/Google spend
over 11 years, $100M+ in the last year alone). This source is specifically about which ad *formats*
to actually produce and directly shapes what `generate-ad` should default to writing.

### Volume alone is worthless — only the "creative hit rate" matters

- **Creative hit rate = (# high-performing ads) / (total ads launched) × 100.** A "high-performing"
  ad is defined as one that spent more than 5% of total campaign budget AND hit its CPA/ROAS target.
- The total number of ads produced means nothing on its own — "the only thing that matters is the
  number of high performing ads in your account." A 5% hit rate is normal/solid; more volume only
  helps because it produces more winners at that same rate, not because volume itself is a lever.
- Practical implication for this skill: **don't pad a batch with weak filler concepts to hit a volume
  number.** Every concept produced should be a genuine attempt at a winner — quality-of-concept is
  what compounds, not count of files in a folder. This refines (doesn't contradict) the "10-15 new
  concepts" launch-volume guidance above — that's a target count, not a permission to lower the bar
  per concept.
- Bad pixel-training mechanism (why sloppy volume actively hurts, not just wastes budget): every ad
  served — including weak ones — feeds signal to Meta's pixel. High-volume low-quality creative
  generates more "visited but bounced" negative-adjacent events, which drags the account's delivery
  quality down, not just that one ad's performance.

### Skip the middle of the funnel entirely — build only the two extremes

- Classic top/middle/bottom funnel planning is "great in theory but not how Facebook ads work." The
  fix: **only build ads for the very top of funnel and the very bottom of funnel.** Never build a
  dedicated "middle funnel" ad.
- Why this works: ad quality naturally spans a spectrum — a strong top-of-funnel ad's spillover
  reaches some of the middle audience anyway, and a strong bottom-of-funnel ad's spillover reaches
  the rest of the middle. Aiming at the extremes covers the middle "through natural osmosis" without
  ever diluting an ad's focus by trying to speak to two audience states at once.
- **This directly sets the default for what `generate-ad` should ask/assume**: every concept request
  should be explicitly TOP-OF-FUNNEL (problem+solution) or BOTTOM-OF-FUNNEL (objection), never a
  vague "general" ad. If Dylan doesn't specify, default to producing one of each rather than one
  ad that tries to do both jobs.

### Format 1 — Top of funnel: Problem + Solution

- Audience state: not aware of the problem, the solution, or the product (true cold/net-new).
- Formula: **name the avatar's specific problem, then position the offer as the solution to that
  exact problem.** Every product solves *some* problem, even an identity/emotional one ("makes me
  feel like I'm part of something") — if the offer feels like it has no problem to solve, dig
  further into the avatar's emotional/identity motivations rather than concluding there isn't one.
- **The Avatar Framework** (the concrete tool for generating angles): list out every problem a given
  avatar has — irrelevant-to-the-product problems included, cast a wide net. Each individual problem
  becomes a candidate **ad angle**. Avatar + one specific angle = one ad concept.
- **One product can and should run entirely different avatar/angle pairs as separate concepts** — not
  as a hedge, but because the Andromeda algorithm auto-routes each ad to whoever it's visibly speaking
  to. Real example cited: the same supplement brand runs one set of ads calling out GLP-1/Ozempic
  users ("lose weight, not your metabolism") and a completely separate set calling out hair-thinning
  concerns ("keep your hair full and thick") — same product, two unrelated avatars, each gets its own
  concept, both run at once.
- Top-of-funnel ads tend to run longer/heavier (strong hook, fuller body copy, explicit CTA) since
  there's more explaining to do for a cold audience.

### Format 2 — Bottom of funnel: Objection-only

- Audience state: already knows the problem, the solution category, AND the product — they haven't
  converted yet because something specific is stopping them.
- Formula: **pick ONE real objection and address only that one** — never restate the full pitch.
  "This is only an ad you would see in the bottom of funnel" specifically because it calls out one
  thing and stops.
- How to actually source real objections (don't invent them): (1) write down every objection you
  already know the offer gets, (2) call customers who abandoned checkout and ask directly why — this
  is described as reliably surfacing the real reason, not a hypothetical exercise.
- Cited examples of single-objection bottom-funnel ads: a hair-care ad that calls out exactly one
  clinical claim and nothing else; a cookware ad (HexClad) that exists purely to neutralize the
  "competitor products have only a 1-3 year warranty" objection by leading with lifetime warranty —
  no other selling in the ad at all.
- The most common objection worth defaulting to when nothing else is specified: **price** — either
  show favorable value/comparison vs. a competitor, or make the value of the specific price
  unmistakable, rather than a generic "great value" claim.
- Retargeting/catalog ads (dynamic product ads to people who already viewed) are the other bottom-
  funnel lever mentioned, but that's a campaign-setup concern (`build-campaign-plan` territory), not
  a creative-generation one.

### What NOT to pull from this source into `generate-ad`

The back half of the video covers live Ads Manager campaign/ad-set structure (naming convention
`pack_<avatar>_<angle>`, CBO settings, conversion-event selection, audience exclusions, budget
scheduling). That's targeting/campaign-structure knowledge for `build-campaign-plan`, not creative
generation — skipped here to keep this file scoped to what actually changes a `generate-ad` output.

---

## Source: Meta Ads Beginner Fundamentals — "What You NEED To Know To Get Started With Meta Ads" (2026-09-22)

Transcribed from a YouTube beginner's walkthrough of Meta Ads Manager. Unlike the sources above (which
assume an existing account and focus on creative/scaling strategy), this one covers account-setup and
account-structure fundamentals — directly relevant to `build-campaign-plan`'s "campaign settings table"
and "blockers to clear before spending anything" sections, not just creative generation.

### The three-layer mental model (campaign → ad set → ad)

- **Campaign** = the objective layer. Decide here: sales, leads, website traffic, video views, etc.
- **Ad set** = the audience + placement layer. Decide here: who sees the ad (targeting) and where
  (Facebook/Instagram feed, Stories, Reels, etc.).
- **Ad** = the creative layer. The actual image/video/copy/CTA button a real person sees while
  scrolling.
- Nearly every setting in Ads Manager belongs to exactly one of these three layers — framing a
  client's dashboard confusion in these terms ("that's an ad-set decision, not a campaign decision")
  is a useful explanatory tool for `build-campaign-plan` output, not just a mental model for Dylan.

### Account setup — do these BEFORE the first ad goes live, not after

Directly maps to the "Blockers to clear before spending anything" section of the campaign-plan template:

- **Set up a proper Meta Business Portfolio (Business Manager) before creating any ads.** Advertising
  directly from an Instagram profile is the tempting shortcut but costs ~30% more for the same results
  and has materially fewer options. Flag as a blocker if a prospective client's account isn't set up
  this way yet.
- **Install the Meta Pixel on the client's site before the first ad launches**, not after. Without it,
  Meta can't tell whether people who click through actually do anything on the site — "advertising
  blind." This is a concrete, checkable blocker: confirm pixel presence when reviewing a client's
  `landing_page_url` / marketing-config, don't assume it's there.
- **Install the Conversions API (CAPI) alongside the pixel, not instead of it.** Since Apple's ATT
  privacy changes, pixel-only tracking misses a meaningful share of conversion events — pixel + CAPI
  together is the accurate baseline, not an advanced optional step.
- **Starting daily budget should be sized to what the business can actually afford to pay per
  acquired customer** — not an arbitrarily small "safe to test" number. A too-small budget doesn't
  protect against waste; it starves Meta's delivery algorithm of enough activity to learn who
  responds, producing unreliable results either way. This is the same underlying logic as this file's
  existing "$10+/day/ad" minimum above — reinforces it from a different angle (learning-phase data
  volume, not just per-ad signal).

### Targeting — the beginner-safe default

- Two audience types worth naming in a plan: **cold** (never interacted with the business) and
  **warm** (visited the site, purchased before, engaged on FB/IG). Warm audiences are the easiest
  place to show a new/small client their first results, precondition being that a warm audience
  (pixel data, page followers, past customers) actually exists yet.
- **Don't over-narrow targeting by stacking many interests hoping to hand-pick the "perfect"
  audience.** A broader, simpler audience is usually the safer starting point — it gives Meta's
  delivery algorithm more room to find the right people itself. Consistent with the existing
  Andromeda-era guidance above (broad Advantage+ audience, minimal demographic restriction) — this
  source independently arrives at the same recommendation from a beginner-account angle rather than a
  scaling angle, which is a second, unrelated source corroborating "go broad."

### Creative basics for a FIRST ad (pre-testing-framework stage)

- The opening image/line has one job: interrupt the scroll within well under a second. This is the
  same "scroll-stopping hook" principle already in this file's Working Checklist, restated for a
  brand-new account with zero data yet.
- **One clear message beats cramming every feature/benefit into a single ad.** Pick the single most
  important thing and lead with only that.
- For a genuinely first launch (not an established account), **2-3 simple variations is enough** —
  framed here not as rigorous testing but as acknowledging you don't yet know what will resonate, and
  as a hedge against early ad fatigue. Lower-volume framing than the "10-15 new concepts" launch
  guidance elsewhere in this file — reconcile by scale: this source is for a client's very first ads
  ever, the 10-15 figure is for an account/creative batch with some budget behind it already. For a
  brand-new, low-budget client, default toward this source's 2-3-to-start guidance and note it
  explicitly in the plan rather than silently applying the larger number.

### Reading results without panicking

- As a beginner account, there are really only one or two numbers worth watching: **ROAS** (revenue
  generated from ads) if trackable, otherwise **cost per conversion**. Ignore the rest of the
  dashboard early on — it's noise relative to whether the ad is actually profitable.
- **Give a new ad several days before judging it** — Meta's delivery system needs real accumulated
  activity to learn who responds; judging after a few hours or one day is unreliable. This matches
  the existing "7+ days, zoom out" evaluation-window guidance above — a second independent source
  landing on roughly the same minimum judgment window.
- Distinguish a **normal early fluctuation** (one high-cost day) from a **genuine bad sign** (cost
  that stays high and keeps climbing over 4+ weeks) — this is the specific beginner failure mode to
  flag in a plan's "weekly checkpoint questions": don't recommend killing an ad off a single bad day.

### What this source adds beyond what was already in this file

Prior sources here (Hormozi/Andromeda, the Moonlighters, the Ad Library scan) all assume an account
that already exists and has some spend history — they're about scaling and creative strategy. This
source is the missing "day zero" layer: the literal account-setup checklist and the beginner-safe
defaults for a client's very first campaign, which is exactly the gap `build-campaign-plan` step 4
("blockers to clear before spending anything") needs concrete, checkable items for (Business
Portfolio set up? Pixel installed? CAPI installed? Budget sized to real CAC math, not an arbitrary
small test number?).

---

## Source: "Maximise META Leads With Only $30 A Day" — Sam / Local-Business Testing Strategy (2026-09-22)

Transcribed from a YouTube video by a media buyer who specializes in **local, brick-and-mortar lead-gen
clients** — the closest match in tone/budget to DigiGrowth's actual client base (e.g. CrosaCore) of any
source in this file so far. Framed explicitly around the most common real client budget: **$30-35/day,
~$1,000/month** — not an e-commerce/$1k-per-day testing budget. Directly actionable for
`build-campaign-plan`'s campaign-structure and budget sections.

### Two-sided test, not just ad performance

- Local lead-gen has a manual conversion step ads don't capture: someone fills a form, then gets
  contacted, then scheduled, then converts to a customer. So every test has **two sides**: (1) the ad
  test — lowest cost-per-lead (CPL), and (2) the back-end test — actual lead *quality*, tracked after
  the fact. A cheap CPL that produces low-quality leads isn't a win; it may require front-end
  adjustments (targeting, ad angle, qualifying language in the ad itself) once the back-end signal
  comes in. **The measurement plan section of a campaign plan should explicitly track lead quality,
  not just CPL**, when the client's funnel has a manual follow-up/booking step (true for essentially
  all of DigiGrowth's current clients).

### Post-Andromeda targeting philosophy (corroborates existing guidance, different angle)

- Old model: each ad set = a different audience segment/demographic, with ads written to speak
  specifically to that segment. If the ad set underperformed, that whole audience was judged "didn't
  work."
- New (Andromeda) model: the algorithm operates at the **campaign** level, reading signals from the
  ads themselves to route each individual ad to whichever users are most likely to respond —
  independent of how the ad sets are structured. Practical result: **you don't need to
  audience-segment your ad sets anymore; the creative itself is what gets matched to the right
  person.** This independently corroborates the "content is targeting" principle already documented
  above (Hormozi/Andromeda source) — a second, unrelated source arriving at the same conclusion from
  a local-lead-gen angle rather than an e-commerce/DTC angle.

### The "ad set trio" structure — the core tactical recommendation

For a $30-35/day local-business budget, don't run one flat ad set with everything mixed in (Meta will
unevenly overspend on early leaders and starve the rest), and don't fragment into many small ad sets
either (unmanageable, spreads budget too thin to reach real signal). The middle path:

- **Group ads into ad sets by format, not by audience/demographic** — e.g. Ad Set 1 = static images
  only, Ad Set 2 = UGC-style talking-head videos only, Ad Set 3 = carousel/slider ads only.
- **Reason for grouping by format specifically:** Meta's delivery algorithm has a built-in placement
  bias by media type — mix a video, an image, and a carousel in the same ad set and Meta will often
  just dump most of the budget on the video and starve the other formats of a fair test, regardless of
  which would actually perform best. Segmenting by format removes that bias and lets each format
  genuinely compete on its own merits.
- **Run exactly 3 active ads per ad set at a time** ("trios") — different hooks/styles/angles within
  the same format. This gives Meta's within-ad-set creative competition room to find a within-format
  winner while still capping total ad count to something a $30-35/day budget can actually fund a real
  test on.
- When a format/ad set isn't producing results after a fair test, **kill the whole ad set and swap in
  a different format** (e.g. drop carousels, try AI-generated UGC-style talking-head instead) — don't
  keep limping along with a format that's already shown it doesn't work for this client/vertical.
- When a specific ad within a trio wins, **duplicate that winning ad and iterate variations of it
  within the same ad set** (new headline, new benefit angle, same underlying format/style) — this is
  the same "iterate on a winner, don't hunt for a new one" principle already documented under the
  Hormozi/Andromeda source above, applied concretely at the ad-set level.
- Once a format/ad set is clearly winning, **scale its daily budget gradually** (e.g. $45/day → wait
  3-4 days → $60/day) rather than jumping it sharply — avoids resetting the ad set's learning phase.

### Minimum spend before judging an ad — a concrete number, not just "wait a few days"

- **Let an ad spend 1-3x the target CPL before judging it a failure.** E.g. if the target CPL is $30,
  an ad that's only spent $15 hasn't even reached the target cost yet — there's no real signal either
  way. An ad that's spent $60 (2x target) with a low click-through rate and zero leads has had a fair
  shot and can be confidently turned off.
- This is a more precise, budget-relative version of this file's existing "$10+/day/ad" and "7+ days"
  evaluation-window guidance above — use **whichever threshold is stricter** for a given client: the
  1-3x-target-CPL rule scales correctly for both very cheap and very expensive target CPLs, where a
  flat dollar/day minimum doesn't.

### Applicability note

This source explicitly frames itself as "not the one true testing strategy for everybody" — the
grouping-by-format + trio structure is the author's current preferred approach post-Andromeda,
replacing an older per-ad-set-per-audience-segment method they used to run. Treat as a strong,
directly-applicable default for DigiGrowth's typical local-service client budget tier
($30-35/day-ish), not a universal law — note in a plan if a client's real budget or vertical suggests
a different structure fits better.

---

## Source: "Claude + Meta Ads Library = Unlimited Winning Ads" — The Moonlighters (2026-09-22)

Same agency/channel as the earlier Andromeda and "2 Ad Creative Formats" sources. This one is
specifically the **workflow** for turning Ad Library research into finished creative — splits cleanly
into a `research-competitors` half and a `generate-ad` half. Skipped: promotion of "Super Scale" (a
paid third-party tool not integrated at DigiGrowth) — the underlying workflow it automates is what's
extracted below, not the tool itself.

### For `research-competitors`

- **Search by named competitor first, not just vertical keywords.** Type a specific known competitor
  into the Ad Library, sort "all active ads" by impressions high-to-low — this surfaces which of
  *that one brand's* ads are working, which is a sharper signal than a generic vertical keyword search
  alone. Use both: named direct competitors *and* a broader vertical keyword search.
- **Caveat to the existing "long-running ad = validated winner" rule:** run-duration alone can
  mislead in the other direction too — an ad that started running "over a month ago" isn't
  automatically still fresh; it can already be fatiguing by the time you find it. The strongest
  signal isn't just "has this been running a long time" but "is it still actively running *and*
  still getting real spend/impressions *now*" — check recency of activity, not just start date, when
  ranking ads worth recreating.
- **Ad Library images are often watermarked "Protected"** — this blocks most AI image tools from
  doing anything useful with a direct copy/paste of the ad image (they'll refuse or ignore the
  protected image). Flag this as a practical blocker when a finding recommends recreating a specific
  competitor visual — the *structural pattern* (documented in words) is what's portable, not the raw
  image file itself.
- **Look outside the immediate vertical for structural trends too**, not just direct competitors —
  cross-category patterns (e.g. "value stacking," "features into benefits," a specific lighting/photo
  style) that are working broadly across many unrelated categories are often the earliest signal of
  something worth testing, before it's common inside any one specific vertical. Worth a supplementary
  WebSearch/Ad-Library pass beyond the client's exact niche when time allows.

### For `generate-ad`

- **New technique: recreate a specific competitor ad as an image-edit task, not a from-scratch
  generation.** When Dylan (or `research-competitors`) points to one specific competitor ad worth
  recreating: describe its structure in the image prompt (composition, layout, proof placement) and
  explicitly instruct the image model to swap in the client's own branding/product/subject in that
  same structure — this produces something closer to a validated, proven layout than a from-scratch
  prompt does. Pair with a request for **3 alternate headline options**, not just one, so Dylan has a
  real choice rather than a single take.
- **Reinforces the existing iteration-mode framing above**: this source's own definition of "a winner
  worth recreating" (spend concentrated in that one ad, sustained return over time) matches the
  ratio-flip principle already in this file — iterate on proven winners, don't hunt for brand-new
  angles once something's working. This agent has no live Meta ad-account API access (see
  `CLAUDE.md`), so "define the winner automatically from ad-account data" isn't something this skill
  can do itself — Dylan has to tell it which concept won, same as the existing iteration-mode trigger.

---

## Source: "How To Make AI Ads With Claude x Meta [MCP]" (2026-09-22)

A promotional walkthrough for a Meta-MCP + Arcads (third-party UGC video generator) workflow: connect
Claude directly to a live Meta ad account, research winning ads, generate UGC actor videos, then
**upload and launch the campaign and pull live performance data, all via MCP, never opening Ads
Manager**. Most of this is explicitly out of scope for this agent — see `CLAUDE.md`'s "What You Do
NOT Do": DigiGrowth has no `ads_management` API access, so the Meta-MCP research/upload/launch/track
loop this video demonstrates isn't something `research-competitors`, `generate-ad`, or
`build-campaign-plan` can do. What's extracted below is the transferable part — the research prompt
structure and the script/creative discipline — not the account-connected automation.

### For `research-competitors` — a sharper research-prompt structure

Even without live ad-account access, the *shape* of the research ask is reusable via WebSearch alone:
when researching a vertical/product category, explicitly ask for (and organize findings by) these
four things, not just "what's working":
1. Which **creative formats** are getting the highest impressions/engagement (UGC talking-head vs.
   static vs. carousel vs. produced video).
2. Which **hooks** (opening lines/frames) are driving the highest engagement.
3. Which **audience segments** are responding best (age/gender/interest clusters, where stated).
4. **Repeated creative patterns** showing up across multiple winning ads (this is the same
   "repeated structural patterns across unrelated advertisers" principle already in this file, just a
   cleaner checklist framing of it).

### For `generate-ad` — script timing structure and a self-scoring gate

- **Explicit timing breakdown for a short (18-20s) UGC-style script**, useful as a reference if a
  video-script version of a concept is ever requested (video generation itself stays out of scope for
  this skill, delegated to `content-agent`): hook 0-3s, problem 3-8s, solution 8-15s, proof 15-18s,
  CTA 18-20s. This is the same hook → problem → solution → proof → CTA framework this skill already
  uses for stills, with concrete second-by-second pacing — worth citing if Dylan asks for a script to
  hand to `content-agent` or a human UGC creator.
- **Self-scoring gate before delivering concepts:** the source's workflow generates 5 scripts, scores
  each out of 10, and only keeps ones scoring 9.5+ before moving to production. Adapt this as a
  discipline for this skill: after drafting multiple concepts, briefly self-assess each against the
  Working Checklist below before presenting them, and flag (don't silently drop) any concept that
  doesn't clearly pass rather than delivering everything generated as if uniformly ready.
- **Actor/avatar spec per angle** (age, gender, setting, emotion) generated alongside each script
  reinforces the existing "avatar + angle = one concept" framework already in this file — nothing new
  here, but confirms the pattern from a third independent source.

### What NOT to pull from this source

The Meta-MCP connection, live account research pull, campaign creation/launch prompts, targeting
prompts, and performance-pull/iteration loop are all live campaign management via API — out of scope
per `CLAUDE.md` regardless of how convenient the demonstrated workflow looks. If Dylan ever wants this
capability, it's a separate initiative gated on Meta API access, not something to quietly fold into
these skills.

### Update 2026-09-29: the video-production half now applies

Re-reviewed when Dylan asked for video ad variations for CrosaCore. The parts skipped above as out of
scope that now matter (written into `generate-ad`'s "Video Ad Variations" section):
- **Image-first, then video:** generate each actor/scene still, review and fix it, and only then turn
  it into video. Fixing a still is much cheaper and faster than regenerating a video.
- **Video prompt style:** "vertical format, handheld feel, candid and authentic", speaking the
  approved script. Casual UGC framing, not polished production.
- **Iterate on a winner = same actor, different scripts.** Once one video wins, the next variations
  keep the speaker/setting and swap the script (hook/angle).
- **Guardrail the source doesn't mention:** its example is a pajama brand, where an actor "loving the
  product" is ordinary UGC. For a healthcare practice, an AI actor presenting as a patient is a fake
  testimonial. Keep real reviews as on-screen text, and let actors voice only the relatable problem.

Also, the Meta MCP connector *is* live now (2026-09-22), but on 2026-09-29 both of its media-upload
tools returned "being gradually rolled out" for CrosaCore's account. Uploads still go through Ads
Manager by hand until Meta enables them.

### Update 2026-09-29 (later): full replication of the loop, and what it taught

Dylan asked for the whole process replicated, so it's now `generate-ad`'s "AI UGC Video Ads" section
(8 steps), first run on CrosaCore (approved: `clients/crosacore/creatives/video-no-time-for-pt/`). Lessons:
- **Arcads vs. fal.ai:** Arcads ($77-110+/mo, prices hidden until signup) is a front end for the
  same models the video uses (Seedance 2.0, Veo, Nano Banana, Kling, Sora) plus an actor library and
  an MCP connector. fal.ai sells those same models pay-per-use with the key we already have, and one
  finished 15s talking ad costs ~$7-8. We don't need Arcads at our volume. Its one real advantage is
  **licensed real-person actors**, which sidestep the face filter below.
- **Seedance 2.0 rejects photoreal AI actors as input images** ("likenesses of real people", 422
  content_policy_violation, partner validation). The better the actor still, the more likely the
  block. **Veo 3.1 accepted the same still** and lip-synced quoted dialogue accurately (verified by
  transcript), but caps at 8s per take, so scripts are written as 2 takes cut together (a native
  UGC jump cut).
- **The research step changed the ad.** The account data confirmed the desk/corporate angle. The Ad
  Library showed every competitor on "root cause / nothing else worked / $49 offer" and **nobody on
  time or convenience**. The client's own reviews had the proof ("concierge care at your home"). The
  resulting angle, "No time for PT? A PT who comes to your house", came from research, not guessing.
- **The research step also caught a false claim.** Earlier creative said "home **or office**". The
  client's landing page only says "in-clinic & in-home". Verify every offer detail against the
  client's own materials before it goes into a script.
- **What the video skips for healthcare:** its example actor praises a product she "owns." For a
  clinic, an AI actor claiming results or patient status is a fake testimonial. Actors voice the
  situation and the offer's facts, and real reviews go on screen.
- **Actor label: Dylan's call, and he chose none.** The first cut carried an "AI-generated actor
  portrayal" tag. Dylan had it removed from the CrosaCore ad after being told the FTC endorsement
  guides expect a note when an ad implies someone is a real customer. Default to no label for his
  clients unless he asks for one. What stays non-negotiable is the script: no results or patient
  claims from an actor.
- **Lighting: try it, but show Dylan both.** He first said the soft, evenly lit actor looked "a
  little unnatural." A darker, uneven relight (Nano Banana Pro `--ref` edit + matching Veo prompt)
  was made, and after watching both he **preferred the original**. Don't assume "grittier = more
  real". When he flags a look, keep the original files and show the alternative side by side
  before replacing anything.
- **Disclaimer labels: none.** He also had the 3PM Desk ad's "Dramatization" tag removed.

---

## Working Checklist (apply to every generated ad)

- [ ] Is there ONE clear avatar this specific ad is for — visually and verbally unmistakable?
- [ ] Does the creative state or embody the avatar's problem in the first beat (headline/hook or
      opening visual)?
- [ ] Is the mechanism (why the offer solves it) clear, even briefly?
- [ ] Is there a specific, single CTA?
- [ ] Could this be the first of 10 iterations on the same avatar/angle rather than a one-off?
- [ ] Is this ad actually a NEW CONCEPT (different format and/or different archetype/angle) rather
      than just another iteration of an existing concept? Default to proposing new concepts —
      iterations only come after a concept has already proven itself (see the ratio-flip principle
      above).
- [ ] Does the headline/hook alone (no body copy) already make the outcome and avatar clear? (Ogilvy
      80-cents test, per the Value Equation section above)
- [ ] Does the image depict the dream OUTCOME itself, not a generic product/lifestyle stand-in?
- [ ] If proof is included, is it visual (before/after, result screenshot, video-style still) rather
      than a plain text quote?
- [ ] If a real guarantee/risk-reversal exists for this offer, is it stated right after the CTA?
- [ ] Is this ad explicitly TOP-OF-FUNNEL (problem+solution, cold avatar) or BOTTOM-OF-FUNNEL (one
      specific objection, warm avatar) — never an unfocused ad trying to do both jobs at once?
- [ ] If bottom-of-funnel: does it address exactly ONE named objection, without restating the full
      top-of-funnel pitch?
