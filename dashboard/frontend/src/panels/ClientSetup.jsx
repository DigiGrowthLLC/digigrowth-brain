// Marketing Setup v2 (2026-11-16): one repeatable checklist per client.
// Steps, phases and the "done" proofs come from the server
// (GET /api/clients/{id}/setup, backend setup_steps.py), so the OS, the
// 10-minute autocheck and the onboarding agent can't drift apart.
// Most steps tick themselves from real data; the rest have a checkbox.
import React, { useState, useEffect, useCallback } from "react";
import { API } from "../api.js";
import ClientBookingSetup from "./ClientBookingSetup.jsx";

const mono = { fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#5a7aa0", lineHeight: 1.55 };
const label = { fontFamily: "'Space Grotesk', sans-serif" };
const GREEN = "#4ade80";
const RED = "#f87171";

async function call(path, opts = {}) {
  const r = await fetch(API(path), { headers: { "Content-Type": "application/json" }, ...opts });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.detail || `Request failed (${r.status})`);
  return d;
}

// ── Cards reused inside steps ───────────────────────────────────────────────

const AUTOSETUP_STEPS = [
  ["client_portal", "Client portal"],
  ["landing_page", "Funnel"],
  ["sms", "Number"],
  ["response_ai", "Text agent"],
  ["automations", "Messages"],
  ["booking", "Booking"],
  ["voice_agent", "Voice agent"],
];
const AUTOSETUP_COLORS = { done: GREEN, skipped: "#5a7aa0", error: RED };

function AutoSetupCard({ clientId, autosetup, onChange }) {
  const [starting, setStarting] = useState(false);
  const [err, setErr] = useState("");
  const state = autosetup?.state;
  const running = state === "running" || starting;
  const steps = autosetup?.steps || {};

  useEffect(() => {
    if (state !== "running") return undefined;
    const t = setInterval(onChange, 5000);
    return () => clearInterval(t);
    // eslint-disable-next-line
  }, [state]);

  const start = async () => {
    setStarting(true);
    setErr("");
    try {
      await call(`/clients/${clientId}/marketing-config/autosetup`, { method: "POST" });
      await new Promise((res) => setTimeout(res, 1500));
      await onChange();
    } catch (e) {
      setErr(e.message);
    } finally {
      setStarting(false);
    }
  };

  const headline = running ? "Running: the funnel takes a few minutes"
    : state === "done" ? `Last run ${new Date(autosetup.finished_at).toLocaleString()}`
    : state === "error" ? `Run failed: ${autosetup.error || "see server logs"}`
    : "Not run yet: runs by itself when the discovery call is marked Closed";

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <div style={{ ...mono, flex: 1 }}>{headline}</div>
        <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={start} disabled={running}>
          {running ? "RUNNING…" : state ? "RE-RUN (FILLS GAPS)" : "RUN AUTO-SETUP"}
        </button>
      </div>
      {err && <div style={{ ...mono, color: RED, marginTop: 6 }}>{err}</div>}
      {Object.keys(steps).length > 0 && (
        <div style={{ display: "grid", gap: 4, marginTop: 8 }}>
          {AUTOSETUP_STEPS.filter(([key]) => steps[key]).map(([key, name]) => (
            <div key={key} style={mono}>
              <span style={{ color: AUTOSETUP_COLORS[steps[key].status] || "#5a7aa0", fontWeight: 700 }}>{steps[key].status.toUpperCase()}</span>{" "}
              <span style={{ color: "#c8d8f0" }}>{name}:</span> {steps[key].detail}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// Meta ad spend cap (backend ad_spend_caps.py): checks spend every 30 min and
// PAUSES the campaigns at the cap. Cap = signed budget - $100 for software.
function AdSpendCapCard({ clientId, hasAdAccount }) {
  const [cap, setCap] = useState(null);
  const [loaded, setLoaded] = useState(false);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ cap: "", start_date: "", campaign_ids: [], enabled: true });
  const [campaigns, setCampaigns] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    const d = await call(`/clients/${clientId}/ad-spend-cap`).catch(() => ({}));
    setCap(d.cap || null);
    setLoaded(true);
  }, [clientId]);
  useEffect(() => { load(); }, [load]);

  const openEdit = async () => {
    setErr("");
    setForm(cap
      ? { cap: String(cap.cap), start_date: cap.start_date || "", campaign_ids: cap.campaign_ids || [], enabled: cap.enabled }
      : { cap: "", start_date: "", campaign_ids: [], enabled: true });
    setEditing(true);
    if (campaigns === null) {
      try { setCampaigns((await call(`/clients/${clientId}/ad-spend-cap/campaigns`)).campaigns || []); }
      catch (e) { setCampaigns([]); setErr(e.message || "Couldn't load campaigns from Meta"); }
    }
  };
  const save = async () => {
    setBusy(true); setErr("");
    try {
      const d = await call(`/clients/${clientId}/ad-spend-cap`, {
        method: "PUT", body: JSON.stringify({ ...form, cap: Number(form.cap), start_date: form.start_date || null }),
      });
      setCap(d.cap); setEditing(false);
      if (d.check_error) setErr(`Saved, but the spend check failed: ${d.check_error}`);
    } catch (e) { setErr(e.message); } finally { setBusy(false); }
  };
  const checkNow = async () => {
    setBusy(true); setErr("");
    try { setCap((await call(`/clients/${clientId}/ad-spend-cap/check`, { method: "POST" })).cap); }
    catch (e) { setErr(e.message); load(); }
    setBusy(false);
  };
  const remove = async () => {
    setBusy(true);
    await fetch(API(`/clients/${clientId}/ad-spend-cap`), { method: "DELETE" });
    setCap(null); setEditing(false); setBusy(false);
  };

  const money = (v) => `$${Number(v || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  const pct = cap && cap.last_spend != null ? Math.min(100, (cap.last_spend / cap.cap) * 100) : 0;
  const headline = !loaded ? "Loading…"
    : !cap ? "Not set: campaigns run until you stop them"
    : !cap.enabled ? "Off: not checking spend"
    : cap.paused_at ? `Paused at the cap ${new Date(cap.paused_at).toLocaleString()}`
    : cap.last_spend != null ? `${money(cap.last_spend)} of ${money(cap.cap)} spent`
    : `Cap ${money(cap.cap)}, not checked yet`;
  const toggleCampaign = (id) => setForm((f) => ({
    ...f, campaign_ids: f.campaign_ids.includes(id) ? f.campaign_ids.filter((x) => x !== id) : [...f.campaign_ids, id],
  }));

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <div style={{ ...mono, flex: 1, color: cap?.paused_at ? RED : "#8aaad0" }}>{headline}</div>
        {!editing && cap && <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={checkNow} disabled={busy}>{busy ? "CHECKING…" : "CHECK NOW"}</button>}
        {!editing && (
          <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={openEdit} disabled={!hasAdAccount || busy}
            title={hasAdAccount ? "" : "Save the ad account ID first (Meta access step)"}>{cap ? "EDIT" : "SET CAP"}</button>
        )}
      </div>
      {cap && cap.enabled && cap.last_spend != null && !editing && (
        <div style={{ height: 4, borderRadius: 2, background: "rgba(58,123,213,0.15)", marginTop: 8, overflow: "hidden" }}>
          <div style={{ width: `${pct}%`, height: "100%", background: cap.paused_at ? RED : pct >= 80 ? "#f0a028" : "#3a7bd5" }} />
        </div>
      )}
      {cap?.paused_at && !editing && <div style={{ ...mono, marginTop: 6 }}>To keep going: EDIT → raise the cap → SAVE, then switch the campaign back on in Ads Manager.</div>}
      {cap && !editing && cap.last_error && <div style={{ ...mono, color: RED, marginTop: 6 }}>Last check failed: {cap.last_error}</div>}
      {editing && (
        <div style={{ display: "grid", gap: 10, marginTop: 10 }}>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <label style={{ ...mono, display: "grid", gap: 3 }}>CAP ($)
              <input className="dg-input" style={{ fontSize: 11, width: 130 }} type="number" min="1" value={form.cap} placeholder="500"
                onChange={(e) => setForm({ ...form, cap: e.target.value })} autoFocus />
            </label>
            <label style={{ ...mono, display: "grid", gap: 3 }}>COUNT SPEND FROM
              <input className="dg-input" style={{ fontSize: 11, width: 160 }} type="date" value={form.start_date}
                onChange={(e) => setForm({ ...form, start_date: e.target.value })} />
            </label>
          </div>
          <div>
            <div style={{ ...mono, marginBottom: 4 }}>CAMPAIGNS (none ticked = the whole ad account)</div>
            {campaigns === null ? <div style={mono}>Loading campaigns from Meta…</div>
              : campaigns.length === 0 ? <div style={mono}>No campaigns found.</div>
              : campaigns.map((c) => (
                <label key={c.id} style={{ ...mono, display: "flex", gap: 8, alignItems: "center", color: "#c8d8f0" }}>
                  <input type="checkbox" checked={form.campaign_ids.includes(c.id)} onChange={() => toggleCampaign(c.id)} />
                  {c.name} <span style={{ color: "#5a7aa0" }}>· {(c.effective_status || c.status || "").toLowerCase()}</span>
                </label>
              ))}
          </div>
          <label style={{ ...mono, display: "flex", gap: 8, alignItems: "center" }}>
            <input type="checkbox" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} />
            Pause the campaigns automatically at the cap
          </label>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            <button className="btn btn-primary" style={{ fontSize: 10 }} onClick={save} disabled={busy || !form.cap}>{busy ? "SAVING…" : "SAVE"}</button>
            <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={() => setEditing(false)} disabled={busy}>CANCEL</button>
            {cap && <button className="btn btn-secondary" style={{ fontSize: 10, marginLeft: "auto" }} onClick={remove} disabled={busy}>REMOVE CAP</button>}
          </div>
        </div>
      )}
      {err && <div style={{ ...mono, color: RED, marginTop: 6 }}>{err}</div>}
    </div>
  );
}

function GhlWebhookUrl({ clientId }) {
  const [url, setUrl] = useState("");
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    call(`/clients/${clientId}/ghl-webhook-url`).then((d) => setUrl(d.url)).catch(() => {});
  }, [clientId]);
  if (!url) return null;
  return (
    <div style={{ display: "flex", gap: 6, marginTop: 6, alignItems: "center" }}>
      <span style={{ ...mono, whiteSpace: "nowrap" }}>GHL webhook:</span>
      <input className="dg-input" readOnly value={url} style={{ fontSize: 10, flex: 1, minWidth: 0 }} onFocus={(e) => e.target.select()} />
      <button className="btn btn-secondary" style={{ fontSize: 9, padding: "3px 8px" }}
        onClick={() => { navigator.clipboard?.writeText(url); setCopied(true); setTimeout(() => setCopied(false), 1500); }}>
        {copied ? "COPIED" : "COPY"}
      </button>
    </div>
  );
}

// ── Step pieces ─────────────────────────────────────────────────────────────

function StepFields({ clientId, fields, config, onSaved }) {
  const [vals, setVals] = useState(() => Object.fromEntries(fields.map((f) => [f.key, String(config?.[f.key] ?? "")])));
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  // String(): numeric fields (campaign goal/length) come back as numbers.
  const dirty = fields.some((f) => String(vals[f.key] ?? "") !== String(config?.[f.key] ?? ""));
  const save = async () => {
    setBusy(true); setMsg("");
    try {
      const body = Object.fromEntries(fields.map((f) => [f.key, String(vals[f.key] ?? "").trim() || null]));
      await call(`/clients/${clientId}/marketing-config`, { method: "PUT", body: JSON.stringify(body) });
      setMsg("Saved");
      await onSaved();
    } catch (e) { setMsg(e.message); }
    setBusy(false);
  };
  return (
    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "flex-end" }}>
      {fields.map((f) => (
        <label key={f.key} style={{ ...mono, display: "grid", gap: 3, flex: "1 1 180px" }}>
          {f.label.toUpperCase()}
          <input className="dg-input" style={{ fontSize: 11 }} value={vals[f.key] || ""} placeholder={f.placeholder}
            onChange={(e) => setVals({ ...vals, [f.key]: e.target.value })} />
        </label>
      ))}
      <button className="btn btn-primary" style={{ fontSize: 10 }} onClick={save} disabled={busy || !dirty}>{busy ? "SAVING…" : "SAVE"}</button>
      {msg && <span style={{ ...mono, color: msg === "Saved" ? GREEN : RED }}>{msg}</span>}
    </div>
  );
}

function ActionButton({ children, onRun, primary }) {
  const [busy, setBusy] = useState(false);
  return (
    <button className={`btn ${primary ? "btn-primary" : "btn-secondary"}`} style={{ fontSize: 10 }} disabled={busy}
      onClick={async () => { setBusy(true); try { await onRun(); } finally { setBusy(false); } }}>
      {busy ? "WORKING…" : children}
    </button>
  );
}

function StepActions({ step, clientId, client, config, setup, reload, onGoTab }) {
  const [result, setResult] = useState(null);
  const [showBooking, setShowBooking] = useState(false);
  const run = (fn) => async () => {
    setResult(null);
    try { setResult({ ok: true, text: await fn() }); } catch (e) { setResult({ ok: false, text: e.message }); }
    await reload();
  };
  const out = result && <div style={{ ...mono, color: result.ok ? "#8fd9bd" : RED, marginTop: 6, whiteSpace: "pre-wrap" }}>{result.text}</div>;

  switch (step.action) {
    case "autosetup":
      return <AutoSetupCard clientId={clientId} autosetup={setup.autosetup} onChange={reload} />;
    case "ad_cap":
      return <AdSpendCapCard clientId={clientId} hasAdAccount={Boolean(config?.meta_ad_account_id)} />;
    case "review":
      return (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {config?.landing_page_url && <a className="btn btn-secondary" style={{ fontSize: 10, textDecoration: "none" }} href={config.landing_page_url} target="_blank" rel="noreferrer">OPEN FUNNEL ↗</a>}
          <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={() => onGoTab("agents")}>AGENTS & MESSAGES</button>
        </div>
      );
    case "agents":
      return <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={() => onGoTab("agents")}>OPEN AGENTS</button>;
    case "portal":
      return client?.portal_url ? <a className="btn btn-secondary" style={{ fontSize: 10, textDecoration: "none" }} href={client.portal_admin_url || client.portal_url} target="_blank" rel="noreferrer">OPEN THEIR PORTAL ↗</a> : null;
    case "meta_sync":
      return (
        <div>
          <ActionButton onRun={run(async () => `Synced ${(await call(`/clients/${clientId}/marketing-config/sync-meta-ads`, { method: "POST" })).days_synced} day(s) of ad data`)}>SYNC NOW</ActionButton>
          {out}
        </div>
      );
    case "booking":
    case "booking_autofill":
      return (
        <div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {step.action === "booking_autofill" && (
              <ActionButton onRun={run(async () => (await call(`/clients/${clientId}/setup/booking-autofill`, { method: "POST" })).detail)}>AUTOFILL BOOKING</ActionButton>
            )}
            <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={() => setShowBooking((s) => !s)}>
              {showBooking ? "HIDE BOOKING SETUP" : "OPEN BOOKING SETUP"}
            </button>
          </div>
          {out}
          {step.action === "booking_autofill" && <GhlWebhookUrl clientId={clientId} />}
          {showBooking && <div style={{ marginTop: 10 }}><ClientBookingSetup clientId={clientId} /></div>}
        </div>
      );
    case "lead_form":
      return (
        <div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            <ActionButton primary onRun={run(async () => {
              const d = await call(`/clients/${clientId}/setup/instant-form`, { method: "POST" });
              return `Form ${d.form_id} created. Thank-you button → ${d.booking_url}`;
            })}>{setup.meta_form_id ? "CREATE A NEW FORM" : "CREATE FORM"}</ActionButton>
            <ActionButton onRun={run(async () => {
              const r = await fetch(API(`/clients/${clientId}/marketing-config/connect-lead-ads`), { method: "POST" });
              const d = await r.json().catch(() => ({}));
              if (!r.ok) throw new Error(d.detail || "Couldn't connect the relay");
              return "Lead relay connected";
            })}>CONNECT RELAY</ActionButton>
            <ActionButton onRun={run(async () => {
              await call(`/clients/${clientId}/voice-agent/consent-live?live=true`, { method: "POST" });
              return "Consent stamped: Meta leads from now on can be voice-called";
            })}>{setup.consent_since ? "RE-STAMP CONSENT" : "CONSENT LINE IS LIVE"}</ActionButton>
          </div>
          <div style={{ ...mono, marginTop: 6 }}>
            {setup.meta_form_id ? `Form ID ${setup.meta_form_id}` : "No form built yet"}
            {" · "}{setup.consent_since ? `consent stamped ${new Date(setup.consent_since).toLocaleDateString()}` : "consent not stamped"}
            {setup.lead_ads_error && <span style={{ color: RED }}> · relay error: {setup.lead_ads_error}</span>}
          </div>
          {out}
        </div>
      );
    case "test": {
      const t = setup.setup_test || {};
      return (
        <div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            <ActionButton primary onRun={run(async () => (await call(`/clients/${clientId}/setup/test`, { method: "POST" })).steps.join("\n"))}>RUN TEST</ActionButton>
            <ActionButton onRun={run(async () => (await call(`/clients/${clientId}/setup/test/cleanup`, { method: "POST" })).cleanup.join(", "))}>CLEAN UP</ActionButton>
          </div>
          {!result && t.ran_at && (
            <div style={{ ...mono, marginTop: 6 }}>
              Last test {new Date(t.ran_at).toLocaleString()}{t.cleaned_at ? `, cleaned up ${new Date(t.cleaned_at).toLocaleString()}` : ", not cleaned up yet"}
            </div>
          )}
          {out}
        </div>
      );
    }
    default:
      return null;
  }
}

function StepRow({ step, open, onToggle, onTick, ...rest }) {
  const color = step.done ? GREEN : "#3a5a80";
  return (
    <div style={{ borderRadius: 8, background: open ? "rgba(58,123,213,0.06)" : "rgba(255,255,255,0.02)", border: "1px solid rgba(58,123,213,0.08)" }}>
      <div onClick={onToggle} style={{ display: "flex", alignItems: "center", gap: 10, padding: "9px 12px", cursor: "pointer" }}>
        <span style={{ width: 18, height: 18, borderRadius: "50%", flexShrink: 0, display: "grid", placeItems: "center",
          border: `1.5px solid ${color}`, background: step.done ? "rgba(74,222,128,0.15)" : "transparent", color, fontSize: 11 }}>
          {step.done ? "✓" : ""}
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ ...label, fontSize: 12.5, fontWeight: 600, color: step.done ? "#8fb8a0" : "#d0e0f5" }}>{step.title}</div>
          <div style={{ ...mono, fontSize: 9.5, marginTop: 1, color: step.proof ? "#6fbf95" : "#4a6a90" }}>
            {step.proof || (step.ticked ? "Marked done by hand" : "")}
          </div>
        </div>
        <span style={{ ...mono, fontSize: 12, color: "#3a5a80" }}>{open ? "▾" : "▸"}</span>
      </div>
      {open && (
        <div style={{ padding: "0 12px 12px 40px", display: "grid", gap: 10 }}>
          <div style={{ fontSize: 12, color: "#9fb4d4", lineHeight: 1.55 }}>{step.how}</div>
          {step.link && <a href={step.link} target="_blank" rel="noreferrer" style={{ ...mono, color: "#6ab0ff" }}>{step.linkLabel || step.link} ↗</a>}
          {step.fields && <StepFields clientId={rest.clientId} fields={step.fields} config={rest.config} onSaved={rest.reload} />}
          <StepActions step={step} {...rest} />
          {!step.proof && (
            <label style={{ ...mono, display: "flex", alignItems: "center", gap: 6, cursor: "pointer", width: "fit-content" }}>
              <input type="checkbox" checked={step.ticked} onChange={(e) => onTick(e.target.checked)} />
              Mark done (or not needed for this client)
            </label>
          )}
        </div>
      )}
    </div>
  );
}

// What we do for this client (backend client_services.py). The client picks
// these on their portal intake; Dylan can correct them here. Only the steps
// for these services show below and in the client's portal.
function ServicesCard({ clientId, setup, onChange, portalUrl }) {
  const [busy, setBusy] = useState(false);
  const [showAnswers, setShowAnswers] = useState(false);
  const have = setup.services_shown || [];
  const save = async (path, body) => {
    setBusy(true);
    try { onChange(await call(path, { method: "PUT", body: JSON.stringify(body) })); } finally { setBusy(false); }
  };
  const toggle = (id) => save(`/clients/${clientId}/setup/services`,
    { services: have.includes(id) ? have.filter((x) => x !== id) : [...have, id] });
  const answers = setup.intake_answers || {};
  const qs = (setup.intake_questions || []).filter((q) => answers[q.key] !== undefined);
  const source = setup.intake_pending ? "Waiting on the client's portal intake"
    : setup.services_from === "intake" ? "Picked by the client on their portal intake"
    : setup.services_from === "set by Dylan" ? "Set by you" : "Package defaults (client hasn't answered the intake)";
  return (
    <div style={{ padding: "10px 12px", borderRadius: 8, border: "1px solid rgba(58,123,213,0.12)", background: "rgba(255,255,255,0.02)", display: "grid", gap: 8 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 8, flexWrap: "wrap" }}>
        <span style={{ ...label, fontSize: 11, fontWeight: 700, letterSpacing: "0.08em", color: "#9cc4f5" }}>SERVICES</span>
        <span style={{ ...mono, fontSize: 9.5 }}>{source}</span>
        <span style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
          {qs.length > 0 && (
            <button className="btn btn-secondary" style={{ fontSize: 9.5 }} onClick={() => setShowAnswers((v) => !v)}>
              {showAnswers ? "HIDE ANSWERS" : "INTAKE ANSWERS"}
            </button>
          )}
          <button className="btn btn-secondary" style={{ fontSize: 9.5 }} disabled={busy}
            title={setup.intake_pending ? "Let the client into their portal without answering" : "Their portal opens on the intake again, answers prefilled"}
            onClick={() => save(`/clients/${clientId}/setup/intake`, { ask: !setup.intake_pending })}>
            {setup.intake_pending ? "SKIP INTAKE" : "ASK CLIENT AGAIN"}
          </button>
        </span>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
        {(setup.service_options || []).map((o) => {
          const on = have.includes(o.id);
          return (
            <button key={o.id} disabled={busy} title={o.hint} onClick={() => toggle(o.id)} style={{
              ...label, fontSize: 11, fontWeight: 600, padding: "4px 10px", borderRadius: 999, cursor: "pointer",
              border: on ? "1px solid rgba(74,222,128,0.5)" : "1px solid rgba(58,123,213,0.2)",
              background: on ? "rgba(74,222,128,0.12)" : "transparent", color: on ? "#bff0d0" : "#5a7aa0",
            }}>{on ? "✓ " : ""}{o.label}</button>
          );
        })}
      </div>
      {setup.intake_pending && (
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", padding: "8px 10px", borderRadius: 6,
          background: "rgba(240,160,40,0.1)", border: "1px solid rgba(240,160,40,0.35)" }}>
          <span style={{ ...label, fontSize: 12, color: "#f0c078" }}>
            Questionnaire is ON: their portal opens on it until they answer.
          </span>
          {portalUrl && (
            <a href={portalUrl} target="_blank" rel="noreferrer" className="btn btn-secondary" style={{ fontSize: 9.5, marginLeft: "auto", textDecoration: "none" }}>
              OPEN PORTAL ↗
            </a>
          )}
        </div>
      )}
      {showAnswers && (
        <div style={{ display: "grid", gap: 4 }}>
          {qs.map((q) => (
            <div key={q.key} style={{ fontSize: 11.5, color: "#9fb4d4" }}>
              <span style={{ color: "#5a7aa0" }}>{q.label}</span>{" "}
              {Array.isArray(answers[q.key]) ? answers[q.key].join(", ") : answers[q.key]}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ClientSetup({ clientId, onGoTab }) {
  const [setup, setSetup] = useState(null);
  const [config, setConfig] = useState(null);
  const [client, setClient] = useState(null);
  const [open, setOpen] = useState(null);
  const [showDone, setShowDone] = useState(false);
  const [copied, setCopied] = useState(false);
  const [err, setErr] = useState("");

  const reload = useCallback(async () => {
    try {
      const [s, c, cl] = await Promise.all([
        call(`/clients/${clientId}/setup`),
        call(`/clients/${clientId}/marketing-config`),
        call(`/clients/${clientId}`),
      ]);
      setSetup(s); setConfig(c); setClient(cl);
    } catch (e) { setErr(e.message); }
  }, [clientId]);
  useEffect(() => { reload(); }, [reload]);

  if (!setup) return <div style={{ ...mono, padding: 16 }}>{err || "LOADING…"}</div>;

  const tick = async (id, done) => {
    setSetup(await call(`/clients/${clientId}/setup/steps/${id}`, { method: "PUT", body: JSON.stringify({ done }) }));
  };
  const setPackage = async (pkg) => {
    setSetup(await call(`/clients/${clientId}/setup/package`, { method: "PUT", body: JSON.stringify({ package: pkg }) }));
  };
  const pct = Math.round((setup.done / Math.max(1, setup.total)) * 100);
  // Long-lead steps (needs someone else's approval or waits on time) go first:
  // listed above the phases while open, and "Next" points at them (Dylan, 2026-11-25).
  const longLead = setup.steps.filter((s) => s.long_lead && !s.done);
  const next = longLead[0] || setup.steps.find((s) => !s.done);
  const rowProps = { clientId, client, config, setup, reload, onGoTab };

  return (
    <div style={{ padding: "14px 16px", display: "grid", gap: 14 }}>
      {/* Header: progress, package, next step, client ask */}
      <div style={{ display: "flex", gap: 14, alignItems: "center", flexWrap: "wrap" }}>
        <div style={{ flex: "1 1 260px" }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
            <span style={{ ...label, fontSize: 20, fontWeight: 700, color: "#e8f0ff" }}>{setup.done}/{setup.total}</span>
            <span style={{ ...mono }}>steps done</span>
          </div>
          <div style={{ height: 5, borderRadius: 3, background: "rgba(58,123,213,0.15)", marginTop: 6, overflow: "hidden" }}>
            <div style={{ width: `${pct}%`, height: "100%", background: pct === 100 ? GREEN : "#3a7bd5" }} />
          </div>
          {next && (
            <div style={{ ...mono, marginTop: 6 }}>
              Next: <span style={{ color: "#9cc4f5", cursor: "pointer" }} onClick={() => setOpen(next.id)}>{next.title}</span>
            </div>
          )}
        </div>
        <div style={{ display: "flex", borderRadius: 999, border: "1px solid rgba(58,123,213,0.25)", overflow: "hidden" }}>
          {[["growth", "Growth"], ["foundations", "Foundations"]].map(([k, l]) => (
            <button key={k} onClick={() => setPackage(k)} style={{
              ...label, fontSize: 11, fontWeight: 600, padding: "5px 12px", border: "none", cursor: "pointer",
              background: setup.package === k ? "rgba(58,123,213,0.25)" : "transparent",
              color: setup.package === k ? "#cfe3ff" : "#5a7aa0",
            }}>{l}</button>
          ))}
        </div>
        {setup.client_ask && (
          <button className="btn btn-secondary" style={{ fontSize: 10 }} title={setup.client_ask}
            onClick={() => { navigator.clipboard?.writeText(setup.client_ask); setCopied(true); setTimeout(() => setCopied(false), 1500); }}>
            {copied ? "COPIED" : "COPY CLIENT ASK"}
          </button>
        )}
        <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={() => setShowDone((s) => !s)}>
          {showDone ? "HIDE DONE" : "SHOW DONE"}
        </button>
      </div>

      <ServicesCard clientId={clientId} setup={setup} onChange={setSetup} portalUrl={client?.portal_admin_url || client?.portal_url} />

      {longLead.length > 0 && (
        <div style={{ padding: "10px 12px", borderRadius: 8, border: "1px solid rgba(240,160,40,0.35)", background: "rgba(240,160,40,0.06)" }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 6, flexWrap: "wrap" }}>
            <span style={{ ...label, fontSize: 11, fontWeight: 700, letterSpacing: "0.08em", color: "#f0c078" }}>START THESE FIRST</span>
            <span style={{ ...mono, fontSize: 9.5, color: "#a08050" }}>· Needs someone else's approval or waits on time, so it can't be rushed last minute</span>
          </div>
          <div style={{ display: "grid", gap: 6 }}>
            {longLead.map((s) => (
              <div key={s.id}>
                <StepRow step={s} open={open === s.id} onToggle={() => setOpen(open === s.id ? null : s.id)}
                  onTick={(v) => tick(s.id, v)} {...rowProps} />
                <div style={{ ...mono, fontSize: 9.5, color: "#c09a60", padding: "3px 12px 0 40px" }}>{s.long_lead}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {setup.phases.map((ph) => {
        const steps = setup.steps.filter((s) => s.phase === ph.id);
        if (!steps.length) return null;
        const doneN = steps.filter((s) => s.done).length;
        // Open long-lead steps already show in "Start these first".
        const visible = (showDone ? steps : steps.filter((s) => !s.done || open === s.id))
          .filter((s) => !(s.long_lead && !s.done));
        return (
          <div key={ph.id}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 6 }}>
              <span style={{ ...label, fontSize: 11, fontWeight: 700, letterSpacing: "0.08em", color: doneN === steps.length ? GREEN : "#9cc4f5" }}>
                {ph.title.toUpperCase()}
              </span>
              <span style={mono}>{doneN}/{steps.length}</span>
              {ph.note && <span style={{ ...mono, fontSize: 9.5, color: "#3a5a80" }}>· {ph.note}</span>}
            </div>
            <div style={{ display: "grid", gap: 6 }}>
              {visible.map((s) => (
                <StepRow key={s.id} step={s} open={open === s.id} onToggle={() => setOpen(open === s.id ? null : s.id)}
                  onTick={(v) => tick(s.id, v)} {...rowProps} />
              ))}
              {!visible.length && (doneN === steps.length
                ? <div style={{ ...mono, color: "#3a6a50" }}>All done.</div>
                : <div style={{ ...mono, color: "#a08050" }}>What's left here is under Start these first.</div>)}
            </div>
          </div>
        );
      })}
      {err && <div style={{ ...mono, color: RED }}>{err}</div>}
    </div>
  );
}
