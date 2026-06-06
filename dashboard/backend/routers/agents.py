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
import json
import os
import pathlib
import subprocess

import anthropic
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from db import get_pool

router = APIRouter()

_REGISTRY_PATH = pathlib.Path(__file__).parent.parent / "agents_registry.json"
_REPO_ROOT = _REGISTRY_PATH.parent.parent.parent  # dashboard/backend/ → dashboard/ → repo root


# ── Git helpers ───────────────────────────────────────────────────────────────

def _git_commit_push(file_abs: pathlib.Path, agent_name: str, operation: str) -> str:
    """Stage, commit, and push a single file change. Returns a short status string."""
    try:
        rel = str(file_abs.relative_to(_REPO_ROOT))
    except ValueError:
        rel = str(file_abs)

    try:
        r = subprocess.run(["git", "add", rel], cwd=_REPO_ROOT, capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            return f"git add failed: {r.stderr.strip()}"

        # Nothing staged → nothing to commit
        diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=_REPO_ROOT, timeout=5)
        if diff.returncode == 0:
            return "no changes to commit"

        msg = f"Agent edit [{agent_name}]: {operation} {rel}"
        r = subprocess.run(["git", "commit", "-m", msg], cwd=_REPO_ROOT, capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            return f"git commit failed: {r.stderr.strip()}"

        r = subprocess.run(["git", "push"], cwd=_REPO_ROOT, capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return f"git push failed: {r.stderr.strip()}"

        return "committed and pushed"

    except subprocess.TimeoutExpired:
        return "git timed out"
    except Exception as e:
        return f"git error: {e}"

BLOCKED_FILENAMES = {".env", "credentials.json", "settings.local.json"}

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
]


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
            lines = []
            for item in sorted(base.rglob("*")):
                # Skip deeply hidden dirs (e.g. .git)
                if any(p.name.startswith(".") and p.name not in (".env.example",)
                       for p in item.parents if p != root and p != item):
                    continue
                if item.name.startswith(".") and item.name not in (".env.example",):
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
            git_status = _git_commit_push(target, agent["name"], tool_name)
            return f"OK: wrote {len(content)} chars to {path}\ngit: {git_status}"

        elif tool_name == "delete_file":
            path = tool_input.get("path", "")
            target = _safe_path(root, path)
            if not target.exists():
                return f"Error: '{path}' does not exist"
            if target.is_dir():
                return "Error: cannot delete directories via this tool"
            target.unlink()
            git_status = _git_commit_push(target, agent["name"], "delete_file")
            return f"OK: deleted {path}\ngit: {git_status}"

        else:
            return f"Error: unknown tool '{tool_name}'"

    except HTTPException as e:
        return f"Error: {e.detail}"
    except Exception as e:
        return f"Error: {e}"


# ── System prompt builder ──────────────────────────────────────────────────────

def _build_system_prompt(agent: dict) -> str:
    root: pathlib.Path = agent["abs_root"]
    name = agent["name"]
    description = agent.get("description", "")

    parts = [
        f"You are a code and configuration assistant for the **{name}** agent in Dylan's DigiGrowth OS. "
        f"Description: {description}\n\n"
        "You have tools to read, write, create, and delete files in this agent's directory. "
        "Use them freely — read files before editing them, and explain your changes.\n\n"
        "SECURITY: NEVER read, write, or reference .env files, credentials.json, or settings.local.json. "
        "These contain secrets and are blocked at the API level.\n\n"
        "When making code changes, follow the existing patterns in the files you read first. "
        "Be concise — the user is technical."
    ]

    for candidate in ["CLAUDE.md", "prompt.txt", "role.txt"]:
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

    # Commit the new agent scaffold + updated registry
    def _commit_new_agent():
        try:
            subprocess.run(["git", "add", str(agent_root), str(_REGISTRY_PATH)],
                           cwd=_REPO_ROOT, capture_output=True, text=True, timeout=15)
            subprocess.run(["git", "commit", "-m", f"New agent scaffold: {name}"],
                           cwd=_REPO_ROOT, capture_output=True, text=True, timeout=15)
            subprocess.run(["git", "push"],
                           cwd=_REPO_ROOT, capture_output=True, text=True, timeout=30)
        except Exception:
            pass

    await asyncio.to_thread(_commit_new_agent)

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
    git_status = await asyncio.to_thread(_git_commit_push, target, agent["name"], "write_file")
    return {"ok": True, "git": git_status}


@router.post("/agents/{agent_id}/files/{path:path}")
async def create_file_endpoint(agent_id: str, path: str, payload: dict):
    agent = _get_agent(agent_id)
    target = _safe_path(agent["abs_root"], path)
    if target.exists():
        raise HTTPException(status_code=409, detail="File already exists")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(payload.get("content", ""))
    git_status = await asyncio.to_thread(_git_commit_push, target, agent["name"], "create_file")
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
    git_status = await asyncio.to_thread(_git_commit_push, target, agent["name"], "delete_file")
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

    # Persist user message
    user_content = [{"type": "text", "text": user_message}]
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO agent_chats (agent_id, role, content) VALUES ($1, $2, $3)",
            agent_id, "user", json.dumps(user_content),
        )

    history.append({"role": "user", "content": user_content})
    system_prompt = _build_system_prompt(agent)
    model = os.environ.get("AGENTS_CLAUDE_MODEL", "claude-sonnet-4-6")

    async def event_stream():
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        messages = list(history)
        MAX_ITERATIONS = 10

        for _ in range(MAX_ITERATIONS):
            accumulated_text = ""
            assistant_content = []  # full blocks for this turn

            # Stream response from Claude
            with client.messages.stream(
                model=model,
                max_tokens=4096,
                system=system_prompt,
                tools=TOOLS,
                messages=messages,
            ) as stream:
                current_tool_id = None
                current_tool_name = None

                for event in stream:
                    etype = event.type

                    if etype == "content_block_start":
                        block = event.content_block
                        if block.type == "tool_use":
                            current_tool_id = block.id
                            current_tool_name = block.name
                            yield f"data: {json.dumps({'type': 'tool_start', 'tool_name': block.name, 'tool_use_id': block.id})}\n\n"

                    elif etype == "content_block_delta":
                        delta = event.delta
                        if hasattr(delta, "text"):
                            accumulated_text += delta.text
                            yield f"data: {json.dumps({'type': 'text_delta', 'text': delta.text})}\n\n"

                final_message = stream.get_final_message()

            # Build full content blocks list for storage
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

            # Persist tool results as user turn (Anthropic requires alternating roles)
            async with pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO agent_chats (agent_id, role, content) VALUES ($1, $2, $3)",
                    agent_id, "user", json.dumps(tool_results),
                )

            messages.append({"role": "user", "content": tool_results})
            # Loop: Claude will now respond to the tool results

        yield f"data: {json.dumps({'type': 'error', 'message': 'Max tool iterations reached'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
