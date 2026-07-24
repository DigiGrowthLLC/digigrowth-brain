import React, { useState, useEffect, useRef } from "react";
import DashboardPanel from "./panels/DashboardPanel.jsx";
import CRMPanel       from "./panels/CRMPanel.jsx";
import SMSPanel       from "./panels/SMSPanel.jsx";
import DialerPanel    from "./panels/DialerPanel.jsx";
import AgentsPanel    from "./panels/AgentsPanel.jsx";
import SettingsPanel  from "./panels/SettingsPanel.jsx";
import AnalyticsPanel from "./panels/AnalyticsPanel.jsx";
import FinancesPanel  from "./panels/FinancesPanel.jsx";
import SOPsPanel      from "./panels/SOPsPanel.jsx";
import TodoPanel      from "./panels/TodoPanel.jsx";
import WebsitePanel  from "./panels/WebsitePanel.jsx";
import IncomingCallWidget from "./IncomingCallWidget.jsx";
import CallScreen     from "./CallScreen.jsx";
import useIncomingCall from "./useIncomingCall.js";
import useSmsNotifications from "./useSmsNotifications.js";
import SmsToasts, { AUTO_DISMISS_MS } from "./SmsToasts.jsx";
import logoWordmark from "./assets/logo-wordmark.png";

const NAV = [
  { id: "home",      label: "Dashboard" },
  { id: "crm",       label: "CRM" },
  { id: "dialer",    label: "Dialer" },
  { id: "sms",       label: "SMS Inbox" },
  { id: "agents",    label: "Agents" },
  { id: "todos",     label: "To-Do" },
  { id: "analytics", label: "Analytics" },
  { id: "finances",  label: "Finances" },
  { id: "website",   label: "Website" },
  { id: "sops",      label: "Business Resources" },
  { id: "settings",  label: "Settings" },
];

const NAV_ICONS = {
  home: (
    <svg viewBox="0 0 16 16" fill="none" width={15} height={15}>
      <rect x="1" y="1" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.4"/>
      <rect x="9" y="1" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.4"/>
      <rect x="1" y="9" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.4"/>
      <rect x="9" y="9" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.4"/>
    </svg>
  ),
  crm: (
    <svg viewBox="0 0 16 16" fill="none" width={15} height={15}>
      <circle cx="6" cy="5" r="2.5" stroke="currentColor" strokeWidth="1.4"/>
      <path d="M1 13.5c0-2.485 2.239-4.5 5-4.5s5 2.015 5 4.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
      <path d="M12 7.5c1.105 0 2 .895 2 2v1" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
      <circle cx="12" cy="5.5" r="1.5" stroke="currentColor" strokeWidth="1.4"/>
    </svg>
  ),
  dialer: (
    <svg viewBox="0 0 16 16" fill="none" width={15} height={15}>
      <path d="M3 2h2.5l1 3-1.5 1c.667 1.333 2 2.667 3.333 3.333L9.5 7.833l3 1V11.5c0 .828-.672 1.5-1.5 1.5C5.373 13 2 8.627 2 3.5 2 2.672 2.672 2 3.5 2H3z" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  sms: (
    <svg viewBox="0 0 16 16" fill="none" width={15} height={15}>
      <path d="M13 2H3a1 1 0 00-1 1v7a1 1 0 001 1h2v2.5L8 11h5a1 1 0 001-1V3a1 1 0 00-1-1z" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M5 6.5h6M5 8.5h4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
    </svg>
  ),
  agents: (
    <svg viewBox="0 0 16 16" fill="none" width={15} height={15}>
      <rect x="2" y="5" width="12" height="9" rx="2" stroke="currentColor" strokeWidth="1.4"/>
      <path d="M8 5V3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
      <circle cx="8" cy="2.5" r="0.8" fill="currentColor"/>
      <circle cx="5.5" cy="9" r="1" fill="currentColor"/>
      <circle cx="10.5" cy="9" r="1" fill="currentColor"/>
      <path d="M6 11.5h4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
    </svg>
  ),
  todos: (
    <svg viewBox="0 0 16 16" fill="none" width={15} height={15}>
      <rect x="2" y="2" width="12" height="12" rx="2" stroke="currentColor" strokeWidth="1.4"/>
      <path d="M5 8l2 2 4-4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  analytics: (
    <svg viewBox="0 0 16 16" fill="none" width={15} height={15}>
      <path d="M2 13h12" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
      <rect x="3" y="8" width="2" height="5" rx="0.5" fill="currentColor" opacity="0.7"/>
      <rect x="7" y="5" width="2" height="8" rx="0.5" fill="currentColor" opacity="0.7"/>
      <rect x="11" y="2" width="2" height="11" rx="0.5" fill="currentColor" opacity="0.7"/>
    </svg>
  ),
  finances: (
    <svg viewBox="0 0 16 16" fill="none" width={15} height={15}>
      <rect x="1" y="3" width="14" height="10" rx="2" stroke="currentColor" strokeWidth="1.4"/>
      <path d="M1 6h14" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
      <rect x="3" y="9" width="3" height="1.5" rx="0.5" fill="currentColor" opacity="0.6"/>
    </svg>
  ),
  sops: (
    <svg viewBox="0 0 16 16" fill="none" width={15} height={15}>
      <rect x="2" y="1" width="12" height="14" rx="1.5" stroke="currentColor" strokeWidth="1.4"/>
      <path d="M5 5h6M5 8h6M5 11h4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
    </svg>
  ),
  website: (
    <svg viewBox="0 0 16 16" fill="none" width={15} height={15}>
      <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.4"/>
      <path d="M2 8h12M8 2c-1.5 2-2.5 3.8-2.5 6s1 4 2.5 6M8 2c1.5 2 2.5 3.8 2.5 6s-1 4-2.5 6" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
    </svg>
  ),
  settings: (
    <svg viewBox="0 0 16 16" fill="none" width={15} height={15}>
      <circle cx="8" cy="8" r="2.2" stroke="currentColor" strokeWidth="1.4"/>
      <path d="M8 1.5v1.2M8 13.3v1.2M1.5 8h1.2M13.3 8h1.2M3.4 3.4l.85.85M11.75 11.75l.85.85M3.4 12.6l.85-.85M11.75 4.25l.85-.85" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
    </svg>
  ),
};

const LogoMark = () => (
  <img src={logoWordmark} alt="DigiGrowth" style={{ height: 36, flexShrink: 0, display: "block" }} />
);

export default function App() {
  const [active, setActive] = useState("home");
  const [navContext, setNavContext] = useState(null);
  const prevActiveRef = useRef("home");

  const navigateTo = (panel, ctx = null) => {
    setNavContext(ctx);
    setActive(panel);
  };

  const { incoming, activeCall, callInfo, answer, decline, hangUp, clearCallInfo } = useIncomingCall();

  const [smsToasts, setSmsToasts] = useState([]);
  const dismissToast = (id) => setSmsToasts(list => list.filter(t => t.id !== id));
  useSmsNotifications((convo) => {
    const id = `${convo.phone}-${convo.updated_at}`;
    setSmsToasts(list => [...list, {
      id,
      phone: convo.phone,
      label: convo.owner || convo.business || convo.phone,
      body: convo.last_message,
    }]);
    setTimeout(() => dismissToast(id), AUTO_DISMISS_MS);
  });
  const openSmsToast = (t) => {
    dismissToast(t.id);
    navigateTo("sms", t.phone);
  };

  // Answering an inbound call jumps to the dedicated call screen.
  useEffect(() => {
    if (activeCall && active !== "call") {
      prevActiveRef.current = active;
      setActive("call");
    }
  }, [activeCall]);

  // Ending the call (from CallScreen's End Call, or the mini bar elsewhere)
  // always lands on the call screen so the disposition can still be logged —
  // it does NOT navigate away, since the call may have ended with nothing
  // dispositioned yet. Only actually logging a disposition (CallScreen's
  // onDone) returns to whichever tab was open before the call.
  const handleHangUp = () => {
    hangUp();
    prevActiveRef.current = active === "call" ? prevActiveRef.current : active;
    setActive("call");
  };

  const handleDone = () => {
    clearCallInfo();
    setActive(prevActiveRef.current);
  };

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
          <div style={{ display: "flex", alignItems: "center" }}>
            <LogoMark />
          </div>
          <div style={{
            fontFamily: "'Share Tech Mono', monospace",
            fontSize: 9, color: "#2a4a7a", letterSpacing: "0.14em", marginTop: 8,
          }}>
            CLIENT ACQ. PLATFORM
          </div>
        </div>

        {/* Nav */}
        <nav style={{ flex: 1, padding: "14px 12px", display: "flex", flexDirection: "column", gap: 3 }}>
          {NAV.map(({ id, label }) => {
            const isActive = active === id;
            return (
              <button key={id}
                onClick={() => setActive(id)}
                style={{
                  width: "100%", display: "flex", alignItems: "center", gap: 10,
                  padding: "10px 14px", borderRadius: 12,
                  border: "none", cursor: "pointer",
                  background: isActive
                    ? "linear-gradient(90deg, #2857a0 0%, #3a7bd5 100%)"
                    : "transparent",
                  boxShadow: isActive ? "0 4px 18px rgba(58,123,213,0.4)" : "none",
                  transition: "all 0.2s", textAlign: "left",
                }}
                onMouseEnter={e => {
                  if (!isActive) e.currentTarget.style.background = "rgba(58,123,213,0.08)";
                }}
                onMouseLeave={e => {
                  if (!isActive) e.currentTarget.style.background = "transparent";
                }}
              >
                <span style={{
                  color: isActive ? "#6ab0ff" : "#3a5a80",
                  display: "flex", flexShrink: 0,
                }}>
                  {NAV_ICONS[id]}
                </span>
                <span style={{
                  fontFamily: "'Space Grotesk', sans-serif",
                  fontSize: 13, fontWeight: isActive ? 600 : 400,
                  color: isActive ? "#ffffff" : "#6080a8",
                }}>
                  {label}
                </span>
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
        {active === "home"     && <DashboardPanel onNavigate={navigateTo} />}
        {active === "crm"      && <CRMPanel onNavigate={setActive} />}
        {active === "sms"      && <SMSPanel initialPhone={navContext} />}
        {active === "dialer"   && <DialerPanel />}
        {active === "agents"    && <AgentsPanel initialAgentId={navContext} />}
        {active === "analytics" && <AnalyticsPanel />}
        {active === "finances"  && <FinancesPanel />}
        {active === "todos"     && <TodoPanel />}
        {active === "website"   && <WebsitePanel />}
        {active === "sops"      && <SOPsPanel />}
        {active === "settings"  && <SettingsPanel />}
        {active === "call"      && <CallScreen callInfo={callInfo} live={!!activeCall} onHangUp={handleHangUp} onDone={handleDone} />}
      </main>

      <IncomingCallWidget
        incoming={incoming}
        activeCall={activeCall}
        callInfo={callInfo}
        onAnswer={answer}
        onDecline={decline}
        onHangUp={handleHangUp}
        onReturnToCall={() => setActive("call")}
        showMiniBar={active !== "call"}
      />

      <SmsToasts toasts={smsToasts} onOpen={openSmsToast} onDismiss={dismissToast} />
    </div>
  );
}
