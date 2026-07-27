import React, { useState, useEffect } from "react";
import { API } from "./api.js";

// Appointment-reminder capture form — shown alongside the Calendly iframe
// when a rep dispositions a call "Appointment Booked". Calendly itself has
// no webhook wired up (free plan), so this is how the reminder pipeline
// learns the booked date/time + the prospect's timezone. See
// dashboard/backend/routers/appointments.py + reminder_engine.py.
export default function BookingForm({ contactId, phone, name, email, onBooked }) {
  const [timezones, setTimezones] = useState([]);
  const [date, setDate]           = useState("");
  const [time, setTime]           = useState("");
  const [tz, setTz]               = useState("America/New_York");
  const [saving, setSaving]       = useState(false);
  const [saved, setSaved]         = useState(false);
  const [error, setError]         = useState("");

  useEffect(() => {
    fetch(API("/appointment-reminders/timezones")).then(r => r.json()).then(setTimezones).catch(() => {});
  }, []);

  useEffect(() => {
    if (!phone) return;
    fetch(API(`/appointment-reminders/guess-timezone?phone=${encodeURIComponent(phone)}`))
      .then(r => r.json())
      .then(d => { if (d.timezone) setTz(d.timezone); })
      .catch(() => {});
  }, [phone]);

  const save = async () => {
    if (!date || !time) { setError("Enter the appointment date and time"); return; }
    setSaving(true);
    setError("");
    try {
      const r = await fetch(API("/appointment-reminders"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          contact_id: contactId || null,
          prospect_name: name || null,
          prospect_phone: phone || null,
          prospect_email: email || null,
          date, time, timezone: tz,
        }),
      });
      if (!r.ok) throw new Error(await r.text());
      setSaved(true);
      onBooked?.();
    } catch (e) {
      setError("Failed to save — " + (e.message || "unknown error"));
    }
    setSaving(false);
  };

  if (saved) {
    return (
      <div style={{ padding: "10px 14px", fontSize: 12, color: "#14c882", fontFamily: "'Space Grotesk', sans-serif" }}>
        ✅ Confirmation sent, reminders scheduled — 24h, 6h, and 1h before the appointment.
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", gap: 8, padding: "10px 14px", borderTop: "1px solid #1a2540" }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
        <label style={{ fontSize: 10, color: "#5a6f8f" }}>Date</label>
        <input type="date" className="dg-input" value={date} onChange={e => setDate(e.target.value)} style={{ fontSize: 12, padding: "6px 8px" }} />
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
        <label style={{ fontSize: 10, color: "#5a6f8f" }}>Time</label>
        <input type="time" className="dg-input" value={time} onChange={e => setTime(e.target.value)} style={{ fontSize: 12, padding: "6px 8px" }} />
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
        <label style={{ fontSize: 10, color: "#5a6f8f" }}>Prospect's Timezone</label>
        <select className="dg-input" value={tz} onChange={e => setTz(e.target.value)} style={{ fontSize: 12, padding: "6px 8px" }}>
          {timezones.map(t => <option key={t.iana} value={t.iana}>{t.label}</option>)}
        </select>
      </div>
      <button className="btn btn-primary" disabled={saving} onClick={save} style={{ fontSize: 12, padding: "7px 14px" }}>
        {saving ? "Saving…" : "Schedule Reminders"}
      </button>
      {error && <div style={{ fontSize: 11, color: "#dc3c3c", width: "100%" }}>{error}</div>}
    </div>
  );
}
