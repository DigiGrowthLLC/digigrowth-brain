# Patient Acquisition Blueprint — Duende Physical Therapy — 2026-10-23

- Prospect: Dr. Natalia Martinez, DPT, Duende Physical Therapy + Pelvic Health (Berkeley, CA; duendephysicaltherapy.com), contact `fca0ef62-764f-490a-9de5-6b8c66425479`.
- URL: https://pages.digigrowthllc.com/lp/duende-physical-therapy-blueprint
- Package: main offer (ads + guarantee)
- Chat: smoke-tested live on production (postpartum leaking + insurance, then "can I book this week? do I have to do an internal exam?"): two-bubble replies, out-of-network/superbill answered from her facts, internal exam "always optional", two simulated times offered
- Sent to prospect: no

## Scrape notes
- Squarespace site. `scrape_prospect_site.py` only got home + about; /faq and /pricing are accordions, read via Playwright `textContent`. No reviews page on the site.
- Google reviews: the Doppler `PLACES_API_KEY` is rejected by Google ("API key not valid", both new and legacy Places APIs), and signed-out Google Maps hides reviews. Read all 47 through Dylan's signed-in Chrome (read-only).
- Brand: plum `#4B193A`, cream, sage, gold. Logo is the mandala tile (transparent PNG); the DUENDE wordmark is text in the funnel header.
- Photos: hamstring stretch (her face + patient) as the funnel hero, hands-on abdominal work, her hiking portrait for "Meet your PT".

## Ads
- No own-video row: her socials are Instagram and Facebook only; yt-dlp can't pull either without a login, and there is no YouTube. Ads intro says we'd cut her Instagram videos first in a real launch.
- AI static (nano-banana-pro 4:5, ~$0.15; first attempt failed on a local SSL cert error before or during submit, so possibly ~$0.30 total): tired early-30s mom on a worn purple yoga mat in a cluttered craftsman living room, baby bouncer, laundry basket, phone in hand, skeptical frown. Hook "Been told to "just do Kegels"?" (from her own FAQ: Kegels can make some symptoms worse). Copy quotes Kristin's review.
- `ugc-tried-everything` + May's review ("helped me more in the last 2 months... than the last year of PT"). Weak fit: male back-pain actor for a pelvic-first practice.
- `pov-rushed-pt` + Kristin's review ("2 other providers over 8 months"), closer "At Duende, every minute is one-on-one with Dr. Natalia. No aides. No techs." Flag: the beat-3 clip shows a therapist who reads as male under her name.
- Better next step if Dylan wants it: a new pelvic/postpartum AI UGC take (woman, situation only, nothing explicit), added to the video library afterwards.

### Round 2 (same day, Dylan: "the preapproved UGC ads; add a female UGC from my portfolio, keep the male UGC, add a static from my portfolio")
- Ads now, in order:
  1. CrosaCore "Back by Thursday" (female, early 30s, desk tension): its generic 0-7.5s take, then a Duende line card ("every minute is one-on-one with Dr. Natalia, a Doctor of PT. Never an aide."), Ashley's real review and the $49 Assessment end card. Script: `blueprints/duende-physical-therapy-blueprint/scripts/rebrand_ugc.py` (Pinnacle's, re-colored).
  2. `ugc-tried-everything` (male), unchanged.
  3. CrosaCore `corporate-shanti` quote-card static: same photo (female PT, woman patient), old panel covered by a plum panel with Talia's review (pelvic floor + C-section scar) and "Book the $49 assessment".
- Dropped: the generated "just do Kegels" static and the `pov-rushed-pt` video. The funnel hero still says "Been told to just do Kegels?", which no longer matches an ad; easy to change if wanted.
- A "back to square one" Duende version was also rendered (Navdeep's review) but isn't on the page.

## Funnel
"Been told to "just do Kegels"? Let's figure out what's actually going on." $49 assessment, normally $295 (her real 75-minute eval price). 6 Google reviews (Daisy Z., Kristin B., May C., Talia H., Rachel T., Lauren L.), good-fit list, "your 75 minutes" box from her FAQ, Meet Dr. Natalia, her three approach pillars, FAQ (cost, insurance + Medicare, internal exam, location). 195 KB.

## Chat context gaps
- Nothing important missing. Simulated times can land past her 5:30pm close for a 75-minute eval (generic behavior of `blueprint_chat.py`).

## Flags for Dylan
- Medicare: she isn't a Medicare provider and can't accept cash for Medicare-covered care, so the $49 offer can't go to Medicare patients. Exclude 65+ in targeting.
- Never use Marlene F.'s review (she's Natalia's mother).
- Pelvic-health ad copy must stay non-explicit for Meta.
- `PLACES_API_KEY` in Doppler is invalid; anything else using it (leadgen scraper?) is probably failing too.
