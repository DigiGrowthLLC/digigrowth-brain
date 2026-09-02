# DigiGrowth Outreach Video Skill
## Personalized "Loom" Generator — Fixed Headcam Pitch + Static Prospect Site Background

---

## SETUP (Run Once Per Machine)

```bash
pip install playwright
python -m playwright install chromium
```

`ffmpeg` must already be on PATH (used by `video-overlay` too).

---

## SKILL IDENTITY

You generate personalized cold-outreach videos at scale. Dylan records his talking-head pitch
**once** (`content-agent/raw/headcam-master.mp4`) — same script, same audio, every time. For each
prospect, this skill captures *their* website, held static at the top of the page, as the
background, composites Dylan's headcam clip as a small circle bubble bottom-left (classic Loom
look, framed left-of-center per his framing preference), and mixes the headcam's audio back in —
so every send looks like it was recorded live on their site, without re-recording anything.

This is the automated version of the production note in
`content-agent/outputs/cold-loom-script-*.md`: "record on their actual website... screen-shared
behind you."

---

## TRIGGER

Activate this skill when the user says:
- "make an outreach video for [prospect]", "personalize my loom for [prospect]"
- "run the loom skill for [prospect]"
- "generate outreach videos for [list of leads]"
- "outreach video skill"

---

## LOCKED FORMAT DECISIONS (do not change without being asked)

- **Background stays static at the top of the page — no scrolling.** An earlier auto-scrolling
  version was scrapped because the motion read as unnatural. `record_site_scroll.py` holds the
  viewport at scroll position 0 for the full clip duration; do not reintroduce scrolling.
- **Headcam bubble crop keeps Dylan centered with the room's mirror fully cropped out**
  (`CROP_X_SHIFT = -60` in `compose_outreach_video.py`), tuned against `headcam-master.mp4`. If a
  new/different headcam master clip is ever swapped in, re-check this offset against a frame grab
  before trusting the default — render a few offset previews and pick the one that centers him with
  no mirror visible.
- **Finished videos get sent automatically**, not just generated. The skill publishes the watch
  link and texts it to the prospect via the active sequence's primed-message step (Step 8) unless
  Dylan explicitly asks to skip sending.

---

## WORKFLOW

### STEP 1 — Confirm the master headcam clip (once, reused forever)
Check `content-agent/raw/headcam-master.mp4` exists. If missing, stop and ask Dylan to drop his
pitch recording there (normal room, no over-production — per the cold-loom-script production
notes). Do not proceed without it.

### STEP 2 — Resolve the prospect's website, per prospect
- If given a business name: run
  ```bash
  python content-agent/tools/lookup_lead.py "<business name>"
  ```
  This queries the OS's own contacts via `GET {DASHBOARD_URL}/api/contacts?search=<name>&limit=1`
  (Doppler-sourced creds, mirrors how `leadgen-agent` already talks to the OS).
  - `NOT FOUND` or "no website on file" → ask Dylan to paste the URL directly. Do not guess a URL.
- If given a URL directly, skip lookup.

### STEP 3 — Get the headcam clip's duration
```bash
ffprobe -v error -show_entries format=duration -of csv=p=0 content-agent/raw/headcam-master.mp4
```

### STEP 4 — Capture the site background
```bash
python content-agent/tools/record_site_scroll.py "<url>" <duration_seconds> "<tmp_path>/site-scroll.mp4"
```
This launches headless Chromium at 1920x1080, loads the page, and holds it **static at the top —
no scrolling** for the full duration (see Locked Format Decisions above), outputting a video-only
mp4.

### STEP 5 — Composite
```bash
python content-agent/tools/compose_outreach_video.py \
  "content-agent/raw/headcam-master.mp4" \
  "<tmp_path>/site-scroll.mp4" \
  "content-agent/exports/outreach-videos/<business-slug>-<YYYY-MM-DD>.mp4"
```
Circle bubble bottom-left, audio taken from the headcam clip only.

### STEP 6 — Verify
```bash
ffprobe -v error -show_streams "content-agent/exports/outreach-videos/<file>.mp4"
```
Confirm both a video and an audio stream, and duration close to the headcam clip's. Extract 1-2
frames and read them to confirm the bubble looks right and isn't covering key site content:
```bash
ffmpeg -y -ss <T> -i "<output>.mp4" -frames:v 1 -update 1 "<scratchpad>/verify-<T>.jpg"
```

### STEP 7 — Publish a texting-safe link
Raw `.mp4` files should never be sent directly by SMS/MMS — carriers cap MMS video size (~1–5MB,
these clips run 15–30MB) and will strip, recompress, or drop them entirely. Instead, publish to the
OS's own public watch page:
```bash
python content-agent/tools/publish_to_watch.py \
  "content-agent/exports/outreach-videos/<file>.mp4" "<business-slug>" "<Business Name>"
```
This uploads the video to the OS (stored via GitHub, served through a public, unauthenticated
`/watch/<slug>` route with Open Graph video tags so iMessage/RCS render an inline preview card) and
prints back a `WATCH_URL`. Report that URL to Dylan — that's the link that goes in the SMS, not the
local file path.

### STEP 8 — Send it to the prospect automatically
This runs unless Dylan explicitly says just to generate the video without sending it. Send using
the **active SMS sequence's "2. Primed Message" step** (the `relevance` key in
`dashboard/backend/routers/sms.py`'s `SEQUENCE_STEPS` — currently sequence "Free Offer V.1.3",
template `[Loom link] Shoot me a 👍 once you've watched it`), with the placeholder swapped for the
real watch URL:
```bash
python content-agent/tools/send_outreach_sms.py "<prospect phone from Step 2>" "<WATCH_URL>"
```
This looks up whichever `sms_sequences` row currently has `is_active = true` (don't hardcode a
sequence name/id — it can change), substitutes the watch URL into its primed-message template, and
sends via `POST /api/sms/send` tagged `stage="relevance"` so it shows correctly in the SMS
inbox/sequence dropdown. If no sequence is active, or the active sequence's primed-message step has
no Loom-link placeholder, it exits with a clear error instead of guessing — surface that to Dylan
rather than sending something wrong.

### STEP 9 — Report
Tell Dylan: the watch URL, the local file path (reference/archival), and that the primed-message
text was sent (or why it wasn't, if Step 8 errored).

### Batch runs
When given multiple leads in one request, repeat Steps 2–9 **one prospect at a time, in the
foreground**. Do not background this work — unattended runs in this repo have silently died when
backgrounded before (see the leadgen scraping backgrounding incident). Report each watch URL (and
send result) as it finishes rather than batching all reports to the end.

---

## WHAT THIS SKILL DOES NOT DO

- Write or adapt the pitch script → that's the existing cold-loom-script workflow
- Upload to a third-party host (Loom, YouTube, etc.) — it publishes to the OS's own `/watch/<slug>`
  page instead (see Step 7)
- Invent its own outreach copy for the text — it always uses whatever sequence is currently marked
  active in Business Resources → Outreach Templates (see Step 8), never a hardcoded message
- Add captions, lower-thirds, or brand graphics — that's `video-overlay`/`embedded-captions`
  territory and would clash with the raw, personal Loom look this format is going for
- Re-record or edit the headcam clip itself

---

## INVOCATION

```
/outreach-video [business name or URL]
```

Or naturally:
> "Make an outreach video for [prospect]"
> "Generate outreach videos for [lead 1], [lead 2], [lead 3]"
