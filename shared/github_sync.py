"""
Shared GitHub file sync utility.

Any agent script can call push_file() after modifying a file to ensure the
change is persisted to GitHub — surviving Railway redeploys or machine switches.

Usage:
    from shared.github_sync import push_file

    push_file(__file__, "memory.txt")           # relative to calling script
    push_file("/absolute/path/to/file.json")    # absolute path also works
"""

import base64
import json
import os
import pathlib
import subprocess
import urllib.error
import urllib.request

GITHUB_REPO = os.environ.get("GITHUB_REPO", "dylangroenendijk-sys/digigrowth-brain")

# Repo root = parent of this file's directory (shared/ → repo root)
_REPO_ROOT = pathlib.Path(__file__).parent.parent.resolve()


def push_file(caller_or_path, relative_path: str = None, message: str = None) -> str:
    """
    Push a file change to GitHub.

    Two calling styles:
        push_file(__file__, "memory.txt")          # relative to calling script
        push_file("/abs/path/to/file.txt")          # absolute path

    Returns a short status string ("pushed", "committed", "error: ...").
    """
    if relative_path is not None:
        # Style 1: caller script + relative path
        caller_dir = pathlib.Path(caller_or_path).parent
        file_abs = (caller_dir / relative_path).resolve()
    else:
        # Style 2: absolute path string or Path
        file_abs = pathlib.Path(caller_or_path).resolve()

    if not file_abs.exists():
        return f"error: {file_abs} does not exist"

    if message is None:
        try:
            rel = file_abs.relative_to(_REPO_ROOT)
        except ValueError:
            rel = file_abs.name
        message = f"Agent update: {rel}"

    # Try git CLI first (works on local machine where .git/ exists)
    git_result = _try_git(file_abs, message)
    if git_result.startswith("ok"):
        return "committed and pushed"

    # Fall back to GitHub REST API (works on Railway where .git/ is absent)
    return _github_api_push(file_abs, message)


# ── Git CLI ───────────────────────────────────────────────────────────────────

def _try_git(file_abs: pathlib.Path, message: str) -> str:
    try:
        rel = str(file_abs.relative_to(_REPO_ROOT))
    except ValueError:
        return "skip: path outside repo"

    try:
        r = subprocess.run(
            ["git", "add", rel], cwd=_REPO_ROOT,
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode != 0:
            return f"git add failed: {r.stderr.strip()}"

        diff = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=_REPO_ROOT, timeout=5,
        )
        if diff.returncode == 0:
            return "ok: no changes"

        r = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=_REPO_ROOT, capture_output=True, text=True, timeout=15,
        )
        if r.returncode != 0:
            return f"git commit failed: {r.stderr.strip()}"

        r = subprocess.run(
            ["git", "push"],
            cwd=_REPO_ROOT, capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            return f"git push failed: {r.stderr.strip()}"

        return "ok: pushed"

    except FileNotFoundError:
        return "skip: git not found"
    except subprocess.TimeoutExpired:
        return "skip: git timed out"
    except Exception as e:
        return f"skip: {e}"


# ── GitHub REST API ───────────────────────────────────────────────────────────

def _github_api_push(file_abs: pathlib.Path, message: str) -> str:
    token = os.environ.get("GIT_TOKEN", "")
    if not token:
        return "no GIT_TOKEN set"

    try:
        rel = str(file_abs.relative_to(_REPO_ROOT))
    except ValueError:
        return "error: path outside repo"

    try:
        content_b64 = base64.b64encode(file_abs.read_bytes()).decode()
    except Exception as e:
        return f"error reading file: {e}"

    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{rel}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }

    # Get current SHA (needed for updates; None for new files)
    sha = None
    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            sha = json.loads(resp.read()).get("sha")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            return f"error getting SHA: {e}"

    payload: dict = {"message": message, "content": content_b64}
    if sha:
        payload["sha"] = sha

    try:
        req = urllib.request.Request(
            api_url,
            data=json.dumps(payload).encode(),
            headers=headers,
            method="PUT",
        )
        with urllib.request.urlopen(req, timeout=15):
            pass
        return "pushed to GitHub"
    except Exception as e:
        return f"error pushing: {e}"
