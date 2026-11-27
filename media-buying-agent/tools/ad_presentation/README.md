# Ad-batch presentation: the default layout

Every approved ad batch is presented to the client as one Claude Artifact built from this kit
(Dylan, 2026-11-06: "save this presentation document as the default layout going forward").
Reference build: Pinnacle Physical Therapy batch 1, https://claude.ai/artifact/8FUY8QGEe4m7WZJUKbtA8d

## The layout (five sections, nothing else)

0. **Hero:** who it's prepared for, one headline, a one-paragraph lede, four fact tiles (the ads, made from, the offer, test budget).
1. **The offer:** name, struck anchor price next to the real price, scarcity badge, what's included, "why this offer" bullets.
2. **The funnel:** awareness ladder (unaware to most aware), each stage's job, ad chips placed on their stage (generated).
3. **Research:** three number cards (comments read, proven ads studied, their content reviewed) and three insight cards, each with a real quote.
4. **The ads:** one card per ad in funnel order (generated): media with a 9:16 / 4:5 toggle, stage and length, who it's for, why it works, what we did with their content, 3 ad texts in tabs, 5 headlines.
5. **How it runs:** "The setup" (four KPI cards: campaign, who sees it, budget, what counts) and "What happens after someone taps an ad" (numbered steps: ad, form, booking page, pays, visit) with a "Didn't book?" branch box (they get a call, then a text with the booking link if no answer).

Never add: a psychology-rules section, a separate "edits to your content" section, or a "what we need from you / before launch" section.

## Per client

1. Copy `template.html` to `clients/<slug>/creatives/_build/presentation_template.html`.
2. Rewrite every client-specific line: hero, offer box, funnel intro, the research cards, section 5's numbers and step text,
   footer, and the `:root` colors (`--accent`, `--accent-soft`, `--orange`, `--warm`) to the client's brand. Keep `{{LADDER}}` and `{{ADS}}`.
   The shared copy holds Pinnacle's text as the worked example: none of it may ship to another client.
3. Write `clients/<slug>/creatives/_build/presentation.json`:
   ```json
   {"ads": [{"k": "c1", "slug": "c1-folder-name", "stage": "Problem aware", "title": "...", "who": "...",
             "why": ["...", "..."], "changed": ["...", "..."], "static": false}],
    "stages": [{"name": "Unaware", "job": "...", "h": 60, "empty": "text shown when no ad sits on this stage"}]}
   ```
   `stage` must match a stage `name`; `h` is the riser height in px (60, 94, 128, 162, 196 for five stages); `static: true` for image ads.
4. `python media-buying-agent/tools/ad_presentation/build_presentation.py clients/<slug>/creatives <scratchpad>/presentation`
   (720p crf 27 previews, posters, index.html). Limits: 15 MB a file, 64 MB a publish.
5. Check it in a browser (serve the folder with `python -m http.server`, open via localhost), then publish `index.html` + `media/*`
   with `publish_files`. Republish to the same artifact when the batch changes, and put the link in `creatives/README.md`.

Write it for the client: plain language, no internal codes or file paths, never say who handles the calls ("they get a call").
