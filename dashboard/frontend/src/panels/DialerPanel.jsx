import React, { useState, useEffect } from "react";

const API = (p) => `/api${p}`;

const DISPO_COLORS = {
  "Appointment Booked": { text: "#14c882", bg: "rgba(20,200,130,0.08)", border: "rgba(20,200,130,0.2)" },
  "Follow Up":          { text: "#5a9bf0", bg: "rgba(58,123,213,0.08)", border: "rgba(58,123,213,0.2)" },
  "Send Info":          { text: "#a080f0", bg: "rgba(120,80,210,0.08)", border: "rgba(120,80,210,0.2)" },
  "Not Interested":     { text: "#dc3c3c", bg: "rgba(220,60,60,0.08)",  border: "rgba(220,60,60,0.2)"  },
  "No Answer":          { text: "#3a4f6f", bg: "transparent",           border: "#1a2540"               },
  "Voicemail":          { text: "#f0a028", bg: "rgba(240,160,40,0.08)", border: "rgba(240,160,40,0.2)" },
  "SMS Handoff":        { text: "#a080f0", bg: "rgba(120,80,210,0.08)", border: "rgba(120,80,210,0.2)" },
};

function StatCard({ label, value, sub }) {
  return (
    <div className="stat-card">
      <div className="stat-card-label">{label}</div>
      <div className="stat-card-value">{value ?? "—"}</div>
      {sub && <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80", marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

function fmt(ts) {
  if (!ts) return "";
  return new Date(ts).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

export default function DialerPanel() {
  const [data, setData] = useState(null);

  const load = async () => {
    try {
      const r = await fetch(API("/dialer/stats"));
      if (r.ok) setData(await r.json());
    } catch {}
  };

  useEffect(() => { load(); const id = setInterval(load, 5000); return () => clearInterval(id); }, []);

  const session = data?.session  ?? {};
  const history = data?.history  ?? {};
  const recent  = history.recent ?? [];
  const byDispo = history.by_disposition ?? [];
  const totalCalls = history.total_calls ?? 0;

  return (
    <div style={{ flex: 1, overflowY: "auto", padding: 24, display: "flex", flexDirection: "column", gap: 24 }}>

      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 18, fontWeight: 700, color: "#f0f4ff" }}>
            Parallel Dialer
          </div>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80",
                        letterSpacing: "0.18em", marginTop: 3 }}>
            {session.active ? "SESSION · LIVE" : "SESSION · IDLE"}
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{
            width: 8, height: 8, borderRadius: "50%",
            background: session.active ? "#14c882" : "#1a2f52",
            boxShadow: session.active ? "0 0 6px #14c882" : "none",
          }} />
          <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10,
                          color: session.active ? "#14c882" : "#2a4a7a", letterSpacing: "0.1em" }}>
            {session.active ? "ACTIVE" : "IDLE"}
          </span>
        </div>
      </div>

      {/* Live Session Stats */}
      <div>
        <div className="sec-label">{session.active ? "Live Session" : "Last Session"}</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8 }}>
          <StatCard label="Calls Made"  value={session.calls_made} />
          <StatCard label="DMs Reached" value={session.dms_reached} />
          <StatCard label="Remaining"   value={session.remaining}
            sub={session.total_leads ? `OF ${session.total_leads}` : null} />
          <StatCard label="Reach Rate"  value={session.calls_made > 0 ? `${session.reach_rate}%` : "—"} />
        </div>
      </div>

      <div className="dg-divider" />

      {/* Historical */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>

        {/* Disposition breakdown */}
        <div className="glass-card" style={{ padding: 16 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
            <div className="sec-label" style={{ marginBottom: 0 }}>All-Time Breakdown</div>
            <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>
              {totalCalls} CALLS
            </span>
          </div>
          {byDispo.length === 0 ? (
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52", letterSpacing: "0.1em" }}>
              NO DATA YET
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {byDispo.map(d => {
                const pct = totalCalls ? Math.round(d.cnt / totalCalls * 100) : 0;
                const colors = DISPO_COLORS[d.disposition] ?? { text: "#5a6f8f", bg: "transparent", border: "#1a2540" };
                return (
                  <div key={d.disposition}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                      <span style={{ fontSize: 12, color: colors.text }}>{d.disposition}</span>
                      <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80" }}>
                        {d.cnt} ({pct}%)
                      </span>
                    </div>
                    <div style={{ height: 2, background: "#111e36", borderRadius: 1 }}>
                      <div style={{ height: 2, borderRadius: 1, width: `${pct}%`,
                                    background: colors.text, opacity: 0.6 }} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
          <div style={{ marginTop: 14, paddingTop: 12, borderTop: "0.5px solid #1a2540",
                        display: "flex", gap: 16 }}>
            <div>
              <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a4a7a", letterSpacing: "0.1em" }}>BOOKED </span>
              <span style={{ fontSize: 14, fontWeight: 700, color: "#14c882" }}>{history.total_booked ?? 0}</span>
            </div>
            <div>
              <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a4a7a", letterSpacing: "0.1em" }}>REACHED </span>
              <span style={{ fontSize: 14, fontWeight: 700, color: "#5a9bf0" }}>{history.total_reached ?? 0}</span>
            </div>
          </div>
        </div>

        {/* Recent calls */}
        <div className="glass-card" style={{ padding: 16 }}>
          <div className="sec-label">Recent Calls</div>
          {recent.length === 0 ? (
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52", letterSpacing: "0.1em" }}>
              NO CALLS LOGGED
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 1, overflowY: "auto", maxHeight: 280 }}>
              {recent.map((r, i) => {
                const colors = DISPO_COLORS[r.disposition] ?? { text: "#3a4f6f", bg: "transparent", border: "#1a2540" };
                return (
                  <div key={i} style={{
                    display: "flex", alignItems: "center", justifyContent: "space-between",
                    padding: "8px 0", borderBottom: "0.5px solid #1a2540",
                  }}>
                    <div>
                      <div style={{ fontSize: 12, fontWeight: 500, color: "#8aaad0" }}>
                        {r.business || r.owner || r.phone || "Unknown"}
                      </div>
                      <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a4a7a", marginTop: 2 }}>
                        {fmt(r.started_at)}
                      </div>
                    </div>
                    <span style={{
                      fontFamily: "'Share Tech Mono', monospace", fontSize: 9, fontWeight: 600,
                      letterSpacing: "0.08em", color: colors.text,
                    }}>
                      {(r.disposition ?? "—").toUpperCase()}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Idle hint */}
      {!session.active && (
        <div className="glass-card-sm" style={{ padding: "12px 16px" }}>
          <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a7bd5", letterSpacing: "0.1em" }}>
            START SESSION:{" "}
          </span>
          <span style={{ fontSize: 12, color: "#5a6f8f" }}>
            cd parallel-dialer/ and run{" "}
          </span>
          <code style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 11, color: "#3a7bd5" }}>
            python run.py
          </code>
          <span style={{ fontSize: 12, color: "#5a6f8f" }}>
            {" "}— live stats update here automatically.
          </span>
        </div>
      )}
    </div>
  );
}
