import React, { useState, useEffect, useCallback } from "react";

// ── Active-prospect queue for the DM Follow-Up sequence ──────────────────────
// Same visual pattern as SequenceQueueModal.jsx (used by No Show/Cancellation/
// Reminders), but DM Follow-Up is keyed off sms_conversations + contact_id
// rather than appointment_reminders + numeric id, and its add/remove isn't a
// dedicated endpoint — it reuses the existing DM Reached checkbox action
// (POST /api/inbox/contact/{contact_id}/stage) since checking/unchecking that
// box already IS enroll/unenroll (see email_inbox.py's set_contact_stage).
// Dropping off this list on reply is automatic (dm_followup_sequence.py
// clears the row's cycle the moment a reply lands), not something this UI
// has to do — see GET /api/dialer/dm-followup-active's docstring.

async function setDmReached(contactId, checked) {
  return fetch(`/api/inbox/contact/${contactId}/stage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ stage: "dm_reached", checked }),
  });
}

function fmt(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

// ── Add / re-enroll sub-modal ─────────────────────────────────────────────────

function AddToDmFollowUpModal({ activeContactIds, onClose, onAdded }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [addingId, setAddingId] = useState(null);

  const search = useCallback(async (term) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: 20 });
      if (term) params.set("search", term);
      const res = await fetch(`/api/contacts?${params}`);
      const data = await res.json();
      setResults(data.contacts || []);
    } catch { setResults([]); }
    setLoading(false);
  }, []);

  useEffect(() => { search(""); }, [search]);

  async function add(contact) {
    setAddingId(contact.id);
    setErr("");
    const res = await setDmReached(contact.id, true);
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
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 16, fontWeight: 700, color: "#f0f4ff" }}>Add Prospect to DM Follow-Up</div>
          <button onClick={onClose} style={{ background: "none", border: "none", color: "#3a5a80", cursor: "pointer", fontSize: 14 }}>✕</button>
        </div>

        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80" }}>
          Same action as checking "DM Reached" on the contact in the Inbox — starts the 24h-silence countdown from now.
        </div>

        <input
          value={q}
          onChange={e => { setQ(e.target.value); search(e.target.value); }}
          placeholder="Search business, owner, phone…"
          className="dg-input"
          autoFocus
        />

        {err && <div style={{ fontSize: 11, color: "#e05555" }}>{err}</div>}

        <div style={{ overflowY: "auto", flex: 1, display: "flex", flexDirection: "column", gap: 6 }}>
          {loading && <div style={{ fontSize: 11, color: "#3a5a80" }}>Searching…</div>}
          {!loading && results.length === 0 && (
            <div style={{ fontSize: 11, color: "#3a5a80" }}>No contacts found.</div>
          )}
          {results.map(c => {
            const already = activeContactIds.has(c.id);
            return (
              <div key={c.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 10px",
                                        background: "#060a14", border: "0.5px solid #121e36", borderRadius: 6 }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12, color: "#f0f4ff", fontWeight: 600 }}>{c.business || "—"}</div>
                  <div style={{ fontSize: 11, color: "#7a94b8" }}>{c.owner || "—"} · {c.phone || "no phone on file"}</div>
                </div>
                <button
                  onClick={() => add(c)}
                  disabled={!c.phone || already || addingId === c.id}
                  className="btn btn-primary"
                  style={{ fontSize: 10, padding: "5px 10px", whiteSpace: "nowrap" }}
                >
                  {addingId === c.id ? "Adding…" : already ? "Already Active" : "+ Add"}
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ── Main modal ─────────────────────────────────────────────────────────────────

export default function DmFollowUpQueueModal({ onClose }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [err, setErr] = useState("");

  const fetchRows = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/dialer/dm-followup-active");
      const data = await res.json();
      setRows(Array.isArray(data) ? data : []);
    } catch { setRows([]); }
    setLoading(false);
  }, []);

  useEffect(() => { fetchRows(); }, [fetchRows]);

  async function remove(row) {
    const name = row.owner || row.business || row.phone;
    if (!window.confirm(`Remove ${name} from DM Follow-Up? This unchecks "DM Reached" for them — they won't auto re-enroll unless the box is checked again.`)) return;
    setBusyId(row.id);
    setErr("");
    const res = await setDmReached(row.contact_id, false);
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
              DM Follow-Up — Active Prospects
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

        <div style={{ margin: "10px 24px 0", fontSize: 11, color: "#3a5a80", flexShrink: 0 }}>
          Drops off this list automatically the moment a prospect replies — no action needed. "Remove" below is for pulling someone out manually before that happens.
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
              NOBODY CURRENTLY IN AN ACTIVE DM FOLLOW-UP COUNTDOWN
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
                    <td style={{ padding: "8px 10px", fontSize: 12, color: "#f0f4ff" }}>{r.owner || "—"}</td>
                    <td style={{ padding: "8px 10px", fontSize: 11, color: "#7a94b8" }}>{r.business || "—"}</td>
                    <td style={{ padding: "8px 10px", fontSize: 11, color: "#7a94b8" }}>{r.step_label}</td>
                    <td style={{ padding: "8px 10px", fontSize: 11, color: "#7a94b8" }}>{fmt(r.next_touch_due_at)}</td>
                    <td style={{ padding: "8px 10px", textAlign: "right" }}>
                      <button
                        onClick={() => remove(r)}
                        disabled={busyId === r.id}
                        className="btn btn-secondary"
                        style={{ fontSize: 10, padding: "5px 10px", color: "#e05555", whiteSpace: "nowrap" }}
                      >
                        {busyId === r.id ? "…" : "Remove"}
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
        <AddToDmFollowUpModal
          activeContactIds={new Set(rows.map(r => r.contact_id))}
          onClose={() => setShowAdd(false)}
          onAdded={fetchRows}
        />
      )}
    </div>
  );
}
