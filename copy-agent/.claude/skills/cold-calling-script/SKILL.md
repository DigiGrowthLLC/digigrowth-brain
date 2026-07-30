# Cold Calling Script Skill

Build or iterate a cold calling script for any business, grounded in Dylan's own ~9 months of cold-calling framework, review data, and results (not just theory).
Sources:
- `references/insights.md` — a living document: an Update Log of new findings on top of a Baseline synthesized from Dylan's Google Drive (script version history, call reviews, rebuttal vault, playbooks, booking metrics) and the DigiGrowth OS dialer DB (live disposition breakdown + call notes, via the `os_dialer_disposition_breakdown` / `os_dialer_recent_notes` tools)
- `references/psychological-levers.md` — the original 27-item persuasion/bias reference list from the V.1 script construction doc

---

## Trigger

Use this skill when Dylan asks to:
- Build a new cold calling script from scratch for a business (his own or a client's)
- Revise, tighten, or re-version an existing script
- Get help with a specific beat (opener, objection handling, close) rather than a full script
- Diagnose why a script isn't converting

## Core Principles

These are durable — they hold regardless of which script version is current. See `references/insights.md` §2 for full detail.

**Prime Directive: Consistency.** Outreach has a 2–4 week lag before results show. Don't judge a script off a few days of data.

**The 4 Pillars:**
1. **Volume** — the #1 lever. More reps > better wording.
2. **Follow-up** — cold replies after 2–3 touches, warm bookings after 5–8. Persistence is professionalism.
3. **Result, not Process** — sell the destination, keep the "how" vague. Over-explaining kills curiosity.
4. **Offer** — a stronger offer beats a stronger script. Never give pricing/mechanics on the call — the only job of the call is to book the meeting.

**Lock & Key Theory.** Match the prospect's tone, pace, and mindset rather than forcing a fixed reading.

**Vocal delivery matters as much as wording.** Pitch (lower = authority), pace (slow = confident), pauses (silence = control), inflection (downward on statements = certainty, upward only on genuine questions). Dylan's own call reviews flag upward inflection on statements and rushed pacing as his most persistent execution issues — when iterating, don't assume a flat call rate means the script is wrong; it might be delivery.

**Execution habits:** pattern interrupt in the opener (don't sound like a salesperson), don't pitch in the first 10 seconds (buy attention first), objections = Agree → Reframe → Redirect (never defend), end strong (explicit confirmation, no "let me know" softness).

## Script Anatomy

Every full script in the corpus (V.1.1 through V.2.3) follows the same five-beat shape — use it as the skeleton for new scripts, adapting the specifics to the business:

1. **Opener (permission-based, disarming).** Confirm identity, name yourself, ask permission for a short amount of time, explicitly invite them to hang up if irrelevant.
2. **Credibility / value frame with concrete numbers.** A specific, quantified outcome band tied to a believable mechanism — credible enough to be curious about, not fully justified.
3. **Curiosity-gap process explanation.** When asked "how does it work," give a legitimate-sounding but deliberately incomplete answer. This is Pillar 3 (Result not Process) operationalized.
4. **Booking ask.** Direct, assumptive close, immediately followed by "got your calendar on you."
5. **Pre-frame / Ben-Franklin-style close.** A mutual "can we agree on a couple things" exchange once a time is booked, ending in an explicit cancellation pre-handle. This is the most stable, least-revised beat across every version in the corpus — worth keeping close to verbatim.

**Important caveat — do not treat the newest script version as automatically the best one.** The metrics tell a more complicated story than the version history does: March 2026 (running an earlier script) had roughly double April 2026's booking rate, even though the changes in between were framed as improvements. V.2.3, the current script, has almost no call volume behind it yet. When iterating, check `references/insights.md` §7 (Metrics Signal) and ask Dylan for current numbers before assuming a later version outperforms an earlier one — attribute results to data, not version number.

## Objection Handling

Pattern: **Agree → Reframe → Redirect.** Never defend a position; diagnose rather than argue. See `references/insights.md` §5 for the full rebuttal-vault breakdown by objection type (not interested / what is this / busy / booked up / send an email / not enough staff / already doing marketing / already have an agency) and the Sales Arsenal's underlying technique library (silence, non-judgement, never-solve, straight-line discipline, ego-evasion questioning).

## Persuasion Lever Library

`references/psychological-levers.md` holds the original 27 named cognitive biases/persuasion levers (curiosity tendency, zero-risk bias, reciprocation, Ben Franklin effect, disqualified identity bias, etc.) with definitions and cold-call examples. Not all of them are used in the current script — most aren't. Treat this as a reference shelf to pull from when a script needs a new angle or when testing a fresh persuasion technique, not a checklist every script must satisfy.

## Workflow

1. **Gather context.** Which business is this for (DigiGrowth or a client)? What's the ICP, the core pain point, the offer, and the concrete outcome numbers (LTV, close rate, results range) that can credibly anchor beat 2? If iterating an existing script, ask what specifically isn't working (which beat, or delivery vs. wording) and pull current booking-rate data if Dylan has it.
2. **Draft using the five-beat anatomy**, applying the Core Principles and pulling from the Persuasion Lever Library where a beat needs sharpening.
3. **Version and save.** Follow Dylan's existing Drive convention, adapted to `outputs/`:
   - Script: `outputs/cold-calling-script-v[X.X]-[business-name]-YYYY-MM-DD.md`
   - Paired notes doc: `outputs/cold-calling-notes-v[X.X]-[business-name]-YYYY-MM-DD.md` — capture what changed from the prior version and *why*. The insights doc flagged that V.2.2 and V.2.3 both shipped without a paired notes doc, breaking the version-reasoning trail — don't repeat that gap.
   - Confirm what was saved and where, per copy-agent convention.
4. **Suggest a review checkpoint.** Recommend Dylan log call reviews against the new version once he's run it (mirroring the "Cold Call Review" template pattern), and check back on booking-rate metrics before calling the new version an improvement.

## Keeping This Current

This skill is meant to keep learning, not stay frozen at its 2026-07-30 baseline:

- **Reactive:** whenever Dylan shares new call notes, a new Drive doc, or a new insight in conversation — even in passing — append a dated entry to `references/insights.md`'s `## Update Log` right then, tagged `(Dylan, in conversation)`. Don't wait for the scheduled resync to catch it.
- **Scheduled:** a weekly automated resync (`executive-assistant/.claude/skills/cold-calling-resync/SKILL.md`) pulls fresh Drive docs, the current month's metrics sheet, and live OS dialer data (disposition breakdown + call notes) even when Dylan doesn't mention anything — it appends its own entries tagged `(automated resync)` and bumps the `Last resync` marker.
- **When building or iterating a script, check the Update Log's most recent entries first**, before leaning on the Baseline. An entry may supersede a stale number or contradict a stated principle — the Baseline itself already found that "improved" script versions (V.1.9–V.2.2) actually booked at less than half March's rate, so don't assume newer information is automatically better either; weigh it on the data.

## Reminders

- Volume and follow-up beat clever wording — don't over-index on script polish at the expense of call volume.
- Keep the offer vague on the call; the only goal is booking the meeting.
- Never defend an objection — agree, reframe, redirect.
- A newer version number is not evidence of a better script — check the data.
- End every close strong: explicit confirmation, no soft language.
