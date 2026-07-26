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
4. **Intro** (2-3 short paragraphs) — Promise → Proof → Path: name the real problem in the reader's
   own language, establish why this is worth reading, set expectations for what follows.
5. **Body — 2-4 H2 sections** — one subtopic per section, built from a list, steps, or a story (mix
   freely). Ground at least one section in a concrete finding from the research cache (a real
   stat/fact, not a vague claim). Short paragraphs, no fluff, no hard sell.
6. **One natural in-body link** back to the main site (e.g. to `/faq` or `/`) where it fits the
   reader's next question — contextual, not a CTA button. **Do not** add a second CTA, a
   newsletter-signup pitch, or a booking pitch inside the body — research on blog CTA conversion
   backs one primary CTA per page, and that CTA is the page's `<CTA />` component, not the post text.
7. **Word count**: 500-1000 words.

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
  "intro": ["paragraph", "paragraph"],
  "sections": [{"heading": "...", "paragraphs": ["...", "..."]}]
}
```

Submit it for approval instead of publishing directly:
```bash
curl -s -u "admin:$DASHBOARD_PASSWORD" -X POST \
  -H "Content-Type: application/json" \
  -d "{\"kind\":\"blog\",\"title\":\"<post title>\",\"summary\":\"<one-line summary>\",\"payload\":{\"post\":<the post object above>}}" \
  https://digigrowth-brain-production.up.railway.app/api/approvals
```

This returns `{"id": <n>, ...}`. The post is **not** live yet — the backend only pushes it into
`digigrowth-website`'s `src/content/blog-posts.json` when Dylan clicks Approve on the resulting
card (see the dashboard's approvals mechanism). Declining leaves it unpublished; nothing further
happens automatically.

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
