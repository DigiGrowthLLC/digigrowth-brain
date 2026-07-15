import React from "react";

export default function PeriodToggle({ days, setDays, options }) {
  return (
    <div style={{
      display: "flex", background: "rgba(10,18,48,0.7)",
      border: "1px solid rgba(58,123,213,0.1)", borderRadius: 12, padding: 4, gap: 2,
    }}>
      {options.map(([d, label]) => (
        <button key={d} onClick={() => setDays(d)} style={{
          fontFamily: "'Space Grotesk', sans-serif",
          fontSize: 11, fontWeight: 500, padding: "5px 14px",
          borderRadius: 9, border: "none", cursor: "pointer", transition: "all 0.15s",
          background: days === d ? "linear-gradient(135deg, #2857a0 0%, #3a7bd5 100%)" : "transparent",
          color: days === d ? "#fff" : "#4a6080",
          boxShadow: days === d ? "0 2px 10px rgba(58,123,213,0.4)" : "none",
        }}>{label}</button>
      ))}
    </div>
  );
}
