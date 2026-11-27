# Boulder Body Solutions creatives

**Client presentation (batch 1, approved 2026-11-09):** https://claude.ai/artifact/Tyg12xwYHwbToxSLWAEur5
Republish to this URL when the batch changes (build: `_build/` + `media-buying-agent/tools/ad_presentation/build_presentation.py`). Media is ~60 MB after the 2026-11-09 revision, so one publish fits (64 MB limit); split into two passes if it grows.

## Batch 1 (10 ads, all sell the $49 Why-It-Keeps-Coming-Back Assessment, normally $120, 10 spots/month)
| Folder | Stage | Format |
|---|---|---|
| c5-sore-spot | Unaware | Coded animated explainer (MAT named) |
| c1-helps-then-back | Problem aware | AI actor (Veo 3.1 Fast) + Annette review |
| c3-too-young-to-quit | Problem aware | AI actor (redone, trailhead lot) + Max review |
| c2-tried-everything | Solution aware | Aaron's photo, kinetic list + Annette |
| c6-clean-scan | Solution aware | AI actor (redone, garage) + Amie review |
| c7-before-the-injection | Solution aware | Aaron's photo + Nicolene's story |
| c8-managed-never-fixed | Solution aware | AI actor, 5 takes + Sando review |
| c4-before-the-lifts | Product aware | AI chairlift scene + Aaron's photo |
| c9-boulder-checklist | Product aware | Static |
| c10-max-review | Most aware | Static review card |

Upload notes: every ad uses the CTA button **Sign up** (not Book Now, which Meta rejects with an Instant Form). Each video has `-9x16.mp4` (Reels/Stories) and `-4x5.mp4` (Feed) for the same ad. Each `copy.md` holds 3 primary texts + 5 headlines.
Production cost: ~$23.25 (incl. 2026-11-09 redo of C3/C6) on fal.ai (7 stills + 14 Veo 3.1 Fast takes). Voice/actor prompts for iterations: `_veo-takes-reference.sh`.

2026-11-09 revision (Dylan): simpler end card on every ad (`end_card.style = "simple"` / `ov.simple_offer_card`), Aaron's treatment photo shown whole instead of tightly cropped, C3/C6 re-shot with ordinary-looking actors. Rebuild scripts/specs in `_build/redo/`.

2026-11-09 revision 2 (Dylan: too basic, one image reused): 6 AI B-roll images (`_build/broll/`, ~$1.20) cycled into all videos and both statics; picture-in-picture cutaways on the 4 talking ads; end cards + statics now carry real social proof (5.0 Google, #1 BusinessRate 2026) and "Only 10 new-patient spots this month"; first ad text of each ad gets the proof line. Builders: `_build/redo2/` + scratch scripts. Total fal spend ~$24.45 of $25.
