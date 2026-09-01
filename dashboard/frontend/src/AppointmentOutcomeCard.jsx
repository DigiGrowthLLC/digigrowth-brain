import React, { useState } from "react";

// Full "click the appointment -> graphic card" outcome flow — replaces the
// old always-visible inline AppointmentOutcomeButtons row in AppointmentsPanel
// with a modal opened on row click, showing Show Y/N, Closed/Not Closed, and
// a free-text notes field together, then saving all three in one PATCH.
// `patchUrl` is passed in so this same component works against both the
// internal OS's /api/appointment-reminders/{id} and the client portal's
// /portal-api/{token}/appointments/{id} — same payload shape either way.
function Pill({ active, color, onClick, disabled, children }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        fontFamily: "'Share Tech Mono', monospace", fontSize: 11, letterSpacing: "0.06em",
        padding: "8px 16px", borderRadius: 6, cursor: disabled ? "not-allowed" : "pointer",
        color: active ? color : "#5a6f8f",
        background: active ? `${color}1a` : "transparent",
        border: `1px solid ${active ? color : "#1a2540"}`,
        fontWeight: 600, opacity: disabled ? 0.5 : 1,
      }}
    >{children}</button>
  );
}

function fmtWhen(ts) {
  if (!ts) return "";
  return new Date(ts).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

export default function AppointmentOutcomeCard({ appointment, patchUrl, onClose, onSaved }) {
  const [show, setShow]   = useState(appointment.outcome_show || null);
  const [close, setClose] = useState(appointment.outcome_close || null);
  const [notes, setNotes] = useState(appointment.outcome_notes || "");
  const [saving, setSaving] = useState(false);
  const [err, setErr]       = useState("");

  const save = async () => {
    setSaving(true);
    setErr("");
    try {
      const r = await fetch(patchUrl, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ outcome_show: show, outcome_close: close, outcome_notes: notes.trim() || null }),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        setErr(d.detail || "Couldn't save outcome.");
        setSaving(false);
        return;
      }
      onSaved?.({ ...appointment, outcome_show: show, outcome_close: close, outcome_notes: notes.trim() || null });
    } catch (e) {
      setErr("Couldn't save outcome: " + e.message);
      setSaving(false);
    }
  };

  const labelStyle = { fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80", letterSpacing: "0.15em", marginBottom: 8 };

  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 60, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ position: "absolute", inset: 0, background: "rgba(8,12,20,0.72)" }} onClick={onClose} />
      <div className="glass-card" style={{
        position: "relative", width: 440, maxWidth: "92vw", maxHeight: "88vh", overflowY: "auto",
        padding: 24, display: "flex", flexDirection: "column", gap: 18,
      }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 10 }}>
          <div>
            <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 16, fontWeight: 700, color: "#f0f4ff" }}>
              {appointment.prospect_name || "Appointment"}
            </div>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80", letterSpacing: "0.1em", marginTop: 3 }}>
              {fmtWhen(appointment.appointment_at)}
            </div>
          </div>
          <button onClick={onClose} style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 12, color: "#3a5a80", background: "none", border: "none", cursor: "pointer", padding: "2px 6px" }}>✕</button>
        </div>

        <div>
          <div style={labelStyle}>DID THEY SHOW?</div>
          <div style={{ display: "flex", gap: 8 }}>
            <Pill active={show === "show"} color="#14c882" disabled={saving}
              onClick={() => setShow(show === "show" ? null : "show")}>YES — SHOWED</Pill>
            <Pill active={show === "no_show"} color="#dc3c3c" disabled={saving}
              onClick={() => setShow(show === "no_show" ? null : "no_show")}>NO — NO SHOW</Pill>
          </div>
        </div>

        <div>
          <div style={labelStyle}>CONCLUSION</div>
          <div style={{ display: "flex", gap: 8 }}>
            <Pill active={close === "closed"} color="#14c882" disabled={saving}
              onClick={() => setClose(close === "closed" ? null : "closed")}>CLOSED</Pill>
            <Pill active={close === "not_closed"} color="#dc3c3c" disabled={saving}
              onClick={() => setClose(close === "not_closed" ? null : "not_closed")}>NOT CLOSED</Pill>
          </div>
        </div>

        <div>
          <div style={labelStyle}>NOTES</div>
          <textarea
            value={notes} onChange={(e) => setNotes(e.target.value)}
            className="dg-input" rows={4}
            style={{ width: "100%", resize: "vertical", fontFamily: "inherit", boxSizing: "border-box" }}
            placeholder="What happened on the call…"
          />
        </div>

        {err && <div style={{ fontSize: 11, color: "#f06060", fontFamily: "'Share Tech Mono', monospace" }}>{err}</div>}

        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={onClose} className="btn btn-secondary" style={{ flex: 1 }}>Cancel</button>
          <button onClick={save} disabled={saving} className="btn btn-primary" style={{ flex: 2 }}>
            {saving ? "Saving…" : "Save Outcome"}
          </button>
        </div>
      </div>
    </div>
  );
}
