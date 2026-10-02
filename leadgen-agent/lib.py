"""
Free helper functions for the lead qualifier — website scraping, owner-name
extraction, progress tracking, and pushing to the DigiGrowth OS. No paid API
calls (no Google Places, no Anthropic) — those are now done by Claude Code
itself via the `scrape-leads` skill, using the Playwright MCP browser tools
for Maps and its own reasoning (instead of a metered API) for qualification.

CLI usage (invoked by the scrape-leads skill via Bash):
    python lib.py scrape-site <url>                # -> JSON {owner_name, website_text, email}
    python lib.py city-next                        # -> JSON {city, state, term_index} for the next city to work, or {"done": true}
    python lib.py run-start [manual|scheduled]      # -> JSON {run_id} -- call once at the start of every run; the lead target is per run
    python lib.py city-record-progress <city> <state> <term_index> <reviewed_delta> <qualified_delta> [<run_id>]
                                                     # updates city_coverage.json (and the run's tally in runs.json) after finishing a search term
    python lib.py run-tally <run_id>                # -> JSON {run_id, reviewed, qualified, cities, target} for one run -- use this for the lead_target_per_run check, never an in-session counter
    python lib.py city-status [<city>, <state>]     # -> JSON coverage summary (all cities, or one)
    python lib.py daily-tally [<YYYY-MM-DD>]        # -> JSON {date, reviewed, qualified, cities} across everything touched that day (informational only -- the target is per run, see run-tally)
    python lib.py scraped-add <place_id_or_key>    # add an id to scraped_ids.json
    python lib.py scraped-has <place_id_or_key>    # exit 0 if already scraped, 1 if not
    python lib.py crm-filter <listings.json> <out.json>  # drop Maps listings already in the OS CRM (phone/website match); -> JSON {kept, already_in_crm, ...}
    python lib.py crm-has <phone> [<website>]      # exit 0 if that business is already in the OS CRM, 1 if not
    python lib.py push <leads.json path>           # POST leads to DigiGrowth OS, skipping CRM duplicates; -> JSON {pushed_new, skipped_existing, failed}
    python lib.py post-chat <message.md path>      # post a message into the leadgen-agent OS chat

  City pipeline (what the scrape-leads skill actually uses per city):
    python lib.py city-prep <city> <state> <start_term_index> <prep.json> <term_file>...
                                                     # merge term extractions, dedupe across terms, CRM/scraped/blacklist filters -> candidate list
    python lib.py scrape-batch <prep.json> <sites.json> [--exclude "idx:reason;idx:reason"]
                                                     # parallel scrape-site over candidates
    python lib.py digest <prep.json> <sites.json> [start_idx] [count]   # print candidates' site data, a page at a time
    python lib.py city-finish <prep.json> <leads.json> <run_id> [status]
                                                     # push + mark scraped + record every term's progress + run tally, in one call
"""

import json
import os
import re
import sys
import time
import datetime
import pathlib
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "shared"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv()

BASE_DIR           = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE        = os.path.join(BASE_DIR, "config.json")
CITY_COVERAGE_FILE = os.path.join(BASE_DIR, "city_coverage.json")
SCRAPED_FILE        = os.path.join(BASE_DIR, "scraped_ids.json")
RUNS_FILE          = os.path.join(BASE_DIR, "runs.json")

with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = json.load(f)

HEADERS = {"User-Agent": "Mozilla/5.0"}


# ════════════════════════════════════════════════════════════════════════════
#  OWNER NAME EXTRACTION
# ════════════════════════════════════════════════════════════════════════════

_OWNER_PATTERNS = [
    r"(?:Dr|Doctor)\.?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})(?:\s*,?\s*(?:DPT|PT))?",
    r"(?:Founded|Owned)\s+by\s+([A-Z][a-z]+\s+[A-Z][a-z]+)",
    r"I(?:'m| am)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*,?\s*(?:a\s+)?(?:mobile\s+)?(?:physical therapist|PT)",
    r"(?:Owner|Physical Therapist|Founder)[:\s]+([A-Z][a-z]+\s+[A-Z][a-z]+)",
]

_NAME_STOPWORDS = {
    "mobile", "physical", "therapy", "therapist", "therapists", "pt", "dpt",
    "rehab", "rehabilitation", "care", "clinic", "hospital", "services", "service",
    "house", "home", "call", "calls", "senior", "free", "certified",
    "amazing", "award", "winning", "founded", "owned", "dr", "doctor",
    "practice", "wellness", "health", "healing", "comfort", "compassionate",
    "orthopedic", "sports", "geriatric", "specialist",
    "our", "team", "staff", "meet", "the", "about", "contact",
}


def valid_name(s: str) -> bool:
    """True if s reads as a real 2-3 word person name, not a generic phrase,
    section header, or scraping artifact (e.g. 'Our Team', 'Ball Quality')."""
    words = s.strip().split()
    if not (2 <= len(words) <= 3):
        return False
    if not words[0][0].isupper():
        return False
    if any(w.lower() in _NAME_STOPWORDS for w in words):
        return False
    return True


def extract_owner_regex(text: str) -> str:
    for pattern in _OWNER_PATTERNS:
        m = re.search(pattern, text)
        if m and valid_name(m.group(1)):
            return m.group(1).strip()
    return ""


_SIGNAL_KEYWORDS = [
    "dr.", "founder", "owner", "founded", "independently owned",
    "family owned", "locally owned", "our location", "locations",
]


def _prioritized_truncate(text: str, max_words: int) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    priority, rest = [], []
    for s in sentences:
        low = s.lower()
        (priority if any(k in low for k in _SIGNAL_KEYWORDS) else rest).append(s)
    words = []
    for s in priority + rest:
        for w in s.split():
            words.append(w)
            if len(words) >= max_words:
                return " ".join(words)
    return " ".join(words)


_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

_EMAIL_JUNK_DOMAINS = (
    "sentry.io", "wixpress.com", "godaddy.com", "example.com", "yourdomain.com",
    "domain.com", "email.com", "wordpress.com", "schema.org", ".png", ".jpg",
    ".jpeg", ".gif", ".svg", ".webp",
)
_EMAIL_JUNK_LOCAL_PREFIXES = ("noreply", "no-reply", "donotreply", "webmaster", "postmaster")
_GENERIC_EMAIL_PREFIXES = ("contact", "info", "hello", "office", "admin", "frontdesk", "front-desk")


def _clean_emails(raw_emails: list[str]) -> list[str]:
    seen, out = set(), []
    for e in raw_emails:
        e = e.strip().strip(".,;:").lower()
        if not e or e in seen:
            continue
        local, _, domain = e.partition("@")
        if any(j in e for j in _EMAIL_JUNK_DOMAINS):
            continue
        if local in _EMAIL_JUNK_LOCAL_PREFIXES:
            continue
        seen.add(e)
        out.append(e)
    return out


def pick_best_email(emails: list[str], owner_name: str) -> str:
    """Prefer an email whose local part matches the verified owner's name,
    then a generic contact/info-style address, then whatever's left."""
    if not emails:
        return ""
    name_parts = [p.lower() for p in re.split(r"\s+", owner_name.strip()) if len(p) > 1] if owner_name else []
    for e in emails:
        local = e.split("@", 1)[0].lower()
        if any(part in local for part in name_parts):
            return e
    for e in emails:
        local = e.split("@", 1)[0].lower()
        if any(local == g or local.startswith(g) for g in _GENERIC_EMAIL_PREFIXES):
            return e
    return emails[0]


def scrape_website_full(url: str, max_words: int = 600):
    """Single-pass scrape of homepage + /about + /about-us + /contact via
    plain HTTP (no browser needed — this is not a JS-rendered SPA like
    Google Maps). Returns (owner_name, content_text, email)."""
    if not url:
        return "", "", ""
    pages = [
        url.rstrip("/"),
        url.rstrip("/") + "/about",
        url.rstrip("/") + "/about-us",
        url.rstrip("/") + "/contact",
        url.rstrip("/") + "/contact-us",
    ]
    jsonld_owner = ""
    text_chunks = []
    found_emails = []
    for page_url in pages:
        try:
            res = requests.get(page_url, headers=HEADERS, timeout=8)
            if res.status_code != 200:
                continue
            soup = BeautifulSoup(res.text, "html.parser")
            if not jsonld_owner:
                for script in soup.find_all("script", type="application/ld+json"):
                    try:
                        data = json.loads(script.string or "")
                        if isinstance(data, dict):
                            for field in ("founder", "owner"):
                                val = data.get(field)
                                candidate = (val.get("name") if isinstance(val, dict) else val) or ""
                                if candidate and valid_name(candidate):
                                    jsonld_owner = candidate.strip()
                                    break
                    except Exception:
                        continue
            for a in soup.select('a[href^="mailto:"]'):
                addr = a.get("href", "")[7:].split("?")[0]
                if addr:
                    found_emails.append(addr)
            found_emails.extend(_EMAIL_RE.findall(res.text))
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            text_chunks.append(soup.get_text(separator=" ", strip=True))
        except Exception:
            continue

    all_text = " ".join(text_chunks)
    content_text = _prioritized_truncate(all_text, max_words)

    owner = jsonld_owner or extract_owner_regex(all_text)
    email = pick_best_email(_clean_emails(found_emails), owner)

    return owner, content_text, email


# ════════════════════════════════════════════════════════════════════════════
#  CITY COVERAGE / TRAVERSAL
#
#  Owns "which city do we work on next" in code, not in the model's own
#  reasoning over a markdown table each fresh `claude -p` session. That
#  model-driven approach let the same ~15 cities get re-picked over many
#  separate unattended runs (see leadgen-agent memory notes 2026-09) while
#  cities later in the list never got touched. city_coverage.json is the
#  single source of truth for per-city status; `order` is the fixed,
#  population-ranked traversal sequence.
#
#  NOTE: scraped_ids.json's dedup keys are "<name>|<city>" with state
#  dropped (see normalize_scraped_id) -- a latent collision risk for
#  same-named cities in different states (e.g. Columbus, OH vs Columbus, GA;
#  Glendale, AZ vs Glendale, CA). Not fixed here; if both twins of a pair
#  are ever scraped, check scraped_ids.json manually for cross-contamination.
# ════════════════════════════════════════════════════════════════════════════

TERMS_PER_CITY = 4


def load_city_coverage() -> dict:
    with open(CITY_COVERAGE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_city_coverage(coverage: dict):
    with open(CITY_COVERAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(coverage, f, indent=2)
    from github_sync import push_file
    push_file(__file__, "city_coverage.json")


def _city_key(city: str, state: str) -> str:
    for key in load_city_coverage()["order"]:
        name, abbrev = [p.strip() for p in key.rsplit(",", 1)]
        if name.lower() == city.strip().lower() and abbrev.lower() == state.strip().lower():
            return key
    raise KeyError(f"{city}, {state} not found in city_coverage.json order")


def city_next() -> dict:
    """Deterministically pick the next city to work on:
    1. Resume an in_progress city if one exists (mid-run interruption).
    2. Otherwise the first not_started city in population order.
    3. Otherwise the covered city least-recently scraped, once its cooldown
       has elapsed (catches new-business churn without immediate re-visits).
    4. Otherwise nothing left to do right now.
    """
    coverage = load_city_coverage()
    cities = coverage["cities"]

    for key in coverage["order"]:
        if cities[key]["status"] == "in_progress":
            name, state = [p.strip() for p in key.rsplit(",", 1)]
            return {"city": name, "state": state, "term_index": cities[key]["term_index"], "resuming": True}

    for key in coverage["order"]:
        if cities[key]["status"] == "not_started":
            name, state = [p.strip() for p in key.rsplit(",", 1)]
            return {"city": name, "state": state, "term_index": 0, "resuming": False}

    cooldown_days = coverage.get("cooldown_days", 90)
    today = datetime.date.today()
    due = []
    for key in coverage["order"]:
        rec = cities[key]
        if rec["status"] != "covered" or not rec["last_scraped_date"]:
            continue
        last = datetime.date.fromisoformat(rec["last_scraped_date"])
        if (today - last).days >= cooldown_days:
            due.append((last, key))
    if due:
        due.sort()  # oldest last_scraped_date first
        key = due[0][1]
        name, state = [p.strip() for p in key.rsplit(",", 1)]
        return {"city": name, "state": state, "term_index": 0, "resuming": False}

    return {"done": True}


def city_record_progress(city: str, state: str, term_index: int, reviewed_delta: int, qualified_delta: int,
                         run_id: str = None):
    if run_id:
        _run_record_term(run_id, city, state, term_index, reviewed_delta, qualified_delta)
    coverage = load_city_coverage()
    key = _city_key(city, state)
    rec = coverage["cities"][key]
    rec["reviewed_count"] += reviewed_delta
    rec["qualified_count"] += qualified_delta
    rec["term_index"] = term_index
    rec["last_scraped_date"] = datetime.date.today().isoformat()
    rec["status"] = "covered" if term_index >= TERMS_PER_CITY else "in_progress"
    save_city_coverage(coverage)
    return rec


def city_status(city: str = None, state: str = None) -> dict:
    coverage = load_city_coverage()
    if city and state:
        return coverage["cities"][_city_key(city, state)]
    return coverage["cities"]


def daily_tally(date_str: str = None) -> dict:
    """Sum reviewed/qualified across every city touched on a given date
    (default today). This is the target-check source of truth precisely
    because it survives a process restart -- an in-session running total
    does not. A run can get interrupted (session limit, backgrounding bug)
    and resumed as a brand-new `claude -p` process; that process's own
    in-memory tally starts at zero and has no idea a target may already
    have been met by earlier resumes today, so it keeps going past the
    real target (this happened 2026-09-03: three resumes pushed 176
    qualified leads against a target of 100). Checking this instead fixes
    that at the source."""
    date_str = date_str or datetime.date.today().isoformat()
    coverage = load_city_coverage()
    reviewed = qualified = 0
    cities = []
    for key in coverage["order"]:
        rec = coverage["cities"][key]
        if rec.get("last_scraped_date") == date_str:
            reviewed += rec["reviewed_count"]
            qualified += rec["qualified_count"]
            cities.append(key)
    return {"date": date_str, "reviewed": reviewed, "qualified": qualified, "cities": cities}


# ── Per-run tally ─────────────────────────────────────────────────────────
# The lead target is per run, not per day: a manual skill run and the nightly
# scheduled run each get their own lead_target_per_run, however many other runs
# happened that day. A run spans several `claude -p` processes (the wrapper
# launches one per city, and a session-limit resume is a fresh process), so the
# tally lives on disk keyed by run_id rather than in any one process's memory.
# Counts are logged per search term, so a city started in an earlier run (e.g.
# Richmond, begun 9/28 and finished 9/30) only credits each run with the terms
# it actually ran -- unlike daily_tally, which sums whole-city totals.
# Local-only state (not pushed to GitHub): runs only ever execute on this PC.

def lead_target_per_run() -> int:
    return config.get("lead_target_per_run", config.get("daily_lead_target", 100))


def _load_runs() -> dict:
    if os.path.exists(RUNS_FILE):
        with open(RUNS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"runs": {}}


def _save_runs(runs: dict):
    with open(RUNS_FILE, "w", encoding="utf-8") as f:
        json.dump(runs, f, indent=1)


def run_start(source: str = "manual") -> dict:
    runs = _load_runs()
    now = datetime.datetime.now()
    run_id = f"{now.strftime('%Y-%m-%d_%H-%M-%S')}_{source}"
    runs["runs"][run_id] = {"source": source, "started": now.isoformat(timespec="seconds"), "terms": []}
    # Keep the file small: only the 60 most recent runs matter.
    for old in sorted(runs["runs"])[:-60]:
        del runs["runs"][old]
    _save_runs(runs)
    return {"run_id": run_id, "target": lead_target_per_run()}


def _run_record_term(run_id: str, city: str, state: str, term_index: int, reviewed: int, qualified: int):
    runs = _load_runs()
    run = runs["runs"].setdefault(run_id, {"source": "unknown",
                                           "started": datetime.datetime.now().isoformat(timespec="seconds"),
                                           "terms": []})
    run["terms"].append({"city": f"{city}, {state}", "term_index": term_index,
                         "reviewed": reviewed, "qualified": qualified,
                         "at": datetime.datetime.now().isoformat(timespec="seconds")})
    _save_runs(runs)


def run_tally(run_id: str) -> dict:
    run = _load_runs()["runs"].get(run_id, {"terms": []})
    cities = []
    for t in run["terms"]:
        if t["city"] not in cities:
            cities.append(t["city"])
    return {"run_id": run_id,
            "reviewed": sum(t["reviewed"] for t in run["terms"]),
            "qualified": sum(t["qualified"] for t in run["terms"]),
            "cities": cities,
            "target": lead_target_per_run()}


def normalize_scraped_id(raw: str) -> str:
    """Collapse "<name>|<city>|<state>" to a stable dedup key: lowercased
    name + city, state dropped. State format has drifted between runs
    ("Florida" vs "fl", present vs absent) and caused the same business to
    be re-scraped under a "new" key — name+city alone is unique enough here
    and immune to that drift."""
    parts = [p.strip().lower() for p in raw.split("|")]
    name = parts[0] if len(parts) > 0 else raw.strip().lower()
    city = parts[1] if len(parts) > 1 else ""
    return f"{name}|{city}"


def load_scraped_ids() -> set:
    if os.path.exists(SCRAPED_FILE):
        with open(SCRAPED_FILE, "r", encoding="utf-8") as f:
            raw_ids = json.load(f)
        return {normalize_scraped_id(raw) for raw in raw_ids}
    return set()


def save_scraped_ids(ids: set):
    with open(SCRAPED_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(ids), f)
    from github_sync import push_file
    push_file(__file__, "scraped_ids.json")


# ════════════════════════════════════════════════════════════════════════════
#  DIGIGROWTH OS PUSH
# ════════════════════════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════════════════════════
#  CRM DEDUP — "is this business already in the DigiGrowth OS?"
# ════════════════════════════════════════════════════════════════════════════
# scraped_ids.json keys on name+city, so the same clinic surfacing in a
# neighboring city's search (a Miami clinic in a Hialeah search, an Allen
# clinic in a McKinney search) slipped past it, got re-qualified, and was
# counted as a new lead even though POST /api/contacts just merged it into
# the existing row by phone. The CRM itself is the source of truth: match on
# phone (last 10 digits) and website domain, which are stable across
# searches, before spending any qualification work on a listing.

CRM_INDEX_FILE = os.path.join(BASE_DIR, "crm_index.json")
CRM_INDEX_TTL_SECONDS = 30 * 60

# Hosting/social domains many unrelated businesses share — never a dedup signal.
_SHARED_DOMAINS = {
    "facebook.com", "instagram.com", "google.com", "g.page", "business.site",
    "linktr.ee", "yelp.com", "wixsite.com", "squarespace.com", "godaddysites.com",
    "sites.google.com", "square.site", "janeapp.com", "linkedin.com",
}


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    return digits[-10:] if len(digits) >= 10 else ""


def normalize_domain(url: str) -> str:
    host = re.sub(r"^[a-z]+://", "", (url or "").strip().lower()).split("/")[0].split("?")[0]
    host = host.split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    if not host or host in _SHARED_DOMAINS or any(host.endswith("." + d) for d in _SHARED_DOMAINS):
        return ""
    return host


def crm_index(refresh: bool = False) -> dict:
    """{"phones": set, "domains": set} for every contact in the OS CRM.
    Cached to crm_index.json for 30 min so a run makes ~7 paged GETs per
    half hour instead of one per listing."""
    if not refresh and os.path.exists(CRM_INDEX_FILE):
        with open(CRM_INDEX_FILE, "r", encoding="utf-8") as f:
            cached = json.load(f)
        if time.time() - cached.get("fetched_at", 0) < CRM_INDEX_TTL_SECONDS:
            return {"phones": set(cached["phones"]), "domains": set(cached["domains"])}

    base_url = os.environ.get("DASHBOARD_URL", "").rstrip("/")
    auth = ("admin", os.environ.get("DASHBOARD_PASSWORD", ""))
    phones, domains = set(), set()
    offset = 0
    while True:
        r = requests.get(f"{base_url}/api/contacts", auth=auth,
                         params={"limit": 200, "offset": offset}, timeout=60)
        r.raise_for_status()
        page = r.json().get("contacts", [])
        for c in page:
            if p := normalize_phone(c.get("phone")):
                phones.add(p)
            if d := normalize_domain(c.get("website")):
                domains.add(d)
        if len(page) < 200:
            break
        offset += 200

    index = {"phones": phones, "domains": domains}
    _save_crm_index(index)
    return index


def _save_crm_index(index: dict):
    with open(CRM_INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump({"fetched_at": time.time(), "phones": sorted(index["phones"]),
                   "domains": sorted(index["domains"])}, f)


def crm_has(index: dict, phone: str, website: str) -> bool:
    p, d = normalize_phone(phone), normalize_domain(website)
    return bool((p and p in index["phones"]) or (d and d in index["domains"]))


def crm_filter(listings: list) -> tuple:
    """Split Maps listings into (not_in_crm, already_in_crm)."""
    index = crm_index()
    fresh, existing = [], []
    for l in listings:
        (existing if crm_has(index, l.get("phone"), l.get("website")) else fresh).append(l)
    return fresh, existing


def push_to_os(leads: list, lead_status: str = "new") -> dict:
    """POST qualified leads, skipping any already in the CRM (re-checked
    against a fresh index right before pushing). Prints and returns
    {"pushed_new": n, "skipped_existing": [...], "failed": [...]}.
    pushed_new — not len(leads) — is the qualified count to record."""
    result = {"pushed_new": 0, "skipped_existing": [], "failed": []}
    if not leads:
        print(json.dumps(result))
        return result
    base_url = os.environ.get("DASHBOARD_URL", "").rstrip("/")
    password = os.environ.get("DASHBOARD_PASSWORD", "")
    auth = ("admin", password)
    index = crm_index(refresh=True)
    grade_order = {"A": 0, "B": 1, "C": 2, "D": 3}
    for lead in sorted(leads, key=lambda r: grade_order.get(r.get("Grade", "D"), 3)):
        if crm_has(index, lead.get("Phone"), lead.get("Website")):
            result["skipped_existing"].append(lead["Business Name"])
            continue
        body = {
            "business": lead["Business Name"],
            "owner":    lead["Owner Name"],
            "phone":    lead["Phone"],
            "email":    lead.get("Email", ""),
            "website":  lead["Website"],
            "city":     lead.get("City", ""),
            "state":    lead.get("State", ""),
            "grade":    lead["Grade"],
            "opener":   lead["Opener"],
            "notes":    lead.get("Grade Reason", ""),
            "status":   lead_status,
            "tags":     ["independent-pt"],
        }
        try:
            r = requests.post(f"{base_url}/api/contacts", auth=auth, json=body, timeout=10)
            r.raise_for_status()
            result["pushed_new"] += 1
            if "idx" in lead:
                result.setdefault("pushed_idx", []).append(lead["idx"])
            if p := normalize_phone(lead.get("Phone")):
                index["phones"].add(p)
            if d := normalize_domain(lead.get("Website")):
                index["domains"].add(d)
            time.sleep(0.3)
        except Exception as e:
            print(f"  WARNING push failed for {lead['Business Name']}: {e}")
            result["failed"].append(lead["Business Name"])
    _save_crm_index(index)
    print(json.dumps(result))
    return result


def post_chat_message(content: str):
    """Insert a message into the leadgen-agent's OS chat (visible in the
    dashboard's Agents panel) without triggering a Claude turn there."""
    base_url = os.environ.get("DASHBOARD_URL", "").rstrip("/")
    password = os.environ.get("DASHBOARD_PASSWORD", "")
    auth = ("admin", password)
    r = requests.post(
        f"{base_url}/api/agents/leadgen-agent/inject",
        auth=auth,
        json={"content": content, "role": "assistant"},
        timeout=10,
    )
    r.raise_for_status()
    print("posted to leadgen-agent OS chat")


# ════════════════════════════════════════════════════════════════════════════
#  CITY PIPELINE — city-prep / scrape-batch / digest / city-finish
#
#  Every deterministic step of a city lives here so the model only spends
#  turns on the browser and on qualification. Before these existed, each
#  `claude -p` city process re-read lib.py's source and hand-wrote its own
#  batching/scraping/filter helpers (~70 turns per city on 2026-10-01, every
#  turn re-reading a 100k-token context). The model now does: extract all
#  terms -> city-prep -> scrape-batch -> digest pages -> write leads.json ->
#  city-finish.
# ════════════════════════════════════════════════════════════════════════════

SEARCH_TERMS = ["physical therapy", "physical therapist", "outpatient physical therapy", "sports physical therapy"]

_INSTITUTIONAL_KEYWORDS = [
    "hospital", "home health", "nursing home", "skilled nursing", "hospice", "urgent care",
    "behavioral health", "addiction", "mental health", "psychiatric", "chiropractic",
    "chiropractor", "home care", "va medical", "rehabilitation hospital", "assisted living",
    "senior living", "physical therapy school", "university",
]


def _chain_blacklist() -> list[str]:
    """Names from memory.txt's CHAIN / FRANCHISE BLACKLIST line."""
    with open(os.path.join(BASE_DIR, "memory.txt"), "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    for i, line in enumerate(lines):
        if line.strip().upper().startswith("CHAIN / FRANCHISE BLACKLIST"):
            if i + 1 < len(lines):
                return [n.strip().lower() for n in lines[i + 1].split(",") if n.strip()]
    return []


def _listing_key(l: dict) -> str:
    return normalize_phone(l.get("phone")) or normalize_domain(l.get("website")) or (l.get("name") or "").strip().lower()


def _load_listings(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):  # scroll+extract evaluate returns {end, counts, listings}
        data = data.get("listings", [])
    return [l for l in data if l.get("name")]


def city_prep(city: str, state: str, start_term: int, term_files: list[str]) -> dict:
    """Merge the term extractions for one city (term_files[i] is term
    start_term+i+1), dedupe across terms, and run every free filter.

    reviewed per term = listings first seen in this city on that term, not in
    the CRM, and not already in scraped_ids.json -- each business counts once
    per city. Writes nothing to scraped_ids.json; city-finish does that, so a
    process that dies mid-city leaves the city cleanly redoable."""
    index = crm_index()
    scraped = load_scraped_ids()
    blacklist = _chain_blacklist()
    seen = set()
    terms, skipped, candidates = [], [], []
    for offset, path in enumerate(term_files):
        term_no = start_term + offset + 1
        listings = _load_listings(path)
        t = {"term_index": term_no, "term": SEARCH_TERMS[term_no - 1], "raw": len(listings),
             "dup_in_city": 0, "in_crm": 0, "already_scraped": 0, "reviewed": 0}
        for l in listings:
            key = _listing_key(l)
            if key in seen:
                t["dup_in_city"] += 1
                continue
            seen.add(key)
            if crm_has(index, l.get("phone"), l.get("website")):
                t["in_crm"] += 1
                continue
            sid = normalize_scraped_id(f"{l['name']}|{city}|{state}")
            if sid in scraped:
                t["already_scraped"] += 1
                continue
            t["reviewed"] += 1
            entry = {"name": l["name"], "phone": l.get("phone", ""), "website": l.get("website", ""),
                     "term_index": term_no}
            low = l["name"].lower()
            if not entry["phone"] or not entry["website"]:
                entry["reason"] = "no phone or website"
            elif hit := next((b for b in blacklist if b in low), None):
                entry["reason"] = f"chain blacklist ({hit})"
            elif hit := next((k for k in _INSTITUTIONAL_KEYWORDS if k in low), None):
                entry["reason"] = f"institutional keyword ({hit})"
            if "reason" in entry:
                skipped.append(entry)
            else:
                entry["idx"] = len(candidates)
                candidates.append(entry)
        terms.append(t)
    return {"city": city, "state": state, "start_term": start_term, "terms": terms,
            "skipped": skipped, "candidates": candidates, "excluded": {}, "finished": False}


def _print_prep_summary(prep: dict):
    for t in prep["terms"]:
        print(f"T{t['term_index']} {t['term']}: raw {t['raw']}, dup-in-city {t['dup_in_city']}, "
              f"in CRM {t['in_crm']}, already scraped {t['already_scraped']}, reviewed {t['reviewed']}")
    reasons = {}
    for s in prep["skipped"]:
        reasons.setdefault(s["reason"].split(" (")[0], []).append(s["name"])
    for r, names in reasons.items():
        print(f"skipped - {r}: {len(names)}" + ("" if r == "no phone or website" else f" ({'; '.join(names)})"))
    print(f"\n{len(prep['candidates'])} candidates (idx | name | domain | term):")
    for c in prep["candidates"]:
        print(f"{c['idx']} | {c['name']} | {normalize_domain(c['website']) or c['website'][:50]} | T{c['term_index']}")


def scrape_batch(prep: dict, exclude: dict, workers: int = 8) -> dict:
    """scrape-site every non-excluded candidate in parallel -> {idx: {...}}."""
    from concurrent.futures import ThreadPoolExecutor
    max_words = config.get("max_website_text_words", 300)
    todo = [c for c in prep["candidates"] if str(c["idx"]) not in exclude]

    def one(c):
        try:
            owner, text, email = scrape_website_full(c["website"], max_words)
        except Exception:
            owner, text, email = "", "", ""
        return str(c["idx"]), {"owner_name": owner, "website_text": text, "email": email}

    with ThreadPoolExecutor(max_workers=workers) as ex:
        return dict(ex.map(one, todo))


def _print_digest(prep: dict, sites: dict, start: int, count: int):
    shown = [c for c in prep["candidates"] if str(c["idx"]) in sites and c["idx"] >= start][:count]
    for c in shown:
        s = sites[str(c["idx"])]
        print(f"[{c['idx']}] {c['name']} | {c['phone']} | {c['website']}")
        print(f"owner(regex): {s['owner_name'] or '-'} | email: {s['email'] or '-'}")
        print(f"text: {s['website_text'] or '(EMPTY - site returned no text)'}\n")
    remaining = [c["idx"] for c in prep["candidates"] if str(c["idx"]) in sites and c["idx"] > (shown[-1]["idx"] if shown else start)]
    print(f"--- next: digest ... {remaining[0]}" if remaining else "--- end of digest")


def _opener_ok(opener: str) -> bool:
    return bool(opener) and len(opener.split()) <= 15 and "?" not in opener


def city_finish(prep: dict, leads: list, run_id: str, status: str = "new") -> dict:
    """Push, mark every listing reviewed this city as scraped, record per-term
    progress under run_id, and return the run tally. Re-applies run.py's
    guardrails (valid owner name, opener <=15 words / no '?') as a backstop."""
    by_idx = {c["idx"]: c for c in prep["candidates"]}
    pushable, rejected = [], []
    for lead in leads:
        idx = lead.get("idx")
        if idx not in by_idx:
            rejected.append(f"{lead.get('Business Name')}: missing/unknown idx")
        elif not valid_name(re.sub(r"^(dr|doctor)\.?\s+", "", lead.get("Owner Name", "").split(",")[0].strip(), flags=re.I)):
            rejected.append(f"{lead.get('Business Name')}: owner name fails valid_name")
        elif not _opener_ok(lead.get("Opener", "")):
            rejected.append(f"{lead.get('Business Name')}: opener empty, >15 words, or has '?'")
        else:
            lead.setdefault("City", prep["city"])
            lead.setdefault("State", prep["state"])
            pushable.append(lead)

    result = push_to_os(pushable, status)
    qualified_by_term = {}
    for idx in result.get("pushed_idx", []):
        t = by_idx[idx]["term_index"]
        qualified_by_term[t] = qualified_by_term.get(t, 0) + 1

    ids = load_scraped_ids()
    for l in prep["skipped"] + prep["candidates"]:
        ids.add(normalize_scraped_id(f"{l['name']}|{prep['city']}|{prep['state']}"))
    save_scraped_ids(ids)

    for t in prep["terms"]:
        city_record_progress(prep["city"], prep["state"], t["term_index"], t["reviewed"],
                             qualified_by_term.get(t["term_index"], 0), run_id)

    grades = {}
    for lead in pushable:
        if lead.get("idx") in result.get("pushed_idx", []):
            grades[lead["Grade"]] = grades.get(lead["Grade"], 0) + 1
    return {"push": result, "rejected_by_guardrails": rejected,
            "city": {"reviewed": sum(t["reviewed"] for t in prep["terms"]),
                     "qualified": result["pushed_new"], "grades": grades,
                     "by_term": [{"term_index": t["term_index"], "reviewed": t["reviewed"],
                                  "qualified": qualified_by_term.get(t["term_index"], 0)} for t in prep["terms"]]},
            "run_tally": run_tally(run_id)}


def _load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)


# ════════════════════════════════════════════════════════════════════════════
#  CLI
# ════════════════════════════════════════════════════════════════════════════

def _cli():
    if len(sys.argv) < 2:
        print("usage: lib.py <scrape-site|city-next|city-record-progress|city-status|scraped-add|scraped-has|push> [args]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "scrape-site":
        url = sys.argv[2]
        owner, text, email = scrape_website_full(url, config.get("max_website_text_words", 300))
        print(json.dumps({"owner_name": owner, "website_text": text, "email": email}))

    elif cmd == "city-next":
        print(json.dumps(city_next()))

    elif cmd == "city-record-progress":
        city, state, term_index, reviewed_delta, qualified_delta = sys.argv[2:7]
        run_id = sys.argv[7] if len(sys.argv) > 7 else None
        rec = city_record_progress(city, state, int(term_index), int(reviewed_delta), int(qualified_delta), run_id)
        print(json.dumps(rec))

    elif cmd == "city-status":
        if len(sys.argv) > 3:
            print(json.dumps(city_status(sys.argv[2], sys.argv[3])))
        else:
            print(json.dumps(city_status()))

    elif cmd == "run-start":
        print(json.dumps(run_start(sys.argv[2] if len(sys.argv) > 2 else "manual")))

    elif cmd == "run-tally":
        print(json.dumps(run_tally(sys.argv[2])))

    elif cmd == "daily-tally":
        date_str = sys.argv[2] if len(sys.argv) > 2 else None
        print(json.dumps(daily_tally(date_str)))

    elif cmd == "scraped-add":
        ids = load_scraped_ids()
        ids.add(normalize_scraped_id(sys.argv[2]))
        save_scraped_ids(ids)
        print("ok")

    elif cmd == "scraped-has":
        ids = load_scraped_ids()
        sys.exit(0 if normalize_scraped_id(sys.argv[2]) in ids else 1)

    elif cmd == "crm-filter":
        # crm-filter <listings.json> <out.json>: drop listings already in the CRM
        with open(sys.argv[2], "r", encoding="utf-8") as f:
            listings = json.load(f)
        fresh, existing = crm_filter(listings)
        with open(sys.argv[3], "w", encoding="utf-8") as f:
            json.dump(fresh, f, indent=1)
        print(json.dumps({"kept": len(fresh), "already_in_crm": len(existing),
                          "already_in_crm_names": [l.get("name") for l in existing]}))

    elif cmd == "crm-has":
        # crm-has "<phone>" "<website>": exit 0 if already in the CRM, 1 if not
        sys.exit(0 if crm_has(crm_index(), sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "") else 1)

    elif cmd == "push":
        leads_path = sys.argv[2]
        status = sys.argv[3] if len(sys.argv) > 3 else "new"
        with open(leads_path, "r", encoding="utf-8") as f:
            leads = json.load(f)
        push_to_os(leads, status)

    elif cmd == "city-prep":
        # city-prep <city> <state> <start_term_index> <prep_out.json> <term_file>...
        city, state, start_term, out = sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5]
        prep = city_prep(city, state, start_term, sys.argv[6:])
        _save_json(out, prep)
        _print_prep_summary(prep)

    elif cmd == "scrape-batch":
        # scrape-batch <prep.json> <sites_out.json> [--exclude idx:reason;idx:reason]
        prep = _load_json(sys.argv[2])
        exclude = {}
        if "--exclude" in sys.argv:
            raw = sys.argv[sys.argv.index("--exclude") + 1]
            for part in filter(None, (p.strip() for p in raw.split(";"))):
                idx, _, reason = part.partition(":")
                exclude[idx.strip()] = reason.strip() or "excluded by name"
        prep["excluded"] = exclude
        _save_json(sys.argv[2], prep)
        sites = scrape_batch(prep, exclude)
        _save_json(sys.argv[3], sites)
        empty = [k for k, v in sites.items() if not v["website_text"]]
        print(json.dumps({"scraped": len(sites), "excluded": len(exclude), "empty_text_idx": empty}))

    elif cmd == "digest":
        # digest <prep.json> <sites.json> [start_idx] [count]
        _print_digest(_load_json(sys.argv[2]), _load_json(sys.argv[3]),
                      int(sys.argv[4]) if len(sys.argv) > 4 else 0,
                      int(sys.argv[5]) if len(sys.argv) > 5 else 12)

    elif cmd == "city-finish":
        # city-finish <prep.json> <leads.json> <run_id> [status]
        prep = _load_json(sys.argv[2])
        if prep.get("finished"):
            print("this prep.json was already finished -- not pushing/recording twice")
            sys.exit(1)
        leads = _load_json(sys.argv[3])
        out = city_finish(prep, leads, sys.argv[4], sys.argv[5] if len(sys.argv) > 5 else "new")
        prep["finished"] = True
        _save_json(sys.argv[2], prep)
        print(json.dumps(out, indent=1))

    elif cmd == "post-chat":
        msg_path = sys.argv[2]
        with open(msg_path, "r", encoding="utf-8") as f:
            content = f.read()
        post_chat_message(content)

    else:
        print(f"unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    _cli()
