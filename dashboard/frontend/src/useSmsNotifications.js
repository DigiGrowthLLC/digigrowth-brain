import { useEffect, useRef } from "react";
import { API } from "./api.js";

const SEEN_KEY = "dg_sms_last_seen"; // { [phone]: updated_at ISO string }

// Polls the SMS inbox for the whole OS session (mounted once at the App
// level, like useIncomingCall) and calls `onNewInbound` for any inbound
// message that lands while the dashboard is open — regardless of which nav
// tab is active. Seen state persists in localStorage so a reload doesn't
// re-fire for messages already surfaced.
export default function useSmsNotifications(onNewInbound) {
  const onNewInboundRef = useRef(onNewInbound);
  useEffect(() => { onNewInboundRef.current = onNewInbound; }, [onNewInbound]);

  useEffect(() => {
    let cancelled = false;
    let firstPoll = true;

    const loadSeen = () => {
      try { return JSON.parse(localStorage.getItem(SEEN_KEY)) || {}; }
      catch { return {}; }
    };
    const saveSeen = (seen) => {
      try { localStorage.setItem(SEEN_KEY, JSON.stringify(seen)); } catch {}
    };

    const poll = async () => {
      try {
        const r = await fetch(API("/sms/conversations"));
        if (!r.ok) return;
        const convos = await r.json();
        const seen = loadSeen();

        for (const c of convos) {
          if (c.last_direction !== "inbound" || !c.updated_at) continue;
          const prev = seen[c.phone];
          if (prev && new Date(prev) >= new Date(c.updated_at)) continue;

          // Don't fire a burst of toasts for pre-existing threads on first
          // load — just record the baseline and start watching from here.
          if (!firstPoll) {
            onNewInboundRef.current?.(c);
          }
          seen[c.phone] = c.updated_at;
        }

        saveSeen(seen);
      } catch {}
      firstPoll = false;
    };

    poll();
    const id = setInterval(() => { if (!cancelled) poll(); }, 15000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);
}
