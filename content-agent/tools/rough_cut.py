"""Rough-cut a talking-head clip: remove dead space and flubbed retakes.

Two-pass, approval-gated:

    # 1. Plan: detect cuts, write cut-plan.json next to the output, print a table
    python tools/rough_cut.py <video> <transcript.json> --out <dir>

    # 2. Review/edit cut-plan.json (delete any "remove" entry you want to keep), then apply
    python tools/rough_cut.py <video> <transcript.json> --out <dir> --apply

--apply reads the existing cut-plan.json (so hand edits are honored), renders
<dir>/cut.mp4 with short audio fades at every join, and writes <dir>/transcript.cut.json -
the word list remapped onto the cut timeline, so nothing needs re-transcribing.

Detection:
  - dead space: ffmpeg silencedetect intervals >= --min-silence that contain no word midpoint,
    shrunk by --pad on both sides so speech never gets clipped
  - stumbles: any 3 words repeated within --retake-window seconds (e.g. "how fully schedule
    good, how fully schedule's good") -> the earlier (flubbed) attempt is removed
  - repeated passages: 5+ word runs that recur more than --retake-window apart (whole
    re-read takes) are REPORTED in "repeated_passages", never auto-cut - picking the best take
    is a judgment call: read the transcript, choose, and add a "remove" entry by hand
  - filler words (um, uh, ...) are only flagged in the report, never cut

transcript.json is the flat [{"text","start","end"}] list from transcribe.py --words.
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys

FILLERS = {"um", "uh", "erm", "uhm", "hmm", "ah"}


def probe_duration(video):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
        capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def detect_silences(video, min_silence, noise_db):
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(video), "-vn",
         "-af", f"silencedetect=noise={noise_db}dB:d={min_silence}", "-f", "null", "-"],
        capture_output=True, text=True)
    starts = [float(m) for m in re.findall(r"silence_start: ([\d.]+)", proc.stderr)]
    ends = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", proc.stderr)]
    return list(zip(starts, ends))


def norm(word):
    w = re.sub(r"[^a-z0-9']", "", word.lower())
    return w[:-2] if w.endswith("'s") else w


def detect_stumbles(words, window, n=3):
    """Earlier attempt of any n-gram that is re-said within `window` seconds."""
    toks = [norm(w["text"]) for w in words]
    cuts, i = [], 0
    while i <= len(toks) - n:
        key = toks[i:i + n]
        hit = None
        if all(key):
            for j in range(i + n, len(toks) - n + 1):
                if words[j]["start"] - words[i]["start"] > window:
                    break
                if toks[j:j + n] == key:
                    hit = j
        if hit is not None:
            said = " ".join(w["text"] for w in words[i:hit])
            cuts.append({"start": words[i]["start"], "end": words[hit]["start"],
                         "reason": f"stumble: \"{said[:60]}\""})
            i = hit
        else:
            i += 1
    return cuts


def detect_repeated_passages(words, window, n=5, horizon=240):
    """Runs of n+ words that recur more than `window` s later - likely whole re-read takes."""
    toks = [norm(w["text"]) for w in words]
    seen, found = {}, []
    for i in range(len(toks) - n + 1):
        key = tuple(toks[i:i + n])
        if not all(key):
            continue
        for j in seen.get(key, []):
            gap = words[i]["start"] - words[j]["start"]
            if window < gap <= horizon and not any(
                    abs(f["first_at"] - words[j]["start"]) < 3 and abs(f["again_at"] - words[i]["start"]) < 3
                    for f in found):
                found.append({"first_at": words[j]["start"], "again_at": words[i]["start"],
                              "text": " ".join(w["text"] for w in words[i:i + 8])})
        seen.setdefault(key, []).append(i)
    # Cluster n-gram hits into take ranges: hits at a similar offset (the same re-read), each
    # within 20s of the previous one, become one "first ... / again ..." pair.
    clusters = []
    for f in sorted(found, key=lambda f: f["first_at"]):
        offset = f["again_at"] - f["first_at"]
        for c in clusters:
            if abs(offset - c["offset"]) < 6 and 0 <= f["first_at"] - c["first"][1] < 20:
                c["first"][1], c["again"][1] = f["first_at"], f["again_at"]
                break
        else:
            clusters.append({"offset": offset, "first": [f["first_at"], f["first_at"]],
                             "again": [f["again_at"], f["again_at"]], "text": f["text"]})
    return [{"first_at": c["first"][0], "first_until": c["first"][1],
             "again_at": c["again"][0], "again_until": c["again"][1], "text": c["text"]}
            for c in clusters]


def merge(ranges):
    out = []
    for r in sorted(ranges, key=lambda r: r["start"]):
        if out and r["start"] <= out[-1]["end"]:
            out[-1]["end"] = max(out[-1]["end"], r["end"])
            out[-1]["reason"] += " + " + r["reason"]
        else:
            out.append(dict(r))
    return out


def build_plan(video, words, a):
    duration = probe_duration(video)
    mids = [(w["start"] + w["end"]) / 2 for w in words]
    removes = []
    for s, e in detect_silences(video, a.min_silence, a.noise_db):
        if any(s < m < e for m in mids):
            continue
        s2, e2 = (0.0 if s <= 0.05 else s + a.pad), (duration if e >= duration - 0.05 else e - a.pad)
        if e2 - s2 >= 0.2:
            removes.append({"start": round(s2, 3), "end": round(e2, 3),
                            "reason": f"dead space {e - s:.1f}s"})
    removes += detect_stumbles(words, a.retake_window)
    removes = merge(removes)

    keeps, t = [], 0.0
    for r in removes:
        if r["start"] - t >= 0.1:
            keeps.append({"start": round(t, 3), "end": round(r["start"], 3)})
        t = max(t, r["end"])
    if duration - t >= 0.1:
        keeps.append({"start": round(t, 3), "end": round(duration, 3)})

    fillers = [{"t": w["start"], "word": w["text"]} for w in words if norm(w["text"]) in FILLERS]
    return {"source": str(video), "duration": duration, "remove": removes,
            "keep": keeps, "fillers_flagged": fillers,
            "repeated_passages": detect_repeated_passages(words, a.retake_window)}


def fmt(t):
    t = round(t, 2)
    return f"{int(t // 60)}:{t % 60:05.2f}"


def print_plan(plan):
    kept = sum(k["end"] - k["start"] for k in plan["keep"])
    print(f"{'#':>3}  {'from':>8}  {'to':>8}  {'len':>5}  reason")
    for i, r in enumerate(plan["remove"], 1):
        print(f"{i:>3}  {fmt(r['start']):>8}  {fmt(r['end']):>8}  {r['end'] - r['start']:5.1f}  {r['reason']}")
    print(f"\n{len(plan['remove'])} cuts | {fmt(plan['duration'])} -> {fmt(kept)} "
          f"({plan['duration'] - kept:.1f}s removed)")
    if plan.get("repeated_passages"):
        print("\nRepeated passages - likely multiple takes. NOT cut: pick the best take and add")
        print("a remove entry for the others in cut-plan.json:")
        for r in plan["repeated_passages"]:
            print(f"  {fmt(r['first_at'])}-{fmt(r['first_until'])} re-said at "
                  f"{fmt(r['again_at'])}-{fmt(r['again_until'])}: \"{r['text']}...\"")
    if plan["fillers_flagged"]:
        print("Fillers flagged (not cut): " +
              ", ".join(f"{f['word']}@{fmt(f['t'])}" for f in plan["fillers_flagged"][:20]))


def apply_plan(video, words, plan, out_dir, fade=0.04):
    keeps = plan["keep"]
    parts, labels = [], []
    for i, k in enumerate(keeps):
        d = k["end"] - k["start"]
        f = min(fade, d / 4)
        parts.append(f"[0:v]trim={k['start']}:{k['end']},setpts=PTS-STARTPTS[v{i}]")
        parts.append(f"[0:a]atrim={k['start']}:{k['end']},asetpts=PTS-STARTPTS,"
                     f"afade=t=in:d={f},afade=t=out:st={d - f:.3f}:d={f}[a{i}]")
        labels.append(f"[v{i}][a{i}]")
    parts.append(f"{''.join(labels)}concat=n={len(keeps)}:v=1:a=1[v][a]")
    script = out_dir / "cut-filter.txt"
    script.write_text(";\n".join(parts), encoding="utf-8")

    out = out_dir / "cut.mp4"
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(video),
                    "-filter_complex_script", str(script), "-map", "[v]", "-map", "[a]",
                    "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)],
                   check=True)

    # Remap word timestamps onto the cut timeline; words inside removed ranges are dropped.
    remapped, offset = [], 0.0
    bounds = []
    for k in keeps:
        bounds.append((k["start"], k["end"], offset))
        offset += k["end"] - k["start"]
    for w in words:
        mid = (w["start"] + w["end"]) / 2
        for s, e, off in bounds:
            if s <= mid < e:
                remapped.append({"text": w["text"],
                                 "start": round(max(w["start"], s) - s + off, 3),
                                 "end": round(min(w["end"], e) - s + off, 3)})
                break
    (out_dir / "transcript.cut.json").write_text(json.dumps(remapped, indent=2), encoding="utf-8")

    actual = probe_duration(out)
    print(f"Rendered {out} ({fmt(actual)}, expected {fmt(offset)})")
    print(f"Remapped transcript: {out_dir / 'transcript.cut.json'} ({len(remapped)}/{len(words)} words kept)")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("video")
    p.add_argument("transcript")
    p.add_argument("--out", help="output dir (default: the video's folder)")
    p.add_argument("--apply", action="store_true", help="render using the existing cut-plan.json")
    p.add_argument("--min-silence", type=float, default=0.7)
    p.add_argument("--noise-db", type=float, default=-35)
    p.add_argument("--pad", type=float, default=0.15, help="breathing room kept around speech")
    p.add_argument("--retake-window", type=float, default=6.0)
    a = p.parse_args()

    video = pathlib.Path(a.video)
    out_dir = pathlib.Path(a.out) if a.out else video.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    words = json.loads(pathlib.Path(a.transcript).read_text(encoding="utf-8"))
    plan_path = out_dir / "cut-plan.json"

    if a.apply:
        if not plan_path.exists():
            sys.exit(f"No {plan_path} - run without --apply first to create it.")
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        # Recompute keeps from the (possibly hand-edited) remove list.
        plan["remove"] = merge(plan["remove"])
        keeps, t = [], 0.0
        for r in plan["remove"]:
            if r["start"] - t >= 0.1:
                keeps.append({"start": t, "end": r["start"]})
            t = max(t, r["end"])
        if plan["duration"] - t >= 0.1:
            keeps.append({"start": t, "end": plan["duration"]})
        plan["keep"] = keeps
        print_plan(plan)
        apply_plan(video, words, plan, out_dir)
    else:
        plan = build_plan(video, words, a)
        plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
        print_plan(plan)
        print(f"\nPlan saved: {plan_path}\nReview it, then re-run with --apply.")


if __name__ == "__main__":
    main()
