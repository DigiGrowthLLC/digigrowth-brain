#!/usr/bin/env python3
"""Re-send fal.ai generations to the OS from their .meta.json sidecars.

For generations made before per-client fal tracking (2026-11-22) or whose
report failed. Duplicates are fine (the OS keys on request id).

    doppler run --project digigrowth --config prd -- \
        python content-agent/tools/report_fal_usage.py media-buying-agent/clients [more dirs...]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from generate_creative import client_from_path, report_generation  # noqa: E402

sent = skipped = 0
for root in sys.argv[1:] or ["."]:
    for meta_path in Path(root).rglob("*.meta.json"):
        try:
            meta = json.loads(meta_path.read_text())
        except (OSError, ValueError):
            skipped += 1
            continue
        if not meta.get("request_id"):
            skipped += 1
            continue
        meta.setdefault("client", client_from_path(meta_path))
        if not meta["client"]:
            meta["client"] = client_from_path(meta_path)
        ok = report_generation(meta)
        sent += ok
        skipped += not ok
        print(f"{'sent' if ok else 'FAILED'}  {meta.get('client') or '(business)'}  {meta_path}")
print(f"{sent} sent, {skipped} skipped")
