import React, { useState, useEffect, useRef, useCallback } from "react";
import { createPortal } from "react-dom";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer,
} from "recharts";
import { API } from "../api.js";
import { SECTIONS } from "../onboardingSections.js";
import PeriodToggle from "../components/PeriodToggle.jsx";

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
  { id: "agent", label: "Agent" },
  { id: "finance", label: "Finance" },
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
          {detailsTab === "agent" && <ClientAgentSetup clientId={client.id} />}
          {detailsTab === "finance" && <ClientFinance clientId={client.id} />}
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

// ---------------- Per-client finance ledger (Finance tab) ----------------
//
// What it costs DigiGrowth to deliver/run this client's campaign (ad spend,
// tools, labor) against the revenue that client's own business generated
// from it — same manual-ledger shape as FinancesPanel.jsx's agency-wide
// P&L, just scoped to client_transactions via routers/client_finance.py, so
// ROAS (revenue / ad spend) can be tracked per client instead of only
// agency-wide.

const CLIENT_FINANCE_EXPENSE_CATEGORIES = ["Ad Spend", "Software & Tools", "Labor & Fulfillment", "Other"];
const CLIENT_FINANCE_PERIOD_OPTIONS = [[7, "7D"], [30, "30D"], [90, "90D"], [365, "1Y"]];

function clientFinanceMoney(v) {
  if (v == null) return "—";
  return `$${Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function ClientFinanceTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: "rgba(10,18,48,0.95)", border: "1px solid rgba(58,123,213,0.2)",
      borderRadius: 10, padding: "8px 14px", fontSize: 12,
      fontFamily: "'Space Grotesk', sans-serif",
    }}>
      <div style={{ color: "#8aaad0", marginBottom: 4 }}>{label}</div>
      {payload.map((p) => (
        <div key={p.dataKey} style={{ color: p.color, fontWeight: 600 }}>
          {p.name}: ${p.value?.toLocaleString()}
        </div>
      ))}
    </div>
  );
}

function ClientFinanceSummaryCard({ label, value, color, sub }) {
  return (
    <div className="stat-card">
      <div className="stat-card-label">{label}</div>
      <div className="stat-card-value" style={{ color: color || "#f0f4ff" }}>{value ?? "—"}</div>
      {sub && <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80", marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

function AddClientTransactionModal({ clientId, onClose, onSaved }) {
  const today = new Date().toISOString().slice(0, 10);
  const [form, setForm] = useState({
    is_income: false,
    description: "",
    amount: "",
    date: today,
    category: "Ad Spend",
    notes: "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const set = (k, v) => setForm((prev) => ({ ...prev, [k]: v }));

  const handleSave = async () => {
    const amt = parseFloat(form.amount);
    if (!form.amount || isNaN(amt) || amt <= 0) { setError("Enter a valid amount greater than 0."); return; }
    setSaving(true);
    setError(null);
    try {
      const resp = await fetch(API(`/clients/${clientId}/finance/transactions`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          is_income: form.is_income,
          description: form.description.trim() || undefined,
          amount: amt,
          date: form.date,
          category: form.is_income ? "Client Revenue" : form.category,
          notes: form.notes.trim() || null,
        }),
      });
      if (!resp.ok) { setError(await resp.text()); return; }
      onSaved(await resp.json());
      onClose();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.65)",
        backdropFilter: "blur(6px)", zIndex: 1000,
        display: "flex", alignItems: "center", justifyContent: "center",
      }}
      onClick={onClose}
    >
      <div className="glass-card" style={{ width: 440, padding: "28px 32px" }} onClick={(e) => e.stopPropagation()}>
        <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 17, fontWeight: 700, color: "#f0f4ff", marginBottom: 22 }}>
          Add Entry
        </div>

        <div style={{ display: "flex", marginBottom: 20, background: "rgba(10,18,48,0.7)", borderRadius: 10, padding: 4, gap: 4 }}>
          {[[false, "Expense"], [true, "Client Revenue"]].map(([val, label]) => (
            <button key={label} onClick={() => set("is_income", val)} style={{
              flex: 1, fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, fontWeight: 600,
              padding: "9px 0", borderRadius: 8, border: "none", cursor: "pointer",
              background: form.is_income === val
                ? val ? "linear-gradient(135deg, #0d7a4e, #14c882)" : "linear-gradient(135deg, #7a3a00, #f0a028)"
                : "transparent",
              color: form.is_income === val ? "#fff" : "#4a6080",
              transition: "all 0.15s",
            }}>{label}</button>
          ))}
        </div>

        <div style={{ marginBottom: 14 }}>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", letterSpacing: "0.12em", marginBottom: 5 }}>DESCRIPTION</div>
          <input
            className="dg-input" type="text"
            style={{ width: "100%", fontSize: 13, boxSizing: "border-box" }}
            placeholder={form.is_income ? "e.g. Attributed sales from campaign…" : "e.g. Meta Ads spend, editor hours…"}
            value={form.description}
            onChange={(e) => set("description", e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSave()}
          />
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 14 }}>
          <div>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", letterSpacing: "0.12em", marginBottom: 5 }}>AMOUNT ($)</div>
            <input
              className="dg-input" type="number" min="0" step="0.01"
              style={{ width: "100%", fontSize: 13, boxSizing: "border-box" }}
              placeholder="0.00"
              value={form.amount}
              onChange={(e) => set("amount", e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSave()}
            />
          </div>
          <div>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", letterSpacing: "0.12em", marginBottom: 5 }}>DATE</div>
            <input
              className="dg-input" type="date"
              style={{ width: "100%", fontSize: 13, boxSizing: "border-box" }}
              value={form.date}
              onChange={(e) => set("date", e.target.value)}
            />
          </div>
        </div>

        {!form.is_income && (
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", letterSpacing: "0.12em", marginBottom: 5 }}>CATEGORY</div>
            <select
              className="dg-input"
              style={{ width: "100%", fontSize: 13 }}
              value={form.category}
              onChange={(e) => set("category", e.target.value)}
            >
              {CLIENT_FINANCE_EXPENSE_CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            {form.category === "Ad Spend" && (
              <div style={{ fontSize: 10, color: "#5a7096", marginTop: 5 }}>
                Counts as the ROAS denominator for this client.
              </div>
            )}
          </div>
        )}

        <div style={{ marginBottom: 20 }}>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", letterSpacing: "0.12em", marginBottom: 5 }}>NOTES (OPTIONAL)</div>
          <input
            className="dg-input" type="text"
            style={{ width: "100%", fontSize: 13, boxSizing: "border-box" }}
            placeholder="Optional note…"
            value={form.notes}
            onChange={(e) => set("notes", e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSave()}
          />
        </div>

        {error && (
          <div style={{
            marginBottom: 14, padding: "8px 12px", borderRadius: 8,
            background: "rgba(220,60,60,0.08)", border: "1px solid rgba(220,60,60,0.2)",
            fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#dc3c3c", letterSpacing: "0.04em",
          }}>
            {error}
          </div>
        )}

        <div style={{ display: "flex", gap: 10 }}>
          <button onClick={onClose} className="btn btn-secondary" style={{ flex: 1, fontSize: 12 }}>Cancel</button>
          <button onClick={handleSave} disabled={saving} className="btn btn-primary" style={{ flex: 1, fontSize: 12 }}>
            {saving ? "Saving…" : `Add ${form.is_income ? "Revenue" : "Expense"}`}
          </button>
        </div>
      </div>
    </div>
  );
}

function ClientFinance({ clientId }) {
  const [days, setDays] = useState(30);
  const [summary, setSummary] = useState(null);
  const [categories, setCategories] = useState(null);
  const [txns, setTxns] = useState(null);
  const [txnType, setTxnType] = useState("all");
  const [showAddForm, setShowAddForm] = useState(false);
  const [expandedTxn, setExpandedTxn] = useState(null);
  const [deletingId, setDeletingId] = useState(null);
  const [hoveredTxn, setHoveredTxn] = useState(null);

  const loadAll = useCallback(async (d = days) => {
    const [s, c, t] = await Promise.all([
      fetch(API(`/clients/${clientId}/finance/summary?days=${d}`)).then((x) => (x.ok ? x.json() : null)),
      fetch(API(`/clients/${clientId}/finance/categories?days=${d}`)).then((x) => (x.ok ? x.json() : null)),
      fetch(API(`/clients/${clientId}/finance/transactions?days=${d}&type=all&limit=1000`)).then((x) => (x.ok ? x.json() : null)),
    ]);
    setSummary(s);
    setCategories(c);
    setTxns(t);
  }, [clientId, days]);

  useEffect(() => { loadAll(days); /* eslint-disable-next-line */ }, [clientId, days]);

  const handleTxnSaved = (newTxn) => {
    setTxns((prev) => prev ? { ...prev, total: prev.total + 1, transactions: [newTxn, ...prev.transactions] } : { total: 1, transactions: [newTxn] });
    loadAll();
  };

  const deleteTxn = async (id) => {
    setDeletingId(id);
    try {
      await fetch(API(`/clients/${clientId}/finance/transactions/${id}`), { method: "DELETE" });
      setTxns((prev) => prev ? { ...prev, total: prev.total - 1, transactions: prev.transactions.filter((t) => t.id !== id) } : prev);
      setExpandedTxn(null);
      loadAll();
    } finally {
      setDeletingId(null);
    }
  };

  const updateTxn = async (id, patch) => {
    await fetch(API(`/clients/${clientId}/finance/transactions/${id}`), {
      method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(patch),
    });
    setTxns((prev) => prev ? { ...prev, transactions: prev.transactions.map((t) => (t.id === id ? { ...t, ...patch } : t)) } : prev);
  };

  const filteredTxns = (txns?.transactions ?? []).filter((t) => {
    if (txnType === "income") return t.is_income;
    if (txnType === "expense") return !t.is_income;
    return true;
  });

  if (!summary) {
    return (
      <div style={{ padding: 16, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>LOADING…</div>
    );
  }

  const roasColor = summary.roas == null ? "#3a5a80" : summary.roas >= 3 ? "#14c882" : summary.roas >= 1 ? "#f0a028" : "#dc3c3c";

  return (
    <div style={{ padding: "14px 16px", borderTop: "1px solid rgba(58,123,213,0.1)", display: "flex", flexDirection: "column", gap: 18 }}>
      {showAddForm && (
        <AddClientTransactionModal clientId={clientId} onClose={() => setShowAddForm(false)} onSaved={handleTxnSaved} />
      )}

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80", letterSpacing: "0.14em" }}>
          MANUAL LEDGER · COST TO DELIVER VS. CLIENT-ATTRIBUTED REVENUE
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <button onClick={() => setShowAddForm(true)} className="btn btn-primary" style={{ fontSize: 11, padding: "6px 14px" }}>
            + Add Entry
          </button>
          <PeriodToggle days={days} setDays={setDays} options={CLIENT_FINANCE_PERIOD_OPTIONS} />
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
        <ClientFinanceSummaryCard label="Client Revenue" value={clientFinanceMoney(summary.revenue)} color="#14c882" />
        <ClientFinanceSummaryCard label="Total Expenses" value={clientFinanceMoney(summary.expenses)} color="#f0a028" />
        <ClientFinanceSummaryCard label="Ad Spend" value={clientFinanceMoney(summary.ad_spend)} color="#6ab0ff" />
        <ClientFinanceSummaryCard
          label="ROAS"
          value={summary.roas != null ? `${summary.roas}x` : "—"}
          color={roasColor}
          sub={summary.roas == null ? "NO AD SPEND LOGGED" : summary.roas >= 3 ? "STRONG" : summary.roas >= 1 ? "BREAKEVEN+" : "LOSING MONEY"}
        />
      </div>

      <div className="glass-card" style={{ padding: "16px 18px" }}>
        <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 13, fontWeight: 600, color: "#d0dcf0", marginBottom: 12 }}>
          Revenue vs Expenses
        </div>
        <ResponsiveContainer width="100%" height={140}>
          <AreaChart data={categories?.daily ?? []} margin={{ top: 5, right: 5, bottom: 0, left: -10 }}>
            <defs>
              <linearGradient id={`cfRevenue-${clientId}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#14c882" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#14c882" stopOpacity={0} />
              </linearGradient>
              <linearGradient id={`cfExpense-${clientId}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#f0a028" stopOpacity={0.25} />
                <stop offset="95%" stopColor="#f0a028" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(58,123,213,0.06)" />
            <XAxis dataKey="date" tick={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, fill: "#2a4a7a" }} axisLine={false} tickLine={false}
              tickFormatter={(v) => (v ? v.slice(5) : "")} />
            <YAxis tick={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, fill: "#2a4a7a" }} axisLine={false} tickLine={false} tickFormatter={(v) => `$${v}`} />
            <Tooltip content={<ClientFinanceTooltip />} />
            <Area type="monotone" dataKey="revenue" name="Revenue" stroke="#14c882" strokeWidth={2} fill={`url(#cfRevenue-${clientId})`} />
            <Area type="monotone" dataKey="expenses" name="Expenses" stroke="#f0a028" strokeWidth={2} fill={`url(#cfExpense-${clientId})`} />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="glass-card" style={{ padding: "16px 18px" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 13, fontWeight: 600, color: "#d0dcf0" }}>Entries</div>
          <div style={{ display: "flex", background: "rgba(10,18,48,0.5)", border: "1px solid rgba(58,123,213,0.1)", borderRadius: 8, padding: 3, gap: 2 }}>
            {[["all", "ALL"], ["income", "REVENUE"], ["expense", "EXPENSES"]].map(([v, label]) => (
              <button key={v} onClick={() => setTxnType(v)} style={{
                fontFamily: "'Share Tech Mono', monospace", fontSize: 9, padding: "4px 12px", letterSpacing: "0.08em",
                borderRadius: 6, border: "none", cursor: "pointer",
                background: txnType === v ? "rgba(58,123,213,0.3)" : "transparent",
                color: txnType === v ? "#6ab0ff" : "#2a4a7a",
              }}>{label}</button>
            ))}
          </div>
        </div>

        {filteredTxns.length === 0 ? (
          <div style={{ padding: "24px 0", textAlign: "center", fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52", letterSpacing: "0.1em" }}>
            NO ENTRIES YET
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column" }}>
            {filteredTxns.map((t) => (
              <div key={t.id} onMouseEnter={() => setHoveredTxn(t.id)} onMouseLeave={() => setHoveredTxn(null)}>
                <div
                  onClick={() => setExpandedTxn(expandedTxn === t.id ? null : t.id)}
                  style={{
                    display: "flex", alignItems: "center", justifyContent: "space-between",
                    padding: "9px 0", borderBottom: expandedTxn === t.id ? "none" : "0.5px solid #1a2540", cursor: "pointer",
                  }}
                >
                  <div style={{ display: "flex", flexDirection: "column", gap: 2, flex: 1, marginRight: 12 }}>
                    <span style={{ fontSize: 12, color: "#8aaad0", fontWeight: 500 }}>{t.description || "—"}</span>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a4a7a" }}>{t.date}</span>
                      <span style={{
                        fontFamily: "'Share Tech Mono', monospace", fontSize: 8, padding: "2px 6px", borderRadius: 4,
                        background: "rgba(58,123,213,0.08)", color: "#3a7bd5", letterSpacing: "0.06em",
                      }}>{t.category}</span>
                    </div>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span style={{
                      fontFamily: "'Share Tech Mono', monospace", fontSize: 13, fontWeight: 700,
                      color: t.is_income ? "#14c882" : "#f0a028", letterSpacing: "-0.01em",
                    }}>
                      {t.is_income ? "+" : "-"}{clientFinanceMoney(t.amount)}
                    </span>
                    <button
                      onClick={(e) => { e.stopPropagation(); deleteTxn(t.id); }}
                      disabled={deletingId === t.id}
                      style={{
                        padding: "3px 9px", borderRadius: 5, border: "1px solid rgba(220,60,60,0.25)",
                        background: "rgba(220,60,60,0.06)", color: "#dc3c3c",
                        fontFamily: "'Share Tech Mono', monospace", fontSize: 8, cursor: "pointer", letterSpacing: "0.06em",
                        opacity: deletingId === t.id ? 0.5 : hoveredTxn === t.id ? 1 : 0,
                        transition: "opacity 0.15s", pointerEvents: hoveredTxn === t.id ? "auto" : "none",
                      }}
                    >
                      {deletingId === t.id ? "…" : "✕"}
                    </button>
                  </div>
                </div>

                {expandedTxn === t.id && (
                  <div style={{ padding: "10px 12px", background: "rgba(10,18,48,0.4)", borderBottom: "0.5px solid #1a2540", display: "flex", gap: 10, alignItems: "center" }}>
                    <select
                      value={t.category}
                      onChange={(e) => updateTxn(t.id, { category: e.target.value })}
                      className="dg-input"
                      style={{ fontSize: 11, padding: "5px 8px", flex: "0 0 auto" }}
                    >
                      {(t.is_income ? ["Client Revenue"] : CLIENT_FINANCE_EXPENSE_CATEGORIES).map((c) => <option key={c} value={c}>{c}</option>)}
                    </select>
                    <input
                      className="dg-input" style={{ flex: 1, fontSize: 11 }} placeholder="Add note…"
                      defaultValue={t.notes || ""} onBlur={(e) => updateTxn(t.id, { notes: e.target.value })}
                    />
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
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
// Cloudflare R2 (r2_storage.py) — this just lists metadata and gets
// presigned URLs on demand: an `inline=true` one (no Content-Disposition:
// attachment header) to render image/video thumbnails and a lightbox
// directly in the browser, and a plain one for the DOWNLOAD button. Lets
// Dylan flip through what a client uploaded and judge what's usable without
// downloading each file first.
//
// Perf note: an earlier version fetched a presigned URL AND mounted a real
// <video> element for every video the instant the grid rendered — with a
// batch of dozens of 50-80MB videos, that meant dozens of simultaneous
// browser video decoders spinning up at once, which is what made the whole
// tab lag badly. Fix: images lazy-load only once actually scrolled into
// view (IntersectionObserver), and videos never load or decode anything
// for their thumbnail at all — just a static icon — until the user
// explicitly clicks to open one in the lightbox.
function UploadThumb({ clientId, file, onOpen, onDownload, onDelete }) {
  const [inlineUrl, setInlineUrl] = useState(null);
  const [loadingVideo, setLoadingVideo] = useState(false);
  const elRef = useRef(null);
  const isImage = file.file_type?.startsWith("image/");
  const isVideo = file.file_type?.startsWith("video/");

  const fetchInlineUrl = async () => {
    const r = await fetch(API(`/clients/${clientId}/uploads/${file.id}/download?inline=true`));
    if (r.ok) return (await r.json()).url;
    return null;
  };

  // Images: fetch + render only once the thumbnail is actually visible.
  useEffect(() => {
    if (!isImage || inlineUrl || !elRef.current) return;
    const el = elRef.current;
    const observer = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting) {
        observer.disconnect();
        fetchInlineUrl().then((url) => url && setInlineUrl(url));
      }
    }, { rootMargin: "200px" });
    observer.observe(el);
    return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isImage, clientId, file.id]);

  const openVideo = async () => {
    if (loadingVideo) return;
    setLoadingVideo(true);
    const url = inlineUrl || (await fetchInlineUrl());
    setLoadingVideo(false);
    if (url) { setInlineUrl(url); onOpen(file, url); }
  };

  const clickable = isImage ? Boolean(inlineUrl) : isVideo;

  return (
    <div
      ref={elRef}
      title={file.file_name}
      onClick={() => { if (isImage && inlineUrl) onOpen(file, inlineUrl); else if (isVideo) openVideo(); }}
      style={{
        position: "relative", aspectRatio: "1 / 1", borderRadius: 10, overflow: "hidden",
        background: "rgba(255,255,255,0.03)", border: "1px solid rgba(58,123,213,0.12)",
        cursor: clickable ? "pointer" : "default",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}
    >
      {isImage && inlineUrl && (
        <img src={inlineUrl} alt={file.file_name} loading="lazy" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      )}
      {isImage && !inlineUrl && (
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a8a" }}>…</div>
      )}
      {isVideo && (
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "center", width: "100%", height: "100%",
          background: "rgba(58,123,213,0.06)",
        }}>
          <div style={{ fontSize: 28, color: loadingVideo ? "#3a5a8a" : "#9cc4f5" }}>{loadingVideo ? "…" : "▶"}</div>
        </div>
      )}
      {!isImage && !isVideo && (
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#5a7aa0", textAlign: "center", padding: 8 }}>
          FILE
        </div>
      )}
      <div style={{ position: "absolute", top: 4, right: 4, display: "flex", gap: 4 }}>
        <button
          title="Download" onClick={(e) => { e.stopPropagation(); onDownload(file); }}
          style={{
            width: 22, height: 22, borderRadius: 6, border: "none", cursor: "pointer",
            background: "rgba(0,0,0,0.55)", color: "#e8f0ff", fontSize: 11, lineHeight: 1,
            display: "flex", alignItems: "center", justifyContent: "center",
          }}
        >⬇</button>
        <button
          title="Delete" onClick={(e) => { e.stopPropagation(); onDelete(file); }}
          style={{
            width: 22, height: 22, borderRadius: 6, border: "none", cursor: "pointer",
            background: "rgba(0,0,0,0.55)", color: "#e05c5c", fontSize: 11, lineHeight: 1,
            display: "flex", alignItems: "center", justifyContent: "center",
          }}
        >✕</button>
      </div>
    </div>
  );
}

function UploadLightbox({ clientId, file, url, onClose, onDelete }) {
  const isImage = file.file_type?.startsWith("image/");
  const download = async () => {
    const r = await fetch(API(`/clients/${clientId}/uploads/${file.id}/download`));
    if (r.ok) {
      const { url: dlUrl } = await r.json();
      window.open(dlUrl, "_blank", "noreferrer");
    }
  };

  return createPortal(
    <div
      onClick={onClose}
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.85)", zIndex: 1000,
        display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 24,
      }}
    >
      <div onClick={(e) => e.stopPropagation()} style={{ maxWidth: "90vw", maxHeight: "80vh", display: "flex" }}>
        {isImage ? (
          <img src={url} alt={file.file_name} style={{ maxWidth: "90vw", maxHeight: "80vh", objectFit: "contain", borderRadius: 8 }} />
        ) : (
          <video src={url} controls autoPlay style={{ maxWidth: "90vw", maxHeight: "80vh", borderRadius: 8 }} />
        )}
      </div>
      <div onClick={(e) => e.stopPropagation()} style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 14 }}>
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 11, color: "#d0e8ff" }}>{file.file_name}</div>
        <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={download}>DOWNLOAD</button>
        <button className="btn btn-danger" style={{ fontSize: 10 }} onClick={() => onDelete(file)}>DELETE</button>
        <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={onClose}>CLOSE</button>
      </div>
    </div>,
    document.body
  );
}

const UPLOADS_PAGE_SIZE = 24;

function ClientUploads({ clientId }) {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lightbox, setLightbox] = useState(null); // { file, url }
  // Caps how many thumbnails actually mount at once — the previous version
  // rendered (and lazy-loaded) every file in one grid the instant the tab
  // opened; with a big batch that's still dozens of thumbnails mounting,
  // observing, and fetching simultaneously even with per-item lazy-loading.
  // Paging the render itself, not just the network fetch, is what actually
  // keeps opening the tab fast regardless of how many files a client has.
  const [visibleCount, setVisibleCount] = useState(UPLOADS_PAGE_SIZE);

  const load = async () => {
    const r = await fetch(API(`/clients/${clientId}/uploads`));
    if (r.ok) setFiles(await r.json());
    setVisibleCount(UPLOADS_PAGE_SIZE);
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
    setLightbox(null);
    load();
  };

  if (loading) return <div style={{ padding: 16, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>LOADING…</div>;

  // Non-media files (PDFs, docx, etc.) aren't shown in this gallery at all
  // — this tab is for reviewing photos/videos, not managing every document
  // type a client might upload. They're still included in DOWNLOAD ALL
  // (ZIP) and still exist in storage; just not listed here.
  const mediaFiles = files.filter((f) => f.file_type?.startsWith("image/") || f.file_type?.startsWith("video/"));

  if (mediaFiles.length === 0) {
    return <div style={{ padding: 16, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>NO PHOTOS OR VIDEOS UPLOADED YET</div>;
  }

  const visibleFiles = mediaFiles.slice(0, visibleCount);
  const hasMore = mediaFiles.length > visibleCount;

  return (
    <div style={{ padding: "14px 16px", borderTop: "1px solid rgba(58,123,213,0.1)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#5a7aa0" }}>
          SHOWING {visibleFiles.length} OF {mediaFiles.length} FILE{mediaFiles.length === 1 ? "" : "S"}
        </div>
        <button
          className="btn btn-secondary" style={{ fontSize: 10 }}
          onClick={() => window.open(API(`/clients/${clientId}/uploads/zip`), "_blank")}
        >
          DOWNLOAD ALL (ZIP)
        </button>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))", gap: 10 }}>
        {visibleFiles.map((f) => (
          <UploadThumb
            key={f.id} clientId={clientId} file={f}
            onOpen={(file, url) => setLightbox({ file, url })}
            onDownload={download} onDelete={remove}
          />
        ))}
      </div>
      {hasMore && (
        <div style={{ display: "flex", justifyContent: "center", marginTop: 14 }}>
          <button
            className="btn btn-secondary" style={{ fontSize: 10 }}
            onClick={() => setVisibleCount((n) => n + UPLOADS_PAGE_SIZE)}
          >
            LOAD {Math.min(UPLOADS_PAGE_SIZE, mediaFiles.length - visibleCount)} MORE
          </button>
        </div>
      )}
      {lightbox && (
        <UploadLightbox
          clientId={clientId} file={lightbox.file} url={lightbox.url}
          onClose={() => setLightbox(null)} onDelete={remove}
        />
      )}
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

// Numbered, linked how-to for each marketing-setup step — the "click Set Up,
// get a doc with numbered steps and the exact links to go to" the user asked
// for. Automatable sub-steps (Buy Number, Test) point at the button right
// below instead of an external link. Anything genuinely automatable end-to-
// end is flagged separately below (see AUTOMATION_CANDIDATES).
const MARKETING_GUIDES = {
  sms: {
    title: "Set Up SMS Marketing",
    steps: [
      { text: "Click \"Buy Number\" on this tab — provisions a dedicated Twilio subaccount + local number for this client. (Automated — no external step.)" },
      { text: "Register an A2P 10DLC Brand + Campaign for this client's Twilio subaccount using their real business name/EIN — required before real volume will deliver reliably.", link: "https://console.twilio.com/us1/develop/sms/regulatory-compliance/brand-registrations", linkLabel: "Twilio Console → Regulatory Compliance" },
      { text: "Confirm the inbound webhook is set (this happens automatically on purchase) — nothing to do here, just verify." },
      { text: "Send yourself a test text to/from the new number and confirm it lands in the message log." },
      { text: "Once Response AI is connected below, confirm it's using this same number, not one of its own." },
      { text: "Automated — nothing to do here: every message sent/received through this number is already wired into the client's portal (Inbox tab's \"Your Number & Mailbox Activity\" panel) and into their Dashboard/Analytics stats. Just confirm it shows up there after your test text." },
    ],
  },
  email: {
    title: "Set Up Email Marketing",
    steps: [
      { text: "Never send outreach from the client's own root domain, even a mailbox they don't use daily (e.g. contact@) — it shares reputation with their real business mailbox. Instead, pick a dedicated outreach SUBDOMAIN for this client (e.g. mail.clientdomain.com or go.clientdomain.com).",
        fields: [{ key: "email_subdomain", label: "Outreach subdomain", placeholder: "mail.clientdomain.com" }] },
      { text: "In DigiGrowth's own Workspace Admin (NOT the client's) — Account → Domains → Add a domain — add that subdomain as a Secondary Domain. Check the domain-count limit on DigiGrowth's Workspace plan first if you've added several of these already.", link: "https://admin.google.com/ac/domains", linkLabel: "Google Admin Console (digigrowthllc.com) → Domains" },
      { text: "Verify ownership: Google gives you a TXT record (Name matches your subdomain, e.g. \"mail\") — add it at the CLIENT's registrar. This is the only step that needs the client's registrar access, not their Workspace login.", registrar: true },
      { text: "Once verified, Google shows an MX activation code. Add it at the client's registrar as a new record — Type MX, Name = your subdomain label (e.g. \"mail\"), Priority 1, Data smtp.google.com, TTL lowest available. Do NOT touch or delete the client's existing root-domain (\"@\") MX record — that's their real business email.", registrar: true },
      { text: "Add an SPF TXT record for the subdomain — Name = same subdomain label, value exactly \"v=spf1 include:_spf.google.com ~all\" (the v=spf1 prefix is required, easy to accidentally omit).", registrar: true },
      { text: "Wait 24-72 hours after the MX record goes live before generating DKIM — Google enforces this wait; generating earlier can produce an invalid key you'd have to redo." },
      { text: "After the wait, go to Apps → Google Workspace → Gmail → Authenticate email, select the subdomain specifically (not the root domain), and Generate a new DKIM record (2048-bit, \"google\" prefix are fine defaults).", link: "https://admin.google.com/ac/apps/gmail/authenticateemail", linkLabel: "Google Admin Console → Gmail → Authenticate email" },
      { text: "Add the generated DKIM TXT record at the client's registrar, wait for it to propagate, then click Start Authentication in the Admin console.", registrar: true },
      { text: "Create the sending mailbox on the subdomain under DigiGrowth's Workspace (e.g. contact@mail.clientdomain.com).", link: "https://admin.google.com/ac/users", linkLabel: "Google Admin Console → Users → Add new user" },
      { text: "Locally run reauth_google.py (repo root), logged into GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET (Railway variables on the digigrowth-brain service), signed in as the new mailbox, to generate a refresh token. (Local script — no link.)" },
      { text: "Paste the refresh token and sender email below — the subdomain field above is reused automatically.",
        fields: [
          { key: "gmail_refresh_token", label: "Gmail refresh token", placeholder: "1//0…" },
          { key: "gmail_sender_email", label: "Sender email", placeholder: "contact@mail.clientdomain.com" },
        ] },
      { text: "Send a test email and confirm it lands (check spam too).", testAction: "email" },
      { text: "Automated — nothing to do here: every email sent through this mailbox is already wired into the client's portal (Inbox tab's \"Your Number & Mailbox Activity\" panel) and into their Dashboard/Analytics stats. Just confirm it shows up there after your test email." },
      { text: "Before starting real outreach, run this mailbox through an automated warm-up to build sending reputation. Real outreach can still start any time even if warm-up isn't finished — it just tops up around whatever real volume already goes out.", warmupAction: true },
    ],
  },
  response_ai: {
    title: "Set Up Response AI",
    steps: [
      { text: "Confirm SMS marketing is provisioned first — this reuses the client's own Twilio number, it doesn't bring its own." },
      { text: "Head to this client's own \"Agent\" tab (next to Marketing Setup). Everything below happens there." },
      { text: "Enable the agent, then write its context (business info, offer, tone, hours, FAQs, what to escalate) — or click GENERATE CONTEXT to draft one from this client's onboarding answers, linked contact info, and any uploaded PDFs/docx, then review and edit it." },
      { text: "Fill in the SMS Sequence — 5 short stage goals (first text through fifth text) the agent tries to progress a conversation through. It doesn't follow this rigidly: it always answers whatever the lead actually asks first, then steers back toward the next stage." },
      { text: "Set Rules — a minimum reply delay and a max words-per-text are actually enforced, not just suggested. Add any other freeform rules (tone quirks, things to never say, etc.) in the big text box; the agent reads it before every reply." },
      { text: "Optional: connect the client's Calendly under \"Calendar (Calendly)\" — a Personal Access Token (Calendly account → Integrations & Apps → API & Webhooks → Generate New Token) lets the agent check real open times before proposing one, instead of asking blind. Without it, the agent just asks the lead for their preferred day/time." },
      { text: "Text the client's number from your own phone and have a real back-and-forth. Confirm: replies sound on-brand and follow the sequence loosely, agreeing to a time actually creates an appointment (check the Appointments tab), and asking for a human stops the AI from replying further to that thread. Use the Agent tab's \"Testing\" section to reset that number's conversation state between test runs." },
    ],
  },
  landing_page: {
    title: "Create Landing Page",
    steps: [
      { text: "Not yet automated — see the automation note below this guide. For now: build the page manually from the DigiGrowth landing-page template, matching the offer/guarantee/CTA from onboarding." },
      { text: "Push it live as its own Vercel project (not a route on the corporate site).", link: "https://vercel.com/new", linkLabel: "Vercel → New Project" },
      { text: "Point the client's domain/subdomain at it via their registrar's DNS settings.", registrar: true },
      { text: "Paste the live URL below.",
        fields: [{ key: "landing_page_url", label: "Live URL", placeholder: "https://…" }] },
    ],
  },
  ad_creatives: {
    title: "Create Paid Ad Creatives",
    steps: [
      { text: "Use the ad-copy skill (content-agent) to write the ad copy/hook/CTA." },
      { text: "Set up the Meta Pixel before running anything: create (or open) the client's pixel in Business Manager → Events Manager, then install the pixel base code plus Lead/Purchase standard events on their landing page. Do this before spending any budget — without it, none of the ad spend is trackable and Analytics' ad-spend fields have nothing to attribute to.", link: "https://business.facebook.com/events_manager2/list/pixel/", linkLabel: "Meta Events Manager",
        fields: [{ key: "meta_pixel_id", label: "Pixel ID", placeholder: "1234567890123456" }] },
      { text: "Verify the pixel is actually firing (base PageView + the Lead/Purchase events) using the Meta Pixel Helper browser extension on the live landing page before moving on." },
      { text: "Enter this client's Meta ad account ID and Page ID (Business Manager → Business Settings → Accounts) so ad-spend sync and Facebook Lead Ads auto-follow-up can find this client's data.",
        link: "https://business.facebook.com/settings/ad-accounts", linkLabel: "Business Settings → Ad Accounts",
        fields: [
          { key: "meta_ad_account_id", label: "Meta Ad Account ID", placeholder: "123456789012345" },
          { key: "meta_page_id", label: "Meta Page ID", placeholder: "987654321098765" },
        ], testAction: "meta_ads" },
      { text: "Not yet automated for visuals — see the automation note below this guide. For now: produce the image/video manually using the copy above." },
      { text: "Upload the finished creative directly into the client's ad account.", link: "https://business.facebook.com/adsmanager", linkLabel: "Meta Ads Manager" },
    ],
  },
  automations: {
    title: "Set Up SMS/Email Automations",
    steps: [
      { text: "Confirm SMS Marketing and Email Marketing above are both done first — this reuses the client's own Twilio number and Gmail mailbox, it doesn't bring its own." },
      { text: "Open this client's Sequences tab and fill in the No Show and Cancellation SMS + email copy (seeded with PT-oriented language on client creation — rewrite it for their actual industry)." },
      { text: "That's it to go live — automated, nothing else to click: the moment a lead tied to this client goes No Show or gets Canceled (marked from the internal Appointments tab, or by the client themselves once self-service booking is turned on for them), the matching SMS/email fires automatically from the client's own number/mailbox. No scheduler or extra wiring needed (client_appointment_sequence.py)." },
      { text: "Test: mark a test appointment No Show (or Cancel it) from the Appointments tab and confirm the message lands from the client's own number/inbox, not DigiGrowth's." },
      { text: "Real limitation, not automatable from here: this only covers leads DigiGrowth booked for this client through this OS. A client's EXISTING patient base lives in their own booking software/EHR, which this system has no connection to — the same automation for their whole existing patient list needs that specific system integrated (a real per-client dev task) or the client running it through their own tool." },
    ],
  },
  client_portal: {
    title: "Set Up Client Portal",
    steps: [
      { text: "Connect the client's own Calendly so leads booked through their portal (Leads tab → a lead's booking modal) land straight on their real calendar instead of showing \"not connected yet.\" Paste their event type's booking page URL (Calendly → the specific event type → Share → Copy Link) — this is the same link used as the ad funnel's CTA destination, not a generic Calendly homepage link.",
        fields: [{ key: "calendly_url", label: "Client's Calendly event link", placeholder: "https://calendly.com/their-username/event-type" }] },
      { text: "Link this client's leads: Clients list → \"Link contact to client\" (or \"Link all unassigned\") for every contact that's actually theirs — Leads/SMS/Email/Appointment stats all key off contacts.client_id, so an unlinked contact is invisible everywhere in their portal." },
      { text: "Open this client's portal Analytics tab (use their portal link) and sanity-check Total Leads and SMS/Email Sent+Replies against what you already know is true." },
      { text: "Appointments Booked / Show Rate / Close Rate compute live from the internal Appointments tab's outcome marking (outcome_show/outcome_close) for this client's leads — nothing to connect, just make sure reps are actually marking outcomes for this client's appointments instead of leaving them blank." },
      { text: "\"Your Number\"/\"Your Mailbox\" SMS + email counts only populate once real sends go through the client's own Twilio number / Gmail mailbox (portal replies, the automations above, or the Response AI agent once enabled) — if those read zero, that's accurate, not broken, until one of those is live." },
      { text: "Ad Spend / Impressions / Clicks / CTR / CPC / Cost per Lead are NOT wired up yet — there's no Meta or Google Ads API integration in this codebase (meta_ads.py is a stub), so the portal correctly shows \"Coming Soon\" for every client. Building that needs a real Meta Marketing API / Google Ads API integration plus each client's own ad-account access — flag to Dylan as a separate build, don't expect it from this step." },
    ],
  },
};

// What's realistically automatable end-to-end vs. what always needs a human
// in the loop (an account login, a legal/compliance review, a DNS change at
// a registrar we don't control). Shown once at the top of the Marketing
// Setup tab so it's obvious which steps are worth building automation for.
const AUTOMATION_CANDIDATES = [
  { step: "Landing Page", note: "Automatable: a content-agent skill could take the client's onboarding answers (offer, guarantee, CTA, brand) and generate the page's copy + layout automatically, matching the existing digigrowth-website design system. Still needs a human to review before it goes live and to push the Vercel deploy." },
  { step: "Paid Ad Creatives", note: "Partially automatable: ad copy is already automatable (ad-copy skill). A short video ad could be generated via the existing HyperFrames motion-graphics pipeline from that same copy. Static image ads and pushing directly into Meta's ad account are not automatable without picking an image-gen provider and building the Meta Ads API integration (currently a stub)." },
  { step: "SMS / Email / Response AI", note: "SMS and Email still need a one-time human setup step outside our system (Twilio's A2P compliance review, a Google Workspace login/OAuth consent) that no API lets us do on someone's behalf. Response AI is fully self-built and automated once enabled — response_ai.py replies to inbound SMS itself, no third-party account needed, just per-client context/sequence/rules written on the Agent tab. What's already automated across all three: the number/mailbox setup itself, every send/receive once connected, and the client-portal wiring (Inbox activity panel + Dashboard/Analytics stats)." },
  { step: "SMS/Email Automations", note: "As of 2026-09-13, fully automated once the copy's filled in: writing the No Show/Cancellation SMS+email copy on the Sequences tab is the only manual step — the actual send (client_appointment_sequence.py) fires on its own the moment a lead's appointment is marked No Show/Canceled, no scheduler or extra connection needed. Not automatable: onboarding a client's EXISTING patient base, which lives in their own booking/EHR system outside this app." },
  { step: "Analytics", note: "Mostly already automatic: Leads/SMS/Email/Appointment stats compute live once contacts are linked to the client — no integration needed, just a data-hygiene check. Ad spend/CTR/CPC/etc. are the one real gap: no Meta or Google Ads API integration exists in this codebase yet, so those stay \"Coming Soon\" until that's built as its own project." },
];

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
      ? `Connected — ${cfg.gmail_sender_email || "mailbox linked"}${cfg.email_subdomain ? ` (${cfg.email_subdomain})` : ""}`
      : "Not connected"),
    done: (cfg) => Boolean(cfg?.gmail_refresh_token),
  },
  {
    key: "response_ai", label: "Response AI",
    status: (cfg) => (cfg?.response_ai_enabled
      ? (cfg?.response_ai_context ? "Enabled — context set" : "Enabled — no context written yet")
      : "Not enabled"),
    done: (cfg) => Boolean(cfg?.response_ai_enabled && cfg?.response_ai_context),
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
    // Was keyed off ad_creative_status (a "how many assets tracked" JSONB
    // field) instead of the guide checklist like every other step here —
    // nothing in the app ever actually writes to ad_creative_status, so
    // checking off every step in the guide modal never marked this done.
    // Matches automations/client_portal below now: done = every guide step
    // checked off. Status text is untouched (still a legitimate separate
    // "how many assets tracked" readout once that field is ever populated).
    done: (cfg) => _guideStepsAllDone(cfg, "ad_creatives"),
  },
  {
    key: "automations", label: "SMS/Email Automations",
    status: (cfg) => (cfg?.twilio_number && cfg?.gmail_refresh_token
      ? "Channels ready — add No Show/Cancellation copy on the Sequences tab"
      : "SMS + Email Marketing must be set up first"),
    done: (cfg) => _guideStepsAllDone(cfg, "automations"),
  },
  {
    key: "client_portal", label: "Set Up Client Portal",
    status: (cfg, client) => (client?.calendly_url
      ? "Calendly connected — Analytics still needs manual verification, see guide"
      : "Calendly not connected yet — see guide"),
    done: (cfg) => _guideStepsAllDone(cfg, "client_portal"),
  },
];

// For steps with no single dedicated config field to key off of (automations/
// analytics above) — "done" instead means every numbered guide step has been
// checked off in that step's own guide_progress.
function _guideStepsAllDone(cfg, guideKey) {
  const total = MARKETING_GUIDES[guideKey]?.steps?.length || 0;
  if (!total) return false;
  const progress = cfg?.guide_progress?.[guideKey] || {};
  return Object.keys(progress).filter((k) => progress[k]).length >= total;
}

// Inline "paste the info this step needs, right here" mini-form — saves via
// the same saveFields() the tab's own field editors use, so filling it in
// from inside the guide and from the tab below stay in sync.
function GuideStepFields({ fields, config, client, onSaveFields, onSaved }) {
  const [drafts, setDrafts] = useState(() =>
    Object.fromEntries(fields.map((f) => [f.key, config?.[f.key] || client?.[f.key] || ""]))
  );
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState("");

  const save = async () => {
    setSaving(true);
    setSaved(false);
    setSaveError("");
    const payload = {};
    for (const f of fields) payload[f.key] = (drafts[f.key] || "").trim() || null;
    const result = await onSaveFields(payload);
    setSaving(false);
    if (result?.ok) {
      setSaved(true);
      onSaved?.();
    } else {
      setSaveError(result?.error || "Save failed");
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 8 }}>
      {fields.map((f) => (
        <div key={f.key}>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#5a7aa0", marginBottom: 2 }}>{f.label}</div>
          <input
            className="dg-input" style={{ fontSize: 11, width: "100%" }}
            value={drafts[f.key]} placeholder={f.placeholder}
            onChange={(e) => { setDrafts((d) => ({ ...d, [f.key]: e.target.value })); setSaved(false); setSaveError(""); }}
          />
        </div>
      ))}
      <button className="btn btn-primary" style={{ fontSize: 10, alignSelf: "flex-start" }} onClick={save} disabled={saving}>
        {saving ? "SAVING…" : saved ? "SAVED ✓" : "SAVE"}
      </button>
      {saveError && (
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#e05c5c" }}>{saveError}</div>
      )}
    </div>
  );
}

// Enable toggle + freeform per-client context editor for the self-built
// response_ai.py agent — same onSaveFields plumbing as GuideStepFields
// above, just a checkbox + textarea instead of single-line inputs (the
// context is meant to be a real paragraph: business info, tone, offer,
// hours, what to escalate).
function ResponseAiSetup({ clientId, config, onSaveFields, onSaved }) {
  const [enabled, setEnabled] = useState(Boolean(config?.response_ai_enabled));
  const [context, setContext] = useState(config?.response_ai_context || "");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState("");

  const generateContext = async () => {
    if (context.trim() && !window.confirm("This will replace the context text below with an AI-drafted version. Continue?")) {
      return;
    }
    setGenerating(true);
    setGenerateError("");
    setSaved(false);
    try {
      const r = await fetch(API(`/clients/${clientId}/marketing-config/generate-response-ai-context`), { method: "POST" });
      if (!r.ok) {
        const detail = await r.json().catch(() => null);
        throw new Error(detail?.detail || "Failed to generate context");
      }
      const { context: drafted } = await r.json();
      setContext(drafted || "");
    } catch (e) {
      setGenerateError(e.message);
    } finally {
      setGenerating(false);
    }
  };

  const save = async () => {
    setSaving(true);
    setSaved(false);
    setSaveError("");
    const result = await onSaveFields({ response_ai_enabled: enabled, response_ai_context: context.trim() || null });
    setSaving(false);
    if (result?.ok) {
      setSaved(true);
      onSaved?.();
    } else {
      setSaveError(result?.error || "Save failed");
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 8 }}>
      <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "#d0e8ff", cursor: "pointer" }}>
        <input
          type="checkbox" checked={enabled}
          onChange={(e) => { setEnabled(e.target.checked); setSaved(false); setSaveError(""); }}
        />
        Enable the AI response agent for this client
      </label>
      <div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 2 }}>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#5a7aa0" }}>
            CLIENT CONTEXT (business info, tone, offer, hours, FAQs, what to escalate)
          </div>
          <button
            className="btn btn-secondary" style={{ fontSize: 9, padding: "3px 8px" }}
            onClick={generateContext} disabled={generating || !clientId}
          >
            {generating ? "GENERATING…" : "GENERATE CONTEXT"}
          </button>
        </div>
        <textarea
          className="dg-input" rows={8} style={{ fontSize: 12, width: "100%", boxSizing: "border-box", resize: "vertical" }}
          value={context}
          onChange={(e) => { setContext(e.target.value); setSaved(false); setSaveError(""); }}
          placeholder={"e.g. Bright Path Physical Therapy. Guarantee: 10-20 new patient consultations in 6 weeks or we keep working for free. Hours: Mon-Fri 8am-6pm. Escalate anything about insurance/billing or a lead who sounds upset."}
        />
        <div style={{ marginTop: 3, fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#5a7aa0" }}>
          Drafts from this client's onboarding answers, linked contact info, and any uploaded PDFs/docx — review and edit before saving, it won't always get everything right.
        </div>
        {generateError && (
          <div style={{ marginTop: 4, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#e05c5c" }}>{generateError}</div>
        )}
      </div>
      <button className="btn btn-primary" style={{ fontSize: 10, alignSelf: "flex-start" }} onClick={save} disabled={saving}>
        {saving ? "SAVING…" : saved ? "SAVED ✓" : "SAVE"}
      </button>
      {saveError && (
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#e05c5c" }}>{saveError}</div>
      )}
    </div>
  );
}

const AGENT_SEQUENCE_LENGTH = 5;
const AGENT_SEQUENCE_LABELS = ["First text", "Second text", "Third text", "Fourth text", "Fifth text"];

// The loose conversational arc response_ai.py tries to progress a lead
// through — 5 fixed stages (mirrors client_sms_sequences' fixed-step shape
// elsewhere in this file) stored as one JSONB array. Not a rigid script:
// the agent always answers off-script questions first, per its own system
// prompt preamble — this is just the "what's next" guidance.
function AgentSequenceEditor({ config, onSaveFields }) {
  const initial = Array.isArray(config?.response_ai_sequence) ? config.response_ai_sequence : [];
  const [steps, setSteps] = useState(() =>
    Array.from({ length: AGENT_SEQUENCE_LENGTH }, (_, i) => initial[i] || "")
  );
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState("");

  const save = async () => {
    setSaving(true);
    setSaved(false);
    setSaveError("");
    const result = await onSaveFields({ response_ai_sequence: steps.map((s) => s.trim()) });
    setSaving(false);
    if (result?.ok) setSaved(true); else setSaveError(result?.error || "Save failed");
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ fontSize: 12, color: "#8aaad0" }}>
        The general sequence the agent tries to move a conversation through — it doesn't have to follow this perfectly. If a lead asks a question, it answers first, then tries to progress to the next stage.
      </div>
      {AGENT_SEQUENCE_LABELS.map((label, i) => (
        <div key={i}>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#5a7aa0", marginBottom: 2 }}>{label.toUpperCase()}</div>
          <textarea
            className="dg-input" rows={2} style={{ fontSize: 12, width: "100%", boxSizing: "border-box", resize: "vertical" }}
            value={steps[i]}
            onChange={(e) => {
              const next = [...steps];
              next[i] = e.target.value;
              setSteps(next);
              setSaved(false); setSaveError("");
            }}
            placeholder={i === 0 ? "e.g. Greet them, confirm what they're looking for, and ask a qualifying question." : "e.g. Present the offer and ask if they'd like to grab a free consult time."}
          />
        </div>
      ))}
      <button className="btn btn-primary" style={{ fontSize: 10, alignSelf: "flex-start" }} onClick={save} disabled={saving}>
        {saving ? "SAVING…" : saved ? "SAVED ✓" : "SAVE"}
      </button>
      {saveError && (
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#e05c5c" }}>{saveError}</div>
      )}
    </div>
  );
}

// Behavioral guardrails. Two are actually enforced in code (not just prompt
// suggestions): the reply delay (deferred via scheduler_registry so the
// Twilio webhook never blocks on it) and a hard word-count cap (enforced
// both as a prompt instruction and a truncation fallback in response_ai.py).
// Everything else is freeform text the admin writes, which the agent is
// told to read before every reply — same "AI reads it, doesn't just
// display it" pattern as response_ai_context.
function AgentRulesEditor({ config, onSaveFields }) {
  const [minDelay, setMinDelay] = useState(config?.response_ai_min_delay_seconds ?? 0);
  const [maxWords, setMaxWords] = useState(config?.response_ai_max_words ?? "");
  const [rules, setRules] = useState(config?.response_ai_rules || "");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState("");

  const save = async () => {
    setSaving(true);
    setSaved(false);
    setSaveError("");
    const result = await onSaveFields({
      response_ai_min_delay_seconds: Number(minDelay) || 0,
      response_ai_max_words: maxWords === "" ? null : Number(maxWords),
      response_ai_rules: rules.trim() || null,
    });
    setSaving(false);
    if (result?.ok) setSaved(true); else setSaveError(result?.error || "Save failed");
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
        <div>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#5a7aa0", marginBottom: 2 }}>
            MIN DELAY BEFORE REPLYING (SECONDS)
          </div>
          <input
            type="number" min="0" className="dg-input" style={{ fontSize: 12, width: 120 }}
            value={minDelay}
            onChange={(e) => { setMinDelay(e.target.value); setSaved(false); setSaveError(""); }}
          />
        </div>
        <div>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#5a7aa0", marginBottom: 2 }}>
            MAX WORDS PER TEXT
          </div>
          <input
            type="number" min="1" className="dg-input" style={{ fontSize: 12, width: 120 }}
            value={maxWords} placeholder="no limit"
            onChange={(e) => { setMaxWords(e.target.value); setSaved(false); setSaveError(""); }}
          />
        </div>
      </div>
      <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#5a7aa0" }}>
        Both are actually enforced — the delay is scheduled server-side, and the word cap is hard-truncated even if the AI runs long.
      </div>
      <div>
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#5a7aa0", marginBottom: 2 }}>
          ADDITIONAL RULES (the agent reads this before every reply)
        </div>
        <textarea
          className="dg-input" rows={8} style={{ fontSize: 12, width: "100%", boxSizing: "border-box", resize: "vertical" }}
          value={rules}
          onChange={(e) => { setRules(e.target.value); setSaved(false); setSaveError(""); }}
          placeholder={"e.g. Never mention competitors by name. Always use the lead's first name if known. If they ask about a refund, escalate immediately rather than answering."}
        />
      </div>
      <button className="btn btn-primary" style={{ fontSize: 10, alignSelf: "flex-start" }} onClick={save} disabled={saving}>
        {saving ? "SAVING…" : saved ? "SAVED ✓" : "SAVE"}
      </button>
      {saveError && (
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#e05c5c" }}>{saveError}</div>
      )}
    </div>
  );
}

// Wipes a test phone number's conversation state (client_lead_conversations
// row + client_sms_messages history) so re-texting the client's number
// starts response_ai.py fresh — no escalated/booked state or prior message
// context left over from an earlier test run.
function AgentResetTest({ clientId }) {
  const [phone, setPhone] = useState("");
  const [resetting, setResetting] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const reset = async () => {
    if (!phone.trim()) return;
    setResetting(true);
    setResult(null);
    setError("");
    try {
      const r = await fetch(API(`/clients/${clientId}/response-ai/reset-test?phone=${encodeURIComponent(phone.trim())}`), { method: "POST" });
      if (!r.ok) {
        const detail = await r.json().catch(() => null);
        throw new Error(detail?.detail || "Failed to reset");
      }
      setResult(await r.json());
    } catch (e) {
      setError(e.message);
    } finally {
      setResetting(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ display: "flex", gap: 6 }}>
        <input
          className="dg-input" style={{ fontSize: 12, flex: 1 }} placeholder="+15551234567"
          value={phone} onChange={(e) => { setPhone(e.target.value); setResult(null); setError(""); }}
        />
        <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={reset} disabled={resetting || !phone.trim()}>
          {resetting ? "RESETTING…" : "RESET"}
        </button>
      </div>
      {result && (
        result.messages_deleted > 0 ? (
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#4ade80" }}>
            Reset ✓ — cleared conversation state and {result.messages_deleted} message{result.messages_deleted === 1 ? "" : "s"}. Text the number again to start fresh.
          </div>
        ) : (
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#f0b429" }}>
            No messages found for that number on this client — double check the number, it may not match any test conversation here.
          </div>
        )
      )}
      {error && (
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#e05c5c" }}>{error}</div>
      )}
    </div>
  );
}

// Calendly connection — a Personal Access Token the client (or Dylan, once
// added as an admin on their account) generates from Calendly's own
// settings. Read-only use (calendly_integration.py) — lets response_ai's
// check_availability tool propose real open times instead of asking blind.
// Calendly's API can't create a confirmed booking on someone's behalf, so
// this is availability-checking only; the actual booking still gets logged
// the same way it always has.
function AgentCalendlyConnect({ config, onSaveFields }) {
  // Deliberately NEVER pre-fill this with the existing token (unlike every
  // other field in this file) — a password-type input silently holding the
  // old secret as masked dots is a real trap: paste a new one without
  // first selecting-all, or click Save without noticing the field already
  // had content, and you silently re-save the SAME old token while
  // believing you replaced it. Starting blank means typing anything and
  // saving unambiguously replaces it, and an accidental empty-save is a
  // no-op (see save() below) rather than wiping the connection out.
  const [token, setToken] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState("");
  const connected = Boolean(config?.calendly_api_token);

  const save = async () => {
    if (!token.trim()) return;
    setSaving(true);
    setSaved(false);
    setSaveError("");
    const result = await onSaveFields({ calendly_api_token: token.trim() });
    setSaving(false);
    if (result?.ok) { setSaved(true); setToken(""); } else setSaveError(result?.error || "Save failed");
  };

  const disconnect = async () => {
    if (!window.confirm("Disconnect Calendly for this client? The agent will go back to asking leads for their preferred day/time.")) return;
    setSaving(true);
    setSaveError("");
    const result = await onSaveFields({ calendly_api_token: null });
    setSaving(false);
    if (result?.ok) { setSaved(true); setToken(""); } else setSaveError(result?.error || "Failed to disconnect");
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ fontSize: 12, color: "#8aaad0" }}>
        Generate a Personal Access Token from the client's Calendly account (Integrations &amp; Apps → API &amp; Webhooks → Generate New Token — not a "connect an app" OAuth button) and paste it below. {connected ? "Connected — paste a new token below to replace it." : "Not connected — the agent will just ask leads for their preferred day/time until this is set."}
      </div>
      <div style={{ display: "flex", gap: 6 }}>
        <input
          type="password" autoComplete="off" className="dg-input" style={{ fontSize: 12, flex: 1, boxSizing: "border-box" }}
          value={token} placeholder={connected ? "Paste a new token to replace the connected one" : "Calendly Personal Access Token"}
          onChange={(e) => { setToken(e.target.value); setSaved(false); setSaveError(""); }}
        />
        {connected && (
          <button className="btn btn-danger" style={{ fontSize: 10 }} onClick={disconnect} disabled={saving}>
            DISCONNECT
          </button>
        )}
      </div>
      <button className="btn btn-primary" style={{ fontSize: 10, alignSelf: "flex-start" }} onClick={save} disabled={saving || !token.trim()}>
        {saving ? "SAVING…" : saved ? "SAVED ✓" : "SAVE"}
      </button>
      {saveError && (
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#e05c5c" }}>{saveError}</div>
      )}
      <AgentCalendlyEventType config={config} onSaveFields={onSaveFields} />
    </div>
  );
}

// The exact event type this client's agent should check — required, never
// inferred. A token can see event types belonging to OTHER people entirely
// (e.g. Dylan's own token, as an admin on a client's Calendly, also sees
// his own unrelated event types) — "just grab whichever comes back first"
// risks silently checking/booking against the wrong calendar the moment
// more than one client shares that ambiguity. Not a secret, so — unlike
// the token field above — this is safe to pre-fill and edit in place.
function AgentCalendlyEventType({ config, onSaveFields }) {
  const [url, setUrl] = useState(config?.calendly_event_type_url || "");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState("");

  useEffect(() => { setUrl(config?.calendly_event_type_url || ""); }, [config?.calendly_event_type_url]);

  const save = async () => {
    setSaving(true);
    setSaved(false);
    setSaveError("");
    const result = await onSaveFields({ calendly_event_type_url: url.trim() || null });
    setSaving(false);
    if (result?.ok) setSaved(true); else setSaveError(result?.error || "Save failed");
  };

  return (
    <div style={{ marginTop: 4, paddingTop: 10, borderTop: "1px solid rgba(255,255,255,0.06)" }}>
      <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#5a7aa0", marginBottom: 2 }}>
        EVENT TYPE / BOOKING LINK TO CHECK
      </div>
      <div style={{ fontSize: 11, color: "#8aaad0", marginBottom: 6 }}>
        The client's actual public Calendly link for the offer this agent books (e.g. their free consult) — copy it straight from Calendly. Required for availability checks to actually run, even with a token connected.
      </div>
      <div style={{ display: "flex", gap: 6 }}>
        <input
          className="dg-input" style={{ fontSize: 12, flex: 1, boxSizing: "border-box" }}
          value={url} placeholder="https://calendly.com/name/event-slug"
          onChange={(e) => { setUrl(e.target.value); setSaved(false); setSaveError(""); }}
        />
        <button className="btn btn-primary" style={{ fontSize: 10 }} onClick={save} disabled={saving}>
          {saving ? "SAVING…" : saved ? "SAVED ✓" : "SAVE"}
        </button>
      </div>
      {saveError && (
        <div style={{ marginTop: 4, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#e05c5c" }}>{saveError}</div>
      )}
    </div>
  );
}

// Dedicated "Agent" tab — the self-built response_ai.py agent's full admin
// surface (context, sequence, rules) in one place, rather than buried
// inside the Marketing Setup guide's checklist. Fetches/saves through the
// same generic marketing-config endpoint every other per-client config
// field in this file already uses.
function ClientAgentSetup({ clientId }) {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    const r = await fetch(API(`/clients/${clientId}/marketing-config`));
    if (r.ok) setConfig(await r.json());
    setLoading(false);
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [clientId]);

  const saveFields = async (fields) => {
    let result = { ok: true, error: null };
    try {
      const r = await fetch(API(`/clients/${clientId}/marketing-config`), {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(fields),
      });
      if (!r.ok) {
        const detail = await r.json().catch(() => null);
        result = { ok: false, error: detail?.detail || "Failed to save" };
        setError(result.error);
      } else {
        setError("");
      }
    } catch (e) {
      result = { ok: false, error: e.message };
      setError(e.message);
    }
    await load();
    return result;
  };

  if (loading) return <div style={{ padding: 16, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>LOADING…</div>;

  const section = (title, description, children) => (
    <div style={{ marginBottom: 20, padding: 14, borderRadius: 10, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(58,123,213,0.1)" }}>
      <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: 13, color: "#e8f0ff", marginBottom: 2 }}>{title}</div>
      {description && <div style={{ fontSize: 11.5, color: "#8aaad0", marginBottom: 10 }}>{description}</div>}
      {children}
    </div>
  );

  return (
    <div style={{ padding: "14px 16px", borderTop: "1px solid rgba(58,123,213,0.1)" }}>
      <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a4a7a", marginBottom: 14, lineHeight: 1.5 }}>
        This client's self-built AI SMS response agent (response_ai.py) — replies to inbound leads on their own Twilio number. Enable per client from the toggle below.
      </div>
      {section(
        "Enable & Context",
        "The agent's knowledge of the business — enable it and write or generate its context.",
        <ResponseAiSetup clientId={clientId} config={config} onSaveFields={saveFields} />
      )}
      {section(
        "SMS Sequence",
        null,
        <AgentSequenceEditor config={config} onSaveFields={saveFields} />
      )}
      {section(
        "Rules",
        "Behavioral guardrails, enforced by the agent itself — not just suggestions.",
        <AgentRulesEditor config={config} onSaveFields={saveFields} />
      )}
      {section(
        "Calendar (Calendly)",
        "Optional — lets the agent check real availability before proposing a time, instead of asking blind.",
        <AgentCalendlyConnect config={config} onSaveFields={saveFields} />
      )}
      {section(
        "Testing",
        "Wipe a test number's conversation state to start the agent fresh — no escalated/booked status or old message history carried over.",
        <AgentResetTest clientId={clientId} />
      )}
      {error && (
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#e05c5c" }}>{error}</div>
      )}
    </div>
  );
}

// The "click a step, get a doc with numbered instructions + the exact links
// to go to" surface — one guide at a time, rendered via portal like the
// existing dropdown menus in this file. Each step can be checked off
// (persisted per-client), can carry an inline field to paste the info that
// step produces, or (email's test step) a live action button.
function GuideModal({
  guide, progress, onToggleStep, config, client, onSaveFields,
  testEmailTo, setTestEmailTo, sendTestEmail, testingEmail, testError,
  syncEmailNow, syncingEmail,
  syncMetaAdsNow, syncingMeta, metaSyncResult, metaSyncError,
  warmupStatus, warmupLoading, warmupError, startWarmup, refreshWarmupStatus,
  onClose,
}) {
  useEffect(() => {
    if (guide?.steps?.some((s) => s.warmupAction)) refreshWarmupStatus?.();
  }, [guide]);

  if (!guide) return null;
  const total = guide.steps.length;
  const doneCount = guide.steps.filter((_, i) => progress?.[i]).length;
  const registrar = client?.registrar_resource;
  const registrarIsUrl = registrar && /^https?:\/\//i.test(registrar);

  return createPortal(
    <div
      onClick={onClose}
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)",
        display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000, padding: 24,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "#0d1830", border: "1px solid #1a2540", borderRadius: 12,
          width: "100%", maxWidth: 560, maxHeight: "80vh", overflow: "auto",
          boxShadow: "0 24px 64px rgba(0,0,0,0.6)", padding: 22,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 15, fontWeight: 700, color: "#e8f0ff" }}>
            {guide.title}
          </div>
          <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={onClose}>CLOSE</button>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
          <div style={{ flex: 1, height: 5, borderRadius: 3, background: "rgba(255,255,255,0.06)", overflow: "hidden" }}>
            <div style={{ height: "100%", width: `${total ? (doneCount / total) * 100 : 0}%`, background: "#4ade80", transition: "width 0.2s" }} />
          </div>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#5a7aa0", whiteSpace: "nowrap" }}>
            {doneCount}/{total} DONE
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {guide.steps.map((s, i) => {
            const checked = Boolean(progress?.[i]);
            return (
              <div key={i} style={{ display: "flex", gap: 10 }}>
                <button
                  onClick={() => onToggleStep(i)}
                  title={checked ? "Mark not done" : "Mark done"}
                  style={{
                    flexShrink: 0, width: 22, height: 22, borderRadius: 6, cursor: "pointer",
                    border: checked ? "1px solid #4ade80" : "1px solid #3a5a8a", padding: 0,
                    background: checked ? "rgba(74,222,128,0.22)" : "rgba(58,123,213,0.1)",
                    color: checked ? "#4ade80" : "#9cc4f5",
                    fontFamily: "'Share Tech Mono', monospace", fontSize: 11, fontWeight: 700,
                    display: "flex", alignItems: "center", justifyContent: "center",
                  }}>{checked ? "✓" : i + 1}</button>
                <div style={{ flex: 1, opacity: checked ? 0.6 : 1 }}>
                  <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8 }}>
                    <div style={{ fontSize: 12.5, color: "#d0e8ff", lineHeight: 1.5, textDecoration: checked ? "line-through" : "none" }}>{s.text}</div>
                    <button
                      onClick={() => onToggleStep(i)}
                      className="btn btn-secondary"
                      style={{ fontSize: 9, padding: "2px 7px", flexShrink: 0, whiteSpace: "nowrap" }}
                    >
                      {checked ? "UNDO" : "MARK DONE"}
                    </button>
                  </div>
                  {s.link && (
                    <a href={s.link} target="_blank" rel="noreferrer"
                      style={{ display: "inline-block", marginTop: 4, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a7bd5" }}>
                      → {s.linkLabel || s.link}
                    </a>
                  )}
                  {s.registrar && (
                    registrarIsUrl ? (
                      <a href={registrar} target="_blank" rel="noreferrer"
                        style={{ display: "inline-block", marginTop: 4, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a7bd5" }}>
                        → Open this client's registrar
                      </a>
                    ) : registrar ? (
                      <div style={{ marginTop: 4, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#9cc4f5" }}>
                        Registrar note: {registrar}
                      </div>
                    ) : (
                      <div style={{ marginTop: 4, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#5a7aa0" }}>
                        No registrar link saved for this client yet — add one on the Resources tab.
                      </div>
                    )
                  )}
                  {s.fields && (
                    <GuideStepFields
                      fields={s.fields} config={config} client={client} onSaveFields={onSaveFields}
                      onSaved={() => onToggleStep(i, true)}
                    />
                  )}
                  {s.testAction === "email" && (
                    <div>
                      <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
                        <input className="dg-input" style={{ fontSize: 11, flex: 1 }} value={testEmailTo} placeholder="test@…"
                          onChange={(e) => setTestEmailTo(e.target.value)} />
                        <button
                          className="btn btn-secondary" style={{ fontSize: 10 }}
                          onClick={async () => { if (await sendTestEmail()) onToggleStep(i, true); }}
                          disabled={testingEmail || !testEmailTo.trim()}
                        >
                          {testingEmail ? "SENDING…" : "SEND TEST"}
                        </button>
                      </div>
                      <div style={{ marginTop: 6 }}>
                        <button
                          className="btn btn-secondary" style={{ fontSize: 9, padding: "3px 8px" }}
                          onClick={syncEmailNow} disabled={syncingEmail}
                        >
                          {syncingEmail ? "CHECKING…" : "CHECK FOR REPLIES NOW"}
                        </button>
                        <div style={{ marginTop: 3, fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#5a7aa0" }}>
                          Reply to your own test email from the address you sent it to, then click this to pull it in immediately (it also syncs automatically every ~2 min).
                        </div>
                      </div>
                      {testError && (
                        <div style={{ marginTop: 4, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#e05c5c" }}>{testError}</div>
                      )}
                    </div>
                  )}
                  {s.testAction === "meta_ads" && (
                    <div style={{ marginTop: 8 }}>
                      <button
                        className="btn btn-secondary" style={{ fontSize: 9, padding: "3px 8px" }}
                        onClick={syncMetaAdsNow} disabled={syncingMeta}
                      >
                        {syncingMeta ? "SYNCING…" : "SYNC NOW"}
                      </button>
                      <div style={{ marginTop: 3, fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#5a7aa0" }}>
                        Pulls this client's last 3 days of Meta ad spend immediately instead of waiting for the daily 5am sync — use this to confirm the connection actually works.
                      </div>
                      {metaSyncResult && (
                        <div style={{ marginTop: 4, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#4ade80" }}>
                          {metaSyncResult}
                        </div>
                      )}
                      {metaSyncError && (
                        <div style={{ marginTop: 4, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#e05c5c" }}>
                          {metaSyncError}
                        </div>
                      )}
                    </div>
                  )}
                  {s.warmupAction && (
                    <div style={{ marginTop: 8 }}>
                      {!warmupStatus || warmupStatus.status === "not_started" ? (
                        <button
                          className="btn btn-primary" style={{ fontSize: 10 }}
                          onClick={startWarmup} disabled={warmupLoading}
                        >
                          {warmupLoading ? "STARTING…" : "START WARM-UP"}
                        </button>
                      ) : (
                        <div>
                          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                            <div style={{ flex: 1, height: 5, borderRadius: 3, background: "rgba(255,255,255,0.06)", overflow: "hidden" }}>
                              <div style={{
                                height: "100%",
                                width: `${warmupStatus.total_days ? (Math.min(warmupStatus.current_day, warmupStatus.total_days) / warmupStatus.total_days) * 100 : 0}%`,
                                background: warmupStatus.status === "complete" ? "#4ade80" : "#3a7bd5", transition: "width 0.2s",
                              }} />
                            </div>
                            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#5a7aa0", whiteSpace: "nowrap" }}>
                              {warmupStatus.status === "complete"
                                ? "WARM-UP COMPLETE ✓"
                                : `DAY ${warmupStatus.current_day}/${warmupStatus.total_days}`}
                            </div>
                          </div>
                          {warmupStatus.status === "running" && (
                            <div style={{ marginTop: 4, fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#5a7aa0" }}>
                              {warmupStatus.sent_today}/{warmupStatus.day_target} sent today (real outreach sends count toward this too)
                            </div>
                          )}
                          <button
                            className="btn btn-secondary" style={{ fontSize: 9, padding: "3px 8px", marginTop: 6 }}
                            onClick={refreshWarmupStatus} disabled={warmupLoading}
                          >
                            {warmupLoading ? "CHECKING…" : "REFRESH"}
                          </button>
                        </div>
                      )}
                      {warmupError && (
                        <div style={{ marginTop: 4, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#e05c5c" }}>{warmupError}</div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>,
    document.body
  );
}

function ClientMarketingSetup({ clientId }) {
  const [config, setConfig] = useState(null);
  const [client, setClient] = useState(null);
  const [loading, setLoading] = useState(true);
  const [provisioning, setProvisioning] = useState(false);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(null); // field name currently being edited
  const [draft, setDraft] = useState("");
  const [draft2, setDraft2] = useState(""); // second field, for multi-field editors (email)
  const [draft3, setDraft3] = useState(""); // third field (email subdomain)
  const [saving, setSaving] = useState(false);
  const [testEmailTo, setTestEmailTo] = useState("");
  const [testingEmail, setTestingEmail] = useState(false);
  const [guideKey, setGuideKey] = useState(null); // which step's guide modal is open
  const [showAutomation, setShowAutomation] = useState(false);

  const load = async () => {
    const [cr, mr] = await Promise.all([
      fetch(API(`/clients/${clientId}`)),
      fetch(API(`/clients/${clientId}/marketing-config`)),
    ]);
    if (cr.ok) setClient(await cr.json());
    if (mr.ok) setConfig(await mr.json());
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

  // Fields the guide's `fields` step type can save that actually live on the
  // `clients` row, not client_marketing_config (e.g. calendly_url, used by
  // the client portal's booking modal) — everything else in a step's fields
  // still goes to marketing-config as before.
  const CLIENT_TABLE_FIELDS = new Set(["calendly_url"]);

  // Returns { ok, error } instead of throwing, so callers (including the
  // guide modal's inline field forms) can tell a save actually took and
  // only then treat the step as done — a write that 500s (e.g. a column
  // that doesn't exist yet) must never report success.
  const saveFields = async (fields) => {
    setSaving(true);
    setError("");
    let result = { ok: true, error: null };
    try {
      const clientFields = {};
      const configFields = {};
      for (const [key, value] of Object.entries(fields)) {
        (CLIENT_TABLE_FIELDS.has(key) ? clientFields : configFields)[key] = value;
      }
      const requests = [];
      if (Object.keys(clientFields).length) {
        requests.push(fetch(API(`/clients/${clientId}`), {
          method: "PATCH", headers: { "Content-Type": "application/json" },
          body: JSON.stringify(clientFields),
        }));
      }
      if (Object.keys(configFields).length) {
        requests.push(fetch(API(`/clients/${clientId}/marketing-config`), {
          method: "PUT", headers: { "Content-Type": "application/json" },
          body: JSON.stringify(configFields),
        }));
      }
      const responses = await Promise.all(requests);
      const failed = responses.find((r) => !r.ok);
      if (failed) {
        const detail = await failed.json().catch(() => null);
        result = { ok: false, error: detail?.detail || "Failed to save" };
        setError(result.error);
      }
    } catch (e) {
      result = { ok: false, error: e.message };
      setError(e.message);
    }
    setEditing(null);
    setSaving(false);
    await load();
    return result;
  };

  const toggleGuideStep = (key, idx, value) => {
    const cur = config?.guide_progress || {};
    const nextValue = value === undefined ? !cur[key]?.[idx] : value;
    const guideProg = { ...(cur[key] || {}), [idx]: nextValue };
    saveFields({ guide_progress: { ...cur, [key]: guideProg } });
  };

  const sendTestEmail = async () => {
    if (!testEmailTo.trim()) return false;
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
      return true;
    } catch (e) {
      setError(e.message);
      return false;
    } finally {
      setTestingEmail(false);
    }
  };

  const [syncingEmail, setSyncingEmail] = useState(false);
  const syncEmailNow = async () => {
    setSyncingEmail(true);
    setError("");
    try {
      const r = await fetch(API(`/clients/${clientId}/marketing-config/sync-email`), { method: "POST" });
      if (!r.ok) {
        const detail = await r.json().catch(() => null);
        throw new Error(detail?.detail || "Failed to check for replies");
      }
      await load();
      return true;
    } catch (e) {
      setError(e.message);
      return false;
    } finally {
      setSyncingEmail(false);
    }
  };

  const [syncingMeta, setSyncingMeta] = useState(false);
  const [metaSyncResult, setMetaSyncResult] = useState("");
  const [metaSyncError, setMetaSyncError] = useState("");
  const syncMetaAdsNow = async () => {
    setSyncingMeta(true);
    setMetaSyncResult("");
    setMetaSyncError("");
    try {
      const r = await fetch(API(`/clients/${clientId}/marketing-config/sync-meta-ads`), { method: "POST" });
      const data = await r.json().catch(() => null);
      if (!r.ok) throw new Error(data?.detail || "Failed to sync Meta ads");
      setMetaSyncResult(`Synced ${data.days_synced} day(s) — check the client's portal Analytics tab.`);
    } catch (e) {
      setMetaSyncError(e.message);
    } finally {
      setSyncingMeta(false);
    }
  };

  const [warmupStatus, setWarmupStatus] = useState(null);
  const [warmupLoading, setWarmupLoading] = useState(false);
  const [warmupError, setWarmupError] = useState("");
  const fetchWarmupStatus = async () => {
    setWarmupLoading(true);
    setWarmupError("");
    try {
      const r = await fetch(API(`/clients/${clientId}/marketing-config/warmup-status`));
      if (!r.ok) throw new Error("Failed to load warm-up status");
      setWarmupStatus(await r.json());
    } catch (e) {
      setWarmupError(e.message);
    } finally {
      setWarmupLoading(false);
    }
  };
  const startWarmup = async () => {
    setWarmupLoading(true);
    setWarmupError("");
    try {
      const r = await fetch(API(`/clients/${clientId}/marketing-config/start-warmup`), { method: "POST" });
      if (!r.ok) {
        const detail = await r.json().catch(() => null);
        throw new Error(detail?.detail || "Failed to start warm-up");
      }
      await fetchWarmupStatus();
    } catch (e) {
      setWarmupError(e.message);
    } finally {
      setWarmupLoading(false);
    }
  };

  if (loading) {
    return <div style={{ padding: 16, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>LOADING…</div>;
  }

  return (
    <div style={{ padding: "14px 16px", borderTop: "1px solid rgba(58,123,213,0.1)" }}>
      <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a4a7a", marginBottom: 12, lineHeight: 1.5 }}>
        This client's OWN marketing infrastructure — their Twilio number, their email-sending
        domain, their AI response agent (see the Agent tab), their landing page, their ad
        creatives, their No Show/Cancellation automations, and their portal analytics. Separate
        from DigiGrowth's own outreach system. Numbered steps below (1-7) are meant to be done in order.
      </div>

      <button
        className="btn btn-secondary" style={{ fontSize: 10, marginBottom: 12 }}
        onClick={() => setShowAutomation((s) => !s)}
      >
        {showAutomation ? "HIDE AUTOMATION NOTES" : "WHAT CAN BE AUTOMATED?"}
      </button>
      {showAutomation && (
        <div style={{ padding: "10px 12px", borderRadius: 8, background: "rgba(58,123,213,0.06)", marginBottom: 12, display: "flex", flexDirection: "column", gap: 8 }}>
          {AUTOMATION_CANDIDATES.map((a) => (
            <div key={a.step}>
              <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 11, fontWeight: 700, color: "#9cc4f5" }}>{a.step}</div>
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#5a7aa0", marginTop: 2, lineHeight: 1.5 }}>{a.note}</div>
            </div>
          ))}
        </div>
      )}

      {MARKETING_STEPS.map((step, idx) => (
        <div key={step.key} style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "10px 12px", borderRadius: 8, background: "rgba(255,255,255,0.02)", marginBottom: 8,
        }}>
          <div>
            <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, fontWeight: 600, color: "#c8d8f0", display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ color: step.done(config) ? "#4ade80" : "#5a7aa0" }}>{step.done(config) ? "✓" : "○"}</span>
              {idx + 1}. {step.label}
            </div>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#5a7aa0", marginTop: 2 }}>
              {step.status(config, client)}
            </div>
            <button
              className="btn btn-secondary" style={{ fontSize: 9, marginTop: 6, padding: "3px 8px" }}
              onClick={() => setGuideKey(step.key)}
            >
              SET UP GUIDE
            </button>
          </div>
          {step.key === "sms" && !config?.twilio_number && (
            <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={provisionNumber} disabled={provisioning}>
              {provisioning ? "PROVISIONING…" : "BUY NUMBER"}
            </button>
          )}
          {step.key === "email" && (
            editing === "gmail" ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 6, alignItems: "flex-end" }}>
                <input className="dg-input" style={{ fontSize: 11, width: 220 }} value={draft3} placeholder="go.clientdomain.com (outreach subdomain)"
                  onChange={(e) => setDraft3(e.target.value)} autoFocus />
                <input className="dg-input" style={{ fontSize: 11, width: 220 }} value={draft2} placeholder="contact@go.clientdomain.com"
                  onChange={(e) => setDraft2(e.target.value)} />
                <input className="dg-input" style={{ fontSize: 11, width: 220 }} value={draft} placeholder="Gmail refresh token (from reauth_google.py)"
                  onChange={(e) => setDraft(e.target.value)} />
                <button className="btn btn-primary" style={{ fontSize: 10 }}
                  onClick={() => saveFields({ email_subdomain: draft3.trim() || null, gmail_sender_email: draft2.trim() || null, gmail_refresh_token: draft.trim() || null })}
                  disabled={saving}>
                  SAVE
                </button>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 6, alignItems: "flex-end" }}>
                <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={() => { setEditing("gmail"); setDraft(config?.gmail_refresh_token || ""); setDraft2(config?.gmail_sender_email || ""); setDraft3(config?.email_subdomain || ""); }}>
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

      <GuideModal
        guide={guideKey ? MARKETING_GUIDES[guideKey] : null}
        progress={guideKey ? config?.guide_progress?.[guideKey] : null}
        onToggleStep={(idx, value) => toggleGuideStep(guideKey, idx, value)}
        config={config}
        client={client}
        onSaveFields={saveFields}
        testEmailTo={testEmailTo}
        setTestEmailTo={setTestEmailTo}
        sendTestEmail={sendTestEmail}
        testingEmail={testingEmail}
        testError={error}
        syncEmailNow={syncEmailNow}
        syncingEmail={syncingEmail}
        syncMetaAdsNow={syncMetaAdsNow}
        syncingMeta={syncingMeta}
        metaSyncResult={metaSyncResult}
        metaSyncError={metaSyncError}
        warmupStatus={warmupStatus}
        warmupLoading={warmupLoading}
        warmupError={warmupError}
        startWarmup={startWarmup}
        refreshWarmupStatus={fetchWarmupStatus}
        onClose={() => setGuideKey(null)}
      />
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
