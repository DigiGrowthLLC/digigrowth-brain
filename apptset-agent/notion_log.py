"""
Notion event queue for SMS agent.

Python side writes events to notion_queue.json (append-only).
The EA SMS skill flushes this file to the Notion Outreach page.
Keeps Python free of MCP dependencies.
"""

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

QUEUE_FILE = Path(__file__).parent / "notion_queue.json"
_lock      = threading.Lock()


def log_event(event_type, lead=None, extra=None):
    """
    Append an event to notion_queue.json.

    event_type: OUTBOUND_SENT | REPLY_RECEIVED | STAGE_ADVANCED |
                BOOKED | CLOSED_DEAD | FOLLOWUP_SENT
    lead: dict with owner, business, contact_id, phone
    extra: dict of additional fields (e.g. stage, follow_up_count)
    """
    entry = {
        "event":     event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if lead:
        entry["contact"]  = (lead.get("owner") or "").strip()
        entry["business"] = lead.get("business") or ""
        entry["phone"]    = lead.get("phone") or ""
    if extra:
        entry.update(extra)

    with _lock:
        existing = []
        if QUEUE_FILE.exists():
            try:
                existing = json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                existing = []
        existing.append(entry)
        QUEUE_FILE.write_text(json.dumps(existing, indent=2), encoding="utf-8")


def read_queue():
    """Return all queued events and clear the file."""
    with _lock:
        if not QUEUE_FILE.exists():
            return []
        try:
            events = json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            events = []
        QUEUE_FILE.write_text("[]", encoding="utf-8")
    return events
