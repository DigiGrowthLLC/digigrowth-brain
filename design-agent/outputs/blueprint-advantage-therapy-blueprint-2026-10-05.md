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
