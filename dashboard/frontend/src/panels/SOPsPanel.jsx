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
    content: 'Start writing...';
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
  .sop-prose ul { padding-left: 20px; margin: 0 0 12px; list-style-type: disc; }
  .sop-prose ol { padding-left: 20px; margin: 0 0 12px; list-style-type: decimal; }
  .sop-prose li { font-size: 13.5px; line-height: 1.8; margin-bottom: 4px; list-style-position: outside; }
  .sop-prose ul ul { list-style-type: circle; }
  .sop-prose ul ul ul { list-style-type: square; }
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

const SUBSECTIONS = [
  { id: "sop",          label: "SOPs",               subtitle: "STANDARD OPERATING PROCEDURES", newLabel: "New SOP",        placeholder: "SOP title..." },
  { id: "business_doc", label: "Business Documents",  subtitle: "CONTRACTS · PROPOSALS · DOCS",  newLabel: "New Document",   placeholder: "Document title..." },
  { id: "recording",    label: "Recordings",          subtitle: "CALLS · DEMOS · RECORDINGS",    newLabel: "New Recording",  placeholder: "Recording title..." },
];

// ── Main panel ───────────────────────────────────────────────────────────────
export default function SOPsPanel() {
  const [activeSection, setActiveSection] = useState("sop");
  const [sops, setSops] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [selectedItem, setSelectedItem] = useState(null);
  const [isNew, setIsNew] = useState(false);
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("General");
  const [customCatMode, setCustomCatMode] = useState(false);
  const [visibility, setVisibility] = useState("private");
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);
  const [uploading, setUploading] = useState(false);
  const suppressNextUpdate = useRef(false);
  const uploadRef = useRef(null);

  const section = SUBSECTIONS.find(s => s.id === activeSection) || SUBSECTIONS[0];

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
    const r = await fetch(`/api/sops?doc_type=${activeSection}`);
    if (r.ok) setSops(await r.json());
  }, [activeSection]);

  useEffect(() => { fetchSOPs(); }, [fetchSOPs]);

  useEffect(() => {
    setSelectedId(null);
    setSelectedItem(null);
    setIsNew(false);
    setDirty(false);
    setTitle("");
    setCategory("General");
    setContent("");
  }, [activeSection]);

  const categories = [...new Set(sops.map(s => s.category || "General").filter(Boolean))];

  const setContent = (html) => {
    suppressNextUpdate.current = true;
    editor?.commands.setContent(html, false);
  };

  const openSOP = (sop) => {
    if (dirty && !window.confirm("Discard unsaved changes?")) return;
    setSelectedId(sop.id);
    setSelectedItem(sop);
    setTitle(sop.title);
    setCategory(sop.category || "General");
    setVisibility(sop.visibility || "private");
    setIsNew(false);
    setDirty(false);
    setCustomCatMode(false);
    if (!sop.file_name) {
      setContent(toHTML(sop.content));
      requestAnimationFrame(() => editor?.commands.focus());
    }
  };

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = "";
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("title", file.name);
      form.append("category", "General");
      form.append("doc_type", activeSection);
      form.append("visibility", "private");
      const r = await fetch("/api/sops/upload", { method: "POST", body: form });
      if (r.ok) {
        const created = await r.json();
        await fetchSOPs();
        openSOP(created);
      }
    } finally {
      setUploading(false);
    }
  };

  const startNew = () => {
    if (dirty && !window.confirm("Discard unsaved changes?")) return;
    setSelectedId(null);
    setSelectedItem(null);
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
    const payload = { title: title.trim(), content, category, visibility, doc_type: activeSection };
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
    e?.stopPropagation();
    if (!window.confirm(`Delete "${sop.title}"?`)) return;
    await fetch(`/api/sops/${sop.id}`, { method: "DELETE" });
    if (selectedId === sop.id) {
      setSelectedId(null);
      setSelectedItem(null);
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
        <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: 18, color: "#e8f0ff" }}>{section.label}</span>
        <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80", letterSpacing: "0.14em" }}>{section.subtitle}</span>
        <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
          {savedFlash && (
            <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#34d399", letterSpacing: "0.1em" }}>SAVED ✓</span>
          )}
          {showEditor && !selectedItem?.file_name && (
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
          {selectedId !== null && !isNew && (
            <button
              onClick={() => deleteSOP(selectedItem)}
              title="Delete this document"
              style={{
                background: "rgba(220,60,60,0.1)",
                border: "1px solid rgba(220,60,60,0.3)",
                borderRadius: 6, color: "#dc3c3c",
                fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600,
                fontSize: 12, padding: "6px 14px", cursor: "pointer",
              }}
            >Delete</button>
          )}
          <input ref={uploadRef} type="file" style={{ display: "none" }} onChange={handleUpload} />
          <button
            onClick={() => uploadRef.current?.click()}
            disabled={uploading}
            style={{
              background: "rgba(58,123,213,0.12)",
              border: "1px solid rgba(58,123,213,0.25)",
              borderRadius: 6, color: "#6ab0ff",
              fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600,
              fontSize: 12, padding: "6px 14px", cursor: uploading ? "not-allowed" : "pointer",
              opacity: uploading ? 0.6 : 1,
            }}
          >{uploading ? "Uploading…" : "↑ Upload"}</button>
          <button
            onClick={startNew}
            style={{
              background: "linear-gradient(90deg, #2857a0, #3a7bd5)",
              border: "none", borderRadius: 6, color: "#fff",
              fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600,
              fontSize: 12, padding: "6px 14px", cursor: "pointer",
            }}
          >+ {section.newLabel}</button>
        </div>
      </div>

      {/* Body */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>

        {/* Sidebar */}
        <div style={{
          width: 240, flexShrink: 0,
          borderRight: "1px solid rgba(58,123,213,0.1)",
          display: "flex", flexDirection: "column", overflow: "hidden",
        }}>
          {/* Subsection tabs */}
          <div style={{ padding: "10px 8px 0", flexShrink: 0 }}>
            {SUBSECTIONS.map(sub => (
              <button
                key={sub.id}
                onClick={() => setActiveSection(sub.id)}
                style={{
                  display: "block", width: "100%", textAlign: "left",
                  padding: "7px 12px", marginBottom: 2,
                  background: activeSection === sub.id ? "rgba(58,123,213,0.18)" : "transparent",
                  border: activeSection === sub.id ? "1px solid rgba(58,123,213,0.3)" : "1px solid transparent",
                  borderRadius: 6, cursor: "pointer",
                  fontFamily: "'Space Grotesk', sans-serif",
                  fontSize: 12, fontWeight: activeSection === sub.id ? 600 : 400,
                  color: activeSection === sub.id ? "#6ab0ff" : "#4a6a8a",
                  transition: "all 0.15s",
                }}
              >{sub.label}</button>
            ))}
            <div style={{ borderBottom: "1px solid rgba(58,123,213,0.1)", margin: "8px 0" }} />
          </div>

          <div style={{ flex: 1, overflowY: "auto", padding: "0 0 12px" }}>
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
              + {section.newLabel}
            </div>
          )}
          {Object.keys(grouped).length === 0 && !isNew && (
            <div style={{ padding: "20px 16px", fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#2a4a6a", textAlign: "center", letterSpacing: "0.1em" }}>
              NO {section.label.toUpperCase()} YET
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
                    {sop.file_name
                      ? <span style={{ fontSize: 11, flexShrink: 0, opacity: 0.7 }}>{/^audio|^video/.test(sop.file_type || "") ? "🎙" : "📎"}</span>
                      : <span style={{ width: 6, height: 6, borderRadius: "50%", flexShrink: 0, background: sop.visibility === "public" ? "#34d399" : "#6ab0ff", opacity: 0.8 }} />
                    }
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
        </div>

        {/* Editor / file viewer pane */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          {!showEditor ? (
            <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1e3050", letterSpacing: "0.12em" }}>
                SELECT OR CREATE A {section.label.toUpperCase().replace(/S$/, "")}
              </div>
            </div>
          ) : selectedItem?.file_name ? (
            /* ── File viewer ── */
            <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
              <div style={{
                padding: "14px 36px", borderBottom: "1px solid rgba(58,123,213,0.1)",
                display: "flex", alignItems: "center", gap: 12, flexShrink: 0,
              }}>
                <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: 15, color: "#e8f0ff", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {selectedItem.title}
                </span>
                <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80", letterSpacing: "0.1em", flexShrink: 0 }}>
                  {selectedItem.file_type} · {selectedItem.file_size ? (selectedItem.file_size / 1024 / 1024).toFixed(1) + " MB" : ""}
                </span>
                <a
                  href={`/api/sops/${selectedItem.id}/file`}
                  download={selectedItem.file_name}
                  style={{
                    background: "rgba(58,123,213,0.12)", border: "1px solid rgba(58,123,213,0.25)",
                    borderRadius: 6, color: "#6ab0ff", textDecoration: "none",
                    fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600,
                    fontSize: 12, padding: "6px 14px", flexShrink: 0,
                  }}
                >↓ Download</a>
              </div>
              <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", overflow: "hidden", padding: 24 }}>
                {/^audio\//.test(selectedItem.file_type || "") ? (
                  <audio controls src={`/api/sops/${selectedItem.id}/file`} style={{ width: "100%", maxWidth: 600 }} />
                ) : /^video\//.test(selectedItem.file_type || "") ? (
                  <video controls src={`/api/sops/${selectedItem.id}/file`} style={{ maxWidth: "100%", maxHeight: "100%", borderRadius: 8 }} />
                ) : /\/pdf$/.test(selectedItem.file_type || "") ? (
                  <iframe src={`/api/sops/${selectedItem.id}/file`} style={{ width: "100%", height: "100%", border: "none", borderRadius: 8, background: "#fff" }} title={selectedItem.file_name} />
                ) : (
                  <div style={{ textAlign: "center" }}>
                    <div style={{ fontSize: 48, marginBottom: 16 }}>📎</div>
                    <div style={{ fontFamily: "'Space Grotesk', sans-serif", color: "#9ab8d8", marginBottom: 20 }}>{selectedItem.file_name}</div>
                    <a
                      href={`/api/sops/${selectedItem.id}/file`}
                      download={selectedItem.file_name}
                      style={{
                        background: "linear-gradient(90deg, #2857a0, #3a7bd5)", border: "none",
                        borderRadius: 6, color: "#fff", textDecoration: "none",
                        fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600,
                        fontSize: 13, padding: "9px 24px",
                      }}
                    >↓ Download File</a>
                  </div>
                )}
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
                  placeholder={section.placeholder}
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
