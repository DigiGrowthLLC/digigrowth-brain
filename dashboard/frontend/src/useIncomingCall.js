import { useState, useEffect, useRef, useCallback } from "react";
import { API } from "./api.js";

// Owns a Twilio.Device registered for the whole OS session, independent of
// the Dialer panel's own session-scoped Device, so an inbound callback rings
// through no matter which tab is open. Mounted once at the App level.
export default function useIncomingCall() {
  const [incoming, setIncoming] = useState(null); // CallInvite, awaiting answer/decline
  const [activeCall, setActiveCall] = useState(null); // live Call, once answered
  const [callInfo, setCallInfo] = useState(null); // { name, business, phone, contactId }
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
        setTimeout(() => { if (!cancelled) init(); }, 1000);
        return;
      }
      try {
        const token = await fetchToken();
        if (cancelled) return;

        const device = new window.Twilio.Device(token, { logLevel: "warn" });
        deviceRef.current = device;

        device.on("error", (e) => console.warn("Incoming call device error:", e));

        device.on("tokenWillExpire", async () => {
          try {
            device.updateToken(await fetchToken());
          } catch (e) {
            console.warn("Incoming call token refresh failed:", e);
          }
        });

        device.on("incoming", (callInvite) => {
          const params = callInvite.customParameters || new Map();
          setCallInfo({
            name: params.get("name") || "",
            business: params.get("business") || "",
            phone: params.get("phone") || "",
            contactId: params.get("contactId") || "",
          });
          setIncoming(callInvite);

          if (window.Notification && Notification.permission === "granted") {
            const label = params.get("name") || params.get("business") || params.get("phone") || "Unknown caller";
            new Notification("Incoming call", { body: label });
          }
        });

        await device.register();
      } catch (e) {
        console.warn("Incoming call init failed:", e);
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

  const answer = useCallback(() => {
    setIncoming((inv) => {
      if (!inv) return inv;
      const call = inv.accept();
      setActiveCall(call);
      call.on("disconnect", () => { setActiveCall(null); setCallInfo(null); });
      call.on("error",      () => { setActiveCall(null); setCallInfo(null); });
      return null;
    });
  }, []);

  const decline = useCallback(() => {
    setIncoming((inv) => { inv?.reject(); return null; });
    setCallInfo(null);
  }, []);

  const hangUp = useCallback(() => {
    setActiveCall((call) => { try { call?.disconnect(); } catch {} return null; });
    setCallInfo(null);
  }, []);

  return { incoming, activeCall, callInfo, answer, decline, hangUp };
}
