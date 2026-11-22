"""Rise & Reframe blueprint ads, round 3 (Dylan 2026-11-22):
- 3 own-video cuts redone: burned-in source captions frosted out, clean word-timed captions, hook card,
  name card, 5.0-on-Google badge, crossfaded offer end card (stars + $150/$49 + 10 spots this month).
- AI row = ads that actually ran: CrosaCore "Back by Thursday" + "Back to Square One" UGC (generic
  first take, then her line card, a real review card and the same end card), and Boulder's approved
  "Pain that keeps coming back?" checklist static rebuilt in her colors.
Usage: python build_r3.py [own] [ugc] [static]
"""
import json
import pathlib
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter

B = pathlib.Path(__file__).resolve().parent          # .../blueprint-rise-reframe/cut
P = B.parent                                          # .../blueprint-rise-reframe
REPO = pathlib.Path(r"C:/Users/dylan/Videos/Business/AI Agents/DigiGrowth-Brain")
sys.path.insert(0, str(REPO / "media-buying-agent/tools"))
import ad_overlays as ov  # noqa: E402

CARD, ACC = (46, 28, 15), (198, 156, 85)
ov.set_palette(card=CARD, accent=ACC, panel=(59, 36, 19))
W, H, FPS, END_S, XF = 1080, 1920, 30, 4.0, 0.35
OUT = P / "ads"
WORK = B / "work"
WORK.mkdir(exist_ok=True)
RATING, PROOF_LINE = "5.0 on Google", "Dr. BettyLou DeYoung, DPT · one-on-one"
SCARCE = "ONLY 10 SPOTS THIS MONTH"
WARM = (240, 214, 168)


def run(cmd):
    subprocess.run([str(c) for c in cmd], check=True)


def white_logo():
    out = WORK / "logo_white.png"
    lg = Image.open(P / "logo.png").convert("RGBA")
    lg = Image.merge("RGBA", (*[Image.new("L", lg.size, 255)] * 3, lg.getchannel("A")))
    lg.save(out)
    return out


def end_card(bg):
    return ov.offer_end_card(bg, W, H, "New Patient Assessment", "$150", "$49", RATING, PROOF_LINE, SCARCE,
                             "BOOK NOW", "Temecula & Murrieta · no referral needed", logo=white_logo(),
                             scarce_color=WARM)


def star_badge(text, y):
    """Small dark pill with 5 gold stars + text, top-center (social proof that stays on screen)."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = ov.font(ov.SEMI, 38)
    r, gap = 17, 40
    tw = d.textlength(text, font=f)
    bw = 5 * gap + 24 + tw + 70
    x0 = (W - bw) / 2
    d.rounded_rectangle((x0, y, x0 + bw, y + 78), 39, fill=CARD + (225,), outline=ACC + (160,), width=2)
    for i in range(5):
        ov._star(d, x0 + 35 + r + i * gap, y + 39, r, ACC)
    d.text((x0 + 35 + 5 * gap + 14, y + 40), text, font=f, fill=(255, 255, 255, 255), anchor="lm")
    return im


def still(img, dur, out):
    run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-t", dur, "-i", img,
         "-f", "lavfi", "-t", dur, "-i", "anullsrc=r=48000:cl=stereo",
         "-vf", f"scale={W}:{H},setsar=1,format=yuv420p", "-r", FPS,
         "-c:v", "libx264", "-crf", "18", "-c:a", "aac", "-b:a", "160k", "-shortest", out])


def web(src, out):
    run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vf", "scale=720:1280", "-c:v", "libx264", "-crf", "26",
         "-preset", "slow", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", out])
    print(f"{out.name}: {out.stat().st_size / 1e6:.1f} MB", flush=True)


def with_end(body, dur, bgframe, name):
    """Crossfade the offer end card onto the body, write <name>-9x16.mp4 + <name>-web.mp4."""
    ec = WORK / f"{name}_end.png"
    end_card(Image.open(bgframe)).save(ec)
    endv = WORK / f"{name}_end.mp4"
    still(ec, END_S, endv)
    full = WORK / f"{name}-9x16.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-i", body, "-i", endv, "-filter_complex",
         f"[0:v]fps={FPS},format=yuv420p,setsar=1[b];[1:v]fps={FPS},format=yuv420p,setsar=1[e];"
         f"[b][e]xfade=transition=fade:duration={XF}:offset={dur - XF:.3f}[v];"
         f"[0:a]afade=t=out:st={dur - 0.25:.3f}:d=0.25[a0];[a0][1:a]acrossfade=d={XF}:c1=nofade:c2=nofade[a]",
         "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "19", "-preset", "slow", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", full])
    web(full, OUT / f"{name}-web.mp4")


# ---------------------------------------------------------------- own videos
V = P / "vids"
OWN = {
    "own-matt": dict(
        src="Fbqz5pDNA0w", hook="Spiral fracture. A rod from knee to ankle. Pain every day.",
        name=("Matt, 29", "Real Rise & Reframe patient"),
        segs=[(17.20, 19.30), (20.38, 30.72), (50.52, 56.30), (59.50, 63.48), (105.00, 116.55), (124.36, 125.22)],
        fixes={"life -changing": "life-changing", "I'm 29.": "I'm 29."}),
    "own-eval": dict(
        src="lrqlYgXohhE", hook="Hip or back pain that won't quit? Here's what we look for first.",
        name=("Dr. BettyLou DeYoung, DPT", "Rise & Reframe Physical Therapy"),
        segs=[(18.02, 26.04), (26.04, 40.94), (55.40, 61.90), (64.36, 72.30)],
        fixes={"So when": "When", "a torn": "a tear"}),
    "own-matt-week4": dict(
        src="yetN8A8_yh0", video="yetN8A8_yh0_fix", hook="Matt, 4 weeks into PT with Dr. BettyLou", top_strip=True,
        name=("Matt, week 4", "Real Rise & Reframe patient"),
        segs=[(8.74, 15.95), (128.00, 137.55), (174.78, 177.48)],
        fixes={"10 %": "10%", "30 %": "30%", "pain -wise": "pain-wise"}),
}
CAP_BAND = (0.695, 0.815)   # source's own burned-in captions sit here
TOP_BAND = (0.13, 0.235)    # week-4 video also flashes words up here


def own(name, ad):
    work = WORK / name
    work.mkdir(exist_ok=True)
    words = json.load(open(B / "transcripts" / f"{ad['src']}.words.json"))
    timeline, off = [], 0.0
    for a, b in ad["segs"]:
        for ws, we, t in words:
            if ws >= a - 0.05 and we <= b + 0.15:
                timeline.append((max(ws, a) - a + off, min(we, b) - a + off, t))
        off += b - a
    dur = off
    chunks = []
    for s, e, t in ov.chunk_words(timeline, 3):
        t = t.replace(" -", "-")
        for k, v in ad.get("fixes", {}).items():
            t = t.replace(k, v)
        chunks.append((s, e, t))
    hook_until = 3.0
    ass = work / "caps.ass"
    ov.write_ass(ass, W, H, chunks, 84, int(H * (1 - CAP_BAND[1])) + 22)
    ov.hook_card(W, H, ad["hook"], int(H * 0.17), size=62).save(work / "hook.png")
    ov.lower_third(W, H, ad["name"][0], ad["name"][1], int(H * 0.56)).save(work / "name.png")
    star_badge("5.0 on Google · 18 reviews", int(H * 0.055)).save(work / "badge.png")

    inputs, parts = [], []
    # Round 4 (Dylan): no frosted strips, no added captions or star badge; her videos keep their own captions.
    bands = []
    for i, (a, b) in enumerate(ad["segs"]):
        d = b - a
        inputs += ["-ss", f"{a}", "-t", f"{d:.3f}", "-i", V / f"{ad.get('video', ad['src'])}.mp4"]
        parts.append(f"[{i}:v]scale={W}:{H},setsar=1,fps={FPS},trim=duration={d:.3f},setpts=PTS-STARTPTS[v{i}];"
                     f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=duration={d:.3f},asetpts=PTS-STARTPTS,"
                     f"afade=t=in:d=0.04,afade=t=out:st={max(d - 0.07, 0):.3f}:d=0.07[a{i}]")
    n = len(ad["segs"])
    inputs += ["-i", work / "hook.png", "-i", work / "name.png", "-i", work / "badge.png"]
    # feathered frosted strips over the source's burned-in captions (one mask PNG per strip, looped)
    chain, cur = "", "vc"
    for j, (f0, f1) in enumerate(bands):
        y0, y1 = int(H * f0) // 2 * 2 - 40, int(H * f1) // 2 * 2 + 40
        bh = y1 - y0
        m = Image.new("L", (W, bh), 0)
        md = ImageDraw.Draw(m)
        for yy in range(bh):
            e = min(yy, bh - 1 - yy)
            md.line([(0, yy), (W, yy)], fill=int(255 * min(1, e / 60)))
        m.save(work / f"mask{j}.png")
        inputs += ["-loop", "1", "-framerate", FPS, "-t", f"{dur:.3f}", "-i", work / f"mask{j}.png"]
        mi = n + 3 + j
        chain += (f"[{cur}]split[o{j}][s{j}];[s{j}]crop={W}:{bh}:0:{y0},boxblur=24:2,eq=brightness=-0.05,format=yuva420p[sb{j}];"
                  f"[{mi}:v]format=gray[mk{j}];[sb{j}][mk{j}]alphamerge[sm{j}];[o{j}][sm{j}]overlay=0:{y0}:shortest=1[f{j}];")
        cur = f"f{j}"
    nm0, nm1 = hook_until + 0.3, hook_until + 4.3
    assp = str(ass).replace("\\", "/").replace(":", "\:")
    fc = ";".join(parts) + ";" + "".join(f"[v{i}][a{i}]" for i in range(n)) +         f"concat=n={n}:v=1:a=1[vc][ac];" + chain +         f"[{cur}][{n}:v]overlay=0:0:enable='lt(t,{hook_until})'[vh];"         f"[vh][{n + 1}:v]overlay=0:0:enable='between(t,{nm0},{nm1})'[vn];"         f"[vn]null[vout];[ac]loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[aout]"
    body = work / "body.mp4"
    run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", fc, "-map", "[vout]", "-map", "[aout]",
         "-r", FPS, "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2", body])
    fr = work / "frame.jpg"
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{ad['segs'][-1][1] - 0.5}", "-i", V / f"{ad.get('video', ad['src'])}.mp4",
         "-frames:v", "1", "-vf", f"scale={W}:{H}", fr])
    with_end(body, dur, fr, name)
    # poster for the blueprint card: a frame just after the hook, badge + name visible
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{hook_until + 1.2}", "-i", body, "-frames:v", "1",
         "-vf", "scale=720:1280", OUT / f"{name}_poster.jpg"])


# ---------------------------------------------------------------- AI UGC
UGC = {
    "ugc-thursday": dict(
        src=B / "work/ugc-thursday/longhead.mp4", cut=17.70,
        line="At Rise & Reframe, every session is one-on-one with Dr. BettyLou. Never an aide.",
        quote="After her evaluation, she had identified a number of issues (including some I couldn't have "
              "self-diagnosed in a million years). In just an hour I saw significant improvement in my movement.",
        attr="RICK · REAL GOOGLE REVIEW"),
    "ugc-square-one": dict(
        src=B / "work/ugc-square-one/longhead.mp4", cut=19.16,
        line="In Temecula, Dr. BettyLou DeYoung, DPT works one-on-one, start to finish.",
        quote="By practicing and doing the exercises that Dr. Betty suggested, I have had very good improvement "
              "in my hip, back and leg pain. If you're thinking about personal 1 on 1 physical therapy, I highly recommend Rise and Reframe.",
        attr="KEVIN · REAL GOOGLE REVIEW"),
}


def ugc(name, u):
    work = WORK / name
    work.mkdir(exist_ok=True)
    head = work / "head.mp4"
    c = u["cut"]
    run(["ffmpeg", "-v", "error", "-y", "-t", c, "-i", u["src"], "-vf", f"scale={W}:{H},setsar=1,fps={FPS}",
         "-af", f"afade=t=out:st={c - 0.2:.2f}:d=0.2,aresample=48000", "-ac", "2",
         "-c:v", "libx264", "-crf", "18", "-c:a", "aac", "-b:a", "160k", head])
    frame = work / "frame.jpg"
    run(["ffmpeg", "-v", "error", "-y", "-ss", "2.0", "-i", u["src"], "-frames:v", "1", "-vf", f"scale={W}:{H}", frame])
    bg = Image.open(frame).convert("RGB").filter(ImageFilter.GaussianBlur(26))
    bg = Image.blend(bg, Image.new("RGB", (W, H), CARD), 0.6).convert("RGBA")
    line = bg.copy()
    line.alpha_composite(ov.hook_card(W, H, u["line"], H // 2, size=62))
    line.convert("RGB").save(work / "line.png")
    proof = bg.copy()
    proof.alpha_composite(ov.proof_card(W, H, u["quote"], u["attr"], H // 2 + 40))
    proof.convert("RGB").save(work / "proof.png")
    parts = [head]
    for nm, dur in (("proof", 4.0),):
        still(work / f"{nm}.png", dur, work / f"{nm}.mp4")
        parts.append(work / f"{nm}.mp4")
    inputs = sum((["-i", x] for x in parts), [])
    fc = "".join(f"[{i}:v][{i}:a]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=1:a=1[v][a]"
    body = work / "body.mp4"
    run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", body])
    with_end(body, c + 4.0, frame, name)
    run(["ffmpeg", "-v", "error", "-y", "-ss", "1.2", "-i", head, "-frames:v", "1", "-vf", "scale=720:1280",
         OUT / f"{name}_poster.jpg"])


# ---------------------------------------------------------------- static (Boulder C10 review-card layout, AI photo)
def static():
    SW, SH = 1080, 1350
    CREAM, INK = (247, 242, 233), (40, 28, 18)
    im = Image.new("RGB", (SW, SH), CARD)
    d = ImageDraw.Draw(im)
    TOP = 300
    d.rectangle((0, 0, SW, TOP), fill=CREAM)
    for i in range(5):
        ov._star(d, 74 + i * 44, 58, 19, ACC)
    d.text((74 + 5 * 44 + 6, 59), "5.0 on Google  ·  Temecula & Murrieta", font=ov.font(ov.SEMI, 32), fill=(110, 95, 80), anchor="lm")
    q = ("“2 years of shoulder pain. Traditional PT, massage, rest... nothing worked. "
         "After 2 sessions my pain was drastically reduced.”")
    fq = ov.font(ov.BOLD, 44)
    y = 100
    for ln in ov.wrap(d, q, fq, SW - 120):
        d.text((60, y), ln, font=fq, fill=INK); y += 56
    PH = 670
    ph = Image.open(B / "takes/static-shoulder-f.png").convert("RGB")
    sc = max(SW / ph.width, PH / ph.height)
    ph = ph.resize((round(ph.width * sc), round(ph.height * sc)))
    ox, oy = (ph.width - SW) // 2, (ph.height - PH) // 2
    im.paste(ph.crop((ox, oy, ox + SW, oy + PH)), (0, TOP))
    pill = "One-on-one with Dr. BettyLou DeYoung, DPT"
    fp = ov.font(ov.SEMI, 32)
    pw = d.textlength(pill, font=fp) + 48
    py = TOP + PH - 74
    d.rounded_rectangle((40, py, 40 + pw, py + 54), 27, fill=(30, 20, 12))
    d.text((64, py + 28), pill, font=fp, fill=(255, 255, 255), anchor="lm")
    y0 = TOP + PH
    d.rectangle((0, y0, SW, SH), fill=(46, 28, 15))
    d.text((54, y0 + 30), "New Patient Assessment", font=ov.font(ov.BOLD, 54), fill=(255, 255, 255))
    fw, fn2 = ov.font(ov.BOLD, 56), ov.font(ov.BOLD, 92)
    x, yb = 56, y0 + 186
    d.text((x, yb), "$150", font=fw, fill=(190, 170, 150), anchor="ls")
    ww = d.textlength("$150", font=fw)
    d.line([(x - 6, yb - 12), (x + ww + 6, yb - 38)], fill=ACC, width=7)
    d.text((x + ww + 24, yb), "$49", font=fn2, fill=ACC, anchor="ls")
    nx = x + ww + 24 + d.textlength("$49", font=fn2) + 30
    d.text((nx, yb - 8), "Only 10 new-patient spots this month", font=ov.font(ov.SEMI, 34), fill=WARM, anchor="ls")
    bw, bh = SW - 108, 104
    by = SH - bh - 30
    d.rounded_rectangle((54, by, 54 + bw, by + bh), bh / 2, fill=ACC)
    d.text((SW / 2, by + bh / 2 + 2), "BOOK NOW  ·  CLAIM YOUR SPOT", font=ov.font(ov.BOLD, 50), fill=CARD, anchor="mm")
    im.save(OUT / "static_review.jpg", quality=92)
    print("static_review.jpg")


if __name__ == "__main__":
    want = set(sys.argv[1:]) or {"own", "ugc", "static"}
    if "static" in want:
        static()
    if "ugc" in want:
        for k, v in UGC.items():
            ugc(k, v)
    if "own" in want or want & set(OWN):
        for k, v in OWN.items():
            if "own" in want or k in want:
                own(k, v)
