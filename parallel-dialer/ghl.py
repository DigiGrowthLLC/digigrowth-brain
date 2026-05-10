import os
import requests
from dotenv import load_dotenv

load_dotenv()

GHL_API_KEY = os.environ.get("GHL_API_KEY", "")

DISPOSITION_TAGS = {
    "Appointment Booked": "appointment-booked",
    "Follow Up":          "follow-up",
    "Not Interested":     "not-interested",
    "Send Info":          "send-info",
    "SMS Handoff":        "sms-handoff",
}


def _headers():
    return {
        "Authorization": f"Bearer {GHL_API_KEY}",
        "Content-Type":  "application/json",
        "Version":       "2021-04-15",
    }


def _base(config):
    return config.get("ghl_base_url", "https://rest.gohighlevel.com/v1")


# ════════════════════════════════════════════════════════════════════════════
#  CONTACT LOOKUP / CREATE
# ════════════════════════════════════════════════════════════════════════════

def get_contact_by_phone(config, phone):
    """Look up a GHL contact by phone number. Returns contact dict or None."""
    url    = f"{_base(config)}/contacts/search"
    params = {"phone": phone, "locationId": config["ghl_location_id"]}
    try:
        r = requests.get(url, headers=_headers(), params=params, timeout=10)
        r.raise_for_status()
        contacts = r.json().get("contacts", [])
        return contacts[0] if contacts else None
    except Exception as e:
        print(f"  ⚠️  GHL contact lookup failed: {e}")
        return None


def create_contact(config, lead):
    """Create a new GHL contact from a lead dict. Returns contact ID or None."""
    url  = f"{_base(config)}/contacts/"
    body = {
        "locationId":  config["ghl_location_id"],
        "firstName":   lead.get("owner", "").split()[0] if lead.get("owner") else "",
        "lastName":    " ".join(lead.get("owner", "").split()[1:]) if lead.get("owner") else "",
        "companyName": lead.get("business", ""),
        "phone":       lead.get("phone", ""),
        "tags":        ["dialer-lead"],
    }
    try:
        r = requests.post(url, headers=_headers(), json=body, timeout=10)
        r.raise_for_status()
        return r.json().get("contact", {}).get("id")
    except Exception as e:
        print(f"  ⚠️  GHL contact create failed: {e}")
        return None


def get_or_create_contact(config, lead):
    """Get existing GHL contact or create one. Returns contact ID or None."""
    contact = get_contact_by_phone(config, lead["phone"])
    if contact:
        return contact["id"]
    return create_contact(config, lead)


# ════════════════════════════════════════════════════════════════════════════
#  TAGS
# ════════════════════════════════════════════════════════════════════════════

def tag_contact(config, contact_id, disposition):
    """Add a disposition tag to a GHL contact."""
    tag = DISPOSITION_TAGS.get(disposition)
    if not tag:
        return
    url  = f"{_base(config)}/contacts/{contact_id}/tags"
    body = {"tags": [tag]}
    try:
        r = requests.post(url, headers=_headers(), json=body, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print(f"  ⚠️  GHL tag failed: {e}")


# ════════════════════════════════════════════════════════════════════════════
#  WORKFLOWS
# ════════════════════════════════════════════════════════════════════════════

def trigger_workflow(config, contact_id, workflow_key):
    """Fire a GHL workflow by key (maps to workflow ID in config)."""
    workflow_id = config.get("ghl_workflows", {}).get(workflow_key)
    if not workflow_id:
        print(f"  ⚠️  No workflow ID configured for '{workflow_key}' — skipping")
        return
    url  = f"{_base(config)}/contacts/{contact_id}/workflow/{workflow_id}"
    body = {"eventStartTime": _now_iso()}
    try:
        r = requests.post(url, headers=_headers(), json=body, timeout=10)
        r.raise_for_status()
        print(f"  ✅ GHL workflow '{workflow_key}' triggered for {contact_id}")
    except Exception as e:
        print(f"  ⚠️  GHL workflow trigger failed: {e}")


# ════════════════════════════════════════════════════════════════════════════
#  DISPOSITION ROUTER
# ════════════════════════════════════════════════════════════════════════════

def handle_disposition(config, lead, disposition):
    """
    Route post-call disposition to the correct GHL actions.

    Appointment Booked → tag + (booking handled separately via booking.py)
    Follow Up          → tag + trigger follow_up workflow
    Not Interested     → tag + trigger not_interested workflow
    Send Info          → tag + trigger send_info workflow
    No Answer / SMS Handoff → handled by run.py after 3 strikes
    """
    contact_id = get_or_create_contact(config, lead)
    if not contact_id:
        print(f"  ❌ Could not find/create GHL contact for {lead['phone']}")
        return

    tag_contact(config, contact_id, disposition)

    workflow_map = {
        "Follow Up":    "follow_up",
        "Not Interested": "not_interested",
        "Send Info":    "send_info",
        "SMS Handoff":  "sms_handoff",
    }
    workflow_key = workflow_map.get(disposition)
    if workflow_key:
        trigger_workflow(config, contact_id, workflow_key)

    return contact_id


def trigger_sms_handoff(config, lead):
    """Trigger SMS appointment-setting workflow after 3 unanswered calls."""
    print(f"  📱 Handing off {lead['business']} ({lead['phone']}) to SMS agent...")
    return handle_disposition(config, lead, "SMS Handoff")


# ════════════════════════════════════════════════════════════════════════════
#  NOTES
# ════════════════════════════════════════════════════════════════════════════

def add_note(config, contact_id, note_text):
    """Add a call note to a GHL contact."""
    url  = f"{_base(config)}/contacts/{contact_id}/notes"
    body = {"body": note_text, "userId": ""}
    try:
        r = requests.post(url, headers=_headers(), json=body, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print(f"  ⚠️  GHL note failed: {e}")


def _now_iso():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
