import React, { useState, useEffect, useCallback, useRef } from "react";
import { API } from "../api.js";
import { T, Card, SectionTitle, Pill, Toggle, Empty, inputStyle } from "../ui.jsx";

// Automatic bookkeeping (backend finance_auto.py): Zapier's Novo sheet +
// CSV upload for the bank, Stripe for revenue, AI sorting with a review list,
// and real profit per client.

const money = (v) => (v == null ? "–" : `${v < 0 ? "-" : ""}$${Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`);

function ago(iso) {
  if (!iso) return "never";
  const m = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m} min ago`;
  if (m < 48 * 60) return `${Math.round(m / 60)} h ago`;
  return `${Math.round(m / 1440)} days ago`;
}

const selectStyle = { ...inputStyle, width: "auto", padding: "6px 10px", fontSize: 12.5 };

export function useFinanceStatus() {
  const [status, setStatus] = useState(null);
  const load = useCallback(async () => {
    const r = await fetch(API("/finances/auto/status"));
    if (r.ok) setStatus(await r.json());
  }, []);
  useEffect(() => { load(); }, [load]);
  return [status, load];
}

function Row({ label, ok, children }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, padding: "10px 0", borderBottom: `1px solid ${T.line}`, flexWrap: "wrap" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
        <Pill tone={ok === true ? "good" : ok === false ? "bad" : "neutral"} dot>{ok === true ? "On" : ok === false ? "Problem" : "Not set up"}</Pill>
        <span style={{ fontSize: 13.5, color: T.text, fontWeight: 500 }}>{label}</span>
      </div>
      <div style={{ fontSize: 12.5, color: T.textMute, minWidth: 0 }}>{children}</div>
    </div>
  );
}

export function BankFeedCard({ status, onChanged }) {
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(null);
  const [msg, setMsg] = useState(null);
  const [showHow, setShowHow] = useState(false);
  const fileRef = useRef(null);

  useEffect(() => { setUrl(status?.sheet_url || ""); }, [status?.sheet_url]);
  useEffect(() => { if (status && !status.sheet_url) setShowHow(true); }, [status?.sheet_url]);

  const call = async (key, path, body) => {
    setBusy(key); setMsg(null);
    try {
      const r = await fetch(API(path), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(data.detail || `Error ${r.status}`);
      return data;
    } catch (e) {
      setMsg({ tone: "bad", text: e.message });
      return null;
    } finally {
      setBusy(null);
    }
  };

  const saveSheet = async () => {
    const d = await call("sheet", "/finances/auto/sheet", { url });
    if (d) {
      const res = d.result;
      setMsg({ tone: "good", text: res ? `Connected. ${res.added} new transaction(s) pulled in, ${res.sorted} sorted.` : "Saved." });
      onChanged();
    }
  };

  const syncNow = async () => {
    const d = await call("sync", "/finances/auto/sync");
    if (d) {
      const parts = [];
      if (d.sheet?.added != null) parts.push(`${d.sheet.added} new from the bank`);
      if (d.stripe?.added != null) parts.push(`${d.stripe.added} new from Stripe`);
      if (typeof d.sorted === "number") parts.push(`${d.sorted} sorted`);
      const errs = [d.sheet?.error, d.stripe?.error, d.costs?.error].filter(Boolean);
      setMsg(errs.length ? { tone: "bad", text: errs.join(" · ") } : { tone: "good", text: parts.length ? `Done: ${parts.join(", ")}.` : "Everything is up to date." });
      onChanged();
    }
  };

  const upload = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    const text = await file.text();
    const d = await call("csv", "/finances/auto/import-csv", { csv: text });
    if (d) {
      setMsg({ tone: "good", text: `Imported ${d.added} transaction(s)${d.skipped ? ` (${d.skipped} already in)` : ""}. ${d.sorted} sorted by AI.` });
      onChanged();
    }
  };

  if (!status) return null;
  return (
    <Card>
      <SectionTitle
        title="Automatic tracking"
        hint="Bank spending comes from Novo through Zapier, revenue comes straight from Stripe. Stripe's deposits into Novo are counted as transfers, so money is never counted twice."
        right={
          <div style={{ display: "flex", gap: 8 }}>
            <input ref={fileRef} type="file" accept=".csv,text/csv" style={{ display: "none" }} onChange={upload} />
            <button className="btn btn-secondary" style={{ fontSize: 12.5 }} disabled={!!busy} onClick={() => fileRef.current?.click()}>
              {busy === "csv" ? "Importing…" : "Upload Novo CSV"}
            </button>
            <button className="btn btn-primary" style={{ fontSize: 12.5 }} disabled={!!busy} onClick={syncNow}>
              {busy === "sync" ? "Syncing…" : "Sync now"}
            </button>
          </div>
        }
      />

      <Row label="Novo bank (via Zapier sheet)" ok={status.sheet_url ? !status.sheet_error : null}>
        {status.sheet_error ? <span style={{ color: T.bad }}>{status.sheet_error.slice(0, 140)}</span>
          : status.sheet_url ? `Checked ${ago(status.sheet_synced_at)} · ${status.counts?.zapier || 0} transactions`
          : "Paste your Zapier sheet link below"}
      </Row>
      <Row label="Stripe revenue" ok={status.stripe_synced_at ? !status.stripe_error : null}>
        {status.stripe_error ? <span style={{ color: T.bad }}>{status.stripe_error.slice(0, 140)}</span>
          : `Checked ${ago(status.stripe_synced_at)} · ${status.counts?.stripe || 0} entries`}
      </Row>
      <Row label="Real per-client costs (Meta, Twilio, voice agent)" ok={status.costs_synced_at ? !status.costs_error : null}>
        {status.costs_error ? <span style={{ color: T.bad }}>{status.costs_error.slice(0, 140)}</span> : `Updated ${ago(status.costs_synced_at)}`}
      </Row>
      {(status.counts?.csv || 0) > 0 && <Row label="Uploaded CSVs" ok>{status.counts.csv} transactions</Row>}

      <div style={{ display: "flex", gap: 8, marginTop: 14, flexWrap: "wrap" }}>
        <input style={{ ...inputStyle, flex: "1 1 280px" }} placeholder="Google Sheet link Zapier writes to" value={url} onChange={(e) => setUrl(e.target.value)} />
        <button className="btn btn-secondary" style={{ fontSize: 12.5 }} disabled={!!busy || url === (status.sheet_url || "")} onClick={saveSheet}>
          {busy === "sheet" ? "Checking…" : "Save sheet"}
        </button>
      </div>

      {msg && <div style={{ marginTop: 10, fontSize: 13, color: msg.tone === "bad" ? T.bad : T.good }}>{msg.text}</div>}

      <button onClick={() => setShowHow(!showHow)} style={{ background: "none", border: "none", padding: 0, marginTop: 12, color: T.accent, fontSize: 13, cursor: "pointer", fontFamily: T.font }}>
        {showHow ? "Hide setup steps" : "How to set up the Zapier connection"}
      </button>
      {showHow && (
        <ol style={{ margin: "10px 0 0", paddingLeft: 20, color: T.textDim, fontSize: 13, lineHeight: 1.7 }}>
          <li>In Google Sheets (on the Google account the OS uses for your calendar), make a new sheet called <b>Novo transactions</b> with these headers in row 1: <b>Date</b>, <b>Description</b>, <b>Amount</b>, <b>Type</b>.</li>
          <li>In Zapier, create a Zap. Trigger: <b>Novo → New Transaction</b>, and log in to Novo when it asks.</li>
          <li>Action: <b>Google Sheets → Create Spreadsheet Row</b>, pick that sheet, and map Novo's date, description, amount and type (debit / credit) fields to the columns.</li>
          <li>Test it, turn the Zap on, then paste the sheet's link above and click <b>Save sheet</b>. The OS checks it every hour.</li>
          <li>For history from before today, download a CSV from Novo (Transactions → Export) and click <b>Upload Novo CSV</b>. Duplicates are skipped.</li>
        </ol>
      )}
    </Card>
  );
}

function CategorySelect({ value, status, onChange }) {
  const cats = status?.categories || { income: [], expense: [], transfer: "Transfer" };
  const known = [...cats.income, ...cats.expense, cats.transfer];
  return (
    <select style={selectStyle} value={value} onChange={(e) => onChange(e.target.value)}>
      {!known.includes(value) && <option value={value}>{value}</option>}
      <optgroup label="Money in">{cats.income.map((c) => <option key={c} value={c}>{c}</option>)}</optgroup>
      <optgroup label="Money out">{cats.expense.map((c) => <option key={c} value={c}>{c}</option>)}</optgroup>
      <optgroup label="Not counted"><option value={cats.transfer}>{cats.transfer}</option></optgroup>
    </select>
  );
}

export function ReviewCard({ status, onChanged }) {
  const [rows, setRows] = useState(null);
  const load = useCallback(async () => {
    const r = await fetch(API("/finances/auto/review"));
    if (r.ok) setRows(await r.json());
  }, []);
  useEffect(() => { load(); }, [load, status?.needs_review]);

  const patch = async (id, body) => {
    setRows((prev) => prev.filter((r) => r.id !== id));
    await fetch(API(`/finances/transactions/${id}`), { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    await load();
    onChanged();
  };

  if (!rows || rows.length === 0) return null;
  return (
    <Card style={{ borderColor: "rgba(242,173,61,0.35)" }}>
      <SectionTitle
        title={`Needs a look (${rows.length})`}
        hint="The AI wasn't sure about these. Pick the right category (or client) and it remembers that merchant from now on, or click OK if its guess is right."
      />
      <div style={{ display: "flex", flexDirection: "column" }}>
        {rows.map((t) => (
          <div key={t.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 0", borderBottom: `1px solid ${T.line}`, flexWrap: "wrap" }}>
            <div style={{ flex: "1 1 240px", minWidth: 0 }}>
              <div style={{ fontSize: 13.5, color: T.text, fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{t.description || "–"}</div>
              <div style={{ fontSize: 12, color: T.textMute }}>{t.date}{t.ai_note ? ` · ${t.ai_note}` : ""}</div>
            </div>
            <div style={{ fontFamily: T.display, fontWeight: 600, fontSize: 14, color: t.amount > 0 ? T.good : T.warn, minWidth: 90, textAlign: "right" }}>{money(t.amount)}</div>
            {t.source === "stripe" ? (
              <select style={selectStyle} value={t.client_id || ""} onChange={(e) => e.target.value && patch(t.id, { client_id: Number(e.target.value) })}>
                <option value="">Which client?</option>
                {(status?.clients || []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            ) : (
              <CategorySelect value={t.category} status={status} onChange={(v) => patch(t.id, { category: v })} />
            )}
            {t.category !== "Uncategorized" && t.source !== "stripe" && (
              <button className="btn btn-secondary" style={{ fontSize: 12, padding: "5px 12px" }} onClick={() => patch(t.id, { confirm: true })}>OK</button>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}

function shiftMonth(ym, n) {
  const [y, m] = ym.split("-").map(Number);
  const d = new Date(y, m - 1 + n, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export function ClientProfitCard() {
  const now = new Date();
  const thisMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  const [month, setMonth] = useState(thisMonth);
  const [data, setData] = useState(null);

  const load = useCallback(async () => {
    const r = await fetch(API(`/finances/auto/by-client?month=${month}`));
    if (r.ok) setData(await r.json());
  }, [month]);
  useEffect(() => { load(); }, [load]);

  const setCard = async (id, on) => {
    setData((d) => ({ ...d, clients: d.clients.map((c) => (c.client_id === id ? { ...c, ads_on_our_card: on } : c)) }));
    await fetch(API(`/finances/auto/clients/${id}/ads-on-card`), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ on }) });
    load();
  };

  const rows = data?.clients || [];
  const tot = rows.reduce((a, c) => ({ revenue: a.revenue + c.revenue, costs: a.costs + c.costs, profit: a.profit + c.profit }), { revenue: 0, costs: 0, profit: 0 });
  const th = { textAlign: "right", fontSize: 12, fontWeight: 500, color: T.textMute, padding: "8px 10px", whiteSpace: "nowrap" };
  const td = { textAlign: "right", fontSize: 13.5, color: T.textDim, padding: "10px", fontVariantNumeric: "tabular-nums", whiteSpace: "nowrap" };

  return (
    <Card>
      <SectionTitle
        title="Profit per client"
        hint="What each client paid you through Stripe, minus what they actually cost: Meta ad spend (when it runs on your card), their Twilio texts + calls, voice agent calls, tools and Stripe fees."
        right={
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <button className="btn btn-secondary" style={{ fontSize: 12, padding: "4px 10px" }} onClick={() => setMonth(shiftMonth(month, -1))}>‹</button>
            <span style={{ fontSize: 13, color: T.text, minWidth: 110, textAlign: "center" }}>{data?.label || "…"}</span>
            <button className="btn btn-secondary" style={{ fontSize: 12, padding: "4px 10px" }} disabled={month >= thisMonth} onClick={() => setMonth(shiftMonth(month, 1))}>›</button>
          </div>
        }
      />
      {rows.length === 0 ? <Empty>No client activity this month.</Empty> : (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: T.font }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${T.line}` }}>
                <th style={{ ...th, textAlign: "left" }}>Client</th>
                <th style={th}>Paid you</th>
                <th style={th}>Ad spend</th>
                <th style={th}>Ads on my card</th>
                <th style={th}>Tools + calls</th>
                <th style={th}>Fees</th>
                <th style={th}>Profit</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr key={c.client_id} style={{ borderBottom: `1px solid ${T.line}` }}>
                  <td style={{ ...td, textAlign: "left", color: T.text, fontWeight: 500 }}>{c.name}</td>
                  <td style={{ ...td, color: c.revenue ? T.good : T.textMute }}>{money(c.revenue)}</td>
                  <td style={{ ...td, opacity: c.ads_on_our_card ? 1 : 0.45 }}>{money(c.ad_spend)}</td>
                  <td style={td}><Toggle on={c.ads_on_our_card} onChange={(on) => setCard(c.client_id, on)} /></td>
                  <td style={td}>{money(c.tools)}</td>
                  <td style={td}>{money(c.fees)}</td>
                  <td style={{ ...td, fontWeight: 600, color: c.profit >= 0 ? T.good : T.bad }}>{money(c.profit)}</td>
                </tr>
              ))}
              <tr>
                <td style={{ ...td, textAlign: "left", color: T.text, fontWeight: 600 }}>Total</td>
                <td style={{ ...td, color: T.text, fontWeight: 600 }}>{money(tot.revenue)}</td>
                <td style={td} colSpan={3} />
                <td style={{ ...td, color: T.textMute }}>costs {money(tot.costs)}</td>
                <td style={{ ...td, fontWeight: 700, color: tot.profit >= 0 ? T.good : T.bad }}>{money(tot.profit)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
