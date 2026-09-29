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
   different subject. Video creative is out of scope for this skill (delegate to `content-agent`'s
   `outreach-video`/`video-production` skills if a video ad is wanted — this skill is stills-first).
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

## After Generating

Per the ratio-flip principle: don't default to offering another iteration on the same concept. Instead
ask whether Dylan wants to (a) generate more distinct new concepts (the default next step, while
nothing has proven itself yet), or (b) — only once he's told you a specific concept is actually
performing — start iterating variations on that one winner.
