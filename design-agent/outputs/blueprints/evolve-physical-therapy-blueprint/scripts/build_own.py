"""Evolve PT blueprint: 3 ads cut from Dr. Morgan's own Instagram reels (2026-11-26).
Her reels are music-only with their own on-screen text, so: keep her text + music, hook card 0-3s,
name lower-third, organic CTA cut (the clinic tour's QR / "visit my website" ending), 4s offer end card
crossfaded in. Adapted from Rise & Reframe's scripts/build_r3.py own().
Expects vids/<id>.mp4 (python -m yt_dlp -f b -o "<id>.%(ext)s" https://www.instagram.com/reel/<id>/)
Usage: python scripts/build_own.py   (run from the blueprint folder)"""
import pathlib, subprocess, sys
from PIL import Image
P = pathlib.Path(__file__).resolve().parent.parent
REPO = pathlib.Path(r"C:/Users/dylan/Videos/Business/AI Agents/DigiGrowth-Brain")
sys.path.insert(0, str(REPO / "media-buying-agent/tools"))
import ad_overlays as ov  # noqa: E402

CARD, ACC, WARM = (24, 34, 30), (117, 168, 149), (214, 236, 226)
ov.set_palette(card=CARD, accent=ACC, panel=(32, 46, 40))
W, H, FPS, END_S, XF = 1080, 1920, 30, 4.0, 0.35
V, OUT, WORK = P / "vids", P / "ads", P / "own_work"
OUT.mkdir(exist_ok=True); WORK.mkdir(exist_ok=True)
NAME = ("Dr. Morgan Gese, DPT, OCS", "Evolve Physical Therapy · Richland")
OWN = {
    "own-clinic": dict(src="DOpDvBWjiS_", hook="This isn't your typical PT clinic.", cover=(0.125, 470), segs=[(0.0, 28.4, None)]),
    "own-pushup": dict(src="DP2PZuaESPi", hook="Can't do a full push-up yet? Don't skip it. Scale it.", name_at=5.6, poster_at=8.0, segs=[(0.0, 35.6, None)]),
    "own-sideplank": dict(src="DO68xpUjuo5", hook="Hip strength that holds up when you train.", cover=(0.19, 600),
                          segs=[(0.8, 3.8, None), (3.8, 30.0, "288:512:36:64")]),
}


def run(cmd):
    subprocess.run([str(c) for c in cmd], check=True)


def white_logo():
    out = WORK / "logo_white.png"
    lg = Image.open(P / "logo.png").convert("RGBA")
    Image.merge("RGBA", (*[Image.new("L", lg.size, 255)] * 3, lg.getchannel("A"))).save(out)
    return out


def build(name, ad):
    work = WORK / name; work.mkdir(exist_ok=True)
    src = V / f"{ad['src']}.mp4"
    # cover=(y_center, height): a full-width card that hides the reel's own animated title (no words peeking out)
    cy, kw = 0.17, {}
    if ad.get("cover"):
        cy, kw = ad["cover"][0], dict(min_h=ad["cover"][1], margin=0, alpha=255)
    ov.hook_card(W, H, ad["hook"], int(H * cy), size=62, **kw).save(work / "hook.png")
    ov.lower_third(W, H, NAME[0], NAME[1], int(H * 0.56)).save(work / "name.png")
    inputs, parts = [], []
    for i, (a, b, crop) in enumerate(ad["segs"]):
        d = b - a
        inputs += ["-ss", f"{a}", "-t", f"{d:.3f}", "-i", src]
        cf = f"crop={crop}," if crop else ""
        parts.append(f"[{i}:v]{cf}scale={W}:{H},setsar=1,fps={FPS},trim=duration={d:.3f},setpts=PTS-STARTPTS[v{i}];"
                     f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=duration={d:.3f},asetpts=PTS-STARTPTS[a{i}]")
    n = len(ad["segs"])
    dur = sum(b - a for a, b, _ in ad["segs"])
    inputs += ["-i", work / "hook.png", "-i", work / "name.png"]
    # name card after the reel's own intro text (push-up reel: teal title card until ~5s)
    hook_until = 3.0
    nm0 = ad.get("name_at", 3.3)
    nm1 = nm0 + 4.0
    fc = ";".join(parts) + ";" + "".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[vc][ac];" \
         f"[vc][{n}:v]overlay=0:0:enable='lt(t,{hook_until})'[vh];" \
         f"[vh][{n + 1}:v]overlay=0:0:enable='between(t,{nm0},{nm1})'[vout];" \
         f"[ac]loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[aout]"
    body = work / "body.mp4"
    run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", fc, "-map", "[vout]", "-map", "[aout]", "-r", FPS,
         "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
         "-ar", "48000", "-ac", "2", body])
    a, b, crop = ad["segs"][-1]
    fr = work / "frame.jpg"
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{b - 0.5}", "-i", src, "-frames:v", "1",
         "-vf", (f"crop={crop}," if crop else "") + f"scale={W}:{H}", fr])
    ec = work / "end.png"
    ov.offer_end_card(Image.open(fr), W, H, "New Patient Assessment", "$175", "$49", "4.9 on Google",
                      "Dr. Morgan Gese, DPT, OCS · one-on-one", "ONLY 10 SPOTS THIS MONTH", "BOOK NOW",
                      "Richland, WA · no referral needed", logo=white_logo(), scarce_color=WARM).save(ec)
    endv = work / "end.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-t", END_S, "-i", ec, "-f", "lavfi", "-t", END_S,
         "-i", "anullsrc=r=48000:cl=stereo", "-vf", f"scale={W}:{H},setsar=1,format=yuv420p", "-r", FPS,
         "-c:v", "libx264", "-crf", "18", "-c:a", "aac", "-b:a", "160k", "-shortest", endv])
    full = work / f"{name}-9x16.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-i", body, "-i", endv, "-filter_complex",
         f"[0:v]fps={FPS},format=yuv420p,setsar=1[b];[1:v]fps={FPS},format=yuv420p,setsar=1[e];"
         f"[b][e]xfade=transition=fade:duration={XF}:offset={dur - XF:.3f}[v];"
         f"[0:a]afade=t=out:st={dur - 0.6:.3f}:d=0.6[a0];[a0][1:a]acrossfade=d={XF}:c1=nofade:c2=nofade[a]",
         "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "19", "-preset", "slow", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", full])
    web = OUT / f"{name}-web.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-i", full, "-vf", "scale=720:1280", "-c:v", "libx264", "-crf", "26",
         "-preset", "slow", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", web])
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{ad.get('poster_at', 4.5)}", "-i", body, "-frames:v", "1", "-vf", "scale=720:1280",
         OUT / f"{name}_poster.jpg"])
    print(f"{web.name}: {web.stat().st_size / 1e6:.1f} MB, {dur + END_S - XF:.1f}s", flush=True)


if __name__ == "__main__":
    for k, v in OWN.items():
        if len(sys.argv) < 2 or k in sys.argv[1:]:
            build(k, v)
