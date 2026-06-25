import json
import os
import pathlib
import sys
import time
import re
import requests
from datetime import datetime
from bs4 import BeautifulSoup
import anthropic
from dotenv import load_dotenv

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "shared"))
from github_sync import push_file

load_dotenv()

# ── File paths ──────────────────────────────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
MEMORY_FILE   = os.path.join(BASE_DIR, "memory.txt")
ROLE_FILE     = os.path.join(BASE_DIR, "role.txt")
PROMPT_FILE   = os.path.join(BASE_DIR, "prompt.txt")
CONFIG_FILE   = os.path.join(BASE_DIR, "config.json")
PROGRESS_FILE = os.path.join(BASE_DIR, "progress.json")
SCRAPED_FILE  = os.path.join(BASE_DIR, "scraped_ids.json")

# ── Load config ──────────────────────────────────────────────────────────────
with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = json.load(f)

# ── API clients ───────────────────────────────────────────────────────────────
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
PLACES_KEY = os.environ["PLACES_API_KEY"]
HEADERS    = {"User-Agent": "Mozilla/5.0"}

# ── US States ─────────────────────────────────────────────────────────────────
US_STATES = {
    "Alabama": ["Birmingham", "Montgomery", "Huntsville", "Mobile", "Tuscaloosa"],
    "Alaska": ["Anchorage", "Fairbanks", "Juneau"],
    "Arizona": ["Phoenix", "Tucson", "Scottsdale", "Mesa", "Chandler"],
    "Arkansas": ["Little Rock", "Fort Smith", "Fayetteville", "Springdale", "Jonesboro"],
    "California": ["Los Angeles", "San Diego", "San Jose", "San Francisco", "Sacramento", "Fresno", "Oakland"],
    "Colorado": ["Denver", "Colorado Springs", "Aurora", "Fort Collins", "Boulder"],
    "Connecticut": ["Bridgeport", "New Haven", "Hartford", "Stamford"],
    "Delaware": ["Wilmington", "Dover", "Newark"],
    "Florida": ["Jacksonville", "Miami", "Tampa", "Orlando", "St. Petersburg", "Hialeah"],
    "Georgia": ["Atlanta", "Augusta", "Columbus", "Macon", "Savannah"],
    "Hawaii": ["Honolulu", "Pearl City", "Hilo"],
    "Idaho": ["Boise", "Meridian", "Nampa", "Idaho Falls"],
    "Illinois": ["Chicago", "Aurora", "Rockford", "Joliet", "Naperville"],
    "Indiana": ["Indianapolis", "Fort Wayne", "Evansville", "South Bend"],
    "Iowa": ["Des Moines", "Cedar Rapids", "Davenport", "Sioux City"],
    "Kansas": ["Wichita", "Overland Park", "Kansas City", "Topeka"],
    "Kentucky": ["Louisville", "Lexington", "Bowling Green", "Owensboro"],
    "Louisiana": ["New Orleans", "Baton Rouge", "Shreveport", "Lafayette"],
    "Maine": ["Portland", "Lewiston", "Bangor"],
    "Maryland": ["Baltimore", "Frederick", "Rockville", "Gaithersburg"],
    "Massachusetts": ["Boston", "Worcester", "Springfield", "Cambridge", "Lowell"],
    "Michigan": ["Detroit", "Grand Rapids", "Warren", "Sterling Heights", "Lansing"],
    "Minnesota": ["Minneapolis", "Saint Paul", "Rochester", "Duluth"],
    "Mississippi": ["Jackson", "Gulfport", "Southaven", "Hattiesburg"],
    "Missouri": ["Kansas City", "Saint Louis", "Springfield", "Columbia"],
    "Montana": ["Billings", "Missoula", "Great Falls", "Bozeman"],
    "Nebraska": ["Omaha", "Lincoln", "Bellevue", "Grand Island"],
    "Nevada": ["Las Vegas", "Henderson", "Reno", "North Las Vegas"],
    "New Hampshire": ["Manchester", "Nashua", "Concord"],
    "New Jersey": ["Newark", "Jersey City", "Paterson", "Elizabeth", "Trenton"],
    "New Mexico": ["Albuquerque", "Las Cruces", "Rio Rancho", "Santa Fe"],
    "New York": ["New York City", "Buffalo", "Rochester", "Yonkers", "Syracuse"],
    "North Carolina": ["Charlotte", "Raleigh", "Greensboro", "Durham", "Winston-Salem"],
    "North Dakota": ["Fargo", "Bismarck", "Grand Forks"],
    "Ohio": ["Columbus", "Cleveland", "Cincinnati", "Toledo", "Akron"],
    "Oklahoma": ["Oklahoma City", "Tulsa", "Norman", "Broken Arrow"],
    "Oregon": ["Portland", "Salem", "Eugene", "Gresham", "Hillsboro"],
    "Pennsylvania": ["Philadelphia", "Pittsburgh", "Allentown", "Erie", "Reading"],
    "Rhode Island": ["Providence", "Cranston", "Warwick", "Pawtucket"],
    "South Carolina": ["Columbia", "Charleston", "North Charleston", "Mount Pleasant"],
    "South Dakota": ["Sioux Falls", "Rapid City", "Aberdeen"],
    "Tennessee": ["Nashville", "Memphis", "Knoxville", "Chattanooga", "Clarksville"],
    "Texas": ["Houston", "San Antonio", "Dallas", "Austin", "Fort Worth", "El Paso", "Arlington"],
    "Utah": ["Salt Lake City", "West Valley City", "Provo", "West Jordan", "Orem"],
    "Vermont": ["Burlington", "South Burlington", "Rutland"],
    "Virginia": ["Virginia Beach", "Norfolk", "Chesapeake", "Richmond", "Arlington"],
    "Washington": ["Seattle", "Spokane", "Tacoma", "Vancouver", "Bellevue"],
    "West Virginia": ["Charleston", "Huntington", "Morgantown"],
    "Wisconsin": ["Milwaukee", "Madison", "Green Bay", "Kenosha", "Racine"],
    "Wyoming": ["Cheyenne", "Casper", "Laramie"]
}

SEARCH_TERMS = [
    "mobile veterinarian",
    "mobile vet",
    "in-home vet",
    "house call vet",
    "mobile animal hospital",
    "mobile pet clinic",
    "in-home veterinary"
]

CHAIN_KEYWORDS = [
    "vca animal", "banfield", "petsmart vets", "vetco", "bluepearl",
    "thrive pet", "petiq", "lap of love", "national veterinary",
    "humane society", "spca", "aspca", "animal shelter",
    "animal emergency", "emergency animal", "university veterinary",
    "college of veterinary"
]



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


# ════════════════════════════════════════════════════════════════════════════
#  MEMORY SYSTEM
# ════════════════════════════════════════════════════════════════════════════

def read_memory():
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        return f.read()

def update_memory(new_information):
    relevant_keywords = [
        "chain", "franchise", "blacklist", "niche", "market", "qualify",
        "disqualify", "training", "gym", "studio", "fitness", "criteria",
        "location", "target", "owner", "semi-private", "private"
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

def search_places(query):
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {"query": query, "key": PLACES_KEY}
    try:
        res  = requests.get(url, params=params, timeout=10)
        data = res.json()
        if data.get("status") not in ["OK", "ZERO_RESULTS"]:
            print(f"    ⚠️  API status: {data.get('status')} — {data.get('error_message','')}")
            return []
        return data.get("results", [])
    except Exception as e:
        print(f"    ❌ Search error: {e}")
        return []


def get_place_details(place_id):
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": "name,formatted_phone_number,website,formatted_address,reviews",
        "key": PLACES_KEY
    }
    try:
        res  = requests.get(url, params=params, timeout=10)
        data = res.json()
        if data.get("status") == "OK":
            return data.get("result", {})
    except Exception:
        pass
    return {}


def scrape_state_leads(progress, scraped_ids, daily_limit):
    raw_leads  = []
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
                place_id = place.get("place_id")
                if not place_id or place_id in scraped_ids:
                    continue
                name = place.get("name", "")
                if any(chain in name.lower() for chain in CHAIN_KEYWORDS):
                    scraped_ids.add(place_id)
                    continue
                scraped_ids.add(place_id)
                raw_leads.append({
                    "place_id": place_id,
                    "name":     name,
                    "address":  place.get("formatted_address", ""),
                    "state":    state_name,
                    "city":     city
                })
                if len(raw_leads) >= daily_limit * 6:
                    progress["current_city_index"] = city_index
                    progress["current_term_index"] = term_index
                    save_progress(progress)
                    save_scraped_ids(scraped_ids)
                    return raw_leads

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
    return raw_leads


# ════════════════════════════════════════════════════════════════════════════
#  WEBSITE SCRAPER + OWNER LOOKUP (single pass — no Claude calls)
# ════════════════════════════════════════════════════════════════════════════

_OWNER_PATTERNS = [
    r"(?:Dr|Doctor)\.?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})(?:\s*,?\s*DVM)?",
    r"(?:Founded|Owned)\s+by\s+([A-Z][a-z]+\s+[A-Z][a-z]+)",
    r"I(?:'m| am)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*,?\s*(?:a\s+)?(?:mobile\s+)?vet",
    r"(?:Owner|Veterinarian|Founder)[:\s]+([A-Z][a-z]+\s+[A-Z][a-z]+)",
]

def _valid_name(s):
    words = s.strip().split()
    return 2 <= len(words) <= 3 and words[0][0].isupper()

def extract_owner_regex(text):
    """Rule-based name extraction from any text block."""
    for pattern in _OWNER_PATTERNS:
        m = re.search(pattern, text)
        if m and _valid_name(m.group(1)):
            return m.group(1).strip()
    return ""


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
    content_text = " ".join(all_text.split()[:max_words])

    if jsonld_owner:
        return jsonld_owner, content_text

    # Regex fallback on page text
    name = extract_owner_regex(all_text)
    return name, content_text


def find_owner_name(business_name, reviews, website_url):
    """Free owner lookup: JSON-LD → page regex → review regex. Zero Claude calls."""
    print(f"    🔍 Checking website...")
    owner, content_text = scrape_website_full(website_url)
    if owner:
        print(f"    ✅ Found on website: {owner}")
        return owner, content_text

    # Regex on already-fetched Maps reviews (no extra API call)
    if reviews:
        review_text = " ".join(r.get("text", "") for r in reviews[:5])
        owner = extract_owner_regex(review_text)
        if owner:
            print(f"    ✅ Found in reviews: {owner}")
            return owner, content_text

    print(f"    ⚠️  No owner found")
    return "", content_text


# ════════════════════════════════════════════════════════════════════════════
#  LEAD QUALIFIER
# ════════════════════════════════════════════════════════════════════════════

def qualify_lead(business_name, phone, website_url, owner_name, address, website_text, role, memory):
    prompt   = open(PROMPT_FILE, encoding="utf-8").read()
    filled   = (
        prompt
        .replace("{business_name}", business_name)
        .replace("{phone}",         phone)
        .replace("{website_url}",   website_url)
        .replace("{owner_name}",    owner_name)
        .replace("{website_text}",  website_text)
    )
    response = client.messages.create(
        model=config["model"],
        max_tokens=500,
        system=[{
            "type": "text",
            "text": f"{role}\n\nAgent memory and criteria:\n{memory}",
            "cache_control": {"type": "ephemeral"}
        }],
        messages=[{"role": "user", "content": filled}]
    )
    usage = response.usage
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
    if cache_read or cache_write:
        print(f"  💾 Cache: read={cache_read} write={cache_write}")
    raw = response.content[0].text.strip()
    try:
        return json.loads(raw.replace("```json", "").replace("```", "").strip()), cache_read > 0
    except json.JSONDecodeError:
        return {
            "qualified": False, "grade": "D",
            "grade_reason": "Parse error",
            "disqualify_reason": f"Unparseable: {raw[:100]}",
            "niche_confirmed": False, "niche_notes": "", "opener": None
        }, cache_read > 0


# ════════════════════════════════════════════════════════════════════════════
#  RULE-BASED PRE-FILTER
# ════════════════════════════════════════════════════════════════════════════

def rule_based_filter(name, phone, website):
    if not phone:
        return False, "No phone number"
    if not website:
        return False, "No website"
    for chain in CHAIN_KEYWORDS:
        if chain in name.lower():
            return False, f"Chain detected: {chain}"
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
            "tags":     ["mobile-vet"],
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
    if datetime.now().weekday() >= 5:
        print("⏸️  Weekend — skipping run.")
        return
    progress    = load_progress()
    scraped_ids = load_scraped_ids()
    daily_limit = config.get("daily_lead_limit", 10)

    print(f"📅 {datetime.now().strftime('%A, %B %d %Y')}")
    print(f"📊 Total leads scraped so far: {len(scraped_ids)}")
    print(f"🏷️  Lead status: {lead_status}")
    print(f"\n🌎 Scraping Google Maps...")

    role   = open(ROLE_FILE, encoding="utf-8").read()
    memory = read_memory()

    raw_leads = scrape_state_leads(progress, scraped_ids, daily_limit)
    print(f"📋 Raw leads collected: {len(raw_leads)}")

    if not raw_leads:
        print("❌ No raw leads found.")
        return

    qualified_leads = []
    processed       = 0
    cache_hits      = 0

    for lead in raw_leads:
        if len(qualified_leads) >= daily_limit:
            break

        processed += 1
        name      = lead["name"]
        place_id  = lead["place_id"]
        print(f"\n[{processed}/{len(raw_leads)}] Processing: {name}")

        details = get_place_details(place_id)
        phone   = details.get("formatted_phone_number", "")
        website = details.get("website", "")
        address = details.get("formatted_address", lead.get("address", ""))
        reviews = details.get("reviews", [])

        keep, reason = rule_based_filter(name, phone, website)
        if not keep:
            print(f"  ⏭️  Skipped: {reason}")
            continue

        # Single-pass scrape: owner extraction (JSON-LD → regex) + content text
        owner_name, website_text = find_owner_name(name, reviews, website)
        if not owner_name:
            print(f"  ⏭️  Skipped: No owner found")
            continue

        result, cached = qualify_lead(name, phone, website, owner_name, address, website_text, role, memory)
        if cached:
            cache_hits += 1

        if result.get("qualified"):
            grade  = result.get("grade", "C")
            opener = result.get("opener") or ""
            print(f"  ✅ Grade: {grade} | Owner: {owner_name} | Opener: {opener}")
            qualified_leads.append({
                "Business Name":     name,
                "Phone":             phone,
                "Website":           website,
                "Address":           address,
                "Email":             "",
                "Owner Name":        owner_name,
                "Grade":             grade,
                "Grade Reason":      result.get("grade_reason", ""),
                "Qualified":         "Yes",
                "Niche Notes":       result.get("niche_notes", ""),
                "Disqualify Reason": "",
                "Opener":            opener,
                "Notes":             "",
                "State":             lead.get("state", ""),
                "City":              lead.get("city", "")
            })
        else:
            print(f"  ❌ Disqualified: {result.get('disqualify_reason')}")

        time.sleep(0.3)

    print(f"\n📊 Results: {len(qualified_leads)} qualified today | Cache hits: {cache_hits}/{processed}")
    push_to_os(qualified_leads, lead_status)
    push_file(__file__, "progress.json")
    push_file(__file__, "scraped_ids.json")


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
        run_pipeline(args.status)