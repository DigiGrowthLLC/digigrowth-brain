import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import ClientPortal from "./ClientPortal.jsx";
import logoWordmark from "../assets/logo-wordmark.png";

// portal.digigrowthllc.com/<slug> (2026-11-21, backend: portal_links.py +
// routers/portal_auth.py). The browser keeps the portal token per slug after
// an email-code login; the OS's "Open portal" button hands it over in the
// #k= fragment so Dylan never sees the login.

const keyFor = (slug) => `dg_portal:${slug}`;
const readToken = (slug) => { try { return localStorage.getItem(keyFor(slug)); } catch { return null; } };
const saveToken = (slug, t) => { try { localStorage.setItem(keyFor(slug), t); } catch { /* private mode: session only */ } };
const dropToken = (slug) => { try { localStorage.removeItem(keyFor(slug)); } catch { /* ignore */ } };

const shell = {
  minHeight: "100vh", background: "#090f26", display: "flex", alignItems: "center", justifyContent: "center",
  padding: 16, fontFamily: "'Inter', 'Space Grotesk', sans-serif", color: "#e8eefc",
  backgroundImage: "radial-gradient(ellipse at 20% 0%, rgba(40,87,160,0.22) 0%, transparent 55%), radial-gradient(ellipse at 95% 10%, rgba(20,200,130,0.07) 0%, transparent 45%)",
};
const card = {
  width: "100%", maxWidth: 400, padding: "32px 28px", borderRadius: 18,
  background: "rgba(15,26,60,0.72)", border: "1px solid rgba(106,176,255,0.18)",
  boxShadow: "0 20px 60px rgba(0,0,0,0.45)", backdropFilter: "blur(14px)",
};
const input = {
  width: "100%", boxSizing: "border-box", padding: "12px 14px", borderRadius: 10, fontSize: 15,
  background: "rgba(9,15,38,0.8)", border: "1px solid rgba(106,176,255,0.25)", color: "#e8eefc", outline: "none",
};
const button = {
  width: "100%", padding: "12px 14px", borderRadius: 10, border: "none", fontSize: 15, fontWeight: 600,
  background: "linear-gradient(135deg, #3a7bd5, #6ab0ff)", color: "#fff", cursor: "pointer",
};
const fonts = <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet" />;

function Message({ children }) {
  return <div style={shell}>{fonts}<div style={{ ...card, textAlign: "center", color: "#8aaad0" }}>
    <img src={logoWordmark} alt="DigiGrowth" style={{ height: 34, marginBottom: 18 }} />
    <div style={{ fontSize: 15, lineHeight: 1.5 }}>{children}</div>
  </div></div>;
}

export function PortalHome() {
  return <Message>This is the DigiGrowth client portal. Use the link we sent you to open your clinic's portal.</Message>;
}

function Login({ slug, name, onToken }) {
  const [step, setStep] = useState("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const post = async (path, body) => {
    const r = await fetch(`/portal-auth/${slug}/${path}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.detail || "Something went wrong. Please try again.");
    return data;
  };
  const sendCode = async (e) => {
    e?.preventDefault();
    setBusy(true); setErr("");
    try { await post("request", { email }); setStep("code"); }
    catch (x) { setErr(x.message); }
    setBusy(false);
  };
  const verify = async (e) => {
    e.preventDefault();
    setBusy(true); setErr("");
    try { const { token } = await post("verify", { email, code }); onToken(token); }
    catch (x) { setErr(x.message); setBusy(false); }
  };

  return (
    <div style={shell}>{fonts}
      <div style={card}>
        <img src={logoWordmark} alt="DigiGrowth" style={{ height: 34, display: "block", marginBottom: 22 }} />
        <div style={{ fontSize: 13, color: "#6ab0ff", fontWeight: 600, marginBottom: 6 }}>Client portal</div>
        <h1 style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 24, fontWeight: 700, margin: "0 0 8px", letterSpacing: "-0.02em" }}>{name}</h1>
        {step === "email" ? (
          <form onSubmit={sendCode} style={{ display: "grid", gap: 12, marginTop: 18 }}>
            <div style={{ fontSize: 14, color: "#8aaad0" }}>Enter your email and we'll send you a login code.</div>
            <input style={input} type="email" required autoFocus autoComplete="email" placeholder="you@clinic.com"
              value={email} onChange={(e) => setEmail(e.target.value)} />
            <button style={{ ...button, opacity: busy ? 0.7 : 1 }} disabled={busy}>{busy ? "Sending…" : "Send code"}</button>
          </form>
        ) : (
          <form onSubmit={verify} style={{ display: "grid", gap: 12, marginTop: 18 }}>
            <div style={{ fontSize: 14, color: "#8aaad0", lineHeight: 1.5 }}>
              If {email} is on file, a 6-digit code is on its way. It can take a minute.
              If it's a new email for this portal, we've asked your DigiGrowth contact to approve it
              and you'll get an email as soon as they do.
            </div>
            <input style={{ ...input, fontSize: 22, letterSpacing: "0.3em", textAlign: "center" }} inputMode="numeric"
              autoComplete="one-time-code" autoFocus maxLength={6} placeholder="000000"
              value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} />
            <button style={{ ...button, opacity: busy || code.length < 6 ? 0.7 : 1 }} disabled={busy || code.length < 6}>{busy ? "Checking…" : "Log in"}</button>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
              <button type="button" onClick={() => { setStep("email"); setCode(""); setErr(""); }} style={{ background: "none", border: "none", color: "#8aaad0", cursor: "pointer", padding: 0 }}>Use a different email</button>
              <button type="button" onClick={sendCode} disabled={busy} style={{ background: "none", border: "none", color: "#6ab0ff", cursor: "pointer", padding: 0 }}>Resend code</button>
            </div>
          </form>
        )}
        {err && <div style={{ marginTop: 12, fontSize: 13.5, color: "#ff8a8a" }}>{err}</div>}
        <div style={{ marginTop: 22, fontSize: 12.5, color: "#5f7aa6", lineHeight: 1.5 }}>
          Not getting a code? Someone already on your team can add you under Team access in the portal.
        </div>
      </div>
    </div>
  );
}

export default function PortalEntry() {
  const slug = (useParams().slug || "").toLowerCase();
  const [token, setToken] = useState(null);
  const [name, setName] = useState("");
  const [state, setState] = useState("checking"); // checking | login | in | missing

  useEffect(() => {
    let t = readToken(slug);
    const m = window.location.hash.match(/[#&]k=([^&]+)/);
    if (m) {
      t = decodeURIComponent(m[1]);
      saveToken(slug, t);
      window.history.replaceState(null, "", window.location.pathname + window.location.search);
    }
    (async () => {
      if (t) {
        const r = await fetch(`/portal-api/${t}`).catch(() => null);
        if (r?.ok) { setToken(t); setState("in"); return; }
        dropToken(slug);
      }
      const info = await fetch(`/portal-auth/${slug}`).catch(() => null);
      if (info?.ok) { setName((await info.json()).name); setState("login"); }
      else setState("missing");
    })();
  }, [slug]);

  if (state === "checking") return <div style={shell} />;
  if (state === "missing") return <Message>We couldn't find that portal. Check the link we sent you.</Message>;
  if (state === "login") return <Login slug={slug} name={name} onToken={(t) => { saveToken(slug, t); setToken(t); setState("in"); }} />;
  return <ClientPortal token={token} />;
}

// Old links (<railway or os host>/portal/<token>): move over to the portal's
// own address, carrying the token so the person stays logged in. Falls back
// to rendering the portal in place if the new address can't be resolved.
export function LegacyPortalRedirect() {
  const { token } = useParams();
  const [fallback, setFallback] = useState(false);
  useEffect(() => {
    fetch(`/portal-auth/by-token/${token}`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(({ slug, portal_url }) => {
        if (!portal_url) throw new Error();
        if (new URL(portal_url).host === window.location.host) {
          saveToken(slug, token);
          window.location.replace(`/${slug}`);
        } else {
          window.location.replace(`${portal_url}#k=${encodeURIComponent(token)}`);
        }
      })
      .catch(() => setFallback(true));
  }, [token]);
  return fallback ? <ClientPortal token={token} /> : <div style={shell} />;
}
