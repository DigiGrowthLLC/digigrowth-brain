#!/usr/bin/env python3
"""Generate AI images and videos via fal.ai for ad creative / content use.

Usage:
    python tools/generate_creative.py image "<prompt>" --aspect 1:1 --out ../path/image.png
    python tools/generate_creative.py image "<prompt>" --model nano-banana-pro --aspect 9:16 \
        [--ref ../path/reference.jpg ...] --out ../path/actor.png
    python tools/generate_creative.py video "<motion prompt>" --image ../path/still.png \
        --duration 5 --out ../path/clip.mp4
    python tools/generate_creative.py video "<shot brief with \"quoted dialogue\">" --model seedance2 \
        --image ../path/actor.png --duration 15 --out ../path/ugc.mp4

Models:
  image  flux (default)        fal-ai/flux-pro/v1.1: realistic stills, cheapest
         nano-banana-pro       fal-ai/nano-banana-pro: best for UGC "actor" stills; with --ref it
                               uses the /edit endpoint to keep a reference (product, place, person)
  video  kling (default)       Kling 2.1 image-to-video: silent B-roll, ~$0.25/5s
         seedance2             Seedance 2.0 image-to-video: native audio + lip-synced speech. Put
                               spoken lines in double quotes in the prompt. 4-15s, 720p ~$0.30/s,
                               1080p ~$0.68/s. REJECTS photoreal human faces as the input image
                               ("likenesses of real people"), so it can't animate an AI actor still
         veo31                 Veo 3.1 image-to-video: native audio + lip-synced speech from quoted
                               dialogue; accepts AI actor stills. 4, 6 or 8s per take, $0.40/s with
                               audio. Split longer scripts into takes from the same still
         veo31-fast            Veo 3.1 Fast: same inputs and lip-sync, $0.15/s with audio (~60%
                               cheaper). Default for UGC takes; use veo31 only if Fast looks off

  music  stable-audio          fal-ai/stable-audio: royalty-free instrumental bed, up to ~45s
                               (`music "<style prompt>" --duration 24 --out bed.wav`)

`video` mode animates an approved still, so the still can be reviewed and fixed cheaply before
paying for video generation.

Requires FAL_KEY in the environment (fetch via
`doppler secrets get FAL_KEY --project digigrowth --config prd --plain` and
pass through `doppler run -- python tools/generate_creative.py ...`, or export
it into the shell first).

Writes the requested output file plus a sibling `<out>.meta.json` provenance
sidecar (model, prompt, request id, generated_at, ...).
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.error
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

IMAGE_MODELS = {
    "flux": "fal-ai/flux-pro/v1.1",
    "nano-banana-pro": "fal-ai/nano-banana-pro",
}
VIDEO_MODELS = {
    "kling": "fal-ai/kling-video/v2.1/standard/image-to-video",
    "seedance2": "bytedance/seedance-2.0/image-to-video",
    "veo31": "fal-ai/veo3.1/image-to-video",
    "veo31-fast": "fal-ai/veo3.1/fast/image-to-video",
}


def _headers() -> dict:
    fal_key = os.environ.get("FAL_KEY")
    if not fal_key:
        sys.exit("FAL_KEY not set in environment — run via `doppler run --project digigrowth "
                 "--config prd -- python tools/generate_creative.py ...`")
    return {"Authorization": f"Key {fal_key}", "Content-Type": "application/json"}


def _call(url: str, payload: dict | None = None) -> dict:
    req = urllib.request.Request(url, headers=_headers(), method="POST" if payload else "GET",
                                 data=json.dumps(payload).encode("utf-8") if payload else None)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        sys.exit(f"fal request failed ({e.code}): {e.read().decode('utf-8', 'replace')[:1500]}")


def _run_queued(model: str, payload: dict, timeout_s: int = 900) -> tuple[dict, str]:
    """Submit to fal's queue API and wait (video jobs run 1-5 min, too long for fal.run)."""
    job = _call(f"https://queue.fal.run/{model}", payload)
    deadline = time.time() + timeout_s
    while _call(job["status_url"]).get("status") != "COMPLETED":
        if time.time() > deadline:
            sys.exit(f"{model} job {job['request_id']} still not done after {timeout_s // 60} min")
        time.sleep(8)
    return _call(job["response_url"]), job["request_id"]


def _data_uri(path: Path) -> str:
    mime = {".png": "image/png", ".webp": "image/webp"}.get(path.suffix.lower(), "image/jpeg")
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def _download(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=300) as r:
        return r.read()


def generate_image(prompt: str, aspect: str, model: str = "flux", refs: list[Path] | None = None) -> dict:
    if model == "flux":
        endpoint = IMAGE_MODELS["flux"]
        payload = {"prompt": prompt, "num_images": 1,
                   "image_size": ASPECT_TO_SIZE.get(aspect, {"width": 1088, "height": 1088})}
    else:
        endpoint = IMAGE_MODELS["nano-banana-pro"] + ("/edit" if refs else "")
        payload = {"prompt": prompt, "num_images": 1, "aspect_ratio": aspect, "resolution": "2K",
                   "output_format": "png"}
        if refs:
            payload["image_urls"] = [_data_uri(r) for r in refs]
    result, request_id = _run_queued(endpoint, payload, timeout_s=300)
    return {
        "image_bytes": _download(result["images"][0]["url"]),
        "request_id": request_id,
        "model": endpoint,
        "prompt": prompt,
        "aspect": aspect,
    }


def generate_video(image_path: Path, prompt: str, duration: str, model: str = "kling",
                   resolution: str = "1080p", aspect: str = "9:16") -> dict:
    endpoint = VIDEO_MODELS[model]
    payload = {"prompt": prompt, "image_url": _data_uri(image_path), "duration": duration}
    if model == "kling":
        payload["negative_prompt"] = "blur, distort, low quality, warped hands, extra fingers, text, watermark"
    elif model in ("veo31", "veo31-fast"):
        payload.update({"duration": f"{duration}s", "resolution": resolution, "aspect_ratio": aspect,
                        "generate_audio": True})
    else:
        payload.update({"resolution": resolution, "aspect_ratio": aspect, "generate_audio": True})
    result, request_id = _run_queued(endpoint, payload)
    return {"video_bytes": _download(result["video"]["url"]), "request_id": request_id,
            "model": endpoint, "prompt": prompt}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["image", "video", "music"])
    parser.add_argument("prompt")
    parser.add_argument("--model", help="image: flux (default) | nano-banana-pro; "
                                        "video: kling (default) | seedance2 | veo31 | veo31-fast")
    parser.add_argument("--aspect", choices=list(ASPECT_TO_SIZE),
                        help="default 1:1 for images, 9:16 for video")
    parser.add_argument("--ref", action="append", default=[],
                        help="image mode, nano-banana-pro: reference image(s) to keep (repeatable)")
    parser.add_argument("--image", help="video mode: the approved still to animate")
    parser.add_argument("--duration", default="5",
                        help="video mode: seconds (kling: 5 or 10; seedance2: 4-15; veo31/veo31-fast: 4, 6, 8)")
    parser.add_argument("--resolution", default="1080p", help="video mode, seedance2: 720p | 1080p")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if args.aspect is None:
        args.aspect = "9:16" if args.mode == "video" else "1:1"
    now = datetime.now(timezone.utc).isoformat()

    if args.mode == "music":
        result, request_id = _run_queued("fal-ai/stable-audio", {
            "prompt": args.prompt, "seconds_total": int(args.duration), "steps": 100}, timeout_s=300)
        audio = result.get("audio_file") or result.get("audio")
        out_path.write_bytes(_download(audio["url"]))
        meta = {"model": "fal-ai/stable-audio", "prompt": args.prompt, "request_id": request_id,
                "generated_at": now, "duration": args.duration}
    elif args.mode == "video":
        model = args.model or "kling"
        if model not in VIDEO_MODELS:
            sys.exit(f"unknown video model {model}; choose from {list(VIDEO_MODELS)}")
        if not args.image:
            sys.exit("video mode needs --image <approved still>")
        result = generate_video(Path(args.image), args.prompt, args.duration, model,
                                args.resolution, args.aspect)
        out_path.write_bytes(result["video_bytes"])
        meta = {"model": result["model"], "prompt": result["prompt"],
                "request_id": result["request_id"], "generated_at": now,
                "source_image": str(args.image), "duration": args.duration}
    else:
        model = args.model or "flux"
        if model not in IMAGE_MODELS:
            sys.exit(f"unknown image model {model}; choose from {list(IMAGE_MODELS)}")
        result = generate_image(args.prompt, args.aspect, model, [Path(r) for r in args.ref])
        out_path.write_bytes(result["image_bytes"])
        meta = {"model": result["model"], "prompt": result["prompt"],
                "request_id": result["request_id"], "generated_at": now,
                "aspect": result["aspect"], "ref": args.ref or None}

    meta_path = Path(str(out_path) + ".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2))
    print(f"Wrote {out_path}")
    print(f"Wrote {meta_path}")


if __name__ == "__main__":
    main()
