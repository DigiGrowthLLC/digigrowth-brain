import React, { useState, useEffect, useCallback, useRef } from "react";

const STATUSES = [
  { value: "all",                label: "ALL" },
  { value: "new",                label: "NEW" },
  { value: "dialer-lead",        label: "DIALER" },
  { value: "sms-handoff",        label: "SMS HANDOFF" },
  { value: "appointment-booked", label: "BOOKED" },
  { value: "not-interested",     label: "NOT INT." },
  { value: "send-info",          label: "SEND INFO" },
  { value: "voicemail",          label: "VOICEMAIL" },
  { value: "gatekeeper-blocked", label: "GATEKEEPER" },
  { value: "manual-followup",    label: "MANUAL F/U" },
];

const STATUS_BADGE = {
  "new":                "badge-gray",
  "dialer-lead":        "badge-blue",
  "sms-handoff":        "badge-purple",
  "appointment-booked": "badge-green",
  "not-interested":     "badge-red",
  "send-info":          "badge-amber",
  "voicemail":          "badge-amber",
  "gatekeeper-blocked": "badge-orange",
  "manual-followup":    "badge-amber",
};

const GRADE_BADGE = {
  A: "badge-green",
  B: "badge-blue",
  C: "badge-amber",
  D: "badge-red",
};

const DEFAULT_TAG_COLOR = "#3a7bd5";
const TAG_COLOR_PRESETS = ["#3a7bd5", "#5a9a5a", "#e0a030", "#e05555", "#a05ae0", "#5adcc8", "#e05a9e", "#8a9dc0"];

function TagChip({ name, color, onRemove }) {
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 5,
      padding: "2px 8px", borderRadius: 10,
      background: `${color}22`, border: `0.5px solid ${color}80`,
      color, fontFamily: "'Share Tech Mono', monospace", fontSize: 10,
      whiteSpace: "nowrap",
    }}>
      {name}
      {onRemove && (
        <span onClick={e => { e.stopPropagation(); onRemove(); }}
          style={{ cursor: "pointer", opacity: 0.7, fontSize: 10, lineHeight: 1 }}>✕</span>
      )}
    </span>
  );
}

// ── Manage Tags Modal ─────────────────────────────────────────────────────────

function ManageTagsModal({ tags, onClose, onChanged }) {
  const [name, setName] = useState("");
  const [color, setColor] = useState(DEFAULT_TAG_COLOR);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  async function createTag(e) {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true); setErr("");
    const res = await fetch("/api/tags", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name.trim(), color }),
    });
    if (res.ok) { setName(""); setColor(DEFAULT_TAG_COLOR); onChanged(); }
    else { const d = await res.json().catch(() => ({})); setErr(d.detail || "Failed to create tag."); }
    setSaving(false);
  }

  async function deleteTag(tag) {
    if (!window.confirm(`Delete tag "${tag.name}"? It will be removed from all contacts.`)) return;
    await fetch(`/api/tags/${tag.id}`, { method: "DELETE" });
    onChanged();
  }

  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 60, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ position: "absolute", inset: 0, background: "rgba(4,8,16,0.85)" }} onClick={onClose} />
      <div style={{ position: "relative", background: "#0a1020", border: "0.5px solid #1a2540", borderRadius: 8, width: 420, maxHeight: "80vh", overflowY: "auto", padding: "24px 28px", display: "flex", flexDirection: "column", gap: 18 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 16, fontWeight: 700, color: "#f0f4ff" }}>Manage Tags</div>
          <button onClick={onClose} style={{ background: "none", border: "none", color: "#3a5a80", cursor: "pointer", fontSize: 14 }}>✕</button>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {tags.length === 0 && (
            <div style={{ fontSize: 12, color: "#3a5a80", fontFamily: "'Share Tech Mono', monospace" }}>No tags yet.</div>
          )}
          {tags.map(t => (
            <div key={t.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "6px 10px", background: "#060a14", border: "0.5px solid #121e36", borderRadius: 6 }}>
              <TagChip name={t.name} color={t.color} />
              <span style={{ marginLeft: "auto" }} />
              <button onClick={() => deleteTag(t)}
                style={{ background: "none", border: "none", color: "#5a3a3a", cursor: "pointer", fontSize: 11, fontFamily: "'Share Tech Mono', monospace" }}>
                Delete
              </button>
            </div>
          ))}
        </div>

        <form onSubmit={createTag} style={{ display: "flex", flexDirection: "column", gap: 10, borderTop: "0.5px solid #1a2540", paddingTop: 16 }}>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a4a7a", letterSpacing: "0.15em" }}>NEW TAG</div>
          <div style={{ display: "flex", gap: 8 }}>
            <input value={name} onChange={e => setName(e.target.value)} placeholder="Tag name…"
              className="dg-input" style={{ flex: 1 }} />
            <input type="color" value={color} onChange={e => setColor(e.target.value)}
              style={{ width: 36, height: 34, padding: 2, background: "#080c14", border: "0.5px solid #1a2540", borderRadius: 4, cursor: "pointer" }} />
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            {TAG_COLOR_PRESETS.map(c => (
              <button type="button" key={c} onClick={() => setColor(c)}
                style={{ width: 18, height: 18, borderRadius: "50%", background: c, cursor: "pointer",
                         border: c === color ? "2px solid #f0f4ff" : "1px solid rgba(255,255,255,0.2)" }} />
            ))}
          </div>
          {err && <div style={{ fontSize: 12, color: "#e05555" }}>{err}</div>}
          <button type="submit" className="btn btn-primary" disabled={saving || !name.trim()}>
            {saving ? "Saving…" : "+ Create Tag"}
          </button>
        </form>
      </div>
    </div>
  );
}

function fmtLastCalled(ts) {
  if (!ts) return null;
  return new Date(ts).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

// ── CSV parser ────────────────────────────────────────────────────────────────

function parseCsvLine(line) {
  const cols = []; let cur = ""; let inQ = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') { if (inQ && line[i + 1] === '"') { cur += '"'; i++; } else inQ = !inQ; }
    else if (ch === ',' && !inQ) { cols.push(cur.trim()); cur = ""; }
    else cur += ch;
  }
  cols.push(cur.trim()); return cols;
}

const CSV_ALIASES = {
  phone:    ["phone", "phone number", "mobile", "cell", "telephone"],
  business: ["business", "company", "business name", "company name"],
  owner:    ["owner", "name", "contact", "contact name", "full name", "first name"],
  email:    ["email", "email address"],
  website:  ["website", "url", "site", "web"],
  city:     ["city", "town"],
  state:    ["state", "province", "region"],
  grade:    ["grade", "lead grade", "score", "tier"],
  opener:   ["opener", "cold call opener", "pitch", "intro"],
  notes:    ["notes", "note", "comments", "comment"],
  status:   ["status"],
};

function parseCSV(text) {
  const lines = text.replace(/\r/g, "").split("\n").filter(l => l.trim());
  if (lines.length < 2) return [];
  const headers = parseCsvLine(lines[0]).map(h => h.toLowerCase().replace(/['"]/g, "").trim());
  const colMap = {};
  for (const [field, aliases] of Object.entries(CSV_ALIASES)) {
    const idx = headers.findIndex(h => aliases.includes(h));
    if (idx >= 0) colMap[field] = idx;
  }
  return lines.slice(1).map(line => {
    const cols = parseCsvLine(line);
    const row = {};
    for (const [field, idx] of Object.entries(colMap)) row[field] = (cols[idx] || "").replace(/^"|"$/g, "").trim();
    return row;
  });
}

// ── Add Contact Modal ─────────────────────────────────────────────────────────

const EMPTY_FORM = { business: "", owner: "", phone: "", email: "", website: "", city: "", state: "", grade: "", status: "new", opener: "", notes: "" };

function AddContactModal({ onClose, onSaved }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  function set(k, v) { setForm(f => ({ ...f, [k]: v })); }

  async function submit(e) {
    e.preventDefault();
    if (!form.phone.trim()) { setErr("Phone is required."); return; }
    setSaving(true); setErr("");
    const res = await fetch("/api/contacts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: "", ...form, grade: form.grade || null }),
    });
    if (res.ok) { onSaved(); onClose(); }
    else { const d = await res.json().catch(() => ({})); setErr(d.detail || "Save failed."); }
    setSaving(false);
  }

  const field = (label, key, opts = {}) => (
    <div>
      <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a4a7a", letterSpacing: "0.15em", marginBottom: 4 }}>{label.toUpperCase()}</div>
      {opts.type === "select" ? (
        <select value={form[key]} onChange={e => set(key, e.target.value)} className="dg-input" style={{ width: "100%", background: "#080c14" }}>
          {opts.options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      ) : opts.type === "textarea" ? (
        <textarea value={form[key]} onChange={e => set(key, e.target.value)} className="dg-input" rows={3}
          style={{ width: "100%", resize: "vertical", fontFamily: "inherit" }} placeholder={opts.placeholder || ""} />
      ) : (
        <input value={form[key]} onChange={e => set(key, e.target.value)} className="dg-input"
          style={{ width: "100%" }} placeholder={opts.placeholder || ""} />
      )}
    </div>
  );

  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 60, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ position: "absolute", inset: 0, background: "rgba(4,8,16,0.85)" }} onClick={onClose} />
      <div style={{ position: "relative", background: "#0a1020", border: "0.5px solid #1a2540", borderRadius: 8, width: 560, maxHeight: "88vh", overflowY: "auto", padding: "24px 28px", display: "flex", flexDirection: "column", gap: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 16, fontWeight: 700, color: "#f0f4ff" }}>Add Contact</div>
          <button onClick={onClose} style={{ background: "none", border: "none", color: "#3a5a80", cursor: "pointer", fontSize: 14 }}>✕</button>
        </div>
        <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
            {field("Business Name", "business")}
            {field("Owner / Contact", "owner")}
            {field("Phone *", "phone", { placeholder: "+1 555-000-0000" })}
            {field("Email", "email")}
            {field("City", "city")}
            {field("State", "state")}
            {field("Grade", "grade", { type: "select", options: [{ value: "", label: "—" }, { value: "A", label: "A" }, { value: "B", label: "B" }, { value: "C", label: "C" }, { value: "D", label: "D" }] })}
            {field("Status", "status", { type: "select", options: STATUSES.filter(s => s.value !== "all").map(s => ({ value: s.value, label: s.label })) })}
          </div>
          {field("Website", "website")}
          {field("Cold Call Opener", "opener", { type: "textarea", placeholder: "Opening line for cold call…" })}
          {field("Notes", "notes", { type: "textarea" })}
          {err && <div style={{ fontSize: 12, color: "#e05555" }}>{err}</div>}
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 4 }}>
            <button type="button" onClick={onClose} className="btn btn-secondary">Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? "Saving…" : "Add Contact"}</button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Import CSV Modal ──────────────────────────────────────────────────────────

function ImportModal({ onClose, onImported, tags, onTagsChanged }) {
  const [parsed, setParsed]   = useState(null);
  const [result, setResult]   = useState(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr]         = useState("");
  const fileRef               = useRef();
  const [importStatus, setImportStatus] = useState("");
  const [importTags, setImportTags]     = useState([]);
  const [newTagName, setNewTagName]     = useState("");

  function toggleImportTag(name) {
    setImportTags(t => t.includes(name) ? t.filter(x => x !== name) : [...t, name]);
  }

  async function createAndSelectTag(e) {
    e.preventDefault();
    const name = newTagName.trim();
    if (!name) return;
    const res = await fetch("/api/tags", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    if (res.ok) {
      onTagsChanged();
      setImportTags(t => t.includes(name) ? t : [...t, name]);
      setNewTagName("");
    }
  }

  function handleFile(e) {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = ev => {
      const rows = parseCSV(ev.target.result);
      setParsed(rows); setResult(null); setErr("");
    };
    reader.readAsText(file);
  }

  async function doImport() {
    if (!parsed?.length) return;
    setLoading(true); setErr("");
    const res = await fetch("/api/contacts/import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ contacts: parsed, status: importStatus || null, tags: importTags }),
    });
    if (res.ok) {
      const data = await res.json();
      setResult(data);
      onImported();
    } else {
      const d = await res.json().catch(() => ({}));
      setErr(d.detail || "Import failed.");
    }
    setLoading(false);
  }

  const withPhone = parsed ? parsed.filter(r => r.phone) : [];
  const preview   = withPhone.slice(0, 3);

  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 60, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ position: "absolute", inset: 0, background: "rgba(4,8,16,0.85)" }} onClick={onClose} />
      <div style={{ position: "relative", background: "#0a1020", border: "0.5px solid #1a2540", borderRadius: 8, width: 600, maxHeight: "88vh", overflowY: "auto", padding: "24px 28px", display: "flex", flexDirection: "column", gap: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 16, fontWeight: 700, color: "#f0f4ff" }}>Import Contacts</div>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80", letterSpacing: "0.14em", marginTop: 3 }}>CSV — PHONE COLUMN REQUIRED</div>
          </div>
          <button onClick={onClose} style={{ background: "none", border: "none", color: "#3a5a80", cursor: "pointer", fontSize: 14 }}>✕</button>
        </div>

        <div style={{ fontSize: 12, color: "#4a6a90", lineHeight: 1.6 }}>
          Supported headers (case-insensitive): <span style={{ fontFamily: "'Share Tech Mono', monospace", color: "#3a7bd5" }}>phone, business, owner, email, website, city, state, grade, opener, notes, status</span>.<br />
          Existing contacts matched by phone will be updated with any new non-empty values.
        </div>

        <div>
          <input ref={fileRef} type="file" accept=".csv,text/csv" onChange={handleFile}
            style={{ display: "none" }} />
          <button onClick={() => fileRef.current.click()} className="btn btn-secondary" style={{ fontSize: 12 }}>
            Choose CSV File
          </button>
        </div>

        {parsed && !result && (
          <>
            <div style={{ padding: "12px 16px", background: "#060a14", border: "0.5px solid #1a2540", borderRadius: 6 }}>
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a7bd5", letterSpacing: "0.14em" }}>
                {withPhone.length} CONTACTS READY &nbsp;·&nbsp; {parsed.length - withPhone.length} SKIPPED (NO PHONE)
              </div>
            </div>

            {preview.length > 0 && (
              <div>
                <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a4a7a", letterSpacing: "0.15em", marginBottom: 8 }}>PREVIEW (FIRST {preview.length})</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  {preview.map((row, i) => (
                    <div key={i} style={{ padding: "8px 12px", background: "#060a14", border: "0.5px solid #121e36", borderRadius: 4, fontSize: 11, color: "#7a9abf", fontFamily: "'Share Tech Mono', monospace" }}>
                      {row.business && <span style={{ color: "#c4d0e8", marginRight: 10 }}>{row.business}</span>}
                      {row.owner && <span style={{ marginRight: 10 }}>{row.owner}</span>}
                      <span style={{ color: "#3a7bd5" }}>{row.phone}</span>
                      {row.grade && <span style={{ marginLeft: 10, color: "#5a9a5a" }}>{row.grade}</span>}
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div style={{ display: "flex", flexDirection: "column", gap: 10, padding: "12px 16px", background: "#060a14", border: "0.5px solid #1a2540", borderRadius: 6 }}>
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a4a7a", letterSpacing: "0.15em" }}>APPLY TO ALL IMPORTED CONTACTS (OPTIONAL)</div>

              <div>
                <div style={{ fontSize: 11, color: "#5a7096", marginBottom: 4 }}>Status — overrides any status column in the CSV</div>
                <select value={importStatus} onChange={e => setImportStatus(e.target.value)}
                  className="dg-input" style={{ width: "100%", background: "#080c14" }}>
                  <option value="">— use CSV value / default "new" —</option>
                  {STATUSES.filter(s => s.value !== "all").map(s => (
                    <option key={s.value} value={s.value}>{s.label}</option>
                  ))}
                </select>
              </div>

              <div>
                <div style={{ fontSize: 11, color: "#5a7096", marginBottom: 4 }}>Tags — added to every imported contact</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 8 }}>
                  {tags.length === 0 && (
                    <span style={{ fontSize: 11, color: "#3a5a80" }}>No tags defined yet — create one below.</span>
                  )}
                  {tags.map(t => {
                    const active = importTags.includes(t.name);
                    return (
                      <button type="button" key={t.id} onClick={() => toggleImportTag(t.name)}
                        style={{
                          padding: "3px 9px", borderRadius: 10, cursor: "pointer",
                          background: active ? `${t.color}33` : "transparent",
                          border: `0.5px solid ${active ? t.color : "#1a2f52"}`,
                          color: active ? t.color : "#5a7096",
                          fontFamily: "'Share Tech Mono', monospace", fontSize: 10,
                        }}>
                        {active ? "✓ " : ""}{t.name}
                      </button>
                    );
                  })}
                </div>
                <form onSubmit={createAndSelectTag} style={{ display: "flex", gap: 6 }}>
                  <input value={newTagName} onChange={e => setNewTagName(e.target.value)}
                    placeholder="New tag name…" className="dg-input" style={{ flex: 1, fontSize: 12 }} />
                  <button type="submit" className="btn btn-ghost" disabled={!newTagName.trim()} style={{ fontSize: 11 }}>
                    + Create
                  </button>
                </form>
              </div>
            </div>

            {err && <div style={{ fontSize: 12, color: "#e05555" }}>{err}</div>}

            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
              <button onClick={onClose} className="btn btn-secondary">Cancel</button>
              <button onClick={doImport} className="btn btn-primary" disabled={loading || withPhone.length === 0}>
                {loading ? "Importing…" : `Import ${withPhone.length} Contacts`}
              </button>
            </div>
          </>
        )}

        {result && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ padding: "16px 20px", background: "#060a14", border: "0.5px solid #1a2540", borderRadius: 6, display: "flex", gap: 24 }}>
              {[["Added", result.inserted, "#3a7bd5"], ["Updated", result.updated, "#5a9a5a"], ["Skipped", result.skipped, "#5a5a7a"]].map(([label, val, color]) => (
                <div key={label}>
                  <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a4a7a", letterSpacing: "0.15em" }}>{label}</div>
                  <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 24, fontWeight: 700, color }}>{val}</div>
                </div>
              ))}
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <button onClick={onClose} className="btn btn-primary">Done</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function ContactRow({ contact, checked, onCheck, onSelect, tagColor }) {
  return (
    <tr
      style={{ borderBottom: "0.5px solid #1a2540", cursor: "pointer", transition: "background 0.1s", background: checked ? "rgba(40,87,160,0.1)" : "transparent" }}
      onMouseEnter={e => { if (!checked) e.currentTarget.style.background = "#0d1626"; }}
      onMouseLeave={e => { if (!checked) e.currentTarget.style.background = "transparent"; }}
    >
      <td style={{ padding: "10px 10px 10px 14px", width: 32 }} onClick={e => e.stopPropagation()}>
        <input
          type="checkbox"
          checked={checked}
          onChange={() => onCheck(contact.id)}
          style={{ accentColor: "#3a7bd5", width: 13, height: 13, cursor: "pointer" }}
        />
      </td>
      <td style={{ padding: "10px 14px", fontSize: 13, fontWeight: 600, color: "#c4d0e8", maxWidth: 180, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} onClick={() => onSelect(contact)}>
        {contact.business || <span style={{ color: "#1a2f52" }}>—</span>}
      </td>
      <td style={{ padding: "10px 14px", fontSize: 12, color: "#8a9dc0", maxWidth: 140, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} onClick={() => onSelect(contact)}>
        {contact.owner || <span style={{ color: "#1a2f52" }}>—</span>}
      </td>
      <td style={{ padding: "10px 14px", fontFamily: "'Share Tech Mono', monospace", fontSize: 11, color: "#5a6f8f" }} onClick={() => onSelect(contact)}>
        {contact.phone || "—"}
      </td>
      <td style={{ padding: "10px 14px" }} onClick={() => onSelect(contact)}>
        {contact.grade
          ? <span className={`badge ${GRADE_BADGE[contact.grade] || "badge-gray"}`}>{contact.grade}</span>
          : <span style={{ color: "#1a2f52" }}>—</span>}
      </td>
      <td style={{ padding: "10px 14px" }} onClick={() => onSelect(contact)}>
        <span className={`badge ${STATUS_BADGE[contact.status] || "badge-gray"}`}>
          {contact.status}
        </span>
      </td>
      <td style={{ padding: "10px 14px", fontFamily: "'Share Tech Mono', monospace", fontSize: 11, color: "#5a6f8f", textAlign: "center" }} onClick={() => onSelect(contact)}>
        {contact.call_attempts}
      </td>
      <td style={{ padding: "10px 14px", fontFamily: "'Share Tech Mono', monospace", fontSize: 11, color: "#5a6f8f", whiteSpace: "nowrap" }} onClick={() => onSelect(contact)}>
        {fmtLastCalled(contact.last_called_at) || <span style={{ color: "#1a2f52" }}>never</span>}
      </td>
      <td style={{ padding: "10px 14px", fontSize: 11, color: "#5a6f8f", maxWidth: 160, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} onClick={() => onSelect(contact)}>
        {contact.last_disposition || <span style={{ color: "#1a2f52" }}>—</span>}
      </td>
      <td style={{ padding: "10px 14px", fontFamily: "'Share Tech Mono', monospace", fontSize: 11, color: "#3a4f6f" }} onClick={() => onSelect(contact)}>
        {contact.state || "—"}
      </td>
      <td style={{ padding: "10px 14px", maxWidth: 200 }} onClick={() => onSelect(contact)}>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
          {(contact.tags || []).length > 0
            ? contact.tags.map(t => <TagChip key={t} name={t} color={tagColor(t)} />)
            : <span style={{ color: "#1a2f52" }}>—</span>}
        </div>
      </td>
    </tr>
  );
}

const EDITABLE_FIELDS = ["business", "owner", "phone", "email", "website", "city", "state", "grade", "opener"];

function ContactDrawer({ contact, onClose, onUpdate, onNavigate, tags, tagColor, onTagsChanged }) {
  const [status, setStatus] = useState(contact.status);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [addedToQueue, setAddedToQueue] = useState(false);
  const [queueError, setQueueError] = useState("");
  const [callingNow, setCallingNow] = useState(false);

  const [display, setDisplay] = useState(contact);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({});
  const [editErr, setEditErr] = useState("");
  const [tagPick, setTagPick] = useState("");
  const [newTagName, setNewTagName] = useState("");

  async function addTag(tagName) {
    const name = tagName.trim();
    if (!name) return;
    const res = await fetch(`/api/contacts/${contact.id}/tags`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tag: name }),
    });
    if (res.ok) {
      const updated = await res.json();
      setDisplay(updated);
      onUpdate();
    }
  }

  async function removeTag(tagName) {
    const res = await fetch(`/api/contacts/${contact.id}/tags/${encodeURIComponent(tagName)}`, { method: "DELETE" });
    if (res.ok) {
      const updated = await res.json();
      setDisplay(updated);
      onUpdate();
    }
  }

  async function addExistingTag() {
    if (!tagPick) return;
    await addTag(tagPick);
    setTagPick("");
  }

  async function createAndAddTag(e) {
    e.preventDefault();
    const name = newTagName.trim();
    if (!name) return;
    const res = await fetch("/api/tags", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    if (res.ok) {
      onTagsChanged();
      await addTag(name);
      setNewTagName("");
    }
  }

  function setField(k, v) { setForm(f => ({ ...f, [k]: v })); }

  function startEditing() {
    const initial = {};
    for (const k of EDITABLE_FIELDS) initial[k] = display[k] || "";
    setForm(initial);
    setEditErr("");
    setEditing(true);
  }

  async function saveEdits() {
    setSaving(true); setEditErr("");
    try {
      const res = await fetch(`/api/contacts/${contact.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...form, grade: form.grade || null }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        setEditErr(d.detail || "Save failed.");
        setSaving(false);
        return;
      }
      const updated = await res.json();
      setDisplay(updated);
      onUpdate();
      setEditing(false);
    } catch (e) {
      setEditErr(String(e));
    }
    setSaving(false);
  }

  async function saveStatus(newStatus) {
    setSaving(true);
    await fetch(`/api/contacts/${contact.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: newStatus }),
    });
    setStatus(newStatus); onUpdate(); setSaving(false);
  }

  async function addToQueue() {
    setSaving(true);
    setQueueError("");
    try {
      const res = await fetch(`/api/contacts/${contact.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "dialer-lead" }),
      });
      if (!res.ok) {
        const body = await res.text();
        setQueueError(`Error ${res.status}: ${body}`);
        setSaving(false);
        return;
      }
      setStatus("dialer-lead");
      setAddedToQueue(true);
      onUpdate();
      setTimeout(() => setAddedToQueue(false), 2000);
    } catch (e) {
      setQueueError(String(e));
    }
    setSaving(false);
  }

  async function callNow() {
    setCallingNow(true);
    try {
      await fetch("/api/dialer/call-single", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ contact_id: contact.id }),
      });
      if (onNavigate) onNavigate("dialer");
    } catch {}
    setCallingNow(false);
  }

  async function submitNote(e) {
    e.preventDefault();
    if (!note.trim()) return;
    const res = await fetch(`/api/contacts/${contact.id}/note`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: note }),
    });
    if (res.ok) {
      const { notes } = await res.json();
      setDisplay(d => ({ ...d, notes }));
    }
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
                      display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 10 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            {editing ? (
              <input value={form.business} onChange={e => setField("business", e.target.value)}
                className="dg-input" placeholder="Business name"
                style={{ width: "100%", fontSize: 14, fontWeight: 700, marginBottom: 6 }} />
            ) : (
              <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 16, fontWeight: 700, color: "#f0f4ff" }}>
                {display.business || "Unknown"}
              </div>
            )}
            {editing ? (
              <div style={{ display: "flex", gap: 6 }}>
                <input value={form.owner} onChange={e => setField("owner", e.target.value)}
                  className="dg-input" placeholder="Owner" style={{ flex: 1, fontSize: 11 }} />
                <input value={form.phone} onChange={e => setField("phone", e.target.value)}
                  className="dg-input" placeholder="Phone" style={{ flex: 1, fontSize: 11 }} />
              </div>
            ) : (
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80",
                            letterSpacing: "0.12em", marginTop: 3 }}>
                {display.owner || "—"} · {display.phone}
              </div>
            )}
          </div>
          <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
            {!editing && (
              <button onClick={startEditing}
                style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 11, color: "#5a9bf0",
                         background: "rgba(58,123,213,0.12)", border: "1px solid rgba(58,123,213,0.3)",
                         borderRadius: 6, cursor: "pointer", padding: "5px 10px" }}>
                ✎ Edit
              </button>
            )}
            <button onClick={onClose}
              style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 12, color: "#3a5a80",
                       background: "none", border: "none", cursor: "pointer", padding: "2px 6px" }}>
              ✕
            </button>
          </div>
        </div>

        <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 20, flex: 1 }}>

          {/* Info grid */}
          {editing ? (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              {[["Email", "email"], ["Website", "website"], ["City", "city"], ["State", "state"]].map(([label, key]) => (
                <div key={key}>
                  <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a4a7a",
                                letterSpacing: "0.15em", marginBottom: 4 }}>
                    {label.toUpperCase()}
                  </div>
                  <input value={form[key]} onChange={e => setField(key, e.target.value)}
                    className="dg-input" style={{ width: "100%" }} />
                </div>
              ))}
              <div>
                <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a4a7a",
                              letterSpacing: "0.15em", marginBottom: 4 }}>
                  GRADE
                </div>
                <select value={form.grade} onChange={e => setField("grade", e.target.value)}
                  className="dg-input" style={{ width: "100%", background: "#080c14" }}>
                  <option value="">—</option>
                  <option value="A">A</option>
                  <option value="B">B</option>
                  <option value="C">C</option>
                  <option value="D">D</option>
                </select>
              </div>
            </div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px 16px" }}>
              {[
                ["Email", display.email],
                ["Website", display.website],
                ["City", display.city],
                ["State", display.state],
                ["Grade", display.grade],
                ["Calls", display.call_attempts],
                ["Last Disposition", display.last_disposition],
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
          )}

          {/* Opener */}
          {editing ? (
            <div>
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a4a7a",
                            letterSpacing: "0.15em", marginBottom: 6 }}>
                COLD CALL OPENER
              </div>
              <textarea value={form.opener} onChange={e => setField("opener", e.target.value)}
                className="dg-input" rows={3} style={{ width: "100%", resize: "vertical", fontFamily: "inherit" }}
                placeholder="Opening line for cold call…" />
            </div>
          ) : display.opener && (
            <div className="dg-surface" style={{ padding: "10px 14px" }}>
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a4a7a",
                            letterSpacing: "0.15em", marginBottom: 6 }}>
                COLD CALL OPENER
              </div>
              <div style={{ fontSize: 12, color: "#8aaad0", fontStyle: "italic", lineHeight: 1.5 }}>
                "{display.opener}"
              </div>
            </div>
          )}

          {editing && (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {editErr && (
                <div style={{ fontSize: 11, color: "#f06060", fontFamily: "'Share Tech Mono', monospace" }}>
                  {editErr}
                </div>
              )}
              <div style={{ display: "flex", gap: 8 }}>
                <button onClick={saveEdits} disabled={saving} className="btn btn-primary" style={{ flex: 1 }}>
                  {saving ? "Saving…" : "Save Changes"}
                </button>
                <button onClick={() => setEditing(false)} disabled={saving} className="btn btn-secondary" style={{ flex: 1 }}>
                  Cancel
                </button>
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

          {/* Tags */}
          <div>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a4a7a",
                          letterSpacing: "0.15em", marginBottom: 10 }}>
              TAGS
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 10 }}>
              {(display.tags || []).length > 0
                ? display.tags.map(t => (
                    <TagChip key={t} name={t} color={tagColor(t)} onRemove={() => removeTag(t)} />
                  ))
                : <span style={{ fontSize: 11, color: "#3a5a80" }}>No tags yet.</span>}
            </div>
            <div style={{ display: "flex", gap: 6 }}>
              <select value={tagPick} onChange={e => setTagPick(e.target.value)}
                className="dg-input" style={{ flex: 1, background: "#080c14" }}>
                <option value="">— add existing tag —</option>
                {tags.filter(t => !(display.tags || []).includes(t.name)).map(t => (
                  <option key={t.id} value={t.name}>{t.name}</option>
                ))}
              </select>
              <button type="button" onClick={addExistingTag} disabled={!tagPick} className="btn btn-secondary" style={{ fontSize: 11 }}>
                Add
              </button>
            </div>
            <form onSubmit={createAndAddTag} style={{ display: "flex", gap: 6, marginTop: 6 }}>
              <input value={newTagName} onChange={e => setNewTagName(e.target.value)}
                placeholder="New tag name…" className="dg-input" style={{ flex: 1 }} />
              <button type="submit" className="btn btn-ghost" disabled={!newTagName.trim()} style={{ fontSize: 11 }}>
                + Create
              </button>
            </form>
          </div>

          {/* Dialer actions */}
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {queueError && (
            <div style={{ fontSize: 11, color: "#f06060", fontFamily: "'Share Tech Mono', monospace", padding: "4px 0" }}>
              {queueError}
            </div>
          )}
          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={callNow} disabled={callingNow}
              style={{
                flex: 1, padding: "9px 12px", borderRadius: 8,
                background: "rgba(58,123,213,0.15)", border: "1px solid rgba(58,123,213,0.35)",
                color: "#5a9bf0", fontFamily: "'Space Grotesk', sans-serif",
                fontSize: 12, fontWeight: 600, cursor: callingNow ? "not-allowed" : "pointer",
                opacity: callingNow ? 0.6 : 1,
              }}>
              {callingNow ? "Starting…" : "📞 Call Now"}
            </button>
            <button onClick={addToQueue} disabled={saving}
              style={{
                flex: 1, padding: "9px 12px", borderRadius: 8,
                background: "rgba(20,200,130,0.1)", border: "1px solid rgba(20,200,130,0.25)",
                color: addedToQueue ? "#14c882" : "#5ad4a8",
                fontFamily: "'Space Grotesk', sans-serif",
                fontSize: 12, fontWeight: 600, cursor: saving ? "not-allowed" : "pointer",
                opacity: saving ? 0.6 : 1,
              }}>
              {addedToQueue ? "Added ✓" : "＋ Add to Queue"}
            </button>
          </div>
          </div>

          {/* Notes */}
          {display.notes && (
            <div>
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a4a7a",
                            letterSpacing: "0.15em", marginBottom: 6 }}>
                NOTES
              </div>
              <div className="dg-surface" style={{ padding: "10px 14px", fontSize: 12,
                                                   color: "#6080a8", lineHeight: 1.5, whiteSpace: "pre-wrap" }}>
                {display.notes}
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

export default function CRMPanel({ onNavigate }) {
  const [contacts, setContacts]       = useState([]);
  const [total, setTotal]             = useState(0);
  const [loading, setLoading]         = useState(true);
  const [activeStatus, setActiveStatus] = useState("all");
  const [activeTag, setActiveTag]     = useState("");
  const [search, setSearch]           = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [offset, setOffset]           = useState(0);
  const [selected, setSelected]       = useState(null);
  const [showAdd, setShowAdd]         = useState(false);
  const [showImport, setShowImport]   = useState(false);
  const [showManageTags, setShowManageTags] = useState(false);
  const [tags, setTags]               = useState([]);

  const fetchTags = useCallback(async () => {
    try {
      const res = await fetch("/api/tags");
      setTags(await res.json());
    } catch { setTags([]); }
  }, []);

  useEffect(() => { fetchTags(); }, [fetchTags]);

  const tagColor = useCallback(
    name => tags.find(t => t.name === name)?.color || DEFAULT_TAG_COLOR,
    [tags]
  );

  // ── Selection state ──
  const [checkedIds, setCheckedIds]   = useState(new Set());
  const [selectAllPages, setSelectAllPages] = useState(false); // true = all contacts across pages

  // ── Bulk action state ──
  const [bulkAction, setBulkAction]   = useState("set_status");
  const [bulkValue, setBulkValue]     = useState("");
  const [bulkTagInput, setBulkTagInput] = useState("");
  const [bulkRunning, setBulkRunning] = useState(false);
  const [bulkFeedback, setBulkFeedback] = useState("");

  const LIMIT = 50;

  const fetchContacts = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams({ limit: LIMIT, offset });
    if (activeStatus !== "all") params.set("status", activeStatus);
    if (activeTag) params.set("tag", activeTag);
    if (search) params.set("search", search);
    try {
      const res  = await fetch(`/api/contacts?${params}`);
      const data = await res.json();
      setContacts(data.contacts || []);
      setTotal(data.total || 0);
    } catch { setContacts([]); }
    setLoading(false);
  }, [activeStatus, activeTag, search, offset]);

  useEffect(() => { fetchContacts(); }, [fetchContacts]);

  function handleSearch(e) { e.preventDefault(); setSearch(searchInput); setOffset(0); }
  function handleStatus(val) { setActiveStatus(val); setOffset(0); setCheckedIds(new Set()); setSelectAllPages(false); }

  // ── Selection helpers ──
  const pageIds = contacts.map(c => c.id);
  const allPageChecked = pageIds.length > 0 && pageIds.every(id => checkedIds.has(id));
  const someChecked = checkedIds.size > 0 || selectAllPages;

  function toggleCheck(id) {
    setSelectAllPages(false);
    setCheckedIds(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  function togglePageAll() {
    setSelectAllPages(false);
    if (allPageChecked) {
      setCheckedIds(prev => { const next = new Set(prev); pageIds.forEach(id => next.delete(id)); return next; });
    } else {
      setCheckedIds(prev => { const next = new Set(prev); pageIds.forEach(id => next.add(id)); return next; });
    }
  }

  function clearSelection() { setCheckedIds(new Set()); setSelectAllPages(false); }

  async function runBulkAction() {
    const action = bulkAction;
    const value  = action === "set_status" ? bulkValue : bulkTagInput.trim();
    if ((action === "add_tag" || action === "remove_tag") && !value) return;
    if (action === "set_status" && !value) return;
    if (action === "delete" && !window.confirm(`Delete ${selectAllPages ? total : checkedIds.size} contact(s)? This cannot be undone.`)) return;

    setBulkRunning(true);
    setBulkFeedback("");

    if (action === "add_tag" && !tags.some(t => t.name === value)) {
      await fetch("/api/tags", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: value }),
      });
      fetchTags();
    }

    const body = selectAllPages
      ? { select_all: true, filter_status: activeStatus, filter_search: search || null, action, value: value || null }
      : { ids: [...checkedIds], select_all: false, action, value: value || null };

    const res = await fetch("/api/contacts/bulk", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (res.ok) {
      setBulkFeedback(`${data.affected} contact(s) updated`);
      clearSelection();
      await fetchContacts();
      setTimeout(() => setBulkFeedback(""), 3000);
    } else {
      setBulkFeedback(data.detail || "Error");
    }
    setBulkRunning(false);
  }

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

        <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
          <form onSubmit={handleSearch} style={{ display: "flex", gap: 6 }}>
            <input value={searchInput} onChange={e => setSearchInput(e.target.value)}
              placeholder="Search business, owner, phone…"
              className="dg-input" style={{ width: 240 }} />
            <button type="submit" className="btn btn-primary">Search</button>
            {search && (
              <button type="button" className="btn btn-secondary"
                onClick={() => { setSearch(""); setSearchInput(""); setOffset(0); }}>
                Clear
              </button>
            )}
          </form>
          <button onClick={() => setShowAdd(true)} className="btn btn-primary" style={{ whiteSpace: "nowrap" }}>+ Add Contact</button>
          <button onClick={() => setShowImport(true)} className="btn btn-secondary" style={{ whiteSpace: "nowrap" }}>↑ Import CSV</button>
          <button onClick={() => setShowManageTags(true)} className="btn btn-secondary" style={{ whiteSpace: "nowrap" }}>🏷 Manage Tags</button>
        </div>
      </div>

      {/* Status filters */}
      <div style={{ padding: "8px 20px", borderBottom: "0.5px solid #1a2540",
                    display: "flex", gap: 10, alignItems: "center", overflowX: "auto", flexShrink: 0 }}>
        <div style={{ display: "flex", gap: 4 }}>
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
        <div style={{ width: 1, height: 18, background: "#1a2540", flexShrink: 0 }} />
        <select value={activeTag} onChange={e => { setActiveTag(e.target.value); setOffset(0); }}
          style={{ background: "#0a1020", border: "0.5px solid #1a2540", borderRadius: 4, color: "#8aaad0",
                   fontFamily: "'Share Tech Mono', monospace", fontSize: 10, padding: "5px 8px", cursor: "pointer", flexShrink: 0 }}>
          <option value="">ALL TAGS</option>
          {tags.map(t => <option key={t.id} value={t.name}>{t.name}</option>)}
        </select>
      </div>

      {/* Bulk action bar */}
      {someChecked && (
        <div style={{
          padding: "8px 20px", flexShrink: 0,
          background: "rgba(40,87,160,0.12)",
          borderBottom: "0.5px solid rgba(58,123,213,0.25)",
          display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap",
        }}>
          <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#6ab0ff", whiteSpace: "nowrap" }}>
            {selectAllPages ? `ALL ${total.toLocaleString()}` : checkedIds.size} SELECTED
          </span>

          {!selectAllPages && checkedIds.size === pageIds.length && total > checkedIds.size && (
            <button
              onClick={() => setSelectAllPages(true)}
              style={{ background: "none", border: "none", cursor: "pointer", fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a7bd5", textDecoration: "underline", padding: 0 }}
            >
              Select all {total.toLocaleString()} contacts
            </button>
          )}

          <div style={{ width: 1, height: 16, background: "rgba(58,123,213,0.3)" }} />

          {/* Action selector */}
          <div style={{ display: "flex", gap: 4 }}>
            {[
              ["set_status", "Set Status"],
              ["add_tag", "Add Tag"],
              ["remove_tag", "Remove Tag"],
              ["delete", "Delete"],
            ].map(([value, label]) => (
              <button key={value}
                onClick={() => { setBulkAction(value); setBulkValue(""); setBulkTagInput(""); }}
                style={{
                  background: bulkAction === value ? "#2857a0" : "#0a1020",
                  border: `0.5px solid ${bulkAction === value ? "#3a7bd5" : "#1a2540"}`,
                  borderRadius: 4, color: bulkAction === value ? "#c8dcff" : "#8aaad0",
                  fontFamily: "'Space Grotesk', sans-serif", fontSize: 11,
                  padding: "4px 10px", cursor: "pointer", whiteSpace: "nowrap",
                }}>
                {label}
              </button>
            ))}
          </div>

          {/* Value input based on action */}
          {bulkAction === "set_status" && (
            <select
              value={bulkValue}
              onChange={e => setBulkValue(e.target.value)}
              style={{ background: "#0a1020", border: "0.5px solid #1a2540", borderRadius: 4, color: "#8aaad0", fontFamily: "'Space Grotesk', sans-serif", fontSize: 11, padding: "4px 8px", cursor: "pointer" }}
            >
              <option value="">— pick status —</option>
              {STATUSES.filter(s => s.value !== "all").map(s => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          )}
          {bulkAction === "add_tag" && (
            <>
              <input
                value={bulkTagInput}
                onChange={e => setBulkTagInput(e.target.value)}
                placeholder="Tag name (new or existing)…"
                list="crm-bulk-tag-options"
                onKeyDown={e => e.key === "Enter" && runBulkAction()}
                style={{ background: "#0a1020", border: "0.5px solid #1a2540", borderRadius: 4, color: "#c4d0e8", fontFamily: "'Space Grotesk', sans-serif", fontSize: 11, padding: "4px 10px", width: 180, outline: "none" }}
              />
              <datalist id="crm-bulk-tag-options">
                {tags.map(t => <option key={t.id} value={t.name} />)}
              </datalist>
            </>
          )}
          {bulkAction === "remove_tag" && (
            <select
              value={bulkTagInput}
              onChange={e => setBulkTagInput(e.target.value)}
              style={{ background: "#0a1020", border: "0.5px solid #1a2540", borderRadius: 4, color: "#8aaad0", fontFamily: "'Space Grotesk', sans-serif", fontSize: 11, padding: "4px 8px", cursor: "pointer" }}
            >
              <option value="">— pick tag —</option>
              {tags.map(t => <option key={t.id} value={t.name}>{t.name}</option>)}
            </select>
          )}

          <button
            onClick={runBulkAction}
            disabled={bulkRunning}
            style={{
              background: bulkAction === "delete" ? "rgba(200,50,50,0.2)" : "linear-gradient(90deg,#2857a0,#3a7bd5)",
              border: bulkAction === "delete" ? "0.5px solid #8b2020" : "none",
              borderRadius: 4, color: bulkAction === "delete" ? "#e05555" : "#fff",
              fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600,
              fontSize: 11, padding: "5px 14px", cursor: bulkRunning ? "not-allowed" : "pointer", opacity: bulkRunning ? 0.6 : 1,
            }}
          >{bulkRunning ? "…" : bulkAction === "delete" ? "Delete" : "Apply"}</button>

          <button
            onClick={clearSelection}
            style={{ background: "none", border: "none", cursor: "pointer", fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80", padding: "4px 6px" }}
          >✕ Clear</button>

          {bulkFeedback && (
            <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#34d399" }}>{bulkFeedback}</span>
          )}
        </div>
      )}

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
                <th style={{ padding: "8px 10px 8px 14px", width: 32 }}>
                  <input
                    type="checkbox"
                    checked={allPageChecked}
                    onChange={togglePageAll}
                    style={{ accentColor: "#3a7bd5", width: 13, height: 13, cursor: "pointer" }}
                  />
                </th>
                {["Business","Owner","Phone","Grade","Status","Calls","Last Called","Last Disposition","State","Tags"].map(h => (
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
              {contacts.map(c => (
                <ContactRow
                  key={c.id}
                  contact={c}
                  checked={checkedIds.has(c.id)}
                  onCheck={toggleCheck}
                  onSelect={setSelected}
                  tagColor={tagColor}
                />
              ))}
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
          onUpdate={fetchContacts} onNavigate={onNavigate}
          tags={tags} tagColor={tagColor} onTagsChanged={fetchTags} />
      )}
      {showAdd && (
        <AddContactModal onClose={() => setShowAdd(false)} onSaved={fetchContacts} />
      )}
      {showImport && (
        <ImportModal onClose={() => setShowImport(false)} onImported={fetchContacts}
          tags={tags} onTagsChanged={fetchTags} />
      )}
      {showManageTags && (
        <ManageTagsModal tags={tags} onClose={() => setShowManageTags(false)}
          onChanged={() => { fetchTags(); fetchContacts(); }} />
      )}
    </div>
  );
}
