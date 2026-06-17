import React, { useState, useEffect, useRef, useCallback } from "react";

const API = (p) => `/api${p}`;

function timeAgo(ts) {
  if (!ts) return "";
  const d = new Date(ts), now = new Date(), diff = now - d;
  if (diff < 60000) return "now";
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h`;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function fmtMsgTime(ts) {
  if (!ts) return "";
  const d = new Date(ts), diff = Date.now() - d;
  if (diff < 86400000) return d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" }) + ", " +
         d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
}

export default function SMSPanel() {
  const [convos, setConvos]       = useState([]);
  const [selected, setSelected]   = useState(null);
  const [thread, setThread]       = useState(null);
  const [replyText, setReplyText] = useState("");
  const [sending, setSending]     = useState(false);
  const [loading, setLoading]     = useState(true);
  const bottomRef = useRef(null);

  const loadConvos = useCallback(async () => {
    try {
      const r = await fetch(API("/sms/conversations"));
      if (r.ok) setConvos(await r.json());
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => { loadConvos(); const id = setInterval(loadConvos, 15000); return () => clearInterval(id); }, [loadConvos]);

  const openThread = async (phone) => {
    setSelected(phone);
    setThread(null);
    try {
      const r = await fetch(API(`/sms/conversations/${encodeURIComponent(phone)}`));
      if (r.ok) setThread(await r.json());
    } catch {}
  };

  useEffect(() => {
    if (!selected) return;
    const id = setInterval(() => openThread(selected), 8000);
    return () => clearInterval(id);
  }, [selected]);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [thread?.messages]);

  const sendReply = async () => {
    if (!replyText.trim() || !selected) return;
    setSending(true);
    try {
      await fetch(API("/sms/send"), {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone: selected, body: replyText.trim() }),
      });
      setReplyText(""); await openThread(selected); await loadConvos();
    } catch {}
    setSending(false);
  };

  const closeConvo = async () => {
    if (!selected) return;
    await fetch(API(`/sms/conversations/${encodeURIComponent(selected)}/close`), { method: "POST" });
    await openThread(selected); await loadConvos();
  };

  return (
    <div style={{ display: "flex", height: "100%" }}>

      {/* Thread list */}
      <aside style={{
        width: 260, borderRight: "0.5px solid #1a2540",
        display: "flex", flexDirection: "column", flexShrink: 0,
      }}>
        <div style={{ padding: "14px 16px", borderBottom: "0.5px solid #1a2540",
                      display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 14, fontWeight: 600, color: "#f0f4ff" }}>
            SMS Inbox
          </div>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80" }}>
            {convos.length} THREADS
          </div>
        </div>

        <div style={{ flex: 1, overflowY: "auto" }}>
          {loading && (
            <div style={{ padding: 16, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52" }}>
              LOADING...
            </div>
          )}
          {!loading && convos.length === 0 && (
            <div style={{ padding: 16, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52" }}>
              NO CONVERSATIONS
            </div>
          )}
          {convos.map(c => (
            <button key={c.phone} onClick={() => openThread(c.phone)}
              style={{
                width: "100%", textAlign: "left", padding: "12px 16px",
                borderBottom: "0.5px solid #1a2540", cursor: "pointer",
                background: selected === c.phone ? "#0d1626" : "transparent",
                borderLeft: `2px solid ${selected === c.phone ? "#3a7bd5" : "transparent"}`,
                border: "none", borderBottom: "0.5px solid #1a2540",
                borderLeft: selected === c.phone ? "2px solid #3a7bd5" : "2px solid transparent",
                transition: "all 0.1s",
              }}
              onMouseEnter={e => { if (selected !== c.phone) e.currentTarget.style.background = "#0a1020"; }}
              onMouseLeave={e => { if (selected !== c.phone) e.currentTarget.style.background = "transparent"; }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 3 }}>
                <span style={{ fontSize: 13, fontWeight: 500, color: "#c4d0e8", overflow: "hidden",
                               textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>
                  {c.business || c.owner || c.phone}
                </span>
                <span className={`badge ${c.status === "closed" ? "badge-green" : "badge-blue"}`}
                  style={{ marginLeft: 6, flexShrink: 0 }}>
                  {c.status === "closed" ? "BOOKED" : "ACTIVE"}
                </span>
              </div>
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a4a7a" }}>
                {c.phone}
              </div>
              {c.last_message && (
                <div style={{ fontSize: 11, color: "#3a4f6f", marginTop: 4,
                              overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {c.last_message}
                </div>
              )}
            </button>
          ))}
        </div>
      </aside>

      {/* Thread view */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        {!selected ? (
          <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center",
                        justifyContent: "center", gap: 8 }}>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52", letterSpacing: "0.2em" }}>
              SELECT A CONVERSATION
            </div>
          </div>
        ) : (
          <>
            {/* Thread header */}
            <div style={{ padding: "14px 20px", borderBottom: "0.5px solid #1a2540",
                          display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0 }}>
              <div>
                <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 14, fontWeight: 600, color: "#f0f4ff" }}>
                  {thread?.business || thread?.owner || selected}
                </div>
                <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80",
                              letterSpacing: "0.1em", marginTop: 2 }}>
                  {selected}{thread?.grade ? ` · GRADE ${thread.grade}` : ""}
                </div>
              </div>
              {thread?.status !== "closed" && (
                <button onClick={closeConvo} className="btn btn-ghost"
                  style={{ fontSize: 10, borderColor: "rgba(20,200,130,0.35)", color: "#14c882" }}>
                  MARK BOOKED
                </button>
              )}
            </div>

            {/* Messages */}
            <div style={{ flex: 1, overflowY: "auto", padding: "16px 20px", display: "flex",
                          flexDirection: "column", gap: 10 }}>
              {!thread && (
                <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52" }}>
                  LOADING...
                </div>
              )}
              {thread?.messages?.map((m, i) => {
                const isOut = m.direction === "outbound";
                return (
                  <div key={i} style={{ display: "flex", justifyContent: isOut ? "flex-end" : "flex-start" }}>
                    <div style={{
                      maxWidth: 320, padding: "9px 13px", borderRadius: isOut ? "8px 8px 2px 8px" : "8px 8px 8px 2px",
                      background: isOut ? "#1f3d70" : "#0d1626",
                      border: `0.5px solid ${isOut ? "#2857a0" : "#1a2540"}`,
                    }}>
                      <div style={{ fontSize: 13, color: isOut ? "#c8dcff" : "#8aaad0", lineHeight: 1.4 }}>
                        {m.body}
                      </div>
                      <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9,
                                    color: isOut ? "#5a7faa" : "#4a6a8a", marginTop: 4, textAlign: isOut ? "right" : "left" }}>
                        {fmtMsgTime(m.sent_at)}
                      </div>
                    </div>
                  </div>
                );
              })}
              <div ref={bottomRef} />
            </div>

            {/* Reply box */}
            {thread?.status !== "closed" ? (
              <div style={{ padding: "12px 20px", borderTop: "0.5px solid #1a2540", flexShrink: 0, display: "flex", gap: 8 }}>
                <textarea
                  value={replyText}
                  onChange={e => setReplyText(e.target.value)}
                  onKeyDown={e => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) sendReply(); }}
                  placeholder="Type a reply… (⌘↵ to send)"
                  rows={2}
                  className="dg-input"
                  style={{ flex: 1, resize: "none", fontSize: 13 }}
                />
                <button onClick={sendReply} disabled={sending || !replyText.trim()}
                  className="btn btn-primary" style={{ alignSelf: "flex-end" }}>
                  {sending ? "..." : "SEND"}
                </button>
              </div>
            ) : (
              <div style={{ padding: "12px 20px", borderTop: "0.5px solid #1a2540",
                            textAlign: "center", fontFamily: "'Share Tech Mono', monospace",
                            fontSize: 10, color: "#14c882", letterSpacing: "0.18em" }}>
                APPOINTMENT BOOKED · CONVERSATION CLOSED
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
