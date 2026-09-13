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
