"""
Local worker for the SMS setter — runs on Dylan's PC, drafts (or in auto
mode, sends) replies to his cold SMS prospects using his Claude
SUBSCRIPTION via `claude -p`, not the API. Because it runs here, the setter
is only active while this machine is on and logged in; when it's off,
replies just wait in the Inbox like before.

Loop (every POLL_SECONDS):
  1. GET  /api/sms-setter/worker/queue  (also the heartbeat the Inbox shows
     as online/offline) -> system prompt, output schema, threads to draft
  2. for each thread: `claude -p` with that prompt -> structured draft
  3. POST /api/sms-setter/worker/submit -> the server stores it, and in auto
     mode sends it (see dashboard/backend/sms_setter_ai.py for guardrails)
  4. for each lesson in the queue (a reply Dylan typed himself instead of
     the draft): `claude -p` distills it -> POST /api/sms-setter/worker/lesson.
     Active lessons come back inside the system prompt from step 1
  5. in auto mode: POST /api/sms-setter/worker/flush -> sends drafts that
     were held until business hours

Started at logon by the DigiGrowth-SMSSetter scheduled task
(register-sms-setter-task.ps1), under `doppler run` for DASHBOARD_URL /
DASHBOARD_PASSWORD. ANTHROPIC_API_KEY (also in that Doppler config) is
stripped before launching claude, otherwise Claude Code would bill the API
key instead of the subscription.

Manual run (foreground, logs to console too):
  doppler run --project digigrowth --config prd -- python apptset-agent/sms_setter_worker.py --console
  ... --once     one pass, then exit
"""
import argparse
import base64
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

POLL_SECONDS = 60
CLAUDE_TIMEOUT_SECONDS = 300
MODEL = os.environ.get("SMS_SETTER_MODEL", "opus")
EFFORT = os.environ.get("SMS_SETTER_EFFORT", "medium")
_LOCK_PORT = 47614   # single-instance guard: a second copy can't bind it and exits

LOG_DIR = Path(__file__).parent / "logs"
_console = False


def log(msg: str) -> None:
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    LOG_DIR.mkdir(exist_ok=True)
    with open(LOG_DIR / f"sms-setter_{datetime.now():%Y-%m-%d}.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")
    if _console:
        print(line, flush=True)


# ── Dashboard API ─────────────────────────────────────────────────────────────

def _api(method: str, path: str, body: dict | None = None) -> dict:
    base = os.environ["DASHBOARD_URL"].rstrip("/")
    auth = base64.b64encode(f"admin:{os.environ['DASHBOARD_PASSWORD']}".encode()).decode()
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method, headers={
        "Authorization": f"Basic {auth}", "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read() or b"{}")


# ── Claude Code (subscription) ────────────────────────────────────────────────

def _claude_exe() -> str:
    """The real claude.exe behind npm's claude.cmd shim — calling the .cmd
    would route the JSON-schema argument through cmd.exe's quoting rules."""
    shim = shutil.which("claude.cmd") or shutil.which("claude")
    if not shim:
        raise RuntimeError("claude CLI not found on PATH")
    exe = Path(shim).parent / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
    return str(exe) if exe.exists() else shim


def run_claude(system_prompt: str, prompt: str, schema: dict) -> dict | None:
    """One draft through `claude -p` on the subscription. No tools, no
    project/user settings, no MCP servers, no saved session — just the
    prompt in and schema-validated JSON out. Returns the structured output
    or None."""
    workdir = Path(tempfile.gettempdir()) / "sms-setter-claude"
    workdir.mkdir(exist_ok=True)
    sys_file = workdir / "system_prompt.md"
    sys_file.write_text(system_prompt, encoding="utf-8")

    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    cmd = [
        _claude_exe(), "-p",
        "--model", MODEL, "--effort", EFFORT,
        "--output-format", "json",
        "--json-schema", json.dumps(schema),
        "--system-prompt-file", str(sys_file),
        "--tools", "",
        "--strict-mcp-config",
        "--setting-sources", "",
        "--no-session-persistence",
    ]
    proc = subprocess.run(
        cmd, input=prompt, capture_output=True, text=True, encoding="utf-8", cwd=workdir, env=env,
        timeout=CLAUDE_TIMEOUT_SECONDS, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError:
        log(f"claude returned non-JSON (exit {proc.returncode}): {proc.stdout[:300]} {proc.stderr[:300]}")
        return None
    if out.get("is_error") or not isinstance(out.get("structured_output"), dict):
        log(f"claude error: subtype={out.get('subtype')} result={str(out.get('result'))[:300]}")
        return None
    if out.get("apiKeySource"):
        # Should never happen (the key is stripped above) — but if it does,
        # this is billing the API, not the subscription. Say so loudly.
        log(f"WARNING: claude used an API key ({out['apiKeySource']}), not the subscription")
    return out["structured_output"]


# ── Loop ──────────────────────────────────────────────────────────────────────

def one_pass() -> None:
    q = _api("GET", "/api/sms-setter/worker/queue")
    items = q.get("items", [])
    if items:
        log(f"mode={q['mode']} drafting {len(items)} thread(s)")
    for item in items:
        started = time.time()
        try:
            result = run_claude(q["system_prompt"], item["prompt"], q["schema"])
        except subprocess.TimeoutExpired:
            log(f"{item['business']}: claude timed out")
            continue
        if not result:
            continue
        resp = _api("POST", "/api/sms-setter/worker/submit", {
            "phone": item["phone"], "last_inbound_at": item["last_inbound_at"],
            "result": result, "model": f"claude-code:{MODEL}",
        })
        log(f"{item['business']}: {result.get('action')} ({time.time() - started:.0f}s) -> {resp}")
    for lesson in q.get("lessons") or []:
        try:
            result = run_claude(q["lesson_system_prompt"], lesson["prompt"], q["lesson_schema"])
        except subprocess.TimeoutExpired:
            log(f"lesson {lesson['id']}: claude timed out")
            continue
        if not result:
            continue
        resp = _api("POST", "/api/sms-setter/worker/lesson", {"id": lesson["id"], "result": result})
        learned = f"learned \"{result.get('situation')}\"" if result.get("useful") else "nothing reusable"
        log(f"lesson {lesson['id']}: {learned} -> {resp}")
    if q.get("mode") == "auto":
        flushed = _api("POST", "/api/sms-setter/worker/flush", {})
        if flushed.get("sent"):
            log(f"sent {flushed['sent']} held draft(s)")


def main() -> None:
    global _console
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--console", action="store_true")
    args = ap.parse_args()
    _console = args.console

    lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        lock.bind(("127.0.0.1", _LOCK_PORT))
    except OSError:
        log("another sms_setter_worker is already running, exiting")
        return

    log(f"worker started (model={MODEL}, effort={EFFORT}, claude={_claude_exe()})")
    while True:
        try:
            one_pass()
        except urllib.error.URLError as e:
            log(f"dashboard unreachable: {e}")
        except Exception as e:
            log(f"pass failed: {type(e).__name__}: {e}")
        if args.once:
            return
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    sys.exit(main())
