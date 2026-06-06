import React, { useState } from "react";
import DashboardPanel from "./panels/DashboardPanel.jsx";
import CRMPanel       from "./panels/CRMPanel.jsx";
import SMSPanel       from "./panels/SMSPanel.jsx";
import DialerPanel    from "./panels/DialerPanel.jsx";

const NAV = [
  { id: "home",      label: "Dashboard", icon: "⚡", ready: true  },
  { id: "crm",       label: "CRM",       icon: "👥", ready: true  },
  { id: "dialer",    label: "Dialer",    icon: "📞", ready: true  },
  { id: "sms",       label: "SMS Inbox", icon: "💬", ready: true  },
  { id: "agents",    label: "Agents",    icon: "🤖", ready: false },
  { id: "analytics", label: "Analytics", icon: "📊", ready: false },
];

const LogoMark = () => (
  <div style={{
    width: 38, height: 38, flexShrink: 0,
    background: "linear-gradient(135deg, #1a3a6b 0%, #2857a0 100%)",
    borderRadius: 10,
    border: "1px solid rgba(58,123,213,0.3)",
    display: "flex", alignItems: "center", justifyContent: "center",
    boxShadow: "0 4px 12px rgba(40,87,160,0.4)",
  }}>
    <svg viewBox="0 0 22 22" fill="none" width={18} height={18}>
      <path d="M4 18L11 4L18 18" stroke="#6ab0ff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M6.5 13h9" stroke="#3a7bd5" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  </div>
);

export default function App() {
  const [active, setActive] = useState("home");

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden" }}>

      {/* Sidebar */}
      <aside style={{
        width: 220,
        background: "linear-gradient(180deg, rgba(9,15,38,0.98) 0%, rgba(7,12,30,0.98) 100%)",
        borderRight: "1px solid rgba(58,123,213,0.07)",
        display: "flex", flexDirection: "column", flexShrink: 0,
        backdropFilter: "blur(20px)",
      }}>

        {/* Brand */}
        <div style={{ padding: "22px 18px 20px", borderBottom: "1px solid rgba(58,123,213,0.07)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 11 }}>
            <LogoMark />
            <div>
              <div style={{
                fontFamily: "'Space Grotesk', sans-serif",
                fontSize: 15, fontWeight: 700,
                color: "#f0f4ff", letterSpacing: "-0.01em", lineHeight: 1.2,
              }}>
                DigiGrowth OS
              </div>
              <div style={{
                fontFamily: "'Share Tech Mono', monospace",
                fontSize: 9, color: "#2a4a7a", letterSpacing: "0.14em", marginTop: 2,
              }}>
                CLIENT ACQ. PLATFORM
              </div>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav style={{ flex: 1, padding: "14px 12px", display: "flex", flexDirection: "column", gap: 3 }}>
          {NAV.map(({ id, label, icon, ready }) => {
            const isActive = active === id;
            return (
              <button key={id}
                onClick={() => ready && setActive(id)}
                style={{
                  width: "100%", display: "flex", alignItems: "center", gap: 10,
                  padding: "10px 14px", borderRadius: 12,
                  border: "none", cursor: ready ? "pointer" : "not-allowed",
                  background: isActive
                    ? "linear-gradient(90deg, #2857a0 0%, #3a7bd5 100%)"
                    : "transparent",
                  boxShadow: isActive ? "0 4px 18px rgba(58,123,213,0.4)" : "none",
                  transition: "all 0.2s", textAlign: "left",
                }}
                onMouseEnter={e => {
                  if (!isActive && ready) e.currentTarget.style.background = "rgba(58,123,213,0.08)";
                }}
                onMouseLeave={e => {
                  if (!isActive) e.currentTarget.style.background = "transparent";
                }}
              >
                <span style={{ fontSize: 16, lineHeight: 1, opacity: isActive ? 1 : ready ? 0.7 : 0.3 }}>
                  {icon}
                </span>
                <span style={{
                  fontFamily: "'Space Grotesk', sans-serif",
                  fontSize: 13, fontWeight: isActive ? 600 : 400,
                  color: isActive ? "#ffffff" : ready ? "#6080a8" : "#2a3a50",
                }}>
                  {label}
                </span>
                {!ready && (
                  <span style={{
                    marginLeft: "auto",
                    fontFamily: "'Share Tech Mono', monospace",
                    fontSize: 8, color: "#1e2f4a", letterSpacing: "0.1em",
                  }}>
                    SOON
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        {/* Bottom card (Need help style) */}
        <div style={{
          margin: "0 12px 16px",
          padding: "14px 16px",
          borderRadius: 16,
          background: "linear-gradient(135deg, rgba(40,87,160,0.25) 0%, rgba(58,123,213,0.12) 100%)",
          border: "1px solid rgba(58,123,213,0.15)",
        }}>
          <div style={{
            fontFamily: "'Space Grotesk', sans-serif",
            fontSize: 12, fontWeight: 600, color: "#c4d0e8", marginBottom: 3,
          }}>
            DigiGrowth LLC
          </div>
          <div style={{
            fontFamily: "'Share Tech Mono', monospace",
            fontSize: 9, color: "#3a5a80", letterSpacing: "0.12em",
          }}>
            SYS · V2.0 · LIVE
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main style={{
        flex: 1, overflow: "hidden", display: "flex", flexDirection: "column",
        background: "transparent",
      }}>
        {active === "home"   && <DashboardPanel />}
        {active === "crm"    && <CRMPanel />}
        {active === "sms"    && <SMSPanel />}
        {active === "dialer" && <DialerPanel />}
        {!["home","crm","sms","dialer"].includes(active) && (
          <div style={{
            flex: 1, display: "flex", flexDirection: "column",
            alignItems: "center", justifyContent: "center", gap: 10,
          }}>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a3a60", letterSpacing: "0.2em" }}>
              MODULE OFFLINE
            </div>
            <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 24, fontWeight: 700, color: "#1a2f52" }}>
              Coming Soon
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
