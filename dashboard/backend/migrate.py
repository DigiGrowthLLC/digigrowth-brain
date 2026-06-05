"""
One-time migration: GHL contacts → DigiGrowth OS Postgres database.

Usage:
    DATABASE_URL=postgres://... GHL_PRIVATE_TOKEN=... GHL_LOCATION_ID=... python migrate.py

After verifying contacts appear correctly in the dashboard, cancel GHL.
"""

import asyncio
import os
import sys
import uuid
import requests
from dotenv import load_dotenv
from db import get_pool

load_dotenv()

GHL_BASE = "https://services.leadconnectorhq.com"
CF_LEAD_GRADE       = "53vuuYEBnWTFA2bieX12"
CF_CUSTOM_OPENER    = "Mg7mf31yey0FoCoEYoPJ"
CF_COLD_CALL_RESULT = "9gUOgOam3DuuNsTqw5Si"
CF_NUM_CALLS        = "YBAjRCgeXi4IDwWHZkWc"

TAG_TO_STATUS = {
    "appointment-booked":  "appointment-booked",
    "sms-handoff":         "sms-handoff",
    "not-interested":      "not-interested",
    "send-info":           "send-info",
    "voicemail-left":      "voicemail",
    "needs-call":          "dialer-lead",
    "newsletter":          None,  # handled as newsletter=True flag
}

ATTEMPT_PARSE = {"Cold Call 1": 1, "Cold Call 2": 2, "Cold Call 3": 3}


def _headers():
    token = os.environ.get("GHL_PRIVATE_TOKEN") or os.environ.get("GHL_API_KEY", "")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Version": "2021-07-28"}


def _cf(contact, field_id):
    for field in contact.get("customFields", []):
        if field.get("id") == field_id:
            val = field.get("value", "")
            if isinstance(val, list):
                return val[0] if val else ""
            return val or ""
    return ""


def _infer_status(tags):
    for tag, status in TAG_TO_STATUS.items():
        if tag in tags and status is not None:
            return status
    return "new"


def fetch_all_ghl_contacts(location_id):
    print("Fetching contacts from GHL...")
    all_contacts = []
    body = {"locationId": location_id, "pageLimit": 100}
    page = 0
    while True:
        r = requests.post(f"{GHL_BASE}/contacts/search", headers=_headers(), json=body, timeout=30)
        r.raise_for_status()
        data = r.json()
        batch = data.get("contacts", [])
        if not batch:
            break
        all_contacts.extend(batch)
        page += 1
        print(f"  Page {page}: {len(all_contacts)} contacts so far...")
        if len(batch) < 100:
            break
        last = batch[-1]
        body["searchAfter"] = last.get("searchAfter") or [last["id"]]
    print(f"Total contacts fetched: {len(all_contacts)}")
    return all_contacts


def ghl_contact_to_row(c):
    first = c.get("firstName") or ""
    last  = c.get("lastName") or ""
    tags  = [t.lower() for t in (c.get("tags") or [])]

    grade        = _cf(c, CF_LEAD_GRADE) or None
    opener       = _cf(c, CF_CUSTOM_OPENER) or None
    last_disp    = _cf(c, CF_COLD_CALL_RESULT) or None
    attempt_str  = _cf(c, CF_NUM_CALLS) or ""
    call_attempts = ATTEMPT_PARSE.get(attempt_str, 0)

    status    = _infer_status(tags)
    newsletter = "newsletter" in tags

    return {
        "id":               c.get("id") or str(uuid.uuid4()),
        "business":         c.get("companyName") or None,
        "owner":            f"{first} {last}".strip() or None,
        "phone":            c.get("phone") or None,
        "email":            c.get("email") or None,
        "website":          None,
        "city":             c.get("city") or None,
        "state":            c.get("state") or None,
        "grade":            grade,
        "opener":           opener,
        "status":           status,
        "call_attempts":    call_attempts,
        "last_disposition": last_disp,
        "notes":            None,
        "newsletter":       newsletter,
    }


async def run_migration():
    location_id = os.environ.get("GHL_LOCATION_ID", "FVNoxxUHiEhxjgsdhvsV")
    contacts = fetch_all_ghl_contacts(location_id)

    pool = await get_pool()
    inserted = 0
    skipped  = 0

    async with pool.acquire() as conn:
        for c in contacts:
            row = ghl_contact_to_row(c)
            if not row["phone"]:
                skipped += 1
                continue
            try:
                await conn.execute(
                    """
                    INSERT INTO contacts
                        (id, business, owner, phone, email, website, city, state,
                         grade, opener, status, call_attempts, last_disposition, notes, newsletter)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
                    ON CONFLICT (phone) DO UPDATE SET
                        business         = EXCLUDED.business,
                        owner            = EXCLUDED.owner,
                        email            = EXCLUDED.email,
                        grade            = EXCLUDED.grade,
                        opener           = EXCLUDED.opener,
                        status           = EXCLUDED.status,
                        call_attempts    = EXCLUDED.call_attempts,
                        last_disposition = EXCLUDED.last_disposition,
                        newsletter       = EXCLUDED.newsletter,
                        updated_at       = now()
                    """,
                    row["id"], row["business"], row["owner"], row["phone"],
                    row["email"], row["website"], row["city"], row["state"],
                    row["grade"], row["opener"], row["status"],
                    row["call_attempts"], row["last_disposition"],
                    row["notes"], row["newsletter"],
                )
                inserted += 1
            except Exception as e:
                print(f"  ⚠️  Failed to insert {row['phone']}: {e}")
                skipped += 1

    print(f"\nMigration complete: {inserted} inserted/updated, {skipped} skipped (no phone).")


if __name__ == "__main__":
    asyncio.run(run_migration())
