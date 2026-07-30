# Weekly AI Blog Skill

Writes DigiGrowth's weekly blog post — how AI helps independent service-based businesses win more
clients — for digigrowthllc.com's `/blog`. Value-first, not sales-y. Can share a weekly topic and
research with the newsletter (`apptset-agent/.claude/skills/newsletter/SKILL.md`) when their
schedules happen to overlap, so the two pieces of content don't duplicate research effort — but
since the blog runs Wednesdays and the newsletter runs Monday/Friday, that overlap is rare; most
weeks this skill runs its own research.

---

## Trigger

Delegated by the daily-briefing skill's Wednesday Step 4.6. Can also be triggered manually ("write
this week's blog post").

---

## Before Writing

1. **Read `apptset-agent/weekly_research_cache.json`** for this week's topic and findings, in case
   the newsletter skill's Step 1.5 wrote it earlier today. Use this topic and findings — do not run
   a second web search — only when the file is fresh (today's date). In practice this is rare now
   (newsletter runs Monday/Friday, this skill runs Wednesday), so the fallback below is the normal
   path, not an edge case.
   - **Fallback (the normal case now)**: if the cache file is missing or stale (not today's date),
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
   reader's next question — contextual, not a CTA button. Write it as a real markdown link,
   `[link text](/path)` — the site parses this syntax and renders an actual clickable link; plain
   text like "see our FAQ: /faq" renders as literal unclickable text. **Do not** add a second CTA, a
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

Submit it for approval instead of publishing directly. This session's sandbox can't reach Railway
directly, so instead of calling `/api/approvals` over HTTP, drop a request file that a Railway-side
relay job (`pending_approvals_relay.py`, polled ~6:40am ET daily) picks up and turns into a real
Approve/Decline card. Write the file directly rather than inlining it in a shell one-liner — post
text contains quotes/apostrophes that are painful and error-prone to shell-escape inline:
```bash
mkdir -p content-agent/pending_approvals
cat > content-agent/pending_approvals/blog-YYYY-MM-DD.json <<'JSONEOF'
{
  "title": "<post title>",
  "summary": "<one-line summary>",
  "payload": {"post": <the post object above>}
}
JSONEOF
```
Push `content-agent/pending_approvals/blog-YYYY-MM-DD.json` to GitHub with `push_file()` from
`shared/github_sync.py` (or `git add`/`commit`/`push` directly if running with git access).

The post is **not** live yet — the backend only pushes it into `digigrowth-website`'s
`src/content/blog-posts.json` when Dylan clicks Approve on the resulting card, where he can expand
"View full draft" to read the whole post before deciding. Declining leaves it unpublished; nothing
further happens automatically.

Return this summary (the daily-briefing skill forwards it verbatim into the brief's
`## Blog Post Preview` section):
```
**Title:** [title]
**Slug:** [slug]
**Summary:** [one-line summary]

Draft saved and queued for approval — the Approve/Decline card will appear as a separate message in
this chat within a few minutes once Railway's relay job picks up this request.
```

---

## After Submitting

Log the post in `content-agent/memory.md` under "SEO Content": title, slug, topic, date, and
"pending approval" (update to "published"/"declined" once Dylan decides, if you're told the
outcome in a later turn).

Offer to repurpose the post's core point into a LinkedIn post (`/social-post`) or ad angle
(`/ad-copy`) — one idea, many formats.
