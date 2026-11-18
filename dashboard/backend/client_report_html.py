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
Styled like the Patient Acquisition Blueprint (design-agent/references/
blueprint-template.html, Dylan 2026-11-17): dark navy grid backdrop, glow orb,
mono status bar, clinic x DigiGrowth lockup, spec strip, numbered section heads,
glass cards with line icons. Dark only, like the blueprint.
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
        bh = max(4, round(v / top * (h - 46)))  # headroom for the value label above the tallest bar
        x = i * (w + gap)
        y = h - 22 - bh
        bars.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{bh}" rx="6" class="b"/>'
            f'<text x="{x + w / 2}" y="{y - 6}" text-anchor="middle" class="bv">{v}</text>'
            f'<text x="{x + w / 2}" y="{h - 4}" text-anchor="middle" class="bl">Wk {weeks[i]["week"]}</text>')
    return (f'<div class="chart"><svg viewBox="-4 0 {width + 8} {h}" width="{width + 8}" height="{h}" role="img" '
            f'aria-label="Bookings per week"><defs><linearGradient id="bg1" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="#5fd4ff"/><stop offset="1" stop-color="#3a7bd5"/></linearGradient></defs>'
            f'{"".join(bars)}</svg></div>')


def _icon(name: str) -> str:
    """Inline line icons (stroke = currentColor), same idea as the blueprint's: no emoji."""
    paths = {
        "check": '<path d="M20 6 9 17l-5-5"/>',
        "alert": '<path d="M12 9v4"/><path d="M12 17h.01"/><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/>',
        "arrow": '<path d="M5 12h14"/><path d="m13 6 6 6-6 6"/>',
        "star": '<path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2L12 17.3l-5.6 2.9 1.1-6.2L3 9.6l6.2-.9z"/>',
        "chart": '<path d="M3 3v18h18"/><path d="m7 15 4-4 3 3 5-6"/>',
        "grid": '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
        "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.9"/><path d="M16 3.1a4 4 0 0 1 0 7.8"/>',
        "chat": '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
        "rocket": '<path d="M4.5 16.5c-1.5 1.3-2 5-2 5s3.7-.5 5-2c.7-.8.7-2.1-.1-2.9a2.2 2.2 0 0 0-2.9-.1z"/><path d="M12 15l-3-3a22 22 0 0 1 2-3.9A12.9 12.9 0 0 1 22 2c0 2.7-.8 7.5-6 11a22.4 22.4 0 0 1-4 2z"/><path d="M9 12H4s.6-3 2-4c1.6-1.1 5 0 5 0"/><path d="M12 15v5s3-.6 4-2c1.1-1.6 0-5 0-5"/>',
        "layers": '<path d="m12 2 10 5-10 5L2 7z"/><path d="m2 17 10 5 10-5"/><path d="m2 12 10 5 10-5"/>',
        "heart": '<path d="M19 14c1.5-1.5 3-3.2 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.8 0-3 .5-4.5 2-1.5-1.5-2.7-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4 3 5.5l7 7z"/>',
    }
    return (f'<svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{paths[name]}</svg>')


CSS = """
:root{--bg:#070c1f;--bg2:#0b1230;--ink:#eef2ff;--muted:#94a0c4;--dim:#5d6a92;--line:rgba(148,170,255,.13);--line2:rgba(148,170,255,.22);
--card:linear-gradient(180deg,rgba(255,255,255,.045),rgba(255,255,255,.015));
--blue:#3a7bd5;--cyan:#5fd4ff;--violet:#8f7bff;--amber:#f5a524;--green:#34d399;--red:#ff7b7b;color-scheme:dark}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font-family:'Space Grotesk',system-ui,sans-serif;font-size:15.5px;line-height:1.55;-webkit-font-smoothing:antialiased;overflow-x:hidden}
body::before{content:"";position:fixed;inset:0;pointer-events:none;z-index:0;
background-image:linear-gradient(rgba(148,170,255,.045) 1px,transparent 1px),linear-gradient(90deg,rgba(148,170,255,.045) 1px,transparent 1px);
background-size:64px 64px;mask-image:linear-gradient(180deg,#000,rgba(0,0,0,.35) 60%,rgba(0,0,0,.15));-webkit-mask-image:linear-gradient(180deg,#000,rgba(0,0,0,.35) 60%,rgba(0,0,0,.15))}
body>*{position:relative;z-index:1}
a{color:var(--cyan)}
.wrap{max-width:1040px;margin:0 auto;padding:0 24px}
.mono{font-family:'Share Tech Mono',monospace}
.i{width:18px;height:18px;flex:none;display:block}

/* top bar */
.bar{background:rgba(5,9,25,.85);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);border-bottom:1px solid var(--line);font-family:'Share Tech Mono',monospace;font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--dim)}
.bar .wrap{display:flex;align-items:center;gap:14px;padding-top:10px;padding-bottom:10px;flex-wrap:wrap}
.bar b{color:var(--ink);font-weight:400}
.bar .dot{width:7px;height:7px;border-radius:50%;background:var(--green);box-shadow:0 0 10px var(--green)}
.bar .sep{color:var(--line2)}
.bar .r{margin-left:auto}

/* hero */
.hero{position:relative;padding:64px 0 0;overflow:hidden}
.orb{position:absolute;width:640px;height:640px;border-radius:50%;filter:blur(110px);opacity:.32;background:radial-gradient(circle,var(--blue),transparent 65%);top:-300px;right:-120px;animation:drift 16s ease-in-out infinite alternate}
@keyframes drift{to{transform:translate(-80px,60px) scale(1.1)}}
.lockup{display:inline-flex;align-items:center;gap:14px;padding:8px 16px 8px 10px;border:1px solid var(--line2);border-radius:10px;background:rgba(255,255,255,.03);margin-bottom:30px;max-width:100%}
.lockup img{height:34px;width:auto;max-width:150px;object-fit:contain;background:#fff;padding:4px 8px;border-radius:7px;box-sizing:content-box}
.lockup .cn{font-weight:600;padding-left:6px}
.lockup .x{color:var(--dim);font-family:'Share Tech Mono',monospace;font-size:13px}
.lockup .dg{font-weight:700;letter-spacing:.01em}
.kicker{font-family:'Share Tech Mono',monospace;color:var(--cyan);font-size:12.5px;letter-spacing:.16em;text-transform:uppercase}
h1{font-size:clamp(30px,4.6vw,52px);line-height:1.06;margin:16px 0 0;max-width:920px;letter-spacing:-.03em;font-weight:700;text-wrap:balance}
.grad{background:linear-gradient(90deg,var(--cyan),var(--blue) 55%,var(--violet));-webkit-background-clip:text;background-clip:text;color:transparent}
.lead{color:var(--muted);font-size:17px;max-width:760px;margin:18px 0 0}
.spec{display:grid;grid-template-columns:1.2fr 1fr 1fr 1.2fr .8fr;margin-top:44px;border-top:1px solid var(--line2);border-bottom:1px solid var(--line)}
.spec>div{padding:16px 18px 18px 0;min-width:0}
.spec>div+div{padding-left:18px;border-left:1px solid var(--line)}
.spec .k{font-family:'Share Tech Mono',monospace;font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--dim);margin-bottom:5px}
.spec .v{font-size:15px;font-weight:500;line-height:1.35}
.spec .v.hl{color:var(--cyan)}
.st-good{color:var(--green)!important}.st-warn{color:var(--amber)!important}
.sdot{display:inline-block;width:7px;height:7px;border-radius:50%;background:currentColor;margin-right:7px;vertical-align:middle;box-shadow:0 0 8px currentColor}

/* sections */
section{padding:72px 0;position:relative}
section.alt{background:linear-gradient(180deg,rgba(11,18,48,.85),rgba(7,12,31,.6));border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
.head{max-width:760px;margin:0 0 32px}
.idx{display:flex;align-items:center;gap:12px;font-family:'Share Tech Mono',monospace;font-size:12.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--muted)}
.idx .n{color:var(--cyan)}
.idx .ln{flex:0 0 48px;height:1px;background:linear-gradient(90deg,var(--cyan),transparent)}
.idx .i{width:16px;height:16px;color:var(--cyan)}
.head h2{font-size:clamp(26px,3.4vw,38px);line-height:1.1;margin:14px 0 10px;letter-spacing:-.025em;font-weight:700}
.head p{color:var(--muted);margin:0;font-size:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:inset 0 1px 0 rgba(255,255,255,.05)}
.ib{width:38px;height:38px;border-radius:10px;display:grid;place-items:center;flex:none;border:1px solid rgba(95,212,255,.28);background:rgba(58,123,213,.12);color:var(--cyan)}
.ib.amb{border-color:rgba(245,165,36,.3);background:rgba(245,165,36,.1);color:var(--amber)}
.ib.grn{border-color:rgba(52,211,153,.3);background:rgba(52,211,153,.1);color:var(--green)}

/* numbers */
.outs{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}
.out{padding:22px 20px;min-width:0}
.out .k{font-family:'Share Tech Mono',monospace;font-size:11px;letter-spacing:.14em;color:var(--dim);text-transform:uppercase}
.out .v{font-size:44px;font-weight:700;letter-spacing:-.03em;line-height:1;margin:14px 0 10px;font-variant-numeric:tabular-nums}
.out .v small{font-size:17px;color:var(--muted);font-weight:500;letter-spacing:0}
.out.hl{border-color:rgba(95,212,255,.4);background:linear-gradient(180deg,rgba(58,123,213,.16),rgba(58,123,213,.04))}
.chg{font-size:13px;font-weight:600}.chg.good{color:var(--green)}.chg.bad{color:var(--red)}.chg.flat,.chg.none{color:var(--muted);font-weight:500}
.prog{height:6px;border-radius:99px;background:rgba(148,170,255,.12);overflow:hidden;margin:0 0 10px}
.prog i{display:block;height:100%;border-radius:99px;background:linear-gradient(90deg,var(--cyan),var(--blue))}

/* quick read */
.g-cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
.g-cards .card{padding:22px}
.g-cards .top{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}
.g-cards .no{font-family:'Share Tech Mono',monospace;font-size:12px;color:var(--dim);letter-spacing:.1em}
.g-cards h4{margin:0 0 8px;font-size:17px;letter-spacing:-.01em}
ul.ticks{list-style:none;padding:0;margin:0;display:grid;gap:10px}
ul.ticks li{position:relative;padding-left:18px;color:var(--muted);font-size:14.5px;line-height:1.5}
ul.ticks li::before{content:"";position:absolute;left:0;top:.62em;width:7px;height:7px;border-radius:2px;background:var(--cyan);opacity:.75}
ul.ticks li.empty{padding-left:0}ul.ticks li.empty::before{display:none}
.help{display:flex;gap:16px;align-items:flex-start;margin-top:16px;padding:20px 22px;border-color:rgba(95,212,255,.3)}
.help b{display:block;margin-bottom:8px;font-size:16px}

/* feature (next campaign / feedback): the blueprint's close block */
.guar{padding:44px 40px 40px;background:radial-gradient(ellipse at 0% 0%,rgba(58,123,213,.25),transparent 55%),radial-gradient(ellipse at 100% 100%,rgba(143,123,255,.14),transparent 50%),#060b1e;border:1px solid rgba(95,212,255,.25);border-radius:18px;position:relative;overflow:hidden}
.guar h2{font-size:clamp(26px,3.6vw,42px);margin:14px 0 12px;line-height:1.06;letter-spacing:-.03em;max-width:780px}
.guar .lead{margin:0 0 20px}
.guar ul.ticks li{color:var(--ink)}
.ask{margin:22px 0 0;padding-top:18px;border-top:1px dashed var(--line2);font-weight:600}
.ask span{display:block;font-weight:400;color:var(--muted);font-size:14px;margin-top:4px}

/* chart, quality, Q&A */
.chart{overflow-x:auto;padding:24px 22px 16px}
.chart .b{fill:url(#bg1)}.chart .bv{fill:var(--ink);font:600 14px 'Space Grotesk',sans-serif}.chart .bl{fill:var(--dim);font:12px 'Share Tech Mono',monospace;letter-spacing:.06em}
.two{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:16px}
.lq{padding:22px}
.lq .row{display:flex;gap:28px;flex-wrap:wrap;margin-bottom:14px}
.lq .num{font-size:40px;font-weight:700;letter-spacing:-.03em;line-height:1}
.lq .num+span{display:block;font-family:'Share Tech Mono',monospace;font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--dim);margin-top:6px}
.qa{padding:18px 22px}
.qa+.qa{margin-top:12px}
.qa .q{font-family:'Share Tech Mono',monospace;font-size:12px;letter-spacing:.06em;color:var(--cyan);margin-bottom:6px}
.qa .a{color:var(--ink)}
.muted{color:var(--muted);font-size:14.5px}

/* full numbers */
details{background:var(--card);border:1px solid var(--line);border-radius:14px}
summary{cursor:pointer;padding:18px 22px;font-weight:600;font-size:16px;list-style:none;display:flex;justify-content:space-between;align-items:center;gap:12px}
summary::-webkit-details-marker{display:none}
summary::after{content:"+";font-family:'Share Tech Mono',monospace;font-size:20px;color:var(--cyan)}
details[open] summary::after{content:"\\2013"}
.det{padding:0 22px 22px;display:grid;gap:24px}
.det h3{font-family:'Share Tech Mono',monospace;font-size:11.5px;letter-spacing:.14em;text-transform:uppercase;margin:0 0 8px;color:var(--dim);font-weight:400}
.tw{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:14.5px;font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:10px 8px;border-bottom:1px solid var(--line);white-space:nowrap}
th{font-family:'Share Tech Mono',monospace;color:var(--dim);font-weight:400;font-size:11px;letter-spacing:.12em;text-transform:uppercase}
.st{font-family:'Share Tech Mono',monospace;font-size:11px;letter-spacing:.08em;text-transform:uppercase;padding:3px 8px;border-radius:6px;border:1px solid}
.st.good{color:var(--green);border-color:rgba(52,211,153,.3);background:rgba(52,211,153,.08)}
.st.ok{color:var(--amber);border-color:rgba(245,165,36,.3);background:rgba(245,165,36,.08)}
.st.poor{color:var(--red);border-color:rgba(255,123,123,.3);background:rgba(255,123,123,.08)}
.st.low_data{color:var(--muted);border-color:var(--line2);background:rgba(255,255,255,.02)}
.mini{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
.mini>div{border:1px solid var(--line);border-radius:10px;padding:12px 14px;background:rgba(255,255,255,.02)}
.mini .num{font-size:24px;font-weight:700;letter-spacing:-.02em}
.mini .lbl{font-family:'Share Tech Mono',monospace;font-size:10.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--dim)}

/* feedback form */
form{display:grid;gap:12px;margin-top:22px;max-width:640px}
.fl{font-family:'Share Tech Mono',monospace;font-size:11.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--dim)}
.rates{display:flex;flex-wrap:wrap;gap:6px}
.rate{min-width:42px;padding:9px 0;border-radius:9px;border:1px solid var(--line2);background:rgba(255,255,255,.03);color:var(--ink);font:600 15px 'Space Grotesk',sans-serif;cursor:pointer}
.rate:hover{border-color:rgba(95,212,255,.45)}
.rate.on{background:rgba(58,123,213,.3);border-color:var(--cyan);color:#fff}
select,textarea{width:100%;background:rgba(5,9,25,.6);border:1px solid var(--line2);border-radius:10px;color:var(--ink);padding:11px 13px;font:inherit}
select:focus,textarea:focus{outline:none;border-color:var(--cyan)}
textarea{min-height:110px;resize:vertical}
.chk{display:flex;gap:10px;align-items:center;font-size:14.5px;color:var(--muted)}
.chk input{accent-color:var(--blue);width:16px;height:16px}
.btn{justify-self:start;background:linear-gradient(90deg,var(--blue),#4f8ff0);border:0;color:#fff;font:600 15px 'Space Grotesk',sans-serif;padding:12px 24px;border-radius:10px;cursor:pointer;box-shadow:0 10px 30px rgba(58,123,213,.35)}
.btn:disabled{opacity:.6}
.btn:focus-visible,.rate:focus-visible,summary:focus-visible{outline:2px solid var(--cyan);outline-offset:2px}
.qs{margin:18px 0 0;padding:16px 18px}
.qs b{display:block;margin-bottom:8px}
.thanks{display:none;color:var(--green);font-weight:600}

footer{color:var(--dim);font-family:'Share Tech Mono',monospace;font-size:12px;letter-spacing:.1em;text-transform:uppercase;border-top:1px solid var(--line)}
footer .wrap{display:flex;justify-content:space-between;gap:12px;padding-top:22px;padding-bottom:30px;flex-wrap:wrap}

.reveal{opacity:0;transform:translateY(20px);transition:opacity .7s ease,transform .7s ease}
.reveal.in{opacity:1;transform:none}
@media (prefers-reduced-motion:reduce){.reveal{opacity:1;transform:none;transition:none}.orb{animation:none}html{scroll-behavior:auto}}

@media (max-width:900px){
  .outs{grid-template-columns:1fr 1fr}
  .g-cards,.two{grid-template-columns:1fr}
  .spec{grid-template-columns:1fr 1fr}
  .spec>div,.spec>div+div{padding:14px 14px 14px 0;border-left:0;border-bottom:1px solid var(--line)}
  .spec>div:nth-child(even){padding-left:14px;border-left:1px solid var(--line)}
  .spec>div:last-child{grid-column:1/-1;border-bottom:0;padding-left:0;border-left:0}
  section{padding:56px 0}
  .guar{padding:32px 22px 26px}
  .bar .r{margin-left:0}
}
@media (max-width:480px){
  .wrap{padding:0 16px}
  .hero{padding-top:40px}
  h1{font-size:30px}
  .head h2{font-size:25px}
  .lead{font-size:15.5px}
  .out{padding:18px 16px}
  .out .v{font-size:34px}
  .mini{grid-template-columns:1fr 1fr}
  .bar .sep,.bar .r{display:none}
  .lockup{margin-bottom:22px}
  .kicker{font-size:11.5px;letter-spacing:.12em}
}
"""


def render_html(report: dict) -> str:
    data, a, kind = report["data"], report["analysis"], report["kind"]
    clinic = data["client"]["name"]
    logo = (data["client"].get("logo_url") or "").strip()
    camp = data["campaign"]
    final = kind == "final"
    scope = data["to_date"] if final else (data.get("week") or data["to_date"])
    k = scope.get("kpis") or {}
    lk = {} if final else (((data.get("last_week") or {}).get("kpis")) or {})
    pace = data.get("pace")

    title = "Final campaign report" if final else f"Week {report['week_number']} report"
    dates = f"{_date(report['period_start'])} – {_date(report['period_end'])}"
    issued = _date(datetime.now(ET).isoformat())

    # Numbered section heads, like the blueprint ("01 ── The numbers")
    counter = [0]

    def head(label: str, icon: str, h2: str = "", sub: str = "") -> str:
        counter[0] += 1
        return (f'<div class="head reveal"><div class="idx"><span class="n">{counter[0]:02d}</span><span class="ln"></span>'
                f'{_icon(icon)}{_e(label)}</div>'
                + (f'<h2>{h2}</h2>' if h2 else "") + (f'<p>{_e(sub)}</p>' if sub else "") + '</div>')

    alt = [False]

    def section(inner: str, sid: str = "") -> str:
        alt[0] = not alt[0]
        return (f'<section{f" id={sid!r}" if sid else ""}{" class=alt" if alt[0] else ""}>'
                f'<div class="wrap">{inner}</div></section>')

    # Status (spec strip)
    if pace:
        if pace["booked"] >= pace["goal"]:
            status = ("good", "Goal reached")
        elif final:
            status = ("warn", "Goal not reached")
        else:
            status = ("good", "On pace") if pace["on_pace"] else ("warn", "Behind pace")
        goal_v = f'{pace["booked"]} / {pace["goal"]} {_e(camp.get("goal_label") or "booked")}'
    else:
        status = None
        goal_v = f'Day {_e(camp.get("days_elapsed"))} of {_e(camp.get("length_days"))}' if camp.get("days_elapsed") else "Campaign"
    status_html = (f'<span class="st-{status[0]}"><span class="sdot"></span>{status[1]}</span>' if status else "–")

    lock_left = (f'<img src="{_e(logo)}" alt="{_e(clinic)} logo">' if logo else "") + f'<span class="cn">{_e(clinic)}</span>'

    # 01: the four numbers
    if pace:
        pct = min(100, pace["pct_of_goal"])
        bud = camp.get("budget")
        progress_line = (f'{_money(bud["spent"])} of {_money(bud["cap"])} ad budget spent' if bud
                         else f'Day {camp.get("days_elapsed")} of {camp.get("length_days")}')
        goal_tile = (f'<div class="out card hl"><div class="k">Campaign goal</div>'
                     f'<div class="v">{pace["booked"]}<small> / {pace["goal"]}</small></div>'
                     f'<div class="prog"><i style="width:{pct}%"></i></div>'
                     f'<span class="chg flat">{_e(progress_line)}</span></div>')
    else:
        goal_tile = (f'<div class="out card"><div class="k">Showed up</div><div class="v">{_num(k.get("shows"))}</div>'
                     f'{_delta(k.get("shows"), lk.get("shows"))}</div>')
    period_word = "total" if final else "this week"
    outs = (
        f'<div class="out card{"" if pace else " hl"}"><div class="k">Booked {period_word}</div><div class="v">{_num(k.get("booked"))}</div>'
        f'{"" if final else _delta(k.get("booked"), lk.get("booked"))}</div>'
        f'<div class="out card"><div class="k">Cost per booking</div><div class="v">{_money(k.get("cost_per_booking"))}</div>'
        f'{"" if final else _delta(k.get("cost_per_booking"), lk.get("cost_per_booking"), True)}</div>'
        f'<div class="out card"><div class="k">New leads</div><div class="v">{_num(k.get("leads"))}</div>'
        f'{"" if final else _delta(k.get("leads"), lk.get("leads"))}</div>'
        + goal_tile)
    sections = [section(
        head("The numbers", "chart", "The four numbers that matter" + ("" if final else " this week"),
             "The whole campaign, start to finish." if final else "Each one compared with last week.")
        + f'<div class="outs reveal">{outs}</div>', "numbers")]

    # 02: the quick read
    quick = (
        f'<div class="card"><div class="top"><span class="ib grn">{_icon("check")}</span><span class="no">01</span></div>'
        f'<h4>What\'s working</h4><ul class="ticks">{_items(a.get("on_target"))}</ul></div>'
        f'<div class="card"><div class="top"><span class="ib amb">{_icon("alert")}</span><span class="no">02</span></div>'
        f'<h4>What we\'re fixing</h4><ul class="ticks">{_items(a.get("off_target"))}</ul></div>'
        f'<div class="card"><div class="top"><span class="ib">{_icon("arrow")}</span><span class="no">03</span></div>'
        f'<h4>{"What we recommend" if final else "Next week"}</h4><ul class="ticks">{_items(a.get("next_steps"))}</ul></div>')
    help_html = ""
    if a.get("client_asks"):
        help_html = (f'<div class="card help reveal"><span class="ib">{_icon("star")}</span><div>'
                     f'<b>How your team can help</b><ul class="ticks">{_items(a["client_asks"])}</ul></div></div>')
    sections.append(section(head("The quick read", "layers", "What happened, and what we're doing about it")
                            + f'<div class="g-cards reveal">{quick}</div>{help_html}', "read"))

    # Final: next campaign + week by week
    if final:
        nc = a.get("next_campaign") or {}
        if nc.get("plan") or nc.get("intro"):
            counter[0] += 1
            sections.append(section(
                f'<div class="guar reveal"><div class="idx"><span class="n">{counter[0]:02d}</span><span class="ln"></span>'
                f'{_icon("rocket")}Your next campaign</div>'
                f'<h2>Here\'s how we\'d <span class="grad">build on these results</span>.</h2>'
                f'<p class="lead">{_e(nc.get("intro"))}</p><ul class="ticks">{_items(nc.get("plan"))}</ul>'
                f'<p class="ask">{_e(nc.get("ask"))}<span>Tick "I\'d like to talk about the next campaign" at the bottom and I\'ll reach out.</span></p>'
                f'</div>', "next"))
        if data.get("weeks"):
            sections.append(section(head("Week by week", "chart", "Bookings, week by week")
                                    + f'<div class="card reveal">{_bars(data["weeks"])}</div>', "weeks"))

    # Patient quality + Q&A (side by side when both exist)
    lq = data.get("lead_quality")
    lq_html = ""
    if lq and (lq["good"] + lq["not_fit"] or lq.get("unrated")):
        notes = "".join(f"<li>{_e(n)}</li>" for n in (lq.get("notes") or [])[:3])
        ask = ('A few patients you marked as showed and closed still need a "good fit?" answer in your portal (Appointments). '
               'It is the fastest way for us to find you more of the right people.' if lq.get("unrated")
               else "Thanks for rating your patients. We use it to tune who sees your ads.")
        lq_html = (f'<div class="card lq reveal"><div class="row">'
                   f'<div><div class="num" style="color:var(--green)">{lq["good"]}</div><span>Good fit</span></div>'
                   f'<div><div class="num" style="color:var(--red)">{lq["not_fit"]}</div><span>Not a fit</span></div></div>'
                   f'{f"<ul class=ticks style=margin-bottom:12px>{notes}</ul>" if notes else ""}<p class="muted" style="margin:0">{ask}</p></div>')
    answered = [f for f in data.get("client_feedback", []) if f.get("answer")][-4:]
    qa_html = "".join(
        f'<div class="card qa reveal"><div class="q">You asked: {_e(f["message"])}</div><div class="a">{_e(f["answer"])}</div></div>'
        for f in answered)
    if lq_html and qa_html:
        sections.append(section(head("Patients + your questions", "users", "Patient quality, and your answers")
                                + f'<div class="two">{lq_html}<div>{qa_html}</div></div>', "quality"))
    elif lq_html:
        sections.append(section(head("Patient quality", "users", "Patient quality (your ratings)") + lq_html, "quality"))
    elif qa_html:
        sections.append(section(head("You asked", "chat", "You asked, we answered") + qa_html, "answers"))

    # Folded details
    rows = ""
    for s in scope.get("stages", []):
        st = s.get("status") or "low_data"
        lab = {"good": "On target", "ok": "Close", "poor": "Below target", "low_data": "Too early"}.get(st, st)
        rows += (f"<tr><td>{_e(s['label'])}</td><td>{_num(s.get('count'))}</td><td>{_pct(s.get('rate'))}</td>"
                 f"<td>{_pct(s.get('target'))}</td><td><span class='st {st}'>{lab}</span></td></tr>")
    det = []
    if rows:
        det.append('<div><h3>Step by step, from ad to booking</h3><p class="muted" style="margin:0 0 8px">Each rate is the share who made it '
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
    if det:
        sections.append(section(head("Full numbers", "grid", "", "Everything behind the numbers above, step by step.")
                                + f'<details class="reveal"><summary>See the full numbers</summary><div class="det">{"".join(det)}</div></details>',
                                "details"))

    # Testimonial ask (final)
    if final:
        review = os.environ.get("DIGIGROWTH_REVIEW_URL", "").strip()
        tt = (report.get("testimonial_text") or "").replace("{clinic}", clinic).replace(
            "{first_name}", data["client"].get("first_name") or "")
        tt_html = _e(tt).replace("{review_link_line}", (
            f'A quick Google review would mean a lot too: <a href="{_e(review)}" target="_blank" rel="noopener">leave a review</a>.'
            if review else ""))
        if tt_html.strip():
            sections.append(section(head("Share your experience", "heart", "Share your experience")
                                    + f'<div class="card reveal" style="padding:22px"><p style="margin:0">{tt_html}</p></div>', "share"))

    # Feedback (the blueprint's close block)
    qs = "".join(f"<li>{_e(q)}</li>" for q in (a.get("questions_for_client") or []))
    rmin, rmax = (0, 10) if final else (1, 5)
    rating_q = ("How likely are you to recommend DigiGrowth to another clinic owner?" if final
                else "How are you feeling about the campaign this week?")
    rates = "".join(f'<button type="button" class="rate" data-v="{i}" aria-label="{i}">{i}</button>' for i in range(rmin, rmax + 1))
    extra = ('<label class="chk"><input type="checkbox" id="testimonial"> You can share my feedback as a testimonial (first name only)</label>'
             '<label class="chk"><input type="checkbox" id="next"> I\'d like to talk about the next campaign</label>') if final else ""
    counter[0] += 1
    sections.append(section(f"""<div class="guar reveal" id="feedback">
  <div class="idx"><span class="n">{counter[0]:02d}</span><span class="ln"></span>{_icon("chat")}Questions or ideas</div>
  <h2>You know your patients best. <span class="grad">Tell us what you see.</span></h2>
  <p class="lead">Anything you send here comes straight to Dylan, and you'll get an answer before the next report.</p>
  {f'<div class="card qs"><b>I would love your take on:</b><ul class="ticks">{qs}</ul></div>' if qs else ''}
  <form id="fb">
    <div class="fl">{_e(rating_q)} ({rmin} to {rmax})</div>
    <div class="rates">{rates}</div>
    <select id="kind" aria-label="Type"><option value="question">I have a question</option><option value="suggestion">I have a suggestion</option><option value="feedback">General feedback</option></select>
    <textarea id="msg" aria-label="Your message" placeholder="Type here..."></textarea>
    {extra}
    <button class="btn" type="submit">Send to Dylan</button>
    <div class="thanks" id="ok">Got it, thank you. Dylan will get back to you.</div>
  </form>
</div>"""))

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex">
<meta name="theme-color" content="#070c1f">
<title>{_e(clinic)} · {_e(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Share+Tech+Mono&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body>

<div class="bar"><div class="wrap"><span class="dot"></span><b>{"Final Campaign Report" if final else "Weekly Campaign Report"}</b><span class="sep">/</span><span>Prepared for {_e(clinic)}</span><span class="r">{_e(dates)}</span></div></div>

<header class="hero">
  <div class="orb"></div>
  <div class="wrap">
    <div class="lockup reveal">{lock_left}<span class="x">×</span><span class="dg">DigiGrowth</span></div>
    <div class="kicker reveal">Digital Growth Engine // {_e(title)}</div>
    <h1 class="reveal">{_e(a.get("headline"))}</h1>
    <p class="lead reveal">{_e(a.get("summary"))}</p>
    <div class="spec reveal">
      <div><div class="k">Prepared for</div><div class="v">{_e(clinic)}</div></div>
      <div><div class="k">Period</div><div class="v">{_e(dates)}</div></div>
      <div><div class="k">Status</div><div class="v">{status_html}</div></div>
      <div><div class="k">{"Campaign goal" if pace else "Campaign"}</div><div class="v hl">{goal_v}</div></div>
      <div><div class="k">Issued</div><div class="v">{_e(issued)}</div></div>
    </div>
  </div>
</header>

{"".join(sections)}

<footer><div class="wrap"><span>Prepared for {_e(clinic)} by DigiGrowth</span><span>digigrowthllc.com</span></div></footer>

<script>
(function(){{
if('IntersectionObserver' in window){{var io=new IntersectionObserver(function(es){{es.forEach(function(e){{if(e.isIntersecting){{e.target.classList.add('in');io.unobserve(e.target)}}}})}},{{threshold:0.08}});
document.querySelectorAll('.reveal').forEach(function(el){{io.observe(el)}})}}else{{document.querySelectorAll('.reveal').forEach(function(el){{el.classList.add('in')}})}}
var r=null;document.querySelectorAll('.rate').forEach(function(b){{b.onclick=function(){{document.querySelectorAll('.rate').forEach(function(x){{x.classList.remove('on')}});b.classList.add('on');r=+b.dataset.v}}}});
var f=document.getElementById('fb');f.onsubmit=function(e){{e.preventDefault();var m=document.getElementById('msg').value.trim();
var t=document.getElementById('testimonial'),n=document.getElementById('next');
if(!m&&r===null&&!(n&&n.checked)&&!(t&&t.checked))return;var btn=f.querySelector('.btn');btn.disabled=true;
fetch(location.pathname.replace(/\\/$/,'')+'/feedback',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{kind:document.getElementById('kind').value,message:m,rating:r,testimonial_ok:!!(t&&t.checked),wants_next:!!(n&&n.checked)}})}})
.then(function(x){{if(!x.ok)throw 0;document.getElementById('ok').style.display='block';document.getElementById('msg').value='';}}).catch(function(){{btn.disabled=false;btn.textContent='Could not send, try again'}})}}}})();
</script></body></html>"""
