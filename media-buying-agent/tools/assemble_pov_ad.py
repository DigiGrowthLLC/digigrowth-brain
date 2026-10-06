#!/usr/bin/env python3
"""Assemble a silent POV text-on-video ad (9:16) from short AI scene clips and a JSON spec.

The CrosaCore "3PM Desk" format, made reusable for design-agent's patient-acquisition-blueprint
skill: each beat is a scene clip (e.g. Kling image-to-video from an approved still) with one text
card over it, then a real-review proof card and an end card, optionally under a music bed. Text
cards show from frame 0, because a paused video (or a poster grab) displays its first frame.

Usage (from the repo root):
    python media-buying-agent/tools/assemble_pov_ad.py path/to/spec.json

Spec (paths relative to the spec file):
{
  "slug": "advantage-pov-rushed-pt",
  "beats": [{"clip": "clip1.mp4", "text": "POV: a 15-minute PT visit, and ..."}, ...],   # 5s each
  "beat_seconds": 5,
  "proof": {"quote": "...", "attribution": "FIRST NAME · REAL GOOGLE REVIEW"},          # real review
  "end_card": {"eyebrow": "PRACTICE · CITY", "headline": "Free Phone Consult",
               "lines": ["...", "..."], "button": "LEARN MORE", "footnote": "..."},
  "palette": {"card": [10,10,10], "accent": [208,11,20], "panel": [45,8,12]},          # optional RGB
  "music": "bed.wav"                                                                    # optional
}
Writes <slug>-9x16.mp4 next to the spec, plus work/pov/ intermediates.
"""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).parent))
import ad_overlays as ov  # noqa: E402

W, H = 1080, 1920
PROOF_S, END_S = 4.0, 3.5


def main():
    spec_path = Path(sys.argv[1]).resolve()
    base = spec_path.parent
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if spec.get("palette"):
        pal = spec["palette"]
        ov.set_palette(*(tuple(pal[k]) if pal.get(k) else None for k in ("card", "accent", "panel")))
    work = base / "work" / "pov"
    work.mkdir(parents=True, exist_ok=True)
    beats = spec["beats"]
    beat_s = float(spec.get("beat_seconds", 5))
    total = beat_s * len(beats) + PROOF_S + END_S

    for i, b in enumerate(beats):
        ov.hook_card(W, H, b["text"], 430, size=64).save(work / f"text{i}.png")

    last_clip = base / beats[-1]["clip"]
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-sseof", "-0.2", "-i", str(last_clip),
                    "-frames:v", "1", str(work / "last.jpg")], check=True)
    last = Image.open(work / "last.jpg").convert("RGB").resize((W, H))
    blur = Image.blend(last.filter(ImageFilter.GaussianBlur(26)), Image.new("RGB", (W, H), ov.GREEN), 0.5).convert("RGBA")
    proof = ov.proof_card(W, H, spec["proof"]["quote"], spec["proof"]["attribution"], H // 2)
    Image.alpha_composite(blur, proof).convert("RGB").save(work / "proof.jpg", quality=94)
    ec = spec["end_card"]
    ov.end_card(last, W, H, ec["eyebrow"], ec["headline"], ec.get("lines", []), ec.get("button", "LEARN MORE"),
                ec.get("footnote", "")).save(work / "end.jpg", quality=94)

    inputs, filters = [], []
    for i, b in enumerate(beats):
        inputs += ["-t", str(beat_s), "-i", str(base / b["clip"]),
                   "-loop", "1", "-t", str(beat_s), "-i", str(work / f"text{i}.png")]
        filters.append(f"[{2 * i}:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps=30,setsar=1[c{i}];"
                       f"[c{i}][{2 * i + 1}:v]overlay=0:0[s{i}]")
    n = 2 * len(beats)
    inputs += ["-loop", "1", "-t", str(PROOF_S), "-i", str(work / "proof.jpg"),
               "-loop", "1", "-t", str(END_S), "-i", str(work / "end.jpg")]
    if spec.get("music"):
        inputs += ["-i", str(base / spec["music"])]
        audio = (f"[{n + 2}:a]atrim=0:{total},asetpts=PTS-STARTPTS,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000,"
                 f"afade=t=in:d=0.5,afade=t=out:st={total - 1.2}:d=1.2,apad=whole_dur={total}[aout]")
    else:
        inputs += ["-f", "lavfi", "-t", str(total), "-i", "anullsrc=r=48000:cl=stereo"]
        audio = f"[{n + 2}:a]anull[aout]"
    filters.append(f"[{n}:v]fps=30,setsar=1,fade=t=in:d=0.3[p];[{n + 1}:v]fps=30,setsar=1,fade=t=in:d=0.3[e]")
    filters.append("".join(f"[s{i}]" for i in range(len(beats))) + f"[p][e]concat=n={len(beats) + 2}:v=1:a=0,format=yuv420p[v]")
    filters.append(audio)

    out = base / f"{spec['slug']}-9x16.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(filters),
                    "-map", "[v]", "-map", "[aout]", "-t", str(total), "-c:v", "libx264", "-preset", "slow", "-crf", "21",
                    "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out)], check=True)
    print(f"Wrote {out} ({total:.1f}s)")


if __name__ == "__main__":
    main()
