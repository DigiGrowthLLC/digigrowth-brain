import React from "react";

const AUTO_DISMISS_MS = 8000;

// Stack of in-app SMS notification toasts, fixed to the top-right corner —
// visible over whichever nav tab is active. Rendered once at the App level.
export default function SmsToasts({ toasts, onOpen, onDismiss }) {
  if (!toasts.length) return null;

  return (
    <div style={{
      position: "fixed", top: 18, right: 18, zIndex: 2000,
      display: "flex", flexDirection: "column", gap: 10, width: 320,
      pointerEvents: "none",
    }}>
      {toasts.map(t => (
        <div
          key={t.id}
          onClick={() => onOpen(t)}
          style={{
            pointerEvents: "auto", cursor: "pointer",
            padding: "12px 14px", borderRadius: 12,
            background: "rgba(13,22,38,0.97)",
            border: "1px solid rgba(58,123,213,0.35)",
            boxShadow: "0 8px 28px rgba(0,0,0,0.45)",
            backdropFilter: "blur(12px)",
            animation: "dg-toast-in 0.18s ease-out",
          }}
        >
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
              <svg viewBox="0 0 16 16" fill="none" width={13} height={13} style={{ flexShrink: 0 }}>
                <path d="M13 2H3a1 1 0 00-1 1v7a1 1 0 001 1h2v2.5L8 11h5a1 1 0 001-1V3a1 1 0 00-1-1z"
                  stroke="#3a7bd5" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              <span style={{
                fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, fontWeight: 600, color: "#f0f4ff",
              }}>
                {t.label}
              </span>
            </div>
            <button
              onClick={e => { e.stopPropagation(); onDismiss(t.id); }}
              style={{
                background: "transparent", border: "none", color: "#3a5a80",
                cursor: "pointer", fontSize: 14, lineHeight: 1, padding: "0 2px", flexShrink: 0,
              }}
            >
              ×
            </button>
          </div>
          {t.body && (
            <div style={{
              marginTop: 5, fontSize: 12, color: "#8aaad0", lineHeight: 1.4,
              overflow: "hidden", textOverflow: "ellipsis",
              display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical",
            }}>
              {t.body}
            </div>
          )}
        </div>
      ))}
      <style>{`
        @keyframes dg-toast-in {
          from { opacity: 0; transform: translateY(-8px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}

export { AUTO_DISMISS_MS };
