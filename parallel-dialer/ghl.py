import os
import requests
from dotenv import load_dotenv

load_dotenv()

GHL_BASE = "https://services.leadconnectorhq.com"

# ── Custom field IDs (from GET /locations/{id}/customFields) ─────────────────
CF_COLD_CALL_RESULT     = "9gUOgOam3DuuNsTqw5Si"   # MULTIPLE_OPTIONS
CF_NUMBER_OF_COLD_CALLS = "YBAjRCgeXi4IDwWHZkWc"   # MULTIPLE_OPTIONS: "Cold Call 1/2/3"
CF_LEAD_GRADE           = "53vuuYEBnWTFA2bieX12"    # TEXT
CF_CUSTOM_OPENER        = "Mg7mf31yey0FoCoEYoPJ"    # LARGE_TEXT

# Maps attempt number → MULTIPLE_OPTIONS value stored in GHL
ATTEMPT_VALUE = {1: "Cold Call 1", 2: "Cold Call 2", 3: "Cold Call 3"}
ATTEMPT_PARSE = {v: k for k, v in ATTEMPT_VALUE.items()}

# Maps our disposition labels → GHL cold_call_result option values
COLD_CALL_RESULT_MAP = {
    "Follow Up":          "Follow Up",
    "Not Interested":     "Not Interested",
    "No Answer":          "No Answer",
    "Appointment Booked": "Appointment Booked",
    "Send Info":          "Send Info",
    "SMS Handoff":        "No Answer",
}


def _headers():
    token = os.environ.get("GHL_PRIVATE_TOKEN") or os.environ.get("GHL_API_KEY", "")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
        "Version":       "2021-07-28",
    }


# ════════════════════════════════════════════════════════════════════════════
#  CONTACT LOOKUP / CREATE
# ════════════════════════════════════════════════════════════════════════════

def get_contact_by_phone(config, phone):
    """Look up a GHL contact by phone number. Returns contact dict or None."""
    url    = f"{GHL_BASE}/contacts/"
    params = {"query": phone, "locationId": config.get("ghl_location_id", "")}
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
    name_parts = lead.get("owner", "").split()
    body = {
        "locationId":  config.get("ghl_location_id", ""),
        "firstName":   name_parts[0] if name_parts else "",
        "lastName":    " ".join(name_parts[1:]) if len(name_parts) > 1 else "",
        "companyName": lead.get("business", ""),
        "phone":       lead.get("phone", ""),
        "email":       lead.get("email", ""),
        "tags":        ["dialer-lead"],
    }
    try:
        r = requests.post(f"{GHL_BASE}/contacts/", headers=_headers(), json=body, timeout=10)
        r.raise_for_status()
        return r.json().get("contact", {}).get("id")
    except Exception as e:
        print(f"  ⚠️  GHL contact create failed: {e}")
        return None


def get_or_create_contact(config, lead):
    """Get existing GHL contact or create one. Returns contact ID or None."""
    contact = get_contact_by_phone(config, lead.get("phone", ""))
    if contact:
        return contact.get("id")
    return create_contact(config, lead)


# ════════════════════════════════════════════════════════════════════════════
#  CUSTOM FIELD HELPERS
# ════════════════════════════════════════════════════════════════════════════

def _cf(contact, field_id):
    """
    Read a custom field from a contact by field ID.
    Handles both scalar and MULTIPLE_OPTIONS (list) values.
    """
    for field in contact.get("customFields", []):
        if field.get("id") == field_id:
            val = field.get("value", "")
            if isinstance(val, list):
                return val[0] if val else ""
            return val or ""
    return ""


def _update_custom_fields(config, contact_id, field_updates: dict):
    """
    Update custom fields on a GHL contact.
    field_updates = {CF_ID: value, ...}
    """
    body = {
        "customFields": [
            {"id": fid, "field_value": str(val)}
            for fid, val in field_updates.items()
        ]
    }
    try:
        r = requests.put(
            f"{GHL_BASE}/contacts/{contact_id}",
            headers=_headers(), json=body, timeout=10
        )
        r.raise_for_status()
    except Exception as e:
        print(f"  ⚠️  GHL custom field update failed: {e}")


# ════════════════════════════════════════════════════════════════════════════
#  CALL ATTEMPT TRACKING
# ════════════════════════════════════════════════════════════════════════════

def get_attempt_count(config, phone):
    """
    Return number of cold calls from the GHL number_of_cold_calls field.
    Field stores MULTIPLE_OPTIONS value like "Cold Call 1" → returns 1.
    """
    contact = get_contact_by_phone(config, phone)
    if not contact:
        return 0
    val = _cf(contact, CF_NUMBER_OF_COLD_CALLS)
    return ATTEMPT_PARSE.get(val, 0)


def record_call_attempt(config, contact_id, attempt_number):
    """Update number_of_cold_calls field after a call attempt."""
    val = ATTEMPT_VALUE.get(attempt_number, f"Cold Call {attempt_number}")
    _update_custom_fields(config, contact_id, {CF_NUMBER_OF_COLD_CALLS: val})
    print(f"  📞 GHL: number_of_cold_calls → {val}")


# ════════════════════════════════════════════════════════════════════════════
#  DISPOSITION ROUTER
# ════════════════════════════════════════════════════════════════════════════

def handle_disposition(config, lead, disposition):
    """
    Update GHL after a classified call:
    - Sets cold_call_result custom field (fires existing GHL workflows)
    - Adds 'send info' tag if disposition is Send Info
    """
    contact_id = get_or_create_contact(config, lead)
    if not contact_id:
        print(f"  ❌ Could not find/create GHL contact for {lead.get('phone')}")
        return None

    result_value = COLD_CALL_RESULT_MAP.get(disposition, disposition)
    _update_custom_fields(config, contact_id, {CF_COLD_CALL_RESULT: result_value})
    print(f"  ✅ GHL: cold_call_result → {result_value}")

    # Remove needs-call tag so contact drops off the dialer queue
    dialer_tag = config.get("dialer_tag", "needs-call")
    try:
        requests.delete(
            f"{GHL_BASE}/contacts/{contact_id}/tags",
            headers=_headers(),
            json={"tags": [dialer_tag]},
            timeout=10
        )
    except Exception:
        pass

    if disposition == "Send Info":
        try:
            requests.post(
                f"{GHL_BASE}/contacts/{contact_id}/tags",
                headers=_headers(),
                json={"tags": ["send info"]},
                timeout=10
            )
        except Exception:
            pass

    return contact_id


def trigger_sms_handoff(config, lead):
    """Trigger SMS appointment-setting workflow after 3 unanswered calls."""
    print(f"  📱 Handing off {lead.get('business')} ({lead.get('phone')}) to SMS agent...")
    return handle_disposition(config, lead, "SMS Handoff")


# ════════════════════════════════════════════════════════════════════════════
#  WORKFLOW MANUAL ACTION — complete pending call action after each call
# ════════════════════════════════════════════════════════════════════════════

def _get_pending_call_tasks(config, contact_id, _retries=3):
    """Return any pending manual call tasks for a GHL contact. Retries on 429."""
    import time
    url    = f"{GHL_BASE}/contacts/{contact_id}/tasks"
    params = {"locationId": config.get("ghl_location_id", "")}
    for attempt in range(_retries):
        try:
            r = requests.get(url, headers=_headers(), params=params, timeout=10)
            if r.status_code == 429:
                time.sleep(1 * (attempt + 1))
                continue
            r.raise_for_status()
            tasks = r.json().get("tasks", [])
            return [
                t for t in tasks
                if not t.get("completed", False)
                and "call" in t.get("title", "").lower()
            ]
        except Exception as e:
            if attempt < _retries - 1:
                time.sleep(0.5)
            else:
                print(f"  ⚠️  GHL get tasks failed: {e}")
    return []


def _complete_task(config, contact_id, task_id):
    """Mark a GHL task as completed."""
    url  = f"{GHL_BASE}/contacts/{contact_id}/tasks/{task_id}"
    body = {"completed": True}
    try:
        r = requests.put(url, headers=_headers(), json=body, timeout=10)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"  ⚠️  GHL complete task failed: {e}")
        return False


def _get_or_create_conversation(config, contact_id):
    """Get the GHL conversation ID for a contact, or create one."""
    location_id = config.get("ghl_location_id", "")
    try:
        r = requests.get(
            f"{GHL_BASE}/conversations/search",
            headers=_headers(),
            params={"locationId": location_id, "contactId": contact_id},
            timeout=10
        )
        r.raise_for_status()
        convos = r.json().get("conversations", [])
        if convos:
            return convos[0]["id"]

        r2 = requests.post(
            f"{GHL_BASE}/conversations",
            headers=_headers(),
            json={"locationId": location_id, "contactId": contact_id},
            timeout=10
        )
        r2.raise_for_status()
        return r2.json().get("conversation", {}).get("id")
    except Exception as e:
        print(f"  ⚠️  GHL conversation lookup failed: {e}")
        return None


def satisfy_workflow_call_action(config, contact_id, disposition, duration_seconds=0):
    """
    Log the call in the contact's conversation timeline.
    Workflow progression happens automatically via tag removal + cold_call_result field.
    """
    location_id = config.get("ghl_location_id", "")

    call_status_map = {
        "No Answer":          "no-answer",
        "SMS Handoff":        "no-answer",
        "Follow Up":          "answered",
        "Appointment Booked": "answered",
        "Send Info":          "answered",
        "Not Interested":     "answered",
    }
    conv_id = _get_or_create_conversation(config, contact_id)
    if conv_id:
        try:
            requests.post(
                f"{GHL_BASE}/conversations/messages",
                headers=_headers(),
                json={
                    "type":           "Call",
                    "conversationId": conv_id,
                    "contactId":      contact_id,
                    "direction":      "outbound",
                    "status":         call_status_map.get(disposition, "answered"),
                    "duration":       duration_seconds,
                    "body":           f"Parallel Dialer — {disposition}",
                    "locationId":     location_id,
                },
                timeout=10
            )
            print(f"  📋 GHL call logged: {disposition} ({duration_seconds}s)")
        except Exception as e:
            print(f"  ⚠️  GHL call log failed: {e}")


# ════════════════════════════════════════════════════════════════════════════
#  NOTES
# ════════════════════════════════════════════════════════════════════════════

def add_note(config, contact_id, note_text):
    """Add a call note to a GHL contact."""
    url  = f"{GHL_BASE}/contacts/{contact_id}/notes"
    body = {"body": note_text, "userId": ""}
    try:
        r = requests.post(url, headers=_headers(), json=body, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print(f"  ⚠️  GHL note failed: {e}")


def _now_iso():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


# ════════════════════════════════════════════════════════════════════════════
#  WORKFLOW TRIGGER
# ════════════════════════════════════════════════════════════════════════════

def trigger_workflow(config, contact_id, workflow_id):
    """Enroll a contact in a GHL workflow by ID."""
    location_id = config.get("ghl_location_id", "")
    try:
        r = requests.post(
            f"{GHL_BASE}/contacts/{contact_id}/workflow/{workflow_id}",
            headers=_headers(),
            json={"locationId": location_id},
            timeout=10,
        )
        r.raise_for_status()
    except Exception as e:
        print(f"  ⚠️  GHL workflow trigger failed: {e}")


# ════════════════════════════════════════════════════════════════════════════
#  VOICEMAIL DISPOSITION
# ════════════════════════════════════════════════════════════════════════════

def handle_voicemail(config, contact_id):
    """
    After leaving a voicemail:
    - Set cold_call_result = No Answer
    - Remove needs-call tag (drops from dialer queue)
    - Add voicemail-left tag
    - Trigger AI appointment-setting workflow
    """
    dialer_tag = config.get("dialer_tag", "needs-call")

    _update_custom_fields(config, contact_id, {CF_COLD_CALL_RESULT: "No Answer"})

    try:
        requests.delete(
            f"{GHL_BASE}/contacts/{contact_id}/tags",
            headers=_headers(),
            json={"tags": [dialer_tag]},
            timeout=10,
        )
    except Exception:
        pass

    try:
        requests.post(
            f"{GHL_BASE}/contacts/{contact_id}/tags",
            headers=_headers(),
            json={"tags": ["voicemail-left"]},
            timeout=10,
        )
    except Exception:
        pass

    workflow_id = config.get("ghl_workflows", {}).get("voicemail", "")
    if workflow_id and not workflow_id.startswith("WORKFLOW_ID"):
        trigger_workflow(config, contact_id, workflow_id)
        print(f"  🤖 GHL: voicemail left → AI appointment agent triggered")
    else:
        print(f"  📭 GHL: voicemail-left tag added (set ghl_workflows.voicemail to activate AI agent)")


# ════════════════════════════════════════════════════════════════════════════
#  LEAD LOADING FROM GHL MANUAL ACTIONS
# ════════════════════════════════════════════════════════════════════════════

def _contact_to_lead(contact):
    """Convert a GHL contact dict to a dialer lead dict."""
    first = contact.get("firstName", "") or ""
    last  = contact.get("lastName", "") or ""
    return {
        "contact_id": contact.get("id"),
        "phone":      contact.get("phone", ""),
        "business":   contact.get("companyName") or "",
        "owner":      f"{first} {last}".strip(),
        "grade":      _cf(contact, CF_LEAD_GRADE) or "C",
        "opener":     _cf(contact, CF_CUSTOM_OPENER) or "",
        "email":      contact.get("email", ""),
        "attempts":   0,
    }


# ════════════════════════════════════════════════════════════════════════════
#  TAG HELPERS
# ════════════════════════════════════════════════════════════════════════════

def add_tag(config, contact_id, tag):
    """Add a single tag to a GHL contact."""
    try:
        requests.post(
            f"{GHL_BASE}/contacts/{contact_id}/tags",
            headers=_headers(),
            json={"tags": [tag]},
            timeout=10,
        )
    except Exception as e:
        print(f"  ⚠️  GHL add tag '{tag}' failed: {e}")


def remove_tag(config, contact_id, tag):
    """Remove a single tag from a GHL contact."""
    try:
        requests.delete(
            f"{GHL_BASE}/contacts/{contact_id}/tags",
            headers=_headers(),
            json={"tags": [tag]},
            timeout=10,
        )
    except Exception as e:
        print(f"  ⚠️  GHL remove tag '{tag}' failed: {e}")


# ════════════════════════════════════════════════════════════════════════════
#  NEWSLETTER LEADS
# ════════════════════════════════════════════════════════════════════════════

def get_newsletter_leads(config):
    """Return all contacts tagged 'newsletter', converted to lead dicts."""
    location_id  = config.get("ghl_location_id", "")
    page_limit   = 100
    all_contacts = []
    body = {
        "locationId": location_id,
        "filters": [{"field": "tags", "operator": "contains", "value": "newsletter"}],
        "pageLimit": page_limit,
    }

    while True:
        try:
            r = requests.post(
                f"{GHL_BASE}/contacts/search",
                headers=_headers(), json=body, timeout=20,
            )
            r.raise_for_status()
            data  = r.json()
            batch = data.get("contacts", [])
            if not batch:
                break
            all_contacts.extend(batch)
            if len(batch) < page_limit:
                break
            last = batch[-1]
            body["searchAfter"] = last.get("searchAfter") or [last["id"]]
        except Exception as e:
            print(f"  ⚠️  GHL newsletter leads fetch failed: {e}")
            break

    leads = [_contact_to_lead(c) for c in all_contacts if c.get("email")]
    print(f"  ✅ {len(leads)} contacts with 'newsletter' tag and email address")
    return leads


def load_dialer_leads(config):
    """
    Return contacts tagged 'needs-call' (set by GHL workflow before each manual action),
    sorted by lead grade A→D.

    The workflow adds 'needs-call' when a manual call action is queued and removes it
    (or our dialer removes it) when the call is completed.
    """
    location_id = config.get("ghl_location_id", "")
    dialer_tag  = config.get("dialer_tag", "needs-call")
    page_limit  = 100
    all_contacts = []
    body = {
        "locationId": location_id,
        "filters": [{"field": "tags", "operator": "contains", "value": dialer_tag}],
        "pageLimit": page_limit,
    }

    while True:
        try:
            r = requests.post(
                f"{GHL_BASE}/contacts/search",
                headers=_headers(), json=body, timeout=20
            )
            r.raise_for_status()
            data  = r.json()
            batch = data.get("contacts", [])
            if not batch:
                break
            all_contacts.extend(batch)
            if len(batch) < page_limit:
                break
            last = batch[-1]
            body["searchAfter"] = last.get("searchAfter") or [last["id"]]
        except Exception as e:
            print(f"  ⚠️  GHL contacts fetch failed: {e}")
            break

    leads = [_contact_to_lead(c) for c in all_contacts if c.get("phone")]

    grade_order = {"A": 0, "B": 1, "C": 2, "D": 3}
    leads.sort(key=lambda x: grade_order.get(x.get("grade", "C"), 3))
    print(f"  ✅ {len(leads)} leads ready to dial")
    return leads
