#!/usr/bin/env python3
"""Customize ready-made AI video ads from media-buying-agent/video-library/ for one practice.

No new AI generation (no fal spend): the library footage is generic, and this puts the practice's
own colors, real Google review card, CTA end card (and, for POV ads, its closing line) on it, via
assemble_ugc_ad.py / assemble_pov_ad.py.

Usage (from the repo root):
    python media-buying-agent/tools/library_ad.py <practice.json> <out_dir> [item_id ...]

Item ids are the keys in video-library/library.json; omit them to build every item listed under
"reviews" in practice.json.

practice.json:
{
  "slug": "advantage",
  "palette": {"card": [10,10,10], "accent": [208,11,20], "panel": [45,8,12]},
  "end_card": {"eyebrow": "ADVANTAGE THERAPY · LAS VEGAS", "headline": "Free Phone Consult",
               "lines": ["1-on-1 manual therapy with a DPT", "..."], "button": "LEARN MORE", "footnote": "..."},
  "reviews": {                       # one REAL review per item to build; first name only
    "ugc-tried-everything": {"quote": "...", "attribution": "ANGIE · REAL GOOGLE REVIEW"},
    "pov-rushed-pt": {"quote": "...", "attribution": "JESSICA · REAL GOOGLE REVIEW"}
  },
  "pov_closer": "At Advantage Therapy, every visit is a full hour. One-on-one. Hands-on.",
  "hooks": {"ugc-tried-everything": "..."},   # optional override of the library hook
  "music": "path/to/bed.wav"                  # optional, relative to practice.json
}
Writes <out_dir>/<slug>-<item>-9x16.mp4 (UGC also -4x5) plus a page-weight copy
<out_dir>/<slug>-<item>-web.mp4 (720x1280) for the blueprint page.
"""
import json
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
LIB = TOOLS.parent / "video-library"


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    practice_path = Path(sys.argv[1]).resolve()
    p = json.loads(practice_path.read_text(encoding="utf-8"))
    out = Path(sys.argv[2]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    lib = json.loads((LIB / "library.json").read_text(encoding="utf-8"))["items"]
    wanted = sys.argv[3:] or list(p["reviews"])
    music = str((practice_path.parent / p["music"]).resolve()) if p.get("music") else None

    for item_id in wanted:
        item = lib[item_id]
        if item_id not in p["reviews"]:
            sys.exit(f"{item_id}: add a real review for it under 'reviews' in {practice_path.name}")
        name = f"{p['slug']}-{item_id}"
        work = out / item_id
        work.mkdir(exist_ok=True)
        hook = (p.get("hooks") or {}).get(item_id) or item.get("hook")

        if item["type"] == "ugc":
            spec = {"slug": name, "takes": [{"path": str(LIB / item["take"]), "in": 0.0, "out": 99}],
                    "hook": hook, "label": "", "proof": p["reviews"][item_id], "end_card": p["end_card"],
                    "palette": p.get("palette"), "caption_fixes": item.get("caption_fixes", {})}
            dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                        str(LIB / item["take"])], capture_output=True, text=True, check=True).stdout)
            spec["takes"][0]["out"] = round(dur - 0.05, 2)
            if music:
                spec["music"] = music
            tool = "assemble_ugc_ad.py"
        else:
            if not p.get("pov_closer"):
                sys.exit(f"{item_id}: set 'pov_closer' ({item['closer_hint']})")
            beats = [t if t else p["pov_closer"] for t in item["beats"]]
            spec = {"slug": name, "beats": [{"clip": str(LIB / c), "text": t} for c, t in zip(item["clips"], beats)],
                    "proof": p["reviews"][item_id], "end_card": p["end_card"], "palette": p.get("palette")}
            if music:
                spec["music"] = music
            tool = "assemble_pov_ad.py"

        spec_path = work / "spec.json"
        spec_path.write_text(json.dumps(spec, indent=1, ensure_ascii=False), encoding="utf-8")
        subprocess.run([sys.executable, str(TOOLS / tool), str(spec_path)], check=True)
        for f in work.glob(f"{name}-*.mp4"):
            f.replace(out / f.name)
        web = out / f"{name}-web.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(out / f"{name}-9x16.mp4"), "-vf", "scale=720:1280",
                        "-c:v", "libx264", "-preset", "slow", "-crf", "27", "-c:a", "aac", "-b:a", "96k",
                        "-movflags", "+faststart", str(web)], check=True)
        print(f"{item_id}: {web} ({web.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
