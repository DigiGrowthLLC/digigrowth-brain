---
name: patient-acquisition-blueprint
description: Build a personalized Patient Acquisition Blueprint page for one PT practice prospect that Dylan walks through on a sales call, always in the default Rise & Reframe format: header lockup + section selector band, the engine overview, ads (3 cuts of the practice's own social videos + the 3 default AI ads: two AI UGC actors and an AI review-card static, catered to the prospect by design-agent/tools/default_ai_ads.py), the funnel in desktop + phone frames plus the booking page we build, a LIVE AI text agent, a live in-browser voice agent demo, reactivation + follow-up with the real portal messaging, social, and the guarantee. Hosted at /lp/<slug>. Use when Dylan says "run the blueprint for X", "build a patient acquisition blueprint", or wants a show-the-whole-system page for a prospect. Also builds the FOUNDATIONS version ($500/mo package: SEO website, AI text agent, reactivation, follow-up, the math, no ads or guarantee) when he says "Foundations blueprint for X" or names the Foundations package.
---

# Patient Acquisition Blueprint

One page that shows a practice owner the entire Digital Growth Engine built around *their* practice: what their ads would look like, the funnel those ads land on, an AI agent they can actually talk to, how their existing list gets reactivated, and how every lead that doesn't book gets recycled instead of lost.

How it differs from `landing-page-lead-magnet`: that page is a cold-SMS curiosity planter with a mockup of their site on top. The blueprint is the **full system walkthrough**, written to the practice owner from the first line, for prospects **already on a sales call** with Dylan: he walks them through it live (and may send the link after). Its centerpiece is the live agent. It has no booking CTA, since the prospect is already on the call.

**One prospect at a time, in the foreground. Never background this skill.** (Standing rule across agents since the leadgen backgrounding incident.)

**Nothing is sent to the prospect without Dylan's explicit approval.** Publishing the page so Dylan can test it live is fine (step 10). Sending the link is a separate yes.

## THE DEFAULT FORMAT: Rise & Reframe (Dylan, 2026-11-22)

**Every growth blueprint uses this exact format.** Only the prospect and business change. Reference: Rise & Reframe Physical Therapy (BettyLou DeYoung, Temecula), live at `pages.digigrowthllc.com/lp/rise-reframe-physical-therapy-blueprint`, source in `design-agent/outputs/blueprints/rise-reframe-physical-therapy-blueprint/`. **Start every new blueprint by copying its `blueprint.json`** and rewriting every fact for the new practice; keep its structure, section set, lengths and tone. The template and build script render everything below automatically.

Blueprints are presented on the discovery call, almost never sent, so every section must read at a glance.

**Page, top to bottom:**
1. **Header bar**: clinic logo × glowing blue × × DigiGrowth wordmark (the client-portal lockup). Then the hero: kicker + headline only (no subhead, spec row or "Prepared for" bar).
2. **Section selector band** (`secbar`, automatic): full-width, glowing lines top and bottom, every section with its page number + icon, each a link.
3. **00 System overview**: the animated engine diagram + 6 step cards (`step_blurbs`: ads, funnel + booking page, text agent, voice agent, reactivation + follow-up, social).
4. **01 Ads**: row 1 "Cut from your own videos" = 3 cuts of their social videos; row 2 = **the 3 default AI ads** in this order: AI UGC "Back by Thursday", AI static review card, AI UGC "Back to Square One" (step 6).
5. **02 Funnel**: three "why" cards, the funnel in desktop + phone frames, then **"Then a booking page we build for you"**: 5 benefit cards above a live render of the real DigiGrowth Booking page filled from `"booking"` (photo, logo, provider, ONE review + the real Google count, what to expect, event with price/anchor cents and spots). Simulated times; submitting shows a demo note.
6. **03 Text agent**: the live chat, scenarios `meta_lead`, `reactivation`, `missed_call` (never `website`: DigiGrowth has no website chat).
7. **04 Voice agent**: the timeline + the live in-browser voice demo (same voice settings as Advantage Therapy's agent: 11labs-Kate, 1.2x, tuned, "Jamie"; `dashboard/backend/blueprint_voice.py`).
8. **05 Reactivation + follow-up** (one section): the real playbooks (`client_reactivation.PLAYBOOKS`): "Check-in, from Dr. <name>" every 90 days (texts as the owner, offers the $49 visit only once they mention a problem) + "Last call, when the ad budget is spent" (text, then a `{"from": "event"}` marker "No reply? Next day the AI voice agent calls", then the booking). Then "Plus three automatic follow-ups" from the real sequences: lead didn't book (Pinnacle's $49 `prospect_followup` wording), started booking but didn't finish (the booking-abandon text with the link), no-show. Never "missed call text-back" (not a client automation).
9. **06 Social**: posts grid + DM agent, no "booster" note.
10. **07 Guarantee**: headline + one-line `close_intro`, an open stat row (24/7 live results, 7 guaranteed, $0 retainer) with gradient numbers and a rotating "7 minimum" seal. The page ends there.

**Writing rules:** every intro ONE sentence (~15 words), headlines under ~8 words, card texts under ~10 words; no key tiles or point chips anywhere (no `engine_keys`, `keys` or `points`); complex ideas shown visually. Every CTA/end card carries the verified Google rating (Places API, never guessed), struck $150 + $49, "Only 10 spots this month" and one button. Funnel CTAs: no "A full evaluation is normally $150" note under the price. Ad primary texts end with the rating line and "Only 10 spots this month". All SMS GSM-7 safe.

**Own-video cuts**: word-level transcribe (faster-whisper), cut on word gaps, hook card 0-3s, name lower-third, 4s `ov.offer_end_card` crossfaded in. Keep the source's burned-in captions if it has them and add none (no blur strips); move them down if the hook card covers them (Rise & Reframe's `scripts/build_r3.py` + the caption-move note in its README entry). No star badge on the video. If the channel has fewer than 3 good shorts, check its long videos (`/videos`) for a usable 20-50s cut. Funnel hero photo: crop so the hands-on treatment shows.

Rejected along the way (don't bring back): the Boulder "keeps coming back" checklist static, the basic CrosaCore review-card statics (`corporate-shanti`/`dawn`), 13-15s UGCs, a blur strip over source captions, a divider / offer strip / plan-at-a-glance cards under the hero, green guarantee boxes, a reviewer name on the static.

**Older formats (history only, don't use for new growth blueprints):** Boulder Body Solutions (2026-10-28, `outputs/blueprints/boulder-body-solutions-blueprint/`: 1 UGC + 2 statics) and Advantage Therapy (2026-10-05, `references/blueprint-example.json`).

## Foundations package (back-end only)

**The approved Foundations format is Exceptional Solutions PT (Samantha Newell, 2026-10-08).** Start every Foundations blueprint by copying `references/blueprint-example-foundations.json` (her full blueprint.json, the field-by-field template) and `references/foundations-example-site.html` (her 10-page SEO website), then rewrite every word and fact for the new practice. Her live page is the visual reference: `pages.digigrowthllc.com/lp/exceptional-solutions-pt-blueprint`; her source files are in `outputs/blueprints/exceptional-solutions-pt-blueprint/`.

When Dylan asks for a blueprint "for the Foundations package" (his smaller tier, $500/month: the back-end systems plus a patient booking page, no ads, **no guarantee**), set `"package": "foundations"` in `blueprint.json`. The build then drops the Ads and Guarantee sections and ends with an "included" block (with `price`/`price_note`) instead. Skip steps 4 and 6 (no social videos, no ads). **Instead of a one-page funnel, Foundations gets a multi-page SEO website** (Dylan, 2026-10-08): one hash-routed HTML file (`#/about`, `#/ehlers-danlos-syndrome` ...) with Home, About, one page per condition the practice treats, Approach, Insurance, Reviews, FAQ, Contact; a per-page title + meta description (`data-title`), one H1 each, LocalBusiness/Physiotherapy + FAQPage JSON-LD, name/address/phone in the footer, internal links, a mobile menu. Give it as `funnel` with `"label": "SEO website"`, `step_title`, `html_file`, and optionally `pages` (route, path, title, description, target keyword) for a clickable "SEO map" (Dylan removed it from the Exceptional Solutions page, so leave it out by default). Worked example: `references/foundations-example-site.html`. Per the client-funnel rule every CTA is a **free consultation held as a Google Meet video call**, no prices (the insurance page lists plans only); `chat_context` books that same free consultation. Give 4 `step_blurbs` (website, agent, reactivation, recovery). Leave out `ads` and `close_intro`. Add `included` (with the price), and a `math` block with **fixed `outcomes`** (Dylan: no calculator, prospects don't know their numbers): time back, estimated added revenue, fewer no-shows, return, each computed from cited research and the practice's own prices, each with a `how` line showing the math and its source (Dylan wants the prospect to see how every estimate was made). Label any assumption as an assumption ("we assume about 30 inquiries a month"), never as a fact. Cite only real, linked studies in `stats` (shown as "Based on" chips); never an unsourced number like "62% of calls go unanswered", and never claim results "from our past clients" unless Dylan supplies that data. The page must not mention ads, the guarantee or the $49 assessment, and must say the agent is text-only (SMS + web chat). Worked example: `outputs/blueprint-exceptional-solutions-pt-blueprint-2026-10-08.md`.

## The page

Fixed by `design-agent/references/blueprint-template.html` (DigiGrowth navy/glass theme; the practice's own colors only inside the ads, funnel, booking page and chat). Section order and content: THE DEFAULT FORMAT above.


Per prospect you write `blueprint.json` (all copy, ad data, SMS examples, chat greeting/chips, `chat_context`; schema in `design-agent/tools/build_blueprint.py`'s docstring), `funnel.html`, and the ad media. `build_blueprint.py` fills the template, inlines images and the funnel, and copies videos to `out/assets/` for upload. The live chat posts to `/lp/<slug>/chat` (`dashboard/backend/routers/landing_pages.py` → `dashboard/backend/blueprint_chat.py`), answering from `chat_context` stored on the page's `landing_pages` row. **Booking in the demo chat is simulated:** made-up open times, nothing written to any calendar, nobody texted.

If the page itself needs a design change, change `blueprint-template.html` (or the build script) so every future blueprint gets it, and rebuild. Don't hand-edit a built page.

**No emoji anywhere, on the blueprint or the funnel** (Dylan, 2026-10-08: they read generic, not technical). The shell uses line-icon SVGs from `ICONS` in `build_blueprint.py`; a `funnel.why[].icon` or `recovery.items[].icon` names one of those keys (e.g. `target`, `ban`, `pointer`, `phone`, `clock`, `calendarx`) or is left out for the default. The funnel uses inline SVG icons too; `references/blueprint-example-funnel.html` (Pinnacle, 2026-10-08) is the current style reference: floating rating badge on the hero photo, icon trust strip, review cards with initial avatars, numbered Discovery-style steps, icon cards, accordion FAQ, sticky mobile CTA. Don't name a CSS class `.s`, `.n` etc. inside a component when a section already uses it (a `.s` badge once inherited the section's 44px padding).

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
   - **Edit 3 of them into ads** the default way (THE DEFAULT FORMAT, "Own-video cuts"): the strongest 15-50s, **cut their organic calls to action** ("comment X", "learn more in the caption", "text me"), hook card, name lower-third, the $49 offer end card with rating + 10 spots. Rise & Reframe's `scripts/build_r3.py` (`own()`) is the builder to adapt. Re-encode to 720x1280, H.264 CRF ~26, AAC 96k, `+faststart`, under ~8 MB each. These go in `ads.video_items`. Real before/afters are fine for the preview, but flag to Dylan that Meta can restrict before/after health imagery if they ever run as real ads.

5. **Write `chat_context`: the demo agent's whole knowledge of the practice.** Facts only, all from the scrape: name, area, clinicians and credentials, approach, conditions, services, the real first step (free consult/phone consult/screen, as their site words it), prices if the site lists them, the $49 assessment offer with its regular price and monthly limit as the funnel states them (e.g. "The $49 assessment is normally $150; only 10 open each month"; Auto-Setup carries this into the client's AI agent and follow-up texts), insurance/cash-pay, HSA/FSA, superbills, hours, address, contact method, 1-2 real review snippets. Plain sentences or labeled lines, roughly 150-450 words. If the site doesn't say something, leave it out: the agent says "I'll have the team confirm" for anything missing. Never pad with guesses, since the agent states whatever is here as fact.

6. **Make the 3 default AI ads** (Dylan, 2026-11-22: the Rise & Reframe set, catered to each prospect):
   ```bash
   doppler run --project digigrowth --config prd -- python design-agent/tools/default_ai_ads.py "<scratch_dir>/blueprint.json" --generate
   ```
   Fill the blueprint's `ai_ads` block first (copy Rise & Reframe's): `city`, `areas`, `doctor_short` (+ `doctor_spoken` if the voice needs a spelling), `doctor_line`, `offer` (name, was/now, spots and their spoken forms), the verified `rating`, `end_footer`, `palette` (their near-black `card`, brand `accent`), 3 **different** real reviews (`thursday` and `square_one` = full quote + "FIRST · REAL GOOGLE REVIEW"; `static` = a short 3-line quote naming a body part), and `photo` (`therapist` = the practitioner's gender, `body_part` from the static quote). The tool:
   - generates 4 Veo 3.1 Fast takes of the two CrosaCore actors (~$1.20 each) saying "there's a PT in <city> ... one-on-one" + "$150 → $49, only 10 spots a month", and one nano-banana-pro photo (~$0.15). Needs fal credit (403 "TOP_UP" / "Exhausted balance" = out of credit: tell Dylan).
   - checks each take against the script (prints "match NN%"; a WARNING under 90% means listen, then regenerate or set a manual `segs` trim), trims to the last word, cuts a repeated word, captions in the source style, and assembles the actor's generic first line → 2 new lines → ONE review card → offer end card (~25-30s).
   - builds the static: rating + areas on top, the short quote, the AI photo (~670px of 1350), name pill, offer strip, Book Now. No reviewer name on it.
   It writes `ads/ugc-thursday-web.mp4`, `ads/static_review.jpg`, `ads/ugc-square-one-web.mp4` (+ posters) next to `blueprint.json`. Look at a frame sheet of each before building. `ads.items` = those three in that order, primary texts/headlines adapted from Rise & Reframe's. Actors voice the situation and the offer's facts only, never results; "spots", never "she only takes 10 patients".

7. **Write `funnel.html`, the patient-facing page ad #1 clicks into.** A complete standalone, **responsive** HTML document; the blueprint shows it twice, in a phone frame (~375px) and in a desktop browser frame (rendered at 1280px, scaled down). Design mobile first, then a `@media (min-width:900px)` layer: two-column hero (copy left, photo right), a CTA button in the header, a 3-column review wall.
   - **Patient voice only**, exactly as in `landing-page-lead-magnet`'s Section 1 voice check: it *is* their page talking to a patient. No DigiGrowth, no "your practice", no meta.
   - **The patient offer is the $49 assessment** (per `context/offer.md`): the hero, CTA and FAQ sell a $49 assessment ("normally $X", using the practice's real assessment/eval price from their site, or $150 if it isn't shown), paid when booking, with **only 10 spots each month** (the default limit in `offer.md`, unless the practice's capacity says otherwise). The CTA reads like "Book your $49 assessment". No "free consult".
   - **Price anchor + scarcity on the page by default, big and impossible to miss** (Dylan, 2026-11-05: small grey text was "barely visible"; live on Pinnacle's funnel `/lp/pinnacle-physical-therapy-5`, copy its `.deal` CSS): a bordered price card **above the hero CTA**, in the offer section under its heading, and above the final CTA, holding a large red struck-through `$150`, a ~48px accent-colored `$49`, a red "SAVE $101" pill and a pulsing red dot + "Only **10 spots** each month". The sticky mobile bar shows a red struck `$150`, a bold ~24px `$49` and a red "Only 10 spots/month". Also in the FAQ cost answer ("Our first visit is normally $150. The [assessment] is $49, paid when you book. We only open 10 each month...") and in the final CTA ("Normally $150, now $49. We only open 10 each month, so grab yours while spots are open."). Real limit only: no countdown timers or fake "2 left".
   - Message match: the hero headline restates the first ad's promise. Their palette, their logo, 1-2 real photos (from `assets.json`, or a clean frame from their own video, cropped above any burned-in caption).
   - **Check every photo before using it.** Site hero images are often wide banners with a dark fade on one side for text; in a small frame they look like a dark sliver. Crop to the real subject.
   - **Social proof leads.** Per `cro-funnel-principles.md`: hero + one CTA + a "5.0 on Google" line (only a rating the site itself shows) → trust bar → **wall of 6 real reviews** → good-fit list → 3 real treatment approaches → short FAQ (price, insurance, location) → the same CTA again. Buttons are visual only (`href="#"`).
   - **Every section uses the same container width and left alignment** (Dylan, 2026-10-05: a narrower, centered FAQ looked out of place). Scope row styles to the rows (`.faq .w>div`), never a bare `.faq div`, which also hits the container and strips its padding.
   - ~38px of top padding on the mobile header so the phone notch doesn't clip the logo; hide the page's scrollbar (`html{scrollbar-width:none}` + `::-webkit-scrollbar{display:none}`) so the desktop preview looks clean.
   - Inline CSS, no JS, no external requests (system font stack), under ~250 KB with photos. The `--p`/`--p-ink` variables don't reach inside the iframe, so set colors directly.

8. **Write `blueprint.json`.** Start from Rise & Reframe's (`outputs/blueprints/rise-reframe-physical-therapy-blueprint/blueprint.json`); keep every block, rewrite every word and fact for this practice.
   - `slug`: `<business-slug>-blueprint` (the suffix keeps it from overwriting the practice's lead-magnet page).
   - `brand.primary`/`primary_text`/`avatar_bg`: real button color and its text color (chat header, bubbles, ad avatars), and the logo's background color.
   - `hero.headline`: the practice's outcome, addressed to the owner, 2-4 words in `*asterisks*` for the gradient accent. Anchor numbers only to the real offer (7-10 paid assessments in the first 30 days, 7 guaranteed). No subheading.
   - `engine_intro`: personalize it to something real on their site (Advantage: "your site says you text and don't take calls" set up the missed-call angle).
   - `step_blurbs`: six: ads, funnel + booking page, text agent, voice agent, reactivation + follow-up, social.
   - `ads.intro`, `ads.video_items` (step 4), `ads.items` (step 6).
   - `funnel`: `headline`/`intro`/`why` answer "I already have a website": their site is good and stays, but a site is built to inform, while an ad click needs one reason and one way to book. Three `why` cards: only the information that gets someone to book; no distractions (no menu, articles, links away); one choice, since too many options cause decision paralysis. `url` is the address shown in the browser bar (their domain + `/assessment`). `points` are the four ticks under the devices.
   - `agent.greeting` + 3 `chips`: what a real patient of this practice would type (a symptom from their specialty, insurance/cost, a booking request for the $49 assessment).
   - `reactivation` + `recovery`: the real playbooks and sequences as in THE DEFAULT FORMAT (check-in from the owner, last call + event marker; lead didn't book, started booking, no-show). No email, no missed-call text-back.
   - `booking`: the practice's booking page data (default format, point 5); its `url` is `booking.digigrowthllc.com/<their-slug>`.
   - All SMS text must be **GSM-7 safe** (no em dashes, curly quotes, ellipses or emoji; the build warns). Use realistic first names, never real patients from the reviews.
   - `close_intro`: one sentence above the guarantee stats. The page deliberately ends there, with no booking CTA.

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

12. **Save the source for Dylan's sales call.** Copy the prospect's `blueprint.json`, funnel/site source + built HTML, logo, photos, `page_text.txt` and `out/page.html` + `out/chat_context.txt` (into `built/`) to `design-agent/outputs/blueprints/<slug>/`, and add a row plus a short "worth knowing for the call" block to `design-agent/outputs/blueprints/README.md`. The scratch folder is temporary; without this the page can't be edited later. Leave large video files out (they're in R2; the README says how to pull them back).

13. **Completion note** to `design-agent/outputs/blueprint-<slug>-YYYY-MM-DD.md`: URL, which social videos were cut (ids + cuts), which library items and reviews were used (or any new AI footage and its prompts/scripts), the static's prompt, fal spend, anything the chat context was missing, and whether it was sent.

## Guardrails

- No fabricated stats, testimonials or results. DigiGrowth's only numeric claims are the stated guarantee and the offer terms in `context/offer.md`. Practice facts come from their own site; proof comes from their real reviews.
- AI actors voice the situation and the offer's facts only, never results or patient status. No AI/"dramatization" label (Dylan's standing call).
- The ads are examples for the call. Never upload or run them on the prospect's behalf.
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
