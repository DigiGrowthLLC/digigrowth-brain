import React, { useState, useEffect, useCallback } from "react";

const STATUSES = [
  { value: "all",                label: "ALL" },
  { value: "new",                label: "NEW" },
  { value: "dialer-lead",        label: "DIALER" },
  { value: "sms-handoff",        label: "SMS HANDOFF" },
  { value: "appointment-booked", label: "BOOKED" },
  { value: "not-interested",     label: "NOT INT." },
  { value: "send-info",          label: "SEND INFO" },
  { value: "voicemail",          label: "VOICEMAIL" },
];

const STATUS_BADGE = {
  "new":                "badge-gray",
  "dialer-lead":        "badge-blue",
  "sms-handoff":        "badge-purple",
  "appointment-booked": "badge-green",
  "not-interested":     "badge-red",
  "send-info":          "badge-amber",
  "voicemail":          "badge-amber",
};

const GRADE_BADGE = {
  A: "badge-green",
  B: "badge-blue",
  C: "badge-amber",
  D: "badge-red",
};

function ContactRow({ contact, onSelect }) {
  return (
    <tr
      onClick={() => onSelect(contact)}
      style={{ borderBottom: "0.5px solid #1a2540", cursor: "pointer", transition: "background 0.1s" }}
      onMouseEnter={e => e.currentTarget.style.background = "#0d1626"}
      onMouseLeave={e => e.currentTarget.style.background = "transparent"}
    >
      <td style={{ padding: "10px 14px", fontSize: 13, fontWeight: 600, color: "#c4d0e8", maxWidth: 180, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {contact.business || <span style={{ color: "#1a2f52" }}>—</span>}
      </td>
      <td style={{ padding: "10px 14px", fontSize: 12, color: "#8a9dc0", maxWidth: 140, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {contact.owner || <span style={{ color: "#1a2f52" }}>—</span>}
      </td>
      <td style={{ padding: "10px 14px", fontFamily: "'Share Tech Mono', monospace", fontSize: 11, color: "#5a6f8f" }}>
        {contact.phone || "—"}
      </td>
      <td style={{ padding: "10px 14px" }}>
        {contact.grade
          ? <span className={`badge ${GRADE_BADGE[contact.grade] || "badge-gray"}`}>{contact.grade}</span>
          : <span style={{ color: "#1a2f52" }}>—</span>}
      </td>
      <td style={{ padding: "10px 14px" }}>
        <span className={`badge ${STATUS_BADGE[contact.status] || "badge-gray"}`}>
          {contact.status}
        </span>
      </td>
      <td style={{ padding: "10px 14px", fontFamily: "'Share Tech Mono', monospace", fontSize: 11, color: "#5a6f8f", textAlign: "center" }}>
        {contact.call_attempts}
      </td>
      <td style={{ padding: "10px 14px", fontSize: 11, color: "#5a6f8f", maxWidth: 160, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {contact.last_disposition || <span style={{ color: "#1a2f52" }}>—</span>}
      </td>
      <td style={{ padding: "10px 14px", fontFamily: "'Share Tech Mono', monospace", fontSize: 11, color: "#3a4f6f" }}>
        {contact.state || "—"}
      </td>
    </tr>
  );
}

function ContactDrawer({ contact, onClose, onUpdate }) {
  const [status, setStatus] = useState(contact.status);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);

  async function saveStatus(newStatus) {
    setSaving(true);
    await fetch(`/api/contacts/${contact.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: newStatus }),
    });
    setStatus(newStatus); onUpdate(); setSaving(false);
  }

  async function submitNote(e) {
    e.preventDefault();
    if (!note.trim()) return;
    await fetch(`/api/contacts/${contact.id}/note`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: note }),
    });
    setNote(""); onUpdate();
  }

  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 50, display: "flex", justifyContent: "flex-end" }}>
      <div style={{ position: "absolute", inset: 0, background: "rgba(8,12,20,0.7)" }} onClick={onClose} />
      <aside style={{
        position: "relative", width: 460,
        background: "#0d1626",
        borderLeft: "0.5px solid #1a2540",
        height: "100%", overflowY: "auto",
        display: "flex", flexDirection: "column",
      }}>
        {/* Header */}
        <div style={{ padding: "18px 20px", borderBottom: "0.5px solid #1a2540",
                      display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
          <div>
            <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 16, fontWeight: 700, color: "#f0f4ff" }}>
              {contact.business || "Unknown"}
            </div>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80",
                          letterSpacing: "0.12em", marginTop: 3 }}>
              {contact.owner || "—"} · {contact.phone}
            </div>
          </div>
          <button onClick={onClose}
            style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 12, color: "#3a5a80",
                     background: "none", border: "none", cursor: "pointer", padding: "2px 6px" }}>
            ✕
          </button>
        </div>

        <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 20, flex: 1 }}>

          {/* Info grid */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px 16px" }}>
            {[
              ["Email", contact.email],
              ["Website", contact.website],
              ["City", contact.city],
              ["State", contact.state],
              ["Grade", contact.grade],
              ["Calls", contact.call_attempts],
              ["Last Disposition", contact.last_disposition],
            ].filter(([, v]) => v != null && v !== "").map(([label, value]) => (
              <div key={label}>
                <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a4a7a",
                              letterSpacing: "0.15em", marginBottom: 3 }}>
                  {label.toUpperCase()}
                </div>
                <div style={{ fontSize: 12, color: "#8aaad0" }}>{String(value)}</div>
              </div>
            ))}
          </div>

          {/* Opener */}
          {contact.opener && (
            <div className="dg-surface" style={{ padding: "10px 14px" }}>
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a4a7a",
                            letterSpacing: "0.15em", marginBottom: 6 }}>
                COLD CALL OPENER
              </div>
              <div style={{ fontSize: 12, color: "#8aaad0", fontStyle: "italic", lineHeight: 1.5 }}>
                "{contact.opener}"
              </div>
            </div>
          )}

          {/* Status update */}
          <div>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a4a7a",
                          letterSpacing: "0.15em", marginBottom: 10 }}>
              UPDATE STATUS
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {STATUSES.filter(s => s.value !== "all").map(({ value, label }) => (
                <button key={value} onClick={() => saveStatus(value)} disabled={saving}
                  className={`btn ${status === value ? "btn-primary" : "btn-secondary"}`}
                  style={{ fontSize: 10, padding: "5px 10px" }}>
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Notes */}
          {contact.notes && (
            <div>
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a4a7a",
                            letterSpacing: "0.15em", marginBottom: 6 }}>
                NOTES
              </div>
              <div className="dg-surface" style={{ padding: "10px 14px", fontSize: 12,
                                                   color: "#6080a8", lineHeight: 1.5, whiteSpace: "pre-wrap" }}>
                {contact.notes}
              </div>
            </div>
          )}

          {/* Add note */}
          <form onSubmit={submitNote} style={{ display: "flex", gap: 8 }}>
            <input value={note} onChange={e => setNote(e.target.value)}
              placeholder="Add a note…" className="dg-input" style={{ flex: 1 }} />
            <button type="submit" className="btn btn-ghost">Add</button>
          </form>
        </div>
      </aside>
    </div>
  );
}

export default function CRMPanel() {
  const [contacts, setContacts]       = useState([]);
  const [total, setTotal]             = useState(0);
  const [loading, setLoading]         = useState(true);
  const [activeStatus, setActiveStatus] = useState("all");
  const [search, setSearch]           = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [offset, setOffset]           = useState(0);
  const [selected, setSelected]       = useState(null);
  const LIMIT = 50;

  const fetchContacts = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams({ limit: LIMIT, offset });
    if (activeStatus !== "all") params.set("status", activeStatus);
    if (search) params.set("search", search);
    try {
      const res  = await fetch(`/api/contacts?${params}`);
      const data = await res.json();
      setContacts(data.contacts || []);
      setTotal(data.total || 0);
    } catch { setContacts([]); }
    setLoading(false);
  }, [activeStatus, search, offset]);

  useEffect(() => { fetchContacts(); }, [fetchContacts]);

  function handleSearch(e) { e.preventDefault(); setSearch(searchInput); setOffset(0); }
  function handleStatus(val) { setActiveStatus(val); setOffset(0); }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>

      {/* Header */}
      <div style={{ padding: "16px 20px", borderBottom: "0.5px solid #1a2540",
                    display: "flex", alignItems: "center", gap: 16, flexShrink: 0 }}>
        <div>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 18, fontWeight: 700, color: "#f0f4ff" }}>
            CRM
          </div>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80",
                        letterSpacing: "0.18em", marginTop: 2 }}>
            {total.toLocaleString()} CONTACTS
          </div>
        </div>

        <form onSubmit={handleSearch} style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
          <input value={searchInput} onChange={e => setSearchInput(e.target.value)}
            placeholder="Search business, owner, phone…"
            className="dg-input" style={{ width: 260 }} />
          <button type="submit" className="btn btn-primary">Search</button>
          {search && (
            <button type="button" className="btn btn-secondary"
              onClick={() => { setSearch(""); setSearchInput(""); setOffset(0); }}>
              Clear
            </button>
          )}
        </form>
      </div>

      {/* Status filters */}
      <div style={{ padding: "8px 20px", borderBottom: "0.5px solid #1a2540",
                    display: "flex", gap: 4, overflowX: "auto", flexShrink: 0 }}>
        {STATUSES.map(({ value, label }) => (
          <button key={value} onClick={() => handleStatus(value)}
            style={{
              fontFamily: "'Share Tech Mono', monospace",
              fontSize: 10, letterSpacing: "0.1em",
              padding: "5px 10px", borderRadius: 3, border: "0.5px solid",
              cursor: "pointer", whiteSpace: "nowrap", transition: "all 0.15s",
              background: activeStatus === value ? "#2857a0" : "transparent",
              borderColor: activeStatus === value ? "#3a7bd5" : "#1a2f52",
              color: activeStatus === value ? "#c8dcff" : "#3a5a80",
            }}>
            {label}
          </button>
        ))}
      </div>

      {/* Table */}
      <div style={{ flex: 1, overflowY: "auto" }}>
        {loading ? (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 120,
                        fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52",
                        letterSpacing: "0.18em" }}>
            LOADING...
          </div>
        ) : contacts.length === 0 ? (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 120,
                        fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52",
                        letterSpacing: "0.18em" }}>
            NO CONTACTS FOUND
          </div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead style={{ position: "sticky", top: 0, background: "#080c14", zIndex: 1 }}>
              <tr style={{ borderBottom: "0.5px solid #1a2540" }}>
                {["Business","Owner","Phone","Grade","Status","Calls","Last Disposition","State"].map(h => (
                  <th key={h} style={{
                    padding: "8px 14px", textAlign: "left",
                    fontFamily: "'Share Tech Mono', monospace",
                    fontSize: 9, fontWeight: 600, letterSpacing: "0.18em",
                    color: "#2a4a7a", textTransform: "uppercase",
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {contacts.map(c => <ContactRow key={c.id} contact={c} onSelect={setSelected} />)}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      <div style={{ padding: "10px 20px", borderTop: "0.5px solid #1a2540",
                    display: "flex", alignItems: "center", justifyContent: "space-between",
                    flexShrink: 0 }}>
        <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>
          {offset + 1}–{Math.min(offset + LIMIT, total)} OF {total.toLocaleString()}
        </span>
        <div style={{ display: "flex", gap: 6 }}>
          <button onClick={() => setOffset(Math.max(0, offset - LIMIT))}
            disabled={offset === 0} className="btn btn-secondary"
            style={{ fontSize: 10, padding: "5px 12px" }}>
            ← PREV
          </button>
          <button onClick={() => setOffset(offset + LIMIT)}
            disabled={offset + LIMIT >= total} className="btn btn-secondary"
            style={{ fontSize: 10, padding: "5px 12px" }}>
            NEXT →
          </button>
        </div>
      </div>

      {selected && (
        <ContactDrawer contact={selected} onClose={() => setSelected(null)}
          onUpdate={fetchContacts} />
      )}
    </div>
  );
}
