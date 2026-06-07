"""
Settings router — full-repo Claude Code interface with bash execution.

POST   /settings/chat              SSE chat (Claude + file tools + run_bash)
GET    /settings/history           last 40 chat rows
DELETE /settings/history           clear history
POST   /settings/exec              direct command execution (SSE stream, no Claude)
GET    /settings/files             file tree (repo root)
GET    /settings/files/{path}      read file (500KB cap)
PUT    /settings/files/{path}      write file + GitHub push
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

router = APIRouter()

_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent.parent.resolve()
_GITHUB_REPO = os.environ.get("GITHUB_REPO", "dylangroenendijk-sys/digigrowth-brain")
_AGENT_ID = "settings-os"

BLOCKED_FILENAMES = {".env", "credentials.json", "settings.local.json"}
SKIP_DIRS = {"node_modules", "__pycache__", ".venv", "venv", ".mypy_cache",
             ".pytest_cache", ".git", ".claude"}


# ── GitHub API helpers ────────────────────────────────────────────────────────

def _gh_request(method: str, path: str, body: dict | None = None) -> dict:
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
    try:
        return _gh_request("GET", rel_path).get("sha")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def _github_push_file(file_abs: pathlib.Path, operation: str) -> str:
    token = os.environ.get("GIT_TOKEN", "")
    if not token:
        return "no GIT_TOKEN — saved locally only"
    try:
        rel = str(file_abs.relative_to(_REPO_ROOT))
    except ValueError:
        return "path outside repo — skipped"
    try:
        if operation == "delete":
            sha = _gh_get_sha(rel)
            if not sha:
                return "not on GitHub — nothing to delete"
            _gh_request("DELETE", rel, {"message": f"Settings: delete {rel}", "sha": sha})
            return "deleted on GitHub"
        content_b64 = base64.b64encode(file_abs.read_bytes()).decode()
        sha = _gh_get_sha(rel)
        payload = {"message": f"Settings: {operation} {rel}", "content": content_b64}
        if sha:
            payload["sha"] = sha
        _gh_request("PUT", rel, payload)
        return "pushed to GitHub"
    except Exception as e:
        return f"github error: {e}"


# ── Path sandbox ──────────────────────────────────────────────────────────────

def _safe_path(rel: str) -> pathlib.Path:
    target = (_REPO_ROOT / rel).resolve()
    try:
        target.relative_to(_REPO_ROOT)
    except ValueError:
        raise HTTPException(status_code=403, detail="Path traversal not allowed")
    if target.name in BLOCKED_FILENAMES:
        raise HTTPException(status_code=403, detail=f"Access to {target.name} is forbidden")
    return target


# ── File tree ─────────────────────────────────────────────────────────────────

def _build_tree(path: pathlib.Path, depth: int = 0) -> list:
    if depth > 6:
        return []
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
        rel = str(item.relative_to(_REPO_ROOT))
        if item.is_dir():
            entries.append({
                "name": item.name, "path": rel, "type": "dir",
                "children": _build_tree(item, depth + 1),
            })
        else:
            entries.append({
                "name": item.name, "path": rel, "type": "file",
                "size": item.stat().st_size,
            })
    return entries


# ── Bash execution ────────────────────────────────────────────────────────────

async def _run_bash(command: str, cwd: str = "") -> str:
    if cwd:
        work_dir = (_REPO_ROOT / cwd).resolve()
        try:
            work_dir.relative_to(_REPO_ROOT)
        except ValueError:
            return "Error: cwd must be within repo"
    else:
        work_dir = _REPO_ROOT
    try:
        proc = await asyncio.create_subprocess_shell(
            command, cwd=str(work_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
        output = stdout.decode(errors="replace")[:12000]
        suffix = f"\n[exit {proc.returncode}]" if proc.returncode else ""
        return output + suffix
    except asyncio.TimeoutError:
        proc.kill()
        return "Command timed out (60s limit)"
    except Exception as e:
        return f"Error running command: {e}"


# ── Sync tool executor (file ops) ─────────────────────────────────────────────

def _execute_file_tool(tool_name: str, tool_input: dict) -> str:
    try:
        if tool_name == "list_files":
            subdir = (tool_input.get("subdir") or "").strip()
            base = _safe_path(subdir) if subdir else _REPO_ROOT
            if not base.exists():
                return f"Error: '{subdir}' does not exist"
            lines = []
            for item in sorted(base.rglob("*")):
                if any(p.name in SKIP_DIRS for p in item.parents):
                    continue
                if any(p.name.startswith(".") and p.name not in (".env.example",)
                       for p in item.parents if p != _REPO_ROOT and p != item):
                    continue
                if item.name.startswith(".") and item.name not in (".env.example",):
                    continue
                rel = item.relative_to(_REPO_ROOT)
                indent = "  " * (len(rel.parts) - 1)
                icon = "/" if item.is_dir() else " "
                lines.append(f"{indent}{icon} {item.name}")
            return "\n".join(lines) if lines else "(empty)"

        elif tool_name == "read_file":
            path = tool_input.get("path", "")
            target = _safe_path(path)
            if not target.exists() or not target.is_file():
                return f"Error: '{path}' does not exist"
            if target.stat().st_size > 100_000:
                return f"Error: file too large ({target.stat().st_size} bytes)"
            return target.read_text(errors="replace")

        elif tool_name in ("write_file", "create_file"):
            path = tool_input.get("path", "")
            content = tool_input.get("content", "")
            target = _safe_path(path)
            if tool_name == "create_file" and target.exists():
                return f"Error: '{path}' already exists. Use write_file to overwrite."
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
            git_status = _github_push_file(target, tool_name)
            return f"OK: wrote {len(content)} chars to {path}\ngit: {git_status}"

        elif tool_name == "delete_file":
            path = tool_input.get("path", "")
            target = _safe_path(path)
            if not target.exists():
                return f"Error: '{path}' does not exist"
            if target.is_dir():
                return "Error: cannot delete directories"
            target.unlink()
            git_status = _github_push_file(target, "delete")
            return f"OK: deleted {path}\ngit: {git_status}"

        else:
            return f"Error: unknown tool '{tool_name}'"

    except HTTPException as e:
        return f"Error: {e.detail}"
    except Exception as e:
        return f"Error: {e}"


# ── Claude tools definition ───────────────────────────────────────────────────

TOOLS = [
    {
        "name": "read_file",
        "description": "Read the full contents of a file in the repo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path relative to repo root, e.g. 'dashboard/backend/main.py'"}
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write or overwrite a file. Creates parent directories if needed.",
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
        "description": "List files in the repo or a subdirectory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "subdir": {"type": "string", "description": "Optional subdirectory. Leave empty for repo root.", "default": ""}
            },
        },
    },
    {
        "name": "create_file",
        "description": "Create a new file. Returns error if it already exists — use write_file to overwrite.",
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
        "description": "Permanently delete a file. Cannot be undone.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "run_bash",
        "description": "Execute a shell command in the repo. Use for git, npm, python, pip, etc. Output capped at 12000 chars. 60s timeout.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to run"},
                "cwd": {
                    "type": "string",
                    "description": "Subdirectory to run in (relative to repo root). Default: repo root.",
                    "default": "",
                },
            },
            "required": ["command"],
        },
    },
]


# ── System prompt ─────────────────────────────────────────────────────────────

def _build_system_prompt() -> str:
    parts = [
        "You are Claude Code embedded in DigiGrowth OS — a full-stack coding assistant "
        "with access to the entire platform codebase.\n\n"
        "Stack: React + Vite (dashboard/frontend/), FastAPI + asyncpg (dashboard/backend/), "
        "PostgreSQL, Railway Docker deployment.\n\n"
        "You have tools to read, write, create, and delete any file in the repo, and you can "
        "run shell commands with run_bash.\n\n"
        "Rules:\n"
        "- NEVER read, write, or reference .env, credentials.json, or settings.local.json\n"
        "- Read files before editing them — do targeted edits, not full rewrites\n"
        "- Warn before deleting files or running destructive commands (rm -rf, git reset --hard, etc.)\n"
        "- On Railway, git push won't work (no .git/) — file writes are persisted via GitHub REST API automatically\n"
        "- Be concise — the user is the developer who built this system\n"
    ]

    claude_md = _REPO_ROOT / "CLAUDE.md"
    if claude_md.exists():
        try:
            content = claude_md.read_text(errors="replace")[:4000]
            parts.append(f"\n---\n## CLAUDE.md\n\n{content}")
        except Exception:
            pass

    return "".join(parts)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/settings/files")
async def list_files_root():
    return {"files": _build_tree(_REPO_ROOT)}


@router.get("/settings/files/{path:path}")
async def read_file_endpoint(path: str):
    target = _safe_path(path)
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    if target.stat().st_size > 500_000:
        raise HTTPException(status_code=413, detail="File too large (>500KB)")
    return {"path": path, "content": target.read_text(errors="replace"), "size": target.stat().st_size}


@router.put("/settings/files/{path:path}")
async def write_file_endpoint(path: str, payload: dict):
    target = _safe_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(payload.get("content", ""))
    git_status = await asyncio.to_thread(_github_push_file, target, "write_file")
    return {"ok": True, "git": git_status}


@router.get("/settings/history")
async def get_history():
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
            _AGENT_ID,
        )
    return [
        {"id": r["id"], "role": r["role"],
         "content": json.loads(r["content"]), "created_at": str(r["created_at"])}
        for r in rows
    ]


@router.delete("/settings/history")
async def clear_history():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM agent_chats WHERE agent_id = $1", _AGENT_ID)
    return {"ok": True}


@router.post("/settings/exec")
async def exec_command(body: dict):
    """Direct terminal execution — streams stdout+stderr as SSE, no Claude."""
    command = (body.get("command") or "").strip()
    cwd = (body.get("cwd") or "").strip()
    if not command:
        raise HTTPException(status_code=400, detail="command required")

    if cwd:
        work_dir = (_REPO_ROOT / cwd).resolve()
        try:
            work_dir.relative_to(_REPO_ROOT)
        except ValueError:
            raise HTTPException(status_code=403, detail="cwd must be within repo")
    else:
        work_dir = _REPO_ROOT

    async def _stream():
        try:
            proc = await asyncio.create_subprocess_shell(
                command, cwd=str(work_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            async for line in proc.stdout:
                yield f"data: {json.dumps({'type': 'output', 'text': line.decode(errors='replace')})}\n\n"
            await proc.wait()
            yield f"data: {json.dumps({'type': 'done', 'code': proc.returncode})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/settings/chat")
async def chat(request: Request):
    body = await request.json()
    user_message = (body.get("message") or "").strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="message required")

    pool = await get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT role, content FROM (
                SELECT role, content, created_at
                FROM agent_chats WHERE agent_id = $1
                ORDER BY created_at DESC LIMIT 40
            ) sub ORDER BY sub.created_at ASC
            """,
            _AGENT_ID,
        )

    history = [{"role": r["role"], "content": json.loads(r["content"])} for r in rows]

    user_content = [{"type": "text", "text": user_message}]
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO agent_chats (agent_id, role, content) VALUES ($1, $2, $3)",
            _AGENT_ID, "user", json.dumps(user_content),
        )

    history.append({"role": "user", "content": user_content})
    system_prompt = _build_system_prompt()
    model = os.environ.get("AGENTS_CLAUDE_MODEL", "claude-sonnet-4-6")

    async def event_stream():
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        messages = list(history)
        MAX_ITERATIONS = 10

        for _ in range(MAX_ITERATIONS):
            accumulated_text = ""
            assistant_content = []

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

            for block in final_message.content:
                if block.type == "text":
                    assistant_content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    assistant_content.append({
                        "type": "tool_use", "id": block.id,
                        "name": block.name, "input": block.input,
                    })

            async with pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO agent_chats (agent_id, role, content) VALUES ($1, $2, $3)",
                    _AGENT_ID, "assistant", json.dumps(assistant_content),
                )

            if final_message.stop_reason != "tool_use":
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                return

            messages.append({"role": "assistant", "content": assistant_content})
            tool_results = []

            for block in final_message.content:
                if block.type != "tool_use":
                    continue

                if block.name == "run_bash":
                    result = await _run_bash(
                        block.input.get("command", ""),
                        block.input.get("cwd", ""),
                    )
                else:
                    result = await asyncio.to_thread(
                        _execute_file_tool, block.name, block.input
                    )

                yield f"data: {json.dumps({'type': 'tool_result', 'tool_use_id': block.id, 'tool_name': block.name, 'result': result[:3000]})}\n\n"

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

            async with pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO agent_chats (agent_id, role, content) VALUES ($1, $2, $3)",
                    _AGENT_ID, "user", json.dumps(tool_results),
                )

            messages.append({"role": "user", "content": tool_results})

        yield f"data: {json.dumps({'type': 'error', 'message': 'Max tool iterations reached'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
