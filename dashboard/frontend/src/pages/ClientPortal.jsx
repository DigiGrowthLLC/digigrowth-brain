import React, { useState, useEffect } from "react";
import { useParams } from "react-router-dom";

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

const TAB_LABELS = { onboarding: "Onboarding", videos: "Get Started Videos", stats: "Performance" };

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

function StatCell({ label, value }) {
  return (
    <div className="stat-card">
      <div className="stat-card-label">{label}</div>
      <div className="stat-card-value">{value}</div>
    </div>
  );
}

function StatsTab({ token }) {
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

  return (
    <div>
      <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80", letterSpacing: "0.16em", textTransform: "uppercase", marginBottom: 12 }}>SMS</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 14, marginBottom: 28 }}>
        <StatCell label="Conversations" value={stats.sms.conversations} />
        <StatCell label="Messages Sent" value={stats.sms.sent} />
        <StatCell label="Replies" value={stats.sms.replies} />
      </div>

      <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80", letterSpacing: "0.16em", textTransform: "uppercase", marginBottom: 12 }}>Email</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 14, marginBottom: 28 }}>
        <StatCell label="Conversations" value={stats.email.conversations} />
        <StatCell label="Emails Sent" value={stats.email.sent} />
        <StatCell label="Replies" value={stats.email.replies} />
      </div>

      <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80", letterSpacing: "0.16em", textTransform: "uppercase", marginBottom: 12 }}>Facebook Ads</div>
      <div className="glass-card" style={{ textAlign: "center", padding: 30, color: "#5a7aa0", fontSize: 13 }}>
        Facebook Ads reporting — coming soon
      </div>
    </div>
  );
}

export default function ClientPortal() {
  const { token } = useParams();
  const [client, setClient] = useState(null);
  const [notFound, setNotFound] = useState(false);
  const [tab, setTab] = useState("onboarding");

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

      <div style={{ maxWidth: 900, margin: "0 auto", padding: "36px 24px" }}>
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

        {tab === "onboarding" && <OnboardingTab token={token} />}
        {tab === "videos" && <VideosTab token={token} />}
        {tab === "stats" && <StatsTab token={token} />}
      </div>
    </div>
  );
}
