# Newsletter

Generates DigiGrowth's AI-tip email for contacts flagged `newsletter` in the DigiGrowth OS CRM. Draft runs Monday and Friday as part of the morning briefing.

**Brand framework — "The AI Growth Loop":** DigiGrowth's methodology has a name, reused consistently across every email so recipients start to recognize it as a system, not a one-off tip (same device as "Golden Pillars" / "Gym Growth Accelerator" in the direct-response swipe file this format was modeled on — see "Design Notes" at the bottom). If Dylan wants a different name, swap it here and in Step 3 below — it's referenced in one place conceptually but used in the body text of every email, so keep it findable.

**Run manually:** Ask the EA to "draft the newsletter." The EA delegates here via `manage-apptset-agent`.
**Scheduled (draft):** Runs automatically Monday/Friday as part of the daily briefing (Step 4.5). Each day picks its own topic from the rotation — not the same draft twice.
**Sending is live**, via Gmail API (`dylanrg@digigrowthllc.com`) — not a single blast. Approving the
draft queues one personalized email per newsletter-flagged contact, and a scheduled backend job
sends them gradually (~25/day cap, small batches every ~25 min during business hours) to protect the
sending mailbox's domain reputation. See "Delivery" below.

---

## What This Skill Does

1. Picks this week's topic from a rotating list of AI client acquisition tips for independent service-based businesses
2. Runs one web search on that topic and caches the findings (`weekly_research_cache.json`) — `content-agent`'s `weekly-ai-blog` skill reads this cache when it's fresh (same day), saving a second search. Since the blog now runs Wednesdays and this runs Monday/Friday, that overlap is rare — the blog does its own research most weeks now
3. Generates a personalized email draft (uses `{{first_name}}` and `{{business_name}}` placeholders)
4. Saves the draft to `newsletter_draft.json` for the Python send script
5. Renders the draft as a PDF and posts it inline in the OS chat, linked from that day's daily brief
6. Submits the draft for approval via the dashboard's approvals API, so Dylan gets a live Approve/Decline control in chat
7. On Approve: the backend queues one personalized email per newsletter-flagged contact and sends them gradually (~25/day, small batches through the day) via Gmail API — see "Delivery" below. `newsletter.py` is legacy and unused; ignore it.

---

## Instructions

Execute without asking for confirmation. Do not advise — just execute and report.

Resolve paths dynamically — do not hardcode any absolute paths. Run this first to get the repo root:
```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
```
Then use:
- apptset-agent dir: `$REPO_ROOT/apptset-agent`
- config: `$REPO_ROOT/apptset-agent/config.json`
- draft file: `$REPO_ROOT/apptset-agent/newsletter_draft.json`
- topic log: `$REPO_ROOT/apptset-agent/newsletter_topic_log.json`

---

## Draft Mode

Run when delegated by the EA's `manage-apptset-agent` skill, or when Dylan says "draft the newsletter."

### Step 1 — Pick this week's topic and mode

Read `newsletter_topic_log.json`. If the file doesn't exist, treat it as an empty array `[]`.

Compare the log against the topic list below. Pick the **first topic not used in the last 20 entries**. If all 20 have been used recently, restart from topic 01.

**Also pick this week's mode** — which structural element gets the most emphasis in Step 3, so weeks read as genuinely different angles rather than one template with the topic swapped out. Cycle through in order, using whatever `mode` the most recent log entry recorded (if the log is empty or has no `mode` field yet, start at `tip-led`):

1. `tip-led` — today's default: one actionable insight, light reframe, light proof
2. `proof-story-led` — the anonymized proof story (Step 3, part 3) is the centerpiece; everything else stays short
3. `reframe-led` — the us-vs-them contrast (Step 3, part 2) is the centerpiece
4. `objection-led` — open with the soft qualifier / a common reason prospects hesitate, then resolve it into the CTA

After `objection-led`, cycle back to `tip-led`.

### Step 1.5 — Research this week's topic (shared with the blog post)

Do **one web search** on this week's topic (e.g. "AI lead follow-up automation small business 2026 statistics") to ground the email in real, current data instead of writing from memory alone. Pull 2-4 concrete facts/stats, each with its source URL.

**Verify before caching.** Fetch each candidate source URL and confirm the specific claim actually appears there (in substance — doesn't need to be verbatim). Drop any stat you can't confirm on the page itself; don't keep a stat just because it sounds plausible or was easy to find in a search snippet. If a dropped stat leaves you short, run one more targeted search to replace it rather than falling back to an unconfirmed number. This step exists because unverified stats have shipped in past drafts (traced back to sources that didn't actually contain the claim) — since Step 3 below now builds a proof narrative around these stats, an unconfirmed one is a real credibility/trust risk, not just a minor inaccuracy.

Save the verified findings to `apptset-agent/weekly_research_cache.json`:
```json
{
  "date": "YYYY-MM-DD",
  "topic": "topic text from Step 1",
  "findings": ["concrete fact or stat", "..."],
  "sources": ["https://...", "..."]
}
```
Overwrite any existing file — always use this week's fresh research. `content-agent`'s `weekly-ai-blog` skill reads this same file when it's still fresh (same-day) — since the blog now runs Wednesdays, that only lines up if this happens to be a Wednesday run; otherwise the blog does its own research.

If the search turns up nothing useful for this topic, write `findings: []` and continue — Step 3 falls back to writing from general knowledge for this week only.

**Swipe file tip:** if Dylan wants a second research pass beyond the web search, other AI/service-
business newsletters are useful inspiration for angle and structure (not content to copy) — this
isn't part of the automated flow, just worth knowing as an option if a topic feels thin.

### Step 2 — Get recipient list

`read_file` on `apptset-agent/newsletter_recipients.json` (repo-relative, already pulled by this run's guard step). It's exported nightly by Railway from the DigiGrowth OS CRM (`contacts` table, `newsletter = true`) — see `dashboard/backend/main.py`'s `_export_newsletter_contacts` job — so no live API call is needed here.

Format:
```json
{
  "count": 12,
  "recipients": [{"owner": "...", "business": "...", "email": "..."}, ...],
  "exported_at": "2026-07-21T09:45:00+00:00"
}
```

Store `count` and the `owner`/`business` pairs for use in Step 5.

If the file doesn't exist or fails to parse, set count to "unknown" and list to empty. Continue.

### Step 3 — Generate this week's email

Write the email yourself — do not delegate to newsletter.py for generation. Use the topic from Step 1 as the core insight, grounded in the findings saved in Step 1.5 — reference at least one concrete fact/stat from `weekly_research_cache.json` instead of writing purely from memory.

**Subject:** Specific and curiosity-driven. Under 60 characters. No spam words (free, win, guarantee, etc.). Reference the topic concretely. **Prefer a concrete number when this week's verified research supports one** (e.g. "The stat behind 40% more bookings" beats "Why bookings are slipping") — numbers read as more credible and scannable than adjectives. Fall back to plain curiosity-driven phrasing on weeks where no clean number fits naturally; don't force one in.

**HTML body requirements:**
- Self-contained fragment (no `<!DOCTYPE>`, no `<html>`/`<head>`)
- Centered div, max-width 600px, font-family sans-serif, line-height 1.6, inline styles
- Use `{{first_name}}` where you'd address them by name (replaced per contact at send time)
- Use `{{business_name}}` where you'd reference their studio (replaced per contact at send time)
- Use `{{unsubscribe_link}}` as the `href` of a real unsubscribe link in the footer (replaced per
  contact with a working one-click unsubscribe URL when queued — see Step 6). Do NOT write "Reply
  STOP to unsubscribe" — that's an SMS convention and does nothing on email.
- **Use HTML entities for all non-ASCII characters** — never paste raw Unicode. Em dash → `&mdash;`, smart quotes → `&ldquo;` / `&rdquo;`, apostrophe → `&#39;` or `&apos;`. This prevents garbled symbols (â€") when an email client renders the HTML.
- **Line rhythm — one thought per `<p>` block, not dense paragraphs.** This is the swipe file's most distinctive formatting trait (see "Design Notes") and applies throughout every part of the Email structure below: most `<p>` blocks are a single sentence, sometimes a fragment. Multi-clause sentences get split across separate `<p>` blocks rather than staying joined. Use a short transitional beat as its own isolated `<p>` block to control pacing and let the next line land — `But…`, `Here's the thing…`, `Look…`, `So…`, `Now…` — don't chain these into the sentence before or after them. A short rhetorical question is usually its own line too. Every `<p>` tag must have `style="margin:0;"` and be followed by a `<br>` tag before the next one — do NOT rely on CSS margin/padding, email clients collapse it, and do NOT group multiple sentences into one `<p>` by default. This is about giving each thought room for a skimmer's eye to catch it, not about padding length — the email should still read in well under 90 seconds, since white space reads fast even when the block looks long scrolled.

  Example — same content, dense (avoid) vs. line-broken (use):

  Dense: *"Most businesses only answer DMs when someone happens to be at their desk — and by the time they reply, the lead has already messaged three other options. An AI chatbot changes that: it answers instantly, qualifies the lead, and books the call straight onto your calendar."*

  Line-broken:
  `<p style="margin:0;">Most businesses only answer DMs when someone happens to be at their desk.</p><br>`
  `<p style="margin:0;">By the time they reply, the lead's already messaged three other options.</p><br>`
  `<p style="margin:0;">An AI chatbot changes that.</p><br>`
  `<p style="margin:0;">It answers instantly. Qualifies the lead. Books the call — straight onto your calendar.</p><br>`
- **Bold key phrases:** wrap the most important stats, numbers, and action phrases in `<strong>` tags so readers scanning quickly know what matters. Aim for 4-7 bolded phrases per email (e.g. response time stats, sequence steps, outcome metrics, the core benefit).

**Email structure** (weight each part per this week's mode from Step 1 — the centerpiece part gets more room, the rest stay short; all parts are still present every week for consistency):

1. **Pattern-interrupt open** — `Hey {{first_name}},` then 1-2 sentences that don't just state a pain point flatly but hook attention: a contrarian claim, a surprising stat, or a one-line "confession." Rotate the exact phrasing week to week — don't reuse the same opening sentence shape every time.
2. **Reframe** (centerpiece on `reframe-led` weeks) — one short beat contrasting the old way (manual follow-up, generic marketing agency, DIY guesswork) with The AI Growth Loop's way. This is implicit objection-handling, not a hard sell — a sentence or two, not a paragraph.
3. **Proof-as-story** (centerpiece on `proof-story-led` weeks) — the verified stat(s) from `weekly_research_cache.json`, written as a short anonymized narrative ("One [industry] business did X, in Y timeframe...") rather than a flat stat dump. Break the narrative across several one-thought `<p>` lines per the line-rhythm rule above, rather than one dense paragraph — that's what keeps a "story" feeling like pacing instead of a stat block. Never name a specific DigiGrowth client or invent a testimonial — DigiGrowth doesn't have a case-study library yet, so proof stays third-party/industry-sourced and clearly framed that way.
4. **Soft qualifier** (centerpiece on `objection-led` weeks, where it can move earlier and expand slightly) — one line signaling this isn't generic advice for everyone, e.g. "This works best for businesses that book 1:1 appointments — if that's not you, skip this one." Increases trust via selectivity. Must be a true, reasonable qualifier — never a fabricated one used just for effect.
5. **CTA**: "Want me to put together a custom AI + marketing plan for {{business_name}}? Book a quick discovery call — [booking_link from config]" — tie it back to The AI Growth Loop by name so the framework and the offer feel connected.
6. Casual sign-off from "Dylan | Digigrowth"
7. **P.S. line** — one line reinforcing the CTA or handling one likely objection (e.g. "P.S. — this isn't a sales pitch, just 20 minutes to see if it's a fit."). Do not restate or link the CTA a second time here — see "One CTA, said once" below; the P.S. supports the ask, it doesn't repeat it.
8. Footer (required, CAN-SPAM): a real `<a href="{{unsubscribe_link}}">Unsubscribe</a>` link, plus
   the mailing address from `config.json` → `newsletter.mailing_address` if set. If that field is
   empty, still include the unsubscribe link but flag to Dylan in your summary that the mailing
   address needs to be added before this is fully compliant — don't invent an address.

**No fabricated pressure.** Don't invent urgency ("only 3 spots left this week"), scarcity, or disqualifying claims that aren't true. The direct-response swipe file this format draws from uses aggressive versions of these on a cold list at volume; DigiGrowth's list is opt-in and warm, so invented pressure is a credibility risk, not a conversion win. Every claim — proof stat, qualifier, urgency — must be genuinely true, not just persuasive-sounding.

**Copywriting discipline** (from DigiGrowth's newsletter playbook):
- Short, punchy sentences, one thought per line — see "Line rhythm" under HTML body requirements
  above; it applies to all 8 parts below, not just the opener. Less is more — cut anything that
  isn't the pain point, the insight, or the CTA.
- A numbered/bulleted list is fine if it genuinely aids scanning (e.g. a 3-step workflow) — don't
  force one in every email.
- **One CTA, said once.** Don't repeat the booking link or stack a second ask — that's the same
  one-primary-CTA principle the blog uses.
- Don't over-polish. A newsletter that took 20-30 minutes to write usually reads more natural and
  performs better than one that's been agonized over — write it, check it against the requirements
  above, ship it. This is a rep you're building, not a single perfect artifact.
- **Consistent identity, varied emphasis**: same fonts, same 8-part skeleton, same voice, same
  framework name (The AI Growth Loop) every week — recipients should recognize a DigiGrowth email
  before they read the subject line. The week's `mode` (Step 1) changes which part gets the most
  room, not the underlying format.

**Tone:** Direct, friendly, trusted expert who knows AI and service-based business marketing. No hype. No buzzwords. Under 90 seconds to read.

**On cadence:** drafts Monday/Friday (Dylan's explicit choice). Each day is its own topic pick from
the rotation, not a repeat. This does **not** change per-contact send frequency by fiat — every
draft still goes through its own approval (Approve/Decline), so nothing sends without Dylan
reviewing it each time. The throttled delivery mechanism (`process_newsletter_queue()`, ~25/day cap)
still governs actual sending regardless of how many drafts get approved in a week — it doesn't need
to change for this. If the contact list grows large, 2x/week approvals means 2x the monthly volume
per contact — worth keeping an eye on engagement (see Tracking below) as the list grows, since
that's the tradeoff of higher frequency.

### Step 4 — Save draft

Read `config.json` → `newsletter.booking_link`. Replace `[booking_link from config]` in the HTML with the actual URL before saving.

Write the draft to `newsletter_draft.json`:
```json
{
  "subject": "...",
  "html": "..."
}
```

Append the used topic and mode to `newsletter_topic_log.json`:
```json
[
  {"topic": "topic text here", "mode": "tip-led", "date": "YYYY-MM-DD"},
  ...
]
```
If the file doesn't exist, create it with a single-item array. Older entries without a `mode` field are expected — Step 1's cycle just treats a missing `mode` on the most recent entry as if it were `objection-led` (so the next pick is `tip-led`).

### Step 5 — Save the draft markdown

Build a Markdown review document with this exact structure:

````
# Newsletter Draft — [Month Date, Year]

Review this draft. Approving it queues a personalized send to every contact flagged `newsletter` —
delivered gradually (~25/day), not all at once. See "Delivery" below.

## Subject

[subject]

## Recipients

| Name | Business |
| --- | --- |
| ... one row per contact from Step 2, "—" if business is blank ... |

[N] contacts flagged `newsletter` in the DigiGrowth OS

## Topic this week

[topic from Step 1] — mode: [mode from Step 1]

---

## Email Preview

[opening line]

[each body paragraph, one per line]

[CTA line]

[sign-off]

[P.S. line]

---

## HTML Source

```html
[the full raw HTML]
```
````

Save this document to `apptset-agent/newsletter-draft-YYYY-MM-DD.md` (today's date). Overwrite any existing file with today's date.

Push it (the repo is ephemeral on Railway — use `push_file()` from `shared/github_sync.py`, or `git add`/`commit`/`push` directly if running with git access):
- `apptset-agent/newsletter-draft-YYYY-MM-DD.md`

Do not attempt to generate the PDF here or call any Railway API — this session's sandbox can't reach Railway directly. A Railway-side job (`pending_approvals_relay.py`, polled ~6:40am ET daily) picks up the request written in Step 6 below, renders the PDF from this `.md` file, and posts the live PDF preview + Approve/Decline card into the OS chat on its own.

### Step 6 — Drop a pending-approval request

Instead of calling the dashboard's approvals API directly (this sandbox can't reach Railway), write a request file that the Railway-side relay job picks up on its next poll and turns into a real Approve/Decline card — **with the actual draft content attached**, so Dylan can read the full email before deciding, not just a title and topic line.

**Include `subject` and `html` in the payload** (the same values just saved to `newsletter_draft.json`) — the dashboard's Approval card renders `payload.html` inline as the draft preview. Omitting them means Dylan sees an empty preview and has to approve blind — always include them.

Write the file directly rather than inlining it in a shell one-liner — the HTML contains quotes and apostrophes that are painful and error-prone to shell-escape inline:

```bash
mkdir -p apptset-agent/pending_approvals
cat > apptset-agent/pending_approvals/newsletter-YYYY-MM-DD.json <<'JSONEOF'
{
  "title": "[subject]",
  "summary": "[topic] — [N] recipients",
  "payload": {
    "date": "YYYY-MM-DD",
    "subject": "[subject]",
    "html": "[the full HTML email body, JSON-escaped]"
  }
}
JSONEOF
```

Push `apptset-agent/pending_approvals/newsletter-YYYY-MM-DD.json` with `push_file()`, same as Step 5.

Return this summary for the daily brief:

```
**Subject:** [subject]
**To:** [N] contacts flagged `newsletter` in the DigiGrowth OS
**Topic:** [topic]
**Note:** Approving queues a personalized send to every contact flagged `newsletter` in the OS. Delivery is gradual (~25/day cap, spread through business hours) to protect domain reputation — not an instant blast. The PDF preview and Approve/Decline card will appear as a separate message in this chat within a few minutes once Railway's relay job picks up this request — no marker to include here.
```

---

## Delivery — how sending actually works

Approving a newsletter approval (`kind: "newsletter"`) triggers `dashboard/backend/routers/approvals.py`'s `_enqueue_newsletter()`:
1. Reads every contact where `newsletter = true` directly from the OS CRM (live query, not the nightly-exported `newsletter_recipients.json` file — that file is only for this skill's own Step 2 preview).
2. Personalizes `{{first_name}}`, `{{business_name}}`, and `{{unsubscribe_link}}` per contact and inserts one row per contact into the `newsletter_send_queue` table. **Nothing is sent yet at this point.**
3. A scheduled job in `dashboard/backend/main.py` (`_process_newsletter_queue`, cron `*/25 9-17 * * mon-fri` ET) sends a small batch (4) off the queue via `integrations.gmail_send_html()` — real Gmail API send from `dylanrg@digigrowthllc.com` — capped at `NEWSLETTER_DAILY_CAP` (25) sends/day total. A big list spreads across multiple days automatically; it never blasts everything from a single approval.

`newsletter.py --send` is legacy — it used GoHighLevel, which is no longer in use. Ignore it; do not run `newsletter.py --send`.

If Dylan asks to check on send status: query `newsletter_send_queue` (status `queued`/`sent`/`failed`, `error` column has the failure reason if any).

**Before real prospect volume ramps up**, `config.json` → `newsletter.mailing_address` needs to be filled in for CAN-SPAM compliance — flag this if it's still empty and Dylan asks about sending to a real list.

---

## Tracking & Benchmarks

Gmail API sends (`gmail_send_html`) have **no built-in open/click tracking** — there's no pixel or
link-wrapping today, so open rate and clickthrough rate aren't measurable yet without adding that
instrumentation (not built — flag to Dylan if he asks for these numbers specifically).

What already IS trackable, and matters more anyway: **did the email generate a booked call.** Check
the CRM/dialer for discovery calls or bookings in the days after a send — that's the real signal,
not opens. If open/click tracking becomes a priority, industry benchmarks to compare against once
it exists: open rate ≥10% at 48 hours is the floor, 20-30%+ is good; clickthrough rate 0.5-3% is
typical.

## Repurposing

After a newsletter is approved and queued, offer to repurpose its core insight into a LinkedIn post
(`/social-post`) or ad angle (`/ad-copy`) — same "one idea, many formats" pattern used elsewhere in
content-agent. Not automatic; ask Dylan if he wants this for a given week's topic.

---

## Topic Rotation List

Pick in order, skipping topics used in the last 20 weeks. Cycle back to 01 when all are exhausted.

```
01. The AI follow-up sequence that books consultations while you sleep
02. How independent service-based businesses are using AI to turn cold leads into paying clients
03. The 3-message AI SMS flow that gets 40%+ reply rates
04. Why AI-powered "speed to lead" is the biggest revenue unlock for service-based businesses right now
05. How one service-based business added 20 new appointments/month with a single AI automation
06. The AI tool that writes every follow-up message so you never have to
07. How to use AI to reactivate your dead leads list (without lifting a finger)
08. The AI workflow that follows up with every no-show automatically
09. Why service-based businesses using AI outreach are booking 3x more discovery calls
10. How AI qualifies your leads before you ever pick up the phone
11. The AI-powered referral system that fills your pipeline on autopilot
12. How independent service-based businesses are using AI to cut their cost-per-lead in half
13. The AI chatbot that handles your DMs and books calls 24/7
14. How to use AI to turn your Google reviews into a lead generation machine
15. The AI sequence that turns website visitors into booked consultations
16. How AI helps service-based businesses personalize outreach at scale (without it feeling robotic)
17. The AI email strategy that keeps your brand top-of-mind with 500 leads at once
18. Why the service-based businesses winning right now all have one thing in common: AI automation
19. How to build an AI client acquisition system for under $500/month
20. The AI-powered onboarding flow that reduces no-shows by 30%
```

---

## Edge Cases

- **No contacts flagged `newsletter`:** Report "0 contacts flagged `newsletter` in the DigiGrowth OS — flag contacts in the CRM before drafting." Still save the draft.
- **`newsletter_recipients.json` missing or unparseable:** Note it in the saved draft markdown (count "unknown", empty recipient table). Still save the draft — this file is exported nightly by Railway, so a missing file usually means the export job hasn't run yet or failed; check Railway logs.
- **Draft already exists from this week:** Overwrite it. Always use the freshest draft.
- **Topic log is corrupted / unparseable:** Treat as empty, start from topic 01 and mode `tip-led`.
- **Mode field missing on old log entries:** Expected for entries written before this rotation existed — treat a missing `mode` on the latest entry as `objection-led` so the next pick lands on `tip-led`.

---

## Design Notes

The email structure, line rhythm/formatting, subject-line guidance, named framework, and mode rotation above were adapted from a direct-response cold-outreach swipe file (28 templates, a fitness-industry marketing consultancy's client-acquisition emails) at Dylan's request, to make DigiGrowth's newsletter more conversion-oriented. Two constraints carried over deliberately, because the swipe file's audience (cold prospects) and DigiGrowth's (an opt-in list of contacts already in the CRM) aren't the same:

- **No fabricated proof.** The swipe file's core engine is named-client case studies with specific numbers. DigiGrowth doesn't have a case-study library yet, so proof stays anonymized and industry-sourced — verified against its source (Step 1.5) — never a stand-in for a real DigiGrowth client result. Revisit this once real client outcomes exist to cite.
- **No fabricated urgency/scarcity/disqualifiers.** The swipe file uses these aggressively because it's cold outbound at volume, where some recipients bouncing off a hard qualifier is fine. On a warm opt-in list, an invented "only 3 spots left" or "unsubscribe if you're already successful" reads as manipulative to a recipient with a standing relationship — so this skill keeps the *structural* device (a soft qualifier line, a P.S. reinforcement) but requires every claim used to be genuinely true.

If engagement data (once tracking exists — see "Tracking & Benchmarks") shows a particular mode underperforming, that's the signal to revisit this structure, not a fixed schedule.
