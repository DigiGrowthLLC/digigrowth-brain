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


def hook_card(W, H, text, y_center, size=64, margin=60, min_h=0, alpha=235):
    """Big hook quote on a dark rounded card, centered at y_center. Transparent PNG.
    margin/min_h/alpha let the card double as a cover over burned-in source text."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = font(BOLD, size)
    lines = wrap(d, text, f, W - 200)
    lh = int(size * 1.22)
    h = max(lh * len(lines) + 70, min_h)
    top = y_center - h // 2
    d.rounded_rectangle((margin, top, W - margin, top + h), 28, fill=CARD + (alpha,))
    d.rounded_rectangle((margin, top, W - margin, top + 8), 4, fill=GOLD + (255,))
    top += (h - (lh * len(lines) + 70)) // 2
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


def price_end_card(bg, W, H, eyebrow, name, was, now, anchor_note, badge, lines, urgency,
                   button="BOOK NOW", footnote="", logo=None):
    """Offer end card with a visible price anchor + scarcity (paid offers, e.g. $49 vs $150, 10 a month).

    Struck-through `was` price next to a big `now` price, an accent-filled scarcity badge, an urgency
    line over the button. Real limits only: never invent countdowns. `logo` = optional path (RGBA PNG).
    """
    base = bg.convert("RGB").resize((W, H)).filter(ImageFilter.GaussianBlur(28))
    base = Image.blend(base, Image.new("RGB", (W, H), GREEN), 0.78).convert("RGBA")
    d = ImageDraw.Draw(base)
    tall = H > 1500
    s = 1.0 if tall else 0.86
    f_eye, f_name = font(BOLD, int(36 * s)), font(BOLD, int(76 * s))
    f_was, f_now = font(BOLD, int(96 * s)), font(BOLD, int(210 * s))
    f_note, f_badge = font(SEMI, int(36 * s)), font(BOLD, int(44 * s))
    f_ln, f_urg, f_btn, f_sm = font(SEMI, int(40 * s)), font(BOLD, int(46 * s)), font(BOLD, int(52 * s)), font(REG, int(32 * s))

    items = []  # (height, draw_fn)
    lg = None
    if logo:
        lg = Image.open(logo).convert("RGBA")
        lg.thumbnail((int(300 * s), int(170 * s)))
        items.append((lg.height + 30, lambda y: base.alpha_composite(lg, (int(W / 2 - lg.width / 2), int(y)))))
    items.append((int(56 * s), lambda y: text_block(d, [eyebrow], f_eye, W / 2, y, GOLD, 50)))
    name_lines = wrap(d, name, f_name, W - 140)
    items.append((int(92 * s) * len(name_lines) + 10, lambda y: text_block(d, name_lines, f_name, W / 2, y, WHITE, int(92 * s))))

    def price(y):
        ww, nw, gap = d.textlength(was, font=f_was), d.textlength(now, font=f_now), 40
        x0 = W / 2 - (ww + gap + nw) / 2
        yb = y + int(205 * s)  # shared baseline
        d.text((x0, yb), was, font=f_was, fill=(185, 200, 204), anchor="ls")
        sy = yb - int(36 * s)
        d.line([(x0 - 8, sy + 14), (x0 + ww + 8, sy - 14)], fill=GOLD, width=max(8, int(10 * s)))
        d.text((x0 + ww + gap, yb), now, font=f_now, fill=GOLD, anchor="ls")
    items.append((int(225 * s), price))
    items.append((int(58 * s), lambda y: text_block(d, [anchor_note], f_note, W / 2, y, (215, 228, 230), 46)))

    def badge_fn(y):
        bw = d.textlength(badge, font=f_badge) + 80
        bh = int(84 * s)
        d.rounded_rectangle((W / 2 - bw / 2, y, W / 2 + bw / 2, y + bh), bh / 2, fill=GOLD)
        d.text((W / 2, y + bh / 2 + 2), badge, font=f_badge, fill=CARD, anchor="mm")
    items.append((int(84 * s) + 34, badge_fn))
    for ln in lines:
        items.append((int(56 * s), lambda y, ln=ln: text_block(d, [ln], f_ln, W / 2, y, (225, 232, 228), 50)))
    items.append((int(70 * s) + 10, lambda y: text_block(d, [urgency], f_urg, W / 2, y + 16, WHITE, 60)))

    def btn(y):
        bw, bh = int(620 * s), int(116 * s)
        d.rounded_rectangle((W / 2 - bw / 2, y, W / 2 + bw / 2, y + bh), bh / 2, fill=WHITE)
        d.text((W / 2, y + bh / 2 + 2), button, font=f_btn, fill=CARD, anchor="mm")
    items.append((int(116 * s) + 30, btn))
    if footnote:
        items.append((int(44 * s), lambda y: text_block(d, [footnote], f_sm, W / 2, y, (200, 210, 205), 44)))

    total = sum(h for h, _ in items)
    y = (H - total) / 2
    for h, fn in items:
        fn(y)
        y += h
    return base.convert("RGB")


def simple_offer_card(bg, W, H, name, was, now, scarcity, button="SIGN UP", logo=None, proof=None):
    """Minimal CTA end card (Dylan 2026-11-09, Boulder: "too much going on").

    Five things only: logo, offer name, struck `was` + big `now`, one plain scarcity line, one button.
    `proof` (optional, real numbers only, e.g. "5.0 on Google · Ranked #1, BusinessRate 2026") adds one
    row of 5 stars + that text under the logo.
    """
    base = bg.convert("RGB").resize((W, H)).filter(ImageFilter.GaussianBlur(30))
    base = Image.blend(base, Image.new("RGB", (W, H), CARD), 0.86).convert("RGBA")
    d = ImageDraw.Draw(base)
    s = 1.0 if H > 1500 else 0.86
    f_name, f_was, f_now = font(BOLD, int(68 * s)), font(BOLD, int(90 * s)), font(BOLD, int(200 * s))
    f_sc, f_btn = font(SEMI, int(40 * s)), font(BOLD, int(54 * s))
    items = []
    if logo:
        lg = Image.open(logo).convert("RGBA")
        lg.thumbnail((int(260 * s), int(140 * s)))
        items.append((lg.height + int(56 * s), lambda y: base.alpha_composite(lg, (int(W / 2 - lg.width / 2), int(y)))))
    if proof:
        f_pr = font(SEMI, int(36 * s))

        def proof_row(y):
            r, gap = int(20 * s), int(46 * s)
            tw = d.textlength(proof, font=f_pr)
            row_w = 5 * gap - (gap - 2 * r) + int(20 * s) + tw
            sx = W / 2 - row_w / 2 + r
            cy = y + int(22 * s)
            for i in range(5):
                _star(d, sx + i * gap, cy, r, GOLD)
            d.text((sx + 4 * gap + r + int(20 * s), cy + 2), proof, font=f_pr, fill=WHITE, anchor="lm")
        items.append((int(44 * s) + int(44 * s), proof_row))
    name_lines = wrap(d, name, f_name, W - 160)
    lh = int(82 * s)
    items.append((lh * len(name_lines) + int(10 * s), lambda y: text_block(d, name_lines, f_name, W / 2, y, WHITE, lh)))

    def price(y):
        ww, nw, gap = d.textlength(was, font=f_was), d.textlength(now, font=f_now), 44
        x0 = W / 2 - (ww + gap + nw) / 2
        yb = y + int(196 * s)
        d.text((x0, yb), was, font=f_was, fill=(160, 180, 176), anchor="ls")
        d.line([(x0 - 8, yb - int(20 * s)), (x0 + ww + 8, yb - int(60 * s))], fill=GOLD, width=max(8, int(10 * s)))
        d.text((x0 + ww + gap, yb), now, font=f_now, fill=GOLD, anchor="ls")
    items.append((int(240 * s), price))
    items.append((int(76 * s), lambda y: d.text((W / 2, y), scarcity, font=f_sc, fill=(225, 232, 228), anchor="ma")))

    def btn(y):
        bw, bh = int(560 * s), int(116 * s)
        d.rounded_rectangle((W / 2 - bw / 2, y, W / 2 + bw / 2, y + bh), bh / 2, fill=GOLD)
        d.text((W / 2, y + bh / 2 + 2), button, font=f_btn, fill=CARD, anchor="mm")
    items.append((int(116 * s), btn))
    total = sum(h for h, _ in items)
    y = (H - total) / 2
    for h, fn in items:
        fn(y)
        y += h
    return base.convert("RGB")


def _star(d, cx, cy, r, fill):
    import math
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    d.polygon(pts, fill=fill)


def offer_end_card(bg, W, H, name, was, now, rating, proof_line, scarcity, button="BOOK NOW",
                   footnote="", logo=None, scarce_color=(120, 214, 232)):
    """Clean offer end card (Dylan 2026-11-06: social proof up front, less going on).

    Stack: logo, offer name, struck `was` + big `now`, social proof (5 stars + `rating`, e.g. "4.9 on Google",
    then `proof_line`, e.g. a credential), scarcity as a plain label (clock icon, no pill), one accent-filled
    button (the only filled accent element), optional small footnote. Real numbers only.
    """
    base = bg.convert("RGB").resize((W, H)).filter(ImageFilter.GaussianBlur(30))
    base = Image.blend(base, Image.new("RGB", (W, H), CARD), 0.84).convert("RGBA")
    d = ImageDraw.Draw(base)
    s = 1.0 if H > 1500 else 0.86
    f_name, f_was, f_now = font(BOLD, int(70 * s)), font(BOLD, int(92 * s)), font(BOLD, int(200 * s))
    f_rate, f_line = font(BOLD, int(46 * s)), font(SEMI, int(34 * s))
    f_sc, f_btn, f_sm = font(BOLD, int(38 * s)), font(BOLD, int(54 * s)), font(REG, int(30 * s))
    items = []
    if logo:
        lg = Image.open(logo).convert("RGBA")
        lg.thumbnail((int(280 * s), int(160 * s)))
        items.append((lg.height + int(44 * s), lambda y: base.alpha_composite(lg, (int(W / 2 - lg.width / 2), int(y)))))
    items.append((int(84 * s), lambda y: d.text((W / 2, y), name, font=f_name, fill=WHITE, anchor="ma")))

    def price(y):
        ww, nw, gap = d.textlength(was, font=f_was), d.textlength(now, font=f_now), 44
        x0 = W / 2 - (ww + gap + nw) / 2
        yb = y + int(196 * s)
        d.text((x0, yb), was, font=f_was, fill=(160, 180, 186), anchor="ls")
        d.line([(x0 - 8, yb - int(20 * s)), (x0 + ww + 8, yb - int(60 * s))], fill=GOLD, width=max(8, int(10 * s)))
        d.text((x0 + ww + gap, yb), now, font=f_now, fill=GOLD, anchor="ls")
    items.append((int(250 * s), price))

    def proof(y):  # a framed proof panel so it reads as its own block
        pw, ph = int(W * 0.78), int(150 * s)
        x0 = W / 2 - pw / 2
        panel = Image.new("RGBA", (W, H), (0, 0, 0, 0))  # translucent: composite, ImageDraw on RGBA would overwrite
        ImageDraw.Draw(panel).rounded_rectangle((x0, y, x0 + pw, y + ph), int(22 * s), fill=(255, 255, 255, 26),
                                                outline=(255, 255, 255, 70), width=2)
        base.alpha_composite(panel)
        r, gap = int(22 * s), int(52 * s)
        tw = d.textlength(rating, font=f_rate)
        row_w = 5 * gap - (gap - 2 * r) + int(22 * s) + tw
        sx = W / 2 - row_w / 2 + r
        cy = y + int(48 * s)
        for i in range(5):
            _star(d, sx + i * gap, cy, r, GOLD)
        d.text((sx + 4 * gap + r + int(22 * s), cy + 2), rating, font=f_rate, fill=WHITE, anchor="lm")
        d.text((W / 2, y + int(104 * s)), proof_line, font=f_line, fill=(215, 228, 230), anchor="mm")
    items.append((int(150 * s) + int(40 * s), proof))

    def scarce(y):
        tw = d.textlength(scarcity, font=f_sc)
        cy = y + int(24 * s)
        cx = W / 2 + int(22 * s)
        d.text((cx, cy), scarcity, font=f_sc, fill=scarce_color, anchor="mm")
        ix = cx - tw / 2 - int(30 * s)
        rr = int(16 * s)
        d.ellipse((ix - rr, cy - rr, ix + rr, cy + rr), outline=scarce_color, width=4)
        d.line([(ix, cy - rr * 0.6), (ix, cy), (ix + rr * 0.5, cy + rr * 0.3)], fill=scarce_color, width=3)
    items.append((int(48 * s) + int(34 * s), scarce))

    def btn(y):
        bw, bh = int(620 * s), int(118 * s)
        d.rounded_rectangle((W / 2 - bw / 2, y, W / 2 + bw / 2, y + bh), bh / 2, fill=GOLD)
        d.text((W / 2, y + bh / 2 + 2), button, font=f_btn, fill=CARD, anchor="mm")
    items.append((int(118 * s) + int(30 * s), btn))
    if footnote:
        items.append((int(40 * s), lambda y: d.text((W / 2, y), footnote, font=f_sm, fill=(170, 190, 195), anchor="ma")))
    total = sum(h for h, _ in items)
    y = (H - total) / 2
    for h, fn in items:
        fn(y)
        y += h
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
