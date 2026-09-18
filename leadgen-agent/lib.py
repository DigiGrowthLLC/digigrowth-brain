"""
Free helper functions for the lead qualifier — website scraping, owner-name
extraction, progress tracking, and pushing to the DigiGrowth OS. No paid API
calls (no Google Places, no Anthropic) — those are now done by Claude Code
itself via the `scrape-leads` skill, using the Playwright MCP browser tools
for Maps and its own reasoning (instead of a metered API) for qualification.

CLI usage (invoked by the scrape-leads skill via Bash):
    python lib.py scrape-site <url>                # -> JSON {owner_name, website_text, email}
    python lib.py city-next                        # -> JSON {city, state, term_index} for the next city to work, or {"done": true}
    python lib.py city-record-progress <city> <state> <term_index> <reviewed_delta> <qualified_delta>
                                                     # updates city_coverage.json after finishing a search term
    python lib.py city-status [<city>, <state>]     # -> JSON coverage summary (all cities, or one)
    python lib.py daily-tally [<YYYY-MM-DD>]        # -> JSON {date, reviewed, qualified, cities} across everything touched that day (persists across process restarts -- use this for the daily_lead_target check, never an in-session counter)
    python lib.py scraped-add <place_id_or_key>    # add an id to scraped_ids.json
    python lib.py scraped-has <place_id_or_key>    # exit 0 if already scraped, 1 if not
    python lib.py push <leads.json path>           # POST leads to DigiGrowth OS
    python lib.py post-chat <message.md path>      # post a message into the leadgen-agent OS chat
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


def city_record_progress(city: str, state: str, term_index: int, reviewed_delta: int, qualified_delta: int):
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

def push_to_os(leads: list, lead_status: str = "new"):
    if not leads:
        print("No qualified leads to push.")
        return
    base_url = os.environ.get("DASHBOARD_URL", "").rstrip("/")
    password = os.environ.get("DASHBOARD_PASSWORD", "")
    auth = ("admin", password)
    grade_order = {"A": 0, "B": 1, "C": 2, "D": 3}
    pushed = 0
    for lead in sorted(leads, key=lambda r: grade_order.get(r.get("Grade", "D"), 3)):
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
            pushed += 1
            time.sleep(0.3)
        except Exception as e:
            print(f"  WARNING push failed for {lead['Business Name']}: {e}")
    print(f"{pushed}/{len(leads)} leads pushed to DigiGrowth OS (status={lead_status}).")


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
        rec = city_record_progress(city, state, int(term_index), int(reviewed_delta), int(qualified_delta))
        print(json.dumps(rec))

    elif cmd == "city-status":
        if len(sys.argv) > 3:
            print(json.dumps(city_status(sys.argv[2], sys.argv[3])))
        else:
            print(json.dumps(city_status()))

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

    elif cmd == "push":
        leads_path = sys.argv[2]
        status = sys.argv[3] if len(sys.argv) > 3 else "new"
        with open(leads_path, "r", encoding="utf-8") as f:
            leads = json.load(f)
        push_to_os(leads, status)

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
