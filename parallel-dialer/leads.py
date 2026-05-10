import os
import json
import time
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "state.json")

# Columns expected from lead-qualifier output
COL_PHONE    = "Phone"
COL_BUSINESS = "Business Name"
COL_OWNER    = "Owner Name"
COL_GRADE    = "Grade"
COL_OPENER   = "Opener"

# Optional columns — included in lead data if present in the sheet
OPTIONAL_COLS = {
    "email":   "Email",
    "website": "Website",
    "address": "Address",
    "city":    "City",
    "state":   "State",
}

# Columns added by dialer
COL_ATTEMPTS    = "Dial Attempts"
COL_LAST_DIALED = "Last Dialed"
COL_DISPOSITION = "Disposition"
COL_HANDED_OFF  = "Handed Off"

DIALER_COLUMNS = [COL_ATTEMPTS, COL_LAST_DIALED, COL_DISPOSITION, COL_HANDED_OFF]

GRADE_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3}

TERMINAL_DISPOSITIONS = {"Appointment Booked", "Not Interested", "SMS Handoff"}


# ════════════════════════════════════════════════════════════════════════════
#  SHEET CONNECTION
# ════════════════════════════════════════════════════════════════════════════

def get_sheet(config):
    creds = Credentials.from_service_account_file(
        os.path.join(BASE_DIR, "credentials.json"),
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(config["google_sheet_id"])
    try:
        return sh.worksheet(config["leads_tab"])
    except gspread.exceptions.WorksheetNotFound:
        raise RuntimeError(
            f"Tab '{config['leads_tab']}' not found in sheet. "
            "Check google_sheet_id and leads_tab in config.json."
        )


def ensure_dialer_columns(ws):
    """Add dialer tracking columns to the sheet if they don't exist yet."""
    headers = ws.row_values(1)
    missing = [c for c in DIALER_COLUMNS if c not in headers]
    if missing:
        next_col = len(headers) + 1
        for i, col_name in enumerate(missing):
            ws.update_cell(1, next_col + i, col_name)
            time.sleep(0.2)
    return ws.row_values(1)


# ════════════════════════════════════════════════════════════════════════════
#  LOAD LEADS
# ════════════════════════════════════════════════════════════════════════════

def load_leads(config):
    """
    Pull leads eligible for dialing from Google Sheets.
    Eligible = qualified, not terminally dispositioned, attempts < max.
    Returns (leads list, worksheet, headers list).
    """
    max_attempts = config.get("max_call_attempts", 3)
    ws      = get_sheet(config)
    headers = ensure_dialer_columns(ws)
    rows    = ws.get_all_records()
    leads   = []

    for i, row in enumerate(rows, start=2):
        phone = str(row.get(COL_PHONE, "")).strip()
        if not phone:
            continue

        disposition = str(row.get(COL_DISPOSITION, "")).strip()
        handed_off  = str(row.get(COL_HANDED_OFF, "")).strip()
        attempts    = int(row.get(COL_ATTEMPTS, 0) or 0)

        if disposition in TERMINAL_DISPOSITIONS:
            continue
        if handed_off == "Yes":
            continue
        if attempts >= max_attempts:
            continue

        lead = {
            "row_index":   i,
            "phone":       phone,
            "business":    str(row.get(COL_BUSINESS, "")).strip(),
            "owner":       str(row.get(COL_OWNER, "")).strip(),
            "grade":       str(row.get(COL_GRADE, "C")).strip(),
            "opener":      str(row.get(COL_OPENER, "")).strip(),
            "attempts":    attempts,
            "disposition": disposition,
        }
        for key, col_name in OPTIONAL_COLS.items():
            if col_name in headers:
                lead[key] = str(row.get(col_name, "")).strip()
        leads.append(lead)

    leads.sort(key=lambda x: GRADE_ORDER.get(x["grade"], 3))
    return leads, ws, headers


# ════════════════════════════════════════════════════════════════════════════
#  WRITE BACK
# ════════════════════════════════════════════════════════════════════════════

def update_disposition(ws, headers, row_index, disposition, attempts):
    """Write call result back to the sheet."""
    _set(ws, headers, row_index, COL_ATTEMPTS,    attempts)
    _set(ws, headers, row_index, COL_LAST_DIALED, _now())
    _set(ws, headers, row_index, COL_DISPOSITION, disposition)


def mark_handed_off(ws, headers, row_index):
    """Mark lead as handed off to GHL SMS agent."""
    _set(ws, headers, row_index, COL_DISPOSITION, "SMS Handoff")
    _set(ws, headers, row_index, COL_HANDED_OFF,  "Yes")


def _set(ws, headers, row_index, col_name, value):
    col_idx = headers.index(col_name) + 1
    ws.update_cell(row_index, col_idx, value)
    time.sleep(0.2)


# ════════════════════════════════════════════════════════════════════════════
#  LOCAL STATE (state.json)
# ════════════════════════════════════════════════════════════════════════════

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"leads": {}, "session": {}}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def init_lead_state(state, lead):
    """Register a lead in state.json if not already tracked."""
    phone = lead["phone"]
    if phone not in state["leads"]:
        state["leads"][phone] = {
            "business":     lead["business"],
            "owner":        lead["owner"],
            "row_index":    lead["row_index"],
            "attempts":     lead["attempts"],
            "disposition":  lead.get("disposition", ""),
            "last_attempt": "",
            "handed_off":   False,
            "pending_write": False,
        }


def record_attempt(state, phone):
    """Increment attempt count and timestamp."""
    if phone in state["leads"]:
        state["leads"][phone]["attempts"] += 1
        state["leads"][phone]["last_attempt"] = _now()


def record_disposition(state, phone, disposition):
    """Set disposition and flag for sheet write-back."""
    if phone in state["leads"]:
        state["leads"][phone]["disposition"]  = disposition
        state["leads"][phone]["pending_write"] = True


def needs_handoff(state, phone, max_attempts):
    """Return True if lead has exhausted all attempts with no DM reached."""
    lead = state["leads"].get(phone, {})
    terminal = lead.get("disposition", "") in TERMINAL_DISPOSITIONS
    return (
        lead.get("attempts", 0) >= max_attempts
        and not terminal
        and not lead.get("handed_off", False)
    )


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")
