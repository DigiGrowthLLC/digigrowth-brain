import base64
import json
import os
import urllib.error
import urllib.request
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import integrations
from db import get_pool

router = APIRouter()

_WEBSITE_REPO = "dylangroenendijk-sys/digigrowth-website"
_BLOG_POSTS_PATH = "src/content/blog-posts.json"
_BRAIN_REPO = os.environ.get("GITHUB_REPO", "dylangroenendijk-sys/digigrowth-brain")
_API_BASE = os.environ.get("DASHBOARD_URL", "https://digigrowth-brain-production.up.railway.app")
NEWSLETTER_DAILY_CAP = integrations.NEWSLETTER_DAILY_CAP

_COLS = "id, kind, title, summary, payload, status, result, created_at, decided_at"


class CreateApproval(BaseModel):
    kind: str          # "blog" | "newsletter" | "cleanup"
    title: str
    summary: Optional[str] = None
    payload: dict = {}


class DecideApproval(BaseModel):
    decision: str       # "approve" | "decline"


def _row_to_dict(row) -> dict:
    d = dict(row)
    d["payload"] = json.loads(d["payload"]) if isinstance(d["payload"], str) else d["payload"]
    d["created_at"] = d["created_at"].isoformat() if d["created_at"] else None
    d["decided_at"] = d["decided_at"].isoformat() if d["decided_at"] else None
    return d


def _gh_request(repo: str, path: str, headers: dict, method: str = "GET", data: bytes = None):
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    return urllib.request.urlopen(req, timeout=30)


def _publish_blog_post(payload: dict) -> str:
    """Fetch blog-posts.json from digigrowth-website, prepend the new post, push it back."""
    token = os.environ.get("GIT_TOKEN", "")
    if not token:
        return "error: GIT_TOKEN not configured"

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }

    post = payload.get("post")
    if not post or not post.get("slug"):
        return "error: payload missing 'post' with a slug"

    # Fetch current file (may not exist / may be empty array)
    sha = None
    posts = []
    try:
        with _gh_request(_WEBSITE_REPO, _BLOG_POSTS_PATH, headers) as resp:
            data = json.loads(resp.read())
            sha = data.get("sha")
            raw = base64.b64decode(data["content"]).decode("utf-8")
            posts = json.loads(raw) if raw.strip() else []
    except urllib.error.HTTPError as e:
        if e.code != 404:
            return f"error fetching blog-posts.json: {e}"
    except Exception as e:
        return f"error reading current blog-posts.json: {e}"

    if any(p.get("slug") == post["slug"] for p in posts):
        return f"error: slug '{post['slug']}' already exists"

    posts = [post] + posts
    new_content = json.dumps(posts, indent=2) + "\n"

    push_payload: dict = {
        "message": f"Publish blog post: {post.get('title', post['slug'])}",
        "content": base64.b64encode(new_content.encode("utf-8")).decode(),
    }
    if sha:
        push_payload["sha"] = sha

    try:
        with _gh_request(
            _WEBSITE_REPO, _BLOG_POSTS_PATH, headers,
            method="PUT", data=json.dumps(push_payload).encode(),
        ):
            pass
        return "pushed to GitHub"
    except urllib.error.HTTPError as e:
        return f"error pushing blog-posts.json: {e}"
    except Exception as e:
        return f"error: {e}"


def _apply_cleanup(payload: dict) -> str:
    """Apply the weekly-cleanup routine's proposed file changes to digigrowth-brain
    via the Contents API. Each item in payload['changes'] is either:
      {"file": "path/in/repo", "action": "write", "content": "<full new file text>", ...}
      {"file": "path/in/repo", "action": "delete", ...}
    payload['auto_fixed'] is display-only (already applied by the routine itself
    when it ran) and is never touched here."""
    token = os.environ.get("GIT_TOKEN", "")
    if not token:
        return "error: GIT_TOKEN not configured"

    changes = payload.get("changes") or []
    if not changes:
        return "no changes to apply"

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }

    results = []
    for change in changes:
        path = change.get("file")
        action = change.get("action")
        if not path or action not in ("write", "delete"):
            results.append(f"{path or '?'}: skipped (invalid change)")
            continue

        sha = None
        try:
            with _gh_request(_BRAIN_REPO, path, headers) as resp:
                sha = json.loads(resp.read()).get("sha")
        except urllib.error.HTTPError as e:
            if e.code != 404:
                results.append(f"{path}: error getting SHA — {e}")
                continue
        except Exception as e:
            results.append(f"{path}: error getting SHA — {e}")
            continue

        try:
            if action == "write":
                body: dict = {
                    "message": f"Cleanup: {change.get('summary') or path}",
                    "content": base64.b64encode(change.get("content", "").encode("utf-8")).decode(),
                }
                if sha:
                    body["sha"] = sha
                with _gh_request(_BRAIN_REPO, path, headers, method="PUT", data=json.dumps(body).encode()):
                    pass
                results.append(f"{path}: updated")
            else:  # delete
                if not sha:
                    results.append(f"{path}: already gone")
                    continue
                body = {"message": f"Cleanup: remove {path}", "sha": sha}
                with _gh_request(_BRAIN_REPO, path, headers, method="DELETE", data=json.dumps(body).encode()):
                    pass
                results.append(f"{path}: deleted")
        except Exception as e:
            results.append(f"{path}: error — {e}")

    return "; ".join(results)


async def _enqueue_newsletter(conn, approval_id: int, payload: dict) -> str:
    """Personalize the draft per newsletter-flagged contact and drop each into
    newsletter_send_queue — actual sending happens gradually via the scheduled
    queue processor in main.py, not all at once here, to protect the sending
    mailbox's domain reputation as the list grows."""
    subject = payload.get("subject")
    html = payload.get("html")
    if not subject or not html:
        return "error: draft has no subject/html attached — nothing queued"

    # A contact counts as subscribed via either the boolean flag or the "Newsletter"
    # tag — the dialer's auto-opt-in (Follow Up 30/90 Day dispositions) only sets the
    # tag, not the boolean, so checking just one misses contacts opted in that way.
    contacts = await conn.fetch(
        """SELECT id, owner, business, email FROM contacts
           WHERE (newsletter = true OR 'Newsletter' = ANY(tags))
           AND email IS NOT NULL AND email != ''"""
    )
    if not contacts:
        return "0 contacts flagged newsletter in the DigiGrowth OS — nothing queued"

    for c in contacts:
        first_name = (c["owner"] or "there").split(" ")[0]
        business_name = c["business"] or "your business"
        unsubscribe_link = f"{_API_BASE}/api/newsletter/unsubscribe/{c['id']}"
        personalized_subject = (
            subject.replace("{{first_name}}", first_name).replace("{{business_name}}", business_name)
        )
        personalized_html = (
            html.replace("{{first_name}}", first_name)
                .replace("{{business_name}}", business_name)
                .replace("{{unsubscribe_link}}", unsubscribe_link)
        )
        await conn.execute(
            """INSERT INTO newsletter_send_queue (approval_id, contact_id, email, subject, html)
               VALUES ($1, $2, $3, $4, $5)""",
            approval_id, c["id"], c["email"], personalized_subject, personalized_html,
        )

    return (
        f"queued {len(contacts)} email(s) for gradual delivery "
        f"(~{NEWSLETTER_DAILY_CAP}/day cap, paced through business hours — not sent all at once)"
    )


async def create_approval_row(pool, kind: str, title: str, summary: Optional[str], payload: dict) -> dict:
    """Shared insert used by both the /api/approvals route and the
    pending-approvals relay job in main.py (which calls this in-process
    instead of looping back through HTTP)."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            INSERT INTO pending_approvals (kind, title, summary, payload)
            VALUES ($1, $2, $3, $4)
            RETURNING {_COLS}
            """,
            kind, title, summary, json.dumps(payload),
        )
    return _row_to_dict(row)


@router.post("/approvals")
async def create_approval(body: CreateApproval):
    if body.kind not in ("blog", "newsletter", "cleanup"):
        raise HTTPException(status_code=400, detail="kind must be 'blog', 'newsletter', or 'cleanup'")
    pool = await get_pool()
    return await create_approval_row(pool, body.kind, body.title, body.summary, body.payload)


@router.get("/approvals/{approval_id}")
async def get_approval(approval_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(f"SELECT {_COLS} FROM pending_approvals WHERE id = $1", approval_id)
    if not row:
        raise HTTPException(status_code=404, detail="approval not found")
    return _row_to_dict(row)


@router.post("/approvals/{approval_id}/decide")
async def decide_approval(approval_id: int, body: DecideApproval):
    if body.decision not in ("approve", "decline"):
        raise HTTPException(status_code=400, detail="decision must be 'approve' or 'decline'")

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(f"SELECT {_COLS} FROM pending_approvals WHERE id = $1", approval_id)
        if not row:
            raise HTTPException(status_code=404, detail="approval not found")
        approval = _row_to_dict(row)

        if approval["status"] != "pending":
            return approval  # already decided — idempotent, don't re-run side effects

        result = None
        if body.decision == "approve" and approval["kind"] == "blog":
            result = _publish_blog_post(approval["payload"])
        elif body.decision == "approve" and approval["kind"] == "newsletter":
            result = await _enqueue_newsletter(conn, approval_id, approval["payload"])
        elif body.decision == "approve" and approval["kind"] == "cleanup":
            result = _apply_cleanup(approval["payload"])

        new_status = "approved" if body.decision == "approve" else "declined"
        updated = await conn.fetchrow(
            f"""
            UPDATE pending_approvals
            SET status = $1, result = $2, decided_at = now()
            WHERE id = $3
            RETURNING {_COLS}
            """,
            new_status, result, approval_id,
        )
    return _row_to_dict(updated)


@router.post("/newsletter/process-queue")
async def process_newsletter_queue_now():
    """Manually trigger one batch of the newsletter send queue right now,
    instead of waiting for the scheduled 9am-5pm ET weekday window — for
    testing, or clearing a backlog. Same daily cap and batch size as the
    scheduled job (they share integrations.process_newsletter_queue())."""
    result = await integrations.process_newsletter_queue()
    return {"result": result}
