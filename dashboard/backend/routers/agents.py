"""
Agents router — file management + streaming Claude chat with tool use.

GET    /agents                             list agents from registry
POST   /agents                             scaffold new agent + add to registry
GET    /agents/{id}/files                  file tree
GET    /agents/{id}/files/{path}           read file
PUT    /agents/{id}/files/{path}           write/overwrite file
POST   /agents/{id}/files/{path}           create new file (409 if exists)
DELETE /agents/{id}/files/{path}           delete file
GET    /agents/{id}/history                last 40 chat rows
DELETE /agents/{id}/history               clear chat history
POST   /agents/{id}/chat                   SSE stream — Claude + tool-use loop
"""

import asyncio
import base64
import json
import os
import pathlib
import urllib.error
import urllib.request

import anthropic
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

from db import get_pool
from integrations import execute_integration_tool

router = APIRouter()

_REGISTRY_PATH = pathlib.Path(__file__).parent.parent / "agents_registry.json"
_REPO_ROOT = _REGISTRY_PATH.parent.parent.parent  # dashboard/backend/ → dashboard/ → repo root
_GITHUB_REPO = os.environ.get("GITHUB_REPO", "dylangroenendijk-sys/digigrowth-brain")


# ── GitHub API helpers ────────────────────────────────────────────────────────

def _gh_request(method: str, path: str, body: dict | None = None) -> dict:
    """Make a GitHub API request. Raises on HTTP error."""
    token = os.environ.get("GIT_TOKEN", "")
    url = f"https://api.github.com/repos/{_GITHUB_REPO}/contents/{path}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def _gh_get_sha(rel_path: str) -> str | None:
    """Get current file SHA from GitHub (None if file doesn't exist yet)."""
    try:
        result = _gh_request("GET", rel_path)
        return result.get("sha")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def github_push_file(file_abs: pathlib.Path, agent_name: str, operation: str) -> str:
    """Push a file write/create/delete to GitHub via REST API. Returns status string."""
    token = os.environ.get("GIT_TOKEN", "")
    if not token:
        return "no GIT_TOKEN — file saved locally only"

    try:
        rel = str(file_abs.relative_to(_REPO_ROOT))
    except ValueError:
        return "path outside repo — skipped"

    try:
        if operation == "delete_file":
            sha = _gh_get_sha(rel)
            if not sha:
                return "file not on GitHub — nothing to delete"
            _gh_request("DELETE", rel, {
                "message": f"Agent delete [{agent_name}]: {rel}",
                "sha": sha,
            })
            return "deleted on GitHub"

        # write_file / create_file
        content_b64 = base64.b64encode(file_abs.read_bytes()).decode()
        sha = _gh_get_sha(rel)  # None for new files
        payload = {
            "message": f"Agent edit [{agent_name}]: {operation} {rel}",
            "content": content_b64,
        }
        if sha:
            payload["sha"] = sha
        _gh_request("PUT", rel, payload)
        return "pushed to GitHub"

    except Exception as e:
        return f"github error: {e}"

async def crm_list_followups(limit: int = 20) -> str:
    """Contacts flagged 'Follow Up (Manual)' by the dialer — not lost, not closed."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT business, owner, phone, last_disposition, last_called_at
            FROM contacts
            WHERE last_disposition = 'Follow Up (Manual)'
            ORDER BY last_called_at ASC NULLS LAST
            LIMIT $1
            """,
            limit,
        )
    if not rows:
        return "No contacts currently flagged for follow-up in the OS."
    lines = []
    for r in rows:
        name = r["business"] or r["owner"] or r["phone"] or "Unknown"
        called = r["last_called_at"].strftime("%Y-%m-%d") if r["last_called_at"] else "no call logged"
        lines.append(f"{name} — {r['last_disposition']} — last called {called} — {r['phone'] or ''}")
    return "\n".join(lines)


async def os_sms_outreach_stats() -> str:
    """Live SMS funnel numbers (sent/reply/interested/booked) for 7d/30d/all-time."""
    from datetime import datetime, timedelta, timezone
    from routers.analytics import _sms_metrics

    pool = await get_pool()
    async with pool.acquire() as conn:
        stats_7d  = await _sms_metrics(conn, datetime.now(timezone.utc) - timedelta(days=7))
        stats_30d = await _sms_metrics(conn, datetime.now(timezone.utc) - timedelta(days=30))
        stats_all = await _sms_metrics(conn)

    def _line(label, s):
        return (f"{label}: {s['total_outreach']} sent, {s['reply_rate']}% replied, "
                f"{s['interested_rate']}% interested, {s['booked']} booked")

    if not stats_all["total_outreach"]:
        return "No SMS activity in the OS yet."

    return "\n".join([_line("Last 7 days", stats_7d), _line("Last 30 days", stats_30d), _line("All-time", stats_all)])


async def os_dialer_disposition_breakdown() -> str:
    """All-time call disposition breakdown from the OS dialer DB (call_logs), independent of the Sheets-based cold calling tracker."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        total_calls = await conn.fetchval("SELECT COUNT(*) FROM call_logs")
        rows = await conn.fetch(
            """
            SELECT disposition, COUNT(*) AS cnt
            FROM call_logs
            WHERE disposition IS NOT NULL
            GROUP BY disposition
            ORDER BY cnt DESC
            """
        )
    if not total_calls:
        return "No calls logged in the OS dialer yet."
    lines = [f"Total calls logged: {total_calls}"]
    for r in rows:
        pct = round(r["cnt"] / total_calls * 100, 1)
        lines.append(f"{r['disposition']}: {r['cnt']} ({pct}%)")
    return "\n".join(lines)


async def os_dialer_recent_notes(limit: int = 20) -> str:
    """Most recent OS dialer calls that have free-text notes attached — the DB-native equivalent of a call review."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT cl.disposition, cl.notes, cl.started_at,
                   c.business, c.owner
            FROM call_logs cl
            LEFT JOIN contacts c ON c.id = cl.contact_id
            WHERE cl.notes IS NOT NULL AND cl.notes != ''
            ORDER BY cl.started_at DESC NULLS LAST
            LIMIT $1
            """,
            limit,
        )
    if not rows:
        return "No call notes logged in the OS dialer yet."
    lines = []
    for r in rows:
        name = r["business"] or r["owner"] or "Unknown"
        date = r["started_at"].strftime("%Y-%m-%d") if r["started_at"] else "unknown date"
        lines.append(f"[{date}] {name} — {r['disposition'] or 'no disposition'}: {r['notes']}")
    return "\n".join(lines)


BLOCKED_FILENAMES = {".env", "credentials.json", "settings.local.json"}
SKIP_DIRS = {"node_modules", "__pycache__", ".venv", "venv", ".mypy_cache", ".pytest_cache"}

TOOLS = [
    {
        "name": "read_file",
        "description": "Read the full contents of a file in this agent's directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path from agent root, e.g. 'prompt.txt' or 'subdir/file.py'"}
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write or overwrite a file in this agent's directory. Creates parent dirs if needed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_files",
        "description": "List all files and directories in the agent's root or a subdirectory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "subdir": {"type": "string", "description": "Optional subdirectory path. Leave empty for root.", "default": ""}
            },
        },
    },
    {
        "name": "create_file",
        "description": "Create a new file. Returns an error if the file already exists — use write_file to overwrite.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "delete_file",
        "description": "Permanently delete a file. Cannot be undone. Does not delete directories.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"}
            },
            "required": ["path"],
        },
    },
    # ── Gmail ──────────────────────────────────────────────────────────────────
    {
        "name": "gmail_search",
        "description": "Search Gmail threads. Returns thread IDs and snippets. Requires GOOGLE_* env vars.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Gmail search query, e.g. 'from:someone@example.com subject:invoice'"},
                "max_results": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "gmail_read_thread",
        "description": "Read full content of a Gmail thread by thread_id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "thread_id": {"type": "string"},
            },
            "required": ["thread_id"],
        },
    },
    {
        "name": "gmail_send",
        "description": "Send an email from the configured Gmail account.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string"},
                "body": {"type": "string", "description": "Plain-text body"},
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "gmail_create_draft",
        "description": "Create a Gmail draft (does not send).",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["to", "subject", "body"],
        },
    },
    # ── Google Calendar ────────────────────────────────────────────────────────
    {
        "name": "calendar_list_events",
        "description": "List upcoming Google Calendar events. Requires GOOGLE_* env vars.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days_ahead": {"type": "integer", "default": 7, "description": "How many days ahead to look"},
                "calendar_id": {"type": "string", "default": "primary"},
            },
        },
    },
    {
        "name": "calendar_create_event",
        "description": "Create a Google Calendar event.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "start_datetime": {"type": "string", "description": "ISO 8601 datetime, e.g. '2026-06-10T09:00:00-07:00'"},
                "end_datetime": {"type": "string", "description": "ISO 8601 datetime"},
                "description": {"type": "string", "default": ""},
                "attendees": {"type": "array", "items": {"type": "string"}, "description": "List of attendee emails"},
                "calendar_id": {"type": "string", "default": "primary"},
            },
            "required": ["title", "start_datetime", "end_datetime"],
        },
    },
    {
        "name": "calendar_update_event",
        "description": "Update an existing Google Calendar event by event_id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string"},
                "title": {"type": "string"},
                "start_datetime": {"type": "string"},
                "end_datetime": {"type": "string"},
                "description": {"type": "string"},
                "calendar_id": {"type": "string", "default": "primary"},
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "calendar_delete_event",
        "description": "Delete a Google Calendar event by event_id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string"},
                "calendar_id": {"type": "string", "default": "primary"},
            },
            "required": ["event_id"],
        },
    },
    # ── Google Drive ───────────────────────────────────────────────────────────
    {
        "name": "drive_search",
        "description": "Search Google Drive files. Requires GOOGLE_* env vars.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Drive query, e.g. \"name contains 'invoice'\""},
                "max_results": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "drive_list_recent",
        "description": "List Google Drive files modified or opened within the last N days (default 7). Returns file IDs and names.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days":        {"type": "integer", "default": 7,  "description": "How many days back to look"},
                "max_results": {"type": "integer", "default": 30, "description": "Max files to return"},
            },
        },
    },
    {
        "name": "drive_read_file",
        "description": "Read content of a Google Drive file by file_id. Exports Google Docs as plain text.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_id": {"type": "string"},
            },
            "required": ["file_id"],
        },
    },
    # ── OS Dashboard ───────────────────────────────────────────────────────────
    {
        "name": "update_os_stats",
        "description": (
            "Write sales and outreach metrics extracted from Google Sheets directly into the OS dashboard "
            "and Analytics panel. Updates sales_stats.json which drives: Sales Statistics card, "
            "Daily Scoreboard (shows/closes), and the bottom of the 6-Stage Acquisition Funnel. "
            "Only provide fields where you found real data — omit fields you did not find. "
            "Base fields (shows, closes, total_revenue, discovery_calls, etc.) should be cumulative "
            "all-time totals. If the source sheet has a date column, also compute and pass the "
            "_30d and _7d variants (sum of rows dated within the last 30/7 days) so the Analytics "
            "panel's period toggle (7D/30D/All Time) reflects real data instead of falling back to 0."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                # Sales funnel (cumulative all-time totals)
                "shows":              {"type": "integer", "description": "Total prospects who showed up to a sales call/demo"},
                "closes":             {"type": "integer", "description": "Total deals closed / clients signed"},
                "total_revenue":      {"type": "number",  "description": "Total revenue collected in dollars"},
                "avg_deal_size":      {"type": "number",  "description": "Average deal size in dollars (auto-calculated if omitted)"},
                "discovery_calls":    {"type": "integer", "description": "Total discovery / intro calls completed"},
                "strategy_sessions":  {"type": "integer", "description": "Total strategy sessions / deep-dive calls completed"},
                # Sales funnel — last 30 days (sum rows dated within last 30 days, using the sheet's date column)
                "shows_30d":            {"type": "integer", "description": "Shows in last 30 days"},
                "closes_30d":           {"type": "integer", "description": "Closes in last 30 days"},
                "total_revenue_30d":    {"type": "number",  "description": "Revenue collected in last 30 days"},
                "discovery_calls_30d":  {"type": "integer", "description": "Discovery calls in last 30 days"},
                # Sales funnel — last 7 days
                "shows_7d":             {"type": "integer", "description": "Shows in last 7 days"},
                "closes_7d":            {"type": "integer", "description": "Closes in last 7 days"},
                "total_revenue_7d":     {"type": "number",  "description": "Revenue collected in last 7 days"},
                "discovery_calls_7d":   {"type": "integer", "description": "Discovery calls in last 7 days"},
                # Outreach — all-time totals
                "calls_made":            {"type": "integer", "description": "All-time total calls dialed"},
                "calls_answered":        {"type": "integer", "description": "All-time total calls answered (pickups)"},
                "contacts_reached":      {"type": "integer", "description": "All-time total contacts spoken to / pitched (the sheet's own KPI panel calls this 'Pitches')"},
                "resonations":           {"type": "integer", "description": "All-time total prospects who resonated with the pitch (the sheet's 'Resonations' column)"},
                "appointments_booked":   {"type": "integer", "description": "All-time total appointments booked"},
                "sms_sent":              {"type": "integer", "description": "All-time total SMS sent"},
                # Outreach — last 30 days (sum rows dated within last 30 days)
                "calls_made_30d":        {"type": "integer", "description": "Calls dialed in last 30 days"},
                "calls_answered_30d":    {"type": "integer", "description": "Calls answered in last 30 days"},
                "contacts_reached_30d":  {"type": "integer", "description": "Contacts reached in last 30 days"},
                "resonations_30d":       {"type": "integer", "description": "Resonations in last 30 days"},
                "appointments_booked_30d":{"type": "integer", "description": "Appointments booked in last 30 days"},
                # Outreach — last 7 days (sum rows dated within last 7 days)
                "calls_made_7d":         {"type": "integer", "description": "Calls dialed in last 7 days"},
                "calls_answered_7d":     {"type": "integer", "description": "Calls answered in last 7 days"},
                "contacts_reached_7d":   {"type": "integer", "description": "Contacts reached in last 7 days"},
                "resonations_7d":        {"type": "integer", "description": "Resonations in last 7 days"},
                "appointments_booked_7d":{"type": "integer", "description": "Appointments booked in last 7 days"},
                "source_note":           {"type": "string",  "description": "Brief note on which sheet(s) this data came from"},
                # Per-day breakdown — powers campaign-scoped calling analytics, which
                # need to sum an arbitrary date range instead of the fixed 7d/30d/all-time
                # buckets above. Only include days you have real cold-calling-sheet data
                # for; omitted days are left untouched (upserted, not wiped) on every call.
                "daily": {
                    "type": "object",
                    "description": (
                        "Per-day cold-calling totals, keyed by ISO date (YYYY-MM-DD). Each "
                        "value is an object with any of: calls_made, calls_answered, "
                        "contacts_reached, resonations, appointments_booked (sum of that "
                        "day's rows from the Cold Calling Metrics sheet). Merged into "
                        "existing daily history — only pass days you actually found data for."
                    ),
                },
            },
        },
    },
    {
        "name": "crm_list_followups",
        "description": (
            "List CRM contacts in the DigiGrowth OS whose last call disposition is 'Follow Up (Manual)' "
            "— i.e. prospects flagged for a manual follow-up during a dialer call, as opposed "
            "to leads marked lost/not-interested or already closed. Returns business/owner name, phone, "
            "disposition, and last call date, oldest first."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 20, "description": "Max contacts to return"},
            },
        },
    },
    {
        "name": "os_sms_outreach_stats",
        "description": (
            "Live SMS outreach funnel numbers from the DigiGrowth OS (sms_messages/sms_conversations "
            "tables) — messages sent, reply rate, interested rate, and appointments booked, for the "
            "last 7 days, last 30 days, and all-time. Use this for the SMS half of the daily briefing's "
            "Outreach section (cold calling numbers still come from the Google Drive tracker)."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "os_dialer_disposition_breakdown",
        "description": (
            "All-time call disposition breakdown from the OS dialer DB (call_logs table) — total calls "
            "logged and a count/percentage per disposition (e.g. Appointment Booked, Not Interested, "
            "Voicemail, Gatekeeper). This is DB-native, live OS data, separate from the Sheets-based "
            "cold calling tracker in Google Drive — use it to see what the dialer itself has actually "
            "recorded."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "os_dialer_recent_notes",
        "description": (
            "Most recent OS dialer calls that have free-text notes attached (call_logs.notes), with "
            "disposition, contact, and date — the DB-native equivalent of a manual call review. Use "
            "this to surface qualitative signal (objections heard, what worked/didn't) straight from "
            "logged calls, separate from any Drive call-review docs."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 20, "description": "Max notes to return"},
            },
        },
    },
    # ── Notion ─────────────────────────────────────────────────────────────────
    {
        "name": "notion_search",
        "description": "Search Notion pages and databases. Requires NOTION_TOKEN env var.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "notion_read_page",
        "description": "Read content of a Notion page by page_id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "page_id": {"type": "string"},
            },
            "required": ["page_id"],
        },
    },
    {
        "name": "notion_create_page",
        "description": "Create a new Notion page as a child of an existing page.",
        "input_schema": {
            "type": "object",
            "properties": {
                "parent_page_id": {"type": "string"},
                "title": {"type": "string"},
                "content": {"type": "string", "description": "Initial paragraph text", "default": ""},
            },
            "required": ["parent_page_id", "title"],
        },
    },
    {
        "name": "notion_update_page",
        "description": "Update title or archive a Notion page.",
        "input_schema": {
            "type": "object",
            "properties": {
                "page_id": {"type": "string"},
                "title": {"type": "string"},
                "archived": {"type": "boolean", "default": False},
            },
            "required": ["page_id"],
        },
    },
]

_INTEGRATION_TOOLS = {
    "gmail_search", "gmail_read_thread", "gmail_send", "gmail_create_draft",
    "calendar_list_events", "calendar_create_event", "calendar_update_event", "calendar_delete_event",
    "drive_search", "drive_list_recent", "drive_read_file",
    "notion_search", "notion_read_page", "notion_create_page", "notion_update_page",
}


# ── Registry helpers ──────────────────────────────────────────────────────────

def _load_registry() -> list[dict]:
    return json.loads(_REGISTRY_PATH.read_text())


def _get_agent(agent_id: str) -> dict:
    for a in _load_registry():
        if a["id"] == agent_id:
            root = (pathlib.Path(__file__).parent.parent / a["root_dir"]).resolve()
            return {**a, "abs_root": root}
    raise HTTPException(status_code=404, detail="Agent not found")


# ── Path sandbox ──────────────────────────────────────────────────────────────

def _safe_path(root: pathlib.Path, rel: str) -> pathlib.Path:
    """Resolve rel inside root. Raises 403 on traversal or blocked filenames."""
    target = (root / rel).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise HTTPException(status_code=403, detail="Path traversal not allowed")
    if target.name in BLOCKED_FILENAMES:
        raise HTTPException(status_code=403, detail=f"Access to {target.name} is forbidden")
    return target


# ── Tool executor (sync, run via asyncio.to_thread) ───────────────────────────

def _execute_tool(agent: dict, tool_name: str, tool_input: dict) -> str:
    root: pathlib.Path = agent["abs_root"]

    try:
        if tool_name == "list_files":
            subdir = (tool_input.get("subdir") or "").strip()
            base = _safe_path(root, subdir) if subdir else root
            if not base.exists():
                return f"Error: directory '{subdir}' does not exist"
            VISIBLE_DOTS = {".env.example", ".claude"}
            lines = []
            for item in sorted(base.rglob("*")):
                # Skip hidden dirs except .claude (skills/rules) and .env.example
                if any(p.name.startswith(".") and p.name not in VISIBLE_DOTS
                       for p in item.parents if p != root and p != item):
                    continue
                if item.name.startswith(".") and item.name not in VISIBLE_DOTS:
                    continue
                rel = item.relative_to(root)
                indent = "  " * (len(rel.parts) - 1)
                icon = "/" if item.is_dir() else " "
                lines.append(f"{indent}{icon} {item.name}")
            return "\n".join(lines) if lines else "(empty)"

        elif tool_name == "read_file":
            path = tool_input.get("path", "")
            target = _safe_path(root, path)
            if not target.exists() or not target.is_file():
                return f"Error: '{path}' does not exist"
            size = target.stat().st_size
            if size > 100_000:
                return f"Error: file too large ({size} bytes). Showing first 100 lines instead is not supported — try a more specific question."
            return target.read_text(errors="replace")

        elif tool_name in ("write_file", "create_file"):
            path = tool_input.get("path", "")
            content = tool_input.get("content", "")
            target = _safe_path(root, path)
            if tool_name == "create_file" and target.exists():
                return f"Error: '{path}' already exists. Use write_file to overwrite."
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
            git_status = github_push_file(target, agent["name"], tool_name)
            return f"OK: wrote {len(content)} chars to {path}\ngit: {git_status}"

        elif tool_name == "delete_file":
            path = tool_input.get("path", "")
            target = _safe_path(root, path)
            if not target.exists():
                return f"Error: '{path}' does not exist"
            if target.is_dir():
                return "Error: cannot delete directories via this tool"
            target.unlink()
            git_status = github_push_file(target, agent["name"], "delete_file")
            return f"OK: deleted {path}\ngit: {git_status}"

        elif tool_name == "update_os_stats":
            stats_path = pathlib.Path(__file__).parent.parent / "sales_stats.json"
            try:
                current = json.loads(stats_path.read_text()) if stats_path.exists() else {}
            except Exception:
                current = {}

            FIELD_MAP = {
                "shows":                  "shows",
                "closes":                 "closes",
                "total_revenue":          "total_revenue",
                "avg_deal_size":          "avg_deal_size",
                "discovery_calls":        "discovery_calls",
                "strategy_sessions":      "strategy_sessions",
                # sales funnel — 30-day / 7-day
                "shows_30d":              "shows_30d",
                "closes_30d":             "closes_30d",
                "total_revenue_30d":      "total_revenue_30d",
                "discovery_calls_30d":    "discovery_calls_30d",
                "shows_7d":               "shows_7d",
                "closes_7d":              "closes_7d",
                "total_revenue_7d":       "total_revenue_7d",
                "discovery_calls_7d":     "discovery_calls_7d",
                # all-time
                "calls_made":             "sheet_calls_made",
                "calls_answered":         "sheet_calls_answered",
                "contacts_reached":       "sheet_contacts_reached",
                "resonations":            "sheet_resonations",
                "appointments_booked":    "sheet_appointments_booked",
                "sms_sent":               "sheet_sms_sent",
                # 30-day
                "calls_made_30d":         "sheet_calls_made_30d",
                "calls_answered_30d":     "sheet_calls_answered_30d",
                "contacts_reached_30d":   "sheet_contacts_reached_30d",
                "resonations_30d":        "sheet_resonations_30d",
                "appointments_booked_30d":"sheet_appointments_booked_30d",
                # 7-day
                "calls_made_7d":          "sheet_calls_made_7d",
                "calls_answered_7d":      "sheet_calls_answered_7d",
                "contacts_reached_7d":    "sheet_contacts_reached_7d",
                "resonations_7d":         "sheet_resonations_7d",
                "appointments_booked_7d": "sheet_appointments_booked_7d",
            }
            updated = []
            for key, stat_key in FIELD_MAP.items():
                if key in tool_input and tool_input[key] is not None:
                    current[stat_key] = tool_input[key]
                    updated.append(f"{stat_key}={tool_input[key]}")

            # Per-day breakdown — upsert each date's fields, never wipe history,
            # since a single digest run only covers whatever window the sheet
            # actually had fresh data for (see input_schema description above).
            daily_input = tool_input.get("daily")
            if isinstance(daily_input, dict) and daily_input:
                daily = current.setdefault("daily", {})
                for date_key, day_fields in daily_input.items():
                    if not isinstance(day_fields, dict):
                        continue
                    daily.setdefault(date_key, {}).update(day_fields)
                updated.append(f"daily+={len(daily_input)}d")

            # Auto-calculate avg_deal_size if not provided
            closes = current.get("closes", 0)
            revenue = current.get("total_revenue", 0)
            if closes and revenue and "avg_deal_size" not in tool_input:
                current["avg_deal_size"] = round(revenue / closes)

            from datetime import datetime as _dt, timezone as _tz
            current["last_sheet_sync"] = _dt.now().isoformat()
            # last_sheet_sync bumps on every call, including no-op runs where the
            # cold-calling sheet wasn't reopened — sheet_data_last_changed only
            # bumps when fresh sheet_* data actually came in this call, so
            # analytics.py's _sheet_stat() can tell "digest ran today" apart from
            # "cold-calling sheet was genuinely re-read today" and decay stale
            # 7d/30d buckets instead of serving them forever.
            if any(stat_key.startswith("sheet_") for key, stat_key in FIELD_MAP.items()
                   if key in tool_input and tool_input[key] is not None):
                current["sheet_data_last_changed"] = _dt.now(_tz.utc).isoformat()
            if tool_input.get("source_note"):
                current["last_sheet_sync_note"] = tool_input["source_note"]

            stats_path.write_text(json.dumps(current, indent=2))
            git_status = github_push_file(stats_path, agent["name"], "write_file")
            if not updated:
                return "No recognized stat fields provided — sales_stats.json unchanged."
            return (
                f"OS stats updated: {', '.join(updated)}\n"
                f"Dashboard and Analytics panel will reflect these on next load.\n"
                f"git: {git_status}"
            )

        elif tool_name in _INTEGRATION_TOOLS:
            return execute_integration_tool(tool_name, tool_input)

        else:
            return f"Error: unknown tool '{tool_name}'"

    except HTTPException as e:
        return f"Error: {e.detail}"
    except Exception as e:
        return f"Error: {e}"


# ── System prompt builder ──────────────────────────────────────────────────────

_MODE_INSTRUCTIONS = {
    "plan": (
        "\n\nMODE: PLAN ONLY — Do NOT call write_file, create_file, or delete_file under any circumstances. "
        "Instead, describe exactly what changes you would make, show the proposed content inline, "
        "and tell the user to switch to Auto mode to apply them."
    ),
    "ask": (
        "\n\nMODE: ASK BEFORE EDITS — Before calling write_file, create_file, or delete_file, "
        "always stop and describe the exact change you're about to make, then ask the user to confirm. "
        "Only proceed with the file operation after explicit user approval."
    ),
}

def _resolve_at_includes(content: str, root: pathlib.Path, depth: int = 0) -> str:
    """Replace @path/to/file.md references with the file's content (one level deep)."""
    if depth > 2:
        return content
    lines = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("@") and not stripped.startswith("@@"):
            ref_path = stripped[1:].strip()
            target = (root / ref_path).resolve()
            try:
                target.relative_to(root)
                if target.exists() and target.is_file():
                    included = target.read_text(errors="replace")[:3000]
                    included = _resolve_at_includes(included, root, depth + 1)
                    lines.append(f"<!-- {ref_path} -->\n{included}")
                    continue
            except (ValueError, Exception):
                pass
        lines.append(line)
    return "\n".join(lines)


def _load_skills(root: pathlib.Path, match_message: str = "") -> str:
    """
    Load SKILL.md files from .claude/skills/.
    If match_message is provided, only load the skill whose folder name or first line
    best matches the message (avoids bloating the system prompt with all skills).
    Falls back to listing skill names only when no match.
    """
    skills_dir = root / ".claude" / "skills"
    if not skills_dir.exists():
        return ""

    skill_files = {}
    for skill_dir in sorted(skills_dir.iterdir()):
        skill_file = skill_dir / "SKILL.md"
        if skill_file.exists():
            skill_files[skill_dir.name] = skill_file

    if not skill_files:
        return ""

    if match_message:
        msg_lower = match_message.lower()
        for name, path in skill_files.items():
            # Match on folder name words or first heading in the file
            name_words = name.replace("-", " ").replace("_", " ")
            try:
                first_line = path.read_text(errors="replace").split("\n")[0].lower()
            except Exception:
                first_line = ""
            if any(w in msg_lower for w in name_words.split()) or name_words in msg_lower:
                try:
                    content = path.read_text(errors="replace")[:15000]
                    return f"### Active Skill: {name}\n\nExecute these instructions now:\n\n{content}"
                except Exception:
                    pass

    # No match — just list available skill names so Claude can read one if needed
    names = ", ".join(skill_files.keys())
    return f"Available skills (read the relevant SKILL.md if needed): {names}"


def _build_system_prompt(agent: dict, mode: str = "auto", match_message: str = "") -> str:
    from datetime import datetime as _dt
    today = _dt.now().strftime("%Y-%m-%d")

    root: pathlib.Path = agent["abs_root"]
    name = agent["name"]
    description = agent.get("description", "")

    parts = [
        f"Today's date: {today}\n\n"
        f"You are a code and configuration assistant for the **{name}** agent in Dylan's DigiGrowth OS. "
        f"Description: {description}\n\n"
        "You have tools to read, write, create, and delete files in this agent's directory. "
        "Use them freely — read files before editing them, and explain your changes.\n\n"
        "MEMORY: You have a persistent memory file at memory.md in your directory. "
        "After any conversation where you learn something important — a decision, a preference, "
        "a key fact, a recurring task — write it to memory.md using write_file. "
        "Keep entries concise, one fact per bullet. This file is loaded every session so you remember across conversations.\n\n"
        "SECURITY: NEVER read, write, or reference .env files, credentials.json, or settings.local.json. "
        "These contain secrets and are blocked at the API level.\n\n"
        "When making code changes, follow the existing patterns in the files you read first. "
        "Be concise — the user is technical."
    ]

    if mode in _MODE_INSTRUCTIONS:
        parts.append(_MODE_INSTRUCTIONS[mode])

    for candidate in ["memory.md", "CLAUDE.md", "prompt.txt", "role.txt"]:
        p = root / candidate
        if p.exists():
            try:
                raw = p.read_text(errors="replace")[:6000]
                content = _resolve_at_includes(raw, root)
                parts.append(f"\n---\n## {candidate}\n\n{content}")
            except Exception:
                pass

    skills_content = _load_skills(root, match_message)
    if skills_content:
        parts.append(f"\n---\n## Skills\n\n{skills_content}")

    return "\n".join(parts)


# ── Agent registry endpoints ──────────────────────────────────────────────────

@router.get("/agents")
async def list_agents():
    return _load_registry()


@router.post("/agents")
async def create_agent(payload: dict):
    name = (payload.get("name") or "").strip()
    description = (payload.get("description") or "").strip()
    agent_type = (payload.get("type") or "assistant").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name required")

    agent_id = name.lower().replace(" ", "-")
    repo_root = _REGISTRY_PATH.parent.parent.parent  # agents_registry.json → backend/ → dashboard/ → repo root
    agent_root = repo_root / agent_id

    if agent_root.exists():
        raise HTTPException(status_code=400, detail=f"Directory '{agent_id}' already exists")

    agent_root.mkdir(parents=True)

    (agent_root / "run.py").write_text(
        f'"""\n{name}\nType: {agent_type}\n"""\n\nif __name__ == "__main__":\n    pass\n'
    )
    (agent_root / "config.json").write_text("{}\n")
    (agent_root / "prompt.txt").write_text("")
    (agent_root / "CLAUDE.md").write_text(f"## Agent: {name}\n\n{description}\n")
    (agent_root / "requirements.txt").write_text("anthropic\n")
    (agent_root / ".env.example").write_text("ANTHROPIC_API_KEY=\n")

    registry = _load_registry()
    registry.append({
        "id": agent_id,
        "name": name,
        "description": description,
        "root_dir": f"../../{agent_id}",
        "color": "#3a7bd5",
        "badge_class": "badge-blue",
    })
    _REGISTRY_PATH.write_text(json.dumps(registry, indent=2))

    # Push scaffold files + updated registry to GitHub
    def _push_new_agent():
        for f in list(agent_root.iterdir()) + [_REGISTRY_PATH]:
            try:
                github_push_file(f, "system", "create_file")
            except Exception:
                pass

    await asyncio.to_thread(_push_new_agent)

    return {"id": agent_id, "name": name}


# ── File management endpoints ─────────────────────────────────────────────────

@router.get("/agents/{agent_id}/files")
async def list_files(agent_id: str, subdir: str = ""):
    agent = _get_agent(agent_id)
    root: pathlib.Path = agent["abs_root"]
    base = _safe_path(root, subdir) if subdir else root

    def _build_tree(path: pathlib.Path) -> list:
        entries = []
        try:
            items = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name))
        except PermissionError:
            return entries
        for item in items:
            if item.name.startswith(".") and item.name not in (".env.example", ".claude"):
                continue
            if item.is_dir() and item.name in SKIP_DIRS:
                continue
            rel = str(item.relative_to(root))
            if item.is_dir():
                entries.append({
                    "name": item.name, "path": rel, "type": "dir",
                    "children": _build_tree(item),
                })
            else:
                entries.append({
                    "name": item.name, "path": rel, "type": "file",
                    "size": item.stat().st_size,
                })
        return entries

    return {"files": _build_tree(base)}


@router.get("/agents/{agent_id}/files/{path:path}")
async def read_file_endpoint(agent_id: str, path: str):
    agent = _get_agent(agent_id)
    target = _safe_path(agent["abs_root"], path)
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    size = target.stat().st_size
    if size > 500_000:
        raise HTTPException(status_code=413, detail="File too large to display (>500KB)")
    return {"path": path, "content": target.read_text(errors="replace"), "size": size}


@router.get("/agents/{agent_id}/brief-pdf")
async def serve_brief_pdf(agent_id: str):
    """Serve the latest daily-briefing PDF, generating it from the MD if needed."""
    import integrations as _integrations
    agent = _get_agent(agent_id)
    reports_dir = agent["abs_root"] / "reports"

    pdfs = sorted(reports_dir.glob("daily-briefing-*.pdf"), reverse=True)

    # If no PDF yet, try to generate one from the latest MD file
    if not pdfs:
        mds = sorted(reports_dir.glob("daily-briefing-*.md"), reverse=True)
        if not mds:
            raise HTTPException(status_code=404, detail="No daily brief found")
        md_path = mds[0]
        pdf_path = md_path.with_suffix(".pdf")
        try:
            pdf_bytes = await asyncio.to_thread(
                _integrations._md_to_pdf_bytes, md_path.read_text(encoding="utf-8")
            )
            pdf_path.write_bytes(pdf_bytes)
            pdfs = [pdf_path]
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"PDF generation failed: {exc}")

    return Response(
        content=pdfs[0].read_bytes(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=\"{pdfs[0].name}\""},
    )


@router.post("/agents/process-pending-approvals")
async def process_pending_approvals_now(date: str | None = None):
    """On-demand trigger for the pending-approvals relay (see
    pending_approvals_relay.py) — lets Dylan or a Doppler-authenticated
    session process a newsletter/blog draft immediately instead of waiting
    for the daily 6:40am ET Railway poll. `date` defaults to today (ET) if
    omitted; pass YYYY-MM-DD to process a specific day's draft."""
    from pending_approvals_relay import process_pending_approvals
    result = await process_pending_approvals(date)
    return {"result": result}


@router.get("/agents/campaign-sms-export")
async def campaign_sms_export(campaign_id: int):
    """Read-only dump of every SMS conversation tagged to a campaign — full
    message thread per contact, plus funnel stage flags and disposition.
    One-shot ad-hoc report, not a paginated UI feed: built for pulling a
    campaign's raw messaging data out for qualitative/psychology-driven
    analysis (message wording, response patterns) that the aggregate
    /analytics/outreach numbers can't answer on their own."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        convs = await conn.fetch(
            """
            SELECT sc.phone, sc.status, sc.disposition, sc.updated_at,
                   sc.stage_initial_outreach, sc.stage_replied, sc.stage_dm_reached,
                   sc.stage_primed, sc.stage_engaged, sc.stage_interested,
                   c.id AS contact_id, c.business, c.owner, c.grade, c.state, c.opener
            FROM sms_conversations sc
            LEFT JOIN contacts c ON c.id = sc.contact_id
            WHERE sc.campaign_id = $1
            ORDER BY sc.updated_at DESC NULLS LAST
            """,
            campaign_id,
        )
        result = []
        for conv in convs:
            msgs = await conn.fetch(
                "SELECT direction, body, sent_at, stage FROM sms_messages WHERE phone = $1 ORDER BY sent_at",
                conv["phone"],
            )
            row = dict(conv)
            row["messages"] = [dict(m) for m in msgs]
            result.append(row)
    return {"campaign_id": campaign_id, "conversation_count": len(result), "conversations": result}


@router.post("/agents/export-sms-stats-now")
async def export_sms_stats_now():
    """On-demand trigger for the SMS outreach snapshot export (see
    main.py's _export_sms_outreach_stats, scheduled daily 5:50am ET) —
    lets Dylan verify the file lands on GitHub right now instead of
    waiting for tomorrow's export."""
    import main
    await main._export_sms_outreach_stats()
    return {"ok": True}


@router.post("/agents/post-report-now")
async def post_report_now(filename_prefix: str, date: str | None = None):
    """On-demand trigger mirroring main.py's _post_report_from_github cron
    jobs (sheets-digest 6:15am ET, daily-briefing 6:30am ET) — lets Dylan
    paste a report into the EA chat immediately instead of waiting for
    tomorrow's poll, which looks for tomorrow's date and would never pick up
    a report that landed on GitHub late. `filename_prefix` is
    "daily-briefing" or "sheets-digest"; `date` defaults to today (ET)."""
    import base64
    from datetime import datetime
    from zoneinfo import ZoneInfo

    import httpx

    date_str = date or datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    rel_path = f"executive-assistant/reports/{filename_prefix}-{date_str}.md"
    repo = os.environ.get("GITHUB_REPO", "dylangroenendijk-sys/digigrowth-brain")
    token = os.environ.get("GIT_TOKEN", "")
    api_url = f"https://api.github.com/repos/{repo}/contents/{rel_path}"
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(api_url, headers=headers)
    if resp.status_code == 404:
        return {"result": f"{rel_path} not found on GitHub"}
    resp.raise_for_status()
    report_text = base64.b64decode(resp.json()["content"]).decode("utf-8").strip()
    if not report_text:
        return {"result": f"{rel_path} is empty"}

    local_path = pathlib.Path("/repo") / rel_path
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_text(report_text, encoding="utf-8")

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO agent_chats (agent_id, role, content) VALUES ($1, $2, $3)",
            "executive-assistant", "assistant",
            json.dumps([{"type": "text", "text": report_text}]),
        )

    if filename_prefix == "daily-briefing":
        try:
            from integrations import save_daily_brief_pdf
            await asyncio.get_event_loop().run_in_executor(None, save_daily_brief_pdf)
        except Exception as e:
            return {"result": f"posted to chat; PDF step failed: {e}"}

    return {"result": f"posted {rel_path} to EA chat"}


@router.get("/agents/{agent_id}/newsletter-pdf")
async def serve_newsletter_pdf(agent_id: str):
    """Serve the latest newsletter-draft PDF, generating it from the MD if needed."""
    import integrations as _integrations
    agent = _get_agent(agent_id)
    root_dir = agent["abs_root"]

    pdfs = sorted(root_dir.glob("newsletter-draft-*.pdf"), reverse=True)

    # If no PDF yet, try to generate one from the latest MD file
    if not pdfs:
        mds = sorted(root_dir.glob("newsletter-draft-*.md"), reverse=True)
        if not mds:
            raise HTTPException(status_code=404, detail="No newsletter draft found")
        md_path = mds[0]
        pdf_path = md_path.with_suffix(".pdf")
        try:
            pdf_bytes = await asyncio.to_thread(
                _integrations._md_to_pdf_bytes, md_path.read_text(encoding="utf-8")
            )
            pdf_path.write_bytes(pdf_bytes)
            pdfs = [pdf_path]
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"PDF generation failed: {exc}")

    return Response(
        content=pdfs[0].read_bytes(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=\"{pdfs[0].name}\""},
    )


@router.put("/agents/{agent_id}/files/{path:path}")
async def write_file_endpoint(agent_id: str, path: str, payload: dict):
    agent = _get_agent(agent_id)
    target = _safe_path(agent["abs_root"], path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(payload.get("content", ""))
    git_status = await asyncio.to_thread(github_push_file, target, agent["name"], "write_file")
    return {"ok": True, "git": git_status}


@router.post("/agents/{agent_id}/files/{path:path}")
async def create_file_endpoint(agent_id: str, path: str, payload: dict):
    agent = _get_agent(agent_id)
    target = _safe_path(agent["abs_root"], path)
    if target.exists():
        raise HTTPException(status_code=409, detail="File already exists")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(payload.get("content", ""))
    git_status = await asyncio.to_thread(github_push_file, target, agent["name"], "create_file")
    return {"ok": True, "git": git_status}


@router.delete("/agents/{agent_id}/files/{path:path}")
async def delete_file_endpoint(agent_id: str, path: str):
    agent = _get_agent(agent_id)
    target = _safe_path(agent["abs_root"], path)
    if not target.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if target.is_dir():
        raise HTTPException(status_code=400, detail="Cannot delete directories")
    target.unlink()
    git_status = await asyncio.to_thread(github_push_file, target, agent["name"], "delete_file")
    return {"ok": True, "git": git_status}


# ── Direct message inject (used by cloud routines to post to chat) ────────────

@router.post("/agents/{agent_id}/inject")
async def inject_message(agent_id: str, payload: dict):
    """Insert a message directly into agent chat history without triggering Claude."""
    content = (payload.get("content") or "").strip()
    role = payload.get("role", "assistant")
    if not content:
        raise HTTPException(status_code=400, detail="content required")
    if role not in ("assistant", "user"):
        raise HTTPException(status_code=400, detail="role must be assistant or user")
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO agent_chats (agent_id, role, content) VALUES ($1, $2, $3)",
            agent_id, role, json.dumps([{"type": "text", "text": content}]),
        )
        if role == "assistant":
            preview = content[:200].strip()
            if preview:
                agent_label = next(
                    (a["name"] for a in _load_registry() if a["id"] == agent_id), agent_id
                )
                await conn.execute(
                    "INSERT INTO agent_messages (agent, message) VALUES ($1, $2)",
                    agent_label, preview,
                )
    return {"ok": True}


# ── Chat history endpoints ────────────────────────────────────────────────────

@router.get("/agents/{agent_id}/history")
async def get_history(agent_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, role, content, created_at FROM (
                SELECT id, role, content, created_at
                FROM agent_chats WHERE agent_id = $1
                ORDER BY created_at DESC LIMIT 20
            ) sub ORDER BY sub.created_at ASC
            """,
            agent_id,
        )
    return [
        {"id": r["id"], "role": r["role"],
         "content": json.loads(r["content"]), "created_at": str(r["created_at"])}
        for r in rows
    ]


@router.delete("/agents/{agent_id}/history")
async def clear_history(agent_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM agent_chats WHERE agent_id = $1", agent_id)
    return {"ok": True}


# ── Streaming chat endpoint ───────────────────────────────────────────────────

@router.post("/agents/{agent_id}/chat")
async def chat(agent_id: str, request: Request):
    body = await request.json()
    user_message = (body.get("message") or "").strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="message required")

    agent = _get_agent(agent_id)
    pool = await get_pool()

    # Load last 40 rows as context (preserves full tool-use alternation)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT role, content FROM (
                SELECT role, content, created_at
                FROM agent_chats WHERE agent_id = $1
                ORDER BY created_at DESC LIMIT 20
            ) sub ORDER BY sub.created_at ASC
            """,
            agent_id,
        )

    history = [{"role": r["role"], "content": json.loads(r["content"])} for r in rows]

    # Sanitize history: remove any assistant turn whose tool_use blocks are not
    # immediately followed by a user turn containing matching tool_result blocks.
    # This self-heals corrupted history from mid-run failures (rate limits, timeouts).
    def _sanitize(msgs):
        clean = []
        i = 0
        while i < len(msgs):
            msg = msgs[i]
            if msg["role"] == "assistant":
                tool_ids = {b["id"] for b in msg["content"] if b.get("type") == "tool_use"}
                if tool_ids:
                    # Check next message has matching tool_results
                    next_msg = msgs[i + 1] if i + 1 < len(msgs) else None
                    if next_msg and next_msg["role"] == "user":
                        result_ids = {b.get("tool_use_id") for b in next_msg["content"]
                                      if b.get("type") == "tool_result"}
                        if tool_ids <= result_ids:
                            clean.append(msg)
                            i += 1
                            continue
                    # Orphaned tool_use — drop this turn (and skip the orphaned result if present)
                    i += 1
                    if i < len(msgs) and msgs[i]["role"] == "user":
                        i += 1  # skip dangling tool_result turn too
                    continue
            clean.append(msg)
            i += 1
        return clean

    history = _sanitize(history)

    # Persist user message
    user_content = [{"type": "text", "text": user_message}]
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO agent_chats (agent_id, role, content) VALUES ($1, $2, $3)",
            agent_id, "user", json.dumps(user_content),
        )

    history.append({"role": "user", "content": user_content})
    mode = (body.get("mode") or "auto").strip()
    system_prompt = _build_system_prompt(agent, mode, match_message=user_message)
    # Per-agent model override (agents_registry.json's "model" field) takes priority over the
    # shared env var — copy-heavy agents (content-agent, copy-agent) are pinned to the most
    # capable model since copy quality matters more there than latency/cost; agents without an
    # explicit "model" fall back to the shared default, which stays the faster/cheaper tier.
    model = agent.get("model") or os.environ.get("AGENTS_CLAUDE_MODEL", "claude-sonnet-5")

    async def event_stream():
        try:
            client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
            messages = list(history)
            MAX_ITERATIONS = 25

            for _ in range(MAX_ITERATIONS):
                accumulated_text = ""
                assistant_content = []

                # Stream response from Claude
                with client.messages.stream(
                    model=model,
                    max_tokens=4096,
                    system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
                    tools=TOOLS,
                    messages=messages,
                ) as stream:
                    for event in stream:
                        etype = event.type
                        if etype == "content_block_start":
                            block = event.content_block
                            if block.type == "tool_use":
                                yield f"data: {json.dumps({'type': 'tool_start', 'tool_name': block.name, 'tool_use_id': block.id})}\n\n"
                        elif etype == "content_block_delta":
                            delta = event.delta
                            if hasattr(delta, "text"):
                                accumulated_text += delta.text
                                yield f"data: {json.dumps({'type': 'text_delta', 'text': delta.text})}\n\n"
                    final_message = stream.get_final_message()

                # Build content blocks for storage
                for block in final_message.content:
                    if block.type == "text":
                        assistant_content.append({"type": "text", "text": block.text})
                    elif block.type == "tool_use":
                        assistant_content.append({
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        })

                # Persist assistant turn
                async with pool.acquire() as conn:
                    await conn.execute(
                        "INSERT INTO agent_chats (agent_id, role, content) VALUES ($1, $2, $3)",
                        agent_id, "assistant", json.dumps(assistant_content),
                    )

                # Done — no tool calls
                if final_message.stop_reason != "tool_use":
                    async with pool.acquire() as conn:
                        await conn.execute(
                            """
                            DELETE FROM agent_chats
                            WHERE agent_id = $1
                              AND id NOT IN (
                                SELECT id FROM agent_chats
                                WHERE agent_id = $1
                                ORDER BY created_at DESC
                                LIMIT 100
                              )
                            """,
                            agent_id,
                        )
                        preview = accumulated_text[:200].strip()
                        if preview:
                            await conn.execute(
                                "INSERT INTO agent_messages (agent, message) VALUES ($1, $2)",
                                agent.get("name", agent_id), preview,
                            )
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    return

                # Execute tool calls
                messages.append({"role": "assistant", "content": assistant_content})
                tool_results = []

                for block in final_message.content:
                    if block.type != "tool_use":
                        continue
                    if block.name == "crm_list_followups":
                        result = await crm_list_followups(block.input.get("limit", 20))
                    elif block.name == "os_sms_outreach_stats":
                        result = await os_sms_outreach_stats()
                    elif block.name == "os_dialer_disposition_breakdown":
                        result = await os_dialer_disposition_breakdown()
                    elif block.name == "os_dialer_recent_notes":
                        result = await os_dialer_recent_notes(block.input.get("limit", 20))
                    else:
                        result = await asyncio.to_thread(
                            _execute_tool, agent, block.name, block.input
                        )
                    yield f"data: {json.dumps({'type': 'tool_result', 'tool_use_id': block.id, 'tool_name': block.name, 'result': result[:3000]})}\n\n"
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,  # full result for current-turn context
                    })

                # Persist tool results — truncate large results to prevent history bloat
                _STORE_LIMIT = 6000
                stored_results = [
                    {**tr, "content": tr["content"][:_STORE_LIMIT] if len(tr["content"]) > _STORE_LIMIT else tr["content"]}
                    for tr in tool_results
                ]
                async with pool.acquire() as conn:
                    await conn.execute(
                        "INSERT INTO agent_chats (agent_id, role, content) VALUES ($1, $2, $3)",
                        agent_id, "user", json.dumps(stored_results),
                    )
                messages.append({"role": "user", "content": tool_results})

            yield f"data: {json.dumps({'type': 'error', 'message': 'Max tool iterations reached'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
