import json
import os
import time
import re
import requests
from datetime import datetime
from bs4 import BeautifulSoup
import anthropic
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

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
with open(CONFIG_FILE, "r") as f:
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
    "personal training studio",
    "personal trainer",
    "private gym",
    "fitness studio",
    "strength training gym",
    "semi private training",
    "athletic training facility"
]

CHAIN_KEYWORDS = [
    "planet fitness", "anytime fitness", "la fitness", "crunch",
    "gold's gym", "golds gym", "24 hour fitness", "ymca", "orangetheory",
    "f45", "eos fitness", "equinox", "life time", "lifetime fitness",
    "snap fitness", "club pilates", "pure barre", "burn boot camp",
    "barry's", "solidcore", "ufc gym", "title boxing", "workout anytime",
    "jazzercise", "curves", "exercise coach"
]


# ════════════════════════════════════════════════════════════════════════════
#  PROGRESS TRACKING
# ════════════════════════════════════════════════════════════════════════════

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f)
    return {
        "current_state_index": 0,
        "current_city_index": 0,
        "current_term_index": 0,
        "states": list(US_STATES.keys())
    }

def save_progress(progress):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)

def load_scraped_ids():
    if os.path.exists(SCRAPED_FILE):
        with open(SCRAPED_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_scraped_ids(ids):
    with open(SCRAPED_FILE, "w") as f:
        json.dump(list(ids), f)


# ════════════════════════════════════════════════════════════════════════════
#  MEMORY SYSTEM
# ════════════════════════════════════════════════════════════════════════════

def read_memory():
    with open(MEMORY_FILE, "r") as f:
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
    with open(MEMORY_FILE, "a") as f:
        f.write(entry)
    print(f"✅ Memory updated: {new_information}")


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
#  OWNER LOOKUP
# ════════════════════════════════════════════════════════════════════════════

def find_owner_from_website(website_url, business_name):
    if not website_url:
        return ""
    pages = [
        website_url,
        website_url.rstrip("/") + "/about",
        website_url.rstrip("/") + "/about-us",
        website_url.rstrip("/") + "/team",
        website_url.rstrip("/") + "/our-team",
        website_url.rstrip("/") + "/staff",
    ]
    all_text = []
    for page in pages:
        try:
            res = requests.get(page, headers=HEADERS, timeout=8)
            if res.status_code != 200:
                continue
            soup = BeautifulSoup(res.text, "html.parser")
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict):
                        for field in ["founder", "owner"]:
                            if field in data:
                                val = data[field]
                                if isinstance(val, dict) and "name" in val:
                                    return val["name"].strip()
                                if isinstance(val, str) and val.strip():
                                    return val.strip()
                except Exception:
                    continue
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            all_text.append(soup.get_text(separator=" ", strip=True)[:800])
        except Exception:
            continue

    if not all_text:
        return ""

    combined = " ".join(all_text)[:2000]
    try:
        response = client.messages.create(
            model=config["model"],
            max_tokens=50,
            messages=[{"role": "user", "content": (
                f"Read this text from a gym website called '{business_name}':\n\n{combined}\n\n"
                f"Is there a real person clearly identified as owner, founder, or head trainer? "
                f"If yes return ONLY their first and last name. If no return ONLY the word null."
            )}]
        )
        result = response.content[0].text.strip()
        if result.lower() in ["null", "none", ""]:
            return ""
        if len(result.split()) in [2, 3] and result[0].isupper():
            return result
    except Exception:
        pass
    return ""


def find_owner_from_maps(place_id, business_name):
    try:
        url    = "https://maps.googleapis.com/maps/api/place/details/json"
        params = {"place_id": place_id, "fields": "reviews", "key": PLACES_KEY}
        res    = requests.get(url, params=params, timeout=8)
        data   = res.json()
        if data.get("status") != "OK":
            return ""
        reviews     = data.get("result", {}).get("reviews", [])
        review_text = " ".join([r.get("text", "") for r in reviews[:5]])
        if not review_text.strip():
            return ""
        response = client.messages.create(
            model=config["model"],
            max_tokens=50,
            messages=[{"role": "user", "content": (
                f"Read these Google Maps reviews for '{business_name}':\n\n{review_text[:1500]}\n\n"
                f"Is there a real person clearly identified as owner or founder? "
                f"If yes return ONLY their first and last name. If no return ONLY the word null."
            )}]
        )
        result = response.content[0].text.strip()
        if result.lower() in ["null", "none", ""]:
            return ""
        if len(result.split()) in [2, 3] and result[0].isupper():
            return result
    except Exception:
        pass
    return ""


def find_owner_name(business_name, place_id, website_url):
    print(f"    🔍 Checking website...")
    name = find_owner_from_website(website_url, business_name)
    if name:
        print(f"    ✅ Found on website: {name}")
        return name
    print(f"    🔍 Checking Maps reviews...")
    name = find_owner_from_maps(place_id, business_name)
    if name:
        print(f"    ✅ Found on Maps: {name}")
        return name
    print(f"    ⚠️  No owner found")
    return ""


# ════════════════════════════════════════════════════════════════════════════
#  WEBSITE SCRAPER
# ════════════════════════════════════════════════════════════════════════════

def scrape_website(url, max_words=600):
    if not url:
        return ""
    text_chunks = []
    for page in [url, url.rstrip("/") + "/about", url.rstrip("/") + "/about-us"]:
        try:
            res = requests.get(page, headers=HEADERS, timeout=8)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()
                text_chunks.append(soup.get_text(separator=" ", strip=True))
        except Exception:
            continue
    combined = " ".join(text_chunks)
    return " ".join(combined.split()[:max_words])


# ════════════════════════════════════════════════════════════════════════════
#  LEAD QUALIFIER
# ════════════════════════════════════════════════════════════════════════════

def qualify_lead(business_name, phone, website_url, owner_name, address, website_text):
    role     = open(ROLE_FILE).read()
    memory   = read_memory()
    prompt   = open(PROMPT_FILE).read()
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
        system=f"{role}\n\nAgent memory and criteria:\n{memory}",
        messages=[{"role": "user", "content": filled}]
    )
    raw = response.content[0].text.strip()
    try:
        return json.loads(raw.replace("```json", "").replace("```", "").strip())
    except json.JSONDecodeError:
        return {
            "qualified": False, "grade": "D",
            "grade_reason": "Parse error",
            "disqualify_reason": f"Unparseable: {raw[:100]}",
            "niche_confirmed": False, "niche_notes": "", "opener": None
        }


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
#  GOOGLE SHEETS
# ════════════════════════════════════════════════════════════════════════════

def get_sheet():
    creds = Credentials.from_service_account_file(
        os.path.join(BASE_DIR, "credentials.json"),
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(config["google_sheet_id"])
    try:
        return sh.worksheet(config["sheet_tab_name"])
    except gspread.exceptions.WorksheetNotFound:
        return sh.add_worksheet(title=config["sheet_tab_name"], rows="1000", cols="20")

def push_to_sheet(worksheet, rows):
    if not rows:
        print("No qualified leads to push.")
        return
    headers = config["output_columns"]
    worksheet.clear()
    worksheet.append_row(headers)
    grade_order = {"A": 0, "B": 1, "C": 2, "D": 3}
    for row in sorted(rows, key=lambda r: grade_order.get(r.get("Grade", "D"), 3)):
        worksheet.append_row([row.get(col, "") for col in headers])
        time.sleep(0.5)
    print(f"✅ {len(rows)} leads pushed to Google Sheets.")


# ════════════════════════════════════════════════════════════════════════════
#  MAIN PIPELINE
# ════════════════════════════════════════════════════════════════════════════

def run_pipeline():
    if datetime.now().weekday() >= 5:
        print("⏸️  Weekend — skipping run.")
        return
    progress    = load_progress()
    scraped_ids = load_scraped_ids()
    daily_limit = config.get("daily_lead_limit", 55)

    print(f"📅 {datetime.now().strftime('%A, %B %d %Y')}")
    print(f"📊 Total leads scraped so far: {len(scraped_ids)}")
    print(f"\n🌎 Scraping Google Maps...")

    raw_leads = scrape_state_leads(progress, scraped_ids, daily_limit)
    print(f"📋 Raw leads collected: {len(raw_leads)}")

    if not raw_leads:
        print("❌ No raw leads found.")
        return

    qualified_leads = []
    processed       = 0

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

        keep, reason = rule_based_filter(name, phone, website)
        if not keep:
            print(f"  ⏭️  Skipped: {reason}")
            continue

        owner_name = find_owner_name(name, place_id, website)
        if not owner_name:
            print(f"  ⏭️  Skipped: No owner found")
            continue

        website_text = scrape_website(website)
        result       = qualify_lead(name, phone, website, owner_name, address, website_text)

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

    print(f"\n📊 Results: {len(qualified_leads)} qualified today")
    push_to_sheet(get_sheet(), qualified_leads)


# ════════════════════════════════════════════════════════════════════════════
#  ENTRY POINTS
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "remember":
        update_memory(" ".join(sys.argv[2:]))
    else:
        run_pipeline()