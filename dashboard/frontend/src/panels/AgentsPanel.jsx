import React, { useState, useEffect, useRef, useCallback } from "react";
import { marked } from "marked";

const API = (p) => `/api${p}`;

// ── Helpers ───────────────────────────────────────────────────────────────────

function timeAgo(ts) {
  if (!ts) return "";
  const d = new Date(ts), now = new Date(), diff = now - d;
  if (diff < 60000) return "just now";
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function fmtMsgTime(ts) {
  if (!ts) return "";
  const d = new Date(ts), diff = Date.now() - d;
  if (diff < 86400000) return d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" }) + ", " +
         d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
}

// ── Thinking block (collapsible) ─────────────────────────────────────────────

function ThinkingBlock({ text, streaming }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div style={{
      fontFamily: "'Share Tech Mono', monospace", fontSize: 11,
      background: "rgba(30,10,50,0.7)", border: "1px solid rgba(140,80,220,0.2)",
      borderRadius: 8, padding: "6px 10px", marginBottom: 4,
      maxWidth: "85%",
    }}>
      <div
        onClick={() => !streaming && setExpanded(e => !e)}
        style={{
          cursor: streaming ? "default" : "pointer",
          display: "flex", alignItems: "center", gap: 6, color: streaming ? "#c080f0" : "#9060c8",
        }}
      >
        <span style={{ display: "inline-block", animation: streaming ? "spin 1s linear infinite" : "none", fontSize: 13 }}>
          {streaming ? "↻" : "◈"}
        </span>
        <span>{streaming ? "Thinking…" : "Thought process"}</span>
        {!streaming && (
          <span style={{ color: "#4a2a6a", marginLeft: "auto" }}>{expanded ? "▲" : "▼"}</span>
        )}
      </div>
      {expanded && text && (
        <div style={{
          marginTop: 6, color: "#7a5a9a", maxHeight: 300, overflowY: "auto",
          whiteSpace: "pre-wrap", wordBreak: "break-word", fontSize: 10, lineHeight: 1.6,
          borderTop: "1px solid rgba(140,80,220,0.1)", paddingTop: 6,
        }}>
          {text}
        </div>
      )}
    </div>
  );
}

// ── Tool block (collapsible) ──────────────────────────────────────────────────

function ToolBlock({ block }) {
  const [expanded, setExpanded] = useState(false);
  const running = block.status === "running";
  return (
    <div style={{
      fontFamily: "'Share Tech Mono', monospace", fontSize: 11,
      background: "rgba(7,12,30,0.8)", border: "1px solid rgba(58,123,213,0.15)",
      borderRadius: 8, padding: "6px 10px", marginBottom: 4,
      maxWidth: "85%",
    }}>
      <div
        onClick={() => !running && block.result && setExpanded(e => !e)}
        style={{
          cursor: running || !block.result ? "default" : "pointer",
          display: "flex", alignItems: "center", gap: 6, color: running ? "#f0a028" : "#3a7bd5",
        }}
      >
        <span style={{ display: "inline-block", animation: running ? "spin 1s linear infinite" : "none" }}>
          {running ? "↻" : "✓"}
        </span>
        <span>{block.name}</span>
        {!running && block.result && (
          <span style={{ color: "#2a4a7a", marginLeft: "auto" }}>{expanded ? "▲" : "▼"}</span>
        )}
      </div>
      {expanded && block.result && (
        <div style={{
          marginTop: 6, color: "#4a6a8a", maxHeight: 220, overflowY: "auto",
          whiteSpace: "pre-wrap", wordBreak: "break-all", fontSize: 10,
          borderTop: "1px solid rgba(58,123,213,0.1)", paddingTop: 6,
        }}>
          {block.result}
        </div>
      )}
    </div>
  );
}

// ── Styles ───────────────────────────────────────────────────────────────────

const CHAT_STYLES = `
.md-content { color: #8aaad0; font-size: 13px; line-height: 1.6; }
.md-content h1 { color: #c8dcff; font-size: 15px; font-weight: 600; margin: 12px 0 5px; font-family: 'Space Grotesk', sans-serif; }
.md-content h2 { color: #a8c4f0; font-size: 13px; font-weight: 600; margin: 10px 0 4px; font-family: 'Space Grotesk', sans-serif; text-transform: uppercase; letter-spacing: 0.04em; }
.md-content h3 { color: #8aaad0; font-size: 13px; font-weight: 600; margin: 8px 0 3px; }
.md-content p { margin: 3px 0 7px; }
.md-content ul, .md-content ol { padding-left: 18px; margin: 3px 0 7px; }
.md-content li { margin-bottom: 3px; }
.md-content hr { border: none; border-top: 1px solid rgba(58,123,213,0.15); margin: 8px 0; }
.md-content strong { color: #c8dcff; font-weight: 600; }
.md-content em { color: #7090b8; font-style: italic; }
.md-content code { background: rgba(58,123,213,0.12); border-radius: 3px; padding: 1px 5px; font-family: 'Share Tech Mono', monospace; font-size: 12px; }
.md-content a { color: #3a7bd5; text-decoration: none; }

.brief-body { padding: 0; }
.brief-body h1 { display: none; }
.brief-body h2 {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 10px; font-weight: 700;
  color: #3a7bd5; letter-spacing: 0.12em; text-transform: uppercase;
  margin: 0; padding: 8px 16px 7px;
  background: rgba(58,123,213,0.07);
  border-top: 1px solid rgba(58,123,213,0.15);
  border-bottom: 1px solid rgba(58,123,213,0.1);
}
.brief-body h3 { font-size: 12px; font-weight: 600; color: #8aaad0; margin: 8px 0 3px; padding: 0 16px; }
.brief-body p { font-size: 13px; color: #7a9ac0; line-height: 1.6; margin: 0; padding: 5px 16px 3px; }
.brief-body ul { list-style: none; padding: 6px 16px 6px 16px; margin: 0; }
.brief-body ol { padding: 6px 16px 6px 32px; margin: 0; }
.brief-body li { font-size: 13px; color: #7a9ac0; line-height: 1.55; margin-bottom: 4px; padding-left: 14px; position: relative; }
.brief-body li::before { content: "›"; position: absolute; left: 0; color: #3a7bd5; font-weight: 700; }
.brief-body ol li::before { display: none; }
.brief-body hr { border: none; border-top: 1px solid rgba(58,123,213,0.08); margin: 0; }
.brief-body strong { color: #c8dcff; font-weight: 600; }
.brief-body em { color: #5a7a9a; font-style: italic; }
.brief-body code { background: rgba(58,123,213,0.12); border-radius: 3px; padding: 1px 5px; font-family: 'Share Tech Mono', monospace; font-size: 12px; }
`;

// ── Briefing card ─────────────────────────────────────────────────────────────

function BriefingCard({ text, streaming }) {
  const dateMatch = text.match(/^# Morning Briefing\s*[—\-–]\s*(.+)/m);
  const dateLabel = dateMatch ? dateMatch[1].trim() : "";

  if (streaming) {
    return (
      <div style={{
        width: "100%", borderRadius: 10, overflow: "hidden",
        border: "1px solid rgba(58,123,213,0.25)",
        background: "linear-gradient(160deg, rgba(12,22,58,0.98) 0%, rgba(7,12,35,0.96) 100%)",
      }}>
        <div style={{
          background: "rgba(58,123,213,0.1)", borderBottom: "1px solid rgba(58,123,213,0.2)",
          padding: "10px 16px", display: "flex", alignItems: "center", gap: 8,
        }}>
          <span style={{ color: "#3a7bd5", fontSize: 14, lineHeight: 1 }}>◈</span>
          <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, fontWeight: 700, color: "#c8dcff", letterSpacing: "0.06em", textTransform: "uppercase" }}>
            Morning Briefing
          </span>
          {dateLabel && (
            <span style={{ marginLeft: "auto", fontFamily: "'Share Tech Mono', monospace", fontSize: 11, color: "#4a6a9a" }}>
              {dateLabel}
            </span>
          )}
        </div>
        <div style={{ padding: "12px 16px", fontSize: 13, color: "#8aaad0", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
          {text}
          <span style={{ display: "inline-block", animation: "blink 0.9s step-end infinite", marginLeft: 1, color: "#3a7bd5" }}>▋</span>
        </div>
      </div>
    );
  }

  const html = marked.parse(text);

  return (
    <div style={{
      width: "100%", borderRadius: 10, overflow: "hidden",
      border: "1px solid rgba(58,123,213,0.25)",
      background: "linear-gradient(160deg, rgba(12,22,58,0.98) 0%, rgba(7,12,35,0.96) 100%)",
      boxShadow: "0 4px 32px rgba(0,0,0,0.35)",
    }}>
      <div style={{
        background: "rgba(58,123,213,0.1)", borderBottom: "1px solid rgba(58,123,213,0.2)",
        padding: "11px 16px", display: "flex", alignItems: "center", gap: 8,
      }}>
        <span style={{ color: "#3a7bd5", fontSize: 14, lineHeight: 1 }}>◈</span>
        <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, fontWeight: 700, color: "#c8dcff", letterSpacing: "0.06em", textTransform: "uppercase" }}>
          Morning Briefing
        </span>
        {dateLabel && (
          <span style={{ marginLeft: "auto", fontFamily: "'Share Tech Mono', monospace", fontSize: 11, color: "#4a6a9a" }}>
            {dateLabel}
          </span>
        )}
      </div>
      <div className="brief-body" dangerouslySetInnerHTML={{ __html: html }} />
    </div>
  );
}

// ── Inline PDF embed ──────────────────────────────────────────────────────────

const PDF_SLUG_ENDPOINTS = {
  newsletter: "/agents/apptset-agent/newsletter-pdf",
};

function InlinePdfCard({ slug }) {
  const endpoint = PDF_SLUG_ENDPOINTS[slug];
  if (!endpoint) return null;
  return (
    <div style={{
      width: "100%", borderRadius: 10, overflow: "hidden", marginTop: 8,
      border: "1px solid rgba(58,123,213,0.25)",
      background: "linear-gradient(160deg, rgba(12,22,58,0.98) 0%, rgba(7,12,35,0.96) 100%)",
      boxShadow: "0 4px 32px rgba(0,0,0,0.35)",
    }}>
      <div style={{
        background: "rgba(58,123,213,0.1)", borderBottom: "1px solid rgba(58,123,213,0.2)",
        padding: "11px 16px", display: "flex", alignItems: "center", gap: 8,
      }}>
        <span style={{ color: "#3a7bd5", fontSize: 14, lineHeight: 1 }}>◈</span>
        <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, fontWeight: 700, color: "#c8dcff", letterSpacing: "0.06em", textTransform: "uppercase" }}>
          PDF Preview
        </span>
      </div>
      <embed
        src={API(endpoint)}
        type="application/pdf"
        style={{ width: "100%", height: 560, display: "block", border: "none" }}
      />
    </div>
  );
}

// ── Message bubble ────────────────────────────────────────────────────────────

const PDF_MARKER_RE = /\[\[PDF:([\w-]+)\]\]/;

function MessageBubble({ msg }) {
  const isUser = msg.role === "user";

  // Skip pure tool_result user turns (internal API turns, not human messages)
  if (isUser && msg.content?.every(b => b.type === "tool_result")) return null;

  const rawText = (msg.content || [])
    .filter(b => b.type === "text")
    .map(b => b.text)
    .join("");

  const pdfMatch = rawText.match(PDF_MARKER_RE);
  const pdfSlug = pdfMatch ? pdfMatch[1] : null;
  const text = pdfSlug ? rawText.replace(PDF_MARKER_RE, "").trimEnd() : rawText;

  if (isUser) {
    return (
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 10 }}>
        <div style={{
          maxWidth: "70%", padding: "9px 13px",
          borderRadius: "8px 8px 2px 8px",
          background: "#1f3d70", border: "0.5px solid #2857a0",
        }}>
          <div style={{ fontSize: 13, color: "#c8dcff", lineHeight: 1.55, whiteSpace: "pre-wrap" }}>
            {text}
          </div>
          {msg.created_at && (
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#4a6a9a", marginTop: 4, textAlign: "right" }}>
              {fmtMsgTime(msg.created_at)}
            </div>
          )}
        </div>
      </div>
    );
  }

  const isBriefing = text.trimStart().startsWith("# Morning Briefing");

  return (
    <div style={{ marginBottom: 10 }}>
      <style>{CHAT_STYLES}</style>
      {msg.thinking !== undefined && (
        <ThinkingBlock text={msg.thinking} streaming={msg._thinkingStreaming} />
      )}
      {(msg.toolBlocks || []).map(tb => <ToolBlock key={tb.id} block={tb} />)}
      {(text || msg._streaming || msg._error) && (
        isBriefing ? (
          <BriefingCard text={text} streaming={msg._streaming} />
        ) : (
          <div style={{
            maxWidth: "85%", padding: "10px 14px",
            borderRadius: "8px 8px 8px 2px",
            background: "linear-gradient(127deg, rgba(10,18,48,0.88) 0%, rgba(8,14,38,0.6) 100%)",
            border: "1px solid rgba(58,123,213,0.07)",
            marginTop: (msg.toolBlocks?.length > 0) ? 6 : 0,
          }}>
            {msg._streaming ? (
              <div style={{ fontSize: 13, color: "#8aaad0", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
                {text}
                <span style={{ display: "inline-block", animation: "blink 0.9s step-end infinite", marginLeft: 1, color: "#3a7bd5" }}>▋</span>
              </div>
            ) : (
              <div className="md-content" dangerouslySetInnerHTML={{ __html: marked.parse(text || "") }} />
            )}
            {msg._error && (
              <div style={{ fontSize: 11, color: "#dc3c3c", marginTop: text ? 4 : 0 }}>Error: {msg._error}</div>
            )}
            {msg.created_at && !msg._streaming && (
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80", marginTop: 6 }}>
                {fmtMsgTime(msg.created_at)}
              </div>
            )}
          </div>
        )
      )}
      {pdfSlug && !msg._streaming && <InlinePdfCard slug={pdfSlug} />}
    </div>
  );
}

// ── File tree ─────────────────────────────────────────────────────────────────

function FileNode({ node, onSelect, depth = 0 }) {
  const [open, setOpen] = useState(depth === 0);
  const indent = 12 + depth * 14;

  if (node.type === "dir") {
    return (
      <div>
        <div
          onClick={() => setOpen(o => !o)}
          style={{
            padding: `3px 12px 3px ${indent}px`, cursor: "pointer",
            fontSize: 11, color: "#3a5a80", display: "flex", alignItems: "center", gap: 5,
            fontFamily: "'Share Tech Mono', monospace",
          }}
          onMouseEnter={e => e.currentTarget.style.color = "#6080a8"}
          onMouseLeave={e => e.currentTarget.style.color = "#3a5a80"}
        >
          <span style={{ fontSize: 9 }}>{open ? "▾" : "▸"}</span>
          <span>{node.name}/</span>
        </div>
        {open && (node.children || []).map(child => (
          <FileNode key={child.path} node={child} onSelect={onSelect} depth={depth + 1} />
        ))}
      </div>
    );
  }

  return (
    <button
      onClick={() => onSelect(node.path)}
      style={{
        width: "100%", textAlign: "left", background: "none", border: "none",
        padding: `3px 12px 3px ${indent + 14}px`,
        fontSize: 11, color: "#4a6a8a", cursor: "pointer",
        fontFamily: "'Share Tech Mono', monospace", display: "block",
      }}
      onMouseEnter={e => e.currentTarget.style.color = "#8aaad0"}
      onMouseLeave={e => e.currentTarget.style.color = "#4a6a8a"}
    >
      {node.name}
      {node.size != null && (
        <span style={{ color: "#1e3050", marginLeft: 6, fontSize: 9 }}>
          {node.size > 1024 ? `${(node.size / 1024).toFixed(1)}k` : `${node.size}b`}
        </span>
      )}
    </button>
  );
}

function FilePanel({ agentId, onInsertPath, onClose }) {
  const [tree, setTree] = useState([]);
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setTree([]); setPreview(null);
    fetch(API(`/agents/${agentId}/files`))
      .then(r => r.json())
      .then(d => setTree(d.files || []));
  }, [agentId]);

  const openFile = async (path) => {
    setLoading(true);
    const r = await fetch(API(`/agents/${agentId}/files/${path}`));
    if (r.ok) setPreview(await r.json());
    setLoading(false);
  };

  return (
    <div style={{
      width: 280, flexShrink: 0,
      borderLeft: "0.5px solid #1a2540",
      display: "flex", flexDirection: "column",
      background: "rgba(8,14,38,0.6)",
    }}>
      <div style={{
        padding: "10px 14px", borderBottom: "0.5px solid #1a2540",
        display: "flex", justifyContent: "space-between", alignItems: "center",
        flexShrink: 0,
      }}>
        <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a7bd5", letterSpacing: "0.15em" }}>
          FILES
        </span>
        <button onClick={onClose} style={{
          background: "none", border: "none", color: "#3a5a80", cursor: "pointer", fontSize: 14, lineHeight: 1,
        }}>✕</button>
      </div>

      {!preview ? (
        <div style={{ flex: 1, overflowY: "auto", paddingTop: 6 }}>
          {tree.map(node => (
            <FileNode key={node.path} node={node} onSelect={openFile} depth={0} />
          ))}
        </div>
      ) : (
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <div style={{
            padding: "6px 10px", borderBottom: "0.5px solid #1a2540",
            display: "flex", gap: 6, alignItems: "center", flexShrink: 0,
          }}>
            <button
              onClick={() => setPreview(null)}
              style={{ background: "none", border: "none", color: "#3a7bd5", cursor: "pointer", fontSize: 10,
                       fontFamily: "'Share Tech Mono', monospace", letterSpacing: "0.1em" }}
            >
              ← BACK
            </button>
            <span style={{
              fontSize: 10, color: "#3a7bd5",
              fontFamily: "'Share Tech Mono', monospace",
              overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
            }}>
              {preview.path}
            </span>
          </div>
          <div style={{ flex: 1, overflowY: "auto", padding: 10 }}>
            <pre style={{
              fontSize: 10, color: "#4a6a8a",
              fontFamily: "'Share Tech Mono', monospace",
              whiteSpace: "pre-wrap", wordBreak: "break-all", margin: 0, lineHeight: 1.55,
            }}>
              {preview.content}
            </pre>
          </div>
          <div style={{ padding: "8px 10px", borderTop: "0.5px solid #1a2540", flexShrink: 0 }}>
            <button
              onClick={() => onInsertPath(preview.path)}
              className="btn btn-secondary"
              style={{ width: "100%", fontSize: 9, padding: "6px 10px", letterSpacing: "0.1em" }}
            >
              INSERT PATH IN CHAT
            </button>
          </div>
        </div>
      )}
      {loading && (
        <div style={{
          position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center",
          background: "rgba(7,12,30,0.6)",
        }}>
          <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a7bd5" }}>LOADING…</span>
        </div>
      )}
    </div>
  );
}

// ── New agent modal ───────────────────────────────────────────────────────────

function NewAgentModal({ onClose, onCreated }) {
  const [form, setForm] = useState({ name: "", description: "", type: "assistant" });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    if (!form.name.trim()) return;
    setSaving(true); setError("");
    const r = await fetch(API("/agents"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(form),
    });
    if (r.ok) {
      const data = await r.json();
      onCreated(data.id);
      onClose();
    } else {
      const err = await r.json().catch(() => ({}));
      setError(err.detail || "Failed to create agent");
      setSaving(false);
    }
  };

  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.65)",
      display: "flex", alignItems: "center", justifyContent: "center", zIndex: 200,
    }}>
      <div className="glass-card" style={{ width: 420, padding: 28 }}>
        <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 16, fontWeight: 700, color: "#f0f4ff", marginBottom: 20 }}>
          New Agent
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <input
            className="dg-input"
            placeholder="Agent name"
            value={form.name}
            onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
            onKeyDown={e => e.key === "Enter" && submit()}
          />
          <textarea
            className="dg-input"
            placeholder="Description (what does this agent do?)"
            rows={3}
            value={form.description}
            onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
            style={{ resize: "none" }}
          />
          <select
            className="dg-input"
            value={form.type}
            onChange={e => setForm(f => ({ ...f, type: e.target.value }))}
          >
            <option value="assistant">Assistant</option>
            <option value="dialer">Dialer</option>
            <option value="scraper">Scraper</option>
            <option value="webhook">Webhook</option>
          </select>
        </div>
        {error && (
          <div style={{ fontSize: 11, color: "#dc3c3c", marginTop: 10 }}>{error}</div>
        )}
        <div style={{ display: "flex", gap: 10, marginTop: 20, justifyContent: "flex-end" }}>
          <button className="btn btn-secondary" onClick={onClose}>CANCEL</button>
          <button
            className="btn btn-primary"
            onClick={submit}
            disabled={saving || !form.name.trim()}
          >
            {saving ? "CREATING…" : "CREATE AGENT"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main panel ────────────────────────────────────────────────────────────────

const MODES = [
  { id: "auto",  label: "Auto",  desc: "Runs freely, no confirmation needed" },
  { id: "ask",   label: "Ask",   desc: "Confirms before every file edit" },
  { id: "plan",  label: "Plan",  desc: "Plans only — never writes files" },
];

export default function AgentsPanel({ initialAgentId }) {
  const [agents, setAgents] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [filePanelOpen, setFilePanelOpen] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [mode, setMode] = useState("auto");
  const bottomRef = useRef(null);
  const textareaRef = useRef(null);
  const streamIdRef = useRef(null);
  const abortRef = useRef(null);

  const loadAgents = useCallback(async () => {
    const r = await fetch(API("/agents"));
    if (r.ok) {
      const data = await r.json();
      setAgents(data);
      if (initialAgentId) {
        const match = data.find(a => a.id === initialAgentId || a.name === initialAgentId);
        if (match) { setSelectedId(match.id); return; }
      }
      if (data.length && !selectedId) setSelectedId(data[0].id);
    }
  }, [selectedId, initialAgentId]);

  useEffect(() => { loadAgents(); }, []);

  const loadHistory = useCallback(async (agentId) => {
    const r = await fetch(API(`/agents/${agentId}/history`));
    if (r.ok) setMessages(await r.json());
    else setMessages([]);
  }, []);

  useEffect(() => {
    if (selectedId) { loadHistory(selectedId); setFilePanelOpen(false); }
  }, [selectedId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const selectedAgent = agents.find(a => a.id === selectedId);

  const stopStreaming = () => {
    abortRef.current?.abort();
    abortRef.current = null;
    setMessages(prev => prev.map(m =>
      m._streaming ? { ...m, _streaming: false, _thinkingStreaming: false } : m
    ));
    setStreaming(false);
  };

  const sendMessage = async () => {
    if (!input.trim() || streaming || !selectedId) return;

    const userText = input.trim();
    setInput("");
    setStreaming(true);

    const userId = Date.now();
    const streamId = Date.now() + 1;
    streamIdRef.current = streamId;

    const controller = new AbortController();
    abortRef.current = controller;

    setMessages(prev => [
      ...prev,
      { id: userId, role: "user", content: [{ type: "text", text: userText }] },
      { id: streamId, role: "assistant", content: [{ type: "text", text: "" }], toolBlocks: [], thinking: undefined, _thinkingStreaming: false, _streaming: true },
    ]);

    try {
      const resp = await fetch(API(`/agents/${selectedId}/chat`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userText, mode }),
        signal: controller.signal,
      });

      if (!resp.ok) {
        setMessages(prev => prev.map(m =>
          m.id === streamId ? { ...m, _streaming: false, _error: `HTTP ${resp.status}` } : m
        ));
        setStreaming(false);
        return;
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop();

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          let evt;
          try { evt = JSON.parse(line.slice(6)); } catch { continue; }

          if (evt.type === "thinking_start") {
            setMessages(prev => prev.map(m =>
              m.id === streamId ? { ...m, thinking: "", _thinkingStreaming: true } : m
            ));
          } else if (evt.type === "thinking_delta") {
            setMessages(prev => prev.map(m =>
              m.id === streamId ? { ...m, thinking: (m.thinking || "") + evt.text } : m
            ));
          } else if (evt.type === "thinking_done") {
            setMessages(prev => prev.map(m =>
              m.id === streamId ? { ...m, _thinkingStreaming: false } : m
            ));
          } else if (evt.type === "text_delta") {
            setMessages(prev => prev.map(m =>
              m.id === streamId
                ? { ...m, content: [{ type: "text", text: (m.content[0]?.text || "") + evt.text }] }
                : m
            ));
          } else if (evt.type === "tool_start") {
            setMessages(prev => prev.map(m =>
              m.id === streamId
                ? { ...m, toolBlocks: [...(m.toolBlocks || []), { id: evt.tool_use_id, name: evt.tool_name, status: "running", result: null }] }
                : m
            ));
          } else if (evt.type === "tool_result") {
            setMessages(prev => prev.map(m =>
              m.id === streamId
                ? { ...m, toolBlocks: (m.toolBlocks || []).map(tb =>
                    tb.id === evt.tool_use_id ? { ...tb, status: "done", result: evt.result } : tb
                  )}
                : m
            ));
          } else if (evt.type === "done") {
            setMessages(prev => prev.map(m =>
              m.id === streamId ? { ...m, _streaming: false } : m
            ));
            setStreaming(false);
          } else if (evt.type === "error") {
            setMessages(prev => prev.map(m =>
              m.id === streamId ? { ...m, _streaming: false, _error: evt.message } : m
            ));
            setStreaming(false);
          }
        }
      }
    } catch (err) {
      if (err.name !== "AbortError") {
        setMessages(prev => prev.map(m =>
          m.id === streamIdRef.current ? { ...m, _streaming: false, _error: String(err) } : m
        ));
      }
      setStreaming(false);
    }
  };

  const clearHistory = async () => {
    if (!selectedId) return;
    await fetch(API(`/agents/${selectedId}/history`), { method: "DELETE" });
    setMessages([]);
  };

  const insertPath = (path) => {
    setInput(prev => prev ? `${prev} ${path}` : path);
    textareaRef.current?.focus();
  };

  return (
    <>
      <style>{`
        @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }
        @keyframes spin { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
      `}</style>

      {showModal && (
        <NewAgentModal
          onClose={() => setShowModal(false)}
          onCreated={(id) => { loadAgents(); setSelectedId(id); }}
        />
      )}

      <div style={{ display: "flex", height: "100%", overflow: "hidden" }}>

        {/* ── Left sidebar: agent list ────────────────────────────────── */}
        <aside style={{
          width: 260, flexShrink: 0,
          borderRight: "0.5px solid #1a2540",
          display: "flex", flexDirection: "column",
          background: "rgba(8,12,28,0.6)",
        }}>
          <div style={{
            padding: "16px 16px 12px",
            borderBottom: "0.5px solid #1a2540",
          }}>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a7bd5", letterSpacing: "0.2em" }}>
              AGENTS · {agents.length}
            </div>
          </div>

          <div style={{ flex: 1, overflowY: "auto", padding: "8px 10px", display: "flex", flexDirection: "column", gap: 3 }}>
            {agents.map(agent => {
              const isActive = selectedId === agent.id;
              return (
                <button
                  key={agent.id}
                  onClick={() => setSelectedId(agent.id)}
                  style={{
                    width: "100%", textAlign: "left", border: "none", cursor: "pointer",
                    padding: "10px 12px", borderRadius: 10,
                    background: isActive
                      ? "linear-gradient(90deg, #2857a0 0%, #3a7bd5 100%)"
                      : "transparent",
                    boxShadow: isActive ? "0 4px 14px rgba(58,123,213,0.35)" : "none",
                    transition: "all 0.15s",
                  }}
                  onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = "rgba(58,123,213,0.08)"; }}
                  onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = "transparent"; }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 3 }}>
                    <span
                      className={`badge ${agent.badge_class || "badge-blue"}`}
                      style={{ fontSize: 8, padding: "2px 6px" }}
                    >
                      {agent.id.split("-")[0].toUpperCase()}
                    </span>
                    <span style={{
                      fontFamily: "'Space Grotesk', sans-serif",
                      fontSize: 12, fontWeight: 600,
                      color: isActive ? "#ffffff" : "#c4d0e8",
                    }}>
                      {agent.name}
                    </span>
                  </div>
                  <div style={{
                    fontSize: 11, color: isActive ? "rgba(255,255,255,0.65)" : "#3a5a80",
                    whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                  }}>
                    {agent.description}
                  </div>
                </button>
              );
            })}
          </div>

          <div style={{ padding: "10px 12px", borderTop: "0.5px solid #1a2540" }}>
            <button
              className="btn btn-secondary"
              onClick={() => setShowModal(true)}
              style={{ width: "100%", fontSize: 10, letterSpacing: "0.1em" }}
            >
              + NEW AGENT
            </button>
          </div>
        </aside>

        {/* ── Chat pane ──────────────────────────────────────────────── */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", minWidth: 0 }}>

          {selectedAgent ? (
            <>
              {/* Header */}
              <div style={{
                padding: "14px 20px", borderBottom: "0.5px solid #1a2540",
                display: "flex", alignItems: "center", justifyContent: "space-between",
                flexShrink: 0,
              }}>
                <div>
                  <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 15, fontWeight: 700, color: "#f0f4ff" }}>
                    {selectedAgent.name}
                  </div>
                  <div style={{ fontSize: 11, color: "#3a5a80", marginTop: 2 }}>
                    {selectedAgent.description}
                  </div>
                </div>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  {/* Mode toggles */}
                  <div style={{
                    display: "flex", gap: 2,
                    background: "rgba(7,12,30,0.6)", border: "0.5px solid #1a2540",
                    borderRadius: 8, padding: 3,
                  }}>
                    {MODES.map(m => (
                      <button
                        key={m.id}
                        title={m.desc}
                        onClick={() => setMode(m.id)}
                        style={{
                          background: mode === m.id ? "rgba(58,123,213,0.25)" : "transparent",
                          border: mode === m.id ? "0.5px solid rgba(58,123,213,0.4)" : "0.5px solid transparent",
                          borderRadius: 6, padding: "4px 10px", cursor: "pointer",
                          fontSize: 10, fontFamily: "'Share Tech Mono', monospace",
                          letterSpacing: "0.08em",
                          color: mode === m.id ? "#7aaae8" : "#3a5a80",
                          transition: "all 0.15s",
                        }}
                      >
                        {m.label}
                      </button>
                    ))}
                  </div>
                  <button
                    className="btn btn-ghost"
                    onClick={() => setFilePanelOpen(o => !o)}
                    style={{ fontSize: 10, padding: "6px 12px", letterSpacing: "0.1em",
                             background: filePanelOpen ? "rgba(58,123,213,0.15)" : "transparent" }}
                  >
                    FILES
                  </button>
                  <button
                    className="btn btn-secondary"
                    onClick={clearHistory}
                    style={{ fontSize: 10, padding: "6px 12px", letterSpacing: "0.1em" }}
                  >
                    CLEAR
                  </button>
                </div>
              </div>

              {/* Messages */}
              <div style={{ flex: 1, overflowY: "auto", padding: "20px 24px" }}>
                {messages.length === 0 && (
                  <div style={{
                    display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
                    height: "100%", gap: 10,
                  }}>
                    <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a3a60", letterSpacing: "0.2em" }}>
                      {selectedAgent.id.toUpperCase()} · READY
                    </div>
                    <div style={{ fontSize: 13, color: "#2a4a70", textAlign: "center", maxWidth: 380 }}>
                      Ask me to read, edit, or explain any file in this agent's directory.
                    </div>
                  </div>
                )}
                {messages.map(msg => <MessageBubble key={msg.id} msg={msg} />)}
                <div ref={bottomRef} />
              </div>

              {/* Input */}
              <div style={{
                padding: "12px 20px", borderTop: "0.5px solid #1a2540", flexShrink: 0,
                display: "flex", gap: 10, alignItems: "flex-end",
              }}>
                <textarea
                  ref={textareaRef}
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); sendMessage(); }
                  }}
                  placeholder={`Message ${selectedAgent.name}… (⌘↵ to send)`}
                  className="dg-input"
                  rows={3}
                  disabled={streaming}
                  style={{ resize: "none", flex: 1, lineHeight: 1.5 }}
                />
                {streaming ? (
                  <button
                    onClick={stopStreaming}
                    style={{
                      flexShrink: 0, alignSelf: "flex-end", padding: "9px 18px", fontSize: 11,
                      background: "rgba(180,40,40,0.15)", border: "0.5px solid rgba(220,60,60,0.4)",
                      borderRadius: 8, color: "#e06060", cursor: "pointer",
                      fontFamily: "'Share Tech Mono', monospace", letterSpacing: "0.1em",
                    }}
                  >
                    ■ STOP
                  </button>
                ) : (
                  <button
                    className="btn btn-primary"
                    onClick={sendMessage}
                    disabled={!input.trim()}
                    style={{ flexShrink: 0, alignSelf: "flex-end", padding: "9px 18px", fontSize: 11 }}
                  >
                    SEND
                  </button>
                )}
              </div>
            </>
          ) : (
            <div style={{
              flex: 1, display: "flex", alignItems: "center", justifyContent: "center",
              flexDirection: "column", gap: 8,
            }}>
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a3a60", letterSpacing: "0.2em" }}>
                SELECT AN AGENT
              </div>
            </div>
          )}
        </div>

        {/* ── File panel (togglable) ─────────────────────────────────── */}
        {filePanelOpen && selectedId && (
          <FilePanel
            agentId={selectedId}
            onInsertPath={insertPath}
            onClose={() => setFilePanelOpen(false)}
          />
        )}
      </div>
    </>
  );
}
