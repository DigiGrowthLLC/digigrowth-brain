# Content Creation SOP

Step-by-step process for every piece of content, start to finish. Free tools only.

## 1. Capture the Idea
1. Pull from one of 4 buckets (see `context/brand-strategy.md`): real-time thought, recent past (this week's calls/meetings), far past (big lesson), or manufactured (challenge/experiment).
2. Jot it in one line — that's the seed for the script.

## 2. Write the Script
1. Trigger the skill: `/video-creation`
2. Answer the 7 intake questions (topic, platform, target viewer, goal, story angle, assets, CTA).
3. Let it lock the title, story lens, and write the last line first.
4. Review the full script output: hook (5-step formula) → body → outro → last line, with inline `[VISUAL: ...]` callouts.
5. Output saves to `outputs/video-[topic]-YYYY-MM-DD.md`. This is your shot list and B-roll list too.

## 3. Record
1. **Camera:** use your phone, not the webcam — phone sensors beat cheap webcams.
2. **Mic:** use your external mic, not the phone/webcam mic, regardless of camera choice.
3. **Camera height:** raise the phone to eye level or slightly above on the ring-light arm (stack books / extend tripod column if needed). Avoid a sustained upward angle — it reads as unsure, not confident.
4. **Lighting:** face a window or a lamp with paper/cloth diffusion in front of it. Avoid overhead light.
5. **Teleprompter:** load the script from Step 2 into a free teleprompter app and read from it instead of memorizing.
6. Record face cam and any screen recordings. Save everything to `raw/`.

## 4. Clean Up Audio (free pass)
1. Run the raw audio through **Adobe Podcast Enhance** (free, browser-based) — removes background noise/echo.
2. Optional: use **Audacity** (free) for manual noise reduction / normalization if you want more control.
3. Save the cleaned audio back into `raw/` alongside the video, or re-mux if needed.

## 5. Edit / Post-Production
1. If face cam needs background removal, do that in **CapCut** first and export — this is the only pre-processing CapCut handles in this pipeline.
2. Trigger the skill: `/digigrowth-video` (or describe the raw footage paths naturally) to run the `video-production` skill.
3. Confirm the audit (file paths, durations, audio tracks).
4. Approve the scene plan it proposes before it renders anything.
5. It builds the full edit — cuts, transitions, captions, overlays, intro/outro — applying the DigiGrowth brand system automatically.
6. It exports both formats to `exports/`: `[title]_short.mp4` (9:16) and `[title]_long.mp4` (16:9).
7. Use CapCut only as a separate fast-path for quick one-off clips that don't need full brand treatment — not as a manual edit step in this main pipeline.

## 6. Repurpose
1. Pull the hook / best line from the finished script.
2. Trigger `/social-post` → generate 2–3 platform posts (LinkedIn, Instagram, X) from the hook.
3. Trigger `/ad-copy` if the piece has a clear offer angle worth testing as an ad.
4. Trigger `/email-sequence` if the piece fits into a nurture or cold sequence.
5. All save to `outputs/` with clear filenames.

## 7. Publish
1. Long-form (`exports/[title]_long.mp4`) → YouTube.
2. Short-form (`exports/[title]_short.mp4`) → Reels / TikTok / Shorts.
3. Social posts → LinkedIn / Instagram / X.
4. Ad copy → Meta Ads Manager.
5. Emails → email tool / outreach sequence.

## 8. Track & Iterate
1. After publishing, add a short entry to `memory.md`: hook/angle used, platform, date.
2. Once performance data is in, add a one-line note (worked / didn't, why) to the same entry.
3. Review this log periodically to spot which hooks/angles to reuse.

## 9. SEO Blog (separate track, not part of the video pipeline above)
1. Trigger the skill: `/seo-blog`
2. It checks `context/seo-keywords.md` for the next un-covered pillar/keyword and `memory.md` for
   posts already published, so pillars don't get duplicated.
3. Review the output: title, meta description, H1/H2 structure, and CTA.
4. Output saves to `outputs/blog-post-[slug]-YYYY-MM-DD.md`.
5. **Publish:** copy the finished post into the `digigrowth-website` repo's blog content (once the
   `/blog` route exists there — see that repo's SEO plan), commit, and push to `master` to deploy.
   This is a manual copy step today; there's no automated sync between the two repos.
6. Log the post in `memory.md` under "SEO Content": title, pillar, keyword, publish date.
7. Optionally repurpose the post's core point via `/social-post` or `/ad-copy`.
