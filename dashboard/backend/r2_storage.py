"""Cloudflare R2 (S3-compatible) object storage for client-uploaded files
(the portal's Upload tab — routers/client_portal.py's /uploads endpoints).

Files never pass through this backend's own memory/disk: the browser asks
this module for a short-lived presigned PUT URL, uploads directly to R2 with
it, then tells the backend "done" so the row can be recorded in
client_uploads. Downloads work the same way in reverse (a presigned GET URL).
This keeps Railway's own storage/bandwidth completely out of the picture,
regardless of how much clients upload.

Requires these in the shared `digigrowth` Doppler vault (not set yet as of
this module's introduction — every function below raises a clear
RuntimeError until they are):
    R2_ACCOUNT_ID
    R2_ACCESS_KEY_ID
    R2_SECRET_ACCESS_KEY
    R2_BUCKET_NAME

Setup (one-time, in the Cloudflare dashboard):
    1. cloudflare.com -> sign up (free) -> R2 Object Storage
    2. Create bucket, e.g. "digigrowth-client-uploads"
    3. R2 -> Manage API Tokens -> Create API token (Object Read & Write,
       scoped to that bucket)
    4. Copy the Account ID, Access Key ID, and Secret Access Key it gives
       you into Doppler under the four names above (project `digigrowth`,
       config `prd`), then redeploy.
"""

import os
import uuid

import boto3
from botocore.client import Config

_PRESIGN_EXPIRES_SECONDS = 600  # 10 minutes — plenty for a browser to start an upload/download


def _configured() -> bool:
    return all(
        os.environ.get(k)
        for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME")
    )


def _client():
    if not _configured():
        raise RuntimeError(
            "Cloudflare R2 isn't configured yet — set R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, "
            "R2_SECRET_ACCESS_KEY, and R2_BUCKET_NAME in Doppler (see r2_storage.py's module "
            "docstring for setup steps)."
        )
    account_id = os.environ["R2_ACCOUNT_ID"]
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def is_configured() -> bool:
    """Lets the portal's Upload tab show a friendly "not connected yet"
    state instead of erroring, same pattern as this codebase's other
    not-yet-live integrations (Meta Ads, per-client Calendly, etc.)."""
    return _configured()


def make_key(client_id: int, file_name: str) -> str:
    """clients/<client_id>/<uuid>-<safe original filename> — the uuid
    prefix guarantees uniqueness (two people uploading "logo.png" never
    collide) while keeping the original name readable in the R2 console."""
    safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in file_name.strip())[:180] or "file"
    return f"clients/{client_id}/{uuid.uuid4().hex}-{safe_name}"


def presign_put(key: str, content_type: str) -> str:
    bucket = os.environ["R2_BUCKET_NAME"]
    return _client().generate_presigned_url(
        "put_object",
        Params={"Bucket": bucket, "Key": key, "ContentType": content_type or "application/octet-stream"},
        ExpiresIn=_PRESIGN_EXPIRES_SECONDS,
    )


def presign_get(key: str, download_filename: str | None = None) -> str:
    bucket = os.environ["R2_BUCKET_NAME"]
    params = {"Bucket": bucket, "Key": key}
    if download_filename:
        params["ResponseContentDisposition"] = f'attachment; filename="{download_filename}"'
    return _client().generate_presigned_url("get_object", Params=params, ExpiresIn=_PRESIGN_EXPIRES_SECONDS)


def delete_object(key: str) -> None:
    bucket = os.environ["R2_BUCKET_NAME"]
    _client().delete_object(Bucket=bucket, Key=key)


def get_object_bytes(key: str) -> bytes:
    """Reads one object fully into memory — used by context_gen.py to
    transiently extract text from a client's uploaded PDFs/docx (business
    info, resource libraries, etc.) when drafting a response_ai_context
    suggestion. Nothing is written to disk; the bytes are discarded after
    text extraction. Only sensible for the modest-sized documents this is
    used for, not video — see iter_object_chunks for large-file streaming."""
    bucket = os.environ["R2_BUCKET_NAME"]
    return _client().get_object(Bucket=bucket, Key=key)["Body"].read()


def iter_object_chunks(key: str, chunk_size: int = 1024 * 1024):
    """Streams one object's bytes in chunks — used by the admin "download all
    as a zip" endpoint (routers/clients.py) to build a zip archive on the fly
    without ever buffering a whole file (let alone a whole client's uploads)
    in memory. Still never touches disk/Postgres — this is a transient
    in-memory stream from R2 straight into the HTTP response."""
    bucket = os.environ["R2_BUCKET_NAME"]
    body = _client().get_object(Bucket=bucket, Key=key)["Body"]
    for chunk in body.iter_chunks(chunk_size=chunk_size):
        yield chunk


def upload_file(path: str, key: str, content_type: str) -> None:
    """Streams a local file to R2 (multipart under the hood for big files) —
    used by outreach_video.py to publish server-generated videos without
    ever reading the whole file into memory."""
    bucket = os.environ["R2_BUCKET_NAME"]
    _client().upload_file(path, bucket, key, ExtraArgs={"ContentType": content_type})


def download_file(key: str, path: str) -> None:
    """Streams one object from R2 to a local path (outreach_video.py's
    headcam master clip cache)."""
    bucket = os.environ["R2_BUCKET_NAME"]
    _client().download_file(bucket, key, path)
