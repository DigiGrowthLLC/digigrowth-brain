import React, { useState, useEffect } from "react";
import { API } from "./api.js";

function fmtWhen(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleString("en-US", {
    weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  });
}

// Sits below the Calendly iframe in BookingModal. Booking itself now happens
// automatically via the Calendly webhook (routers/calendly_webhooks.py) the
// moment the rep completes the booking in the iframe above — this no longer
// captures date/time manually. Instead it polls for the appointment that
// webhook just created for this contact and offers a one-click way to stop
// its 24h/6h/1h reminders (without canceling the appointment itself) in case
// the rep books something that shouldn't send them — e.g. an internal test,
// or the prospect asks not to be texted.
//
// Requires contactId — a prospect not yet linked to a CRM contact has no way
// to be matched back to the webhook-created row, so this falls back to a
// plain "booked automatically" notice with no stop control in that case.
export default function BookingForm({ contactId, onBooked }) {
  const [appointment, setAppointment] = useState(null);
  const [checked, setChecked] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [stopped, setStopped] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!contactId) { setChecked(true); return; }
    let cancelled = false;
    const check = async () => {
      try {
        const r = await fetch(API(`/appointment-reminders?status=scheduled&contact_id=${encodeURIComponent(contactId)}`));
        if (r.ok && !cancelled) {
          const rows = await r.json();
          if (rows.length) { setAppointment(rows[0]); onBooked?.(); }
        }
      } catch {}
      if (!cancelled) setChecked(true);
    };
    check();
    // Polls while the modal is open — the webhook can take a few seconds
    // after the rep completes the Calendly iframe booking.
    const id = setInterval(check, 4000);
    return () => { cancelled = true; clearInterval(id); };
  }, [contactId]);

  const stopReminders = async () => {
    if (!appointment) return;
    setStopping(true);
    setError("");
    try {
      const r = await fetch(API(`/appointment-reminders/${appointment.id}/sequence/reminder/remove`), { method: "POST" });
      if (!r.ok) throw new Error(await r.text());
      setStopped(true);
    } catch (e) {
      setError("Failed to stop reminders — " + (e.message || "unknown error"));
    }
    setStopping(false);
  };

  return (
    <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 10, padding: "10px 14px", borderTop: "1px solid #1a2540" }}>
      {!contactId ? (
        <div style={{ fontSize: 11.5, color: "#5a6f8f", fontFamily: "'Space Grotesk', sans-serif" }}>
          Book using the Calendly widget above — reminders are scheduled automatically once it's booked. (No linked contact here, so there's no automatic way to stop them from this window — use the Appointments tab afterward if needed.)
        </div>
      ) : stopped ? (
        <div style={{ fontSize: 12, color: "#f0a028", fontFamily: "'Space Grotesk', sans-serif" }}>
          Reminders stopped for this appointment — it's still on the books, it just won't text/email the prospect.
        </div>
      ) : appointment ? (
        <>
          <div style={{ fontSize: 12, color: "#14c882", fontFamily: "'Space Grotesk', sans-serif" }}>
            ✅ Booked for {fmtWhen(appointment.appointment_at)} — reminders scheduled automatically.
          </div>
          <button className="btn btn-danger" disabled={stopping} onClick={stopReminders} style={{ fontSize: 11, padding: "6px 12px" }}>
            {stopping ? "Stopping…" : "Stop Reminders"}
          </button>
        </>
      ) : (
        <div style={{ fontSize: 11.5, color: "#5a6f8f", fontFamily: "'Space Grotesk', sans-serif" }}>
          {checked ? "Book using the Calendly widget above — reminders will be scheduled automatically once it's booked (usually within a few seconds)." : "Checking…"}
        </div>
      )}
      {error && <div style={{ fontSize: 11, color: "#dc3c3c", width: "100%" }}>{error}</div>}
    </div>
  );
}
