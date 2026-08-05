import React, { useState, useEffect } from "react";
import { API } from "./api.js";
import BookingModal from "./BookingModal.jsx";
import AppointmentsSection from "./AppointmentsSection.jsx";

const GRADES   = ["A", "B", "C", "D"];
const STATUSES = ["new", "dialer-lead", "sms-handoff", "appointment-booked", "not-interested", "send-info", "voicemail", "manual-followup"];

// Fetches/edits a contact by id. `variant="modal"` (default) renders as a
// fixed-overlay dialog (dismissible via backdrop click or Cancel) — used by
// the SMS inbox. `variant="inline"` renders just the card content with no
// overlay/backdrop, for embedding directly in a screen (e.g. the live call
// screen) — Cancel is omitted since there's nothing to dismiss back to.
function CampaignChip({ name, color, onRemove }) {
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

export default function ContactCard({ contactId, phone, onClose, onSaved, variant = "modal", hideHeader = false }) {
  const [contact, setContact] = useState(null);
  const [form, setForm]       = useState(null);
  const [saving, setSaving]   = useState(false);
  const [error, setError]     = useState(null);
  const [bookingOpen, setBookingOpen] = useState(false);
  const [apptRefresh, setApptRefresh] = useState(0);

  const [campaignInfo, setCampaignInfo] = useState(null);
  const [availableCampaigns, setAvailableCampaigns] = useState([]);
  const [campaignPick, setCampaignPick] = useState("");

  useEffect(() => {
    if (!contactId) return;
    fetch(API(`/contacts/${contactId}`))
      .then(r => r.ok ? r.json() : null)
      .then(c => { if (c) { setContact(c); setForm(c); } });
  }, [contactId]);

  const loadCampaignInfo = () => {
    if (!contactId) return;
    fetch(API(`/contacts/${contactId}/campaigns`)).then(r => r.ok ? r.json() : null).then(setCampaignInfo);
  };

  useEffect(() => {
    if (!contactId) return;
    loadCampaignInfo();
    Promise.all([
      fetch(API("/campaigns?channel=sms")).then(r => r.ok ? r.json() : []),
      fetch(API("/campaigns?channel=email")).then(r => r.ok ? r.json() : []),
    ]).then(([sms, email]) => {
      setAvailableCampaigns([
        ...sms.map(c => ({ ...c, channel: "sms" })),
        ...email.map(c => ({ ...c, channel: "email" })),
      ]);
    });
  }, [contactId]);

  async function addCampaign(campaignId) {
    if (!campaignId) return;
    const res = await fetch(API(`/contacts/${contactId}/campaigns`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ campaign_id: Number(campaignId) }),
    });
    if (res.ok) {
      setCampaignPick("");
      loadCampaignInfo();
    }
  }

  async function removeCampaign(campaignId) {
    const res = await fetch(API(`/contacts/${contactId}/campaigns/${campaignId}`), { method: "DELETE" });
    if (res.ok) loadCampaignInfo();
  }

  const set = (k, v) => setForm(prev => ({ ...prev, [k]: v }));

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
      if (Object.keys(patch).length === 0) { onClose?.(); return; }
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
                {phone}{contact?.grade ? ` · GRADE ${contact.grade}` : ""}
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
            <Field label="CUSTOM OPENER" k="opener" />
            <Field label="STATUS" k="status" options={STATUSES} />

            <div style={{ marginBottom: 12 }}>
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", letterSpacing: "0.12em", marginBottom: 4 }}>CAMPAIGN</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 8 }}>
                {campaignInfo?.sms && (
                  <CampaignChip
                    name={`SMS: ${campaignInfo.sms.name}${campaignInfo.sms.pending ? " (pending)" : ""}`}
                    color="#5a9bf0"
                    onRemove={() => removeCampaign(campaignInfo.sms.id)}
                  />
                )}
                {campaignInfo?.email && (
                  <CampaignChip
                    name={`Email: ${campaignInfo.email.name}${campaignInfo.email.pending ? " (pending)" : ""}`}
                    color="#9b6bd8"
                    onRemove={() => removeCampaign(campaignInfo.email.id)}
                  />
                )}
                {!campaignInfo?.sms && !campaignInfo?.email && (
                  <span style={{ fontSize: 11, color: "#3a5a80" }}>Not in a campaign.</span>
                )}
              </div>
              <div style={{ display: "flex", gap: 6 }}>
                <select value={campaignPick} onChange={e => setCampaignPick(e.target.value)}
                  className="dg-input" style={{ flex: 1, fontSize: 11 }}>
                  <option value="">— add to campaign —</option>
                  {availableCampaigns
                    .filter(c => !(c.channel === "sms" && campaignInfo?.sms) && !(c.channel === "email" && campaignInfo?.email))
                    .map(c => (
                      <option key={c.id} value={c.id}>{c.channel === "sms" ? "SMS" : "Email"}: {c.name}</option>
                    ))}
                </select>
                <button type="button" onClick={() => addCampaign(campaignPick)} disabled={!campaignPick} className="btn btn-secondary" style={{ fontSize: 11 }}>
                  Add
                </button>
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
          <button onClick={() => setBookingOpen(true)} className="btn btn-ghost" style={{
            flex: 1, fontSize: 11, borderColor: "rgba(20,200,130,0.35)", color: "#14c882",
          }}>
            📅 Book Appointment
          </button>
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
        }}
        onClick={onClose}
      >
        <div
          className="glass-card"
          style={{ width: 480, maxHeight: "85vh", display: "flex", flexDirection: "column", padding: 0, overflow: "hidden" }}
          onClick={e => e.stopPropagation()}
        >
          {body}
        </div>
      </div>
      {bookingModal}
    </>
  );
}
