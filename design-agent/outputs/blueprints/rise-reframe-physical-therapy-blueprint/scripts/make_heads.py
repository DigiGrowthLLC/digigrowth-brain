"""Round 5: extend the two AI UGC actors with Rise & Reframe lines (Veo takes in takes/), captioned like the originals.
Output: work/<name>/longhead.mp4 = original generic first line + new takes."""
import pathlib, subprocess, sys
from faster_whisper import WhisperModel
B = pathlib.Path(__file__).resolve().parent
REPO = pathlib.Path(r"C:/Users/dylan/Videos/Business/AI Agents/DigiGrowth-Brain")
sys.path.insert(0, str(REPO / "media-buying-agent/tools"))
import ad_overlays as ov
W, H, FPS = 1080, 1920, 30
T = B / "takes"
POLISH = "gblur=sigma=0.8,noise=alls=8:allf=t+u,eq=saturation=0.9:contrast=0.96:gamma=1.02,colorbalance=rm=0.02:bm=-0.02,"
HEADS = {
    "ugc-thursday": dict(src=REPO / "design-agent/references/default-ads/ugc-back-by-thursday-head.mp4", cut=7.5, polish=False,
                         takes=[("th-t2", [(0, 3.14), (3.80, 7.62)]), ("th-t3", [(0, 3.2)])]),
    "ugc-square-one": dict(src=REPO / "media-buying-agent/clients/crosacore/creatives/video-back-to-square-one/video-9x16.mp4", cut=5.55, polish=True,
                           takes=[("sq-t2", [(0, 7.25)]), ("sq-t3", [(0, 6.3)])]),
}
m = WhisperModel("medium", device="cpu", compute_type="int8")
def run(c): subprocess.run([str(x) for x in c], check=True)
def ffp(p): return str(p).replace("\\", "/").replace(":", r"\:")
for name, h in HEADS.items():
    wd = B / "work" / name; wd.mkdir(parents=True, exist_ok=True)
    parts = []
    p0 = wd / "p0.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-t", h["cut"], "-i", h["src"], "-vf", f"scale={W}:{H},setsar=1,fps={FPS}",
         "-af", f"afade=t=out:st={h['cut']-0.15:.2f}:d=0.15,aresample=48000", "-ac", "2", "-c:v", "libx264", "-crf", "18", "-c:a", "aac", "-b:a", "160k", p0])
    parts.append(p0)
    for tk, segs in h["takes"]:
        raw = wd / f"{tk}-raw.mp4"
        vf = "".join(f"[0:v]trim={a}:{b},setpts=PTS-STARTPTS[v{i}];[0:a]atrim={a}:{b},asetpts=PTS-STARTPTS,afade=t=in:d=0.04,afade=t=out:st={b-a-0.06:.2f}:d=0.06[a{i}];" for i, (a, b) in enumerate(segs))
        vf += "".join(f"[v{i}][a{i}]" for i in range(len(segs))) + f"concat=n={len(segs)}:v=1:a=1[cv][ca];[cv]{POLISH if h['polish'] else ''}scale={W}:{H},setsar=1,fps={FPS}[vo]"
        run(["ffmpeg", "-v", "error", "-y", "-i", T / f"{tk}.mp4", "-filter_complex", vf, "-map", "[vo]", "-map", "[ca]",
             "-ar", "48000", "-ac", "2", "-c:v", "libx264", "-crf", "16", "-c:a", "aac", "-b:a", "160k", raw])
        segs_, _ = m.transcribe(str(raw), word_timestamps=True, initial_prompt="Temecula. Dr. BettyLou. one-on-one.")
        words = []
        for s in segs_:
            for w in s.words:
                t = w.word.strip().lower()
                if t.startswith("-") and words:
                    words[-1] = (words[-1][0], w.end, words[-1][2] + t)
                elif t == "lou." and words and words[-1][2] == "betty":
                    words[-1] = (words[-1][0], w.end, "BettyLou,")
                else:
                    words.append((w.start, w.end, t))
        FIX = {"pt": "PT", "temecula": "Temecula", "temecula.": "Temecula,", "dr.": "Dr.", "visits": "visit's", "one-on-one.": "one-on-one,", "150.": "$150,", "150,": "$150,", "49": "$49", "49.": "$49."}
        words = [(a, b, "49" if t == "49" and i + 1 < len(words) and words[i + 1][2] == "bucks" else FIX.get(t, t)) for i, (a, b, t) in enumerate(words)]
        print(tk, " ".join(w[2] for w in words), flush=True)
        ass = wd / f"{tk}.ass"
        chunks = ov.chunk_words(words, 3)
        print(chunks, flush=True)
        ov.write_ass(ass, W, H, chunks, 50, 690)
        cap = wd / f"{tk}.mp4"
        run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-vf", f"subtitles='{ffp(ass)}',format=yuv420p", "-c:v", "libx264", "-crf", "17", "-c:a", "copy", cap])
        parts.append(cap)
    inputs = sum((["-i", x] for x in parts), [])
    fc = "".join(f"[{i}:v][{i}:a]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=1:a=1[v][a]"
    out = wd / "longhead.mp4"
    run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", out])
    d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout.strip()
    print(name, "longhead", d, flush=True)
