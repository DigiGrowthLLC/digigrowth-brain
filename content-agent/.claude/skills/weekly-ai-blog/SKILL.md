# Weekly AI Blog Skill

Writes DigiGrowth's weekly blog post — how AI helps independent service-based businesses win more
clients — for digigrowthllc.com's `/blog`. Value-first, not sales-y. Shares the same weekly topic
and research as the newsletter (`apptset-agent/.claude/skills/newsletter/SKILL.md`) so the two
pieces of content don't duplicate research effort.

---

## Trigger

Delegated by the daily-briefing skill's Monday Step 4.6, after the newsletter step (4.5) has
already run. Can also be triggered manually ("write this week's blog post").

---

## Before Writing

1. **Read `apptset-agent/weekly_research_cache.json`** for this week's topic and findings (written
   by the newsletter skill's Step 1.5, moments earlier in the same Monday run). Use this topic and
   findings — do not run a second web search when this file is fresh (today's date).
   - **Standalone/manual run fallback**: if the cache file is missing or stale (not today's date),
     pick the next topic from the newsletter skill's Topic Rotation List that doesn't match
     `content-agent/memory.md`'s "SEO Content" log, then run one web search yourself before writing.
2. Check `context/brand.md` for the target client (independent service-based businesses broadly,
   not fitness-only) and objections.
3. Check `content-agent/memory.md`'s "SEO Content" log to avoid repeating a topic/angle already
   covered.

---

## Structure

Per `context/brand-strategy.md`'s give:ask separation rule — the body is all give, the only ask is
the CTA that's already built into the site's `<CTA />` component (not part of this post's body).

1. **Title** — reads like something a business owner would click; includes the topic naturally.
2. **Meta description** — 150-160 chars.
3. **Slug** — kebab-case, derived from the title.
4. **Thumbnail icon** — pick one keyword from `speed`, `reactivation`, `funnel`, `followup`, `ai`
   (default `ai` if nothing else fits) that best represents this post's topic — used for the
   thumbnail graphic on the blog index. See the post object schema below.
5. **Intro (2-3 short paragraphs) — lead with a story, not a stat.** Put the reader in a specific,
   concrete scene of the problem: a named-feeling moment ("a lead fills out your form at 9pm..."),
   not an abstract claim ("many businesses struggle with..."). Write it like you're describing their
   Tuesday, not a market trend. Promise → Proof → Path still applies underneath the story: the scene
   *is* the promise (this is about you), the specificity *is* the proof (I understand your exact
   situation), and the shift into "here's what actually fixes it" *is* the path.
6. **Body — 2-4 H2 sections** — one subtopic per section, built from a list, steps, or a story (mix
   freely). Ground at least one section in a concrete finding from the research cache (a real
   stat/fact, not a vague claim). Keep threading the reader's specific situation through each
   section — don't drift into generic industry commentary. Frame the solution as personal: not
   "businesses can use AI to..." but "here's what changes for you specifically when..." Short
   paragraphs, no fluff, no hard sell.
7. **One natural in-body link** back to the main site (e.g. to `/faq` or `/`) where it fits the
   reader's next question — contextual, not a CTA button. **Do not** add a second CTA, a
   newsletter-signup pitch, or a booking pitch inside the body — research on blog CTA conversion
   backs one primary CTA per page, and that CTA is the page's `<CTA />` component, not the post text.
8. **Word count**: 700-1200 words — the story/personal-solution framing needs more room to breathe
   than a pure listicle would.

---

## Voice & Tone

Direct, confident, outcome-focused — same voice rules as the rest of content-agent. No exclamation
points for emphasis, no buzzword soup, no vague superlatives.

---

## Publish (submit for approval — do not auto-publish)

Build the post object:
```json
{
  "slug": "kebab-case-slug",
  "title": "...",
  "metaDescription": "...",
  "date": "YYYY-MM-DD",
  "thumbnailIcon": "speed | reactivation | funnel | followup | ai",
  "intro": ["paragraph", "paragraph"],
  "sections": [{"heading": "...", "paragraphs": ["...", "..."]}]
}
```

Submit it for approval instead of publishing directly. Write the request body to a temp file first
rather than inlining it in the `curl` command — post text contains quotes/apostrophes that are
painful and error-prone to shell-escape inline:
```bash
cat > /tmp/approval_payload.json <<'JSONEOF'
{
  "kind": "blog",
  "title": "<post title>",
  "summary": "<one-line summary>",
  "payload": {"post": <the post object above>}
}
JSONEOF
curl -s -u "admin:$DASHBOARD_PASSWORD" -X POST \
  -H "Content-Type: application/json" \
  -d @/tmp/approval_payload.json \
  https://digigrowth-brain-production.up.railway.app/api/approvals
```

This returns `{"id": <n>, ...}`. The post is **not** live yet — the backend only pushes it into
`digigrowth-website`'s `src/content/blog-posts.json` when Dylan clicks Approve on the resulting
card, where he can expand "View full draft" to read the whole post before deciding (see the
dashboard's approvals mechanism). Declining leaves it unpublished; nothing further happens
automatically.

Return this summary (the daily-briefing skill forwards it verbatim into the brief's
`## Blog Post Preview` section):
```
**Title:** [title]
**Slug:** [slug]
**Summary:** [one-line summary]

[[APPROVAL:<id>]]
```
The `[[APPROVAL:<id>]]` line is a literal marker — the OS chat frontend detects it and renders live
Approve/Decline buttons. Replace `<id>` with the id returned above. Do not add a link, description,
or any other text around it.

---

## After Submitting

Log the post in `content-agent/memory.md` under "SEO Content": title, slug, topic, date, and
"pending approval" (update to "published"/"declined" once Dylan decides, if you're told the
outcome in a later turn).

Offer to repurpose the post's core point into a LinkedIn post (`/social-post`) or ad angle
(`/ad-copy`) — one idea, many formats.
