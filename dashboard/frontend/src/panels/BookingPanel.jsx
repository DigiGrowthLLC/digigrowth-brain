import React, { useEffect, useState } from "react";
import { API } from "../api.js";
import ContactLink from "../ContactLink.jsx";
import ClientBookingSetup from "./ClientBookingSetup.jsx";
import { T, Card, Toggle, Pill as UIPill } from "../ui.jsx";

// OS nav → Booking Links: DigiGrowth Booking (our own Calendly replacement,
// backend/booking_engine.py) across every client. Pick a client to open its
// full setup (calendar, hours, appointment types, Stripe, bookings).

const mono = { fontFamily: "'Share Tech Mono', monospace" };
const note = { fontSize: 11.5, color: "#6f88ad", lineHeight: 1.5 };

function Pill({ color, children }) {
  return (
    <span style={{ ...mono, fontSize: 9.5, letterSpacing: "0.08em", color, border: `1px solid ${color}55`, background: `${color}14`, borderRadius: 999, padding: "2px 8px", whiteSpace: "nowrap" }}>
      {children}
    </span>
  );
}

function statusOf(c) {
  if (c.enabled) return c.calendar_errors > 0 ? ["LIVE · CALENDAR ERROR", "#e05a5a"] : ["LIVE", "#14c882"];
  if (c.booking_slug) return c.missing.length ? ["SETTING UP", "#f0a028"] : ["READY, OFF", "#6ab0ff"];
  return ["NOT STARTED", "#5a7aa0"];
}

// Dylan's own booking page (backend/personal_booking.py), his Calendly
// replacement: booking.digigrowthllc.com/discovery-call.
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function PersonalBooking({ copy, copied }) {
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");
  const [editHours, setEditHours] = useState(false);
  const [hours, setHours] = useState({});
  const [saving, setSaving] = useState(false);

  const load = () => fetch(API("/personal-booking"))
    .then(async (r) => { if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || "Couldn't load your booking link"); return r.json(); })
    .then((x) => { setD(x); setHours(x.settings.hours); }).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, []);

  const send = async (path, method, body) => {
    setSaving(true); setErr("");
    const r = await fetch(API(path), { method, headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined });
    const x = await r.json().catch(() => ({}));
    setSaving(false);
    if (!r.ok) { setErr(x.detail || "Couldn't save"); return false; }
    setD(x); setHours(x.settings.hours); return true;
  };
  const setDay = (i, on, a, b) => setHours((h) => ({ ...h, [i]: on ? [[a || "08:00", b || "22:00"]] : [] }));

  const firstRange = d ? Object.values(d.settings.hours).find((x) => x.length) : null;
  const t12 = (hm) => { const [h, m] = hm.split(":").map(Number); return `${h % 12 || 12}${m ? `:${String(m).padStart(2, "0")}` : ""} ${h < 12 ? "AM" : "PM"}`; };
  const onDays = d ? DAYS.filter((_, i) => (d.settings.hours[i] || []).length) : [];
  const dayText = onDays.length === 7 ? "Every day" : onDays.join(", ") === "Mon, Tue, Wed, Thu, Fri" ? "Weekdays" : onDays.join(", ") || "No days";
  const smallBtn = { background: "none", border: `1px solid ${T.line}`, borderRadius: 8, color: T.textDim, cursor: "pointer", fontSize: 12, padding: "5px 10px", whiteSpace: "nowrap" };

  return (
    <Card style={{ marginBottom: 18 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <div>
          <div style={{ fontFamily: T.display, fontWeight: 600, fontSize: 16, color: T.text }}>Personal booking link</div>
          <div style={{ fontSize: 13, color: T.textMute, marginTop: 2 }}>Where prospects and clients book calls with you.</div>
        </div>
        {d && <UIPill tone={d.booked_30d ? "good" : "neutral"}>{d.booked_30d} booked in 30 days</UIPill>}
      </div>
      {err && <div style={{ color: T.bad, fontSize: 12, marginTop: 10 }}>{err}</div>}
      {!d && !err && <div style={{ ...note, marginTop: 10 }}>Loading…</div>}
      {d && (
        <>
          <div style={{ marginTop: 14, border: `1px solid ${T.line}`, borderRadius: 10 }}>
            {d.types.map((t, i) => (
              <div key={t.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 12px", borderTop: i ? `1px solid ${T.line}` : "none", flexWrap: "wrap" }}>
                <div style={{ flex: "1 1 180px", minWidth: 0, opacity: t.active ? 1 : 0.5 }}>
                  <a href={t.url} target="_blank" rel="noreferrer" style={{ fontSize: 14, fontWeight: 600, color: T.text, textDecoration: "none" }}>{t.name}</a>
                  <span style={{ fontSize: 12, color: T.textMute, marginLeft: 8 }}>{t.listed ? "Public" : "Clients only"}</span>
                </div>
                <select className="dg-input" value={t.duration_min} disabled={saving} title="Call length" style={{ width: 86, padding: "4px 6px", fontSize: 12 }}
                  onChange={(e) => send(`/personal-booking/types/${t.id}`, "PATCH", { duration_min: Number(e.target.value) })}>
                  {[15, 20, 30, 45, 60, 90].map((m) => <option key={m} value={m}>{m} min</option>)}
                </select>
                <button style={smallBtn} onClick={() => copy(t.url)}>{copied === t.url ? "Copied" : "Copy link"}</button>
                <Toggle on={t.active} busy={saving} onChange={(on) => send(`/personal-booking/types/${t.id}`, "PATCH", { active: on })} />
              </div>
            ))}
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, flexWrap: "wrap", marginTop: 12 }}>
            <div style={{ fontSize: 13, color: T.textDim }}>
              {dayText}{firstRange ? `, ${t12(firstRange[0][0])} to ${t12(firstRange[0][1])} ET` : ""}
              <span style={{ color: T.textMute }}> · {Math.round(d.settings.min_notice_min / 60)}h notice · skips anything on your calendars</span>
            </div>
            <button style={smallBtn} onClick={() => setEditHours((v) => !v)}>{editHours ? "Close" : "Edit hours"}</button>
          </div>
          {editHours && (
            <div style={{ marginTop: 10, display: "grid", gap: 6 }}>
              {DAYS.map((name, i) => {
                const r = (hours[i] || [])[0];
                return (
                  <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 13, color: T.textDim }}>
                    <label style={{ width: 70, display: "flex", gap: 6, alignItems: "center" }}>
                      <input type="checkbox" checked={!!r} onChange={(e) => setDay(i, e.target.checked)} />{name}
                    </label>
                    {r ? (
                      <>
                        <input type="time" className="dg-input" value={r[0]} onChange={(e) => setDay(i, true, e.target.value, r[1])} style={{ width: 130 }} />
                        <span style={note}>to</span>
                        <input type="time" className="dg-input" value={r[1]} onChange={(e) => setDay(i, true, r[0], e.target.value)} style={{ width: 130 }} />
                      </>
                    ) : <span style={note}>Off</span>}
                  </div>
                );
              })}
              <div>
                <button className="btn btn-primary" disabled={saving} onClick={async () => { if (await send("/personal-booking/settings", "PUT", { hours })) setEditHours(false); }}>
                  {saving ? "Saving…" : "Save hours"}
                </button>
              </div>
            </div>
          )}

          <div style={{ borderTop: `1px solid ${T.line}`, paddingTop: 12, marginTop: 14 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: T.text, marginBottom: 6 }}>Upcoming calls</div>
            {d.upcoming.length === 0 && <div style={{ fontSize: 13, color: T.textMute }}>None yet.</div>}
            {d.upcoming.map((b) => (
              <div key={b.id} style={{ display: "flex", gap: 12, alignItems: "center", padding: "6px 0", fontSize: 13, flexWrap: "wrap" }}>
                <div style={{ color: T.textDim, width: 160 }}>{new Date(b.start_at).toLocaleString("en-US", { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</div>
                <div style={{ flex: 1, color: T.text, minWidth: 180 }}><ContactLink phone={b.phone}>{b.name}</ContactLink> <span style={{ color: T.textMute }}>· {b.type_name}{b.business ? ` · ${b.business}` : ""}</span>{b.calendar_error && <UIPill tone="bad" style={{ marginLeft: 8 }}>Calendar error</UIPill>}</div>
                {b.meet_link && <a href={b.meet_link} target="_blank" rel="noreferrer" style={{ color: T.accent, fontSize: 12 }}>Meet</a>}
                <a href={b.manage_url} target="_blank" rel="noreferrer" style={{ color: T.accent, fontSize: 12 }}>Their page</a>
                <button style={smallBtn} disabled={saving}
                  onClick={() => window.confirm(`Cancel ${b.name}'s call? Their calendar invite is removed.`) && send(`/personal-booking/bookings/${b.id}/cancel`, "POST")}>Cancel</button>
              </div>
            ))}
          </div>
        </>
      )}
    </Card>
  );
}

export default function BookingPanel() {
  const [data, setData] = useState(null);
  const [google, setGoogle] = useState(null);
  const [err, setErr] = useState("");
  const [selected, setSelected] = useState(null);
  const [filter, setFilter] = useState("");
  const [copied, setCopied] = useState(null);

  const load = () => fetch(API("/booking/overview"))
    .then(async (r) => { if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || "Couldn't load bookings"); return r.json(); })
    .then(setData).catch((e) => setErr(e.message));

  useEffect(() => {
    load();
    fetch(API("/booking/google")).then((r) => r.json()).then(setGoogle).catch(() => setGoogle({ ok: false }));
  }, []);

  const copy = async (url) => {
    try { await navigator.clipboard.writeText(url); setCopied(url); setTimeout(() => setCopied(null), 1500); } catch {}
  };

  if (selected) {
    return (
      <div style={{ flex: 1, minHeight: 0, overflowY: "auto", padding: 24 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6, fontSize: 12.5 }}>
          <button onClick={() => { setSelected(null); load(); }}
            style={{ background: "none", border: "none", padding: 0, cursor: "pointer", color: "#6ab0ff", fontFamily: "inherit", fontSize: 12.5 }}>
            ← Booking Links
          </button>
          <span style={{ color: "#3a5a80" }}>/</span>
          <span style={{ color: "#8aaad0" }}>{selected.name}</span>
        </div>
        <h2 style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 24, fontWeight: 700, letterSpacing: "-0.02em", color: "#f0f4ff", margin: "0 0 16px" }}>{selected.name}</h2>
        <ClientBookingSetup clientId={selected.id} />
      </div>
    );
  }

  const clients = (data?.clients || []).filter((c) => c.name.toLowerCase().includes(filter.toLowerCase()));
  const live = (data?.clients || []).filter((c) => c.enabled).length;
  const upcomingTotal = (data?.clients || []).reduce((n, c) => n + Number(c.upcoming || 0), 0);
  const booked30 = (data?.clients || []).reduce((n, c) => n + Number(c.booked_30d || 0), 0);

  return (
    <div style={{ flex: 1, minHeight: 0, overflowY: "auto", padding: 24 }}>
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 12, flexWrap: "wrap", marginBottom: 18 }}>
        <div>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 24, fontWeight: 700, color: "#f0f4ff", letterSpacing: "-0.02em" }}>Booking Links</div>
          <div style={{ ...note, marginTop: 4, maxWidth: 620 }}>
            Your own booking link, plus each clinic's booking page. Patients book on the link, it lands on the clinic's Google Calendar, and reminders and follow-ups run as usual.
          </div>
        </div>
        <div title="Clinics share their Google Calendar with this account (Make changes to events)"
          style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "6px 12px", borderRadius: 999, fontSize: 11.5,
            border: `1px solid ${google && !google.ok ? "rgba(224,90,90,0.4)" : "rgba(58,123,213,0.25)"}`, background: "rgba(58,123,213,0.08)", color: "#9cc4f5" }}>
          <span style={{ width: 7, height: 7, borderRadius: "50%", background: google ? (google.ok ? "#14c882" : "#e05a5a") : "#5a7aa0" }} />
          Calendars shared with {google ? (google.ok ? google.account : "(Google not reachable)") : "…"}
        </div>
      </div>

      {err && <div style={{ color: "#ff8a8a", fontSize: 12, marginBottom: 12 }}>{err}</div>}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 12, marginBottom: 18 }}>
        {[["Live links", live, "#14c882"], ["Upcoming bookings", upcomingTotal, "#6ab0ff"], ["Booked (30 days)", booked30, "#a080f0"]].map(([k, v, c]) => (
          <div key={k} className="stat-card" style={{ padding: "14px 18px", borderLeft: `3px solid ${c}`, display: "block" }}>
            <div style={{ ...mono, fontSize: 10, color: "#5a7aa0", letterSpacing: "0.1em", textTransform: "uppercase" }}>{k}</div>
            <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 28, fontWeight: 700, color: "#f0f4ff", marginTop: 4 }}>{data ? v : "—"}</div>
          </div>
        ))}
      </div>

      <PersonalBooking copy={copy} copied={copied} />

      <div className="glass-card" style={{ padding: 16, marginBottom: 18 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10, gap: 10 }}>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600, color: "#d0e8ff" }}>Clients</div>
          <input className="dg-input" placeholder="Search clients…" value={filter} onChange={(e) => setFilter(e.target.value)} style={{ maxWidth: 240 }} />
        </div>
        {!data && !err && <div style={note}>Loading…</div>}
        {clients.map((c) => {
          const [label, color] = statusOf(c);
          return (
            <div key={c.id} style={{ display: "flex", alignItems: "center", gap: 14, padding: "12px 6px", borderTop: "1px solid rgba(58,123,213,0.1)", flexWrap: "wrap" }}>
              <div style={{ width: 36, height: 36, borderRadius: 10, flexShrink: 0, display: "grid", placeItems: "center",
                fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: 15, color: "#fff",
                background: `linear-gradient(135deg, ${color}, rgba(40,87,160,0.9))` }}>{c.name.trim().charAt(0)}</div>
              <div style={{ flex: "1 1 220px", minWidth: 0 }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: "#e8f0ff" }}>{c.name}{c.status !== "active" && <span style={{ ...note, marginLeft: 6 }}>({c.status})</span>}</div>
                <div style={{ ...note, marginTop: 2 }}>
                  {c.public_url ? (
                    <>
                      <a href={c.public_url} target="_blank" rel="noreferrer" style={{ color: "#6ab0ff" }}>{c.public_url.replace(/^https?:\/\//, "")}</a>
                      <button onClick={() => copy(c.public_url)} style={{ background: "none", border: "none", color: "#5a7aa0", cursor: "pointer", fontSize: 11, marginLeft: 6 }}>{copied === c.public_url ? "copied" : "copy"}</button>
                    </>
                  ) : "No booking link yet"}
                </div>
              </div>
              <Pill color={color}>{label}</Pill>
              <button className={c.booking_slug ? "btn btn-secondary" : "btn btn-primary"} onClick={() => setSelected(c)}>
                {c.booking_slug ? "Manage" : "Set up"}
              </button>
            </div>
          );
        })}
        {data && clients.length === 0 && <div style={note}>No clients match.</div>}
      </div>

      <div className="glass-card" style={{ padding: 16 }}>
        <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600, color: "#d0e8ff", marginBottom: 10 }}>Next bookings (all clients)</div>
        {data && data.upcoming.length === 0 && <div style={note}>Nothing booked yet.</div>}
        {(data?.upcoming || []).map((b) => (
          <div key={b.id} style={{ display: "flex", gap: 12, alignItems: "center", padding: "7px 0", borderTop: "1px solid rgba(58,123,213,0.08)", fontSize: 12, flexWrap: "wrap" }}>
            <div style={{ ...mono, color: "#9cc4f5", width: 170 }}>{new Date(b.start_at).toLocaleString("en-US", { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</div>
            <div style={{ flex: 1, color: "#d0e8ff", minWidth: 180 }}><ContactLink phone={b.phone} clientId={b.client_id}>{b.name}</ContactLink> <span style={note}>· {b.event_name} · {b.client_name}{b.paid_at ? ` · paid $${(b.price_cents / 100).toFixed(0)}` : ""}</span></div>
            <a href={b.manage_url} target="_blank" rel="noreferrer" style={{ color: "#6ab0ff", fontSize: 11 }}>Patient page</a>
          </div>
        ))}
        <div style={{ ...note, marginTop: 8 }}>Times shown in your computer's timezone.</div>
      </div>
    </div>
  );
}
