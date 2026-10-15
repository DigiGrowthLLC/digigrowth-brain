"""Cut Pinnacle's own videos into 9:16 ad previews: trim segments, crop, captions, hook card, end card."""
import json, subprocess, sys, pathlib
from PIL import Image

REPO = pathlib.Path(r"C:/Users/dylan/Videos/Business/AI Agents/DigiGrowth-Brain")
sys.path.insert(0, str(REPO / "media-buying-agent/tools"))
import ad_overlays as ov
from faster_whisper import WhisperModel

S = pathlib.Path(__file__).parent
V = S / "vids"
OUT = S / "social"
OUT.mkdir(exist_ok=True)
W, H = 720, 1280
ov.set_palette(card=(8, 34, 42), accent=(255, 171, 94), panel=(20, 92, 110))

CUTS = {
    "cut1": {"src": "ixMeCbQ2gZY.mp4", "crop": None, "segs": [(0.0, 41.5), (49.7, 58.3)],
             "hook": "Retired from Channel 7, then plantar fasciitis hit"},
    "cut2": {"src": "VC6Gu2c3pg8.mp4", "crop": (608, 1080, 656, 0), "segs": [(40.85, 64.7), (98.3, 105.8), (114.95, 115.75)],
             "hook": "\"I've been to PT before. It didn't help.\""},
    "cut3": {"src": "1_-fjlolliI.mp4", "crop": (484, 860, 618, 0), "segs": [(0.0, 21.3), (62.7, 84.2)],
             "hook": "Jaw pain, headaches, clicking when you chew?"},
}
END = dict(eyebrow="LITTLE ROCK, AR", headline="$49 Discovery Visit",
           lines=["Every session with your PT, never a tech", "No meds, shots or surgery"],
           button="BOOK NOW", footnote="12511 Cantrell Rd, Suite 100")

model = WhisperModel("small", device="cpu", compute_type="int8")
logo = Image.open(S / "logo.png").convert("RGBA")
logo.thumbnail((240, 150))


def run(cmd):
    subprocess.run(cmd, check=True)


for name, c in CUTS.items():
    if len(sys.argv) > 1 and name not in sys.argv[1:]:
        continue
    src = V / c["src"]
    segs, _ = model.transcribe(str(src), word_timestamps=True)
    words = [(w.start, w.end, w.word) for s in segs for w in s.words]
    # map words into the output timeline
    out_words, offset = [], 0.0
    for a, b in c["segs"]:
        for ws, we, t in words:
            if ws >= a - 0.05 and we <= b + 0.15:
                out_words.append((ws - a + offset, min(we, b) - a + offset, t))
        offset += b - a
    body_dur = offset
    chunks = [(s, e, t.replace("Permey", "Perme").replace("tempromandibular", "temporomandibular"))
              for s, e, t in ov.chunk_words(out_words, 3)]
    ass = OUT / f"{name}.ass"
    ov.write_ass(ass, W, H, chunks, 60, 300)

    # hook card for the first 3.2s
    hook_png = OUT / f"{name}-hook.png"
    ov.hook_card(W, H, c["hook"], 210, size=46).save(hook_png)

    # body: trim + concat + crop + captions + hook
    vf = ("crop=%d:%d:%d:%d," % c["crop"] if c["crop"] is not None else "") + f"scale={W}:{H},setsar=1"
    parts, inputs = [], ["-i", str(src)]
    for i, (a, b) in enumerate(c["segs"]):
        parts.append(f"[0:v]trim={a}:{b},setpts=PTS-STARTPTS,{vf}[v{i}];[0:a]atrim={a}:{b},asetpts=PTS-STARTPTS[a{i}]")
    n = len(c["segs"])
    cat = "".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[vc][ac]"
    assp = str(ass).replace("\\", "/").replace(":", "\\:")
    fc = ";".join(parts) + ";" + cat + f";[vc]ass='{assp}'[vs];[vs][1:v]overlay=0:0:enable='lt(t,3.2)'[vout]"
    body = OUT / f"{name}-body.mp4"
    run(["ffmpeg", "-v", "error", "-y", *inputs, "-i", str(hook_png), "-filter_complex", fc,
         "-map", "[vout]", "-map", "[ac]", "-r", "30", "-c:v", "libx264", "-crf", "20", "-preset", "medium",
         "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2", str(body)])

    # end card from a frame of the body
    fr = OUT / f"{name}-frame.jpg"
    run(["ffmpeg", "-v", "error", "-y", "-ss", "1.0", "-i", str(src), "-frames:v", "1",
         "-vf", vf, str(fr)])
    ec = ov.end_card(Image.open(fr), W, H, END["eyebrow"], END["headline"], END["lines"],
                     END["button"], END["footnote"]).convert("RGBA")
    ec.alpha_composite(logo, ((W - logo.width) // 2, 60))
    ec_png = OUT / f"{name}-end.png"
    ec.convert("RGB").save(ec_png)
    endv = OUT / f"{name}-end.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-t", "2.5", "-i", str(ec_png),
         "-f", "lavfi", "-t", "2.5", "-i", "anullsrc=r=44100:cl=stereo",
         "-vf", f"scale={W}:{H},setsar=1,format=yuv420p", "-r", "30", "-c:v", "libx264", "-crf", "20",
         "-c:a", "aac", "-b:a", "128k", "-shortest", str(endv)])

    final = OUT / f"{name}.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-i", str(body), "-i", str(endv), "-filter_complex",
         "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]", "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", "-crf", ("33" if name == "cut3" else "27"), "-preset", "slow", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(final)])
    mb = final.stat().st_size / 1e6
    print(f"{name}: {body_dur + 2.5:.1f}s, {mb:.1f} MB")
    json.dump(chunks, open(OUT / f"{name}-captions.json", "w"), indent=0)
