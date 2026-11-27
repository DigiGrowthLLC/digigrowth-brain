# Patient Acquisition Blueprints

One folder per prospect. The live page is what you open on the sales call; the folder is the source, so the page can be edited and republished later.

| Prospect | Practice | Package | Live blueprint |
|---|---|---|---|
| Brian Murphy | Pinnacle Physical Therapy, Little Rock AR | Main offer (ads + guarantee) | https://pages.digigrowthllc.com/lp/pinnacle-physical-therapy-blueprint |
| Samantha Newell | Exceptional Solutions PT, Grand Rapids MI | Foundations ($500/mo, no ads, no guarantee) | https://pages.digigrowthllc.com/lp/exceptional-solutions-pt-blueprint |
| Natalia Martinez | Duende Physical Therapy + Pelvic Health, Berkeley CA | Main offer (ads + guarantee) | https://pages.digigrowthllc.com/lp/duende-physical-therapy-blueprint |
| Aaron Shaver | Boulder Body Solutions, Boulder CO | Main offer + voice agent + social (first on the 2026-10-28 format) | https://pages.digigrowthllc.com/lp/boulder-body-solutions-blueprint |
| BettyLou DeYoung | Rise & Reframe Physical Therapy, Temecula + Murrieta CA | Main offer + voice agent + social (**THE DEFAULT FORMAT**, 2026-11-22) | https://pages.digigrowthllc.com/lp/rise-reframe-physical-therapy-blueprint |
| Dr. Morgan Gese | Evolve Physical Therapy, Richland WA | Main offer + voice agent + social (default format, 2026-11-26, auto-run after a two-call close) | https://pages.digigrowthllc.com/lp/evolve-physical-therapy-blueprint |

None of these links has been sent to the prospect yet.

---

## Dr. Morgan Gese · Evolve Physical Therapy

`evolve-physical-therapy-blueprint/` · full notes: [../blueprint-evolve-physical-therapy-blueprint-2026-11-26.md](../blueprint-evolve-physical-therapy-blueprint-2026-11-26.md)

**On the page (default format):** 3 ads cut from her own Instagram reels (clinic tour, push-up scaling, side-plank progressions; music-only, her own on-screen text kept) · the 3 default AI ads (**short versions: fal.ai was out of credit**, see below) · $49 funnel (normally $175, her real Initial Assessment price) + the booking page we build · live text agent · live voice demo · reactivation + follow-up · social · guarantee.

**Worth knowing for the call**
- Solo, cash-pay, full 60-minute one-on-one visits; board-certified OCS, dry needling + spinal manipulation; fitness-forward (lifters, CrossFit, Orangetheory, runners). Books through Jane. 4.9 on Google, only 11 reviews.
- Real prices on her site: $175 initial assessment and follow-ups ($160 in a package), free 15-min phone consult, $85 dry-needling recovery session. So the anchor is $175 (SAVE $126), not our default $150.
- Doesn't bill insurance (superbills, HSA/FSA), no referral needed (WA direct access), $25 late-cancel fee, Mon-Fri 9-5.
- First call: she wants outreach to feel personal. The reactivation block is framed "written in your voice and sent as you". She also said she'd test organic for a few months first; the social section and the own-video ads speak to that.
- The call summary mentions a six-week pilot; the page uses the current 30-day guarantee (`context/offer.md`, fixed in the template). Settle which one on the call.
- The static's quote is Megan K.'s review from her website (not confirmed on Google), condensed.
- **The two AI UGCs are short versions without the per-prospect "PT in Richland" line**: fal.ai returned 403 "Exhausted balance". Thursday = generic line + Jennifer's review + end card (15s); Square One = generic line + the cached "first visit's 49 bucks, 10 spots" take + Mark's review + end card (19s). After a top-up, run `default_ai_ads.py blueprint.json --generate` (~$3.60: the 2 city lines + Thursday's "$175 → $49" line; the Square One offer line is reused), rebuild and republish with `--assets`.
- The live chat is a demo: booking is simulated, nothing hits a calendar.

`scripts/build_own.py` rebuilds the own-video cuts (expects `vids/<id>.mp4`, downloaded with `python -m yt_dlp -f b -o "<id>.%(ext)s" https://www.instagram.com/reel/<id>/`, which worked without a login here). `scripts/make_funnel.py` regenerates `funnel.html`. `scripts/ugc_nofal.py` is the no-fal UGC build. Videos in R2: `/lp/evolve-physical-therapy-blueprint/a/video1-5.mp4` = own-clinic, own-pushup, own-sideplank, ugc-thursday, ugc-square-one.

---

## BettyLou DeYoung · Rise & Reframe Physical Therapy

`rise-reframe-physical-therapy-blueprint/` · full notes: [../blueprint-rise-reframe-physical-therapy-blueprint-2026-11-21.md](../blueprint-rise-reframe-physical-therapy-blueprint-2026-11-21.md)

**THE DEFAULT FORMAT (Dylan, 2026-11-22): every new growth blueprint copies this one's `blueprint.json`.** On the page: header lockup + section selector band · 3 ads cut from her own videos (Matt's story, "What to Expect" eval, Matt week 4, source captions kept; week 4's top captions were moved down under the hook card: `scripts/build_r3.py` `video="yetN8A8_yh0_fix"`) · the 3 default AI ads (Back by Thursday UGC + Rick, review-card static + Pamela's quote on an AI shoulder photo, Back to Square One UGC + Kevin; rebuild with `design-agent/tools/default_ai_ads.py blueprint.json`, the raw Veo takes aren't kept, so `--generate` makes new ones) · $49 funnel + the booking page we build · live text agent · live voice demo (Advantage's voice settings) · reactivation + follow-up with the real portal messaging · social · guarantee.

**Worth knowing for the call**
- Solo, cash-based, one-on-one 60-minute sessions with BettyLou; two locations (Temecula + Murrieta), Mon-Fri 8-6. Site promises a reply "within one business day": that's the engine angle.
- **No prices on her site** (FAQ says "reach out"). The $150 anchor is our default, not her number. Confirm her real eval/session price and fix the funnel + chat context.
- She doesn't take insurance and needs no referral; the agent says both.
- One of her Google reviews (Rick) says he found her through an Instagram ad, so her market already books from ads.
- Matt's video is a real patient: get his OK before it runs as a paid ad.
- The live chat is a demo: booking is simulated, nothing hits a calendar.

`scripts/build_r3.py own` rebuilds the own-video cuts (expects `vids/<id>.mp4` downloaded with yt-dlp; ids + cuts in the script). All 5 videos are in R2 at `/lp/rise-reframe-physical-therapy-blueprint/a/video1-5.mp4`.

---

## Aaron Shaver · Boulder Body Solutions

`boulder-body-solutions-blueprint/` · full notes: [../blueprint-boulder-body-solutions-blueprint-2026-10-28.md](../blueprint-boulder-body-solutions-blueprint-2026-10-28.md)

**On the page (new format, 2026-10-28):** engine diagram (7 steps) · 3 ads: our best UGC ("Back by Thursday", rebranded) + our two best review-card statics (Max's review on the Google Review Male layout, Amie's on Aaron's own clinic photo) · $49 assessment funnel (normally $120) · live AI agent with 4 scenario tabs (Meta ad lead, website, past patient, missed call) · voice agent explainer (no demo) · SMS-only reactivation · nothing leaks · social media (10 posts from the ad creative + DM agent, framed as an ad booster) · the guarantee.

**Worth knowing for the call**
- Solo practice: every session is Aaron, one-on-one, 60-120 min. That's the pitch for the agent and the voice agent.
- Pricing on his site: 60 min $120, 90 min $180, 120 min $240. Free phone consultations. **Insurance isn't mentioned anywhere on the site**; the chat says the team will confirm. Ask him.
- No Google rating on his site; the funnel uses his real "Ranked #1, BusinessRate June 2026" award instead. No hours listed either.
- No social videos found (no social links on the site), so there's no "your own videos" ad row.
- The live chat is a demo: booking is simulated, nothing hits a calendar.

`scripts/` hold the static and UGC builders as run from the scratch folder (they expect `photo0.png`, `logo.png` and `crosa/video-back-by-thursday.mp4` next to them). The ad video is in R2 at `/lp/boulder-body-solutions-blueprint/a/video1.mp4`.

---

## Brian Murphy · Pinnacle Physical Therapy

`pinnacle-physical-therapy-blueprint/` · full notes: [../blueprint-pinnacle-physical-therapy-blueprint-2026-10-08.md](../blueprint-pinnacle-physical-therapy-blueprint-2026-10-08.md)

**On the page:** engine diagram · 3 ads cut from his own YouTube videos (Ned Perme testimonial, "I've been to PT before", TMJ) · 3 AI UGC ads (tried everything, back by Thursday, back to square one) · $49 Discovery Visit funnel in laptop + phone · live AI text agent · reactivation · nothing leaks · the guarantee.

**Worth knowing for the call**
- He already sells a $49 Discovery Visit, so the offer fits his practice as-is.
- His site never says whether he takes insurance; the chat says the team will confirm. Ask him.
- Ned Perme is a public figure: fine for the preview, get his consent before his video runs as a paid ad.
- The live chat is a demo: booking is simulated, nothing hits a calendar.

---

## Samantha Newell · Exceptional Solutions PT

`exceptional-solutions-pt-blueprint/` · full notes: [../blueprint-exceptional-solutions-pt-blueprint-2026-10-08.md](../blueprint-exceptional-solutions-pt-blueprint-2026-10-08.md)

**On the page:** engine diagram · 10-page SEO website (click through it in the preview) · live AI text agent (books a free Google Meet consult) · reactivation · nothing leaks · the math (7.5 hrs back, ~$1,980/mo, 1/3 fewer no-shows, 4x, each with how it's estimated) · what's included + $500/month.

**Worth knowing for the call**
- She's the only employee; that's the pitch (the agent replies while she's treating).
- The math rests on assumptions (30 inquiries/month, 15 min each, 2 extra patients, her $910 package). Ask her real inquiry volume and adjust on the spot if it's different.
- Open items: are appointment reminders part of Foundations? Foundations isn't written into `context/offer.md` yet.

---

## Natalia Martinez · Duende Physical Therapy + Pelvic Health

`duende-physical-therapy-blueprint/` · full notes: [../blueprint-duende-physical-therapy-blueprint-2026-10-23.md](../blueprint-duende-physical-therapy-blueprint-2026-10-23.md)

**On the page:** engine diagram · 3 ads from our library (female "Back by Thursday" UGC, male tried-everything UGC, Shanti review-card static rebuilt with Talia's C-section review; no own-video row, her videos are Instagram-only) · $49 assessment funnel (normally $295) in laptop + phone · live AI text agent · reactivation · nothing leaks · the guarantee.

**Worth knowing for the call**
- Solo practice: every minute is one-on-one with her, no front desk. That's the pitch for the agent (she can't text back mid 75-minute eval).
- She's out-of-network ($295 eval, $270 follow-up, superbills, sliding scale). She is NOT a Medicare provider and legally can't take cash from Medicare patients for covered care, so the ads must exclude Medicare-age targeting/patients; the funnel FAQ says so.
- 5.0 on Google, 47 reviews. One 5-star review (Marlene F.) is from her mother; never use it. Two older reviews mention her "moving on", from a previous job.
- Pelvic-health ads get extra Meta scrutiny (sexual/health policy): keep copy non-explicit and never assert the viewer's condition.
- The live chat is a demo: booking is simulated, nothing hits a calendar.

---

## Editing and republishing a blueprint

From the repo root (Doppler supplies the keys):

```bash
python design-agent/tools/build_blueprint.py design-agent/outputs/blueprints/<slug>/blueprint.json <out_dir>
doppler run --project digigrowth --config prd -- python design-agent/tools/publish_landing_page.py "<slug>" "<out_dir>/page.html" "<Business>" "<contact_id>" --chat-context "<out_dir>/chat_context.txt"
```

Contact ids: Pinnacle `2f90a865-e412-4508-8fdb-b9a922af97c8`, Exceptional Solutions `68881152-2562-4587-94e9-c04f909c1984`, Duende `fca0ef62-764f-490a-9de5-6b8c66425479`, Boulder Body Solutions `52f1ce67-6c38-4545-8c73-cbbb6bf98c33`.

**Duende's ad videos aren't in its folder either** (~3.5 MB): `/lp/duende-physical-therapy-blueprint/a/video1.mp4` and `video2.mp4` are `libads/duende-ugc-thursday-web.mp4` and `libads/duende-ugc-tried-everything-web.mp4`. Rebuild them with `scripts/rebrand_ugc.py` (expects CrosaCore's `video-back-by-thursday/video-9x16.mp4` copied to `crosa/video-back-by-thursday.mp4` next to it) and `media-buying-agent/tools/library_ad.py` with its `practice.json`.

Republishing without `--assets` keeps the videos already in R2. **Pinnacle's ad videos aren't in this folder** (about 20 MB). To rebuild Pinnacle locally, download them back from the live page first: `/lp/pinnacle-physical-therapy-blueprint/a/video1.mp4` … `video6.mp4` are, in order, `social/cut1.mp4`, `social/cut2.mp4`, `social/cut3.mp4`, `libads/pinnacle-ugc-tried-everything-web.mp4`, `libads/pinnacle-ugc-thursday-web.mp4`, `libads/pinnacle-ugc-squareone-web.mp4` (the paths `blueprint.json` expects).

`built/page.html` in each folder is the exact page that's live, kept as a backup.
