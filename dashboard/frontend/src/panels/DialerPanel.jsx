import React, { useState, useEffect } from "react";

const API = (path) => `/api${path}`;

const DISPO_COLORS = {
  "Appointment Booked": "text-green-400",
  "Follow Up":          "text-blue-400",
  "Send Info":          "text-indigo-400",
  "Not Interested":     "text-red-400",
  "No Answer":          "text-gray-400",
  "Voicemail":          "text-yellow-400",
  "SMS Handoff":        "text-purple-400",
};

function StatCard({ label, value, sub }) {
  return (
    <div className="bg-gray-800 rounded-xl p-4">
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className="text-2xl font-bold text-white">{value ?? "—"}</div>
      {sub && <div className="text-xs text-gray-500 mt-0.5">{sub}</div>}
    </div>
  );
}

function fmt(ts) {
  if (!ts) return "";
  return new Date(ts).toLocaleString("en-US", {
    month: "short", day: "numeric",
    hour: "numeric", minute: "2-digit",
  });
}

export default function DialerPanel() {
  const [data, setData] = useState(null);

  const load = async () => {
    try {
      const res = await fetch(API("/dialer/stats"));
      if (res.ok) setData(await res.json());
    } catch {}
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, []);

  const session  = data?.session  ?? {};
  const history  = data?.history  ?? {};
  const recent   = history.recent ?? [];
  const byDispo  = history.by_disposition ?? [];

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white">Parallel Dialer</h2>
        <div className="flex items-center gap-2">
          <span
            className={`w-2 h-2 rounded-full ${session.active ? "bg-green-400 animate-pulse" : "bg-gray-600"}`}
          />
          <span className="text-sm text-gray-400">
            {session.active ? "Session Active" : "Idle — run python run.py to start"}
          </span>
        </div>
      </div>

      {/* Live Session Stats */}
      <section>
        <div className="text-xs text-gray-500 uppercase tracking-wide mb-3">
          {session.active ? "Live Session" : "Last Session"}
        </div>
        <div className="grid grid-cols-4 gap-3">
          <StatCard label="Calls Made"  value={session.calls_made}  />
          <StatCard label="DMs Reached" value={session.dms_reached} />
          <StatCard
            label="Remaining"
            value={session.remaining}
            sub={session.total_leads ? `of ${session.total_leads} total` : null}
          />
          <StatCard
            label="Reach Rate"
            value={session.calls_made > 0 ? `${session.reach_rate}%` : "—"}
          />
        </div>
      </section>

      <div className="grid grid-cols-2 gap-6">
        {/* Disposition breakdown */}
        <section className="bg-gray-800 rounded-xl p-4">
          <div className="text-xs text-gray-500 uppercase tracking-wide mb-3">
            All-Time Breakdown ({history.total_calls ?? 0} calls)
          </div>
          {byDispo.length === 0 ? (
            <div className="text-sm text-gray-600">No call data yet.</div>
          ) : (
            <div className="space-y-2">
              {byDispo.map((d) => {
                const pct = history.total_calls
                  ? Math.round((d.cnt / history.total_calls) * 100)
                  : 0;
                return (
                  <div key={d.disposition}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className={DISPO_COLORS[d.disposition] ?? "text-gray-300"}>
                        {d.disposition}
                      </span>
                      <span className="text-gray-400">{d.cnt} ({pct}%)</span>
                    </div>
                    <div className="h-1 bg-gray-700 rounded-full">
                      <div
                        className="h-1 bg-indigo-500 rounded-full"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
          <div className="mt-4 pt-3 border-t border-gray-700 flex gap-4 text-sm">
            <div>
              <span className="text-gray-500">Booked: </span>
              <span className="text-green-400 font-medium">{history.total_booked ?? 0}</span>
            </div>
            <div>
              <span className="text-gray-500">Reached: </span>
              <span className="text-blue-400 font-medium">{history.total_reached ?? 0}</span>
            </div>
          </div>
        </section>

        {/* Recent calls */}
        <section className="bg-gray-800 rounded-xl p-4">
          <div className="text-xs text-gray-500 uppercase tracking-wide mb-3">Recent Calls</div>
          {recent.length === 0 ? (
            <div className="text-sm text-gray-600">No calls logged yet.</div>
          ) : (
            <div className="space-y-2 overflow-y-auto max-h-64">
              {recent.map((r, i) => (
                <div key={i} className="flex items-start justify-between text-sm py-1 border-b border-gray-700">
                  <div>
                    <div className="text-white font-medium">
                      {r.business || r.owner || r.phone || "Unknown"}
                    </div>
                    <div className="text-xs text-gray-500">{fmt(r.started_at)}</div>
                    {r.notes && (
                      <div className="text-xs text-gray-500 mt-0.5 italic">{r.notes}</div>
                    )}
                  </div>
                  <span className={`text-xs font-medium ${DISPO_COLORS[r.disposition] ?? "text-gray-400"}`}>
                    {r.disposition ?? "—"}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      {/* Setup reminder */}
      {!session.active && (
        <div className="bg-gray-800 rounded-xl p-4 text-sm text-gray-500 border border-gray-700">
          <span className="text-gray-300 font-medium">To start a session:</span> open a terminal,
          cd into <code className="text-indigo-400">parallel-dialer/</code> and run{" "}
          <code className="text-indigo-400">python run.py</code>. Live stats will appear here automatically.
        </div>
      )}
    </div>
  );
}
