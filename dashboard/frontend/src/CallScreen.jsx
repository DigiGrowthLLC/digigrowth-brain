import React, { useState, useEffect } from "react";
import { API } from "./api.js";
import ContactCard from "./ContactCard.jsx";
import { DISPO_BUTTONS, CALENDLY_URL } from "./dispositions.js";

function fmtElapsed(sec) {
  const m = Math.floor(sec / 60).toString().padStart(2, "0");
  const s = Math.floor(sec % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

// Shown in <main> (App.jsx) in place of the normal panels while an inbound
// call answered via IncomingCallWidget is live, and afterward for logging
// the disposition — mirrors the Dialer panel's live-book + classify pattern.
export default function CallScreen({ callInfo, live, onHangUp, onDone }) {
  const [elapsed, setElapsed] = useState(0);
  const [classifying, setClassifying] = useState(false);
  const [notes, setNotes] = useState("");
  const [bookingOpen, setBookingOpen] = useState(false);
  const [bookedLive, setBookedLive] = useState(false);

  useEffect(() => {
    if (!live) return;
    const start = Date.now();
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - start) / 1000)), 1000);
    return () => clearInterval(id);
  }, [live]);

  // Call ended (remote hangup or End Call) with a disposition already logged
  // live mid-call ("Appointment Booked") — don't ask to classify it twice.
  useEffect(() => {
    if (!live && bookedLive) onDone?.();
  }, [live, bookedLive]);

  const classify = async (disposition) => {
    setClassifying(true);
    try {
      await fetch(API("/dialer/classify"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          disposition, notes,
          contact_id: callInfo?.contactId,
          phone: callInfo?.phone,
        }),
      });
      setNotes("");
      if (disposition === "Appointment Booked") {
        setBookingOpen(true);
        if (live) setBookedLive(true);
      } else {
        onDone?.();
      }
    } catch {}
    setClassifying(false);
  };

  const label = callInfo?.name || callInfo?.business || callInfo?.phone || "Unknown caller";

  return (
    <div style={{ flex: 1, overflowY: "auto", padding: 24, display: "flex", flexDirection: "column", gap: 20, maxWidth: 640, margin: "0 auto", width: "100%", boxSizing: "border-box" }}>

      {/* Call header */}
      <div className="glass-card" style={{ padding: "20px 24px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: live ? "#14c882" : "#3a5a80", letterSpacing: "0.15em", marginBottom: 4 }}>
            {live ? "● ON CALL" : "CALL ENDED"}
          </div>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 18, fontWeight: 700, color: "#f0f4ff" }}>
            {label}
          </div>
          {callInfo?.business && callInfo?.name && (
            <div style={{ fontSize: 12, color: "#5a6f8f", marginTop: 2 }}>{callInfo.business}</div>
          )}
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 11, color: "#3a5a80", marginTop: 6 }}>
            {callInfo?.phone} · {fmtElapsed(elapsed)}
          </div>
        </div>
        {live && (
          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={() => classify("Appointment Booked")} disabled={classifying} style={{
              padding: "10px 18px", borderRadius: 8, fontSize: 13, fontWeight: 700,
              background: "rgba(20,200,130,0.12)", color: "#14c882",
              border: "1px solid rgba(20,200,130,0.3)", cursor: classifying ? "not-allowed" : "pointer",
              opacity: classifying ? 0.5 : 1,
            }}>✅ Appointment Booked</button>
            <button onClick={onHangUp} style={{
              padding: "10px 24px", borderRadius: 8, fontSize: 13, fontWeight: 700,
              background: "rgba(220,60,60,0.15)", color: "#dc3c3c",
              border: "1px solid rgba(220,60,60,0.35)", cursor: "pointer",
            }}>End Call</button>
          </div>
        )}
      </div>

      {/* Post-call disposition */}
      {!live && !bookedLive && (
        <div className="glass-card" style={{ padding: 20, display: "flex", flexDirection: "column", gap: 10 }}>
          <div className="sec-label" style={{ marginBottom: 0 }}>Disposition</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
            {DISPO_BUTTONS.map(({ label: dLabel, emoji, style }) => (
              <button key={dLabel} disabled={classifying} onClick={() => classify(dLabel)} style={{
                ...style, borderRadius: 6, padding: "10px 8px",
                fontSize: 12, fontWeight: 600, cursor: classifying ? "not-allowed" : "pointer",
                opacity: classifying ? 0.5 : 1,
                fontFamily: "'Space Grotesk', sans-serif",
              }}>
                {emoji} {dLabel}
              </button>
            ))}
          </div>
          <textarea
            className="dg-input"
            placeholder="Call notes (optional)…"
            rows={2}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, resize: "none" }}
          />
        </div>
      )}

      {/* Contact card */}
      <div className="glass-card" style={{ padding: 20 }}>
        {callInfo?.contactId ? (
          <ContactCard contactId={callInfo.contactId} phone={callInfo.phone} variant="inline" />
        ) : (
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80" }}>
            No contact record found for {callInfo?.phone || "this number"}.<br />
            <span style={{ color: "#2a4070" }}>Create a contact from the CRM tab to link it.</span>
          </div>
        )}
      </div>

      {/* Booking modal */}
      {bookingOpen && (
        <div onClick={(e) => e.target === e.currentTarget && setBookingOpen(false)} style={{
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
              <button onClick={() => { setBookingOpen(false); if (!live) onDone?.(); }} style={{
                background: "rgba(30,47,80,0.5)", border: "1px solid #1a2540",
                borderRadius: 6, color: "#5a6f8f", width: 30, height: 30, cursor: "pointer", fontSize: 16,
              }}>✕</button>
            </div>
            <div style={{ flex: 1, overflow: "hidden" }}>
              <iframe src={CALENDLY_URL} style={{ width: "100%", height: "100%", border: "none" }} allow="camera; microphone" />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
