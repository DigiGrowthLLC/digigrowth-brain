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
3. **A bullet/emoji checklist of specific conditions treated** — ✅ Knee Pain ✅ Shoulder Pain ✅ Back Pain ✅ Neck Pain, etc. — lets the reader self-identify in under a second rather than reading prose. *(Superseded 2026-10-07: keep the list, drop the emojis. See the Hormozi live ad review section below.)*
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

## Source: "Why Feature-Heavy Ads Lose the Buyer" — Alex Hormozi Live Ad Review (2026-10-07)

Hormozi critiquing a member's live ad (a coaching offer: emoji-heavy copy, a "Hey manifestors!"
callout, an offer stack of features, abstract colorful AI images). Almost all of it is copy
guidance, so it lands mainly in `generate-ad` step 2. Skipped: the closing ACQ event promo.

### Ads must look like content, so no emojis in copy

- Marketers adopted emojis around 2014 because they made ads feel native. Now every marketer uses
  them, so "the pendulum has swung back": emojis read as *ad*, and people scroll past ads. A paid ad
  can follow an ad's structure, but its look and feel should pass for an organic post.
- **Default: no emojis in primary text, headlines or on-image text.** This overrides the ✅
  condition checklist in the 2026-09-13 Ad Library scan above. Keep the checklist *structure* (a
  scannable list of conditions), written as plain short lines instead of emoji bullets. Same when
  modeling copy on a proven ad that uses emojis: borrow its structure, drop the emojis.
- No hype punctuation either. "Become a magnet to prosperity!" made him scroll on sight: an
  exclamation-point headline is a tell that it's an ad.

### The callout has to be a label people actually give themselves

- "Hey manifestors" fails because few people self-identify with that word. If the label isn't one
  the avatar would use about themselves, **chunk up or down a level** to one they would ("people who
  believe in X", "desk workers", "runners over 40"). Check every callout and avatar label against
  this: would the avatar say this word about themselves, unprompted?

### Lead with the pain, aiming for an instant "yeah, that's me"

- The first line's job is to make the reader **nod their head**. Write it as an implied yes / "yes
  statement" (from his book *$100M Leads*): a situation they recognize from their own life, usually
  a question. His examples: "You ever keep trying things and nothing seems to stick?" "Do you ever
  look in the mirror and wonder why you're not further than you are right now?"
- A stack of features or an offer list is not a hook. Lead with the pain the avatar is living with
  and what life would be like without it, and get to features later (and only as benefits, below).
- **Healthcare guardrail (ours, not his):** Meta's personal-attributes policy rejects hooks that
  assert the viewer's health condition ("Is your back pain..."). Make the yes-statement about a
  *situation*, not a diagnosis: "Ever leave a PT visit wondering what you actually did for 45
  minutes?" or "Ever skip the gym because your knee might act up?" work; "Do you have knee pain?"
  doesn't.

### Features → benefit → benefit of the benefit, then say it fresh

- Most ads state a feature and call it a benefit. Chain it twice:
  - Feature: a meal plan.
  - Benefit: you never wonder what's for dinner.
  - Benefit of the benefit: you hit your goals because there's no guesswork.
- Then **check the wording for banner blindness.** If you've heard the phrase in marketing before
  ("no guesswork", "root cause", "tailored to you", "get back to doing what you love"), readers
  skim past it. Rewrite until it sounds new: "no guesswork" became **"so the easiest thing to eat is
  also the right thing to eat."** That line produces a gut reaction a stock phrase can't.
- This sharpens the "so that" chain in the Value Equation section above: run the chain, then
  rewrite the last link in words nobody in the vertical is already using.

### Plain-writing rules ("fixes 90% of people's copy")

- Third-grade reading level or lower.
- Simple sentences. Cut most commas: split the sentence instead.
- For a long run of points, use "..." between them and put them on separate lines.
- Tell simple stories, narratives and analogies.

### Analogies from the avatar's world make the ad educational

- An analogy compares the thing they don't know (your offer) to a thing they do. That's what
  teaching is. Pick it from the audience's world: auto-shop owners get a car analogy; moms get a
  kids analogy ("You know how Timmy won't eat what you put in front of him? You're Timmy too...").
  For PT avatars, reach for their world: the desk job, the kid's soccer game, the morning run,
  the car that needs a tune-up before it breaks down.
- "The best way to get someone to believe you'll provide value after they buy is to provide value
  before they buy." A well-formatted ad can teach one useful thing. Educational beats pitchy.

### Testimonials and images

- A block of text testimonials stacked in the copy underperforms. **Reformat testimonials as video
  with punch-ins** (zoom cuts on the key line). Matches the "visual proof beats text proof" point
  in the Hormozi landing-page section above.
- Abstract AI images ("crazy colors") don't sell. **Show the process: your steps of implementation
  and why they work.** For `generate-ad` image prompts: depict the mechanism or a concrete step (the
  assessment, the hands-on session, the home visit), not a mood graphic.

### CTA: personalization

- He's repeated this across reviews: frame the CTA around personalization (what *they* get, built
  for their situation), not a generic "Book now."

---

## Source: "How to make Meta Ad Creatives in 2026" — Jared Robinson, Creative Don (2026-10-08)

A DTC creative-agency founder (8 figures spent on Meta) on the *psychology* of a good ad, not account
structure. He breaks down 4 static ads his team made: a fertility quiz, a looksmaxxing app, golf
putter covers and a "snuff cup." Then he gives his research process and brief template. Mostly
`generate-ad` material (concept planning, copy, image direction) plus one research habit. Skipped:
the agency pitch and the "comment below" ask.

### The 4 core elements: Attention, Curiosity, Emotion, Connection

Every good ad does some mix of these four. Name which ones a concept is built on before writing it.

1. **Attention: you have about 0.5 seconds, not 3.** Watch people scroll: they're gone in under a
   second if the first frame isn't interesting. The *first frame / the image itself* has to stop
   them before any copy is read. This sharpens the 0-3s hook in the video script timing: the 0-3s
   window is for the spoken hook, but frame 1 must already be arresting on mute (a striking face, a
   strange object, a dark mood, a joke you get at a glance).
2. **Curiosity: you don't have to sell the whole thing in the ad.** A long "cold scroller to buyer"
   ad sells everything in the ad. The other option is to spark just enough curiosity to earn the
   click, and let the page after it (quiz, listicle, landing page) do the explaining and selling.
   Those ads do very little selling on purpose.
3. **Emotion: pick the core emotion on purpose.** Fear, insecurity, self-blame, hope, excitement,
   humor, belonging. His examples run from very dark (fertility, looksmaxxing) to pure humor (golf,
   dip cup). Which one is right depends on who the buyer is and where they are emotionally, so
   decide it from the avatar, not from taste.
4. **Connection: the ad has to read as made by someone who knows them.** Use the avatar's own
   insider words and in-jokes. The looksmaxxing ad says "ascend" because that's the niche's word;
   outsiders wouldn't get it and that's the point. This extends the 2026-10-07 "labels people
   give themselves" rule from the callout to the whole ad's vocabulary.

His summary: a good ad speaks directly to the ICP, opens a curiosity gap, triggers an emotional
response and gives a clear path to a solution. The result is the viewer feeling **"this was made
for me."** Generic ads that look like everyone else's never get that.

### Two ad modes, chosen by the product and the avatar

- **Problem/emotion products → lead with Curiosity + Emotion.** The fertility ad: a woman with her
  head in her hands, two handwritten inner-monologue notes ("What's wrong with me?" / "Maybe
  nothing."), the headline "Stop blaming yourself for not seeing that positive test." and a CTA
  button "Take the Quiz → See What's Stopping You." It names the private self-blame, takes it off
  them, and promises an answer one click away. Very little product in the ad.
- **Low-stakes / identity products → lead with Attention + Connection, often humor.** "The foursome
  experience you dream about" (putter covers, sold to Gen Z/millennial golfers who drink beers with
  the boys, not the old guard) and "Made for spitters, not quitters." They sell belonging ("makes
  me one of the boys") and they get *shared*, which is free reach.
- Each ad is built for one avatar so precisely that the other avatars would scroll past it in two
  seconds. That's correct: matches "content is targeting" from the Andromeda sections above.
- **Nobody cares about specs** (ingredients, fabric weight). Corroborates feature → benefit →
  benefit of the benefit.

### Research: days of manual reading before any ad

- Spend 3-4 days reading the avatar's own words: Reddit threads, competitors' reviews, Amazon
  reviews, TikTok comments, comments on competitor ads. Copy and paste verbatim quotes and take
  screenshots into a raw **research document**. Don't summarize it into a prompt.
- His point about AI: a "deep research" prompt gives you the average. It won't write "made for
  spitters, not quitters." The funny, insider, painfully specific lines come from reading real
  people talk. **For us:** the `deep-research` skill does the collecting with AI (Dylan's call,
  2026-10-08), but its output is a file of *verbatim* customer phrases with sources
  (`clients/<slug>/customer-language.md`), not a summary, and Dylan reviews it at three gates.
  Hooks and callouts are lifted or adapted from those phrases, and each ad cites which phrase it
  came from.
- PT sources to mine: Google reviews of competing clinics (both the 5-star and the 1-2 star ones),
  Reddit (r/physicaltherapy, r/running, r/backpain, r/Pickleball, local city subs), Facebook group
  comments, comments under competitor PT ads in the Ad Library.

### The brief template: six fields per concept

Write this for every concept before making anything:

1. **Concept**
2. **Creative type**: curiosity static, us vs. them, USP callout, social proof / review, meme /
   humor, etc. Always log it. Without it you end up making 100 copies of the same ad, and Meta
   needs creative diversity (corroborates the new-concept vs. iteration rules above).
3. **Angle**: what you're saying and who it's for.
4. **Headline**
5. **CTA**
6. **Visual direction**

### Offer still matters

He bought Skims purely because the offer was too good to refuse. Great creative carries a strong
offer. It doesn't replace one.

### Applicability notes (DigiGrowth / PT)

- **Curiosity mode needs a page that sells.** It only works when the click goes to a landing page
  or quiz that explains and sells. Client ads that go to a **Meta Instant Form** (e.g. Crosacore via
  Make) have no page after the click, so the ad itself must carry the problem, mechanism and
  offer. Pure-curiosity ads there just bring in low-intent form fills. Use curiosity mode for
  campaigns that send traffic to a client landing page.
- **The "stop blaming yourself" pattern fits PT well, kept to situations.** Meta's
  personal-attributes policy still applies: blame-relief about a *situation* passes ("Stop blaming
  yourself for skipping the morning run"; "Stop blaming your age. Most people were just never
  shown the right plan."), but asserting the viewer's condition doesn't ("Stop blaming yourself
  for your back pain"). Handwritten inner-monologue notes on the image are a strong visual for the
  dark/emotional mode.
- **Humor/identity mode suits active avatars** (runners, golfers, pickleball players, weekend
  lifters): an in-joke from their world beats a clinical headline. Keep it kind. Never joke about
  the pain itself.
- **Client funnels push the free consult, never prices** (see the client-funnel rule). A curiosity
  CTA like "See what's actually stopping your runs" pointing to the free consult is the
  PT version of "Take the quiz → see what's stopping you."
- No emojis still applies. None of his four ads use them.

---

## Source: "How to Win with Facebook Ad Creatives in 2027" — AdsMastery (2026-10-08)

An e-com agency owner ($600M+ in ad spend) on account-level creative *mix*: what has to be in the ad
set for Andromeda to scale it. This is strategy, not copywriting, so it lands mainly in
`build-campaign-plan` section 7 (the 10 concepts) and section 8 (measurement). **Dylan's call:
real-creator UGC is out** (his "creator army": samples, TikTok GMV Max, creator communities, invite
tools). Everywhere the video says UGC, we use our tested **AI UGC** pipeline instead (Veo talking
actors, `generate-ad`'s "AI UGC Video Ads" loop). Also skipped: the tool promos and the next-video
plug.

### The 33% rule, our version: three pillars

His slide labels each pillar with a job. Our version:

| Pillar | His job label | What it is for us | Strength | Weakness |
|---|---|---|---|---|
| AI statics / AI scene video | Discovery: find winners | fal.ai images, Kling scenes | Fast, a few dollars, fills any missing format | Less trust, can drift off the formula |
| AI UGC (replaces his creator army) | Scale: mass volume | Veo 3.1 talking actors | A "real person talking" at volume. Vary actor age, gender and setting to reach different avatars | Not authentic proof. Never a patient (existing rule) |
| In-house | Control | The practitioner's founder story, team, the clinic behind the scenes | The most trust, full control of the message, hardest for competitors to copy | Slowest (about 30 min to hours per ad), depends on the client's footage |

- Keep roughly **a third from each pillar.** The trust gap in the two AI pillars is closed by real
  reviews as proof cards and by the in-house pillar.
- **Founder stories work.** He disagrees with "build the product brand, not the founder": a real
  "why I started this" and the setbacks along the way make people relate and want to support a
  small business. For PT, that's the practitioner's own story. Note this is *not* the same as a
  re-cut of the practitioner's educational footage, which Dylan rejected (2026-09-29).

### Cover the whole awareness ladder, in one ad set

- Also roughly **a third each of top, middle and bottom of funnel**, all inside **one ad set**.
  Andromeda decides who sees which ad at which stage. Don't split stages into separate audiences.
  This corroborates the house format (1 campaign, 1 ad set, 10 ads).
- His formats by stage, with our PT translation:

| Stage | His formats | PT version |
|---|---|---|
| Unaware | Educational stat, founder story, "did you know" | A surprising fact about a *situation* ("Most runners who stop for a sore knee never had a knee problem"), never asserting the viewer's condition. Founder story |
| Problem-aware | Before/after, benefit callouts | A functional before/after told through a real patient's review (couldn't do X, now does X). No body before/after images (Meta restricts those in health) |
| Solution-aware | 3 reasons why, us vs. them, reviews, testimonials | PT vs. rest / chiro / injections / YouTube stretches; 3 reasons one-on-one PT works; real Google review cards; AI UGC actor voicing the situation |
| Product-aware | Limited-time offer, offer, testimonials | Free-consult reminder with reviews. Never a price (client-funnel rule) |
| Most-aware | One direct CTA ad | "Book your free consult," plain and direct |

- **Conflict with "The Only 2 Ad Creative Formats" (2026-09-13), which said skip the middle of the
  funnel:** this newer rule wins *for the mix*. The 10 ads span the ladder, middle included. That
  source's real point still holds *per ad*: each ad does exactly one stage's job, never a vague
  blend.

### The 2027 strategy: unique formats per angle, not variants of one winner

- **The old way (his "2026 strategy"):** find the winning format, then make variants of it (same
  walk-and-talk, new person; same static, new background). All the spend piles into 1-4 ads, and
  when that format fatigues, the account tanks and you start hunting for a new winner again.
- **The new way:** for each avatar, pick 3 angles. Each angle gets the **full format set: Review,
  Benefit, Founder, Educate, Problem, Offer**. Every ad is unique, and no two share both angle and
  format. Run 10-15 of these.
- **The health signal is spend spread across many ads**, not concentrated in the top 3-4. If spend is
  stuck in a few ads, add new *formats*, not more variants.
- **Don't switch off "weaker" ads that are still getting spend.** They have a role at their stage
  of the ladder, and that's what keeps return on ad spend steady as spend rises.
- **Conflict with the "minimum spend before judging" rule** in the $30/day source above: judge the
  *ad set* by cost per booked consult and by how spend is spread. Don't kill an ad only because its
  own cost per lead is worse while it's still getting spend. Still kill ads for policy problems, and
  ads with zero results after the minimum-spend threshold. His advice comes from accounts spending
  thousands a day, and our clients run about $25/day, so with 10 ads the threshold takes a while to
  reach. Be patient, not trigger-happy.
- Corroborates the ratio flip (new concepts over iterations) from the Post-Andromeda Q&A.

### The angle flywheel

- When an angle wins in one pillar, rebuild it in the other two. His example: a creator's
  ingredient-label comparison took an account from 1.7x to 4x return on ad spend once the founder
  re-made it as AI and in-house ads. The founder had never thought of that angle himself.
- For us: a winning AI UGC script becomes a static and a founder-story take, and the reverse.
- His **wide vs. specific briefs** map onto our AI UGC scripts: *wide* = fresh angles from
  `deep-research`; *specific* = modeled on our current best ad (the existing "same actor,
  different scripts" double-down).

### Personification: open new avatars by sub-problem when spend plateaus

- One general avatar ("people who can't sleep") eventually maxes out. Split it by *sub-problem*:
  can't fall asleep / falls asleep but wakes up groggy / keeps waking up at night. These are
  different people, and each gets its own full pillar × ladder set.
- Or split by identity: athlete, mom who works out 3 days a week, office worker, frequent traveler.
- For PT, these come from the `deep-research` segments: runner knee, desk-worker neck, weekend
  warrior, parent lifting kids, golfer, post-surgery. Corroborates "go niche" from the Hormozi /
  Andromeda section. At $25/day, launch one avatar first, and open the next when results plateau.

---

## Source: "How to Make Meta Video Ads in 2026" — Creative Don (2026-10-08)

Jared Robinson again (same agency as the 2026 static-ads source above), this time on the **video
script structure** behind their best DTC video ads (high six figures in purchase value from single
ads). Lands in `generate-ad`'s video sections. His examples are apparel (gym leggings and tanks, a
premium hat). Skipped: the creative-audit pitch and the comment bait. His "don't let influencers
freeball it" applies to us as: **AI UGC scripts are always written from proven messaging**
(real-creator UGC is out, per Dylan).

### Three parts, three jobs

1. **Hook (about the first 5 seconds): stop the scroll. That's all.** It's not there to sell or to
   get the click. Three ingredients:
   - **A visual hook in frame 1.** If nothing interesting is happening on screen the instant they
     scroll onto it, the copy doesn't matter. On screen in his example: a big bold caption of the
     key phrase ("BUTT ENHANCING TECH") over the product in action.
   - **Curiosity copy.** "The girls got the leggings with the butt-enhancing tech... Worker made
     tanks for the boys with chest-enhancing tech." The viewer wonders what that even means.
   - **It qualifies the ICP in about a second**, using words only the niche gets (gym people know
     the leggings). Everyone else scrolls on, which is fine. Corroborates Connection / insider words
     (2026 static source) and "content is targeting" (Andromeda).
2. **Body: sell, using messaging you already know works.**
   - Lead with a **value proposition / unique mechanism**: the product as *the* solution, or the
     next new thing. "This is not your cheap store-bought tank top. The cheap ones stretch out
     fast." Then the selling points people actually responded to ("holds its shape all day"), the
     use cases, and **identity** ("built for bodybuilders, powerlifters and hard work").
   - Never write a script on unvalidated messaging. He finds the messages with cheap, structured
     **static tests first**, then scripts videos from what won.
3. **CTA: overcome objections and doubt, not "check it out."** Many ads have good hook and hold
   rates and still don't sell, because they end on "check it out" or "selling out fast." Once
   someone has watched 30 seconds they're interested. The ending's job is to push them over the
   line with:
   - **Objection handling** ("there's a reason it's priced like this, it's not for people who want
     to cheap out")
   - **Risk reversal** (free returns, a 30-day money-back guarantee)
   - **Social proof volume** ("20,000 people already trust us... 45,000 sold in under two years"),
     shown as a fast scroll through a wall of review cards with the speaker in a corner bubble
   - **An offer**, plus urgency or scarcity.
   In his example, the last ~20 seconds of a ~50-second ad are all CTA and objection handling.

### His go-to full structure (6 beats)

Works as a talking actor, a VSL or a founder-led VSL. He says it "absolutely prints."

1. **Hook**: call out the ICP and the angle (plus the visual hook and curiosity above)
2. **Storytelling**: what's the problem? Relate to the ICP.
3. **UMP → UMS**: the unique-mechanism problem ("why the usual options fail") turning into the
   unique-mechanism solution: **why we work when others don't**
4. **Risk reversal**: guarantee, warranty
5. **Testimonials**: results, or sheer volume of 5-star reviews
6. **CTA**: offer, urgency, scarcity

Beats 2-3 are where the selling happens. Beats 4-6 push them over the line.

### How this fits our rules

- **Script length.** Our AI UGC loop makes ~15-20s ads with a 5s end card. That stays as the
  short format. His 6 beats become a **separate long-form concept type, the "full-structure
  video" (~40-60s)**: 5-7 Veo takes of 8 seconds or less (hook, story, UMP, UMS), then a proof
  section (review cards) and an offer card. Or use the practitioner's own footage as a founder-led
  version. Put one full-structure concept among a campaign's 10. It's a different format, which
  is what the 2027 strategy wants anyway.
- **Static tests first vs. our house format** (at least 7 of 10 ads are video, Dylan 2026-10-06):
  **the house format stays.** For a first launch, "proven messaging" means the `deep-research`
  quote bank plus the proven competitor ads (both already validated outside our account). After
  the first read, new video scripts go on the angles that won in *any* format (the flywheel). A
  statics-first test launch is an option to offer Dylan for a new client, not the default.
- **The CTA under our client-funnel rules:**
  - **No price, ever**, so his "price objection" becomes the PT objections from `deep-research`:
    cost/insurance worries, time off work, "PT didn't work for me before", "do I need a
    referral?" Answer only with facts from the client's `client-context.md` (e.g. Texas direct
    access) and never a price.
  - **Risk reversal = the free consult itself**: "free, no obligation, you'll leave with a plan
    either way." Mention a guarantee only if the client really offers one.
  - **Urgency or scarcity only if it's real** and the client's voice rules allow it. A no-pressure
    brand doesn't get "only 3 spots left."
  - **Social proof** = review count + real review cards, first names only. Our proof card already
    does this. The scrolling review wall with the speaker in a corner bubble is a richer version.
- **Corroborates:** the 0.5s attention rule, insider words, Hormozi's risk reversal right after the
  CTA, visual proof over text proof, and the existing 0-3s hook timing.

### PT translation of UMP → UMS

- **UMP examples**, only where true for that client's competitors: "Most clinics give you 15
  minutes with the PT, then an aide hands you a sheet of exercises." "Rest and YouTube stretches
  calm it down, then it comes back the first time you run."
- **UMS** = the client's *real* differentiator (Crosacore: a full one-on-one hour with Brandon,
  in-clinic or at home). Never invent one.
- **Identity** works for PT too: "built for people who refuse to stop running."

---

## Source: "How I Make AI Static Ads in minutes" — static ads masterclass (2026-10-08)

A paid-social strategist (10 years, tens of thousands of statics for Laura Geller, Nuts.com and
others; her top static did $1.8M in spend at 2.15 ROAS). Part 1 is a static-ad masterclass. Part 2
is a **sponsored** demo of Superscale, an AI ad agent. We take its *workflow*, not the tool: every
step maps onto what we already have (see the table at the end). Lands in `generate-ad` steps 2-3,
the concept library and `build-campaign-plan` step 2. Skipped: the sponsor pitch.

### Myths

- **"Statics are only for retargeting."** False. With the right persona and awareness-level
  messaging, statics scale to cold audiences.
- **"Only video works for us."** A skill issue: people think about statics as a *format*, not as
  messaging that "waves a flag" at a cold persona.
- **"Statics are just for testing messages cheaply before video."** That misses what a great static
  can do on its own. **Resolution with the Creative Don video section:** both are true. Statics are a
  cheap message test *and* real performers, so the ~3 statics in the house format get designed as
  full ads, never as throwaways.

### Layer 1: strategy, decided before any copy

1. **One goal.** Offer, education, or reaching the problem-aware. Never two jobs in one static.
   Corroborates the one-job-per-ad rule.
2. **One specific persona**: not "small business owners" but which one, at what stage, with which
   objection. That decides the vocabulary, the proof needed and the objections to answer.
3. **The format.** It decides which copy survives and what the image must carry.
4. **The awareness level.** It's the bridge between persona and goal and the copy framework.
   Corroborates the AdsMastery ladder.

### Layer 2: design

- **Hierarchy:** headline first (it does the targeting), then the product or key visual, then
  supporting elements. The focal point is usually the headline, and sometimes the image.
- **The one-second comprehension test.** Clarity beats creativity. If a stranger can't tell what's
  being sold or said at a glance, kill it. Her "scrap it" example: a bottle surrounded by six
  "NO MORE" callouts with little illustrations. No focal point, too much going on. **AI statics
  drift into exactly this**, so check every generated static against it.

### Layer 3: copy tactics (every winning static uses at least one)

1. **Specific numbers** for time, effort or cost ("5 minutes", "under $5", "one use"). Her top
   static: "The 5 Minute Makeup Routine."
2. **Call out the audience by name.** Self-selection is a targeting mechanic. Corroborates the
   callout rule.
3. **Taboo:** say what competitors are too polite to say.
4. **Primal desire as the headline:** status, belonging, safety, approval. The product is just the
   mechanism. The desire is the headline.
5. **A curiosity loop:** show the setup, hide the payoff behind the click. If it wins, make sure
   the landing page pays it off. Corroborates curiosity mode from the 2026 static source.
6. **Negative marketing:** name what they're afraid of.
7. **Golden-nugget testimonials.** Her most repeated winner. Export all reviews (CSV) and have an
   LLM pull the lines that would work best as ads. Better than writing copy.
8. **Show the transformation, don't describe it.** Before/after is legal, just restricted for
   cosmetic and weight-loss products.

### Production levels and seven formats

- **Three production levels:** graphic, hi-fi production, and **lo-fi creator content** (statics
  that look like a phone photo). Brands forget the lo-fi kind, and it's "really moving the needle"
  right now.
- **Formats to always test** (taking a winning message into several formats is easy creative
  diversity):
  1. **Educational infographic.** Top of funnel; feels organic because it teaches. Example:
     "Instant brighter teeth in 3 easy steps" with numbered steps.
  2. **Headliner.** One big headline front and center (Ogilvy-era). The home of taboo lines.
  3. **Benefit callouts.** The product in the middle with benefits around it. Test a primal-desire
     headline or a golden-nugget testimonial on top. Keep it to a few callouts (see the hierarchy
     rule).
  4. **Comparison / us vs. them.**
  5. **Transformation.** The **biggest gap** in most accounts and the biggest opportunity for
     problem- and solution-aware people, who are "just looking for proof."
  6. **Grid.** Several items in a grid. Her $8.4M top static was a grid ("The 5 Minute Makeup
     Routine": four products with prices). Best for multi-product brands.
  7. **Text-only.** Founder letters, notes-app posts. Example: "iPhone Cases Are Weird.", a
     short-line letter ending in press proof.

### Her AI workflow, mapped onto our stack (no new tool needed)

| Her step (Superscale) | Our equivalent |
|---|---|
| Pull brand fonts, colors and products from the URL | Client portal + `design-agent` site scrape |
| A "brand brain" doc from Claude | `client-context.md` + `deep-research.md` |
| Research own and competitor ads | `research-competitors` + the Meta connector |
| **Creative gap analysis**: which formats, personas and awareness levels the account is missing | **New:** creative gap table in `build-campaign-plan` step 2 |
| Generate ~3 variations per concept to start | `generate-ad` step 3 (fal.ai Nano Banana Pro) |
| Edit by chat: fix typos, colors, sizes | Nano Banana `--ref` edits, at the visual gate |
| "5 variations of this ad for 3 personas" (works on competitor ads too) | `generate-ad` input 5 (recreate a proven ad) |

Her critiques of the AI output **corroborate our rules**: she deletes em dashes, fixes AI
spelling errors, dislikes quote-heavy review collages (matches Hormozi's "stacked text testimonials
underperform"), and flags that AI statics often have "too much going on."

### PT translation

- **The seven formats for PT:**
  1. Infographic: "3 reasons your knee aches after long runs" or "What happens in your first
     visit (step by step)."
  2. Headliner: a taboo line such as "Most clinics book you for an hour. You see the PT for 15
     minutes." Only where that's true of local competitors, and never naming one.
  3. Benefit callouts: around a real session photo. Three callouts at most.
  4. Comparison: one-on-one PT vs. rest, chiro, injections or a 15-minute clinic.
  5. Transformation: a functional before/after told through a real review ("couldn't lift my
     daughter" → "carried her up the stairs"). Never body before/after images.
  6. Grid: "what we help with" or the team. Lowest priority for PT.
  7. Text-only: a founder letter from the PT ("Why I left the big clinic to open my own").
- **Lo-fi:** a phone-photo look of a real session or the clinic. Pairs with the in-house pillar.
- **Tactics in PT terms:**
  - Numbers describe the *service* ("60 minutes, one-on-one", "in-home"), never outcome promises.
  - Primal desires: independence, keeping up with the kids, safety, not being "the injured one."
  - Negative marketing names the fear (surgery, being told to stop running) without asserting the
    viewer's condition.
  - **Golden nuggets:** run the client's Google reviews through the LLM, first names only.

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
- [ ] Does this ad do ONE funnel job, never an unfocused ad trying to do several at once? (Since
      2026-10-08 the middle funnel is in scope too. See the awareness-stage item below.)
- [ ] If it's an objection ad (product/most aware): does it address exactly ONE named objection,
      without restating the full top-of-funnel pitch?
- [ ] Does the first line get an instant "yeah, that's me" (a pain/situation yes-statement), rather
      than an offer, a feature list or an exclamation-point promise?
- [ ] Is every callout label one the avatar would use about themselves?
- [ ] Zero emojis and no hype punctuation; does it read like an organic post?
- [ ] Is every feature taken to its benefit of the benefit, in wording that isn't a stock
      marketing phrase?
- [ ] Third-grade reading level, short sentences, few commas, line breaks?
- [ ] If there's an analogy or teaching point, is it drawn from the avatar's own world?
- [ ] Does the CTA speak to personalization rather than a generic "book now"?
- [ ] Does frame 1 / the image alone stop the scroll in half a second, on mute, before any copy is
      read?
- [ ] Is the concept's lead element named (Attention / Curiosity / Emotion / Connection) and its
      core emotion chosen on purpose for this avatar?
- [ ] If it's a curiosity-led ad that sells very little, does the click go to a page that does the
      selling (not a bare Instant Form)?
- [ ] Does the copy use at least one insider word or phrase the avatar actually uses, ideally
      lifted from real customer language (reviews, Reddit, comments)?
- [ ] Is the brief complete (concept, creative type, angle, headline, CTA, visual direction), and
      is the creative type different from the other concepts in the batch?
- [ ] Is each ad tagged with exactly one awareness stage (unaware / problem / solution / product /
      most aware) and doing only that stage's job?
- [ ] Does the set of concepts span the whole ladder, middle funnel included?
- [ ] Does the set mix the three pillars (AI static/scene, AI UGC, in-house) roughly in thirds,
      where the client's footage allows?
- [ ] Are any two concepts just variants of the same format (same format, cosmetic change)? If so,
      replace one with a different format.
- [ ] Video: is there a visual hook in frame 1 (something happening, plus a bold keyword caption),
      and does the hook qualify the ICP in about a second?
- [ ] Video: does the body name the unique-mechanism problem and the solution (why this works when
      the usual options don't), using only the client's real differentiators?
- [ ] Video: does the ending handle at least one real objection, plus risk reversal (the free
      consult) and social proof, rather than a bare "book now"?
- [ ] Video: is the script built on proven messaging? Cite the research quote, proven ad or
      winning angle it came from.
- [ ] Static: does it pass the one-second comprehension test, with one clear focal point (usually
      the headline) and not too much going on?
- [ ] Static: does it use at least one copy tactic (specific number, audience callout, taboo,
      primal desire, curiosity loop, named fear, golden-nugget review, shown transformation)?
- [ ] Static: is its format named (infographic, headliner, callouts, comparison, transformation,
      grid, text-only) and its production level (graphic, hi-fi, lo-fi), and do the statics in a
      batch use different formats?
