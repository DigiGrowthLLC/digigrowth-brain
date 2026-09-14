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

3. **Generate the image(s).** Build an image prompt from the hook/avatar/format of each concept (the
   visual should make the avatar unmistakable at a glance — literally show the avatar or a strong
   visual metaphor for their situation, per the "put the avatar in the ad" principle; vary the visual
   *format/style* across concepts too — e.g. one clean product/lifestyle still, one native-style
   "screenshot-like" high-curiosity still — not the same visual template restated). For each concept,
   run from `content-agent/`:
   ```
   python tools/generate_creative.py image "<prompt>" --aspect 1:1 --out "../media-buying-agent/outputs/<slug>/image.png"
   ```
   - Default `--aspect 1:1` for Feed; use `4:5` for a taller Feed/Reel-friendly crop, `9:16` for
     Stories/Reels — ask if unclear which placement this is for.
   - This writes `image.png` and a `image.png.meta.json` provenance sidecar automatically.

4. **Save each concept's pairing** to its own `media-buying-agent/outputs/ad-<slug>-<YYYY-MM-DD>/`:
   - `copy.md` — avatar/angle, format, the copy, placement notes (mirrors `content-agent`'s
     `ad-copy` skill output format).
   - `image.png` + `image.png.meta.json` (from step 3).
   - When producing multiple new concepts in one request, use a distinct `<slug>` per concept so
     they land in separate folders — never merge distinct concepts into one folder.

5. **Report** all output folder paths and run the Working Checklist from `context/ad-creative-
   principles.md` against what was produced — flag anything that doesn't clearly pass (e.g. no
   proof point available yet, or a "new concept" batch that's actually just iterations in disguise).

---

## After Generating

Per the ratio-flip principle: don't default to offering another iteration on the same concept. Instead
ask whether Dylan wants to (a) generate more distinct new concepts (the default next step, while
nothing has proven itself yet), or (b) — only once he's told you a specific concept is actually
performing — start iterating variations on that one winner.
