"""The client-facing campaign report page (weekly + final), rendered from the
dict client_success.create_report() builds. Pure function, no I/O.

Design goal (Dylan, 2026-11-17): a clinic owner should understand it in under
a minute. So the page reads top-down as:
  1. Headline + status pill (on pace / behind / goal reached)
  2. Four numbers that matter, each with its change vs last week
  3. The quick read: what's working / what we're fixing / next week
  4. (final) Your next campaign + week-by-week bars
  5. Patient quality, answers to their questions
  6. Everything else (step-by-step funnel, campaign to date, AI assistant)
     folded under "See the full numbers"
  7. Questions/ideas form (+ testimonial ask on the final report)
Light by default for readability, follows the phone's dark mode.
"""
from __future__ import annotations

import html
import os
from datetime import datetime
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


def _e(v) -> str:
    return html.escape(str(v)) if v is not None else ""


def _money(v):
    if v is None:
        return "–"
    return f"${v:,.0f}" if (v >= 100 or float(v).is_integer()) else f"${v:,.2f}"


def _num(v):
    return "–" if v is None else f"{v:,}" if isinstance(v, int) else f"{v:,.0f}"


def _pct(v):
    return "–" if v is None else f"{v:g}%"


def _date(iso: str | None) -> str:
    if not iso:
        return ""
    d = datetime.fromisoformat(iso).astimezone(ET)
    return f"{d.strftime('%b')} {d.day}"


def _delta(cur, prev, lower_is_better=False) -> str:
    if cur is None or prev in (None, 0):
        return '<span class="chg none">first week</span>' if prev is None and cur is not None else ""
    ch = (cur - prev) / prev * 100
    if abs(ch) < 1:
        return '<span class="chg flat">same as last week</span>'
    good = (ch < 0) if lower_is_better else (ch > 0)
    arrow = "↑" if ch > 0 else "↓"
    return f'<span class="chg {"good" if good else "bad"}">{arrow} {abs(ch):.0f}% vs last week</span>'


def _items(items) -> str:
    if not items:
        return '<li class="empty">Nothing here this time.</li>'
    return "".join(f"<li>{_e(i)}</li>" for i in items)


def _bars(weeks: list[dict]) -> str:
    """Bookings per week as small inline-SVG bars (final report)."""
    vals = [int((w.get("kpis") or {}).get("booked") or 0) for w in weeks]
    if not vals:
        return ""
    top = max(vals) or 1
    w, h, gap = 56, 120, 18
    width = len(vals) * (w + gap) - gap
    bars = []
    for i, v in enumerate(vals):
        bh = max(4, round(v / top * (h - 30)))
        x = i * (w + gap)
        y = h - 22 - bh
        bars.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{bh}" rx="6" class="bar"/>'
            f'<text x="{x + w / 2}" y="{y - 6}" text-anchor="middle" class="bv">{v}</text>'
            f'<text x="{x + w / 2}" y="{h - 4}" text-anchor="middle" class="bl">Wk {weeks[i]["week"]}</text>')
    return (f'<div class="chart"><svg viewBox="-4 0 {width + 8} {h}" width="{width + 8}" height="{h}" role="img" '
            f'aria-label="Bookings per week">{"".join(bars)}</svg></div>')


CSS = """
:root{--bg:#f4f6fb;--card:#fff;--line:#e3e8f2;--fg:#0f1b33;--mut:#5d6b85;--soft:#eef3fc;
--acc:#2f6fd0;--good:#0f9d63;--goodbg:#e6f6ee;--warn:#b86e00;--warnbg:#fff3df;--bad:#c93b3b;--badbg:#fdecec;color-scheme:light}
@media (prefers-color-scheme:dark){:root{--bg:#0a1024;--card:#111a35;--line:#22304f;--fg:#e9f0ff;--mut:#91a3c4;--soft:#16224a;
--acc:#6aa5ff;--good:#3ddc97;--goodbg:rgba(61,220,151,.12);--warn:#f5b24c;--warnbg:rgba(245,178,76,.12);--bad:#ff7b7b;--badbg:rgba(255,123,123,.12);color-scheme:dark}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font-family:Inter,system-ui,-apple-system,sans-serif;font-size:15px;line-height:1.55;-webkit-font-smoothing:antialiased}
.wrap{max-width:820px;margin:0 auto;padding:28px max(16px,env(safe-area-inset-left)) 64px max(16px,env(safe-area-inset-right));display:grid;gap:16px}
h1,h2,.num{font-family:"Space Grotesk",Inter,sans-serif}
.top{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap}
.eyebrow{font-size:12px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--acc)}
h1{font-size:28px;line-height:1.15;margin:4px 0 2px;letter-spacing:-.01em}
.dates{color:var(--mut);font-size:14px}
.pill{display:inline-flex;align-items:center;gap:6px;font-size:13px;font-weight:600;padding:6px 12px;border-radius:99px;white-space:nowrap}
.pill.good{background:var(--goodbg);color:var(--good)}.pill.warn{background:var(--warnbg);color:var(--warn)}.pill.bad{background:var(--badbg);color:var(--bad)}
.pill::before{content:"";width:7px;height:7px;border-radius:50%;background:currentColor}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px}
.hero{padding:24px}
.hero p.big{color:var(--fg);font-family:"Space Grotesk",Inter,sans-serif;font-size:21px;font-weight:600;line-height:1.35;margin:0 0 8px;text-wrap:balance}
.hero p{margin:0;color:var(--mut)}
.kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px;display:grid;gap:2px;min-width:0}
.kpi .lbl{font-size:12.5px;color:var(--mut)}
.kpi .num{font-size:26px;font-weight:700;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.kpi .num small{font-size:14px;color:var(--mut);font-weight:500}
.chg{font-size:12px;font-weight:600}.chg.good{color:var(--good)}.chg.bad{color:var(--bad)}.chg.flat,.chg.none{color:var(--mut);font-weight:500}
.prog{height:8px;border-radius:99px;background:var(--soft);overflow:hidden;margin-top:6px}
.prog i{display:block;height:100%;border-radius:99px;background:var(--acc)}
.quick{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.col{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;min-width:0}
.col h2{font-size:15px;margin:0 0 8px;display:flex;align-items:center;gap:8px}
.ico{width:22px;height:22px;border-radius:7px;display:inline-grid;place-items:center;font-size:13px;font-weight:700;flex-shrink:0}
.col.ok .ico{background:var(--goodbg);color:var(--good)}.col.fix .ico{background:var(--warnbg);color:var(--warn)}.col.next .ico{background:var(--soft);color:var(--acc)}
ul{margin:0;padding-left:18px}li{margin:5px 0}li.empty{list-style:none;margin-left:-18px;color:var(--mut)}
.help{display:flex;gap:12px;align-items:flex-start;background:var(--soft);border-radius:14px;padding:14px 16px}
.help b{display:block;margin-bottom:2px}
h2.sec{font-size:17px;margin:0 0 10px}
.feature{border-color:var(--good);background:linear-gradient(0deg,var(--goodbg),var(--goodbg)),var(--card)}
.chart{overflow-x:auto}.chart .bar{fill:var(--acc)}.chart .bv{fill:var(--fg);font:600 13px Inter,sans-serif}.chart .bl{fill:var(--mut);font:12px Inter,sans-serif}
.lq{display:flex;gap:18px;flex-wrap:wrap;align-items:baseline}
.lq .num{font-size:22px;font-weight:700}
.qa{padding:10px 0;border-top:1px solid var(--line)}.qa:first-of-type{border-top:0;padding-top:0}
.qa .q{color:var(--mut);font-size:14px}.qa .a{margin-top:3px}
details{background:var(--card);border:1px solid var(--line);border-radius:14px}
summary{cursor:pointer;padding:16px 20px;font-weight:600;list-style:none;display:flex;justify-content:space-between;align-items:center}
summary::-webkit-details-marker{display:none}summary::after{content:"+";font-size:20px;color:var(--mut)}details[open] summary::after{content:"–"}
.det{padding:0 20px 20px;display:grid;gap:18px}
.det h3{font-size:14px;margin:0 0 6px;color:var(--mut);font-weight:600}
.tw{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:14px;font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:8px 6px;border-bottom:1px solid var(--line);white-space:nowrap}th{color:var(--mut);font-weight:500;font-size:12.5px}
.st{font-size:12px;font-weight:600;padding:2px 8px;border-radius:99px}
.st.good{background:var(--goodbg);color:var(--good)}.st.ok{background:var(--warnbg);color:var(--warn)}.st.poor{background:var(--badbg);color:var(--bad)}.st.low_data{background:var(--soft);color:var(--mut)}
.mini{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
.mini div{background:var(--soft);border-radius:10px;padding:10px 12px}.mini .num{font-size:19px;font-weight:700}.mini .lbl{font-size:12px;color:var(--mut)}
.muted{color:var(--mut);font-size:14px}
form{display:grid;gap:10px;margin-top:12px}
.rates{display:flex;flex-wrap:wrap;gap:6px}
.rate{min-width:42px;padding:9px 0;border-radius:10px;border:1px solid var(--line);background:var(--card);color:var(--fg);font:inherit;cursor:pointer}
.rate.on{background:var(--acc);border-color:var(--acc);color:#fff}
select,textarea{width:100%;background:var(--card);border:1px solid var(--line);border-radius:10px;color:var(--fg);padding:10px 12px;font:inherit}
textarea{min-height:100px;resize:vertical}
.chk{display:flex;gap:8px;align-items:center;font-size:14px}
.btn{justify-self:start;background:var(--acc);border:0;color:#fff;font:inherit;font-weight:600;padding:11px 22px;border-radius:10px;cursor:pointer}
.btn:focus-visible,.rate:focus-visible,summary:focus-visible{outline:2px solid var(--acc);outline-offset:2px}
.thanks{display:none;color:var(--good);font-weight:600}
footer{text-align:center;color:var(--mut);font-size:12.5px;margin-top:8px}
@media (max-width:680px){.kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.quick,.mini{grid-template-columns:minmax(0,1fr)}h1{font-size:24px}.hero p.big{font-size:19px}}
"""


def render_html(report: dict) -> str:
    data, a, kind = report["data"], report["analysis"], report["kind"]
    clinic = data["client"]["name"]
    camp = data["campaign"]
    final = kind == "final"
    scope = data["to_date"] if final else (data.get("week") or data["to_date"])
    k = scope.get("kpis") or {}
    lk = {} if final else (((data.get("last_week") or {}).get("kpis")) or {})
    pace = data.get("pace")

    title = "Final campaign report" if final else f"Week {report['week_number']} report"
    dates = f"{_date(report['period_start'])} – {_date(report['period_end'])}"

    # Status pill
    if pace:
        if final:
            pill = ('<span class="pill good">Goal reached</span>' if pace["booked"] >= pace["goal"]
                    else '<span class="pill warn">Goal not reached</span>')
        else:
            pill = ('<span class="pill good">Goal reached</span>' if pace["booked"] >= pace["goal"]
                    else '<span class="pill good">On pace</span>' if pace["on_pace"] else '<span class="pill warn">Behind pace</span>')
    else:
        pill = ""

    # Four numbers
    if pace:
        pct = min(100, pace["pct_of_goal"])
        bud = camp.get("budget")
        progress_line = (f'{_money(bud["spent"])} of {_money(bud["cap"])} ad budget spent' if bud
                         else f'Day {camp.get("days_elapsed")} of {camp.get("length_days")}')
        goal_tile = (f'<div class="kpi"><span class="lbl">Campaign goal</span>'
                     f'<span class="num">{pace["booked"]}<small> / {pace["goal"]} {_e(camp.get("goal_label") or "booked")}</small></span>'
                     f'<div class="prog"><i style="width:{pct}%"></i></div>'
                     f'<span class="chg flat">{_e(progress_line)}</span></div>')
    else:
        goal_tile = (f'<div class="kpi"><span class="lbl">Showed up</span><span class="num">{_num(k.get("shows"))}</span>'
                     f'{_delta(k.get("shows"), lk.get("shows"))}</div>')
    period_word = "total" if final else "this week"
    kpis = (
        f'<div class="kpi"><span class="lbl">Booked {period_word}</span><span class="num">{_num(k.get("booked"))}</span>'
        f'{"" if final else _delta(k.get("booked"), lk.get("booked"))}</div>'
        f'<div class="kpi"><span class="lbl">Cost per booking</span><span class="num">{_money(k.get("cost_per_booking"))}</span>'
        f'{"" if final else _delta(k.get("cost_per_booking"), lk.get("cost_per_booking"), True)}</div>'
        f'<div class="kpi"><span class="lbl">New leads</span><span class="num">{_num(k.get("leads"))}</span>'
        f'{"" if final else _delta(k.get("leads"), lk.get("leads"))}</div>'
        + goal_tile)

    quick = (
        f'<div class="col ok"><h2><span class="ico">✓</span>What\'s working</h2><ul>{_items(a.get("on_target"))}</ul></div>'
        f'<div class="col fix"><h2><span class="ico">!</span>What we\'re fixing</h2><ul>{_items(a.get("off_target"))}</ul></div>'
        f'<div class="col next"><h2><span class="ico">→</span>{"What we recommend" if final else "Next week"}</h2>'
        f'<ul>{_items(a.get("next_steps"))}</ul></div>')

    help_html = ""
    if a.get("client_asks"):
        help_html = ('<div class="help"><span class="ico" style="background:var(--card);color:var(--acc)">★</span><div>'
                     '<b>How your team can help</b><ul>' + _items(a["client_asks"]) + '</ul></div></div>')

    next_html = weeks_html = ""
    if final:
        nc = a.get("next_campaign") or {}
        if nc.get("plan") or nc.get("intro"):
            next_html = (f'<section class="card feature"><h2 class="sec">Your next campaign</h2>'
                         f'<p style="margin:0 0 10px">{_e(nc.get("intro"))}</p><ul>{_items(nc.get("plan"))}</ul>'
                         f'<p style="margin:12px 0 0;font-weight:600">{_e(nc.get("ask"))}</p>'
                         f'<p class="muted" style="margin:4px 0 0">Tick "I\'d like to talk about the next campaign" at the bottom and I\'ll reach out.</p></section>')
        if data.get("weeks"):
            weeks_html = (f'<section class="card"><h2 class="sec">Bookings week by week</h2>{_bars(data["weeks"])}</section>')

    lq = data.get("lead_quality")
    lq_html = ""
    if lq and (lq["good"] + lq["not_fit"] or lq.get("unrated")):
        notes = "".join(f"<li>{_e(n)}</li>" for n in (lq.get("notes") or [])[:3])
        ask = ('A few patients you marked as showed and closed still need a "good fit?" answer in your portal (Appointments). '
               'It is the fastest way for us to find you more of the right people.' if lq.get("unrated")
               else "Thanks for rating your patients. We use it to tune who sees your ads.")
        lq_html = (f'<section class="card"><h2 class="sec">Patient quality (your ratings)</h2>'
                   f'<div class="lq"><span><span class="num" style="color:var(--good)">{lq["good"]}</span> good fit</span>'
                   f'<span><span class="num" style="color:var(--bad)">{lq["not_fit"]}</span> not a fit</span></div>'
                   f'{f"<ul style=margin-top:8px>{notes}</ul>" if notes else ""}<p class="muted" style="margin:8px 0 0">{ask}</p></section>')

    answered = [f for f in data.get("client_feedback", []) if f.get("answer")][-4:]
    qa_html = ""
    if answered:
        qa_html = ('<section class="card"><h2 class="sec">You asked, we answered</h2>' + "".join(
            f'<div class="qa"><div class="q">You asked: {_e(f["message"])}</div><div class="a">{_e(f["answer"])}</div></div>'
            for f in answered) + "</section>")

    # Folded details
    rows = ""
    for s in scope.get("stages", []):
        st = s.get("status") or "low_data"
        lab = {"good": "On target", "ok": "Close", "poor": "Below target", "low_data": "Too early"}.get(st, st)
        rows += (f"<tr><td>{_e(s['label'])}</td><td>{_num(s.get('count'))}</td><td>{_pct(s.get('rate'))}</td>"
                 f"<td>{_pct(s.get('target'))}</td><td><span class='st {st}'>{lab}</span></td></tr>")
    det = []
    if rows:
        det.append('<div><h3>Step by step, from ad to booking</h3><p class="muted" style="margin:0 0 6px">Each rate is the share who made it '
                   'from the step before.</p><div class="tw"><table><thead><tr><th>Step</th><th>Count</th><th>Rate</th><th>Target</th>'
                   f'<th></th></tr></thead><tbody>{rows}</tbody></table></div></div>')
    t = data["to_date"]["kpis"] or {}
    if not final:
        det.append('<div><h3>Campaign so far</h3><div class="mini">'
                   f'<div><div class="lbl">Booked</div><div class="num">{_num(t.get("booked"))}</div></div>'
                   f'<div><div class="lbl">Showed up</div><div class="num">{_num(t.get("shows"))}</div></div>'
                   f'<div><div class="lbl">Became patients</div><div class="num">{_num(t.get("patients"))}</div></div>'
                   f'<div><div class="lbl">Leads</div><div class="num">{_num(t.get("leads"))}</div></div>'
                   f'<div><div class="lbl">Cost per lead</div><div class="num">{_money(t.get("cost_per_lead"))}</div></div>'
                   f'<div><div class="lbl">Ad spend</div><div class="num">{_money(t.get("spend"))}</div></div></div></div>')
    else:
        det.append('<div><h3>Whole campaign</h3><div class="mini">'
                   f'<div><div class="lbl">Showed up</div><div class="num">{_num(t.get("shows"))}</div></div>'
                   f'<div><div class="lbl">Became patients</div><div class="num">{_num(t.get("patients"))}</div></div>'
                   f'<div><div class="lbl">Ad spend</div><div class="num">{_money(t.get("spend"))}</div></div></div></div>')
    ai = data.get("ai_agent_to_date") if final else data.get("ai_agent_week")
    if ai and ai.get("leads"):
        det.append(f'<div><h3>Your AI text assistant {"(whole campaign)" if final else "(this week)"}</h3><div class="mini">'
                   f'<div><div class="lbl">Leads texted</div><div class="num">{_num(ai.get("leads"))}</div></div>'
                   f'<div><div class="lbl">Replied</div><div class="num">{_num(ai.get("replied"))}</div></div>'
                   f'<div><div class="lbl">Booked</div><div class="num">{_num(ai.get("booked"))}</div></div></div></div>')
    details_html = (f'<details><summary>See the full numbers</summary><div class="det">{"".join(det)}</div></details>'
                    if det else "")

    # Testimonial ask (final)
    testi_html = ""
    if final:
        review = os.environ.get("DIGIGROWTH_REVIEW_URL", "").strip()
        tt = (report.get("testimonial_text") or "").replace("{clinic}", clinic).replace(
            "{first_name}", data["client"].get("first_name") or "")
        tt_html = _e(tt).replace("{review_link_line}", (
            f'A quick Google review would mean a lot too: <a href="{_e(review)}" target="_blank" rel="noopener">leave a review</a>.'
            if review else ""))
        if tt_html.strip():
            testi_html = f'<section class="card"><h2 class="sec">Share your experience</h2><p style="margin:0">{tt_html}</p></section>'

    qs = "".join(f"<li>{_e(q)}</li>" for q in (a.get("questions_for_client") or []))
    rmin, rmax = (0, 10) if final else (1, 5)
    rating_q = ("How likely are you to recommend DigiGrowth to another clinic owner?" if final
                else "How are you feeling about the campaign this week?")
    rates = "".join(f'<button type="button" class="rate" data-v="{i}" aria-label="{i}">{i}</button>' for i in range(rmin, rmax + 1))
    extra = ('<label class="chk"><input type="checkbox" id="testimonial"> You can share my feedback as a testimonial (first name only)</label>'
             '<label class="chk"><input type="checkbox" id="next"> I\'d like to talk about the next campaign</label>') if final else ""

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex">
<title>{_e(clinic)}: {_e(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Space+Grotesk:wght@600;700&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body><div class="wrap">

<div class="top"><div><div class="eyebrow">{_e(clinic)}</div><h1>{_e(title)}</h1><div class="dates">{_e(dates)}</div></div>{pill}</div>

<section class="card hero"><p class="big">{_e(a.get("headline"))}</p><p>{_e(a.get("summary"))}</p></section>

<div class="kpis">{kpis}</div>

<div class="quick">{quick}</div>
{help_html}
{next_html}
{weeks_html}
{lq_html}
{qa_html}
{details_html}
{testi_html}

<section class="card" id="feedback"><h2 class="sec">Questions or ideas?</h2>
  <p class="muted" style="margin:0">You know your patients best. Anything you send here comes straight to Dylan, and you'll get an answer before the next report.</p>
  {f'<p style="margin:12px 0 4px;font-weight:600">I would love your take on:</p><ul>{qs}</ul>' if qs else ''}
  <form id="fb">
    <div class="muted">{_e(rating_q)} ({rmin} to {rmax})</div>
    <div class="rates">{rates}</div>
    <select id="kind" aria-label="Type"><option value="question">I have a question</option><option value="suggestion">I have a suggestion</option><option value="feedback">General feedback</option></select>
    <textarea id="msg" aria-label="Your message" placeholder="Type here..."></textarea>
    {extra}
    <button class="btn" type="submit">Send to Dylan</button>
    <div class="thanks" id="ok">Got it, thank you. Dylan will get back to you.</div>
  </form>
</section>
<footer>Prepared by DigiGrowth for {_e(clinic)}</footer>
</div>
<script>
(function(){{var r=null;document.querySelectorAll('.rate').forEach(function(b){{b.onclick=function(){{document.querySelectorAll('.rate').forEach(function(x){{x.classList.remove('on')}});b.classList.add('on');r=+b.dataset.v}}}});
var f=document.getElementById('fb');f.onsubmit=function(e){{e.preventDefault();var m=document.getElementById('msg').value.trim();
var t=document.getElementById('testimonial'),n=document.getElementById('next');
if(!m&&r===null&&!(n&&n.checked)&&!(t&&t.checked))return;var btn=f.querySelector('.btn');btn.disabled=true;
fetch(location.pathname.replace(/\\/$/,'')+'/feedback',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{kind:document.getElementById('kind').value,message:m,rating:r,testimonial_ok:!!(t&&t.checked),wants_next:!!(n&&n.checked)}})}})
.then(function(x){{if(!x.ok)throw 0;document.getElementById('ok').style.display='block';document.getElementById('msg').value='';}}).catch(function(){{btn.disabled=false;btn.textContent='Could not send, try again'}})}}}})();
</script></body></html>"""
