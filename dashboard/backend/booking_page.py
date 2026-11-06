"""The patient-facing booking page + manage page (one self-contained HTML
document, vanilla JS). Served by routers/booking.py at /book/<slug>,
/lp/<landing slug>/book (funnels) and /booking/<token> (manage). All API
calls are relative to the page's own path, so it works unchanged behind the
client-funnels Vercel proxy on a clinic's own domain."""
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
  :root{ --accent:__ACCENT__; --ink:#1d2433; --soft:#5b6478; --line:#e4e8f0; --bg:#f6f8fb; --ok:#11845b; --bad:#c2410c; }
  *{ box-sizing:border-box; }
  body{ margin:0; background:var(--bg); color:var(--ink); font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }
  .wrap{ max-width:560px; margin:0 auto; padding:28px 16px 64px; }
  .clinic{ font-size:13px; font-weight:600; color:var(--soft); letter-spacing:.02em; margin-bottom:6px; }
  h1{ font-size:24px; line-height:1.25; margin:0 0 10px; }
  .meta{ display:flex; flex-wrap:wrap; gap:6px 16px; color:var(--soft); font-size:14px; margin-bottom:6px; }
  .price{ font-weight:700; color:var(--ink); }
  .price .was{ color:var(--soft); font-weight:400; margin-left:6px; }
  .scarcity{ display:inline-block; margin-top:6px; font-size:12.5px; font-weight:600; color:var(--bad); background:#fff1ea; border-radius:999px; padding:3px 10px; }
  .desc{ color:var(--soft); font-size:14px; margin:10px 0 0; white-space:pre-wrap; }
  .card{ background:#fff; border:1px solid var(--line); border-radius:14px; padding:18px; margin-top:18px; box-shadow:0 1px 2px rgba(16,24,40,.04); }
  .step{ font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:.06em; color:var(--soft); margin:0 0 12px; }
  .daysbar{ display:flex; align-items:center; gap:8px; }
  .days{ display:flex; gap:8px; overflow-x:auto; scrollbar-width:none; flex:1; padding:2px; }
  .days::-webkit-scrollbar{ display:none; }
  .day{ flex:0 0 64px; border:1px solid var(--line); background:#fff; border-radius:12px; padding:8px 4px; text-align:center; cursor:pointer; font:inherit; color:var(--ink); }
  .day small{ display:block; font-size:11px; color:var(--soft); text-transform:uppercase; letter-spacing:.04em; }
  .day b{ display:block; font-size:18px; }
  .day[disabled]{ opacity:.35; cursor:default; }
  .day.on{ border-color:var(--accent); background:var(--accent); color:#fff; }
  .day.on small{ color:rgba(255,255,255,.85); }
  .arrow{ border:1px solid var(--line); background:#fff; border-radius:10px; width:34px; height:34px; cursor:pointer; font-size:16px; color:var(--soft); flex:0 0 auto; }
  .times{ display:grid; grid-template-columns:repeat(auto-fill,minmax(100px,1fr)); gap:8px; margin-top:14px; }
  .time{ border:1px solid var(--accent); color:var(--accent); background:#fff; border-radius:10px; padding:10px 6px; font:inherit; font-weight:600; cursor:pointer; }
  .time.on{ background:var(--accent); color:#fff; }
  .tz{ font-size:12px; color:var(--soft); margin-top:12px; }
  .empty{ color:var(--soft); font-size:14px; padding:6px 0; }
  label{ display:block; font-size:13px; font-weight:600; margin:12px 0 5px; }
  input,textarea{ width:100%; font:inherit; padding:11px 12px; border:1px solid #cfd6e3; border-radius:10px; background:#fff; color:var(--ink); }
  input:focus,textarea:focus{ outline:2px solid var(--accent); outline-offset:0; border-color:var(--accent); }
  .btn{ display:block; width:100%; margin-top:16px; border:0; border-radius:12px; padding:14px; font:inherit; font-weight:700; font-size:16px; background:var(--accent); color:#fff; cursor:pointer; text-align:center; text-decoration:none; }
  .btn[disabled]{ opacity:.6; cursor:default; }
  .btn.ghost{ background:#fff; color:var(--ink); border:1px solid var(--line); }
  .btn.danger{ background:#fff; color:var(--bad); border:1px solid #f3c7b2; }
  .row{ display:flex; gap:10px; }
  .row .btn{ flex:1; }
  .chosen{ font-weight:600; }
  .err{ color:var(--bad); font-size:14px; margin-top:10px; }
  .ok{ text-align:center; }
  .ok .tick{ width:56px; height:56px; border-radius:50%; background:#e7f6ef; color:var(--ok); display:flex; align-items:center; justify-content:center; font-size:28px; margin:4px auto 10px; }
  .muted{ color:var(--soft); font-size:14px; }
  .link{ background:none; border:0; color:var(--accent); font:inherit; cursor:pointer; padding:0; text-decoration:underline; }
  .hidden{ display:none !important; }
  footer{ text-align:center; color:#9aa3b5; font-size:12px; margin-top:28px; }
</style>
</head>
<body>
<div class="wrap" id="app">
  <div class="clinic" id="clinic">__CLINIC__</div>
  <div id="loading" class="muted">Loading...</div>
</div>
<script>
const MODE = __MODE__;
const BASE = location.pathname.replace(/\/+$/, "");
const qs = new URLSearchParams(location.search);
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
let TZ = "UTC";
const fmt = (iso, opts) => new Intl.DateTimeFormat("en-US", { timeZone: TZ, ...opts }).format(new Date(iso));
const fmtDay = (iso) => fmt(iso, { weekday: "long", month: "long", day: "numeric" });
const fmtTime = (iso) => fmt(iso, { hour: "numeric", minute: "2-digit" });
const tzLabel = () => { try { return new Intl.DateTimeFormat("en-US", { timeZone: TZ, timeZoneName: "long" }).formatToParts(new Date()).find(p => p.type === "timeZoneName").value; } catch { return TZ; } };
const money = (c) => "$" + (c / 100).toFixed(c % 100 ? 2 : 0);

async function api(path, opts) {
  const r = await fetch(BASE + "/api/" + path, { headers: { "Content-Type": "application/json" }, ...opts });
  let body = null; try { body = await r.json(); } catch {}
  if (!r.ok) throw new Error((body && body.detail) || "Something went wrong. Please try again.");
  return body;
}

function eventHeader(ev, clinic) {
  const loc = ev.location_type === "google_meet" ? "Video call" : ev.location_type === "phone" ? "Phone call" : (ev.location_text || "In person");
  const price = ev.price_cents > 0
    ? `<span class="price">${money(ev.price_cents)}${ev.anchor_price_cents > ev.price_cents ? `<span class="was">normally <s>${money(ev.anchor_price_cents)}</s></span>` : ""}</span>`
    : (ev.anchor_price_cents ? `<span class="price">Free<span class="was">normally <s>${money(ev.anchor_price_cents)}</s></span></span>` : "");
  return `<h1>${esc(ev.name)}</h1>
    <div class="meta"><span>${ev.duration_min} min</span><span>${esc(loc)}</span>${price}</div>
    ${ev.spots_per_month ? `<span class="scarcity">Only ${ev.spots_per_month} spots per month</span>` : ""}
    ${ev.description ? `<p class="desc">${esc(ev.description)}</p>` : ""}`;
}

// ── Slot picker (shared by booking + reschedule) ──
function slotPicker(container, fetchSlots, onPick) {
  let start = null, data = null, day = null;
  container.innerHTML = `<div class="daysbar"><button class="arrow" data-a="prev" aria-label="Earlier dates">&#8249;</button><div class="days"></div><button class="arrow" data-a="next" aria-label="Later dates">&#8250;</button></div>
    <div class="times"></div><div class="tz"></div>`;
  const daysEl = container.querySelector(".days"), timesEl = container.querySelector(".times");
  container.querySelector(".tz").textContent = "Times shown in " + tzLabel();
  async function load(from) {
    daysEl.innerHTML = `<div class="empty">Loading times...</div>`; timesEl.innerHTML = "";
    try { data = await fetchSlots(from); } catch (e) { daysEl.innerHTML = `<div class="err">${esc(e.message)}</div>`; return; }
    start = data.days.length ? data.days[0].date : from;
    const first = data.days.find(d => d.slots.length);
    day = first ? first.date : null;
    render();
  }
  function render() {
    if (!data.days.length) { daysEl.innerHTML = `<div class="empty">No more dates available.</div>`; return; }
    daysEl.innerHTML = data.days.map(d => {
      const dt = new Date(d.date + "T12:00:00Z");
      const wd = dt.toLocaleDateString("en-US", { weekday: "short", timeZone: "UTC" });
      const md = dt.toLocaleDateString("en-US", { month: "short", timeZone: "UTC" });
      return `<button class="day ${d.date === day ? "on" : ""}" data-d="${d.date}" ${d.slots.length ? "" : "disabled"}><small>${wd}</small><b>${dt.getUTCDate()}</b><small>${md}</small></button>`;
    }).join("");
    const cur = data.days.find(d => d.date === day);
    timesEl.innerHTML = !cur ? `<div class="empty">No openings in these dates. Try the next ones.</div>`
      : cur.slots.map(s => `<button class="time" data-s="${s}">${fmtTime(s)}</button>`).join("");
  }
  container.addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    if (b.dataset.d) { day = b.dataset.d; render(); }
    else if (b.dataset.s) { timesEl.querySelectorAll(".time").forEach(t => t.classList.toggle("on", t === b)); onPick(b.dataset.s); }
    else if (b.dataset.a === "next" && data && data.days.length) {
      const last = data.days[data.days.length - 1].date; const n = new Date(last + "T12:00:00Z"); n.setUTCDate(n.getUTCDate() + 1);
      load(n.toISOString().slice(0, 10));
    } else if (b.dataset.a === "prev" && start) {
      const p = new Date(start + "T12:00:00Z"); p.setUTCDate(p.getUTCDate() - 14); load(p.toISOString().slice(0, 10));
    }
  });
  load(null);
}

// ── Booking mode ──
async function bookMode() {
  const info = await api("info");
  TZ = info.timezone;
  const app = $("#app");
  $("#loading").remove();
  if (!info.event_types.length) { app.insertAdjacentHTML("beforeend", `<p class="muted">Online booking isn't available right now. Please call the clinic.</p>`); return; }
  const wanted = qs.get("type");
  let ev = info.event_types.find(e => e.slug === wanted) || (info.event_types.length === 1 ? info.event_types[0] : null);
  if (qs.get("cancelled")) { api("release", { method: "POST", body: JSON.stringify({ token: qs.get("cancelled") }) }).catch(() => {}); }
  if (!ev) {
    app.insertAdjacentHTML("beforeend", `<h1>Book an appointment</h1><div class="card"><div class="step">Choose a visit</div>${info.event_types.map(e =>
      `<button class="btn ghost" data-ev="${e.id}" style="text-align:left">${esc(e.name)} <span class="muted">· ${e.duration_min} min${e.price_cents ? " · " + money(e.price_cents) : ""}</span></button>`).join("")}</div>`);
    app.addEventListener("click", (e) => { const b = e.target.closest("[data-ev]"); if (b) { app.querySelectorAll("h1,.card").forEach(n => n.remove()); renderBook(info.event_types.find(x => x.id == b.dataset.ev)); } }, { once: false });
    return;
  }
  renderBook(ev);

  function renderBook(ev) {
    app.insertAdjacentHTML("beforeend", `${eventHeader(ev, info.clinic)}
      <div class="card" id="pick"><div class="step">1. Pick a time</div><div id="picker"></div></div>
      <div class="card hidden" id="form"><div class="step">2. Your details</div>
        <div class="chosen" id="chosen"></div>
        <label for="n">Full name</label><input id="n" autocomplete="name" required>
        <label for="p">Mobile phone</label><input id="p" type="tel" autocomplete="tel" required>
        <label for="m">Email</label><input id="m" type="email" autocomplete="email" required>
        ${ev.ask_question ? `<label for="q">${esc(ev.ask_question)}</label><textarea id="q" rows="3"></textarea>` : ""}
        <button class="btn" id="go">${ev.price_cents > 0 ? "Continue to payment" : "Confirm booking"}</button>
        <div class="err" id="err"></div>
        ${ev.price_cents > 0 ? `<p class="muted" style="margin-top:10px">Secure payment by Stripe. Your time is held for 30 minutes while you pay.</p>` : ""}
      </div>`);
    let chosen = null;
    slotPicker($("#picker"), (from) => api(`slots?event_type_id=${ev.id}${from ? "&start=" + from : ""}`), (s) => {
      chosen = s; $("#form").classList.remove("hidden");
      $("#chosen").textContent = fmtDay(s) + " at " + fmtTime(s);
      $("#form").scrollIntoView({ behavior: "smooth", block: "start" });
    });
    $("#go").addEventListener("click", async () => {
      const btn = $("#go"); $("#err").textContent = "";
      const body = { event_type_id: ev.id, start: chosen, name: $("#n").value, phone: $("#p").value, email: $("#m").value,
        answer: $("#q") ? $("#q").value : null,
        utm_source: qs.get("utm_source") || (location.pathname.startsWith("/lp/") ? "paid_ad" : null),
        utm_content: qs.get("utm_content") };
      btn.disabled = true; btn.textContent = "One moment...";
      try {
        const r = await api("reserve", { method: "POST", body: JSON.stringify(body) });
        if (r.checkout_url) { location.href = r.checkout_url; return; }
        location.href = r.manage_url + "?new=1";
      } catch (e) {
        $("#err").textContent = e.message; btn.disabled = false;
        btn.textContent = ev.price_cents > 0 ? "Continue to payment" : "Confirm booking";
      }
    });
  }
}

// ── Manage mode ──
async function manageMode() {
  let info = await api("info");
  TZ = info.timezone;
  $("#loading").remove();
  const app = $("#app");
  let polls = 0;
  function render() {
    app.querySelectorAll(".view").forEach(n => n.remove());
    const when = `${fmtDay(info.start)} at ${fmtTime(info.start)}`;
    let top = "";
    if (info.status === "pending_payment" && qs.get("paid") && polls < 15) {
      top = `<div class="card ok view"><p class="muted">Confirming your payment...</p></div>`;
      setTimeout(async () => { polls++; info = await api("info"); render(); }, 2000);
      app.insertAdjacentHTML("beforeend", top); return;
    }
    if (info.status === "confirmed") {
      const fresh = qs.get("new") || qs.get("paid");
      top = `<div class="card ok view"><div class="tick">&#10003;</div>
        <h1>${fresh ? "You're booked!" : "Your appointment"}</h1>
        <p><b>${esc(info.event.name)}</b><br>${when}<br><span class="muted">${esc(info.event.location_type === "in_person" ? (info.event.location_text || "") : info.event.location_type === "phone" ? "We'll call you" : "")}</span></p>
        ${info.meet_link ? `<a class="btn" href="${esc(info.meet_link)}" target="_blank" rel="noopener">Join video call</a>` : ""}
        ${info.paid ? `<p class="muted">Paid online. Thank you.</p>` : ""}
        <a class="btn ghost" href="${esc(info.add_to_calendar)}" target="_blank" rel="noopener">Add to my Google Calendar</a>
        ${fresh ? `<p class="muted">We texted you a confirmation with this page's link.</p>` : ""}
      </div>`;
      if (info.can_change) top += `<div class="card view" id="change">
          <div class="row"><button class="btn ghost" id="rs">Reschedule</button><button class="btn danger" id="cx">Cancel</button></div>
          <div id="area"></div></div>`;
    } else if (info.status === "cancelled") {
      top = `<div class="card ok view"><h1>This appointment was cancelled</h1><p class="muted">${esc(info.cancel_reason || "")}</p>
        ${info.refunded ? `<p class="muted">Your payment has been refunded. It can take 5 to 10 days to show on your statement.</p>` : ""}</div>`;
    } else if (info.status === "pending_payment") {
      top = `<div class="card ok view"><h1>Still confirming your payment</h1><p class="muted">This can take a minute. Refresh this page shortly. You'll also get a text once it's confirmed.</p></div>`;
    } else {
      top = `<div class="card ok view"><h1>This booking wasn't completed</h1><p class="muted">The payment wasn't finished, so the time was released.</p></div>`;
    }
    app.insertAdjacentHTML("beforeend", top);
    const rs = $("#rs"), cx = $("#cx");
    if (rs) rs.onclick = () => {
      $("#area").innerHTML = `<div class="step" style="margin-top:16px">Pick a new time</div><div id="picker"></div><div class="err" id="err"></div><button class="btn hidden" id="save"></button>`;
      let chosen = null;
      slotPicker($("#picker"), (from) => api(`slots${from ? "?start=" + from : ""}`), (s) => {
        chosen = s; const b = $("#save"); b.classList.remove("hidden"); b.textContent = "Move to " + fmtDay(s) + " at " + fmtTime(s);
      });
      $("#save").onclick = async () => {
        $("#save").disabled = true; $("#err").textContent = "";
        try { info = await api("reschedule", { method: "POST", body: JSON.stringify({ start: chosen }) }); qs.delete("new"); qs.delete("paid"); render(); }
        catch (e) { $("#err").textContent = e.message; $("#save").disabled = false; }
      };
    };
    if (cx) cx.onclick = () => {
      const refund = info.paid ? (info.refund_policy === "always" ? "Your payment will be refunded."
        : info.refund_policy === "24h" ? "Payments are refunded when you cancel at least 24 hours ahead." : "Payments aren't refundable.") : "";
      $("#area").innerHTML = `<p style="margin-top:16px">Cancel your appointment on ${when}? ${refund}</p>
        <label for="why">Anything we should know? (optional)</label><textarea id="why" rows="2"></textarea>
        <div class="row"><button class="btn ghost" id="keep">Keep it</button><button class="btn danger" id="yes">Yes, cancel</button></div><div class="err" id="err"></div>`;
      $("#keep").onclick = () => { $("#area").innerHTML = ""; };
      $("#yes").onclick = async () => {
        $("#yes").disabled = true;
        try { info = await api("cancel", { method: "POST", body: JSON.stringify({ reason: $("#why").value }) }); render(); }
        catch (e) { $("#err").textContent = e.message; $("#yes").disabled = false; }
      };
    };
  }
  render();
}

(MODE === "book" ? bookMode : manageMode)().catch((e) => {
  const l = $("#loading"); if (l) l.outerHTML = `<p class="err">${esc(e.message)}</p>`;
});
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
