import React, { useState, useEffect, useRef } from "react";
import { easternToday, isTodoDue } from "../easternTime.js";
import { API } from "../api.js";
import { linkify, inboxLinkFrom, InboxLinkButton } from "../linkify.jsx";
import DatePickerButton, { formatPickedDate } from "../components/DatePickerButton.jsx";
import { T, Card, PageHeader, SectionTitle, Pill, Stat, Empty, Loading, HealthBadge } from "../ui.jsx";

// Dashboard (redesigned 2026-11-17): one screen for "what needs me today".
// Left: the outreach numbers once (stat strip + one funnel) and the pipeline.
// Right: today's calendar and due to-dos. Bottom: who needs a reply, what
// the agents reported, and which clients need attention (Client Success).

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

// ── Outreach funnel: one horizontal bar per stage, with step conversion ─────
function Funnel({ stages }) {
  const top = Math.max(1, ...stages.map((s) => s.value || 0));
  if (!stages.some((s) => s.value > 0)) return <Empty>No outreach in this period.</Empty>;
  return (
    <div style={{ display: "grid", gap: 12 }}>
      {stages.map((s, i) => {
        const prev = i ? stages[i - 1].value : null;
        return (
          <div key={s.label} style={{ display: "grid", gridTemplateColumns: "92px 1fr 64px", alignItems: "center", gap: 12 }}>
            <span style={{ fontSize: 13, color: T.textDim }}>{s.label}</span>
            <div style={{ height: 26, borderRadius: 8, background: "rgba(120,150,210,0.08)", overflow: "hidden" }}>
              <div style={{ display: "flex", alignItems: "center", height: "100%" }}>
                <div style={{ width: `${Math.max(2, (s.value / top) * 100)}%`, height: "100%", borderRadius: 8, background: s.color, display: "flex", alignItems: "center", paddingLeft: 10 }}>
                  {s.value / top >= 0.12 && <span style={{ fontSize: 12.5, fontWeight: 700, color: "#06102a" }}>{s.value}</span>}
                </div>
                {s.value / top < 0.12 && <span style={{ fontSize: 12.5, fontWeight: 700, color: T.text, marginLeft: 8 }}>{s.value}</span>}
              </div>
            </div>
            <span style={{ fontSize: 12.5, color: T.textMute, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{prev != null ? pct(s.value, prev) : ""}</span>
          </div>
        );
      })}
      <div style={{ fontSize: 12, color: T.textMute }}>Right column: share who made it from the step above.</div>
    </div>
  );
}

function AttentionRow({ title, sub, right, onClick, tone }) {
  return (
    <div onClick={onClick} role={onClick ? "button" : undefined} tabIndex={onClick ? 0 : undefined}
      onKeyDown={(e) => { if (onClick && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); onClick(); } }}
      style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 12px", borderRadius: 10, cursor: onClick ? "pointer" : "default",
        background: T.surface2, border: `1px solid ${tone === "warn" ? "rgba(242,173,61,0.3)" : T.line}` }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13.5, fontWeight: 600, color: T.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{title}</div>
        {sub && <div style={{ fontSize: 12.5, color: T.textMute, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", marginTop: 1 }}>{sub}</div>}
      </div>
      {right && <div style={{ flexShrink: 0 }}>{right}</div>}
    </div>
  );
}

// ── Main ────────────────────────────────────────────────────────────────────
export default function DashboardPanel({ onNavigate }) {
  const [period, setPeriod] = useState("all");
  const [date, setDate] = useState(null); // a picked day overrides `period`
  const [stats, setStats] = useState(null);
  const [agentMsgs, setAgentMsgs] = useState([]);
  const [clientMsgs, setClientMsgs] = useState([]);
  const [clientsCs, setClientsCs] = useState([]);
  const [calEvents, setCalEvents] = useState([]);
  const [calLoading, setCalLoading] = useState(true);
  const [calError, setCalError] = useState(null);

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
    const [s, a, c, cs] = await Promise.all([
      fetch(API(`/dashboard/summary?period=${p}${d ? `&date=${d}` : ""}`)),
      fetch(API("/dashboard/agent-messages")),
      fetch(API("/dashboard/client-messages")),
      fetch("/api/client-success/clients").catch(() => null),
    ]);
    const summary = s.ok ? await s.json() : null;
    if (summary && seq === latestLoad.current) setStats(summary);
    if (a.ok) setAgentMsgs((await a.json()).filter((m) => !m.read));
    if (c.ok) setClientMsgs(await c.json());
    if (cs && cs.ok) setClientsCs(await cs.json());
  };
  useEffect(() => { load(period, date); }, [period, date]);
  useEffect(() => { loadCalendar(); }, []);
  useEffect(() => { const id = setInterval(() => load(period, date), 30000); return () => clearInterval(id); }, [period, date]);

  const markRead = async (id) => {
    setAgentMsgs((p) => p.filter((m) => m.id !== id));
    await fetch(API(`/dashboard/agent-messages/${id}/read`), { method: "POST" });
  };

  const calling = stats?.calling ?? {};
  const sms = stats?.sms ?? {};
  const contacts = stats?.contacts ?? {};
  const outreach = calling.total_outreach ?? 0;
  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  const today = new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });

  const clientAttention = clientsCs
    .filter((c) => !c.is_test && c.status === "active")
    .map((c) => {
      const why = [];
      if (c.health?.band === "red") why.push(`At risk (health ${c.health.score})`);
      if (c.open_questions) why.push(`${c.open_questions} question${c.open_questions > 1 ? "s" : ""} to answer`);
      return { c, why };
    })
    .filter((x) => x.why.length);

  return (
    <div className="px-4 py-4 sm:px-8 sm:py-7" style={{ flex: 1, overflowY: "auto", overflowX: "hidden" }}>
      <div style={{ maxWidth: 1240, margin: "0 auto", display: "grid", gridTemplateColumns: "minmax(0, 1fr)", gap: 18 }}>
        <PageHeader
          title={`${greeting}, Dylan`}
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

        {/* Numbers strip */}
        <Card pad={0}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))" }}>
            {[
              { label: "Outreach", value: outreach, sub: periodLabel },
              { label: "Reached", value: calling.total_reached ?? 0, sub: `${pct(calling.total_reached ?? 0, outreach)} of outreach` },
              { label: "Appointments booked", value: calling.total_appointments ?? 0, sub: outreach ? `${calling.total_abr}% booking rate` : "–", tone: "good" },
              { label: "SMS messages", value: sms.messages ?? 0, sub: `${sms.active ?? 0} active conversations` },
            ].map((s, i) => (
              <div key={s.label} style={{ padding: "18px 20px", borderLeft: i ? `1px solid ${T.line}` : "none" }}>
                <Stat label={s.label} value={stats ? s.value : "–"} sub={s.sub} tone={s.tone} />
              </div>
            ))}
          </div>
        </Card>

        {/* Row: funnel + pipeline */}
        <div className="grid grid-cols-1 lg:grid-cols-[2fr_1fr] lg:h-[290px]" style={{ gap: 18 }}>
          <Panel title="Outreach funnel" hint={periodLabel}>
            {stats ? (
              <Funnel stages={[
                { label: "Outreach", value: outreach, color: "#4d8ef0" },
                { label: "Answered", value: calling.total_answered ?? 0, color: "#6aa5ff" },
                { label: "Reached", value: calling.total_reached ?? 0, color: "#2fd08f" },
                { label: "Booked", value: calling.total_appointments ?? 0, color: "#f2ad3d" },
              ]} />
            ) : <Loading />}
          </Panel>
          <Panel title="Pipeline" hint={periodLabel}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 22, paddingTop: 6 }}>
              <Stat label="Total contacts" value={contacts.total ?? 0} />
              <Stat label="New this period" value={contacts.new ?? 0} tone="good" />
              <Stat label="Booked by SMS" value={sms.booked ?? 0} />
              <Stat label="Active conversations" value={sms.active ?? 0} />
            </div>
          </Panel>
        </div>

        {/* Row: today */}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 xl:h-[460px]" style={{ gap: 18 }}>
          <div className="flex flex-col h-[420px] xl:h-auto" style={{ minWidth: 0 }}><TodoList onNavigate={onNavigate} /></div>
          <div className="flex flex-col h-[420px] xl:h-auto" style={{ minWidth: 0 }}><CalendarWidget events={calEvents} loading={calLoading} error={calError} /></div>
          <div className="flex flex-col h-[420px] xl:h-auto md:col-span-2 xl:col-span-1" style={{ minWidth: 0 }}>
            <Panel title="Needs a reply" right={clientMsgs.length ? <Pill tone="warn">{clientMsgs.length}</Pill> : null}>
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

        {/* Row: clients + agents */}
        <div className={`grid grid-cols-1 ${clientAttention.length ? "lg:grid-cols-2" : ""} lg:h-[320px]`} style={{ gap: 18 }}>
          {clientAttention.length > 0 && (
            <div className="flex flex-col h-[320px] lg:h-auto" style={{ minWidth: 0 }}>
              <Panel title="Clients needing you" style={{ borderColor: "rgba(242,173,61,0.35)" }}
                right={<button className="btn btn-ghost" style={{ padding: "5px 12px" }} onClick={() => onNavigate?.("clients")}>Clients →</button>}>
                <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr)", gap: 8 }}>
                  {clientAttention.map(({ c, why }) => (
                    <AttentionRow key={c.id} tone="warn" title={c.name} sub={why.join(" · ")} right={<HealthBadge health={c.health} compact />}
                      onClick={() => onNavigate?.("clients", { clientId: c.id })} />
                  ))}
                </div>
              </Panel>
            </div>
          )}
          <div className="flex flex-col h-[320px] lg:h-auto" style={{ minWidth: 0 }}>
            <Panel title="Agent activity" right={agentMsgs.length ? <Pill tone="info">{agentMsgs.length} new</Pill> : null}>
              <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr)", gap: 8 }}>
                {agentMsgs.length === 0 ? <Empty>No new messages from your agents.</Empty> : agentMsgs.map((m) => (
                  <AttentionRow key={m.id} title={plain(m.message)} sub={`${m.agent ?? "system"} · ${timeAgo(m.created_at)}`}
                    onClick={() => { onNavigate?.("agents", m.agent); markRead(m.id); }} />
                ))}
              </div>
            </Panel>
          </div>
        </div>
      </div>
    </div>
  );
}
