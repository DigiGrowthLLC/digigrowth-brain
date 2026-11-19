import React, { useEffect, useState } from "react";
import { API } from "./api.js";
import ContactCard from "./ContactCard.jsx";

// Any prospect's name anywhere in the OS opens their contact card (Dylan,
// 2026-11-19). <ContactLink id|phone|email clientId> wraps the name;
// <ContactCardHost /> is mounted once in App.jsx and shows the card.
// When only a phone/email is known (a booking, a voice call, a DM) it's
// resolved through GET /api/contact-cards/resolve.

const EVENT = "dg:open-contact";

export function openContactCard(target) {
  window.dispatchEvent(new CustomEvent(EVENT, { detail: target }));
}

export default function ContactLink({ id, phone, email, clientId, children, style }) {
  if (!id && !phone && !email) return <>{children}</>;
  const open = (e) => { e.stopPropagation(); e.preventDefault(); openContactCard({ id, phone, email, clientId }); };
  return (
    <span role="button" tabIndex={0} title="Open contact card" onClick={open}
      onKeyDown={(e) => { if (e.key === "Enter") open(e); }}
      style={{ cursor: "pointer", textDecoration: "underline", textDecorationColor: "rgba(106,176,255,0.35)", textUnderlineOffset: 3, ...style }}>
      {children}
    </span>
  );
}

export function ContactCardHost() {
  const [target, setTarget] = useState(null);
  const [resolved, setResolved] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    const onOpen = (e) => { setErr(""); setResolved(null); setTarget(e.detail || null); };
    window.addEventListener(EVENT, onOpen);
    return () => window.removeEventListener(EVENT, onOpen);
  }, []);

  useEffect(() => {
    if (!target) return;
    if (target.id) { setResolved(target.id); return; }
    const q = new URLSearchParams();
    if (target.phone) q.set("phone", target.phone);
    if (target.email) q.set("email", target.email);
    if (target.clientId) q.set("client_id", target.clientId);
    fetch(API(`/contact-cards/resolve?${q}`))
      .then(async (r) => { if (!r.ok) throw new Error("No contact record for this person yet."); return r.json(); })
      .then((d) => setResolved(d.id))
      .catch((e) => setErr(e.message));
  }, [target]);

  if (!target) return null;
  const close = () => { setTarget(null); setResolved(null); setErr(""); };
  if (!resolved) {
    return (
      <div onClick={close} style={{ position: "fixed", inset: 0, zIndex: 1000, background: "rgba(0,0,0,0.55)", display: "grid", placeItems: "center" }}>
        <div className="glass-card" style={{ padding: "16px 20px", fontSize: 13, color: err ? "#f0c078" : "#8aaad0" }}>{err || "Opening contact card…"}</div>
      </div>
    );
  }
  return <ContactCard key={resolved} contactId={resolved} phone={target.phone} onClose={close} />;
}
