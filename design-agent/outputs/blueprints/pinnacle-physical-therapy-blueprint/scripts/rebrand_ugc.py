"""Reuse the generic first take of two CrosaCore AI UGC ads for Pinnacle: keep 0..cut (hook + actor's line),
drop everything Austin/CrosaCore after it, add a Pinnacle line card, a real Pinnacle review card and the end card."""
import pathlib, subprocess, sys
from PIL import Image, ImageFilter

REPO = pathlib.Path(r"C:/Users/dylan/Videos/Business/AI Agents/DigiGrowth-Brain")
sys.path.insert(0, str(REPO / "media-buying-agent/tools"))
import ad_overlays as ov

S = pathlib.Path(__file__).parent
C = S / "crosa"
OUT = S / "libads"
W, H = 1080, 1920
ov.set_palette(card=(8, 34, 42), accent=(255, 171, 94), panel=(20, 92, 110))
logo = Image.open(S / "logo.png").convert("RGBA")
logo.thumbnail((360, 230))

ADS = {
    "thursday": {"src": C / "video-back-by-thursday.mp4", "cut": 7.5,
                 "line": "At Pinnacle, every session is one-on-one with your physical therapist. Never a tech.",
                 "quote": "I've been through physical therapy twice for my back, and never got such quality care and personal attention before.",
                 "attr": "ANDREW · REAL PATIENT REVIEW"},
    "squareone": {"src": C / "video-back-to-square-one.mp4", "cut": 5.35,
                  "line": "At Pinnacle, Dr. Brian Murphy looks at your whole body to find the root cause.",
                  "quote": "He has helped me get through personal injury and get back to triathlon competition.",
                  "attr": "MICHAEL · REAL PATIENT REVIEW"},
}
END = dict(eyebrow="PINNACLE PT · LITTLE ROCK", headline="$49 Discovery Visit",
           lines=["Every session with your PT, never a tech", "No meds, shots or surgery"],
           button="BOOK NOW", footnote="12511 Cantrell Rd, Suite 100")


def run(cmd):
    subprocess.run(cmd, check=True)


def still_clip(img_path, dur, out):
    run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-t", str(dur), "-i", str(img_path),
         "-f", "lavfi", "-t", str(dur), "-i", "anullsrc=r=48000:cl=stereo",
         "-vf", f"scale={W}:{H},setsar=1,format=yuv420p", "-r", "30",
         "-c:v", "libx264", "-crf", "20", "-c:a", "aac", "-b:a", "128k", "-shortest", str(out)])


for name, a in ADS.items():
    work = OUT / f"rb-{name}"
    work.mkdir(parents=True, exist_ok=True)
    head = work / "head.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-i", str(a["src"]), "-t", str(a["cut"]),
         "-vf", f"scale={W}:{H},setsar=1,fps=30", "-af", f"afade=t=out:st={a['cut'] - 0.25}:d=0.25,aresample=48000",
         "-ac", "2", "-c:v", "libx264", "-crf", "20", "-c:a", "aac", "-b:a", "128k", str(head)])
    frame = work / "frame.jpg"
    run(["ffmpeg", "-v", "error", "-y", "-ss", "2.0", "-i", str(a["src"]), "-frames:v", "1", str(frame)])
    bg = Image.open(frame).convert("RGB").resize((W, H)).filter(ImageFilter.GaussianBlur(26))
    bg = Image.blend(bg, Image.new("RGB", (W, H), (8, 34, 42)), 0.55).convert("RGBA")

    line = bg.copy(); line.alpha_composite(ov.hook_card(W, H, a["line"], H // 2, size=62))
    line.convert("RGB").save(work / "line.png")
    proof = bg.copy(); proof.alpha_composite(ov.proof_card(W, H, a["quote"], a["attr"], H // 2))
    proof.convert("RGB").save(work / "proof.png")
    ec = ov.end_card(Image.open(frame), W, H, END["eyebrow"], END["headline"], END["lines"],
                     END["button"], END["footnote"]).convert("RGBA")
    ec.alpha_composite(logo, ((W - logo.width) // 2, 110))
    ec.convert("RGB").save(work / "end.png")

    parts = [head]
    for nm, dur in (("line", 3.0), ("proof", 3.5), ("end", 3.0)):
        still_clip(work / f"{nm}.png", dur, work / f"{nm}.mp4")
        parts.append(work / f"{nm}.mp4")
    inputs = sum((["-i", str(p)] for p in parts), [])
    fc = "".join(f"[{i}:v][{i}:a]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=1:a=1[v][a]"
    final = OUT / f"pinnacle-ugc-{name}-9x16.mp4"
    run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", "-crf", "21", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(final)])
    web = OUT / f"pinnacle-ugc-{name}-web.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-i", str(final), "-vf", "scale=720:1280", "-c:v", "libx264", "-crf", "27",
         "-preset", "slow", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(web)])
    print(name, f"{web.stat().st_size / 1e6:.1f} MB")
