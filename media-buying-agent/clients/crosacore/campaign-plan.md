# CrosaCore (Brandon Crosdale) — Campaign Revision v3
**As of:** 2026-09-22 · **Remaining budget:** $411.19 of the original $500 · **Deadline:** 2026-10-11 (19 days left)
**Source:** live Meta Ads data pulled directly from the account via the Meta Ads MCP connector (now
wired up — see note at the bottom), not estimated. `media-buying-agent/CLAUDE.md` is corrected to
reflect this.

---

## 1. What actually happened (live account data, pulled 2026-09-22)

Campaign **"Free 15-min Phone Consult"** (`120254284123690523`, objective `OUTCOME_LEADS`) is
currently **paused at the campaign level** — nothing is spending right now. One ad set ("Consult Ad
Set") held both launch ads, targeting a single broad **25-65, Austin 10mi** Advantage+ audience —
not the 2 separate per-avatar ad sets the original plan called for, and budget was set at the
**campaign level ($25/day, CBO)**, not per-ad-set (ABO) as planned. Worth knowing, not worth
re-litigating — the numbers below are what actually ran.

| | Corporate ad | Older/Recovery ad |
|---|---|---|
| Spend | $46.47 | $42.34 |
| Impressions | 4,105 | 2,639 |
| Clicks | 51 | 23 |
| CPC | **$0.91** | $1.84 |
| CTR | **1.24%** | 0.87% |
| Reach | 1,619 | 1,062 |
| Frequency | 2.54 | 2.48 |
| Tracked leads/bookings | **0** | **0** (1 Messenger conversation started, nothing else) |

**Total spend: $88.81. Remaining: $411.19** — matches what you're carrying forward.

**Your read matches the data:** the Corporate concept is genuinely the better performer — roughly
2x cheaper per click and a 42% higher CTR than the Older/Recovery concept, on top of the qualitative
signal you already had (older demographic wasn't converting). Killing Older/Recovery and doubling
down on Corporate is the right call.

## 2. The real blocker: nothing is confirming a lead

This is the finding that changes the plan more than anything else: **neither ad shows a single
tracked Lead, form-fill, or booking-confirmation event** — only link clicks, landing page views, and
one Messenger conversation. 74 total clicks and $88.81 in spend produced zero conversion signal for
Meta's algorithm to optimize toward, even though the ad set is set to optimize for
`OFFSITE_CONVERSIONS`. That's exactly the risk flagged (and left unconfirmed) in the original
2026-09-13 plan's blocker list — it's no longer hypothetical.

Two live possibilities, both need checking before another dollar is spent:
1. **The Pixel/Lead event genuinely isn't firing** on the Calendly booking-confirmation step at
   `funnel.crosacore.com` — the most likely cause, and the same gap flagged two weeks ago.
2. **People are clicking through and bouncing** — 51+23 clicks got 0 bookings, which on its own
   (even with tracking fixed) would be a landing-page or offer-friction problem, not just a
   measurement problem.

**Do this before resuming spend, not after:** confirm in Meta Events Manager whether a `Lead` (or
custom `ScheduleCall`) event is registered against this pixel at all in the last 30 days. If it's
truly zero events, the fix is wiring the Calendly booking-confirmation page (or a `type=canceled`
redirect check to rule out embed issues) to fire the pixel — a 15-minute fix, but a blocking one.
Spending the remaining $411 with this still broken repeats the exact same result at any budget.

## 3. Revised creative lineup

Killing the Older/Recovery concept entirely (per your call and the data). Corporate Professional
becomes the only avatar for the rest of the budget, running as **3 image variants of the same
concept** instead of 1 — testing whether the client photo (not the copy, which stays constant)
moves performance, per your ask for gender variations:

| Ad | Photo | Proof quote | Status |
|---|---|---|---|
| Corporate Demographic AD (live) | ambiguous-presenting client + therapist, shoulder assessment | Lauren Wright, Apple recruiter | Already spent $46.47 — keep running, don't restart |
| **NEW — Corporate, Male** | male professional + therapist, shoulder assessment | Akhil Mehta, hardware design engineer — real Google review, desk-job/posture angle | Built today: `outputs/ad-crosacore-corporate-male-2026-09-22/` |
| **NEW — Corporate, Female** | female professional + therapist, guided back stretch | Dawn McKinney, Apple analyst — real Google review, desk-job/energy angle | Built today: `outputs/ad-crosacore-corporate-female-2026-09-22/` |

Both new concepts pass Brandon's brand-voice rules (no guarantees, no "cure"/"pain-free" claimed as
CrosaCore's own promise, outcomes attributed as direct quotes, no em dashes) — same check as the
original launch creative. Copy and full provenance in each folder's `copy.md`.

**Also killing the 28-58 broad age targeting** in favor of skewing younger, per your read that the
older demographic isn't working: **25-45** instead of 25-65. This isn't just a hunch — it lines up
with the actual avatar in both new proof quotes (a hardware engineer and an Apple analyst, not
late-career professionals) and with your own decision to stop chasing the older segment.

## 4. Revised campaign structure for the remaining $411

| Setting | Value |
|---|---|
| Campaign | Same campaign, reactivate — no need to rebuild the funnel/pixel setup |
| Ad set | Collapse to **one ad set**, "Corporate Professionals" — 3 active ads (original + male + female), Advantage+ delivery decides winner among them automatically |
| Age / Gender | **25-45** / All (down from 25-65 — corrects the age-skew finding) |
| Location | Austin, TX metro, 10mi (unchanged, already correct) |
| Budget | **$18/day** (CBO, matching the account's existing setup rather than fighting it) |
| Objective | Leave as Leads / `OFFSITE_CONVERSIONS` **only once the Lead event is confirmed firing** — if it can't be fixed same-day, switch temporarily to `Landing Page Views` so the algorithm has a real signal to optimize toward instead of guessing, then switch back once Lead events are live |
| Runway | $411 ÷ $18/day ≈ **22 days** — fits inside the 19 days left to 2026-10-11 if it starts within the next few days; tightens further with every day spend stays paused |

**Day 3-4 checkpoint (per the original plan's own rule, still the right call):** kill any of the 3
ads at $25-30 spent with a CTR meaningfully below the group average — don't wait out a clear
underperformer. By Day 7, expect enough signal to know whether the male photo, the female photo, or
the original photo is the actual winner; put 80%+ of remaining daily budget on whichever one is.

## 5. Budget-reality math

- Blended CPC across both ads so far: ~$1.20. At a typical 2-4% landing-page-view→lead rate for a
  cold local-service audience (once tracking actually counts it), that's roughly **$30-60 per lead**
  — in line with the original plan's $20-30 target, maybe slightly above it given the CTR/CPC mix so
  far.
- $411 ÷ ~$30-60/lead → **7-14 more leads** on the remaining budget (on top of whatever the
  untracked 74 clicks already produced that never got counted — worth manually checking the Calendly
  booking log against ad-attributed traffic dates, since Meta's own numbers may be undercounting real
  bookings right now).
- At the same 40-55% lead→booked assumption from the original plan, that's **roughly 3-7 more booked
  consults** for the rest of the budget — realistically landing the full campaign in the 8-12
  originally projected, not the 10 minimum, if the tracking fix happens this week rather than eating
  more of the runway.

## 6. Next steps for Dylan, in order

1. **Check Meta Events Manager for this pixel today** — confirm whether any `Lead`/custom
   booking event has fired in the last 30 days. This is the single highest-leverage thing to fix
   before touching budget or creative again.
2. If it's broken: fix the Calendly-confirmation → pixel wiring (or add a `ScheduleCall` custom
   conversion) before reactivating spend.
3. Reactivate the campaign, restructure the single ad set to 25-45 age / 3 active ads (original +
   male + female corporate concepts), $18/day.
4. Pause/archive the Older/Recovery ad rather than deleting it — useful negative signal if a future
   client in an older-skewing vertical comes up.
5. Day 3-4: check CTR per ad, cut the weakest.
6. Weekly: cost per *booked consult* (cross-check against the actual PT Everywhere/Calendly booking
   log, not just Meta's dashboard, until the pixel fix is confirmed reliable).

---

## Note: Meta MCP connector is now live

As of today, `media-buying-agent/CLAUDE.md`'s "no live Meta ad-account access" limitation is
outdated — a Meta Ads MCP connector is connected in this environment (account "Crosacore Ad Account",
`1497204665790539`), so this plan is built from real pulled performance data rather than assumptions.
The CLAUDE.md file already carries a 2026-09-22 correction note; this plan is the first real use of
that access.
