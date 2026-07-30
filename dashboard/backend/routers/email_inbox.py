"""
Email Inbox router — Gmail polling sync + email-channel endpoints for the
unified Inbox tab (SMS + Email). Scope: only messages to/from an address
that matches an existing contacts.email value are synced — this is a
prospect-communication tool, not a general email client.

Endpoints (all under /api):
  GET  /api/email/conversations               — list email threads (channel-only, used internally)
  GET  /api/email/conversations/{thread_id}    — thread messages
  POST /api/email/send                         — reply / new thread
  POST /api/email/conversations/{thread_id}/close
  POST /api/email/conversations/{thread_id}/interested
  POST /api/email/sync                         — manual sync trigger (testing)
  GET  /api/inbox/tags                         — distinct contact tags, for the filter dropdown
  GET  /api/inbox/conversations                — contact-grouped SMS + Email list, filterable
  GET  /api/inbox/contact/{contact_id}         — one contact's merged SMS + Email message stream
  POST /api/inbox/contact/{contact_id}/close
  POST /api/inbox/contact/{contact_id}/stage   — set Replied/Engaged/Interested checkbox (manual override)
  DELETE /api/inbox/contact/{contact_id}

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


_BOUNCE_FROM_RE = re.compile(r"mailer-daemon|postmaster|mail delivery", re.I)
_BOUNCE_SUBJECT_RE = re.compile(
    r"delivery status notification|undelivered mail|delivery has failed|"
    r"returned to sender|delivery incomplete|address not found",
    re.I,
)


def _looks_like_bounce(from_addr: str, subject: str) -> bool:
    return bool(_BOUNCE_FROM_RE.search(from_addr or "") or _BOUNCE_SUBJECT_RE.search(subject or ""))


async def _mark_bounce(conn, full: dict, contact_by_email: dict) -> bool:
    """Best-effort: scan a delivery-failure notice's body for a known contact's
    address and mark that contact's most recent un-bounced outbound send as
    bounced. Gmail bounce notices always quote the original recipient
    somewhere in the body, but the exact format varies by failure type —
    this is a heuristic, not a guaranteed match."""
    body = (integrations._extract_body(full["payload"]) or full.get("snippet", "")).lower()
    for email, contact_id in contact_by_email.items():
        if email in body:
            result = await conn.execute(
                """UPDATE email_messages SET bounced_at = now()
                   WHERE id = (
                       SELECT id FROM email_messages
                       WHERE contact_id = $1 AND direction = 'outbound' AND bounced_at IS NULL
                       ORDER BY sent_at DESC LIMIT 1
                   )""",
                contact_id,
            )
            return result != "UPDATE 0"
    return False


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

        svc = await asyncio.to_thread(integrations._business_gmail_service)
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

            if _looks_like_bounce(from_addr, subject):
                await _mark_bounce(conn, full, contact_by_email)
                continue  # delivery-failure notices aren't real conversation messages

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
            """INSERT INTO email_messages (contact_id, thread_id, email, direction, subject, body, gmail_message_id, sent_at, tracking_token)
               VALUES ($1, $2, $3, 'outbound', $4, $5, $6, now(), $7)
               ON CONFLICT (gmail_message_id) DO NOTHING""",
            contact_id, new_thread_id, to, subject, body, sent["id"], sent.get("tracking_token"),
        )

    return {"ok": True, "thread_id": new_thread_id, "contact_id": contact_id}


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


# ── Merged Inbox (SMS + Email, grouped by contact) ────────────────────────────
#
# Both channels are threaded per-contact, not per-channel: one row per
# prospect in the thread list, and a single chronological message stream
# (each message tagged with its channel) in the detail view. This matches
# the mental model of "one conversation with this person," not "one
# conversation per communication method."

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


def _merge_contact_row(grouped: dict, r: dict, channel: str):
    cid = r["contact_id"]
    if not cid:
        return  # scope: only known-contact threads are ever synced/created
    g = grouped.get(cid)
    if not g:
        g = grouped[cid] = {
            "contact_id": cid, "business": r["business"], "owner": r["owner"],
            "phone": r["phone"], "email": r["email"], "tags": r["tags"] or [],
            "contact_status": r["contact_status"],
            "channels": [], "last_message": None, "updated_at": None,
            "status": "closed", "disposition": None, "unread": False,
            "stage_replied": False, "stage_engaged": False, "stage_interested": False,
        }
    if channel not in g["channels"]:
        g["channels"].append(channel)
    if g["updated_at"] is None or (r["updated_at"] and r["updated_at"] > g["updated_at"]):
        g["updated_at"] = r["updated_at"]
        g["last_message"] = r["last_message"]
    if r.get("unread"):
        g["unread"] = True
    if channel == "sms":
        g["stage_replied"] = g["stage_replied"] or bool(r.get("stage_replied"))
        g["stage_engaged"] = g["stage_engaged"] or bool(r.get("stage_engaged"))
        g["stage_interested"] = g["stage_interested"] or bool(r.get("stage_interested"))
    if r["status"] != "closed":
        g["status"] = "active"
        if channel == "email" and r["disposition"] == "interested":
            g["disposition"] = "interested"
    elif g["status"] == "closed" and g["disposition"] is None:
        g["disposition"] = r["disposition"]


@router.get("/inbox/conversations")
async def list_inbox_conversations(
    channel: str = "all",
    since: str = "all",
    tag: Optional[str] = None,
    contact_status: Optional[str] = None,
):
    pool = await get_pool()
    grouped: dict = {}
    async with pool.acquire() as conn:
        if channel in ("all", "sms"):
            clauses = ["sc.contact_id IS NOT NULL"]
            args: list = []
            if since in _SINCE_INTERVAL:
                clauses.append(f"sc.updated_at >= now() - interval '{_SINCE_INTERVAL[since]}'")
            if tag:
                args.append(tag)
                clauses.append(f"${len(args)} = ANY(c.tags)")
            if contact_status and contact_status != "all":
                args.append(contact_status)
                clauses.append(f"c.status = ${len(args)}")
            sms_rows = await conn.fetch(
                f"""
                SELECT sc.contact_id, sc.status, sc.disposition, sc.updated_at,
                       sc.stage_replied, sc.stage_engaged, sc.stage_interested,
                       c.business, c.owner, c.phone, c.email, c.tags, c.status AS contact_status,
                       (SELECT body FROM sms_messages WHERE phone = sc.phone
                        ORDER BY sent_at DESC LIMIT 1) AS last_message,
                       EXISTS (
                           SELECT 1 FROM sms_messages
                           WHERE phone = sc.phone AND direction = 'inbound'
                             AND sent_at > COALESCE(sc.last_read_at, '-infinity'::timestamptz)
                       ) AS unread
                FROM sms_conversations sc
                LEFT JOIN contacts c ON c.id = sc.contact_id
                WHERE {' AND '.join(clauses)}
                """,
                *args,
            )
            for r in sms_rows:
                _merge_contact_row(grouped, dict(r), "sms")

        if channel in ("all", "email"):
            clauses = ["ec.contact_id IS NOT NULL"]
            args = []
            if since in _SINCE_INTERVAL:
                clauses.append(f"ec.updated_at >= now() - interval '{_SINCE_INTERVAL[since]}'")
            if tag:
                args.append(tag)
                clauses.append(f"${len(args)} = ANY(c.tags)")
            if contact_status and contact_status != "all":
                args.append(contact_status)
                clauses.append(f"c.status = ${len(args)}")
            email_rows = await conn.fetch(
                f"""
                SELECT ec.contact_id, ec.status, ec.disposition, ec.updated_at,
                       c.business, c.owner, c.phone, c.email, c.tags, c.status AS contact_status,
                       (SELECT body FROM email_messages WHERE thread_id = ec.thread_id
                        ORDER BY sent_at DESC LIMIT 1) AS last_message,
                       EXISTS (
                           SELECT 1 FROM email_messages
                           WHERE thread_id = ec.thread_id AND direction = 'inbound'
                             AND sent_at > COALESCE(ec.last_read_at, '-infinity'::timestamptz)
                       ) AS unread
                FROM email_conversations ec
                LEFT JOIN contacts c ON c.id = ec.contact_id
                WHERE {' AND '.join(clauses)}
                """,
                *args,
            )
            for r in email_rows:
                _merge_contact_row(grouped, dict(r), "email")

    rows = list(grouped.values())
    rows.sort(key=lambda r: r["updated_at"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return rows


@router.get("/inbox/contact/{contact_id}")
async def get_contact_thread(contact_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        contact = await conn.fetchrow(
            "SELECT id, business, owner, phone, email, grade, tags FROM contacts WHERE id = $1", contact_id
        )
        if not contact:
            return {"contact_id": contact_id, "messages": []}

        sms_msgs = await conn.fetch(
            "SELECT direction, body, sent_at FROM sms_messages WHERE contact_id = $1 ORDER BY sent_at", contact_id
        )
        email_msgs = await conn.fetch(
            "SELECT direction, subject, body, sent_at FROM email_messages WHERE contact_id = $1 ORDER BY sent_at",
            contact_id,
        )
        sms_conv = await conn.fetchrow(
            """SELECT status, disposition, stage_replied, stage_engaged, stage_interested
               FROM sms_conversations WHERE contact_id = $1""",
            contact_id,
        )
        email_conv = await conn.fetchrow(
            """SELECT thread_id, subject, status, disposition FROM email_conversations
               WHERE contact_id = $1 ORDER BY updated_at DESC LIMIT 1""",
            contact_id,
        )

        await conn.execute("UPDATE sms_conversations SET last_read_at = now() WHERE contact_id = $1", contact_id)
        await conn.execute("UPDATE email_conversations SET last_read_at = now() WHERE contact_id = $1", contact_id)

    messages = [
        {"channel": "sms", "direction": m["direction"], "body": m["body"], "sent_at": m["sent_at"]}
        for m in sms_msgs
    ] + [
        {"channel": "email", "direction": m["direction"], "subject": m["subject"], "body": m["body"], "sent_at": m["sent_at"]}
        for m in email_msgs
    ]
    messages.sort(key=lambda m: m["sent_at"])

    sms_active = sms_conv and sms_conv["status"] != "closed"
    email_active = email_conv and email_conv["status"] != "closed"
    status = "active" if (sms_active or email_active) else "closed"
    if email_active and email_conv["disposition"] == "interested":
        disposition = "interested"
    elif status == "closed":
        disposition = (sms_conv["disposition"] if sms_conv else None) or (email_conv["disposition"] if email_conv else None)
    else:
        disposition = None

    return {
        "contact_id": contact_id,
        "business": contact["business"],
        "owner": contact["owner"],
        "grade": contact["grade"],
        "phone": contact["phone"],
        "email": contact["email"],
        "status": status,
        "disposition": disposition,
        "sms_status": sms_conv["status"] if sms_conv else None,
        "sms_disposition": sms_conv["disposition"] if sms_conv else None,
        "stage_replied": sms_conv["stage_replied"] if sms_conv else False,
        "stage_engaged": sms_conv["stage_engaged"] if sms_conv else False,
        "stage_interested": sms_conv["stage_interested"] if sms_conv else False,
        "email_thread_id": email_conv["thread_id"] if email_conv else None,
        "email_subject": email_conv["subject"] if email_conv else None,
        "email_status": email_conv["status"] if email_conv else None,
        "email_disposition": email_conv["disposition"] if email_conv else None,
        "messages": messages,
    }


@router.post("/inbox/contact/{contact_id}/close")
async def close_contact_threads(contact_id: str, payload: Optional[dict] = None):
    disposition = (payload or {}).get("disposition", "booked")
    if disposition not in _CLOSE_DISPOSITION_TO_CONTACT_STATUS:
        disposition = "booked"

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE sms_conversations SET status = 'closed', disposition = $2, updated_at = now() "
            "WHERE contact_id = $1 AND status != 'closed'",
            contact_id, disposition,
        )
        await conn.execute(
            "UPDATE email_conversations SET status = 'closed', disposition = $2, updated_at = now() "
            "WHERE contact_id = $1 AND status != 'closed'",
            contact_id, disposition,
        )
        await conn.execute(
            "UPDATE contacts SET status = $2, updated_at = now() WHERE id = $1",
            contact_id, _CLOSE_DISPOSITION_TO_CONTACT_STATUS[disposition],
        )
    return {"ok": True}


_STAGE_COLUMNS = {"replied", "engaged", "interested"}


@router.post("/inbox/contact/{contact_id}/stage")
async def set_contact_stage(contact_id: str, payload: dict):
    """
    Manual funnel checklist (Replied/Engaged/Interested) for the contact's SMS
    conversation. Any click through the UI is an explicit human override: it
    sets both the checkbox value and its `_manual` lock, so automatic
    reply-count detection (sms.py::_recompute_stage_flags) stops touching
    that stage for this conversation from here on — analytics reads the
    checkbox column directly, not the underlying reply count.
    """
    stage = (payload or {}).get("stage")
    checked = bool((payload or {}).get("checked"))
    if stage not in _STAGE_COLUMNS:
        return {"ok": False, "error": "stage must be one of replied/engaged/interested"}

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            f"""
            UPDATE sms_conversations
            SET stage_{stage} = $2, stage_{stage}_manual = true, updated_at = now()
            WHERE contact_id = $1
            """,
            contact_id, checked,
        )
    return {"ok": True, "stage": stage, "checked": checked}


@router.delete("/inbox/contact/{contact_id}")
async def delete_contact_threads(contact_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM sms_messages WHERE contact_id = $1", contact_id)
        await conn.execute("DELETE FROM sms_conversations WHERE contact_id = $1", contact_id)
        await conn.execute("DELETE FROM email_messages WHERE contact_id = $1", contact_id)
        await conn.execute("DELETE FROM email_conversations WHERE contact_id = $1", contact_id)
    return {"ok": True}
