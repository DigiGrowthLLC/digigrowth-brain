# Patient Acquisition Blueprint: Rise & Reframe Physical Therapy (2026-11-21)

- **Prospect:** Dr. BettyLou DeYoung, Rise & Reframe PT, Temecula + Murrieta CA (contact 23e0fec0-24dc-4adf-9780-0f3f5fb96fa6). Discovery call was 2026-11-19.
- **URL:** https://pages.digigrowthllc.com/lp/rise-reframe-physical-therapy-blueprint
- **Chat:** tested live on production (insurance + running knee question, then "can I book this week?": two-bubble answers, two times offered).
- **Sent to prospect:** no.

## Ads
- Own videos (YouTube @RiseReframePT):
  - `Fbqz5pDNA0w` "Matt Castro Pt.1": cuts 17.0-38.9, 56.8-63.6, 105.0-123.9 (+2.5s $49 end card), 47s. No organic CTA to remove.
  - `lrqlYgXohhE` "What to Expect Coming in for an Eval pt1": cuts 0-6.9, 26.0-55.4 (+ end card), 36s.
  - Skipped: breathwork and mindset shorts (too abstract for a pain ad).
- AI row: default "Back by Thursday" UGC via `blueprint_default_ads.ugc()` (Pamela's review, line card "every session is one-on-one with Dr. BettyLou. Never an aide."). The two default statics' photos were replaced with her own clinic photos (the headline default shows a male clinician; she's a solo female owner). Review static = Rick's Google review.
- No fal spend, no new AI generation.

## Missing from the site (chat says the team will confirm)
- Eval/session prices (the $150 anchor is our default). No aggregate Google rating shown, so the funnel says "Real Google reviews" with no number.

## Round 2 (2026-11-22, Dylan: presentation format)
- Page rebuilt on the new presentation template: one-line intros, key-point tiles, chip lists, section nav, voice timeline, guarantee as 3 numbers.
- AI row now pre-approved creative only: Back by Thursday UGC (Rick), corporate-shanti static (Pamela), corporate-dawn static (Tamara). Her own photos are out of the AI row.
- Third own-video ad: `yetN8A8_yh0` "Matt Castro Pt.2", cuts 8.6-16.2, 128.0-137.9, 174.6-177.8 (week 4, "lost like 30% of my pain").
- Funnel hero recropped 4:5 so the hands-on treatment shows.
- Website chat tab removed.
- Live voice demo added (blueprint_voice.py); works once the backend is deployed.
