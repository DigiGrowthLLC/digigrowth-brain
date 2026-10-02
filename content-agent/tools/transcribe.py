"""Transcribe a video/audio file with faster-whisper.

Usage:
    python transcribe.py <file>                         # plain-text transcript -> outputs/
    python transcribe.py <file> --words --out <dir>     # + word-level transcript.json for editing
    python transcribe.py <file> --words --model large-v3 --out projects/<title>

Default mode is unchanged: one line per segment, saved to
outputs/transcript-<stem>-<date>.txt.

--words additionally writes, into --out (default: outputs/):
  transcript.json  flat word list [{"text","start","end"}] - the format video-overlay,
                   rough_cut.py and the hyperframes compositions read
  segments.json    [{"text","start","end"}] per spoken segment
and prefixes each .txt line with a [m:ss] timestamp.
"""
import argparse
import datetime
import json
import pathlib
import subprocess
import sys

# Auto-install faster-whisper if missing
try:
    from faster_whisper import WhisperModel
except ImportError:
    print("Installing faster-whisper...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "faster-whisper"])
    from faster_whisper import WhisperModel

parser = argparse.ArgumentParser(description="Transcribe a video/audio file.")
parser.add_argument("filename")
parser.add_argument("--words", action="store_true",
                    help="word-level timestamps -> transcript.json + segments.json")
parser.add_argument("--model", default="base",
                    help="whisper model (base = fast, large-v3 = best for edit timing)")
parser.add_argument("--out", help="output directory (default: content-agent/outputs)")
parser.add_argument("--language", default="en",
                    help="spoken language (default en; pass auto to detect - detection misfires on quiet clips)")
args = parser.parse_args()

# Resolve path — check as-is, then Downloads
path = pathlib.Path(args.filename)
if not path.exists():
    dl = pathlib.Path.home() / "Downloads" / path.name
    if dl.exists():
        path = dl
    else:
        print(f"File not found: {args.filename}")
        print(f"Also checked: {dl}")
        sys.exit(1)

print(f"Transcribing: {path}")
print(f"Loading model ({args.model}, int8) — first run downloads the model...")
model = WhisperModel(args.model, device="cpu", compute_type="int8")

language = None if args.language == "auto" else args.language
segments, info = model.transcribe(str(path), beam_size=5, word_timestamps=args.words, language=language)
print(f"Language: {info.language} ({info.language_probability:.0%})\n")


def stamp(t):
    return f"[{int(t // 60)}:{int(t % 60):02d}]"


lines, words, segs = [], [], []
for segment in segments:
    text = segment.text.strip()
    line = f"{stamp(segment.start)} {text}" if args.words else text
    print(line, flush=True)
    lines.append(line)
    if args.words:
        segs.append({"text": text, "start": round(segment.start, 3), "end": round(segment.end, 3)})
        for w in segment.words or []:
            words.append({"text": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3)})

out_dir = pathlib.Path(args.out) if args.out else pathlib.Path(__file__).parent.parent / "outputs"
out_dir.mkdir(parents=True, exist_ok=True)
date = datetime.date.today().isoformat()
out_path = out_dir / f"transcript-{path.stem}-{date}.txt"
out_path.write_text("\n".join(lines), encoding="utf-8")
print(f"\nSaved to: {out_path}")

if args.words:
    (out_dir / "transcript.json").write_text(json.dumps(words, indent=2), encoding="utf-8")
    (out_dir / "segments.json").write_text(json.dumps(segs, indent=2), encoding="utf-8")
    print(f"Saved word-level transcript ({len(words)} words): {out_dir / 'transcript.json'}")
