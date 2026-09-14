# CrosaCore (Brandon Crosdale) — Meta Campaign Plan (v2)
**Budget:** $500 total / 4 weeks ($125/wk, ~$17.85/day) · **Goal:** 10 booked Pain Confidence Consultations by 2026-10-11
**Location:** Austin, TX · **Landing page:** LIVE at `funnel.crosacore.com` (confirmed 2026-09-13, CTA → real Calendly link, 20 views already recorded)
**Sources:** Client portal uploads (147 files) + full onboarding questionnaire (client_id 1, pulled via API), live Meta Ad Library research, `media-buying-agent/context/ad-creative-principles.md`.

**Changes from v1:** (1) confirmed the funnel is deployed — blocker cleared; (2) pulled Brandon's actual onboarding answers, which carry his written brand-voice rules, real economics, and the exact drop-off objection — none of which were in v1; (3) reworked the ad concepts after Dylan flagged that the raw client video is educational talking-to-camera content, not footage built for an ad (no hook, no CTA, no testimonial) — see Section 3.

---

## 1. Brand voice rules (from Brandon's own onboarding answers — binding, not optional)

Direct quote from his "what to avoid" answer: *"Avoid guarantees or absolute claims such as 'cure chronic pain,' 'fix the root cause,' 'permanent pain relief,' 'pain-free,' or anything implying guaranteed outcomes. Avoid fear-based messaging, attacking other providers, or suggesting imaging, doctors, chiropractors, or previous PT were wrong. I also do not want overly salesy, hype-heavy, bro-science, generic wellness, or AI-sounding language. Keep the tone confident, intelligent, human, evidence-informed, and straightforward. No em dashes."*

This directly overrides part of v1: Concept A's line about other PT only getting people "70% better" reads as knocking prior providers, and any line implying "100% pain-free" as *our* claim (rather than a quoted patient's own words) breaks the no-guarantees rule. Every concept below is rewritten clean against this list — testimonial outcomes are always attributed as a direct quote from the patient, never restated as CrosaCore's own promise.

---

## 2. What his onboarding answers add

- **Ideal patient (his own words):** "5-60 year old busy professional who has dealt with pain for months or years and is frustrated that it keeps coming back... still working and functioning at a high level, but pain has started affecting training, sleep, confidence... often tried PT, chiropractic care, injections, massage, or rest without getting a lasting solution."
- **Real drop-off reason (his own words):** *cost* — "some people hesitate when they realize they will be paying out of pocket," plus not immediately understanding why the approach justifies the investment. This means the free/no-obligation framing of the consult call is the actual objection-handler, not an incidental detail — it should be prominent in every ad, not just the landing page FAQ.
- **Economics:** avg. patient generates ~$2,200 over ~8 visits; a comparable in-person eval is priced at $200/hr. Useful context for Dylan, not for ad copy: even a $50 cost-per-consult is a strong ROI if even a third of booked consults convert to care.
- **Top conditions (his own words):** chronic/persistent musculoskeletal pain, recurring low back pain, neck and shoulder pain, hip and knee pain, difficulty returning to exercise/strength training after pain or injury — used directly in the condition checklists below instead of invented ones.
- **Booking note:** back-office scheduling has moved to PT Everywhere, but the funnel's actual Meta-facing CTA still correctly points to his Calendly link for the free consult — confirmed live, no action needed there.

---

## 3. Why the raw video isn't ad-ready as-is (Dylan's catch)

The 7 client-portal video files are Brandon speaking to camera about pain topics — real, credible, on-brand footage, but **educational content, not an ad**: no opening hook, no on-screen offer, no testimonial, no CTA. Dropping one into Ads Manager as-is would perform like an organic clip, not a direct-response ad — there's nothing telling a scroller what to do or why to stop scrolling in the first two seconds.

**This doesn't waste the footage — it means the footage needs one edit pass before it's a launch asset, not zero.** Two paths, not mutually exclusive:

- **Launch creative (Weeks 1-2): static image ads.** Real CROSACORE photos + a text-overlay hook + a real attributed testimonial quote + condition checklist + CTA. This is genuinely ad-shaped with zero video editing required, matches the Ad Library's dominant structural pattern (Section 4), and can go live immediately.
- **Phase 2 creative (once a concept proves itself, or if there's time before launch): edited video ads.** Take the existing raw talking-head clips and add a hook title card, a condition-checklist card, and a closing testimonial + CTA card on top, using the `talking-head-recut` or `embedded-captions` skill — turning the existing footage into an actual ad instead of running it raw. This is real production work (even if fast), so it shouldn't block Week 1 launch.

Section 6 below is written as static-first for this reason.

---

## 4. Meta Ad Library findings (live research, not secondhand guidance)

Browsed the actual Ad Library (sorted by total impressions) for active pain/PT/chiropractic/orthopedic ads in the US. Full findings logged in `ad-creative-principles.md`. Two patterns repeated across unrelated advertisers, several running since early-to-mid 2025 (per this agent's "golden rule," still-running is the actual signal):

1. **The dominant template:** a direct city callout ("Hey Austin!"), a low-friction named offer, a bullet/emoji checklist of specific conditions, one CTA to a dedicated offer page.
2. **The physician-tier variant** (closer to CrosaCore's actual voice): softer, relational copy explicitly removing pressure — "consultations should feel like real conversations... without pressure."

**Applied here:** the structure (city callout, symptom checklist, single low-friction CTA), never the "$49, only 30 spots" scarcity/hype tone — that would violate Brandon's own no-hype, no-guarantees brand rule directly, not just clash with a general vibe.

---

## 5. Budget reality

$17.85/day is under the $10+/day-per-ad floor this agent's own principles doc recommends, and under the 10-15 concepts it suggests launching with. Scaled down: **2 ad sets at launch, ~$9/day each**, judged faster than the standard 7-day window (kill anything at $25-30 spent with zero leads).

- Target CPL: ~$20-30 blended for cash-pay PT.
- $500 ÷ ~$20-30 → **17-25 leads**.
- A 40-55% lead→booked rate (strong existing review base, free-call framing addressing the real cost objection directly, fast follow-up) → **roughly 8-12 consults.** Treat 10 as the realistic target, not a floor — reallocate fast rather than waiting out underperformers.

---

## 6. Campaign structure (Meta Ads Manager settings)

| Setting | Value |
|---|---|
| Campaign objective | **Leads (Website)** — the funnel is live with a working Calendly CTA, so send traffic straight there rather than Instant Forms |
| Budget type | **ABO** |
| Ad sets at launch | 2 static-image concepts (1 per avatar below), ~$9/day each |
| Audience | Broad Advantage+, no interest stacking |
| Age / Gender | 28-58 / All |
| Location | Austin, TX metro, 15-20mi radius |
| Placements | Advantage+ (all placements) |
| Pixel | Confirm a `Lead` (or custom `ScheduleCall`) event fires on the Calendly booking-confirmation view before spending — otherwise Meta is optimizing on link clicks only |

**Weekly rotation:** Week 1 — both avatar concepts live, ~$9/day each. Day 3-4 checkpoint — kill anything at $25-30 spend / 0 leads, reallocate. Weeks 2-3 — narrow to whichever avatar shows the cheapest cost-per-*consult* (not cheapest lead — a concept that books beats one that's just cheap), start 1-2 hook iterations only on the confirmed winner. Week 4 — full budget on the proven winner.

---

## 7. Ad concepts — 2 avatars, 1 offer (free 15-minute Pain Confidence Consultation)

2 concepts, each targeting a genuinely different avatar, both driving the same free-consultation offer. Each pairs a real CROSACORE photo — actually reviewed, not guessed — with a real, attributed testimonial quote. No invented claims, no dig at prior providers, no em dashes, no "pain-free"/"cure"/"fix" framed as CrosaCore's own promise.

### Concept 1 — Busy Corporate Professionals
**Photo:** `CROSACORE-092.jpg` — reviewed: Brandon mid-conversation with two clients in casual-professional dress in front of a whiteboard, explaining a pain-science diagram. Reads as a real consult/education moment, on-brand.
- **Hook:** "Hey Austin. Does a demanding job leave no time to deal with pain?"
- **Primary text:** "In her own words: 'As a recruiter at Apple, I live a busy, high-pressure lifestyle where staying active isn't optional. Since starting with Brandon, I've had a real reduction in pain and learned how to work through flare-ups without catastrophizing.' Dr. Brandon Crosdale, PT, DPT, OCS, offers a free, no-pressure 15-minute Pain Confidence Consultation built around a schedule that doesn't stop. Cash-pay, no insurance billing required."
- **Condition checklist:** "Desk-driven neck and shoulder tension · Recurring low back pain · Pain that's hard to switch off from · No time for lengthy treatment"
- **Headline:** "Free 15-Minute Pain Confidence Consultation"
- **CTA:** Learn More

### Concept 2 — Older / Recovery-Focused Patients
**Photo gap, flagged:** none of the ~18 portal photos reviewed this session show a clearly older-appearing patient — the visible client photos skew younger/athletic. Recommend either a solo Brandon photo (e.g. `CROSACORE-002.jpg`) so the message, not the image, carries the avatar signal, or ask Brandon directly whether a better-matched photo exists before launch — the Ad Library research (message-match: "put the avatar in the ad") means an image that visually skews young works against this concept's targeting.
- **Hook:** "Hey Austin. Ready to move with confidence again after surgery or a setback?"
- **Primary text:** "In her own words: 'I was anxious and fearful of exercise... Brandon was patient and kind and acknowledged my feelings... The personal attention he is able to provide is uncommon in physical therapy... I feel more confident and healthier than ever.' Dr. Brandon Crosdale, PT, DPT, OCS, offers a free, no-pressure 15-minute Pain Confidence Consultation to talk through what's safe and what's next."
- **Condition checklist:** "Recovering from surgery · Fear of re-injury or falling · Balance or mobility concerns · Wanting to stay independent"
- **Headline:** "Free 15-Minute Pain Confidence Consultation"
- **CTA:** Learn More

---

## 8. Phase 2 — turning the raw video into real ads (once Week 1 is live)

For either concept, a matching raw talking-head clip can become a proper video ad by adding, on top of the existing footage:
1. An opening title card (0-2s): the hook line, on-screen, before Brandon starts speaking.
2. A condition-checklist card cut in partway through.
3. A closing card: one attributed testimonial line + the CTA ("Free 15-Minute Pain Confidence Consultation").

This is a `talking-head-recut`-skill job (or `embedded-captions` if just adding on-screen text over the existing cut) — not a reshoot. Worth doing once a concept's photo version proves itself, to add a second creative type to that winning concept's ad set rather than as Week 1 launch material.

---

## 9. Measurement

- **North star:** cost per *booked consult*, not CPL or CTR.
- **Target cost/consult:** ≤$50.
- **Weekly checkpoint:** cheapest cost/lead → which concept's leads are actually booking → is spend pacing to $500 by week 4.

---

## 10. Next steps for Dylan

1. Confirm the Meta Pixel (or a `Lead`/custom event) is actually firing on the Calendly booking-confirmation step at `funnel.crosacore.com` — the page is live but conversion tracking wasn't verified.
2. Decide the Concept 2 photo: use a solo Brandon shot, or check with Brandon for a better-matched older-patient photo before launch (flagged above).
3. Confirm someone calls/responds to every lead fast — this determines the outcome more than the ads do.
4. Say the word and the actual static creative files (image + copy, ready to upload) get built for both concepts.
