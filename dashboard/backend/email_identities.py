"""Provider-matched sending infrastructure for the internal (DigiGrowth-
owned) cold-outreach email identities — dedicated Google/Microsoft mailboxes
on subdomains of digigrowthllc.com, used by email_handoff_sequence.py and
warmed up by identity_warmup.py. See email_send_identities/identity_warmup*
in db.py.

Two things live here:
  1. detect_provider() / pick_identity() — MX-lookup a lead's email domain
     and route the send through a matching-provider identity, so a Gmail
     recipient gets sent from a Google identity and an Outlook recipient
     from a Microsoft identity (falls back to any active identity for an
     unrecognized/'other' domain).
  2. Provider-specific senders/pollers — _identity_gmail_service is a
     per-mailbox Gmail-API factory (same OAuth app as the internal OS,
     different refresh token per identity). _identity_graph_send /
     _poll_identity_inbox_graph are new Microsoft Graph API integration —
     no existing pattern in this repo to copy from, since no other module
     here has ever sent through a Microsoft mailbox.
"""
import asyncio
import base64
import os
import re
from datetime import datetime, timedelta, timezone as dt_timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import integrations
from db import get_pool

_GOOGLE_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
_PROVIDER_TTL = timedelta(days=30)


# ── MX-based provider detection ──────────────────────────────────────────

def _mx_hostnames(domain: str) -> list[str]:
    import dns.resolver

    answers = dns.resolver.resolve(domain, "MX", lifetime=5)
    return [str(r.exchange).rstrip(".").lower() for r in answers]


async def detect_provider(email: str) -> str:
    """Returns 'google' | 'microsoft' | 'other'. Never raises — DNS
    failures (NXDOMAIN, timeout, no MX) fall back to 'other'."""
    domain = (email or "").split("@")[-1].strip().lower()
    if not domain:
        return "other"
    try:
        hostnames = await asyncio.to_thread(_mx_hostnames, domain)
    except Exception:
        return "other"

    for host in hostnames:
        if host.endswith(".google.com") or host.endswith(".googlemail.com"):
            return "google"
        if host.endswith(".mail.protection.outlook.com"):
            return "microsoft"
    return "other"


async def get_cached_provider(conn, contact: dict) -> str:
    """Reads contact.email_provider if fresh (<30 days old), otherwise
    re-detects and persists it. Keeps email_handoff_sequence.py from
    re-querying DNS on every 5-min poll for a lead still waiting out its
    send window."""
    email = (contact.get("email") or "").strip()
    checked_at = contact.get("email_provider_checked_at")
    cached = contact.get("email_provider")
    now = datetime.now(dt_timezone.utc)
    if cached and checked_at and (now - checked_at) < _PROVIDER_TTL:
        return cached

    provider = await detect_provider(email)
    await conn.execute(
        "UPDATE contacts SET email_provider = $2, email_provider_checked_at = now() WHERE id = $1",
        contact["id"], provider,
    )
    return provider


# ── Identity selection (round-robin per provider) ────────────────────────

async def pick_identity(conn, provider: str) -> dict | None:
    """Round-robins across active identities matching `provider`. Falls
    back to any active identity (any provider) if none match — covers
    provider == 'other' and the case where only one provider has active
    identities so far. Returns None (caller skips/retries next poll) if
    zero active identities exist anywhere."""
    rows = await conn.fetch(
        "SELECT * FROM email_send_identities WHERE status = 'active' AND provider = $1 ORDER BY id",
        provider,
    )
    if not rows:
        rows = await conn.fetch(
            "SELECT * FROM email_send_identities WHERE status = 'active' ORDER BY id",
        )
    if not rows:
        return None

    # send_cursor lives on whichever row we're about to pick — use the
    # lowest-id row's cursor as the shared pointer into this candidate set.
    anchor = rows[0]
    idx = anchor["send_cursor"] % len(rows)
    identity = dict(rows[idx])
    await conn.execute(
        "UPDATE email_send_identities SET send_cursor = send_cursor + 1, updated_at = now() WHERE id = $1",
        anchor["id"],
    )
    return identity


# ── Google identity sending ─────────────────────────────────────────────

def _identity_google_creds(refresh_token: str):
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


def _identity_gmail_service(refresh_token: str):
    from googleapiclient.discovery import build
    return build("gmail", "v1", credentials=_identity_google_creds(refresh_token), cache_discovery=False)


def _send_via_gmail(identity: dict, to: str, subject: str, body: str,
                    html: str | None = None, reply_to: str | None = None, headers: dict | None = None) -> str:
    svc = _identity_gmail_service(identity["oauth_refresh_token"])
    if html:
        # multipart/alternative (plain + HTML) rather than HTML-only — the
        # plain part keeps spam filters happier than a bare HTML body.
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(body, "plain"))
        msg.attach(MIMEText(html, "html"))
    else:
        msg = MIMEText(body)
    msg["to"] = to
    msg["subject"] = subject
    if reply_to:
        msg["Reply-To"] = reply_to
    for name, value in (headers or {}).items():
        msg[name] = value
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    sent = svc.users().messages().send(userId="me", body={"raw": raw}).execute()
    return sent["id"]


# ── Microsoft identity sending (new — no existing pattern in this repo) ──

_GRAPH_SCOPES = ["https://graph.microsoft.com/Mail.Send", "https://graph.microsoft.com/Mail.Read"]
# Moving warm-up mail out of Junk / marking it read+important needs
# Mail.ReadWrite, which only mailboxes re-consented with reauth_microsoft.py
# since 2026-10-29 have. Without it, placement is still measured, just not fixed.
_GRAPH_RW_SCOPES = ["https://graph.microsoft.com/Mail.ReadWrite", "https://graph.microsoft.com/Mail.Send"]


def _graph_access_token(identity: dict, scopes: list[str] | None = None) -> str:
    import msal

    for key in ("MS_CLIENT_ID", "MS_CLIENT_SECRET"):
        if not os.environ.get(key):
            raise RuntimeError(f"Missing env var: {key}")

    tenant_id = identity.get("ms_tenant_id") or os.environ.get("MS_TENANT_ID")
    if not tenant_id:
        raise RuntimeError(f"Identity {identity.get('id')} has no ms_tenant_id and MS_TENANT_ID is unset")

    app = msal.ConfidentialClientApplication(
        client_id=os.environ["MS_CLIENT_ID"],
        client_credential=os.environ["MS_CLIENT_SECRET"],
        authority=f"https://login.microsoftonline.com/{tenant_id}",
    )
    result = app.acquire_token_by_refresh_token(identity["oauth_refresh_token"], scopes=scopes or _GRAPH_SCOPES)
    if "access_token" not in result:
        raise RuntimeError(f"Graph token refresh failed: {result.get('error_description', result)}")
    return result["access_token"]


def _send_via_graph(identity: dict, to: str, subject: str, body: str,
                    html: str | None = None, reply_to: str | None = None, headers: dict | None = None) -> str:
    import httpx

    token = _graph_access_token(identity)
    message = {
        "subject": subject,
        "body": {"contentType": "HTML", "content": html} if html else {"contentType": "Text", "content": body},
        "toRecipients": [{"emailAddress": {"address": to}}],
    }
    if reply_to:
        message["replyTo"] = [{"emailAddress": {"address": reply_to}}]
    # Graph only accepts custom "x-" headers (List-Unsubscribe is rejected),
    # so `headers` is Gmail-only in practice.
    resp = httpx.post(
        "https://graph.microsoft.com/v1.0/me/sendMail",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": message, "saveToSentItems": True},
        timeout=20,
    )
    resp.raise_for_status()
    # Graph's sendMail returns 202 with no body/id — unlike Gmail's send API.
    return ""


# ── Unified send entrypoint ──────────────────────────────────────────────

async def send_from_identity(identity: dict, to: str, subject: str, body: str,
                             html: str | None = None, reply_to: str | None = None,
                             headers: dict | None = None) -> str:
    """Sends through whichever provider `identity` belongs to. Returns the
    provider message id (empty string for Graph, which doesn't return one
    synchronously). Raises on failure — callers are expected to catch and
    log, same discipline as every other send helper in this codebase."""
    if identity["provider"] == "google":
        return await asyncio.to_thread(_send_via_gmail, identity, to, subject, body, html, reply_to, headers)
    elif identity["provider"] == "microsoft":
        return await asyncio.to_thread(_send_via_graph, identity, to, subject, body, html, reply_to)
    raise RuntimeError(f"Unknown provider: {identity['provider']}")


def _extract_email(header_value: str) -> str:
    m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", header_value or "")
    return m.group(0).lower() if m else ""


_SYNC_LOOKBACK_SEC = 120  # overlap window between polls

_AUTO_REPLY_SUBJECT = re.compile(
    r"^\s*(automatic reply|auto[- ]?reply|autoreply|auto:|out of (the )?office)", re.IGNORECASE,
)
_AUTO_REPLY_BODY = re.compile(
    r"out of (the )?office|i am currently out|i'?m currently out|limited access to (my )?e-?mail"
    r"|this is an automated|auto-?reply|away from (the office|my desk) until",
    re.IGNORECASE,
)


def _is_auto_reply(headers: dict, subject: str, body: str) -> bool:
    """Out-of-office / autoresponder detection, so an OOO bounce-back isn't
    treated as a real lead reply (which would permanently stop the Email
    Handoff sequence — see email_handoff_sequence._has_replied). Standard
    headers first (RFC 3834 Auto-Submitted, Precedence, X-Autoreply), then
    subject/body wording as a fallback for servers that set neither."""
    h = {k.lower(): (v or "").lower() for k, v in (headers or {}).items()}
    if h.get("auto-submitted", "no") not in ("", "no"):
        return True
    if h.get("precedence") in ("auto_reply", "bulk", "junk") or "x-autoreply" in h or "x-autorespond" in h:
        return True
    if _AUTO_REPLY_SUBJECT.search(subject or ""):
        return True
    return bool(_AUTO_REPLY_BODY.search((body or "")[:600]))


# ── Inbox polling ──────────────────────────────────────────────────────
#
# One combined pass per identity per tick: fetches new inbound mail, and
# splits it into (a) real lead replies — matched against known
# contacts.email, inserted into email_messages/email_conversations exactly
# like routers/email_inbox.py's internal sync, which is what
# email_handoff_sequence.py's reply-stop check already reads — and
# (b) warm-up candidates — mail from another row in email_send_identities,
# returned to the caller (identity_warmup.py) for thread-matching rather
# than handled here, to keep warm-up's thread_key bookkeeping out of this
# module. A message is always exactly one or the other, never both, so one
# fetch + one cursor advance covers both concerns without double-polling
# the same mailbox.

def _gmail_raw_messages(svc, query_after: int) -> list[dict]:
    q = f"in:inbox after:{query_after}" if query_after else "in:inbox newer_than:30d"
    res = svc.users().messages().list(userId="me", q=q, maxResults=50).execute()
    out = []
    for m in res.get("messages", []):
        full = svc.users().messages().get(userId="me", id=m["id"], format="full").execute()
        headers = {h["name"].lower(): h["value"] for h in full["payload"].get("headers", [])}
        subject = headers.get("subject", "(no subject)")
        body = integrations._extract_body(full["payload"]) or full.get("snippet", "")
        out.append({
            "message_id": m["id"],
            "from_addr": _extract_email(headers.get("from", "")),
            "subject": subject,
            "body": body,
            "internal_ts": int(full.get("internalDate", "0")) // 1000,
            "is_auto_reply": _is_auto_reply(headers, subject, body),
        })
    return out


def _gmail_sent_messages(svc, query_after: int) -> list[dict]:
    """Mail Dylan sent from this mailbox in Gmail itself (not via the
    dashboard), so those replies show in the Inbox thread too. Sequence
    touches and dashboard replies are already in email_messages under the
    same Gmail id and get skipped by the caller."""
    q = f"in:sent after:{query_after}" if query_after else "in:sent newer_than:30d"
    res = svc.users().messages().list(userId="me", q=q, maxResults=50).execute()
    out = []
    for m in res.get("messages", []):
        full = svc.users().messages().get(userId="me", id=m["id"], format="full").execute()
        headers = {h["name"].lower(): h["value"] for h in full["payload"].get("headers", [])}
        out.append({
            "message_id": m["id"],
            "to_addrs": re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", f"{headers.get('to', '')},{headers.get('cc', '')}".lower()),
            "subject": headers.get("subject", "(no subject)"),
            "body": integrations._extract_body(full["payload"]) or full.get("snippet", ""),
            "internal_ts": int(full.get("internalDate", "0")) // 1000,
        })
    return out


def _graph_raw_messages(identity: dict, since_ts: int) -> list[dict]:
    import httpx

    token = _graph_access_token(identity)
    since_iso = datetime.fromtimestamp(since_ts, tz=dt_timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    resp = httpx.get(
        "https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "$filter": f"receivedDateTime ge {since_iso}",
            "$select": "id,from,subject,bodyPreview,receivedDateTime,internetMessageHeaders",
            "$top": 50,
        },
        timeout=20,
    )
    resp.raise_for_status()
    out = []
    for m in resp.json().get("value", []):
        received = m.get("receivedDateTime", "")
        try:
            ts = int(datetime.strptime(received, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt_timezone.utc).timestamp())
        except ValueError:
            ts = since_ts
        headers = {h.get("name", ""): h.get("value", "") for h in (m.get("internetMessageHeaders") or [])}
        subject = m.get("subject") or "(no subject)"
        body = m.get("bodyPreview") or ""
        out.append({
            "message_id": m["id"],
            "from_addr": (m.get("from", {}).get("emailAddress", {}).get("address") or "").lower(),
            "subject": subject,
            "body": body,
            "internal_ts": ts,
            "is_auto_reply": _is_auto_reply(headers, subject, body),
        })
    return out


_BOUNCE_FROM_RE = re.compile(r"mailer-daemon|postmaster|mail delivery|microsoftexchange", re.I)
_BOUNCE_SUBJECT_RE = re.compile(
    r"undeliverable|delivery status notification|mail delivery failed|returned mail|"
    r"delivery has failed|failure notice|could not be delivered|address not found",
    re.I,
)


def _looks_like_bounce(from_addr: str, subject: str) -> bool:
    return bool(_BOUNCE_FROM_RE.search(from_addr or "") or _BOUNCE_SUBJECT_RE.search(subject or ""))


async def _record_bounce(conn, identity: dict, msg: dict, contact_by_email: dict):
    """A cold send from this identity bounced: mark that send bounced (feeds
    the identity's bounce rate in identity_warmup.run_health_check) and stop
    the rest of the prospect's Email Handoff sequence — there's no point
    following up on an address that doesn't exist. The notice quotes the
    failed recipient somewhere in its body; match it against known contacts."""
    body = (msg.get("body") or "").lower()
    for email, contact_id in contact_by_email.items():
        if email and email in body:
            await conn.execute(
                """UPDATE email_messages SET bounced_at = now()
                   WHERE id = (
                       SELECT id FROM email_messages
                       WHERE contact_id = $1 AND direction = 'outbound' AND bounced_at IS NULL
                         AND thread_id LIKE $2
                       ORDER BY sent_at DESC LIMIT 1
                   )""",
                contact_id, f"identity-{identity['id']}-%",
            )
            await conn.execute(
                "UPDATE email_handoff_state SET stopped_at = coalesce(stopped_at, now()), "
                "skip_reason = coalesce(skip_reason, 'bounced'), updated_at = now() WHERE contact_id = $1",
                contact_id,
            )
            print(f"[email_identities] bounce recorded for {email} on {identity['mailbox_email']}")
            return


def _forward_address() -> str:
    return os.environ.get("REPLY_FORWARD_EMAIL") or integrations.EXPECTED_SENDER_EMAIL


async def forward_reply_to_main_inbox(identity: dict, contact: dict, msg: dict):
    """Copies a real lead reply into Dylan's main DigiGrowth inbox so he
    doesn't have to watch the dashboard. Sent FROM the identity mailbox
    (not the business Gmail), so email_inbox.py's business-Gmail sync never
    mistakes it for a prospect message — the From is an identity, which is
    never a contact. Reply-To is the lead, so hitting Reply in Gmail answers
    them directly (from the main address; the dashboard Inbox reply keeps
    the same identity sender). Out-of-office replies are not forwarded.
    Never raises — a failed forward must not break the inbox sync."""
    lead_email = msg["from_addr"]
    who = " / ".join(p for p in (contact.get("owner"), contact.get("business")) if p) or lead_email
    body = (
        f"Lead reply from {who} <{lead_email}>\n"
        f"Received on {identity['mailbox_email']} (Email Handoff sequence).\n"
        f"Hitting Reply here answers the lead directly. To keep the same sender, reply from the dashboard Inbox instead.\n"
        f"{'-' * 40}\n\n"
        f"{msg['body']}"
    )
    try:
        await send_from_identity(
            identity, _forward_address(), f"[Lead Reply] {who}: {msg['subject']}", body, reply_to=lead_email,
        )
    except Exception as e:
        print(f"[email_identities] reply forward failed for {lead_email}: {e}")


async def sync_identity_inbox(identity: dict) -> dict:
    """Polls one identity's mailbox for new inbound mail since its own
    email_sync_last_ts cursor. Returns
    {"lead_replies": int, "warmup_candidates": [raw message dicts]}."""
    pool = await get_pool()
    last_ts = identity["email_sync_last_ts"] or 0

    sent_messages = []
    if identity["provider"] == "google":
        query_after = max(0, last_ts - _SYNC_LOOKBACK_SEC)
        svc = await asyncio.to_thread(_identity_gmail_service, identity["oauth_refresh_token"])
        raw_messages = await asyncio.to_thread(_gmail_raw_messages, svc, query_after)
        if identity["status"] != "partner":
            sent_messages = await asyncio.to_thread(_gmail_sent_messages, svc, query_after)
    elif identity["provider"] == "microsoft":
        # Sent-folder sync is Gmail-only: Graph sends are stored under
        # synthetic ids (no id comes back from sendMail), so they couldn't
        # be de-duplicated against the sent folder.
        since_ts = max(0, last_ts - _SYNC_LOOKBACK_SEC)
        raw_messages = await asyncio.to_thread(_graph_raw_messages, identity, since_ts)
    else:
        return {"lead_replies": 0, "warmup_candidates": []}

    async with pool.acquire() as conn:
        contacts = await conn.fetch(
            "SELECT id, email, business, owner FROM contacts WHERE email IS NOT NULL AND trim(email) != ''"
        )
        contact_by_email = {c["email"].strip().lower(): c["id"] for c in contacts if c["email"]}
        contact_info = {c["id"]: dict(c) for c in contacts}
        identity_emails = {
            r["mailbox_email"].lower()
            for r in await conn.fetch("SELECT mailbox_email FROM email_send_identities WHERE id != $1", identity["id"])
        }

        lead_replies, warmup_candidates = 0, []
        newest_ts = last_ts
        for msg in raw_messages:
            exists = await conn.fetchval("SELECT 1 FROM email_messages WHERE gmail_message_id = $1", msg["message_id"])
            if exists:
                continue
            newest_ts = max(newest_ts, msg["internal_ts"])
            from_addr = msg["from_addr"]

            if from_addr in identity_emails:
                warmup_candidates.append(msg)
                continue

            if identity["status"] == "partner":
                continue  # a partner is a personal inbox — only warm-up mail is ours to touch

            if _looks_like_bounce(from_addr, msg["subject"]):
                await _record_bounce(conn, identity, msg, contact_by_email)
                continue

            if from_addr not in contact_by_email:
                continue  # not a known prospect and not a sibling identity — skip

            contact_id = contact_by_email[from_addr]
            thread_id = f"identity-{identity['id']}-{contact_id}"
            conv = await conn.fetchrow("SELECT id FROM email_conversations WHERE thread_id = $1", thread_id)
            if not conv:
                await conn.execute(
                    """INSERT INTO email_conversations (contact_id, thread_id, email, subject, status)
                       VALUES ($1, $2, $3, $4, 'active')""",
                    contact_id, thread_id, from_addr, msg["subject"],
                )
            else:
                await conn.execute(
                    "UPDATE email_conversations SET subject = $2, updated_at = now() WHERE thread_id = $1",
                    thread_id, msg["subject"],
                )
            await conn.execute(
                """INSERT INTO email_messages (contact_id, thread_id, email, direction, subject, body, gmail_message_id, sent_at, is_auto_reply)
                   VALUES ($1, $2, $3, 'inbound', $4, $5, $6, to_timestamp($7), $8)
                   ON CONFLICT (gmail_message_id) DO NOTHING""",
                contact_id, thread_id, from_addr, msg["subject"], msg["body"], msg["message_id"], msg["internal_ts"],
                msg.get("is_auto_reply", False),
            )
            lead_replies += 1
            if not msg.get("is_auto_reply"):
                await forward_reply_to_main_inbox(identity, contact_info.get(contact_id, {}), msg)

        own = identity_emails | {identity["mailbox_email"].lower(), integrations.EXPECTED_SENDER_EMAIL.lower()}
        for msg in sent_messages:
            newest_ts = max(newest_ts, msg["internal_ts"])
            if await conn.fetchval("SELECT 1 FROM email_messages WHERE gmail_message_id = $1", msg["message_id"]):
                continue
            to_addr = next((a for a in msg["to_addrs"] if a in contact_by_email and a not in own), None)
            if not to_addr:
                continue  # warm-up mail, a forward to Dylan, or a non-prospect
            contact_id = contact_by_email[to_addr]
            thread_id = f"identity-{identity['id']}-{contact_id}"
            if not await conn.fetchval("SELECT 1 FROM email_conversations WHERE thread_id = $1", thread_id):
                await conn.execute(
                    """INSERT INTO email_conversations (contact_id, thread_id, email, subject, status)
                       VALUES ($1, $2, $3, $4, 'active')""",
                    contact_id, thread_id, to_addr, msg["subject"],
                )
            await conn.execute(
                """INSERT INTO email_messages (contact_id, thread_id, email, direction, subject, body, gmail_message_id, sent_at)
                   VALUES ($1, $2, $3, 'outbound', $4, $5, $6, to_timestamp($7))
                   ON CONFLICT (gmail_message_id) DO NOTHING""",
                contact_id, thread_id, to_addr, msg["subject"], msg["body"], msg["message_id"], msg["internal_ts"],
            )

        if newest_ts > last_ts:
            await conn.execute(
                "UPDATE email_send_identities SET email_sync_last_ts = $2, updated_at = now() WHERE id = $1",
                identity["id"], newest_ts,
            )

    return {"lead_replies": lead_replies, "warmup_candidates": warmup_candidates}


# ── Warm-up mailbox actions (identity_warmup.py) ──────────────────────────
#
# What Instantly does on the receiving side of every warm-up email: find it
# wherever it landed (inbox, Promotions, spam), record that placement (the
# health score), pull it out of spam / Promotions, open it, mark it
# important, and file it under a "Warmup" label out of the way. Replies go
# out threaded under the original message. Gmail mailboxes can do all of
# this with the existing gmail.modify scope; Microsoft ones need
# Mail.ReadWrite to move/mark (see _GRAPH_RW_SCOPES).

WARMUP_LABEL = "Warmup"
_WARMUP_LOOKBACK_DAYS = 3
_label_ids: dict[str, str] = {}

# Newsletter subscriptions (the SOP's inbound-volume step) and DMARC reports
# are archived + marked read so the inbox only shows prospect mail.
_NEWSLETTER_QUERY = (
    "in:inbox (from:(axios.com OR thedailybeast.com OR buzzfeed.com OR theskimm.com OR morningbrew.com) "
    "OR (subject:dmarc subject:report))"
)


def _gmail_label_id(svc, mailbox: str) -> str:
    if mailbox in _label_ids:
        return _label_ids[mailbox]
    labels = svc.users().labels().list(userId="me").execute().get("labels", [])
    label = next((l for l in labels if l["name"] == WARMUP_LABEL), None)
    if not label:
        body = {"name": WARMUP_LABEL, "labelListVisibility": "labelShow", "messageListVisibility": "show"}
        try:
            label = svc.users().labels().create(userId="me", body={
                **body, "color": {"backgroundColor": "#cccccc", "textColor": "#000000"},  # grey, per the SOP
            }).execute()
        except Exception:
            label = svc.users().labels().create(userId="me", body=body).execute()
    _label_ids[mailbox] = label["id"]
    return label["id"]


def _gmail_placement(labels: list[str]) -> str:
    if "SPAM" in labels:
        return "spam"
    if any(l in labels for l in ("CATEGORY_PROMOTIONS", "CATEGORY_UPDATES", "CATEGORY_SOCIAL", "CATEGORY_FORUMS")):
        return "promotions"
    return "inbox"


def _gmail_warmup_scan(identity: dict, senders: list[str]) -> list[dict]:
    svc = _identity_gmail_service(identity["oauth_refresh_token"])
    label_id = _gmail_label_id(svc, identity["mailbox_email"])
    q = (f"from:({' OR '.join(senders)}) in:anywhere -in:trash -in:sent "
         f"-label:{WARMUP_LABEL} newer_than:{_WARMUP_LOOKBACK_DAYS}d")
    res = svc.users().messages().list(userId="me", q=q, maxResults=50, includeSpamTrash=True).execute()
    out = []
    for m in res.get("messages", []):
        full = svc.users().messages().get(userId="me", id=m["id"], format="full").execute()
        headers = {h["name"].lower(): h["value"] for h in full["payload"].get("headers", [])}
        out.append({
            "message_id": m["id"],
            "from_addr": _extract_email(headers.get("from", "")),
            "subject": headers.get("subject", ""),
            "body": integrations._extract_body(full["payload"]) or full.get("snippet", ""),
            "placement": _gmail_placement(full.get("labelIds", [])),
            "label_id": label_id,
        })
    return out


def _gmail_warmup_engage(identity: dict, msg: dict) -> bool:
    """Not-spam / move-to-Primary first (that's the positive signal), then
    open, mark important, and file under the Warmup label."""
    svc = _identity_gmail_service(identity["oauth_refresh_token"])
    rescued = False
    if msg["placement"] == "spam":
        svc.users().messages().modify(userId="me", id=msg["message_id"],
                                      body={"removeLabelIds": ["SPAM"], "addLabelIds": ["INBOX"]}).execute()
        rescued = True
    elif msg["placement"] == "promotions":
        svc.users().messages().modify(userId="me", id=msg["message_id"], body={
            "removeLabelIds": ["CATEGORY_PROMOTIONS", "CATEGORY_UPDATES", "CATEGORY_SOCIAL", "CATEGORY_FORUMS"],
            "addLabelIds": ["CATEGORY_PERSONAL"],
        }).execute()
        rescued = True
    svc.users().messages().modify(userId="me", id=msg["message_id"], body={
        "removeLabelIds": ["UNREAD", "INBOX"], "addLabelIds": ["IMPORTANT", msg["label_id"]],
    }).execute()
    return rescued


def _gmail_warmup_reply(identity: dict, received_message_id: str, body: str) -> str:
    svc = _identity_gmail_service(identity["oauth_refresh_token"])
    full = svc.users().messages().get(userId="me", id=received_message_id, format="metadata",
                                      metadataHeaders=["From", "Subject", "Message-ID", "References"]).execute()
    headers = {h["name"].lower(): h["value"] for h in full["payload"].get("headers", [])}
    subject = headers.get("subject", "")
    msg = MIMEText(body)
    msg["to"] = headers.get("from", "")
    msg["subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    if headers.get("message-id"):
        msg["In-Reply-To"] = headers["message-id"]
        msg["References"] = f"{headers.get('references', '')} {headers['message-id']}".strip()
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    sent = svc.users().messages().send(userId="me", body={"raw": raw, "threadId": full["threadId"]}).execute()
    return sent["id"]


def _gmail_archive_newsletters(identity: dict) -> int:
    svc = _identity_gmail_service(identity["oauth_refresh_token"])
    ids = [m["id"] for m in svc.users().messages().list(userId="me", q=_NEWSLETTER_QUERY, maxResults=100)
           .execute().get("messages", [])]
    if ids:
        svc.users().messages().batchModify(userId="me", body={"ids": ids, "removeLabelIds": ["INBOX", "UNREAD"]}).execute()
    return len(ids)


def _graph_warmup_scan(identity: dict, senders: list[str]) -> list[dict]:
    import httpx

    token = _graph_access_token(identity)
    since = (datetime.now(dt_timezone.utc) - timedelta(days=_WARMUP_LOOKBACK_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    wanted = {s.lower() for s in senders}
    out = []
    for folder in ("inbox", "junkemail"):
        resp = httpx.get(
            f"https://graph.microsoft.com/v1.0/me/mailFolders/{folder}/messages",
            headers={"Authorization": f"Bearer {token}", "Prefer": 'outlook.body-content-type="text"'},
            params={
                "$filter": f"receivedDateTime ge {since}",
                "$select": "id,from,subject,body,inferenceClassification,isRead",
                "$top": 50,
            },
            timeout=20,
        )
        resp.raise_for_status()
        for m in resp.json().get("value", []):
            from_addr = (m.get("from", {}).get("emailAddress", {}).get("address") or "").lower()
            if from_addr not in wanted or m.get("isRead"):
                continue  # read = already handled on an earlier pass (or by hand)
            if folder == "junkemail":
                placement = "spam"
            elif m.get("inferenceClassification") == "other":
                placement = "promotions"  # Outlook's "Other" tab
            else:
                placement = "inbox"
            out.append({
                "message_id": m["id"], "from_addr": from_addr, "subject": m.get("subject") or "",
                "body": (m.get("body") or {}).get("content", ""), "placement": placement,
            })
    return out


def _graph_warmup_engage(identity: dict, msg: dict) -> bool:
    import httpx

    try:
        token = _graph_access_token(identity, _GRAPH_RW_SCOPES)
    except Exception:
        return False  # not re-consented with Mail.ReadWrite yet — placement is still recorded
    h = {"Authorization": f"Bearer {token}"}
    message_id, rescued = msg["message_id"], False
    if msg["placement"] == "spam":
        resp = httpx.post(f"https://graph.microsoft.com/v1.0/me/messages/{message_id}/move",
                          headers=h, json={"destinationId": "inbox"}, timeout=20)
        resp.raise_for_status()
        message_id, rescued = resp.json()["id"], True
    patch = {"isRead": True, "importance": "high"}
    if msg["placement"] == "promotions":
        patch["inferenceClassification"] = "focused"
        rescued = True
    httpx.patch(f"https://graph.microsoft.com/v1.0/me/messages/{message_id}", headers=h, json=patch,
                timeout=20).raise_for_status()
    msg["message_id"] = message_id  # a move gives the message a new id; replies need the current one
    return rescued


def _graph_warmup_reply(identity: dict, received_message_id: str, body: str) -> str:
    import httpx

    token = _graph_access_token(identity)
    httpx.post(f"https://graph.microsoft.com/v1.0/me/messages/{received_message_id}/reply",
               headers={"Authorization": f"Bearer {token}"}, json={"comment": body}, timeout=20).raise_for_status()
    return ""


async def warmup_scan(identity: dict, senders: list[str]) -> list[dict]:
    """Warm-up mail from `senders` that reached this mailbox in the last few
    days and hasn't been handled yet, wherever it landed, each with its
    `placement` ('inbox' | 'promotions' | 'spam')."""
    if not senders:
        return []
    if identity["provider"] == "google":
        return await asyncio.to_thread(_gmail_warmup_scan, identity, senders)
    if identity["provider"] == "microsoft":
        return await asyncio.to_thread(_graph_warmup_scan, identity, senders)
    return []


async def warmup_engage(identity: dict, msg: dict) -> bool:
    """Rescue + open + mark important. Returns True if it was moved out of
    spam/Promotions."""
    if identity["provider"] == "google":
        return await asyncio.to_thread(_gmail_warmup_engage, identity, msg)
    return await asyncio.to_thread(_graph_warmup_engage, identity, msg)


async def warmup_reply(identity: dict, received_message_id: str, body: str) -> str:
    """Replies in-thread to a warm-up message this mailbox received."""
    if identity["provider"] == "google":
        return await asyncio.to_thread(_gmail_warmup_reply, identity, received_message_id, body)
    return await asyncio.to_thread(_graph_warmup_reply, identity, received_message_id, body)


async def archive_newsletters(identity: dict) -> int:
    if identity["provider"] != "google":
        return 0
    return await asyncio.to_thread(_gmail_archive_newsletters, identity)
