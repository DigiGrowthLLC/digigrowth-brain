# DigiGrowth Video Overlay Skill
## HyperFrames Branded Talking-Head Overlay Agent

---

## SETUP (Run Once Per Machine)

```bash
GIT_LFS_SKIP_SMUDGE=1 npx skills add heygen-com/hyperframes --all
npx hyperframes browser ensure
npx hyperframes doctor
```

---

## SKILL IDENTITY

You are the HyperFrames branded overlay agent for DigiGrowth. Given a raw talking-head `.mp4` and a transcript, you build a polished `public/index.html` composition — dark navy glassmorphism cards + pill badges + floating text graphics, all synced to the transcript — then render and mux the audio back in.

Visual reference for this skill's output style: `content-agent/projects/cant-code-video/output-v5-final.mp4`

---

## TRIGGER

Activate this skill when the user says:
- "add graphics to my video", "add overlays", "brand my video", "video overlay"
- "talking head overlay", "graphics like my last video"
- Points to a `.mp4` file and asks to add graphics

---

## BRAND SYSTEM

Apply these tokens to every card, pill, and text overlay. Never deviate unless explicitly told to.

### Colors
```
--brand-blue:   #3a7bd5        /* kickers, bullets, pill borders, accent borders */
--brand-navy:   #090f26        /* card background base */
--brand-green:  #14c882        /* positive/automation cards — kicker, dots, border */
--text-white:   #ffffff
--text-dim:     rgba(255,255,255,0.52)
--text-faint:   rgba(255,255,255,0.38)
--border-glass: rgba(58,123,213,0.28)
--border-acc:   rgba(58,123,213,0.70)
```

### Glass Card Base (used by all card-type overlays)
```css
background: linear-gradient(155deg, rgba(58,123,213,0.18) 0%, rgba(9,15,38,0.93) 48%);
border: 1px solid rgba(58,123,213,0.28);
border-radius: 10px;
box-shadow: 0 8px 32px rgba(0,0,0,0.65),
            0 0 20px rgba(58,123,213,0.15),
            inset 0 1px 0 rgba(255,255,255,0.06);
backdrop-filter: blur(12px);
```
Accent side border — add AFTER the base border declaration:
```css
border-left:   3px solid rgba(58,123,213,0.70);  /* left-panel cards */
border-right:  3px solid rgba(58,123,213,0.70);  /* right-panel cards */
border-bottom: 3px solid rgba(58,123,213,0.70);  /* lower-corner cards */
/* For green variant, replace rgba(58,123,213,…) with rgba(20,200,130,…) */
```

### Kicker Label
```css
font-size: 10px; font-weight: 700; letter-spacing: 3px;
text-transform: uppercase; color: #3a7bd5; margin-bottom: 14px;
/* Green variant: color: #14c882 */
```

### Bullet Dots
```css
.bdot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; margin-top: 6px; }
.bdot-blue  { background: #3a7bd5; box-shadow: 0 0 8px rgba(58,123,213,0.8); }
.bdot-green { background: #14c882; box-shadow: 0 0 8px rgba(20,200,130,0.8); }
.bdot-dim   { background: rgba(255,255,255,0.30); }
```

---

## POSITION CLASSES

```css
/* Face safe zones (1920×1080): face x=468–1451, chin y≈706 */

.hook-c {                           /* centred title, above head */
  position: absolute;
  left: 50%; transform: translateX(-50%);
  top: 50px; min-width: 620px; text-align: center;
  /* Use glass card base + border-top: 3px solid #3a7bd5 */
}
.lp {                               /* left panel, vertically centred */
  position: absolute;
  left: 60px; top: 50%; transform: translateY(-50%);
  width: 360px;
  /* glass base + border-left: 3px solid rgba(58,123,213,0.70) */
}
.rp {                               /* right panel, vertically centred */
  position: absolute;
  right: 60px; top: 50%; transform: translateY(-50%);
  width: 380px;
  /* glass base + border-right */
}
.ll {                               /* lower-left corner */
  position: absolute;
  left: 80px; bottom: 70px; max-width: 700px;
  /* glass base + border-bottom */
}
.lr {                               /* lower-right corner */
  position: absolute;
  right: 80px; bottom: 70px; max-width: 700px;
  /* glass base + border-bottom */
}
.tp {                               /* tool pill badge — upper-left */
  position: absolute;
  left: 60px; top: 80px;
  /* see pill card type below */
}
.fl {                               /* floating text list — left side, no background */
  position: absolute;
  left: 80px; top: 200px;
}
.ch-lower {                         /* chapter lower-third — bottom-left pill */
  position: absolute;
  left: 60px; bottom: 60px;
  /* see chapter pill type below */
}
```

---

## CARD TYPE TEMPLATES

### 1. Hook Card — `.hook-c`
Centred below face. Used for opening title only.

```html
<div id="c01" class="hook-c">
  <div id="c01-h" style="font-size:62px;font-weight:700;color:#fff;letter-spacing:-1px;
    line-height:1.05;text-shadow:0 0 32px rgba(58,123,213,0.55);">
    <span class="cc">W</span><span class="cc">O</span><span class="cc">R</span>
    <span class="cc">D</span><span class="cc">S</span><span class="cc">.</span>
  </div>
  <div id="c01-s" style="font-size:20px;color:rgba(255,255,255,0.52);margin-top:10px;opacity:0;">
    Subtitle line here.
  </div>
</div>
```
GSAP: `tl.from('#c01-h .cc', {opacity:0,y:10,scale:0.8,duration:0.3,ease:'back.out(2)',stagger:0.04}, t+0.10);`
`tl.to('#c01-s', {opacity:1,duration:0.5}, t+3.0);`

---

### 2. Stat Counter — `.lp`
Number counts up when shown. Use for any numeric callout.

```html
<div class="lp" style="[glass base] border-left:3px solid rgba(58,123,213,0.70);">
  <div class="kk">THE OLD WAY</div>
  <div id="c-num" style="font-size:88px;font-weight:700;color:#3a7bd5;line-height:1;
    text-shadow:0 0 30px rgba(58,123,213,0.55);">0</div>
  <div style="font-size:18px;color:rgba(255,255,255,0.52);margin-top:6px;">descriptor text here.</div>
</div>
```
GSAP count-up:
```js
;(function(){ var o={v:0};
  tl.to(o,{v:TARGET_NUMBER,duration:2.2,ease:'power2.out',onUpdate:function(){
    var el=document.querySelector('#c-num'); if(el) el.textContent=Math.round(o.v).toLocaleString();
  }}, TRIGGER_TIME);
})();
```

---

### 3. Pull Quote — `.lr` or `.ll`
Italic context + bold statement with one blue emphasis word.

```html
<div class="lr" style="[glass base] border-bottom:3px solid rgba(58,123,213,0.70);">
  <div id="c-l1" style="font-size:19px;color:rgba(255,255,255,0.48);font-style:italic;
    margin-bottom:8px;opacity:0;">Context sentence here.</div>
  <div id="c-l2" style="font-size:26px;font-weight:700;color:#fff;line-height:1.3;opacity:0;">
    Bold statement with <span style="color:#3a7bd5;">key word</span> highlighted.
  </div>
</div>
```

---

### 4. Bullet List — Old Way — `.lp`
Dim dots, items reveal as spoken. Use for "the hard/manual way".

```html
<div class="lp" style="[glass base] border-left:3px solid rgba(58,123,213,0.70);">
  <div class="kk">OLD WAY</div>
  <div id="c-a" class="brow"><div class="bdot bdot-dim"></div><div class="btxt">Step one</div></div>
  <div id="c-b" class="brow"><div class="bdot bdot-dim"></div><div class="btxt">Step two</div></div>
  <div id="c-c" class="brow"><div class="bdot bdot-dim"></div><div class="btxt">Step three</div></div>
  <div id="c-x" style="font-size:17px;font-weight:700;color:rgba(255,255,255,0.40);
    margin-top:10px;padding-top:10px;border-top:1px solid rgba(255,255,255,0.08);opacity:0;">
    Manual. All me.
  </div>
</div>
```
Shared row class: `.brow { display:flex;align-items:flex-start;gap:14px;padding:7px 0;opacity:0; }`
`.btxt { font-size:22px;font-weight:500;color:#fff;line-height:1.3; }`

---

### 5. Bullet List — New Way / Automated — `.rp`
Green dots and green kicker. Use for "the system/automated way".

```html
<div class="rp" style="[glass base] border-right:3px solid rgba(20,200,130,0.68);">
  <div class="kk" style="color:#14c882;">NOW →</div>
  <div id="c-a" class="brow"><div class="bdot bdot-green"></div><div class="btxt">It does X.</div></div>
  <div id="c-b" class="brow"><div class="bdot bdot-green"></div><div class="btxt">It does Y.</div></div>
  <div id="c-c" class="brow"><div class="bdot bdot-green"></div><div class="btxt">It does Z.</div></div>
  <div id="c-p" style="font-size:15px;color:rgba(255,255,255,0.42);margin-top:12px;
    padding-top:10px;border-top:1px solid rgba(255,255,255,0.07);opacity:0;">
    Closing payoff line here.
  </div>
</div>
```

---

### 6. Comparison Table — `.rp`
Two rows: dim label (old) vs green label (new/me).

```html
<div class="rp" style="[glass base] border-right:3px solid rgba(58,123,213,0.70);">
  <div class="kk">THE REAL COMPARISON</div>
  <div id="c-r1" style="display:flex;align-items:baseline;gap:10px;padding:10px 0;
    border-bottom:1px solid rgba(58,123,213,0.12);opacity:0;">
    <div style="font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;
      color:rgba(255,255,255,0.38);min-width:100px;">THEM</div>
    <div style="font-size:23px;font-weight:700;color:#fff;">Their result</div>
  </div>
  <div id="c-r2" style="display:flex;align-items:baseline;gap:10px;padding:10px 0;opacity:0;">
    <div style="font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;
      color:#14c882;min-width:100px;">ME</div>
    <div style="font-size:23px;font-weight:700;color:#14c882;">My result</div>
  </div>
  <div id="c-s" style="font-size:14px;color:rgba(255,255,255,0.38);margin-top:12px;
    padding-top:10px;border-top:1px solid rgba(58,123,213,0.12);opacity:0;line-height:1.55;">
    Supporting context sentence.
  </div>
</div>
```

---

### 7. Insight Reveal — `.lp` or `.lr`
Two-line fade reveal. Use for insight or "the real truth" moments.

```html
<div class="lp" style="[glass base] border-left:3px solid rgba(58,123,213,0.70);">
  <div id="c-l1" style="font-size:22px;font-weight:700;color:#fff;margin-bottom:8px;opacity:0;">
    First insight line.
  </div>
  <div id="c-l2" style="font-size:22px;font-weight:700;color:#fff;margin-bottom:14px;opacity:0;">
    They care if you know <span style="color:#3a7bd5;">what you want</span>.
  </div>
  <div id="c-l3" style="font-size:15px;color:rgba(255,255,255,0.38);font-style:italic;opacity:0;">
    Bridge line to next section.
  </div>
</div>
```

---

### 8. Outro Numbered List — `.lr`
Numbered takeaways + closer line. Use at the end of the video.

```html
<div class="lr" style="[glass base] border-bottom:3px solid rgba(58,123,213,0.70);">
  <div class="kk">TAKE THIS WITH YOU</div>
  <div id="c-n1" style="display:flex;align-items:center;gap:14px;padding:8px 0;
    border-bottom:1px solid rgba(58,123,213,0.12);opacity:0;">
    <div style="font-size:16px;font-weight:700;color:#3a7bd5;min-width:20px;">1</div>
    <div style="font-size:20px;font-weight:500;color:rgba(255,255,255,0.88);">First takeaway.</div>
  </div>
  <div id="c-n2" style="display:flex;align-items:center;gap:14px;padding:8px 0;
    border-bottom:1px solid rgba(58,123,213,0.12);opacity:0;">
    <div style="font-size:16px;font-weight:700;color:#3a7bd5;min-width:20px;">2</div>
    <div style="font-size:20px;font-weight:500;color:rgba(255,255,255,0.88);">Second takeaway.</div>
  </div>
  <div id="c-n3" style="display:flex;align-items:center;gap:14px;padding:8px 0;opacity:0;">
    <div style="font-size:16px;font-weight:700;color:#3a7bd5;min-width:20px;">3</div>
    <div style="font-size:20px;font-weight:500;color:rgba(255,255,255,0.88);">Third takeaway.</div>
  </div>
  <div id="c-cl" style="font-size:24px;font-weight:700;color:#3a7bd5;
    text-shadow:0 0 16px rgba(58,123,213,0.4);margin-top:14px;
    padding-top:12px;border-top:1px solid rgba(58,123,213,0.20);opacity:0;">
    Closer question or statement?
  </div>
</div>
```

---

### 9. Tool Pill Badge — `.tp` (inspired by reference video)
Names a tool/app when first mentioned. Small, brief (3–6s), upper-left.

```html
<div class="tp" style="
  position:absolute; left:60px; top:80px;
  background:rgba(9,15,38,0.88);
  border:2px solid rgba(58,123,213,0.75);
  border-radius:50px;
  box-shadow:0 0 16px rgba(58,123,213,0.50), 0 0 40px rgba(58,123,213,0.18);
  padding:14px 28px;
  display:flex; align-items:center; gap:14px;">
  <span style="font-size:26px;">🤖</span>  <!-- or inline SVG icon -->
  <span style="font-size:22px;font-weight:700;color:#fff;letter-spacing:1px;
    text-transform:uppercase;">TOOL NAME</span>
</div>
```
Timing rule: **3–6 seconds max.** Show at exact moment tool is named. Hide when sentence ends.

---

### 10. Floating Bullet List — `.fl` (inspired by reference video)
Text floats directly ON the footage — no card background. Use for rapid-fire questions or contrasts.

```html
<div class="fl" style="position:absolute; left:80px; top:200px;">
  <div id="c-f1" style="display:flex;align-items:flex-start;gap:14px;margin-bottom:22px;opacity:0;">
    <span style="font-size:28px;color:#3a7bd5;line-height:1.1;flex-shrink:0;">✦</span>
    <div style="font-size:30px;font-weight:700;color:#fff;line-height:1.2;
      text-shadow:0 2px 16px rgba(0,0,0,0.9);">
      Does this <span style="color:#3a7bd5;">actually work</span>?
    </div>
  </div>
  <div id="c-f2" style="display:flex;align-items:flex-start;gap:14px;margin-bottom:22px;opacity:0;">
    <span style="font-size:28px;color:#3a7bd5;line-height:1.1;flex-shrink:0;">✦</span>
    <div style="font-size:30px;font-weight:700;color:#fff;line-height:1.2;
      text-shadow:0 2px 16px rgba(0,0,0,0.9);">
      Is it <span style="color:#14c882;">worth it</span>?
    </div>
  </div>
  <div id="c-f3" style="display:flex;align-items:flex-start;gap:14px;opacity:0;">
    <span style="font-size:28px;color:#3a7bd5;line-height:1.1;flex-shrink:0;">✦</span>
    <div style="font-size:30px;font-weight:700;color:#fff;line-height:1.2;
      text-shadow:0 2px 16px rgba(0,0,0,0.9);">
      How long does it take?
    </div>
  </div>
</div>
```
Timing rule: **5–8 seconds.** Items stagger in 0.4s apart.
Requires strong text-shadow since there's no card background — `text-shadow:0 2px 16px rgba(0,0,0,0.9)`.

---

### 11. Chapter Lower Third — `.ch-lower` (inspired by reference video)
Blue pill at bottom-left marking a new skill/section. Show at the start of each main section, 4–6s.

```html
<div class="ch-lower" style="
  position:absolute; left:60px; bottom:60px;
  background:linear-gradient(90deg, rgba(58,123,213,0.88), rgba(9,15,38,0.88));
  border:1px solid rgba(58,123,213,0.50);
  border-radius:50px;
  box-shadow:0 0 20px rgba(58,123,213,0.45), 0 4px 16px rgba(0,0,0,0.5);
  padding:16px 32px;
  display:flex; align-items:center; gap:16px;">
  <span style="font-size:24px;">⚡</span>  <!-- icon for this section -->
  <span style="font-size:22px;font-weight:700;color:#fff;">SECTION TITLE</span>
</div>
```

---

### 12. Full-Screen Chapter Card Grid (inspired by reference video)
Full 1920×1080 dark scene — cuts AWAY from talking head for 2–4s at major chapter breaks.
Use for "here are the N things I'll cover" moments or major transitions.

```html
<!-- Full-screen clip, track-index 2, short duration (2–4s) -->
<div style="
  position:absolute; inset:0;
  background:radial-gradient(ellipse at center, rgba(9,30,60,1) 0%, rgba(9,15,38,1) 70%);
  display:flex; align-items:center; justify-content:center; gap:40px;">

  <!-- Card: repeat for each item -->
  <div style="
    width:380px; padding:40px 30px 30px;
    background:linear-gradient(160deg, rgba(58,123,213,0.18) 0%, rgba(9,15,38,0.95) 60%);
    border:2px solid rgba(58,123,213,0.55);
    border-radius:20px;
    box-shadow:0 0 40px rgba(58,123,213,0.25), 0 8px 32px rgba(0,0,0,0.7);
    display:flex; flex-direction:column; align-items:center; gap:24px;
    text-align:center;">
    <div style="width:90px;height:90px;border-radius:50%;
      background:rgba(58,123,213,0.15);
      border:1px solid rgba(58,123,213,0.35);
      display:flex;align-items:center;justify-content:center;font-size:40px;">⚙️</div>
    <div style="font-size:22px;font-weight:700;color:#fff;line-height:1.3;">Card label here</div>
  </div>

</div>
```

---

## GSAP TIMELINE TEMPLATE

Always register on `window.__timelines['talking-head-recut']`.

```js
(function () {
  var tl = window.gsap.timeline({ paused: true });

  function show(id, t) {
    tl.set('.ch[data-card-id="' + id + '"]', { visibility: 'visible' }, t);
    tl.fromTo('.ch[data-card-id="' + id + '"]',
      { opacity: 0 }, { opacity: 1, duration: 0.35, ease: 'power2.out' }, t);
  }
  function hide(id, end) {
    tl.to('.ch[data-card-id="' + id + '"]',
      { opacity: 0, duration: 0.30, ease: 'power2.in' }, end - 0.30);
    tl.set('.ch[data-card-id="' + id + '"]', { visibility: 'hidden' }, end);
  }

  /* Add show/hide calls + element animations here */

  window.__timelines = window.__timelines || {};
  window.__timelines['talking-head-recut'] = tl;
})();
```

Every `.ch.clip` wrapper needs:
```html
<div class="ch clip" data-card-id="card-NN"
  data-start="[N]" data-duration="[D]" data-track-index="2"
  style="visibility:hidden;opacity:0;">
```

`#stage` must have `data-layout-allow-occlusion="true"`.

---

## TIMING RULES

| Card type | Typical duration | Rule |
|-----------|-----------------|------|
| Hook | 8–13s | Show from video start, hide when hook topic ends |
| Stat counter | 4–6s | Show at exact word the number is mentioned |
| Pull quote | 6–9s | Show when quote starts, hide within 1s of ending |
| Bullet list (old/new) | 8–14s | Show when first item is spoken; items stagger in |
| Comparison table | 10–18s | Show at first comparison mention |
| Insight reveal | 8–12s | Show at insight; second line at natural pause |
| Outro numbered | 12–16s | Show when takeaways start, NOT at "here's what I want you..." |
| Tool pill badge | 3–6s | Show at exact mention; disappear when sentence ends |
| Floating bullet list | 5–8s | Items stagger 0.4s apart |
| Chapter lower third | 4–6s | Show at section start |
| Full-screen chapter | 2–4s | Cut-away; back to talking head after |

**Universal rule:** Card appears when speaker starts that specific topic. Never before.
Aim for ~1 card per 15–20s of content (10–14 cards for a 3–4 min video).
Never let two track-2 elements overlap in time.

---

## WORKFLOW

### STEP 0 — OPTIONAL: Analyse reference video
If a style reference `.mp4` is provided:
```bash
# Extract 20 frames evenly spaced
$vid = "[reference.mp4]"
$out = "C:\Users\dylan\AppData\Local\Temp\claude\ref-frames"
New-Item -ItemType Directory -Force $out | Out-Null
$ts = @(5,30,60,90,120,180,240,300,360,420,480,540,600,660,720,840,960,1080,1150,1180)
foreach ($t in $ts) {
  ffmpeg -y -ss $t -i $vid -frames:v 1 -update 1 "$out\f$($t.ToString('D4')).jpg" 2>$null
}
```
Read all frames. Note card types, positions, colours, border styles. Adapt the brand system if needed.

### STEP 1 — Project setup
```bash
# Create project folder (copy fonts + vendor from reference project)
mkdir -p content-agent/projects/[title]/public/fonts
mkdir -p content-agent/projects/[title]/public/vendor
cp content-agent/projects/cant-code-video/public/fonts/* content-agent/projects/[title]/public/fonts/
cp content-agent/projects/cant-code-video/public/vendor/gsap.min.js content-agent/projects/[title]/public/vendor/

# Re-encode for dense keyframes (keeps audio)
ffmpeg -i "[source].mp4" -crf 18 -g 30 -keyint_min 30 -pix_fmt yuv420p \
  -movflags +faststart -c:a aac \
  "content-agent/projects/[title]/public/input-video.mp4"
```

### STEP 2 — Transcript
If no `transcript.json` exists, run `/transcribe` with Whisper large-v3.
The transcript must be **word-level** (each word has its own timestamp).

### STEP 3 — Card plan (present before coding)
Read the transcript. Identify card moments. Output this table and **wait for approval**:

```
| # | Type               | Time in → out | Position | Content summary     |
|---|--------------------|---------------|----------|---------------------|
| 01| Hook               | 0.0 → 12.0   | hook-c   | "TITLE WORDS."      |
| 02| Stat counter       | 24.5 → 28.5  | lp       | 5,000 cold calls    |
...
```

Rules:
- Card appears when speaker **starts** that specific topic/word
- Card hides within 1s of that topic ending (check word timestamps)
- No track-2 time overlaps
- List cards: start when first list item is spoken, not the lead-in sentence

### STEP 4 — Write `public/index.html`
Use templates above. Required on `#stage`:
```html
data-composition-id="talking-head-recut"
data-start="0" data-duration="[video duration]"
data-fps="30" data-width="1920" data-height="1080"
data-layout-allow-occlusion="true"
```

Include `<script src="vendor/gsap.min.js"></script>` before the GSAP timeline block.

### STEP 5 — Lint
```bash
npx hyperframes lint public
```
Fix any **errors** before proceeding. Warnings about `studio_missing_editable_id` and
`timeline_track_too_dense` are safe to ignore for rendering.

### STEP 6 — Render + mux audio
```bash
npx hyperframes render public -o output-[v].mp4 --fps 30

# Mux original audio — ALWAYS use the pre-re-encode source, not input-video.mp4
ffmpeg -y -i "output-[v].mp4" -i "[original source].mp4" \
  -c:v copy -c:a copy -map 0:v:0 -map 1:a:0 "output-[v]-final.mp4"
```

### STEP 7 — Verify
Extract frames at 3–5 key card timestamps:
```bash
ffmpeg -y -ss [T] -i "output-[v]-final.mp4" -frames:v 1 -update 1 "verify-[T].jpg"
```
Read and visually confirm:
- Hook card is below the chin, not overlapping the face
- Bullet dots are visible and rendering correctly
- No card looks like a caption bar (no full-width bars)
- Audio plays correctly (check file has audio stream: `ffprobe output-[v]-final.mp4`)

---

## WHAT THIS SKILL DOES NOT DO

- Generate transcripts → use `/transcribe`
- Write the video script → use `/video-creation`
- Add captions/subtitles → use `/embedded-captions`
- Upload or publish to any platform
- Color grade or background-remove the raw footage

---

## INVOCATION

```
/video-overlay [path to .mp4]
```

Or naturally:
> "Add DigiGrowth branded graphics to this video — [path]"
> "Brand my talking head video like the last one"
> "Add overlays synced to the transcript"
