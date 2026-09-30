#!/usr/bin/env python3
"""Assemble a finished AI UGC video ad (9:16 + 4:5) from talking-actor takes and a JSON spec.

Step 4 of the generate-ad skill's "AI UGC Video Ads" loop. Takes the approved takes from
`content-agent/tools/generate_creative.py video --model veo31`, transcribes them for word-timed
captions, then adds the hook card, an "AI-generated actor portrayal" label, a real-review proof card,
an end card, and an optional music bed under the cards.

Usage (from the repo root):
    python media-buying-agent/tools/assemble_ugc_ad.py path/to/spec.json

Spec (paths relative to the spec file):
{
  "slug": "crosacore-no-time-for-pt",
  "takes": [{"path": "work/take1.mp4", "in": 0.0, "out": 7.45}, ...],   # trimmed + concatenated
  "hook": "No time for PT?",                  # on-screen card for the first ~3s
  "label": "AI-generated actor portrayal",    # optional corner tag on the actor footage; omit or "" for none
  "proof": {"quote": "...", "attribution": "FIRST NAME · ROLE, REAL GOOGLE REVIEW"},   # real review
  "end_card": {"eyebrow": "CLIENT · CITY", "headline": "Free 15-Minute Consultation",
               "lines": ["...", "..."], "button": "BOOK NOW", "footnote": "..."},
  "music": "work/bed.wav",                    # optional; plays under proof + end card only
  "crop_4x5_top": 120,                        # where the 4:5 window starts in the 1920 frame
  "caption_fixes": {"3pm.": "3pm,"}           # optional word replacements for the transcript
}
Writes <slug>-9x16.mp4 and <slug>-4x5.mp4 next to the spec, plus work/assembly/ intermediates.
Requires ffmpeg (with libass) and faster-whisper.
"""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).parent))
import ad_overlays as ov  # noqa: E402

W, H, FPS = 1080, 1920, 30
PROOF_D, END_D = 3.8, 3.0


def transcribe_words(path: Path):
    from faster_whisper import WhisperModel
    model = WhisperModel("small", device="cpu", compute_type="int8")
    segs, _ = model.transcribe(str(path), word_timestamps=True)
    return [(w.start, w.end, w.word) for s in segs for w in s.words]


def label_png(text: str, y: int) -> Image.Image:
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if not text:
        return im
    d = ImageDraw.Draw(im)
    f = ov.font(ov.SEMI, 28)
    tw = d.textlength(text, font=f)
    d.rounded_rectangle((W - tw - 90, y, W - 50, y + 46), 12, fill=(0, 0, 0, 150))
    d.text((W - tw - 70, y + 6), text, font=f, fill=(235, 235, 235))
    return im


def ffpath(p: Path) -> str:
    return p.as_posix().replace(":", "\\:")


def main():
    spec_path = Path(sys.argv[1]).resolve()
    base = spec_path.parent
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    work = base / "work" / "assembly"
    work.mkdir(parents=True, exist_ok=True)
    takes = [(base / t["path"], float(t["in"]), float(t["out"])) for t in spec["takes"]]
    fixes = spec.get("caption_fixes", {})

    # word-timed captions on the output timeline
    tl, t0 = [], 0.0
    for path, a, b in takes:
        for s, e, w in transcribe_words(path):
            text = fixes.get(w.strip(), w)
            if a <= s < b and text.strip():  # a fix of "" drops a token (e.g. a split "p" ".m.")
                tl.append((t0 + s - a, t0 + min(e, b) - a, text))
        t0 += b - a
    speech = t0
    total = speech + PROOF_D + END_D
    caps = [(s, min(e, speech), t) for s, e, t in ov.chunk_words(tl)]

    last_path, last_in, last_out = takes[-1]
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(last_out - 0.3, 0):.2f}", "-i",
                    str(last_path), "-frames:v", "1", str(work / "last.jpg")], check=True)
    last = Image.open(work / "last.jpg").convert("RGB").resize((W, H))

    top = int(spec.get("crop_4x5_top", 120))
    formats = {
        "9x16": dict(crop="", y0=0, h=1920, cap=78, capv=680, label_y=290, hook=0.55),
        "4x5": dict(crop=f"crop=1080:1350:0:{top},", y0=top, h=1350, cap=72, capv=110, label_y=top + 30, hook=0.66),
    }
    ec = spec["end_card"]
    music = base / spec["music"] if spec.get("music") else None

    for name, f in formats.items():
        y0, h = f["y0"], f["h"]
        ov.hook_card(W, H, spec["hook"], y0 + int(h * f["hook"]), size=76).save(work / f"hook_{name}.png")
        label_png(spec.get("label", ""), f["label_y"]).save(work / f"label_{name}.png")
        blur = last.filter(ImageFilter.GaussianBlur(26))
        blur = Image.blend(blur, Image.new("RGB", (W, H), ov.GREEN), 0.5).convert("RGBA")
        proof = ov.proof_card(W, H, spec["proof"]["quote"], spec["proof"]["attribution"], y0 + h // 2)
        Image.alpha_composite(blur, proof).convert("RGB").save(work / f"proof_{name}.jpg", quality=94)
        end = Image.new("RGB", (W, H))
        end.paste(ov.end_card(last.crop((0, y0, W, y0 + h)), W, h, ec["eyebrow"], ec["headline"],
                              ec["lines"], ec.get("button", "BOOK NOW"), ec.get("footnote", "")), (0, y0))
        end.save(work / f"end_{name}.jpg", quality=94)
        ass = work / f"caps_{name}.ass"
        ov.write_ass(ass, W, h, caps, f["cap"], f["capv"])

        inputs, vparts, aparts = [], [], []
        for i, (p, a, b) in enumerate(takes):
            inputs += ["-ss", str(a), "-t", f"{b - a:.2f}", "-i", str(p)]
            vparts.append(f"[{i}:v]fps={FPS},scale={W}:{H},setsar=1[v{i}]")
            aparts.append(f"[{i}:a]aresample=48000,afade=t=in:d=0.02,afade=t=out:st={b - a - 0.08:.2f}:d=0.08[a{i}]")
        n = len(takes)
        for img, d in [(f"proof_{name}.jpg", PROOF_D), (f"end_{name}.jpg", END_D)]:
            inputs += ["-loop", "1", "-t", str(d), "-i", str(work / img)]
        for png in [f"hook_{name}.png", f"label_{name}.png"]:
            inputs += ["-loop", "1", "-t", f"{total:.2f}", "-i", str(work / png)]
        ip, ie, ih, il = n, n + 1, n + 2, n + 3
        chain = vparts + aparts + [
            f"[{ip}:v]fps={FPS},setsar=1[vp];[{ie}:v]fps={FPS},setsar=1[ve]",
            "".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[vs][as]",
            "[vs][vp][ve]concat=n=3:v=1:a=0[vb]",
            f"[vb][{ih}:v]overlay=0:0:enable='between(t,0,2.9)'[o1]",
            f"[o1][{il}:v]overlay=0:0:enable='lt(t,{speech:.2f})'[o2]",
            f"[o2]{f['crop']}subtitles='{ffpath(ass)}',format=yuv420p[vout]",
            f"[as]loudnorm=I=-14:TP=-1.5:LRA=11,apad=whole_dur={total:.2f}[vo]",
        ]
        if music:
            inputs += ["-i", str(music)]
            tail = total - speech
            chain += [
                f"[{n + 4}:a]atrim=0:{tail + 0.5:.2f},asetpts=PTS-STARTPTS,loudnorm=I=-20:TP=-2:LRA=11,aresample=48000,afade=t=in:d=0.6,"
                f"afade=t=out:st={tail - 1.2:.2f}:d=1.2,adelay={int((speech - 0.3) * 1000)}:all=1[mb]",
                "[vo][mb]amix=inputs=2:duration=first:normalize=0,aresample=48000[aout]",
            ]
        else:
            chain.append("[vo]anull[aout]")
        out = base / f"{spec['slug']}-{name}.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y"] + inputs + [
            "-filter_complex", ";".join(chain), "-map", "[vout]", "-map", "[aout]", "-t", f"{total:.2f}",
            "-c:v", "libx264", "-preset", "slow", "-crf", "19", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)], check=True)
        print(f"Wrote {out} ({total:.1f}s)")


if __name__ == "__main__":
    main()
