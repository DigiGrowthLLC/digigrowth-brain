"""Client ad-batch presentation (Claude Artifact): 720p previews + index.html. The default layout for every client.

Usage (from anywhere):
    python media-buying-agent/tools/ad_presentation/build_presentation.py <creatives_dir> <out_dir>
then publish <out_dir>/index.html + <out_dir>/media/* with the artifacts publish_files tool.

Reads from <creatives_dir>/_build/:
  presentation.json           {"ads": [...], "stages": [...]}  (see README.md for the fields)
  presentation_template.html  the client's copy of template.html, with its text rewritten
                              (falls back to the shared template.html, which still holds Pinnacle's text)
Each ad's folder <creatives_dir>/<slug>/ needs copy.md (3 "**V1** · Modeled on X: ..." texts + a
"**Headlines:** a · b · c · d · e" line) and either <slug>-9x16.mp4 + <slug>-4x5.mp4 or <slug>.png.
"""
import html, json, re, subprocess, sys, pathlib

HERE = pathlib.Path(__file__).resolve().parent
C = pathlib.Path(sys.argv[1]).resolve()
OUT = pathlib.Path(sys.argv[2]); MED = OUT / "media"; MED.mkdir(parents=True, exist_ok=True)
cfg = json.loads((C / "_build" / "presentation.json").read_text(encoding="utf-8"))
ADS, STAGES = cfg["ads"], cfg["stages"]
tpl_path = C / "_build" / "presentation_template.html"
if not tpl_path.exists():
    tpl_path = HERE / "template.html"
    print("note: no client template, using the shared one (its text is Pinnacle's: rewrite before sending)")
e = html.escape


def run(cmd):
    subprocess.run(cmd, check=True)


def dur(f):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)]).decode())


def parse(copy):
    t = copy.read_text(encoding="utf-8")
    vs = re.findall(r"\*\*V(\d)\*\* · Modeled on [^:]+: (.+?)\n((?:>.*(?:\n|$))+)", t)
    out = []
    for n, struct, body in vs:
        lines = [re.sub(r"^> ?", "", ln) for ln in body.strip().split("\n")]
        out.append((struct.strip().capitalize(), "\n".join(lines).strip()))
    heads = re.search(r"\*\*Headlines:\*\* (.+)", t).group(1).split(" · ")
    return out, heads


cards = []
for a in ADS:
    d = C / a["slug"]
    texts, heads = parse(d / "copy.md")
    assert len(texts) == 3 and len(heads) == 5, a["slug"]
    if a.get("static"):
        png = d / f"{a['slug']}.png"
        run(["ffmpeg", "-v", "error", "-y", "-i", str(png), "-q:v", "3", str(MED / f"{a['k']}.jpg")])
        media = f'<div class="still"><img src="media/{a["k"]}.jpg" alt="{e(a["title"])}"></div>'
        tag = f"{a['stage']} · Image"
    else:
        for fmt, (w, h) in {"9x16": (720, 1280), "4x5": (720, 900)}.items():
            run(["ffmpeg", "-v", "error", "-y", "-i", str(d / f"{a['slug']}-{fmt}.mp4"), "-vf", f"scale={w}:{h}",
                 "-c:v", "libx264", "-crf", "27", "-preset", "slow", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k",
                 "-movflags", "+faststart", str(MED / f"{a['k']}-{fmt}.mp4")])
        run(["ffmpeg", "-v", "error", "-y", "-ss", "0.6", "-i", str(MED / f"{a['k']}-9x16.mp4"), "-frames:v", "1", "-q:v", "4",
             str(MED / f"{a['k']}-poster.jpg")])
        media = (f'<div class="player" data-k="{a["k"]}"><video src="media/{a["k"]}-9x16.mp4" poster="media/{a["k"]}-poster.jpg" '
                 f'controls playsinline preload="none"></video><div class="sizes" role="group" aria-label="Video size">'
                 f'<button class="on" data-size="9x16">Reels 9:16</button><button data-size="4x5">Feed 4:5</button></div></div>')
        tag = f"{a['stage']} · {round(dur(d / (a['slug'] + '-9x16.mp4')))}s"
    tabs = "".join(f'<button role="tab" class="{"on" if i == 0 else ""}" data-i="{i}">Version {i + 1}</button>' for i in range(3))
    panes = "".join(f'<div class="pane" data-i="{i}" {"" if i == 0 else "hidden"}><p class="model">{e(s)}</p><pre class="text">{e(b)}</pre></div>'
                    for i, (s, b) in enumerate(texts))
    li = lambda xs: "".join(f"<li>{e(x)}</li>" for x in xs)
    cards.append(f'''<article class="ad" id="{a["k"]}">
  <div class="media">{media}</div>
  <div class="info">
    <div class="tag">{e(tag)}</div>
    <h3 class="ad-title">{e(a["title"])}</h3>
    <p class="who"><b>Who it's for:</b> {e(a["who"])}</p>
    <div class="two"><div><h4>Why it works</h4><ul>{li(a["why"])}</ul></div><div><h4>What we did with your content</h4><ul>{li(a["changed"])}</ul></div></div>
    <h4>Ad text (Meta rotates all three)</h4>
    <div class="tabs" role="tablist">{tabs}</div>{panes}
    <details><summary>Headlines (5)</summary><ul class="heads">{li(heads)}</ul></details>
  </div>
</article>''')

ladder = ""
for st in STAGES:
    chips = "".join(f'<a class="ad-chip" href="#{a["k"]}">{a["k"].upper()}</a>' for a in ADS if a["stage"] == st["name"])
    if not chips:
        chips = f'<span class="none">{e(st.get("empty", "Not in this first batch."))}</span>'
    ladder += (f'<div class="step" style="--h:{st["h"]}px"><div class="riser"></div><div class="step-body"><div class="step-name">{st["name"]}</div>'
               f'<p>{st["job"]}</p><div class="chips">{chips}</div></div></div>')

tpl = tpl_path.read_text(encoding="utf-8")
page = tpl.replace("{{LADDER}}", ladder).replace("{{ADS}}", "\n".join(cards))
(OUT / "index.html").write_text(page, encoding="utf-8")
tot = sum(f.stat().st_size for f in MED.iterdir())
big = max(MED.iterdir(), key=lambda f: f.stat().st_size)
print(f"ok: {len(list(MED.iterdir()))} media files, {tot / 1e6:.1f} MB total, largest {big.name} {big.stat().st_size / 1e6:.1f} MB")
