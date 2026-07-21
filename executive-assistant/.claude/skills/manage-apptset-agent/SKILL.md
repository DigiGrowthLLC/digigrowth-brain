# Manage Appt-Setting Agent

Gives the EA direct control over the newsletter (draft generation) without leaving the chat.

**Agent location:** `$(git rev-parse --show-toplevel)/apptset-agent/`

GoHighLevel and Notion are no longer in use anywhere in this repo. SMS appointment-setting
(opening message + inbox) now lives entirely in the DigiGrowth OS dashboard
(`dashboard/backend/routers/sms.py`, `dashboard/frontend/src/panels/SMSPanel.jsx`), triggered
automatically whenever a contact's status becomes `sms-handoff` in the CRM — there is nothing
to run or manage here for SMS anymore.

---

## File Map

| File | What it controls |
|---|---|
| `config.json` | Newsletter topic hint, booking link, from-name |
| `newsletter.py` | Newsletter draft generation (`--preview`). No send path — see Send Mode below. |
| `newsletter_draft.json` | This week's saved email draft — subject + HTML template |
| `newsletter_topic_log.json` | Record of topics used and when — drives weekly rotation |
| `newsletter_recipients.json` | Nightly export from the OS CRM (`contacts` table, `newsletter = true`) |
| `.claude/skills/newsletter/SKILL.md` | Full newsletter skill — all draft and send logic |

---

## Run Commands

```bash
# Generate a newsletter draft manually
cd "$(git rev-parse --show-toplevel)/apptset-agent" && doppler run -- python newsletter.py --preview
```

---

## Common Tasks

### Draft this week's newsletter
Follow the **Draft Mode** steps in `$(git rev-parse --show-toplevel)/apptset-agent/.claude/skills/newsletter/SKILL.md`. That skill is the source of truth for all newsletter logic — topic rotation, email generation (written inline by the agent, not delegated to `newsletter.py`), PDF preview, and draft saving.

### Send this week's newsletter
Sending is **not wired up** — GHL was the old delivery mechanism and nothing has replaced it. If Dylan asks to send, tell him it isn't resolved yet and ask what he wants to send through (Twilio email/SMS, a transactional email API, manual export). See the newsletter skill's "Send Mode" section.

### Add a lead to the newsletter list
Flag the contact `newsletter = true` in the DigiGrowth OS CRM. No code changes needed.

### Update the booking link
Edit `config.json` → `newsletter.booking_link`.

### Add a new newsletter topic
Edit the newsletter SKILL.md → append to the Topic Rotation List.

### SMS appointment setting
Not managed here anymore. To check conversations or fire an opener manually, use the DigiGrowth OS dashboard's SMS panel directly, or ask about contact status in the CRM.

---

## Current Standing Directives

*Dylan updates this section to give ongoing orders to the EA about this agent.*

- Newsletter drafts every Monday automatically as part of the daily briefing
- Do not send the newsletter without Dylan's explicit approval — always preview first
- Never read aloud, output, or edit stored secrets

---

## Security

Secrets live in the shared `digigrowth` Doppler vault (config `prd_apptset`), not a local `.env` file — never read aloud, never edit directly.
