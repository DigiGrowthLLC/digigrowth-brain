import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import App from "./App.jsx";
import TeamSOPs from "./pages/TeamSOPs.jsx";
import ClientPortal from "./pages/ClientPortal.jsx";
import ErrorBoundary from "./ErrorBoundary.jsx";
import AuthGate from "./AuthGate.jsx";
import { installAuthFetch } from "./auth.js";
import "./index.css";

// Must run before any component fetches — see auth.js for why the app
// can't just rely on the browser's native Basic Auth popup.
installAuthFetch();

ReactDOM.createRoot(document.getElementById("root")).render(
  <ErrorBoundary>
    <BrowserRouter>
      <Routes>
        {/* Public routes — no dashboard password */}
        <Route path="/team" element={<TeamSOPs />} />
        <Route path="/portal/:token" element={<ClientPortal />} />
        <Route path="/*" element={<AuthGate><App /></AuthGate>} />
      </Routes>
    </BrowserRouter>
  </ErrorBoundary>
);
