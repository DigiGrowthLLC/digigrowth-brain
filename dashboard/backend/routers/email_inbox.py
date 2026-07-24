"""
Email Inbox router — Gmail polling sync + email-channel endpoints for the
unified Inbox tab (SMS + Email). Scope: only messages to/from an address
that matches an existing contacts.email value are synced — this is a
prospect-communication tool, not a general email client.

Endpoints (all under /api):
  GET  /api/email/conversations               — list threads
  GET  /api/email/conversations/{thread_id}    — thread messages
  POST /api/email/send                         — reply / new thread
  POST /api/email/conversations/{thread_id}/close
  POST /api/email/conversations/{thread_id}/interested
  POST /api/email/sync                         — manual sync trigger (testing)
  GET  /api/inbox/conversations                — merged SMS + Email list, filterable

sync_gmail_job() is registered on the app's APScheduler (main.py) to run
every ~60s. It never raises — a bad poll just logs and waits for the next tick.
"""

import asyncio
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter

import integrations
from db import get_pool

router = APIRouter()

SYNC_CURSOR_KEY = "email_sync_last_ts"
SYNC_LOOKBACK_SEC = 120  # overlap window so a message straddling a poll boundary is never missed

_CLOSE_DISPOSITION_TO_CONTACT_STATUS = {
    "booked":         "appointment-booked",
    "not_interested": "not-interested",
}


def _extract_email(header_value: str) -> str:
    """'Dylan G <dylan@digigrowthllc.com>' -> 'dylan@digigrowthllc.com' (lowercased)."""
    m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", header_value or "")
    return m.group(0).lower() if m else ""


# ── Sync job ──────────────────────────────────────────────────────────────────

async def _sync_gmail_once() -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Clean up any conversations/messages left over from a looser match
        # (e.g. a contact with a blank/whitespace email used to false-match
        # unparseable recipient headers) — re-validate against current contacts.
        await conn.execute(
            """
            DELETE FROM email_conversations ec
            WHERE NOT EXISTS (
                SELECT 1 FROM contacts c
                WHERE c.id = ec.contact_id AND lower(trim(c.email)) = lower(trim(ec.email))
            )
            """
        )
        await conn.execute(
            """
            DELETE FROM email_messages em
            WHERE NOT EXISTS (SELECT 1 FROM email_conversations ec WHERE ec.thread_id = em.thread_id)
            """
        )

        contacts = await conn.fetch("SELECT id, email FROM contacts WHERE email IS NOT NULL AND trim(email) != ''")
        contact_by_email = {c["email"].strip().lower(): c["id"] for c in contacts if c["email"] and c["email"].strip()}
        if not contact_by_email:
            return {"fetched": 0, "matched": 0, "skipped": 0}

        cursor_row = await conn.fetchrow("SELECT value FROM dialer_settings WHERE key = $1", SYNC_CURSOR_KEY)
        last_ts = int(cursor_row["value"]) if cursor_row and cursor_row["value"] else 0
        query_after = max(0, last_ts - SYNC_LOOKBACK_SEC)

        svc = await asyncio.to_thread(integrations._gmail_service)
        q = f"after:{query_after}" if query_after else "newer_than:7d"
        res = await asyncio.to_thread(
            lambda: svc.users().messages().list(userId="me", q=q, maxResults=100).execute()
        )
        msg_ids = [m["id"] for m in res.get("messages", [])]

        fetched, matched = 0, 0
        newest_ts = last_ts

        for mid in msg_ids:
            exists = await conn.fetchval("SELECT 1 FROM email_messages WHERE gmail_message_id = $1", mid)
            if exists:
                continue
            fetched += 1
            full = await asyncio.to_thread(
                lambda mid=mid: svc.users().messages().get(userId="me", id=mid, format="full").execute()
            )
            headers = {h["name"].lower(): h["value"] for h in full["payload"].get("headers", [])}
            from_addr = _extract_email(headers.get("from", ""))
            subject = headers.get("subject", "(no subject)")
            thread_id = full["threadId"]
            internal_ts = int(full.get("internalDate", "0")) // 1000
            newest_ts = max(newest_ts, internal_ts)

            # Scope: only messages actually sent BY a known prospect (their
            # stored contacts.email) land in the Inbox. We deliberately do NOT
            # also match on the "to" header — this account's own inbox address
            # can end up stored as *some* contact's email (e.g. a test/self
            # entry), and matching "to" would then pull in the account owner's
            # entire personal inbox. Outbound replies sent through the Inbox's
            # own reply box are recorded directly by /email/send instead.
            contact_id, counterparty, direction = None, None, None
            if from_addr and from_addr in contact_by_email:
                contact_id, counterparty, direction = contact_by_email[from_addr], from_addr, "inbound"
            if not contact_id:
                continue  # not a known-prospect inbound message — skip per scope rule

            body = integrations._extract_body(full["payload"]) or full.get("snippet", "")
            matched += 1

            conv = await conn.fetchrow("SELECT id FROM email_conversations WHERE thread_id = $1", thread_id)
            if not conv:
                await conn.execute(
                    """INSERT INTO email_conversations (contact_id, thread_id, email, subject, status)
                       VALUES ($1, $2, $3, $4, 'active')""",
                    contact_id, thread_id, counterparty, subject,
                )
            else:
                await conn.execute(
                    "UPDATE email_conversations SET subject = $2, updated_at = now() WHERE thread_id = $1",
                    thread_id, subject,
                )

            await conn.execute(
                """INSERT INTO email_messages (contact_id, thread_id, email, direction, subject, body, gmail_message_id, sent_at)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, to_timestamp($8))
                   ON CONFLICT (gmail_message_id) DO NOTHING""",
                contact_id, thread_id, counterparty, direction, subject, body, mid, internal_ts,
            )

        if newest_ts > last_ts:
            await conn.execute(
                """INSERT INTO dialer_settings (key, value) VALUES ($1, $2)
                   ON CONFLICT (key) DO UPDATE SET value = $2""",
                SYNC_CURSOR_KEY, str(newest_ts),
            )

    return {"fetched": fetched, "matched": matched, "skipped": fetched - matched}


async def sync_gmail_job():
    """APScheduler entrypoint — never raises, so a bad poll can't kill the scheduler loop."""
    try:
        result = await _sync_gmail_once()
        print(f"[email-sync] fetched={result['fetched']} matched={result['matched']} skipped={result['skipped']}", flush=True)
    except Exception as e:
        print(f"[email-sync] error: {e}", flush=True)


@router.post("/email/sync")
async def manual_sync():
    """Manual trigger for testing/verification — same code path as the scheduled job."""
    return {"ok": True, **(await _sync_gmail_once())}


# ── Authenticated API endpoints ───────────────────────────────────────────────

@router.get("/email/conversations")
async def list_email_conversations():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT ec.id, ec.thread_id, ec.email, ec.subject, ec.status, ec.disposition, ec.updated_at,
                   c.business, c.owner,
                   (SELECT body FROM email_messages
                    WHERE thread_id = ec.thread_id
                    ORDER BY sent_at DESC LIMIT 1) AS last_message,
                   (SELECT direction FROM email_messages
                    WHERE thread_id = ec.thread_id
                    ORDER BY sent_at DESC LIMIT 1) AS last_direction
            FROM email_conversations ec
            LEFT JOIN contacts c ON c.id = ec.contact_id
            ORDER BY ec.updated_at DESC NULLS LAST
            """
        )
    return [dict(r) for r in rows]


@router.get("/email/conversations/{thread_id}")
async def get_email_conversation(thread_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        conv = await conn.fetchrow(
            """
            SELECT ec.*, c.business, c.owner, c.grade
            FROM email_conversations ec
            LEFT JOIN contacts c ON c.id = ec.contact_id
            WHERE ec.thread_id = $1
            """,
            thread_id,
        )
        if not conv:
            return {"thread_id": thread_id, "messages": [], "status": "active", "disposition": None}

        await conn.execute(
            "UPDATE email_conversations SET last_read_at = now() WHERE thread_id = $1", thread_id
        )

        msgs_raw = await conn.fetch(
            "SELECT direction, subject, body, email, sent_at FROM email_messages WHERE thread_id = $1 ORDER BY sent_at",
            thread_id,
        )

    return {
        "thread_id":   thread_id,
        "contact_id":  conv["contact_id"],
        "status":      conv["status"],
        "disposition": conv["disposition"],
        "business":    conv["business"],
        "owner":       conv["owner"],
        "grade":       conv["grade"],
        "email":       conv["email"],
        "subject":     conv["subject"],
        "messages":    [dict(m) for m in msgs_raw],
    }


@router.post("/email/send")
async def manual_email_send(payload: dict):
    thread_id = (payload.get("thread_id") or "").strip()
    to        = (payload.get("to") or "").strip()
    subject   = (payload.get("subject") or "").strip() or "(no subject)"
    body      = (payload.get("body") or "").strip()
    if not to or not body:
        return {"ok": False, "error": "to and body required"}

    try:
        sent = await asyncio.to_thread(integrations.gmail_send_reply, to, subject, body, thread_id)
    except Exception as e:
        return {"ok": False, "error": str(e)}

    new_thread_id = sent["threadId"]

    pool = await get_pool()
    async with pool.acquire() as conn:
        contact_row = await conn.fetchrow("SELECT id FROM contacts WHERE lower(email) = lower($1)", to)
        contact_id = contact_row["id"] if contact_row else None

        conv = await conn.fetchrow("SELECT id FROM email_conversations WHERE thread_id = $1", new_thread_id)
        if not conv:
            await conn.execute(
                """INSERT INTO email_conversations (contact_id, thread_id, email, subject, status)
                   VALUES ($1, $2, $3, $4, 'active')""",
                contact_id, new_thread_id, to, subject,
            )
        else:
            await conn.execute(
                "UPDATE email_conversations SET updated_at = now() WHERE thread_id = $1", new_thread_id
            )

        await conn.execute(
            """INSERT INTO email_messages (contact_id, thread_id, email, direction, subject, body, gmail_message_id, sent_at)
               VALUES ($1, $2, $3, 'outbound', $4, $5, $6, now())
               ON CONFLICT (gmail_message_id) DO NOTHING""",
            contact_id, new_thread_id, to, subject, body, sent["id"],
        )

    return {"ok": True, "thread_id": new_thread_id}


@router.post("/email/conversations/{thread_id}/close")
async def close_email_conversation(thread_id: str, payload: Optional[dict] = None):
    disposition = (payload or {}).get("disposition", "booked")
    if disposition not in _CLOSE_DISPOSITION_TO_CONTACT_STATUS:
        disposition = "booked"

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE email_conversations SET status = 'closed', disposition = $2, updated_at = now() WHERE thread_id = $1",
            thread_id, disposition,
        )
        row = await conn.fetchrow(
            "SELECT contact_id FROM email_conversations WHERE thread_id = $1", thread_id
        )
        if row and row["contact_id"]:
            await conn.execute(
                "UPDATE contacts SET status = $2, updated_at = now() WHERE id = $1",
                row["contact_id"], _CLOSE_DISPOSITION_TO_CONTACT_STATUS[disposition],
            )
    return {"ok": True}


@router.post("/email/conversations/{thread_id}/interested")
async def toggle_email_interested(thread_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status, disposition FROM email_conversations WHERE thread_id = $1", thread_id
        )
        if not row:
            return {"ok": False, "error": "conversation not found"}
        if row["status"] == "closed":
            return {"ok": False, "error": "conversation is closed"}

        new_disposition = None if row["disposition"] == "interested" else "interested"
        await conn.execute(
            "UPDATE email_conversations SET disposition = $2, updated_at = now() WHERE thread_id = $1",
            thread_id, new_disposition,
        )
    return {"ok": True, "disposition": new_disposition}


@router.delete("/email/conversations/{thread_id}")
async def delete_email_conversation(thread_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM email_messages WHERE thread_id = $1", thread_id)
        await conn.execute("DELETE FROM email_conversations WHERE thread_id = $1", thread_id)
    return {"ok": True}


# ── Merged Inbox endpoint (SMS + Email) ───────────────────────────────────────

_SINCE_INTERVAL = {"today": "1 day", "7d": "7 days", "30d": "30 days"}


@router.get("/inbox/tags")
async def list_inbox_tags():
    """Full universe of contact tags, independent of the currently-filtered
    conversation list — powers the Inbox tag filter dropdown."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT DISTINCT unnest(tags) AS tag FROM contacts WHERE tags <> '{}' ORDER BY 1"
        )
    return [r["tag"] for r in rows]


@router.get("/inbox/conversations")
async def list_inbox_conversations(channel: str = "all", since: str = "all", tag: Optional[str] = None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = []

        if channel in ("all", "sms"):
            clauses = []
            args: list = []
            if since in _SINCE_INTERVAL:
                clauses.append(f"sc.updated_at >= now() - interval '{_SINCE_INTERVAL[since]}'")
            if tag:
                args.append(tag)
                clauses.append(f"${len(args)} = ANY(c.tags)")
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            sms_rows = await conn.fetch(
                f"""
                SELECT 'sms' AS channel, sc.phone AS thread_key, sc.status, sc.disposition, sc.updated_at,
                       c.business, c.owner, c.tags,
                       (SELECT body FROM sms_messages WHERE phone = sc.phone
                        ORDER BY sent_at DESC LIMIT 1) AS last_message
                FROM sms_conversations sc
                LEFT JOIN contacts c ON c.id = sc.contact_id
                {where}
                """,
                *args,
            )
            rows.extend(dict(r) for r in sms_rows)

        if channel in ("all", "email"):
            clauses = []
            args: list = []
            if since in _SINCE_INTERVAL:
                clauses.append(f"ec.updated_at >= now() - interval '{_SINCE_INTERVAL[since]}'")
            if tag:
                args.append(tag)
                clauses.append(f"${len(args)} = ANY(c.tags)")
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            email_rows = await conn.fetch(
                f"""
                SELECT 'email' AS channel, ec.thread_id AS thread_key, ec.status, ec.disposition, ec.updated_at,
                       c.business, c.owner, c.tags, ec.subject,
                       (SELECT body FROM email_messages WHERE thread_id = ec.thread_id
                        ORDER BY sent_at DESC LIMIT 1) AS last_message
                FROM email_conversations ec
                LEFT JOIN contacts c ON c.id = ec.contact_id
                {where}
                """,
                *args,
            )
            rows.extend(dict(r) for r in email_rows)

    rows.sort(key=lambda r: r["updated_at"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return rows
