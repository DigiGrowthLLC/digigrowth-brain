import React, { useEffect, useState } from "react";
import { T, Card, SectionTitle, Pill, Stat, Progress, Empty, Loading, fmtDate } from "../ui.jsx";

// Analytics -> Client retention: did clients stay after their campaign?
// One row per finished campaign (client_retention.py), opened when its final
// report goes out; outcomes are recorded on the client's Client Success
// Manager card ("Did they stay?"). Follows the period toggle by final report date.

const STATUS = {
  renewed: { tone: "good", label: "Stayed" },
  churned: { tone: "bad", label: "Left" },
  paused: { tone: "warn", label: "Paused" },
  pending: { tone: "neutral", label: "No answer yet" },
};
const PERIOD = { 1: "today", 7: "in the last 7 days", 30: "in the last 30 days", 365: "in the last year" };
const MIN_RELIABLE = 3;

const money = (v) => `$${Number(v || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
const rate = (r) => (r == null ? "–" : `${r}%`);
const th = { fontSize: 12, fontWeight: 600, color: T.textMute, textAlign: "left", padding: "8px 10px", borderBottom: `1px solid ${T.line}`, whiteSpace: "nowrap" };
const td = { fontSize: 13.5, color: T.text, padding: "10px 10px", borderBottom: `1px solid ${T.line}`, verticalAlign: "top" };

function Cell({ c }) {
  if (!c || !c.total) return <span style={{ color: T.textMute }}>–</span>;
  return <span><b style={{ fontWeight: 600 }}>{c.yes} of {c.total}</b> <span style={{ color: T.textMute }}>({Math.round((c.yes / c.total) * 100)}%)</span></span>;
}

function fmtAvg(v, row) {
  if (v == null) return <span style={{ color: T.textMute }}>–</span>;
  return row.money ? money(v) : row.pct ? `${Math.round(v)}%` : v;
}

export default function RetentionView({ days = 0, date = null }) {
  const [d, setD] = useState(null);
  const [err, setErr] = useState(false);
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
        <SectionTitle title="Do clients stay after their campaign?"
          hint={`Each finished campaign counts once its final report goes out${periodText ? ` (here: ${periodText})` : ""}. You record whether the client stayed on their Client Success Manager card.`} />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 18, marginTop: 8 }}>
          <Stat label="Clients who left" value={rate(t.churn_rate)} sub={t.decided ? `${t.churned} of ${t.decided} campaigns with an answer` : "No answers yet"} tone={t.churn_rate != null && t.churn_rate > 50 ? "bad" : undefined} />
          <Stat label="Clients who stayed" value={rate(t.renewal_rate)} sub={t.decided ? `${t.renewed} of ${t.decided} campaigns with an answer` : "No answers yet"} tone={t.renewal_rate != null && t.renewal_rate >= 50 ? "good" : undefined} />
          <Stat label="Monthly revenue lost" value={money(t.mrr_lost)} sub={`${money(t.mrr_kept)}/mo kept from clients who stayed`} tone={t.mrr_lost ? "bad" : undefined} />
          <Stat label="Waiting on your answer" value={t.pending} sub={t.paused ? `${t.paused} paused (not counted either way)` : "Final report sent, no answer yet"} />
        </div>
      </Card>

      {t.campaigns_ended === 0 ? (
        <Card><Empty>{periodText ? `No final reports went out ${periodText}. Try a longer period.` : "No finished campaigns yet. The first one shows up here when its final report goes out."}</Empty></Card>
      ) : (
        <>
          <Card>
            <SectionTitle title="Clients who stayed vs. clients who left"
              hint="What was true for each group when their campaign ended. Look for rows where the two columns are far apart." />
            {t.decided < MIN_RELIABLE && (
              <div style={{ fontSize: 12.5, color: T.warn, background: "rgba(242,173,61,0.08)", border: "1px solid rgba(242,173,61,0.25)", borderRadius: 8, padding: "8px 12px", margin: "4px 0 12px" }}>
                Only {t.decided} campaign{t.decided === 1 ? "" : "s"} with an answer so far. Patterns start to mean something after about {MIN_RELIABLE}.
              </div>
            )}
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 420 }}>
                <thead><tr><th style={th}>At the end of the campaign…</th><th style={th}>Stayed ({t.renewed})</th><th style={th}>Left ({t.churned})</th></tr></thead>
                <tbody>
                  {d.compare.map((row) => (
                    <tr key={row.key}><td style={{ ...td, color: T.textDim }}>{row.question}</td><td style={td}><Cell c={row.stayed} /></td><td style={td}><Cell c={row.left} /></td></tr>
                  ))}
                  <tr><td colSpan={3} style={{ ...th, paddingTop: 18 }}>On average</td></tr>
                  {d.averages.map((row) => (
                    <tr key={row.key}><td style={{ ...td, color: T.textDim }}>{row.label}</td><td style={td}>{fmtAvg(row.stayed, row)}</td><td style={td}>{fmtAvg(row.left, row)}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div style={{ fontSize: 12, color: T.textMute, marginTop: 10 }}>
              A dash means no data: show rate and new patients only count visits the clinic marked in their portal.
            </div>
          </Card>

          {d.reasons.length > 0 && (
            <Card>
              <SectionTitle title="Why clients left" />
              {d.reasons.map((r) => (
                <div key={r.key} style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) 2fr 30px", gap: 12, alignItems: "center", padding: "7px 0" }}>
                  <span style={{ fontSize: 13.5, color: T.textDim }}>{r.label}</span>
                  <Progress value={r.count} max={Math.max(...d.reasons.map((x) => x.count))} />
                  <span style={{ fontSize: 13.5, color: T.text, textAlign: "right" }}>{r.count}</span>
                </div>
              ))}
            </Card>
          )}

          <Card>
            <SectionTitle title="Every finished campaign" />
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 620 }}>
                <thead><tr>{["Client", "Outcome", "Booked", "New patients", "$/month", "Final report"].map((h) => <th key={h} style={th}>{h}</th>)}</tr></thead>
                <tbody>
                  {d.campaigns.map((c) => {
                    const s = c.signals || {};
                    return (
                      <tr key={c.id}>
                        <td style={td}><div style={{ fontWeight: 600 }}>{c.client_name}</div>{c.notes && <div style={{ fontSize: 12.5, color: T.textMute, marginTop: 4, maxWidth: 360 }}>{c.notes}</div>}</td>
                        <td style={td}><Pill tone={STATUS[c.status]?.tone}>{STATUS[c.status]?.label || c.status}</Pill>{c.reason_label && <div style={{ fontSize: 12.5, color: T.textMute, marginTop: 4 }}>{c.reason_label}</div>}</td>
                        <td style={td}>{s.goal ? `${s.booked ?? 0} of ${s.goal}` : s.booked ?? "–"}{s.cost_per_booking != null && <div style={{ fontSize: 12.5, color: T.textMute }}>{money(s.cost_per_booking)} each</div>}</td>
                        <td style={td}>{c.patients ?? <span style={{ color: T.textMute }}>Not marked</span>}{c.show_rate != null && <div style={{ fontSize: 12.5, color: T.textMute }}>{c.show_rate}% showed</div>}</td>
                        <td style={td}>{c.monthly_value != null ? money(c.monthly_value) : "–"}</td>
                        <td style={td}>{fmtDate(c.opened_at)}{c.decided_by === "auto" && <div style={{ fontSize: 12.5, color: T.textMute }}>Auto: new campaign</div>}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
