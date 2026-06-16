# Parallel Dialer

Dials up to 10 leads simultaneously via Twilio, bridges the first answered call to Dylan's browser, classifies dispositions via button click, and logs everything to the DigiGrowth OS CRM. After 3 unanswered attempts, leads hand off automatically to the OS SMS appointment-setting workflow.

**Run:** `python run.py`

---

## File Roles

| File | Purpose |
|---|---|
| `run.py` | CLI entry point — start session, test, newsletter |
| `dialer.py` | Twilio: place outbound calls, manage conference, cancel overflow |
| `webhook.py` | Flask server: handle all Twilio call events via TwiML, serve browser UI |
| `leads.py` | Utility: phone number normalization |
| `agent.html` | Browser UI: Twilio.Device client, disposition buttons, contact info display |
| `config.json` | Settings — phone numbers, OS API URL, ngrok URL, Twilio config |
| `memory.txt` | Agent memory — rules, notes, edge cases |
| `.env` | Twilio API keys — never commit |

---

## Setup (First Time)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up env
cp .env.example .env
# Fill in: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_API_KEY_SID,
#          TWILIO_API_KEY_SECRET, TWILIO_TWIML_APP_SID,
#          OS_API_PASSWORD, NGROK_AUTH_TOKEN

# 3. Fill in config.json
#    - twilio_phone_number (your Twilio number)
#    - os_api_url (DigiGrowth OS Railway URL)
#    - webhook_base_url (your ngrok static domain URL)
#    - calendly_url (your booking link)

# 4. Start ngrok (auto-started by run.py if NGROK_AUTH_TOKEN is set)

# 5. Test the call bridge
python run.py test

# 6. Start a real session
python run.py
```

---

## CLI Commands

```bash
python run.py          # Start dialing session
python run.py test     # Place a test call to verify Twilio + webhook setup
python run.py newsletter  # Generate and send weekly AI newsletter
```

---

## How a Call Works

1. `run.py` loads eligible leads from DigiGrowth OS CRM (`GET /api/dialer/leads`)
   - Leads ordered: Grade A → B → C → D, then by fewest attempts
   - Excluded: appointment-booked, not-interested, sms-handoff, dnc
   - Cooldown: contacts last called within 4 hours are skipped
2. Ngrok tunnel auto-starts, TwiML App Voice URL is auto-updated
3. Browser UI opens at `http://localhost:5000/agent`
4. Dylan clicks Connect — his browser joins the Twilio conference
5. Dialer calls up to 10 leads simultaneously
6. **First lead to answer** → bridged to conference immediately (Dylan hears them)
7. All other ringing calls → canceled
8. Call ends → Dylan clicks a disposition button in the browser
9. Disposition POSTed to OS CRM (`POST /api/dialer/disposition`)
10. Contact status updated in PostgreSQL; call logged to `call_logs` table
11. Next batch starts

---

## Disposition → OS CRM Status Map

| Disposition | OS Contact Status |
|---|---|
| Appointment Booked | `appointment-booked` |
| Follow Up | `dialer-lead` |
| Send Info | `send-info` |
| Not Interested | `not-interested` |
| No Answer | `dialer-lead` |
| SMS Handoff (auto after 3×) | `sms-handoff` |

---

## 3-Strike Handoff

If a lead reaches 3 unanswered call attempts:
- OS CRM sets contact status → `sms-handoff`
- Twilio sends an outbound SMS automatically (handled in `dashboard/backend/routers/dialer.py`)

---

## Machine Detection

Twilio's `AnsweredBy` parameter is used to detect voicemails:
- `machine_end_*` or `fax` → call is dropped immediately, counted as No Answer
- `machine_start` (IVR/gatekeeper) → held silently, popup appears in browser for Dylan to connect or decline

---

## Environment Variables (`.env`)

```
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_API_KEY_SID=SK...
TWILIO_API_KEY_SECRET=...
TWILIO_TWIML_APP_SID=AP...
OS_API_PASSWORD=...        # same as DASHBOARD_PASSWORD on Railway
NGROK_AUTH_TOKEN=...       # free ngrok account token
```

---

## Security

`.env` is in `.gitignore`. Never commit it.
