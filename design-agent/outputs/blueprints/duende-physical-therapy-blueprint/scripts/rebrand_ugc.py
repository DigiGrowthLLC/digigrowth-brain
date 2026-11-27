"""Reuse the generic first take of two CrosaCore AI UGC ads for Duende: keep 0..cut (hook + actor's line),
drop everything Austin/CrosaCore after it, add a Duende line card, a real Duende review card and the end card."""
import pathlib, subprocess, sys
from PIL import Image, ImageFilter

REPO = pathlib.Path(r"C:/Users/dylan/Videos/Business/AI Agents/DigiGrowth-Brain")
sys.path.insert(0, str(REPO / "media-buying-agent/tools"))
import ad_overlays as ov

S = pathlib.Path(__file__).parent
C = S / "crosa"
OUT = S / "libads"
W, H = 1080, 1920
ov.set_palette(card=(34, 10, 27), accent=(217, 168, 102), panel=(75, 25, 58))
logo = Image.open(S / "logo.png").convert("RGBA")
logo.thumbnail((360, 230))

ADS = {
    "thursday": {"src": C / "video-back-by-thursday.mp4", "cut": 7.5,
                 "line": "At Duende, every minute is one-on-one with Dr. Natalia, a Doctor of PT. Never an aide.",
                 "quote": "I felt noticeable improvement during the session, and was given tools to continue improving at home.",
                 "attr": "ASHLEY · REAL GOOGLE REVIEW"},
    "squareone": {"src": C / "video-back-to-square-one.mp4", "cut": 5.35,
                  "line": "At Duende, Dr. Natalia finds what keeps setting you back. You choose the finish line.",
                  "quote": "Tries to explore all the possible areas which could be triggering the symptoms and tries to go to the core of the problem.",
                  "attr": "NAVDEEP · REAL GOOGLE REVIEW"},
}
END = dict(eyebrow="DUENDE PT · BERKELEY", headline="$49 Assessment",
           lines=["75 minutes, one-on-one with a DPT", "Pelvic floor + orthopedic PT"],
           button="BOOK NOW", footnote="1911 Addison St, Berkeley")


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
    bg = Image.blend(bg, Image.new("RGB", (W, H), (34, 10, 27)), 0.55).convert("RGBA")

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
    final = OUT / f"duende-ugc-{name}-9x16.mp4"
    run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", "-crf", "21", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(final)])
    web = OUT / f"duende-ugc-{name}-web.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-i", str(final), "-vf", "scale=720:1280", "-c:v", "libx264", "-crf", "27",
         "-preset", "slow", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(web)])
    print(name, f"{web.stat().st_size / 1e6:.1f} MB")
