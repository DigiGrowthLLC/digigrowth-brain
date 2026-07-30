import React, { useState, useEffect } from "react";
import {
  LineChart, Line,
  BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer,
} from "recharts";
import { API } from "../api.js";

function timeAgo(ts) {
  if (!ts) return "";
  const d = new Date(ts), now = new Date(), diff = now - d;
  if (diff < 60000) return "just now";
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

// ── Top stat card (Vision UI style) ──────────────────────────────────────────

const STAT_ICONS = {
  dialer: (
    <svg viewBox="0 0 20 20" fill="none" width={20} height={20}>
      <path d="M4 3h3l1.5 3.5-2 1.2c.8 1.7 2.3 3.2 4 4l1.2-2L15.5 11V14c0 .6-.4 1-1 1C7 15 4 8 4 4c0-.6.4-1 1-1H4z" stroke="#6ab0ff" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  reach: (
    <svg viewBox="0 0 20 20" fill="none" width={20} height={20}>
      <circle cx="7" cy="7" r="3" stroke="#6ab0ff" strokeWidth="1.6"/>
      <circle cx="14" cy="7" r="3" stroke="#6ab0ff" strokeWidth="1.6"/>
      <path d="M2 17c0-3 2.24-5 5-5m5 0c2.76 0 5 2 5 5" stroke="#6ab0ff" strokeWidth="1.6" strokeLinecap="round"/>
    </svg>
  ),
  booked: (
    <svg viewBox="0 0 20 20" fill="none" width={20} height={20}>
      <rect x="3" y="4" width="14" height="13" rx="2" stroke="#6ab0ff" strokeWidth="1.6"/>
      <path d="M7 2v4M13 2v4M3 9h14" stroke="#6ab0ff" strokeWidth="1.6" strokeLinecap="round"/>
      <path d="M7 13l2 2 4-4" stroke="#6ab0ff" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  sms: (
    <svg viewBox="0 0 20 20" fill="none" width={20} height={20}>
      <path d="M16 3H4a1 1 0 00-1 1v8a1 1 0 001 1h3v3l4-3h5a1 1 0 001-1V4a1 1 0 00-1-1z" stroke="#6ab0ff" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M7 9h6M7 12h4" stroke="#6ab0ff" strokeWidth="1.4" strokeLinecap="round"/>
    </svg>
  ),
};

function TopStatCard({ label, value, delta, positive, iconKey }) {
  return (
    <div className="stat-card">
      <div>
        <div className="stat-card-label">{label}</div>
        <div className="stat-card-value">{value ?? "—"}</div>
        {delta != null && (
          <div className="stat-card-delta" style={{ color: positive ? "#14c882" : "#dc3c3c" }}>
            {positive ? "↑" : "↓"} {delta}
          </div>
        )}
      </div>
      <div className="stat-card-icon">{STAT_ICONS[iconKey]}</div>
    </div>
  );
}

// ── Custom chart tooltip ──────────────────────────────────────────────────────

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: "rgba(10,18,48,0.95)", border: "1px solid rgba(58,123,213,0.2)",
      borderRadius: 10, padding: "8px 14px", fontSize: 12,
      fontFamily: "'Space Grotesk', sans-serif",
    }}>
      <div style={{ color: "#8aaad0", marginBottom: 4 }}>{label}</div>
      {payload.map(p => (
        <div key={p.dataKey} style={{ color: p.color, fontWeight: 600 }}>
          {p.name}: {p.value}
        </div>
      ))}
    </div>
  );
}

// ── To-Do (dashboard widget — today + overdue only) ──────────────────────────

// Turns bare URLs in plain text into clickable links, leaving everything
// else as-is — descriptions are just freeform notes, not markdown.
function linkifyText(text) {
  const parts = text.split(/(https?:\/\/[^\s]+)/g);
  return parts.map((part, i) =>
    /^https?:\/\//.test(part)
      ? <a key={i} href={part} target="_blank" rel="noreferrer" onClick={e => e.stopPropagation()}
          style={{ color: "#3a7bd5", wordBreak: "break-all" }}>{part}</a>
      : <React.Fragment key={i}>{part}</React.Fragment>
  );
}

function TodoWidgetRow({ t, overdue, onComplete, onRemove, onSaveDescription }) {
  const [expanded, setExpanded] = useState(false);
  const [draft, setDraft] = useState(t.description || "");

  const toggle = () => {
    setDraft(t.description || "");
    setExpanded(e => !e);
  };

  const commit = () => {
    const trimmed = draft.trim();
    if (trimmed !== (t.description || "")) onSaveDescription(t.id, trimmed);
  };

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <button onClick={() => onComplete(t.id)} style={{
          flexShrink: 0, width: 16, height: 16, cursor: "pointer",
          border: "1px solid rgba(58,123,213,0.3)", borderRadius: 4,
          background: "transparent",
        }} />
        <span
          onClick={toggle}
          title={t.description ? "Click to view/edit notes" : "Click to add notes"}
          style={{ flex: 1, fontSize: 13, color: "#8aaad0", lineHeight: 1.4, cursor: "pointer", display: "flex", alignItems: "center", gap: 6 }}
        >
          {t.text}
          {!!t.description && (
            <span title="Has notes" style={{ width: 5, height: 5, borderRadius: "50%", flexShrink: 0, background: "#3a7bd5" }} />
          )}
        </span>
        {t.due_date && (
          <span style={{
            fontFamily: "'Share Tech Mono', monospace", fontSize: 9,
            color: overdue ? "#dc3c3c" : "#3a5a80", letterSpacing: "0.06em", flexShrink: 0,
          }}>
            {t.due_date.slice(5).replace("-", "/")}
          </span>
        )}
        <button onClick={() => onRemove(t.id)} style={{
          fontSize: 10, color: "#2a4a7a", cursor: "pointer", background: "none", border: "none",
        }}>✕</button>
      </div>
      {expanded && (
        <div style={{ padding: "6px 0 0 26px", display: "flex", flexDirection: "column", gap: 6 }}>
          <textarea
            autoFocus
            className="dg-input"
            rows={2}
            placeholder="Notes, instructions, or a link…"
            value={draft}
            onChange={e => setDraft(e.target.value)}
            onBlur={commit}
            onKeyDown={e => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) e.target.blur(); }}
            style={{ width: "100%", fontSize: 12, resize: "vertical", boxSizing: "border-box" }}
          />
          {draft.trim() && (
            <div style={{ fontSize: 11, lineHeight: 1.5, color: "#5a7faa" }}>{linkifyText(draft)}</div>
          )}
        </div>
      )}
    </div>
  );
}

function TodoList() {
  const [todos, setTodos] = useState([]);
  const [draft, setDraft] = useState("");
  const todayStr = new Date().toISOString().slice(0, 10);

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

  const complete = async (id) => {
    setTodos(prev => prev.filter(t => t.id !== id));
    await fetch(API(`/dashboard/todos/${id}`), {
      method: "PATCH", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ done: true }),
    });
  };

  const remove = async (id) => {
    setTodos(prev => prev.filter(t => t.id !== id));
    await fetch(API(`/dashboard/todos/${id}`), { method: "DELETE" });
  };

  const saveDescription = async (id, description) => {
    setTodos(prev => prev.map(t => t.id === id ? { ...t, description } : t));
    await fetch(API(`/dashboard/todos/${id}`), {
      method: "PATCH", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ description }),
    });
  };

  const visible = todos
    .filter(t => !t.due_date || t.due_date.slice(0, 10) <= todayStr)
    .slice(0, 6);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
        <input value={draft} onChange={e => setDraft(e.target.value)}
          onKeyDown={e => e.key === "Enter" && add()}
          placeholder="Quick add…" className="dg-input"
          style={{ flex: 1, fontSize: 12 }} />
        <button onClick={add} className="btn btn-primary" style={{ padding: "8px 14px", fontSize: 11 }}>
          Add
        </button>
      </div>
      <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 8 }}>
        {visible.map(t => {
          const overdue = t.due_date && t.due_date.slice(0, 10) < todayStr;
          return (
            <TodoWidgetRow
              key={t.id}
              t={t}
              overdue={overdue}
              onComplete={complete}
              onRemove={remove}
              onSaveDescription={saveDescription}
            />
          );
        })}
        {visible.length === 0 && (
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52" }}>
            ALL CLEAR
          </div>
        )}
      </div>
    </div>
  );
}

// ── Calendar widget ───────────────────────────────────────────────────────────

function CalendarWidget({ events, loading, error }) {
  const todayKey = new Date().toISOString().slice(0, 10);
  const todayEvents = events.filter(ev => ev.start.slice(0, 10) === todayKey);

  const fmtTime = (start, end, allDay) => {
    if (allDay) return "All day";
    const opts = { hour: "numeric", minute: "2-digit", hour12: true };
    const s = new Date(start).toLocaleTimeString("en-US", opts);
    const e = end ? new Date(end).toLocaleTimeString("en-US", opts) : null;
    return e ? `${s} – ${e}` : s;
  };

  return (
    <div className="glass-card" style={{ padding: "20px 22px", display: "flex", flexDirection: "column", minHeight: 280 }}>
      <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 14, fontWeight: 600, color: "#d0dcf0", marginBottom: 16 }}>
        Today's Calendar
      </div>

      {loading && (
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>LOADING…</div>
      )}
      {!loading && error && (
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>
          {error.toLowerCase().includes("missing") || error.toLowerCase().includes("configured")
            ? "GOOGLE CALENDAR NOT CONFIGURED"
            : error.toUpperCase()}
        </div>
      )}
      {!loading && !error && todayEvents.length === 0 && (
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52" }}>NO EVENTS TODAY</div>
      )}

      <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 8 }}>
        {todayEvents.map(ev => (
          <div key={ev.id} style={{
            padding: "8px 12px", borderRadius: 10,
            background: "rgba(58,123,213,0.06)",
            border: "1px solid rgba(58,123,213,0.12)",
            borderLeft: "3px solid #3a7bd5",
          }}>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", letterSpacing: "0.08em", marginBottom: 2 }}>
              {fmtTime(ev.start, ev.end, ev.all_day)}
            </div>
            <div style={{ fontSize: 13, color: "#8aaad0", lineHeight: 1.4 }}>{ev.title}</div>
            {ev.location && (
              <div style={{ fontSize: 10, color: "#3a5a7a", marginTop: 2 }}>{ev.location}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}


// ── Main ──────────────────────────────────────────────────────────────────────

export default function DashboardPanel({ onNavigate }) {
  const [period, setPeriod]       = useState("all");
  const [stats, setStats]         = useState(null);
  const [agentMsgs, setAgentMsgs]   = useState([]);
  const [clientMsgs, setClientMsgs] = useState([]);
  const [calEvents, setCalEvents]   = useState([]);
  const [calLoading, setCalLoading] = useState(true);
  const [calError, setCalError]     = useState(null);

  const loadCalendar = async () => {
    try {
      const r = await fetch(API("/dashboard/calendar?days=1"));
      if (r.ok) {
        const d = await r.json();
        setCalEvents(d.events || []);
        setCalError(d.error || null);
      }
    } catch {
      setCalError("Failed to load");
    } finally {
      setCalLoading(false);
    }
  };

  const PERIOD_LABEL = { day: "TODAY", week: "THIS WEEK", month: "THIS MONTH", all: "ALL TIME" };

  const load = async (p = period) => {
    const [s, a, c] = await Promise.all([
      fetch(API(`/dashboard/summary?period=${p}`)),
      fetch(API("/dashboard/agent-messages")),
      fetch(API("/dashboard/client-messages")),
    ]);
    if (s.ok) setStats(await s.json());
    if (a.ok) setAgentMsgs((await a.json()).filter(m => !m.read));
    if (c.ok) setClientMsgs(await c.json());
  };

  useEffect(() => { load(period); }, [period]);
  useEffect(() => { loadCalendar(); }, []);
  useEffect(() => {
    const id = setInterval(() => load(period), 30000);
    return () => clearInterval(id);
  }, [period]);

  const markRead = async (id) => {
    setAgentMsgs(p => p.filter(m => m.id !== id));
    await fetch(API(`/dashboard/agent-messages/${id}/read`), { method: "POST" });
  };

  const calling  = stats?.calling  ?? {};
  const sms      = stats?.sms      ?? {};
  const contacts = stats?.contacts ?? {};
  const unread   = agentMsgs.length;

  // Disposition bar data from chart — channel-agnostic (calling + SMS)
  // totals, matching the Analytics tab's 6-Stage Acquisition Funnel.
  const barData = [
    { name: "Outreach", value: calling.total_outreach     ?? 0, fill: "#3a7bd5" },
    { name: "Reached",  value: calling.total_reached       ?? 0, fill: "#14c882" },
    { name: "Booked",   value: calling.total_appointments  ?? 0, fill: "#f0a028" },
    { name: "SMS",      value: sms.active                   ?? 0, fill: "#a080f0" },
  ];

  const today = new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });

  return (
    <div style={{ flex: 1, overflowY: "auto", padding: "24px 28px", display: "flex", flexDirection: "column", gap: 22 }}>

      {/* ── Header ─────────────────────────────────────────────────── */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 24, fontWeight: 700,
                        color: "#f0f4ff", letterSpacing: "-0.02em" }}>
            Dashboard
          </div>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80",
                        letterSpacing: "0.14em", marginTop: 4 }}>
            {today.toUpperCase()}
          </div>
        </div>
        {/* Period toggle */}
        <div style={{
          display: "flex", background: "rgba(10,18,48,0.7)",
          border: "1px solid rgba(58,123,213,0.1)", borderRadius: 12, padding: 4, gap: 2,
        }}>
          {[["day","Today"],["week","Week"],["month","Month"],["all","All Time"]].map(([p, label]) => (
            <button key={p} onClick={() => setPeriod(p)} style={{
              fontFamily: "'Space Grotesk', sans-serif",
              fontSize: 12, fontWeight: 500, padding: "6px 16px",
              borderRadius: 9, border: "none", cursor: "pointer", transition: "all 0.15s",
              background: period === p ? "linear-gradient(135deg, #2857a0 0%, #3a7bd5 100%)" : "transparent",
              color: period === p ? "#fff" : "#4a6080",
              boxShadow: period === p ? "0 2px 10px rgba(58,123,213,0.4)" : "none",
            }}>{label}</button>
          ))}
        </div>
      </div>

      {/* ── Row 1: 4 Stat Cards ────────────────────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16 }}>
        <TopStatCard label="Total Outreach"    value={calling.total_outreach}  iconKey="dialer"
          delta={calling.total_outreach > 0 ? `${calling.total_outreach} touches` : null} positive={true} />
        <TopStatCard label="Total Reached"     value={calling.total_reached}   iconKey="reach"
          delta={calling.total_outreach > 0 ? `${((calling.total_reached / calling.total_outreach) * 100).toFixed(1)}% rate` : null} positive={true} />
        <TopStatCard label="Total Appointments" value={calling.total_appointments} iconKey="booked"
          delta={calling.total_appointments > 0 ? "booked" : null} positive={true} />
        <TopStatCard label="Total ABR"
          value={calling.total_outreach > 0 ? `${calling.total_abr}%` : "—"}
          iconKey="sms"
          delta="appt booking rate" positive={true} />
      </div>

      {/* ── Row 2: To-Do + Today's Calendar ───────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>

        {/* To-Do */}
        <div className="glass-card" style={{ padding: "20px 22px", display: "flex", flexDirection: "column", minHeight: 280 }}>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 14, fontWeight: 600, color: "#d0dcf0", marginBottom: 16 }}>
            To-Do
          </div>
          <TodoList />
        </div>

        {/* Today's Calendar */}
        <CalendarWidget events={calEvents} loading={calLoading} error={calError} />

      </div>

      {/* ── Row 3: Charts ──────────────────────────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "1.8fr 1fr", gap: 16 }}>

        {/* Funnel chart — calls overview for selected period */}
        <div className="glass-card" style={{ padding: "22px 24px" }}>
          <div style={{ marginBottom: 20 }}>
            <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 16, fontWeight: 600, color: "#d0dcf0" }}>
              Outreach Overview
            </div>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#14c882", letterSpacing: "0.1em", marginTop: 3 }}>
              {PERIOD_LABEL[period]}
            </div>
          </div>
          {(() => {
            const funnelData = [
              { stage: "Outreach", value: calling.total_outreach    ?? 0 },
              { stage: "Answered", value: calling.total_answered     ?? 0 },
              { stage: "Reached",  value: calling.total_reached      ?? 0 },
              { stage: "Booked",   value: calling.total_appointments ?? 0 },
            ];
            const hasData = funnelData.some(d => d.value > 0);
            return hasData ? (
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={funnelData} margin={{ top: 5, right: 10, bottom: 0, left: -20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(58,123,213,0.06)" />
                  <XAxis dataKey="stage" tick={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, fill: "#2a4a7a" }}
                    axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, fill: "#2a4a7a" }}
                    axisLine={false} tickLine={false} />
                  <Tooltip content={<ChartTooltip />} />
                  <Line type="monotone" dataKey="value" name="Count"
                    stroke="#3a7bd5" strokeWidth={2}
                    dot={{ fill: "#3a7bd5", r: 4, strokeWidth: 0 }}
                    activeDot={{ fill: "#6ab0ff", r: 5, strokeWidth: 0 }} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div style={{
                height: 180, display: "flex", alignItems: "center", justifyContent: "center",
                fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52", letterSpacing: "0.15em",
              }}>
                NO DATA FOR THIS PERIOD
              </div>
            );
          })()}
        </div>

        {/* Bar chart — this period breakdown */}
        <div className="glass-card" style={{ padding: "22px 24px" }}>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 16, fontWeight: 600, color: "#d0dcf0", marginBottom: 4 }}>
            Period Breakdown
          </div>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a7bd5",
                        letterSpacing: "0.1em", marginBottom: 18 }}>
            {PERIOD_LABEL[period]}
          </div>
          <ResponsiveContainer width="100%" height={140}>
            <BarChart data={barData} margin={{ top: 0, right: 0, bottom: 0, left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(58,123,213,0.06)" />
              <XAxis dataKey="name" tick={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, fill: "#2a4a7a" }}
                axisLine={false} tickLine={false} />
              <YAxis tick={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, fill: "#2a4a7a" }}
                axisLine={false} tickLine={false} />
              <Tooltip content={<ChartTooltip />} />
              <Bar dataKey="value" name="Count" radius={[4,4,0,0]}>
                {barData.map((entry, i) => (
                  <rect key={i} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>

          <div className="dg-divider" style={{ margin: "14px 0" }} />
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            {barData.map(({ name, value, fill }) => (
              <div key={name} style={{ textAlign: "center" }}>
                <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a4a7a", letterSpacing: "0.1em" }}>
                  {name.toUpperCase()}
                </div>
                <div style={{ fontSize: 16, fontWeight: 700, color: fill, marginTop: 2 }}>{value}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Row 4: Metric cards ────────────────────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>

        {/* Reach Rate */}
        <div className="glass-card" style={{ padding: "24px 22px" }}>
          <div className="sec-label">Reach Rate</div>
          <div style={{ textAlign: "center", padding: "10px 0" }}>
            <div style={{
              fontSize: 52, fontWeight: 700, color: "#f0f4ff",
              letterSpacing: "-0.04em", lineHeight: 1,
              background: "linear-gradient(135deg, #3a7bd5, #6ab0ff)",
              WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
            }}>
              {calling.total_outreach > 0 ? `${((calling.total_reached / calling.total_outreach) * 100).toFixed(1)}%` : "—"}
            </div>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10,
                          color: "#3a5a80", letterSpacing: "0.12em", marginTop: 8 }}>
              REACHED / TOTAL OUTREACH
            </div>
          </div>
          <div className="dg-divider" style={{ margin: "12px 0" }} />
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <div>
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a4a7a", letterSpacing: "0.12em" }}>OUTREACH</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: "#c4d0e8", marginTop: 2 }}>{calling.total_outreach ?? 0}</div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a4a7a", letterSpacing: "0.12em" }}>REACHED</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: "#14c882", marginTop: 2 }}>{calling.total_reached ?? 0}</div>
            </div>
          </div>
        </div>

        {/* Pipeline */}
        <div className="glass-card" style={{ padding: "24px 22px" }}>
          <div className="sec-label">Pipeline</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {[
              { label: "Total Contacts", value: contacts.total ?? 0, color: "#5a9bf0" },
              { label: "New This Period", value: contacts.new ?? 0,   color: "#14c882" },
              { label: "SMS Booked",      value: sms.booked ?? 0,     color: "#f0a028" },
              { label: "Active Convos",   value: sms.active ?? 0,     color: "#a080f0" },
            ].map(({ label, value, color }) => (
              <div key={label} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <div style={{ width: 6, height: 6, borderRadius: "50%", background: color, flexShrink: 0 }} />
                  <span style={{ fontSize: 12, color: "#6080a8" }}>{label}</span>
                </div>
                <span style={{ fontSize: 15, fontWeight: 700, color: "#c4d0e8" }}>{value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Row 5: Agent Activity + Needs Reply ────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>

        {/* Agent Messages */}
        <div className="glass-card" style={{ padding: "20px 22px", display: "flex", flexDirection: "column", height: 280 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
            <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 14, fontWeight: 600, color: "#d0dcf0" }}>
              Agent Activity
            </div>
            {unread > 0 && <span className="badge badge-blue">{unread} new</span>}
          </div>
          <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 8 }}>
            {agentMsgs.length === 0 && (
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52" }}>NO MESSAGES</div>
            )}
            {agentMsgs.map(m => (
              <div key={m.id} onClick={() => {
                onNavigate?.("agents", m.agent);
                markRead(m.id);
              }} style={{
                padding: "10px 12px", borderRadius: 10, cursor: "pointer",
                background: "rgba(58,123,213,0.06)",
                border: "1px solid rgba(58,123,213,0.15)",
                transition: "all 0.15s",
              }}
              onMouseEnter={e => e.currentTarget.style.background = "rgba(58,123,213,0.1)"}
              onMouseLeave={e => e.currentTarget.style.background = "rgba(58,123,213,0.06)"}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                  <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", letterSpacing: "0.1em" }}>
                    {(m.agent ?? "system").toUpperCase()}
                  </span>
                  <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#1a2f52" }}>
                    {timeAgo(m.created_at)}
                  </span>
                </div>
                <div style={{ fontSize: 12, color: "#8aaad0", lineHeight: 1.4 }}>{m.message}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Needs Reply */}
        <div className="glass-card" style={{ padding: "20px 22px", display: "flex", flexDirection: "column", height: 280 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
            <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 14, fontWeight: 600, color: "#d0dcf0" }}>
              Needs Reply
            </div>
            {clientMsgs.length > 0 && <span className="badge badge-amber">{clientMsgs.length}</span>}
          </div>
          <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 8 }}>
            {clientMsgs.length === 0 && (
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52" }}>ALL CAUGHT UP</div>
            )}
            {clientMsgs.map(m => (
              <div key={m.phone} onClick={() => {
                onNavigate?.("inbox", { channel: "sms", phone: m.phone });
                setClientMsgs(p => p.filter(x => x.phone !== m.phone));
              }} style={{
                padding: "10px 12px", borderRadius: 10, cursor: "pointer",
                background: "rgba(240,160,40,0.04)",
                border: "1px solid rgba(240,160,40,0.12)",
                borderLeft: "3px solid #f0a028",
                transition: "all 0.15s",
              }}
              onMouseEnter={e => e.currentTarget.style.background = "rgba(240,160,40,0.09)"}
              onMouseLeave={e => e.currentTarget.style.background = "rgba(240,160,40,0.04)"}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 3 }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: "#c4d0e8" }}>
                    {m.business || m.owner || m.phone}
                  </span>
                  <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80" }}>
                    {timeAgo(m.last_inbound_at)}
                  </span>
                </div>
                <div style={{ fontSize: 11, color: "#5a6f8f", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {m.last_message}
                </div>
                <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a3a50", marginTop: 3 }}>
                  {m.phone}
                </div>
              </div>
            ))}
          </div>
        </div>

      </div>

    </div>
  );
}
