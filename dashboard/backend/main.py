import asyncio
import os
import secrets
import sys
from contextlib import asynccontextmanager

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles

import integrations
from db import get_pool
from routers import crm, sms, dialer, dialer_webhooks, dashboard, agents, settings, analytics, finances, sops, public_sops, legal

security = HTTPBasic()
DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "changeme")


async def _trigger_agent_skill(agent_id: str, message: str, timeout: int = 300) -> None:
    """Call the agent chat endpoint from the scheduler (self-call via localhost).
    Retries once after 60s if the first attempt fails.
    History is self-healed by the chat endpoint before every run.
    """
    port = os.environ.get("PORT", "8000")
    url = f"http://localhost:{port}/api/agents/{agent_id}/chat"

    async def _run() -> bool:
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST", url,
                    auth=("admin", DASHBOARD_PASSWORD),
                    json={"message": message, "mode": "auto"},
                ) as resp:
                    async for line in resp.aiter_lines():
                        if '"type": "error"' in line:
                            print(f"[cron] {agent_id} stream error: {line[:200]}")
                            return False
            return True
        except Exception as exc:
            print(f"[cron] {agent_id} / '{message}' attempt failed: {exc}")
            return False

    success = await _run()
    if not success:
        print(f"[cron] {agent_id} / '{message}' — retrying in 60s")
        await asyncio.sleep(60)
        ok = await _run()
        if not ok:
            print(f"[cron] {agent_id} / '{message}' — retry also failed, will try again next scheduled run")


def require_auth(credentials: HTTPBasicCredentials = Depends(security)):
    ok = secrets.compare_digest(credentials.password.encode(), DASHBOARD_PASSWORD.encode())
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


async def _run_daily_briefing() -> None:
    """Run the daily briefing agent, then pin the brief as the final chat message."""
    import pathlib, json as _json
    await _trigger_agent_skill("executive-assistant", "Run the daily briefing", timeout=600)
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, integrations.save_daily_brief_pdf)
    print(f"[cron] daily-brief PDF: {result}")

    # Pin the saved .md as the last chat message so it's always visible regardless
    # of how many tool-call rows the agent run generated (chat loads last 20 rows).
    reports_dir = pathlib.Path("/repo/executive-assistant/reports")
    files = sorted(reports_dir.glob("daily-briefing-*.md"), reverse=True)
    if not files:
        return
    brief_text = files[0].read_text(encoding="utf-8").strip()
    if not brief_text:
        return
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO agent_chats (agent_id, role, content) VALUES ($1, $2, $3)",
                "executive-assistant",
                "assistant",
                _json.dumps([{"type": "text", "text": brief_text}]),
            )
        print("[cron] daily-brief pinned to EA chat", flush=True)
    except Exception as e:
        print(f"[cron] daily-brief chat pin failed: {e}", flush=True)


async def _run_leadgen() -> None:
    """Check if a dialing session ran today, then launch the leadgen script."""
    import pathlib
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
            import json as _json
            await conn.execute(
                "INSERT INTO agent_chats (agent_id, role, content) VALUES ($1, $2, $3)",
                "executive-assistant",
                "assistant",
                _json.dumps([{"type": "text", "text": msg}]),
            )
    except Exception as e:
        print(f"[cron] leadgen chat notify failed: {e}", flush=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_pool()

    scheduler = AsyncIOScheduler()
    eastern = "America/New_York"
    scheduler.add_job(
        _trigger_agent_skill,
        CronTrigger(hour=6, minute=0, timezone=eastern),
        args=["executive-assistant", "Run the sheets digest"],
        id="sheets-digest-daily",
        replace_existing=True,
    )
    scheduler.add_job(
        _run_daily_briefing,
        CronTrigger(hour=6, minute=1, timezone=eastern),
        id="daily-briefing-daily",
        replace_existing=True,
    )
    scheduler.add_job(
        _run_leadgen,
        CronTrigger(hour=20, minute=0, timezone=eastern, day_of_week="mon-fri"),
        id="leadgen-daily",
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
app.include_router(dialer_webhooks.router)     # public — Twilio voice webhooks
app.include_router(dialer.router, prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(dashboard.router, prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(agents.router, prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(settings.router,   prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(analytics.router,  prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(finances.router,   prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(sops.router,       prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(public_sops.router)  # no auth — readable by team
app.include_router(legal.router)        # no auth — Twilio campaign registration

# Serve built frontend (populated by Railway build step)
frontend_dist = os.path.join(os.path.dirname(__file__), "frontend/dist")
if os.path.isdir(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")
