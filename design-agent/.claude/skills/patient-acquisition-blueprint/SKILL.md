---
name: patient-acquisition-blueprint
description: Build a personalized Patient Acquisition Blueprint page for one PT practice prospect that Dylan walks through on a sales call — ads (cut from the practice's own social videos, plus AI UGC/POV videos customized from a reusable video library and an AI static), the patient funnel shown in a desktop browser and a phone, a LIVE AI appointment-setting chat agent trained on their website, email + SMS database reactivation, and an animated flow diagram of the whole engine (reactivation + new ad leads + missed calls → AI agent → booked consult, with unbooked leads, no-shows and finished patients recycled back into reactivation). Hosted at /lp/<slug>. Use when Dylan says "run the blueprint for X", "build a patient acquisition blueprint", or wants a show-the-whole-system page for a prospect.
---

# Patient Acquisition Blueprint

One page that shows a practice owner the entire AI Growth Engine built around *their* practice: what their ads would look like, the funnel those ads land on, an AI agent they can actually talk to, how their existing list gets reactivated, and how every lead that doesn't book gets recycled instead of lost.

How it differs from `landing-page-lead-magnet`: that page is a cold-SMS curiosity planter with a mockup of their site on top. The blueprint is the **full system walkthrough**, written to the practice owner from the first line, for prospects **already on a sales call** with Dylan: he walks them through it live (and may send the link after). Its centerpiece is the live agent. It has no booking CTA, since the prospect is already on the call.

**One prospect at a time, in the foreground. Never background this skill.** (Standing rule across agents since the leadgen backgrounding incident.)

**Nothing is sent to the prospect without Dylan's explicit approval.** Publishing the page so Dylan can test it live is fine (step 10). Sending the link is a separate yes.

Worked example (Dylan-approved, 2026-10-05): Advantage Therapy, Las Vegas, live at `pages.digigrowthllc.com/lp/advantage-therapy-blueprint`. Its content is `references/blueprint-example.json`, its funnel is `references/blueprint-example-funnel.html` (photos stubbed out), and the run notes are `outputs/blueprint-advantage-therapy-blueprint-2026-10-05.md`.

## The page, top to bottom

Fixed by `design-agent/references/blueprint-template.html` (DigiGrowth navy/glass theme; the practice's own colors only inside the ads, funnel and chat):

1. **Disclaimer bar**, then the **hero**: their logo × DigiGrowth lockup, kicker, and a headline only. No navigation buttons and no subheading (Dylan removed both, 2026-10-05).
2. **How the whole thing works**: the animated engine diagram, next to five step cards: 1 Ads, 2 Funnel, 3 AI agent, 4 Database reactivation, 5 Nothing leaks.
3. **1 · Ads**: a row "Cut from your own videos" (their real social videos, edited into ads), then a row "AI-generated concepts" (AI UGC video, one static, AI POV video), all in Facebook-post frames.
4. **2 · Funnel**: "Why ads go to a funnel, not your website" with three reason cards, then the funnel shown in a desktop browser frame with a phone beside it.
5. **3 · AI appointment agent**: the live chat in the practice's colors.
6. **4 · Database reactivation**: an SMS thread and an email to leads and past patients they already have.
7. **5 · Nothing leaks**: missed-call text-back, unbooked follow-up, no-show recovery.
8. **The guarantee** (7-10 paid assessments in the first 6 weeks, 7 guaranteed, three cards; terms in `context/offer.md`). The page ends here.

Per prospect you write `blueprint.json` (all copy, ad data, SMS/email examples, chat greeting/chips, `chat_context`; schema in `design-agent/tools/build_blueprint.py`'s docstring), `funnel.html`, and the ad media. `build_blueprint.py` fills the template, inlines images and the funnel, and copies videos to `out/assets/` for upload. The live chat posts to `/lp/<slug>/chat` (`dashboard/backend/routers/landing_pages.py` → `dashboard/backend/blueprint_chat.py`), answering from `chat_context` stored on the page's `landing_pages` row. **Booking in the demo chat is simulated:** made-up open times, nothing written to any calendar, nobody texted.

If the page itself needs a design change, change `blueprint-template.html` (or the build script) so every future blueprint gets it, and rebuild. Don't hand-edit a built page.

## Steps

Work in a scratch folder, e.g. `<scratchpad>/blueprint-<slug>/`.

1. **Look up the prospect.**
   ```bash
   python design-agent/tools/lookup_prospect.py "<name or business>"
   ```
   Gives `contact_id`, `phone`, `website`, `owner`. If Dylan gave a website directly and there's no contact on file, carry on with the website alone and pass `-` as the contact_id in step 10.

2. **Scrape their site.**
   ```bash
   python design-agent/tools/scrape_prospect_site.py "<website>" "<scratch_dir>"
   ```
   Same tool and rules as `landing-page-lead-magnet` step 2: read `page_text.txt` closely (services, offer, insurance/cash-pay, prices, hours, location, reviews), colors from `palette.json`, logo and photos from `assets.json`. **Look at `hero.png` too.** On Wix and similar builders the scraped "logo" is often a generic 24px site icon, and `palette.json` can miss the real brand color (it read white/blue on Advantage's black-and-red site). When that happens, crop the real wordmark out of `hero.png` with PIL, sample the brand color from its pixels, and set `brand.avatar_bg` to the logo's own background color (`#000000` for a logo cut from a black header).

3. **Read before writing.**
   - `media-buying-agent/context/ad-creative-principles.md` (ads follow its Working Checklist)
   - `media-buying-agent/.claude/skills/generate-ad/SKILL.md`: "Who can say what", "Video Ad Variations" and "AI UGC Video Ads"
   - `design-agent/references/cro-funnel-principles.md` (for the funnel)
   - `context/offer.md` at the repo root (offer, guarantee, pilot terms, KPIs: the only DigiGrowth claims the page may make)
   - `design-agent/references/blueprint-example.json`, for tone and length per field

4. **Pull their real reviews and social videos.** The strongest material on the page.
   - **Reviews:** most PT sites have a reviews/testimonials page `page_text.txt` doesn't cover. Open it with Playwright (Wix renders reviews with JS, so `requests` misses them), scroll to load them all, read `document.body.innerText`. Pick 6 that fit the funnel's angle ("tried everything else", "fewer visits than other PT") for the funnel's review wall, plus one or two for ad proof cards. Attribute as first name + last initial ("Jessica C.").
   - **Videos:** take their social links from the homepage HTML (`instagram.com/`, `tiktok.com/@`, `youtube.com/@`). Instagram and TikTok refuse downloads without a login; YouTube Shorts works and usually has the same videos. `yt-dlp` is pip-installed (`python -m yt_dlp`). List with view counts:
     ```bash
     python -m yt_dlp --flat-playlist --playlist-end 30 --print "%(id)s|%(view_count)s|%(title).80s" "https://www.youtube.com/@<handle>/shorts"
     ```
     Shortlist 3-4 by views and fit (a real patient result, a before/after, the owner explaining why they're different), download (`python -m yt_dlp -f "bv*[height<=1920][ext=mp4]+ba[ext=m4a]/b" --merge-output-format mp4 -o <id>.mp4 https://www.youtube.com/shorts/<id>`), transcribe (faster-whisper), and look at a contact sheet per video (`ffmpeg -vf "fps=1/5,scale=180:-1,tile=6x2"`) before choosing cuts.
   - **Edit 3 of them into ads, lightly:** trim to the strongest 15-50s, **cut their organic calls to action** ("comment X", "learn more in the caption", "text me"), and append a 2.5s branded end card (their logo, their real first-step offer, e.g. "Free phone consult"). Keep their own burned-in captions; don't stack a second set. Re-encode to 720x1280, H.264 CRF ~27, AAC 96k, `+faststart`, under ~8 MB each. These go in `ads.video_items`. Real before/afters are fine for the preview, but flag to Dylan that Meta can restrict before/after health imagery if they ever run as real ads.

5. **Write `chat_context`: the demo agent's whole knowledge of the practice.** Facts only, all from the scrape: name, area, clinicians and credentials, approach, conditions, services, the real first step (free consult/phone consult/screen, as their site words it), prices if the site lists them, insurance/cash-pay, HSA/FSA, superbills, hours, address, contact method, 1-2 real review snippets. Plain sentences or labeled lines, roughly 150-450 words. If the site doesn't say something, leave it out: the agent says "I'll have the team confirm" for anything missing. Never pad with guesses, since the agent states whatever is here as fact.

6. **Make the AI-generated concepts row: an AI UGC video, one static, an AI POV video** (Dylan's preferred mix, 2026-10-05). **The two videos come from the reusable video library, not new generation** (Dylan, 2026-10-06): the footage in `media-buying-agent/video-library/` is generic (no city, practice name or offer details), and each blueprint just puts the practice's own colors, real Google review card and CTA end card on it. No fal spend, about a minute to build.
   - Read `media-buying-agent/video-library/library.json` and pick one UGC item and the POV item whose `fits` matches this practice (e.g. `ugc-caregiver-mom` only for practices that offer in-home/mobile PT; `pov-rushed-pt` suits cash-pay/one-on-one practices). Respect any `caution`.
   - For each, pick a **real review** (from step 4) that matches the clip's angle: "finally got results after other care" for `ugc-tried-everything`, "fewer visits / real hands-on time" for `pov-rushed-pt`. First name only in the attribution ("ANGIE · REAL GOOGLE REVIEW").
   - Write `practice.json` (schema in the tool's docstring): `slug`, `palette` (their brand color as `accent`, a near-black `card`), `end_card` (their eyebrow "PRACTICE · CITY", their real first step as the headline, two true lines, button, footnote), `reviews` per item, and `pov_closer`, the POV ad's final beat in their own facts ("At <Practice>, every visit is ..."). Then:
     ```bash
     python media-buying-agent/tools/library_ad.py "<scratch_dir>/practice.json" "<scratch_dir>/libads"
     ```
     It writes 9:16 (and 4:5 for UGC) finals plus `<slug>-<item>-web.mp4` copies for the page. Check a frame sheet of each, then point the `video` fields in `ads.items` at the `-web.mp4` files.
   - **Generate new AI video only when Dylan asks for it, or nothing in the library fits** (e.g. a practice whose angle the library doesn't cover). Then follow `generate-ad`'s "AI UGC Video Ads" loop (actor still prompt starting "Full-bleed photograph, no phone interface, no status bar, no app UI"; two Veo 3.1 takes; `assemble_ugc_ad.py`) or the POV format (Kling clips from stills; `assemble_pov_ad.py`), all from `content-agent/` under `doppler run --project digigrowth --config prd --`. Actors voice the situation only, never a result or patient claim. **Script any new take so it's reusable**: keep city, practice name and offer details out of the spoken line and put them on the cards instead. Then add the clean footage to the library (trimmed, re-encoded to 1080x1920 CRF ~26) with a `library.json` entry. If fal returns 403 "TOP_UP", it's out of credit: tell Dylan and fall back to the library.
   - **AI static (top of funnel)**, still generated per prospect since it's cheap and shows their own setting: `generate_creative.py image ... --model nano-banana-pro --aspect 4:5` under `doppler run`, the avatar or the practice's distinctive setting unmistakable at a glance, harsh realism language (see the Ad Creative Realism memory), **no text in the image** (the hook is an HTML overlay via the `hook` field). Look at it before using it.
   - In `ads.items`, an entry with `video` renders as a video card, one with `image` as a static.
   - Copy rules for every ad: hook → problem → solution → proof → CTA. Never assert the viewer's condition ("Your back pain..."), since Meta rejects it. Proof only from real reviews, first-name attribution. Fill `angle_label` ("Top of funnel · AI UGC", "Bottom of funnel · AI POV video", ...) and `angle`.

7. **Write `funnel.html`, the patient-facing page ad #1 clicks into.** A complete standalone, **responsive** HTML document; the blueprint shows it twice, in a phone frame (~375px) and in a desktop browser frame (rendered at 1280px, scaled down). Design mobile first, then a `@media (min-width:900px)` layer: two-column hero (copy left, photo right), a CTA button in the header, a 3-column review wall.
   - **Patient voice only**, exactly as in `landing-page-lead-magnet`'s Section 1 voice check: it *is* their page talking to a patient. No DigiGrowth, no "your practice", no meta.
   - **The patient offer is the $49 assessment** (per `context/offer.md`): the hero, CTA and FAQ sell a $49 assessment ("normally $X", using the practice's real assessment/eval price from their site, or $150 if it isn't shown), paid when booking, with limited spots each month. The CTA reads like "Book your $49 assessment". No "free consult".
   - Message match: the hero headline restates the first ad's promise. Their palette, their logo, 1-2 real photos (from `assets.json`, or a clean frame from their own video, cropped above any burned-in caption).
   - **Check every photo before using it.** Site hero images are often wide banners with a dark fade on one side for text; in a small frame they look like a dark sliver. Crop to the real subject.
   - **Social proof leads.** Per `cro-funnel-principles.md`: hero + one CTA + a "5.0 on Google" line (only a rating the site itself shows) → trust bar → **wall of 6 real reviews** → good-fit list → 3 real treatment approaches → short FAQ (price, insurance, location) → the same CTA again. Buttons are visual only (`href="#"`).
   - **Every section uses the same container width and left alignment** (Dylan, 2026-10-05: a narrower, centered FAQ looked out of place). Scope row styles to the rows (`.faq .w>div`), never a bare `.faq div`, which also hits the container and strips its padding.
   - ~38px of top padding on the mobile header so the phone notch doesn't clip the logo; hide the page's scrollbar (`html{scrollbar-width:none}` + `::-webkit-scrollbar{display:none}`) so the desktop preview looks clean.
   - Inline CSS, no JS, no external requests (system font stack), under ~250 KB with photos. The `--p`/`--p-ink` variables don't reach inside the iframe, so set colors directly.

8. **Write `blueprint.json`.** Start from `references/blueprint-example.json` for structure; every word gets rewritten for this practice.
   - `slug`: `<business-slug>-blueprint` (the suffix keeps it from overwriting the practice's lead-magnet page).
   - `brand.primary`/`primary_text`/`avatar_bg`: real button color and its text color (chat header, bubbles, ad avatars), and the logo's background color.
   - `hero.headline`: the practice's outcome, addressed to the owner, 2-4 words in `*asterisks*` for the gradient accent. Anchor numbers only to the real offer (7-10 paid assessments in the first 6 weeks, 7 guaranteed). No subheading.
   - `engine_intro`: personalize it to something real on their site (Advantage: "your site says you text and don't take calls" set up the missed-call angle).
   - `step_blurbs`: five, in order: ads, funnel, AI agent, database reactivation (email + SMS campaigns to leads and past patients they already have), nothing leaks.
   - `ads.intro`, `ads.video_items` (step 4), `ads.items` (step 6).
   - `funnel`: `headline`/`intro`/`why` answer "I already have a website": their site is good and stays, but a site is built to inform, while an ad click needs one reason and one way to book. Three `why` cards: only the information that gets someone to book; no distractions (no menu, articles, links away); one choice, since too many options cause decision paralysis. `url` is the address shown in the browser bar (their domain + `/assessment`). `points` are the four ticks under the devices.
   - `agent.greeting` + 3 `chips`: what a real patient of this practice would type (a symptom from their specialty, insurance/cost, a booking request for the $49 assessment).
   - `reactivation`: an SMS thread (practice text + a lead reply) and an email (`subject`, `body` with `\n\n` paragraph breaks) to old leads/past patients, in the practice's voice.
   - `recovery.items`: three cards in this order: missed-call text-back, unbooked-lead follow-up, no-show recovery.
   - All SMS text must be **GSM-7 safe** (no em dashes, curly quotes, ellipses or emoji; the build warns). Use realistic first names, never real patients from the reviews.
   - `close_intro`: one or two sentences above the fixed guarantee cards. The page deliberately ends there, with no booking CTA.

9. **Build and check.**
   ```bash
   python design-agent/tools/build_blueprint.py "<scratch_dir>/blueprint.json" "<scratch_dir>/out"
   ```
   Fix every WARNING. Then look at it: either publish `out/page.html` as a Claude Artifact (the chat shows "runs on the published blueprint link" and video cards show poster frames there; both expected), or serve `out/` locally with a tiny HTTP server that answers `/lp/<slug>/chat` via `blueprint_chat.reply()` and serves `/a/<name>` from `out/assets/`, so the chat and videos work before publishing. Force `.reveal{opacity:1 !important}` before screenshots, check desktop and ~390px mobile, and save screenshots under `.playwright-mcp/`, never the repo root.

10. **Publish for live testing.**
    ```bash
    python design-agent/tools/publish_landing_page.py "<slug>" "<scratch_dir>/out/page.html" "<business>" "<contact_id or ->" --chat-context "<scratch_dir>/out/chat_context.txt" --assets "<scratch_dir>/out/assets"
    ```
    `--assets` uploads the videos to R2 (served from `/lp/<slug>/a/<name>`); a republish without it keeps what's already uploaded. Prints the live URL. Smoke-test on production: each `/a/videoN.mp4` returns 200, and POST two messages to `<url>/chat` (an insurance/services question, then "can I book this week?"): the answer and the next question come back as two `replies`, from the practice's facts, then two times are offered. Revisions: edit, rebuild, re-run the same publish command (it upserts the slug).

11. **Sending is a separate yes.** Only when Dylan explicitly asks. The landing-page SMS tool's locked wording is about the pilot mockup, so don't reuse it. Ask how he wants it delivered (he texts it himself, a call follow-up, or a one-off SMS he approves word for word).

12. **Completion note** to `design-agent/outputs/blueprint-<slug>-YYYY-MM-DD.md`: URL, which social videos were cut (ids + cuts), which library items and reviews were used (or any new AI footage and its prompts/scripts), the static's prompt, fal spend, anything the chat context was missing, and whether it was sent.

## Guardrails

- No fabricated stats, testimonials or results. DigiGrowth's only numeric claims are the stated guarantee and the offer terms in `context/offer.md`. Practice facts come from their own site; proof comes from their real reviews.
- AI actors voice the situation and the offer's facts only, never results or patient status. No AI/"dramatization" label (Dylan's standing call).
- The ads are labeled as examples (the top bar says so). Never upload or run them on the prospect's behalf.
- The demo agent costs real API spend per message on a public URL. It's rate-limited (30 messages/IP/hour, 400/page/day) and only answers on pages published with `--chat-context`. Republishing without the flag keeps the existing context; to switch a page's chat off: `UPDATE landing_pages SET chat_context = NULL WHERE slug = '<slug>'`.
- Model: `BLUEPRINT_CHAT_MODEL` env var (default `claude-opus-5-5`, low effort, ~3s replies).
- **Chat format (Dylan, 2026-10-05):** text-message length. Each reply is the answer (about 20 words), then the next question as a **separate** text, e.g. the insurance answer, then "What's been bothering you?". The backend splits on the blank line and the page shows two bubbles. Change it in `blueprint_chat.py`'s preamble, not per page.

## Completion Message

```
Patient Acquisition Blueprint — <business> — YYYY-MM-DD
Slug: <slug>
URL: <live url>
Chat: tested live (yes/no)
Sent to prospect: <no / how>
```
