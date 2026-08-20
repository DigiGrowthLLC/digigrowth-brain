import React, { useState } from "react";
import { API } from "./api.js";

// Two independent toggle-pairs — Show/No Show and Closed/Not Closed — for
// marking what actually happened after a booked appointment. Shared between
// AppointmentsPanel.jsx (the central cross-contact Appointments tab) and
// AppointmentsSection.jsx (the per-contact list embedded in ContactCard/CRM)
// so outcome marking works the same everywhere an appointment shows up.
// PATCHes dashboard/backend/routers/appointments.py's outcome_show/
// outcome_close columns — purely a record on the appointment itself, not
// wired into Pipeline/Dashboard analytics.
//
// Clicking the already-active option clears it back to unmarked (toggle,
// not a one-way radio) — lets a rep undo a wrong click without a separate
// "clear" control.
function Pill({ active, color, onClick, disabled, children }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        fontFamily: "'Share Tech Mono', monospace", fontSize: 9, letterSpacing: "0.04em",
        padding: "3px 8px", borderRadius: 4, cursor: disabled ? "not-allowed" : "pointer",
        color: active ? color : "#3a5a80",
        background: active ? `${color}1a` : "transparent",
        border: `1px solid ${active ? color : "#1a2540"}`,
        opacity: disabled ? 0.5 : 1,
      }}
    >{children}</button>
  );
}

export default function AppointmentOutcomeButtons({ appointment, onUpdated }) {
  const [saving, setSaving] = useState(false);

  const setOutcome = async (field, value) => {
    const next = appointment[field] === value ? null : value;
    setSaving(true);
    try {
      const r = await fetch(API(`/appointment-reminders/${appointment.id}`), {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ [field]: next }),
      });
      if (r.ok) onUpdated?.({ ...appointment, [field]: next });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
      <div style={{ display: "flex", gap: 4 }}>
        <Pill active={appointment.outcome_show === "show"} color="#14c882" disabled={saving}
          onClick={() => setOutcome("outcome_show", "show")}>SHOW</Pill>
        <Pill active={appointment.outcome_show === "no_show"} color="#dc3c3c" disabled={saving}
          onClick={() => setOutcome("outcome_show", "no_show")}>NO SHOW</Pill>
      </div>
      <div style={{ display: "flex", gap: 4 }}>
        <Pill active={appointment.outcome_close === "closed"} color="#14c882" disabled={saving}
          onClick={() => setOutcome("outcome_close", "closed")}>CLOSED</Pill>
        <Pill active={appointment.outcome_close === "not_closed"} color="#dc3c3c" disabled={saving}
          onClick={() => setOutcome("outcome_close", "not_closed")}>NOT CLOSED</Pill>
      </div>
    </div>
  );
}
