# Newsletter

Generates and delivers DigiGrowth's weekly AI-tip email to GHL contacts tagged `newsletter`. Draft runs every Monday as part of the morning briefing. Dylan reviews and manually triggers the send.

**Run manually:** Ask the EA to "draft the newsletter" or "send the newsletter." The EA delegates here via `manage-apptset-agent`.
**Scheduled (draft):** Runs automatically every Monday as part of the daily briefing (Step 4.5).

---

## What This Skill Does

1. Picks this week's topic from a rotating list of AI client acquisition tips for independent mobile and in-home veterinary practices
2. Generates a personalized email draft (uses `{{first_name}}` and `{{business_name}}` placeholders)
3. Saves the draft to `newsletter_draft.json` for the Python send script
4. Renders the draft as a PDF and posts it inline in the OS chat, linked from Saturday's daily brief
5. On send trigger: runs `newsletter.py --send` which personalizes and delivers to every tagged contact

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

### Step 1 — Pick this week's topic

Read `newsletter_topic_log.json`. If the file doesn't exist, treat it as an empty array `[]`.

Compare the log against the topic list below. Pick the **first topic not used in the last 20 entries**. If all 20 have been used recently, restart from topic 01.

### Step 2 — Get recipient list

Run:
```bash
cd "$(git rev-parse --show-toplevel)/apptset-agent" && doppler run -- python -c "
import json, ghl
c = json.load(open('config.json'))
leads = ghl.get_newsletter_leads(c)
print(len(leads))
for l in leads:
    print(l.get('owner',''), '|', l.get('business',''))
"
```

Parse the output: first line is the count, subsequent lines are `name | business` pairs. Store both the count and the full list for use in Step 5.

If the command fails (API error, no env vars), set count to "unknown" and list to empty. Continue.

### Step 3 — Generate this week's email

Write the email yourself — do not delegate to newsletter.py for generation. Use the topic from Step 1 as the core insight.

**Subject:** Specific and curiosity-driven. Under 60 characters. No spam words (free, win, guarantee, etc.). Reference the topic concretely.

**HTML body requirements:**
- Self-contained fragment (no `<!DOCTYPE>`, no `<html>`/`<head>`)
- Centered div, max-width 600px, font-family sans-serif, line-height 1.6, inline styles
- Use `{{first_name}}` where you'd address them by name (replaced per contact at send time)
- Use `{{business_name}}` where you'd reference their studio (replaced per contact at send time)
- **Use HTML entities for all non-ASCII characters** — never paste raw Unicode. Em dash → `&mdash;`, smart quotes → `&ldquo;` / `&rdquo;`, apostrophe → `&#39;` or `&apos;`. This prevents garbled symbols (â€") when GHL renders the email.
- **Paragraph spacing:** every `<p>` tag must have `style="margin:0;"` and be followed by a `<br>` tag before the next paragraph. Do NOT rely on CSS margin/padding for spacing between paragraphs — email clients collapse it. Use explicit `<br>` tags between every paragraph block.
- **Bold key phrases:** wrap the most important stats, numbers, and action phrases in `<strong>` tags so readers scanning quickly know what matters. Aim for 4-7 bolded phrases per email (e.g. response time stats, sequence steps, outcome metrics, the core benefit).

**Email structure:**
1. `Hey {{first_name}},` — then 1-2 sentences on a real pain point or AI adoption stat for mobile/in-home veterinary practices
2. ONE actionable insight about using AI for client acquisition tied to this week's topic (3-5 sentences, concrete and specific — no fluff)
3. CTA: "Want me to put together a custom AI + marketing plan for {{business_name}}? Book a quick discovery call — [booking_link from config]"
5. Casual sign-off from "Dylan | Digigrowth"
6. Footer: small plain-text unsubscribe note

**Tone:** Direct, friendly, trusted expert who knows AI and veterinary practice marketing. No hype. No buzzwords. Under 90 seconds to read.

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

### Step 5 — Render PDF preview and post inline to OS chat

Build a Markdown review document with this exact structure:

````
# Newsletter Draft — [Month Date, Year]

Review this draft. Tell your EA "send the newsletter" to deploy.

## Subject

[subject]

## Recipients

| Name | Business |
| --- | --- |
| ... one row per contact from Step 2, "—" if business is blank ... |

[N] contacts tagged `newsletter` in GHL

## Topic this week

[topic from Step 1]

---

## Email Preview

[opening line]

[each body paragraph, one per line]

[CTA line]

[sign-off]

---

## HTML Source

```html
[the full raw HTML]
```
````

Save this document to `apptset-agent/newsletter-draft-YYYY-MM-DD.md` (today's date). Overwrite any existing file with today's date.

Generate the PDF by calling the backend's PDF endpoint (this reads the `.md` file just saved and renders/caches a matching `.pdf` alongside it):
```bash
curl -s -u "admin:$DASHBOARD_PASSWORD" https://digigrowth-brain-production.up.railway.app/api/agents/apptset-agent/newsletter-pdf -o /dev/null
```

Push both files (the repo is ephemeral on Railway — use `push_file()` from `shared/github_sync.py`, or `git add`/`commit`/`push` directly if running with git access):
- `apptset-agent/newsletter-draft-YYYY-MM-DD.md`
- `apptset-agent/newsletter-draft-YYYY-MM-DD.pdf`

Return this summary for the daily brief:

```
**Subject:** [subject]
**To:** [N] contacts tagged `newsletter` in GHL
**Topic:** [topic]

[[PDF:newsletter]]
```

The `[[PDF:newsletter]]` line is a literal marker — the OS chat frontend detects it and renders the PDF inline. Do not add a link, description, or any other text around it.

---

## Send Mode

Run when Dylan says "send the newsletter" or when delegated by `manage-apptset-agent`.

### Step 1 — Confirm draft exists

Check that `newsletter_draft.json` exists. If it doesn't: "No draft found — run the newsletter draft first or ask me to draft it now." Stop.

If Dylan has given edit instructions directly (in chat), apply them to `newsletter_draft.json` now, then regenerate `apptset-agent/newsletter-draft-YYYY-MM-DD.md`/`.pdf` per Step 5 of Draft Mode before continuing.

### Step 2 — Send

Run:
```bash
cd "$(git rev-parse --show-toplevel)/apptset-agent" && doppler run -- python newsletter.py --send
```

For a **test send** to a single contact, run instead:
```bash
cd "$(git rev-parse --show-toplevel)/apptset-agent" && doppler run -- python newsletter.py --send --test-contact "Name"
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
02. How mobile vet practices are using AI to turn cold leads into paying clients
03. The 3-message AI SMS flow that gets 40%+ reply rates
04. Why AI-powered "speed to lead" is the biggest revenue unlock for vet practices right now
05. How one mobile vet practice added 20 new appointments/month with a single AI automation
06. The AI tool that writes every follow-up message so you never have to
07. How to use AI to reactivate your dead leads list (without lifting a finger)
08. The AI workflow that follows up with every no-show automatically
09. Why vet practices using AI outreach are booking 3x more discovery calls
10. How AI qualifies your leads before you ever pick up the phone
11. The AI-powered referral system that fills your pipeline on autopilot
12. How mobile vet practices are using AI to cut their cost-per-lead in half
13. The AI chatbot that handles your DMs and books calls 24/7
14. How to use AI to turn your Google reviews into a lead generation machine
15. The AI sequence that turns website visitors into booked consultations
16. How AI helps vet practices personalize outreach at scale (without it feeling robotic)
17. The AI email strategy that keeps your brand top-of-mind with 500 leads at once
18. Why the vet practices winning right now all have one thing in common: AI automation
19. How to build an AI client acquisition system for under $500/month
20. The AI-powered onboarding flow that reduces no-shows by 30%
```

---

## Edge Cases

- **No contacts tagged newsletter:** Report "0 contacts tagged 'newsletter' in GHL — add the tag to leads before sending." Do not send.
- **Python command fails (missing credentials / API error):** Note it in the saved draft markdown. Still save the draft. Dylan can fix credentials and send manually later.
- **Draft already exists from this week:** Overwrite it. Always use the freshest draft.
- **Topic log is corrupted / unparseable:** Treat as empty, start from topic 01.
