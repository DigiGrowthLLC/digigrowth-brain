# Manage Appt-Setting Agent

Gives the EA direct control over the appointment-setting agent — manage the newsletter, SMS conversations, GHL contact flows, and configuration without leaving the chat.

**Agent location:** `$(git rev-parse --show-toplevel)/apptset-agent/`

---

## File Map

| File | What it controls |
|---|---|
| `config.json` | GHL location ID, SMS limits, booking link, newsletter settings |
| `ghl.py` | GHL API: contact lookup, tags, SMS send, newsletter lead fetch |
| `sms_agent.py` | SMS stage machine, intent classification, send_outbound, check_followups |
| `notion_messages.py` | Live Notion message fetcher — reads SMS sub-pages before every send |
| `notion_log.py` | Event queue for Notion stats logging |
| `sheets_import.py` | Google Sheets → GHL lead import (Mon-Fri 6pm auto + manual) |
| `sms_stats.py` | SMS analytics — all-time + last-30-day KPI totals |
| `newsletter.py` | Newsletter generation and delivery (`--send`) |
| `server.py` | Webhook server (InboundMessage + ContactTagUpdate) + follow-up scheduler |
| `newsletter_draft.json` | This week's saved email draft — subject + HTML template |
| `newsletter_topic_log.json` | Record of topics used and when — drives weekly rotation |
| `.claude/skills/newsletter/SKILL.md` | Full newsletter skill — all draft and send logic |
| `.claude/skills/sms-agent/SKILL.md` | SMS agent skill — status, review, import, sync Notion |

---

## Run Commands

```bash
# Send newsletter from the saved draft
cd "$(git rev-parse --show-toplevel)/apptset-agent" && doppler run -- python newsletter.py --send

# Check SMS conversation stats
cd "$(git rev-parse --show-toplevel)/apptset-agent" && doppler run -- python sms_stats.py

# Import leads from Google Sheets manually
cd "$(git rev-parse --show-toplevel)/apptset-agent" && doppler run -- python sheets_import.py

# Start the webhook server (InboundMessage + ContactTagUpdate)
cd "$(git rev-parse --show-toplevel)/apptset-agent" && doppler run -- python server.py

# Check how many contacts are tagged 'newsletter' in GHL
cd "$(git rev-parse --show-toplevel)/apptset-agent" && doppler run -- python -c "import json, ghl; c=json.load(open('config.json')); leads=ghl.get_newsletter_leads(c); print(len(leads))"
```

---

## Common Tasks

### Draft this week's newsletter
Follow the **Draft Mode** steps in `$(git rev-parse --show-toplevel)/apptset-agent/.claude/skills/newsletter/SKILL.md`. That skill is the source of truth for all newsletter logic — topic rotation, email generation, Notion preview page, and draft saving.

### Send this week's newsletter
Follow the **Send Mode** steps in the newsletter skill. Confirm the draft exists first, then run `python newsletter.py --send` and log the decision.

### Check SMS conversations
Follow **Mode 2** in `$(git rev-parse --show-toplevel)/apptset-agent/.claude/skills/sms-agent/SKILL.md` to list active conversations or drill into a specific contact's thread.

### Import leads from Google Sheets
Follow **Mode 3** in the SMS agent skill. This runs `sheets_import.py` which skips if the parallel dialer already ran today.

### Sync SMS stats to Notion
Follow **Mode 4** in the SMS agent skill. Updates the All Time + Last 30 Days KPI tables on the Outreach & Appointment Setting Notion page.

### Add a lead to the newsletter list
In GHL, add the tag `newsletter` to the contact. No code changes needed.

### Update the booking link
Edit `config.json` → `newsletter.booking_link` (and `sms_agent.booking_link` if using a different SMS link).

### Add a new newsletter topic
Edit the newsletter SKILL.md → append to the Topic Rotation List.

### Change follow-up count
Edit `config.json` → `sms_agent.max_followups`. Default is 3. To expand, also add corresponding sub-pages to the Notion SMS page (Follow-up 4, etc.).

---

## Current Standing Directives

*Dylan updates this section to give ongoing orders to the EA about this agent.*

- Newsletter drafts every Monday automatically as part of the daily briefing
- Do not send the newsletter without Dylan's explicit approval — always preview in Notion first
- Do not change `ghl_location_id` without Dylan confirming
- Never read aloud, output, or edit stored secrets

---

## Security

Secrets live in the shared `digigrowth` Doppler vault (config `prd_apptset`), not a local `.env` file — never read aloud, never edit directly.
