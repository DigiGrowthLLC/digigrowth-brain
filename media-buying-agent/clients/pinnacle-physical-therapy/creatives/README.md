# Pinnacle Physical Therapy creatives

**Batch 1 (2026-11-05), own footage, approved:** 6 videos cut from Brian's YouTube channel, 2 AI actor videos (C1, C7) and 2 statics (C5, C6): all 10 approved by 2026-11-06 (@pinnaclephysicaltherapy4551). Each folder holds the full-quality upload files (9:16 + 4:5) and `copy.md` (3 primary texts, 5 headlines, proven-ad sources). Canonical copy: `copy-batch1.md`. Client-facing artifact (all 10, 2026-11-06): https://claude.ai/artifact/8FUY8QGEe4m7WZJUKbtA8d (slug 3ab55a7d-e814-445f-88f8-35fdd3ee2496). Rebuild with `_build/build_presentation.py <out_dir>` + `_build/presentation_template.html`, republish to the same slug.

| Folder | Ad | Source video |
|---|---|---|
| c2-back-is-the-victim | 34s, Brian to camera | l-5EI7a0Q8k "Hips / Low Back Pain Connection" |
| c3-dont-quit-golf | 39s, Darrell's testimonial | OdFQkrzqH1Y |
| c4-golfers-over-40-play-18 | 23s, TPI screen + text beats, lo-fi bed | 3CzsTua9Z8I |
| c8-what-happens-at-the-visit | 36s, Brian to camera | COyKXZUd5Oo "What is A Discovery Visit?" |
| c9-advil-back-nine | 18s, Brian to camera | zgKeN-e5j54 "Is pain holding your golf game back?" |
| c5-barry-review-card | Static, Barry's quote on Brian's headshot (variation a of 3) | Portal upload 243 + Barry's site testimonial |
| c6-offer-card | Static, $49 offer card (variation a of 3) | Portal upload 248 |
| c1-advil-first-tee | 27s AI actor (golf cart, ~55), 3 Veo takes incl. spoken $150 anchor + 10 spots | actor.png + spec in copy.md |
| c7-youtube-swing-tips | 29s AI actor (garage, ~47), 3 Veo takes incl. spoken anchor + 10 spots | actor.png + spec in copy.md |
| c10-full-golf-story | 49s, Brian + Kevin + TPI b-roll | 1GvMMQmZRh4, 3d_yWiZhRbI, 3CzsTua9Z8I, fELuP0w07-U |

Rebuild: `_build/cut_reels.py` + `_build/build_c4.py` + `_build/build_statics.py` (statics need the portal photos in a `portal/` folder) (re-download the sources into a `vids/` folder with yt-dlp first; transcripts are in `_build/transcripts/`). Burned-in source titles are cropped (VH) or covered (band).
Cleared 2026-11-05 (Dylan): 2020 golfer testimonials OK for paid ads; copy in Brian's voice OK; TPI screen is NOT part of the $49 visit, so all copy says "movement screen" and C4's beats sell Brian's golf expertise, not the screen (C4 + C6 re-rendered). His separate $99 TPI Golf Body Screen (Chenal CC) is live but separate from our offer: leave it alone.

**2026-11-06 (Dylan):** all videos end on the price end card (`ad_overlays.price_end_card`): struck $150 + big $49, ONLY 10 SPOTS THIS MONTH badge, "Book now before they're gone", 4s. The 6 own-footage cuts got it as an overlay on their last 3s + 1s (originals backed up in the session scratchpad); the `_build` scripts still draw the old card, so swap `ov.end_card` for `ov.price_end_card` before rebuilding.
