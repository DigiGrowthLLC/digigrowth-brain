# Style From Reference Skill
## Turn an inspiration video into a reusable editing-style skill

---

## SKILL IDENTITY

Dylan finds an edit he loves (a reel, an ad, a YouTube intro) and hands it over. Your job is to
work out **why it works**, precisely enough that another run could reproduce the feel on his
footage. Then write that down as a style skill that `video-overlay` / `video-production` can apply.
The skill improves every time it's used, through its Lessons log.

"If you find yourself repeating something, put it in the skill."

---

## TRIGGER

- "analyze this video and make it a skill", "turn this into a style"
- "make my videos look like this", "steal this editing style"
- A reference `.mp4` handed over together with "like this" / "this style"

---

## WORKFLOW

### STEP 1 — Gather the evidence
Work in the session scratchpad (never the repo) at `<scratchpad>/ref-<name>/`.
```bash
# duration + resolution
ffprobe -v error -show_entries format=duration:stream=width,height,r_frame_rate -of json "<ref>.mp4"

# every cut: frames at scene changes (lower 0.3 -> 0.2 if it finds too few)
ffmpeg -i "<ref>.mp4" -vf "select='gt(scene,0.3)',showinfo,scale=640:-1" -vsync vfr "<dir>/cut-%03d.jpg" 2> "<dir>/scenes.log"
# cut timestamps are the pts_time values in scenes.log

# evenly spaced frames too (1 every 2s for clips under 60s, every 5s otherwise), to catch motion inside shots
ffmpeg -i "<ref>.mp4" -vf "fps=1/2,scale=640:-1" "<dir>/even-%03d.jpg"

# speech, if any
python content-agent/tools/transcribe.py "<ref>.mp4" --words --out "<dir>"
```
If there are more than ~40 frames, tile them into contact sheets (ffmpeg `tile=4x4`) before
reading so you can see the rhythm.

### STEP 2 — Analyze (read every sheet)
Fill in each dimension with **measurements, not adjectives**:

| Dimension | What to capture |
|---|---|
| Pacing | Average shot length, how the cut rate changes over time (does it accelerate into the payoff?), where it holds |
| Structure | Hook (first 2s), build, payoff, and the ending (logo lockup? loop back?) |
| Typography | Families (closest Google Font), weights, sizes relative to frame height, case, tracking, how words enter (per-letter, per-word, mask reveal) |
| Color | 3–6 hex values sampled from frames: background, primary, accent, text. Gradients and grain |
| Layout | Where text and graphics sit relative to the subject, safe zones, use of depth/3D/parallax |
| Motion vocabulary | Named moves with durations and eases (e.g. "0.25s back.out overshoot pop", "whip-pan 6f", "slow push-in 1→1.08 over 4s") |
| Transitions | Hard cut / match cut / zoom-through / mask wipe, and when each one is used |
| Sound | Music energy and BPM feel, whether cuts land on beats, SFX types (whoosh, click, riser, impact) and what triggers them |
| Assets | Real screenshots or product shots vs AI imagery vs stock; how they're framed |
| The "why" | 3–5 sentences on what makes it feel the way it does. This is the part to reproduce |

Show Dylan the analysis in chat as a short summary and ask whether it caught what he likes about it.
He may point at one specific thing ("the pop-in text is what I want"). Weight the skill toward that.

### STEP 3 — Write the style skill
Create `content-agent/.claude/skills/style-<name>/SKILL.md` with these sections:
1. **When to use.** The kinds of videos this style fits, and the ones it doesn't.
2. **Tokens.** A colors/fonts/sizes block in CSS-variable form, mapped to DigiGrowth's brand where
   they conflict. Keep the reference's feel but use house colors, unless Dylan says to copy the
   palette.
3. **Motion vocabulary.** Each named move as a ready GSAP snippet with duration and ease.
4. **Pacing rules.** Cut or beat frequency, hold rules, and how density changes over the video.
5. **Layouts.** Which `video-overlay` card types (1–17) to use, which to avoid, and any new
   layout as an HTML template following the media and legibility rules in `video-overlay`.
6. **Sound.** Music prompt for `generate_creative.py music`, SFX triggers.
7. **Reference.** The source file path plus 3–4 key frame descriptions, so a future run can
   re-check against it.
8. **Lessons log.** Empty, in the same format as `video-overlay`'s.

Then add one line to the **STYLES** list in `content-agent/.claude/skills/video-overlay/SKILL.md`
Step 0: `` - `style-<name>`: <one-line description> ``.

### STEP 4 — Prove it
Offer a short test: apply the style to 15–30s of one of Dylan's clips through `/video-production`,
including its verification loop. Whatever he dislikes in the test goes straight into the new
skill's Lessons log. That's the flywheel.

---

## WHAT THIS SKILL DOES NOT DO

- Copy someone's footage, logos, or music into Dylan's videos. It extracts technique, not assets.
- Edit the video itself. That's `/video-production` / `/video-overlay`, using the new style.

---

## INVOCATION

```
/style-from-reference [path to reference .mp4] [optional: style name]
```
> "Analyze this reel and turn it into a skill: C:\Users\dylan\Downloads\ref.mp4"
