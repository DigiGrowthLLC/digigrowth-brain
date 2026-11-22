"""Client portal email-code login (public, no dashboard auth). See portal_links.py.

GET  /portal-auth/{slug}                   -> {name} for the login screen (404 if unknown)
POST /portal-auth/{slug}/request {email}   -> emails a 6-digit code if the address is allowed
POST /portal-auth/{slug}/verify {email, code} -> {token}; the browser keeps it per slug
GET  /portal-auth/by-token/{token}         -> {slug, portal_url}; moves old /portal/<token> links over

Codes are stored hashed, expire after 15 minutes, allow 5 wrong tries, and a
portal can request at most 5 codes per 15 minutes (per email) so the business
mailbox can't be used to spam anyone. The request answer is the same whether
or not the email is on file, so the endpoint can't be used to find out who a
clinic's contacts are. An email that isn't on file becomes an access request
+ To-Do for Dylan (Allow / Deny), at most 5 pending per portal.
"""
import asyncio
import hashlib
import hmac
import secrets
from datetime import datetime
from zoneinfo import ZoneInfo

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
        allowed = bool(await portal_links.login_check(conn, c["id"], email))
        if allowed:
            code = f"{secrets.randbelow(1_000_000):06d}"
            await conn.execute(
                "INSERT INTO client_portal_login_codes (client_id, email, code_hash, expires_at) "
                "VALUES ($1, $2, $3, now() + make_interval(mins => $4))",
                c["id"], email, _hash(code), CODE_TTL_MIN)
        else:
            await _ask_dylan(conn, c, email)
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


MAX_PENDING_REQUESTS = 5  # per portal, so a bot typing emails can't flood the To-Do list


async def _ask_dylan(conn, c, email: str) -> None:
    """An email that isn't on file: one access request + To-Do (Allow / Deny
    buttons on the To-Do, routers/clients.py). Blocked addresses (denied
    before, or removed by the clinic) are dropped silently."""
    blocked = await conn.fetchval("SELECT portal_blocked_emails FROM clients WHERE id = $1", c["id"]) or []
    if email in blocked:
        print(f"[portal-auth] blocked email tried {c['name']}'s portal")
        return
    if await conn.fetchval(
        "SELECT 1 FROM client_portal_access_requests WHERE client_id = $1 AND email = $2 AND status = 'pending'",
        c["id"], email):
        return
    if await conn.fetchval(
        "SELECT count(*) FROM client_portal_access_requests WHERE client_id = $1 AND status = 'pending'",
        c["id"]) >= MAX_PENDING_REQUESTS:
        print(f"[portal-auth] {c['name']}: too many pending access requests, not adding another")
        return
    req_id = await conn.fetchval(
        "INSERT INTO client_portal_access_requests (client_id, email) VALUES ($1, $2) "
        "ON CONFLICT DO NOTHING RETURNING id", c["id"], email)
    if not req_id:
        return
    known = ", ".join(sorted(await portal_links.allowed_emails(conn, c["id"]))) or "none yet"
    await conn.execute(
        "INSERT INTO todos (text, description, due_date, portal_access_request_id) VALUES ($1, $2, $3, $4)",
        f"{email} wants into {c['name']}'s portal",
        f"{email} asked for a login code, but it isn't on {c['name']}'s login list.\n\n"
        f"Allow: they get an email saying they're in, and can log in from then on.\n"
        f"Deny: nothing is sent and they won't ask again.\n\n"
        f"Current logins: {known}",
        datetime.now(ZoneInfo("America/New_York")).date(), req_id)


async def decide_request(request_id: int, allow: bool) -> dict:
    """Dylan's Allow / Deny on an access request (To-Do buttons + OS card)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        req = await conn.fetchrow(
            "SELECT r.id, r.client_id, r.email, r.status, c.name, c.portal_slug FROM client_portal_access_requests r "
            "JOIN clients c ON c.id = r.client_id WHERE r.id = $1", request_id)
        if not req:
            raise HTTPException(status_code=404, detail="Request not found")
        if req["status"] == "pending":
            if allow:
                await portal_links.add_login(conn, req["client_id"], req["email"])
            else:
                await portal_links.remove_login(conn, req["client_id"], req["email"])
            await conn.execute(
                "UPDATE client_portal_access_requests SET status = $2, decided_at = now() WHERE id = $1",
                request_id, "allowed" if allow else "denied")
        await conn.execute("DELETE FROM todos WHERE portal_access_request_id = $1", request_id)
    if allow and req["status"] == "pending":
        url = portal_links.portal_url(req["portal_slug"] or "")
        text = (
            f"Hi,\n\nYou now have access to the {req['name']} client portal.\n\n"
            f"Open {url} and enter {req['email']} to get your login code.\n\nDigiGrowth"
        )
        result = await asyncio.to_thread(
            integrations._gmail_send_now, req["email"], f"You're in: {req['name']} client portal", text, False, True)
        if not str(result).startswith("Sent email"):
            print(f"[portal-auth] access-approved email failed for request {request_id}: {result}")
    return {"ok": True, "email": req["email"], "status": "allowed" if allow else "denied"}


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
