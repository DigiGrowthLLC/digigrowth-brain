import React, { useState, useEffect, useCallback } from "react";
import { API } from "../api.js";
import AppointmentOutcomeButtons from "../AppointmentOutcomeButtons.jsx";

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

// An appointment counts as "past" an hour after its scheduled time — status
// stays 'scheduled' in the DB either way (only an explicit Cancel flips it),
// so this split is purely a client-side time comparison against appointment_at.
const PAST_GRACE_MS = 60 * 60 * 1000;
const FILTER_LABELS = { upcoming: "Upcoming Appointments", past: "Past Appointments", canceled: "Canceled Appointments", all: "All Appointments" };

export default function AppointmentsPanel() {
  const [rows, setRows]       = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter]   = useState("upcoming");

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

  const displayRows = filter === "upcoming"
    ? rows.filter(r => new Date(r.appointment_at).getTime() + PAST_GRACE_MS > Date.now())
    : filter === "past"
    ? rows.filter(r => new Date(r.appointment_at).getTime() + PAST_GRACE_MS <= Date.now())
    : rows;

  const cancel = async (id) => {
    if (!confirm("Cancel reminders for this appointment?")) return;
    await fetch(API(`/appointment-reminders/${id}/cancel`), { method: "POST" }).catch(() => {});
    load();
  };

  const handleOutcomeUpdated = (updated) => {
    setRows(rs => rs.map(r => r.id === updated.id ? updated : r));
  };

  return (
    <div style={{ flex: 1, overflowY: "auto", padding: 24, display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <div className="sec-label" style={{ marginBottom: 2 }}>{FILTER_LABELS[filter]}</div>
        </div>
        <select className="dg-input" value={filter} onChange={e => setFilter(e.target.value)} style={{ fontSize: 12, padding: "6px 10px", width: "auto" }}>
          <option value="upcoming">Upcoming</option>
          <option value="past">Past</option>
          <option value="canceled">Canceled</option>
          <option value="all">All</option>
        </select>
      </div>

      <div className="glass-card" style={{ padding: 0, overflow: "hidden" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
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
                    <AppointmentOutcomeButtons appointment={row} onUpdated={handleOutcomeUpdated} />
                  )}
                </td>
                <td style={{ padding: "10px 14px" }}>
                  {row.status === "scheduled" && (
                    <button onClick={() => cancel(row.id)} style={{
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
    </div>
  );
}
