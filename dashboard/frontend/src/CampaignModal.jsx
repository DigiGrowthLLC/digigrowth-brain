import React, { useState } from "react";
import { API } from "./api.js";

// "New Campaign" modal — names a campaign for one outreach channel and
// activates it, which ends whatever campaign was previously active for
// that channel (see dashboard/backend/routers/campaigns.py). Used from
// DialerPanel (calling) and InboxPanel (sms/email) via CampaignBadge.
export default function CampaignModal({ open, channel, activeCampaignName, onClose, onCreated }) {
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  if (!open) return null;

  async function submit() {
    const trimmed = name.trim();
    if (!trimmed) return;
    setSaving(true);
    setErr("");
    try {
      const res = await fetch(API("/campaigns"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ channel, name: trimmed }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        setErr(d.detail || "Failed to create campaign.");
        setSaving(false);
        return;
      }
      const campaign = await res.json();
      setName("");
      onCreated?.(campaign);
      onClose?.();
    } catch {
      setErr("Failed to create campaign.");
    }
    setSaving(false);
  }

  return (
    <div onClick={(e) => e.target === e.currentTarget && onClose?.()} style={{
      position: "fixed", inset: 0, background: "rgba(4,8,16,0.85)",
      display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000, padding: 24,
    }}>
      <div style={{
        background: "#0a1020", border: "0.5px solid #1a2540", borderRadius: 8,
        width: 420, padding: "24px 28px", display: "flex", flexDirection: "column", gap: 14,
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 16, fontWeight: 700, color: "#f0f4ff" }}>
            New Campaign
          </div>
          <button onClick={onClose} style={{ background: "none", border: "none", color: "#3a5a80", cursor: "pointer", fontSize: 14 }}>✕</button>
        </div>

        {activeCampaignName && (
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#f0a028", letterSpacing: "0.05em" }}>
            This ends the current campaign: {activeCampaignName}
          </div>
        )}

        <input
          autoFocus
          className="dg-input"
          placeholder="Campaign name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
        />

        {err && <div style={{ fontSize: 11, color: "#dc3c3c" }}>{err}</div>}

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={saving || !name.trim()} onClick={submit}>
            {saving ? "Creating…" : "Create"}
          </button>
        </div>
      </div>
    </div>
  );
}
