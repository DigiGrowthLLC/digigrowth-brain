"""
Domain health for the cold-outreach email identities — backs the "Domain
Health" view in IdentityWarmupModal.jsx.

Two halves:

1. Live DNS checks (SPF / DKIM / DMARC / MX) run from Railway on demand for
   each identity's sending domain. DKIM selectors are provider-specific:
   `google` for Google Workspace, `selector1`/`selector2` for Microsoft 365.
   A subdomain with no _dmarc record of its own inherits the organizational
   domain's policy (RFC 7489 §6.6.3) — the subdomain _dmarc records were
   deleted on 2026-09-28 so reports roll up to the root's rua — so that
   case is reported as inherited, not missing.

2. DMARC aggregate-report summaries. rua points at Postmark's DMARC digest
   service, which emails its digests to dylanrg@digigrowthllc.com. The EA
   Daily Briefing cloud routine already reads that inbox every morning, so
   it parses any DMARC emails it finds and drops
   executive-assistant/domain_health/pending/dmarc-YYYY-MM-DD.json into
   GitHub (its sandbox can't reach Railway — same relay pattern as
   pending_approvals_relay.py). ingest_pending() picks those files up,
   upserts them into domain_health_reports, then deletes them.
"""

import asyncio
import json
from datetime import date, datetime

import httpx

from db import get_pool
from pending_approvals_relay import _REPO, _gh_delete, _gh_get, _headers

PENDING_DIR = "executive-assistant/domain_health/pending"

_DKIM_SELECTORS = {
    "google": ["google"],
    "microsoft": ["selector1", "selector2"],
}


# ── DNS checks ────────────────────────────────────────────────────────────

def _txt(name: str) -> list[str]:
    import dns.resolver

    try:
        answers = dns.resolver.resolve(name, "TXT", lifetime=5)
    except Exception:
        return []
    return ["".join(part.decode("utf-8", "replace") for part in r.strings) for r in answers]


def _mx(name: str) -> list[str]:
    import dns.resolver

    try:
        answers = dns.resolver.resolve(name, "MX", lifetime=5)
    except Exception:
        return []
    return [str(r.exchange).rstrip(".").lower() for r in answers]


def _org_domain(domain: str) -> str:
    parts = domain.split(".")
    return ".".join(parts[-2:]) if len(parts) > 2 else domain


def _dmarc_tags(record: str) -> dict:
    tags = {}
    for piece in record.split(";"):
        if "=" in piece:
            k, v = piece.split("=", 1)
            tags[k.strip().lower()] = v.strip()
    return tags


def _check_dns_sync(domain: str, provider: str) -> dict:
    checks = {}

    spf = [r for r in _txt(domain) if r.lower().startswith("v=spf1")]
    if len(spf) == 1:
        checks["spf"] = {"ok": True, "detail": spf[0]}
    elif len(spf) > 1:
        checks["spf"] = {"ok": False, "detail": f"{len(spf)} SPF records — receivers treat multiple as a permerror"}
    else:
        checks["spf"] = {"ok": False, "detail": "No SPF record"}

    selectors = _DKIM_SELECTORS.get(provider, ["google", "selector1", "selector2"])
    found = [s for s in selectors if any("p=" in r for r in _txt(f"{s}._domainkey.{domain}"))]
    checks["dkim"] = (
        {"ok": True, "detail": f"Selector(s) published: {', '.join(found)}"}
        if found else
        {"ok": False, "detail": f"No DKIM key at {', '.join(s + '._domainkey' for s in selectors)}"}
    )

    own = [r for r in _txt(f"_dmarc.{domain}") if r.lower().startswith("v=dmarc1")]
    org = _org_domain(domain)
    if own:
        tags = _dmarc_tags(own[0])
        checks["dmarc"] = {"ok": True, "policy": tags.get("p", "none"), "detail": own[0]}
    elif org != domain:
        parent = [r for r in _txt(f"_dmarc.{org}") if r.lower().startswith("v=dmarc1")]
        if parent:
            tags = _dmarc_tags(parent[0])
            checks["dmarc"] = {
                "ok": True, "policy": tags.get("sp", tags.get("p", "none")),
                "detail": f"Inherited from {org}: {parent[0]}",
            }
        else:
            checks["dmarc"] = {"ok": False, "detail": f"No DMARC record on {domain} or {org}"}
    else:
        checks["dmarc"] = {"ok": False, "detail": "No DMARC record"}
    if checks["dmarc"]["ok"]:
        effective = own[0] if own else parent[0]
        checks["dmarc"]["rua"] = _dmarc_tags(effective).get("rua")
        if not checks["dmarc"]["rua"]:
            checks["dmarc"]["ok"] = False
            checks["dmarc"]["detail"] += " — no rua, so no aggregate reports will be sent"

    mx = _mx(domain)
    checks["mx"] = (
        {"ok": True, "detail": ", ".join(mx[:3])}
        if mx else
        {"ok": False, "detail": "No MX — replies to this domain bounce"}
    )
    return checks


async def check_dns(domain: str, provider: str) -> dict:
    return await asyncio.to_thread(_check_dns_sync, domain, provider)


# ── Report ingest (briefing → GitHub → here) ──────────────────────────────

async def _gh_list(rel_dir: str) -> list[str]:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"https://api.github.com/repos/{_REPO}/contents/{rel_dir}", headers=_headers())
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    return [f["path"] for f in resp.json() if f.get("type") == "file" and f["name"].endswith(".json")]


def _as_date(value) -> date:
    return date.fromisoformat(str(value)[:10])


def _as_int(value):
    try:
        return int(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None


async def _upsert_report(conn, r: dict) -> None:
    received = r.get("received_at")
    await conn.execute(
        """
        INSERT INTO domain_health_reports
            (domain, reporter, period_start, period_end, total_messages, dmarc_pass,
             dmarc_fail, spf_pass, dkim_pass, sources, notes, email_subject, received_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb, $11, $12, $13)
        ON CONFLICT (domain, reporter, period_start, period_end) DO UPDATE SET
            total_messages = EXCLUDED.total_messages, dmarc_pass = EXCLUDED.dmarc_pass,
            dmarc_fail = EXCLUDED.dmarc_fail, spf_pass = EXCLUDED.spf_pass,
            dkim_pass = EXCLUDED.dkim_pass, sources = EXCLUDED.sources,
            notes = EXCLUDED.notes, email_subject = EXCLUDED.email_subject,
            received_at = EXCLUDED.received_at
        """,
        r["domain"].strip().lower(),
        (r.get("reporter") or "unknown").strip(),
        _as_date(r["period_start"]),
        _as_date(r.get("period_end") or r["period_start"]),
        _as_int(r.get("total_messages")),
        _as_int(r.get("dmarc_pass")),
        _as_int(r.get("dmarc_fail")),
        _as_int(r.get("spf_pass")),
        _as_int(r.get("dkim_pass")),
        json.dumps(r.get("sources") or []),
        r.get("notes"),
        r.get("email_subject"),
        datetime.fromisoformat(received) if received else None,
    )


async def ingest_pending() -> str:
    """Upsert every pending DMARC JSON file into domain_health_reports and
    delete it from GitHub. A file that fails to parse is left in place so
    it can be fixed by hand rather than silently dropped."""
    try:
        paths = await _gh_list(PENDING_DIR)
    except Exception as e:
        return f"domain-health: GitHub list failed: {e}"
    if not paths:
        return "domain-health: nothing pending"

    pool = await get_pool()
    results = []
    for path in paths:
        try:
            raw = await _gh_get(path)
            if raw is None:
                continue
            reports = json.loads(raw).get("reports") or []
            async with pool.acquire() as conn:
                async with conn.transaction():
                    for r in reports:
                        await _upsert_report(conn, r)
        except Exception as e:
            results.append(f"{path}: failed ({e})")
            continue
        del_result = await _gh_delete(path, f"Processed DMARC summary: {path}")
        results.append(f"{path}: {len(reports)} report(s) ({del_result})")
    return "domain-health: " + "; ".join(results)


# ── View data ─────────────────────────────────────────────────────────────

async def domain_health_overview() -> list[dict]:
    """One entry per outreach sending domain (partner mailboxes excluded —
    they never cold-send), with live DNS checks and the DMARC reports for
    that domain plus any reported at its organizational (root) domain."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        identities = await conn.fetch(
            """
            SELECT domain, provider, mailbox_email, status FROM email_send_identities
            WHERE status != 'partner' ORDER BY created_at
            """
        )
        by_domain: dict[str, dict] = {}
        for row in identities:
            d = row["domain"].strip().lower()
            entry = by_domain.setdefault(d, {"domain": d, "provider": row["provider"], "mailboxes": []})
            entry["mailboxes"].append({"email": row["mailbox_email"], "status": row["status"]})

        for d, entry in by_domain.items():
            org = _org_domain(d)
            rows = await conn.fetch(
                """
                SELECT * FROM domain_health_reports
                WHERE domain = $1 OR domain = $2
                ORDER BY period_end DESC, id DESC LIMIT 20
                """,
                d, org,
            )
            entry["reports"] = [
                {**dict(r), "sources": json.loads(r["sources"]) if isinstance(r["sources"], str) else r["sources"],
                 "inherited": r["domain"] != d}
                for r in rows
            ]

    domains = list(by_domain.values())
    dns_results = await asyncio.gather(*(check_dns(e["domain"], e["provider"]) for e in domains))
    for entry, checks in zip(domains, dns_results):
        entry["dns"] = checks
    return domains
