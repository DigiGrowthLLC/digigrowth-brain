import sys
import subprocess
import pathlib
import datetime

# Auto-install faster-whisper if missing
try:
    from faster_whisper import WhisperModel
except ImportError:
    print("Installing faster-whisper...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "faster-whisper"])
    from faster_whisper import WhisperModel

filename = sys.argv[1] if len(sys.argv) > 1 else None
if not filename:
    print("Usage: python transcribe.py <filename>")
    sys.exit(1)

# Resolve path — check as-is, then Downloads
path = pathlib.Path(filename)
if not path.exists():
    dl = pathlib.Path.home() / "Downloads" / path.name
    if dl.exists():
        path = dl
    else:
        print(f"File not found: {filename}")
        print(f"Also checked: {dl}")
        sys.exit(1)

print(f"Transcribing: {path}")
print("Loading model (base, int8) — first run downloads ~150MB...")
model = WhisperModel("base", device="cpu", compute_type="int8")

segments, info = model.transcribe(str(path), beam_size=5)
print(f"Language: {info.language} ({info.language_probability:.0%})\n")

lines = []
for segment in segments:
    line = segment.text.strip()
    print(line)
    lines.append(line)

out_dir = pathlib.Path(__file__).parent.parent / "outputs"
out_dir.mkdir(exist_ok=True)
date = datetime.date.today().isoformat()
out_path = out_dir / f"transcript-{path.stem}-{date}.txt"
out_path.write_text("\n".join(lines), encoding="utf-8")
print(f"\nSaved to: {out_path}")
