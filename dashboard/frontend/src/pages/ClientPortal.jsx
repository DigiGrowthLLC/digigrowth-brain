import React, { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import {
  LineChart, Line,
  BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer,
} from "recharts";

const SECTIONS = [
  {
    key: "practice_snapshot",
    title: "Practice Snapshot",
    questions: [
      { key: "name_website", label: "Practice name & website" },
      { key: "service_area", label: "City/metro you serve, and do you treat multiple locations?" },
      { key: "top_conditions", label: "Top 3–5 conditions or complaints you treat most" },
      { key: "insurance", label: "Do you accept insurance, cash-pay, or both? If insurance, which panels?" },
    ],
  },
  {
    key: "ideal_patient",
    title: "Ideal Patient",
    questions: [
      { key: "best_patient", label: "Describe your best patient — age range, what brought them in, why they stuck with the full plan of care" },
      { key: "drop_off_reason", label: "What's the #1 reason a good-fit patient doesn't book after inquiring?" },
    ],
  },
  {
    key: "offer_economics",
    title: "Offer & Economics",
    questions: [
      { key: "avg_visits", label: "Average number of visits per plan of care" },
      { key: "avg_revenue", label: "Average revenue per patient over a full plan of care, roughly" },
      { key: "specials", label: "Do you currently run any specials, free screens, or intro offers?" },
    ],
  },
  {
    key: "differentiation_voice",
    title: "Differentiation & Voice",
    questions: [
      { key: "why_you", label: "Why do patients choose you over the PT practice or chiro down the street?" },
      { key: "avoid", label: "Any phrases, claims, or tone you want us to avoid (regulatory, brand, or personal preference)?" },
      { key: "reviews", label: "Link to your best Google/FB reviews, or a couple of patient quotes we can use" },
    ],
  },
  {
    key: "current_marketing",
    title: "Current Marketing & Assets",
    questions: [
      { key: "past_marketing", label: "What marketing have you tried before, and what worked or flopped?" },
      { key: "assets", label: "Do you have existing photo/video of the clinic, staff, or patient sessions we can use?" },
      { key: "inquiry_volume", label: "Roughly how many new patient inquiries are you getting a month right now, from any source?" },
    ],
  },
  {
    key: "ops",
    title: "Ops",
    questions: [
      { key: "booking_software", label: "What do you currently book appointments with (software/system)?" },
      { key: "handoff", label: "Who on staff should the AI booking agent hand off to for anything it can't answer?" },
      { key: "no_show_rate", label: "Rough no-show rate today, if you know it" },
    ],
  },
];

const TAB_LABELS = {
  dashboard: "Dashboard",
  appointments: "Appointments",
  leads: "Leads",
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

function OnboardingTab({ token }) {
  const [responses, setResponses] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(null);
  const [openSection, setOpenSection] = useState(SECTIONS[0].key);

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

  if (loading) return <div style={{ color: "#3a5a80", fontFamily: "'Share Tech Mono', monospace", fontSize: 11, padding: 40 }}>LOADING...</div>;

  const completedCount = SECTIONS.filter((s) => responses[s.key]?.completed_at).length;

  return (
    <div>
      <div className="stat-card" style={{ marginBottom: 24, maxWidth: 260 }}>
        <div className="stat-card-label">Onboarding Progress</div>
        <div className="stat-card-value">{completedCount}/{SECTIONS.length}</div>
      </div>

      {SECTIONS.map((s) => {
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
      })}
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
      .then((data) => { setRows((data || []).slice(0, 5)); setLoading(false); })
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

  useEffect(() => {
    fetch(`/portal-api/${token}/stats`)
      .then((r) => r.json())
      .then((data) => { setStats(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [token]);

  if (loading) return <div style={{ color: "#3a5a80", fontFamily: "'Share Tech Mono', monospace", fontSize: 11, padding: 40 }}>LOADING...</div>;
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

function OutcomePill({ active, color, onClick, disabled, children }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        fontFamily: "'Share Tech Mono', monospace", fontSize: 9, letterSpacing: "0.04em",
        padding: "3px 8px", borderRadius: 4, cursor: disabled ? "not-allowed" : "pointer",
        color: active ? color : "#3a5a80",
        background: active ? `${color}1a` : "transparent",
        border: `1px solid ${active ? color : "#1a2540"}`,
        opacity: disabled ? 0.5 : 1,
      }}
    >{children}</button>
  );
}

function AppointmentOutcome({ token, appointment, onUpdated }) {
  const [saving, setSaving] = useState(false);

  const setOutcome = async (field, value) => {
    const next = appointment[field] === value ? null : value;
    setSaving(true);
    try {
      const r = await fetch(`/portal-api/${token}/appointments/${appointment.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ [field]: next }),
      });
      if (r.ok) onUpdated(await r.json());
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
      <div style={{ display: "flex", gap: 4 }}>
        <OutcomePill active={appointment.outcome_show === "show"} color="#14c882" disabled={saving}
          onClick={() => setOutcome("outcome_show", "show")}>SHOW</OutcomePill>
        <OutcomePill active={appointment.outcome_show === "no_show"} color="#dc3c3c" disabled={saving}
          onClick={() => setOutcome("outcome_show", "no_show")}>NO SHOW</OutcomePill>
      </div>
      <div style={{ display: "flex", gap: 4 }}>
        <OutcomePill active={appointment.outcome_close === "closed"} color="#14c882" disabled={saving}
          onClick={() => setOutcome("outcome_close", "closed")}>CLOSED</OutcomePill>
        <OutcomePill active={appointment.outcome_close === "not_closed"} color="#dc3c3c" disabled={saving}
          onClick={() => setOutcome("outcome_close", "not_closed")}>LOST</OutcomePill>
      </div>
    </div>
  );
}

const APPT_PAST_GRACE_MS = 60 * 60 * 1000;
const APPT_FILTER_LABELS = { upcoming: "Upcoming", past: "Past", canceled: "Canceled", all: "All" };

function AppointmentsTab({ token }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("upcoming");

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

  const handleUpdated = (updated) => {
    setRows((rs) => rs.map((r) => (r.id === updated.id ? { ...r, ...updated } : r)));
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
                  {row.status !== "canceled" && <AppointmentOutcome token={token} appointment={row} onUpdated={handleUpdated} />}
                  {row.status === "canceled" && <span style={{ fontSize: 11, color: "#3a5a80" }}>canceled</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
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

function LeadsTab({ token }) {
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

  const load = async () => {
    setLoading(true);
    const r = await fetch(`/portal-api/${token}/leads`);
    if (r.ok) setLeads(await r.json());
    setLoading(false);
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [token]);

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
        <div style={{ display: "flex", gap: 8 }}>
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
              {["Business", "Owner", "Phone", "Email", "City", "State"].map((h) => (
                <th key={h} style={{ textAlign: "left", padding: "10px 14px", fontSize: 10, color: "#5a6f8f", fontFamily: "'Share Tech Mono', monospace", letterSpacing: "0.05em" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {!loading && leads.length === 0 && (
              <tr><td colSpan={6} style={{ padding: 20, textAlign: "center", color: "#3a5a80", fontSize: 12 }}>No leads yet.</td></tr>
            )}
            {leads.map((l) => (
              <tr key={l.id} style={{ borderBottom: "1px solid rgba(58,123,213,0.08)" }}>
                <td style={{ padding: "10px 14px", fontSize: 12, color: "#f0f4ff" }}>{l.business || "—"}</td>
                <td style={{ padding: "10px 14px", fontSize: 12, color: "#8a9cc0" }}>{l.owner || "—"}</td>
                <td style={{ padding: "10px 14px", fontSize: 12, color: "#8a9cc0" }}>{l.phone || "—"}</td>
                <td style={{ padding: "10px 14px", fontSize: 12, color: "#8a9cc0" }}>{l.email || "—"}</td>
                <td style={{ padding: "10px 14px", fontSize: 12, color: "#8a9cc0" }}>{l.city || "—"}</td>
                <td style={{ padding: "10px 14px", fontSize: 12, color: "#8a9cc0" }}>{l.state || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function ClientPortal() {
  const { token } = useParams();
  const [client, setClient] = useState(null);
  const [notFound, setNotFound] = useState(false);
  const [tab, setTab] = useState("dashboard");

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
        {tab === "leads" && <LeadsTab token={token} />}
        {tab === "onboarding" && <OnboardingTab token={token} />}
        {tab === "videos" && <VideosTab token={token} />}
      </div>
    </div>
  );
}
