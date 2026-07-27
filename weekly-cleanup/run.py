"""
Weekly Repo Cleanup — pure-Python helper library.

This module holds ONLY the zero-LLM-cost helpers the "EA Weekly Cleanup" Claude
Code routine reuses each week:

  * Detection  — run_detection() and its sub-scans build a bounded candidate
                 list of unused imports, zero-caller functions, broken doc
                 references, and duplicated helpers.
  * Retention  — archive_old_reports() moves reports/ files older than
                 RETENTION_DAYS into archives/reports-YYYY-MM/.
  * Stale flag — flag_stale_projects() reports projects/ entries with no git
                 activity in STALE_PROJECT_DAYS (never touches them).
  * State      — load_last_run_sha() reads the SHA of the previous run.

There is no `main()` and no CLI — this is an import-only helper library, not a
runnable script. The judgment/fix phase that the old script performed via a
metered Anthropic API call now lives in the routine itself, which imports these
helpers and does the reasoning with its own native Claude Code tools. Keeping
these helpers here is what makes `from run import run_detection, ...` work; the
functions are copied verbatim from the pre-migration script so detection output
is byte-for-byte identical to what it produced.
"""

import ast
import hashlib
import json
import pathlib
import re
import subprocess
from datetime import datetime, timedelta, timezone

import sys
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "shared"))
from github_sync import push_file, delete_file  # noqa: E402

# ── Paths ───────────────────────────────────────────────────────────────────

REPO_ROOT       = pathlib.Path(__file__).parent.parent.resolve()
EA_REPORTS_DIR  = REPO_ROOT / "executive-assistant" / "reports"
EA_ARCHIVES_DIR = REPO_ROOT / "executive-assistant" / "archives"
EA_PROJECTS_DIR = REPO_ROOT / "executive-assistant" / "projects"
STATE_FILE      = REPO_ROOT / "weekly-cleanup" / "last_run.json"

# ── Config ──────────────────────────────────────────────────────────────────

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


# ── State ────────────────────────────────────────────────────────────────────

def load_last_run_sha() -> str:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text()).get("sha", "")
        except Exception:
            return ""
    return ""
