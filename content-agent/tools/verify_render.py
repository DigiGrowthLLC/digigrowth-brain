"""Verification-loop helper: contact sheets + automated checks for a rendered edit.

Usage:
    python tools/verify_render.py <render.mp4> <beats.json> --out <scratchpad dir>
        [--source <original.mp4>] [--transcript <transcript.json>] [--iteration N]
        [--tolerance 0.25] [--full]

beats.json is the approved card/beat plan:
    [{"id": "c01", "type": "Hook", "start": 0.0, "end": 12.0, "label": "I CAN'T CODE.",
      "cue": "can't code", "track": 2}, ...]
("cue" and "track" are optional. Beats default to track 2.)

For every beat it grabs 3 frames (in + 0.4s, midpoint, out - 0.2s) and tiles them into
labeled contact sheets (8 beats per sheet) at <out>/iter<N>-sheet-<k>.jpg. Read the sheets
and score them against the rubric in the video-overlay skill.
--out must be a scratchpad/temp dir, never the repo (CLAUDE.md screenshot rule).

Automated checks (printed as PASS/FAIL):
  - render has a video and an audio stream
  - render duration within 0.1s of --source (if given)
  - no two beats on the same track overlap in time
  - each beat with a "cue" starts within --tolerance s of that cue phrase in --transcript (if given)

--full also saves a full-resolution midpoint frame per beat (<out>/iter<N>-<id>-mid.jpg) -
thumbnails show layout and timing, full frames are for proofreading card text.
"""
import argparse
import json
import pathlib
import re
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont

THUMB_W, THUMB_H, LABEL_H = 480, 270, 34


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "stream=codec_type:format=duration", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    data = json.loads(out)
    kinds = {s["codec_type"] for s in data.get("streams", [])}
    return kinds, float(data["format"]["duration"])


def grab(video, t, dest, scale=True):
    vf = ["-vf", f"scale={THUMB_W}:{THUMB_H}"] if scale else []
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{max(t, 0):.3f}",
                    "-i", str(video), "-frames:v", "1", *vf, "-update", "1", str(dest)], check=True)


def font(size):
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def norm(w):
    return re.sub(r"[^a-z0-9']", "", w.lower())


def find_cue(words, cue, near):
    """Start time of the occurrence of `cue` closest to `near`, or None."""
    target = [norm(w) for w in cue.split() if norm(w)]
    toks = [norm(w["text"]) for w in words]
    hits = [words[i]["start"] for i in range(len(toks) - len(target) + 1)
            if toks[i:i + len(target)] == target]
    return min(hits, key=lambda t: abs(t - near)) if hits else None


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("render")
    p.add_argument("beats")
    p.add_argument("--out", required=True)
    p.add_argument("--source")
    p.add_argument("--transcript")
    p.add_argument("--iteration", type=int, default=1)
    p.add_argument("--tolerance", type=float, default=0.25, help="max seconds between cue word and beat start")
    p.add_argument("--full", action="store_true", help="also save full-res midpoint frames for proofreading")
    a = p.parse_args()

    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    beats = sorted(json.loads(pathlib.Path(a.beats).read_text(encoding="utf-8")), key=lambda b: b["start"])
    results = []

    kinds, dur = probe(a.render)
    results.append(("video + audio streams", {"video", "audio"} <= kinds, f"streams: {sorted(kinds)}"))
    if a.source:
        _, src = probe(a.source)
        results.append(("duration matches source", abs(dur - src) <= 0.1, f"render {dur:.2f}s vs source {src:.2f}s"))

    by_track = {}
    for b in beats:
        by_track.setdefault(b.get("track", 2), []).append(b)
    overlaps = [f"{x['id']}/{y['id']}" for bs in by_track.values()
                for x, y in zip(bs, bs[1:]) if y["start"] < x["end"] - 0.01]
    results.append(("no same-track overlaps", not overlaps, ", ".join(overlaps) or "none"))

    if a.transcript:
        words = json.loads(pathlib.Path(a.transcript).read_text(encoding="utf-8"))
        late = []
        for b in beats:
            if not b.get("cue"):
                continue
            t = find_cue(words, b["cue"], b["start"])
            if t is None:
                late.append(f"{b['id']}: cue \"{b['cue']}\" not found")
            elif abs(b["start"] - t) > a.tolerance:
                late.append(f"{b['id']}: starts {b['start']:.2f}s, cue at {t:.2f}s")
        results.append(("beats land on cue words", not late, "; ".join(late) or f"all within {a.tolerance}s"))

    # Contact sheets: one row per beat, 3 frames per row, 8 rows per sheet.
    f_label, f_small = font(20), font(16)
    sheets = []
    with tempfile.TemporaryDirectory() as tmp:
        for k in range(0, len(beats), 8):
            chunk = beats[k:k + 8]
            sheet = Image.new("RGB", (THUMB_W * 3, (THUMB_H + LABEL_H) * len(chunk)), (12, 14, 24))
            draw = ImageDraw.Draw(sheet)
            for row, b in enumerate(chunk):
                y = row * (THUMB_H + LABEL_H)
                label = f"{b['id']}  {b.get('type', '')}  {b['start']:.2f}-{b['end']:.2f}s  {b.get('label', '')}"
                draw.text((8, y + 6), label[:120], fill=(240, 240, 240), font=f_label)
                for col, (tag, t) in enumerate((("in+0.4", b["start"] + 0.4),
                                                ("mid", (b["start"] + b["end"]) / 2),
                                                ("out-0.2", b["end"] - 0.2))):
                    img = pathlib.Path(tmp) / f"{b['id']}-{col}.jpg"
                    grab(a.render, min(t, dur - 0.05), img)
                    sheet.paste(Image.open(img), (col * THUMB_W, y + LABEL_H))
                    draw.text((col * THUMB_W + 8, y + LABEL_H + 6), f"{tag} {t:.2f}s",
                              fill=(255, 220, 90), font=f_small)
            dest = out / f"iter{a.iteration}-sheet-{k // 8 + 1}.jpg"
            sheet.save(dest, quality=85)
            sheets.append(dest)

    if a.full:
        for b in beats:
            dest = out / f"iter{a.iteration}-{b['id']}-mid.jpg"
            grab(a.render, (b["start"] + b["end"]) / 2, dest, scale=False)
            sheets.append(dest)

    print(f"Iteration {a.iteration} - {pathlib.Path(a.render).name} ({dur:.2f}s, {len(beats)} beats)\n")
    for name, ok, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}: {detail}")
    print("\nContact sheets (read each one and score against the rubric):")
    for s in sheets:
        print(f"  {s}")


if __name__ == "__main__":
    main()
