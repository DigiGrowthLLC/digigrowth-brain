# Client Ad Funnel — Crosacore — 2026-09-13

Preview approved: yes
Deployed: pending Dylan's Vercel deploy
Custom domain: not yet connected

## What was built
Single-page CRO-optimized funnel for Crosacore's Meta ads, driving one action:
book the free Pain Confidence Consultation (Calendly).

- Real content from `lookup_client.py` (onboarding answers) and `scrape_prospect_site.py`
  (crosacore.com's real palette, logo, photos).
- Real social proof pulled from the client's own `CrosaCore_Testimonial_Library_Client_Acquisition.docx`
  (uploaded via their portal) — 68 real Google reviews, 12 featured as a review wall
  right after the hero, plus a social-proof trust bar (review count, patient
  employers, certifications — no fabricated rating number, since PLACES_API_KEY
  is dead).
- $200 evaluation removed per Dylan's direction — page is consultation-only.
- Iterated through several rounds of feedback (trust bar positioning/content,
  banner styling) before final approval.

## Final file
Saved locally at (not yet pushed anywhere — Dylan deploys manually per skill step 6):
`design-agent/outputs/crosacore-funnel-index.html` (copy of the approved page)

## Next step (Dylan, manual — see funnel-building SKILL.md step 6)
1. New Vercel project, drag-and-drop the folder containing this index.html (or `vercel --prod`).
2. Add a subdomain (e.g. `funnel.crosacore.com` or `go.crosacore.com`) in Vercel → Settings → Domains.
3. Add the CNAME Vercel gives you at Crosacore's registrar (Squarespace — see
   the client's Registrar Platform link on their Resources tab).
4. Once Vercel shows the domain verified, paste the live URL into the Marketing
   Setup tab's Landing Page step (`client_marketing_config.landing_page_url`).
