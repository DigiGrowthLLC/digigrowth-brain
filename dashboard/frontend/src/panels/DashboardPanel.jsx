import React, { useState, useEffect, useRef } from "react";

const API = (path) => `/api${path}`;

function fmt(ts) {
  if (!ts) return "";
  const d = new Date(ts);
  const now = new Date();
  const diff = now - d;
  if (diff < 60000) return "just now";
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

const AGENT_ICONS = { leadgen: "🔍", dialer: "📞", sms: "💬", system: "⚙️" };
const GRADE_COLORS = { A: "text-green-400", B: "text-blue-400", C: "text-yellow-400", D: "text-gray-400" };

function StatCard({ label, value, sub, accent = "indigo" }) {
  const colors = {
    indigo: "border-indigo-500/30 bg-indigo-500/5",
    green:  "border-green-500/30 bg-green-500/5",
    blue:   "border-blue-500/30 bg-blue-500/5",
    yellow: "border-yellow-500/30 bg-yellow-500/5",
  };
  return (
    <div className={`rounded-xl border p-4 ${colors[accent]}`}>
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className="text-2xl font-bold text-white">{value ?? "—"}</div>
      {sub != null && <div className="text-xs text-gray-500 mt-0.5">{sub}</div>}
    </div>
  );
}

// ── To-Do List ────────────────────────────────────────────────────────────────

function TodoList() {
  const [todos, setTodos] = useState([]);
  const [draft, setDraft]   = useState("");
  const inputRef = useRef(null);

  const load = async () => {
    const res = await fetch(API("/dashboard/todos"));
    if (res.ok) setTodos(await res.json());
  };

  useEffect(() => { load(); }, []);

  const add = async () => {
    if (!draft.trim()) return;
    await fetch(API("/dashboard/todos"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: draft.trim() }),
    });
    setDraft("");
    load();
  };

  const toggle = async (id, done) => {
    await fetch(API(`/dashboard/todos/${id}`), {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ done: !done }),
    });
    load();
  };

  const remove = async (id) => {
    await fetch(API(`/dashboard/todos/${id}`), { method: "DELETE" });
    load();
  };

  const pending = todos.filter((t) => !t.done);
  const done    = todos.filter((t) => t.done);

  return (
    <div className="flex flex-col h-full">
      <div className="flex gap-2 mb-3">
        <input
          ref={inputRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && add()}
          placeholder="Add a task…"
          className="flex-1 bg-gray-800 text-sm text-gray-100 placeholder-gray-600 rounded-lg px-3 py-2 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        />
        <button
          onClick={add}
          className="px-3 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm transition-colors"
        >
          Add
        </button>
      </div>

      <div className="flex-1 overflow-y-auto space-y-1.5">
        {pending.map((t) => (
          <div key={t.id} className="flex items-start gap-2 group">
            <button
              onClick={() => toggle(t.id, t.done)}
              className="mt-0.5 w-4 h-4 rounded border border-gray-600 hover:border-indigo-400 shrink-0 transition-colors"
            />
            <span className="flex-1 text-sm text-gray-200">{t.text}</span>
            <button
              onClick={() => remove(t.id)}
              className="text-gray-700 hover:text-red-400 text-xs opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
            >
              ✕
            </button>
          </div>
        ))}

        {done.length > 0 && (
          <>
            <div className="text-xs text-gray-700 pt-2 pb-1">Done</div>
            {done.map((t) => (
              <div key={t.id} className="flex items-start gap-2 group">
                <button
                  onClick={() => toggle(t.id, t.done)}
                  className="mt-0.5 w-4 h-4 rounded border border-gray-700 bg-gray-700 shrink-0"
                >
                  <span className="block text-[9px] text-gray-400 leading-none text-center">✓</span>
                </button>
                <span className="flex-1 text-sm text-gray-600 line-through">{t.text}</span>
                <button
                  onClick={() => remove(t.id)}
                  className="text-gray-700 hover:text-red-400 text-xs opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
                >
                  ✕
                </button>
              </div>
            ))}
          </>
        )}

        {todos.length === 0 && (
          <div className="text-sm text-gray-600 pt-2">No tasks yet.</div>
        )}
      </div>
    </div>
  );
}

// ── Main Panel ────────────────────────────────────────────────────────────────

export default function DashboardPanel() {
  const [period, setPeriod]         = useState("day");
  const [stats, setStats]           = useState(null);
  const [agentMsgs, setAgentMsgs]   = useState([]);
  const [clientMsgs, setClientMsgs] = useState([]);

  const load = async (p = period) => {
    const [sRes, aRes, cRes] = await Promise.all([
      fetch(API(`/dashboard/summary?period=${p}`)),
      fetch(API("/dashboard/agent-messages")),
      fetch(API("/dashboard/client-messages")),
    ]);
    if (sRes.ok) setStats(await sRes.json());
    if (aRes.ok) setAgentMsgs(await aRes.json());
    if (cRes.ok) setClientMsgs(await cRes.json());
  };

  useEffect(() => { load(period); }, [period]);
  useEffect(() => {
    const id = setInterval(() => load(period), 30000);
    return () => clearInterval(id);
  }, [period]);

  const markRead = async (id) => {
    await fetch(API(`/dashboard/agent-messages/${id}/read`), { method: "POST" });
    setAgentMsgs((prev) => prev.map((m) => m.id === id ? { ...m, read: true } : m));
  };

  const calling  = stats?.calling  ?? {};
  const sms      = stats?.sms      ?? {};
  const contacts = stats?.contacts ?? {};
  const unread   = agentMsgs.filter((m) => !m.read).length;

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Good morning</h1>
          <p className="text-sm text-gray-500 mt-0.5">Here's what's happening at DigiGrowth.</p>
        </div>
        <div className="flex bg-gray-800 rounded-lg p-0.5 text-sm">
          {["day", "week", "month"].map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-3 py-1.5 rounded-md transition-colors capitalize ${
                period === p ? "bg-indigo-600 text-white" : "text-gray-400 hover:text-white"
              }`}
            >
              {p === "day" ? "Today" : p === "week" ? "This Week" : "This Month"}
            </button>
          ))}
        </div>
      </div>

      {/* Calling Stats */}
      <section>
        <div className="text-xs text-gray-500 uppercase tracking-wide mb-2">Cold Calling</div>
        <div className="grid grid-cols-4 gap-3">
          <StatCard label="Calls Made"  value={calling.calls_made}  accent="indigo" />
          <StatCard label="DMs Reached" value={calling.dms_reached} accent="blue" />
          <StatCard
            label="Reach Rate"
            value={calling.calls_made > 0 ? `${calling.reach_rate}%` : "—"}
            accent="yellow"
          />
          <StatCard label="Appointments Booked" value={calling.booked} accent="green" />
        </div>
      </section>

      {/* SMS + Contacts Stats */}
      <section>
        <div className="text-xs text-gray-500 uppercase tracking-wide mb-2">SMS & Contacts</div>
        <div className="grid grid-cols-5 gap-3">
          <StatCard label="Active Convos"   value={sms.active}        accent="indigo" />
          <StatCard label="Booked via SMS"  value={sms.booked}        accent="green" />
          <StatCard label="Messages"        value={sms.messages}      accent="blue" />
          <StatCard label="Total Contacts"  value={contacts.total}    accent="indigo" />
          <StatCard
            label="New Contacts"
            value={contacts.new}
            sub={`this ${period}`}
            accent="yellow"
          />
        </div>
      </section>

      {/* Bottom 3-column layout */}
      <div className="grid grid-cols-3 gap-5" style={{ minHeight: 320 }}>

        {/* Agent Messages */}
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-4 flex flex-col">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm font-semibold text-white">Agent Activity</span>
            {unread > 0 && (
              <span className="text-xs bg-indigo-600 text-white px-2 py-0.5 rounded-full">
                {unread} new
              </span>
            )}
          </div>
          <div className="flex-1 overflow-y-auto space-y-2">
            {agentMsgs.length === 0 && (
              <div className="text-sm text-gray-600">No messages yet.</div>
            )}
            {agentMsgs.map((m) => (
              <div
                key={m.id}
                onClick={() => !m.read && markRead(m.id)}
                className={`rounded-lg px-3 py-2 text-sm cursor-pointer transition-colors ${
                  m.read ? "bg-gray-800/50" : "bg-gray-800 border border-indigo-500/20"
                }`}
              >
                <div className="flex items-center gap-1.5 mb-0.5">
                  <span>{AGENT_ICONS[m.agent] ?? "🤖"}</span>
                  <span className="text-gray-400 text-xs capitalize">{m.agent}</span>
                  <span className="ml-auto text-xs text-gray-600">{fmt(m.created_at)}</span>
                </div>
                <div className={m.read ? "text-gray-500" : "text-gray-200"}>{m.message}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Client Messages Needing Reply */}
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-4 flex flex-col">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm font-semibold text-white">Needs Reply</span>
            {clientMsgs.length > 0 && (
              <span className="text-xs bg-yellow-600 text-white px-2 py-0.5 rounded-full">
                {clientMsgs.length}
              </span>
            )}
          </div>
          <div className="flex-1 overflow-y-auto space-y-2">
            {clientMsgs.length === 0 && (
              <div className="text-sm text-gray-600">All caught up.</div>
            )}
            {clientMsgs.map((m) => (
              <div
                key={m.phone}
                className="bg-gray-800 rounded-lg px-3 py-2 border-l-2 border-yellow-500"
              >
                <div className="flex items-center justify-between mb-0.5">
                  <span className="text-sm font-medium text-white truncate">
                    {m.business || m.owner || m.phone}
                  </span>
                  <div className="flex items-center gap-1.5 shrink-0 ml-2">
                    {m.grade && (
                      <span className={`text-xs font-bold ${GRADE_COLORS[m.grade] ?? "text-gray-400"}`}>
                        {m.grade}
                      </span>
                    )}
                    <span className="text-xs text-gray-600">{fmt(m.updated_at)}</span>
                  </div>
                </div>
                <div className="text-xs text-gray-400 truncate">{m.last_message}</div>
                <div className="text-xs text-gray-600 mt-0.5">{m.phone}</div>
              </div>
            ))}
          </div>
        </div>

        {/* To-Do List */}
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-4 flex flex-col">
          <div className="text-sm font-semibold text-white mb-3">To-Do</div>
          <TodoList />
        </div>

      </div>
    </div>
  );
}
