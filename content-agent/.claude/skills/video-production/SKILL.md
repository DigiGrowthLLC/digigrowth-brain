# DigiGrowth Content Enhancement Skill
## End-to-end AI video editing: raw footage → cut → beats → assets → build → verified export

---

## SETUP (Run Once)

```bash
GIT_LFS_SKIP_SMUDGE=1 npx skills add heygen-com/hyperframes --all
npx hyperframes browser ensure
npx hyperframes doctor
```
`ffmpeg`/`ffprobe` on PATH, and `faster-whisper` (auto-installed by `tools/transcribe.py`). Paid
asset generation needs `FAL_KEY` from Doppler (`doppler run --project digigrowth --config prd -- ...`).

---

## SKILL IDENTITY

You are DigiGrowth's video post-production agent. Raw footage (face cam, screen recordings, or both)
goes in, and a polished, on-brand video comes out, already checked by you before Dylan sees it. This
skill **orchestrates** the pipeline. The per-card craft (templates, positions, GSAP) lives in
`/video-overlay`, which this skill calls for the build.

The five pillars, in order: **transcribe → cut → plan beats → use skills → verify in a loop.**
Background and prompt examples: `content-agent/context/ai-video-editing-notes.md`.

Run editing jobs at **high effort**.

---

## BRAND SYSTEM

House style is the DigiGrowth dark navy glassmorphism, the same as the dashboard and `video-overlay`:
```
--brand-navy:   #090f26   /* base / card background */
--brand-blue:   #3a7bd5   /* accent, kickers, borders, highlights */
--brand-green:  #14c882   /* positive / automated / growth */
--text-white:   #ffffff
--text-dim:     rgba(255,255,255,0.52)
```
- Fonts: **Space Grotesk** (headlines, UI labels), **Share Tech Mono** (numbers, stats, metadata), Inter (body)
- Glass card base and every card template: see `/video-overlay` BRAND SYSTEM
- Gradients go dark-to-blue only, never rainbow
- A style skill from `/style-from-reference` may override motion and layout. Brand colors stay unless Dylan says otherwise.

---

## WORKFLOW

When given raw footage, follow these steps in order. Project folder: `content-agent/projects/[title]/`.

### STEP 1 — Audit the input
- Confirm the files exist, and identify face cam vs screen recording vs combined
- `ffprobe` duration, resolution, fps, and audio stream for each
- Report findings before proceeding

### STEP 2 — Transcribe + rough cut
```bash
python content-agent/tools/transcribe.py "[raw].mp4" --words --model large-v3 --out content-agent/projects/[title]
python content-agent/tools/rough_cut.py "[raw].mp4" content-agent/projects/[title]/transcript.json --out content-agent/projects/[title]
```
This prints the cut table: dead space and stumbles are auto-detected, and **repeated passages**
(multiple takes of the same lines) are reported but not cut.
- **Take selection is your job.** For each repeated passage, read those transcript ranges and pick
  the cleanest, most energetic take (usually the last complete one). Add `remove` entries for the
  other takes to `cut-plan.json`, with reason `take selection: kept take N`.
- Present the final cut list to Dylan with a before → after duration and **wait for approval**.
- `rough_cut.py ... --apply` renders `cut.mp4` and writes `transcript.cut.json` (already remapped,
  so there's no need to re-transcribe).
- Listen-check 2–3 joins by extracting ±2s around them. If a word got clipped, widen that remove
  range's edge by 0.1s and re-apply.
- Skip this step only if Dylan says the footage is already a clean take.

"Just clean up my clip" = Steps 1–2 only, then hand over `cut.mp4`.

### STEP 3 — Director's Brief + scene plan
Collect the brief (cues "when I say X → Y", vibe, latitude strict/creative, proof moments) as
defined in `/video-overlay` Step 2.5. Then output a scene plan:

```
SCENE PLAN
----------
Format: [SHORT 9:16 / LONG 16:9 / BOTH]
Style: [house / style-<name>]    Vibe: [...]    Latitude: [strict / creative]
Duration after cut: [X]

Scene 1: [0:00–0:03] — Hook — [what's on screen, push-in?]
Scene 2: [...]
Scene N: [...] — CTA / Outro

Beats: [card plan table from /video-overlay Step 3, with Cue + Asset columns; (added) marks your own additions]
Assets to source: [list + estimated $ for any paid generation]
Captions: [yes/no, identity]
Music/SFX: [yes/no, prompt]
```
**Wait for approval before building.**

### STEP 4 — Source assets
Follow `/video-overlay` Step 3.5: real capture first, then AI stills, then Kling motion. Get still
approval before paying for motion, and keep everything in `public/assets/manifest.json`.

### STEP 5 — Build
Run `/video-overlay` Steps 1 and 4–6 against `cut.mp4` + `transcript.cut.json` + the approved
`beats.json`.

**Face cam segments**
- Lower third on first appearance: `Dylan | DigiGrowth`
- Push-ins for the hook and big emphasis (card 15)
- Proof moments use Side Insert (13) or Takeover (16); teaching segments use Split Takeover (17)

**Screen recording segments**
- Thin `--brand-blue` frame around the screen
- Callout labels on key UI elements (`/graphic-overlays` style), zoom-punch when switching tools

**Stat/data moments**
- Share Tech Mono numbers that count up on entry, with a green glow for positive metrics
- `/motion-graphics` for any chart or growth visual

**Captions**
- Short-form: mandatory. Long-form: only if asked.
- Run `/embedded-captions` with the `anchor` identity by default, on house colors.

### STEP 6 — Verification loop
Run `/video-overlay` Step 7 in full: `verify_render.py` → read the sheets → score against the
rubric → fix → re-render, up to 3 iterations, each logged in `review-log.md`. **Never hand over an
unverified first render.**

### STEP 7 — Export
- **16:9:** the composition at 1920×1080, rendered via `npx hyperframes render public -o exports/[title]_long.mp4 --fps 30`, then mux.
- **9:16:** a separate composition at `data-width="1080" data-height="1920"`, reflowed rather than
  letterboxed (face cam cropped to the subject, cards stacked above and below the face), then
  rendered the same way to `exports/[title]_short.mp4`. The 9:16 goes through its own verify loop.
- Confirm file sizes, durations, and audio streams, and flag any render error immediately.

### STEP 8 — Lessons
Hand over the final exports + `review-log.md`, ask what he liked and didn't like, and append the
answers to the relevant Lessons log (`/video-overlay`, or the style skill used).

---

## TRANSITIONS

| Context | Transition |
|---|---|
| Scene to scene | Hard cut or 8-frame fade |
| Screen recording switch | Zoom punch (1.05x scale, 6 frames) |
| Into a b-roll takeover | Zoom punch in, hard cut out |
| Stat reveal | Slide up from bottom |
| Hook to body | Whip pan right |
| Outro | Fade to black with logo hold |

Never use dissolves or soft wipes. They read as low effort.

---

## INTRO / OUTRO TEMPLATES

**Short form intro (0:00–0:03):** the hook text pops in center (Space Grotesk 700, 52px), subtitle
below (dim), and a blue accent line sweeps left-to-right under the headline. The face cam starts on
a slow push-in.

**Short form outro (final 5s):** "Follow for more AI business tools", with the DigiGrowth wordmark
bottom center and a blue glow pulse.

**Long form intro (0:00–0:20):** face cam + title card split, topic headline top left, and a
"what you'll learn" card within the first 60s.

**Long form outro:** Subscribe CTA with an animated arrow, 2–3 related-video cards, and a 3s logo hold.

---

## SHORT FORM RULES (9:16)

- The hook lands in the first 2 seconds, with no slow intros
- Captions always on; text overlays bigger than you think (min 28px body)
- One idea per scene, cut aggressively, and change the visual every 2–4s (b-roll, push-in, card)
- Screen recordings: crop to the most relevant 60% and fill the frame
- A pattern interrupt before the CTA (zoom, color flash, or hard cut)

## LONG FORM RULES (16:9)

- Chapter lower-thirds every 2–3 minutes
- The lower third reappears after any cut longer than 30 seconds
- Screen recordings get a browser-chrome frame
- Proof over claims: every "this tool does X" gets a real capture or a generated visual

---

## ERROR HANDLING

- HyperFrames error → `npx hyperframes doctor`, then `npx hyperframes browser ensure`, then lint/validate before re-rendering
- A b-roll video renders black → it isn't a direct child of `#stage` (see the media rule in `/video-overlay`)
- A cue phrase isn't found in the transcript → flag it in the plan, never guess a timestamp
- Audio drift after a cut → check that `transcript.cut.json` (not the raw transcript) was used, then re-render the affected section
- Never silently skip a scene. Flag it and ask how to proceed.

---

## WHAT THIS SKILL DOES NOT DO

- Write the script → `/video-creation`
- Color grade raw footage or mix/master audio beyond ducking a music bed
- Upload to YouTube/TikTok (export only)
- Send anything to prospects → `/outreach-video`

---

## INVOCATION

```
/video-production [path to raw footage or folder]
```
> "Edit this with the video-production skill: [path]. When I say 'X', bring in Y. Vibe: fast and premium."
> "Just clean up this clip — cut the mistakes and dead space." (Steps 1–2 only)
