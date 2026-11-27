import React, { useState, useEffect } from "react";
import { API } from "../api.js";
import DatePickerButton, { formatPickedDate } from "../components/DatePickerButton.jsx";
import CampaignModal from "../CampaignModal.jsx";
import RetentionView from "./RetentionView.jsx";
import { T, Card, PageHeader, SectionTitle, Tabs, Pill, Empty, inputStyle, PERIOD_OPTIONS, PERIOD_TEXT } from "../ui.jsx";

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
  sales:   { name: "Sales", color: "#f2ad3d" },
};

const ANALYTICS_PERIOD_OPTIONS = PERIOD_OPTIONS; // shared with Finances (ui.jsx)

// ── Small building blocks ────────────────────────────────────────────────

function Segmented({ value, onChange, options }) {
  return (
    <div style={{ display: "inline-flex", flexWrap: "wrap", gap: 2, padding: 3, borderRadius: 11, background: "rgba(5,10,28,0.55)", border: `1px solid ${T.line}` }}>
      {options.map(([v, label]) => {
        const on = value === v;
        return (
          <button key={v} onClick={() => onChange(v)} style={{
            border: "none", cursor: "pointer", borderRadius: 8, padding: "6px 10px",
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
  trend: <><path d="M22 7 13.5 15.5 8.5 10.5 2 17" /><path d="M16 7h6v6" /></>,
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

// ── Comparison table (channels on Overview, campaigns on Campaigns) ──────

function useNarrow(px = 600) {
  const [narrow, setNarrow] = useState(() => typeof window !== "undefined" && window.innerWidth < px);
  useEffect(() => {
    const on = () => setNarrow(window.innerWidth < px);
    window.addEventListener("resize", on);
    return () => window.removeEventListener("resize", on);
  }, [px]);
  return narrow;
}

// One column per thing being compared, one row per metric, read straight
// across. `best` rows highlight the top value in that column's color; a
// dash = that column doesn't track the metric. columns: [{ key, color,
// title, short, sub }]; rows: [{ label, hint, vals[], fmt, tone, strong, best }].
// Many columns (campaigns) scroll sideways with the metric column pinned.
function ComparisonTable({ columns, rows, loading }) {
  const narrow = useNarrow();
  const scrolls = columns.length > 3;
  const colW = narrow ? 92 : 150;
  const metricW = narrow ? 118 : 210;
  const minWidth = scrolls ? metricW + columns.length * colW : undefined;
  const cell = { padding: narrow ? "11px 6px" : "12px 14px", textAlign: "right", borderTop: `1px solid ${T.line}`, fontVariantNumeric: "tabular-nums", whiteSpace: "nowrap" };
  // Pinned metric column needs a solid background to cover cells sliding under it.
  const pin = scrolls ? { position: "sticky", left: 0, zIndex: 1, background: "#0c1536" } : {};

  // One or two columns: shrink the card so values sit near their labels
  // instead of across a wide empty table.
  const fewMax = columns.length < 3 && !narrow ? 300 + columns.length * 240 : undefined;

  return (
    <Card pad={0} style={{ overflow: "hidden", maxWidth: fewMax }}>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", minWidth, borderCollapse: "collapse", tableLayout: scrolls ? "fixed" : "auto" }}>
          <thead>
            <tr>
              <th style={{ ...pin, width: scrolls ? metricW : undefined, padding: narrow ? "14px 6px 10px 14px" : "16px 14px 12px 20px", textAlign: "left", verticalAlign: "bottom", fontSize: 12.5, fontWeight: 500, color: T.textMute }}>Metric</th>
              {columns.map(col => (
                <th key={col.key} style={{ width: scrolls ? colW : (narrow ? "21%" : "19%"), padding: narrow ? "14px 6px 10px" : "16px 14px 12px", textAlign: "right", verticalAlign: "bottom" }}>
                  <div style={{ fontFamily: T.display, fontSize: narrow ? 13 : 14.5, fontWeight: 600, color: T.text, whiteSpace: scrolls ? "normal" : "nowrap", textAlign: "right", lineHeight: 1.3 }}>
                    <span style={{ display: "inline-block", width: 8, height: 8, borderRadius: "50%", background: col.color, marginRight: narrow ? 5 : 7, verticalAlign: "middle", position: "relative", top: -1 }} />
                    {narrow && col.short ? col.short : col.title}
                  </div>
                  {col.sub && <div style={{ marginTop: 5, fontSize: 11.5, fontWeight: 400, color: T.textMute, whiteSpace: "normal" }}>{col.sub}</div>}
                  <div style={{ height: 3, borderRadius: 99, background: col.color, marginTop: 8, opacity: 0.7 }} />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(r => {
              const present = r.vals.filter(v => v != null);
              const top = r.best && present.length > 1 ? Math.max(...present) : null;
              const tint = r.strong ? "rgba(47,208,143,0.045)" : "transparent";
              return (
                <tr key={r.label} style={{ background: tint }}>
                  <td style={{ ...cell, ...pin, ...(scrolls && r.strong ? { background: "#0d1c38" } : {}), textAlign: "left", paddingLeft: narrow ? 14 : 20, whiteSpace: "normal" }}>
                    <div style={{ fontSize: narrow ? 13 : 14, fontWeight: r.strong ? 600 : 500, color: r.strong ? T.text : T.textDim }}>{r.label}</div>
                    {r.hint && !narrow && <div style={{ fontSize: 11.5, color: T.textMute, marginTop: 2 }}>{r.hint}</div>}
                  </td>
                  {r.vals.map((v, i) => {
                    const col = columns[i];
                    const isTop = top != null && v === top && top > 0;
                    const color = v == null ? T.textMute
                      : r.tone === "bad" ? (v > 0 ? T.bad : T.textDim)
                      : r.tone === "good" ? T.good : T.text;
                    return (
                      <td key={col.key} style={cell}>
                        <span style={{
                          fontFamily: T.display, fontSize: narrow ? (r.strong ? 15.5 : 13.5) : (r.strong ? 18 : 15.5), fontWeight: r.strong ? 700 : 600, color,
                          padding: narrow ? "2px 5px" : "3px 9px", borderRadius: 8,
                          background: isTop ? `${col.color}24` : "transparent",
                          boxShadow: isTop ? `inset 0 0 0 1px ${col.color}55` : "none",
                        }}>
                          {loading ? "…" : v == null ? "–" : r.fmt(v)}
                        </span>
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

const CHANNEL_COLUMNS = [
  { key: "calling", color: CH.calling.color, title: CH.calling.name, short: "Calls" },
  { key: "sms", color: CH.sms.color, title: CH.sms.name },
  { key: "email", color: CH.email.color, title: CH.email.name },
];

function ChannelTable({ calling: c, sms: s, email: e, loading }) {
  const rows = [
    { label: "Reached out to", vals: [c.total, s.total_outreach, e.total_sent], fmt: num, hint: "Calls made · prospects texted · prospects emailed" },
    { label: "Answered / replied", vals: [c.answer_rate, s.reply_rate, e.reply_rate], fmt: pct, best: true },
    { label: "Reached the owner", vals: [c.pitch_rate, s.dm_reached_rate, e.video_play_rate], fmt: pct, best: true, hint: "Email: watched the video" },
    { label: "Interested", vals: [c.resonation_rate, s.interested_rate, e.positive_reply_rate], fmt: pct, best: true, hint: "Calling: pitch resonated · Email: positive reply" },
    { label: "Booked", vals: [c.booked, s.booked, e.booked], fmt: num, tone: "good", strong: true, best: true },
    { label: "ABR", vals: [c.abr, s.abr, e.abr], fmt: pct, tone: "good", strong: true, best: true, hint: "Booked ÷ reached out to" },
    { label: "Not interested", vals: [null, s.not_interested_rate, e.not_interested_rate], fmt: pct, tone: "bad" },
    { label: "Unsubscribed", vals: [null, null, e.unsubscribe_rate], fmt: pct, tone: "bad" },
  ];
  return <ComparisonTable columns={CHANNEL_COLUMNS} rows={rows} loading={loading} />;
}

// Metric rows per campaign channel; `ms` = each campaign's metrics, in column order.
function campaignRows(channel, ms) {
  const col = (k) => ms.map(m => (m ? m[k] ?? null : null));
  // Sales (sales_tracking.campaign_metrics): first discovery calls booked
  // while the campaign ran; a close on a follow-up call counts for the first.
  if (channel === "sales") return [
    { label: "Calls booked", vals: col("booked"), fmt: num, hint: "Follow-up calls not counted" },
    { label: "Show rate", vals: col("show_rate"), fmt: pct, best: true },
    { label: "Closed", vals: col("closes"), fmt: num, tone: "good", strong: true, best: true },
    { label: "Close rate", vals: col("close_rate"), fmt: pct, tone: "good", strong: true, best: true, hint: "Of calls that showed" },
    { label: "Two-call closes", vals: col("two_call_closes"), fmt: num, hint: "Second call booked" },
    { label: "Revenue", vals: col("total_revenue"), fmt: money, best: true },
    { label: "Avg call length", vals: col("avg_call_minutes"), fmt: v => `${v} min` },
  ];
  if (channel === "calling") return [
    { label: "Calls made", vals: col("total"), fmt: num },
    { label: "Answer rate", vals: col("answer_rate"), fmt: pct, best: true },
    { label: "Pitch rate", vals: col("pitch_rate"), fmt: pct, best: true, hint: "Reached the decision maker" },
    { label: "Resonation rate", vals: col("resonation_rate"), fmt: pct, best: true, hint: "Of pitches that landed" },
    { label: "Booked", vals: col("booked"), fmt: num, tone: "good", strong: true, best: true },
    { label: "ABR", vals: col("abr"), fmt: pct, tone: "good", strong: true, best: true, hint: "Booked ÷ calls made" },
  ];
  if (channel === "email") return [
    { label: "Prospects emailed", vals: col("total_sent"), fmt: num },
    { label: "Reply rate", vals: col("reply_rate"), fmt: pct, best: true },
    { label: "Watched the video", vals: col("video_play_rate"), fmt: pct, best: true },
    { label: "Positive replies", vals: col("positive_reply_rate"), fmt: pct, best: true },
    { label: "Booked", vals: col("booked"), fmt: num, tone: "good", strong: true, best: true },
    { label: "ABR", vals: col("abr"), fmt: pct, tone: "good", strong: true, best: true, hint: "Booked ÷ prospects emailed" },
    { label: "Not interested", vals: col("not_interested_rate"), fmt: pct, tone: "bad" },
    { label: "Unsubscribed", vals: col("unsubscribe_rate"), fmt: pct, tone: "bad" },
  ];
  return [
    { label: "Prospects texted", vals: col("total_outreach"), fmt: num },
    { label: "Reply rate", vals: col("reply_rate"), fmt: pct, best: true },
    { label: "Reached the owner", vals: col("dm_reached_rate"), fmt: pct, best: true },
    { label: "Primed", vals: col("primed_rate"), fmt: pct, best: true },
    { label: "Engaged", vals: col("engaged_rate"), fmt: pct, best: true },
    { label: "Interested", vals: col("interested_rate"), fmt: pct, best: true },
    { label: "Booked", vals: col("booked"), fmt: num, tone: "good", strong: true, best: true },
    { label: "ABR", vals: col("abr"), fmt: pct, tone: "good", strong: true, best: true, hint: "Booked ÷ prospects texted" },
    { label: "Not interested", vals: col("not_interested_rate"), fmt: pct, tone: "bad" },
  ];
}

// ── Campaigns tab ────────────────────────────────────────────────────────

const CAMPAIGN_CHANNEL_OPTIONS = [["sms", "SMS"], ["email", "Email"], ["calling", "Cold calling"], ["sales", "Sales"]];
const CAMPAIGN_COLORS = ["#4d8ef0", "#2dd4bf", "#a78bfa", "#f2ad3d", "#f472b6", "#38bdf8", "#a3e635", "#fb923c"];

function fmtCampaignDate(iso) {
  if (!iso) return "now";
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

const selectStyle = { ...inputStyle, width: "auto", minWidth: 200, padding: "8px 12px", cursor: "pointer" };

// Everything else about the campaign, grouped and quieter than the tiles.
function SalesMoreStats({ m }) {
  const groups = [
    { title: "Calls", rows: [
      ["Showed", num(m.shows)],
      ["No-shows", num(m.no_shows), m.no_shows ? T.bad : null],
      ["Upcoming", num(m.upcoming)],
      ["Waiting on an outcome", num(m.awaiting_outcome), m.awaiting_outcome ? T.warn : null],
    ] },
    { title: "Closing", rows: [
      ["Closed on the first call", num(m.closed_on_first_call)],
      ["Closed on a follow-up", num(m.closed_on_follow_up)],
      ["Not closed", num(m.not_closed)],
      ["Booked → closed", pct(m.booked_to_close)],
    ] },
    { title: "Two-call closes", rows: [
      ["Two-call closes", num(m.two_call_closes)],
      ["Closed on the 2nd call", num(m.two_call_won), m.two_call_won ? T.good : null],
      ["Didn't close", num(m.two_call_lost)],
      ["Waiting on the 2nd call", num(m.two_call_open)],
    ] },
    { title: "Calls and deals", rows: [
      ["Avg call length", m.avg_call_minutes != null ? `${m.avg_call_minutes} min` : "–"],
      ["Calls recorded", `${num(m.calls_recorded)} of ${num(m.shows)}`],
      ["Avg deal size", money(m.avg_deal_size)],
    ] },
  ];
  return (
    <Card pad={0} style={{ overflow: "hidden" }}>
      <div style={{ padding: "14px 18px 0", fontFamily: T.display, fontSize: 14.5, fontWeight: 600, color: T.text }}>More stats</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))" }}>
        {groups.map(g => (
          <div key={g.title} style={{ padding: "12px 18px 16px" }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: T.textMute, marginBottom: 6 }}>{g.title}</div>
            {g.rows.map(([label, value, color]) => (
              <div key={label} style={{ display: "flex", justifyContent: "space-between", gap: 12, padding: "6px 0", borderTop: `1px solid ${T.line}`, fontSize: 13 }}>
                <span style={{ color: T.textDim }}>{label}</span>
                <span style={{ color: color || T.text, fontWeight: 600, fontVariantNumeric: "tabular-nums", whiteSpace: "nowrap" }}>{value}</span>
              </div>
            ))}
          </div>
        ))}
      </div>
    </Card>
  );
}

// Sales: the running campaign's headline numbers as tiles, then (only once
// there's more than one campaign) the side-by-side comparison.
function SalesCampaigns({ campaigns, details, columns, rows, loading, periodNote, onStop, onReactivate }) {
  const current = campaigns.find(c => c.is_active) || campaigns[0];
  const m = details[current.id]?.metrics;
  const v = (x, f) => (loading || !m ? "…" : f(x));
  const since = current.periods?.[0]?.started_at;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div>
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", marginBottom: 12 }}>
          <span style={{ fontFamily: T.display, fontSize: 17, fontWeight: 700, color: T.text }}>{current.name}</span>
          <Pill tone={current.is_active ? "good" : "neutral"} dot style={{ fontSize: 11, padding: "2px 8px" }}>{current.is_active ? "Running" : "Ended"}</Pill>
          <span style={{ fontSize: 12.5, color: T.textMute }}>
            {since ? `Since ${fmtCampaignDate(since)}` : ""}{periodNote ? ` · ${periodNote}` : ""}
          </span>
          {current.is_active ? (
            <button onClick={() => onStop(current)} style={{ marginLeft: "auto", background: "none", border: "none", padding: 0, cursor: "pointer", color: T.bad, fontSize: 12.5, fontWeight: 600 }}>Stop</button>
          ) : (
            <button onClick={() => onReactivate(current.id)} style={{ marginLeft: "auto", background: "none", border: "none", padding: 0, cursor: "pointer", color: T.accent, fontSize: 12.5, fontWeight: 600 }}>Reactivate</button>
          )}
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 12 }}>
          <Kpi label="Calls booked" icon={ICON.target} color={CH.sales.color} value={v(m?.booked, num)} sub="Follow-up calls not counted" />
          <Kpi label="Show rate" icon={ICON.check} color="#4d8ef0" value={v(m?.show_rate, pct)} sub={m ? `${m.shows} showed · ${m.no_shows} no-show${m.no_shows === 1 ? "" : "s"}` : null} />
          <Kpi label="Close rate" icon={ICON.trend} color={T.good} value={v(m?.close_rate, pct)} sub={m ? `${m.closes} closed of ${m.shows} who showed` : null} />
          <Kpi label="Revenue" icon={ICON.money} color="#a78bfa" value={v(m?.total_revenue, money)} sub={m && m.closes ? `${money(m.avg_deal_size)} avg deal` : null} />
        </div>
      </div>

      {m && <SalesMoreStats m={m} />}

      {campaigns.length > 1 && (
        <div>
          <SectionTitle title="Compare campaigns" hint="The highlighted value is the best campaign on that row." />
          <ComparisonTable columns={columns} rows={rows} loading={loading} />
        </div>
      )}
    </div>
  );
}

// Every campaign in the chosen channel side by side (running one first),
// each column with its own dates + Running/Ended, so they compare at a glance.
function CampaignsView({ days, date }) {
  const [channel, setChannel]     = useState("sms");
  const [campaigns, setCampaigns] = useState(null);
  const [details, setDetails]     = useState({}); // campaign id -> /analytics/campaign response
  const [modalOpen, setModalOpen] = useState(false);
  const [reload, setReload]       = useState(0);

  useEffect(() => {
    let stale = false;
    setCampaigns(null);
    fetch(API(`/campaigns?channel=${channel}`)).then(r => r.ok ? r.json() : []).then(list => {
      if (!stale) setCampaigns([...list].sort((a, b) => (b.is_active ? 1 : 0) - (a.is_active ? 1 : 0)));
    });
    return () => { stale = true; };
  }, [channel, reload]);

  useEffect(() => {
    if (!campaigns?.length) { setDetails({}); return; }
    let stale = false;
    setDetails({});
    Promise.all(campaigns.map(c =>
      fetch(API(`/analytics/campaign/${c.id}?days=${days}${date ? `&date=${date}` : ""}`)).then(r => r.ok ? r.json() : null).then(d => [c.id, d])
    )).then(pairs => { if (!stale) setDetails(Object.fromEntries(pairs)); });
    return () => { stale = true; };
  }, [campaigns, days, date]);

  async function reactivate(id) {
    await fetch(API(`/campaigns/${id}/activate`), { method: "POST" });
    setReload(n => n + 1);
  }

  async function stop(c) {
    const what = channel === "sales" ? "sales calls" : `${CH[channel].name.toLowerCase()} outreach`;
    if (!window.confirm(`Stop "${c.name}"? Its stats stay. New ${what} won't count toward any campaign until you reactivate one or start a new one.`)) return;
    await fetch(API(`/campaigns/${c.id}/stop`), { method: "POST" });
    setReload(n => n + 1);
  }

  function onCampaignCreated(campaign) {
    if (campaign.channel === channel) setReload(n => n + 1);
    else setChannel(campaign.channel);
  }

  const loading = campaigns != null && campaigns.length > 0 && Object.keys(details).length === 0;
  const columns = (campaigns || []).map((c, i) => {
    const d = details[c.id];
    return {
      key: c.id,
      color: CAMPAIGN_COLORS[i % CAMPAIGN_COLORS.length],
      title: c.name,
      sub: (
        <span style={{ display: "inline-flex", flexDirection: "column", alignItems: "flex-end", gap: 5 }}>
          <Pill tone={c.is_active ? "good" : "neutral"} dot style={{ fontSize: 11, padding: "2px 8px" }}>{c.is_active ? "Running" : "Ended"}</Pill>
          {d?.periods?.length > 0 && <span>{d.periods.map((p, j) => `${j ? ", " : ""}${fmtCampaignDate(p.started_at)} – ${fmtCampaignDate(p.ended_at)}`).join("")}</span>}
          {c.is_active ? (
            <button onClick={() => stop(c)} style={{ background: "none", border: "none", padding: 0, cursor: "pointer", color: T.bad, fontSize: 11.5, fontWeight: 600 }}>Stop</button>
          ) : (
            <button onClick={() => reactivate(c.id)} style={{ background: "none", border: "none", padding: 0, cursor: "pointer", color: T.accent, fontSize: 11.5, fontWeight: 600 }}>Reactivate</button>
          )}
        </span>
      ),
    };
  });
  const rows = campaignRows(channel, (campaigns || []).map(c => details[c.id]?.metrics));
  const smsNote = channel === "sms" && (days !== 0 || date)
    ? `Owner reached / primed / engaged / interested count from when each box was ticked (${date ? formatPickedDate(date) : PERIOD_TEXT[days] || "this period"}). Boxes ticked before that tracking existed only show under All time.`
    : null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10 }}>
        <Segmented value={channel} onChange={setChannel} options={CAMPAIGN_CHANNEL_OPTIONS} />
        <button className="btn btn-primary" onClick={() => setModalOpen(true)}>New campaign</button>
      </div>

      <CampaignModal open={modalOpen} defaultChannel={channel} onClose={() => setModalOpen(false)} onCreated={onCampaignCreated} />

      {campaigns == null ? (
        <Card><Empty>Loading…</Empty></Card>
      ) : !campaigns.length ? (
        <Card><Empty>No {CH[channel].name.toLowerCase()} campaigns yet.</Empty></Card>
      ) : channel === "sales" ? (
        <SalesCampaigns campaigns={campaigns} details={details} columns={columns} rows={rows} loading={loading}
          periodNote={days !== 0 || date ? `Calls held ${date ? `on ${formatPickedDate(date)}` : (PERIOD_TEXT[days] || "this period").toLowerCase()}` : null}
          onStop={stop} onReactivate={reactivate} />
      ) : (
        <div>
          <SectionTitle title={`${CH[channel].name} campaigns`}
            hint={`Read across to compare. The highlighted value is the best campaign on that row.${columns.length > 3 ? " Scroll sideways for older campaigns." : ""}`} />
          {smsNote && <div style={{ fontSize: 12, color: T.textMute, margin: "-4px 0 10px", lineHeight: 1.45 }}>{smsNote}</div>}
          <ComparisonTable columns={columns} rows={rows} loading={loading} />
        </div>
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

// ── Booking link (Dylan's own booking page, booking.digigrowthllc.com/discovery-call) ──
// Visitors -> picked a time -> booked, overall and per channel. Channel comes
// from the link's tag (?utm_source= on the website, ?via= on texts/emails the
// OS sends) or the referring site; Dylan's own visits are left out server-side.

const BOOKING_CH_COLOR = {
  email: CH.email.color, sms: CH.sms.color, website: "#4d8ef0", social: "#f472b6",
  video: "#f2ad3d", pages: "#38bdf8", other: "#a3e635", direct: "#8b93b5",
};
const BOOKING_CH_SHORT = { sms: "SMS", social: "Social", direct: "Direct", video: "Video", pages: "Pages" };

function BookingLinkView({ days, date }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    let stale = false;
    setData(null);
    fetch(API(`/personal-booking/analytics?days=${days}${date ? `&date=${date}` : ""}`))
      .then(r => r.ok ? r.json() : null).then(d => { if (!stale) setData(d || { error: true }); })
      .catch(() => { if (!stale) setData({ error: true }); });
    return () => { stale = true; };
  }, [days, date]);

  if (data?.error) return <Card pad={20}><Empty>Couldn't load booking link analytics.</Empty></Card>;
  const t = data?.total ?? {};
  const loading = !data;
  const chs = data?.channels ?? [];
  const columns = chs.map(c => ({ key: c.key, color: BOOKING_CH_COLOR[c.key] || T.accent, title: c.label, short: BOOKING_CH_SHORT[c.key] }));
  const rows = [
    { label: "Visitors", hint: "People who opened the link", vals: chs.map(c => c.visitors), fmt: num },
    { label: "Picked a time", vals: chs.map(c => c.pick_rate), fmt: pct, best: true, hint: "Of visitors" },
    { label: "Booked", vals: chs.map(c => c.booked), fmt: num, tone: "good" },
    { label: "Conversion rate", vals: chs.map(c => c.conversion_rate), fmt: pct, best: true, strong: true, hint: "Booked ÷ visitors" },
  ];
  const since = data?.tracking_since ? new Date(data.tracking_since).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(150px, 45%), 1fr))", gap: 12 }}>
        <Kpi label="Link visitors" value={loading ? "…" : num(t.visitors)} color="#4d8ef0" icon={ICON.trend} sub="Prospects, not you" />
        <Kpi label="Picked a time" value={loading ? "…" : pct(t.pick_rate)} color={T.warn} icon={ICON.target}
          sub={data ? `${num(t.picked)} of ${num(t.visitors)} visitors` : null} />
        <Kpi label="Booked" value={loading ? "…" : num(t.booked)} color={T.good} icon={ICON.check}
          sub={data ? (data.ai_booked ? `+${num(data.ai_booked)} booked by your AI setters` : "Through the link") : null} />
        <Kpi label="Conversion rate" value={loading ? "…" : pct(t.conversion_rate)} color={T.accent} icon={ICON.trend}
          sub="Booked ÷ visitors" />
      </div>
      <ComparisonTable columns={columns} rows={rows} loading={loading} />
      <div style={{ fontSize: 12, color: T.textMute, lineHeight: 1.5 }}>
        Each visitor counts once, under the channel of their first visit. Your own visits (OS-logged devices) and test bookings are left out.
        AI-setter bookings skip the link, so they're not in the rates.{since ? ` Tracking since ${since}.` : ""}
      </div>
    </div>
  );
}

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
  // Overall ABR: calls booked ÷ total outreach (every channel), one decimal
  // because it's usually well under 1%.
  const overallAbr = funnel.dialed ? Math.round((funnel.booked / funnel.dialed) * 1000) / 10 : null;

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
              <Kpi label="Overall ABR" value={overallAbr != null ? `${overallAbr}%` : "–"} color={T.accent} icon={ICON.trend}
                sub={pipeline ? `${num(funnel.booked)} booked from ${num(funnel.dialed)} reached out to` : null} />
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
              <SectionTitle title="Outreach by channel" hint="Read across to compare. The highlighted value is the best channel on that row. Each booking counts once, under the channel that won it." />
              <ChannelTable calling={tabData("calling")} sms={tabData("sms")} email={tabData("email")} loading={!outreach} />
            </div>

            {/* Content */}
            <div>
              <SectionTitle title="Video engagement" hint="How far people get through your videos, and how many book after." />
              <ContentCampaignsView />
            </div>

            {/* Booking link */}
            <div>
              <SectionTitle title="Booking link" hint="Your discovery call page: how many visitors book, overall and by the channel the link came from." />
              <BookingLinkView days={days} date={date} />
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
