"""
Auto-fills the four single-value resource fields on a client's row
(ads_manager_resource / registrar_resource / hosting_resource /
funnel_resource — the client admin view's Resources section) so Dylan
doesn't paste them by hand. Two sources:

1. Config the dashboard already has: the client's landing_page_url (or first
   client_websites row) -> Funnel; their meta_ad_account_id -> an Ads Manager
   link for that account.
2. Platform access-invite emails in the business Gmail inbox
   (dylanrg@digigrowthllc.com) — Meta business portfolio, GoDaddy delegate
   access, Wix collaborator, Squarespace, Namecheap, Cloudflare, Vercel, etc.
   Each invite is matched to ONE client by name / contact name / domain /
   email in the subject or body, or, when the email names nobody (GoDaddy's
   doesn't), by that client ticking the matching portal action item within an
   hour of it arriving. No unique match -> skipped, never guessed.

Never overwrites a manual entry: every value written here is remembered in
clients.resource_autofill, and a field is only rewritten while it still holds
exactly what was auto-written (so a higher-priority source, e.g. the real ad
account link replacing the portfolio invite note, can upgrade it). Once Dylan
edits a field by hand it's his.

3. The client's DNS host, looked up from their domain's nameservers and
   added once as an "Other Resources" entry. The registrar (where the domain
   was bought) often isn't where DNS records are edited — Advantage Therapy's
   domain is at GoDaddy but its DNS is on Wix — and DNS changes have to be
   made wherever the nameservers point.

autofill_job() runs on the app scheduler (main.py), and also runs
guide_autocheck (ticks Marketing Setup steps the data proves are done); POST
/api/client-resources/autofill (clients.py) runs it on demand with a longer
Gmail lookback for a backfill.
"""
import asyncio
import json
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

import guide_autocheck
import integrations
from db import get_pool

FIELDS = ("ads_manager_resource", "registrar_resource", "hosting_resource", "funnel_resource")

# Higher wins; a config-derived link beats an invite-derived note.
PRIORITY_INVITE = 1
PRIORITY_CONFIG = 2

# Portal "Next Steps" action items whose completion time can pin an invite
# email to a client when the email itself names nobody.
_ACTION_ITEM_HINTS = {
    "ads_manager_resource": re.compile(r"meta|facebook|ads manager", re.I),
    "registrar_resource":   re.compile(r"registrar|domain|hosting", re.I),
    "hosting_resource":     re.compile(r"registrar|domain|hosting|website", re.I),
}
_TIMING_WINDOW_SEC = 60 * 60

_FREE_MAIL = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com", "aol.com", "live.com", "me.com", "msn.com"}

# (sender-domain regex, subject+body regex, field, platform label, link, name-extractor regex or None)
_INVITE_RULES = [
    (r"facebookmail\.com$", r"invited you to join .+ business portfolio",
     "ads_manager_resource", "Meta business portfolio", "https://business.facebook.com/latest/settings",
     r"join the (.+?) business portfolio"),
    (r"facebookmail\.com$", r"(shared|gave you|granted) .*access to .*ad account",
     "ads_manager_resource", "Meta ad account access", "https://adsmanager.facebook.com/adsmanager/manage/campaigns", None),
    (r"godaddy\.com$", r"account access invite|invited you to access",
     "registrar_resource", "GoDaddy (delegate access)", "https://account.godaddy.com/access", None),
    (r"namecheap\.com$", r"(shar|grant|invit)\w* .*access",
     "registrar_resource", "Namecheap", "https://ap.www.namecheap.com/domains/list/", None),
    (r"cloudflare\.com$", r"invited you to join",
     "registrar_resource", "Cloudflare", "https://dash.cloudflare.com/", None),
    (r"porkbun\.com$", r"(shar|grant|invit)\w* .*access",
     "registrar_resource", "Porkbun", "https://porkbun.com/account/domainsSpeedy", None),
    (r"wix\.com$", r"invited you to collaborate",
     "hosting_resource", "Wix site", "https://manage.wix.com/account/sites",
     r"collaborate on the site (.+?)(?:\s{2,}|\.|\n|$)|collaborating on (.+?)(?:\n|$)"),
    (r"squarespace\.com$", r"invited you to",
     "hosting_resource", "Squarespace", "https://account.squarespace.com/", None),
    (r"vercel\.com$", r"invited you to join",
     "hosting_resource", "Vercel", "https://vercel.com/dashboard", None),
    (r"webflow\.com$", r"invited you to",
     "hosting_resource", "Webflow", "https://webflow.com/dashboard", None),
    (r"shopify\.com$", r"collaborator",
     "hosting_resource", "Shopify", "https://admin.shopify.com/", None),
]
_INVITE_SENDERS = "facebookmail.com OR godaddy.com OR namecheap.com OR cloudflare.com OR porkbun.com OR wix.com OR squarespace.com OR vercel.com OR webflow.com OR shopify.com"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decode_json(value) -> dict:
    if isinstance(value, str):
        try:
            return json.loads(value) or {}
        except ValueError:
            return {}
    return value or {}


async def offer(conn, client_id: int, field: str, value: str, priority: int, source: str) -> bool:
    """Write value into field unless Dylan has set it by hand. Returns True if written."""
    if field not in FIELDS or not value:
        return False
    row = await conn.fetchrow(f"SELECT {field} AS cur, resource_autofill FROM clients WHERE id = $1", client_id)
    if not row:
        return False
    auto = _decode_json(row["resource_autofill"])
    cur = (row["cur"] or "").strip()
    prev = auto.get(field) or {}
    if cur:
        if prev.get("value") != cur:
            return False  # manual entry (or edited since we wrote it) — hands off
        if cur == value or priority < prev.get("priority", 0):
            return False
    auto[field] = {"value": value, "priority": priority, "source": source, "at": _now_iso()}
    await conn.execute(
        f"UPDATE clients SET {field} = $2, resource_autofill = $3::jsonb, updated_at = now() WHERE id = $1",
        client_id, value, json.dumps(auto),
    )
    print(f"[resource-autofill] client {client_id}: {field} <- {value} ({source})", flush=True)
    return True


# ── Source 1: config the dashboard already has ────────────────────────────────

async def reconcile_config(conn) -> int:
    written = 0
    rows = await conn.fetch(
        """SELECT c.id, cmc.landing_page_url, cmc.meta_ad_account_id,
                  (SELECT url FROM client_websites w WHERE w.client_id = c.id ORDER BY sort_order, id LIMIT 1) AS website_url
           FROM clients c LEFT JOIN client_marketing_config cmc ON cmc.client_id = c.id
           WHERE NOT c.is_test"""
    )
    for r in rows:
        funnel = (r["landing_page_url"] or r["website_url"] or "").strip()
        if funnel:
            written += await offer(conn, r["id"], "funnel_resource", funnel, PRIORITY_CONFIG, "landing page")
        act = re.sub(r"\D", "", r["meta_ad_account_id"] or "")
        if act:
            link = f"https://adsmanager.facebook.com/adsmanager/manage/campaigns?act={act}"
            written += await offer(conn, r["id"], "ads_manager_resource", link, PRIORITY_CONFIG, "meta ad account")
    return written


# ── Source 2: access-invite emails ────────────────────────────────────────────

def _domain(value: str) -> str:
    value = (value or "").strip().lower()
    if not value:
        return ""
    if "@" in value:
        return value.rsplit("@", 1)[1]
    host = urlparse(value if "//" in value else f"//{value}").hostname or ""
    return host.removeprefix("www.")


async def _client_terms(conn) -> dict[int, set[str]]:
    """Lowercased strings that identify each real client in an email."""
    clients = await conn.fetch(
        """SELECT c.id, c.name, c.contact_name, c.email,
                  ct.business, ct.owner, ct.email AS contact_email, ct.website,
                  (SELECT answers->>'name_website' FROM client_onboarding_responses r
                    WHERE r.client_id = c.id AND r.section = 'practice_snapshot') AS name_website
           FROM clients c
           LEFT JOIN contacts ct ON ct.client_id = c.id AND ct.is_client_anchor
           WHERE NOT c.is_test"""
    )
    out: dict[int, set[str]] = {}
    for c in clients:
        terms: set[str] = set()
        for name in (c["name"], c["contact_name"], c["owner"], c["business"]):
            name = (name or "").strip().lower()
            if not name:
                continue
            terms.add(name)
            # "Advantage Therapy- Manual Physical Therapy Las Vegas" -> "advantage therapy"
            terms.add(re.split(r"\s*[-|:–]\s*", name)[0])
        for email in (c["email"], c["contact_email"]):
            email = (email or "").strip().lower()
            if email:
                terms.add(email)
                if _domain(email) not in _FREE_MAIL:
                    terms.add(_domain(email))
        for site in [c["website"], *re.findall(r"[\w.-]+\.[a-z]{2,}", c["name_website"] or "")]:
            d = _domain(site)
            if d and d not in _FREE_MAIL:
                terms.add(d)
        # Short or agency-side strings would false-match every email.
        out[c["id"]] = {t for t in terms if len(t) >= 6 and "digigrowth" not in t}
    return out


async def _client_by_timing(conn, field: str, sent_at: datetime) -> int | None:
    hint = _ACTION_ITEM_HINTS.get(field)
    if not hint:
        return None
    rows = await conn.fetch(
        """SELECT DISTINCT cc.client_id, ai.title
           FROM client_action_item_completions cc
           JOIN onboarding_action_items ai ON ai.id = cc.action_item_id
           JOIN clients c ON c.id = cc.client_id AND NOT c.is_test
           WHERE cc.completed_at BETWEEN $1::timestamptz - $2::float8 * interval '1 second'
                                     AND $1::timestamptz + $2::float8 * interval '1 second'""",
        sent_at, float(_TIMING_WINDOW_SEC),
    )
    ids = {r["client_id"] for r in rows if hint.search(r["title"])}
    return ids.pop() if len(ids) == 1 else None


def _classify(sender: str, text: str):
    sender_domain = _domain(sender)
    for dom_re, text_re, field, label, link, name_re in _INVITE_RULES:
        if re.search(dom_re, sender_domain) and re.search(text_re, text, re.I | re.S):
            name = None
            if name_re:
                m = re.search(name_re, text, re.I)
                name = next((g.strip() for g in m.groups() if g), None) if m else None
            value = f'{label} "{name}": {link}' if name else f"{label}: {link}"
            return field, value, label
    return None


async def scan_invites(days: int = 3) -> int:
    svc = await asyncio.to_thread(integrations._business_gmail_service)
    query = f"newer_than:{int(days)}d from:({_INVITE_SENDERS})"
    msg_ids: list[str] = []
    page_token = None
    while True:
        res = await asyncio.to_thread(
            lambda pt=page_token: svc.users().messages().list(userId="me", q=query, maxResults=100, pageToken=pt).execute()
        )
        msg_ids += [m["id"] for m in res.get("messages", [])]
        page_token = res.get("nextPageToken")
        if not page_token or len(msg_ids) >= 500:
            break

    written = 0
    pool = await get_pool()
    async with pool.acquire() as conn:
        terms_by_client = await _client_terms(conn)
        for mid in msg_ids:
            full = await asyncio.to_thread(
                lambda mid=mid: svc.users().messages().get(userId="me", id=mid, format="full").execute()
            )
            headers = {h["name"].lower(): h["value"] for h in full["payload"].get("headers", [])}
            sender = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", headers.get("from", ""))
            body = integrations._extract_body(full["payload"]) or full.get("snippet", "")
            text = f"{headers.get('subject', '')}\n{body}"
            hit = _classify(sender.group(0) if sender else "", text)
            if not hit:
                continue
            field, value, label = hit

            lowered = text.lower()
            matches = {cid for cid, terms in terms_by_client.items() if any(t in lowered for t in terms)}
            client_id = matches.pop() if len(matches) == 1 else None
            if client_id is None and not matches:
                sent_at = datetime.fromtimestamp(int(full.get("internalDate", "0")) / 1000, tz=timezone.utc)
                client_id = await _client_by_timing(conn, field, sent_at)
            if client_id is None:
                print(f"[resource-autofill] {label} invite {mid}: no unique client match, skipped", flush=True)
                continue
            written += await offer(conn, client_id, field, value, PRIORITY_INVITE, f"{label} invite email")
    return written


# Nameserver suffix -> where the DNS records are actually edited.
_DNS_HOSTS = [
    ("wixdns.net", "Wix", "https://manage.wix.com/account/domains"),
    ("domaincontrol.com", "GoDaddy", "https://dcc.godaddy.com/control/portfolio"),
    ("cloudflare.com", "Cloudflare", "https://dash.cloudflare.com/"),
    ("squarespacedns.com", "Squarespace", "https://account.squarespace.com/domains"),
    ("googledomains.com", "Squarespace (ex-Google Domains)", "https://account.squarespace.com/domains"),
    ("registrar-servers.com", "Namecheap", "https://ap.www.namecheap.com/domains/list/"),
    ("vercel-dns.com", "Vercel", "https://vercel.com/dashboard/domains"),
    ("awsdns", "AWS Route 53", "https://console.aws.amazon.com/route53/"),
    ("porkbun.com", "Porkbun", "https://porkbun.com/account/domainsSpeedy"),
    ("hostgator.com", "HostGator", "https://portal.hostgator.com/"),
    ("bluehost.com", "Bluehost", "https://my.bluehost.com/"),
    ("dreamhost.com", "DreamHost", "https://panel.dreamhost.com/"),
]


async def _client_domain(conn, client_id: int) -> str:
    row = await conn.fetchrow(
        """SELECT c.email, ct.website,
                  (SELECT answers->>'name_website' FROM client_onboarding_responses r
                    WHERE r.client_id = c.id AND r.section = 'practice_snapshot') AS name_website
           FROM clients c LEFT JOIN contacts ct ON ct.client_id = c.id AND ct.is_client_anchor
           WHERE c.id = $1""",
        client_id,
    )
    if not row:
        return ""
    for site in [row["website"], *re.findall(r"[\w.-]+\.[a-z]{2,}", row["name_website"] or ""), row["email"]]:
        d = _domain(site or "")
        if d and d not in _FREE_MAIL:
            return d
    return ""


async def detect_dns_hosts(conn) -> int:
    added = 0
    ids = [r["id"] for r in await conn.fetch(
        "SELECT id FROM clients c WHERE NOT is_test AND NOT EXISTS "
        "(SELECT 1 FROM client_resources cr WHERE cr.client_id = c.id AND cr.label = 'DNS host')")]
    async with httpx.AsyncClient(timeout=10) as http:
        for client_id in ids:
            domain = await _client_domain(conn, client_id)
            if not domain:
                continue
            try:
                r = await http.get("https://dns.google/resolve", params={"name": domain, "type": "NS"})
                ns = sorted(a["data"].rstrip(".").lower() for a in r.json().get("Answer", []) if a.get("type") == 2)
            except Exception as e:
                print(f"[resource-autofill] DNS lookup for {domain} failed: {e}", flush=True)
                continue
            if not ns:
                continue
            host, link = next(((h, l) for suffix, h, l in _DNS_HOSTS if any(suffix in n for n in ns)), (None, None))
            value = (f"{host}: edit {domain}'s DNS records here, not at the registrar: {link}\nNameservers: {', '.join(ns)}"
                     if host else f"Unrecognized DNS host for {domain}. Nameservers: {', '.join(ns)}")
            await conn.execute(
                "INSERT INTO client_resources (client_id, label, value, sort_order) VALUES ($1, 'DNS host', $2, 0)",
                client_id, value,
            )
            print(f"[resource-autofill] client {client_id}: DNS host {host or ns}", flush=True)
            added += 1
    return added


async def run(days: int = 3) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        from_config = await reconcile_config(conn)
        dns_hosts = await detect_dns_hosts(conn)
    from_email = await scan_invites(days)
    await guide_autocheck.autocheck_all()
    return {"from_config": from_config, "from_email": from_email, "dns_hosts": dns_hosts}


async def autofill_job():
    """APScheduler entrypoint — never raises."""
    try:
        result = await run()
        if result["from_config"] or result["from_email"] or result["dns_hosts"]:
            print(f"[resource-autofill] {result}", flush=True)
    except Exception as e:
        print(f"[resource-autofill] error: {e}", flush=True)
