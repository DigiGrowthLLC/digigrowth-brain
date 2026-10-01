"""
Send Info -> personalized Loom queue.

Setting a contact's disposition to "Send Info" used to fire a generic
templated SMS + email immediately (routers/crm.py, routers/dialer.py). Now
it enqueues a row here instead: the outreach-video skill's Send Info Queue
Mode (content-agent/.claude/skills/outreach-video/SKILL.md) needs local
Playwright + ffmpeg + Dylan's local headcam-master.mp4, none of which exist
on this Railway container, so the personalized video can't be generated
synchronously inside a request. A scheduled local Claude Code run drains
this queue (content-agent/run-send-info-queue.ps1, same shape as
leadgen-agent's scheduled scrape-leads run), calling complete()/fail() below
via the /api/send-info-queue endpoints in routers/dialer.py once each
video's ready (or has failed).

routers.sms and integrations are imported lazily inside functions to avoid
circular imports (both of those modules are imported by routers that in
turn get imported before this module in some call chains).

The same queue also serves the "Gatekeeper Deferral" status (kind =
'gatekeeper_deferral'): a front desk told Dylan to reach the owner by email,
so the owner gets the same personalized video, emailed only (no SMS — that
number is the front desk's), with the gatekeeper-deferral template naming
the receptionist when the thread or call notes did. The local video run
doesn't care which kind a row is; complete() sends the right thing.
"""

import re

from db import get_pool

SEND_INFO = "send_info"
GATEKEEPER_DEFERRAL = "gatekeeper_deferral"


async def enqueue(contact: dict, kind: str = SEND_INFO) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO send_info_loom_queue (contact_id, kind) VALUES ($1, $2)",
            contact["id"], kind,
        )


# ── Receptionist name ─────────────────────────────────────────────────────────
# Front desks introduce themselves in a handful of ways: "This is Nell at the
# front desk", "My name is Jennifer, her office assistant", a "-Kayla" or
# "~Fernanda" sign-off. A capitalized word in one of those spots is a name
# unless it's the owner's own name or part of the practice name ("This is
# Rocket City Performance Therapy").

_INTRO = re.compile(
    r"\b(?:this is|it'?s|it is|i'?m|i am|my name is|you(?:'ve)? got|you get|you have)\s+([A-Z][a-z]{1,15})\b",
    re.I,
)
_SIGNOFF = re.compile(r"(?:^|\s)[-~–—]\s*([A-Z][a-z]{1,15})\s*$|(?:thanks|thank you|best),?\s*\n\s*([A-Z][a-z]{1,15})\s*$", re.I | re.M)
_NOTE = re.compile(
    r"\b(?:receptionist|front desk|gatekeeper|assistant|admin|spoke (?:with|to)|talked to)\s*(?:named|is|was|:|-)?\s+([A-Z][a-z]{1,15})\b"
)
_NOT_NAMES = {
    "the", "his", "her", "our", "their", "dr", "doctor", "office", "front", "desk", "clinic", "physical", "therapy",
    "pt", "physio", "practice", "business", "main", "line", "number", "team", "admin", "assistant", "patient",
    "services", "yes", "no", "hi", "hello", "hey", "sorry", "not", "just", "also", "actually", "currently", "here",
    "she", "he", "him", "we", "you", "your", "a", "an", "one", "on", "in", "at", "with", "from", "for", "regarding",
}


def receptionist_name(inbound_texts: list[str], notes: str | None, owner: str | None, business: str | None) -> str | None:
    """Best guess at the gatekeeper's first name, most recent mention first,
    or None — the template then just says "your receptionist"."""
    owner_words = {w.lower().strip(".,") for w in (owner or "").split()}
    business_words = {w.lower().strip(".,'&-") for w in re.split(r"\s+", business or "")}

    def ok(name: str | None) -> str | None:
        if not name:
            return None
        n = name.strip()
        if n.lower() in _NOT_NAMES or n.lower() in owner_words or n.lower() in business_words:
            return None
        return n[0].upper() + n[1:].lower()

    for text in reversed([t for t in inbound_texts if t]):
        for m in list(_INTRO.finditer(text)):
            # _INTRO is case-insensitive for the lead-in only; the name itself
            # must be written capitalized, or "this is his office" would match.
            if m.group(1)[0].isupper() and (name := ok(m.group(1))):
                return name
        for m in _SIGNOFF.finditer(text.strip()):
            if name := ok(m.group(1) or m.group(2)):
                return name
    for m in reversed(list(_NOTE.finditer(notes or ""))):
        if name := ok(m.group(1)):
            return name
    return None


async def _receptionist_for(conn, contact_id: str, phone: str | None, notes: str | None,
                            owner: str | None, business: str | None) -> str | None:
    digits = re.sub(r"\D", "", phone or "")[-10:]
    texts = [r["body"] for r in await conn.fetch(
        "SELECT body FROM sms_messages WHERE direction = 'inbound' AND "
        "(contact_id = $1 OR ($2 <> '' AND right(regexp_replace(phone, '\\D', '', 'g'), 10) = $2)) ORDER BY sent_at",
        contact_id, digits,
    )]
    return receptionist_name(texts, notes, owner, business)


async def _send_now(contact: dict, loom_url: str | None) -> None:
    import integrations
    from routers import sms as sms_router

    try:
        await sms_router.send_info_message(contact, loom_url=loom_url)
    except Exception as e:
        print(f"send-info SMS failed for {contact.get('phone')}: {e}")
    if contact.get("email"):
        try:
            result = await integrations.send_info_email(
                contact["email"], contact.get("owner"), contact.get("business"), loom_url=loom_url,
            )
            if not result.startswith("Sent email"):
                print(f"send-info email to {contact['email']} did not send: {result}")
        except Exception as e:
            print(f"send-info email failed for {contact.get('email')}: {e}")


async def _send_gatekeeper_deferral(conn, contact: dict, notes: str | None, loom_url: str) -> str | None:
    """Email only, to the address on the contact (the one the front desk
    gave Dylan). Returns an error string if it couldn't send."""
    import integrations

    if not contact.get("email"):
        return "no email on file: add the email the front desk gave you to the contact, then set Gatekeeper Deferral again"
    receptionist = await _receptionist_for(
        conn, contact["id"], contact.get("phone"), notes, contact.get("owner"), contact.get("business"),
    )
    try:
        result = await integrations.gatekeeper_deferral_email(
            contact["email"], contact.get("owner"), contact.get("business"), receptionist, loom_url,
        )
    except Exception as e:
        return f"email failed: {e}"
    return None if result.startswith("Sent email") else f"email did not send: {result}"


async def complete(queue_id: int, watch_url: str) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT q.*, c.id AS c_id, c.phone, c.email, c.owner, c.business, c.notes "
            "FROM send_info_loom_queue q JOIN contacts c ON c.id = q.contact_id "
            "WHERE q.id = $1",
            queue_id,
        )
        if not row:
            raise ValueError(f"Queue entry {queue_id} not found")
        contact = {"id": row["c_id"], "phone": row["phone"], "email": row["email"],
                   "owner": row["owner"], "business": row["business"]}
        if row["kind"] == GATEKEEPER_DEFERRAL:
            error = await _send_gatekeeper_deferral(conn, contact, row["notes"], watch_url)
            if error:
                print(f"gatekeeper-deferral send failed for contact {contact['id']}: {error}")
                failed = await conn.fetchrow(
                    "UPDATE send_info_loom_queue SET status = 'failed', watch_url = $2, error = $3, completed_at = now() "
                    "WHERE id = $1 RETURNING *",
                    queue_id, watch_url, error,
                )
                return dict(failed)
        else:
            await _send_now(contact, loom_url=watch_url)
        updated = await conn.fetchrow(
            "UPDATE send_info_loom_queue SET status = 'done', watch_url = $2, completed_at = now() "
            "WHERE id = $1 RETURNING *",
            queue_id, watch_url,
        )
    return dict(updated)


async def fail(queue_id: int, error: str) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE send_info_loom_queue SET status = 'failed', error = $2, completed_at = now() "
            "WHERE id = $1 RETURNING *",
            queue_id, error,
        )
    if not row:
        raise ValueError(f"Queue entry {queue_id} not found")
    return dict(row)
