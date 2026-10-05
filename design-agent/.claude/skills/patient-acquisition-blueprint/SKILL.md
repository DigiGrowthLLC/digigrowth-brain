---
name: patient-acquisition-blueprint
description: Build a personalized Patient Acquisition Blueprint page for one PT practice prospect — AI-generated example ad creatives, a funnel preview in a phone frame, a LIVE AI appointment-setting chat agent trained on their own website, and an animated flow diagram of the whole engine (database reactivation + new ad leads + missed calls → AI agent → booked consult, with unbooked leads, no-shows and finished patients recycled back into reactivation). Hosted at /lp/<slug>. Use when Dylan says "run the blueprint for X", "build a patient acquisition blueprint", or wants a show-the-whole-system page for a prospect or a sales call.
---

# Patient Acquisition Blueprint

One page that shows a practice owner the entire AI Growth Engine built around *their* practice: what their ads would look like, the funnel those ads land on, an AI agent they can actually talk to, and how every lead that doesn't book gets recycled instead of lost.

How it differs from `landing-page-lead-magnet`: that page is a cold-SMS curiosity planter with a mockup of their site on top. The blueprint is the **full system walkthrough**, written to the practice owner from the first line, for a warmer moment: after a reply, before or during a discovery call, or as the follow-up after one. Its centerpiece is the live agent.

**One prospect at a time, in the foreground. Never background this skill.** (Standing rule across agents since the leadgen backgrounding incident.)

**Nothing is sent to the prospect without Dylan's explicit approval.** Publishing the page so Dylan can test the chat live is fine (step 9). Sending the link is a separate yes.

## How the page is built

The fixed parts live in `design-agent/references/blueprint-template.html`: the layout, the DigiGrowth navy/glass theme, the animated engine diagram, the chat widget, the guarantee close. Don't hand-edit a built page. Per prospect, you write:

- `blueprint.json`: all the copy, the ad data, the SMS examples, the agent's greeting/chips, and `chat_context` (schema in `design-agent/tools/build_blueprint.py`'s docstring; `references/blueprint-example.json` is a full worked example)
- `funnel.html`: a standalone patient-facing funnel page, shown inside a phone frame
- 3 ad images

`build_blueprint.py` fills the template, compresses the images and inlines everything into one `page.html`. The live chat posts to `/lp/<slug>/chat` (`dashboard/backend/routers/landing_pages.py` → `dashboard/backend/blueprint_chat.py`), which answers from `chat_context` stored on the page's `landing_pages` row. **Booking in the demo chat is simulated:** made-up open times, nothing written to any calendar, nobody texted.

If the template itself needs a design change (a better diagram, a new section), change `blueprint-template.html` so every future blueprint gets it, and rebuild.

## Steps

Work in a scratch folder, e.g. `<scratchpad>/blueprint-<slug>/`.

1. **Look up the prospect.**
   ```bash
   python design-agent/tools/lookup_prospect.py "<name or business>"
   ```
   Gives `contact_id`, `phone`, `website`, `owner`. If Dylan gave a website directly and there's no contact on file, carry on with the website alone and pass `-` as the contact_id in step 9.

2. **Scrape their site.**
   ```bash
   python design-agent/tools/scrape_prospect_site.py "<website>" "<scratch_dir>"
   ```
   Same tool and same rules as `landing-page-lead-magnet` step 2: read `page_text.txt` closely (services, offer, insurance/cash-pay, hours, location, real reviews), take colors from `palette.json`, take the logo and photos from `assets.json` as data URIs (sanity-check an SVG logo's fill before trusting it). **Look at `hero.png` too.** On Wix and similar builders the scraped "logo" is often a generic 24px site icon, and `palette.json` can miss the real brand color (it read white/blue on a black-and-red site). When that happens, crop the real wordmark out of `hero.png` with PIL, sample the brand color from its pixels, and set `brand.avatar_bg` to the logo's own background color (e.g. `#000000` for a logo cut from a black header).

3. **Read before writing.**
   - `media-buying-agent/context/ad-creative-principles.md` (the ads follow its Working Checklist)
   - `media-buying-agent/.claude/skills/generate-ad/SKILL.md`, the "Who can say what" rules
   - `design-agent/references/cro-funnel-principles.md` (for the funnel preview)
   - `apptset-agent/context/sms-setter-playbook.md`, "The facts you can use" (offer, guarantee, pilot terms: the only DigiGrowth claims the page may make)
   - `design-agent/references/blueprint-example.json`, for tone and length per field

4. **Write `chat_context`: the demo agent's whole knowledge of the practice.** Facts only, all from the scrape: name, city/area, who treats patients (credentials), services, the real first-visit offer (free consult/screen/discovery visit, as their site words it), insurance or cash-pay policy, superbills, hours, address, anything distinctive about their approach, and 1-2 real review snippets if they help. Plain sentences or short labeled lines, roughly 150-400 words. If the site doesn't say something (prices, insurance), leave it out. The agent is told to say "I'll have the team confirm" for anything missing, which is exactly what a good real agent does. Never pad with guesses: whatever's in here, the agent will state as fact to whoever's testing it.

5. **Generate 3 ad images.** Three distinct concepts, not variations, from their real services and patients:
   - 2 top-of-funnel (a specific patient avatar and situation: the weekend runner, the desk worker with neck pain, the post-op patient) and 1 bottom-of-funnel (one objection the site gives you material for: cash-pay/insurance, "will PT actually help", time).
   - Image prompt: the avatar unmistakable at a glance, in a believable PT clinic or real-life setting, concrete props for the vertical, harsh realism language (see the Ad Creative Realism memory). **No text in the image**: the hook goes on as an HTML overlay (`hook` field).
   - Run from `content-agent/`, under `doppler run` (the generator needs `FAL_KEY`). The three can run in parallel: put the commands in a small script with `&` + `wait` and run the script under one `doppler run`.
     ```bash
     doppler run --project digigrowth --config prd -- python tools/generate_creative.py image "<prompt>" --model nano-banana-pro --aspect 4:5 --out "<scratch_dir>/ads/ad1.png"
     ```
     Use `--model nano-banana-pro` for any concept with a clear human face. If fal returns a 403 "TOP_UP", fal is out of credit: tell Dylan, don't silently swap in stock photos.
   - Look at each image (Read it, inline) before using it. Regenerate anything with mangled hands, gibberish signage or an off setting.
   - Copy rules: hook → problem → solution → proof → CTA. Never assert the viewer's condition ("Your back pain..."), since Meta rejects it. Describe the situation instead. Proof comes only from the scrape (real reviews, first-name attribution) or is omitted. No fabricated testimonials, no AI actor presented as a patient. Fill `angle_label` with "Top of funnel" / "Bottom of funnel" and `angle` with the short angle name.

6. **Write `funnel.html`, the patient-facing funnel page that ad #1 clicks into.** A complete standalone HTML document designed for a ~375px-wide phone screen (it renders inside the phone frame via an iframe):
   - **Patient voice only**, exactly as in `landing-page-lead-magnet`'s Section 1 voice check: it *is* their page talking to a patient. No DigiGrowth, no "your practice", no meta.
   - Message match: the hero headline restates ad #1's promise. Their palette, their logo, at most 1 real photo from `assets.json`.
   - Structure per `cro-funnel-principles.md`, compressed for a phone: hero + one CTA button → trust line → 3 real services → 2 real reviews (if the scrape has them) → short FAQ (2-3) → the same CTA again. Buttons are visual only (`href="#"`).
   - Inline CSS, no JS needed, no external requests (system font stack). Keep it under ~250 KB with the photo. The `--p`/`--p-ink` brand variables don't reach inside the iframe, so set colors directly.

7. **Write `blueprint.json`.** Copy `references/blueprint-example.json` as a starting point for structure only; every word gets rewritten for this practice. Notes per field:
   - `slug`: `<business-slug>-blueprint`. Keep the `-blueprint` suffix so it never overwrites the same practice's lead-magnet page.
   - `brand.primary`/`primary_text`: their real button color and its text color from `palette.json` (the chat header, chat bubbles and ad avatar use these). Make sure the pair is readable.
   - `hero.headline`: about the practice's outcome, addressed to the owner. Wrap 2-4 words in `*asterisks*` for the gradient accent. Anchor numbers only to the real guarantee (10-20 booked consults in 6 weeks).
   - `agent.greeting` + 3 `chips`: what a real patient of *this* practice would type (one symptom question from their specialty, one insurance/cost question, one booking request).
   - `recovery.items`: four cards in this order: missed-call text-back, unbooked-lead follow-up, no-show recovery, database reactivation. Each has an example SMS thread in the practice's voice. **SMS text must be GSM-7 safe**: no em dashes, curly quotes, ellipses or emoji in `messages[].text` (the build warns). Use realistic first names, never real patients from the reviews.
   - `close_intro`: one or two sentences. The guarantee cards and the Calendly CTA are fixed in the template.
   - The template's engine diagram and guarantee wording are fixed. Don't restate their numbers differently elsewhere in the copy.

8. **Build and preview.**
   ```bash
   python design-agent/tools/build_blueprint.py "<scratch_dir>/blueprint.json" "<scratch_dir>/out"
   ```
   Fix every WARNING it prints. Then publish `<scratch_dir>/out/page.html` as a Claude Artifact so Dylan sees the page. In the Artifact the chat shows "runs on the published blueprint link", which is expected (the Artifact can't reach the backend). Check mobile too (force `.reveal{opacity:1 !important}` before screenshots, same gotcha as the lead-magnet skill; save screenshots under `.playwright-mcp/`, never the repo root).

9. **Publish for live testing** once the visual direction looks right:
   ```bash
   python design-agent/tools/publish_landing_page.py "<slug>" "<scratch_dir>/out/page.html" "<business>" "<contact_id or ->" --chat-context "<scratch_dir>/out/chat_context.txt"
   ```
   Prints the live URL. Give it to Dylan to test the agent himself. Run a quick smoke test yourself too: POST two messages to `<url>/chat` (a services question, then "can I book this week?") and confirm it answers from the practice's facts and offers two times. Revisions: edit the json or funnel, rebuild, re-run this same publish command (it upserts the same slug).

10. **Sending is a separate yes.** Only when Dylan explicitly asks to send it to the prospect. The landing-page SMS tool's locked wording is about the pilot mockup, so don't reuse it. Ask Dylan how he wants it delivered (text it himself, in a call follow-up, or a one-off SMS he approves word for word).

11. **Completion note** to `design-agent/outputs/blueprint-<slug>-YYYY-MM-DD.md`: URL, the 3 ad angles, image prompts used, anything the chat context was missing, and whether it was sent.

## Guardrails

- No fabricated stats, testimonials or results. DigiGrowth's only numeric claim is the stated guarantee. Practice facts come from their own site.
- The ads are labeled as examples (the top bar says so). Never upload or run them on the prospect's behalf.
- The demo agent costs real API spend per message on a public URL. It's rate-limited (30 messages/IP/hour, 400/page/day) and only answers on pages published with `--chat-context`. Republishing without the flag keeps the existing context, so to switch a page's chat off, clear it in SQL: `UPDATE landing_pages SET chat_context = NULL WHERE slug = '<slug>'`.
- Model: `BLUEPRINT_CHAT_MODEL` env var (default `claude-opus-5-5`, low effort, ~3-5s replies).

## Completion Message

```
Patient Acquisition Blueprint — <business> — YYYY-MM-DD
Slug: <slug>
URL: <live url>
Chat: tested live (yes/no)
Sent to prospect: <no / how>
```
