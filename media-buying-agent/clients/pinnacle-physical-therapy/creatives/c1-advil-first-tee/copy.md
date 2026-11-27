# c1-advil-first-tee (Pinnacle Physical Therapy, batch 1, approved 2026-11-06)

Upload both sizes to the same ad (9:16 Reels/Stories, 4:5 Feed). All 3 primary texts and 5 headlines go into the same ad. AI actor (Nano Banana Pro still `actor.png` -> Veo 3.1 takes); no AI label on screen (Dylan).

Same offer, rules and CTA as batch 1 (copy-batch1.md): $49 Pain-Free Golf Visit, a full evaluation is normally $150, only 10 a month, Book Now (Instant Form), "movement screen" only (no TPI screen in the $49 visit), no emoji, no invented deadlines. The actors only voice the situation and the offer; the proof is Barry's real review. No AI label on screen (Dylan's call).

## C1 · Advil before the first tee
AI actor (man ~55, golf cart at sunrise) · problem aware · lead: Connection · emotion: "that's me", then relief

**V1** · Modeled on P1 (Life Chiropractic, running 13.5 months): the list of fixes they've tried, then "it's not that you're doing it wrong", then the new step
> Advil before the first tee. Stretching in the parking lot. A heat wrap in the bag.
>
> And it still tightens up by the turn.
>
> It's not that you're doing it wrong. A lot of the time your back is doing work your hips and upper back should be doing.
>
> The Pain-Free Golf Visit is 30 minutes, one-on-one with Dr. Brian Murphy, a TPI-certified golf PT in West Little Rock. A history, a movement screen and a straight answer on what's going on.
>
> $49. A full evaluation is normally $150. Only 10 a month.
> Tap Book Now and we'll text you a link to pick your time.

**V2** · Modeled on P28 (Great North Athletics, running 8.3 months): activity-loss question, includes, anchor + cap + reviews
> Need a couple of Advil just to get through 18?
>
> The Pain-Free Golf Visit finds out why. It includes:
> 30 minutes one-on-one with Dr. Brian Murphy, DPT
> A movement screen to see what's limiting you
> What's going on, in plain English
> Whether PT can help, how long it takes and what it costs
>
> $49. A full evaluation is normally $150. 10 visits this month. 4.9 stars on Google.
> Tap Book Now and we'll text you a link to pick your time.

**V3** · Modeled on P36 (The Golf Sock, running 12.7 months): one identity line, the video does the rest
> This is the pre-round routine a lot of Little Rock golfers over 40 are quietly running. There's a better one.
>
> $49 Pain-Free Golf Visit with Dr. Brian Murphy. A full evaluation is normally $150. Only 10 a month.

**Headlines:** Advil Is Not a Warm-Up · Find Out Why It Tightens Up by the Turn · $49 Pain-Free Golf Visit · A Full Evaluation Is Normally $150 · Only 10 Visits a Month

Spoken lines: see the takes in the spec below.

```json
{
 "slug": "c1-advil-first-tee",
 "takes": [
  {
   "path": "work/c1-take1.mp4",
   "in": 0.5,
   "out": 6.6
  },
  {
   "path": "work/c1-take2.mp4",
   "in": 0.0,
   "out": 7.2
  },
  {
   "path": "work/c1-take3.mp4",
   "in": 0.0,
   "out": 4.5
  },
  {
   "path": "work/c1-take3.mp4",
   "in": 5.68,
   "out": 6.95
  }
 ],
 "hook": "Three Advil before the first tee?",
 "caption_fixes": {
  "warm -up.": "warm-up.",
  "49": "$49",
  "150": "$150"
 },
 "label": "",
 "proof": {
  "quote": "Dr. Murphy saw me and evaluated my entire movements of the body, not just my back.",
  "attribution": "BARRY \u00b7 GOLFER, REAL PATIENT REVIEW"
 },
 "end_card": {
  "eyebrow": "PINNACLE PHYSICAL THERAPY \u00b7 LITTLE ROCK",
  "headline": "Pain-Free Golf Visit",
  "lines": [
   "One-on-one with Dr. Brian Murphy, DPT"
  ],
  "button": "BOOK NOW",
  "footnote": "12511 Cantrell Rd, West Little Rock",
  "logo": "C:/Users/dylan/Videos/Business/AI Agents/DigiGrowth-Brain/design-agent/outputs/blueprints/pinnacle-physical-therapy-blueprint/logo.png",
  "price": {
   "was": "$150",
   "now": "$49",
   "note": "A full evaluation is normally $150",
   "badge": "ONLY 10 SPOTS THIS MONTH",
   "urgency": "Book now before they're gone"
  }
 },
 "palette": {
  "card": [
   8,
   34,
   42
  ],
  "accent": [
   255,
   171,
   94
  ],
  "panel": [
   20,
   92,
   110
  ]
 },
 "music": "work/bed.wav",
 "crop_4x5_top": 160,
 "hook_pos": {
  "9x16": 0.1,
  "4x5": 0.12
 },
 "hook_seconds": 2.0,
 "end_seconds": 4.0
}
```
