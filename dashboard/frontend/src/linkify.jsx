import React from "react";

// Shared by TodoPanel and DashboardPanel's To-Do widget. Turns bare URLs in
// freeform notes into clickable links. Links back into this OS (e.g. the
// "?panel=inbox&contact=..." links the SMS setter puts on prospect to-dos)
// open in the same tab with a readable label instead of the raw URL; any
// other link opens in a new tab.

// Any link carrying ?panel= is treated as a link into this app, and is
// re-pointed at whatever address the OS is open on right now — the backend
// can't always know which domain Dylan uses (Railway's own vs. a custom one).
function isAppLink(url) {
  try {
    const u = new URL(url);
    return u.pathname === "/" && u.searchParams.has("panel");
  } catch {
    return false;
  }
}

function sameOrigin(url) {
  const u = new URL(url);
  return `${window.location.origin}/${u.search}`;
}

export function linkify(text) {
  const parts = (text || "").split(/(https?:\/\/[^\s]+)/g);
  return parts.map((part, i) => {
    if (!/^https?:\/\//.test(part)) return <React.Fragment key={i}>{part}</React.Fragment>;
    if (isAppLink(part)) {
      const panel = new URL(part).searchParams.get("panel");
      return (
        <a key={i} href={sameOrigin(part)} onClick={e => e.stopPropagation()}
          style={{ color: "#3a7bd5", fontWeight: 600 }}>
          {panel === "inbox" ? "Open in Inbox →" : `Open ${panel} →`}
        </a>
      );
    }
    return (
      <a key={i} href={part} target="_blank" rel="noreferrer" onClick={e => e.stopPropagation()}
        style={{ color: "#3a7bd5", wordBreak: "break-all" }}>{part}</a>
    );
  });
}

// The first in-app Inbox link in a to-do's notes, if any — lets a to-do row
// show a one-click INBOX button without expanding the notes first.
export function inboxLinkFrom(text) {
  const match = (text || "").match(/https?:\/\/[^\s]+/g) || [];
  const link = match.find(u => isAppLink(u) && new URL(u).searchParams.get("panel") === "inbox");
  return link ? sameOrigin(link) : null;
}

export function InboxLinkButton({ href }) {
  if (!href) return null;
  return (
    <a href={href} onClick={e => e.stopPropagation()} title="Open this prospect's thread in the Inbox"
      style={{
        flexShrink: 0, padding: "1px 6px", borderRadius: 4, textDecoration: "none",
        border: "1px solid rgba(58,123,213,0.35)", color: "#3a7bd5",
        fontFamily: "'Share Tech Mono', monospace", fontSize: 9, letterSpacing: "0.06em",
      }}>
      INBOX →
    </a>
  );
}
