import React, { useState, useEffect, useCallback } from "react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer,
} from "recharts";
import { API } from "../api.js";
import PeriodToggle from "../components/PeriodToggle.jsx";

const CATEGORIES = [
  "Revenue",
  "Advertising & Marketing",
  "Technology",
  "Team & Labor",
  "Operations",
  "Transfers",
  "Miscellaneous",
  "Uncategorized",
];

const EXPENSE_CATEGORIES = CATEGORIES.filter(c => c !== "Revenue");

function money(v) {
  if (v == null) return "—";
  return `$${Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
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

const FINANCES_PERIOD_OPTIONS = [[7,"7D"],[30,"30D"],[90,"90D"],[365,"1Y"]];

function SummaryCard({ label, value, color, sub }) {
  return (
    <div className="stat-card">
      <div className="stat-card-label">{label}</div>
      <div className="stat-card-value" style={{ color: color || "#f0f4ff" }}>{value ?? "—"}</div>
      {sub && <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80", marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

const FREQ_LABELS = { weekly: "Weekly", monthly: "Monthly", yearly: "Yearly" };

function AddTransactionModal({ onClose, onSaved, onRecurringSaved }) {
  const today = new Date().toISOString().slice(0, 10);
  const [form, setForm] = useState({
    is_income:  false,
    recurring:  false,
    frequency:  "monthly",
    description: "",
    amount:      "",
    date:        today,
    category:    "Uncategorized",
    notes:       "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError]   = useState(null);

  const set = (k, v) => setForm(prev => ({ ...prev, [k]: v }));

  const handleSave = async () => {
    if (!form.description.trim()) { setError("Description is required."); return; }
    const amt = parseFloat(form.amount);
    if (!form.amount || isNaN(amt) || amt <= 0) { setError("Enter a valid amount greater than 0."); return; }
    setSaving(true);
    setError(null);
    try {
      if (form.recurring) {
        const resp = await fetch(API("/finances/recurring"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            is_income:   form.is_income,
            description: form.description.trim(),
            amount:      amt,
            start_date:  form.date,
            frequency:   form.frequency,
            category:    form.is_income ? "Revenue" : form.category,
            notes:       form.notes.trim() || null,
          }),
        });
        if (!resp.ok) { setError(await resp.text()); return; }
        onRecurringSaved();
      } else {
        const resp = await fetch(API("/finances/transactions"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            is_income:   form.is_income,
            description: form.description.trim(),
            amount:      amt,
            date:        form.date,
            category:    form.is_income ? "Revenue" : form.category,
            notes:       form.notes.trim() || null,
          }),
        });
        if (!resp.ok) { setError(await resp.text()); return; }
        onSaved(await resp.json());
      }
      onClose();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.65)",
        backdropFilter: "blur(6px)", zIndex: 1000,
        display: "flex", alignItems: "center", justifyContent: "center",
      }}
      onClick={onClose}
    >
      <div className="glass-card" style={{ width: 440, padding: "28px 32px" }} onClick={e => e.stopPropagation()}>
        <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 17, fontWeight: 700, color: "#f0f4ff", marginBottom: 22 }}>
          Add Transaction
        </div>

        {/* Revenue / Expense toggle */}
        <div style={{ display: "flex", marginBottom: 12, background: "rgba(10,18,48,0.7)", borderRadius: 10, padding: 4, gap: 4 }}>
          {[[false, "Expense"], [true, "Revenue"]].map(([val, label]) => (
            <button key={label} onClick={() => set("is_income", val)} style={{
              flex: 1, fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, fontWeight: 600,
              padding: "9px 0", borderRadius: 8, border: "none", cursor: "pointer",
              background: form.is_income === val
                ? val ? "linear-gradient(135deg, #0d7a4e, #14c882)" : "linear-gradient(135deg, #7a3a00, #f0a028)"
                : "transparent",
              color: form.is_income === val ? "#fff" : "#4a6080",
              transition: "all 0.15s",
            }}>{label}</button>
          ))}
        </div>

        {/* One-time / Recurring toggle */}
        <div style={{ display: "flex", marginBottom: 20, background: "rgba(10,18,48,0.5)", borderRadius: 10, padding: 4, gap: 4 }}>
          {[[false, "One-time"], [true, "Recurring"]].map(([val, label]) => (
            <button key={label} onClick={() => set("recurring", val)} style={{
              flex: 1, fontFamily: "'Space Grotesk', sans-serif", fontSize: 11, fontWeight: 600,
              padding: "7px 0", borderRadius: 8, border: "none", cursor: "pointer",
              background: form.recurring === val ? "rgba(58,123,213,0.35)" : "transparent",
              color: form.recurring === val ? "#6ab0ff" : "#4a6080",
              transition: "all 0.15s",
            }}>{label}</button>
          ))}
        </div>

        {/* Description */}
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", letterSpacing: "0.12em", marginBottom: 5 }}>DESCRIPTION</div>
          <input
            className="dg-input" type="text"
            style={{ width: "100%", fontSize: 13, boxSizing: "border-box" }}
            placeholder={form.is_income ? "e.g. Client retainer, invoice…" : "e.g. AWS, Anthropic API…"}
            value={form.description}
            onChange={e => set("description", e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleSave()}
          />
        </div>

        {/* Amount + Date/Start date */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 14 }}>
          <div>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", letterSpacing: "0.12em", marginBottom: 5 }}>AMOUNT ($)</div>
            <input
              className="dg-input" type="number" min="0" step="0.01"
              style={{ width: "100%", fontSize: 13, boxSizing: "border-box" }}
              placeholder="0.00"
              value={form.amount}
              onChange={e => set("amount", e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleSave()}
            />
          </div>
          <div>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", letterSpacing: "0.12em", marginBottom: 5 }}>
              {form.recurring ? "FIRST OCCURRENCE" : "DATE"}
            </div>
            <input
              className="dg-input" type="date"
              style={{ width: "100%", fontSize: 13, boxSizing: "border-box" }}
              value={form.date}
              onChange={e => set("date", e.target.value)}
            />
          </div>
        </div>

        {/* Frequency — only for recurring */}
        {form.recurring && (
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", letterSpacing: "0.12em", marginBottom: 5 }}>FREQUENCY</div>
            <div style={{ display: "flex", background: "rgba(10,18,48,0.7)", borderRadius: 10, padding: 4, gap: 4 }}>
              {["weekly", "monthly", "yearly"].map(f => (
                <button key={f} onClick={() => set("frequency", f)} style={{
                  flex: 1, fontFamily: "'Space Grotesk', sans-serif", fontSize: 11, fontWeight: 600,
                  padding: "7px 0", borderRadius: 8, border: "none", cursor: "pointer",
                  background: form.frequency === f ? "rgba(58,123,213,0.35)" : "transparent",
                  color: form.frequency === f ? "#6ab0ff" : "#4a6080",
                  transition: "all 0.15s",
                }}>{FREQ_LABELS[f]}</button>
              ))}
            </div>
          </div>
        )}

        {/* Category — only for expenses */}
        {!form.is_income && (
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", letterSpacing: "0.12em", marginBottom: 5 }}>CATEGORY</div>
            <select
              className="dg-input"
              style={{ width: "100%", fontSize: 13 }}
              value={form.category}
              onChange={e => set("category", e.target.value)}
            >
              {EXPENSE_CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
        )}

        {/* Notes */}
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", letterSpacing: "0.12em", marginBottom: 5 }}>NOTES (OPTIONAL)</div>
          <input
            className="dg-input" type="text"
            style={{ width: "100%", fontSize: 13, boxSizing: "border-box" }}
            placeholder="Optional note…"
            value={form.notes}
            onChange={e => set("notes", e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleSave()}
          />
        </div>

        {error && (
          <div style={{
            marginBottom: 14, padding: "8px 12px", borderRadius: 8,
            background: "rgba(220,60,60,0.08)", border: "1px solid rgba(220,60,60,0.2)",
            fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#dc3c3c", letterSpacing: "0.04em",
          }}>
            {error}
          </div>
        )}

        <div style={{ display: "flex", gap: 10 }}>
          <button onClick={onClose} className="btn btn-secondary" style={{ flex: 1, fontSize: 12 }}>Cancel</button>
          <button onClick={handleSave} disabled={saving} className="btn btn-primary" style={{ flex: 1, fontSize: 12 }}>
            {saving ? "Saving…" : form.recurring
              ? `Add Recurring ${form.is_income ? "Revenue" : "Expense"}`
              : `Add ${form.is_income ? "Revenue" : "Expense"}`}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function FinancesPanel() {
  const [days, setDays]             = useState(30);
  const [summary, setSummary]       = useState(null);
  const [categories, setCategories] = useState(null);
  const [txns, setTxns]             = useState(null);
  const [recurring, setRecurring]   = useState([]);
  const [txnType, setTxnType]       = useState("all");
  const [selectedCategory, setSelectedCategory] = useState(null);
  const [expandedTxn, setExpandedTxn]   = useState(null);
  const [showAddForm, setShowAddForm]   = useState(false);
  const [deletingId, setDeletingId]     = useState(null);
  const [deletingRuleId, setDeletingRuleId] = useState(null);
  const [hoveredTxn, setHoveredTxn]    = useState(null);

  const loadAll = useCallback(async (d = days) => {
    // Apply any pending recurring instances first, then load data
    await fetch(API("/finances/recurring/apply"), { method: "POST" });
    const [s, c, t, r] = await Promise.all([
      fetch(API(`/finances/summary?days=${d}`)).then(x => x.ok ? x.json() : null),
      fetch(API(`/finances/categories?days=${d}`)).then(x => x.ok ? x.json() : null),
      fetch(API(`/finances/transactions?days=${d}&type=all&limit=1000`)).then(x => x.ok ? x.json() : null),
      fetch(API("/finances/recurring")).then(x => x.ok ? x.json() : []),
    ]);
    setSummary(s);
    setCategories(c);
    setTxns(t);
    setRecurring(r ?? []);
  }, [days]);

  useEffect(() => { loadAll(days); }, [days]);

  const handleTxnSaved = (newTxn) => {
    setTxns(prev => prev ? {
      ...prev,
      total: prev.total + 1,
      transactions: [newTxn, ...prev.transactions],
    } : { total: 1, transactions: [newTxn] });
    loadAll();
  };

  const deleteTxn = async (id) => {
    setDeletingId(id);
    try {
      await fetch(API(`/finances/transactions/${id}`), { method: "DELETE" });
      setTxns(prev => prev ? {
        ...prev,
        total: prev.total - 1,
        transactions: prev.transactions.filter(t => t.id !== id),
      } : prev);
      setExpandedTxn(null);
      loadAll();
    } finally {
      setDeletingId(null);
    }
  };

  const deleteRule = async (id) => {
    setDeletingRuleId(id);
    try {
      await fetch(API(`/finances/recurring/${id}`), { method: "DELETE" });
      setRecurring(prev => prev.filter(r => r.id !== id));
    } finally {
      setDeletingRuleId(null);
    }
  };

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
  }).filter(t => !selectedCategory || t.category === selectedCategory);

  const marginColor = summary?.margin == null ? "#3a5a80"
    : summary.margin > 30 ? "#14c882"
    : summary.margin > 0  ? "#f0a028"
    : "#dc3c3c";

  if (!summary) {
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

      {showAddForm && (
        <AddTransactionModal
          onClose={() => setShowAddForm(false)}
          onSaved={handleTxnSaved}
          onRecurringSaved={() => loadAll()}
        />
      )}

      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 22, fontWeight: 700, color: "#f0f4ff", letterSpacing: "-0.02em" }}>
            Finances
          </div>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80", letterSpacing: "0.18em", marginTop: 3 }}>
            MANUAL LEDGER · BUSINESS ACCOUNT
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <button
            onClick={() => setShowAddForm(true)}
            className="btn btn-primary"
            style={{ fontSize: 11, display: "flex", alignItems: "center", gap: 6, padding: "7px 16px" }}
          >
            + Add Transaction
          </button>
          <PeriodToggle days={days} setDays={setDays} options={FINANCES_PERIOD_OPTIONS} />
        </div>
      </div>

      {/* Summary cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
        <SummaryCard label="Revenue"  value={money(summary?.income)}   color="#14c882" />
        <SummaryCard label="Expenses" value={money(summary?.expenses)}  color="#f0a028" />
        <SummaryCard
          label="Net Profit"
          value={money(summary?.net)}
          color={(summary?.net ?? 0) >= 0 ? "#14c882" : "#dc3c3c"}
        />
        <SummaryCard
          label="Profit Margin"
          value={summary?.margin != null ? `${summary.margin}%` : "—"}
          color={marginColor}
          sub={summary?.margin != null ? (summary.margin > 30 ? "HEALTHY" : summary.margin > 0 ? "SLIM" : "LOSS") : null}
        />
      </div>

      {/* Recurring rules */}
      {recurring.length > 0 && (
        <div className="glass-card" style={{ padding: "18px 20px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
            <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 15, fontWeight: 600, color: "#d0dcf0" }}>
              Recurring
            </div>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", letterSpacing: "0.1em" }}>
              {recurring.length} ACTIVE
            </div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
            {recurring.map((rule, i) => (
              <div key={rule.id} style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                padding: "9px 0",
                borderBottom: i < recurring.length - 1 ? "0.5px solid #1a2540" : "none",
              }}>
                <div style={{ display: "flex", flexDirection: "column", gap: 3, flex: 1, marginRight: 12 }}>
                  <span style={{ fontSize: 12, color: "#8aaad0", fontWeight: 500 }}>
                    {rule.description || "—"}
                  </span>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{
                      fontFamily: "'Share Tech Mono', monospace", fontSize: 8,
                      padding: "2px 6px", borderRadius: 4,
                      background: "rgba(58,123,213,0.12)", color: "#3a7bd5", letterSpacing: "0.06em",
                    }}>
                      {rule.frequency.toUpperCase()}
                    </span>
                    <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a4a7a" }}>
                      next {rule.next_occurrence}
                    </span>
                    {rule.category && rule.category !== "Revenue" && (
                      <span style={{
                        fontFamily: "'Share Tech Mono', monospace", fontSize: 8,
                        padding: "2px 6px", borderRadius: 4,
                        background: "rgba(240,160,40,0.08)", color: "#a07020", letterSpacing: "0.06em",
                      }}>
                        {rule.category}
                      </span>
                    )}
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span style={{
                    fontFamily: "'Share Tech Mono', monospace", fontSize: 13, fontWeight: 700,
                    color: rule.is_income ? "#14c882" : "#f0a028",
                  }}>
                    {rule.is_income ? "+" : "-"}{money(rule.amount)}
                  </span>
                  <button
                    onClick={() => deleteRule(rule.id)}
                    disabled={deletingRuleId === rule.id}
                    style={{
                      padding: "4px 10px", borderRadius: 6,
                      border: "1px solid rgba(220,60,60,0.25)",
                      background: "rgba(220,60,60,0.06)", color: "#dc3c3c",
                      fontFamily: "'Share Tech Mono', monospace", fontSize: 8,
                      cursor: "pointer", letterSpacing: "0.06em",
                      opacity: deletingRuleId === rule.id ? 0.5 : 1,
                    }}
                  >
                    {deletingRuleId === rule.id ? "…" : "STOP"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Income vs Expenses trend */}
      <div className="glass-card" style={{ padding: "20px 22px" }}>
        <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 15, fontWeight: 600, color: "#d0dcf0", marginBottom: 4 }}>
          Income vs Expenses
        </div>
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", letterSpacing: "0.1em", marginBottom: 16 }}>
          LAST {days === 365 ? "12 MONTHS" : `${days} DAYS`} · CUMULATIVE · {(categories?.granularity ?? "daily").toUpperCase()}
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
            <XAxis
              dataKey="date"
              tick={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, fill: "#2a4a7a" }}
              axisLine={false} tickLine={false}
              tickFormatter={v => {
                if (!v) return "";
                if (days > 90) {
                  // monthly: show "Jan", "Feb", etc. Parse the "YYYY-MM-DD" string
                  // manually — new Date(v) parses as UTC midnight, which
                  // shifts back a day (and a month label) in timezones behind UTC.
                  const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
                  return MONTHS[parseInt(v.slice(5, 7), 10) - 1];
                }
                // daily/weekly: show "MM-DD"
                return v.slice(5);
              }}
            />
            <YAxis tick={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, fill: "#2a4a7a" }}
              axisLine={false} tickLine={false} tickFormatter={v => `$${v}`} />
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
              {categories.expense_breakdown.map(c => {
                const isSelected = selectedCategory === c.category;
                return (
                  <div
                    key={c.category}
                    onClick={() => setSelectedCategory(isSelected ? null : c.category)}
                    style={{
                      cursor: "pointer", borderRadius: 8, padding: "6px 8px", margin: "-6px -8px",
                      background: isSelected ? "rgba(58,123,213,0.12)" : "transparent",
                      border: isSelected ? "1px solid rgba(58,123,213,0.25)" : "1px solid transparent",
                      transition: "all 0.15s",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                      <span style={{ fontSize: 12, color: isSelected ? "#6ab0ff" : "#8aaad0", fontWeight: isSelected ? 600 : 400 }}>
                        {c.category}
                      </span>
                      <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: isSelected ? "#6ab0ff" : "#3a5a80" }}>
                        {money(c.total)} ({c.pct}%)
                      </span>
                    </div>
                    <div style={{ height: 2, background: "#111e36", borderRadius: 1 }}>
                      <div style={{ height: 2, borderRadius: 1, width: `${c.pct}%`, background: isSelected ? "#3a7bd5" : "#f0a028", opacity: isSelected ? 1 : 0.7 }} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="glass-card" style={{ padding: "18px 20px" }}>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 15, fontWeight: 600, color: "#d0dcf0", marginBottom: 14 }}>
            Top Expenses
          </div>
          {(categories?.expense_breakdown?.slice(0, 3) ?? []).map((c, i) => {
            const isSelected = selectedCategory === c.category;
            return (
              <div
                key={c.category}
                onClick={() => setSelectedCategory(isSelected ? null : c.category)}
                style={{
                  padding: "10px 8px", margin: "0 -8px",
                  borderBottom: i < 2 ? "0.5px solid #1a2540" : "none",
                  cursor: "pointer", borderRadius: 8,
                  background: isSelected ? "rgba(58,123,213,0.12)" : "transparent",
                  transition: "background 0.15s",
                }}
              >
                <div style={{ fontSize: 11, color: isSelected ? "#6ab0ff" : "#6080a8", marginBottom: 3 }}>{c.category}</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: isSelected ? "#3a7bd5" : "#f0a028", letterSpacing: "-0.02em" }}>
                  {money(c.total)}
                </div>
              </div>
            );
          })}
          {!categories?.expense_breakdown?.length && (
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52", letterSpacing: "0.1em" }}>NO DATA</div>
          )}
        </div>
      </div>

      {/* Transaction list */}
      <div className="glass-card" style={{ padding: "18px 20px" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 15, fontWeight: 600, color: "#d0dcf0" }}>
              Transactions
            </div>
            {selectedCategory && (
              <button
                onClick={() => setSelectedCategory(null)}
                style={{
                  display: "flex", alignItems: "center", gap: 5,
                  fontFamily: "'Share Tech Mono', monospace", fontSize: 9,
                  padding: "3px 8px 3px 10px", borderRadius: 20,
                  background: "rgba(58,123,213,0.18)", border: "1px solid rgba(58,123,213,0.35)",
                  color: "#6ab0ff", cursor: "pointer", letterSpacing: "0.06em",
                }}
              >
                {selectedCategory}
                <span style={{ fontSize: 11, lineHeight: 1, color: "#3a7bd5" }}>×</span>
              </button>
            )}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
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
            <button
              onClick={() => setShowAddForm(true)}
              className="btn btn-primary"
              style={{ fontSize: 10, padding: "5px 12px" }}
            >
              + Add
            </button>
          </div>
        </div>

        {filteredTxns.length === 0 ? (
          <div style={{ padding: "32px 0", textAlign: "center" }}>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52", letterSpacing: "0.1em", marginBottom: 12 }}>
              NO TRANSACTIONS
            </div>
            <button onClick={() => setShowAddForm(true)} className="btn btn-secondary" style={{ fontSize: 11 }}>
              Add your first transaction
            </button>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column" }}>
            {filteredTxns.map(t => (
              <div key={t.id}
                onMouseEnter={() => setHoveredTxn(t.id)}
                onMouseLeave={() => setHoveredTxn(null)}
              >
                <div
                  onClick={() => setExpandedTxn(expandedTxn === t.id ? null : t.id)}
                  style={{
                    display: "flex", alignItems: "center", justifyContent: "space-between",
                    padding: "9px 0", borderBottom: expandedTxn === t.id ? "none" : "0.5px solid #1a2540",
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
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span style={{
                      fontFamily: "'Share Tech Mono', monospace", fontSize: 13, fontWeight: 700,
                      color: t.is_income ? "#14c882" : "#f0a028",
                      letterSpacing: "-0.01em",
                    }}>
                      {t.is_income ? "+" : "-"}{money(t.amount)}
                    </span>
                    <button
                      onClick={e => { e.stopPropagation(); deleteTxn(t.id); }}
                      disabled={deletingId === t.id}
                      style={{
                        padding: "3px 9px", borderRadius: 5,
                        border: "1px solid rgba(220,60,60,0.25)",
                        background: "rgba(220,60,60,0.06)", color: "#dc3c3c",
                        fontFamily: "'Share Tech Mono', monospace", fontSize: 8,
                        cursor: "pointer", letterSpacing: "0.06em",
                        opacity: deletingId === t.id ? 0.5 : hoveredTxn === t.id ? 1 : 0,
                        transition: "opacity 0.15s",
                        pointerEvents: hoveredTxn === t.id ? "auto" : "none",
                      }}
                    >
                      {deletingId === t.id ? "…" : "✕"}
                    </button>
                  </div>
                </div>

                {/* Inline edit row (category + notes) */}
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
    </div>
  );
}
