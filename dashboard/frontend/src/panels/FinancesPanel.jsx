import React, { useState, useEffect, useCallback, useMemo } from "react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { API } from "../api.js";
import { T, Card, PageHeader, SectionTitle, Tabs, Pill, Stat, Progress, Empty, Loading, inputStyle, PERIOD_OPTIONS, PERIOD_TEXT } from "../ui.jsx";
import { BankFeedCard, ReviewCard, ClientProfitCard, useFinanceStatus } from "../components/FinanceAuto.jsx";

// Finances tab (redesigned 2026-11-22): summary strip, then Overview /
// Clients / Transactions / Connections. Data comes from finance_auto.py
// (Novo via Zapier, Stripe, real per-client costs). "Transfer" rows (Stripe
// payouts into Novo) are listed but never counted in the totals.
const CATEGORIES = [
  "Client Revenue", "Other Income",
  "Ad Spend", "Software & Tools", "AI & APIs", "Phone & SMS", "Contractors",
  "Payment & Bank Fees", "Refunds", "Office & Equipment", "Education",
  "Travel & Meals", "Taxes & Legal", "Other",
  "Transfer", "Uncategorized",
];
const EXPENSE_CATEGORIES = CATEGORIES.filter((c) => !["Client Revenue", "Other Income"].includes(c));
const FREQ_LABELS = { weekly: "Weekly", monthly: "Monthly", yearly: "Yearly" };
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

const money = (v) => (v == null ? "–" : `$${Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`);
const money0 = (v) => (v == null ? "–" : `${v < 0 ? "-" : ""}$${Math.abs(v).toLocaleString("en-US", { maximumFractionDigits: 0 })}`);
const shortDate = (s) => (s ? `${MONTHS[parseInt(s.slice(5, 7), 10) - 1]} ${parseInt(s.slice(8, 10), 10)}` : "–");
const label = { fontSize: 12.5, color: T.textMute, marginBottom: 6, display: "block" };

function Segmented({ value, options, onChange }) {
  return (
    <div style={{ display: "inline-flex", padding: 3, gap: 2, borderRadius: 10, background: T.surface2, border: `1px solid ${T.line}` }}>
      {options.map(([v, l]) => (
        <button key={v} onClick={() => onChange(v)} style={{
          border: "none", cursor: "pointer", borderRadius: 8, padding: "6px 10px", fontFamily: T.font, fontSize: 12.5, fontWeight: 600,
          background: value === v ? T.accentSoft : "transparent", color: value === v ? T.text : T.textMute,
        }}>{l}</button>
      ))}
    </div>
  );
}

function ChartTooltip({ active, payload, label: l }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: "rgba(10,18,48,0.95)", border: `1px solid ${T.lineStrong}`, borderRadius: 10, padding: "8px 12px", fontSize: 12.5, fontFamily: T.font }}>
      <div style={{ color: T.textMute, marginBottom: 4 }}>{l}</div>
      {payload.map((p) => <div key={p.dataKey} style={{ color: p.color, fontWeight: 600 }}>{p.name}: {money(p.value)}</div>)}
    </div>
  );
}

function AddTransactionModal({ onClose, onSaved }) {
  const today = new Date().toISOString().slice(0, 10);
  const [form, setForm] = useState({ is_income: false, recurring: false, frequency: "monthly", description: "", amount: "", date: today, category: "Software & Tools", notes: "" });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const set = (k, v) => setForm((p) => ({ ...p, [k]: v }));

  const save = async () => {
    if (!form.description.trim()) return setError("Add a description.");
    const amt = parseFloat(form.amount);
    if (!amt || amt <= 0) return setError("Enter an amount above 0.");
    setSaving(true); setError(null);
    try {
      const common = { is_income: form.is_income, description: form.description.trim(), amount: amt, category: form.is_income ? "Client Revenue" : form.category, notes: form.notes.trim() || null };
      const resp = form.recurring
        ? await fetch(API("/finances/recurring"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...common, start_date: form.date, frequency: form.frequency }) })
        : await fetch(API("/finances/transactions"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...common, date: form.date }) });
      if (!resp.ok) return setError(await resp.text());
      onSaved();
      onClose();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const field = { ...inputStyle, width: "100%", boxSizing: "border-box" };
  return (
    <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)", backdropFilter: "blur(6px)", zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }}>
      <div className="ui-card" style={{ padding: 24, width: "100%", maxWidth: 440 }} onClick={(e) => e.stopPropagation()}>
        <div style={{ fontFamily: T.display, fontSize: 18, fontWeight: 700, color: T.text, marginBottom: 16 }}>Add a transaction</div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
          <Segmented value={form.is_income} options={[[false, "Expense"], [true, "Revenue"]]} onChange={(v) => set("is_income", v)} />
          <Segmented value={form.recurring} options={[[false, "One time"], [true, "Repeats"]]} onChange={(v) => set("recurring", v)} />
        </div>
        <div style={{ display: "grid", gap: 12 }}>
          <div><span style={label}>Description</span>
            <input style={field} value={form.description} onChange={(e) => set("description", e.target.value)} placeholder={form.is_income ? "e.g. Client retainer" : "e.g. Railway"} /></div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div><span style={label}>Amount ($)</span>
              <input style={field} type="number" min="0" step="0.01" value={form.amount} onChange={(e) => set("amount", e.target.value)} placeholder="0.00" /></div>
            <div><span style={label}>{form.recurring ? "First date" : "Date"}</span>
              <input style={field} type="date" value={form.date} onChange={(e) => set("date", e.target.value)} /></div>
          </div>
          {form.recurring && (
            <div><span style={label}>How often</span>
              <Segmented value={form.frequency} options={Object.entries(FREQ_LABELS)} onChange={(v) => set("frequency", v)} /></div>
          )}
          {!form.is_income && (
            <div><span style={label}>Category</span>
              <select style={field} value={form.category} onChange={(e) => set("category", e.target.value)}>
                {EXPENSE_CATEGORIES.map((c) => <option key={c}>{c}</option>)}
              </select></div>
          )}
          <div><span style={label}>Note (optional)</span>
            <input style={field} value={form.notes} onChange={(e) => set("notes", e.target.value)} onKeyDown={(e) => e.key === "Enter" && save()} /></div>
        </div>
        {error && <div style={{ marginTop: 12, fontSize: 13, color: T.bad }}>{error}</div>}
        <div style={{ display: "flex", gap: 10, marginTop: 20 }}>
          <button className="btn btn-secondary" style={{ flex: 1 }} onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" style={{ flex: 1 }} disabled={saving} onClick={save}>{saving ? "Saving…" : "Add"}</button>
        </div>
      </div>
    </div>
  );
}

function Overview({ summary, categories, days, onPickCategory }) {
  const cats = categories?.expense_breakdown || [];
  // All time asks for 10 years; start the chart at the first month with money moving.
  const series = categories?.daily ?? [];
  const first = series.findIndex((p) => p.income || p.expenses);
  const trimmed = first > 0 ? series.slice(first) : series;
  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1.5fr_1fr]" style={{ gap: 16 }}>
      <Card>
        <SectionTitle title="Money in vs money out" hint={`Running total · ${PERIOD_TEXT[days] || `last ${days} days`}`} />
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={trimmed} margin={{ top: 8, right: 4, bottom: 0, left: -8 }}>
            <defs>
              <linearGradient id="fIn" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor={T.good} stopOpacity={0.28} /><stop offset="95%" stopColor={T.good} stopOpacity={0} /></linearGradient>
              <linearGradient id="fOut" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor={T.warn} stopOpacity={0.22} /><stop offset="95%" stopColor={T.warn} stopOpacity={0} /></linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(120,150,210,0.08)" vertical={false} />
            <XAxis dataKey="date" tick={{ fontFamily: T.font, fontSize: 11, fill: T.textMute }} axisLine={false} tickLine={false}
              tickFormatter={(v) => (!v ? "" : days === 0 ? `${MONTHS[parseInt(v.slice(5, 7), 10) - 1]} ${v.slice(2, 4)}` : days > 90 ? MONTHS[parseInt(v.slice(5, 7), 10) - 1] : shortDate(v))} minTickGap={24} />
            <YAxis tick={{ fontFamily: T.font, fontSize: 11, fill: T.textMute }} axisLine={false} tickLine={false} tickFormatter={(v) => `$${v}`} />
            <Tooltip content={<ChartTooltip />} />
            <Area type="monotone" dataKey="income" name="In" stroke={T.good} strokeWidth={2} fill="url(#fIn)" />
            <Area type="monotone" dataKey="expenses" name="Out" stroke={T.warn} strokeWidth={2} fill="url(#fOut)" />
          </AreaChart>
        </ResponsiveContainer>
      </Card>
      <Card>
        <SectionTitle title="Where the money went" hint="Click a category to see its transactions" />
        {!cats.length ? <Empty>No spending in this period.</Empty> : (
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {cats.map((c) => (
              <button key={c.category} onClick={() => onPickCategory(c.category)} style={{ background: "none", border: "none", textAlign: "left", cursor: "pointer", padding: "8px 6px", borderRadius: 8, fontFamily: T.font }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6, fontSize: 13.5 }}>
                  <span style={{ color: T.text }}>{c.category}</span>
                  <span style={{ color: T.textDim, fontVariantNumeric: "tabular-nums" }}>{money(c.total)} <span style={{ color: T.textMute }}>· {c.pct}%</span></span>
                </div>
                <Progress value={c.pct} max={100} />
              </button>
            ))}
          </div>
        )}
        {summary?.expenses > 0 && <div style={{ marginTop: 10, fontSize: 12.5, color: T.textMute }}>Total spent: {money(summary.expenses)}</div>}
      </Card>
    </div>
  );
}

function TxnRow({ t, open, onToggle, onUpdate, onDelete }) {
  return (
    <div style={{ borderBottom: `1px solid ${T.line}` }}>
      <div onClick={onToggle} style={{ display: "grid", gridTemplateColumns: "64px 1fr auto", alignItems: "center", gap: 12, padding: "11px 4px", cursor: "pointer" }}>
        <span style={{ fontSize: 12.5, color: T.textMute }}>{shortDate(t.date)}</span>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 13.5, color: T.text, fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{t.description || "–"}</div>
          <div style={{ display: "flex", gap: 6, marginTop: 4, flexWrap: "wrap" }}>
            <Pill tone={t.category === "Transfer" ? "neutral" : t.is_income ? "good" : "info"} style={{ fontSize: 11, padding: "1px 8px" }}>{t.category === "Transfer" ? "Transfer · not counted" : t.category}</Pill>
            {t.client_name && <Pill style={{ fontSize: 11, padding: "1px 8px" }}>{t.client_name}</Pill>}
            {t.needs_review && <Pill tone="warn" style={{ fontSize: 11, padding: "1px 8px" }}>Needs a look</Pill>}
          </div>
        </div>
        <span style={{ fontFamily: T.display, fontWeight: 600, fontSize: 14.5, fontVariantNumeric: "tabular-nums", color: t.category === "Transfer" ? T.textMute : t.is_income ? T.good : T.text }}>
          {t.is_income ? "+" : "-"}{money(t.amount)}
        </span>
      </div>
      {open && (
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", padding: "0 4px 12px 80px" }}>
          <select style={{ ...inputStyle, width: "auto", padding: "6px 10px", fontSize: 12.5 }} value={t.category} onChange={(e) => onUpdate({ category: e.target.value })}>
            {!CATEGORIES.includes(t.category) && <option>{t.category}</option>}
            {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
          </select>
          <input style={{ ...inputStyle, flex: "1 1 200px", padding: "6px 10px", fontSize: 12.5 }} placeholder="Add a note" defaultValue={t.notes || ""} onBlur={(e) => e.target.value !== (t.notes || "") && onUpdate({ notes: e.target.value })} />
          <span style={{ fontSize: 12, color: T.textMute }}>{t.source === "stripe" ? "From Stripe" : t.source === "manual" ? "Added by hand" : "From Novo"}</span>
          <button className="btn btn-secondary" style={{ fontSize: 12, padding: "5px 12px", color: T.bad }} onClick={onDelete}>Delete</button>
        </div>
      )}
    </div>
  );
}

function Transactions({ txns, category, setCategory, onUpdate, onDelete, onAdd }) {
  const [type, setType] = useState("all");
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(null);
  const [showAll, setShowAll] = useState(false);
  const list = (txns || []).filter((t) =>
    (type === "all" || (type === "income" ? t.is_income : !t.is_income)) &&
    (!category || t.category === category) &&
    (!q || `${t.description} ${t.client_name || ""} ${t.category}`.toLowerCase().includes(q.toLowerCase())));
  const shown = showAll ? list : list.slice(0, 60);
  return (
    <Card>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginBottom: 8 }}>
        <Segmented value={type} options={[["all", "All"], ["income", "Money in"], ["expense", "Money out"]]} onChange={setType} />
        <select style={{ ...inputStyle, width: "auto", padding: "6px 10px", fontSize: 12.5 }} value={category || ""} onChange={(e) => setCategory(e.target.value || null)}>
          <option value="">All categories</option>
          {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
        </select>
        <input style={{ ...inputStyle, flex: "1 1 180px", padding: "6px 10px", fontSize: 12.5 }} placeholder="Search" value={q} onChange={(e) => setQ(e.target.value)} />
        <button className="btn btn-primary" style={{ fontSize: 12.5 }} onClick={onAdd}>Add</button>
      </div>
      {!list.length ? <Empty>No transactions match.</Empty> : (
        <>
          {shown.map((t) => (
            <TxnRow key={t.id} t={t} open={open === t.id} onToggle={() => setOpen(open === t.id ? null : t.id)}
              onUpdate={(p) => onUpdate(t.id, p)} onDelete={() => onDelete(t)} />
          ))}
          {list.length > shown.length && (
            <button className="btn btn-secondary" style={{ marginTop: 12, fontSize: 12.5 }} onClick={() => setShowAll(true)}>Show all {list.length}</button>
          )}
        </>
      )}
    </Card>
  );
}

function Recurring({ rules, onStop }) {
  if (!rules.length) return null;
  return (
    <Card>
      <SectionTitle title="Repeating entries" hint="Added automatically on their date" />
      {rules.map((r) => (
        <div key={r.id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 0", borderBottom: `1px solid ${T.line}`, flexWrap: "wrap" }}>
          <div style={{ flex: "1 1 200px", minWidth: 0 }}>
            <div style={{ fontSize: 13.5, color: T.text, fontWeight: 500 }}>{r.description || "–"}</div>
            <div style={{ fontSize: 12, color: T.textMute }}>{FREQ_LABELS[r.frequency] || r.frequency} · next {shortDate(r.next_occurrence)}{r.category ? ` · ${r.category}` : ""}</div>
          </div>
          <span style={{ fontFamily: T.display, fontWeight: 600, color: r.is_income ? T.good : T.text }}>{r.is_income ? "+" : "-"}{money(r.amount)}</span>
          <button className="btn btn-secondary" style={{ fontSize: 12, padding: "5px 12px" }} onClick={() => onStop(r)}>Stop</button>
        </div>
      ))}
    </Card>
  );
}

export default function FinancesPanel() {
  const [days, setDays] = useState(90);
  const [tab, setTab] = useState("overview");
  const [summary, setSummary] = useState(null);
  const [categories, setCategories] = useState(null);
  const [txns, setTxns] = useState(null);
  const [recurring, setRecurring] = useState([]);
  const [category, setCategory] = useState(null);
  const [adding, setAdding] = useState(false);
  const [status, reloadStatus] = useFinanceStatus();

  const loadAll = useCallback(async () => {
    const d = days || 3650; // 0 = all time
    await fetch(API("/finances/recurring/apply"), { method: "POST" });
    const get = (p, d) => fetch(API(p)).then((x) => (x.ok ? x.json() : d));
    const [s, c, t, r] = await Promise.all([
      get(`/finances/summary?days=${d}`, null),
      get(`/finances/categories?days=${d}`, null),
      get(`/finances/transactions?days=${d}&type=all&limit=2000`, null),
      get("/finances/recurring", []),
    ]);
    setSummary(s); setCategories(c); setTxns(t?.transactions || []); setRecurring(r || []);
    reloadStatus();
  }, [days, reloadStatus]);
  useEffect(() => { loadAll(); }, [loadAll]);

  const updateTxn = async (id, patch) => {
    setTxns((prev) => prev.map((t) => (t.id === id ? { ...t, ...patch } : t)));
    await fetch(API(`/finances/transactions/${id}`), { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(patch) });
    if (patch.category) loadAll();
  };
  const deleteTxn = async (t) => {
    if (!window.confirm(`Delete "${t.description || "this transaction"}" (${money(t.amount)})? This can't be undone.`)) return;
    await fetch(API(`/finances/transactions/${t.id}`), { method: "DELETE" });
    loadAll();
  };
  const stopRule = async (r) => {
    if (!window.confirm(`Stop "${r.description}"? Past entries stay.`)) return;
    await fetch(API(`/finances/recurring/${r.id}`), { method: "DELETE" });
    setRecurring((prev) => prev.filter((x) => x.id !== r.id));
  };

  const connProblem = useMemo(() => status && (status.sheet_error || status.stripe_error || status.costs_error || !status.sheet_url), [status]);
  if (!summary) return <Loading />;

  const net = summary.net ?? 0;
  const tabs = [
    { id: "overview", label: "Overview" },
    { id: "clients", label: "Clients" },
    { id: "transactions", label: "Transactions", count: txns?.length },
    { id: "connections", label: "Connections", count: connProblem ? "!" : null, alert: !!connProblem },
  ];

  return (
    <div className="px-4 py-4 sm:px-6 sm:py-6" style={{ flex: 1, overflowY: "auto" }}>
      <div style={{ maxWidth: 1180, margin: "0 auto", display: "flex", flexDirection: "column", gap: 16 }}>
        {adding && <AddTransactionModal onClose={() => setAdding(false)} onSaved={loadAll} />}

        <PageHeader
          title="Finances"
          subtitle="Novo + Stripe, sorted automatically"
          actions={<>
            <Segmented value={days} options={PERIOD_OPTIONS} onChange={setDays} />
            <button className="btn btn-primary" style={{ fontSize: 13 }} onClick={() => setAdding(true)}>Add transaction</button>
          </>}
        />

        <Card>
          <div className="grid grid-cols-2 sm:grid-cols-4" style={{ gap: 16 }}>
            <Stat label="Money in" value={money0(summary.income)} tone="good" />
            <Stat label="Money out" value={money0(summary.expenses)} />
            <Stat label="Profit" value={money0(net)} tone={net >= 0 ? "good" : "bad"} />
            <Stat label="Margin" value={summary.margin != null ? `${summary.margin}%` : "–"}
              sub={summary.margin == null ? null : summary.margin > 30 ? "Healthy" : summary.margin > 0 ? "Slim" : "Losing money"} />
          </div>
        </Card>

        <ReviewCard status={status} onChanged={loadAll} />

        <Tabs tabs={tabs} value={tab} onChange={setTab} />

        {tab === "overview" && <Overview summary={summary} categories={categories} days={days} onPickCategory={(c) => { setCategory(c); setTab("transactions"); }} />}
        {tab === "clients" && <ClientProfitCard />}
        {tab === "transactions" && (
          <Transactions txns={txns} category={category} setCategory={setCategory} onUpdate={updateTxn} onDelete={deleteTxn} onAdd={() => setAdding(true)} />
        )}
        {tab === "connections" && <>
          <BankFeedCard status={status} onChanged={loadAll} />
          <Recurring rules={recurring} onStop={stopRule} />
        </>}
      </div>
    </div>
  );
}
