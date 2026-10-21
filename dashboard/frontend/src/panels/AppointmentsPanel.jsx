import React, { useState, useEffect, useCallback } from "react";
import { API } from "../api.js";
import AppointmentOutcomeCard from "../AppointmentOutcomeCard.jsx";

function fmtLocal(iso, tz) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("en-US", {
      timeZone: tz, month: "short", day: "numeric",
      hour: "numeric", minute: "2-digit", timeZoneName: "short",
    });
  } catch {
    return new Date(iso).toLocaleString("en-US");
  }
}

function Check({ sentAt }) {
  return (
    <span style={{ color: sentAt ? "#14c882" : "#3a5a80", fontSize: 11, fontFamily: "'Share Tech Mono', monospace" }}>
      {sentAt ? "✓ sent" : "pending"}
    </span>
  );
}

// Compact clickable summary of the outcome card's saved state — opens
// AppointmentOutcomeCard on click instead of the old always-visible inline
// pill buttons, so setting/reviewing an outcome is a deliberate "click the
// appointment" action rather than four buttons live in every row.
function OutcomeSummary({ appointment, onClick }) {
  const showLabel  = appointment.outcome_show === "show" ? "Show" : appointment.outcome_show === "no_show" ? "No Show" : null;
  const closeLabel = appointment.outcome_close === "closed" ? "Closed" : appointment.outcome_close === "not_closed" ? "Not Closed" : null;
  const showColor  = appointment.outcome_show === "show" ? "#14c882" : "#dc3c3c";
  const closeColor = appointment.outcome_close === "closed" ? "#14c882" : "#dc3c3c";
  const hasOutcome = showLabel || closeLabel;
  return (
    <button
      onClick={onClick}
      style={{
        background: "none", border: "none", cursor: "pointer", padding: "4px 8px",
        borderRadius: 6, textAlign: "left",
        fontFamily: "'Share Tech Mono', monospace", fontSize: 10.5,
      }}
    >
      {hasOutcome ? (
        <span>
          {showLabel && <span style={{ color: showColor }}>{showLabel}</span>}
          {showLabel && closeLabel && <span style={{ color: "#3a5a80" }}> · </span>}
          {closeLabel && <span style={{ color: closeColor }}>{closeLabel}</span>}
          {appointment.outcome_notes && <span style={{ color: "#5a6f8f" }}> · 📝</span>}
        </span>
      ) : (
        <span style={{ color: "#5a6f8f" }}>Set outcome ›</span>
      )}
    </button>
  );
}

// An appointment counts as "past" an hour after its scheduled time — status
// stays 'scheduled' in the DB either way (only an explicit Cancel flips it),
// so this split is purely a client-side time comparison against appointment_at.
const PAST_GRACE_MS = 60 * 60 * 1000;
const FILTER_LABELS = { upcoming: "Upcoming", past: "Past", canceled: "Canceled", all: "All" };

// One panel per Calendly link (appointment_reminders.call_type, set by the
// Calendly webhook). Discovery is the sales table with outcomes; onboarding
// and launch are client calls, so they get no show/close outcome — marking
// a no-show there would fire the prospect No Show sequence.
const CALL_TYPES = [
  { key: "discovery",  label: "Discovery Calls",  noun: "Appointments" },
  { key: "onboarding", label: "Onboarding Calls", noun: "Onboarding Calls" },
  { key: "launch",     label: "Launch Calls",     noun: "Launch Calls" },
];

const thStyle = { textAlign: "left", padding: "10px 14px", fontSize: 10, color: "#5a6f8f", fontFamily: "'Share Tech Mono', monospace", letterSpacing: "0.05em" };
const tdStyle = { padding: "10px 14px", fontSize: 12, color: "#8a9cc0" };

function CancelCell({ row, onCancel }) {
  if (row.status === "scheduled") {
    return (
      <button onClick={() => onCancel(row)} style={{
        background: "rgba(220,60,60,0.1)", border: "1px solid rgba(220,60,60,0.3)",
        color: "#dc3c3c", borderRadius: 6, padding: "4px 10px", fontSize: 11, cursor: "pointer",
      }}>Cancel</button>
    );
  }
  return row.status === "canceled" ? <span style={{ fontSize: 11, color: "#3a5a80" }}>canceled</span> : null;
}

// Onboarding / launch calls: who the client is and when — no sales
// outcome, and no reminder columns since these calls get no reminders
// (reminder_engine.py only sends for discovery calls).
function ClientCallTable({ rows, loading, onCancel }) {
  return (
    <div className="glass-card" style={{ padding: 0, overflow: "auto" }}>
      <table style={{ width: "100%", minWidth: 480, borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ borderBottom: "1px solid #1a2540" }}>
            {["Client", "Business", "Call (local time)", ""].map(h => <th key={h} style={thStyle}>{h}</th>)}
          </tr>
        </thead>
        <tbody>
          {!loading && rows.length === 0 && (
            <tr><td colSpan={4} style={{ padding: 20, textAlign: "center", color: "#3a5a80", fontSize: 12 }}>No calls in this view.</td></tr>
          )}
          {rows.map(row => (
            <tr key={row.id} style={{ borderBottom: "1px solid #131f38" }}>
              <td style={{ ...tdStyle, color: "#f0f4ff" }}>{row.prospect_name || row.owner || "—"}</td>
              <td style={tdStyle}>{row.business || "—"}</td>
              <td style={tdStyle}>{fmtLocal(row.appointment_at, row.prospect_timezone)}</td>
              <td style={{ padding: "10px 14px" }}><CancelCell row={row} onCancel={onCancel} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function AppointmentsPanel() {
  const [rows, setRows]       = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter]   = useState("upcoming");
  const [callType, setCallType] = useState("discovery");
  const [outcomeTarget, setOutcomeTarget] = useState(null); // the row being edited in the outcome card

  // "upcoming"/"past" both pull every non-canceled row from the backend
  // (status=scheduled) and split by time client-side below — the backend
  // has no separate "past" status to filter on.
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const backendStatus = filter === "upcoming" || filter === "past" ? "scheduled" : filter;
      const r = await fetch(API(`/appointment-reminders?status=${backendStatus}`));
      setRows(await r.json());
    } catch {
      setRows([]);
    }
    setLoading(false);
  }, [filter]);

  useEffect(() => { load(); }, [load]);

  const periodRows = filter === "upcoming"
    ? rows.filter(r => new Date(r.appointment_at).getTime() + PAST_GRACE_MS > Date.now())
    : filter === "past"
    ? rows.filter(r => new Date(r.appointment_at).getTime() + PAST_GRACE_MS <= Date.now())
    : rows;
  const typeOf = r => r.call_type || "discovery";
  const displayRows = periodRows.filter(r => typeOf(r) === callType);
  const activeType = CALL_TYPES.find(t => t.key === callType);

  // Our own texts/emails stay silent either way. Canceling in Calendly too
  // stops Calendly's own reminders, but Calendly always emails the invitee a
  // cancellation notice for that (its API can't suppress it), so it's asked
  // per appointment.
  const cancel = async (row) => {
    if (!confirm("Cancel this appointment? (No texts or emails go out from the OS.)")) return;
    const alsoCalendly = !!row.calendly_event_uri && confirm(
      "Also cancel it in Calendly?\n\nOK = cancel in Calendly too (Calendly will email them a cancellation notice and stop its reminders).\nCancel = OS only (Calendly booking stays live)."
    );
    try {
      const res = await fetch(API(`/appointment-reminders/${row.id}/cancel${alsoCalendly ? "?cancel_calendly=true" : ""}`), { method: "POST" });
      const data = await res.json().catch(() => ({}));
      if (data.calendly_error) alert(`Canceled in the OS, but the Calendly cancel failed:\n${data.calendly_error}`);
    } catch {}
    load();
  };

  const handleOutcomeSaved = (updated) => {
    setRows(rs => rs.map(r => r.id === updated.id ? updated : r));
    setOutcomeTarget(null);
  };

  return (
    <div style={{ flex: 1, overflowY: "auto", padding: 24, display: "flex", flexDirection: "column", gap: 16 }}>
      <div className="flex-wrap" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10 }}>
        <div>
          <div className="sec-label" style={{ marginBottom: 2 }}>{FILTER_LABELS[filter]} {activeType.noun}</div>
        </div>
        <div className="flex-wrap" style={{ display: "flex", gap: 6 }}>
          {CALL_TYPES.map(t => {
            const count = periodRows.filter(r => typeOf(r) === t.key).length;
            return (
              <button
                key={t.key}
                onClick={() => setCallType(t.key)}
                className={callType === t.key ? "btn btn-primary" : "btn btn-secondary"}
                style={{ fontSize: 10, padding: "6px 14px" }}
              >
                {t.label}{count ? ` (${count})` : ""}
              </button>
            );
          })}
        </div>
        <select className="dg-input" value={filter} onChange={e => setFilter(e.target.value)} style={{ fontSize: 12, padding: "6px 10px", width: "auto" }}>
          <option value="upcoming">Upcoming</option>
          <option value="past">Past</option>
          <option value="canceled">Canceled</option>
          <option value="all">All</option>
        </select>
      </div>

      {callType !== "discovery" ? (
        <ClientCallTable rows={displayRows} loading={loading} onCancel={cancel} />
      ) : (
      /* Table has 8 columns — horizontal overflow on a phone is contained
          to this scroller, same as CRM's contact table. */
      <div className="glass-card" style={{ padding: 0, overflow: "auto" }}>
        <table style={{ width: "100%", minWidth: 720, borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid #1a2540" }}>
              {["Prospect", "Business", "Appointment (local time)", "24h", "6h", "1h", "Outcome", ""].map(h => (
                <th key={h} style={{ textAlign: "left", padding: "10px 14px", fontSize: 10, color: "#5a6f8f", fontFamily: "'Share Tech Mono', monospace", letterSpacing: "0.05em" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {!loading && displayRows.length === 0 && (
              <tr><td colSpan={8} style={{ padding: 20, textAlign: "center", color: "#3a5a80", fontSize: 12 }}>No appointments in this view.</td></tr>
            )}
            {displayRows.map(row => (
              <tr key={row.id} style={{ borderBottom: "1px solid #131f38" }}>
                <td style={{ padding: "10px 14px", fontSize: 12, color: "#f0f4ff" }}>{row.prospect_name || row.owner || "—"}</td>
                <td style={{ padding: "10px 14px", fontSize: 12, color: "#8a9cc0" }}>{row.business || "—"}</td>
                <td style={{ padding: "10px 14px", fontSize: 12, color: "#8a9cc0" }}>{fmtLocal(row.appointment_at, row.prospect_timezone)}</td>
                <td style={{ padding: "10px 14px" }}><Check sentAt={row.reminder_24h_sent_at} /></td>
                <td style={{ padding: "10px 14px" }}><Check sentAt={row.reminder_6h_sent_at} /></td>
                <td style={{ padding: "10px 14px" }}><Check sentAt={row.reminder_1h_sent_at} /></td>
                <td style={{ padding: "10px 14px" }}>
                  {row.status !== "canceled" && (
                    <OutcomeSummary appointment={row} onClick={() => setOutcomeTarget(row)} />
                  )}
                </td>
                <td style={{ padding: "10px 14px" }}>
                  {row.status === "scheduled" && (
                    <button onClick={() => cancel(row)} style={{
                      background: "rgba(220,60,60,0.1)", border: "1px solid rgba(220,60,60,0.3)",
                      color: "#dc3c3c", borderRadius: 6, padding: "4px 10px", fontSize: 11, cursor: "pointer",
                    }}>Cancel</button>
                  )}
                  {row.status === "canceled" && <span style={{ fontSize: 11, color: "#3a5a80" }}>canceled</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      )}

      {outcomeTarget && (
        <AppointmentOutcomeCard
          appointment={outcomeTarget}
          patchUrl={API(`/appointment-reminders/${outcomeTarget.id}`)}
          onClose={() => setOutcomeTarget(null)}
          onSaved={handleOutcomeSaved}
          showRevenueFields
        />
      )}
    </div>
  );
}
