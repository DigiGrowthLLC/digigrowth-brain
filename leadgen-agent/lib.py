"""
Free helper functions for the lead qualifier — website scraping, owner-name
extraction, progress tracking, and pushing to the DigiGrowth OS. No paid API
calls (no Google Places, no Anthropic) — those are now done by Claude Code
itself via the `scrape-leads` skill, using the Playwright MCP browser tools
for Maps and its own reasoning (instead of a metered API) for qualification.

CLI usage (invoked by the scrape-leads skill via Bash):
    python lib.py scrape-site <url>              # -> JSON {owner_name, website_text}
    python lib.py progress-get                    # -> JSON progress.json contents
    python lib.py progress-set <json>              # overwrite progress.json
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
import pathlib
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "shared"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv()

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE   = os.path.join(BASE_DIR, "config.json")
PROGRESS_FILE = os.path.join(BASE_DIR, "progress.json")
SCRAPED_FILE  = os.path.join(BASE_DIR, "scraped_ids.json")

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


def scrape_website_full(url: str, max_words: int = 600):
    """Single-pass scrape of homepage + /about + /about-us via plain HTTP
    (no browser needed — this is not a JS-rendered SPA like Google Maps).
    Returns (owner_name, content_text)."""
    if not url:
        return "", ""
    pages = [
        url.rstrip("/"),
        url.rstrip("/") + "/about",
        url.rstrip("/") + "/about-us",
    ]
    jsonld_owner = ""
    text_chunks = []
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
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            text_chunks.append(soup.get_text(separator=" ", strip=True))
        except Exception:
            continue

    all_text = " ".join(text_chunks)
    content_text = _prioritized_truncate(all_text, max_words)

    if jsonld_owner:
        return jsonld_owner, content_text

    name = extract_owner_regex(all_text)
    return name, content_text


# ════════════════════════════════════════════════════════════════════════════
#  PROGRESS / DEDUP TRACKING
# ════════════════════════════════════════════════════════════════════════════

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"state": "", "city": "", "term": ""}


def save_progress(progress: dict):
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2)
    from github_sync import push_file
    push_file(__file__, "progress.json")


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
        print("usage: lib.py <scrape-site|progress-get|progress-set|scraped-add|scraped-has|push> [args]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "scrape-site":
        url = sys.argv[2]
        owner, text = scrape_website_full(url, config.get("max_website_text_words", 300))
        print(json.dumps({"owner_name": owner, "website_text": text}))

    elif cmd == "progress-get":
        print(json.dumps(load_progress()))

    elif cmd == "progress-set":
        save_progress(json.loads(sys.argv[2]))
        print("ok")

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
