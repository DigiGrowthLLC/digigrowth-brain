"""HTML for Dylan's booking page (personal_booking.py). One self-contained page,
two modes: "book" (pick a call type, time, details) and "manage" (the
booking's own page: join link, reschedule, cancel). Every API call is
relative to the page's own path, so it works at
booking.digigrowthllc.com/discovery-call and at /book/discovery-call alike."""

_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<meta name="robots" content="noindex">
<style>
  :root{ --accent:#2f6fd6; --accent-soft:color-mix(in srgb, var(--accent) 12%, #fff); --ink:#151b28; --soft:#5a6377;
         --line:#e3e7ee; --bg:#f4f6f9; --card:#fff; --ok:#11845b; --warn:#a15c07; --warn-bg:#fff4e2; --bad:#c2410c; --star:#e0a100; }
  *{ box-sizing:border-box; }
  html,body{ margin:0; }
  body{ background:var(--bg); color:var(--ink); font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; -webkit-font-smoothing:antialiased; }
  button{ font:inherit; }
  .wrap{ max-width:1040px; margin:0 auto; padding:28px 16px 56px; }
  .shell{ background:var(--card); border:1px solid var(--line); border-radius:18px; box-shadow:0 8px 30px rgba(16,24,40,.06); display:grid; grid-template-columns:360px 1fr; overflow:hidden; }
  .info{ padding:26px 26px 24px; border-right:1px solid var(--line); display:flex; flex-direction:column; gap:14px; }
  .main{ padding:22px 26px 26px; min-width:0; }
  @media (max-width:860px){ .shell{ grid-template-columns:1fr; } .info{ border-right:0; border-bottom:1px solid var(--line); padding:20px; gap:12px; } .main{ padding:18px 16px 22px; } }
  .who{ display:flex; align-items:center; gap:12px; }
  .logo{ max-height:38px; max-width:180px; object-fit:contain; align-self:flex-start; }
  .avatar{ width:56px; height:56px; border-radius:50%; object-fit:cover; background:var(--accent-soft); flex:0 0 auto; border:2px solid #fff; box-shadow:0 0 0 1px var(--line); }
  .clinic{ font-weight:700; font-size:14.5px; }
  .provider{ color:var(--soft); font-size:13px; }
  .headline{ font-size:13.5px; font-weight:700; color:var(--accent); }
  h1{ font-size:24px; line-height:1.2; margin:0; letter-spacing:-.01em; }
  .meta{ display:flex; flex-direction:column; gap:7px; color:var(--soft); font-size:14px; }
  .meta div{ display:flex; gap:9px; align-items:flex-start; }
  .meta svg{ flex:0 0 18px; margin-top:2px; color:var(--soft); }
  .price{ color:var(--ink); font-weight:700; }
  .price .was{ color:var(--soft); font-weight:400; margin-left:4px; }
  .price .was s{ text-decoration-thickness:1.5px; }
  .spots{ align-self:flex-start; font-size:12.5px; font-weight:700; color:var(--warn); background:var(--warn-bg); border-radius:999px; padding:3px 10px; }
  .proof{ border:1px solid var(--line); border-radius:12px; padding:12px 14px; display:flex; flex-direction:column; gap:6px; background:#fbfcfe; }
  .stars{ display:flex; align-items:center; gap:6px; font-size:13.5px; }
  .stars .s{ color:var(--star); letter-spacing:1px; font-size:15px; }
  .quote{ font-size:13.5px; color:var(--ink); }
  .quote small{ color:var(--soft); }
  .checks{ list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:6px; font-size:13.5px; }
  .checks li{ display:flex; gap:8px; }
  .checks li::before{ content:"\2713"; color:var(--ok); font-weight:700; }
  .desc{ color:var(--soft); font-size:13.5px; margin:0; white-space:pre-wrap; }
  .progress{ display:flex; gap:6px; margin-bottom:16px; }
  .progress div{ flex:1; }
  .progress i{ display:block; height:4px; border-radius:4px; background:var(--line); }
  .progress .done i{ background:var(--accent); }
  .progress span{ display:block; font-size:11.5px; color:var(--soft); margin-top:5px; font-weight:600; }
  .progress .done span{ color:var(--accent); }
  h2{ font-size:17px; margin:0 0 12px; }
  .next{ width:100%; display:flex; justify-content:space-between; align-items:center; gap:10px; border:0; border-radius:12px; background:var(--accent); color:#fff; padding:13px 16px; cursor:pointer; text-align:left; }
  .next b{ font-size:15px; } .next small{ display:block; opacity:.85; font-size:12px; font-weight:600; letter-spacing:.02em; text-transform:uppercase; }
  .calhead{ display:flex; align-items:center; justify-content:space-between; margin:18px 0 8px; }
  .calhead b{ font-size:15px; }
  .navbtn{ width:34px; height:34px; border-radius:50%; border:1px solid var(--line); background:#fff; cursor:pointer; color:var(--ink); font-size:16px; }
  .navbtn[disabled]{ opacity:.35; cursor:default; }
  .cal{ display:grid; grid-template-columns:repeat(7,1fr); gap:4px; text-align:center; }
  .dow{ font-size:11px; font-weight:700; color:var(--soft); text-transform:uppercase; padding:4px 0; }
  .day{ aspect-ratio:1; max-height:48px; border:0; border-radius:50%; background:transparent; color:#b8bfcc; font-weight:600; cursor:default; font-variant-numeric:tabular-nums; }
  .day.open{ background:var(--accent-soft); color:var(--accent); cursor:pointer; }
  .day.open:hover{ filter:brightness(.96); }
  .day.sel{ background:var(--accent); color:#fff; }
  .day.today{ box-shadow:inset 0 0 0 1.5px var(--line); }
  .times{ margin-top:16px; border-top:1px solid var(--line); padding-top:14px; }
  .times-h{ display:flex; justify-content:space-between; align-items:baseline; gap:10px; flex-wrap:wrap; margin-bottom:10px; }
  .times-h b{ font-size:14.5px; }
  .left{ font-size:12.5px; font-weight:700; color:var(--warn); }
  .grid{ display:grid; grid-template-columns:repeat(auto-fill,minmax(110px,1fr)); gap:8px; }
  .t{ border:1.5px solid var(--accent); color:var(--accent); background:#fff; border-radius:10px; padding:11px 6px; font-weight:700; cursor:pointer; font-variant-numeric:tabular-nums; }
  .t:hover{ background:var(--accent-soft); }
  .more{ margin-top:10px; background:none; border:0; color:var(--accent); font-weight:600; cursor:pointer; padding:4px 0; }
  .tz{ font-size:12px; color:var(--soft); margin-top:12px; }
/*__TZ_PICKER_CSS__*/
  .chosen{ display:flex; justify-content:space-between; align-items:center; gap:10px; background:var(--accent-soft); border-radius:12px; padding:12px 14px; margin-bottom:6px; }
  .chosen b{ display:block; } .chosen small{ color:var(--soft); }
  .link{ background:none; border:0; color:var(--accent); font-weight:600; cursor:pointer; padding:0; text-decoration:underline; }
  label{ display:block; font-size:13px; font-weight:700; margin:14px 0 6px; }
  label small{ font-weight:400; color:var(--soft); }
  input,textarea{ width:100%; font:inherit; font-size:16px; padding:12px 13px; border:1px solid #cdd4e0; border-radius:10px; background:#fff; color:var(--ink); }
  input:focus,textarea:focus,button:focus-visible{ outline:2px solid var(--accent); outline-offset:1px; }
  .cta{ display:flex; align-items:center; justify-content:center; gap:8px; width:100%; margin-top:18px; border:0; border-radius:12px; padding:15px; font-weight:800; font-size:16px; background:var(--accent); color:#fff; cursor:pointer; text-decoration:none; }
  .cta[disabled]{ opacity:.6; cursor:default; }
  .cta.ghost{ background:#fff; color:var(--ink); border:1px solid var(--line); font-weight:700; }
  .cta.danger{ background:#fff; color:var(--bad); border:1px solid #f3c7b2; font-weight:700; }
  .assure{ list-style:none; margin:12px 0 0; padding:0; display:flex; flex-direction:column; gap:5px; font-size:13px; color:var(--soft); }
  .assure li{ display:flex; gap:7px; } .assure li::before{ content:"\2713"; color:var(--ok); font-weight:800; }
  .fine{ font-size:11.5px; color:#8a93a5; margin-top:12px; }
  .consent{ display:flex; gap:10px; align-items:flex-start; margin:12px 0 0; font-size:12.5px; line-height:1.45; color:var(--soft); font-weight:400; cursor:pointer; }
  .consent input{ width:18px; height:18px; flex:0 0 18px; margin:1px 0 0; padding:0; accent-color:var(--accent); }
  .consent a{ color:inherit; }
  .err{ color:var(--bad); font-size:14px; margin-top:10px; }
  .note{ background:var(--warn-bg); color:var(--warn); border-radius:10px; padding:10px 12px; font-size:13.5px; margin-bottom:12px; }
  .muted{ color:var(--soft); font-size:14px; }
  .row{ display:flex; gap:10px; } .row > *{ flex:1; }
  .ok{ text-align:center; padding:6px 0; }
  .tick{ width:58px; height:58px; border-radius:50%; background:#e5f5ee; color:var(--ok); display:flex; align-items:center; justify-content:center; font-size:30px; margin:0 auto 10px; }
  .hidden{ display:none !important; }
  .skeleton{ height:220px; border-radius:12px; background:linear-gradient(90deg,#f0f2f6,#f7f8fb,#f0f2f6); background-size:200% 100%; animation:sh 1.2s infinite; }
  @keyframes sh{ to{ background-position:-200% 0; } }
  @media (prefers-reduced-motion: reduce){ .skeleton{ animation:none; } }
  footer{ text-align:center; color:#9aa3b5; font-size:12px; margin-top:20px; }
  .mark{ display:flex; align-items:center; justify-content:center; color:var(--accent); font-weight:800; font-size:18px; }
  .types button{ display:flex; justify-content:space-between; align-items:center; width:100%; margin-bottom:10px; padding:15px 16px; border-radius:12px; text-align:left;
                 border:1.5px solid var(--line); background:#fff; color:var(--ink); font-weight:700; cursor:pointer; }
  .types button:hover{ border-color:var(--accent); background:var(--accent-soft); }
  .results-btn{ display:flex; align-items:center; justify-content:space-between; gap:10px; width:100%; text-align:left; cursor:pointer; color:var(--ink); }
  .results-btn:hover{ border-color:var(--accent); }
  .results-btn b{ font-size:14px; } .results-btn .go{ color:var(--accent); font-weight:700; font-size:13.5px; white-space:nowrap; }
  .modal{ position:fixed; inset:0; z-index:50; background:rgba(15,20,32,.72); display:flex; justify-content:center; align-items:flex-start; overflow-y:auto; padding:28px 16px; }
  .sheet{ background:#fff; border-radius:18px; max-width:980px; width:100%; padding:22px; position:relative; }
  .sheet h2{ font-size:20px; margin:0 34px 4px 0; } .sheet .sub{ color:var(--soft); font-size:14px; margin:0 0 16px; }
  .close{ position:absolute; top:14px; right:14px; width:36px; height:36px; border-radius:50%; border:1px solid var(--line); background:#fff; font-size:20px; cursor:pointer; color:var(--ink); }
  .shot{ margin:0 0 22px; } .shot:last-child{ margin-bottom:0; }
  .shot img{ width:100%; display:block; border-radius:12px; border:1px solid var(--line); }
  .h-stars{ color:var(--star); letter-spacing:2px; font-size:.8em; vertical-align:2px; margin-left:6px; white-space:nowrap; }
  .disclaimer{ margin:-4px 0 10px; font-size:12.5px; color:var(--soft); font-style:italic; }
  .shot figcaption{ margin-top:8px; font-size:13.5px; color:var(--soft); }
  .shot figcaption b{ color:var(--ink); }
  .badge{ display:inline-block; font-size:11.5px; font-weight:800; letter-spacing:.03em; border-radius:999px; padding:2px 9px; margin-right:6px; vertical-align:1px; }
  .badge.real{ background:#e5f5ee; color:var(--ok); } .badge.sample{ background:var(--warn-bg); color:var(--warn); }
  footer a{ color:inherit; }
</style>
</head>
<body>
<div class="wrap"><div class="shell">
  <aside class="info" id="info"></aside>
  <section class="main" id="main"><div class="skeleton"></div></section>
</div><footer>DigiGrowth · <a href="https://digigrowthllc.com">digigrowthllc.com</a></footer></div>
<script>
const MODE = __MODE__;
const BASE = location.pathname.replace(/\/+$/, "");
const qs = new URLSearchParams(location.search);
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
// ?tz=<IANA zone> shows times in the prospect's zone when Dylan books for them from the OS
// (BookingModal.jsx); otherwise the visitor's own browser zone. The Change link under the calendar switches it.
let TZ = (() => {
  const want = qs.get("tz");
  if (want) { try { new Intl.DateTimeFormat("en-US", { timeZone: want }); return want; } catch {} }
  return Intl.DateTimeFormat().resolvedOptions().timeZone || "America/New_York";
})();
const fmt = (iso, o) => new Intl.DateTimeFormat("en-US", { timeZone: TZ, ...o }).format(new Date(iso));
const fmtDay = (iso) => fmt(iso, { weekday: "long", month: "long", day: "numeric" });
const fmtTime = (iso) => fmt(iso, { hour: "numeric", minute: "2-digit" });
const localDate = (iso) => new Intl.DateTimeFormat("en-CA", { timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(iso));
const today = () => localDate(new Date().toISOString());
const tzLabel = () => { try { return new Intl.DateTimeFormat("en-US", { timeZone: TZ, timeZoneName: "long" }).formatToParts(new Date()).find(p => p.type === "timeZoneName").value; } catch { return TZ; } };
/*__TZ_PICKER__*/
const digits = (s) => String(s || "").replace(/\D/g, "");
const addMonth = (ym, n) => { const [y, m] = ym.split("-").map(Number); return new Date(Date.UTC(y, m - 1 + n, 1)).toISOString().slice(0, 7); };
const ICON = {
  clock: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
  video: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="6" width="13" height="12" rx="2"/><path d="M16 10l5-3v10l-5-3"/></svg>',
  cal: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>',
};

async function api(path, opts) {
  const r = await fetch(BASE + "/api/" + path, { headers: { "Content-Type": "application/json" }, ...opts });
  let body = null; try { body = await r.json(); } catch {}
  if (!r.ok) throw new Error((body && body.detail) || "Something went wrong. Please try again.");
  return body;
}
const post = (path, body) => api(path, { method: "POST", body: JSON.stringify(body) });

function infoPanel(ev, extra) {
  return `<div class="who"><div class="avatar mark">DG</div><div><div class="clinic">Dylan Groenendijk</div><div class="provider">Founder, DigiGrowth</div></div></div>
    <h1>${esc(ev ? ev.name : "Book a call")}</h1>
    ${ev ? `<div class="meta"><div>${ICON.clock}<span>${ev.duration_min} min</span></div><div>${ICON.video}<span>Google Meet (link in your invite)</span></div>${extra || ""}</div>
    ${ev.description ? `<p class="desc">${esc(ev.description)}</p>` : ""}` : ""}
    ${MODE === "book" ? `<button class="proof results-btn" id="resultsbtn"><span><span class="stars"><span class="s" aria-hidden="true">★★★★★</span><b>Real client results</b></span><span class="quote">A PT clinic's recent campaign: 11 new-patient visits booked against a goal of 10, at $46 per booking.</span></span><span class="go">See client results →</span></button>` : ""}`;
}

// "Example client results" gallery: two demo dashboards (sample numbers). Button reads "See client results",
// popup heading "Example client results" (Dylan, 2026-11-22); images carry no "sample" tag.
// The real Advantage screenshot (real-pt-clinic-results.jpg) was dropped from the gallery 2026-11-22 (Dylan).
const RESULTS = [
  { src: "sample-dashboard-1.jpg" },
  { src: "sample-dashboard-2.jpg" },
];
function openResults() {
  const m = document.createElement("div");
  m.className = "modal"; m.setAttribute("role", "dialog"); m.setAttribute("aria-modal", "true"); m.setAttribute("aria-label", "Example client results");
  m.innerHTML = `<div class="sheet"><button class="close" aria-label="Close">×</button><h2>Example client results <span class="h-stars" aria-hidden="true">★★★★★</span></h2>
    <p class="sub">Every client gets a live portal like this, showing leads, booked visits and cost per booking.</p>
    ${RESULTS.map((r) => `<figure class="shot"><img src="${BASE}/results/${r.src}?v=3" alt="Client portal dashboard" loading="lazy"></figure>`).join("")}</div>`;
  const close = () => { m.remove(); document.removeEventListener("keydown", onKey); };
  const onKey = (e) => { if (e.key === "Escape") close(); };
  m.onclick = (e) => { if (e.target === m) close(); };
  m.querySelector(".close").onclick = close;
  document.addEventListener("keydown", onKey);
  document.body.appendChild(m); m.querySelector(".close").focus();
}
document.addEventListener("click", (e) => { if (e.target.closest && e.target.closest("#resultsbtn")) openResults(); });

function progress(n) {
  return `<div class="progress">${["Pick a time", "Your details", "Confirmed"].map((l, i) => `<div class="${i < n ? "done" : ""}"><i></i><span>${l}</span></div>`).join("")}</div>`;
}

function curate(slots) {
  if (slots.length <= 4) return slots;
  const pick = new Set([0, Math.round((slots.length - 1) / 3), Math.round(2 * (slots.length - 1) / 3), slots.length - 1]);
  return [...pick].sort((a, b) => a - b).map(i => slots[i]);
}

// Month slot cache: "YYYY-MM" -> { "YYYY-MM-DD": [iso...] } in the visitor's timezone.
function slotLoader(fetchSlots) {
  const months = {};
  const load = async (ym) => {
    if (months[ym]) return months[ym];
    const first = ym + "-01", t = today();
    const start = first < t ? t : first;
    const [y, m] = ym.split("-").map(Number);
    const days = new Date(Date.UTC(y, m, 0)).getUTCDate() - Number(start.slice(8)) + 2;
    const slots = await fetchSlots(start, days);
    const map = {};
    slots.forEach((s) => { const d = localDate(s); if (d.slice(0, 7) === ym) (map[d] = map[d] || []).push(s); });
    return (months[ym] = map);
  };
  load.reset = () => { for (const k in months) delete months[k]; };  // zone changed: days regroup
  return load;
}

function picker(root, load, onPick, note) {
  let ym = today().slice(0, 7), day = null, showAll = false;
  root.innerHTML = `${note ? `<div class="note">${esc(note)}</div>` : ""}<div id="nextwrap"><div class="skeleton" style="height:56px"></div></div><div id="calwrap"></div><div id="timeswrap"></div>${tzLine()}`;
  wireTz(() => { load.reset(); picker(root, load, onPick, note); });
  async function findNext() {
    let m = ym;
    for (let i = 0; i < 3; i++, m = addMonth(m, 1)) {
      const map = await load(m), open = Object.keys(map).filter((k) => map[k].length).sort();
      if (open.length) return { day: open[0], slot: map[open[0]][0] };
    }
    return null;
  }
  async function render() {
    let map;
    try { map = await load(ym); } catch (e) { root.innerHTML = `<p class="err">${esc(e.message)}</p>`; return; }
    const [y, m] = ym.split("-").map(Number);
    const firstDow = (new Date(Date.UTC(y, m - 1, 1)).getUTCDay() + 6) % 7, n = new Date(Date.UTC(y, m, 0)).getUTCDate(), t = today();
    let cells = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"].map((d) => `<div class="dow">${d}</div>`).join("");
    for (let i = 0; i < firstDow; i++) cells += "<div></div>";
    for (let d = 1; d <= n; d++) {
      const iso = `${ym}-${String(d).padStart(2, "0")}`, ok = (map[iso] || []).length > 0;
      cells += `<button class="day ${ok ? "open" : ""} ${iso === day ? "sel" : ""} ${iso === t ? "today" : ""}" ${ok ? `data-d="${iso}"` : "disabled"} aria-label="${iso}${ok ? ", available" : ""}">${d}</button>`;
    }
    const label = new Date(Date.UTC(y, m - 1, 1)).toLocaleDateString("en-US", { month: "long", year: "numeric", timeZone: "UTC" });
    $("#calwrap").innerHTML = `<div class="calhead"><button class="navbtn" id="pm" ${ym > t.slice(0, 7) ? "" : "disabled"} aria-label="Previous month">‹</button><b>${label}</b><button class="navbtn" id="nm" aria-label="Next month">›</button></div><div class="cal">${cells}</div>`;
    $("#pm").onclick = () => { ym = addMonth(ym, -1); showAll = false; render(); };
    $("#nm").onclick = () => { ym = addMonth(ym, 1); showAll = false; render(); };
    $("#calwrap").querySelectorAll("[data-d]").forEach((b) => b.onclick = () => { day = b.dataset.d; showAll = false; render(); });
    const slots = (day && map[day]) || [];
    const shown = showAll ? slots : curate(slots);
    $("#timeswrap").innerHTML = slots.length
      ? `<div class="times"><div class="times-h"><b>${esc(fmtDay(slots[0]))}</b></div>
         <div class="grid">${shown.map((s) => `<button class="t" data-s="${s}">${esc(fmtTime(s))}</button>`).join("")}</div>
         ${slots.length > shown.length ? `<button class="more" id="more">Show all ${slots.length} times</button>` : ""}</div>`
      : `<div class="times muted">Pick a highlighted day to see times.</div>`;
    $("#timeswrap").querySelectorAll("[data-s]").forEach((b) => b.onclick = () => onPick(b.dataset.s));
    const more = $("#more"); if (more) more.onclick = () => { showAll = true; render(); };
  }
  findNext().then((next) => {
    if (!next) { $("#nextwrap").innerHTML = `<p class="muted">No open times in the next few weeks. Email dylanrg@digigrowthllc.com and I'll find a time.</p>`; return render(); }
    $("#nextwrap").innerHTML = `<button class="next" id="nextbtn"><span><small>Next available</small><b>${esc(fmtDay(next.slot))} at ${esc(fmtTime(next.slot))}</b></span><span aria-hidden="true">→</span></button>`;
    $("#nextbtn").onclick = () => onPick(next.slot);
    day = next.day; ym = next.day.slice(0, 7); render();
  }).catch((e) => { root.innerHTML = `<p class="err">${esc(e.message)}</p>`; });
}

async function bookMode() {
  const info = await api("info");
  const want = qs.get("type") === "strategy-call" ? "discovery-call" : qs.get("type");
  const shown = info.types.filter((t) => t.listed || t.slug === want);
  let ev = info.types.find((t) => t.slug === want) || (shown.length === 1 ? shown[0] : null);
  // Booking-link analytics: ?utm_source= (website) or the short ?via= (links the OS sends).
  const UTM = { utm_source: qs.get("utm_source") || qs.get("via"), utm_content: qs.get("utm_content") };
  const VID = (() => {
    const fresh = () => Math.random().toString(36).slice(2) + Date.now().toString(36);
    try { let v = localStorage.getItem("dg_bk_vid"); if (!v) { v = fresh(); localStorage.setItem("dg_bk_vid", v); } return v; }
    catch { return fresh(); }
  })();
  const REF = document.referrer || null;
  const sent = {};
  const track = (step, type) => {
    if (sent[step]) return; sent[step] = 1;
    try {
      const body = JSON.stringify({ visitor_id: VID, step, type, referrer: REF, ...UTM });
      if (!(navigator.sendBeacon && navigator.sendBeacon(BASE + "/api/track", new Blob([body], { type: "text/plain" }))))
        fetch(BASE + "/api/track", { method: "POST", body, keepalive: true }).catch(() => {});
    } catch {}
  };
  track("view", want || (ev && ev.slug) || null);
  if (!info.types.length) { $("#info").innerHTML = infoPanel(null); $("#main").innerHTML = `<p class="muted">Booking isn't open right now.</p>`; return; }
  if (!ev) {
    $("#info").innerHTML = infoPanel(null);
    $("#main").innerHTML = `${progress(0)}<h2>Pick a call</h2><div class="types">${shown.map((t) => `<button data-t="${t.id}"><span>${esc(t.name)}</span><span class="muted">${t.duration_min} min</span></button>`).join("")}</div>`;
    $("#main").querySelectorAll("[data-t]").forEach((b) => b.onclick = () => { ev = info.types.find((t) => t.id == b.dataset.t); start(); });
    return;
  }
  start();

  function start(note) {
    $("#info").innerHTML = infoPanel(ev);
    $("#main").innerHTML = `${progress(1)}<div id="pick"></div>`;
    const load = slotLoader((s, d) => api(`slots?type_id=${ev.id}&start=${s}&days=${d}`).then((r) => r.slots));
    picker($("#pick"), load, details, note);
  }

  function details(slot) {
    track("time", ev.slug);
    $("#info").innerHTML = infoPanel(ev, `<div>${ICON.cal}<span>${esc(fmtDay(slot))}, ${esc(fmtTime(slot))}</span></div>`);
    $("#main").innerHTML = `${progress(2)}<h2>Your details</h2>
      <div class="chosen"><div><b>${esc(fmtDay(slot))}</b><small>${esc(fmtTime(slot))} · ${ev.duration_min} min · ${esc(tzLabel())}</small></div><button class="link" id="chg">Change</button></div>
      <label for="n">Full name</label><input id="n" autocomplete="name" value="${esc(qs.get("name") || "")}">
      <label for="e">Email <small>(your Google Meet invite goes here)</small></label><input id="e" type="email" autocomplete="email" value="${esc(qs.get("email") || "")}">
      <label for="p">Mobile number <small>(for reminders)</small></label><input id="p" type="tel" inputmode="tel" autocomplete="tel" value="${esc(qs.get("phone") || "")}">
      <label for="b">Practice name <small>(optional)</small></label><input id="b" autocomplete="organization">
      <label for="q">Anything you'd like to cover? <small>(optional)</small></label><textarea id="q" rows="2"></textarea>
      <label class="consent" for="c"><input type="checkbox" id="c"><span>Yes, DigiGrowth may text me at this number about this call. Msg frequency varies. Msg &amp; data rates may apply. Reply STOP to opt out.</span></label>
      <button class="cta" id="go">Confirm my call</button><div class="err" id="err"></div>
      <p class="fine">You'll get a calendar invite with the Google Meet link, plus reminders before the call. Free to reschedule or cancel anytime.</p>`;
    $("#chg").onclick = () => start();
    $("#n").focus({ preventScroll: true });
    $("#go").onclick = async () => {
      const name = $("#n").value.trim(), email = $("#e").value.trim(), phone = $("#p").value;
      $("#err").textContent = "";
      if (!name) return ($("#err").textContent = "Please enter your name.");
      if (!/^\S+@\S+\.\S+$/.test(email)) return ($("#err").textContent = "Please enter a valid email.");
      if (digits(phone).length < 10) return ($("#err").textContent = "Please enter a 10-digit mobile number.");
      const btn = $("#go"); btn.disabled = true; btn.textContent = "Booking...";
      try {
        const r = await post("reserve", { type_id: ev.id, start: slot, name, email, phone, business: $("#b").value, note: $("#q").value,
          timezone: TZ, sms_consent: $("#c").checked, visitor_id: VID, referrer: REF, ...UTM });
        location.href = r.manage_url + "?new=1";
      } catch (e) {
        btn.disabled = false; btn.textContent = "Confirm my call";
        if (/taken/i.test(e.message)) return start(e.message);
        $("#err").textContent = e.message;
      }
    };
  }
}

async function manageMode() {
  let info = await api("info");
  const ev = { name: info.type_name, duration_min: info.duration_min, description: "" };
  function render() {
    $("#info").innerHTML = infoPanel(ev, `<div>${ICON.cal}<span>${esc(fmtDay(info.start))}, ${esc(fmtTime(info.start))}</span></div>`);
    const when = `${fmtDay(info.start)} at ${fmtTime(info.start)}`;
    if (info.status !== "confirmed") {
      $("#main").innerHTML = `<div class="ok"><h2>This call was cancelled</h2><p class="muted">Want a new time? <a class="link" href="${esc(info.book_url)}">Book again</a></p></div>`;
      return;
    }
    const fresh = qs.get("new");
    $("#main").innerHTML = `${progress(3)}<div class="ok"><div class="tick">✓</div><h2 style="font-size:22px">${fresh ? "You're booked!" : "Your call"}</h2>
        <p style="margin:0 0 4px"><b>${esc(when)}</b></p><p class="muted" style="margin:0">${esc(ev.name)} · ${ev.duration_min} min · ${esc(tzLabel())}</p></div>
      ${info.meet_link ? `<a class="cta" href="${esc(info.meet_link)}" target="_blank" rel="noopener">Join Google Meet</a>` : ""}
      <a class="cta ghost" href="${esc(info.add_to_calendar)}" target="_blank" rel="noopener">Add to my calendar</a>
      ${fresh ? `<p class="muted" style="text-align:center;margin-top:12px">A calendar invite with the Meet link is on its way to ${esc(info.email)}.</p>` : ""}
      <div class="row" style="margin-top:6px"><button class="cta ghost" id="rs">Reschedule</button><button class="cta danger" id="cx">Cancel</button></div><div id="area"></div>`;
    $("#rs").onclick = () => {
      $("#area").innerHTML = `<h2 style="margin-top:22px">Pick a new time</h2><div id="pick"></div><div class="err" id="err"></div>`;
      const load = slotLoader((s, d) => api(`slots?start=${s}&days=${d}`).then((r) => r.slots));
      picker($("#pick"), load, async (slot) => {
        try { info = await post("reschedule", { start: slot }); qs.delete("new"); render(); }
        catch (e) { $("#err").textContent = e.message; }
      });
    };
    $("#cx").onclick = () => {
      $("#area").innerHTML = `<p style="margin-top:18px">Cancel your call on ${esc(when)}?</p>
        <label for="why">Anything I should know? <small>(optional)</small></label><textarea id="why" rows="2"></textarea>
        <div class="row"><button class="cta ghost" id="keep">Keep it</button><button class="cta danger" id="yes">Yes, cancel</button></div><div class="err" id="err"></div>`;
      $("#keep").onclick = () => ($("#area").innerHTML = "");
      $("#yes").onclick = async () => {
        $("#yes").disabled = true;
        try { info = await post("cancel", { reason: $("#why").value }); render(); }
        catch (e) { $("#err").textContent = e.message; $("#yes").disabled = false; }
      };
    };
  }
  render();
}

(MODE === "book" ? bookMode : manageMode)().catch((e) => { $("#main").innerHTML = `<p class="err">${esc(e.message)}</p>`; });
</script>
</body>
</html>
"""


def render(mode: str) -> str:
    title = "Book a call with DigiGrowth" if mode == "book" else "Your call with DigiGrowth"
    from booking_page import TZ_PICKER_CSS, TZ_PICKER_JS
    return _TEMPLATE.replace("/*__TZ_PICKER_CSS__*/", TZ_PICKER_CSS).replace("/*__TZ_PICKER__*/", TZ_PICKER_JS).replace("__TITLE__", title).replace("__MODE__", '"book"' if mode == "book" else '"manage"')
