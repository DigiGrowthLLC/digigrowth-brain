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
2. **Avatar/angle** — who this specific ad is for, and the one angle it's built around (e.g. "PT
   clinic owners struggling to fill afternoon slots" — not "small business owners" broadly). If
   Dylan hasn't picked one, propose 2-3 narrow avatar/angle options per `context/ad-creative-
   principles.md`'s "go niche" guidance rather than defaulting to something broad.
3. **Format** — static image ad (default) vs. logo. Video creative is out of scope for this skill
   (delegate to `content-agent`'s `outreach-video`/`video-production` skills if a video ad is
   wanted — this skill is stills-first).

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
   - Write 1 primary version + 1 alternate hook (an iteration on the same avatar/angle, per the
     "go deep before you go wide" principle — not an unrelated angle).

3. **Generate the image.** Build an image prompt from the hook/avatar (the visual should make the
   avatar unmistakable at a glance — literally show the avatar or a strong visual metaphor for their
   situation, per the "put the avatar in the ad" principle). Run from `content-agent/`:
   ```
   python tools/generate_creative.py image "<prompt>" --aspect 1:1 --out "../media-buying-agent/outputs/<slug>/image.png"
   ```
   - Default `--aspect 1:1` for Feed; use `4:5` for a taller Feed/Reel-friendly crop, `9:16` for
     Stories/Reels — ask if unclear which placement this is for.
   - This writes `image.png` and a `image.png.meta.json` provenance sidecar automatically.

4. **Save the pairing** to `media-buying-agent/outputs/ad-<slug>-<YYYY-MM-DD>/`:
   - `copy.md` — avatar/angle, both copy versions, placement notes (mirrors `content-agent`'s
     `ad-copy` skill output format).
   - `image.png` + `image.png.meta.json` (from step 3).

5. **Report** the output folder path and run the Working Checklist from `context/ad-creative-
   principles.md` against what was produced — flag anything that doesn't clearly pass (e.g. no
   proof point available yet).

---

## After Generating

Offer to produce another iteration on the same avatar/angle (varying style/tone/proof per the
"iterate on winners" principle) rather than immediately jumping to a different avatar.
