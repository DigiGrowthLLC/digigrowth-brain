# Patient Acquisition Blueprint — Pinnacle Physical Therapy — 2026-10-08

- Prospect: Dr. Brian Murphy, Pinnacle Physical Therapy (Little Rock, AR; pinnacledpt.com), contact `2f90a865-e412-4508-8fdb-b9a922af97c8`. Discovery call held 2026-10-07.
- URL: https://pages.digigrowthllc.com/lp/pinnacle-physical-therapy-blueprint
- Chat: smoke-tested live on production (sciatica + insurance, then "can I book this week?"): two-bubble replies, sciatica answered from site facts, insurance deferred to the team, two simulated times offered
- Sent to prospect: no

## Scrape notes
- Site is behind Cloudflare: `requests`/curl get the challenge page and `scrape_prospect_site.py` returned the homepage text for every route. Subpages, reviews, logo and photos were pulled via Playwright (in-page `fetch`).
- Scraped "logo" was a dumbbell icon; real logo is `wp-content/uploads/2022/07/Pinnacle-Logo-BlackOutterGlow-WhiteText-WhiteClimber-...png` (white text, needs a dark/teal background). Brand colors sampled from hero.png: teal `#248ca1`, orange `#ffab5e`.
- All site photos are stock, so the funnel uses frames from his own videos. Round 2 (Dylan: the first frames looked bad): hero is now hands-on jaw/neck work at 204s of `4gvGkYLKuVI` (TMJ eval), second photo is Brian screening a golfer at 128s of `3CzsTua9Z8I` (TPI screen, 1080p), both cropped clear of logo bugs and lightly sharpened; desktop hero box changed to 4:3 so the landscape shot isn't cut. Round 3 (Dylan picked option B): hero is Brian with clipboard watching a golfer's TPI screen (66s of `3CzsTua9Z8I`, crop 680-1760 x 60-870); second photo is the hands-on jaw shot at 14s of `4gvGkYLKuVI`, so the page doesn't repeat the gym scene.
- **He already sells a $49 Discovery Visit** (consult + movement screen: root cause, can PT help, how long, what it costs, home tips). The funnel and ads use his own offer and wording. No "normally $X" anchor, since the site lists no eval price and the Discovery Visit is always $49.
- Insurance policy isn't stated anywhere on the site, so the chat says "I'll have the team confirm". Worth asking Brian on the next call.

## Ads, own videos (YouTube channel UC_OeBatGPWUOM--A4gYImRA; Instagram not tried)
1. `ixMeCbQ2gZY`: Ned Perme testimonial (retired from Channel 7, plantar fasciitis, 9 laser treatments, back to pickleball in 8 weeks). Cuts 0-41.5 + 49.7-58.3s, already vertical.
2. `VC6Gu2c3pg8`: "How are you different from other PTs?" Cuts 40.85-64.7 + 98.3-105.8 + 114.95-115.75s, center-cropped 9:16, starting after his burned-in title card; the hook card carries the "I've been to PT before" objection.
3. `1_-fjlolliI`: TMJ specialist. Cuts 0-21.3 + 62.7-84.2s, cropped to the top 860px to drop the source's burned-in subtitles and name lower-third.
- All three: captions added (the horizontal sources had none), a 3.2s hook card, organic CTAs cut, and a 2.5s end card (logo, "$49 Discovery Visit", "Every session with your PT, never a tech", "No meds, shots or surgery"). Script: scratch `cut_social.py` (uses `media-buying-agent/tools/ad_overlays.py`).

## Ads, AI row
- `ugc-tried-everything` + Barry's review ("so called best pain doctors and physical therapist in Little Rock to no avail... back to playing golf again"). Flag: the actor's car window shows palm trees and desert mountains, which doesn't read as Arkansas.
- `pov-rushed-pt` + Ireon's review ("No techs, no assistants, just him... only taken 5 visits"), closer "At Pinnacle, every session is with your physical therapist. Never a tech or an aide."
- Static (nano-banana-pro, 4:5): sweaty 55-year-old golfer on a pine-lined Arkansas fairway, hand pressed into his back, push cart beside him. Hook "Back pain cutting your round short?", copy from Barry's review + TPI Level 2. fal spend: one nano-banana-pro image (~$0.15).

### Round 4 (Dylan didn't like AI ads 2 and 3; "pick from our other AI videos")
- The golf static and the `pov-rushed-pt` video were replaced with two CrosaCore AI UGC ads, reusing only their generic first take (hook card + captions burned in, nothing Austin-specific): "Back by Thursday?" (0-7.5s of `clients/crosacore/creatives/video-back-by-thursday/video-9x16.mp4`) and "Back to square one?" (0-5.35s of `video-back-to-square-one`). Each then gets a Pinnacle line card, a real Pinnacle review (Andrew; Michael the triathlete) and the $49 Discovery Visit end card. Script: scratch `rebrand_ugc.py`. No fal spend.
- Their clean takes weren't saved anywhere, which is why they aren't in `video-library/` yet. Worth saving raw takes next time a UGC ad is generated.
- No other AI video fit: "No time for PT" and "Skip the drive" are in-home PT (Pinnacle doesn't do it), "3pm desk" is built on Brandon's photos.

## Funnel
"Been to PT before and it didn't help? This is different." 6 real reviews from the site's testimonials page (Barry, Ireon, Andrew, Jeannie, Matthew, Rachael; the site only gives first names), "what you'll discover" box from his own Discovery Visit copy, Analyze/Educate/Empower, FAQ (cost, who you'll see, location/hours). "4.9 on Google" is the more conservative of the two ratings on the site (4.9 and 5.0).

## Flags for Dylan
- Ned Perme is a public figure. His testimonial is fine for the preview, but get explicit consent before it runs as a paid ad.
- Insurance status unknown (see above).
