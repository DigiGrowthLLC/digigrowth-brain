# CRO Principles for Client Ad Funnels

Reference knowledge for design-agent's `funnel-building` skill — a CRO-optimized
landing page built for one of DigiGrowth's actual CLIENTS to run Meta ads traffic
into, driving a single conversion: booking a consultation. This is a different job
from `landing-page-lead-magnet`'s cold-outreach mockup (see
`funnel-best-practices.md` for that one) — there's no prospect to impersonate, no
DigiGrowth pitch riding along underneath, and no "curiosity gap that stays
incomplete." A paid-traffic funnel's only job is to convert the click it already
paid for, as efficiently as possible, into a booked call. Read this before writing
a client funnel page; update it once real client ad-campaign data confirms or
contradicts something here.

## The One Rule Everything Else Serves

**One page, one audience, one offer, one action.** Every element either moves the
visitor toward booking a consultation or it's cut. No nav bar, no footer links to
other pages, no "learn more" side-quests, no social icons pointing away from the
page. A paid-traffic landing page with an exit isn't a landing page — it's a leak.

## Message Match (the highest-leverage lever on this whole page)

The single biggest predictor of a paid-traffic page's conversion rate is how well
the page's headline and hero image match the ad the visitor just clicked — not the
page's overall polish. Someone who clicked "Free consult for your knee pain"
expects the very next thing they see to say exactly that back to them, in the same
words, within the first second. A generic "Welcome to [Practice]" headline breaks
that scent trail and the visitor bounces before reading anything else.

- The hero headline should be able to plug directly into the ad's own headline —
  restate the specific promise the ad made, don't generalize it into a broader
  "we help people get better" statement.
- If DigiGrowth doesn't have the specific ad copy yet when this page is built,
  default to the most common single pain point from the client's own onboarding
  answers (`ideal_patient.best_patient`, `differentiation_voice.why_you`) rather
  than a generic value prop — a specific pain point still reads as "this is for me"
  even without the exact ad text to match.

## Above-the-Fold Gets Most of the Effort

The section visible without scrolling is the only part of the page every single
visitor sees, and a large share of visitors never scroll past it at all. Treat the
headline, subheadline, CTA button, and hero image as the highest-leverage real
estate on the entire page, worth disproportionately more design/copy attention
than everything below it combined. If choices have to be made about where to
spend the most care, spend it here first.

## The Value Equation (the copy framework behind the headline/subheadline)

A useful way to pressure-test hero and offer copy: does it address all four of
these, and does the headline alone (not the paragraph under it) carry as much of
this as possible?

1. **Dream outcome.** State the actual end result the visitor wants, not a
   description of the service. A "we offer [service]" headline answers the wrong
   question — reframe it as "[service], so that [benefit], so that [bigger
   benefit]" and keep chaining until it lands on the thing the visitor actually
   cares about. For a client funnel, the dream outcome comes from
   `ideal_patient.best_patient`/`why_you`, not a generic "get better" phrase.
2. **Perceived likelihood of success.** The two levers that raise this: real
   proof (see the Proof section's visual hierarchy below) and risk reversal (see
   the CTA section below) — a promise alone is the weakest form of this, proof
   and reduced risk both outperform it.
3. **Time delay.** Naming a concrete, honest timeframe in the headline or
   subheadline closes the gap between "I take action" and "I get the result" in
   the visitor's head — e.g. a specific number of sessions or weeks, when the
   client's own onboarding answers support a real number. Never invent a
   timeframe the client didn't give.
4. **Effort and sacrifice.** The subheadline's job is making the path to the
   dream outcome feel easy, not additionally selling the outcome again. If the
   page includes a "how it works"/process explainer, cap it at 3-4 steps — more
   than that measurably reads as more effort, regardless of how simple the real
   process actually is.

The hero image should visually carry the dream outcome or proof of it, not be a
generic stand-in — a photo of the actual thing the visitor wants to experience
(or the real practice/provider, per this skill's real-photo rule) outperforms
an unrelated "lifestyle" stock image every time.

Headlines carry a wildly disproportionate share of a page's total impact, since a
large share of visitors read only headlines and skim past body copy entirely.
Apply this to every headline on the page, not just the hero — a section that says
"What Makes Us Different" or "How It Works" as its own heading wastes the
highest-attention text on the page restating a label; put the actual answer in
the heading itself instead of the generic prompt for it.

## Section Order That Converts (fixed structure, not a suggestion)

1. **Hero — message-matched promise + single CTA, above the fold.** Headline
   restating the ad's promise, one supporting sentence, a real photo (from the
   client's own scrape/assets — never stock), and the primary CTA button visible
   without scrolling. No form here yet — the ask at this stage is "keep going," not
   "convert."
2. **Trust bar, immediately below the fold.** A thin strip of real credibility
   signals — years in practice, patients treated, real review-platform logos/stars
   if the client has them, insurance logos accepted. This is the visitor's very
   next "is this legit" check right after the headline — don't bury it lower.
3. **The problem, named specifically.** One short section that names the exact pain
   point/frustration the target patient has (pull from `ideal_patient.best_patient`
   and `ideal_patient.drop_off_reason` — the drop-off reason especially is a real,
   client-reported objection worth defusing early, not just at the FAQ). Stakes
   framing works here the same way it does in the cold-outreach page (see
   `funnel-best-practices.md`'s loss-aversion note) — what happens if this doesn't
   get addressed, not just what's gained if it does.
4. **The offer / solution.** State the client's real offer plainly — pull
   `offer_economics.specials` if a real intro offer/free-screen exists, otherwise
   frame it as a straightforward free consultation. Never invent a discount,
   price, or "limited time" offer the client didn't actually give you.
5. **Proof.** Real testimonials/reviews if the scrape or
   `differentiation_voice.reviews` produced any (same rule as the cold-outreach
   skill: real names, real wording, never invented) — otherwise a real
   credentials/experience section instead of a fabricated quote. A "why patients
   choose us" section built from `differentiation_voice.why_you` works well here
   too, alongside or in place of testimonials.
   - **Visual proof outperforms text-only proof.** A plain text quote is the
     weakest form this can take — a real photo alongside it is stronger, a real
     before/after or in-session photo stronger still. Use whatever real visual
     material the scrape/client assets actually provide; never fabricate a
     before/after or a result that isn't real.
   - **Show proof up front, never hide it behind a carousel.** A rotating
     carousel gets a small fraction of the engagement a static, always-visible
     row of proof gets — anything hidden behind a click or a swipe effectively
     goes unseen. If there's enough real proof to show, lay it out as a visible
     grid rather than paging through it.
6. **Objection-handling FAQ.** 3-5 questions, written to defuse the actual reasons
   people don't book — lead with whatever `ideal_patient.drop_off_reason` says if
   it's usable, then round out with the universal objections for this vertical:
   cost/insurance, how long it takes, what the first visit is actually like. Short
   answers — this section's job is reassurance, not a full page of copy.
7. **Final CTA.** Restate the offer once more and repeat the exact same button as
   the hero — same label, same destination. Consistency here matters more than
   novel copy; someone who scrolled this far already decided, don't make them
   re-decide with different wording.

A **sticky/persistent CTA** (a slim bar or floating button that stays visible while
scrolling, mobile especially) is a strong addition on top of this structure — it
means the action is always one tap away regardless of scroll position, which
matters more on a page with no nav to scroll back up through.

## The CTA Itself

- **One destination for every button on the page: the client's real Calendly
  link.** Not a "contact us" form, not a phone-only option, not a second
  competing CTA lower down ("or sign up for our newsletter") — one action, asked
  for repeatedly, never diluted by a second choice.
- **Button copy should be direct, not soft** — this is bottom-of-funnel paid
  traffic that already clicked an ad for this specific offer, not a cold
  cross-outreach touch. "Book Your Free Consultation" beats "Learn More" here,
  the reverse of the cold-outreach page's CTA-softness rule (see
  `funnel-best-practices.md`) — different funnel stage, different CTA register.
- If the client's Calendly supports embedding, prefer an inline embedded
  scheduler over an outbound link for the final CTA specifically — one fewer
  click/tab-switch between "decided" and "booked" measurably helps completion.
  A plain link is a fine fallback if embedding isn't practical.
- **Put real risk-reversal right at the point of decision, not buried lower.**
  A short row of real reassurances directly under the CTA button (e.g. "no
  cost," "no obligation," "cash-pay, superbills available") measurably reduces
  hesitation right where it matters most — the moment someone is deciding
  whether to click. Only ever state reassurances that are actually true for
  this specific client; never invent a guarantee, warranty, or policy they
  don't actually offer.

## What NOT To Do On This Page

- **No navigation menu, no footer link list, no social icons.** Anything that
  isn't the CTA is a way to leave without converting.
- **No countdown timer or fake scarcity** ("only 2 spots left!") unless the client
  told DigiGrowth it's real. A fabricated urgency claim is both a trust risk if
  noticed and a legal risk depending on the client's industry — never invent one.
- **No stock photography where a real client photo exists.** A real (if slightly
  imperfect) photo of the actual practice/staff outperforms a polished stock photo
  for trust on a service-business page — this is well past debate in the CRO
  literature and matches the same "real over generic" principle already governing
  `funnel-best-practices.md`.
- **No long-form storytelling before the CTA is visible.** Paid traffic is
  colder-attention than a warm inbound visitor already reading a blog post — get
  to the offer and the button fast, elaborate below the fold, not above it.

## Technical / Speed

- **Every second of added load time measurably costs conversion** — this matters
  even more here than on the cold-outreach mockup, since ad spend is directly
  paying for every visitor who bounces before the page finishes loading. Same
  discipline as the cold-outreach skill: single HTML file, inline CSS, vanilla JS
  only, no frameworks, compress any embedded images before inlining them.
  Reuse the same scroll-reveal + ambient-motion approach and the same mobile
  breakpoint fixes documented in `landing-page-lead-magnet`'s SKILL.md (image
  height/aspect-ratio, mobile min-height reset, 480px heading sizing) — they're
  general single-file-landing-page lessons, not specific to that skill's use case.
- **Mobile-first is non-negotiable for Meta ad traffic specifically** — the large
  majority of Meta/Instagram ad clicks are mobile sessions. Design and test the
  mobile layout as the primary experience, not a shrink-to-fit afterthought.

## Ongoing Optimization Once the Page Is Live

Formal A/B testing needs real volume to mean anything — without enough monthly
visitors, a "winning" variant can't be told apart from random noise. Most of
DigiGrowth's individual client funnels won't reach that volume on their own. Two
practical implications:

- **Don't run a formal split test on a single client's low-traffic funnel** —
  there usually isn't enough volume for the result to be trustworthy. Instead,
  build the page from already-validated principles (this file) rather than
  testing variants of it in isolation.
- **If/when DigiGrowth accumulates enough funnels and real conversion data across
  clients to see a pattern, that's the point to update this file** — a lesson
  that shows up consistently across several client funnels is worth promoting
  into a standing rule here, the same "get smarter from real data" discipline
  this file already commits to.
- **If a single client's traffic ever does get large enough for real testing**,
  the highest-leverage things to test first are the headline and the hero image
  — changes to the above-the-fold section consistently produce the largest
  swings in conversion rate, far more than changes further down the page.

## Update Log

Add a dated entry here whenever a real client ad-campaign result confirms,
contradicts, or refines something above.

### 2026-09-13 (initial version)
Seeded from general CRO/landing-page research and this codebase's existing
`funnel-best-practices.md` — no DigiGrowth client ad-funnel campaign data exists
yet to confirm or refine any of this. Treat everything above as a reasoned
starting point, not a validated result, until real campaign data comes back.

### 2026-09-13 (added: Value Equation framework, proof/CTA specifics, testing discipline)
Added the Value Equation section, the above-the-fold effort note, the visual-proof-
hierarchy and no-carousel guidance, the risk-reversal-under-the-CTA note, and the
Ongoing Optimization section — synthesized from a CRO/landing-page strategy video
(https://www.youtube.com/watch?v=zA0B-VwOPn4, transcript saved to
content-agent/outputs/), cross-checked against this file's existing principles
before adding (all consistent, nothing contradicted). Still general
best-practice knowledge, not yet confirmed by a DigiGrowth client's own campaign
data.
