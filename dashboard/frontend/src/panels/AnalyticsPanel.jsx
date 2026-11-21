import React, { useState, useEffect } from "react";
import { API } from "../api.js";
import DatePickerButton, { formatPickedDate } from "../components/DatePickerButton.jsx";
import CampaignModal from "../CampaignModal.jsx";
import RetentionView from "./RetentionView.jsx";
import { T, Card, PageHeader, SectionTitle, Tabs, Pill, Empty, inputStyle } from "../ui.jsx";

// Analytics (2026-11-21 redesign): headline KPIs first, then the funnel as
// one row per stage with its step conversion, then one card per outreach
// channel side by side (volume + bookings up top, rates as a short list),
// then content engagement and lead mix. Every number and endpoint is the
// same as before; only the presentation changed.

const pct = (v) => (v != null ? `${v}%` : "–");
const num = (v) => (v != null ? Number(v).toLocaleString() : "–");
const money = (v) => (v != null ? `$${Number(v).toLocaleString()}` : "–");

function _pct(n, d) {
  if (!d) return null;
  return Math.round((n / d) * 100);
}

// One color per channel so the cards read apart at a glance; green is
// reserved for bookings/wins and red for negative signals.
const CH = {
  calling: { name: "Cold calling", color: "#4d8ef0" },
  sms:     { name: "SMS", color: "#2dd4bf" },
  email:   { name: "Email", color: "#a78bfa" },
};

const ANALYTICS_PERIOD_OPTIONS = [[1, "Today"], [7, "7 days"], [30, "30 days"], [365, "1 year"], [0, "All time"]];
const PERIOD_TEXT = { 1: "Today", 7: "Last 7 days", 30: "Last 30 days", 365: "Last 12 months", 0: "All time" };

// ── Small building blocks ────────────────────────────────────────────────

function Segmented({ value, onChange, options }) {
  return (
    <div style={{ display: "inline-flex", flexWrap: "wrap", gap: 2, padding: 3, borderRadius: 11, background: "rgba(5,10,28,0.55)", border: `1px solid ${T.line}` }}>
      {options.map(([v, label]) => {
        const on = value === v;
        return (
          <button key={v} onClick={() => onChange(v)} style={{
            border: "none", cursor: "pointer", borderRadius: 8, padding: "6px 12px",
            fontFamily: T.font, fontSize: 12.5, fontWeight: on ? 600 : 500,
            background: on ? T.accent : "transparent", color: on ? "#fff" : T.textMute,
            transition: "background .15s, color .15s",
          }}>{label}</button>
        );
      })}
    </div>
  );
}

const ICON = {
  calendar: <><rect x="3" y="4" width="18" height="18" rx="2" /><path d="M16 2v4M8 2v4M3 10h18" /></>,
  check: <><path d="M20 6 9 17l-5-5" /></>,
  target: <><circle cx="12" cy="12" r="10" /><circle cx="12" cy="12" r="6" /><circle cx="12" cy="12" r="2" /></>,
  money: <><path d="M12 2v20" /><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" /></>,
};

function Kpi({ label, value, sub, color, icon }) {
  return (
    <div style={{
      borderRadius: 16, padding: "16px 18px 18px", minWidth: 0,
      background: `linear-gradient(160deg, ${color}22 0%, ${color}08 55%, rgba(255,255,255,0.015) 100%)`,
      border: `1px solid ${color}38`,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
        <span style={{ width: 28, height: 28, borderRadius: 8, display: "grid", placeItems: "center", background: `${color}22`, color, flexShrink: 0 }}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{icon}</svg>
        </span>
        <span style={{ fontSize: 13, fontWeight: 600, color: T.textDim }}>{label}</span>
      </div>
      <div style={{ fontFamily: T.display, fontSize: "clamp(26px, 5vw, 34px)", fontWeight: 700, color: T.text, letterSpacing: "-0.03em", lineHeight: 1, marginTop: 14, fontVariantNumeric: "tabular-nums" }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: 12.5, color: T.textMute, marginTop: 7 }}>{sub}</div>}
    </div>
  );
}

// ── Acquisition funnel: one row per stage ────────────────────────────────

function Funnel({ stages, loading }) {
  const n = stages.length;
  return (
    <div style={{ display: "grid", gap: 8 }}>
      {stages.map((s, i) => {
        // Bars narrow evenly so it reads as a funnel; the real drop-off is
        // the "% of previous" figure on the right.
        const width = 100 - (i * 58) / Math.max(1, n - 1);
        return (
          <div key={s.label} style={{ display: "grid", gridTemplateColumns: "minmax(82px, 18%) minmax(0, 1fr) minmax(60px, 10%)", gap: "clamp(8px, 2vw, 14px)", alignItems: "center" }}>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: T.text }}>{s.label}</div>
              {s.hint && <div style={{ fontSize: 11.5, color: T.textMute, marginTop: 1, lineHeight: 1.35 }}>{s.hint}</div>}
            </div>
            <div style={{ position: "relative", height: 40, display: "flex", justifyContent: "center" }}>
              <div style={{
                width: `${width}%`, height: "100%", borderRadius: 10,
                background: `linear-gradient(90deg, ${s.color}55, ${s.color}22)`, border: `1px solid ${s.color}55`,
              }} />
              <div style={{
                position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center",
                fontFamily: T.display, fontSize: "clamp(16px, 3.6vw, 19px)", fontWeight: 700, color: T.text,
                fontVariantNumeric: "tabular-nums", textShadow: "0 1px 6px rgba(0,0,0,.45)",
              }}>
                {loading ? "…" : num(s.value)}
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              {i === 0 ? (
                <span style={{ fontSize: 12, color: T.textMute }}>Start</span>
              ) : (
                <>
                  <div style={{ fontFamily: T.display, fontSize: 16, fontWeight: 700, color: s.rate != null ? s.color : T.textMute, fontVariantNumeric: "tabular-nums" }}>{pct(s.rate)}</div>
                  <div style={{ fontSize: 11, color: T.textMute }}>{s.rateLabel || "of previous"}</div>
                </>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Channel cards ────────────────────────────────────────────────────────

function MetricRow({ label, value, tone, hint }) {
  const color = tone === "bad" ? T.bad : tone === "good" ? T.good : T.text;
  return (
    <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 12, padding: "9px 0", borderTop: `1px solid ${T.line}` }}>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 13.5, color: T.textDim }}>{label}</div>
        {hint && <div style={{ fontSize: 11.5, color: T.textMute, marginTop: 1 }}>{hint}</div>}
      </div>
      <div style={{ fontFamily: T.display, fontSize: 15.5, fontWeight: 600, color, fontVariantNumeric: "tabular-nums", whiteSpace: "nowrap" }}>{value}</div>
    </div>
  );
}

function ChannelCard({ ch, volumeLabel, volume, booked, abr, rows, loading, note }) {
  const c = CH[ch];
  return (
    <Card pad={20} style={{ borderTop: `3px solid ${c.color}`, minWidth: 0 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
        <span style={{ width: 9, height: 9, borderRadius: "50%", background: c.color }} />
        <span style={{ fontFamily: T.display, fontSize: 16, fontWeight: 600, color: T.text }}>{c.name}</span>
      </div>
      {note && <div style={{ fontSize: 12, color: T.textMute, marginTop: 4, lineHeight: 1.45 }}>{note}</div>}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, margin: "16px 0 14px" }}>
        <div>
          <div style={{ fontSize: 12.5, color: T.textMute }}>{volumeLabel}</div>
          <div style={{ fontFamily: T.display, fontSize: 28, fontWeight: 700, color: T.text, letterSpacing: "-0.02em", fontVariantNumeric: "tabular-nums", lineHeight: 1.2 }}>
            {loading ? "…" : num(volume)}
          </div>
        </div>
        <div>
          <div style={{ fontSize: 12.5, color: T.textMute }}>Booked</div>
          <div style={{ fontFamily: T.display, fontSize: 28, fontWeight: 700, color: T.good, letterSpacing: "-0.02em", fontVariantNumeric: "tabular-nums", lineHeight: 1.2 }}>
            {loading ? "…" : num(booked)}
          </div>
          {!loading && <div style={{ fontSize: 12, color: T.textMute }}>{pct(abr)} booking rate</div>}
        </div>
      </div>

      <div>
        {rows.map((r) => <MetricRow key={r.label} {...r} value={loading ? "…" : r.value} />)}
      </div>
    </Card>
  );
}

function CallingCard({ m, loading }) {
  return (
    <ChannelCard ch="calling" loading={loading} volumeLabel="Calls made" volume={m.total} booked={m.booked} abr={m.abr}
      rows={[
        { label: "Answer rate", value: pct(m.answer_rate) },
        { label: "Pitch rate", value: pct(m.pitch_rate), hint: "Reached the decision maker" },
        { label: "Resonation rate", value: pct(m.resonation_rate), hint: "Of pitches that landed" },
      ]} />
  );
}

function SmsCard({ m, loading, note }) {
  return (
    <ChannelCard ch="sms" loading={loading} note={note} volumeLabel="Prospects texted" volume={m.total_outreach} booked={m.booked} abr={m.abr}
      rows={[
        { label: "Reply rate", value: pct(m.reply_rate) },
        { label: "Reached the owner", value: m.dm_reached != null ? `${num(m.dm_reached)} · ${pct(m.dm_reached_rate)}` : "–" },
        { label: "Primed", value: pct(m.primed_rate) },
        { label: "Engaged", value: pct(m.engaged_rate) },
        { label: "Interested", value: pct(m.interested_rate), tone: m.interested_rate > 0 ? "good" : undefined },
        { label: "Not interested", value: pct(m.not_interested_rate), tone: m.not_interested_rate > 0 ? "bad" : undefined },
      ]} />
  );
}

function EmailCard({ m, loading, note }) {
  return (
    <ChannelCard ch="email" loading={loading} note={note} volumeLabel="Prospects emailed" volume={m.total_sent} booked={m.booked} abr={m.abr}
      rows={[
        { label: "Reply rate", value: pct(m.reply_rate), hint: m.replied != null ? `${num(m.replied)} replied` : null },
        { label: "Watched the video", value: pct(m.video_play_rate), hint: m.video_plays != null ? `${num(m.video_plays)} pressed play` : null },
        { label: "Positive replies", value: pct(m.positive_reply_rate), tone: m.positive_reply_rate > 0 ? "good" : undefined },
        { label: "Unsubscribed", value: pct(m.unsubscribe_rate), tone: m.unsubscribe_rate > 2 ? "bad" : undefined },
        { label: "Not interested", value: pct(m.not_interested_rate), tone: m.not_interested_rate > 0 ? "bad" : undefined },
      ]} />
  );
}

// ── Campaigns tab ────────────────────────────────────────────────────────

const CAMPAIGN_CHANNEL_OPTIONS = [["sms", "SMS"], ["email", "Email"], ["calling", "Cold calling"]];

function fmtCampaignDate(iso) {
  if (!iso) return "now";
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

const selectStyle = { ...inputStyle, width: "auto", minWidth: 200, padding: "8px 12px", cursor: "pointer" };

function CampaignHeader({ detail, onReactivate }) {
  return (
    <Card pad={18} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
      <div style={{ minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <span style={{ fontFamily: T.display, fontSize: 17, fontWeight: 700, color: T.text }}>{detail.campaign.name}</span>
          <Pill tone={detail.campaign.is_active ? "good" : "neutral"} dot>{detail.campaign.is_active ? "Running" : "Ended"}</Pill>
        </div>
        <div style={{ fontSize: 12.5, color: T.textMute, marginTop: 5 }}>
          {detail.periods.map((p, i) => (
            <span key={i}>{i > 0 ? ", " : ""}{fmtCampaignDate(p.started_at)} – {fmtCampaignDate(p.ended_at)}</span>
          ))}
        </div>
      </div>
      {!detail.campaign.is_active && (
        <button className="btn btn-secondary" onClick={() => onReactivate(detail.campaign.id)}>Reactivate</button>
      )}
    </Card>
  );
}

function CampaignsView({ days, date }) {
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
    let stale = false;
    fetch(API(`/analytics/campaign/${selectedId}?days=${days}${date ? `&date=${date}` : ""}`)).then(r => r.ok ? r.json() : null).then(d => { if (!stale) setDetail(d); });
    return () => { stale = true; };
  }, [selectedId, days, date]);

  async function reactivate(id) {
    await fetch(API(`/campaigns/${id}/activate`), { method: "POST" });
    loadCampaigns(channel, selectedId);
    fetch(API(`/analytics/campaign/${selectedId}?days=${days}${date ? `&date=${date}` : ""}`)).then(r => r.ok ? r.json() : null).then(setDetail);
  }

  function onCampaignCreated(campaign) {
    if (campaign.channel === channel) {
      loadCampaigns(channel, campaign.id);
    } else {
      pendingSelectId.current = campaign.id;
      setChannel(campaign.channel);
    }
  }

  const m = detail?.metrics || {};
  const smsNote = (days !== 0 || date)
    ? `Owner reached / primed / engaged / interested count from when each box was ticked (${date ? formatPickedDate(date) : PERIOD_TEXT[days] || "this period"}). Boxes ticked before that tracking existed only show under All time.`
    : null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10 }}>
        <Segmented value={channel} onChange={setChannel} options={CAMPAIGN_CHANNEL_OPTIONS} />
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          {campaigns.length > 0 && (
            <select value={selectedId || ""} onChange={e => setSelectedId(Number(e.target.value))} style={selectStyle}>
              {campaigns.map(c => (
                <option key={c.id} value={c.id}>{c.name}{c.is_active ? " (running)" : ""}</option>
              ))}
            </select>
          )}
          <button className="btn btn-primary" onClick={() => setModalOpen(true)}>New campaign</button>
        </div>
      </div>

      <CampaignModal open={modalOpen} defaultChannel={channel} onClose={() => setModalOpen(false)} onCreated={onCampaignCreated} />

      {!campaigns.length && <Card><Empty>No {CH[channel].name.toLowerCase()} campaigns yet.</Empty></Card>}

      {detail && (
        <>
          <CampaignHeader detail={detail} onReactivate={reactivate} />
          <div style={{ maxWidth: 560 }}>
            {channel === "sms" && <SmsCard m={m} note={smsNote} />}
            {channel === "email" && <EmailCard m={m} />}
            {channel === "calling" && <CallingCard m={m} />}
          </div>
        </>
      )}
    </div>
  );
}

// ── Content engagement (VSL + Loom outreach) ─────────────────────────────

function StepStrip({ steps }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: `repeat(auto-fit, minmax(110px, 1fr))`, gap: 10 }}>
      {steps.map((s, i) => (
        <div key={s.label} style={{ borderRadius: 12, padding: "12px 14px", background: T.surface2, border: `1px solid ${T.line}`, minWidth: 0 }}>
          <div style={{ fontSize: 12.5, color: T.textMute }}>{s.label}</div>
          <div style={{ fontFamily: T.display, fontSize: 24, fontWeight: 700, color: s.good ? T.good : T.text, fontVariantNumeric: "tabular-nums", lineHeight: 1.25 }}>{num(s.value)}</div>
          <div style={{ fontSize: 11.5, color: T.textMute, minHeight: 15 }}>{i > 0 && s.rate != null ? `${s.rate}% ${s.rateOf || "of previous"}` : ""}</div>
        </div>
      ))}
    </div>
  );
}

// VSL funnel: every viewer of the /contact page's video, identified or
// anonymous (content_tracking.py's vsl_funnel).
function VslFunnel({ data }) {
  if (!data) return <Empty>Loading…</Empty>;
  return (
    <StepStrip steps={[
      { label: "Viewed", value: data.viewed },
      { label: "Watched 50%+", value: data.watched_half, rate: _pct(data.watched_half, data.viewed) },
      { label: "Finished", value: data.completed, rate: _pct(data.completed, data.watched_half) },
      { label: "Booked", value: data.booked, rate: data.booking_rate, rateOf: "of viewers", good: true },
    ]} />
  );
}

// Loom outreach funnel: only contacts actually sent a self-hosted outreach
// video (routers/content_tracking.py). Engaged/Interested are the manual
// CRM stage checkboxes.
function LoomFunnel({ data }) {
  if (!data) return <Empty>Loading…</Empty>;
  return (
    <StepStrip steps={[
      { label: "Sent", value: data.sent },
      { label: "Viewed", value: data.viewed, rate: _pct(data.viewed, data.sent) },
      { label: "Finished", value: data.completed, rate: _pct(data.completed, data.viewed) },
      { label: "Engaged", value: data.engaged, rate: _pct(data.engaged, data.completed) },
      { label: "Interested", value: data.interested, rate: _pct(data.interested, data.engaged) },
      { label: "Booked", value: data.booked, rate: _pct(data.booked, data.interested), good: true },
    ]} />
  );
}

const CONTENT_CHANNEL_OPTIONS = [["vsl", "Contact page video"], ["loom", "Loom outreach"]];
const CONTENT_CAMPAIGN_MODAL_CHANNELS = [
  { value: "vsl",  label: "VSL" },
  { value: "loom", label: "Loom Outreach" },
];

// Same flip-through-campaigns pattern as CampaignsView, for vsl/loom. A
// campaign here has no per-contact record (routers/campaigns.py): a VSL
// campaign captures every view while it's active, a Loom campaign every
// outreach video published while it's active.
function ContentCampaignsView() {
  const [channel, setChannel]       = useState("vsl");
  const [campaigns, setCampaigns]   = useState([]);
  const [selectedId, setSelectedId] = useState(null); // null = all time (unfiltered)
  const [detail, setDetail]         = useState(null);
  const [allTime, setAllTime]       = useState(null);
  const [modalOpen, setModalOpen]   = useState(false);
  const pendingSelectId = React.useRef(undefined);

  useEffect(() => {
    const path = channel === "vsl" ? "/content-analytics/vsl" : "/content-analytics/loom-outreach";
    fetch(API(`${path}?days=0`)).then(r => r.ok ? r.json() : null).then(setAllTime);
  }, [channel]);

  const loadCampaigns = (ch, selectId) => {
    fetch(API(`/campaigns?channel=${ch}`)).then(r => r.ok ? r.json() : []).then(list => {
      setCampaigns(list);
      // Default to the running campaign; all-time only when there are none.
      setSelectedId(selectId !== undefined ? selectId : (list.find(c => c.is_active)?.id ?? null));
    });
  };

  useEffect(() => {
    setDetail(null);
    loadCampaigns(channel, pendingSelectId.current);
    pendingSelectId.current = undefined;
  }, [channel]);

  useEffect(() => {
    if (selectedId == null) { setDetail(null); return; }
    fetch(API(`/analytics/campaign/${selectedId}?days=0`)).then(r => r.ok ? r.json() : null).then(setDetail);
  }, [selectedId]);

  async function reactivate(id) {
    await fetch(API(`/campaigns/${id}/activate`), { method: "POST" });
    loadCampaigns(channel, id);
  }

  function onCampaignCreated(campaign) {
    if (campaign.channel === channel) {
      loadCampaigns(channel, campaign.id);
    } else {
      pendingSelectId.current = campaign.id;
      setChannel(campaign.channel);
    }
  }

  const data = selectedId == null ? allTime : detail?.metrics;

  return (
    <Card pad={20}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10, marginBottom: 14 }}>
        <Segmented value={channel} onChange={setChannel} options={CONTENT_CHANNEL_OPTIONS} />
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <select value={selectedId ?? ""} onChange={e => setSelectedId(e.target.value === "" ? null : Number(e.target.value))} style={selectStyle}>
            <option value="">All time (every campaign)</option>
            {campaigns.map(c => (
              <option key={c.id} value={c.id}>{c.name}{c.is_active ? " (running)" : ""}</option>
            ))}
          </select>
          <button className="btn btn-secondary" onClick={() => setModalOpen(true)}>New {channel === "vsl" ? "VSL" : "Loom"} campaign</button>
        </div>
      </div>

      <CampaignModal open={modalOpen} defaultChannel={channel} channels={CONTENT_CAMPAIGN_MODAL_CHANNELS}
        onClose={() => setModalOpen(false)} onCreated={onCampaignCreated} />

      {selectedId != null && detail && (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10, marginBottom: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <span style={{ fontSize: 14, fontWeight: 600, color: T.text }}>{detail.campaign.name}</span>
            <Pill tone={detail.campaign.is_active ? "good" : "neutral"} dot>{detail.campaign.is_active ? "Running" : "Ended"}</Pill>
            <span style={{ fontSize: 12.5, color: T.textMute }}>
              {detail.periods.map((p, i) => (
                <span key={i}>{i > 0 ? ", " : ""}{fmtCampaignDate(p.started_at)} – {fmtCampaignDate(p.ended_at)}</span>
              ))}
            </span>
          </div>
          {!detail.campaign.is_active && (
            <button className="btn btn-secondary" onClick={() => reactivate(detail.campaign.id)}>Reactivate</button>
          )}
        </div>
      )}

      {channel === "loom" && <div style={{ fontSize: 12.5, color: T.textMute, marginBottom: 10 }}>Only prospects who were actually sent an outreach video.</div>}
      {channel === "vsl" ? <VslFunnel data={data} /> : <LoomFunnel data={data} />}
    </Card>
  );
}

// ── Leads: grades + states ───────────────────────────────────────────────

const GRADE_COLOR = { A: T.good, B: T.accent, C: T.warn };

function GradeTable({ rows }) {
  if (!rows?.length) return <Empty>No grade data yet.</Empty>;
  const th = { fontSize: 12, fontWeight: 500, color: T.textMute, padding: "0 0 8px", textAlign: "right" };
  const td = { fontSize: 14, color: T.text, padding: "10px 0", textAlign: "right", borderTop: `1px solid ${T.line}`, fontVariantNumeric: "tabular-nums" };
  return (
    <table style={{ width: "100%", borderCollapse: "collapse" }}>
      <thead>
        <tr>
          <th style={{ ...th, textAlign: "left" }}>Grade</th>
          <th style={th}>Leads</th>
          <th style={th}>Booked</th>
          <th style={th}>Booking rate</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(g => (
          <tr key={g.grade}>
            <td style={{ ...td, textAlign: "left" }}>
              <span style={{ display: "inline-grid", placeItems: "center", width: 26, height: 26, borderRadius: 8, fontWeight: 700, fontSize: 13,
                color: GRADE_COLOR[g.grade] || T.textDim, background: `${GRADE_COLOR[g.grade] || T.textDim}1f` }}>{g.grade}</span>
            </td>
            <td style={td}>{num(g.cnt)}</td>
            <td style={{ ...td, color: g.booked ? T.good : T.textMute }}>{num(g.booked)}</td>
            <td style={{ ...td, fontWeight: 600, color: g.book_rate > 0 ? T.good : T.textMute }}>{g.book_rate}%</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function TopStates({ states }) {
  if (!states?.length) return <Empty>No location data yet.</Empty>;
  const max = states[0]?.cnt || 1;
  return (
    <div style={{ display: "grid", gap: 10 }}>
      {states.map((s, i) => (
        <div key={s.state} style={{ display: "grid", gridTemplateColumns: "minmax(80px, 130px) minmax(0, 1fr) 48px", gap: 12, alignItems: "center" }}>
          <span style={{ fontSize: 13.5, color: T.textDim, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{s.state}</span>
          <div style={{ height: 8, borderRadius: 99, background: "rgba(169,186,216,0.08)", overflow: "hidden" }}>
            <div style={{ width: `${Math.max(3, (s.cnt / max) * 100)}%`, height: "100%", borderRadius: 99, background: i === 0 ? T.accent : `${T.accent}88` }} />
          </div>
          <span style={{ fontFamily: T.display, fontSize: 14, fontWeight: 600, color: T.text, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{num(s.cnt)}</span>
        </div>
      ))}
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────

const ANALYTICS_VIEW_TABS = [
  { id: "overview",  label: "Overview" },
  { id: "campaigns", label: "Campaigns" },
  { id: "retention", label: "Client retention" },
];

export default function AnalyticsPanel() {
  const [view, setView]               = useState("overview");
  const [days, setDays]               = useState(0);
  const [date, setDate]               = useState(null); // a picked day overrides `days`
  const [outreach, setOutreach]       = useState(null);
  const [pipeline, setPipeline]       = useState(null);
  const [sales, setSales]             = useState(null);

  const dateQs = date ? `&date=${date}` : "";
  const pickPeriod = (d) => { setDays(d); setDate(null); };
  const outreachTab = days === 0 && !date ? "all_time" : "period";
  const periodLabel = date ? formatPickedDate(date) : PERIOD_TEXT[days];

  // `stale` drops a response that lands after the period changed again.
  useEffect(() => {
    let stale = false;
    setOutreach(null);
    fetch(API(`/analytics/outreach?days=${days}${dateQs}`)).then(r => r.ok ? r.json() : null).then(o => { if (!stale) setOutreach(o); });
    return () => { stale = true; };
  }, [days, date]);

  useEffect(() => {
    let stale = false;
    Promise.all([
      fetch(API(`/analytics/pipeline?days=${days}${dateQs}`)).then(r => r.ok ? r.json() : null),
      fetch(API(`/analytics/sales?days=${days}${dateQs}`)).then(r => r.ok ? r.json() : null),
    ]).then(([p, s]) => { if (!stale) { setPipeline(p); setSales(s); } });
    return () => { stale = true; };
  }, [days, date]);

  const funnel = pipeline?.funnel ?? {};
  // Shows ÷ calls with a marked outcome, not ÷ booked — upcoming and
  // unmarked calls aren't no-shows.
  const showOutcomes = (funnel.shows ?? 0) + (funnel.no_shows ?? 0);
  const stages = [
    { label: "Leads", hint: "In your CRM", value: funnel.total_leads, color: "#4d8ef0" },
    { label: "Outreach", hint: "First call, text or email", value: funnel.dialed, rate: funnel.total_leads ? _pct(funnel.dialed, funnel.total_leads) : null, color: "#4d8ef0" },
    { label: "Answered", hint: "Picked up or replied", value: funnel.answered, rate: funnel.dialed ? _pct(funnel.answered, funnel.dialed) : null, color: "#2dd4bf" },
    { label: "Pitched", hint: "Reached owner or watched video", value: funnel.pitched, rate: funnel.answered ? _pct(funnel.pitched, funnel.answered) : null, color: "#2dd4bf" },
    { label: "Booked", hint: "Sales calls booked", value: funnel.booked, rate: funnel.pitched ? _pct(funnel.booked, funnel.pitched) : null, color: T.good },
    { label: "Showed", hint: "Of calls with an outcome", value: funnel.shows, rate: showOutcomes ? _pct(funnel.shows, showOutcomes) : null, rateLabel: "show rate", color: T.warn },
    { label: "Closed", hint: "New clients", value: funnel.closes, rate: funnel.shows ? _pct(funnel.closes, funnel.shows) : null, rateLabel: "of shows", color: T.warn },
  ];

  const tabData = (ch) => outreach?.[ch]?.[outreachTab] ?? {};
  const showRate = (sales?.shows ?? 0) + (sales?.no_shows ?? 0) > 0 ? Math.round(sales.show_rate) : null;

  return (
    <div className="px-4 py-4 sm:px-6 sm:py-6" style={{ flex: 1, overflowY: "auto" }}>
      <div style={{ maxWidth: 1240, margin: "0 auto", display: "flex", flexDirection: "column", gap: 22 }}>

        <PageHeader
          title="Analytics"
          subtitle={`Outreach and client acquisition · ${periodLabel}`}
          actions={<>
            <Segmented value={date ? null : days} onChange={pickPeriod} options={ANALYTICS_PERIOD_OPTIONS} />
            <DatePickerButton date={date} setDate={setDate} />
          </>}
        />

        <Tabs tabs={ANALYTICS_VIEW_TABS} value={view} onChange={setView} style={{ marginTop: -8, overflowY: "hidden" }} />

        {view === "retention" ? (
          <RetentionView days={days} date={date} />
        ) : view === "campaigns" ? (
          <CampaignsView days={days} date={date} />
        ) : (
          <>
            {/* Headline numbers */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(150px, 45%), 1fr))", gap: 12 }}>
              <Kpi label="Calls booked" value={num(sales?.discovery_calls)} color={T.accent} icon={ICON.calendar}
                sub={sales ? `${num(sales.shows)} showed up` : null} />
              <Kpi label="Show rate" value={showRate != null ? `${showRate}%` : "–"} color={T.warn} icon={ICON.check}
                sub={sales ? `${num(sales.no_shows)} no-shows` : null} />
              <Kpi label="Close rate" value={pct(sales?.close_rate)} color={T.good} icon={ICON.target}
                sub={sales ? `${num(sales.closes)} closed of those who showed` : null} />
              <Kpi label="Revenue" value={money(sales?.total_revenue)} color="#a78bfa" icon={ICON.money}
                sub={sales?.avg_deal_size != null ? `${money(sales.avg_deal_size)} average deal` : null} />
            </div>

            {/* Funnel */}
            <Card pad={22}>
              <SectionTitle title="Acquisition funnel" hint="Every channel combined. The right column is how many made it from the stage above." />
              <div style={{ marginTop: 8 }}>
                <Funnel stages={stages} loading={!pipeline} />
              </div>
            </Card>

            {/* Channels */}
            <div>
              <SectionTitle title="Outreach by channel" hint="Each booking counts once, under the channel that won it. Email gets it when they watched the emailed video first." />
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(290px, 1fr))", gap: 14, alignItems: "start" }}>
                <CallingCard m={tabData("calling")} loading={!outreach} />
                <SmsCard m={tabData("sms")} loading={!outreach} />
                <EmailCard m={tabData("email")} loading={!outreach} />
              </div>
            </div>

            {/* Content */}
            <div>
              <SectionTitle title="Video engagement" hint="How far people get through your videos, and how many book after." />
              <ContentCampaignsView />
            </div>

            {/* Leads */}
            <div>
              <SectionTitle title="Your leads"
                right={pipeline && <span style={{ fontSize: 12.5, color: T.textMute }}>
                  <b style={{ color: T.text }}>{num(pipeline.new_this_week ?? 0)}</b> new this week · <b style={{ color: T.text }}>{num(pipeline.new_this_month ?? 0)}</b> this month
                </span>} />
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 14, alignItems: "start" }}>
                <Card pad={20}>
                  <div style={{ fontFamily: T.display, fontSize: 15, fontWeight: 600, color: T.text, marginBottom: 12 }}>By grade</div>
                  <GradeTable rows={pipeline?.by_grade} />
                </Card>
                <Card pad={20}>
                  <div style={{ fontFamily: T.display, fontSize: 15, fontWeight: 600, color: T.text, marginBottom: 12 }}>Top states</div>
                  <TopStates states={pipeline?.top_states} />
                </Card>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
