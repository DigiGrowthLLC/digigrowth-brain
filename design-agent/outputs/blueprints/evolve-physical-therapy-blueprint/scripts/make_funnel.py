"""Evolve PT funnel: R&R's funnel_src.html (palette already swapped) with Evolve's body; writes funnel_src.html
(placeholders {{LOGO}} {{HERO}} {{PH2}}) and funnel.html (images inlined from funnel_imgs.json)."""
import json
import pathlib

P = pathlib.Path(__file__).resolve().parent.parent
s = (P / "funnel_src.html").read_text(encoding="utf-8")
head = s.split("</head><body>")[0]
# R&R brown/gold -> Evolve near-black green / sage (no-op once swapped)
for a, b in [("#2b1a0e", "#1a1f1c"), ("#faf3ed", "#f5f4f0"), ("#c69c55", "#75a895"), ("rgba(198,156,85", "rgba(117,168,149"),
             ("#eadfd3", "#e2e6e1"), ("#6b5443", "#56605b"), ("#2e1c0f", "#17221e"), ("#3b2413", "#1f2e29"),
             ("#4a2f1a", "#284039"), ("#f3e6d6", "#dcebe4"), ("#e0b86f", "#9fd0bc"), ("#eadccb", "#d4e2dc"),
             ("#d9c6b1", "#bccfc7"), ("rgba(20,10,0", "rgba(0,12,8"), ("#7a6453", "#66706b"), ("#f6ecdf", "#e9f2ee"),
             ("#9a7232", "#4f8a73"), ("#a87a35", "#4f8a73"), ("#f1e6d8", "#e3ece8"), ("#f3ebe1", "#eef1ee"),
             ("#8a7362", "#78827d"), ("rgba(60,35,15", "rgba(15,40,30"), ("#c8b49e", "#a9b8b1")]:
    head = head.replace(a, b)
# white text on the sage buttons/badges (her site's own button style)
head = head.replace("background:#75a895;color:#17221e", "background:#75a895;color:#fff")
head = head.replace("<title>Rise &amp; Reframe Physical Therapy</title>", "<title>Evolve Physical Therapy | Richland, WA</title>")
head = head.replace(".top img{height:48px;", ".top img{height:40px;")

CK = '<svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>'
ARR = '<svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>'
PIN = '<svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s7-6.2 7-12a7 7 0 1 0-14 0c0 5.8 7 12 7 12z"/><circle cx="12" cy="10" r="2.5"/></svg>'
CLK = '<svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>'
USR = '<svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="m16 11 2 2 4-4"/></svg>'
AWD = '<svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="6"/><path d="M15.48 12.89 17 22l-5-3-5 3 1.52-9.11"/></svg>'
DOC = '<svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="m9 15 2 2 4-4"/></svg>'
CARD = '<svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20"/></svg>'
SRCH = '<svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>'
HAND = '<svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1-1.1a5.5 5.5 0 0 0-7.8 7.8l1 1.1L12 21l7.8-7.5 1-1.1a5.5 5.5 0 0 0 0-7.8z"/></svg>'
BOLT = '<svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/></svg>'
DEAL = ('<div class="deal"><div class="deal-prices"><span class="deal-was">$175</span><span class="deal-now">$49</span>'
        '<span class="deal-save">SAVE $126</span></div><div class="deal-spots"><span class="deal-dot"></span>Only <b>10 spots</b> each month</div></div>')


def q(text, name, label):
    return (f'<div class="q"><div class="st">★★★★★</div><p>"{text}"</p><div class="who"><span class="av">{name[0]}</span>'
            f'<div><b>{name}</b><span>{label}</span></div></div></div>')


REVIEWS = "\n ".join([
    q("I can't recommend PT Morgan Gese highly enough. After working with several physical therapists, she stands out by a mile. "
      "Morgan has taken the time to understand what's actually going on rather than applying a standard formula based on where I am hurt.",
      "Jennifer H.", "Tried other PTs first"),
    q("For years I have experienced chronic knee pain and slowly but surely hindered my hyper-active lifestyle. "
      "After just one consult and a session my knee mobility improved.", "Dylan S.", "Chronic knee pain"),
    q("I had a soft tissue injury to my knee that would not go away on its own. With Dr Gese's treatment and knowledge I am "
      "100 per cent healed. Her 1 on 1 visits make the time spent with her valuable.", "Mark G.", "Knee injury"),
    q("I went to Morgan for Achilles tendonitis. She took the time to figure out what was going on, tested my range of motion, "
      "walked me through some exercises and then gave me a strength plan that I can do on my own.", "Casey C.", "Achilles tendonitis"),
    q("She was also able to correct years of bad lifting habits and form in my upper body (specifically shoulder) and alleviate "
      "the pain I was experiencing.", "Megan K.", "Shoulder + lifting form"),
    q("I had the joy of being Morgan's patient through running related hip soreness, staying strong during pregnancy, and "
      "getting back into exercise postpartum.", "Abby H.", "Running, pregnancy, postpartum"),
])

BODY = f'''
<div class="top"><div class="w"><img src="{{{{LOGO}}}}" alt="Evolve Physical Therapy">
 <div class="hb"><a class="tel">{PIN}Richland, WA</a><a class="btn" href="#">Book the $49 New Patient Assessment</a></div>
</div></div>
<div class="hero"><div class="w">
 <div>
  <span class="pill"><b></b>Richland &amp; Tri-Cities physical therapy</span>
  <h1>"Wait and see" isn't a plan. <em>Get back to training.</em></h1>
  <p>Every visit is <b>a full hour, one-on-one with Dr. Morgan Gese, DPT</b>. She finds what's causing your pain, eases it, then builds you back to the lifts and workouts you love.</p>
  {DEAL}<br>
  <a class="btn" href="#">Book my $49 New Patient Assessment{ARR}</a>
  <div class="under">{CLK}Paid when you book. No referral needed.</div>
 </div>
 <div class="pic"><img src="{{{{HERO}}}}" alt="Dr. Morgan Gese treating a patient's neck">
  <div class="badge2">{USR}1-on-1, a full hour</div>
  <div class="badge"><span class="bn">4.9</span><span class="bs"><b>★★★★★</b>on Google</span></div>
 </div>
</div></div>
<div class="trust"><div class="w">
 <div class="t"><span class="ic">{AWD}</span><div><b>Board-certified OCS</b><span>Orthopedic Clinical Specialist</span></div></div>
 <div class="t"><span class="ic">{USR}</span><div><b>A doctor every visit</b><span>Full hour, just you</span></div></div>
 <div class="t"><span class="ic">{DOC}</span><div><b>No referral needed</b><span>Start right away</span></div></div>
 <div class="t"><span class="ic">{CARD}</span><div><b>HSA / FSA welcome</b><span>Superbills on request</span></div></div>
</div></div>
<div class="s"><div class="w"><p class="eye">Real patient reviews</p><h2>Active people who <em>finally got answers</em></h2><div class="wall">
 {REVIEWS}
</div></div></div>
<div class="s" style="padding-top:0"><div class="w two">
 <div><p class="eye">Who we help</p><h2>You're a <em>good fit</em> if you:</h2><ul class="fit">
  <li><span class="ck">{CK}</span>Have back, hip, knee, shoulder, foot or neck pain that gets in the way of training</li>
  <li><span class="ck">{CK}</span>Were told to rest it, and it came right back</li>
  <li><span class="ck">{CK}</span>Want to keep lifting, running or playing, not be told to stop</li>
  <li><span class="ck">{CK}</span>Want one doctor, hands-on care and a training plan in one place</li></ul></div>
 <div class="ph2"><img src="{{{{PH2}}}}" alt="Dr. Morgan Gese coaching a deadlift"></div>
</div></div>
<div class="s" style="padding-top:0"><div class="w"><div class="disc">
 <p class="eye">The $49 New Patient Assessment</p><h2>What you'll <em>leave with</em></h2>
 {DEAL}
 <p class="lead">A full hour with Dr. Morgan: your story, a movement assessment with video analysis, and hands-on treatment. You leave knowing:</p>
 <div class="steps">
  <div class="step"><span class="n">01</span><p>What's actually causing your pain, not just where it hurts</p></div>
  <div class="step"><span class="n">02</span><p>Whether we can help, with an honest answer</p></div>
  <div class="step"><span class="n">03</span><p>A clear plan built around how you actually train</p></div>
  <div class="step"><span class="n">04</span><p>A home program with videos you can start today</p></div>
 </div>
</div></div></div>
<div class="s" style="padding-top:0"><div class="w"><p class="eye">The Evolve approach</p><h2>A clear path <em>back to training</em></h2><div class="cards">
 <div class="c"><div class="hd"><span class="ic">{SRCH}</span><span class="no">01</span></div><b>Find the pain generator</b><p>A thorough interview, assessment and movement analysis that leads to the real source of your pain.</p></div>
 <div class="c"><div class="hd"><span class="ic">{HAND}</span><span class="no">02</span></div><b>Ease the irritation</b><p>Hands-on care that settles the pain: manual therapy, dry needling, cupping and spinal manipulation.</p></div>
 <div class="c"><div class="hd"><span class="ic">{BOLT}</span><span class="no">03</span></div><b>Evolve your potential</b><p>Build strength, power and endurance so the pain doesn't come back and re-injury gets far less likely.</p></div>
</div></div></div>
<div class="s faq" style="padding-top:0"><div class="w"><p class="eye">Before you book</p><h2>Quick <em>questions</em></h2>
 <details open><summary>What does it cost?<span class="pm">+</span></summary><p>Our first visit is normally <span class="was-inline">$175</span>. The New Patient Assessment is <b>$49</b>, paid when you book. We only open 10 each month so every new patient gets a full hour with Dr. Morgan. If you continue, she walks you through visit and package pricing before you commit. No surprise bills.</p></details>
 <details><summary>Do you take insurance?<span class="pm">+</span></summary><p>We don't bill insurance, on purpose: it lets your plan follow what your body needs, not what's covered. We're happy to give you a superbill to submit for out-of-network reimbursement, and HSA/FSA cards are welcome.</p></details>
 <details><summary>Do I need a referral?<span class="pm">+</span></summary><p>No. Physical therapy is direct access in Washington, so you can book and get started right away.</p></details>
 <details><summary>Where are you?<span class="pm">+</span></summary><p>2000 Saint St, Richland, WA 99354. Monday to Friday, 9am to 5pm, Saturdays by appointment.</p></details>
</div></div>
<div class="end"><div class="w"><h2>Start with a $49 New Patient Assessment</h2>{DEAL}<p>Normally $175, now $49. We only open 10 each month, so grab yours while spots are open.</p><a class="btn" href="#">Book my $49 New Patient Assessment{ARR}</a>
 <div class="row"><span>{CK}One-on-one with Dr. Morgan</span><span>{CK}No referral needed</span><span>{CK}Richland, WA</span></div>
</div></div>
<div class="sticky"><div class="tx"><span class="st-prices"><s class="st-was">$175</s><b class="st-now">$49</b></span><span class="st-spots">Only 10 spots/month</span></div><a class="btn" href="#">Book my visit</a></div>
</body></html>'''

src = head + "</head><body>" + BODY
(P / "funnel_src.html").write_text(src, encoding="utf-8")
imgs = json.load(open(P / "funnel_imgs.json"))
out = src.replace("{{LOGO}}", imgs["logo"]).replace("{{HERO}}", imgs["hero"]).replace("{{PH2}}", imgs["ph2"])
(P / "funnel.html").write_text(out, encoding="utf-8")
print(f"funnel.html {len(out.encode()) // 1024} KB, leftover placeholders: {'{{' in out}")
