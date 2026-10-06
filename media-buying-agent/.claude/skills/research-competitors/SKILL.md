# Research Competitors Skill

Scan the live Meta Ad Library (plus published best-practice guides) for a vertical, and log what's
actually working — the structural patterns competitors are spending the most on — as reusable
knowledge. Standalone: doesn't require writing a full campaign plan. Use it just to build up
`ad-creative-principles.md`, to sanity-check a client's current creative against the market, or as a
first pass before `build-campaign-plan` (which calls this skill as its own research step).

---

## Trigger

A request to research competitors, check the Meta Ad Library, see what's performing well in a
vertical, or "see what we can replicate" — without necessarily wanting a full campaign plan out the
other end. Also invoked internally by `build-campaign-plan` step 2.

---

## Inputs Needed

Ask if not already given:
1. **The vertical or niche** to research (e.g. "physical therapy / chiropractic," "SMMA," "local
   HVAC"). If this is for a specific existing client, use their vertical + geo, not a generic category.
2. **Optional: a specific client** — if given, cross-check findings against that client's actual
   brand-voice rules/positioning (pulled from `GET /api/clients/{id}` → `onboarding` object) so the
   output flags tone mismatches, not just structural patterns to copy wholesale.

---

## The bar: at least 10 proven ads (Dylan, 2026-10-06)

Every run must end with **at least 10 proven ads**, each with its **verbatim copy** captured. An ad
counts as proven only if it is **still active today AND started running 6+ months ago**. A
long-running active ad is one an advertiser has kept paying for, which is the closest public signal
of performance the Ad Library offers. Newer ads, inactive ads, and one-off gimmicks don't count
toward the 10, however good they look.

These 10 are the raw material for the rest of the pipeline: `build-campaign-plan` ties each of its
10 concepts to one of them, and `generate-ad` writes each approved ad's 3 copy variations from
their copy. So the copy has to be captured word for word, not summarized.

## Steps

### 0. Collect proven ads with the Meta connector (`mcp__meta-ads__ads_library_search`)

Load it via ToolSearch. It returns each ad's creative text, page name, start/creation date and
snapshot URL, but can't filter by date or sort by reach, so:
- Run several searches with `ad_active_status: "ACTIVE"`, `countries: ["US"]`, `limit: 50`: the
  vertical's core keywords, the client's specific services/conditions (e.g. "physical therapy",
  "back pain", "dry needling", "sports injury"), and named direct competitors (`page_ids` when known).
- Keep only ads whose start date is **6+ months before today**. Dedupe near-identical copies from
  the same advertiser (count the concept once, note how many variants they run, which is itself a
  signal).
- **Under 10?** Widen in this order: more keywords and conditions, the same vertical in other US
  cities/regions, then adjacent verticals with the same buyer and offer type (e.g. chiropractic and
  sports medicine for a PT client). Never pad the list with ads under 6 months old. If 10 truly
  can't be found, stop and say how many were found and where you looked.
- For each proven ad, open the `ad_snapshot_url` (playwright) when the text alone doesn't show the
  format (video vs. static vs. carousel) or the on-screen hook.

### 1. Browse the live Meta Ad Library with `playwright` MCP tools

Run two passes, not just one:
- **Vertical keyword search:**
  ```
  mcp__playwright__browser_navigate →
  https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=US&media_type=all&q=<vertical keywords>&search_type=keyword_unordered&sort_data[mode]=total_impressions&sort_data[direction]=desc
  ```
- **Named direct-competitor search** (if 1-2 direct competitors are known for the client/vertical —
  ask if not given): search the Ad Library for that specific advertiser's page/name instead of a
  keyword, sort the same way. This surfaces which of *that one brand's* ads are actually working,
  a sharper signal than a generic keyword search alone.

Sorting by `total_impressions` surfaces the ads competitors are actually spending the most on. Also
check "Started running on <date>" — but treat it as a soft signal, not absolute: a very long run (a
year+) is a strong validated-winner signal, while an ad that only started ~a month ago **could
already be fatiguing** rather than still working — recency of *continued* activity matters as much as
raw start date. `browser_snapshot` on this page is large (100k+ tokens) — it gets saved to a file
automatically; read that file in chunks via `Read`/`Grep` rather than requesting it inline.

Note: Ad Library creative images are frequently watermarked "Protected," which blocks most AI image
tools from doing anything useful with a direct copy of the file. Document the **structural pattern in
words** (layout, proof placement, copy structure) rather than assuming the raw image itself can be
handed to `generate-ad` as a usable reference asset.

Look for **repeated structural patterns across unrelated advertisers** in the vertical — that's the
signal, not any single ad. Note per finding:
- The structural pattern itself (opener format, offer mechanic, proof format, CTA style, creative
  format — static vs. talking-head video vs. carousel).
- How many unrelated advertisers repeat it, and how long the ads have been running *and* whether
  they're still actively running now (both matter — see the fatigue caveat above).
- Anything that's clearly one advertiser's one-off gimmick, not a pattern (skip these).

**Optional supplementary pass:** cross-category patterns (structural trends working broadly across
unrelated categories, not just this vertical — e.g. "value stacking," a specific lighting/photo style)
are often an early signal worth testing before they're common in any one specific vertical. Worth a
few extra minutes of browsing outside the exact niche when time allows, noted separately from the
vertical-specific findings.

### 2. Cross-check with published best-practice guides

Run 2-3 `WebSearch` queries for published best-practice content on the same vertical, to catch
budget/CPL benchmarks, follow-up-speed stats, or structural advice the live sample might have missed
(a small live sample can be skewed by whoever happens to be spending heavily right now). Structure the
ask around these four questions specifically, rather than a vague "what's working" search — it
produces more organized, directly usable findings:
1. Which **creative formats** are getting the highest impressions/engagement in this vertical right
   now (UGC talking-head vs. static vs. carousel vs. produced video)?
2. Which **hooks** (opening lines/frames) are driving the highest engagement?
3. Which **audience segments** are responding best, where stated?
4. What **creative patterns repeat** across multiple winning ads (ties back to the Ad Library
   structural-pattern findings from step 1 — use this to confirm or extend them)?

### 3. Separate structure from tone

**Judgment call, every time:** a pattern that's proven to convert (e.g. urgency/scarcity, a discount
voucher) can still be wrong for a specific client if it contradicts that client's own stated
positioning (e.g. "individualized, no-pressure" care shouldn't borrow a "$49, only 30 spots left"
mechanic). If a client was given as input, explicitly check each finding against their
`onboarding.differentiation_voice` rules. Always call out *structure* (what to borrow) separately from
*tone* (match to the client) — never just paste the winning template as-is.

### 4. Save the proven ads file

Write `context/proven-ads/<vertical-slug>.md` (create the folder if needed). If the file exists,
re-verify each entry is still active, drop dead ones, and add new ones, keeping the date it was last
checked at the top. One entry per proven ad, numbered P1, P2, ... so plans and ads can cite them:

```
## P1 · <Advertiser> · <city/region if shown> · running since <YYYY-MM-DD> (<N> months) · <format>
Snapshot: <ad_snapshot_url>
Variants running: <n>
Primary text (verbatim):
> <full text, line breaks kept>
Headline (verbatim): <...>   CTA button: <...>
Hook: <first line / first 3 seconds on screen>
Copy structure: <e.g. city callout → pain question → mechanism → proof → offer → CTA>
Offer: <...>   Proof type: <review quote / stat / credential / before-after>
Borrow: <the structure worth reusing>   Don't borrow: <claims, offers or tone that clash with the client>
```

### 5. Append findings to `context/ad-creative-principles.md`

Per this agent's existing convention — add a new dated `## Source: Meta Ad Library Field Scan — <vertical> (YYYY-MM-DD)` section, never overwrite prior research. Note explicitly that findings are
vertical-specific, not universal. Structure like the existing Ad Library scan sections in that file:
dominant winning template, any notable sub-segment variation (e.g. "orthopedic/surgeon-tier ads skew
softer"), and an applicability note for tone-matching.

### 6. Report back

Lead with the proven-ads table (P#, advertiser, months running, format, hook, copy structure), then
the patterns. Summarize the findings directly in the conversation (the saved file is the durable record, but Dylan
shouldn't have to open it to see what was found). If this was run for a specific client, flag which
patterns are safe to use as-is vs. need a tone adjustment before informing any ad copy.

---

## After Researching

Ask whether to (a) hand off to `generate-ad` to produce creative using one of the validated patterns,
or (b) hand off to `build-campaign-plan` if this was really the first step toward a full client plan.
