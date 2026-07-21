import { useState, useEffect, useRef, useCallback } from "react";
import { API } from "./api.js";

// Owns a Twilio.Device registered for the whole OS session, independent of
// the Dialer panel's own session-scoped Device, so an inbound callback rings
// through no matter which tab is open. Mounted once at the App level.
export default function useIncomingCall() {
  // @twilio/voice-sdk v2 has no separate CallInvite — the "incoming" event
  // hands over the actual Call object, ringing and awaiting accept()/reject().
  const [incoming, setIncoming] = useState(null); // ringing Call, awaiting answer/decline
  const [activeCall, setActiveCall] = useState(null); // same Call, once answered
  const [callInfo, setCallInfo] = useState(null); // { name, business, phone, contactId }
  const deviceRef = useRef(null);
  const incomingRef = useRef(null);
  useEffect(() => { incomingRef.current = incoming; }, [incoming]);

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

        device.on("incoming", (call) => {
          try {
            const params = call.customParameters instanceof Map ? call.customParameters : new Map();
            const info = {
              name: params.get("name") || "",
              business: params.get("business") || "",
              phone: params.get("phone") || "",
              contactId: params.get("contactId") || "",
            };
            setCallInfo(info);
            setIncoming(call);

            if (window.Notification && Notification.permission === "granted") {
              const label = info.name || info.business || info.phone || "Unknown caller";
              new Notification("Incoming call", { body: label });
            }
          } catch (e) {
            console.warn("Failed to handle incoming call event:", e);
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
    // In @twilio/voice-sdk v2, the "incoming" event hands over the actual
    // Call object (there's no separate CallInvite) — accept() mutates it in
    // place and returns undefined, it does NOT hand back a new Call.
    const call = incomingRef.current;
    if (!call) return;
    setIncoming(null); // hide the popup immediately — accept() only ever fires once
    try {
      call.accept();
      setActiveCall(call);

      // callInfo (contact name/business/phone/contactId) stays set after the
      // call ends — CallScreen still needs it for the post-call disposition
      // and to keep the contact card linked. Only clearing activeCall here.
      const end = () => setActiveCall(null);
      call.on("disconnect", end);
      call.on("error", (e) => { console.warn("Incoming call error:", e); end(); });

      // Belt-and-suspenders: also poll the call's actual status. If Twilio's
      // "disconnect" event doesn't reliably reach this leg when the OTHER
      // party hangs up, this still catches it within a couple seconds
      // instead of the call screen showing "on call" forever.
      const statusPoll = setInterval(() => {
        if (call.status() === "closed") {
          clearInterval(statusPoll);
          end();
        }
      }, 2000);
      call.on("disconnect", () => clearInterval(statusPoll));
    } catch (e) {
      console.warn("Failed to accept incoming call:", e);
    }
  }, []);

  const decline = useCallback(() => {
    const call = incomingRef.current;
    setIncoming(null);
    setCallInfo(null);
    try { call?.reject(); } catch (e) { console.warn("Failed to reject incoming call:", e); }
  }, []);

  const hangUp = useCallback(() => {
    setActiveCall((call) => { try { call?.disconnect(); } catch {} return null; });
  }, []);

  // callInfo is cleared explicitly once the rep is actually done with this
  // call (disposition logged, or CallScreen otherwise dismissed).
  const clearCallInfo = useCallback(() => setCallInfo(null), []);

  return { incoming, activeCall, callInfo, answer, decline, hangUp, clearCallInfo };
}
