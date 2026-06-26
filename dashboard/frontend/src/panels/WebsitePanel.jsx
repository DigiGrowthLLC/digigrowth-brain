import React from "react";

const VERCEL_URL = "https://vercel.com/digi-growth/digigrowth-website";
const SITE_URL   = "https://digigrowth-website.vercel.app";

export default function WebsitePanel() {
  return (
    <div style={{
      flex: 1, overflowY: "auto", padding: "32px 32px",
      fontFamily: "'Space Grotesk', sans-serif",
    }}>

      {/* Header */}
      <div style={{ marginBottom: 32 }}>
        <div style={{
          fontFamily: "'Share Tech Mono', monospace", fontSize: 10,
          color: "#3a7bd5", letterSpacing: "0.2em", marginBottom: 8,
        }}>
          WEBSITE
        </div>
        <div style={{ fontSize: 22, fontWeight: 700, color: "#d0dcf0", letterSpacing: "-0.3px" }}>
          DigiGrowth Website
        </div>
      </div>

      {/* Cards row */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, maxWidth: 700 }}>

        {/* Vercel Dashboard */}
        <a
          href={VERCEL_URL}
          target="_blank"
          rel="noopener noreferrer"
          style={{ textDecoration: "none" }}
        >
          <div className="glass-card" style={{
            padding: "28px 28px",
            cursor: "pointer",
            transition: "all 0.2s",
            border: "1px solid rgba(58,123,213,0.15)",
          }}
          onMouseEnter={e => {
            e.currentTarget.style.borderColor = "rgba(58,123,213,0.4)";
            e.currentTarget.style.background  = "rgba(15,25,60,0.95)";
            e.currentTarget.style.transform   = "translateY(-3px)";
            e.currentTarget.style.boxShadow   = "0 12px 40px rgba(0,0,0,0.3)";
          }}
          onMouseLeave={e => {
            e.currentTarget.style.borderColor = "rgba(58,123,213,0.15)";
            e.currentTarget.style.background  = "";
            e.currentTarget.style.transform   = "translateY(0)";
            e.currentTarget.style.boxShadow   = "";
          }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14 }}>
              {/* Vercel triangle icon */}
              <div style={{
                width: 38, height: 38, borderRadius: 10,
                background: "linear-gradient(135deg, #1a1a1a, #333)",
                border: "1px solid rgba(255,255,255,0.1)",
                display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
              }}>
                <svg viewBox="0 0 24 24" fill="white" width={16} height={16}>
                  <path d="M12 2L2 19.5h20L12 2z"/>
                </svg>
              </div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: "#d0dcf0" }}>Vercel Dashboard</div>
                <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80", letterSpacing: "0.1em", marginTop: 2 }}>
                  DEPLOYMENTS · LOGS · SETTINGS
                </div>
              </div>
            </div>
            <div style={{ fontSize: 12, color: "#5a6f8f", lineHeight: 1.6 }}>
              View deployments, check build logs, and manage your site settings on Vercel.
            </div>
            <div style={{
              marginTop: 16, display: "inline-flex", alignItems: "center", gap: 6,
              fontSize: 11, color: "#3a7bd5", fontWeight: 600,
            }}>
              Open Vercel <span style={{ fontSize: 13 }}>→</span>
            </div>
          </div>
        </a>

        {/* Live Site */}
        <a
          href={SITE_URL}
          target="_blank"
          rel="noopener noreferrer"
          style={{ textDecoration: "none" }}
        >
          <div className="glass-card" style={{
            padding: "28px 28px",
            cursor: "pointer",
            transition: "all 0.2s",
            border: "1px solid rgba(20,200,130,0.15)",
          }}
          onMouseEnter={e => {
            e.currentTarget.style.borderColor = "rgba(20,200,130,0.4)";
            e.currentTarget.style.background  = "rgba(10,30,25,0.95)";
            e.currentTarget.style.transform   = "translateY(-3px)";
            e.currentTarget.style.boxShadow   = "0 12px 40px rgba(0,0,0,0.3)";
          }}
          onMouseLeave={e => {
            e.currentTarget.style.borderColor = "rgba(20,200,130,0.15)";
            e.currentTarget.style.background  = "";
            e.currentTarget.style.transform   = "translateY(0)";
            e.currentTarget.style.boxShadow   = "";
          }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14 }}>
              <div style={{
                width: 38, height: 38, borderRadius: 10,
                background: "linear-gradient(135deg, #0a2a20, #0d3d2a)",
                border: "1px solid rgba(20,200,130,0.2)",
                display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
              }}>
                <svg viewBox="0 0 24 24" fill="none" width={16} height={16}>
                  <circle cx="12" cy="12" r="9" stroke="#14c882" strokeWidth="1.8"/>
                  <path d="M2 12h20M12 2c-2.5 3-4 6-4 10s1.5 7 4 10M12 2c2.5 3 4 6 4 10s-1.5 7-4 10" stroke="#14c882" strokeWidth="1.5" strokeLinecap="round"/>
                </svg>
              </div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: "#d0dcf0" }}>Live Site</div>
                <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#1a5a40", letterSpacing: "0.1em", marginTop: 2 }}>
                  PRODUCTION · LIVE
                </div>
              </div>
            </div>
            <div style={{ fontSize: 12, color: "#5a6f8f", lineHeight: 1.6 }}>
              Open the live DigiGrowth website as visitors see it.
            </div>
            <div style={{
              marginTop: 16, display: "inline-flex", alignItems: "center", gap: 6,
              fontSize: 11, color: "#14c882", fontWeight: 600,
            }}>
              Open Site <span style={{ fontSize: 13 }}>→</span>
            </div>
          </div>
        </a>

      </div>
    </div>
  );
}
