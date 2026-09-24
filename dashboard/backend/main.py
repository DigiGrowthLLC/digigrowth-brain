import asyncio
import json
import os
import pathlib
import secrets
from contextlib import asynccontextmanager

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

import integrations
import client_email
import email_warmup
import scheduler_registry
from db import get_pool
from pending_approvals_relay import process_pending_approvals, process_pending_cleanup_approval
from routers import crm, sms, sms_sequences, cold_call_scripts, dialer, dialer_webhooks, dashboard, agents, settings, analytics, finances, sops, public_sops, legal, email_inbox, email_tracking, email_identities, approvals, tags, newsletter, newsletter_queue, appointments, campaigns, clients, client_portal, watch, landing_pages, content_tracking, client_marketing, client_finance, client_sms_webhooks, client_voice_webhooks, meta_lead_webhooks, calendly_webhooks, calendly_admin
import call_reminders
import cancel_sequence
import client_appointment_reminders
import client_appointment_sequence
import dm_followup_sequence
import email_handoff_sequence
import email_followup_trigger
import outreach_video
import identity_warmup
import meta_ads
import no_show_sequence
import onboarding_sequence
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

    repo = os.environ.get("GITHUB_REPO", "DigiGrowthLLC/digigrowth-brain")
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


async def _push_file_to_github(rel_path: str, content: str, message: str) -> str:
    """Write a file to GitHub via the REST API (get current SHA, then PUT)."""
    import base64

    repo = os.environ.get("GITHUB_REPO", "DigiGrowthLLC/digigrowth-brain")
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


async def _export_sms_outreach_stats() -> None:
    """Export live SMS outreach stats (7d/30d/all-time) to a git-tracked JSON
    file the daily-briefing cloud routine can read locally, instead of
    calling Railway's API mid-run. That live call has repeatedly failed —
    the routine's sandbox sits behind a network egress proxy that rejects
    outbound connections to Railway before any response comes back, so even
    the curl fallback in the skill's Step 3A-SMS fails the same way an auth
    problem would, just for an unrelated reason. Since Railway can reach its
    own DB and GitHub trivially, it's the one side of this that should do
    the network call — same pattern as _export_newsletter_contacts above."""
    from routers.analytics import outreach as _outreach

    try:
        stats_7d  = await _outreach(days=7)
        stats_30d = await _outreach(days=30)
    except Exception as e:
        print(f"[cron] sms-outreach-export: query failed: {e}", flush=True)
        return

    payload = {
        "period_7d":  stats_7d["sms"]["period"],
        "period_30d": stats_30d["sms"]["period"],
        "all_time":   stats_7d["sms"]["all_time"],
        "exported_at": _today_eastern(),
    }
    content = json.dumps(payload, indent=2)

    local_path = pathlib.Path("/repo/executive-assistant/sms_outreach_snapshot.json")
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_text(content, encoding="utf-8")

    status = await _push_file_to_github(
        "executive-assistant/sms_outreach_snapshot.json", content,
        f"SMS outreach snapshot: {_today_eastern()}",
    )
    print(f"[cron] sms-outreach-export: ({status})", flush=True)


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
    Mon/Fri only, blog is Wednesdays only)."""
    try:
        result = await process_pending_approvals()
        print(f"[cron] {result}", flush=True)
    except Exception as e:
        print(f"[cron] pending-approvals-relay failed: {e}", flush=True)


async def _process_cleanup_approval_relay_job() -> None:
    """Picks up the weekly-cleanup routine's cleanup-<date>.json request file
    from GitHub (see weekly-cleanup/CLAUDE.md 'Posting a Review Card') and
    turns it into a real pending_approvals row + agent_chats card — same
    can't-reach-Railway-directly reason as _process_pending_approvals_job,
    just on its own Sunday-evening schedule since weekly-cleanup doesn't run
    on the daily-briefing's cadence. Runs weekly; no-ops harmlessly if the
    routine found nothing worth flagging that week."""
    try:
        result = await process_pending_cleanup_approval()
        print(f"[cron] {result}", flush=True)
    except Exception as e:
        print(f"[cron] cleanup-approval-relay failed: {e}", flush=True)


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
    scheduler_registry.set_scheduler(scheduler)
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
        _export_sms_outreach_stats,
        CronTrigger(hour=5, minute=50, timezone=eastern),
        id="sms-outreach-export-daily",
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
        _process_cleanup_approval_relay_job,
        CronTrigger(hour=20, minute=20, timezone=eastern, day_of_week="sun"),
        id="cleanup-approval-relay",
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
        client_email.sync_client_email_job,
        IntervalTrigger(seconds=120),
        id="client-email-sync",
        replace_existing=True,
    )
    scheduler.add_job(
        email_warmup.send_due_touches,
        IntervalTrigger(minutes=20),
        id="email-warmup",
        replace_existing=True,
    )
    scheduler.add_job(
        _process_newsletter_queue,
        CronTrigger(minute="*/10", hour="9-17", day_of_week="mon-fri", timezone=eastern),
        id="newsletter-queue-processor",
        replace_existing=True,
    )
    scheduler.add_job(
        reminder_engine.send_due_reminders,
        IntervalTrigger(minutes=5),
        id="appointment-reminders",
        replace_existing=True,
    )
    scheduler.add_job(
        client_appointment_reminders.send_due_reminders,
        IntervalTrigger(minutes=5),
        id="client-appointment-reminders",
        replace_existing=True,
    )
    scheduler.add_job(
        no_show_sequence.send_due_touches,
        IntervalTrigger(minutes=5),
        id="no-show-sequence",
        replace_existing=True,
    )
    scheduler.add_job(
        cancel_sequence.send_due_touches,
        IntervalTrigger(minutes=5),
        id="cancel-sequence",
        replace_existing=True,
    )
    scheduler.add_job(
        client_appointment_sequence.send_due_touches,
        IntervalTrigger(minutes=5),
        id="client-appointment-sequence",
        replace_existing=True,
    )
    scheduler.add_job(
        call_reminders.check_all,
        IntervalTrigger(minutes=5),
        id="call-reminders",
        replace_existing=True,
    )
    scheduler.add_job(
        dm_followup_sequence.send_due_touches,
        IntervalTrigger(minutes=5),
        id="dm-followup-sequence",
        replace_existing=True,
    )
    scheduler.add_job(
        email_handoff_sequence.send_due_touches,
        IntervalTrigger(minutes=5),
        id="email-handoff-sequence",
        replace_existing=True,
    )
    scheduler.add_job(
        email_followup_trigger.send_due_touches,
        IntervalTrigger(minutes=5),
        id="email-followup-trigger",
        replace_existing=True,
    )
    scheduler.add_job(
        outreach_video.process_next,
        IntervalTrigger(minutes=2),
        id="email-handoff-loom-generator",
        replace_existing=True,
    )
    scheduler.add_job(
        identity_warmup.send_due_touches,
        IntervalTrigger(minutes=20),
        id="identity-warmup-touches",
        replace_existing=True,
    )
    scheduler.add_job(
        identity_warmup.send_due_replies,
        IntervalTrigger(minutes=10),
        id="identity-warmup-replies",
        replace_existing=True,
    )
    scheduler.add_job(
        onboarding_sequence.send_followup_touches,
        CronTrigger(hour=8, minute=0, timezone=eastern),
        id="onboarding-followup",
        replace_existing=True,
    )
    scheduler.add_job(
        meta_ads.sync_meta_ad_stats,
        CronTrigger(hour=5, minute=0, timezone=eastern),
        id="sync_meta_ad_stats",
        replace_existing=True,
    )
    scheduler.start()

    yield

    scheduler.shutdown(wait=False)


app = FastAPI(title="DigiGrowth OS", lifespan=lifespan)

@app.middleware("http")
async def watch_host_router(request, call_next):
    """The branded video host (loom.<domain>, routers/watch.py PUBLIC_VIDEO_BASE) only serves
    outreach videos: /<slug> -> /watch/<slug>, /<slug>/file -> the file,
    /track/view-event for the page's beacons, and a no-index robots.txt.
    Everything else on that host (dashboard, /api) is a 404, so the branded
    video domain never exposes the internal app."""
    from fastapi.responses import PlainTextResponse
    from routers.watch import WATCH_HOST

    host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").split(":")[0].lower()
    if not WATCH_HOST or host != WATCH_HOST:
        return await call_next(request)

    path = request.url.path
    if path == "/robots.txt":
        return PlainTextResponse("User-agent: *\nDisallow: /\n")
    if path == "/track/view-event":
        return await call_next(request)
    parts = [p for p in path.split("/") if p]
    if len(parts) == 2 and parts[0] == "unsubscribe":
        # Outreach opt-out link (email_handoff_sequence._unsubscribe_url)
        new_path = f"/api/email/unsubscribe/{parts[1]}"
        request.scope["path"] = new_path
        request.scope["raw_path"] = new_path.encode()
        return await call_next(request)
    if len(parts) == 1 or (len(parts) == 2 and parts[1] == "file"):
        new_path = "/watch/" + "/".join(parts)
        request.scope["path"] = new_path
        request.scope["raw_path"] = new_path.encode()
        return await call_next(request)
    return PlainTextResponse("Not found", status_code=404)


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
app.include_router(email_identities.router, prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(dialer_webhooks.router)     # public — Twilio voice webhooks
app.include_router(dialer.router, prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(sms_sequences.router, prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(cold_call_scripts.router, prefix="/api", dependencies=[Depends(require_auth)])
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
app.include_router(campaigns.router,  prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(clients.router,    prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(watch.admin_router, prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(watch.router)       # no auth — clicked from a texted link
app.include_router(landing_pages.admin_router, prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(landing_pages.router)  # no auth — clicked from a texted link
app.include_router(content_tracking.admin_router, prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(content_tracking.router)  # no auth — hit via sendBeacon from the public website and /watch pages
app.include_router(public_sops.router)  # no auth — readable by team
app.include_router(legal.router)        # no auth — Twilio campaign registration
app.include_router(newsletter.router, prefix="/api")  # no auth — clicked from an email link
app.include_router(email_tracking.router, prefix="/api")  # no auth — pixel + unsubscribe links, clicked from outreach emails
app.include_router(client_portal.router)  # no auth — client-facing, scoped by unguessable token
app.include_router(client_marketing.router, prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(client_finance.router, prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(client_sms_webhooks.router)  # no auth — Twilio webhooks for each client's own number
app.include_router(client_voice_webhooks.router)  # no auth — Twilio voice webhooks for the client portal's "Call Now" button
app.include_router(meta_lead_webhooks.router)  # no auth — Meta's own webhook protocol, verified via HMAC signature + verify-token handshake instead
app.include_router(calendly_webhooks.router)  # no auth — Calendly's own webhook protocol, verified via HMAC signature instead
app.include_router(calendly_admin.router, prefix="/api", dependencies=[Depends(require_auth)])

# Serve built frontend (populated by Railway build step). Hashed JS/CSS/image
# assets are served directly from /assets; everything else falls back to
# index.html so react-router can handle deep-links client-side (/team,
# /portal/:token, etc.) — StaticFiles(html=True) alone only serves index.html
# for the bare "/", not for arbitrary sub-paths, so a direct hit or refresh
# on any client-side route 404'd before this fallback existed.
frontend_dist = os.path.join(os.path.dirname(__file__), "frontend/dist")
if os.path.isdir(frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        return FileResponse(os.path.join(frontend_dist, "index.html"))
