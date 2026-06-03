"""
Notion message fetcher for SMS agent.

Fetches the live message sequence from the Notion SMS page immediately before
every send — no caching. If Dylan updates a message in Notion, it takes effect
on the next outbound.

Notion SMS page: 310d25c0-53ea-80f7-a0e2-d9f780a03e6e
Sub-pages map to stages by title keyword:
  "initial message"  → opening
  "primed"           → primed
  "engaged"          → engaged
  "cta"              → cta
  "follow-up 1"      → followup_1
  "follow-up 2"      → followup_2
  "follow-up 3"      → followup_3
  (also matches "fup 1", "followup 1", etc.)
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

NOTION_API      = "https://api.notion.com/v1"
NOTION_SMS_PAGE = "310d25c053ea80f7a0e2d9f780a03e6e"

# Keywords that identify each stage from sub-page titles (lowercase match)
STAGE_KEYWORDS = {
    "initial": "opening",
    "primed":  "primed",
    "engaged": "engaged",
    "cta":     "cta",
    "booking": "booking",
    "follow-up 1": "followup_1",
    "follow-up 2": "followup_2",
    "follow-up 3": "followup_3",
    "fup 1":       "followup_1",
    "fup 2":       "followup_2",
    "fup 3":       "followup_3",
    "followup 1":  "followup_1",
    "followup 2":  "followup_2",
    "followup 3":  "followup_3",
}


def _headers():
    token = os.environ.get("NOTION_TOKEN", "")
    if not token:
        raise RuntimeError(
            "NOTION_TOKEN not set in .env — add your Notion integration token "
            "(notion.so/my-integrations) and share the SMS page with it."
        )
    return {
        "Authorization":  f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type":   "application/json",
    }


def _get_block_children(block_id):
    """Return all child blocks of a page or block."""
    url     = f"{NOTION_API}/blocks/{block_id}/children"
    results = []
    cursor  = None
    while True:
        params = {"page_size": 100}
        if cursor:
            params["start_cursor"] = cursor
        r = requests.get(url, headers=_headers(), params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        results.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return results


_SKIP_TYPES = {"heading_1", "heading_2", "heading_3", "divider", "child_page", "child_database"}

def _extract_text(blocks):
    """Extract plain text from Notion blocks, skipping headings and structural blocks."""
    parts = []
    for block in blocks:
        btype = block.get("type", "")
        if btype in _SKIP_TYPES:
            continue
        bdata = block.get(btype, {})
        rich  = bdata.get("rich_text", [])
        line  = "".join(rt.get("plain_text", "") for rt in rich)
        if line.strip():
            parts.append(line.strip())
    return "\n".join(parts)


def _title_to_stage(title):
    """Map a Notion sub-page title to a stage key. Returns None if no match."""
    lower = title.lower()
    for keyword, stage in STAGE_KEYWORDS.items():
        if keyword in lower:
            return stage
    return None


def fetch_messages():
    """
    Fetch the current SMS message sequence from Notion right now.

    Returns dict mapping stage name → message text, e.g.:
        {
            "opening":   "Hey is this {first_name}?",
            "primed":    "Awesome it's Dylan...",
            "engaged":   "Perfect, feel free to...",
            "cta":       "Awesome, yea do you mind...",
            "followup_1": "...",   # if Dylan has added these sub-pages
            "followup_2": "...",
            "followup_3": "...",
        }

    Called immediately before every outbound send — never cached.
    """
    blocks   = _get_block_children(NOTION_SMS_PAGE)
    messages = {}

    for block in blocks:
        if block.get("type") != "child_page":
            continue
        title = block.get("child_page", {}).get("title", "")
        stage = _title_to_stage(title)
        if not stage:
            continue
        page_id    = block.get("id", "").replace("-", "")
        sub_blocks = _get_block_children(page_id)
        text       = _extract_text(sub_blocks)
        if text:
            messages[stage] = text

    return messages


def _strip_label(text):
    """
    Remove a leading label like 'Initial Message: ' or 'Primed: ' from message text.
    Keeps the label visible in Notion for Dylan's reference but strips it before sending.
    Matches: one or more words followed by ': ' at the very start of the text.
    """
    import re
    return re.sub(r"^[\w][\w ]{0,30}:\s+", "", text, count=1)


def get_message(stage, messages, lead=None):
    """
    Get the message for a given stage from a fetched messages dict.
    Replaces {first_name} and {business} placeholders if lead is provided.
    Raises KeyError if the stage is not found in Notion.
    """
    if stage not in messages:
        raise KeyError(
            f"No Notion sub-page found for stage '{stage}'. "
            f"Add a sub-page titled to match '{stage}' on the SMS Notion page."
        )
    text = _strip_label(messages[stage])
    if lead:
        first_name = (lead.get("owner") or "there").split()[0]
        business   = lead.get("business") or "your studio"
        opener     = lead.get("opener") or ""
        text = text.replace("{first_name}", first_name)
        text = text.replace("{{first_name}}", first_name)
        text = text.replace("{business}", business)
        text = text.replace("{{business_name}}", business)
        text = text.replace("{{contact.first_name}}", first_name)
        # Bracket-style placeholders Dylan uses in Notion
        text = text.replace("[Studio Name]", business)
        text = text.replace("[studio name]", business)
        text = text.replace("[custom opener]", opener)
    return text


def fetch_reference(page_ids):
    """
    Fetch one or more reference pages from Notion and return combined plain text.
    Accepts a string (single ID) or list of IDs.
    Returns empty string if nothing is set or all fetches fail.
    """
    if not page_ids:
        return ""
    if isinstance(page_ids, str):
        page_ids = [page_ids]
    parts = []
    for page_id in page_ids:
        if not page_id:
            continue
        try:
            blocks = _get_block_children(page_id.replace("-", ""))
            text = _extract_text(blocks)
            if text:
                parts.append(text)
        except Exception as e:
            print(f"  ⚠️  Could not fetch reference page {page_id}: {e}")
    return "\n\n---\n\n".join(parts)
