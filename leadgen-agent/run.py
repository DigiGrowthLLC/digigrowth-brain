import json
import os
import pathlib
import sys
import time
import re
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
import anthropic
from dotenv import load_dotenv

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "shared"))
from github_sync import push_file

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv()

# ── File paths ──────────────────────────────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
MEMORY_FILE   = os.path.join(BASE_DIR, "memory.txt")
ROLE_FILE     = os.path.join(BASE_DIR, "role.txt")
PROMPT_FILE   = os.path.join(BASE_DIR, "prompt.txt")
CONFIG_FILE   = os.path.join(BASE_DIR, "config.json")
PROGRESS_FILE = os.path.join(BASE_DIR, "progress.json")
SCRAPED_FILE  = os.path.join(BASE_DIR, "scraped_ids.json")
STATS_FILE    = os.path.join(BASE_DIR, "qualify_stats.json")

# ── Load config ──────────────────────────────────────────────────────────────
with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = json.load(f)

# ── API clients ───────────────────────────────────────────────────────────────
client = anthropic.Anthropic(api_key=os.environ[config.get("anthropic_api_key_env", "ANTHROPIC_API_KEY")])
PLACES_KEY = os.environ["PLACES_API_KEY"]
HEADERS    = {"User-Agent": "Mozilla/5.0"}

# ── US States ─────────────────────────────────────────────────────────────────
# Ordered by population/market density (biggest first) rather than
# alphabetically — the scraper works through this list in order, so this
# controls which markets get hit soonest. Small/rural states are still
# fully covered, just later in the cycle (see scrape_state_leads()).
US_STATES = {
    "California": ["Los Angeles", "San Diego", "San Jose", "San Francisco", "Sacramento", "Fresno", "Oakland"],
    "Texas": ["Houston", "San Antonio", "Dallas", "Austin", "Fort Worth", "El Paso", "Arlington"],
    "Florida": ["Jacksonville", "Miami", "Tampa", "Orlando", "St. Petersburg", "Hialeah"],
    "New York": ["New York City", "Buffalo", "Rochester", "Yonkers", "Syracuse"],
    "Pennsylvania": ["Philadelphia", "Pittsburgh", "Allentown", "Erie", "Reading"],
    "Illinois": ["Chicago", "Aurora", "Rockford", "Joliet", "Naperville"],
    "Ohio": ["Columbus", "Cleveland", "Cincinnati", "Toledo", "Akron"],
    "Georgia": ["Atlanta", "Augusta", "Columbus", "Macon", "Savannah"],
    "North Carolina": ["Charlotte", "Raleigh", "Greensboro", "Durham", "Winston-Salem"],
    "Michigan": ["Detroit", "Grand Rapids", "Warren", "Sterling Heights", "Lansing"],
    "New Jersey": ["Newark", "Jersey City", "Paterson", "Elizabeth", "Trenton"],
    "Virginia": ["Virginia Beach", "Norfolk", "Chesapeake", "Richmond", "Arlington"],
    "Washington": ["Seattle", "Spokane", "Tacoma", "Vancouver", "Bellevue"],
    "Arizona": ["Phoenix", "Tucson", "Scottsdale", "Mesa", "Chandler"],
    "Massachusetts": ["Boston", "Worcester", "Springfield", "Cambridge", "Lowell"],
    "Tennessee": ["Nashville", "Memphis", "Knoxville", "Chattanooga", "Clarksville"],
    "Indiana": ["Indianapolis", "Fort Wayne", "Evansville", "South Bend"],
    "Missouri": ["Kansas City", "Saint Louis", "Springfield", "Columbia"],
    "Maryland": ["Baltimore", "Frederick", "Rockville", "Gaithersburg"],
    "Wisconsin": ["Milwaukee", "Madison", "Green Bay", "Kenosha", "Racine"],
    "Colorado": ["Denver", "Colorado Springs", "Aurora", "Fort Collins", "Boulder"],
    "Minnesota": ["Minneapolis", "Saint Paul", "Rochester", "Duluth"],
    "South Carolina": ["Columbia", "Charleston", "North Charleston", "Mount Pleasant"],
    "Alabama": ["Birmingham", "Montgomery", "Huntsville", "Mobile", "Tuscaloosa"],
    "Louisiana": ["New Orleans", "Baton Rouge", "Shreveport", "Lafayette"],
    "Kentucky": ["Louisville", "Lexington", "Bowling Green", "Owensboro"],
    "Oregon": ["Portland", "Salem", "Eugene", "Gresham", "Hillsboro"],
    "Oklahoma": ["Oklahoma City", "Tulsa", "Norman", "Broken Arrow"],
    "Connecticut": ["Bridgeport", "New Haven", "Hartford", "Stamford"],
    "Utah": ["Salt Lake City", "West Valley City", "Provo", "West Jordan", "Orem"],
    "Iowa": ["Des Moines", "Cedar Rapids", "Davenport", "Sioux City"],
    "Nevada": ["Las Vegas", "Henderson", "Reno", "North Las Vegas"],
    "Arkansas": ["Little Rock", "Fort Smith", "Fayetteville", "Springdale", "Jonesboro"],
    "Mississippi": ["Jackson", "Gulfport", "Southaven", "Hattiesburg"],
    "Kansas": ["Wichita", "Overland Park", "Kansas City", "Topeka"],
    "New Mexico": ["Albuquerque", "Las Cruces", "Rio Rancho", "Santa Fe"],
    "Nebraska": ["Omaha", "Lincoln", "Bellevue", "Grand Island"],
    "West Virginia": ["Charleston", "Huntington", "Morgantown"],
    "Idaho": ["Boise", "Meridian", "Nampa", "Idaho Falls"],
    "Hawaii": ["Honolulu", "Pearl City", "Hilo"],
    "New Hampshire": ["Manchester", "Nashua", "Concord"],
    "Maine": ["Portland", "Lewiston", "Bangor"],
    "Montana": ["Billings", "Missoula", "Great Falls", "Bozeman"],
    "Rhode Island": ["Providence", "Cranston", "Warwick", "Pawtucket"],
    "Delaware": ["Wilmington", "Dover", "Newark"],
    "South Dakota": ["Sioux Falls", "Rapid City", "Aberdeen"],
    "North Dakota": ["Fargo", "Bismarck", "Grand Forks"],
    "Alaska": ["Anchorage", "Fairbanks", "Juneau"],
    "Vermont": ["Burlington", "South Burlington", "Rutland"],
    "Wyoming": ["Cheyenne", "Casper", "Laramie"]
}

SEARCH_TERMS = [
    "mobile physical therapist",
    "in-home physical therapy",
    "house call physical therapist",
    "mobile rehabilitation therapy"
]

CHAIN_KEYWORDS = [
    "ati physical therapy", "athletico", "us physical therapy", "select physical therapy",
    "select medical", "ivy rehab", "fyzical therapy", "cora physical therapy",
    "novacare rehabilitation", "results physiotherapy", "bayada home health",
    "interim healthcare", "amedisys", "lhc group", "encompass health"
]

# Free, pre-AI disqualification signal — Google Places "New" API returns a
# `types` list at no extra cost (same pricing tier as the fields we already
# request), so we ask for it and reject obvious non-PT institutional
# categories before a candidate is even counted toward the raw-lead cap,
# let alone sent to the (paid, batched) AI qualification call.
NON_PT_PLACE_TYPES = {
    "hospital", "home_health_care_service", "nursing_home", "hospice",
    "urgent_care_center", "medical_clinic", "chiropractor", "government_office",
}

# Same idea applied to the business name — catches obvious non-PT/institutional
# businesses even when Google's type data is missing or too generic (e.g.
# "health") to safely filter on alone. Kept conservative/specific so a
# legitimate small PT practice with "rehab"/"therapy"/"wellness" in its name
# never gets caught by this.
NON_PT_NAME_KEYWORDS = [
    "hospital", "home health", "nursing home", "skilled nursing", "hospice",
    "urgent care", "behavioral health", "addiction", "mental health",
    "psychiatric", "chiropractic", "chiropractor", "home care",
    "va medical", "rehabilitation hospital", "assisted living", "senior living",
    "physical therapy school", "university",
]


def _looks_like_non_pt(name: str, types: list) -> bool:
    """Cheap pre-AI filter: True if this is obviously not an independent PT
    practice (hospital, home health agency, chiropractor, etc.) based on
    Places API type data or the business name alone — no API/model cost."""
    types_lower = {t.lower() for t in (types or [])}
    if types_lower & NON_PT_PLACE_TYPES:
        return True
    name_lower = name.lower()
    return any(kw in name_lower for kw in NON_PT_NAME_KEYWORDS)



# ════════════════════════════════════════════════════════════════════════════
#  PROGRESS TRACKING
# ════════════════════════════════════════════════════════════════════════════

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "current_state_index": 0,
        "current_city_index": 0,
        "current_term_index": 0,
        "states": list(US_STATES.keys())
    }

def save_progress(progress):
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2)

def load_scraped_ids():
    if os.path.exists(SCRAPED_FILE):
        with open(SCRAPED_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_scraped_ids(ids):
    with open(SCRAPED_FILE, "w", encoding="utf-8") as f:
        json.dump(list(ids), f)

def log_qualify_stats(raw_leads, candidates, qualified):
    """Appends one entry per run recording how much of the raw-lead pool
    (cap = daily_limit * 6) survives each free filtering stage vs. Claude
    qualification — pure observability, no effect on pipeline behavior.
    Lets the cap multiplier eventually be right-sized against real data
    instead of guessed."""
    entries = []
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            entries = json.load(f)
    entries.append({
        "date":               datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d"),
        "raw_leads":          raw_leads,
        "candidates":         candidates,
        "qualified":          qualified,
        "qualify_ratio":      round(qualified / raw_leads, 4) if raw_leads else None,
    })
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)


# ════════════════════════════════════════════════════════════════════════════
#  MEMORY SYSTEM
# ════════════════════════════════════════════════════════════════════════════

def read_memory():
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        return f.read()

def update_memory(new_information):
    relevant_keywords = [
        "chain", "franchise", "blacklist", "niche", "market", "qualify",
        "disqualify", "criteria", "location", "target", "owner",
        "physical therapist", "physical therapy", "pt", "dpt", "mobile", "in-home", "house call",
        "practice", "clinic", "hospital", "rehab"
    ]
    if not any(word in new_information.lower() for word in relevant_keywords):
        print("⚠️  Not saved — not relevant to lead generation or agent role.")
        return
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n[{timestamp}] {new_information}"
    with open(MEMORY_FILE, "a", encoding="utf-8") as f:
        f.write(entry)
    print(f"✅ Memory updated: {new_information}")
    push_file(__file__, "memory.txt")


# ════════════════════════════════════════════════════════════════════════════
#  GOOGLE MAPS SCRAPER
# ════════════════════════════════════════════════════════════════════════════

PLACES_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

# Google's Places API (New) bills per REQUEST at the highest-tier field
# requested — NOT per place returned in that request's response (confirmed
# against current docs: https://developers.google.com/maps/documentation/places/web-service/usage-and-billing).
# So one searchText call already returns up to ~20 places' worth of data,
# including phone/website, for a single per-request charge. Splitting phone/
# website into a separate Place Details call per surviving candidate (as a
# prior version of this file did) multiplies request count instead of
# reducing it — it was a net cost INCREASE, not a saving. Keep it as one call.
PLACES_FIELD_MASK = "places.id,places.displayName,places.formattedAddress,places.internationalPhoneNumber,places.websiteUri,places.types"

def search_places(query):
    """Places API (New) searchText — returns name, address, phone, and website
    in a single call. Free chain/non-PT filtering (see _looks_like_non_pt)
    still runs on the response before a result becomes a raw_lead — that
    doesn't reduce this call's cost (already paid per-request regardless of
    result count) but does cut the volume of candidates that reach the
    (paid) Claude qualification step downstream."""
    headers = {
        "Content-Type":    "application/json",
        "X-Goog-Api-Key":  PLACES_KEY,
        "X-Goog-FieldMask": PLACES_FIELD_MASK,
    }
    try:
        res  = requests.post(PLACES_SEARCH_URL, headers=headers, json={"textQuery": query}, timeout=10)
        data = res.json()
        if "error" in data:
            print(f"    ⚠️  API error: {data['error'].get('message','')}")
            return []
        return data.get("places", [])
    except Exception as e:
        print(f"    ❌ Search error: {e}")
        return []


# Safety bound on how many states a single run will cross while topping up
# the raw-lead pool — protects runtime/API cost if the cursor lands on a long
# stretch of very low-yield markets back to back. Coverage isn't affected:
# the cursor just resumes exactly where it left off on the next run.
MAX_STATES_PER_RUN = 10

# Overall safety bound across every top-up round in a single run (see the
# scrape/qualify loop in run_pipeline). Protects against chasing an
# unreachable daily_limit across dozens of low-yield states in one sitting.
MAX_STATES_TOTAL = 40


def _scrape_current_state(progress, scraped_ids, raw_leads, cap):
    """Scrapes from the current city/term position onward within the
    current state, appending pre-filtered candidates to raw_leads. Returns
    True if the cap was reached (caller should stop), False if this state
    was fully exhausted without reaching it (caller should advance state)."""
    state_name = progress["states"][progress["current_state_index"]]
    cities     = list(US_STATES[state_name])

    print(f"\n🗺️  Current state: {state_name}")

    city_index = progress["current_city_index"]
    term_index = progress["current_term_index"]

    while city_index < len(cities):
        city = cities[city_index]

        while term_index < len(SEARCH_TERMS):
            term  = SEARCH_TERMS[term_index]
            query = f"{term} in {city}, {state_name}"
            print(f"  🔍 Searching: {query}")

            results = search_places(query)

            for place in results:
                place_id = place.get("id")
                if not place_id or place_id in scraped_ids:
                    continue
                name  = place.get("displayName", {}).get("text", "")
                types = place.get("types", [])
                if any(chain in name.lower() for chain in CHAIN_KEYWORDS):
                    scraped_ids.add(place_id)
                    continue
                if _looks_like_non_pt(name, types):
                    scraped_ids.add(place_id)
                    print(f"    ⏭️  Skipped (obviously not independent PT): {name}")
                    continue
                scraped_ids.add(place_id)
                raw_leads.append({
                    "place_id": place_id,
                    "name":     name,
                    "address":  place.get("formattedAddress", ""),
                    "phone":    place.get("internationalPhoneNumber", ""),
                    "website":  place.get("websiteUri", ""),
                    "state":    state_name,
                    "city":     city
                })
                if len(raw_leads) >= cap:
                    progress["current_city_index"] = city_index
                    progress["current_term_index"] = term_index
                    save_progress(progress)
                    save_scraped_ids(scraped_ids)
                    return True

            term_index += 1

        city_index += 1
        term_index  = 0
        progress["current_city_index"] = city_index
        progress["current_term_index"] = 0
        save_progress(progress)

    # Finished state — advance
    print(f"\n✅ Finished {state_name} — moving to next state")
    progress["current_state_index"] += 1
    progress["current_city_index"]   = 0
    progress["current_term_index"]   = 0

    if progress["current_state_index"] >= len(progress["states"]):
        print("🎉 All 50 states done — restarting!")
        progress["current_state_index"] = 0

    save_progress(progress)
    save_scraped_ids(scraped_ids)
    return False


def scrape_state_leads(progress, scraped_ids, daily_limit):
    """Tops up the raw-lead pool to daily_limit*6, crossing into as many
    subsequent states as needed (bounded by MAX_STATES_PER_RUN) so a run
    landing on a low-yield market still comes back with a full candidate
    pool instead of stopping the moment the current state runs dry.
    Returns (raw_leads, states_crossed) — the caller uses states_crossed
    to enforce an overall safety bound across repeated top-up calls."""
    raw_leads = []
    cap       = daily_limit * 6
    states_crossed = 0

    for _ in range(MAX_STATES_PER_RUN):
        reached_cap = _scrape_current_state(progress, scraped_ids, raw_leads, cap)
        states_crossed += 1
        if reached_cap:
            break
    else:
        print(f"⚠️  Crossed {MAX_STATES_PER_RUN} states this run without filling the pool "
              f"({len(raw_leads)}/{cap}) — stopping here for today.")

    return raw_leads, states_crossed


# ════════════════════════════════════════════════════════════════════════════
#  WEBSITE SCRAPER + OWNER LOOKUP (single pass — no Claude calls)
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

def _valid_name(s):
    words = s.strip().split()
    if not (2 <= len(words) <= 3):
        return False
    if not words[0][0].isupper():
        return False
    if any(w.lower() in _NAME_STOPWORDS for w in words):
        return False
    return True

def extract_owner_regex(text):
    """Rule-based name extraction from any text block."""
    for pattern in _OWNER_PATTERNS:
        m = re.search(pattern, text)
        if m and _valid_name(m.group(1)):
            return m.group(1).strip()
    return ""


# Sentences containing any of these are moved to the front before truncating
# to max_words — lets a smaller word budget still capture the exact evidence
# the qualification prompt looks for (mobile/in-home disclosure, owner name)
# instead of losing it to generic filler earlier on the page.
_SIGNAL_KEYWORDS = [
    "mobile", "in-home", "in home", "house call", "we come to you",
    "dr.", "founder", "owner",
]

def _prioritized_truncate(text, max_words):
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


def scrape_website_full(url, max_words=600):
    """Single-pass scrape of homepage + /about + /about-us.

    Returns (owner_name, content_text) where owner_name comes from JSON-LD or
    regex on page text (no Claude call). content_text is truncated for Claude
    qualification. Replaces both find_owner_from_website() and scrape_website().
    """
    if not url:
        return "", ""
    pages = [
        url.rstrip("/"),
        url.rstrip("/") + "/about",
        url.rstrip("/") + "/about-us",
    ]
    jsonld_owner = ""
    text_chunks  = []
    for page_url in pages:
        try:
            res = requests.get(page_url, headers=HEADERS, timeout=8)
            if res.status_code != 200:
                continue
            soup = BeautifulSoup(res.text, "html.parser")
            # JSON-LD structured data — fastest, most reliable
            if not jsonld_owner:
                for script in soup.find_all("script", type="application/ld+json"):
                    try:
                        data = json.loads(script.string or "")
                        if isinstance(data, dict):
                            for field in ("founder", "owner"):
                                val = data.get(field)
                                candidate = (val.get("name") if isinstance(val, dict) else val) or ""
                                if candidate and _valid_name(candidate):
                                    jsonld_owner = candidate.strip()
                                    break
                    except Exception:
                        continue
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            text_chunks.append(soup.get_text(separator=" ", strip=True))
        except Exception:
            continue

    all_text     = " ".join(text_chunks)
    content_text = _prioritized_truncate(all_text, max_words)

    if jsonld_owner:
        return jsonld_owner, content_text

    # Regex fallback on page text
    name = extract_owner_regex(all_text)
    return name, content_text


def find_owner_name(website_url, max_words=600):
    """Free owner lookup: JSON-LD → page regex. Zero Claude calls."""
    print(f"    🔍 Checking website...")
    owner, content_text = scrape_website_full(website_url, max_words)
    if owner:
        print(f"    ✅ Found on website: {owner}")
        return owner, content_text

    print(f"    ⚠️  No owner found")
    return "", content_text


# ════════════════════════════════════════════════════════════════════════════
#  LEAD QUALIFIER (Message Batches API — 50% cheaper than sync calls; this is
#  a scheduled job with no need for real-time responses)
# ════════════════════════════════════════════════════════════════════════════

BATCH_POLL_INTERVAL_SEC = 20
BATCH_MAX_WAIT_SEC      = 30 * 60

def _qualify_message_params(business_name, phone, website_url, owner_name, website_text, role, memory):
    prompt = open(PROMPT_FILE, encoding="utf-8").read()
    filled = (
        prompt
        .replace("{business_name}", business_name)
        .replace("{phone}",         phone)
        .replace("{website_url}",   website_url)
        .replace("{owner_name}",    owner_name)
        .replace("{website_text}",  website_text)
    )
    return {
        "model": config["model"],
        "max_tokens": 500,
        "system": [{
            "type": "text",
            "text": f"{role}\n\nAgent memory and criteria:\n{memory}",
            "cache_control": {"type": "ephemeral"}
        }],
        "messages": [{"role": "user", "content": filled}]
    }


def _parse_qualify_response(raw_text):
    try:
        return json.loads(raw_text.replace("```json", "").replace("```", "").strip())
    except json.JSONDecodeError:
        return {
            "qualified": False, "grade": "D",
            "grade_reason": "Parse error",
            "disqualify_reason": f"Unparseable: {raw_text[:100]}",
            "niche_confirmed": False, "niche_notes": "", "opener": None
        }


def qualify_leads_batch(candidates, role, memory):
    """candidates: list of dicts with place_id/name/phone/website/owner_name/website_text.
    Returns {place_id: parsed_result_dict} for every candidate submitted."""
    if not candidates:
        return {}

    requests_payload = [
        {
            "custom_id": c["place_id"],
            "params": _qualify_message_params(
                c["name"], c["phone"], c["website"], c["owner_name"], c["website_text"], role, memory
            )
        }
        for c in candidates
    ]

    print(f"  📦 Submitting batch of {len(requests_payload)} qualification requests...")
    batch = client.messages.batches.create(requests=requests_payload)
    print(f"  📦 Batch {batch.id} submitted — polling for completion...")

    waited = 0
    while batch.processing_status != "ended":
        if waited >= BATCH_MAX_WAIT_SEC:
            print(f"  ⚠️  Batch not finished after {BATCH_MAX_WAIT_SEC}s — proceeding with partial/no results.")
            break
        time.sleep(BATCH_POLL_INTERVAL_SEC)
        waited += BATCH_POLL_INTERVAL_SEC
        batch = client.messages.batches.retrieve(batch.id)

    results = {}
    if batch.processing_status == "ended":
        for entry in client.messages.batches.results(batch.id):
            if entry.result.type == "succeeded":
                text = entry.result.message.content[0].text.strip()
                results[entry.custom_id] = _parse_qualify_response(text)
            else:
                results[entry.custom_id] = {
                    "qualified": False, "grade": "D",
                    "grade_reason": "Batch error",
                    "disqualify_reason": f"Batch result type: {entry.result.type}",
                    "niche_confirmed": False, "niche_notes": "", "opener": None
                }
    return results


# ════════════════════════════════════════════════════════════════════════════
#  RULE-BASED PRE-FILTER
# ════════════════════════════════════════════════════════════════════════════

def rule_based_filter(phone, website):
    # Chain names are already filtered out in scrape_state_leads() before a
    # candidate ever reaches raw_leads, so no re-check needed here.
    if not phone:
        return False, "No phone number"
    if not website:
        return False, "No website"
    return True, ""


# ════════════════════════════════════════════════════════════════════════════
#  DIGIGROWTH OS EXPORT
# ════════════════════════════════════════════════════════════════════════════

def push_to_os(leads, lead_status="dialer-lead"):
    if not leads:
        print("No qualified leads to push.")
        return
    base_url = os.environ.get("DASHBOARD_URL", "").rstrip("/")
    password = os.environ.get("DASHBOARD_PASSWORD", "")
    auth     = ("admin", password)
    grade_order = {"A": 0, "B": 1, "C": 2, "D": 3}
    pushed = 0
    for lead in sorted(leads, key=lambda r: grade_order.get(r.get("Grade", "D"), 3)):
        body = {
            "business": lead["Business Name"],
            "owner":    lead["Owner Name"],
            "phone":    lead["Phone"],
            "email":    lead["Email"],
            "website":  lead["Website"],
            "city":     lead["City"],
            "state":    lead["State"],
            "grade":    lead["Grade"],
            "opener":   lead["Opener"],
            "notes":    lead["Grade Reason"],
            "status":   lead_status,
            "tags":     ["mobile-pt"],
        }
        try:
            r = requests.post(f"{base_url}/api/contacts", auth=auth, json=body, timeout=10)
            r.raise_for_status()
            pushed += 1
            time.sleep(0.3)
        except Exception as e:
            print(f"  ⚠️  OS push failed for {lead['Business Name']}: {e}")
    print(f"✅ {pushed}/{len(leads)} leads pushed to DigiGrowth OS (status={lead_status}).")


# ════════════════════════════════════════════════════════════════════════════
#  MAIN PIPELINE
# ════════════════════════════════════════════════════════════════════════════

def run_pipeline(lead_status="dialer-lead"):
    if not config.get("enabled", True):
        print("⏸️  Agent disabled via config.json (set \"enabled\": true to resume) — skipping run.")
        return
    now_et = datetime.now(ZoneInfo("America/New_York"))
    if now_et.weekday() >= 5:
        print("⏸️  Weekend — skipping run.")
        return
    progress    = load_progress()
    scraped_ids = load_scraped_ids()
    daily_limit = config.get("daily_lead_limit", 10)

    print(f"📅 {now_et.strftime('%A, %B %d %Y')}")
    print(f"📊 Total leads scraped so far: {len(scraped_ids)}")
    print(f"🏷️  Lead status: {lead_status}")
    print(f"\n🌎 Scraping Google Maps...")

    role   = open(ROLE_FILE, encoding="utf-8").read()
    memory = read_memory()

    # Loop: scrape → filter → qualify, and if the qualified pool still falls
    # short of daily_limit, go back for another batch of raw leads instead of
    # settling for whatever the first pass happened to yield. Bounded by
    # MAX_STATES_TOTAL across the whole run so a run of back-to-back low-yield
    # markets can't blow up runtime/API cost chasing an unreachable target.
    all_qualified  = []
    total_states_crossed = 0
    round_num = 0
    # Pass-through instrumentation — no effect on pipeline behavior, just
    # logs how much of the raw-lead pool (cap = daily_limit * 6) actually
    # survives each filtering stage, so the multiplier can eventually be
    # right-sized against real data instead of guessed.
    total_raw_leads  = 0
    total_candidates = 0

    while len(all_qualified) < daily_limit and total_states_crossed < MAX_STATES_TOTAL:
        round_num += 1
        remaining = daily_limit - len(all_qualified)
        print(f"\n🔁 Round {round_num}: need {remaining} more qualified lead(s)")

        raw_leads, states_crossed = scrape_state_leads(progress, scraped_ids, remaining)
        total_states_crossed += states_crossed
        total_raw_leads      += len(raw_leads)
        print(f"📋 Raw leads collected this round: {len(raw_leads)}")

        if not raw_leads:
            print("❌ No raw leads found this round — stopping.")
            break

        # Phase 1: free filtering + website scraping (no Claude cost). Places
        # API (New) already returned phone/website in scrape_state_leads — no
        # separate Details call needed.
        candidates = []
        for lead in raw_leads:
            name    = lead["name"]
            phone   = lead.get("phone", "")
            website = lead.get("website", "")

            keep, reason = rule_based_filter(phone, website)
            if not keep:
                print(f"  ⏭️  Skipped {name}: {reason}")
                continue

            owner_name, website_text = find_owner_name(website, config.get("max_website_text_words", 600))
            candidates.append({
                **lead,
                "phone": phone, "website": website,
                "owner_name": owner_name, "website_text": website_text,
            })

        total_candidates += len(candidates)
        print(f"📋 Candidates passing rule filter: {len(candidates)}/{len(raw_leads)}")

        if not candidates:
            continue

        # Phase 2: one batch of qualification calls (Message Batches API —
        # 50% cheaper than synchronous calls; fine for a scheduled,
        # non-interactive job)
        results_by_id = qualify_leads_batch(candidates, role, memory)

        for c in candidates:
            result = results_by_id.get(c["place_id"])
            if not result:
                continue
            if not result.get("qualified"):
                print(f"  ❌ Disqualified {c['name']}: {result.get('disqualify_reason')}")
                continue

            grade          = result.get("grade", "C")
            verified_owner = result.get("verified_owner_name") or ""
            if not _valid_name(verified_owner):
                print(f"  ❌ Disqualified {c['name']}: no verified owner name (model said qualified, overriding)")
                continue
            opener         = result.get("opener") or ""
            if opener and len(opener.split()) > 15:
                print(f"  ⚠️  Opener too long ({len(opener.split())} words) — nulled")
                opener = ""
            if opener and "?" in opener:
                print(f"  ⚠️  Opener has question mark — nulled")
                opener = ""
            # Rule: a lead with no custom opener doesn't get pushed to the OS —
            # better to drop it here than hand off a generic/cold lead with
            # nothing personalized to open with.
            if not opener:
                print(f"  ❌ Disqualified {c['name']}: no usable custom opener")
                continue
            print(f"  ✅ {c['name']} — Grade: {grade} | Owner: {verified_owner} | Opener: {opener}")
            all_qualified.append({
                "Business Name":     c["name"],
                "Phone":             c["phone"],
                "Website":           c["website"],
                "Address":           c.get("address", ""),
                "Email":             "",
                "Owner Name":        verified_owner,
                "Grade":             grade,
                "Grade Reason":      result.get("grade_reason", ""),
                "Qualified":         "Yes",
                "Niche Notes":       result.get("niche_notes", ""),
                "Disqualify Reason": "",
                "Opener":            opener,
                "Notes":             "",
                "State":             c.get("state", ""),
                "City":              c.get("city", "")
            })

    if total_states_crossed >= MAX_STATES_TOTAL and len(all_qualified) < daily_limit:
        print(f"⚠️  Hit the {MAX_STATES_TOTAL}-state safety bound with only "
              f"{len(all_qualified)}/{daily_limit} qualified — stopping here for today.")

    grade_order = {"A": 0, "B": 1, "C": 2, "D": 3}
    all_qualified.sort(key=lambda r: grade_order.get(r.get("Grade", "D"), 3))
    qualified_leads = all_qualified

    print(f"\n📊 Results: {len(qualified_leads)} qualified, pushing all (target={daily_limit})")
    log_qualify_stats(total_raw_leads, total_candidates, len(qualified_leads))
    push_to_os(qualified_leads, lead_status)
    push_file(__file__, "progress.json")
    push_file(__file__, "scraped_ids.json")
    push_file(__file__, "qualify_stats.json")


# ════════════════════════════════════════════════════════════════════════════
#  ENTRY POINTS
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", default="dialer-lead",
                        choices=["dialer-lead", "sms-handoff", "new"],
                        help="CRM status for pushed leads")
    args, remaining = parser.parse_known_args()

    if remaining and remaining[0] == "remember":
        update_memory(" ".join(remaining[1:]))
    else:
        try:
            run_pipeline(args.status)
        except Exception:
            import traceback
            error_log = os.path.join(BASE_DIR, "error.log")
            trace = traceback.format_exc()
            with open(error_log, "a", encoding="utf-8") as f:
                f.write(f"\n[{datetime.now(ZoneInfo('America/New_York')).isoformat()}]\n{trace}")
            print(trace)
            push_file(__file__, "error.log")
            raise