import React, { useEffect, useState } from "react";
import { T, Card, SectionTitle, Pill, Stat, Progress, Empty, Loading, fmtDate } from "../ui.jsx";

// Analytics -> Retention: did clients stay after their campaign?
// One row per finished campaign (client_retention.py), opened when its final
// report goes out; outcomes are recorded on the client's Client Success
// Manager card. Every rate shows its count because the sample is small.

const STATUS = {
  renewed: { tone: "good", label: "Renewed" },
  churned: { tone: "bad", label: "Churned" },
  paused: { tone: "warn", label: "Paused" },
  pending: { tone: "neutral", label: "Pending" },
};

const money = (v) => `$${Number(v || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
const rate = (r) => (r == null ? "–" : `${r}%`);

function Bucket({ b }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 140px) minmax(0, 1fr) 92px", alignItems: "center", gap: 12, padding: "6px 0" }}>
      <span style={{ fontSize: 13, color: T.textDim, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{b.label}</span>
      <Progress value={b.renewed} max={b.total || 1} tone={b.rate >= 50 ? "good" : "warn"} />
      <span style={{ fontSize: 13, color: T.text, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
        {rate(b.rate)} <span style={{ color: T.textMute }}>({b.renewed}/{b.total})</span>
      </span>
    </div>
  );
}

const PERIOD = { 1: "today", 7: "in the last 7 days", 30: "in the last 30 days", 365: "in the last year" };

export default function RetentionView({ days = 0, date = null }) {
  const [d, setD] = useState(null);
  const [err, setErr] = useState(false);
  // Follows the Analytics period toggle: campaigns whose final report went out in the period.
  useEffect(() => {
    let stale = false;
    setD(null); setErr(false);
    fetch(`/api/client-success/retention?days=${days}${date ? `&date=${date}` : ""}`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((x) => { if (!stale) setD(x); })
      .catch(() => { if (!stale) setErr(true); });
    return () => { stale = true; };
  }, [days, date]);
  const periodText = date ? `on ${new Date(`${date}T12:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" })}` : PERIOD[days] || (days ? `in the last ${days} days` : "");

  if (err) return <Card><Empty>Couldn't load retention data.</Empty></Card>;
  if (!d) return <Loading />;
  const t = d.totals;

  return (
    <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr)", gap: 16 }}>
      <Card>
        <SectionTitle title="Client retention"
          hint={`Did clients stay after their campaign? Counts campaigns whose final report went out ${periodText || "at any time"}; record the outcome on the client's Client Success Manager card. Rates are out of renewed + churned campaigns.`} />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 18, marginTop: 8 }}>
          <Stat label="Churn rate" value={rate(t.churn_rate)} sub={`${t.churned} of ${t.decided} decided`} tone={t.churn_rate != null && t.churn_rate > 50 ? "bad" : undefined} />
          <Stat label="Renewal rate" value={rate(t.renewal_rate)} sub={`${t.renewed} of ${t.decided} decided`} tone={t.renewal_rate != null && t.renewal_rate >= 50 ? "good" : undefined} />
          <Stat label="Waiting on a decision" value={t.pending} sub={t.paused ? `${t.paused} paused` : "after the final report"} />
          <Stat label="Campaigns finished" value={t.campaigns_ended} sub={`${t.clients} client${t.clients === 1 ? "" : "s"} · ${t.repeat_clients} came back`} />
          <Stat label="Monthly revenue kept" value={money(t.mrr_kept)} sub={`${money(t.mrr_lost)}/mo lost to churn`} />
          <Stat label="Days to decide" value={t.avg_days_to_decide ?? "–"} sub="final report → outcome, average" />
        </div>
      </Card>

      {t.campaigns_ended === 0 ? (
        <Card><Empty>{periodText ? `No final reports went out ${periodText}. Try a longer period.` : "No finished campaigns yet. The first one shows up here when its final report goes out."}</Empty></Card>
      ) : (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 16 }}>
            <Card>
              <SectionTitle title="What renewals line up with" hint="Renewal rate split by what we knew when each campaign ended. Small samples: read the counts, not just the %." />
              {d.correlations.length === 0 ? <Empty>Record a renewed or churned outcome to see these.</Empty> :
                d.correlations.map((c) => (
                  <div key={c.key} style={{ padding: "10px 0", borderTop: `1px solid ${T.line}` }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: T.text, marginBottom: 4 }}>{c.title}</div>
                    {c.buckets.map((b) => <Bucket key={b.label} b={b} />)}
                  </div>
                ))}
            </Card>
            <Card>
              <SectionTitle title="Why clients churned" />
              {d.reasons.length === 0 ? <Empty>No churned clients recorded.</Empty> :
                d.reasons.map((r) => (
                  <div key={r.key} style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) 2fr 30px", gap: 12, alignItems: "center", padding: "7px 0" }}>
                    <span style={{ fontSize: 13, color: T.textDim }}>{r.label}</span>
                    <Progress value={r.count} max={Math.max(...d.reasons.map((x) => x.count))} tone="bad" />
                    <span style={{ fontSize: 13, color: T.text, textAlign: "right" }}>{r.count}</span>
                  </div>
                ))}
            </Card>
          </div>

          <Card>
            <SectionTitle title="Every finished campaign" />
            {d.campaigns.map((c) => {
              const s = c.signals || {};
              return (
                <div key={c.id} style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "6px 14px", padding: "12px 0", borderTop: `1px solid ${T.line}` }}>
                  <span style={{ fontWeight: 600, color: T.text, fontSize: 13.5, minWidth: 150 }}>{c.client_name}</span>
                  <Pill tone={STATUS[c.status]?.tone}>{STATUS[c.status]?.label || c.status}</Pill>
                  {c.reason_label && <span style={{ fontSize: 12.5, color: T.textMute }}>{c.reason_label}</span>}
                  <span style={{ fontSize: 12.5, color: T.textDim }}>
                    {s.goal ? `${s.booked ?? 0}/${s.goal} goal` : `${s.booked ?? 0} booked`}
                    {s.cost_per_booking != null ? ` · ${money(s.cost_per_booking)}/booking` : ""}
                    {s.health_band ? ` · health ${s.health_band}` : ""}
                    {c.show_rate != null ? ` · ${c.show_rate}% showed` : ""}
                    {c.patients != null ? ` · ${c.patients} new patient${c.patients === 1 ? "" : "s"}` : " · outcomes not marked"}
                    {c.opened_report ? " · opened report" : " · report not opened"}
                    {c.wants_next ? " · asked about next" : ""}
                    {c.testimonial ? " · testimonial" : ""}
                  </span>
                  <span style={{ marginLeft: "auto", fontSize: 12.5, color: T.textMute }}>
                    {c.monthly_value != null ? `${money(c.monthly_value)}/mo · ` : ""}report {fmtDate(c.opened_at)}{c.decided_at ? ` · decided ${fmtDate(c.decided_at)}${c.decided_by === "auto" ? " (auto)" : ""}` : ""}
                  </span>
                  {c.notes && <div style={{ flexBasis: "100%", fontSize: 12.5, color: T.textMute }}>{c.notes}</div>}
                </div>
              );
            })}
          </Card>
        </>
      )}
    </div>
  );
}
