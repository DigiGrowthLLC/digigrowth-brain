"""
Batch free-filter helper for scrape-leads sessions. Not part of the skill's
documented CLI — a throwaway convenience wrapper around lib.py's filter
primitives so a whole city/term batch can be filtered in one process instead
of one Bash call per listing.

Usage:
    python filter_batch.py <raw_listings.json> <city> <state>

raw_listings.json: [{"name":..., "phone":..., "website":...}, ...]

Prints JSON: {"survivors": [...], "skipped_counts": {...}, "reviewed": N}
Marks every listing (survivor or not... survivors get marked later, after
qualification) - here it only marks the SKIPPED ones as scraped, since
survivors still need to go through website scrape + qualification first.
"""
import json
import sys
import lib

CHAINS = [
    "ati physical therapy", "athletico", "us physical therapy", "select physical therapy",
    "select medical", "ivy rehab", "fyzical", "cora physical therapy", "novacare",
    "results physiotherapy", "bayada", "interim healthcare", "amedisys", "lhc group",
    "encompass health",
]
NON_PT_KEYWORDS = [
    "hospital", "home health", "nursing home", "skilled nursing", "hospice", "urgent care",
    "behavioral health", "addiction", "mental health", "psychiatric", "chiropractic",
    "chiropractor", "home care", "va medical", "rehabilitation hospital", "assisted living",
    "senior living", "physical therapy school", "university",
]


def looks_like_chain_or_non_pt(name: str) -> bool:
    n = name.lower()
    return any(k in n for k in CHAINS) or any(k in n for k in NON_PT_KEYWORDS)

def main():
    raw_path, city, state = sys.argv[1], sys.argv[2], sys.argv[3]
    with open(raw_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    scraped_ids = lib.load_scraped_ids()
    survivors = []
    skipped = {"dup": 0, "no_phone_or_site": 0, "chain_or_nonpt": 0}

    for item in raw:
        name = (item.get("name") or "").strip()
        phone = item.get("phone")
        website = item.get("website")
        key = f"{name}|{city}|{state}"
        norm = lib.normalize_scraped_id(key)

        if norm in scraped_ids:
            skipped["dup"] += 1
            continue
        if not phone or not website:
            skipped["no_phone_or_site"] += 1
            scraped_ids.add(norm)
            continue
        if looks_like_chain_or_non_pt(name):
            skipped["chain_or_nonpt"] += 1
            scraped_ids.add(norm)
            continue

        survivors.append({"name": name, "phone": phone, "website": website})

    lib.save_scraped_ids(scraped_ids)

    print(json.dumps({
        "survivors": survivors,
        "skipped_counts": skipped,
        "reviewed": len(raw),
    }, indent=2))

if __name__ == "__main__":
    main()
