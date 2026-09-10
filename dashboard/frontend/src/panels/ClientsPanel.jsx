import React, { useState, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
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

// The Details panel's sub-tabs — replaces what used to be 5 separate
// toggle buttons (Onboarding/Checklist/Sequences/Requests/Uploads), each
// with its own always-mounted-when-open panel. One toggle, one panel,
// pick which sub-view with a small pill row inside it.
const DETAILS_TABS = [
  { id: "onboarding", label: "Onboarding" },
  { id: "checklist", label: "Launch Checklist" },
  { id: "sequences", label: "Sequences" },
  { id: "marketing", label: "Marketing Setup" },
  { id: "requests", label: "Requests" },
  { id: "uploads", label: "Uploads" },
  { id: "resources", label: "Resources" },
];

function ClientRow({ client, onEdit, onRegenerate, onRevoke, onDelete, onLinkContact }) {
  const [copied, setCopied] = useState(false);
  const [showDetails, setShowDetails] = useState(false);
  const [detailsTab, setDetailsTab] = useState("onboarding");
  const [showMenu, setShowMenu] = useState(false);
  const [menuPos, setMenuPos] = useState({ top: 0, right: 0 });
  const menuButtonRef = useRef(null);
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
    <div style={{ borderRadius: 10, background: "rgba(255,255,255,0.02)", marginBottom: 8 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 14, padding: "14px 16px" }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600, fontSize: 14, color: "#d0e8ff" }}>
              {client.name}
            </span>
            <span className={`badge ${client.status === "active" ? "badge-green" : client.status === "paused" ? "badge-amber" : "badge-gray"}`}>
              {client.status}
            </span>
            {client.is_test && (
              <span className="badge badge-blue" title="Only this client's portal can use DigiGrowth's real shared Twilio/Gmail credentials (calling, SMS/email send) — every other client always gets the 'not connected yet' stub.">
                TEST CLIENT — LIVE INTEGRATIONS
              </span>
            )}
            {revoked && <span className="badge badge-red">TOKEN REVOKED</span>}
            {!client.booking_notification_enabled && (
              <span className="badge badge-gray" title="This client will not receive an SMS when a new appointment is booked for their lead">
                BOOKING SMS OFF
              </span>
            )}
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

        <a href={client.portal_url} target="_blank" rel="noreferrer" className="btn btn-secondary" style={{ fontSize: 10, textDecoration: "none" }}>
          VIEW PORTAL ↗
        </a>
        <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={copyLink}>
          {copied ? "COPIED" : "COPY LINK"}
        </button>
        <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={() => setShowDetails((s) => !s)}>
          {showDetails ? "HIDE DETAILS" : "DETAILS"}
        </button>
        <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={() => onEdit(client)}>
          EDIT
        </button>

        <button
          ref={menuButtonRef}
          className="btn btn-secondary"
          style={{ fontSize: 10, padding: "6px 10px" }}
          onClick={() => {
            if (!showMenu && menuButtonRef.current) {
              const r = menuButtonRef.current.getBoundingClientRect();
              setMenuPos({ top: r.bottom + 4, right: window.innerWidth - r.right });
            }
            setShowMenu((s) => !s);
          }}
          title="More actions"
        >
          ⋯
        </button>
        {showMenu && createPortal(
          <>
            <div style={{ position: "fixed", inset: 0, zIndex: 1000 }} onClick={() => setShowMenu(false)} />
            <div style={{
              position: "fixed", top: menuPos.top, right: menuPos.right, zIndex: 1001,
              background: "#0d1a3a", border: "1px solid rgba(58,123,213,0.25)", borderRadius: 8,
              minWidth: 160, overflow: "hidden", boxShadow: "0 8px 24px rgba(0,0,0,0.4)",
            }}>
              <button
                onClick={() => { setPendingContact(client.linked_contact || null); setLinking((s) => !s); setShowMenu(false); }}
                style={menuItemStyle}
              >
                {linking ? "Cancel Linking" : "Link Contact"}
              </button>
              {revoked ? (
                <button onClick={() => { onRegenerate(client.id); setShowMenu(false); }} style={menuItemStyle}>
                  Regenerate Token
                </button>
              ) : (
                <button onClick={() => { onRevoke(client.id); setShowMenu(false); }} style={menuItemStyle}>
                  Revoke Token
                </button>
              )}
              <button
                onClick={() => { onDelete(client.id); setShowMenu(false); }}
                style={{ ...menuItemStyle, color: "#e05c5c" }}
              >
                Delete Client
              </button>
            </div>
          </>,
          document.body
        )}
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
      {showDetails && (
        <div>
          <div style={{ display: "flex", gap: 6, padding: "10px 16px 0", borderTop: "1px solid rgba(58,123,213,0.1)" }}>
            {DETAILS_TABS.map((t) => (
              <button
                key={t.id}
                onClick={() => setDetailsTab(t.id)}
                style={{
                  background: detailsTab === t.id ? "rgba(58,123,213,0.14)" : "transparent",
                  border: detailsTab === t.id ? "1px solid rgba(58,123,213,0.3)" : "1px solid transparent",
                  borderRadius: 999, cursor: "pointer", padding: "5px 12px",
                  fontFamily: "'Space Grotesk', sans-serif", fontSize: 11, fontWeight: 600,
                  color: detailsTab === t.id ? "#9cc4f5" : "#5a7aa0",
                }}
              >
                {t.label}
              </button>
            ))}
          </div>
          {detailsTab === "onboarding" && <OnboardingAnswers clientId={client.id} />}
          {detailsTab === "checklist" && <ClientLaunchChecklist clientId={client.id} />}
          {detailsTab === "sequences" && <ClientSequences clientId={client.id} />}
          {detailsTab === "marketing" && <ClientMarketingSetup clientId={client.id} />}
          {detailsTab === "requests" && <ClientRequests clientId={client.id} />}
          {detailsTab === "uploads" && <ClientUploads clientId={client.id} />}
          {detailsTab === "resources" && <ClientResources clientId={client.id} />}
        </div>
      )}
    </div>
  );
}

const menuItemStyle = {
  display: "block", width: "100%", textAlign: "left", padding: "9px 14px",
  background: "none", border: "none", cursor: "pointer",
  fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, color: "#c4d0e8",
};

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
    booking_notification_enabled: initial?.booking_notification_enabled ?? true,
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
      <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "#8aaad0", cursor: "pointer" }}>
        <input
          type="checkbox"
          checked={form.booking_notification_enabled}
          onChange={(e) => setForm((f) => ({ ...f, booking_notification_enabled: e.target.checked }))}
        />
        Text this client when a new appointment is booked for their lead
      </label>
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
            SHARED CHECKLIST ON EVERY CLIENT'S ONBOARDING TAB — THE CLIENT CHECKS THESE OFF
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

// ---------------- Launch checklist (agency-run "To Do" tab) ----------------
//
// Separate catalog from ActionItemsSection above: those are onboarding
// steps the CLIENT completes. This is DigiGrowth's own launch-readiness
// checklist — the client's portal shows it read-only (LaunchChecklistTab in
// ClientPortal.jsx); completion is set here, per-client, by whoever on the
// team actually does the work (see the per-client toggle panel added to
// ClientRow below).

const CHECKLIST_PHASE_OPTIONS = [
  { value: "prelaunch", label: "Prelaunch" },
  { value: "post_launch", label: "Post Launch" },
];

function ChecklistItemRow({ item, onDelete }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 14, padding: "10px 14px", borderRadius: 8, background: "rgba(255,255,255,0.02)", marginBottom: 6 }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600, fontSize: 13, color: "#d0e8ff" }}>{item.title}</div>
        {item.description && (
          <div style={{ fontSize: 11, color: "#5a7096", marginTop: 2 }}>{item.description}</div>
        )}
      </div>
      <button className="btn btn-danger" style={{ fontSize: 10 }} onClick={() => onDelete(item.id)}>DELETE</button>
    </div>
  );
}

function LaunchChecklistSection() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ title: "", description: "", phase: "prelaunch" });
  const [saving, setSaving] = useState(false);

  const load = async () => {
    const r = await fetch(API("/launch-checklist-items"));
    if (r.ok) setItems(await r.json());
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const save = async () => {
    if (!form.title.trim()) return;
    setSaving(true);
    await fetch(API("/launch-checklist-items"), {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: form.title.trim(),
        description: form.description.trim() || undefined,
        phase: form.phase,
        sort_order: items.filter((i) => i.phase === form.phase).length,
      }),
    });
    setForm({ title: "", description: "", phase: form.phase });
    setShowForm(false);
    setSaving(false);
    load();
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this item from the launch checklist? It'll disappear from every client's To Do tab.")) return;
    await fetch(API(`/launch-checklist-items/${id}`), { method: "DELETE" });
    load();
  };

  const prelaunch = items.filter((i) => (i.phase || "prelaunch") === "prelaunch");
  const postLaunch = items.filter((i) => i.phase === "post_launch");

  return (
    <div style={{ marginTop: 32 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <div>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 18, fontWeight: 700, color: "#f0f4ff" }}>
            Launch Checklist (To Do tab)
          </div>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80", letterSpacing: "0.14em", marginTop: 3 }}>
            AGENCY-COMPLETED — CLIENT SEES READ-ONLY PROGRESS. TOGGLE PER CLIENT ON ITS ROW BELOW.
          </div>
        </div>
        <button className="btn btn-primary" style={{ fontSize: 11, padding: "8px 18px" }} onClick={() => setShowForm((s) => !s)}>
          {showForm ? "CANCEL" : "+ ADD ITEM"}
        </button>
      </div>

      {showForm && (
        <div className="glass-card" style={{ padding: "18px 20px", marginBottom: 16, display: "flex", flexDirection: "column", gap: 12 }}>
          <input className="dg-input" placeholder="Title, e.g. Set up email marketing" value={form.title}
            onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} autoFocus />
          <textarea className="dg-input" rows={2} placeholder="Description (optional)" value={form.description}
            onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} style={{ resize: "vertical" }} />
          <div>
            <div style={{ fontSize: 11, color: "#5a7096", marginBottom: 4 }}>Phase</div>
            <select className="dg-input" value={form.phase} onChange={(e) => setForm((f) => ({ ...f, phase: e.target.value }))}>
              {CHECKLIST_PHASE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <button className="btn btn-primary" onClick={save} disabled={saving || !form.title.trim()} style={{ fontSize: 11 }}>
              {saving ? "SAVING…" : "SAVE ITEM"}
            </button>
          </div>
        </div>
      )}

      {CHECKLIST_PHASE_OPTIONS.map((phaseOpt) => {
        const phaseItems = phaseOpt.value === "prelaunch" ? prelaunch : postLaunch;
        return (
          <div key={phaseOpt.value} style={{ marginBottom: 18 }}>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80", letterSpacing: "0.12em", marginBottom: 8 }}>
              {phaseOpt.label.toUpperCase()}
            </div>
            <div className="glass-card" style={{ padding: "10px 8px" }}>
              {loading && <div style={{ padding: 20, textAlign: "center", fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52" }}>LOADING…</div>}
              {!loading && phaseItems.length === 0 && (
                <div style={{ padding: 20, textAlign: "center", fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52" }}>NO ITEMS YET</div>
              )}
              {phaseItems.map((item) => <ChecklistItemRow key={item.id} item={item} onDelete={remove} />)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// Per-client toggle panel — expandable from ClientRow, lets whoever's doing
// the setup work mark this specific client's launch-checklist items done as
// they actually get completed. Read-only catalog (titles/phases come from
// LaunchChecklistSection above); only completion status is per-client here.
function ClientLaunchChecklist({ clientId }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    const r = await fetch(API(`/clients/${clientId}/launch-checklist`));
    if (r.ok) setItems(await r.json());
    setLoading(false);
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [clientId]);

  const toggle = async (item) => {
    const completed = !item.completed_at;
    const r = await fetch(API(`/clients/${clientId}/launch-checklist/${item.id}`), {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ completed }),
    });
    if (r.ok) {
      const updated = await r.json();
      setItems((prev) => prev.map((i) => (i.id === item.id ? { ...i, completed_at: updated.completed_at } : i)));
    }
  };

  if (loading) {
    return <div style={{ padding: 16, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>LOADING…</div>;
  }
  if (items.length === 0) {
    return (
      <div style={{ padding: 16, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>
        NO LAUNCH CHECKLIST ITEMS YET — ADD SOME BELOW UNDER "LAUNCH CHECKLIST (TO DO TAB)"
      </div>
    );
  }

  return (
    <div style={{ padding: "14px 16px", borderTop: "1px solid rgba(58,123,213,0.1)", display: "flex", flexDirection: "column", gap: 8 }}>
      {items.map((item) => {
        const done = !!item.completed_at;
        return (
          <div
            key={item.id}
            style={{
              padding: "8px 12px", borderRadius: 8,
              background: done ? "rgba(20,200,130,0.06)" : "rgba(255,255,255,0.02)",
            }}
          >
            <div onClick={() => toggle(item)} style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }}>
              <span style={{
                flexShrink: 0, width: 16, height: 16, borderRadius: 4,
                border: done ? "1px solid #14c882" : "1px solid rgba(58,123,213,0.35)",
                background: done ? "#14c882" : "transparent",
                color: "#06110c", fontSize: 10, fontWeight: 700,
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>{done ? "✓" : ""}</span>
              <span style={{ fontSize: 12.5, color: done ? "#8fd9bd" : "#d0e8ff", textDecoration: done ? "line-through" : "none" }}>
                {item.title}
              </span>
            </div>
            {item.description && (
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#5a7aa0", marginTop: 6, marginLeft: 26, lineHeight: 1.5, whiteSpace: "pre-wrap" }}>
                {item.description}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// Per-client editable outreach copy — Appointment Reminder / No Show /
// Cancellation, previewed read-only in the client's own portal (Sequences
// tab). Not wired to any real send yet; this is just content editing.
const SEQUENCE_GROUP_LABELS = {
  appointment_reminder: "Appointment Reminders",
  no_show: "No Show Follow-Up",
  cancellation: "Cancellation Follow-Up",
};
const SEQUENCE_GROUP_ORDER = ["appointment_reminder", "no_show", "cancellation"];

function SequenceStepEditor({ step, onSaved }) {
  const [subject, setSubject] = useState(step.subject || "");
  const [body, setBody] = useState(step.body || "");
  const [saving, setSaving] = useState(false);
  const dirty = subject !== (step.subject || "") || body !== (step.body || "");

  const save = async () => {
    setSaving(true);
    const r = await fetch(API(`/clients/${step.client_id}/sequences/${step.id}`), {
      method: "PATCH", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ subject: subject || null, body }),
    });
    if (r.ok) onSaved(await r.json());
    setSaving(false);
  };

  return (
    <div style={{ padding: "10px 12px", borderRadius: 8, background: "rgba(255,255,255,0.02)", marginBottom: 8 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
        <span style={{ fontSize: 12.5, fontWeight: 600, color: "#d0e8ff", flex: 1 }}>{step.label}</span>
        <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5" }}>{step.channel.toUpperCase()}</span>
      </div>
      {step.channel === "email" && (
        <input
          className="dg-input" placeholder="Subject" value={subject}
          onChange={(e) => setSubject(e.target.value)}
          style={{ width: "100%", boxSizing: "border-box", fontSize: 12, marginBottom: 6 }}
        />
      )}
      <textarea
        className="dg-input" rows={3} value={body}
        onChange={(e) => setBody(e.target.value)}
        style={{ width: "100%", boxSizing: "border-box", fontSize: 12, resize: "vertical", marginBottom: 6 }}
      />
      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={save} disabled={saving || !dirty}>
          {saving ? "SAVING…" : "SAVE"}
        </button>
      </div>
    </div>
  );
}

function ClientSequences({ clientId }) {
  const [steps, setSteps] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    const r = await fetch(API(`/clients/${clientId}/sequences`));
    if (r.ok) setSteps((await r.json()).map((s) => ({ ...s, client_id: clientId })));
    setLoading(false);
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [clientId]);

  if (loading) return <div style={{ padding: 16, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>LOADING…</div>;
  if (steps.length === 0) {
    return <div style={{ padding: 16, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>NO SEQUENCE STEPS FOR THIS CLIENT</div>;
  }

  return (
    <div style={{ padding: "14px 16px", borderTop: "1px solid rgba(58,123,213,0.1)" }}>
      {SEQUENCE_GROUP_ORDER.map((key) => {
        const group = steps.filter((s) => s.sequence_key === key);
        if (group.length === 0) return null;
        return (
          <div key={key} style={{ marginBottom: 14 }}>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80", letterSpacing: "0.1em", marginBottom: 6 }}>
              {(SEQUENCE_GROUP_LABELS[key] || key).toUpperCase()}
            </div>
            {group.map((step) => (
              <SequenceStepEditor
                key={step.id}
                step={step}
                onSaved={(updated) => setSteps((prev) => prev.map((s) => (s.id === updated.id ? { ...updated, client_id: clientId } : s)))}
              />
            ))}
          </div>
        );
      })}
    </div>
  );
}

// Client "please fix/do this" requests, submitted from the portal's To Do
// tab. Mark done here as they get handled.
function ClientRequests({ clientId }) {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    const r = await fetch(API(`/clients/${clientId}/requests`));
    if (r.ok) setRequests(await r.json());
    setLoading(false);
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [clientId]);

  const setStatus = async (request, status) => {
    const r = await fetch(API(`/clients/${clientId}/requests/${request.id}`), {
      method: "PATCH", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    if (r.ok) {
      const updated = await r.json();
      setRequests((prev) => prev.map((req) => (req.id === request.id ? updated : req)));
    }
  };

  if (loading) return <div style={{ padding: 16, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>LOADING…</div>;
  if (requests.length === 0) {
    return <div style={{ padding: 16, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>NO REQUESTS FROM THIS CLIENT YET</div>;
  }

  return (
    <div style={{ padding: "14px 16px", borderTop: "1px solid rgba(58,123,213,0.1)", display: "flex", flexDirection: "column", gap: 8 }}>
      {requests.map((r) => {
        const done = r.status === "done";
        return (
          <div key={r.id} style={{
            display: "flex", alignItems: "flex-start", gap: 10, padding: "10px 12px", borderRadius: 8,
            background: done ? "rgba(20,200,130,0.05)" : "rgba(240,160,40,0.06)",
          }}>
            <input
              type="checkbox" checked={done}
              onChange={() => setStatus(r, done ? "open" : "done")}
              style={{ marginTop: 3, flexShrink: 0, cursor: "pointer" }}
            />
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 12.5, color: done ? "#8fd9bd" : "#d0e8ff", textDecoration: done ? "line-through" : "none", lineHeight: 1.5 }}>
                {r.message}
              </div>
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80", marginTop: 4 }}>
                {new Date(r.created_at).toLocaleString()}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// Files a client uploaded via the portal's Upload tab. Bytes live in
// Cloudflare R2 (r2_storage.py) — this just lists metadata and gets a
// presigned download link on demand.
function ClientUploads({ clientId }) {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    const r = await fetch(API(`/clients/${clientId}/uploads`));
    if (r.ok) setFiles(await r.json());
    setLoading(false);
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [clientId]);

  const download = async (file) => {
    const r = await fetch(API(`/clients/${clientId}/uploads/${file.id}/download`));
    if (r.ok) {
      const { url } = await r.json();
      window.open(url, "_blank", "noreferrer");
    } else {
      window.alert("Couldn't get a download link — file storage may not be connected yet.");
    }
  };

  const remove = async (file) => {
    if (!window.confirm(`Delete "${file.file_name}"? This can't be undone.`)) return;
    await fetch(API(`/clients/${clientId}/uploads/${file.id}`), { method: "DELETE" });
    load();
  };

  if (loading) return <div style={{ padding: 16, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>LOADING…</div>;
  if (files.length === 0) {
    return <div style={{ padding: 16, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>NO FILES UPLOADED YET</div>;
  }

  return (
    <div style={{ padding: "14px 16px", borderTop: "1px solid rgba(58,123,213,0.1)", display: "flex", flexDirection: "column", gap: 8 }}>
      {files.map((f) => (
        <div key={f.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 12px", borderRadius: 8, background: "rgba(255,255,255,0.02)" }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 12.5, color: "#d0e8ff", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{f.file_name}</div>
            {f.notes && <div style={{ fontSize: 11, color: "#5a7096", marginTop: 2 }}>{f.notes}</div>}
          </div>
          <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={() => download(f)}>DOWNLOAD</button>
          <button className="btn btn-danger" style={{ fontSize: 10 }} onClick={() => remove(f)}>DELETE</button>
        </div>
      ))}
    </div>
  );
}

// One of the three single-value resource fields living directly on the
// client row (ads_manager_resource / registrar_resource / hosting_resource).
// Free text — a link, a login note, an account ID, whatever's easiest to
// paste for that platform.
function ResourceField({ clientId, field, label, placeholder, value, onSaved }) {
  const [text, setText] = useState(value || "");
  const [saving, setSaving] = useState(false);
  const dirty = text !== (value || "");

  useEffect(() => { setText(value || ""); }, [value]);

  const save = async () => {
    setSaving(true);
    const r = await fetch(API(`/clients/${clientId}`), {
      method: "PATCH", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ [field]: text }),
    });
    if (r.ok) onSaved(await r.json());
    setSaving(false);
  };

  return (
    <div style={{ padding: "10px 12px", borderRadius: 8, background: "rgba(255,255,255,0.02)", marginBottom: 8 }}>
      <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a7bd5", letterSpacing: "0.08em", marginBottom: 6 }}>
        {label.toUpperCase()}
      </div>
      <textarea
        className="dg-input" rows={2} placeholder={placeholder} value={text}
        onChange={(e) => setText(e.target.value)}
        style={{ width: "100%", boxSizing: "border-box", fontSize: 12, resize: "vertical", marginBottom: 6 }}
      />
      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={save} disabled={saving || !dirty}>
          {saving ? "SAVING…" : "SAVE"}
        </button>
      </div>
    </div>
  );
}

function MiscResourceRow({ resource, onDelete }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 14, padding: "10px 14px", borderRadius: 8, background: "rgba(255,255,255,0.02)", marginBottom: 6 }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600, fontSize: 13, color: "#d0e8ff" }}>{resource.label}</div>
        <div style={{ fontSize: 12, color: "#8aaad0", marginTop: 2, wordBreak: "break-all", whiteSpace: "pre-wrap" }}>{resource.value}</div>
      </div>
      <button className="btn btn-danger" style={{ fontSize: 10 }} onClick={() => onDelete(resource.id)}>DELETE</button>
    </div>
  );
}

// Per-client resource hub: three single-value platform fields (Ads Manager,
// Registrar, Hosting) stored on the client row, plus an open-ended list for
// everything else (Drive links, brand assets, marketing material, etc.).
// Admin-only reference — nothing here is shown in the client's own portal.
const MARKETING_STEPS = [
  {
    key: "sms", label: "SMS Marketing",
    status: (cfg) => (cfg?.twilio_number ? `Provisioned — ${cfg.twilio_number}` : "Not provisioned"),
    done: (cfg) => Boolean(cfg?.twilio_number),
  },
  {
    key: "email", label: "Email Marketing",
    status: (cfg) => (cfg?.gmail_refresh_token
      ? `Connected — ${cfg.gmail_sender_email || "mailbox linked"}`
      : "Not connected"),
    done: (cfg) => Boolean(cfg?.gmail_refresh_token),
  },
  {
    key: "response_ai", label: "Response AI (Appointwise)",
    status: (cfg) => (cfg?.appointwise_agent_id
      ? `Connected — ${cfg.appointwise_agent_id}${cfg.appointwise_webhook_url ? "" : " (webhook not set)"}`
      : "Not connected"),
    done: (cfg) => Boolean(cfg?.appointwise_agent_id && cfg?.appointwise_webhook_url),
  },
  {
    key: "landing_page", label: "Landing Page",
    status: (cfg) => (cfg?.landing_page_url ? cfg.landing_page_url : "Not created"),
    done: (cfg) => Boolean(cfg?.landing_page_url),
  },
  {
    key: "ad_creatives", label: "Paid Ad Creatives",
    status: (cfg) => {
      const n = cfg?.ad_creative_status ? Object.keys(cfg.ad_creative_status).length : 0;
      return n > 0 ? `${n} asset${n === 1 ? "" : "s"} tracked` : "None yet";
    },
    done: (cfg) => Boolean(cfg?.ad_creative_status && Object.keys(cfg.ad_creative_status).length > 0),
  },
];

function ClientMarketingSetup({ clientId }) {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [provisioning, setProvisioning] = useState(false);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(null); // field name currently being edited
  const [draft, setDraft] = useState("");
  const [draft2, setDraft2] = useState(""); // second field, for multi-field editors (email)
  const [saving, setSaving] = useState(false);
  const [testEmailTo, setTestEmailTo] = useState("");
  const [testingEmail, setTestingEmail] = useState(false);

  const load = async () => {
    const r = await fetch(API(`/clients/${clientId}/marketing-config`));
    if (r.ok) setConfig(await r.json());
    setLoading(false);
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [clientId]);

  const provisionNumber = async () => {
    setProvisioning(true);
    setError("");
    try {
      const r = await fetch(API(`/clients/${clientId}/marketing-config/provision-sms`), { method: "POST" });
      if (!r.ok) {
        const detail = await r.json().catch(() => null);
        throw new Error(detail?.detail || "Failed to provision a number");
      }
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setProvisioning(false);
    }
  };

  const startEdit = (field, current) => {
    setEditing(field);
    setDraft(current || "");
  };

  const saveField = async (field) => {
    setSaving(true);
    await fetch(API(`/clients/${clientId}/marketing-config`), {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ [field]: draft.trim() || null }),
    });
    setEditing(null);
    setSaving(false);
    load();
  };

  const saveFields = async (fields) => {
    setSaving(true);
    await fetch(API(`/clients/${clientId}/marketing-config`), {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(fields),
    });
    setEditing(null);
    setSaving(false);
    load();
  };

  const sendTestEmail = async () => {
    if (!testEmailTo.trim()) return;
    setTestingEmail(true);
    setError("");
    try {
      const r = await fetch(API(`/clients/${clientId}/marketing-config/test-email`), {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ to: testEmailTo.trim() }),
      });
      if (!r.ok) {
        const detail = await r.json().catch(() => null);
        throw new Error(detail?.detail || "Failed to send test email");
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setTestingEmail(false);
    }
  };

  if (loading) {
    return <div style={{ padding: 16, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>LOADING…</div>;
  }

  return (
    <div style={{ padding: "14px 16px", borderTop: "1px solid rgba(58,123,213,0.1)" }}>
      <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a4a7a", marginBottom: 12, lineHeight: 1.5 }}>
        This client's OWN marketing infrastructure — their Twilio number, their email-sending
        domain, their Appointwise agent, their landing page, their ad creatives. Separate from
        DigiGrowth's own outreach system.
      </div>

      {MARKETING_STEPS.map((step) => (
        <div key={step.key} style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "10px 12px", borderRadius: 8, background: "rgba(255,255,255,0.02)", marginBottom: 8,
        }}>
          <div>
            <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, fontWeight: 600, color: "#c8d8f0", display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ color: step.done(config) ? "#4ade80" : "#5a7aa0" }}>{step.done(config) ? "✓" : "○"}</span>
              {step.label}
            </div>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#5a7aa0", marginTop: 2 }}>
              {step.status(config)}
            </div>
          </div>
          {step.key === "sms" && !config?.twilio_number && (
            <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={provisionNumber} disabled={provisioning}>
              {provisioning ? "PROVISIONING…" : "BUY NUMBER"}
            </button>
          )}
          {step.key === "email" && (
            editing === "gmail" ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 6, alignItems: "flex-end" }}>
                <input className="dg-input" style={{ fontSize: 11, width: 220 }} value={draft2} placeholder="hello@clientdomain.com"
                  onChange={(e) => setDraft2(e.target.value)} autoFocus />
                <input className="dg-input" style={{ fontSize: 11, width: 220 }} value={draft} placeholder="Gmail refresh token (from reauth_google.py)"
                  onChange={(e) => setDraft(e.target.value)} />
                <button className="btn btn-primary" style={{ fontSize: 10 }}
                  onClick={() => saveFields({ gmail_sender_email: draft2.trim() || null, gmail_refresh_token: draft.trim() || null })}
                  disabled={saving}>
                  SAVE
                </button>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 6, alignItems: "flex-end" }}>
                <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={() => { setEditing("gmail"); setDraft(config?.gmail_refresh_token || ""); setDraft2(config?.gmail_sender_email || ""); }}>
                  {config?.gmail_refresh_token ? "EDIT" : "CONNECT MAILBOX"}
                </button>
                {config?.gmail_refresh_token && (
                  <div style={{ display: "flex", gap: 6 }}>
                    <input className="dg-input" style={{ fontSize: 11, width: 150 }} value={testEmailTo} placeholder="test@…"
                      onChange={(e) => setTestEmailTo(e.target.value)} />
                    <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={sendTestEmail} disabled={testingEmail || !testEmailTo.trim()}>
                      {testingEmail ? "SENDING…" : "TEST"}
                    </button>
                  </div>
                )}
              </div>
            )
          )}
          {step.key === "response_ai" && (
            editing === "appointwise" ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 6, alignItems: "flex-end" }}>
                <input className="dg-input" style={{ fontSize: 11, width: 220 }} value={draft} placeholder="Appointwise agent ID"
                  onChange={(e) => setDraft(e.target.value)} autoFocus />
                <input className="dg-input" style={{ fontSize: 11, width: 220 }} value={draft2} placeholder="Appointwise webhook URL"
                  onChange={(e) => setDraft2(e.target.value)} />
                <button className="btn btn-primary" style={{ fontSize: 10 }}
                  onClick={() => saveFields({ appointwise_agent_id: draft.trim() || null, appointwise_webhook_url: draft2.trim() || null })}
                  disabled={saving}>
                  SAVE
                </button>
              </div>
            ) : (
              <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={() => { setEditing("appointwise"); setDraft(config?.appointwise_agent_id || ""); setDraft2(config?.appointwise_webhook_url || ""); }}>
                {config?.appointwise_agent_id ? "EDIT" : "CONNECT"}
              </button>
            )
          )}
          {step.key === "landing_page" && (
            editing === "landing_page_url" ? (
              <div style={{ display: "flex", gap: 6 }}>
                <input className="dg-input" style={{ fontSize: 11 }} value={draft} placeholder="https://…"
                  onChange={(e) => setDraft(e.target.value)} autoFocus />
                <button className="btn btn-primary" style={{ fontSize: 10 }} onClick={() => saveField("landing_page_url")} disabled={saving}>SAVE</button>
              </div>
            ) : (
              <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={() => startEdit("landing_page_url", config?.landing_page_url)}>
                {config?.landing_page_url ? "EDIT" : "SET URL"}
              </button>
            )
          )}
        </div>
      ))}

      {error && (
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#e05c5c", marginTop: 4 }}>
          {error}
        </div>
      )}
    </div>
  );
}

function ClientResources({ clientId }) {
  const [client, setClient] = useState(null);
  const [resources, setResources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ label: "", value: "" });
  const [saving, setSaving] = useState(false);

  const load = async () => {
    const [cr, rr] = await Promise.all([
      fetch(API(`/clients/${clientId}`)),
      fetch(API(`/clients/${clientId}/resources`)),
    ]);
    if (cr.ok) setClient(await cr.json());
    if (rr.ok) setResources(await rr.json());
    setLoading(false);
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [clientId]);

  const addResource = async () => {
    if (!form.label.trim() || !form.value.trim()) return;
    setSaving(true);
    await fetch(API(`/clients/${clientId}/resources`), {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ label: form.label.trim(), value: form.value.trim(), sort_order: resources.length }),
    });
    setForm({ label: "", value: "" });
    setShowForm(false);
    setSaving(false);
    load();
  };

  const removeResource = async (id) => {
    if (!window.confirm("Delete this resource?")) return;
    await fetch(API(`/clients/${clientId}/resources/${id}`), { method: "DELETE" });
    load();
  };

  if (loading) {
    return <div style={{ padding: 16, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>LOADING…</div>;
  }

  return (
    <div style={{ padding: "14px 16px", borderTop: "1px solid rgba(58,123,213,0.1)" }}>
      <ResourceField
        clientId={clientId} field="ads_manager_resource" label="Ads Manager"
        placeholder="e.g. Business Manager link, ID, or login notes…"
        value={client?.ads_manager_resource} onSaved={setClient}
      />
      <ResourceField
        clientId={clientId} field="registrar_resource" label="Registrar Platform"
        placeholder="e.g. GoDaddy / Namecheap link or login notes…"
        value={client?.registrar_resource} onSaved={setClient}
      />
      <ResourceField
        clientId={clientId} field="hosting_resource" label="Hosting Platform"
        placeholder="e.g. Vercel / hosting link or login notes…"
        value={client?.hosting_resource} onSaved={setClient}
      />

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", margin: "18px 0 8px" }}>
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a7bd5", letterSpacing: "0.08em" }}>
          OTHER RESOURCES
        </div>
        <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={() => setShowForm((s) => !s)}>
          {showForm ? "CANCEL" : "+ ADD"}
        </button>
      </div>

      {showForm && (
        <div style={{ padding: "10px 12px", borderRadius: 8, background: "rgba(255,255,255,0.02)", marginBottom: 8, display: "flex", flexDirection: "column", gap: 8 }}>
          <input
            className="dg-input" placeholder="Label, e.g. Photos / Testimonials / Brand Files" value={form.label}
            onChange={(e) => setForm((f) => ({ ...f, label: e.target.value }))} autoFocus
          />
          <textarea
            className="dg-input" rows={2} placeholder="Link or notes…" value={form.value}
            onChange={(e) => setForm((f) => ({ ...f, value: e.target.value }))}
            style={{ resize: "vertical" }}
          />
          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <button className="btn btn-primary" style={{ fontSize: 11 }} onClick={addResource} disabled={saving || !form.label.trim() || !form.value.trim()}>
              {saving ? "SAVING…" : "SAVE RESOURCE"}
            </button>
          </div>
        </div>
      )}

      {resources.length === 0 && !showForm && (
        <div style={{ padding: "16px 0", fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>
          NO OTHER RESOURCES YET
        </div>
      )}
      {resources.map((r) => <MiscResourceRow key={r.id} resource={r} onDelete={removeResource} />)}
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
      <LaunchChecklistSection />
    </div>
  );
}
