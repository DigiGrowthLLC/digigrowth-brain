import React, { useState, useEffect, useCallback, useRef } from "react";
import { T, Tabs, Toggle, inputStyle, Card, Pill, Empty, SectionTitle } from "../ui.jsx";
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
import EmailHandoffQueueModal from "./EmailHandoffQueueModal";
import IdentityWarmupModal from "./IdentityWarmupModal";

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
        fontFamily: T.font,
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
            borderRadius: 5, color: T.textDim, fontSize: 10, padding: "3px 6px", cursor: "pointer",
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
          <span style={{ fontFamily: T.font, fontSize: 11, color: "#6ab0ff", whiteSpace: "nowrap" }}>
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
              color: T.text, fontFamily: T.font,
              fontSize: 12, padding: "5px 10px", outline: "none",
            }}
          />
          <button
            onClick={applyLink}
            style={{
              background: "linear-gradient(90deg, #2857a0, #3a7bd5)", border: "none",
              borderRadius: 5, color: "#fff",
              fontFamily: T.font, fontWeight: 600,
              fontSize: 11, padding: "5px 14px", cursor: "pointer",
            }}
          >Apply</button>
          <button
            onClick={cancelLink}
            style={{
              background: "transparent", border: "1px solid rgba(58,123,213,0.2)",
              borderRadius: 5, color: T.textMute,
              fontFamily: T.font, fontSize: 11,
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
  { id: "sop",                label: "SOPs",                description: "Step-by-step procedures for how the business runs.",                                          newLabel: "New SOP",      placeholder: "SOP title",      noun: "SOP" },
  { id: "business_doc",       label: "Business documents",  description: "Contracts, proposals and other files you keep on hand.",                                         newLabel: "New document", placeholder: "Document title", noun: "document" },
  { id: "outreach_templates", label: "Outreach templates",  description: "Every text, email and script the OS sends or shows, and what makes each one go out.",            newLabel: "New",          placeholder: "Template title", noun: "template" },
];

// What each built-in outreach template is for, in plain words. `purpose`
// decides the "By purpose" grouping in the sidebar and on the overview;
// `when` is the one-line "what makes it go out" shown under the title.
const PURPOSES = [
  { id: "cold",         label: "Cold outreach",        hint: "Getting prospects to reply and book." },
  { id: "sequences",    label: "Inbox text sequences", hint: "Step-by-step texts you send from the Inbox. The Default one is what the Inbox shows." },
  { id: "after_call",   label: "After a call",         hint: "Sent from what you pick when a call ends." },
  { id: "calls",        label: "Call scripts",         hint: "Shown in the dialer while you're on a call." },
  { id: "appointments", label: "Booked calls",         hint: "Reminders and recovery around your sales calls." },
  { id: "new_clients",  label: "New clients",          hint: "Sent once a deal closes." },
  { id: "client_updates", label: "Client updates",     hint: "Sent to clinics you already work with." },
  { id: "docs",         label: "Your saved templates", hint: "Free-form templates you wrote yourself." },
];

const TEMPLATE_META = {
  sendInfo:              { purpose: "after_call",     icon: "phone",    channels: ["Text", "Email"], when: "A call is marked Send Info" },
  gkDeferralTemplate:    { purpose: "after_call",     icon: "mail",     channels: ["Email"],         when: "Front desk says to email the owner" },
  smsSequence:           { purpose: "sequences",      icon: "chat",     channels: ["Text"],          when: "Steps you send from the Inbox", generic: true },
  emailHandoffTemplate:  { purpose: "cold",           icon: "mail",     channels: ["Email"],         when: "A contact is set to Email Handoff (3 emails)" },
  dmFollowupTemplate:    { purpose: "cold",           icon: "chat",     channels: ["Text"],          when: "A DM Reached chat goes 24h without a reply" },
  callScript:            { purpose: "calls",          icon: "phone",    channels: ["Call"],          when: "Shown in the dialer during calls", generic: true },
  reminderTemplate:      { purpose: "appointments",   icon: "calendar", channels: ["Text", "Email"], when: "24h, 6h and 1h before a booked call, and on reschedule" },
  noShow:                { purpose: "appointments",   icon: "calendar", channels: ["Text", "Email"], when: "An appointment is marked No Show (3 touches)" },
  cancelTemplate:        { purpose: "appointments",   icon: "calendar", channels: ["Text", "Email"], when: "An appointment is cancelled (3 touches)" },
  onboardingTemplate:    { purpose: "new_clients",    icon: "spark",    channels: ["Email", "Text"], when: "A deal is marked Closed (won)" },
  clientBookingTemplate: { purpose: "client_updates", icon: "bell",     channels: ["Text"],          when: "A patient books with one of your clients" },
  clientSuccess:         { purpose: "client_updates", icon: "chart",    channels: ["Email", "Text"], when: "Weekly and final campaign reports, milestones, check-ins" },
};
const SPECIAL_FLAGS = Object.keys(TEMPLATE_META);
const metaFor = (item) => {
  const flag = SPECIAL_FLAGS.find(f => item?.[f]);
  return flag ? TEMPLATE_META[flag] : null;
};
const isSpecialItem = (item) => !!metaFor(item);
// Pseudo-item titles used to carry the channel in brackets ("No Show (SMS +
// Email)"); the channel now shows as chips, so strip it from the label.
const cleanTitle = (t) => (t || "").replace(/\s*\((?:SMS|Email)(?:\s*\+\s*(?:SMS|Email))?\)\s*$/i, "");

const readPref = (k, d) => { try { return localStorage.getItem(k) || d; } catch { return d; } };
const writePref = (k, v) => { try { localStorage.setItem(k, v); } catch { /* private mode */ } };

// Channels as one quiet line ("Text · Email") instead of coloured chips.
function ChannelChips({ channels }) {
  return (
    <span style={{ fontSize: 12, color: T.textMute, whiteSpace: "nowrap", flexShrink: 0 }}>{channels.join(" · ")}</span>
  );
}

// Monochrome line icons (replaces the old emoji set).
const ICON_PATHS = {
  chat:     "M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z",
  mail:     "M4 6h16v12H4z M4 7l8 6 8-6",
  phone:    "M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a1 1 0 0 1-1 1A16 16 0 0 1 4 5a1 1 0 0 1 1-1z",
  calendar: "M4 6h16v14H4z M4 10h16 M8 3v4 M16 3v4",
  spark:    "M12 3l2.2 5.8L20 11l-5.8 2.2L12 19l-2.2-5.8L4 11l5.8-2.2z",
  bell:     "M6 16V11a6 6 0 0 1 12 0v5l2 2H4z M10 20a2 2 0 0 0 4 0",
  chart:    "M4 20h16 M7 16v-5 M12 16V7 M17 16v-8",
  doc:      "M6 3h8l4 4v14H6z M14 3v4h4 M9 12h6 M9 16h6",
  pdf:      "M6 3h8l4 4v14H6z M14 3v4h4 M9 14h6",
  audio:    "M12 4a3 3 0 0 1 3 3v5a3 3 0 0 1-6 0V7a3 3 0 0 1 3-3z M6 11a6 6 0 0 0 12 0 M12 17v3",
  video:    "M4 7h11v10H4z M15 10l5-3v10l-5-3",
  file:     "M16 8l-6.5 6.5a2 2 0 0 0 2.8 2.8L19 10.6a4 4 0 0 0-5.7-5.7L6.6 11.6a6 6 0 0 0 8.5 8.5L20 15",
};
function ResIcon({ name, size = 30, active }) {
  return (
    <span style={{
      width: size, height: size, borderRadius: 8, flexShrink: 0, display: "inline-flex", alignItems: "center", justifyContent: "center",
      background: active ? "rgba(77,142,240,0.22)" : "rgba(120,150,210,0.08)", color: active ? "#8fb8ff" : T.textDim,
    }}>
      <svg width={size * 0.53} height={size * 0.53} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d={ICON_PATHS[name] || ICON_PATHS.doc} />
      </svg>
    </span>
  );
}

const fmtUpdated = (d) => {
  if (!d) return "";
  const dt = new Date(d);
  const days = Math.floor((Date.now() - dt.getTime()) / 86400000);
  if (days <= 0) return "Updated today";
  if (days === 1) return "Updated yesterday";
  if (days < 30) return `Updated ${days} days ago`;
  return `Updated ${dt.toLocaleDateString(undefined, { month: "short", day: "numeric", year: dt.getFullYear() === new Date().getFullYear() ? undefined : "numeric" })}`;
};

const docKind = (item) => item.file_name
  ? (/^audio/.test(item.file_type || "") ? { icon: "audio", label: "Audio" } : /^video/.test(item.file_type || "") ? { icon: "video", label: "Video" } : /\/pdf$/.test(item.file_type || "") ? { icon: "pdf", label: "PDF" } : { icon: "file", label: "File" })
  : { icon: "doc", label: "Doc" };

const btnBase = {
  borderRadius: 8, fontFamily: T.font, fontWeight: 600, fontSize: 13,
  padding: "7px 14px", cursor: "pointer", whiteSpace: "nowrap",
};
const btnPrimary = { ...btnBase, background: "linear-gradient(90deg, #2857a0, #3a7bd5)", border: "none", color: "#fff" };
const btnGhost = { ...btnBase, background: "rgba(77,142,240,0.1)", border: `1px solid ${T.lineStrong}`, color: "#8fb8ff" };
const btnDanger = { ...btnBase, background: "rgba(240,106,106,0.1)", border: "1px solid rgba(240,106,106,0.3)", color: T.bad };

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

// Same pattern again, for the client booking-alert SMS — backed by GET/PUT
// /api/dialer/client-booking-template. SMS-only, single template, addressed
// to the CLIENT (business owner) rather than a prospect/lead — the only
// template on this page that is. Fires automatically the instant a new
// appointment is booked for one of the client's leads (CRM or client
// portal self-booking) — see client_booking_notification.py.
const CLIENT_BOOKING_PSEUDO_ID = "__client_booking__";
const CLIENT_BOOKING_ITEM = { id: CLIENT_BOOKING_PSEUDO_ID, title: "Client Booking Alert (SMS)", clientBookingTemplate: true };

// AI client success manager: weekly + final campaign reports to each client
// (ClientSuccessEditor below, /api/client-success/*).
const CLIENT_SUCCESS_PSEUDO_ID = "__client_success__";
const CLIENT_SUCCESS_ITEM = { id: CLIENT_SUCCESS_PSEUDO_ID, title: "Client Success Templates", clientSuccess: true };

// Same pattern again, for the email-handoff opener — backed by GET/PUT
// /api/dialer/email-handoff-template. Email-only, a one-time copy of the SMS
// "Free Offer V.1.3" sequence's steps kept in its own store (dialer_settings
// email_handoff_* keys, not sms_sequences) so editing it here never touches
// the SMS sequence. Only the "Initial Message" step is auto-sent — fires the
// moment a contact's status is set to "email-handoff" (crm.py's
// _fire_email_handoff, called from the same status-transition sites as the
// SMS handoff: PATCH /contacts/{id}, the disposition endpoint, bulk
// set_status, and contact create/import) — e.g. after a gatekeeper redirects
// outreach to an email address instead of a phone number. Same status
// dropdown as SMS Handoff in the CRM/Inbox, plus its own "Email Handoff"
// disposition button in the dialer's post-call grid (dispositions.js).
const EMAIL_HANDOFF_PSEUDO_ID = "__email_handoff__";
const EMAIL_HANDOFF_ITEM = { id: EMAIL_HANDOFF_PSEUDO_ID, title: "Email Handoff (Email)", emailHandoffTemplate: true };

// Same pattern again, for the "Gatekeeper Deferral" status — backed by
// GET/PUT /api/dialer/gatekeeper-deferral-template. Email-only. Setting a
// contact to Gatekeeper Deferral (a front desk said to email the owner)
// queues the same personalized video as Send Info; once it's made, this
// email goes to the address on the contact (send_info_queue.py).
const GK_DEFERRAL_PSEUDO_ID = "__gk_deferral__";
const GK_DEFERRAL_ITEM = { id: GK_DEFERRAL_PSEUDO_ID, title: "Gatekeeper Deferral (Email)", gkDeferralTemplate: true };

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
          padding: "6px 10px", color: T.textDim,
          fontFamily: T.font, fontSize: 12, outline: "none",
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
        padding: "6px 10px", color: T.textDim,
        fontFamily: T.font, fontSize: 12, outline: "none",
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
    border: `1px solid ${T.lineStrong}`, borderRadius: 8,
    padding: "10px 12px", lineHeight: 1.5, color: T.text,
    fontFamily: T.font, fontSize: 13,
    outline: "none", resize: "vertical", boxSizing: "border-box",
  };
  const labelStyle = {
    display: "block", marginBottom: 6,
    fontFamily: T.font, fontSize: 12.5, fontWeight: 600,
    color: T.textDim,
  };
  const hintStyle = {
    marginTop: 6, fontFamily: T.font,
    fontSize: 12, color: T.textMute, lineHeight: 1.5,
  };

  if (loading) {
    return (
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ fontSize: 13, color: T.textMute }}>Loading…</div>
      </div>
    );
  }

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div style={{
        padding: "12px 36px", borderBottom: "1px solid rgba(58,123,213,0.1)",
        display: "flex", alignItems: "center", gap: 12, flexShrink: 0,
      }}>
        <span style={{ flex: 1, fontFamily: T.font, fontSize: 13, color: T.textDim, lineHeight: 1.5 }}>
          Sent automatically whenever a call is dispositioned <strong style={{ color: "#8fb8ff" }}>Send Info</strong>. Edits apply to the very next send.
        </span>
        <CategoryPicker
          categories={categories}
          category={category}
          setCategory={setCategory}
          customCatMode={customCatMode}
          setCustomCatMode={setCustomCatMode}
        />
        {savedFlash && (
          <span style={{ fontSize: 12.5, color: T.good, fontWeight: 600 }}>Saved ✓</span>
        )}
        <button
          onClick={save}
          disabled={saving || !dirty}
          style={{
            background: dirty ? "linear-gradient(90deg, #2857a0, #3a7bd5)" : "rgba(58,123,213,0.12)",
            border: dirty ? "none" : "1px solid rgba(58,123,213,0.25)",
            borderRadius: 6, color: dirty ? "#fff" : "#6ab0ff",
            fontFamily: T.font, fontWeight: 600,
            fontSize: 12, padding: "6px 16px", flexShrink: 0,
            cursor: saving || !dirty ? "not-allowed" : "pointer",
            opacity: saving ? 0.6 : 1,
          }}
        >{saving ? "Saving…" : dirty ? "Save changes" : "Save"}</button>
      </div>

      <div style={{ flex: 1, overflowY: "auto", padding: "24px 36px", display: "flex", flexDirection: "column", gap: 24 }}>
        <div>
          <label style={labelStyle}>Text message</label>
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
          <label style={labelStyle}>Email subject</label>
          <input
            value={emailSubject}
            onChange={e => setEmailSubject(e.target.value)}
            placeholder="Info as promised"
            style={fieldStyle}
          />
          <div style={hintStyle}>The contact's business name is appended automatically (e.g. "Info as promised — Acme Co").</div>
        </div>

        <div>
          <label style={labelStyle}>Email body</label>
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

// ── Gatekeeper Deferral editor ──────────────────────────────────────────────
// The email integrations.gatekeeper_deferral_email() sends once the
// personalized video for a Gatekeeper Deferral contact is ready.
function GatekeeperDeferralEditor({ categories, onCategoryChange }) {
  const [emailSubject, setEmailSubject] = useState("");
  const [emailBody, setEmailBody] = useState("");
  const [category, setCategory] = useState("General");
  const [customCatMode, setCustomCatMode] = useState(false);
  const [saved, setSaved] = useState({ emailSubject: "", emailBody: "", category: "General" });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);

  useEffect(() => {
    (async () => {
      const r = await fetch("/api/dialer/gatekeeper-deferral-template");
      if (r.ok) {
        const data = await r.json();
        setEmailSubject(data.email_subject || "");
        setEmailBody(data.email_body || "");
        setCategory(data.category || "General");
        setSaved({ emailSubject: data.email_subject || "", emailBody: data.email_body || "", category: data.category || "General" });
        onCategoryChange?.(data.category || "General");
      }
      setLoading(false);
    })();
  }, []);

  const dirty = emailSubject !== saved.emailSubject || emailBody !== saved.emailBody || category !== saved.category;

  const save = async () => {
    setSaving(true);
    try {
      const r = await fetch("/api/dialer/gatekeeper-deferral-template", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email_subject: emailSubject, email_body: emailBody, category }),
      });
      if (r.ok) {
        setSaved({ emailSubject, emailBody, category });
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
    border: `1px solid ${T.lineStrong}`, borderRadius: 8,
    padding: "10px 12px", lineHeight: 1.5, color: T.text,
    fontFamily: T.font, fontSize: 13,
    outline: "none", resize: "vertical", boxSizing: "border-box",
  };
  const labelStyle = {
    display: "block", marginBottom: 6,
    fontFamily: T.font, fontSize: 12.5, fontWeight: 600,
    color: T.textDim,
  };
  const hintStyle = {
    marginTop: 6, fontFamily: T.font,
    fontSize: 12, color: T.textMute, lineHeight: 1.6,
  };
  const code = (t) => <code style={{ color: "#6ab0ff" }}>{t}</code>;

  if (loading) {
    return (
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ fontSize: 13, color: T.textMute }}>Loading…</div>
      </div>
    );
  }

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div style={{
        padding: "12px 36px", borderBottom: "1px solid rgba(58,123,213,0.1)",
        display: "flex", alignItems: "center", gap: 12, flexShrink: 0,
      }}>
        <span style={{ flex: 1, fontFamily: T.font, fontSize: 13, color: T.textDim, lineHeight: 1.5 }}>
          Sent when a contact is set to <strong style={{ color: "#8fb8ff" }}>Gatekeeper Deferral</strong>, once their personalized video is ready. Goes to the email on the contact, so put the address the front desk gave you there first.
        </span>
        <CategoryPicker
          categories={categories}
          category={category}
          setCategory={setCategory}
          customCatMode={customCatMode}
          setCustomCatMode={setCustomCatMode}
        />
        {savedFlash && (
          <span style={{ fontSize: 12.5, color: T.good, fontWeight: 600 }}>Saved ✓</span>
        )}
        <button
          onClick={save}
          disabled={saving || !dirty}
          style={{
            background: dirty ? "linear-gradient(90deg, #2857a0, #3a7bd5)" : "rgba(58,123,213,0.12)",
            border: dirty ? "none" : "1px solid rgba(58,123,213,0.25)",
            borderRadius: 6, color: dirty ? "#fff" : "#6ab0ff",
            fontFamily: T.font, fontWeight: 600,
            fontSize: 12, padding: "6px 16px", flexShrink: 0,
            cursor: saving || !dirty ? "not-allowed" : "pointer",
            opacity: saving ? 0.6 : 1,
          }}
        >{saving ? "Saving…" : dirty ? "Save changes" : "Save"}</button>
      </div>

      <div style={{ flex: 1, overflowY: "auto", padding: "24px 36px", display: "flex", flexDirection: "column", gap: 24 }}>
        <div>
          <label style={labelStyle}>Email subject</label>
          <input
            value={emailSubject}
            onChange={e => setEmailSubject(e.target.value)}
            style={fieldStyle}
          />
          <div style={hintStyle}>
            {code("{receptionist}")} and {code("{first_name}")} work here too. The business name is appended automatically
            (e.g. "Following up on my chat with Sophie — Acme PT").
          </div>
        </div>

        <div>
          <label style={labelStyle}>Email body</label>
          <textarea
            value={emailBody}
            onChange={e => setEmailBody(e.target.value)}
            rows={12}
            style={fieldStyle}
          />
          <div style={hintStyle}>
            {code("{first_name}")} the owner's first name · {code("{loom_link}")} their personalized video ·{" "}
            {code("{receptionist}")} becomes just their name ("Sophie") when the text thread or your call notes name the
            person (e.g. "this is Sophie", "-Sophie", or a note like "receptionist Sophie"), otherwise "your receptionist".
          </div>
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
  "onboarding_nudge_email_subject", "onboarding_nudge_email_body",
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
    border: `1px solid ${T.lineStrong}`, borderRadius: 8,
    padding: "10px 12px", lineHeight: 1.5, color: T.text,
    fontFamily: T.font, fontSize: 13,
    outline: "none", resize: "vertical", boxSizing: "border-box",
  };
  const labelStyle = {
    display: "block", marginBottom: 6,
    fontFamily: T.font, fontSize: 12.5, fontWeight: 600,
    color: T.textDim,
  };
  const headingStyle = {
    display: "block", marginBottom: 8,
    fontFamily: T.font, fontSize: 16, fontWeight: 700,
    color: T.text, letterSpacing: "0.01em",
  };
  const hintStyle = {
    marginTop: 6, fontFamily: T.font,
    fontSize: 12, color: T.textMute, lineHeight: 1.5,
  };

  if (loading) {
    return (
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ fontSize: 13, color: T.textMute }}>Loading…</div>
      </div>
    );
  }

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div style={{
        padding: "12px 36px", borderBottom: "1px solid rgba(58,123,213,0.1)",
        display: "flex", alignItems: "center", gap: 12, flexShrink: 0,
      }}>
        <span style={{ flex: 1, fontFamily: T.font, fontSize: 13, color: T.textDim, lineHeight: 1.5 }}>
          Welcome email fires immediately when a rep marks an appointment's outcome <strong style={{ color: "#8fb8ff" }}>Closed</strong> (won). The onboarding email + SMS fire the next morning (8am ET), and the reminder email 3 days later if no onboarding step is done yet. Edits apply to the very next send.
        </span>
        <CategoryPicker
          categories={categories}
          category={category}
          setCategory={setCategory}
          customCatMode={customCatMode}
          setCustomCatMode={setCustomCatMode}
        />
        {savedFlash && (
          <span style={{ fontSize: 12.5, color: T.good, fontWeight: 600 }}>Saved ✓</span>
        )}
        <button
          onClick={save}
          disabled={saving || !dirty}
          style={{
            background: dirty ? "linear-gradient(90deg, #2857a0, #3a7bd5)" : "rgba(58,123,213,0.12)",
            border: dirty ? "none" : "1px solid rgba(58,123,213,0.25)",
            borderRadius: 6, color: dirty ? "#fff" : "#6ab0ff",
            fontFamily: T.font, fontWeight: 600,
            fontSize: 12, padding: "6px 16px", flexShrink: 0,
            cursor: saving || !dirty ? "not-allowed" : "pointer",
            opacity: saving ? 0.6 : 1,
          }}
        >{saving ? "Saving…" : dirty ? "Save changes" : "Save"}</button>
      </div>

      <div style={{ flex: 1, overflowY: "auto", padding: "24px 36px", display: "flex", flexDirection: "column", gap: 24 }}>
        <div>
          <label style={headingStyle}>1. Welcome Email (sent immediately)</label>
          <label style={{ ...labelStyle, marginTop: 4 }}>Email subject</label>
          <input
            value={values.onboarding_welcome_email_subject || ""}
            onChange={e => setValues(v => ({ ...v, onboarding_welcome_email_subject: e.target.value }))}
            placeholder="Welcome to DigiGrowth, {first_name}!"
            style={fieldStyle}
          />
          <div style={{ ...hintStyle, marginBottom: 14 }}>Use <code style={{ color: "#6ab0ff" }}>{"{first_name}"}</code> to insert the client's first name.</div>

          <label style={labelStyle}>Email body</label>
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
            Sends the client's <strong style={{ color: "#8fb8ff" }}>client portal</strong> link — their one hub for the intake form, Onboarding Call booking, and campaign stats. Requires a <code style={{ color: "#6ab0ff" }}>clients</code> record already linked to this contact (Clients tab) by the time this fires, or the send is skipped.
          </div>
          <label style={{ ...labelStyle, marginTop: 4 }}>Email subject</label>
          <input
            value={values.onboarding_followup_email_subject || ""}
            onChange={e => setValues(v => ({ ...v, onboarding_followup_email_subject: e.target.value }))}
            placeholder="Your DigiGrowth client portal, {first_name}"
            style={fieldStyle}
          />
          <div style={{ ...hintStyle, marginBottom: 14 }}>Use <code style={{ color: "#6ab0ff" }}>{"{first_name}"}</code> to insert the client's first name.</div>

          <label style={labelStyle}>Email body</label>
          <textarea
            value={values.onboarding_followup_email_body || ""}
            onChange={e => setValues(v => ({ ...v, onboarding_followup_email_body: e.target.value }))}
            rows={10}
            placeholder={"Hey {first_name},\n\nHere's your client portal: {portal_link}"}
            style={{ ...fieldStyle, marginBottom: 14 }}
          />

          <label style={labelStyle}>Text message</label>
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

        <div style={{ borderTop: "1px solid rgba(58,123,213,0.1)", paddingTop: 20 }}>
          <label style={headingStyle}>3. Onboarding Reminder Email (3 days after the portal email)</label>
          <div style={{ ...hintStyle, marginTop: 0, marginBottom: 10 }}>
            Only sent if the client hasn't completed <strong style={{ color: "#8fb8ff" }}>any</strong> onboarding step in their portal yet (no Next Steps item ticked, no intake form section completed). Email only.
          </div>
          <label style={{ ...labelStyle, marginTop: 4 }}>Email subject</label>
          <input
            value={values.onboarding_nudge_email_subject || ""}
            onChange={e => setValues(v => ({ ...v, onboarding_nudge_email_subject: e.target.value }))}
            placeholder="Quick reminder about your onboarding, {first_name}"
            style={fieldStyle}
          />
          <div style={{ ...hintStyle, marginBottom: 14 }}>Use <code style={{ color: "#6ab0ff" }}>{"{first_name}"}</code> to insert the client's first name.</div>

          <label style={labelStyle}>Email body</label>
          <textarea
            value={values.onboarding_nudge_email_body || ""}
            onChange={e => setValues(v => ({ ...v, onboarding_nudge_email_body: e.target.value }))}
            rows={10}
            placeholder={"Hey {first_name},\n\nJust a quick reminder to fill out your onboarding steps: {portal_link}"}
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

// ── Client Success Templates ────────────────────────────────────────────────
// Shared wording for the AI Client Success Manager. Everything per client
// (reports, approvals, health, questions, patient quality) lives in
// Clients -> client -> Agents -> Client Success Manager (ClientSuccessAgent.jsx).
// Backed by /api/client-success/settings (dashboard/backend/client_success.py).
const CSM_FIELDS = [
  "csm_enabled", "csm_send_email", "csm_send_sms",
  "csm_weekly_email_subject", "csm_weekly_email_body", "csm_weekly_sms",
  "csm_final_email_subject", "csm_final_email_body", "csm_final_sms", "csm_ai_brief",
  "csm_milestones_channel", "csm_ms_first_lead", "csm_ms_halfway", "csm_ms_goal_hit",
  "csm_checkins_enabled", "csm_checkin_subject", "csm_checkin_body", "csm_final_testimonial_text",
];
const CSM_MILESTONES = [
  ["first_lead", "First lead", "The first lead comes in after launch."],
  ["halfway", "Halfway to goal", "Bookings reach half the campaign goal."],
  ["goal_hit", "Goal reached", "Bookings reach the campaign goal."],
];
const csmOn = (v) => ["on", "true", "1", "yes"].includes(String(v || "").toLowerCase());

function ClientSuccessEditor({ categories, onCategoryChange }) {
  const [values, setValues] = useState({});
  const [saved, setSaved] = useState({});
  const [category, setCategory] = useState("Client Success");
  const [customCatMode, setCustomCatMode] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);
  const [view, setView] = useState("reports");

  useEffect(() => {
    (async () => {
      const r = await fetch("/api/client-success/settings");
      if (r.ok) {
        const data = await r.json();
        setValues(data);
        setSaved({ ...data, category: data.category || "Client Success" });
        setCategory(data.category || "Client Success");
        onCategoryChange?.(data.category || "Client Success");
      }
      setLoading(false);
    })();
  }, []);

  const dirty = CSM_FIELDS.some(k => (values[k] || "") !== (saved[k] || "")) || category !== saved.category;
  const set = (k, v) => setValues(p => ({ ...p, [k]: v }));
  const flip = (k) => set(k, csmOn(values[k]) ? "off" : "on");

  const save = async () => {
    setSaving(true);
    try {
      const r = await fetch("/api/client-success/settings", {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...values, category }),
      });
      if (r.ok) {
        setSaved({ ...values, category });
        onCategoryChange?.(category);
        setSavedFlash(true);
        setTimeout(() => setSavedFlash(false), 2500);
      }
    } finally { setSaving(false); }
  };

  if (loading) return <div style={{ flex: 1, display: "grid", placeItems: "center", color: T.textMute }}>Loading…</div>;

  const field = (k, label, rows) => (
    <label style={{ display: "grid", gap: 6, marginTop: 14 }}>
      <span style={{ fontSize: 12.5, fontWeight: 600, color: T.textDim }}>{label}</span>
      {rows ? <textarea rows={rows} style={{ ...inputStyle, resize: "vertical", lineHeight: 1.5 }} value={values[k] || ""} onChange={e => set(k, e.target.value)} />
        : <input style={inputStyle} value={values[k] || ""} onChange={e => set(k, e.target.value)} />}
    </label>
  );
  const hint = (t) => <div style={{ fontSize: 12.5, color: T.textMute, marginTop: 8, lineHeight: 1.5 }}>{t}</div>;

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div style={{ padding: "14px 36px", borderBottom: `1px solid ${T.line}`, display: "flex", alignItems: "center", gap: 14, flexShrink: 0, flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 260, fontSize: 13, color: T.textDim, lineHeight: 1.5 }}>
          Shared wording for the AI Client Success Manager. Each client's reports, approvals, health and questions are in <b style={{ color: T.text }}>Clients → client → Agents → Client Success Manager</b>.
        </div>
        <Toggle on={csmOn(values.csm_enabled)} onChange={() => flip("csm_enabled")} label={csmOn(values.csm_enabled) ? "Running" : "Paused for all clients"} />
        <CategoryPicker categories={categories} category={category} setCategory={setCategory} customCatMode={customCatMode} setCustomCatMode={setCustomCatMode} />
        {savedFlash && <span style={{ fontSize: 12.5, color: T.good, fontWeight: 600 }}>Saved ✓</span>}
        <button className="btn btn-primary" onClick={save} disabled={saving || !dirty}>{saving ? "Saving…" : "Save"}</button>
      </div>

      <div style={{ padding: "6px 36px 0", flexShrink: 0 }}>
        <Tabs value={view} onChange={setView} tabs={[
          { id: "reports", label: "Report emails" },
          { id: "final", label: "Final report" },
          { id: "milestones", label: "Milestone texts" },
          { id: "onboarding", label: "Onboarding check-ins" },
          { id: "brief", label: "AI writing style" },
        ]} />
      </div>

      <div style={{ flex: 1, overflowY: "auto", padding: "8px 36px 40px" }}>
        <div style={{ maxWidth: 760 }}>
          {view === "reports" && (
            <>
              <div style={{ display: "flex", gap: 24, marginTop: 16 }}>
                <Toggle on={csmOn(values.csm_send_email)} onChange={() => flip("csm_send_email")} label="Send by email" />
                <Toggle on={csmOn(values.csm_send_sms)} onChange={() => flip("csm_send_sms")} label="Also send by text" />
              </div>
              {hint("Weekly reports go out automatically every Monday at 10am ET. Merge fields: {first_name} {clinic} {week} {link}. Texts are off by default; keep them to plain characters (no em dashes, curly quotes or emoji).")}
              {field("csm_weekly_email_subject", "Weekly report: email subject")}
              {field("csm_weekly_email_body", "Weekly report: email body", 8)}
              {field("csm_weekly_sms", "Weekly report: text message", 3)}
            </>
          )}
          {view === "final" && (
            <>
              {hint("The final report is drafted when a campaign ends and only goes out once you approve it in the client's Client Success Manager. It includes \"Your next campaign\" (written by Claude from the results) and the testimonial ask below.")}
              {field("csm_final_email_subject", "Final report: email subject")}
              {field("csm_final_email_body", "Final report: email body", 8)}
              {field("csm_final_sms", "Final report: text message", 3)}
              {field("csm_final_testimonial_text", "\"Share your experience\" section (testimonial ask)", 4)}
              {hint("Merge fields: {clinic} {first_name} {review_link_line} (a Google review link when DIGIGROWTH_REVIEW_URL is set).")}
            </>
          )}
          {view === "milestones" && (
            <>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 16, flexWrap: "wrap" }}>
                <span style={{ fontSize: 13, color: T.textDim, marginRight: 4 }}>Send milestones by</span>
                {[["sms", "Text"], ["email", "Email"], ["off", "Off"]].map(([ch, label]) => {
                  const on = (values.csm_milestones_channel || "sms") === ch;
                  return <button key={ch} onClick={() => set("csm_milestones_channel", ch)} style={{ border: `1px solid ${on ? "rgba(77,142,240,0.5)" : T.line}`, background: on ? T.accentSoft : "transparent", color: on ? T.text : T.textMute, padding: "6px 14px", borderRadius: 99, fontSize: 13, fontWeight: 600, cursor: "pointer" }}>{label}</button>;
                })}
              </div>
              {hint("Checked every 30 minutes while a campaign runs; each one goes out once per campaign. Merge fields: {first_name} {clinic} {booked} {goal} {leads}.")}
              {CSM_MILESTONES.map(([k, label, when]) => field(`csm_ms_${k}`, `${label} · ${when}`, 2))}
            </>
          )}
          {view === "onboarding" && (
            <>
              <div style={{ marginTop: 16 }}>
                <Toggle on={csmOn(values.csm_checkins_enabled)} onChange={() => flip("csm_checkins_enabled")} label={csmOn(values.csm_checkins_enabled) ? "Check-ins drafted" : "Check-ins off"} />
              </div>
              {hint("Drafted on day 1, 3 and 7 after a client is added, until launch. Each one waits for your approval in that client's Client Success Manager. Merge fields: {first_name} {clinic} {done} {total} {needs} {portal_link} {day}.")}
              {field("csm_checkin_subject", "Subject")}
              {field("csm_checkin_body", "Body", 12)}
            </>
          )}
          {view === "brief" && (
            <>
              {field("csm_ai_brief", "How Claude writes the report analysis", 10)}
              {hint("Applies to the headline, what's working, what we're fixing, next steps, how your team can help, questions for the client and the next-campaign plan. Numbers always come straight from the client's data, and Claude is told never to invent or round them.")}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Client Booking Alert editor ─────────────────────────────────────────────
// One SMS field, backed by GET/PUT /api/dialer/client-booking-template.
// Fires immediately, synchronously, the instant a new appointment is
// booked for one of a client's leads — see
// dashboard/backend/client_booking_notification.py.
const CLIENT_BOOKING_FIELD_KEYS = ["client_booking_notification_sms"];

function ClientBookingAlertEditor({ categories, onCategoryChange }) {
  const [values, setValues] = useState({});
  const [category, setCategory] = useState("General");
  const [customCatMode, setCustomCatMode] = useState(false);
  const [saved, setSaved] = useState({ category: "General" });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);

  useEffect(() => {
    (async () => {
      const r = await fetch("/api/dialer/client-booking-template");
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

  const dirty = CLIENT_BOOKING_FIELD_KEYS.some(k => (values[k] || "") !== (saved[k] || "")) || category !== saved.category;

  const save = async () => {
    setSaving(true);
    try {
      const r = await fetch("/api/dialer/client-booking-template", {
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
    border: `1px solid ${T.lineStrong}`, borderRadius: 8,
    padding: "10px 12px", lineHeight: 1.5, color: T.text,
    fontFamily: T.font, fontSize: 13,
    outline: "none", resize: "vertical", boxSizing: "border-box",
  };
  const labelStyle = {
    display: "block", marginBottom: 6,
    fontFamily: T.font, fontSize: 12.5, fontWeight: 600,
    color: T.textDim,
  };
  const hintStyle = {
    marginTop: 6, fontFamily: T.font,
    fontSize: 12, color: T.textMute, lineHeight: 1.5,
  };

  if (loading) {
    return (
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ fontSize: 13, color: T.textMute }}>Loading…</div>
      </div>
    );
  }

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div style={{
        padding: "12px 36px", borderBottom: "1px solid rgba(58,123,213,0.1)",
        display: "flex", alignItems: "center", gap: 12, flexShrink: 0,
      }}>
        <span style={{ flex: 1, fontFamily: T.font, fontSize: 13, color: T.textDim, lineHeight: 1.5 }}>
          Fires immediately, to the <strong style={{ color: "#8fb8ff" }}>client</strong>, the instant a new appointment is booked for one of their leads (CRM or their own portal). Editable per-client on/off toggle lives on the Clients tab.
        </span>
        <CategoryPicker
          categories={categories}
          category={category}
          setCategory={setCategory}
          customCatMode={customCatMode}
          setCustomCatMode={setCustomCatMode}
        />
        {savedFlash && (
          <span style={{ fontSize: 12.5, color: T.good, fontWeight: 600 }}>Saved ✓</span>
        )}
        <button
          onClick={save}
          disabled={saving || !dirty}
          style={{
            background: dirty ? "linear-gradient(90deg, #2857a0, #3a7bd5)" : "rgba(58,123,213,0.12)",
            border: dirty ? "none" : "1px solid rgba(58,123,213,0.25)",
            borderRadius: 6, color: dirty ? "#fff" : "#6ab0ff",
            fontFamily: T.font, fontWeight: 600,
            fontSize: 12, padding: "6px 16px", flexShrink: 0,
            cursor: saving || !dirty ? "not-allowed" : "pointer",
            opacity: saving ? 0.6 : 1,
          }}
        >{saving ? "Saving…" : dirty ? "Save changes" : "Save"}</button>
      </div>

      <div style={{ flex: 1, overflowY: "auto", padding: "24px 36px", display: "flex", flexDirection: "column", gap: 24 }}>
        <div>
          <label style={labelStyle}>Text message</label>
          <textarea
            value={values.client_booking_notification_sms || ""}
            onChange={e => setValues(v => ({ ...v, client_booking_notification_sms: e.target.value }))}
            rows={4}
            placeholder="Hey {client_first_name}, we just booked you an appointment with {lead_name} for {when}."
            style={fieldStyle}
          />
          <div style={hintStyle}>
            Use <code style={{ color: "#6ab0ff" }}>{"{client_first_name}"}</code> for the client's first name,{" "}
            <code style={{ color: "#6ab0ff" }}>{"{lead_name}"}</code> for the new lead's name, and{" "}
            <code style={{ color: "#6ab0ff" }}>{"{when}"}</code> for the formatted appointment time, e.g. "2:00 PM on Thursday, September 4th".
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Email Handoff editor ────────────────────────────────────────────────────
// 3-touch email sequence (24h / +48h / +4d, chained off real sends — same
// cadence as DM Follow-Up), backed by GET/PUT /api/dialer/email-handoff-template.
// Fires automatically when a contact's status is set to "email-handoff" —
// either manually (gatekeeper redirect) or automatically 3 days after their
// first cold SMS with zero reply (email_followup_trigger.py). Sends route
// through the provider-matched email identities (see the "View Warm-Up
// Status" button below) rather than a single shared mailbox.
const EMAIL_HANDOFF_FIELDS = [
  { heading: "Touch 1", hint: "24 hours after status is set to \"email-handoff\".", instance: "touch1" },
  { heading: "Touch 2", hint: "48 hours after Touch 1 sends.", instance: "touch2" },
  { heading: "Touch 3", hint: "4 days after Touch 2 sends.", instance: "touch3" },
];

function EmailHandoffEditor({ categories, onCategoryChange }) {
  const [values, setValues] = useState({ category: "General" });
  const [saved, setSaved] = useState({ category: "General" });
  const [customCatMode, setCustomCatMode] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);
  const [showWarmup, setShowWarmup] = useState(false);
  const [showQueue, setShowQueue] = useState(false);

  useEffect(() => {
    (async () => {
      const r = await fetch("/api/dialer/email-handoff-template");
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
    ...EMAIL_HANDOFF_FIELDS.flatMap(f => [`email_handoff_${f.instance}_subject`, `email_handoff_${f.instance}_body`]),
    "category",
  ];
  const dirty = allKeys.some(k => (values[k] || "") !== (saved[k] || ""));

  const save = async () => {
    setSaving(true);
    try {
      const r = await fetch("/api/dialer/email-handoff-template", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });
      if (r.ok) {
        setSaved(values);
        onCategoryChange?.(values.category || "General");
        setSavedFlash(true);
        setTimeout(() => setSavedFlash(false), 2500);
      } else {
        const d = await r.json().catch(() => ({}));
        window.alert(d.detail || "Save failed.");
      }
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ fontSize: 13, color: T.textMute }}>Loading…</div>
      </div>
    );
  }

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div style={{
        padding: "12px 36px", borderBottom: "1px solid rgba(58,123,213,0.1)",
        display: "flex", alignItems: "center", gap: 12, flexShrink: 0,
      }}>
        <span style={{ flex: 1, fontFamily: T.font, fontSize: 13, color: T.textDim, lineHeight: 1.5 }}>
          Fires when a contact's status is set to <code style={{ color: "#6ab0ff" }}>email-handoff</code> — 3 touches, stops permanently on reply. Sent from a Google or Microsoft identity matched to the recipient's own provider.
        </span>
        <CategoryPicker
          categories={categories}
          category={values.category || "General"}
          setCategory={c => setValues(v => ({ ...v, category: c }))}
          customCatMode={customCatMode}
          setCustomCatMode={setCustomCatMode}
        />
        {savedFlash && (
          <span style={{ fontSize: 12.5, color: T.good, fontWeight: 600 }}>Saved ✓</span>
        )}
        <button
          onClick={() => setShowWarmup(true)}
          className="btn btn-secondary"
          style={{ fontSize: 12, padding: "6px 14px", whiteSpace: "nowrap", flexShrink: 0 }}
        >View Warm-Up Status</button>
        <button
          onClick={() => setShowQueue(true)}
          className="btn btn-secondary"
          style={{ fontSize: 12, padding: "6px 14px", whiteSpace: "nowrap", flexShrink: 0 }}
        >View active prospects</button>
        <button
          onClick={save}
          disabled={saving || !dirty}
          style={{
            background: dirty ? "linear-gradient(90deg, #2857a0, #3a7bd5)" : "rgba(58,123,213,0.12)",
            border: dirty ? "none" : "1px solid rgba(58,123,213,0.25)",
            borderRadius: 6, color: dirty ? "#fff" : "#6ab0ff",
            fontFamily: T.font, fontWeight: 600,
            fontSize: 12, padding: "6px 16px", flexShrink: 0,
            cursor: saving || !dirty ? "not-allowed" : "pointer",
            opacity: saving ? 0.6 : 1,
          }}
        >{saving ? "Saving…" : dirty ? "Save changes" : "Save"}</button>
      </div>

      {showWarmup && <IdentityWarmupModal onClose={() => setShowWarmup(false)} />}
      {showQueue && <EmailHandoffQueueModal onClose={() => setShowQueue(false)} />}

      <div style={{ flex: 1, overflowY: "auto", padding: "24px 36px", display: "flex", flexDirection: "column", gap: 24 }}>
        {EMAIL_HANDOFF_FIELDS.map((f, i) => {
          const subjectKey = `email_handoff_${f.instance}_subject`;
          const bodyKey = `email_handoff_${f.instance}_body`;
          return (
          <div key={f.instance} style={i > 0 ? { borderTop: "1px solid rgba(58,123,213,0.1)", paddingTop: 20 } : undefined}>
            <label style={sequenceLabelStyle}>{f.heading}</label>
            {f.hint && <div style={{ ...sequenceHintStyle, marginTop: 0, marginBottom: 10 }}>{f.hint}</div>}

            <label style={{ ...sequenceLabelStyle, fontSize: 12.5, fontWeight: 600, color: T.textDim }}>Subject</label>
            <input
              value={values[subjectKey] || ""}
              onChange={e => setValues(v => ({ ...v, [subjectKey]: e.target.value }))}
              placeholder="Quick question, {business}"
              style={{ ...sequenceFieldStyle, marginBottom: 10 }}
            />

            <label style={{ ...sequenceLabelStyle, fontSize: 9 }}>BODY</label>
            <textarea
              value={values[bodyKey] || ""}
              onChange={e => setValues(v => ({ ...v, [bodyKey]: e.target.value }))}
              rows={4}
              placeholder="Hey {first_name}, ..."
              style={sequenceFieldStyle}
            />

            <div style={sequenceHintStyle}>
              Use <code style={{ color: "#6ab0ff" }}>{"{first_name}"}</code>, <code style={{ color: "#6ab0ff" }}>{"{full_name}"}</code>, <code style={{ color: "#6ab0ff" }}>{"{business}"}</code>, <code style={{ color: "#6ab0ff" }}>{"{opener}"}</code> (their custom opener), <code style={{ color: "#6ab0ff" }}>{"{link}"}</code> for the booking link, or <code style={{ color: "#6ab0ff" }}>{"{loom}"}</code> for the prospect's personalized video (made automatically on enrollment; a touch using it waits until the video is ready). Works in subjects too. Wrap words in <code style={{ color: "#6ab0ff" }}>{"**double asterisks**"}</code> to make them bold in the email.
            </div>
          </div>
          );
        })}
      </div>
    </div>
  );
}

// ── SMS Sequence editor ─────────────────────────────────────────────────────
// Fixed-step outreach script shown as the Inbox's "SEQUENCE" dropdown
// (InboxPanel.jsx). Step keys/labels/order must match routers/sms.py
// SEQUENCE_STEPS. Multiple named sequences can exist (GET /api/sms-sequences);
// exactly one is "active" (the Default) at a time — see the "Set as default"
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
  padding: "10px 12px", color: T.text,
  fontFamily: T.font, fontSize: 13,
  outline: "none", resize: "vertical", boxSizing: "border-box",
};
const sequenceLabelStyle = {
  display: "block", marginBottom: 8,
  fontFamily: T.font, fontSize: 16, fontWeight: 700,
  color: T.text, letterSpacing: "0.01em",
};
const sequenceHintStyle = {
  marginTop: 6, fontFamily: T.font,
  fontSize: 12, color: T.textMute, lineHeight: 1.5,
};
const sequenceNameInputStyle = {
  flex: 1, background: "rgba(255,255,255,0.04)",
  border: "1px solid rgba(58,123,213,0.2)", borderRadius: 6,
  padding: "6px 10px", color: T.text,
  fontFamily: T.font, fontSize: 13, fontWeight: 600,
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
        <div style={{ fontSize: 13, color: T.textMute }}>Loading…</div>
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
          <span style={{ fontSize: 12.5, color: T.good, fontWeight: 600 }}>Saved ✓</span>
        )}
        <button
          onClick={activate}
          disabled={sequence.is_active || activating}
          title={sequence.is_active ? "This is already the default sequence" : "Make this the sequence shown in the Inbox"}
          style={{
            background: sequence.is_active ? "rgba(52,211,153,0.12)" : "rgba(58,123,213,0.12)",
            border: sequence.is_active ? "1px solid rgba(52,211,153,0.35)" : "1px solid rgba(58,123,213,0.25)",
            borderRadius: 6, color: sequence.is_active ? "#34d399" : "#6ab0ff",
            fontFamily: T.font, fontWeight: 600,
            fontSize: 12, padding: "6px 14px", flexShrink: 0,
            cursor: sequence.is_active || activating ? "not-allowed" : "pointer",
            opacity: activating ? 0.6 : 1,
          }}
        >{sequence.is_active ? "Default ✓" : activating ? "Setting…" : "Set as default"}</button>
        <button
          onClick={deleteSequence}
          disabled={sequence.is_active}
          title={sequence.is_active ? "Set another sequence as default first" : "Delete this sequence"}
          style={{
            background: "rgba(220,60,60,0.1)",
            border: "1px solid rgba(220,60,60,0.3)",
            borderRadius: 6, color: "#dc3c3c",
            fontFamily: T.font, fontWeight: 600,
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
            fontFamily: T.font, fontWeight: 600,
            fontSize: 12, padding: "6px 16px", flexShrink: 0,
            cursor: saving || !dirty || !name.trim() ? "not-allowed" : "pointer",
            opacity: saving ? 0.6 : 1,
          }}
        >{saving ? "Saving…" : dirty ? "Save changes" : "Save"}</button>
      </div>

      {deleteError && (
        <div style={{
          padding: "8px 36px", background: "rgba(220,60,60,0.1)",
          borderBottom: "1px solid rgba(220,60,60,0.2)",
          fontFamily: T.font, fontSize: 12, color: "#dc3c3c",
        }}>{deleteError}</div>
      )}

      <div style={{ padding: "12px 36px 0", fontFamily: T.font, fontSize: 13, color: T.textDim, lineHeight: 1.5 }}>
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
            fontFamily: T.font, fontWeight: 600,
            fontSize: 12, padding: "6px 16px", flexShrink: 0,
            cursor: saving || !title.trim() ? "not-allowed" : "pointer",
            opacity: saving ? 0.6 : 1,
          }}
        >{saving ? "Creating…" : "Create sequence"}</button>
      </div>

      <div style={{ padding: "12px 36px 0", fontFamily: T.font, fontSize: 13, color: T.textDim, lineHeight: 1.5 }}>
        New text sequence. Fill in the steps you want and leave the rest blank to skip them. New sequences start off <em>not</em> the default — set it as default from its own editor once you're ready to switch to it.
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
        <div style={{ fontSize: 13, color: T.textMute }}>Loading…</div>
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
          <span style={{ fontSize: 12.5, color: T.good, fontWeight: 600 }}>Saved ✓</span>
        )}
        <button
          onClick={activate}
          disabled={script.is_active || activating}
          title={script.is_active ? "This is already the default script" : "Make this the script shown in the Dialer"}
          style={{
            background: script.is_active ? "rgba(52,211,153,0.12)" : "rgba(58,123,213,0.12)",
            border: script.is_active ? "1px solid rgba(52,211,153,0.35)" : "1px solid rgba(58,123,213,0.25)",
            borderRadius: 6, color: script.is_active ? "#34d399" : "#6ab0ff",
            fontFamily: T.font, fontWeight: 600,
            fontSize: 12, padding: "6px 14px", flexShrink: 0,
            cursor: script.is_active || activating ? "not-allowed" : "pointer",
            opacity: activating ? 0.6 : 1,
          }}
        >{script.is_active ? "Default ✓" : activating ? "Setting…" : "Set as default"}</button>
        <button
          onClick={deleteScript}
          disabled={script.is_active}
          title={script.is_active ? "Set another script as default first" : "Delete this script"}
          style={{
            background: "rgba(220,60,60,0.1)",
            border: "1px solid rgba(220,60,60,0.3)",
            borderRadius: 6, color: "#dc3c3c",
            fontFamily: T.font, fontWeight: 600,
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
            fontFamily: T.font, fontWeight: 600,
            fontSize: 12, padding: "6px 16px", flexShrink: 0,
            cursor: saving || !dirty || !name.trim() ? "not-allowed" : "pointer",
            opacity: saving ? 0.6 : 1,
          }}
        >{saving ? "Saving…" : dirty ? "Save changes" : "Save"}</button>
      </div>

      {deleteError && (
        <div style={{
          padding: "8px 36px", background: "rgba(220,60,60,0.1)",
          borderBottom: "1px solid rgba(220,60,60,0.2)",
          fontFamily: T.font, fontSize: 12, color: "#dc3c3c",
        }}>{deleteError}</div>
      )}

      <div style={{ padding: "12px 36px 0", fontFamily: T.font, fontSize: 13, color: T.textDim, lineHeight: 1.5 }}>
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
            fontFamily: T.font, fontWeight: 600,
            fontSize: 12, padding: "6px 16px", flexShrink: 0,
            cursor: saving || !title.trim() ? "not-allowed" : "pointer",
            opacity: saving ? 0.6 : 1,
          }}
        >{saving ? "Creating…" : "Create script"}</button>
      </div>

      <div style={{ padding: "12px 36px 0", fontFamily: T.font, fontSize: 13, color: T.textDim, lineHeight: 1.5 }}>
        New call script. Fill in the sections you want and leave the rest blank to skip them. New scripts start off <em>not</em> the default — set it as default from its own editor once you're ready to switch to it.
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
    heading: "Onboarding / Launch Call: 1-Hour Reminder",
    hint: "The only reminder onboarding and launch calls get. Include {Meeting_Link}.",
    instance: "client_1h",
  },
  {
    heading: "Reschedule Notice", hint: "Sent immediately when a rep reschedules a booked appointment.",
    instance: "reschedule",
  },
];

// Dylan's own Calendly connection — real bookings on his Calendly link then
// automatically create the appointment_reminders row that drives the
// 24h/6h/1h reminders below (reminder_engine.py), instead of him entering
// them manually. See routers/calendly_admin.py + routers/calendly_webhooks.py.
function DylanCalendlyConnect() {
  const [status, setStatus] = useState(null);
  const [token, setToken] = useState("");
  const [saving, setSaving] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");

  const load = async () => {
    const r = await fetch("/api/calendly/my-status");
    if (r.ok) setStatus(await r.json());
  };
  useEffect(() => { load(); }, []);

  const saveToken = async () => {
    if (!token.trim()) return;
    setSaving(true); setError(""); setMsg("");
    try {
      const r = await fetch("/api/calendly/my-token", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: token.trim() }),
      });
      if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(d.detail || "Failed to save token"); }
      setToken("");
      await load();
      setMsg("Token saved.");
    } catch (e) { setError(e.message); }
    setSaving(false);
  };

  const connect = async () => {
    setConnecting(true); setError(""); setMsg("");
    try {
      const r = await fetch("/api/calendly/connect", { method: "POST" });
      if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(d.detail || "Failed to connect"); }
      await load();
      setMsg("Connected — real bookings will now auto-create reminders.");
    } catch (e) { setError(e.message); }
    setConnecting(false);
  };

  if (!status) return null;

  return (
    <div className="glass-card-sm" style={{ padding: "16px 18px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
        <div>
          <div style={{ fontFamily: T.font, fontSize: 13, fontWeight: 700, color: T.text }}>
            Your Calendly Connection
          </div>
          <div style={{ fontSize: 11, color: "#5a7aa0", marginTop: 3, maxWidth: 520 }}>
            {status.webhook_connected
              ? "Connected — a real booking on your Calendly link now automatically creates these reminders, no manual entry needed."
              : "Not connected yet — bookings on your Calendly link still need to be entered manually to trigger these reminders."}
          </div>
        </div>
        <span className={`badge ${status.webhook_connected ? "badge-green" : "badge-gray"}`}>
          {status.webhook_connected ? "CONNECTED" : "NOT CONNECTED"}
        </span>
      </div>
      {!status.token_saved ? (
        <div style={{ marginTop: 12 }}>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <input className="dg-input" style={{ flex: 1, minWidth: 220, fontSize: 12 }}
              placeholder="Calendly Personal Access Token"
              value={token} onChange={e => setToken(e.target.value)} type="password" />
            <button className="btn btn-primary" style={{ fontSize: 11 }} onClick={saveToken} disabled={saving || !token.trim()}>
              {saving ? "Saving…" : "Save Token"}
            </button>
          </div>
          <div style={{ ...hintStyleShared, marginTop: 6 }}>
            From Calendly → Integrations & Apps → API & Webhooks → Generate New Token.
          </div>
        </div>
      ) : (
        <div style={{ marginTop: 12 }}>
          <button className="btn btn-secondary" style={{ fontSize: 11 }} onClick={connect} disabled={connecting}>
            {connecting ? "Connecting…" : status.webhook_connected ? "Reconnect" : "Connect Calendly"}
          </button>
        </div>
      )}
      {msg && <div style={{ marginTop: 8, fontSize: 11, color: "#4ade80" }}>{msg}</div>}
      {error && <div style={{ marginTop: 8, fontSize: 11, color: "#e05c5c" }}>{error}</div>}
    </div>
  );
}

const hintStyleShared = {
  fontFamily: T.font, fontSize: 12, color: T.textMute, lineHeight: 1.5,
};

// Dylan's own Facebook Page id — same idea as DylanCalendlyConnect above,
// for meta_lead_webhooks.py's Dylan's-own-pipeline branch. Inert until
// Meta App Review grants real leadgen permissions (see that module's
// docstring) — saving this now just means it's ready the moment that
// access lands, same reasoning as building the Calendly webhook ahead of
// time didn't require anything special either.
function DylanMetaPageId() {
  const [pageId, setPageId] = useState("");
  const [saved, setSaved] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetch("/api/dialer/dylan-meta-page-id").then(r => r.json()).then(d => {
      setPageId(d.page_id || "");
      setSaved(d.page_id || "");
    }).catch(() => {});
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      const r = await fetch("/api/dialer/dylan-meta-page-id", {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ page_id: pageId.trim() }),
      });
      if (r.ok) setSaved(pageId.trim());
    } finally {
      setSaving(false);
    }
  };

  if (saved === null) return null;

  return (
    <div className="glass-card-sm" style={{ padding: "16px 18px", marginTop: -8 }}>
      <div style={{ fontFamily: T.font, fontSize: 13, fontWeight: 700, color: T.text }}>
        Your Facebook Page (for Lead Ads)
      </div>
      <div style={{ fontSize: 11, color: "#5a7aa0", marginTop: 3, marginBottom: 10, maxWidth: 520 }}>
        Not active yet — requires Meta App Review to approve leadgen permissions. Saving this now just means a Lead Ads submission on your own page will create a CRM contact automatically the moment that access is granted, same as a client's already does.
      </div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <input className="dg-input" style={{ flex: 1, minWidth: 220, fontSize: 12 }}
          placeholder="Facebook Page ID" value={pageId} onChange={e => setPageId(e.target.value)} />
        <button className="btn btn-secondary" style={{ fontSize: 11 }} onClick={save} disabled={saving || pageId.trim() === saved}>
          {saving ? "Saving…" : pageId.trim() === saved ? "Saved" : "Save"}
        </button>
      </div>
    </div>
  );
}

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
    border: `1px solid ${T.lineStrong}`, borderRadius: 8,
    padding: "10px 12px", lineHeight: 1.5, color: T.text,
    fontFamily: T.font, fontSize: 13,
    outline: "none", resize: "vertical", boxSizing: "border-box",
  };
  const labelStyle = {
    display: "block", marginBottom: 6,
    fontFamily: T.font, fontSize: 12.5, fontWeight: 600,
    color: T.textDim,
  };
  const headingStyle = {
    display: "block", marginBottom: 8,
    fontFamily: T.font, fontSize: 16, fontWeight: 700,
    color: T.text, letterSpacing: "0.01em",
  };
  const hintStyle = {
    marginTop: 6, fontFamily: T.font,
    fontSize: 12, color: T.textMute, lineHeight: 1.5,
  };

  if (loading) {
    return (
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ fontSize: 13, color: T.textMute }}>Loading…</div>
      </div>
    );
  }

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div style={{
        padding: "12px 36px", borderBottom: "1px solid rgba(58,123,213,0.1)",
        display: "flex", alignItems: "center", gap: 12, flexShrink: 0,
      }}>
        <span style={{ flex: 1, fontFamily: T.font, fontSize: 13, color: T.textDim, lineHeight: 1.5 }}>
          Sent by the <strong style={{ color: "#8fb8ff" }}>appointment reminder</strong> pipeline (24h/6h/1h reminders, reschedule notice). Edits apply to the very next send.
        </span>
        <CategoryPicker
          categories={categories}
          category={values.category || "General"}
          setCategory={c => setValues(v => ({ ...v, category: c }))}
          customCatMode={customCatMode}
          setCustomCatMode={setCustomCatMode}
        />
        {savedFlash && (
          <span style={{ fontSize: 12.5, color: T.good, fontWeight: 600 }}>Saved ✓</span>
        )}
        <button
          onClick={() => setShowQueue(true)}
          className="btn btn-secondary"
          style={{ fontSize: 12, padding: "6px 14px", whiteSpace: "nowrap", flexShrink: 0 }}
        >View active prospects</button>
        <button
          onClick={save}
          disabled={saving || !dirty}
          style={{
            background: dirty ? "linear-gradient(90deg, #2857a0, #3a7bd5)" : "rgba(58,123,213,0.12)",
            border: dirty ? "none" : "1px solid rgba(58,123,213,0.25)",
            borderRadius: 6, color: dirty ? "#fff" : "#6ab0ff",
            fontFamily: T.font, fontWeight: 600,
            fontSize: 12, padding: "6px 16px", flexShrink: 0,
            cursor: saving || !dirty ? "not-allowed" : "pointer",
            opacity: saving ? 0.6 : 1,
          }}
        >{saving ? "Saving…" : dirty ? "Save changes" : "Save"}</button>
      </div>

      {showQueue && <SequenceQueueModal sequence="reminder" onClose={() => setShowQueue(false)} />}

      <div style={{ flex: 1, overflowY: "auto", padding: "24px 36px", display: "flex", flexDirection: "column", gap: 24 }}>
        <DylanCalendlyConnect />
        <DylanMetaPageId />
        {REMINDER_FIELDS.map((f, i) => {
          const smsKey = `reminder_${f.instance}_sms`;
          const subjectKey = `reminder_${f.instance}_email_subject`;
          const bodyKey = `reminder_${f.instance}_email_body`;
          return (
          <div key={f.instance} style={i > 0 ? { borderTop: "1px solid rgba(58,123,213,0.1)", paddingTop: 20 } : undefined}>
            <label style={headingStyle}>{f.heading}</label>
            {f.hint && <div style={{ ...hintStyle, marginTop: 0, marginBottom: 10 }}>{f.hint}</div>}

            <label style={labelStyle}>Text message</label>
            <textarea
              value={values[smsKey] || ""}
              onChange={e => setValues(v => ({ ...v, [smsKey]: e.target.value }))}
              rows={3}
              placeholder="Hey {first_name}, ..."
              style={fieldStyle}
            />

            <div style={{ marginTop: 14 }}>
              <label style={labelStyle}>Email subject</label>
              <input
                value={values[subjectKey] || ""}
                onChange={e => setValues(v => ({ ...v, [subjectKey]: e.target.value }))}
                style={fieldStyle}
              />
            </div>

            <div style={{ marginTop: 14 }}>
              <label style={labelStyle}>Email body</label>
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
// immediately, touch 3 the next day, touch 4 (the "breakup") on day 3.
// Backed by GET/PUT /api/dialer/no-show-template — no_show_sequence.py reads
// these same keys fresh from dialer_settings at send time. The sequence
// stops permanently the moment the prospect replies on either channel (see
// stop_sequence_for_reply() in no_show_sequence.py). The old Touch 2 (3h,
// SMS-only same-day follow-up) was removed by request; the numbering gap is
// intentional — see no_show_sequence.py's docstring.
const NO_SHOW_FIELDS = [
  { heading: "Touch 1 — Missed You", hint: "Sent immediately when marked No Show. SMS + email.", instance: "touch1" },
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
    border: `1px solid ${T.lineStrong}`, borderRadius: 8,
    padding: "10px 12px", lineHeight: 1.5, color: T.text,
    fontFamily: T.font, fontSize: 13,
    outline: "none", resize: "vertical", boxSizing: "border-box",
  };
  const labelStyle = {
    display: "block", marginBottom: 6,
    fontFamily: T.font, fontSize: 12.5, fontWeight: 600,
    color: T.textDim,
  };
  const headingStyle = {
    display: "block", marginBottom: 8,
    fontFamily: T.font, fontSize: 16, fontWeight: 700,
    color: T.text, letterSpacing: "0.01em",
  };
  const hintStyle = {
    marginTop: 6, fontFamily: T.font,
    fontSize: 12, color: T.textMute, lineHeight: 1.5,
  };

  if (loading) {
    return (
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ fontSize: 13, color: T.textMute }}>Loading…</div>
      </div>
    );
  }

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div style={{
        padding: "12px 36px", borderBottom: "1px solid rgba(58,123,213,0.1)",
        display: "flex", alignItems: "center", gap: 12, flexShrink: 0,
      }}>
        <span style={{ flex: 1, fontFamily: T.font, fontSize: 13, color: T.textDim, lineHeight: 1.5 }}>
          Fires automatically after an appointment is marked <strong style={{ color: "#8fb8ff" }}>No Show</strong> in the Appointments tab — 3 touches, stops the moment the prospect replies. Edits apply to the very next send.
        </span>
        <CategoryPicker
          categories={categories}
          category={values.category || "General"}
          setCategory={c => setValues(v => ({ ...v, category: c }))}
          customCatMode={customCatMode}
          setCustomCatMode={setCustomCatMode}
        />
        {savedFlash && (
          <span style={{ fontSize: 12.5, color: T.good, fontWeight: 600 }}>Saved ✓</span>
        )}
        <button
          onClick={() => setShowQueue(true)}
          className="btn btn-secondary"
          style={{ fontSize: 12, padding: "6px 14px", whiteSpace: "nowrap", flexShrink: 0 }}
        >View active prospects</button>
        <button
          onClick={save}
          disabled={saving || !dirty}
          style={{
            background: dirty ? "linear-gradient(90deg, #2857a0, #3a7bd5)" : "rgba(58,123,213,0.12)",
            border: dirty ? "none" : "1px solid rgba(58,123,213,0.25)",
            borderRadius: 6, color: dirty ? "#fff" : "#6ab0ff",
            fontFamily: T.font, fontWeight: 600,
            fontSize: 12, padding: "6px 16px", flexShrink: 0,
            cursor: saving || !dirty ? "not-allowed" : "pointer",
            opacity: saving ? 0.6 : 1,
          }}
        >{saving ? "Saving…" : dirty ? "Save changes" : "Save"}</button>
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

            <label style={labelStyle}>Text message</label>
            <textarea
              value={values[smsKey] || ""}
              onChange={e => setValues(v => ({ ...v, [smsKey]: e.target.value }))}
              rows={3}
              placeholder="Hey {first_name}, ..."
              style={fieldStyle}
            />

            <div style={{ marginTop: 14 }}>
              <label style={labelStyle}>Email subject</label>
              <input
                value={values[subjectKey] || ""}
                onChange={e => setValues(v => ({ ...v, [subjectKey]: e.target.value }))}
                style={fieldStyle}
              />
            </div>

            <div style={{ marginTop: 14 }}>
              <label style={labelStyle}>Email body</label>
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
// immediately, touch 3 the next day, touch 4 (the "breakup") on day 3.
// Backed by GET/PUT /api/dialer/cancel-template — cancel_sequence.py reads
// these same keys fresh from dialer_settings at send time. The sequence
// stops permanently the moment the prospect replies on either channel (see
// stop_sequence_for_reply() in cancel_sequence.py). The old Touch 2 (3h,
// SMS-only same-day follow-up) was removed by request; the numbering gap is
// intentional — see cancel_sequence.py's docstring.
const CANCEL_FIELDS = [
  { heading: "Touch 1 — No Worries", hint: "Sent immediately when canceled. SMS + email.", instance: "touch1" },
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
    border: `1px solid ${T.lineStrong}`, borderRadius: 8,
    padding: "10px 12px", lineHeight: 1.5, color: T.text,
    fontFamily: T.font, fontSize: 13,
    outline: "none", resize: "vertical", boxSizing: "border-box",
  };
  const labelStyle = {
    display: "block", marginBottom: 6,
    fontFamily: T.font, fontSize: 12.5, fontWeight: 600,
    color: T.textDim,
  };
  const headingStyle = {
    display: "block", marginBottom: 8,
    fontFamily: T.font, fontSize: 16, fontWeight: 700,
    color: T.text, letterSpacing: "0.01em",
  };
  const hintStyle = {
    marginTop: 6, fontFamily: T.font,
    fontSize: 12, color: T.textMute, lineHeight: 1.5,
  };

  if (loading) {
    return (
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ fontSize: 13, color: T.textMute }}>Loading…</div>
      </div>
    );
  }

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div style={{
        padding: "12px 36px", borderBottom: "1px solid rgba(58,123,213,0.1)",
        display: "flex", alignItems: "center", gap: 12, flexShrink: 0,
      }}>
        <span style={{ flex: 1, fontFamily: T.font, fontSize: 13, color: T.textDim, lineHeight: 1.5 }}>
          Fires automatically after an appointment is marked <strong style={{ color: "#8fb8ff" }}>Cancel</strong> in the Appointments tab — 3 touches, stops the moment the prospect replies. Edits apply to the very next send.
        </span>
        <CategoryPicker
          categories={categories}
          category={values.category || "General"}
          setCategory={c => setValues(v => ({ ...v, category: c }))}
          customCatMode={customCatMode}
          setCustomCatMode={setCustomCatMode}
        />
        {savedFlash && (
          <span style={{ fontSize: 12.5, color: T.good, fontWeight: 600 }}>Saved ✓</span>
        )}
        <button
          onClick={() => setShowQueue(true)}
          className="btn btn-secondary"
          style={{ fontSize: 12, padding: "6px 14px", whiteSpace: "nowrap", flexShrink: 0 }}
        >View active prospects</button>
        <button
          onClick={save}
          disabled={saving || !dirty}
          style={{
            background: dirty ? "linear-gradient(90deg, #2857a0, #3a7bd5)" : "rgba(58,123,213,0.12)",
            border: dirty ? "none" : "1px solid rgba(58,123,213,0.25)",
            borderRadius: 6, color: dirty ? "#fff" : "#6ab0ff",
            fontFamily: T.font, fontWeight: 600,
            fontSize: 12, padding: "6px 16px", flexShrink: 0,
            cursor: saving || !dirty ? "not-allowed" : "pointer",
            opacity: saving ? 0.6 : 1,
          }}
        >{saving ? "Saving…" : dirty ? "Save changes" : "Save"}</button>
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

            <label style={labelStyle}>Text message</label>
            <textarea
              value={values[smsKey] || ""}
              onChange={e => setValues(v => ({ ...v, [smsKey]: e.target.value }))}
              rows={3}
              placeholder="Hey {first_name}, ..."
              style={fieldStyle}
            />

            <div style={{ marginTop: 14 }}>
              <label style={labelStyle}>Email subject</label>
              <input
                value={values[subjectKey] || ""}
                onChange={e => setValues(v => ({ ...v, [subjectKey]: e.target.value }))}
                style={fieldStyle}
              />
            </div>

            <div style={{ marginTop: 14 }}>
              <label style={labelStyle}>Email body</label>
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
    border: `1px solid ${T.lineStrong}`, borderRadius: 8,
    padding: "10px 12px", lineHeight: 1.5, color: T.text,
    fontFamily: T.font, fontSize: 13,
    outline: "none", resize: "vertical", boxSizing: "border-box",
  };
  const labelStyle = {
    display: "block", marginBottom: 6,
    fontFamily: T.font, fontSize: 12.5, fontWeight: 600,
    color: T.textDim,
  };
  const headingStyle = {
    display: "block", marginBottom: 8,
    fontFamily: T.font, fontSize: 16, fontWeight: 700,
    color: T.text, letterSpacing: "0.01em",
  };
  const hintStyle = {
    marginTop: 6, fontFamily: T.font,
    fontSize: 12, color: T.textMute, lineHeight: 1.5,
  };

  if (loading) {
    return (
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ fontSize: 13, color: T.textMute }}>Loading…</div>
      </div>
    );
  }

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div style={{
        padding: "12px 36px", borderBottom: "1px solid rgba(58,123,213,0.1)",
        display: "flex", alignItems: "center", gap: 12, flexShrink: 0,
      }}>
        <span style={{ flex: 1, fontFamily: T.font, fontSize: 13, color: T.textDim, lineHeight: 1.5 }}>
          Fires automatically once a conversation marked <strong style={{ color: "#8fb8ff" }}>DM Reached</strong> in the Inbox goes 24h without a reply — 3 touches, stops on reply, restarts if quiet again. Edits apply to the very next send.
        </span>
        <CategoryPicker
          categories={categories}
          category={values.category || "General"}
          setCategory={c => setValues(v => ({ ...v, category: c }))}
          customCatMode={customCatMode}
          setCustomCatMode={setCustomCatMode}
        />
        {savedFlash && (
          <span style={{ fontSize: 12.5, color: T.good, fontWeight: 600 }}>Saved ✓</span>
        )}
        <button
          onClick={() => setShowQueue(true)}
          className="btn btn-secondary"
          style={{ fontSize: 12, padding: "6px 14px", whiteSpace: "nowrap", flexShrink: 0 }}
        >View active prospects</button>
        <button
          onClick={save}
          disabled={saving || !dirty}
          style={{
            background: dirty ? "linear-gradient(90deg, #2857a0, #3a7bd5)" : "rgba(58,123,213,0.12)",
            border: dirty ? "none" : "1px solid rgba(58,123,213,0.25)",
            borderRadius: 6, color: dirty ? "#fff" : "#6ab0ff",
            fontFamily: T.font, fontWeight: 600,
            fontSize: 12, padding: "6px 16px", flexShrink: 0,
            cursor: saving || !dirty ? "not-allowed" : "pointer",
            opacity: saving ? 0.6 : 1,
          }}
        >{saving ? "Saving…" : dirty ? "Save changes" : "Save"}</button>
      </div>

      {showQueue && <DmFollowUpQueueModal onClose={() => setShowQueue(false)} />}

      <div style={{ flex: 1, overflowY: "auto", padding: "24px 36px", display: "flex", flexDirection: "column", gap: 24 }}>
        {DM_FOLLOWUP_FIELDS.map((f, i) => {
          const smsKey = `dm_followup_${f.instance}_sms`;
          return (
          <div key={f.instance} style={i > 0 ? { borderTop: "1px solid rgba(58,123,213,0.1)", paddingTop: 20 } : undefined}>
            <label style={headingStyle}>{f.heading}</label>
            {f.hint && <div style={{ ...hintStyle, marginTop: 0, marginBottom: 10 }}>{f.hint}</div>}

            <label style={labelStyle}>Text message</label>
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
  const [activeSection, setActiveSectionRaw] = useState(() => {
    const v = readPref("dg.resources.section", "sop");
    return SUBSECTIONS.some(s => s.id === v) ? v : "sop";
  });
  const [sops, setSops] = useState([]);
  const [loadingList, setLoadingList] = useState(true);
  const [search, setSearch] = useState("");
  const [groupBy, setGroupByRaw] = useState(() => readPref("dg.resources.groupBy", "purpose"));
  const [newMenuOpen, setNewMenuOpen] = useState(false);
  const [newKind, setNewKind] = useState("doc");
  const [sendInfoCategory, setSendInfoCategory] = useState("General");
  const [noShowCategory, setNoShowCategory] = useState("General");
  const [cancelCategory, setCancelCategory] = useState("General");
  const [dmFollowupCategory, setDmFollowupCategory] = useState("General");
  const [onboardingCategory, setOnboardingCategory] = useState("General");
  const [clientBookingCategory, setClientBookingCategory] = useState("General");
  const [clientSuccessCategory, setClientSuccessCategory] = useState("Client Success");
  useEffect(() => {
    fetch("/api/client-success/settings").then(r => (r.ok ? r.json() : null)).then(d => { if (d?.category) setClientSuccessCategory(d.category); }).catch(() => {});
  }, []);
  const [emailHandoffCategory, setEmailHandoffCategory] = useState("General");
  const [gkDeferralCategory, setGkDeferralCategory] = useState("General");
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
  const isOutreach = activeSection === "outreach_templates";
  const setGroupBy = (v) => { setGroupByRaw(v); writePref("dg.resources.groupBy", v); };

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
    try {
      const r = await fetch(`/api/sops?doc_type=${activeSection}`);
      if (r.ok) setSops(await r.json());
    } finally {
      setLoadingList(false);
    }
  }, [activeSection]);

  useEffect(() => { setLoadingList(true); fetchSOPs(); }, [fetchSOPs]);

  const fetchSequences = useCallback(async () => {
    const r = await fetch("/api/sms-sequences");
    if (r.ok) setSequences(await r.json());
  }, []);

  const fetchCallScripts = useCallback(async () => {
    const r = await fetch("/api/cold-call-scripts");
    if (r.ok) setCallScripts(await r.json());
  }, []);

  // Each built-in template keeps its category in its own store, so fetch
  // them all up front: the "Category" grouping and every category picker
  // need them before any one of those editors is opened.
  useEffect(() => {
    if (activeSection !== "outreach_templates") return;
    fetchSequences();
    fetchCallScripts();
    (async () => {
      const [infoR, noShowR, cancelR, dmFollowupR, onboardingR, emailHandoffR, remR, gkR] = await Promise.all([
        fetch("/api/dialer/info-template"),
        fetch("/api/dialer/no-show-template"),
        fetch("/api/dialer/cancel-template"),
        fetch("/api/dialer/dm-followup-template"),
        fetch("/api/dialer/onboarding-template"),
        fetch("/api/dialer/email-handoff-template"),
        fetch("/api/dialer/reminder-template"),
        fetch("/api/dialer/gatekeeper-deferral-template"),
      ]);
      if (infoR.ok) setSendInfoCategory((await infoR.json()).category || "General");
      if (noShowR.ok) setNoShowCategory((await noShowR.json()).category || "General");
      if (cancelR.ok) setCancelCategory((await cancelR.json()).category || "General");
      if (dmFollowupR.ok) setDmFollowupCategory((await dmFollowupR.json()).category || "General");
      if (onboardingR.ok) setOnboardingCategory((await onboardingR.json()).category || "General");
      if (emailHandoffR.ok) setEmailHandoffCategory((await emailHandoffR.json()).category || "General");
      if (remR.ok) setRemCategory((await remR.json()).category || "General");
      if (gkR.ok) setGkDeferralCategory((await gkR.json()).category || "General");
    })();
  }, [activeSection, fetchSequences, fetchCallScripts]);

  const setContent = (html) => {
    suppressNextUpdate.current = true;
    editor?.commands.setContent(html, false);
  };

  const clearSelection = () => {
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
  };

  const setActiveSection = (id) => {
    if (id === activeSection) return;
    if (dirty && !window.confirm("Discard unsaved changes?")) return;
    writePref("dg.resources.section", id);
    setSearch("");
    setActiveSectionRaw(id);
  };

  useEffect(() => { clearSelection(); }, [activeSection]);

  // Built-in template categories live outside the `sops` table (dialer
  // settings, sms_sequences, cold_call_scripts); fold them in so a category
  // made on one of them shows up in every picker in this section.
  const categories = dedupeCategories([
    ...sops.map(s => s.category || "General"),
    ...(isOutreach
      ? [
          sendInfoCategory, noShowCategory, cancelCategory, dmFollowupCategory, onboardingCategory, clientBookingCategory, clientSuccessCategory, emailHandoffCategory, gkDeferralCategory, remCategory,
          ...sequences.map(s => s.category || "General"),
          ...callScripts.map(s => s.category || "General"),
        ]
      : []),
  ]);

  const isSequenceCategory = isOutreach && isNew && newKind === "sequence";
  const isScriptCategory = isOutreach && isNew && newKind === "script";

  const openSOP = (sop) => {
    if (sop.id === selectedId && !isNew) return;
    if (dirty && !window.confirm("Discard unsaved changes?")) return;
    setSelectedId(sop.id);
    setSelectedItem(sop);
    setIsNew(false);
    setDirty(false);
    setCustomCatMode(false);
    setSelectedSequenceId(sop.smsSequence ? sop.sequenceId : null);
    setSelectedScriptId(sop.callScript ? sop.scriptId : null);
    if (isSpecialItem(sop)) return;
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

  const startNew = (kind = "doc") => {
    setNewMenuOpen(false);
    if (dirty && !window.confirm("Discard unsaved changes?")) return;
    setSelectedId(null);
    setSelectedItem(null);
    setSelectedSequenceId(null);
    setNewSequenceSteps({});
    setSelectedScriptId(null);
    setNewScriptSections({});
    setNewKind(kind);
    setIsNew(true);
    setTitle("");
    const kindCats = kind === "sequence" ? sequences.map(s => s.category) : kind === "script" ? callScripts.map(s => s.category) : sops.map(s => s.category);
    setCategory(kindCats.find(Boolean) || categories[0] || "General");
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
          setSelectedItem(created);
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
    if (selectedId === sop.id) clearSelection();
    await fetchSOPs();
  };

  // Built-in templates become list items next to the saved docs, so they
  // group, search and open the same way.
  const pseudoItems = isOutreach ? [
    { ...SEND_INFO_ITEM,        category: sendInfoCategory },
    { ...NO_SHOW_ITEM,          category: noShowCategory },
    { ...CANCEL_ITEM,           category: cancelCategory },
    { ...DM_FOLLOWUP_ITEM,      category: dmFollowupCategory },
    { ...ONBOARDING_ITEM,       category: onboardingCategory },
    { ...CLIENT_BOOKING_ITEM,   category: clientBookingCategory },
    { ...CLIENT_SUCCESS_ITEM,   category: clientSuccessCategory },
    { ...EMAIL_HANDOFF_ITEM,    category: emailHandoffCategory },
    { ...GK_DEFERRAL_ITEM,      category: gkDeferralCategory },
    ...[...sequences].sort((x, y) => (y.is_active ? 1 : 0) - (x.is_active ? 1 : 0)).map(seq => ({
      id: `seq-${seq.id}`,
      title: seq.name,
      category: seq.category || "General",
      smsSequence: true,
      sequenceId: seq.id,
      isDefault: seq.is_active,
    })),
    ...[...callScripts].sort((x, y) => (y.is_active ? 1 : 0) - (x.is_active ? 1 : 0)).map(cs => ({
      id: `script-${cs.id}`,
      title: cs.name,
      category: cs.category || "General",
      callScript: true,
      scriptId: cs.id,
      isDefault: cs.is_active,
    })),
    { ...REMINDER_TEMPLATE_ITEM, category: remCategory },
  ] : [];

  const q = search.trim().toLowerCase();
  const matches = (item) => !q || `${cleanTitle(item.title)} ${metaFor(item)?.when || ""} ${item.category || ""}`.toLowerCase().includes(q);
  const allItems = [...pseudoItems, ...sops].filter(matches);
  const totalCount = pseudoItems.length + sops.length;
  const effectiveGroupBy = isOutreach ? groupBy : "category";

  let groups;
  if (effectiveGroupBy === "purpose") {
    groups = PURPOSES
      .map(p => ({ key: p.id, label: p.label, hint: p.hint, items: allItems.filter(i => (metaFor(i)?.purpose || "docs") === p.id) }))
      .filter(g => g.items.length);
  } else {
    // Case/whitespace-insensitive (catKey), so "SMS Outreach" and
    // "sms outreach" stay one group.
    const byCat = allItems.reduce((acc, item) => {
      const cat = item.category || "General";
      const key = catKey(cat);
      if (!acc[key]) acc[key] = { key, label: cat.trim(), items: [] };
      acc[key].items.push(item);
      return acc;
    }, {});
    groups = Object.values(byCat);
  }

  const showEditor = selectedId !== null || isNew;
  const detailOpen = !!selectedItem || showEditor;

  const itemIcon = (item) => metaFor(item)?.icon || docKind(item).icon;
  // Generic "when" lines (every sequence / script says the same thing) are
  // already the group's hint, so rows leave them out.
  const itemSub = (item) => {
    const meta = metaFor(item);
    if (meta) return meta.generic ? "" : meta.when;
    return [item.file_name ? docKind(item).label : "", fmtUpdated(item.updated_at), effectiveGroupBy === "purpose" ? item.category : ""].filter(Boolean).join(" · ");
  };

  const newOptions = [
    { kind: "doc",      label: "Saved template",  hint: "Free-form text you copy from" },
    { kind: "sequence", label: "Text sequence",   hint: "Step-by-step texts for the Inbox" },
    { kind: "script",   label: "Call script",     hint: "Opener, intro, body and close for the dialer" },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden", fontFamily: T.font }}>
      <style>{PROSE_CSS + `
        .res-row .res-del { opacity: 0; transition: opacity .15s; }
        .res-row:hover .res-del { opacity: 1; }
        .res-row { transition: background .12s; }
        .res-row:hover { background: rgba(77,142,240,0.06); }
        .res-list > .res-row + .res-row { border-top: 1px solid ${T.line}; }
        .res-list > .res-row:hover .res-chev { color: ${T.textDim}; transform: translateX(2px); }
        .res-chev { transition: transform .15s, color .15s; }
      `}</style>

      {/* Header */}
      <div style={{ padding: "20px 28px 0", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 14, flexWrap: "wrap" }}>
          <div style={{ minWidth: 0 }}>
            {detailOpen && (
              <button onClick={clearSelection} className="md:hidden" style={{ background: "none", border: "none", color: "#8fb8ff", cursor: "pointer", fontSize: 13, fontWeight: 600, padding: "0 0 6px" }}>
                ‹ Back to list
              </button>
            )}
            <h1 style={{ fontFamily: T.display, fontSize: 24, fontWeight: 700, color: T.text, letterSpacing: "-0.02em", margin: 0 }}>Resources</h1>
            <div style={{ fontSize: 13.5, color: T.textMute, marginTop: 4 }}>{section.description}</div>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center", position: "relative" }}>
            <input ref={uploadRef} type="file" style={{ display: "none" }} onChange={handleUpload} />
            <button onClick={() => uploadRef.current?.click()} disabled={uploading} style={{ ...btnGhost, opacity: uploading ? 0.6 : 1, cursor: uploading ? "not-allowed" : "pointer" }}>
              {uploading ? "Uploading…" : "Upload"}
            </button>
            {isOutreach ? (
              <>
                <button onClick={() => setNewMenuOpen(o => !o)} style={btnPrimary}>+ New ▾</button>
                {newMenuOpen && (
                  <>
                    <div onClick={() => setNewMenuOpen(false)} style={{ position: "fixed", inset: 0, zIndex: 40 }} />
                    <div style={{
                      position: "absolute", top: "calc(100% + 6px)", right: 0, zIndex: 41, width: 270,
                      background: "#0d1734", border: `1px solid ${T.lineStrong}`, borderRadius: 10, padding: 6,
                      boxShadow: "0 12px 32px rgba(0,0,0,0.45)",
                    }}>
                      {newOptions.map(o => (
                        <button key={o.kind} onClick={() => startNew(o.kind)} className="res-row" style={{ display: "block", width: "100%", textAlign: "left", background: "none", border: "none", borderRadius: 8, padding: "8px 10px", cursor: "pointer" }}>
                          <div style={{ fontSize: 13.5, fontWeight: 600, color: T.text }}>{o.label}</div>
                          <div style={{ fontSize: 12, color: T.textMute, marginTop: 1 }}>{o.hint}</div>
                        </button>
                      ))}
                    </div>
                  </>
                )}
              </>
            ) : (
              <button onClick={() => startNew("doc")} style={btnPrimary}>+ {section.newLabel}</button>
            )}
          </div>
        </div>
        <Tabs style={{ marginTop: 14 }} value={activeSection} onChange={setActiveSection}
          tabs={SUBSECTIONS.map(s => ({ id: s.id, label: s.label, count: s.id === activeSection && !loadingList ? totalCount : 0 }))} />
      </div>

      {/* Body */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>

        {/* Sidebar: only while something is open (desktop); otherwise the overview is the list */}
        {detailOpen && (
        <div className="hidden md:flex flex-col flex-shrink-0 md:w-[264px]" style={{ borderRight: `1px solid ${T.line}`, overflow: "hidden" }}>
          <div style={{ padding: "12px 12px 6px", flexShrink: 0 }}>
            <button onClick={() => { if (dirty && !window.confirm("Discard unsaved changes?")) return; clearSelection(); }}
              style={{ background: "none", border: "none", color: T.textMute, cursor: "pointer", fontSize: 12.5, fontWeight: 600, padding: "2px 4px 10px" }}>
              ‹ All {section.label.toLowerCase()}
            </button>
            <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search…"
              style={{ ...inputStyle, padding: "7px 11px", fontSize: 13 }} />
          </div>
          <div style={{ flex: 1, overflowY: "auto", padding: "0 0 16px" }}>
            {isNew && (
              <div style={{ margin: "6px 8px", padding: "7px 10px", borderRadius: 8, background: T.accentSoft, fontSize: 13, color: "#8fb8ff", fontWeight: 600 }}>
                {isOutreach ? newOptions.find(o => o.kind === newKind)?.label : section.newLabel} (not saved)
              </div>
            )}
            {groups.map(g => (
              <div key={g.key} style={{ marginTop: 10 }}>
                <div style={{ padding: "4px 18px", fontSize: 11.5, fontWeight: 600, color: T.textMute }}>{g.label}</div>
                {g.items.map(item => {
                  const isActive = selectedId === item.id;
                  return (
                    <div key={item.id} onClick={() => openSOP(item)} className="res-row" style={{
                      display: "flex", alignItems: "center", gap: 9, margin: "1px 8px", padding: "6px 10px", borderRadius: 7, cursor: "pointer",
                      background: isActive ? T.accentSoft : undefined,
                    }}>
                      <span style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: 13, fontWeight: isActive ? 600 : 500, color: isActive ? T.text : T.textDim }}>
                        {cleanTitle(item.title)}
                      </span>
                      {item.isDefault && <span title="Default" style={{ width: 6, height: 6, borderRadius: 99, background: T.good, flexShrink: 0 }} />}
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
        )}

        {/* Detail pane: hidden on mobile until something is open */}
        <div className="flex flex-col flex-1 min-w-0" style={{ overflow: "hidden" }}>
          {selectedItem && isSpecialItem(selectedItem) && (
            <div style={{ padding: "16px 36px 0", flexShrink: 0, display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <ResIcon name={itemIcon(selectedItem)} size={28} />
              <span style={{ fontFamily: T.display, fontSize: 18, fontWeight: 700, color: T.text }}>{cleanTitle(selectedItem.title)}</span>
              <ChannelChips channels={metaFor(selectedItem).channels} />
              <span style={{ fontSize: 12.5, color: T.textMute }}>{metaFor(selectedItem).when}</span>
            </div>
          )}
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
          ) : selectedItem?.clientBookingTemplate ? (
            <ClientBookingAlertEditor categories={categories} onCategoryChange={setClientBookingCategory} />
          ) : selectedItem?.clientSuccess ? (
            <ClientSuccessEditor categories={categories} onCategoryChange={setClientSuccessCategory} />
          ) : selectedItem?.emailHandoffTemplate ? (
            <EmailHandoffEditor categories={categories} onCategoryChange={setEmailHandoffCategory} />
          ) : selectedItem?.gkDeferralTemplate ? (
            <GatekeeperDeferralEditor categories={categories} onCategoryChange={setGkDeferralCategory} />
          ) : selectedItem?.smsSequence ? (
            <SmsSequenceEditor
              sequence={sequences.find(s => s.id === selectedSequenceId)}
              categories={categories}
              onSaved={fetchSequences}
              onDeleted={() => { clearSelection(); fetchSequences(); }}
            />
          ) : selectedItem?.callScript ? (
            <CallScriptEditor
              script={callScripts.find(s => s.id === selectedScriptId)}
              categories={categories}
              onSaved={fetchCallScripts}
              onDeleted={() => { clearSelection(); fetchCallScripts(); }}
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
                  smsSequence: true, sequenceId: created.id, isDefault: created.is_active,
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
                  callScript: true, scriptId: created.id, isDefault: created.is_active,
                });
                setSelectedScriptId(created.id);
                fetchCallScripts();
              }}
            />
          ) : !showEditor ? (
            /* ── Overview: one clean list, grouped ── */
            <div style={{ flex: 1, overflowY: "auto", padding: "20px 28px 48px" }}>
              <div style={{ maxWidth: 880 }}>
                <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap", marginBottom: 22 }}>
                  <input value={search} onChange={e => setSearch(e.target.value)} placeholder={`Search ${section.noun}s…`}
                    style={{ ...inputStyle, flex: 1, minWidth: 200, width: "auto", padding: "8px 12px", fontSize: 13.5 }} />
                  {isOutreach && (
                    <div style={{ display: "flex", padding: 3, borderRadius: 9, border: `1px solid ${T.line}`, background: "rgba(255,255,255,0.02)" }}>
                      {[["purpose", "By purpose"], ["category", "By category"]].map(([id, label]) => {
                        const on = groupBy === id;
                        return (
                          <button key={id} onClick={() => setGroupBy(id)} style={{
                            border: "none", background: on ? T.accentSoft : "transparent", color: on ? T.text : T.textMute,
                            padding: "5px 12px", borderRadius: 7, fontSize: 12.5, fontWeight: 600, cursor: "pointer",
                          }}>{label}</button>
                        );
                      })}
                    </div>
                  )}
                </div>
                {loadingList && groups.length === 0 && <Empty>Loading…</Empty>}
                {groups.length === 0 && !loadingList && (
                  <div style={{ textAlign: "center", padding: "48px 20px" }}>
                    <div style={{ display: "flex", justifyContent: "center", marginBottom: 12 }}><ResIcon name="doc" size={40} /></div>
                    <div style={{ fontFamily: T.display, fontSize: 16, fontWeight: 600, color: T.text }}>
                      {q ? "Nothing matches your search" : `No ${section.label.toLowerCase()} yet`}
                    </div>
                    <div style={{ fontSize: 13, color: T.textMute, margin: "6px 0 18px" }}>
                      {q ? "Try a different word, or clear the search." : "Write one here or upload a file you already have."}
                    </div>
                    {!q && (
                      <div style={{ display: "flex", gap: 8, justifyContent: "center" }}>
                        <button onClick={() => startNew("doc")} style={btnPrimary}>+ {isOutreach ? "Saved template" : section.newLabel}</button>
                        <button onClick={() => uploadRef.current?.click()} style={btnGhost}>Upload file</button>
                      </div>
                    )}
                  </div>
                )}
                {groups.map(g => (
                  <section key={g.key} style={{ marginBottom: 26 }}>
                    <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 8, padding: "0 2px" }}>
                      <span style={{ fontFamily: T.display, fontSize: 14.5, fontWeight: 600, color: T.text }}>{g.label}</span>
                      <span style={{ fontSize: 12.5, color: T.textMute }}>{g.items.length}</span>
                      {g.hint && <span className="hidden md:inline" style={{ fontSize: 12.5, color: T.textMute, marginLeft: "auto", textAlign: "right" }}>{g.hint}</span>}
                    </div>
                    <div className="res-list" style={{ border: `1px solid ${T.line}`, borderRadius: 12, background: "rgba(13,22,52,0.45)", overflow: "hidden" }}>
                      {g.items.map(item => {
                        const meta = metaFor(item);
                        const sub = itemSub(item);
                        return (
                          <div key={item.id} onClick={() => openSOP(item)} className="res-row"
                            style={{ display: "flex", alignItems: "center", gap: 12, padding: "11px 14px", cursor: "pointer" }}>
                            <ResIcon name={itemIcon(item)} />
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                                <span style={{ fontSize: 14, fontWeight: 600, color: T.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{cleanTitle(item.title)}</span>
                                {item.isDefault && <Pill tone="good" style={{ fontSize: 10.5, padding: "1px 7px" }}>Default</Pill>}
                                {!meta && item.visibility === "public" && <Pill tone="good" style={{ fontSize: 10.5, padding: "1px 7px" }}>Public</Pill>}
                              </div>
                              {sub && <div style={{ fontSize: 12.5, color: T.textMute, marginTop: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{sub}</div>}
                            </div>
                            {meta && <span className="hidden sm:inline"><ChannelChips channels={meta.channels} /></span>}
                            {!meta && (
                              <button className="res-del" onClick={e => deleteSOP(item, e)} title="Delete"
                                style={{ background: "none", border: "none", cursor: "pointer", color: T.bad, fontSize: 16, lineHeight: 1, padding: "0 2px", flexShrink: 0 }}>×</button>
                            )}
                            <span className="res-chev" style={{ color: T.textMute, fontSize: 16, flexShrink: 0 }}>›</span>
                          </div>
                        );
                      })}
                    </div>
                  </section>
                ))}
              </div>
            </div>
          ) : selectedItem?.file_name ? (
            /* ── File viewer ── */
            <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
              <div style={{ padding: "14px 36px", borderBottom: `1px solid ${T.line}`, display: "flex", alignItems: "center", gap: 12, flexShrink: 0, flexWrap: "wrap" }}>
                <span style={{ fontFamily: T.display, fontWeight: 700, fontSize: 17, color: T.text, flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {selectedItem.title}
                </span>
                <span style={{ fontSize: 12.5, color: T.textMute, flexShrink: 0 }}>
                  {docKind(selectedItem).label}{selectedItem.file_size ? ` · ${(selectedItem.file_size / 1024 / 1024).toFixed(1)} MB` : ""}{selectedItem.updated_at ? ` · ${fmtUpdated(selectedItem.updated_at)}` : ""}
                </span>
                <a href={`/api/sops/${selectedItem.id}/file`} download={selectedItem.file_name} style={{ ...btnGhost, textDecoration: "none" }}>↓ Download</a>
                <button onClick={() => deleteSOP(selectedItem)} style={btnDanger}>Delete</button>
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
                    <div style={{ fontSize: 48, marginBottom: 12 }}>📎</div>
                    <div style={{ color: T.textDim, marginBottom: 6 }}>{selectedItem.file_name}</div>
                    <div style={{ fontSize: 12.5, color: T.textMute, marginBottom: 18 }}>This file type can't be previewed here.</div>
                    <a href={`/api/sops/${selectedItem.id}/file`} download={selectedItem.file_name} style={{ ...btnPrimary, textDecoration: "none", padding: "9px 22px" }}>↓ Download file</a>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <>
              {/* ── Document editor ── */}
              <div style={{ padding: "12px 36px", borderBottom: `1px solid ${T.line}`, display: "flex", alignItems: "center", gap: 10, flexShrink: 0, flexWrap: "wrap" }}>
                <input
                  value={title}
                  onChange={e => { setTitle(e.target.value); setDirty(true); }}
                  placeholder={section.placeholder}
                  autoFocus={isNew}
                  style={{ ...inputStyle, flex: 1, minWidth: 220, width: "auto", fontFamily: T.display, fontWeight: 700, fontSize: 16, padding: "7px 12px" }}
                />
                <CategoryPicker
                  categories={categories}
                  category={category}
                  setCategory={(c) => { setCategory(c); setDirty(true); }}
                  customCatMode={customCatMode}
                  setCustomCatMode={setCustomCatMode}
                  onCommit={() => setDirty(true)}
                />
                <div title="Private: only you see it. Public: can be shared outside the OS." style={{ display: "flex", borderRadius: 8, overflow: "hidden", border: `1px solid ${T.lineStrong}`, flexShrink: 0 }}>
                  {["private", "public"].map(v => (
                    <button key={v} onClick={() => { setVisibility(v); setDirty(true); }} style={{
                      padding: "6px 11px", border: "none", cursor: "pointer",
                      background: visibility === v ? (v === "public" ? "rgba(47,208,143,0.2)" : T.accentSoft) : "transparent",
                      color: visibility === v ? (v === "public" ? T.good : "#8fb8ff") : T.textMute,
                      fontSize: 12.5, fontWeight: 600, textTransform: "capitalize",
                    }}>{v}</button>
                  ))}
                </div>
                {savedFlash && <span style={{ fontSize: 12.5, color: T.good, fontWeight: 600 }}>Saved ✓</span>}
                {selectedId !== null && !isNew && <button onClick={() => deleteSOP(selectedItem)} style={btnDanger}>Delete</button>}
                <button onClick={save} disabled={saving || !title.trim()} style={{
                  ...(dirty && title.trim() ? btnPrimary : btnGhost),
                  cursor: saving || !title.trim() ? "not-allowed" : "pointer", opacity: saving ? 0.6 : 1,
                }}>{saving ? "Saving…" : isNew ? "Create" : dirty ? "Save changes" : "Save"}</button>
              </div>

              <FormatBar editor={editor} />

              <div style={{ flex: 1, overflowY: "auto", padding: "24px 36px" }}>
                <div style={{ maxWidth: 820 }}>
                  <EditorContent editor={editor} />
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
