import React, { useState, useEffect } from "react";
import { easternToday } from "../easternTime.js";
import { API } from "../api.js";
import { linkify, inboxLinkFrom, InboxLinkButton } from "../linkify.jsx";
import { T, Card, PageHeader, SectionTitle, Pill, Stat, Empty, Loading, inputStyle } from "../ui.jsx";

// To-Do (redesigned 2026-11-17): quick add always on top, summary counts,
// search, and one card per group (Overdue / Today / Upcoming / No date).

const RECURRENCE_LABELS = { daily: "Daily", weekdays: "Weekdays", weekly: "Weekly", monthly: "Monthly" };

function groupTodos(todos) {
  const todayStr = easternToday();
  const overdue = [], today = [], upcoming = [], undated = [];
  for (const t of todos) {
    if (!t.due_date) { undated.push(t); continue; }
    const d = t.due_date.slice(0, 10);
    if (d < todayStr) overdue.push(t);
    else if (d === todayStr) today.push(t);
    else upcoming.push(t);
  }
  return { overdue, today, upcoming, undated };
}

function fmtDate(iso) {
  return new Date(iso + "T12:00:00").toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
}
function fmtTime(hhmm) {
  const [h, m] = hhmm.split(":").map(Number);
  return new Date(2000, 0, 1, h, m).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
}

function TodoItem({ todo, overdue, onComplete, onDelete, onSaveDescription }) {
  const [expanded, setExpanded] = useState(false);
  const [draft, setDraft] = useState(todo.description || "");
  const commit = () => {
    const trimmed = draft.trim();
    if (trimmed !== (todo.description || "")) onSaveDescription(todo.id, trimmed);
  };
  return (
    <div style={{ borderTop: `1px solid ${T.line}`, padding: "11px 0" }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
        <button onClick={() => onComplete(todo.id)} aria-label="Mark done" title="Mark done" style={{
          flexShrink: 0, width: 20, height: 20, marginTop: 0, cursor: "pointer", borderRadius: 7, border: `1.5px solid ${T.lineStrong}`, background: "transparent",
        }} />
        <div onClick={() => { setDraft(todo.description || ""); setExpanded((e) => !e); }} style={{ flex: 1, minWidth: 0, cursor: "pointer" }}
          title={todo.description ? "View or edit notes" : "Add notes"}>
          <div style={{ fontSize: 14, color: T.text, lineHeight: 1.4 }}>{todo.text}</div>
          {!expanded && todo.description && (
            <div style={{ fontSize: 12.5, color: T.textMute, marginTop: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{todo.description.split("\n")[0]}</div>
          )}
        </div>
        <InboxLinkButton href={inboxLinkFrom(todo.description)} />
        {todo.recurrence && <Pill tone="info">↻ {RECURRENCE_LABELS[todo.recurrence]}</Pill>}
        {todo.due_date && (
          <span style={{ fontSize: 12.5, color: overdue ? T.bad : T.textMute, flexShrink: 0, fontVariantNumeric: "tabular-nums" }}>
            {fmtDate(todo.due_date.slice(0, 10))}{todo.due_time ? ` · ${fmtTime(todo.due_time)}` : ""}
          </span>
        )}
        <button onClick={() => onDelete(todo.id)} aria-label="Delete" title="Delete" style={{ fontSize: 13, color: T.textMute, cursor: "pointer", background: "none", border: "none", flexShrink: 0 }}>✕</button>
      </div>
      {expanded && (
        <div style={{ padding: "10px 0 0 32px", display: "grid", gap: 6 }}>
          <textarea autoFocus className="dg-input" rows={3} placeholder="Notes, instructions, or a link…" value={draft}
            onChange={(e) => setDraft(e.target.value)} onBlur={commit}
            onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) e.target.blur(); }} style={{ resize: "vertical" }} />
          {draft.trim() && <div style={{ fontSize: 12.5, lineHeight: 1.5, color: T.textDim }}>{linkify(draft)}</div>}
        </div>
      )}
    </div>
  );
}

const EMPTY_FORM = { text: "", due_date: "", due_time: "", recurrence: "", description: "" };

export default function TodoPanel() {
  const [todos, setTodos] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [more, setMore] = useState(false);
  const [saving, setSaving] = useState(false);
  const [query, setQuery] = useState("");

  const load = async () => {
    const r = await fetch(API("/dashboard/todos"));
    if (r.ok) setTodos(await r.json());
  };
  useEffect(() => { load(); }, []);

  const patch = (id, body) => fetch(API(`/dashboard/todos/${id}`), { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const complete = async (id) => {
    setTodos((p) => p.filter((t) => t.id !== id));
    await patch(id, { done: true });
    load(); // a recurring task comes back with its next date
  };
  const remove = async (id) => { setTodos((p) => p.filter((t) => t.id !== id)); await fetch(API(`/dashboard/todos/${id}`), { method: "DELETE" }); };
  const saveDescription = async (id, description) => { setTodos((p) => p.map((t) => (t.id === id ? { ...t, description } : t))); await patch(id, { description }); };

  const save = async () => {
    if (!form.text.trim()) return;
    setSaving(true);
    await fetch(API("/dashboard/todos"), {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: form.text.trim(), due_date: form.due_date || undefined, due_time: form.due_time || undefined,
        recurrence: form.recurrence || undefined, description: form.description.trim() || undefined,
      }),
    });
    setForm(EMPTY_FORM); setMore(false); setSaving(false); load();
  };

  const q = query.trim().toLowerCase();
  const filtered = (todos || []).filter((t) => !q || `${t.text} ${t.description || ""}`.toLowerCase().includes(q));
  const { overdue, today, upcoming, undated } = groupTodos(filtered);
  const all = groupTodos(todos || []);
  const groups = [
    { key: "overdue", title: "Overdue", items: overdue, tone: "bad" },
    { key: "today", title: "Today", items: today, tone: "info" },
    { key: "upcoming", title: "Upcoming", items: upcoming, tone: "neutral" },
    { key: "undated", title: "No due date", items: undated, tone: "neutral" },
  ];

  return (
    <div className="px-4 py-4 sm:px-8 sm:py-7" style={{ flex: 1, overflowY: "auto" }}>
      <div style={{ maxWidth: 960, margin: "0 auto", display: "grid", gap: 18 }}>
        <PageHeader title="To-Do" subtitle={todos ? `${todos.length} open task${todos.length !== 1 ? "s" : ""}` : "Loading…"} />

        <Card pad={0}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))" }}>
            {[["Overdue", all.overdue.length, all.overdue.length ? "bad" : undefined], ["Today", all.today.length], ["Upcoming", all.upcoming.length], ["No due date", all.undated.length]].map(([l, v, tone], i) => (
              <div key={l} style={{ padding: "16px 20px", borderLeft: i ? `1px solid ${T.line}` : "none" }}><Stat label={l} value={todos ? v : "–"} tone={tone} /></div>
            ))}
          </div>
        </Card>

        <Card>
          <div style={{ display: "flex", gap: 8 }}>
            <input style={inputStyle} placeholder="Add a task and press Enter…" value={form.text} aria-label="New task"
              onChange={(e) => setForm((f) => ({ ...f, text: e.target.value }))} onKeyDown={(e) => e.key === "Enter" && save()} />
            <button className="btn btn-secondary" onClick={() => setMore((m) => !m)}>{more ? "Fewer options" : "Date & repeat"}</button>
            <button className="btn btn-primary" onClick={save} disabled={saving || !form.text.trim()}>{saving ? "Saving…" : "Add"}</button>
          </div>
          {more && (
            <div style={{ display: "grid", gap: 10, marginTop: 12 }}>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 10 }}>
                <input type="date" style={{ ...inputStyle, colorScheme: "dark" }} value={form.due_date} aria-label="Due date" onChange={(e) => setForm((f) => ({ ...f, due_date: e.target.value }))} />
                <input type="time" style={{ ...inputStyle, colorScheme: "dark" }} value={form.due_time} aria-label="Due time" onChange={(e) => setForm((f) => ({ ...f, due_time: e.target.value }))} />
                <select style={inputStyle} value={form.recurrence} aria-label="Repeat" onChange={(e) => setForm((f) => ({ ...f, recurrence: e.target.value }))}>
                  <option value="">No repeat</option><option value="daily">Daily</option><option value="weekdays">Weekdays (Mon–Fri)</option>
                  <option value="weekly">Weekly</option><option value="monthly">Monthly</option>
                </select>
              </div>
              <textarea rows={2} style={{ ...inputStyle, resize: "vertical" }} placeholder="Notes, instructions, or a link (optional)" value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} />
            </div>
          )}
        </Card>

        <input style={{ ...inputStyle, maxWidth: 320 }} placeholder="Search tasks…" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Search tasks" />

        {todos === null ? <Loading /> : filtered.length === 0 ? (
          <Card><Empty>{todos.length ? "No tasks match your search." : "All clear. No open tasks."}</Empty></Card>
        ) : groups.filter((g) => g.items.length).map((g) => (
          <Card key={g.key} style={g.key === "overdue" ? { borderColor: "rgba(240,106,106,0.3)" } : undefined}>
            <SectionTitle title={g.title} right={<Pill tone={g.tone}>{g.items.length}</Pill>} style={{ marginBottom: 4 }} />
            {g.items.map((t) => (
              <TodoItem key={t.id} todo={t} overdue={g.key === "overdue"} onComplete={complete} onDelete={remove} onSaveDescription={saveDescription} />
            ))}
          </Card>
        ))}
      </div>
    </div>
  );
}
