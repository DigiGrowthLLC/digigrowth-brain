---
name: cold-email
description: Create and iterate cold email outreach campaigns that book appointments — new campaigns, subject lines, touch-by-touch sequences, A/B variants, and data-driven rewrites of the live Email Handoff sequence — for DigiGrowth or client businesses, modeled on a proven 'On'/'Off' framework swipe file.
---

# Cold Email Skill

Write, test, and iterate cold outreach emails whose only job is to **book a call**. Works for
DigiGrowth itself or a client business (same any-business scope as the rest of `copy-agent`).

Sources:
- `references/swipe-file.md` — Dylan's proven 'On'/'Off' framework cold emails, subject-line
  formulas, and the distilled patterns behind them. **Read it before drafting anything.** It holds
  the structural models; this file holds the rules for adapting them.
- `../offer/SKILL.md` and `outputs/offer-*.md` — the offer being pitched. A cold email is only as
  strong as its offer; if there's no clear offer for this business/niche yet, build one with the
  `offer` skill first.

## Trigger

Use this skill when Dylan asks to:
- Write a new cold email campaign/sequence (any niche, DigiGrowth or a client)
- Rewrite or improve the live **Email Handoff** sequence in the dashboard
- Generate subject lines, openers, P.S. lines, or A/B variants
- Diagnose why a campaign isn't getting opens/replies/bookings and fix the copy
- Adapt a swipe-file email to a specific niche or offer

For appointment *lifecycle* messaging (reminders, no-shows, cancellations), use
`outbound-sequences` instead — this skill is for getting the first "yes, let's talk."

## Ground truth: the live Email Handoff engine

DigiGrowth's automated cold email runs through the **Email Handoff** sequence
(`dashboard/backend/email_handoff_sequence.py`). Copy for it must fit these real mechanics:

| Fact | Detail |
|---|---|
| Who gets it | SMS prospects whose first text went out 3+ days ago with **zero** SMS reply (auto trigger: `email_followup_trigger.py`), or anyone Dylan manually adds/sets to "email-handoff". So the reader has already ignored a text from us. |
| Touches | **3, fixed.** Touch 1 = 24h after enrollment · Touch 2 = 48h after Touch 1 · Touch 3 = 4 days after Touch 2. Campaign-wide, sends go out one at a time at least 10 minutes apart, so a touch can land a bit after its due time. |
| Stops on | Any real reply (out-of-office auto-replies don't count), unsubscribe, or manual removal. Every touch must stand alone. |
| Merge fields | `{first_name}` (from contact owner), `{full_name}` (owner's full name, falls back to business name), `{business}`, `{link}` (Calendly URL), `{loom}` (the prospect's personalized video watch link, generated server-side at enrollment by `dashboard/backend/outreach_video.py`). All work in subjects and bodies. **Nothing else resolves** — no `{city}`, `{niche}`, `{result}`. |
| Format | Plain text body; the system auto-wraps an HTML copy with an open-tracking pixel and **auto-appends an unsubscribe footer**. Don't write your own unsubscribe line or signature block links. |
| Sender | Rotating cold mailboxes on `mail.`/`info.digigrowthllc.com` (Google/Microsoft), ~20 sends/mailbox/day. Replies land in the dashboard Inbox and get forwarded to Dylan's main inbox. |
| Where it's edited | Business Resources → Outreach Templates → **Email Handoff (Email)** → Touch 1/2/3 subject + body. That editor also has **View Active Prospects** and **View Warm-Up Status**. |
| Metrics | `GET /api/analytics/outreach?days=N` → `email_handoff` (enrolled, touch1-3 sent, opened, open_rate, replied, reply_rate) and `email` (Touch 1 counts as Sent/Open Rate there). |

**Implications for copy:**
- The swipe file's `(LOOM)` slot maps to `{loom}`: a real per-prospect video (Dylan's fixed
  headcam pitch as a bubble over a screenshot of *their* website; headcam-only if no site is on
  file). Frame it honestly: "I made you a quick video on {business}'s site" is true of what they'll
  see; don't claim it was recorded live, one-off, just for them.
- `{loom}` + `{link}` in one email = two links. For Touch 1 prefer `{loom}` alone with a reply-based
  ask, and move `{link}` to Touch 2/3.
- `(NICHE)`, `(RESULT)`, `(AVATAR)`, `(CITY)` can't be merged — write them into the template as
  literal text for the niche the sequence is aimed at (currently physical therapy practices).
- Touch 1 should acknowledge the channel switch lightly (they were texted first) without guilt.
- For a campaign that will NOT run through Email Handoff (a client's own tool, a manual send, a new
  engine), you can use any placeholders — just list them at the top of the output file.

## Adapting the swipe file — non-negotiables

The swipe file is someone else's agency's emails. Before any line goes out as DigiGrowth:

1. **No borrowed proof.** Never reuse the source author's client names, member counts, "300+ gyms", "107,648 leads", "$6.72M", "100+ owners", etc. Use only DigiGrowth's real results (ask Dylan,
   or check `media-buying-agent/clients/<slug>/` and the offer files — first-name-only attribution
   per the media-buying convention). **If there's no real number yet, don't invent one** — use the
   current offer's honest framing instead (e.g. the PT case-study cohort: free management in
   exchange for a testimonial) or a capability claim without a stat.
2. **No false "I'm not automated" claims.** The Email Handoff sequence *is* automated, so lines like "this isn't an automated message", "I send these all personally", "not blasting you from software", and a fake "Sent from my iPhone" are untrue — and they backfire when a prospect sees Touch 2 arrive on schedule. Keep the *human* signal with true statements: "I'm a real person and I read every reply myself", "reply here and it comes straight to me", a specific observation about their business. (These lines are fine only for a genuinely one-to-one manual send.)
3. **Conditional angles must be real.** Off 5.0 ("we have inquiries in your city with nowhere to send them") only if a live campaign actually is producing unrouted leads there. Off 6.0 ("my research team saw something concerning") only when it names a specific real finding.
4. **Guarantee wording must match the actual offer.** "Pay on results" / "if we don't deliver, you don't pay" only if the offer being pitched really works that way — check the offer file; don't promise a guarantee DigiGrowth doesn't honor.

## Deliverability rules (new cold mailboxes)

These mailboxes are young; copy choices affect whether mail lands in the inbox at all.
- **At most one link per email** (usually `{link}`), and zero in Touch 1 is often better — a reply-to-this question ("worth a look?") outperforms a link on a cold first touch and protects reputation.
- No images or attachments, and no formatting beyond line breaks.
- Keep Touch 1 short — **50-125 words**; follow-ups shorter (30-80).
- Avoid spam-trigger clusters: stacked "FREE", "100%", "guarantee", "$$$", ALL CAPS, multiple "!!!". One plain mention of the guarantee is fine; three in one email isn't.
- Subject lines: 2-6 words, lowercase-ish, look 1:1 (swipe formulas: "quick question, {business}", "question for {first_name}"). No emoji, no "RE:" fakery on a first touch.
- Vary wording touch-to-touch — identical phrasing across a sequence hurts both reply rate and filtering.

## Sequence architecture (3 touches)

Default mapping of the swipe-file patterns onto the 3 Email Handoff slots:

| Touch | Job | Draw from |
|---|---|---|
| 1 | Compliment + one concrete outcome + risk reversal + one low-friction question | On 2.0 (compressed), Off 3.0 capacity question |
| 2 | New angle, not a repeat: proof, a specific observation, or "how it works" in 2 lines + `{link}` | On 1.0/3.0 proof paragraph, Off 2.0 |
| 3 | Soft close-the-loop: easy yes/no, no guilt, door left open | Off 3.0 style, P.S.-style restatement |

Later touches soften, never escalate. Each must make sense read alone.

## Workflow

### A. New campaign
1. **Clarify**: business (DigiGrowth or client), niche + avatar, the offer (find/confirm its file), real proof available, and delivery (Email Handoff engine vs. elsewhere).
2. **Pick 2 frameworks** from the swipe file that fit the offer (e.g. risk-reversal-led → On 2.0; demand-led → Off 3.0) and say why.
3. **Draft** Touch 1-3 (subject + body each) with the adaptation and deliverability rules applied. Write a **variant B for Touch 1** (different framework or subject) so there's something to test.
4. **Self-check** each email against: word count, link count, merge fields that actually resolve, no borrowed proof, no false "not automated" claims, one CTA.
5. **Save** (see Output) and tell Dylan where each touch goes in the dashboard.

### B. Iterate the live sequence
1. **Pull current state** — live templates and metrics, using `doppler run` so the password never appears in the command (see memory `dashboard-api-credential-access`):
   ```bash
   doppler run --project digigrowth --config prd -- bash -c \
     'curl -s -u "admin:$DASHBOARD_PASSWORD" "$DASHBOARD_URL/api/dialer/email-handoff-template";
      curl -s -u "admin:$DASHBOARD_PASSWORD" "$DASHBOARD_URL/api/analytics/outreach?days=30"'
   ```
   Also skim real replies in the Inbox if the question is "why are replies negative/confused?".
2. **Diagnose by metric** (only once there are ~30+ sends; below that, say the sample is too small):
   - Low **open rate** (< ~30%) → subject line and/or deliverability (check bounce rate, warm-up status) — not the body.
   - OK opens, low **reply rate** (< ~2-3%) → Touch 1 body: offer clarity, relevance, ask friction.
   - Replies but few **bookings** → the ask/offer or the reply handling, not the cold copy.
   - Opens are approximate (Apple Mail prefetch is filtered by a 2-minute rule; many clients block pixels) — use them directionally.
3. **Change one variable at a time** (subject OR opener OR CTA) so the next read is attributable. Bump the version (v1.0 → v1.1 for tweaks, v2.0 for a new framework).
4. **Save** the new version with a short "what changed & why / metric it targets" note.
5. **Pushing live**: the templates auto-send to real prospects, so **never PUT to `/api/dialer/email-handoff-template` without Dylan's explicit go-ahead** on the final text. Default is to give him the text to paste into the Outreach Templates editor. If he approves a push, PUT only the keys being changed (`email_handoff_touch{1,2,3}_{subject,body}`) and re-GET to confirm.

## Output

Save to `outputs/cold-email-[business-or-niche]-v[X.Y]-YYYY-MM-DD.md`:

```md
# Cold Email — [Business/Niche] v1.0
Delivery: Email Handoff engine (merge fields: {first_name}, {full_name}, {business}, {link}, {loom}) | or: [other]
Offer: outputs/offer-....md · Frameworks used: On 2.0 (T1), Off 2.0 (T2)
Change log: v1.0 — initial

## Touch 1 — 24h after enrollment
**Subject:** ...
**Body:**
...
_(words: N · links: N)_

## Touch 1 — Variant B
...

## Touch 2 — +48h
...

## Touch 3 — +4 days
...

## Paste-in map
Business Resources → Outreach Templates → Email Handoff (Email) → Touch 1 Subject / Body ...
```

Confirm what was saved and where, per `copy-agent` convention.

## Reminders

- Read `references/swipe-file.md` first; model its structure, not its claims.
- Only `{first_name}`, `{full_name}`, `{business}`, `{link}`, `{loom}` resolve in the live engine.
- Never borrow the swipe file's results or client names; never invent stats.
- No "this isn't automated" / "Sent from my iPhone" lines on automated sends.
- One link max, short bodies, one CTA, softening across touches, each touch standalone.
- Iterate from real metrics, one variable at a time, versioned — and never push live templates without Dylan's approval.
