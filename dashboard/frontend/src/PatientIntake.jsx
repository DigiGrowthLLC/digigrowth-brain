import React, { useEffect, useRef, useState } from "react";

// Patient intake section of a client prospect's contact card (backend
// patient_intake.py). Shared by the OS ContactCard and the client portal's
// LeadDrawer; `base` is the intake URL for whichever side is calling:
//   OS:     /api/contact-cards/<id>/intake
//   portal: /portal-api/<token>/leads/<id>/intake
// Filled automatically from the lead form, booking form, texts, DMs and AI
// call transcripts; anything typed here is kept and never overwritten.

const SOURCE_COLOR = {
  "Lead form": "#6ab0ff", "Booking form": "#a080f0", "Text messages": "#14c882",
  "DMs": "#e07ad0", "Phone call": "#f0a028", "Notes": "#8aaad0", "Entered by hand": "#d0e8ff",
};

function ago(iso) {
  if (!iso) return "";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 90) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export default function PatientIntake({ base }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState({});
  const [busy, setBusy] = useState(false);
  const pollRef = useRef(null);

  const load = () => fetch(base)
    .then(async (r) => { if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || "Couldn't load intake"); return r.json(); })
    .then((d) => { setData(d); setErr(""); return d; })
    .catch((e) => { setErr(e.message); return null; });

  useEffect(() => {
    let tries = 0;
    load().then((d) => {
      // First open of a prospect: the server reads their conversations in the
      // background; check back a few times so the card fills in by itself.
      if (d?.pending) {
        pollRef.current = setInterval(async () => {
          tries += 1;
          const n = await load();
          if (!n?.pending || tries >= 8) clearInterval(pollRef.current);
        }, 4000);
      }
    });
    return () => clearInterval(pollRef.current);
  }, [base]); // eslint-disable-line react-hooks/exhaustive-deps

  const startEdit = () => {
    const d = {};
    for (const f of data.field_defs) d[f.key] = data.fields?.[f.key]?.value || "";
    setDraft(d);
    setEditing(true);
  };

  const save = async () => {
    setBusy(true);
    const changes = {};
    for (const f of data.field_defs) {
      if ((draft[f.key] || "") !== (data.fields?.[f.key]?.value || "")) changes[f.key] = draft[f.key] || "";
    }
    if (Object.keys(changes).length) {
      const r = await fetch(base, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(changes) });
      if (r.ok) setData({ ...(await r.json()), pending: false }); else setErr("Couldn't save.");
    }
    setBusy(false);
    setEditing(false);
  };

  const refresh = async () => {
    setBusy(true);
    const r = await fetch(`${base}/refresh`, { method: "POST" });
    if (r.ok) setData(await r.json()); else setErr("Couldn't refresh.");
    setBusy(false);
  };

  const label = { fontSize: 11, color: "#6a8ab0", marginBottom: 2 };
  const filled = data ? data.field_defs.filter((f) => data.fields?.[f.key]?.value) : [];
  const empty = data ? data.field_defs.filter((f) => !data.fields?.[f.key]?.value) : [];

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
        <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 13.5, fontWeight: 600, color: "#e8f0ff", flex: 1 }}>Patient intake</div>
        {data && !editing && (
          <>
            <button type="button" onClick={refresh} disabled={busy} title="Re-read their forms, texts, DMs and calls now"
              style={{ background: "none", border: "none", color: "#6ab0ff", cursor: busy ? "wait" : "pointer", fontSize: 12, padding: 0 }}>
              {busy ? "Reading…" : "Refresh"}
            </button>
            <button type="button" onClick={startEdit}
              style={{ background: "none", border: "none", color: "#6ab0ff", cursor: "pointer", fontSize: 12, padding: 0 }}>Edit</button>
          </>
        )}
      </div>

      <div className="glass-card-sm" style={{ padding: "12px 14px", display: "flex", flexDirection: "column", gap: 10 }}>
        {!data && !err && <div style={{ fontSize: 12, color: "#5a7aa0" }}>Loading…</div>}
        {err && <div style={{ fontSize: 12, color: "#f06060" }}>{err}</div>}

        {data && editing && (
          <>
            {data.field_defs.map((f) => (
              <div key={f.key}>
                <div style={label}>{f.label}</div>
                <input className="dg-input" value={draft[f.key] || ""} onChange={(e) => setDraft((d) => ({ ...d, [f.key]: e.target.value }))}
                  style={{ width: "100%", fontSize: 12.5, boxSizing: "border-box" }} />
              </div>
            ))}
            <div style={{ fontSize: 11, color: "#5a7aa0", lineHeight: 1.5 }}>What you type is kept as-is. Clear a field to let it fill in automatically again.</div>
            <div style={{ display: "flex", gap: 8 }}>
              <button type="button" className="btn btn-secondary" style={{ flex: 1 }} onClick={() => setEditing(false)} disabled={busy}>Cancel</button>
              <button type="button" className="btn btn-primary" style={{ flex: 1 }} onClick={save} disabled={busy}>{busy ? "Saving…" : "Save intake"}</button>
            </div>
          </>
        )}

        {data && !editing && (
          <>
            {data.summary && <div style={{ fontSize: 13, color: "#d0e8ff", lineHeight: 1.5 }}>{data.summary}</div>}
            {filled.map((f) => {
              const v = data.fields[f.key];
              return (
                <div key={f.key}>
                  <div style={{ ...label, display: "flex", gap: 6, alignItems: "center" }}>
                    {f.label}
                    {v.source && <span style={{ fontSize: 10, color: SOURCE_COLOR[v.source] || "#8aaad0", opacity: 0.85 }}>· {v.source}</span>}
                  </div>
                  <div style={{ fontSize: 13, color: "#f0f4ff", lineHeight: 1.45, whiteSpace: "pre-wrap" }}>{v.value}</div>
                </div>
              );
            })}
            {filled.length === 0 && (
              <div style={{ fontSize: 12.5, color: "#7f9cc4", lineHeight: 1.5 }}>
                {data.pending ? "Reading their forms and conversations…" : "Nothing yet. This fills in from their lead form, booking answers, texts, DMs and AI calls, or add it yourself with Edit."}
              </div>
            )}
            {filled.length > 0 && empty.length > 0 && (
              <div style={{ fontSize: 11.5, color: "#5a7aa0" }}>Not known yet: {empty.map((f) => f.label.toLowerCase()).join(", ")}</div>
            )}
            {data.extracted_at && <div style={{ fontSize: 10.5, color: "#4a6a90" }}>Updated from their conversations {ago(data.extracted_at)}</div>}
            {data.error && <div style={{ fontSize: 11, color: "#f0a028" }}>Last automatic update failed: {data.error}</div>}
          </>
        )}
      </div>
    </div>
  );
}
