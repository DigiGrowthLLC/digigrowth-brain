# Newsletter

Generates DigiGrowth's weekly AI-tip email for contacts flagged `newsletter` in the DigiGrowth OS CRM. Draft runs every Monday as part of the morning briefing.

**Run manually:** Ask the EA to "draft the newsletter." The EA delegates here via `manage-apptset-agent`.
**Scheduled (draft):** Runs automatically every Monday as part of the daily briefing (Step 4.5).
**Send Mode is currently disabled.** GoHighLevel (the old sending mechanism) is no longer in use and nothing has replaced it yet — Draft Mode still works, but there is no way to actually deliver the email right now. See "Send Mode" below.

---

## What This Skill Does

1. Picks this week's topic from a rotating list of AI client acquisition tips for independent service-based businesses
2. Runs one web search on that topic and caches the findings (`weekly_research_cache.json`) — shared with `content-agent`'s `weekly-ai-blog` skill so both pieces of content are grounded in the same research without a second search
3. Generates a personalized email draft (uses `{{first_name}}` and `{{business_name}}` placeholders)
4. Saves the draft to `newsletter_draft.json` for the Python send script
5. Renders the draft as a PDF and posts it inline in the OS chat, linked from Monday's daily brief
6. Submits the draft for approval via the dashboard's approvals API, so Dylan gets a live Approve/Decline control in chat
7. On send trigger: runs `newsletter.py --send` which personalizes and delivers to every tagged contact (currently unwired — see Send Mode)

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

### Step 1.5 — Research this week's topic (shared with the blog post)

Do **one web search** on this week's topic (e.g. "AI lead follow-up automation small business 2026 statistics") to ground the email in real, current data instead of writing from memory alone. Pull 2-4 concrete facts/stats, each with its source URL.

Save the findings to `apptset-agent/weekly_research_cache.json`:
```json
{
  "date": "YYYY-MM-DD",
  "topic": "topic text from Step 1",
  "findings": ["concrete fact or stat", "..."],
  "sources": ["https://...", "..."]
}
```
Overwrite any existing file — always use this week's fresh research. `content-agent`'s `weekly-ai-blog` skill reads this same file so the blog post covers the same ground without a second search — one search, two pieces of content.

If the search turns up nothing useful for this topic, write `findings: []` and continue — Step 3 falls back to writing from general knowledge for this week only.

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

**Subject:** Specific and curiosity-driven. Under 60 characters. No spam words (free, win, guarantee, etc.). Reference the topic concretely.

**HTML body requirements:**
- Self-contained fragment (no `<!DOCTYPE>`, no `<html>`/`<head>`)
- Centered div, max-width 600px, font-family sans-serif, line-height 1.6, inline styles
- Use `{{first_name}}` where you'd address them by name (replaced per contact at send time)
- Use `{{business_name}}` where you'd reference their studio (replaced per contact at send time)
- **Use HTML entities for all non-ASCII characters** — never paste raw Unicode. Em dash → `&mdash;`, smart quotes → `&ldquo;` / `&rdquo;`, apostrophe → `&#39;` or `&apos;`. This prevents garbled symbols (â€") when an email client renders the HTML.
- **Paragraph spacing:** every `<p>` tag must have `style="margin:0;"` and be followed by a `<br>` tag before the next paragraph. Do NOT rely on CSS margin/padding for spacing between paragraphs — email clients collapse it. Use explicit `<br>` tags between every paragraph block.
- **Bold key phrases:** wrap the most important stats, numbers, and action phrases in `<strong>` tags so readers scanning quickly know what matters. Aim for 4-7 bolded phrases per email (e.g. response time stats, sequence steps, outcome metrics, the core benefit).

**Email structure:**
1. `Hey {{first_name}},` — then 1-2 sentences on a real pain point or AI adoption stat for independent service-based businesses
2. ONE actionable insight about using AI for client acquisition tied to this week's topic (3-5 sentences, concrete and specific — no fluff)
3. CTA: "Want me to put together a custom AI + marketing plan for {{business_name}}? Book a quick discovery call — [booking_link from config]"
5. Casual sign-off from "Dylan | Digigrowth"
6. Footer: small plain-text unsubscribe note

**Tone:** Direct, friendly, trusted expert who knows AI and service-based business marketing. No hype. No buzzwords. Under 90 seconds to read.

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

Review this draft. Sending is currently disabled (see "Send Mode" below) — this is preview-only for now.

## Subject

[subject]

## Recipients

| Name | Business |
| --- | --- |
| ... one row per contact from Step 2, "—" if business is blank ... |

[N] contacts flagged `newsletter` in the DigiGrowth OS

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

### Step 6 — Submit for approval

Call the dashboard's approvals endpoint so Dylan gets a real Approve/Decline control in chat instead of just a static preview:

```bash
curl -s -u "admin:$DASHBOARD_PASSWORD" -X POST \
  -H "Content-Type: application/json" \
  -d '{"kind":"newsletter","title":"[subject]","summary":"[topic] — [N] recipients","payload":{"date":"YYYY-MM-DD"}}' \
  https://digigrowth-brain-production.up.railway.app/api/approvals
```

This returns `{"id": <n>, ...}`. Note that id for the marker below.

Return this summary for the daily brief:

```
**Subject:** [subject]
**To:** [N] contacts flagged `newsletter` in the DigiGrowth OS
**Topic:** [topic]
**Note:** Approving marks this ready to send — actual sending isn't wired up yet (see Send Mode below); approval today just confirms the draft is good.

[[PDF:newsletter]]
[[APPROVAL:<id>]]
```

Both marker lines are literal — the OS chat frontend detects `[[PDF:newsletter]]` and renders the PDF inline, and detects `[[APPROVAL:<id>]]` and renders live Approve/Decline buttons. Replace `<id>` with the actual id returned above. Do not add a link, description, or any other text around either marker line.

---

## Send Mode — currently disabled

`newsletter.py --send` and `apptset-agent/ghl.py` sent email through GoHighLevel's conversations API. Dylan no longer uses GHL, and nothing has replaced it yet, so **do not run `newsletter.py --send`** — it will fail (missing/invalid GHL credentials) or, worse, silently no-op.

If Dylan says "send the newsletter": tell him sending isn't wired up yet and ask what he wants to send through (e.g. Twilio email/SMS via the OS's existing integration, a transactional email API, manual export for a bulk-email tool). Do not attempt to fix or work around this yourself — the recipient list (`newsletter_recipients.json`, sourced from the OS CRM) and the draft content are ready; only actual delivery is unresolved.

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
- **Topic log is corrupted / unparseable:** Treat as empty, start from topic 01.
