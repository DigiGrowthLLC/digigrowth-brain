# Generate Ad Skill

Produce a finished Meta (Facebook/Instagram) ad — copy + a matching AI-generated image — for one
specific avatar/angle, ready for Dylan to review and upload manually. This does not touch the Meta
API, targeting, budgets, or campaign structure — see `CLAUDE.md` for what this agent does and does
not do.

---

## Trigger

Any request to write an ad, generate ad creative, make a Facebook/Instagram/Meta ad, or produce an
ad image + copy pairing.

---

## Inputs Needed

Ask if not already given:
1. **Offer/client** — what's being advertised (DigiGrowth's own service, or a specific client's
   business — get the vertical, guarantee/result, and price if relevant).
2. **Avatar(s)/angle(s)** — who this ad is for. If Dylan hasn't picked one, propose 2-3 narrow
   avatar/angle options per `context/ad-creative-principles.md`'s "go niche" guidance rather than
   defaulting to something broad.
2a. **Funnel stage — top or bottom** (per the "Only 2 Ad Creative Formats" section of `context/ad-
   creative-principles.md`): every concept must be explicitly one or the other, never a vague
   in-between ad.
   - **Top of funnel** = problem + solution, for an avatar who doesn't know your product yet. Build
     the angle from the avatar's list of problems (the Avatar Framework).
   - **Bottom of funnel** = one specific objection (usually price, unless Dylan names another), for
     an avatar who already knows the product but hasn't converted. Address only that one objection —
     don't restate the full pitch.
   - If Dylan doesn't specify, default to producing one of each rather than a single ad that tries to
     do both.
3. **New concept vs. iteration** (per the "Post-Andromeda" section of `context/ad-creative-
   principles.md`) — clarify which mode this request is:
   - **Default / most requests**: Dylan wants fresh creative to test → produce **new concepts**
     (each one a different format and/or different archetype/angle, not just a copy tweak). If asked
     for "a batch" or "some ads," default to 3-5 distinct new concepts rather than variations of one.
   - **Only when Dylan says a specific concept already won/is working**: produce **iterations** of
     that one concept (hook/copy/proof variants) instead — this mode is the minority case now, not
     the default (the old 80% iteration / 20% new-concept ratio flipped post-Andromeda).
4. **Format** — static image ad (default) vs. logo. When producing multiple new concepts, vary
   format across them where sensible (e.g. one native/advertorial-style still, one more
   testimonial/UGC-style still) rather than making every concept visually the same template with a
   different subject. Stills are the default. For **video ad variations** (scripts + shot briefs),
   follow the "Video Ad Variations" section below. Final editing/rendering of a video is still
   delegated to `content-agent`'s `video-production` skill.
5. **Recreating a specific competitor ad?** If Dylan or `research-competitors` points to one specific
   validated competitor ad to base a concept on (rather than building from scratch), treat this as an
   image-*edit* task, not a blank-canvas generation: describe that ad's actual structure (composition,
   layout, proof placement) in the image prompt and instruct the model to swap in the client's own
   branding/product/subject within that same structure, rather than just referencing it loosely. Note
   the raw Ad Library image usually can't be used directly as an input asset (it's typically
   watermarked "Protected") — work from the structural description, not the file itself. Always
   generate at least 3 alternate headline options for a recreated concept, not just one.

---

## Steps

1. **Re-read `context/ad-creative-principles.md`** before writing — every ad this skill produces
   should be checkable against its "Working Checklist" at the bottom.

2. **Write the copy** using the hook → problem → solution → proof → CTA framework:
   - **Hook** — stop the scroll, speaks directly to the avatar's pain, doubles as the on-image
     headline text.
   - **Problem** — agitate the specific pain this avatar has (not a generic pain).
   - **Solution** — the offer, stated simply.
   - **Proof** — a specific number, timeframe, or named result. Never fabricate a stat — use what
     Dylan/the client has actually claimed elsewhere (check `content-agent/memory.md` or ask), or
     mark it `[PROOF NEEDED: ...]` rather than inventing one.
   - **CTA** — one clear action.
   - If in **new-concept mode** (the default — see Inputs Needed): write copy for each distinct
     concept separately — each should read like a genuinely different ad (different format framing
     and/or different archetype), not the same ad with a swapped headline.
   - If in **iteration mode** (only once Dylan has confirmed a concept is a winner): write 1 primary
     + 1-2 alternate hooks on that same concept.
   - **If Dylan wants a short-form UGC video script** instead of/alongside a still (to hand off to
     `content-agent` or a human UGC creator — this skill itself stays stills-first, no video
     generation): map the same hook → problem → solution → proof → CTA beats onto an 18-20 second
     timed structure — hook 0-3s, problem 3-8s, solution 8-15s, proof 15-18s, CTA 18-20s — rather than
     leaving pacing unstated.

3. **Generate the image(s).** Build an image prompt from the hook/avatar/format of each concept (the
   visual should make the avatar unmistakable at a glance — literally show the avatar or a strong
   visual metaphor for their situation, per the "put the avatar in the ad" principle; vary the visual
   *format/style* across concepts too — e.g. one clean product/lifestyle still, one native-style
   "screenshot-like" high-curiosity still — not the same visual template restated). For each concept,
   run from `content-agent/`:
   ```
   python tools/generate_creative.py image "<prompt>" --aspect 4:5 --out "../media-buying-agent/outputs/<slug>/image.png"
   ```
   - Default `--aspect 4:5` (Meta's recommended Feed size). Use `9:16` only when Dylan asks for
     Stories/Reels placements, or `1:1` when he explicitly asks for square.
   - **Final ad size: every finished ad image (base photo + text overlays/CTA, i.e. what goes into
     `clients/<slug>/creatives/`) must be exactly 1080x1350 (4:5).** Build the overlay canvas at
     1080x1350 from the start, not a custom height, and lay out the text/CTA to fit inside it. The
     fal.ai base photo comes back at 1088x1360, so scale/crop it to cover the 1080x1350 canvas. If
     Dylan asks for Stories/Reels, the final size is 1080x1920 (9:16). For square, it's 1080x1080. Check
     the final file's pixel dimensions before calling a concept done.
   - This writes `image.png` and a `image.png.meta.json` provenance sidecar automatically.

4. **Save each concept's pairing while iterating** to its own
   `media-buying-agent/outputs/ad-<slug>-<YYYY-MM-DD>/`:
   - `copy.md` — avatar/angle, format, the copy, placement notes (mirrors `content-agent`'s
     `ad-copy` skill output format).
   - `image.png` + `image.png.meta.json` (from step 3).
   - When producing multiple new concepts in one request, use a distinct `<slug>` per concept so
     they land in separate folders — never merge distinct concepts into one folder.
   - This is scratch space — base photos, rejected attempts, and revision history all belong here
     while a concept is still being judged, same as before.

5. **Report** all output folder paths and run the Working Checklist from `context/ad-creative-
   principles.md` against what was produced — flag anything that doesn't clearly pass (e.g. no
   proof point available yet, or a "new concept" batch that's actually just iterations in disguise).
   Do this explicitly per concept, not as one blanket pass over the batch — when producing multiple
   concepts, call out which ones are strongest and which are weaker/borderline rather than presenting
   the whole batch as uniformly ready.

6. **Once Dylan approves a concept**, finalize it (see `CLAUDE.md`'s "Output Files" section): copy
   just the final image + a clean `copy.md` into
   `media-buying-agent/clients/<client-slug>/creatives/<concept-slug>/`, then delete the working
   `outputs/ad-<slug>-<YYYY-MM-DD>/` folder (and any sibling folders for rejected/superseded attempts
   on the same concept) so drafts don't pile up in the repo. Don't finalize a concept Dylan hasn't
   actually approved — a still-in-review concept stays in `outputs/` until it's a yes.

---

## Video Ad Variations

Use when Dylan asks for more video ads, or variations on an existing video ad. Source: "How To Make AI
Ads With Claude x Meta" (see `context/ad-creative-principles.md`, 2026-09-22 source + 2026-09-29
update).

1. **Start from the existing video.** Ask for (or read) the current video ad's script, speaker,
   setting and format. A *variation* keeps the same speaker/format/setting and changes the **script:
   a new hook and angle**. If the speaker, format, and angle all change, it's a new concept, not a
   variation. Say which one you're producing.
2. **Write 4-5 scripts, keep the best 2.** Each 18-20s, natural spoken language, written for a cold
   audience: hook 0-3s, problem 3-8s, solution 8-15s, proof 15-18s, CTA 18-20s. Score each out of 10
   against the Working Checklist in `context/ad-creative-principles.md`. Present only 9.5+ scripts
   as ready, and list the rest as weaker instead of silently dropping them.
3. **Per script, write a shot brief:** speaker (age, gender, setting, emotion), vertical, handheld,
   candid feel; the on-screen hook text for the first 3 seconds; burned-in captions (most viewers
   watch muted); the end card with the offer + CTA.
4. **Who can say what (healthcare/service clients):**
   - Proof must come from real people. Real Google reviews go **on screen as text quotes**,
     first-name attribution, same as the statics.
   - The practitioner (e.g. Brandon's real footage from the client portal) can speak as himself.
   - An AI-generated or hired actor may voice the *problem* as a relatable scenario ("Nine hours at a
     desk, and my shoulders are wrecked by 3pm") but must **never** present themselves as a patient,
     or read a real review as their own story. A fabricated patient testimonial breaks FTC
     endorsement rules and Meta's ad policies.
   - Don't write hooks that assert the viewer's condition ("Your back pain…", "Are you suffering from
     sciatica?"). Meta's personal-attributes policy rejects them. Describe the situation or the
     service instead.
5. **If generating AI footage:** generate and get approval on the speaker/scene **still first**
   (cheap to fix), then turn the approved still into video (image-to-video, "vertical 9:16, handheld
   feel, candid and authentic") with `generate_creative.py video "<motion prompt>" --image <still>
   --duration 5 --out <clip>.mp4` (fal.ai Kling image-to-video, ~2-4 min per clip). Kling can't
   lip-sync, so AI shots are silent: use text-on-video (POV) or the practitioner's real voice.
   Shoot AI people from behind in follow-up shots so one face doesn't have to stay consistent
   across separate generations. No "Dramatization"/AI disclaimer label on screen: Dylan had them
   removed (2026-09-29).
   Worked example (2026-09-29, approved): `clients/crosacore/creatives/video-3pm-desk/` (AI desk
   shots + real portal photos + music bed). A re-cut of the practitioner's own educational footage
   ("Better on Vacation") was made the same day and **rejected** by Dylan.
6. **Deliver two sizes:** 4:5 (1080x1350) for Feed and 9:16 (1080x1920) for Reels/Stories, both
   uploaded to the same ad.
7. **Save** each variation's `script.md` (script, shot brief, score) to
   `media-buying-agent/outputs/ad-<slug>-video-<YYYY-MM-DD>/`; finalize approved ones into
   `clients/<client-slug>/creatives/<concept-slug>/` (`video.mp4` + `copy.md`) like stills.
8. **Account placement:** videos run in their **own ad set**, separate from statics (see "Segment by
   Creative Type" in the principles file). Meta skews spend by media type when they're mixed.

For a **talking AI actor** (UGC selfie-style), use the full loop below instead of step 5.

---

## AI UGC Video Ads (the "Claude x Meta" loop)

Use when Dylan asks for an AI UGC ad, a "completely original" AI video ad, or to "run the Arcads
process." This replicates the workflow from "How To Make AI Ads With Claude x Meta" (research → scripts
→ actor stills → talking video → launch → read results → double down) with our own stack. Arcads
isn't needed: it resells the same models (Seedance, Veo, Nano Banana) at $77-110+/mo. We call them
pay-per-use on fal.ai (~$7-8 per finished 15s ad). What Arcads adds is a library of *licensed real
actors*, which matters only if the Seedance face block (step 4) becomes a real bottleneck. Worked
example (approved): `clients/crosacore/creatives/video-no-time-for-pt/` (finished ads, `actor.png`
and `copy.md` with the reusable voice/lighting lines).

1. **Research, before writing anything** (the step "most people skip"). Save as `brief.md`:
   - **Own account:** `ads_get_ad_entities` at `level: "ad"`, `date_preset: "last_30d"` (or
     `maximum` for a young account): spend, CTR, CPC, CPM, results per ad. Which angle and format
     is already winning? Is lead tracking actually firing?
   - **Category (Meta Ad Library):** `ads_library_search` with category keywords, `countries: ["US"]`,
     `ad_active_status: "ACTIVE"`, `limit: 50`. Tally repeated headline patterns and offers,
     advertisers running many variants, and **what nobody is saying** (white space).
   - **Web:** WebSearch "best performing UGC video ad hooks <category> Meta <year>" for current
     formats, hooks and benchmarks.
   - **Client proof:** mine the client's real reviews/testimonials (portal uploads) for a quote that
     proves the chosen angle, and verify every factual claim against the client's own materials
     (e.g. CrosaCore is "in-clinic & in-home", **not** office; that wording error was caught in
     this step).
   - End with a one-paragraph brief: avatar, winning angle, format, proof.
2. **Scripts (senior performance-marketer pass):** top 3 pain points → **5 scripts**, one per angle,
   written for a cold audience in natural spoken language. **One Veo take = 8s max**, so write each
   script as ~2 takes of ≤8s: hook 0-3s, problem 3-7s, solution 7-12s, CTA 12-15s spoken, then
   proof card + end card added in the edit (≈20s total). Score each /10 against the Working
   Checklist, keep only **9.5+**, and list the rest with the reason (don't drop silently). Give each
   kept script an **actor spec**: age, gender, setting, emotion, wardrobe. Apply the "Who can say
   what" guardrails above: the actor voices the situation and the offer's facts, **never** a
   results claim or a patient story.
3. **Actor still (Nano Banana Pro), then approval:**
   `generate_creative.py image "<actor spec + setting + 'vertical front-camera selfie frame,
   natural skin texture, realistic smartphone quality, no text'>" --model nano-banana-pro
   --aspect 9:16 --out work/actor-<x>.png` (~$0.15). Add `--ref <file>` to hold a product, place or
   outfit exactly. **Review the still before any video**: hands, face, wardrobe, background text.
   Fix with a new prompt now, because fixing a still is much cheaper than a video. Dylan approves it,
   unless he's said to run it end to end.
4. **Talking video (Veo 3.1):** one call per take, all from the **same approved still**:
   `generate_creative.py video "<Handheld front-camera selfie video, vertical 9:16, candid UGC. The
   woman talks straight into the camera, <voice description, identical in every take>... She says:
   \"<exact line>\" Quiet <setting> ambience, no music, no subtitles, no on-screen text.>"
   --model veo31 --image work/actor-<x>.png --duration 8 --out work/take<n>.mp4` ($0.40/s ≈ $3.20
   per take). **Don't use `seedance2` for AI actors:** its partner filter rejects photoreal faces as
   "likenesses of real people" (422 content_policy_violation). It's fine for scenes without a face.
   Then **verify**: transcribe each take (words must match the script), sample frames for glitches,
   and ask Dylan to listen to the cut between takes, since the voice can drift slightly across
   generations.
5. **Assemble:** write `spec.json` (takes with in/out trim points, hook text, real-review proof card,
   end card, music, and an optional corner `label`) and run
   `python media-buying-agent/tools/assemble_ugc_ad.py <folder>/spec.json`. It transcribes the takes
   for word-timed captions, keeps text out of the Reels bottom-35% zone, and renders `<slug>-9x16.mp4`
   + `<slug>-4x5.mp4`. For a music bed under the cards:
   `generate_creative.py music "<style>, no vocals" --duration 12 --out work/bed.wav`. Check frames
   from both formats before calling it done.
6. **Launch:** Meta's upload tools (`ads_creative_upload_media`) are still "being gradually rolled
   out" for the client accounts as of 2026-09-29, so Dylan uploads in Ads Manager. Hand over the
   files, primary text, headline and button, and name the ad set it belongs in (videos get their own
   ad set). Launching via the Meta connector stays off unless Dylan explicitly asks for it in that
   conversation. Even then, create everything **PAUSED** for him to review and switch on (see
   `CLAUDE.md`).
7. **Read results (after 5-7 days of spend):** `ads_get_ad_entities` at `level: "ad"` for the ad set:
   spend, CTR, CPC, 3-second view rate (hook rate: 25-40% is strong, under 20% means a hook problem),
   leads, cost per lead. Report the winner in plain English.
8. **Double down on the winner:** "same actor, different scripts." Reuse the winning actor still and
   voice description, write 5 new scripts on the winning angle, and repeat steps 2 → 5. Changing the
   actor or format makes it a new concept, not an iteration.

---

## After Generating

Per the ratio-flip principle: don't default to offering another iteration on the same concept. Instead
ask whether Dylan wants to (a) generate more distinct new concepts (the default next step, while
nothing has proven itself yet), or (b) — only once he's told you a specific concept is actually
performing — start iterating variations on that one winner.
