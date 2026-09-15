import React, { useState, useEffect, useCallback } from "react";
import { getAuthHeader, setAuthPassword, clearAuth } from "./auth.js";
import logoWordmark from "./assets/logo-wordmark.png";

// Gates <App /> behind an in-app login screen instead of the browser's
// native Basic Auth popup — see auth.js for why. Not used on /team or
// /portal/:token, which are public routes with no dashboard password.
export default function AuthGate({ children }) {
  const [status, setStatus] = useState("checking"); // checking | authed | login
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const verify = useCallback(async () => {
    if (!getAuthHeader()) { setStatus("login"); return; }
    try {
      const res = await fetch("/api/dashboard/summary");
      setStatus(res.ok ? "authed" : "login");
    } catch {
      setStatus("login");
    }
  }, []);

  useEffect(() => { verify(); }, [verify]);

  useEffect(() => {
    const onInvalid = () => setStatus("login");
    window.addEventListener("dg-auth-invalid", onInvalid);
    return () => window.removeEventListener("dg-auth-invalid", onInvalid);
  }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    setAuthPassword(password);
    try {
      const res = await fetch("/api/dashboard/summary");
      if (res.ok) {
        setStatus("authed");
      } else {
        clearAuth();
        setError("Incorrect password.");
      }
    } catch {
      clearAuth();
      setError("Couldn't reach the server — check your connection.");
    }
    setSubmitting(false);
  }

  if (status === "checking") {
    return (
      <div style={{
        height: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
        background: "#070c1e",
      }}>
        <div style={{
          fontFamily: "'Share Tech Mono', monospace", fontSize: 11,
          letterSpacing: "0.18em", color: "#3a5a80",
        }}>
          LOADING…
        </div>
      </div>
    );
  }

  if (status === "login") {
    return (
      <div style={{
        minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
        padding: 24, background: "#070c1e",
      }}>
        <form
          onSubmit={handleSubmit}
          className="glass-card"
          style={{
            width: "100%", maxWidth: 360, padding: "32px 28px",
            display: "flex", flexDirection: "column", gap: 16,
          }}
        >
          <div style={{ display: "flex", justifyContent: "center", marginBottom: 4 }}>
            <img src={logoWordmark} alt="DigiGrowth" style={{ height: 44 }} />
          </div>
          <div style={{
            fontFamily: "'Share Tech Mono', monospace", fontSize: 10, letterSpacing: "0.18em",
            color: "#3a5a80", textAlign: "center", textTransform: "uppercase",
          }}>
            Sign in to continue
          </div>
          <input
            type="password"
            autoFocus
            autoComplete="current-password"
            className="dg-input"
            placeholder="Dashboard password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            style={{ fontSize: 16 }}
          />
          {error && <div style={{ fontSize: 12, color: "#e05555" }}>{error}</div>}
          <button
            type="submit"
            disabled={submitting || !password}
            className="btn btn-primary"
            style={{ width: "100%" }}
          >
            {submitting ? "Checking…" : "Log In"}
          </button>
        </form>
      </div>
    );
  }

  return children;
}
