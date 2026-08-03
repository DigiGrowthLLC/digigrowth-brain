# Cold Calling Insights — Synthesized from ~9 Months of Iteration

*Source: Dylan's Google Drive cold-calling corpus (scripts, notes, call reviews, rebuttal vault, playbooks, metrics). Compiled 2026-07-30 as a pre-read before building the `cold-calling-script` skill.*

`Last resync: 2026-08-03`

---

## Update Log

Reverse-chronological. Each entry is tagged `(automated resync)` (weekly, via `executive-assistant/.claude/skills/cold-calling-resync/SKILL.md`) or `(Dylan, in conversation)` (reactive, added the moment new data/notes come up). Check here first before leaning on the Baseline below — an entry may supersede a stale number or contradict a stated principle (the way March 2026's real booking rate contradicted the "V.1.9 was an improvement" narrative — see Baseline §7-8).

### 2026-08-03 (automated resync)
- **Drive:** No new or changed cold-calling docs since the last resync (2026-07-30) — searched all known title patterns modified after that date, zero matches.
- **Metrics:** No August 2026 Cold Calling Metrics sheet exists yet. Most recent sheet is still July 2026 (`July 2026 DigiGrowth Cold Calling Metrics`, last modified 2026-07-21, unchanged since the prior resync): 30 calls, 4 answered, 1 pitch, 0 resonations, 0 booked — sample still too small to read (per Baseline §7).
- **OS dialer:** Could not reach the OS dialer API this run — the cloud environment's network policy rejected the CONNECT to `digigrowth-brain-production.up.railway.app` (403 at the proxy layer), not a "no calls logged" response. This is an infrastructure gap in this run, not a data finding; the OS dialer disposition/notes source was not checked this week.
- **Changes the picture?** No — no new signal surfaced from the two reachable sources, and the OS dialer gap is a tooling issue to flag to Dylan, not a contradiction of anything in the Baseline.

---

## Baseline Synthesis (2026-07-30)

### 1. Executive Summary

Dylan has been running a disciplined, data-tracked cold-calling operation targeting athletic/training facility owners since at least November 2025, iterating through at least eight named script versions (V.1 → V.2.3) plus a spun-off "AI voice agent" variant for a separate product (Synthesis). The throughline across every doc is a consistent theoretical framework — the Prime Directive of Consistency, the 4 Pillars (Volume, Follow-up, Result-not-Process, Offer), Lock & Key psychological matching, and a heavy emphasis on vocal delivery (pace, pitch, pauses, inflection) — layered on top of a fairly stable script skeleton (permission-based opener → vague value-prop with concrete dollar figures → curiosity-gap process explanation → booking ask → Ben-Franklin-style pre-frame close). Script changes over time were driven less by structural rewrites and more by micro-tuning: shortening/lengthening the opener, swapping "salesperson" framing for "growth partner" framing, and eventually personalizing the opener to each prospect's current offer (V.2.3). Call reviews consistently diagnose the same three delivery problems (upward inflection reading as uncertainty, rushing/speaking too fast, low authority framing) far more than they diagnose script-content problems — suggesting execution, not script wording, is the current bottleneck. The metrics tell a more complicated story than the qualitative notes do: booking rate (appointments booked ÷ pitches) peaked in March 2026 at ~10% and then fell by more than half in April even as the script version "improved," and July 2026 data is too sparse to draw conclusions — a genuine tension worth resolving before treating V.2.3 as a proven best-in-class reference.

### 2. Core Framework & Principles

These recur nearly verbatim across "Cold Calling Critical Information," the "Pre Cold Calling Playbook" (and its lowercase duplicate), and are echoed in the Sales Arsenal — they represent Dylan's durable operating philosophy, independent of any one script version.

**Prime Directive: Consistency.** Results follow effort, not emotion. Outreach has a 2–4 week lag before results show, so short-term emotional swings are noise, not signal.

**The 4 Core Pillars:**
1. **Volume** — the #1 driver of success. Constantly ask "how do I 2x–10x this?" More reps = more data = faster iteration. Sessions structured as 1hr on / 15min break to sustain volume without burnout. "Lead Quality Paradox": contact everyone, because "unqualified" leads still convert sometimes.
2. **Follow-up** — wins most appointments. Cold outreach gets replies after 2–3 follow-ups; warm leads convert after 5–8. Persistence is framed as professionalism, not pushiness.
3. **Result, not Process** — sell the destination, not the mechanism. Curiosity beats information; over-explaining the "how" kills the sale. Keep the *how* vague so curiosity pulls the prospect toward the call.
4. **Offer** — a stronger offer beats a stronger script; a 2x offer improvement is treated as roughly equivalent to a 10x copy improvement. Never share pricing or full mechanics on the cold call — the only goal of the call is to book the meeting.

**Lock & Key Theory.** Every prospect's mind is a lock; the message is the key. Match their tone, pace, and mindset rather than forcing a fixed script reading.

**Vocal Psychology** (treated as "your real weapon," most heavily emphasized in the notes/reviews, more than script wording):
- *Pitch*: lower = authority, higher = excitement — vary it so delivery doesn't sound robotic.
- *Pace*: slow = confident, fast = emotional; pace should be a deliberate choice, not a nervous default. One note prescribes speaking at ~80% of natural fast speed with micro-pauses after key statements.
- *Pauses*: silence builds control and gravity (this is "Weapon 1" in the Sales Arsenal too — let silence pull more information out of the prospect).
- *Inflection*: downward = certainty (use on statements), upward = curiosity or pattern interrupt (use on questions) — reviews repeatedly flag Dylan defaulting to upward inflection even on statements, which reads as approval-seeking uncertainty.
- *Tone/volume*: slightly quieter volume pulls listeners in; enunciation signals precision and credibility.

**Execution habits:**
- *Pattern interrupt* — don't open like a salesperson; confused/curious tones and unexpected phrasing keep the prospect from auto-triggering their "sales call" defense script.
- *First 10 seconds* — don't pitch immediately; the only job of the opener is to buy attention and lower defenses.
- *Objections* — Agree → Reframe → Redirect. Never defend a position; maintain frame control (see also Sales Arsenal Weapon 8: use questions that undermine a belief rather than arguing against it directly).
- *End strong* — confirm the appointment explicitly, no soft "let me know" language; hold the frame through the close.

**Mindset / identity work — "Cold Call Dylan."** A deliberately constructed persona: emotionally detached from outcome, calm, composed, confident without approval-seeking, visualizes success before the session starts. Rejection fear is explicitly reframed as an evolutionary social-status protection mechanism that has no real bearing on cold calling outcomes (the "DISARM protocol" reference) — the business is framed as an entity separate from the self, so a "no" is not a personal verdict. The Sales Arsenal's "Non-Judgement" and "Let them sweat the gravity of their situation" weapons reinforce the same discipline: don't rescue the prospect from their own pain, don't let internal bias about a prospect's fit skew the call.

### 3. Script Anatomy (Reusable Pattern)

Every full script version — V.1.1 through the current V.2.3 — follows the same five-beat structure, even as the wording of each beat evolved. V.2.3 is the cleanest current expression of it:

1. **Opener (permission-based, disarming).** Confirm identity, name yourself, ask permission for a short amount of time, explicitly invite them to hang up if irrelevant ("feel free to cut me off if this isn't in your swimlane"). In V.2.3 this is personalized: it references the prospect's own current promotion/offer as a custom hook rather than a generic line.
2. **Credibility / value frame with concrete numbers.** State a specific, quantified outcome band ("5-15k in new business month by month") tied to a believable mechanism (an "AI-backed client acquisition system"), without over-explaining. Numbers exist to be *credible enough to be curious about*, not to fully justify the offer.
3. **Curiosity-gap process explanation.** When asked "what does the process look like," deliberately give an incomplete answer — enough to sound legitimate ("infrastructure and systems behind the scenes that removes you as the bottleneck") while stating outright that it's "hard to explain properly on a quick call." This is the Result-not-Process pillar operationalized.
4. **Booking ask.** Direct, assumptive close — "is it worth setting up a quick call," immediately followed by "got your calendar on you" once they agree, with essentially no space left for hesitation.
5. **Pre-frame / Ben-Franklin-style close.** A distinctive, consistent block used across every version once a time is booked: a scripted sequence of "can we agree on a couple things" mutual-permission exchanges (both sides can say no without hard feelings), ending in an explicit cancellation pre-handle ("can you think of any reason you'd want to cancel?"). This close is the most stable, least-revised element of the entire corpus — it appears nearly word-for-word from the earliest full script through V.2.3.

The Free Offer Script (V.1.1) and the Synthesis AI voice agent script are variants of this same anatomy adapted to a different offer/ICP (a free AI-employee build, and an AI phone agent for healthcare respectively) — useful as proof the anatomy generalizes, but they are not part of the DigiGrowth training-facility script's direct lineage and shouldn't be conflated with it in the skill.

### 4. Version Evolution

- **V.1 Construction doc** — not a script per se; a reference list of 25+ named cognitive biases/psychological levers (curiosity tendency, zero-risk bias, reciprocation, Ben Franklin effect, disqualified identity bias, etc.) mapped to an early athletic-facility script draft. This is the theoretical seed everything downstream draws from.
- **V.1.4–V.1.6 (notes, Feb–Mar 2026)** — early diagnosis: training facility owners respond to precision and directness, not friendliness; they get impatient with too many discovery questions. Notes flag the opener as too long/salesy and lacking a "curiosity spark." Multiple opener rewrites tested (Ex 1–3) converging on a shorter "I'll be direct... if this isn't for you just tell me... would 20-40 more intro sessions help?" pattern.
- **V.1.7 (mid-March)** — first version to hit meaningful traction: notes report a "2% ABR, major improvement" and it's designated the control script for future A/B comparison. Feedback: opener still reads as "salesman" in the first line; wants more authority.
- **V.1.8–V.1.9** — reframes Dylan from "I help training facilities book intro sessions" to a "growth partner" positioning, explicitly because notes flagged that the "I help X" framing diminished perceived authority. V.1.9 adds the quantified value stack (25% close rate, $1,000 LTV → "$5-10k, sometimes 15k in new business") that persists through V.2.3.
- **V.2.1** — same body as V.1.9, functionally a naming/versioning checkpoint more than a rewrite (the notes doc for V.2.1 is a single line: authority still feels diminished, keep pushing "growth partner" framing).
- **V.2.2** — no textual change captured in the notes corpus; appears in the metrics log as a brief test (4/20–4/21) before reverting to V.2.1.
- **V.2.3 (current)** — the one structural addition: a custom opener that references the specific prospect's current promo/offer, replacing the generic pain-point line. This is the most significant change since V.1.9 and is not yet reflected in a matching "V.2.3 notes" doc, so the *reasoning* behind it isn't documented as explicitly as earlier changes — it can be inferred (specificity → higher relevance → lower defensiveness) but Dylan hasn't written that hypothesis down anywhere in the corpus.
- Separately, **V.1.1 Free Offer Script** and the **Synthesis AI voice agent script** represent lateral experiments (different ICP/offer) rather than steps in the main version chain.

### 5. Objection Handling & Rebuttals

The Rebuttal Vault (spreadsheet) is organized by objection type with a consistent Agree→Reframe→Redirect shape, plus an unused "Score /10" column suggesting Dylan intended to rate rebuttal effectiveness but never populated it:

- **"Not interested"** → acknowledge, then force a binary diagnostic: "is that because you don't want help, or because you don't trust a random guy on the phone to be the one to do it?"
- **"What is this / what are you selling"** → explicit non-pitch framing ("this isn't a pitch, I only work with businesses with a real bottleneck"), then restate the pain pattern seen across similar prospects.
- **"Busy / no time"** → diagnostic branch: timing vs. priority. If "not a priority," reframe with a risk scenario ("if member acquisition dropped 20% next month, would it become one?").
- **"Booked up"** → treated as a good problem, then probed for whether it's true capacity or a comfortable ceiling, surfacing waitlist/cancellation risk to reopen the need.
- **"Send me an email"** → resisted as a stall; countered by asking what specifically they'd want in it, then pivoting to "let me have 30 seconds instead of playing email tag."
- **"Not enough staff"** → reframed from a volume risk to a "predictable demand makes hiring a math decision, not a risk" argument.
- **"We run our own marketing"** → diagnostic sequence (organic/paid/mix → hitting targets? → predictable or fluctuating?) rather than a canned rebuttal — mirrors the Sales Arsenal's "diagnose, don't close" philosophy.
- **"Working with an agency"** → non-confrontational reframe: everyone's working with someone, the goal is just to see if there's a better alternative, with an explicit early exit offered if it's not a fit.

**The DigiGrowth Sales Arsenal** (11 "weapons") supplies the underlying technique library the rebuttals draw on: Silence (let discomfort surface more information), Non-Judgement (internal bias skews call direction), Never Solve (let the prospect sit with the pain rather than reassuring them), Raw Confidence, Patience (treat every call as a full-length professional engagement, not a rushed transaction), Straight-Line discipline (resist rapport tangents), Reframing (mirror back understanding), Ego-Evasion questioning (undermine beliefs via questions, not direct challenge), Diagnose-not-Close, "OK" as a neutral acknowledgment, and a preference for audio-only over video calls.

### 6. What the Reviews/Logs Reveal

The individual "Cold Call Review" entries (4/14–4/27) are strikingly repetitive given they span two weeks: nearly every session's #1 flagged issue is **upward inflection reading as uncertainty**, followed by **rushing/speaking too fast** (hypothesized as discomfort with silence and nerves), and **diminished authority framing** in the self-introduction. By 4/27–4/28 the review notes shrink to a single line each ("inflections not placed at the right time... just not aware, maybe nervous"), suggesting either diminishing new insight from the review process or reviewer fatigue — worth flagging since the review template explicitly caps actionables at 1–3 "specific and testable" items per the "Anti-Overthinking Rule," and recent reviews aren't hitting even that bar with much specificity.

The weekly analysis log (3/23–3/27, the one populated instance) shows a 184-call week with a 13.6% pickup rate, 60% DM-reach rate once picked up, 40% "good conversation" rate, and a 12% booking rate off answered calls — but only 1.6% of all dials converted to a booked call. Training-video takeaways for that week: stop pitching gatekeepers, slow down, speak louder/more confidently. The weekly-log *template* itself (the other instance) was never filled in, meaning most weeks in the corpus have no structured weekly retrospective — only the daily metrics-sheet rows and occasional single-day call reviews.

### 7. Metrics Signal

Reading the four monthly sheets together (Feb sheet actually spans Nov 2025–Feb 2026; only rows from late Feb 2026 onward carry a script-version label):

| Month | Total Calls | Pitches | Resonations | Booked | Booked ÷ Pitches |
|---|---|---|---|---|---|
| Feb 2026 (incl. pre-Feb data) | 1,459 | 85 | 8 | 1 | ~1.2% |
| Mar 2026 | 924 | 78 | 4 | 8 | ~10.3% (matches sheet's own "ABR = 10.26%") |
| Apr 2026 | 1,344 | 124 | 15 | 6 | ~4.8% (matches sheet's own "ABR = 4.84%") |
| Jul 2026 (2 days logged so far) | 30 | 1 | 0 | 0 | 0% (sample too small to read) |

The qualitative narrative across the notes docs is one of steady improvement (V.1.7 called a "major improvement," V.1.8/V.1.9 fixing authority framing, V.2.x adding personalization). The metrics only partly support that: **March 2026, running V.1.5–V.1.8, produced the best booking rate in the entire dataset (~10%) — more than double April's rate (~4.8%) despite April running the supposedly-improved V.1.9/V.2.1/V.2.2.** Call volume also dropped from March to April (924 → wait, actually April is higher at 1,344 vs March's 924) while conversion efficiency fell. July's data is far too sparse (2 sessions, 30 total dials, 1 pitch) to say anything about V.2.3's real performance yet — the newest and most-refined script version is, ironically, the least metrics-validated one in the whole corpus.

### 8. Open Questions / Gaps

- **March outperforms April despite "improved" scripts.** The single clearest metrics-vs-narrative contradiction in the corpus: booking rate roughly halved from March (V.1.5–V.1.8 era) to April (V.1.9–V.2.2 era) even though every notes doc in between describes changes as fixes/improvements (authority framing, growth-partner positioning). Worth asking Dylan whether this is small-sample noise, a seasonal/list-quality effect, or a real regression from the "growth partner" reframe before treating the current script lineage as strictly better than its predecessors.
- **V.2.3 is essentially unvalidated by metrics.** Only 2 days / 30 dials / 1 pitch logged in July. The insights doc (and any skill built from it) is currently treating V.2.3 as the reference implementation on the strength of its design logic (personalized opener) rather than performance data.
- **No "V.2.2" or "V.2.3" notes doc exists**, breaking the otherwise-consistent script-then-notes pairing pattern. The reasoning behind the V.2.3 personalization change and the V.2.2 experiment (tested only 2 days, then apparently abandoned back to V.2.1) is inferred, not documented.
- **Two near-duplicate "Pre Cold Calling Playbook" docs** (capitalized and lowercase title) exist with overlapping but not identical content — the lowercase one is shorter and reads like an earlier draft focused mainly on identity/visualization, missing the KPI/measurement and tactical-reminders sections of the fuller doc. Worth confirming which is canonical before the skill cites it, and archiving/deleting the other.
- **Two "Cold Call Review" template docs are essentially blank forms** (the generic "Cold Call Review" and the "Cold Call Review Template" variant), while the dated instances (4/15, 4/16, 4/27, 4/28) are filled copies of the same template. Only the blank templates and 4 dated instances survive in Drive — no reviews are logged for the V.2.2/V.2.3 period, meaning the most recent script has no documented call-review feedback loop at all.
- **The weekly analysis log is mostly unused.** Only one of two weekly-log instances (3/23–3/27) was ever filled in; the practice of weekly retrospectives (pickup rate, DM-reach rate, good-conversation rate, etc.) appears to have lapsed in favor of just the daily metrics-sheet rows, which don't capture some of the richer weekly categories (e.g., "good conversation rate," "new objections noticed").
- **Sales-side metrics are entirely empty.** Every monthly sheet has "Sales Calls Done," "Sales," and "Sales $" columns that are 0/blank across all four months — meaning this entire corpus documents the *booking* funnel only. There's no visibility yet into whether booked appointments are converting to actual sales, which is a real gap if the skill is meant to optimize for revenue outcomes rather than just booked-call volume.
- **The Synthesis AI voice agent script and the Free Offer Script (V.1.1)** are adjacent-but-different offers/ICPs mixed into the same Drive folder as the core training-facility script lineage. They're useful as pattern-generalization evidence (Section 3) but should probably be explicitly excluded as source material if the skill is scoped specifically to the DigiGrowth training-facility cold-calling motion, to avoid the skill accidentally blending offers.
- **The stated psychological-lever list in the V.1 Construction doc (25+ biases) is far richer than what's actually visible in use in V.2.3.** Only a handful (curiosity, zero-risk, reciprocity-adjacent framing, permission-based mis-influence) are clearly still active in the current script; most of the catalogued biases (rhyme-as-reason, humor bias, trend bias, disqualified-identity bias, etc.) don't appear applied anywhere in the later scripts or notes. Worth deciding whether that list is an aspirational reference to mine further or largely superseded.
