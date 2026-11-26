import React, { useState } from "react";

// Full "click the appointment -> graphic card" outcome flow — replaces the
// old always-visible inline AppointmentOutcomeButtons row in AppointmentsPanel
// with a modal opened on row click, showing Show Y/N, Closed/Not Closed, and
// a free-text notes field together, then saving all three in one PATCH.
// `patchUrl` is passed in so this same component works against both the
// internal OS's /api/appointment-reminders/{id} and the client portal's
// /portal-api/{token}/appointments/{id} — same payload shape either way.
function Pill({ active, color, onClick, disabled, children }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        fontFamily: "'Share Tech Mono', monospace", fontSize: 11, letterSpacing: "0.06em",
        padding: "8px 16px", borderRadius: 6, cursor: disabled ? "not-allowed" : "pointer",
        color: active ? color : "#5a6f8f",
        background: active ? `${color}1a` : "transparent",
        border: `1px solid ${active ? color : "#1a2540"}`,
        fontWeight: 600, opacity: disabled ? 0.5 : 1,
      }}
    >{children}</button>
  );
}

function fmtWhen(ts) {
  if (!ts) return "";
  return new Date(ts).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

// ratingUrl (client portal only): once Showed + Closed are picked, the card
// asks whether the patient was a good fit — the lead-quality loop in
// backend csm_extras.py (tags the contact, feeds reports, flags targeting).
export default function AppointmentOutcomeCard({ appointment, patchUrl, ratingUrl, onClose, onSaved, showRevenueFields = false }) {
  const [show, setShow]   = useState(appointment.outcome_show || null);
  const [close, setClose] = useState(appointment.outcome_close || null);
  const [fit, setFit]     = useState(appointment.fit_rating || null);
  const [fitNote, setFitNote] = useState(appointment.fit_note || "");
  const askFit = !!ratingUrl && show === "show" && close === "closed";
  const [notes, setNotes] = useState(appointment.outcome_notes || "");
  // Agency-level sales KPIs (Dylan's own pipeline only) -- only ever read,
  // sent, and rendered when showRevenueFields is true (internal
  // AppointmentsPanel). Never wired into the client-portal usage of this
  // same component -- see routers/appointments.py vs. client_portal.py.
  const [pricing, setPricing] = useState(
    appointment.pricing != null ? String(appointment.pricing) : ""
  );
  const [callLength, setCallLength] = useState(appointment.call_length || "");
  const [callRecordingUrl, setCallRecordingUrl] = useState(appointment.call_recording_url || "");
  const [questionFormUrl, setQuestionFormUrl] = useState(appointment.question_form_url || "");
  const [saving, setSaving] = useState(false);
  const [err, setErr]       = useState("");

  const save = async () => {
    setSaving(true);
    setErr("");
    try {
      const body = { outcome_show: show, outcome_close: close, outcome_notes: notes.trim() || null };
      if (showRevenueFields) {
        body.pricing = pricing.trim() === "" ? null : Number(pricing);
        body.call_length = callLength.trim() || null;
        body.call_recording_url = callRecordingUrl.trim() || null;
        body.question_form_url = questionFormUrl.trim() || null;
      }
      const r = await fetch(patchUrl, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const resp = await r.json().catch(() => ({}));
      if (!r.ok) {
        setErr(resp.detail || "Couldn't save outcome.");
        setSaving(false);
        return;
      }
      if (askFit && fit) {
        await fetch(ratingUrl, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ rating: fit, note: fitNote.trim() }),
        }).catch(() => {});
      }
      const saved = { ...appointment, outcome_show: show, outcome_close: close, outcome_notes: notes.trim() || null,
        ...(askFit && fit ? { fit_rating: fit, fit_note: fitNote.trim() || null } : {}) };
      if (resp.blueprint) {
        saved.own_blueprint_status = resp.blueprint.status;
        saved.own_blueprint_url = resp.blueprint.url || null;
      }
      if (showRevenueFields) {
        saved.pricing = body.pricing;
        saved.call_length = body.call_length;
        saved.call_recording_url = body.call_recording_url;
        saved.question_form_url = body.question_form_url;
      }
      onSaved?.(saved);
    } catch (e) {
      setErr("Couldn't save outcome: " + e.message);
      setSaving(false);
    }
  };

  const labelStyle = { fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80", letterSpacing: "0.15em", marginBottom: 8 };

  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 60, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ position: "absolute", inset: 0, background: "rgba(8,12,20,0.72)" }} onClick={onClose} />
      <div className="glass-card" style={{
        position: "relative", width: 440, maxWidth: "92vw", maxHeight: "88vh", overflowY: "auto",
        padding: 24, display: "flex", flexDirection: "column", gap: 18,
      }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 10 }}>
          <div>
            <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 16, fontWeight: 700, color: "#f0f4ff" }}>
              {appointment.prospect_name || "Appointment"}
            </div>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80", letterSpacing: "0.1em", marginTop: 3 }}>
              {fmtWhen(appointment.appointment_at)}
            </div>
          </div>
          <button onClick={onClose} style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 12, color: "#3a5a80", background: "none", border: "none", cursor: "pointer", padding: "2px 6px" }}>✕</button>
        </div>

        <div>
          <div style={labelStyle}>DID THEY SHOW?</div>
          <div style={{ display: "flex", gap: 8 }}>
            <Pill active={show === "show"} color="#14c882" disabled={saving}
              onClick={() => setShow(show === "show" ? null : "show")}>YES — SHOWED</Pill>
            <Pill active={show === "no_show"} color="#dc3c3c" disabled={saving}
              onClick={() => setShow(show === "no_show" ? null : "no_show")}>NO — NO SHOW</Pill>
          </div>
        </div>

        <div>
          <div style={labelStyle}>CONCLUSION</div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <Pill active={close === "closed"} color="#14c882" disabled={saving}
              onClick={() => setClose(close === "closed" ? null : "closed")}>CLOSED</Pill>
            <Pill active={close === "not_closed"} color="#dc3c3c" disabled={saving}
              onClick={() => setClose(close === "not_closed" ? null : "not_closed")}>NOT CLOSED</Pill>
            {/* Dylan's own sales calls only: no close yet, a second call is
                booked. Saving it queues the prospect's blueprint
                (backend sales_tracking.py), linked on their next appointment. */}
            {showRevenueFields && (
              <Pill active={close === "two_call"} color="#f2ad3d" disabled={saving}
                onClick={() => setClose(close === "two_call" ? null : "two_call")}>TWO-CALL CLOSE</Pill>
            )}
          </div>
          {showRevenueFields && close === "two_call" && (
            <div style={{ fontSize: 11.5, color: "#c9a25a", marginTop: 8, lineHeight: 1.45 }}>
              {appointment.own_blueprint_status === "done" && appointment.own_blueprint_url
                ? <>Blueprint ready: <a href={appointment.own_blueprint_url} target="_blank" rel="noreferrer" style={{ color: "#f2ad3d" }}>open it</a>. It's also linked on their next appointment.</>
                : appointment.own_blueprint_status
                ? `Blueprint ${appointment.own_blueprint_status === "failed" ? "failed. Retry it from their next appointment" : "is being built on your PC"}.`
                : "Saving builds their Patient Acquisition Blueprint on your PC. The link shows on their next appointment."}
            </div>
          )}
        </div>

        {askFit && (
          <div style={{ padding: 14, borderRadius: 10, background: "rgba(58,123,213,0.08)", border: "1px solid rgba(58,123,213,0.25)" }}>
            <div style={labelStyle}>WAS THIS PATIENT A GOOD FIT?</div>
            <div style={{ fontSize: 12, color: "#7f9cc4", marginBottom: 10 }}>
              Tells us who to find more of. Only DigiGrowth sees this.
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <Pill active={fit === "good"} color="#14c882" disabled={saving}
                onClick={() => setFit(fit === "good" ? null : "good")}>👍 GOOD FIT</Pill>
              <Pill active={fit === "not_fit"} color="#dc3c3c" disabled={saving}
                onClick={() => setFit(fit === "not_fit" ? null : "not_fit")}>👎 NOT A FIT</Pill>
            </div>
            {fit && (
              <input
                value={fitNote} onChange={(e) => setFitNote(e.target.value)}
                className="dg-input" style={{ width: "100%", boxSizing: "border-box", marginTop: 10, fontSize: 12 }}
                placeholder={fit === "good" ? "What made them a great fit? (optional)" : "Why not? e.g. wanted insurance billing (optional)"}
              />
            )}
          </div>
        )}

        {showRevenueFields && close === "closed" && (
          <div>
            <div style={labelStyle}>PRICING</div>
            <input
              type="number" min="0" step="0.01"
              value={pricing} onChange={(e) => setPricing(e.target.value)}
              className="dg-input" style={{ width: "100%", boxSizing: "border-box" }}
              placeholder="$0.00"
            />
          </div>
        )}

        {showRevenueFields && appointment.call_data_source === "fireflies" && (
          <div style={{ fontSize: 11.5, color: "#7f9cc4", marginBottom: -8 }}>
            Call length and recording filled in from Fireflies.
          </div>
        )}

        {showRevenueFields && (
          <div>
            <div style={labelStyle}>CALL LENGTH</div>
            <input
              type="text"
              value={callLength} onChange={(e) => setCallLength(e.target.value)}
              className="dg-input" style={{ width: "100%", boxSizing: "border-box" }}
              placeholder="e.g. 32 min"
            />
          </div>
        )}

        {showRevenueFields && (
          <div>
            <div style={labelStyle}>CALL RECORDING LINK</div>
            <input
              type="url"
              value={callRecordingUrl} onChange={(e) => setCallRecordingUrl(e.target.value)}
              className="dg-input" style={{ width: "100%", boxSizing: "border-box" }}
              placeholder="Paste the call recording URL…"
            />
          </div>
        )}

        {showRevenueFields && (
          <div>
            <div style={labelStyle}>QUESTION FORM LINK</div>
            <input
              type="url"
              value={questionFormUrl} onChange={(e) => setQuestionFormUrl(e.target.value)}
              className="dg-input" style={{ width: "100%", boxSizing: "border-box" }}
              placeholder="Paste this prospect's filled-out question form URL…"
            />
          </div>
        )}

        <div>
          <div style={labelStyle}>NOTES</div>
          <textarea
            value={notes} onChange={(e) => setNotes(e.target.value)}
            className="dg-input" rows={4}
            style={{ width: "100%", resize: "vertical", fontFamily: "inherit", boxSizing: "border-box" }}
            placeholder="What happened on the call…"
          />
        </div>

        {err && <div style={{ fontSize: 11, color: "#f06060", fontFamily: "'Share Tech Mono', monospace" }}>{err}</div>}

        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={onClose} className="btn btn-secondary" style={{ flex: 1 }}>Cancel</button>
          <button onClick={save} disabled={saving} className="btn btn-primary" style={{ flex: 2 }}>
            {saving ? "Saving…" : "Save Outcome"}
          </button>
        </div>
      </div>
    </div>
  );
}
