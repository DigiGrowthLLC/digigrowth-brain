import React, { useState, useEffect } from "react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer,
} from "recharts";

const API = (p) => `/api${p}`;

const DISPO_COLORS = {
  "Appointment Booked": "#14c882",
  "Follow Up":          "#5a9bf0",
  "Send Info":          "#a080f0",
  "Not Interested":     "#dc3c3c",
  "No Answer":          "#3a4f6f",
  "Voicemail":          "#f0a028",
  "SMS Handoff":        "#a080f0",
};

function pct(v) { return v != null ? `${v}%` : "—"; }
function num(v) { return v != null ? v : "—"; }
function money(v) { return v != null ? `$${v.toLocaleString()}` : "—"; }

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

function SecLabel({ children, style }) {
  return (
    <div className="sec-label" style={style}>{children}</div>
  );
}

function MiniStat({ label, value, color }) {
  return (
    <div className="stat-card" style={{ padding: "14px 16px" }}>
      <div className="stat-card-label">{label}</div>
      <div className="stat-card-value" style={{ color: color || "#f0f4ff" }}>{value ?? "—"}</div>
    </div>
  );
}

function PeriodToggle({ days, setDays }) {
  return (
    <div style={{
      display: "flex", background: "rgba(10,18,48,0.7)",
      border: "1px solid rgba(58,123,213,0.1)", borderRadius: 12, padding: 4, gap: 2,
    }}>
      {[[7,"7D"],[30,"30D"],[90,"90D"]].map(([d, label]) => (
        <button key={d} onClick={() => setDays(d)} style={{
          fontFamily: "'Space Grotesk', sans-serif",
          fontSize: 11, fontWeight: 500, padding: "5px 14px",
          borderRadius: 9, border: "none", cursor: "pointer", transition: "all 0.15s",
          background: days === d ? "linear-gradient(135deg, #2857a0 0%, #3a7bd5 100%)" : "transparent",
          color: days === d ? "#fff" : "#4a6080",
          boxShadow: days === d ? "0 2px 10px rgba(58,123,213,0.4)" : "none",
        }}>{label}</button>
      ))}
    </div>
  );
}

function TabToggle({ value, onChange, options }) {
  return (
    <div style={{
      display: "flex", background: "rgba(10,18,48,0.5)",
      border: "1px solid rgba(58,123,213,0.1)", borderRadius: 8, padding: 3, gap: 2,
    }}>
      {options.map(([v, label]) => (
        <button key={v} onClick={() => onChange(v)} style={{
          fontFamily: "'Share Tech Mono', monospace",
          fontSize: 9, fontWeight: 500, padding: "4px 12px", letterSpacing: "0.08em",
          borderRadius: 6, border: "none", cursor: "pointer", transition: "all 0.15s",
          background: value === v ? "rgba(58,123,213,0.3)" : "transparent",
          color: value === v ? "#6ab0ff" : "#2a4a7a",
        }}>{label}</button>
      ))}
    </div>
  );
}

function OutreachTable({ outreach, tab }) {
  if (!outreach) {
    return (
      <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52", letterSpacing: "0.1em" }}>
        LOADING...
      </div>
    );
  }

  const call = outreach.calling?.[tab] ?? {};
  const sms  = outreach.sms?.[tab]     ?? {};

  const rows = [
    {
      label: "Total Outreach",
      call: num(call.total),
      sms:  num(sms.total_sent),
      email: "—",
    },
    {
      label: "Answer / Open Rate",
      call: pct(call.answer_rate),
      sms:  pct(sms.reply_rate),
      email: "—",
      isRate: true,
    },
    {
      label: "Conversation Rate",
      call: pct(call.conversation_rate),
      sms:  pct(sms.conversation_rate),
      email: "—",
      isRate: true,
    },
    {
      label: "Engaged / Pitch Rate",
      call: pct(call.pitch_rate),
      sms:  pct(sms.engaged_rate),
      email: "—",
      isRate: true,
    },
    {
      label: "ABR",
      call: pct(call.abr),
      sms:  pct(sms.abr),
      email: "—",
      isRate: true,
      highlight: true,
    },
    {
      label: "Total Booked",
      call: num(call.booked),
      sms:  num(sms.booked),
      email: "—",
      isBig: true,
    },
  ];

  const colStyle = { flex: 1, textAlign: "right", fontFamily: "'Share Tech Mono', monospace" };

  return (
    <div>
      {/* Header row */}
      <div style={{ display: "flex", marginBottom: 10, padding: "0 0 8px", borderBottom: "0.5px solid #1a2540" }}>
        <div style={{ flex: 1.6, fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a4a7a", letterSpacing: "0.1em" }}>METRIC</div>
        <div style={{ ...colStyle, fontSize: 9, color: "#5a9bf0", letterSpacing: "0.1em" }}>SMS</div>
        <div style={{ ...colStyle, fontSize: 9, color: "#3a7bd5", letterSpacing: "0.1em" }}>COLD CALLING</div>
        <div style={{ ...colStyle, fontSize: 9, color: "#2a4a7a", letterSpacing: "0.1em" }}>EMAIL</div>
      </div>
      {rows.map((r, i) => (
        <div key={i} style={{
          display: "flex", alignItems: "center",
          padding: "9px 0", borderBottom: "0.5px solid rgba(26,37,64,0.6)",
        }}>
          <div style={{ flex: 1.6, fontSize: 12, color: "#8aaad0" }}>{r.label}</div>
          <div style={{ ...colStyle, fontSize: r.isBig ? 16 : 12, fontWeight: r.isBig ? 700 : 500,
                        color: r.isBig ? "#14c882" : r.highlight ? "#14c882" : "#c4d0e8" }}>
            {r.sms}
          </div>
          <div style={{ ...colStyle, fontSize: r.isBig ? 16 : 12, fontWeight: r.isBig ? 700 : 500,
                        color: r.isBig ? "#14c882" : r.highlight ? "#14c882" : "#c4d0e8" }}>
            {r.call}
          </div>
          <div style={{ ...colStyle, fontSize: 11, color: "#2a4a7a" }}>
            {r.email}
          </div>
        </div>
      ))}
      {/* Email note */}
      <div style={{ marginTop: 10, fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#1a3a60", letterSpacing: "0.08em" }}>
        EMAIL · {outreach.email?.note ?? "GHL webhook integration needed for open/click tracking"}
      </div>
    </div>
  );
}

function FunnelBlock({ label, value, convRate, benchmark, color, isFirst }) {
  return (
    <div style={{ display: "flex", alignItems: "center", flex: 1 }}>
      {!isFirst && (
        <div style={{ fontSize: 18, color: "#1a2f52", margin: "0 6px", flexShrink: 0 }}>›</div>
      )}
      <div style={{
        flex: 1, background: "rgba(10,18,48,0.6)", border: `1px solid rgba(${color},0.2)`,
        borderRadius: 10, padding: "14px 12px", textAlign: "center",
      }}>
        <div style={{ fontSize: 28, fontWeight: 700, color: `rgba(${color},1)`, lineHeight: 1, letterSpacing: "-0.02em" }}>
          {value ?? "—"}
        </div>
        <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 11, color: "#8aaad0", marginTop: 5 }}>
          {label}
        </div>
        {convRate != null && (
          <div style={{ marginTop: 6 }}>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10,
                          color: `rgba(${color},0.8)`, letterSpacing: "0.06em" }}>
              {pct(convRate)}
            </div>
            {benchmark && (
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 8, color: "#1a3a60", marginTop: 2, letterSpacing: "0.06em" }}>
                target {benchmark}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function AnalyticsPanel() {
  const [days, setDays]         = useState(30);
  const [outreach, setOutreach] = useState(null);
  const [calls, setCalls]       = useState(null);
  const [pipeline, setPipeline] = useState(null);
  const [sales, setSales]       = useState(null);
  const [outreachTab, setOutreachTab] = useState("period");

  useEffect(() => {
    Promise.all([
      fetch(API(`/analytics/outreach?days=${days}`)).then(r => r.ok ? r.json() : null),
      fetch(API(`/analytics/calls?days=${days}`)).then(r => r.ok ? r.json() : null),
    ]).then(([o, c]) => { setOutreach(o); setCalls(c); });
  }, [days]);

  useEffect(() => {
    Promise.all([
      fetch(API("/analytics/pipeline")).then(r => r.ok ? r.json() : null),
      fetch(API("/analytics/sales")).then(r => r.ok ? r.json() : null),
    ]).then(([p, s]) => { setPipeline(p); setSales(s); });
  }, []);

  const funnel = pipeline?.funnel ?? {};
  const totalCalls = calls?.total_calls ?? 0;

  // Funnel conversion rates
  const dialedRate   = funnel.total_leads ? _pct(funnel.dialed,   funnel.total_leads) : null;
  const answeredRate = funnel.dialed      ? _pct(funnel.answered, funnel.dialed)      : null;
  const pitchedRate  = funnel.answered    ? _pct(funnel.pitched,  funnel.answered)    : null;
  const bookedRate   = funnel.pitched     ? _pct(funnel.booked,   funnel.pitched)     : null;
  const showRate     = funnel.booked      ? _pct(funnel.shows,    funnel.booked)      : null;
  const closeRate    = funnel.shows       ? _pct(funnel.closes,   funnel.shows)       : null;

  return (
    <div style={{ flex: 1, overflowY: "auto", padding: 24, display: "flex", flexDirection: "column", gap: 24 }}>

      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 22, fontWeight: 700, color: "#f0f4ff", letterSpacing: "-0.02em" }}>
            Analytics
          </div>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80", letterSpacing: "0.18em", marginTop: 3 }}>
            OUTREACH & ACQUISITION
          </div>
        </div>
        <PeriodToggle days={days} setDays={setDays} />
      </div>

      {/* ── Outreach & Appointment Setting ─────────────────────────── */}
      <div className="glass-card" style={{ padding: "20px 22px" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 18 }}>
          <SecLabel style={{ marginBottom: 0 }}>Outreach & Appointment Setting</SecLabel>
          <TabToggle
            value={outreachTab}
            onChange={setOutreachTab}
            options={[["all_time","ALL TIME"],["period",`LAST ${days}D`]]}
          />
        </div>
        <OutreachTable outreach={outreach} tab={outreachTab} />
      </div>

      {/* ── 6-Stage Acquisition Funnel ─────────────────────────────── */}
      <div className="glass-card" style={{ padding: "20px 22px" }}>
        <SecLabel>6-Stage Acquisition Funnel</SecLabel>
        <div style={{ display: "flex", alignItems: "stretch", gap: 0, marginTop: 4 }}>
          <FunnelBlock isFirst label="Total Leads" value={funnel.total_leads} convRate={null}
            color="90,155,240" />
          <FunnelBlock label="Dialed" value={funnel.dialed} convRate={dialedRate}
            benchmark={null} color="90,155,240" />
          <FunnelBlock label="Answered" value={funnel.answered} convRate={answeredRate}
            benchmark="10–15%" color="20,200,130" />
          <FunnelBlock label="Pitched" value={funnel.pitched} convRate={pitchedRate}
            benchmark="40–50%" color="20,200,130" />
          <FunnelBlock label="Booked" value={funnel.booked} convRate={bookedRate}
            benchmark="2–5%" color="20,200,130" />
          <FunnelBlock label="Shows" value={funnel.shows} convRate={showRate}
            benchmark="60–70%" color="240,160,40" />
          <FunnelBlock label="Closes" value={funnel.closes} convRate={closeRate}
            benchmark="20–30%" color="240,160,40" />
        </div>
        <div style={{ marginTop: 12, fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#1a3a60", letterSpacing: "0.08em" }}>
          SHOWS & CLOSES · MANUAL ENTRY — UPDATE VIA SETTINGS OS
        </div>
      </div>

      {/* ── Sales Statistics ───────────────────────────────────────── */}
      <div>
        <SecLabel>Sales Statistics</SecLabel>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
          <MiniStat label="Total Leads Generated" value={num(sales?.total_leads)}     color="#5a9bf0" />
          <MiniStat label="Discovery Calls"        value={num(sales?.discovery_calls)} color="#5a9bf0" />
          <MiniStat label="Strategy Sessions"      value={num(sales?.strategy_sessions)} />
          <MiniStat label="Close Rate"  value={sales?.close_rate != null ? `${sales.close_rate}%` : "—"} color="#14c882" />
          <MiniStat label="Total Revenue"  value={money(sales?.total_revenue)} color="#14c882" />
          <MiniStat label="Avg Deal Size"  value={money(sales?.avg_deal_size)} />
        </div>
      </div>

      {/* ── Daily Scoreboard ──────────────────────────────────────── */}
      <div>
        <SecLabel>Daily Scoreboard · Last {days}D</SecLabel>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 10 }}>
          <MiniStat label="Calls Made" value={num(calls?.total_calls)} color="#3a7bd5" />
          <MiniStat label="Pickups"    value={num(calls?.pickups)}     color="#14c882" />
          <MiniStat label="Bookings"   value={num(calls?.booked)}      color="#14c882" />
          <MiniStat label="Shows"      value={num(sales?.shows)}       color="#f0a028" />
          <MiniStat label="Closes"     value={num(sales?.closes)}      color="#f0a028" />
        </div>
      </div>

      <div className="dg-divider" />

      {/* ── Cold Calling Detail ────────────────────────────────────── */}
      <div>
        <SecLabel>Cold Calling Detail</SecLabel>
        <div style={{ display: "grid", gridTemplateColumns: "1.8fr 1fr", gap: 16 }}>

          {/* Daily trend chart */}
          <div className="glass-card" style={{ padding: "18px 20px" }}>
            <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 14, fontWeight: 600, color: "#d0dcf0", marginBottom: 4 }}>
              Calls vs Pickups
            </div>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", letterSpacing: "0.1em", marginBottom: 16 }}>
              LAST {days} DAYS
            </div>
            <ResponsiveContainer width="100%" height={160}>
              <AreaChart data={calls?.daily ?? []} margin={{ top: 5, right: 5, bottom: 0, left: -20 }}>
                <defs>
                  <linearGradient id="acGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#3a7bd5" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#3a7bd5" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="apGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#14c882" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#14c882" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(58,123,213,0.06)" />
                <XAxis dataKey="date" tick={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, fill: "#2a4a7a" }}
                  axisLine={false} tickLine={false} tickFormatter={v => v ? v.slice(5) : ""} />
                <YAxis tick={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, fill: "#2a4a7a" }}
                  axisLine={false} tickLine={false} />
                <Tooltip content={<ChartTooltip />} />
                <Area type="monotone" dataKey="calls"   name="Calls"   stroke="#3a7bd5" strokeWidth={2} fill="url(#acGrad)" />
                <Area type="monotone" dataKey="pickups" name="Pickups" stroke="#14c882" strokeWidth={2} fill="url(#apGrad)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Disposition breakdown */}
          <div className="glass-card" style={{ padding: "18px 20px" }}>
            <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 14, fontWeight: 600, color: "#d0dcf0", marginBottom: 14 }}>
              By Disposition
            </div>
            {!calls?.by_disposition?.length ? (
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52", letterSpacing: "0.1em" }}>
                NO DATA YET
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {calls.by_disposition.map(d => {
                  const pct2 = totalCalls ? Math.round(d.cnt / totalCalls * 100) : 0;
                  const color = DISPO_COLORS[d.disposition] ?? "#3a5a80";
                  return (
                    <div key={d.disposition}>
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                        <span style={{ fontSize: 11, color }}>{d.disposition}</span>
                        <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80" }}>
                          {d.cnt} ({pct2}%)
                        </span>
                      </div>
                      <div style={{ height: 2, background: "#111e36", borderRadius: 1 }}>
                        <div style={{ height: 2, borderRadius: 1, width: `${pct2}%`, background: color, opacity: 0.7 }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Lead Grades & Geo ──────────────────────────────────────── */}
      <div>
        <SecLabel>Lead Grades & Geography</SecLabel>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>

          {/* Grade table */}
          <div className="glass-card" style={{ padding: "18px 20px" }}>
            <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 14, fontWeight: 600, color: "#d0dcf0", marginBottom: 14 }}>
              Grade Performance
            </div>
            {!pipeline?.by_grade?.length ? (
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52", letterSpacing: "0.1em" }}>NO GRADE DATA</div>
            ) : (
              <div>
                <div style={{ display: "flex", marginBottom: 8, gap: 8 }}>
                  {["Grade","Contacts","Booked","ABR"].map((h, i) => (
                    <div key={h} style={{
                      flex: i === 0 ? 0.6 : 1,
                      fontFamily: "'Share Tech Mono', monospace", fontSize: 9,
                      color: "#2a4a7a", letterSpacing: "0.1em",
                      textAlign: i > 0 ? "right" : "left",
                    }}>{h}</div>
                  ))}
                </div>
                {pipeline.by_grade.map(g => (
                  <div key={g.grade} style={{
                    display: "flex", gap: 8, padding: "7px 0",
                    borderBottom: "0.5px solid rgba(26,37,64,0.6)",
                  }}>
                    <div style={{ flex: 0.6 }}>
                      <span style={{
                        fontFamily: "'Share Tech Mono', monospace", fontSize: 11, fontWeight: 700,
                        color: g.grade === "A" ? "#14c882" : g.grade === "B" ? "#5a9bf0" : "#f0a028",
                      }}>{g.grade}</span>
                    </div>
                    <div style={{ flex: 1, textAlign: "right", fontSize: 12, color: "#c4d0e8" }}>{g.cnt}</div>
                    <div style={{ flex: 1, textAlign: "right", fontSize: 12, color: "#14c882" }}>{g.booked}</div>
                    <div style={{ flex: 1, textAlign: "right", fontFamily: "'Share Tech Mono', monospace", fontSize: 11,
                                  color: g.book_rate > 0 ? "#14c882" : "#2a4a7a" }}>{g.book_rate}%</div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Top states */}
          <div className="glass-card" style={{ padding: "18px 20px" }}>
            <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 14, fontWeight: 600, color: "#d0dcf0", marginBottom: 14 }}>
              Top States
            </div>
            {!pipeline?.top_states?.length ? (
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52", letterSpacing: "0.1em" }}>NO DATA</div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {pipeline.top_states.map((s, i) => {
                  const maxCnt = pipeline.top_states[0]?.cnt || 1;
                  const w = Math.round(s.cnt / maxCnt * 100);
                  return (
                    <div key={s.state}>
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                        <span style={{ fontSize: 12, color: "#8aaad0" }}>{s.state}</span>
                        <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80" }}>{s.cnt}</span>
                      </div>
                      <div style={{ height: 2, background: "#111e36", borderRadius: 1 }}>
                        <div style={{ height: 2, borderRadius: 1, width: `${w}%`,
                                      background: i === 0 ? "#3a7bd5" : "#1a3a60", opacity: 0.8 }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
            {pipeline && (
              <div style={{ marginTop: 14, paddingTop: 12, borderTop: "0.5px solid #1a2540",
                            display: "flex", gap: 16 }}>
                <div>
                  <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a4a7a", letterSpacing: "0.1em" }}>NEW THIS WEEK </span>
                  <span style={{ fontSize: 14, fontWeight: 700, color: "#5a9bf0" }}>{pipeline.new_this_week ?? 0}</span>
                </div>
                <div>
                  <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a4a7a", letterSpacing: "0.1em" }}>THIS MONTH </span>
                  <span style={{ fontSize: 14, fontWeight: 700, color: "#3a7bd5" }}>{pipeline.new_this_month ?? 0}</span>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

    </div>
  );
}

function _pct(num, denom) {
  if (!denom) return null;
  return Math.round(num / denom * 100);
}
