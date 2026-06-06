import React, { useState, useEffect, useRef, useCallback } from "react";

const API = (path) => `/api${path}`;

function fmt(ts) {
  if (!ts) return "";
  const d = new Date(ts);
  return d.toLocaleString("en-US", {
    month: "short", day: "numeric",
    hour: "numeric", minute: "2-digit",
  });
}

function StatusBadge({ status }) {
  const cls = status === "closed"
    ? "bg-green-900 text-green-300"
    : "bg-yellow-900 text-yellow-300";
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${cls}`}>
      {status === "closed" ? "Booked" : "Active"}
    </span>
  );
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
      const res = await fetch(API("/sms/conversations"));
      if (res.ok) setConvos(await res.json());
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => {
    loadConvos();
    const id = setInterval(loadConvos, 15000);
    return () => clearInterval(id);
  }, [loadConvos]);

  const openThread = async (phone) => {
    setSelected(phone);
    setThread(null);
    try {
      const res = await fetch(API(`/sms/conversations/${encodeURIComponent(phone)}`));
      if (res.ok) setThread(await res.json());
    } catch {}
  };

  useEffect(() => {
    if (!selected) return;
    const id = setInterval(() => openThread(selected), 8000);
    return () => clearInterval(id);
  }, [selected]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [thread?.messages]);

  const sendReply = async () => {
    if (!replyText.trim() || !selected) return;
    setSending(true);
    try {
      await fetch(API("/sms/send"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone: selected, body: replyText.trim() }),
      });
      setReplyText("");
      await openThread(selected);
      await loadConvos();
    } catch {}
    setSending(false);
  };

  const closeConvo = async () => {
    if (!selected) return;
    await fetch(API(`/sms/conversations/${encodeURIComponent(selected)}/close`), {
      method: "POST",
    });
    await openThread(selected);
    await loadConvos();
  };

  const handleKey = (e) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) sendReply();
  };

  return (
    <div className="flex h-full">
      {/* Thread list */}
      <aside className="w-72 border-r border-gray-800 flex flex-col shrink-0">
        <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
          <span className="text-sm font-semibold text-white">SMS Inbox</span>
          <span className="text-xs text-gray-500">{convos.length} threads</span>
        </div>

        <div className="flex-1 overflow-y-auto">
          {loading && (
            <div className="p-4 text-sm text-gray-500">Loading…</div>
          )}
          {!loading && convos.length === 0 && (
            <div className="p-4 text-sm text-gray-600">No conversations yet.</div>
          )}
          {convos.map((c) => (
            <button
              key={c.phone}
              onClick={() => openThread(c.phone)}
              className={`w-full text-left px-4 py-3 border-b border-gray-800 transition-colors hover:bg-gray-800 ${
                selected === c.phone ? "bg-gray-800" : ""
              }`}
            >
              <div className="flex items-center justify-between mb-0.5">
                <span className="text-sm font-medium text-white truncate">
                  {c.business || c.owner || c.phone}
                </span>
                <StatusBadge status={c.status} />
              </div>
              <div className="text-xs text-gray-500 truncate">{c.phone}</div>
              {c.last_message && (
                <div className="text-xs text-gray-600 truncate mt-1">{c.last_message}</div>
              )}
            </button>
          ))}
        </div>
      </aside>

      {/* Thread view */}
      <div className="flex-1 flex flex-col min-w-0">
        {!selected && (
          <div className="flex-1 flex items-center justify-center text-gray-600 text-sm">
            Select a conversation
          </div>
        )}

        {selected && (
          <>
            {/* Header */}
            <div className="px-5 py-3 border-b border-gray-800 flex items-center justify-between shrink-0">
              <div>
                <div className="text-sm font-semibold text-white">
                  {thread?.business || thread?.owner || selected}
                </div>
                <div className="text-xs text-gray-500 flex items-center gap-2 mt-0.5">
                  {selected}
                  {thread?.grade && (
                    <span className="text-indigo-400">Grade {thread.grade}</span>
                  )}
                </div>
              </div>
              {thread?.status !== "closed" && (
                <button
                  onClick={closeConvo}
                  className="text-xs px-3 py-1.5 rounded bg-green-700 hover:bg-green-600 text-white transition-colors"
                >
                  Mark Booked
                </button>
              )}
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-5 py-4 space-y-3">
              {!thread && (
                <div className="text-sm text-gray-500">Loading…</div>
              )}
              {thread?.messages?.map((m, i) => {
                const isOut = m.direction === "outbound";
                return (
                  <div key={i} className={`flex ${isOut ? "justify-end" : "justify-start"}`}>
                    <div
                      className={`max-w-xs px-3 py-2 rounded-2xl text-sm leading-snug ${
                        isOut
                          ? "bg-indigo-600 text-white rounded-br-sm"
                          : "bg-gray-800 text-gray-100 rounded-bl-sm"
                      }`}
                    >
                      <div>{m.body}</div>
                      <div className={`text-xs mt-1 ${isOut ? "text-indigo-300" : "text-gray-500"}`}>
                        {fmt(m.sent_at)}
                      </div>
                    </div>
                  </div>
                );
              })}
              <div ref={bottomRef} />
            </div>

            {/* Reply box */}
            {thread?.status !== "closed" ? (
              <div className="px-5 py-3 border-t border-gray-800 shrink-0">
                <div className="flex gap-2">
                  <textarea
                    value={replyText}
                    onChange={(e) => setReplyText(e.target.value)}
                    onKeyDown={handleKey}
                    placeholder="Type a reply… (⌘↵ to send)"
                    rows={2}
                    className="flex-1 bg-gray-800 text-sm text-gray-100 placeholder-gray-600 rounded-lg px-3 py-2 resize-none focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  />
                  <button
                    onClick={sendReply}
                    disabled={sending || !replyText.trim()}
                    className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium disabled:opacity-40 transition-colors self-end"
                  >
                    {sending ? "…" : "Send"}
                  </button>
                </div>
              </div>
            ) : (
              <div className="px-5 py-3 border-t border-gray-800 text-center text-xs text-green-500 shrink-0">
                Appointment booked — conversation closed
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
