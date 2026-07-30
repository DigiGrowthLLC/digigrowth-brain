# Manage Content Agent

Gives the EA direct control over the weekly AI blog post (and content-agent generally) without
leaving the chat.

**Agent location:** `$(git rev-parse --show-toplevel)/content-agent/`

---

## File Map

| File | What it controls |
|---|---|
| `.claude/skills/weekly-ai-blog/SKILL.md` | Full weekly blog skill — topic/research reuse, writing structure, approval submission |
| `.claude/skills/seo-blog/SKILL.md` | General-purpose pillar/cornerstone SEO articles (separate from the weekly cadence) |
| `context/seo-keywords.md` | Content pillars and target keywords for `seo-blog` |
| `context/brand.md` | Target client, objections, value prop |
| `memory.md` | "SEO Content" log — every published/pending post: title, slug, topic, date, status |
| `../apptset-agent/weekly_research_cache.json` | Shared topic + research written by the newsletter skill, read by `weekly-ai-blog` — only fresh (today's date) on newsletter days, so in practice this is rare now that the blog runs Wednesdays and the newsletter runs Mon/Fri |
| `../digigrowth-website/src/content/blog-posts.json` | Live blog content — only updated on Approve, via the dashboard's `/api/approvals` endpoint |

---

## Run Commands

```bash
# Write this week's blog post manually (outside the Wednesday automation)
cd "$(git rev-parse --show-toplevel)/content-agent" && # then trigger the weekly-ai-blog skill in chat
```

There's no standalone script — `weekly-ai-blog` is a skill the agent follows inline (same pattern as the newsletter skill), not a Python script.

---

## Common Tasks

### Draft this week's blog post manually
Follow `weekly-ai-blog/SKILL.md`. It reads `weekly_research_cache.json` for the shared topic/research if the newsletter step already ran today; otherwise it runs its own single search.

### Check what's pending approval
Ask the dashboard: `GET /api/approvals` isn't built as a list endpoint yet — check the most recent Wednesday's `## Blog Post Preview` section in `reports/daily-briefing-YYYY-MM-DD.md`, or look for `[[APPROVAL:<id>]]` markers in recent content-agent chat history.

### Check publish status
Read `content-agent/memory.md`'s "SEO Content" log, or check `digigrowth-website/src/content/blog-posts.json` directly (only updated posts that were actually approved appear there).

### Add a new SEO pillar/keyword
Edit `content-agent/context/seo-keywords.md`.

---

## Current Standing Directives

*Dylan updates this section to give ongoing orders to the EA about this agent.*

- Blog post drafts every Wednesday automatically as part of the daily briefing
- Never auto-publish — always submit for approval and wait for Dylan's decision
- Shares research with the newsletter when the cache happens to be fresh (rare now, since the newsletter runs Mon/Fri and the blog runs Wednesday) — otherwise runs its own single search, which is the normal path now

---

## Security

Secrets live in the shared `digigrowth` Doppler vault (config `prd`), not a local `.env` file — never read aloud, never edit directly.
