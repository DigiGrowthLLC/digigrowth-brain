"""
Weekly Repo Cleanup Agent

Runs every Sunday at 8pm ET (triggered by dashboard/backend/main.py's scheduler,
which invokes this script as a subprocess — see _run_weekly_cleanup()).

Scans the whole repo for dead code, redundant/conflicting instructions, and
stale reports. Auto-fixes anything it can verify is safe without changing
behavior; anything needing human judgment is written to the weekly report's
"Needs Approval" section instead, which the EA's daily-briefing skill surfaces
in the following Monday's brief (Step 4.6).

Two phases:
  1. Detection (this file, pure Python/grep — zero LLM cost): builds a bounded
     candidate list of unused imports, zero-caller functions, broken doc
     references, duplicated helpers, and recently-changed files.
  2. Judgment + fix (one bounded Claude session, Opus): reviews the candidate
     list with a narrow tool set (read/write/delete/grep/verify — no raw Bash),
     applies only high-confidence safe fixes, and writes the rest to the
     "Needs Approval" section.

Also handles report retention (archive reports/ older than 7 days into
archives/reports-YYYY-MM/) and flags (never touches) stale projects/ entries.

Usage:
  python run.py              # real run — makes changes, pushes to GitHub
  python run.py --dry-run    # logs everything it would do, changes nothing
"""

import argparse
import ast
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import anthropic

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "shared"))
from github_sync import push_file, delete_file  # noqa: E402

# ── Paths ───────────────────────────────────────────────────────────────────

REPO_ROOT       = pathlib.Path(__file__).parent.parent.resolve()
EA_REPORTS_DIR  = REPO_ROOT / "executive-assistant" / "reports"
EA_ARCHIVES_DIR = REPO_ROOT / "executive-assistant" / "archives"
EA_PROJECTS_DIR = REPO_ROOT / "executive-assistant" / "projects"
STATE_FILE      = REPO_ROOT / "weekly-cleanup" / "last_run.json"

# ── Config ──────────────────────────────────────────────────────────────────

MODEL              = "claude-opus-4-8"
MAX_TOOL_CALLS     = 40
MAX_FILES_TOUCHED  = 15
RETENTION_DAYS     = 7
STALE_PROJECT_DAYS = 60
MAX_CANDIDATES_PER_CATEGORY = 30

BLOCKED_FILENAMES = {".env", "credentials.json", "settings.local.json"}
SKIP_DIR_NAMES    = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", "worktrees"}

CODE_EXTENSIONS = {".py", ".jsx", ".js"}
DOC_EXTENSIONS  = {".md"}


def _iter_files(exts: set) -> list:
    """All repo files with the given extensions, skipping blocked/junk dirs."""
    out = []
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in exts:
            continue
        if path.name in BLOCKED_FILENAMES:
            continue
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        out.append(path)
    return out


def _rel(path: pathlib.Path) -> str:
    return str(path.relative_to(REPO_ROOT))


# ── Phase 1: Detection (pure Python, zero LLM cost) ──────────────────────────

def find_unused_imports() -> list:
    """For each Python import, check whether the imported name is referenced
    anywhere else in the same file. AST-based, not a runtime guarantee — just
    a candidate signal for the judgment phase to verify before acting."""
    candidates = []
    for path in _iter_files({".py"}):
        try:
            source = path.read_text(errors="replace")
            tree = ast.parse(source, filename=str(path))
        except (SyntaxError, UnicodeDecodeError):
            continue

        imported_names = []  # (name, lineno)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name.split(".")[0]
                    imported_names.append((name, node.lineno))
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    name = alias.asname or alias.name
                    imported_names.append((name, node.lineno))

        if not imported_names:
            continue

        lines = source.splitlines()
        for name, lineno in imported_names:
            # Count occurrences of the bare name outside its own import line
            pattern = re.compile(r"\b" + re.escape(name) + r"\b")
            uses = sum(
                1 for i, line in enumerate(lines, start=1)
                if i != lineno and pattern.search(line)
            )
            if uses == 0:
                candidates.append({
                    "category": "unused_import",
                    "file": _rel(path),
                    "line": lineno,
                    "name": name,
                })
        if len(candidates) >= MAX_CANDIDATES_PER_CATEGORY:
            break
    return candidates[:MAX_CANDIDATES_PER_CATEGORY]


def find_zero_caller_functions() -> list:
    """Top-level Python functions and FastAPI routes with no reference anywhere
    else in the repo. Candidate signal only — the judgment phase must verify
    with its own grep before touching anything (dunder methods, dynamically
    dispatched handlers, and frontend-called endpoints can look zero-caller
    to a naive text search)."""
    candidates = []
    py_files = _iter_files({".py"})

    # Build a corpus once instead of re-scanning per-candidate
    corpus = {}
    for path in py_files:
        try:
            corpus[path] = path.read_text(errors="replace")
        except UnicodeDecodeError:
            continue

    # Any decorator that registers a function as a framework entrypoint (FastAPI's
    # @router.get/post/... — under any router variable name, e.g. webhook_router —
    # or Flask's @app.route/get/post/...) — these are "used" by the framework
    # even though nothing in the codebase calls them by name.
    route_decorator = re.compile(r'@\w*(?:router|app)\.(?:get|post|put|patch|delete|route)\(')
    def_line = re.compile(r'^(?:async )?def (\w+)\(', re.MULTILINE)

    for path, source in corpus.items():
        lines = source.splitlines()
        names = set()
        for m in def_line.finditer(source):
            name = m.group(1)
            if name.startswith("_"):
                continue  # private helpers are usually intra-file; too noisy for this cheap pass
            lineno = source.count("\n", 0, m.start()) + 1
            preceding = "\n".join(lines[max(0, lineno - 4):lineno - 1])
            if route_decorator.search(preceding):
                continue  # registered as a framework route — not a candidate
            names.add(name)

        for name in names:
            pattern = re.compile(r"\b" + re.escape(name) + r"\b")
            occurrences = 0
            for other_path, other_source in corpus.items():
                occurrences += len(pattern.findall(other_source))
                if occurrences > 1:
                    break
            if occurrences <= 1:  # only its own definition
                candidates.append({
                    "category": "zero_caller_function",
                    "file": _rel(path),
                    "name": name,
                })
        if len(candidates) >= MAX_CANDIDATES_PER_CATEGORY:
            break
    return candidates[:MAX_CANDIDATES_PER_CATEGORY]


def find_broken_doc_references() -> list:
    """@file includes and backtick-quoted file paths in docs that don't exist
    anywhere in the repo (checked as a path suffix, not just relative to the
    doc's own directory, since these often reference a different agent's
    directory by name)."""
    candidates = []
    # Require a "/" so this doesn't match emails like someone@gmail.com
    at_include = re.compile(r'@([\w\-]+(?:/[\w./\-]+)+\.\w+)')
    backtick_path = re.compile(r'`([\w\-]+(?:/[\w./\-]+)+\.\w+)`')
    placeholder = re.compile(r'YYYY|MM-DD|<[\w\-]+>|\{\{')

    all_paths_by_suffix = None  # lazily built, cached across calls in this run

    def _exists_anywhere(ref: str) -> bool:
        nonlocal all_paths_by_suffix
        if all_paths_by_suffix is None:
            all_paths_by_suffix = [p for p in REPO_ROOT.rglob("*")
                                    if p.is_file() and not any(part in SKIP_DIR_NAMES for part in p.relative_to(REPO_ROOT).parts)]
        ref_parts = pathlib.PurePosixPath(ref).parts
        return any(p.parts[-len(ref_parts):] == ref_parts for p in
                   (pp.relative_to(REPO_ROOT) for pp in all_paths_by_suffix))

    for path in _iter_files(DOC_EXTENSIONS):
        try:
            text = path.read_text(errors="replace")
        except UnicodeDecodeError:
            continue

        refs = set(at_include.findall(text)) | set(backtick_path.findall(text))
        for ref in refs:
            if placeholder.search(ref):
                continue  # naming-convention example, not a real reference
            candidate_paths = [path.parent / ref, REPO_ROOT / ref]
            if any(p.exists() for p in candidate_paths):
                continue
            if _exists_anywhere(ref):
                continue
            candidates.append({
                "category": "broken_doc_reference",
                "file": _rel(path),
                "reference": ref,
            })
        if len(candidates) >= MAX_CANDIDATES_PER_CATEGORY:
            break
    return candidates[:MAX_CANDIDATES_PER_CATEGORY]


def find_duplicate_functions() -> list:
    """Python function bodies (whitespace-normalized) that appear byte-identical
    in 2+ distinct files. Only flags exact duplicates — the judgment phase
    decides whether/how to consolidate."""
    bodies = {}  # hash -> list of (file, funcname)
    for path in _iter_files({".py"}):
        try:
            source = path.read_text(errors="replace")
            tree = ast.parse(source, filename=str(path))
        except (SyntaxError, UnicodeDecodeError):
            continue

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            try:
                segment = ast.get_source_segment(source, node) or ""
            except Exception:
                continue
            # Normalize: strip the def line (names/args may legitimately differ)
            body_lines = segment.splitlines()[1:]
            normalized = "\n".join(line.strip() for line in body_lines if line.strip())
            if len(normalized) < 80:
                continue  # too small to be a meaningful duplicate signal
            digest = hashlib.sha256(normalized.encode()).hexdigest()
            bodies.setdefault(digest, []).append((_rel(path), node.name))

    candidates = []
    for digest, locations in bodies.items():
        distinct_files = {loc[0] for loc in locations}
        if len(distinct_files) >= 2:
            candidates.append({
                "category": "duplicate_function",
                "locations": [f"{f}:{n}" for f, n in locations],
            })
    return candidates[:MAX_CANDIDATES_PER_CATEGORY]


def recent_git_changes(since_sha: str = None) -> list:
    """Files changed since the last run (or last 7 days if no prior run)."""
    try:
        if since_sha:
            result = subprocess.run(
                ["git", "diff", "--name-only", since_sha, "HEAD"],
                cwd=REPO_ROOT, capture_output=True, text=True, timeout=15,
            )
        else:
            result = subprocess.run(
                ["git", "log", "--since=7 days ago", "--name-only", "--pretty=format:"],
                cwd=REPO_ROOT, capture_output=True, text=True, timeout=15,
            )
        if result.returncode != 0:
            return []
        return sorted({line.strip() for line in result.stdout.splitlines() if line.strip()})
    except Exception:
        return []


def run_detection(since_sha: str = None) -> dict:
    return {
        "unused_imports":        find_unused_imports(),
        "zero_caller_functions": find_zero_caller_functions(),
        "broken_doc_references": find_broken_doc_references(),
        "duplicate_functions":   find_duplicate_functions(),
        "recently_changed":      recent_git_changes(since_sha),
    }


# ── Phase 3: Retention (pure Python, zero LLM cost) ──────────────────────────

_DATE_IN_NAME = re.compile(r"(\d{4}-\d{2}-\d{2})")


def archive_old_reports(dry_run: bool) -> list:
    """Move reports/ files older than RETENTION_DAYS into archives/reports-YYYY-MM/.
    Returns a list of human-readable log lines for the weekly report."""
    if not EA_REPORTS_DIR.exists():
        return []

    cutoff = datetime.now(timezone.utc).date() - timedelta(days=RETENTION_DAYS)
    log = []

    for path in sorted(EA_REPORTS_DIR.iterdir()):
        if not path.is_file():
            continue
        m = _DATE_IN_NAME.search(path.name)
        if not m:
            continue
        try:
            file_date = datetime.strptime(m.group(1), "%Y-%m-%d").date()
        except ValueError:
            continue
        if file_date >= cutoff:
            continue

        archive_subdir = EA_ARCHIVES_DIR / f"reports-{file_date.strftime('%Y-%m')}"
        dest = archive_subdir / path.name
        rel_src = _rel(path)
        rel_dest = _rel(dest)

        if dry_run:
            log.append(f"[dry-run] would archive {rel_src} -> {rel_dest}")
            continue

        archive_subdir.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(path.read_bytes())
        push_status = push_file(dest, message=f"Archive: {path.name}")
        path.unlink()
        delete_status = delete_file(path, message=f"Archive: remove {path.name} (moved to archives/)")
        log.append(f"Archived {rel_src} -> {rel_dest} (write: {push_status}, delete: {delete_status})")

    return log


def flag_stale_projects() -> list:
    """Never touches projects/ — only reports entries with no git activity in
    STALE_PROJECT_DAYS for human review."""
    if not EA_PROJECTS_DIR.exists():
        return []

    flagged = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=STALE_PROJECT_DAYS)
    for entry in sorted(EA_PROJECTS_DIR.iterdir()):
        if not entry.is_dir():
            continue
        try:
            result = subprocess.run(
                ["git", "log", "-1", "--format=%ct", "--", _rel(entry)],
                cwd=REPO_ROOT, capture_output=True, text=True, timeout=10,
            )
            ts = result.stdout.strip()
            if not ts:
                continue
            last_commit = datetime.fromtimestamp(int(ts), tz=timezone.utc)
            if last_commit < cutoff:
                days = (datetime.now(timezone.utc) - last_commit).days
                flagged.append(f"{entry.name} — no activity in {days} days (last: {last_commit.date()})")
        except Exception:
            continue
    return flagged


# ── Phase 2: Judgment + fix (one bounded Claude session) ─────────────────────

TOOLS = [
    {
        "name": "read_file",
        "description": "Read the full contents of a file anywhere in the repo.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Repo-relative path"}},
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Overwrite a file anywhere in the repo. Use only for verified, safe, behavior-neutral fixes.",
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
        "description": "Permanently delete a single file (not directories). Use only for confirmed dead files.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "list_files",
        "description": "List files under a repo-relative subdirectory (or the repo root if omitted).",
        "input_schema": {
            "type": "object",
            "properties": {"subdir": {"type": "string", "default": ""}},
        },
    },
    {
        "name": "grep",
        "description": "Search file contents for a regex pattern across the repo (or a glob-limited subset).",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex pattern"},
                "glob": {"type": "string", "description": "Optional glob to limit the search, e.g. '**/*.py'", "default": "**/*"},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "run_check",
        "description": (
            "Run a verification command. ONLY these exact command forms are allowed: "
            "'py_compile <path>' (validates a Python file compiles), "
            "'npm_build' (runs the frontend build), "
            "'json_check <path>' (validates JSON syntax). Anything else is rejected."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
]

SYSTEM_PROMPT = """You are the Weekly Repo Cleanup agent for DigiGrowth OS, a solo AI client \
acquisition agency's internal platform. You run once a week, unsupervised, against the live \
production repo. Your job is to make the repo more organized, efficient, and secure WITHOUT \
changing how anything actually works.

You've been given a candidate list from a cheap static scan (unused imports, zero-caller \
functions, broken doc references, duplicated helpers, recently-changed files). These are \
SIGNALS, not conclusions — the static scan has false positives. Verify every candidate \
yourself with `grep`/`read_file` before touching anything.

## Auto-fix directly (no approval needed)
- Dead code you have personally verified has zero callers anywhere in the repo (grep it yourself first)
- Documentation that references a file/path that provably does not exist
- Byte-identical duplicated helper logic — consolidate to one, update callers
- Unused imports and config keys with zero reads anywhere
- Stale docs that directly contradict current, verifiable code or config

## Needs approval — do NOT touch, just describe in your final report
- Anything that could change runtime behavior, even slightly
- Business or content judgment calls (e.g. two conflicting descriptions where you can't be \
certain which is correct)
- Anything touching secrets, auth, payment/financial logic, or external API credentials
- Deleting a file or feature whose necessity you cannot prove is zero
- Database schema changes
- Anything where your confidence is not very high

## Absolute rules
- NEVER read, write, or reference .env, credentials.json, or settings.local.json — these are \
blocked at the tool level anyway, but never even try.
- NEVER touch anything under .git/, node_modules/, or other build/dependency directories.
- After every fix, verify it with `run_check` (py_compile the file you changed, or npm_build \
if you touched frontend code). If verification fails, immediately revert your change by \
rewriting the file back to its original content, and describe it as skipped in your report \
instead of a fix — never leave the repo in a broken state.
- You have a hard budget: touch at most 15 files this run. If the candidate list is larger, \
handle the highest-confidence items first and note in your report that the rest are deferred \
to next week.
- Do not repeat information already covered by a previous fix in your candidate list — dedupe \
your own reasoning.

## When you are done
Respond with plain text only (no further tool calls) using EXACTLY this structure:

## Auto-Fixed
- <file>: <one-line description of what changed and why it's safe>
(or a single line: "Nothing auto-fixed this week." if there was nothing to do)

## Needs Approval
- <file>: <what you found> — <why it needs a human decision, and what you'd recommend>
(or a single line: "Nothing pending." if nothing needs approval)

Do not include any other sections, preamble, or sign-off in this final message — it is parsed \
programmatically and inserted directly into next Monday's daily briefing.
"""


def _safe_path(rel: str) -> pathlib.Path:
    target = (REPO_ROOT / rel).resolve()
    target.relative_to(REPO_ROOT)  # raises ValueError on traversal — caught by caller
    if target.name in BLOCKED_FILENAMES:
        raise PermissionError(f"Access to {target.name} is forbidden")
    return target


def _execute_tool(tool_name: str, tool_input: dict, dry_run: bool, files_touched: set) -> str:
    try:
        if tool_name == "read_file":
            target = _safe_path(tool_input.get("path", ""))
            if not target.exists() or not target.is_file():
                return f"Error: '{tool_input.get('path')}' does not exist"
            return target.read_text(errors="replace")[:50_000]

        elif tool_name == "list_files":
            subdir = (tool_input.get("subdir") or "").strip()
            base = _safe_path(subdir) if subdir else REPO_ROOT
            if not base.exists():
                return f"Error: '{subdir}' does not exist"
            lines = []
            for item in sorted(base.rglob("*")):
                if any(part in SKIP_DIR_NAMES for part in item.relative_to(base).parts):
                    continue
                if item.name in BLOCKED_FILENAMES:
                    continue
                lines.append(str(item.relative_to(REPO_ROOT)))
            return "\n".join(lines[:500]) if lines else "(empty)"

        elif tool_name == "grep":
            pattern = tool_input.get("pattern", "")
            glob = tool_input.get("glob") or "**/*"
            try:
                regex = re.compile(pattern)
            except re.error as e:
                return f"Error: invalid regex — {e}"
            matches = []
            for path in REPO_ROOT.glob(glob):
                if not path.is_file() or path.name in BLOCKED_FILENAMES:
                    continue
                if any(part in SKIP_DIR_NAMES for part in path.relative_to(REPO_ROOT).parts):
                    continue
                try:
                    for i, line in enumerate(path.read_text(errors="replace").splitlines(), start=1):
                        if regex.search(line):
                            matches.append(f"{path.relative_to(REPO_ROOT)}:{i}: {line.strip()[:200]}")
                except Exception:
                    continue
                if len(matches) >= 200:
                    break
            return "\n".join(matches) if matches else "No matches"

        elif tool_name == "write_file":
            path = tool_input.get("path", "")
            content = tool_input.get("content", "")
            target = _safe_path(path)
            if len(files_touched) >= MAX_FILES_TOUCHED and path not in files_touched:
                return f"Error: file budget ({MAX_FILES_TOUCHED}) reached this run — defer to next week"
            if dry_run:
                files_touched.add(path)
                return f"[dry-run] would write {len(content)} chars to {path}"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
            files_touched.add(path)
            status = push_file(target, message=f"Weekly cleanup: {path}")
            return f"OK: wrote {len(content)} chars to {path}\ngit: {status}"

        elif tool_name == "delete_file":
            path = tool_input.get("path", "")
            target = _safe_path(path)
            if not target.exists():
                return f"Error: '{path}' does not exist"
            if target.is_dir():
                return "Error: cannot delete directories via this tool"
            if len(files_touched) >= MAX_FILES_TOUCHED and path not in files_touched:
                return f"Error: file budget ({MAX_FILES_TOUCHED}) reached this run — defer to next week"
            if dry_run:
                files_touched.add(path)
                return f"[dry-run] would delete {path}"
            target.unlink()
            files_touched.add(path)
            status = delete_file(target, message=f"Weekly cleanup: remove {path}")
            return f"OK: deleted {path}\ngit: {status}"

        elif tool_name == "run_check":
            command = (tool_input.get("command") or "").strip()
            if command.startswith("py_compile "):
                file_arg = command[len("py_compile "):].strip()
                target = _safe_path(file_arg)
                result = subprocess.run(
                    [sys.executable, "-m", "py_compile", str(target)],
                    capture_output=True, text=True, timeout=30,
                )
                return "OK: compiles cleanly" if result.returncode == 0 else f"FAIL:\n{result.stderr}"
            elif command == "npm_build":
                result = subprocess.run(
                    ["npm", "run", "build"],
                    cwd=REPO_ROOT / "dashboard" / "frontend",
                    capture_output=True, text=True, timeout=180,
                )
                return "OK: build succeeded" if result.returncode == 0 else f"FAIL:\n{result.stdout}\n{result.stderr}"
            elif command.startswith("json_check "):
                file_arg = command[len("json_check "):].strip()
                target = _safe_path(file_arg)
                try:
                    json.loads(target.read_text())
                    return "OK: valid JSON"
                except Exception as e:
                    return f"FAIL: {e}"
            else:
                return "Error: unrecognized command — only 'py_compile <path>', 'npm_build', 'json_check <path>' are allowed"

        else:
            return f"Error: unknown tool '{tool_name}'"

    except (ValueError, PermissionError) as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error: {e}"


_FALLBACK_REPORT = "## Auto-Fixed\nNothing auto-fixed this week.\n\n## Needs Approval\nNothing pending."


def _extract_final_report(text: str) -> str:
    """The model is instructed to respond with exactly '## Auto-Fixed' ... '##
    Needs Approval' ... and nothing else, but LLMs don't always follow format
    instructions perfectly. Strip any preamble before the first real header so
    a stray sentence never leaks into next Monday's briefing."""
    if not text:
        return _FALLBACK_REPORT
    match = re.search(r"^## Auto-Fixed\b", text, re.MULTILINE)
    if not match:
        return _FALLBACK_REPORT
    return text[match.start():].strip()


def run_judgment_phase(candidates: dict, dry_run: bool) -> str:
    """Runs the bounded Claude session. Returns the model's final report text
    (the '## Auto-Fixed' / '## Needs Approval' block)."""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    summary_lines = []
    for category, items in candidates.items():
        if not items:
            continue
        summary_lines.append(f"### {category} ({len(items)})")
        summary_lines.append(json.dumps(items, indent=2)[:6000])
    candidate_summary = "\n\n".join(summary_lines) if summary_lines else "No candidates found by the static scan this week."

    messages = [{
        "role": "user",
        "content": (
            "Here is this week's static-scan candidate list. Investigate each one, apply safe "
            "fixes directly, and defer anything risky to your final report.\n\n" + candidate_summary
        ),
    }]

    files_touched = set()

    for _ in range(MAX_TOOL_CALLS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason != "tool_use":
            text_blocks = [b.text for b in response.content if b.type == "text"]
            return _extract_final_report("\n".join(text_blocks).strip())

        assistant_content = []
        for block in response.content:
            if block.type == "text":
                assistant_content.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                assistant_content.append({"type": "tool_use", "id": block.id, "name": block.name, "input": block.input})
        messages.append({"role": "assistant", "content": assistant_content})

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            result = _execute_tool(block.name, block.input, dry_run, files_touched)
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result[:4000]})
        messages.append({"role": "user", "content": tool_results})

    return (
        "## Auto-Fixed\n(Ran out of tool-call budget before finishing — see next week's run.)\n\n"
        "## Needs Approval\nNothing pending (run was cut short by the tool-call budget)."
    )


# ── Reporting ─────────────────────────────────────────────────────────────────

def load_last_run_sha() -> str:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text()).get("sha", "")
        except Exception:
            return ""
    return ""


def save_last_run_sha(dry_run: bool) -> None:
    if dry_run:
        return
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
            capture_output=True, text=True, timeout=10,
        )
        sha = result.stdout.strip()
        if sha:
            STATE_FILE.write_text(json.dumps({"sha": sha, "ran_at": datetime.now(timezone.utc).isoformat()}, indent=2))
            push_file(STATE_FILE, message="Weekly cleanup: update last_run.json")
    except Exception:
        pass


def notify_dashboard(message: str) -> None:
    """Post a short activity-feed line, mirroring how other cron jobs notify chat."""
    try:
        port = os.environ.get("PORT", "8000")
        password = os.environ.get("DASHBOARD_PASSWORD", "changeme")
        import urllib.request
        req = urllib.request.Request(
            f"http://localhost:{port}/api/dashboard/agent-messages",
            data=json.dumps({"agent": "Weekly Cleanup", "message": message}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        import base64 as _b64
        req.add_header("Authorization", "Basic " + _b64.b64encode(f"admin:{password}".encode()).decode())
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"  weekly-cleanup: dashboard notify failed: {e}")


def main():
    parser = argparse.ArgumentParser(description="DigiGrowth weekly repo cleanup")
    parser.add_argument("--dry-run", action="store_true", help="Log everything without writing or pushing")
    args = parser.parse_args()
    dry_run = args.dry_run

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"[weekly-cleanup] starting {'(dry-run) ' if dry_run else ''}— {today}")

    last_sha = load_last_run_sha()
    candidates = run_detection(since_sha=last_sha or None)
    print(f"[weekly-cleanup] detection: "
          f"{sum(len(v) for v in candidates.values() if isinstance(v, list))} candidates")

    judgment_report = run_judgment_phase(candidates, dry_run)

    archive_log = archive_old_reports(dry_run)
    stale_projects = flag_stale_projects()

    report_lines = [
        f"# Weekly Cleanup — {today}",
        "",
        judgment_report.strip(),
        "",
        "## Archived",
        *(archive_log if archive_log else ["Nothing to archive this week."]),
        "",
        "## Flagged Stale Projects",
        *(stale_projects if stale_projects else ["Nothing flagged this week."]),
        "",
    ]
    report_text = "\n".join(report_lines)

    report_path = EA_REPORTS_DIR / f"weekly-cleanup-{today}.md"
    if dry_run:
        print("[weekly-cleanup] dry-run — report below, not written or pushed:\n")
        print(report_text)
    else:
        EA_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report_text)
        status = push_file(report_path, message=f"Weekly cleanup report: {today}")
        print(f"[weekly-cleanup] report saved and pushed ({status})")
        notify_dashboard(f"Weekly cleanup complete for {today} — see reports/weekly-cleanup-{today}.md")

    save_last_run_sha(dry_run)
    print("[weekly-cleanup] done")


if __name__ == "__main__":
    main()
