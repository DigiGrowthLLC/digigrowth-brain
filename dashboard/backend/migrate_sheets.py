"""
Import leads from the leadgen Google Sheet → DigiGrowth OS Postgres database.

Usage:
    cd dashboard/backend
    DATABASE_URL=postgres://... python migrate_sheets.py

Requires: credentials.json in either this directory or leadgen-agent/
"""

import asyncio
import os
import sys
import uuid
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()

# ── Config ───────────────────────────────────────────────────────────────────
SHEET_ID  = "1LNF4Taf3sQ2OGbQ382l0fy-RFU31XkkCVSmXJB0YEWs"
SHEET_TAB = "Sheet1"
SCOPES    = ["https://www.googleapis.com/auth/spreadsheets"]

COLUMNS = [
    "Business Name", "Phone", "Website", "Address", "Email",
    "Owner Name", "Grade", "Grade Reason", "Qualified",
    "Niche Notes", "Disqualify Reason", "Opener", "Notes", "State", "City",
]


def find_credentials():
    candidates = [
        Path(__file__).parent / "credentials.json",
        Path(__file__).parent.parent.parent / "leadgen-agent" / "credentials.json",
        Path(__file__).parent.parent.parent / "parallel-dialer" / "credentials.json",
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    print("ERROR: credentials.json not found. Copy it from leadgen-agent/ to dashboard/backend/")
    sys.exit(1)


def load_sheet_rows():
    creds_path = find_credentials()
    creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)
    try:
        ws = sh.worksheet(SHEET_TAB)
    except gspread.exceptions.WorksheetNotFound:
        print(f"ERROR: Tab '{SHEET_TAB}' not found in sheet.")
        sys.exit(1)

    all_values = ws.get_all_values()
    if not all_values:
        print("Sheet is empty.")
        return []

    headers = all_values[0]
    rows = []
    for row in all_values[1:]:
        padded = row + [""] * (len(headers) - len(row))
        rows.append(dict(zip(headers, padded)))
    print(f"Loaded {len(rows)} rows from Google Sheet.")
    return rows


def row_to_contact(row: dict) -> dict | None:
    phone = (row.get("Phone") or "").strip()
    if not phone:
        return None

    qualified = (row.get("Qualified") or "").strip().lower()
    if qualified in ("no", "false", "disqualified"):
        return None

    notes_parts = []
    if row.get("Grade Reason"):
        notes_parts.append(f"Grade reason: {row['Grade Reason']}")
    if row.get("Niche Notes"):
        notes_parts.append(f"Niche: {row['Niche Notes']}")
    if row.get("Notes"):
        notes_parts.append(row["Notes"])

    return {
        "id":       str(uuid.uuid4()),
        "business": (row.get("Business Name") or "").strip() or None,
        "owner":    (row.get("Owner Name") or "").strip() or None,
        "phone":    phone,
        "email":    (row.get("Email") or "").strip() or None,
        "website":  (row.get("Website") or "").strip() or None,
        "city":     (row.get("City") or "").strip() or None,
        "state":    (row.get("State") or "").strip() or None,
        "grade":    (row.get("Grade") or "").strip().upper() or None,
        "opener":   (row.get("Opener") or "").strip() or None,
        "status":   "new",
        "notes":    "\n".join(notes_parts) or None,
        "newsletter": False,
    }


async def run_import():
    from db import get_pool

    rows = load_sheet_rows()
    contacts = [row_to_contact(r) for r in rows]
    contacts = [c for c in contacts if c]
    print(f"{len(contacts)} qualified contacts to import.")

    pool = await get_pool()
    inserted = skipped = 0

    async with pool.acquire() as conn:
        for c in contacts:
            try:
                await conn.execute(
                    """
                    INSERT INTO contacts
                        (id, business, owner, phone, email, website,
                         city, state, grade, opener, status, notes, newsletter)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
                    ON CONFLICT (phone) DO UPDATE SET
                        business  = EXCLUDED.business,
                        owner     = EXCLUDED.owner,
                        email     = EXCLUDED.email,
                        grade     = EXCLUDED.grade,
                        opener    = EXCLUDED.opener,
                        notes     = EXCLUDED.notes,
                        updated_at = now()
                    """,
                    c["id"], c["business"], c["owner"], c["phone"],
                    c["email"], c["website"], c["city"], c["state"],
                    c["grade"], c["opener"], c["status"],
                    c["notes"], c["newsletter"],
                )
                inserted += 1
            except Exception as e:
                print(f"  ⚠️  Failed {c['phone']}: {e}")
                skipped += 1

    print(f"\nDone: {inserted} imported, {skipped} failed.")


if __name__ == "__main__":
    asyncio.run(run_import())
