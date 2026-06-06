import React, { useState, useEffect, useRef } from "react";

const API = (p) => `/api${p}`;

function timeAgo(ts) {
  if (!ts) return "";
  const d = new Date(ts), now = new Date(), diff = now - d;
  if (diff < 60000) return "just now";
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

const AGENT_ICONS = { leadgen: "SCR", dialer: "DLR", sms: "SMS", system: "SYS" };

// ── Stat Card ─────────────────────────────────────────────────────────────────

function StatCard({ label, value, delta }) {
  return (
    <div className="stat-card">
      <div className="stat-card-label">{label}</div>
      <div className="stat-card-value">{value ?? "—"}</div>
      {delta && <div className="stat-card-delta">{delta}</div>}
    </div>
  );
}

// ── To-Do List ────────────────────────────────────────────────────────────────

function TodoList() {
  const [todos, setTodos] = useState([]);
  const [draft, setDraft] = useState("");

  const load = async () => {
    const r = await fetch(API("/dashboard/todos"));
    if (r.ok) setTodos(await r.json());
  };
  useEffect(() => { load(); }, []);

  const add = async () => {
    if (!draft.trim()) return;
    await fetch(API("/dashboard/todos"), {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: draft.trim() }),
    });
    setDraft(""); load();
  };

  const toggle = async (id, done) => {
    await fetch(API(`/dashboard/todos/${id}`), {
      method: "PATCH", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ done: !done }),
    });
    load();
  };

  const remove = async (id) => {
    await fetch(API(`/dashboard/todos/${id}`), { method: "DELETE" });
    load();
  };

  const pending = todos.filter(t => !t.done);
  const done    = todos.filter(t =>  t.done);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ display: "flex", gap: 6, marginBottom: 12 }}>
        <input
          value={draft}
          onChange={e => setDraft(e.target.value)}
          onKeyDown={e => e.key === "Enter" && add()}
          placeholder="Add a task…"
          className="dg-input"
          style={{ flex: 1, fontSize: 12 }}
        />
        <button onClick={add} className="btn btn-primary" style={{ whiteSpace: "nowrap" }}>
          Add
        </button>
      </div>
      <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 6 }}>
        {pending.map(t => (
          <div key={t.id} style={{ display: "flex", alignItems: "flex-start", gap: 8 }}
               className="group">
            <button onClick={() => toggle(t.id, t.done)}
              style={{
                marginTop: 2, width: 14, height: 14, flexShrink: 0,
                border: "0.5px solid #1a2f52", borderRadius: 2,
                background: "transparent", cursor: "pointer",
              }} />
            <span style={{ flex: 1, fontSize: 13, color: "#8aaad0", lineHeight: 1.4 }}>{t.text}</span>
            <button onClick={() => remove(t.id)}
              style={{ fontSize: 10, color: "#2a4a7a", cursor: "pointer", background: "none", border: "none",
                       fontFamily: "'Share Tech Mono', monospace", flexShrink: 0 }}>
              ✕
            </button>
          </div>
        ))}
        {done.length > 0 && (
          <>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#1a2f52",
                          letterSpacing: "0.15em", marginTop: 6, paddingTop: 6,
                          borderTop: "0.5px solid #1a2540" }}>
              DONE
            </div>
            {done.map(t => (
              <div key={t.id} style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
                <div style={{
                  marginTop: 2, width: 14, height: 14, flexShrink: 0,
                  border: "0.5px solid #1a2f52", borderRadius: 2,
                  background: "#1a2f52", cursor: "pointer",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 8, color: "#3a5a80",
                }} onClick={() => toggle(t.id, t.done)}>✓</div>
                <span style={{ flex: 1, fontSize: 12, color: "#2a4a7a", textDecoration: "line-through" }}>{t.text}</span>
                <button onClick={() => remove(t.id)}
                  style={{ fontSize: 10, color: "#1a2f52", cursor: "pointer", background: "none", border: "none",
                           fontFamily: "'Share Tech Mono', monospace" }}>
                  ✕
                </button>
              </div>
            ))}
          </>
        )}
        {todos.length === 0 && (
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52", letterSpacing: "0.1em" }}>
            NO TASKS
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────

export default function DashboardPanel() {
  const [period, setPeriod]     = useState("day");
  const [stats, setStats]       = useState(null);
  const [agentMsgs, setAgentMsgs] = useState([]);
  const [clientMsgs, setClientMsgs] = useState([]);

  const load = async (p = period) => {
    const [s, a, c] = await Promise.all([
      fetch(API(`/dashboard/summary?period=${p}`)),
      fetch(API("/dashboard/agent-messages")),
      fetch(API("/dashboard/client-messages")),
    ]);
    if (s.ok) setStats(await s.json());
    if (a.ok) setAgentMsgs(await a.json());
    if (c.ok) setClientMsgs(await c.json());
  };

  useEffect(() => { load(period); }, [period]);
  useEffect(() => {
    const id = setInterval(() => load(period), 30000);
    return () => clearInterval(id);
  }, [period]);

  const markRead = async (id) => {
    await fetch(API(`/dashboard/agent-messages/${id}/read`), { method: "POST" });
    setAgentMsgs(p => p.map(m => m.id === id ? { ...m, read: true } : m));
  };

  const c = stats?.calling  ?? {};
  const s = stats?.sms      ?? {};
  const ct = stats?.contacts ?? {};
  const unread = agentMsgs.filter(m => !m.read).length;

  const PERIOD_LABELS = { day: "TODAY", week: "THIS WEEK", month: "THIS MONTH" };

  return (
    <div style={{ flex: 1, overflowY: "auto", padding: 24, display: "flex", flexDirection: "column", gap: 24 }}>

      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 22, fontWeight: 700,
                        color: "#f0f4ff", letterSpacing: "-0.01em" }}>
            Good morning, Dylan.
          </div>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80",
                        letterSpacing: "0.14em", marginTop: 4 }}>
            SYS // DIGIGROWTH OS · {PERIOD_LABELS[period]}
          </div>
        </div>

        {/* Period toggle */}
        <div style={{
          display: "flex", background: "#0d1626",
          border: "0.5px solid #1a2540", borderRadius: 4, padding: 3, gap: 2,
        }}>
          {[["day","TODAY"],["week","WEEK"],["month","MONTH"]].map(([p, label]) => (
            <button key={p} onClick={() => setPeriod(p)}
              style={{
                fontFamily: "'Share Tech Mono', monospace",
                fontSize: 10, letterSpacing: "0.12em",
                padding: "5px 12px", borderRadius: 3, border: "none", cursor: "pointer",
                background: period === p ? "#2857a0" : "transparent",
                color: period === p ? "#c8dcff" : "#3a5a80",
                transition: "all 0.15s",
              }}>
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="dg-divider" />

      {/* Cold Calling Stats */}
      <div>
        <div className="sec-label">Cold Calling</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8 }}>
          <StatCard label="Calls Made"  value={c.calls_made} />
          <StatCard label="DMs Reached" value={c.dms_reached} />
          <StatCard label="Reach Rate"  value={c.calls_made > 0 ? `${c.reach_rate}%` : "—"} />
          <StatCard label="Booked"      value={c.booked}
            delta={c.booked > 0 ? `↑ ${c.booked} intro${c.booked !== 1 ? "s" : ""}` : null} />
        </div>
      </div>

      {/* SMS + Contacts Stats */}
      <div>
        <div className="sec-label">SMS & Pipeline</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 8 }}>
          <StatCard label="Active Convos"  value={s.active} />
          <StatCard label="SMS Booked"     value={s.booked} />
          <StatCard label="Messages"       value={s.messages} />
          <StatCard label="Total Contacts" value={ct.total} />
          <StatCard label="New Contacts"   value={ct.new} />
        </div>
      </div>

      <div className="dg-divider" />

      {/* Bottom 3-col */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16, minHeight: 300 }}>

        {/* Agent Activity */}
        <div className="dg-card" style={{ padding: 16, display: "flex", flexDirection: "column" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
            <div className="sec-label" style={{ marginBottom: 0 }}>Agent Activity</div>
            {unread > 0 && (
              <span className="badge badge-blue">{unread} new</span>
            )}
          </div>
          <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 8 }}>
            {agentMsgs.length === 0 && (
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52", letterSpacing: "0.1em" }}>
                NO MESSAGES
              </div>
            )}
            {agentMsgs.map(m => (
              <div key={m.id} onClick={() => !m.read && markRead(m.id)}
                style={{
                  padding: "10px 12px", borderRadius: 4, cursor: m.read ? "default" : "pointer",
                  background: m.read ? "transparent" : "rgba(58,123,213,0.05)",
                  border: `0.5px solid ${m.read ? "#1a2540" : "rgba(58,123,213,0.2)"}`,
                  transition: "all 0.15s",
                }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                  <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9,
                                  color: "#3a7bd5", letterSpacing: "0.1em" }}>
                    {AGENT_ICONS[m.agent] ?? "AGT"}
                  </span>
                  <span style={{ marginLeft: "auto", fontFamily: "'Share Tech Mono', monospace",
                                  fontSize: 9, color: "#2a4a7a" }}>
                    {timeAgo(m.created_at)}
                  </span>
                </div>
                <div style={{ fontSize: 12, color: m.read ? "#3a4f6f" : "#8aaad0", lineHeight: 1.4 }}>
                  {m.message}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Needs Reply */}
        <div className="dg-card" style={{ padding: 16, display: "flex", flexDirection: "column" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
            <div className="sec-label" style={{ marginBottom: 0 }}>Needs Reply</div>
            {clientMsgs.length > 0 && (
              <span className="badge badge-amber">{clientMsgs.length}</span>
            )}
          </div>
          <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 8 }}>
            {clientMsgs.length === 0 && (
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52", letterSpacing: "0.1em" }}>
                ALL CAUGHT UP
              </div>
            )}
            {clientMsgs.map(m => (
              <div key={m.phone} style={{
                padding: "10px 12px", borderRadius: 4,
                background: "rgba(240,160,40,0.04)",
                border: "0.5px solid rgba(240,160,40,0.15)",
                borderLeft: "2px solid #f0a028",
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 3 }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: "#c4d0e8" }}>
                    {m.business || m.owner || m.phone}
                  </span>
                  <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80" }}>
                    {timeAgo(m.updated_at)}
                  </span>
                </div>
                <div style={{ fontSize: 11, color: "#5a6f8f", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {m.last_message}
                </div>
                <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a4a7a", marginTop: 3 }}>
                  {m.phone}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* To-Do */}
        <div className="dg-card" style={{ padding: 16, display: "flex", flexDirection: "column" }}>
          <div className="sec-label">To-Do</div>
          <TodoList />
        </div>

      </div>
    </div>
  );
}
