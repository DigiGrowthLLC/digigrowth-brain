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
