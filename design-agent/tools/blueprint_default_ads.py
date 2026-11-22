"""
The default AI ads for every Patient Acquisition Blueprint (Dylan, 2026-10-28), rebranded per
practice from references/default-ads/:
- static_headline.jpg  CrosaCore's "Corporate Female" headline card (corporate-lauren)
- static_review.jpg    CrosaCore's Dawn review card (corporate-dawn)
- ugc-thursday-web.mp4 "Back by Thursday" AI UGC: the generic first 7.5s, then a practice line
                       card, a real review card and a $49 end card (+ a full-size -9x16.mp4)
Each keeps the original photo/footage and paints a new panel in the practice's colors over the
old CrosaCore one.

Usage: python blueprint_default_ads.py <practice.json> <out_dir>
practice.json (logo path relative to the json):
{
  "logo": "logo.png",
  "palette": {"card": [8,30,52], "accent": [143,180,220], "panel": [14,52,92], "button_text": [8,32,53]},
  "headline_static": {"eyebrow": "PRACTICE · CITY, ST", "headline": "...", "sub": "...", "button": "BOOK THE $49 ASSESSMENT"},
  "review_static": {"quote": "verbatim review", "attr": "FIRST · REAL PATIENT REVIEW", "button": "BOOK THE $49 ASSESSMENT"},
  "ugc": {"line": "At <Practice>, ...", "quote": "verbatim review", "attr": "FIRST · REAL PATIENT REVIEW"},
  "end_card": {"eyebrow": "...", "headline": "$49 Assessment", "lines": ["...", "..."], "button": "BOOK NOW", "footnote": "address"}
}
"""
import json
import pathlib
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "design-agent/references/default-ads"
sys.path.insert(0, str(ROOT / "media-buying-agent/tools"))
import ad_overlays as ov  # noqa: E402

F = "C:/Windows/Fonts/"
W, H = 1080, 1350
# The CrosaCore panels these cover start at y=857 (headline card) and y=885 (review card).
PANEL_TOP_MAX = 845


def font(name, size):
    return ImageFont.truetype(F + name, size)


def wrap(d, text, f, maxw):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= maxw:
            cur = t
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def panel(img_path, blocks, button, pal, out):
    """blocks: [(text, font, color, line_height, gap_after)] drawn centered, then the button."""
    im = Image.open(img_path).convert("RGB")
    d = ImageDraw.Draw(im)
    laid = [(wrap(d, t, f, 920), f, c, lh, gap) for t, f, c, lh, gap in blocks]
    fb = font("arialbd.ttf", 34)
    content = sum(len(ls) * lh + gap for ls, _, _, lh, gap in laid) + 88
    top = min(H - 30 - content - 88, PANEL_TOP_MAX)
    d.rounded_rectangle((38, top, W - 38, H - 30), radius=22, fill=tuple(pal["card"]))
    y = top + (H - 30 - top - content) // 2
    for lines, f, c, lh, gap in laid:
        for ln in lines:
            d.text((W / 2 - d.textlength(ln, font=f) / 2, y), ln, font=f, fill=c)
            y += lh
        y += gap
    bw = d.textlength(button, font=fb) + 110
    d.rounded_rectangle((W / 2 - bw / 2, y, W / 2 + bw / 2, y + 88), radius=44, fill=tuple(pal["accent"]),
                        outline=(255, 255, 255), width=3)
    d.text((W / 2 - d.textlength(button, font=fb) / 2, y + 25), button, font=fb,
           fill=tuple(pal.get("button_text") or pal["card"]))
    im.save(out, quality=90)


def run(cmd):
    subprocess.run(cmd, check=True)


def still_clip(img, dur, out, w, h):
    run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-t", str(dur), "-i", str(img),
         "-f", "lavfi", "-t", str(dur), "-i", "anullsrc=r=48000:cl=stereo",
         "-vf", f"scale={w}:{h},setsar=1,format=yuv420p", "-r", "30",
         "-c:v", "libx264", "-crf", "20", "-c:a", "aac", "-b:a", "128k", "-shortest", str(out)])


def ugc(p, base, out):
    vw, vh = 1080, 1920
    pal = p["palette"]
    ov.set_palette(card=tuple(pal["card"]), accent=tuple(pal["accent"]), panel=tuple(pal.get("panel") or pal["card"]))
    work = out / "_ugc"
    work.mkdir(parents=True, exist_ok=True)
    src = SRC / "ugc-back-by-thursday-head.mp4"
    head = work / "head.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vf", f"scale={vw}:{vh},setsar=1,fps=30",
         "-af", "afade=t=out:st=7.25:d=0.25,aresample=48000", "-ac", "2",
         "-c:v", "libx264", "-crf", "20", "-c:a", "aac", "-b:a", "128k", str(head)])
    frame = work / "frame.jpg"
    run(["ffmpeg", "-v", "error", "-y", "-ss", "2.0", "-i", str(src), "-frames:v", "1", str(frame)])
    bg = Image.open(frame).convert("RGB").resize((vw, vh)).filter(ImageFilter.GaussianBlur(26))
    bg = Image.blend(bg, Image.new("RGB", (vw, vh), tuple(pal["card"])), 0.55).convert("RGBA")
    u = p["ugc"]
    line = bg.copy(); line.alpha_composite(ov.hook_card(vw, vh, u["line"], vh // 2, size=62))
    line.convert("RGB").save(work / "line.png")
    proof = bg.copy(); proof.alpha_composite(ov.proof_card(vw, vh, u["quote"], u["attr"], vh // 2))
    proof.convert("RGB").save(work / "proof.png")
    e = p["end_card"]
    ec = ov.end_card(Image.open(frame), vw, vh, e["eyebrow"], e["headline"], e["lines"], e.get("button", "BOOK NOW"),
                     e.get("footnote", "")).convert("RGBA")
    if p.get("logo"):
        logo = Image.open(base / p["logo"]).convert("RGBA")
        logo.thumbnail((560, 230))
        # White silhouette: a brand-colored logo can vanish on the brand-colored end card.
        logo = Image.merge("RGBA", (*[Image.new("L", logo.size, 255)] * 3, logo.getchannel("A")))
        ec.alpha_composite(logo, ((vw - logo.width) // 2, 110))
    ec.convert("RGB").save(work / "end.png")
    parts = [head]
    for nm, dur in (("line", 3.0), ("proof", 3.5), ("end", 3.0)):
        still_clip(work / f"{nm}.png", dur, work / f"{nm}.mp4", vw, vh)
        parts.append(work / f"{nm}.mp4")
    inputs = sum((["-i", str(x)] for x in parts), [])
    fc = "".join(f"[{i}:v][{i}:a]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=1:a=1[v][a]"
    final = out / "ugc-thursday-9x16.mp4"
    run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", "-crf", "21", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(final)])
    web = out / "ugc-thursday-web.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-i", str(final), "-vf", "scale=720:1280", "-c:v", "libx264", "-crf", "27",
         "-preset", "slow", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(web)])
    print(f"{web} ({web.stat().st_size / 1e6:.1f} MB)")


def main():
    if len(sys.argv) != 3:
        print("Usage: python blueprint_default_ads.py <practice.json> <out_dir>")
        sys.exit(1)
    src = pathlib.Path(sys.argv[1]).resolve()
    base = src.parent
    out = pathlib.Path(sys.argv[2]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    p = json.loads(src.read_text(encoding="utf-8"))
    pal = p["palette"]
    accent = tuple(pal["accent"])

    hs = p["headline_static"]
    panel(SRC / "headline-static.jpg", [
        (hs["eyebrow"], font("arialbd.ttf", 26), accent, 34, 22),
        (hs["headline"], font("arialbd.ttf", 50), (255, 255, 255), 58, 18),
        (hs["sub"], font("arial.ttf", 27), (226, 232, 240), 35, 30),
    ], hs.get("button", "BOOK THE $49 ASSESSMENT"), pal, out / "static_headline.jpg")
    print(out / "static_headline.jpg")

    rs = p["review_static"]
    panel(SRC / "review-static.jpg", [
        ("\u201c" + rs["quote"] + "\u201d", font("arial.ttf", 37), (255, 255, 255), 45, 20),
        (rs["attr"], font("arialbd.ttf", 25), accent, 32, 28),
    ], rs.get("button", "BOOK THE $49 ASSESSMENT"), pal, out / "static_review.jpg")
    print(out / "static_review.jpg")

    ugc(p, base, out)


if __name__ == "__main__":
    main()
