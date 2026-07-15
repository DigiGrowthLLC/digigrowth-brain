import React, { useState, useEffect, useRef, useCallback } from "react";
import { API } from "../api.js";

const TERM_PRESETS = [
  "pip list",
  "python --version",
  "ls -la",
  "ls dashboard/backend/routers/",
  "ls dashboard/frontend/src/panels/",
];

// ── Tool block ────────────────────────────────────────────────────────────────

function ToolBlock({ block }) {
  const [expanded, setExpanded] = useState(false);
  const running = block.status === "running";
  return (
    <div style={{
      fontFamily: "'Share Tech Mono', monospace", fontSize: 11,
      background: "rgba(7,12,30,0.8)", border: "1px solid rgba(58,123,213,0.15)",
      borderRadius: 8, padding: "6px 10px", marginBottom: 4, maxWidth: "88%",
    }}>
      <div
        onClick={() => !running && block.result && setExpanded(e => !e)}
        style={{
          cursor: running || !block.result ? "default" : "pointer",
          display: "flex", alignItems: "center", gap: 6,
          color: running ? "#f0a028" : block.name === "run_bash" ? "#14c882" : "#3a7bd5",
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
          marginTop: 6, color: "#4a6a8a", maxHeight: 300, overflowY: "auto",
          whiteSpace: "pre-wrap", wordBreak: "break-all", fontSize: 10,
          borderTop: "1px solid rgba(58,123,213,0.1)", paddingTop: 6,
        }}>
          {block.result}
        </div>
      )}
    </div>
  );
}

// ── Message bubble ────────────────────────────────────────────────────────────

function MessageBubble({ msg }) {
  const isUser = msg.role === "user";
  const textContent = msg.content?.find(b => b.type === "text");
  const text = textContent?.text || "";
  const toolBlocks = msg.toolBlocks || [];
  const isStreaming = msg._streaming;

  if (isUser) {
    return (
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 12 }}>
        <div style={{
          maxWidth: "75%", padding: "10px 14px", borderRadius: "14px 14px 4px 14px",
          background: "linear-gradient(135deg, #1f3d70 0%, #162a50 100%)",
          border: "1px solid rgba(58,123,213,0.25)",
          fontFamily: "'Space Grotesk', sans-serif", fontSize: 13, color: "#c8dcff",
          lineHeight: 1.6, whiteSpace: "pre-wrap", wordBreak: "break-word",
        }}>
          {text}
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", marginBottom: 12, gap: 4 }}>
      {toolBlocks.map(tb => <ToolBlock key={tb.id} block={tb} />)}
      {(text || isStreaming) && (
        <div className="glass-card-sm" style={{
          maxWidth: "88%", padding: "10px 14px", borderRadius: "4px 14px 14px 14px",
          fontFamily: "'Space Grotesk', sans-serif", fontSize: 13, color: "#b0c8e8",
          lineHeight: 1.7, whiteSpace: "pre-wrap", wordBreak: "break-word",
        }}>
          {text}
          {isStreaming && (
            <span style={{ display: "inline-block", width: 7, height: 13, background: "#3a7bd5",
                           marginLeft: 2, verticalAlign: "text-bottom",
                           animation: "blink 1s step-end infinite" }} />
          )}
        </div>
      )}
      {msg._error && (
        <div style={{ fontSize: 11, color: "#dc3c3c", fontFamily: "'Share Tech Mono', monospace" }}>
          {msg._error}
        </div>
      )}
    </div>
  );
}

// ── File tree ─────────────────────────────────────────────────────────────────

function FileNode({ node, onSelect, selectedPath }) {
  const [open, setOpen] = useState(false);
  const isDir = node.type === "dir";
  const isSelected = node.path === selectedPath;

  return (
    <div>
      <div
        onClick={() => isDir ? setOpen(o => !o) : onSelect(node)}
        style={{
          display: "flex", alignItems: "center", gap: 6,
          padding: "3px 6px", borderRadius: 6, cursor: "pointer",
          background: isSelected ? "rgba(58,123,213,0.15)" : "transparent",
          color: isDir ? "#5a9bf0" : "#7aaad0",
          fontSize: 12, fontFamily: "'Space Grotesk', sans-serif",
        }}
        onMouseEnter={e => { if (!isSelected) e.currentTarget.style.background = "rgba(58,123,213,0.06)"; }}
        onMouseLeave={e => { if (!isSelected) e.currentTarget.style.background = "transparent"; }}
      >
        <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: isDir ? "#3a5a80" : "#2a3a50", width: 12, flexShrink: 0 }}>
          {isDir ? (open ? "▾" : "▸") : "·"}
        </span>
        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{node.name}</span>
      </div>
      {isDir && open && node.children && (
        <div style={{ paddingLeft: 14 }}>
          {node.children.map(child => (
            <FileNode key={child.path} node={child} onSelect={onSelect} selectedPath={selectedPath} />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Settings panel ────────────────────────────────────────────────────────────

export default function SettingsPanel() {
  const [messages, setMessages]       = useState([]);
  const [input, setInput]             = useState("");
  const [streaming, setStreaming]     = useState(false);
  const [rightPanel, setRightPanel]   = useState("terminal"); // "terminal" | "files" | null
  const [termCmd, setTermCmd]         = useState("");
  const [termOutput, setTermOutput]   = useState("");
  const [termRunning, setTermRunning] = useState(false);
  const [fileTree, setFileTree]       = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileContent, setFileContent]   = useState(null);

  const bottomRef    = useRef(null);
  const termBottomRef = useRef(null);
  const textareaRef  = useRef(null);
  const streamIdRef  = useRef(null);

  // Load history on mount
  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(API("/settings/history"));
        if (r.ok) setMessages(await r.json());
      } catch {}
    })();
  }, []);

  // Load file tree when files panel opens
  useEffect(() => {
    if (rightPanel !== "files" || fileTree.length > 0) return;
    (async () => {
      try {
        const r = await fetch(API("/settings/files"));
        if (r.ok) { const d = await r.json(); setFileTree(d.files || []); }
      } catch {}
    })();
  }, [rightPanel]);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);
  useEffect(() => { termBottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [termOutput]);

  // ── Send chat message ──────────────────────────────────────────────────────

  const sendMessage = async () => {
    if (!input.trim() || streaming) return;
    const userText = input.trim();
    setInput("");
    setStreaming(true);

    const userId   = Date.now();
    const streamId = Date.now() + 1;
    streamIdRef.current = streamId;

    setMessages(prev => [
      ...prev,
      { id: userId, role: "user", content: [{ type: "text", text: userText }] },
      { id: streamId, role: "assistant", content: [{ type: "text", text: "" }], toolBlocks: [], _streaming: true },
    ]);

    try {
      const resp = await fetch(API("/settings/chat"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userText }),
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
        const lines = buf.split("\n"); buf = lines.pop();

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          let evt; try { evt = JSON.parse(line.slice(6)); } catch { continue; }

          if (streamIdRef.current !== streamId) break;

          if (evt.type === "text_delta") {
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
    } catch (e) {
      setMessages(prev => prev.map(m =>
        m.id === streamId ? { ...m, _streaming: false, _error: e.message } : m
      ));
      setStreaming(false);
    }
  };

  // ── Clear history ──────────────────────────────────────────────────────────

  const clearHistory = async () => {
    await fetch(API("/settings/history"), { method: "DELETE" });
    setMessages([]);
  };

  // ── Terminal exec ──────────────────────────────────────────────────────────

  const runCommand = async (cmd) => {
    const c = (cmd !== undefined ? cmd : termCmd).trim();
    if (!c || termRunning) return;
    setTermOutput(prev => prev + `$ ${c}\n`);
    setTermRunning(true);
    try {
      const resp = await fetch(API("/settings/exec"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command: c }),
      });
      if (!resp.ok) { setTermOutput(prev => prev + `[HTTP ${resp.status}]\n`); return; }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n"); buf = lines.pop();
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          let evt; try { evt = JSON.parse(line.slice(6)); } catch { continue; }
          if (evt.type === "output") setTermOutput(prev => prev + evt.text);
          else if (evt.type === "done") setTermOutput(prev => prev + (evt.code ? `[exit ${evt.code}]\n` : ""));
          else if (evt.type === "error") setTermOutput(prev => prev + `[error: ${evt.message}]\n`);
        }
      }
    } catch (e) {
      setTermOutput(prev => prev + `[error: ${e.message}]\n`);
    } finally {
      setTermRunning(false);
    }
  };

  // ── File select ────────────────────────────────────────────────────────────

  const openFile = async (node) => {
    setSelectedFile(node.path);
    setFileContent(null);
    try {
      const r = await fetch(API(`/settings/files/${node.path}`));
      if (r.ok) { const d = await r.json(); setFileContent(d.content); }
      else setFileContent(`[error: HTTP ${r.status}]`);
    } catch (e) {
      setFileContent(`[error: ${e.message}]`);
    }
  };

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div style={{ display: "flex", height: "100%", overflow: "hidden" }}>

      {/* ── Chat pane ─────────────────────────────────────────────────────── */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", minWidth: 0 }}>

        {/* Header */}
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "14px 20px 12px",
          borderBottom: "1px solid rgba(58,123,213,0.07)", flexShrink: 0,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <svg viewBox="0 0 18 18" fill="none" width={16} height={16}>
              <circle cx="9" cy="9" r="3" stroke="#3a7bd5" strokeWidth="1.5"/>
              <path d="M9 2v2M9 14v2M2 9h2M14 9h2M3.93 3.93l1.41 1.41M12.66 12.66l1.41 1.41M3.93 14.07l1.41-1.41M12.66 5.34l1.41-1.41" stroke="#3a7bd5" strokeWidth="1.4" strokeLinecap="round"/>
            </svg>
            <div>
              <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 15, fontWeight: 700, color: "#f0f4ff" }}>
                DigiGrowth OS
              </div>
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a4a7a", letterSpacing: "0.14em", marginTop: 1 }}>
                CLAUDE CODE · FULL REPO ACCESS
              </div>
            </div>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            {(["terminal", "files"]).map(panel => (
              <button
                key={panel}
                onClick={() => setRightPanel(rightPanel === panel ? null : panel)}
                style={{
                  fontFamily: "'Share Tech Mono', monospace", fontSize: 9,
                  padding: "5px 12px", borderRadius: 8,
                  background: rightPanel === panel ? "rgba(58,123,213,0.2)" : "transparent",
                  border: `1px solid ${rightPanel === panel ? "rgba(58,123,213,0.4)" : "rgba(58,123,213,0.15)"}`,
                  color: rightPanel === panel ? "#6ab0ff" : "#3a5a80",
                  cursor: "pointer", letterSpacing: "0.12em", textTransform: "uppercase",
                }}
              >
                {panel}
              </button>
            ))}
          </div>
        </div>

        {/* Messages */}
        <div style={{ flex: 1, overflowY: "auto", padding: "16px 20px" }}>
          {messages.length === 0 && (
            <div style={{
              display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
              height: "100%", gap: 12, opacity: 0.4,
            }}>
              <svg viewBox="0 0 18 18" fill="none" width={32} height={32}>
                <circle cx="9" cy="9" r="3" stroke="#3a7bd5" strokeWidth="1.5"/>
                <path d="M9 2v2M9 14v2M2 9h2M14 9h2M3.93 3.93l1.41 1.41M12.66 12.66l1.41 1.41M3.93 14.07l1.41-1.41M12.66 5.34l1.41-1.41" stroke="#3a7bd5" strokeWidth="1.4" strokeLinecap="round"/>
              </svg>
              <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 13, color: "#3a5a80", textAlign: "center" }}>
                Ask me to read, edit, or create any file in the repo.
                <br />I can also run shell commands.
              </div>
            </div>
          )}
          {messages.map(msg => <MessageBubble key={msg.id || msg.created_at} msg={msg} />)}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div style={{
          padding: "12px 16px", borderTop: "1px solid rgba(58,123,213,0.07)",
          display: "flex", flexDirection: "column", gap: 8, flexShrink: 0,
        }}>
          <textarea
            ref={textareaRef}
            className="dg-input"
            rows={3}
            style={{ resize: "none", fontFamily: "'Space Grotesk', sans-serif", fontSize: 13, lineHeight: 1.5 }}
            placeholder="Ask Claude to read a file, make a change, run a command…  (Cmd+Enter to send)"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); sendMessage(); }
            }}
          />
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <button
              className="btn btn-secondary"
              onClick={clearHistory}
              disabled={streaming}
              style={{ fontSize: 10, letterSpacing: "0.08em" }}
            >
              CLEAR HISTORY
            </button>
            <button
              className="btn btn-primary"
              onClick={sendMessage}
              disabled={streaming || !input.trim()}
              style={{ minWidth: 80 }}
            >
              {streaming ? "…" : "SEND"}
            </button>
          </div>
        </div>
      </div>

      {/* ── Right panel ───────────────────────────────────────────────────── */}
      {rightPanel && (
        <div style={{
          width: 340, flexShrink: 0,
          borderLeft: "1px solid rgba(58,123,213,0.07)",
          display: "flex", flexDirection: "column", overflow: "hidden",
          background: "rgba(7,12,30,0.4)",
        }}>

          {/* Terminal panel */}
          {rightPanel === "terminal" && (
            <>
              <div style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                padding: "10px 14px", borderBottom: "1px solid rgba(58,123,213,0.07)",
              }}>
                <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a7bd5", letterSpacing: "0.14em" }}>
                  TERMINAL
                </span>
                <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                  <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a3a50" }}>repo root</span>
                  <button
                    onClick={() => setTermOutput("")}
                    style={{
                      fontFamily: "'Share Tech Mono', monospace", fontSize: 9,
                      padding: "2px 8px", borderRadius: 4,
                      background: "transparent", border: "1px solid rgba(58,123,213,0.15)",
                      color: "#2a4a7a", cursor: "pointer",
                    }}
                  >
                    CLR
                  </button>
                </div>
              </div>

              {/* Presets */}
              <div style={{ display: "flex", flexWrap: "wrap", gap: 5, padding: "10px 12px", borderBottom: "1px solid rgba(58,123,213,0.05)" }}>
                {TERM_PRESETS.map(p => (
                  <button
                    key={p}
                    onClick={() => { setTermCmd(p); runCommand(p); }}
                    disabled={termRunning}
                    style={{
                      fontFamily: "'Share Tech Mono', monospace", fontSize: 9,
                      padding: "3px 8px", borderRadius: 5,
                      background: "rgba(58,123,213,0.07)",
                      border: "1px solid rgba(58,123,213,0.18)",
                      color: "#3a7bd5", cursor: termRunning ? "not-allowed" : "pointer",
                      opacity: termRunning ? 0.5 : 1, letterSpacing: "0.04em",
                    }}
                  >
                    {p}
                  </button>
                ))}
              </div>

              {/* Output */}
              <div style={{
                flex: 1, overflowY: "auto",
                background: "#050d1a", margin: "0 10px 0",
                fontFamily: "'Share Tech Mono', monospace", fontSize: 11,
                color: "#7aaad0", whiteSpace: "pre-wrap", wordBreak: "break-all",
                padding: "10px 12px", minHeight: 80,
              }}>
                {termOutput || <span style={{ color: "#1a2f52" }}>— ready —</span>}
                <div ref={termBottomRef} />
              </div>

              {/* Input */}
              <div style={{ display: "flex", gap: 6, padding: "10px 10px 12px", flexShrink: 0 }}>
                <input
                  className="dg-input"
                  style={{ flex: 1, fontFamily: "'Share Tech Mono', monospace", fontSize: 12 }}
                  placeholder="command..."
                  value={termCmd}
                  onChange={e => setTermCmd(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && runCommand()}
                  disabled={termRunning}
                />
                <button
                  className="btn btn-primary"
                  onClick={() => runCommand()}
                  disabled={termRunning || !termCmd.trim()}
                  style={{ minWidth: 50, fontSize: 11 }}
                >
                  {termRunning ? "…" : "RUN"}
                </button>
              </div>
            </>
          )}

          {/* Files panel */}
          {rightPanel === "files" && (
            <>
              <div style={{ padding: "10px 14px", borderBottom: "1px solid rgba(58,123,213,0.07)" }}>
                <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#3a7bd5", letterSpacing: "0.14em" }}>
                  FILES
                </span>
                <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a3a50", marginLeft: 8 }}>
                  repo root
                </span>
              </div>

              {selectedFile && fileContent !== null ? (
                /* File preview */
                <div style={{ display: "flex", flexDirection: "column", flex: 1, overflow: "hidden" }}>
                  <div style={{
                    display: "flex", alignItems: "center", justifyContent: "space-between",
                    padding: "8px 12px", borderBottom: "1px solid rgba(58,123,213,0.07)",
                  }}>
                    <span style={{
                      fontFamily: "'Share Tech Mono', monospace", fontSize: 9,
                      color: "#5a9bf0", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                    }}>
                      {selectedFile}
                    </span>
                    <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
                      <button
                        onClick={() => {
                          setInput(prev => prev ? `${prev} ${selectedFile}` : selectedFile);
                          textareaRef.current?.focus();
                        }}
                        style={{
                          fontFamily: "'Share Tech Mono', monospace", fontSize: 8,
                          padding: "2px 7px", borderRadius: 4,
                          background: "rgba(58,123,213,0.1)", border: "1px solid rgba(58,123,213,0.2)",
                          color: "#3a7bd5", cursor: "pointer", whiteSpace: "nowrap",
                        }}
                      >
                        INSERT PATH
                      </button>
                      <button
                        onClick={() => { setSelectedFile(null); setFileContent(null); }}
                        style={{
                          fontFamily: "'Share Tech Mono', monospace", fontSize: 8,
                          padding: "2px 7px", borderRadius: 4,
                          background: "transparent", border: "1px solid rgba(58,123,213,0.15)",
                          color: "#2a4a7a", cursor: "pointer",
                        }}
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                  <div style={{
                    flex: 1, overflowY: "auto", padding: "10px 12px",
                    fontFamily: "'Share Tech Mono', monospace", fontSize: 10,
                    color: "#6a8aaa", whiteSpace: "pre", overflowX: "auto",
                    background: "rgba(5,13,26,0.5)",
                  }}>
                    {fileContent}
                  </div>
                </div>
              ) : (
                /* File tree */
                <div style={{ flex: 1, overflowY: "auto", padding: "8px 6px" }}>
                  {fileTree.map(node => (
                    <FileNode key={node.path} node={node} onSelect={openFile} selectedPath={selectedFile} />
                  ))}
                  {fileTree.length === 0 && (
                    <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52", padding: 12 }}>
                      loading...
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      )}

      <style>{`
        @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }
        @keyframes spin { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
      `}</style>
    </div>
  );
}
