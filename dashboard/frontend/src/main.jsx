import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import App from "./App.jsx";
import TeamSOPs from "./pages/TeamSOPs.jsx";
import PortalEntry, { PortalHome, LegacyPortalRedirect } from "./pages/PortalEntry.jsx";
import ErrorBoundary from "./ErrorBoundary.jsx";
import AuthGate from "./AuthGate.jsx";
import { installAuthFetch } from "./auth.js";
import "./index.css";

// Must run before any component fetches — see auth.js for why the app
// can't just rely on the browser's native Basic Auth popup.
installAuthFetch();

// The same build serves the OS (os.digigrowthllc.com, plus the Railway URL)
// and the client portals (portal.digigrowthllc.com/<slug>); the host decides.
const IS_PORTAL_HOST = window.location.hostname.startsWith("portal.");

ReactDOM.createRoot(document.getElementById("root")).render(
  <ErrorBoundary>
    <BrowserRouter>
      {IS_PORTAL_HOST ? (
        // portal.digigrowthllc.com: client portals only, never the OS.
        <Routes>
          <Route path="/" element={<PortalHome />} />
          <Route path="/portal/:token" element={<LegacyPortalRedirect />} />
          <Route path="/:slug" element={<PortalEntry />} />
          <Route path="*" element={<PortalHome />} />
        </Routes>
      ) : (
        <Routes>
          {/* Public routes — no dashboard password */}
          <Route path="/team" element={<TeamSOPs />} />
          <Route path="/portal/:token" element={<LegacyPortalRedirect />} />
          <Route path="/*" element={<AuthGate><App /></AuthGate>} />
        </Routes>
      )}
    </BrowserRouter>
  </ErrorBoundary>
);
