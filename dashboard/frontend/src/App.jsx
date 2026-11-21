import React, { useState, useEffect, useRef } from "react";
import DashboardPanel from "./panels/DashboardPanel.jsx";
import CRMPanel       from "./panels/CRMPanel.jsx";
import InboxPanel     from "./panels/InboxPanel.jsx";
import DialerPanel    from "./panels/DialerPanel.jsx";
import AppointmentsPanel from "./panels/AppointmentsPanel.jsx";
import AgentsPanel    from "./panels/AgentsPanel.jsx";
import AnalyticsPanel from "./panels/AnalyticsPanel.jsx";
import FinancesPanel  from "./panels/FinancesPanel.jsx";
import SOPsPanel      from "./panels/SOPsPanel.jsx";
import TodoPanel      from "./panels/TodoPanel.jsx";
import WebsitePanel  from "./panels/WebsitePanel.jsx";
import ClientsPanel  from "./panels/ClientsPanel.jsx";
import BookingPanel  from "./panels/BookingPanel.jsx";
import IncomingCallWidget from "./IncomingCallWidget.jsx";
import { ContactCardHost } from "./ContactLink.jsx";
import CallScreen     from "./CallScreen.jsx";
import useIncomingCall from "./useIncomingCall.js";
import useSmsNotifications from "./useSmsNotifications.js";
import SmsToasts, { AUTO_DISMISS_MS } from "./SmsToasts.jsx";
import logoWordmark from "./assets/logo-wordmark.png";

// Grouped sidebar (2026-11-17 refresh): same panels and ids, organized by
// what Dylan is doing — finding clients, serving them, running the business.
const NAV_GROUPS = [
  { label: "Overview", items: [
    { id: "home",      label: "Dashboard" },
    { id: "todos",     label: "To-Do" },
  ] },
  { label: "Sales", items: [
    { id: "crm",       label: "CRM" },
    { id: "dialer",    label: "Dialer" },
    { id: "inbox",     label: "Inbox" },
    { id: "appointments", label: "Appointments" },
  ] },
  { label: "Clients", items: [
    { id: "clients",   label: "Clients" },
    { id: "booking",   label: "Booking Links" },
  ] },
  { label: "Business", items: [
    { id: "analytics", label: "Analytics" },
    { id: "finances",  label: "Finances" },
    { id: "website",   label: "Website" },
    { id: "sops",      label: "Resources" },
    { id: "agents",    label: "AI Agents" },
  ] },
];
const NAV = NAV_GROUPS.flatMap((g) => g.items);

// Sidebar look mirrors the client portal's (pages/ClientPortal.jsx PORTAL_CSS):
// gradient column, glowing multi-color edge, one accent per section (dot,
// active bar, active icon) and a gradient active pill. Classes are os-* so
// they never collide with the portal's pt-* ones.
const GROUP_ACCENTS = { Overview: "#6ab0ff", Sales: "#14c882", Clients: "#8b6cf0", Business: "#f0a028" };

const OS_NAV_CSS = `
  .os-side { background: linear-gradient(180deg, rgba(10,18,48,0.94) 0%, rgba(7,12,32,0.97) 100%); }
  .os-side::after { content: ""; position: absolute; top: 0; bottom: 0; right: 0; width: 1px; pointer-events: none;
    background: linear-gradient(180deg, rgba(106,176,255,0), rgba(106,176,255,0.55) 25%, rgba(20,200,130,0.45) 60%, rgba(139,108,240,0.35) 85%, rgba(139,108,240,0)); }
  .os-nav-btn { position: relative; display: flex; align-items: center; gap: 11px; width: 100%; padding: 9px 12px;
    box-sizing: border-box; border-radius: 10px; border: 1px solid transparent; text-decoration: none; color: #7f9cc4;
    font-family: 'Space Grotesk', sans-serif; font-size: 13.5px; font-weight: 500; transition: background 0.15s, color 0.15s; }
  .os-nav-btn:hover { background: rgba(58,123,213,0.08); color: #d0e8ff; }
  .os-nav-btn.on { color: #f0f4ff; border-color: rgba(58,123,213,0.3);
    background: linear-gradient(135deg, rgba(40,87,160,0.45), rgba(58,123,213,0.18));
    box-shadow: 0 6px 18px -8px rgba(58,123,213,0.7); }
  .os-nav-btn.on::before { content: ""; position: absolute; left: -14px; top: 8px; bottom: 8px; width: 3px;
    border-radius: 0 3px 3px 0; background: var(--os-accent, #6ab0ff); box-shadow: 0 0 10px var(--os-accent, #6ab0ff); }
  .os-nav-btn.on .os-nav-icon { color: var(--os-accent, #6ab0ff); }
  .os-group { display: flex; align-items: center; gap: 7px; font-family: 'Space Grotesk', sans-serif; font-size: 10.5px;
    font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase; color: #4f6a92; padding: 0 12px; margin-bottom: 6px; }
  .os-group::before { content: ""; width: 6px; height: 6px; border-radius: 50%; background: var(--os-accent, #6ab0ff);
    box-shadow: 0 0 6px var(--os-accent, #6ab0ff); }
`;

const NAV_ICONS = {
  home: (
    <svg viewBox="0 0 16 16" fill="none" width={15} height={15}>
      <rect x="1" y="1" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.4"/>
      <rect x="9" y="1" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.4"/>
      <rect x="1" y="9" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.4"/>
      <rect x="9" y="9" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.4"/>
    </svg>
  ),
  booking: (
    <svg viewBox="0 0 16 16" fill="none" width={15} height={15}>
      <rect x="1.5" y="2.5" width="13" height="12" rx="1.5" stroke="currentColor" strokeWidth="1.4"/>
      <path d="M1.5 6h13M5 1v3M11 1v3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
      <path d="M5.5 10l1.75 1.75L10.5 8.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
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
  appointments: (
    <svg viewBox="0 0 16 16" fill="none" width={15} height={15}>
      <rect x="2" y="3" width="12" height="11" rx="1.5" stroke="currentColor" strokeWidth="1.4"/>
      <path d="M2 6.5h12M5 1.5v3M11 1.5v3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
      <path d="M5.5 9.5l1.5 1.5 3-3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  inbox: (
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
  clients: (
    <svg viewBox="0 0 16 16" fill="none" width={15} height={15}>
      <rect x="2" y="2" width="12" height="12" rx="2" stroke="currentColor" strokeWidth="1.4"/>
      <circle cx="6.5" cy="7" r="1.6" stroke="currentColor" strokeWidth="1.3"/>
      <path d="M4 11.5c0-1.38 1.12-2.5 2.5-2.5S9 10.12 9 11.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
      <path d="M10.5 6h2M10.5 8.5h2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
    </svg>
  ),
  website: (
    <svg viewBox="0 0 16 16" fill="none" width={15} height={15}>
      <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.4"/>
      <path d="M2 8h12M8 2c-1.5 2-2.5 3.8-2.5 6s1 4 2.5 6M8 2c1.5 2 2.5 3.8 2.5 6s-1 4-2.5 6" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
    </svg>
  ),
};

const LogoMark = () => (
  <img src={logoWordmark} alt="DigiGrowth" style={{ height: 40, flexShrink: 0, display: "block" }} />
);

const VALID_PANELS = new Set(NAV.map(n => n.id));

// Each tab has its own address, os.digigrowthllc.com/<path> (2026-11-21).
// Old ?panel=<id> links (to-do notes, backend-generated links) still work:
// they're rewritten to the path form on load.
const PANEL_PATHS = { home: "dashboard", todos: "todo", booking: "booking-links", sops: "resources" };
export const panelPath = (id) => "/" + (PANEL_PATHS[id] || id);
const PATH_PANELS = Object.fromEntries(NAV.map(n => [(PANEL_PATHS[n.id] || n.id), n.id]));

function panelFromLocation() {
  const p = new URLSearchParams(window.location.search).get("panel");
  if (VALID_PANELS.has(p)) return p;
  const seg = window.location.pathname.split("/").filter(Boolean)[0] || "";
  return PATH_PANELS[seg] || "home";
}

// Rewrite a legacy ?panel= URL (or the bare "/") to the tab's path, in place.
function normalizeLocation() {
  const url = new URL(window.location.href);
  const panel = panelFromLocation();
  url.searchParams.delete("panel");
  url.pathname = panelPath(panel);
  if (url.href !== window.location.href) window.history.replaceState({ panel }, "", url);
}

// Deep link into a specific Inbox thread, e.g. the "Open in Inbox" links the
// SMS setter puts on prospect to-dos: ?panel=inbox&contact=<id> (or &phone=).
function navContextFromLocation() {
  const params = new URLSearchParams(window.location.search);
  if (panelFromLocation() !== "inbox") return null;
  const contactId = params.get("contact");
  const phone = params.get("phone");
  if (contactId) return { contactId };
  if (phone) return { phone };
  return null;
}

export default function App() {
  const [active, setActive] = useState(panelFromLocation);
  const [navContext, setNavContext] = useState(navContextFromLocation);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const prevActiveRef = useRef("home");

  const navigateTo = (panel, ctx = null) => {
    setNavContext(ctx);
    setActive(panel);
    if (VALID_PANELS.has(panel)) {
      const url = new URL(window.location.href);
      url.pathname = panelPath(panel);
      url.searchParams.delete("panel");
      url.searchParams.delete("contact");
      url.searchParams.delete("phone");
      // Clients deep link: ?client=<id> opens that client's page.
      if (panel === "clients" && ctx?.clientId) url.searchParams.set("client", ctx.clientId);
      else url.searchParams.delete("client");
      window.history.pushState({ panel }, "", url);
    }
  };

  useEffect(() => { normalizeLocation(); }, []);

  // Back/forward browser navigation between panels
  useEffect(() => {
    const onPopState = () => {
      setNavContext(navContextFromLocation());
      setActive(panelFromLocation());
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  // Close the mobile drawer any time navigation happens — otherwise it'd
  // stay open over the newly-selected panel.
  useEffect(() => { setMobileNavOpen(false); }, [active]);

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
    navigateTo("inbox", { channel: "sms", phone: t.phone });
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

      {/* Mobile top bar — hidden at md+, where the sidebar is always visible */}
      <div className="flex md:hidden" style={{
        position: "fixed", top: 0, left: 0, right: 0, zIndex: 40, height: 56,
        alignItems: "center", justifyContent: "space-between", padding: "0 14px",
        background: "rgba(9,15,38,0.98)", borderBottom: "1px solid rgba(58,123,213,0.1)",
        backdropFilter: "blur(20px)",
      }}>
        <button
          onClick={() => setMobileNavOpen(true)}
          aria-label="Open menu"
          style={{ background: "none", border: "none", color: "#c4d0e8", padding: 6, display: "flex" }}
        >
          <svg viewBox="0 0 20 20" width={22} height={22} fill="none">
            <path d="M3 6h14M3 10h14M3 14h14" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/>
          </svg>
        </button>
        <img src={logoWordmark} alt="DigiGrowth" style={{ height: 30 }} />
        <div style={{ width: 34 }} />
      </div>

      {/* Mobile drawer backdrop */}
      {mobileNavOpen && (
        <div
          className="md:hidden"
          onClick={() => setMobileNavOpen(false)}
          style={{ position: "fixed", inset: 0, background: "rgba(4,8,16,0.7)", zIndex: 49 }}
        />
      )}

      {/* Sidebar — fixed slide-in drawer on mobile, static column at md+ */}
      <aside
        className={
          "fixed md:relative top-0 left-0 bottom-0 md:top-auto md:left-auto md:bottom-auto " +
          "z-50 md:z-auto transition-transform duration-200 md:translate-x-0 " +
          (mobileNavOpen ? "translate-x-0" : "-translate-x-full") +
          " os-side"
        }
        style={{
          width: 244,
          display: "flex", flexDirection: "column", flexShrink: 0,
          backdropFilter: "blur(20px)",
        }}>
        <style>{OS_NAV_CSS}</style>

        {/* Brand */}
        <div style={{ padding: "22px 14px 4px" }}>
          <div style={{ display: "flex", alignItems: "center", padding: "0 12px" }}>
            <LogoMark />
          </div>
        </div>

        {/* Nav */}
        <nav style={{ flex: 1, padding: "16px 14px", display: "flex", flexDirection: "column", gap: 16, overflowY: "auto" }}>
          {NAV_GROUPS.map((group, gi) => (
            <div key={gi} style={{ "--os-accent": GROUP_ACCENTS[group.label] }}>
              {group.label && <div className="os-group">{group.label}</div>}
              <div style={{ display: "grid", gap: 2 }}>
              {group.items.map(({ id, label }) => {
                const isActive = active === id;
                return (
                  <a key={id}
                    href={panelPath(id)}
                    onClick={e => {
                      // Plain left-click stays in this SPA tab; ctrl/cmd/middle
                      // click and "Open link in new tab" fall through to the real href.
                      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
                      e.preventDefault();
                      navigateTo(id);
                    }}
                    aria-current={isActive ? "page" : undefined}
                    className={`os-nav-btn${isActive ? " on" : ""}`}
                  >
                    <span className="os-nav-icon" style={{ display: "flex", flexShrink: 0 }}>
                      {NAV_ICONS[id]}
                    </span>
                    {label}
                  </a>
                );
              })}
              </div>
            </div>
          ))}
        </nav>

        <div style={{ padding: "12px 26px 18px", borderTop: "1px solid rgba(58,123,213,0.14)", fontSize: 12, color: "#4f6a92", fontFamily: "'Space Grotesk', sans-serif" }}>
          DigiGrowth LLC
        </div>
      </aside>

      {/* Main content */}
      <main className="pt-14 md:pt-0" style={{
        flex: 1, minWidth: 0, overflow: "hidden", display: "flex", flexDirection: "column",
        background: "transparent",
      }}>
        {active === "home"     && <DashboardPanel onNavigate={navigateTo} />}
        {active === "crm"      && <CRMPanel onNavigate={navigateTo} />}
        {active === "inbox"    && <InboxPanel initialTarget={navContext} />}
        {active === "dialer"   && <DialerPanel />}
        {active === "appointments" && <AppointmentsPanel />}
        {active === "clients"   && <ClientsPanel key={navContext?.clientId || "list"} />}
        {active === "booking"   && <BookingPanel />}
        {active === "agents"    && <AgentsPanel initialAgentId={navContext} />}
        {active === "analytics" && <AnalyticsPanel />}
        {active === "finances"  && <FinancesPanel />}
        {active === "todos"     && <TodoPanel />}
        {active === "website"   && <WebsitePanel />}
        {active === "sops"      && <SOPsPanel />}
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
      <ContactCardHost />
    </div>
  );
}
