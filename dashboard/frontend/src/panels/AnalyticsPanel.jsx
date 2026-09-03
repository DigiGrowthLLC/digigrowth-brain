import React, { useState, useEffect } from "react";
import { API } from "../api.js";
import PeriodToggle from "../components/PeriodToggle.jsx";
import CampaignModal from "../CampaignModal.jsx";

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

const ANALYTICS_PERIOD_OPTIONS = [[1,"Today"],[7,"7D"],[30,"30D"],[0,"All Time"]];

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
        <MiniStat label="Reply Rate"      value={pct(sms.reply_rate)}      color="#5a9bf0" />
        <MiniStat label="DM Reached Rate" value={pct(sms.dm_reached_rate)} color="#5a9bf0" />
        <MiniStat label="DM Reached"      value={num(sms.dm_reached)}      color="#5a9bf0" />
        <MiniStat label="Primed Rate"     value={pct(sms.primed_rate)}     color="#5a9bf0" />
        <MiniStat label="Engaged Rate"    value={pct(sms.engaged_rate)}    color="#5a9bf0" />
        <MiniStat label="Interested Rate" value={pct(sms.interested_rate)} color="#5a9bf0" />
        <MiniStat label="ABR"             value={pct(sms.abr)}             color="#14c882" />
        <MiniStat label="Total Booked"    value={num(sms.booked)}          color="#14c882" />
        <MiniStat label="Not Interested Rate" value={pct(sms.not_interested_rate)} color="#dc3c3c" />
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
        <MiniStat label="Open Rate"              value={pct(email.open_rate)}           color="#9b6bd8" />
        <MiniStat label="Reply Rate"             value={pct(email.reply_rate)}          color="#9b6bd8" />
        <MiniStat label="Bounce Rate"            value={pct(email.bounce_rate)}         color={email.bounce_rate > 5 ? "#dc3c3c" : "#c4d0e8"} />
        <MiniStat label="Unsubscribe Rate"       value={pct(email.unsubscribe_rate)}    color={email.unsubscribe_rate > 2 ? "#dc3c3c" : "#c4d0e8"} />
        <MiniStat label="ABR"                    value={pct(email.abr)}                 color="#14c882" />
        <MiniStat label="Total Booked"           value={num(email.booked)}              color="#14c882" />
        <MiniStat label="Not Interested Rate"    value={pct(email.not_interested_rate)} color="#dc3c3c" />
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

const CAMPAIGN_CHANNEL_OPTIONS = [["sms","SMS"],["email","Email"],["calling","Cold Calling"]];

function fmtCampaignDate(iso) {
  if (!iso) return "Active";
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function CampaignsView({ days }) {
  const [channel, setChannel]         = useState("sms");
  const [campaigns, setCampaigns]     = useState([]);
  const [selectedId, setSelectedId]   = useState(null);
  const [detail, setDetail]           = useState(null);
  const [modalOpen, setModalOpen]     = useState(false);
  const pendingSelectId = React.useRef(null);

  const loadCampaigns = (ch, selectId) => {
    fetch(API(`/campaigns?channel=${ch}`)).then(r => r.ok ? r.json() : []).then(list => {
      setCampaigns(list);
      if (selectId) setSelectedId(selectId);
      else if (list.length) setSelectedId(list[0].id);
      else setSelectedId(null);
    });
  };

  useEffect(() => {
    setDetail(null);
    loadCampaigns(channel, pendingSelectId.current);
    pendingSelectId.current = null;
  }, [channel]);

  useEffect(() => {
    if (!selectedId) return;
    fetch(API(`/analytics/campaign/${selectedId}?days=${days}`)).then(r => r.ok ? r.json() : null).then(setDetail);
  }, [selectedId, days]);

  async function reactivate(id) {
    await fetch(API(`/campaigns/${id}/activate`), { method: "POST" });
    loadCampaigns(channel, selectedId);
    fetch(API(`/analytics/campaign/${selectedId}?days=${days}`)).then(r => r.ok ? r.json() : null).then(setDetail);
  }

  function onCampaignCreated(campaign) {
    if (campaign.channel === channel) {
      loadCampaigns(channel, campaign.id);
    } else {
      pendingSelectId.current = campaign.id;
      setChannel(campaign.channel);
    }
  }

  const outreachShape = detail
    ? { [channel]: { campaign: detail.metrics } }
    : null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10 }}>
        <PeriodToggle days={channel} setDays={setChannel} options={CAMPAIGN_CHANNEL_OPTIONS} />
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {campaigns.length > 0 && (
            <select
              value={selectedId || ""}
              onChange={e => setSelectedId(Number(e.target.value))}
              style={{
                background: "rgba(30,47,80,0.6)", border: "1px solid #1a2540",
                borderRadius: 6, color: "#8aaad0",
                fontFamily: "'Share Tech Mono', monospace", fontSize: 11,
                padding: "6px 10px", cursor: "pointer",
              }}
            >
              {campaigns.map(c => (
                <option key={c.id} value={c.id}>{c.is_active ? "★ " : ""}{c.name}</option>
              ))}
            </select>
          )}
          <button className="btn btn-primary" style={{ fontSize: 11, padding: "6px 14px" }} onClick={() => setModalOpen(true)}>
            + New Campaign
          </button>
        </div>
      </div>

      <CampaignModal
        open={modalOpen}
        defaultChannel={channel}
        onClose={() => setModalOpen(false)}
        onCreated={onCampaignCreated}
      />

      {!campaigns.length && (
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52", letterSpacing: "0.1em" }}>
          NO {channel.toUpperCase()} CAMPAIGNS YET
        </div>
      )}

      {detail && (
        <>
          <div className="glass-card" style={{ padding: "16px 20px", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10 }}>
            <div>
              <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 15, fontWeight: 700, color: "#f0f4ff" }}>
                {detail.campaign.name}
              </div>
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80", marginTop: 4 }}>
                {detail.periods.map((p, i) => (
                  <span key={i}>{i > 0 ? ", " : ""}{fmtCampaignDate(p.started_at)} – {fmtCampaignDate(p.ended_at)}</span>
                ))}
              </div>
            </div>
            {!detail.campaign.is_active && (
              <button className="btn btn-secondary" onClick={() => reactivate(detail.campaign.id)}>Reactivate</button>
            )}
          </div>

          {channel === "sms" && days !== 0 && (
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#4a6a8a", letterSpacing: "0.04em" }}>
              DM Reached / Primed / Engaged / Interested narrow to {ANALYTICS_PERIOD_OPTIONS.find(([d]) => d === days)?.[1] || "this period"} using when each was actually checked — a conversation whose checkbox was set before that tracking existed won't show up in a period filter, since there's no accurate historical record for it. All-Time still reflects everyone.
            </div>
          )}
          {channel === "sms" && <SmsOutreachCard outreach={outreachShape} tab="campaign" />}
          {channel === "email" && <EmailOutreachCard outreach={outreachShape} tab="campaign" />}
          {channel === "calling" && <ColdCallingCard outreach={outreachShape} tab="campaign" />}
        </>
      )}
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

// VSL funnel: every viewer of the /contact page's video, identified or
// anonymous (see content_tracking.py's vsl_funnel — no "total leads"
// denominator anymore, just Viewed -> Watched 50%+ -> Completed -> Booked).
function VslFunnelCard({ data }) {
  if (!data) return <div className="glass-card" style={{ padding: "20px 22px" }}><SecLabel>VSL (Contact Page Video)</SecLabel><LoadingRow /></div>;
  const halfRate = _pct(data.watched_half, data.viewed);
  const completedRate = _pct(data.completed, data.watched_half);

  return (
    <div className="glass-card" style={{ padding: "20px 22px" }}>
      <SecLabel>VSL (Contact Page Video)</SecLabel>
      <div style={{ display: "flex", alignItems: "stretch", gap: 0, marginTop: 4 }}>
        <FunnelBlock isFirst label="Viewed" value={data.viewed} convRate={null} color="90,155,240" />
        <FunnelBlock label="Watched 50%+" value={data.watched_half} convRate={halfRate} color="20,200,130" />
        <FunnelBlock label="Completed" value={data.completed} convRate={completedRate} color="20,200,130" />
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 10, marginTop: 12 }}>
        <MiniStat label="Booked" value={num(data.booked)} color="#14c882" />
        <MiniStat label="Booking Rate" value={pct(data.booking_rate)} color="#14c882" />
      </div>
    </div>
  );
}

// Loom Outreach funnel: cohort = ONLY contacts who were actually sent a
// self-hosted outreach video (watch_videos.contact_id set) — a contact
// never sent one never appears here, by design (routers/content_tracking.py).
// Sent -> Viewed -> Completed -> Engaged -> Interested -> Booked.
// Engaged/Interested reuse the existing manual CRM stage checkboxes
// (sms_conversations.stage_engaged/stage_interested), not a new concept.
function LoomOutreachFunnelCard({ data }) {
  if (!data) return <div className="glass-card" style={{ padding: "20px 22px" }}><SecLabel>Loom Outreach</SecLabel><LoadingRow /></div>;
  const viewedRate = _pct(data.viewed, data.sent);
  const completedRate = _pct(data.completed, data.viewed);
  const engagedRate = _pct(data.engaged, data.completed);
  const interestedRate = _pct(data.interested, data.engaged);
  const bookedRate = _pct(data.booked, data.interested);

  return (
    <div className="glass-card" style={{ padding: "20px 22px" }}>
      <SecLabel>Loom Outreach</SecLabel>
      <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80", letterSpacing: "0.08em", marginTop: 4, marginBottom: 10 }}>
        ONLY PROSPECTS ACTUALLY SENT AN OUTREACH VIDEO
      </div>
      <div style={{ display: "flex", alignItems: "stretch", gap: 0 }}>
        <FunnelBlock isFirst label="Sent" value={data.sent} convRate={null} color="160,110,240" />
        <FunnelBlock label="Viewed" value={data.viewed} convRate={viewedRate} color="160,110,240" />
        <FunnelBlock label="Completed" value={data.completed} convRate={completedRate} color="90,155,240" />
        <FunnelBlock label="Engaged" value={data.engaged} convRate={engagedRate} color="90,155,240" />
        <FunnelBlock label="Interested" value={data.interested} convRate={interestedRate} color="20,200,130" />
        <FunnelBlock label="Booked" value={data.booked} convRate={bookedRate} color="20,200,130" />
      </div>
    </div>
  );
}

const ANALYTICS_VIEW_TABS = [
  { value: "overview",  label: "OVERVIEW" },
  { value: "campaigns", label: "CAMPAIGNS" },
];

export default function AnalyticsPanel() {
  const [view, setView]               = useState("overview");
  const [days, setDays]               = useState(0);
  const [outreach, setOutreach]       = useState(null);
  const [pipeline, setPipeline]       = useState(null);
  const [sales, setSales]             = useState(null);
  const [vslFunnel, setVslFunnel]     = useState(null);
  const [loomFunnel, setLoomFunnel]   = useState(null);

  useEffect(() => {
    fetch(API(`/analytics/outreach?days=${days}`)).then(r => r.ok ? r.json() : null).then(setOutreach);
  }, [days]);

  useEffect(() => {
    Promise.all([
      fetch(API(`/analytics/pipeline?days=${days}`)).then(r => r.ok ? r.json() : null),
      fetch(API(`/analytics/sales?days=${days}`)).then(r => r.ok ? r.json() : null),
    ]).then(([p, s]) => { setPipeline(p); setSales(s); });
  }, [days]);

  useEffect(() => {
    Promise.all([
      fetch(API(`/content-analytics/vsl?days=${days}`)).then(r => r.ok ? r.json() : null),
      fetch(API(`/content-analytics/loom-outreach?days=${days}`)).then(r => r.ok ? r.json() : null),
    ]).then(([v, l]) => { setVslFunnel(v); setLoomFunnel(l); });
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

      {/* ── Overview / Campaigns sub-tabs ────────────────────────────── */}
      <div style={{ display: "flex", gap: 6 }}>
        {ANALYTICS_VIEW_TABS.map(t => (
          <button
            key={t.value}
            onClick={() => setView(t.value)}
            className={view === t.value ? "btn btn-primary" : "btn btn-secondary"}
            style={{ fontSize: 10, padding: "6px 16px" }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {view === "campaigns" ? (
        <CampaignsView days={days} />
      ) : (
      <>

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

      {/* ── Outreach & Appointment Setting ─────────────────────────── */}
      <div>
        <SecLabel>Outreach & Appointment Setting</SecLabel>
        <div style={{ display: "flex", flexDirection: "column", gap: 16, marginTop: 4 }}>
          <ColdCallingCard outreach={outreach} tab={days === 0 ? "all_time" : "period"} />
          <SmsOutreachCard outreach={outreach} tab={days === 0 ? "all_time" : "period"} />
          <EmailOutreachCard outreach={outreach} tab={days === 0 ? "all_time" : "period"} />
        </div>
      </div>

      {/* ── Sales Statistics ───────────────────────────────────────── */}
      <div>
        <SecLabel>Sales Statistics</SecLabel>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
          <MiniStat label="Appointments Booked" value={num(sales?.discovery_calls)} color="#5a9bf0" />
          <MiniStat label="Shows"               value={num(sales?.shows)}   color="#5a9bf0" />
          <MiniStat label="Show Rate"           value={sales?.discovery_calls ? `${Math.round((sales?.shows ?? 0) / sales.discovery_calls * 100)}%` : "—"} color="#14c882" />
          <MiniStat label="Close Rate"          value={sales?.close_rate != null ? `${sales.close_rate}%` : "—"} color="#14c882" />
          <MiniStat label="Total Revenue"       value={money(sales?.total_revenue)} color="#14c882" />
          <MiniStat label="Avg Deal Size"       value={money(sales?.avg_deal_size)} />
        </div>
      </div>

      {/* ── Content Engagement (VSL + Loom Outreach video tracking) ─── */}
      <div>
        <SecLabel>Content Engagement</SecLabel>
        <div style={{ display: "flex", flexDirection: "column", gap: 16, marginTop: 4 }}>
          <VslFunnelCard data={vslFunnel} />
          <LoomOutreachFunnelCard data={loomFunnel} />
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

      </>
      )}

    </div>
  );
}

function _pct(num, denom) {
  if (!denom) return null;
  return Math.round(num / denom * 100);
}
