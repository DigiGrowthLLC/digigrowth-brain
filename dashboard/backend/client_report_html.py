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
import math
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
.i{width:18px;height:18px;flex:none;display:block}
.mono{font-family:'Share Tech Mono',monospace;letter-spacing:.12em;text-transform:uppercase;font-size:11px;color:var(--dim)}

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
.head{max-width:760px;margin:0 0 28px}
.idx{display:flex;align-items:center;gap:12px;font-family:'Share Tech Mono',monospace;font-size:12.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--muted)}
.idx .n{color:var(--cyan)}
.idx .ln{flex:0 0 48px;height:1px;background:linear-gradient(90deg,var(--cyan),transparent)}
.idx .i{width:16px;height:16px;color:var(--cyan)}
.head h2{font-size:clamp(26px,3.4vw,38px);line-height:1.1;margin:14px 0 10px;letter-spacing:-.025em;font-weight:700;text-wrap:balance}
.head p{color:var(--muted);margin:0;font-size:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:inset 0 1px 0 rgba(255,255,255,.05)}
.ib{width:38px;height:38px;border-radius:10px;display:grid;place-items:center;flex:none;border:1px solid rgba(95,212,255,.28);background:rgba(58,123,213,.12);color:var(--cyan)}
.ib.amb{border-color:rgba(245,165,36,.3);background:rgba(245,165,36,.1);color:var(--amber)}
.ib.grn{border-color:rgba(52,211,153,.3);background:rgba(52,211,153,.1);color:var(--green)}
.stack{display:grid;gap:16px}

/* results: goal + headline numbers (same four as the portal's Results tab) */
.goal{padding:22px 24px;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px 24px;align-items:end;border-color:rgba(95,212,255,.35);background:linear-gradient(180deg,rgba(58,123,213,.16),rgba(58,123,213,.04))}
.goal .big{font-size:40px;font-weight:700;letter-spacing:-.03em;line-height:1.05}
.goal .big small{font-size:18px;color:var(--muted);font-weight:500;letter-spacing:0}
.goal .side{text-align:right;font-size:14px;color:var(--muted)}
.goal .side b{display:block;font-size:15px;margin-bottom:2px}
.goal .prog{grid-column:1/-1}
.prog{height:8px;border-radius:99px;background:rgba(148,170,255,.12);overflow:hidden}
.prog i{display:block;height:100%;border-radius:99px;background:linear-gradient(90deg,var(--cyan),var(--blue))}
.kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.kpi{padding:18px 20px;min-width:0}
.kpi .lbl{font-size:13px;color:var(--muted);font-weight:500}
.kpi .v{font-size:34px;font-weight:700;letter-spacing:-.03em;line-height:1.1;margin:6px 0 4px;font-variant-numeric:tabular-nums}
.kpi .h{font-size:12.5px;color:var(--dim)}
.chg{display:inline-block;margin-top:6px;font-size:12.5px;font-weight:600}.chg.good{color:var(--green)}.chg.bad{color:var(--red)}.chg.flat,.chg.none{color:var(--muted);font-weight:500}

/* patient journey (mirrors the portal's JourneyRow) */
.journey{padding:20px 22px}
.journey h3{margin:0;font-size:17px}
.journey .sub{font-size:13.5px;color:var(--muted);margin-top:2px}
.leak{margin-top:14px;padding:11px 14px;border-radius:9px;background:rgba(245,165,36,.08);border:1px solid rgba(245,165,36,.2);font-size:14px;color:#ecdcb4}
.leak b{color:var(--amber)}
.path-h{margin:20px 0 2px;font-family:'Share Tech Mono',monospace;font-size:11.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--cyan)}
.jrow{display:flex;align-items:center;gap:14px;flex-wrap:wrap;padding:12px 0;border-top:1px solid var(--line)}
.jrow.first{border-top:0}
.jrow .nm{display:flex;align-items:center;gap:12px;flex:1 1 210px;min-width:0}
.jrow .no{width:26px;height:26px;border-radius:13px;flex:none;display:grid;place-items:center;background:rgba(58,123,213,.15);color:#6ab0ff;font-size:12px;font-weight:700}
.jrow .t{font-size:14.5px;font-weight:600}
.jrow .hp{font-size:12px;color:var(--dim)}
.jrow .bw{display:flex;align-items:center;gap:12px;flex:2 1 220px;min-width:0}
.jrow .trk{flex:1;height:10px;border-radius:5px;background:rgba(255,255,255,.05);overflow:hidden}
.jrow .trk i{display:block;height:100%;border-radius:5px;background:linear-gradient(90deg,var(--blue),var(--cyan))}
.jrow .ct{width:76px;text-align:right;font-size:20px;font-weight:700;font-variant-numeric:tabular-nums}
.jrow .rt{width:130px;margin-left:auto;text-align:right}
.jrow .rt b{display:inline-flex;align-items:center;gap:6px;font-size:14.5px}
.jrow .rt span{display:block;font-size:11.5px;color:var(--dim)}
.jrow .nt{flex-basis:100%;font-size:12px;color:var(--muted);margin-left:38px}
.jrow.off .t,.jrow.off .ct{color:var(--dim)}
.rep{display:inline-block;margin-left:8px;padding:1px 7px;border-radius:6px;font-size:10.5px;font-weight:600;letter-spacing:.02em;vertical-align:2px;color:var(--amber);background:rgba(245,165,36,.1);border:1px solid rgba(245,165,36,.28);white-space:nowrap}
.rep.kr{display:table;margin:8px 0 0}
.fnote{font-size:12.5px;color:var(--muted);margin:0}
.fnote b{color:var(--amber);font-weight:600}
.tone-good{color:var(--green)}.tone-ok{color:var(--amber)}.tone-poor{color:var(--red)}
.tdot{width:7px;height:7px;border-radius:50%;background:currentColor;display:inline-block}
.legend{display:flex;gap:16px;flex-wrap:wrap;margin-top:12px;padding-top:12px;border-top:1px solid var(--line);font-size:12px;color:var(--muted)}
.legend span{display:inline-flex;align-items:center;gap:6px}
.trio{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}
.mini{padding:20px 22px}
.mini h3{margin:0 0 12px;font-size:16px}
.mini .g{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.mini .g>div{border:1px solid var(--line);border-radius:10px;padding:12px 14px;background:rgba(255,255,255,.02);min-width:0}
.mini .lbl{font-size:12.5px;color:var(--muted)}
.mini .num{font-size:22px;font-weight:700;letter-spacing:-.02em;margin-top:2px}
.brk{display:flex;flex-wrap:wrap;gap:6px 14px;margin-top:12px;padding-top:12px;border-top:1px solid var(--line);font-size:13px;color:var(--muted)}
.brk b{color:var(--ink)}
.mini .h{font-size:11.5px;color:var(--dim)}

/* appointments waiting on an outcome */
.appts{padding:6px 22px}
.ap-empty{padding:18px 0;color:var(--muted);font-size:14.5px}
.ap{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,2fr);gap:12px 20px;padding:18px 0;border-top:1px solid var(--line)}
.ap:first-child{border-top:0}
.ap .who b{display:block;font-size:15.5px}
.ap .who span{font-size:13px;color:var(--muted)}
.ap .ctl{display:grid;gap:10px;min-width:0}
.seg{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.seg .q{font-size:12.5px;color:var(--dim);width:150px}
.opt{padding:8px 14px;border-radius:9px;border:1px solid var(--line2);background:rgba(255,255,255,.03);color:var(--ink);font:600 14px 'Space Grotesk',sans-serif;cursor:pointer}
.opt:hover{border-color:rgba(95,212,255,.45)}
.opt.on.pos{background:rgba(52,211,153,.16);border-color:var(--green);color:var(--green)}
.opt.on.neg{background:rgba(255,123,123,.12);border-color:var(--red);color:var(--red)}
.opt:focus-visible{outline:2px solid var(--cyan);outline-offset:2px}
.ap textarea{min-height:56px}
.ap .row{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.ap .btn{padding:9px 18px;font-size:14px;box-shadow:none}
.ap [hidden]{display:none!important}
.ap .ok{color:var(--green);font-size:13.5px;font-weight:600}
.ap .bad{color:var(--red);font-size:13.5px}
@media (max-width:700px){.ap{grid-template-columns:1fr}.seg .q{width:100%}}

.quick{padding:4px 24px}
.qr{display:grid;grid-template-columns:38px minmax(0,1fr);gap:16px;padding:18px 0;border-top:1px solid var(--line)}
.qr:first-child{border-top:0}
.qr h4{margin:6px 0 10px;font-size:16.5px}
.quick ul.ticks li{color:var(--ink);font-size:15px}
/* quick read */
.g-cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
.g-cards .card{padding:22px}
.g-cards .top{display:flex;align-items:center;gap:12px;margin-bottom:14px}
.g-cards h4{margin:0;font-size:17px;letter-spacing:-.01em}
ul.ticks{list-style:none;padding:0;margin:0;display:grid;gap:10px}
ul.ticks li{position:relative;padding-left:18px;color:var(--muted);font-size:14.5px;line-height:1.5}
ul.ticks li::before{content:"";position:absolute;left:0;top:.62em;width:7px;height:7px;border-radius:2px;background:var(--cyan);opacity:.75}
ul.ticks li.empty{padding-left:0}ul.ticks li.empty::before{display:none}
.help{display:flex;gap:16px;align-items:flex-start;margin-top:16px;padding:20px 22px;border-color:rgba(95,212,255,.3)}
.help b{display:block;margin-bottom:8px;font-size:16px}

/* feature panels (next campaign, testimonial, questions): the blueprint's close block */
.guar{padding:44px 40px 40px;background:radial-gradient(ellipse at 0% 0%,rgba(58,123,213,.25),transparent 55%),radial-gradient(ellipse at 100% 100%,rgba(143,123,255,.14),transparent 50%),#060b1e;border:1px solid rgba(95,212,255,.25);border-radius:18px;position:relative;overflow:hidden}
.guar h2{font-size:clamp(26px,3.6vw,42px);margin:14px 0 12px;line-height:1.06;letter-spacing:-.03em;max-width:780px;text-wrap:balance}
.guar .lead{margin:0 0 20px}
.guar ul.ticks li{color:var(--ink)}
.cta{display:flex;align-items:center;gap:16px;flex-wrap:wrap;margin-top:24px;padding-top:20px;border-top:1px dashed var(--line2)}
.cta p{margin:0;font-weight:600;flex:1 1 260px}

/* chart, quality, Q&A */
.chart{overflow-x:auto;padding:24px 22px 16px}
.chart .b{fill:url(#bg1)}.chart .bv{fill:var(--ink);font:600 14px 'Space Grotesk',sans-serif}.chart .bl{fill:var(--dim);font:12px 'Share Tech Mono',monospace;letter-spacing:.06em}
.two{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:16px}
.lq{padding:22px}
.lq .row{display:flex;gap:28px;flex-wrap:wrap;margin-bottom:14px}
.lq .num{font-size:40px;font-weight:700;letter-spacing:-.03em;line-height:1}
.lq .num+span{display:block;font-size:13px;color:var(--muted);margin-top:6px}
.qa{padding:18px 22px}
.qa+.qa{margin-top:12px}
.qa .q{font-size:13px;color:var(--cyan);margin-bottom:6px}
.muted{color:var(--muted);font-size:14.5px}

/* forms */
form{display:grid;gap:14px;margin-top:22px;max-width:660px}
.fl{font-size:14.5px;font-weight:600}
.fl small{display:block;font-weight:400;color:var(--muted);font-size:13px}
.rates{display:flex;flex-wrap:wrap;gap:6px}
.rate{min-width:42px;padding:9px 0;border-radius:9px;border:1px solid var(--line2);background:rgba(255,255,255,.03);color:var(--ink);font:600 15px 'Space Grotesk',sans-serif;cursor:pointer}
.rate:hover{border-color:rgba(95,212,255,.45)}
.rate.on{background:rgba(58,123,213,.3);border-color:var(--cyan);color:#fff}
.stars{display:flex;align-items:center;gap:2px;flex-wrap:wrap}
.star{min-width:0;padding:4px;border:0;background:none;color:rgba(148,170,255,.35);line-height:0}
.star svg{width:36px;height:36px;fill:currentColor;transition:transform .12s ease,color .12s ease}
.star:hover svg{transform:scale(1.08)}
.stars:hover .star{color:#f5c84c}.stars .star:hover~.star{color:rgba(148,170,255,.35)}
.star.on{background:none;color:#f5c84c}
.stars-l{margin-left:12px;font-size:14px;color:var(--muted)}
.scale{display:flex;justify-content:space-between;max-width:520px;font-size:12px;color:var(--dim)}
select,textarea{width:100%;background:rgba(5,9,25,.6);border:1px solid var(--line2);border-radius:10px;color:var(--ink);padding:11px 13px;font:inherit}
select:focus,textarea:focus{outline:none;border-color:var(--cyan)}
textarea{min-height:120px;resize:vertical}
.chk{display:flex;gap:10px;align-items:flex-start;font-size:14.5px;color:var(--muted)}
.chk input{accent-color:var(--blue);width:16px;height:16px;margin-top:3px;flex:none}
.btn{justify-self:start;background:linear-gradient(90deg,var(--blue),#4f8ff0);border:0;color:#fff;font:600 15px 'Space Grotesk',sans-serif;padding:12px 24px;border-radius:10px;cursor:pointer;box-shadow:0 10px 30px rgba(58,123,213,.35)}
.btn:disabled{opacity:.6;cursor:default}
.btn:focus-visible,.rate:focus-visible{outline:2px solid var(--cyan);outline-offset:2px}
.qs{margin:18px 0 0;padding:16px 18px}
.qs b{display:block;margin-bottom:8px}
.thanks{display:none;color:var(--green);font-weight:600}
.err{display:none;color:var(--red);font-size:14px}
.review{margin:18px 0 0;font-size:14.5px;color:var(--muted)}

footer{color:var(--dim);font-family:'Share Tech Mono',monospace;font-size:12px;letter-spacing:.1em;text-transform:uppercase;border-top:1px solid var(--line)}
footer .wrap{display:flex;justify-content:space-between;gap:12px;padding-top:22px;padding-bottom:30px;flex-wrap:wrap}

.reveal{opacity:0;transform:translateY(20px);transition:opacity .7s ease,transform .7s ease}
.reveal.in{opacity:1;transform:none}
@media (prefers-reduced-motion:reduce){.reveal{opacity:1;transform:none;transition:none}.orb{animation:none}html{scroll-behavior:auto}}

@media (max-width:900px){
  .kpis{grid-template-columns:1fr 1fr}
  .g-cards,.two{grid-template-columns:1fr}
  .spec{grid-template-columns:1fr 1fr}
  .spec>div,.spec>div+div{padding:14px 14px 14px 0;border-left:0;border-bottom:1px solid var(--line)}
  .spec>div:nth-child(even){padding-left:14px;border-left:1px solid var(--line)}
  .spec>div:last-child{grid-column:1/-1;border-bottom:0;padding-left:0;border-left:0}
  section{padding:56px 0}
  .guar{padding:32px 22px 26px}
  .bar .r{margin-left:0}
}
@media (max-width:560px){
  .goal{grid-template-columns:1fr}
  .goal .side{text-align:left}
  .jrow{gap:8px 12px}
  .jrow .nm{flex:1 1 0}
  .jrow .rt{order:1;width:auto;margin-left:auto}
  .jrow .bw{order:2;flex:1 1 100%;padding-left:38px}
  .jrow .nt{order:3}
}
@media (max-width:480px){
  .wrap{padding:0 16px}
  .hero{padding-top:40px}
  h1{font-size:30px}
  .head h2{font-size:25px}
  .lead{font-size:15.5px}
  .kpi{padding:16px}
  .kpi .v{font-size:28px}
  .goal .big{font-size:32px}
  .journey,.mini{padding:18px 16px}
  .bar .sep,.bar .r{display:none}
  .lockup{margin-bottom:22px}
  .kicker{font-size:11.5px;letter-spacing:.12em}
}
"""

# Plain-English line under each journey step (same as the portal's STEP_HELP).
STEP_HELP = {
    "impressions": "Times your ad was shown",
    "link_clicks": "Clicked the ad",
    "leads": "Filled out the ad's form",
    "replied": "Texted back or picked up a call",
    "funnel_visits": "Landed on your page",
    "booking_views": "Opened the booking page",
    "booking_started": "Entered their name and number",
    "checkout": "Reached the payment step",
    "booked": "Booked a visit",
    "showed": "Came to their visit",
    "patient": "Started care with you",
}
TONE = {"good": "On target", "ok": "Close", "poor": "Below target"}
# Steps the clinic reports by hand (show/no-show and closed in the portal's Appointments).
CLIENT_REPORTED = {"showed", "patient"}
REP_TAG = '<span class="rep">Reported by your team</span>'
REPORTED_NOTE = ('<p class="fnote"><b>*</b> Show-ups and new patients come from what your team marks in your portal '
                 "(Appointments: showed / closed). Visits that haven't been marked yet aren't counted, so the show rate "
                 "and close rate only reflect the visits you've updated.</p>")


# "Appointments waiting on an outcome": loads GET /report/<slug>/appointments
# and saves with PATCH /report/<slug>/appointments/<id> (routers/client_success.py).
APPTS_JS = r'''
(function(){
var box=document.getElementById('apList'),msg=document.getElementById('apMsg');if(!box)return;
var base=location.pathname.replace(/\/$/,'')+'/appointments';
function esc(t){var d=document.createElement('div');d.textContent=t==null?'':t;return d.innerHTML}
function left(){var n=box.querySelectorAll('.ap').length;
msg.textContent=n?(n+(n===1?' visit needs':' visits need')+' an outcome.'):"You're all caught up. Every past visit has an outcome."}
function row(a){var el=document.createElement('div');el.className='ap';var st={show:a.outcome_show,close:a.outcome_close};
el.innerHTML='<div class="who"><b>'+esc(a.name)+'</b><span>'+esc(a.when)+'</span></div><div class="ctl">'+
'<div class="seg"><span class="q">Did they come in?</span><button type="button" class="opt pos" data-f="show" data-v="show">Showed up</button>'+
'<button type="button" class="opt neg" data-f="show" data-v="no_show">No-show</button></div>'+
'<div class="seg cl"><span class="q">Did they start care?</span><button type="button" class="opt pos" data-f="close" data-v="closed">Became a patient</button>'+
'<button type="button" class="opt neg" data-f="close" data-v="not_closed">Not yet</button></div>'+
'<textarea placeholder="Notes (optional): what happened, what they need, why they didn\'t start care..." aria-label="Notes for '+esc(a.name)+'">'+esc(a.notes)+'</textarea>'+
'<div class="row"><button type="button" class="btn">Save</button><span class="ok" hidden>Saved</span><span class="bad" hidden></span></div></div>';
var cl=el.querySelector('.cl');
function paint(){el.querySelectorAll('.opt').forEach(function(b){b.classList.toggle('on',st[b.dataset.f]===b.dataset.v)});cl.hidden=st.show!=='show'}
el.querySelectorAll('.opt').forEach(function(b){b.onclick=function(){st[b.dataset.f]=b.dataset.v;if(b.dataset.f==='show'&&b.dataset.v!=='show')st.close=null;paint()}});
var save=el.querySelector('.btn'),ok=el.querySelector('.ok'),bad=el.querySelector('.bad');
save.onclick=function(){bad.hidden=true;ok.hidden=true;
if(!st.show){bad.textContent='Pick "Showed up" or "No-show" first.';bad.hidden=false;return}
save.disabled=true;
fetch(base+'/'+a.id,{method:'PATCH',headers:{'Content-Type':'application/json'},
body:JSON.stringify({outcome_show:st.show,outcome_close:st.show==='show'?st.close:null,outcome_notes:el.querySelector('textarea').value})})
.then(function(r){if(!r.ok)throw 0;live();var done=st.show==='no_show'||(st.show==='show'&&st.close);
if(done){ok.textContent='Saved';ok.hidden=false;setTimeout(function(){el.remove();left()},900)}
else{save.disabled=false;ok.textContent='Saved. Come back and mark whether they became a patient.';ok.hidden=false}})
.catch(function(){save.disabled=false;bad.textContent="That didn't save. Please try again.";bad.hidden=false})};
paint();return el}
// Live numbers (GET /report/<slug>/live): "New patients" and the journey's
// show-up / became-a-patient rows, refreshed on load and after every save.
function live(){fetch(location.pathname.replace(/\/$/,'')+'/live').then(function(r){if(!r.ok)throw 0;return r.json()}).then(function(d){
function n(v){return v==null?'–':Number(v).toLocaleString()}
document.querySelectorAll('[data-live="patients"]').forEach(function(e){e.textContent=n(d.patients)});
document.querySelectorAll('[data-live="shows"]').forEach(function(e){e.textContent=n(d.shows)});
(d.steps||[]).forEach(function(s){var row=document.querySelector('.jrow[data-step="'+s.path+':'+s.key+'"]');if(!row)return;
row.querySelector('.ct').textContent=n(s.value);
var top=+row.dataset.top||0,trk=row.querySelector('.trk');
trk.innerHTML=(s.value>0&&top)?'<i style="width:'+Math.max(6,Math.min(100,Math.log10(s.value+1)/Math.log10(top+1)*100)).toFixed(0)+'%"></i>':'';
var tone={good:1,ok:1,poor:1}[s.status]?s.status:null,rt=row.querySelector('.rt');
if(rt)rt.innerHTML=s.rate==null?'':'<b class="'+(tone?'tone-'+tone:'')+'">'+(tone?'<i class=tdot></i>':'')+s.rate+'%</b><span>of previous step</span>';
var nt=row.querySelector('.nt');if(s.note){if(!nt){nt=document.createElement('div');nt.className='nt';row.appendChild(nt)}nt.textContent=s.note}else if(nt)nt.remove()})
}).catch(function(){})}
live();
fetch(base).then(function(r){if(!r.ok)throw 0;return r.json()})
.then(function(d){(d.appointments||[]).forEach(function(a){box.appendChild(row(a))});left()})
.catch(function(){msg.textContent="Couldn't load your appointments here. You can mark them in your portal under Appointments."})
})();
'''


def _step_width(value, top) -> float:
    """Log-scale bar width, like the portal: impressions are often 1000x bookings."""
    if not value or not top:
        return 0
    return max(6, min(100, math.log10(value + 1) / math.log10(top + 1) * 100))


def _journey(scope: dict) -> str:
    paths = scope.get("paths") or []
    if not paths and scope.get("stages"):   # reports built before paths were stored
        paths = [{"label": "", "stages": [dict(s, key="", available=True) for s in scope["stages"]]}]
    out = []
    for p in paths:
        stages = p.get("stages") or []
        top = max([s.get("value") or 0 for s in stages if s.get("available", True)] or [0])
        if len(paths) > 1:
            out.append(f'<div class="path-h">{_e(p.get("label"))}</div>')
        for i, s in enumerate(stages):
            off = s.get("available") is False
            tone = s.get("status") if s.get("status") in TONE else None
            rate = '<div class="rt"></div>'
            if i and not off and s.get("rate") is not None:
                basis = "click rate" if s.get("rate_basis") == "click-through rate" else "of previous step"
                tgt = f' title="Target: {_e(s["target"])}% or better"' if s.get("target") else ""
                rate = (f'<div class="rt"{tgt}><b class="{"tone-" + tone if tone else ""}">'
                        f'{"<i class=tdot></i>" if tone else ""}{_pct(s["rate"])}</b><span>{basis}</span></div>')
            note = f'<div class="nt">{_e(s["note"])}</div>' if s.get("note") and not off else ""
            bar = (f'<i style="width:{_step_width(s.get("value"), top):.0f}%"></i>'
                   if not off and (s.get("value") or 0) > 0 else "")
            # Show-up / new-patient rows refresh live (LIVE_JS) as the clinic marks outcomes.
            live = (f' data-step="{_e(p.get("key"))}:{_e(s.get("key"))}" data-top="{top}"'
                    if s.get("key") in CLIENT_REPORTED and p.get("key") else "")
            out.append(
                f'<div class="jrow{" first" if i == 0 and len(paths) == 1 else ""}{" off" if off else ""}"{live}>'
                f'<div class="nm"><span class="no">{i + 1}</span><div><div class="t">{_e(s.get("label"))}'
                f'{REP_TAG if s.get("key") in CLIENT_REPORTED else ""}</div>'
                f'<div class="hp">{"Waiting on ad account access" if off else _e(STEP_HELP.get(s.get("key"), ""))}</div></div></div>'
                f'<div class="bw"><div class="trk">{bar}</div><div class="ct">{"–" if off else _num(s.get("value"))}</div></div>'
                f'{rate}'
                f'{note}'
                f'</div>')
    return "".join(out)


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
    bud = camp.get("budget")

    title = "Final campaign report" if final else f"Week {report['week_number']} report"
    dates = f"{_date(report['period_start'])} – {_date(report['period_end'])}"
    issued = _date(datetime.now(ET).isoformat())
    period_word = "whole campaign" if final else "this week"

    # Numbered section heads, like the blueprint ("01 ── Results")
    def idx(label: str, icon: str) -> str:
        return (f'<div class="idx"><span class="n">{{NUM}}</span><span class="ln"></span>'
                f'{_icon(icon)}{_e(label)}</div>')

    def head(label: str, icon: str, h2: str = "", sub: str = "") -> str:
        return (f'<div class="head reveal">{idx(label, icon)}'
                + (f'<h2>{h2}</h2>' if h2 else "") + (f'<p>{_e(sub)}</p>' if sub else "") + '</div>')

    blocks: dict[str, str] = {}

    def add(block: tuple) -> None:
        inner, sid = block
        blocks[sid] = inner

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


    # ---- Results: goal bar + the portal's four headline numbers
    goal_html = ""
    if pace:
        pct = min(100, pace["pct_of_goal"])
        side = (f'<b>{_money(bud["spent"])} of {_money(bud["cap"])}</b>ad budget spent' if bud
                else f'<b>Day {_e(camp.get("days_elapsed"))} of {_e(camp.get("length_days"))}</b>of the campaign')
        goal_html = (f'<div class="card goal reveal"><div><div class="mono">Campaign goal</div>'
                     f'<div class="big">{pace["booked"]}<small> of {pace["goal"]} {_e(camp.get("goal_label") or "booked")}</small></div></div>'
                     f'<div class="side">{side}</div><div class="prog"><i style="width:{pct}%"></i></div></div>')

    def kpi(label, value, hint, cur=None, prev=None, lower=False, reported=False, live=""):
        chg = "" if final or cur is None else _delta(cur, prev, lower)
        tag = REP_TAG.replace('class="rep"', 'class="rep kr"') if reported else ""
        lv = f' data-live="{live}"' if live else ""
        return (f'<div class="card kpi"><div class="lbl">{label}{"*" if reported else ""}</div><div class="v"{lv}>{value}</div>'
                f'<div class="h">{hint}</div>{chg}{tag}</div>')

    spend_hint = (f"of the {_money(bud['cap'])} budget" if final and bud else period_word)
    kpis = (
        kpi("New patients", _num(k.get("patients")), f'<span data-live="shows">{_num(k.get("shows"))}</span> came to their visit',
              k.get("patients"), lk.get("patients"), reported=True, live="patients")
        + kpi("Visits booked", _num(k.get("booked")), f'from {_num(k.get("leads"))} leads', k.get("booked"), lk.get("booked"))
        + kpi("Cost per booking", _money(k.get("cost_per_booking")), "ad spend ÷ visits booked",
              k.get("cost_per_booking"), lk.get("cost_per_booking"), True)
        + kpi("Ad spend", _money(k.get("spend")), spend_hint))
    add((
        head("Results", "chart", "Your results, " + ("start to finish" if final else "this week"),
             "The same numbers you see on the Results tab in your portal." + ("" if final else " Each one is compared with last week."))
        + f'<div class="stack">{goal_html}<div class="kpis reveal">{kpis}</div>{REPORTED_NOTE}</div>', "results"))

    # ---- The quick read: one card, a row per list (past tense on the final report)
    def qrow(cls, icon, label, items):
        if not items:
            return ""
        return (f'<div class="qr"><span class="ib {cls}">{_icon(icon)}</span><div><h4>{label}</h4>'
                f'<ul class="ticks">{_items(items)}</ul></div></div>')

    quick = (qrow("grn", "check", "What worked" if final else "What's working", a.get("on_target"))
             + qrow("amb", "alert", "What held it back" if final else "What we're fixing", a.get("off_target"))
             + qrow("", "arrow", "What we recommend next" if final else "Next week", a.get("next_steps"))
             + qrow("", "star", "How your team can help", a.get("client_asks")))
    add((head("The quick read", "layers", "The campaign in 30 seconds" if final else "This week in 30 seconds")
         + f'<div class="card quick reveal">{quick or "<p class=muted>Nothing to flag this time.</p>"}</div>', "read"))

    # ---- Patient journey + costs + ad performance + AI assistant (portal layout)
    leak = scope.get("biggest_leak")
    leak_html = (f'<div class="leak"><b>Biggest opportunity:</b> {_e((leak.get("label") or "").lower())} is at '
                 f'{_pct(leak.get("rate"))} (target {_pct(leak.get("target"))}).</div>' if leak else "")
    legend = "".join(f'<span class="tone-{t}"><i class="tdot"></i><span style="color:var(--muted)">{lab}</span></span>'
                     for t, lab in TONE.items()) + "<span>No dot = not enough data yet</span>"
    journey = (f'<div class="card journey reveal"><h3>Patient journey</h3>'
               f'<div class="sub">How many people reached each step, and what share moved on to the next.</div>'
               f'{leak_html}<div style="margin-top:8px">{_journey(scope)}</div><div class="legend">{legend}</div>'
               f'<div style="margin-top:10px">{REPORTED_NOTE}</div></div>')

    def mini(title_, cells, extra=""):
        return (f'<div class="card mini reveal"><h3>{title_}</h3><div class="g">' + "".join(
            f'<div><div class="lbl">{l}</div><div class="num">{v}</div>{f"<div class=h>{h}</div>" if h else ""}</div>'
            for l, v, h in cells) + f'</div>{extra}</div>')

    costs = mini("What each result costs", [
        ("Per lead", _money(k.get("cost_per_lead")), None), ("Per booked visit", _money(k.get("cost_per_booking")), None),
        ("Per visit attended*", _money(k.get("cost_per_show")), None), ("Per new patient*", _money(k.get("cost_per_patient")), None)])
    last_cell = (("Prepaid visits collected", _money(k.get("prepaid_revenue")), f'{_num(k.get("prepaid_count"))} paid bookings')
                 if k.get("prepaid_revenue") is not None else ("Leads", _num(k.get("leads")), None))
    adperf = mini("Ad performance", [
        ("Times shown", _num(k.get("impressions")), f'{_money(k.get("cpm"))} per 1,000' if k.get("cpm") is not None else None),
        ("Click rate", _pct(k.get("ctr")), f'{_num(k.get("link_clicks"))} clicks' if k.get("link_clicks") is not None else None),
        ("Cost per click", _money(k.get("cpc")), None), last_cell])
    add((
        head("Patient journey", "users", "From ad to new patient",
             "Every step a patient takes, " + ("across the whole campaign." if final else "this week."))
        + f'<div class="stack">{journey}<div class="trio">{costs}{adperf}</div></div>', "journey"))

    # ---- Texts and calls (Dylan, 2026-11-19): what the AI text assistant, the team
    # and the AI voice agents did in the period, from client_success._comms_stats.
    comms = data.get("comms_to_date") if final else data.get("comms_week")
    ai = data.get("ai_agent_to_date") if final else data.get("ai_agent_week")
    if comms:
        tx, cl = comms["texts"], comms["calls"]
        def brk(items):
            items = [(l, v) for l, v in items if v]
            return ('<div class="brk">' + "".join(f'<span><b>{_num(v)}</b> {l}</span>' for l, v in items) + '</div>') if items else ""
        texts_card = mini("Text messages", [
            ("Texts sent", _num(tx["sent"]), f'to {_num(tx["people_texted"])} people'),
            ("Replies received", _num(tx["received"]),
             f'{_num(tx["people_replied"])} people replied' + (f' ({tx["reply_rate"]}%)' if tx.get("reply_rate") is not None else "")),
            ("Booked by text", _num((ai or {}).get("booked")),
             f'{_num((ai or {}).get("ai_booked"))} booked by the AI in the chat' if ai and ai.get("ai_booked") is not None else None),
            ("Offered a time", _num((ai or {}).get("offered_times")), "leads the AI offered times to" if ai else None),
        ], brk([("by the AI assistant", tx["by_ai"]), ("by your team", tx["by_team"]), ("follow-ups", tx["followups"]),
                ("reactivation", tx["reactivation"]), ("appointment texts", tx["appointment"])]))
        t = cl["total"]
        if t["placed"]:
            split = [f"{lab}: {_num(r['placed'])} calls, {_num(r['reached'])} reached, {_num(r['booked'])} booked"
                     for lab, r in (("New ad leads", cl.get("ad_leads")), ("Reactivation", cl.get("reactivation")))
                     if r and r.get("placed")]
            calls_card = mini("AI phone calls", [
                ("Calls placed", _num(t["placed"]), f'to {_num(t["people"])} people'),
                ("People reached", _num(t["reached"]), f'{t["reach_rate"]}% picked up' if t.get("reach_rate") is not None else None),
                ("Voicemails left", _num(t["voicemails"]), f'{_num(t["no_answer"])} no answer'),
                ("Booked on a call", _num(t["booked"]), f'{_num(t["talk_minutes"])} min of talk time'),
            ], ('<div class="brk">' + "".join(f"<span>{_e(x)}</span>" for x in split) + "</div>") if split else "")
        else:
            calls_card = ('<div class="card mini reveal"><h3>AI phone calls</h3>'
                          '<p class="muted" style="margin:0">No AI calls ' + ("during the campaign." if final else "this week.") + '</p></div>')
        add((head("Texts and calls", "chat", "Every text and call to your leads",
                  "What your AI assistant, your team and the AI voice agent did " + ("during the campaign." if final else "this week."))
             + f'<div class="two">{texts_card}{calls_card}</div>', "comms"))

    # ---- Appointments waiting on an outcome (loaded live, saved from the page)
    add((
        head("Needs your update", "check", "Appointments waiting on an outcome",
             "Your show rate and close rate only count visits your team has marked. Mark each one below and "
             "it's saved straight to your portal.")
        + '<div class="card appts reveal" id="appts"><div class="ap-empty" id="apMsg">Loading your appointments...</div>'
          '<div id="apList"></div></div>', "outcomes"))

    # ---- Final: week by week
    if final and data.get("weeks"):
        add((head("Week by week", "chart", "Visits booked, week by week")
                                + f'<div class="card reveal">{_bars(data["weeks"])}</div>', "weeks"))

    # ---- Patient quality + answered questions
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
        f'<div class="card qa reveal"><div class="q">You asked: {_e(f["message"])}</div><div>{_e(f["answer"])}</div></div>'
        for f in answered)
    if lq_html and qa_html:
        add((head("Patients + your questions", "users", "Patient quality, and your answers")
                                + f'<div class="two">{lq_html}<div>{qa_html}</div></div>', "quality"))
    elif lq_html:
        add((head("Patient quality", "users", "Patient quality (your ratings)") + lq_html, "quality"))
    elif qa_html:
        add((head("You asked", "chat", "You asked, we answered") + qa_html, "answers"))

    # ---- Final: next campaign, with its own yes button
    if final:
        nc = a.get("next_campaign") or {}
        if nc.get("plan") or nc.get("intro"):
            add((
                f'<div class="guar reveal">{idx("Your next campaign", "rocket")}'
                f'<h2>Here\'s how we\'d <span class="grad">build on these results</span>.</h2>'
                f'<p class="lead">{_e(nc.get("intro"))}</p><ul class="ticks">{_items(nc.get("plan"))}</ul>'
                f'<div class="cta"><p>{_e(nc.get("ask") or "Want to keep going?")}</p>'
                f'<button class="btn" type="button" id="nextBtn">Yes, let\'s talk about it</button>'
                f'<span class="thanks" id="nextOk">Great. Dylan will reach out to set up a time.</span>'
                f'<span class="err" id="nextErr">That didn\'t go through. Please try again.</span></div></div>', "next"))

    # ---- Final: share your experience (a real testimonial form)
    if final:
        review = os.environ.get("DIGIGROWTH_REVIEW_URL", "").strip()
        intro = (report.get("testimonial_text") or "").replace("{clinic}", clinic).replace(
            "{first_name}", data["client"].get("first_name") or "")
        # Older saved wording pointed at a checkbox; the box is now right here.
        intro = intro.replace("Tick the testimonial box below and write whatever comes to mind (what it was like before, what changed).",
                              "Write whatever comes to mind in the box below: what it was like before, and what changed.")
        intro = _e(intro.replace("{review_link_line}", "").strip())
        review_html = (f'<p class="review">A quick Google review helps too: '
                       f'<a href="{_e(review)}" target="_blank" rel="noopener">leave a Google review</a>.</p>' if review else "")
        star = ('<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 2.8 2.9 5.9 6.5.9-4.7 4.6 1.1 6.4L12 17.6l-5.8 3'
                '.1 1.1-6.4-4.7-4.6 6.5-.9z"/></svg>')
        nps = "".join(f'<button type="button" class="rate star" data-group="nps" data-v="{i}" '
                      f'aria-label="{i} star{"s" if i > 1 else ""}">{star}</button>' for i in range(1, 6))
        add((f"""<div class="guar reveal" id="testimonial">
  {idx("Share your experience", "heart")}
  <h2>Tell us how it went.</h2>
  <p class="lead">{intro}</p>
  <form id="tForm">
    <div><div class="fl">How was your experience?</div></div>
    <div class="stars">{nps}<span class="stars-l" id="starL">Tap a star</span></div>
    <label class="fl" for="tMsg">Your testimonial<small>What was it like before, and what changed for {_e(clinic)}?</small></label>
    <textarea id="tMsg" placeholder="Before working with DigiGrowth, we..."></textarea>
    <label class="chk"><input type="checkbox" id="tOk" checked> You can share this on your website and social media with my first name and clinic name.</label>
    <button class="btn" type="submit">Send my testimonial</button>
    <div class="thanks" id="tThanks">Thank you, that means a lot. Dylan will see it right away.</div>
    <div class="err" id="tErr">That didn't go through. Please try again.</div>
  </form>
  {review_html}
</div>""", "share"))

    # ---- Questions or ideas (questions only; the weekly check-in rating lives here too)
    qs = "".join(f"<li>{_e(q)}</li>" for q in (a.get("questions_for_client") or []))
    checkin = ""
    if not final:
        pulse = "".join(f'<button type="button" class="rate" data-group="pulse" data-v="{i}" aria-label="{i} out of 5">{i}</button>'
                        for i in range(1, 6))
        checkin = (f'<div class="fl">Quick check-in: how are you feeling about the campaign this week?</div>'
                   f'<div class="rates">{pulse}</div><div class="scale" style="max-width:240px"><span>1 = worried</span><span>5 = great</span></div>')
    add((f"""<div class="guar reveal" id="feedback">
  {idx("Questions or ideas", "chat")}
  <h2>Have a question? <span class="grad">Ask Dylan here.</span></h2>
  <p class="lead">You know your patients best. Anything you send here goes straight to Dylan, and you'll get an answer before the next report.</p>
  {f'<div class="card qs"><b>I would love your take on:</b><ul class="ticks">{qs}</ul></div>' if qs else ''}
  <form id="qForm">
    {checkin}
    <label class="fl" for="kind">What is it about?</label>
    <select id="kind"><option value="question">I have a question</option><option value="suggestion">I have a suggestion</option><option value="feedback">Something else</option></select>
    <textarea id="msg" aria-label="Your message" placeholder="Type your question or idea..."></textarea>
    <button class="btn" type="submit">Send to Dylan</button>
    <div class="thanks" id="qThanks">Got it, thank you. Dylan will get back to you.</div>
    <div class="err" id="qErr">That didn't go through. Please try again.</div>
  </form>
</div>""", "questions"))

    # Order (Dylan, 2026-11-17): results, then what the clinic needs to do, then the read and the detail;
    # the forms near the end and the next-campaign pitch last.
    order = ["results", "outcomes", "read", "journey", "comms", "weeks", "quality", "answers", "share", "questions", "next"]
    parts = []
    for i, sid in enumerate([o for o in order if o in blocks]):
        inner = blocks[sid].replace("{NUM}", "%02d" % (i + 1))
        parts.append(f'<section id="{sid}"{" class=alt" if i % 2 == 0 else ""}><div class="wrap">{inner}</div></section>')
    assembled = "".join(parts)

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

{assembled}

<footer><div class="wrap"><span>Prepared for {_e(clinic)} by DigiGrowth</span><span>digigrowthllc.com</span></div></footer>

<script>
(function(){{
var els=document.querySelectorAll('.reveal');
if('IntersectionObserver' in window){{var io=new IntersectionObserver(function(es){{es.forEach(function(e){{if(e.isIntersecting){{e.target.classList.add('in');io.unobserve(e.target)}}}})}},{{threshold:0.06}});els.forEach(function(el){{io.observe(el)}})}}
else{{els.forEach(function(el){{el.classList.add('in')}})}}
var picked={{}};
document.querySelectorAll('.rate').forEach(function(b){{b.onclick=function(){{var g=b.dataset.group;
document.querySelectorAll('.rate[data-group="'+g+'"]').forEach(function(x){{x.classList.toggle('on',g==='nps'?+x.dataset.v<=+b.dataset.v:x===b)}});picked[g]=+b.dataset.v;
if(g==='nps'){{var sl=document.getElementById('starL');if(sl)sl.textContent=['','Poor','Fair','Good','Great','Excellent'][picked[g]]}}}}}});
var url=location.pathname.replace(/\\/$/,'')+'/feedback';
function send(body,btn,ok,err,done){{btn.disabled=true;document.getElementById(err).style.display='none';
fetch(url,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(body)}})
.then(function(x){{if(!x.ok)throw 0;document.getElementById(ok).style.display='block';if(done)done()}})
.catch(function(){{btn.disabled=false;document.getElementById(err).style.display='block'}})}}
var nb=document.getElementById('nextBtn');
if(nb)nb.onclick=function(){{send({{kind:'feedback',message:'',wants_next:true}},nb,'nextOk','nextErr',function(){{nb.style.display='none'}})}};
var tf=document.getElementById('tForm');
if(tf)tf.onsubmit=function(e){{e.preventDefault();var m=document.getElementById('tMsg').value.trim();
if(!m&&picked.nps===undefined)return;
send({{kind:'testimonial',message:m,rating:picked.nps===undefined?null:picked.nps,testimonial_ok:document.getElementById('tOk').checked}},
tf.querySelector('.btn'),'tThanks','tErr',function(){{document.getElementById('tMsg').value=''}})}};
var qf=document.getElementById('qForm');
if(qf)qf.onsubmit=function(e){{e.preventDefault();var m=document.getElementById('msg').value.trim();
if(!m&&picked.pulse===undefined)return;var btn=qf.querySelector('.btn');
send({{kind:document.getElementById('kind').value,message:m,rating:picked.pulse===undefined?null:picked.pulse}},btn,'qThanks','qErr',
function(){{document.getElementById('msg').value='';btn.disabled=false}})}};
}})();
{APPTS_JS}
</script></body></html>"""
