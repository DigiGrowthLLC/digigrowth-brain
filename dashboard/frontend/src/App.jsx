import React, { useState } from "react";
import CRMPanel from "./panels/CRMPanel.jsx";
import SMSPanel from "./panels/SMSPanel.jsx";
import DialerPanel from "./panels/DialerPanel.jsx";

const NAV = [
  { id: "crm",       label: "CRM",       icon: "👥", ready: true  },
  { id: "dialer",    label: "Dialer",    icon: "📞", ready: true  },
  { id: "sms",       label: "SMS Inbox", icon: "💬", ready: true  },
  { id: "agents",    label: "Agents",    icon: "🤖", ready: false },
  { id: "analytics", label: "Analytics", icon: "📊", ready: false },
];

export default function App() {
  const [active, setActive] = useState("crm");

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-56 bg-gray-900 border-r border-gray-800 flex flex-col shrink-0">
        <div className="px-5 py-4 border-b border-gray-800">
          <div className="text-lg font-bold text-white tracking-tight">⚡ DigiGrowth</div>
          <div className="text-xs text-gray-500 mt-0.5">Operating System</div>
        </div>

        <nav className="flex-1 py-3 px-2">
          {NAV.map(({ id, label, icon, ready }) => (
            <button
              key={id}
              onClick={() => ready && setActive(id)}
              className={`
                w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm mb-1 transition-colors
                ${active === id
                  ? "bg-indigo-600 text-white font-medium"
                  : ready
                    ? "text-gray-400 hover:bg-gray-800 hover:text-white"
                    : "text-gray-600 cursor-not-allowed"
                }
              `}
            >
              <span className="text-base">{icon}</span>
              <span>{label}</span>
              {!ready && <span className="ml-auto text-xs text-gray-700">soon</span>}
            </button>
          ))}
        </nav>

        <div className="px-4 py-3 border-t border-gray-800 text-xs text-gray-600">
          DigiGrowth LLC
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-hidden flex flex-col bg-gray-950">
        {active === "crm"    && <CRMPanel />}
        {active === "sms"    && <SMSPanel />}
        {active === "dialer" && <DialerPanel />}
        {active !== "crm" && active !== "sms" && active !== "dialer" && (
          <div className="flex-1 flex items-center justify-center text-gray-600">
            Coming soon
          </div>
        )}
      </main>
    </div>
  );
}
