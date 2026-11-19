import React, { useEffect, useState } from "react";
import { API } from "../api.js";
import ContactLink from "../ContactLink.jsx";
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
            Each clinic's own booking page. Patients book on the link, it lands on the clinic's Google Calendar, and reminders and follow-ups run as usual.
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
