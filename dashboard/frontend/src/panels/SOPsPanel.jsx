import React, { useState, useEffect, useCallback, useRef } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { Color } from "@tiptap/extension-color";
import TextStyle from "@tiptap/extension-text-style";
import Link from "@tiptap/extension-link";
import Table from "@tiptap/extension-table";
import TableRow from "@tiptap/extension-table-row";
import TableHeader from "@tiptap/extension-table-header";
import TableCell from "@tiptap/extension-table-cell";
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
  .sop-prose {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 13.5px;
    color: #b8cce8;
    line-height: 1.8;
    min-height: 200px;
    outline: none;
  }
  .sop-prose:focus { outline: none; }
  .sop-prose.ProseMirror { outline: none; }
  .sop-prose.ProseMirror p.is-editor-empty:first-child::before {
    content: 'Start writing your SOP...';
    float: left; color: #2a4a6a;
    pointer-events: none; height: 0;
  }
  .sop-prose h1 {
    font-size: 22px; font-weight: 700; color: #6ab0ff;
    margin: 0 0 14px;
    border-bottom: 1px solid rgba(58,123,213,0.2);
    padding-bottom: 8px;
    font-family: 'Space Grotesk', sans-serif;
  }
  .sop-prose h2 {
    font-size: 16px; font-weight: 600; color: #a0c4ff;
    margin: 22px 0 8px;
    font-family: 'Space Grotesk', sans-serif;
  }
  .sop-prose h3 {
    font-size: 14px; font-weight: 600; color: #c0d8ff;
    margin: 16px 0 6px;
    font-family: 'Space Grotesk', sans-serif;
  }
  .sop-prose p { font-size: 13.5px; line-height: 1.8; margin: 0 0 12px; }
  .sop-prose ul { padding-left: 20px; margin: 0 0 12px; }
  .sop-prose ol { padding-left: 20px; margin: 0 0 12px; }
  .sop-prose li { font-size: 13.5px; line-height: 1.8; margin-bottom: 4px; }
  .sop-prose strong { font-weight: 700; }
  .sop-prose em { font-style: italic; }
  .sop-prose s { opacity: 0.5; }
  .sop-prose hr { border: none; border-top: 1px solid rgba(58,123,213,0.18); margin: 20px 0; }
  .sop-prose blockquote {
    border-left: 3px solid #3a7bd5; padding-left: 14px;
    margin: 0 0 12px; color: #8aaccc; font-style: italic;
  }
  .sop-prose code {
    font-family: 'Share Tech Mono', monospace; font-size: 12px;
    color: #6ab0ff; background: rgba(58,123,213,0.15);
    padding: 1px 5px; border-radius: 3px;
  }
  .sop-prose pre {
    background: rgba(0,0,0,0.35); border: 1px solid rgba(58,123,213,0.2);
    border-radius: 6px; padding: 12px 16px; overflow: auto; margin: 0 0 12px;
  }
  .sop-prose pre code { background: none; padding: 0; color: #b8cce8; }
  .sop-prose a { color: #3a7bd5; text-decoration: underline; cursor: pointer; }
  .sop-prose a:hover { color: #6ab0ff; }
  .sop-prose .tableWrapper { overflow-x: auto; margin: 0 0 12px; }
  .sop-prose table { border-collapse: collapse; width: 100%; font-size: 13px; }
  .sop-prose th {
    padding: 6px 12px; background: rgba(58,123,213,0.2); color: #a0c4ff;
    font-weight: 600; text-align: left; border: 1px solid rgba(58,123,213,0.25); min-width: 80px;
  }
  .sop-prose td { padding: 6px 12px; color: #b8cce8; border: 1px solid rgba(58,123,213,0.12); min-width: 80px; }
  .sop-prose .selectedCell { background: rgba(58,123,213,0.15) !important; }
  .sop-prose .column-resize-handle {
    position: absolute; right: -2px; top: 0; bottom: 0;
    width: 4px; background: rgba(58,123,213,0.4); pointer-events: none;
  }
  .sop-prose .resize-cursor { cursor: col-resize; }
  .tiptap { height: 100%; }
`;

const COLORS = [
  { hex: "#e8f0ff", label: "White" },
  { hex: "#6ab0ff", label: "Blue" },
  { hex: "#34d399", label: "Green" },
  { hex: "#f59e0b", label: "Amber" },
  { hex: "#ef4444", label: "Red" },
  { hex: "#a78bfa", label: "Purple" },
];

// ── Toolbar ──────────────────────────────────────────────────────────────────
function FormatBar({ editor }) {
  const [linkBarOpen, setLinkBarOpen] = useState(false);
  const [linkUrl, setLinkUrl] = useState("");
  const linkInputRef = useRef(null);
  const savedRange = useRef(null);

  if (!editor) return null;

  const Btn = ({ label, action, active = false, style: extra = {} }) => (
    <button
      title={label}
      onMouseDown={e => { e.preventDefault(); action(); }}
      style={{
        background: active ? "rgba(58,123,213,0.3)" : "rgba(255,255,255,0.04)",
        border: `1px solid ${active ? "rgba(58,123,213,0.5)" : "rgba(58,123,213,0.15)"}`,
        borderRadius: 5, color: active ? "#6ab0ff" : "#7a9cc0",
        fontFamily: "'Space Grotesk', sans-serif",
        fontSize: 11, fontWeight: 600,
        padding: "3px 8px", cursor: "pointer", lineHeight: 1.4, minWidth: 28,
        ...extra,
      }}
    >{label}</button>
  );

  const Sep = () => (
    <div style={{ width: 1, height: 14, background: "rgba(58,123,213,0.2)", margin: "0 2px", flexShrink: 0 }} />
  );

  const openLinkBar = (e) => {
    e.preventDefault();
    if (editor.isActive("link")) {
      editor.chain().focus().unsetLink().run();
      return;
    }
    const { from, to } = editor.state.selection;
    if (from === to) return;
    savedRange.current = { from, to };
    setLinkUrl("");
    setLinkBarOpen(true);
    requestAnimationFrame(() => linkInputRef.current?.focus());
  };

  const applyLink = () => {
    const href = linkUrl.trim();
    const range = savedRange.current;
    setLinkBarOpen(false);
    savedRange.current = null;
    setLinkUrl("");
    if (!href || !range) { editor.commands.focus(); return; }
    editor
      .chain()
      .setTextSelection({ from: range.from, to: range.to })
      .setLink({ href: href.startsWith("http") ? href : "https://" + href, target: "_blank" })
      .run();
  };

  const cancelLink = () => {
    setLinkBarOpen(false);
    savedRange.current = null;
    setLinkUrl("");
    editor.commands.focus();
  };

  const inTable = editor.isActive("table");
  const linkActive = editor.isActive("link");

  return (
    <div style={{ flexShrink: 0, borderBottom: "1px solid rgba(58,123,213,0.1)", background: "rgba(0,0,0,0.15)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 4, padding: "8px 36px", flexWrap: "wrap" }}>
        <Btn label="H1" action={() => editor.chain().focus().toggleHeading({ level: 1 }).run()} active={editor.isActive("heading", { level: 1 })} />
        <Btn label="H2" action={() => editor.chain().focus().toggleHeading({ level: 2 }).run()} active={editor.isActive("heading", { level: 2 })} />
        <Btn label="H3" action={() => editor.chain().focus().toggleHeading({ level: 3 }).run()} active={editor.isActive("heading", { level: 3 })} />
        <Sep />
        <Btn label="B" action={() => editor.chain().focus().toggleBold().run()} active={editor.isActive("bold")} style={{ fontWeight: 900 }} />
        <Btn label="I" action={() => editor.chain().focus().toggleItalic().run()} active={editor.isActive("italic")} style={{ fontStyle: "italic" }} />
        <Btn label="S" action={() => editor.chain().focus().toggleStrike().run()} active={editor.isActive("strike")} style={{ textDecoration: "line-through" }} />
        <Sep />
        <Btn label="• List"  action={() => editor.chain().focus().toggleBulletList().run()}  active={editor.isActive("bulletList")} />
        <Btn label="1. List" action={() => editor.chain().focus().toggleOrderedList().run()} active={editor.isActive("orderedList")} />
        <Btn label="——"      action={() => editor.chain().focus().setHorizontalRule().run()} />
        <Sep />
        <button
          onMouseDown={openLinkBar}
          title={linkActive ? "Remove link" : "Add link — select text first"}
          style={{
            background: linkActive || linkBarOpen ? "rgba(58,123,213,0.3)" : "rgba(255,255,255,0.04)",
            border: `1px solid ${linkActive || linkBarOpen ? "rgba(58,123,213,0.5)" : "rgba(58,123,213,0.15)"}`,
            borderRadius: 5, color: linkActive || linkBarOpen ? "#6ab0ff" : "#7a9cc0",
            fontSize: 13, padding: "2px 7px", cursor: "pointer", lineHeight: 1.4,
          }}
        >🔗</button>
        <Sep />
        <Btn label="⊞ Table" action={() => editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()} />
        {inTable && <Btn label="+Row" action={() => editor.chain().focus().addRowAfter().run()} />}
        {inTable && <Btn label="+Col" action={() => editor.chain().focus().addColumnAfter().run()} />}
        {inTable && <Btn label="-Row" action={() => editor.chain().focus().deleteRow().run()} />}
        {inTable && <Btn label="-Col" action={() => editor.chain().focus().deleteColumn().run()} />}
        {inTable && <Btn label="Del Table" action={() => editor.chain().focus().deleteTable().run()} style={{ color: "#dc3c3c" }} />}
        <Sep />
        {COLORS.map(({ hex, label }) => (
          <button
            key={hex}
            title={`Color: ${label}`}
            onMouseDown={e => { e.preventDefault(); editor.chain().focus().setColor(hex).run(); }}
            style={{
              width: 16, height: 16, borderRadius: "50%", background: hex,
              border: editor.isActive("textStyle", { color: hex }) ? "2.5px solid #fff" : "1.5px solid rgba(255,255,255,0.2)",
              cursor: "pointer", padding: 0, flexShrink: 0,
            }}
          />
        ))}
        <button
          title="Reset text color"
          onMouseDown={e => { e.preventDefault(); editor.chain().focus().unsetColor().run(); }}
          style={{
            background: "rgba(255,255,255,0.04)", border: "1px solid rgba(58,123,213,0.15)",
            borderRadius: 5, color: "#7a9cc0", fontSize: 10, padding: "3px 6px", cursor: "pointer",
          }}
        >✕</button>
      </div>

      {linkBarOpen && (
        <div style={{
          display: "flex", alignItems: "center", gap: 8,
          padding: "6px 36px 8px",
          background: "rgba(58,123,213,0.06)",
          borderTop: "1px solid rgba(58,123,213,0.1)",
        }}>
          <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 11, color: "#6ab0ff", whiteSpace: "nowrap" }}>
            Link URL:
          </span>
          <input
            ref={linkInputRef}
            value={linkUrl}
            onChange={e => setLinkUrl(e.target.value)}
            onKeyDown={e => {
              if (e.key === "Enter") { e.preventDefault(); applyLink(); }
              if (e.key === "Escape") cancelLink();
            }}
            placeholder="https://example.com"
            style={{
              flex: 1, background: "rgba(255,255,255,0.06)",
              border: "1px solid rgba(58,123,213,0.3)", borderRadius: 5,
              color: "#e8f0ff", fontFamily: "'Space Grotesk', sans-serif",
              fontSize: 12, padding: "5px 10px", outline: "none",
            }}
          />
          <button
            onClick={applyLink}
            style={{
              background: "linear-gradient(90deg, #2857a0, #3a7bd5)", border: "none",
              borderRadius: 5, color: "#fff",
              fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600,
              fontSize: 11, padding: "5px 14px", cursor: "pointer",
            }}
          >Apply</button>
          <button
            onClick={cancelLink}
            style={{
              background: "transparent", border: "1px solid rgba(58,123,213,0.2)",
              borderRadius: 5, color: "#4a6a8a",
              fontFamily: "'Space Grotesk', sans-serif", fontSize: 11,
              padding: "5px 10px", cursor: "pointer",
            }}
          >Cancel</button>
        </div>
      )}
    </div>
  );
}

// ── Main panel ───────────────────────────────────────────────────────────────
export default function SOPsPanel() {
  const [sops, setSops] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [isNew, setIsNew] = useState(false);
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("General");
  const [customCatMode, setCustomCatMode] = useState(false);
  const [visibility, setVisibility] = useState("private");
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);
  const suppressNextUpdate = useRef(false);

  const editor = useEditor({
    extensions: [
      StarterKit,
      TextStyle,
      Color.configure({ types: ["textStyle"] }),
      Link.configure({
        openOnClick: true,
        HTMLAttributes: { rel: "noopener noreferrer", target: "_blank" },
      }),
      Table.configure({ resizable: true }),
      TableRow,
      TableHeader,
      TableCell,
    ],
    content: "",
    editorProps: { attributes: { class: "sop-prose" } },
    onUpdate: () => {
      if (suppressNextUpdate.current) { suppressNextUpdate.current = false; return; }
      setDirty(true);
    },
  });

  const fetchSOPs = useCallback(async () => {
    const r = await fetch("/api/sops");
    if (r.ok) setSops(await r.json());
  }, []);

  useEffect(() => { fetchSOPs(); }, [fetchSOPs]);

  const categories = [...new Set(sops.map(s => s.category || "General").filter(Boolean))];

  const setContent = (html) => {
    suppressNextUpdate.current = true;
    editor?.commands.setContent(html, false);
  };

  const openSOP = (sop) => {
    if (dirty && !window.confirm("Discard unsaved changes?")) return;
    const html = toHTML(sop.content);
    setSelectedId(sop.id);
    setTitle(sop.title);
    setCategory(sop.category || "General");
    setVisibility(sop.visibility || "private");
    setIsNew(false);
    setDirty(false);
    setCustomCatMode(false);
    setContent(html);
    requestAnimationFrame(() => editor?.commands.focus());
  };

  const startNew = () => {
    if (dirty && !window.confirm("Discard unsaved changes?")) return;
    setSelectedId(null);
    setIsNew(true);
    setTitle("");
    setCategory(categories[0] || "General");
    setVisibility("private");
    setDirty(false);
    setCustomCatMode(false);
    setContent("");
  };

  const save = async () => {
    if (!title.trim()) return;
    const content = editor ? editor.getHTML() : "";
    const payload = { title: title.trim(), content, category, visibility };
    setSaving(true);
    try {
      if (selectedId && !isNew) {
        await fetch(`/api/sops/${selectedId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
      } else {
        const r = await fetch("/api/sops", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ...payload, sort_order: 0 }),
        });
        if (r.ok) {
          const created = await r.json();
          setSelectedId(created.id);
          setIsNew(false);
        }
      }
      setDirty(false);
      setSavedFlash(true);
      setTimeout(() => setSavedFlash(false), 2500);
      await fetchSOPs();
    } finally {
      setSaving(false);
    }
  };

  const deleteSOP = async (sop, e) => {
    e.stopPropagation();
    if (!window.confirm(`Delete "${sop.title}"?`)) return;
    await fetch(`/api/sops/${sop.id}`, { method: "DELETE" });
    if (selectedId === sop.id) {
      setSelectedId(null);
      setIsNew(false);
      setDirty(false);
      setTitle("");
      setCategory("General");
      setContent("");
    }
    await fetchSOPs();
  };

  const grouped = sops.reduce((acc, sop) => {
    const cat = sop.category || "General";
    (acc[cat] = acc[cat] || []).push(sop);
    return acc;
  }, {});

  const showEditor = selectedId !== null || isNew;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      <style>{PROSE_CSS}</style>

      {/* Top bar */}
      <div style={{
        padding: "16px 24px 12px",
        borderBottom: "1px solid rgba(58,123,213,0.12)",
        display: "flex", alignItems: "center", gap: 14, flexShrink: 0,
      }}>
        <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: 18, color: "#e8f0ff" }}>SOPs</span>
        <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80", letterSpacing: "0.14em" }}>STANDARD OPERATING PROCEDURES</span>
        <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
          {savedFlash && (
            <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#34d399", letterSpacing: "0.1em" }}>SAVED ✓</span>
          )}
          {showEditor && (
            <button
              onClick={save}
              disabled={saving || !title.trim()}
              style={{
                background: dirty && title.trim()
                  ? "linear-gradient(90deg, #2857a0, #3a7bd5)"
                  : "rgba(58,123,213,0.12)",
                border: dirty && title.trim() ? "none" : "1px solid rgba(58,123,213,0.25)",
                borderRadius: 6, color: dirty && title.trim() ? "#fff" : "#6ab0ff",
                fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600,
                fontSize: 12, padding: "6px 16px",
                cursor: saving || !title.trim() ? "not-allowed" : "pointer",
                opacity: saving ? 0.6 : 1,
              }}
            >{saving ? "Saving..." : dirty ? "Save *" : "Save"}</button>
          )}
          <button
            onClick={startNew}
            style={{
              background: "linear-gradient(90deg, #2857a0, #3a7bd5)",
              border: "none", borderRadius: 6, color: "#fff",
              fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600,
              fontSize: 12, padding: "6px 14px", cursor: "pointer",
            }}
          >+ New SOP</button>
        </div>
      </div>

      {/* Body */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>

        {/* Sidebar */}
        <div style={{
          width: 240, flexShrink: 0,
          borderRight: "1px solid rgba(58,123,213,0.1)",
          overflowY: "auto", padding: "12px 0",
        }}>
          {isNew && (
            <div style={{
              margin: "0 8px 8px",
              padding: "7px 12px",
              borderRadius: 6,
              background: "rgba(58,123,213,0.15)",
              border: "1px solid rgba(58,123,213,0.3)",
              fontFamily: "'Space Grotesk', sans-serif",
              fontSize: 12, color: "#6ab0ff", fontWeight: 600,
            }}>
              + New SOP
            </div>
          )}
          {Object.keys(grouped).length === 0 && !isNew && (
            <div style={{ padding: "20px 16px", fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a6a", textAlign: "center", letterSpacing: "0.1em" }}>
              NO SOPS YET
            </div>
          )}
          {Object.entries(grouped).map(([cat, items]) => (
            <div key={cat}>
              <div style={{ padding: "8px 16px 4px", fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80", letterSpacing: "0.14em", textTransform: "uppercase" }}>
                {cat}
              </div>
              {items.map(sop => {
                const isActive = selectedId === sop.id;
                return (
                  <div
                    key={sop.id}
                    onClick={() => openSOP(sop)}
                    style={{
                      display: "flex", alignItems: "center", gap: 6,
                      padding: "7px 16px", cursor: "pointer",
                      background: isActive ? "linear-gradient(90deg, rgba(40,87,160,0.35), rgba(58,123,213,0.2))" : "transparent",
                      borderLeft: isActive ? "2px solid #3a7bd5" : "2px solid transparent",
                      transition: "background 0.15s",
                    }}
                    onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = "rgba(58,123,213,0.07)"; }}
                    onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = "transparent"; }}
                  >
                    <span style={{ width: 6, height: 6, borderRadius: "50%", flexShrink: 0, background: sop.visibility === "public" ? "#34d399" : "#6ab0ff", opacity: 0.8 }} />
                    <span style={{
                      flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                      fontFamily: "'Space Grotesk', sans-serif", fontSize: 12,
                      color: isActive ? "#e8f0ff" : "#7a9cc0",
                      fontWeight: isActive ? 600 : 400,
                    }}>{sop.title}</span>
                    <button
                      onClick={e => deleteSOP(sop, e)}
                      title="Delete"
                      style={{
                        background: "none", border: "none", cursor: "pointer",
                        color: "#dc3c3c", fontSize: 14, lineHeight: 1, padding: 0,
                        flexShrink: 0, opacity: 0, transition: "opacity 0.15s",
                      }}
                      onMouseEnter={e => e.currentTarget.style.opacity = "1"}
                      onMouseLeave={e => e.currentTarget.style.opacity = "0"}
                    >×</button>
                  </div>
                );
              })}
            </div>
          ))}
        </div>

        {/* Editor pane */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          {!showEditor ? (
            <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1e3050", letterSpacing: "0.12em" }}>
                SELECT OR CREATE A SOP
              </div>
            </div>
          ) : (
            <>
              {/* Title + meta row */}
              <div style={{
                padding: "12px 36px",
                borderBottom: "1px solid rgba(58,123,213,0.1)",
                display: "flex", alignItems: "center", gap: 10, flexShrink: 0,
              }}>
                <input
                  value={title}
                  onChange={e => { setTitle(e.target.value); setDirty(true); }}
                  placeholder="SOP title..."
                  autoFocus={isNew}
                  style={{
                    flex: 1, background: "rgba(255,255,255,0.04)",
                    border: "1px solid rgba(58,123,213,0.2)", borderRadius: 6,
                    padding: "6px 12px", color: "#e8f0ff",
                    fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700,
                    fontSize: 15, outline: "none",
                  }}
                />

                {customCatMode ? (
                  <input
                    value={category}
                    onChange={e => { setCategory(e.target.value); setDirty(true); }}
                    placeholder="Category name"
                    autoFocus
                    onBlur={() => { if (!category.trim()) { setCustomCatMode(false); setCategory(categories[0] || "General"); } }}
                    onKeyDown={e => { if (e.key === "Enter") { setCustomCatMode(false); setDirty(true); } }}
                    style={{
                      width: 130, background: "rgba(255,255,255,0.04)",
                      border: "1px solid rgba(58,123,213,0.3)", borderRadius: 6,
                      padding: "6px 10px", color: "#9ab8d8",
                      fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, outline: "none",
                    }}
                  />
                ) : (
                  <select
                    value={category}
                    onChange={e => {
                      if (e.target.value === "__new__") {
                        setCustomCatMode(true);
                        setCategory("");
                      } else {
                        setCategory(e.target.value);
                        setDirty(true);
                      }
                    }}
                    style={{
                      background: "#0d1a3a",
                      border: "1px solid rgba(58,123,213,0.2)", borderRadius: 6,
                      padding: "6px 10px", color: "#9ab8d8",
                      fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, outline: "none",
                      cursor: "pointer",
                    }}
                  >
                    {[...new Set([...categories, ...(category ? [category] : [])])].map(c => (
                      <option key={c} value={c} style={{ background: "#0d1a3a" }}>{c}</option>
                    ))}
                    <option value="__new__" style={{ background: "#0d1a3a" }}>+ New category…</option>
                  </select>
                )}

                <div style={{ display: "flex", borderRadius: 6, overflow: "hidden", border: "1px solid rgba(58,123,213,0.25)", flexShrink: 0 }}>
                  {["private", "public"].map(v => (
                    <button
                      key={v}
                      onClick={() => { setVisibility(v); setDirty(true); }}
                      style={{
                        padding: "5px 10px", border: "none", cursor: "pointer",
                        background: visibility === v
                          ? v === "public" ? "rgba(52,211,153,0.25)" : "rgba(58,123,213,0.3)"
                          : "transparent",
                        color: visibility === v
                          ? v === "public" ? "#34d399" : "#6ab0ff"
                          : "#3a5a80",
                        fontFamily: "'Space Grotesk', sans-serif", fontSize: 11, fontWeight: 600,
                        textTransform: "capitalize", transition: "all 0.15s",
                      }}
                    >{v}</button>
                  ))}
                </div>
              </div>

              <FormatBar editor={editor} />

              <div style={{ flex: 1, overflowY: "auto", padding: "24px 36px" }}>
                <EditorContent editor={editor} />
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
