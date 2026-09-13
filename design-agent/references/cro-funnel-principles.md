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

## Update Log

Add a dated entry here whenever a real client ad-campaign result confirms,
contradicts, or refines something above.

### 2026-09-13 (initial version)
Seeded from general CRO/landing-page research and this codebase's existing
`funnel-best-practices.md` — no DigiGrowth client ad-funnel campaign data exists
yet to confirm or refine any of this. Treat everything above as a reasoned
starting point, not a validated result, until real campaign data comes back.
