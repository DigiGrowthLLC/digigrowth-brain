# Patient Acquisition Blueprint — Advantage Therapy — 2026-10-05

First real run of the `patient-acquisition-blueprint` skill.

- Prospect: Phil Young, Advantage Therapy (manual PT for chronic pain, Las Vegas), contact `6d3d3854-fbc5-4401-8d74-14ee243a9b79`
- URL: https://pages.digigrowthllc.com/lp/advantage-therapy-blueprint
- Chat: smoke-tested live on production (sciatica question, insurance/price, booking). Answers came from site facts only, ~7-8s per reply on prod
- Sent to prospect: no

## Ads (nano-banana-pro, 4:5)
1. Top of funnel, "tried everything, still in pain": man in a messy home kitchen holding his low back, kid's backpack on the floor. Hook "When massage, adjustments and PT didn't stick". Primary text quotes Greg B.'s real Google review.
2. Top of funnel, "real one-on-one time": gloved DPT doing manual therapy on a tattooed athlete in a black-walled gym (matches his SVG3 Fitness location). Hook "60 minutes. One-on-one. Hands-on."
3. Bottom of funnel, insurance objection: therapist explaining a spine model to a patient in a gym-side treatment room. Hook "Why we don't take insurance".

## Notes
- Scraped logo was a generic 24px Wix icon and palette.json read white/blue; the real wordmark was cropped from hero.png and the red (#d00b14) sampled from it. Skill updated to check for this.
- His site says he texts and doesn't answer calls, so the missed-call text-back angle is used in the engine intro and the recovery cards.
- Site lists prices ($250 eval, $800/4-pack), so the demo agent quotes them when asked.

## Round 2 (same day, Dylan's review)
- Chat: replies are now text-length, answer then the next question as a separate bubble (`blueprint_chat.py`).
- Header nav buttons and hero subheading removed; closing booking CTA removed (page is for prospects already on a sales call).
- New "4 · Database reactivation" step + section (SMS thread + email), "Nothing leaks" is step 5.
- Funnel section: "Why ads go to a funnel, not your website" + 3 reason cards; funnel rebuilt responsive and shown in a desktop browser frame next to the phone; 6 real Google reviews (Jessica C., Isa P., Reiney P., Angie P., Stefani C., Baylee R.); hero photo re-cropped (the site banner's left 60% is a black fade); FAQ full-width like the other sections.
- Ads, own videos (YouTube Shorts @DrPhilipYoungDPT; Instagram/TikTok blocked without login): VSnca2boa2g 0-19.5s (sciatica, gone in 3 sessions), Ybe27srG7rc 0-14 + 36-51s (before/after), oBubo8ayq3M 0-50s (why cash-pay). Organic CTAs cut, branded end card added.
- Ads, AI row: UGC car-selfie actor (Veo 3.1, 2 takes, Angie's review card; first still regenerated because it had a fake phone UI baked in), the gym static, and a POV video ("15-minute PT visit, therapist juggling 3 other patients" → "Week 8..." → "a full hour, one-on-one", Jessica's review). No music beds: fal hit 403 TOP_UP on the music call. Spend this round ~$8-9.
- `PLACES_API_KEY` in Doppler returned "API key not valid" (flagged to Dylan).
