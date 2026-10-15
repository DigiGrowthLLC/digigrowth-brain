# Patient Acquisition Blueprint (Foundations) — Exceptional Solutions PT — 2026-10-08

First Foundations-package blueprint (back-end only: no ads, no funnel, no guarantee).

- Prospect: Samantha Newell, DPT, Exceptional Solutions PT (chronic pain, hypermobility, EDS; Grand Rapids, MI; exceptionalsolutionspt.com), contact `68881152-2562-4587-94e9-c04f909c1984`. Discovery call 2026-10-08 2:30 PM.
- URL: https://pages.digigrowthllc.com/lp/exceptional-solutions-pt-blueprint
- Chat: tested live (hEDS + Priority Health, then "can I come in next week? evenings are best"): answered from her site, offered two simulated times. It said "Samantha has hEDS herself" (her site only says EDS), so chat_context now says not to name the type.
- Sent to prospect: no

## What's on the page
00 system overview (sources: database reactivation, new inquiries from web/Google/referrals, missed calls) → 01 AI agent (live chat, books her initial evaluation, insurance-billed or the $90 grand opening eval) → 02 database reactivation → 03 nothing leaks → 04 "The Foundations package": AI agent, reactivation, missed-call text-back, unbooked follow-up, no-show recovery, appointment reminders. No price shown, no guarantee, no ads.

## Angle
Her FAQ says she's the only employee, and her hours are by appointment with calls/texts answered "in a reasonable time frame": the engine intro is built on that. Reactivation copy leans on chronic/hypermobile patients needing care over years.

## Template/build changes (apply to future blueprints)
- `"package": "foundations"` in blueprint.json: section blocks `<!--BLOCK:ads/funnel/guarantee/included-->` are kept or dropped, section numbers and engine step cards are generated, the spec strip shows "Package · Foundations", diagram source 2 reads "New Inquiries", booked node per `booked_node`.
- Lockup logo now sits on a chip in `brand.avatar_bg` (her logo has dark text that vanished on navy).
- Funnel preview JS guarded so the chat still works without a funnel section.

## Round 2 (same day): text-only wording, price + math close, funnel
- Agent wording made explicitly text-only (SMS + web chat, no phone calls); "in your voice" → "in your own words".
- Price shown: $500/month, anchored: "Less than one new patient a month. One patient on your Silver Holistic package ($910) covers Foundations almost twice."
- New "The math" section: cited stats (HBR 2011 Oldroyd et al., 7x lead qualification within an hour; Cochrane 2013, text reminders lifted attendance 67.8% → 78.6%; Bhavsar et al. 2021, 73% of PT patients miss at least one visit) + a live calculator. Defaults: 30 inquiries × 15 min = 7.5 hrs/mo ($900 at her $120/hr rate); 2 extra patients × $910 + 2.6 saved visits × $60 = $1,978/mo; 4.0x on $500; break-even 1 patient. Left out "62% of calls unanswered / 85% never call back": no primary source.
- Funnel added (Dylan: Foundations includes one): Samantha's portrait + treatment room, 4 real reviews (Kelsey, Julia, Grace, Tabitha), CTA = free Google Meet consultation, no prices (client-funnel rule). Chat agent now books that free consultation too.

## Round 3 (same day): SEO website instead of a funnel; fixed numbers instead of a calculator
- Funnel replaced by a 10-page SEO website preview (Home, About, EDS, Hypermobility, Chronic Pain, Approach, Insurance, Reviews, FAQ, Contact): hash-routed single file, per-page titles/meta, Physiotherapy + FAQPage schema, NAP footer, mobile menu, free-consultation CTA everywhere, no prices. "SEO map" cards in the blueprint open each page in the browser preview (phone preview on mobile) and the URL bar follows.
- Calculator removed (Dylan: too complex). Four fixed outcomes: 7.5 hrs time back, $1,980 estimated added revenue, 1/3 fewer no-shows, 4x return (pays for itself with one patient), labeled "based on published industry research and typical clinic numbers" with the three studies as linked chips. Dylan asked for "and what we've seen from our past clients": left out, since there's no Foundations client data yet; add it only with real numbers.

## Open questions for Dylan
- Is "appointment reminders" part of Foundations? I included it with the other back-end systems.
- Should the package price ($500/month) appear on the page? Left off for now.
- Nothing about Foundations exists in `context/offer.md`; worth adding a section there so every agent quotes it the same way.
