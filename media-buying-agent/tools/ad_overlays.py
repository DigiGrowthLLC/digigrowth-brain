"""Overlay renderers (PIL) + ASS caption writer for video ads, used by assemble_ugc_ad.py.

Default palette matches the CrosaCore testimonial statics (near-black green card, gold accent);
call set_palette() with a client's colors to restyle. Fonts are Windows system fonts.
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter

F = "C:/Windows/Fonts/"
BOLD = F + "segoeuib.ttf"
SEMI = F + "seguisb.ttf"
REG = F + "segoeui.ttf"
ARIAL = F + "arial.ttf"
ARIALB = F + "arialbd.ttf"

CARD = (12, 19, 16)          # near-black green card, matches the testimonial statics
GOLD = (227, 183, 90)
GOLD_DK = (166, 122, 60)
GREEN = (30, 58, 51)
WHITE = (255, 255, 255)


def set_palette(card=None, accent=None, panel=None):
    """Restyle for another client: RGB tuples for the card fill, accent (stars/button), end-card panel tint."""
    global CARD, GOLD, GREEN
    CARD, GOLD, GREEN = card or CARD, accent or GOLD, panel or GREEN


def font(p, s):
    return ImageFont.truetype(p, s)


def wrap(draw, text, f, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=f) <= maxw:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def text_block(draw, lines, f, cx, y, fill, lh):
    for ln in lines:
        w = draw.textlength(ln, font=f)
        draw.text((cx - w / 2, y), ln, font=f, fill=fill)
        y += lh
    return y


def hook_card(W, H, text, y_center, size=64):
    """Big hook quote on a dark rounded card, centered at y_center. Transparent PNG."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = font(BOLD, size)
    lines = wrap(d, text, f, W - 200)
    lh = int(size * 1.22)
    h = lh * len(lines) + 70
    top = y_center - h // 2
    d.rounded_rectangle((60, top, W - 60, top + h), 28, fill=CARD + (235,))
    d.rounded_rectangle((60, top, W - 60, top + 8), 4, fill=GOLD + (255,))
    text_block(d, lines, f, W / 2, top + 38, WHITE, lh)
    return im


def lower_third(W, H, name, sub, y):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f1, f2 = font(BOLD, 44), font(SEMI, 32)
    w = max(d.textlength(name, font=f1), d.textlength(sub, font=f2)) + 80
    x = 60
    d.rounded_rectangle((x, y, x + w, y + 130), 20, fill=CARD + (230,))
    d.rectangle((x, y + 18, x + 8, y + 112), fill=GOLD + (255,))
    d.text((x + 36, y + 16), name, font=f1, fill=WHITE)
    d.text((x + 36, y + 74), sub, font=f2, fill=GOLD)
    return im


def proof_card(W, H, quote, attribution, y_center):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    fq, fa, fs = font(ARIAL, 46), font(ARIALB, 30), font(REG, 44)
    lines = wrap(d, "\u201c" + quote + "\u201d", fq, W - 220)
    lh = 60
    attr_lines = wrap(d, attribution, fa, W - 220)
    h = 110 + lh * len(lines) + 30 + 42 * len(attr_lines) + 50
    top = y_center - h // 2
    d.rounded_rectangle((60, top, W - 60, top + h), 30, fill=CARD + (240,))
    stars = "\u2605\u2605\u2605\u2605\u2605"
    sw = d.textlength(stars, font=font("C:/Windows/Fonts/seguisym.ttf", 44))
    d.text((W / 2 - sw / 2, top + 36), stars, font=font("C:/Windows/Fonts/seguisym.ttf", 44), fill=GOLD)
    y = text_block(d, lines, fq, W / 2, top + 110, WHITE, lh)
    text_block(d, attr_lines, fa, W / 2, y + 30, GOLD, 42)
    return im


def end_card(bg, W, H, eyebrow, headline, lines, button="BOOK NOW", footnote=""):
    """Full-frame end card over a blurred, tinted background frame (PIL RGB image)."""
    base = bg.convert("RGB").resize((W, H)).filter(ImageFilter.GaussianBlur(28))
    base = Image.blend(base, Image.new("RGB", (W, H), GREEN), 0.72).convert("RGBA")
    d = ImageDraw.Draw(base)
    cy = H // 2
    f_eye, f_h, f_b, f_btn, f_sm = font(BOLD, 38), font(BOLD, 96), font(SEMI, 44), font(BOLD, 50), font(REG, 34)
    y = cy - 430 if H > 1500 else cy - 400
    y = text_block(d, [eyebrow], f_eye, W / 2, y, GOLD, 60) + 30
    y = text_block(d, wrap(d, headline, f_h, W - 160), f_h, W / 2, y, WHITE, 108) + 30
    for ln in lines:
        y = text_block(d, wrap(d, ln, f_b, W - 160), f_b, W / 2, y, (225, 232, 228), 62)
    y += 50
    bw, bh = 620, 120
    d.rounded_rectangle((W / 2 - bw / 2, y, W / 2 + bw / 2, y + bh), 60, fill=GOLD)
    d.text((W / 2 - d.textlength(button, font=f_btn) / 2, y + 28), button, font=f_btn, fill=CARD)
    if footnote:
        text_block(d, [footnote], f_sm, W / 2, y + bh + 50, (200, 210, 205), 44)
    return base.convert("RGB")


def ass_time(t):
    t = max(0, t)
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def write_ass(path, W, H, chunks, size, margin_v):
    """chunks: list of (start, end, text). Bottom-centered bold white captions with black outline."""
    hdr = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Segoe UI Black,{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,6,2,2,60,60,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(hdr)
        for s, e, t in chunks:
            f.write(f"Dialogue: 0,{ass_time(s)},{ass_time(e)},Cap,,0,0,0,,{t}\n")


def chunk_words(words, max_words=3):
    """words: list of (start, end, text) on the output timeline -> caption chunks."""
    chunks, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= max_words or w[2].rstrip().endswith((",", ".", "?", "!")):
            chunks.append(cur); cur = []
    if cur:
        chunks.append(cur)
    out = []
    for i, c in enumerate(chunks):
        s = c[0][0]
        e = chunks[i + 1][0][0] if i + 1 < len(chunks) else c[-1][1] + 0.3
        e = min(e, c[-1][1] + 0.6)
        out.append((s, e, " ".join(x[2].strip() for x in c)))
    return out
