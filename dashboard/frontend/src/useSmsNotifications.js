import { useEffect, useRef } from "react";
import { API } from "./api.js";

const SEEN_KEY = "dg_sms_last_seen"; // { [phone]: updated_at ISO string }

// Polls the SMS inbox for the whole OS session (mounted once at the App
// level, like useIncomingCall) and fires a native OS notification for any
// inbound message that lands while the tab is open — even if the user is
// on a different panel. Seen state persists in localStorage so a reload
// doesn't re-notify for messages already surfaced.
export default function useSmsNotifications(onOpenThread) {
  const onOpenThreadRef = useRef(onOpenThread);
  useEffect(() => { onOpenThreadRef.current = onOpenThread; }, [onOpenThread]);

  useEffect(() => {
    if (window.Notification && Notification.permission === "default") {
      Notification.requestPermission().catch(() => {});
    }

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

          // Don't fire a burst of notifications for pre-existing threads on
          // first load — just record the baseline and start watching.
          if (!firstPoll && window.Notification && Notification.permission === "granted") {
            const label = c.owner || c.business || c.phone;
            const notif = new Notification(`New text — ${label}`, {
              body: c.last_message || "",
              tag: `sms-${c.phone}`,
            });
            notif.onclick = () => {
              window.focus();
              onOpenThreadRef.current?.(c.phone);
              notif.close();
            };
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
