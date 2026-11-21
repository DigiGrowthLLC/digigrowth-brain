"""Client portal addresses (2026-11-21).

Every client portal lives at a readable address on our own domain,
https://portal.digigrowthllc.com/<portal_slug> (e.g. /boulder-body-solutions),
instead of the old /portal/<random token> link on the Railway URL. Because a
readable name can be guessed, the portal asks for an email login code
(routers/portal_auth.py) before showing anything; the token is what the
browser holds after a successful login and is still what every /portal-api
call is scoped by.

Who can log in: the client's own email, the anchor contact's email (the
prospect the deal came from) and any extra addresses in clients.portal_emails.

Links that go out to clients use portal_url() (login required). The OS's
"Open portal" buttons use portal_admin_url(), which carries the token in the
#fragment (never sent to a server) so Dylan skips the login.
"""
import os
import re

PORTAL_BASE = (os.environ.get("PORTAL_URL") or "https://portal.digigrowthllc.com").rstrip("/")
OS_BASE = (os.environ.get("OS_URL") or "https://os.digigrowthllc.com").rstrip("/")

# First path segments the backend itself serves on every host (public
# routers + SPA assets). A portal slug equal to one of these would be
# swallowed by that route instead of reaching the portal page.
RESERVED_SLUGS = {
    "api", "assets", "portal", "portal-api", "portal-auth", "team", "login", "logout",
    "docs", "redoc", "openapi.json", "privacy", "terms", "book", "booking", "book-asset",
    "booking-stripe-done", "lp", "report", "watch", "watch-videos", "webhooks", "track",
    "dialer", "sms", "public", "voice-agent", "clients", "landing-pages", "content-analytics",
    "favicon.ico", "robots.txt",
}


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s[:60].strip("-") or "client"


def valid_slug(slug: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,58}[a-z0-9])?", slug or "")) and slug not in RESERVED_SLUGS


async def unique_slug(conn, name: str, exclude_client_id: int | None = None) -> str:
    base = slugify(name)
    if base in RESERVED_SLUGS:
        base = f"{base}-clinic"
    slug, n = base, 2
    while await conn.fetchval(
        "SELECT 1 FROM clients WHERE portal_slug = $1 AND id IS DISTINCT FROM $2", slug, exclude_client_id
    ):
        slug, n = f"{base}-{n}", n + 1
    return slug


async def ensure_slug(conn, client_id: int) -> str:
    row = await conn.fetchrow("SELECT name, portal_slug FROM clients WHERE id = $1", client_id)
    if not row:
        return ""
    if row["portal_slug"]:
        return row["portal_slug"]
    slug = await unique_slug(conn, row["name"], client_id)
    await conn.execute("UPDATE clients SET portal_slug = $2 WHERE id = $1", client_id, slug)
    return slug


async def backfill_slugs(conn) -> None:
    for r in await conn.fetch("SELECT id FROM clients WHERE portal_slug IS NULL ORDER BY id"):
        await ensure_slug(conn, r["id"])


def portal_url(slug: str) -> str:
    return f"{PORTAL_BASE}/{slug}" if slug else ""


def portal_admin_url(slug: str, token: str) -> str:
    return f"{PORTAL_BASE}/{slug}#k={token}" if slug and token else ""


def decorate(d: dict) -> dict:
    """Adds portal_url / portal_admin_url to a clients row dict."""
    d["portal_url"] = portal_url(d.get("portal_slug") or "")
    d["portal_admin_url"] = portal_admin_url(d.get("portal_slug") or "", d.get("portal_token") or "")
    return d


async def link_for_client(conn, client_id: int) -> str:
    return portal_url(await ensure_slug(conn, client_id))


async def allowed_emails(conn, client_id: int) -> set[str]:
    row = await conn.fetchrow(
        """SELECT c.email, c.portal_emails,
                  (SELECT email FROM contacts WHERE client_id = c.id AND is_client_anchor LIMIT 1) AS anchor_email
           FROM clients c WHERE c.id = $1""", client_id)
    if not row:
        return set()
    out = {row["email"], row["anchor_email"], *(row["portal_emails"] or [])}
    return {e.strip().lower() for e in out if e and "@" in e}
