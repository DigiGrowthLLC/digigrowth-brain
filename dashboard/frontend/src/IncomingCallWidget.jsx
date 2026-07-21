import React, { useState, useEffect, useRef } from "react";
import { API } from "./api.js";

// Always-mounted (see App.jsx — rendered outside the per-tab panel switch so
// it survives every tab change). Keeps a Twilio.Device registered globally,
// independent of the Dialer panel's own session-scoped Device, so an inbound
// callback rings through no matter which tab Dylan has open.
export default function IncomingCallWidget() {
  const [incoming, setIncoming] = useState(null); // CallInvite, awaiting answer/decline
  const [activeCall, setActiveCall] = useState(null); // live Call, once answered
  const [callInfo, setCallInfo] = useState(null); // { name, business, phone }
  const deviceRef = useRef(null);

  useEffect(() => {
    let cancelled = false;

    const fetchToken = async () => {
      const r = await fetch(API("/dialer/token"));
      const d = await r.json();
      if (!r.ok || d.detail || d.error) throw new Error(d.detail || d.error || r.status);
      return d.token;
    };

    const init = async () => {
      if (!window.Twilio?.Device) {
        // SDK script tag hasn't finished loading yet — retry shortly.
        setTimeout(() => { if (!cancelled) init(); }, 1000);
        return;
      }
      try {
        const token = await fetchToken();
        if (cancelled) return;

        const device = new window.Twilio.Device(token, { logLevel: "warn" });
        deviceRef.current = device;

        device.on("error", (e) => {
          console.warn("IncomingCallWidget device error:", e);
        });

        device.on("tokenWillExpire", async () => {
          try {
            const fresh = await fetchToken();
            device.updateToken(fresh);
          } catch (e) {
            console.warn("IncomingCallWidget token refresh failed:", e);
          }
        });

        device.on("incoming", (callInvite) => {
          const params = callInvite.customParameters || new Map();
          setCallInfo({
            name: params.get("name") || "",
            business: params.get("business") || "",
            phone: params.get("phone") || "",
          });
          setIncoming(callInvite);

          if (window.Notification && Notification.permission === "granted") {
            const label = params.get("name") || params.get("business") || params.get("phone") || "Unknown caller";
            new Notification("Incoming call", { body: label });
          }
        });

        await device.register();
      } catch (e) {
        console.warn("IncomingCallWidget init failed:", e);
      }
    };

    if (window.Notification && Notification.permission === "default") {
      Notification.requestPermission().catch(() => {});
    }

    init();

    return () => {
      cancelled = true;
      try { deviceRef.current?.destroy(); } catch {}
    };
  }, []);

  const answer = () => {
    if (!incoming) return;
    const call = incoming.accept();
    setActiveCall(call);
    setIncoming(null);
    call.on("disconnect", () => { setActiveCall(null); setCallInfo(null); });
    call.on("error", () => { setActiveCall(null); setCallInfo(null); });
  };

  const decline = () => {
    incoming?.reject();
    setIncoming(null);
    setCallInfo(null);
  };

  const hangUp = () => {
    try { activeCall?.disconnect(); } catch {}
    setActiveCall(null);
    setCallInfo(null);
  };

  if (!incoming && !activeCall) return null;

  const label = callInfo?.name || callInfo?.business || callInfo?.phone || "Unknown caller";

  return (
    <div style={{
      position: "fixed", top: 24, right: 24, zIndex: 2000,
      background: "#0d1830", border: `1px solid ${incoming ? "rgba(20,200,130,0.4)" : "rgba(58,123,213,0.4)"}`,
      borderRadius: 12, padding: "16px 18px", width: 260,
      boxShadow: "0 8px 32px rgba(0,0,0,0.6)",
    }}>
      <div style={{ textAlign: "center" }}>
        <div style={{ fontSize: 22, marginBottom: 4 }}>{incoming ? "📞" : "🔊"}</div>
        <div style={{ fontSize: 13, fontWeight: 700, color: "#f0f4ff", marginBottom: 2 }}>
          {incoming ? "Incoming Call" : "On Call"}
        </div>
        <div style={{
          fontFamily: "'Share Tech Mono', monospace", fontSize: 11, color: "#8aaad0", marginBottom: 4,
          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
        }}>
          {label}
        </div>
        {callInfo?.business && callInfo?.name && (
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80", marginBottom: 10 }}>
            {callInfo.business}
          </div>
        )}
        {incoming ? (
          <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
            <button onClick={answer} style={{
              flex: 1, padding: "8px 0", borderRadius: 6, fontSize: 12, fontWeight: 700,
              background: "rgba(20,200,130,0.2)", color: "#14c882",
              border: "1px solid rgba(20,200,130,0.4)", cursor: "pointer",
            }}>Answer</button>
            <button onClick={decline} style={{
              flex: 1, padding: "8px 0", borderRadius: 6, fontSize: 12, fontWeight: 700,
              background: "rgba(220,60,60,0.15)", color: "#dc3c3c",
              border: "1px solid rgba(220,60,60,0.35)", cursor: "pointer",
            }}>Decline</button>
          </div>
        ) : (
          <button onClick={hangUp} style={{
            width: "100%", padding: "8px 0", borderRadius: 6, fontSize: 12, fontWeight: 700,
            background: "rgba(220,60,60,0.15)", color: "#dc3c3c",
            border: "1px solid rgba(220,60,60,0.35)", cursor: "pointer", marginTop: 10,
          }}>End Call</button>
        )}
      </div>
    </div>
  );
}
