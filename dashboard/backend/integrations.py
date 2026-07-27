"""
External service integrations for OS agents.

Credentials via env vars:
  Google:  GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN
  Notion:  NOTION_TOKEN

Each tool function returns a plain string (used directly as tool_result content).
"""

import asyncio
import base64
import os
from email.mime.text import MIMEText

import httpx

from db import get_pool

_MISSING_GOOGLE = (
    "Google not configured. Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, "
    "and GOOGLE_REFRESH_TOKEN env vars."
)
_MISSING_NOTION = "Notion not configured. Set NOTION_TOKEN env var."


# ── Google auth ───────────────────────────────────────────────────────────────

def _google_creds():
    """Return a google.oauth2.credentials.Credentials object or raise RuntimeError."""
    try:
        from google.oauth2.credentials import Credentials
    except ImportError:
        raise RuntimeError("google-auth-oauthlib not installed — add google-api-python-client to requirements.txt")

    required = ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN")
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise RuntimeError(f"Missing env vars: {', '.join(missing)}. {_MISSING_GOOGLE}")

    return Credentials(
        token=None,
        refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=[
            "https://www.googleapis.com/auth/gmail.modify",
            "https://www.googleapis.com/auth/calendar",
            "https://www.googleapis.com/auth/drive.readonly",
        ],
    )


def _gmail_service():
    from googleapiclient.discovery import build
    return build("gmail", "v1", credentials=_google_creds(), cache_discovery=False)


def _calendar_service():
    from googleapiclient.discovery import build
    return build("calendar", "v3", credentials=_google_creds(), cache_discovery=False)


def _drive_service():
    from googleapiclient.discovery import build
    return build("drive", "v3", credentials=_google_creds(), cache_discovery=False)


# ── Notion auth ───────────────────────────────────────────────────────────────

def _notion_headers():
    token = os.environ.get("NOTION_TOKEN", "")
    if not token:
        raise RuntimeError(_MISSING_NOTION)
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


# ── Gmail tools ───────────────────────────────────────────────────────────────

def gmail_search(query: str, max_results: int = 10) -> str:
    try:
        svc = _gmail_service()
        res = svc.users().threads().list(
            userId="me", q=query, maxResults=max_results
        ).execute()
        threads = res.get("threads", [])
        if not threads:
            return f"No threads found for query: {query}"
        lines = [f"Found {len(threads)} thread(s):"]
        for t in threads:
            lines.append(f"  thread_id={t['id']}  snippet={t.get('snippet', '')[:100]}")
        return "\n".join(lines)
    except RuntimeError as e:
        return str(e)
    except Exception as e:
        return f"Gmail error: {e}"


def gmail_read_thread(thread_id: str) -> str:
    try:
        svc = _gmail_service()
        thread = svc.users().threads().get(userId="me", id=thread_id, format="full").execute()
        lines = []
        for msg in thread.get("messages", []):
            headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
            lines.append(f"--- From: {headers.get('From', '?')}  Date: {headers.get('Date', '?')} ---")
            # Extract body text
            body = _extract_body(msg["payload"])
            lines.append(body[:2000])
        return "\n".join(lines) or "(empty thread)"
    except RuntimeError as e:
        return str(e)
    except Exception as e:
        return f"Gmail error: {e}"


def gmail_send(to: str, subject: str, body: str) -> str:
    try:
        svc = _gmail_service()
        msg = MIMEText(body)
        msg["to"] = to
        msg["subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        svc.users().messages().send(userId="me", body={"raw": raw}).execute()
        return f"Sent email to {to}: {subject}"
    except RuntimeError as e:
        return str(e)
    except Exception as e:
        return f"Gmail error: {e}"


NEWSLETTER_DAILY_CAP = 25   # safe range for an established single mailbox is ~25-50/day
NEWSLETTER_BATCH_SIZE = 1   # sent per call — one at a time, paced by the cron interval in main.py


async def process_newsletter_queue() -> str:
    """Send a small batch of queued newsletter emails, respecting a daily cap,
    so a big prospect list goes out gradually over days instead of all at once
    (mass-blasting from a single mailbox is what tanks domain reputation, not
    the total list size). Called both by main.py's scheduled cron job (every
    ~25 min during business hours) and by the manual "process now" endpoint
    for testing outside that window. Returns a one-line summary."""
    import asyncio as _asyncio
    from db import get_pool

    pool = await get_pool()
    async with pool.acquire() as conn:
        paused = await conn.fetchval("SELECT paused FROM newsletter_queue_state WHERE id = true")
        if paused:
            return "queue is paused — nothing sent"

        sent_today = await conn.fetchval(
            """SELECT COUNT(*) FROM newsletter_send_queue
               WHERE status = 'sent'
               AND (sent_at AT TIME ZONE 'America/New_York')::date
                   = (now() AT TIME ZONE 'America/New_York')::date"""
        )
        remaining = NEWSLETTER_DAILY_CAP - sent_today
        if remaining <= 0:
            return f"daily cap reached ({sent_today}/{NEWSLETTER_DAILY_CAP} already sent today) — nothing sent"

        batch = await conn.fetch(
            """SELECT id, email, subject, html FROM newsletter_send_queue
               WHERE status = 'queued' ORDER BY queued_at ASC LIMIT $1""",
            min(NEWSLETTER_BATCH_SIZE, remaining),
        )
        if not batch:
            return "queue is empty — nothing to send"

        sent, failed = 0, 0
        for row in batch:
            result = await _asyncio.to_thread(gmail_send_html, row["email"], row["subject"], row["html"])
            ok = result.startswith("Sent email")
            await conn.execute(
                """UPDATE newsletter_send_queue
                   SET status = $1, error = $2, sent_at = CASE WHEN $1 = 'sent' THEN now() ELSE sent_at END
                   WHERE id = $3""",
                "sent" if ok else "failed", None if ok else result, row["id"],
            )
            sent += 1 if ok else 0
            failed += 0 if ok else 1
            await _asyncio.sleep(3)  # small gap between sends within a batch, not a burst

    return f"sent {sent}, failed {failed} (today's total: {sent_today + sent}/{NEWSLETTER_DAILY_CAP})"


def gmail_send_html(to: str, subject: str, html: str) -> str:
    """Same as gmail_send but for an HTML body (newsletter sends) — MIMEText
    defaults to plain text, which would send the HTML tags as literal text."""
    try:
        svc = _gmail_service()
        msg = MIMEText(html, "html")
        msg["to"] = to
        msg["subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        svc.users().messages().send(userId="me", body={"raw": raw}).execute()
        return f"Sent email to {to}: {subject}"
    except RuntimeError as e:
        return str(e)
    except Exception as e:
        return f"Gmail error: {e}"


INFO_EMAIL_SUBJECT = "Info as promised"

INFO_EMAIL_BODY = """{first_name},

Here's the link: https://digigrowthllc.com

Quick summary of what we do: we help independent service-based businesses bring in 5-15k in new \
business in 6 weeks using Meta ads, database reactivation, and an AI system that \
handles the booking for you — no extra work on your end.

Take a look and let me know if it's worth a closer look. Happy to jump on a call \
if it makes sense.

Dylan
DigiGrowth
"""


async def send_info_email(to: str, owner: str | None, business: str | None) -> str:
    """Send the "Send Info" disposition's follow-up email — website + company blurb.
    Subject/body are editable from Business Resources → Outreach Templates
    (stored in dialer_settings); falls back to the defaults below if never saved.
    """
    first_name = (owner or "").split()[0] if owner else "there"

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT key, value FROM dialer_settings WHERE key IN ('info_email_subject', 'info_email_body')"
        )
    values = {r["key"]: r["value"] for r in rows if r["value"]}
    subject_template = values.get("info_email_subject", INFO_EMAIL_SUBJECT)
    body_template = values.get("info_email_body", INFO_EMAIL_BODY)

    subject = f"{subject_template} — {business}" if business else subject_template
    body = body_template.replace("{first_name}", first_name)
    return await asyncio.to_thread(gmail_send, to, subject, body)


def gmail_send_reply(to: str, subject: str, body: str, thread_id: str) -> dict:
    """Send a reply that threads correctly in Gmail (keyed by `thread_id`)."""
    svc = _gmail_service()
    msg = MIMEText(body)
    msg["to"] = to
    msg["subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    sent = svc.users().messages().send(userId="me", body={"raw": raw, "threadId": thread_id}).execute()
    return {"id": sent["id"], "threadId": sent["threadId"]}


def gmail_create_draft(to: str, subject: str, body: str) -> str:
    try:
        svc = _gmail_service()
        msg = MIMEText(body)
        msg["to"] = to
        msg["subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        draft = svc.users().drafts().create(
            userId="me", body={"message": {"raw": raw}}
        ).execute()
        return f"Draft created (id={draft['id']}) to={to} subject={subject}"
    except RuntimeError as e:
        return str(e)
    except Exception as e:
        return f"Gmail error: {e}"


def _extract_body(payload: dict) -> str:
    """Recursively extract plain-text body from a Gmail message payload."""
    if payload.get("mimeType") == "text/plain":
        data = payload.get("body", {}).get("data", "")
        return base64.urlsafe_b64decode(data + "==").decode(errors="replace") if data else ""
    for part in payload.get("parts", []):
        text = _extract_body(part)
        if text:
            return text
    return ""


# ── Google Calendar tools ────────────────────────────────────────────────────

def calendar_list_events(days_ahead: int = 7, calendar_id: str = "primary") -> str:
    try:
        from datetime import datetime, timezone, timedelta
        svc = _calendar_service()
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=days_ahead)
        res = svc.events().list(
            calendarId=calendar_id,
            timeMin=now.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=50,
        ).execute()
        events = res.get("items", [])
        if not events:
            return f"No events in the next {days_ahead} days."
        lines = [f"{len(events)} event(s) in next {days_ahead} day(s):"]
        for ev in events:
            start = ev["start"].get("dateTime", ev["start"].get("date", "?"))
            lines.append(f"  [{ev['id']}] {start}  {ev.get('summary', '(no title)')}")
        return "\n".join(lines)
    except RuntimeError as e:
        return str(e)
    except Exception as e:
        return f"Calendar error: {e}"


def calendar_create_event(
    title: str,
    start_datetime: str,
    end_datetime: str,
    description: str = "",
    attendees: list[str] | None = None,
    calendar_id: str = "primary",
) -> str:
    try:
        svc = _calendar_service()
        body = {
            "summary": title,
            "description": description,
            "start": {"dateTime": start_datetime},
            "end": {"dateTime": end_datetime},
        }
        if attendees:
            body["attendees"] = [{"email": e} for e in attendees]
        ev = svc.events().insert(calendarId=calendar_id, body=body).execute()
        return f"Created event: {ev['id']}  '{title}'  {start_datetime} → {end_datetime}"
    except RuntimeError as e:
        return str(e)
    except Exception as e:
        return f"Calendar error: {e}"


def calendar_update_event(
    event_id: str,
    title: str | None = None,
    start_datetime: str | None = None,
    end_datetime: str | None = None,
    description: str | None = None,
    calendar_id: str = "primary",
) -> str:
    try:
        svc = _calendar_service()
        ev = svc.events().get(calendarId=calendar_id, eventId=event_id).execute()
        if title is not None:
            ev["summary"] = title
        if description is not None:
            ev["description"] = description
        if start_datetime is not None:
            ev["start"] = {"dateTime": start_datetime}
        if end_datetime is not None:
            ev["end"] = {"dateTime": end_datetime}
        updated = svc.events().update(calendarId=calendar_id, eventId=event_id, body=ev).execute()
        return f"Updated event {event_id}: '{updated.get('summary')}'"
    except RuntimeError as e:
        return str(e)
    except Exception as e:
        return f"Calendar error: {e}"


def calendar_delete_event(event_id: str, calendar_id: str = "primary") -> str:
    try:
        svc = _calendar_service()
        svc.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        return f"Deleted event {event_id}"
    except RuntimeError as e:
        return str(e)
    except Exception as e:
        return f"Calendar error: {e}"


# ── Google Drive tools ────────────────────────────────────────────────────────

def drive_search(query: str, max_results: int = 10) -> str:
    try:
        svc = _drive_service()
        res = svc.files().list(
            q=query,
            pageSize=max_results,
            fields="files(id,name,mimeType,modifiedTime,size)",
        ).execute()
        files = res.get("files", [])
        if not files:
            return f"No files found for: {query}"
        lines = [f"Found {len(files)} file(s):"]
        for f in files:
            lines.append(f"  [{f['id']}] {f['name']}  ({f.get('mimeType','?')})  modified={f.get('modifiedTime','?')}")
        return "\n".join(lines)
    except RuntimeError as e:
        return str(e)
    except Exception as e:
        return f"Drive error: {e}"


def drive_list_recent(max_results: int = 30, days: int = 7) -> str:
    try:
        from datetime import datetime, timedelta, timezone
        svc = _drive_service()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        query = f"(modifiedTime > '{cutoff}' or viewedByMeTime > '{cutoff}') and trashed = false"
        res = svc.files().list(
            q=query,
            orderBy="modifiedTime desc",
            pageSize=max_results,
            fields="files(id,name,mimeType,modifiedTime,viewedByMeTime)",
        ).execute()
        files = res.get("files", [])
        if not files:
            return f"No files modified or opened in the last {days} days."
        lines = [f"{len(files)} file(s) active in last {days} days:"]
        for f in files:
            lines.append(f"  [{f['id']}] {f['name']}  ({f.get('mimeType','?')})")
        return "\n".join(lines)
    except RuntimeError as e:
        return str(e)
    except Exception as e:
        return f"Drive error: {e}"


def drive_read_file(file_id: str) -> str:
    try:
        svc = _drive_service()
        # Try export as plain text for Google Docs
        meta = svc.files().get(fileId=file_id, fields="mimeType,name").execute()
        mime = meta.get("mimeType", "")
        name = meta.get("name", file_id)

        if "google-apps.document" in mime:
            content = svc.files().export(fileId=file_id, mimeType="text/plain").execute()
            text = content.decode(errors="replace") if isinstance(content, bytes) else str(content)
        elif "google-apps.spreadsheet" in mime:
            content = svc.files().export(fileId=file_id, mimeType="text/csv").execute()
            text = content.decode(errors="replace") if isinstance(content, bytes) else str(content)
        else:
            content = svc.files().get_media(fileId=file_id).execute()
            text = content.decode(errors="replace") if isinstance(content, bytes) else str(content)

        return f"File: {name}\n\n{text[:8000]}"
    except RuntimeError as e:
        return str(e)
    except Exception as e:
        return f"Drive error: {e}"


# ── Notion tools ──────────────────────────────────────────────────────────────

def notion_search(query: str, max_results: int = 10) -> str:
    try:
        headers = _notion_headers()
        with httpx.Client(timeout=15) as client:
            res = client.post(
                "https://api.notion.com/v1/search",
                headers=headers,
                json={"query": query, "page_size": max_results},
            )
            res.raise_for_status()
            data = res.json()
        results = data.get("results", [])
        if not results:
            return f"No Notion pages found for: {query}"
        lines = [f"Found {len(results)} result(s):"]
        for r in results:
            title = _notion_title(r)
            lines.append(f"  [{r['id']}] ({r['object']}) {title}")
        return "\n".join(lines)
    except RuntimeError as e:
        return str(e)
    except Exception as e:
        return f"Notion error: {e}"


def notion_read_page(page_id: str) -> str:
    try:
        headers = _notion_headers()
        page_id = page_id.replace("-", "")  # normalize
        with httpx.Client(timeout=15) as client:
            # Get page metadata
            page_res = client.get(f"https://api.notion.com/v1/pages/{page_id}", headers=headers)
            page_res.raise_for_status()
            page = page_res.json()
            title = _notion_title(page)

            # Get blocks (content)
            blocks_res = client.get(
                f"https://api.notion.com/v1/blocks/{page_id}/children?page_size=100",
                headers=headers,
            )
            blocks_res.raise_for_status()
            blocks = blocks_res.json().get("results", [])

        lines = [f"# {title}", ""]
        for block in blocks:
            text = _notion_block_text(block)
            if text:
                lines.append(text)
        return "\n".join(lines)
    except RuntimeError as e:
        return str(e)
    except Exception as e:
        return f"Notion error: {e}"


def notion_create_page(parent_page_id: str, title: str, content: str = "") -> str:
    try:
        headers = _notion_headers()
        parent_page_id = parent_page_id.replace("-", "")
        body = {
            "parent": {"type": "page_id", "page_id": parent_page_id},
            "properties": {
                "title": {"title": [{"type": "text", "text": {"content": title}}]}
            },
            "children": [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": content[:2000]}}]
                    },
                }
            ] if content else [],
        }
        with httpx.Client(timeout=15) as client:
            res = client.post("https://api.notion.com/v1/pages", headers=headers, json=body)
            res.raise_for_status()
            page = res.json()
        return f"Created Notion page: {page['id']}  '{title}'"
    except RuntimeError as e:
        return str(e)
    except Exception as e:
        return f"Notion error: {e}"


def notion_update_page(page_id: str, title: str | None = None, archived: bool = False) -> str:
    try:
        headers = _notion_headers()
        page_id = page_id.replace("-", "")
        body: dict = {"archived": archived}
        if title:
            body["properties"] = {
                "title": {"title": [{"type": "text", "text": {"content": title}}]}
            }
        with httpx.Client(timeout=15) as client:
            res = client.patch(f"https://api.notion.com/v1/pages/{page_id}", headers=headers, json=body)
            res.raise_for_status()
        return f"Updated Notion page {page_id}"
    except RuntimeError as e:
        return str(e)
    except Exception as e:
        return f"Notion error: {e}"


# ── Notion helpers ────────────────────────────────────────────────────────────

def _notion_title(obj: dict) -> str:
    props = obj.get("properties", {})
    for key in ("title", "Name", "Title"):
        if key in props:
            rich = props[key].get("title", [])
            return "".join(r.get("plain_text", "") for r in rich)
    return obj.get("id", "untitled")


def _notion_block_text(block: dict) -> str:
    btype = block.get("type", "")
    content = block.get(btype, {})
    rich = content.get("rich_text", [])
    text = "".join(r.get("plain_text", "") for r in rich)
    if not text:
        return ""
    prefix = {
        "heading_1": "# ", "heading_2": "## ", "heading_3": "### ",
        "bulleted_list_item": "- ", "numbered_list_item": "1. ",
        "to_do": "[ ] ", "quote": "> ", "code": "```\n",
    }.get(btype, "")
    suffix = "\n```" if btype == "code" else ""
    return f"{prefix}{text}{suffix}"


# ── Dashboard helpers ─────────────────────────────────────────────────────────

def calendar_events_structured(days_ahead: int = 7, calendar_id: str = "primary") -> list[dict]:
    """Return structured event dicts for the dashboard calendar widget."""
    from datetime import datetime, timezone, timedelta
    svc = _calendar_service()
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=days_ahead)
    res = svc.events().list(
        calendarId=calendar_id,
        timeMin=now.isoformat(),
        timeMax=end.isoformat(),
        singleEvents=True,
        orderBy="startTime",
        maxResults=50,
    ).execute()
    events = []
    for ev in res.get("items", []):
        all_day = "dateTime" not in ev["start"]
        events.append({
            "id": ev["id"],
            "title": ev.get("summary", "(no title)"),
            "start": ev["start"].get("dateTime") or ev["start"].get("date", ""),
            "end": ev["end"].get("dateTime") or ev["end"].get("date", ""),
            "all_day": all_day,
            "location": ev.get("location", ""),
        })
    return events


# ── Daily brief PDF emailer ───────────────────────────────────────────────────

def _pdf_safe(text: str) -> str:
    """Transliterate Unicode chars unsupported by Helvetica to ASCII equivalents."""
    table = {
        "—": "--", "–": "-", "‒": "-",
        "‘": "'",  "’": "'",
        "“": '"',  "”": '"',
        "…": "...",
        "•": "-",  "·": "-",
        "✓": "[x]", "✕": "[ ]",
        "✅": "[x]", "❌": "[ ]",
        "é": "e",  "è": "e", "ê": "e",
        "à": "a",  "â": "a",
        "ô": "o",  "û": "u", "ü": "u",
    }
    for char, replacement in table.items():
        text = text.replace(char, replacement)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _md_to_pdf_bytes(md_text: str) -> bytes:
    """Convert a Markdown daily brief to a branded PDF and return raw bytes."""
    from fpdf import FPDF

    # Brand palette
    NAVY   = (9,   15,  38)
    BLUE   = (58,  123, 213)
    BLUE_M = (30,  70,  140)   # muted blue for dividers
    BODY   = (25,  35,  65)
    MUTED  = (100, 130, 180)
    WHITE  = (255, 255, 255)
    LTBLUE = (190, 215, 255)
    ROW_A  = (235, 242, 255)   # table alternating row tint

    MARGIN = 18
    pdf = FPDF()
    pdf.set_margins(MARGIN, MARGIN, MARGIN)
    pdf.add_page()
    W = pdf.w - MARGIN * 2

    # ── Extract H1 title / date for header ───────────────────────────
    brief_title, brief_date = "Morning Briefing", ""
    for line in md_text.split("\n"):
        if line.startswith("# "):
            parts = line[2:].strip().split(" -- ", 1)
            if len(parts) == 2:
                brief_title, brief_date = parts[0], parts[1]
            else:
                brief_title = parts[0]
            break

    # ── Header bar ───────────────────────────────────────────────────
    HDR_H = 26
    pdf.set_fill_color(*NAVY)
    pdf.rect(0, 0, pdf.w, HDR_H, "F")

    # Accent stripe
    pdf.set_fill_color(*BLUE)
    pdf.rect(0, HDR_H - 2, pdf.w, 2, "F")

    pdf.set_xy(MARGIN, 6)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(*BLUE)
    pdf.cell(60, 6, "DigiGrowth OS", ln=False)

    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*LTBLUE)
    pdf.set_xy(MARGIN, 14)
    pdf.cell(60, 5, _pdf_safe(brief_title.upper()), ln=False)

    if brief_date:
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*LTBLUE)
        pdf.set_xy(MARGIN, 14)
        pdf.cell(W, 5, _pdf_safe(brief_date), align="R", ln=False)

    pdf.set_y(HDR_H + 6)

    # ── Body ─────────────────────────────────────────────────────────
    # Collect lines; handle table blocks as a unit
    lines = md_text.split("\n")
    i = 0
    while i < len(lines):
        s = _pdf_safe(lines[i].strip())

        # Skip H1 (already in header) and PDF marker
        if s.startswith("# ") or s.startswith("[[PDF:"):
            i += 1
            continue

        # Section header
        if s.startswith("## "):
            pdf.ln(4)
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(*BLUE)
            pdf.set_fill_color(*NAVY)
            pdf.set_x(MARGIN)
            pdf.cell(W, 7, s[3:].upper(), fill=True, ln=True)
            pdf.set_draw_color(*BLUE)
            pdf.set_line_width(0.5)
            pdf.line(MARGIN, pdf.get_y(), MARGIN + W, pdf.get_y())
            pdf.ln(3)
            i += 1
            continue

        # Divider
        if s == "---":
            pdf.ln(2)
            pdf.set_draw_color(*BLUE_M)
            pdf.set_line_width(0.2)
            pdf.line(MARGIN, pdf.get_y(), MARGIN + W, pdf.get_y())
            pdf.ln(4)
            i += 1
            continue

        # Table block — collect all consecutive | lines
        if s.startswith("|"):
            table_lines = []
            while i < len(lines) and _pdf_safe(lines[i].strip()).startswith("|"):
                row = _pdf_safe(lines[i].strip())
                if not all(c in "|-: " for c in row):  # skip separator rows
                    cells = [c.strip() for c in row.strip("|").split("|")]
                    table_lines.append(cells)
                i += 1
            if table_lines:
                max_cols = max(len(r) for r in table_lines)
                col_w = W / max_cols
                for ri, row in enumerate(table_lines):
                    is_header = ri == 0
                    fill_color = NAVY if is_header else (ROW_A if ri % 2 == 0 else WHITE)
                    text_color = WHITE if is_header else BODY
                    pdf.set_fill_color(*fill_color)
                    pdf.set_text_color(*text_color)
                    pdf.set_font("Helvetica", "B" if is_header else "", 8)
                    x_start = MARGIN
                    for ci, cell in enumerate(row[:max_cols]):
                        pdf.set_xy(x_start + ci * col_w, pdf.get_y())
                        pdf.cell(col_w, 6, cell, border=0, fill=True)
                    pdf.ln(6)
                pdf.ln(2)
            continue

        # Bullet
        if s.startswith("- "):
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*BODY)
            pdf.set_x(MARGIN + 4)
            pdf.multi_cell(W - 4, 5.5, f"-  {s[2:]}")
            i += 1
            continue

        # Italic footer (*text*)
        if s.startswith("*") and s.endswith("*") and len(s) > 2:
            pdf.ln(2)
            pdf.set_font("Helvetica", "I", 8)
            pdf.set_text_color(*MUTED)
            pdf.set_x(MARGIN)
            pdf.multi_cell(W, 5, s[1:-1])
            i += 1
            continue

        # Empty line
        if s == "":
            pdf.ln(2)
            i += 1
            continue

        # Bold inline (**text**)
        if s.startswith("**") and s.endswith("**") and len(s) > 4:
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*BODY)
            pdf.set_x(MARGIN)
            pdf.multi_cell(W, 5.5, s[2:-2])
            i += 1
            continue

        # Regular body text
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*BODY)
        pdf.set_x(MARGIN)
        pdf.multi_cell(W, 5.5, s)
        i += 1

    # ── Footer bar ───────────────────────────────────────────────────
    pdf.set_fill_color(*NAVY)
    pdf.rect(0, pdf.h - 10, pdf.w, 10, "F")
    pdf.set_xy(MARGIN, pdf.h - 7)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(*MUTED)
    pdf.cell(W, 4, "DigiGrowth OS  |  Confidential", align="C")

    return bytes(pdf.output())


def save_daily_brief_pdf() -> str:
    """Read the latest daily briefing MD, convert to PDF, and save it alongside the MD file."""
    from pathlib import Path

    reports_dir = Path(__file__).parent.parent.parent / "executive-assistant" / "reports"
    files = sorted(reports_dir.glob("daily-briefing-*.md"), reverse=True)
    if not files:
        return "No daily briefing file found — skipping PDF generation."

    md_path = files[0]
    pdf_path = md_path.with_suffix(".pdf")
    md_text = md_path.read_text(encoding="utf-8")

    try:
        pdf_bytes = _md_to_pdf_bytes(md_text)
        pdf_path.write_bytes(pdf_bytes)
        return f"Saved daily brief PDF: {pdf_path.name}"
    except Exception as exc:
        return f"PDF generation failed: {exc}"


# ── Dispatcher ────────────────────────────────────────────────────────────────

def execute_integration_tool(tool_name: str, tool_input: dict) -> str:
    """Route integration tool calls. Returns result string."""
    if tool_name == "gmail_search":
        return gmail_search(tool_input.get("query", ""), tool_input.get("max_results", 10))
    elif tool_name == "gmail_read_thread":
        return gmail_read_thread(tool_input.get("thread_id", ""))
    elif tool_name == "gmail_send":
        return gmail_send(tool_input["to"], tool_input["subject"], tool_input["body"])
    elif tool_name == "gmail_create_draft":
        return gmail_create_draft(tool_input["to"], tool_input["subject"], tool_input["body"])
    elif tool_name == "calendar_list_events":
        return calendar_list_events(tool_input.get("days_ahead", 7), tool_input.get("calendar_id", "primary"))
    elif tool_name == "calendar_create_event":
        return calendar_create_event(
            tool_input["title"],
            tool_input["start_datetime"],
            tool_input["end_datetime"],
            tool_input.get("description", ""),
            tool_input.get("attendees"),
            tool_input.get("calendar_id", "primary"),
        )
    elif tool_name == "calendar_update_event":
        return calendar_update_event(
            tool_input["event_id"],
            tool_input.get("title"),
            tool_input.get("start_datetime"),
            tool_input.get("end_datetime"),
            tool_input.get("description"),
            tool_input.get("calendar_id", "primary"),
        )
    elif tool_name == "calendar_delete_event":
        return calendar_delete_event(tool_input["event_id"], tool_input.get("calendar_id", "primary"))
    elif tool_name == "drive_search":
        return drive_search(tool_input.get("query", ""), tool_input.get("max_results", 10))
    elif tool_name == "drive_list_recent":
        return drive_list_recent(tool_input.get("max_results", 30), tool_input.get("days", 7))
    elif tool_name == "drive_read_file":
        return drive_read_file(tool_input["file_id"])
    elif tool_name == "notion_search":
        return notion_search(tool_input.get("query", ""), tool_input.get("max_results", 10))
    elif tool_name == "notion_read_page":
        return notion_read_page(tool_input["page_id"])
    elif tool_name == "notion_create_page":
        return notion_create_page(
            tool_input["parent_page_id"],
            tool_input["title"],
            tool_input.get("content", ""),
        )
    elif tool_name == "notion_update_page":
        return notion_update_page(
            tool_input["page_id"],
            tool_input.get("title"),
            tool_input.get("archived", False),
        )
    return f"Error: unknown integration tool '{tool_name}'"
