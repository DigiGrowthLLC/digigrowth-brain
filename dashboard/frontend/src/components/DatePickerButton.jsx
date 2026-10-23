import React, { useRef } from "react";

// Calendar button next to a period toggle: pick one specific day and the
// panel shows that day's numbers (the backend's ?date=YYYY-MM-DD, an Eastern
// calendar day). `date` is null when a regular period is selected instead.

export function etToday() {
  // en-CA formats as YYYY-MM-DD.
  return new Intl.DateTimeFormat("en-CA", { timeZone: "America/New_York" }).format(new Date());
}

export function formatPickedDate(date) {
  // Noon, so no timezone can shift the label onto a neighbouring day.
  return new Date(`${date}T12:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export default function DatePickerButton({ date, setDate }) {
  const inputRef = useRef(null);
  const active = !!date;

  const open = () => {
    try { inputRef.current?.showPicker(); } catch { inputRef.current?.focus(); }
  };

  return (
    <div style={{
      position: "relative", display: "flex", alignItems: "center",
      background: "rgba(10,18,48,0.7)", border: "1px solid rgba(58,123,213,0.1)",
      borderRadius: 12, padding: 4,
    }}>
      <button onClick={open} title="View a specific day" style={{
        display: "flex", alignItems: "center", gap: 7,
        fontFamily: "'Space Grotesk', sans-serif", fontSize: 11, fontWeight: 500,
        padding: active ? "5px 10px" : "5px 9px",
        borderRadius: 9, border: "none", cursor: "pointer", transition: "all 0.15s",
        background: active ? "linear-gradient(135deg, #2857a0 0%, #3a7bd5 100%)" : "transparent",
        color: active ? "#fff" : "#4a6080",
        boxShadow: active ? "0 2px 10px rgba(58,123,213,0.4)" : "none",
      }}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
             strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <rect x="3" y="4" width="18" height="18" rx="2" />
          <path d="M16 2v4M8 2v4M3 10h18" />
        </svg>
        {active && formatPickedDate(date)}
      </button>
      {active && (
        <button onClick={() => setDate(null)} title="Clear date" style={{
          marginLeft: 2, width: 22, height: 22, borderRadius: 7, border: "none", cursor: "pointer",
          background: "transparent", color: "#4a6080", fontSize: 14, lineHeight: 1,
        }}>×</button>
      )}
      <input
        ref={inputRef}
        type="date"
        value={date || ""}
        max={etToday()}
        onChange={e => setDate(e.target.value || null)}
        tabIndex={-1}
        aria-hidden="true"
        style={{
          position: "absolute", left: 0, bottom: 0, width: 1, height: 1,
          opacity: 0, pointerEvents: "none", colorScheme: "dark",
        }}
      />
    </div>
  );
}
