import os
import secrets
from contextlib import asynccontextmanager

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles

from db import get_pool
from routers import crm, sms, dialer, dashboard, agents, settings, analytics, finances, sops, public_sops

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
        _trigger_agent_skill,
        CronTrigger(hour=6, minute=1, timezone=eastern),
        args=["executive-assistant", "Run the daily briefing"],
        kwargs={"timeout": 600},
        id="daily-briefing-daily",
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
app.include_router(sms.webhook_router)  # public — Twilio posts here, no auth
app.include_router(dialer.router, prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(dashboard.router, prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(agents.router, prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(settings.router,   prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(analytics.router,  prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(finances.router,   prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(sops.router,       prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(public_sops.router)  # no auth — readable by team

# Serve built frontend (populated by Railway build step)
frontend_dist = os.path.join(os.path.dirname(__file__), "frontend/dist")
if os.path.isdir(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")
