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
   business — get the vertical, guarantee/result, and price if relevant). For a client, the ad
   sells the **approved offer** in the "## Offer" section of `clients/<slug>/client-context.md`
   (from `build-offer`): its name, what's included, risk reversal and real capacity. With no
   approved offer, use the free-consult default. Where this skill says "free consult" or "never a
   price", read it as "the client's approved offer."
2. **Avatar(s)/angle(s)** — who this ad is for. If Dylan hasn't picked one, propose 2-3 narrow
   avatar/angle options per `context/ad-creative-principles.md`'s "go niche" guidance rather than
   defaulting to something broad. For PT clients, draw the options from
   `context/pt-ad-concept-library.md`, matched to the client's services and demographic by each
   concept's "best for."
2a. **Awareness stage: exactly one per ad** (AdsMastery 2027 section of `context/ad-creative-
   principles.md`, which replaced the older "top or bottom only" rule on 2026-10-08). Tag every
   concept with one stage and make it do only that stage's job:
   - **Unaware**: a surprising fact about a situation, or the founder story.
   - **Problem-aware**: a functional before/after through a real patient review, or benefit
     callouts. Build the angle from the avatar's list of problems (the Avatar Framework).
   - **Solution-aware**: PT vs. the alternatives, 3 reasons why, real review cards.
   - **Product-aware**: one specific objection (usually cost or time, unless Dylan names another),
     plus the free-consult reminder. Address only that one objection, don't restate the full
     pitch, and never a price.
   - **Most-aware**: a direct "book your free consult" ad.
   - In a batch, spread the concepts across stages. If Dylan doesn't specify, default to one
     problem-aware, one solution-aware and one product-aware concept.
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

## Review gates (step by step with Dylan, 2026-10-08)

Dylan wants to review and approve as the ad gets made, not get a finished batch at the end. Each
stage below ends at a gate. At each gate, show the work, ask with `AskUserQuestion` (**Approve** /
**Edit** / **Redo**) and **stop until he answers**. Gates are ordered so each one comes before the
next spend: an edit to the brief is free, an edit to a Veo video costs about $3 per take.

1. **Brief gate:** the six-field brief per concept (step 2), plus the research quote and proven ad
   it's built on.
2. **Copy gate:** hooks, primary-text variations and headlines (step 2).
3. **Visual gate:** the image, or for video the actor still / first scene still (step 3, and
   step 3 of the UGC loop) before any video is generated.
4. **Final gate:** the finished composite or rendered video in both sizes, before finalizing into
   `clients/<slug>/creatives/` (step 6).

With several concepts, go through each gate with the whole batch side by side (so he can compare),
unless he asks to go one concept at a time. Only skip gates if Dylan says so in the current
conversation.

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
   - **CTA** — one clear action, framed around personalization (what they get for *their*
     situation), not a generic "Book now."
   - **Copy rules** (Hormozi live ad review, 2026-10-07 — full notes in `context/ad-creative-
     principles.md`). Apply them to every line before delivering:
     - **Hook = a pain yes-statement.** The first line should make the avatar nod: "yeah, that's
       me." Usually a "You ever...?" question about a situation they live with. Never an offer
       stack, a feature list or an exclamation-point promise. For healthcare, keep the
       yes-statement about a situation, not a condition (Meta's personal-attributes policy):
       "Ever skip the run because your knee might act up?" passes, "Do you have knee pain?" doesn't.
     - **Callouts must be labels people give themselves.** If the avatar wouldn't use the word
       about themselves, chunk up or down a level until they would.
     - **No emojis anywhere** (primary text, headline, on-image text) and no hype punctuation. Ads
       should read like organic posts. Condition checklists stay as plain short lines. When
       modeling on a proven ad that uses emojis, keep its structure and drop the emojis.
     - **Feature → benefit → benefit of the benefit.** Never state a feature alone. Then reword
       any phrase you've seen in marketing before ("no guesswork", "root cause", "get back to what
       you love") until it sounds new. Model: "no guesswork" → "so the easiest thing to eat is also
       the right thing to eat."
     - **Plain writing:** third-grade reading level, short simple sentences, few commas (split the
       sentence instead), "..." and line breaks for runs of points.
     - **Teach something, using an analogy from the avatar's world** (desk job, kid's game, car
       tune-up), so the ad gives value before the click.
   - **Copy tactics for statics** ("How I Make AI Static Ads" section of the principles file): every
     static uses at least one: a specific number about the service, an audience callout, a taboo
     line, a primal desire as the headline, a curiosity loop, a named fear, a golden-nugget review,
     or a shown transformation. **Golden-nugget pass:** before writing proof lines, run the
     client's real reviews through a "which lines would work best as ads" pass and pick from those
     (first names only).
   - **Brief first, then psychology (Creative Don, 2026-10-08, full notes in `context/ad-creative-
     principles.md`).** Before writing each concept, fill its brief: concept, creative type
     (curiosity static, us vs. them, USP callout, social proof, meme/humor...), angle, headline,
     CTA, visual direction. No two concepts in a batch share a creative type. Name the lead
     element (Attention / Curiosity / Emotion / Connection) and the core emotion, chosen for the
     avatar. Curiosity-led ads that barely sell only go to a landing page that sells, never a bare
     Instant Form. Use the avatar's insider words, lifted from `clients/<slug>/customer-language.md`
     when it exists.
   - If in **new-concept mode** (the default — see Inputs Needed): write copy for each distinct
     concept separately — each should read like a genuinely different ad (different format framing
     and/or different archetype), not the same ad with a swapped headline.
   - If in **iteration mode** (only once Dylan has confirmed a concept is a winner): write 1 primary
     + 1-2 alternate hooks on that same concept.
   - **Three copy variations per ad, each modeled on proven copy (Dylan, 2026-10-06).** For every
     ad Dylan has approved (stills and video alike), write **3 primary-text variations**, each one
     built on the copy of a specific proven ad in `context/proven-ads/<vertical-slug>.md` (still
     active, running 6+ months; run `research-competitors` first if that file is missing or stale).
     Start with the proven ad the concept was built on, then two others with a different copy
     structure (e.g. a short city-callout + checklist, a story-led long form, a testimonial-led
     open), so the three read as genuinely different, not reworded. For each variation:
     - Cite its source: `Modeled on P4 (<advertiser>, running <N> months): <structure borrowed>`.
     - Keep the proven ad's **structure, rhythm and length** (opener type, line breaks, where the
       proof and offer sit, CTA phrasing pattern); swap in the client's real offer, avatar, proof
       and facts.
     - Never copy a competitor's claims, prices, offers, credentials, names or distinctive phrases
       word for word, and drop any part that breaks the client's brand-voice rules or
       `client-context.md` (e.g. a "$49, only 30 spots" mechanic for a no-pressure brand).
     - Pair the variations with headlines in the same spirit (Meta accepts up to 5 primary texts and
       5 headlines per ad, so all three go into the same ad for Meta to rotate).
     Save all three in the ad's `copy.md` with their citations.
   - **If Dylan wants a short-form UGC video script** instead of/alongside a still (to hand off to
     `content-agent` or a human UGC creator — this skill itself stays stills-first, no video
     generation): map the same hook → problem → solution → proof → CTA beats onto an 18-20 second
     timed structure — hook 0-3s, problem 3-8s, solution 8-15s, proof 15-18s, CTA 18-20s — rather than
     leaving pacing unstated.

3. **Generate the image(s).** Build an image prompt from the hook/avatar/format of each concept (the
   visual should make the avatar unmistakable at a glance — literally show the avatar or a strong
   visual metaphor for their situation, per the "put the avatar in the ad" principle; vary the visual
   *format/style* across concepts too — e.g. one clean product/lifestyle still, one native-style
   "screenshot-like" high-curiosity still — not the same visual template restated). No abstract
   "AI art" mood images: when the image isn't showing the avatar or the outcome, show the process
   (a concrete step of the service and why it works). Testimonials work better as video with
   punch-ins than as a stacked text block.
   **Static format and checks** (static masterclass section of the principles file): name each
   static's format (infographic, headliner, benefit callouts, comparison, transformation, grid,
   text-only) and production level (graphic, hi-fi, or lo-fi phone-photo look, which is often
   forgotten and working now). Start with **about 3 visual variations per concept**. Before the
   visual gate, check each one: the headline is the focal point, it passes the one-second
   comprehension test, there's no clutter (AI statics drift into too many callouts), and no AI text
   errors or em dashes (fix with a Nano Banana `--ref` edit rather than regenerating). For each concept,
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
   - `copy.md` — the brief from step 2 (concept, creative type, angle, headline, CTA, visual
     direction, lead element + emotion), the copy, placement notes (mirrors `content-agent`'s
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
   audience: hook 0-3s, problem 3-8s, solution 8-15s, proof 15-18s, CTA 18-20s. Apply the same
   hook / unique-mechanism / objection-handling CTA rules as the UGC loop's step 2. Score each out of 10
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

**Full-structure video (long form, ~40-60s).** A separate concept type from the 20s format, built
on Creative Don's 6 beats (see `context/ad-creative-principles.md`, "How to Make Meta Video Ads in
2026"): hook (ICP + angle) → story (the problem, relatable) → unique-mechanism problem → solution
("why this works when the usual options don't") → risk reversal (the free consult; a guarantee
only if the client has one) → testimonials (real review cards, first names, ideally a fast
scroll of several) → CTA (free consult; urgency only if real and on-brand, never a price). Make it
from 5-7 Veo takes of 8 seconds or less with the same approved actor (UGC loop steps 3-4), or from
the practitioner's own footage as a founder-led version. The same review gates apply: script,
then still, then the cut. `assemble_ugc_ad.py` handles takes, a proof card and an end card today.
A scrolling review wall with the speaker in a corner bubble would need a tool change, so ask
Dylan before building it.

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
   proof card + end card added in the edit (≈20s total). Script rules (Creative Don video source,
   2026-10-08): the hook only stops the scroll (visual hook in frame 1, curiosity, qualifies the
   ICP with insider words); the body names the unique-mechanism problem and solution, using
   proven messaging (cite the research quote or proven ad); the CTA handles one real objection
   plus "free consult, no obligation" as the risk reversal, never just "book now." Score each /10 against the Working
   Checklist, keep only **9.5+**, and list the rest with the reason (don't drop silently). Give each
   kept script an **actor spec**: age, gender, setting, emotion, wardrobe. Across the concepts in a
   campaign, vary the actors (age, gender, setting) so each one reaches its own avatar. AI UGC is
   our stand-in for a "creator army" (AdsMastery 2027 section). Apply the "Who can say
   what" guardrails above: the actor voices the situation and the offer's facts, **never** a
   results claim or a patient story.
3. **Actor still (Nano Banana Pro), then approval:**
   `generate_creative.py image "<actor spec + setting + 'vertical front-camera selfie frame,
   natural skin texture, realistic smartphone quality, no text'>" --model nano-banana-pro
   --aspect 9:16 --out work/actor-<x>.png` (~$0.15). Add `--ref <file>` to hold a product, place or
   outfit exactly. **Review the still before any video**: hands, face, wardrobe, background text.
   Fix with a new prompt now, because fixing a still is much cheaper than a video. Dylan approves it
   (visual gate) before any Veo call, unless he's said in this conversation to run it end to end.
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
   **Also run the angle flywheel:** propose rebuilding the winning *angle* in the other pillars (a
   static and an in-house/founder take), so the angle doesn't depend on one format that will
   fatigue. Bring the proposals to Dylan at the brief gate.

---

## After Generating

Per the ratio-flip principle: don't default to offering another iteration on the same concept. Instead
ask whether Dylan wants to (a) generate more distinct new concepts (the default next step, while
nothing has proven itself yet), or (b) — only once he's told you a specific concept is actually
performing — start iterating variations on that one winner.
