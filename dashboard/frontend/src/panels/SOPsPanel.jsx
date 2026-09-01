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
import SequenceQueueModal from "./SequenceQueueModal";
import DmFollowUpQueueModal from "./DmFollowUpQueueModal";

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

// Category names are user-typed free text (see CategoryPicker's "+ New
// category…" custom-entry mode below), so "SMS Outreach" and "sms outreach "
// are trivially easy to end up as two different stored strings even though
// they were meant to be the same category. Every place that lists, groups,
// or matches categories needs to treat them as the same case/whitespace-
// insensitively, or documents silently split into look-alike duplicate
// categories. `catKey` is the comparison key; `dedupeCategories` collapses a
// list to one entry per key, keeping whichever original casing was seen
// first as the canonical display form.
const catKey = (c) => (c || "").trim().toLowerCase();

function dedupeCategories(list) {
  const seen = new Map();
  for (const c of list) {
    if (!c) continue;
    const key = catKey(c);
    if (key && !seen.has(key)) seen.set(key, c.trim());
  }
  return [...seen.values()];
}

// When a user finishes typing a custom category, snap it to an existing
// category's canonical casing if one matches case/whitespace-insensitively —
// this is what actually prevents new near-duplicates from being created,
// rather than just hiding duplicates that already exist.
function resolveCategory(typed, existingCategories) {
  const trimmed = (typed || "").trim();
  const match = existingCategories.find(c => catKey(c) === catKey(trimmed));
  return match || trimmed;
}

const SUBSECTIONS = [
  { id: "sop",                label: "SOPs",               subtitle: "STANDARD OPERATING PROCEDURES", newLabel: "New SOP",      placeholder: "SOP title..." },
  { id: "business_doc",       label: "Business Documents",  subtitle: "CONTRACTS · PROPOSALS · DOCS",  newLabel: "New Document", placeholder: "Document title..." },
  { id: "outreach_templates", label: "Outreach Templates",  subtitle: "SMS · EMAIL · SCRIPTS",          newLabel: "New Template", placeholder: "Template title..." },
];

// Pinned pseudo-document at the top of the Outreach Templates list — not a
// row in the `sops` table. Opening it shows the dedicated SMS/email editor
// backed by GET/PUT /api/dialer/info-template (see OutreachTemplatesEditor
// below), since the dialer's "Send Info" disposition reads from that store,
// not from `sops`.
const SEND_INFO_PSEUDO_ID = "__send_info__";
const SEND_INFO_ITEM = { id: SEND_INFO_PSEUDO_ID, title: "Send Info (SMS + Email)", sendInfo: true };

// Same pattern again, for the "No Show" disposition — backed by GET/PUT
// /api/dialer/no-show-template, since marking an appointment's outcome "No
// Show" in the Appointments tab reads from that store (see
// dashboard/backend/routers/appointments.py's PATCH handler), not from `sops`.
const NO_SHOW_PSEUDO_ID = "__no_show__";
const NO_SHOW_ITEM = { id: NO_SHOW_PSEUDO_ID, title: "No Show (SMS + Email)", noShow: true };

// Same pattern again, for cancellation recovery — backed by GET/PUT
// /api/dialer/cancel-template, since clicking Cancel on an appointment in
// the Appointments tab reads from that store (see
// dashboard/backend/routers/appointments.py's cancel_appointment() handler),
// not from `sops`.
const CANCEL_PSEUDO_ID = "__cancel__";
const CANCEL_ITEM = { id: CANCEL_PSEUDO_ID, title: "Cancellation (SMS + Email)", cancelTemplate: true };

// Same pattern again, for the DM Reach follow-up sequence — backed by
// GET/PUT /api/dialer/dm-followup-template. SMS-only, since DM Reach has no
// email equivalent. Fires automatically once a conversation marked DM
// Reached in the Inbox goes 24h without a reply (dm_followup_sequence.py).
const DM_FOLLOWUP_PSEUDO_ID = "__dm_followup__";
const DM_FOLLOWUP_ITEM = { id: DM_FOLLOWUP_PSEUDO_ID, title: "DM Follow-Up (SMS)", dmFollowupTemplate: true };

// Same pattern again, for the onboarding kickoff welcome email — backed by
// GET/PUT /api/dialer/onboarding-template. Email-only (no SMS), single
// template (not a multi-touch drip). Fires automatically the moment a rep
// marks an appointment's outcome "Closed" (won) in the Appointments tab —
// onboarding_sequence.py.
const ONBOARDING_PSEUDO_ID = "__onboarding__";
const ONBOARDING_ITEM = { id: ONBOARDING_PSEUDO_ID, title: "Onboarding Sequence (Email + SMS)", onboardingTemplate: true };

// Unlike SEND_INFO_ITEM/REMINDER_TEMPLATE_ITEM above, SMS Sequences are no
// longer a single pinned pseudo-doc — there can be many, named and switchable
// (see the `sequences` state / GET /api/sms-sequences below). Each fetched
// sequence becomes its own pseudo-item, built where `pseudoItems` is
// assembled further down, using the same `smsSequence: true` flag pattern so
// it still short-circuits `openSOP()` and slots into the same category
// grouping as everything else in this section.

// Same pattern again, for the appointment-reminder pipeline (24h/6h/1h
// reminders, reschedule notice) — backed by GET/PUT /api/dialer/reminder-template
// (see AppointmentRemindersEditor below), read at send time by
// dashboard/backend/reminder_engine.py.
const REMINDER_TEMPLATE_PSEUDO_ID = "__reminder_template__";
const REMINDER_TEMPLATE_ITEM = { id: REMINDER_TEMPLATE_PSEUDO_ID, title: "Appointment Reminders", reminderTemplate: true };

// ── Shared category picker ──────────────────────────────────────────────────
// Same select-or-type-a-new-one pattern as the regular document editor's
// category control (see the main doc editor's title/meta row below), factored
// out so the pinned Send Info / Appointment Reminders pseudo-docs and every
// SMS Sequence editor can offer the same "same options as the general
// document would have" category picker.
function CategoryPicker({ categories, category, setCategory, customCatMode, setCustomCatMode, onCommit }) {
  if (customCatMode) {
    return (
      <input
        value={category}
        onChange={e => setCategory(e.target.value)}
        placeholder="Category name"
        autoFocus
        onBlur={() => { if (!category.trim()) { setCustomCatMode(false); setCategory(categories[0] || "General"); } }}
        onKeyDown={e => { if (e.key === "Enter") { setCategory(resolveCategory(category, categories)); setCustomCatMode(false); onCommit?.(); } }}
        style={{
          width: 130, background: "rgba(255,255,255,0.04)",
          border: "1px solid rgba(58,123,213,0.3)", borderRadius: 6,
          padding: "6px 10px", color: "#9ab8d8",
          fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, outline: "none",
        }}
      />
    );
  }
  return (
    <select
      value={category}
      onChange={e => {
        if (e.target.value === "__new__") {
          setCustomCatMode(true);
          setCategory("");
        } else {
          setCategory(e.target.value);
        }
      }}
      style={{
        background: "#0d1a3a",
        border: "1px solid rgba(58,123,213,0.2)", borderRadius: 6,
        padding: "6px 10px", color: "#9ab8d8",
        fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, outline: "none",
        cursor: "pointer", flexShrink: 0,
      }}
    >
      {dedupeCategories([...categories, category]).map(c => (
        <option key={c} value={c} style={{ background: "#0d1a3a" }}>{c}</option>
      ))}
      <option value="__new__" style={{ background: "#0d1a3a" }}>+ New category…</option>
    </select>
  );
}

// ── Outreach Templates editor ───────────────────────────────────────────────
// Editable SMS + email templates sent by the dialer's "Send Info" call
// disposition (dashboard/backend/routers/sms.py send_info_message() and
// integrations.py send_info_email()). Both read these from the
// dialer_settings table at send time via GET /api/dialer/info-template —
// this is the editor for that same store.
function OutreachTemplatesEditor({ categories, onCategoryChange }) {
  const [sms, setSms] = useState("");
  const [emailSubject, setEmailSubject] = useState("");
  const [emailBody, setEmailBody] = useState("");
  const [category, setCategory] = useState("General");
  const [customCatMode, setCustomCatMode] = useState(false);
  const [saved, setSaved] = useState({ sms: "", emailSubject: "", emailBody: "", category: "General" });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);

  useEffect(() => {
    (async () => {
      const r = await fetch("/api/dialer/info-template");
      if (r.ok) {
        const data = await r.json();
        setSms(data.sms || "");
        setEmailSubject(data.email_subject || "");
        setEmailBody(data.email_body || "");
        setCategory(data.category || "General");
        setSaved({ sms: data.sms || "", emailSubject: data.email_subject || "", emailBody: data.email_body || "", category: data.category || "General" });
        onCategoryChange?.(data.category || "General");
      }
      setLoading(false);
    })();
  }, []);

  const dirty = sms !== saved.sms || emailSubject !== saved.emailSubject || emailBody !== saved.emailBody || category !== saved.category;

  const save = async () => {
    setSaving(true);
    try {
      const r = await fetch("/api/dialer/info-template", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sms, email_subject: emailSubject, email_body: emailBody, category }),
      });
      if (r.ok) {
        setSaved({ sms, emailSubject, emailBody, category });
        onCategoryChange?.(category);
        setSavedFlash(true);
        setTimeout(() => setSavedFlash(false), 2500);
      }
    } finally {
      setSaving(false);
    }
  };

  const fieldStyle = {
    width: "100%", background: "rgba(255,255,255,0.04)",
    border: "1px solid rgba(58,123,213,0.2)", borderRadius: 6,
    padding: "10px 12px", color: "#e8f0ff",
    fontFamily: "'Space Grotesk', sans-serif", fontSize: 13,
    outline: "none", resize: "vertical", boxSizing: "border-box",
  };
  const labelStyle = {
    display: "block", marginBottom: 6,
    fontFamily: "'Share Tech Mono', monospace", fontSize: 10,
    color: "#3a5a80", letterSpacing: "0.12em",
  };
  const hintStyle = {
    marginTop: 6, fontFamily: "'Space Grotesk', sans-serif",
    fontSize: 11, color: "#4a6a8a",
  };

  if (loading) {
    return (
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1e3050", letterSpacing: "0.12em" }}>LOADING…</div>
      </div>
    );
  }

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div style={{
        padding: "12px 36px", borderBottom: "1px solid rgba(58,123,213,0.1)",
        display: "flex", alignItems: "center", gap: 12, flexShrink: 0,
      }}>
        <span style={{ flex: 1, fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, color: "#7a9cc0" }}>
          Sent automatically whenever a call is dispositioned <strong style={{ color: "#a080f0" }}>Send Info</strong>. Edits apply to the very next send.
        </span>
        <CategoryPicker
          categories={categories}
          category={category}
          setCategory={setCategory}
          customCatMode={customCatMode}
          setCustomCatMode={setCustomCatMode}
        />
        {savedFlash && (
          <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#34d399", letterSpacing: "0.1em" }}>SAVED ✓</span>
        )}
        <button
          onClick={save}
          disabled={saving || !dirty}
          style={{
            background: dirty ? "linear-gradient(90deg, #2857a0, #3a7bd5)" : "rgba(58,123,213,0.12)",
            border: dirty ? "none" : "1px solid rgba(58,123,213,0.25)",
            borderRadius: 6, color: dirty ? "#fff" : "#6ab0ff",
            fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600,
            fontSize: 12, padding: "6px 16px", flexShrink: 0,
            cursor: saving || !dirty ? "not-allowed" : "pointer",
            opacity: saving ? 0.6 : 1,
          }}
        >{saving ? "Saving..." : dirty ? "Save *" : "Save"}</button>
      </div>

      <div style={{ flex: 1, overflowY: "auto", padding: "24px 36px", display: "flex", flexDirection: "column", gap: 24 }}>
        <div>
          <label style={labelStyle}>SMS MESSAGE</label>
          <textarea
            value={sms}
            onChange={e => setSms(e.target.value)}
            rows={4}
            placeholder="Hey {first_name}, here's that info — https://digigrowthllc.com..."
            style={fieldStyle}
          />
          <div style={hintStyle}>Use <code style={{ color: "#6ab0ff" }}>{"{first_name}"}</code> to insert the contact's first name.</div>
        </div>

        <div style={{ borderTop: "1px solid rgba(58,123,213,0.1)", paddingTop: 20 }}>
          <label style={labelStyle}>EMAIL SUBJECT</label>
          <input
            value={emailSubject}
            onChange={e => setEmailSubject(e.target.value)}
            placeholder="Info as promised"
            style={fieldStyle}
          />
          <div style={hintStyle}>The contact's business name is appended automatically (e.g. "Info as promised — Acme Co").</div>
        </div>

        <div>
          <label style={labelStyle}>EMAIL BODY</label>
          <textarea
            value={emailBody}
            onChange={e => setEmailBody(e.target.value)}
            rows={10}
            placeholder={"{first_name},\n\nHere's the link: https://digigrowthllc.com..."}
            style={fieldStyle}
          />
          <div style={hintStyle}>Use <code style={{ color: "#6ab0ff" }}>{"{first_name}"}</code> to insert the contact's first name.</div>
        </div>
      </div>
    </div>
  );
}

// ── Onboarding Sequence editor ──────────────────────────────────────────────
// Two touches, both backed by dashboard/backend/onboarding_sequence.py
// reading the dialer_settings table at send time via GET
// /api/dialer/onboarding-template; this is the editor for that same store.
// 1. Welcome email — fires immediately when a rep marks an appointment
//    "Closed". No form/booking link (those come tomorrow).
// 2. Onboarding email + SMS — the form link + booking link, sent the next
//    calendar morning after the close (8am ET daily poll).
const ONBOARDING_FIELD_KEYS = [
  "onboarding_welcome_email_subject", "onboarding_welcome_email_body",
  "onboarding_followup_email_subject", "onboarding_followup_email_body",
  "onboarding_followup_sms",
];

function OnboardingKickoffEditor({ categories, onCategoryChange }) {
  const [values, setValues] = useState({});
  const [category, setCategory] = useState("General");
  const [customCatMode, setCustomCatMode] = useState(false);
  const [saved, setSaved] = useState({ category: "General" });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);

  useEffect(() => {
    (async () => {
      const r = await fetch("/api/dialer/onboarding-template");
      if (r.ok) {
        const data = await r.json();
        setValues(data);
        setCategory(data.category || "General");
        setSaved({ ...data, category: data.category || "General" });
        onCategoryChange?.(data.category || "General");
      }
      setLoading(false);
    })();
  }, []);

  const dirty = ONBOARDING_FIELD_KEYS.some(k => (values[k] || "") !== (saved[k] || "")) || category !== saved.category;

  const save = async () => {
    setSaving(true);
    try {
      const r = await fetch("/api/dialer/onboarding-template", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...values, category }),
      });
      if (r.ok) {
        setSaved({ ...values, category });
        onCategoryChange?.(category);
        setSavedFlash(true);
        setTimeout(() => setSavedFlash(false), 2500);
      }
    } finally {
      setSaving(false);
    }
  };

  const fieldStyle = {
    width: "100%", background: "rgba(255,255,255,0.04)",
    border: "1px solid rgba(58,123,213,0.2)", borderRadius: 6,
    padding: "10px 12px", color: "#e8f0ff",
    fontFamily: "'Space Grotesk', sans-serif", fontSize: 13,
    outline: "none", resize: "vertical", boxSizing: "border-box",
  };
  const labelStyle = {
    display: "block", marginBottom: 6,
    fontFamily: "'Share Tech Mono', monospace", fontSize: 10,
    color: "#3a5a80", letterSpacing: "0.12em",
  };
  const headingStyle = {
    display: "block", marginBottom: 8,
    fontFamily: "'Space Grotesk', sans-serif", fontSize: 16, fontWeight: 700,
    color: "#e8f0ff", letterSpacing: "0.01em",
  };
  const hintStyle = {
    marginTop: 6, fontFamily: "'Space Grotesk', sans-serif",
    fontSize: 11, color: "#4a6a8a",
  };

  if (loading) {
    return (
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1e3050", letterSpacing: "0.12em" }}>LOADING…</div>
      </div>
    );
  }

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div style={{
        padding: "12px 36px", borderBottom: "1px solid rgba(58,123,213,0.1)",
        display: "flex", alignItems: "center", gap: 12, flexShrink: 0,
      }}>
        <span style={{ flex: 1, fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, color: "#7a9cc0" }}>
          Welcome email fires immediately when a rep marks an appointment's outcome <strong style={{ color: "#a080f0" }}>Closed</strong> (won). The onboarding email + SMS fire the next morning (8am ET). Edits apply to the very next send.
        </span>
        <CategoryPicker
          categories={categories}
          category={category}
          setCategory={setCategory}
          customCatMode={customCatMode}
          setCustomCatMode={setCustomCatMode}
        />
        {savedFlash && (
          <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#34d399", letterSpacing: "0.1em" }}>SAVED ✓</span>
        )}
        <button
          onClick={save}
          disabled={saving || !dirty}
          style={{
            background: dirty ? "linear-gradient(90deg, #2857a0, #3a7bd5)" : "rgba(58,123,213,0.12)",
            border: dirty ? "none" : "1px solid rgba(58,123,213,0.25)",
            borderRadius: 6, color: dirty ? "#fff" : "#6ab0ff",
            fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600,
            fontSize: 12, padding: "6px 16px", flexShrink: 0,
            cursor: saving || !dirty ? "not-allowed" : "pointer",
            opacity: saving ? 0.6 : 1,
          }}
        >{saving ? "Saving..." : dirty ? "Save *" : "Save"}</button>
      </div>

      <div style={{ flex: 1, overflowY: "auto", padding: "24px 36px", display: "flex", flexDirection: "column", gap: 24 }}>
        <div>
          <label style={headingStyle}>1. Welcome Email (sent immediately)</label>
          <label style={{ ...labelStyle, marginTop: 4 }}>EMAIL SUBJECT</label>
          <input
            value={values.onboarding_welcome_email_subject || ""}
            onChange={e => setValues(v => ({ ...v, onboarding_welcome_email_subject: e.target.value }))}
            placeholder="Welcome to DigiGrowth, {first_name}!"
            style={fieldStyle}
          />
          <div style={{ ...hintStyle, marginBottom: 14 }}>Use <code style={{ color: "#6ab0ff" }}>{"{first_name}"}</code> to insert the client's first name.</div>

          <label style={labelStyle}>EMAIL BODY</label>
          <textarea
            value={values.onboarding_welcome_email_body || ""}
            onChange={e => setValues(v => ({ ...v, onboarding_welcome_email_body: e.target.value }))}
            rows={10}
            placeholder={"Hey {first_name},\n\nWelcome aboard...\n\nKeep an eye out tomorrow morning for your form + booking link."}
            style={fieldStyle}
          />
          <div style={hintStyle}>
            Use <code style={{ color: "#6ab0ff" }}>{"{first_name}"}</code> for the client's first name. No form/booking link here on purpose — those go out in the follow-up below.
          </div>
        </div>

        <div style={{ borderTop: "1px solid rgba(58,123,213,0.1)", paddingTop: 20 }}>
          <label style={headingStyle}>2. Onboarding Email + SMS (sent next morning)</label>
          <div style={{ ...hintStyle, marginTop: 0, marginBottom: 10 }}>
            Sends the client's <strong style={{ color: "#a080f0" }}>client portal</strong> link — their one hub for the intake form, Onboarding Call booking, and campaign stats. Requires a <code style={{ color: "#6ab0ff" }}>clients</code> record already linked to this contact (Clients tab) by the time this fires, or the send is skipped.
          </div>
          <label style={{ ...labelStyle, marginTop: 4 }}>EMAIL SUBJECT</label>
          <input
            value={values.onboarding_followup_email_subject || ""}
            onChange={e => setValues(v => ({ ...v, onboarding_followup_email_subject: e.target.value }))}
            placeholder="Your DigiGrowth client portal, {first_name}"
            style={fieldStyle}
          />
          <div style={{ ...hintStyle, marginBottom: 14 }}>Use <code style={{ color: "#6ab0ff" }}>{"{first_name}"}</code> to insert the client's first name.</div>

          <label style={labelStyle}>EMAIL BODY</label>
          <textarea
            value={values.onboarding_followup_email_body || ""}
            onChange={e => setValues(v => ({ ...v, onboarding_followup_email_body: e.target.value }))}
            rows={10}
            placeholder={"Hey {first_name},\n\nHere's your client portal: {portal_link}"}
            style={{ ...fieldStyle, marginBottom: 14 }}
          />

          <label style={labelStyle}>SMS MESSAGE</label>
          <textarea
            value={values.onboarding_followup_sms || ""}
            onChange={e => setValues(v => ({ ...v, onboarding_followup_sms: e.target.value }))}
            rows={4}
            placeholder="Hey {first_name}, here's your client portal: {portal_link}"
            style={fieldStyle}
          />
          <div style={hintStyle}>
            Use <code style={{ color: "#6ab0ff" }}>{"{first_name}"}</code> for the client's first name and{" "}
            <code style={{ color: "#6ab0ff" }}>{"{portal_link}"}</code> for their client portal link.
          </div>
        </div>
      </div>
    </div>
  );
}

// ── SMS Sequence editor ─────────────────────────────────────────────────────
// Fixed-step outreach script shown as the Inbox's "SEQUENCE" dropdown
// (InboxPanel.jsx). Step keys/labels/order must match routers/sms.py
// SEQUENCE_STEPS. Multiple named sequences can exist (GET /api/sms-sequences);
// exactly one is "active" (the Default) at a time — see the "Set as Default"
// button below and POST /api/sms-sequences/{id}/activate.
const SMS_SEQUENCE_STEPS = [
  { key: "gatekeeper", label: "0. Gatekeeper Message" },
  { key: "curiosity_opener", label: "1. Initial Message" },
  { key: "relevance", label: "2. Primed Message" },
  { key: "guarantee", label: "3. Engaged Message" },
  { key: "ask", label: "4. Call To Action" },
  { key: "cta", label: "5. Booking Link" },
];

const sequenceFieldStyle = {
  width: "100%", background: "rgba(255,255,255,0.04)",
  border: "1px solid rgba(58,123,213,0.2)", borderRadius: 6,
  padding: "10px 12px", color: "#e8f0ff",
  fontFamily: "'Space Grotesk', sans-serif", fontSize: 13,
  outline: "none", resize: "vertical", boxSizing: "border-box",
};
const sequenceLabelStyle = {
  display: "block", marginBottom: 8,
  fontFamily: "'Space Grotesk', sans-serif", fontSize: 16, fontWeight: 700,
  color: "#e8f0ff", letterSpacing: "0.01em",
};
const sequenceHintStyle = {
  marginTop: 6, fontFamily: "'Space Grotesk', sans-serif",
  fontSize: 11, color: "#4a6a8a",
};
const sequenceNameInputStyle = {
  flex: 1, background: "rgba(255,255,255,0.04)",
  border: "1px solid rgba(58,123,213,0.2)", borderRadius: 6,
  padding: "6px 10px", color: "#e8f0ff",
  fontFamily: "'Space Grotesk', sans-serif", fontSize: 13, fontWeight: 600,
  outline: "none",
};

// Shared 5-textarea step form used by both SmsSequenceEditor (editing an
// existing sequence) and NewSequenceEditor (creating one via the generic
// "+ New Template" flow under a category that already holds sequences).
function SequenceStepFields({ steps, setSteps }) {
  return (
    <>
      {SMS_SEQUENCE_STEPS.map((s, i) => (
        <div key={s.key} style={i > 0 ? { borderTop: "1px solid rgba(58,123,213,0.1)", paddingTop: 20 } : undefined}>
          <label style={sequenceLabelStyle}>{s.label}</label>
          <textarea
            value={steps[s.key] || ""}
            onChange={e => setSteps(v => ({ ...v, [s.key]: e.target.value }))}
            rows={4}
            placeholder="Type this step's message..."
            style={sequenceFieldStyle}
          />
          <div style={sequenceHintStyle}>
            Use <code style={{ color: "#6ab0ff" }}>{"{{name}}"}</code>, <code style={{ color: "#6ab0ff" }}>{"{{business}}"}</code>, or <code style={{ color: "#6ab0ff" }}>{"{{opener}}"}</code> — or bracket form <code style={{ color: "#6ab0ff" }}>[Name]</code> / <code style={{ color: "#6ab0ff" }}>[Custom Opener]</code> — to insert the contact's info.
          </div>
        </div>
      ))}
    </>
  );
}

function SmsSequenceEditor({ sequence, categories, onSaved, onDeleted }) {
  const [name, setName] = useState("");
  const [category, setCategory] = useState("General");
  const [steps, setSteps] = useState({});
  const [saved, setSaved] = useState({ name: "", category: "General", steps: {} });
  const [customCatMode, setCustomCatMode] = useState(false);
  const [saving, setSaving] = useState(false);
  const [activating, setActivating] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);
  const [deleteError, setDeleteError] = useState(null);

  useEffect(() => {
    if (!sequence) return;
    setName(sequence.name || "");
    setCategory(sequence.category || "General");
    setSteps(sequence.steps || {});
    setSaved({ name: sequence.name || "", category: sequence.category || "General", steps: sequence.steps || {} });
    setDeleteError(null);
  }, [sequence?.id]);

  if (!sequence) {
    return (
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1e3050", letterSpacing: "0.12em" }}>LOADING…</div>
      </div>
    );
  }

  const dirty = name !== saved.name || category !== saved.category
    || SMS_SEQUENCE_STEPS.some(s => (steps[s.key] || "") !== (saved.steps[s.key] || ""));

  const save = async () => {
    setSaving(true);
    try {
      const r = await fetch(`/api/sms-sequences/${sequence.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim(), category, steps }),
      });
      if (r.ok) {
        setSaved({ name, category, steps });
        setSavedFlash(true);
        setTimeout(() => setSavedFlash(false), 2500);
        onSaved?.();
      }
    } finally {
      setSaving(false);
    }
  };

  const activate = async () => {
    setActivating(true);
    try {
      const r = await fetch(`/api/sms-sequences/${sequence.id}/activate`, { method: "POST" });
      if (r.ok) onSaved?.();
    } finally {
      setActivating(false);
    }
  };

  const deleteSequence = async () => {
    if (!window.confirm(`Delete "${sequence.name}"?`)) return;
    setDeleteError(null);
    const r = await fetch(`/api/sms-sequences/${sequence.id}`, { method: "DELETE" });
    if (r.ok) {
      onDeleted?.();
    } else {
      const data = await r.json().catch(() => ({}));
      setDeleteError(data.detail || "Couldn't delete this sequence.");
    }
  };

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div style={{
        padding: "12px 36px", borderBottom: "1px solid rgba(58,123,213,0.1)",
        display: "flex", alignItems: "center", gap: 12, flexShrink: 0,
      }}>
        <input
          value={name}
          onChange={e => setName(e.target.value)}
          placeholder="Sequence name..."
          style={sequenceNameInputStyle}
        />
        <CategoryPicker
          categories={categories}
          category={category}
          setCategory={setCategory}
          customCatMode={customCatMode}
          setCustomCatMode={setCustomCatMode}
        />
        {savedFlash && (
          <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#34d399", letterSpacing: "0.1em" }}>SAVED ✓</span>
        )}
        <button
          onClick={activate}
          disabled={sequence.is_active || activating}
          title={sequence.is_active ? "This is already the default sequence" : "Make this the sequence shown in the Inbox"}
          style={{
            background: sequence.is_active ? "rgba(52,211,153,0.12)" : "rgba(58,123,213,0.12)",
            border: sequence.is_active ? "1px solid rgba(52,211,153,0.35)" : "1px solid rgba(58,123,213,0.25)",
            borderRadius: 6, color: sequence.is_active ? "#34d399" : "#6ab0ff",
            fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600,
            fontSize: 12, padding: "6px 14px", flexShrink: 0,
            cursor: sequence.is_active || activating ? "not-allowed" : "pointer",
            opacity: activating ? 0.6 : 1,
          }}
        >{sequence.is_active ? "Default ✓" : activating ? "Setting..." : "Set as Default"}</button>
        <button
          onClick={deleteSequence}
          disabled={sequence.is_active}
          title={sequence.is_active ? "Set another sequence as default first" : "Delete this sequence"}
          style={{
            background: "rgba(220,60,60,0.1)",
            border: "1px solid rgba(220,60,60,0.3)",
            borderRadius: 6, color: "#dc3c3c",
            fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600,
            fontSize: 12, padding: "6px 14px", flexShrink: 0,
            cursor: sequence.is_active ? "not-allowed" : "pointer",
            opacity: sequence.is_active ? 0.5 : 1,
          }}
        >Delete</button>
        <button
          onClick={save}
          disabled={saving || !dirty || !name.trim()}
          style={{
            background: dirty && name.trim() ? "linear-gradient(90deg, #2857a0, #3a7bd5)" : "rgba(58,123,213,0.12)",
            border: dirty && name.trim() ? "none" : "1px solid rgba(58,123,213,0.25)",
            borderRadius: 6, color: dirty && name.trim() ? "#fff" : "#6ab0ff",
            fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600,
            fontSize: 12, padding: "6px 16px", flexShrink: 0,
            cursor: saving || !dirty || !name.trim() ? "not-allowed" : "pointer",
            opacity: saving ? 0.6 : 1,
          }}
        >{saving ? "Saving..." : dirty ? "Save *" : "Save"}</button>
      </div>

      {deleteError && (
        <div style={{
          padding: "8px 36px", background: "rgba(220,60,60,0.1)",
          borderBottom: "1px solid rgba(220,60,60,0.2)",
          fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, color: "#dc3c3c",
        }}>{deleteError}</div>
      )}

      <div style={{ padding: "12px 36px 0", fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, color: "#7a9cc0" }}>
        {sequence.is_active
          ? <>This is the <strong style={{ color: "#34d399" }}>default</strong> sequence — shown as the SEQUENCE dropdown in the SMS inbox.</>
          : "Not currently the default. Leave a step blank to skip it."}
      </div>

      <div style={{ flex: 1, overflowY: "auto", padding: "24px 36px", display: "flex", flexDirection: "column", gap: 24 }}>
        <SequenceStepFields steps={steps} setSteps={setSteps} />
      </div>
    </div>
  );
}

// New-sequence form rendered inline in place of the generic Tiptap doc
// editor when creating a "+ New Template" under a category that already
// holds at least one SMS sequence (see `isSequenceCategory` further down).
// Reuses the panel's own title/category state (title doubles as the
// sequence's name) so it fits the existing new-doc flow without a separate
// "New SMS Sequence" action.
function NewSequenceEditor({ title, setTitle, category, setCategory, categories, customCatMode, setCustomCatMode, steps, setSteps, onCreated }) {
  const [saving, setSaving] = useState(false);

  const create = async () => {
    if (!title.trim()) return;
    setSaving(true);
    try {
      const r = await fetch("/api/sms-sequences", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: title.trim(), category, steps }),
      });
      if (r.ok) onCreated?.(await r.json());
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div style={{
        padding: "12px 36px", borderBottom: "1px solid rgba(58,123,213,0.1)",
        display: "flex", alignItems: "center", gap: 12, flexShrink: 0,
      }}>
        <input
          value={title}
          onChange={e => setTitle(e.target.value)}
          placeholder="Sequence name..."
          style={sequenceNameInputStyle}
        />
        <CategoryPicker
          categories={categories}
          category={category}
          setCategory={setCategory}
          customCatMode={customCatMode}
          setCustomCatMode={setCustomCatMode}
        />
        <button
          onClick={create}
          disabled={saving || !title.trim()}
          style={{
            background: title.trim() ? "linear-gradient(90deg, #2857a0, #3a7bd5)" : "rgba(58,123,213,0.12)",
            border: title.trim() ? "none" : "1px solid rgba(58,123,213,0.25)",
            borderRadius: 6, color: title.trim() ? "#fff" : "#6ab0ff",
            fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600,
            fontSize: 12, padding: "6px 16px", flexShrink: 0,
            cursor: saving || !title.trim() ? "not-allowed" : "pointer",
            opacity: saving ? 0.6 : 1,
          }}
        >{saving ? "Creating..." : "Create Sequence"}</button>
      </div>

      <div style={{ padding: "12px 36px 0", fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, color: "#7a9cc0" }}>
        This category already holds an SMS Sequence, so new templates here use the sequence format. Leave a step blank to skip it. New sequences start off <em>not</em> the default — set it as default from its own editor once you're ready to switch to it.
      </div>

      <div style={{ flex: 1, overflowY: "auto", padding: "24px 36px", display: "flex", flexDirection: "column", gap: 24 }}>
        <SequenceStepFields steps={steps} setSteps={setSteps} />
      </div>
    </div>
  );
}

// ── Cold Call Script editor ─────────────────────────────────────────────────
// Fixed 4-section dialer script (Opener/Intro/Main Body/Close) read by
// DialerPanel.jsx during a live call (see GET /dialer/script in
// routers/dialer.py, which just reads whichever row here is default).
// Multiple named scripts can exist (GET /api/cold-call-scripts); exactly
// one is "active" (the Default) at a time — same Set-as-Default pattern as
// SmsSequenceEditor above.
const CALL_SCRIPT_SECTIONS = [
  { key: "opener", label: "Opener" },
  { key: "intro", label: "Intro" },
  { key: "main_body", label: "Main Body" },
  { key: "close", label: "Close" },
];

function ScriptSectionFields({ sections, setSections }) {
  return (
    <>
      {CALL_SCRIPT_SECTIONS.map((s, i) => (
        <div key={s.key} style={i > 0 ? { borderTop: "1px solid rgba(58,123,213,0.1)", paddingTop: 20 } : undefined}>
          <label style={sequenceLabelStyle}>{s.label}</label>
          <textarea
            value={sections[s.key] || ""}
            onChange={e => setSections(v => ({ ...v, [s.key]: e.target.value }))}
            rows={6}
            placeholder="Type this section's script..."
            style={sequenceFieldStyle}
          />
          <div style={sequenceHintStyle}>
            Use <code style={{ color: "#6ab0ff" }}>[Name]</code>, <code style={{ color: "#6ab0ff" }}>[Practice Name]</code>, or <code style={{ color: "#6ab0ff" }}>[custom opener]</code> — filled in automatically when a lead answers.
          </div>
        </div>
      ))}
    </>
  );
}

function CallScriptEditor({ script, categories, onSaved, onDeleted }) {
  const [name, setName] = useState("");
  const [category, setCategory] = useState("General");
  const [sections, setSections] = useState({});
  const [saved, setSaved] = useState({ name: "", category: "General", sections: {} });
  const [customCatMode, setCustomCatMode] = useState(false);
  const [saving, setSaving] = useState(false);
  const [activating, setActivating] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);
  const [deleteError, setDeleteError] = useState(null);

  useEffect(() => {
    if (!script) return;
    setName(script.name || "");
    setCategory(script.category || "General");
    setSections(script.sections || {});
    setSaved({ name: script.name || "", category: script.category || "General", sections: script.sections || {} });
    setDeleteError(null);
  }, [script?.id]);

  if (!script) {
    return (
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1e3050", letterSpacing: "0.12em" }}>LOADING…</div>
      </div>
    );
  }

  const dirty = name !== saved.name || category !== saved.category
    || CALL_SCRIPT_SECTIONS.some(s => (sections[s.key] || "") !== (saved.sections[s.key] || ""));

  const save = async () => {
    setSaving(true);
    try {
      const r = await fetch(`/api/cold-call-scripts/${script.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim(), category, sections }),
      });
      if (r.ok) {
        setSaved({ name, category, sections });
        setSavedFlash(true);
        setTimeout(() => setSavedFlash(false), 2500);
        onSaved?.();
      }
    } finally {
      setSaving(false);
    }
  };

  const activate = async () => {
    setActivating(true);
    try {
      const r = await fetch(`/api/cold-call-scripts/${script.id}/activate`, { method: "POST" });
      if (r.ok) onSaved?.();
    } finally {
      setActivating(false);
    }
  };

  const deleteScript = async () => {
    if (!window.confirm(`Delete "${script.name}"?`)) return;
    setDeleteError(null);
    const r = await fetch(`/api/cold-call-scripts/${script.id}`, { method: "DELETE" });
    if (r.ok) {
      onDeleted?.();
    } else {
      const data = await r.json().catch(() => ({}));
      setDeleteError(data.detail || "Couldn't delete this script.");
    }
  };

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div style={{
        padding: "12px 36px", borderBottom: "1px solid rgba(58,123,213,0.1)",
        display: "flex", alignItems: "center", gap: 12, flexShrink: 0,
      }}>
        <input
          value={name}
          onChange={e => setName(e.target.value)}
          placeholder="Script name..."
          style={sequenceNameInputStyle}
        />
        <CategoryPicker
          categories={categories}
          category={category}
          setCategory={setCategory}
          customCatMode={customCatMode}
          setCustomCatMode={setCustomCatMode}
        />
        {savedFlash && (
          <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#34d399", letterSpacing: "0.1em" }}>SAVED ✓</span>
        )}
        <button
          onClick={activate}
          disabled={script.is_active || activating}
          title={script.is_active ? "This is already the default script" : "Make this the script shown in the Dialer"}
          style={{
            background: script.is_active ? "rgba(52,211,153,0.12)" : "rgba(58,123,213,0.12)",
            border: script.is_active ? "1px solid rgba(52,211,153,0.35)" : "1px solid rgba(58,123,213,0.25)",
            borderRadius: 6, color: script.is_active ? "#34d399" : "#6ab0ff",
            fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600,
            fontSize: 12, padding: "6px 14px", flexShrink: 0,
            cursor: script.is_active || activating ? "not-allowed" : "pointer",
            opacity: activating ? 0.6 : 1,
          }}
        >{script.is_active ? "Default ✓" : activating ? "Setting..." : "Set as Default"}</button>
        <button
          onClick={deleteScript}
          disabled={script.is_active}
          title={script.is_active ? "Set another script as default first" : "Delete this script"}
          style={{
            background: "rgba(220,60,60,0.1)",
            border: "1px solid rgba(220,60,60,0.3)",
            borderRadius: 6, color: "#dc3c3c",
            fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600,
            fontSize: 12, padding: "6px 14px", flexShrink: 0,
            cursor: script.is_active ? "not-allowed" : "pointer",
            opacity: script.is_active ? 0.5 : 1,
          }}
        >Delete</button>
        <button
          onClick={save}
          disabled={saving || !dirty || !name.trim()}
          style={{
            background: dirty && name.trim() ? "linear-gradient(90deg, #2857a0, #3a7bd5)" : "rgba(58,123,213,0.12)",
            border: dirty && name.trim() ? "none" : "1px solid rgba(58,123,213,0.25)",
            borderRadius: 6, color: dirty && name.trim() ? "#fff" : "#6ab0ff",
            fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600,
            fontSize: 12, padding: "6px 16px", flexShrink: 0,
            cursor: saving || !dirty || !name.trim() ? "not-allowed" : "pointer",
            opacity: saving ? 0.6 : 1,
          }}
        >{saving ? "Saving..." : dirty ? "Save *" : "Save"}</button>
      </div>

      {deleteError && (
        <div style={{
          padding: "8px 36px", background: "rgba(220,60,60,0.1)",
          borderBottom: "1px solid rgba(220,60,60,0.2)",
          fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, color: "#dc3c3c",
        }}>{deleteError}</div>
      )}

      <div style={{ padding: "12px 36px 0", fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, color: "#7a9cc0" }}>
        {script.is_active
          ? <>This is the <strong style={{ color: "#34d399" }}>default</strong> script — shown in the Dialer during calls.</>
          : "Not currently the default. Leave a section blank to skip it."}
      </div>

      <div style={{ flex: 1, overflowY: "auto", padding: "24px 36px", display: "flex", flexDirection: "column", gap: 24 }}>
        <ScriptSectionFields sections={sections} setSections={setSections} />
      </div>
    </div>
  );
}

// New-script form rendered inline in place of the generic Tiptap doc editor
// when creating a "+ New Template" under a category that already holds at
// least one Cold Call Script (see `isScriptCategory` further down). Mirrors
// NewSequenceEditor above.
function NewCallScriptEditor({ title, setTitle, category, setCategory, categories, customCatMode, setCustomCatMode, sections, setSections, onCreated }) {
  const [saving, setSaving] = useState(false);

  const create = async () => {
    if (!title.trim()) return;
    setSaving(true);
    try {
      const r = await fetch("/api/cold-call-scripts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: title.trim(), category, sections }),
      });
      if (r.ok) onCreated?.(await r.json());
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div style={{
        padding: "12px 36px", borderBottom: "1px solid rgba(58,123,213,0.1)",
        display: "flex", alignItems: "center", gap: 12, flexShrink: 0,
      }}>
        <input
          value={title}
          onChange={e => setTitle(e.target.value)}
          placeholder="Script name..."
          style={sequenceNameInputStyle}
        />
        <CategoryPicker
          categories={categories}
          category={category}
          setCategory={setCategory}
          customCatMode={customCatMode}
          setCustomCatMode={setCustomCatMode}
        />
        <button
          onClick={create}
          disabled={saving || !title.trim()}
          style={{
            background: title.trim() ? "linear-gradient(90deg, #2857a0, #3a7bd5)" : "rgba(58,123,213,0.12)",
            border: title.trim() ? "none" : "1px solid rgba(58,123,213,0.25)",
            borderRadius: 6, color: title.trim() ? "#fff" : "#6ab0ff",
            fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600,
            fontSize: 12, padding: "6px 16px", flexShrink: 0,
            cursor: saving || !title.trim() ? "not-allowed" : "pointer",
            opacity: saving ? 0.6 : 1,
          }}
        >{saving ? "Creating..." : "Create Script"}</button>
      </div>

      <div style={{ padding: "12px 36px 0", fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, color: "#7a9cc0" }}>
        This category already holds a Cold Call Script, so new templates here use the script format. Leave a section blank to skip it. New scripts start off <em>not</em> the default — set it as default from its own editor once you're ready to switch to it.
      </div>

      <div style={{ flex: 1, overflowY: "auto", padding: "24px 36px", display: "flex", flexDirection: "column", gap: 24 }}>
        <ScriptSectionFields sections={sections} setSections={setSections} />
      </div>
    </div>
  );
}

// ── Appointment Reminders editor ────────────────────────────────────────────
// Editable SMS + email templates for the appointment-reminder pipeline: the
// 24h/6h/1h reminders and the reschedule notice (dashboard/backend/reminder_engine.py,
// sent when a rep books/edits an appointment via BookingForm/AppointmentsSection).
// Backed by GET/PUT /api/dialer/reminder-template — reminder_engine.py reads these
// same keys fresh from dialer_settings at send time. The immediate booking-confirmation
// send was removed (reminder_engine.send_booking_confirmation() is no longer called),
// so that template instance is intentionally left out of this list.
const REMINDER_FIELDS = [
  { heading: "24-Hour Reminder", hint: null, instance: "24h" },
  { heading: "6-Hour Reminder", hint: null, instance: "6h" },
  { heading: "1-Hour Reminder", hint: null, instance: "1h" },
  {
    heading: "Reschedule Notice", hint: "Sent immediately when a rep reschedules a booked appointment.",
    instance: "reschedule",
  },
];

function AppointmentRemindersEditor({ categories, onCategoryChange }) {
  const [values, setValues] = useState({ category: "General" });
  const [saved, setSaved] = useState({ category: "General" });
  const [customCatMode, setCustomCatMode] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);
  const [showQueue, setShowQueue] = useState(false);

  useEffect(() => {
    (async () => {
      const r = await fetch("/api/dialer/reminder-template");
      if (r.ok) {
        const data = await r.json();
        setValues(data);
        setSaved(data);
        onCategoryChange?.(data.category || "General");
      }
      setLoading(false);
    })();
  }, []);

  const allKeys = [
    ...REMINDER_FIELDS.flatMap(f => [
      `reminder_${f.instance}_sms`,
      `reminder_${f.instance}_email_subject`,
      `reminder_${f.instance}_email_body`,
    ]),
    "category",
  ];
  const dirty = allKeys.some(k => (values[k] || "") !== (saved[k] || ""));

  const save = async () => {
    setSaving(true);
    try {
      const r = await fetch("/api/dialer/reminder-template", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });
      if (r.ok) {
        setSaved(values);
        onCategoryChange?.(values.category || "General");
        setSavedFlash(true);
        setTimeout(() => setSavedFlash(false), 2500);
      }
    } finally {
      setSaving(false);
    }
  };

  const fieldStyle = {
    width: "100%", background: "rgba(255,255,255,0.04)",
    border: "1px solid rgba(58,123,213,0.2)", borderRadius: 6,
    padding: "10px 12px", color: "#e8f0ff",
    fontFamily: "'Space Grotesk', sans-serif", fontSize: 13,
    outline: "none", resize: "vertical", boxSizing: "border-box",
  };
  const labelStyle = {
    display: "block", marginBottom: 6,
    fontFamily: "'Share Tech Mono', monospace", fontSize: 10,
    color: "#3a5a80", letterSpacing: "0.12em",
  };
  const headingStyle = {
    display: "block", marginBottom: 8,
    fontFamily: "'Space Grotesk', sans-serif", fontSize: 16, fontWeight: 700,
    color: "#e8f0ff", letterSpacing: "0.01em",
  };
  const hintStyle = {
    marginTop: 6, fontFamily: "'Space Grotesk', sans-serif",
    fontSize: 11, color: "#4a6a8a",
  };

  if (loading) {
    return (
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1e3050", letterSpacing: "0.12em" }}>LOADING…</div>
      </div>
    );
  }

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div style={{
        padding: "12px 36px", borderBottom: "1px solid rgba(58,123,213,0.1)",
        display: "flex", alignItems: "center", gap: 12, flexShrink: 0,
      }}>
        <span style={{ flex: 1, fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, color: "#7a9cc0" }}>
          Sent by the <strong style={{ color: "#a080f0" }}>appointment reminder</strong> pipeline (24h/6h/1h reminders, reschedule notice). Edits apply to the very next send.
        </span>
        <CategoryPicker
          categories={categories}
          category={values.category || "General"}
          setCategory={c => setValues(v => ({ ...v, category: c }))}
          customCatMode={customCatMode}
          setCustomCatMode={setCustomCatMode}
        />
        {savedFlash && (
          <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#34d399", letterSpacing: "0.1em" }}>SAVED ✓</span>
        )}
        <button
          onClick={() => setShowQueue(true)}
          className="btn btn-secondary"
          style={{ fontSize: 12, padding: "6px 14px", whiteSpace: "nowrap", flexShrink: 0 }}
        >View Active Prospects</button>
        <button
          onClick={save}
          disabled={saving || !dirty}
          style={{
            background: dirty ? "linear-gradient(90deg, #2857a0, #3a7bd5)" : "rgba(58,123,213,0.12)",
            border: dirty ? "none" : "1px solid rgba(58,123,213,0.25)",
            borderRadius: 6, color: dirty ? "#fff" : "#6ab0ff",
            fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600,
            fontSize: 12, padding: "6px 16px", flexShrink: 0,
            cursor: saving || !dirty ? "not-allowed" : "pointer",
            opacity: saving ? 0.6 : 1,
          }}
        >{saving ? "Saving..." : dirty ? "Save *" : "Save"}</button>
      </div>

      {showQueue && <SequenceQueueModal sequence="reminder" onClose={() => setShowQueue(false)} />}

      <div style={{ flex: 1, overflowY: "auto", padding: "24px 36px", display: "flex", flexDirection: "column", gap: 24 }}>
        {REMINDER_FIELDS.map((f, i) => {
          const smsKey = `reminder_${f.instance}_sms`;
          const subjectKey = `reminder_${f.instance}_email_subject`;
          const bodyKey = `reminder_${f.instance}_email_body`;
          return (
          <div key={f.instance} style={i > 0 ? { borderTop: "1px solid rgba(58,123,213,0.1)", paddingTop: 20 } : undefined}>
            <label style={headingStyle}>{f.heading}</label>
            {f.hint && <div style={{ ...hintStyle, marginTop: 0, marginBottom: 10 }}>{f.hint}</div>}

            <label style={labelStyle}>SMS MESSAGE</label>
            <textarea
              value={values[smsKey] || ""}
              onChange={e => setValues(v => ({ ...v, [smsKey]: e.target.value }))}
              rows={3}
              placeholder="Hey {first_name}, ..."
              style={fieldStyle}
            />

            <div style={{ marginTop: 14 }}>
              <label style={labelStyle}>EMAIL SUBJECT</label>
              <input
                value={values[subjectKey] || ""}
                onChange={e => setValues(v => ({ ...v, [subjectKey]: e.target.value }))}
                style={fieldStyle}
              />
            </div>

            <div style={{ marginTop: 14 }}>
              <label style={labelStyle}>EMAIL BODY</label>
              <textarea
                value={values[bodyKey] || ""}
                onChange={e => setValues(v => ({ ...v, [bodyKey]: e.target.value }))}
                rows={4}
                placeholder="Hey {first_name}, ..."
                style={fieldStyle}
              />
            </div>

            <div style={hintStyle}>
              Use <code style={{ color: "#6ab0ff" }}>{"{first_name}"}</code> for the prospect's first name,{" "}
              <code style={{ color: "#6ab0ff" }}>{"{when}"}</code> for the appointment time in the prospect's own timezone, and{" "}
              <code style={{ color: "#6ab0ff" }}>{"{Meeting_Link}"}</code> for the actual join link (looked up from the synced Google Calendar event at send time).
            </div>
          </div>
          );
        })}
      </div>
    </div>
  );
}

// ── No Show sequence editor ─────────────────────────────────────────────────
// Editable SMS + email templates for the 4-touch No Show drip
// (dashboard/backend/no_show_sequence.py), fired automatically after a rep
// marks an appointment's outcome "No Show" in the Appointments tab — touch 1
// ~20 minutes later, touch 2 same-day a few hours later, touch 3 the next
// day, touch 4 (the "breakup") on day 3. Backed by GET/PUT
// /api/dialer/no-show-template — no_show_sequence.py reads these same keys
// fresh from dialer_settings at send time. The sequence stops permanently
// the moment the prospect replies on either channel (see stop_sequence_for_reply()
// in no_show_sequence.py). Touch 2 is SMS-only by design — leave its email
// fields blank to skip that channel for that touch, same as it ships by default.
const NO_SHOW_FIELDS = [
  { heading: "Touch 1 — Missed You", hint: "Sent immediately when marked No Show. SMS + email.", instance: "touch1" },
  { heading: "Touch 2 — Same-Day Follow-Up", hint: "3 hours after. SMS only — leave email fields blank to keep it that way.", instance: "touch2" },
  { heading: "Touch 3 — Social Proof", hint: "24 hours after. SMS + email.", instance: "touch3" },
  { heading: "Touch 4 — Final / Breakup", hint: "72 hours after. Closes the loop unless the prospect replies. SMS + email.", instance: "touch4" },
];

function NoShowSequenceEditor({ categories, onCategoryChange }) {
  const [values, setValues] = useState({ category: "General" });
  const [saved, setSaved] = useState({ category: "General" });
  const [customCatMode, setCustomCatMode] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);
  const [showQueue, setShowQueue] = useState(false);

  useEffect(() => {
    (async () => {
      const r = await fetch("/api/dialer/no-show-template");
      if (r.ok) {
        const data = await r.json();
        setValues(data);
        setSaved(data);
        onCategoryChange?.(data.category || "General");
      }
      setLoading(false);
    })();
  }, []);

  const allKeys = [
    ...NO_SHOW_FIELDS.flatMap(f => [
      `no_show_${f.instance}_sms`,
      `no_show_${f.instance}_email_subject`,
      `no_show_${f.instance}_email_body`,
    ]),
    "category",
  ];
  const dirty = allKeys.some(k => (values[k] || "") !== (saved[k] || ""));

  const save = async () => {
    setSaving(true);
    try {
      const r = await fetch("/api/dialer/no-show-template", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });
      if (r.ok) {
        setSaved(values);
        onCategoryChange?.(values.category || "General");
        setSavedFlash(true);
        setTimeout(() => setSavedFlash(false), 2500);
      }
    } finally {
      setSaving(false);
    }
  };

  const fieldStyle = {
    width: "100%", background: "rgba(255,255,255,0.04)",
    border: "1px solid rgba(58,123,213,0.2)", borderRadius: 6,
    padding: "10px 12px", color: "#e8f0ff",
    fontFamily: "'Space Grotesk', sans-serif", fontSize: 13,
    outline: "none", resize: "vertical", boxSizing: "border-box",
  };
  const labelStyle = {
    display: "block", marginBottom: 6,
    fontFamily: "'Share Tech Mono', monospace", fontSize: 10,
    color: "#3a5a80", letterSpacing: "0.12em",
  };
  const headingStyle = {
    display: "block", marginBottom: 8,
    fontFamily: "'Space Grotesk', sans-serif", fontSize: 16, fontWeight: 700,
    color: "#e8f0ff", letterSpacing: "0.01em",
  };
  const hintStyle = {
    marginTop: 6, fontFamily: "'Space Grotesk', sans-serif",
    fontSize: 11, color: "#4a6a8a",
  };

  if (loading) {
    return (
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1e3050", letterSpacing: "0.12em" }}>LOADING…</div>
      </div>
    );
  }

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div style={{
        padding: "12px 36px", borderBottom: "1px solid rgba(58,123,213,0.1)",
        display: "flex", alignItems: "center", gap: 12, flexShrink: 0,
      }}>
        <span style={{ flex: 1, fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, color: "#7a9cc0" }}>
          Fires automatically after an appointment is marked <strong style={{ color: "#a080f0" }}>No Show</strong> in the Appointments tab — 4 touches, stops the moment the prospect replies. Edits apply to the very next send.
        </span>
        <CategoryPicker
          categories={categories}
          category={values.category || "General"}
          setCategory={c => setValues(v => ({ ...v, category: c }))}
          customCatMode={customCatMode}
          setCustomCatMode={setCustomCatMode}
        />
        {savedFlash && (
          <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#34d399", letterSpacing: "0.1em" }}>SAVED ✓</span>
        )}
        <button
          onClick={() => setShowQueue(true)}
          className="btn btn-secondary"
          style={{ fontSize: 12, padding: "6px 14px", whiteSpace: "nowrap", flexShrink: 0 }}
        >View Active Prospects</button>
        <button
          onClick={save}
          disabled={saving || !dirty}
          style={{
            background: dirty ? "linear-gradient(90deg, #2857a0, #3a7bd5)" : "rgba(58,123,213,0.12)",
            border: dirty ? "none" : "1px solid rgba(58,123,213,0.25)",
            borderRadius: 6, color: dirty ? "#fff" : "#6ab0ff",
            fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600,
            fontSize: 12, padding: "6px 16px", flexShrink: 0,
            cursor: saving || !dirty ? "not-allowed" : "pointer",
            opacity: saving ? 0.6 : 1,
          }}
        >{saving ? "Saving..." : dirty ? "Save *" : "Save"}</button>
      </div>

      {showQueue && <SequenceQueueModal sequence="no_show" onClose={() => setShowQueue(false)} />}

      <div style={{ flex: 1, overflowY: "auto", padding: "24px 36px", display: "flex", flexDirection: "column", gap: 24 }}>
        {NO_SHOW_FIELDS.map((f, i) => {
          const smsKey = `no_show_${f.instance}_sms`;
          const subjectKey = `no_show_${f.instance}_email_subject`;
          const bodyKey = `no_show_${f.instance}_email_body`;
          return (
          <div key={f.instance} style={i > 0 ? { borderTop: "1px solid rgba(58,123,213,0.1)", paddingTop: 20 } : undefined}>
            <label style={headingStyle}>{f.heading}</label>
            {f.hint && <div style={{ ...hintStyle, marginTop: 0, marginBottom: 10 }}>{f.hint}</div>}

            <label style={labelStyle}>SMS MESSAGE</label>
            <textarea
              value={values[smsKey] || ""}
              onChange={e => setValues(v => ({ ...v, [smsKey]: e.target.value }))}
              rows={3}
              placeholder="Hey {first_name}, ..."
              style={fieldStyle}
            />

            <div style={{ marginTop: 14 }}>
              <label style={labelStyle}>EMAIL SUBJECT {f.instance === "touch2" && "(leave blank to skip email)"}</label>
              <input
                value={values[subjectKey] || ""}
                onChange={e => setValues(v => ({ ...v, [subjectKey]: e.target.value }))}
                style={fieldStyle}
              />
            </div>

            <div style={{ marginTop: 14 }}>
              <label style={labelStyle}>EMAIL BODY {f.instance === "touch2" && "(leave blank to skip email)"}</label>
              <textarea
                value={values[bodyKey] || ""}
                onChange={e => setValues(v => ({ ...v, [bodyKey]: e.target.value }))}
                rows={4}
                placeholder="Hey {first_name}, ..."
                style={fieldStyle}
              />
            </div>

            <div style={hintStyle}>
              Use <code style={{ color: "#6ab0ff" }}>{"{first_name}"}</code> for the prospect's first name and{" "}
              <code style={{ color: "#6ab0ff" }}>{"{link}"}</code> for the booking link.
            </div>
          </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Cancellation recovery sequence editor ───────────────────────────────────
// Editable SMS + email templates for the 4-touch cancellation-recovery drip
// (dashboard/backend/cancel_sequence.py), fired automatically after a rep
// clicks Cancel on an appointment in the Appointments tab — touch 1
// immediately, touch 2 a few hours later, touch 3 the next day, touch 4 (the
// "breakup") on day 3. Backed by GET/PUT /api/dialer/cancel-template —
// cancel_sequence.py reads these same keys fresh from dialer_settings at
// send time. The sequence stops permanently the moment the prospect replies
// on either channel (see stop_sequence_for_reply() in cancel_sequence.py).
// Touch 2 is SMS-only by design — leave its email fields blank to skip that
// channel for that touch, same as it ships by default.
const CANCEL_FIELDS = [
  { heading: "Touch 1 — No Worries", hint: "Sent immediately when canceled. SMS + email.", instance: "touch1" },
  { heading: "Touch 2 — Same-Day Follow-Up", hint: "3 hours after. SMS only — leave email fields blank to keep it that way.", instance: "touch2" },
  { heading: "Touch 3 — Still Worth 15 Minutes", hint: "24 hours after. SMS + email.", instance: "touch3" },
  { heading: "Touch 4 — Final / Breakup", hint: "72 hours after. Closes the loop unless the prospect replies. SMS + email.", instance: "touch4" },
];

function CancelSequenceEditor({ categories, onCategoryChange }) {
  const [values, setValues] = useState({ category: "General" });
  const [saved, setSaved] = useState({ category: "General" });
  const [customCatMode, setCustomCatMode] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);
  const [showQueue, setShowQueue] = useState(false);

  useEffect(() => {
    (async () => {
      const r = await fetch("/api/dialer/cancel-template");
      if (r.ok) {
        const data = await r.json();
        setValues(data);
        setSaved(data);
        onCategoryChange?.(data.category || "General");
      }
      setLoading(false);
    })();
  }, []);

  const allKeys = [
    ...CANCEL_FIELDS.flatMap(f => [
      `cancel_${f.instance}_sms`,
      `cancel_${f.instance}_email_subject`,
      `cancel_${f.instance}_email_body`,
    ]),
    "category",
  ];
  const dirty = allKeys.some(k => (values[k] || "") !== (saved[k] || ""));

  const save = async () => {
    setSaving(true);
    try {
      const r = await fetch("/api/dialer/cancel-template", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });
      if (r.ok) {
        setSaved(values);
        onCategoryChange?.(values.category || "General");
        setSavedFlash(true);
        setTimeout(() => setSavedFlash(false), 2500);
      }
    } finally {
      setSaving(false);
    }
  };

  const fieldStyle = {
    width: "100%", background: "rgba(255,255,255,0.04)",
    border: "1px solid rgba(58,123,213,0.2)", borderRadius: 6,
    padding: "10px 12px", color: "#e8f0ff",
    fontFamily: "'Space Grotesk', sans-serif", fontSize: 13,
    outline: "none", resize: "vertical", boxSizing: "border-box",
  };
  const labelStyle = {
    display: "block", marginBottom: 6,
    fontFamily: "'Share Tech Mono', monospace", fontSize: 10,
    color: "#3a5a80", letterSpacing: "0.12em",
  };
  const headingStyle = {
    display: "block", marginBottom: 8,
    fontFamily: "'Space Grotesk', sans-serif", fontSize: 16, fontWeight: 700,
    color: "#e8f0ff", letterSpacing: "0.01em",
  };
  const hintStyle = {
    marginTop: 6, fontFamily: "'Space Grotesk', sans-serif",
    fontSize: 11, color: "#4a6a8a",
  };

  if (loading) {
    return (
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1e3050", letterSpacing: "0.12em" }}>LOADING…</div>
      </div>
    );
  }

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div style={{
        padding: "12px 36px", borderBottom: "1px solid rgba(58,123,213,0.1)",
        display: "flex", alignItems: "center", gap: 12, flexShrink: 0,
      }}>
        <span style={{ flex: 1, fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, color: "#7a9cc0" }}>
          Fires automatically after an appointment is marked <strong style={{ color: "#a080f0" }}>Cancel</strong> in the Appointments tab — 4 touches, stops the moment the prospect replies. Edits apply to the very next send.
        </span>
        <CategoryPicker
          categories={categories}
          category={values.category || "General"}
          setCategory={c => setValues(v => ({ ...v, category: c }))}
          customCatMode={customCatMode}
          setCustomCatMode={setCustomCatMode}
        />
        {savedFlash && (
          <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#34d399", letterSpacing: "0.1em" }}>SAVED ✓</span>
        )}
        <button
          onClick={() => setShowQueue(true)}
          className="btn btn-secondary"
          style={{ fontSize: 12, padding: "6px 14px", whiteSpace: "nowrap", flexShrink: 0 }}
        >View Active Prospects</button>
        <button
          onClick={save}
          disabled={saving || !dirty}
          style={{
            background: dirty ? "linear-gradient(90deg, #2857a0, #3a7bd5)" : "rgba(58,123,213,0.12)",
            border: dirty ? "none" : "1px solid rgba(58,123,213,0.25)",
            borderRadius: 6, color: dirty ? "#fff" : "#6ab0ff",
            fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600,
            fontSize: 12, padding: "6px 16px", flexShrink: 0,
            cursor: saving || !dirty ? "not-allowed" : "pointer",
            opacity: saving ? 0.6 : 1,
          }}
        >{saving ? "Saving..." : dirty ? "Save *" : "Save"}</button>
      </div>

      {showQueue && <SequenceQueueModal sequence="cancel" onClose={() => setShowQueue(false)} />}

      <div style={{ flex: 1, overflowY: "auto", padding: "24px 36px", display: "flex", flexDirection: "column", gap: 24 }}>
        {CANCEL_FIELDS.map((f, i) => {
          const smsKey = `cancel_${f.instance}_sms`;
          const subjectKey = `cancel_${f.instance}_email_subject`;
          const bodyKey = `cancel_${f.instance}_email_body`;
          return (
          <div key={f.instance} style={i > 0 ? { borderTop: "1px solid rgba(58,123,213,0.1)", paddingTop: 20 } : undefined}>
            <label style={headingStyle}>{f.heading}</label>
            {f.hint && <div style={{ ...hintStyle, marginTop: 0, marginBottom: 10 }}>{f.hint}</div>}

            <label style={labelStyle}>SMS MESSAGE</label>
            <textarea
              value={values[smsKey] || ""}
              onChange={e => setValues(v => ({ ...v, [smsKey]: e.target.value }))}
              rows={3}
              placeholder="Hey {first_name}, ..."
              style={fieldStyle}
            />

            <div style={{ marginTop: 14 }}>
              <label style={labelStyle}>EMAIL SUBJECT {f.instance === "touch2" && "(leave blank to skip email)"}</label>
              <input
                value={values[subjectKey] || ""}
                onChange={e => setValues(v => ({ ...v, [subjectKey]: e.target.value }))}
                style={fieldStyle}
              />
            </div>

            <div style={{ marginTop: 14 }}>
              <label style={labelStyle}>EMAIL BODY {f.instance === "touch2" && "(leave blank to skip email)"}</label>
              <textarea
                value={values[bodyKey] || ""}
                onChange={e => setValues(v => ({ ...v, [bodyKey]: e.target.value }))}
                rows={4}
                placeholder="Hey {first_name}, ..."
                style={fieldStyle}
              />
            </div>

            <div style={hintStyle}>
              Use <code style={{ color: "#6ab0ff" }}>{"{first_name}"}</code> for the prospect's first name and{" "}
              <code style={{ color: "#6ab0ff" }}>{"{link}"}</code> for the booking link.
            </div>
          </div>
          );
        })}
      </div>
    </div>
  );
}

// ── DM Follow-Up sequence editor ────────────────────────────────────────────
// Editable SMS templates (no email — DM Reach has no email equivalent) for
// the 3-touch DM Follow-Up drip (dashboard/backend/dm_followup_sequence.py),
// fired automatically once a conversation marked DM Reached in the Inbox
// goes 24h without a reply — touch 1 at 24h, touch 2 at 72h, touch 3
// (breakup) at 7 days. Backed by GET/PUT /api/dialer/dm-followup-template —
// dm_followup_sequence.py reads these same keys fresh from dialer_settings
// at send time. Stops the moment the prospect replies and restarts if
// they go quiet again after a later reply — both derived live from message
// timestamps each poll, no explicit stop action needed (see that module's
// docstring for the full mechanism).
const DM_FOLLOWUP_FIELDS = [
  { heading: "Touch 1 — Still Around?", hint: "24 hours after your last message goes unanswered.", instance: "touch1" },
  { heading: "Touch 2 — Value Reminder", hint: "72 hours after your last message goes unanswered.", instance: "touch2" },
  { heading: "Touch 3 — Final / Breakup", hint: "7 days after your last message goes unanswered. Closes the loop unless the prospect replies.", instance: "touch3" },
];

function DmFollowupSequenceEditor({ categories, onCategoryChange }) {
  const [values, setValues] = useState({ category: "General" });
  const [saved, setSaved] = useState({ category: "General" });
  const [customCatMode, setCustomCatMode] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);
  const [showQueue, setShowQueue] = useState(false);

  useEffect(() => {
    (async () => {
      const r = await fetch("/api/dialer/dm-followup-template");
      if (r.ok) {
        const data = await r.json();
        setValues(data);
        setSaved(data);
        onCategoryChange?.(data.category || "General");
      }
      setLoading(false);
    })();
  }, []);

  const allKeys = [
    ...DM_FOLLOWUP_FIELDS.map(f => `dm_followup_${f.instance}_sms`),
    "category",
  ];
  const dirty = allKeys.some(k => (values[k] || "") !== (saved[k] || ""));

  const save = async () => {
    setSaving(true);
    try {
      const r = await fetch("/api/dialer/dm-followup-template", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });
      if (r.ok) {
        setSaved(values);
        onCategoryChange?.(values.category || "General");
        setSavedFlash(true);
        setTimeout(() => setSavedFlash(false), 2500);
      }
    } finally {
      setSaving(false);
    }
  };

  const fieldStyle = {
    width: "100%", background: "rgba(255,255,255,0.04)",
    border: "1px solid rgba(58,123,213,0.2)", borderRadius: 6,
    padding: "10px 12px", color: "#e8f0ff",
    fontFamily: "'Space Grotesk', sans-serif", fontSize: 13,
    outline: "none", resize: "vertical", boxSizing: "border-box",
  };
  const labelStyle = {
    display: "block", marginBottom: 6,
    fontFamily: "'Share Tech Mono', monospace", fontSize: 10,
    color: "#3a5a80", letterSpacing: "0.12em",
  };
  const headingStyle = {
    display: "block", marginBottom: 8,
    fontFamily: "'Space Grotesk', sans-serif", fontSize: 16, fontWeight: 700,
    color: "#e8f0ff", letterSpacing: "0.01em",
  };
  const hintStyle = {
    marginTop: 6, fontFamily: "'Space Grotesk', sans-serif",
    fontSize: 11, color: "#4a6a8a",
  };

  if (loading) {
    return (
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1e3050", letterSpacing: "0.12em" }}>LOADING…</div>
      </div>
    );
  }

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div style={{
        padding: "12px 36px", borderBottom: "1px solid rgba(58,123,213,0.1)",
        display: "flex", alignItems: "center", gap: 12, flexShrink: 0,
      }}>
        <span style={{ flex: 1, fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, color: "#7a9cc0" }}>
          Fires automatically once a conversation marked <strong style={{ color: "#a080f0" }}>DM Reached</strong> in the Inbox goes 24h without a reply — 3 touches, stops on reply, restarts if quiet again. Edits apply to the very next send.
        </span>
        <CategoryPicker
          categories={categories}
          category={values.category || "General"}
          setCategory={c => setValues(v => ({ ...v, category: c }))}
          customCatMode={customCatMode}
          setCustomCatMode={setCustomCatMode}
        />
        {savedFlash && (
          <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#34d399", letterSpacing: "0.1em" }}>SAVED ✓</span>
        )}
        <button
          onClick={() => setShowQueue(true)}
          className="btn btn-secondary"
          style={{ fontSize: 12, padding: "6px 14px", whiteSpace: "nowrap", flexShrink: 0 }}
        >View Active Prospects</button>
        <button
          onClick={save}
          disabled={saving || !dirty}
          style={{
            background: dirty ? "linear-gradient(90deg, #2857a0, #3a7bd5)" : "rgba(58,123,213,0.12)",
            border: dirty ? "none" : "1px solid rgba(58,123,213,0.25)",
            borderRadius: 6, color: dirty ? "#fff" : "#6ab0ff",
            fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600,
            fontSize: 12, padding: "6px 16px", flexShrink: 0,
            cursor: saving || !dirty ? "not-allowed" : "pointer",
            opacity: saving ? 0.6 : 1,
          }}
        >{saving ? "Saving..." : dirty ? "Save *" : "Save"}</button>
      </div>

      {showQueue && <DmFollowUpQueueModal onClose={() => setShowQueue(false)} />}

      <div style={{ flex: 1, overflowY: "auto", padding: "24px 36px", display: "flex", flexDirection: "column", gap: 24 }}>
        {DM_FOLLOWUP_FIELDS.map((f, i) => {
          const smsKey = `dm_followup_${f.instance}_sms`;
          return (
          <div key={f.instance} style={i > 0 ? { borderTop: "1px solid rgba(58,123,213,0.1)", paddingTop: 20 } : undefined}>
            <label style={headingStyle}>{f.heading}</label>
            {f.hint && <div style={{ ...hintStyle, marginTop: 0, marginBottom: 10 }}>{f.hint}</div>}

            <label style={labelStyle}>SMS MESSAGE</label>
            <textarea
              value={values[smsKey] || ""}
              onChange={e => setValues(v => ({ ...v, [smsKey]: e.target.value }))}
              rows={3}
              placeholder="Hey {first_name}, ..."
              style={fieldStyle}
            />

            <div style={hintStyle}>
              Use <code style={{ color: "#6ab0ff" }}>{"{first_name}"}</code> for the prospect's first name and{" "}
              <code style={{ color: "#6ab0ff" }}>{"{link}"}</code> for the booking link.
            </div>
          </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Main panel ───────────────────────────────────────────────────────────────
export default function SOPsPanel() {
  const [activeSection, setActiveSection] = useState("sop");
  const [sops, setSops] = useState([]);
  const [sendInfoCategory, setSendInfoCategory] = useState("General");
  const [noShowCategory, setNoShowCategory] = useState("General");
  const [cancelCategory, setCancelCategory] = useState("General");
  const [dmFollowupCategory, setDmFollowupCategory] = useState("General");
  const [onboardingCategory, setOnboardingCategory] = useState("General");
  const [remCategory, setRemCategory] = useState("General");
  const [sequences, setSequences] = useState([]);
  const [selectedSequenceId, setSelectedSequenceId] = useState(null);
  const [newSequenceSteps, setNewSequenceSteps] = useState({});
  const [callScripts, setCallScripts] = useState([]);
  const [selectedScriptId, setSelectedScriptId] = useState(null);
  const [newScriptSections, setNewScriptSections] = useState({});
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

  const fetchSequences = useCallback(async () => {
    const r = await fetch("/api/sms-sequences");
    if (r.ok) setSequences(await r.json());
  }, []);

  const fetchCallScripts = useCallback(async () => {
    const r = await fetch("/api/cold-call-scripts");
    if (r.ok) setCallScripts(await r.json());
  }, []);

  // The sidebar labels above the pinned Send Info / Appointment Reminders
  // items normally only pick up their saved category once the user opens
  // that specific item (each editor fetches its own category on mount).
  // Fetch those eagerly here (and the full sequences/scripts lists, needed
  // by pseudoItems/categories/isSequenceCategory/isScriptCategory below) so
  // the section renders correctly on first load instead of showing
  // "General" until clicked.
  useEffect(() => {
    if (activeSection !== "outreach_templates") return;
    fetchSequences();
    fetchCallScripts();
    (async () => {
      const [infoR, noShowR, cancelR, dmFollowupR, onboardingR, remR] = await Promise.all([
        fetch("/api/dialer/info-template"),
        fetch("/api/dialer/no-show-template"),
        fetch("/api/dialer/cancel-template"),
        fetch("/api/dialer/dm-followup-template"),
        fetch("/api/dialer/onboarding-template"),
        fetch("/api/dialer/reminder-template"),
      ]);
      if (infoR.ok) setSendInfoCategory((await infoR.json()).category || "General");
      if (noShowR.ok) setNoShowCategory((await noShowR.json()).category || "General");
      if (cancelR.ok) setCancelCategory((await cancelR.json()).category || "General");
      if (dmFollowupR.ok) setDmFollowupCategory((await dmFollowupR.json()).category || "General");
      if (onboardingR.ok) setOnboardingCategory((await onboardingR.json()).category || "General");
      if (remR.ok) setRemCategory((await remR.json()).category || "General");
    })();
  }, [activeSection, fetchSequences, fetchCallScripts]);

  useEffect(() => {
    setSelectedId(null);
    setSelectedItem(null);
    setSelectedSequenceId(null);
    setNewSequenceSteps({});
    setSelectedScriptId(null);
    setNewScriptSections({});
    setIsNew(false);
    setDirty(false);
    setTitle("");
    setCategory("General");
    setContent("");
  }, [activeSection]);

  // Categories assigned only to the pinned Send Info / Appointment Reminders
  // pseudo-docs live in dialer_settings, and SMS Sequence / Cold Call Script
  // categories live on their own tables — none of these are in the `sops`
  // table, so without folding them in here a category created on one of
  // those would be invisible to every other picker in this section
  // (including the regular document editor), making it look like categories
  // silently fail to save.
  const categories = dedupeCategories([
    ...sops.map(s => s.category || "General"),
    ...(activeSection === "outreach_templates"
      ? [
          sendInfoCategory, noShowCategory, cancelCategory, dmFollowupCategory, onboardingCategory, remCategory,
          ...sequences.map(s => s.category || "General"),
          ...callScripts.map(s => s.category || "General"),
        ]
      : []),
  ]);

  // A category counts as "sequence-type"/"script-type" once it already
  // holds at least one SMS sequence / Cold Call Script — see the
  // "+ New Template" auto-detect below.
  const sequenceCategoryKeys = new Set(sequences.map(s => catKey(s.category || "General")));
  const isSequenceCategory = activeSection === "outreach_templates" && isNew && sequenceCategoryKeys.has(catKey(category));
  const scriptCategoryKeys = new Set(callScripts.map(s => catKey(s.category || "General")));
  const isScriptCategory = activeSection === "outreach_templates" && isNew && !isSequenceCategory && scriptCategoryKeys.has(catKey(category));

  const setContent = (html) => {
    suppressNextUpdate.current = true;
    editor?.commands.setContent(html, false);
  };

  const openSOP = (sop) => {
    if (dirty && !window.confirm("Discard unsaved changes?")) return;
    setSelectedId(sop.id);
    setSelectedItem(sop);
    setIsNew(false);
    setDirty(false);
    setCustomCatMode(false);
    setSelectedSequenceId(sop.smsSequence ? sop.sequenceId : null);
    setSelectedScriptId(sop.callScript ? sop.scriptId : null);
    if (sop.sendInfo || sop.noShow || sop.cancelTemplate || sop.dmFollowupTemplate || sop.smsSequence || sop.reminderTemplate || sop.callScript) return;
    setTitle(sop.title);
    setCategory(sop.category || "General");
    setVisibility(sop.visibility || "private");
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
    setSelectedSequenceId(null);
    setNewSequenceSteps({});
    setSelectedScriptId(null);
    setNewScriptSections({});
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

  // The pinned pseudo-docs (Send Info / SMS Sequence(s) / Appointment
  // Reminders) used to always render in their own individually-labeled rows
  // above the real-document list, never joining it — so even when a
  // pseudo-doc's category was set to exactly match a real document's
  // category, they'd still show as separate sections. Folding them into the
  // same grouping as `sops` here is what actually makes matching categories
  // combine into one section instead of just deduplicating near-identical
  // spellings. Each fetched sequence becomes its own pseudo-item (there can
  // be many, unlike Send Info/Reminders which are always exactly one).
  const pseudoItems = activeSection === "outreach_templates" ? [
    { ...SEND_INFO_ITEM,        category: sendInfoCategory, icon: "☎" },
    { ...NO_SHOW_ITEM,          category: noShowCategory,   icon: "🚫" },
    { ...CANCEL_ITEM,           category: cancelCategory,   icon: "✕" },
    { ...DM_FOLLOWUP_ITEM,      category: dmFollowupCategory, icon: "💭" },
    { ...ONBOARDING_ITEM,       category: onboardingCategory, icon: "🎉" },
    ...sequences.map(seq => ({
      id: `seq-${seq.id}`,
      title: seq.name,
      category: seq.category || "General",
      smsSequence: true,
      sequenceId: seq.id,
      icon: "💬",
      isDefault: seq.is_active,
    })),
    ...callScripts.map(cs => ({
      id: `script-${cs.id}`,
      title: cs.name,
      category: cs.category || "General",
      callScript: true,
      scriptId: cs.id,
      icon: "📞",
      isDefault: cs.is_active,
    })),
    { ...REMINDER_TEMPLATE_ITEM, category: remCategory,     icon: "📅" },
  ] : [];

  // Group case/whitespace-insensitively (see catKey above) so pre-existing
  // near-duplicate category strings ("SMS Outreach" vs "sms outreach") still
  // render as one section instead of splitting the list.
  const grouped = [...pseudoItems, ...sops].reduce((acc, item) => {
    const cat = item.category || "General";
    const key = catKey(cat);
    if (!acc[key]) acc[key] = { label: cat.trim(), items: [] };
    acc[key].items.push(item);
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
          {!selectedItem?.sendInfo && !selectedItem?.noShow && !selectedItem?.cancelTemplate && !selectedItem?.dmFollowupTemplate && !selectedItem?.onboardingTemplate && !selectedItem?.smsSequence && !selectedItem?.reminderTemplate && !selectedItem?.callScript && savedFlash && (
            <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#34d399", letterSpacing: "0.1em" }}>SAVED ✓</span>
          )}
          {!selectedItem?.sendInfo && !selectedItem?.noShow && !selectedItem?.cancelTemplate && !selectedItem?.dmFollowupTemplate && !selectedItem?.onboardingTemplate && !selectedItem?.smsSequence && !selectedItem?.reminderTemplate && !selectedItem?.callScript && !isSequenceCategory && !isScriptCategory && showEditor && !selectedItem?.file_name && (
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
          {!selectedItem?.sendInfo && !selectedItem?.noShow && !selectedItem?.cancelTemplate && !selectedItem?.dmFollowupTemplate && !selectedItem?.onboardingTemplate && !selectedItem?.smsSequence && !selectedItem?.reminderTemplate && !selectedItem?.callScript && selectedId !== null && !isNew && (
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
          {Object.entries(grouped).map(([key, { label, items }]) => (
            <div key={key}>
              <div style={{ padding: "8px 16px 4px", fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80", letterSpacing: "0.14em", textTransform: "uppercase" }}>
                {label}
              </div>
              {items.map(item => {
                const isPseudo = item.sendInfo || item.smsSequence || item.reminderTemplate;
                const isActive = selectedId === item.id;
                return (
                  <div
                    key={item.id}
                    onClick={() => openSOP(item)}
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
                    {isPseudo
                      ? <span style={{ fontSize: 11, flexShrink: 0, opacity: 0.7 }}>{item.icon}</span>
                      : item.file_name
                        ? <span style={{ fontSize: 11, flexShrink: 0, opacity: 0.7 }}>{/^audio|^video/.test(item.file_type || "") ? "🎙" : "📎"}</span>
                        : <span style={{ width: 6, height: 6, borderRadius: "50%", flexShrink: 0, background: item.visibility === "public" ? "#34d399" : "#6ab0ff", opacity: 0.8 }} />
                    }
                    <span style={{
                      flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                      fontFamily: "'Space Grotesk', sans-serif", fontSize: 12,
                      color: isActive ? "#e8f0ff" : "#7a9cc0",
                      fontWeight: isActive ? 600 : 400,
                    }}>{item.title}</span>
                    {item.isDefault && (
                      <span style={{
                        fontFamily: "'Share Tech Mono', monospace", fontSize: 8, color: "#34d399",
                        letterSpacing: "0.08em", flexShrink: 0,
                        border: "1px solid rgba(52,211,153,0.4)", borderRadius: 3, padding: "1px 4px",
                      }}>DEFAULT</span>
                    )}
                    {!isPseudo && (
                      <button
                        onClick={e => deleteSOP(item, e)}
                        title="Delete"
                        style={{
                          background: "none", border: "none", cursor: "pointer",
                          color: "#dc3c3c", fontSize: 14, lineHeight: 1, padding: 0,
                          flexShrink: 0, opacity: 0, transition: "opacity 0.15s",
                        }}
                        onMouseEnter={e => e.currentTarget.style.opacity = "1"}
                        onMouseLeave={e => e.currentTarget.style.opacity = "0"}
                      >×</button>
                    )}
                  </div>
                );
              })}
            </div>
          ))}
          </div>
        </div>

        {/* Editor / file viewer pane */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          {selectedItem?.sendInfo ? (
            <OutreachTemplatesEditor categories={categories} onCategoryChange={setSendInfoCategory} />
          ) : selectedItem?.noShow ? (
            <NoShowSequenceEditor categories={categories} onCategoryChange={setNoShowCategory} />
          ) : selectedItem?.cancelTemplate ? (
            <CancelSequenceEditor categories={categories} onCategoryChange={setCancelCategory} />
          ) : selectedItem?.dmFollowupTemplate ? (
            <DmFollowupSequenceEditor categories={categories} onCategoryChange={setDmFollowupCategory} />
          ) : selectedItem?.onboardingTemplate ? (
            <OnboardingKickoffEditor categories={categories} onCategoryChange={setOnboardingCategory} />
          ) : selectedItem?.smsSequence ? (
            <SmsSequenceEditor
              sequence={sequences.find(s => s.id === selectedSequenceId)}
              categories={categories}
              onSaved={fetchSequences}
              onDeleted={() => {
                setSelectedId(null);
                setSelectedItem(null);
                setSelectedSequenceId(null);
                fetchSequences();
              }}
            />
          ) : selectedItem?.callScript ? (
            <CallScriptEditor
              script={callScripts.find(s => s.id === selectedScriptId)}
              categories={categories}
              onSaved={fetchCallScripts}
              onDeleted={() => {
                setSelectedId(null);
                setSelectedItem(null);
                setSelectedScriptId(null);
                fetchCallScripts();
              }}
            />
          ) : selectedItem?.reminderTemplate ? (
            <AppointmentRemindersEditor categories={categories} onCategoryChange={setRemCategory} />
          ) : isSequenceCategory ? (
            <NewSequenceEditor
              title={title} setTitle={setTitle}
              category={category} setCategory={setCategory}
              categories={categories}
              customCatMode={customCatMode} setCustomCatMode={setCustomCatMode}
              steps={newSequenceSteps} setSteps={setNewSequenceSteps}
              onCreated={(created) => {
                setIsNew(false);
                setNewSequenceSteps({});
                setSelectedId(`seq-${created.id}`);
                setSelectedItem({
                  id: `seq-${created.id}`, title: created.name, category: created.category,
                  smsSequence: true, sequenceId: created.id, icon: "💬", isDefault: created.is_active,
                });
                setSelectedSequenceId(created.id);
                fetchSequences();
              }}
            />
          ) : isScriptCategory ? (
            <NewCallScriptEditor
              title={title} setTitle={setTitle}
              category={category} setCategory={setCategory}
              categories={categories}
              customCatMode={customCatMode} setCustomCatMode={setCustomCatMode}
              sections={newScriptSections} setSections={setNewScriptSections}
              onCreated={(created) => {
                setIsNew(false);
                setNewScriptSections({});
                setSelectedId(`script-${created.id}`);
                setSelectedItem({
                  id: `script-${created.id}`, title: created.name, category: created.category,
                  callScript: true, scriptId: created.id, icon: "📞", isDefault: created.is_active,
                });
                setSelectedScriptId(created.id);
                fetchCallScripts();
              }}
            />
          ) : !showEditor ? (
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
                    onKeyDown={e => { if (e.key === "Enter") { setCategory(resolveCategory(category, categories)); setCustomCatMode(false); setDirty(true); } }}
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
                    {dedupeCategories([...categories, category]).map(c => (
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
