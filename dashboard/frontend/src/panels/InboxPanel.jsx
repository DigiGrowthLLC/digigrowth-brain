import React, { useState, useEffect, useRef, useCallback } from "react";
import { API } from "../api.js";
import ContactCard from "../ContactCard.jsx";
import BookingModal from "../BookingModal.jsx";

function htmlToText(html) {
  if (!html) return "";
  if (!/<[a-z][\s\S]*>/i.test(html)) return html; // plain SMS text, nothing to strip
  const withBreaks = html.replace(/<br\s*\/?>/gi, "\n").replace(/<\/(p|div)>/gi, "\n");
  const el = document.createElement("div");
  el.innerHTML = withBreaks;
  return (el.textContent || el.innerText || "")
    .split("\n")
    .map(line => line.trim())
    .filter(Boolean)
    .join("\n");
}

function fmtMsgTime(ts) {
  if (!ts) return "";
  const d = new Date(ts), diff = Date.now() - d;
  if (diff < 86400000) return d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" }) + ", " +
         d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
}

function convoBadge(c) {
  // Once this contact's business has actually become a client (client_id
  // set on the anchor row -- see is_client_anchor in db.py), that outranks
  // every pipeline-stage badge below: "interested"/"booked" would be stale
  // now that they've converted.
  if (c.client_id) {
    return { label: "CLIENT", cls: "badge-green" };
  }
  if (c.disposition === "not_interested") {
    return { label: "NOT INTERESTED", cls: "badge-red" };
  }
  if (c.status === "closed" || c.disposition === "booked") {
    return { label: "BOOKED", cls: "badge-green" };
  }
  if (c.stage_interested) {
    return { label: "INTERESTED", cls: "badge-amber" };
  }
  return { label: "ACTIVE", cls: "badge-blue" };
}

const CONTACT_STATUSES = [
  { value: "new",                label: "NEW" },
  { value: "dialer-lead",        label: "DIALER" },
  { value: "sms-handoff",        label: "SMS HANDOFF" },
  { value: "email-handoff",      label: "EMAIL HANDOFF" },
  { value: "appointment-booked", label: "BOOKED" },
  { value: "not-interested",     label: "NOT INT." },
  { value: "send-info",          label: "SEND INFO" },
  { value: "voicemail",          label: "VOICEMAIL" },
  { value: "gatekeeper-blocked", label: "GATEKEEPER" },
  { value: "gatekeeper-deferral", label: "GK DEFERRAL" },
  { value: "manual-followup",    label: "MANUAL F/U" },
];

const STAGE_OPTIONS = [
  { value: "initial_outreach", label: "INITIAL OUTREACH" },
  { value: "replied",          label: "REPLIED" },
  { value: "dm_reached",       label: "DM REACHED" },
  { value: "primed",           label: "PRIMED" },
  { value: "engaged",          label: "ENGAGED" },
  { value: "interested",       label: "INTERESTED" },
  { value: "not_interested",   label: "NOT INTERESTED" },
];

const CHANNEL_CHIP = {
  sms:   { label: "SMS",  bg: "rgba(20,200,130,0.12)", color: "#14c882" },
  email: { label: "MAIL", bg: "rgba(160,110,240,0.12)", color: "#a06ef0" },
};

// ── Compose Modal ─────────────────────────────────────────────────────────────

function ComposeModal({ onClose, onSent }) {
  const [channel, setChannel] = useState("sms");
  const [to, setTo]           = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody]       = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError]     = useState(null);

  const handleSend = async () => {
    const b = body.trim();
    if (channel === "sms") {
      const p = to.trim().replace(/\s+/g, "");
      if (!p || !b) return;
      setSending(true);
      setError(null);
      try {
        const r = await fetch(API("/sms/send"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ phone: p, body: b }),
        });
        const data = await r.json().catch(() => ({}));
        if (!r.ok || !data.ok) { setError(data.error || "Failed to send"); return; }
        onSent({ contactId: data.contact_id });
      } catch (e) {
        setError(e.message);
      } finally {
        setSending(false);
      }
    } else {
      const addr = to.trim();
      if (!addr || !b) return;
      setSending(true);
      setError(null);
      try {
        const r = await fetch(API("/email/send"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ thread_id: "", to: addr, subject: subject.trim(), body: b }),
        });
        const data = await r.json().catch(() => ({}));
        if (!r.ok || !data.ok) { setError(data.error || "Failed to send"); return; }
        onSent({ contactId: data.contact_id });
      } catch (e) {
        setError(e.message);
      } finally {
        setSending(false);
      }
    }
  };

  return (
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
        className="glass-card"
        style={{ width: "100%", maxWidth: 420, padding: 0, overflow: "hidden" }}
        onClick={e => e.stopPropagation()}
      >
        <div style={{ padding: "18px 22px 14px", borderBottom: "0.5px solid #1a2540", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 15, fontWeight: 700, color: "#f0f4ff" }}>
            New Message
          </div>
          <button onClick={onClose} style={{ background: "transparent", border: "none", color: "#3a5a80", cursor: "pointer", fontSize: 18, lineHeight: 1, padding: "2px 6px" }}>×</button>
        </div>

        <div style={{ padding: "18px 22px" }}>
          <div style={{ marginBottom: 14, display: "flex", gap: 8 }}>
            {["sms", "email"].map(c => (
              <button key={c} onClick={() => setChannel(c)}
                style={{
                  flex: 1, padding: "6px 0", borderRadius: 6,
                  border: `1px solid ${channel === c ? "rgba(58,123,213,0.6)" : "rgba(58,123,213,0.2)"}`,
                  background: channel === c ? "rgba(58,123,213,0.15)" : "transparent",
                  color: channel === c ? "#3a7bd5" : "#5a6f8f",
                  fontFamily: "'Share Tech Mono', monospace", fontSize: 10, letterSpacing: "0.08em",
                  cursor: "pointer",
                }}>
                {c === "sms" ? "SMS" : "EMAIL"}
              </button>
            ))}
          </div>
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", letterSpacing: "0.12em", marginBottom: 5 }}>
              {channel === "sms" ? "TO (PHONE NUMBER)" : "TO (EMAIL ADDRESS)"}
            </div>
            <input
              className="dg-input"
              type={channel === "sms" ? "tel" : "email"}
              placeholder={channel === "sms" ? "+1 555 000 0000" : "prospect@example.com"}
              value={to}
              onChange={e => setTo(e.target.value)}
              style={{ width: "100%", fontSize: 13, boxSizing: "border-box" }}
              autoFocus
            />
          </div>
          {channel === "email" && (
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", letterSpacing: "0.12em", marginBottom: 5 }}>SUBJECT</div>
              <input
                className="dg-input"
                type="text"
                placeholder="Subject"
                value={subject}
                onChange={e => setSubject(e.target.value)}
                style={{ width: "100%", fontSize: 13, boxSizing: "border-box" }}
              />
            </div>
          )}
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
            disabled={sending || !to.trim() || !body.trim()}
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

const AI_ACTION_META = {
  reply:                 { label: "REPLY",            color: "#3a7bd5" },
  book:                  { label: "BOOK CALL",        color: "#14c882" },
  send_template:         { label: "SEQUENCE",         color: "#3a7bd5" },
  send_pitch:            { label: "SEND PITCH",       color: "#3a7bd5" },
  send_gatekeeper_pitch: { label: "GATEKEEPER PITCH", color: "#3a7bd5" },
  capture_email:         { label: "CAPTURE EMAIL",    color: "#e0a030" },
  follow_up:             { label: "FOLLOW UP LATER",  color: "#e0a030" },
  close_not_interested:  { label: "CLOSE · NOT INTERESTED", color: "#dc3c3c" },
  opt_out:               { label: "OPT OUT",          color: "#dc3c3c" },
  handoff:               { label: "HANDLE PERSONALLY", color: "#e0a030" },
  none:                  { label: "NO REPLY NEEDED",  color: "#5a6f8f" },
};

// AI setter mode switch (see sms_setter_ai.py). The drafting itself runs on
// Dylan's PC (apptset-agent/sms_setter_worker.py), so the dot shows whether
// that worker has checked in recently — offline means nothing drafts or
// sends, whatever the mode says.
function SetterModeBar({ followUpCount, onOpenFollowUps, lessonCount, onOpenLessons }) {
  const [state, setState] = useState(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await fetch(API("/sms-setter/mode"));
      if (r.ok) setState(await r.json());
    } catch {}
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, [load]);

  const setMode = async (mode) => {
    if (!state || mode === state.mode || saving) return;
    if (mode === "auto" && !window.confirm(
      "Turn on AUTO mode? The AI setter will text prospects and book Google Meet calls on its own " +
      "(8am-8pm their time, max 4 texts per thread per day). Handoffs still wait for you."
    )) return;
    setSaving(true);
    try {
      const r = await fetch(API("/sms-setter/mode"), {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode }),
      });
      if (r.ok) setState(await r.json());
    } catch {}
    setSaving(false);
  };

  if (!state) return null;
  const mono = { fontFamily: "'Share Tech Mono', monospace", fontSize: 9, letterSpacing: "0.06em" };
  const modeColor = { off: "#5a6f8f", draft: "#3a7bd5", auto: "#14c882" };
  // Two quiet rows so nothing wraps in the narrow list column: status +
  // mode switch, then the follow-ups (only when there are any) and lessons links.
  const online = state.worker_online;
  return (
    <div style={{ padding: "8px 16px", borderBottom: "0.5px solid #1a2540", display: "flex", flexDirection: "column", gap: 6 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span
          title={`${online ? "PC online" : "PC offline, nothing drafts or sends"} · ${state.worker_last_seen ? `last check-in ${new Date(state.worker_last_seen).toLocaleString()}` : "never checked in"}`}
          style={{ ...mono, color: "#8fa3c4", display: "flex", alignItems: "center", gap: 6, whiteSpace: "nowrap" }}
        >
          <span style={{ width: 6, height: 6, borderRadius: 3, flexShrink: 0, background: online ? "#14c882" : "#dc3c3c" }} />
          AI SETTER{online ? "" : " · OFFLINE"}
        </span>
        <div style={{ flex: 1 }} />
        <div style={{ display: "flex", border: "1px solid rgba(58,123,213,0.2)", borderRadius: 6, overflow: "hidden", flexShrink: 0 }}>
          {["off", "draft", "auto"].map(m => (
            <button key={m} onClick={() => setMode(m)} disabled={saving}
              style={{
                ...mono, padding: "3px 7px", cursor: "pointer", border: "none", whiteSpace: "nowrap",
                background: state.mode === m ? `${modeColor[m]}26` : "transparent",
                color: state.mode === m ? modeColor[m] : "#5a6f8f",
              }}>
              {m.toUpperCase()}
            </button>
          ))}
        </div>
      </div>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        {followUpCount > 0 && (
          <button onClick={onOpenFollowUps} title="Check-ins the AI setter will send"
            style={{
              ...mono, padding: 0, border: "none", background: "transparent", cursor: "pointer",
              color: "#e0a030", textAlign: "left", whiteSpace: "nowrap",
            }}>
            {followUpCount} FOLLOW-UP{followUpCount === 1 ? "" : "S"} →
          </button>
        )}
        <button onClick={onOpenLessons} title="What the AI setter learned from your own replies"
          style={{
            ...mono, padding: 0, border: "none", background: "transparent", cursor: "pointer",
            color: "#14c882", textAlign: "left", whiteSpace: "nowrap",
          }}>
          {lessonCount} LESSON{lessonCount === 1 ? "" : "S"} LEARNED →
        </button>
      </div>
    </div>
  );
}

// ── Scheduled check-ins ("busy, text me tomorrow") ───────────────────────────
// The AI setter's follow_up action books a check-in on the thread
// (sms_conversations.ai_followup_due_at); once due, the worker writes it and
// auto mode sends it. GET /sms-setter/follow-ups lists them all.

const phoneDigits = (p) => (p || "").replace(/\D/g, "").slice(-10);

function fmtInZone(iso, timeZone) {
  try {
    return new Date(iso).toLocaleString("en-US", {
      timeZone, weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short",
    });
  } catch { return new Date(iso).toLocaleString(); }
}

function fmtRelative(iso) {
  const ms = new Date(iso) - Date.now();
  if (ms <= 0) return "due now";
  const h = ms / 3600000;
  if (h < 1) return `in ${Math.max(1, Math.round(ms / 60000))} min`;
  if (h < 24) return `in ${Math.round(h)}h`;
  return `in ${Math.round(h / 24)} day${Math.round(h / 24) === 1 ? "" : "s"}`;
}

// "YYYY-MM-DD" / "HH:MM" of an instant in a given zone, to prefill the editor.
function partsInZone(iso, timeZone) {
  const p = Object.fromEntries(new Intl.DateTimeFormat("en-CA", {
    timeZone, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  }).formatToParts(new Date(iso)).map(x => [x.type, x.value]));
  return { date: `${p.year}-${p.month}-${p.day}`, time: `${p.hour}:${p.minute}` };
}

function FollowUpRow({ f, workerOnline, onOpen, onChanged }) {
  const [editing, setEditing] = useState(false);
  const [date, setDate] = useState("");
  const [time, setTime] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const mono = { fontFamily: "'Share Tech Mono', monospace", fontSize: 9, letterSpacing: "0.06em" };
  const due = new Date(f.due_at) <= new Date();
  const btn = (color) => ({
    ...mono, padding: "3px 8px", borderRadius: 6, cursor: "pointer",
    border: `1px solid ${color}55`, background: `${color}14`, color,
  });

  const startEdit = () => {
    const p = partsInZone(f.due_at, f.timezone);
    setDate(p.date); setTime(p.time); setError(null); setEditing(true);
  };
  const save = async () => {
    setBusy(true); setError(null);
    try {
      const r = await fetch(API("/sms-setter/follow-ups/reschedule"), {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone: f.phone, date, time }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) { setError(data.detail || "Couldn't reschedule"); setBusy(false); return; }
      setEditing(false);
      onChanged();
    } catch (e) { setError(e.message); }
    setBusy(false);
  };
  const cancel = async () => {
    if (!window.confirm(`Cancel the check-in with ${f.owner || f.phone}? The agent won't text them unless they reply.`)) return;
    setBusy(true);
    try { await fetch(API("/sms-setter/follow-ups/cancel"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ phone: f.phone }) }); } catch {}
    setBusy(false);
    onChanged();
  };

  return (
    <div className="glass-card-sm" style={{ padding: "12px 14px", marginBottom: 10, border: `1px solid ${due ? "#e0a03055" : "rgba(58,123,213,0.2)"}` }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 8, flexWrap: "wrap" }}>
        <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 13, fontWeight: 600, color: "#f0f4ff" }}>
          {f.owner || f.phone}
        </div>
        {f.business && <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 11, color: "#5a6f8f" }}>{f.business}</div>}
        {f.set_by === "dylan" && <span style={{ ...mono, color: "#3a7bd5" }}>SET BY YOU</span>}
        <div style={{ flex: 1 }} />
        <span style={{ ...mono, color: due ? "#e0a030" : "#14c882" }}>{fmtRelative(f.due_at).toUpperCase()}</span>
      </div>

      <div style={{ marginTop: 6, fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, color: "#c8d4ec" }}>
        Agent texts them <b>{fmtInZone(f.due_at, f.timezone)}</b>
        <span style={{ color: "#5a6f8f" }}> · their time</span>
      </div>
      <div style={{ ...mono, color: "#5a6f8f", marginTop: 2 }}>
        YOUR TIME: {new Date(f.due_at).toLocaleString([], { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}
      </div>
      {due && !workerOnline && (
        <div style={{ ...mono, color: "#dc3c3c", marginTop: 4 }}>DUE, BUT YOUR PC IS OFFLINE · IT SENDS ONCE THE WORKER IS BACK</div>
      )}

      {f.last_inbound && (
        <div style={{ marginTop: 8, fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, color: "#8fa3c4" }}>
          <span style={{ ...mono, color: "#3a7bd5" }}>THEY SAID </span>"{f.last_inbound.trim().slice(0, 200)}"
        </div>
      )}
      {f.note && (
        <div style={{ marginTop: 4, fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, color: "#8fa3c4" }}>
          <span style={{ ...mono, color: "#3a7bd5" }}>{f.set_by === "dylan" ? "YOUR NOTE " : "WHY "}</span>{f.note}
        </div>
      )}

      {editing ? (
        <div style={{ marginTop: 10, display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
          <input className="dg-input" type="date" value={date} onChange={e => setDate(e.target.value)} style={{ width: 150 }} />
          <input className="dg-input" type="time" value={time} onChange={e => setTime(e.target.value)} style={{ width: 120 }} />
          <span style={{ ...mono, color: "#5a6f8f" }}>THEIR TIME</span>
          <button onClick={save} disabled={busy || !date} style={btn("#14c882")}>SAVE</button>
          <button onClick={() => setEditing(false)} disabled={busy} style={btn("#5a6f8f")}>BACK</button>
        </div>
      ) : (
        <div style={{ marginTop: 10, display: "flex", gap: 6 }}>
          <button onClick={() => onOpen(f)} style={btn("#3a7bd5")}>OPEN THREAD</button>
          <button onClick={startEdit} disabled={busy} style={btn("#e0a030")}>CHANGE TIME</button>
          <button onClick={cancel} disabled={busy} style={btn("#dc3c3c")}>CANCEL</button>
        </div>
      )}
      {error && <div style={{ ...mono, color: "#dc3c3c", marginTop: 6 }}>{error}</div>}
    </div>
  );
}

function FollowUpsModal({ data, onClose, onOpen, onChanged }) {
  const list = data?.follow_ups || [];
  return (
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
        className="glass-card"
        style={{ width: "100%", maxWidth: 560, maxHeight: "85vh", padding: 0, overflow: "hidden", display: "flex", flexDirection: "column" }}
        onClick={e => e.stopPropagation()}
      >
        <div style={{ padding: "18px 22px 14px", borderBottom: "0.5px solid #1a2540", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 15, fontWeight: 700, color: "#f0f4ff" }}>
              Scheduled Follow-Ups
            </div>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#5a6f8f", letterSpacing: "0.06em", marginTop: 3 }}>
              CHECK-INS THE AI SETTER WILL SEND · BOOKED BY THE AGENT OR BY YOU · SOONEST FIRST
            </div>
          </div>
          <button onClick={onClose} style={{ background: "transparent", border: "none", color: "#3a5a80", cursor: "pointer", fontSize: 18, lineHeight: 1, padding: "2px 6px" }}>×</button>
        </div>
        <div style={{ padding: "16px 22px", overflowY: "auto" }}>
          {list.length === 0 ? (
            <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 13, color: "#5a6f8f", textAlign: "center", padding: "24px 0" }}>
              No follow-ups scheduled right now.
            </div>
          ) : list.map(f => (
            <FollowUpRow key={f.phone} f={f} workerOnline={data.worker_online} onOpen={onOpen} onChanged={onChanged} />
          ))}
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80", letterSpacing: "0.06em", marginTop: 6, lineHeight: 1.6 }}>
            IF THEY TEXT BEFORE THEN, THE CHECK-IN IS DROPPED AND THE AGENT ANSWERS THEIR TEXT INSTEAD.
            AUTO MODE SENDS IT 8AM-8PM THEIR TIME; IN DRAFT MODE IT WAITS IN THE INBOX FOR YOU.
          </div>
        </div>
      </div>
    </div>
  );
}

// Dylan books a check-in on a thread himself (POST /sms-setter/follow-ups/
// schedule). Same path as the agent's own check-ins: when it's due the
// worker writes the text, following his note, and auto mode sends it.
function ScheduleFollowUpForm({ phone, onDone, onCancel }) {
  const tomorrow = new Date(Date.now() + 86400000);
  const pad = (n) => String(n).padStart(2, "0");
  const [date, setDate] = useState(`${tomorrow.getFullYear()}-${pad(tomorrow.getMonth() + 1)}-${pad(tomorrow.getDate())}`);
  const [time, setTime] = useState("10:00");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const mono = { fontFamily: "'Share Tech Mono', monospace", fontSize: 9, letterSpacing: "0.06em" };
  const btn = (color) => ({
    ...mono, padding: "3px 8px", borderRadius: 6, cursor: "pointer",
    border: `1px solid ${color}55`, background: `${color}14`, color,
  });

  const save = async () => {
    setBusy(true); setError(null);
    try {
      const r = await fetch(API("/sms-setter/follow-ups/schedule"), {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone, date, time, note }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) { setError(data.detail || "Couldn't schedule"); setBusy(false); return; }
      onDone();
    } catch (e) { setError(e.message); }
    setBusy(false);
  };

  return (
    <div style={{ marginBottom: 10, padding: "10px 12px", borderRadius: 8, border: "1px solid rgba(224,160,48,0.35)", background: "rgba(224,160,48,0.05)" }}>
      <div style={{ ...mono, color: "#e0a030", marginBottom: 8 }}>AI FOLLOW-UP · THE AGENT TEXTS THEM THEN, UNLESS THEY TEXT FIRST</div>
      <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap", marginBottom: 6 }}>
        <input className="dg-input" type="date" value={date} onChange={e => setDate(e.target.value)} style={{ width: 150 }} />
        <input className="dg-input" type="time" value={time} onChange={e => setTime(e.target.value)} style={{ width: 120 }} />
        <span style={{ ...mono, color: "#5a6f8f" }}>THEIR TIME</span>
      </div>
      <textarea className="dg-input" value={note} onChange={e => setNote(e.target.value)} rows={2}
        placeholder="Optional: what should the agent say? e.g. ask if things calmed down after their busy season and if they have 20 min next week"
        style={{ width: "100%", resize: "vertical", fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, boxSizing: "border-box" }} />
      <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
        <button onClick={save} disabled={busy || !date} style={btn("#14c882")}>{busy ? "SAVING..." : "SCHEDULE"}</button>
        <button onClick={onCancel} disabled={busy} style={btn("#5a6f8f")}>CANCEL</button>
      </div>
      {error && <div style={{ ...mono, color: "#dc3c3c", marginTop: 6 }}>{error}</div>}
    </div>
  );
}

// ── Lessons: what the AI setter learned from Dylan's own replies ─────────────
// When Dylan answers a thread himself instead of the setter's draft (a
// handoff, a draft he skipped or edited), the worker distills his reply into
// a lesson that goes into every later prompt (sms_setter_ai.py, "Learning
// from Dylan"). GET /sms-setter/lessons lists them; he can edit or turn off any.

const LESSON_STATUS = {
  collecting: { label: "LEARNING...",       color: "#3a7bd5" },
  active:     { label: "IN USE",            color: "#14c882" },
  skipped:    { label: "NOTHING REUSABLE",  color: "#5a6f8f" },
  disabled:   { label: "OFF",               color: "#dc3c3c" },
};
const LESSON_TRIGGER = {
  handoff: "AI handed it to you", override: "you skipped the AI's draft",
  edited: "you edited the AI's draft", manual: "you clicked TEACH",
};

function LessonRow({ l, workerOnline, onOpen, onChanged }) {
  const [editing, setEditing] = useState(false);
  const [situation, setSituation] = useState(l.situation || "");
  const [lesson, setLesson] = useState(l.lesson || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const mono = { fontFamily: "'Share Tech Mono', monospace", fontSize: 9, letterSpacing: "0.06em" };
  const text = { fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, color: "#8fa3c4" };
  const btn = (color) => ({
    ...mono, padding: "3px 8px", borderRadius: 6, cursor: "pointer",
    border: `1px solid ${color}55`, background: `${color}14`, color,
  });
  const st = LESSON_STATUS[l.status] || LESSON_STATUS.skipped;

  const patch = async (body) => {
    setBusy(true); setError(null);
    try {
      const r = await fetch(API(`/sms-setter/lessons/${l.id}`), {
        method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) { setError(data.detail || "Couldn't save"); setBusy(false); return; }
      setEditing(false);
      onChanged();
    } catch (e) { setError(e.message); }
    setBusy(false);
  };
  const remove = async () => {
    if (!window.confirm("Delete this lesson? The AI setter stops using it.")) return;
    setBusy(true);
    try { await fetch(API(`/sms-setter/lessons/${l.id}`), { method: "DELETE" }); } catch {}
    setBusy(false);
    onChanged();
  };

  return (
    <div className="glass-card-sm" style={{ padding: "12px 14px", marginBottom: 10, border: `1px solid ${st.color}40`, opacity: l.status === "active" || l.status === "collecting" ? 1 : 0.75 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 8, flexWrap: "wrap" }}>
        <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 13, fontWeight: 600, color: "#f0f4ff" }}>
          {l.situation || (l.status === "collecting" ? "Learning from your reply" : "No lesson")}
        </div>
        <div style={{ flex: 1 }} />
        <span style={{ ...mono, color: st.color }}>{st.label}</span>
      </div>
      <div style={{ ...mono, color: "#5a6f8f", marginTop: 3 }}>
        {(l.owner || l.phone)}{l.business ? ` · ${l.business}` : ""} · {LESSON_TRIGGER[l.trigger] || l.trigger} · {new Date(l.created_at).toLocaleDateString([], { month: "short", day: "numeric" })}
      </div>
      {l.status === "collecting" && (
        <div style={{ ...mono, color: workerOnline ? "#3a7bd5" : "#dc3c3c", marginTop: 6 }}>
          {workerOnline ? "YOUR PC WILL ANALYZE THIS A FEW MINUTES AFTER YOUR LAST TEXT" : "WAITING FOR YOUR PC TO COME ONLINE"}
        </div>
      )}

      {editing ? (
        <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 6 }}>
          <input className="dg-input" value={situation} onChange={e => setSituation(e.target.value)} placeholder="Situation, e.g. Prospect worried it's a scam" />
          <textarea className="dg-input" value={lesson} onChange={e => setLesson(e.target.value)} rows={3}
            placeholder="When this happens, the AI should..." style={{ resize: "vertical", fontFamily: "'Space Grotesk', sans-serif", fontSize: 12 }} />
          <div style={{ display: "flex", gap: 6 }}>
            <button onClick={() => patch({ situation, lesson, status: "active" })} disabled={busy || !situation.trim() || !lesson.trim()} style={btn("#14c882")}>SAVE + USE</button>
            <button onClick={() => setEditing(false)} disabled={busy} style={btn("#5a6f8f")}>BACK</button>
          </div>
        </div>
      ) : l.lesson && (
        <div style={{ marginTop: 8, fontFamily: "'Space Grotesk', sans-serif", fontSize: 13, color: "#c8d4ec", lineHeight: 1.45 }}>{l.lesson}</div>
      )}

      <div style={{ marginTop: 8, ...text }}>
        <span style={{ ...mono, color: "#3a7bd5" }}>YOU SENT </span>"{(l.dylan_reply || "").trim().slice(0, 320)}{(l.dylan_reply || "").length > 320 ? "..." : ""}"
      </div>
      {l.ai_action && (
        <div style={{ marginTop: 4, ...text }}>
          <span style={{ ...mono, color: "#5a6f8f" }}>AI WANTED </span>
          {l.ai_action === "handoff" ? `to hand it to you: ${l.ai_rationale || ""}` : `"${(l.ai_reply || "").trim().slice(0, 200)}"`}
        </div>
      )}
      {l.analysis_note && (
        <div style={{ marginTop: 4, ...text }}><span style={{ ...mono, color: "#5a6f8f" }}>WHY </span>{l.analysis_note}</div>
      )}

      {!editing && (
        <div style={{ marginTop: 10, display: "flex", gap: 6, flexWrap: "wrap" }}>
          <button onClick={() => onOpen(l)} style={btn("#3a7bd5")}>OPEN THREAD</button>
          {l.status !== "collecting" && <button onClick={() => { setSituation(l.situation || ""); setLesson(l.lesson || ""); setEditing(true); }} disabled={busy} style={btn("#e0a030")}>{l.lesson ? "EDIT" : "WRITE ONE"}</button>}
          {l.status === "active" && <button onClick={() => patch({ status: "disabled" })} disabled={busy} style={btn("#dc3c3c")}>TURN OFF</button>}
          {(l.status === "disabled" || l.status === "skipped") && l.lesson && <button onClick={() => patch({ status: "active" })} disabled={busy} style={btn("#14c882")}>USE IT</button>}
          <button onClick={remove} disabled={busy} style={btn("#5a6f8f")}>DELETE</button>
        </div>
      )}
      {error && <div style={{ ...mono, color: "#dc3c3c", marginTop: 6 }}>{error}</div>}
    </div>
  );
}

function LessonsModal({ data, onClose, onOpen, onChanged }) {
  const [showAll, setShowAll] = useState(false);
  const all = data?.lessons || [];
  const list = showAll ? all : all.filter(l => l.status === "active" || l.status === "collecting");
  const hidden = all.length - list.length;
  return (
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
        className="glass-card"
        style={{ width: "100%", maxWidth: 600, maxHeight: "85vh", padding: 0, overflow: "hidden", display: "flex", flexDirection: "column" }}
        onClick={e => e.stopPropagation()}
      >
        <div style={{ padding: "18px 22px 14px", borderBottom: "0.5px solid #1a2540", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 15, fontWeight: 700, color: "#f0f4ff" }}>
              What the AI Setter Learned From You
            </div>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#5a6f8f", letterSpacing: "0.06em", marginTop: 3 }}>
              FROM THREADS WHERE YOU REPLIED INSTEAD OF THE AI · LESSONS IN USE GO INTO EVERY DRAFT
            </div>
          </div>
          <button onClick={onClose} style={{ background: "transparent", border: "none", color: "#3a5a80", cursor: "pointer", fontSize: 18, lineHeight: 1, padding: "2px 6px" }}>×</button>
        </div>
        <div style={{ padding: "16px 22px", overflowY: "auto" }}>
          {list.length === 0 ? (
            <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 13, color: "#5a6f8f", textAlign: "center", padding: "24px 0" }}>
              Nothing learned yet. Next time the AI hands you a thread, just reply yourself and it learns from what you send.
            </div>
          ) : list.map(l => (
            <LessonRow key={`${l.id}:${l.status}:${l.lesson || ""}`} l={l} workerOnline={data.worker_online} onOpen={onOpen} onChanged={onChanged} />
          ))}
          {(hidden > 0 || showAll) && (
            <button onClick={() => setShowAll(v => !v)}
              style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, letterSpacing: "0.06em", padding: 0, border: "none", background: "transparent", color: "#3a7bd5", cursor: "pointer" }}>
              {showAll ? "HIDE OFF / NOTHING-REUSABLE" : `SHOW ${hidden} OFF / NOTHING-REUSABLE`}
            </button>
          )}
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80", letterSpacing: "0.06em", marginTop: 10, lineHeight: 1.6 }}>
            LESSONS NEVER OVERRIDE THE PLAYBOOK'S PRICE RULES OR FACTS. NEW OFFER FACTS BELONG IN THE PLAYBOOK, NOT HERE.
          </div>
        </div>
      </div>
    </div>
  );
}

// Sequence step key -> the Inbox SEQUENCE menu's label (routers/sms.py SEQUENCE_STEPS)
const SEQUENCE_STEP_LABELS = {
  gatekeeper: "0. Gatekeeper Message", curiosity_opener: "1. Initial Message", relevance: "2. Primed Message",
  guarantee: "3. Engaged Message", ask: "4. Call To Action", cta: "5. Booking Link",
};

// Which sequence step a draft is (new send_template drafts, plus pre-rename pitch drafts)
function draftTemplateKey(draft) {
  if (draft.action === "send_template") return draft.details?.template || null;
  return { send_pitch: "curiosity_opener", send_gatekeeper_pitch: "gatekeeper" }[draft.action] || null;
}

const STAGE_LABELS = {
  dm_reached: "DM Reached", primed: "Primed", engaged: "Engaged",
  interested: "Interested", not_interested: "Not Interested",
};

function AiDraftCard({ draft, busy, used, onUse, onDismiss, onRegenerate, onBook }) {
  const meta = AI_ACTION_META[draft.action] || AI_ACTION_META.reply;
  const d = draft.details || {};
  const detail =
    draft.action === "book" ? `Send Meet invite: ${d.booking_date} ${d.booking_time} → ${d.email || "(no email yet)"}`
    : draft.action === "capture_email" ? `Email: ${d.email}`
    : draft.action === "handoff" ? (d.todo_created ? "Handle this one yourself · added to your To-Do list" : "Handle this one yourself")
    : draft.action === "follow_up"
      ? `Auto check-in scheduled: ${d.follow_up_at ? new Date(d.follow_up_at).toLocaleString([], { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : d.follow_up_date}`
    : d.scheduled_followup ? "Scheduled check-in (they asked you to follow up later)"
    : null;
  const mono = { fontFamily: "'Share Tech Mono', monospace", fontSize: 9, letterSpacing: "0.08em" };
  return (
    <div className="glass-card-sm" style={{
      marginBottom: 10, padding: "10px 12px", border: `1px solid ${meta.color}55`,
      background: "rgba(58,123,213,0.06)", borderRadius: 10,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
        <span style={{ ...mono, color: "#5a6f8f" }}>AI DRAFT</span>
        <span style={{ ...mono, color: meta.color, border: `1px solid ${meta.color}66`, borderRadius: 4, padding: "1px 6px" }}>
          {meta.label}{draftTemplateKey(draft) ? ` · ${SEQUENCE_STEP_LABELS[draftTemplateKey(draft)].toUpperCase()}` : ""}
        </span>
        {used && <span style={{ ...mono, color: "#14c882" }}>IN REPLY BOX</span>}
        <div style={{ flex: 1 }} />
        <button onClick={onRegenerate} disabled={busy} className="btn btn-ghost" style={{ fontSize: 9, padding: "2px 8px" }}>
          {busy ? "..." : "REGENERATE"}
        </button>
        <button onClick={onDismiss} disabled={busy} className="btn btn-ghost" style={{ fontSize: 9, padding: "2px 8px" }}>
          DISMISS
        </button>
        {draft.action === "book" && !d.booked && (
          <button onClick={onBook} disabled={busy} className="btn btn-ghost"
            title="Create the Google Meet invite (emailed to them) and the appointment"
            style={{ fontSize: 9, padding: "2px 8px", color: "#14c882", borderColor: "#14c88266" }}>
            BOOK IT
          </button>
        )}
        {draft.reply && (
          <button onClick={onUse} disabled={busy} className="btn btn-primary" style={{ fontSize: 9, padding: "2px 10px" }}>
            USE
          </button>
        )}
      </div>
      {draft.reply
        ? <>
            <div style={{ fontSize: 13, color: "#c4d0e8", whiteSpace: "pre-wrap", fontFamily: "'Space Grotesk', sans-serif" }}>{draft.reply}</div>
            {d.second_text && (
              <div style={{ fontSize: 13, color: "#c4d0e8", whiteSpace: "pre-wrap", fontFamily: "'Space Grotesk', sans-serif",
                            marginTop: 6, paddingTop: 6, borderTop: "0.5px dashed #1a2f52" }}>
                <span style={{ ...mono, color: "#5a6f8f", marginRight: 6 }}>2ND TEXT</span>{d.second_text}
              </div>
            )}
          </>
        : <div style={{ fontSize: 12, color: "#5a6f8f", fontStyle: "italic" }}>No text to send.</div>}
      {detail && <div style={{ ...mono, color: meta.color, marginTop: 6 }}>{detail}</div>}
      {d.booked && <div style={{ ...mono, color: "#14c882", marginTop: 6 }}>BOOKED · MEET INVITE SENT, NOW SEND THE CONFIRMATION</div>}
      {d.auto_note && <div style={{ ...mono, color: "#e0a030", marginTop: 6 }}>AUTO: {d.auto_note}</div>}
      {d.stages_marked?.length > 0 && (
        <div style={{ ...mono, color: "#5a6f8f", marginTop: 6 }}>
          MARKED: {d.stages_marked.map(s => STAGE_LABELS[s] || s).join(" · ")}
        </div>
      )}
      {draft.rationale && <div style={{ fontSize: 11, color: "#5a6f8f", marginTop: 4 }}>{draft.rationale}</div>}
    </div>
  );
}

export default function InboxPanel({ initialTarget }) {
  const [convos, setConvos]       = useState([]);
  const [selected, setSelected]   = useState(null); // contact_id
  const [thread, setThread]       = useState(null);
  const [replyChannel, setReplyChannel]   = useState("sms");
  const [replyText, setReplyText] = useState("");
  const [appliedStage, setAppliedStage] = useState(null);
  const [appliedStageLabel, setAppliedStageLabel] = useState(null);
  const [replySubject, setReplySubject] = useState("");
  const [sending, setSending]     = useState(false);
  const [loading, setLoading]     = useState(true);
  const [cardOpen, setCardOpen]   = useState(false);
  const [bookingOpen, setBookingOpen] = useState(false);
  const [stageMenuOpen, setStageMenuOpen] = useState(false);
  const [seqPanelOpen, setSeqPanelOpen] = useState(false);
  const [contactSeqs, setContactSeqs] = useState(null);
  const [contactSeqsLoading, setContactSeqsLoading] = useState(false);
  const [contactSeqsBusy, setContactSeqsBusy] = useState(null); // `${sequence}:${appointment_id}` while an add/remove is in flight
  const [deleting, setDeleting]   = useState(false);
  const [composing, setComposing] = useState(false);
  const [seqOpen, setSeqOpen]       = useState(false);
  const [seqLoading, setSeqLoading] = useState(false);
  const [seqSteps, setSeqSteps]     = useState([]);
  const [seqTitle, setSeqTitle]     = useState("");
  const [seqError, setSeqError]     = useState(null);
  const [aiDraft, setAiDraft]       = useState(null);
  const [aiDraftBusy, setAiDraftBusy] = useState(false);
  const [usedDraftId, setUsedDraftId] = useState(null);
  const [aiRegenerating, setAiRegenerating] = useState(false);
  const [aiWorkerOffline, setAiWorkerOffline] = useState(false);
  const [followUps, setFollowUps] = useState(null);
  const [followUpsOpen, setFollowUpsOpen] = useState(false);

  const loadFollowUps = useCallback(async () => {
    try {
      const r = await fetch(API("/sms-setter/follow-ups"));
      if (r.ok) setFollowUps(await r.json());
    } catch {}
  }, []);

  useEffect(() => {
    loadFollowUps();
    const id = setInterval(loadFollowUps, 60000);
    return () => clearInterval(id);
  }, [loadFollowUps]);

  const [scheduling, setScheduling] = useState(false);
  const [lessons, setLessons] = useState(null);
  const [lessonsOpen, setLessonsOpen] = useState(false);
  const [teachMsg, setTeachMsg] = useState(null);

  const loadLessons = useCallback(async () => {
    try {
      const r = await fetch(API("/sms-setter/lessons"));
      if (r.ok) setLessons(await r.json());
    } catch {}
  }, []);

  useEffect(() => {
    loadLessons();
    const id = setInterval(loadLessons, 60000);
    return () => clearInterval(id);
  }, [loadLessons]);

  // TEACH: learn from the texts Dylan just sent himself on this thread
  // (for replies with no AI draft to compare against, or from before
  // learning existed — anything after a draft is captured on its own).
  const teachFromReply = async () => {
    if (!thread?.phone) return;
    setTeachMsg({ busy: true });
    try {
      const r = await fetch(API("/sms-setter/lessons/capture"), {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone: thread.phone }),
      });
      const data = await r.json().catch(() => ({}));
      setTeachMsg(r.ok
        ? { ok: true, text: data.worker_online ? "GOT IT · YOUR PC IS LEARNING FROM THIS REPLY" : "SAVED · LEARNS WHEN YOUR PC IS BACK ONLINE" }
        : { ok: false, text: (data.detail || "Couldn't save").toUpperCase() });
      loadLessons();
    } catch (e) { setTeachMsg({ ok: false, text: e.message }); }
  };

  useEffect(() => { setScheduling(false); setTeachMsg(null); }, [thread?.contact_id, thread?.phone]);

  const [channelFilter, setChannelFilter] = useState("all");
  const [timeFilter, setTimeFilter]       = useState("all");
  const [tagFilter, setTagFilter]         = useState(null);
  const [statusFilter, setStatusFilter]   = useState(null);
  const [readFilter, setReadFilter]       = useState("all"); // "all" | "unread" | "read"
  const [stageFilter, setStageFilter]     = useState(null);
  const [search, setSearch]               = useState("");

  const bottomRef = useRef(null);
  const autoOpenedRef = useRef(false);

  const [availableTags, setAvailableTags] = useState([]);

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(API("/inbox/tags"));
        if (r.ok) setAvailableTags(await r.json());
      } catch {}
    })();
  }, []);

  const loadConvos = useCallback(async () => {
    try {
      const params = new URLSearchParams({ channel: channelFilter, since: timeFilter });
      if (tagFilter) params.set("tag", tagFilter);
      if (statusFilter) params.set("contact_status", statusFilter);
      if (stageFilter) params.set("stage", stageFilter);
      const r = await fetch(API(`/inbox/conversations?${params.toString()}`));
      if (r.ok) setConvos(await r.json());
    } catch {}
    setLoading(false);
  }, [channelFilter, timeFilter, tagFilter, statusFilter, stageFilter]);

  useEffect(() => {
    loadConvos();
    const id = setInterval(loadConvos, 15000);
    return () => clearInterval(id);
  }, [loadConvos]);

  // Deep-link from toasts/dashboard widgets, which only carry a phone number —
  // resolve it to a contact once the conversation list has loaded.
  useEffect(() => {
    if (!initialTarget || autoOpenedRef.current) return;
    if (initialTarget.contactId) {
      autoOpenedRef.current = true;
      openThread(initialTarget.contactId);
    } else if (initialTarget.phone && convos.length > 0) {
      const match = convos.find(c => c.phone === initialTarget.phone);
      if (match) {
        autoOpenedRef.current = true;
        openThread(match.contact_id);
      }
    }
  }, [initialTarget, convos]);

  // Silently refetch the currently-open thread — used by background polling
  // and post-action refreshes, where blanking the view first (openThread's
  // setThread(null)) would cause a visible flash every few seconds.
  const refreshThread = async (contactId) => {
    try {
      const r = await fetch(API(`/inbox/contact/${encodeURIComponent(contactId)}`));
      if (r.ok) setThread(await r.json());
    } catch {}
  };

  const openThread = async (contactId) => {
    setSelected(contactId);
    setThread(null);
    setSeqOpen(false);
    setStageMenuOpen(false);
    setSeqPanelOpen(false);
    setContactSeqs(null);
    setReplySubject("");
    setAppliedStage(null);
    setAppliedStageLabel(null);
    setConvos(prev => prev.map(c => c.contact_id === contactId ? { ...c, unread: false } : c));
    await refreshThread(contactId);
  };

  useEffect(() => {
    if (!selected) return;
    const id = setInterval(() => refreshThread(selected), 8000);
    return () => clearInterval(id);
  }, [selected]);

  // AI setter draft (sms_setter_ai.py) — polled alongside the thread so a
  // draft generated ~45s after an inbound reply shows up without a reload.
  const loadAiDraft = useCallback(async (phone) => {
    if (!phone) { setAiDraft(null); return; }
    try {
      const r = await fetch(API(`/sms-setter/draft?phone=${encodeURIComponent(phone)}`));
      if (r.ok) {
        const data = await r.json();
        setAiDraft(data.draft);
        setAiRegenerating(!!data.regenerating);
      }
    } catch {}
  }, []);

  useEffect(() => {
    setAiDraft(null);
    setUsedDraftId(null);
    setAiRegenerating(false);
    setAiWorkerOffline(false);
    const phone = thread?.phone;
    if (!phone) return;
    loadAiDraft(phone);
    const id = setInterval(() => loadAiDraft(phone), 8000);
    return () => clearInterval(id);
  }, [thread?.contact_id, thread?.phone, loadAiDraft]);

  const useAiDraft = () => {
    if (!aiDraft) return;
    setReplyChannel("sms");
    const second = aiDraft.details?.second_text;
    setReplyText((aiDraft.reply || "") + (second ? `\n\n${second}` : ""));
    setUsedDraftId(aiDraft.id);
    const templateStage = draftTemplateKey(aiDraft);
    setAppliedStage(templateStage || null);
    setAppliedStageLabel(templateStage ? SEQUENCE_STEP_LABELS[templateStage] : null);
  };

  const dismissAiDraft = async () => {
    if (!aiDraft) return;
    setAiDraftBusy(true);
    try { await fetch(API(`/sms-setter/draft/${aiDraft.id}/dismiss`), { method: "POST" }); } catch {}
    setAiDraft(null);
    setUsedDraftId(null);
    setAiDraftBusy(false);
  };

  const bookAiDraft = async () => {
    if (!aiDraft || !thread?.phone) return;
    setAiDraftBusy(true);
    try {
      const r = await fetch(API(`/sms-setter/draft/${aiDraft.id}/book`), { method: "POST" });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        window.alert(`Couldn't book: ${err.detail || r.status}`);
      }
      await loadAiDraft(thread.phone);
      if (selected) await refreshThread(selected);
    } catch {}
    setAiDraftBusy(false);
  };

  // Drafting runs on Dylan's PC — this just queues the request; the new
  // draft appears on a later poll (within ~a minute if the worker is online).
  const regenerateAiDraft = async () => {
    if (!thread?.phone) return;
    setAiDraftBusy(true);
    try {
      const r = await fetch(API("/sms-setter/draft/regenerate"), {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone: thread.phone }),
      });
      if (r.ok) {
        const data = await r.json();
        setAiRegenerating(true);
        setAiWorkerOffline(!data.worker_online);
      }
    } catch {}
    setUsedDraftId(null);
    setAiDraftBusy(false);
  };

  // Default the reply channel to whichever channel this contact most
  // recently used — a fresh contact card falls back to whichever channel
  // has a usable address.
  useEffect(() => {
    if (!thread) return;
    const lastChannel = thread.messages?.length ? thread.messages[thread.messages.length - 1].channel : null;
    if (lastChannel) setReplyChannel(lastChannel);
    else if (thread.phone) setReplyChannel("sms");
    else if (thread.email) setReplyChannel("email");
  }, [thread?.contact_id]);

  useEffect(() => {
    if (thread?.email_subject && replyChannel === "email") {
      setReplySubject(thread.email_subject.toLowerCase().startsWith("re:") ? thread.email_subject : `Re: ${thread.email_subject}`);
    }
  }, [thread, replyChannel]);

  // Only auto-scroll when the message count actually grows — every poll
  // returns a fresh array reference even with no new messages, so keying
  // off the array itself would re-trigger a smooth-scroll every 8s.
  const msgCount = thread?.messages?.length ?? 0;
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgCount]);

  const sendReply = async () => {
    if (!replyText.trim() || !selected || !thread) return;
    setSending(true);
    try {
      if (replyChannel === "sms") {
        await fetch(API("/sms/send"), {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            phone: thread.phone,
            body: replyText.trim(),
            ...(appliedStage ? { stage: appliedStage } : {}),
            ...(usedDraftId ? { ai_draft_id: usedDraftId } : {}),
          }),
        });
        setAiDraft(null);
        setUsedDraftId(null);
      } else {
        await fetch(API("/email/send"), {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            thread_id: thread.email_thread_id || "",
            to: thread.email,
            subject: replySubject || thread.email_subject || "",
            body: replyText.trim(),
          }),
        });
      }
      setReplyText("");
      setAppliedStage(null);
      setAppliedStageLabel(null);
      await refreshThread(selected);
      await loadConvos();
    } catch {}
    setSending(false);
  };

  const openSequence = async () => {
    if (seqOpen) { setSeqOpen(false); return; }
    setSeqOpen(true);
    setSeqLoading(true);
    setSeqError(null);
    try {
      const url = replyChannel === "email"
        ? API(`/email/sequence/${encodeURIComponent(selected)}`)
        : API(`/sms/sequence/${encodeURIComponent(thread.phone)}`);
      const r = await fetch(url);
      const data = await r.json();
      if (!data.ok) {
        setSeqError("Failed to load sequence.");
        setSeqSteps([]);
      } else {
        setSeqSteps(data.steps);
        setSeqTitle(data.sequence_title);
      }
    } catch {
      setSeqError("Failed to load sequence.");
      setSeqSteps([]);
    }
    setSeqLoading(false);
  };

  const applyStep = (step) => {
    setReplyText(step.text);
    if (replyChannel === "email" && step.subject) setReplySubject(step.subject);
    setAppliedStage(step.key);
    setAppliedStageLabel(step.label);
    setSeqOpen(false);
  };

  const setStage = async (stage, checked) => {
    if (!selected) return;
    await fetch(API(`/inbox/contact/${encodeURIComponent(selected)}/stage`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ stage, checked }),
    });
    await refreshThread(selected);
    await loadConvos();
  };

  const loadContactSeqs = async (contactId) => {
    setContactSeqsLoading(true);
    try {
      const r = await fetch(API(`/appointment-reminders/contact/${encodeURIComponent(contactId)}/sequences`));
      setContactSeqs(r.ok ? await r.json() : null);
    } catch {
      setContactSeqs(null);
    }
    setContactSeqsLoading(false);
  };

  const openSeqPanel = () => {
    setSeqPanelOpen(o => {
      const next = !o;
      if (next && selected) loadContactSeqs(selected);
      return next;
    });
  };

  const toggleDripSequence = async (sequence, appointmentId, active) => {
    setContactSeqsBusy(`${sequence}:${appointmentId}`);
    try {
      await fetch(API(`/appointment-reminders/${appointmentId}/sequence/${sequence}/${active ? "remove" : "add"}`), {
        method: "POST",
      });
      await loadContactSeqs(selected);
    } catch {}
    setContactSeqsBusy(null);
  };

  const deleteConvo = async () => {
    if (!selected) return;
    setDeleting(true);
    try {
      await fetch(API(`/inbox/contact/${encodeURIComponent(selected)}`), { method: "DELETE" });
      setSelected(null);
      setThread(null);
      await loadConvos();
    } catch {}
    setDeleting(false);
  };

  const unreadCount = convos.filter(c => c.unread).length;
  // Search matches name, practice, email, last message, and phone by digits
  // (so "331303", "(331) 303" and "+1331303..." all find the same thread).
  const searchTerm = search.trim().toLowerCase();
  const searchDigits = searchTerm.replace(/\D/g, "");
  const matchesSearch = (c) => {
    if (!searchTerm) return true;
    const text = [c.owner, c.business, c.email, c.last_message].filter(Boolean).join(" ").toLowerCase();
    if (text.includes(searchTerm)) return true;
    return searchDigits.length >= 3 && (c.phone || "").replace(/\D/g, "").includes(searchDigits);
  };
  const filteredConvos = convos.filter(c => {
    if (!matchesSearch(c)) return false;
    if (readFilter === "unread") return !!c.unread;
    if (readFilter === "read") return !c.unread;
    return true;
  });

  const selectStyle = {
    fontFamily: "'Share Tech Mono', monospace", fontSize: 9, letterSpacing: "0.06em",
    background: "#0d1626", color: "#c4d0e8", border: "1px solid #1a2540",
    borderRadius: 6, padding: "5px 8px", cursor: "pointer",
  };

  return (
    <div style={{ display: "flex", height: "100%" }}>

      {cardOpen && (
        <ContactCard
          contactId={thread?.contact_id}
          phone={thread?.phone}
          onClose={() => setCardOpen(false)}
          onSaved={() => refreshThread(selected)}
        />
      )}

      <BookingModal
        open={bookingOpen}
        onClose={() => setBookingOpen(false)}
        contactId={thread?.contact_id}
        phone={thread?.phone}
        name={thread?.owner}
        email={thread?.email}
        channel={replyChannel}
        contact={{ business: thread?.business, grade: thread?.grade }}
      />

      {composing && (
        <ComposeModal
          onClose={() => setComposing(false)}
          onSent={async ({ contactId }) => {
            setComposing(false);
            await loadConvos();
            if (contactId) await openThread(contactId);
          }}
        />
      )}

      {/* Thread list — full-width on mobile when no thread is open, hidden
          once one is (the thread view takes over); always side-by-side at
          md+, regardless of selection. */}
      <aside
        className={(selected ? "hidden " : "flex ") + "md:flex flex-col flex-shrink-0 w-full md:w-[280px]"}
        style={{ borderRight: "0.5px solid #1a2540" }}
      >
        <div style={{ padding: "14px 16px", borderBottom: "0.5px solid #1a2540",
                      display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 14, fontWeight: 600, color: "#f0f4ff" }}>
            Inbox
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80" }}>
              {filteredConvos.length} THREADS
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

        <SetterModeBar
          followUpCount={followUps?.follow_ups?.length || 0}
          onOpenFollowUps={() => { loadFollowUps(); setFollowUpsOpen(true); }}
          lessonCount={lessons?.lessons?.filter(l => l.status === "active").length || 0}
          onOpenLessons={() => { loadLessons(); setLessonsOpen(true); }}
        />
        {lessonsOpen && (
          <LessonsModal
            data={lessons}
            onClose={() => setLessonsOpen(false)}
            onChanged={loadLessons}
            onOpen={(l) => {
              setLessonsOpen(false);
              const match = l.contact_id || convos.find(c => phoneDigits(c.phone) === phoneDigits(l.phone))?.contact_id;
              if (match) openThread(match);
            }}
          />
        )}
        {followUpsOpen && (
          <FollowUpsModal
            data={followUps}
            onClose={() => setFollowUpsOpen(false)}
            onChanged={loadFollowUps}
            onOpen={(f) => {
              setFollowUpsOpen(false);
              const match = f.contact_id || convos.find(c => phoneDigits(c.phone) === phoneDigits(f.phone))?.contact_id;
              if (match) openThread(match);
            }}
          />
        )}

        {/* Filter bar */}
        <div style={{ padding: "10px 16px", borderBottom: "0.5px solid #1a2540", display: "flex", flexDirection: "column", gap: 8 }}>
          <div style={{ position: "relative" }}>
            <input
              className="dg-input"
              value={search}
              onChange={e => setSearch(e.target.value)}
              onKeyDown={e => { if (e.key === "Escape") setSearch(""); }}
              placeholder="Search name, practice, phone, email..."
              style={{ width: "100%", boxSizing: "border-box", fontSize: 12, padding: "7px 28px 7px 10px" }}
            />
            {search && (
              <button onClick={() => setSearch("")} title="Clear search"
                style={{
                  position: "absolute", right: 6, top: "50%", transform: "translateY(-50%)",
                  background: "transparent", border: "none", color: "#5a6f8f", cursor: "pointer",
                  fontSize: 14, lineHeight: 1, padding: "2px 4px",
                }}>
                ×
              </button>
            )}
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            {[
              { value: "all",    label: "ALL" },
              { value: "unread", label: `UNREAD${unreadCount ? ` (${unreadCount})` : ""}` },
              { value: "read",   label: "READ" },
            ].map(o => (
              <button
                key={o.value}
                onClick={() => setReadFilter(o.value)}
                style={{
                  flex: 1, padding: "5px 0", borderRadius: 6,
                  border: `1px solid ${readFilter === o.value ? "rgba(58,123,213,0.6)" : "rgba(58,123,213,0.2)"}`,
                  background: readFilter === o.value ? "rgba(58,123,213,0.15)" : "transparent",
                  color: readFilter === o.value ? "#3a7bd5" : "#5a6f8f",
                  fontFamily: "'Share Tech Mono', monospace", fontSize: 9, letterSpacing: "0.06em",
                  cursor: "pointer",
                }}
              >
                {o.label}
              </button>
            ))}
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            <select value={channelFilter} onChange={e => setChannelFilter(e.target.value)} style={{ ...selectStyle, flex: 1 }}>
              <option value="all">ALL CHANNELS</option>
              <option value="sms">SMS ONLY</option>
              <option value="email">EMAIL ONLY</option>
            </select>
            <select value={timeFilter} onChange={e => setTimeFilter(e.target.value)} style={{ ...selectStyle, flex: 1 }}>
              <option value="all">ALL TIME</option>
              <option value="today">TODAY</option>
              <option value="7d">LAST 7 DAYS</option>
              <option value="30d">LAST 30 DAYS</option>
            </select>
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            <select
              value={statusFilter || ""}
              onChange={e => setStatusFilter(e.target.value || null)}
              style={{ ...selectStyle, flex: 1 }}
            >
              <option value="">ALL STATUSES</option>
              {CONTACT_STATUSES.map(s => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
            <select
              value={tagFilter || ""}
              onChange={e => setTagFilter(e.target.value || null)}
              style={{ ...selectStyle, flex: 1 }}
            >
              <option value="">ALL TAGS</option>
              {availableTags.map(t => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            <select
              value={stageFilter || ""}
              onChange={e => setStageFilter(e.target.value || null)}
              style={{ ...selectStyle, flex: 1 }}
            >
              <option value="">ALL STAGES</option>
              {STAGE_OPTIONS.map(s => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </div>
        </div>

        <div style={{ flex: 1, overflowY: "auto" }}>
          {loading && (
            <div style={{ padding: 16, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52" }}>
              LOADING...
            </div>
          )}
          {!loading && filteredConvos.length === 0 && (
            <div style={{ padding: 16, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52" }}>
              {convos.length === 0 ? "NO CONVERSATIONS" : "NO MATCHING CONVERSATIONS"}
            </div>
          )}
          {filteredConvos.map(c => {
            const isSel = selected === c.contact_id;
            const isUnread = c.unread && !isSel;
            return (
              <button key={c.contact_id} onClick={() => openThread(c.contact_id)}
                style={{
                  width: "100%", textAlign: "left", padding: "12px 16px",
                  cursor: "pointer", position: "relative",
                  background: isSel ? "#0d1626" : (isUnread ? "rgba(58,123,213,0.06)" : "transparent"),
                  borderBottom: "0.5px solid #1a2540",
                  borderLeft: isSel ? "2px solid #3a7bd5" : (isUnread ? "2px solid rgba(58,123,213,0.5)" : "2px solid transparent"),
                  borderTop: "none", borderRight: "none",
                  transition: "all 0.1s",
                }}
                onMouseEnter={e => { if (!isSel) e.currentTarget.style.background = "#0a1020"; }}
                onMouseLeave={e => { if (!isSel) e.currentTarget.style.background = isUnread ? "rgba(58,123,213,0.06)" : "transparent"; }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 3 }}>
                  <span style={{ display: "flex", alignItems: "center", gap: 6, overflow: "hidden", flex: 1 }}>
                    {isUnread && (
                      <span title="Unread message" style={{
                        width: 7, height: 7, borderRadius: "50%", flexShrink: 0,
                        background: "#3a7bd5", boxShadow: "0 0 6px 1px rgba(58,123,213,0.7)",
                      }} />
                    )}
                    <span style={{ fontSize: 13, fontWeight: isUnread ? 700 : 500, color: isUnread ? "#f0f4ff" : "#c4d0e8", overflow: "hidden",
                                   textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {c.owner || c.business || c.phone || c.email}
                    </span>
                  </span>
                  {c.channels.map(ch => (
                    <span key={ch} style={{
                      fontFamily: "'Share Tech Mono', monospace", fontSize: 8, letterSpacing: "0.05em",
                      padding: "2px 5px", borderRadius: 4, marginLeft: 4, flexShrink: 0,
                      background: CHANNEL_CHIP[ch].bg, color: CHANNEL_CHIP[ch].color,
                    }}>
                      {CHANNEL_CHIP[ch].label}
                    </span>
                  ))}
                  <span className={`badge ${convoBadge(c).cls}`}
                    style={{ marginLeft: 6, flexShrink: 0 }}>
                    {convoBadge(c).label}
                  </span>
                </div>
                <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a4a7a" }}>
                  {c.phone || c.email}
                </div>
                {(c.contact_status || (c.tags || []).length > 0) && (
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 4 }}>
                    {c.contact_status && (
                      <span style={{
                        fontFamily: "'Share Tech Mono', monospace", fontSize: 8, letterSpacing: "0.05em",
                        padding: "1px 5px", borderRadius: 4,
                        background: "rgba(58,123,213,0.1)", color: "#5a8ac0",
                      }}>
                        {CONTACT_STATUSES.find(s => s.value === c.contact_status)?.label || c.contact_status}
                      </span>
                    )}
                    {(c.tags || []).map(t => (
                      <span key={t} style={{
                        fontFamily: "'Share Tech Mono', monospace", fontSize: 8, letterSpacing: "0.05em",
                        padding: "1px 5px", borderRadius: 4,
                        background: "rgba(160,110,240,0.1)", color: "#a06ef0",
                      }}>
                        {t}
                      </span>
                    ))}
                  </div>
                )}
                {c.last_message && (
                  <div style={{ fontSize: 11, color: isUnread ? "#8aaad0" : "#3a4f6f", fontWeight: isUnread ? 600 : 400, marginTop: 4,
                                overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {htmlToText(c.last_message)}
                  </div>
                )}
              </button>
            );
          })}
        </div>
      </aside>

      {/* Thread view — takes over full-width on mobile once a thread is
          selected; always visible alongside the list at md+. */}
      <div className={(!selected ? "hidden " : "flex ") + "md:flex flex-col flex-1 min-w-0"}>
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
            <div className="flex-wrap" style={{ padding: "14px 20px", borderBottom: "0.5px solid #1a2540",
                          display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, flexShrink: 0 }}>
              <button
                onClick={() => setSelected(null)}
                className="md:hidden"
                style={{
                  background: "none", border: "none", color: "#3a7bd5", cursor: "pointer",
                  fontFamily: "'Share Tech Mono', monospace", fontSize: 10, letterSpacing: "0.06em",
                  padding: "4px 6px 4px 0", flexShrink: 0,
                }}
              >
                ‹ BACK
              </button>
              <div
                onClick={() => setCardOpen(true)}
                style={{ cursor: "pointer" }}
                title="View contact card"
              >
                <div style={{
                  fontFamily: "'Space Grotesk', sans-serif", fontSize: 14, fontWeight: 600, color: "#f0f4ff",
                  display: "flex", alignItems: "center", gap: 6,
                }}>
                  {thread?.owner || thread?.business || thread?.phone || thread?.email}
                  <span style={{
                    fontFamily: "'Share Tech Mono', monospace", fontSize: 8, color: "#3a7bd5",
                    padding: "2px 6px", borderRadius: 4, background: "rgba(58,123,213,0.1)",
                    letterSpacing: "0.06em",
                  }}>VIEW</span>
                </div>
                <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80",
                              letterSpacing: "0.1em", marginTop: 2 }}>
                  {[thread?.phone, thread?.email].filter(Boolean).join(" · ")}
                  {thread?.grade ? ` · GRADE ${thread.grade}` : ""}
                </div>
              </div>

              <div className="flex-wrap" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                {thread?.status !== "closed" && (
                  <>
                    <div style={{ position: "relative" }}>
                      <button onClick={() => setStageMenuOpen(o => !o)} className="btn btn-ghost"
                        style={{
                          fontSize: 10,
                          borderColor: (replyChannel === "email" ? thread?.email_stage_interested : thread?.stage_interested) ? "rgba(240,160,40,0.6)" : "rgba(240,160,40,0.35)",
                          color: "#f0a028",
                          background: (replyChannel === "email" ? thread?.email_stage_interested : thread?.stage_interested) ? "rgba(240,160,40,0.12)" : "transparent",
                        }}>
                        {/* Stages are per channel and follow the reply-channel
                            toggle by the compose box: SMS stages live on
                            sms_conversations, Email stages on
                            email_contact_stages (+ handoff touches). */}
                        {(replyChannel === "email" ? thread?.email_stage_interested : thread?.stage_interested)
                          ? `★ ${replyChannel === "email" ? "EMAIL" : "SMS"} INTERESTED`
                          : `${replyChannel === "email" ? "EMAIL" : "SMS"} STAGE ▾`}
                      </button>
                      {stageMenuOpen && (
                        <div className="dg-menu" style={{
                          position: "absolute", top: "calc(100% + 4px)", right: 0, zIndex: 20,
                          background: "#0d1626", border: "1px solid #1a2540", borderRadius: 8,
                          padding: "8px 10px", minWidth: 150, boxShadow: "0 8px 24px rgba(0,0,0,0.4)",
                          display: "flex", flexDirection: "column", gap: 6,
                        }}>
                          {(replyChannel === "email" ? [
                            // Email-channel stages. Touch 1/2/3 are automatic
                            // Email Handoff progress markers (disabled), shown only
                            // for enrolled contacts. Engaged/Interested count as a
                            // positive reply in Email analytics.
                            ...(thread?.email_handoff_enrolled ? [
                              { key: "touch1", label: "Touch 1 Sent", checked: !!thread?.email_handoff_touch1_sent_at, disabled: true },
                              { key: "touch2", label: "Touch 2 Sent", checked: !!thread?.email_handoff_touch2_sent_at, disabled: true },
                              { key: "touch3", label: "Touch 3 Sent", checked: !!thread?.email_handoff_touch3_sent_at, disabled: true },
                            ] : []),
                            { key: "email_replied",    label: "Replied",    checked: !!thread?.email_stage_replied },
                            { key: "email_engaged",    label: "Engaged",    checked: !!thread?.email_stage_engaged },
                            { key: "email_interested", label: "Interested", checked: !!thread?.email_stage_interested },
                            { key: "not_interested",   label: "Not Interested", checked: thread?.disposition === "not_interested" },
                          ] : [
                            { key: "initial_outreach", label: "Initial Outreach", checked: !!thread?.stage_initial_outreach },
                            { key: "replied",     label: "Replied",    checked: !!thread?.stage_replied },
                            { key: "dm_reached",  label: "DM Reached", checked: !!thread?.stage_dm_reached },
                            { key: "primed",      label: "Primed",     checked: !!thread?.stage_primed },
                            { key: "engaged",     label: "Engaged",    checked: !!thread?.stage_engaged },
                            { key: "interested",  label: "Interested", checked: !!thread?.stage_interested },
                            { key: "not_interested", label: "Not Interested", checked: thread?.disposition === "not_interested" },
                          ]).map(s => (
                            <label key={s.key} style={{
                              display: "flex", alignItems: "center", gap: 8,
                              cursor: s.disabled ? "default" : "pointer",
                              fontFamily: "'Share Tech Mono', monospace", fontSize: 10,
                              color: s.disabled ? "#5a6f8f" : "#c4d0e8",
                            }}>
                              <input
                                type="checkbox"
                                checked={s.checked}
                                disabled={!!s.disabled}
                                onChange={e => !s.disabled && setStage(s.key, e.target.checked)}
                              />
                              {s.label}
                            </label>
                          ))}
                        </div>
                      )}
                    </div>
                    <div style={{ position: "relative" }}>
                      <button onClick={openSeqPanel} className="btn btn-ghost"
                        style={{ fontSize: 10, borderColor: "rgba(58,123,213,0.4)", color: "#6ab0ff" }}>
                        SEQUENCES ▾
                      </button>
                      {seqPanelOpen && (
                        <div className="dg-menu" style={{
                          position: "absolute", top: "calc(100% + 4px)", right: 0, zIndex: 20,
                          background: "#0d1626", border: "1px solid #1a2540", borderRadius: 8,
                          padding: "10px 12px", width: 280, boxShadow: "0 8px 24px rgba(0,0,0,0.4)",
                          fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#c4d0e8",
                          maxHeight: 360, overflowY: "auto",
                        }}>
                          {contactSeqsLoading && <div style={{ color: "#3a5a80" }}>LOADING…</div>}
                          {!contactSeqsLoading && contactSeqs && (
                            <>
                              <div style={{ color: "#6ab0ff", letterSpacing: "0.08em", marginBottom: 6 }}>DRIP SEQUENCES</div>
                              {contactSeqs.drip_sequences.length === 0 && (
                                <div style={{ color: "#3a5a80", marginBottom: 10 }}>
                                  None yet — no_show/cancel/reminder only appear once triggered by an appointment outcome.
                                </div>
                              )}
                              {contactSeqs.drip_sequences.map((s) => {
                                const busyKey = `${s.sequence}:${s.appointment_id}`;
                                const label = { no_show: "No Show", cancel: "Cancellation", reminder: "Reminder" }[s.sequence];
                                return (
                                  <div key={busyKey} style={{
                                    display: "flex", alignItems: "center", justifyContent: "space-between",
                                    padding: "6px 0", borderBottom: "1px solid #1a2540", gap: 8,
                                  }}>
                                    <div>
                                      <div style={{ color: "#f0f4ff" }}>{label}</div>
                                      <div style={{ color: "#3a5a80", fontSize: 9, marginTop: 2 }}>
                                        {fmtMsgTime(s.appointment_at)} · {s.step_label}
                                        {s.active ? "" : " · stopped"}
                                      </div>
                                    </div>
                                    <button
                                      disabled={contactSeqsBusy === busyKey}
                                      onClick={() => toggleDripSequence(s.sequence, s.appointment_id, s.active)}
                                      className="btn btn-ghost"
                                      style={{
                                        fontSize: 9, padding: "3px 8px", flexShrink: 0,
                                        borderColor: s.active ? "rgba(220,80,80,0.4)" : "rgba(20,200,130,0.4)",
                                        color: s.active ? "#e05c5c" : "#14c882",
                                      }}
                                    >
                                      {s.active ? "REMOVE" : "ADD"}
                                    </button>
                                  </div>
                                );
                              })}

                              <div style={{ color: "#6ab0ff", letterSpacing: "0.08em", margin: "12px 0 6px" }}>DM FOLLOW-UP</div>
                              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                                <div style={{ color: "#3a5a80", fontSize: 9 }}>
                                  {contactSeqs.dm_followup?.dm_followup_enrolled_at
                                    ? `Enrolled${contactSeqs.dm_followup.dm_followup_anchor_at ? " · mid-cycle" : ""}`
                                    : "Not enrolled — independent of the DM Reached checkbox above."}
                                </div>
                                <button
                                  onClick={async () => {
                                    const active = !contactSeqs.dm_followup?.dm_followup_enrolled_at;
                                    const res = await fetch(`/api/inbox/contact/${selected}/dm-followup`, {
                                      method: "POST",
                                      headers: { "Content-Type": "application/json" },
                                      body: JSON.stringify({ active }),
                                    });
                                    if (!res.ok) {
                                      const d = await res.json().catch(() => ({}));
                                      alert(d.detail || "Failed to update DM Follow-Up enrollment.");
                                      return;
                                    }
                                    await loadContactSeqs(selected);
                                  }}
                                  className="btn btn-ghost"
                                  style={{
                                    fontSize: 9, padding: "3px 8px", flexShrink: 0,
                                    borderColor: contactSeqs.dm_followup?.dm_followup_enrolled_at ? "rgba(220,80,80,0.4)" : "rgba(20,200,130,0.4)",
                                    color: contactSeqs.dm_followup?.dm_followup_enrolled_at ? "#e05c5c" : "#14c882",
                                  }}
                                >
                                  {contactSeqs.dm_followup?.dm_followup_enrolled_at ? "REMOVE" : "ADD"}
                                </button>
                              </div>

                              {contactSeqs.onboarding.length > 0 && (
                                <>
                                  <div style={{ color: "#6ab0ff", letterSpacing: "0.08em", margin: "12px 0 6px" }}>ONBOARDING (read-only)</div>
                                  {contactSeqs.onboarding.map((o) => (
                                    <div key={o.appointment_id} style={{ color: "#3a5a80", fontSize: 9, padding: "4px 0" }}>
                                      Kickoff {o.kickoff_sent_at ? "sent" : "pending"}
                                      {" · "}Follow-up {o.followup_sent_at ? "sent" : "pending"}
                                    </div>
                                  ))}
                                </>
                              )}
                            </>
                          )}
                        </div>
                      )}
                    </div>
                    <button onClick={() => setBookingOpen(true)} className="btn btn-ghost"
                      style={{ fontSize: 10, borderColor: "rgba(20,200,130,0.35)", color: "#14c882" }}>
                      BOOK APPOINTMENT
                    </button>
                  </>
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
              {/* The SMS/EMAIL buttons below the compose box double as a
                  filter on this list — previously they only set the reply
                  channel, so clicking them left the thread unchanged. Only
                  filters when the contact has both a phone and email;
                  otherwise there's nothing to filter. */}
              {(thread?.phone && thread?.email
                ? thread.messages?.filter(m => m.channel === replyChannel)
                : thread?.messages
              )?.map((m, i) => {
                const isOut = m.direction === "outbound";
                const chip = CHANNEL_CHIP[m.channel];
                return (
                  <div key={i} style={{ display: "flex", justifyContent: isOut ? "flex-end" : "flex-start" }}>
                    <div style={{
                      maxWidth: "min(420px, 82%)", padding: "9px 13px", borderRadius: isOut ? "8px 8px 2px 8px" : "8px 8px 8px 2px",
                      background: isOut ? "#1f3d70" : "#0d1626",
                      border: `0.5px solid ${isOut ? "#2857a0" : "#1a2540"}`,
                    }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                        <span style={{
                          fontFamily: "'Share Tech Mono', monospace", fontSize: 8, letterSpacing: "0.05em",
                          padding: "1px 5px", borderRadius: 4,
                          background: chip.bg, color: chip.color,
                        }}>
                          {chip.label}
                        </span>
                        {m.channel === "email" && m.subject && (
                          <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9,
                                        color: isOut ? "#7fa8dd" : "#6a8ab0" }}>
                            {m.subject}
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: 13, color: isOut ? "#c8dcff" : "#8aaad0", lineHeight: 1.4, whiteSpace: "pre-wrap" }}>
                        {m.channel === "email" ? htmlToText(m.body) : m.body}
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
              <div style={{ position: "relative", padding: "12px 20px", borderTop: "0.5px solid #1a2540", flexShrink: 0 }}>
                {(() => {
                  if (!thread?.phone) return null;
                  const fu = followUps?.follow_ups?.find(f => phoneDigits(f.phone) === phoneDigits(thread.phone));
                  if (scheduling) return (
                    <ScheduleFollowUpForm phone={thread.phone} onCancel={() => setScheduling(false)}
                      onDone={() => { setScheduling(false); loadFollowUps(); }} />
                  );
                  const sms = (thread.messages || []).filter(m => m.channel === "sms");
                  const lastIsMine = sms.length > 0 && sms[sms.length - 1].direction === "outbound"
                    && sms.some(m => m.direction === "inbound");
                  const link = (color) => ({
                    fontFamily: "'Share Tech Mono', monospace", fontSize: 9, letterSpacing: "0.06em",
                    padding: 0, border: "none", background: "transparent", cursor: "pointer", color,
                  });
                  return (
                    <>
                      {(!fu || lastIsMine) && (
                        <div style={{ display: "flex", gap: 14, flexWrap: "wrap", alignItems: "center", marginBottom: 8 }}>
                          {!fu && (
                            <button onClick={() => setScheduling(true)} title="Have the AI setter text them at a time you pick" style={link("#e0a030")}>
                              + AI FOLLOW-UP
                            </button>
                          )}
                          {lastIsMine && (
                            <button onClick={teachFromReply} disabled={teachMsg?.busy}
                              title="Have the AI setter learn from the reply you just sent, so it handles this kind of message itself next time"
                              style={link("#14c882")}>
                              TEACH AI FROM MY REPLY
                            </button>
                          )}
                          {teachMsg?.text && (
                            <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, letterSpacing: "0.06em", color: teachMsg.ok ? "#14c882" : "#dc3c3c" }}>
                              {teachMsg.text}
                            </span>
                          )}
                        </div>
                      )}
                      {fu && (
                        <div onClick={() => setFollowUpsOpen(true)} title="Open Scheduled Follow-Ups (change time or cancel)"
                          style={{
                            marginBottom: 10, padding: "7px 12px", borderRadius: 8, cursor: "pointer",
                            border: "1px solid rgba(224,160,48,0.35)", background: "rgba(224,160,48,0.07)",
                            fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, color: "#e0a030",
                          }}>
                          Agent follows up {fmtInZone(fu.due_at, fu.timezone)} their time ({fmtRelative(fu.due_at)})
                          {fu.set_by === "dylan" ? " · set by you" : ""}
                        </div>
                      )}
                    </>
                  );
                })()}
                {aiDraft && !aiRegenerating && <AiDraftCard
                  draft={aiDraft} busy={aiDraftBusy} used={usedDraftId === aiDraft.id}
                  onUse={useAiDraft} onDismiss={dismissAiDraft} onRegenerate={regenerateAiDraft}
                  onBook={bookAiDraft}
                />}
                {aiRegenerating && (
                  <div style={{ marginBottom: 10, fontFamily: "'Share Tech Mono', monospace", fontSize: 9, letterSpacing: "0.08em",
                                color: aiWorkerOffline ? "#dc3c3c" : "#3a7bd5" }}>
                    {aiWorkerOffline
                      ? "AI DRAFT QUEUED · PC OFFLINE, WILL DRAFT WHEN YOUR COMPUTER IS ON"
                      : "AI SETTER IS DRAFTING..."}
                  </div>
                )}
                <div style={{ display: "flex", gap: 6, marginBottom: 8 }}>
                  {["sms", "email"].map(ch => {
                    const available = ch === "sms" ? !!thread?.phone : !!thread?.email;
                    return (
                      <button key={ch} onClick={() => {
                        if (!available) return;
                        setReplyChannel(ch);
                        setAppliedStage(null);
                        setAppliedStageLabel(null);
                      }} disabled={!available}
                        style={{
                          padding: "4px 10px", borderRadius: 6,
                          border: `1px solid ${replyChannel === ch ? "rgba(58,123,213,0.6)" : "rgba(58,123,213,0.2)"}`,
                          background: replyChannel === ch ? "rgba(58,123,213,0.15)" : "transparent",
                          color: available ? (replyChannel === ch ? "#3a7bd5" : "#5a6f8f") : "#2a3a52",
                          fontFamily: "'Share Tech Mono', monospace", fontSize: 9, letterSpacing: "0.06em",
                          cursor: available ? "pointer" : "not-allowed",
                        }}>
                        {ch === "sms" ? "SMS" : "EMAIL"}
                      </button>
                    );
                  })}
                </div>
                {replyChannel === "email" && (
                  <input
                    className="dg-input"
                    type="text"
                    placeholder="Subject"
                    value={replySubject}
                    onChange={e => setReplySubject(e.target.value)}
                    style={{ width: "100%", fontSize: 12, marginBottom: 8, boxSizing: "border-box" }}
                  />
                )}
                <div style={{ display: "flex", gap: 8 }}>
                  <button onClick={openSequence} className="btn btn-ghost" style={{ fontSize: 10, alignSelf: "flex-end" }}>
                    SEQUENCE
                  </button>
                  {replyChannel === "sms" && !aiDraft && !aiRegenerating && (
                    <button onClick={regenerateAiDraft} disabled={aiDraftBusy} className="btn btn-ghost"
                      style={{ fontSize: 10, alignSelf: "flex-end" }} title="Ask the AI setter to draft a reply">
                      ASK AI
                    </button>
                  )}
                  {appliedStageLabel && (
                    <div style={{
                      alignSelf: "flex-end", fontFamily: "'Share Tech Mono', monospace", fontSize: 9,
                      color: "#3a7bd5", padding: "0 4px", whiteSpace: "nowrap", display: "flex", alignItems: "center", gap: 4,
                    }}>
                      TAGGED: {appliedStageLabel}
                      <span
                        onClick={() => { setAppliedStage(null); setAppliedStageLabel(null); }}
                        style={{ cursor: "pointer", color: "#5a6f8f", padding: "0 2px" }}
                        title="Untag — send as a freeform message instead"
                      >
                        ×
                      </span>
                    </div>
                  )}
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

                {seqOpen && (
                  <div className="dg-menu" style={{
                    position: "absolute", bottom: "100%", left: 20, marginBottom: 8,
                    background: "#0d1830", border: "1px solid rgba(58,123,213,0.4)",
                    borderRadius: 12, padding: "10px 0", width: 320, maxHeight: 320, overflowY: "auto",
                    boxShadow: "0 8px 32px rgba(0,0,0,0.6)", zIndex: 500,
                  }}>
                    <div style={{
                      padding: "4px 16px 8px", fontFamily: "'Space Grotesk', sans-serif", fontSize: 12,
                      fontWeight: 600, color: "#f0f4ff", borderBottom: "0.5px solid #1a2540",
                    }}>
                      {seqTitle || "Sequence"}
                    </div>
                    {seqLoading && (
                      <div style={{ padding: "12px 16px", fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52" }}>
                        LOADING...
                      </div>
                    )}
                    {seqError && (
                      <div style={{ padding: "12px 16px", fontSize: 12, color: "#dc3c3c" }}>{seqError}</div>
                    )}
                    {!seqLoading && !seqError && seqSteps.length === 0 && (
                      <div style={{ padding: "12px 16px", fontSize: 12, color: "#5a6f8f" }}>
                        No sequence steps filled in yet — add them in Business Resources → Outreach Templates → SMS Sequence.
                      </div>
                    )}
                    {seqSteps.map((s, i) => (
                      <button key={i} onClick={() => applyStep(s)}
                        style={{
                          display: "block", width: "100%", textAlign: "left",
                          padding: "10px 16px", background: "transparent", border: "none", cursor: "pointer",
                        }}
                        onMouseEnter={e => e.currentTarget.style.background = "#0a1020"}
                        onMouseLeave={e => e.currentTarget.style.background = "transparent"}
                      >
                        <div style={{ fontSize: 12, fontWeight: 600, color: "#c4d0e8" }}>{s.label}</div>
                        <div style={{
                          fontSize: 11, color: "#5a6f8f", marginTop: 2,
                          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                        }}>
                          {s.text}
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div style={{
                padding: "12px 20px", borderTop: "0.5px solid #1a2540",
                textAlign: "center", fontFamily: "'Share Tech Mono', monospace",
                fontSize: 10, letterSpacing: "0.18em",
                color: thread?.disposition === "not_interested" ? "#dc3c3c" : "#14c882",
              }}>
                {thread?.disposition === "not_interested"
                  ? "NOT INTERESTED · CONVERSATION CLOSED"
                  : "APPOINTMENT BOOKED · CONVERSATION CLOSED"}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
