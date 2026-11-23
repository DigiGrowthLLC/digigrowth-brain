import React, { useState } from "react";

// DigiGrowth OS design kit (2026-11-17 refresh). New and redesigned screens
// build from these instead of one-off inline styles, so spacing, type and
// color stay consistent. Colors mirror the CSS variables in index.css.
export const T = {
  bg: "#070c1e",
  surface: "rgba(13,22,52,0.72)",
  surface2: "rgba(255,255,255,0.03)",
  line: "rgba(120,150,210,0.14)",
  lineStrong: "rgba(120,150,210,0.26)",
  text: "#eaf1ff",
  textDim: "#a9bad8",
  textMute: "#6c7fa3",
  accent: "#4d8ef0",
  accentSoft: "rgba(77,142,240,0.14)",
  good: "#2fd08f",
  warn: "#f2ad3d",
  bad: "#f06a6a",
  font: "'Inter', 'Space Grotesk', system-ui, sans-serif",
  display: "'Space Grotesk', 'Inter', system-ui, sans-serif",
  mono: "'Share Tech Mono', ui-monospace, monospace",
};

const TONES = {
  good: { fg: T.good, bg: "rgba(47,208,143,0.12)" },
  warn: { fg: T.warn, bg: "rgba(242,173,61,0.13)" },
  bad: { fg: T.bad, bg: "rgba(240,106,106,0.13)" },
  info: { fg: "#8fb8ff", bg: T.accentSoft },
  neutral: { fg: T.textDim, bg: "rgba(169,186,216,0.1)" },
};

export function Card({ children, style, pad = 20, onClick, ...rest }) {
  return (
    <div className="ui-card" onClick={onClick} style={{ padding: pad, ...(onClick ? { cursor: "pointer" } : {}), ...style }} {...rest}>
      {children}
    </div>
  );
}

export function PageHeader({ title, subtitle, actions, back }) {
  return (
    <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 16, flexWrap: "wrap", marginBottom: 20 }}>
      <div style={{ minWidth: 0 }}>
        {back}
        <h1 style={{ fontFamily: T.display, fontSize: 26, fontWeight: 700, color: T.text, letterSpacing: "-0.02em", margin: 0, lineHeight: 1.15 }}>{title}</h1>
        {subtitle && <div style={{ fontSize: 13.5, color: T.textMute, marginTop: 5 }}>{subtitle}</div>}
      </div>
      {actions && <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>{actions}</div>}
    </div>
  );
}

export function SectionTitle({ title, hint, right, style }) {
  return (
    <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 12, marginBottom: 10, ...style }}>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontFamily: T.display, fontSize: 15, fontWeight: 600, color: T.text }}>{title}</div>
        {hint && <div style={{ fontSize: 12.5, color: T.textMute, marginTop: 2, lineHeight: 1.45 }}>{hint}</div>}
      </div>
      {right}
    </div>
  );
}

export function Tabs({ tabs, value, onChange, style }) {
  return (
    <div role="tablist" style={{ display: "flex", gap: 2, borderBottom: `1px solid ${T.line}`, overflowX: "auto", ...style }}>
      {tabs.map((t) => {
        const on = value === t.id;
        return (
          <button key={t.id} role="tab" aria-selected={on} onClick={() => onChange(t.id)} style={{
            background: "none", border: "none", cursor: "pointer", padding: "10px 14px", whiteSpace: "nowrap",
            fontFamily: T.font, fontSize: 13.5, fontWeight: on ? 600 : 500, color: on ? T.text : T.textMute,
            borderBottom: `2px solid ${on ? T.accent : "transparent"}`, marginBottom: -1, display: "flex", alignItems: "center", gap: 7,
          }}>
            {t.label}
            {t.count ? <span style={{ fontSize: 11, fontWeight: 600, padding: "1px 7px", borderRadius: 99, background: t.alert ? TONES.warn.bg : TONES.neutral.bg, color: t.alert ? T.warn : T.textDim }}>{t.count}</span> : null}
          </button>
        );
      })}
    </div>
  );
}

export function Pill({ tone = "neutral", children, dot, style, title }) {
  const c = TONES[tone] || TONES.neutral;
  return (
    <span title={title} style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "3px 10px", borderRadius: 99, fontSize: 12, fontWeight: 600, color: c.fg, background: c.bg, whiteSpace: "nowrap", ...style }}>
      {dot && <span style={{ width: 6, height: 6, borderRadius: "50%", background: c.fg }} />}
      {children}
    </span>
  );
}

export function Toggle({ on, onChange, label, busy }) {
  return (
    <button type="button" role="switch" aria-checked={!!on} disabled={busy} onClick={() => onChange(!on)}
      style={{ display: "inline-flex", alignItems: "center", gap: 8, background: "none", border: "none", padding: 0, cursor: busy ? "wait" : "pointer" }}>
      <span style={{ position: "relative", width: 34, height: 20, borderRadius: 99, background: on ? T.good : "rgba(169,186,216,0.22)", transition: "background .15s", flexShrink: 0 }}>
        <span style={{ position: "absolute", top: 2, left: on ? 16 : 2, width: 16, height: 16, borderRadius: "50%", background: "#fff", transition: "left .15s", boxShadow: "0 1px 3px rgba(0,0,0,.3)" }} />
      </span>
      {label && <span style={{ fontSize: 13, fontWeight: 500, color: on ? T.text : T.textMute }}>{label}</span>}
    </button>
  );
}

export function Stat({ label, value, sub, tone }) {
  return (
    <div style={{ minWidth: 0 }}>
      <div style={{ fontSize: 12.5, color: T.textMute }}>{label}</div>
      <div style={{ fontFamily: T.display, fontSize: 24, fontWeight: 700, color: tone ? TONES[tone].fg : T.text, letterSpacing: "-0.02em", fontVariantNumeric: "tabular-nums", lineHeight: 1.25 }}>{value}</div>
      {sub && <div style={{ fontSize: 12, color: T.textMute }}>{sub}</div>}
    </div>
  );
}

export function Progress({ value, max = 1, tone = "info", height = 6 }) {
  const pct = Math.max(0, Math.min(100, Math.round((value / Math.max(1, max)) * 100)));
  return (
    <div style={{ height, borderRadius: 99, background: "rgba(169,186,216,0.12)", overflow: "hidden" }}>
      <div style={{ width: `${pct}%`, height: "100%", borderRadius: 99, background: tone === "good" ? T.good : T.accent }} />
    </div>
  );
}

export function Empty({ children }) {
  return <div style={{ padding: "28px 16px", textAlign: "center", fontSize: 13, color: T.textMute }}>{children}</div>;
}

export function Loading() {
  return <div style={{ padding: "28px 16px", textAlign: "center", fontSize: 13, color: T.textMute }}>Loading…</div>;
}

// Time periods shared by Analytics and Finances (days; 0 = all time), so both
// pages always offer the same choices.
export const PERIOD_OPTIONS = [[1, "Today"], [7, "7 days"], [30, "30 days"], [90, "90 days"], [365, "1 year"], [0, "All time"]];
export const PERIOD_TEXT = { 1: "Today", 7: "Last 7 days", 30: "Last 30 days", 90: "Last 90 days", 365: "Last 12 months", 0: "All time" };

export const fmtDate = (d) => (d ? new Date(d).toLocaleDateString(undefined, { month: "short", day: "numeric" }) : "–");

const HEALTH_TONE = { green: "good", yellow: "warn", red: "bad" };

// Client health score (backend csm_extras.py) with a hover breakdown.
export function HealthBadge({ health, compact }) {
  const [open, setOpen] = useState(false);
  if (!health) return compact ? null : <Pill tone="neutral">No health score yet</Pill>;
  const tone = HEALTH_TONE[health.band] || "neutral";
  const c = TONES[tone];
  return (
    <span style={{ position: "relative", display: "inline-flex" }} onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}
      onClick={(e) => { e.stopPropagation(); setOpen((o) => !o); }}>
      <Pill tone={tone} dot>Health {health.score}</Pill>
      {open && (
        <div style={{ position: "absolute", top: 28, left: 0, zIndex: 30, width: 280, padding: 14, borderRadius: 12, background: "#0f1a3c", border: `1px solid ${T.lineStrong}`, boxShadow: "0 12px 32px rgba(0,0,0,.5)" }}>
          {Object.entries(health.factors || {}).map(([k, f]) => (
            <div key={k} style={{ marginBottom: 8 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: T.textDim }}>
                <span style={{ textTransform: "capitalize" }}>{k}</span><span>{f.points}/{f.of}</span>
              </div>
              <div style={{ height: 4, borderRadius: 2, background: "rgba(169,186,216,0.12)", marginTop: 4 }}>
                <div style={{ width: `${Math.round((f.points / f.of) * 100)}%`, height: "100%", borderRadius: 2, background: c.fg }} />
              </div>
            </div>
          ))}
          {(health.reasons || []).length > 0 && (
            <ul style={{ margin: "8px 0 0", paddingLeft: 16, fontSize: 12.5, color: T.text, lineHeight: 1.45 }}>
              {health.reasons.map((r) => <li key={r} style={{ marginBottom: 3 }}>{r}</li>)}
            </ul>
          )}
        </div>
      )}
    </span>
  );
}

export const inputStyle = {
  width: "100%", boxSizing: "border-box", background: "rgba(5,10,28,0.6)", border: `1px solid ${T.line}`,
  borderRadius: 10, padding: "9px 12px", color: T.text, fontFamily: T.font, fontSize: 13.5, outline: "none",
};
