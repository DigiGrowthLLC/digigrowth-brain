import React, { useState, useEffect } from "react";

const API = (p) => `/api${p}`;

const RECURRENCE_LABELS = {
  daily:    "↻ daily",
  weekdays: "↻ weekdays",
  weekly:   "↻ weekly",
  monthly:  "↻ monthly",
};

const RECURRENCE_COLORS = {
  daily:    "#a080f0",
  weekdays: "#14c882",
  weekly:   "#3a7bd5",
  monthly:  "#f0a028",
};

function groupTodos(todos) {
  const todayStr = new Date().toISOString().slice(0, 10);
  const overdue = [], today = [], upcoming = [], undated = [];
  for (const t of todos) {
    if (!t.due_date) { undated.push(t); continue; }
    const d = t.due_date.slice(0, 10);
    if (d < todayStr)      overdue.push(t);
    else if (d === todayStr) today.push(t);
    else                    upcoming.push(t);
  }
  return { overdue, today, upcoming, undated };
}

function fmtDate(iso) {
  const d = new Date(iso + "T12:00:00");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function TodoItem({ todo, onComplete, onDelete }) {
  const [hovering, setHovering] = useState(false);
  const recColor = todo.recurrence ? RECURRENCE_COLORS[todo.recurrence] : null;

  return (
    <div
      onMouseEnter={() => setHovering(true)}
      onMouseLeave={() => setHovering(false)}
      style={{
        display: "flex", alignItems: "center", gap: 10,
        padding: "10px 14px", borderRadius: 10,
        background: hovering ? "rgba(58,123,213,0.05)" : "rgba(255,255,255,0.02)",
        transition: "background 0.12s",
      }}
    >
      {/* Checkbox */}
      <button
        onClick={() => onComplete(todo.id)}
        style={{
          flexShrink: 0, width: 17, height: 17, cursor: "pointer",
          border: "1px solid rgba(58,123,213,0.35)", borderRadius: 4,
          background: "transparent",
        }}
      />

      {/* Text */}
      <span style={{ flex: 1, fontSize: 13, color: "#8aaad0", lineHeight: 1.4 }}>
        {todo.text}
      </span>

      {/* Recurrence badge */}
      {todo.recurrence && (
        <span style={{
          fontFamily: "'Share Tech Mono', monospace", fontSize: 8,
          color: recColor, letterSpacing: "0.06em",
          background: `${recColor}18`, border: `1px solid ${recColor}40`,
          borderRadius: 4, padding: "2px 5px", flexShrink: 0,
        }}>
          {RECURRENCE_LABELS[todo.recurrence]}
        </span>
      )}

      {/* Due date */}
      {todo.due_date && (
        <span style={{
          fontFamily: "'Share Tech Mono', monospace", fontSize: 9,
          color: "#3a5a80", letterSpacing: "0.06em", flexShrink: 0,
        }}>
          {fmtDate(todo.due_date)}
        </span>
      )}

      {/* Delete */}
      <button
        onClick={() => onDelete(todo.id)}
        style={{
          fontSize: 10, color: hovering ? "#4a6a8a" : "#1e2f4a",
          cursor: "pointer", background: "none", border: "none",
          transition: "color 0.12s", flexShrink: 0,
        }}
      >
        ✕
      </button>
    </div>
  );
}

function SectionLabel({ label, color, count }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 8, marginTop: 4, marginBottom: 2,
      paddingLeft: 4,
    }}>
      <div style={{ width: 3, height: 12, borderRadius: 2, background: color }} />
      <span style={{
        fontFamily: "'Share Tech Mono', monospace", fontSize: 9,
        color, letterSpacing: "0.16em",
      }}>
        {label}
      </span>
      <span style={{
        fontFamily: "'Share Tech Mono', monospace", fontSize: 8,
        color: "#2a3a50", marginLeft: 2,
      }}>
        {count}
      </span>
    </div>
  );
}

export default function TodoPanel() {
  const [todos, setTodos] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ text: "", due_date: "", recurrence: "" });
  const [saving, setSaving] = useState(false);

  const load = async () => {
    const r = await fetch(API("/dashboard/todos"));
    if (r.ok) setTodos(await r.json());
  };

  useEffect(() => { load(); }, []);

  const complete = async (id) => {
    setTodos(prev => prev.filter(t => t.id !== id));
    await fetch(API(`/dashboard/todos/${id}`), {
      method: "PATCH", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ done: true }),
    });
    // Reload in case a recurring task was rescheduled
    load();
  };

  const remove = async (id) => {
    setTodos(prev => prev.filter(t => t.id !== id));
    await fetch(API(`/dashboard/todos/${id}`), { method: "DELETE" });
  };

  const save = async () => {
    if (!form.text.trim()) return;
    setSaving(true);
    await fetch(API("/dashboard/todos"), {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: form.text.trim(),
        due_date: form.due_date || undefined,
        recurrence: form.recurrence || undefined,
      }),
    });
    setForm({ text: "", due_date: "", recurrence: "" });
    setShowForm(false);
    setSaving(false);
    load();
  };

  const { overdue, today, upcoming, undated } = groupTodos(todos);
  const total = todos.length;

  return (
    <div style={{ flex: 1, overflowY: "auto", padding: "24px 28px", display: "flex", flexDirection: "column", gap: 0 }}>

      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
        <div>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 24, fontWeight: 700, color: "#f0f4ff", letterSpacing: "-0.02em" }}>
            To-Do
          </div>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80", letterSpacing: "0.14em", marginTop: 4 }}>
            {total} TASK{total !== 1 ? "S" : ""} REMAINING
          </div>
        </div>
        <button
          className="btn btn-primary"
          onClick={() => setShowForm(s => !s)}
          style={{ fontSize: 11, padding: "8px 18px", letterSpacing: "0.08em" }}
        >
          {showForm ? "CANCEL" : "+ ADD TASK"}
        </button>
      </div>

      {/* Add task form */}
      {showForm && (
        <div className="glass-card" style={{ padding: "18px 20px", marginBottom: 20, display: "flex", flexDirection: "column", gap: 12 }}>
          <input
            className="dg-input"
            placeholder="Task description…"
            value={form.text}
            onChange={e => setForm(f => ({ ...f, text: e.target.value }))}
            onKeyDown={e => e.key === "Enter" && save()}
            autoFocus
            style={{ fontSize: 13 }}
          />
          <div style={{ display: "flex", gap: 10 }}>
            <input
              type="date"
              className="dg-input"
              value={form.due_date}
              onChange={e => setForm(f => ({ ...f, due_date: e.target.value }))}
              style={{ flex: 1, fontSize: 12, colorScheme: "dark" }}
            />
            <select
              className="dg-input"
              value={form.recurrence}
              onChange={e => setForm(f => ({ ...f, recurrence: e.target.value }))}
              style={{ flex: 1, fontSize: 12 }}
            >
              <option value="">No repeat</option>
              <option value="daily">Daily</option>
              <option value="weekdays">Weekdays (Mon–Fri)</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
            </select>
          </div>
          <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
            <button className="btn btn-secondary" onClick={() => setShowForm(false)} style={{ fontSize: 11 }}>CANCEL</button>
            <button
              className="btn btn-primary"
              onClick={save}
              disabled={saving || !form.text.trim()}
              style={{ fontSize: 11 }}
            >
              {saving ? "SAVING…" : "SAVE TASK"}
            </button>
          </div>
        </div>
      )}

      {/* Task list */}
      <div className="glass-card" style={{ padding: "12px 8px", display: "flex", flexDirection: "column", gap: 2 }}>

        {total === 0 && (
          <div style={{
            padding: "40px 20px", textAlign: "center",
            fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52", letterSpacing: "0.16em",
          }}>
            ALL CLEAR — NO PENDING TASKS
          </div>
        )}

        {overdue.length > 0 && (
          <>
            <SectionLabel label="OVERDUE" color="#dc3c3c" count={overdue.length} />
            {overdue.map(t => (
              <div key={t.id} style={{ borderLeft: "3px solid rgba(220,60,60,0.4)", marginLeft: 4, borderRadius: "0 8px 8px 0" }}>
                <TodoItem todo={t} onComplete={complete} onDelete={remove} />
              </div>
            ))}
          </>
        )}

        {today.length > 0 && (
          <>
            <SectionLabel label="TODAY" color="#3a7bd5" count={today.length} />
            {today.map(t => (
              <div key={t.id} style={{ borderLeft: "3px solid rgba(58,123,213,0.4)", marginLeft: 4, borderRadius: "0 8px 8px 0" }}>
                <TodoItem todo={t} onComplete={complete} onDelete={remove} />
              </div>
            ))}
          </>
        )}

        {upcoming.length > 0 && (
          <>
            <SectionLabel label="UPCOMING" color="#4a6a8a" count={upcoming.length} />
            {upcoming.map(t => (
              <div key={t.id} style={{ borderLeft: "3px solid rgba(74,106,138,0.25)", marginLeft: 4, borderRadius: "0 8px 8px 0" }}>
                <TodoItem todo={t} onComplete={complete} onDelete={remove} />
              </div>
            ))}
          </>
        )}

        {undated.length > 0 && (
          <>
            <SectionLabel label="NO DUE DATE" color="#2a4a7a" count={undated.length} />
            {undated.map(t => (
              <div key={t.id} style={{ marginLeft: 4 }}>
                <TodoItem todo={t} onComplete={complete} onDelete={remove} />
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
}
