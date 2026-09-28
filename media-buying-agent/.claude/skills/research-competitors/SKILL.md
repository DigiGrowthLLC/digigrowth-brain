# Research Competitors Skill

Scan the live Meta Ad Library (plus published best-practice guides) for a vertical, and log what's
actually working — the structural patterns competitors are spending the most on — as reusable
knowledge. Standalone: doesn't require writing a full campaign plan. Use it just to build up
`ad-creative-principles.md`, to sanity-check a client's current creative against the market, or as a
first pass before `build-campaign-plan` (which calls this skill as its own step 2).

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

## Steps

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

### 4. Append findings to `context/ad-creative-principles.md`

Per this agent's existing convention — add a new dated `## Source: Meta Ad Library Field Scan — <vertical> (YYYY-MM-DD)` section, never overwrite prior research. Note explicitly that findings are
vertical-specific, not universal. Structure like the existing Ad Library scan sections in that file:
dominant winning template, any notable sub-segment variation (e.g. "orthopedic/surgeon-tier ads skew
softer"), and an applicability note for tone-matching.

### 5. Report back

Summarize the findings directly in the conversation (the saved file is the durable record, but Dylan
shouldn't have to open it to see what was found). If this was run for a specific client, flag which
patterns are safe to use as-is vs. need a tone adjustment before informing any ad copy.

---

## After Researching

Ask whether to (a) hand off to `generate-ad` to produce creative using one of the validated patterns,
or (b) hand off to `build-campaign-plan` if this was really the first step toward a full client plan.
