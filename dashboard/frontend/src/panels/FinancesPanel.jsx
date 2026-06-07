import React, { useState, useEffect, useCallback } from "react";
import { usePlaidLink } from "react-plaid-link";

// Must be a separate component — usePlaidLink only works correctly when
// mounted after the token is already available, not with token=""
function PlaidConnectButton({ token, onSuccess, onError, disabled }) {
  const { open, ready } = usePlaidLink({
    token,
    onSuccess,
    onExit: (err, metadata) => {
      if (err) {
        onError?.(`Plaid exit error: ${err.error_code} — ${err.error_message}`);
      } else if (metadata?.status !== "institution_selected") {
        // exited after partially completing — surface for debugging
        onError?.(`Exited at step: ${metadata?.status || "unknown"}`);
      }
    },
  });
  return (
    <button
      onClick={() => open()}
      disabled={!ready || disabled}
      className="btn btn-primary"
      style={{ padding: "12px 28px", fontSize: 13, fontWeight: 600, opacity: ready ? 1 : 0.5 }}
    >
      {disabled ? "Connecting…" : "Connect Novo"}
    </button>
  );
}
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer,
} from "recharts";

const API = (p) => `/api${p}`;

const CATEGORIES = [
  "Revenue", "Hosting & Infrastructure", "Communications", "AI Tools",
  "Advertising", "SaaS Tools", "Payment Processing", "Miscellaneous", "Uncategorized",
];

function money(v) {
  if (v == null) return "—";
  return `$${Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function timeAgo(iso) {
  if (!iso) return "never";
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 60000) return "just now";
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
  return `${Math.floor(diff / 86400000)}d ago`;
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: "rgba(10,18,48,0.95)", border: "1px solid rgba(58,123,213,0.2)",
      borderRadius: 10, padding: "8px 14px", fontSize: 12,
      fontFamily: "'Space Grotesk', sans-serif",
    }}>
      <div style={{ color: "#8aaad0", marginBottom: 4 }}>{label}</div>
      {payload.map(p => (
        <div key={p.dataKey} style={{ color: p.color, fontWeight: 600 }}>
          {p.name}: ${p.value?.toLocaleString()}
        </div>
      ))}
    </div>
  );
}

function PeriodToggle({ days, setDays }) {
  return (
    <div style={{
      display: "flex", background: "rgba(10,18,48,0.7)",
      border: "1px solid rgba(58,123,213,0.1)", borderRadius: 12, padding: 4, gap: 2,
    }}>
      {[[7,"7D"],[30,"30D"],[90,"90D"]].map(([d, label]) => (
        <button key={d} onClick={() => setDays(d)} style={{
          fontFamily: "'Space Grotesk', sans-serif",
          fontSize: 11, fontWeight: 500, padding: "5px 14px",
          borderRadius: 9, border: "none", cursor: "pointer", transition: "all 0.15s",
          background: days === d ? "linear-gradient(135deg, #2857a0 0%, #3a7bd5 100%)" : "transparent",
          color: days === d ? "#fff" : "#4a6080",
          boxShadow: days === d ? "0 2px 10px rgba(58,123,213,0.4)" : "none",
        }}>{label}</button>
      ))}
    </div>
  );
}

function SummaryCard({ label, value, color, sub }) {
  return (
    <div className="stat-card">
      <div className="stat-card-label">{label}</div>
      <div className="stat-card-value" style={{ color: color || "#f0f4ff" }}>{value ?? "—"}</div>
      {sub && <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80", marginTop: 2 }}>{sub}</div>}
    </div>
  );
}


export default function FinancesPanel() {
  const [days, setDays]             = useState(30);
  const [summary, setSummary]       = useState(null);
  const [categories, setCategories] = useState(null);
  const [txns, setTxns]             = useState(null);
  const [syncing, setSyncing]       = useState(false);
  const [txnType, setTxnType]       = useState("all");
  const [expandedTxn, setExpandedTxn] = useState(null);
  const [linkToken, setLinkToken]   = useState(null);
  const [connectError, setConnectError] = useState(null);
  const [connecting, setConnecting] = useState(false);
  const [isConnected, setIsConnected] = useState(false);

  const loadAll = useCallback(async (d = days) => {
    const [s, c, t] = await Promise.all([
      fetch(API(`/finances/summary?days=${d}`)).then(r => r.ok ? r.json() : null),
      fetch(API(`/finances/categories?days=${d}`)).then(r => r.ok ? r.json() : null),
      fetch(API(`/finances/transactions?days=${d}&type=all`)).then(r => r.ok ? r.json() : null),
    ]);
    setSummary(s);
    setCategories(c);
    setTxns(t);
    if (s?.connected) setIsConnected(true);
  }, [days]);

  const triggerSync = async () => {
    setSyncing(true);
    try {
      await fetch(API("/finances/plaid/sync"), { method: "POST" });
      await loadAll();
    } finally {
      setSyncing(false);
    }
  };

  // Fetch Plaid link token on mount
  useEffect(() => {
    fetch(API("/finances/plaid/link-token"), { method: "POST" })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.link_token) setLinkToken(d.link_token); })
      .catch(() => {});
    loadAll();
  }, []);

  useEffect(() => { loadAll(days); }, [days]);

  // Auto-sync on load when connected
  useEffect(() => {
    if (isConnected) triggerSync();
  }, [isConnected]);

  const handlePlaidSuccess = useCallback(async (publicToken, metadata) => {
    setConnecting(true);
    setConnectError("Plaid authorized — exchanging token with server…");
    try {
      const resp = await fetch(API("/finances/plaid/exchange"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          public_token: publicToken,
          institution_name: metadata?.institution?.name || "Novo",
        }),
      });
      if (!resp.ok) {
        const err = await resp.text();
        setConnectError(`Server error ${resp.status}: ${err}`);
        return;
      }
      setIsConnected(true);
      const data = await resp.json();
      if (data.sync_error) setConnectError(`Connected — sync note: ${data.sync_error}`);
      await loadAll();
    } catch (e) {
      setConnectError(`Network error: ${e.message}`);
    } finally {
      setConnecting(false);
    }
  }, [loadAll]);

  const updateTxn = async (id, patch) => {
    await fetch(API(`/finances/transactions/${id}`), {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    });
    setTxns(prev => prev ? {
      ...prev,
      transactions: prev.transactions.map(t => t.id === id ? { ...t, ...patch } : t),
    } : prev);
  };

  const filteredTxns = (txns?.transactions ?? []).filter(t => {
    if (txnType === "income")  return t.is_income;
    if (txnType === "expense") return !t.is_income;
    return true;
  });

  const marginColor = summary?.margin == null ? "#3a5a80"
    : summary.margin > 30 ? "#14c882"
    : summary.margin > 0  ? "#f0a028"
    : "#dc3c3c";

  const totalExpenses = categories?.expense_breakdown?.reduce((s, r) => s + r.total, 0) || 1;

  if (!summary && !linkToken) {
    return (
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52", letterSpacing: "0.15em" }}>
          LOADING...
        </div>
      </div>
    );
  }

  return (
    <div style={{ flex: 1, overflowY: "auto", padding: 24, display: "flex", flexDirection: "column", gap: 24 }}>

      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 22, fontWeight: 700, color: "#f0f4ff", letterSpacing: "-0.02em" }}>
            Finances
          </div>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80", letterSpacing: "0.18em", marginTop: 3 }}>
            {summary?.institution_name ? `${summary.institution_name.toUpperCase()} · BUSINESS ACCOUNT` : "NOVO · BUSINESS ACCOUNT"}
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {isConnected && (
            <button
              onClick={triggerSync}
              disabled={syncing}
              className="btn btn-secondary"
              style={{ fontSize: 11, display: "flex", alignItems: "center", gap: 6 }}
            >
              <span style={{ display: "inline-block", transform: syncing ? "rotate(360deg)" : "none", transition: syncing ? "transform 1s linear infinite" : "none" }}>↻</span>
              {syncing ? "SYNCING…" : "SYNC"}
            </button>
          )}
          <PeriodToggle days={days} setDays={setDays} />
        </div>
      </div>

      {/* Not connected */}
      {!isConnected && (
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div className="glass-card" style={{ padding: "40px 48px", textAlign: "center", maxWidth: 440 }}>
            <div style={{ marginBottom: 20 }}>
              <svg viewBox="0 0 48 48" fill="none" width={48} height={48} style={{ margin: "0 auto" }}>
                <rect x="4" y="10" width="40" height="28" rx="4" stroke="#3a7bd5" strokeWidth="2"/>
                <path d="M4 18h40" stroke="#3a7bd5" strokeWidth="2"/>
                <rect x="10" y="26" width="8" height="4" rx="1" fill="#3a7bd5" opacity="0.6"/>
                <rect x="22" y="26" width="5" height="4" rx="1" fill="#3a7bd5" opacity="0.3"/>
              </svg>
            </div>
            <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 18, fontWeight: 700, color: "#f0f4ff", marginBottom: 8 }}>
              Connect Your Novo Account
            </div>
            <div style={{ fontSize: 13, color: "#6080a8", lineHeight: 1.6, marginBottom: 24 }}>
              Link your Novo business bank account to automatically track income, expenses, and profit margin.
            </div>
            {linkToken ? (
              <PlaidConnectButton
                token={linkToken}
                onSuccess={handlePlaidSuccess}
                onError={setConnectError}
                disabled={connecting}
              />
            ) : (
              <button className="btn btn-primary" disabled style={{ padding: "12px 28px", fontSize: 13, opacity: 0.5 }}>
                Loading…
              </button>
            )}
            {connecting && (
              <div style={{ marginTop: 12, fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", letterSpacing: "0.1em" }}>
                CONNECTING & SYNCING…
              </div>
            )}
            {connectError && (
              <div style={{ marginTop: 12, padding: "10px 14px", borderRadius: 8, background: "rgba(220,60,60,0.08)", border: "1px solid rgba(220,60,60,0.2)", fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#dc3c3c", letterSpacing: "0.06em", textAlign: "left" }}>
                {connectError}
              </div>
            )}
            <div style={{ marginTop: 14, fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#1a3a60", letterSpacing: "0.1em" }}>
              POWERED BY PLAID · BANK-GRADE ENCRYPTION
            </div>
          </div>
        </div>
      )}

      {/* Connected dashboard */}
      {isConnected && (
        <>
          {/* Summary cards */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
            <SummaryCard label="Revenue"     value={money(summary.income)}   color="#14c882" />
            <SummaryCard label="Expenses"    value={money(summary.expenses)}  color="#f0a028" />
            <SummaryCard
              label="Net Profit"
              value={money(summary.net)}
              color={summary.net >= 0 ? "#14c882" : "#dc3c3c"}
            />
            <SummaryCard
              label="Profit Margin"
              value={summary.margin != null ? `${summary.margin}%` : "—"}
              color={marginColor}
              sub={summary.margin != null ? (summary.margin > 30 ? "HEALTHY" : summary.margin > 0 ? "SLIM" : "LOSS") : null}
            />
          </div>

          {/* Income vs Expenses trend */}
          <div className="glass-card" style={{ padding: "20px 22px" }}>
            <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 15, fontWeight: 600, color: "#d0dcf0", marginBottom: 4 }}>
              Income vs Expenses
            </div>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", letterSpacing: "0.1em", marginBottom: 16 }}>
              LAST {days} DAYS · DAILY
            </div>
            <ResponsiveContainer width="100%" height={160}>
              <AreaChart data={categories?.daily ?? []} margin={{ top: 5, right: 5, bottom: 0, left: -10 }}>
                <defs>
                  <linearGradient id="fIncome" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#14c882" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#14c882" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="fExpense" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#f0a028" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#f0a028" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(58,123,213,0.06)" />
                <XAxis dataKey="date" tick={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, fill: "#2a4a7a" }}
                  axisLine={false} tickLine={false} tickFormatter={v => v ? v.slice(5) : ""} />
                <YAxis tick={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, fill: "#2a4a7a" }}
                  axisLine={false} tickLine={false} />
                <Tooltip content={<ChartTooltip />} />
                <Area type="monotone" dataKey="income"   name="Income"   stroke="#14c882" strokeWidth={2} fill="url(#fIncome)" />
                <Area type="monotone" dataKey="expenses" name="Expenses" stroke="#f0a028" strokeWidth={2} fill="url(#fExpense)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Spending by category */}
          <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 16 }}>

            <div className="glass-card" style={{ padding: "18px 20px" }}>
              <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 15, fontWeight: 600, color: "#d0dcf0", marginBottom: 14 }}>
                Spending by Category
              </div>
              {!categories?.expense_breakdown?.length ? (
                <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52", letterSpacing: "0.1em" }}>NO EXPENSES YET</div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  {categories.expense_breakdown.map(c => (
                    <div key={c.category}>
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                        <span style={{ fontSize: 12, color: "#8aaad0" }}>{c.category}</span>
                        <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80" }}>
                          {money(c.total)} ({c.pct}%)
                        </span>
                      </div>
                      <div style={{ height: 2, background: "#111e36", borderRadius: 1 }}>
                        <div style={{ height: 2, borderRadius: 1, width: `${c.pct}%`, background: "#f0a028", opacity: 0.7 }} />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="glass-card" style={{ padding: "18px 20px" }}>
              <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 15, fontWeight: 600, color: "#d0dcf0", marginBottom: 14 }}>
                Top Expenses
              </div>
              {(categories?.expense_breakdown?.slice(0, 3) ?? []).map((c, i) => (
                <div key={c.category} style={{
                  padding: "10px 0",
                  borderBottom: i < 2 ? "0.5px solid #1a2540" : "none",
                }}>
                  <div style={{ fontSize: 11, color: "#6080a8", marginBottom: 3 }}>{c.category}</div>
                  <div style={{ fontSize: 20, fontWeight: 700, color: "#f0a028", letterSpacing: "-0.02em" }}>
                    {money(c.total)}
                  </div>
                </div>
              ))}
              {!categories?.expense_breakdown?.length && (
                <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52", letterSpacing: "0.1em" }}>NO DATA</div>
              )}
            </div>
          </div>

          {/* Transaction list */}
          <div className="glass-card" style={{ padding: "18px 20px" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
              <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 15, fontWeight: 600, color: "#d0dcf0" }}>
                Transactions
              </div>
              <div style={{ display: "flex", background: "rgba(10,18,48,0.5)", border: "1px solid rgba(58,123,213,0.1)", borderRadius: 8, padding: 3, gap: 2 }}>
                {[["all","ALL"],["income","INCOME"],["expense","EXPENSES"]].map(([v, label]) => (
                  <button key={v} onClick={() => setTxnType(v)} style={{
                    fontFamily: "'Share Tech Mono', monospace",
                    fontSize: 9, padding: "4px 12px", letterSpacing: "0.08em",
                    borderRadius: 6, border: "none", cursor: "pointer",
                    background: txnType === v ? "rgba(58,123,213,0.3)" : "transparent",
                    color: txnType === v ? "#6ab0ff" : "#2a4a7a",
                  }}>{label}</button>
                ))}
              </div>
            </div>

            {filteredTxns.length === 0 ? (
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52", letterSpacing: "0.1em" }}>
                NO TRANSACTIONS
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column" }}>
                {filteredTxns.map(t => (
                  <div key={t.id}>
                    <div
                      onClick={() => setExpandedTxn(expandedTxn === t.id ? null : t.id)}
                      style={{
                        display: "flex", alignItems: "center", justifyContent: "space-between",
                        padding: "9px 0", borderBottom: "0.5px solid #1a2540",
                        cursor: "pointer",
                      }}
                    >
                      <div style={{ display: "flex", flexDirection: "column", gap: 2, flex: 1, marginRight: 12 }}>
                        <span style={{ fontSize: 12, color: "#8aaad0", fontWeight: 500 }}>
                          {t.description || "—"}
                        </span>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a4a7a" }}>
                            {t.date}
                          </span>
                          <span style={{
                            fontFamily: "'Share Tech Mono', monospace", fontSize: 8,
                            padding: "2px 6px", borderRadius: 4,
                            background: "rgba(58,123,213,0.08)", color: "#3a7bd5",
                            letterSpacing: "0.06em",
                          }}>
                            {t.category}
                          </span>
                        </div>
                      </div>
                      <span style={{
                        fontFamily: "'Share Tech Mono', monospace", fontSize: 13, fontWeight: 700,
                        color: t.is_income ? "#14c882" : "#f0a028",
                        letterSpacing: "-0.01em",
                      }}>
                        {t.is_income ? "+" : "-"}{money(t.amount)}
                      </span>
                    </div>

                    {/* Inline edit row */}
                    {expandedTxn === t.id && (
                      <div style={{
                        padding: "10px 12px", background: "rgba(10,18,48,0.4)",
                        borderBottom: "0.5px solid #1a2540",
                        display: "flex", gap: 10, alignItems: "center",
                      }}>
                        <select
                          value={t.category}
                          onChange={e => updateTxn(t.id, { category: e.target.value })}
                          className="dg-input"
                          style={{ fontSize: 11, padding: "5px 8px", flex: "0 0 auto" }}
                        >
                          {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                        </select>
                        <input
                          className="dg-input"
                          style={{ flex: 1, fontSize: 11 }}
                          placeholder="Add note…"
                          defaultValue={t.notes || ""}
                          onBlur={e => updateTxn(t.id, { notes: e.target.value })}
                        />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Last synced footer */}
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#1a3a60", letterSpacing: "0.1em", textAlign: "center" }}>
            LAST SYNCED · {timeAgo(summary?.last_synced_at).toUpperCase()}
          </div>
        </>
      )}
    </div>
  );
}
