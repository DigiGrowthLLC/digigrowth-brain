# AI Video Editing — Notes & Prompt Library

Source: Nate Herk, "Opus 5.5 Just Changed Video Editing Forever (free skills)" (2026-09).
Transcript: `outputs/transcript-YTDown.com_YouTube_Media_7jHXoPGnA4c_Opus-5-5-Just-Changed-Video-Editing-Forever-free-skills_001_1080p-2026-09-30.txt`

Core idea: HyperFrames (HTML → video) + Claude, driven by natural-language direction. The agent
does the motion design and sound design, and it sources its own b-roll, screenshots, AI images, and
AI video. Editing stops being the bottleneck once your preferences live in skills.

---

## The 5-Pillar Framework

### 1. Transcribe first
- Word-level timestamps are what make beats land on the exact spoken word.
- They also let the agent find the story in raw footage.
- Tool: `python tools/transcribe.py <clip> --words --model large-v3 --out projects/<title>`

### 2. Cut before you decorate
- Remove mistakes, retakes, and dead space before any graphics work.
- Useful on its own: clean a clip, then take it anywhere.
- Tool: `python tools/rough_cut.py <clip> <transcript.json> --out <dir>` → review `cut-plan.json` → `--apply`

### 3. Plan the beats (Director's Brief)
- Speak in cues: "When I say *X*, have *Y* come in where I'm pointing."
- Name the **emotion/vibe**, not just the elements. You often don't know exactly what you want, but you know how the video should feel.
- Set latitude explicitly:
  - **strict**: only the beats I list
  - **creative**: add your own spin (subtle zooms, extra inserts)
- The better you define "good", the more aligned the output.

### 4. Skills flywheel
- Found a video you love? Hand it over: "analyze why this is so good → turn it into a skill" (`style-from-reference`).
- After every run, tell the skill what you liked and what you didn't. It gets written into the skill's Lessons log.
- **If you repeat yourself, it belongs in the skill.**

### 5. Verification loop (most important)
- The agent renders, screenshots, critiques, and fixes, several times over, before you see anything.
- You receive iteration 4–6, not iteration 1.
- Tool: `python tools/verify_render.py <render> <beats.json> --out <scratchpad> --transcript <t.json> --full`

---

## Visual Rules He Called Out
- **Legibility:** anything over footage sits on a liquid-glass card or a scrim. No bare text over busy video.
- **Keyword highlight strip:** key words at the bottom light up as they're spoken.
- **Subtle push-in zoom:** on the face cam, for hooks and emphasis (the agent added this unprompted, and it lifted engagement).
- **Side inserts:** b-roll, screenshots, and generated clips enter from the left or right, beside the face.
- **Show, don't claim:** when you say the tool can do X, put real proof on screen (screen recording or screenshot).
- **Takeovers:** full-screen visuals, or a split with the visual on half and the face on the other half.
- **Sound:** music synced to the cut, plus SFX on element entrances.
- **Showreels:** real assets beat generic ones. Pull from the brand's site and products, and keep typography, colors, and design language unmistakably on-brand.

## Asset Pipeline He Used (our equivalents)
| His | Ours |
|---|---|
| Screen recordings / screenshots | `tools/record_site_scroll.py`, Playwright |
| AI images (key.ai) | `tools/generate_creative.py image` (flux / nano-banana-pro) |
| Image → video (Kling) | `tools/generate_creative.py video` (Kling 2.1 i2v, ~$0.25/5s) |
| Music / SFX | `generate_creative.py music` (stable-audio), `hyperframes-media`, `media-use` |
| Transcription (Whisper / ElevenLabs) | `tools/transcribe.py` (local faster-whisper, free) |

---

## Prompt Library (adapted for DigiGrowth)

### Director's-brief talking head (his intro)
> Edit `<clip>` with HyperFrames using the video-production skill. Transcribe first so every graphic lands on the exact word. When I say "<phrase>", bring <element> in where I'm pointing, on a glass card so it's readable. When I say "<phrase>", put those words in the bottom highlight strip and light them up as I say them. For the rest, whenever I mention a tool or a result, bring in proof on the left/right: a real screen recording or screenshot, or generate one if we don't have it. Vibe: confident, fast, premium. Latitude: creative.

### Course-style / explainer
> Edit this as a course-style video. Start the camera full screen, then move it into a rounded crop over a minimal DigiGrowth navy background. Show big bullet-point takeaways, not wordy. For visual aids, use simple AI-generated images with light motion to illustrate concepts.

### Whiteboard split
> Simple, clean, hand-drawn whiteboard style, as if explaining to a 10-year-old. Some scenes are a full-screen whiteboard takeover. Others put the whiteboard on the left half and my face on the right half. Generate any images you need.

### Fast short-form (9:16)
> Turn this into a fast-paced 9:16 short. Generate the assets you need. Keep it engaging and easy to understand, with scene changes every 2–4 seconds and b-roll behind or beside me.

### Showreel / brand reel
> Make a dynamic 15-second motion-graphics reel for DigiGrowth, like it's your showreel for a resume. Go all out. Use real assets from digigrowthllc.com and our dashboard. Generate anything else with generate_creative.py. Sync music and SFX to the beats.

### Sizzle from a folder
> Look through `<folder of recordings>` and tell a story. Build a 60-second sizzle reel from the best transcript moments (energy, reactions, wins), and end on a logo reveal.

### Reference → skill
> Analyze `<inspiration.mp4>`. Figure out exactly why it works (pacing, type, color, motion, sound) and turn it into a style skill with style-from-reference.

## Settings
- He ran everything at **high effort**. Match that for editing jobs.
- Expect 1 prompt plus 1–2 iteration rounds on complex pieces (his event sizzle reel took 3 prompts).
