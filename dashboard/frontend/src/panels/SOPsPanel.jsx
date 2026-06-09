import React, { useState, useEffect, useCallback } from "react";
import ReactMarkdown from "react-markdown";

const EMPTY_DRAFT = { title: "", content: "", category: "General", visibility: "private" };

const mdComponents = {
  h1: ({ children }) => (
    <h1 style={{ fontSize: 18, fontWeight: 700, color: "#6ab0ff", margin: "0 0 10px", fontFamily: "'Space Grotesk', sans-serif", borderBottom: "1px solid rgba(58,123,213,0.2)", paddingBottom: 6 }}>{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 style={{ fontSize: 15, fontWeight: 600, color: "#a0c4ff", margin: "14px 0 6px", fontFamily: "'Space Grotesk', sans-serif" }}>{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 style={{ fontSize: 13, fontWeight: 600, color: "#c0d8ff", margin: "10px 0 4px", fontFamily: "'Space Grotesk', sans-serif" }}>{children}</h3>
  ),
  p: ({ children }) => (
    <p style={{ fontSize: 13, color: "#b8cce8", lineHeight: 1.75, margin: "0 0 10px" }}>{children}</p>
  ),
  ul: ({ children }) => <ul style={{ paddingLeft: 18, margin: "0 0 10px" }}>{children}</ul>,
  ol: ({ children }) => <ol style={{ paddingLeft: 18, margin: "0 0 10px" }}>{children}</ol>,
  li: ({ children }) => (
    <li style={{ fontSize: 13, color: "#b8cce8", lineHeight: 1.75, marginBottom: 3 }}>{children}</li>
  ),
  pre: ({ children }) => (
    <pre style={{ background: "rgba(0,0,0,0.35)", border: "1px solid rgba(58,123,213,0.2)", borderRadius: 6, padding: "10px 14px", overflow: "auto", margin: "0 0 10px", fontFamily: "'Share Tech Mono', monospace", fontSize: 12, color: "#b8cce8" }}>{children}</pre>
  ),
  code: ({ children, className }) => (
    <code style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 12, color: "#6ab0ff", background: "rgba(58,123,213,0.15)", padding: "1px 5px", borderRadius: 3 }} className={className}>{children}</code>
  ),
  blockquote: ({ children }) => (
    <blockquote style={{ borderLeft: "3px solid #3a7bd5", paddingLeft: 12, margin: "0 0 10px", color: "#8aaccc", fontStyle: "italic" }}>{children}</blockquote>
  ),
  hr: () => <hr style={{ border: "none", borderTop: "1px solid rgba(58,123,213,0.18)", margin: "14px 0" }} />,
  strong: ({ children }) => <strong style={{ color: "#d0e8ff", fontWeight: 700 }}>{children}</strong>,
  em: ({ children }) => <em style={{ color: "#b8cce8" }}>{children}</em>,
  a: ({ href, children }) => (
    <a href={href} style={{ color: "#3a7bd5", textDecoration: "underline" }} target="_blank" rel="noreferrer">{children}</a>
  ),
};

export default function SOPsPanel() {
  const [sops, setSops] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [draft, setDraft] = useState(EMPTY_DRAFT);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const fetchSOPs = useCallback(async () => {
    const r = await fetch("/api/sops");
    if (r.ok) setSops(await r.json());
  }, []);

  useEffect(() => { fetchSOPs(); }, [fetchSOPs]);

  const selectSOP = (sop) => {
    setSelectedId(sop.id);
    setDraft({ title: sop.title, content: sop.content, category: sop.category, visibility: sop.visibility });
    setSaved(false);
  };

  const newSOP = () => {
    setSelectedId(null);
    setDraft(EMPTY_DRAFT);
    setSaved(false);
  };

  const saveSOP = async () => {
    if (!draft.title.trim()) return;
    setSaving(true);
    try {
      if (selectedId) {
        await fetch(`/api/sops/${selectedId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(draft),
        });
      } else {
        const r = await fetch("/api/sops", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ...draft, sort_order: 0 }),
        });
        const created = await r.json();
        setSelectedId(created.id);
      }
      await fetchSOPs();
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  };

  const deleteSOP = async (id, e) => {
    e.stopPropagation();
    if (!window.confirm("Delete this SOP?")) return;
    await fetch(`/api/sops/${id}`, { method: "DELETE" });
    if (selectedId === id) {
      setSelectedId(null);
      setDraft(EMPTY_DRAFT);
    }
    await fetchSOPs();
  };

  // Group by category
  const grouped = sops.reduce((acc, sop) => {
    const cat = sop.category || "General";
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(sop);
    return acc;
  }, {});

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>

      {/* Header */}
      <div style={{
        padding: "18px 24px 14px",
        borderBottom: "1px solid rgba(58,123,213,0.12)",
        display: "flex", alignItems: "center", gap: 16, flexShrink: 0,
      }}>
        <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: 18, color: "#e8f0ff" }}>SOPs</span>
        <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80", letterSpacing: "0.14em" }}>
          STANDARD OPERATING PROCEDURES
        </span>
        <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          <button
            onClick={newSOP}
            style={{
              background: "linear-gradient(90deg, #2857a0, #3a7bd5)",
              border: "none", borderRadius: 6, color: "#fff",
              fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600,
              fontSize: 12, padding: "6px 14px", cursor: "pointer",
            }}
          >
            + New SOP
          </button>
        </div>
      </div>

      {/* Body: 3 columns */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>

        {/* Left: SOP list */}
        <div style={{
          width: 240, flexShrink: 0,
          borderRight: "1px solid rgba(58,123,213,0.1)",
          overflowY: "auto", padding: "12px 0",
        }}>
          {Object.keys(grouped).length === 0 && (
            <div style={{ padding: "20px 16px", fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a6a", textAlign: "center", letterSpacing: "0.1em" }}>
              NO SOPS YET
            </div>
          )}
          {Object.entries(grouped).map(([cat, items]) => (
            <div key={cat}>
              <div style={{
                padding: "8px 16px 4px",
                fontFamily: "'Share Tech Mono', monospace",
                fontSize: 9, color: "#3a5a80", letterSpacing: "0.14em", textTransform: "uppercase",
              }}>
                {cat}
              </div>
              {items.map((sop) => (
                <div
                  key={sop.id}
                  onClick={() => selectSOP(sop)}
                  style={{
                    display: "flex", alignItems: "center", gap: 6,
                    padding: "7px 16px",
                    cursor: "pointer",
                    background: selectedId === sop.id
                      ? "linear-gradient(90deg, rgba(40,87,160,0.35), rgba(58,123,213,0.2))"
                      : "transparent",
                    borderLeft: selectedId === sop.id ? "2px solid #3a7bd5" : "2px solid transparent",
                    transition: "background 0.15s",
                  }}
                >
                  {/* visibility dot */}
                  <span style={{
                    width: 6, height: 6, borderRadius: "50%", flexShrink: 0,
                    background: sop.visibility === "public" ? "#34d399" : "#6ab0ff",
                    opacity: 0.8,
                  }} />
                  <span style={{
                    flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                    fontFamily: "'Space Grotesk', sans-serif", fontSize: 12,
                    color: selectedId === sop.id ? "#e8f0ff" : "#7a9cc0",
                    fontWeight: selectedId === sop.id ? 600 : 400,
                  }}>
                    {sop.title}
                  </span>
                  <button
                    onClick={(e) => deleteSOP(sop.id, e)}
                    style={{
                      background: "none", border: "none", cursor: "pointer",
                      color: "#3a5a80", fontSize: 14, lineHeight: 1, padding: 0,
                      flexShrink: 0, opacity: 0,
                    }}
                    className="sop-delete-btn"
                    title="Delete"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          ))}
        </div>

        {/* Center: Editor */}
        <div style={{
          flex: 1, display: "flex", flexDirection: "column",
          borderRight: "1px solid rgba(58,123,213,0.1)",
          overflow: "hidden",
        }}>
          {/* Meta row */}
          <div style={{
            padding: "12px 16px",
            borderBottom: "1px solid rgba(58,123,213,0.08)",
            display: "flex", gap: 8, alignItems: "center", flexShrink: 0,
          }}>
            <input
              value={draft.title}
              onChange={(e) => setDraft((d) => ({ ...d, title: e.target.value }))}
              placeholder="SOP title..."
              style={{
                flex: 1,
                background: "rgba(255,255,255,0.04)", border: "1px solid rgba(58,123,213,0.2)",
                borderRadius: 6, padding: "6px 10px", color: "#e8f0ff",
                fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600, fontSize: 13,
                outline: "none",
              }}
            />
            <input
              value={draft.category}
              onChange={(e) => setDraft((d) => ({ ...d, category: e.target.value }))}
              placeholder="Category"
              style={{
                width: 110,
                background: "rgba(255,255,255,0.04)", border: "1px solid rgba(58,123,213,0.2)",
                borderRadius: 6, padding: "6px 10px", color: "#9ab8d8",
                fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, outline: "none",
              }}
            />
            {/* Visibility toggle */}
            <div style={{ display: "flex", borderRadius: 6, overflow: "hidden", border: "1px solid rgba(58,123,213,0.25)", flexShrink: 0 }}>
              {["private", "public"].map((v) => (
                <button
                  key={v}
                  onClick={() => setDraft((d) => ({ ...d, visibility: v }))}
                  style={{
                    padding: "5px 10px", border: "none", cursor: "pointer",
                    background: draft.visibility === v
                      ? v === "public" ? "rgba(52,211,153,0.25)" : "rgba(58,123,213,0.3)"
                      : "transparent",
                    color: draft.visibility === v
                      ? v === "public" ? "#34d399" : "#6ab0ff"
                      : "#3a5a80",
                    fontFamily: "'Space Grotesk', sans-serif", fontSize: 11, fontWeight: 600,
                    transition: "all 0.15s",
                    textTransform: "capitalize",
                  }}
                >
                  {v}
                </button>
              ))}
            </div>
          </div>

          {/* Textarea */}
          <textarea
            value={draft.content}
            onChange={(e) => setDraft((d) => ({ ...d, content: e.target.value }))}
            placeholder={"# SOP Title\n\n## Overview\n\nDescribe the procedure here...\n\n## Steps\n\n1. Step one\n2. Step two\n3. Step three"}
            style={{
              flex: 1, resize: "none",
              background: "transparent",
              border: "none", outline: "none",
              padding: "14px 18px",
              fontFamily: "'Share Tech Mono', monospace", fontSize: 12.5,
              color: "#b8cce8", lineHeight: 1.7,
            }}
          />

          {/* Save bar */}
          <div style={{
            padding: "10px 16px",
            borderTop: "1px solid rgba(58,123,213,0.08)",
            display: "flex", alignItems: "center", gap: 10, flexShrink: 0,
          }}>
            <button
              onClick={saveSOP}
              disabled={saving || !draft.title.trim()}
              style={{
                background: saving || !draft.title.trim()
                  ? "rgba(58,123,213,0.2)"
                  : "linear-gradient(90deg, #2857a0, #3a7bd5)",
                border: "none", borderRadius: 6, color: "#fff",
                fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600,
                fontSize: 12, padding: "7px 18px", cursor: saving || !draft.title.trim() ? "not-allowed" : "pointer",
                transition: "all 0.15s",
              }}
            >
              {saving ? "Saving..." : "Save SOP"}
            </button>
            {saved && (
              <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#34d399", letterSpacing: "0.1em" }}>
                SAVED
              </span>
            )}
            {selectedId === null && draft.title.trim() && (
              <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80", letterSpacing: "0.1em" }}>
                NEW SOP
              </span>
            )}
          </div>
        </div>

        {/* Right: Preview */}
        <div style={{
          flex: 1, overflow: "auto",
          padding: "16px 20px",
        }}>
          {draft.title && (
            <div style={{
              fontFamily: "'Share Tech Mono', monospace", fontSize: 9,
              color: "#3a5a80", letterSpacing: "0.14em", marginBottom: 14,
              display: "flex", gap: 10, alignItems: "center",
            }}>
              <span>PREVIEW</span>
              <span style={{
                color: draft.visibility === "public" ? "#34d399" : "#6ab0ff",
                background: draft.visibility === "public" ? "rgba(52,211,153,0.1)" : "rgba(58,123,213,0.1)",
                padding: "1px 6px", borderRadius: 3,
              }}>
                {draft.visibility.toUpperCase()}
              </span>
            </div>
          )}
          {!draft.title && !draft.content && (
            <div style={{
              display: "flex", alignItems: "center", justifyContent: "center",
              height: "100%",
              fontFamily: "'Share Tech Mono', monospace", fontSize: 10,
              color: "#1e3050", letterSpacing: "0.12em",
            }}>
              SELECT OR CREATE A SOP
            </div>
          )}
          <ReactMarkdown components={mdComponents}>
            {draft.content || ""}
          </ReactMarkdown>
        </div>
      </div>

      <style>{`
        .sop-delete-btn { opacity: 0 !important; transition: opacity 0.15s; }
        div:hover > .sop-delete-btn { opacity: 1 !important; }
      `}</style>
    </div>
  );
}
