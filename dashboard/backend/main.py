import os
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles

from db import get_pool
from routers import crm

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_pool()
    yield


app = FastAPI(title="DigiGrowth OS", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(crm.router, prefix="/api", dependencies=[Depends(require_auth)])

# Serve built frontend (populated by Railway build step)
frontend_dist = os.path.join(os.path.dirname(__file__), "../frontend/dist")
if os.path.isdir(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")
