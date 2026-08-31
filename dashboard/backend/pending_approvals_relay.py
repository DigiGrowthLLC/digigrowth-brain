"""
Pending-approvals relay — closes the loop for the newsletter/blog drafts
written by the Claude Code cloud routines ("EA Daily Briefing" and friends).

Those routines run under the Claude subscription in a sandbox that can't
reach Railway directly (same reason the daily-briefing report itself is
relayed via GitHub in main.py's _fetch_report_from_github /
_post_report_from_github). So instead of the newsletter/weekly-ai-blog
skills calling /api/agents/.../newsletter-pdf and /api/approvals directly,
they drop a small JSON request file into <agent_dir>/pending_approvals/ and
push it to GitHub — this module polls for those files, renders the
newsletter PDF and creates the real pending_approvals row + agent_chats
message in-process (Railway already has DASHBOARD_PASSWORD/GIT_TOKEN from
Doppler), then deletes the source file so it isn't reprocessed.

Used by both the scheduled cron job in main.py and the on-demand test
endpoint in routers/agents.py.
"""

import asyncio
import base64
import json
import os
import pathlib
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

import integrations
from db import get_pool
from routers.approvals import create_approval_row

_REPO = os.environ.get("GITHUB_REPO", "dylangroenendijk-sys/digigrowth-brain")
_TOKEN = os.environ.get("GIT_TOKEN", "")
_REPO_ROOT = pathlib.Path("/repo")


def _today_eastern() -> str:
    return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")


def _headers() -> dict:
    headers = {"Accept": "application/vnd.github.v3+json"}
    if _TOKEN:
        headers["Authorization"] = f"token {_TOKEN}"
    return headers


async def _gh_get(rel_path: str) -> str | None:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"https://api.github.com/repos/{_REPO}/contents/{rel_path}", headers=_headers())
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return base64.b64decode(resp.json()["content"]).decode("utf-8")


async def _gh_put_bytes(rel_path: str, content: bytes, message: str) -> str:
    if not _TOKEN:
        return "no GIT_TOKEN set"
    url = f"https://api.github.com/repos/{_REPO}/contents/{rel_path}"
    async with httpx.AsyncClient(timeout=15) as client:
        sha = None
        resp = await client.get(url, headers=_headers())
        if resp.status_code == 200:
            sha = resp.json().get("sha")
        elif resp.status_code != 404:
            return f"error getting SHA: {resp.status_code}"

        payload = {"message": message, "content": base64.b64encode(content).decode()}
        if sha:
            payload["sha"] = sha
        put_resp = await client.put(url, headers=_headers(), json=payload)
        if put_resp.status_code not in (200, 201):
            return f"error pushing: {put_resp.status_code} {put_resp.text[:200]}"
    return "pushed to GitHub"


async def _gh_delete(rel_path: str, message: str) -> str:
    if not _TOKEN:
        return "no GIT_TOKEN set"
    url = f"https://api.github.com/repos/{_REPO}/contents/{rel_path}"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, headers=_headers())
        if resp.status_code == 404:
            return "already gone"
        resp.raise_for_status()
        sha = resp.json().get("sha")
        del_resp = await client.request(
            "DELETE", url, headers=_headers(), json={"message": message, "sha": sha}
        )
        if del_resp.status_code != 200:
            return f"error deleting: {del_resp.status_code} {del_resp.text[:200]}"
    return "deleted from GitHub"


async def process_pending_approval(agent_dir: str, kind: str, date_str: str | None = None) -> str:
    """Pick up <agent_dir>/pending_approvals/<kind>-<date>.json and turn it
    into a real pending_approvals row + agent_chats message. No-ops (returns
    a status string, doesn't raise) if the file isn't there yet — expected
    on days the newsletter/blog don't run."""
    date_str = date_str or _today_eastern()
    job_label = f"pending-approval-{kind}"
    rel_path = f"{agent_dir}/pending_approvals/{kind}-{date_str}.json"

    try:
        raw = await _gh_get(rel_path)
    except Exception as e:
        return f"{job_label}: GitHub fetch failed: {e}"
    if raw is None:
        return f"{job_label}: nothing pending for {date_str}"

    try:
        data = json.loads(raw)
    except Exception as e:
        return f"{job_label}: bad JSON in {rel_path}: {e}"

    pdf_marker = ""
    if kind == "newsletter":
        md_rel = f"{agent_dir}/newsletter-draft-{date_str}.md"
        try:
            md_text = await _gh_get(md_rel)
        except Exception as e:
            md_text = None
            print(f"[cron] {job_label}: fetching {md_rel} failed: {e}", flush=True)
        if md_text is not None:
            local_md = _REPO_ROOT / md_rel
            local_md.parent.mkdir(parents=True, exist_ok=True)
            local_md.write_text(md_text, encoding="utf-8")
            try:
                pdf_bytes = await asyncio.to_thread(integrations._md_to_pdf_bytes, md_text)
                pdf_rel = f"{agent_dir}/newsletter-draft-{date_str}.pdf"
                (_REPO_ROOT / pdf_rel).write_bytes(pdf_bytes)
                push_result = await _gh_put_bytes(pdf_rel, pdf_bytes, f"Newsletter PDF: {date_str}")
                print(f"[cron] {job_label}: PDF {push_result}", flush=True)
                pdf_marker = "[[PDF:newsletter]]\n"
            except Exception as e:
                print(f"[cron] {job_label}: PDF generation failed: {e}", flush=True)

    try:
        pool = await get_pool()
        approval = await create_approval_row(
            pool, kind, data.get("title", kind), data.get("summary"), data.get("payload", {})
        )
    except Exception as e:
        return f"{job_label}: approval insert failed: {e}"

    chat_text = f"{data.get('summary', '')}\n\n{pdf_marker}[[APPROVAL:{approval['id']}]]"
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO agent_chats (agent_id, role, content) VALUES ($1, $2, $3)",
                "executive-assistant", "assistant",
                json.dumps([{"type": "text", "text": chat_text}]),
            )
    except Exception as e:
        return f"{job_label}: approval #{approval['id']} created but chat insert failed: {e}"

    del_result = await _gh_delete(rel_path, f"Processed pending approval: {rel_path}")
    return f"{job_label}: approval #{approval['id']} posted to chat ({del_result})"


async def process_pending_approvals(date_str: str | None = None) -> str:
    newsletter_result = await process_pending_approval("apptset-agent", "newsletter", date_str)
    blog_result = await process_pending_approval("content-agent", "blog", date_str)
    return f"{newsletter_result}; {blog_result}"


async def process_pending_cleanup_approval(date_str: str | None = None) -> str:
    """Separate entry point (not folded into process_pending_approvals above,
    which runs daily at 6:40am) because weekly-cleanup runs Sunday ~8:04pm ET
    — see the dedicated 'weekly-cleanup-approval-relay' cron job in main.py."""
    return await process_pending_approval("weekly-cleanup", "cleanup", date_str)
