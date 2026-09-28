import React, { useState, useEffect, useCallback } from "react";

// ── Domain health for the cold-outreach sending domains ─────────────────────
// Opened from IdentityWarmupModal.jsx. Live SPF/DKIM/DMARC/MX checks come
// from Railway on each load; the DMARC report history is what the EA Daily
// Briefing parsed out of the DMARC emails in dylanrg@digigrowthllc.com and
// relayed in via GitHub (see backend/domain_health.py). "Sync Reports" pulls
// any summaries the briefing committed after the 6:45am ingest.

const GREEN = "#14c882";
const AMBER = "#f0a028";
const RED = "#e05555";

function pct(num, denom) {
  if (num == null || !denom) return null;
  return Math.round((num / denom) * 1000) / 10;
}

function rateColor(p) {
  if (p == null) return "#5a6f8f";
  if (p >= 98) return GREEN;
  if (p >= 90) return AMBER;
  return RED;
}

function fmtRange(start, end) {
  const opts = { month: "short", day: "numeric" };
  const s = new Date(start + "T00:00:00").toLocaleDateString(undefined, opts);
  if (!end || end === start) return s;
  return `${s} – ${new Date(end + "T00:00:00").toLocaleDateString(undefined, opts)}`;
}

function DnsBadge({ label, check }) {
  if (!check) return null;
  const color = check.ok ? GREEN : RED;
  return (
    <div title={check.detail} style={{
      flex: "1 1 120px", padding: "8px 10px", borderRadius: 6,
      border: `1px solid ${check.ok ? "rgba(20,200,130,0.3)" : "rgba(224,85,85,0.35)"}`,
      background: check.ok ? "rgba(20,200,130,0.06)" : "rgba(224,85,85,0.08)",
    }}>
      <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, letterSpacing: "0.18em", color: "#5a6f8f" }}>
        {label}
      </div>
      <div style={{ fontSize: 12, fontWeight: 600, color, marginTop: 2 }}>
        {check.ok ? "✓ Pass" : "✕ Fail"}{check.policy ? ` · p=${check.policy}` : ""}
      </div>
      <div style={{ fontSize: 10, color: "#5a6f8f", marginTop: 3, wordBreak: "break-all" }}>{check.detail}</div>
    </div>
  );
}

function ReportRow({ r }) {
  const [open, setOpen] = useState(false);
  const passRate = pct(r.dmarc_pass, r.total_messages);
  const sources = Array.isArray(r.sources) ? r.sources : [];
  return (
    <>
      <tr onClick={() => sources.length && setOpen(o => !o)}
        style={{ borderBottom: "0.5px solid #121e36", cursor: sources.length ? "pointer" : "default" }}>
        <td style={{ padding: "7px 10px", fontSize: 11, color: "#f0f4ff" }}>
          {fmtRange(r.period_start, r.period_end)}
          {r.inherited && <div style={{ fontSize: 9, color: "#5a6f8f" }}>root-domain report ({r.domain})</div>}
        </td>
        <td style={{ padding: "7px 10px", fontSize: 11, color: "#7a94b8" }}>{r.reporter}</td>
        <td style={{ padding: "7px 10px", fontSize: 11, color: "#7a94b8" }}>{r.total_messages ?? "—"}</td>
        <td style={{ padding: "7px 10px", fontSize: 11, fontWeight: 600, color: rateColor(passRate) }}>
          {passRate == null ? "—" : `${passRate}%`}
        </td>
        <td style={{ padding: "7px 10px", fontSize: 11, color: rateColor(pct(r.spf_pass, r.total_messages)) }}>
          {pct(r.spf_pass, r.total_messages) ?? "—"}{r.spf_pass != null && r.total_messages ? "%" : ""}
        </td>
        <td style={{ padding: "7px 10px", fontSize: 11, color: rateColor(pct(r.dkim_pass, r.total_messages)) }}>
          {pct(r.dkim_pass, r.total_messages) ?? "—"}{r.dkim_pass != null && r.total_messages ? "%" : ""}
        </td>
        <td style={{ padding: "7px 10px", fontSize: 10, color: "#5a6f8f" }}>
          {r.notes || ""}{sources.length ? ` ${open ? "▾" : "▸"} ${sources.length} source${sources.length === 1 ? "" : "s"}` : ""}
        </td>
      </tr>
      {open && sources.map((s, i) => (
        <tr key={i} style={{ background: "rgba(58,123,213,0.04)" }}>
          <td colSpan={2} style={{ padding: "4px 10px 4px 24px", fontSize: 10, color: "#7a94b8" }}>{s.source}</td>
          <td style={{ padding: "4px 10px", fontSize: 10, color: "#7a94b8" }}>{s.count ?? "—"}</td>
          <td style={{ padding: "4px 10px", fontSize: 10, color: s.dmarc === "pass" ? GREEN : s.dmarc ? RED : "#5a6f8f" }}>{s.dmarc || "—"}</td>
          <td style={{ padding: "4px 10px", fontSize: 10, color: s.spf === "pass" ? GREEN : s.spf ? RED : "#5a6f8f" }}>{s.spf || "—"}</td>
          <td style={{ padding: "4px 10px", fontSize: 10, color: s.dkim === "pass" ? GREEN : s.dkim ? RED : "#5a6f8f" }}>{s.dkim || "—"}</td>
          <td />
        </tr>
      ))}
    </>
  );
}

function DomainCard({ d }) {
  const reports = d.reports || [];
  const totals = reports.reduce((acc, r) => {
    if (r.total_messages && r.dmarc_pass != null) {
      acc.total += r.total_messages;
      acc.pass += r.dmarc_pass;
    }
    return acc;
  }, { total: 0, pass: 0 });
  const overall = pct(totals.pass, totals.total);

  return (
    <div className="glass-card-sm" style={{ padding: "14px 16px", display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
        <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 15, fontWeight: 700, color: "#f0f4ff" }}>{d.domain}</div>
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#5a6f8f" }}>
          {d.provider} · {d.mailboxes.map(m => `${m.email} (${m.status})`).join(", ")}
        </div>
        {overall != null && (
          <div style={{ marginLeft: "auto", fontSize: 11, color: rateColor(overall) }}>
            DMARC pass {overall}% across {totals.total.toLocaleString()} msgs
          </div>
        )}
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <DnsBadge label="SPF" check={d.dns?.spf} />
        <DnsBadge label="DKIM" check={d.dns?.dkim} />
        <DnsBadge label="DMARC" check={d.dns?.dmarc} />
        <DnsBadge label="MX" check={d.dns?.mx} />
      </div>

      {reports.length === 0 ? (
        <div style={{ fontSize: 11, color: "#3a5a80" }}>
          No DMARC reports yet. The daily briefing picks them up from dylanrg@digigrowthllc.com as they arrive.
        </div>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 560 }}>
            <thead>
              <tr style={{ borderBottom: "0.5px solid #1a2540" }}>
                {["Window", "Reporter", "Msgs", "DMARC", "SPF", "DKIM", ""].map(h => (
                  <th key={h} style={{
                    padding: "5px 10px", textAlign: "left",
                    fontFamily: "'Share Tech Mono', monospace", fontSize: 9, fontWeight: 600,
                    letterSpacing: "0.18em", color: "#2a4a7a", textTransform: "uppercase",
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {reports.map(r => <ReportRow key={r.id} r={r} />)}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default function DomainHealthModal({ onClose }) {
  const [domains, setDomains] = useState([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [msg, setMsg] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/email-identities/domain-health");
      const data = await res.json();
      setDomains(Array.isArray(data) ? data : []);
    } catch { setDomains([]); }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  async function sync() {
    setSyncing(true);
    setMsg("");
    try {
      const res = await fetch("/api/email-identities/domain-health/sync", { method: "POST" });
      const d = await res.json().catch(() => ({}));
      setMsg(d.result || "Sync failed.");
      await load();
    } catch {
      setMsg("Sync failed.");
    }
    setSyncing(false);
  }

  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 70, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ position: "absolute", inset: 0, background: "rgba(4,8,16,0.85)" }} onClick={onClose} />
      <div style={{ position: "relative", background: "#0a1020", border: "0.5px solid #1a2540", borderRadius: 8,
                    width: "min(980px, 92vw)", maxHeight: "85vh", display: "flex", flexDirection: "column" }}>
        <div style={{ padding: "18px 24px", borderBottom: "0.5px solid #1a2540", display: "flex", alignItems: "center", gap: 16 }}>
          <div>
            <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 16, fontWeight: 700, color: "#f0f4ff" }}>
              Domain Health
            </div>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80", letterSpacing: "0.18em", marginTop: 2 }}>
              LIVE DNS · DMARC REPORTS VIA DAILY BRIEFING
            </div>
          </div>
          <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
            <button onClick={sync} disabled={syncing} className="btn btn-secondary" style={{ whiteSpace: "nowrap" }}>
              {syncing ? "Syncing…" : "Sync Reports"}
            </button>
            <button onClick={onClose} style={{ background: "none", border: "none", color: "#3a5a80", cursor: "pointer", fontSize: 16 }}>✕</button>
          </div>
        </div>

        {msg && <div style={{ margin: "10px 24px 0", fontSize: 11, color: "#7a94b8" }}>{msg}</div>}

        <div style={{ flex: 1, overflowY: "auto", padding: "14px 24px 20px", display: "flex", flexDirection: "column", gap: 14 }}>
          {loading ? (
            <div style={{ padding: "30px 0", textAlign: "center", fontSize: 11, color: "#3a5a80" }}>Checking DNS…</div>
          ) : domains.length === 0 ? (
            <div style={{ padding: "30px 0", textAlign: "center", fontFamily: "'Share Tech Mono', monospace",
                          fontSize: 11, color: "#3a5a80", letterSpacing: "0.18em" }}>
              NO OUTREACH DOMAINS YET
            </div>
          ) : domains.map(d => <DomainCard key={d.domain} d={d} />)}
        </div>
      </div>
    </div>
  );
}
