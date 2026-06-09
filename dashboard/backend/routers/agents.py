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
from fastapi.responses import StreamingResponse

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
        "description": "List recently modified Google Drive files.",
        "input_schema": {
            "type": "object",
            "properties": {
                "max_results": {"type": "integer", "default": 10},
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
            "All values should be cumulative all-time totals (not daily increments) unless the sheet "
            "clearly tracks only a single day."
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
                # Outreach activity (use the most recent period total you can find — weekly or all available)
                "calls_made":         {"type": "integer", "description": "Total calls dialed in the tracked period"},
                "contacts_reached":   {"type": "integer", "description": "Total calls answered / contacts reached"},
                "appointments_booked":{"type": "integer", "description": "Total appointments / intro sessions booked"},
                "sms_sent":           {"type": "integer", "description": "Total SMS messages sent"},
                "source_note":        {"type": "string",  "description": "Brief note on which sheet(s) this data came from and what period it covers"},
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
                "shows":               "shows",
                "closes":              "closes",
                "total_revenue":       "total_revenue",
                "avg_deal_size":       "avg_deal_size",
                "discovery_calls":     "discovery_calls",
                "strategy_sessions":   "strategy_sessions",
                "calls_made":          "sheet_calls_made",
                "contacts_reached":    "sheet_contacts_reached",
                "appointments_booked": "sheet_appointments_booked",
                "sms_sent":            "sheet_sms_sent",
            }
            updated = []
            for key, stat_key in FIELD_MAP.items():
                if key in tool_input and tool_input[key] is not None:
                    current[stat_key] = tool_input[key]
                    updated.append(f"{stat_key}={tool_input[key]}")

            # Auto-calculate avg_deal_size if not provided
            closes = current.get("closes", 0)
            revenue = current.get("total_revenue", 0)
            if closes and revenue and "avg_deal_size" not in tool_input:
                current["avg_deal_size"] = round(revenue / closes)

            from datetime import datetime as _dt
            current["last_sheet_sync"] = _dt.now().isoformat()
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

def _build_system_prompt(agent: dict, mode: str = "auto") -> str:
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
                content = p.read_text(errors="replace")[:4000]
                parts.append(f"\n---\n## {candidate}\n\n{content}")
            except Exception:
                pass

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
            if item.name.startswith(".") and item.name not in (".env.example",):
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
                ORDER BY created_at DESC LIMIT 40
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
                ORDER BY created_at DESC LIMIT 40
            ) sub ORDER BY sub.created_at ASC
            """,
            agent_id,
        )

    history = [{"role": r["role"], "content": json.loads(r["content"])} for r in rows]

    # If the last assistant turn has tool_use blocks with no following tool_result
    # (happens when stop is hit mid-execution), drop it to avoid API rejection.
    if (len(history) >= 1
            and history[-1]["role"] == "assistant"
            and any(b.get("type") == "tool_use" for b in history[-1]["content"])):
        history = history[:-1]

    # Persist user message
    user_content = [{"type": "text", "text": user_message}]
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO agent_chats (agent_id, role, content) VALUES ($1, $2, $3)",
            agent_id, "user", json.dumps(user_content),
        )

    history.append({"role": "user", "content": user_content})
    mode = (body.get("mode") or "auto").strip()
    system_prompt = _build_system_prompt(agent, mode)
    model = os.environ.get("AGENTS_CLAUDE_MODEL", "claude-sonnet-4-6")

    async def event_stream():
        try:
            client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
            messages = list(history)
            MAX_ITERATIONS = 10

            for _ in range(MAX_ITERATIONS):
                accumulated_text = ""
                assistant_content = []

                # Stream response from Claude
                with client.messages.stream(
                    model=model,
                    max_tokens=4096,
                    system=system_prompt,
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
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    return

                # Execute tool calls
                messages.append({"role": "assistant", "content": assistant_content})
                tool_results = []

                for block in final_message.content:
                    if block.type != "tool_use":
                        continue
                    result = await asyncio.to_thread(
                        _execute_tool, agent, block.name, block.input
                    )
                    yield f"data: {json.dumps({'type': 'tool_result', 'tool_use_id': block.id, 'tool_name': block.name, 'result': result[:3000]})}\n\n"
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

                # Persist tool results as user turn
                async with pool.acquire() as conn:
                    await conn.execute(
                        "INSERT INTO agent_chats (agent_id, role, content) VALUES ($1, $2, $3)",
                        agent_id, "user", json.dumps(tool_results),
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
