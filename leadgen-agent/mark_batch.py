"""
Batch scraped-add helper - marks every name in a list as scraped for a given
city/state in one process instead of one Bash call per listing.

Usage:
    python mark_batch.py <names.json> <city> <state>

names.json: ["Business Name", ...]
"""
import json
import sys
import lib

def main():
    names_path, city, state = sys.argv[1], sys.argv[2], sys.argv[3]
    with open(names_path, "r", encoding="utf-8") as f:
        names = json.load(f)

    ids = lib.load_scraped_ids()
    for name in names:
        ids.add(lib.normalize_scraped_id(f"{name}|{city}|{state}"))
    lib.save_scraped_ids(ids)
    print(f"marked {len(names)} ok")

if __name__ == "__main__":
    main()
