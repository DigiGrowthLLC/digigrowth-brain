import React, { Fragment, useState, useEffect, useRef, useCallback } from "react";
import { createPortal } from "react-dom";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer,
} from "recharts";
import { API } from "../api.js";
import { SECTIONS } from "../onboardingSections.js";
import PeriodToggle from "../components/PeriodToggle.jsx";
import ClientSetup from "./ClientSetup.jsx";
import ClientSuccessAgent from "./ClientSuccessAgent.jsx";
import { T, Card, PageHeader, SectionTitle, Tabs, Pill, Stat, Progress, Empty, Loading, HealthBadge, fmtDate, inputStyle } from "../ui.jsx";

function OnboardingAnswers({ clientId }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState({});

  useEffect(() => {
    fetch(API(`/clients/${clientId}`))
      .then((r) => r.json())
      .then((data) => { setDetail(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [clientId]);

  if (loading) {
    return <div style={{ padding: 16, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>LOADING…</div>;
  }
  if (!detail) return null;

  const onboarding = detail.onboarding || {};
  const answerOf = (answers, q) => (answers[q.key] || "").toString().trim();
  const totalQs = SECTIONS.reduce((n, s) => n + s.questions.length, 0);
  const totalAnswered = SECTIONS.reduce((n, s) => {
    const answers = onboarding[s.key]?.answers || {};
    return n + s.questions.filter((q) => answerOf(answers, q)).length;
  }, 0);
  const sectionsDone = SECTIONS.filter((s) => onboarding[s.key]?.completed_at).length;
  const allOpen = SECTIONS.every((s) => open[s.key]);
  const toggleAll = () => setOpen(allOpen ? {} : Object.fromEntries(SECTIONS.map((s) => [s.key, true])));

  return (
    <div style={{ padding: "14px 16px", borderTop: "1px solid rgba(58,123,213,0.1)", display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
        <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#5a7096", letterSpacing: "0.06em" }}>
          {sectionsDone}/{SECTIONS.length} SECTIONS COMPLETE · {totalAnswered}/{totalQs} QUESTIONS ANSWERED
        </span>
        <button
          onClick={toggleAll}
          style={{ marginLeft: "auto", background: "none", border: "none", cursor: "pointer", fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a7bd5", letterSpacing: "0.06em" }}
        >
          {allOpen ? "COLLAPSE ALL" : "EXPAND ALL"}
        </button>
      </div>
      {SECTIONS.map((s) => {
        const section = onboarding[s.key];
        const answers = section?.answers || {};
        const answered = s.questions.filter((q) => answerOf(answers, q)).length;
        const isOpen = !!open[s.key];
        const status = section?.completed_at
          ? { cls: "badge-green", text: "COMPLETE" }
          : answered > 0
            ? { cls: "badge-amber", text: "IN PROGRESS" }
            : { cls: "badge-gray", text: "NOT STARTED" };
        return (
          <div key={s.key} style={{ border: "1px solid rgba(58,123,213,0.15)", borderRadius: 8, background: "rgba(10,20,50,0.35)", overflow: "hidden" }}>
            <button
              onClick={() => setOpen((o) => ({ ...o, [s.key]: !o[s.key] }))}
              style={{ width: "100%", display: "flex", alignItems: "center", gap: 10, padding: "10px 12px", background: "none", border: "none", cursor: "pointer", textAlign: "left" }}
            >
              <span style={{ color: "#3a7bd5", fontSize: 10, width: 10, transform: isOpen ? "rotate(90deg)" : "none", transition: "transform 0.15s" }}>▶</span>
              <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600, fontSize: 12.5, color: "#c4d0e8" }}>{s.title}</span>
              <span style={{ marginLeft: "auto", fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#5a7096" }}>
                {answered}/{s.questions.length}
              </span>
              <span className={`badge ${status.cls}`} style={{ fontSize: 9, ...(status.cls === "badge-gray" ? { background: "rgba(90,112,150,0.15)", color: "#5a7096" } : {}) }}>
                {status.text}
              </span>
            </button>
            {isOpen && (
              <div style={{ display: "flex", flexDirection: "column", gap: 12, padding: "4px 12px 12px 32px", borderTop: "1px solid rgba(58,123,213,0.1)" }}>
                {s.questions.map((q) => {
                  const val = answerOf(answers, q);
                  return (
                    <div key={q.key} style={{ paddingTop: 8 }}>
                      <div style={{ fontSize: 11, color: "#5a7096", marginBottom: 3, lineHeight: 1.4 }}>{q.label}</div>
                      {val ? (
                        <div style={{ fontSize: 12.5, color: "#d0e8ff", lineHeight: 1.5, whiteSpace: "pre-wrap" }}>{val}</div>
                      ) : (
                        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>NOT ANSWERED</div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// A titled block inside a client page tab (Client info, Setup's To Do).
function DetailsSection({ title, collapsible, children }) {
  const [open, setOpen] = useState(!collapsible);
  return (
    <div style={{ borderTop: `1px solid ${T.line}` }}>
      <div onClick={collapsible ? () => setOpen((o) => !o) : undefined}
        style={{ padding: "16px 20px 4px", display: "flex", alignItems: "center", gap: 8, cursor: collapsible ? "pointer" : "default" }}>
        <span style={{ fontFamily: T.display, fontSize: 15, fontWeight: 600, color: T.text }}>{title}</span>
        {collapsible && <span style={{ fontSize: 12, color: T.textMute }}>{open ? "▾" : "▸"}</span>}
      </div>
      {open && children}
      {collapsible && !open && <div style={{ height: 12 }} />}
    </div>
  );
}

// ── Client list + client page (2026-11-17 redesign) ─────────────────────────
// The list is a grid of client cards (health, campaign, setup progress at a
// glance); opening one replaces the list with a full client page whose tabs
// replace the old expand-in-place Details panel.
const DETAIL_TABS = [
  { id: "overview", label: "Overview" },
  { id: "setup", label: "Setup" },
  { id: "agents", label: "Agents" },
  { id: "messages", label: "Messages" },
  { id: "info", label: "Client info" },
  { id: "finance", label: "Finance" },
];

const AVATAR_COLORS = ["#4d8ef0", "#2fd08f", "#8b6cf0", "#f2ad3d", "#22b8cf", "#e84393"];
const avatarColor = (id) => AVATAR_COLORS[(Number(id) || 0) % AVATAR_COLORS.length];

function Avatar({ client, size = 40 }) {
  return (
    <div style={{ width: size, height: size, borderRadius: size * 0.3, flexShrink: 0, display: "grid", placeItems: "center",
      fontFamily: T.display, fontWeight: 700, fontSize: size * 0.42, color: "#fff",
      background: `linear-gradient(135deg, ${avatarColor(client.id)}, rgba(40,87,160,0.9))` }}>
      {(client.name || "?").trim().charAt(0)}
    </div>
  );
}

function campaignLine(cs) {
  if (!cs || cs.state === "not_launched") return "Campaign not live yet";
  if (cs.state === "ended") return `Campaign ended ${fmtDate(cs.ends_at)}`;
  return `Week ${cs.week} · day ${cs.days_elapsed} of ${cs.length_days}`;
}

function ClientCard({ client, cs, setup, onOpen }) {
  const flags = [];
  if (client.is_test) flags.push(<Pill key="t" tone="info">Test</Pill>);
  if (client.token_revoked_at) flags.push(<Pill key="r" tone="bad">Portal revoked</Pill>);
  if (!client.linked_contact) flags.push(<Pill key="c" tone="warn">No contact</Pill>);
  if (cs?.open_questions > 0) flags.push(<Pill key="q" tone="info">{cs.open_questions} question{cs.open_questions > 1 ? "s" : ""}</Pill>);
  return (
    <Card pad={18} onClick={onOpen} style={{ display: "grid", gap: 14, minWidth: 0 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, minWidth: 0 }}>
        <Avatar client={client} />
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
            <span style={{ fontFamily: T.display, fontWeight: 600, fontSize: 15.5, color: T.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{client.name}</span>
            <span title={client.status} style={{ width: 7, height: 7, borderRadius: "50%", flexShrink: 0,
              background: client.status === "active" ? T.good : client.status === "paused" ? T.warn : "#5a6f8f" }} />
          </div>
          <div style={{ fontSize: 12.5, color: T.textMute, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {client.linked_contact?.owner || client.contact_name || "No contact set"} · {client.service_package === "foundations" ? "Foundations" : "Growth"}
          </div>
        </div>
        <HealthBadge health={cs?.health} compact />
      </div>
      <div style={{ display: "grid", gap: 6 }}>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12.5, color: T.textDim }}>
          <span>{campaignLine(cs)}</span>
          {setup && <span style={{ color: setup.done >= setup.total ? T.good : T.textMute }}>Setup {setup.done}/{setup.total}</span>}
        </div>
        {setup && <Progress value={setup.done} max={setup.total} tone={setup.done >= setup.total ? "good" : "info"} height={5} />}
      </div>
      {flags.length > 0 && <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>{flags}</div>}
    </Card>
  );
}

function ClientOverview({ client, cs, setup, onGoTab }) {
  const next = setup?.steps?.find((s) => !s.done);
  const waiting = (cs?.finals_waiting || 0) + (cs?.checkins_waiting || 0) + (cs?.open_questions || 0);
  const warnings = [];
  if (!client.linked_contact) warnings.push("No contact linked: onboarding emails and texts have nobody to go to.");
  if (!client.booking_notification_enabled) warnings.push("Booking texts to the client are off.");
  if (client.token_revoked_at) warnings.push("Their portal link is revoked.");
  return (
    <div style={{ display: "grid", gap: 16 }}>
      {warnings.length > 0 && (
        <Card pad={14} style={{ borderColor: "rgba(242,173,61,0.35)" }}>
          {warnings.map((w) => <div key={w} style={{ fontSize: 13, color: T.warn, padding: "2px 0" }}>• {w}</div>)}
        </Card>
      )}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 16 }}>
        <Card>
          <SectionTitle title="Campaign" right={<HealthBadge health={cs?.health} />} />
          <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
            <Stat label="Status" value={!cs || cs.state === "not_launched" ? "Not live" : cs.state === "ended" ? "Ended" : `Week ${cs.week}`} sub={campaignLine(cs)} />
            <Stat label="Bookings goal" value={cs?.goal ?? "–"} sub={`${cs?.length_days || 30}-day campaign`} />
          </div>
          {cs && cs.state !== "not_launched" && <div style={{ marginTop: 14 }}><Progress value={cs.days_elapsed || 0} max={cs.length_days || 30} /></div>}
        </Card>
        <Card onClick={() => onGoTab("setup")}>
          <SectionTitle title="Setup" right={setup && <Pill tone={setup.done >= setup.total ? "good" : "info"}>{setup.done}/{setup.total}</Pill>} />
          {setup ? <Progress value={setup.done} max={setup.total} tone={setup.done >= setup.total ? "good" : "info"} /> : <Loading />}
          <div style={{ fontSize: 13, color: T.textDim, marginTop: 12 }}>
            {next ? <>Next: <span style={{ color: T.text }}>{next.title}</span></> : "Everything is set up."}
          </div>
        </Card>
        <Card onClick={() => onGoTab("agents")} style={waiting ? { borderColor: "rgba(242,173,61,0.35)" } : undefined}>
          <SectionTitle title="Client success" right={waiting ? <Pill tone="warn">{waiting} waiting</Pill> : <Pill tone="good">All clear</Pill>} />
          <div style={{ display: "grid", gap: 6, fontSize: 13, color: T.textDim }}>
            <span>{cs?.reports || 0} report{cs?.reports === 1 ? "" : "s"} sent or drafted</span>
            {cs?.finals_waiting > 0 && <span style={{ color: T.warn }}>Final report waiting for your approval</span>}
            {cs?.checkins_waiting > 0 && <span style={{ color: T.warn }}>Onboarding check-in waiting for your approval</span>}
            {cs?.open_questions > 0 && <span style={{ color: T.warn }}>{cs.open_questions} client question{cs.open_questions > 1 ? "s" : ""} to answer</span>}
          </div>
        </Card>
      </div>
      <Card>
        <SectionTitle title="Contact" />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 14, fontSize: 13.5 }}>
          <div><div style={{ fontSize: 12, color: T.textMute }}>Owner</div><div style={{ color: T.text }}>{client.linked_contact?.owner || client.contact_name || "–"}</div></div>
          <div><div style={{ fontSize: 12, color: T.textMute }}>Email</div><div style={{ color: T.text, wordBreak: "break-all" }}>{client.email || "–"}</div></div>
          <div><div style={{ fontSize: 12, color: T.textMute }}>Phone</div><div style={{ color: T.text }}>{client.phone || "–"}</div></div>
          <div><div style={{ fontSize: 12, color: T.textMute }}>Onboarding form</div><div style={{ color: T.text }}>{client.onboarding_progress}</div></div>
        </div>
      </Card>
    </div>
  );
}

function ClientPage({ client, cs, onBack, onEdit, onRegenerate, onRevoke, onDelete, onLinkContact, reloadCs }) {
  const [tab, setTab] = useState("overview");
  const [setup, setSetup] = useState(null);
  const [menu, setMenu] = useState(false);
  const [copied, setCopied] = useState(false);
  const [linking, setLinking] = useState(false);
  const [pendingContact, setPendingContact] = useState(null);
  const [savingLink, setSavingLink] = useState(false);

  useEffect(() => {
    fetch(API(`/clients/${client.id}/setup`)).then((r) => (r.ok ? r.json() : null)).then(setSetup).catch(() => {});
  }, [client.id, tab]);
  useEffect(() => { reloadCs?.(); /* eslint-disable-next-line */ }, [tab]);

  const copyLink = () => navigator.clipboard.writeText(client.portal_url).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500); });
  const revoked = !!client.token_revoked_at;
  const waiting = (cs?.finals_waiting || 0) + (cs?.checkins_waiting || 0) + (cs?.open_questions || 0);
  const tabs = DETAIL_TABS.map((t) => (
    t.id === "setup" && setup ? { ...t, count: setup.total - setup.done || null } :
    t.id === "agents" && waiting ? { ...t, count: waiting, alert: true } : t
  ));
  const menuItem = { display: "block", width: "100%", textAlign: "left", background: "none", border: "none", padding: "9px 14px", fontSize: 13, color: T.text, cursor: "pointer", fontFamily: T.font };

  return (
    <div style={{ display: "grid", gap: 18 }}>
      <button onClick={onBack} style={{ justifySelf: "start", background: "none", border: "none", padding: 0, cursor: "pointer", color: "#8fb8ff", fontSize: 13, fontWeight: 600 }}>← All clients</button>
      <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
        <Avatar client={client} size={52} />
        <div style={{ flex: 1, minWidth: 220 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <h1 style={{ fontFamily: T.display, fontSize: 26, fontWeight: 700, color: T.text, margin: 0, letterSpacing: "-0.02em" }}>{client.name}</h1>
            <Pill tone={client.status === "active" ? "good" : client.status === "paused" ? "warn" : "neutral"} dot>{client.status}</Pill>
            {client.is_test && <Pill tone="info">Test client</Pill>}
          </div>
          <div style={{ fontSize: 13.5, color: T.textMute, marginTop: 4 }}>
            {client.linked_contact?.owner || client.contact_name || "No contact"} · {client.service_package === "foundations" ? "Foundations" : "Growth"} package · {campaignLine(cs)}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", position: "relative" }}>
          <a href={client.portal_url} target="_blank" rel="noreferrer" className="btn btn-secondary" style={{ textDecoration: "none" }}>Open portal ↗</a>
          <button className="btn btn-secondary" onClick={copyLink}>{copied ? "Copied" : "Copy portal link"}</button>
          <button className="btn btn-secondary" aria-label="More actions" onClick={() => setMenu((m) => !m)}>⋯</button>
          {menu && (
            <>
              <div style={{ position: "fixed", inset: 0, zIndex: 40 }} onClick={() => setMenu(false)} />
              <div style={{ position: "absolute", top: 42, right: 0, zIndex: 41, minWidth: 190, borderRadius: 12, overflow: "hidden", background: "#0f1a3c", border: `1px solid ${T.lineStrong}`, boxShadow: "0 12px 32px rgba(0,0,0,.5)" }}>
                <button style={menuItem} onClick={() => { onEdit(client); setMenu(false); }}>Edit client</button>
                <button style={menuItem} onClick={() => { setPendingContact(client.linked_contact || null); setLinking(true); setMenu(false); }}>Link contact</button>
                {revoked
                  ? <button style={menuItem} onClick={() => { onRegenerate(client.id); setMenu(false); }}>Regenerate portal link</button>
                  : <button style={menuItem} onClick={() => { onRevoke(client.id); setMenu(false); }}>Revoke portal link</button>}
                <button style={{ ...menuItem, color: T.bad }} onClick={() => { onDelete(client.id); setMenu(false); }}>Delete client</button>
              </div>
            </>
          )}
        </div>
      </div>

      {linking && (
        <Card>
          <SectionTitle title="Link a CRM contact" hint="The person onboarding emails and texts go to." />
          <ContactPicker selected={pendingContact} onSelect={setPendingContact} />
          <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 10 }}>
            <button className="btn btn-secondary" onClick={() => setLinking(false)}>Cancel</button>
            <button className="btn btn-primary" disabled={savingLink} onClick={async () => {
              setSavingLink(true); await onLinkContact(client.id, pendingContact?.id || null); setSavingLink(false); setLinking(false);
            }}>{savingLink ? "Saving…" : "Save link"}</button>
          </div>
        </Card>
      )}

      <Tabs tabs={tabs} value={tab} onChange={setTab} />

      <div>
        {tab === "overview" && <ClientOverview client={client} cs={cs} setup={setup} onGoTab={setTab} />}
        {tab === "setup" && (
          <Card pad={0} style={{ overflow: "hidden" }}>
            <ClientSetup clientId={client.id} onGoTab={(t) => setTab(t === "agents" ? "agents" : t === "info" ? "info" : t)} />
            <DetailsSection title="Client's To Do (what they see in their portal)" collapsible>
              <ClientLaunchChecklist clientId={client.id} />
            </DetailsSection>
          </Card>
        )}
        {tab === "agents" && <ClientAgentSetup clientId={client.id} />}
        {tab === "messages" && (
          <Card pad={0} style={{ overflow: "hidden" }}>
            <div style={{ padding: "18px 20px 0" }}><SectionTitle title="Automatic messages" hint="Confirmation, reminders, no-show, cancellation and follow-up texts for this client's patients." /></div>
            <ClientSequences clientId={client.id} />
          </Card>
        )}
        {tab === "info" && (
          <Card pad={0} style={{ overflow: "hidden" }}>
            <DetailsSection title="Onboarding answers"><OnboardingAnswers clientId={client.id} /></DetailsSection>
            <DetailsSection title="Requests"><ClientRequests clientId={client.id} /></DetailsSection>
            <DetailsSection title="Uploads"><ClientUploads clientId={client.id} /></DetailsSection>
            <DetailsSection title="Resources and logins"><ClientResources clientId={client.id} /></DetailsSection>
          </Card>
        )}
        {tab === "finance" && <Card pad={0} style={{ overflow: "hidden" }}><ClientFinance clientId={client.id} /></Card>}
      </div>
    </div>
  );
}

function ContactPicker({ selected, onSelect, disabled }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    if (!query.trim()) { setResults([]); return; }
    setSearching(true);
    const t = setTimeout(async () => {
      const r = await fetch(API(`/contacts?search=${encodeURIComponent(query.trim())}&limit=8`));
      if (r.ok) {
        const data = await r.json();
        setResults(data.contacts || []);
      }
      setSearching(false);
    }, 300);
    return () => clearTimeout(t);
  }, [query]);

  if (selected) {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 12px", borderRadius: 8, background: "rgba(52,211,153,0.08)", border: "1px solid rgba(52,211,153,0.25)" }}>
        <span style={{ fontSize: 11, color: "#5a7096" }}>Linked to:</span>
        <span style={{ flex: 1, fontFamily: "'Space Grotesk', sans-serif", fontSize: 13, color: "#d0e8ff" }}>
          {selected.owner || selected.business || "Unnamed contact"}{selected.owner && selected.business ? ` — ${selected.business}` : ""}
        </span>
        {!disabled && (
          <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={() => onSelect(null)}>CHANGE</button>
        )}
      </div>
    );
  }

  return (
    <div style={{ position: "relative" }}>
      <input
        className="dg-input"
        placeholder="Link the contact this deal came from — search by business, owner, or phone…"
        value={query}
        onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        disabled={disabled}
      />
      {open && query.trim() && (
        <div style={{
          position: "absolute", top: "calc(100% + 4px)", left: 0, right: 0, zIndex: 10,
          background: "#0d1a3a", border: "1px solid rgba(58,123,213,0.25)", borderRadius: 8,
          maxHeight: 220, overflowY: "auto",
        }}>
          {searching && (
            <div style={{ padding: "10px 14px", fontSize: 11, color: "#3a5a80" }}>Searching…</div>
          )}
          {!searching && results.length === 0 && (
            <div style={{ padding: "10px 14px", fontSize: 11, color: "#3a5a80" }}>No matching contacts</div>
          )}
          {results.map((c) => (
            <div
              key={c.id}
              onClick={() => { onSelect(c); setQuery(""); setResults([]); setOpen(false); }}
              style={{ padding: "10px 14px", cursor: "pointer", borderBottom: "1px solid rgba(58,123,213,0.08)" }}
              onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(58,123,213,0.1)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
            >
              <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 13, color: "#d0e8ff" }}>
                {c.owner || "—"}{c.business ? ` — ${c.business}` : ""}
              </div>
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80", marginTop: 2 }}>{c.phone}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ClientForm({ initial, onSave, onCancel, saving }) {
  const [form, setForm] = useState({
    name: initial?.name || "",
    contact_name: initial?.contact_name || "",
    email: initial?.email || "",
    phone: initial?.phone || "",
    notes: initial?.notes || "",
    booking_notification_enabled: initial?.booking_notification_enabled ?? true,
  });
  const [linkedContact, setLinkedContact] = useState(initial?.linked_contact || null);

  return (
    <div className="glass-card" style={{ padding: "18px 20px", marginBottom: 20, display: "flex", flexDirection: "column", gap: 12 }}>
      <ContactPicker selected={linkedContact} onSelect={setLinkedContact} disabled={!!initial} />
      {initial && (
        <div style={{ fontSize: 11, color: "#5a7096" }}>
          To change the linked contact on an existing client, use the LINK CONTACT button on its row instead.
        </div>
      )}
      <input
        className="dg-input"
        placeholder="Practice name…"
        value={form.name}
        onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
        autoFocus
      />
      <div style={{ display: "flex", gap: 10 }}>
        <input
          className="dg-input"
          placeholder="Contact name"
          value={form.contact_name}
          onChange={(e) => setForm((f) => ({ ...f, contact_name: e.target.value }))}
          style={{ flex: 1 }}
        />
        <input
          className="dg-input"
          placeholder="Phone"
          value={form.phone}
          onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
          style={{ flex: 1 }}
        />
      </div>
      <input
        className="dg-input"
        placeholder="Email"
        value={form.email}
        onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
      />
      <textarea
        className="dg-input"
        rows={2}
        placeholder="Notes (optional)"
        value={form.notes}
        onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
        style={{ resize: "vertical" }}
      />
      <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "#8aaad0", cursor: "pointer" }}>
        <input
          type="checkbox"
          checked={form.booking_notification_enabled}
          onChange={(e) => setForm((f) => ({ ...f, booking_notification_enabled: e.target.checked }))}
        />
        Text this client when a new appointment is booked for their lead
      </label>
      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
        <button className="btn btn-secondary" onClick={onCancel} style={{ fontSize: 11 }}>CANCEL</button>
        <button
          className="btn btn-primary"
          onClick={() => onSave({ ...form, contact_id: initial ? undefined : (linkedContact?.id || undefined) })}
          disabled={saving || !form.name.trim()}
          style={{ fontSize: 11 }}
        >
          {saving ? "SAVING…" : "SAVE CLIENT"}
        </button>
      </div>
    </div>
  );
}

// Accepts a plain YouTube watch/share URL (or an already-embeddable URL) and
// normalizes it to an /embed/ URL — the only form that works inside an
// <iframe> — so the person adding a video can just paste what's in their
// browser bar instead of hand-building an embed link.
function toEmbedUrl(url) {
  const trimmed = (url || "").trim();
  const watch = trimmed.match(/youtube\.com\/watch\?v=([\w-]+)/);
  if (watch) return `https://www.youtube.com/embed/${watch[1]}`;
  const short = trimmed.match(/youtu\.be\/([\w-]+)/);
  if (short) return `https://www.youtube.com/embed/${short[1]}`;
  return trimmed;
}

function VideoRow({ video, onDelete }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 14, padding: "10px 14px", borderRadius: 8, background: "rgba(255,255,255,0.02)", marginBottom: 6 }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600, fontSize: 13, color: "#d0e8ff" }}>{video.title}</div>
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80", marginTop: 2, wordBreak: "break-all" }}>{video.embed_url}</div>
      </div>
      <button className="btn btn-danger" style={{ fontSize: 10 }} onClick={() => onDelete(video.id)}>DELETE</button>
    </div>
  );
}

function VideosSection() {
  const [videos, setVideos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ title: "", description: "", url: "" });
  const [saving, setSaving] = useState(false);

  const load = async () => {
    const r = await fetch(API("/onboarding-videos"));
    if (r.ok) setVideos(await r.json());
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const save = async () => {
    if (!form.title.trim() || !form.url.trim()) return;
    setSaving(true);
    await fetch(API("/onboarding-videos"), {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: form.title.trim(),
        description: form.description.trim() || undefined,
        embed_url: toEmbedUrl(form.url),
        sort_order: videos.length,
      }),
    });
    setForm({ title: "", description: "", url: "" });
    setShowForm(false);
    setSaving(false);
    load();
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this video from every client's Get Started Videos?")) return;
    await fetch(API(`/onboarding-videos/${id}`), { method: "DELETE" });
    load();
  };

  return (
    <div style={{ marginTop: 32 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <div>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 18, fontWeight: 700, color: "#f0f4ff" }}>
            Get Started Videos
          </div>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80", letterSpacing: "0.14em", marginTop: 3 }}>
            SHARED ACROSS EVERY CLIENT PORTAL
          </div>
        </div>
        <button className="btn btn-primary" style={{ fontSize: 11, padding: "8px 18px" }} onClick={() => setShowForm((s) => !s)}>
          {showForm ? "CANCEL" : "+ ADD VIDEO"}
        </button>
      </div>

      {showForm && (
        <div className="glass-card" style={{ padding: "18px 20px", marginBottom: 16, display: "flex", flexDirection: "column", gap: 12 }}>
          <input className="dg-input" placeholder="Title, e.g. Give Meta Ads Manager Access" value={form.title}
            onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} autoFocus />
          <input className="dg-input" placeholder="YouTube link (paste from your browser bar)" value={form.url}
            onChange={(e) => setForm((f) => ({ ...f, url: e.target.value }))} />
          <textarea className="dg-input" rows={2} placeholder="Description (optional)" value={form.description}
            onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} style={{ resize: "vertical" }} />
          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <button className="btn btn-primary" onClick={save} disabled={saving || !form.title.trim() || !form.url.trim()} style={{ fontSize: 11 }}>
              {saving ? "SAVING…" : "SAVE VIDEO"}
            </button>
          </div>
        </div>
      )}

      <div className="glass-card" style={{ padding: "10px 8px" }}>
        {loading && <div style={{ padding: 20, textAlign: "center", fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52" }}>LOADING…</div>}
        {!loading && videos.length === 0 && (
          <div style={{ padding: 20, textAlign: "center", fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52" }}>NO VIDEOS YET</div>
        )}
        {videos.map((v) => <VideoRow key={v.id} video={v} onDelete={remove} />)}
      </div>
    </div>
  );
}

const ACTION_ITEM_LINK_OPTIONS = [
  { value: "", label: "— no link —" },
  { value: "videos", label: "Get Started Videos" },
  { value: "leads", label: "Leads" },
  { value: "appointments", label: "Appointments" },
  { value: "dashboard", label: "Dashboard" },
];
const ACTION_ITEM_LINK_LABELS = Object.fromEntries(ACTION_ITEM_LINK_OPTIONS.map((o) => [o.value, o.label]));

// Which client services an item belongs to (backend client_services.py).
// None ticked = every client sees it; otherwise only clients with one of them.
let _serviceOptions = null;
function ServiceTags({ path, item, onChanged }) {
  const [opts, setOpts] = useState(_serviceOptions || []);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (_serviceOptions) return;
    fetch(API("/client-services")).then((r) => (r.ok ? r.json() : [])).then((d) => { _serviceOptions = d; setOpts(d); });
  }, []);
  const have = item.services || [];
  const toggle = async (id) => {
    setBusy(true);
    await fetch(API(`${path}/${item.id}`), {
      method: "PATCH", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ services: have.includes(id) ? have.filter((x) => x !== id) : [...have, id] }),
    });
    setBusy(false);
    onChanged();
  };
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 6, alignItems: "center" }}>
      <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80", letterSpacing: "0.06em" }}>
        {have.length ? "ONLY FOR:" : "EVERY CLIENT · LIMIT TO:"}
      </span>
      {opts.map((o) => {
        const on = have.includes(o.id);
        return (
          <button key={o.id} disabled={busy} onClick={() => toggle(o.id)} title={o.hint} style={{
            fontSize: 9.5, padding: "2px 7px", borderRadius: 999, cursor: "pointer", fontFamily: "'Space Grotesk', sans-serif",
            border: on ? "1px solid rgba(74,222,128,0.5)" : "1px solid rgba(58,123,213,0.15)",
            background: on ? "rgba(74,222,128,0.12)" : "transparent", color: on ? "#bff0d0" : "#3f5f88",
          }}>{o.label}</button>
        );
      })}
    </div>
  );
}

function ActionItemRow({ item, onDelete, onChanged }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 14, padding: "10px 14px", borderRadius: 8, background: "rgba(255,255,255,0.02)", marginBottom: 6 }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600, fontSize: 13, color: "#d0e8ff" }}>{item.title}</div>
        {item.description && (
          <div style={{ fontSize: 11, color: "#5a7096", marginTop: 2 }}>{item.description}</div>
        )}
        {item.link_tab && (
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", marginTop: 4, letterSpacing: "0.06em" }}>
            LINKS TO {(ACTION_ITEM_LINK_LABELS[item.link_tab] || item.link_tab).toUpperCase()}
          </div>
        )}
        {item.link_url && (
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", marginTop: 4, letterSpacing: "0.06em", wordBreak: "break-all" }}>
            LINKS TO {item.link_url}
          </div>
        )}
        <ServiceTags path="/action-items" item={item} onChanged={onChanged} />
      </div>
      <button className="btn btn-danger" style={{ fontSize: 10 }} onClick={() => onDelete(item.id)}>DELETE</button>
    </div>
  );
}

function ActionItemsSection() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ title: "", description: "", link_tab: "", link_url: "" });
  const [saving, setSaving] = useState(false);

  const load = async () => {
    const r = await fetch(API("/action-items"));
    if (r.ok) setItems(await r.json());
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const save = async () => {
    if (!form.title.trim()) return;
    setSaving(true);
    await fetch(API("/action-items"), {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: form.title.trim(),
        description: form.description.trim() || undefined,
        link_tab: form.link_tab || undefined,
        link_url: form.link_url.trim() || undefined,
        sort_order: items.length,
      }),
    });
    setForm({ title: "", description: "", link_tab: "", link_url: "" });
    setShowForm(false);
    setSaving(false);
    load();
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this Next Step from every client's onboarding checklist?")) return;
    await fetch(API(`/action-items/${id}`), { method: "DELETE" });
    load();
  };

  return (
    <div style={{ marginTop: 32 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <div>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 18, fontWeight: 700, color: "#f0f4ff" }}>
            Onboarding Next Steps
          </div>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80", letterSpacing: "0.14em", marginTop: 3 }}>
            SHARED CHECKLIST ON EVERY CLIENT'S ONBOARDING TAB — THE CLIENT CHECKS THESE OFF
          </div>
        </div>
        <button className="btn btn-primary" style={{ fontSize: 11, padding: "8px 18px" }} onClick={() => setShowForm((s) => !s)}>
          {showForm ? "CANCEL" : "+ ADD STEP"}
        </button>
      </div>

      {showForm && (
        <div className="glass-card" style={{ padding: "18px 20px", marginBottom: 16, display: "flex", flexDirection: "column", gap: 12 }}>
          <input className="dg-input" placeholder="Title, e.g. Give Meta Ads Manager Access" value={form.title}
            onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} autoFocus />
          <textarea className="dg-input" rows={2} placeholder="Description — what they need to do (optional)" value={form.description}
            onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} style={{ resize: "vertical" }} />
          <div>
            <div style={{ fontSize: 11, color: "#5a7096", marginBottom: 4 }}>Links to a portal tab (optional) — shows a "Go to…" button</div>
            <select className="dg-input" value={form.link_tab} onChange={(e) => setForm((f) => ({ ...f, link_tab: e.target.value }))}>
              {ACTION_ITEM_LINK_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
          <div>
            <div style={{ fontSize: 11, color: "#5a7096", marginBottom: 4 }}>Or an external link (optional) — e.g. a Calendly booking link</div>
            <input className="dg-input" placeholder="https://calendly.com/…" value={form.link_url}
              onChange={(e) => setForm((f) => ({ ...f, link_url: e.target.value }))} />
          </div>
          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <button className="btn btn-primary" onClick={save} disabled={saving || !form.title.trim()} style={{ fontSize: 11 }}>
              {saving ? "SAVING…" : "SAVE STEP"}
            </button>
          </div>
        </div>
      )}

      <div className="glass-card" style={{ padding: "10px 8px" }}>
        {loading && <div style={{ padding: 20, textAlign: "center", fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52" }}>LOADING…</div>}
        {!loading && items.length === 0 && (
          <div style={{ padding: 20, textAlign: "center", fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52" }}>NO STEPS YET</div>
        )}
        {items.map((item) => <ActionItemRow key={item.id} item={item} onDelete={remove} onChanged={load} />)}
      </div>
    </div>
  );
}

// ---------------- Launch checklist (agency-run "To Do" tab) ----------------
//
// Separate catalog from ActionItemsSection above: those are onboarding
// steps the CLIENT completes. This is DigiGrowth's own launch-readiness
// checklist — the client's portal shows it read-only (LaunchChecklistTab in
// ClientPortal.jsx); completion is set here, per-client, by whoever on the
// team actually does the work (see the per-client toggle panel added to
// ClientRow below).

// Post-launch items are generic timeline milestones, so they're excluded
// from the admin catalog editor below; they're still checked off per client
// in ClientLaunchChecklist's Post Launch view, and the client portal's
// LaunchChecklistTab renders them (fetched straight from the API).
const CHECKLIST_PHASE_OPTIONS = [
  { value: "prelaunch", label: "Prelaunch" },
];

function ChecklistItemRow({ item, onDelete, onChanged }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 14, padding: "10px 14px", borderRadius: 8, background: "rgba(255,255,255,0.02)", marginBottom: 6 }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600, fontSize: 13, color: "#d0e8ff" }}>{item.title}</div>
        {item.description && (
          <div style={{ fontSize: 11, color: "#5a7096", marginTop: 2 }}>{item.description}</div>
        )}
        <ServiceTags path="/launch-checklist-items" item={item} onChanged={onChanged} />
      </div>
      <button className="btn btn-danger" style={{ fontSize: 10 }} onClick={() => onDelete(item.id)}>DELETE</button>
    </div>
  );
}

function LaunchChecklistSection() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ title: "", description: "", phase: "prelaunch" });
  const [saving, setSaving] = useState(false);

  const load = async () => {
    const r = await fetch(API("/launch-checklist-items"));
    if (r.ok) setItems(await r.json());
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const save = async () => {
    if (!form.title.trim()) return;
    setSaving(true);
    await fetch(API("/launch-checklist-items"), {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: form.title.trim(),
        description: form.description.trim() || undefined,
        phase: form.phase,
        sort_order: items.filter((i) => i.phase === form.phase).length,
      }),
    });
    setForm({ title: "", description: "", phase: form.phase });
    setShowForm(false);
    setSaving(false);
    load();
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this item from the launch checklist? It'll disappear from every client's To Do tab.")) return;
    await fetch(API(`/launch-checklist-items/${id}`), { method: "DELETE" });
    load();
  };

  const prelaunch = items.filter((i) => (i.phase || "prelaunch") === "prelaunch");

  return (
    <div style={{ marginTop: 32 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <div>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 18, fontWeight: 700, color: "#f0f4ff" }}>
            Launch Checklist (To Do tab)
          </div>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80", letterSpacing: "0.14em", marginTop: 3 }}>
            AGENCY-COMPLETED — CLIENT SEES READ-ONLY PROGRESS. TOGGLE PER CLIENT ON ITS ROW BELOW.
          </div>
        </div>
        <button className="btn btn-primary" style={{ fontSize: 11, padding: "8px 18px" }} onClick={() => setShowForm((s) => !s)}>
          {showForm ? "CANCEL" : "+ ADD ITEM"}
        </button>
      </div>

      {showForm && (
        <div className="glass-card" style={{ padding: "18px 20px", marginBottom: 16, display: "flex", flexDirection: "column", gap: 12 }}>
          <input className="dg-input" placeholder="Title, e.g. Set up SMS marketing" value={form.title}
            onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} autoFocus />
          <textarea className="dg-input" rows={2} placeholder="Description (optional)" value={form.description}
            onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} style={{ resize: "vertical" }} />
          <div>
            <div style={{ fontSize: 11, color: "#5a7096", marginBottom: 4 }}>Phase</div>
            <select className="dg-input" value={form.phase} onChange={(e) => setForm((f) => ({ ...f, phase: e.target.value }))}>
              {CHECKLIST_PHASE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <button className="btn btn-primary" onClick={save} disabled={saving || !form.title.trim()} style={{ fontSize: 11 }}>
              {saving ? "SAVING…" : "SAVE ITEM"}
            </button>
          </div>
        </div>
      )}

      {CHECKLIST_PHASE_OPTIONS.map((phaseOpt) => {
        const phaseItems = prelaunch;
        return (
          <div key={phaseOpt.value} style={{ marginBottom: 18 }}>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80", letterSpacing: "0.12em", marginBottom: 8 }}>
              {phaseOpt.label.toUpperCase()}
            </div>
            <div className="glass-card" style={{ padding: "10px 8px" }}>
              {loading && <div style={{ padding: 20, textAlign: "center", fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52" }}>LOADING…</div>}
              {!loading && phaseItems.length === 0 && (
                <div style={{ padding: 20, textAlign: "center", fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52" }}>NO ITEMS YET</div>
              )}
              {phaseItems.map((item) => <ChecklistItemRow key={item.id} item={item} onDelete={remove} onChanged={load} />)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// Per-client toggle panel — expandable from ClientRow, lets whoever's doing
// the setup work mark this specific client's launch-checklist items done as
// they actually get completed. Read-only catalog (titles/phases come from
// LaunchChecklistSection above); only completion status is per-client here.
// A Prelaunch / Post Launch dropdown switches which phase is shown, so the
// post-launch milestones the client's portal shows can be checked off here too.
const CLIENT_CHECKLIST_PHASES = [
  { value: "prelaunch", label: "Prelaunch" },
  { value: "post_launch", label: "Post Launch" },
];

function ClientLaunchChecklist({ clientId }) {
  const [allItems, setAllItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [phase, setPhase] = useState("prelaunch");

  const load = async () => {
    const r = await fetch(API(`/clients/${clientId}/launch-checklist`));
    if (r.ok) setAllItems(await r.json());
    setLoading(false);
  };

  const items = allItems.filter((i) => (i.phase || "prelaunch") === phase);
  const countFor = (p) => {
    const inPhase = allItems.filter((i) => (i.phase || "prelaunch") === p);
    return `${inPhase.filter((i) => i.completed_at).length}/${inPhase.length}`;
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [clientId]);

  const toggle = async (item) => {
    const completed = !item.completed_at;
    const r = await fetch(API(`/clients/${clientId}/launch-checklist/${item.id}`), {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ completed }),
    });
    if (r.ok) {
      const updated = await r.json();
      setAllItems((prev) => prev.map((i) => (i.id === item.id ? { ...i, completed_at: updated.completed_at } : i)));
    }
  };

  if (loading) {
    return <div style={{ padding: 16, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>LOADING…</div>;
  }

  return (
    <div style={{ padding: "14px 16px", borderTop: "1px solid rgba(58,123,213,0.1)", display: "flex", flexDirection: "column", gap: 8 }}>
      <select className="dg-input" value={phase} onChange={(e) => setPhase(e.target.value)}
        style={{ fontSize: 12, padding: "6px 10px", width: "auto", alignSelf: "flex-start", marginBottom: 4 }}>
        {CLIENT_CHECKLIST_PHASES.map((p) => (
          <option key={p.value} value={p.value}>{p.label} ({countFor(p.value)})</option>
        ))}
      </select>
      {items.length === 0 && (
        <div style={{ padding: "8px 0", fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>
          NO {phase === "post_launch" ? "POST LAUNCH" : "PRELAUNCH"} ITEMS YET
        </div>
      )}
      {items.map((item) => {
        const done = !!item.completed_at;
        return (
          <div
            key={item.id}
            style={{
              padding: "8px 12px", borderRadius: 8,
              background: done ? "rgba(20,200,130,0.06)" : "rgba(255,255,255,0.02)",
            }}
          >
            <div onClick={() => toggle(item)} style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }}>
              <span style={{
                flexShrink: 0, width: 16, height: 16, borderRadius: 4,
                border: done ? "1px solid #14c882" : "1px solid rgba(58,123,213,0.35)",
                background: done ? "#14c882" : "transparent",
                color: "#06110c", fontSize: 10, fontWeight: 700,
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>{done ? "✓" : ""}</span>
              <span style={{ fontSize: 12.5, color: done ? "#8fd9bd" : "#d0e8ff", textDecoration: done ? "line-through" : "none" }}>
                {item.title}
              </span>
            </div>
            {item.description && (
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#5a7aa0", marginTop: 6, marginLeft: 26, lineHeight: 1.5, whiteSpace: "pre-wrap" }}>
                {item.description}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// Per-client editable outreach copy — Appointment Reminder / No Show /
// Cancellation, previewed read-only in the client's own portal (Sequences
// tab). Not wired to any real send yet; this is just content editing.
const SEQUENCE_GROUP_LABELS = {
  prospect_followup: { title: "Prospect Follow-Up", timing: "3h / +24h / +3d / +7d after no reply" },
  appointment_reminder: { title: "Appointment Reminders", timing: "on booking / 24h / 6h / 1h before" },
  no_show: { title: "No Show Follow-Up", timing: "now / 3h / 24h" },
  cancellation: { title: "Cancellation Follow-Up", timing: "now / 3h / 24h" },
};
const SEQUENCE_GROUP_ORDER = ["prospect_followup", "appointment_reminder", "no_show", "cancellation"];

// On/off pill for a sequence message or a whole sequence. The same
// client_sequence_steps.enabled flag is switchable from the client's portal.
function OnOffSwitch({ on, onChange, busy, text }) {
  return (
    <button
      type="button" role="switch" aria-checked={on} disabled={busy}
      onClick={() => onChange(!on)}
      title={on ? "On: click to turn off" : "Off: click to turn on"}
      style={{ display: "inline-flex", alignItems: "center", gap: 6, background: "transparent", border: "none", padding: 0, cursor: busy ? "wait" : "pointer" }}
    >
      <span style={{
        position: "relative", width: 30, height: 16, borderRadius: 999, flexShrink: 0,
        background: on ? "rgba(20,200,130,0.25)" : "rgba(90,111,143,0.2)",
        border: `1px solid ${on ? "rgba(20,200,130,0.6)" : "rgba(90,111,143,0.45)"}`,
      }}>
        <span style={{
          position: "absolute", top: 1, left: on ? 15 : 1, width: 12, height: 12, borderRadius: "50%",
          background: on ? "#14c882" : "#5a6f8f", transition: "left 0.15s",
        }} />
      </span>
      <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, letterSpacing: "0.08em", color: on ? "#14c882" : "#5a6f8f" }}>
        {text || (on ? "ON" : "OFF")}
      </span>
    </button>
  );
}

function SequenceStepEditor({ step, onSaved }) {
  const [subject, setSubject] = useState(step.subject || "");
  const [body, setBody] = useState(step.body || "");
  const [saving, setSaving] = useState(false);
  const [toggling, setToggling] = useState(false);
  const dirty = subject !== (step.subject || "") || body !== (step.body || "");

  const toggle = async (enabled) => {
    setToggling(true);
    const r = await fetch(API(`/clients/${step.client_id}/sequences/${step.id}`), {
      method: "PATCH", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled }),
    });
    if (r.ok) onSaved(await r.json());
    setToggling(false);
  };

  const save = async () => {
    setSaving(true);
    const r = await fetch(API(`/clients/${step.client_id}/sequences/${step.id}`), {
      method: "PATCH", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ subject: subject || null, body }),
    });
    if (r.ok) onSaved(await r.json());
    setSaving(false);
  };

  return (
    <div style={{ padding: "10px 12px", borderRadius: 8, background: "rgba(255,255,255,0.02)", marginBottom: 8, opacity: step.enabled === false ? 0.55 : 1 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
        <span style={{ fontSize: 12.5, fontWeight: 600, color: "#d0e8ff", flex: 1 }}>{step.label}</span>
        <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5" }}>{step.channel.toUpperCase()}</span>
        <OnOffSwitch on={step.enabled !== false} onChange={toggle} busy={toggling} />
      </div>
      <textarea
        className="dg-input" rows={3} value={body}
        onChange={(e) => setBody(e.target.value)}
        style={{ width: "100%", boxSizing: "border-box", fontSize: 12, resize: "vertical", marginBottom: 6 }}
      />
      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={save} disabled={saving || !dirty}>
          {saving ? "SAVING…" : "SAVE"}
        </button>
      </div>
    </div>
  );
}

function ClientSequences({ clientId }) {
  const [steps, setSteps] = useState([]);
  const [loading, setLoading] = useState(true);
  const [togglingKey, setTogglingKey] = useState(null);
  const [open, setOpen] = useState({});

  const setSequenceEnabled = async (key, enabled) => {
    setTogglingKey(key);
    const r = await fetch(API(`/clients/${clientId}/sequence-keys/${key}/enabled`), {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled }),
    });
    if (r.ok) setSteps((prev) => prev.map((s) => (s.sequence_key === key ? { ...s, enabled } : s)));
    setTogglingKey(null);
  };

  const load = async () => {
    const r = await fetch(API(`/clients/${clientId}/sequences`));
    if (r.ok) setSteps((await r.json()).map((s) => ({ ...s, client_id: clientId })));
    setLoading(false);
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [clientId]);

  if (loading) return <div style={{ padding: 16, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>LOADING…</div>;
  if (steps.length === 0) {
    return <div style={{ padding: 16, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>NO SEQUENCE STEPS FOR THIS CLIENT</div>;
  }

  const groupKeys = SEQUENCE_GROUP_ORDER.filter((key) => steps.some((s) => s.sequence_key === key));
  const allOpen = groupKeys.every((key) => open[key]);
  const toggleAll = () => setOpen(allOpen ? {} : Object.fromEntries(groupKeys.map((key) => [key, true])));
  const totalOn = steps.filter((s) => s.enabled !== false).length;

  return (
    <div style={{ padding: "14px 16px", borderTop: "1px solid rgba(58,123,213,0.1)", display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
        <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#5a7096", letterSpacing: "0.06em" }}>
          {groupKeys.length} SEQUENCES · {totalOn}/{steps.length} MESSAGES ON
        </span>
        <button
          onClick={toggleAll}
          style={{ marginLeft: "auto", background: "none", border: "none", cursor: "pointer", fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a7bd5", letterSpacing: "0.06em" }}
        >
          {allOpen ? "COLLAPSE ALL" : "EXPAND ALL"}
        </button>
      </div>
      {groupKeys.map((key) => {
        const group = steps.filter((s) => s.sequence_key === key);
        const onCount = group.filter((s) => s.enabled !== false).length;
        const label = SEQUENCE_GROUP_LABELS[key] || { title: key, timing: "" };
        const channels = [...new Set(group.map((s) => s.channel.toUpperCase()))].join(" + ");
        const isOpen = !!open[key];
        return (
          <div key={key} style={{ border: "1px solid rgba(58,123,213,0.15)", borderRadius: 8, background: "rgba(10,20,50,0.35)", overflow: "hidden" }}>
            <div
              role="button" tabIndex={0}
              onClick={() => setOpen((o) => ({ ...o, [key]: !o[key] }))}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setOpen((o) => ({ ...o, [key]: !o[key] })); } }}
              style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 12px", cursor: "pointer" }}
            >
              <span style={{ color: "#3a7bd5", fontSize: 10, width: 10, transform: isOpen ? "rotate(90deg)" : "none", transition: "transform 0.15s" }}>▶</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600, fontSize: 12.5, color: "#c4d0e8" }}>{label.title}</div>
                {label.timing && (
                  <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9.5, color: "#3a5a80", marginTop: 2 }}>{label.timing}</div>
                )}
              </div>
              <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#5a7096" }}>
                {group.length} MSG · {channels}
              </span>
              <span onClick={(e) => e.stopPropagation()}>
                <OnOffSwitch
                  on={onCount > 0}
                  onChange={(enabled) => setSequenceEnabled(key, enabled)}
                  busy={togglingKey === key}
                  text={onCount === group.length ? "ALL ON" : onCount === 0 ? "ALL OFF" : `${onCount}/${group.length} ON`}
                />
              </span>
            </div>
            {/* Hidden rather than unmounted so unsaved edits survive collapsing. */}
            <div style={{ display: isOpen ? "block" : "none", padding: "10px 12px 4px 32px", borderTop: "1px solid rgba(58,123,213,0.1)" }}>
              {group.map((step) => (
                <SequenceStepEditor
                  key={step.id}
                  step={step}
                  onSaved={(updated) => setSteps((prev) => prev.map((s) => (s.id === updated.id ? { ...updated, client_id: clientId } : s)))}
                />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ---------------- Per-client finance ledger (Finance tab) ----------------
//
// What it costs DigiGrowth to deliver/run this client's campaign (ad spend,
// tools, labor) against the revenue that client's own business generated
// from it — same manual-ledger shape as FinancesPanel.jsx's agency-wide
// P&L, just scoped to client_transactions via routers/client_finance.py, so
// ROAS (revenue / ad spend) can be tracked per client instead of only
// agency-wide.

const CLIENT_FINANCE_EXPENSE_CATEGORIES = ["Ad Spend", "Software & Tools", "Labor & Fulfillment", "Other"];
const CLIENT_FINANCE_PERIOD_OPTIONS = [[7, "7D"], [30, "30D"], [90, "90D"], [365, "1Y"]];

function clientFinanceMoney(v) {
  if (v == null) return "—";
  return `$${Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function ClientFinanceTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: "rgba(10,18,48,0.95)", border: "1px solid rgba(58,123,213,0.2)",
      borderRadius: 10, padding: "8px 14px", fontSize: 12,
      fontFamily: "'Space Grotesk', sans-serif",
    }}>
      <div style={{ color: "#8aaad0", marginBottom: 4 }}>{label}</div>
      {payload.map((p) => (
        <div key={p.dataKey} style={{ color: p.color, fontWeight: 600 }}>
          {p.name}: ${p.value?.toLocaleString()}
        </div>
      ))}
    </div>
  );
}

function ClientFinanceSummaryCard({ label, value, color, sub }) {
  return (
    <div className="stat-card">
      <div className="stat-card-label">{label}</div>
      <div className="stat-card-value" style={{ color: color || "#f0f4ff" }}>{value ?? "—"}</div>
      {sub && <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80", marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

function AddClientTransactionModal({ clientId, onClose, onSaved }) {
  const today = new Date().toISOString().slice(0, 10);
  const [form, setForm] = useState({
    is_income: false,
    description: "",
    amount: "",
    date: today,
    category: "Ad Spend",
    notes: "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const set = (k, v) => setForm((prev) => ({ ...prev, [k]: v }));

  const handleSave = async () => {
    const amt = parseFloat(form.amount);
    if (!form.amount || isNaN(amt) || amt <= 0) { setError("Enter a valid amount greater than 0."); return; }
    setSaving(true);
    setError(null);
    try {
      const resp = await fetch(API(`/clients/${clientId}/finance/transactions`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          is_income: form.is_income,
          description: form.description.trim() || undefined,
          amount: amt,
          date: form.date,
          category: form.is_income ? "Client Revenue" : form.category,
          notes: form.notes.trim() || null,
        }),
      });
      if (!resp.ok) { setError(await resp.text()); return; }
      onSaved(await resp.json());
      onClose();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
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
      <div className="glass-card w-full sm:w-[440px]" style={{ padding: "28px 32px" }} onClick={(e) => e.stopPropagation()}>
        <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 17, fontWeight: 700, color: "#f0f4ff", marginBottom: 22 }}>
          Add Entry
        </div>

        <div style={{ display: "flex", marginBottom: 20, background: "rgba(10,18,48,0.7)", borderRadius: 10, padding: 4, gap: 4 }}>
          {[[false, "Expense"], [true, "Client Revenue"]].map(([val, label]) => (
            <button key={label} onClick={() => set("is_income", val)} style={{
              flex: 1, fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, fontWeight: 600,
              padding: "9px 0", borderRadius: 8, border: "none", cursor: "pointer",
              background: form.is_income === val
                ? val ? "linear-gradient(135deg, #0d7a4e, #14c882)" : "linear-gradient(135deg, #7a3a00, #f0a028)"
                : "transparent",
              color: form.is_income === val ? "#fff" : "#4a6080",
              transition: "all 0.15s",
            }}>{label}</button>
          ))}
        </div>

        <div style={{ marginBottom: 14 }}>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", letterSpacing: "0.12em", marginBottom: 5 }}>DESCRIPTION</div>
          <input
            className="dg-input" type="text"
            style={{ width: "100%", fontSize: 13, boxSizing: "border-box" }}
            placeholder={form.is_income ? "e.g. Attributed sales from campaign…" : "e.g. Meta Ads spend, editor hours…"}
            value={form.description}
            onChange={(e) => set("description", e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSave()}
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2" style={{ gap: 12, marginBottom: 14 }}>
          <div>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", letterSpacing: "0.12em", marginBottom: 5 }}>AMOUNT ($)</div>
            <input
              className="dg-input" type="number" min="0" step="0.01"
              style={{ width: "100%", fontSize: 13, boxSizing: "border-box" }}
              placeholder="0.00"
              value={form.amount}
              onChange={(e) => set("amount", e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSave()}
            />
          </div>
          <div>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", letterSpacing: "0.12em", marginBottom: 5 }}>DATE</div>
            <input
              className="dg-input" type="date"
              style={{ width: "100%", fontSize: 13, boxSizing: "border-box" }}
              value={form.date}
              onChange={(e) => set("date", e.target.value)}
            />
          </div>
        </div>

        {!form.is_income && (
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", letterSpacing: "0.12em", marginBottom: 5 }}>CATEGORY</div>
            <select
              className="dg-input"
              style={{ width: "100%", fontSize: 13 }}
              value={form.category}
              onChange={(e) => set("category", e.target.value)}
            >
              {CLIENT_FINANCE_EXPENSE_CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            {form.category === "Ad Spend" && (
              <div style={{ fontSize: 10, color: "#5a7096", marginTop: 5 }}>
                Counts as the ROAS denominator for this client.
              </div>
            )}
          </div>
        )}

        <div style={{ marginBottom: 20 }}>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", letterSpacing: "0.12em", marginBottom: 5 }}>NOTES (OPTIONAL)</div>
          <input
            className="dg-input" type="text"
            style={{ width: "100%", fontSize: 13, boxSizing: "border-box" }}
            placeholder="Optional note…"
            value={form.notes}
            onChange={(e) => set("notes", e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSave()}
          />
        </div>

        {error && (
          <div style={{
            marginBottom: 14, padding: "8px 12px", borderRadius: 8,
            background: "rgba(220,60,60,0.08)", border: "1px solid rgba(220,60,60,0.2)",
            fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#dc3c3c", letterSpacing: "0.04em",
          }}>
            {error}
          </div>
        )}

        <div style={{ display: "flex", gap: 10 }}>
          <button onClick={onClose} className="btn btn-secondary" style={{ flex: 1, fontSize: 12 }}>Cancel</button>
          <button onClick={handleSave} disabled={saving} className="btn btn-primary" style={{ flex: 1, fontSize: 12 }}>
            {saving ? "Saving…" : `Add ${form.is_income ? "Revenue" : "Expense"}`}
          </button>
        </div>
      </div>
    </div>
  );
}

function ClientFinance({ clientId }) {
  const [days, setDays] = useState(30);
  const [summary, setSummary] = useState(null);
  const [categories, setCategories] = useState(null);
  const [txns, setTxns] = useState(null);
  const [txnType, setTxnType] = useState("all");
  const [showAddForm, setShowAddForm] = useState(false);
  const [expandedTxn, setExpandedTxn] = useState(null);
  const [deletingId, setDeletingId] = useState(null);
  const [hoveredTxn, setHoveredTxn] = useState(null);

  const loadAll = useCallback(async (d = days) => {
    const [s, c, t] = await Promise.all([
      fetch(API(`/clients/${clientId}/finance/summary?days=${d}`)).then((x) => (x.ok ? x.json() : null)),
      fetch(API(`/clients/${clientId}/finance/categories?days=${d}`)).then((x) => (x.ok ? x.json() : null)),
      fetch(API(`/clients/${clientId}/finance/transactions?days=${d}&type=all&limit=1000`)).then((x) => (x.ok ? x.json() : null)),
    ]);
    setSummary(s);
    setCategories(c);
    setTxns(t);
  }, [clientId, days]);

  useEffect(() => { loadAll(days); /* eslint-disable-next-line */ }, [clientId, days]);

  const handleTxnSaved = (newTxn) => {
    setTxns((prev) => prev ? { ...prev, total: prev.total + 1, transactions: [newTxn, ...prev.transactions] } : { total: 1, transactions: [newTxn] });
    loadAll();
  };

  const deleteTxn = async (id) => {
    setDeletingId(id);
    try {
      await fetch(API(`/clients/${clientId}/finance/transactions/${id}`), { method: "DELETE" });
      setTxns((prev) => prev ? { ...prev, total: prev.total - 1, transactions: prev.transactions.filter((t) => t.id !== id) } : prev);
      setExpandedTxn(null);
      loadAll();
    } finally {
      setDeletingId(null);
    }
  };

  const updateTxn = async (id, patch) => {
    await fetch(API(`/clients/${clientId}/finance/transactions/${id}`), {
      method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(patch),
    });
    setTxns((prev) => prev ? { ...prev, transactions: prev.transactions.map((t) => (t.id === id ? { ...t, ...patch } : t)) } : prev);
  };

  const filteredTxns = (txns?.transactions ?? []).filter((t) => {
    if (txnType === "income") return t.is_income;
    if (txnType === "expense") return !t.is_income;
    return true;
  });

  if (!summary) {
    return (
      <div style={{ padding: 16, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>LOADING…</div>
    );
  }

  const roasColor = summary.roas == null ? "#3a5a80" : summary.roas >= 3 ? "#14c882" : summary.roas >= 1 ? "#f0a028" : "#dc3c3c";

  return (
    <div style={{ padding: "14px 16px", borderTop: "1px solid rgba(58,123,213,0.1)", display: "flex", flexDirection: "column", gap: 18 }}>
      {showAddForm && (
        <AddClientTransactionModal clientId={clientId} onClose={() => setShowAddForm(false)} onSaved={handleTxnSaved} />
      )}

      <div className="flex-wrap" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10 }}>
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80", letterSpacing: "0.14em" }}>
          MANUAL LEDGER · COST TO DELIVER VS. CLIENT-ATTRIBUTED REVENUE
        </div>
        <div className="flex-wrap" style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <button onClick={() => setShowAddForm(true)} className="btn btn-primary" style={{ fontSize: 11, padding: "6px 14px" }}>
            + Add Entry
          </button>
          <PeriodToggle days={days} setDays={setDays} options={CLIENT_FINANCE_PERIOD_OPTIONS} />
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4" style={{ gap: 12 }}>
        <ClientFinanceSummaryCard label="Client Revenue" value={clientFinanceMoney(summary.revenue)} color="#14c882" />
        <ClientFinanceSummaryCard label="Total Expenses" value={clientFinanceMoney(summary.expenses)} color="#f0a028" />
        <ClientFinanceSummaryCard label="Ad Spend" value={clientFinanceMoney(summary.ad_spend)} color="#6ab0ff" />
        <ClientFinanceSummaryCard
          label="ROAS"
          value={summary.roas != null ? `${summary.roas}x` : "—"}
          color={roasColor}
          sub={summary.roas == null ? "NO AD SPEND LOGGED" : summary.roas >= 3 ? "STRONG" : summary.roas >= 1 ? "BREAKEVEN+" : "LOSING MONEY"}
        />
      </div>

      <div className="glass-card" style={{ padding: "16px 18px" }}>
        <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 13, fontWeight: 600, color: "#d0dcf0", marginBottom: 12 }}>
          Revenue vs Expenses
        </div>
        <ResponsiveContainer width="100%" height={140}>
          <AreaChart data={categories?.daily ?? []} margin={{ top: 5, right: 5, bottom: 0, left: -10 }}>
            <defs>
              <linearGradient id={`cfRevenue-${clientId}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#14c882" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#14c882" stopOpacity={0} />
              </linearGradient>
              <linearGradient id={`cfExpense-${clientId}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#f0a028" stopOpacity={0.25} />
                <stop offset="95%" stopColor="#f0a028" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(58,123,213,0.06)" />
            <XAxis dataKey="date" tick={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, fill: "#2a4a7a" }} axisLine={false} tickLine={false}
              tickFormatter={(v) => (v ? v.slice(5) : "")} />
            <YAxis tick={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, fill: "#2a4a7a" }} axisLine={false} tickLine={false} tickFormatter={(v) => `$${v}`} />
            <Tooltip content={<ClientFinanceTooltip />} />
            <Area type="monotone" dataKey="revenue" name="Revenue" stroke="#14c882" strokeWidth={2} fill={`url(#cfRevenue-${clientId})`} />
            <Area type="monotone" dataKey="expenses" name="Expenses" stroke="#f0a028" strokeWidth={2} fill={`url(#cfExpense-${clientId})`} />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="glass-card" style={{ padding: "16px 18px" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 13, fontWeight: 600, color: "#d0dcf0" }}>Entries</div>
          <div style={{ display: "flex", background: "rgba(10,18,48,0.5)", border: "1px solid rgba(58,123,213,0.1)", borderRadius: 8, padding: 3, gap: 2 }}>
            {[["all", "ALL"], ["income", "REVENUE"], ["expense", "EXPENSES"]].map(([v, label]) => (
              <button key={v} onClick={() => setTxnType(v)} style={{
                fontFamily: "'Share Tech Mono', monospace", fontSize: 9, padding: "4px 12px", letterSpacing: "0.08em",
                borderRadius: 6, border: "none", cursor: "pointer",
                background: txnType === v ? "rgba(58,123,213,0.3)" : "transparent",
                color: txnType === v ? "#6ab0ff" : "#2a4a7a",
              }}>{label}</button>
            ))}
          </div>
        </div>

        {filteredTxns.length === 0 ? (
          <div style={{ padding: "24px 0", textAlign: "center", fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52", letterSpacing: "0.1em" }}>
            NO ENTRIES YET
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column" }}>
            {filteredTxns.map((t) => (
              <div key={t.id} onMouseEnter={() => setHoveredTxn(t.id)} onMouseLeave={() => setHoveredTxn(null)}>
                <div
                  onClick={() => setExpandedTxn(expandedTxn === t.id ? null : t.id)}
                  style={{
                    display: "flex", alignItems: "center", justifyContent: "space-between",
                    padding: "9px 0", borderBottom: expandedTxn === t.id ? "none" : "0.5px solid #1a2540", cursor: "pointer",
                  }}
                >
                  <div style={{ display: "flex", flexDirection: "column", gap: 2, flex: 1, marginRight: 12 }}>
                    <span style={{ fontSize: 12, color: "#8aaad0", fontWeight: 500 }}>{t.description || "—"}</span>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a4a7a" }}>{t.date}</span>
                      <span style={{
                        fontFamily: "'Share Tech Mono', monospace", fontSize: 8, padding: "2px 6px", borderRadius: 4,
                        background: "rgba(58,123,213,0.08)", color: "#3a7bd5", letterSpacing: "0.06em",
                      }}>{t.category}</span>
                    </div>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span style={{
                      fontFamily: "'Share Tech Mono', monospace", fontSize: 13, fontWeight: 700,
                      color: t.is_income ? "#14c882" : "#f0a028", letterSpacing: "-0.01em",
                    }}>
                      {t.is_income ? "+" : "-"}{clientFinanceMoney(t.amount)}
                    </span>
                    <button
                      onClick={(e) => { e.stopPropagation(); deleteTxn(t.id); }}
                      disabled={deletingId === t.id}
                      style={{
                        padding: "3px 9px", borderRadius: 5, border: "1px solid rgba(220,60,60,0.25)",
                        background: "rgba(220,60,60,0.06)", color: "#dc3c3c",
                        fontFamily: "'Share Tech Mono', monospace", fontSize: 8, cursor: "pointer", letterSpacing: "0.06em",
                        opacity: deletingId === t.id ? 0.5 : hoveredTxn === t.id ? 1 : 0,
                        transition: "opacity 0.15s", pointerEvents: hoveredTxn === t.id ? "auto" : "none",
                      }}
                    >
                      {deletingId === t.id ? "…" : "✕"}
                    </button>
                  </div>
                </div>

                {expandedTxn === t.id && (
                  <div style={{ padding: "10px 12px", background: "rgba(10,18,48,0.4)", borderBottom: "0.5px solid #1a2540", display: "flex", gap: 10, alignItems: "center" }}>
                    <select
                      value={t.category}
                      onChange={(e) => updateTxn(t.id, { category: e.target.value })}
                      className="dg-input"
                      style={{ fontSize: 11, padding: "5px 8px", flex: "0 0 auto" }}
                    >
                      {(t.is_income ? ["Client Revenue"] : CLIENT_FINANCE_EXPENSE_CATEGORIES).map((c) => <option key={c} value={c}>{c}</option>)}
                    </select>
                    <input
                      className="dg-input" style={{ flex: 1, fontSize: 11 }} placeholder="Add note…"
                      defaultValue={t.notes || ""} onBlur={(e) => updateTxn(t.id, { notes: e.target.value })}
                    />
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// Client "please fix/do this" requests, submitted from the portal's To Do
// tab. Mark done here as they get handled.
function ClientRequests({ clientId }) {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    const r = await fetch(API(`/clients/${clientId}/requests`));
    if (r.ok) setRequests(await r.json());
    setLoading(false);
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [clientId]);

  const setStatus = async (request, status) => {
    const r = await fetch(API(`/clients/${clientId}/requests/${request.id}`), {
      method: "PATCH", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    if (r.ok) {
      const updated = await r.json();
      setRequests((prev) => prev.map((req) => (req.id === request.id ? updated : req)));
    }
  };

  if (loading) return <div style={{ padding: 16, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>LOADING…</div>;
  if (requests.length === 0) {
    return <div style={{ padding: 16, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>NO REQUESTS FROM THIS CLIENT YET</div>;
  }

  return (
    <div style={{ padding: "14px 16px", borderTop: "1px solid rgba(58,123,213,0.1)", display: "flex", flexDirection: "column", gap: 8 }}>
      {requests.map((r) => {
        const done = r.status === "done";
        return (
          <div key={r.id} style={{
            display: "flex", alignItems: "flex-start", gap: 10, padding: "10px 12px", borderRadius: 8,
            background: done ? "rgba(20,200,130,0.05)" : "rgba(240,160,40,0.06)",
          }}>
            <input
              type="checkbox" checked={done}
              onChange={() => setStatus(r, done ? "open" : "done")}
              style={{ marginTop: 3, flexShrink: 0, cursor: "pointer" }}
            />
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 12.5, color: done ? "#8fd9bd" : "#d0e8ff", textDecoration: done ? "line-through" : "none", lineHeight: 1.5 }}>
                {r.message}
              </div>
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80", marginTop: 4 }}>
                {new Date(r.created_at).toLocaleString()}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// Files a client uploaded via the portal's Upload tab. Bytes live in
// Cloudflare R2 (r2_storage.py) — this just lists metadata and gets
// presigned URLs on demand: an `inline=true` one (no Content-Disposition:
// attachment header) to render image/video thumbnails and a lightbox
// directly in the browser, and a plain one for the DOWNLOAD button. Lets
// Dylan flip through what a client uploaded and judge what's usable without
// downloading each file first.
//
// Perf note: an earlier version fetched a presigned URL AND mounted a real
// <video> element for every video the instant the grid rendered — with a
// batch of dozens of 50-80MB videos, that meant dozens of simultaneous
// browser video decoders spinning up at once, which is what made the whole
// tab lag badly. Fix: images lazy-load only once actually scrolled into
// view (IntersectionObserver), and videos never load or decode anything
// for their thumbnail at all — just a static icon — until the user
// explicitly clicks to open one in the lightbox.
function UploadThumb({ clientId, file, onOpen, onDownload, onDelete }) {
  const [inlineUrl, setInlineUrl] = useState(null);
  const [loadingVideo, setLoadingVideo] = useState(false);
  const elRef = useRef(null);
  const isImage = file.file_type?.startsWith("image/");
  const isVideo = file.file_type?.startsWith("video/");

  const fetchInlineUrl = async () => {
    const r = await fetch(API(`/clients/${clientId}/uploads/${file.id}/download?inline=true`));
    if (r.ok) return (await r.json()).url;
    return null;
  };

  // Images: fetch + render only once the thumbnail is actually visible.
  useEffect(() => {
    if (!isImage || inlineUrl || !elRef.current) return;
    const el = elRef.current;
    const observer = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting) {
        observer.disconnect();
        fetchInlineUrl().then((url) => url && setInlineUrl(url));
      }
    }, { rootMargin: "200px" });
    observer.observe(el);
    return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isImage, clientId, file.id]);

  const openVideo = async () => {
    if (loadingVideo) return;
    setLoadingVideo(true);
    const url = inlineUrl || (await fetchInlineUrl());
    setLoadingVideo(false);
    if (url) { setInlineUrl(url); onOpen(file, url); }
  };

  const clickable = isImage ? Boolean(inlineUrl) : isVideo;

  return (
    <div
      ref={elRef}
      title={file.file_name}
      onClick={() => { if (isImage && inlineUrl) onOpen(file, inlineUrl); else if (isVideo) openVideo(); }}
      style={{
        position: "relative", aspectRatio: "1 / 1", borderRadius: 10, overflow: "hidden",
        background: "rgba(255,255,255,0.03)", border: "1px solid rgba(58,123,213,0.12)",
        cursor: clickable ? "pointer" : "default",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}
    >
      {isImage && inlineUrl && (
        <img src={inlineUrl} alt={file.file_name} loading="lazy" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      )}
      {isImage && !inlineUrl && (
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a8a" }}>…</div>
      )}
      {isVideo && (
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "center", width: "100%", height: "100%",
          background: "rgba(58,123,213,0.06)",
        }}>
          <div style={{ fontSize: 28, color: loadingVideo ? "#3a5a8a" : "#9cc4f5" }}>{loadingVideo ? "…" : "▶"}</div>
        </div>
      )}
      {!isImage && !isVideo && (
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#5a7aa0", textAlign: "center", padding: 8 }}>
          FILE
        </div>
      )}
      <div style={{ position: "absolute", top: 4, right: 4, display: "flex", gap: 4 }}>
        <button
          title="Download" onClick={(e) => { e.stopPropagation(); onDownload(file); }}
          style={{
            width: 22, height: 22, borderRadius: 6, border: "none", cursor: "pointer",
            background: "rgba(0,0,0,0.55)", color: "#e8f0ff", fontSize: 11, lineHeight: 1,
            display: "flex", alignItems: "center", justifyContent: "center",
          }}
        >⬇</button>
        <button
          title="Delete" onClick={(e) => { e.stopPropagation(); onDelete(file); }}
          style={{
            width: 22, height: 22, borderRadius: 6, border: "none", cursor: "pointer",
            background: "rgba(0,0,0,0.55)", color: "#e05c5c", fontSize: 11, lineHeight: 1,
            display: "flex", alignItems: "center", justifyContent: "center",
          }}
        >✕</button>
      </div>
    </div>
  );
}

function UploadLightbox({ clientId, file, url, onClose, onDelete }) {
  const isImage = file.file_type?.startsWith("image/");
  const download = async () => {
    const r = await fetch(API(`/clients/${clientId}/uploads/${file.id}/download`));
    if (r.ok) {
      const { url: dlUrl } = await r.json();
      window.open(dlUrl, "_blank", "noreferrer");
    }
  };

  return createPortal(
    <div
      onClick={onClose}
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.85)", zIndex: 1000,
        display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 24,
      }}
    >
      <div onClick={(e) => e.stopPropagation()} style={{ maxWidth: "90vw", maxHeight: "80vh", display: "flex" }}>
        {isImage ? (
          <img src={url} alt={file.file_name} style={{ maxWidth: "90vw", maxHeight: "80vh", objectFit: "contain", borderRadius: 8 }} />
        ) : (
          <video src={url} controls autoPlay style={{ maxWidth: "90vw", maxHeight: "80vh", borderRadius: 8 }} />
        )}
      </div>
      <div onClick={(e) => e.stopPropagation()} style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 14 }}>
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 11, color: "#d0e8ff" }}>{file.file_name}</div>
        <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={download}>DOWNLOAD</button>
        <button className="btn btn-danger" style={{ fontSize: 10 }} onClick={() => onDelete(file)}>DELETE</button>
        <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={onClose}>CLOSE</button>
      </div>
    </div>,
    document.body
  );
}

const UPLOADS_PAGE_SIZE = 24;

function ClientUploads({ clientId }) {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lightbox, setLightbox] = useState(null); // { file, url }
  // Caps how many thumbnails actually mount at once — the previous version
  // rendered (and lazy-loaded) every file in one grid the instant the tab
  // opened; with a big batch that's still dozens of thumbnails mounting,
  // observing, and fetching simultaneously even with per-item lazy-loading.
  // Paging the render itself, not just the network fetch, is what actually
  // keeps opening the tab fast regardless of how many files a client has.
  const [visibleCount, setVisibleCount] = useState(UPLOADS_PAGE_SIZE);

  const load = async () => {
    const r = await fetch(API(`/clients/${clientId}/uploads`));
    if (r.ok) setFiles(await r.json());
    setVisibleCount(UPLOADS_PAGE_SIZE);
    setLoading(false);
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [clientId]);

  const download = async (file) => {
    const r = await fetch(API(`/clients/${clientId}/uploads/${file.id}/download`));
    if (r.ok) {
      const { url } = await r.json();
      window.open(url, "_blank", "noreferrer");
    } else {
      window.alert("Couldn't get a download link — file storage may not be connected yet.");
    }
  };

  const remove = async (file) => {
    if (!window.confirm(`Delete "${file.file_name}"? This can't be undone.`)) return;
    await fetch(API(`/clients/${clientId}/uploads/${file.id}`), { method: "DELETE" });
    setLightbox(null);
    load();
  };

  if (loading) return <div style={{ padding: 16, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>LOADING…</div>;

  // Non-media files (PDFs, docx, etc.) aren't shown in this gallery at all
  // — this tab is for reviewing photos/videos, not managing every document
  // type a client might upload. They're still included in DOWNLOAD ALL
  // (ZIP) and still exist in storage; just not listed here.
  const mediaFiles = files.filter((f) => f.file_type?.startsWith("image/") || f.file_type?.startsWith("video/"));

  if (mediaFiles.length === 0) {
    return <div style={{ padding: 16, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>NO PHOTOS OR VIDEOS UPLOADED YET</div>;
  }

  const visibleFiles = mediaFiles.slice(0, visibleCount);
  const hasMore = mediaFiles.length > visibleCount;

  return (
    <div style={{ padding: "14px 16px", borderTop: "1px solid rgba(58,123,213,0.1)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#5a7aa0" }}>
          SHOWING {visibleFiles.length} OF {mediaFiles.length} FILE{mediaFiles.length === 1 ? "" : "S"}
        </div>
        <button
          className="btn btn-secondary" style={{ fontSize: 10 }}
          onClick={() => window.open(API(`/clients/${clientId}/uploads/zip`), "_blank")}
        >
          DOWNLOAD ALL (ZIP)
        </button>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))", gap: 10 }}>
        {visibleFiles.map((f) => (
          <UploadThumb
            key={f.id} clientId={clientId} file={f}
            onOpen={(file, url) => setLightbox({ file, url })}
            onDownload={download} onDelete={remove}
          />
        ))}
      </div>
      {hasMore && (
        <div style={{ display: "flex", justifyContent: "center", marginTop: 14 }}>
          <button
            className="btn btn-secondary" style={{ fontSize: 10 }}
            onClick={() => setVisibleCount((n) => n + UPLOADS_PAGE_SIZE)}
          >
            LOAD {Math.min(UPLOADS_PAGE_SIZE, mediaFiles.length - visibleCount)} MORE
          </button>
        </div>
      )}
      {lightbox && (
        <UploadLightbox
          clientId={clientId} file={lightbox.file} url={lightbox.url}
          onClose={() => setLightbox(null)} onDelete={remove}
        />
      )}
    </div>
  );
}

// One of the three single-value resource fields living directly on the
// client row (ads_manager_resource / registrar_resource / hosting_resource).
// Free text — a link, a login note, an account ID, whatever's easiest to
// paste for that platform.
// Collapsible card shell shared by the Resources tab's sections. The body is
// hidden rather than unmounted so unsaved edits survive collapsing.
function ResourceCard({ title, summary, muted, isOpen, onToggle, right, children }) {
  return (
    <div style={{ border: "1px solid rgba(58,123,213,0.15)", borderRadius: 8, background: "rgba(10,20,50,0.35)", overflow: "hidden" }}>
      <div
        role="button" tabIndex={0}
        onClick={onToggle}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onToggle(); } }}
        style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 12px", cursor: "pointer" }}
      >
        <span style={{ color: "#3a7bd5", fontSize: 10, width: 10, transform: isOpen ? "rotate(90deg)" : "none", transition: "transform 0.15s" }}>▶</span>
        <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600, fontSize: 12.5, color: "#c4d0e8", flexShrink: 0 }}>{title}</span>
        <span style={{
          flex: 1, minWidth: 0, textAlign: "right", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
          fontFamily: muted ? "'Share Tech Mono', monospace" : "inherit", fontSize: muted ? 10 : 11.5, color: muted ? "#2a4a7a" : "#5a7096",
        }}>
          {summary}
        </span>
        {right && <span onClick={(e) => e.stopPropagation()}>{right}</span>}
      </div>
      <div style={{ display: isOpen ? "block" : "none", padding: "10px 12px 12px 32px", borderTop: "1px solid rgba(58,123,213,0.1)" }}>
        {children}
      </div>
    </div>
  );
}

function ResourceField({ clientId, field, label, placeholder, value, onSaved, isOpen, onToggle, children }) {
  const [text, setText] = useState(value || "");
  const [saving, setSaving] = useState(false);
  const dirty = text !== (value || "");
  const saved = (value || "").trim();

  useEffect(() => { setText(value || ""); }, [value]);

  const save = async () => {
    setSaving(true);
    const r = await fetch(API(`/clients/${clientId}`), {
      method: "PATCH", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ [field]: text }),
    });
    if (r.ok) onSaved(await r.json());
    setSaving(false);
  };

  return (
    <ResourceCard
      title={label}
      summary={dirty ? "UNSAVED CHANGES" : saved ? saved.split("\n")[0] : "NOT SET"}
      muted={dirty || !saved}
      isOpen={isOpen} onToggle={onToggle}
    >
      <textarea
        className="dg-input" rows={2} placeholder={placeholder} value={text}
        onChange={(e) => setText(e.target.value)}
        style={{ width: "100%", boxSizing: "border-box", fontSize: 12, resize: "vertical", marginBottom: 6 }}
      />
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        {children}
        <button className="btn btn-secondary" style={{ fontSize: 10, marginLeft: "auto" }} onClick={save} disabled={saving || !dirty}>
          {saving ? "SAVING…" : "SAVE"}
        </button>
      </div>
    </ResourceCard>
  );
}

// Excludes the CALLER's own IP (resolved server-side via X-Forwarded-For)
// from all funnel/VSL view tracking going forward — click this from your
// own browser/device, not somewhere else, since it's your IP on THIS
// request that gets excluded. Safe to click again if your IP changes.
// Lives next to the Funnel resource link since that's the page it's for.
function ExcludeMyIpButton() {
  const [state, setState] = useState("idle"); // idle | saving | done | error
  const [ip, setIp] = useState(null);

  const click = async () => {
    setState("saving");
    try {
      const r = await fetch(API("/content-analytics/exclude-my-ip"), { method: "POST" });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || "Failed");
      setIp(d.ip);
      setState("done");
    } catch {
      setState("error");
    }
  };

  if (state === "done") {
    return (
      <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#14c882" }}>
        ✓ Excluded {ip}
      </span>
    );
  }
  return (
    <button className="btn btn-secondary" style={{ fontSize: 10, padding: "6px 12px" }} onClick={click} disabled={state === "saving"}>
      {state === "saving" ? "Excluding…" : state === "error" ? "Failed — retry?" : "Exclude My IP From Tracking"}
    </button>
  );
}

function MiscResourceRow({ resource, onDelete }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 14, padding: "10px 14px", borderRadius: 8, background: "rgba(255,255,255,0.02)", marginBottom: 6 }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600, fontSize: 13, color: "#d0e8ff" }}>{resource.label}</div>
        <div style={{ fontSize: 12, color: "#8aaad0", marginTop: 2, wordBreak: "break-all", whiteSpace: "pre-wrap" }}>{resource.value}</div>
      </div>
      <button className="btn btn-danger" style={{ fontSize: 10 }} onClick={() => onDelete(resource.id)}>DELETE</button>
    </div>
  );
}

// Enable toggle + freeform per-client context editor for the self-built
// response_ai.py agent, a checkbox + textarea (the
// context is meant to be a real paragraph: business info, tone, offer,
// hours, what to escalate).
function ResponseAiSetup({ clientId, config, onSaveFields, onSaved }) {
  const [enabled, setEnabled] = useState(Boolean(config?.response_ai_enabled));
  const [context, setContext] = useState(config?.response_ai_context || "");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState("");

  const generateContext = async () => {
    if (context.trim() && !window.confirm("This will replace the context text below with an AI-drafted version. Continue?")) {
      return;
    }
    setGenerating(true);
    setGenerateError("");
    setSaved(false);
    try {
      const r = await fetch(API(`/clients/${clientId}/marketing-config/generate-response-ai-context`), { method: "POST" });
      if (!r.ok) {
        const detail = await r.json().catch(() => null);
        throw new Error(detail?.detail || "Failed to generate context");
      }
      const { context: drafted } = await r.json();
      setContext(drafted || "");
    } catch (e) {
      setGenerateError(e.message);
    } finally {
      setGenerating(false);
    }
  };

  const save = async () => {
    setSaving(true);
    setSaved(false);
    setSaveError("");
    const result = await onSaveFields({ response_ai_enabled: enabled, response_ai_context: context.trim() || null });
    setSaving(false);
    if (result?.ok) {
      setSaved(true);
      onSaved?.();
    } else {
      setSaveError(result?.error || "Save failed");
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 8 }}>
      <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "#d0e8ff", cursor: "pointer" }}>
        <input
          type="checkbox" checked={enabled}
          onChange={(e) => { setEnabled(e.target.checked); setSaved(false); setSaveError(""); }}
        />
        Enable the AI response agent for this client
      </label>
      <div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 2 }}>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#5a7aa0" }}>
            CLIENT CONTEXT (business info, tone, offer, hours, FAQs, what to escalate)
          </div>
          <button
            className="btn btn-secondary" style={{ fontSize: 9, padding: "3px 8px" }}
            onClick={generateContext} disabled={generating || !clientId}
          >
            {generating ? "GENERATING…" : "GENERATE CONTEXT"}
          </button>
        </div>
        <textarea
          className="dg-input" rows={8} style={{ fontSize: 12, width: "100%", boxSizing: "border-box", resize: "vertical" }}
          value={context}
          onChange={(e) => { setContext(e.target.value); setSaved(false); setSaveError(""); }}
          placeholder={"e.g. Bright Path Physical Therapy. Hours: Mon-Fri 8am-6pm. Escalate anything about insurance/billing or a lead who sounds upset."}
        />
        <div style={{ marginTop: 3, fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#5a7aa0" }}>
          Drafts from this client's onboarding answers, linked contact info, and any uploaded PDFs/docx — review and edit before saving, it won't always get everything right.
        </div>
        {generateError && (
          <div style={{ marginTop: 4, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#e05c5c" }}>{generateError}</div>
        )}
      </div>
      <button className="btn btn-primary" style={{ fontSize: 10, alignSelf: "flex-start" }} onClick={save} disabled={saving}>
        {saving ? "SAVING…" : saved ? "SAVED ✓" : "SAVE"}
      </button>
      {saveError && (
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#e05c5c" }}>{saveError}</div>
      )}
    </div>
  );
}

const AGENT_SEQUENCE_LENGTH = 5;
const AGENT_SEQUENCE_LABELS = ["First text", "Second text", "Third text", "Fourth text", "Fifth text"];

// The loose conversational arc response_ai.py tries to progress a lead
// through — 5 fixed stages (mirrors client_sms_sequences' fixed-step shape
// elsewhere in this file) stored as one JSONB array. Not a rigid script:
// the agent always answers off-script questions first, per its own system
// prompt preamble — this is just the "what's next" guidance.
function AgentSequenceEditor({ config, onSaveFields }) {
  const initial = Array.isArray(config?.response_ai_sequence) ? config.response_ai_sequence : [];
  const [steps, setSteps] = useState(() =>
    Array.from({ length: AGENT_SEQUENCE_LENGTH }, (_, i) => initial[i] || "")
  );
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState("");

  const save = async () => {
    setSaving(true);
    setSaved(false);
    setSaveError("");
    const result = await onSaveFields({ response_ai_sequence: steps.map((s) => s.trim()) });
    setSaving(false);
    if (result?.ok) setSaved(true); else setSaveError(result?.error || "Save failed");
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ fontSize: 12, color: "#8aaad0" }}>
        The general sequence the agent tries to move a conversation through — it doesn't have to follow this perfectly. If a lead asks a question, it answers first, then tries to progress to the next stage.
      </div>
      {AGENT_SEQUENCE_LABELS.map((label, i) => (
        <div key={i}>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#5a7aa0", marginBottom: 2 }}>{label.toUpperCase()}</div>
          <textarea
            className="dg-input" rows={2} style={{ fontSize: 12, width: "100%", boxSizing: "border-box", resize: "vertical" }}
            value={steps[i]}
            onChange={(e) => {
              const next = [...steps];
              next[i] = e.target.value;
              setSteps(next);
              setSaved(false); setSaveError("");
            }}
            placeholder={i === 0 ? "e.g. Greet them, confirm what they're looking for, and ask a qualifying question." : "e.g. Present the offer and ask if they'd like to grab a free consult time."}
          />
        </div>
      ))}
      <button className="btn btn-primary" style={{ fontSize: 10, alignSelf: "flex-start" }} onClick={save} disabled={saving}>
        {saving ? "SAVING…" : saved ? "SAVED ✓" : "SAVE"}
      </button>
      {saveError && (
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#e05c5c" }}>{saveError}</div>
      )}
    </div>
  );
}

// Behavioral guardrails. Two are actually enforced in code (not just prompt
// suggestions): the reply delay (deferred via scheduler_registry so the
// Twilio webhook never blocks on it) and a hard word-count cap (enforced
// both as a prompt instruction and a truncation fallback in response_ai.py).
// Everything else is freeform text the admin writes, which the agent is
// told to read before every reply — same "AI reads it, doesn't just
// display it" pattern as response_ai_context.
function AgentRulesEditor({ config, onSaveFields }) {
  const [minDelay, setMinDelay] = useState(config?.response_ai_min_delay_seconds ?? 0);
  const [maxWords, setMaxWords] = useState(config?.response_ai_max_words ?? "");
  const [rules, setRules] = useState(config?.response_ai_rules || "");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState("");

  const save = async () => {
    setSaving(true);
    setSaved(false);
    setSaveError("");
    const result = await onSaveFields({
      response_ai_min_delay_seconds: Number(minDelay) || 0,
      response_ai_max_words: maxWords === "" ? null : Number(maxWords),
      response_ai_rules: rules.trim() || null,
    });
    setSaving(false);
    if (result?.ok) setSaved(true); else setSaveError(result?.error || "Save failed");
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
        <div>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#5a7aa0", marginBottom: 2 }}>
            MIN DELAY BEFORE REPLYING (SECONDS)
          </div>
          <input
            type="number" min="0" className="dg-input" style={{ fontSize: 12, width: 120 }}
            value={minDelay}
            onChange={(e) => { setMinDelay(e.target.value); setSaved(false); setSaveError(""); }}
          />
        </div>
        <div>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#5a7aa0", marginBottom: 2 }}>
            MAX WORDS PER TEXT
          </div>
          <input
            type="number" min="1" className="dg-input" style={{ fontSize: 12, width: 120 }}
            value={maxWords} placeholder="no limit"
            onChange={(e) => { setMaxWords(e.target.value); setSaved(false); setSaveError(""); }}
          />
        </div>
      </div>
      <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#5a7aa0" }}>
        Both are actually enforced — the delay is scheduled server-side, and the word cap is hard-truncated even if the AI runs long.
      </div>
      <div>
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#5a7aa0", marginBottom: 2 }}>
          ADDITIONAL RULES (the agent reads this before every reply)
        </div>
        <textarea
          className="dg-input" rows={8} style={{ fontSize: 12, width: "100%", boxSizing: "border-box", resize: "vertical" }}
          value={rules}
          onChange={(e) => { setRules(e.target.value); setSaved(false); setSaveError(""); }}
          placeholder={"e.g. Never mention competitors by name. Always use the lead's first name if known. If they ask about a refund, escalate immediately rather than answering."}
        />
      </div>
      <button className="btn btn-primary" style={{ fontSize: 10, alignSelf: "flex-start" }} onClick={save} disabled={saving}>
        {saving ? "SAVING…" : saved ? "SAVED ✓" : "SAVE"}
      </button>
      {saveError && (
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#e05c5c" }}>{saveError}</div>
      )}
    </div>
  );
}

// The response AI's funnel (GET /clients/{id}/ai-stats): texted -> replied
// -> offered times -> booked -> showed, plus where the rest ended up.
function AgentPerformance({ clientId }) {
  const [days, setDays] = useState(null);
  const [stats, setStats] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setStats(null);
    fetch(API(`/clients/${clientId}/ai-stats${days ? `?days=${days}` : ""}`))
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (!cancelled) setStats(d); });
    return () => { cancelled = true; };
  }, [clientId, days]);

  const pct = (n) => (stats?.leads ? `${Math.round((100 * n) / stats.leads)}%` : "–");
  const funnel = stats ? [
    ["Texted", stats.leads], ["Replied", stats.replied], ["Offered times", stats.offered_times],
    ["Booked", stats.booked], ["Showed", stats.showed],
  ] : [];
  const other = stats ? [
    ["Booked by the AI", stats.ai_booked], ["Unqualified", stats.unqualified],
    ["Escalated", stats.escalated], ["Closed", stats.closed],
  ] : [];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "flex", gap: 6 }}>
        {[[null, "ALL TIME"], [30, "30 DAYS"], [7, "7 DAYS"]].map(([d, label]) => (
          <button key={label} className="btn btn-secondary" style={{ fontSize: 10, opacity: days === d ? 1 : 0.5 }} onClick={() => setDays(d)}>
            {label}
          </button>
        ))}
      </div>
      {!stats ? (
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>LOADING…</div>
      ) : (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(96px, 1fr))", gap: 8 }}>
            {funnel.map(([label, n]) => (
              <div key={label} className="glass-card-sm" style={{ padding: "10px 12px" }}>
                <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#5a7aa0", letterSpacing: "0.06em" }}>{label.toUpperCase()}</div>
                <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: 18, color: "#e8f0ff" }}>{n}</div>
                {label !== "Texted" && <div style={{ fontSize: 10, color: "#3a7bd5" }}>{pct(n)}</div>}
              </div>
            ))}
          </div>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#8aaad0" }}>
            {other.map(([label, n]) => `${label}: ${n}`).join("  ·  ")}
            {stats.lessons_pending > 0 && `  ·  ${stats.lessons_pending} lesson${stats.lessons_pending === 1 ? "" : "s"} awaiting approval`}
          </div>
        </>
      )}
    </div>
  );
}

// Lessons drafted from human replies (client_ai_lessons.py). Pending ones
// wait for approval; only Active ones go into the agent's prompt.
function AgentLessons({ clientId }) {
  const [lessons, setLessons] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [draft, setDraft] = useState("");
  const [showSkipped, setShowSkipped] = useState(false);
  const [error, setError] = useState("");

  const load = async () => {
    const r = await fetch(API(`/clients/${clientId}/ai-lessons`));
    if (r.ok) setLessons(await r.json());
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [clientId]);

  const update = async (id, fields) => {
    setError("");
    const r = await fetch(API(`/clients/${clientId}/ai-lessons/${id}`), {
      method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(fields),
    });
    if (!r.ok) setError((await r.json().catch(() => null))?.detail || "Failed to save");
    setEditingId(null);
    await load();
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this lesson?")) return;
    await fetch(API(`/clients/${clientId}/ai-lessons/${id}`), { method: "DELETE" });
    await load();
  };

  if (!lessons) return <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>LOADING…</div>;

  const visible = lessons.filter((l) => showSkipped || l.status !== "skipped");
  const skippedCount = lessons.length - lessons.filter((l) => l.status !== "skipped").length;
  const statusColor = { pending: "#f0b429", active: "#4ade80", disabled: "#5a7aa0", skipped: "#5a7aa0" };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {visible.length === 0 && (
        <div style={{ fontSize: 12, color: "#5a7aa0" }}>
          No lessons yet. They appear here a few minutes after someone texts one of this client's leads by hand from the portal.
        </div>
      )}
      {visible.map((l) => (
        <div key={l.id} style={{ padding: 12, borderRadius: 8, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(58,123,213,0.12)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 8, marginBottom: 6 }}>
            <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600, fontSize: 12.5, color: "#d0e8ff" }}>
              {l.situation || "No reusable lesson"}
            </div>
            <span className="mono" style={{ fontSize: 9, color: statusColor[l.status] || "#5a7aa0", letterSpacing: "0.06em" }}>{l.status.toUpperCase()}</span>
          </div>
          {editingId === l.id ? (
            <textarea className="dg-input" rows={3} style={{ width: "100%", fontSize: 12 }} value={draft} onChange={(e) => setDraft(e.target.value)} />
          ) : (
            l.lesson && <div style={{ fontSize: 12.5, color: "#c4d0e8", lineHeight: 1.5 }}>{l.lesson}</div>
          )}
          <div style={{ fontSize: 11, color: "#5a7aa0", marginTop: 6, whiteSpace: "pre-wrap" }}>
            What they texted: "{l.human_reply}"
          </div>
          {l.analysis_note && <div style={{ fontSize: 11, color: "#5a7aa0", marginTop: 2 }}>{l.analysis_note}</div>}
          <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
            {editingId === l.id ? (
              <>
                <button className="btn btn-primary" style={{ fontSize: 10 }} onClick={() => update(l.id, { lesson: draft.trim() })}>SAVE</button>
                <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={() => setEditingId(null)}>CANCEL</button>
              </>
            ) : (
              <>
                {l.status !== "active" && l.lesson && (
                  <button className="btn btn-primary" style={{ fontSize: 10 }} onClick={() => update(l.id, { status: "active" })}>APPROVE</button>
                )}
                {l.status === "active" && (
                  <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={() => update(l.id, { status: "disabled" })}>TURN OFF</button>
                )}
                {l.lesson && (
                  <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={() => { setEditingId(l.id); setDraft(l.lesson); }}>EDIT</button>
                )}
                <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={() => remove(l.id)}>DELETE</button>
              </>
            )}
          </div>
        </div>
      ))}
      {skippedCount > 0 && (
        <button className="btn btn-secondary" style={{ fontSize: 10, alignSelf: "flex-start" }} onClick={() => setShowSkipped(!showSkipped)}>
          {showSkipped ? "HIDE" : "SHOW"} {skippedCount} SKIPPED
        </button>
      )}
      {error && <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#e05c5c" }}>{error}</div>}
    </div>
  );
}

// Wipes a test phone number's conversation state (client_lead_conversations
// row + client_sms_messages history) so re-texting the client's number
// starts response_ai.py fresh — no escalated/booked state or prior message
// context left over from an earlier test run.
function AgentResetTest({ clientId }) {
  const [phone, setPhone] = useState("");
  const [resetting, setResetting] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const reset = async () => {
    if (!phone.trim()) return;
    setResetting(true);
    setResult(null);
    setError("");
    try {
      const r = await fetch(API(`/clients/${clientId}/response-ai/reset-test?phone=${encodeURIComponent(phone.trim())}`), { method: "POST" });
      if (!r.ok) {
        const detail = await r.json().catch(() => null);
        throw new Error(detail?.detail || "Failed to reset");
      }
      setResult(await r.json());
    } catch (e) {
      setError(e.message);
    } finally {
      setResetting(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ display: "flex", gap: 6 }}>
        <input
          className="dg-input" style={{ fontSize: 12, flex: 1 }} placeholder="+15551234567"
          value={phone} onChange={(e) => { setPhone(e.target.value); setResult(null); setError(""); }}
        />
        <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={reset} disabled={resetting || !phone.trim()}>
          {resetting ? "RESETTING…" : "RESET"}
        </button>
      </div>
      {result && (
        result.messages_deleted > 0 ? (
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#4ade80" }}>
            Reset ✓ — cleared conversation state and {result.messages_deleted} message{result.messages_deleted === 1 ? "" : "s"}. Text the number again to start fresh.
          </div>
        ) : (
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#f0b429" }}>
            No messages found for that number on this client — double check the number, it may not match any test conversation here.
          </div>
        )
      )}
      {error && (
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#e05c5c" }}>{error}</div>
      )}
    </div>
  );
}

// Calendly connection — a Personal Access Token the client (or Dylan, once
// added as an admin on their account) generates from Calendly's own
// settings. Read-only use (calendly_integration.py) — lets response_ai's
// check_availability tool propose real open times instead of asking blind.
// Calendly's API can't create a confirmed booking on someone's behalf, so
// this is availability-checking only; the actual booking still gets logged
// the same way it always has.
// Registered automatically when the token is saved (client_marketing.py);
// autoError is that attempt's failure, the button is the retry.
function CalendlyWebhookConnect({ clientId, connected, autoError }) {
  const [webhookConnected, setWebhookConnected] = useState(Boolean(connected));
  const [connecting, setConnecting] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState(autoError || "");
  useEffect(() => { setWebhookConnected(Boolean(connected)); setErr(autoError || ""); }, [connected, autoError]);

  const connect = async () => {
    setConnecting(true); setMsg(""); setErr("");
    try {
      const r = await fetch(API(`/clients/${clientId}/marketing-config/connect-calendly-webhook`), { method: "POST" });
      if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(d.detail || "Failed to connect"); }
      setWebhookConnected(true);
      setMsg("Connected — real bookings now automatically create this client's No Show reminders.");
    } catch (e) { setErr(e.message); }
    setConnecting(false);
  };

  return (
    <div style={{ marginTop: 10, paddingTop: 10, borderTop: "1px solid rgba(58,123,213,0.1)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <div style={{ fontSize: 12, color: "#8aaad0", flex: 1 }}>
          Auto-create No Show reminders the moment this client's leads actually book — no manual entry.
        </div>
        <span className={`badge ${webhookConnected ? "badge-green" : "badge-gray"}`}>
          {webhookConnected ? "CONNECTED" : "NOT CONNECTED"}
        </span>
      </div>
      <button className="btn btn-secondary" style={{ fontSize: 10, marginTop: 8 }} onClick={connect} disabled={connecting}>
        {connecting ? "CONNECTING…" : webhookConnected ? "RECONNECT" : "CONNECT WEBHOOK"}
      </button>
      {msg && <div style={{ marginTop: 6, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#4ade80" }}>{msg}</div>}
      {err && <div style={{ marginTop: 6, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#e05c5c" }}>{err}</div>}
    </div>
  );
}

// GoHighLevel counterpart of the Calendly token above (ghl_integration.py),
// for a client who books on GHL. Same never-pre-filled secret field. The
// calendar is the GHL booking link already saved as the client's booking
// link, so the token is the only thing to set.
function AgentGhlConnect({ config, onSaveFields }) {
  const [token, setToken] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState("");
  const connected = Boolean(config?.ghl_api_token);

  const save = async (value) => {
    setSaving(true);
    setSaved(false);
    setSaveError("");
    const result = await onSaveFields({ ghl_api_token: value });
    setSaving(false);
    if (result?.ok) { setSaved(true); setToken(""); } else setSaveError(result?.error || "Save failed");
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ fontSize: 12, color: "#8aaad0" }}>
        Only for a client who books on GoHighLevel. In their GHL sub-account: Settings → Private Integrations → Create, with scopes View Calendars, Edit Calendar Events and Edit Contacts, then paste the token below. The agent books onto the calendar in the client's GHL booking link. Calendly wins if both are connected. {connected ? "Connected — paste a new token below to replace it." : "Not connected."}
      </div>
      <div style={{ display: "flex", gap: 6 }}>
        <input
          type="password" autoComplete="off" className="dg-input" style={{ fontSize: 12, flex: 1, boxSizing: "border-box" }}
          value={token} placeholder={connected ? "Paste a new token to replace the connected one" : "GHL Private Integration token"}
          onChange={(e) => { setToken(e.target.value); setSaved(false); setSaveError(""); }}
        />
        {connected && (
          <button className="btn btn-danger" style={{ fontSize: 10 }} disabled={saving}
            onClick={() => window.confirm("Disconnect GoHighLevel for this client?") && save(null)}>
            DISCONNECT
          </button>
        )}
      </div>
      <button className="btn btn-primary" style={{ fontSize: 10, alignSelf: "flex-start" }} onClick={() => save(token.trim())} disabled={saving || !token.trim()}>
        {saving ? "SAVING…" : saved ? "SAVED ✓" : "SAVE"}
      </button>
      {saveError && (
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#e05c5c" }}>{saveError}</div>
      )}
    </div>
  );
}

function AgentCalendlyConnect({ config, onSaveFields, clientId }) {
  // Deliberately NEVER pre-fill this with the existing token (unlike every
  // other field in this file) — a password-type input silently holding the
  // old secret as masked dots is a real trap: paste a new one without
  // first selecting-all, or click Save without noticing the field already
  // had content, and you silently re-save the SAME old token while
  // believing you replaced it. Starting blank means typing anything and
  // saving unambiguously replaces it, and an accidental empty-save is a
  // no-op (see save() below) rather than wiping the connection out.
  const [token, setToken] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState("");
  const connected = Boolean(config?.calendly_api_token);

  const save = async () => {
    if (!token.trim()) return;
    setSaving(true);
    setSaved(false);
    setSaveError("");
    const result = await onSaveFields({ calendly_api_token: token.trim() });
    setSaving(false);
    if (result?.ok) { setSaved(true); setToken(""); } else setSaveError(result?.error || "Save failed");
  };

  const disconnect = async () => {
    if (!window.confirm("Disconnect Calendly for this client? The agent will go back to asking leads for their preferred day/time.")) return;
    setSaving(true);
    setSaveError("");
    const result = await onSaveFields({ calendly_api_token: null });
    setSaving(false);
    if (result?.ok) { setSaved(true); setToken(""); } else setSaveError(result?.error || "Failed to disconnect");
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ fontSize: 12, color: "#8aaad0" }}>
        Generate a Personal Access Token from the client's Calendly account (Integrations &amp; Apps → API &amp; Webhooks → Generate New Token — not a "connect an app" OAuth button) and paste it below. {connected ? "Connected — paste a new token below to replace it." : "Not connected — the agent will just ask leads for their preferred day/time until this is set."}
      </div>
      <div style={{ display: "flex", gap: 6 }}>
        <input
          type="password" autoComplete="off" className="dg-input" style={{ fontSize: 12, flex: 1, boxSizing: "border-box" }}
          value={token} placeholder={connected ? "Paste a new token to replace the connected one" : "Calendly Personal Access Token"}
          onChange={(e) => { setToken(e.target.value); setSaved(false); setSaveError(""); }}
        />
        {connected && (
          <button className="btn btn-danger" style={{ fontSize: 10 }} onClick={disconnect} disabled={saving}>
            DISCONNECT
          </button>
        )}
      </div>
      <button className="btn btn-primary" style={{ fontSize: 10, alignSelf: "flex-start" }} onClick={save} disabled={saving || !token.trim()}>
        {saving ? "SAVING…" : saved ? "SAVED ✓" : "SAVE"}
      </button>
      {saveError && (
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#e05c5c" }}>{saveError}</div>
      )}
      <AgentCalendlyEventType config={config} onSaveFields={onSaveFields} />
      {connected && (
        <CalendlyWebhookConnect clientId={clientId} connected={Boolean(config?.calendly_webhook_uri)} autoError={config?.calendly_webhook_error} />
      )}
    </div>
  );
}

// The exact event type this client's agent should check — required, never
// inferred. A token can see event types belonging to OTHER people entirely
// (e.g. Dylan's own token, as an admin on a client's Calendly, also sees
// his own unrelated event types) — "just grab whichever comes back first"
// risks silently checking/booking against the wrong calendar the moment
// more than one client shares that ambiguity. Not a secret, so — unlike
// the token field above — this is safe to pre-fill and edit in place.
function AgentCalendlyEventType({ config, onSaveFields }) {
  const [url, setUrl] = useState(config?.calendly_event_type_url || "");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState("");

  useEffect(() => { setUrl(config?.calendly_event_type_url || ""); }, [config?.calendly_event_type_url]);

  const save = async () => {
    setSaving(true);
    setSaved(false);
    setSaveError("");
    const result = await onSaveFields({ calendly_event_type_url: url.trim() || null });
    setSaving(false);
    if (result?.ok) setSaved(true); else setSaveError(result?.error || "Save failed");
  };

  return (
    <div style={{ marginTop: 4, paddingTop: 10, borderTop: "1px solid rgba(255,255,255,0.06)" }}>
      <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#5a7aa0", marginBottom: 2 }}>
        EVENT TYPE / BOOKING LINK TO CHECK
      </div>
      <div style={{ fontSize: 11, color: "#8aaad0", marginBottom: 6 }}>
        The client's actual public Calendly link for the offer this agent books (e.g. their free consult) — copy it straight from Calendly. Required for availability checks to actually run, even with a token connected.
      </div>
      <div style={{ display: "flex", gap: 6 }}>
        <input
          className="dg-input" style={{ fontSize: 12, flex: 1, boxSizing: "border-box" }}
          value={url} placeholder="https://calendly.com/name/event-slug"
          onChange={(e) => { setUrl(e.target.value); setSaved(false); setSaveError(""); }}
        />
        <button className="btn btn-primary" style={{ fontSize: 10 }} onClick={save} disabled={saving}>
          {saving ? "SAVING…" : saved ? "SAVED ✓" : "SAVE"}
        </button>
      </div>
      {saveError && (
        <div style={{ marginTop: 4, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#e05c5c" }}>{saveError}</div>
      )}
    </div>
  );
}

// Database reactivation (client_reactivation.py): campaigns that text this
// client's EXISTING leads — past patients, old inquiries, quiet leads —
// never fresh ad leads. Each campaign = an audience (lead sources + tags)
// and its own touches; the agent rewrites each touch for the person.
const LEAD_SOURCE_LABELS = {
  past_patient: "Past patients", old_inquiry: "Old inquiries", import: "Imported lists",
  manual: "Added by hand", website: "Website bookings", inbound_sms: "Texted in on their own",
  ig_dm: "Instagram DMs", fb_dm: "Facebook DMs",
  meta_form: "Meta form leads", funnel: "Funnel leads",
};
const REACTIVATION_STATUS_COLOR = {
  draft: "#5a7aa0", active: "#4ade80", paused: "#f0b429", done: "#6ab0ff",
  queued: "#5a7aa0", replied: "#6ab0ff", booked: "#4ade80", completed: "#5a7aa0",
  opted_out: "#dc3c3c", excluded: "#5a7aa0",
};

function ReactivationChip({ label, count, on, onClick }) {
  return (
    <span
      onClick={onClick}
      style={{
        cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 5,
        padding: "3px 9px", borderRadius: 999, fontSize: 10.5,
        fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600,
        color: on ? "#e8f0ff" : "#8aaad0",
        background: on ? "rgba(58,123,213,0.35)" : "rgba(58,123,213,0.08)",
        border: `1px solid ${on ? "rgba(106,176,255,0.7)" : "rgba(58,123,213,0.25)"}`,
      }}
    >
      {label}<span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, opacity: 0.8 }}>{count}</span>
    </span>
  );
}

function ReactivationCampaignEditor({ clientId, options, campaign, onSaved, onCancel }) {
  const playbookInfo = (key) => options.playbooks.find((p) => p.key === key) || options.playbooks[0];
  const [playbook, setPlaybook] = useState(campaign?.playbook || "checkin");
  const [name, setName] = useState(campaign?.name || "");
  const [sources, setSources] = useState(campaign?.audience_sources || playbookInfo("checkin").sources);
  const [tags, setTags] = useState(campaign?.audience_tags || []);
  const [angle, setAngle] = useState(campaign?.angle || playbookInfo("checkin").angle);
  const [dailyCap, setDailyCap] = useState(campaign?.daily_cap || 30);
  const [touches, setTouches] = useState(campaign?.touches || playbookInfo("checkin").touches);
  // Only a campaign saved with a real offer end date keeps one; new last calls have none.
  const [endsOn] = useState(campaign?.ends_on || "");
  const lastCall = playbook === "last_call";
  const pickPlaybook = (key) => {
    setPlaybook(key); setPreview(null);
    if (!campaign) {
      const info = playbookInfo(key);
      setSources(info.sources); setTags([]); setAngle(info.angle); setTouches(info.touches);
    }
  };
  const [preview, setPreview] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const toggle = (list, setList, value) => {
    setList(list.includes(value) ? list.filter((v) => v !== value) : [...list, value]);
    setPreview(null);
  };
  const setTouch = (i, field, value) => setTouches(touches.map((t, j) => (j === i ? { ...t, [field]: value } : t)));

  const runPreview = async () => {
    const r = await fetch(API(`/clients/${clientId}/reactivation/preview`), {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ audience_sources: sources, audience_tags: tags, playbook, ends_on: endsOn || null }),
    });
    if (r.ok) setPreview(await r.json());
  };

  const save = async () => {
    setSaving(true); setError("");
    const body = {
      name, audience_sources: sources, audience_tags: tags, angle, daily_cap: Number(dailyCap) || 30,
      touches: touches.map((t) => ({ day: Number(t.day) || 0, body: t.body, ...(t.call ? { call: true } : {}) })),
      playbook, ends_on: endsOn || null,
    };
    const r = await fetch(API(campaign ? `/clients/${clientId}/reactivation/campaigns/${campaign.id}` : `/clients/${clientId}/reactivation/campaigns`), {
      method: campaign ? "PUT" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    setSaving(false);
    if (!r.ok) { setError((await r.json().catch(() => null))?.detail || "Failed to save"); return; }
    onSaved();
  };

  const label = (text) => (
    <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#5a7aa0", letterSpacing: "0.06em", margin: "12px 0 6px" }}>{text}</div>
  );

  return (
    <div style={{ padding: 12, borderRadius: 8, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(58,123,213,0.15)" }}>
      {label("PLAYBOOK")}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
        {options.playbooks.map((p) => (
          <ReactivationChip key={p.key} label={p.label} count={p.sender_name ? `from ${p.sender_name}` : ""}
            on={playbook === p.key} onClick={() => pickPlaybook(p.key)} />
        ))}
      </div>
      <div style={{ fontSize: 11, color: "#5a7aa0", marginTop: 6, lineHeight: 1.5 }}>{playbookInfo(playbook).description}</div>

      {label("CAMPAIGN NAME")}
      <input className="dg-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Past patients, fall check-in" style={{ width: "100%", fontSize: 12 }} />

      {lastCall && (
        <div style={{ fontSize: 11, color: "#5a7aa0", marginTop: 10, lineHeight: 1.5 }}>
          Starts by itself when the client's ad budget (Meta ad spend cap on Marketing Setup) is spent. Reaches Meta form
          and funnel leads since the ads launched who never came in: never booked, canceled or no-showed. Text first, then a
          call 24 hours later if they haven't replied.
        </div>
      )}

      {!lastCall && label("WHO IT TEXTS: ANY LEAD MATCHING ONE OF THESE")}
      {!lastCall && <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
        {options.sources.map((s) => (
          <ReactivationChip key={s.source} label={LEAD_SOURCE_LABELS[s.source] || s.source} count={s.count}
            on={sources.includes(s.source)} onClick={() => toggle(sources, setSources, s.source)} />
        ))}
      </div>}
      {!lastCall && options.tags.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 }}>
          {options.tags.map((t) => (
            <ReactivationChip key={t.tag} label={`#${t.tag}`} count={t.count}
              on={tags.includes(t.tag)} onClick={() => toggle(tags, setTags, t.tag)} />
          ))}
        </div>
      )}
      <div style={{ fontSize: 11, color: "#5a7aa0", marginTop: 6, lineHeight: 1.5 }}>
        Always skipped: anyone booked (upcoming or in the last 60 days), Unqualified, opted out, tagged Don't contact, a thread a human took over or one that said no in the last 90 days, or already in another open campaign.{lastCall ? "" : " Also: recent ad leads (last 30 days), anyone texted in the last 30 days, anyone in the regular follow-up."}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 8 }}>
        <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={runPreview} disabled={!lastCall && !sources.length && !tags.length}>PREVIEW AUDIENCE</button>
        {preview && (
          <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10.5, color: "#6ab0ff" }}>
            {preview.count} would be texted
          </span>
        )}
      </div>
      {preview?.sample?.length > 0 && (
        <div style={{ marginTop: 6, fontSize: 11, color: "#8aaad0", lineHeight: 1.6 }}>
          {preview.sample.map((p) => (
            <div key={p.phone}>{p.name} · {LEAD_SOURCE_LABELS[p.lead_source] || p.lead_source || "no source"}{p.issue ? ` · ${p.issue}` : ""}{p.source_detail ? ` · ${p.source_detail}` : ""}</div>
          ))}
        </div>
      )}

      {label("ANGLE (WHAT THIS OUTREACH IS ABOUT, AND THE OFFER IF ANY)")}
      <textarea className="dg-input" rows={2} value={angle} onChange={(e) => setAngle(e.target.value)}
        placeholder="e.g. Seasonal check-in for discharged patients; offer a returning-patient visit at the client's agreed price"
        style={{ width: "100%", fontSize: 12, resize: "vertical" }} />

      {!lastCall && label("NEW PEOPLE TEXTED PER DAY")}
      {!lastCall && <input className="dg-input" type="number" min={1} value={dailyCap} onChange={(e) => setDailyCap(e.target.value)} style={{ width: 90, fontSize: 12 }} />}

      {label("TOUCHES (THE AGENT PERSONALIZES EACH ONE; SENT AS WRITTEN IF THE AGENT IS OFF)")}
      {touches.map((t, i) => (
        <div key={i} style={{ display: "flex", gap: 8, marginBottom: 8, alignItems: "flex-start" }}>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 2 }}>
            <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 8.5, color: "#5a7aa0" }}>DAY</span>
            <input className="dg-input" type="number" min={0} value={t.day} onChange={(e) => setTouch(i, "day", e.target.value)} style={{ width: 54, fontSize: 12 }} />
            {lastCall && (
              <label style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 8.5, color: "#5a7aa0", display: "flex", alignItems: "center", gap: 3, cursor: "pointer" }}>
                <input type="checkbox" checked={Boolean(t.call)} onChange={(e) => setTouch(i, "call", e.target.checked)} />CALL
              </label>
            )}
          </div>
          <textarea className="dg-input" rows={2} value={t.body} onChange={(e) => setTouch(i, "body", e.target.value)} style={{ flex: 1, fontSize: 12, resize: "vertical" }} />
          <button className="btn btn-secondary" style={{ fontSize: 10, padding: "4px 8px" }} onClick={() => setTouches(touches.filter((_, j) => j !== i))}>✕</button>
        </div>
      ))}
      <button className="btn btn-secondary" style={{ fontSize: 10 }}
        onClick={() => setTouches([...touches, { day: (Number(touches[touches.length - 1]?.day) || 0) + (lastCall ? 1 : 7), body: "" }])}>
        + ADD TOUCH
      </button>
      <div style={{ fontSize: 11, color: "#5a7aa0", marginTop: 6 }}>
        Use {"{first_name}"}, {"{sender}"}, {"{business}"}, {"{checkin_question}"} (e.g. "how's your shoulder been doing?" from their tags), {"{offer}"} and {"{end_day}"}. "Reply STOP to opt out." is added to the first text automatically. Sends 10am-6pm, Monday-Saturday, clinic time.{lastCall ? " CALL = the voice agent calls first if they consented to calls, and texts only if they don't pick up." : " Check-ins repeat every 90 days, building on the last conversation, until they book or say no."}
      </div>

      <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
        <button className="btn btn-primary" style={{ fontSize: 11 }} onClick={save} disabled={saving || !name.trim()}>{saving ? "SAVING…" : "SAVE"}</button>
        <button className="btn btn-secondary" style={{ fontSize: 11 }} onClick={onCancel}>CANCEL</button>
      </div>
      {error && <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#e05c5c", marginTop: 6 }}>{error}</div>}
    </div>
  );
}

function ReactivationPeople({ clientId, campaignId }) {
  const [rows, setRows] = useState(null);
  useEffect(() => {
    fetch(API(`/clients/${clientId}/reactivation/campaigns/${campaignId}/enrollments`))
      .then((r) => (r.ok ? r.json() : [])).then(setRows);
  }, [clientId, campaignId]);
  if (!rows) return <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>LOADING…</div>;
  if (!rows.length) return <div style={{ fontSize: 12, color: "#5a7aa0" }}>Nobody enrolled yet. Start the campaign to enroll its audience.</div>;
  return (
    <div style={{ maxHeight: 320, overflowY: "auto", marginTop: 8 }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11.5 }}>
        <thead>
          <tr>
            {["Name", "Phone", "Status", "Texts", "Last text", "Note"].map((h) => (
              <th key={h} style={{ textAlign: "left", padding: "6px 8px", fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#5a7aa0" }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} style={{ borderTop: "1px solid rgba(58,123,213,0.08)" }}>
              <td style={{ padding: "6px 8px", color: "#d0e8ff" }}>{r.owner || "—"}</td>
              <td style={{ padding: "6px 8px", color: "#8aaad0" }}>{r.phone}</td>
              <td style={{ padding: "6px 8px", color: REACTIVATION_STATUS_COLOR[r.status] || "#8aaad0", fontFamily: "'Share Tech Mono', monospace", fontSize: 9.5 }}>{r.status.replace("_", " ").toUpperCase()}</td>
              <td style={{ padding: "6px 8px", color: "#8aaad0" }}>{r.touches_sent}</td>
              <td style={{ padding: "6px 8px", color: "#8aaad0" }}>{r.last_touch_at ? new Date(r.last_touch_at).toLocaleDateString() : "—"}</td>
              <td style={{ padding: "6px 8px", color: "#5a7aa0" }}>
                {r.cycle > 1 ? `Check-in #${r.cycle} · ` : ""}
                {r.end_reason || r.source_detail || ""}
                {r.next_checkin_at ? ` · next check-in ${new Date(r.next_checkin_at).toLocaleDateString()}` : ""}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Who hears from this client next, and when: reactivation texts and calls,
// 90-day check-ins, check-ins leads asked for (schedule_followup) and calls
// the voice agent has waiting (client_reactivation.queue()).
function ReactivationQueue({ clientId }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(null);
  const load = () => fetch(API(`/clients/${clientId}/reactivation/queue`)).then((r) => (r.ok ? r.json() : { items: [] })).then(setData);
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [clientId]);
  const stop = async (item) => {
    const what = item.kind === "asked_followup" ? "Cancel this check-in they asked for?" : `Stop all reactivation texts to ${item.name || item.phone}, including future 90-day check-ins?`;
    if (!window.confirm(what)) return;
    setBusy(`${item.kind}-${item.id}`);
    await fetch(API(`/clients/${clientId}/reactivation/queue/stop`), {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind: item.kind, id: String(item.id) }),
    });
    setBusy(null);
    load();
  };
  if (!data) return <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>LOADING…</div>;
  const fmt = (iso, est) => {
    const d = new Date(est ? `${iso}T12:00:00` : iso);
    return (est ? "~" : "") + d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" }) +
      (est ? "" : ` ${d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}`);
  };
  return (
    <div style={{ padding: 12, borderRadius: 8, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(58,123,213,0.12)" }}>
      <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9.5, color: "#5a7aa0", letterSpacing: "0.08em", marginBottom: 6 }}>
        QUEUE · {data.items.length} UPCOMING{data.paused ? " · REACTIVATION IS SWITCHED OFF, NOTHING BELOW SENDS YET" : ""}
      </div>
      {!data.items.length ? (
        <div style={{ fontSize: 12, color: "#5a7aa0" }}>Nobody is lined up right now.</div>
      ) : (
        <div style={{ maxHeight: 360, overflowY: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11.5 }}>
            <thead>
              <tr>
                {["When", "Name", "Phone", "What", "From", ""].map((h) => (
                  <th key={h} style={{ textAlign: "left", padding: "6px 8px", fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#5a7aa0" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.items.map((it) => (
                <tr key={`${it.kind}-${it.id}`} style={{ borderTop: "1px solid rgba(58,123,213,0.08)", opacity: it.paused ? 0.55 : 1 }}>
                  <td style={{ padding: "6px 8px", color: "#d0e8ff", whiteSpace: "nowrap" }}>{it.due ? fmt(it.due, it.estimated) : it.when_label}</td>
                  <td style={{ padding: "6px 8px", color: "#d0e8ff" }}>{it.name || "—"}</td>
                  <td style={{ padding: "6px 8px", color: "#8aaad0" }}>{it.phone}</td>
                  <td style={{ padding: "6px 8px", color: "#8aaad0" }}>{it.what}</td>
                  <td style={{ padding: "6px 8px", color: "#5a7aa0" }}>{it.campaign}{it.paused ? " (paused)" : ""}</td>
                  <td style={{ padding: "6px 8px" }}>
                    {it.stoppable && (
                      <button className="btn btn-secondary" style={{ fontSize: 9, padding: "3px 8px" }} disabled={busy === `${it.kind}-${it.id}`} onClick={() => stop(it)}>
                        {it.kind === "asked_followup" ? "CANCEL" : "STOP"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div style={{ fontSize: 10.5, color: "#5a7aa0", marginTop: 6 }}>
        ~ = estimated from the daily cap. Sends 10am-6pm Mon-Sat clinic time. STOP takes someone out for good (the owner or the patient said no).
      </div>
    </div>
  );
}

// The offer every reactivation text names, plus a one-line reminder of what
// it is ("our Free Back Pain Discovery Call (a free 20-minute call with a
// PT)"). Auto-filled from the agent context the first time; change it when
// the client's offer changes (the last call's 30-day text then says "new").
function ReactivationOffer({ clientId }) {
  const [offer, setOffer] = useState(null);
  const [form, setForm] = useState({ name: "", detail: "" });
  const [msg, setMsg] = useState("");
  useEffect(() => {
    fetch(API(`/clients/${clientId}/reactivation/offer`)).then((r) => (r.ok ? r.json() : null)).then((o) => {
      setOffer(o || { name: "", detail: "" }); setForm({ name: o?.name || "", detail: o?.detail || "" });
    });
  }, [clientId]);
  if (!offer) return null;
  const dirty = form.name !== (offer.name || "") || form.detail !== (offer.detail || "");
  const save = async () => {
    const r = await fetch(API(`/clients/${clientId}/reactivation/offer`), {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(form),
    });
    const d = await r.json().catch(() => null);
    if (r.ok) { setOffer(d); setMsg("Saved"); } else setMsg(d?.detail || "Failed");
  };
  return (
    <div style={{ padding: 12, borderRadius: 8, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(58,123,213,0.12)" }}>
      <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9.5, color: "#5a7aa0", letterSpacing: "0.08em" }}>
        OFFER IN THESE TEXTS{offer.auto && offer.name ? " · AUTO-FILLED, CHECK IT" : ""}
      </div>
      <div style={{ display: "flex", gap: 8, marginTop: 6, flexWrap: "wrap" }}>
        <input className="dg-input" placeholder="Free Back Pain Discovery Call" value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })} style={{ fontSize: 12, flex: "1 1 200px" }} />
        {dirty && <button className="btn btn-primary" style={{ fontSize: 10 }} onClick={save}>SAVE</button>}
      </div>
      <div style={{ fontSize: 11, color: "#5a7aa0", marginTop: 6, lineHeight: 1.5 }}>
        Reads as: "our {form.name || "<offer>"} is wrapping up". Change it when the client's
        offer changes: ad leads who heard about the old one get "saw you missed out on our {"<old>"}, we're running a new special" next time.
        {msg && <span style={{ color: "#6ab0ff" }}> {msg}</span>}
      </div>
    </div>
  );
}

function ReactivationAgent({ clientId, agentEnabled }) {
  const [options, setOptions] = useState(null);
  const [campaigns, setCampaigns] = useState([]);
  const [editing, setEditing] = useState(null); // "new" | campaign id | null
  const [peopleFor, setPeopleFor] = useState(null);
  const [busy, setBusy] = useState(null);
  const [message, setMessage] = useState("");
  const [showQueue, setShowQueue] = useState(false);

  const load = async () => {
    const [o, c] = await Promise.all([
      fetch(API(`/clients/${clientId}/reactivation/options`)),
      fetch(API(`/clients/${clientId}/reactivation/campaigns`)),
    ]);
    if (o.ok) setOptions(await o.json());
    if (c.ok) setCampaigns(await c.json());
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [clientId]);

  const act = async (campaign, action) => {
    if (action === "start" && !window.confirm(`Start "${campaign.name}"? It begins reaching out to its audience${campaign.playbook === "last_call" ? " now (text, then a call 24 hours later if no reply)" : ` (up to ${campaign.daily_cap} new people a day)`} from this client's number.`)) return;
    if (action === "delete" && !window.confirm(`Delete "${campaign.name}"?`)) return;
    setBusy(campaign.id); setMessage("");
    const r = await fetch(
      API(`/clients/${clientId}/reactivation/campaigns/${campaign.id}${action === "delete" ? "" : `/${action}`}`),
      { method: action === "delete" ? "DELETE" : "POST" },
    );
    const data = await r.json().catch(() => null);
    if (!r.ok) setMessage(data?.detail || "Failed");
    else if (action === "start") setMessage(`"${campaign.name}" is running. ${data.added} ${data.added === 1 ? "person" : "people"} added.`);
    setBusy(null);
    await load();
  };

  if (!options) return <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>LOADING…</div>;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={() => setShowQueue(!showQueue)}>
          {showQueue ? "HIDE QUEUE" : "VIEW QUEUE"}
        </button>
        <span style={{ fontSize: 11, color: "#5a7aa0" }}>
          Check-ins start when the ads spend their first dollar; the last call when the ad budget is spent.
        </span>
      </div>
      {showQueue && <ReactivationQueue clientId={clientId} />}
      <ReactivationOffer clientId={clientId} />
      {!agentEnabled && (
        <div style={{ fontSize: 11.5, color: "#f0b429" }}>
          The Facebook Leads Agent is off for this client, so touches go out exactly as written and replies wait for a human. Turn it on to have the agent personalize touches and answer replies.
        </div>
      )}
      {campaigns.length === 0 && editing !== "new" && (
        <div style={{ fontSize: 12, color: "#5a7aa0" }}>
          No campaigns yet. Import the client's past patients or old inquiries from their portal (Leads → Import CSV, pick the list type), then create a campaign for that audience.
        </div>
      )}
      {campaigns.map((c) => (
        editing === c.id ? (
          <ReactivationCampaignEditor key={c.id} clientId={clientId} options={options} campaign={c}
            onSaved={() => { setEditing(null); load(); }} onCancel={() => setEditing(null)} />
        ) : (
          <div key={c.id} style={{ padding: 12, borderRadius: 8, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(58,123,213,0.12)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
              <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600, fontSize: 12.5, color: "#d0e8ff" }}>{c.name}</div>
              <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: REACTIVATION_STATUS_COLOR[c.status], letterSpacing: "0.06em" }}>{c.status.toUpperCase()}</span>
            </div>
            <div style={{ fontSize: 11, color: "#5a7aa0", marginTop: 4 }}>
              {(options.playbooks.find((p) => p.key === c.playbook) || {}).label || "Check-in"}{" · "}
              {c.playbook === "last_call"
                ? "ad leads who never came in"
                : [...c.audience_sources.map((s) => LEAD_SOURCE_LABELS[s] || s), ...c.audience_tags.map((t) => `#${t}`)].join(", ") || "No audience picked"}
              {c.auto_trigger ? ` · started automatically (${c.auto_trigger === "first_spend" ? "first ad dollar" : "ad budget spent"})` : ""}
              {" · "}{c.touches.length} touches{c.playbook === "last_call" ? "" : ` · ${c.daily_cap}/day`}
            </div>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#8aaad0", marginTop: 6 }}>
              {c.stats.enrolled} enrolled · {c.stats.texted} texted · {c.stats.replied} replied · {c.stats.booked} booked · {c.stats.opted_out} opted out
            </div>
            <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
              {c.status !== "active" && (
                <button className="btn btn-primary" style={{ fontSize: 10 }} disabled={busy === c.id} onClick={() => act(c, "start")}>
                  {c.status === "draft" ? "START" : c.status === "paused" ? "RESUME" : "ADD NEWLY ELIGIBLE"}
                </button>
              )}
              {c.status === "active" && (
                <button className="btn btn-secondary" style={{ fontSize: 10 }} disabled={busy === c.id} onClick={() => act(c, "pause")}>PAUSE</button>
              )}
              <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={() => setEditing(c.id)}>EDIT</button>
              <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={() => setPeopleFor(peopleFor === c.id ? null : c.id)}>
                {peopleFor === c.id ? "HIDE PEOPLE" : "PEOPLE"}
              </button>
              {c.stats.texted === 0 && (
                <button className="btn btn-secondary" style={{ fontSize: 10 }} disabled={busy === c.id} onClick={() => act(c, "delete")}>DELETE</button>
              )}
            </div>
            {peopleFor === c.id && <ReactivationPeople clientId={clientId} campaignId={c.id} />}
          </div>
        )
      ))}
      {editing === "new" ? (
        <ReactivationCampaignEditor clientId={clientId} options={options} campaign={null}
          onSaved={() => { setEditing(null); load(); }} onCancel={() => setEditing(null)} />
      ) : (
        <button className="btn btn-secondary" style={{ fontSize: 11, alignSelf: "flex-start" }} onClick={() => setEditing("new")}>+ NEW CAMPAIGN</button>
      )}
      {message && <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#6ab0ff" }}>{message}</div>}
    </div>
  );
}

// Social media conversation agent (client_dm_agent.py): answers Instagram and
// Facebook DMs, gets a number or a booking inside Meta's 24-hour window.
const DM_STATUS_COLOR = {
  ai_active: "#4ade80", booked: "#6ab0ff", escalated: "#f0b429", closed: "#5a7aa0", unqualified: "#9aa3b2",
};

function DmTestChat({ clientId }) {
  const [platform, setPlatform] = useState("instagram");
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [phone, setPhone] = useState(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  const send = async () => {
    const text = draft.trim();
    if (!text) return;
    const next = [...messages, { role: "user", content: text }];
    setMessages(next); setDraft(""); setSending(true); setError("");
    const r = await fetch(API(`/clients/${clientId}/dm-agent/test`), {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ platform, messages: next, phone }),
    });
    const data = await r.json().catch(() => null);
    setSending(false);
    if (!r.ok) { setError(data?.detail || "Failed"); return; }
    if (data.phone) setPhone(data.phone);
    setMessages([...next, { role: "assistant", content: data.reply || "(no reply)" }]);
  };

  return (
    <div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8 }}>
        <select className="dg-input" value={platform} onChange={(e) => setPlatform(e.target.value)} style={{ fontSize: 11, padding: "5px 8px", width: 130 }}>
          <option value="instagram">Instagram</option>
          <option value="facebook">Facebook</option>
        </select>
        <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={() => { setMessages([]); setPhone(null); setError(""); }}>RESET</button>
        {phone && <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#6ab0ff" }}>number captured: {phone}</span>}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 280, overflowY: "auto", marginBottom: 8 }}>
        {messages.map((m, i) => (
          <div key={i} style={{
            alignSelf: m.role === "user" ? "flex-start" : "flex-end", maxWidth: "80%", whiteSpace: "pre-wrap",
            padding: "7px 10px", borderRadius: 10, fontSize: 12, lineHeight: 1.45,
            background: m.role === "user" ? "rgba(255,255,255,0.05)" : "rgba(58,123,213,0.25)", color: "#d0e8ff",
          }}>{m.content}</div>
        ))}
        {sending && <div style={{ alignSelf: "flex-end", fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#5a7aa0" }}>TYPING…</div>}
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        <input className="dg-input" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Message the agent as a lead would…"
          onKeyDown={(e) => { if (e.key === "Enter" && !sending) send(); }} style={{ flex: 1, fontSize: 12 }} />
        <button className="btn btn-primary" style={{ fontSize: 11 }} onClick={send} disabled={sending || !draft.trim()}>SEND</button>
      </div>
      <div style={{ fontSize: 11, color: "#5a7aa0", marginTop: 6 }}>
        Test mode reads the real calendar but saves, books and escalates nothing.
      </div>
      {error && <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#e05c5c", marginTop: 4 }}>{error}</div>}
    </div>
  );
}

function DmThreads({ clientId }) {
  const [threads, setThreads] = useState(null);
  const [openId, setOpenId] = useState(null);
  const [messages, setMessages] = useState([]);

  const load = async () => {
    const r = await fetch(API(`/clients/${clientId}/dm-agent/threads`));
    if (r.ok) setThreads(await r.json());
  };
  const loadMessages = async (id) => {
    const r = await fetch(API(`/clients/${clientId}/dm-agent/threads/${id}/messages`));
    if (r.ok) setMessages(await r.json());
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [clientId]);
  // DMs arrive via webhook, so poll to show new threads and replies live.
  useEffect(() => {
    const t = setInterval(() => { load(); if (openId) loadMessages(openId); }, 10000);
    return () => clearInterval(t);
    // eslint-disable-next-line
  }, [clientId, openId]);

  const open = async (id) => {
    if (openId === id) { setOpenId(null); return; }
    setOpenId(id); setMessages([]);
    await loadMessages(id);
  };
  const handBack = async (id) => {
    await fetch(API(`/clients/${clientId}/dm-agent/threads/${id}/hand-back`), { method: "POST" });
    await load();
  };

  if (!threads) return <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>LOADING…</div>;
  if (!threads.length) return <div style={{ fontSize: 12, color: "#5a7aa0" }}>No DMs yet.</div>;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {threads.map((t) => (
        <div key={t.id} style={{ padding: 10, borderRadius: 8, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(58,123,213,0.12)" }}>
          <div onClick={() => open(t.id)} style={{ cursor: "pointer", display: "flex", justifyContent: "space-between", gap: 8 }}>
            <div>
              <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600, fontSize: 12.5, color: "#d0e8ff" }}>
                {t.sender_name || "Unknown"} <span style={{ fontSize: 10.5, color: "#5a7aa0", fontWeight: 400 }}>· {t.platform === "instagram" ? "Instagram" : "Facebook"}{t.phone ? ` · ${t.phone}` : ""}</span>
              </div>
              <div style={{ fontSize: 11, color: "#8aaad0", marginTop: 2 }}>{(t.last_body || "").slice(0, 90)}</div>
            </div>
            <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: DM_STATUS_COLOR[t.status] || "#8aaad0", whiteSpace: "nowrap" }}>
              {t.status.replace("_", " ").toUpperCase()}
            </span>
          </div>
          {openId === t.id && (
            <div style={{ marginTop: 8 }}>
              {t.status_reason && <div style={{ fontSize: 11, color: "#f0b429", marginBottom: 6 }}>{t.status_reason}</div>}
              <div style={{ display: "flex", flexDirection: "column", gap: 5, maxHeight: 260, overflowY: "auto" }}>
                {messages.map((m) => (
                  <div key={m.id} style={{
                    alignSelf: m.direction === "inbound" ? "flex-start" : "flex-end", maxWidth: "80%", whiteSpace: "pre-wrap",
                    padding: "6px 9px", borderRadius: 9, fontSize: 11.5,
                    background: m.direction === "inbound" ? "rgba(255,255,255,0.05)" : m.sender === "human" ? "rgba(240,180,41,0.2)" : "rgba(58,123,213,0.25)",
                    color: "#d0e8ff",
                  }}>
                    {m.body}
                    <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 8.5, color: "#5a7aa0", marginTop: 2 }}>
                      {m.sender === "human" ? "CLINIC STAFF · " : m.sender === "ai" ? "AI · " : ""}{new Date(m.created_at).toLocaleString()}
                    </div>
                  </div>
                ))}
              </div>
              {(t.status !== "ai_active" || t.human_last_at) && (
                <button className="btn btn-secondary" style={{ fontSize: 10, marginTop: 8 }} onClick={() => handBack(t.id)}>HAND BACK TO AI</button>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function SocialMediaAgent({ clientId, config, onSaveFields }) {
  const [connecting, setConnecting] = useState(false);
  const [result, setResult] = useState(null);

  const connect = async () => {
    setConnecting(true); setResult(null);
    const r = await fetch(API(`/clients/${clientId}/dm-agent/connect`), { method: "POST" });
    setResult(await r.json().catch(() => ({ ok: false, error: "Failed" })));
    setConnecting(false);
    await onSaveFields({});
  };

  const block = (title, children) => (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#5a7aa0", letterSpacing: "0.06em", marginBottom: 6 }}>{title}</div>
      {children}
    </div>
  );
  const row = (label, value, ok) => (
    <div style={{ fontSize: 11.5, color: ok ? "#8aaad0" : "#f0b429", marginBottom: 3 }}>{ok ? "✓" : "○"} {label}{value ? `: ${value}` : ""}</div>
  );

  return (
    <div>
      {block("STATUS", (
        <div>
          <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "#d0e8ff", marginBottom: 10, cursor: "pointer" }}>
            <input type="checkbox" checked={Boolean(config?.dm_agent_enabled)} onChange={(e) => onSaveFields({ dm_agent_enabled: e.target.checked })} />
            Agent replies to DMs
          </label>
          {row("Facebook Page ID", config?.meta_page_id, Boolean(config?.meta_page_id))}
          {row("Instagram account linked to the Page", config?.instagram_account_id, Boolean(config?.instagram_account_id))}
          {row("Page subscribed to DMs", config?.dm_connected_at ? new Date(config.dm_connected_at).toLocaleDateString() : null, Boolean(config?.dm_connected_at))}
          {config?.dm_connect_error && <div style={{ fontSize: 11, color: "#e05c5c", marginTop: 4 }}>{config.dm_connect_error}</div>}
          <button className="btn btn-secondary" style={{ fontSize: 10, marginTop: 8 }} onClick={connect} disabled={connecting}>
            {connecting ? "CONNECTING…" : config?.dm_connected_at ? "RECONNECT" : "CONNECT DMS"}
          </button>
          {result && !result.ok && <div style={{ fontSize: 11, color: "#e05c5c", marginTop: 4 }}>{result.error}</div>}
          <div style={{ fontSize: 11, color: "#5a7aa0", marginTop: 8, lineHeight: 1.55 }}>
            One-time Meta setup: the System User token needs pages_messaging, instagram_basic and instagram_manage_messages; in the Meta app's Webhooks settings, subscribe the Page object to messages + message_echoes and the Instagram object to messages, both pointing at /webhooks/meta-leadgen; and in Meta Business Suite turn off automated replies (so they don't double-answer). Real DMs from the public need those permissions approved in Meta App Review; until then only people with a role on the app get through.
          </div>
        </div>
      ))}
      {block("TEST CHAT", <DmTestChat clientId={clientId} />)}
      {block("CONVERSATIONS", <DmThreads clientId={clientId} />)}
    </div>
  );
}

// AI voice agent (client_voice_agent.py): Retell calls new Meta + funnel
// leads first, texts after no answer. Growth package only.
const VOICE_OUTCOME_COLOR = { booked: "#3ecf8e", answered: "#8ab4f8", not_interested: "#f0b429", no_answer: "#5a7aa0", voicemail: "#5a7aa0", skipped: "#3a5a80", error: "#e05c5c", unknown: "#f0b429" };

function VoiceAgent({ clientId, config, onSaveFields }) {
  const [data, setData] = useState(null);
  const [voices, setVoices] = useState([]);
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState(null);
  const [testPhone, setTestPhone] = useState("");
  const [openCall, setOpenCall] = useState(null);

  const load = async () => {
    const r = await fetch(API(`/clients/${clientId}/voice-agent`));
    if (r.ok) setData(await r.json());
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [clientId]);
  useEffect(() => {
    if (!data?.retell_key_set || voices.length) return;
    fetch(API(`/voice-agent/voices`)).then((r) => (r.ok ? r.json() : [])).then((v) => setVoices(Array.isArray(v) ? v : [])).catch(() => {});
  }, [data, voices.length]);

  const act = async (label, path, body) => {
    setBusy(label); setMsg(null);
    const r = await fetch(API(path), { method: "POST", headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined });
    const j = await r.json().catch(() => ({}));
    setMsg(r.ok ? { ok: true, text: `${label}: done` } : { ok: false, text: j.detail || `${label} failed` });
    setBusy("");
    await onSaveFields({});
    await load();
  };

  const block = (title, children) => (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#5a7aa0", letterSpacing: "0.06em", marginBottom: 6 }}>{title}</div>
      {children}
    </div>
  );
  const row = (label, value, ok) => (
    <div style={{ fontSize: 11.5, color: ok ? "#8aaad0" : "#f0b429", marginBottom: 3 }}>{ok ? "✓" : "○"} {label}{value ? `: ${value}` : ""}</div>
  );
  const s = data?.stats_30d || {};

  return (
    <div>
      {block("STATUS", (
        <div>
          {row("RETELL_API_KEY on the server", null, Boolean(data?.retell_key_set))}
          {row("Client's Twilio number", config?.twilio_number, Boolean(config?.twilio_number))}
          {row("Text agent context (the voice agent uses the same one)", null, Boolean(config?.response_ai_context))}
          {row("Retell agent", config?.voice_synced_at ? `synced ${new Date(config.voice_synced_at).toLocaleString()}` : null, Boolean(config?.retell_agent_id))}
          {config?.voice_sync_error && <div style={{ fontSize: 11, color: "#e05c5c", margin: "2px 0 4px" }}>{config.voice_sync_error}</div>}
          {row("AI-call consent line live on the Meta Instant Form", config?.voice_consent_meta_since ? `since ${new Date(config.voice_consent_meta_since).toLocaleString()}` : "Meta leads are NOT called until you stamp this", Boolean(config?.voice_consent_meta_since))}
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginTop: 10 }}>
            <select className="dg-input" style={{ maxWidth: 260, fontSize: 11 }} value={config?.voice_id || ""} onChange={(e) => onSaveFields({ voice_id: e.target.value || null })}>
              <option value="">Default voice</option>
              {voices.map((v) => <option key={v.voice_id} value={v.voice_id}>{v.voice_name} · {v.provider} · {v.gender || ""} {v.accent || ""}</option>)}
            </select>
            <input className="dg-input" type="number" step="0.05" min="0.5" max="2" style={{ maxWidth: 90, fontSize: 11 }} title="Speaking speed (1.0 = normal)" placeholder="Speed 1.0" defaultValue={config?.voice_speed || ""}
              onBlur={(e) => { const n = parseFloat(e.target.value); const val = Number.isFinite(n) ? Math.min(2, Math.max(0.5, n)) : null; if (val !== (config?.voice_speed ?? null)) onSaveFields({ voice_speed: val }); }} />
            <input className="dg-input" style={{ maxWidth: 150, fontSize: 11 }} placeholder="Name (default: voice's)" defaultValue={config?.voice_agent_name || ""}
              onBlur={(e) => { if ((e.target.value || "") !== (config?.voice_agent_name || "")) onSaveFields({ voice_agent_name: e.target.value.trim() || null }); }} />
            <button className="btn btn-secondary" style={{ fontSize: 10 }} disabled={!!busy} onClick={() => act("Sync agent", `/clients/${clientId}/voice-agent/sync`)}>
              {busy === "Sync agent" ? "SYNCING…" : config?.retell_agent_id ? "SYNC AGENT" : "CREATE AGENT"}
            </button>
            <button className="btn btn-secondary" style={{ fontSize: 10 }} disabled={!!busy} onClick={() => act("Consent stamp", `/clients/${clientId}/voice-agent/consent-live?live=${config?.voice_consent_meta_since ? "false" : "true"}`)}>
              {config?.voice_consent_meta_since ? "CLEAR CONSENT STAMP" : "CONSENT LINE IS LIVE NOW"}
            </button>
          </div>
          <div style={{ fontSize: 10.5, color: "#5a7aa0", marginTop: 6 }}>Re-sync after changing the voice, speed (1.0 = normal), name, or the Facebook Leads Agent's context/rules. It introduces itself by that name and the clinic.</div>
          <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "#d0e8ff", marginTop: 12, cursor: "pointer" }}>
            <input type="checkbox" checked={Boolean(config?.voice_agent_enabled)} onChange={(e) => onSaveFields({ voice_agent_enabled: e.target.checked })} />
            Voice agent calls new leads (also shows the call-consent box on the booking page)
          </label>
          {data?.ready_problem && config?.voice_agent_enabled && <div style={{ fontSize: 11, color: "#f0b429", marginTop: 4 }}>Not calling yet: {data.ready_problem}</div>}
          {msg && <div style={{ fontSize: 11, color: msg.ok ? "#3ecf8e" : "#e05c5c", marginTop: 6 }}>{msg.text}</div>}
          <div style={{ fontSize: 11, color: "#5a7aa0", marginTop: 8, lineHeight: 1.55 }}>
            Flow: AI call ~3 min after a Meta lead (funnel: 10 min after they leave the booking page unfinished), no text first. No answer → immediate redial → voicemail, then the text agent's opener. Retries +2h, next day ~10:30, day after ~16:30, 8am-8pm clinic time only. Stops when they text back, book, opt out or say stop. After-hours leads get the text now and the first call at 9am.
          </div>
        </div>
      ))}
      {block("TEST CALL (no booking, no texts, no tags)", (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <input className="dg-input" style={{ maxWidth: 200, fontSize: 12 }} placeholder="(754) 248-5326" value={testPhone} onChange={(e) => setTestPhone(e.target.value)} />
          <button className="btn btn-primary" style={{ fontSize: 10 }} disabled={!!busy || !testPhone.trim()} onClick={() => act("Test call", `/clients/${clientId}/voice-agent/test-call`, { phone: testPhone })}>
            {busy === "Test call" ? "QUEUING…" : "CALL ME"}
          </button>
          <button className="btn btn-secondary" style={{ fontSize: 10 }} onClick={load}>REFRESH</button>
        </div>
      ))}
      {block("LAST 30 DAYS", (
        <div style={{ fontSize: 12, color: "#d0e8ff" }}>
          {s.leads || 0} leads called · {s.reached || 0} reached{s.leads ? ` (${Math.round((100 * (s.reached || 0)) / s.leads)}%)` : ""} · {s.booked || 0} booked on the call
        </div>
      ))}
      {block("CALLS", (
        <div>
          {!(data?.calls || []).length && <div style={{ fontSize: 11.5, color: "#5a7aa0" }}>No calls yet.</div>}
          {(data?.calls || []).map((c) => (
            <div key={c.id} style={{ padding: "7px 10px", borderRadius: 6, background: "rgba(255,255,255,0.02)", marginBottom: 4, cursor: c.transcript || c.summary ? "pointer" : "default" }} onClick={() => setOpenCall(openCall === c.id ? null : c.id)}>
              <div style={{ display: "flex", gap: 10, fontSize: 11.5, color: "#d0e8ff", flexWrap: "wrap" }}>
                <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#5a7aa0" }}>{new Date(c.dialed_at || c.run_at).toLocaleString()}</span>
                <span>{c.lead_name || c.phone}</span>
                <span style={{ color: "#5a7aa0" }}>{c.source} · call {c.attempt}{c.double_dial ? " (redial)" : ""}</span>
                <span style={{ color: VOICE_OUTCOME_COLOR[c.outcome] || "#8aaad0" }}>{c.outcome || c.status}</span>
                {c.duration_ms ? <span style={{ color: "#5a7aa0" }}>{Math.round(c.duration_ms / 1000)}s</span> : null}
                {c.error && <span style={{ color: "#5a7aa0" }}>{c.error}</span>}
              </div>
              {openCall === c.id && (
                <div style={{ marginTop: 6, fontSize: 11.5, color: "#8aaad0", whiteSpace: "pre-wrap", lineHeight: 1.5 }}>
                  {c.summary && <div style={{ marginBottom: 6 }}><b>Summary:</b> {c.summary}</div>}
                  {c.recording_url && <div style={{ marginBottom: 6 }}><a href={c.recording_url} target="_blank" rel="noreferrer" style={{ color: "#3a7bd5" }} onClick={(e) => e.stopPropagation()}>Recording</a></div>}
                  {c.transcript}
                </div>
              )}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

// Dedicated "Agents" tab — an accordion of every AI agent running for this
// client. The Facebook Leads Agent (response_ai.py's full admin surface:
// context, sequence, rules) and the Database Reactivation Agent are fixed
// rows; additional rows are placeholder agent slots (client_agents table)
// named ahead of being built. Fetches/saves through the
// same generic marketing-config endpoint every other per-client config
// field in this file already uses.
// One collapsible row in the Agents tab's accordion — click the header to
// expand/collapse, same interaction as the Finance tab's transaction rows
// (expandedTxn above).
function AgentAccordionItem({ title, subtitle, open, onToggle, onDelete, status, children }) {
  return (
    <Card pad={0} style={{ marginBottom: 12, overflow: "visible", borderColor: open ? T.lineStrong : undefined }}>
      <div onClick={onToggle} role="button" tabIndex={0}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onToggle(); } }}
        style={{ display: "flex", alignItems: "center", gap: 14, padding: "16px 18px", cursor: "pointer" }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <span style={{ fontFamily: T.display, fontWeight: 600, fontSize: 15, color: T.text }}>{title}</span>
            {status && <Pill tone={status.tone} dot>{status.label}</Pill>}
          </div>
          {subtitle && <div style={{ fontSize: 13, color: T.textMute, marginTop: 3, lineHeight: 1.45 }}>{subtitle}</div>}
        </div>
        {onDelete && (
          <button onClick={(e) => { e.stopPropagation(); onDelete(); }} className="btn btn-danger" style={{ padding: "4px 10px", fontSize: 12 }}>Remove</button>
        )}
        <span style={{ color: T.textMute, fontSize: 14, transform: open ? "rotate(90deg)" : "none", transition: "transform 0.15s" }}>›</span>
      </div>
      {open && <div style={{ padding: "4px 18px 18px", borderTop: `1px solid ${T.line}`, paddingTop: 16 }}>{children}</div>}
    </Card>
  );
}

function ClientAgentSetup({ clientId }) {
  const [config, setConfig] = useState(null);
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [openAgent, setOpenAgent] = useState(null); // "facebook" | a client_agents row id | null
  const [showAddAgent, setShowAddAgent] = useState(false);
  const [newAgentName, setNewAgentName] = useState("");
  const [addingAgent, setAddingAgent] = useState(false);

  const load = async () => {
    const [configRes, agentsRes] = await Promise.all([
      fetch(API(`/clients/${clientId}/marketing-config`)),
      fetch(API(`/clients/${clientId}/agents`)),
    ]);
    if (configRes.ok) setConfig(await configRes.json());
    if (agentsRes.ok) setAgents(await agentsRes.json());
    setLoading(false);
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [clientId]);

  const saveFields = async (fields) => {
    let result = { ok: true, error: null };
    try {
      const r = await fetch(API(`/clients/${clientId}/marketing-config`), {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(fields),
      });
      if (!r.ok) {
        const detail = await r.json().catch(() => null);
        result = { ok: false, error: detail?.detail || "Failed to save" };
        setError(result.error);
      } else {
        setError("");
      }
    } catch (e) {
      result = { ok: false, error: e.message };
      setError(e.message);
    }
    await load();
    return result;
  };

  const addAgent = async () => {
    const name = newAgentName.trim();
    if (!name) return;
    setAddingAgent(true);
    const r = await fetch(API(`/clients/${clientId}/agents`), {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    if (r.ok) {
      const agent = await r.json();
      setAgents((prev) => [...prev, agent]);
      setNewAgentName("");
      setShowAddAgent(false);
    }
    setAddingAgent(false);
  };

  const deleteAgent = async (agentId) => {
    if (!window.confirm("Remove this agent slot?")) return;
    const r = await fetch(API(`/clients/${clientId}/agents/${agentId}`), { method: "DELETE" });
    if (r.ok) {
      setAgents((prev) => prev.filter((a) => a.id !== agentId));
      if (openAgent === agentId) setOpenAgent(null);
    }
  };

  if (loading) return <div style={{ padding: 16, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>LOADING…</div>;

  const section = (title, description, children) => (
    <div style={{ marginBottom: 14, padding: 16, borderRadius: 12, background: T.surface2, border: `1px solid ${T.line}` }}>
      <SectionTitle title={title} hint={description} />
      {children}
    </div>
  );
  const onOff = (on) => (on ? { tone: "good", label: "On" } : { tone: "neutral", label: "Off" });

  return (
    <div>
      <AgentAccordionItem
        title="Client Success Manager"
        subtitle="Weekly reports, the final report, health score, milestone texts, onboarding check-ins and the client's questions."
        status={{ tone: "info", label: "AI CSM" }}
        open={openAgent === "csm"}
        onToggle={() => setOpenAgent(openAgent === "csm" ? null : "csm")}
      >
        <ClientSuccessAgent clientId={clientId} />
      </AgentAccordionItem>

      <AgentAccordionItem
        title="Text Agent (Facebook leads)"
        subtitle="Texts new leads from the client's own number, answers questions and books them."
        status={onOff(config?.response_ai_enabled)}
        open={openAgent === "facebook"}
        onToggle={() => setOpenAgent(openAgent === "facebook" ? null : "facebook")}
      >
        {section(
          "Enable & Context",
          "The agent's knowledge of the business — enable it and write or generate its context.",
          <ResponseAiSetup clientId={clientId} config={config} onSaveFields={saveFields} />
        )}
        {section(
          "SMS Sequence",
          null,
          <AgentSequenceEditor config={config} onSaveFields={saveFields} />
        )}
        {section(
          "Rules",
          "Behavioral guardrails, enforced by the agent itself — not just suggestions.",
          <AgentRulesEditor config={config} onSaveFields={saveFields} />
        )}
        {section(
          "Calendar (Calendly)",
          "Optional — lets the agent check real availability before proposing a time, instead of asking blind.",
          <AgentCalendlyConnect config={config} onSaveFields={saveFields} clientId={clientId} />
        )}
        {section(
          "Calendar (GoHighLevel)",
          "Same as Calendly, for a client who books on a GHL calendar.",
          <AgentGhlConnect config={config} onSaveFields={saveFields} />
        )}
        {section(
          "Performance",
          "Every lead the agent has texted, by how far they got. Booked includes leads who booked on their own.",
          <AgentPerformance clientId={clientId} />
        )}
        {section(
          "Lessons Learned",
          "When someone texts a lead by hand, the agent drafts a lesson from it. Nothing reaches the agent until you approve it.",
          <AgentLessons clientId={clientId} />
        )}
        {section(
          "Testing",
          "Wipe a test number's conversation state to start the agent fresh — no escalated/booked status or old message history carried over.",
          <AgentResetTest clientId={clientId} />
        )}
        {error && (
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#e05c5c" }}>{error}</div>
        )}
      </AgentAccordionItem>

      <AgentAccordionItem
        title="Database Reactivation Agent"
        subtitle="Texts the client's existing leads (past patients, old inquiries, quiet leads), never fresh ad leads. Replies go to the agent above."
        open={openAgent === "reactivation"}
        onToggle={() => setOpenAgent(openAgent === "reactivation" ? null : "reactivation")}
      >
        <ReactivationAgent clientId={clientId} agentEnabled={Boolean(config?.response_ai_enabled)} />
      </AgentAccordionItem>

      <AgentAccordionItem
        title="Social Media Conversation Agent"
        status={onOff(config?.dm_agent_enabled)}
        subtitle="Answers Instagram and Facebook DMs and books them, getting their number inside Meta's 24-hour window."
        open={openAgent === "social"}
        onToggle={() => setOpenAgent(openAgent === "social" ? null : "social")}
      >
        <SocialMediaAgent clientId={clientId} config={config} onSaveFields={saveFields} />
      </AgentAccordionItem>

      <AgentAccordionItem
        title="Voice Agent"
        status={onOff(config?.voice_agent_enabled)}
        subtitle="Calls new Meta and funnel leads within minutes (Retell, from the client's own number) and books them; texts take over when nobody answers. Growth package only."
        open={openAgent === "voice"}
        onToggle={() => setOpenAgent(openAgent === "voice" ? null : "voice")}
      >
        <VoiceAgent clientId={clientId} config={config} onSaveFields={saveFields} />
      </AgentAccordionItem>

      {agents.map((a) => (
        <AgentAccordionItem
          key={a.id}
          title={a.name}
          subtitle="Not built yet — this is a placeholder slot."
          open={openAgent === a.id}
          onToggle={() => setOpenAgent(openAgent === a.id ? null : a.id)}
          onDelete={() => deleteAgent(a.id)}
        >
          <div style={{ fontSize: 12, color: "#5a7aa0" }}>Coming soon — this agent isn't built yet.</div>
        </AgentAccordionItem>
      ))}

      {showAddAgent ? (
        <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
          <input
            className="dg-input" autoFocus placeholder="Agent name (e.g. Database Reactivation Agent)"
            value={newAgentName} onChange={(e) => setNewAgentName(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") addAgent(); if (e.key === "Escape") setShowAddAgent(false); }}
            style={{ flex: 1, fontSize: 12 }}
          />
          <button className="btn btn-primary" onClick={addAgent} disabled={addingAgent || !newAgentName.trim()} style={{ fontSize: 11 }}>
            {addingAgent ? "ADDING…" : "ADD"}
          </button>
          <button className="btn btn-secondary" onClick={() => { setShowAddAgent(false); setNewAgentName(""); }} style={{ fontSize: 11 }}>CANCEL</button>
        </div>
      ) : (
        <button className="btn btn-ghost" onClick={() => setShowAddAgent(true)} style={{ marginTop: 4 }}>+ Add agent slot</button>
      )}
    </div>
  );
}

// The webhook URL a GoHighLevel client's booking workflow posts to
// (routers/ghl_webhooks.py). Fetched rather than built here: the per-client
// key in it is derived server-side.
// Single free-text resource fields on the client row (clients.*_resource).
const RESOURCE_FIELDS = [
  { field: "ads_manager_resource", label: "Ads Manager", placeholder: "e.g. Business Manager link, ID, or login notes…" },
  { field: "registrar_resource", label: "Registrar Platform", placeholder: "e.g. GoDaddy / Namecheap link or login notes…" },
  { field: "hosting_resource", label: "Hosting Platform", placeholder: "e.g. Vercel / hosting link or login notes…" },
  { field: "funnel_resource", label: "Funnel", placeholder: "e.g. the client's live funnel/landing-page URL…" },
  { field: "scheduling_resource", label: "Scheduling Software", placeholder: "e.g. Jane / Calendly / GHL calendar link or login notes…" },
];

function ClientResources({ clientId }) {
  const [client, setClient] = useState(null);
  const [open, setOpen] = useState({});
  const [resources, setResources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ label: "", value: "" });
  const [saving, setSaving] = useState(false);

  const load = async () => {
    const [cr, rr] = await Promise.all([
      fetch(API(`/clients/${clientId}`)),
      fetch(API(`/clients/${clientId}/resources`)),
    ]);
    if (cr.ok) setClient(await cr.json());
    if (rr.ok) setResources(await rr.json());
    setLoading(false);
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [clientId]);

  const addResource = async () => {
    if (!form.label.trim() || !form.value.trim()) return;
    setSaving(true);
    await fetch(API(`/clients/${clientId}/resources`), {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ label: form.label.trim(), value: form.value.trim(), sort_order: resources.length }),
    });
    setForm({ label: "", value: "" });
    setShowForm(false);
    setSaving(false);
    load();
  };

  const removeResource = async (id) => {
    if (!window.confirm("Delete this resource?")) return;
    await fetch(API(`/clients/${clientId}/resources/${id}`), { method: "DELETE" });
    load();
  };

  if (loading) {
    return <div style={{ padding: 16, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>LOADING…</div>;
  }

  const fields = RESOURCE_FIELDS.map((f) => ({ ...f, value: client?.[f.field] }));
  const setCount = fields.filter((f) => (f.value || "").trim()).length;
  const cardKeys = [...RESOURCE_FIELDS.map((f) => f.field), "other"];
  const allOpen = cardKeys.every((k) => open[k]);
  const toggleAll = () => setOpen(allOpen ? {} : Object.fromEntries(cardKeys.map((k) => [k, true])));
  const toggle = (k) => setOpen((o) => ({ ...o, [k]: !o[k] }));

  return (
    <div style={{ padding: "14px 16px", borderTop: "1px solid rgba(58,123,213,0.1)", display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
        <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#5a7096", letterSpacing: "0.06em" }}>
          {setCount}/{fields.length} PLATFORMS SET · {resources.length} OTHER
        </span>
        <button
          onClick={toggleAll}
          style={{ marginLeft: "auto", background: "none", border: "none", cursor: "pointer", fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a7bd5", letterSpacing: "0.06em" }}
        >
          {allOpen ? "COLLAPSE ALL" : "EXPAND ALL"}
        </button>
      </div>

      {fields.map((f) => (
        <ResourceField
          key={f.field}
          clientId={clientId} field={f.field} label={f.label} placeholder={f.placeholder}
          value={f.value} onSaved={setClient}
          isOpen={!!open[f.field]} onToggle={() => toggle(f.field)}
        >
          {f.field === "funnel_resource" && client?.funnel_resource && (
            <>
              <a href={client.funnel_resource} target="_blank" rel="noreferrer" className="btn btn-secondary" style={{ fontSize: 10 }}>
                VISIT FUNNEL &#8599;
              </a>
              <ExcludeMyIpButton />
            </>
          )}
        </ResourceField>
      ))}

      <ResourceCard
        title="Other Resources"
        summary={resources.length ? `${resources.length} SAVED` : "NONE YET"}
        muted
        isOpen={!!open.other} onToggle={() => toggle("other")}
        right={
          <button
            className="btn btn-secondary" style={{ fontSize: 10 }}
            onClick={() => { setShowForm((s) => !s); setOpen((o) => ({ ...o, other: true })); }}
          >
            {showForm ? "CANCEL" : "+ ADD"}
          </button>
        }
      >
      {showForm && (
        <div style={{ padding: "10px 12px", borderRadius: 8, background: "rgba(255,255,255,0.02)", marginBottom: 8, display: "flex", flexDirection: "column", gap: 8 }}>
          <input
            className="dg-input" placeholder="Label, e.g. Photos / Testimonials / Brand Files" value={form.label}
            onChange={(e) => setForm((f) => ({ ...f, label: e.target.value }))} autoFocus
          />
          <textarea
            className="dg-input" rows={2} placeholder="Link or notes…" value={form.value}
            onChange={(e) => setForm((f) => ({ ...f, value: e.target.value }))}
            style={{ resize: "vertical" }}
          />
          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <button className="btn btn-primary" style={{ fontSize: 11 }} onClick={addResource} disabled={saving || !form.label.trim() || !form.value.trim()}>
              {saving ? "SAVING…" : "SAVE RESOURCE"}
            </button>
          </div>
        </div>
      )}

      {resources.length === 0 && !showForm && (
        <div style={{ padding: "4px 0", fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>
          NO OTHER RESOURCES YET
        </div>
      )}
      {resources.map((r) => <MiscResourceRow key={r.id} resource={r} onDelete={removeResource} />)}
      </ResourceCard>
    </div>
  );
}


export default function ClientsPanel() {
  const [clients, setClients] = useState([]);
  const [csMap, setCsMap] = useState({});
  const [setups, setSetups] = useState({});
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const [saving, setSaving] = useState(false);
  const [newLink, setNewLink] = useState(null);
  const [pageTab, setPageTab] = useState("clients");
  const [openId, setOpenId] = useState(() => Number(new URLSearchParams(window.location.search).get("client")) || null);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("active");

  const loadCs = async () => {
    const r = await fetch("/api/client-success/clients");
    if (r.ok) setCsMap(Object.fromEntries((await r.json()).map((c) => [c.id, c])));
  };
  const loadOneCs = async (id) => {
    const r = await fetch(`/api/client-success/clients/${id}`);
    if (r.ok) { const d = await r.json(); setCsMap((m) => ({ ...m, [id]: { ...(m[id] || {}), ...d } })); }
  };
  const load = async () => {
    const r = await fetch(API("/clients"));
    if (r.ok) {
      const list = await r.json();
      setClients(list);
      Promise.all(list.map((c) => fetch(API(`/clients/${c.id}/setup`)).then((x) => (x.ok ? x.json() : null)).then((d) => [c.id, d]).catch(() => [c.id, null])))
        .then((pairs) => setSetups(Object.fromEntries(pairs)));
    }
    setLoading(false);
    loadCs();
  };

  useEffect(() => { load(); }, []);
  useEffect(() => {
    const url = new URL(window.location.href);
    if (openId) url.searchParams.set("client", openId); else url.searchParams.delete("client");
    window.history.replaceState(window.history.state, "", url);
  }, [openId]);

  const saveClient = async (form) => {
    setSaving(true);
    if (editing) {
      await fetch(API(`/clients/${editing.id}`), {
        method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      setEditing(null);
    } else {
      const r = await fetch(API("/clients"), {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (r.ok) {
        const created = await r.json();
        setNewLink(created.portal_url);
      }
    }
    setShowForm(false);
    setSaving(false);
    load();
  };

  const regenerate = async (id) => { await fetch(API(`/clients/${id}/regenerate-token`), { method: "POST" }); load(); };
  const revoke = async (id) => { await fetch(API(`/clients/${id}/revoke-token`), { method: "POST" }); load(); };
  const remove = async (id) => {
    if (!window.confirm("Delete this client? Onboarding answers and portal access will be removed.")) return;
    await fetch(API(`/clients/${id}`), { method: "DELETE" });
    setOpenId(null);
    load();
  };
  const linkContact = async (id, contactId) => {
    await fetch(API(`/clients/${id}/link-contact`), {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ contact_id: contactId }),
    });
    load();
  };

  const open = clients.find((c) => c.id === openId);
  const editForm = (showForm || editing) && (
    <div style={{ marginBottom: 18 }}>
      <ClientForm initial={editing} saving={saving} onSave={saveClient} onCancel={() => { setShowForm(false); setEditing(null); }} />
    </div>
  );

  if (open) {
    return (
      <div className="px-4 py-4 sm:px-8 sm:py-7" style={{ flex: 1, overflowY: "auto" }}>
        <div style={{ maxWidth: 1180, margin: "0 auto" }}>
          {editForm}
          <ClientPage client={open} cs={csMap[open.id]} onBack={() => setOpenId(null)}
            onEdit={(c) => { setEditing(c); setShowForm(false); }} onRegenerate={regenerate} onRevoke={revoke}
            onDelete={remove} onLinkContact={linkContact} reloadCs={() => loadOneCs(open.id)} />
        </div>
      </div>
    );
  }

  const active = clients.filter((c) => c.status === "active");
  const atRisk = clients.filter((c) => csMap[c.id]?.health?.band === "red").length;
  const live = clients.filter((c) => csMap[c.id]?.state === "running").length;
  const waiting = clients.reduce((n, c) => n + (csMap[c.id]?.open_questions || 0), 0);
  const q = query.trim().toLowerCase();
  const shown = clients
    .filter((c) => (filter === "active" ? c.status === "active" && !c.is_test : true))
    .filter((c) => !q || [c.name, c.contact_name, c.linked_contact?.owner].some((v) => (v || "").toLowerCase().includes(q)));

  return (
    <div className="px-4 py-4 sm:px-8 sm:py-7" style={{ flex: 1, overflowY: "auto" }}>
      <div style={{ maxWidth: 1180, margin: "0 auto" }}>
        <PageHeader
          title="Clients"
          subtitle="Everything for each client in one place: setup, AI agents, messages, reports and info."
          actions={pageTab === "clients" && (
            <button className="btn btn-primary" onClick={() => { setEditing(null); setNewLink(null); setShowForm((s) => !s); }}>
              {showForm ? "Cancel" : "+ New client"}
            </button>
          )}
        />

        <Tabs value={pageTab} onChange={setPageTab} style={{ marginBottom: 20 }}
          tabs={[{ id: "clients", label: "Clients" }, { id: "content", label: "Shared portal content" }]} />

        {pageTab === "content" && (
          <>
            <div style={{ fontSize: 13.5, color: T.textMute, marginBottom: 6, lineHeight: 1.5 }}>
              Shared by every client portal: the how-to videos, the next steps each client checks off during onboarding,
              and the launch checklist template shown on their Launch Progress page.
            </div>
            <VideosSection />
            <ActionItemsSection />
            <LaunchChecklistSection />
          </>
        )}

        {pageTab === "clients" && (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 12, marginBottom: 20 }}>
              <Card pad={16}><Stat label="Active clients" value={active.filter((c) => !c.is_test).length} /></Card>
              <Card pad={16}><Stat label="Campaigns live" value={live} /></Card>
              <Card pad={16}><Stat label="At risk" value={atRisk} tone={atRisk ? "bad" : undefined} /></Card>
              <Card pad={16}><Stat label="Client questions waiting" value={waiting} tone={waiting ? "warn" : undefined} /></Card>
            </div>

            {newLink && (
              <Card pad={14} style={{ marginBottom: 16, display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
                <span style={{ fontSize: 13, color: T.textDim }}>Portal link created:</span>
                <span style={{ fontSize: 13, color: "#8fb8ff", flex: 1, wordBreak: "break-all" }}>{newLink}</span>
                <button className="btn btn-secondary" onClick={() => navigator.clipboard.writeText(newLink)}>Copy</button>
                <button className="btn btn-secondary" onClick={() => setNewLink(null)}>Dismiss</button>
              </Card>
            )}

            {editForm}

            <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap", marginBottom: 14 }}>
              <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search clients…" aria-label="Search clients"
                style={{ ...inputStyle, maxWidth: 320 }} />
              <div style={{ display: "flex", gap: 4, padding: 3, borderRadius: 10, background: "rgba(120,150,210,0.08)" }}>
                {[["active", "Active"], ["all", "All"]].map(([id, label]) => (
                  <button key={id} onClick={() => setFilter(id)} style={{ border: "none", cursor: "pointer", padding: "6px 14px", borderRadius: 8, fontSize: 13, fontWeight: 600,
                    background: filter === id ? "rgba(77,142,240,0.2)" : "transparent", color: filter === id ? T.text : T.textMute }}>{label}</button>
                ))}
              </div>
              <span style={{ fontSize: 12.5, color: T.textMute, marginLeft: "auto" }}>{shown.length} shown</span>
            </div>

            {loading ? <Loading /> : shown.length === 0 ? <Empty>{clients.length ? "No clients match." : "No clients yet."}</Empty> : (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: 14 }}>
                {shown.map((c) => (
                  <ClientCard key={c.id} client={c} cs={csMap[c.id]} setup={setups[c.id]} onOpen={() => setOpenId(c.id)} />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
