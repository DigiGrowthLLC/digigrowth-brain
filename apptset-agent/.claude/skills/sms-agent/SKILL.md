# SMS Agent Skill

Four modes for managing the SMS appointment-setting agent. Execute without asking for confirmation — just run and report.

The apptset-agent directory: `$(git rev-parse --show-toplevel)/apptset-agent`

---

## Mode 1 — Status

Triggered by: "SMS status", "how are SMS conversations going?", "SMS stats"

Run:
```bash
cd "$(git rev-parse --show-toplevel)/apptset-agent" && python sms_stats.py
```

Report the output cleanly — all-time totals, last-30-day totals, active conversations count, recent bookings.

---

## Mode 2 — Review conversations

Triggered by: "show SMS conversations", "review [name]'s SMS thread", "what stage is [name] at?"

### List active conversations
```bash
cd "$(git rev-parse --show-toplevel)/apptset-agent" && python sms_stats.py
```
Pull the active conversations table from the output.

### Show a specific contact's thread
```bash
cd "$(git rev-parse --show-toplevel)/apptset-agent" && python -c "
import sqlite3, json
db = 'sms_conversations.db'
with sqlite3.connect(db) as conn:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(\"SELECT phone, lead_json, messages, stage, status, follow_up_count FROM conversations WHERE LOWER(lead_json) LIKE '%[NAME_LOWER]%'\").fetchall()
for r in rows:
    lead = json.loads(r['lead_json'])
    print(f'--- {lead.get(\"owner\")} | {lead.get(\"business\")} | stage={r[\"stage\"]} | status={r[\"status\"]} | fups={r[\"follow_up_count\"]}')
    msgs = json.loads(r['messages'])
    for m in msgs:
        prefix = 'OUT:' if m['role']=='assistant' else 'IN: '
        print(f'  {prefix} {m[\"content\"]}')
"
```

Replace `[NAME_LOWER]` with the lowercase search term.

---

## Mode 3 — Trigger import

Triggered by: "import leads from sheets", "run the Sheets import", "trigger lead import"

Run:
```bash
cd "$(git rev-parse --show-toplevel)/apptset-agent" && python sheets_import.py
```

Report: how many new contacts created, how many already existed, how many tagged with sms-handoff.

---

## Mode 4 — Sync SMS stats to Notion

Triggered by: "sync SMS stats", "update Notion with SMS stats", "push SMS numbers to Notion"

### Step 1 — Get current stats
```bash
cd "$(git rev-parse --show-toplevel)/apptset-agent" && python sms_stats.py --json
```

Parse the JSON output to get all_time and last_30 values.

### Step 2 — Fetch the Outreach & Appointment Setting Notion page
Use `notion-fetch` on page ID `350d25c053ea809c55cbc3e38b4d6c` to find the KPI tables and their property IDs.

### Step 3 — Update both KPI tables
Find the SMS column rows in:
- **All Time** table
- **Last 30 Days** table

Update these fields using `notion-update-page`:
- Outbound Sent
- Replies
- Engaged
- Booked
- Booking Rate %

Report: "SMS stats synced to Notion — [summary of values updated]"
