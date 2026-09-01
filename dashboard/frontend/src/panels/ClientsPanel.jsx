import React, { useState, useEffect } from "react";
import { API } from "../api.js";
import { SECTIONS } from "../onboardingSections.js";

function OnboardingAnswers({ clientId }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(API(`/clients/${clientId}`))
      .then((r) => r.json())
      .then((data) => { setDetail(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [clientId]);

  if (loading) {
    return <div style={{ padding: 16, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>LOADING…</div>;
  }
  if (!detail) return null;

  const onboarding = detail.onboarding || {};
  const anyAnswers = Object.values(onboarding).some((s) => s.answers && Object.keys(s.answers).length > 0);

  return (
    <div style={{ padding: "14px 16px", borderTop: "1px solid rgba(58,123,213,0.1)", display: "flex", flexDirection: "column", gap: 16 }}>
      {!anyAnswers && (
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>
          NOTHING SUBMITTED YET
        </div>
      )}
      {SECTIONS.map((s) => {
        const section = onboarding[s.key];
        const answers = section?.answers || {};
        const hasAny = Object.values(answers).some((v) => (v || "").toString().trim());
        if (!hasAny) return null;
        return (
          <div key={s.key}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
              <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600, fontSize: 12.5, color: "#c4d0e8" }}>{s.title}</span>
              {section?.completed_at ? (
                <span className="badge badge-green" style={{ fontSize: 9 }}>COMPLETE</span>
              ) : (
                <span className="badge badge-amber" style={{ fontSize: 9 }}>IN PROGRESS</span>
              )}
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {s.questions.map((q) => {
                const val = (answers[q.key] || "").toString().trim();
                if (!val) return null;
                return (
                  <div key={q.key}>
                    <div style={{ fontSize: 11, color: "#5a7096", marginBottom: 2 }}>{q.label}</div>
                    <div style={{ fontSize: 12.5, color: "#d0e8ff", lineHeight: 1.5, whiteSpace: "pre-wrap" }}>{val}</div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function ClientRow({ client, onEdit, onRegenerate, onRevoke, onDelete, onLinkContact }) {
  const [copied, setCopied] = useState(false);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [linking, setLinking] = useState(false);
  const [pendingContact, setPendingContact] = useState(null);
  const [savingLink, setSavingLink] = useState(false);

  const copyLink = () => {
    navigator.clipboard.writeText(client.portal_url).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };

  const saveLink = async () => {
    setSavingLink(true);
    await onLinkContact(client.id, pendingContact?.id || null);
    setSavingLink(false);
    setLinking(false);
    setPendingContact(null);
  };

  const revoked = !!client.token_revoked_at;

  return (
    <div style={{ borderRadius: 10, background: "rgba(255,255,255,0.02)", marginBottom: 8, overflow: "hidden" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 14, padding: "14px 16px" }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600, fontSize: 14, color: "#d0e8ff" }}>
              {client.name}
            </span>
            <span className={`badge ${client.status === "active" ? "badge-green" : client.status === "paused" ? "badge-amber" : "badge-gray"}`}>
              {client.status}
            </span>
            {revoked && <span className="badge badge-red">TOKEN REVOKED</span>}
            {client.linked_contact ? (
              <span className="badge badge-blue" title="Onboarding follow-up will send this client's portal link">
                LINKED: {client.linked_contact.owner || client.linked_contact.business || "contact"}
              </span>
            ) : (
              <span className="badge badge-amber" title="No contact linked — the next-morning onboarding email/SMS has nothing to send for this client">
                NO CONTACT LINKED
              </span>
            )}
          </div>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 11, color: "#3a5a80", marginTop: 4 }}>
            Onboarding {client.onboarding_progress} · {client.contact_name || "no contact set"}
          </div>
        </div>

        <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={() => setShowOnboarding((s) => !s)}>
          {showOnboarding ? "HIDE ONBOARDING" : "VIEW ONBOARDING"}
        </button>
        <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={copyLink}>
          {copied ? "COPIED" : "COPY LINK"}
        </button>
        <a href={client.portal_url} target="_blank" rel="noreferrer" className="btn btn-secondary" style={{ fontSize: 10, textDecoration: "none" }}>
          VIEW PORTAL ↗
        </a>
        <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={() => { setPendingContact(client.linked_contact || null); setLinking((s) => !s); }}>
          {linking ? "CANCEL" : "LINK CONTACT"}
        </button>
        <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={() => onEdit(client)}>
          EDIT
        </button>
        {revoked ? (
          <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={() => onRegenerate(client.id)}>
            REGENERATE
          </button>
        ) : (
          <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={() => onRevoke(client.id)}>
            REVOKE
          </button>
        )}
        <button className="btn btn-danger" style={{ fontSize: 10 }} onClick={() => onDelete(client.id)}>
          DELETE
        </button>
      </div>
      {linking && (
        <div style={{ padding: "0 16px 14px", display: "flex", flexDirection: "column", gap: 10 }}>
          <ContactPicker selected={pendingContact} onSelect={setPendingContact} />
          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <button className="btn btn-primary" style={{ fontSize: 11 }} onClick={saveLink} disabled={savingLink}>
              {savingLink ? "SAVING…" : "SAVE LINK"}
            </button>
          </div>
        </div>
      )}
      {showOnboarding && <OnboardingAnswers clientId={client.id} />}
    </div>
  );
}

// Search-and-pick widget for linking the CRM contact/prospect this client's
// deal actually came from. Points contacts.client_id at the client once
// selected (create_client / link-contact endpoints) — this is what
// onboarding_sequence.py's next-morning follow-up resolves to find which
// client's portal link to send, so a client with no contact linked never
// gets that email/SMS sent for it.
function ContactPicker({ selected, onSelect, disabled }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    if (!query.trim()) { setResults([]); return; }
    setSearching(true);
    const t = setTimeout(async () => {
      const r = await fetch(API(`/contacts?search=${encodeURIComponent(query.trim())}&limit=8`));
      if (r.ok) {
        const data = await r.json();
        setResults(data.contacts || []);
      }
      setSearching(false);
    }, 300);
    return () => clearTimeout(t);
  }, [query]);

  if (selected) {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 12px", borderRadius: 8, background: "rgba(52,211,153,0.08)", border: "1px solid rgba(52,211,153,0.25)" }}>
        <span style={{ fontSize: 11, color: "#5a7096" }}>Linked to:</span>
        <span style={{ flex: 1, fontFamily: "'Space Grotesk', sans-serif", fontSize: 13, color: "#d0e8ff" }}>
          {selected.owner || selected.business || "Unnamed contact"}{selected.owner && selected.business ? ` — ${selected.business}` : ""}
        </span>
        {!disabled && (
          <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={() => onSelect(null)}>CHANGE</button>
        )}
      </div>
    );
  }

  return (
    <div style={{ position: "relative" }}>
      <input
        className="dg-input"
        placeholder="Link the contact this deal came from — search by business, owner, or phone…"
        value={query}
        onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        disabled={disabled}
      />
      {open && query.trim() && (
        <div style={{
          position: "absolute", top: "calc(100% + 4px)", left: 0, right: 0, zIndex: 10,
          background: "#0d1a3a", border: "1px solid rgba(58,123,213,0.25)", borderRadius: 8,
          maxHeight: 220, overflowY: "auto",
        }}>
          {searching && (
            <div style={{ padding: "10px 14px", fontSize: 11, color: "#3a5a80" }}>Searching…</div>
          )}
          {!searching && results.length === 0 && (
            <div style={{ padding: "10px 14px", fontSize: 11, color: "#3a5a80" }}>No matching contacts</div>
          )}
          {results.map((c) => (
            <div
              key={c.id}
              onClick={() => { onSelect(c); setQuery(""); setResults([]); setOpen(false); }}
              style={{ padding: "10px 14px", cursor: "pointer", borderBottom: "1px solid rgba(58,123,213,0.08)" }}
              onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(58,123,213,0.1)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
            >
              <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 13, color: "#d0e8ff" }}>
                {c.owner || "—"}{c.business ? ` — ${c.business}` : ""}
              </div>
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80", marginTop: 2 }}>{c.phone}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ClientForm({ initial, onSave, onCancel, saving }) {
  const [form, setForm] = useState({
    name: initial?.name || "",
    contact_name: initial?.contact_name || "",
    email: initial?.email || "",
    phone: initial?.phone || "",
    notes: initial?.notes || "",
  });
  const [linkedContact, setLinkedContact] = useState(initial?.linked_contact || null);

  return (
    <div className="glass-card" style={{ padding: "18px 20px", marginBottom: 20, display: "flex", flexDirection: "column", gap: 12 }}>
      <ContactPicker selected={linkedContact} onSelect={setLinkedContact} disabled={!!initial} />
      {initial && (
        <div style={{ fontSize: 11, color: "#5a7096" }}>
          To change the linked contact on an existing client, use the LINK CONTACT button on its row instead.
        </div>
      )}
      <input
        className="dg-input"
        placeholder="Practice name…"
        value={form.name}
        onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
        autoFocus
      />
      <div style={{ display: "flex", gap: 10 }}>
        <input
          className="dg-input"
          placeholder="Contact name"
          value={form.contact_name}
          onChange={(e) => setForm((f) => ({ ...f, contact_name: e.target.value }))}
          style={{ flex: 1 }}
        />
        <input
          className="dg-input"
          placeholder="Phone"
          value={form.phone}
          onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
          style={{ flex: 1 }}
        />
      </div>
      <input
        className="dg-input"
        placeholder="Email"
        value={form.email}
        onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
      />
      <textarea
        className="dg-input"
        rows={2}
        placeholder="Notes (optional)"
        value={form.notes}
        onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
        style={{ resize: "vertical" }}
      />
      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
        <button className="btn btn-secondary" onClick={onCancel} style={{ fontSize: 11 }}>CANCEL</button>
        <button
          className="btn btn-primary"
          onClick={() => onSave({ ...form, contact_id: initial ? undefined : (linkedContact?.id || undefined) })}
          disabled={saving || !form.name.trim()}
          style={{ fontSize: 11 }}
        >
          {saving ? "SAVING…" : "SAVE CLIENT"}
        </button>
      </div>
    </div>
  );
}

// Accepts a plain YouTube watch/share URL (or an already-embeddable URL) and
// normalizes it to an /embed/ URL — the only form that works inside an
// <iframe> — so the person adding a video can just paste what's in their
// browser bar instead of hand-building an embed link.
function toEmbedUrl(url) {
  const trimmed = (url || "").trim();
  const watch = trimmed.match(/youtube\.com\/watch\?v=([\w-]+)/);
  if (watch) return `https://www.youtube.com/embed/${watch[1]}`;
  const short = trimmed.match(/youtu\.be\/([\w-]+)/);
  if (short) return `https://www.youtube.com/embed/${short[1]}`;
  return trimmed;
}

function VideoRow({ video, onDelete }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 14, padding: "10px 14px", borderRadius: 8, background: "rgba(255,255,255,0.02)", marginBottom: 6 }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600, fontSize: 13, color: "#d0e8ff" }}>{video.title}</div>
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80", marginTop: 2, wordBreak: "break-all" }}>{video.embed_url}</div>
      </div>
      <button className="btn btn-danger" style={{ fontSize: 10 }} onClick={() => onDelete(video.id)}>DELETE</button>
    </div>
  );
}

function VideosSection() {
  const [videos, setVideos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ title: "", description: "", url: "" });
  const [saving, setSaving] = useState(false);

  const load = async () => {
    const r = await fetch(API("/onboarding-videos"));
    if (r.ok) setVideos(await r.json());
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const save = async () => {
    if (!form.title.trim() || !form.url.trim()) return;
    setSaving(true);
    await fetch(API("/onboarding-videos"), {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: form.title.trim(),
        description: form.description.trim() || undefined,
        embed_url: toEmbedUrl(form.url),
        sort_order: videos.length,
      }),
    });
    setForm({ title: "", description: "", url: "" });
    setShowForm(false);
    setSaving(false);
    load();
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this video from every client's Get Started Videos?")) return;
    await fetch(API(`/onboarding-videos/${id}`), { method: "DELETE" });
    load();
  };

  return (
    <div style={{ marginTop: 32 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <div>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 18, fontWeight: 700, color: "#f0f4ff" }}>
            Get Started Videos
          </div>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80", letterSpacing: "0.14em", marginTop: 3 }}>
            SHARED ACROSS EVERY CLIENT PORTAL
          </div>
        </div>
        <button className="btn btn-primary" style={{ fontSize: 11, padding: "8px 18px" }} onClick={() => setShowForm((s) => !s)}>
          {showForm ? "CANCEL" : "+ ADD VIDEO"}
        </button>
      </div>

      {showForm && (
        <div className="glass-card" style={{ padding: "18px 20px", marginBottom: 16, display: "flex", flexDirection: "column", gap: 12 }}>
          <input className="dg-input" placeholder="Title, e.g. Give Meta Ads Manager Access" value={form.title}
            onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} autoFocus />
          <input className="dg-input" placeholder="YouTube link (paste from your browser bar)" value={form.url}
            onChange={(e) => setForm((f) => ({ ...f, url: e.target.value }))} />
          <textarea className="dg-input" rows={2} placeholder="Description (optional)" value={form.description}
            onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} style={{ resize: "vertical" }} />
          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <button className="btn btn-primary" onClick={save} disabled={saving || !form.title.trim() || !form.url.trim()} style={{ fontSize: 11 }}>
              {saving ? "SAVING…" : "SAVE VIDEO"}
            </button>
          </div>
        </div>
      )}

      <div className="glass-card" style={{ padding: "10px 8px" }}>
        {loading && <div style={{ padding: 20, textAlign: "center", fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52" }}>LOADING…</div>}
        {!loading && videos.length === 0 && (
          <div style={{ padding: 20, textAlign: "center", fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52" }}>NO VIDEOS YET</div>
        )}
        {videos.map((v) => <VideoRow key={v.id} video={v} onDelete={remove} />)}
      </div>
    </div>
  );
}

const ACTION_ITEM_LINK_OPTIONS = [
  { value: "", label: "— no link —" },
  { value: "videos", label: "Get Started Videos" },
  { value: "leads", label: "Leads" },
  { value: "appointments", label: "Appointments" },
  { value: "dashboard", label: "Dashboard" },
];
const ACTION_ITEM_LINK_LABELS = Object.fromEntries(ACTION_ITEM_LINK_OPTIONS.map((o) => [o.value, o.label]));

function ActionItemRow({ item, onDelete }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 14, padding: "10px 14px", borderRadius: 8, background: "rgba(255,255,255,0.02)", marginBottom: 6 }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600, fontSize: 13, color: "#d0e8ff" }}>{item.title}</div>
        {item.description && (
          <div style={{ fontSize: 11, color: "#5a7096", marginTop: 2 }}>{item.description}</div>
        )}
        {item.link_tab && (
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", marginTop: 4, letterSpacing: "0.06em" }}>
            LINKS TO {(ACTION_ITEM_LINK_LABELS[item.link_tab] || item.link_tab).toUpperCase()}
          </div>
        )}
        {item.link_url && (
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", marginTop: 4, letterSpacing: "0.06em", wordBreak: "break-all" }}>
            LINKS TO {item.link_url}
          </div>
        )}
      </div>
      <button className="btn btn-danger" style={{ fontSize: 10 }} onClick={() => onDelete(item.id)}>DELETE</button>
    </div>
  );
}

function ActionItemsSection() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ title: "", description: "", link_tab: "", link_url: "" });
  const [saving, setSaving] = useState(false);

  const load = async () => {
    const r = await fetch(API("/action-items"));
    if (r.ok) setItems(await r.json());
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const save = async () => {
    if (!form.title.trim()) return;
    setSaving(true);
    await fetch(API("/action-items"), {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: form.title.trim(),
        description: form.description.trim() || undefined,
        link_tab: form.link_tab || undefined,
        link_url: form.link_url.trim() || undefined,
        sort_order: items.length,
      }),
    });
    setForm({ title: "", description: "", link_tab: "", link_url: "" });
    setShowForm(false);
    setSaving(false);
    load();
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this Next Step from every client's onboarding checklist?")) return;
    await fetch(API(`/action-items/${id}`), { method: "DELETE" });
    load();
  };

  return (
    <div style={{ marginTop: 32 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <div>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 18, fontWeight: 700, color: "#f0f4ff" }}>
            Onboarding Next Steps
          </div>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80", letterSpacing: "0.14em", marginTop: 3 }}>
            SHARED CHECKLIST ON EVERY CLIENT'S ONBOARDING TAB
          </div>
        </div>
        <button className="btn btn-primary" style={{ fontSize: 11, padding: "8px 18px" }} onClick={() => setShowForm((s) => !s)}>
          {showForm ? "CANCEL" : "+ ADD STEP"}
        </button>
      </div>

      {showForm && (
        <div className="glass-card" style={{ padding: "18px 20px", marginBottom: 16, display: "flex", flexDirection: "column", gap: 12 }}>
          <input className="dg-input" placeholder="Title, e.g. Give Meta Ads Manager Access" value={form.title}
            onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} autoFocus />
          <textarea className="dg-input" rows={2} placeholder="Description — what they need to do (optional)" value={form.description}
            onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} style={{ resize: "vertical" }} />
          <div>
            <div style={{ fontSize: 11, color: "#5a7096", marginBottom: 4 }}>Links to a portal tab (optional) — shows a "Go to…" button</div>
            <select className="dg-input" value={form.link_tab} onChange={(e) => setForm((f) => ({ ...f, link_tab: e.target.value }))}>
              {ACTION_ITEM_LINK_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
          <div>
            <div style={{ fontSize: 11, color: "#5a7096", marginBottom: 4 }}>Or an external link (optional) — e.g. a Calendly booking link</div>
            <input className="dg-input" placeholder="https://calendly.com/…" value={form.link_url}
              onChange={(e) => setForm((f) => ({ ...f, link_url: e.target.value }))} />
          </div>
          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <button className="btn btn-primary" onClick={save} disabled={saving || !form.title.trim()} style={{ fontSize: 11 }}>
              {saving ? "SAVING…" : "SAVE STEP"}
            </button>
          </div>
        </div>
      )}

      <div className="glass-card" style={{ padding: "10px 8px" }}>
        {loading && <div style={{ padding: 20, textAlign: "center", fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52" }}>LOADING…</div>}
        {!loading && items.length === 0 && (
          <div style={{ padding: 20, textAlign: "center", fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52" }}>NO STEPS YET</div>
        )}
        {items.map((item) => <ActionItemRow key={item.id} item={item} onDelete={remove} />)}
      </div>
    </div>
  );
}

export default function ClientsPanel() {
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const [saving, setSaving] = useState(false);
  const [newLink, setNewLink] = useState(null);

  const load = async () => {
    const r = await fetch(API("/clients"));
    if (r.ok) setClients(await r.json());
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const saveClient = async (form) => {
    setSaving(true);
    if (editing) {
      await fetch(API(`/clients/${editing.id}`), {
        method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      setEditing(null);
    } else {
      const r = await fetch(API("/clients"), {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (r.ok) {
        const created = await r.json();
        setNewLink(created.portal_url);
      }
    }
    setShowForm(false);
    setSaving(false);
    load();
  };

  const regenerate = async (id) => {
    await fetch(API(`/clients/${id}/regenerate-token`), { method: "POST" });
    load();
  };

  const revoke = async (id) => {
    await fetch(API(`/clients/${id}/revoke-token`), { method: "POST" });
    load();
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this client? Onboarding answers and portal access will be removed.")) return;
    await fetch(API(`/clients/${id}`), { method: "DELETE" });
    load();
  };

  const linkContact = async (id, contactId) => {
    await fetch(API(`/clients/${id}/link-contact`), {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ contact_id: contactId }),
    });
    load();
  };

  return (
    <div style={{ flex: 1, overflowY: "auto", padding: "24px 28px", display: "flex", flexDirection: "column", gap: 0 }}>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
        <div>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 24, fontWeight: 700, color: "#f0f4ff", letterSpacing: "-0.02em" }}>
            Clients
          </div>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80", letterSpacing: "0.14em", marginTop: 4 }}>
            {clients.length} CLIENT{clients.length !== 1 ? "S" : ""}
          </div>
        </div>
        <button
          className="btn btn-primary"
          onClick={() => { setEditing(null); setNewLink(null); setShowForm((s) => !s); }}
          style={{ fontSize: 11, padding: "8px 18px", letterSpacing: "0.08em" }}
        >
          {showForm ? "CANCEL" : "+ NEW CLIENT"}
        </button>
      </div>

      {newLink && (
        <div className="glass-card" style={{ padding: "14px 18px", marginBottom: 20, display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontSize: 12, color: "#8aaad0" }}>Portal link created:</span>
          <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 12, color: "#6ab0ff", flex: 1, wordBreak: "break-all" }}>{newLink}</span>
          <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={() => { navigator.clipboard.writeText(newLink); }}>COPY</button>
          <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={() => setNewLink(null)}>DISMISS</button>
        </div>
      )}

      {(showForm || editing) && (
        <ClientForm
          initial={editing}
          saving={saving}
          onSave={saveClient}
          onCancel={() => { setShowForm(false); setEditing(null); }}
        />
      )}

      <div className="glass-card" style={{ padding: "12px 8px" }}>
        {loading && (
          <div style={{ padding: "40px 20px", textAlign: "center", fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52", letterSpacing: "0.16em" }}>
            LOADING…
          </div>
        )}
        {!loading && clients.length === 0 && (
          <div style={{ padding: "40px 20px", textAlign: "center", fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52", letterSpacing: "0.16em" }}>
            NO CLIENTS YET
          </div>
        )}
        {clients.map((c) => (
          <ClientRow
            key={c.id}
            client={c}
            onEdit={(client) => { setEditing(client); setShowForm(false); setNewLink(null); }}
            onRegenerate={regenerate}
            onRevoke={revoke}
            onDelete={remove}
            onLinkContact={linkContact}
          />
        ))}
      </div>

      <VideosSection />
      <ActionItemsSection />
    </div>
  );
}
