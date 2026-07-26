# SEO Blog Skill

Write long-form, SEO-targeted blog/authority articles for DigiGrowth, aimed at ranking on
digigrowthllc.com and driving organic traffic from service-based business owners.

---

## Trigger

Any request containing: "blog", "blog post", "SEO article", "SEO content", "authority article",
"long-form"

---

## Before Writing

1. Check `context/seo-keywords.md` for the content pillar and target keyword — if Dylan hasn't
   specified one, pick the next un-covered pillar and confirm with him.
2. Check `context/brand.md` for the target client, objections, and value prop — every post should
   speak to the broad service-business audience (not fitness-only) unless Dylan explicitly asks for
   a vertical-specific piece.
3. Check `memory.md` for posts already published on this pillar/keyword to avoid duplicating angles.

---

## Structure (every post)

1. **Title** — includes the primary keyword naturally, reads like something a business owner would
   click, not a keyword-stuffed headline.
2. **Meta description draft** — 150-160 chars, includes the primary keyword, ends with an implicit
   or explicit reason to click.
3. **H1** — matches the title's promise (should differ slightly from `<title>` for natural variation).
4. **Intro (2-3 short paragraphs)** — Promise → Proof → Path (see `context/brand-strategy.md`'s 3 P's
   hook framework). State the reader's problem in their own language before offering the answer.
5. **Body — H2 sections** — one H2 per subtopic, built from a list, steps, or a story (the only 3
   content formats — mix freely). Use short paragraphs, bullet lists where useful, no walls of text.
6. **Internal links** — link to `/pricing`, `/faq`, or `/contact` where it's a natural fit for the
   reader's next step — don't force it into every section.
7. **CTA close** — one clear next action ("Book a free strategy call"), consistent with the
   give:ask separation rule: the body stays all give, the CTA is the only ask.
8. **Word count** — 800-1500 words for pillar/cornerstone posts; shorter (500-800) is fine for
   narrower long-tail posts.

---

## Voice & Tone

Follow the content-agent voice rules: direct, confident, outcome-focused, no fluff, no buzzword
soup, no exclamation points for emphasis. Write for a busy, skeptical, numbers-driven reader —
same as ad copy and email sequences.

---

## After Writing

1. Save to `outputs/blog-post-[slug]-YYYY-MM-DD.md` with the meta description and target keyword
   noted at the top of the file (frontmatter-style) so it can be copied into `digigrowth-website`'s
   blog content later.
2. Log the post (title, pillar, keyword, date) in `memory.md` under "SEO Content".
3. Offer to repurpose the post's best point into a LinkedIn post (`/social-post`) or ad angle
   (`/ad-copy`) — one idea, many formats.
