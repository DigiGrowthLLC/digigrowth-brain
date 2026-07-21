// Shared disposition list — used by the Dialer panel's post-hangup
// classification grid and the inbound CallScreen's post-hangup grid, so both
// stay in sync (backed by the same models.py DISPOSITION_TO_STATUS map).

export const DISPO_COLORS = {
  "Appointment Booked": { text: "#14c882", bg: "rgba(20,200,130,0.08)", border: "rgba(20,200,130,0.2)" },
  "Follow Up 30 Day":   { text: "#5a9bf0", bg: "rgba(58,123,213,0.08)", border: "rgba(58,123,213,0.2)" },
  "Follow Up 90 Day":   { text: "#5a9bf0", bg: "rgba(58,123,213,0.08)", border: "rgba(58,123,213,0.2)" },
  "Send Info":          { text: "#a080f0", bg: "rgba(120,80,210,0.08)", border: "rgba(120,80,210,0.2)" },
  "Not Interested":     { text: "#dc3c3c", bg: "rgba(220,60,60,0.08)",  border: "rgba(220,60,60,0.2)"  },
  "No Answer":          { text: "#3a4f6f", bg: "transparent",           border: "#1a2540"               },
  "Voicemail":          { text: "#f0a028", bg: "rgba(240,160,40,0.08)", border: "rgba(240,160,40,0.2)" },
  "SMS Handoff":        { text: "#a080f0", bg: "rgba(120,80,210,0.08)", border: "rgba(120,80,210,0.2)" },
  "Gatekeeper":         { text: "#f07028", bg: "rgba(240,112,40,0.08)", border: "rgba(240,112,40,0.2)" },
  "Not Qualified":      { text: "#8a5cf0", bg: "rgba(138,92,240,0.08)", border: "rgba(138,92,240,0.2)" },
  "Follow Up (Manual)": { text: "#f0a028", bg: "rgba(240,160,40,0.08)", border: "rgba(240,160,40,0.2)" },
  "Missed Callback":    { text: "#dc3c3c", bg: "rgba(220,60,60,0.08)",  border: "rgba(220,60,60,0.2)"  },
};

export const DISPO_BUTTONS = [
  { label: "Appointment Booked", emoji: "✅", style: { background: "rgba(20,200,130,0.12)",  border: "1px solid rgba(20,200,130,0.3)",  color: "#14c882" } },
  { label: "Follow Up 30 Day",  emoji: "📅", style: { background: "rgba(58,123,213,0.12)",  border: "1px solid rgba(58,123,213,0.3)",  color: "#5a9bf0" } },
  { label: "Follow Up 90 Day",  emoji: "🗓️", style: { background: "rgba(90,60,200,0.12)",   border: "1px solid rgba(90,60,200,0.3)",   color: "#9070e8" } },
  { label: "Send Info",         emoji: "📧", style: { background: "rgba(120,80,210,0.12)",  border: "1px solid rgba(120,80,210,0.3)",  color: "#a080f0" } },
  { label: "Not Interested",    emoji: "🚫", style: { background: "rgba(220,60,60,0.12)",   border: "1px solid rgba(220,60,60,0.3)",   color: "#dc3c3c" } },
  { label: "Not Qualified",     emoji: "⛔", style: { background: "rgba(138,92,240,0.12)",  border: "1px solid rgba(138,92,240,0.3)",  color: "#8a5cf0" } },
  { label: "Gatekeeper",        emoji: "🤖", style: { background: "rgba(240,112,40,0.12)",  border: "1px solid rgba(240,112,40,0.3)",  color: "#f07028" } },
  { label: "No Answer",         emoji: "—",  style: { background: "rgba(30,47,80,0.4)",     border: "1px solid #1a2540",               color: "#3a5a80" } },
  { label: "Voicemail",         emoji: "📬", style: { background: "rgba(240,160,40,0.12)",  border: "1px solid rgba(240,160,40,0.3)",  color: "#f0a028" } },
  { label: "SMS Handoff",       emoji: "💬", style: { background: "rgba(120,80,210,0.12)",  border: "1px solid rgba(120,80,210,0.3)",  color: "#a080f0" } },
  { label: "Follow Up (Manual)", emoji: "📌", style: { background: "rgba(240,160,40,0.12)", border: "1px solid rgba(240,160,40,0.3)",  color: "#f0a028" } },
];

// ?month= pins Calendly to the current month so it always opens on today's
// month instead of drifting to a hardcoded one.
export const CALENDLY_URL = `https://calendly.com/dylanrg-digigrowthllc/30min?month=${new Date().toISOString().slice(0, 7)}`;
