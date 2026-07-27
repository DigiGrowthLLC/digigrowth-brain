import asyncio
import json
import os
import pathlib
import secrets
import sys
from contextlib import asynccontextmanager

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles

import integrations
from db import get_pool
from pending_approvals_relay import process_pending_approvals
from routers import crm, sms, dialer, dialer_webhooks, dashboard, agents, settings, analytics, finances, sops, public_sops, legal, email_inbox, approvals, tags, newsletter, newsletter_queue, appointments
import reminder_engine

security = HTTPBasic()
DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "changeme")


def require_auth(credentials: HTTPBasicCredentials = Depends(security)):
    ok = secrets.compare_digest(credentials.password.encode(), DASHBOARD_PASSWORD.encode())
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


def _today_eastern() -> str:
    from datetime import datetime
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")


async def _fetch_report_from_github(rel_path: str, job_label: str) -> str | None:
    """Read a file committed by a Claude cloud routine straight from the
    GitHub API. The routines run under the Claude subscription (not the
    metered API) but their sandbox can't reach Railway directly, so they only
    commit their report to GitHub — Railway already talks to the GitHub API
    for github_push_file, so this closes the loop from that side instead.
    """
    import base64

    repo = os.environ.get("GITHUB_REPO", "dylangroenendijk-sys/digigrowth-brain")
    token = os.environ.get("GIT_TOKEN", "")
    api_url = f"https://api.github.com/repos/{repo}/contents/{rel_path}"
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(api_url, headers=headers)
        if resp.status_code == 404:
            print(f"[cron] {job_label}: {rel_path} not on GitHub yet — routine may still be running", flush=True)
            return None
        resp.raise_for_status()
        text = base64.b64decode(resp.json()["content"]).decode("utf-8").strip()
    except Exception as e:
        print(f"[cron] {job_label}: GitHub fetch failed: {e}", flush=True)
        return None

    if not text:
        return None

    # Mirror to local disk — Railway's container isn't git-synced, so nothing
    # else (PDF export, file browser) sees the routine's GitHub commit otherwise.
    local_path = pathlib.Path("/repo") / rel_path
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_text(text, encoding="utf-8")
    return text


async def _post_report_from_github(filename_prefix: str, job_label: str, after: callable = None) -> None:
    """Fetch today's report (EA Sheets Digest / EA Daily Briefing) and paste
    it into the EA chat window — a plain read + DB insert, no LLM call."""
    rel_path = f"executive-assistant/reports/{filename_prefix}-{_today_eastern()}.md"
    report_text = await _fetch_report_from_github(rel_path, job_label)
    if report_text is None:
        return

    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO agent_chats (agent_id, role, content) VALUES ($1, $2, $3)",
                "executive-assistant",
                "assistant",
                json.dumps([{"type": "text", "text": report_text}]),
            )
        print(f"[cron] {job_label}: posted to EA chat", flush=True)
    except Exception as e:
        print(f"[cron] {job_label}: chat insert failed: {e}", flush=True)

    if after is not None:
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, after)
            print(f"[cron] {job_label}: {result}", flush=True)
        except Exception as e:
            print(f"[cron] {job_label}: post-step failed: {e}", flush=True)


async def _run_leadgen() -> None:
    """Check if a dialing session ran today, then launch the leadgen script."""
    cfg_path = pathlib.Path("/repo/leadgen-agent/config.json")
    if cfg_path.exists():
        cfg = json.loads(cfg_path.read_text())
        if not cfg.get("enabled", True):
            print("[cron] leadgen skipped — disabled in config.json", flush=True)
            return
    pool = await get_pool()
    async with pool.acquire() as conn:
        count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM call_logs
            WHERE (started_at AT TIME ZONE 'America/New_York')::date
                  = (now() AT TIME ZONE 'America/New_York')::date
            """
        )
    lead_status = "dialer-lead" if count > 0 else "sms-handoff"
    print(f"[cron] leadgen starting — call_logs today={count}, status={lead_status}", flush=True)
    script = pathlib.Path("/repo/leadgen-agent/run.py")
    proc = await asyncio.create_subprocess_exec(
        sys.executable, str(script), "--status", lead_status,
        cwd=str(script.parent),
    )
    await proc.wait()
    print(f"[cron] leadgen done — status={lead_status} rc={proc.returncode}", flush=True)

    # Post completion summary into the EA chat window
    try:
        async with pool.acquire() as conn:
            added = await conn.fetchval(
                "SELECT COUNT(*) FROM contacts WHERE created_at > now() - interval '30 minutes'"
            )
            status_label = "ready to dial" if lead_status == "dialer-lead" else "queued for SMS outreach"
            ok_flag = "✅" if proc.returncode == 0 else "⚠️"
            msg = (
                f"{ok_flag} **Leadgen complete** — {added} leads added ({status_label})."
                if proc.returncode == 0
                else f"⚠️ Leadgen finished with errors (exit code {proc.returncode}). Check Railway logs."
            )
            await conn.execute(
                "INSERT INTO agent_chats (agent_id, role, content) VALUES ($1, $2, $3)",
                "executive-assistant",
                "assistant",
                json.dumps([{"type": "text", "text": msg}]),
            )
    except Exception as e:
        print(f"[cron] leadgen chat notify failed: {e}", flush=True)


async def _push_file_to_github(rel_path: str, content: str, message: str) -> str:
    """Write a file to GitHub via the REST API (get current SHA, then PUT)."""
    import base64

    repo = os.environ.get("GITHUB_REPO", "dylangroenendijk-sys/digigrowth-brain")
    token = os.environ.get("GIT_TOKEN", "")
    if not token:
        return "no GIT_TOKEN set"
    api_url = f"https://api.github.com/repos/{repo}/contents/{rel_path}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}

    async with httpx.AsyncClient(timeout=15) as client:
        sha = None
        resp = await client.get(api_url, headers=headers)
        if resp.status_code == 200:
            sha = resp.json().get("sha")
        elif resp.status_code != 404:
            return f"error getting SHA: {resp.status_code}"

        payload = {"message": message, "content": base64.b64encode(content.encode()).decode()}
        if sha:
            payload["sha"] = sha
        put_resp = await client.put(api_url, headers=headers, json=payload)
        if put_resp.status_code not in (200, 201):
            return f"error pushing: {put_resp.status_code} {put_resp.text[:200]}"
    return "pushed to GitHub"


async def _export_newsletter_contacts() -> None:
    """Export contacts flagged `newsletter = true` in the OS CRM to a
    git-tracked JSON file the newsletter skill's cloud routine can read via
    `git pull` — it can't reach Railway's API directly (sandboxed network),
    so this closes the loop from Railway's side, same pattern as the report
    pickups above. Replaces the old GHL-based recipient lookup (GHL is no
    longer in use)."""
    from datetime import datetime, timezone

    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT owner, business, email FROM contacts
                   WHERE (newsletter = true OR 'Newsletter' = ANY(tags))
                   ORDER BY business"""
            )
    except Exception as e:
        print(f"[cron] newsletter-export: DB query failed: {e}", flush=True)
        return

    payload = {
        "count": len(rows),
        "recipients": [{"owner": r["owner"], "business": r["business"], "email": r["email"]} for r in rows],
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }
    content = json.dumps(payload, indent=2)

    local_path = pathlib.Path("/repo/apptset-agent/newsletter_recipients.json")
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_text(content, encoding="utf-8")

    status = await _push_file_to_github(
        "apptset-agent/newsletter_recipients.json", content,
        f"Newsletter recipient export: {len(rows)} contacts",
    )
    print(f"[cron] newsletter-export: {len(rows)} contacts ({status})", flush=True)


async def _process_newsletter_queue() -> None:
    """Scheduled wrapper — runs every ~25 min during business hours on weekdays
    (see the CronTrigger below). Actual logic lives in
    integrations.process_newsletter_queue() so the manual "process now" test
    endpoint (routers/newsletter.py) can share it."""
    try:
        result = await integrations.process_newsletter_queue()
        print(f"[cron] newsletter-queue: {result}", flush=True)
    except Exception as e:
        print(f"[cron] newsletter-queue: failed: {e}", flush=True)


async def _process_pending_approvals_job() -> None:
    """Picks up newsletter/blog draft JSON files the daily-briefing/weekly-ai-blog
    cloud routines committed to GitHub (see pending_approvals_relay.py for why —
    same can't-reach-Railway-directly reason as _fetch_report_from_github above)
    and turns them into real pending_approvals rows + agent_chats messages.
    Runs daily; no-ops harmlessly on days no draft was written (newsletter is
    Mon/Wed/Fri only, blog is Mondays only)."""
    try:
        result = await process_pending_approvals()
        print(f"[cron] {result}", flush=True)
    except Exception as e:
        print(f"[cron] pending-approvals-relay failed: {e}", flush=True)


async def _post_weekly_cleanup_report() -> None:
    """Pick up the weekly cleanup report committed by the 'EA Weekly Cleanup'
    cloud routine (runs Sundays ~8:04pm ET under the Claude subscription) and
    post an activity-feed line — mirrors the old notify_dashboard() behavior
    from weekly-cleanup/run.py, which this routine replaces."""
    today = _today_eastern()
    rel_path = f"executive-assistant/reports/weekly-cleanup-{today}.md"
    report_text = await _fetch_report_from_github(rel_path, "weekly-cleanup")
    if report_text is None:
        return
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO agent_messages (agent, message) VALUES ($1, $2)",
                "Weekly Cleanup",
                f"Weekly cleanup complete for {today} — see reports/weekly-cleanup-{today}.md",
            )
        print("[cron] weekly-cleanup: posted to activity feed", flush=True)
    except Exception as e:
        print(f"[cron] weekly-cleanup: activity feed insert failed: {e}", flush=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_pool()

    scheduler = AsyncIOScheduler()
    eastern = "America/New_York"
    # Sheets digest and daily briefing now run as Claude Code cloud routines
    # ("EA Sheets Digest" 5:57am ET, "EA Daily Briefing" 6:03am ET) under the
    # subscription plan instead of the metered API. These jobs just pick up
    # the finished report from GitHub and paste it into the EA chat — see
    # _post_report_from_github. Times are staggered after the routines to
    # give them time to finish.
    scheduler.add_job(
        _export_newsletter_contacts,
        CronTrigger(hour=5, minute=45, timezone=eastern),
        id="newsletter-contacts-export-daily",
        replace_existing=True,
    )
    scheduler.add_job(
        _post_report_from_github,
        CronTrigger(hour=6, minute=15, timezone=eastern, day_of_week="mon-fri"),
        args=["sheets-digest", "sheets-digest"],
        id="sheets-digest-daily",
        replace_existing=True,
    )
    scheduler.add_job(
        _post_report_from_github,
        CronTrigger(hour=6, minute=30, timezone=eastern, day_of_week="mon-fri"),
        args=["daily-briefing", "daily-briefing"],
        kwargs={"after": integrations.save_daily_brief_pdf},
        id="daily-briefing-daily",
        replace_existing=True,
    )
    scheduler.add_job(
        _process_pending_approvals_job,
        CronTrigger(hour=6, minute=40, timezone=eastern),
        id="pending-approvals-relay",
        replace_existing=True,
    )
    scheduler.add_job(
        _run_leadgen,
        CronTrigger(hour=20, minute=0, timezone=eastern, day_of_week="mon-fri"),
        id="leadgen-daily",
        replace_existing=True,
    )
    scheduler.add_job(
        _post_weekly_cleanup_report,
        CronTrigger(hour=20, minute=30, timezone=eastern, day_of_week="sun"),
        id="weekly-cleanup",
        replace_existing=True,
    )
    scheduler.add_job(
        email_inbox.sync_gmail_job,
        IntervalTrigger(seconds=60),
        id="email-inbox-sync",
        replace_existing=True,
    )
    scheduler.add_job(
        _process_newsletter_queue,
        CronTrigger(minute="*/25", hour="9-17", day_of_week="mon-fri", timezone=eastern),
        id="newsletter-queue-processor",
        replace_existing=True,
    )
    scheduler.add_job(
        reminder_engine.send_due_reminders,
        IntervalTrigger(minutes=5),
        id="appointment-reminders",
        replace_existing=True,
    )
    scheduler.start()

    yield

    scheduler.shutdown(wait=False)


app = FastAPI(title="DigiGrowth OS", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(crm.router, prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(sms.router, prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(sms.webhook_router)         # public — Twilio SMS webhooks
app.include_router(email_inbox.router, prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(dialer_webhooks.router)     # public — Twilio voice webhooks
app.include_router(dialer.router, prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(dashboard.router, prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(agents.router, prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(settings.router,   prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(analytics.router,  prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(finances.router,   prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(sops.router,       prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(approvals.router,  prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(newsletter_queue.router, prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(tags.router,       prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(appointments.router, prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(public_sops.router)  # no auth — readable by team
app.include_router(legal.router)        # no auth — Twilio campaign registration
app.include_router(newsletter.router, prefix="/api")  # no auth — clicked from an email link

# Serve built frontend (populated by Railway build step)
frontend_dist = os.path.join(os.path.dirname(__file__), "frontend/dist")
if os.path.isdir(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")
