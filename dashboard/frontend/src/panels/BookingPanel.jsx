import React, { useEffect, useState } from "react";
import { API } from "../api.js";
import ClientBookingSetup from "./ClientBookingSetup.jsx";

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
        <button className="btn btn-secondary" onClick={() => { setSelected(null); load(); }} style={{ marginBottom: 14 }}>← All booking links</button>
        <div className="sec-label">Booking Links</div>
        <h2 style={{ fontFamily: "'Space Grotesk', sans-serif", color: "#e8f0ff", margin: "4px 0 14px" }}>{selected.name}</h2>
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
      <div className="sec-label">Booking Links</div>
      <h2 style={{ fontFamily: "'Space Grotesk', sans-serif", color: "#e8f0ff", margin: "4px 0 6px" }}>DigiGrowth Booking</h2>
      <div style={{ ...note, marginBottom: 16 }}>
        Our own booking pages for each clinic, replacing Calendly. Clinics share their Google Calendar with{" "}
        <b style={{ color: "#d0e8ff" }}>{google ? (google.ok ? google.account : "— Google not reachable —") : "…"}</b>{" "}
        ("Make changes to events"); patients book on the link, it lands on their calendar, and your reminders and follow-ups run as usual.
      </div>

      {err && <div style={{ color: "#ff8a8a", fontSize: 12, marginBottom: 12 }}>{err}</div>}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 12, marginBottom: 18 }}>
        {[["Live links", live], ["Upcoming bookings", upcomingTotal], ["Booked (30 days)", booked30]].map(([k, v]) => (
          <div key={k} className="stat-card" style={{ padding: 14 }}>
            <div style={{ ...mono, fontSize: 10, color: "#5a7aa0", letterSpacing: "0.1em", textTransform: "uppercase" }}>{k}</div>
            <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 26, fontWeight: 700, color: "#e8f0ff" }}>{data ? v : "—"}</div>
          </div>
        ))}
      </div>

      <div className="glass-card" style={{ padding: 16, marginBottom: 18 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10, gap: 10 }}>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600, color: "#d0e8ff" }}>Clients</div>
          <input className="dg-input" placeholder="Search clients…" value={filter} onChange={(e) => setFilter(e.target.value)} style={{ maxWidth: 240 }} />
        </div>
        {!data && !err && <div style={note}>Loading…</div>}
        {clients.map((c) => {
          const [label, color] = statusOf(c);
          return (
            <div key={c.id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 4px", borderTop: "1px solid rgba(58,123,213,0.1)", flexWrap: "wrap" }}>
              <div style={{ flex: "1 1 220px", minWidth: 0 }}>
                <div style={{ fontSize: 13.5, fontWeight: 600, color: "#d0e8ff" }}>{c.name}{c.status !== "active" && <span style={{ ...note, marginLeft: 6 }}>({c.status})</span>}</div>
                <div style={note}>
                  {c.public_url ? (
                    <>
                      <a href={c.public_url} target="_blank" rel="noreferrer" style={{ color: "#6ab0ff" }}>{c.public_url.replace(/^https?:\/\//, "")}</a>
                      <button onClick={() => copy(c.public_url)} style={{ background: "none", border: "none", color: "#5a7aa0", cursor: "pointer", fontSize: 11, marginLeft: 6 }}>{copied === c.public_url ? "copied" : "copy"}</button>
                    </>
                  ) : "No booking link yet"}
                  {c.missing.length > 0 && <span style={{ color: "#f0a028" }}> · needs: {c.missing.join(", ")}</span>}
                </div>
              </div>
              <div style={{ ...note, width: 170 }}>
                {c.upcoming} upcoming · {c.booked_30d} in 30d
                {c.funnel && c.funnel.view > 0 && (
                  <div title="Booking page visits in the last 30 days, and the share that booked">
                    {c.funnel.view} visits · <b style={{ color: "#14c882" }}>{Math.round(((c.funnel.booked || 0) / c.funnel.view) * 100)}% booked</b>
                  </div>
                )}
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
            <div style={{ flex: 1, color: "#d0e8ff", minWidth: 180 }}>{b.name} <span style={note}>· {b.event_name} · {b.client_name}{b.paid_at ? ` · paid $${(b.price_cents / 100).toFixed(0)}` : ""}</span></div>
            <a href={b.manage_url} target="_blank" rel="noreferrer" style={{ color: "#6ab0ff", fontSize: 11 }}>Patient page</a>
          </div>
        ))}
        <div style={{ ...note, marginTop: 8 }}>Times shown in your computer's timezone.</div>
      </div>
    </div>
  );
}
