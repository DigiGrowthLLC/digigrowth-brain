import React, { useState, useEffect, useCallback } from "react";
import { API } from "../api.js";
import CampaignModal from "../CampaignModal.jsx";

// Shows the currently active campaign for one outreach channel, a
// "+ New Campaign" action, and a "Switch" dropdown to reactivate a past
// campaign (campaigns.py's /campaigns/{id}/activate — same endpoint whether
// the campaign is brand new or being resumed). Used in DialerPanel (calling)
// and twice in InboxPanel (sms/email).
export default function CampaignBadge({ channel, label }) {
  const [active, setActive]   = useState(null);
  const [all, setAll]         = useState([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [switchOpen, setSwitchOpen] = useState(false);

  const load = useCallback(() => {
    fetch(API(`/campaigns/active?channel=${channel}`)).then(r => r.ok ? r.json() : null).then(setActive);
    fetch(API(`/campaigns?channel=${channel}`)).then(r => r.ok ? r.json() : []).then(setAll);
  }, [channel]);

  useEffect(() => { load(); }, [load]);

  async function reactivate(id) {
    await fetch(API(`/campaigns/${id}/activate`), { method: "POST" });
    setSwitchOpen(false);
    load();
  }

  const inactive = all.filter(c => !c.is_active);

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: "#3a5a80", letterSpacing: "0.08em" }}>
        {label ? `${label}: ` : ""}{active ? active.name : "No active campaign"}
      </span>
      <button className="btn btn-secondary" style={{ fontSize: 10, padding: "4px 10px" }} onClick={() => setModalOpen(true)}>
        + New Campaign
      </button>
      {inactive.length > 0 && (
        <div style={{ position: "relative" }}>
          <button className="btn btn-secondary" style={{ fontSize: 10, padding: "4px 10px" }} onClick={() => setSwitchOpen(o => !o)}>
            Switch ▾
          </button>
          {switchOpen && (
            <div style={{
              position: "absolute", top: "calc(100% + 4px)", right: 0, zIndex: 20,
              background: "#0d1626", border: "1px solid #1a2540", borderRadius: 8,
              padding: "6px 0", minWidth: 180, boxShadow: "0 8px 24px rgba(0,0,0,0.4)",
            }}>
              {inactive.map(c => (
                <button
                  key={c.id}
                  onClick={() => reactivate(c.id)}
                  style={{
                    display: "block", width: "100%", textAlign: "left", background: "none", border: "none",
                    padding: "6px 12px", cursor: "pointer", fontSize: 11, color: "#c4d0e8",
                    fontFamily: "'Share Tech Mono', monospace",
                  }}
                >
                  Reactivate: {c.name}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
      <CampaignModal
        open={modalOpen}
        channel={channel}
        activeCampaignName={active?.name}
        onClose={() => setModalOpen(false)}
        onCreated={load}
      />
    </div>
  );
}
