"""HTML for Dylan's booking page (personal_booking.py). One self-contained page,
two modes: "book" (pick a call type, time, details) and "manage" (the
booking's own page: join link, reschedule, cancel). Every API call is
relative to the page's own path, so it works at
booking.digigrowthllc.com/strategy-call and at /book/strategy-call alike."""

_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<meta name="robots" content="noindex">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@600;700&display=swap" rel="stylesheet">
<style>
  :root{ --bg:#090f26; --card:rgba(16,27,62,.78); --line:rgba(106,176,255,.16); --text:#eef3ff; --soft:#93a7c9; --mute:#5f7aa6;
         --accent:#3a7bd5; --accent2:#6ab0ff; --ok:#14c882; --bad:#ff8a8a; }
  *{ box-sizing:border-box; }
  body{ margin:0; min-height:100vh; background:var(--bg); color:var(--text); font-family:Inter,system-ui,sans-serif; font-size:15px;
        background-image:radial-gradient(ellipse at 15% 0%,rgba(40,87,160,.25) 0%,transparent 55%),radial-gradient(ellipse at 95% 15%,rgba(20,200,130,.07) 0%,transparent 45%);
        background-attachment:fixed; }
  .wrap{ max-width:980px; margin:0 auto; padding:32px 16px 40px; }
  .shell{ display:grid; grid-template-columns:320px 1fr; border:1px solid var(--line); border-radius:20px; overflow:hidden; background:var(--card);
          backdrop-filter:blur(14px); box-shadow:0 24px 70px rgba(0,0,0,.45); }
  .info{ padding:28px 26px; border-right:1px solid var(--line); }
  .main{ padding:28px 26px; min-height:460px; }
  @media (max-width:760px){ .shell{ grid-template-columns:1fr; } .info{ border-right:0; border-bottom:1px solid var(--line); } }
  .brand{ display:flex; align-items:center; gap:12px; margin-bottom:22px; }
  .mark{ width:44px; height:44px; border-radius:12px; display:grid; place-items:center; font:700 18px 'Space Grotesk',sans-serif; color:#fff;
         background:linear-gradient(135deg,var(--accent),var(--accent2)); flex-shrink:0; }
  .host{ font-weight:600; } .co{ color:var(--soft); font-size:13px; }
  h1{ font:700 26px/1.2 'Space Grotesk',sans-serif; letter-spacing:-.02em; margin:0 0 14px; }
  h2{ font:700 19px 'Space Grotesk',sans-serif; margin:0 0 14px; }
  .meta div{ display:flex; gap:10px; align-items:center; color:var(--soft); margin:8px 0; font-size:14px; }
  .meta svg{ color:var(--accent2); flex-shrink:0; }
  .desc{ color:var(--soft); line-height:1.55; font-size:14px; margin-top:16px; }
  .calhead{ display:flex; align-items:center; justify-content:space-between; margin-bottom:10px; }
  .navbtn{ width:34px; height:34px; border-radius:10px; border:1px solid var(--line); background:transparent; color:var(--text); font-size:18px; cursor:pointer; }
  .navbtn:disabled{ opacity:.3; cursor:default; }
  .cal{ display:grid; grid-template-columns:repeat(7,1fr); gap:6px; }
  .dow{ text-align:center; font-size:11.5px; color:var(--mute); padding:4px 0; }
  .day{ aspect-ratio:1; border-radius:10px; border:0; background:transparent; color:var(--mute); font:500 14px Inter,sans-serif; cursor:default; }
  .day.open{ background:rgba(58,123,213,.16); color:var(--text); cursor:pointer; font-weight:600; }
  .day.open:hover{ background:rgba(58,123,213,.3); }
  .day.sel{ background:linear-gradient(135deg,var(--accent),var(--accent2)) !important; color:#fff; }
  .split{ display:grid; grid-template-columns:1fr 200px; gap:22px; }
  @media (max-width:760px){ .split{ grid-template-columns:1fr; } }
  .times{ display:grid; gap:8px; max-height:380px; overflow-y:auto; align-content:start; }
  .times b{ font-size:14px; margin-bottom:2px; }
  .t{ padding:11px; border-radius:10px; border:1px solid rgba(106,176,255,.4); background:transparent; color:var(--accent2); font:600 14px Inter,sans-serif; cursor:pointer; }
  .t:hover{ background:rgba(58,123,213,.15); }
  .tz{ color:var(--mute); font-size:12.5px; margin-top:14px; }
  label{ display:block; font-size:13px; color:var(--soft); margin:14px 0 6px; font-weight:500; }
  label small{ color:var(--mute); font-weight:400; }
  input, textarea{ width:100%; padding:12px 13px; border-radius:10px; border:1px solid rgba(106,176,255,.25); background:rgba(9,15,38,.75);
                   color:var(--text); font:15px Inter,sans-serif; outline:none; }
  input:focus, textarea:focus{ border-color:var(--accent2); }
  .consent{ display:flex; gap:10px; align-items:flex-start; font-size:12.5px; line-height:1.45; cursor:pointer; }
  .consent input{ width:18px; height:18px; flex:0 0 18px; margin:1px 0 0; accent-color:var(--accent); }
  .cta{ display:flex; align-items:center; justify-content:center; gap:8px; width:100%; margin-top:18px; padding:13px; border-radius:11px; border:0;
        background:linear-gradient(135deg,var(--accent),var(--accent2)); color:#fff; font:600 15px Inter,sans-serif; cursor:pointer; text-decoration:none; }
  .cta:disabled{ opacity:.6; }
  .cta.ghost{ background:transparent; border:1px solid rgba(106,176,255,.4); color:var(--accent2); }
  .cta.danger{ background:transparent; border:1px solid rgba(255,138,138,.45); color:var(--bad); }
  .row{ display:flex; gap:10px; } .row > *{ flex:1; }
  .chosen{ display:flex; justify-content:space-between; align-items:center; padding:13px 15px; border-radius:12px; background:rgba(58,123,213,.12); border:1px solid var(--line); }
  .chosen small{ display:block; color:var(--soft); margin-top:2px; }
  .link{ background:none; border:0; color:var(--accent2); cursor:pointer; font:500 14px Inter,sans-serif; }
  .types button{ display:flex; justify-content:space-between; width:100%; margin-bottom:10px; padding:15px; border-radius:12px; text-align:left;
                 border:1px solid var(--line); background:rgba(9,15,38,.5); color:var(--text); font:600 15px Inter,sans-serif; cursor:pointer; }
  .types button:hover{ border-color:var(--accent2); }
  .muted{ color:var(--soft); } .err{ color:var(--bad); font-size:14px; margin-top:10px; }
  .fine{ font-size:11.5px; color:var(--mute); margin-top:12px; line-height:1.5; }
  .ok{ text-align:center; } .tick{ width:58px; height:58px; border-radius:50%; background:rgba(20,200,130,.15); color:var(--ok); display:grid; place-items:center; font-size:28px; margin:0 auto 12px; }
  .skeleton{ height:240px; border-radius:12px; background:linear-gradient(90deg,rgba(255,255,255,.03),rgba(255,255,255,.07),rgba(255,255,255,.03)); background-size:200% 100%; animation:sh 1.2s infinite; }
  @keyframes sh{ to{ background-position:-200% 0; } }
  @media (prefers-reduced-motion: reduce){ .skeleton{ animation:none; } }
  footer{ text-align:center; color:var(--mute); font-size:12px; margin-top:18px; }
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
const TZ = Intl.DateTimeFormat().resolvedOptions().timeZone || "America/New_York";
const fmt = (iso, o) => new Intl.DateTimeFormat("en-US", { timeZone: TZ, ...o }).format(new Date(iso));
const fmtDay = (iso) => fmt(iso, { weekday: "long", month: "long", day: "numeric" });
const fmtTime = (iso) => fmt(iso, { hour: "numeric", minute: "2-digit" });
const localDate = (iso) => new Intl.DateTimeFormat("en-CA", { timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(iso));
const today = () => localDate(new Date().toISOString());
const tzLabel = () => { try { return new Intl.DateTimeFormat("en-US", { timeZone: TZ, timeZoneName: "long" }).formatToParts(new Date()).find(p => p.type === "timeZoneName").value; } catch { return TZ; } };
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
  return `<div class="brand"><div class="mark">DG</div><div><div class="host">Dylan Groenendijk</div><div class="co">DigiGrowth</div></div></div>
    <h1>${esc(ev ? ev.name : "Book a call")}</h1>
    ${ev ? `<div class="meta"><div>${ICON.clock}<span>${ev.duration_min} min</span></div><div>${ICON.video}<span>Google Meet (link in your invite)</span></div>${extra || ""}</div>
    ${ev.description ? `<p class="desc">${esc(ev.description)}</p>` : ""}` : ""}`;
}

// Month slot cache: "YYYY-MM" -> { "YYYY-MM-DD": [iso...] } in the visitor's timezone.
function slotLoader(fetchSlots) {
  const months = {};
  return async (ym) => {
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
}

function picker(root, load, onPick, note) {
  let ym = today().slice(0, 7), day = null, tries = 0;
  root.innerHTML = `${note ? `<p class="err" style="margin-top:0">${esc(note)}</p>` : ""}<div class="split"><div id="calwrap"><div class="skeleton"></div></div><div class="times" id="times"></div></div><div class="tz">Times shown in ${esc(tzLabel())}</div>`;
  async function render() {
    let map;
    try { map = await load(ym); } catch (e) { root.innerHTML = `<p class="err">${esc(e.message)}</p>`; return; }
    const open = Object.keys(map).filter((k) => map[k].length).sort();
    if (!day && !open.length && tries < 2) { tries++; ym = addMonth(ym, 1); return render(); }
    if (!day || !map[day]) day = open[0] || null;
    const [y, m] = ym.split("-").map(Number);
    const firstDow = (new Date(Date.UTC(y, m - 1, 1)).getUTCDay() + 6) % 7, n = new Date(Date.UTC(y, m, 0)).getUTCDate();
    let cells = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"].map((d) => `<div class="dow">${d}</div>`).join("");
    for (let i = 0; i < firstDow; i++) cells += "<div></div>";
    for (let d = 1; d <= n; d++) {
      const iso = `${ym}-${String(d).padStart(2, "0")}`, ok = (map[iso] || []).length > 0;
      cells += `<button class="day ${ok ? "open" : ""} ${iso === day ? "sel" : ""}" ${ok ? `data-d="${iso}"` : "disabled"}>${d}</button>`;
    }
    const label = new Date(Date.UTC(y, m - 1, 1)).toLocaleDateString("en-US", { month: "long", year: "numeric", timeZone: "UTC" });
    $("#calwrap").innerHTML = `<div class="calhead"><button class="navbtn" id="pm" ${ym > today().slice(0, 7) ? "" : "disabled"}>‹</button><b>${label}</b><button class="navbtn" id="nm">›</button></div><div class="cal">${cells}</div>`;
    $("#pm").onclick = () => { ym = addMonth(ym, -1); day = null; render(); };
    $("#nm").onclick = () => { ym = addMonth(ym, 1); day = null; render(); };
    $("#calwrap").querySelectorAll("[data-d]").forEach((b) => b.onclick = () => { day = b.dataset.d; render(); });
    const times = day ? map[day] : [];
    $("#times").innerHTML = times.length
      ? `<b>${esc(fmtDay(times[0]))}</b>` + times.map((s) => `<button class="t" data-s="${s}">${esc(fmtTime(s))}</button>`).join("")
      : `<p class="muted">No open times this month. Try the next one.</p>`;
    $("#times").querySelectorAll("[data-s]").forEach((b) => b.onclick = () => onPick(b.dataset.s));
  }
  render();
}

async function bookMode() {
  const info = await api("info");
  const want = qs.get("type");
  const shown = info.types.filter((t) => t.listed || t.slug === want);
  let ev = info.types.find((t) => t.slug === want) || (shown.length === 1 ? shown[0] : null);
  const UTM = { utm_source: qs.get("utm_source"), utm_content: qs.get("utm_content") };
  if (!info.types.length) { $("#info").innerHTML = infoPanel(null); $("#main").innerHTML = `<p class="muted">Booking isn't open right now.</p>`; return; }
  if (!ev) {
    $("#info").innerHTML = infoPanel(null);
    $("#main").innerHTML = `<h2>Pick a call</h2><div class="types">${shown.map((t) => `<button data-t="${t.id}"><span>${esc(t.name)}</span><span class="muted">${t.duration_min} min</span></button>`).join("")}</div>`;
    $("#main").querySelectorAll("[data-t]").forEach((b) => b.onclick = () => { ev = info.types.find((t) => t.id == b.dataset.t); start(); });
    return;
  }
  start();

  function start(note) {
    $("#info").innerHTML = infoPanel(ev);
    $("#main").innerHTML = `<h2>Pick a time</h2><div id="pick"></div>`;
    const load = slotLoader((s, d) => api(`slots?type_id=${ev.id}&start=${s}&days=${d}`).then((r) => r.slots));
    picker($("#pick"), load, details, note);
  }

  function details(slot) {
    $("#info").innerHTML = infoPanel(ev, `<div>${ICON.cal}<span>${esc(fmtDay(slot))}, ${esc(fmtTime(slot))}</span></div>`);
    $("#main").innerHTML = `<h2>Your details</h2>
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
          timezone: TZ, sms_consent: $("#c").checked, ...UTM });
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
    $("#main").innerHTML = `<div class="ok"><div class="tick">✓</div><h2>${fresh ? "You're booked!" : "Your call"}</h2>
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
    return _TEMPLATE.replace("__TITLE__", title).replace("__MODE__", '"book"' if mode == "book" else '"manage"')
