"""
Sales tracking endpoints (see sales_tracking.py).

Authenticated (/api):
  GET  /sales/blueprint-jobs/worker/next         the PC worker claims the next blueprint run
  POST /sales/blueprint-jobs/{id}/worker/result  the worker reports it (ok/slug/url/notes/error)
  POST /sales/blueprint-jobs/{id}/retry          Appointments' Retry on a failed blueprint
  POST /sales/fireflies/sync                     pull recent Fireflies transcripts now

Public:
  POST /webhooks/fireflies   Fireflies' "Transcription completed" webhook
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

import sales_tracking

admin_router = APIRouter()
router = APIRouter()


@admin_router.get("/sales/blueprint-jobs/worker/next")
async def worker_next_job():
    return {"job": await sales_tracking.claim_next_job()}


@admin_router.post("/sales/blueprint-jobs/{job_id}/worker/result")
async def worker_job_result(job_id: int, payload: dict):
    row = await sales_tracking.finish_job(job_id, payload or {})
    if not row:
        raise HTTPException(404, "job not found")
    return {"ok": True, "status": row["status"], "url": row["url"]}


@admin_router.post("/sales/blueprint-jobs/{job_id}/retry")
async def retry_blueprint_job(job_id: int):
    row = await sales_tracking.retry_job(job_id)
    if not row:
        raise HTTPException(404, "job not found")
    return {"ok": True, "id": row["id"], "status": row["status"]}


@admin_router.post("/sales/fireflies/sync")
async def fireflies_sync_now():
    return await sales_tracking.sync_fireflies()


@router.post("/webhooks/fireflies", include_in_schema=False)
async def fireflies_webhook(request: Request, background: BackgroundTasks):
    raw = await request.body()
    if not sales_tracking.verify_fireflies_signature(raw, request.headers.get("x-hub-signature")):
        raise HTTPException(401, "bad signature")
    try:
        body = await request.json()
    except Exception:
        body = {}
    meeting_id = body.get("meetingId") or body.get("meeting_id")
    if meeting_id:
        async def _run():
            try:
                await sales_tracking.sync_fireflies_meeting(meeting_id)
            except Exception as e:
                print(f"[sales] Fireflies webhook for {meeting_id} failed: {e}", flush=True)
        background.add_task(_run)
    return {"ok": True}
