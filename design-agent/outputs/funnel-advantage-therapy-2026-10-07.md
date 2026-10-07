# Client Ad Funnel — Advantage Therapy — 2026-10-07

Preview approved: pending (shown to Dylan 2026-10-07)
Deployed: not yet (waiting on Phil's Calendly free-consult event link)
Custom domain: not yet connected (planned: go.advantagetherapy.vegas)

## What was built
Single-page funnel for Advantage Therapy (Dr. Phil Young DPT, Las Vegas) driving one action:
a **free consultation held as a Google Meet video call**. Rewritten 2026-10-07 from the original
$49-assessment version per Dylan: client funnels run a free consult, no prices on the page.

- Built before onboarding: client 4 has no onboarding answers and no `calendly_url`
  yet, so everything comes from his own site scrape plus the 2026-10-05 blueprint.
- Real photos only, from his site (Phil treating at SVG3 Fitness, Dr. Monique Lawson,
  a home-exercise shot). The blueprint's AI-generated ad image was deliberately NOT used.
- Seven real Google reviews (Jessica C., Isa P., Greg B., Reiney P., Stefani C., Angie P.,
  Baylee R.), first name + last initial. No rating number or review count stated.
- Brand: black + his red #d00b14, real wordmark logo, Oswald + Inter.
- Website registered for tracking: client_websites id 2 ("Meta Ads Funnel", renamed 2026-10-07),
  already listed in his portal's Website tab.

## Files
- `design-agent/outputs/advantage-therapy-funnel-preview.html` — preview, every CTA is `#book`, no tracking.
- Build kit (template + `build.py`) lives in the session scratchpad; `python build.py <booking URL>`
  writes `dist/index.html` with the URL (+ `utm_source=paid_ad`) on every CTA and the
  WEBSITE_ID 2 tracking snippet.

## Blocking before deploy
Phil has no Calendly yet. Plan: a Calendly "Free Consultation" event with location set to
Google Meet (paid plan so the Response AI can direct-book it), then swap every `#book` CTA for
that event link (+ `utm_source=paid_ad`) and add the WEBSITE_ID 2 tracking snippet
(tracking + `ads-lead` tagging key off calendly.com links). The scratchpad build kit from the
first session still renders the old $49 copy; rebuild from the updated preview HTML instead.
