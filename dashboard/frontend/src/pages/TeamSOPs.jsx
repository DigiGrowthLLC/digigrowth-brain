import React, { useState, useEffect } from "react";
import { marked } from "marked";

function isMarkdown(str) {
  return /^#{1,6} |\*\*[^*]|\*[^*\n]|^- |\n- |\d+\. /m.test(str || "");
}

function toHTML(str) {
  if (!str) return "";
  if (str.trimStart().startsWith("<")) return str;
  if (isMarkdown(str)) return marked.parse(str);
  return str;
}

const PROSE_CSS = `
  .sop-prose { font-family: 'Space Grotesk', sans-serif; font-size: 13.5px; color: #b8cce8; line-height: 1.8; }
  .sop-prose h1 { font-size: 22px; font-weight: 700; color: #6ab0ff; margin: 0 0 14px;
    border-bottom: 1px solid rgba(58,123,213,0.2); padding-bottom: 8px; }
  .sop-prose h2 { font-size: 16px; font-weight: 600; color: #a0c4ff; margin: 22px 0 8px; }
  .sop-prose h3 { font-size: 14px; font-weight: 600; color: #c0d8ff; margin: 16px 0 6px; }
  .sop-prose p  { font-size: 13.5px; color: #b8cce8; line-height: 1.8; margin: 0 0 12px; }
  .sop-prose ul { padding-left: 20px; margin: 0 0 12px; }
  .sop-prose ol { padding-left: 20px; margin: 0 0 12px; }
  .sop-prose li { font-size: 13.5px; color: #b8cce8; line-height: 1.8; margin-bottom: 4px; }
  .sop-prose strong { color: #d0e8ff; font-weight: 700; }
  .sop-prose em  { color: #b8cce8; font-style: italic; }
  .sop-prose s   { color: #4a6a8a; }
  .sop-prose hr  { border: none; border-top: 1px solid rgba(58,123,213,0.18); margin: 20px 0; }
  .sop-prose blockquote { border-left: 3px solid #3a7bd5; padding-left: 14px;
    margin: 0 0 12px; color: #8aaccc; font-style: italic; }
  .sop-prose code { font-family: 'Share Tech Mono', monospace; font-size: 12px;
    color: #6ab0ff; background: rgba(58,123,213,0.15); padding: 1px 5px; border-radius: 3px; }
  .sop-prose pre { background: rgba(0,0,0,0.35); border: 1px solid rgba(58,123,213,0.2);
    border-radius: 6px; padding: 12px 16px; overflow: auto; margin: 0 0 12px; }
  .sop-prose pre code { background: none; padding: 0; color: #b8cce8; }
  .sop-prose a { color: #3a7bd5; text-decoration: underline; }
`;

function SOPCard({ sop }) {
  const [open, setOpen] = useState(false);

  return (
    <div style={{
      background: "rgba(255,255,255,0.03)",
      border: "1px solid rgba(58,123,213,0.15)",
      borderRadius: 10, overflow: "hidden", marginBottom: 10,
    }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: "100%", textAlign: "left",
          background: "none", border: "none", cursor: "pointer",
          padding: "14px 18px", display: "flex", alignItems: "center", gap: 12,
        }}
      >
        <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600, fontSize: 14, color: "#d0e8ff", flex: 1 }}>
          {sop.title}
        </span>
        <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: open ? "#6ab0ff" : "#3a5a80", letterSpacing: "0.08em", transition: "color 0.15s" }}>
          {open ? "CLOSE ▲" : "READ ▼"}
        </span>
      </button>
      {open && (
        <div style={{ padding: "0 18px 16px", borderTop: "1px solid rgba(58,123,213,0.1)", paddingTop: 14 }}>
          <div className="sop-prose" dangerouslySetInnerHTML={{ __html: toHTML(sop.content || "") }} />
        </div>
      )}
    </div>
  );
}

export default function TeamSOPs() {
  const [sops, setSops] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/public/sops")
      .then(r => r.json())
      .then(data => { setSops(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const grouped = sops.reduce((acc, sop) => {
    const cat = sop.category || "General";
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(sop);
    return acc;
  }, {});

  return (
    <div style={{
      minHeight: "100vh",
      background: "#090f26",
      backgroundImage: "radial-gradient(ellipse at 20% 50%, rgba(40,87,160,0.08) 0%, transparent 60%), radial-gradient(ellipse at 80% 20%, rgba(58,123,213,0.05) 0%, transparent 50%)",
      fontFamily: "'Space Grotesk', sans-serif",
    }}>
      <style>{PROSE_CSS}</style>
      <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Share+Tech+Mono&display=swap" rel="stylesheet" />

      <div style={{ borderBottom: "1px solid rgba(58,123,213,0.15)", padding: "20px 40px", display: "flex", alignItems: "center", gap: 16 }}>
        <div style={{ width: 32, height: 32, background: "linear-gradient(135deg, #1a3a6b 0%, #2857a0 100%)", borderRadius: 8, border: "1px solid rgba(58,123,213,0.3)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
          <svg viewBox="0 0 16 16" fill="none" width={13} height={13}>
            <rect x="2" y="1" width="12" height="14" rx="1.5" stroke="#6ab0ff" strokeWidth="1.4"/>
            <path d="M5 5h6M5 8h6M5 11h4" stroke="#6ab0ff" strokeWidth="1.2" strokeLinecap="round"/>
          </svg>
        </div>
        <div>
          <div style={{ fontWeight: 700, fontSize: 15, color: "#e8f0ff" }}>DigiGrowth</div>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80", letterSpacing: "0.14em" }}>TEAM PROCEDURES</div>
        </div>
      </div>

      <div style={{ maxWidth: 760, margin: "0 auto", padding: "36px 24px" }}>
        {loading && (
          <div style={{ textAlign: "center", padding: 60, fontFamily: "'Share Tech Mono', monospace", fontSize: 11, color: "#2a4a6a", letterSpacing: "0.12em" }}>
            LOADING...
          </div>
        )}
        {!loading && sops.length === 0 && (
          <div style={{ textAlign: "center", padding: 60, fontFamily: "'Share Tech Mono', monospace", fontSize: 11, color: "#2a4a6a", letterSpacing: "0.12em" }}>
            NO PUBLIC SOPS YET
          </div>
        )}
        {Object.entries(grouped).map(([cat, items]) => (
          <div key={cat} style={{ marginBottom: 32 }}>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80", letterSpacing: "0.16em", textTransform: "uppercase", marginBottom: 12, paddingBottom: 8, borderBottom: "1px solid rgba(58,123,213,0.1)" }}>
              {cat}
            </div>
            {items.map(sop => <SOPCard key={sop.id} sop={sop} />)}
          </div>
        ))}
      </div>
    </div>
  );
}
