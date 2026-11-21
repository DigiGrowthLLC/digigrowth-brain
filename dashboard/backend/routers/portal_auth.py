"""Client portal email-code login (public, no dashboard auth). See portal_links.py.

GET  /portal-auth/{slug}                   -> {name} for the login screen (404 if unknown)
POST /portal-auth/{slug}/request {email}   -> emails a 6-digit code if the address is allowed
POST /portal-auth/{slug}/verify {email, code} -> {token}; the browser keeps it per slug
GET  /portal-auth/by-token/{token}         -> {slug, portal_url}; moves old /portal/<token> links over

Codes are stored hashed, expire after 15 minutes, allow 5 wrong tries, and a
portal can request at most 5 codes per 15 minutes (per email) so the business
mailbox can't be used to spam anyone. The request answer is the same whether
or not the email is on file, so the endpoint can't be used to find out who a
clinic's contacts are.
"""
import asyncio
import hashlib
import hmac
import secrets

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import integrations
import portal_links
from db import get_pool

router = APIRouter(prefix="/portal-auth")

CODE_TTL_MIN = 15
MAX_TRIES = 5
MAX_REQUESTS_PER_WINDOW = 5


class CodeRequest(BaseModel):
    email: str


class CodeVerify(BaseModel):
    email: str
    code: str


def _hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


async def _client_by_slug(conn, slug: str):
    return await conn.fetchrow(
        "SELECT id, name, contact_name, portal_token FROM clients "
        "WHERE portal_slug = $1 AND token_revoked_at IS NULL", (slug or "").lower())


@router.get("/by-token/{token}")
async def by_token(token: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM clients WHERE portal_token = $1 AND token_revoked_at IS NULL", token)
        if not row:
            raise HTTPException(status_code=404, detail="Invalid or revoked portal link")
        slug = await portal_links.ensure_slug(conn, row["id"])
    return {"slug": slug, "portal_url": portal_links.portal_url(slug)}


@router.get("/{slug}")
async def portal_info(slug: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        c = await _client_by_slug(conn, slug)
    if not c:
        raise HTTPException(status_code=404, detail="Portal not found")
    return {"name": c["name"]}


@router.post("/{slug}/request")
async def request_code(slug: str, body: CodeRequest):
    email = (body.email or "").strip().lower()
    if "@" not in email or len(email) > 200:
        raise HTTPException(status_code=400, detail="Enter a valid email address")
    pool = await get_pool()
    async with pool.acquire() as conn:
        c = await _client_by_slug(conn, slug)
        if not c:
            raise HTTPException(status_code=404, detail="Portal not found")
        recent = await conn.fetchval(
            "SELECT count(*) FROM client_portal_login_codes WHERE client_id = $1 AND email = $2 "
            "AND created_at > now() - make_interval(mins => $3)", c["id"], email, CODE_TTL_MIN)
        if recent >= MAX_REQUESTS_PER_WINDOW:
            raise HTTPException(status_code=429, detail="Too many codes requested. Try again in 15 minutes.")
        allowed = email in await portal_links.allowed_emails(conn, c["id"])
        if allowed:
            code = f"{secrets.randbelow(1_000_000):06d}"
            await conn.execute(
                "INSERT INTO client_portal_login_codes (client_id, email, code_hash, expires_at) "
                "VALUES ($1, $2, $3, now() + make_interval(mins => $4))",
                c["id"], email, _hash(code), CODE_TTL_MIN)
        else:
            print(f"[portal-auth] login code asked for {c['name']} by an email not on file")
    if allowed:
        subject = f"{code} is your {c['name']} portal code"
        text = (
            f"Hi,\n\nYour login code for the {c['name']} client portal is:\n\n    {code}\n\n"
            f"It works for {CODE_TTL_MIN} minutes. Your portal: {portal_links.portal_url(slug)}\n\n"
            "If you didn't ask for this, you can ignore this email.\n\nDigiGrowth"
        )
        # Sent right away (not through the 10-minute-spaced outbox): the
        # client is waiting on the login screen for it.
        result = await asyncio.to_thread(integrations._gmail_send_now, email, subject, text, False, True)
        if not str(result).startswith("Sent email"):
            print(f"[portal-auth] code email failed for client {c['id']}: {result}")
            raise HTTPException(status_code=502, detail="Couldn't send the code right now. Please try again.")
    return {"ok": True}


@router.post("/{slug}/verify")
async def verify_code(slug: str, body: CodeVerify):
    email = (body.email or "").strip().lower()
    code = "".join(ch for ch in (body.code or "") if ch.isdigit())
    pool = await get_pool()
    async with pool.acquire() as conn:
        c = await _client_by_slug(conn, slug)
        if not c:
            raise HTTPException(status_code=404, detail="Portal not found")
        row = await conn.fetchrow(
            "SELECT id, code_hash, attempts FROM client_portal_login_codes "
            "WHERE client_id = $1 AND email = $2 AND used_at IS NULL AND expires_at > now() "
            "ORDER BY id DESC LIMIT 1", c["id"], email)
        if not row or row["attempts"] >= MAX_TRIES:
            raise HTTPException(status_code=400, detail="That code expired. Request a new one.")
        if not hmac.compare_digest(row["code_hash"], _hash(code)):
            await conn.execute("UPDATE client_portal_login_codes SET attempts = attempts + 1 WHERE id = $1", row["id"])
            left = MAX_TRIES - row["attempts"] - 1
            raise HTTPException(status_code=400, detail=f"Wrong code. {left} tries left." if left else "Wrong code. Request a new one.")
        await conn.execute("UPDATE client_portal_login_codes SET used_at = now() WHERE id = $1", row["id"])
    return {"token": c["portal_token"]}
