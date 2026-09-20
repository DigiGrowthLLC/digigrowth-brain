import React, { useState, useEffect, useCallback } from "react";

// ── Cold-outreach email identity roster + warm-up sequence view ─────────────
// Same modal-chrome pattern as DmFollowUpQueueModal.jsx, but identity-shaped
// rows (ramp progress) instead of contact rows (next-touch-due). Identity
// CRUD is colocated here (an inline "+ Add Identity" form) rather than a
// separate settings page — see routers/email_identities.py for the backing
// endpoints and identity_warmup.py for what "warming"/"active"/"paused"
// status actually gate.

function fmt(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

const STATUS_COLOR = {
  warming: "#f0a028",
  active: "#14c882",
  paused: "#5a6f8f",
};

// ── Add identity sub-modal ────────────────────────────────────────────────

function AddIdentityModal({ onClose, onAdded }) {
  const [provider, setProvider] = useState("google");
  const [domain, setDomain] = useState("");
  const [mailboxEmail, setMailboxEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [refreshToken, setRefreshToken] = useState("");
  const [tenantId, setTenantId] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  async function save() {
    if (!domain.trim() || !mailboxEmail.trim()) {
      setErr("Domain and mailbox email are required.");
      return;
    }
    setSaving(true);
    setErr("");
    try {
      const res = await fetch("/api/email-identities", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider, domain: domain.trim(), mailbox_email: mailboxEmail.trim(),
          display_name: displayName.trim(), oauth_refresh_token: refreshToken.trim(),
          ms_tenant_id: tenantId.trim(),
        }),
      });
      if (res.ok) {
        onAdded();
        onClose();
      } else {
        const d = await res.json().catch(() => ({}));
        setErr(d.detail || "Failed to add identity.");
      }
    } catch {
      setErr("Failed to add identity.");
    }
    setSaving(false);
  }

  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 70, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ position: "absolute", inset: 0, background: "rgba(4,8,16,0.85)" }} onClick={onClose} />
      <div style={{ position: "relative", background: "#0a1020", border: "0.5px solid #1a2540", borderRadius: 8,
                    width: 480, maxWidth: "92vw", display: "flex", flexDirection: "column", padding: "24px 28px", gap: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 16, fontWeight: 700, color: "#f0f4ff" }}>Add Email Identity</div>
          <button onClick={onClose} style={{ background: "none", border: "none", color: "#3a5a80", cursor: "pointer", fontSize: 14 }}>✕</button>
        </div>

        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80" }}>
          Mint the refresh token out-of-band first (reauth_google.py for Google, reauth_microsoft.py for Microsoft), then paste it here.
        </div>

        <div style={{ display: "flex", gap: 8 }}>
          {["google", "microsoft"].map(p => (
            <button key={p} onClick={() => setProvider(p)}
              style={{
                flex: 1, padding: "8px 10px", borderRadius: 6,
                border: `1px solid ${provider === p ? "rgba(58,123,213,0.6)" : "rgba(58,123,213,0.2)"}`,
                background: provider === p ? "rgba(58,123,213,0.15)" : "transparent",
                color: provider === p ? "#3a7bd5" : "#5a6f8f",
                fontFamily: "'Share Tech Mono', monospace", fontSize: 10, letterSpacing: "0.06em", cursor: "pointer",
              }}>
              {p.toUpperCase()}
            </button>
          ))}
        </div>

        <input value={domain} onChange={e => setDomain(e.target.value)} placeholder="Domain (e.g. outreach1.digigrowthllc.com)" className="dg-input" />
        <input value={mailboxEmail} onChange={e => setMailboxEmail(e.target.value)} placeholder="Mailbox email" className="dg-input" />
        <input value={displayName} onChange={e => setDisplayName(e.target.value)} placeholder="Display name (optional)" className="dg-input" />
        <input value={refreshToken} onChange={e => setRefreshToken(e.target.value)} placeholder="OAuth refresh token" className="dg-input" />
        {provider === "microsoft" && (
          <input value={tenantId} onChange={e => setTenantId(e.target.value)} placeholder="Azure AD tenant id" className="dg-input" />
        )}

        {err && <div style={{ fontSize: 11, color: "#e05555" }}>{err}</div>}

        <button onClick={save} disabled={saving} className="btn btn-primary" style={{ alignSelf: "flex-end" }}>
          {saving ? "Adding…" : "+ Add Identity"}
        </button>
      </div>
    </div>
  );
}

// ── Main modal ─────────────────────────────────────────────────────────────

export default function IdentityWarmupModal({ onClose }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [err, setErr] = useState("");

  const fetchRows = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/email-identities/warmup-sequence");
      const data = await res.json();
      setRows(Array.isArray(data) ? data : []);
    } catch { setRows([]); }
    setLoading(false);
  }, []);

  useEffect(() => { fetchRows(); }, [fetchRows]);

  async function startWarmup(row) {
    setBusyId(row.id);
    setErr("");
    const res = await fetch(`/api/email-identities/${row.id}/start-warmup`, { method: "POST" });
    if (res.ok) fetchRows();
    else { const d = await res.json().catch(() => ({})); setErr(d.detail || "Failed to start warm-up."); }
    setBusyId(null);
  }

  async function setStatus(row, status) {
    setBusyId(row.id);
    setErr("");
    const path = status === "active" ? "activate" : "pause";
    const res = await fetch(`/api/email-identities/${row.id}/${path}`, { method: "POST" });
    if (res.ok) fetchRows();
    else { const d = await res.json().catch(() => ({})); setErr(d.detail || "Failed to update status."); }
    setBusyId(null);
  }

  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 60, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ position: "absolute", inset: 0, background: "rgba(4,8,16,0.85)" }} onClick={onClose} />
      <div style={{ position: "relative", background: "#0a1020", border: "0.5px solid #1a2540", borderRadius: 8,
                    width: "min(980px, 92vw)", maxHeight: "85vh", display: "flex", flexDirection: "column" }}>

        <div style={{ padding: "18px 24px", borderBottom: "0.5px solid #1a2540",
                      display: "flex", alignItems: "center", gap: 16 }}>
          <div>
            <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 16, fontWeight: 700, color: "#f0f4ff" }}>
              Email Identities — Warm-Up Status
            </div>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80",
                          letterSpacing: "0.18em", marginTop: 2 }}>
              {rows.length.toLocaleString()} IDENTITIES
            </div>
          </div>
          <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
            <button onClick={() => setShowAdd(true)} className="btn btn-primary" style={{ whiteSpace: "nowrap" }}>
              + Add Identity
            </button>
            <button onClick={onClose} style={{ background: "none", border: "none", color: "#3a5a80", cursor: "pointer", fontSize: 16 }}>✕</button>
          </div>
        </div>

        <div style={{ margin: "10px 24px 0", fontSize: 11, color: "#3a5a80", flexShrink: 0 }}>
          New identities start "warming" — cross-emailing each other with real threaded replies — and are never used for real leads until manually promoted to "active".
        </div>

        {err && (
          <div style={{ margin: "10px 24px 0", fontSize: 11, color: "#e05555", flexShrink: 0 }}>{err}</div>
        )}

        <div style={{ flex: 1, overflowY: "auto", padding: "14px 24px 20px" }}>
          {loading ? (
            <div style={{ padding: "30px 0", textAlign: "center", fontSize: 11, color: "#3a5a80" }}>Loading…</div>
          ) : rows.length === 0 ? (
            <div style={{ padding: "30px 0", textAlign: "center", fontFamily: "'Share Tech Mono', monospace",
                          fontSize: 11, color: "#3a5a80", letterSpacing: "0.18em" }}>
              NO EMAIL IDENTITIES YET — ADD ONE TO START WARMING IT UP
            </div>
          ) : (
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ borderBottom: "0.5px solid #1a2540" }}>
                  {["Identity", "Provider", "Status", "Day", "Sent Today", "Last Activity", ""].map(h => (
                    <th key={h} style={{
                      padding: "6px 10px", textAlign: "left",
                      fontFamily: "'Share Tech Mono', monospace", fontSize: 9, fontWeight: 600,
                      letterSpacing: "0.18em", color: "#2a4a7a", textTransform: "uppercase",
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map(r => (
                  <tr key={r.id} style={{ borderBottom: "0.5px solid #121e36" }}>
                    <td style={{ padding: "8px 10px", fontSize: 12, color: "#f0f4ff" }}>
                      {r.display_name || r.mailbox_email}
                      <div style={{ fontSize: 10, color: "#5a6f8f" }}>{r.mailbox_email}</div>
                    </td>
                    <td style={{ padding: "8px 10px", fontSize: 11, color: "#7a94b8" }}>{r.provider}</td>
                    <td style={{ padding: "8px 10px", fontSize: 11, color: STATUS_COLOR[r.identity_status] || "#7a94b8" }}>
                      {r.identity_status}{r.warmup_status ? ` (${r.warmup_status})` : ""}
                    </td>
                    <td style={{ padding: "8px 10px", fontSize: 11, color: "#7a94b8" }}>
                      {r.warmup_status ? `${r.current_day || 1} / ${r.total_days}` : "—"}
                    </td>
                    <td style={{ padding: "8px 10px", fontSize: 11, color: "#7a94b8" }}>
                      {r.warmup_status ? `${r.sent_today || 0} / ${r.day_target ?? "—"}` : "—"}
                    </td>
                    <td style={{ padding: "8px 10px", fontSize: 11, color: "#7a94b8" }}>{fmt(r.last_sent_at)}</td>
                    <td style={{ padding: "8px 10px", textAlign: "right", whiteSpace: "nowrap" }}>
                      {!r.warmup_status && (
                        <button onClick={() => startWarmup(r)} disabled={busyId === r.id}
                          className="btn btn-secondary" style={{ fontSize: 10, padding: "5px 10px", marginRight: 6 }}>
                          {busyId === r.id ? "…" : "Start Warm-Up"}
                        </button>
                      )}
                      {r.identity_status !== "active" ? (
                        <button onClick={() => setStatus(r, "active")} disabled={busyId === r.id}
                          className="btn btn-secondary" style={{ fontSize: 10, padding: "5px 10px", color: "#14c882" }}>
                          Activate
                        </button>
                      ) : (
                        <button onClick={() => setStatus(r, "paused")} disabled={busyId === r.id}
                          className="btn btn-secondary" style={{ fontSize: 10, padding: "5px 10px", color: "#e05555" }}>
                          Pause
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {showAdd && (
        <AddIdentityModal onClose={() => setShowAdd(false)} onAdded={fetchRows} />
      )}
    </div>
  );
}
