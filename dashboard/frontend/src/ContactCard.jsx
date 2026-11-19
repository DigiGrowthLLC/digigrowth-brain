import React, { useState, useEffect } from "react";
import { API } from "./api.js";
import BookingModal from "./BookingModal.jsx";
import AppointmentsSection from "./AppointmentsSection.jsx";
import PatientIntake from "./PatientIntake.jsx";

const GRADES   = ["A", "B", "C", "D"];
const STATUSES = ["new", "dialer-lead", "sms-handoff", "email-handoff", "appointment-booked", "not-interested", "send-info", "gatekeeper-deferral", "voicemail", "manual-followup"];

// Fetches/edits a contact by id. `variant="modal"` (default) renders as a
// fixed-overlay dialog (dismissible via backdrop click or Cancel) — used by
// the SMS inbox. `variant="inline"` renders just the card content with no
// overlay/backdrop, for embedding directly in a screen (e.g. the live call
// screen) — Cancel is omitted since there's nothing to dismiss back to.
export default function ContactCard({ contactId, phone, onClose, onSaved, variant = "modal", hideHeader = false }) {
  const [contact, setContact] = useState(null);
  const [form, setForm]       = useState(null);
  const [saving, setSaving]   = useState(false);
  const [error, setError]     = useState(null);
  const [bookingOpen, setBookingOpen] = useState(false);
  const [apptRefresh, setApptRefresh] = useState(0);

  const [campaignInfo, setCampaignInfo] = useState(null);
  const [availableCampaigns, setAvailableCampaigns] = useState({ sms: [], email: [] });
  const [campaignForm, setCampaignForm] = useState({ sms: "", email: "" });

  useEffect(() => {
    if (!contactId) return;
    fetch(API(`/contacts/${contactId}`))
      .then(r => r.ok ? r.json() : null)
      .then(c => { if (c) { setContact(c); setForm(c); } });
  }, [contactId]);

  const loadCampaignInfo = () => {
    if (!contactId) return;
    fetch(API(`/contacts/${contactId}/campaigns`)).then(r => r.ok ? r.json() : null).then(info => {
      setCampaignInfo(info);
      setCampaignForm({ sms: info?.sms?.id ?? "", email: info?.email?.id ?? "" });
    });
  };

  useEffect(() => {
    if (!contactId) return;
    loadCampaignInfo();
    Promise.all([
      fetch(API("/campaigns?channel=sms")).then(r => r.ok ? r.json() : []),
      fetch(API("/campaigns?channel=email")).then(r => r.ok ? r.json() : []),
    ]).then(([sms, email]) => setAvailableCampaigns({ sms, email }));
  }, [contactId]);

  const set = (k, v) => setForm(prev => ({ ...prev, [k]: v }));
  // A client's own prospect (a patient lead), not one of Dylan's B2B
  // prospects: no grade/opener/status/campaigns, shows patient intake.
  const isPatient = !!(contact?.client_id && !contact?.is_client_anchor);
  const formAnswers = (() => {
    const raw = contact?.form_answers;
    try { const v = typeof raw === "string" ? JSON.parse(raw) : raw; return Array.isArray(v) ? v : []; } catch { return []; }
  })();

  const handleSave = async () => {
    if (!form || !contactId) return;
    setSaving(true);
    setError(null);
    try {
      const patch = {};
      const editable = ["business", "owner", "phone", "email", "website", "city", "state", "grade", "opener", "notes", "status"];
      for (const k of editable) {
        if (form[k] !== contact[k]) patch[k] = form[k] ?? null;
      }

      const campaignChanges = [];
      for (const channel of ["sms", "email"]) {
        const before = campaignInfo?.[channel]?.id ?? "";
        const after = campaignForm[channel] ?? "";
        if (String(before) !== String(after)) campaignChanges.push({ channel, before, after });
      }

      if (Object.keys(patch).length === 0 && campaignChanges.length === 0) { onClose?.(); return; }

      if (Object.keys(patch).length > 0) {
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
      }

      for (const chg of campaignChanges) {
        if (chg.after) {
          await fetch(API(`/contacts/${contactId}/campaigns`), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ campaign_id: Number(chg.after) }),
          });
        } else if (chg.before) {
          await fetch(API(`/contacts/${contactId}/campaigns/${chg.before}`), { method: "DELETE" });
        }
      }
      if (campaignChanges.length > 0) loadCampaignInfo();

      onClose?.();
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

  const body = (
    <>
      {/* Header */}
      {!hideHeader && (
        <div style={{ padding: variant === "inline" ? "0 0 16px" : "20px 24px 16px", borderBottom: "0.5px solid #1a2540", flexShrink: 0 }}>
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
            <div>
              <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 17, fontWeight: 700, color: "#f0f4ff" }}>
                {contact?.owner || contact?.business || phone}
              </div>
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80", letterSpacing: "0.1em", marginTop: 3 }}>
                {contact?.phone || phone}{contact?.grade && !isPatient ? ` · GRADE ${contact.grade}` : ""}{isPatient && contact?.client_name ? ` · ${contact.client_name.toUpperCase()} PROSPECT` : ""}
              </div>
            </div>
            {variant === "modal" && (
              <button onClick={onClose} style={{
                background: "transparent", border: "none", color: "#3a5a80",
                cursor: "pointer", fontSize: 18, lineHeight: 1, padding: "2px 6px",
              }}>×</button>
            )}
          </div>
        </div>
      )}

      {/* Body */}
      <div style={{ flex: 1, overflowY: "auto", padding: variant === "inline" ? (hideHeader ? "0" : "16px 0 0") : "20px 24px" }}>
        {!form ? (
          contactId ? (
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52" }}>LOADING…</div>
          ) : (
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80" }}>
              No contact record found for {phone}.<br />
              <span style={{ color: "#2a4070" }}>Create a contact from the CRM tab to link it.</span>
            </div>
          )
        ) : isPatient ? (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2" style={{ gap: "0 16px" }}>
              <Field label="NAME" k="owner" />
              <Field label="PHONE" k="phone" />
              <Field label="EMAIL" k="email" />
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", letterSpacing: "0.12em", marginBottom: 4 }}>SOURCE</div>
                <div style={{ fontSize: 12, color: "#d0e8ff", padding: "7px 0" }}>{(contact?.lead_source || "—").replace(/_/g, " ")}{contact?.lead_platform ? ` · ${contact.lead_platform}` : ""}</div>
              </div>
            </div>
            <div style={{ marginBottom: 16 }}>
              <PatientIntake base={API(`/contact-cards/${contactId}/intake`)} />
            </div>
            {formAnswers.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", letterSpacing: "0.12em", marginBottom: 6 }}>LEAD FORM ANSWERS</div>
                <div className="glass-card-sm" style={{ padding: "10px 12px", display: "flex", flexDirection: "column", gap: 8 }}>
                  {formAnswers.map((a, i) => (
                    <div key={i}>
                      <div style={{ fontSize: 11, color: "#6a8ab0" }}>{a.question}</div>
                      <div style={{ fontSize: 12.5, color: "#f0f4ff", whiteSpace: "pre-wrap" }}>{a.answer}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <AppointmentsSection contactId={contactId} refreshSignal={apptRefresh} />
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", letterSpacing: "0.12em", marginBottom: 4 }}>NOTES</div>
              <textarea className="dg-input"
                style={{ width: "100%", fontSize: 12, resize: "vertical", minHeight: 72, boxSizing: "border-box" }}
                value={form?.notes ?? ""}
                onChange={e => set("notes", e.target.value)}
              />
            </div>
          </>
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2" style={{ gap: "0 16px" }}>
              <Field label="BUSINESS NAME" k="business" />
              <Field label="OWNER / CONTACT" k="owner" />
              <Field label="PHONE" k="phone" />
              <Field label="EMAIL" k="email" />
              <Field label="WEBSITE" k="website" />
              <Field label="CITY" k="city" />
              <Field label="STATE" k="state" />
              <Field label="GRADE" k="grade" options={GRADES} />
            </div>
            <Field label="CUSTOM OPENER" k="opener" />
            <Field label="STATUS" k="status" options={STATUSES} />

            <div className="grid grid-cols-1 sm:grid-cols-2" style={{ gap: "0 16px" }}>
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", letterSpacing: "0.12em", marginBottom: 4 }}>
                  SMS CAMPAIGN
                </div>
                <select className="dg-input" style={{ width: "100%", fontSize: 12 }}
                  value={campaignForm.sms} onChange={e => setCampaignForm(f => ({ ...f, sms: e.target.value }))}>
                  <option value="">—</option>
                  {(availableCampaigns.sms || []).map(c => (
                    <option key={c.id} value={c.id}>{c.name}{campaignInfo?.sms?.id === c.id && campaignInfo.sms.pending ? " (pending)" : ""}</option>
                  ))}
                </select>
              </div>
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", letterSpacing: "0.12em", marginBottom: 4 }}>
                  EMAIL CAMPAIGN
                </div>
                <select className="dg-input" style={{ width: "100%", fontSize: 12 }}
                  value={campaignForm.email} onChange={e => setCampaignForm(f => ({ ...f, email: e.target.value }))}>
                  <option value="">—</option>
                  {(availableCampaigns.email || []).map(c => (
                    <option key={c.id} value={c.id}>{c.name}{campaignInfo?.email?.id === c.id && campaignInfo.email.pending ? " (pending)" : ""}</option>
                  ))}
                </select>
              </div>
            </div>

            <AppointmentsSection contactId={contactId} refreshSignal={apptRefresh} />
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
        <div style={{ padding: variant === "inline" ? "14px 0 0" : "14px 24px", borderTop: "0.5px solid #1a2540", flexShrink: 0, display: "flex", gap: 10 }}>
          {variant === "modal" && (
            <button onClick={onClose} className="btn btn-secondary" style={{ flex: 1, fontSize: 11 }}>Cancel</button>
          )}
          {!isPatient && <button onClick={() => setBookingOpen(true)} className="btn btn-ghost" style={{
            flex: 1, fontSize: 11, borderColor: "rgba(20,200,130,0.35)", color: "#14c882",
          }}>
            📅 Book Appointment
          </button>}
          <button onClick={handleSave} disabled={saving} className="btn btn-primary" style={{ flex: 1, fontSize: 11 }}>
            {saving ? "Saving…" : "Save Changes"}
          </button>
        </div>
      )}
    </>
  );

  const bookingModal = (
    <BookingModal
      open={bookingOpen}
      onClose={() => setBookingOpen(false)}
      contactId={contactId}
      phone={form?.phone || phone}
      name={form?.owner}
      email={form?.email}
      contact={{ business: form?.business, city: form?.city, state: form?.state, grade: form?.grade, website: form?.website }}
      onBooked={() => setApptRefresh(n => n + 1)}
    />
  );

  if (variant === "inline") {
    return (
      <div style={{ display: "flex", flexDirection: "column" }}>
        {body}
        {bookingModal}
      </div>
    );
  }

  return (
    <>
      <div
        style={{
          position: "fixed", inset: 0, background: "rgba(0,0,0,0.65)",
          backdropFilter: "blur(6px)", zIndex: 1000,
          display: "flex", alignItems: "center", justifyContent: "center",
          padding: 16,
        }}
        onClick={onClose}
      >
        <div
          className="glass-card w-full sm:w-[480px]"
          style={{ maxHeight: "85vh", display: "flex", flexDirection: "column", padding: 0, overflow: "hidden" }}
          onClick={e => e.stopPropagation()}
        >
          {body}
        </div>
      </div>
      {bookingModal}
    </>
  );
}
