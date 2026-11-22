"""Client portal addresses (2026-11-21).

Every client portal lives at a readable address on our own domain,
https://portal.digigrowthllc.com/<portal_slug> (e.g. /boulder-body-solutions),
instead of the old /portal/<random token> link on the Railway URL. Because a
readable name can be guessed, the portal asks for an email login code
(routers/portal_auth.py) before showing anything; the token is what the
browser holds after a successful login and is still what every /portal-api
call is scoped by.

Who can log in: see the block above allowed_emails() below (client + main
contact emails, every email we know for the prospect, added logins, the
clinic's own domain; anyone else asks Dylan through a To-Do).

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


# Who can log in (2026-11-21, v2). A prospect often writes from one address
# and books from another, and a clinic usually has more than one person
# (owner + office manager), so logins come from four places:
#   1. the client record's email + the anchor contact's email (fixed);
#   2. every address we already know for the anchor contact: the email they
#      typed on any booking with Dylan (sales / onboarding / launch call) and
#      every email-thread address (outreach sent to them, replies from them);
#   3. clients.portal_emails: added by Dylan (OS), by the client (portal ->
#      Team access) or by Dylan's Allow on an access-request To-Do;
#   4. any address on the clinic's own domain (website / email / funnel
#      domain), never a free mailbox provider.
# clients.portal_blocked_emails overrides 2-4 (a Deny, or a teammate the
# client removed). An address not covered asks Dylan through a To-Do
# (routers/portal_auth.py -> client_portal_access_requests).

FREE_EMAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "yahoo.com", "ymail.com", "rocketmail.com", "hotmail.com",
    "outlook.com", "live.com", "msn.com", "aol.com", "icloud.com", "me.com", "mac.com",
    "comcast.net", "att.net", "sbcglobal.net", "verizon.net", "cox.net", "charter.net",
    "bellsouth.net", "earthlink.net", "protonmail.com", "proton.me", "gmx.com", "mail.com",
    "zoho.com", "yandex.com", "hey.com", "fastmail.com", "duck.com",
    "digigrowthllc.com",  # ours, never a clinic's
}


def norm_email(e: str | None) -> str:
    e = (e or "").strip().lower()
    return e if "@" in e and " " not in e and len(e) <= 200 else ""


def _domain_of(e: str) -> str:
    return e.rsplit("@", 1)[-1] if "@" in e else ""


def _host(url: str | None) -> str:
    h = re.sub(r"^[a-z]+://", "", (url or "").strip().lower()).split("/")[0].split(":")[0].split("?")[0]
    h = re.sub(r"^www\.", "", h)
    return h if "." in h else ""


async def _anchor(conn, client_id: int):
    return await conn.fetchrow(
        "SELECT id, email, website FROM contacts WHERE client_id = $1 AND is_client_anchor LIMIT 1", client_id)


async def known_emails(conn, client_id: int) -> dict[str, str]:
    """email -> where it came from (sources 1-3 above, blocked ones left out)."""
    c = await conn.fetchrow(
        "SELECT email, portal_emails, portal_blocked_emails FROM clients WHERE id = $1", client_id)
    if not c:
        return {}
    blocked = {norm_email(e) for e in (c["portal_blocked_emails"] or [])}
    out: dict[str, str] = {}

    def add(e, source, fixed=False):
        e = norm_email(e)
        if e and e not in out and (fixed or e not in blocked):
            out[e] = source

    add(c["email"], "Client email", fixed=True)
    anchor = await _anchor(conn, client_id)
    if anchor:
        add(anchor["email"], "Main contact", fixed=True)
        for r in await conn.fetch(
            "SELECT DISTINCT lower(trim(prospect_email)) AS e FROM appointment_reminders "
            "WHERE contact_id = $1 AND coalesce(prospect_email, '') <> ''", anchor["id"]):
            add(r["e"], "Booked a call with this email")
        for r in await conn.fetch(
            "SELECT DISTINCT lower(trim(email)) AS e FROM email_conversations WHERE contact_id = $1", anchor["id"]):
            add(r["e"], "Emailed with us")
    for e in c["portal_emails"] or []:
        add(e, "Added login")
    return out


async def clinic_domains(conn, client_id: int) -> list[str]:
    c = await conn.fetchrow("SELECT email FROM clients WHERE id = $1", client_id)
    anchor = await _anchor(conn, client_id)
    mk = await conn.fetchrow(
        "SELECT funnel_domain, booking_domain FROM client_marketing_config WHERE client_id = $1", client_id)
    found = set()
    for e in (c["email"] if c else None, anchor["email"] if anchor else None):
        d = _domain_of(norm_email(e))
        if d:
            found.add(d)
    if anchor:
        found.add(_host(anchor["website"]))
    for col in ("funnel_domain", "booking_domain"):
        h = _host(mk[col]) if mk else ""
        found.add(re.sub(r"^(go|book|booking|lp)\.", "", h))
    return sorted(d for d in found if d and d not in FREE_EMAIL_DOMAINS)


async def login_check(conn, client_id: int, email: str) -> str | None:
    """Why this email may log in (a source label), or None."""
    email = norm_email(email)
    if not email:
        return None
    known = await known_emails(conn, client_id)
    if email in known:
        return known[email]
    blocked = await conn.fetchval("SELECT portal_blocked_emails FROM clients WHERE id = $1", client_id) or []
    if email in {norm_email(e) for e in blocked}:
        return None
    d = _domain_of(email)
    if d in await clinic_domains(conn, client_id):
        return f"Clinic email domain (@{d})"
    return None


async def allowed_emails(conn, client_id: int) -> set[str]:
    """The listed addresses (sources 1-3). Domain logins are checked by login_check()."""
    return set(await known_emails(conn, client_id))


async def add_login(conn, client_id: int, email: str) -> None:
    email = norm_email(email)
    if not email:
        return
    await conn.execute(
        """UPDATE clients SET
               portal_emails = (SELECT array_agg(DISTINCT x ORDER BY x) FROM unnest(coalesce(portal_emails, '{}') || ARRAY[$2]) x),
               portal_blocked_emails = array_remove(coalesce(portal_blocked_emails, '{}'), $2),
               updated_at = now()
           WHERE id = $1""", client_id, email)


async def remove_login(conn, client_id: int, email: str) -> None:
    """Drops an added login and blocks it, so a derived source or the clinic
    domain doesn't quietly let it back in."""
    email = norm_email(email)
    if not email:
        return
    await conn.execute(
        """UPDATE clients SET
               portal_emails = array_remove(coalesce(portal_emails, '{}'), $2),
               portal_blocked_emails = (SELECT array_agg(DISTINCT x ORDER BY x) FROM unnest(coalesce(portal_blocked_emails, '{}') || ARRAY[$2]) x),
               updated_at = now()
           WHERE id = $1""", client_id, email)


async def login_summary(conn, client_id: int) -> dict:
    known = await known_emails(conn, client_id)
    blocked = await conn.fetchval("SELECT portal_blocked_emails FROM clients WHERE id = $1", client_id) or []
    pending = await conn.fetch(
        "SELECT id, email, created_at FROM client_portal_access_requests "
        "WHERE client_id = $1 AND status = 'pending' ORDER BY id", client_id)
    return {
        "logins": [{"email": e, "source": s, "fixed": s in ("Client email", "Main contact")} for e, s in known.items()],
        "domains": await clinic_domains(conn, client_id),
        "blocked": sorted(norm_email(e) for e in blocked if norm_email(e)),
        "pending": [{"id": r["id"], "email": r["email"], "created_at": r["created_at"].isoformat()} for r in pending],
    }
