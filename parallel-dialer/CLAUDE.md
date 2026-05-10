# Parallel Dialer

Dials up to 10 leads simultaneously via Twilio, bridges the first answered call to Dylan's phone, classifies dispositions via DTMF keypress, and routes each lead into the correct GHL workflow. After 3 unanswered attempts, leads hand off automatically to the GHL SMS appointment-setting workflow.

**Run:** `python run.py`

---

## File Roles

| File | Purpose |
|---|---|
| `run.py` | CLI entry point — start session, status, retry, handoff, test |
| `dialer.py` | Twilio: place outbound calls, manage conference, cancel overflow |
| `webhook.py` | Flask server: handle all Twilio call events via TwiML |
| `leads.py` | Google Sheets: load leads, write dispositions, manage state.json |
| `ghl.py` | GHL API: contact lookup/create, tags, workflow triggers, notes |
| `config.json` | All settings — phone numbers, sheet ID, GHL workflow IDs, webhook URL |
| `memory.txt` | Agent memory — rules, notes, edge cases |
| `state.json` | Auto-generated: per-lead attempt counts and dispositions |
| `.env` | Twilio + GHL API keys — never commit |
| `credentials.json` | Google service account — never commit (copy from lead-qualifier/) |

---

## Setup (First Time)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy credentials from lead-qualifier (same Google service account)
cp ../lead-qualifier/credentials.json .

# 3. Set up env
cp .env.example .env
# Fill in: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, GHL_API_KEY

# 4. Fill in config.json
#    - twilio_phone_number, dylan_phone_number
#    - google_sheet_id (same sheet as lead-qualifier output)
#    - leads_tab (default: "Qualified Leads")
#    - ghl_location_id, ghl_calendar_id
#    - ghl_workflows (get IDs from GHL → Automations)
#    - webhook_base_url (your ngrok URL)

# 5. Start ngrok (in a separate terminal)
ngrok http 5000

# 6. Test the call bridge
python run.py test

# 7. Start a real session
python run.py
```

---

## CLI Commands

```bash
python run.py            # Start dialing session
python run.py status     # Show session stats (calls, dispositions, handoffs)
python run.py retry      # Re-dial leads with <3 attempts and no disposition
python run.py handoff    # Manually trigger SMS handoff for all 3-strike leads
python run.py test       # Place a single test call to verify Twilio setup
```

---

## How a Call Works

1. `run.py` loads eligible leads from Google Sheets (Grade A → B → C → D)
2. Flask webhook server starts on port 5000
3. Dialer calls up to 10 leads simultaneously
4. **First lead to answer** → put in Twilio Conference (hears hold music)
5. Dylan's phone is called — when he answers, conference starts → live call
6. Other answered calls → polite message + hangup
7. Call ends → Dylan hears classification prompt
8. Dylan presses:
   - `1` Appointment Booked
   - `2` Follow Up
   - `3` Not Interested
   - `4` Send Info
   - `5` No Answer
9. Disposition saved to `state.json` and flushed to Google Sheets
10. GHL workflow triggered based on disposition

---

## 3-Strike Handoff

If a lead reaches 3 unanswered call attempts:
- Marked as `SMS Handoff` in Google Sheets
- GHL "SMS Handoff" workflow fires → appointment setter sends outbound SMS sequence

---

## Disposition → GHL Workflow Map

| Keypress | Disposition | GHL Action |
|---|---|---|
| 1 | Appointment Booked | Tag + (book via booking.py — Phase 4) |
| 2 | Follow Up | Tag + `follow_up` workflow |
| 3 | Not Interested | Tag + `not_interested` workflow |
| 4 | Send Info | Tag + `send_info` workflow |
| 5 / auto | No Answer × 3 | `sms_handoff` workflow |

---

## Build Phases

- **Phase 1 (current):** Foundation — single-line bridge, Sheets integration, GHL stubs
- **Phase 2:** True parallel dialing — 10 lines simultaneously
- **Phase 3:** Live GHL workflow wiring with real IDs
- **Phase 4:** GHL Calendar appointment booking via `booking.py`

---

## Security

`.env` and `credentials.json` are in `.gitignore`. Never commit them.
