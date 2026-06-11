import React, { useState, useEffect, useCallback } from "react";
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

const EMPTY_DRAFT = { title: "", content: "", category: "General", visibility: "private" };
const CONTENT_PAD = "24px 36px";

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
  .sop-prose:focus { outline: none; }
  .sop-prose.ProseMirror { outline: none; }
  .sop-prose.ProseMirror p.is-editor-empty:first-child::before {
    content: 'Start writing your SOP...'; float: left;
    color: #2a4a6a; pointer-events: none; height: 0;
  }
  .sop-prose h1 { font-size: 22px; font-weight: 700; color: #6ab0ff; margin: 0 0 14px;
    border-bottom: 1px solid rgba(58,123,213,0.2); padding-bottom: 8px;
    font-family: 'Space Grotesk', sans-serif; }
  .sop-prose h2 { font-size: 16px; font-weight: 600; color: #a0c4ff; margin: 22px 0 8px;
    font-family: 'Space Grotesk', sans-serif; }
  .sop-prose h3 { font-size: 14px; font-weight: 600; color: #c0d8ff; margin: 16px 0 6px;
    font-family: 'Space Grotesk', sans-serif; }
  .sop-prose p { font-size: 13.5px; line-height: 1.8; margin: 0 0 12px; }
  .sop-prose ul { padding-left: 20px; margin: 0 0 12px; }
  .sop-prose ol { padding-left: 20px; margin: 0 0 12px; }
  .sop-prose li { font-size: 13.5px; line-height: 1.8; margin-bottom: 4px; }
  .sop-prose strong { color: #d0e8ff; font-weight: 700; }
  .sop-prose em { font-style: italic; }
  .sop-prose s { color: #4a6a8a; }
  .sop-prose hr { border: none; border-top: 1px solid rgba(58,123,213,0.18); margin: 20px 0; }
  .sop-prose blockquote { border-left: 3px solid #3a7bd5; padding-left: 14px;
    margin: 0 0 12px; color: #8aaccc; font-style: italic; }
  .sop-prose code { font-family: 'Share Tech Mono', monospace; font-size: 12px;
    color: #6ab0ff; background: rgba(58,123,213,0.15); padding: 1px 5px; border-radius: 3px; }
  .sop-prose pre { background: rgba(0,0,0,0.35); border: 1px solid rgba(58,123,213,0.2);
    border-radius: 6px; padding: 12px 16px; overflow: auto; margin: 0 0 12px; }
  .sop-prose pre code { background: none; padding: 0; color: #b8cce8; }
  .sop-prose a { color: #3a7bd5; text-decoration: underline; cursor: pointer; }
  .sop-prose a:hover { color: #6ab0ff; }
  .sop-prose .tableWrapper { overflow-x: auto; margin: 0 0 12px; }
  .sop-prose table { border-collapse: collapse; width: 100%; font-size: 13px; margin: 0; }
  .sop-prose th { padding: 6px 12px; background: rgba(58,123,213,0.2); color: #a0c4ff;
    font-weight: 600; text-align: left; border: 1px solid rgba(58,123,213,0.25); min-width: 80px; }
  .sop-prose td { padding: 6px 12px; color: #b8cce8; border: 1px solid rgba(58,123,213,0.12); min-width: 80px; }
  .sop-prose .selectedCell { background: rgba(58,123,213,0.15) !important; }
  .sop-prose .column-resize-handle { position: absolute; right: -2px; top: 0; bottom: 0;
    width: 4px; background: rgba(58,123,213,0.4); pointer-events: none; }
  .sop-prose .resize-cursor { cursor: col-resize; }
  .tiptap { height: 100%; }
  .sop-del { opacity: 0 !important; transition: opacity 0.15s; }
  div:hover > .sop-del { opacity: 1 !important; }
`;

// ── Colors for toolbar ───────────────────────────────────────────────────────
const COLORS = [
  { hex: "#e8f0ff", label: "White" },
  { hex: "#6ab0ff", label: "Blue" },
  { hex: "#34d399", label: "Green" },
  { hex: "#f59e0b", label: "Amber" },
  { hex: "#ef4444", label: "Red" },
  { hex: "#a78bfa", label: "Purple" },
];

// ── Format toolbar ───────────────────────────────────────────────────────────
function FormatBar({ editor }) {
  const [linkInput, setLinkInput] = useState("");
  const [showLink, setShowLink] = useState(false);

  if (!editor) return null;

  const btn = (label, onClick, isActive = false, extra = {}) => (
    <button
      key={label}
      onMouseDown={e => { e.preventDefault(); onClick(); }}
      title={label}
      style={{
        background: isActive ? "rgba(58,123,213,0.3)" : "rgba(255,255,255,0.04)",
        border: `1px solid ${isActive ? "rgba(58,123,213,0.5)" : "rgba(58,123,213,0.15)"}`,
        borderRadius: 5, color: isActive ? "#6ab0ff" : "#7a9cc0",
        fontFamily: "'Space Grotesk', sans-serif", fontSize: 11, fontWeight: 600,
        padding: "3px 8px", cursor: "pointer", lineHeight: 1.4, minWidth: 28,
        ...extra,
      }}
    >{label}</button>
  );

  const sep = (k) => (
    <div key={k} style={{ width: 1, height: 14, background: "rgba(58,123,213,0.2)", margin: "0 2px", flexShrink: 0 }} />
  );

  const applyLink = () => {
    if (!linkInput.trim()) { setShowLink(false); return; }
    const href = linkInput;
    editor.chain().focus().setLink({ href, target: "_blank" }).run();
    setLinkInput(""); setShowLink(false);
  };

  const handleLinkBtn = (e) => {
    e.preventDefault();
    if (editor.isActive("link")) {
      editor.chain().focus().unsetLink().run();
    } else {
      setShowLink(s => !s);
    }
  };

  const inTable = editor.isActive("table");

  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 4,
      padding: "8px 36px", flexShrink: 0, flexWrap: "wrap",
      borderBottom: "1px solid rgba(58,123,213,0.1)",
      background: "rgba(0,0,0,0.15)",
    }}>
      {btn("H1", () => editor.chain().focus().toggleHeading({ level: 1 }).run(), editor.isActive("heading", { level: 1 }))}
      {btn("H2", () => editor.chain().focus().toggleHeading({ level: 2 }).run(), editor.isActive("heading", { level: 2 }))}
      {btn("H3", () => editor.chain().focus().toggleHeading({ level: 3 }).run(), editor.isActive("heading", { level: 3 }))}
      {sep("s1")}
      {btn("B",  () => editor.chain().focus().toggleBold().run(),   editor.isActive("bold"),   { fontWeight: 900 })}
      {btn("I",  () => editor.chain().focus().toggleItalic().run(), editor.isActive("italic"), { fontStyle: "italic" })}
      {btn("S",  () => editor.chain().focus().toggleStrike().run(), editor.isActive("strike"), { textDecoration: "line-through" })}
      {sep("s2")}
      {btn("• List",  () => editor.chain().focus().toggleBulletList().run(),  editor.isActive("bulletList"))}
      {btn("1. List", () => editor.chain().focus().toggleOrderedList().run(), editor.isActive("orderedList"))}
      {btn("——",       () => editor.chain().focus().setHorizontalRule().run())}
      {sep("s3")}

      {/* Link */}
      <button
        onMouseDown={handleLinkBtn}
        title={editor.isActive("link") ? "Remove link" : "Add link"}
        style={{
          background: editor.isActive("link") ? "rgba(58,123,213,0.3)" : "rgba(255,255,255,0.04)",
          border: `1px solid ${editor.isActive("link") ? "rgba(58,123,213,0.5)" : "rgba(58,123,213,0.15)"}`,
          borderRadius: 5, color: editor.isActive("link") ? "#6ab0ff" : "#7a9cc0",
          fontFamily: "'Space Grotesk', sans-serif", fontSize: 11, fontWeight: 600,
          padding: "3px 8px", cursor: "pointer", lineHeight: 1.4,
        }}
      >🔗</button>
      {showLink && (
        <input
          autoFocus
          value={linkInput}
          onChange={e => setLinkInput(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); applyLink(); } if (e.key === "Escape") { setShowLink(false); setLinkInput(""); } }}
          onBlur={applyLink}
          placeholder="https://..."
          style={{
            background: "rgba(7,12,30,0.8)", border: "1px solid rgba(58,123,213,0.35)",
            borderRadius: 5, color: "#8aaad0", fontSize: 11, padding: "3px 8px",
            outline: "none", width: 180,
          }}
        />
      )}

      {sep("s4")}

      {/* Table */}
      {btn("⊞ Table", () => editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run())}
      {inTable && btn("+Row", () => editor.chain().focus().addRowAfter().run())}
      {inTable && btn("+Col", () => editor.chain().focus().addColumnAfter().run())}
      {inTable && btn("-Row", () => editor.chain().focus().deleteRow().run())}
      {inTable && btn("-Col", () => editor.chain().focus().deleteColumn().run())}
      {inTable && btn("Del Table", () => editor.chain().focus().deleteTable().run(), false, { color: "#dc3c3c" })}

      {sep("s5")}
      {COLORS.map(({ hex, label }) => (
        <button
          key={hex}
          title={label}
          onMouseDown={e => { e.preventDefault(); editor.chain().focus().setColor(hex).run(); }}
          style={{
            width: 14, height: 14, borderRadius: "50%",
            background: hex, border: "1.5px solid rgba(255,255,255,0.15)",
            cursor: "pointer", padding: 0, flexShrink: 0,
          }}
        />
      ))}
    </div>
  );
}

// ── Header strip ─────────────────────────────────────────────────────────────
function SOPHeader({ draft, setDraft, editing, onEdit, onSave, onCancel, saving, savedFlash }) {
  return (
    <div style={{
      padding: "14px 36px", borderBottom: "1px solid rgba(58,123,213,0.1)",
      display: "flex", alignItems: "center", gap: 10, flexShrink: 0, minHeight: 52,
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
              >{v}</button>
            ))}
          </div>
          <button
            onClick={onCancel}
            style={{ background: "transparent", border: "1px solid rgba(58,123,213,0.2)", borderRadius: 6, color: "#4a6a8a", fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600, fontSize: 12, padding: "5px 12px", cursor: "pointer" }}
          >Cancel</button>
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
          >{saving ? "Saving..." : "Save"}</button>
        </>
      ) : (
        <>
          <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: 15, color: "#e8f0ff", flex: 1 }}>
            {draft.title}
          </span>
          {savedFlash && (
            <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#34d399", letterSpacing: "0.1em" }}>SAVED</span>
          )}
          <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a5a80", letterSpacing: "0.08em" }}>{draft.category}</span>
          <span style={{
            fontFamily: "'Share Tech Mono', monospace", fontSize: 10, letterSpacing: "0.08em",
            color: draft.visibility === "public" ? "#34d399" : "#6ab0ff",
            background: draft.visibility === "public" ? "rgba(52,211,153,0.1)" : "rgba(58,123,213,0.1)",
            padding: "2px 8px", borderRadius: 3,
          }}>{draft.visibility.toUpperCase()}</span>
          <button
            onClick={onEdit}
            style={{
              background: "rgba(58,123,213,0.12)", border: "1px solid rgba(58,123,213,0.25)",
              borderRadius: 6, color: "#6ab0ff",
              fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600,
              fontSize: 12, padding: "5px 14px", cursor: "pointer",
            }}
          >Edit</button>
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

  const editor = useEditor({
    extensions: [
      StarterKit,
      TextStyle,
      Color.configure({ types: ["textStyle"] }),
      Link.configure({ openOnClick: true, HTMLAttributes: { rel: "noopener noreferrer", target: "_blank" } }),
      Table.configure({ resizable: true }),
      TableRow,
      TableHeader,
      TableCell,
    ],
    content: "",
    onUpdate: ({ editor }) => {
      setDraft(d => ({ ...d, content: editor.getHTML() }));
    },
    editorProps: {
      attributes: { class: "sop-prose" },
    },
  });

  const fetchSOPs = useCallback(async () => {
    const r = await fetch("/api/sops");
    if (r.ok) setSops(await r.json());
  }, []);

  useEffect(() => { fetchSOPs(); }, [fetchSOPs]);

  const selectSOP = (sop) => {
    const html = toHTML(sop.content);
    const data = { title: sop.title, content: html, category: sop.category, visibility: sop.visibility };
    setSelectedId(sop.id);
    setCommitted(data);
    setDraft(data);
    setEditing(false);
    if (editor) editor.commands.setContent(html);
  };

  const newSOP = () => {
    setSelectedId(null);
    setCommitted(EMPTY_DRAFT);
    setDraft(EMPTY_DRAFT);
    setEditing(true);
    if (editor) { editor.commands.setContent(""); editor.commands.focus(); }
  };

  const onEdit = () => {
    const html = toHTML(committed.content);
    setDraft({ ...committed, content: html });
    if (editor) { editor.commands.setContent(html); editor.commands.focus(); }
    setEditing(true);
  };

  const cancelEdit = () => {
    if (!selectedId) { setSelectedId(null); setCommitted(EMPTY_DRAFT); setDraft(EMPTY_DRAFT); }
    else {
      setDraft({ ...committed });
      if (editor) editor.commands.setContent(committed.content);
    }
    setEditing(false);
  };

  const saveSOP = async () => {
    const content = editor ? editor.getHTML() : draft.content;
    const payload = { ...draft, content };
    if (!payload.title.trim()) return;
    setSaving(true);
    try {
      if (selectedId) {
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
        const created = await r.json();
        setSelectedId(created.id);
      }
      const saved = { ...payload };
      setCommitted(saved);
      setDraft(saved);
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
    if (selectedId === id) {
      setSelectedId(null); setCommitted(EMPTY_DRAFT); setDraft(EMPTY_DRAFT);
      setEditing(false);
      if (editor) editor.commands.setContent("");
    }
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
      <style>{PROSE_CSS}</style>

      {/* Panel header */}
      <div style={{ padding: "18px 24px 14px", borderBottom: "1px solid rgba(58,123,213,0.12)", display: "flex", alignItems: "center", gap: 16, flexShrink: 0 }}>
        <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: 18, color: "#e8f0ff" }}>SOPs</span>
        <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80", letterSpacing: "0.14em" }}>STANDARD OPERATING PROCEDURES</span>
        <div style={{ marginLeft: "auto" }}>
          <button
            onClick={newSOP}
            style={{ background: "linear-gradient(90deg, #2857a0, #3a7bd5)", border: "none", borderRadius: 6, color: "#fff", fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600, fontSize: 12, padding: "6px 14px", cursor: "pointer" }}
          >+ New SOP</button>
        </div>
      </div>

      {/* Body */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>

        {/* Left: SOP list */}
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
                  style={{
                    display: "flex", alignItems: "center", gap: 6, padding: "7px 16px",
                    cursor: "pointer",
                    background: selectedId === sop.id ? "linear-gradient(90deg, rgba(40,87,160,0.35), rgba(58,123,213,0.2))" : "transparent",
                    borderLeft: selectedId === sop.id ? "2px solid #3a7bd5" : "2px solid transparent",
                    transition: "background 0.15s",
                  }}
                >
                  <span style={{ width: 6, height: 6, borderRadius: "50%", flexShrink: 0, background: sop.visibility === "public" ? "#34d399" : "#6ab0ff", opacity: 0.8 }} />
                  <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, color: selectedId === sop.id ? "#e8f0ff" : "#7a9cc0", fontWeight: selectedId === sop.id ? 600 : 400 }}>{sop.title}</span>
                  <button onClick={e => deleteSOP(sop.id, e)} className="sop-del" title="Delete" style={{ background: "none", border: "none", cursor: "pointer", color: "#3a5a80", fontSize: 14, lineHeight: 1, padding: 0, flexShrink: 0 }}>×</button>
                </div>
              ))}
            </div>
          ))}
        </div>

        {/* Right: header + content */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>

          {(hasContent || editing) && (
            <SOPHeader
              draft={draft}
              setDraft={setDraft}
              editing={editing}
              onEdit={onEdit}
              onSave={saveSOP}
              onCancel={cancelEdit}
              saving={saving}
              savedFlash={savedFlash}
            />
          )}

          {editing && <FormatBar editor={editor} />}

          <div style={{ flex: 1, overflow: "hidden", position: "relative" }}>

            {/* Tiptap editor — always mounted, shown only when editing */}
            <div style={{
              position: "absolute", inset: 0,
              display: editing ? "block" : "none",
              overflowY: "auto", padding: CONTENT_PAD,
            }}>
              <EditorContent editor={editor} />
            </div>

            {/* Preview — same CSS class, same padding */}
            {!editing && (
              <div style={{ position: "absolute", inset: 0, overflowY: "auto", padding: CONTENT_PAD }}>
                {!hasContent ? (
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1e3050", letterSpacing: "0.12em" }}>
                    SELECT OR CREATE A SOP
                  </div>
                ) : (
                  <div className="sop-prose" dangerouslySetInnerHTML={{ __html: committed.content || "" }} />
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
