import React, { useState, useEffect } from "react";
import ContactCard from "./ContactCard.jsx";

function fmtElapsed(sec) {
  const m = Math.floor(sec / 60).toString().padStart(2, "0");
  const s = Math.floor(sec % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

// Shown in <main> (App.jsx) in place of the normal panels while an inbound
// call answered via IncomingCallWidget is live.
export default function CallScreen({ callInfo, onHangUp }) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const start = Date.now();
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - start) / 1000)), 1000);
    return () => clearInterval(id);
  }, []);

  const label = callInfo?.name || callInfo?.business || callInfo?.phone || "Unknown caller";

  return (
    <div style={{ flex: 1, overflowY: "auto", padding: 24, display: "flex", flexDirection: "column", gap: 20, maxWidth: 640, margin: "0 auto", width: "100%", boxSizing: "border-box" }}>

      {/* Call header */}
      <div className="glass-card" style={{ padding: "20px 24px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#14c882", letterSpacing: "0.15em", marginBottom: 4 }}>
            ● ON CALL
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
        <button onClick={onHangUp} style={{
          padding: "10px 24px", borderRadius: 8, fontSize: 13, fontWeight: 700,
          background: "rgba(220,60,60,0.15)", color: "#dc3c3c",
          border: "1px solid rgba(220,60,60,0.35)", cursor: "pointer",
        }}>End Call</button>
      </div>

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
    </div>
  );
}
