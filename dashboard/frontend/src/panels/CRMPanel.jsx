import React, { useState, useEffect, useCallback } from "react";

const STATUSES = [
  { value: "all",               label: "All" },
  { value: "new",               label: "New" },
  { value: "dialer-lead",       label: "Dialer Lead" },
  { value: "sms-handoff",       label: "SMS Handoff" },
  { value: "appointment-booked",label: "Booked" },
  { value: "not-interested",    label: "Not Interested" },
  { value: "send-info",         label: "Send Info" },
  { value: "voicemail",         label: "Voicemail" },
];

const STATUS_COLORS = {
  "new":                "bg-gray-700 text-gray-200",
  "dialer-lead":        "bg-blue-900 text-blue-200",
  "sms-handoff":        "bg-purple-900 text-purple-200",
  "appointment-booked": "bg-green-900 text-green-200",
  "not-interested":     "bg-red-900 text-red-200",
  "send-info":          "bg-yellow-900 text-yellow-200",
  "voicemail":          "bg-orange-900 text-orange-200",
};

const GRADE_COLORS = {
  A: "bg-green-800 text-green-200",
  B: "bg-blue-800 text-blue-200",
  C: "bg-yellow-800 text-yellow-200",
  D: "bg-red-800 text-red-200",
};

function Badge({ children, colorClass }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${colorClass}`}>
      {children}
    </span>
  );
}

function ContactRow({ contact, onSelect }) {
  return (
    <tr
      className="border-b border-gray-800 hover:bg-gray-900 cursor-pointer transition-colors"
      onClick={() => onSelect(contact)}
    >
      <td className="px-4 py-3 text-sm font-medium text-white truncate max-w-[180px]">
        {contact.business || <span className="text-gray-600">—</span>}
      </td>
      <td className="px-4 py-3 text-sm text-gray-300 truncate max-w-[140px]">
        {contact.owner || <span className="text-gray-600">—</span>}
      </td>
      <td className="px-4 py-3 text-sm text-gray-400 font-mono">
        {contact.phone || "—"}
      </td>
      <td className="px-4 py-3">
        {contact.grade
          ? <Badge colorClass={GRADE_COLORS[contact.grade] || "bg-gray-700 text-gray-200"}>{contact.grade}</Badge>
          : <span className="text-gray-600 text-sm">—</span>
        }
      </td>
      <td className="px-4 py-3">
        <Badge colorClass={STATUS_COLORS[contact.status] || "bg-gray-700 text-gray-200"}>
          {contact.status}
        </Badge>
      </td>
      <td className="px-4 py-3 text-sm text-gray-400 text-center">
        {contact.call_attempts}
      </td>
      <td className="px-4 py-3 text-sm text-gray-400 truncate max-w-[160px]">
        {contact.last_disposition || <span className="text-gray-600">—</span>}
      </td>
      <td className="px-4 py-3 text-sm text-gray-500 truncate max-w-[120px]">
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
    setStatus(newStatus);
    onUpdate();
    setSaving(false);
  }

  async function submitNote(e) {
    e.preventDefault();
    if (!note.trim()) return;
    await fetch(`/api/contacts/${contact.id}/note`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: note }),
    });
    setNote("");
    onUpdate();
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <aside className="relative w-[480px] bg-gray-900 border-l border-gray-800 h-full overflow-y-auto flex flex-col">
        <div className="px-6 py-4 border-b border-gray-800 flex items-center justify-between">
          <div>
            <div className="font-semibold text-white text-lg">{contact.business || "Unknown"}</div>
            <div className="text-sm text-gray-400">{contact.owner}</div>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-white text-xl">✕</button>
        </div>

        <div className="px-6 py-4 space-y-4 flex-1">
          {/* Info grid */}
          <div className="grid grid-cols-2 gap-3 text-sm">
            {[
              ["Phone", contact.phone],
              ["Email", contact.email],
              ["Website", contact.website],
              ["City", contact.city],
              ["State", contact.state],
              ["Grade", contact.grade],
              ["Calls", contact.call_attempts],
              ["Last Disposition", contact.last_disposition],
            ].map(([label, value]) => value ? (
              <div key={label}>
                <div className="text-gray-500 text-xs mb-0.5">{label}</div>
                <div className="text-gray-200 truncate">{value}</div>
              </div>
            ) : null)}
          </div>

          {/* Opener */}
          {contact.opener && (
            <div className="bg-gray-800 rounded-lg p-3">
              <div className="text-xs text-gray-500 mb-1">Cold Call Opener</div>
              <div className="text-sm text-gray-200 italic">"{contact.opener}"</div>
            </div>
          )}

          {/* Status change */}
          <div>
            <div className="text-xs text-gray-500 mb-2">Update Status</div>
            <div className="flex flex-wrap gap-2">
              {STATUSES.filter(s => s.value !== "all").map(({ value, label }) => (
                <button
                  key={value}
                  onClick={() => saveStatus(value)}
                  disabled={saving}
                  className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                    status === value
                      ? "bg-indigo-600 text-white"
                      : "bg-gray-800 text-gray-300 hover:bg-gray-700"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Notes */}
          {contact.notes && (
            <div>
              <div className="text-xs text-gray-500 mb-1">Notes</div>
              <div className="text-sm text-gray-300 bg-gray-800 rounded p-3 whitespace-pre-wrap">
                {contact.notes}
              </div>
            </div>
          )}

          {/* Add note */}
          <form onSubmit={submitNote} className="flex gap-2">
            <input
              value={note}
              onChange={e => setNote(e.target.value)}
              placeholder="Add a note..."
              className="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-indigo-500"
            />
            <button
              type="submit"
              className="px-3 py-2 bg-indigo-600 hover:bg-indigo-500 rounded text-sm text-white transition-colors"
            >
              Add
            </button>
          </form>
        </div>
      </aside>
    </div>
  );
}

export default function CRMPanel() {
  const [contacts, setContacts] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [activeStatus, setActiveStatus] = useState("all");
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState(null);
  const LIMIT = 50;

  const fetchContacts = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams({ limit: LIMIT, offset });
    if (activeStatus !== "all") params.set("status", activeStatus);
    if (search) params.set("search", search);
    try {
      const res = await fetch(`/api/contacts?${params}`);
      const data = await res.json();
      setContacts(data.contacts || []);
      setTotal(data.total || 0);
    } catch {
      setContacts([]);
    }
    setLoading(false);
  }, [activeStatus, search, offset]);

  useEffect(() => { fetchContacts(); }, [fetchContacts]);

  function handleSearch(e) {
    e.preventDefault();
    setSearch(searchInput);
    setOffset(0);
  }

  function handleStatusFilter(val) {
    setActiveStatus(val);
    setOffset(0);
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-800 flex items-center gap-4 shrink-0">
        <div>
          <h1 className="text-xl font-bold text-white">CRM</h1>
          <div className="text-sm text-gray-500">{total.toLocaleString()} contacts</div>
        </div>

        {/* Search */}
        <form onSubmit={handleSearch} className="ml-auto flex gap-2">
          <input
            value={searchInput}
            onChange={e => setSearchInput(e.target.value)}
            placeholder="Search business, owner, phone..."
            className="w-64 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-indigo-500"
          />
          <button
            type="submit"
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-sm text-white transition-colors"
          >
            Search
          </button>
          {search && (
            <button
              type="button"
              onClick={() => { setSearch(""); setSearchInput(""); setOffset(0); }}
              className="px-3 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm text-gray-400 transition-colors"
            >
              Clear
            </button>
          )}
        </form>
      </div>

      {/* Status filter */}
      <div className="px-6 py-2 border-b border-gray-800 flex gap-2 overflow-x-auto shrink-0">
        {STATUSES.map(({ value, label }) => (
          <button
            key={value}
            onClick={() => handleStatusFilter(value)}
            className={`px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors ${
              activeStatus === value
                ? "bg-indigo-600 text-white"
                : "bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-white"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        {loading ? (
          <div className="flex items-center justify-center h-32 text-gray-600">Loading...</div>
        ) : contacts.length === 0 ? (
          <div className="flex items-center justify-center h-32 text-gray-600">No contacts found</div>
        ) : (
          <table className="w-full">
            <thead className="sticky top-0 bg-gray-950 border-b border-gray-800">
              <tr>
                {["Business", "Owner", "Phone", "Grade", "Status", "Calls", "Last Disposition", "State"].map(h => (
                  <th key={h} className="px-4 py-2.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {contacts.map(c => (
                <ContactRow key={c.id} contact={c} onSelect={setSelected} />
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      <div className="px-6 py-3 border-t border-gray-800 flex items-center justify-between text-sm text-gray-500 shrink-0">
        <span>
          {offset + 1}–{Math.min(offset + LIMIT, total)} of {total.toLocaleString()}
        </span>
        <div className="flex gap-2">
          <button
            onClick={() => setOffset(Math.max(0, offset - LIMIT))}
            disabled={offset === 0}
            className="px-3 py-1 rounded bg-gray-800 disabled:opacity-30 hover:bg-gray-700 transition-colors"
          >
            ← Prev
          </button>
          <button
            onClick={() => setOffset(offset + LIMIT)}
            disabled={offset + LIMIT >= total}
            className="px-3 py-1 rounded bg-gray-800 disabled:opacity-30 hover:bg-gray-700 transition-colors"
          >
            Next →
          </button>
        </div>
      </div>

      {/* Contact drawer */}
      {selected && (
        <ContactDrawer
          contact={selected}
          onClose={() => setSelected(null)}
          onUpdate={() => { fetchContacts(); }}
        />
      )}
    </div>
  );
}
