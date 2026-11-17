import React, { useEffect, useState } from "react";
import { T, Card, SectionTitle, Pill, Toggle, Stat, Progress, Empty, Loading, HealthBadge, fmtDate, inputStyle } from "../ui.jsx";

// One client's AI Client Success Manager (Clients -> client -> Agents).
// Everything about how this client is being looked after in one place:
// campaign + health, reports (final ones wait for approval), what's waiting
// on Dylan (check-in drafts, questions), patient quality and milestones.
// Shared wording/templates stay in Business Resources -> Outreach Templates
// -> Client Success Templates. Backend: client_success.py + csm_extras.py.

const api = (p, opts) => fetch(`/api/client-success${p}`, opts);
const json = (body, method = "POST") => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

const MILESTONE_LABEL = { first_lead: "First lead", halfway: "Halfway to goal", goal_hit: "Goal reached", first_show: "First patient showed up" };

function LinkBtn({ children, onClick, disabled, tone, href }) {
  const style = { background: "none", border: "none", padding: 0, cursor: disabled ? "default" : "pointer", fontSize: 13, fontWeight: 600,
    color: tone === "bad" ? T.bad : tone === "mute" ? T.textMute : "#8fb8ff", textDecoration: "none", opacity: disabled ? 0.5 : 1, whiteSpace: "nowrap" };
  return href ? <a href={href} target="_blank" rel="noreferrer" style={style}>{children}</a>
    : <button type="button" style={style} onClick={onClick} disabled={disabled}>{children}</button>;
}

function Row({ children, style }) {
  return <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", padding: "12px 0", borderTop: `1px solid ${T.line}`, ...style }}>{children}</div>;
}

function CheckinDraft({ k, onChanged }) {
  const [subject, setSubject] = useState(k.subject);
  const [body, setBody] = useState(k.body);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const url = `/checkins/${k.client_id}/${k.key}`;
  const send = async () => {
    if (!window.confirm(`Email this check-in${k.to_email ? ` to ${k.to_email}` : ""}?`)) return;
    setBusy(true); setErr("");
    const r = await api(`${url}/send`, json({ subject, body }));
    if (!r.ok) setErr((await r.json().catch(() => ({}))).detail || "Send failed");
    setBusy(false); onChanged();
  };
  const patch = async (extra) => { await api(url, json({ subject, body, ...extra }, "PATCH")); onChanged(); };
  return (
    <div style={{ padding: 14, borderRadius: 12, border: `1px solid rgba(242,173,61,0.35)`, background: "rgba(242,173,61,0.05)", marginTop: 10 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 10, flexWrap: "wrap" }}>
        <span style={{ fontWeight: 600, color: T.text, fontSize: 13.5 }}>Day {String(k.key).replace("d", "")} onboarding check-in</span>
        <Pill tone="warn">Needs your approval</Pill>
        <span style={{ marginLeft: "auto", fontSize: 12, color: T.textMute }}>{k.to_email || "No email on file"}</span>
      </div>
      <input style={{ ...inputStyle, marginBottom: 8 }} value={subject} onChange={(e) => setSubject(e.target.value)} aria-label="Subject" />
      <textarea rows={8} style={{ ...inputStyle, resize: "vertical", lineHeight: 1.5 }} value={body} onChange={(e) => setBody(e.target.value)} aria-label="Email body" />
      <div style={{ display: "flex", gap: 16, justifyContent: "flex-end", alignItems: "center", marginTop: 10 }}>
        {err && <span style={{ color: T.bad, fontSize: 12.5, marginRight: "auto" }}>{err}</span>}
        <LinkBtn tone="mute" onClick={() => patch({ status: "dismissed" })}>Skip</LinkBtn>
        <LinkBtn onClick={() => patch({})}>Save edits</LinkBtn>
        <button className="btn btn-primary" disabled={busy} onClick={send}>{busy ? "Sending…" : "Approve & send"}</button>
      </div>
    </div>
  );
}

function Question({ f, onChanged }) {
  const [text, setText] = useState(f.answer || "");
  const [busy, setBusy] = useState(false);
  const save = async (email) => {
    if (!text.trim()) return;
    setBusy(true);
    await api(`/feedback/${f.id}`, json({ answer: text, email }, "PATCH"));
    setBusy(false); onChanged();
  };
  return (
    <div style={{ padding: 14, borderRadius: 12, border: `1px solid ${f.answer ? T.line : "rgba(77,142,240,0.4)"}`, marginTop: 10 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <Pill tone="info">{f.kind}</Pill>
        {f.rating != null && <Pill tone={(f.report_kind === "final" ? f.rating >= 9 : f.rating >= 4) ? "good" : (f.report_kind === "final" ? f.rating <= 6 : f.rating <= 2) ? "bad" : "neutral"}>Rated {f.rating}/{f.report_kind === "final" ? 10 : 5}</Pill>}
        {f.wants_next && <Pill tone="good">Wants next campaign</Pill>}
        {f.testimonial_ok && <Pill tone="good">Testimonial OK</Pill>}
        <span style={{ marginLeft: "auto", fontSize: 12, color: T.textMute }}>{f.report_kind === "final" ? "Final report" : f.week_number ? `Week ${f.week_number}` : ""} · {fmtDate(f.created_at)}</span>
      </div>
      {f.message && <div style={{ fontSize: 14, color: T.text, margin: "10px 0", whiteSpace: "pre-wrap", lineHeight: 1.5 }}>{f.message}</div>}
      {f.message && (
        <>
          <textarea rows={2} style={{ ...inputStyle, resize: "vertical" }} value={text} onChange={(e) => setText(e.target.value)}
            placeholder="Your answer (also shown at the top of their next report)…" aria-label="Answer" />
          <div style={{ display: "flex", gap: 16, justifyContent: "flex-end", alignItems: "center", marginTop: 8 }}>
            {f.answered_at && <span style={{ fontSize: 12, color: T.good, marginRight: "auto" }}>Answered {fmtDate(f.answered_at)}</span>}
            <LinkBtn disabled={busy} onClick={() => save(false)}>Save answer</LinkBtn>
            <button className="btn btn-secondary" disabled={busy} onClick={() => save(true)}>Save & email it</button>
          </div>
        </>
      )}
    </div>
  );
}

export default function ClientSuccessAgent({ clientId }) {
  const [sum, setSum] = useState(null);
  const [reports, setReports] = useState([]);
  const [feedback, setFeedback] = useState([]);
  const [checkins, setCheckins] = useState([]);
  const [lq, setLq] = useState({ ratings: [], summary: [] });
  const [ms, setMs] = useState([]);
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState("");

  const load = async () => {
    const q = `client_id=${clientId}`;
    const [s, r, f, k, l, m] = await Promise.all([
      api(`/clients/${clientId}`).then((x) => (x.ok ? x.json() : null)),
      api(`/reports?${q}&limit=30`).then((x) => (x.ok ? x.json() : [])),
      api(`/feedback?${q}`).then((x) => (x.ok ? x.json() : [])),
      api(`/checkins?${q}`).then((x) => (x.ok ? x.json() : [])),
      api(`/lead-quality?${q}&limit=20`).then((x) => (x.ok ? x.json() : { ratings: [], summary: [] })),
      api(`/milestones?${q}`).then((x) => (x.ok ? x.json() : [])),
    ]);
    setSum(s); setReports(r); setFeedback(f); setCheckins(k); setLq(l); setMs(m);
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [clientId]);

  if (!sum) return <Loading />;

  const patchClient = async (body) => { await api(`/clients/${clientId}`, json(body, "PATCH")); load(); };
  const generate = async (kind) => {
    setBusy(`gen-${kind}`); setError("");
    const r = await api(`/clients/${clientId}/generate`, json({ kind, send: false }));
    const d = await r.json().catch(() => ({}));
    if (!r.ok) setError(d.detail || "Couldn't build the report.");
    else if (d.url) window.open(d.url, "_blank");
    setBusy(null); load();
  };
  const sendReport = async (rep) => {
    if (!window.confirm(rep.kind === "final" ? "Approve and send this final report to the client?" : "Send this report to the client?")) return;
    setBusy(`send-${rep.id}`); await api(`/reports/${rep.id}/send`, { method: "POST" }); setBusy(null); load();
  };
  const deleteReport = async (rep) => {
    if (!window.confirm("Delete this report? Its link stops working.")) return;
    await api(`/reports/${rep.id}`, { method: "DELETE" }); load();
  };

  const launched = sum.state !== "not_launched";
  const money = (v) => `$${Number(v || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  const stateText = !launched ? "Campaign not launched yet" : sum.state === "ended" ? `Campaign ended ${fmtDate(sum.ends_at)}`
    : sum.budget ? `Week ${sum.week} · ${money(sum.budget.spent)} of ${money(sum.budget.cap)} ad budget`
    : `Week ${sum.week} · day ${sum.days_elapsed} of ${sum.length_days}`;
  const drafts = checkins.filter((k) => k.status === "draft");
  const open = feedback.filter((f) => f.message && !f.answer);
  const answered = feedback.filter((f) => !(f.message && !f.answer));
  const lqSum = lq.summary[0];

  return (
    <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr)", gap: 16 }}>
      {/* Status */}
      <Card>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 16 }}>
          <Toggle on={!!sum.enabled} onChange={(v) => patchClient({ csm_reports_enabled: v })} label={sum.enabled ? "Reports, milestones and health tracking on" : "Off for this client"} />
          <span style={{ marginLeft: "auto" }}><HealthBadge health={sum.health} /></span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 16, alignItems: "end" }}>
          <Stat label="Campaign" value={launched ? (sum.state === "ended" ? "Ended" : `Week ${sum.week}`) : "Not live"} sub={stateText} />
          <div>
            <div style={{ fontSize: 12.5, color: T.textMute, marginBottom: 4 }}>Bookings goal</div>
            <input type="number" min="0" defaultValue={sum.goal ?? ""} placeholder="e.g. 7" style={{ ...inputStyle, width: 110 }}
              onBlur={(e) => patchClient({ campaign_booking_goal: e.target.value })} aria-label="Bookings goal" />
          </div>
          <div>
            <div style={{ fontSize: 12.5, color: T.textMute, marginBottom: 4 }}>Goal counts</div>
            <input defaultValue={sum.goal_label && sum.goal_label !== "bookings" ? sum.goal_label : ""} placeholder="assessments" style={{ ...inputStyle, width: 150 }}
              onBlur={(e) => patchClient({ campaign_goal_label: e.target.value })} aria-label="What the goal counts" />
          </div>
          {sum.budget ? (
            <div><div style={{ fontSize: 12.5, color: T.textMute, marginBottom: 8 }}>Ad budget: {money(sum.budget.spent)} of {money(sum.budget.cap)}</div><Progress value={sum.budget.spent} max={sum.budget.cap} /></div>
          ) : launched && sum.length_days ? (
            <div><div style={{ fontSize: 12.5, color: T.textMute, marginBottom: 8 }}>Day {sum.days_elapsed} of {sum.length_days}</div><Progress value={sum.days_elapsed || 0} max={sum.length_days} /></div>
          ) : null}
        </div>
        <div style={{ fontSize: 12.5, color: T.textMute, marginTop: 14, lineHeight: 1.5 }}>
          The campaign ends when the ad spend cap is reached; the final report is drafted then and waits for your approval, like check-ins and answers. Weekly reports go out automatically every Monday. Wording for all of it lives in Business Resources → Outreach Templates → Client Success Templates.
        </div>
      </Card>

      {/* Waiting on you */}
      {(drafts.length > 0 || open.length > 0 || reports.some((r) => r.kind === "final" && !r.sent_at)) && (
        <Card style={{ borderColor: "rgba(242,173,61,0.35)" }}>
          <SectionTitle title="Waiting on you" hint="Nothing here goes to the client until you approve it." />
          {reports.filter((r) => r.kind === "final" && !r.sent_at).map((r) => (
            <Row key={r.id}>
              <Pill tone="warn">Final report</Pill>
              <span style={{ flex: 1, minWidth: 200, fontSize: 13.5, color: T.text }}>{r.analysis?.headline || "Final campaign report"}</span>
              <LinkBtn href={r.url}>Review</LinkBtn>
              {r.artifact_url && <LinkBtn href={r.artifact_url}>Artifact</LinkBtn>}
              <button className="btn btn-primary" disabled={!!busy} onClick={() => sendReport(r)}>{busy === `send-${r.id}` ? "Sending…" : "Approve & send"}</button>
            </Row>
          ))}
          {drafts.map((k) => <CheckinDraft key={`${k.key}-${k.status}`} k={k} onChanged={load} />)}
          {open.map((f) => <Question key={f.id} f={f} onChanged={load} />)}
        </Card>
      )}

      {/* Reports */}
      <Card>
        <SectionTitle title="Reports" hint="Weekly reports send on Mondays; finals wait for your approval."
          right={launched && (
            <div style={{ display: "flex", gap: 14 }}>
              <LinkBtn disabled={!!busy} onClick={() => generate("weekly")}>{busy === "gen-weekly" ? "Building…" : "Preview weekly"}</LinkBtn>
              <LinkBtn disabled={!!busy} onClick={() => generate("final")}>{busy === "gen-final" ? "Building…" : "Build final"}</LinkBtn>
            </div>
          )} />
        {error && <div style={{ color: T.bad, fontSize: 13, marginBottom: 8 }}>{error}</div>}
        {reports.length === 0 ? <Empty>{launched ? "No reports yet. The first weekly report goes out next Monday." : "Reports start once the campaign launches."}</Empty> :
          reports.map((r) => (
            <Row key={r.id}>
              <span style={{ fontWeight: 600, color: T.text, fontSize: 13.5, minWidth: 92 }}>{r.kind === "final" ? "Final" : `Week ${r.week_number}`}</span>
              {r.sent_at ? <Pill tone="good">Sent {fmtDate(r.sent_at)}</Pill> : r.kind === "final" ? <Pill tone="warn">Awaiting approval</Pill> : <Pill>Preview</Pill>}
              <span style={{ fontSize: 12.5, color: r.view_count ? T.good : T.textMute }}>{r.sent_at ? (r.view_count ? `Opened ${r.view_count}×` : "Not opened yet") : ""}</span>
              <span style={{ flex: 1, minWidth: 180, fontSize: 13, color: T.textDim, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.analysis?.headline}</span>
              <LinkBtn href={r.url}>Open</LinkBtn>
              {!r.sent_at && r.kind !== "final" && <LinkBtn disabled={!!busy} onClick={() => sendReport(r)}>Send</LinkBtn>}
              <LinkBtn tone="bad" onClick={() => deleteReport(r)}>Delete</LinkBtn>
            </Row>
          ))}
      </Card>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 16 }}>
        {/* Patient quality */}
        <Card>
          <SectionTitle title="Patient quality" hint={'The clinic answers "good fit?" when it marks an appointment Showed + Closed.'} />
          {lqSum ? (
            <div style={{ display: "flex", gap: 24, marginBottom: 6 }}>
              <Stat label="Good fit (30 days)" value={lqSum.good} tone="good" />
              <Stat label="Not a fit" value={lqSum.not_fit} tone={lqSum.not_fit ? "bad" : undefined} />
            </div>
          ) : <Empty>No ratings yet.</Empty>}
          {lq.ratings.slice(0, 5).map((q) => (
            <Row key={q.id} style={{ alignItems: "flex-start" }}>
              <Pill tone={q.rating === "good" ? "good" : "bad"}>{q.rating === "good" ? "Good fit" : "Not a fit"}</Pill>
              <div style={{ flex: 1, minWidth: 0, fontSize: 13 }}>
                <div style={{ color: T.text }}>{q.prospect_name || "Patient"}</div>
                {q.note && <div style={{ color: T.textDim }}>"{q.note}"</div>}
              </div>
              <span style={{ fontSize: 12, color: T.textMute }}>{fmtDate(q.created_at)}</span>
            </Row>
          ))}
        </Card>

        {/* Milestones + answered */}
        <Card>
          <SectionTitle title="Milestones" hint="First lead, halfway, goal reached. Each is texted once per campaign." />
          {ms.length === 0 ? <Empty>None yet.</Empty> : ms.map((m) => (
            <Row key={`${m.key}-${m.created_at}`}>
              <span style={{ flex: 1, fontSize: 13.5, color: T.text }}>{MILESTONE_LABEL[m.key] || m.key}</span>
              {m.sent_at ? <Pill tone="good">Texted {fmtDate(m.sent_at)}</Pill> : <Pill>Passed before tracking</Pill>}
            </Row>
          ))}
          {answered.length > 0 && (
            <>
              <SectionTitle title="Past questions & feedback" style={{ marginTop: 18 }} />
              {answered.slice(0, 4).map((f) => (
                <Row key={f.id} style={{ alignItems: "flex-start" }}>
                  <div style={{ flex: 1, minWidth: 0, fontSize: 13 }}>
                    <div style={{ color: T.textDim }}>{f.message || (f.rating != null ? `Rated ${f.rating}` : "Feedback")}</div>
                    {f.answer && <div style={{ color: T.text, marginTop: 2 }}>↳ {f.answer}</div>}
                  </div>
                  <span style={{ fontSize: 12, color: T.textMute }}>{fmtDate(f.created_at)}</span>
                </Row>
              ))}
            </>
          )}
        </Card>
      </div>

      {/* Sent check-ins */}
      {checkins.some((k) => k.status === "sent") && (
        <Card>
          <SectionTitle title="Onboarding check-ins sent" />
          {checkins.filter((k) => k.status === "sent").map((k) => (
            <Row key={k.key}><span style={{ flex: 1, fontSize: 13.5, color: T.text }}>Day {String(k.key).replace("d", "")}: {k.subject}</span><Pill tone="good">Sent {fmtDate(k.sent_at)}</Pill></Row>
          ))}
        </Card>
      )}
    </div>
  );
}
