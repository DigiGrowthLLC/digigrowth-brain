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
  POST /api/inbox/contact/{contact_id}/stage   — set a stage checkbox (manual override); see
                                                  set_contact_stage()'s docstring for the full list,
                                                  including Not Interested (no dedicated button anymore)
  DELETE /api/inbox/contact/{contact_id}

sync_gmail_job() is registered on the app's APScheduler (main.py) to run
every ~60s. It never raises — a bad poll just logs and waits for the next tick.
"""

import asyncio
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException

import integrations
import cancel_sequence
import no_show_sequence
from db import get_pool
from routers.campaigns import resolve_send_campaign

router = APIRouter()

SYNC_CURSOR_KEY = "email_sync_last_ts"
SYNC_LOOKBACK_SEC = 120  # overlap window so a message straddling a poll boundary is never missed

_CLOSE_DISPOSITION_TO_CONTACT_STATUS = {
    "booked":         "appointment-booked",
    "not_interested": "not-interested",
}


_ALL_EMAILS_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


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

async def _sync_gmail_once(sent_backfill_days: int | None = None) -> dict:
    """sent_backfill_days: one-off pass over the last N days of Sent mail
    only (Gmail replies sent before outbound sync existed); the cursor
    still only ever moves forward."""
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
        # Our own mailboxes (this account, outreach identities, warm-up
        # partners) can end up stored as a contact's email (a test contact,
        # a self entry) — never treat them as a prospect, or every email
        # Dylan sends would land in the Inbox as that "prospect" writing in.
        own = {integrations.EXPECTED_SENDER_EMAIL.lower()} | {
            r["mailbox_email"].lower() for r in await conn.fetch("SELECT mailbox_email FROM email_send_identities")
        }
        contact_by_email = {
            c["email"].strip().lower(): c["id"] for c in contacts
            if c["email"] and c["email"].strip() and c["email"].strip().lower() not in own
        }
        if not contact_by_email:
            return {"fetched": 0, "matched": 0, "skipped": 0}

        cursor_row = await conn.fetchrow("SELECT value FROM dialer_settings WHERE key = $1", SYNC_CURSOR_KEY)
        last_ts = int(cursor_row["value"]) if cursor_row and cursor_row["value"] else 0
        query_after = max(0, last_ts - SYNC_LOOKBACK_SEC)

        svc = await asyncio.to_thread(integrations._business_gmail_service)
        q = f"after:{query_after}" if query_after else "newer_than:7d"
        if sent_backfill_days:
            q = f"in:sent newer_than:{int(sent_backfill_days)}d"
        res = await asyncio.to_thread(
            lambda: svc.users().messages().list(userId="me", q=q, maxResults=500 if sent_backfill_days else 100).execute()
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

            # Scope: messages sent BY a known prospect, plus mail Dylan sent
            # TO one straight from Gmail (Sent label) — so a reply typed in
            # Gmail shows in the Inbox thread too. Sends made through the
            # Inbox's reply box are already recorded by /email/send under
            # this same Gmail message id, so the exists check above skips
            # them. Own addresses were dropped from contact_by_email, so the
            # account's own mail can never match as a "prospect".
            contact_id, counterparty, direction = None, None, None
            if from_addr and from_addr in contact_by_email:
                contact_id, counterparty, direction = contact_by_email[from_addr], from_addr, "inbound"
            elif "SENT" in full.get("labelIds", []):
                recipients = _ALL_EMAILS_RE.findall(f"{headers.get('to', '')},{headers.get('cc', '')}".lower())
                to_addr = next((a for a in recipients if a in contact_by_email), None)
                if to_addr:
                    contact_id, counterparty, direction = contact_by_email[to_addr], to_addr, "outbound"
            if not contact_id:
                continue  # not to/from a known prospect — skip per scope rule

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
            if direction == "inbound":
                await no_show_sequence.stop_sequence_for_reply(email=counterparty)
                await cancel_sequence.stop_sequence_for_reply(email=counterparty)

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
async def manual_sync(sent_backfill_days: Optional[int] = None):
    """Manual trigger for testing/verification — same code path as the scheduled job.
    ?sent_backfill_days=N also pulls in the last N days of Gmail Sent mail to prospects."""
    return {"ok": True, **(await _sync_gmail_once(sent_backfill_days))}


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
            WHERE c.client_id IS NULL OR c.is_client_anchor
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


async def _send_on_identity_thread(thread_id: str, to: str, subject: str, body: str) -> dict:
    """Inbox reply on an Email Handoff thread ("identity-{identity_id}-{contact_id}",
    see email_handoff_sequence._record_outbound). The lead is talking to that
    cold-outreach identity mailbox, not the business Gmail, so the reply
    must go out from the same identity — the business Gmail has no such
    thread (its API rejects the synthetic thread id) and a different From
    address would break the conversation for the lead."""
    import email_identities

    try:
        identity_id = int(thread_id.split("-", 2)[1])
    except (IndexError, ValueError):
        return {"ok": False, "error": f"malformed identity thread id: {thread_id}"}

    pool = await get_pool()
    async with pool.acquire() as conn:
        identity = await conn.fetchrow("SELECT * FROM email_send_identities WHERE id = $1", identity_id)
        contact_row = await conn.fetchrow(
            "SELECT id, email_opted_out FROM contacts WHERE lower(email) = lower($1)", to,
        )
    if not identity:
        return {"ok": False, "error": f"sending identity {identity_id} no longer exists"}
    if contact_row and contact_row["email_opted_out"]:
        return {"ok": False, "error": f"{to} has unsubscribed from outreach email."}

    reply_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    try:
        message_id = await email_identities.send_from_identity(dict(identity), to, reply_subject, body)
    except Exception as e:
        return {"ok": False, "error": str(e)}

    contact_id = contact_row["id"] if contact_row else None
    if not message_id:
        message_id = f"graph-{uuid.uuid4().hex}"  # Graph sendMail returns no id
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE email_conversations SET updated_at = now() WHERE thread_id = $1", thread_id,
        )
        await conn.execute(
            """INSERT INTO email_messages (contact_id, thread_id, email, direction, subject, body, gmail_message_id, sent_at)
               VALUES ($1, $2, $3, 'outbound', $4, $5, $6, now())
               ON CONFLICT (gmail_message_id) DO NOTHING""",
            contact_id, thread_id, to, reply_subject, body, message_id,
        )
    return {"ok": True, "thread_id": thread_id, "contact_id": contact_id}


@router.post("/email/send")
async def manual_email_send(payload: dict):
    thread_id = (payload.get("thread_id") or "").strip()
    to        = (payload.get("to") or "").strip()
    subject   = (payload.get("subject") or "").strip() or "(no subject)"
    body      = (payload.get("body") or "").strip()
    if not to or not body:
        return {"ok": False, "error": "to and body required"}

    if thread_id.startswith("identity-"):
        return await _send_on_identity_thread(thread_id, to, subject, body)

    try:
        sent = await asyncio.to_thread(integrations.gmail_send_reply, to, subject, body, thread_id)
    except Exception as e:
        return {"ok": False, "error": str(e)}

    new_thread_id = sent["threadId"]

    pool = await get_pool()
    async with pool.acquire() as conn:
        contact_row = await conn.fetchrow("SELECT id FROM contacts WHERE lower(email) = lower($1)", to)
        contact_id = contact_row["id"] if contact_row else None
        if payload.get("compose"):
            # New Message box: same as /sms/send — a new address gets a
            # contact so the thread lists in the Inbox and replies sync.
            from routers.sms import ensure_compose_contact
            contact_id = await ensure_compose_contact(
                conn, email=to, owner=payload.get("owner"), business=payload.get("business"),
            )

        # Each individual send is tagged with whichever campaign is active
        # right now (a CRM-assigned pending campaign for this contact takes
        # priority — see campaigns.py::resolve_send_campaign) — total-outreach
        # counts must only include messages actually sent while a campaign
        # was active, not every message ever sent on a thread whose
        # conversation later got tagged. The conversation-level tag below
        # ("this prospect belongs to campaign X") is separate and only set
        # once, on the thread's first outbound send.
        active_campaign_id = await resolve_send_campaign(conn, "email", contact_id)

        conv = await conn.fetchrow("SELECT id FROM email_conversations WHERE thread_id = $1", new_thread_id)
        if not conv:
            await conn.execute(
                """INSERT INTO email_conversations (contact_id, thread_id, email, subject, status, campaign_id)
                   VALUES ($1, $2, $3, $4, 'active', $5)""",
                contact_id, new_thread_id, to, subject, active_campaign_id,
            )
        else:
            await conn.execute(
                "UPDATE email_conversations SET updated_at = now() WHERE thread_id = $1", new_thread_id
            )

        await conn.execute(
            """INSERT INTO email_messages (contact_id, thread_id, email, direction, subject, body, gmail_message_id, sent_at, tracking_token, campaign_id)
               VALUES ($1, $2, $3, 'outbound', $4, $5, $6, now(), $7, $8)
               ON CONFLICT (gmail_message_id) DO NOTHING""",
            contact_id, new_thread_id, to, subject, body, sent["id"], sent.get("tracking_token"), active_campaign_id,
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
    """
    `updated_at` here drives the Inbox's sort order, so it must reflect the
    conversation's actual last message activity (last_message_at, from the
    per-channel messages table) — NOT the conversation row's own updated_at
    column, which also bumps on metadata-only changes (a campaign
    assignment, a disposition edit, etc.) that aren't new outreach and
    shouldn't reorder the list.
    """
    cid = r["contact_id"]
    if not cid:
        return  # scope: only known-contact threads are ever synced/created
    g = grouped.get(cid)
    if not g:
        g = grouped[cid] = {
            "contact_id": cid, "business": r["business"], "owner": r["owner"],
            "phone": r["phone"], "email": r["email"], "tags": r["tags"] or [],
            "contact_status": r["contact_status"], "client_id": r.get("client_id"),
            "channels": [], "last_message": None, "updated_at": None,
            "status": "closed", "disposition": None, "unread": False,
            "stage_initial_outreach": False, "stage_replied": False, "stage_dm_reached": False,
            "stage_primed": False, "stage_engaged": False, "stage_interested": False,
            "is_email_handoff": r["contact_status"] == "email-handoff",
            "email_handoff_touch1_sent_at": None, "email_handoff_touch2_sent_at": None,
            "email_handoff_touch3_sent_at": None, "email_stage_replied": False,
        }
    if channel not in g["channels"]:
        g["channels"].append(channel)
    if g["updated_at"] is None or (r["last_message_at"] and r["last_message_at"] > g["updated_at"]):
        g["updated_at"] = r["last_message_at"]
        # Which conversation holds the newest message — its body is fetched
        # afterwards, only for the page of rows actually returned.
        g["_last_key"] = (channel, r["conv_phone"] if channel == "sms" else r["thread_id"])
    if r.get("unread"):
        g["unread"] = True
    if channel == "sms":
        g["stage_initial_outreach"] = g["stage_initial_outreach"] or bool(r.get("stage_initial_outreach"))
        g["stage_replied"] = g["stage_replied"] or bool(r.get("stage_replied"))
        g["stage_dm_reached"] = g["stage_dm_reached"] or bool(r.get("stage_dm_reached"))
        g["stage_primed"] = g["stage_primed"] or bool(r.get("stage_primed"))
        g["stage_engaged"] = g["stage_engaged"] or bool(r.get("stage_engaged"))
        g["stage_interested"] = g["stage_interested"] or bool(r.get("stage_interested"))
    if r["disposition"] and not g["disposition"]:
        g["disposition"] = r["disposition"]
    if r["status"] != "closed":
        g["status"] = "active"
    if channel == "email" and r["disposition"] == "interested":
        g["disposition"] = "interested"


def _merge_email_handoff_row(grouped: dict, r: dict):
    """Layers Email Handoff sequence progress onto an already-grouped
    contact row (created by the sms/email blocks above) — a contact only
    ever reaches "email-handoff" status after existing in the Inbox via one
    of those channels already, so this never needs to create a fresh row."""
    cid = r["contact_id"]
    g = grouped.get(cid)
    if not g:
        return
    g["is_email_handoff"] = True
    g["email_handoff_touch1_sent_at"] = r["touch1_sent_at"]
    g["email_handoff_touch2_sent_at"] = r["touch2_sent_at"]
    g["email_handoff_touch3_sent_at"] = r["touch3_sent_at"]
    g["email_stage_replied"] = bool(r["stage_replied"])


@router.get("/email/sequence/{contact_id}")
async def get_email_sequence(contact_id: str):
    """Mirrors GET /sms/sequence/{phone} for the email channel — backs the
    Inbox compose box's SEQUENCE button when replying by email, letting a
    rep manually pick one of the 3 Email Handoff touches regardless of the
    contact's current enrollment/status (same as the SMS version isn't
    gated on sms-handoff status either)."""
    import email_handoff_sequence

    pool = await get_pool()
    async with pool.acquire() as conn:
        contact = await conn.fetchrow(
            """SELECT c.owner, c.business, c.opener, ehs.loom_url FROM contacts c
               LEFT JOIN email_handoff_state ehs ON ehs.contact_id = c.id WHERE c.id = $1""",
            contact_id,
        )

    contact_dict = dict(contact) if contact else {}
    templates = await email_handoff_sequence._get_templates()
    steps = []
    for instance in ("touch1", "touch2", "touch3"):
        subject = (templates.get(f"email_handoff_{instance}_subject") or "").strip()
        body = (templates.get(f"email_handoff_{instance}_body") or "").strip()
        if not body:
            continue
        steps.append({
            "key": instance,
            "label": {"touch1": "Touch 1", "touch2": "Touch 2", "touch3": "Touch 3"}[instance],
            "subject": email_handoff_sequence._fill(subject, contact_dict),
            "text": email_handoff_sequence._fill(body, contact_dict),
        })

    return {"ok": True, "sequence_title": "Email Handoff", "steps": steps}


_PREVIEW_CHARS = 300


@router.get("/inbox/conversations")
async def list_inbox_conversations(
    channel: str = "all",
    since: str = "all",
    tag: Optional[str] = None,
    contact_status: Optional[str] = None,
    stage: Optional[str] = None,
    q: Optional[str] = None,
    read: str = "all",
    limit: int = 100,
    offset: int = 0,
):
    """One page of the contact-grouped Inbox list, newest activity first.

    Returns {rows, total, unread_count}: `total` counts every match for the
    filters (so the UI can offer LOAD MORE), `unread_count` ignores the
    `read` filter (it labels the UNREAD tab). The grouping/sorting runs over
    every matching conversation using only indexed timestamps; message
    bodies are fetched for the returned page alone.
    """
    pool = await get_pool()
    grouped: dict = {}
    term = (q or "").strip().lower()
    digits = re.sub(r"\D", "", term)
    async with pool.acquire() as conn:
        # Search also matches any message text (not just the newest), so an
        # old thread is findable by what was said in it.
        text_hits: set = set()
        if term:
            hit_rows = await conn.fetch(
                """
                SELECT contact_id FROM sms_messages WHERE contact_id IS NOT NULL AND body ILIKE $1
                UNION
                SELECT contact_id FROM email_messages WHERE contact_id IS NOT NULL AND body ILIKE $1
                """,
                f"%{term}%",
            )
            text_hits = {r["contact_id"] for r in hit_rows}

        if channel in ("all", "sms"):
            # A client's own portal-managed lead (client_id set, not the
            # anchor) shouldn't show up mixed into Dylan's internal Inbox —
            # same exclusion as crm.py/dialer.py/analytics.py.
            clauses = ["sc.contact_id IS NOT NULL", "(c.client_id IS NULL OR c.is_client_anchor)"]
            args: list = []
            if since in _SINCE_INTERVAL:
                clauses.append(f"lm.last_message_at >= now() - interval '{_SINCE_INTERVAL[since]}'")
            if tag:
                args.append(tag)
                clauses.append(f"${len(args)} = ANY(c.tags)")
            if contact_status and contact_status != "all":
                args.append(contact_status)
                clauses.append(f"c.status = ${len(args)}")
            if stage == "not_interested":
                clauses.append("sc.disposition = 'not_interested'")
            elif stage in _STAGE_COLUMNS:
                clauses.append(f"sc.stage_{stage} = true")
            sms_rows = await conn.fetch(
                f"""
                SELECT sc.contact_id, sc.status, sc.disposition, sc.phone AS conv_phone,
                       sc.stage_initial_outreach, sc.stage_replied, sc.stage_dm_reached, sc.stage_primed, sc.stage_engaged, sc.stage_interested,
                       c.business, c.owner, c.phone, c.email, c.tags, c.status AS contact_status, c.client_id,
                       lm.last_message_at,
                       EXISTS (
                           SELECT 1 FROM sms_messages
                           WHERE phone = sc.phone AND direction = 'inbound'
                             AND sent_at > COALESCE(sc.last_read_at, '-infinity'::timestamptz)
                       ) AS unread
                FROM sms_conversations sc
                LEFT JOIN contacts c ON c.id = sc.contact_id
                LEFT JOIN LATERAL (
                    SELECT MAX(sent_at) AS last_message_at FROM sms_messages WHERE phone = sc.phone
                ) lm ON true
                WHERE {' AND '.join(clauses)}
                """,
                *args,
            )
            for r in sms_rows:
                _merge_contact_row(grouped, dict(r), "sms")

        # Stage checkboxes (initial_outreach/replied/dm_reached/primed/engaged/interested) only
        # exist on sms_conversations, so an active stage filter (other than not_interested,
        # which is disposition-based on both channels) excludes email entirely.
        if channel in ("all", "email") and not (stage and stage != "not_interested"):
            clauses = ["ec.contact_id IS NOT NULL", "(c.client_id IS NULL OR c.is_client_anchor)"]
            args = []
            if since in _SINCE_INTERVAL:
                clauses.append(f"lm.last_message_at >= now() - interval '{_SINCE_INTERVAL[since]}'")
            if tag:
                args.append(tag)
                clauses.append(f"${len(args)} = ANY(c.tags)")
            if contact_status and contact_status != "all":
                args.append(contact_status)
                clauses.append(f"c.status = ${len(args)}")
            if stage == "not_interested":
                clauses.append("ec.disposition = 'not_interested'")
            email_rows = await conn.fetch(
                f"""
                SELECT ec.contact_id, ec.status, ec.disposition, ec.thread_id,
                       c.business, c.owner, c.phone, c.email, c.tags, c.status AS contact_status, c.client_id,
                       lm.last_message_at,
                       EXISTS (
                           SELECT 1 FROM email_messages
                           WHERE thread_id = ec.thread_id AND direction = 'inbound'
                             AND sent_at > COALESCE(ec.last_read_at, '-infinity'::timestamptz)
                       ) AS unread
                FROM email_conversations ec
                LEFT JOIN contacts c ON c.id = ec.contact_id
                LEFT JOIN LATERAL (
                    SELECT MAX(sent_at) AS last_message_at FROM email_messages WHERE thread_id = ec.thread_id
                ) lm ON true
                WHERE {' AND '.join(clauses)}
                """,
                *args,
            )
            for r in email_rows:
                _merge_contact_row(grouped, dict(r), "email")

        rows = list(grouped.values())
        if term:
            def _matches(g):
                if g["contact_id"] in text_hits:
                    return True
                hay = " ".join(filter(None, [g["owner"], g["business"], g["email"]])).lower()
                if term in hay:
                    return True
                return len(digits) >= 3 and digits in re.sub(r"\D", "", g["phone"] or "")
            rows = [g for g in rows if _matches(g)]
        unread_count = sum(1 for g in rows if g["unread"])
        if read == "unread":
            rows = [g for g in rows if g["unread"]]
        elif read == "read":
            rows = [g for g in rows if not g["unread"]]
        rows.sort(key=lambda r: r["updated_at"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        total = len(rows)
        page = rows[max(offset, 0): max(offset, 0) + max(1, min(limit, 500))]

        if page:
            handoff_rows = await conn.fetch(
                """
                SELECT contact_id, touch1_sent_at, touch2_sent_at, touch3_sent_at, stage_replied
                FROM email_handoff_state WHERE contact_id = ANY($1::text[])
                """,
                [g["contact_id"] for g in page],
            )
            for r in handoff_rows:
                _merge_email_handoff_row(grouped, dict(r))

            # Last-message previews, for this page only (one indexed lookup
            # per conversation, truncated — email bodies can be large HTML).
            keys = [g.get("_last_key") for g in page]
            sms_keys = [k[1] for k in keys if k and k[0] == "sms"]
            email_keys = [k[1] for k in keys if k and k[0] == "email"]
            previews: dict = {}
            if sms_keys:
                for r in await conn.fetch(
                    f"""SELECT DISTINCT ON (phone) phone, left(body, {_PREVIEW_CHARS}) AS body
                        FROM sms_messages WHERE phone = ANY($1::text[]) ORDER BY phone, sent_at DESC""",
                    sms_keys,
                ):
                    previews[("sms", r["phone"])] = r["body"]
            if email_keys:
                for r in await conn.fetch(
                    f"""SELECT DISTINCT ON (thread_id) thread_id, left(body, {_PREVIEW_CHARS}) AS body
                        FROM email_messages WHERE thread_id = ANY($1::text[]) ORDER BY thread_id, sent_at DESC""",
                    email_keys,
                ):
                    previews[("email", r["thread_id"])] = r["body"]
            for g in page:
                g["last_message"] = previews.get(g.get("_last_key"))

    for g in page:
        g.pop("_last_key", None)
    return {"rows": page, "total": total, "unread_count": unread_count}


@router.get("/inbox/contact/{contact_id}")
async def get_contact_thread(contact_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        contact = await conn.fetchrow(
            "SELECT id, business, owner, phone, email, grade, tags, status FROM contacts WHERE id = $1", contact_id
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
            """SELECT status, disposition, stage_initial_outreach, stage_replied, stage_dm_reached, stage_primed, stage_engaged, stage_interested
               FROM sms_conversations WHERE contact_id = $1""",
            contact_id,
        )
        email_conv = await conn.fetchrow(
            """SELECT thread_id, subject, status, disposition FROM email_conversations
               WHERE contact_id = $1 ORDER BY updated_at DESC LIMIT 1""",
            contact_id,
        )
        email_handoff = await conn.fetchrow(
            """SELECT enrolled_at, touch1_sent_at, touch2_sent_at, touch3_sent_at,
                      stage_replied, stage_replied_manual, stage_replied_at
               FROM email_handoff_state WHERE contact_id = $1""",
            contact_id,
        )
        email_stages = await conn.fetchrow(
            "SELECT stage_replied, stage_engaged, stage_interested FROM email_contact_stages WHERE contact_id = $1",
            contact_id,
        )
        has_real_email_reply = bool(await conn.fetchval(
            "SELECT 1 FROM email_messages WHERE contact_id = $1 AND direction = 'inbound' AND NOT is_auto_reply LIMIT 1",
            contact_id,
        ))

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

    # Email Replied: a rep's explicit tick wins; otherwise automatic (a real
    # inbound email, or the handoff sequence having flagged a reply).
    if email_stages and email_stages["stage_replied"] is not None:
        email_replied = email_stages["stage_replied"]
    else:
        email_replied = has_real_email_reply or bool(email_handoff and email_handoff["stage_replied"])

    sms_active = sms_conv and sms_conv["status"] != "closed"
    email_active = email_conv and email_conv["status"] != "closed"
    # No conversation on either channel yet (e.g. jumping here from the CRM
    # contact card before any outreach) is a fresh thread, not a closed one.
    status = "closed" if (sms_conv or email_conv) and not (sms_active or email_active) else "active"
    disposition = (sms_conv["disposition"] if sms_conv else None) or (email_conv["disposition"] if email_conv else None)
    if email_active and email_conv["disposition"] == "interested":
        disposition = "interested"

    return {
        "contact_id": contact_id,
        "business": contact["business"],
        "owner": contact["owner"],
        "grade": contact["grade"],
        "phone": contact["phone"],
        "email": contact["email"],
        "contact_status": contact["status"],
        "status": status,
        "disposition": disposition,
        "sms_status": sms_conv["status"] if sms_conv else None,
        "sms_disposition": sms_conv["disposition"] if sms_conv else None,
        "stage_initial_outreach": sms_conv["stage_initial_outreach"] if sms_conv else False,
        "stage_replied": sms_conv["stage_replied"] if sms_conv else False,
        "stage_dm_reached": sms_conv["stage_dm_reached"] if sms_conv else False,
        "stage_primed": sms_conv["stage_primed"] if sms_conv else False,
        "stage_engaged": sms_conv["stage_engaged"] if sms_conv else False,
        "stage_interested": sms_conv["stage_interested"] if sms_conv else False,
        "email_thread_id": email_conv["thread_id"] if email_conv else None,
        "email_subject": email_conv["subject"] if email_conv else None,
        "email_status": email_conv["status"] if email_conv else None,
        "email_disposition": email_conv["disposition"] if email_conv else None,
        # Email Handoff sequence progress — the frontend shows THESE instead
        # of the stage_* fields above when contact_status == "email-handoff"
        # (see SOPsPanel.jsx/InboxPanel.jsx). touch1/2/3_sent_at are
        # automatic progress markers (not rep-editable); email_stage_replied
        # is the one manually-toggleable checkbox, set via
        # POST /inbox/contact/{id}/stage {stage: "email_replied"}.
        "is_email_handoff": contact["status"] == "email-handoff",
        "email_handoff_enrolled_at": email_handoff["enrolled_at"] if email_handoff else None,
        "email_handoff_touch1_sent_at": email_handoff["touch1_sent_at"] if email_handoff else None,
        "email_handoff_touch2_sent_at": email_handoff["touch2_sent_at"] if email_handoff else None,
        "email_handoff_touch3_sent_at": email_handoff["touch3_sent_at"] if email_handoff else None,
        "email_stage_replied": email_replied,
        "email_stage_replied_at": email_handoff["stage_replied_at"] if email_handoff else None,
        # Email-channel stages (email_contact_stages) — shown in the Inbox's
        # stage menu while the Email reply channel is selected.
        "email_handoff_enrolled": email_handoff is not None,
        "email_stage_engaged": bool(email_stages and email_stages["stage_engaged"]),
        "email_stage_interested": bool(email_stages and email_stages["stage_interested"]),
        "messages": messages,
    }


_STAGE_COLUMNS = {"initial_outreach", "replied", "dm_reached", "primed", "engaged", "interested"}


@router.post("/inbox/contact/{contact_id}/stage")
async def set_contact_stage(contact_id: str, payload: dict):
    """
    Manual funnel checklist (Initial Outreach/Replied/DM Reached/Primed/
    Engaged/Interested/Not Interested) for the contact's SMS conversation.
    Any click through the UI is an explicit human override: it sets both the
    checkbox value and its `_manual` lock, so automatic detection — reply-
    count based for Replied/Primed/Engaged/Interested
    (sms.py::_recompute_stage_flags), first-outbound-send based for Initial
    Outreach (sms.py::_store_message) — stops touching that stage for this
    conversation from here on — analytics reads the checkbox column
    directly, not the underlying send/reply activity. DM Reached has no
    automatic detection at all — it's always and only set by a human
    clicking this checkbox.

    Not Interested is handled separately below: unlike the others it isn't
    backed by its own stage_* boolean — checking it sets the same
    sms_conversations/email_conversations.disposition and contacts.status
    that Analytics' Not Interested rate already reads (previously only
    reachable via the Inbox's now-removed standalone button, which also
    used to close the thread — this checkbox never does), and unchecking it
    clears the disposition back to null and returns the contact to
    'dialer-lead'.
    """
    stage = (payload or {}).get("stage")
    checked = bool((payload or {}).get("checked"))

    if stage == "not_interested":
        disposition = "not_interested" if checked else None
        pool = await get_pool()
        async with pool.acquire() as conn:
            # dm_followup_sequence.py's poller already excludes any row with
            # disposition IS NOT NULL, so this alone stops a live cycle from
            # sending again — but checking Not Interested here also hard-clears
            # enrollment itself (dm_followup_enrolled_at + the in-flight
            # anchor/touch columns), not just relies on the disposition
            # filter, so there's no stale enrollment state sitting around
            # that a later disposition change could silently reactivate. See
            # POST /inbox/contact/{contact_id}/dm-followup's docstring — it
            # refuses to (re-)enroll anyone currently dispositioned, so a rep
            # can't accidentally re-add a Not Interested prospect either.
            await conn.execute(
                """
                UPDATE sms_conversations SET disposition = $2, updated_at = now()""" + (
                    ", dm_followup_enrolled_at = NULL, dm_followup_anchor_at = NULL, "
                    "dm_followup_touch1_sent_at = NULL, dm_followup_touch2_sent_at = NULL, "
                    "dm_followup_touch3_sent_at = NULL" if checked else ""
                ) + " WHERE contact_id = $1",
                contact_id, disposition,
            )
            await conn.execute(
                "UPDATE email_conversations SET disposition = $2, updated_at = now() WHERE contact_id = $1",
                contact_id, disposition,
            )
            await conn.execute(
                "UPDATE contacts SET status = $2, updated_at = now() WHERE id = $1",
                contact_id, "not-interested" if checked else "dialer-lead",
            )
        return {"ok": True, "stage": stage, "checked": checked}

    if stage in ("email_engaged", "email_interested"):
        # Email-channel funnel stages (email_contact_stages). Engaged or
        # Interested = a positive reply in Email analytics.
        col = stage.removeprefix("email_")
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                f"""
                INSERT INTO email_contact_stages (contact_id, stage_{col}, stage_{col}_at, updated_at)
                VALUES ($1, $2, CASE WHEN $2 THEN now() END, now())
                ON CONFLICT (contact_id) DO UPDATE SET
                    stage_{col} = $2, stage_{col}_at = CASE WHEN $2 THEN now() END, updated_at = now()
                """,
                contact_id, checked,
            )
        return {"ok": True, "stage": stage, "checked": checked}

    if stage == "email_replied":
        # Email-channel Replied. Stored on email_contact_stages (explicit
        # override of the automatic real-reply detection) AND, for a contact
        # in the Email Handoff sequence, on email_handoff_state as a manual
        # override — which is what stops the sequence's remaining touches.
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO email_contact_stages (contact_id, stage_replied, stage_replied_at, updated_at)
                VALUES ($1, $2, CASE WHEN $2 THEN now() END, now())
                ON CONFLICT (contact_id) DO UPDATE SET
                    stage_replied = $2, stage_replied_at = CASE WHEN $2 THEN now() END, updated_at = now()
                """,
                contact_id, checked,
            )
            await conn.execute(
                """
                UPDATE email_handoff_state
                SET stage_replied = $2, stage_replied_manual = true,
                    stage_replied_at = CASE WHEN $2 THEN now() ELSE NULL END, updated_at = now()
                WHERE contact_id = $1
                """,
                contact_id, checked,
            )
        return {"ok": True, "stage": stage, "checked": checked}

    if stage not in _STAGE_COLUMNS:
        return {"ok": False, "error": "stage must be one of initial_outreach/replied/dm_reached/primed/engaged/interested/not_interested/email_replied/email_engaged/email_interested"}

    pool = await get_pool()
    async with pool.acquire() as conn:
        if stage == "dm_reached":
            # Analytics-only as of 2026-09-22 — this checkbox used to be the
            # ONLY control for the DM Follow-Up sequence's enrollment
            # (checking it stamped dm_followup_enrolled_at, unchecking it
            # cleared enrollment and the in-flight cycle), which meant the
            # sole way to stop an unwanted follow-up cycle was to uncheck DM
            # Reached — corrupting the DM-Reached-rate analytics that same
            # checkbox feeds (analytics.py's _sms_metrics reads stage_dm_reached
            # /stage_dm_reached_at directly). Reported live 2026-09-22.
            #
            # Enrollment now lives entirely behind its own control — see
            # POST /inbox/contact/{contact_id}/dm-followup below — and this
            # branch only ever touches stage_dm_reached/stage_dm_reached_at.
            # It deliberately does NOT stamp or clear dm_followup_enrolled_at
            # (or the anchor/touch columns) in either direction anymore, so
            # correcting an accidental click here can never silently start or
            # stop a live follow-up cycle, and vice versa.
            await conn.execute(
                """
                UPDATE sms_conversations
                SET stage_dm_reached = $2, stage_dm_reached_manual = true,
                    stage_dm_reached_at = CASE WHEN $2 THEN now() ELSE NULL END, updated_at = now()
                WHERE contact_id = $1
                """,
                contact_id, checked,
            )
        else:
            # Analytics narrows Replied/Primed/Engaged/Interested to a period
            # using stage_{stage}_at (see analytics.py::_sms_metrics) — stamp
            # it whenever this checkbox is set, clear it when unset. Initial
            # Outreach has no _at column (Total Outreach is already message-
            # count based and genuinely timestamped, so it doesn't need one).
            at_clause = f", stage_{stage}_at = " + ("now()" if checked else "NULL") if stage != "initial_outreach" else ""
            await conn.execute(
                f"""
                UPDATE sms_conversations
                SET stage_{stage} = $2, stage_{stage}_manual = true{at_clause}, updated_at = now()
                WHERE contact_id = $1
                """,
                contact_id, checked,
            )
    return {"ok": True, "stage": stage, "checked": checked}


@router.post("/inbox/contact/{contact_id}/dm-followup")
async def set_dm_followup_active(contact_id: str, payload: dict):
    """
    Dedicated start/stop control for the DM Follow-Up sequence
    (dm_followup_sequence.py), independent of the "DM Reached" analytics
    checkbox above — see that branch's comment for why they used to be the
    same action and why that broke analytics. dm_followup_enrolled_at is
    now the sole thing dm_followup_sequence.py's poller (and dialer.py's
    dm-followup-active queue) check for "is this cycle live"; whether
    stage_dm_reached is also checked no longer matters to either.

    active=true enrolls (idempotent — COALESCE keeps an existing enrollment's
    original timestamp rather than restarting the clock). Refuses to enroll
    a Not Interested contact. A booked one CAN be enrolled from here (Dylan,
    2026-10-16: a booked prospect is never auto-enrolled, but adding them by
    hand from the Inbox's Sequences panel must work) — every automatic path
    (dm_followup_sequence.auto_enroll, sms.py's AI-setter send) still
    requires disposition IS NULL, and booking clears any live enrollment, so
    a booked thread is only ever enrolled because someone clicked ADD here.
    The poller and the dialer queue accept disposition 'booked' for that.

    active=false unenrolls and clears the in-flight cycle (anchor + all
    touch-sent columns) so a later re-enroll starts a fresh 24h countdown
    rather than resuming mid-cycle.
    """
    active = bool((payload or {}).get("active"))
    pool = await get_pool()
    async with pool.acquire() as conn:
        conv = await conn.fetchrow(
            "SELECT disposition, stage_dm_reached FROM sms_conversations WHERE contact_id = $1", contact_id,
        )
        if not conv:
            raise HTTPException(status_code=404, detail="No SMS conversation for this contact")
        if active:
            # The sequence never sends before DM Reached (dm_followup_sequence's
            # docstring), so an ADD here would just sit — say so instead.
            if not conv["stage_dm_reached"]:
                raise HTTPException(
                    status_code=400,
                    detail="DM Follow-Up only runs once the owner is reached. Check DM Reached first.",
                )
            if conv["disposition"] not in (None, "booked"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Contact is dispositioned '{conv['disposition']}' — cannot enroll in DM Follow-Up",
                )
            await conn.execute(
                "UPDATE sms_conversations SET dm_followup_enrolled_at = COALESCE(dm_followup_enrolled_at, now()), "
                "dm_followup_stopped_at = NULL, updated_at = now() WHERE contact_id = $1",
                contact_id,
            )
        else:
            # dm_followup_stopped_at keeps dm_followup_sequence's auto-enroll
            # from putting the thread straight back in.
            await conn.execute(
                """
                UPDATE sms_conversations
                SET dm_followup_enrolled_at = NULL, dm_followup_anchor_at = NULL,
                    dm_followup_touch1_sent_at = NULL, dm_followup_touch2_sent_at = NULL,
                    dm_followup_touch3_sent_at = NULL, dm_followup_stopped_at = now(), updated_at = now()
                WHERE contact_id = $1
                """,
                contact_id,
            )
    return {"ok": True, "active": active}


@router.delete("/inbox/contact/{contact_id}")
async def delete_contact_threads(contact_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM sms_messages WHERE contact_id = $1", contact_id)
        await conn.execute("DELETE FROM sms_conversations WHERE contact_id = $1", contact_id)
        await conn.execute("DELETE FROM email_messages WHERE contact_id = $1", contact_id)
        await conn.execute("DELETE FROM email_conversations WHERE contact_id = $1", contact_id)
        await conn.execute("DELETE FROM email_handoff_state WHERE contact_id = $1", contact_id)
    return {"ok": True}
