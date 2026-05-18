# Manage Appt-Setting Agent

Gives the EA direct control over the appointment-setting agent — manage the newsletter, SMS conversations, GHL contact flows, and configuration without leaving the chat.

**Agent location:** `/Users/dylangroenendijk/digigrowth-brain/apptset-agent /`

---

## File Map

| File | What it controls |
|---|---|
| `config.json` | GHL location ID, SMS limits, booking link, newsletter settings |
| `ghl.py` | GHL API: contact lookup, tags, SMS send, newsletter lead fetch |
| `sms_agent.py` | SMS conversation logic, Claude persona, appointment detection, message cap |
| `newsletter.py` | Newsletter generation and delivery (`--preview` / `--send`) |
| `server.py` | Inbound SMS webhook server (Flask + ngrok) |
| `newsletter_draft.json` | This week's saved email draft — subject + HTML template |
| `newsletter_topic_log.json` | Record of topics used and when — drives weekly rotation |
| `.env` | API keys — never read aloud, never edit |
| `.claude/skills/newsletter/SKILL.md` | Full newsletter skill — all draft and send logic lives here |

---

## Run Commands

```bash
# Draft this week's newsletter (generate + save to newsletter_draft.json)
cd "/Users/dylangroenendijk/digigrowth-brain/apptset-agent " && python newsletter.py --preview

# Send newsletter from the saved draft
cd "/Users/dylangroenendijk/digigrowth-brain/apptset-agent " && python newsletter.py --send

# Check how many contacts are tagged 'newsletter' in GHL
cd "/Users/dylangroenendijk/digigrowth-brain/apptset-agent " && python -c "import json, ghl; c=json.load(open('config.json')); leads=ghl.get_newsletter_leads(c); print(len(leads))"

# Start the inbound SMS webhook server
cd "/Users/dylangroenendijk/digigrowth-brain/apptset-agent " && python server.py
```

---

## Common Tasks

### Draft this week's newsletter
Follow the **Draft Mode** steps in `.claude/skills/newsletter/SKILL.md` (in the apptset-agent directory). That skill is the source of truth for all newsletter logic — topic rotation, email generation, Notion preview page, and draft saving.

### Send this week's newsletter
Follow the **Send Mode** steps in `.claude/skills/newsletter/SKILL.md`. Confirm the draft exists first, then run `python newsletter.py --send` and log the decision.

### Add a lead to the newsletter list
In GHL, add the tag `newsletter` to the contact. No code changes needed.

### Update the booking link
Edit `config.json` → `newsletter.booking_link` (and `sms_agent.booking_link` if SMS uses a different link).

### Add a new newsletter topic
Edit `.claude/skills/newsletter/SKILL.md` → append to the Topic Rotation List. Topics are picked in order, so add new ones at the bottom.

### Update the SMS persona
Edit `sms_agent.py` → find the system prompt block, update the persona text directly. Changes take effect on the next inbound message.

### Change the SMS message cap
Edit `config.json` → `sms_agent.max_messages`. Default is 15.

### Check newsletter draft content
Read `newsletter_draft.json` — contains the current subject line and HTML template. The `{{first_name}}` and `{{business_name}}` placeholders are replaced per contact at send time.

---

## Current Standing Directives

*Dylan updates this section to give ongoing orders to the EA about this agent.*

- Newsletter drafts every Saturday automatically as part of the daily briefing
- Do not send the newsletter without Dylan's explicit approval — always preview in Notion first
- Do not change `ghl_location_id` without Dylan confirming
- Never read or output `.env` file contents

---

## Security

`.env` is in `.gitignore`. Never commit API keys.
