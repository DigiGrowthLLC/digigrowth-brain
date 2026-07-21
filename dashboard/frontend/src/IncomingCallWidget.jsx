import React from "react";

// Presentational only — Twilio Device/call state lives in useIncomingCall(),
// owned by App.jsx so it can also drive navigation to CallScreen on answer.
// Renders the ringing popup (Answer/Decline) top-right, or — once answered —
// a small "on call" bar when the user has navigated away from CallScreen,
// so the call stays visible/endable no matter which tab they're on.
export default function IncomingCallWidget({ incoming, activeCall, callInfo, onAnswer, onDecline, onHangUp, onReturnToCall, showMiniBar }) {
  if (!incoming && !(activeCall && showMiniBar)) return null;

  const label = callInfo?.name || callInfo?.business || callInfo?.phone || "Unknown caller";

  return (
    <div style={{
      position: "fixed", top: 24, right: 24, zIndex: 2000,
      background: "#0d1830", border: `1px solid ${incoming ? "rgba(20,200,130,0.4)" : "rgba(58,123,213,0.4)"}`,
      borderRadius: 12, padding: "16px 18px", width: 260,
      boxShadow: "0 8px 32px rgba(0,0,0,0.6)",
    }}>
      <div style={{ textAlign: "center" }}>
        <div style={{ fontSize: 22, marginBottom: 4 }}>{incoming ? "📞" : "🔊"}</div>
        <div style={{ fontSize: 13, fontWeight: 700, color: "#f0f4ff", marginBottom: 2 }}>
          {incoming ? "Incoming Call" : "On Call"}
        </div>
        <div style={{
          fontFamily: "'Share Tech Mono', monospace", fontSize: 11, color: "#8aaad0", marginBottom: 4,
          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
        }}>
          {label}
        </div>
        {callInfo?.business && callInfo?.name && (
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80", marginBottom: 10 }}>
            {callInfo.business}
          </div>
        )}
        {incoming ? (
          <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
            <button onClick={onAnswer} style={{
              flex: 1, padding: "8px 0", borderRadius: 6, fontSize: 12, fontWeight: 700,
              background: "rgba(20,200,130,0.2)", color: "#14c882",
              border: "1px solid rgba(20,200,130,0.4)", cursor: "pointer",
            }}>Answer</button>
            <button onClick={onDecline} style={{
              flex: 1, padding: "8px 0", borderRadius: 6, fontSize: 12, fontWeight: 700,
              background: "rgba(220,60,60,0.15)", color: "#dc3c3c",
              border: "1px solid rgba(220,60,60,0.35)", cursor: "pointer",
            }}>Decline</button>
          </div>
        ) : (
          <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
            <button onClick={onReturnToCall} style={{
              flex: 1, padding: "8px 0", borderRadius: 6, fontSize: 12, fontWeight: 700,
              background: "rgba(58,123,213,0.15)", color: "#5a9bf0",
              border: "1px solid rgba(58,123,213,0.35)", cursor: "pointer",
            }}>View</button>
            <button onClick={onHangUp} style={{
              flex: 1, padding: "8px 0", borderRadius: 6, fontSize: 12, fontWeight: 700,
              background: "rgba(220,60,60,0.15)", color: "#dc3c3c",
              border: "1px solid rgba(220,60,60,0.35)", cursor: "pointer",
            }}>End Call</button>
          </div>
        )}
      </div>
    </div>
  );
}
