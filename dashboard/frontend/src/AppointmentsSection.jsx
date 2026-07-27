import React, { useState, useEffect, useCallback } from "react";
import { API } from "./api.js";

function fmtLocal(iso, tz) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("en-US", {
      timeZone: tz, month: "short", day: "numeric", year: "numeric",
      hour: "numeric", minute: "2-digit", timeZoneName: "short",
    });
  } catch {
    return new Date(iso).toLocaleString("en-US");
  }
}

// Splits a UTC ISO timestamp into <input type=date>/<input type=time> values
// in the appointment's own timezone (not the browser's).
function splitLocal(iso, tz) {
  const d = new Date(iso);
  try {
    const date = new Intl.DateTimeFormat("en-CA", { timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit" }).format(d);
    const time = new Intl.DateTimeFormat("en-GB", { timeZone: tz, hour: "2-digit", minute: "2-digit", hour12: false }).format(d);
    return { date, time };
  } catch {
    return { date: "", time: "" };
  }
}

function Badge({ children, color }) {
  return (
    <span style={{
      fontFamily: "'Share Tech Mono', monospace", fontSize: 9, letterSpacing: "0.05em",
      padding: "2px 6px", borderRadius: 4, color, background: `${color}1a`,
    }}>{children}</span>
  );
}

// Embedded in ContactCard.jsx and CRMPanel.jsx's ContactDrawer — shows every
// booking captured for this contact (dashboard/backend/routers/appointments.py),
// with inline reschedule/edit and cancel. Appointment *creation* still goes
// through BookingModal/BookingForm; this is for managing what's already booked.
export default function AppointmentsSection({ contactId, refreshSignal }) {
  const [rows, setRows]         = useState([]);
  const [loading, setLoading]   = useState(false);
  const [timezones, setTimezones] = useState([]);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm]         = useState({ date: "", time: "", timezone: "" });
  const [savingEdit, setSavingEdit] = useState(false);
  const [editErr, setEditErr]   = useState("");

  const load = useCallback(async () => {
    if (!contactId) { setRows([]); return; }
    setLoading(true);
    try {
      const r = await fetch(API(`/appointment-reminders?status=all&contact_id=${encodeURIComponent(contactId)}`));
      setRows(r.ok ? await r.json() : []);
    } catch {
      setRows([]);
    }
    setLoading(false);
  }, [contactId]);

  useEffect(() => { load(); }, [load, refreshSignal]);
  useEffect(() => {
    fetch(API("/appointment-reminders/timezones")).then(r => r.json()).then(setTimezones).catch(() => {});
  }, []);

  if (!contactId) return null;

  const now = Date.now();
  const upcoming = rows.filter(r => r.status === "scheduled" && new Date(r.appointment_at).getTime() > now)
    .sort((a, b) => new Date(a.appointment_at) - new Date(b.appointment_at));
  const past = rows.filter(r => !(r.status === "scheduled" && new Date(r.appointment_at).getTime() > now))
    .sort((a, b) => new Date(b.appointment_at) - new Date(a.appointment_at));

  const startEdit = (row) => {
    setEditingId(row.id);
    setEditErr("");
    setForm({ ...splitLocal(row.appointment_at, row.prospect_timezone), timezone: row.prospect_timezone });
  };

  const saveEdit = async (id) => {
    setSavingEdit(true);
    setEditErr("");
    try {
      const r = await fetch(API(`/appointment-reminders/${id}`), {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (!r.ok) throw new Error(await r.text());
      setEditingId(null);
      await load();
    } catch (e) {
      setEditErr("Failed to save — " + (e.message || "unknown error"));
    }
    setSavingEdit(false);
  };

  const cancelAppointment = async (id) => {
    if (!confirm("Cancel this appointment's reminders?")) return;
    await fetch(API(`/appointment-reminders/${id}/cancel`), { method: "POST" }).catch(() => {});
    await load();
  };

  const statusBadge = (row) => {
    if (row.status === "canceled") return <Badge color="#dc3c3c">CANCELED</Badge>;
    if (new Date(row.appointment_at).getTime() <= now) return <Badge color="#5a6f8f">PAST</Badge>;
    return <Badge color="#14c882">SCHEDULED</Badge>;
  };

  const reminderSummary = (row) => {
    const sent = ["confirmation_sent_at", "reminder_24h_sent_at", "reminder_6h_sent_at", "reminder_1h_sent_at"]
      .filter(k => row[k]).length;
    return `${sent}/4 reminders sent`;
  };

  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", letterSpacing: "0.12em", marginBottom: 6 }}>
        APPOINTMENTS
      </div>

      {loading && <div style={{ fontSize: 11, color: "#3a5a80" }}>Loading…</div>}
      {!loading && rows.length === 0 && (
        <div style={{ fontSize: 11, color: "#3a5a80" }}>No appointments booked yet.</div>
      )}

      {!loading && upcoming.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: past.length ? 10 : 0 }}>
          {upcoming.map(row => (
            <div key={row.id} className="dg-surface" style={{ padding: "10px 12px" }}>
              {editingId === row.id ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    <input type="date" className="dg-input" value={form.date}
                      onChange={e => setForm(f => ({ ...f, date: e.target.value }))}
                      style={{ fontSize: 12, padding: "6px 8px" }} />
                    <input type="time" className="dg-input" value={form.time}
                      onChange={e => setForm(f => ({ ...f, time: e.target.value }))}
                      style={{ fontSize: 12, padding: "6px 8px" }} />
                    <select className="dg-input" value={form.timezone}
                      onChange={e => setForm(f => ({ ...f, timezone: e.target.value }))}
                      style={{ fontSize: 12, padding: "6px 8px" }}>
                      {timezones.map(t => <option key={t.iana} value={t.iana}>{t.label}</option>)}
                    </select>
                  </div>
                  {editErr && <div style={{ fontSize: 11, color: "#dc3c3c" }}>{editErr}</div>}
                  <div style={{ display: "flex", gap: 8 }}>
                    <button className="btn btn-primary" disabled={savingEdit} onClick={() => saveEdit(row.id)} style={{ fontSize: 11, padding: "6px 12px" }}>
                      {savingEdit ? "Saving…" : "Save"}
                    </button>
                    <button className="btn btn-secondary" onClick={() => setEditingId(null)} style={{ fontSize: 11, padding: "6px 12px" }}>
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10 }}>
                  <div>
                    <div style={{ fontSize: 12, color: "#f0f4ff", fontWeight: 600 }}>{fmtLocal(row.appointment_at, row.prospect_timezone)}</div>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 4 }}>
                      {statusBadge(row)}
                      <span style={{ fontSize: 10, color: "#3a5a80" }}>{reminderSummary(row)}</span>
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
                    <button onClick={() => startEdit(row)} style={{
                      background: "rgba(58,123,213,0.1)", border: "1px solid rgba(58,123,213,0.3)",
                      color: "#5a9bf0", borderRadius: 6, padding: "4px 10px", fontSize: 11, cursor: "pointer",
                    }}>Reschedule</button>
                    <button onClick={() => cancelAppointment(row.id)} style={{
                      background: "rgba(220,60,60,0.1)", border: "1px solid rgba(220,60,60,0.3)",
                      color: "#dc3c3c", borderRadius: 6, padding: "4px 10px", fontSize: 11, cursor: "pointer",
                    }}>Cancel</button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {!loading && past.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {past.map(row => (
            <div key={row.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "6px 2px", fontSize: 11, color: "#5a6f8f" }}>
              <span>{fmtLocal(row.appointment_at, row.prospect_timezone)}</span>
              {statusBadge(row)}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
