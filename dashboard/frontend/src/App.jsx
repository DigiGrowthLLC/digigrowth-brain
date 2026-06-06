import React, { useState } from "react";
import DashboardPanel from "./panels/DashboardPanel.jsx";
import CRMPanel       from "./panels/CRMPanel.jsx";
import SMSPanel       from "./panels/SMSPanel.jsx";
import DialerPanel    from "./panels/DialerPanel.jsx";

const NAV = [
  { id: "home",      label: "Dashboard", icon: "DASH", ready: true  },
  { id: "crm",       label: "CRM",       icon: "CRM",  ready: true  },
  { id: "dialer",    label: "Dialer",    icon: "DIAL", ready: true  },
  { id: "sms",       label: "SMS Inbox", icon: "SMS",  ready: true  },
  { id: "agents",    label: "Agents",    icon: "AGT",  ready: false },
  { id: "analytics", label: "Analytics", icon: "ANLT", ready: false },
];

const LogoMark = () => (
  <div style={{
    width: 36, height: 36,
    background: "#1a3a6b",
    border: "0.5px solid #2857a0",
    borderRadius: 6,
    display: "flex", alignItems: "center", justifyContent: "center",
    flexShrink: 0,
  }}>
    <svg viewBox="0 0 22 22" fill="none" width={20} height={20}>
      <path d="M4 18L11 4L18 18" stroke="#6ab0ff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M6.5 13h9" stroke="#3a7bd5" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  </div>
);

export default function App() {
  const [active, setActive] = useState("home");

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: "#080c14" }}>
      {/* Sidebar */}
      <aside style={{
        width: 200,
        background: "#080c14",
        borderRight: "0.5px solid #1a2540",
        display: "flex",
        flexDirection: "column",
        flexShrink: 0,
      }}>
        {/* Brand */}
        <div style={{ padding: "20px 16px 18px", borderBottom: "0.5px solid #1a2540" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <LogoMark />
            <div>
              <div style={{
                fontFamily: "'Space Grotesk', sans-serif",
                fontSize: 15,
                fontWeight: 700,
                color: "#f0f4ff",
                letterSpacing: "-0.01em",
                lineHeight: 1.2,
              }}>
                DigiGrowth OS
              </div>
              <div style={{
                fontFamily: "'Share Tech Mono', monospace",
                fontSize: 9,
                color: "#3a5a80",
                letterSpacing: "0.14em",
                marginTop: 2,
              }}>
                CLIENT ACQ. PLATFORM
              </div>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav style={{ flex: 1, padding: "10px 8px" }}>
          {NAV.map(({ id, label, icon, ready }) => {
            const isActive = active === id;
            return (
              <button
                key={id}
                onClick={() => ready && setActive(id)}
                style={{
                  width: "100%",
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "8px 10px",
                  marginBottom: 2,
                  borderRadius: 4,
                  border: "none",
                  cursor: ready ? "pointer" : "not-allowed",
                  background: isActive ? "#111e36" : "transparent",
                  borderLeft: isActive ? "2px solid #3a7bd5" : "2px solid transparent",
                  transition: "all 0.15s",
                  textAlign: "left",
                }}
                onMouseEnter={e => {
                  if (!isActive && ready) e.currentTarget.style.background = "#0d1626";
                }}
                onMouseLeave={e => {
                  if (!isActive) e.currentTarget.style.background = "transparent";
                }}
              >
                <span style={{
                  fontFamily: "'Share Tech Mono', monospace",
                  fontSize: 9,
                  fontWeight: 600,
                  letterSpacing: "0.08em",
                  color: isActive ? "#3a7bd5" : ready ? "#3a5a80" : "#1e2f4a",
                  minWidth: 28,
                }}>
                  {icon}
                </span>
                <span style={{
                  fontFamily: "'Space Grotesk', sans-serif",
                  fontSize: 13,
                  fontWeight: isActive ? 600 : 400,
                  color: isActive ? "#d0dcf0" : ready ? "#5a6f8f" : "#2a3a50",
                }}>
                  {label}
                </span>
                {!ready && (
                  <span style={{
                    marginLeft: "auto",
                    fontFamily: "'Share Tech Mono', monospace",
                    fontSize: 8,
                    color: "#1e2f4a",
                    letterSpacing: "0.1em",
                  }}>
                    SOON
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        {/* Footer */}
        <div style={{
          padding: "12px 16px",
          borderTop: "0.5px solid #1a2540",
          fontFamily: "'Share Tech Mono', monospace",
          fontSize: 9,
          color: "#1e2f4a",
          letterSpacing: "0.12em",
        }}>
          SYS · V2.0 · LIVE
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-hidden flex flex-col" style={{ background: "#080c14" }}>
        {active === "home"   && <DashboardPanel />}
        {active === "crm"    && <CRMPanel />}
        {active === "sms"    && <SMSPanel />}
        {active === "dialer" && <DialerPanel />}
        {!["home","crm","sms","dialer"].includes(active) && (
          <div className="flex-1 flex flex-col items-center justify-center gap-3">
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a3a60", letterSpacing: "0.2em" }}>
              MODULE OFFLINE
            </div>
            <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 22, fontWeight: 700, color: "#1a2f52" }}>
              Coming Soon
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
