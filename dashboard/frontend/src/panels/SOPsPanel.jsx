import React, { useState, useEffect, useCallback, useRef } from "react";
import ReactMarkdown from "react-markdown";
import rehypeRaw from "rehype-raw";

const EMPTY_DRAFT = { title: "", content: "", category: "General", visibility: "private" };

const CONTENT_PAD = "24px 36px";

// ── Markdown render components ───────────────────────────────────────────────
const md = {
  h1: ({ children }) => <h1 style={{ fontSize: 22, fontWeight: 700, color: "#6ab0ff", margin: "0 0 14px", fontFamily: "'Space Grotesk', sans-serif", borderBottom: "1px solid rgba(58,123,213,0.2)", paddingBottom: 8 }}>{children}</h1>,
  h2: ({ children }) => <h2 style={{ fontSize: 16, fontWeight: 600, color: "#a0c4ff", margin: "22px 0 8px", fontFamily: "'Space Grotesk', sans-serif" }}>{children}</h2>,
  h3: ({ children }) => <h3 style={{ fontSize: 14, fontWeight: 600, color: "#c0d8ff", margin: "16px 0 6px", fontFamily: "'Space Grotesk', sans-serif" }}>{children}</h3>,
  p:  ({ children }) => <p  style={{ fontSize: 13.5, color: "#b8cce8", lineHeight: 1.8, margin: "0 0 12px" }}>{children}</p>,
  ul: ({ children }) => <ul style={{ paddingLeft: 20, margin: "0 0 12px" }}>{children}</ul>,
  ol: ({ children }) => <ol style={{ paddingLeft: 20, margin: "0 0 12px" }}>{children}</ol>,
  li: ({ children }) => <li style={{ fontSize: 13.5, color: "#b8cce8", lineHeight: 1.8, marginBottom: 4 }}>{children}</li>,
  pre: ({ children }) => <pre style={{ background: "rgba(0,0,0,0.35)", border: "1px solid rgba(58,123,213,0.2)", borderRadius: 6, padding: "12px 16px", overflow: "auto", margin: "0 0 12px", fontFamily: "'Share Tech Mono', monospace", fontSize: 12, color: "#b8cce8" }}>{children}</pre>,
  code: ({ children, className }) => <code style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 12, color: "#6ab0ff", background: "rgba(58,123,213,0.15)", padding: "1px 5px", borderRadius: 3 }} className={className}>{children}</code>,
  blockquote: ({ children }) => <blockquote style={{ borderLeft: "3px solid #3a7bd5", paddingLeft: 14, margin: "0 0 12px", color: "#8aaccc", fontStyle: "italic" }}>{children}</blockquote>,
  hr: () => <hr style={{ border: "none", borderTop: "1px solid rgba(58,123,213,0.18)", margin: "20px 0" }} />,
  strong: ({ children }) => <strong style={{ color: "#d0e8ff", fontWeight: 700 }}>{children}</strong>,
  em:     ({ children }) => <em style={{ color: "#b8cce8" }}>{children}</em>,
  del:    ({ children }) => <del style={{ color: "#4a6a8a" }}>{children}</del>,
  a: ({ href, children }) => <a href={href} style={{ color: "#3a7bd5", textDecoration: "underline" }} target="_blank" rel="noreferrer">{children}</a>,
  table:  ({ children }) => <div style={{ overflowX: "auto", margin: "0 0 12px" }}><table style={{ borderCollapse: "collapse", width: "100%", fontSize: 13 }}>{children}</table></div>,
  th: ({ children }) => <th style={{ padding: "6px 12px", background: "rgba(58,123,213,0.2)", color: "#a0c4ff", fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600, textAlign: "left", border: "1px solid rgba(58,123,213,0.2)" }}>{children}</th>,
  td: ({ children }) => <td style={{ padding: "6px 12px", color: "#b8cce8", border: "1px solid rgba(58,123,213,0.12)" }}>{children}</td>,
  span: ({ style, children }) => <span style={style}>{children}</span>,
};

// ── Formatting toolbar ───────────────────────────────────────────────────────
const COLORS = [
  { hex: "#e8f0ff", label: "White" },
  { hex: "#6ab0ff", label: "Blue" },
  { hex: "#34d399", label: "Green" },
  { hex: "#f59e0b", label: "Amber" },
  { hex: "#ef4444", label: "Red" },
  { hex: "#a78bfa", label: "Purple" },
];

const FONT_SIZES = [
  { label: "Small",  value: "11px" },
  { label: "Normal", value: "13.5px" },
  { label: "Large",  value: "17px" },
  { label: "XL",     value: "22px" },
];

function FormatBar({ taRef, setDraft }) {
  const [showSizes, setShowSizes] = useState(false);

  const wrap = (before, after = before) => {
    const el = taRef.current;
    if (!el) return;
    const s = el.selectionStart, e = el.selectionEnd, v = el.value;
    const sel = v.slice(s, e);
    const next = v.slice(0, s) + before + sel + after + v.slice(e);
    setDraft(d => ({ ...d, content: next }));
    requestAnimationFrame(() => { el.focus(); el.setSelectionRange(s + before.length, e + before.length); });
  };

  const heading = (level) => {
    const el = taRef.current;
    if (!el) return;
    const s = el.selectionStart, v = el.value;
    const lineStart = v.lastIndexOf("\n", s - 1) + 1;
    const prefix = "#".repeat(level) + " ";
    const existing = v.slice(lineStart).match(/^#+\s/);
    const next = existing
      ? v.slice(0, lineStart) + prefix + v.slice(lineStart + existing[0].length)
      : v.slice(0, lineStart) + prefix + v.slice(lineStart);
    setDraft(d => ({ ...d, content: next }));
    requestAnimationFrame(() => el.focus());
  };

  const insertLine = (text) => {
    const el = taRef.current;
    if (!el) return;
    const s = el.selectionStart, v = el.value;
    const lineStart = v.lastIndexOf("\n", s - 1) + 1;
    const next = v.slice(0, lineStart) + text + v.slice(lineStart);
    setDraft(d => ({ ...d, content: next }));
    requestAnimationFrame(() => { el.focus(); el.setSelectionRange(lineStart + text.length, lineStart + text.length); });
  };

  const applyColor = (hex) => wrap(`<span style="color: ${hex}">`, "</span>");
  const applySize  = (px)  => wrap(`<span style="font-size: ${px}">`, "</span>");

  const btn = (label, onClick, extra = {}) => (
    <button
      key={label}
      onClick={onClick}
      title={label}
      style={{
        background: "rgba(255,255,255,0.04)",
        border: "1px solid rgba(58,123,213,0.15)",
        borderRadius: 5, color: "#7a9cc0",
        fontFamily: "'Space Grotesk', sans-serif",
        fontSize: 11, fontWeight: 600,
        padding: "3px 8px", cursor: "pointer",
        lineHeight: 1.4, minWidth: 28,
        transition: "all 0.1s",
        ...extra,
      }}
    >
      {label}
    </button>
  );

  const sep = () => <div style={{ width: 1, height: 14, background: "rgba(58,123,213,0.2)", margin: "0 2px", flexShrink: 0 }} />;

  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 4,
      padding: "8px 36px", flexShrink: 0, flexWrap: "wrap",
      borderBottom: "1px solid rgba(58,123,213,0.1)",
      background: "rgba(0,0,0,0.15)",
    }}>
      {btn("H1", () => heading(1))}
      {btn("H2", () => heading(2))}
      {btn("H3", () => heading(3))}
      {sep()}
      {btn("B",  () => wrap("**"),     { fontWeight: 900, color: "#d0e8ff" })}
      {btn("I",  () => wrap("*"),      { fontStyle: "italic", color: "#b8cce8" })}
      {btn("S",  () => wrap("~~"),     { textDecoration: "line-through", color: "#6a8aaa" })}
      {sep()}
      {/* Font size dropdown */}
      <div style={{ position: "relative" }}>
        <button
          onClick={() => setShowSizes(s => !s)}
          style={{
            background: showSizes ? "rgba(58,123,213,0.2)" : "rgba(255,255,255,0.04)",
            border: "1px solid rgba(58,123,213,0.15)",
            borderRadius: 5, color: "#7a9cc0",
            fontFamily: "'Space Grotesk', sans-serif",
            fontSize: 11, fontWeight: 600,
            padding: "3px 8px", cursor: "pointer",
            lineHeight: 1.4,
          }}
        >
          Aa ▾
        </button>
        {showSizes && (
          <div style={{
            position: "absolute", top: "calc(100% + 4px)", left: 0,
            background: "#0d1830", border: "1px solid rgba(58,123,213,0.25)",
            borderRadius: 6, zIndex: 100, overflow: "hidden", minWidth: 90,
          }}>
            {FONT_SIZES.map(({ label, value }) => (
              <button
                key={label}
                onClick={() => { applySize(value); setShowSizes(false); }}
                style={{
                  display: "block", width: "100%", textAlign: "left",
                  background: "none", border: "none", cursor: "pointer",
                  padding: "6px 12px", color: "#9ab8d8",
                  fontFamily: "'Space Grotesk', sans-serif",
                  fontSize: value, lineHeight: 1.3,
                  transition: "background 0.1s",
                }}
                onMouseEnter={e => e.currentTarget.style.background = "rgba(58,123,213,0.15)"}
                onMouseLeave={e => e.currentTarget.style.background = "none"}
              >
                {label}
              </button>
            ))}
          </div>
        )}
      </div>
      {sep()}
      {/* Color swatches */}
      {COLORS.map(({ hex, label }) => (
        <button
          key={hex}
          title={label}
          onClick={() => applyColor(hex)}
          style={{
            width: 14, height: 14, borderRadius: "50%",
            background: hex, border: "1.5px solid rgba(255,255,255,0.15)",
            cursor: "pointer", padding: 0, flexShrink: 0,
          }}
        />
      ))}
      {sep()}
      {btn("• List", () => insertLine("- "))}
      {btn("1. List", () => insertLine("1. "))}
      {btn("——", () => wrap("\n---\n"), { letterSpacing: 1 })}
    </div>
  );
}

// ── Shared header strip ──────────────────────────────────────────────────────
function SOPHeader({ draft, setDraft, editing, onEdit, onSave, onCancel, saving, savedFlash }) {
  const visBadge = (vis) => (
    <span style={{
      fontFamily: "'Share Tech Mono', monospace", fontSize: 10, letterSpacing: "0.08em",
      color: vis === "public" ? "#34d399" : "#6ab0ff",
      background: vis === "public" ? "rgba(52,211,153,0.1)" : "rgba(58,123,213,0.1)",
      padding: "2px 8px", borderRadius: 3,
    }}>
      {vis.toUpperCase()}
    </span>
  );

  return (
    <div style={{
      padding: "14px 36px",
      borderBottom: "1px solid rgba(58,123,213,0.1)",
      display: "flex", alignItems: "center", gap: 10, flexShrink: 0,
      minHeight: 52,
    }}>
      {editing ? (
        <>
          <input
            value={draft.title}
            onChange={e => setDraft(d => ({ ...d, title: e.target.value }))}
            placeholder="SOP title..."
            autoFocus
            style={{
              flex: 1, background: "rgba(255,255,255,0.04)",
              border: "1px solid rgba(58,123,213,0.2)", borderRadius: 6,
              padding: "5px 10px", color: "#e8f0ff",
              fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700,
              fontSize: 15, outline: "none",
            }}
          />
          <input
            value={draft.category}
            onChange={e => setDraft(d => ({ ...d, category: e.target.value }))}
            placeholder="Category"
            style={{
              width: 100, background: "rgba(255,255,255,0.04)",
              border: "1px solid rgba(58,123,213,0.2)", borderRadius: 6,
              padding: "5px 10px", color: "#9ab8d8",
              fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, outline: "none",
            }}
          />
          <div style={{ display: "flex", borderRadius: 6, overflow: "hidden", border: "1px solid rgba(58,123,213,0.25)", flexShrink: 0 }}>
            {["private", "public"].map(v => (
              <button
                key={v}
                onClick={() => setDraft(d => ({ ...d, visibility: v }))}
                style={{
                  padding: "4px 10px", border: "none", cursor: "pointer",
                  background: draft.visibility === v
                    ? v === "public" ? "rgba(52,211,153,0.25)" : "rgba(58,123,213,0.3)"
                    : "transparent",
                  color: draft.visibility === v
                    ? v === "public" ? "#34d399" : "#6ab0ff"
                    : "#3a5a80",
                  fontFamily: "'Space Grotesk', sans-serif", fontSize: 11, fontWeight: 600,
                  textTransform: "capitalize", transition: "all 0.15s",
                }}
              >
                {v}
              </button>
            ))}
          </div>
          <button onClick={onCancel} style={{ background: "transparent", border: "1px solid rgba(58,123,213,0.2)", borderRadius: 6, color: "#4a6a8a", fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600, fontSize: 12, padding: "5px 12px", cursor: "pointer" }}>
            Cancel
          </button>
          <button
            onClick={onSave}
            disabled={saving || !draft.title.trim()}
            style={{
              background: saving || !draft.title.trim() ? "rgba(58,123,213,0.2)" : "linear-gradient(90deg, #2857a0, #3a7bd5)",
              border: "none", borderRadius: 6, color: "#fff",
              fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600,
              fontSize: 12, padding: "5px 16px",
              cursor: saving || !draft.title.trim() ? "not-allowed" : "pointer",
            }}
          >
            {saving ? "Saving..." : "Save"}
          </button>
        </>
      ) : (
        <>
          <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: 15, color: "#e8f0ff", flex: 1 }}>
            {draft.title}
          </span>
          {savedFlash && <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#34d399", letterSpacing: "0.1em" }}>SAVED</span>}
          <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80", letterSpacing: "0.08em" }}>{draft.category}</span>
          {visBadge(draft.visibility)}
          <button
            onClick={onEdit}
            style={{
              background: "rgba(58,123,213,0.12)", border: "1px solid rgba(58,123,213,0.25)",
              borderRadius: 6, color: "#6ab0ff",
              fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600,
              fontSize: 12, padding: "5px 14px", cursor: "pointer",
            }}
          >
            Edit
          </button>
        </>
      )}
    </div>
  );
}

// ── Main panel ───────────────────────────────────────────────────────────────
export default function SOPsPanel() {
  const [sops, setSops] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [committed, setCommitted] = useState(EMPTY_DRAFT);
  const [draft, setDraft] = useState(EMPTY_DRAFT);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);
  const taRef = useRef(null);

  const fetchSOPs = useCallback(async () => {
    const r = await fetch("/api/sops");
    if (r.ok) setSops(await r.json());
  }, []);

  useEffect(() => { fetchSOPs(); }, [fetchSOPs]);

  const selectSOP = (sop) => {
    const data = { title: sop.title, content: sop.content, category: sop.category, visibility: sop.visibility };
    setSelectedId(sop.id);
    setCommitted(data);
    setDraft(data);
    setEditing(false);
  };

  const newSOP = () => {
    setSelectedId(null);
    setCommitted(EMPTY_DRAFT);
    setDraft(EMPTY_DRAFT);
    setEditing(true);
  };

  const cancelEdit = () => {
    if (!selectedId) { setSelectedId(null); setCommitted(EMPTY_DRAFT); setDraft(EMPTY_DRAFT); }
    else setDraft({ ...committed });
    setEditing(false);
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
      setCommitted({ ...draft });
      setEditing(false);
      setSavedFlash(true);
      setTimeout(() => setSavedFlash(false), 2000);
      await fetchSOPs();
    } finally {
      setSaving(false);
    }
  };

  const deleteSOP = async (id, e) => {
    e.stopPropagation();
    if (!window.confirm("Delete this SOP?")) return;
    await fetch(`/api/sops/${id}`, { method: "DELETE" });
    if (selectedId === id) { setSelectedId(null); setCommitted(EMPTY_DRAFT); setDraft(EMPTY_DRAFT); setEditing(false); }
    await fetchSOPs();
  };

  const grouped = sops.reduce((acc, sop) => {
    const cat = sop.category || "General";
    (acc[cat] = acc[cat] || []).push(sop);
    return acc;
  }, {});

  const hasContent = committed.title || committed.content;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>

      {/* Panel header */}
      <div style={{ padding: "18px 24px 14px", borderBottom: "1px solid rgba(58,123,213,0.12)", display: "flex", alignItems: "center", gap: 16, flexShrink: 0 }}>
        <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: 18, color: "#e8f0ff" }}>SOPs</span>
        <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80", letterSpacing: "0.14em" }}>STANDARD OPERATING PROCEDURES</span>
        <div style={{ marginLeft: "auto" }}>
          <button onClick={newSOP} style={{ background: "linear-gradient(90deg, #2857a0, #3a7bd5)", border: "none", borderRadius: 6, color: "#fff", fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600, fontSize: 12, padding: "6px 14px", cursor: "pointer" }}>
            + New SOP
          </button>
        </div>
      </div>

      {/* Body */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>

        {/* Left: list */}
        <div style={{ width: 240, flexShrink: 0, borderRight: "1px solid rgba(58,123,213,0.1)", overflowY: "auto", padding: "12px 0" }}>
          {Object.keys(grouped).length === 0 && (
            <div style={{ padding: "20px 16px", fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a6a", textAlign: "center", letterSpacing: "0.1em" }}>NO SOPS YET</div>
          )}
          {Object.entries(grouped).map(([cat, items]) => (
            <div key={cat}>
              <div style={{ padding: "8px 16px 4px", fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80", letterSpacing: "0.14em", textTransform: "uppercase" }}>{cat}</div>
              {items.map(sop => (
                <div
                  key={sop.id}
                  onClick={() => selectSOP(sop)}
                  style={{ display: "flex", alignItems: "center", gap: 6, padding: "7px 16px", cursor: "pointer", background: selectedId === sop.id ? "linear-gradient(90deg, rgba(40,87,160,0.35), rgba(58,123,213,0.2))" : "transparent", borderLeft: selectedId === sop.id ? "2px solid #3a7bd5" : "2px solid transparent", transition: "background 0.15s" }}
                >
                  <span style={{ width: 6, height: 6, borderRadius: "50%", flexShrink: 0, background: sop.visibility === "public" ? "#34d399" : "#6ab0ff", opacity: 0.8 }} />
                  <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, color: selectedId === sop.id ? "#e8f0ff" : "#7a9cc0", fontWeight: selectedId === sop.id ? 600 : 400 }}>{sop.title}</span>
                  <button onClick={e => deleteSOP(sop.id, e)} className="sop-del" title="Delete" style={{ background: "none", border: "none", cursor: "pointer", color: "#3a5a80", fontSize: 14, lineHeight: 1, padding: 0, flexShrink: 0 }}>×</button>
                </div>
              ))}
            </div>
          ))}
        </div>

        {/* Right: SOP header + content (both modes share this container) */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>

          {/* Shared header */}
          {(hasContent || editing) && (
            <SOPHeader
              draft={draft}
              setDraft={setDraft}
              editing={editing}
              onEdit={() => { setDraft({ ...committed }); setEditing(true); }}
              onSave={saveSOP}
              onCancel={cancelEdit}
              saving={saving}
              savedFlash={savedFlash}
            />
          )}

          {/* Format toolbar — edit mode only */}
          {editing && <FormatBar taRef={taRef} setDraft={setDraft} />}

          {/* Content area */}
          <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
            {editing ? (
              /* Edit: textarea with same padding as preview */
              <textarea
                ref={taRef}
                value={draft.content}
                onChange={e => setDraft(d => ({ ...d, content: e.target.value }))}
                placeholder={"# SOP Title\n\n## Overview\n\nDescribe the procedure here...\n\n## Steps\n\n1. Step one\n2. Step two\n3. Step three"}
                style={{
                  flex: 1, resize: "none",
                  background: "transparent", border: "none", outline: "none",
                  padding: CONTENT_PAD,
                  fontFamily: "'Share Tech Mono', monospace", fontSize: 13,
                  color: "#b8cce8", lineHeight: 1.8,
                }}
              />
            ) : (
              /* View: rendered markdown with same padding */
              <div style={{ flex: 1, overflowY: "auto", padding: CONTENT_PAD }}>
                {!hasContent ? (
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1e3050", letterSpacing: "0.12em" }}>
                    SELECT OR CREATE A SOP
                  </div>
                ) : (
                  <ReactMarkdown components={md} rehypePlugins={[rehypeRaw]}>
                    {committed.content || ""}
                  </ReactMarkdown>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      <style>{`
        .sop-del { opacity: 0 !important; transition: opacity 0.15s; }
        div:hover > .sop-del { opacity: 1 !important; }
      `}</style>
    </div>
  );
}
