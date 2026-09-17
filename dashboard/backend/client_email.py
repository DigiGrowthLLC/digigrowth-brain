"""
Sends email through a REAL client's OWN Google Workspace mailbox on their
own domain — deliberately separate from integrations.py's gmail_send*
functions, which always send from DigiGrowth's own shared mailbox
(GOOGLE_REFRESH_TOKEN env var). This mirrors that same Gmail-API approach,
but the refresh token is per-client (stored in
client_marketing_config.gmail_refresh_token, obtained by running
reauth_google.py logged into the client's own mailbox) rather than a single
global env var — see the "Set up email marketing" launch-checklist item's
description for the manual setup steps.

Shares the same OAuth app (GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET) as the
internal OS — only the refresh token (i.e. which mailbox) differs per client.
"""
import asyncio
import base64
import os
import re
from email.mime.text import MIMEText

import integrations
from db import get_pool

_GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
]

_SYNC_LOOKBACK_SEC = 120  # overlap window, matches email_inbox.py's internal sync


def _extract_email(header_value: str) -> str:
    m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", header_value or "")
    return m.group(0).lower() if m else ""


def _client_creds(refresh_token: str):
    from google.oauth2.credentials import Credentials

    for key in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"):
        if not os.environ.get(key):
            raise RuntimeError(f"Missing env var: {key}")

    return Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=_GOOGLE_SCOPES,
    )


def _client_gmail_service(refresh_token: str):
    from googleapiclient.discovery import build
    return build("gmail", "v1", credentials=_client_creds(refresh_token), cache_discovery=False)


async def send_client_email(client_id: int, to: str, subject: str, body: str) -> str:
    pool = await get_pool()
    async with pool.acquire() as conn:
        config = await conn.fetchrow(
            "SELECT gmail_refresh_token FROM client_marketing_config WHERE client_id = $1",
            client_id,
        )
        if not config or not config["gmail_refresh_token"]:
            raise RuntimeError(f"Client {client_id} has no connected Gmail mailbox yet")

        svc = _client_gmail_service(config["gmail_refresh_token"])
        msg = MIMEText(body)
        msg["to"] = to
        msg["subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        sent = svc.users().messages().send(userId="me", body={"raw": raw}).execute()

        await conn.execute(
            """
            INSERT INTO client_email_messages (client_id, to_email, subject, body, gmail_message_id, direction)
            VALUES ($1, $2, $3, $4, $5, 'outbound')
            """,
            client_id, to, subject, body, sent["id"],
        )

    # Local import avoids a circular import (email_warmup imports this
    # module to reuse _client_gmail_service). Best-effort — never raises,
    # counts this real send toward the client's warm-up ramp target if one
    # is running, but must never block or affect a real send either way.
    import email_warmup
    await email_warmup.record_real_send(client_id)

    return f"Sent email to {to}: {subject}"


# ── Inbound sync (a prospect replying to the client's mailbox) ──────────────
#
# Mirrors routers/email_inbox.py's internal Gmail poll, but far simpler: a
# client's dedicated outreach mailbox never mixes with anyone's personal
# inbox, so unlike the internal sync there's no contact-matching heuristic
# needed — every message that lands in the mailbox's INBOX is a real reply
# worth recording.

async def _sync_one_mailbox(conn, client_id: int, refresh_token: str, last_ts: int) -> int:
    """Polls one client's mailbox for new inbound mail since last_ts (unix
    seconds). Returns the newest message timestamp seen (>= last_ts)."""
    svc = _client_gmail_service(refresh_token)
    query_after = max(0, last_ts - _SYNC_LOOKBACK_SEC)
    q = f"in:inbox after:{query_after}" if query_after else "in:inbox newer_than:30d"
    res = await asyncio.to_thread(
        lambda: svc.users().messages().list(userId="me", q=q, maxResults=50).execute()
    )
    newest_ts = last_ts
    for m in res.get("messages", []):
        mid = m["id"]
        exists = await conn.fetchval(
            "SELECT 1 FROM client_email_messages WHERE gmail_message_id = $1", mid
        )
        if exists:
            continue
        full = await asyncio.to_thread(
            lambda mid=mid: svc.users().messages().get(userId="me", id=mid, format="full").execute()
        )
        headers = {h["name"].lower(): h["value"] for h in full["payload"].get("headers", [])}
        from_addr = _extract_email(headers.get("from", ""))
        subject = headers.get("subject", "(no subject)")
        internal_ts = int(full.get("internalDate", "0")) // 1000
        newest_ts = max(newest_ts, internal_ts)
        body = integrations._extract_body(full["payload"]) or full.get("snippet", "")

        await conn.execute(
            """
            INSERT INTO client_email_messages (client_id, to_email, subject, body, gmail_message_id, direction, created_at)
            VALUES ($1, $2, $3, $4, $5, 'inbound', to_timestamp($6))
            """,
            client_id, from_addr, subject, body, mid, internal_ts,
        )
        if from_addr:
            import client_appointment_sequence
            await client_appointment_sequence.stop_sequence_for_reply(email=from_addr)
    return newest_ts


async def sync_all_client_mailboxes_once() -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT client_id, gmail_refresh_token, email_sync_last_ts "
            "FROM client_marketing_config WHERE gmail_refresh_token IS NOT NULL"
        )

    synced, errors = 0, 0
    for r in rows:
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                last_ts = r["email_sync_last_ts"] or 0
                newest_ts = await _sync_one_mailbox(conn, r["client_id"], r["gmail_refresh_token"], last_ts)
                if newest_ts > last_ts:
                    await conn.execute(
                        "UPDATE client_marketing_config SET email_sync_last_ts = $2 WHERE client_id = $1",
                        r["client_id"], newest_ts,
                    )
            synced += 1
        except Exception as e:
            errors += 1
            print(f"[client-email-sync] client={r['client_id']} error: {e}", flush=True)
    return {"clients_synced": synced, "errors": errors}


async def sync_client_email_job():
    """APScheduler entrypoint — never raises, mirrors email_inbox.sync_gmail_job."""
    try:
        result = await sync_all_client_mailboxes_once()
        if result["clients_synced"] or result["errors"]:
            print(f"[client-email-sync] {result}", flush=True)
    except Exception as e:
        print(f"[client-email-sync] error: {e}", flush=True)
