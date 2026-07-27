import React, { useState, useEffect, useCallback } from "react";

const STATUS_TABS = [
  { value: "",        label: "ALL" },
  { value: "queued",  label: "QUEUED" },
  { value: "sent",    label: "SENT" },
  { value: "failed",  label: "FAILED" },
];

const STATUS_BADGE = { queued: "badge-blue", sent: "badge-green", failed: "badge-red" };

function fmt(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

// ── Add Prospect sub-modal ────────────────────────────────────────────────────

function AddProspectModal({ onClose, onAdded }) {
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
    const res = await fetch("/api/newsletter/queue", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ contact_id: contact.id }),
    });
    if (res.ok) {
      onAdded();
      onClose();
    } else {
      const d = await res.json().catch(() => ({}));
      setErr(d.detail || "Failed to add prospect.");
    }
    setAddingId(null);
  }

  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 70, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ position: "absolute", inset: 0, background: "rgba(4,8,16,0.85)" }} onClick={onClose} />
      <div style={{ position: "relative", background: "#0a1020", border: "0.5px solid #1a2540", borderRadius: 8,
                    width: 480, maxHeight: "80vh", display: "flex", flexDirection: "column", padding: "24px 28px", gap: 14 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 16, fontWeight: 700, color: "#f0f4ff" }}>Add Prospect to Queue</div>
          <button onClick={onClose} style={{ background: "none", border: "none", color: "#3a5a80", cursor: "pointer", fontSize: 14 }}>✕</button>
        </div>

        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80" }}>
          Uses the most recently approved newsletter draft as the template.
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
          {results.map(c => (
            <div key={c.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 10px",
                                      background: "#060a14", border: "0.5px solid #121e36", borderRadius: 6 }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 12, color: "#f0f4ff", fontWeight: 600 }}>{c.business || "—"}</div>
                <div style={{ fontSize: 11, color: "#7a94b8" }}>{c.owner || "—"} · {c.email || "no email on file"}</div>
              </div>
              <button
                onClick={() => add(c)}
                disabled={!c.email || addingId === c.id}
                className="btn btn-primary"
                style={{ fontSize: 10, padding: "5px 10px", whiteSpace: "nowrap" }}
              >
                {addingId === c.id ? "Adding…" : "+ Add"}
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Edit drawer ────────────────────────────────────────────────────────────────

function QueueItemDrawer({ item, onClose, onChanged }) {
  const [email, setEmail] = useState(item.email);
  const [subject, setSubject] = useState(item.subject);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  async function save(extra = {}) {
    setSaving(true);
    setErr("");
    const res = await fetch(`/api/newsletter/queue/${item.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, subject, ...extra }),
    });
    if (res.ok) { onChanged(); onClose(); }
    else { const d = await res.json().catch(() => ({})); setErr(d.detail || "Failed to save."); }
    setSaving(false);
  }

  async function remove() {
    if (!window.confirm(`Remove ${item.owner || item.email} from the newsletter queue?`)) return;
    setSaving(true);
    const res = await fetch(`/api/newsletter/queue/${item.id}`, { method: "DELETE" });
    if (res.ok) { onChanged(); onClose(); }
    else { const d = await res.json().catch(() => ({})); setErr(d.detail || "Failed to remove."); setSaving(false); }
  }

  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 65, display: "flex", justifyContent: "flex-end" }}>
      <div style={{ position: "absolute", inset: 0, background: "rgba(4,8,16,0.7)" }} onClick={onClose} />
      <div style={{ position: "relative", background: "#0a1020", borderLeft: "0.5px solid #1a2540",
                    width: 420, height: "100%", overflowY: "auto", padding: "24px 28px",
                    display: "flex", flexDirection: "column", gap: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 16, fontWeight: 700, color: "#f0f4ff" }}>
            Queue Item #{item.id}
          </div>
          <button onClick={onClose} style={{ background: "none", border: "none", color: "#3a5a80", cursor: "pointer", fontSize: 14 }}>✕</button>
        </div>

        <div>
          <span className={`badge ${STATUS_BADGE[item.status] || "badge-gray"}`}>{item.status.toUpperCase()}</span>
          {item.error && <div style={{ marginTop: 8, fontSize: 11, color: "#e05555" }}>{item.error}</div>}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <label style={{ fontSize: 10, color: "#3a5a80", letterSpacing: "0.1em" }}>RECIPIENT</label>
          <div style={{ fontSize: 12, color: "#f0f4ff" }}>{item.owner || "—"} · {item.business || "—"}</div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <label style={{ fontSize: 10, color: "#3a5a80", letterSpacing: "0.1em" }}>EMAIL</label>
          <input value={email} onChange={e => setEmail(e.target.value)} className="dg-input"
            disabled={item.status === "sent"} />
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <label style={{ fontSize: 10, color: "#3a5a80", letterSpacing: "0.1em" }}>SUBJECT</label>
          <input value={subject} onChange={e => setSubject(e.target.value)} className="dg-input"
            disabled={item.status === "sent"} />
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <label style={{ fontSize: 10, color: "#3a5a80", letterSpacing: "0.1em" }}>QUEUED</label>
          <div style={{ fontSize: 12, color: "#7a94b8" }}>{fmt(item.queued_at)}</div>
        </div>

        {err && <div style={{ fontSize: 11, color: "#e05555" }}>{err}</div>}

        {item.status !== "sent" && (
          <div style={{ display: "flex", gap: 8, marginTop: "auto", paddingTop: 12, borderTop: "0.5px solid #1a2540" }}>
            <button onClick={() => save()} disabled={saving} className="btn btn-primary" style={{ flex: 1 }}>
              {saving ? "Saving…" : "Save"}
            </button>
            {item.status === "failed" && (
              <button onClick={() => save({ status: "queued" })} disabled={saving} className="btn btn-secondary">
                Retry
              </button>
            )}
            <button onClick={remove} disabled={saving} className="btn btn-secondary" style={{ color: "#e05555" }}>
              Remove
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main modal ─────────────────────────────────────────────────────────────────

export default function NewsletterQueueModal({ onClose }) {
  const [status, setStatus] = useState("");
  const [queue, setQueue] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [showAdd, setShowAdd] = useState(false);
  const [paused, setPaused] = useState(false);
  const [pauseBusy, setPauseBusy] = useState(false);

  const fetchQueue = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams({ limit: 200 });
    if (status) params.set("status", status);
    try {
      const res = await fetch(`/api/newsletter/queue?${params}`);
      const data = await res.json();
      setQueue(data.queue || []);
      setTotal(data.total || 0);
    } catch { setQueue([]); }
    setLoading(false);
  }, [status]);

  const fetchState = useCallback(async () => {
    try {
      const res = await fetch("/api/newsletter/queue/state");
      const data = await res.json();
      setPaused(!!data.paused);
    } catch { /* leave as-is */ }
  }, []);

  useEffect(() => { fetchQueue(); }, [fetchQueue]);
  useEffect(() => { fetchState(); }, [fetchState]);

  async function togglePause() {
    setPauseBusy(true);
    const next = !paused;
    const res = await fetch("/api/newsletter/queue/state", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ paused: next }),
    });
    if (res.ok) setPaused(next);
    setPauseBusy(false);
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
              Newsletter Send Queue
            </div>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80",
                          letterSpacing: "0.18em", marginTop: 2 }}>
              {total.toLocaleString()} ITEM{total === 1 ? "" : "S"}
            </div>
          </div>
          <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
            <button
              onClick={togglePause}
              disabled={pauseBusy}
              className="btn btn-secondary"
              style={{ whiteSpace: "nowrap", color: paused ? "#5ad07a" : "#e0a030" }}
            >
              {pauseBusy ? "…" : paused ? "▶ Resume Queue" : "⏸ Pause Queue"}
            </button>
            <button onClick={() => setShowAdd(true)} className="btn btn-primary" style={{ whiteSpace: "nowrap" }}>
              + Add Prospect
            </button>
            <button onClick={onClose} style={{ background: "none", border: "none", color: "#3a5a80", cursor: "pointer", fontSize: 16 }}>✕</button>
          </div>
        </div>

        {paused && (
          <div style={{ margin: "10px 24px 0", padding: "8px 14px", borderRadius: 6,
                        background: "#e0a03022", border: "0.5px solid #e0a03080",
                        color: "#e0a030", fontSize: 11, fontFamily: "'Share Tech Mono', monospace", flexShrink: 0 }}>
            ⏸ QUEUE PAUSED — no emails will send until you hit Resume. Queued items are untouched.
          </div>
        )}

        <div style={{ padding: "10px 24px 0", display: "flex", gap: 6, flexShrink: 0 }}>
          {STATUS_TABS.map(t => (
            <button
              key={t.value}
              onClick={() => setStatus(t.value)}
              className={status === t.value ? "btn btn-primary" : "btn btn-secondary"}
              style={{ fontSize: 10, padding: "5px 12px" }}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div style={{ flex: 1, overflowY: "auto", padding: "14px 24px 20px" }}>
          {loading ? (
            <div style={{ padding: "30px 0", textAlign: "center", fontSize: 11, color: "#3a5a80" }}>Loading…</div>
          ) : queue.length === 0 ? (
            <div style={{ padding: "30px 0", textAlign: "center", fontFamily: "'Share Tech Mono', monospace",
                          fontSize: 11, color: "#3a5a80", letterSpacing: "0.18em" }}>
              NOTHING IN THE QUEUE
            </div>
          ) : (
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ borderBottom: "0.5px solid #1a2540" }}>
                  {["Recipient", "Email", "Subject", "Status", "Queued", "Sent"].map(h => (
                    <th key={h} style={{
                      padding: "6px 10px", textAlign: "left",
                      fontFamily: "'Share Tech Mono', monospace", fontSize: 9, fontWeight: 600,
                      letterSpacing: "0.18em", color: "#2a4a7a", textTransform: "uppercase",
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {queue.map(q => (
                  <tr key={q.id} onClick={() => setSelected(q)}
                    style={{ borderBottom: "0.5px solid #121e36", cursor: "pointer" }}
                    onMouseEnter={e => e.currentTarget.style.background = "#0d1428"}
                    onMouseLeave={e => e.currentTarget.style.background = "transparent"}
                  >
                    <td style={{ padding: "8px 10px", fontSize: 12, color: "#f0f4ff" }}>
                      {q.owner || "—"}{q.business ? ` · ${q.business}` : ""}
                    </td>
                    <td style={{ padding: "8px 10px", fontSize: 11, color: "#7a94b8" }}>{q.email}</td>
                    <td style={{ padding: "8px 10px", fontSize: 11, color: "#7a94b8", maxWidth: 220,
                                 overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{q.subject}</td>
                    <td style={{ padding: "8px 10px" }}>
                      <span className={`badge ${STATUS_BADGE[q.status] || "badge-gray"}`}>{q.status.toUpperCase()}</span>
                    </td>
                    <td style={{ padding: "8px 10px", fontSize: 11, color: "#7a94b8" }}>{fmt(q.queued_at)}</td>
                    <td style={{ padding: "8px 10px", fontSize: 11, color: "#7a94b8" }}>{fmt(q.sent_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {selected && (
        <QueueItemDrawer item={selected} onClose={() => setSelected(null)} onChanged={fetchQueue} />
      )}
      {showAdd && (
        <AddProspectModal onClose={() => setShowAdd(false)} onAdded={fetchQueue} />
      )}
    </div>
  );
}
