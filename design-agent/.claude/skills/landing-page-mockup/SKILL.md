---
name: landing-page-mockup
description: Given one cold-outreach prospect's name/business, scrape their real website, build a personalized landing-page mockup (their own booking flow + a funnel/guarantee explainer), show it for approval, then publish and send the link. Use when Dylan says "run the landing page skill for X" or asks to build a personalized outreach page for a specific prospect.
---

# Landing Page Mockup

Turns one named cold-outreach prospect into a hosted, personalized landing page and a short outbound SMS — replacing the long pitch message that the SMS campaign report found causing most of the funnel's drop-off.

**Always run this for one prospect at a time, in the foreground.** Never background this skill — a prior incident in this codebase (leadgen-agent) saw a backgrounded batch job die silently; that's a standing rule here too.

**Never send anything without Dylan's explicit approval of the generated page.** Steps 1-4 always run; steps 5-6 only run after he says yes.

## Steps

1. **Look up the prospect.**
   ```bash
   python design-agent/tools/lookup_prospect.py "<name or business>"
   ```
   Gives you `contact_id`, `phone`, `website`, `owner`, and the existing `opener` (for reference — not required, this skill scrapes fresh). Stop and tell Dylan if no contact is found or there's no website on file.

2. **Scrape the prospect's real site.**
   ```bash
   python design-agent/tools/scrape_prospect_site.py "<website>" "<scratch_dir>"
   ```
   Produces `<scratch_dir>/page_text.txt` (extracted homepage/about/services/contact text — **read this closely for real testimonials/reviews**, not just service descriptions; most PT sites have patient quotes on the homepage or a reviews page, and those are real material, not something to invent). Also writes `<scratch_dir>/palette.json` (their real rendered button/header/heading colors — the actual values, not a guess) and `<scratch_dir>/assets.json`, which already contains their **logo and up to a few real content photos, pre-downloaded and embedded as base64 `data:` URIs** — read that file and splice the URIs directly into `<img src="...">` tags, don't re-fetch or hotlink the original CDN URLs (hotlinks are fragile — some sites block by referrer — and silently render blank in the Claude Artifact preview step 5 depends on, since its CSP blocks external images outright). Cap it at **at most 2 embedded photos** in the final page — more than that makes the page noticeably heavy for a cold-SMS tap-through; pick the ones that actually earn their place (a real in-session photo for the hero, one more if it strengthens a later section).

3. **Read `design-agent/references/funnel-best-practices.md` before writing anything.** This is a real step, every run — it encodes the structure/psychology rules (single focused intent, benefit-led headline, curiosity gap, stakes framing, no invented stats) this page needs to follow. Also read `design-agent/references/example-landing-page.html` — a real, Dylan-approved worked example (Foundation Physical Therapy) with every rule below actually applied: the section order, the visual seam, the funnel graphic + count-up script, the card-grid patterns, the exact CSS approach. Reuse its structure and the vanilla-JS reveal/count-up script; never reuse its specific copy, services, or reviews for a different business — re-derive all of that fresh from the new prospect's own scrape.

4. **Write the page.** This is your own reasoning, not a template fill — use the scraped text/colors and the reference file's guidance. The page always has exactly these six sections, in this order — this structure is fixed, not a suggestion:

   **Section 1 — The mockup (top, above the fold — but not just a hero banner).** This is a hyper-personalized extension of their *actual, existing* site — build it like a real, finished landing page, not a single centered block of text with their name dropped in. A real page has structure; this needs all of it:

   **Voice check, non-negotiable: every word in Section 1 is written as if you ARE the practice's own website, talking to a prospective patient.** It is never talking to the practice owner, never mentions DigiGrowth, "your practice," "your real services," "built for you," a pilot, a guarantee, or anything meta about this being a mockup. A real independent PT site sells *itself* to *patients* — pain points, the practice's actual approach, real services described the way a patient would want to hear them, real patient reviews. If a sentence in Section 1 could only make sense to the practice owner reading about their own business, it's wrong — rewrite it as if a patient is reading it. (A prior draft of this skill leaked lines like "Built around your real services, not a generic template" and "Real reviews from foundationptatl.com" directly into the patient-facing mockup — both are meta-commentary addressed to the practice owner, and both are bugs. All practice-owner-facing/DigiGrowth framing belongs only in Sections 2-6, past the seam below.)
   - **A real header**: their logo (embedded, see step 2, sized generously — around 44-48px tall, not a cramped 30-something px icon) and a CTA button on the right. No nav links — a nav pointing at anchors inside a one-page mockup (or worse, at Section 3's DigiGrowth pitch) adds clutter without adding function here; keep the header to logo + CTA. Sticky is a nice touch, not required.
   - **Above the header, a small disclaimer bar is the very first thing anyone sees** — before any of the mockup. One line, unobtrusive (a thin dark bar, not a wall of text): says plainly that this is a preview of what DigiGrowth's AI Growth Engine could build for their business, then the mockup begins right below it. This sits outside Section 1's "pure patient voice" rule (see below) — it's explicitly DigiGrowth talking, on purpose, so nobody mistakes the mockup underneath for their real site.
   - **An asymmetric hero, not a centered column.** Two-column layout — headline/subhead/CTA on one side, a real photo (from `assets.json`) on the other — or another clearly composed layout. A single center-aligned paragraph stack reads as a placeholder, not a real landing page; don't default to it.
   - **Replicate their real offer**, not a paraphrase of it. Pull their actual headline structure, their actual free-consult/booking offer wording, and real specific details (services, specialties, phrases — from `page_text.txt`, never invented).
   - **A real services/features section** — pull 3+ of their actual services from the scrape into a proper multi-column grid (not a bullet list), each with a short real description.
   - **If the scrape found real testimonials/reviews, use them** — a dedicated reviews section with 2-3 real quotes (real names, real wording, from `page_text.txt`) is one of the strongest trust signals available and this is genuinely how good this section is currently landing when reviews exist. Don't skip this if the material is there.
   - **Use their exact extracted palette** from `palette.json` (button bg/text, header bg, heading color) as the real color system throughout this whole section — not an approximation. Fall back to a clean neutral only if the scrape genuinely found nothing usable — never fall back to DigiGrowth's own navy/blue here, this section has to read as theirs.
   - **Then add flare on top of their real palette** — hyper-modern, professionally finished, better-produced than a typical small-practice site: real depth (soft shadows, layered cards, a gradient built from *their* colors), confident modern type scale, generous spacing, hover states on cards/buttons. Aim for the production level of digigrowthllc.com's own site (subtle grid/dot background texture, a soft radial glow behind the headline, an accent-color gradient on key words) — don't undersell this, "wow" is the actual bar, not just "clean."
   - **Motion.** This isn't static. Add a lightweight scroll-reveal (a lone `IntersectionObserver` + a `.reveal`/`.reveal.in` opacity+translateY transition is enough — see `content-agent`'s brand system or DigiGrowth's own site for the level of polish to aim for) so sections fade/rise into view as the page scrolls, plus at least one subtle ambient animation in the hero (a slow-drifting gradient blob/orb via CSS `@keyframes`, or similar) — small, tasteful motion that makes the page feel alive, not a slideshow of effects.
   - No form on this section. The ask here is "look," not "convert."

   **Section 2 — What this is (1-2 sentences, no more).** A plain statement: this is a preview of the pilot program mentioned in the text, built specifically for [Practice Name]. Keep it correlated to the SMS wording (the send template in step 7 says "pilot program" for exactly this reason) — no disconnect between what was promised and what they're looking at. This is also where the system gets named: **DigiGrowth's real product name is "the AI Growth Engine"** (this is the actual name used on digigrowthllc.com's own homepage, not invented) — introduce it here with a small badge/kicker, then keep threading that name through Sections 3 and the guarantee callout below, so the whole pitch reads as one named system rather than a generic "we help PT practices" pitch.

   **Section 3 — The funnel breakdown, as an actual graphic.** This is a visual demonstration for the practice owner, in **their patients'** perspective — not DigiGrowth's own outreach funnel for finding the practice. Get the framing right: it's "impressions -> engagement -> qualified leads -> 10-20 booked consultations" (use those exact stage names — they're the vocabulary the practice owner will recognize from any ad/marketing funnel), never "outreach touches to practices" (that's a different funnel — how DigiGrowth found *them* — and doesn't belong on their page). Frame it explicitly as the AI Growth Engine's output (see Section 2) — e.g. "Here's what the AI Growth Engine typically delivers," not a generic unnamed process.
   - **Build a real narrowing funnel graphic**, not a bulleted list of rows. A shrinking-width bar/trapezoid stack, or an SVG funnel shape, with each stage sized roughly proportional to its number — something that visually reads as "funnel" at a glance, the way an actual funnel diagram would in a real sales deck.
   - **Animate the numbers on scroll** (count up from 0 to the real value once the section enters view, via the same `IntersectionObserver` already driving the reveal animations — trigger a short count-up tween on intersection, no animation library needed for a simple number tween).
   - Frame the stage numbers as typical/expected ranges based on independent-PT-practice patterns, worded so they read as illustrative, not a sourced statistic or a guarantee — only the final 10-20 booked-consultations figure is DigiGrowth's actual stated guarantee; the earlier stages are reasoned estimates, not a documented industry benchmark (none exists — see `references/funnel-best-practices.md`), so word them accordingly (e.g. "typically looks something like" not "X% of patients"). Keep the final bar's label to just "consultations booked" — don't also append "guaranteed" there, since the dedicated guarantee callout right after already owns that word; repeating it in the graphic undercuts the callout's impact.
   - **Pull in real persuasion/social-proof elements from digigrowthllc.com** where they're genuinely true and relevant (e.g. real stat badges DigiGrowth's own live site displays — response-time, automation, guarantee framing) — reinforcing, not duplicating, Section 3's numbers. Never fabricate a stat that isn't actually stated somewhere real (DigiGrowth's own site or its stated guarantee).
   - Center the section's heading and subtext (this is a headline moment, not a left-aligned paragraph), and skip small gray disclaimer/footnote lines under the graphic or trust badges — the "typical ranges, not a guarantee" framing belongs in the sentence copy itself (see wording above), not as a separate muted caption underneath. This centering default applies to every heading+intro-paragraph block past the seam, not just this section — a left-aligned section-head inside an otherwise-centered page reads as an inconsistency, not a deliberate style choice. Only break from centered with a real reason (e.g. a genuine two-column layout).

   **After the guarantee callout, add a "the partnership" section — DigiGrowth's scope, still vague on mechanism.** This is broader than the guarantee: it's the case for why this is a long-term relationship, not a one-time lead drop. Cover, in DigiGrowth's own voice this time (past the seam, so this is fine): (1) full-funnel control — one system runs generating demand through getting it booked, not a lead list handed off; (2) partnership past the booking — staying involved to improve lead quality, tighten close rates, and grow lifetime value over time; (3) the actual goal is capturing as much of the practice's local market digitally as it can handle, not a single good month. Branded to the AI Growth Engine like everything else past the seam. Stay vague on *how* (no channels, scripts, or tactics named — same discipline as the curiosity-gap section below) while being direct about *what* DigiGrowth's scope actually is.

   **Section 4 — Why it's free (short, addresses the obvious objection).** One or two sentences on why this is a no-cost pilot — building case studies in the niche before rates go up, in exchange for a testimonial once results land. Preempts the "what's the catch" reaction before it becomes an objection.

   **Section 5 — The curiosity gap.** Do not fully explain the outreach method, script, or exact channels. Reference that there's a real system behind the funnel numbers without detailing it — e.g. "the outreach sequence and scripts that drive this are built per-practice" without showing them. This is a deliberate incomplete reveal: enough that the numbers in Section 3 read as backed by something real, not enough that a prospect could reverse-engineer it or feel like they already got the whole thing for free.

   **Section 6 — Single CTA.** One action, no menu of options: book a short call to review their specific practice's numbers and get set up for the pilot. One button/link only, linking to `https://calendly.com/dylanrg-digigrowthllc/30min` — every additional choice is friction. Keep this a real booking link, not a "message us" prompt — by this point in the page someone has scrolled through the full pitch, which makes them a warmer, higher-intent visitor than the cold SMS tap; a specific calendar slot converts better here than reopening a reply-and-wait loop, and it matches what both Foundation PT's own real site and digigrowthllc.com already do at this stage. Add a small scarcity line right under the button — spots-remaining framing (e.g. "We're only taking on 3 practices for this program this month") — a subtle pulsing dot or similar small accent is a nice touch, not required.

   **Every section below Section 1 must visibly announce itself as a new section.** Don't let Sections 2-6 blend into one continuous scroll of paragraphs — each one needs its own small eyebrow/kicker label naming its role (e.g. "WHAT THIS IS", "HOW IT TYPICALLY PLAYS OUT", "WHY IT'S FREE") and a clear visual break from the section before it (a background-color shift, a divider, a change in card treatment) so someone scrolling — or Dylan reviewing — can tell at a glance which of the six sections they're looking at and why it's there.

   **The seam between Section 1 and Section 2 needs an explicit, unmissable marker — not just a color change.** Section 1 is a mockup of *their* page; someone looking at it shouldn't have to guess where the mockup stops and DigiGrowth's actual pitch to them begins. Put a real banner at that exact seam — literal text to that effect (e.g. "PREVIEW ENDS HERE" — write your own version, but the meaning must be explicit), visually distinct from every other divider on the page. Keep this banner to the tag line alone — no smaller gray explanatory subtext underneath it; the tag itself should carry the meaning.

   **Somewhere in Sections 3-4, add one dedicated, prominently-styled guarantee/risk-reversal callout — don't leave the guarantee as just one line inside the funnel graphic.** Brand it as **the AI Growth Engine's** guarantee, not a generic promise — same named-system thread as Sections 2-3. This is the actual close of the pitch and should be pushed hard, not undersold: a bold headline restating the 10-20 number, then a short checklist (2-3 items, each with a checkmark) explicitly covering: (1) if the guarantee isn't hit, DigiGrowth keeps working for free until it is — no renegotiation, (2) DigiGrowth's service fee is waived on their end for the pilot — the practice pays nothing, no fee/card/catch (say it as "the fee is waived on our end," not "zero cost to run" — the framing is DigiGrowth absorbing the cost, not the engagement having none; the supporting line should say plainly "you don't pay us anything — we work for free until your results are hit," tying the waived fee directly back to guarantee item (1) rather than treating them as unrelated points), (3) DigiGrowth stands behind the results — there's no version of this where the practice doesn't come out ahead of where it started. Give it its own high-contrast block (e.g. the dark/ink treatment, not blended into a lighter section) so it reads as the moment the pitch commits to something concrete.
   - **Lay the checklist out as equal-width cards in a row (a grid), not a left-aligned stack of lines.** A ragged left-aligned list under a centered headline reads visually unbalanced — a symmetric 2-3-column card grid (icon/checkmark on top, bold micro-headline, then a short supporting line, all center-aligned within each card) reads as a deliberate, finished layout instead. The same applies to the partnership section's cards below — give them real depth (a gradient icon badge, a hover lift + shadow, a subtle background glow behind the section) rather than plain bordered boxes; flat cards read as unfinished next to the rest of the page's polish.

   Despite all of the above, keep the page purposeful, not bloated — a curiosity planter for a cold prospect, not a sales page for a warm lead. Mobile-first. "Lightweight" here means inline CSS and a handful of lines of vanilla JS for the scroll-reveal/ambient motion (no React/Vue/animation library) — it does not mean skipping structure or motion; a well-built single-file page with two embedded photos loads plenty fast on a modern connection.
   The generated HTML **must** contain a literal `<head>` and `</body>` tag (the serving router injects OG meta tags after `<head>` and a tracking snippet before `</body>` — see `dashboard/backend/routers/landing_pages.py`).
   Save the full HTML to a scratch file, e.g. `<scratch_dir>/page.html`.

5. **Show Dylan the page for approval.** Publish the generated HTML file as a Claude Artifact (this renders it inline in the session) so he sees the actual result — not a description of it. **Stop here and wait for his explicit yes.** Do not proceed to step 6/7 without it. If he asks for changes, revise and re-show — don't publish/send a version he hasn't actually seen.

6. **On approval, publish for real.**
   ```bash
   python design-agent/tools/publish_landing_page.py "<slug>" "<scratch_dir>/page.html" "<business name>" "<contact_id>" "<scratch_dir>/hero.png"
   ```
   Pick `<slug>` as a clean, readable business-name slug (e.g. `elite-performance-pt`) — collisions upsert, so re-running for the same business updates the same page rather than erroring. Omit the hero image argument entirely if step 2's screenshot wasn't used in the final design. This prints the final URL (once `LANDING_PAGES_URL` is set in Doppler — see the "branded subdomain" note in this skill's Open Items) or the bare `/lp/<slug>` path otherwise.

7. **Send the link.**
   ```bash
   python design-agent/tools/send_landing_page_sms.py "<phone>" "<first name>" "<business name>" "<url>" "<slug>"
   ```
   This checks the URL actually resolves (HTTP HEAD, non-4xx/5xx) before sending anything — refuses and exits if it doesn't, so a DNS/cert hiccup on the branded subdomain can never result in texting a broken link to a real prospect. Once that check passes, it sends the short, locked message ("mocked up what the pilot program could look like for [Practice]...") and marks the page `sent`. It says "pilot program" deliberately — Section 2 of the page refers back to that exact phrase, so the two need to match. It **replaces** the sequence's long `curiosity_opener` pitch for this prospect — don't also send the long pitch through the normal sequence flow for anyone run through this skill.

8. Save a short completion note to `design-agent/outputs/landing-page-<slug>-YYYY-MM-DD.md` (today's full 4-digit year) and end with the completion message.

## Setup note — the branded subdomain

`pages.digigrowthllc.com` is registered as a Railway custom domain for the `digigrowth-brain` service (done 2026-09-12, `railway domain pages.digigrowthllc.com --service digigrowth-brain`), and `LANDING_PAGES_URL` is already set to `https://pages.digigrowthllc.com` in the shared Doppler vault — every tool in this skill picks it up automatically once it resolves.

DNS for `digigrowthllc.com` is on Cloudflare. The domain won't actually resolve until these two records are added there (Dylan's action, not something this skill's code can do):

| Type | Name | Value |
|---|---|---|
| CNAME | `pages` | `upqh2hil.up.railway.app` |
| TXT | `_railway-verify.pages` | `railway-verify=de3ff6f6d71e4e81c8b7c88684849f7b6f4ff6742aaabe4f9cfc3b9175e41904` |

Set the CNAME to DNS-only (grey cloud, not Cloudflare-proxied) — Railway needs a direct connection to issue the SSL cert and validate ownership; it can be switched to proxied later once the cert issues. Check `railway domain status pages.digigrowthllc.com` for current verification/certificate state. Until it's verified, `publish_landing_page.py` still works — it just won't have `LANDING_PAGES_URL` resolve to anything reachable yet, so double-check `railway domain status` shows `Verified: yes` before actually texting a link to a real prospect.

**Volume discipline once it's live:** a brand-new subdomain has no reputation history with carriers yet. Don't run it at full campaign volume on day one — ramp it in alongside whatever's already sending, and watch Twilio Messaging Insights (delivery/error rates, especially error code `30007` = carrier filtering) for the first several days of real sends through it.

## What This Skill Does NOT Do

- Doesn't touch the base `sms_sequences` table or its templates — this is a locked, explicit-stage send, same bypass pattern as the outreach-video skill's Loom send.
- Doesn't fabricate statistics or testimonials as sourced fact. Section 3's funnel-stage numbers (impressions -> engagement -> qualified leads) are explicitly illustrative/typical ranges, worded that way — only the final 10-20 booked-consults figure is DigiGrowth's real, stated guarantee.
- Doesn't auto-send anything — the approval gate in step 5 is not optional.
- Doesn't batch multiple prospects in one run — one at a time, by name, every time.

## Completion Message

```
Landing Page Mockup complete — <business> — YYYY-MM-DD
Slug: <slug>
URL: <final url or /lp/<slug> path>
Sent to: <phone>
```

If Dylan didn't approve (revised and re-shown, or declined entirely):
```
Landing Page Mockup — <business> — not sent
Reason: [awaiting revision / declined / other]
```
