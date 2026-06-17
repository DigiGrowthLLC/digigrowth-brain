import React, { useState, useEffect, useRef, useCallback } from "react";

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

const DISPO_BUTTONS = [
  { label: "Appointment Booked", emoji: "✅", style: { background: "rgba(20,200,130,0.12)", border: "1px solid rgba(20,200,130,0.3)", color: "#14c882" } },
  { label: "Follow Up",          emoji: "📞", style: { background: "rgba(58,123,213,0.12)", border: "1px solid rgba(58,123,213,0.3)", color: "#5a9bf0" } },
  { label: "Send Info",          emoji: "📧", style: { background: "rgba(120,80,210,0.12)", border: "1px solid rgba(120,80,210,0.3)", color: "#a080f0" } },
  { label: "Not Interested",     emoji: "🚫", style: { background: "rgba(220,60,60,0.12)",  border: "1px solid rgba(220,60,60,0.3)",  color: "#dc3c3c" } },
  { label: "No Answer",          emoji: "—",  style: { background: "rgba(30,47,80,0.4)",    border: "1px solid #1a2540",              color: "#3a5a80" } },
  { label: "Voicemail",          emoji: "📬", style: { background: "rgba(240,160,40,0.12)", border: "1px solid rgba(240,160,40,0.3)", color: "#f0a028" } },
];

const GRADE_COLORS = { A: "#14c882", B: "#5a9bf0", C: "#f0a028", D: "#dc3c3c" };
const CALENDLY_URL = "https://calendly.com/dylanrg-digigrowthllc/30min";

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

function escHtml(str) {
  return (str || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

function fillScriptText(template, lead) {
  let text = escHtml(template);
  text = text.replace(/\[Name\]/gi,          `<span style="color:#14c882;font-weight:700">${escHtml(lead.owner    || "")}</span>`);
  text = text.replace(/\[Practice Name\]/gi, `<span style="color:#14c882;font-weight:700">${escHtml(lead.business || "")}</span>`);
  text = text.replace(/\[Studio Name\]/gi,   `<span style="color:#14c882;font-weight:700">${escHtml(lead.business || "")}</span>`);
  text = text.replace(/\[custom opener\]/gi, `<span style="color:#5a9bf0;font-weight:700">${escHtml(lead.opener   || "")}</span>`);
  text = text.replace(/\n/g, "<br>");
  return text;
}

const TERM_PRESETS = ["python run.py newsletter", "ls -la", "pip list | grep twilio"];

export default function DialerPanel() {
  const [stats, setStats]       = useState(null);
  const [sess, setSess]         = useState(null);
  const [sessionActive, setSessionActive] = useState(false);
  const [leadCount, setLeadCount]         = useState(null);
  const [initiating, setInitiating]       = useState(false);
  const [deviceReady, setDeviceReady]     = useState(false);
  const [connecting, setConnecting]       = useState(false);
  const [ending, setEnding]               = useState(false);
  const [notes, setNotes]                 = useState("");
  const [classifying, setClassifying]     = useState(false);
  const [bookingOpen, setBookingOpen]     = useState(false);
  // Script
  const [scriptTemplate, setScriptTemplate] = useState("");
  const [filledScript, setFilledScript]     = useState("");
  const [scriptFilled, setScriptFilled]     = useState(false);
  // Dial feedback
  const [dialMsg, setDialMsg] = useState("");
  const prevStatusRef = useRef(null);
  // Terminal
  const [termOpen, setTermOpen]       = useState(false);
  const [termCmd, setTermCmd]         = useState("");
  const [termOutput, setTermOutput]   = useState("");
  const [termRunning, setTermRunning] = useState(false);
  const termBottomRef = useRef(null);
  const deviceRef     = useRef(null);
  const activeCallRef = useRef(null);

  // ── Stats poll (5s) ─────────────────────────────────────────────────────────
  const loadStats = useCallback(async () => {
    try {
      const r = await fetch(API("/dialer/stats"));
      if (r.ok) setStats(await r.json());
    } catch {}
  }, []);

  useEffect(() => {
    loadStats();
    const id = setInterval(loadStats, 5000);
    return () => clearInterval(id);
  }, [loadStats]);

  // ── Session poll (1s while active) ──────────────────────────────────────────
  useEffect(() => {
    if (!sessionActive) return;
    const id = setInterval(async () => {
      try {
        const r = await fetch(API("/dialer/session"));
        if (!r.ok) return;
        const data = await r.json();
        setSess(data);
        if (!data.active) { setSessionActive(false); setDeviceReady(false); }
      } catch {}
    }, 1000);
    return () => clearInterval(id);
  }, [sessionActive]);

  // ── Auto-dial next batch + script fill/clear on status transitions ──────────
  useEffect(() => {
    if (!sess) return;
    const prev = prevStatusRef.current;
    prevStatusRef.current = sess.status;

    // After classify → waiting: fire next batch
    if (prev === "classify" && sess.status === "waiting" && !sess.end_requested) {
      setDialMsg("");
      fetch(API("/dialer/dial-batch"), { method: "POST" })
        .then(r => r.json())
        .then(d => {
          if (d.errors && d.errors.length > 0) setDialMsg(`Twilio error: ${d.errors[0]}`);
          else if (d.done && d.dialed === 0)   setDialMsg("No more leads in queue.");
          else if (d.dialed === 0)             setDialMsg("0 calls placed — check Railway logs.");
          else                                 setDialMsg(`Dialing ${d.dialed} lead${d.dialed > 1 ? "s" : ""}…`);
        })
        .catch(() => {});
    }

    // Lead connected: fill script
    if (sess.status === "connected" && sess.current_lead && !scriptFilled) {
      if (scriptTemplate.trim()) {
        setFilledScript(fillScriptText(scriptTemplate, sess.current_lead));
        setScriptFilled(true);
      }
    }

    // Back to waiting/idle: clear filled script
    if (sess.status === "waiting") {
      setScriptFilled(false);
      setFilledScript("");
    }
  }, [sess?.status, sess?.current_lead]);

  useEffect(() => { termBottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [termOutput]);

  // ── Start Session ────────────────────────────────────────────────────────────
  const startSession = async () => {
    setInitiating(true);
    setLeadCount(null);
    setDialMsg("");
    try {
      const r = await fetch(API("/dialer/session/init"), { method: "POST" });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || "Init failed");
      setLeadCount(d.lead_count);
      setSessionActive(true);
      prevStatusRef.current = null;
      const s = await fetch(API("/dialer/session"));
      if (s.ok) setSess(await s.json());
    } catch (e) {
      alert("Could not start session: " + e.message);
    } finally {
      setInitiating(false);
    }
  };

  // ── Connect Twilio Device ────────────────────────────────────────────────────
  const connectDevice = async () => {
    if (!window.Twilio?.Device) {
      alert("Twilio SDK not loaded — reload the page and try again.");
      return;
    }
    setConnecting(true);
    try {
      const tr = await fetch(API("/dialer/token"));
      const td = await tr.json();
      if (td.detail || td.error) throw new Error(td.detail || td.error);

      const device = new window.Twilio.Device(td.token, { logLevel: "error" });
      await device.register();
      deviceRef.current = device;

      const session_id = sess?.session_id || "";
      const call = await device.connect({ params: { session_id } });
      activeCallRef.current = call;

      call.on("accept", () => {
        setDeviceReady(true);
        setConnecting(false);
        setDialMsg("Dialing first batch…");
        fetch(API("/dialer/dial-batch"), { method: "POST" })
          .then(r => r.json())
          .then(d => {
            if (d.errors && d.errors.length > 0)
              setDialMsg(`Twilio error: ${d.errors[0]}`);
            else if (d.done && d.dialed === 0)
              setDialMsg("No leads with status 'dialer-lead' — update lead statuses in CRM first.");
            else if (d.dialed === 0)
              setDialMsg("0 calls placed — check Railway logs for Twilio errors.");
            else
              setDialMsg(`Dialing ${d.dialed} lead${d.dialed > 1 ? "s" : ""}…`);
          })
          .catch(() => {});
      });
      call.on("disconnect", () => setDeviceReady(false));
      call.on("error", (e) => { setConnecting(false); alert("Twilio error: " + e.message); });
    } catch (e) {
      setConnecting(false);
      alert("Connect failed: " + e.message);
    }
  };

  const disconnectDevice = () => {
    try { activeCallRef.current?.disconnect(); } catch {}
    try { deviceRef.current?.destroy(); } catch {}
    deviceRef.current = null;
    activeCallRef.current = null;
    setDeviceReady(false);
  };

  // ── Call actions ──────────────────────────────────────────────────────────────
  const endCall = () => fetch(API("/dialer/end-call"), { method: "POST" }).catch(() => {});

  const classify = async (disposition) => {
    setClassifying(true);
    try {
      await fetch(API("/dialer/classify"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ disposition, notes }),
      });
      setNotes("");
      if (disposition === "Appointment Booked") setBookingOpen(true);
    } catch {}
    setClassifying(false);
  };

  const connectGK = () => fetch(API("/dialer/gatekeeper/connect"), { method: "POST" }).catch(() => {});
  const declineGK = () => fetch(API("/dialer/gatekeeper/decline"), { method: "POST" }).catch(() => {});

  const endSession = async () => {
    setEnding(true);
    try {
      await fetch(API("/dialer/end-session"), { method: "POST" });
    } catch {}
    disconnectDevice();
    setSessionActive(false);
    setSess(null);
    setLeadCount(null);
    setDialMsg("");
    setScriptFilled(false);
    setFilledScript("");
    prevStatusRef.current = null;
    setEnding(false);
    loadStats();
  };

  // ── Terminal ──────────────────────────────────────────────────────────────────
  const runCommand = async (cmd) => {
    const c = (cmd || termCmd).trim();
    if (!c || termRunning) return;
    setTermOutput(prev => prev + `\n$ ${c}\n`);
    setTermRunning(true);
    try {
      const resp = await fetch(API("/dialer/exec"), {
        method: "POST", headers: { "Content-Type": "application/json" },
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
    } finally { setTermRunning(false); }
  };

  // ── Derived ───────────────────────────────────────────────────────────────────
  const session    = stats?.session ?? {};
  const history    = stats?.history ?? {};
  const recent     = history.recent ?? [];
  const byDispo    = history.by_disposition ?? [];
  const totalCalls = history.total_calls ?? 0;

  const liveStatus  = sess?.status ?? "idle";
  const currentLead = sess?.current_lead ?? null;
  const gatekeeper  = sess?.gatekeeper ?? null;
  const liveStats   = sess?.stats ?? {};

  const statusDot = liveStatus === "connected" ? "#14c882"
                  : liveStatus === "classify"  ? "#3a7bd5"
                  : liveStatus === "waiting"   ? "#f0a028"
                  : "#3a5a80";

  const statusLabel = liveStatus === "connected" ? "LIVE CALL"
                    : liveStatus === "classify"  ? "CLASSIFY"
                    : liveStatus === "waiting"   ? "DIALING…"
                    : "IDLE";

  return (
    <div style={{ flex: 1, overflowY: "auto", padding: 24, display: "flex", flexDirection: "column", gap: 24 }}>

      {/* ── Header ── */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 18, fontWeight: 700, color: "#f0f4ff" }}>
            Parallel Dialer
          </div>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80", letterSpacing: "0.18em", marginTop: 3 }}>
            {sessionActive ? (liveStatus === "connected" ? "SESSION · LIVE CALL" : "SESSION · ACTIVE") : "SESSION · IDLE"}
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{
            width: 8, height: 8, borderRadius: "50%",
            background: sessionActive ? "#14c882" : "#1a2f52",
            boxShadow: sessionActive ? "0 0 6px #14c882" : "none",
          }} />
          <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10,
                          color: sessionActive ? "#14c882" : "#2a4a7a", letterSpacing: "0.1em" }}>
            {sessionActive ? "ACTIVE" : "IDLE"}
          </span>
        </div>
      </div>

      {/* ── Calling Interface ── */}
      <div className="glass-card" style={{ padding: 20, display: "flex", flexDirection: "column", gap: 16 }}>

        {!sessionActive ? (
          /* Idle */
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12, padding: "8px 0" }}>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80", letterSpacing: "0.14em" }}>
              {session.leads_ready > 0 ? `${session.leads_ready} LEADS READY TO DIAL` : "NO LEADS WITH STATUS DIALER-LEAD"}
            </div>
            {session.leads_ready === 0 && (
              <div style={{ fontSize: 11, color: "#5a6f8f", textAlign: "center", maxWidth: 320 }}>
                Go to CRM → select your leads → set status to <strong style={{ color: "#5a9bf0" }}>Dialer Lead</strong> to queue them.
              </div>
            )}
            <button
              className="btn btn-primary"
              style={{ fontSize: 13, padding: "10px 32px", minWidth: 160 }}
              onClick={startSession}
              disabled={initiating}
            >
              {initiating ? "Loading Leads…" : "Start Session"}
            </button>
          </div>
        ) : (
          /* Active session */
          <>
            {/* Top bar: status + controls */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <div style={{
                  width: 8, height: 8, borderRadius: "50%", flexShrink: 0,
                  background: statusDot,
                  boxShadow: liveStatus === "connected" || liveStatus === "waiting" ? `0 0 6px ${statusDot}` : "none",
                }} />
                <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#8aaad0", letterSpacing: "0.1em" }}>
                  {statusLabel}
                </span>
                {leadCount !== null && (
                  <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9,
                                  color: leadCount === 0 ? "#dc3c3c" : "#3a5a80",
                                  background: leadCount === 0 ? "rgba(220,60,60,0.1)" : "rgba(30,47,80,0.4)",
                                  border: `1px solid ${leadCount === 0 ? "rgba(220,60,60,0.2)" : "#1a2540"}`,
                                  borderRadius: 4, padding: "2px 6px" }}>
                    {leadCount} LEADS
                  </span>
                )}
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <select
                  style={{
                    background: "rgba(30,47,80,0.6)", border: "1px solid #1a2540",
                    borderRadius: 6, color: "#8aaad0",
                    fontFamily: "'Share Tech Mono', monospace", fontSize: 10,
                    padding: "4px 8px", cursor: "pointer",
                  }}
                  defaultValue="10"
                  onChange={(e) => fetch(API("/dialer/set-lines"), {
                    method: "POST", headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ lines: parseInt(e.target.value) }),
                  }).catch(() => {})}
                >
                  {[1, 3, 5, 10].map(n => <option key={n} value={n}>{n} Lines</option>)}
                </select>

                {!deviceReady ? (
                  <button className="btn btn-primary" style={{ fontSize: 11, padding: "6px 16px" }}
                    onClick={connectDevice} disabled={connecting || leadCount === 0}>
                    {connecting ? "Connecting…" : "Connect"}
                  </button>
                ) : (
                  <button className="btn btn-secondary"
                    style={{ fontSize: 11, padding: "6px 16px", color: "#dc3c3c", borderColor: "rgba(220,60,60,0.3)" }}
                    onClick={disconnectDevice}>
                    Disconnect
                  </button>
                )}

                <button
                  className="btn btn-secondary"
                  style={{ fontSize: 11, padding: "6px 16px", color: "#dc3c3c", borderColor: "rgba(220,60,60,0.3)",
                           opacity: ending ? 0.5 : 1 }}
                  onClick={endSession}
                  disabled={ending}
                >
                  {ending ? "Ending…" : "End Session"}
                </button>
              </div>
            </div>

            {/* No leads warning */}
            {leadCount === 0 && (
              <div style={{
                background: "rgba(220,60,60,0.08)", border: "1px solid rgba(220,60,60,0.2)",
                borderRadius: 8, padding: "10px 14px",
                fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#dc3c3c",
                letterSpacing: "0.08em",
              }}>
                0 LEADS LOADED — go to CRM and set lead statuses to "Dialer Lead"
              </div>
            )}

            {/* Dial status message */}
            {dialMsg && (
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10,
                             color: "#3a5a80", letterSpacing: "0.08em" }}>
                {dialMsg}
              </div>
            )}

            {/* Live mini-stats */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8 }}>
              {[
                { label: "Calls", value: liveStats.calls_made ?? 0 },
                { label: "DMs",   value: liveStats.dms_reached ?? 0 },
                { label: "Left",  value: liveStats.remaining ?? "—" },
                { label: "Total", value: liveStats.total ?? "—" },
              ].map(({ label, value }) => (
                <div key={label} style={{
                  background: "rgba(15,25,50,0.5)", borderRadius: 8, padding: "8px 10px",
                  border: "1px solid #1a2540", textAlign: "center",
                }}>
                  <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 18, fontWeight: 700, color: "#f0f4ff" }}>
                    {value}
                  </div>
                  <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80", letterSpacing: "0.12em", marginTop: 2 }}>
                    {label}
                  </div>
                </div>
              ))}
            </div>

            {/* Lead Card */}
            {currentLead && (liveStatus === "connected" || liveStatus === "classify") && (
              <div style={{
                background: "rgba(15,25,50,0.6)", borderRadius: 10, padding: "14px 16px",
                border: "1px solid rgba(58,123,213,0.2)", display: "flex", flexDirection: "column", gap: 8,
              }}>
                <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8 }}>
                  <div>
                    <div style={{ fontSize: 16, fontWeight: 700, color: "#f0f4ff" }}>
                      {currentLead.owner || "—"}
                    </div>
                    <div style={{ fontSize: 12, color: "#5a6f8f", marginTop: 2 }}>{currentLead.business || "—"}</div>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    {currentLead.grade && (
                      <span style={{
                        fontFamily: "'Share Tech Mono', monospace", fontSize: 11, fontWeight: 700,
                        padding: "2px 8px", borderRadius: 20,
                        color: GRADE_COLORS[currentLead.grade] || "#8aaad0",
                        background: "rgba(30,47,80,0.6)",
                        border: `1px solid ${GRADE_COLORS[currentLead.grade] || "#1a2540"}33`,
                      }}>{currentLead.grade}</span>
                    )}
                    {currentLead.gatekeeper && (
                      <span style={{
                        fontFamily: "'Share Tech Mono', monospace", fontSize: 9,
                        padding: "2px 8px", borderRadius: 20,
                        background: "rgba(240,100,20,0.1)", color: "#f0a028",
                        border: "1px solid rgba(240,100,20,0.3)",
                      }}>GATEKEEPER</span>
                    )}
                  </div>
                </div>
                {currentLead.opener && (
                  <div style={{ fontSize: 12, color: "#5a9bf0", fontStyle: "italic",
                                 borderTop: "1px solid #1a2540", paddingTop: 8 }}>
                    {currentLead.opener}
                  </div>
                )}
                <div style={{ display: "flex", gap: 12 }}>
                  {currentLead.phone && (
                    <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80" }}>
                      {currentLead.phone}
                    </span>
                  )}
                  {currentLead.city && (
                    <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80" }}>
                      {[currentLead.city, currentLead.state].filter(Boolean).join(", ")}
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* End Call */}
            {liveStatus === "connected" && (
              <div style={{ display: "flex", justifyContent: "center" }}>
                <button onClick={endCall} style={{
                  background: "rgba(220,60,60,0.12)", border: "1px solid rgba(220,60,60,0.3)",
                  color: "#dc3c3c", borderRadius: 6, padding: "10px 32px",
                  fontSize: 13, fontWeight: 600, cursor: "pointer",
                }}>
                  End Call
                </button>
              </div>
            )}

            {/* Script section */}
            <div>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                <div className="sec-label" style={{ marginBottom: 0 }}>Call Script</div>
                {scriptFilled && (
                  <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9,
                                  color: "#14c882", letterSpacing: "0.1em" }}>
                    FILLED ·{" "}
                    <span style={{ color: "#14c882" }}>[Name]</span>{" "}
                    <span style={{ color: "#5a9bf0" }}>[opener]</span>
                  </span>
                )}
                {!scriptFilled && (
                  <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a3a50" }}>
                    [Name] [Practice Name] [custom opener]
                  </span>
                )}
              </div>

              {scriptFilled ? (
                <div
                  dangerouslySetInnerHTML={{ __html: filledScript }}
                  style={{
                    background: "#050d1a", borderRadius: 8, padding: "12px 14px",
                    minHeight: 120, maxHeight: 260, overflowY: "auto",
                    fontFamily: "'Space Grotesk', sans-serif", fontSize: 13,
                    color: "#a0b8d0", lineHeight: 1.75, whiteSpace: "pre-wrap",
                    border: "1px solid rgba(58,123,213,0.15)",
                  }}
                />
              ) : (
                <textarea
                  className="dg-input"
                  placeholder={"Paste your call script here.\nUse [Name], [Practice Name], and [custom opener] as placeholders — they'll fill in automatically when a lead answers."}
                  value={scriptTemplate}
                  onChange={(e) => setScriptTemplate(e.target.value)}
                  rows={6}
                  style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 13, resize: "vertical", lineHeight: 1.7 }}
                />
              )}
            </div>

            {/* Classification panel */}
            {liveStatus === "classify" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <div className="sec-label" style={{ marginBottom: 0 }}>Disposition</div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
                  {DISPO_BUTTONS.map(({ label, emoji, style }) => (
                    <button key={label} disabled={classifying} onClick={() => classify(label)} style={{
                      ...style, borderRadius: 6, padding: "10px 8px",
                      fontSize: 12, fontWeight: 600, cursor: classifying ? "not-allowed" : "pointer",
                      opacity: classifying ? 0.5 : 1,
                      fontFamily: "'Space Grotesk', sans-serif",
                    }}>
                      {emoji} {label}
                    </button>
                  ))}
                </div>
                <textarea
                  className="dg-input"
                  placeholder="Call notes (optional)…"
                  rows={2}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, resize: "none" }}
                />
              </div>
            )}

            {/* Waiting indicator */}
            {liveStatus === "waiting" && deviceReady && !dialMsg && (
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80", letterSpacing: "0.1em" }}>
                DIALING IN BACKGROUND — WAITING FOR ANSWER…
              </div>
            )}

            {!deviceReady && leadCount > 0 && (
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a", letterSpacing: "0.1em" }}>
                CLICK CONNECT TO JOIN THE CONFERENCE AND START DIALING
              </div>
            )}
          </>
        )}

        {/* Gatekeeper popup */}
        {gatekeeper && (
          <div style={{
            position: "fixed", bottom: 88, right: 24,
            background: "#0d1830", border: "1px solid rgba(240,120,20,0.4)",
            borderRadius: 12, padding: "18px 20px", width: 260,
            boxShadow: "0 8px 32px rgba(0,0,0,0.6)", zIndex: 500,
          }}>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: 22, marginBottom: 4 }}>🤖</div>
              <div style={{ fontSize: 13, fontWeight: 700, color: "#fed7aa", marginBottom: 2 }}>Gatekeeper Detected</div>
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#5a6f8f", marginBottom: 14,
                             overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {gatekeeper.business || gatekeeper.owner || gatekeeper.phone || "Automated system"}
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <button onClick={connectGK} style={{
                  flex: 1, padding: "8px 0", borderRadius: 6, fontSize: 12, fontWeight: 700,
                  background: "rgba(240,120,20,0.2)", color: "#fed7aa",
                  border: "1px solid rgba(240,120,20,0.4)", cursor: "pointer",
                }}>Connect</button>
                <button onClick={declineGK} style={{
                  flex: 1, padding: "8px 0", borderRadius: 6, fontSize: 12, fontWeight: 700,
                  background: "rgba(30,47,80,0.4)", color: "#5a6f8f",
                  border: "1px solid #1a2540", cursor: "pointer",
                }}>Decline</button>
              </div>
            </div>
          </div>
        )}

        {/* Booking modal */}
        {bookingOpen && (
          <div onClick={(e) => e.target === e.currentTarget && setBookingOpen(false)} style={{
            position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)",
            display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000, padding: 24,
          }}>
            <div style={{
              background: "#0d1830", border: "1px solid #1a2540", borderRadius: 12,
              width: "100%", maxWidth: 860, height: "85vh",
              display: "flex", flexDirection: "column", overflow: "hidden",
              boxShadow: "0 24px 64px rgba(0,0,0,0.6)",
            }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between",
                             padding: "14px 20px", borderBottom: "1px solid #1a2540", flexShrink: 0 }}>
                <span style={{ fontSize: 14, fontWeight: 700, color: "#f0f4ff" }}>Book Appointment</span>
                <button onClick={() => setBookingOpen(false)} style={{
                  background: "rgba(30,47,80,0.5)", border: "1px solid #1a2540",
                  borderRadius: 6, color: "#5a6f8f", width: 30, height: 30, cursor: "pointer", fontSize: 16,
                }}>✕</button>
              </div>
              <div style={{ flex: 1, overflow: "hidden" }}>
                <iframe src={CALENDLY_URL} style={{ width: "100%", height: "100%", border: "none" }} allow="camera; microphone" />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── Live Session Stats ── */}
      <div>
        <div className="sec-label">{session.active ? "Live Session" : "Last Session"}</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 8 }}>
          <StatCard label="Calls Made"    value={session.calls_made} />
          <StatCard label="DMs Reached"   value={session.dms_reached} />
          <StatCard label="Remaining"     value={session.remaining}
            sub={session.total_leads ? `OF ${session.total_leads}` : null} />
          <StatCard label="Reach Rate"    value={session.calls_made > 0 ? `${session.reach_rate}%` : "—"} />
          <StatCard label="Ready to Dial" value={session.leads_ready ?? "—"}
            sub={session.leads_ready > 0 ? "IN QUEUE" : null} />
        </div>
      </div>

      <div className="dg-divider" />

      {/* ── Historical ── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>

        <div className="glass-card" style={{ padding: 16 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
            <div className="sec-label" style={{ marginBottom: 0 }}>All-Time Breakdown</div>
            <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>
              {totalCalls} CALLS
            </span>
          </div>
          {byDispo.length === 0 ? (
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52", letterSpacing: "0.1em" }}>NO DATA YET</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {byDispo.map(d => {
                const pct    = totalCalls ? Math.round(d.cnt / totalCalls * 100) : 0;
                const colors = DISPO_COLORS[d.disposition] ?? { text: "#5a6f8f" };
                return (
                  <div key={d.disposition}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                      <span style={{ fontSize: 12, color: colors.text }}>{d.disposition}</span>
                      <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80" }}>
                        {d.cnt} ({pct}%)
                      </span>
                    </div>
                    <div style={{ height: 2, background: "#111e36", borderRadius: 1 }}>
                      <div style={{ height: 2, borderRadius: 1, width: `${pct}%`, background: colors.text, opacity: 0.6 }} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
          <div style={{ marginTop: 14, paddingTop: 12, borderTop: "0.5px solid #1a2540", display: "flex", gap: 16 }}>
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

        <div className="glass-card" style={{ padding: 16 }}>
          <div className="sec-label">Recent Calls</div>
          {recent.length === 0 ? (
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52", letterSpacing: "0.1em" }}>NO CALLS LOGGED</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 1, overflowY: "auto", maxHeight: 280 }}>
              {recent.map((r, i) => {
                const colors = DISPO_COLORS[r.disposition] ?? { text: "#3a4f6f" };
                return (
                  <div key={i} style={{ display: "flex", alignItems: "center", justifyContent: "space-between",
                                         padding: "8px 0", borderBottom: "0.5px solid #1a2540" }}>
                    <div>
                      <div style={{ fontSize: 12, fontWeight: 500, color: "#8aaad0" }}>
                        {r.business || r.owner || r.phone || "Unknown"}
                      </div>
                      <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a4a7a", marginTop: 2 }}>
                        {fmt(r.started_at)}
                      </div>
                    </div>
                    <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, fontWeight: 600,
                                    letterSpacing: "0.08em", color: colors.text }}>
                      {(r.disposition ?? "—").toUpperCase()}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* ── Terminal ── */}
      <div className="glass-card" style={{ padding: 0, overflow: "hidden" }}>
        <div onClick={() => setTermOpen(o => !o)} style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "10px 16px", cursor: "pointer",
          borderBottom: termOpen ? "1px solid rgba(58,123,213,0.1)" : "none",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a7bd5", letterSpacing: "0.14em" }}>TERMINAL</span>
            <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a3a50" }}>parallel-dialer/</span>
          </div>
          <span style={{ fontSize: 10, color: "#2a4a7a" }}>{termOpen ? "▲" : "▼"}</span>
        </div>
        {termOpen && (
          <div style={{ padding: "12px 14px", display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {TERM_PRESETS.map(p => (
                <button key={p} onClick={() => { setTermCmd(p); runCommand(p); }} disabled={termRunning} style={{
                  fontFamily: "'Share Tech Mono', monospace", fontSize: 9, padding: "4px 10px", borderRadius: 6,
                  background: "rgba(58,123,213,0.08)", border: "1px solid rgba(58,123,213,0.2)",
                  color: "#3a7bd5", cursor: termRunning ? "not-allowed" : "pointer",
                  opacity: termRunning ? 0.5 : 1, letterSpacing: "0.05em",
                }}>{p}</button>
              ))}
            </div>
            {termOutput && (
              <div style={{
                background: "#050d1a", borderRadius: 8, padding: "10px 12px",
                maxHeight: 280, overflowY: "auto",
                fontFamily: "'Share Tech Mono', monospace", fontSize: 11,
                color: "#7aaad0", whiteSpace: "pre-wrap", wordBreak: "break-all",
                border: "1px solid rgba(58,123,213,0.1)",
              }}>
                {termOutput}<div ref={termBottomRef} />
              </div>
            )}
            <div style={{ display: "flex", gap: 8 }}>
              <input className="dg-input" style={{ flex: 1, fontFamily: "'Share Tech Mono', monospace", fontSize: 12 }}
                placeholder="enter command..." value={termCmd}
                onChange={e => setTermCmd(e.target.value)}
                onKeyDown={e => e.key === "Enter" && runCommand()} disabled={termRunning} />
              <button className="btn btn-primary" onClick={() => runCommand()}
                disabled={termRunning || !termCmd.trim()} style={{ minWidth: 60, fontSize: 11 }}>
                {termRunning ? "…" : "RUN"}
              </button>
              <button className="btn btn-secondary" onClick={() => setTermOutput("")} style={{ fontSize: 11 }}>CLR</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
