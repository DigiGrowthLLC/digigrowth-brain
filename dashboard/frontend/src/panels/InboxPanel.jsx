import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { API } from "../api.js";
import ContactCard from "../ContactCard.jsx";

function fmtMsgTime(ts) {
  if (!ts) return "";
  const d = new Date(ts), diff = Date.now() - d;
  if (diff < 86400000) return d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" }) + ", " +
         d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
}

// ── Compose Modal ─────────────────────────────────────────────────────────────

function convoBadge(c) {
  if (c.status === "closed") {
    return c.disposition === "not_interested"
      ? { label: "NOT INTERESTED", cls: "badge-red" }
      : { label: "BOOKED", cls: "badge-green" };
  }
  if (c.disposition === "interested") {
    return { label: "INTERESTED", cls: "badge-amber" };
  }
  return { label: "ACTIVE", cls: "badge-blue" };
}

function ComposeModal({ onClose, onSent }) {
  const [channel, setChannel] = useState("sms");
  const [to, setTo]           = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody]       = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError]     = useState(null);

  const handleSend = async () => {
    const b = body.trim();
    if (channel === "sms") {
      const p = to.trim().replace(/\s+/g, "");
      if (!p || !b) return;
      setSending(true);
      setError(null);
      try {
        const r = await fetch(API("/sms/send"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ phone: p, body: b }),
        });
        if (!r.ok) { setError(await r.text()); return; }
        onSent({ channel: "sms", thread_key: p });
      } catch (e) {
        setError(e.message);
      } finally {
        setSending(false);
      }
    } else {
      const addr = to.trim();
      if (!addr || !b) return;
      setSending(true);
      setError(null);
      try {
        const r = await fetch(API("/email/send"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ thread_id: "", to: addr, subject: subject.trim(), body: b }),
        });
        const data = await r.json().catch(() => ({}));
        if (!r.ok || !data.ok) { setError(data.error || "Failed to send"); return; }
        onSent({ channel: "email", thread_key: data.thread_id });
      } catch (e) {
        setError(e.message);
      } finally {
        setSending(false);
      }
    }
  };

  return (
    <div
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.65)",
        backdropFilter: "blur(6px)", zIndex: 1000,
        display: "flex", alignItems: "center", justifyContent: "center",
      }}
      onClick={onClose}
    >
      <div
        className="glass-card"
        style={{ width: 420, padding: 0, overflow: "hidden" }}
        onClick={e => e.stopPropagation()}
      >
        <div style={{ padding: "18px 22px 14px", borderBottom: "0.5px solid #1a2540", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 15, fontWeight: 700, color: "#f0f4ff" }}>
            New Message
          </div>
          <button onClick={onClose} style={{ background: "transparent", border: "none", color: "#3a5a80", cursor: "pointer", fontSize: 18, lineHeight: 1, padding: "2px 6px" }}>×</button>
        </div>

        <div style={{ padding: "18px 22px" }}>
          <div style={{ marginBottom: 14, display: "flex", gap: 8 }}>
            {["sms", "email"].map(c => (
              <button key={c} onClick={() => setChannel(c)}
                style={{
                  flex: 1, padding: "6px 0", borderRadius: 6,
                  border: `1px solid ${channel === c ? "rgba(58,123,213,0.6)" : "rgba(58,123,213,0.2)"}`,
                  background: channel === c ? "rgba(58,123,213,0.15)" : "transparent",
                  color: channel === c ? "#3a7bd5" : "#5a6f8f",
                  fontFamily: "'Share Tech Mono', monospace", fontSize: 10, letterSpacing: "0.08em",
                  cursor: "pointer",
                }}>
                {c === "sms" ? "SMS" : "EMAIL"}
              </button>
            ))}
          </div>
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", letterSpacing: "0.12em", marginBottom: 5 }}>
              {channel === "sms" ? "TO (PHONE NUMBER)" : "TO (EMAIL ADDRESS)"}
            </div>
            <input
              className="dg-input"
              type={channel === "sms" ? "tel" : "email"}
              placeholder={channel === "sms" ? "+1 555 000 0000" : "prospect@example.com"}
              value={to}
              onChange={e => setTo(e.target.value)}
              style={{ width: "100%", fontSize: 13, boxSizing: "border-box" }}
              autoFocus
            />
          </div>
          {channel === "email" && (
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", letterSpacing: "0.12em", marginBottom: 5 }}>SUBJECT</div>
              <input
                className="dg-input"
                type="text"
                placeholder="Subject"
                value={subject}
                onChange={e => setSubject(e.target.value)}
                style={{ width: "100%", fontSize: 13, boxSizing: "border-box" }}
              />
            </div>
          )}
          <div style={{ marginBottom: 6 }}>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a7bd5", letterSpacing: "0.12em", marginBottom: 5 }}>MESSAGE</div>
            <textarea
              className="dg-input"
              rows={4}
              placeholder="Type your message…"
              value={body}
              onChange={e => setBody(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleSend(); }}
              style={{ width: "100%", fontSize: 13, resize: "none", boxSizing: "border-box" }}
            />
          </div>
          {error && (
            <div style={{ marginBottom: 10, padding: "8px 12px", borderRadius: 8,
              background: "rgba(220,60,60,0.08)", border: "1px solid rgba(220,60,60,0.2)",
              fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#dc3c3c" }}>
              {error}
            </div>
          )}
        </div>

        <div style={{ padding: "12px 22px 18px", display: "flex", gap: 10 }}>
          <button onClick={onClose} className="btn btn-secondary" style={{ flex: 1, fontSize: 11 }}>Cancel</button>
          <button
            onClick={handleSend}
            disabled={sending || !to.trim() || !body.trim()}
            className="btn btn-primary"
            style={{ flex: 1, fontSize: 11 }}
          >
            {sending ? "Sending…" : "Send"}
          </button>
        </div>
      </div>
    </div>
  );
}


// ── Main panel ────────────────────────────────────────────────────────────────

export default function InboxPanel({ initialTarget }) {
  const [convos, setConvos]       = useState([]);
  const [selected, setSelected]   = useState(null); // {channel, thread_key}
  const [thread, setThread]       = useState(null);
  const [replyText, setReplyText] = useState("");
  const [replySubject, setReplySubject] = useState("");
  const [sending, setSending]     = useState(false);
  const [loading, setLoading]     = useState(true);
  const [cardOpen, setCardOpen]   = useState(false);
  const [deleting, setDeleting]   = useState(false);
  const [composing, setComposing] = useState(false);
  const [seqOpen, setSeqOpen]       = useState(false);
  const [seqLoading, setSeqLoading] = useState(false);
  const [seqSteps, setSeqSteps]     = useState([]);
  const [seqTitle, setSeqTitle]     = useState("");
  const [seqError, setSeqError]     = useState(null);

  const [channelFilter, setChannelFilter] = useState("all");
  const [timeFilter, setTimeFilter]       = useState("all");
  const [tagFilter, setTagFilter]         = useState(null);

  const bottomRef = useRef(null);

  const availableTags = useMemo(
    () => [...new Set(convos.flatMap(c => c.tags || []))].sort(),
    [convos]
  );

  const loadConvos = useCallback(async () => {
    try {
      const params = new URLSearchParams({ channel: channelFilter, since: timeFilter });
      if (tagFilter) params.set("tag", tagFilter);
      const r = await fetch(API(`/inbox/conversations?${params.toString()}`));
      if (r.ok) setConvos(await r.json());
    } catch {}
    setLoading(false);
  }, [channelFilter, timeFilter, tagFilter]);

  useEffect(() => {
    loadConvos();
    const id = setInterval(loadConvos, 15000);
    return () => clearInterval(id);
  }, [loadConvos]);

  useEffect(() => {
    if (initialTarget?.phone) openThread({ channel: initialTarget.channel || "sms", thread_key: initialTarget.phone });
    else if (initialTarget?.threadId) openThread({ channel: initialTarget.channel || "email", thread_key: initialTarget.threadId });
  }, [initialTarget]);

  const threadPath = (item) =>
    item.channel === "email"
      ? `/email/conversations/${encodeURIComponent(item.thread_key)}`
      : `/sms/conversations/${encodeURIComponent(item.thread_key)}`;

  // Silently refetch the currently-open thread — used by background polling
  // and post-action refreshes, where blanking the view first (openThread's
  // setThread(null)) would cause a visible flash every few seconds.
  const refreshThread = async (item) => {
    try {
      const r = await fetch(API(threadPath(item)));
      if (r.ok) setThread(await r.json());
    } catch {}
  };

  const openThread = async (item) => {
    setSelected(item);
    setThread(null);
    setSeqOpen(false);
    setReplySubject("");
    await refreshThread(item);
  };

  useEffect(() => {
    if (!selected) return;
    const id = setInterval(() => refreshThread(selected), 8000);
    return () => clearInterval(id);
  }, [selected]);

  useEffect(() => {
    if (thread?.subject && selected?.channel === "email") {
      setReplySubject(thread.subject.toLowerCase().startsWith("re:") ? thread.subject : `Re: ${thread.subject}`);
    }
  }, [thread, selected]);

  // Only auto-scroll when the message count actually grows — every poll
  // returns a fresh array reference even with no new messages, so keying
  // off the array itself would re-trigger a smooth-scroll every 8s.
  const msgCount = thread?.messages?.length ?? 0;
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgCount]);

  const sendReply = async () => {
    if (!replyText.trim() || !selected) return;
    setSending(true);
    try {
      if (selected.channel === "sms") {
        await fetch(API("/sms/send"), {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ phone: selected.thread_key, body: replyText.trim() }),
        });
      } else {
        await fetch(API("/email/send"), {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            thread_id: selected.thread_key,
            to: thread?.email,
            subject: replySubject || thread?.subject || "",
            body: replyText.trim(),
          }),
        });
      }
      setReplyText("");
      await refreshThread(selected);
      await loadConvos();
    } catch {}
    setSending(false);
  };

  const openSequence = async () => {
    if (seqOpen) { setSeqOpen(false); return; }
    setSeqOpen(true);
    setSeqLoading(true);
    setSeqError(null);
    try {
      const r = await fetch(API(`/sms/sequence/${encodeURIComponent(selected.thread_key)}`));
      const data = await r.json();
      if (!data.ok) {
        setSeqError("Failed to load sequence.");
        setSeqSteps([]);
      } else {
        setSeqSteps(data.steps);
        setSeqTitle(data.sequence_title);
      }
    } catch {
      setSeqError("Failed to load sequence.");
      setSeqSteps([]);
    }
    setSeqLoading(false);
  };

  const applyStep = (text) => {
    setReplyText(text);
    setSeqOpen(false);
  };

  const closeConvo = async (disposition) => {
    if (!selected) return;
    const base = selected.channel === "email" ? "/email/conversations" : "/sms/conversations";
    await fetch(API(`${base}/${encodeURIComponent(selected.thread_key)}/close`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ disposition }),
    });
    await refreshThread(selected);
    await loadConvos();
  };

  const toggleInterested = async () => {
    if (!selected) return;
    const base = selected.channel === "email" ? "/email/conversations" : "/sms/conversations";
    await fetch(API(`${base}/${encodeURIComponent(selected.thread_key)}/interested`), { method: "POST" });
    await refreshThread(selected);
    await loadConvos();
  };

  const deleteConvo = async () => {
    if (!selected) return;
    setDeleting(true);
    try {
      const base = selected.channel === "email" ? "/email/conversations" : "/sms/conversations";
      await fetch(API(`${base}/${encodeURIComponent(selected.thread_key)}`), { method: "DELETE" });
      setSelected(null);
      setThread(null);
      await loadConvos();
    } catch {}
    setDeleting(false);
  };

  const selectStyle = {
    fontFamily: "'Share Tech Mono', monospace", fontSize: 9, letterSpacing: "0.06em",
    background: "#0d1626", color: "#c4d0e8", border: "1px solid #1a2540",
    borderRadius: 6, padding: "5px 8px", cursor: "pointer",
  };

  return (
    <div style={{ display: "flex", height: "100%" }}>

      {cardOpen && (
        <ContactCard
          contactId={thread?.contact_id}
          phone={selected?.channel === "sms" ? selected.thread_key : undefined}
          onClose={() => setCardOpen(false)}
          onSaved={() => refreshThread(selected)}
        />
      )}

      {composing && (
        <ComposeModal
          onClose={() => setComposing(false)}
          onSent={async (item) => {
            setComposing(false);
            await loadConvos();
            await openThread(item);
          }}
        />
      )}

      {/* Thread list */}
      <aside style={{
        width: 280, borderRight: "0.5px solid #1a2540",
        display: "flex", flexDirection: "column", flexShrink: 0,
      }}>
        <div style={{ padding: "14px 16px", borderBottom: "0.5px solid #1a2540",
                      display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 14, fontWeight: 600, color: "#f0f4ff" }}>
            Inbox
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80" }}>
              {convos.length} THREADS
            </div>
            <button
              onClick={() => setComposing(true)}
              style={{
                padding: "4px 10px", borderRadius: 6,
                border: "1px solid rgba(58,123,213,0.35)",
                background: "rgba(58,123,213,0.08)", color: "#3a7bd5",
                fontFamily: "'Share Tech Mono', monospace", fontSize: 9,
                cursor: "pointer", letterSpacing: "0.06em",
              }}
            >
              + NEW
            </button>
          </div>
        </div>

        {/* Filter bar */}
        <div style={{ padding: "10px 16px", borderBottom: "0.5px solid #1a2540", display: "flex", flexDirection: "column", gap: 8 }}>
          <div style={{ display: "flex", gap: 6 }}>
            <select value={channelFilter} onChange={e => setChannelFilter(e.target.value)} style={{ ...selectStyle, flex: 1 }}>
              <option value="all">ALL CHANNELS</option>
              <option value="sms">SMS ONLY</option>
              <option value="email">EMAIL ONLY</option>
            </select>
            <select value={timeFilter} onChange={e => setTimeFilter(e.target.value)} style={{ ...selectStyle, flex: 1 }}>
              <option value="all">ALL TIME</option>
              <option value="today">TODAY</option>
              <option value="7d">LAST 7 DAYS</option>
              <option value="30d">LAST 30 DAYS</option>
            </select>
          </div>
          {availableTags.length > 0 && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
              {availableTags.map(t => (
                <button key={t} onClick={() => setTagFilter(tagFilter === t ? null : t)}
                  style={{
                    fontFamily: "'Share Tech Mono', monospace", fontSize: 8.5, letterSpacing: "0.04em",
                    padding: "3px 8px", borderRadius: 10, cursor: "pointer",
                    border: `1px solid ${tagFilter === t ? "rgba(58,123,213,0.7)" : "rgba(58,123,213,0.25)"}`,
                    background: tagFilter === t ? "rgba(58,123,213,0.2)" : "transparent",
                    color: tagFilter === t ? "#c8dcff" : "#5a6f8f",
                  }}>
                  {t}
                </button>
              ))}
            </div>
          )}
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
          {convos.map(c => {
            const isSel = selected?.channel === c.channel && selected?.thread_key === c.thread_key;
            return (
              <button key={`${c.channel}:${c.thread_key}`} onClick={() => openThread({ channel: c.channel, thread_key: c.thread_key })}
                style={{
                  width: "100%", textAlign: "left", padding: "12px 16px",
                  cursor: "pointer",
                  background: isSel ? "#0d1626" : "transparent",
                  borderBottom: "0.5px solid #1a2540",
                  borderLeft: isSel ? "2px solid #3a7bd5" : "2px solid transparent",
                  borderTop: "none", borderRight: "none",
                  transition: "all 0.1s",
                }}
                onMouseEnter={e => { if (!isSel) e.currentTarget.style.background = "#0a1020"; }}
                onMouseLeave={e => { if (!isSel) e.currentTarget.style.background = "transparent"; }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 3 }}>
                  <span style={{ fontSize: 13, fontWeight: 500, color: "#c4d0e8", overflow: "hidden",
                                 textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>
                    {c.owner || c.business || c.thread_key}
                  </span>
                  <span style={{
                    fontFamily: "'Share Tech Mono', monospace", fontSize: 8, letterSpacing: "0.05em",
                    padding: "2px 5px", borderRadius: 4, marginLeft: 6, flexShrink: 0,
                    background: c.channel === "email" ? "rgba(160,110,240,0.12)" : "rgba(20,200,130,0.12)",
                    color: c.channel === "email" ? "#a06ef0" : "#14c882",
                  }}>
                    {c.channel === "email" ? "MAIL" : "SMS"}
                  </span>
                  <span className={`badge ${convoBadge(c).cls}`}
                    style={{ marginLeft: 6, flexShrink: 0 }}>
                    {convoBadge(c).label}
                  </span>
                </div>
                <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#2a4a7a" }}>
                  {c.channel === "email" ? (c.subject || c.thread_key) : c.thread_key}
                </div>
                {c.last_message && (
                  <div style={{ fontSize: 11, color: "#3a4f6f", marginTop: 4,
                                overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {c.last_message}
                  </div>
                )}
              </button>
            );
          })}
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
              <div
                onClick={() => setCardOpen(true)}
                style={{ cursor: "pointer" }}
                title="View contact card"
              >
                <div style={{
                  fontFamily: "'Space Grotesk', sans-serif", fontSize: 14, fontWeight: 600, color: "#f0f4ff",
                  display: "flex", alignItems: "center", gap: 6,
                }}>
                  {thread?.owner || thread?.business || selected.thread_key}
                  <span style={{
                    fontFamily: "'Share Tech Mono', monospace", fontSize: 8, color: "#3a7bd5",
                    padding: "2px 6px", borderRadius: 4, background: "rgba(58,123,213,0.1)",
                    letterSpacing: "0.06em",
                  }}>VIEW</span>
                </div>
                <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80",
                              letterSpacing: "0.1em", marginTop: 2 }}>
                  {selected.channel === "email" ? (thread?.email || selected.thread_key) : selected.thread_key}
                  {thread?.grade ? ` · GRADE ${thread.grade}` : ""}
                  {selected.channel === "email" && thread?.subject ? ` · ${thread.subject}` : ""}
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                {thread?.status !== "closed" && (
                  <>
                    <button onClick={toggleInterested} className="btn btn-ghost"
                      style={{
                        fontSize: 10,
                        borderColor: thread?.disposition === "interested" ? "rgba(240,160,40,0.6)" : "rgba(240,160,40,0.35)",
                        color: "#f0a028",
                        background: thread?.disposition === "interested" ? "rgba(240,160,40,0.12)" : "transparent",
                      }}>
                      {thread?.disposition === "interested" ? "★ INTERESTED" : "MARK INTERESTED"}
                    </button>
                    <button onClick={() => closeConvo("booked")} className="btn btn-ghost"
                      style={{ fontSize: 10, borderColor: "rgba(20,200,130,0.35)", color: "#14c882" }}>
                      MARK BOOKED
                    </button>
                    <button onClick={() => closeConvo("not_interested")} className="btn btn-ghost"
                      style={{ fontSize: 10, borderColor: "rgba(220,60,60,0.35)", color: "#dc3c3c" }}>
                      NOT INTERESTED
                    </button>
                  </>
                )}
                <button
                  onClick={deleteConvo}
                  disabled={deleting}
                  style={{
                    padding: "6px 12px", borderRadius: 8, border: "1px solid rgba(220,60,60,0.25)",
                    background: "rgba(220,60,60,0.06)", color: "#dc3c3c",
                    fontFamily: "'Share Tech Mono', monospace", fontSize: 9,
                    cursor: "pointer", letterSpacing: "0.06em",
                    opacity: deleting ? 0.5 : 1,
                  }}
                >
                  {deleting ? "…" : "DELETE"}
                </button>
              </div>
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
                      maxWidth: 420, padding: "9px 13px", borderRadius: isOut ? "8px 8px 2px 8px" : "8px 8px 8px 2px",
                      background: isOut ? "#1f3d70" : "#0d1626",
                      border: `0.5px solid ${isOut ? "#2857a0" : "#1a2540"}`,
                    }}>
                      {selected.channel === "email" && m.subject && (
                        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9,
                                      color: isOut ? "#7fa8dd" : "#6a8ab0", marginBottom: 4 }}>
                          {m.subject}
                        </div>
                      )}
                      <div style={{ fontSize: 13, color: isOut ? "#c8dcff" : "#8aaad0", lineHeight: 1.4, whiteSpace: "pre-wrap" }}>
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
              <div style={{ position: "relative", padding: "12px 20px", borderTop: "0.5px solid #1a2540", flexShrink: 0 }}>
                {selected.channel === "email" && (
                  <input
                    className="dg-input"
                    type="text"
                    placeholder="Subject"
                    value={replySubject}
                    onChange={e => setReplySubject(e.target.value)}
                    style={{ width: "100%", fontSize: 12, marginBottom: 8, boxSizing: "border-box" }}
                  />
                )}
                <div style={{ display: "flex", gap: 8 }}>
                  {selected.channel === "sms" && (
                    <button onClick={openSequence} className="btn btn-ghost" style={{ fontSize: 10, alignSelf: "flex-end" }}>
                      SEQUENCE
                    </button>
                  )}
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

                {seqOpen && (
                  <div style={{
                    position: "absolute", bottom: "100%", left: 20, marginBottom: 8,
                    background: "#0d1830", border: "1px solid rgba(58,123,213,0.4)",
                    borderRadius: 12, padding: "10px 0", width: 320, maxHeight: 320, overflowY: "auto",
                    boxShadow: "0 8px 32px rgba(0,0,0,0.6)", zIndex: 500,
                  }}>
                    <div style={{
                      padding: "4px 16px 8px", fontFamily: "'Space Grotesk', sans-serif", fontSize: 12,
                      fontWeight: 600, color: "#f0f4ff", borderBottom: "0.5px solid #1a2540",
                    }}>
                      {seqTitle || "Sequence"}
                    </div>
                    {seqLoading && (
                      <div style={{ padding: "12px 16px", fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#1a2f52" }}>
                        LOADING...
                      </div>
                    )}
                    {seqError && (
                      <div style={{ padding: "12px 16px", fontSize: 12, color: "#dc3c3c" }}>{seqError}</div>
                    )}
                    {!seqLoading && !seqError && seqSteps.length === 0 && (
                      <div style={{ padding: "12px 16px", fontSize: 12, color: "#5a6f8f" }}>
                        No sequence steps filled in yet — add them in Business Resources → Outreach Templates → SMS Sequence.
                      </div>
                    )}
                    {seqSteps.map((s, i) => (
                      <button key={i} onClick={() => applyStep(s.text)}
                        style={{
                          display: "block", width: "100%", textAlign: "left",
                          padding: "10px 16px", background: "transparent", border: "none", cursor: "pointer",
                        }}
                        onMouseEnter={e => e.currentTarget.style.background = "#0a1020"}
                        onMouseLeave={e => e.currentTarget.style.background = "transparent"}
                      >
                        <div style={{ fontSize: 12, fontWeight: 600, color: "#c4d0e8" }}>{s.label}</div>
                        <div style={{
                          fontSize: 11, color: "#5a6f8f", marginTop: 2,
                          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                        }}>
                          {s.text}
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div style={{
                padding: "12px 20px", borderTop: "0.5px solid #1a2540",
                textAlign: "center", fontFamily: "'Share Tech Mono', monospace",
                fontSize: 10, letterSpacing: "0.18em",
                color: thread?.disposition === "not_interested" ? "#dc3c3c" : "#14c882",
              }}>
                {thread?.disposition === "not_interested"
                  ? "NOT INTERESTED · CONVERSATION CLOSED"
                  : "APPOINTMENT BOOKED · CONVERSATION CLOSED"}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
