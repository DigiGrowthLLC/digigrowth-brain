import React, { useEffect, useState } from "react";
import { API } from "../api.js";
import ContactLink from "../ContactLink.jsx";

// Clients → Details → Booking: DigiGrowth Booking (our own Calendly
// replacement — backend/booking_engine.py + routers/booking.py).

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const LOCATIONS = [
  { value: "in_person", label: "In person" },
  { value: "google_meet", label: "Google Meet (video)" },
  { value: "phone", label: "Phone call" },
];
const REFUNDS = [
  { value: "24h", label: "Refund if cancelled 24h+ ahead" },
  { value: "always", label: "Always refund on cancel" },
  { value: "none", label: "No refunds" },
];
const US_TIMEZONES = [
  ["America/New_York", "Eastern (New York)"],
  ["America/Chicago", "Central (Chicago)"],
  ["America/Denver", "Mountain (Denver)"],
  ["America/Phoenix", "Mountain, no DST (Phoenix)"],
  ["America/Los_Angeles", "Pacific (Los Angeles)"],
  ["America/Anchorage", "Alaska (Anchorage)"],
  ["Pacific/Honolulu", "Hawaii (Honolulu)"],
];
const STATUS_COLORS = { confirmed: "#14c882", pending_payment: "#f0a028", cancelled: "#e05a5a" };

const label = { fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#5a7aa0", letterSpacing: "0.08em", textTransform: "uppercase", display: "block", marginBottom: 4 };
const h = { fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600, fontSize: 14, color: "#d0e8ff", margin: "0 0 10px" };
const note = { fontSize: 11.5, color: "#6f88ad", lineHeight: 1.5 };
const row = { display: "flex", gap: 10, flexWrap: "wrap", alignItems: "flex-end" };

async function call(path, opts = {}) {
  const r = await fetch(API(path), { headers: { "Content-Type": "application/json" }, ...opts });
  const body = await r.json().catch(() => null);
  if (!r.ok) throw new Error((body && body.detail) || `Request failed (${r.status})`);
  return body;
}

function Section({ title, children, right }) {
  return (
    <div className="glass-card-sm" style={{ padding: 16, marginBottom: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h4 style={h}>{title}</h4>{right}
      </div>
      {children}
    </div>
  );
}

function Field({ name, children, width }) {
  return <label style={{ width: width || "auto", flex: width ? "0 0 auto" : 1, minWidth: 120 }}><span style={label}>{name}</span>{children}</label>;
}

const BOOKING_TABS = [["overview", "Overview"], ["schedule", "Schedule"], ["visits", "Visits & payments"], ["page", "Booking page"]];

const dollars = (c) => (c == null || c === "" ? "" : (c / 100).toString());
const cents = (d) => (d === "" || d == null ? null : Math.round(parseFloat(d) * 100));
const t5 = (t) => (t || "").slice(0, 5);

export default function ClientBookingSetup({ clientId }) {
  const [data, setData] = useState(null);
  const [google, setGoogle] = useState(null);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState(null);
  const [drafting, setDrafting] = useState(false);
  const [tab, setTab] = useState("overview");

  const load = async () => {
    try { setData(await call(`/clients/${clientId}/booking`)); } catch (e) { setErr(e.message); }
  };
  useEffect(() => {
    load();
    call("/booking/google").then(setGoogle).catch((e) => setGoogle({ ok: false, error: e.message, calendars: [] }));
    // eslint-disable-next-line
  }, [clientId]);

  const run = async (fn, okMsg) => {
    setBusy(true); setErr(""); setMsg("");
    try { const r = await fn(); if (r && r.settings) setData(r); if (okMsg) setMsg(okMsg); return r; }
    catch (e) { setErr(e.message); }
    finally { setBusy(false); }
  };

  // eslint-disable-next-line react-hooks/rules-of-hooks
  useEffect(() => {
    if (!data || !data.page_autofill_running) return undefined;
    const t = setTimeout(load, 4000);
    return () => clearTimeout(t);
    // eslint-disable-next-line
  }, [data]);

  if (!data) return <div style={note}>{err || "Loading booking setup…"}</div>;
  const s = data.settings;
  const save = (patch, okMsg = "Saved") => run(() => call(`/clients/${clientId}/booking`, { method: "PUT", body: JSON.stringify(patch) }), okMsg);

  return (
    <div style={{ marginTop: 8 }}>
      {(err || msg) && (
        <div style={{ marginBottom: 10, fontSize: 12, color: err ? "#ff8a8a" : "#8fd9bd" }}>{err || msg}</div>
      )}

      {draft && <AutofillReview draft={draft} data={data} busy={busy}
        onApply={async (body) => { const r = await run(() => call(`/clients/${clientId}/booking/autofill/apply`, { method: "POST", body: JSON.stringify(body) }), "Applied. Review the Schedule and Visits tabs, then check availability."); if (r) setDraft(null); }}
        onClose={() => setDraft(null)} />}

      {/* Status header: live/off, what's left, the link, and the two main actions. */}
      {(() => {
        const checks = [
          { label: "Calendar", ok: Boolean(s.calendar_id), tab: "schedule" },
          { label: "Hours", ok: data.hours.length > 0, tab: "schedule" },
          { label: "Visit type", ok: data.event_types.some((e) => e.active), tab: "visits" },
          ...(data.event_types.some((e) => e.active && e.price_cents > 0)
            ? [{ label: "Stripe", ok: Boolean(s.stripe_charges_enabled), tab: "visits" }] : []),
        ];
        const ready = checks.every((c) => c.ok);
        return (
          <div className="glass-card-sm" style={{ padding: "18px 20px", marginBottom: 14,
            borderLeft: `3px solid ${s.enabled ? "#14c882" : ready ? "#3a7bd5" : "#f0a028"}` }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
              <span style={{ display: "inline-flex", alignItems: "center", gap: 7, padding: "4px 12px", borderRadius: 999,
                fontFamily: "'Share Tech Mono', monospace", fontSize: 10.5, letterSpacing: "0.1em",
                color: s.enabled ? "#14c882" : "#f0a028", background: s.enabled ? "rgba(20,200,130,0.1)" : "rgba(240,160,40,0.1)",
                border: `1px solid ${s.enabled ? "rgba(20,200,130,0.3)" : "rgba(240,160,40,0.3)"}` }}>
                <span style={{ width: 7, height: 7, borderRadius: "50%", background: s.enabled ? "#14c882" : "#f0a028" }} />
                {s.enabled ? "LIVE" : "OFF"}
              </span>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", flex: 1 }}>
                {checks.map((c) => (
                  <button key={c.label} onClick={() => setTab(c.tab)} title={c.ok ? "Done" : "Not set yet"}
                    style={{ cursor: "pointer", fontSize: 11.5, padding: "3px 10px", borderRadius: 999,
                      border: `1px solid ${c.ok ? "rgba(20,200,130,0.25)" : "rgba(240,160,40,0.35)"}`,
                      background: "transparent", color: c.ok ? "#8fd9bd" : "#f0c078" }}>
                    {c.ok ? "✓" : "○"} {c.label}
                  </button>
                ))}
              </div>
              <button className="btn btn-secondary" style={{ fontSize: 10.5 }} disabled={drafting || busy} onClick={async () => {
                setDrafting(true); setErr(""); setMsg(""); setDraft(null);
                try { setDraft(await call(`/clients/${clientId}/booking/autofill/preview`, { method: "POST" })); }
                catch (e) { setErr(e.message); }
                finally { setDrafting(false); }
              }}>{drafting ? "READING CLIENT INFO…" : "✨ AUTO-FILL"}</button>
              <button className={s.enabled ? "btn btn-secondary" : "btn btn-primary"} style={{ fontSize: 10.5 }} disabled={busy || (!s.enabled && !ready)}
                title={!s.enabled && !ready ? "Finish the items on the left first" : ""}
                onClick={() => save({ enabled: !s.enabled }, s.enabled ? "Booking turned off (funnel falls back to Calendly)" : "Booking is live")}>
                {s.enabled ? "TURN OFF" : "TURN ON"}
              </button>
            </div>
            <div style={{ display: "flex", gap: 6, marginTop: 12, alignItems: "center", flexWrap: "wrap" }}>
              <input className="dg-input" readOnly value={data.public_url} style={{ flex: "1 1 320px", fontSize: 12 }} onFocus={(e) => e.target.select()} />
              <button className="btn btn-secondary" style={{ fontSize: 10.5 }} onClick={() => { navigator.clipboard?.writeText(data.public_url); setMsg("Link copied"); }}>COPY</button>
              <a className="btn btn-secondary" style={{ fontSize: 10.5, textDecoration: "none" }} href={data.public_url} target="_blank" rel="noreferrer">OPEN ↗</a>
            </div>
            <div style={{ ...note, marginTop: 8 }}>
              {s.enabled
                ? "Live: the funnel's Book button, the client portal and the AI agents all use this link."
                : ready ? "Everything's set. Check availability on the Overview tab, then Turn on."
                : "The link won't open for patients until it's turned on."}
              {data.funnel_urls.length > 0 && <> Funnel pages: {data.funnel_urls.map((u) => <a key={u} href={u} target="_blank" rel="noreferrer" style={{ color: "#6ab0ff", marginRight: 8 }}>{u.split("/lp/")[1]}</a>)}</>}
            </div>
          </div>
        );
      })()}

      <div style={{ display: "flex", gap: 4, marginBottom: 14, borderBottom: "1px solid rgba(58,123,213,0.12)", overflowX: "auto" }}>
        {BOOKING_TABS.map(([id, name]) => (
          <button key={id} onClick={() => setTab(id)} style={{
            background: "none", border: "none", cursor: "pointer", padding: "9px 14px", whiteSpace: "nowrap",
            fontFamily: "'Space Grotesk', sans-serif", fontSize: 13, fontWeight: 600,
            color: tab === id ? "#6ab0ff" : "#5a7aa0",
            borderBottom: `2px solid ${tab === id ? "#3a7bd5" : "transparent"}`, marginBottom: -1,
          }}>{name}</button>
        ))}
      </div>

      {tab === "overview" && (
        <>
          <FunnelCard funnel={data.funnel} />
          <PreviewSection data={data} clientId={clientId} />
          <BookingsSection clientId={clientId} />
        </>
      )}
      {tab === "schedule" && (
        <>
          <CalendarSection data={data} google={google} save={save} busy={busy} />
          <HoursSection data={data} clientId={clientId} run={run} busy={busy} />
          <OverridesSection data={data} clientId={clientId} run={run} busy={busy} />
        </>
      )}
      {tab === "visits" && (
        <>
          <EventTypesSection data={data} clientId={clientId} run={run} reload={load} busy={busy} />
          <PaymentsSection data={data} clientId={clientId} save={save} run={run} reload={load} busy={busy} />
        </>
      )}
      {tab === "page" && (
        <>
          <Section title="Link and look">
            <div style={row}>
              <Field name="Link name">
                <input className="dg-input" defaultValue={s.booking_slug} onBlur={(e) => e.target.value !== s.booking_slug && save({ booking_slug: e.target.value })} />
              </Field>
              <Field name="Button color" width={110}>
                <input className="dg-input" type="color" defaultValue={s.accent_color} onBlur={(e) => save({ accent_color: e.target.value })} style={{ height: 34, padding: 2 }} />
              </Field>
            </div>
          </Section>
          <PageDetailsSection data={data} clientId={clientId} save={save} run={run} busy={busy} />
        </>
      )}
    </div>
  );
}

function AutofillReview({ draft, data, busy, onApply, onClose }) {
  const ev = draft.event_type || {};
  const hasHours = (draft.hours || []).length > 0;
  const existing = data.event_types;
  const [useTz, setUseTz] = useState(!!draft.timezone && draft.timezone !== data.settings.timezone);
  const [useHours, setUseHours] = useState(hasHours);
  const [useEvent, setUseEvent] = useState(true);
  const [target, setTarget] = useState(existing.length === 1 ? String(existing[0].id) : "");
  const fmtT = (t) => { const [hh, mm] = t.split(":").map(Number); return `${((hh + 11) % 12) + 1}:${String(mm).padStart(2, "0")} ${hh < 12 ? "AM" : "PM"}`; };
  const byDay = WEEKDAYS.map((d, i) => [d, (draft.hours || []).filter((x) => x.weekday === i)]);
  const loc = ev.location_type === "in_person" ? (ev.location_text || "In person (no address found)") : ev.location_type === "google_meet" ? "Google Meet" : "Phone call";
  const box = { display: "flex", gap: 10, alignItems: "flex-start", padding: "10px 0", borderTop: "1px solid rgba(58,123,213,0.12)" };
  return (
    <div className="glass-card-sm" style={{ padding: 16, marginBottom: 12, border: "1px solid rgba(106,176,255,0.35)" }}>
      <h4 style={h}>Auto-fill draft (nothing saved yet)</h4>
      <div style={{ ...note, marginBottom: 6 }}>From: {(draft.sources_used || []).join(" · ")}</div>

      <div style={box}>
        <input type="checkbox" checked={useTz} disabled={!draft.timezone} onChange={(e) => setUseTz(e.target.checked)} />
        <div><div style={{ fontSize: 13, color: "#d0e8ff", fontWeight: 600 }}>Timezone</div>
          <div style={note}>{draft.timezone ? (US_TIMEZONES.find((t) => t[0] === draft.timezone) || [0, draft.timezone])[1] : "Not found"}{draft.timezone && draft.timezone === data.settings.timezone ? " (already set)" : ""}</div></div>
      </div>

      <div style={box}>
        <input type="checkbox" checked={useHours} disabled={!hasHours} onChange={(e) => setUseHours(e.target.checked)} />
        <div style={{ flex: 1 }}><div style={{ fontSize: 13, color: "#d0e8ff", fontWeight: 600 }}>New patient hours {hasHours && data.hours.length > 0 && <span style={{ color: "#f0a028", fontWeight: 400 }}>(replaces current hours)</span>}</div>
          {hasHours ? byDay.map(([d, blocks]) => (
            <div key={d} style={{ ...note, display: "flex", gap: 8 }}><span style={{ width: 34, color: "#9cc4f5" }}>{d}</span>{blocks.length ? blocks.map((b) => `${fmtT(b.start)} to ${fmtT(b.end)}`).join(", ") : "Closed"}</div>
          )) : <div style={note}>No hours found in the client's info. Set them in step 2.</div>}
          {draft.hours_source && <div style={{ ...note, opacity: 0.8, marginTop: 2 }}>Source: {draft.hours_source}</div>}
        </div>
      </div>

      <div style={box}>
        <input type="checkbox" checked={useEvent} onChange={(e) => setUseEvent(e.target.checked)} />
        <div style={{ flex: 1 }}><div style={{ fontSize: 13, color: "#d0e8ff", fontWeight: 600 }}>Appointment type: {ev.name}</div>
          <div style={note}>{ev.duration_min} min · {loc} · {ev.price_cents ? `$${dollars(ev.price_cents)} paid online` : "Free"}
            {ev.anchor_price_cents ? ` (normally $${dollars(ev.anchor_price_cents)})` : ""}{ev.spots_per_month ? ` · only ${ev.spots_per_month} spots/month` : ""}</div>
          {ev.ask_question && <div style={note}>Asks: "{ev.ask_question}"</div>}
          {ev.description && <div style={note}>Description: {ev.description}</div>}
          {existing.length > 0 && (
            <select className="dg-input" value={target} onChange={(e) => setTarget(e.target.value)} style={{ marginTop: 6, maxWidth: 320 }}>
              <option value="">Create as a new appointment type</option>
              {existing.map((x) => <option key={x.id} value={x.id}>Update "{x.name}"</option>)}
            </select>
          )}
        </div>
      </div>

      {(draft.notes || []).length > 0 && (
        <div style={{ ...note, color: "#f0cf9a", background: "rgba(240,160,40,0.06)", border: "1px solid rgba(240,160,40,0.2)", borderRadius: 8, padding: "8px 12px", marginTop: 8 }}>
          <b>Check these:</b>
          <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>{draft.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
        </div>
      )}

      <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
        <button className="btn btn-primary" disabled={busy || !(useTz || useHours || useEvent)} onClick={() => onApply({
          ...(useTz ? { timezone: draft.timezone } : {}),
          ...(useHours ? { hours: draft.hours } : {}),
          ...(useEvent ? { event_type: ev, ...(target ? { event_type_id: Number(target) } : {}) } : {}),
        })}>Apply selected</button>
        <button className="btn btn-secondary" onClick={onClose}>Discard</button>
      </div>
    </div>
  );
}

const FUNNEL_STEPS = [["view", "Opened page"], ["time", "Picked a time"], ["details", "Left name + mobile"], ["submit", "Clicked book / pay"], ["booked", "Booked"]];

export function FunnelBars({ funnel, compact }) {
  const f = funnel || {};
  const top = f.view || 0;
  if (!top) return <div style={note}>No visits tracked yet. Numbers show up after the first patient opens the page.</div>;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: compact ? 3 : 6 }}>
      {FUNNEL_STEPS.map(([k, label]) => {
        const n = f[k] || 0; const pct = Math.round((n / top) * 100);
        return (
          <div key={k} style={{ display: "grid", gridTemplateColumns: compact ? "120px 1fr 70px" : "150px 1fr 90px", gap: 10, alignItems: "center", fontSize: compact ? 11 : 12 }}>
            <span style={{ color: "#9cc4f5" }}>{label}</span>
            <div style={{ height: compact ? 6 : 8, borderRadius: 6, background: "rgba(58,123,213,0.12)" }}>
              <div style={{ width: `${Math.max(pct, n ? 2 : 0)}%`, height: "100%", borderRadius: 6, background: k === "booked" ? "#14c882" : "#3a7bd5" }} />
            </div>
            <span style={{ ...mono, color: "#d0e8ff", fontSize: compact ? 10.5 : 11.5, textAlign: "right" }}>{n} · {pct}%</span>
          </div>
        );
      })}
      {(f.followups_sent || 0) > 0 && (
        <div style={{ ...note, marginTop: 4 }}>Unfinished-booking texts sent: <b style={{ color: "#d0e8ff" }}>{f.followups_sent}</b> · booked after the text: <b style={{ color: "#14c882" }}>{f.recovered || 0}</b></div>
      )}
    </div>
  );
}
const mono = { fontFamily: "'Share Tech Mono', monospace" };

function FunnelCard({ funnel }) {
  return (
    <Section title="Conversion (last 30 days)">
      <div style={{ ...note, marginBottom: 8 }}>Each patient visit to the booking page, step by step. The biggest drop shows where the page loses people.</div>
      <FunnelBars funnel={funnel} />
    </Section>
  );
}

function PageDetailsSection({ data, clientId, save, run, busy }) {
  const s = data.settings;
  const parse = (v) => { try { return typeof v === "string" ? JSON.parse(v) : (v || []); } catch { return []; } };
  const [form, setForm] = useState(null);
  useEffect(() => {
    const rv = parse(s.reviews);
    setForm({
      provider_name: s.provider_name || "", provider_title: s.provider_title || "", photo_url: s.photo_url || "", logo_url: s.logo_url || "",
      what_to_expect: s.what_to_expect || "", review_rating: s.review_rating ?? "", review_count: s.review_count ?? "",
      // Up to 10 on file (the booking page shows the first, the rest under "View more reviews"); always one empty row to add another.
      reviews: Array.from({ length: Math.min(10, Math.max(3, rv.length + 1)) }, (_, i) => rv[i] || { text: "", author: "" }),
      contact_phone: s.contact_phone || "", contact_email: s.contact_email || "",
    });
    // eslint-disable-next-line
  }, [s.provider_name, s.provider_title, s.photo_url, s.logo_url, s.what_to_expect, s.review_rating, s.review_count, s.reviews, s.contact_phone, s.contact_email]);
  const [query, setQuery] = useState("");
  if (!form) return null;
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const setReview = (i, k) => (e) => setForm({ ...form, reviews: form.reviews.map((r, j) => (j === i ? { ...r, [k]: e.target.value } : r)) });
  const rating = parseFloat(form.review_rating);
  const count = parseInt(form.review_count, 10);
  const ratingShows = rating >= 4 && (!(count >= 0) || count >= 5);
  const willShow = ratingShows || form.reviews.some((r) => r.text.trim());
  const repull = (overwrite) => run(() => call(`/clients/${clientId}/booking/page-autofill`, { method: "POST", body: JSON.stringify({ overwrite }) }),
    overwrite ? "Replaced with what's in the portal, website and funnel" : "Filled the empty fields from the portal, website and funnel");
  return (
    <Section title="Page details (trust + follow-up)" right={
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", justifyContent: "flex-end" }}>
        <button className="btn btn-secondary" disabled={busy || data.page_autofill_running} onClick={() => repull(false)} title="Fills only the empty fields">Pull from client info</button>
        <button className="btn btn-secondary" disabled={busy || data.page_autofill_running} onClick={() => repull(true)} title="Replaces what's there">Replace from client info</button>
        <button className="btn btn-primary" disabled={busy} onClick={() => save({ ...form, reviews: form.reviews.filter((r) => r.text.trim()) }, "Page details saved")}>Save</button>
      </div>
    }>
      <div style={{ ...note, marginBottom: 10, color: data.page_autofill_running ? "#6ab0ff" : "#6f88ad" }}>
        {data.page_autofill_running ? "Pulling the therapist, photo, reviews and visit details from the client portal, their website and their funnel..."
          : s.page_autofill_note ? (
            <details>
              <summary style={{ cursor: "pointer" }}>Auto-filled {s.page_autofilled_at ? new Date(s.page_autofilled_at).toLocaleDateString() : ""} from the portal, website and funnel (show notes)</summary>
              <div style={{ marginTop: 6 }}>{s.page_autofill_note}</div>
            </details>
          )
          : "Fills itself from the client portal, their website and their funnel. Reviews are only ever copied word for word."}
      </div>
      <div style={row}>
        <Field name="Patient questions: phone" width={200}>
          <input className="dg-input" value={form.contact_phone} onChange={set("contact_phone")} placeholder={data.client_contact?.phone || "(555) 123-4567"} />
        </Field>
        <Field name="Patient questions: email">
          <input className="dg-input" value={form.contact_email} onChange={set("contact_email")} placeholder={data.client_contact?.email || "frontdesk@clinic.com"} />
        </Field>
      </div>
      <div style={{ ...note, marginTop: 4, marginBottom: 10 }}>
        Goes in the instant confirmation text: "Questions? Call ... or email ...". Left blank, it uses the phone and email on the client's record (shown greyed out).
      </div>
      <div style={row}>
        <Field name="Therapist name"><input className="dg-input" value={form.provider_name} onChange={set("provider_name")} placeholder="Brian Smith" /></Field>
        <Field name="Title" width={160}><input className="dg-input" value={form.provider_title} onChange={set("provider_title")} placeholder="PT, DPT" /></Field>
      </div>
      <div style={{ ...row, marginTop: 8 }}>
        <Field name="Photo link (therapist or clinic, https://)"><input className="dg-input" value={form.photo_url} onChange={set("photo_url")} placeholder="Leave blank to use the funnel's hero image" /></Field>
        {form.photo_url && <img src={form.photo_url} alt="" style={{ width: 44, height: 44, borderRadius: "50%", objectFit: "cover", alignSelf: "flex-end" }} />}
      </div>
      <div style={{ ...row, marginTop: 8 }}>
        <Field name="Logo link (must read well on white)"><input className="dg-input" value={form.logo_url} onChange={set("logo_url")} placeholder="Optional" /></Field>
        {form.logo_url && <img src={form.logo_url} alt="" style={{ maxHeight: 36, maxWidth: 140, background: "#fff", borderRadius: 4, padding: 2, alignSelf: "flex-end" }} />}
      </div>
      <div style={{ ...row, marginTop: 8 }}>
        <Field name="What to expect (one per line, up to 4; shown as checkmarks)">
          <textarea className="dg-input" rows={3} value={form.what_to_expect} onChange={set("what_to_expect")} placeholder={"Sit down 1-on-1 with a physical therapist\nLeave knowing what's wrong and the plan"} />
        </Field>
      </div>

      <div style={{ marginTop: 14, paddingTop: 12, borderTop: "1px solid rgba(58,123,213,0.12)" }}>
        <div style={{ ...row, alignItems: "flex-end" }}>
          <Field name="Google rating" width={110}><input className="dg-input" type="number" step="0.1" min="1" max="5" value={form.review_rating} onChange={set("review_rating")} /></Field>
          <Field name="Review count" width={110}><input className="dg-input" type="number" min="0" value={form.review_count} onChange={set("review_count")} /></Field>
          <div style={{ flex: 1, display: "flex", gap: 6, alignItems: "flex-end", minWidth: 260 }}>
            <input className="dg-input" style={{ flex: 1 }} placeholder="Clinic name + city (optional)" value={query} onChange={(e) => setQuery(e.target.value)} />
            <button className="btn btn-secondary" disabled={busy || !data.places_configured} title={data.places_configured ? "" : "Needs a valid PLACES_API_KEY on the server"}
              onClick={() => run(() => call(`/clients/${clientId}/booking/reviews/fetch`, { method: "POST", body: JSON.stringify({ query: query || null }) }), "Pulled from Google")}>
              Fetch from Google
            </button>
          </div>
        </div>
        <div style={{ ...note, marginTop: 6, color: willShow ? "#8fd9bd" : "#f0a028" }}>
          {ratingShows ? "Rating and reviews show on the booking page." : willShow ? "Reviews show on the booking page; the rating stays hidden (needs 4.0+, and 5+ reviews when the count is known)." : "Nothing to show yet. Ratings under 4.0 or with fewer than 5 reviews stay hidden, since they hurt more than help."}
          {!data.places_configured && " The Google key on the server is missing or invalid, so type these in for now."}
        </div>
        {form.reviews.map((r, i) => (
          <div key={i} style={{ ...row, marginTop: 8 }}>
            <Field name={`Review ${i + 1}${i === 0 ? " (shown first)" : ""} (real, copied word for word)`}><input className="dg-input" value={r.text} onChange={setReview(i, "text")} /></Field>
            <Field name="First name" width={130}><input className="dg-input" value={r.author} onChange={setReview(i, "author")} /></Field>
          </div>
        ))}
        {form.reviews.length < 10 && (
          <button className="btn btn-secondary" style={{ marginTop: 8 }} onClick={() => setForm({ ...form, reviews: [...form.reviews, { text: "", author: "" }] })}>+ Add review</button>
        )}
      </div>

      <label style={{ ...note, display: "flex", gap: 8, alignItems: "center", marginTop: 14 }}>
        <input type="checkbox" checked={!!s.abandon_followup} disabled={busy} onChange={(e) => save({ abandon_followup: e.target.checked }, e.target.checked ? "Unfinished-booking texts on" : "Unfinished-booking texts off")} />
        Text patients who leave their name + mobile but don't finish booking (one text, 10 minutes later, from the clinic's number; replies go to the AI text agent)
      </label>
    </Section>
  );
}

function CalendarSection({ data, google, save, busy }) {
  const s = data.settings;
  // Google reports edit access as "owner", "writer" or (newer) "writerWithoutPrivateAccess".
  const canWrite = (c) => c.access_role === "owner" || (c.access_role || "").startsWith("writer");
  const writable = (google?.calendars || []).filter(canWrite);
  const readable = (google?.calendars || []).filter((c) => c.id !== s.calendar_id);
  const current = (google?.calendars || []).find((c) => c.id === s.calendar_id);
  return (
    <Section title="Clinic calendar">
      {!google ? <div style={note}>Checking Google…</div> : !google.ok ? (
        <div style={{ ...note, color: "#ff8a8a" }}>Can't reach Google Calendar: {google.error}</div>
      ) : (
        <>
          <div style={{ ...note, marginBottom: 10 }}>
            Clinics share their Google Calendar with <b style={{ color: "#d0e8ff" }}>{google.account}</b> ("Make changes to events").
            Once shared, it shows up below. If it doesn't, accept the share email in that inbox, then reload.
          </div>
          <div style={row}>
            <Field name="Book appointments into">
              <select className="dg-input" value={s.calendar_id || ""} disabled={busy} onChange={(e) => save({ calendar_id: e.target.value })}>
                <option value="">— pick the clinic's calendar —</option>
                {writable.map((c) => <option key={c.id} value={c.id}>{c.name}{c.primary ? " (our own)" : ""} · {c.id}</option>)}
              </select>
              {(google?.calendars || []).some((c) => !canWrite(c) && !c.id.includes("#")) && (
                <div style={{ ...note, marginTop: 4 }}>
                  Shared view-only (not listed): {(google.calendars || []).filter((c) => !canWrite(c) && !c.id.includes("#")).map((c) => c.id).join(", ")}. Ask them to switch it to "Make changes to events".
                </div>
              )}
            </Field>
            <Field name="Clinic timezone" width={230}>
              <select className="dg-input" value={data.effective_timezone} disabled={busy} onChange={(e) => save({ timezone: e.target.value })}>
                {[...new Set([data.effective_timezone, ...US_TIMEZONES.map((t) => t[0])])].map((tz) => (
                  <option key={tz} value={tz}>{(US_TIMEZONES.find((t) => t[0] === tz) || [tz, tz])[1]}</option>
                ))}
              </select>
            </Field>
          </div>
          {current && !canWrite(current) && (
            <div style={{ ...note, color: "#f0a028", marginTop: 6 }}>This calendar is shared read-only. Ask the clinic to switch it to "Make changes to events".</div>
          )}
          <div style={{ ...note, marginTop: 6 }}>Timezone is set automatically from the clinic's Google Calendar when you pick it{!s.calendar_id ? " (until then it's guessed from the clinic's location)" : ""}. Change it only if it's wrong.</div>
          {readable.length > 0 && (
            <details style={{ marginTop: 10 }}>
              <summary style={{ ...note, cursor: "pointer" }}>Also block times that are busy on… ({(s.busy_calendar_ids || []).length} selected)</summary>
              <div style={{ marginTop: 6, display: "flex", flexDirection: "column", gap: 4 }}>
                {readable.map((c) => (
                  <label key={c.id} style={{ ...note, display: "flex", gap: 8, alignItems: "center" }}>
                    <input type="checkbox" checked={(s.busy_calendar_ids || []).includes(c.id)} disabled={busy}
                      onChange={(e) => save({ busy_calendar_ids: e.target.checked ? [...(s.busy_calendar_ids || []), c.id] : (s.busy_calendar_ids || []).filter((x) => x !== c.id) })} />
                    {c.name} <span style={{ opacity: 0.6 }}>{c.id}</span>
                  </label>
                ))}
              </div>
            </details>
          )}
        </>
      )}
    </Section>
  );
}

function HoursSection({ data, clientId, run, busy }) {
  const [blocks, setBlocks] = useState(data.hours.map((x) => ({ ...x, start_time: t5(x.start_time), end_time: t5(x.end_time) })));
  useEffect(() => { setBlocks(data.hours.map((x) => ({ ...x, start_time: t5(x.start_time), end_time: t5(x.end_time) }))); }, [data.hours]);
  const set = (i, patch) => setBlocks((b) => b.map((x, j) => (j === i ? { ...x, ...patch } : x)));
  return (
    <Section title="New patient hours" right={
      <button className="btn btn-primary" disabled={busy} onClick={() => run(() => call(`/clients/${clientId}/booking/hours`, { method: "PUT", body: JSON.stringify({ hours: blocks }) }), "Hours saved")}>Save hours</button>
    }>
      <div style={{ ...note, marginBottom: 8 }}>When new patients can book, in the clinic's timezone. Add two blocks on a day to skip lunch.</div>
      {WEEKDAYS.map((name, wd) => {
        const idx = blocks.map((b, i) => [b, i]).filter(([b]) => b.weekday === wd);
        return (
          <div key={wd} style={{ display: "flex", gap: 10, alignItems: "center", padding: "5px 0", borderTop: "1px solid rgba(58,123,213,0.08)" }}>
            <div style={{ width: 40, fontSize: 12, color: "#9cc4f5", fontWeight: 600 }}>{name}</div>
            <div style={{ flex: 1, display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
              {idx.length === 0 && <span style={{ ...note, opacity: 0.7 }}>Closed</span>}
              {idx.map(([b, i]) => (
                <span key={i} style={{ display: "flex", gap: 4, alignItems: "center" }}>
                  <input className="dg-input" type="time" value={b.start_time} onChange={(e) => set(i, { start_time: e.target.value })} style={{ width: 110 }} />
                  <span style={note}>to</span>
                  <input className="dg-input" type="time" value={b.end_time} onChange={(e) => set(i, { end_time: e.target.value })} style={{ width: 110 }} />
                  <button className="btn btn-secondary" style={{ padding: "4px 8px" }} onClick={() => setBlocks((bl) => bl.filter((_, j) => j !== i))}>✕</button>
                </span>
              ))}
              <button className="btn btn-secondary" style={{ padding: "4px 10px", fontSize: 11 }}
                onClick={() => setBlocks((bl) => [...bl, { weekday: wd, start_time: "09:00", end_time: "17:00" }])}>+ hours</button>
            </div>
          </div>
        );
      })}
    </Section>
  );
}

function OverridesSection({ data, clientId, run, busy }) {
  const norm = (o) => ({ date: o.date, closed: o.closed, start_time: t5(o.start_time), end_time: t5(o.end_time) });
  const [rows, setRows] = useState(data.overrides.map(norm));
  useEffect(() => { setRows(data.overrides.map(norm)); }, [data.overrides]);
  const set = (i, patch) => setRows((r) => r.map((x, j) => (j === i ? { ...x, ...patch } : x)));
  return (
    <Section title="Days off & special hours" right={
      <button className="btn btn-primary" disabled={busy} onClick={() => run(() => call(`/clients/${clientId}/booking/overrides`, { method: "PUT", body: JSON.stringify({ overrides: rows }) }), "Days off saved")}>Save</button>
    }>
      {rows.length === 0 && <div style={note}>None. Holidays, vacations or one-off hours go here.</div>}
      {rows.map((o, i) => (
        <div key={i} style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6, flexWrap: "wrap" }}>
          <input className="dg-input" type="date" value={o.date} onChange={(e) => set(i, { date: e.target.value })} style={{ width: 150 }} />
          <label style={{ ...note, display: "flex", gap: 4, alignItems: "center" }}>
            <input type="checkbox" checked={o.closed} onChange={(e) => set(i, { closed: e.target.checked })} /> Closed all day
          </label>
          {!o.closed && (<>
            <input className="dg-input" type="time" value={o.start_time} onChange={(e) => set(i, { start_time: e.target.value })} style={{ width: 110 }} />
            <span style={note}>to</span>
            <input className="dg-input" type="time" value={o.end_time} onChange={(e) => set(i, { end_time: e.target.value })} style={{ width: 110 }} />
          </>)}
          <button className="btn btn-secondary" style={{ padding: "4px 8px" }} onClick={() => setRows((r) => r.filter((_, j) => j !== i))}>✕</button>
        </div>
      ))}
      <button className="btn btn-secondary" style={{ marginTop: 6, fontSize: 11 }}
        onClick={() => setRows((r) => [...r, { date: new Date().toISOString().slice(0, 10), closed: true, start_time: "09:00", end_time: "12:00" }])}>+ add a date</button>
    </Section>
  );
}

// DigiGrowth's standard patient offers. Picking one fills the form; every
// field stays editable. Paid ($49) follows the paid-offer default:
// "normally $150" + "only 10 spots per month".
const OFFER_PRESETS = [
  { key: "phone15", label: "15 min Free Phone Consult", fields: {
    name: "Free 15-Minute Phone Consultation", duration_min: 15, location_type: "phone", location_text: "",
    price_cents: 0, anchor_price_cents: null, spots_per_month: null, buffer_after_min: 0,
    description: "A quick call with a physical therapist to talk through what's going on and whether we can help." } },
  { key: "inperson30", label: "30 min Free In-Person Consult", fields: {
    name: "Free 30-Minute Consultation", duration_min: 30, location_type: "in_person",
    price_cents: 0, anchor_price_cents: null, spots_per_month: null, buffer_after_min: 15,
    description: "Meet a physical therapist in the clinic, talk through what's going on, and see if we're a good fit." } },
  { key: "meet30", label: "30 min Free Google Meet Consult", fields: {
    name: "Free 30-Minute Video Consultation", duration_min: 30, location_type: "google_meet", location_text: "",
    price_cents: 0, anchor_price_cents: null, spots_per_month: null, buffer_after_min: 0,
    description: "A video call with a physical therapist to talk through what's going on and whether we can help." } },
  { key: "assess49", label: "$49 Assessment", fields: {
    name: "$49 New Patient Assessment", duration_min: 30, location_type: "in_person",
    price_cents: 4900, anchor_price_cents: 15000, spots_per_month: 10, buffer_after_min: 15,
    description: "A full one-on-one assessment with a physical therapist. Leave knowing what's going on and the plan to fix it." } },
];

const EMPTY_EVENT = {
  name: "New Patient Assessment", description: "", duration_min: 30, location_type: "in_person", location_text: "",
  price_cents: 0, anchor_price_cents: null, spots_per_month: null, ask_question: "What brings you in?",
  buffer_before_min: 0, buffer_after_min: 15, min_notice_hours: 12, max_days_ahead: 30, daily_cap: null,
  slot_interval_min: 30, active: true, sort_order: 0,
};

function EventTypesSection({ data, clientId, run, reload, busy }) {
  const [editing, setEditing] = useState(null); // event object being edited (id null = new)
  const saveEvent = async () => {
    const body = { ...editing };
    delete body.id; delete body.client_id; delete body.created_at;
    const r = await run(() => editing.id
      ? call(`/clients/${clientId}/booking/event-types/${editing.id}`, { method: "PUT", body: JSON.stringify(body) })
      : call(`/clients/${clientId}/booking/event-types`, { method: "POST", body: JSON.stringify(body) }), "Appointment type saved");
    if (r) { setEditing(null); reload(); }
  };
  const remove = async (ev) => {
    const r = await run(() => call(`/clients/${clientId}/booking/event-types/${ev.id}`, { method: "DELETE" }), "Removed");
    if (r) reload();
  };
  return (
    <Section title="Appointment types" right={!editing && <button className="btn btn-secondary" onClick={() => setEditing({ ...EMPTY_EVENT, id: null })}>+ New</button>}>
      {data.event_types.length === 0 && !editing && <div style={note}>None yet. Add the visit patients book (e.g. New Patient Assessment).</div>}
      {data.event_types.map((ev) => (
        <div key={ev.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 0", borderTop: "1px solid rgba(58,123,213,0.08)", opacity: ev.active ? 1 : 0.5 }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 13, color: "#d0e8ff", fontWeight: 600 }}>{ev.name}{!ev.active && " (hidden)"}</div>
            <div style={note}>{ev.duration_min} min · {LOCATIONS.find((l) => l.value === ev.location_type)?.label} · {ev.price_cents ? `$${dollars(ev.price_cents)} paid online` : "Free"}{ev.anchor_price_cents ? ` (normally $${dollars(ev.anchor_price_cents)})` : ""} · link: {data.public_url}?type={ev.slug}</div>
          </div>
          <button className="btn btn-secondary" onClick={() => setEditing({ ...ev })}>Edit</button>
          <button className="btn btn-secondary" disabled={busy} onClick={() => remove(ev)}>Delete</button>
        </div>
      ))}
      {editing && <EventForm ev={editing} setEv={setEditing} onSave={saveEvent} onCancel={() => setEditing(null)} busy={busy}
        clinicAddress={(data.event_types.find((e) => e.location_type === "in_person" && e.location_text) || {}).location_text || ""} />}
    </Section>
  );
}

function EventForm({ ev, setEv, onSave, onCancel, busy, clinicAddress }) {
  const applyPreset = (key) => {
    const p = OFFER_PRESETS.find((x) => x.key === key);
    if (!p) return;
    const fields = { ...p.fields };
    if (fields.location_type === "in_person") fields.location_text = ev.location_text || clinicAddress || "";
    setEv({ ...ev, ...fields, ask_question: ev.ask_question || "What brings you in?" });
  };
  const f = (k) => (e) => setEv({ ...ev, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  const n = (k) => (e) => setEv({ ...ev, [k]: e.target.value === "" ? null : parseInt(e.target.value, 10) });
  return (
    <div style={{ marginTop: 10, padding: 12, borderRadius: 10, background: "rgba(58,123,213,0.06)" }}>
      <div style={{ ...row, marginBottom: 8 }}>
        <Field name="Start from one of our offers" width={300}>
          <select className="dg-input" value="" onChange={(e) => applyPreset(e.target.value)}>
            <option value="">Choose an offer...</option>
            {OFFER_PRESETS.map((p) => <option key={p.key} value={p.key}>{p.label}</option>)}
          </select>
        </Field>
        <div style={{ ...note, flex: 1, alignSelf: "center" }}>Fills in the fields below. Edit anything after.</div>
      </div>
      <div style={row}>
        <Field name="Name"><input className="dg-input" value={ev.name || ""} onChange={f("name")} /></Field>
        <Field name="Length (min)" width={110}><input className="dg-input" type="number" value={ev.duration_min ?? ""} onChange={n("duration_min")} /></Field>
        <Field name="Where" width={190}>
          <select className="dg-input" value={ev.location_type} onChange={f("location_type")}>{LOCATIONS.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}</select>
        </Field>
      </div>
      {ev.location_type === "in_person" && (
        <div style={{ ...row, marginTop: 8 }}><Field name="Clinic address"><input className="dg-input" value={ev.location_text || ""} onChange={f("location_text")} /></Field></div>
      )}
      <div style={{ ...row, marginTop: 8 }}>
        <Field name="Description (optional)"><textarea className="dg-input" rows={2} value={ev.description || ""} onChange={f("description")} /></Field>
      </div>
      <div style={{ ...row, marginTop: 8 }}>
        <Field name="Price $ (0 = free)" width={130}><input className="dg-input" type="number" min="0" step="1" value={dollars(ev.price_cents) || "0"} onChange={(e) => setEv({ ...ev, price_cents: cents(e.target.value) || 0 })} /></Field>
        <Field name='"Normally" $' width={120}><input className="dg-input" type="number" min="0" value={dollars(ev.anchor_price_cents)} onChange={(e) => setEv({ ...ev, anchor_price_cents: cents(e.target.value) })} /></Field>
        <Field name="Spots / month (shown)" width={150}><input className="dg-input" type="number" min="0" value={ev.spots_per_month ?? ""} onChange={n("spots_per_month")} /></Field>
        <Field name="Question to ask (optional)"><input className="dg-input" value={ev.ask_question || ""} onChange={f("ask_question")} /></Field>
      </div>
      <div style={{ ...row, marginTop: 8 }}>
        <Field name="Min notice (hrs)" width={120}><input className="dg-input" type="number" value={ev.min_notice_hours ?? ""} onChange={n("min_notice_hours")} /></Field>
        <Field name="Book up to (days)" width={130}><input className="dg-input" type="number" value={ev.max_days_ahead ?? ""} onChange={n("max_days_ahead")} /></Field>
        <Field name="Max per day" width={110}><input className="dg-input" type="number" placeholder="no limit" value={ev.daily_cap ?? ""} onChange={n("daily_cap")} /></Field>
        <Field name="Start times every (min)" width={160}><input className="dg-input" type="number" value={ev.slot_interval_min ?? ""} onChange={n("slot_interval_min")} /></Field>
        <Field name="Buffer before" width={110}><input className="dg-input" type="number" value={ev.buffer_before_min ?? ""} onChange={n("buffer_before_min")} /></Field>
        <Field name="Buffer after" width={110}><input className="dg-input" type="number" value={ev.buffer_after_min ?? ""} onChange={n("buffer_after_min")} /></Field>
      </div>
      <label style={{ ...note, display: "flex", gap: 6, alignItems: "center", marginTop: 8 }}>
        <input type="checkbox" checked={!!ev.active} onChange={f("active")} /> Bookable (uncheck to hide it)
      </label>
      <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
        <button className="btn btn-primary" disabled={busy} onClick={onSave}>Save</button>
        <button className="btn btn-secondary" onClick={onCancel}>Cancel</button>
      </div>
    </div>
  );
}

function PaymentsSection({ data, clientId, save, run, reload, busy }) {
  const s = data.settings;
  const [status, setStatus] = useState(null);
  const [link, setLink] = useState("");
  const needsPayment = data.event_types.some((e) => e.active && e.price_cents > 0);
  useEffect(() => {
    if (s.stripe_account_id && data.stripe_platform_configured) {
      call(`/clients/${clientId}/booking/stripe/refresh`, { method: "POST" }).then(setStatus).catch(() => {});
    }
    // eslint-disable-next-line
  }, [clientId, s.stripe_account_id]);
  return (
    <Section title="Payments (Stripe)">
      {!data.stripe_platform_configured ? (
        <div style={{ ...note, color: "#f0a028" }}>
          Stripe platform not set up yet: add <code>STRIPE_SECRET_KEY</code> (your Stripe account with Connect enabled) and
          <code> STRIPE_CONNECT_WEBHOOK_SECRET</code> to Doppler/Railway. Free appointments work without it.
        </div>
      ) : (
        <>
          <div style={{ ...note, marginBottom: 8 }}>
            Patients pay the clinic's own Stripe account directly. 100% goes to the clinic; DigiGrowth takes no cut.
            {!data.stripe_webhook_configured && <span style={{ color: "#f0a028" }}> Webhook secret missing: payments still confirm when the patient returns from checkout, but add STRIPE_CONNECT_WEBHOOK_SECRET as a backstop.</span>}
          </div>
          <div style={{ ...note, marginBottom: 8 }}>
            Status: {!s.stripe_account_id ? <b>not connected</b> : status ? (
              <b style={{ color: status.charges_enabled ? "#14c882" : "#f0a028" }}>
                {status.charges_enabled ? `Connected${status.business_name ? ` (${status.business_name})` : ""}, can take payments` : "Started, clinic hasn't finished Stripe's setup yet"}
              </b>
            ) : <b>checking…</b>}
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button className="btn btn-primary" disabled={busy} onClick={async () => {
              const r = await run(() => call(`/clients/${clientId}/booking/stripe/connect`, { method: "POST" }));
              if (r?.url) { setLink(r.url); reload(); }
            }}>{s.stripe_account_id ? "New Stripe setup link" : "Create Stripe setup link"}</button>
            {s.stripe_account_id && <button className="btn btn-secondary" disabled={busy} onClick={async () => setStatus(await run(() => call(`/clients/${clientId}/booking/stripe/refresh`, { method: "POST" })))}>Refresh status</button>}
          </div>
          {link && (
            <div style={{ marginTop: 8 }}>
              <div style={note}>Send this to the clinic (works once, expires in a few minutes, so make a new one if needed). They log in to Stripe or create an account, and payouts go to their bank.</div>
              <input className="dg-input" readOnly value={link} onFocus={(e) => e.target.select()} style={{ width: "100%", marginTop: 4 }} />
            </div>
          )}
        </>
      )}
      <div style={{ ...row, marginTop: 10 }}>
        <Field name="When a patient cancels a paid visit" width={280}>
          <select className="dg-input" value={s.refund_policy} disabled={busy} onChange={(e) => save({ refund_policy: e.target.value })}>
            {REFUNDS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
          </select>
        </Field>
      </div>
      {needsPayment && !(status && status.charges_enabled) && (
        <div style={{ ...note, color: "#f0a028", marginTop: 6 }}>A paid appointment type is active but Stripe isn't ready, so patients will see "call the clinic to book" for it.</div>
      )}
    </Section>
  );
}

function PreviewSection({ data, clientId }) {
  const [eventId, setEventId] = useState(data.event_types[0]?.id || "");
  const [slots, setSlots] = useState(null);
  const [err, setErr] = useState("");
  const load = async () => {
    setErr(""); setSlots(null);
    try { setSlots(await call(`/clients/${clientId}/booking/slots?event_type_id=${eventId}&days=7`)); } catch (e) { setErr(e.message); }
  };
  if (!data.event_types.length) return null;
  const fmt = (iso, tz) => new Intl.DateTimeFormat("en-US", { timeZone: tz, hour: "numeric", minute: "2-digit" }).format(new Date(iso));
  return (
    <Section title="Check availability" right={
      <div style={{ display: "flex", gap: 6 }}>
        <select className="dg-input" value={eventId} onChange={(e) => setEventId(e.target.value)}>{data.event_types.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}</select>
        <button className="btn btn-secondary" onClick={load}>Show next 7 days</button>
      </div>
    }>
      {err && <div style={{ ...note, color: "#ff8a8a" }}>{err}</div>}
      {slots && slots.days.map((d) => (
        <div key={d.date} style={{ display: "flex", gap: 10, padding: "4px 0", fontSize: 12 }}>
          <div style={{ width: 90, color: "#9cc4f5" }}>{new Date(d.date + "T12:00:00Z").toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric", timeZone: "UTC" })}</div>
          <div style={{ color: d.slots.length ? "#d0e8ff" : "#5a7aa0" }}>{d.slots.length ? d.slots.map((x) => fmt(x, slots.timezone)).join(", ") : "No openings"}</div>
        </div>
      ))}
      {!slots && !err && <div style={note}>Shows exactly what patients will see, after the clinic's calendar, buffers and notice rules.</div>}
    </Section>
  );
}

function BookingsSection({ clientId }) {
  const [rows, setRows] = useState(null);
  const [err, setErr] = useState("");
  const load = () => call(`/clients/${clientId}/booking/bookings`).then(setRows).catch((e) => setErr(e.message));
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [clientId]);
  const cancel = async (b) => {
    setErr("");
    try { await call(`/clients/${clientId}/booking/bookings/${b.id}/cancel`, { method: "POST", body: "{}" }); load(); }
    catch (e) { setErr(e.message); }
  };
  return (
    <Section title="Recent bookings" right={<button className="btn btn-secondary" onClick={load}>Refresh</button>}>
      {err && <div style={{ ...note, color: "#ff8a8a" }}>{err}</div>}
      {rows && rows.length === 0 && <div style={note}>No bookings yet.</div>}
      {rows && rows.map((b) => (
        <div key={b.id} style={{ display: "flex", gap: 10, alignItems: "center", padding: "7px 0", borderTop: "1px solid rgba(58,123,213,0.08)", fontSize: 12 }}>
          <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: STATUS_COLORS[b.status] || "#8aaad0", width: 110 }}>{b.status.replace("_", " ").toUpperCase()}</span>
          <div style={{ flex: 1 }}>
            <div style={{ color: "#d0e8ff" }}><ContactLink phone={b.phone} email={b.email} clientId={b.client_id}>{b.name}</ContactLink> · {b.event_name}</div>
            <div style={note}>
              {new Date(b.start_at).toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" })} (your time) · {b.phone} · {b.email}
              {b.paid_at && ` · paid $${dollars(b.price_cents)}`}{b.refunded_at && " · refunded"}
              {b.calendar_error && <span style={{ color: "#ff8a8a" }}> · not on clinic calendar: {b.calendar_error}</span>}
            </div>
          </div>
          <a href={b.manage_url} target="_blank" rel="noreferrer" style={{ color: "#6ab0ff", fontSize: 11 }}>Patient page</a>
          {b.status === "confirmed" && new Date(b.start_at) > new Date() && <button className="btn btn-secondary" onClick={() => cancel(b)}>Cancel</button>}
        </div>
      ))}
    </Section>
  );
}
