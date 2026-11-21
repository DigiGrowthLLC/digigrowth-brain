import React, { useEffect, useState } from "react";
import { T, Card, Pill, Empty, Loading, fmtDate } from "../ui.jsx";

// Analytics -> Client retention: did clients stay after their campaign?
// One row per finished campaign (client_retention.py), opened when its final
// report goes out; outcomes are recorded on the client's Client Success
// Manager card ("Did they stay?"). Follows the period toggle by final report date.

const STATUS = {
  renewed: { tone: "good", label: "Stayed" },
  churned: { tone: "bad", label: "Left" },
  paused: { tone: "warn", label: "Paused" },
  pending: { tone: "info", label: "Pending" },
};
const PERIOD = { 1: "today", 7: "in the last 7 days", 30: "in the last 30 days", 365: "in the last year" };

const money = (v) => `$${Number(v || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
const rate = (r) => (r == null ? "–" : `${r}%`);

// Big metric tile: each one gets its own color so they read apart at a glance.
function Metric({ label, value, color, icon }) {
  return (
    <div style={{
      position: "relative", overflow: "hidden", borderRadius: 16, padding: "18px 20px 20px",
      background: `linear-gradient(160deg, ${color}26 0%, ${color}08 55%, rgba(255,255,255,0.015) 100%)`,
      border: `1px solid ${color}40`,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ width: 30, height: 30, borderRadius: 9, display: "grid", placeItems: "center", background: `${color}22`, color }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{icon}</svg>
        </span>
        <span style={{ fontSize: 13, fontWeight: 600, color: T.textDim }}>{label}</span>
      </div>
      <div style={{ fontFamily: T.display, fontSize: 40, fontWeight: 700, color: T.text, letterSpacing: "-0.03em", lineHeight: 1, marginTop: 16, fontVariantNumeric: "tabular-nums" }}>
        {value}
      </div>
    </div>
  );
}

const ICONS = {
  churn: <><path d="M22 17 13.5 8.5 8.5 13.5 2 7" /><path d="M16 17h6v-6" /></>,
  stay: <><path d="M22 7 13.5 15.5 8.5 10.5 2 17" /><path d="M16 7h6v6" /></>,
  money: <><path d="M12 2v20" /><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" /></>,
  wait: <><circle cx="12" cy="12" r="10" /><path d="M12 6v6l4 2" /></>,
};

function Section({ title, children }) {
  return (
    <Card pad={22}>
      <div style={{ fontFamily: T.display, fontSize: 16, fontWeight: 600, color: T.text, marginBottom: 14 }}>{title}</div>
      {children}
    </Card>
  );
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
  const periodText = date ? `on ${new Date(`${date}T12:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" })}` : PERIOD[days] || "";

  if (err) return <Card><Empty>Couldn't load retention data.</Empty></Card>;
  if (!d) return <Loading />;
  const t = d.totals;
  const maxReason = Math.max(1, ...d.reasons.map((x) => x.count));

  return (
    <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr)", gap: 16 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))", gap: 14 }}>
        <Metric label="Churn rate" value={rate(t.churn_rate)} color={T.bad} icon={ICONS.churn} />
        <Metric label="Clients who stayed" value={rate(t.renewal_rate)} color={T.good} icon={ICONS.stay} />
        <Metric label="Monthly revenue lost" value={money(t.mrr_lost)} color={T.warn} icon={ICONS.money} />
        <Metric label="Pending decision" value={t.pending} color={T.accent} icon={ICONS.wait} />
      </div>

      {t.campaigns_ended === 0 ? (
        <Card><Empty>{periodText ? `No finished campaigns ${periodText}.` : "No finished campaigns yet."}</Empty></Card>
      ) : (
        <>
          {d.reasons.length > 0 && (
            <Section title="Why clients left">
              <div style={{ display: "grid", gap: 12 }}>
                {d.reasons.map((r) => (
                  <div key={r.key} style={{ display: "grid", gridTemplateColumns: "minmax(110px, 180px) minmax(0, 1fr) 28px", gap: 14, alignItems: "center" }}>
                    <span style={{ fontSize: 14, color: T.textDim }}>{r.label}</span>
                    <div style={{ height: 10, borderRadius: 99, background: "rgba(169,186,216,0.08)", overflow: "hidden" }}>
                      <div style={{ width: `${(r.count / maxReason) * 100}%`, height: "100%", borderRadius: 99, background: `linear-gradient(90deg, ${T.bad}, #ff9a8a)` }} />
                    </div>
                    <span style={{ fontFamily: T.display, fontSize: 15, fontWeight: 700, color: T.text, textAlign: "right" }}>{r.count}</span>
                  </div>
                ))}
              </div>
            </Section>
          )}

          <Section title="Every finished campaign">
            <div style={{ display: "grid", gap: 8 }}>
              {d.campaigns.map((c) => {
                const s = c.signals || {};
                const st = STATUS[c.status] || STATUS.pending;
                return (
                  <div key={c.id} style={{
                    display: "flex", flexWrap: "wrap", gap: "12px 16px", alignItems: "center",
                    padding: "14px 16px", borderRadius: 12, background: T.surface2, border: `1px solid ${T.line}`,
                  }}>
                    <div style={{ minWidth: 0, flex: "2 1 180px" }}>
                      <div style={{ fontWeight: 600, color: T.text, fontSize: 14.5, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.client_name}</div>
                      <div style={{ fontSize: 12, color: T.textMute, marginTop: 2 }}>{fmtDate(c.opened_at)}</div>
                    </div>
                    <div style={{ flex: "1 1 90px" }}><Pill tone={st.tone} dot>{st.label}</Pill>{c.reason_label && <div style={{ fontSize: 12, color: T.textMute, marginTop: 5 }}>{c.reason_label}</div>}</div>
                    <Fact label="Booked" value={s.goal ? `${s.booked ?? 0}/${s.goal}` : s.booked ?? "–"} />
                    <Fact label="New patients" value={c.patients ?? "–"} />
                    <Fact label="Per month" value={c.monthly_value != null ? money(c.monthly_value) : "–"} />
                  </div>
                );
              })}
            </div>
          </Section>
        </>
      )}
    </div>
  );
}

function Fact({ label, value }) {
  return (
    <div style={{ flex: "1 1 80px" }}>
      <div style={{ fontSize: 11.5, color: T.textMute }}>{label}</div>
      <div style={{ fontFamily: T.display, fontSize: 16, fontWeight: 600, color: T.text, marginTop: 2, fontVariantNumeric: "tabular-nums" }}>{value}</div>
    </div>
  );
}
