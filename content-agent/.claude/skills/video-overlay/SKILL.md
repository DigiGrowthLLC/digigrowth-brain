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

### Legibility rule (applies to every card below and above)
Anything that sits over footage gets a **glass card or a scrim** behind it. Bare text over busy
video only works for the Floating Bullet List (#10), and only with its heavy text-shadow. If a
verify-loop frame shows text fighting the background, add a backing. Don't just shrink the font.

### Media rule (cards 13, 15, 16)
HyperFrames only decodes a `<video>` that is a **direct child of `#stage`**. Never put one inside a
card div, or it renders black. Build a b-roll card as two siblings: a glass **backing** `.ch` div
(frame, label) and the `<video class="clip">` positioned exactly inside it at a higher z-index.
Animate the video from the main timeline at global time. Images (`<img>`) *can* live inside the
card. Every b-roll `<video>` is `muted playsinline`, and the talking-head audio stays the only sound
bed. Assets live in `public/assets/` (see Step 3.5).

---

### 13. Side Insert — `.lp` / `.rp` (b-roll, screenshot, or clip beside the face)
Proof on screen: when Dylan names a tool, result, site, or dashboard, show it. Enters from its
own side, 5–8s.

```html
<!-- backing card (track 2) -->
<div class="ch clip" data-card-id="card-NN" data-start="T" data-duration="D" data-track-index="2"
  style="visibility:hidden;opacity:0;position:absolute;right:60px;top:50%;transform:translateY(-50%);
  width:400px;padding:14px;[glass base] border-right:3px solid rgba(58,123,213,0.70);">
  <div class="kk">LIVE DASHBOARD</div>
  <div style="width:372px;height:232px;border-radius:6px;overflow:hidden;">
    <img src="assets/NN-shot.png" style="width:100%;height:100%;object-fit:cover;">  <!-- still -->
  </div>
</div>
<!-- for a moving clip, leave the inner box empty and add a sibling video (track 3) -->
<video id="bv-NN" class="clip" src="assets/NN-clip.mp4" muted playsinline
  data-start="T" data-duration="D" data-track-index="3"
  style="position:absolute;right:74px;top:calc(50% - 90px);width:372px;height:232px;
  object-fit:cover;border-radius:6px;z-index:5;"></video>
```
GSAP: slide in from the edge it lives on. `tl.from('.ch[data-card-id="card-NN"]', {x:60, duration:0.45, ease:'power3.out'}, T)`,
and the same `x` tween on `#bv-NN`. Position from the face safe zones: right cards start x ≥ 1500 and left cards end x ≤ 420.

---

### 14. Keyword Highlight Strip — bottom-center
The 2–4 words that ARE the point sit at the bottom and light up one by one as they're spoken.
Use for the thesis line or a key phrase, once or twice per video. It's not a caption track.

```html
<div class="ch clip" data-card-id="card-NN" data-start="T" data-duration="D" data-track-index="2"
  style="visibility:hidden;opacity:0;position:absolute;left:50%;bottom:64px;transform:translateX(-50%);
  padding:14px 30px;border-radius:12px;background:rgba(9,15,38,0.72);
  backdrop-filter:blur(10px);border:1px solid rgba(58,123,213,0.28);white-space:nowrap;">
  <span id="kw-NN-1" class="kw" style="font-size:54px;font-weight:700;color:rgba(255,255,255,0.35);">BEST</span>
  <span id="kw-NN-2" class="kw" style="font-size:54px;font-weight:700;color:rgba(255,255,255,0.35);">OUTPUTS</span>
  <span id="kw-NN-3" class="kw" style="font-size:54px;font-weight:700;color:rgba(255,255,255,0.35);">EVER</span>
</div>
```
GSAP, one tween per word **at that word's transcript start time**:
`tl.to('#kw-NN-1', {color:'#fff', textShadow:'0 0 24px rgba(58,123,213,0.9)', duration:0.15}, WORD_T)`.
Put the last word in `#3a7bd5` for the payoff.

---

### 15. Face-Cam Push-In — animates `#a-roll`
A subtle scale on the talking head for the hook and big emphasis moments. It isn't a card, so it
takes no track-2 slot. Use at most 1 per ~30s, or it turns into seasickness.
```js
tl.to('#a-roll', {scale:1.06, transformOrigin:'50% 35%', duration:3.5, ease:'sine.inOut'}, T);
tl.to('#a-roll', {scale:1.00, duration:0.35, ease:'power2.out'}, T_END);   // reset on a hard beat
```
A push-in changes the face safe zones for its duration. Keep side cards off that window, or
nudge them outward by ~40px.

---

### 16. Full-Screen Takeover (b-roll / AI clip / screenshot)
Cuts away from the face for 2–5s to show the thing. Talking-head audio keeps playing underneath.
Use a `<video class="clip">` directly on `#stage` at track 3 with `inset:0; width:1920px; height:1080px; object-fit:cover;`,
plus an optional glass kicker label card at track 2 in the upper-left. Enter with a 6-frame zoom
punch (`scale:1.05→1`) and exit with a hard cut. For a still, use an `<img>` with a slow Ken Burns
(`scale 1→1.08` over the clip).

---

### 17. Split Takeover — visual left / face right
Teaching moments (the whiteboard/explainer look). `#a-roll` moves to the right half, and the visual
fills the left half.
```js
// T: split in, T_END: back to full
tl.to('#a-roll', {xPercent:25, scale:1.0, duration:0.5, ease:'power3.inOut'}, T);
tl.to('#a-roll', {xPercent:0, duration:0.5, ease:'power3.inOut'}, T_END - 0.5);
```
The left panel is a `.ch` clip at `left:0;top:0;width:960px;height:1080px;` with a navy background
(`#090f26`) and the visual inside. Images and HTML diagrams go inside; video goes as a sibling per
the media rule. Check the verify-loop frame to confirm the face isn't cut at the new crop. Re-tune
`xPercent` for each piece of footage.

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
| Side insert (b-roll) | 5–8s | Show at the exact mention of the thing being proven |
| Keyword highlight strip | 2–5s | Each word lights at its own transcript timestamp |
| Face-cam push-in | 3–5s | Hook + big emphasis only, max ~1 per 30s, no track-2 slot |
| Full-screen takeover | 2–5s | Cut away on the noun; cut back before the next point |
| Split takeover | 6–20s | Whole teaching segment; enter/exit on sentence boundaries |

**Universal rule:** Card appears when speaker starts that specific topic. Never before.
Aim for ~1 card per 15–20s of content (10–14 cards for a 3–4 min video). With
`creative` latitude, add b-roll inserts and push-ins on top of that for more visual change, but
never stack two beats inside the same 2s.
Never let two track-2 elements overlap in time (b-roll `<video>`s use track 3).
**Content must be on screen when the card is.** A card that appears as an empty glass box and
fills in later reads as a glitch. Stagger items in only when they're spoken, but show the kicker or
first line at the card's own in-point.

---

## WORKFLOW

### STEP 0 — Style + lessons
1. **Read the LESSONS LOG at the bottom of this file first.** Those rules come from Dylan's past
   reviews and override the defaults above.
2. Pick the style. The default is the house glass system above. If Dylan names a style skill from
   **STYLES** below, read that skill and apply its tokens and motion vocabulary on top of the card
   templates.
3. If Dylan hands over a new inspiration video ("make it like this"), run `/style-from-reference`
   first. It turns the reference into a reusable style skill, and you then use that.

**STYLES** (added by `/style-from-reference`, one line each):
- `house`: DigiGrowth navy glass (this file). The default.

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
`[source]` is the **rough cut** (`projects/[title]/cut.mp4`) when the footage is raw. See
`/video-production` Step 2. Use the original file only if it's already a clean take.

### STEP 2 — Transcript
If no `transcript.json` exists:
```bash
python content-agent/tools/transcribe.py "[source].mp4" --words --model large-v3 --out content-agent/projects/[title]
```
This writes a word-level `transcript.json` (`[{text,start,end}]`). If the source is a rough cut,
use the `transcript.cut.json` that `rough_cut.py --apply` wrote instead; it's already remapped
onto the cut timeline, so there's no need to re-transcribe.

### STEP 2.5 — Director's Brief
Before planning cards, collect Dylan's direction. If he already gave it in the request, extract it
without asking again:
- **Cues:** "when I say X → Y". Resolve each X to its word timestamp in the transcript. If a phrase
  isn't found or appears more than once, **flag it in the plan**. Never guess a time.
- **Vibe:** the emotion the video should create (e.g. "confident, fast, premium" or "calm,
  friendly"). This drives card density, entrance eases, and whether push-ins and takeovers are used.
- **Latitude:** `strict` means only the listed beats. `creative` means cues plus your own additions,
  and every addition gets marked `(added)` in the plan so he can veto it. With no latitude given,
  default to `creative` and say so.
- **Proof moments:** anywhere he claims a tool or result, plan a Side Insert or Takeover showing
  it (Step 3.5 sources it).

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
- Add a **Cue** column (the exact spoken words that trigger the beat) and an **Asset** column (for
  b-roll beats: `screenshot of X` / `AI still → Kling` / `none`)

Once approved, save the plan as `projects/[title]/beats.json` in the format `verify_render.py` reads:
```json
[{"id": "card-01", "type": "Hook", "start": 0.0, "end": 12.0, "label": "I CAN'T CODE.", "cue": "can't code", "track": 2}]
```

### STEP 3.5 — Source assets
For every beat whose Asset column isn't `none`, produce a file in `projects/[title]/public/assets/`
and record it in `public/assets/manifest.json` (`{"card-NN": {"file", "source", "cost_usd"}}`).
Work in this order of preference, because real proof beats generated filler:
1. **Real capture.** For screenshots or screen recordings of a site or the dashboard, use
   `python content-agent/tools/record_site_scroll.py "<url>" <secs> <out.mp4>` or a Playwright
   screenshot. Dylan's own screen recordings go first if he supplied any.
2. **AI still.** `doppler run --project digigrowth --config prd -- python content-agent/tools/generate_creative.py image "<prompt>" --aspect 16:9 --out <file>.png`
   (flux default; `--model nano-banana-pro --ref <img>` when it must match a real product, place, or person).
3. **Motion b-roll.** Animate an *approved* still: `generate_creative.py video "<motion prompt>" --image <still>.png --duration 5 --out <file>.mp4`
   (Kling, ~$0.25/5s).
4. **Music/SFX** (optional, only when asked or when the vibe calls for it): `generate_creative.py music "<style>" --duration <s>`
   or `/hyperframes-media` / `/media-use` for SFX. Keep music ducked under speech at about −18dB.
   Put SFX hits on card entrances, not on every beat.

Rules: show the total estimated cost before any paid generation. Show generated stills to Dylan
inline in chat (Read the image) and get a yes before paying to animate them. Don't route that
review through an artifact.

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

If there's a music bed, mix it under the voice instead of copying the audio stream:
```bash
ffmpeg -y -i "output-[v].mp4" -i "[original source].mp4" -i "public/assets/music.wav" \
  -filter_complex "[2:a]volume=-18dB,afade=t=out:st=[dur-2]:d=2[m];[1:a][m]amix=inputs=2:duration=first:normalize=0[a]" \
  -map 0:v:0 -map "[a]" -c:v copy -c:a aac -b:a 192k "output-[v]-final.mp4"
```

### STEP 7 — Verification loop (do NOT hand over iteration 1)
Dylan should receive a draft the agent has already watched and fixed. Loop up to **3 times**:

1. **Check.**
   ```bash
   python content-agent/tools/verify_render.py "output-[v]-final.mp4" beats.json \
     --out "<session scratchpad>/verify-[title]" --source "[original source].mp4" \
     --transcript transcript.json --iteration N --full
   ```
   Contact sheets and frames go to the **scratchpad, never the project or repo folder**.
2. **Read every contact sheet** (in/mid/out per beat) and the full-res mid frames, then score each
   beat against the rubric:
   - [ ] **Face:** no card, insert, or split crop covers the face (safe zone x 468–1451, chin y≈706)
   - [ ] **Legibility:** text readable at phone size, backed by glass or a scrim, no text fighting the footage
   - [ ] **Filled at in-point:** no empty glass box at in+0.4s (content is visible when the card is)
   - [ ] **Timing:** the automated cue check passes; the card leaves within ~1s of its topic ending
   - [ ] **Copy:** no typos, and the copy matches what's said (proofread the full-res frames)
   - [ ] **Brand:** house tokens (or the chosen style), no off-palette colors, no caption-bar-looking cards
   - [ ] **Media:** b-roll videos aren't black or blank (black = the media rule was broken)
   - [ ] **Audio:** the automated streams check passes; music (if any) sits under the voice
3. **Fix** every failure in `index.html`, re-render, re-mux, and increment N.
4. **Log** each iteration in `projects/[title]/review-log.md`: iteration number, what failed, and what changed.

Stop when a full pass is clean, or after iteration 3. Then hand Dylan the final file **plus the
review log**, and call out anything still unresolved rather than hiding it.
For a quicker inner loop on a single beat, use `npx hyperframes snapshot` at that timestamp
instead of a full re-render.

### STEP 8 — Lessons
After Dylan reviews, ask what he liked and didn't like, then **append each point as a rule** to
the LESSONS LOG below (or to the style skill's own log if a style skill was used), with the date.
If he's corrected the same thing twice, it's a rule. Don't wait for him to ask.

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

---

## LESSONS LOG

Rules learned from Dylan's reviews. Read before Step 3 and apply them over the defaults above.
Append new ones at Step 8 in this format: `- YYYY-MM-DD: <rule> (why: <what he said>)`.
When a rule is superseded, edit it in place instead of stacking a contradiction.

- 2026-09-30: Cards must never appear as an empty glass box. Show the kicker or first line at the
  card's in-point (why: the verify pass on `cant-code-video` v6 showed cards 09/11/12/13 blank for
  ~1s after entering).
