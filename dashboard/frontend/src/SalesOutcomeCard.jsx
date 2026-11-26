import React, { useState } from "react";
import { T, inputStyle } from "./ui.jsx";

// Dylan's own sales-call disposition (Appointments tab, discovery calls),
// 2026-11-25. Built around what he actually has to enter now:
//   1. Did they show?   (a no-show starts the No Show texts on save)
//   2. How did it end?  Closed / Two-call close / Not closed
//        closed   -> deal value (saving creates their portal + onboarding)
//        two_call -> their second call + the blueprint being built for it
//   3. Notes
// Call length, recording and summary come from Fireflies
// (backend sales_tracking.py), so they're shown, not asked; "Edit" opens
// the fields for a call Fireflies didn't catch. The client portal keeps
// its own AppointmentOutcomeCard.jsx.

function fmtWhen(ts, tz) {
  if (!ts) return "";
  try {
    return new Date(ts).toLocaleString("en-US", { timeZone: tz || undefined, weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
  } catch {
    return new Date(ts).toLocaleString("en-US");
  }
}

function Choice({ active, tone, onClick, disabled, title, sub }) {
  const color = { good: T.good, bad: T.bad, warn: T.warn }[tone] || T.accent;
  return (
    <button type="button" onClick={onClick} disabled={disabled} style={{
      flex: "1 1 120px", minWidth: 0, textAlign: "left", cursor: disabled ? "not-allowed" : "pointer",
      padding: "11px 13px", borderRadius: 11, fontFamily: T.font,
      background: active ? `${color}1c` : T.surface2,
      border: `1px solid ${active ? color : T.line}`,
      boxShadow: active ? `inset 0 0 0 1px ${color}55` : "none",
      transition: "background .15s, border-color .15s",
    }}>
      <div style={{ fontSize: 14, fontWeight: 600, color: active ? color : T.text }}>{title}</div>
      {sub && <div style={{ fontSize: 11.5, color: T.textMute, marginTop: 3, lineHeight: 1.35 }}>{sub}</div>}
    </button>
  );
}

function Step({ n, title, children, hint }) {
  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 10 }}>
        <span style={{ width: 22, height: 22, borderRadius: "50%", display: "grid", placeItems: "center", fontSize: 11.5, fontWeight: 700, color: T.accent, background: T.accentSoft, flexShrink: 0 }}>{n}</span>
        <span style={{ fontFamily: T.display, fontSize: 15, fontWeight: 600, color: T.text }}>{title}</span>
      </div>
      {children}
      {hint && <div style={{ fontSize: 12, color: T.textMute, marginTop: 8, lineHeight: 1.45 }}>{hint}</div>}
    </div>
  );
}

const label = { fontSize: 12.5, fontWeight: 500, color: T.textDim, marginBottom: 6 };
const box = { borderRadius: 11, padding: "12px 14px", background: T.surface2, border: `1px solid ${T.line}` };

export default function SalesOutcomeCard({ appointment, patchUrl, nextCall, onClose, onSaved }) {
  const a = appointment;
  const [show, setShow]   = useState(a.outcome_show || null);
  const [close, setClose] = useState(a.outcome_close || null);
  const [pricing, setPricing] = useState(a.pricing != null ? String(a.pricing) : "");
  const [notes, setNotes] = useState(a.outcome_notes || "");
  const [callLength, setCallLength] = useState(a.call_length || "");
  const [recording, setRecording]   = useState(a.call_recording_url || "");
  const [formUrl, setFormUrl]       = useState(a.question_form_url || "");
  const [editCall, setEditCall]     = useState(false);
  const [showSummary, setShowSummary] = useState(false);
  const [saving, setSaving] = useState(false);
  const [err, setErr]       = useState("");

  const isFuture = new Date(a.appointment_at).getTime() > Date.now();
  const fromFireflies = a.call_data_source === "fireflies";
  const hasCallData = !!(a.call_length || a.call_recording_url);
  const startedAgo = Date.now() - new Date(a.appointment_at).getTime();
  const firefliesPending = !hasCallData && startedAgo > 0 && startedAgo < 6 * 3600 * 1000;
  const showed = show === "show";

  const save = async () => {
    setSaving(true);
    setErr("");
    // A no-show can't have a conclusion; a non-close carries no deal value.
    const outcomeClose = showed ? close : null;
    const body = {
      outcome_show: show,
      outcome_close: outcomeClose,
      outcome_notes: notes.trim() || null,
      pricing: outcomeClose === "closed" && pricing.trim() !== "" ? Number(pricing) : null,
      call_length: callLength.trim() || null,
      call_recording_url: recording.trim() || null,
      question_form_url: formUrl.trim() || null,
    };
    try {
      const r = await fetch(patchUrl, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const resp = await r.json().catch(() => ({}));
      if (!r.ok) { setErr(resp.detail || "Couldn't save."); setSaving(false); return; }
      onSaved?.({
        ...a, ...body,
        ...(resp.blueprint ? { own_blueprint_status: resp.blueprint.status, own_blueprint_url: resp.blueprint.url || null } : {}),
      });
    } catch (e) {
      setErr("Couldn't save: " + e.message);
      setSaving(false);
    }
  };

  const bpStatus = a.own_blueprint_status;
  const saveLabel = !show ? "Save notes"
    : show === "no_show" ? "Save no-show"
    : close === "closed" ? "Save close"
    : close === "two_call" ? "Save two-call close"
    : "Save";

  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 60, display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }}>
      <div style={{ position: "absolute", inset: 0, background: "rgba(5,9,22,0.74)" }} onClick={onClose} />
      <div className="ui-card" style={{
        position: "relative", width: 520, maxWidth: "100%", maxHeight: "90vh", overflowY: "auto",
        padding: 22, display: "flex", flexDirection: "column", gap: 20, fontFamily: T.font,
      }}>
        {/* Header */}
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontFamily: T.display, fontSize: 19, fontWeight: 700, color: T.text, letterSpacing: "-0.01em" }}>
              {a.prospect_name || a.owner || "Sales call"}
            </div>
            <div style={{ fontSize: 13, color: T.textMute, marginTop: 3 }}>
              {[a.business, fmtWhen(a.appointment_at, a.prospect_timezone)].filter(Boolean).join(" · ")}
            </div>
          </div>
          <button onClick={onClose} aria-label="Close" style={{ background: "none", border: "none", color: T.textMute, fontSize: 18, cursor: "pointer", padding: "0 4px", lineHeight: 1 }}>×</button>
        </div>

        {a.blueprint_status === "done" && a.blueprint_url && (
          <a href={a.blueprint_url} target="_blank" rel="noreferrer" style={{ ...box, display: "flex", justifyContent: "space-between", alignItems: "center", textDecoration: "none", borderColor: "rgba(242,173,61,0.4)", background: "rgba(242,173,61,0.07)" }}>
            <span style={{ fontSize: 13.5, color: T.text }}><b>Their blueprint</b> <span style={{ color: T.textMute }}>· for this call</span></span>
            <span style={{ fontSize: 13, color: T.warn, fontWeight: 600 }}>Open ↗</span>
          </a>
        )}

        {isFuture && (
          <div style={{ ...box, fontSize: 13, color: T.textDim }}>This call hasn't happened yet. You can still add notes.</div>
        )}

        {/* 1. Show */}
        <Step n={1} title="Did they show?"
          hint={show === "no_show" ? "Saving starts the No Show texts to them." : null}>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <Choice active={show === "show"} tone="good" disabled={saving} title="Showed" onClick={() => setShow(show === "show" ? null : "show")} />
            <Choice active={show === "no_show"} tone="bad" disabled={saving} title="No-show" onClick={() => setShow(show === "no_show" ? null : "no_show")} />
          </div>
        </Step>

        {/* 2. Outcome */}
        {showed && (
          <Step n={2} title="How did it end?">
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <Choice active={close === "closed"} tone="good" disabled={saving} title="Closed" sub="They signed"
                onClick={() => setClose(close === "closed" ? null : "closed")} />
              <Choice active={close === "two_call"} tone="warn" disabled={saving} title="Two-call close" sub="Second call booked"
                onClick={() => setClose(close === "two_call" ? null : "two_call")} />
              <Choice active={close === "not_closed"} tone="bad" disabled={saving} title="Not closed" sub="No next call"
                onClick={() => setClose(close === "not_closed" ? null : "not_closed")} />
            </div>

            {close === "closed" && (
              <div style={{ marginTop: 14 }}>
                <div style={label}>Deal value</div>
                <div style={{ position: "relative" }}>
                  <span style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: T.textMute, fontSize: 14 }}>$</span>
                  <input type="number" min="0" step="0.01" value={pricing} onChange={e => setPricing(e.target.value)}
                    placeholder="0 for a pilot" style={{ ...inputStyle, paddingLeft: 24 }} />
                </div>
                {a.outcome_close !== "closed" && (
                  <div style={{ fontSize: 12, color: T.textMute, marginTop: 8, lineHeight: 1.45 }}>
                    Saving creates their client portal and starts onboarding.
                  </div>
                )}
              </div>
            )}

            {close === "two_call" && (
              <div style={{ ...box, marginTop: 14, display: "grid", gap: 8 }}>
                <div style={{ fontSize: 13.5, color: T.text }}>
                  <span style={{ color: T.textMute }}>Second call: </span>
                  {nextCall ? fmtWhen(nextCall.appointment_at, nextCall.prospect_timezone)
                    : <span style={{ color: T.warn }}>not booked yet. Book it from their contact card.</span>}
                </div>
                <div style={{ fontSize: 13, color: T.textDim, lineHeight: 1.45 }}>
                  {bpStatus === "done" && a.own_blueprint_url
                    ? <>Blueprint ready: <a href={a.own_blueprint_url} target="_blank" rel="noreferrer" style={{ color: T.warn, fontWeight: 600 }}>open it ↗</a></>
                    : bpStatus === "failed" ? <span style={{ color: T.bad }}>The blueprint build failed. Retry it from their next appointment.</span>
                    : bpStatus ? "Their blueprint is being built on your PC. It'll show on the second call."
                    : "Saving builds their Patient Acquisition Blueprint on your PC. It'll show on the second call."}
                </div>
              </div>
            )}
          </Step>
        )}

        {/* Call details: from Fireflies, editable when it missed one */}
        {!isFuture && show !== "no_show" && (
          <div style={box}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10 }}>
              <span style={{ fontSize: 13.5, fontWeight: 600, color: T.text }}>
                Call details {fromFireflies && <span style={{ fontWeight: 400, color: T.textMute }}>· from Fireflies</span>}
              </span>
              <button type="button" onClick={() => setEditCall(v => !v)}
                style={{ background: "none", border: "none", padding: 0, color: T.accent, fontSize: 12.5, fontWeight: 600, cursor: "pointer" }}>
                {editCall ? "Done" : hasCallData ? "Edit" : "Add by hand"}
              </button>
            </div>

            {!editCall && (
              hasCallData ? (
                <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginTop: 8, fontSize: 13, color: T.textDim }}>
                  {callLength && <span>{/^\d+$/.test(callLength.trim()) ? `${callLength} min` : callLength}</span>}
                  {recording && <a href={recording} target="_blank" rel="noreferrer" style={{ color: T.accent }}>Recording ↗</a>}
                  {formUrl && <a href={formUrl} target="_blank" rel="noreferrer" style={{ color: T.accent }}>Question form ↗</a>}
                  {a.call_summary && (
                    <button type="button" onClick={() => setShowSummary(v => !v)}
                      style={{ background: "none", border: "none", padding: 0, color: T.accent, fontSize: 13, cursor: "pointer" }}>
                      {showSummary ? "Hide summary" : "Summary"}
                    </button>
                  )}
                </div>
              ) : (
                <div style={{ fontSize: 12.5, color: T.textMute, marginTop: 6, lineHeight: 1.45 }}>
                  {firefliesPending ? "Fireflies usually adds the recording and length within 15 minutes of the call."
                    : "Fireflies didn't catch this call."}
                </div>
              )
            )}
            {!editCall && showSummary && a.call_summary && (
              <div style={{ fontSize: 12.5, color: T.textDim, marginTop: 10, lineHeight: 1.55, whiteSpace: "pre-wrap" }}>{a.call_summary}</div>
            )}

            {editCall && (
              <div style={{ display: "grid", gap: 10, marginTop: 10 }}>
                <div>
                  <div style={label}>Call length</div>
                  <input value={callLength} onChange={e => setCallLength(e.target.value)} placeholder="e.g. 32 min" style={inputStyle} />
                </div>
                <div>
                  <div style={label}>Recording link</div>
                  <input type="url" value={recording} onChange={e => setRecording(e.target.value)} placeholder="https://app.fireflies.ai/view/…" style={inputStyle} />
                </div>
                <div>
                  <div style={label}>Question form link</div>
                  <input type="url" value={formUrl} onChange={e => setFormUrl(e.target.value)} placeholder="Their filled-out question form" style={inputStyle} />
                </div>
              </div>
            )}
          </div>
        )}

        {/* Notes */}
        <div>
          <div style={label}>Notes</div>
          <textarea value={notes} onChange={e => setNotes(e.target.value)} rows={3}
            placeholder={close === "not_closed" ? "Why they didn't move forward…" : close === "two_call" ? "What to cover on the second call…" : "What happened on the call…"}
            style={{ ...inputStyle, resize: "vertical", fontFamily: T.font, lineHeight: 1.5 }} />
        </div>

        {err && <div style={{ fontSize: 12.5, color: T.bad }}>{err}</div>}

        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={onClose} className="btn btn-secondary" style={{ flex: 1 }}>Cancel</button>
          <button onClick={save} disabled={saving} className="btn btn-primary" style={{ flex: 2 }}>
            {saving ? "Saving…" : saveLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
