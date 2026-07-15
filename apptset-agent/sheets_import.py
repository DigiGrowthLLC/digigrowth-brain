"""
Google Sheets → GHL lead import.
Reads the Digigrowth leads sheet, creates GHL contacts for new leads,
and adds the sms-handoff tag so the SMS agent fires automatically.

Skips import if a parallel-dialer session was logged in git today
(looks for "Session data —" in today's commits).

Usage:
  python sheets_import.py
"""

import io
import json
import os
import re
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import gspread
from dotenv import load_dotenv

import ghl as ghl_mod

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SHEET_ID = "1LNF4Taf3sQ2OGbQ382l0fy-RFU31XkkCVSmXJB0YEWs"
TAB_NAME = "Sheet1"

# Expected column names (case-insensitive match)
COL_NAME     = "name"
COL_PHONE    = "phone"
COL_BUSINESS = "business"
COL_CITY     = "city"
COL_GRADE    = "lead grade"


def _dialer_ran_today():
    """Return True if a 'Session data —' commit exists in today's git log."""
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "--since=midnight"],
            capture_output=True, text=True, cwd=BASE_DIR,
        )
        return "Session data" in result.stdout
    except Exception:
        return False


def _normalize_phone(raw):
    """Strip non-digits and return E.164 format (+1XXXXXXXXXX for US)."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    return f"+{digits}" if digits else ""


def _col_index(headers, name):
    """Return zero-based column index for a header name (case-insensitive)."""
    lower = [h.lower().strip() for h in headers]
    try:
        return lower.index(name.lower())
    except ValueError:
        return None


def run_import(config):
    if _dialer_ran_today():
        print("  ⏭  Parallel dialer ran today — skipping Sheets import")
        return

    creds_path = os.path.join(BASE_DIR, "credentials.json")
    if not os.path.exists(creds_path):
        print(f"  ⚠️  credentials.json not found at {creds_path}")
        print("       Generate a Google service-account key with Sheets access and place it here.")
        sys.exit(1)

    gc    = gspread.service_account(filename=creds_path)
    sheet = gc.open_by_key(SHEET_ID).worksheet(TAB_NAME)
    rows  = sheet.get_all_values()

    if not rows:
        print("  ⚠️  Sheet is empty")
        return

    headers = rows[0]
    data    = rows[1:]

    ci_name     = _col_index(headers, COL_NAME)
    ci_phone    = _col_index(headers, COL_PHONE)
    ci_business = _col_index(headers, COL_BUSINESS)
    ci_city     = _col_index(headers, COL_CITY)
    ci_grade    = _col_index(headers, COL_GRADE)

    if ci_phone is None:
        print(f"  ⚠️  Could not find 'Phone' column in sheet headers: {headers}")
        sys.exit(1)

    def _cell(row, idx):
        return row[idx].strip() if idx is not None and idx < len(row) else ""

    new_count      = 0
    existing_count = 0
    sent_count     = 0

    for row in data:
        raw_phone = _cell(row, ci_phone)
        if not raw_phone:
            continue

        phone    = _normalize_phone(raw_phone)
        name     = _cell(row, ci_name)
        business = _cell(row, ci_business)
        city     = _cell(row, ci_city)
        grade    = _cell(row, ci_grade) or "C"

        # Split name into first/last
        parts      = name.split(None, 1)
        first_name = parts[0] if parts else ""
        last_name  = parts[1] if len(parts) > 1 else ""

        # Look up or create contact
        contact = ghl_mod.get_contact_by_phone(config, phone)
        if contact:
            existing_count += 1
            contact_id = contact.get("id", "")
        else:
            contact = ghl_mod.create_contact(
                config, first_name, last_name, phone, business, city, grade
            )
            if not contact:
                print(f"  ⚠️  Could not create contact for {phone} — skipping")
                continue
            contact_id = contact.get("id", "")
            new_count += 1

        # Add sms-handoff tag (triggers send_outbound via /tag-update webhook)
        tags = [t.lower() for t in (contact.get("tags") or [])]
        if "sms-handoff" not in tags:
            ghl_mod.add_tag(config, contact_id, "sms-handoff")
            sent_count += 1
            print(f"  ➕ sms-handoff added: {name or phone} ({business})")
        else:
            print(f"  ⏭  Already has sms-handoff: {name or phone}")

    print(f"\n  ✅ Import complete — {new_count} new, {existing_count} existing, {sent_count} tagged")


if __name__ == "__main__":
    config_path = os.path.join(BASE_DIR, "config.json")
    with open(config_path) as f:
        config = json.load(f)
    run_import(config)
