# CrosaCore (Brandon Crosdale, DPT, OCS): Client Context

Rules specific to this client. They override the general skill defaults wherever the two disagree.
Read this before writing any CrosaCore plan, ad, or script.

## Who
- Cash-pay physical therapy + strength work, **central Austin clinic at 711 W 38th St**. Also does
  in-home visits. Dashboard client_id **1**. Meta ad account **1497204665790539**, Page
  1239614145912021.
- Does not bill insurance; superbills available for out-of-network reimbursement. Eval is $200 for
  an hour; average patient is ~8 visits / ~$2,200.

## Targeting and angle rules (from Dylan, 2026-10-06)
- **Lead with in-clinic.** Every ad, script and end card should emphasize one-on-one treatment at
  the central Austin clinic. In-home can be mentioned as secondary at most. Never say "office" or
  "workplace" visits; the landing page only says "in-clinic & in-home".
- **Patients up to age 60 only.** Set the age max to 60 as a **hard limit**, not an Advantage+
  suggestion. In the first half of the budget the suggestion setting let 67% of spend go to people
  55-65+. Don't make concepts aimed at older people or their caregivers (the "Driving Mom to PT"
  ad was dropped for this).
- **Avatar:** a busy professional under 60 with pain that keeps coming back, often a lifter or
  active person who wants to get back to training. They've usually tried PT, chiro, massage or rest
  without a lasting fix. (Brandon's own onboarding answer.)
- **Say "private pay" in the ad.** In round one, 2 of 4 leads asked about insurance and dropped.
  Screening for it up front costs a little volume and saves wasted leads.

## Brand voice (Brandon's onboarding rules, binding on every line)
- No guarantees or absolute claims ("cure", "fix the root cause", "permanent", "pain-free").
- Don't attack other providers or imply previous PT/chiro/doctors were wrong.
- Not salesy, hype-heavy or AI-sounding. Confident, evidence-informed, straightforward.
- **No em dashes.** Testimonials are first name only and quoted as the patient's words, never
  restated as CrosaCore's own promise.
- No ad copy that asserts the viewer has a condition ("your back pain"); Meta rejects it.

## How leads flow
- Meta **Instant Form** leads → Make.com relay → Brandon's portal CRM → the AI SMS setter ("Sophie")
  texts within minutes. Website/pixel conversion tracking never worked reliably, so optimize for
  Instant Form leads, not website leads.
- The AI tags leads it can't serve **Unqualified** (out of area, insists on insurance billing), which
  stops all automated messaging to them.
- Prospect follow-up, appointment reminders and no-show/cancellation sequences run from the portal
  (SMS + email). Finishing a sequence with no reply tags the lead **Database Reactivation**.

## What the account data has shown (as of 2026-10-05)
- ~$257 of the $500 budget spent; budget deadline **2026-10-18**.
- The old website campaign's cheap clicks were mostly **Audience Network** junk; exclude it.
- **Facebook Reels** took 43% of lead form spend with zero leads; exclude it. FB Feed and Stories
  produced the cheapest leads.
- The 10-mile radius audience is small and CPMs climbed from $66 to $103 in a week. Use "people who
  live in" the area, not "recently in" (an out-of-state lead got through on "recently in").
- Current approved creative lives in `creatives/`. The in-clinic video ads are
  `video-back-to-square-one` and `video-back-by-thursday`.
