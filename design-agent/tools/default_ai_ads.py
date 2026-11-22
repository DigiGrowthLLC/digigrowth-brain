"""The 3 default AI ads of a Patient Acquisition Blueprint (Dylan, 2026-11-22: the Rise & Reframe set is
the default for every prospect, catered to them):

  1. ugc-thursday     AI UGC: CrosaCore's "Back by Thursday" actor (her generic first line) + 2 new lines
                      naming the prospect's city and offer + ONE real review card + offer end card (~25-30s)
  2. static_review    AI static: Boulder C10 review-card layout: rating + one short real review on top, a
                      big AI photo of a therapist treating the body part in the quote, offer strip + Book Now
  3. ugc-square-one   AI UGC: CrosaCore's "Back to Square One" actor, same structure, a different review

Row order on the page: ugc-thursday, static_review, ugc-square-one.

Usage:
  python design-agent/tools/default_ai_ads.py <blueprint.json> [--generate]

Reads the blueprint's "ai_ads" block (see AI_ADS_EXAMPLE below) + its "logo", writes into the blueprint's
folder: ads/ugc-thursday-web.mp4, ads/ugc-square-one-web.mp4, their _poster.jpg, ads/static_review.jpg.
Work files go to <folder>/ai_ads_work/.

--generate creates whatever is missing with fal.ai (needs credit; run with doppler run --project digigrowth
--config prd --). For the standard offer ($150 -> $49, 10 spots) that's just the 2 city/doctor lines (Veo 3.1
Fast, ~$1.20 each = ~$2.40 per prospect): the offer lines come from default-ads/takes/ and the static's photo
from default-ads/photos/ when that therapist/body-part combo exists (new combos ~$0.15, then cached). Without
--generate, missing takes must already be in ai_ads_work/takes/ (th-t2.mp4, sq-t2.mp4, ...).
Takes are trimmed automatically (to the last spoken word; an immediately repeated word like
"Temecula, Temecula" is cut), checked against the script (a warning prints if the words don't match:
listen before using it), and captioned in the source ads' style. "segs" in a take's config overrides the
automatic trim: {"th-t3": [[0, 3.2]]}.
"""
import difflib
import json
import pathlib
import re
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "media-buying-agent/tools"))
import ad_overlays as ov  # noqa: E402

W, H, FPS, END_S, XF, PROOF_S = 1080, 1920, 30, 4.0, 0.35, 4.0
CROSA = REPO / "media-buying-agent/clients/crosacore/creatives"
GEN = REPO / "content-agent/tools/generate_creative.py"
POLISH = "gblur=sigma=0.8,noise=alls=8:allf=t+u,eq=saturation=0.9:contrast=0.96:gamma=1.02,colorbalance=rm=0.02:bm=-0.02,"

# The two actors. "head" = their generic, already-captioned first line (approved, ran for CrosaCore).
ACTORS = {
    "ugc-thursday": dict(
        head=REPO / "design-agent/references/default-ads/ugc-back-by-thursday-head.mp4", head_cut=7.5,
        still=CROSA / "video-back-by-thursday/actor.png", polish=False, review="thursday",
        voice="The woman, early 30s, warm, wry, mid-pitch American female voice, casual and unscripted-sounding, moderate pace,",
        setting="Quiet bright office ambience.",
        takes=[("th-t2", "Turns out there's a PT in {city} who works one-on-one the whole visit.",
                "turns out there's a PT in {city} who works one-on-one the whole visit."),
               ("th-t3", "Normally {spoken_was}, right now it's {spoken_now}. And there's only {spoken_spots} spots a month.",
                "normally {was}, right now it's {now}. and there's only {spots} spots a month.",
                ("th-offer.mp4", "Normally a hundred fifty, right now it's forty-nine.", "normally $150, right now it's $49."))]),
    "ugc-square-one": dict(
        head=CROSA / "video-back-to-square-one/video-9x16.mp4", head_cut=5.55,
        still=CROSA / "video-back-to-square-one/actor.png", polish=True, review="square_one",
        voice="The man, late 30s, relaxed, slightly exasperated but good-humored, mid-low American male voice, casual and unscripted-sounding, moderate pace,",
        setting="Quiet parked car ambience.",
        takes=[("sq-t2", "So there's a PT in {city}, {doctor_spoken}, one-on-one start to finish.",
                "so there's a PT in {city}, {doctor_short}, one-on-one, start to finish."),
               ("sq-t3", "First visit's {spoken_now} bucks right now. Only {spoken_spots} spots a month.",
                "first visit's {now_num} bucks right now. only {spots} spots a month.",
                ("sq-offer.mp4", "First visit's forty-nine bucks right now. Only ten spots a month.",
                 "first visit's 49 bucks right now. only 10 spots a month."))]),
}
# Cost savers (Dylan, 2026-11-22: "anyway to make it a bit less?"): the offer lines name no practice, so for the
# standard offer ($150 -> $49, 10 spots) every prospect reuses the cached takes in default-ads/takes/ (4th
# element above) and only the city/doctor line is filmed per prospect. The static's AI photo has no faces or
# branding, so photos are kept in default-ads/photos/<therapist>-<body part>.jpg and reused.
DEFAULTS = REPO / "design-agent/references/default-ads"

AI_ADS_EXAMPLE = {
    "city": "Temecula", "areas": "Temecula & Murrieta",
    "doctor_short": "Dr. BettyLou", "doctor_spoken": "Dr. BettyLou",
    "doctor_line": "Dr. BettyLou DeYoung, DPT · one-on-one",
    "offer": {"name": "New Patient Assessment", "was": "$150", "now": "$49", "spots": 10,
              "spoken_was": "a hundred fifty", "spoken_now": "forty-nine", "spoken_spots": "ten"},
    "rating": "5.0 on Google", "end_footer": "Temecula & Murrieta · no referral needed",
    "palette": {"card": [46, 28, 15], "accent": [198, 156, 85], "panel": [59, 36, 19], "warm": [240, 214, 168]},
    "reviews": {"thursday": {"quote": "...", "attr": "RICK · REAL GOOGLE REVIEW"},
                "square_one": {"quote": "...", "attr": "KEVIN · REAL GOOGLE REVIEW"},
                "static": {"quote": "2 years of shoulder pain. ... drastically reduced."}},
    "photo": {"therapist": "female", "body_part": "shoulder"},
    "segs": {},
}


def run(cmd):
    subprocess.run([str(c) for c in cmd], check=True)


def dur_of(p) -> float:
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                                capture_output=True, text=True).stdout.strip())


def ffp(p) -> str:
    return str(p).replace("\\", "/").replace(":", r"\:")


def norm(t: str) -> str:
    return re.sub(r"[^a-z0-9]", "", t.lower())


class Builder:
    def __init__(self, bp_path: pathlib.Path, generate: bool):
        self.base = bp_path.parent
        d = json.load(open(bp_path, encoding="utf-8"))
        if "ai_ads" not in d:
            sys.exit("blueprint.json has no \"ai_ads\" block. See AI_ADS_EXAMPLE in this file.")
        self.c, self.d, self.generate = d["ai_ads"], d, generate
        self.work = self.base / "ai_ads_work"
        self.takes = self.work / "takes"
        self.out = self.base / "ads"
        for p in (self.work, self.takes, self.out):
            p.mkdir(parents=True, exist_ok=True)
        pal = self.c.get("palette") or {}
        self.CARD = tuple(pal.get("card") or (46, 28, 15))
        self.ACC = tuple(pal.get("accent") or (198, 156, 85))
        self.PANEL = tuple(pal.get("panel") or self.CARD)
        self.WARM = tuple(pal.get("warm") or (240, 214, 168))
        ov.set_palette(card=self.CARD, accent=self.ACC, panel=self.PANEL)
        o = self.c["offer"]
        self.vars = {"city": self.c["city"], "doctor_short": self.c["doctor_short"],
                     "doctor_spoken": self.c.get("doctor_spoken") or self.c["doctor_short"],
                     "was": o["was"], "now": o["now"], "now_num": o["now"].lstrip("$"), "spots": str(o["spots"]),
                     "spoken_was": o["spoken_was"], "spoken_now": o["spoken_now"], "spoken_spots": o["spoken_spots"]}
        self._whisper = None

    # ------------------------------------------------------------ helpers
    def whisper(self):
        if self._whisper is None:
            from faster_whisper import WhisperModel
            self._whisper = WhisperModel("medium", device="cpu", compute_type="int8")
        return self._whisper

    def words(self, path, prompt=""):
        segs, _ = self.whisper().transcribe(str(path), word_timestamps=True, initial_prompt=prompt or None)
        out = []
        for s in segs:
            for w in s.words:
                t = w.word.strip()
                if t.startswith("-") and out:           # "one -on -one" -> one token
                    out[-1] = (out[-1][0], w.end, out[-1][2] + t)
                else:
                    out.append((w.start, w.end, t))
        return out

    def gen(self, args):
        if not self.generate:
            sys.exit(f"Missing {args[-1]}. Re-run with --generate (fal.ai credit needed) or add the file.")
        run(["python", GEN, *args])

    def white_logo(self):
        out = self.work / "logo_white.png"
        lg = self.d.get("logo")
        if not lg or str(lg).startswith("data:"):
            return None
        im = Image.open(self.base / lg).convert("RGBA")
        Image.merge("RGBA", (*[Image.new("L", im.size, 255)] * 3, im.getchannel("A"))).save(out)
        return out

    def still(self, img, dur, out):
        run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-t", dur, "-i", img, "-f", "lavfi", "-t", dur,
             "-i", "anullsrc=r=48000:cl=stereo", "-vf", f"scale={W}:{H},setsar=1,format=yuv420p", "-r", FPS,
             "-c:v", "libx264", "-crf", "18", "-c:a", "aac", "-b:a", "160k", "-shortest", out])

    # ------------------------------------------------------------ takes
    def ensure_take(self, actor, name, spoken):
        path = self.takes / f"{name}.mp4"
        if not path.exists():
            prompt = (f"Handheld front-camera selfie video, vertical 9:16, candid UGC. {actor['voice']} talks straight into "
                      f"the camera and says exactly: \"{spoken}\" {actor['setting']} No music, no subtitles, no on-screen text.")
            self.gen(["video", prompt, "--model", "veo31-fast", "--image", actor["still"], "--duration", "8", "--out", path])
        return path

    def auto_segs(self, words, take_dur):
        """Keep up to the last spoken word; cut an immediately repeated word ("Temecula, Temecula")."""
        cuts = [(words[i][0], words[i + 1][0]) for i in range(len(words) - 1) if norm(words[i][2]) and norm(words[i][2]) == norm(words[i + 1][2])]
        end = min(take_dur, words[-1][1] + 0.15)
        segs, t = [], 0.0
        for a, b in cuts:
            segs.append((t, a))
            t = b
        segs.append((t, end))
        return [(round(a, 2), round(b, 2)) for a, b in segs if b - a > 0.05]

    def caption_words(self, words, caption_line):
        """Whisper timings, script spelling: align the take's words to the caption line."""
        cap = caption_line.split()
        a, b = [norm(w[2]) for w in words], [norm(t) for t in cap]
        out = [list(w) for w in words]
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
            if tag == "equal" or (tag == "replace" and i2 - i1 == j2 - j1):
                for k in range(i2 - i1):
                    out[i1 + k][2] = cap[j1 + k]
        return [tuple(w) for w in out]

    def build_take(self, actor, name, spoken, caption):
        raw_in = self.ensure_take(actor, name, spoken)
        words = self.words(raw_in, f"{self.vars['city']}. {self.vars['doctor_short']}. one-on-one.")
        heard = " ".join(w[2] for w in words)
        sim = difflib.SequenceMatcher(None, norm(heard), norm(spoken.replace(self.vars["spoken_now"], self.vars["now_num"])
                                                               .replace(self.vars["spoken_was"], self.vars["was"].lstrip("$"))
                                                               .replace(self.vars["spoken_spots"], self.vars["spots"]))).ratio()
        print(f"  {name}: heard \"{heard}\" (match {sim:.0%})", flush=True)
        if sim < 0.9:
            print(f"  WARNING {name}: the take doesn't match the script. Listen to {raw_in} before using it.", flush=True)
        segs = (self.c.get("segs") or {}).get(name) or self.auto_segs(words, dur_of(raw_in))
        out = self.work / f"{name}-trim.mp4"
        fc = "".join(f"[0:v]trim={a}:{b},setpts=PTS-STARTPTS[v{i}];[0:a]atrim={a}:{b},asetpts=PTS-STARTPTS,"
                     f"afade=t=in:d=0.04,afade=t=out:st={max(0, b - a - 0.06):.2f}:d=0.06[a{i}];" for i, (a, b) in enumerate(segs))
        fc += "".join(f"[v{i}][a{i}]" for i in range(len(segs))) + f"concat=n={len(segs)}:v=1:a=1[cv][ca];" \
              f"[cv]{POLISH if actor['polish'] else ''}scale={W}:{H},setsar=1,fps={FPS}[vo]"
        run(["ffmpeg", "-v", "error", "-y", "-i", raw_in, "-filter_complex", fc, "-map", "[vo]", "-map", "[ca]",
             "-ar", "48000", "-ac", "2", "-c:v", "libx264", "-crf", "16", "-c:a", "aac", "-b:a", "160k", out])
        tw = self.caption_words(self.words(out, f"{self.vars['city']}. {self.vars['doctor_short']}."), caption)
        ass = self.work / f"{name}.ass"
        ov.write_ass(ass, W, H, ov.chunk_words(tw, 3), 50, 690)
        cap = self.work / f"{name}-cap.mp4"
        run(["ffmpeg", "-v", "error", "-y", "-i", out, "-vf", f"subtitles='{ffp(ass)}',format=yuv420p",
             "-c:v", "libx264", "-crf", "17", "-c:a", "copy", cap])
        return cap

    # ------------------------------------------------------------ ugc
    def ugc(self, name):
        actor = ACTORS[name]
        print(name, flush=True)
        head0 = self.work / f"{name}-head0.mp4"
        c = actor["head_cut"]
        run(["ffmpeg", "-v", "error", "-y", "-t", c, "-i", actor["head"], "-vf", f"scale={W}:{H},setsar=1,fps={FPS}",
             "-af", f"afade=t=out:st={c - 0.15:.2f}:d=0.15,aresample=48000", "-ac", "2",
             "-c:v", "libx264", "-crf", "18", "-c:a", "aac", "-b:a", "160k", head0])
        o = self.c["offer"]
        standard = (o["was"], o["now"], int(o["spots"])) == ("$150", "$49", 10)
        parts = [head0]
        for n, sp, cp, *cache in actor["takes"]:
            sp, cp = sp.format(**self.vars), cp.format(**self.vars)
            if cache and standard and (DEFAULTS / "takes" / cache[0][0]).exists():
                cached = self.takes / f"{n}.mp4"
                if not cached.exists():
                    cached.write_bytes((DEFAULTS / "takes" / cache[0][0]).read_bytes())
                _, sp, cp = cache[0]
                print(f"  {n}: reusing the cached offer line ({cache[0][0]}, $0)", flush=True)
            parts.append(self.build_take(actor, n, sp, cp))
        frame = self.work / f"{name}-frame.jpg"
        run(["ffmpeg", "-v", "error", "-y", "-ss", "2.0", "-i", actor["head"], "-frames:v", "1", "-vf", f"scale={W}:{H}", frame])
        bg = Image.open(frame).convert("RGB").filter(ImageFilter.GaussianBlur(26))
        bg = Image.blend(bg, Image.new("RGB", (W, H), self.CARD), 0.6).convert("RGBA")
        rv = self.c["reviews"][actor["review"]]
        proof = bg.copy()
        proof.alpha_composite(ov.proof_card(W, H, rv["quote"], rv["attr"], H // 2 + 40))
        proof.convert("RGB").save(self.work / f"{name}-proof.png")
        pv = self.work / f"{name}-proof.mp4"
        self.still(self.work / f"{name}-proof.png", PROOF_S, pv)
        parts.append(pv)
        body = self.work / f"{name}-body.mp4"
        fc = "".join(f"[{i}:v][{i}:a]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=1:a=1[v][a]"
        run(["ffmpeg", "-v", "error", "-y", *sum((["-i", p] for p in parts), []), "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
             "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", body])
        o = self.c["offer"]
        ec = self.work / f"{name}-end.png"
        ov.offer_end_card(Image.open(frame), W, H, o["name"], o["was"], o["now"], self.c.get("rating") or "5.0 on Google",
                          self.c["doctor_line"], f"ONLY {o['spots']} SPOTS THIS MONTH", "BOOK NOW",
                          self.c.get("end_footer") or self.c["areas"], logo=self.white_logo(), scarce_color=self.WARM).save(ec)
        endv = self.work / f"{name}-end.mp4"
        self.still(ec, END_S, endv)
        d = dur_of(body)
        full = self.work / f"{name}-9x16.mp4"
        run(["ffmpeg", "-v", "error", "-y", "-i", body, "-i", endv, "-filter_complex",
             f"[0:v]fps={FPS},format=yuv420p,setsar=1[b];[1:v]fps={FPS},format=yuv420p,setsar=1[e];"
             f"[b][e]xfade=transition=fade:duration={XF}:offset={d - XF:.3f}[v];"
             f"[0:a]afade=t=out:st={d - 0.25:.3f}:d=0.25[a0];[a0][1:a]acrossfade=d={XF}:c1=nofade:c2=nofade[a]",
             "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "19", "-preset", "slow", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", full])
        web = self.out / f"{name}-web.mp4"
        run(["ffmpeg", "-v", "error", "-y", "-i", full, "-vf", "scale=720:1280", "-c:v", "libx264", "-crf", "26", "-preset", "slow",
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", web])
        run(["ffmpeg", "-v", "error", "-y", "-ss", "1.2", "-i", head0, "-frames:v", "1", "-vf", "scale=720:1280", self.out / f"{name}_poster.jpg"])
        print(f"  -> {web.name} ({dur_of(web):.1f}s)", flush=True)

    # ------------------------------------------------------------ static
    def static(self):
        print("static_review", flush=True)
        ph_path = self.takes / "photo.png"
        p = self.c.get("photo") or {}
        who = "female" if (p.get("therapist") or "female").lower().startswith("f") else "male"
        part = p.get("body_part") or "shoulder"
        lib = DEFAULTS / "photos" / f"{who}-{norm(part)}.jpg"
        if not ph_path.exists() and lib.exists():
            Image.open(lib).save(ph_path)
            print(f"  reusing the library photo {lib.name} ($0)", flush=True)
        if not ph_path.exists():
            prompt = (f"Close-up of a {who} physical therapist's bare hands (no gloves, short natural nails) doing hands-on work on a "
                      f"patient's {part}, while the patient sits or lies on a padded treatment table in plain athletic clothes. "
                      "Therapist in a plain dusty-navy scrub top, only torso and arms visible. Warm late-afternoon window light, "
                      "small private clinic room with a light wood wall. Crop shows hands, forearms and the treated area only, both "
                      "faces fully out of frame. Realistic candid photo, natural light, real skin texture, ordinary people, slightly "
                      "imperfect framing, no color grading, NOT a stock photo, NOT glossy. No text, no logos, no brand names, no watermark.")
            self.gen(["image", prompt, "--model", "nano-banana-pro", "--aspect", "16:9", "--out", ph_path])
            im0 = Image.open(ph_path).convert("RGB")
            im0.resize((1600, round(im0.height * 1600 / im0.width))).save(lib, quality=88)
            print(f"  saved {lib.name} to the photo library: look at it, delete it there if it's not usable", flush=True)
        SW, SH = 1080, 1350
        CREAM, INK = (247, 242, 233), (40, 28, 18)
        im = Image.new("RGB", (SW, SH), self.CARD)
        d = ImageDraw.Draw(im)
        TOP = 300
        d.rectangle((0, 0, SW, TOP), fill=CREAM)
        for i in range(5):
            ov._star(d, 74 + i * 44, 58, 19, self.ACC)
        d.text((74 + 5 * 44 + 6, 59), f"{self.c.get('rating') or '5.0 on Google'}  ·  {self.c['areas']}",
               font=ov.font(ov.SEMI, 32), fill=(110, 95, 80), anchor="lm")
        fq, y = ov.font(ov.BOLD, 44), 100
        for ln in ov.wrap(d, "“" + self.c["reviews"]["static"]["quote"].strip("“”\"") + "”", fq, SW - 120)[:3]:
            d.text((60, y), ln, font=fq, fill=INK)
            y += 56
        PH = 670
        ph = Image.open(ph_path).convert("RGB")
        sc = max(SW / ph.width, PH / ph.height)
        ph = ph.resize((round(ph.width * sc), round(ph.height * sc)))
        ox, oy = (ph.width - SW) // 2, (ph.height - PH) // 2
        im.paste(ph.crop((ox, oy, ox + SW, oy + PH)), (0, TOP))
        pill = self.c["doctor_line"].replace(" · one-on-one", "")
        pill = pill if pill.lower().startswith("one-on-one") else f"One-on-one with {pill}"
        fp = ov.font(ov.SEMI, 32)
        pw = d.textlength(pill, font=fp) + 48
        py = TOP + PH - 74
        d.rounded_rectangle((40, py, 40 + pw, py + 54), 27, fill=tuple(max(0, v - 16) for v in self.CARD))
        d.text((64, py + 28), pill, font=fp, fill=(255, 255, 255), anchor="lm")
        y0 = TOP + PH
        o = self.c["offer"]
        d.rectangle((0, y0, SW, SH), fill=self.CARD)
        d.text((54, y0 + 30), o["name"], font=ov.font(ov.BOLD, 54), fill=(255, 255, 255))
        fw, fn2 = ov.font(ov.BOLD, 56), ov.font(ov.BOLD, 92)
        x, yb = 56, y0 + 186
        d.text((x, yb), o["was"], font=fw, fill=(190, 170, 150), anchor="ls")
        ww = d.textlength(o["was"], font=fw)
        d.line([(x - 6, yb - 12), (x + ww + 6, yb - 38)], fill=self.ACC, width=7)
        d.text((x + ww + 24, yb), o["now"], font=fn2, fill=self.ACC, anchor="ls")
        nx = x + ww + 24 + d.textlength(o["now"], font=fn2) + 30
        d.text((nx, yb - 8), f"Only {o['spots']} new-patient spots this month", font=ov.font(ov.SEMI, 34), fill=self.WARM, anchor="ls")
        bw, bh = SW - 108, 104
        by = SH - bh - 30
        d.rounded_rectangle((54, by, 54 + bw, by + bh), bh / 2, fill=self.ACC)
        d.text((SW / 2, by + bh / 2 + 2), "BOOK NOW  ·  CLAIM YOUR SPOT", font=ov.font(ov.BOLD, 50), fill=self.CARD, anchor="mm")
        im.save(self.out / "static_review.jpg", quality=92)
        print("  -> static_review.jpg", flush=True)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    b = Builder(pathlib.Path(args[0]).resolve(), "--generate" in sys.argv)
    only = set(args[1:])
    if not only or "static" in only:
        b.static()
    for n in ACTORS:
        if not only or n in only:
            b.ugc(n)
