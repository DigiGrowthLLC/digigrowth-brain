import React, { useState, useEffect, useRef, useMemo } from "react";
import { useParams } from "react-router-dom";
import {
  LineChart, Line,
  BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer,
} from "recharts";
import { SECTIONS } from "../onboardingSections.js";
import PeriodToggle from "../components/PeriodToggle.jsx";
import AppointmentOutcomeCard from "../AppointmentOutcomeCard.jsx";

// Shared "All Time / Month / Week / Today" bucket vocabulary — matches
// dashboard/backend/routers/client_portal.py's _PERIOD_INTERVAL exactly
// (string keys, not the internal Analytics tab's numeric-days convention),
// used by both the Dashboard tab's period selector and the Inbox tab's
// time filter below.
const PORTAL_PERIOD_OPTIONS = [["today", "Today"], ["week", "Week"], ["month", "Month"], ["all", "All Time"]];

// An appointment counts as "still upcoming" until an hour past its actual
// time — a bit of grace for a call running long — rather than the instant
// its clock time passes. Defined once here (not just near the Appointments
// tab further down) so the dashboard's UpcomingAppointmentsWidget can apply
// the same rule: the backend's status=scheduled filter alone doesn't mean
// "in the future" — a past appointment whose outcome was never marked
// Show/No-Show/Closed stays status='scheduled' forever, so without this
// client-side time check it would show up as "upcoming" indefinitely.
const APPT_PAST_GRACE_MS = 60 * 60 * 1000;

const TAB_LABELS = {
  dashboard: "Dashboard",
  appointments: "Appointments",
  leads: "Leads",
  inbox: "Inbox",
  onboarding: "Onboarding",
  videos: "Get Started Videos",
};

function Field({ q, value, onChange }) {
  return (
    <div style={{ marginBottom: 18 }}>
      <label style={{ display: "block", fontFamily: "'Space Grotesk', sans-serif", fontSize: 13, color: "#b8cce8", marginBottom: 6 }}>
        {q.label}
      </label>
      <textarea
        className="dg-input"
        rows={2}
        value={value || ""}
        onChange={(e) => onChange(q.key, e.target.value)}
        style={{ width: "100%", resize: "vertical", fontFamily: "'Space Grotesk', sans-serif" }}
      />
    </div>
  );
}

function ActionItemRow({ token, item, onUpdated, onGoToTab }) {
  const [saving, setSaving] = useState(false);
  const done = !!item.completed_at;

  const toggle = async () => {
    setSaving(true);
    const r = await fetch(`/portal-api/${token}/action-items/${item.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ completed: !done }),
    });
    if (r.ok) {
      const updated = await r.json();
      onUpdated({ ...item, completed_at: updated.completed_at });
    }
    setSaving(false);
  };

  return (
    <div style={{
      display: "flex", alignItems: "flex-start", gap: 12, padding: "12px 16px", borderRadius: 10,
      background: done ? "rgba(20,200,130,0.05)" : "rgba(255,255,255,0.02)",
      border: done ? "1px solid rgba(20,200,130,0.2)" : "1px solid transparent",
    }}>
      <button onClick={toggle} disabled={saving} style={{
        flexShrink: 0, width: 20, height: 20, marginTop: 2, borderRadius: 5, cursor: "pointer",
        border: done ? "1px solid #14c882" : "1px solid rgba(58,123,213,0.35)",
        background: done ? "#14c882" : "transparent",
        color: "#06110c", fontSize: 12, fontWeight: 700,
        display: "flex", alignItems: "center", justifyContent: "center",
      }}>{done ? "✓" : ""}</button>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 13.5, fontWeight: 600, color: done ? "#8fd9bd" : "#d0e8ff", textDecoration: done ? "line-through" : "none" }}>
          {item.title}
        </div>
        {item.description && (
          <div style={{ fontSize: 12, color: "#8aaad0", marginTop: 3, lineHeight: 1.5 }}>{item.description}</div>
        )}
        {item.link_tab && TAB_LABELS[item.link_tab] && (
          <button onClick={() => onGoToTab(item.link_tab)} style={{ marginTop: 6, background: "none", border: "none", color: "#3a7bd5", fontSize: 11.5, cursor: "pointer", padding: 0, textDecoration: "underline" }}>
            ▶ Go to {TAB_LABELS[item.link_tab]}
          </button>
        )}
        {item.link_url && (
          <a href={item.link_url} target="_blank" rel="noreferrer" style={{ display: "block", marginTop: 6, color: "#3a7bd5", fontSize: 11.5, textDecoration: "underline" }}>
            ▶ Open Link
          </a>
        )}
      </div>
    </div>
  );
}

function NextStepsSection({ token, onGoToTab }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/portal-api/${token}/action-items`)
      .then((r) => r.json())
      .then((data) => { setItems(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [token]);

  if (loading || items.length === 0) return null;

  const doneCount = items.filter((i) => i.completed_at).length;

  return (
    <div style={{ marginBottom: 28 }}>
      <SectionHeading>Next Steps ({doneCount}/{items.length})</SectionHeading>
      <div className="glass-card" style={{ padding: 12, display: "flex", flexDirection: "column", gap: 8 }}>
        {items.map((item) => (
          <ActionItemRow
            key={item.id}
            token={token}
            item={item}
            onUpdated={(updated) => setItems((prev) => prev.map((i) => (i.id === updated.id ? updated : i)))}
            onGoToTab={onGoToTab}
          />
        ))}
      </div>
    </div>
  );
}

function OnboardingFormSection({ token }) {
  const [responses, setResponses] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(null);
  const [openSection, setOpenSection] = useState(SECTIONS[0].key);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    fetch(`/portal-api/${token}/onboarding`)
      .then((r) => r.json())
      .then((data) => { setResponses(data.responses || {}); setLoading(false); })
      .catch(() => setLoading(false));
  }, [token]);

  const answersFor = (sectionKey) => responses[sectionKey]?.answers || {};

  const setAnswer = (sectionKey, qKey, val) => {
    setResponses((prev) => ({
      ...prev,
      [sectionKey]: { ...prev[sectionKey], answers: { ...(prev[sectionKey]?.answers || {}), [qKey]: val } },
    }));
  };

  const save = async (sectionKey, completed) => {
    setSaving(sectionKey);
    const r = await fetch(`/portal-api/${token}/onboarding/${sectionKey}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answers: answersFor(sectionKey), completed }),
    });
    if (r.ok) {
      const updated = await r.json();
      setResponses((prev) => ({ ...prev, [sectionKey]: updated }));
    }
    setSaving(null);
  };

  const completedCount = SECTIONS.filter((s) => responses[s.key]?.completed_at).length;

  return (
    <div>
      <div
        onClick={() => setCollapsed((c) => !c)}
        style={{ display: "flex", alignItems: "center", justifyContent: "space-between", cursor: "pointer", marginBottom: collapsed ? 0 : 12 }}
      >
        <SectionHeading>Onboarding Form ({completedCount}/{SECTIONS.length})</SectionHeading>
        <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80" }}>{collapsed ? "▼" : "▲"}</span>
      </div>

      {!collapsed && (loading ? (
        <div style={{ color: "#3a5a80", fontFamily: "'Share Tech Mono', monospace", fontSize: 11, padding: 20 }}>LOADING...</div>
      ) : (
        SECTIONS.map((s) => {
          const isDone = !!responses[s.key]?.completed_at;
          const isOpen = openSection === s.key;
          return (
            <div key={s.key} className="glass-card" style={{ marginBottom: 14, padding: 0, overflow: "hidden" }}>
              <button
                onClick={() => setOpenSection(isOpen ? null : s.key)}
                style={{ width: "100%", textAlign: "left", background: "none", border: "none", cursor: "pointer", padding: "16px 20px", display: "flex", alignItems: "center", gap: 12 }}
              >
                <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600, fontSize: 14, color: "#d0e8ff", flex: 1 }}>
                  {s.title}
                </span>
                {isDone && (
                  <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#14c882", letterSpacing: "0.08em" }}>
                    ✓ COMPLETE
                  </span>
                )}
                <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80" }}>
                  {isOpen ? "▲" : "▼"}
                </span>
              </button>
              {isOpen && (
                <div style={{ padding: "0 20px 20px", borderTop: "1px solid rgba(58,123,213,0.1)", paddingTop: 16 }}>
                  {s.questions.map((q) => (
                    <Field key={q.key} q={q} value={answersFor(s.key)[q.key]} onChange={(qk, val) => setAnswer(s.key, qk, val)} />
                  ))}
                  <div style={{ display: "flex", gap: 10 }}>
                    <button className="btn btn-secondary" onClick={() => save(s.key, false)} disabled={saving === s.key}>
                      {saving === s.key ? "Saving..." : "Save"}
                    </button>
                    <button className="btn btn-primary" onClick={() => save(s.key, true)} disabled={saving === s.key}>
                      {saving === s.key ? "Saving..." : "Save & Mark Complete"}
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })
      ))}
    </div>
  );
}

function OnboardingTab({ token, onGoToTab }) {
  return (
    <div>
      <NextStepsSection token={token} onGoToTab={onGoToTab} />
      <OnboardingFormSection token={token} />
    </div>
  );
}

function VideosTab({ token }) {
  const [videos, setVideos] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/portal-api/${token}/videos`)
      .then((r) => r.json())
      .then((data) => { setVideos(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [token]);

  if (loading) return <div style={{ color: "#3a5a80", fontFamily: "'Share Tech Mono', monospace", fontSize: 11, padding: 40 }}>LOADING...</div>;
  if (videos.length === 0) return (
    <div style={{ textAlign: "center", padding: 60, fontFamily: "'Share Tech Mono', monospace", fontSize: 11, color: "#2a4a6a", letterSpacing: "0.12em" }}>
      NO VIDEOS YET — CHECK BACK SOON
    </div>
  );

  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: 18 }}>
      {videos.map((v) => (
        <div key={v.id} className="glass-card-sm">
          <div style={{ position: "relative", paddingTop: "56.25%", borderRadius: 8, overflow: "hidden", marginBottom: 12 }}>
            <iframe
              src={v.embed_url}
              title={v.title}
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowFullScreen
              style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%", border: "none" }}
            />
          </div>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600, fontSize: 14, color: "#d0e8ff", marginBottom: 4 }}>{v.title}</div>
          {v.description && <div style={{ fontSize: 12.5, color: "#8aaad0", lineHeight: 1.5 }}>{v.description}</div>}
        </div>
      ))}
    </div>
  );
}

function SectionHeading({ children }) {
  return (
    <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80", letterSpacing: "0.16em", textTransform: "uppercase", marginBottom: 12 }}>
      {children}
    </div>
  );
}

// ── Dashboard (Vision UI style, mirrors the internal DashboardPanel) ────────

const DASH_ICONS = {
  leads: (
    <svg viewBox="0 0 20 20" fill="none" width={20} height={20}>
      <circle cx="7" cy="7" r="3" stroke="#6ab0ff" strokeWidth="1.6" />
      <path d="M2 17c0-3 2.24-5 5-5m5 0c2.76 0 5 2 5 5" stroke="#6ab0ff" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  ),
  appointments: (
    <svg viewBox="0 0 20 20" fill="none" width={20} height={20}>
      <rect x="3" y="4" width="14" height="13" rx="2" stroke="#6ab0ff" strokeWidth="1.6" />
      <path d="M7 2v4M13 2v4M3 9h14" stroke="#6ab0ff" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  ),
  upcoming: (
    <svg viewBox="0 0 20 20" fill="none" width={20} height={20}>
      <circle cx="10" cy="10" r="7.5" stroke="#6ab0ff" strokeWidth="1.6" />
      <path d="M10 6v4l3 2" stroke="#6ab0ff" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  rate: (
    <svg viewBox="0 0 20 20" fill="none" width={20} height={20}>
      <path d="M4 11l3.5 3.5L16 6" stroke="#6ab0ff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
};

function DashTopStat({ label, value, delta, iconKey }) {
  return (
    <div className="stat-card">
      <div>
        <div className="stat-card-label">{label}</div>
        <div className="stat-card-value">{value ?? "—"}</div>
        {delta != null && (
          <div className="stat-card-delta" style={{ color: "#14c882" }}>{delta}</div>
        )}
      </div>
      <div className="stat-card-icon">{DASH_ICONS[iconKey]}</div>
    </div>
  );
}

function DashChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: "rgba(10,18,48,0.95)", border: "1px solid rgba(58,123,213,0.2)",
      borderRadius: 10, padding: "8px 14px", fontSize: 12,
      fontFamily: "'Space Grotesk', sans-serif",
    }}>
      <div style={{ color: "#8aaad0", marginBottom: 4 }}>{label}</div>
      {payload.map((p) => (
        <div key={p.dataKey} style={{ color: p.color, fontWeight: 600 }}>{p.name}: {p.value}</div>
      ))}
    </div>
  );
}

function GradientRateCard({ label, pct, sublabel, breakdown }) {
  return (
    <div className="glass-card" style={{ padding: "24px 22px" }}>
      <div className="sec-label">{label}</div>
      <div style={{ textAlign: "center", padding: "10px 0" }}>
        <div style={{
          fontSize: 52, fontWeight: 700, color: "#f0f4ff",
          letterSpacing: "-0.04em", lineHeight: 1,
          background: "linear-gradient(135deg, #3a7bd5, #6ab0ff)",
          WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
        }}>
          {pct != null ? `${pct}%` : "—"}
        </div>
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80", letterSpacing: "0.12em", marginTop: 8 }}>
          {sublabel}
        </div>
      </div>
      {breakdown && (
        <>
          <div className="dg-divider" style={{ margin: "12px 0" }} />
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            {breakdown.map(({ label: l, value, color }) => (
              <div key={l}>
                <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a4a7a", letterSpacing: "0.12em" }}>{l.toUpperCase()}</div>
                <div style={{ fontSize: 18, fontWeight: 700, color, marginTop: 2 }}>{value}</div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function UpcomingAppointmentsWidget({ token }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/portal-api/${token}/appointments?status=scheduled`)
      .then((r) => r.json())
      .then((data) => {
        // status=scheduled alone doesn't mean "in the future" — see
        // APPT_PAST_GRACE_MS's comment above. Without this filter, an
        // appointment whose outcome was never marked keeps showing here as
        // "upcoming" long after it's actually happened.
        const stillUpcoming = (data || []).filter(
          (r) => new Date(r.appointment_at).getTime() + APPT_PAST_GRACE_MS > Date.now()
        );
        setRows(stillUpcoming.slice(0, 5));
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [token]);

  return (
    <div className="glass-card" style={{ padding: "20px 22px", display: "flex", flexDirection: "column", minHeight: 280 }}>
      <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 14, fontWeight: 600, color: "#d0dcf0", marginBottom: 16 }}>
        Upcoming Appointments
      </div>
      {loading && <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>LOADING…</div>}
      {!loading && rows.length === 0 && (
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52" }}>NOTHING UPCOMING</div>
      )}
      <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 8 }}>
        {rows.map((r) => (
          <div key={r.id} style={{
            padding: "8px 12px", borderRadius: 10,
            background: "rgba(58,123,213,0.06)", border: "1px solid rgba(58,123,213,0.12)",
            borderLeft: "3px solid #3a7bd5",
          }}>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", letterSpacing: "0.08em", marginBottom: 2 }}>
              {fmtLocal(r.appointment_at, r.prospect_timezone)}
            </div>
            <div style={{ fontSize: 13, color: "#8aaad0", lineHeight: 1.4 }}>{r.prospect_name || r.owner || "—"}</div>
            {r.business && <div style={{ fontSize: 10, color: "#3a5a7a", marginTop: 2 }}>{r.business}</div>}
          </div>
        ))}
      </div>
    </div>
  );
}

function RecentLeadsWidget({ token }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/portal-api/${token}/leads`)
      .then((r) => r.json())
      .then((data) => { setRows((data || []).slice(0, 5)); setLoading(false); })
      .catch(() => setLoading(false));
  }, [token]);

  return (
    <div className="glass-card" style={{ padding: "20px 22px", display: "flex", flexDirection: "column", minHeight: 280 }}>
      <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 14, fontWeight: 600, color: "#d0dcf0", marginBottom: 16 }}>
        Recent Leads
      </div>
      {loading && <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a7a" }}>LOADING…</div>}
      {!loading && rows.length === 0 && (
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52" }}>NO LEADS YET</div>
      )}
      <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 8 }}>
        {rows.map((l) => (
          <div key={l.id} style={{
            display: "flex", justifyContent: "space-between", alignItems: "center",
            padding: "8px 12px", borderRadius: 10, background: "rgba(255,255,255,0.02)",
          }}>
            <div>
              <div style={{ fontSize: 13, color: "#c4d0e8", fontWeight: 600 }}>{l.business || l.owner || "—"}</div>
              <div style={{ fontSize: 10, color: "#5a7096", marginTop: 2 }}>{l.phone}</div>
            </div>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#14c882", flexShrink: 0 }} />
          </div>
        ))}
      </div>
    </div>
  );
}

function DashboardTab({ token }) {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState("all");

  useEffect(() => {
    setLoading(true);
    fetch(`/portal-api/${token}/stats?period=${period}`)
      .then((r) => r.json())
      .then((data) => { setStats(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [token, period]);

  if (loading && !stats) return <div style={{ color: "#3a5a80", fontFamily: "'Share Tech Mono', monospace", fontSize: 11, padding: 40 }}>LOADING...</div>;
  if (!stats) return null;

  const appt = stats.appointments;

  const funnelData = [
    { stage: "Booked", value: appt.total },
    { stage: "Shown", value: appt.shows },
    { stage: "Closed", value: appt.closed },
  ];
  const hasFunnelData = funnelData.some((d) => d.value > 0);

  const channelData = [
    { name: "SMS Sent", value: stats.sms.sent, fill: "#3a7bd5" },
    { name: "SMS Replies", value: stats.sms.replies, fill: "#14c882" },
    { name: "Email Sent", value: stats.email.sent, fill: "#f0a028" },
    { name: "Email Replies", value: stats.email.replies, fill: "#a080f0" },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

      {/* Period selector — same All Time/Month/Week/Today bucket vocabulary
          as the internal OS's Analytics tab, scoping every stat below. */}
      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <PeriodToggle days={period} setDays={setPeriod} options={PORTAL_PERIOD_OPTIONS} />
      </div>

      {/* Row 1: top stat cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16 }}>
        <DashTopStat label="Total Leads" value={stats.leads.total} iconKey="leads" />
        <DashTopStat label="Total Appointments" value={appt.total} iconKey="appointments" />
        <DashTopStat label="Upcoming Appointments" value={appt.upcoming} iconKey="upcoming" delta={appt.upcoming > 0 ? "on the calendar" : null} />
        <DashTopStat label="Show Rate" value={appt.shows + appt.no_shows > 0 ? `${appt.show_rate}%` : "—"} iconKey="rate" />
      </div>

      {/* Row 2: upcoming appointments + recent leads */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <UpcomingAppointmentsWidget token={token} />
        <RecentLeadsWidget token={token} />
      </div>

      {/* Row 3: charts */}
      <div style={{ display: "grid", gridTemplateColumns: "1.8fr 1fr", gap: 16 }}>
        <div className="glass-card" style={{ padding: "22px 24px" }}>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 16, fontWeight: 600, color: "#d0dcf0", marginBottom: 20 }}>
            Appointment Funnel
          </div>
          {hasFunnelData ? (
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={funnelData} margin={{ top: 5, right: 10, bottom: 0, left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(58,123,213,0.06)" />
                <XAxis dataKey="stage" tick={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, fill: "#2a4a7a" }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, fill: "#2a4a7a" }} axisLine={false} tickLine={false} />
                <Tooltip content={<DashChartTooltip />} />
                <Line type="monotone" dataKey="value" name="Count" stroke="#3a7bd5" strokeWidth={2}
                  dot={{ fill: "#3a7bd5", r: 4, strokeWidth: 0 }} activeDot={{ fill: "#6ab0ff", r: 5, strokeWidth: 0 }} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ height: 180, display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52", letterSpacing: "0.15em" }}>
              NO DATA YET
            </div>
          )}
        </div>

        <div className="glass-card" style={{ padding: "22px 24px" }}>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 16, fontWeight: 600, color: "#d0dcf0", marginBottom: 4 }}>
            Channel Activity
          </div>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a7bd5", letterSpacing: "0.1em", marginBottom: 18 }}>
            SMS &amp; EMAIL
          </div>
          <ResponsiveContainer width="100%" height={140}>
            <BarChart data={channelData} margin={{ top: 0, right: 0, bottom: 0, left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(58,123,213,0.06)" />
              <XAxis dataKey="name" tick={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 8, fill: "#2a4a7a" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, fill: "#2a4a7a" }} axisLine={false} tickLine={false} />
              <Tooltip content={<DashChartTooltip />} />
              <Bar dataKey="value" name="Count" radius={[4, 4, 0, 0]}>
                {channelData.map((entry, i) => <rect key={i} fill={entry.fill} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Row 4: rate cards */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <GradientRateCard
          label="Show Rate"
          pct={appt.shows + appt.no_shows > 0 ? appt.show_rate : null}
          sublabel="SHOWS / BOOKED APPOINTMENTS"
          breakdown={[
            { label: "Shows", value: appt.shows, color: "#14c882" },
            { label: "No-Shows", value: appt.no_shows, color: "#dc3c3c" },
          ]}
        />
        <GradientRateCard
          label="Close Rate"
          pct={appt.closed + appt.not_closed > 0 ? appt.close_rate : null}
          sublabel="CLOSED / DECIDED APPOINTMENTS"
          breakdown={[
            { label: "Closed", value: appt.closed, color: "#14c882" },
            { label: "Lost", value: appt.not_closed, color: "#dc3c3c" },
          ]}
        />
      </div>

      {/* Row 5: ads placeholder */}
      <div>
        <SectionHeading>Facebook Ads</SectionHeading>
        <div className="glass-card" style={{ textAlign: "center", padding: 30, color: "#5a7aa0", fontSize: 13 }}>
          Facebook Ads reporting — coming soon
        </div>
      </div>
    </div>
  );
}

function fmtLocal(iso, tz) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("en-US", {
      timeZone: tz, month: "short", day: "numeric",
      hour: "numeric", minute: "2-digit",
    });
  } catch {
    return new Date(iso).toLocaleString("en-US");
  }
}

// Compact clickable summary that opens AppointmentOutcomeCard — same
// "click the appointment -> graphic card" pattern as the internal OS's
// AppointmentsPanel.jsx, sharing the same modal component.
function OutcomeSummary({ appointment, onClick }) {
  const showLabel  = appointment.outcome_show === "show" ? "Show" : appointment.outcome_show === "no_show" ? "No Show" : null;
  const closeLabel = appointment.outcome_close === "closed" ? "Closed" : appointment.outcome_close === "not_closed" ? "Not Closed" : null;
  const showColor  = appointment.outcome_show === "show" ? "#14c882" : "#dc3c3c";
  const closeColor = appointment.outcome_close === "closed" ? "#14c882" : "#dc3c3c";
  const hasOutcome = showLabel || closeLabel;
  return (
    <button
      onClick={onClick}
      style={{ background: "none", border: "none", cursor: "pointer", padding: "4px 8px", borderRadius: 6, textAlign: "left", fontFamily: "'Share Tech Mono', monospace", fontSize: 10.5 }}
    >
      {hasOutcome ? (
        <span>
          {showLabel && <span style={{ color: showColor }}>{showLabel}</span>}
          {showLabel && closeLabel && <span style={{ color: "#3a5a80" }}> · </span>}
          {closeLabel && <span style={{ color: closeColor }}>{closeLabel}</span>}
          {appointment.outcome_notes && <span style={{ color: "#5a6f8f" }}> · 📝</span>}
        </span>
      ) : (
        <span style={{ color: "#5a6f8f" }}>Set outcome ›</span>
      )}
    </button>
  );
}

function ApptStatChip({ label, value, color }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2, padding: "8px 14px", borderRadius: 8, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(58,123,213,0.15)", minWidth: 84 }}>
      <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#5a6f8f", letterSpacing: "0.1em" }}>{label}</div>
      <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 18, fontWeight: 700, color: color || "#f0f4ff" }}>{value}</div>
    </div>
  );
}

const APPT_FILTER_LABELS = { upcoming: "Upcoming", past: "Past", canceled: "Canceled", all: "All" };

function AppointmentsTab({ token }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("upcoming");
  const [outcomeTarget, setOutcomeTarget] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const backendStatus = filter === "upcoming" || filter === "past" ? "scheduled" : filter;
      const r = await fetch(`/portal-api/${token}/appointments?status=${backendStatus}`);
      setRows(await r.json());
    } catch {
      setRows([]);
    }
    setLoading(false);
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [token, filter]);

  const displayRows = filter === "upcoming"
    ? rows.filter((r) => new Date(r.appointment_at).getTime() + APPT_PAST_GRACE_MS > Date.now())
    : filter === "past"
    ? rows.filter((r) => new Date(r.appointment_at).getTime() + APPT_PAST_GRACE_MS <= Date.now())
    : rows;

  // Same DB-derived-only stat strip as the internal OS's AppointmentsPanel —
  // computed from whatever's on screen, not wired into portal_stats()'s
  // sheet-adjacent numbers.
  const stats = useMemo(() => {
    const shows     = displayRows.filter((r) => r.outcome_show === "show").length;
    const noShows   = displayRows.filter((r) => r.outcome_show === "no_show").length;
    const closed    = displayRows.filter((r) => r.outcome_close === "closed").length;
    const notClosed = displayRows.filter((r) => r.outcome_close === "not_closed").length;
    return { shows, noShows, closed, notClosed };
  }, [displayRows]);

  const handleOutcomeSaved = (updated) => {
    setRows((rs) => rs.map((r) => (r.id === updated.id ? { ...r, ...updated } : r)));
    setOutcomeTarget(null);
  };

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <SectionHeading>{APPT_FILTER_LABELS[filter]} Appointments</SectionHeading>
        <select className="dg-input" value={filter} onChange={(e) => setFilter(e.target.value)} style={{ fontSize: 12, padding: "6px 10px", width: "auto" }}>
          <option value="upcoming">Upcoming</option>
          <option value="past">Past</option>
          <option value="canceled">Canceled</option>
          <option value="all">All</option>
        </select>
      </div>

      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 16 }}>
        <ApptStatChip label="SHOWS" value={stats.shows} color="#14c882" />
        <ApptStatChip label="NO SHOWS" value={stats.noShows} color="#dc3c3c" />
        <ApptStatChip label="CLOSED" value={stats.closed} color="#14c882" />
        <ApptStatChip label="NOT CLOSED" value={stats.notClosed} color="#dc3c3c" />
      </div>

      <div className="glass-card" style={{ padding: 0, overflow: "hidden", overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid rgba(58,123,213,0.15)" }}>
              {["Prospect", "Business", "Appointment", "Outcome"].map((h) => (
                <th key={h} style={{ textAlign: "left", padding: "10px 14px", fontSize: 10, color: "#5a6f8f", fontFamily: "'Share Tech Mono', monospace", letterSpacing: "0.05em" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {!loading && displayRows.length === 0 && (
              <tr><td colSpan={4} style={{ padding: 20, textAlign: "center", color: "#3a5a80", fontSize: 12 }}>No appointments in this view.</td></tr>
            )}
            {displayRows.map((row) => (
              <tr key={row.id} style={{ borderBottom: "1px solid rgba(58,123,213,0.08)" }}>
                <td style={{ padding: "10px 14px", fontSize: 12, color: "#f0f4ff" }}>{row.prospect_name || row.owner || "—"}</td>
                <td style={{ padding: "10px 14px", fontSize: 12, color: "#8a9cc0" }}>{row.business || "—"}</td>
                <td style={{ padding: "10px 14px", fontSize: 12, color: "#8a9cc0" }}>{fmtLocal(row.appointment_at, row.prospect_timezone)}</td>
                <td style={{ padding: "10px 14px" }}>
                  {row.status !== "canceled" && <OutcomeSummary appointment={row} onClick={() => setOutcomeTarget(row)} />}
                  {row.status === "canceled" && <span style={{ fontSize: 11, color: "#3a5a80" }}>canceled</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {outcomeTarget && (
        <AppointmentOutcomeCard
          appointment={outcomeTarget}
          patchUrl={`/portal-api/${token}/appointments/${outcomeTarget.id}`}
          onClose={() => setOutcomeTarget(null)}
          onSaved={handleOutcomeSaved}
        />
      )}
    </div>
  );
}

const LEAD_CSV_ALIASES = {
  phone:    ["phone", "phone number", "mobile", "cell", "telephone"],
  business: ["business", "company", "business name", "company name"],
  owner:    ["owner", "name", "contact", "contact name", "full name", "first name"],
  email:    ["email", "email address"],
  website:  ["website", "url", "site", "web"],
  city:     ["city", "town"],
  state:    ["state", "province", "region"],
  notes:    ["notes", "note", "comments", "comment"],
};

function parseCsvLine(line) {
  const cols = []; let cur = ""; let inQ = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') { if (inQ && line[i + 1] === '"') { cur += '"'; i++; } else inQ = !inQ; }
    else if (ch === ',' && !inQ) { cols.push(cur.trim()); cur = ""; }
    else cur += ch;
  }
  cols.push(cur.trim()); return cols;
}

function parseLeadCSV(text) {
  const lines = text.replace(/\r/g, "").split("\n").filter((l) => l.trim());
  if (lines.length < 2) return [];
  const headers = parseCsvLine(lines[0]).map((h) => h.toLowerCase().replace(/['"]/g, "").trim());
  const colMap = {};
  for (const [field, aliases] of Object.entries(LEAD_CSV_ALIASES)) {
    const idx = headers.findIndex((h) => aliases.includes(h));
    if (idx >= 0) colMap[field] = idx;
  }
  return lines.slice(1).map((line) => {
    const cols = parseCsvLine(line);
    const row = {};
    for (const [field, idx] of Object.entries(colMap)) row[field] = (cols[idx] || "").replace(/^"|"$/g, "").trim();
    return row;
  });
}

// Small colored pill matching the internal CRM's tag chip look — same
// palette convention (tag.color as the border/text, a translucent fill of
// the same hue) as CRMPanel.jsx's TagChip.
function TagChip({ tag, onRemove }) {
  const color = tag.color || "#3a7bd5";
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      padding: "2px 8px", borderRadius: 999, fontSize: 10,
      fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600,
      color, background: `${color}22`, border: `1px solid ${color}55`,
    }}>
      {tag.name}
      {onRemove && (
        <span onClick={onRemove} style={{ cursor: "pointer", opacity: 0.7, fontWeight: 700 }}>×</span>
      )}
    </span>
  );
}

// Contact card / drawer — mirrors the internal CRM's ContactDrawer
// (CRMPanel.jsx), scaled down to what's meaningful for a client editing
// their own lead: contact fields + notes + tags. Deliberately leaves out
// the internal-only sections (status/grade, SMS+email campaign assignment,
// cold-call opener, Call Now/dialer-queue actions) — those are
// DigiGrowth's own sales-pipeline machinery, not something a client's own
// lead-editing view should expose, same reasoning as leaving contact
// status out of the Inbox filter bar.
const LEAD_DRAWER_FIELDS = [
  { label: "Business", k: "business" },
  { label: "Owner", k: "owner" },
  { label: "Phone", k: "phone" },
  { label: "Email", k: "email" },
  { label: "Website", k: "website" },
  { label: "City", k: "city" },
  { label: "State", k: "state" },
];

function LeadDrawer({ token, lead, allTags, onClose, onUpdated, onMessage }) {
  const [display, setDisplay] = useState(lead);
  const [form, setForm] = useState(() => {
    const initial = {};
    for (const f of LEAD_DRAWER_FIELDS) initial[f.k] = lead[f.k] || "";
    initial.notes = lead.notes || "";
    return initial;
  });
  const [saving, setSaving] = useState(false);
  const [saveErr, setSaveErr] = useState("");
  const [tagPick, setTagPick] = useState("");
  const [callMsg, setCallMsg] = useState("");
  // idle | connecting | ringing | connected | ended
  const [callPhase, setCallPhase] = useState("idle");
  const deviceRef = useRef(null);
  const activeCallRef = useRef(null);
  const pollRef = useRef(null);
  const [showBook, setShowBook] = useState(false);
  const [timezones, setTimezones] = useState([]);
  const [bookDate, setBookDate] = useState("");
  const [bookTime, setBookTime] = useState("");
  const [bookTz, setBookTz] = useState("America/New_York");
  const [booking, setBooking] = useState(false);
  const [bookMsg, setBookMsg] = useState("");

  useEffect(() => {
    if (!showBook || timezones.length) return;
    fetch(`/portal-api/${token}/appointments/timezones`).then((r) => r.json()).then(setTimezones).catch(() => {});
  }, [showBook, token, timezones.length]);

  const bookAppointment = async () => {
    if (!bookDate || !bookTime) { setBookMsg("Enter the appointment date and time."); return; }
    setBooking(true);
    setBookMsg("");
    try {
      const r = await fetch(`/portal-api/${token}/leads/${lead.id}/book`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ date: bookDate, time: bookTime, timezone: bookTz }),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) { setBookMsg(d.detail || "Couldn't book appointment."); setBooking(false); return; }
      setBookMsg("✅ Appointment booked — reminders scheduled.");
      setBookDate(""); setBookTime("");
    } catch (e) {
      setBookMsg("Couldn't book appointment: " + e.message);
    }
    setBooking(false);
  };

  const setField = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const stopPolling = () => { clearInterval(pollRef.current); pollRef.current = null; };

  const teardownCall = async () => {
    stopPolling();
    try { activeCallRef.current?.disconnect(); } catch {}
    try { deviceRef.current?.destroy(); } catch {}
    deviceRef.current = null;
    activeCallRef.current = null;
    await fetch(`/portal-api/${token}/dialer/end-session`, { method: "POST" }).catch(() => {});
  };

  useEffect(() => () => { teardownCall(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const pollSession = () => {
    stopPolling();
    pollRef.current = setInterval(async () => {
      const r = await fetch(`/portal-api/${token}/dialer/session`).catch(() => null);
      if (!r || !r.ok) return;
      const d = await r.json();
      if (d.status === "connected") setCallPhase("connected");
      else if (d.status === "classify" || (!d.active && callPhase !== "connecting")) {
        setCallPhase("ended");
        setCallMsg("Call ended.");
        stopPolling();
      } else if (d.status === "waiting") setCallPhase("ringing");
    }, 1500);
  };

  const handleCall = async () => {
    if (!window.Twilio?.Device) {
      setCallMsg("Calling isn't ready yet — try refreshing the page.");
      return;
    }
    setCallPhase("connecting");
    setCallMsg("");
    try {
      const cr = await fetch(`/portal-api/${token}/leads/${lead.id}/call`, { method: "POST" });
      const cd = await cr.json().catch(() => ({}));
      if (!cr.ok) { setCallPhase("idle"); setCallMsg(cd.detail || "Couldn't start the call."); return; }
      // Real clients get a 200 OK with ok:false (the "not connected yet"
      // stub) rather than an HTTP error — stop here instead of trying to
      // connect a Twilio Device that the backend will just 403 anyway.
      if (cd.ok === false) { setCallPhase("idle"); setCallMsg(cd.detail || "Calling isn't available yet."); return; }

      const tr = await fetch(`/portal-api/${token}/dialer/token`);
      const td = await tr.json().catch(() => ({}));
      if (!tr.ok) { setCallPhase("idle"); setCallMsg(td.detail || "Couldn't connect to the calling line."); return; }

      const device = new window.Twilio.Device(td.token, { logLevel: "warn" });
      deviceRef.current = device;
      device.on("error", (e) => { setCallPhase("idle"); setCallMsg("Call error: " + (e.message || "unknown")); stopPolling(); });

      await device.register();
      const call = await device.connect({ params: { session_id: cd.session_id } });
      activeCallRef.current = call;

      call.on("accept", async () => {
        setCallMsg("Connected — dialing " + (display.owner || display.business || "the lead") + "…");
        await fetch(`/portal-api/${token}/dialer/dial-batch`, { method: "POST" }).catch(() => {});
        pollSession();
      });
      call.on("disconnect", () => { setCallPhase("ended"); stopPolling(); });
      call.on("cancel", () => { setCallPhase("idle"); setCallMsg("Call was canceled."); stopPolling(); });
    } catch (e) {
      setCallPhase("idle");
      setCallMsg("Could not place call: " + e.message);
    }
  };

  const handleHangup = async () => {
    await fetch(`/portal-api/${token}/dialer/end-call`, { method: "POST" }).catch(() => {});
    await teardownCall();
    setCallPhase("ended");
  };

  const handleSave = async () => {
    setSaving(true);
    setSaveErr("");
    const patch = {};
    for (const f of LEAD_DRAWER_FIELDS) {
      if (form[f.k] !== (display[f.k] || "")) patch[f.k] = form[f.k] || null;
    }
    if (form.notes !== (display.notes || "")) patch.notes = form.notes || null;

    if (Object.keys(patch).length > 0) {
      const r = await fetch(`/portal-api/${token}/leads/${lead.id}`, {
        method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      });
      if (r.ok) {
        const updated = await r.json();
        setDisplay(updated);
        onUpdated(updated);
      } else {
        const d = await r.json().catch(() => ({}));
        setSaveErr(d.detail || "Save failed.");
      }
    }
    setSaving(false);
  };

  const addTag = async (tagName) => {
    const name = tagName.trim();
    if (!name) return;
    const r = await fetch(`/portal-api/${token}/leads/${lead.id}/tags`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tag: name }),
    });
    if (r.ok) {
      const updated = await r.json();
      setDisplay(updated);
      onUpdated(updated);
    }
    setTagPick("");
  };

  const removeTag = async (tagName) => {
    const r = await fetch(`/portal-api/${token}/leads/${lead.id}/tags/${encodeURIComponent(tagName)}`, { method: "DELETE" });
    if (r.ok) {
      const updated = await r.json();
      setDisplay(updated);
      onUpdated(updated);
    }
  };

  const tagByName = (name) => allTags.find((t) => t.name === name) || { name, color: "#3a7bd5" };
  const labelStyle = { fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a4a7a", letterSpacing: "0.15em", marginBottom: 4 };

  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 50, display: "flex", justifyContent: "flex-end" }}>
      <div style={{ position: "absolute", inset: 0, background: "rgba(8,12,20,0.7)" }} onClick={onClose} />
      <aside style={{
        position: "relative", width: 440, background: "#0d1626", borderLeft: "0.5px solid #1a2540",
        height: "100%", overflowY: "auto", display: "flex", flexDirection: "column",
      }}>
        <div style={{ padding: "18px 20px", borderBottom: "0.5px solid #1a2540", display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 10 }}>
          <div>
            <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 16, fontWeight: 700, color: "#f0f4ff" }}>
              {display.business || "Unknown"}
            </div>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80", letterSpacing: "0.12em", marginTop: 3 }}>
              {display.owner || "—"} · {display.phone || "—"}
            </div>
          </div>
          <button onClick={onClose} style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 12, color: "#3a5a80", background: "none", border: "none", cursor: "pointer", padding: "2px 6px" }}>✕</button>
        </div>

        <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 18, flex: 1 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 16px" }}>
            {LEAD_DRAWER_FIELDS.map((f) => (
              <div key={f.k} style={{ marginBottom: 12 }}>
                <div style={labelStyle}>{f.label.toUpperCase()}</div>
                <input value={form[f.k]} onChange={(e) => setField(f.k, e.target.value)} className="dg-input" style={{ width: "100%", fontSize: 12, boxSizing: "border-box" }} />
              </div>
            ))}
          </div>

          <div>
            <div style={labelStyle}>NOTES</div>
            <textarea value={form.notes} onChange={(e) => setField("notes", e.target.value)} className="dg-input" rows={3}
              style={{ width: "100%", resize: "vertical", fontFamily: "inherit", boxSizing: "border-box" }} placeholder="Notes about this lead…" />
          </div>

          {saveErr && <div style={{ fontSize: 11, color: "#f06060", fontFamily: "'Share Tech Mono', monospace" }}>{saveErr}</div>}
          <button onClick={handleSave} disabled={saving} className="btn btn-primary">{saving ? "Saving…" : "Save Changes"}</button>

          <div style={{ display: "flex", gap: 8 }}>
            {/* Jumps to the Inbox tab with this lead's thread open — mirrors
                the internal CRM's ContactDrawer "✉ Message" button
                (messageContact() -> onNavigate("inbox", {contactId})). */}
            <button
              onClick={onMessage}
              style={{
                flex: 1, padding: "9px 12px", borderRadius: 8,
                background: "rgba(160,110,240,0.12)", border: "1px solid rgba(160,110,240,0.35)",
                color: "#a06ef0", fontFamily: "'Space Grotesk', sans-serif",
                fontSize: 12, fontWeight: 600, cursor: "pointer",
              }}
            >
              ✉ Message
            </button>
            {/* Places a real call through DigiGrowth's existing shared
                Twilio line — same dialer engine as the internal OS,
                connecting this browser as the agent leg (see handleCall). */}
            {callPhase === "connected" ? (
              <button
                onClick={handleHangup}
                style={{
                  flex: 1, padding: "9px 12px", borderRadius: 8,
                  background: "rgba(220,60,60,0.14)", border: "1px solid rgba(220,60,60,0.4)",
                  color: "#e05c5c", fontFamily: "'Space Grotesk', sans-serif",
                  fontSize: 12, fontWeight: 600, cursor: "pointer",
                }}
              >
                ☎ Hang Up
              </button>
            ) : (
              <button
                onClick={handleCall}
                disabled={callPhase === "connecting" || callPhase === "ringing"}
                style={{
                  flex: 1, padding: "9px 12px", borderRadius: 8,
                  background: "rgba(90,200,140,0.12)", border: "1px solid rgba(90,200,140,0.35)",
                  color: "#5ac88c", fontFamily: "'Space Grotesk', sans-serif",
                  fontSize: 12, fontWeight: 600,
                  cursor: (callPhase === "connecting" || callPhase === "ringing") ? "default" : "pointer",
                  opacity: (callPhase === "connecting" || callPhase === "ringing") ? 0.7 : 1,
                }}
              >
                📞 {callPhase === "connecting" ? "Connecting…" : callPhase === "ringing" ? "Ringing…" : "Call"}
              </button>
            )}
          </div>
          {callMsg && (
            <div style={{ fontSize: 11, color: "#8aaad0", fontFamily: "'Share Tech Mono', monospace", lineHeight: 1.5 }}>
              {callMsg}
            </div>
          )}

          <div>
            <button
              onClick={() => setShowBook((s) => !s)}
              style={{
                width: "100%", padding: "9px 12px", borderRadius: 8,
                background: "rgba(240,160,40,0.12)", border: "1px solid rgba(240,160,40,0.35)",
                color: "#f0a028", fontFamily: "'Space Grotesk', sans-serif",
                fontSize: 12, fontWeight: 600, cursor: "pointer",
              }}
            >
              📅 {showBook ? "Cancel Booking" : "Book Appointment"}
            </button>
            {showBook && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 10, padding: 12, borderRadius: 8, background: "rgba(255,255,255,0.02)", border: "1px solid #1a2540" }}>
                <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                  <label style={{ fontSize: 10, color: "#5a6f8f" }}>Date</label>
                  <input type="date" className="dg-input" value={bookDate} onChange={(e) => setBookDate(e.target.value)} style={{ fontSize: 12, padding: "6px 8px" }} />
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                  <label style={{ fontSize: 10, color: "#5a6f8f" }}>Time</label>
                  <input type="time" className="dg-input" value={bookTime} onChange={(e) => setBookTime(e.target.value)} style={{ fontSize: 12, padding: "6px 8px" }} />
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 3, flex: 1, minWidth: 140 }}>
                  <label style={{ fontSize: 10, color: "#5a6f8f" }}>Timezone</label>
                  <select className="dg-input" value={bookTz} onChange={(e) => setBookTz(e.target.value)} style={{ fontSize: 12, padding: "6px 8px" }}>
                    {timezones.map((t) => <option key={t.iana} value={t.iana}>{t.label}</option>)}
                  </select>
                </div>
                <button onClick={bookAppointment} disabled={booking} className="btn btn-primary" style={{ fontSize: 12, padding: "7px 14px" }}>
                  {booking ? "Booking…" : "Confirm"}
                </button>
                {bookMsg && <div style={{ fontSize: 11, color: bookMsg.startsWith("✅") ? "#14c882" : "#f06060", width: "100%" }}>{bookMsg}</div>}
              </div>
            )}
          </div>

          <div>
            <div style={{ ...labelStyle, marginBottom: 10 }}>TAGS</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 10 }}>
              {(display.tags || []).length > 0
                ? display.tags.map((t) => <TagChip key={t} tag={tagByName(t)} onRemove={() => removeTag(t)} />)
                : <span style={{ fontSize: 11, color: "#3a5a80" }}>No tags yet.</span>}
            </div>
            <div style={{ display: "flex", gap: 6 }}>
              <select value={tagPick} onChange={(e) => setTagPick(e.target.value)} className="dg-input" style={{ flex: 1, background: "#080c14" }}>
                <option value="">— add existing tag —</option>
                {allTags.filter((t) => !(display.tags || []).includes(t.name)).map((t) => (
                  <option key={t.id} value={t.name}>{t.name}</option>
                ))}
              </select>
              <button type="button" onClick={() => addTag(tagPick)} disabled={!tagPick} className="btn btn-secondary" style={{ fontSize: 11 }}>Add</button>
            </div>
          </div>
        </div>
      </aside>
    </div>
  );
}

function LeadsTab({ token, onMessage }) {
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [form, setForm] = useState({ business: "", owner: "", phone: "", email: "", website: "", city: "", state: "", notes: "" });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  const [parsed, setParsed] = useState(null);
  const [importResult, setImportResult] = useState(null);
  const [importing, setImporting] = useState(false);

  // Tagging — mirrors the internal CRM's tag system (routers/tags.py +
  // routers/crm.py's per-contact tag endpoints), scoped to this client's
  // own leads via the portal_add_lead_tag/portal_remove_lead_tag endpoints.
  const [allTags, setAllTags] = useState([]);
  const [activeTag, setActiveTag] = useState("");
  const [tagPickFor, setTagPickFor] = useState(null); // lead id currently showing the "add tag" picker
  const [selectedLead, setSelectedLead] = useState(null); // lead currently open in the contact card drawer

  const tagByName = (name) => allTags.find((t) => t.name === name) || { name, color: "#3a7bd5" };

  const loadTags = async () => {
    const r = await fetch(`/portal-api/${token}/tags`);
    if (r.ok) setAllTags(await r.json());
  };

  const load = async () => {
    setLoading(true);
    const qs = activeTag ? `?tag=${encodeURIComponent(activeTag)}` : "";
    const r = await fetch(`/portal-api/${token}/leads${qs}`);
    if (r.ok) setLeads(await r.json());
    setLoading(false);
  };

  useEffect(() => { loadTags(); /* eslint-disable-next-line */ }, [token]);
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [token, activeTag]);

  const addTagToLead = async (leadId, tagName) => {
    if (!tagName.trim()) return;
    const r = await fetch(`/portal-api/${token}/leads/${leadId}/tags`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tag: tagName.trim() }),
    });
    if (r.ok) {
      const updated = await r.json();
      setLeads((prev) => prev.map((l) => (l.id === leadId ? updated : l)));
    }
    setTagPickFor(null);
  };

  const removeTagFromLead = async (leadId, tagName) => {
    const r = await fetch(`/portal-api/${token}/leads/${leadId}/tags/${encodeURIComponent(tagName)}`, { method: "DELETE" });
    if (r.ok) {
      const updated = await r.json();
      setLeads((prev) => prev.map((l) => (l.id === leadId ? updated : l)));
    }
  };

  const addLead = async () => {
    if (!form.phone.trim()) { setErr("Phone is required."); return; }
    setSaving(true); setErr("");
    const r = await fetch(`/portal-api/${token}/leads`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(form),
    });
    if (r.ok) {
      setForm({ business: "", owner: "", phone: "", email: "", website: "", city: "", state: "", notes: "" });
      setShowAdd(false);
      load();
    } else {
      const d = await r.json().catch(() => ({}));
      setErr(d.detail || "Save failed.");
    }
    setSaving(false);
  };

  const handleFile = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => { setParsed(parseLeadCSV(ev.target.result)); setImportResult(null); };
    reader.readAsText(file);
  };

  const doImport = async () => {
    if (!parsed?.length) return;
    setImporting(true);
    const r = await fetch(`/portal-api/${token}/leads/import`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ contacts: parsed }),
    });
    if (r.ok) { setImportResult(await r.json()); load(); }
    setImporting(false);
  };

  const withPhone = parsed ? parsed.filter((r) => r.phone) : [];

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <SectionHeading>Leads ({leads.length})</SectionHeading>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <select
            className="dg-input"
            value={activeTag}
            onChange={(e) => setActiveTag(e.target.value)}
            style={{ fontSize: 11, padding: "6px 10px", width: 150 }}
          >
            <option value="">All tags</option>
            {allTags.map((t) => <option key={t.id} value={t.name}>{t.name}</option>)}
          </select>
          <button className="btn btn-secondary" style={{ fontSize: 11 }} onClick={() => { setShowImport((s) => !s); setShowAdd(false); }}>
            {showImport ? "CANCEL" : "IMPORT CSV"}
          </button>
          <button className="btn btn-primary" style={{ fontSize: 11 }} onClick={() => { setShowAdd((s) => !s); setShowImport(false); }}>
            {showAdd ? "CANCEL" : "+ ADD LEAD"}
          </button>
        </div>
      </div>

      {showAdd && (
        <div className="glass-card" style={{ padding: "18px 20px", marginBottom: 20, display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ display: "flex", gap: 10 }}>
            <input className="dg-input" placeholder="Business name" value={form.business} onChange={(e) => setForm((f) => ({ ...f, business: e.target.value }))} style={{ flex: 1 }} />
            <input className="dg-input" placeholder="Owner / contact" value={form.owner} onChange={(e) => setForm((f) => ({ ...f, owner: e.target.value }))} style={{ flex: 1 }} />
          </div>
          <div style={{ display: "flex", gap: 10 }}>
            <input className="dg-input" placeholder="Phone *" value={form.phone} onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))} style={{ flex: 1 }} />
            <input className="dg-input" placeholder="Email" value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} style={{ flex: 1 }} />
          </div>
          <div style={{ display: "flex", gap: 10 }}>
            <input className="dg-input" placeholder="City" value={form.city} onChange={(e) => setForm((f) => ({ ...f, city: e.target.value }))} style={{ flex: 1 }} />
            <input className="dg-input" placeholder="State" value={form.state} onChange={(e) => setForm((f) => ({ ...f, state: e.target.value }))} style={{ flex: 1 }} />
          </div>
          <input className="dg-input" placeholder="Website" value={form.website} onChange={(e) => setForm((f) => ({ ...f, website: e.target.value }))} />
          <textarea className="dg-input" rows={2} placeholder="Notes" value={form.notes} onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))} style={{ resize: "vertical" }} />
          {err && <div style={{ fontSize: 12, color: "#e05555" }}>{err}</div>}
          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <button className="btn btn-primary" onClick={addLead} disabled={saving} style={{ fontSize: 11 }}>{saving ? "SAVING…" : "SAVE LEAD"}</button>
          </div>
        </div>
      )}

      {showImport && (
        <div className="glass-card" style={{ padding: "18px 20px", marginBottom: 20, display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ fontSize: 12, color: "#8aaad0", lineHeight: 1.6 }}>
            CSV with a <strong>phone</strong> column required. Recognized headers: business, owner, phone, email, website, city, state, notes.
          </div>
          <input type="file" accept=".csv,text/csv" onChange={handleFile} />
          {parsed && !importResult && (
            <>
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 11, color: "#6ab0ff" }}>
                {withPhone.length} leads ready · {parsed.length - withPhone.length} skipped (no phone)
              </div>
              <button className="btn btn-primary" onClick={doImport} disabled={importing} style={{ fontSize: 11, width: "fit-content" }}>
                {importing ? "IMPORTING…" : `IMPORT ${withPhone.length} LEADS`}
              </button>
            </>
          )}
          {importResult && (
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 11, color: "#14c882" }}>
              {importResult.inserted} added · {importResult.updated} updated · {importResult.skipped} skipped
            </div>
          )}
        </div>
      )}

      <div className="glass-card" style={{ padding: 0, overflow: "hidden", overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid rgba(58,123,213,0.15)" }}>
              {["Business", "Owner", "Phone", "Email", "City", "State", "Tags"].map((h) => (
                <th key={h} style={{ textAlign: "left", padding: "10px 14px", fontSize: 10, color: "#5a6f8f", fontFamily: "'Share Tech Mono', monospace", letterSpacing: "0.05em" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {!loading && leads.length === 0 && (
              <tr><td colSpan={7} style={{ padding: 20, textAlign: "center", color: "#3a5a80", fontSize: 12 }}>No leads yet.</td></tr>
            )}
            {leads.map((l) => (
              <tr
                key={l.id}
                onClick={() => setSelectedLead(l)}
                style={{ borderBottom: "1px solid rgba(58,123,213,0.08)", cursor: "pointer" }}
                onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(58,123,213,0.04)"; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
              >
                <td style={{ padding: "10px 14px", fontSize: 12, color: "#f0f4ff" }}>{l.business || "—"}</td>
                <td style={{ padding: "10px 14px", fontSize: 12, color: "#8a9cc0" }}>{l.owner || "—"}</td>
                <td style={{ padding: "10px 14px", fontSize: 12, color: "#8a9cc0" }}>{l.phone || "—"}</td>
                <td style={{ padding: "10px 14px", fontSize: 12, color: "#8a9cc0" }}>{l.email || "—"}</td>
                <td style={{ padding: "10px 14px", fontSize: 12, color: "#8a9cc0" }}>{l.city || "—"}</td>
                <td style={{ padding: "10px 14px", fontSize: 12, color: "#8a9cc0" }}>{l.state || "—"}</td>
                <td style={{ padding: "10px 14px", fontSize: 12 }} onClick={(e) => e.stopPropagation()}>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 4, alignItems: "center" }}>
                    {(l.tags || []).map((tagName) => (
                      <TagChip key={tagName} tag={tagByName(tagName)} onRemove={() => removeTagFromLead(l.id, tagName)} />
                    ))}
                    {tagPickFor === l.id ? (
                      <select
                        autoFocus
                        className="dg-input"
                        style={{ fontSize: 10, padding: "2px 6px", width: 110 }}
                        onChange={(e) => addTagToLead(l.id, e.target.value)}
                        onBlur={() => setTagPickFor(null)}
                        defaultValue=""
                      >
                        <option value="" disabled>Pick tag…</option>
                        {allTags.filter((t) => !(l.tags || []).includes(t.name)).map((t) => (
                          <option key={t.id} value={t.name}>{t.name}</option>
                        ))}
                      </select>
                    ) : (
                      <span
                        onClick={() => setTagPickFor(l.id)}
                        style={{ cursor: "pointer", fontSize: 10, color: "#3a7bd5", fontFamily: "'Share Tech Mono', monospace" }}
                      >+ tag</span>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selectedLead && (
        <LeadDrawer
          token={token}
          lead={selectedLead}
          allTags={allTags}
          onClose={() => setSelectedLead(null)}
          onUpdated={(updated) => {
            setSelectedLead(updated);
            setLeads((prev) => prev.map((l) => (l.id === updated.id ? updated : l)));
          }}
          onMessage={() => { onMessage(selectedLead.id); setSelectedLead(null); }}
        />
      )}
    </div>
  );
}

function fmtMsgTime(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

function InboxThread({ token, contactId, onSent }) {
  const [thread, setThread] = useState(null);
  const [loading, setLoading] = useState(true);
  const [channel, setChannel] = useState("sms");
  const [draft, setDraft] = useState("");
  const [notice, setNotice] = useState(null);
  const [sending, setSending] = useState(false);

  const load = async () => {
    setLoading(true);
    const r = await fetch(`/portal-api/${token}/inbox/${contactId}`);
    if (r.ok) {
      const data = await r.json();
      setThread(data);
      setChannel(data.contact.phone ? "sms" : "email");
    }
    setLoading(false);
  };

  useEffect(() => { setNotice(null); setDraft(""); load(); /* eslint-disable-next-line */ }, [token, contactId]);

  const send = async () => {
    if (!draft.trim()) return;
    setSending(true);
    // Backend now times out a hung Gmail/Twilio call after 20s (see
    // client_portal.py's portal_send_message), but this client-side
    // AbortController is the actual fix for the reported "freeze" — the
    // fetch itself had no timeout at all before, so if the request somehow
    // never got a response (network drop, etc.) the SEND button would stay
    // disabled forever with no way out short of reloading the page.
    const controller = new AbortController();
    const abortTimer = setTimeout(() => controller.abort(), 25000);
    try {
      const r = await fetch(`/portal-api/${token}/inbox/${contactId}/send`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ channel, body: draft.trim() }),
        signal: controller.signal,
      });
      const data = await r.json().catch(() => ({}));
      if (r.ok && data.ok) {
        setNotice(null);
        setDraft("");
        await load();
        onSent?.();
      } else {
        setNotice(data.detail || "Couldn't send — try again.");
      }
    } catch (e) {
      setNotice(e.name === "AbortError" ? "Send timed out — try again." : "Couldn't send — try again.");
    } finally {
      clearTimeout(abortTimer);
      setSending(false);
    }
  };

  if (loading) return <div style={{ padding: 40, color: "#3a5a80", fontFamily: "'Share Tech Mono', monospace", fontSize: 11 }}>LOADING...</div>;
  if (!thread) return null;

  const { contact } = thread;
  // The SMS/EMAIL buttons below double as the reply channel AND a filter
  // on the thread itself — previously they only set the send channel, so
  // clicking them visibly changed nothing in the message list, which read
  // as "doesn't do anything." Only filters when the contact actually has
  // both channels present; otherwise there's nothing to filter.
  const hasBothChannels = Boolean(contact.phone) && Boolean(contact.email);
  const messages = hasBothChannels ? thread.messages.filter((m) => m.channel === channel) : thread.messages;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ padding: "14px 18px", borderBottom: "1px solid rgba(58,123,213,0.12)" }}>
        <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600, fontSize: 14, color: "#d0e8ff" }}>
          {contact.owner || contact.business || "—"}
        </div>
        <div style={{ fontSize: 11, color: "#5a7096", marginTop: 2 }}>
          {[contact.phone, contact.email].filter(Boolean).join(" · ")}
        </div>
      </div>

      {/* minHeight: 0 is load-bearing here — a flex child defaults to
          min-height: auto, so without it this div grows to fit every
          message instead of respecting flex:1, pushing the parent past
          the glass-card's fixed 560px height and getting clipped by its
          overflow:hidden instead of actually scrolling. Reported live as
          "doesn't let me scroll" with the last message cut off. */}
      <div style={{ flex: 1, minHeight: 0, overflowY: "auto", padding: 18, display: "flex", flexDirection: "column", gap: 10 }}>
        {messages.length === 0 && (
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52" }}>NO MESSAGES YET</div>
        )}
        {messages.map((m, i) => {
          const outbound = m.direction === "outbound";
          return (
            <div key={i} style={{ display: "flex", justifyContent: outbound ? "flex-end" : "flex-start" }}>
              <div style={{
                maxWidth: "72%", padding: "9px 13px", borderRadius: 12,
                background: outbound ? "rgba(58,123,213,0.18)" : "rgba(255,255,255,0.04)",
                border: outbound ? "1px solid rgba(58,123,213,0.3)" : "1px solid rgba(255,255,255,0.06)",
              }}>
                <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 3 }}>
                  <span className="mono" style={{ fontSize: 9, color: "#3a7bd5", letterSpacing: "0.06em" }}>{m.channel.toUpperCase()}</span>
                  <span style={{ fontSize: 9, color: "#3a5a80" }}>{fmtMsgTime(m.sent_at)}</span>
                </div>
                {m.subject && <div style={{ fontSize: 12, fontWeight: 600, color: "#c4d0e8", marginBottom: 3 }}>{m.subject}</div>}
                <div style={{ fontSize: 13, color: "#d0e8ff", lineHeight: 1.5, whiteSpace: "pre-wrap" }}>{m.body}</div>
              </div>
            </div>
          );
        })}
      </div>

      <div style={{ padding: 14, borderTop: "1px solid rgba(58,123,213,0.12)" }}>
        {notice && (
          <div style={{ fontSize: 11.5, color: "#f0a028", marginBottom: 10, lineHeight: 1.5 }}>{notice}</div>
        )}
        <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
          {contact.phone && (
            <button onClick={() => setChannel("sms")} className="btn btn-secondary" style={{ fontSize: 10, opacity: channel === "sms" ? 1 : 0.5 }}>SMS</button>
          )}
          {contact.email && (
            <button onClick={() => setChannel("email")} className="btn btn-secondary" style={{ fontSize: 10, opacity: channel === "email" ? 1 : 0.5 }}>EMAIL</button>
          )}
        </div>
        <textarea
          className="dg-input" rows={2} placeholder="Type a reply..."
          value={draft} onChange={(e) => setDraft(e.target.value)}
          style={{ width: "100%", resize: "vertical", marginBottom: 8 }}
        />
        <button className="btn btn-primary" onClick={send} disabled={sending || !draft.trim()} style={{ fontSize: 11 }}>
          {sending ? "SENDING..." : "SEND"}
        </button>
      </div>
    </div>
  );
}

// Filter bar mirrors the internal InboxPanel's shape (channel/since/tag
// query params against email_inbox.py) — see client_portal.py's
// portal_inbox_list for the matching backend params. `status` (contact
// pipeline status — "dialer-lead", "gatekeeper-blocked", etc.) is
// deliberately left out of the client-facing UI even though the backend
// accepts it: those are DigiGrowth's own internal sales-pipeline labels,
// not something meaningful to show a client about their own leads — same
// reasoning as excluding the anchor contact elsewhere in this file.
const INBOX_CHANNEL_OPTIONS = [["all", "All Channels"], ["sms", "SMS"], ["email", "Email"]];

function InboxTab({ token, initialContactId, onInitialContactConsumed }) {
  const [convos, setConvos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [channelFilter, setChannelFilter] = useState("all");
  const [sinceFilter, setSinceFilter] = useState("all");
  const [tagFilter, setTagFilter] = useState("");
  const [allTags, setAllTags] = useState([]);
  // Search — same business/owner/phone/email match the CRM's contact
  // search uses (GET /contacts?search=), applied client-side here since
  // the inbox list is small per client and already fully loaded.
  const [searchQuery, setSearchQuery] = useState("");
  // Read/Unread/All — same client-side filter as the internal InboxPanel's
  // readFilter (that one's client-side there too, not a backend param).
  const [readFilter, setReadFilter] = useState("all");

  const load = async () => {
    setLoading(true);
    const params = new URLSearchParams({ channel: channelFilter, since: sinceFilter });
    if (tagFilter) params.set("tag", tagFilter);
    const r = await fetch(`/portal-api/${token}/inbox?${params.toString()}`);
    if (r.ok) setConvos(await r.json());
    setLoading(false);
  };

  useEffect(() => {
    fetch(`/portal-api/${token}/tags`).then((r) => r.ok && r.json()).then((d) => d && setAllTags(d));
    /* eslint-disable-next-line */
  }, [token]);
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [token, channelFilter, sinceFilter, tagFilter]);

  // Jumped here from a lead's "Message" button — open that contact's
  // thread directly even if it has no prior messages yet (InboxThread/the
  // backend's GET /{token}/inbox/{contactId} both handle an empty
  // history fine), then clear the pending target so re-visiting the tab
  // later doesn't keep forcing it back open.
  useEffect(() => {
    if (initialContactId) {
      setSelected(initialContactId);
      onInitialContactConsumed?.();
    }
    /* eslint-disable-next-line */
  }, [initialContactId]);

  const openConvo = (contactId) => {
    setSelected(contactId);
    setConvos((prev) => prev.map((c) => (c.contact_id === contactId ? { ...c, unread: false } : c)));
  };

  const q = searchQuery.trim().toLowerCase();
  const visibleConvos = convos
    .filter((c) => !q || [c.business, c.owner, c.phone, c.email, c.last_message].some((v) => (v || "").toLowerCase().includes(q)))
    .filter((c) => readFilter === "all" || (readFilter === "unread" ? c.unread : !c.unread));

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <SectionHeading>Inbox</SectionHeading>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input
            className="dg-input"
            placeholder="Search business, owner, phone, email…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ fontSize: 11, padding: "6px 10px", width: 220 }}
          />
          <select className="dg-input" value={channelFilter} onChange={(e) => setChannelFilter(e.target.value)} style={{ fontSize: 11, padding: "6px 10px", width: 130 }}>
            {INBOX_CHANNEL_OPTIONS.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
          </select>
          <select className="dg-input" value={readFilter} onChange={(e) => setReadFilter(e.target.value)} style={{ fontSize: 11, padding: "6px 10px", width: 110 }}>
            <option value="all">All</option>
            <option value="unread">Unread</option>
            <option value="read">Read</option>
          </select>
          <select className="dg-input" value={tagFilter} onChange={(e) => setTagFilter(e.target.value)} style={{ fontSize: 11, padding: "6px 10px", width: 130 }}>
            <option value="">All tags</option>
            {allTags.map((t) => <option key={t.id} value={t.name}>{t.name}</option>)}
          </select>
          <PeriodToggle days={sinceFilter} setDays={setSinceFilter} options={PORTAL_PERIOD_OPTIONS} />
        </div>
      </div>
      <div className="glass-card" style={{ padding: 0, overflow: "hidden", display: "grid", gridTemplateColumns: "300px 1fr", height: 560 }}>
        <div style={{ borderRight: "1px solid rgba(58,123,213,0.12)", overflowY: "auto" }}>
          {loading && <div style={{ padding: 20, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52" }}>LOADING…</div>}
          {!loading && visibleConvos.length === 0 && (
            <div style={{ padding: 20, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52", lineHeight: 1.6 }}>
              {q || readFilter !== "all" ? "NO MATCHES" : "NO CONVERSATIONS YET — this fills in once your SMS/email account is connected."}
            </div>
          )}
          {visibleConvos.map((c) => {
            const isSel = selected === c.contact_id;
            // Unread highlight mirrors the internal InboxPanel's own
            // treatment exactly (tinted background + accent left border +
            // glowing dot + bold name) — selection always wins visually
            // over unread once a thread's open, same as internal.
            const isUnread = c.unread && !isSel;
            return (
              <button
                key={c.contact_id}
                onClick={() => openConvo(c.contact_id)}
                style={{
                  display: "block", width: "100%", textAlign: "left", cursor: "pointer",
                  padding: "12px 16px", border: "none", borderTop: "none", borderRight: "none",
                  borderBottom: "1px solid rgba(58,123,213,0.08)",
                  borderLeft: isSel ? "2px solid #3a7bd5" : (isUnread ? "2px solid rgba(58,123,213,0.5)" : "2px solid transparent"),
                  background: isSel ? "rgba(58,123,213,0.1)" : (isUnread ? "rgba(58,123,213,0.06)" : "none"),
                  transition: "background 0.1s",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  {isUnread && (
                    <span title="Unread message" style={{
                      width: 7, height: 7, borderRadius: "50%", flexShrink: 0,
                      background: "#3a7bd5", boxShadow: "0 0 6px 1px rgba(58,123,213,0.7)",
                    }} />
                  )}
                  <span style={{ fontSize: 13, fontWeight: isUnread ? 700 : 600, color: isUnread ? "#f0f4ff" : "#d0e8ff", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {c.owner || c.business || c.phone || c.email}
                  </span>
                </div>
                <div style={{ display: "flex", gap: 6, marginTop: 4 }}>
                  {c.channels.map((ch) => (
                    <span key={ch} className="mono" style={{ fontSize: 8, color: "#3a7bd5", letterSpacing: "0.06em" }}>{ch.toUpperCase()}</span>
                  ))}
                </div>
                {c.last_message && (
                  <div style={{ fontSize: 11, color: isUnread ? "#8aaad0" : "#5a7096", fontWeight: isUnread ? 600 : 400, marginTop: 4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {c.last_message}
                  </div>
                )}
              </button>
            );
          })}
        </div>
        {/* Grid items default to min-height: auto, so without an explicit
            height + overflow:hidden here this column grows to fit
            InboxThread's content instead of being capped at the grid
            row's 560px track — that's what let the thread panel overflow
            past the glass-card and get clipped instead of scrolling. */}
        <div style={{ height: 560, overflow: "hidden" }}>
          {selected ? (
            <InboxThread token={token} contactId={selected} onSent={load} />
          ) : (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "#3a5a80", fontSize: 13 }}>
              Select a conversation
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function ClientPortal() {
  const { token } = useParams();
  const [client, setClient] = useState(null);
  const [notFound, setNotFound] = useState(false);
  const [tab, setTab] = useState("dashboard");
  // Set by LeadDrawer's "Message" button (via LeadsTab's onMessage prop) to
  // jump to the Inbox tab with that lead's thread already open — mirrors
  // the internal CRM's ContactDrawer messageContact()/onNavigate("inbox",
  // {contactId}) pattern. Lives here (not in InboxTab's own state) since
  // Leads and Inbox are sibling tabs.
  const [inboxTargetContactId, setInboxTargetContactId] = useState(null);

  useEffect(() => {
    fetch(`/portal-api/${token}`)
      .then((r) => {
        if (!r.ok) { setNotFound(true); return null; }
        return r.json();
      })
      .then((data) => { if (data) setClient(data); })
      .catch(() => setNotFound(true));
  }, [token]);

  if (notFound) {
    return (
      <div style={{ minHeight: "100vh", background: "#090f26", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "'Space Grotesk', sans-serif", color: "#8aaad0" }}>
        This link is no longer valid.
      </div>
    );
  }

  return (
    <div style={{
      minHeight: "100vh",
      background: "#090f26",
      backgroundImage: "radial-gradient(ellipse at 20% 50%, rgba(40,87,160,0.08) 0%, transparent 60%), radial-gradient(ellipse at 80% 20%, rgba(58,123,213,0.05) 0%, transparent 50%)",
      fontFamily: "'Space Grotesk', sans-serif",
    }}>
      <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Share+Tech+Mono&display=swap" rel="stylesheet" />

      <div style={{ borderBottom: "1px solid rgba(58,123,213,0.15)", padding: "20px 40px", display: "flex", alignItems: "center", gap: 16 }}>
        <div style={{ width: 32, height: 32, background: "linear-gradient(135deg, #1a3a6b 0%, #2857a0 100%)", borderRadius: 8, border: "1px solid rgba(58,123,213,0.3)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
          <svg viewBox="0 0 16 16" fill="none" width={13} height={13}>
            <rect x="2" y="1" width="12" height="14" rx="1.5" stroke="#6ab0ff" strokeWidth="1.4" />
            <path d="M5 5h6M5 8h6M5 11h4" stroke="#6ab0ff" strokeWidth="1.2" strokeLinecap="round" />
          </svg>
        </div>
        <div>
          <div style={{ fontWeight: 700, fontSize: 15, color: "#e8f0ff" }}>{client ? client.name : "DigiGrowth"}</div>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80", letterSpacing: "0.14em" }}>CLIENT PORTAL</div>
        </div>
      </div>

      <div style={{ maxWidth: 1240, margin: "0 auto", padding: "36px 24px" }}>
        <div style={{ display: "flex", gap: 8, marginBottom: 28, borderBottom: "1px solid rgba(58,123,213,0.1)" }}>
          {Object.entries(TAB_LABELS).map(([id, label]) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              style={{
                background: "none", border: "none", cursor: "pointer",
                padding: "10px 16px", fontFamily: "'Space Grotesk', sans-serif", fontSize: 13, fontWeight: 600,
                color: tab === id ? "#6ab0ff" : "#5a7aa0",
                borderBottom: tab === id ? "2px solid #3a7bd5" : "2px solid transparent",
              }}
            >
              {label}
            </button>
          ))}
        </div>

        {tab === "dashboard" && <DashboardTab token={token} />}
        {tab === "appointments" && <AppointmentsTab token={token} />}
        {tab === "leads" && (
          <LeadsTab
            token={token}
            onMessage={(contactId) => { setInboxTargetContactId(contactId); setTab("inbox"); }}
          />
        )}
        {tab === "inbox" && (
          <InboxTab
            token={token}
            initialContactId={inboxTargetContactId}
            onInitialContactConsumed={() => setInboxTargetContactId(null)}
          />
        )}
        {tab === "onboarding" && <OnboardingTab token={token} onGoToTab={setTab} />}
        {tab === "videos" && <VideosTab token={token} />}
      </div>
    </div>
  );
}
