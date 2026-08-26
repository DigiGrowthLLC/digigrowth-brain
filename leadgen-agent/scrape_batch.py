"""
Batch website-scrape helper for scrape-leads sessions. Not part of the
skill's documented CLI - wraps lib.scrape_website_full for a whole
survivors list in one process instead of one Bash call per listing.

Usage:
    python scrape_batch.py <survivors.json>

survivors.json: [{"name":..., "phone":..., "website":...}, ...]

Prints JSON: [{"name":..., "phone":..., "website":..., "owner_name":..., "website_text":...}, ...]
"""
import json
import sys
import lib

def main():
    path = sys.argv[1]
    with open(path, "r", encoding="utf-8") as f:
        survivors = json.load(f)

    max_words = lib.config.get("max_website_text_words", 300)
    out = []
    for item in survivors:
        owner, text = lib.scrape_website_full(item["website"], max_words)
        out.append({
            "name": item["name"],
            "phone": item["phone"],
            "website": item["website"],
            "owner_name": owner,
            "website_text": text,
        })
    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    main()
