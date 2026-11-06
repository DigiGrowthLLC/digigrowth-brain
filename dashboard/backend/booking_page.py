"""The patient-facing booking page + manage page (one self-contained HTML
document, vanilla JS). Served by routers/booking.py at /book/<slug>,
/lp/<landing slug>/book (funnels) and /booking/<token> (manage). All API
calls are relative to the page's own path, so it works unchanged behind the
client-funnels Vercel proxy on a clinic's own domain.

Layout follows Calendly (who/what on the left, month calendar + times on the
right) with the conversion elements from the 2026-11-06 research plan:
next-available button, a few spread-out times per day, real "times left this
week" count, Google rating + a real review, risk reversal under the button,
3-step progress, name + mobile only, partial capture as they type, resume
links, ?h= headline pass-through, step tracking. No fake urgency."""
import html
import json

_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>__TITLE__</title>
<style>
  :root{ --accent:__ACCENT__; --accent-soft:color-mix(in srgb, var(--accent) 12%, #fff); --ink:#151b28; --soft:#5a6377;
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
</style>
</head>
<body>
<div class="wrap"><div class="shell" id="shell">
  <aside class="info" id="info"><div class="clinic">__CLINIC__</div></aside>
  <section class="main" id="main"><div class="skeleton"></div></section>
</div><footer>Secure online booking</footer></div>
<script>
const MODE = __MODE__;
const BASE = location.pathname.replace(/\/+$/, "");
const qs = new URLSearchParams(location.search);
const $ = (s, r = document) => r.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
let TZ = "UTC";
const fmt = (iso, o) => new Intl.DateTimeFormat("en-US", { timeZone: TZ, ...o }).format(new Date(iso));
const fmtDay = (iso) => fmt(iso, { weekday: "long", month: "long", day: "numeric" });
const fmtShortDay = (iso) => fmt(iso, { weekday: "short", month: "short", day: "numeric" });
const fmtTime = (iso) => fmt(iso, { hour: "numeric", minute: "2-digit" });
const localDate = (iso) => new Intl.DateTimeFormat("en-CA", { timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(iso));
const todayLocal = () => localDate(new Date().toISOString());
const tzLabel = () => { try { return new Intl.DateTimeFormat("en-US", { timeZone: TZ, timeZoneName: "long" }).formatToParts(new Date()).find(p => p.type === "timeZoneName").value; } catch { return TZ; } };
const money = (c) => "$" + (c / 100).toFixed(c % 100 ? 2 : 0);
const digits = (s) => String(s || "").replace(/\D/g, "");
const SESSION = (() => { try { const k = "dgb_s_" + BASE; let v = sessionStorage.getItem(k); if (!v) { v = (crypto.randomUUID ? crypto.randomUUID() : String(Math.random()).slice(2) + Date.now()); sessionStorage.setItem(k, v); } return v; } catch { return String(Math.random()).slice(2) + Date.now(); } })();
const UTM = { utm_source: qs.get("utm_source") || (location.pathname.startsWith("/lp/") ? "paid_ad" : null), utm_content: qs.get("utm_content") };

async function api(path, opts) {
  const r = await fetch(BASE + "/api/" + path, { headers: { "Content-Type": "application/json" }, ...opts });
  let body = null; try { body = await r.json(); } catch {}
  if (!r.ok) throw new Error((body && body.detail) || "Something went wrong. Please try again.");
  return body;
}
const post = (path, body) => api(path, { method: "POST", body: JSON.stringify(body) });
const track = (step, ev) => { if (MODE === "book") post("event", { session: SESSION, step, event_type_id: ev && ev.id, ...UTM }).catch(() => {}); };

const ICON = {
  clock: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
  pin: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 21s7-6.2 7-12a7 7 0 1 0-14 0c0 5.8 7 12 7 12z"/><circle cx="12" cy="9" r="2.5"/></svg>',
  video: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="6" width="13" height="12" rx="2"/><path d="M16 10l5-3v10l-5-3"/></svg>',
  phone: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2"/></svg>',
  tag: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 12l-8 8-9-9V3h8z"/><circle cx="7.5" cy="7.5" r="1.5"/></svg>',
  lock: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>',
};
const locLine = (ev) => ev.location_type === "google_meet" ? [ICON.video, "Video call (link sent after booking)"]
  : ev.location_type === "phone" ? [ICON.phone, "Phone call: we call you"] : [ICON.pin, ev.location_text || "In person"];

function infoPanel(clinic, ev, prof, headline) {
  const [li, lt] = locLine(ev);
  const avatar = prof.photo_url ? `<img class="avatar" src="${esc(prof.photo_url)}" alt="">` : "";
  const price = ev.price_cents > 0
    ? `<div>${ICON.tag}<span class="price">${money(ev.price_cents)}${ev.anchor_price_cents > ev.price_cents ? `<span class="was">normally <s>${money(ev.anchor_price_cents)}</s></span>` : ""}</span></div>`
    : `<div>${ICON.tag}<span class="price">Free${ev.anchor_price_cents ? `<span class="was">normally <s>${money(ev.anchor_price_cents)}</s></span>` : ""}</span></div>`;
  const rv = prof.reviews;
  const proof = rv ? `<div class="proof">${rv.rating ? `<div class="stars"><span class="s">${"★".repeat(Math.round(rv.rating))}</span><b>${rv.rating.toFixed(1)}</b><span class="muted">${rv.count ? `(${rv.count} Google reviews)` : "on Google"}</span></div>` : ""}
      ${rv.items && rv.items[0] ? `<div class="quote">“${esc(rv.items[0].text)}” ${rv.items[0].author ? `<small>${esc(rv.items[0].author)}</small>` : ""}</div>` : ""}</div>` : "";
  const expect = (prof.what_to_expect || []).length ? `<ul class="checks">${prof.what_to_expect.map(x => `<li>${esc(x)}</li>`).join("")}</ul>`
    : (ev.description ? `<p class="desc">${esc(ev.description)}</p>` : "");
  return `${prof.logo_url ? `<img class="logo" src="${esc(prof.logo_url)}" alt="${esc(clinic)}">` : ""}<div class="who">${avatar}<div><div class="clinic">${esc(clinic)}</div>${prof.provider_name ? `<div class="provider">${esc(prof.provider_name)}${prof.provider_title ? ", " + esc(prof.provider_title) : ""}</div>` : ""}</div></div>
    ${headline ? `<div class="headline">${esc(headline)}</div>` : ""}
    <h1>${esc(ev.name)}</h1>
    <div class="meta"><div>${ICON.clock}<span>${ev.duration_min} min</span></div><div>${li}<span>${esc(lt)}</span></div>${price}</div>
    ${ev.spots_per_month ? `<span class="spots">Only ${ev.spots_per_month} new-patient spots per month</span>` : ""}
    ${proof}${expect}`;
}

function progress(n) {
  return `<div class="progress">${["Pick a time", "Your details", "Confirmed"].map((l, i) => `<div class="${i < n ? "done" : ""}"><i></i><span>${l}</span></div>`).join("")}</div>`;
}

function curate(slots) {
  if (slots.length <= 4) return slots;
  const pick = new Set([0, Math.round((slots.length - 1) / 3), Math.round(2 * (slots.length - 1) / 3), slots.length - 1]);
  return [...pick].sort((a, b) => a - b).map(i => slots[i]);
}

// ── Booking mode ─────────────────────────────────────────────────────────────
async function bookMode() {
  const info = await api("info");
  TZ = info.timezone;
  const prof = info.profile || {};
  if (!info.event_types.length) { $("#main").innerHTML = `<p class="muted">Online booking isn't available right now. Please call the clinic.</p>`; return; }
  let resume = {};
  if (qs.get("r")) { try { resume = await api("resume?r=" + encodeURIComponent(qs.get("r"))); } catch {} }
  const wantType = qs.get("type") || resume.type;
  let ev = info.event_types.find(e => e.slug === wantType) || (info.event_types.length === 1 ? info.event_types[0] : null);
  const headline = (qs.get("h") || "").slice(0, 90);
  if (qs.get("cancelled")) post("release", { token: qs.get("cancelled") }).catch(() => {});
  const pre = { name: qs.get("name") || resume.name || "", phone: qs.get("phone") || resume.phone || "", slot: qs.get("slot") || resume.slot || null };

  if (!ev) {
    $("#info").innerHTML = `<div class="who">${prof.photo_url ? `<img class="avatar" src="${esc(prof.photo_url)}" alt="">` : ""}<div><div class="clinic">${esc(info.clinic)}</div></div></div><h1>Book a visit</h1>`;
    $("#main").innerHTML = `<h2>Choose a visit</h2>${info.event_types.map(e => `<button class="cta ghost" style="justify-content:space-between" data-ev="${e.id}"><span>${esc(e.name)}</span><span class="muted">${e.duration_min} min${e.price_cents ? " · " + money(e.price_cents) : " · Free"}</span></button>`).join("")}`;
    $("#main").onclick = (e) => { const b = e.target.closest("[data-ev]"); if (b) { ev = info.event_types.find(x => x.id == b.dataset.ev); $("#main").onclick = null; start(); } };
    track("view", null);
  }

  function start() {
    $("#info").innerHTML = infoPanel(info.clinic, ev, prof, headline);
    track("view", ev);
    if (pre.slot) jumpToSlot(); else pickStep();
  }

  // month cache: "YYYY-MM" -> {date: [slots]}
  const months = {};
  async function loadMonth(ym) {
    if (months[ym]) return months[ym];
    const today = todayLocal();
    const first = ym + "-01";
    const startDay = first < today ? today : first;
    const [y, m] = ym.split("-").map(Number);
    const days = new Date(Date.UTC(y, m, 0)).getUTCDate() - Number(startDay.slice(8)) + 1;
    const data = await api(`slots?event_type_id=${ev.id}&start=${startDay}&days=${Math.max(1, days)}`);
    const map = {}; data.days.forEach(d => { map[d.date] = d.slots; });
    months[ym] = map; return map;
  }
  const ymOf = (d) => d.slice(0, 7);
  const addMonth = (ym, n) => { const [y, m] = ym.split("-").map(Number); const d = new Date(Date.UTC(y, m - 1 + n, 1)); return d.toISOString().slice(0, 7); };
  const lastBookable = () => { const d = new Date(todayLocal() + "T12:00:00Z"); d.setUTCDate(d.getUTCDate() + (ev.max_days_ahead || 14)); return d.toISOString().slice(0, 10); };

  async function findNext() {
    let ym = ymOf(todayLocal());
    for (let i = 0; i < 3; i++) {
      const map = await loadMonth(ym);
      const day = Object.keys(map).sort().find(k => map[k].length);
      if (day) return { day, slot: map[day][0] };
      if (ym >= ymOf(lastBookable())) break;
      ym = addMonth(ym, 1);
    }
    return null;
  }

  let state = { ym: ymOf(todayLocal()), day: null, slot: null, showAll: false };

  async function pickStep(note) {
    const main = $("#main");
    main.innerHTML = `${progress(1)}${note ? `<div class="note">${esc(note)}</div>` : ""}<div id="nextwrap"><div class="skeleton" style="height:56px"></div></div><div id="calwrap"></div><div id="timeswrap"></div><div class="tz">Times shown in ${esc(tzLabel())}</div>`;
    let next;
    try { next = await findNext(); } catch (e) { main.innerHTML = `<p class="err">${esc(e.message)}</p>`; return; }
    if (!next) { $("#nextwrap").innerHTML = `<p class="muted">No openings in the next ${ev.max_days_ahead || 14} days. Please call the clinic and they'll fit you in.</p>`; return; }
    $("#nextwrap").innerHTML = `<button class="next" id="nextbtn"><span><small>Next available</small><b>${esc(fmtDay(next.slot))} at ${esc(fmtTime(next.slot))}</b></span><span aria-hidden="true">→</span></button>`;
    $("#nextbtn").onclick = () => choose(next.slot);
    if (!state.day) { state.day = next.day; state.ym = ymOf(next.day); }
    renderCal();
  }

  async function renderCal() {
    const map = await loadMonth(state.ym);
    const [y, m] = state.ym.split("-").map(Number);
    const firstDow = (new Date(Date.UTC(y, m - 1, 1)).getUTCDay() + 6) % 7;
    const nDays = new Date(Date.UTC(y, m, 0)).getUTCDate();
    const today = todayLocal();
    const label = new Date(Date.UTC(y, m - 1, 1)).toLocaleDateString("en-US", { month: "long", year: "numeric", timeZone: "UTC" });
    let cells = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"].map(d => `<div class="dow">${d}</div>`).join("");
    for (let i = 0; i < firstDow; i++) cells += "<div></div>";
    for (let d = 1; d <= nDays; d++) {
      const iso = `${state.ym}-${String(d).padStart(2, "0")}`;
      const open = (map[iso] || []).length > 0;
      cells += `<button class="day ${open ? "open" : ""} ${iso === state.day ? "sel" : ""} ${iso === today ? "today" : ""}" ${open ? `data-d="${iso}"` : "disabled"} aria-label="${iso}${open ? ", available" : ""}">${d}</button>`;
    }
    const canPrev = state.ym > ymOf(today), canNext = state.ym < ymOf(lastBookable());
    $("#calwrap").innerHTML = `<div class="calhead"><button class="navbtn" id="prevm" ${canPrev ? "" : "disabled"} aria-label="Previous month">‹</button><b>${label}</b><button class="navbtn" id="nextm" ${canNext ? "" : "disabled"} aria-label="Next month">›</button></div><div class="cal">${cells}</div>`;
    $("#prevm").onclick = () => { state.ym = addMonth(state.ym, -1); state.showAll = false; renderCal(); };
    $("#nextm").onclick = () => { state.ym = addMonth(state.ym, 1); state.showAll = false; renderCal(); };
    $("#calwrap").querySelectorAll("[data-d]").forEach(b => b.onclick = () => { state.day = b.dataset.d; state.showAll = false; renderCal(); });
    renderTimes(map);
  }

  async function weekLeft(dayIso) {
    // Real count of open start times left this week (Mon-Sun), only when every bookable day of the week is loaded.
    const d = new Date(dayIso + "T12:00:00Z"); const dow = (d.getUTCDay() + 6) % 7; d.setUTCDate(d.getUTCDate() - dow);
    const today = todayLocal(), last = lastBookable(); let n = 0;
    for (let i = 0; i < 7; i++) {
      const iso = d.toISOString().slice(0, 10); d.setUTCDate(d.getUTCDate() + 1);
      if (iso < today || iso > last) continue;
      const map = await loadMonth(ymOf(iso)).catch(() => null);
      if (!map) return null;
      n += (map[iso] || []).length;
    }
    return n;
  }

  async function renderTimes(map) {
    const wrap = $("#timeswrap");
    const slots = (map[state.day] || []);
    if (!state.day || !slots.length) { wrap.innerHTML = `<div class="times muted">Pick a highlighted day to see times.</div>`; return; }
    const shown = state.showAll ? slots : curate(slots);
    wrap.innerHTML = `<div class="times"><div class="times-h"><b>${esc(fmtDay(slots[0]))}</b><span class="left" id="left"></span></div>
      <div class="grid">${shown.map(s => `<button class="t" data-s="${s}">${esc(fmtTime(s))}</button>`).join("")}</div>
      ${slots.length > shown.length ? `<button class="more" id="more">Show all ${slots.length} times</button>` : ""}</div>`;
    wrap.querySelectorAll("[data-s]").forEach(b => b.onclick = () => choose(b.dataset.s));
    const more = $("#more"); if (more) more.onclick = () => { state.showAll = true; renderTimes(map); };
    const n = await weekLeft(state.day);
    if (n !== null && n > 0 && n <= 6 && $("#left")) $("#left").textContent = `Only ${n} time${n === 1 ? "" : "s"} left this week`;
  }

  function choose(slot) {
    state.slot = slot; track("time", ev); detailsStep();
  }

  async function jumpToSlot() {
    // Pre-picked slot (resume link, AI agent link): straight to details if it's still open.
    try {
      const day = localDate(pre.slot);
      const map = await loadMonth(ymOf(day));
      if ((map[day] || []).includes(pre.slot)) { state.day = day; state.ym = ymOf(day); choose(pre.slot); return; }
    } catch {}
    pickStep("That time was just taken. Here's what's open now.");
  }

  let saveTimer = null;
  function savePartial() {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      const name = $("#n") && $("#n").value.trim(), phone = $("#p") && $("#p").value;
      if (name && digits(phone).length >= 10) post("partial", { session: SESSION, name, phone, event_type_id: ev.id, start: state.slot, ...UTM }).catch(() => {});
    }, 700);
  }

  function detailsStep() {
    const paid = ev.price_cents > 0;
    const pol = prof.refund_policy;
    const assure = paid
      ? [pol === "always" ? "Fully refundable if you cancel" : pol === "24h" ? "Full refund if you cancel 24+ hours ahead" : null, "Reschedule from your confirmation text", "Secure checkout by Stripe"]
      : ["Free to reschedule or cancel", "Confirmation sent by text"];
    $("#main").innerHTML = `${progress(2)}
      <div class="chosen"><div><b>${esc(fmtDay(state.slot))}</b><small>${esc(fmtTime(state.slot))} · ${ev.duration_min} min · ${esc(tzLabel())}</small></div><button class="link" id="change">Change</button></div>
      <label for="n">Full name</label><input id="n" autocomplete="name" value="${esc(pre.name)}" required>
      <label for="p">Mobile number <small>(for your confirmation text)</small></label><input id="p" type="tel" inputmode="tel" autocomplete="tel" value="${esc(pre.phone)}" required>
      ${ev.ask_question ? `<label for="q">${esc(ev.ask_question)} <small>(optional)</small></label><textarea id="q" rows="2"></textarea>` : ""}
      <button class="cta" id="go">${paid ? ICON.lock + " Continue to secure payment" : "Confirm my visit"}</button>
      <ul class="assure">${assure.filter(Boolean).map(a => `<li>${esc(a)}</li>`).join("")}</ul>
      ${paid ? `<p class="muted" style="margin-top:8px;font-size:13px">We hold this time for you for 30 minutes while you pay.</p>` : ""}
      <div class="err" id="err"></div>
      <p class="fine">By booking you agree to get appointment texts from ${esc(info.clinic)}. Msg &amp; data rates may apply. Reply STOP to opt out.</p>`;
    $("#change").onclick = () => pickStep();
    $("#n").oninput = savePartial; $("#p").oninput = savePartial;
    if (pre.name && digits(pre.phone).length >= 10) savePartial();
    ($("#n").value ? $("#p") : $("#n")).focus({ preventScroll: true });
    $("#main").scrollIntoView({ behavior: "smooth", block: "start" });
    $("#go").onclick = async () => {
      const btn = $("#go"), label = btn.innerHTML; $("#err").textContent = "";
      const name = $("#n").value.trim(), phone = $("#p").value;
      if (!name) { $("#err").textContent = "Please enter your name."; return; }
      if (digits(phone).length < 10) { $("#err").textContent = "Please enter a 10-digit mobile number."; return; }
      btn.disabled = true; btn.textContent = "One moment...";
      try {
        const r = await post("reserve", { event_type_id: ev.id, start: state.slot, name, phone, answer: $("#q") ? $("#q").value : null, session: SESSION, ...UTM });
        if (r.checkout_url) { location.href = r.checkout_url; return; }
        location.href = r.manage_url + "?new=1";
      } catch (e) {
        btn.disabled = false; btn.innerHTML = label;
        if (/taken/i.test(e.message)) { state.slot = null; pickStep(e.message); return; }
        $("#err").textContent = e.message;
      }
    };
  }

  if (ev) start();
}

// ── Manage mode ──────────────────────────────────────────────────────────────
async function manageMode() {
  let info = await api("info");
  TZ = info.timezone;
  let polls = 0;
  const ev = info.event;
  const prof = { provider_name: info.provider_name, provider_title: info.provider_title, photo_url: info.photo_url, what_to_expect: info.what_to_expect, reviews: null };
  $("#info").innerHTML = infoPanel(info.clinic, ev, prof, "");
  function render() {
    const main = $("#main");
    const when = `${fmtDay(info.start)} at ${fmtTime(info.start)}`;
    if (info.status === "pending_payment" && qs.get("paid") && polls < 15) {
      main.innerHTML = `${progress(2)}<div class="ok"><p class="muted">Confirming your payment...</p></div>`;
      setTimeout(async () => { polls++; info = await api("info"); render(); }, 2000); return;
    }
    if (info.status === "confirmed") {
      const fresh = qs.get("new") || qs.get("paid");
      main.innerHTML = `${progress(3)}<div class="ok"><div class="tick">✓</div><h2 style="font-size:22px">${fresh ? "You're booked!" : "Your appointment"}</h2>
        <p style="margin:0 0 4px"><b>${esc(when)}</b></p><p class="muted" style="margin:0">${esc(ev.name)} · ${ev.duration_min} min</p></div>
        ${info.meet_link ? `<a class="cta" href="${esc(info.meet_link)}" target="_blank" rel="noopener">Join video call</a>` : ""}
        ${info.map_url ? `<a class="cta ghost" href="${esc(info.map_url)}" target="_blank" rel="noopener">Directions to ${esc(info.clinic)}</a>` : ""}
        <a class="cta ghost" href="${esc(info.add_to_calendar)}" target="_blank" rel="noopener">Add to my calendar</a>
        ${info.paid ? `<p class="muted" style="text-align:center;margin-top:10px">Paid online. Thank you.</p>` : ""}
        ${fresh ? `<p class="muted" style="text-align:center;margin-top:10px">We just texted you a confirmation. You'll get reminders before your visit.</p>` : ""}
        ${info.can_change ? `<div class="row" style="margin-top:6px"><button class="cta ghost" id="rs">Reschedule</button><button class="cta danger" id="cx">Cancel</button></div><div id="area"></div>` : ""}`;
    } else if (info.status === "cancelled") {
      main.innerHTML = `<div class="ok"><h2>This appointment was cancelled</h2><p class="muted">${esc(info.cancel_reason || "")}</p>
        ${info.refunded ? `<p class="muted">Your payment has been refunded. It can take 5 to 10 days to show on your statement.</p>` : ""}</div>`;
    } else if (info.status === "pending_payment") {
      main.innerHTML = `<div class="ok"><h2>Still confirming your payment</h2><p class="muted">This can take a minute. Refresh this page shortly. You'll also get a text once it's confirmed.</p></div>`;
    } else {
      main.innerHTML = `<div class="ok"><h2>This booking wasn't completed</h2><p class="muted">The payment wasn't finished, so the time was released.</p></div>`;
    }
    const rs = $("#rs"), cx = $("#cx");
    if (rs) rs.onclick = () => reschedule();
    if (cx) cx.onclick = () => {
      const refund = info.paid ? (info.refund_policy === "always" ? "Your payment will be refunded."
        : info.refund_policy === "24h" ? "Payments are refunded when you cancel at least 24 hours ahead." : "Payments aren't refundable.") : "";
      $("#area").innerHTML = `<p style="margin-top:16px">Cancel your visit on ${esc(when)}? ${esc(refund)} Rescheduling keeps your spot.</p>
        <label for="why">Anything we should know? <small>(optional)</small></label><textarea id="why" rows="2"></textarea>
        <div class="row"><button class="cta ghost" id="keep">Keep it</button><button class="cta danger" id="yes">Yes, cancel</button></div><div class="err" id="err"></div>`;
      $("#keep").onclick = () => { $("#area").innerHTML = ""; };
      $("#yes").onclick = async () => {
        $("#yes").disabled = true;
        try { info = await post("cancel", { reason: $("#why").value }); render(); }
        catch (e) { $("#err").textContent = e.message; $("#yes").disabled = false; }
      };
    };
  }
  async function reschedule() {
    const area = $("#area");
    area.innerHTML = `<h2 style="margin-top:18px">Pick a new time</h2><div id="rlist"><div class="skeleton" style="height:120px"></div></div><div class="err" id="err"></div>`;
    let data; try { data = await api("slots?days=14"); } catch (e) { $("#err").textContent = e.message; return; }
    const days = data.days.filter(d => d.slots.length).slice(0, 6);
    if (!days.length) { $("#rlist").innerHTML = `<p class="muted">No other openings right now. Please call the clinic.</p>`; return; }
    $("#rlist").innerHTML = days.map(d => `<div style="margin:12px 0 6px;font-weight:700;font-size:14px">${esc(fmtShortDay(d.slots[0]))}</div><div class="grid">${curate(d.slots).map(s => `<button class="t" data-s="${s}">${esc(fmtTime(s))}</button>`).join("")}</div>`).join("");
    $("#rlist").querySelectorAll("[data-s]").forEach(b => b.onclick = async () => {
      b.disabled = true; $("#err").textContent = "";
      try { info = await post("reschedule", { start: b.dataset.s }); qs.delete("new"); qs.delete("paid"); render(); }
      catch (e) { $("#err").textContent = e.message; b.disabled = false; }
    });
  }
  render();
}

(MODE === "book" ? bookMode : manageMode)().catch((e) => { $("#main").innerHTML = `<p class="err">${esc(e.message)}</p>`; });
</script>
</body>
</html>
"""


def render_page(mode: str, clinic: str, accent: str) -> str:
    title = f"Book with {clinic}" if mode == "book" else f"Your appointment with {clinic}"
    return (_TEMPLATE
            .replace("__TITLE__", html.escape(title))
            .replace("__CLINIC__", html.escape(clinic or ""))
            .replace("__ACCENT__", accent if accent and accent.startswith("#") and len(accent) == 7 else "#2f6fd6")
            .replace("__MODE__", json.dumps(mode)))
