import React, { useState, useEffect, useRef, useCallback } from "react";
import { API } from "../api.js";

const GRADES   = ["A", "B", "C", "D"];
const STATUSES = ["new", "dialer-lead", "sms-handoff", "appointment-booked", "not-interested", "send-info", "voicemail", "manual-followup"];

function fmtMsgTime(ts) {
  if (!ts) return "";
  const d = new Date(ts), diff = Date.now() - d;
  if (diff < 86400000) return d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" }) + ", " +
         d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
}

// ── Contact Card Modal ────────────────────────────────────────────────────────

function ContactCard({ contactId, phone, onClose, onSaved }) {
  const [contact, setContact] = useState(null);
  const [form, setForm]       = useState(null);
  const [saving, setSaving]   = useState(false);
  const [error, setError]     = useState(null);

  useEffect(() => {
    if (!contactId) return;
    fetch(API(`/contacts/${contactId}`))
      .then(r => r.ok ? r.json() : null)
      .then(c => { if (c) { setContact(c); setForm(c); } });
  }, [contactId]);

  const set = (k, v) => setForm(prev => ({ ...prev, [k]: v }));

  const handleSave = async () => {
    if (!form || !contactId) return;
    setSaving(true);
    setError(null);
    try {
      const patch = {};
      const editable = ["business", "owner", "phone", "email", "website", "city", "state", "grade", "notes", "status"];
      for (const k of editable) {
        if (form[k] !== contact[k]) patch[k] = form[k] ?? null;
      }
      if (Object.keys(patch).length === 0) { onClose(); return; }
      const r = await fetch(API(`/contacts/${contactId}`), {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      });
      if (!r.ok) { setError(await r.text()); return; }
      const updated = await r.json();
      setContact(updated);
      setForm(updated);
      onSaved?.(updated);
      onClose();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const Field = ({ label, k, type = "text", options }) => (
    <div style={{ marginBottom: 12 }}>
      <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", letterSpacing: "0.12em", marginBottom: 4 }}>
        {label}
      </div>
      {options ? (
        <select className="dg-input" style={{ width: "100%", fontSize: 12 }}
          value={form?.[k] ?? ""} onChange={e => set(k, e.target.value)}>
          <option value="">—</option>
          {options.map(o => <option key={o} value={o}>{o}</option>)}
        </select>
      ) : (
        <input className="dg-input" type={type}
          style={{ width: "100%", fontSize: 12, boxSizing: "border-box" }}
          value={form?.[k] ?? ""}
          onChange={e => set(k, e.target.value)}
        />
      )}
    </div>
  );

  return (
    <div
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.65)",
        backdropFilter: "blur(6px)", zIndex: 1000,
        display: "flex", alignItems: "center", justifyContent: "center",
      }}
      onClick={onClose}
    >
      <div
        className="glass-card"
        style={{ width: 480, maxHeight: "85vh", display: "flex", flexDirection: "column", padding: 0, overflow: "hidden" }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ padding: "20px 24px 16px", borderBottom: "0.5px solid #1a2540", flexShrink: 0 }}>
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
            <div>
              <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 17, fontWeight: 700, color: "#f0f4ff" }}>
                {contact?.business || contact?.owner || phone}
              </div>
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80", letterSpacing: "0.1em", marginTop: 3 }}>
                {phone}{contact?.grade ? ` · GRADE ${contact.grade}` : ""}
              </div>
            </div>
            <button onClick={onClose} style={{
              background: "transparent", border: "none", color: "#3a5a80",
              cursor: "pointer", fontSize: 18, lineHeight: 1, padding: "2px 6px",
            }}>×</button>
          </div>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: "auto", padding: "20px 24px" }}>
          {!form ? (
            contactId ? (
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52" }}>LOADING…</div>
            ) : (
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80" }}>
                No contact record found for {phone}.<br />
                <span style={{ color: "#2a4070" }}>Create a contact from the CRM tab to link it.</span>
              </div>
            )
          ) : (
            <>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 16px" }}>
                <Field label="BUSINESS NAME" k="business" />
                <Field label="OWNER / CONTACT" k="owner" />
                <Field label="PHONE" k="phone" />
                <Field label="EMAIL" k="email" />
                <Field label="WEBSITE" k="website" />
                <Field label="CITY" k="city" />
                <Field label="STATE" k="state" />
                <Field label="GRADE" k="grade" options={GRADES} />
              </div>
              <Field label="STATUS" k="status" options={STATUSES} />
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", letterSpacing: "0.12em", marginBottom: 4 }}>NOTES</div>
                <textarea className="dg-input"
                  style={{ width: "100%", fontSize: 12, resize: "vertical", minHeight: 72, boxSizing: "border-box" }}
                  value={form?.notes ?? ""}
                  onChange={e => set("notes", e.target.value)}
                />
              </div>
            </>
          )}

          {error && (
            <div style={{ marginTop: 8, padding: "8px 12px", borderRadius: 8,
              background: "rgba(220,60,60,0.08)", border: "1px solid rgba(220,60,60,0.2)",
              fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#dc3c3c" }}>
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        {form && (
          <div style={{ padding: "14px 24px", borderTop: "0.5px solid #1a2540", flexShrink: 0, display: "flex", gap: 10 }}>
            <button onClick={onClose} className="btn btn-secondary" style={{ flex: 1, fontSize: 11 }}>Cancel</button>
            <button onClick={handleSave} disabled={saving} className="btn btn-primary" style={{ flex: 1, fontSize: 11 }}>
              {saving ? "Saving…" : "Save Changes"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Compose Modal ─────────────────────────────────────────────────────────────

function ComposeModal({ onClose, onSent }) {
  const [phone, setPhone]     = useState("");
  const [body, setBody]       = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError]     = useState(null);

  const handleSend = async () => {
    const p = phone.trim().replace(/\s+/g, "");
    const b = body.trim();
    if (!p || !b) return;
    setSending(true);
    setError(null);
    try {
      const r = await fetch(API("/sms/send"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone: p, body: b }),
      });
      if (!r.ok) { setError(await r.text()); return; }
      onSent(p);
    } catch (e) {
      setError(e.message);
    } finally {
      setSending(false);
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
      <div
        className="glass-card"
        style={{ width: 420, padding: 0, overflow: "hidden" }}
        onClick={e => e.stopPropagation()}
      >
        <div style={{ padding: "18px 22px 14px", borderBottom: "0.5px solid #1a2540", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 15, fontWeight: 700, color: "#f0f4ff" }}>
            New Message
          </div>
          <button onClick={onClose} style={{ background: "transparent", border: "none", color: "#3a5a80", cursor: "pointer", fontSize: 18, lineHeight: 1, padding: "2px 6px" }}>×</button>
        </div>

        <div style={{ padding: "18px 22px" }}>
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", letterSpacing: "0.12em", marginBottom: 5 }}>TO (PHONE NUMBER)</div>
            <input
              className="dg-input"
              type="tel"
              placeholder="+1 555 000 0000"
              value={phone}
              onChange={e => setPhone(e.target.value)}
              style={{ width: "100%", fontSize: 13, boxSizing: "border-box" }}
              autoFocus
            />
          </div>
          <div style={{ marginBottom: 6 }}>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", letterSpacing: "0.12em", marginBottom: 5 }}>MESSAGE</div>
            <textarea
              className="dg-input"
              rows={4}
              placeholder="Type your message…"
              value={body}
              onChange={e => setBody(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleSend(); }}
              style={{ width: "100%", fontSize: 13, resize: "none", boxSizing: "border-box" }}
            />
          </div>
          {error && (
            <div style={{ marginBottom: 10, padding: "8px 12px", borderRadius: 8,
              background: "rgba(220,60,60,0.08)", border: "1px solid rgba(220,60,60,0.2)",
              fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#dc3c3c" }}>
              {error}
            </div>
          )}
        </div>

        <div style={{ padding: "12px 22px 18px", display: "flex", gap: 10 }}>
          <button onClick={onClose} className="btn btn-secondary" style={{ flex: 1, fontSize: 11 }}>Cancel</button>
          <button
            onClick={handleSend}
            disabled={sending || !phone.trim() || !body.trim()}
            className="btn btn-primary"
            style={{ flex: 1, fontSize: 11 }}
          >
            {sending ? "Sending…" : "Send"}
          </button>
        </div>
      </div>
    </div>
  );
}


// ── Main panel ────────────────────────────────────────────────────────────────

export default function SMSPanel({ initialPhone }) {
  const [convos, setConvos]       = useState([]);
  const [selected, setSelected]   = useState(null);
  const [thread, setThread]       = useState(null);
  const [replyText, setReplyText] = useState("");
  const [sending, setSending]     = useState(false);
  const [loading, setLoading]     = useState(true);
  const [cardOpen, setCardOpen]   = useState(false);
  const [deleting, setDeleting]   = useState(false);
  const [composing, setComposing] = useState(false);
  const bottomRef = useRef(null);

  const loadConvos = useCallback(async () => {
    try {
      const r = await fetch(API("/sms/conversations"));
      if (r.ok) setConvos(await r.json());
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => {
    loadConvos();
    const id = setInterval(loadConvos, 15000);
    return () => clearInterval(id);
  }, [loadConvos]);

  useEffect(() => {
    if (initialPhone) openThread(initialPhone);
  }, [initialPhone]);

  const openThread = async (phone) => {
    setSelected(phone);
    setThread(null);
    try {
      const r = await fetch(API(`/sms/conversations/${encodeURIComponent(phone)}`));
      if (r.ok) setThread(await r.json());
    } catch {}
  };

  useEffect(() => {
    if (!selected) return;
    const id = setInterval(() => openThread(selected), 8000);
    return () => clearInterval(id);
  }, [selected]);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [thread?.messages]);

  const sendReply = async () => {
    if (!replyText.trim() || !selected) return;
    setSending(true);
    try {
      await fetch(API("/sms/send"), {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone: selected, body: replyText.trim() }),
      });
      setReplyText("");
      await openThread(selected);
      await loadConvos();
    } catch {}
    setSending(false);
  };

  const closeConvo = async () => {
    if (!selected) return;
    await fetch(API(`/sms/conversations/${encodeURIComponent(selected)}/close`), { method: "POST" });
    await openThread(selected);
    await loadConvos();
  };

  const deleteConvo = async () => {
    if (!selected) return;
    setDeleting(true);
    try {
      await fetch(API(`/sms/conversations/${encodeURIComponent(selected)}`), { method: "DELETE" });
      setSelected(null);
      setThread(null);
      await loadConvos();
    } catch {}
    setDeleting(false);
  };

  return (
    <div style={{ display: "flex", height: "100%" }}>

      {cardOpen && (
        <ContactCard
          contactId={thread?.contact_id}
          phone={selected}
          onClose={() => setCardOpen(false)}
          onSaved={() => openThread(selected)}
        />
      )}

      {composing && (
        <ComposeModal
          onClose={() => setComposing(false)}
          onSent={async (phone) => {
            setComposing(false);
            await loadConvos();
            await openThread(phone);
          }}
        />
      )}

      {/* Thread list */}
      <aside style={{
        width: 260, borderRight: "0.5px solid #1a2540",
        display: "flex", flexDirection: "column", flexShrink: 0,
      }}>
        <div style={{ padding: "14px 16px", borderBottom: "0.5px solid #1a2540",
                      display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 14, fontWeight: 600, color: "#f0f4ff" }}>
            SMS Inbox
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80" }}>
              {convos.length} THREADS
            </div>
            <button
              onClick={() => setComposing(true)}
              style={{
                padding: "4px 10px", borderRadius: 6,
                border: "1px solid rgba(58,123,213,0.35)",
                background: "rgba(58,123,213,0.08)", color: "#3a7bd5",
                fontFamily: "'Share Tech Mono', monospace", fontSize: 9,
                cursor: "pointer", letterSpacing: "0.06em",
              }}
            >
              + NEW
            </button>
          </div>
        </div>

        <div style={{ flex: 1, overflowY: "auto" }}>
          {loading && (
            <div style={{ padding: 16, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52" }}>
              LOADING...
            </div>
          )}
          {!loading && convos.length === 0 && (
            <div style={{ padding: 16, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52" }}>
              NO CONVERSATIONS
            </div>
          )}
          {convos.map(c => (
            <button key={c.phone} onClick={() => openThread(c.phone)}
              style={{
                width: "100%", textAlign: "left", padding: "12px 16px",
                cursor: "pointer",
                background: selected === c.phone ? "#0d1626" : "transparent",
                borderBottom: "0.5px solid #1a2540",
                borderLeft: selected === c.phone ? "2px solid #3a7bd5" : "2px solid transparent",
                borderTop: "none", borderRight: "none",
                transition: "all 0.1s",
              }}
              onMouseEnter={e => { if (selected !== c.phone) e.currentTarget.style.background = "#0a1020"; }}
              onMouseLeave={e => { if (selected !== c.phone) e.currentTarget.style.background = "transparent"; }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 3 }}>
                <span style={{ fontSize: 13, fontWeight: 500, color: "#c4d0e8", overflow: "hidden",
                               textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>
                  {c.business || c.owner || c.phone}
                </span>
                <span className={`badge ${c.status === "closed" ? "badge-green" : "badge-blue"}`}
                  style={{ marginLeft: 6, flexShrink: 0 }}>
                  {c.status === "closed" ? "BOOKED" : "ACTIVE"}
                </span>
              </div>
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a4a7a" }}>
                {c.phone}
              </div>
              {c.last_message && (
                <div style={{ fontSize: 11, color: "#3a4f6f", marginTop: 4,
                              overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {c.last_message}
                </div>
              )}
            </button>
          ))}
        </div>
      </aside>

      {/* Thread view */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        {!selected ? (
          <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center",
                        justifyContent: "center", gap: 8 }}>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52", letterSpacing: "0.2em" }}>
              SELECT A CONVERSATION
            </div>
          </div>
        ) : (
          <>
            {/* Thread header */}
            <div style={{ padding: "14px 20px", borderBottom: "0.5px solid #1a2540",
                          display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0 }}>
              <div
                onClick={() => setCardOpen(true)}
                style={{ cursor: "pointer" }}
                title="View contact card"
              >
                <div style={{
                  fontFamily: "'Space Grotesk', sans-serif", fontSize: 14, fontWeight: 600, color: "#f0f4ff",
                  display: "flex", alignItems: "center", gap: 6,
                }}>
                  {thread?.business || thread?.owner || selected}
                  <span style={{
                    fontFamily: "'Share Tech Mono', monospace", fontSize: 8, color: "#3a7bd5",
                    padding: "2px 6px", borderRadius: 4, background: "rgba(58,123,213,0.1)",
                    letterSpacing: "0.06em",
                  }}>VIEW</span>
                </div>
                <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80",
                              letterSpacing: "0.1em", marginTop: 2 }}>
                  {selected}{thread?.grade ? ` · GRADE ${thread.grade}` : ""}
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                {thread?.status !== "closed" && (
                  <button onClick={closeConvo} className="btn btn-ghost"
                    style={{ fontSize: 10, borderColor: "rgba(20,200,130,0.35)", color: "#14c882" }}>
                    MARK BOOKED
                  </button>
                )}
                <button
                  onClick={deleteConvo}
                  disabled={deleting}
                  style={{
                    padding: "6px 12px", borderRadius: 8, border: "1px solid rgba(220,60,60,0.25)",
                    background: "rgba(220,60,60,0.06)", color: "#dc3c3c",
                    fontFamily: "'Share Tech Mono', monospace", fontSize: 9,
                    cursor: "pointer", letterSpacing: "0.06em",
                    opacity: deleting ? 0.5 : 1,
                  }}
                >
                  {deleting ? "…" : "DELETE"}
                </button>
              </div>
            </div>

            {/* Messages */}
            <div style={{ flex: 1, overflowY: "auto", padding: "16px 20px", display: "flex",
                          flexDirection: "column", gap: 10 }}>
              {!thread && (
                <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52" }}>
                  LOADING...
                </div>
              )}
              {thread?.messages?.map((m, i) => {
                const isOut = m.direction === "outbound";
                return (
                  <div key={i} style={{ display: "flex", justifyContent: isOut ? "flex-end" : "flex-start" }}>
                    <div style={{
                      maxWidth: 320, padding: "9px 13px", borderRadius: isOut ? "8px 8px 2px 8px" : "8px 8px 8px 2px",
                      background: isOut ? "#1f3d70" : "#0d1626",
                      border: `0.5px solid ${isOut ? "#2857a0" : "#1a2540"}`,
                    }}>
                      <div style={{ fontSize: 13, color: isOut ? "#c8dcff" : "#8aaad0", lineHeight: 1.4 }}>
                        {m.body}
                      </div>
                      <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9,
                                    color: isOut ? "#5a7faa" : "#4a6a8a", marginTop: 4, textAlign: isOut ? "right" : "left" }}>
                        {fmtMsgTime(m.sent_at)}
                      </div>
                    </div>
                  </div>
                );
              })}
              <div ref={bottomRef} />
            </div>

            {/* Reply box */}
            {thread?.status !== "closed" ? (
              <div style={{ padding: "12px 20px", borderTop: "0.5px solid #1a2540", flexShrink: 0, display: "flex", gap: 8 }}>
                <textarea
                  value={replyText}
                  onChange={e => setReplyText(e.target.value)}
                  onKeyDown={e => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) sendReply(); }}
                  placeholder="Type a reply… (⌘↵ to send)"
                  rows={2}
                  className="dg-input"
                  style={{ flex: 1, resize: "none", fontSize: 13 }}
                />
                <button onClick={sendReply} disabled={sending || !replyText.trim()}
                  className="btn btn-primary" style={{ alignSelf: "flex-end" }}>
                  {sending ? "..." : "SEND"}
                </button>
              </div>
            ) : (
              <div style={{ padding: "12px 20px", borderTop: "0.5px solid #1a2540",
                            textAlign: "center", fontFamily: "'Share Tech Mono', monospace",
                            fontSize: 10, color: "#14c882", letterSpacing: "0.18em" }}>
                APPOINTMENT BOOKED · CONVERSATION CLOSED
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
