"""Free pre-send address checks for cold Touch 1s (deliverability SOP:
bounce rate under 8%, no duplicate sends — context/cold-email-deliverability.md).

No paid verifier (NeverBounce etc.) and no SMTP RCPT probing: probing
mail servers from our own infrastructure is itself a reputation risk, and
Railway blocks outbound port 25 anyway. What's checked instead:
  - the address is well-formed
  - its domain accepts mail (has MX, or at least an A record)
  - it never bounced before
  - no other contact with the same address already got a Touch 1
"""
import asyncio
import re

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+'-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$")
_domain_cache: dict[str, bool] = {}


def _domain_accepts_mail_sync(domain: str) -> bool:
    import dns.resolver

    for record in ("MX", "A"):
        try:
            if dns.resolver.resolve(domain, record, lifetime=5):
                return True
        except dns.resolver.NXDOMAIN:
            return False
        except Exception:
            continue
    return False


async def domain_accepts_mail(domain: str) -> bool:
    if domain not in _domain_cache:
        _domain_cache[domain] = await asyncio.to_thread(_domain_accepts_mail_sync, domain)
    return _domain_cache[domain]


async def check(conn, contact_id: str, email: str) -> str | None:
    """None if the address is OK to cold-email, else the reason it isn't."""
    email = (email or "").strip().lower()
    if not _EMAIL_RE.match(email):
        return "invalid address"
    if not await domain_accepts_mail(email.split("@")[1]):
        return "domain doesn't accept mail"
    if await conn.fetchval(
        "SELECT 1 FROM email_messages WHERE lower(email) = $1 AND bounced_at IS NOT NULL LIMIT 1", email,
    ):
        return "bounced before"
    if await conn.fetchval(
        """SELECT 1 FROM email_handoff_state ehs JOIN contacts c ON c.id = ehs.contact_id
           WHERE lower(trim(c.email)) = $1 AND ehs.contact_id != $2 AND ehs.touch1_sent_at IS NOT NULL LIMIT 1""",
        email, contact_id,
    ):
        return "duplicate: already emailed under another contact"
    return None
