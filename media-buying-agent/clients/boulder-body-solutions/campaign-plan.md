Artifact: https://claude.ai/artifact/2qW6gw3mrZL9iCtbMXFPHb (approved by Dylan 2026-11-09, gates G1-G8; republish to this URL on edits)

# Campaign plan: Boulder Body Solutions (Dr. Aaron Shaver, DPT, MAT), drafted 2026-11-09

Goal: **7-10 paid $49 Why-It-Keeps-Coming-Back Assessments in 30 days** on **$30/day ($900)**.
Segments: (A) active adults who keep getting pulled out of their sport; (B) chronic pain, tried everything.

## 0. Account data
Boulder has never run ads (no Meta ad account linked, no spend history). Evidence comes from DigiGrowth's other clients:

| Client / ad | Format | Offer + capture | Cost/lead | Booked |
|---|---|---|---|---|
| Advantage C7 "Before the Injection" | Patient-story video | Free 15-min call, Instant Form | $10.63 (13 leads, CTR 4.6%) | Advantage overall: 25 leads, ~10 replied, ~5 booked |
| Advantage C4 "Normal MRI" | Patient-story video | same | $11.69 (6) | |
| Advantage C3 "Neck Headaches" | Patient-story video | same | $14.24 (6) | |
| CrosaCore "Google Review Male" | Static review | Instant Form | $12.95 (2) | CrosaCore overall: 12 leads, ~8 replied, ~1 booked |
| CrosaCore "UGC Female #2" | AI UGC | Instant Form | $22.93 (3) | |
| CrosaCore website-lead ads | Static → landing page | Website | 0 leads on $89 | |

Carry forward: Advantage's dark-then-curiosity patient-story angles (structure only). Drop: AI UGC as the lead format (leads, but ~1 in 12 booked); website-conversion ads.

## 1. Assets
- **Portal uploads:** none.
- **Website** (boulderbodysolutions.com): photos of Aaron and the clinic (`design-agent/outputs/blueprints/boulder-body-solutions-blueprint/photo0.png`, `photo1.png`), 9 written patient reviews (Max, Amie, Annette, Sando, Lisa, Marc, Gabby, Helen, Nicolene). No video, and no Instagram/YouTube/Facebook links on the site.
- **Blueprint ads already built** (`.../ads/`): static review cards for Amie and Max, a rebranded AI UGC video (poster `ugc_poster.jpg`; Annette's review + $49 end card), tiles of Aaron and of hands-on work.
- **Gap:** no footage of Aaron. A 20-minute phone shoot (MAT test-retest on a willing patient, plus Aaron to camera) would unlock the founder and in-house concepts. The full content table comes at G7.

## 2. Research headlines (full: `clients/boulder-body-solutions/deep-research.md`)
- **#1 pain: "it helps, then it comes back"** ("all help but don't fix the problem"; "feel good for a day or two... Rinse and repeat for the next 20 years").
- **Tried-everything lists** (massage, yoga, Pilates, acupuncture, PT, dry needling, chiro, injections).
- **Segment A identity loss + deadlines** ("too young to give up on my passion"; ski season).
- **Objections:** another thing that won't work; is it short-term like massage; upsells and endless visits.
- **Positioning:** don't compete on reviews (every top Boulder PT is 4.9-5.0 with 140-717 reviews). Own: one therapist, the whole hour; for people regular PT didn't fix; the visible muscle test and re-test.
- **Register:** A = identity + deadline; B = frustration then a curiosity turn ("the sore spot is the one doing all the work").

## 3. Proven ads + the offer
22 of 43 active 6+ month proven ads shortlisted (`context/proven-ads/pt-chiro-pain.md`): the sport-clinic template P39-P42, the mechanism ads P43/P44/P46, long patient stories P38, tried-everything P1-P4/P6/P34/P35, founder stories P8/P10/P12, plus P28, P31, P32, P45. No proven MAT, ski or climbing ads exist, so those angles are fresh tests.

**Offer (approved by Dylan and Aaron, 2026-11-09): The Why-It-Keeps-Coming-Back Assessment.** $49, normally $120, paid at booking via the texted link. 60 min one-on-one with Dr. Aaron · full story · muscle-by-muscle MAT test · hands-on work + re-test to see what changed · a clear plan. No guarantee. Urgency: "Dr. Aaron sees every patient himself, so there are only 10 new-patient spots a month."

## 4. Blockers (clear before any spend)
1. **Booking page + payment:** Aaron's booking page has no calendar, hours or event type, and Stripe isn't connected. The funnel's button currently redirects to his homepage. The text-to-pay flow can't work until this is live. **Hard blocker.**
2. **Meta assets:** no ad account linked for Boulder, and his business Facebook Page and Instagram aren't known (none linked on his site). Needed: his Page (and IG, if any) shared to DigiGrowth's Business Portfolio, plus an ad account (pilot ads run on Dylan's card). **Hard blocker.**
3. **Lead flow:** an Instant Form → Make relay → CRM + AI text agent route for client 6 (the same setup as CrosaCore). Test it with the default test number before launch. **Hard blocker.**
4. **AI text agent (Maya) brief:** rename the offer, add the stack, the spot line and the paid-link flow. Decide whether the "free phone consult" fallback stays (recommended: keep it only for people who won't pay, never offered first).
5. **Texting number is +1 218 (Minnesota).** Boulder leads get texts from an out-of-state area code, which hurts reply rates. Recommend a 303/720 number. *Soft blocker.*
6. **Office hours** for the agent and the booking page (still not on file).
7. **Funnel page:** rename the offer to match (it already shows "Normally $120 · Limited spots each month").
8. No pixel/CAPI needed for an Instant Form campaign. Optimize for leads; track paid bookings in the dashboard.

## 5. Budget math
- $30/day × 30 days = **$900**, above the $25/day house minimum.
- **Expected cost per lead:** $15-25. Advantage got $10-14 on a *free* offer; a stated $49 price and Boulder's higher CPMs push it up. That gives **36-60 leads** (mid case ~45).
- **Lead → paid conversion needed:** 7 paid ÷ 45 leads = **16%** (10 paid = 22%). Advantage booked ~20% of leads on a *free* call; a paid booking will convert lower. Assume 12-18%, which gives **~5-8 paid** on the mid case.
- **Verdict: tight.** 7 is reachable if cost per lead stays ≤ $20 and the AI agent converts ≥ 16%.
- **Levers that close the gap without more spend:**
  - (a) **SMS reactivation** of Aaron's 108 CRM contacts and past patients in week 1 with the same offer (part of DigiGrowth's standard delivery).
  - (b) Ask about price in the form ("The assessment is $49, normally $120. Ready to book?") so the AI agent works pre-qualified leads.
  - (c) The agent sends the pay link within 5 minutes.

## 6. Campaign settings (house format)
| Setting | Value |
|---|---|
| Campaign | 1 campaign, objective **Leads**, no special ad category |
| Ad set | 1 ad set, **$30/day** (campaign budget) |
| Conversion location | **Instant Form**, "More volume" type, but with a price-acknowledgement question (see 5b) and "What have you already tried?" (Massage / Chiro / PT / Injections or meds / Nothing yet) |
| Geo | Boulder, CO + **15-mile radius** (Boulder, Louisville, Lafayette, Superior, Gunbarrel, Niwot, south Longmont), **hard limit** |
| Age | **28-70, hard limit** (covers both segments; not an Advantage+ suggestion) |
| Gender | All |
| Detailed targeting | None (broad); the creative does the targeting |
| Placements | Advantage+ placements, with Audience Network **excluded** |
| Ads | **10 ads, at least 7 video**, 3 statics max |
| Lead follow-up | AI text agent within 5 min, texts the $49 booking link; reactivation SMS to 108 contacts in week 1 |
| Why one ad set | Concentrates learning on a small budget; Meta's delivery picks which of the 10 ads get spend. No per-format or per-segment ad sets. |

## 5B. Content audit (Dylan, G6: AI + Aaron's existing photos and reviews only, no filming)
| Asset | Type | What it shows | Quality | Concepts | Edit needed |
|---|---|---|---|---|---|
| `design-agent/.../boulder-body-solutions-blueprint/photo0.png`, `photo1.png` | Website photos | Aaron / the clinic | Website-grade | C2, C7, C9 | Crop to 4:5 and 9:16 |
| `.../ads/tile_aaron.jpg`, `tile_hands.jpg` | Photo tiles | Aaron; hands-on work | Small (tiles) | C2, C9 | Upscale or use as inset only |
| `.../ads/static_review_max.jpg`, `static_review_amie.jpg` | Built review statics | Max and Amie review cards, $49 CTA | Ad-ready | C10 | New CTA and spot line |
| `.../ads/ugc_poster.jpg` + rebranded UGC video (blueprint) | AI UGC video | Generic actor, Boulder line card, Annette's review, $49 end card | Ad-ready | Reference for C1 | New script; this one was built from a CrosaCore ad |
| 9 written reviews (website) | Text | Max, Amie, Annette, Sando, Lisa, Marc, Gabby, Helen, Nicolene | Real, first names | C2, C7, C8, C9, C10 | Quote cards |
| Video of Aaron, test-retest footage, social accounts | none | none | n/a | none | Gap: AI fills (Dylan, G6) |

## 7. Ad concepts (10): every one sells the Why-It-Keeps-Coming-Back Assessment ($49, normally $120, 10 spots/month)

| # | Concept | Proven ref | Borrowed | Research quote | Stage | Pillar | Format | Avatar | Lead element |
|---|---|---|---|---|---|---|---|---|---|
| C1 | Helps, then it's back | P2 BIRP + Advantage C7 | "You do the homework, still comes back" → why → offer | "feel good for a day or two... Rinse and repeat" (T3) | Problem-aware | AI UGC actor | Selfie video 30-40s, 9:16 + 4:5 | B: woman ~45, neck/shoulder for years | Emotion: frustration |
| C2 | The tried-everything list | P1 Life Chiro, P35 | Rapid list of tried fixes → "still dealing with" → offer | "massage, yoga, Pilates, traditional physical therapy and acupuncture" (Annette, CL) | Solution-aware | In-house (photo + real review) | Kinetic-text video 15-20s over Aaron's clinic photo, Annette's review card | B: tried-everything | Connection |
| C3 | Too young to quit | P40 Be Ready, P32 | "Not able to run like you used to?" identity hook → review → offer | "I'm only 40 and too young to give up on my passion" (T6) | Problem-aware | AI UGC actor | Selfie video 25-35s, outdoors on a Boulder-looking trail | A: runner ~40, told to stop | Emotion: defiance |
| C4 | Before the lifts open | P42 Athletes' Potential | Hyper-specific sport moments as callout → anchored named assessment → spot cap | "great tutorial ... exactly what's needed 4 wks before ski trip" (V6); "back on the slopes before the season ended" (ALT) | Product-aware (offer-led) | AI scene/motion | Video 15-20s: AI ski scenes + on-screen moments ("knee on the last run", "back after the drive up") + offer card | A: skier 30-55 | Attention / urgency |
| C5 | The sore spot is the one doing all the work | P43 / P44 Xstance, P46 ReliveX | "You treat where it hurts, the problem started somewhere else" + arrow chain | "smaller muscles that have stopped doing their job" (RA); "a seemingly unrelated muscle group" (MP-MAT) | Unaware | AI scene/motion | Animated explainer 20-30s: body outline, weak muscle → neighbor overworks → joint takes the strain; names MAT | A + B | Curiosity |
| C6 | Whatever your scan says (revised 2026-11-10, Aaron: don't put off people with degeneration on imaging) | P3 ATIVA + Advantage C4 ($11.69 CPL) | "MRI says normal? Or wear and tear?" → "a scan can't show which muscles turn on" → offer | "everything looks fine, everything's normal" (T3) | Solution-aware | AI UGC actor | Selfie video ~16s | B: man ~50, low back, any MRI result | Curiosity |
| C7 | One more option before the injection | P34 ZRecover + Advantage C7 ($10.63 CPL) | "Tried PT, injections without lasting relief?" → real patient story → offer | Nicolene: "7 weeks post my Tenex surgery I am still without relief... more improvement than months of PT" (CL) | Solution-aware | In-house (real review) | Review-story video 20-30s: text-on-screen of Nicolene's review over Aaron's hands-on photo, offer end card | B: injection or surgery on the table | Emotion: fear → hope |
| C8 | Full-structure story (6 beats) | P38 RunLab | Long tried-everything story → "the difference was the test" → back to what they love | "I learned to manage the pain but it didn't go away" (RA); Max, Sando, Lisa (CL) | Solution-aware | AI UGC actor | 45-60s: hook → story → why MAT is different (test, work, re-test) → what the visit includes → 3 real reviews → CTA | A: active adult ~45 (climber/runner) | Connection |
| C9 | Boulder callout + checklist | P39 Tranquil Place, P41 iCare, library #13 | Geo + sport callout → checklist → itemized named assessment → anchor → spot line | "all help but don't fix the problem" (T2) | Product-aware | AI static (with Aaron's photo) | Static 4:5: "Boulder: knee, hip, back or shoulder that keeps coming back?" + 4-item checklist + offer stack + Aaron inset | A + B | Attention |
| C10 | Max's review card | P19 Elevate (review hook) + blueprint static | Real review as the headline → offer | Max: "countless physical therapists that were unable to treat me effectively" (CL) | Most-aware | In-house (real review) | Static 4:5 + 9:16 review card (rebuild `static_review_max.jpg`), spot line | A: recurring sport injury | Connection / proof |

**Spread check:**
- Videos: 8 (C1-C8); statics: 2 (C9, C10).
- Awareness: 3 unaware/problem-aware (C5, C1, C3); 4 solution-aware (C2, C6, C7, C8); 3 product/most-aware (C4, C9, C10).
- Pillars: AI UGC actor C1, C3, C6, C8; AI scene/static C4, C5, C9; in-house (Aaron's photos + real reviews) C2, C7, C10.
- Segments: A = C3, C4, C8, C10; B = C1, C2, C6, C7; both = C5, C9.
- Too close? C1 and C2 share the "keeps coming back" angle but differ in format (actor story vs. kinetic list + real review) and stage. C6 and C7 are both "tried the medical route" but differ in trigger (scan vs. injection) and format. No two share both creative type and angle.

**Copy rules for every concept** (from client-context):
- MAT is named in hooks and explained only as "finds the muscles that stopped doing their job".
- Only Aaron's own patients appear as proof, first names only.
- AI actors never claim to be his patients. They speak as people in the situation, and quotes stay with the real reviewers.
- No emoji. No "root cause" or "back to what you love".
- No outcome promises; outcomes appear only inside real reviews.
- The spot line goes in every CTA.
- Hooks describe a situation, never assert the viewer's condition.

**Skipped library concepts:** #1 workshop, #2 free visit (the offer is the named $49 assessment), #9 home visits, #10 falls, #11 pelvic floor, #14 practitioner to camera (no footage; Aaron is never rendered as an AI actor).

## 8. Measurement
- **North star:** paid assessments booked (goal 7-10 in 30 days). **Target cost per paid assessment: ≤ $90-130** ($900 ÷ 7-10).
- **Funnel metrics:** cost per lead (expect $15-25), lead → paid rate (need ≥ 16%), show rate, assessment → plan conversion (ask Aaron weekly).
- **Video:** hook rate (3-second views ÷ impressions) and hold rate (ThruPlays ÷ impressions). Low hook = fix the first frame. Good hook + low hold = fix the body. Good both + few leads = the ending isn't handling objections, so fix the CTA/offer card.
- **Spend-spread check:** healthy = spend reaching most of the 10 ads. If it's stuck in 2-3, the next batch adds new *formats*, not variants.
- **Kill rules:** judge the ad set on cost per paid assessment, not one ad's cost per lead. Kill policy problems, and ads with 0 leads after ~$40 spend (about 2× expected CPL). Don't kill an ad that's getting spend and leads just because its CPL is above the others.
- **Weekly checkpoints (each Monday):**
  - Week 1: delivery spread, cost per lead, reactivation bookings.
  - Week 2: lead → paid rate, so tune Maya's pay-link follow-up if under 16%.
  - Week 3: on pace for 7? If not, add 3 new-format ads from the strongest angle and push reactivation round 2.
  - Week 4: guarantee pacing.
- **Scaling path:** when the first angles plateau, open a new segment (prehab/knee and hip replacement, the 3rd segment Aaron named) rather than more variants of the same.

## 9. Next steps for Dylan (priority order)
1. **Build Aaron's booking page:** calendar, hours, event "Why-It-Keeps-Coming-Back Assessment" (60 min, $49, anchor $120, 10/month), and connect his Stripe. Fix the funnel button (it currently redirects to his homepage).
2. **Meta setup:** get his Facebook Page (and IG, if any) into DigiGrowth's Business Portfolio, and create/assign the ad account on Dylan's card.
3. **Lead flow:** Instant Form → Make → /webhooks/make-leadgen → CRM + Maya for client 6; test with +17542485326.
4. **Maya's brief:** the new offer name, stack, spot line and pay-link flow; the free phone consult only as a fallback for people who won't pay; his office hours.
5. **Texting number:** swap the 218 number for a 303/720 one.
6. **Funnel page:** rename the offer.
7. **Reactivation:** SMS the offer to Aaron's 108 CRM contacts in week 1.
8. **Creative:** run `generate-ad` on C1-C10 (gated: copy → stills/actors → video), then upload 10 ads and launch at $30/day.

## Gate log
## Gates
- G1 (2026-11-09): APPROVED as-is. Segments: active adults in rec sports + chronic pain / tried everything (not prehab, not athletes). Budget $30/day for 30 days; success metric 7-10 paid $49 assessments in 30 days.
- G2 (2026-11-09): APPROVED. Advantage's patient-story angles (still comes back / tried everything / clean scan) are the first concept candidates (structure only, none of Phil's patients/claims); AI UGC deprioritized. Lead path: Meta Instant Form, then the AI agent texts the $49 booking link (paid-offer flow). Aaron's booking page (calendar, hours, appointment type, Stripe) must be live before launch.
- G3 (2026-11-09): APPROVED. deep-research R1 brief, R2 raw (167 quotes) and R3 dossier all approved. Dylan: name MAT in hooks. Final files in clients/boulder-body-solutions/ (deep-research.md, customer-language.md, client-context.md). Strongest angles: #1 helps-then-it's-back, #2 tried-everything list, #5 muscle that stopped doing its job, #6 clean scan, #10 before the injection.
- G4 (2026-11-09): APPROVED. Shortlist for Boulder: P38-P46 (new) + P1, P2, P3, P4, P6, P8, P10, P12, P28, P31, P32, P34, P35. No strikes.
- G5 / O1 (2026-11-09): APPROVED audit ($49 normally $120; capacity assumed 10/mo). Allowed levers: named assessment ONLY (no guarantee, no free option, no bonus).
- G5 / O2 (2026-11-09): picked A "The Why-It-Keeps-Coming-Back Assessment" (score 26 vs ski 25, MAT test 21). Ski season = ad angle, not offer.
- G5 / O3 (2026-11-09): APPROVED; Dylan says Aaron is already OK with it, incl. 10 spots/month. Saved to clients/boulder-body-solutions/client-context.md "## Offer (approved 2026-11-09)".
- G6 (2026-11-09): APPROVED strategy as drafted (blockers, budget math, settings). Footage: AI + Aaron's existing photos/reviews only, no filming.
- G7 (2026-11-09): APPROVED all 10 concepts (C1-C10).
- G8: full plan published as Artifact https://claude.ai/artifact/2qW6gw3mrZL9iCtbMXFPHb (source html in session scratchpad), awaiting Dylan. On approval: copy campaign-plan.md to clients/boulder-body-solutions/ with the artifact link on line 1, delete this folder (move offer.md content already lives in client-context.md).
- (G4 detail:) context/proven-ads/pt-chiro-pain.md re-verified (P7, P21, P22 dropped) + P38-P46 added = 43 active proven ads. Principles section added to context/ad-creative-principles.md (2026-11-09).

## Step 2 / 2B (2026-11-09)
- Boulder: no Meta ad account visible (only an unnamed 963679400743775 with $0 lifetime, no business). No spend history, so the creative gap table is fully open.
- Pinnacle (266698946): $0 lifetime spend on everything visible. Nothing to learn.
- Advantage Therapy (1953827625146160), live since ~10/30, Instant Form, FREE 15-min "Why does it keep coming back?" call, founder/patient-story video:
  - C7 Before the Injection: $138, CTR 4.60%, 13 leads, $10.63 CPL
  - C4 Normal MRI: $70, 4.61%, 6 leads, $11.69 CPL
  - C3 Neck Headaches: $85, 4.47%, 6 leads, $14.24 CPL
  - C1/C2/C5/C6/C8/C9/C10: <$3 each, Meta didn't spend on them.
  - Lead quality (SMS, approx.): 25 threads, 10 replied, ~5 booked.
- CrosaCore (1497204665790539), Sep-Oct, Instant Form, AI UGC + Google-review statics; ~$500, 12 leads:
  - UGC Female #2 $22.93 CPL (4.42%); Video Female UGC $29.39 (5 leads); Google Review Male $12.95 (2 leads); Google Review Female $35.04
  - Website-lead ads (Corporate/Older Demographic) got 0 tracked leads on $89.
  - Lead quality (approx.): 15 threads, 8 replied, ~1 booked.
