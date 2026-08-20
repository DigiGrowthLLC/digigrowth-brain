import React, { useState, useEffect } from "react";
import { CALENDLY_URL } from "./dispositions.js";
import { API } from "./api.js";
import BookingForm from "./BookingForm.jsx";

// One labeled value + a click-to-copy button — the building block of
// ProspectInfoPanel below. Skips rendering entirely when there's no value,
// so the panel never shows a row of blank fields for whichever surface
// didn't have that piece of data on hand.
function CopyableField({ label, value }) {
  const [copied, setCopied] = useState(false);
  if (!value) return null;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {}
  };

  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ fontSize: 9, letterSpacing: "0.08em", color: "#3a5a80", fontFamily: "'Share Tech Mono', monospace", marginBottom: 3 }}>
        {label.toUpperCase()}
      </div>
      <div
        onClick={copy}
        title="Click to copy"
        style={{
          display: "flex", alignItems: "center", gap: 6, cursor: "pointer",
          padding: "5px 8px", borderRadius: 6,
          background: "rgba(255,255,255,0.03)", border: "1px solid rgba(58,123,213,0.15)",
        }}
      >
        <span style={{ flex: 1, fontSize: 12.5, color: "#e8f0ff", wordBreak: "break-word" }}>{value}</span>
        <span style={{ flexShrink: 0, fontSize: 10, color: copied ? "#14c882" : "#3a5a80" }}>
          {copied ? "Copied ✓" : "Copy"}
        </span>
      </div>
    </div>
  );
}

// Sits alongside the Calendly iframe + BookingForm so the rep can see (and
// copy/paste) the prospect's own details while actually booking them into
// Calendly, instead of the info being hidden behind this full-screen modal.
// `contact` carries whatever extra fields the calling surface has on hand
// (business/city/state/grade/website) — every caller already has
// name/phone/email as separate props, so those are read directly.
function ProspectInfoPanel({ name, phone, email, contact }) {
  const [timezone, setTimezone] = useState(null);

  useEffect(() => {
    if (!phone) return;
    fetch(API(`/appointment-reminders/guess-timezone?phone=${encodeURIComponent(phone)}`))
      .then(r => r.json())
      .then(d => setTimezone(d.timezone || null))
      .catch(() => {});
  }, [phone]);

  const c = contact || {};

  return (
    <div style={{
      width: 280, flexShrink: 0, borderLeft: "1px solid #1a2540",
      padding: "16px 16px 20px", overflowY: "auto",
    }}>
      <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.08em", color: "#7a9cc0", marginBottom: 14 }}>
        PROSPECT INFO
      </div>
      <CopyableField label="Name" value={name} />
      <CopyableField label="Business" value={c.business} />
      <CopyableField label="Phone" value={phone} />
      <CopyableField label="Email" value={email} />
      <CopyableField label="Timezone" value={timezone} />
      <CopyableField label="Website" value={c.website} />
      <CopyableField label="City" value={c.city} />
      <CopyableField label="State" value={c.state} />
      <CopyableField label="Grade" value={c.grade} />
    </div>
  );
}

// Shared "book on Calendly + capture the reminder details" modal — the
// Calendly iframe for live booking plus BookingForm for the reminder
// pipeline's date/time/timezone capture (Calendly's free plan has no
// webhook, so this is how appointment_reminders rows get created), plus a
// ProspectInfoPanel so the prospect's details stay visible/copyable while
// booking — this modal covers the whole screen, so whatever contact info
// was visible before opening it isn't anymore.
// Used from the Dialer, the inbound CallScreen, the SMS Inbox, and the
// Contact Card — anywhere a rep can book an appointment for a prospect.
export default function BookingModal({ open, onClose, contactId, phone, name, email, channel, contact, onBooked }) {
  if (!open) return null;
  return (
    <div onClick={(e) => e.target === e.currentTarget && onClose?.()} style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)",
      display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000, padding: 24,
    }}>
      <div style={{
        background: "#0d1830", border: "1px solid #1a2540", borderRadius: 12,
        width: "100%", maxWidth: 1180, height: "85vh",
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
        <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
          <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
            <div style={{ flex: 1, overflow: "hidden" }}>
              <iframe src={CALENDLY_URL} style={{ width: "100%", height: "100%", border: "none" }} allow="camera; microphone" />
            </div>
            <BookingForm contactId={contactId} phone={phone} name={name} email={email} channel={channel} onBooked={onBooked} />
          </div>
          <ProspectInfoPanel name={name} phone={phone} email={email} contact={contact} />
        </div>
      </div>
    </div>
  );
}
