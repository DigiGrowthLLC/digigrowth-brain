"""Rebuild CrosaCore's two best statics (Google Review Male = corporate-james, Google Review Female =
corporate-shanti format) for Boulder Body Solutions: same quote-card layout, Aaron's real reviews,
his blue, a $49 assessment button. Static 2 uses Aaron's real clinic photo (fal is out of credit,
and the Shanti photo shows a female PT; Aaron practices alone)."""
import pathlib
from PIL import Image, ImageDraw, ImageFont

S = pathlib.Path(__file__).parent
REPO = pathlib.Path(r"C:/Users/dylan/Videos/Business/AI Agents/DigiGrowth-Brain")
F = "C:/Windows/Fonts/"
W, H = 1080, 1350
CARD = (8, 30, 52)          # deep navy from his blue
ACCENT = (143, 180, 220)    # his light blue (#8FB4DC, site's MAT band)
INK = (8, 30, 52)


def font(name, size):
    return ImageFont.truetype(F + name, size)


def wrap(d, text, f, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= maxw:
            cur = t
        else:
            lines.append(cur); cur = w
    lines.append(cur)
    return lines


def card(base: Image.Image, quote, attr, button, out, max_top=None):
    im = base.convert("RGB").copy()
    d = ImageDraw.Draw(im)
    fq, fa, fb = font("arial.ttf", 38), font("arialbd.ttf", 25), font("arialbd.ttf", 34)
    lines = wrap(d, "\u201c" + quote + "\u201d", fq, 900)
    lh = 46
    body = len(lines) * lh + 30 + 34 + 34 + 92
    top = H - 30 - body - 80
    pad = 44
    if max_top is not None and top > max_top:
        pad += (top - max_top) // 2
        top = max_top
    d.rounded_rectangle((38, top, W - 38, H - 30), radius=22, fill=CARD)
    y = top + pad
    for ln in lines:
        d.text((W / 2 - d.textlength(ln, font=fq) / 2, y), ln, font=fq, fill=(255, 255, 255)); y += lh
    y += 22
    d.text((W / 2 - d.textlength(attr, font=fa) / 2, y), attr, font=fa, fill=ACCENT); y += 56
    bw = d.textlength(button, font=fb) + 110
    d.rounded_rectangle((W / 2 - bw / 2, y, W / 2 + bw / 2, y + 88), radius=44, fill=ACCENT, outline=(255, 255, 255), width=3)
    d.text((W / 2 - d.textlength(button, font=fb) / 2, y + 25), button, font=fb, fill=INK)
    im.save(out, quality=90)
    print(out, "panel top", top)


def cover(img, w, h, cx=0.5, cy=0.5):
    img = img.convert("RGB")
    s = max(w / img.width, h / img.height)
    img = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    x = round((img.width - w) * cx); y = round((img.height - h) * cy)
    return img.crop((x, y, x + w, y + h))


(S / "ads").mkdir(exist_ok=True)
james = Image.open(REPO / "media-buying-agent/clients/crosacore/creatives/corporate-james/image.jpg")
card(james, "I've had recurring leg pain/injuries for years, and have been to countless physical therapists that "
     "were unable to treat me effectively. After just a few sessions with Aaron, my pain and mobility improved significantly.",
     "MAX \u00b7 REAL PATIENT REVIEW", "BOOK THE $49 ASSESSMENT", S / "ads/static_review_max.jpg")

# Aaron's real photo: 4:5 crop around him and the patient's leg, pushed up so the card sits over the table.
real = Image.open(S / "photo0.png")
canvas = Image.new("RGB", (W, H), (0, 0, 0))
top_part = cover(real.crop((150, 0, 1100, 733)), W, 820, cx=0.45, cy=0.0)
canvas.paste(top_part, (0, 0))
canvas.paste((22, 24, 26), (0, 820, W, H))  # the table's near-black, behind the card margins
card(canvas, "Best PT in Boulder. Hands down. Aaron has been able to treat chronic pain that has stumped dozens of "
     "other medical professionals.", "AMIE \u00b7 REAL PATIENT REVIEW", "BOOK THE $49 ASSESSMENT", S / "ads/static_review_amie.jpg", max_top=800)
