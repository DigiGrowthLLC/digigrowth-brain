import base64
import json
import os
import time
import urllib.error
import urllib.request
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from db import get_pool

router = APIRouter()

_COLS = "id, title, content, category, visibility, sort_order, doc_type, file_name, file_type, file_size, github_path, created_at, updated_at"
_GITHUB_REPO = os.environ.get("GITHUB_REPO", "dylangroenendijk-sys/digigrowth-brain")
_MAX_UPLOAD_BYTES = 95 * 1024 * 1024  # 95 MB — under GitHub's 100 MB API limit


def _gh_push(path: str, data: bytes, message: str) -> None:
    token = os.environ.get("GIT_TOKEN", "")
    if not token:
        raise HTTPException(status_code=500, detail="GIT_TOKEN not configured")
    url = f"https://api.github.com/repos/{_GITHUB_REPO}/contents/{path}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }
    sha = None
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            sha = json.loads(resp.read()).get("sha")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise HTTPException(status_code=502, detail=f"GitHub error: {e}")
    payload: dict = {"message": message, "content": base64.b64encode(data).decode()}
    if sha:
        payload["sha"] = sha
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=60):
            pass
    except urllib.error.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"GitHub push failed: {e}")


def _gh_fetch(path: str) -> bytes:
    token = os.environ.get("GIT_TOKEN", "")
    url = f"https://api.github.com/repos/{_GITHUB_REPO}/contents/{path}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
        if result.get("content"):
            return base64.b64decode(result["content"].replace("\n", ""))
        if result.get("download_url"):
            dl_req = urllib.request.Request(result["download_url"], headers={"Authorization": f"token {token}"})
            with urllib.request.urlopen(dl_req, timeout=60) as resp:
                return resp.read()
        raise HTTPException(status_code=404, detail="File content unavailable")
    except urllib.error.HTTPError as e:
        raise HTTPException(status_code=404 if e.code == 404 else 502, detail=f"GitHub error: {e}")


class SOPCreate(BaseModel):
    title: str
    content: str = ""
    category: str = "General"
    visibility: str = "private"
    sort_order: int = 0
    doc_type: str = "sop"


class SOPUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    visibility: Optional[str] = None
    sort_order: Optional[int] = None
    doc_type: Optional[str] = None


@router.get("/sops")
async def list_sops(category: Optional[str] = Query(None), doc_type: Optional[str] = Query(None)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        if category and doc_type:
            rows = await conn.fetch(
                f"SELECT {_COLS} FROM sops WHERE category = $1 AND doc_type = $2 ORDER BY category, sort_order, id",
                category, doc_type,
            )
        elif category:
            rows = await conn.fetch(
                f"SELECT {_COLS} FROM sops WHERE category = $1 ORDER BY category, sort_order, id",
                category,
            )
        elif doc_type:
            rows = await conn.fetch(
                f"SELECT {_COLS} FROM sops WHERE doc_type = $1 ORDER BY category, sort_order, id",
                doc_type,
            )
        else:
            rows = await conn.fetch(
                f"SELECT {_COLS} FROM sops ORDER BY category, sort_order, id"
            )
    return [dict(r) for r in rows]


@router.post("/sops")
async def create_sop(body: SOPCreate):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""INSERT INTO sops (title, content, category, visibility, sort_order, doc_type)
               VALUES ($1, $2, $3, $4, $5, $6) RETURNING {_COLS}""",
            body.title, body.content, body.category, body.visibility, body.sort_order, body.doc_type,
        )
    return dict(row)


@router.patch("/sops/{sop_id}")
async def update_sop(sop_id: int, body: SOPUpdate):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    fields = ", ".join(f"{k} = ${i + 2}" for i, k in enumerate(updates))
    values = list(updates.values())

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"UPDATE sops SET {fields}, updated_at = now() WHERE id = $1 RETURNING *",
            sop_id, *values,
        )
    if not row:
        raise HTTPException(status_code=404, detail="SOP not found")
    return dict(row)


@router.delete("/sops/{sop_id}")
async def delete_sop(sop_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM sops WHERE id = $1", sop_id)
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="SOP not found")
    return {"ok": True}


@router.post("/sops/upload")
async def upload_file(
    file: UploadFile = File(...),
    title: str = Form(""),
    category: str = Form("General"),
    doc_type: str = Form("sop"),
    visibility: str = Form("private"),
):
    data = await file.read()
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 95 MB limit")

    file_name = file.filename or "untitled"
    file_type = file.content_type or "application/octet-stream"
    file_size = len(data)
    display_title = title.strip() or file_name

    # Push to GitHub — never store binary in Postgres
    safe_name = "".join(c if c.isalnum() or c in ".-_" else "_" for c in file_name)
    github_path = f"uploads/{doc_type}/{int(time.time())}_{safe_name}"
    _gh_push(github_path, data, f"Upload: {display_title}")

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""INSERT INTO sops
                (title, content, category, visibility, sort_order, doc_type, file_name, file_type, file_size, github_path)
                VALUES ($1, '', $2, $3, 0, $4, $5, $6, $7, $8)
                RETURNING {_COLS}""",
            display_title, category, visibility, doc_type, file_name, file_type, file_size, github_path,
        )
    return dict(row)


@router.get("/sops/{sop_id}/file")
async def get_file(sop_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT file_name, file_type, github_path FROM sops WHERE id = $1", sop_id
        )
    if not row or not row["github_path"]:
        raise HTTPException(status_code=404, detail="No file attached")
    content = _gh_fetch(row["github_path"])
    return Response(
        content=content,
        media_type=row["file_type"] or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{row["file_name"]}"'},
    )
