#!/usr/bin/env python3
"""Generate an AI image via fal.ai for ad creative / content use.

Usage:
    python tools/generate_creative.py image "<prompt>" --aspect 1:1 --out ../path/image.png

Requires FAL_KEY in the environment (fetch via
`doppler secrets get FAL_KEY --project digigrowth --config prd --plain` and
pass through `doppler run -- python tools/generate_creative.py ...`, or export
it into the shell first).

Writes the requested output file plus a sibling `<out>.meta.json` provenance
sidecar (model, prompt, request id, aspect, generated_at).
"""
import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ASPECT_TO_SIZE = {
    # Explicit width/height (multiples of 32) instead of fal's named presets —
    # the presets top out around 768x1024, which is well below the ~1080px-wide
    # canvas this agent composites onto, so every ad was being upscaled ~40% and
    # coming out visibly soft. These sizes land at/above the final canvas width.
    "1:1": {"width": 1088, "height": 1088},
    "4:5": {"width": 1088, "height": 1360},
    "9:16": {"width": 832, "height": 1472},
    "16:9": {"width": 1472, "height": 832},
}

MODEL = "fal-ai/flux-pro/v1.1"


def generate_image(prompt: str, aspect: str) -> dict:
    fal_key = os.environ.get("FAL_KEY")
    if not fal_key:
        sys.exit("FAL_KEY not set in environment — run via `doppler run --project digigrowth "
                 "--config prd -- python tools/generate_creative.py ...`")

    image_size = ASPECT_TO_SIZE.get(aspect, {"width": 1088, "height": 1088})
    payload = json.dumps({
        "prompt": prompt,
        "image_size": image_size,
        "num_images": 1,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"https://fal.run/{MODEL}",
        data=payload,
        headers={
            "Authorization": f"Key {fal_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read().decode("utf-8"))

    image_url = result["images"][0]["url"]
    request_id = result.get("request_id") or result.get("requestId") or ""
    with urllib.request.urlopen(image_url, timeout=120) as img_resp:
        image_bytes = img_resp.read()

    return {
        "image_bytes": image_bytes,
        "request_id": request_id,
        "model": MODEL,
        "prompt": prompt,
        "aspect": aspect,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["image"])
    parser.add_argument("prompt")
    parser.add_argument("--aspect", default="1:1", choices=list(ASPECT_TO_SIZE))
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    result = generate_image(args.prompt, args.aspect)
    out_path.write_bytes(result["image_bytes"])

    meta = {
        "model": result["model"],
        "prompt": result["prompt"],
        "request_id": result["request_id"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "aspect": result["aspect"],
        "ref": None,
    }
    meta_path = Path(str(out_path) + ".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2))

    print(f"Wrote {out_path}")
    print(f"Wrote {meta_path}")


if __name__ == "__main__":
    main()
