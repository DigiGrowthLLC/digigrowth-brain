"""Load every 5-star Google review for a client onto their booking page (Dylan, 2026-11-22:
"overload" the booking page's social proof with as many 5-star reviews as possible).

Google's API only returns 5 reviews, and Google Maps shows logged-out visitors only 5, so the
full list is copied from Dylan's signed-in Chrome (steps in the service-delivery-setup skill,
"Reviews loaded"), saved as a text file, then imported here:

  doppler run --project digigrowth --config prd -- python onboarding-agent/scripts/import_google_reviews.py <client_id> <reviews.txt> [--count 159] [--rating 4.9] [--dry-run]

Input: one review per line, "@@<n>|<reviewer display name>|<text>" (" ¶ " = paragraph break),
ending with "@@END", or a JSON list of {"fn"/"author", "t"/"text"}. Only 5-star reviews go in the
file. Reviews already on file stay first and in order (the first one is the one the page shows);
new ones are added after them, deduplicated. First names only, never full names.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.request

SKIP_FIRST = {"the", "oh", "mr", "mrs", "ms", "dr", "a", "an", "my", "just", "its", "it's"}
MAX_CHARS = 4000


def _norm(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def _first_name(display: str) -> str:
    tok = (display or "").strip().split()
    if not tok:
        return ""
    w = tok[0]
    if w.lower() in SKIP_FIRST or not re.fullmatch(r"[A-Za-z][A-Za-z'\-]{1,20}", w):
        return ""
    return w[0].upper() + w[1:]


def _clean(text: str) -> str:
    parts = [p.strip() for p in re.split(r"\s*¶\s*|\n+", text or "") if p.strip()]
    # Drop trailing sign-offs ("Coleen Moorman", "Karen Wood", "Little Rock, AR"): no full names on the page.
    while len(parts) > 1 and len(parts[-1].split()) <= 4 and not re.search(r"[.!?]$", parts[-1]):
        parts.pop()
    out = " ".join(parts)
    # A "Name Surname" signature glued onto the last sentence ("...thankful for the work he did. Greg Young").
    out = re.sub(r"([.!?])\s+[A-Z][a-z]+ [A-Z][a-z]+$", r"\1", out)
    return re.sub(r"\s{2,}", " ", out).strip()[:MAX_CHARS]


def parse(path: str) -> list[dict]:
    raw = open(path, encoding="utf-8-sig").read()
    if raw.lstrip().startswith("["):
        items = [{"author": _first_name(r.get("fn") or r.get("author") or ""), "text": _clean(r.get("t") or r.get("text") or "")}
                 for r in json.loads(raw)]
    else:
        items = []
        for line in raw.splitlines():
            m = re.match(r"^@@(\d+)\|([^|]*)\|(.*)$", line.strip())
            if m:
                items.append({"author": _first_name(m.group(2)), "text": _clean(m.group(3))})
    return [r for r in items if len(r["text"]) >= 20]


def _api(method: str, path: str, body: dict | None = None) -> dict:
    base = os.environ["DASHBOARD_URL"].rstrip("/")
    auth = base64.b64encode(f"admin:{os.environ['DASHBOARD_PASSWORD']}".encode()).decode()
    req = urllib.request.Request(base + "/api" + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": "Basic " + auth, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read() or b"{}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("client_id", type=int)
    ap.add_argument("file")
    ap.add_argument("--count", type=int, help="Total Google review count shown next to the rating")
    ap.add_argument("--rating", type=float, help="Google star rating, e.g. 4.9")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    new = parse(a.file)
    s = _api("GET", f"/clients/{a.client_id}/booking")["settings"]
    on_file = s.get("reviews") or []
    if isinstance(on_file, str):
        on_file = json.loads(on_file)
    keys = [_norm(r.get("text", "")) for r in on_file]
    merged, added = list(on_file), 0
    for r in new:
        k = _norm(r["text"])
        # Same review already on file (exactly, or one is a shortened copy of the other).
        if any(k == x or (len(x) >= 40 and (x in k or k in x)) for x in keys):
            continue
        merged.append(r)
        keys.append(k)
        added += 1
    print(f"{len(on_file)} on file, {len(new)} in the file, {added} new -> {len(merged)} total")
    if a.dry_run:
        for r in merged[len(on_file):len(on_file) + 5]:
            print(" -", r["author"] or "(no name)", "|", r["text"][:100])
        return
    body: dict = {"reviews": merged}
    if a.count is not None:
        body["review_count"] = a.count
    if a.rating is not None:
        body["review_rating"] = a.rating
    _api("PUT", f"/clients/{a.client_id}/booking", body)
    after = _api("GET", f"/clients/{a.client_id}/booking")["settings"].get("reviews") or []
    if isinstance(after, str):
        after = json.loads(after)
    print(f"Saved: {len(after)} reviews on file")
    if len(after) < len(merged):
        sys.exit(f"Only {len(after)} of {len(merged)} saved: is the server's MAX_REVIEWS deploy live yet?")


if __name__ == "__main__":
    main()
