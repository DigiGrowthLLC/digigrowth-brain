import React, { useState, useEffect, useCallback } from "react";

// ── Shared queue view for the three appointment-lifecycle sequences ──────────
// (No Show recovery, Cancellation recovery, Appointment Reminders) — same
// pattern as NewsletterQueueModal.jsx (list + row-click drawer-free remove +
// a search-and-add sub-modal), but backed by
// GET/POST /api/appointment-reminders/sequence/{sequence}[/add|/remove]
// instead of the newsletter queue endpoints. "sequence" is one of
// "no_show" | "cancel" | "reminder".

const SEQUENCE_COPY = {
  no_show: {
    title: "No Show Recovery — Active Prospects",
    emptyLabel: "NOBODY CURRENTLY IN THE NO-SHOW SEQUENCE",
    removeLabel: "Stop Sequence",
    removeConfirm: (name) => `Stop the no-show sequence for ${name}? They'll receive no further touches unless re-added.`,
    addTitle: "Add Prospect to No-Show Sequence",
    addHint: "Only appointments not already mid no-show-sequence are shown. Adding restarts the 4-touch drip from Touch 1.",
  },
  cancel: {
    title: "Cancellation Recovery — Active Prospects",
    emptyLabel: "NOBODY CURRENTLY IN THE CANCELLATION SEQUENCE",
    removeLabel: "Stop Sequence",
    removeConfirm: (name) => `Stop the cancellation-recovery sequence for ${name}? They'll receive no further touches unless re-added.`,
    addTitle: "Add Prospect to Cancellation Sequence",
    addHint: "Only appointments not already mid cancellation-sequence are shown. Adding restarts the 4-touch drip from Touch 1 and marks the appointment canceled.",
  },
  reminder: {
    title: "Appointment Reminders — Upcoming",
    emptyLabel: "NO UPCOMING APPOINTMENTS WITH REMINDERS ACTIVE",
    removeLabel: "Stop Reminders",
    removeConfirm: (name) => `Stop future 24h/6h/1h reminders for ${name}? The appointment itself is unaffected.`,
    addTitle: "Re-Arm Reminders for an Appointment",
    addHint: "Only future, scheduled appointments are shown. Adding resets the 24h/6h/1h windows as if just booked.",
  },
};

function fmt(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

// ── Add / re-enroll sub-modal ─────────────────────────────────────────────────

function AddToSequenceModal({ sequence, activeIds, onClose, onAdded }) {
  const copy = SEQUENCE_COPY[sequence];
  const [q, setQ] = useState("");
  const [all, setAll] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [addingId, setAddingId] = useState(null);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const res = await fetch("/api/appointment-reminders?status=all");
        const data = await res.json();
        setAll(Array.isArray(data) ? data : []);
      } catch { setAll([]); }
      setLoading(false);
    })();
  }, []);

  const now = Date.now();
  const candidates = all.filter(a => {
    if (activeIds.has(a.id)) return false;
    if (sequence === "reminder" && (a.status !== "scheduled" || new Date(a.appointment_at).getTime() <= now)) return false;
    if (!q.trim()) return true;
    const hay = `${a.prospect_name || ""} ${a.business || ""} ${a.owner || ""}`.toLowerCase();
    return hay.includes(q.trim().toLowerCase());
  });

  async function add(appt) {
    setAddingId(appt.id);
    setErr("");
    const res = await fetch(`/api/appointment-reminders/${appt.id}/sequence/${sequence}/add`, { method: "POST" });
    if (res.ok) {
      onAdded();
      onClose();
    } else {
      const d = await res.json().catch(() => ({}));
      setErr(d.detail || "Failed to add.");
    }
    setAddingId(null);
  }

  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 70, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ position: "absolute", inset: 0, background: "rgba(4,8,16,0.85)" }} onClick={onClose} />
      <div style={{ position: "relative", background: "#0a1020", border: "0.5px solid #1a2540", borderRadius: 8,
                    width: 480, maxHeight: "80vh", display: "flex", flexDirection: "column", padding: "24px 28px", gap: 14 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 16, fontWeight: 700, color: "#f0f4ff" }}>{copy.addTitle}</div>
          <button onClick={onClose} style={{ background: "none", border: "none", color: "#3a5a80", cursor: "pointer", fontSize: 14 }}>✕</button>
        </div>

        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80" }}>{copy.addHint}</div>

        <input
          value={q}
          onChange={e => setQ(e.target.value)}
          placeholder="Search prospect, business…"
          className="dg-input"
          autoFocus
        />

        {err && <div style={{ fontSize: 11, color: "#e05555" }}>{err}</div>}

        <div style={{ overflowY: "auto", flex: 1, display: "flex", flexDirection: "column", gap: 6 }}>
          {loading && <div style={{ fontSize: 11, color: "#3a5a80" }}>Loading…</div>}
          {!loading && candidates.length === 0 && (
            <div style={{ fontSize: 11, color: "#3a5a80" }}>No matching appointments.</div>
          )}
          {candidates.map(a => (
            <div key={a.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 10px",
                                      background: "#060a14", border: "0.5px solid #121e36", borderRadius: 6 }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 12, color: "#f0f4ff", fontWeight: 600 }}>{a.prospect_name || a.owner || "—"}</div>
                <div style={{ fontSize: 11, color: "#7a94b8" }}>{a.business || "—"} · {fmt(a.appointment_at)}</div>
              </div>
              <button
                onClick={() => add(a)}
                disabled={addingId === a.id}
                className="btn btn-primary"
                style={{ fontSize: 10, padding: "5px 10px", whiteSpace: "nowrap" }}
              >
                {addingId === a.id ? "Adding…" : "+ Add"}
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Main modal ─────────────────────────────────────────────────────────────────

export default function SequenceQueueModal({ sequence, onClose }) {
  const copy = SEQUENCE_COPY[sequence];
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [err, setErr] = useState("");

  const fetchRows = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/appointment-reminders/sequence/${sequence}`);
      const data = await res.json();
      setRows(Array.isArray(data) ? data : []);
    } catch { setRows([]); }
    setLoading(false);
  }, [sequence]);

  useEffect(() => { fetchRows(); }, [fetchRows]);

  async function remove(row) {
    const name = row.prospect_name || row.business || `#${row.id}`;
    if (!window.confirm(copy.removeConfirm(name))) return;
    setBusyId(row.id);
    setErr("");
    const res = await fetch(`/api/appointment-reminders/${row.id}/sequence/${sequence}/remove`, { method: "POST" });
    if (res.ok) fetchRows();
    else { const d = await res.json().catch(() => ({})); setErr(d.detail || "Failed to remove."); }
    setBusyId(null);
  }

  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 60, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ position: "absolute", inset: 0, background: "rgba(4,8,16,0.85)" }} onClick={onClose} />
      <div style={{ position: "relative", background: "#0a1020", border: "0.5px solid #1a2540", borderRadius: 8,
                    width: "min(900px, 92vw)", maxHeight: "85vh", display: "flex", flexDirection: "column" }}>

        <div style={{ padding: "18px 24px", borderBottom: "0.5px solid #1a2540",
                      display: "flex", alignItems: "center", gap: 16 }}>
          <div>
            <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 16, fontWeight: 700, color: "#f0f4ff" }}>
              {copy.title}
            </div>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80",
                          letterSpacing: "0.18em", marginTop: 2 }}>
              {rows.length.toLocaleString()} ACTIVE
            </div>
          </div>
          <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
            <button onClick={() => setShowAdd(true)} className="btn btn-primary" style={{ whiteSpace: "nowrap" }}>
              + Add Prospect
            </button>
            <button onClick={onClose} style={{ background: "none", border: "none", color: "#3a5a80", cursor: "pointer", fontSize: 16 }}>✕</button>
          </div>
        </div>

        {err && (
          <div style={{ margin: "10px 24px 0", fontSize: 11, color: "#e05555", flexShrink: 0 }}>{err}</div>
        )}

        <div style={{ flex: 1, overflowY: "auto", padding: "14px 24px 20px" }}>
          {loading ? (
            <div style={{ padding: "30px 0", textAlign: "center", fontSize: 11, color: "#3a5a80" }}>Loading…</div>
          ) : rows.length === 0 ? (
            <div style={{ padding: "30px 0", textAlign: "center", fontFamily: "'Share Tech Mono', monospace",
                          fontSize: 11, color: "#3a5a80", letterSpacing: "0.18em" }}>
              {copy.emptyLabel}
            </div>
          ) : (
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ borderBottom: "0.5px solid #1a2540" }}>
                  {["Prospect", "Business", "Step", "Next Touch Due", ""].map(h => (
                    <th key={h} style={{
                      padding: "6px 10px", textAlign: "left",
                      fontFamily: "'Share Tech Mono', monospace", fontSize: 9, fontWeight: 600,
                      letterSpacing: "0.18em", color: "#2a4a7a", textTransform: "uppercase",
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map(r => (
                  <tr key={r.id} style={{ borderBottom: "0.5px solid #121e36" }}>
                    <td style={{ padding: "8px 10px", fontSize: 12, color: "#f0f4ff" }}>{r.prospect_name || "—"}</td>
                    <td style={{ padding: "8px 10px", fontSize: 11, color: "#7a94b8" }}>{r.business || r.owner || "—"}</td>
                    <td style={{ padding: "8px 10px", fontSize: 11, color: "#7a94b8" }}>{r.step_label}</td>
                    <td style={{ padding: "8px 10px", fontSize: 11, color: "#7a94b8" }}>{fmt(r.next_touch_due_at)}</td>
                    <td style={{ padding: "8px 10px", textAlign: "right" }}>
                      <button
                        onClick={() => remove(r)}
                        disabled={busyId === r.id}
                        className="btn btn-secondary"
                        style={{ fontSize: 10, padding: "5px 10px", color: "#e05555", whiteSpace: "nowrap" }}
                      >
                        {busyId === r.id ? "…" : copy.removeLabel}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {showAdd && (
        <AddToSequenceModal
          sequence={sequence}
          activeIds={new Set(rows.map(r => r.id))}
          onClose={() => setShowAdd(false)}
          onAdded={fetchRows}
        />
      )}
    </div>
  );
}
