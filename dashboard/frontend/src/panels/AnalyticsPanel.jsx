import React, { useState, useEffect } from "react";
import { API } from "../api.js";
import PeriodToggle from "../components/PeriodToggle.jsx";

function pct(v) { return v != null ? `${v}%` : "—"; }
function num(v) { return v != null ? v : "—"; }
function money(v) { return v != null ? `$${v.toLocaleString()}` : "—"; }

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

const ANALYTICS_PERIOD_OPTIONS = [[7,"7D"],[30,"30D"],[0,"All Time"]];

function LoadingRow() {
  return (
    <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52", letterSpacing: "0.1em" }}>
      LOADING...
    </div>
  );
}

function SmsOutreachCard({ outreach, tab }) {
  if (!outreach) return <div className="glass-card" style={{ padding: "20px 22px" }}><SecLabel>SMS Outreach</SecLabel><LoadingRow /></div>;
  const sms = outreach.sms?.[tab] ?? {};

  return (
    <div className="glass-card" style={{ padding: "20px 22px" }}>
      <SecLabel>SMS Outreach</SecLabel>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10, marginTop: 4 }}>
        <MiniStat label="Total Outreach"  value={num(sms.total_outreach)}  color="#5a9bf0" />
        <MiniStat label="Contacted"       value={num(sms.contacted)}       color="#5a9bf0" />
        <MiniStat label="Reply Rate"      value={pct(sms.reply_rate)}      color="#5a9bf0" />
        <MiniStat label="Primed Rate"     value={pct(sms.primed_rate)}     color="#5a9bf0" />
        <MiniStat label="Engaged Rate"    value={pct(sms.engaged_rate)}    color="#5a9bf0" />
        <MiniStat label="Interested Rate" value={pct(sms.interested_rate)} color="#5a9bf0" />
        <MiniStat label="ABR"             value={pct(sms.abr)}             color="#14c882" />
        <MiniStat label="Total Booked"    value={num(sms.booked)}          color="#14c882" />
      </div>
    </div>
  );
}

function EmailOutreachCard({ outreach, tab }) {
  if (!outreach) return <div className="glass-card" style={{ padding: "20px 22px" }}><SecLabel>Email Outreach</SecLabel><LoadingRow /></div>;
  const email = outreach.email?.[tab] ?? {};

  return (
    <div className="glass-card" style={{ padding: "20px 22px" }}>
      <SecLabel>Email Outreach</SecLabel>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10, marginTop: 4 }}>
        <MiniStat label="Sent"                  value={num(email.total_sent)}          color="#9b6bd8" />
        <MiniStat label="Reply Rate"             value={pct(email.reply_rate)}          color="#9b6bd8" />
        <MiniStat label="Open Rate (Raw)"        value={pct(email.open_rate)}           color="#9b6bd8" />
        <MiniStat label="Open Rate (Confirmed)"  value={pct(email.open_rate_confirmed)} color="#9b6bd8" />
        <MiniStat label="Bounce Rate"            value={pct(email.bounce_rate)}         color={email.bounce_rate > 5 ? "#dc3c3c" : "#c4d0e8"} />
        <MiniStat label="Unsubscribe Rate"       value={pct(email.unsubscribe_rate)}    color={email.unsubscribe_rate > 2 ? "#dc3c3c" : "#c4d0e8"} />
        <MiniStat label="ABR"                    value={pct(email.abr)}                 color="#14c882" />
        <MiniStat label="Total Booked"           value={num(email.booked)}              color="#14c882" />
      </div>
    </div>
  );
}

function ColdCallingCard({ outreach, tab }) {
  if (!outreach) return <div className="glass-card" style={{ padding: "20px 22px" }}><SecLabel>Cold Calling</SecLabel><LoadingRow /></div>;
  const call = outreach.calling?.[tab] ?? {};

  return (
    <div className="glass-card" style={{ padding: "20px 22px" }}>
      <SecLabel>Cold Calling</SecLabel>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginTop: 4 }}>
        <MiniStat label="Total Calls"       value={num(call.total)}             color="#3a7bd5" />
        <MiniStat label="Answer Rate"       value={pct(call.answer_rate)}       color="#3a7bd5" />
        <MiniStat label="Pitch Rate"        value={pct(call.pitch_rate)}        color="#3a7bd5" />
        <MiniStat label="Resonation Rate"   value={pct(call.resonation_rate)}   color="#3a7bd5" />
        <MiniStat label="ABR"               value={pct(call.abr)}               color="#14c882" />
        <MiniStat label="Total Booked"      value={num(call.booked)}            color="#14c882" />
      </div>
    </div>
  );
}

function FunnelBlock({ label, value, convRate, color, isFirst }) {
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
          </div>
        )}
      </div>
    </div>
  );
}

export default function AnalyticsPanel() {
  const [days, setDays]               = useState(0);
  const [outreach, setOutreach]       = useState(null);
  const [pipeline, setPipeline]       = useState(null);
  const [sales, setSales]             = useState(null);

  useEffect(() => {
    fetch(API(`/analytics/outreach?days=${days}`)).then(r => r.ok ? r.json() : null).then(setOutreach);
  }, [days]);

  useEffect(() => {
    Promise.all([
      fetch(API(`/analytics/pipeline?days=${days}`)).then(r => r.ok ? r.json() : null),
      fetch(API(`/analytics/sales?days=${days}`)).then(r => r.ok ? r.json() : null),
    ]).then(([p, s]) => { setPipeline(p); setSales(s); });
  }, [days]);

  const funnel = pipeline?.funnel ?? {};

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
        <PeriodToggle days={days} setDays={setDays} options={ANALYTICS_PERIOD_OPTIONS} />
      </div>

      {/* ── Outreach & Appointment Setting ─────────────────────────── */}
      <div>
        <SecLabel>Outreach & Appointment Setting</SecLabel>
        <div style={{ display: "flex", flexDirection: "column", gap: 16, marginTop: 4 }}>
          <SmsOutreachCard outreach={outreach} tab={days === 0 ? "all_time" : "period"} />
          <EmailOutreachCard outreach={outreach} tab={days === 0 ? "all_time" : "period"} />
          <ColdCallingCard outreach={outreach} tab={days === 0 ? "all_time" : "period"} />
        </div>
      </div>

      {/* ── 6-Stage Acquisition Funnel ─────────────────────────────── */}
      <div className="glass-card" style={{ padding: "20px 22px" }}>
        <SecLabel>6-Stage Acquisition Funnel</SecLabel>
        <div style={{ display: "flex", alignItems: "stretch", gap: 0, marginTop: 4 }}>
          <FunnelBlock isFirst label="Total Leads" value={funnel.total_leads} convRate={null}
            color="90,155,240" />
          <FunnelBlock label="Total Outreach" value={funnel.dialed} convRate={dialedRate}
            color="90,155,240" />
          <FunnelBlock label="Answered" value={funnel.answered} convRate={answeredRate}
            color="20,200,130" />
          <FunnelBlock label="Pitched" value={funnel.pitched} convRate={pitchedRate}
            color="20,200,130" />
          <FunnelBlock label="Booked" value={funnel.booked} convRate={bookedRate}
            color="20,200,130" />
          <FunnelBlock label="Shows" value={funnel.shows} convRate={showRate}
            color="240,160,40" />
          <FunnelBlock label="Closes" value={funnel.closes} convRate={closeRate}
            color="240,160,40" />
        </div>
      </div>

      {/* ── Sales Statistics ───────────────────────────────────────── */}
      <div>
        <SecLabel>Sales Statistics</SecLabel>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
          <MiniStat label="Appointments Booked" value={num(sales?.discovery_calls)} color="#5a9bf0" />
          <MiniStat label="Discovery Calls"     value={num(sales?.shows)}   color="#5a9bf0" />
          <MiniStat label="Show Rate"           value={funnel.booked ? `${Math.round((sales?.shows ?? 0) / funnel.booked * 100)}%` : "—"} color="#14c882" />
          <MiniStat label="Close Rate"          value={sales?.close_rate != null ? `${sales.close_rate}%` : "—"} color="#14c882" />
          <MiniStat label="Total Revenue"       value={money(sales?.total_revenue)} color="#14c882" />
          <MiniStat label="Avg Deal Size"       value={money(sales?.avg_deal_size)} />
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
