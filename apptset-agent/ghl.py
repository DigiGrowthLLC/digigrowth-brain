"""
GHL API helpers for the SMS appointment agent.
Only the functions needed for SMS conversation management.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

GHL_BASE = "https://services.leadconnectorhq.com"

# Custom field IDs (shared with parallel-dialer)
CF_LEAD_GRADE    = "53vuuYEBnWTFA2bieX12"
CF_CUSTOM_OPENER = "Mg7mf31yey0FoCoEYoPJ"


def _headers():
    token = os.environ.get("GHL_PRIVATE_TOKEN") or os.environ.get("GHL_API_KEY", "")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
        "Version":       "2021-07-28",
    }


def _cf(contact, field_id):
    for field in contact.get("customFields", []):
        if field.get("id") == field_id:
            val = field.get("value", "")
            if isinstance(val, list):
                return val[0] if val else ""
            return val or ""
    return ""


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


def contact_to_lead(contact):
    """Convert a GHL contact dict to a lead dict for the SMS agent."""
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
        "city":       contact.get("city", ""),
        "state":      contact.get("state", ""),
    }


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


def get_or_create_conversation(config, contact_id):
    """Return the GHL conversation ID for a contact, creating one if needed."""
    location_id = config.get("ghl_location_id", "")
    try:
        r = requests.get(
            f"{GHL_BASE}/conversations/search",
            headers=_headers(),
            params={"locationId": location_id, "contactId": contact_id},
            timeout=10,
        )
        r.raise_for_status()
        convos = r.json().get("conversations", [])
        if convos:
            return convos[0]["id"]

        r2 = requests.post(
            f"{GHL_BASE}/conversations",
            headers=_headers(),
            json={"locationId": location_id, "contactId": contact_id},
            timeout=10,
        )
        r2.raise_for_status()
        return r2.json().get("conversation", {}).get("id")
    except Exception as e:
        print(f"  ⚠️  GHL conversation lookup/create failed: {e}")
        return None


def get_newsletter_leads(config):
    """Return all contacts tagged 'newsletter' that have an email address."""
    location_id = config.get("ghl_location_id", "")
    page_limit  = 100
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

    leads = [contact_to_lead(c) for c in all_contacts if c.get("email")]
    print(f"  ✅ {len(leads)} contacts with 'newsletter' tag and email address")
    return leads


def send_sms(config, contact_id, message):
    """Send an outbound SMS to a contact via GHL conversations API."""
    conv_id = get_or_create_conversation(config, contact_id)
    if not conv_id:
        raise RuntimeError(f"Could not get GHL conversation for contact {contact_id}")

    body = {
        "type":           "SMS",
        "conversationId": conv_id,
        "contactId":      contact_id,
        "message":        message,
    }
    from_number = config.get("ghl_from_number", "")
    if from_number:
        body["fromNumber"] = from_number

    r = requests.post(
        f"{GHL_BASE}/conversations/messages",
        headers=_headers(),
        json=body,
        timeout=10,
    )
    r.raise_for_status()
    msg_id = r.json().get("messageId", "")
    print(f"  📱 GHL SMS → contact {contact_id}: {message[:80]}{'...' if len(message) > 80 else ''} [{msg_id}]")
    return msg_id
