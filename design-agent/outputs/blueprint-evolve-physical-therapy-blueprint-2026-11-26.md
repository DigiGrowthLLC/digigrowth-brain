Patient Acquisition Blueprint — Evolve Physical Therapy — 2026-11-26
Slug: evolve-physical-therapy-blueprint
URL: https://pages.digigrowthllc.com/lp/evolve-physical-therapy-blueprint
Chat: tested live (yes)
Sent to prospect: no

Run automatically after Dylan marked a two-call close on Dr. Morgan Gese's first sales call (contact `44406db9-10e1-4eaa-91c4-d536b63c925f`). The page is for the second call (Tuesday 1:00 PM). Source: `blueprints/evolve-physical-therapy-blueprint/`.

## Prospect facts used
- Evolve Physical Therapy, LLC, 2000 Saint St, Richland WA 99354. Dr. Morgan Gese, PT, DPT, OCS (board-certified Orthopedic Clinical Specialist, dry needling + spinal manipulation endorsed, former D1 basketball player). Solo, cash-pay, 60-minute one-on-one visits. Mon-Fri 9-5, Sat by appointment.
- Prices (Jane booking page + her blog): Initial Assessment $175, follow-up $175, package follow-up $160, dry needling recovery $85, free 15-min phone consult. **Funnel anchor = $175** (SAVE $126), 10 spots/month.
- Google (Places API, verified): **4.9, 11 reviews**. Brand color sage `#75a895` sampled from the site header.
- Fireflies summary (used to tailor, never quoted): solo cash practice at ~$6K/mo aiming for $10K; needs 3-5 new patients a week because patients finish in 3-4 visits; wants outreach to feel personal; plans to test organic first. Tailoring on the page: engine intro ("speedy care from first contact... mid-session, nobody's free to text back"), reactivation intro ("written in your voice and sent as you"), close ("you find what others missed, often in a few visits").

## Ads
**Own videos (Instagram reels, downloaded with yt-dlp without a login; she has no YouTube/TikTok):**
- `own-clinic`: reel `DOpDvBWjiS_` 0-28.4s (cut the QR / "visit my website" ending). Hook "This isn't your typical PT clinic." (full-width card hides her animated title).
- `own-pushup`: reel `DP2PZuaESPi` 0-35.6s. Hook "Can't do a full push-up yet? Don't skip it. Scale it." Name card at 5.6s, after her teal intro.
- `own-sideplank`: reel `DO68xpUjuo5` 0.8-3.8s (title) + 3.8-30s cropped out of its pillarbox (288x512 source, so it's soft when upscaled).
- All three are music-only with her own on-screen text, so no captions were added. Name lower-third "Dr. Morgan Gese, DPT, OCS", 4s $175→$49 offer end card with 4.9 rating + 10 spots. The music is Instagram audio: fine for the preview, swap it for licensed audio before running.

**Default AI ads:**
- `static_review.jpg`: library photo `female-shoulder.jpg` ($0). Quote condensed from Megan K.'s review on her website: "She corrected years of bad lifting habits in my shoulder and alleviated the pain." No reviewer name on the image.
- **fal.ai was out of credit** (403 "User is locked. Reason: Exhausted balance"). So both UGCs were built without new footage (`scripts/ugc_nofal.py`):
  - `ugc-thursday` (15.2s): generic "Back by Thursday?" line + Jennifer's Google review card + end card. No city line, no spoken offer line.
  - `ugc-square-one` (19.4s): generic line + the cached "First visit's 49 bucks right now. Only 10 spots a month." take (match 100%; it names no anchor, so it's still accurate at $175) + Mark's Google review card + end card.
  - Full versions after a top-up: `doppler run ... python design-agent/tools/default_ai_ads.py blueprint.json --generate` makes th-t2 ("Turns out there's a PT in Richland who works one-on-one the whole visit."), sq-t2 ("So there's a PT in Richland, Doctor Morgan, one-on-one start to finish.") and th-t3 ("Normally a hundred seventy-five, right now it's forty-nine. And there's only ten spots a month."). That's ~$3.60: the $175 anchor isn't the cached $150 take. Put the cached `sq-offer.mp4` in `ai_ads_work/takes/sq-t3.mp4` first so Square One's offer line stays free.
- **fal spend this run: $0.**

## Funnel + booking page
- Funnel `funnel.html` (165 KB): hero "\"Wait and see\" isn't a plan. Get back to training." (her own line), hands-on neck treatment photo, deadlift-coaching photo, 6 reviews (Jennifer H., Dylan S., Mark G., Casey C., Abby H. from Google; Megan K. from her site), her 3-step approach, FAQ (cost/insurance/referral/location).
- Booking page: Morgan's portrait, logo on white (`logo_booking.png`: the build drops transparency, so the transparent logo rendered as a black box), Jennifer's review, 4.9 (11), 60 min, $49 normally $175, 10 spots. URL shown: `booking.digigrowthllc.com/evolve-pt`.

## Chat context
About 640 words, all from her site, FAQ, blog, Jane page and Google. Nothing missing that patients usually ask. Live test: an insurance + deadlift-back question got the superbill/HSA answer, then "find you a time for the $49 New Patient Assessment?", then two times when asked to book.

## Flags for Dylan
- 6-week pilot (call summary) vs the 30-day guarantee on the page (offer.md + template).
- fal top-up needed before the full UGCs can be made.
- Her reels use Instagram music, and the third reel is low-res.
