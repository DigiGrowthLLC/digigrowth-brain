import React, { useEffect, useState } from "react";
import { API } from "../api.js";

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

const dollars = (c) => (c == null || c === "" ? "" : (c / 100).toString());
const cents = (d) => (d === "" || d == null ? null : Math.round(parseFloat(d) * 100));
const t5 = (t) => (t || "").slice(0, 5);

export default function ClientBookingSetup({ clientId }) {
  const [data, setData] = useState(null);
  const [google, setGoogle] = useState(null);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

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

  if (!data) return <div style={note}>{err || "Loading booking setup…"}</div>;
  const s = data.settings;
  const save = (patch, okMsg = "Saved") => run(() => call(`/clients/${clientId}/booking`, { method: "PUT", body: JSON.stringify(patch) }), okMsg);

  return (
    <div style={{ marginTop: 8 }}>
      {(err || msg) && (
        <div style={{ marginBottom: 10, fontSize: 12, color: err ? "#ff8a8a" : "#8fd9bd" }}>{err || msg}</div>
      )}

      <Section
        title="DigiGrowth Booking"
        right={
          <button className={s.enabled ? "btn btn-secondary" : "btn btn-primary"} disabled={busy}
            onClick={() => save({ enabled: !s.enabled }, s.enabled ? "Booking turned off (funnel falls back to Calendly)" : "Booking is live")}>
            {s.enabled ? "Turn off" : "Turn on"}
          </button>
        }
      >
        <div style={{ ...note, marginBottom: 8 }}>
          Status: <b style={{ color: s.enabled ? "#14c882" : "#f0a028" }}>{s.enabled ? "LIVE" : "OFF"}</b>
          {" · "}When live, the funnel's Book button, the client portal's Book button and the link below all use this
          instead of Calendly.
        </div>
        <div style={row}>
          <Field name="Booking link">
            <div style={{ display: "flex", gap: 6 }}>
              <input className="dg-input" readOnly value={data.public_url} style={{ flex: 1 }} />
              <a className="btn btn-secondary" href={data.public_url} target="_blank" rel="noreferrer">Open</a>
            </div>
          </Field>
          <Field name="Link name" width={180}>
            <input className="dg-input" defaultValue={s.booking_slug} onBlur={(e) => e.target.value !== s.booking_slug && save({ booking_slug: e.target.value })} />
          </Field>
          <Field name="Button color" width={110}>
            <input className="dg-input" type="color" defaultValue={s.accent_color} onBlur={(e) => save({ accent_color: e.target.value })} style={{ height: 34, padding: 2 }} />
          </Field>
        </div>
        {data.funnel_urls.length > 0 && (
          <div style={{ ...note, marginTop: 8 }}>Funnel booking pages: {data.funnel_urls.map((u) => <a key={u} href={u} target="_blank" rel="noreferrer" style={{ color: "#6ab0ff", marginRight: 10 }}>{u.split("/lp/")[1]}</a>)}</div>
        )}
      </Section>

      <CalendarSection data={data} google={google} save={save} busy={busy} />
      <HoursSection data={data} clientId={clientId} run={run} busy={busy} />
      <OverridesSection data={data} clientId={clientId} run={run} busy={busy} />
      <EventTypesSection data={data} clientId={clientId} run={run} reload={load} busy={busy} />
      <PaymentsSection data={data} clientId={clientId} save={save} run={run} reload={load} busy={busy} />
      <PreviewSection data={data} clientId={clientId} />
      <BookingsSection clientId={clientId} />
    </div>
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
    <Section title="1 · Clinic calendar">
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
    <Section title="2 · New patient hours" right={
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
    <Section title="3 · Days off & special hours" right={
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

const EMPTY_EVENT = {
  name: "New Patient Assessment", description: "", duration_min: 60, location_type: "in_person", location_text: "",
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
    <Section title="4 · Appointment types" right={!editing && <button className="btn btn-secondary" onClick={() => setEditing({ ...EMPTY_EVENT, id: null })}>+ New</button>}>
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
      {editing && <EventForm ev={editing} setEv={setEditing} onSave={saveEvent} onCancel={() => setEditing(null)} busy={busy} />}
    </Section>
  );
}

function EventForm({ ev, setEv, onSave, onCancel, busy }) {
  const f = (k) => (e) => setEv({ ...ev, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  const n = (k) => (e) => setEv({ ...ev, [k]: e.target.value === "" ? null : parseInt(e.target.value, 10) });
  return (
    <div style={{ marginTop: 10, padding: 12, borderRadius: 10, background: "rgba(58,123,213,0.06)" }}>
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
    <Section title="5 · Payments (Stripe)">
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
    <Section title="6 · Check availability" right={
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
            <div style={{ color: "#d0e8ff" }}>{b.name} · {b.event_name}</div>
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
