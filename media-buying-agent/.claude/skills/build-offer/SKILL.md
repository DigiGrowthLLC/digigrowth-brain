# Build Offer Skill

Design the patient-facing offer a client's ads sell: the thing a stranger books to get an
evaluation on the calendar. Built from three inputs: who the target audience is and what stops
them (from `deep-research`), offers already proven in this market (from `research-competitors`
and `context/pt-ad-concept-library.md`), and marketing psychology. Dylan picks and shapes it at
three gates. The client approves it before any ad sells it.

The offer is usually the biggest lever in a campaign. A strong offer in front of a weak ad beats a
weak offer in front of a great ad. So this step comes *before* concepts and copy, and every ad
afterwards sells the approved offer.

**Not to be confused with `context/offer.md`.** That file is DigiGrowth's offer *to clinics*
(pay per booking, the 6-week guarantee). This skill designs the *clinic's* offer *to patients*.

---

## Trigger

"Build an offer", "what offer should <client> run", "improve the offer", or step 5 of
`build-campaign-plan`. Standalone or inside a campaign build.

---

## How this skill runs: three gates

Same as the other campaign skills: at each **GATE**, show a short summary in chat, ask with
`AskUserQuestion` (**Approve** / **Edit** / **Redo**), and **stop until Dylan answers**. Inside a
campaign build, these three gates together are **GATE G5**. Record each decision in the
campaign's `progress.md` (or `outputs/offer-<slug>-<date>/progress.md` when run standalone).

| Gate | Dylan reviews |
|---|---|
| O1 | Offer audit + audience: the current offer, the client's constraints, what the audience needs from an offer |
| O2 | 3 offer candidates, scored, each modeled on a proven offer |
| O3 | The final offer one-pager, ready for Dylan to take to the client |

---

## Inputs

Read before anything else:
- `clients/<slug>/client-context.md` (rules, segments, lead capture: Instant Form vs. landing page)
- `clients/<slug>/deep-research.md` + `customer-language.md` (pains, objections, what they've
  tried, dream outcome, price sensitivity). If missing, run `deep-research` first, or ask Dylan
  whether to proceed on lighter evidence.
- `context/proven-ads/<vertical>.md`: the `Offer:` line of every proven ad.
- `context/pt-ad-concept-library.md`, offer concepts #1-3, plus excluded patterns.
- Dashboard: `onboarding.offer_economics.answers` (prices, plan of care value, eval→plan
  conversion), `onboarding.ideal_patient.answers`, and the client's site (current offer, listed
  prices).

---

## Steps

### 1. Offer audit and audience → GATE O1

**The client's side** (ask Dylan for what's missing; mark guesses as *assumed*):
- **Current offer** and where it's stated (site, funnel, Response AI context).
- **Economics:** eval price (if any), plan-of-care value, eval→plan conversion rate. That gives
  the most a booked eval is worth, and so what the offer can afford to give away.
- **Capacity:** how many new evals per week they can take. Real scarcity comes from this number,
  never from invention.
- **What they're willing to do:** free visit vs. phone/video consult, workshops, a take-home plan,
  a guarantee, a discount, a bonus visit.
- **Lead capture constraint:** a Meta **Instant Form can't take payment**. A paid eval needs a
  landing page with checkout or a paid booking link, or the payment is taken at booking by the
  front desk.

**The audience's side** (from deep-research, with quotes):
- The **dream outcome** in their words, and the **trigger** that makes them act now.
- The **top 3 objections and fears** that stop them booking (cost, "PT didn't work before",
  time off work, fear of needles or surgery, "is this legit?").
- **Price sensitivity and trust level.** Cash-pay skeptics need more risk reversal. A "tried
  everything" avatar needs a different *mechanism*, not just a discount.
- **Awareness level** of most of the audience (from the ladder in `ad-creative-principles.md`).
  Cold, unaware audiences need a lower-commitment offer than solution-aware ones.

**GATE O1:** show both sides in one short table each. Dylan corrects the economics and constraints.

### 2. Map the proven offers

List every offer from the proven ads, the concept library and a quick WebSearch for the vertical.
For each one: the offer type, how long it has run (longevity = proof), and who it's aimed at. PT
offer types seen so far:
- Free consult (phone or video)
- Free discovery visit (in person, short)
- Named diagnostic for one body part ("Complete Shoulder Diagnostic", "Run Strong Analysis"),
  free or low-cost
- Free condition workshop or class
- Low-cost first visit ($29-$99) or a paid eval with a money-back guarantee
- Intro packages, first visit + follow-up

Note which types are **long-running** in this vertical, and which are crowded locally (if every
clinic nearby runs "free consult", a named diagnostic stands out).

### 3. Build 3 offer candidates → GATE O2

Build **three genuinely different** candidates (e.g. one free, one named-diagnostic, one
low-cost-with-guarantee). Each one is **modeled on a proven offer** (cite the P# or library #) and
built with these tools:

**a. The Value Equation (Hormozi), lever by lever:**
value = (dream outcome × perceived likelihood of achieving it) ÷ (time delay × effort and
sacrifice).
- *Dream outcome:* name the outcome they want, in their words (sleeping through the night,
  lifting the kids), not "an evaluation."
- *Perceived likelihood:* proof (real reviews, "3 sessions" patterns), the practitioner's
  credentials and own story, a named method.
- *Time delay:* how fast they get something: seen this week, leave the first visit with a plan.
- *Effort and sacrifice:* a short visit, near work, a video consult, no referral needed, no
  insurance paperwork.

**b. Grand-slam structure:**
- **A name** that says who it's for, what they get and how fast (e.g. "The 60-Minute Back Pain
  Breakdown", "Free Desk Neck Check"). It tells the avatar it's for them.
- **What's included, as a stack:** each item answers one objection or obstacle (the full
  assessment, a written plan to take home, a hands-on first treatment, a home routine).
- **Risk reversal:** guarantee the *experience*, never a health outcome. E.g. "If you don't leave
  with a clear plan, the visit is free" or "full refund, no questions." Never "pain-free or your
  money back."
- **Real urgency or scarcity:** the actual weekly capacity ("4 new-patient spots a week"), never
  invented. Skip it for no-pressure brands.
- **Bonuses** that cost the clinic little and raise perceived value (a home exercise video, a
  posture setup guide, a second check-in).

**c. Psychology checks** (name the ones each candidate uses):
- *Zero-price effect:* "free" gets far more leads, but lower intent and lower show rates.
- *Commitment / skin in the game:* a small price ($29-$99) or a deposit filters for intent and
  raises show rates. Fewer leads, better ones.
- *Anchoring:* show the eval's normal value next to the offer's price, only with a real number.
- *Loss aversion:* frame what they keep losing by waiting (runs, sleep, work) and what the visit
  protects.
- *Reciprocity:* give something useful up front (a written plan, a take-home routine).
- *Specificity:* specific names, times and contents read as more credible than vague ones.
- *Social proof and authority:* review volume, DPT credentials, the founder's own story.

**d. Fit and feasibility:**
- Does it work with the lead capture (an Instant Form can't take payment)?
- Can the client deliver it at their capacity?
- Does it survive the client's voice rules?
- Is it Meta-compliant (no health outcome promises, no condition assertions)?

**Score each candidate** (1-5) on: value equation, fit to the audience's top objections, proof
from the market (longevity), lead quality vs. volume, ease of delivery. Present the scores with
the reasoning. Recommend one, and say what it gives up.

**GATE O2:** Dylan picks one (or a mix), edits it, or asks for new candidates. With a small budget
(about $25/day), run **one offer** first. Offer split-tests come later, once the ads are proven.

### 4. Final offer one-pager → GATE O3

Write `outputs/offer-<slug>-<date>/offer.md` (or inside the campaign folder):
- **Name**, who it's for, what's included, price (or free), risk reversal, urgency/scarcity (and
  the real capacity behind it), bonuses
- **The one-line pitch** for ads, and the CTA wording
- **Objections it answers**, each with the quote from deep-research
- **What has to change to deliver it:** booking link or event, payment collection, Response AI
  context, landing page or Instant Form copy, front-desk script, confirmation and reminder texts
- **What to measure:** booked evals, show rate, eval→plan conversion, cost per booked eval

**GATE O3:** Dylan approves the one-pager. Then **he takes it to the client**. The offer isn't
final until the client agrees. Ask Dylan to confirm the client's yes (or note "pending client
approval" and continue the campaign with that flag).

### 5. Save it

Once approved by Dylan and the client:
- Add an **"## Offer (approved <date>)"** section to `clients/<slug>/client-context.md`: the
  final one-pager in short form. **It overrides the free-consult default for this client**: ads,
  Response AI and funnels sell this offer (prices included, if the offer has one).
- List the changes needed outside this agent (Response AI context, funnel, booking link, payment)
  as next steps for Dylan. Don't edit the dashboard or live funnels from this skill.
- Delete the working `outputs/offer-<slug>-<date>/` folder (finalized-only convention).
- If something about offers generalizes across PT clients, add it to
  `context/pt-ad-concept-library.md` under the offer concepts.

---

## Guardrails

- **Guarantee the experience, never a health outcome.** No "pain-free or your money back", no
  "fixed in 3 visits." Outcome stories come only from real reviews.
- **No invented scarcity or fake discounts.** Scarcity comes from real capacity, and an anchor
  price is the real normal price.
- **Default when nothing is approved:** the free consult (the 2026-10-07 client-funnel rule). An
  approved offer in `client-context.md` replaces it for that client only.
- **The client has the final say on their offer.** Dylan approves the design, the client approves
  the business terms.
