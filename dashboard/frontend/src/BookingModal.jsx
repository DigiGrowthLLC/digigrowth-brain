import React from "react";
import { CALENDLY_URL } from "./dispositions.js";
import BookingForm from "./BookingForm.jsx";

// Shared "book on Calendly + capture the reminder details" modal — the
// Calendly iframe for live booking plus BookingForm for the reminder
// pipeline's date/time/timezone capture (Calendly's free plan has no
// webhook, so this is how appointment_reminders rows get created).
// Used from the Dialer, the inbound CallScreen, the SMS Inbox, and the
// Contact Card — anywhere a rep can book an appointment for a prospect.
export default function BookingModal({ open, onClose, contactId, phone, name, email, onBooked }) {
  if (!open) return null;
  return (
    <div onClick={(e) => e.target === e.currentTarget && onClose?.()} style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)",
      display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000, padding: 24,
    }}>
      <div style={{
        background: "#0d1830", border: "1px solid #1a2540", borderRadius: 12,
        width: "100%", maxWidth: 860, height: "85vh",
        display: "flex", flexDirection: "column", overflow: "hidden",
        boxShadow: "0 24px 64px rgba(0,0,0,0.6)",
      }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between",
                       padding: "14px 20px", borderBottom: "1px solid #1a2540", flexShrink: 0 }}>
          <span style={{ fontSize: 14, fontWeight: 700, color: "#f0f4ff" }}>Book Appointment</span>
          <button onClick={onClose} style={{
            background: "rgba(30,47,80,0.5)", border: "1px solid #1a2540",
            borderRadius: 6, color: "#5a6f8f", width: 30, height: 30, cursor: "pointer", fontSize: 16,
          }}>✕</button>
        </div>
        <div style={{ flex: 1, overflow: "hidden" }}>
          <iframe src={CALENDLY_URL} style={{ width: "100%", height: "100%", border: "none" }} allow="camera; microphone" />
        </div>
        <BookingForm contactId={contactId} phone={phone} name={name} email={email} onBooked={onBooked} />
      </div>
    </div>
  );
}
