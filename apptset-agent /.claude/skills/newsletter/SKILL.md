# Newsletter

Generates and delivers DigiGrowth's weekly AI-tip email to GHL contacts tagged `newsletter`. Draft runs every Saturday as part of the morning briefing. Dylan reviews and manually triggers the send.

**Run manually:** Ask the EA to "draft the newsletter" or "send the newsletter." The EA delegates here via `manage-apptset-agent`.
**Scheduled (draft):** Runs automatically every Saturday as part of the daily briefing (Step 4.5).

---

## What This Skill Does

1. Picks this week's topic from a rotating list of AI client acquisition tips for fitness studios
2. Generates a personalized email draft (uses `{{first_name}}` and `{{business_name}}` placeholders)
3. Saves the draft to `newsletter_draft.json` for the Python send script
4. Creates a Notion preview page and links to it from Saturday's daily brief
5. On send trigger: runs `newsletter.py --send` which personalizes and delivers to every tagged contact

---

## Instructions

Execute without asking for confirmation. Do not advise — just execute and report.

The apptset-agent directory path is: `/Users/dylangroenendijk/digigrowth-brain/apptset-agent /`
The config is at: `/Users/dylangroenendijk/digigrowth-brain/apptset-agent /config.json`
The draft file is: `/Users/dylangroenendijk/digigrowth-brain/apptset-agent /newsletter_draft.json`
The topic log is: `/Users/dylangroenendijk/digigrowth-brain/apptset-agent /newsletter_topic_log.json`

---

## Draft Mode

Run when delegated by the EA's `manage-apptset-agent` skill, or when Dylan says "draft the newsletter."

### Step 1 — Pick this week's topic

Read `newsletter_topic_log.json`. If the file doesn't exist, treat it as an empty array `[]`.

Compare the log against the topic list below. Pick the **first topic not used in the last 20 entries**. If all 20 have been used recently, restart from topic 01.

### Step 2 — Get recipient count

Run:
```bash
cd "/Users/dylangroenendijk/digigrowth-brain/apptset-agent " && python -c "
import json, ghl
c = json.load(open('config.json'))
leads = ghl.get_newsletter_leads(c)
print(len(leads))
"
```

If the command fails (API error, no env vars), set count to "unknown" and continue.

### Step 3 — Generate this week's email

Write the email yourself — do not delegate to newsletter.py for generation. Use the topic from Step 1 as the core insight.

**Subject:** Specific and curiosity-driven. Under 60 characters. No spam words (free, win, guarantee, etc.). Reference the topic concretely.

**HTML body requirements:**
- Self-contained fragment (no `<!DOCTYPE>`, no `<html>`/`<head>`)
- Centered div, max-width 600px, font-family sans-serif, line-height 1.6, inline styles
- Use `{{first_name}}` where you'd address them by name (replaced per contact at send time)
- Use `{{business_name}}` where you'd reference their studio (replaced per contact at send time)

**Email structure:**
1. `Hey {{first_name}},` — then 1-2 sentences on a real pain point or AI adoption stat for fitness studios
2. ONE actionable insight about using AI for client acquisition tied to this week's topic (3-5 sentences, concrete and specific — no fluff)
3. Social proof placeholder: `<p><em>[Insert client win here]</em></p>`
4. CTA: "Want me to put together a custom AI + marketing plan for {{business_name}}? Book a quick discovery call — [booking_link from config]"
5. Casual sign-off from "Dylan | Digigrowth"
6. Footer: small plain-text unsubscribe note

**Tone:** Direct, friendly, trusted expert who knows AI and fitness marketing. No hype. No buzzwords. Under 90 seconds to read.

### Step 4 — Save draft

Read `config.json` → `newsletter.booking_link`. Replace `[booking_link from config]` in the HTML with the actual URL before saving.

Write the draft to `newsletter_draft.json`:
```json
{
  "subject": "...",
  "html": "..."
}
```

Append the used topic to `newsletter_topic_log.json`:
```json
[
  {"topic": "topic text here", "date": "YYYY-MM-DD"},
  ...
]
```
If the file doesn't exist, create it with a single-item array.

### Step 5 — Create Notion preview page

Create a new Notion page as a subpage of the Daily Brief (`355d25c0-53ea-8094-af4b-e13e20d48d3b`) using `notion-create-pages`.

**Page title:** `Newsletter Draft — [Month Date, Year]`

**Page content (as Notion blocks, in order):**
1. `callout`: "Review this draft. Tell your EA 'send the newsletter' to deploy."
2. `heading_2`: "Subject" → `paragraph`: the subject line
3. `heading_2`: "Recipients" → `paragraph`: "[N] contacts tagged `newsletter` in GHL"
4. `heading_2`: "Topic this week" → `paragraph`: the topic from Step 1
5. `divider`
6. `heading_2`: "Email Preview" — format the HTML body as readable Notion blocks:
   - Opening line → `paragraph`
   - Each body paragraph → `paragraph`
   - Social proof placeholder → `quote` block
   - CTA → `callout` block
   - Sign-off → `paragraph`
7. `divider`
8. `heading_3`: "HTML Source" → `code` block (language: html): the full raw HTML (for copy-paste into a browser)

After creating the page, retrieve its URL. Return this summary for the daily brief:

```
**Subject:** [subject]
**To:** [N] contacts tagged `newsletter` in GHL
**Topic:** [topic]

→ [Preview in Notion]([page URL]) — review and say "send the newsletter" to deploy.
```

---

## Send Mode

Run when Dylan says "send the newsletter" or when delegated by `manage-apptset-agent`.

### Step 1 — Confirm draft exists

Check that `newsletter_draft.json` exists. If it doesn't: "No draft found — run the newsletter draft first or ask me to draft it now." Stop.

### Step 2 — Send

Run:
```bash
cd "/Users/dylangroenendijk/digigrowth-brain/apptset-agent " && python newsletter.py --send
```

Capture and report the output (sent count, failed count).

### Step 3 — Log the decision

Read the subject from `newsletter_draft.json`. Append to `executive-assistant/decisions/log.md`:

```
[YYYY-MM-DD] DECISION: Sent weekly newsletter | REASONING: Saturday draft reviewed and approved by Dylan | CONTEXT: Subject: "[subject]" | Recipients: [N sent]
```

---

## Topic Rotation List

Pick in order, skipping topics used in the last 20 weeks. Cycle back to 01 when all are exhausted.

```
01. The AI follow-up sequence that books consultations while you sleep
02. How fitness studios are using AI to turn cold leads into paying clients
03. The 3-message AI SMS flow that gets 40%+ reply rates
04. Why AI-powered "speed to lead" is the biggest revenue unlock for studios right now
05. How one studio added 20 intro sessions/month with a single AI automation
06. The AI tool that writes every follow-up message so you never have to
07. How to use AI to reactivate your dead leads list (without lifting a finger)
08. The AI workflow that follows up with every no-show automatically
09. Why studios using AI outreach are booking 3x more discovery calls
10. How AI qualifies your leads before you ever pick up the phone
11. The AI-powered referral system that fills your pipeline on autopilot
12. How fitness studios are using AI to cut their cost-per-lead in half
13. The AI chatbot that handles your DMs and books calls 24/7
14. How to use AI to turn your Google reviews into a lead generation machine
15. The AI sequence that turns website visitors into booked consultations
16. How AI helps studios personalize outreach at scale (without it feeling robotic)
17. The AI email strategy that keeps your brand top-of-mind with 500 leads at once
18. Why the studios winning right now all have one thing in common: AI automation
19. How to build an AI client acquisition system for under $500/month
20. The AI-powered onboarding flow that reduces no-shows by 30%
```

---

## Edge Cases

- **No contacts tagged newsletter:** Report "0 contacts tagged 'newsletter' in GHL — add the tag to leads before sending." Do not send.
- **Python command fails (missing .env / API error):** Note it in the Notion preview. Still save the draft. Dylan can fix credentials and send manually later.
- **Draft already exists from this week:** Overwrite it. Always use the freshest draft.
- **Topic log is corrupted / unparseable:** Treat as empty, start from topic 01.
