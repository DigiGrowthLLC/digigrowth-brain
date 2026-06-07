import React, { useState, useEffect, useRef } from "react";

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

const TERM_PRESETS = ["python run.py", "git status", "pip install -r requirements.txt", "python -c \"import dialer; print('ok')\""];

export default function DialerPanel() {
  const [data, setData] = useState(null);
  const [termOpen, setTermOpen]       = useState(false);
  const [termCmd, setTermCmd]         = useState("");
  const [termOutput, setTermOutput]   = useState("");
  const [termRunning, setTermRunning] = useState(false);
  const termBottomRef = useRef(null);

  const load = async () => {
    try {
      const r = await fetch(API("/dialer/stats"));
      if (r.ok) setData(await r.json());
    } catch {}
  };

  useEffect(() => { load(); const id = setInterval(load, 5000); return () => clearInterval(id); }, []);

  useEffect(() => { termBottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [termOutput]);

  const runCommand = async (cmd) => {
    const c = (cmd || termCmd).trim();
    if (!c || termRunning) return;
    setTermOutput(prev => prev + `\n$ ${c}\n`);
    setTermRunning(true);
    try {
      const resp = await fetch(API("/dialer/exec"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command: c }),
      });
      if (!resp.ok) { setTermOutput(prev => prev + `[HTTP ${resp.status}]\n`); return; }
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n"); buf = lines.pop();
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          let evt; try { evt = JSON.parse(line.slice(6)); } catch { continue; }
          if (evt.type === "output") setTermOutput(prev => prev + evt.text);
          else if (evt.type === "done") setTermOutput(prev => prev + (evt.code ? `[exit ${evt.code}]\n` : ""));
          else if (evt.type === "error") setTermOutput(prev => prev + `[error: ${evt.message}]\n`);
        }
      }
    } catch (e) {
      setTermOutput(prev => prev + `[fetch error: ${e.message}]\n`);
    } finally {
      setTermRunning(false);
    }
  };

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
            use the terminal below or run{" "}
          </span>
          <code style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 11, color: "#3a7bd5" }}>
            python run.py
          </code>
          <span style={{ fontSize: 12, color: "#5a6f8f" }}>
            {" "}from parallel-dialer/.
          </span>
        </div>
      )}

      {/* Terminal */}
      <div className="glass-card" style={{ padding: 0, overflow: "hidden" }}>
        {/* Terminal header */}
        <div
          onClick={() => setTermOpen(o => !o)}
          style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            padding: "10px 16px", cursor: "pointer",
            borderBottom: termOpen ? "1px solid rgba(58,123,213,0.1)" : "none",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a7bd5", letterSpacing: "0.14em" }}>
              TERMINAL
            </span>
            <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a3a50" }}>
              parallel-dialer/
            </span>
          </div>
          <span style={{ fontSize: 10, color: "#2a4a7a" }}>{termOpen ? "▲" : "▼"}</span>
        </div>

        {termOpen && (
          <div style={{ padding: "12px 14px", display: "flex", flexDirection: "column", gap: 10 }}>
            {/* Preset chips */}
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {TERM_PRESETS.map(p => (
                <button
                  key={p}
                  onClick={() => { setTermCmd(p); runCommand(p); }}
                  disabled={termRunning}
                  style={{
                    fontFamily: "'Share Tech Mono', monospace", fontSize: 9,
                    padding: "4px 10px", borderRadius: 6,
                    background: "rgba(58,123,213,0.08)",
                    border: "1px solid rgba(58,123,213,0.2)",
                    color: "#3a7bd5", cursor: termRunning ? "not-allowed" : "pointer",
                    opacity: termRunning ? 0.5 : 1,
                    letterSpacing: "0.05em",
                  }}
                >
                  {p}
                </button>
              ))}
            </div>

            {/* Output */}
            {termOutput && (
              <div style={{
                background: "#050d1a", borderRadius: 8, padding: "10px 12px",
                maxHeight: 280, overflowY: "auto",
                fontFamily: "'Share Tech Mono', monospace", fontSize: 11,
                color: "#7aaad0", whiteSpace: "pre-wrap", wordBreak: "break-all",
                border: "1px solid rgba(58,123,213,0.1)",
              }}>
                {termOutput}
                <div ref={termBottomRef} />
              </div>
            )}

            {/* Command input */}
            <div style={{ display: "flex", gap: 8 }}>
              <input
                className="dg-input"
                style={{ flex: 1, fontFamily: "'Share Tech Mono', monospace", fontSize: 12 }}
                placeholder="enter command..."
                value={termCmd}
                onChange={e => setTermCmd(e.target.value)}
                onKeyDown={e => e.key === "Enter" && runCommand()}
                disabled={termRunning}
              />
              <button
                className="btn btn-primary"
                onClick={() => runCommand()}
                disabled={termRunning || !termCmd.trim()}
                style={{ minWidth: 60, fontSize: 11 }}
              >
                {termRunning ? "…" : "RUN"}
              </button>
              <button
                className="btn btn-secondary"
                onClick={() => setTermOutput("")}
                style={{ fontSize: 11 }}
              >
                CLR
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
