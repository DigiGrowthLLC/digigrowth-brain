import React, { useState, useEffect, useRef } from "react";
import { easternToday, isTodoDue } from "../easternTime.js";
import { API } from "../api.js";
import { LineChart, Line, BarChart, Bar, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { linkify, inboxLinkFrom, InboxLinkButton } from "../linkify.jsx";
import DatePickerButton, { formatPickedDate } from "../components/DatePickerButton.jsx";
import { T, Card, PageHeader, SectionTitle, Pill, Stat, Empty, Loading } from "../ui.jsx";

// Dashboard: the original layout (stats, to-do + calendar, charts, reach +
// pipeline, agent activity + needs reply) in the 2026-11-17 design kit.
// To-do, calendar, agent activity and needs reply keep a fixed height and
// scroll inside; the last two have a Clear button.

function timeAgo(ts) {
  if (!ts) return "";
  const d = new Date(ts), diff = Date.now() - d;
  if (diff < 60000) return "just now";
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

const pct = (n, d) => (d > 0 ? `${((n / d) * 100).toFixed(1)}%` : "–");

// A card that fills its grid row; the body scrolls inside it, so every card in
// a row ends at the same line no matter how much it holds.
function Panel({ title, hint, right, children, style }) {
  return (
    <Card style={{ flex: "1 1 0", height: "100%", minWidth: 0, minHeight: 0, display: "flex", flexDirection: "column", ...style }}>
      <SectionTitle title={title} hint={hint} right={right} />
      <div style={{ flex: 1, minHeight: 0, minWidth: 0, overflowY: "auto", overflowX: "hidden" }}>{children}</div>
    </Card>
  );
}

// Agent messages are written in markdown ("## Lead gen run — ... **Doral, FL**").
const plain = (t) => String(t || "").replace(/^#+\s*/gm, "").replace(/\*\*|__|`/g, "").replace(/\s+/g, " ").trim();

// ── To-Do (today + overdue only) ────────────────────────────────────────────
function TodoWidgetRow({ t, overdue, onComplete, onRemove, onSaveDescription }) {
  const [expanded, setExpanded] = useState(false);
  const [draft, setDraft] = useState(t.description || "");
  const commit = () => {
    const trimmed = draft.trim();
    if (trimmed !== (t.description || "")) onSaveDescription(t.id, trimmed);
  };
  return (
    <div style={{ padding: "9px 0", borderTop: `1px solid ${T.line}` }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
        <button onClick={() => onComplete(t.id)} aria-label="Mark done" title="Mark done" style={{
          flexShrink: 0, width: 18, height: 18, marginTop: 1, cursor: "pointer", borderRadius: 6,
          border: `1.5px solid ${T.lineStrong}`, background: "transparent",
        }} />
        <span onClick={() => { setDraft(t.description || ""); setExpanded((e) => !e); }}
          title={t.description ? "View or edit notes" : "Add notes"}
          style={{ flex: 1, fontSize: 13.5, color: T.text, lineHeight: 1.4, cursor: "pointer", minWidth: 0 }}>
          {t.text}
          {!!t.description && <span style={{ display: "inline-block", width: 6, height: 6, borderRadius: "50%", background: T.accent, marginLeft: 7, verticalAlign: "middle" }} />}
        </span>
        <InboxLinkButton href={inboxLinkFrom(t.description)} />
        {t.due_date && overdue && <Pill tone="bad">Overdue</Pill>}
        <button onClick={() => onRemove(t.id)} aria-label="Delete" style={{ fontSize: 13, color: T.textMute, cursor: "pointer", background: "none", border: "none", lineHeight: "19px", padding: 0 }}>✕</button>
      </div>
      {expanded && (
        <div style={{ padding: "8px 0 0 28px", display: "grid", gap: 6 }}>
          <textarea autoFocus className="dg-input" rows={2} placeholder="Notes, instructions, or a link…"
            value={draft} onChange={(e) => setDraft(e.target.value)} onBlur={commit}
            onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) e.target.blur(); }}
            style={{ resize: "vertical" }} />
          {draft.trim() && <div style={{ fontSize: 12.5, lineHeight: 1.5, color: T.textDim }}>{linkify(draft)}</div>}
        </div>
      )}
    </div>
  );
}

function TodoList({ onNavigate }) {
  const [todos, setTodos] = useState(null);
  const [draft, setDraft] = useState("");
  const todayStr = easternToday();
  const load = async () => {
    const r = await fetch(API("/dashboard/todos"));
    if (r.ok) setTodos(await r.json());
  };
  useEffect(() => { load(); }, []);
  const add = async () => {
    if (!draft.trim()) return;
    await fetch(API("/dashboard/todos"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: draft.trim() }) });
    setDraft(""); load();
  };
  const patch = (id, body) => fetch(API(`/dashboard/todos/${id}`), { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const complete = async (id) => { setTodos((p) => p.filter((t) => t.id !== id)); await patch(id, { done: true }); };
  const remove = async (id) => { setTodos((p) => p.filter((t) => t.id !== id)); await fetch(API(`/dashboard/todos/${id}`), { method: "DELETE" }); };
  const saveDescription = async (id, description) => { setTodos((p) => p.map((t) => (t.id === id ? { ...t, description } : t))); await patch(id, { description }); };

  const due = (todos || []).filter(isTodoDue);
  return (
    <Card style={{ flex: "1 1 0", height: "100%", minWidth: 0, minHeight: 0, display: "flex", flexDirection: "column" }}>
      <SectionTitle title="To-Do" hint="Due today and overdue"
        right={<button className="btn btn-ghost" style={{ padding: "5px 12px" }} onClick={() => onNavigate?.("todos")}>All to-dos →</button>} />
      <div style={{ display: "flex", gap: 8, marginBottom: 6 }}>
        <input value={draft} onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => e.key === "Enter" && add()}
          placeholder="Quick add…" className="dg-input" aria-label="New to-do" />
        <button onClick={add} className="btn btn-primary">Add</button>
      </div>
      <div style={{ flex: 1, minHeight: 0, overflowY: "auto", overflowX: "hidden" }}>
        {todos === null ? <Loading /> : due.length === 0 ? <Empty>All clear for today.</Empty> :
          due.map((t) => (
            <TodoWidgetRow key={t.id} t={t} overdue={t.due_date && t.due_date.slice(0, 10) < todayStr}
              onComplete={complete} onRemove={remove} onSaveDescription={saveDescription} />
          ))}
      </div>
    </Card>
  );
}

// ── Calendar ────────────────────────────────────────────────────────────────
function CalendarWidget({ events, loading, error }) {
  const todayEvents = events.filter((ev) => ev.start.slice(0, 10) === easternToday());
  const fmt = (start, end, allDay) => {
    if (allDay) return "All day";
    const o = { hour: "numeric", minute: "2-digit", hour12: true };
    const s = new Date(start).toLocaleTimeString("en-US", o);
    return end ? `${s} – ${new Date(end).toLocaleTimeString("en-US", o)}` : s;
  };
  const notSetUp = error && /missing|configured/i.test(error);
  return (
    <Panel title="Today's calendar" right={todayEvents.length ? <Pill tone="info">{todayEvents.length}</Pill> : null}>
      {loading ? <Loading /> : error ? <Empty>{notSetUp ? "Google Calendar isn't connected." : error}</Empty>
        : todayEvents.length === 0 ? <Empty>Nothing on the calendar today.</Empty> : (
          <div style={{ display: "grid", gap: 8 }}>
            {todayEvents.map((ev) => (
              <div key={ev.id} style={{ display: "grid", gridTemplateColumns: "92px minmax(0, 1fr)", gap: 10, padding: "9px 12px", borderRadius: 10, background: T.surface2, border: `1px solid ${T.line}` }}>
                <span style={{ fontSize: 12.5, color: "#8fb8ff", fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>{fmt(ev.start, ev.end, ev.all_day)}</span>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 13.5, color: T.text, lineHeight: 1.35 }}>{ev.title}</div>
                  {ev.location && <div style={{ fontSize: 12, color: T.textMute, marginTop: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={ev.location}>{ev.location}</div>}
                </div>
              </div>
            ))}
          </div>
        )}
    </Panel>
  );
}

// ── Charts ──────────────────────────────────────────────────────────────────
function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: "#0f1a3c", border: `1px solid ${T.lineStrong}`, borderRadius: 10, padding: "8px 12px", fontSize: 12.5 }}>
      <div style={{ color: T.textDim, marginBottom: 3 }}>{label}</div>
      {payload.map((p) => <div key={p.dataKey} style={{ color: p.color || T.text, fontWeight: 600 }}>{p.name}: {p.value}</div>)}
    </div>
  );
}
const AXIS = { fontFamily: "Inter, sans-serif", fontSize: 11.5, fill: "#6c7fa3" };

const STAT_ICONS = {
  dialer: <path d="M4 3h3l1.5 3.5-2 1.2c.8 1.7 2.3 3.2 4 4l1.2-2L15.5 11V14c0 .6-.4 1-1 1C7 15 4 8 4 4c0-.6.4-1 1-1H4z" />,
  reach: <><circle cx="7" cy="7" r="3" /><circle cx="14" cy="7" r="3" /><path d="M2 17c0-3 2.24-5 5-5m5 0c2.76 0 5 2 5 5" /></>,
  booked: <><rect x="3" y="4" width="14" height="13" rx="2" /><path d="M7 2v4M13 2v4M3 9h14M7 13l2 2 4-4" /></>,
  rate: <><path d="M3 16l4-5 3 3 6-8" /><path d="M12 6h4v4" /></>,
};

function StatTile({ label, value, sub, icon, tone }) {
  return (
    <Card pad={18} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, minWidth: 0 }}>
      <Stat label={label} value={value} sub={sub} tone={tone} />
      <div style={{ width: 42, height: 42, borderRadius: 12, flexShrink: 0, display: "grid", placeItems: "center", background: T.accentSoft }}>
        <svg viewBox="0 0 20 20" width={20} height={20} fill="none" stroke="#8fb8ff" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">{STAT_ICONS[icon]}</svg>
      </div>
    </Card>
  );
}

function AttentionRow({ title, sub, right, onClick, tone }) {
  return (
    <div onClick={onClick} role={onClick ? "button" : undefined} tabIndex={onClick ? 0 : undefined}
      onKeyDown={(e) => { if (onClick && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); onClick(); } }}
      style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 12px", borderRadius: 10, cursor: onClick ? "pointer" : "default",
        background: T.surface2, border: `1px solid ${tone === "warn" ? "rgba(242,173,61,0.3)" : T.line}`, borderLeft: tone === "warn" ? `3px solid ${T.warn}` : undefined }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13.5, fontWeight: 600, color: T.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{title}</div>
        {sub && <div style={{ fontSize: 12.5, color: T.textMute, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", marginTop: 1 }}>{sub}</div>}
      </div>
      {right && <div style={{ flexShrink: 0 }}>{right}</div>}
    </div>
  );
}

function ClearButton({ onClick, busy }) {
  return <button className="btn btn-ghost" style={{ padding: "4px 12px", fontSize: 12.5 }} disabled={busy} onClick={onClick}>{busy ? "Clearing…" : "Clear"}</button>;
}

// ── Main ────────────────────────────────────────────────────────────────────
export default function DashboardPanel({ onNavigate }) {
  const [period, setPeriod] = useState("all");
  const [date, setDate] = useState(null); // a picked day overrides `period`
  const [stats, setStats] = useState(null);
  const [agentMsgs, setAgentMsgs] = useState([]);
  const [clientMsgs, setClientMsgs] = useState([]);
  const [calEvents, setCalEvents] = useState([]);
  const [calLoading, setCalLoading] = useState(true);
  const [calError, setCalError] = useState(null);
  const [clearing, setClearing] = useState(null);

  const loadCalendar = async () => {
    try {
      const r = await fetch(API("/dashboard/calendar?days=1"));
      if (r.ok) { const d = await r.json(); setCalEvents(d.events || []); setCalError(d.error || null); }
    } catch { setCalError("Couldn't load the calendar."); } finally { setCalLoading(false); }
  };

  const PERIOD_LABEL = { day: "Today", week: "This week", month: "This month", all: "All time" };
  const periodLabel = date ? formatPickedDate(date) : PERIOD_LABEL[period];

  // Only the latest load may set stats: a slow All Time response must not
  // land on top of a day picked after it.
  const latestLoad = useRef(0);
  const load = async (p = period, d = date) => {
    const seq = ++latestLoad.current;
    const [s, a, c] = await Promise.all([
      fetch(API(`/dashboard/summary?period=${p}${d ? `&date=${d}` : ""}`)),
      fetch(API("/dashboard/agent-messages")),
      fetch(API("/dashboard/client-messages")),
    ]);
    const summary = s.ok ? await s.json() : null;
    if (summary && seq === latestLoad.current) setStats(summary);
    if (a.ok) setAgentMsgs((await a.json()).filter((m) => !m.read));
    if (c.ok) setClientMsgs(await c.json());
  };
  useEffect(() => { load(period, date); }, [period, date]);
  useEffect(() => { loadCalendar(); }, []);
  useEffect(() => { const id = setInterval(() => load(period, date), 30000); return () => clearInterval(id); }, [period, date]);

  const markRead = async (id) => {
    setAgentMsgs((p) => p.filter((m) => m.id !== id));
    await fetch(API(`/dashboard/agent-messages/${id}/read`), { method: "POST" });
  };
  const clearAgents = async () => {
    setClearing("agents");
    await fetch(API("/dashboard/agent-messages/read-all"), { method: "POST" });
    setAgentMsgs([]); setClearing(null);
  };
  const clearReplies = async () => {
    if (!window.confirm("Mark every thread in Needs a reply as read? They'll stop showing as unread in the Inbox too.")) return;
    setClearing("replies");
    await fetch(API("/dashboard/client-messages/clear"), { method: "POST" });
    setClientMsgs([]); setClearing(null);
  };

  const calling = stats?.calling ?? {};
  const sms = stats?.sms ?? {};
  const contacts = stats?.contacts ?? {};
  const outreach = calling.total_outreach ?? 0;
  const reached = calling.total_reached ?? 0;
  const today = new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });

  const funnelData = [
    { stage: "Outreach", value: outreach },
    { stage: "Answered", value: calling.total_answered ?? 0 },
    { stage: "Reached", value: reached },
    { stage: "Booked", value: calling.total_appointments ?? 0 },
  ];
  // "SMS" uses sms.messages (period-scoped), not sms.active (a static snapshot).
  const barData = [
    { name: "Outreach", value: outreach, fill: "#4d8ef0" },
    { name: "Reached", value: reached, fill: "#2fd08f" },
    { name: "Booked", value: calling.total_appointments ?? 0, fill: "#f2ad3d" },
    { name: "SMS", value: sms.messages ?? 0, fill: "#a080f0" },
  ];

  return (
    <div className="px-4 py-4 sm:px-8 sm:py-7" style={{ flex: 1, overflowY: "auto", overflowX: "hidden" }}>
      <div style={{ maxWidth: 1320, margin: "0 auto", display: "grid", gridTemplateColumns: "minmax(0, 1fr)", gap: 18 }}>
        <PageHeader
          title="Dashboard"
          subtitle={today}
          actions={
            <>
              <div style={{ display: "flex", gap: 3, padding: 3, borderRadius: 10, background: "rgba(120,150,210,0.08)" }}>
                {[["day", "Today"], ["week", "Week"], ["month", "Month"], ["all", "All time"]].map(([p, label]) => {
                  const on = !date && period === p;
                  return (
                    <button key={p} onClick={() => { setPeriod(p); setDate(null); }} style={{
                      fontSize: 13, fontWeight: 600, padding: "6px 14px", borderRadius: 8, border: "none", cursor: "pointer",
                      background: on ? "rgba(77,142,240,0.22)" : "transparent", color: on ? T.text : T.textMute,
                    }}>{label}</button>
                  );
                })}
              </div>
              <DatePickerButton date={date} setDate={setDate} />
            </>
          }
        />

        {/* Row 1: stat cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4" style={{ gap: 16 }}>
          <StatTile label="Total outreach" value={stats ? outreach : "–"} sub={periodLabel} icon="dialer" />
          <StatTile label="Total reached" value={stats ? reached : "–"} sub={outreach ? `${pct(reached, outreach)} reach rate` : "–"} icon="reach" />
          <StatTile label="Appointments" value={stats ? calling.total_appointments ?? 0 : "–"} sub="booked" icon="booked" tone="good" />
          <StatTile label="Booking rate" value={outreach ? `${calling.total_abr}%` : "–"} sub="of outreach" icon="rate" />
        </div>

        {/* Row 2: To-Do + calendar, same height, scroll inside */}
        <div className="grid grid-cols-1 md:grid-cols-2" style={{ gap: 16 }}>
          <div className="flex flex-col" style={{ height: 400, minWidth: 0 }}><TodoList onNavigate={onNavigate} /></div>
          <div className="flex flex-col" style={{ height: 400, minWidth: 0 }}><CalendarWidget events={calEvents} loading={calLoading} error={calError} /></div>
        </div>

        {/* Row 3: charts */}
        <div className="grid grid-cols-1 lg:grid-cols-[1.8fr_1fr]" style={{ gap: 16 }}>
          <Card>
            <SectionTitle title="Outreach overview" hint={periodLabel} />
            {funnelData.some((d) => d.value > 0) ? (
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={funnelData} margin={{ top: 8, right: 12, bottom: 0, left: -18 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(120,150,210,0.08)" />
                  <XAxis dataKey="stage" tick={AXIS} axisLine={false} tickLine={false} />
                  <YAxis tick={AXIS} axisLine={false} tickLine={false} />
                  <Tooltip content={<ChartTooltip />} />
                  <Line type="monotone" dataKey="value" name="Count" stroke="#4d8ef0" strokeWidth={2.5}
                    dot={{ fill: "#4d8ef0", r: 4, strokeWidth: 0 }} activeDot={{ fill: "#8fb8ff", r: 6, strokeWidth: 0 }} />
                </LineChart>
              </ResponsiveContainer>
            ) : <div style={{ height: 200, display: "grid", placeItems: "center" }}><Empty>No outreach in this period.</Empty></div>}
          </Card>
          <Card>
            <SectionTitle title="Period breakdown" hint={periodLabel} />
            <ResponsiveContainer width="100%" height={150}>
              <BarChart data={barData} margin={{ top: 4, right: 0, bottom: 0, left: -18 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(120,150,210,0.08)" vertical={false} />
                <XAxis dataKey="name" tick={AXIS} axisLine={false} tickLine={false} />
                <YAxis tick={AXIS} axisLine={false} tickLine={false} />
                <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(120,150,210,0.06)" }} />
                <Bar dataKey="value" name="Count" radius={[6, 6, 0, 0]}>
                  {barData.map((e) => <Cell key={e.name} fill={e.fill} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8, borderTop: `1px solid ${T.line}`, marginTop: 12, paddingTop: 12 }}>
              {barData.map(({ name, value, fill }) => (
                <div key={name} style={{ textAlign: "center" }}>
                  <div style={{ fontSize: 12, color: T.textMute }}>{name}</div>
                  <div style={{ fontSize: 17, fontWeight: 700, color: fill, fontVariantNumeric: "tabular-nums" }}>{value}</div>
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* Row 4: reach rate + pipeline */}
        <div className="grid grid-cols-1 sm:grid-cols-2" style={{ gap: 16 }}>
          <Card>
            <SectionTitle title="Reach rate" hint="Reached ÷ total outreach" />
            <div style={{ fontFamily: T.display, fontSize: 46, fontWeight: 700, letterSpacing: "-0.03em", color: T.text, lineHeight: 1.1, margin: "6px 0 14px" }}>
              {outreach ? pct(reached, outreach) : "–"}
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", borderTop: `1px solid ${T.line}`, paddingTop: 12 }}>
              <Stat label="Outreach" value={outreach} />
              <div style={{ textAlign: "right" }}><Stat label="Reached" value={reached} tone="good" /></div>
            </div>
          </Card>
          <Card>
            <SectionTitle title="Pipeline" hint={periodLabel} />
            <div style={{ display: "grid", gap: 12 }}>
              {[
                ["Total contacts", contacts.total ?? 0, "#8fb8ff"],
                ["New this period", contacts.new ?? 0, T.good],
                ["SMS booked", sms.booked ?? 0, T.warn],
                ["Active conversations", sms.active ?? 0, "#a080f0"],
              ].map(([label, value, color]) => (
                <div key={label} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ display: "flex", alignItems: "center", gap: 9, fontSize: 13.5, color: T.textDim }}>
                    <span style={{ width: 8, height: 8, borderRadius: "50%", background: color }} />{label}
                  </span>
                  <span style={{ fontSize: 16, fontWeight: 700, color: T.text, fontVariantNumeric: "tabular-nums" }}>{value}</span>
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* Row 5: agent activity + needs reply, same height, scroll inside */}
        <div className="grid grid-cols-1 md:grid-cols-2" style={{ gap: 16 }}>
          <div className="flex flex-col" style={{ height: 320, minWidth: 0 }}>
            <Panel title="Agent activity"
              right={<div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                {agentMsgs.length > 0 && <Pill tone="info">{agentMsgs.length} new</Pill>}
                {agentMsgs.length > 0 && <ClearButton busy={clearing === "agents"} onClick={clearAgents} />}
              </div>}>
              <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr)", gap: 8 }}>
                {agentMsgs.length === 0 ? <Empty>No new messages from your agents.</Empty> : agentMsgs.map((m) => (
                  <AttentionRow key={m.id} title={plain(m.message)} sub={`${m.agent ?? "system"} · ${timeAgo(m.created_at)}`}
                    onClick={() => { onNavigate?.("agents", m.agent); markRead(m.id); }} />
                ))}
              </div>
            </Panel>
          </div>
          <div className="flex flex-col" style={{ height: 320, minWidth: 0 }}>
            <Panel title="Needs a reply"
              right={<div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                {clientMsgs.length > 0 && <Pill tone="warn">{clientMsgs.length}</Pill>}
                {clientMsgs.length > 0 && <ClearButton busy={clearing === "replies"} onClick={clearReplies} />}
              </div>}>
              <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr)", gap: 8 }}>
                {clientMsgs.length === 0 ? <Empty>All caught up.</Empty> : clientMsgs.map((m) => (
                  <AttentionRow key={m.phone} tone="warn" title={m.business || m.owner || m.phone} sub={m.last_message}
                    right={<span style={{ fontSize: 12, color: T.textMute, whiteSpace: "nowrap" }}>{timeAgo(m.last_inbound_at)}</span>}
                    onClick={() => { onNavigate?.("inbox", { channel: "sms", phone: m.phone }); setClientMsgs((p) => p.filter((x) => x.phone !== m.phone)); }} />
                ))}
              </div>
            </Panel>
          </div>
        </div>
      </div>
    </div>
  );
}
