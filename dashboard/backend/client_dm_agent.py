"""Social media conversation agent — a CLIENT's AI appointment setter for
Instagram and Facebook Page DMs: ad replies, "how much?", story replies,
any inbound message for any reason. Same brain as response_ai.py (the
client's context, rules, approved lessons, calendar), different channel.

Inbound: Meta's webhook for the client's Page (routers/meta_lead_webhooks.py
receives every Page/Instagram webhook for the app, since an app has one
callback URL per object) hands each `messaging` event here. A thread is one
person on one platform (Meta's page-scoped sender id). A message from the
lead sets reply_due_at a few seconds out, so a burst of messages gets one
answer, and process_due() (main.py, every 15s) replies. Restart-safe: the
due time lives in the table, not in memory.

The 24-hour rule: Meta only lets a business send automated messages within
24 hours of the person's last message. So the agent's real job is to get a
booking, or their mobile number, inside that window. Once it has a number
(save_contact_info), the lead becomes a normal client lead (lead_source
ig_dm / fb_dm) and booking runs through response_ai's own tools with that
phone. If the DM then goes quiet, one SMS hands the conversation over to
text (stage 'dm_handoff', which enrolls them in the regular follow-up).

Silence inside the window: one DM nudge after 3 hours, and if there's
still no number, a last one at ~22 hours asking for it.

Human takeover: a message the clinic's staff send from Business Suite
arrives as an echo we didn't send; the agent stays out of that thread for
12 hours after a human's last message. Escalations go to Dylan's To-Do
list (urgent ones also text the clinic), like the SMS agent.

Requires (per client, see the Agents tab): dm_agent_enabled, the Page ID,
the Page subscribed to messages + message_echoes (connect()), and the app's
Instagram webhook subscribed to messages. Real (non-test) DMs need the
app's pages_messaging / instagram_manage_messages permissions approved in
Meta App Review; until then only people with a role on the app get through.
"""

import asyncio
import os
import time
from datetime import datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

import anthropic
import httpx

import lead_flags
from db import get_pool
from timezone_lookup import guess_timezone

_GRAPH_BASE = "https://graph.facebook.com/v21.0"
_REPLY_DEBOUNCE = timedelta(seconds=15)
_WINDOW = timedelta(hours=24)
_HUMAN_PAUSE = timedelta(hours=12)
_NUDGE_AFTER = timedelta(hours=3)
_LAST_CALL_AT = timedelta(hours=22)  # after their last message, inside the window
_HANDOFF_AFTER = timedelta(hours=20)  # of silence after our last DM, number on file
_HISTORY_LIMIT = 30
_MAX_TOOL_ITERATIONS = 5
_MAX_CHARS = 900  # Instagram caps a DM at 1000

PLATFORM_LABEL = {"instagram": "Instagram", "facebook": "Facebook"}

_DM_CHANNEL_ADDITION = (
    "\n=== THIS CONVERSATION IS A {platform} DIRECT MESSAGE, NOT A TEXT ===\n"
    "Everything above about texting applies, with these differences:\n"
    "- They messaged the business's {platform} account. They may be replying to an ad or a post, "
    "asking a quick question, or just saying hi: find out what they need before anything else.\n"
    "- Keep it short and casual, like a person at the clinic answering DMs. No emoji unless they use them.\n"
    "- Meta only lets the business message them for 24 hours after their last message. So once they "
    "show any interest in coming in, or ask something that needs a follow-up, ask for their mobile "
    "number (\"what's the best number to reach you?\"), and call save_contact_info as soon as they "
    "give it. Booking needs it too: propose_appointment won't work until a number is saved.\n"
    "- You can't schedule a later check-in here. If they want to be contacted later, get their number "
    "and say the team will text them.\n"
)

_DM_SAVE_TOOL = {
    "name": "save_contact_info",
    "description": (
        "Save the lead's mobile number (and name/email if they gave them) the moment they share it. "
        "This is what lets you book them and lets the clinic text them after this DM conversation. "
        "Call it before propose_appointment."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "phone": {"type": "string", "description": "Their mobile number, as they wrote it."},
            "name": {"type": "string", "description": "Their full name, if they gave it."},
            "email": {"type": "string", "description": "Their email, if they gave it."},
        },
        "required": ["phone"],
    },
}

_page_tokens: dict[str, tuple[str, float]] = {}
_app_id: str | None = None


async def _our_app_id() -> str | None:
    """This Meta app's id (what an echo of our own send carries as app_id),
    looked up once from the System User token."""
    global _app_id
    if _app_id is None:
        try:
            async with httpx.AsyncClient() as http:
                resp = await http.get(f"{_GRAPH_BASE}/app", params={"access_token": os.environ.get("META_SYSTEM_USER_TOKEN", "")}, timeout=15)
            if resp.status_code == 200:
                _app_id = str(resp.json().get("id") or "") or None
        except Exception as e:
            print(f"[client_dm_agent] app id lookup failed: {e}")
    return _app_id


def _tools() -> list[dict]:
    import response_ai
    keep = {"check_availability", "propose_appointment", "escalate_to_human", "mark_unqualified", "close_conversation"}
    return [t for t in response_ai._TOOLS if t["name"] in keep] + [_DM_SAVE_TOOL]


async def _page_token(page_id: str) -> str:
    """Page access token from the shared System User token, cached for an
    hour (every send needs one)."""
    from routers.meta_lead_webhooks import _get_page_access_token

    cached = _page_tokens.get(page_id)
    if cached and cached[1] > time.time():
        return cached[0]
    system_token = os.environ.get("META_SYSTEM_USER_TOKEN")
    if not system_token:
        raise RuntimeError("META_SYSTEM_USER_TOKEN not set")
    async with httpx.AsyncClient() as http:
        token = await _get_page_access_token(http, page_id, system_token)
    _page_tokens[page_id] = (token, time.time() + 3600)
    return token


async def _client_for(conn, platform: str, account_id: str):
    column = "instagram_account_id" if platform == "instagram" else "meta_page_id"
    return await conn.fetchrow(
        f"""
        SELECT cmc.client_id, cmc.meta_page_id, cmc.dm_agent_enabled, cmc.twilio_number
        FROM client_marketing_config cmc WHERE cmc.{column} = $1
        """,
        account_id,
    )


async def _lookup_name(page_id: str, sender_id: str) -> str | None:
    try:
        token = await _page_token(page_id)
        async with httpx.AsyncClient() as http:
            resp = await http.get(f"{_GRAPH_BASE}/{sender_id}", params={"fields": "name", "access_token": token}, timeout=15)
        if resp.status_code == 200:
            return (resp.json().get("name") or "").strip() or None
    except Exception as e:
        print(f"[client_dm_agent] name lookup failed for {sender_id}: {e}")
    return None


def _message_text(message: dict) -> str:
    text = (message.get("text") or "").strip()
    if text:
        return text
    kinds = {a.get("type") for a in message.get("attachments") or []}
    if "story_mention" in kinds:
        return "[mentioned the business in their story]"
    if kinds:
        return f"[sent {', '.join(sorted(k for k in kinds if k))}]"
    if message.get("reply_to", {}).get("story"):
        return "[replied to the business's story]"
    return "[sent a message with no text]"


async def handle_webhook_entry(platform: str, entry: dict) -> None:
    """One webhook `entry` with `messaging` events. Never raises."""
    account_id = str(entry.get("id") or "")
    for event in entry.get("messaging") or []:
        try:
            message = event.get("message")
            if not message or message.get("is_deleted"):
                continue
            sender_id = str((event.get("sender") or {}).get("id") or "")
            recipient_id = str((event.get("recipient") or {}).get("id") or "")
            if message.get("is_echo"):
                await _record_echo(platform, account_id, recipient_id, message)
            elif sender_id and sender_id != account_id:
                await _record_inbound(platform, account_id, sender_id, message)
        except Exception as e:
            print(f"[client_dm_agent] {platform} event failed for account={account_id}: {e}")


async def _record_inbound(platform: str, account_id: str, sender_id: str, message: dict) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        client = await _client_for(conn, platform, account_id)
        if not client:
            print(f"[client_dm_agent] {platform} account {account_id} isn't mapped to a client — skipping DM")
            return
        thread = await conn.fetchrow(
            """
            INSERT INTO client_dm_threads (client_id, platform, sender_id) VALUES ($1, $2, $3)
            ON CONFLICT (client_id, platform, sender_id) DO UPDATE SET platform = EXCLUDED.platform
            RETURNING *
            """,
            client["client_id"], platform, sender_id,
        )
        inserted = await conn.fetchval(
            "INSERT INTO client_dm_messages (thread_id, direction, sender, body, mid) VALUES ($1, 'inbound', 'lead', $2, $3) "
            "ON CONFLICT (mid) DO NOTHING RETURNING id",
            thread["id"], _message_text(message), message.get("mid"),
        )
        if not inserted:
            return  # Meta retried a delivery we already have
        # A new message from them reopens a thread the agent closed
        # (they're back) and restarts the silence nudges.
        status = "ai_active" if thread["status"] == "closed" else thread["status"]
        # Booked leads still get answers (rescheduling, questions); the
        # booked-context in the prompt keeps the agent from re-pitching.
        replying = client["dm_agent_enabled"] and status in ("ai_active", "booked")
        due = datetime.now(dt_timezone.utc) + _REPLY_DEBOUNCE if replying else None
        await conn.execute(
            "UPDATE client_dm_threads SET last_inbound_at = now(), status = $2, reply_due_at = $3, nudges_sent = 0 WHERE id = $1",
            thread["id"], status, due,
        )
    if not thread["sender_name"] and client["meta_page_id"]:
        name = await _lookup_name(client["meta_page_id"], sender_id)
        if name:
            async with pool.acquire() as conn:
                await conn.execute("UPDATE client_dm_threads SET sender_name = $2 WHERE id = $1", thread["id"], name)


async def _record_echo(platform: str, account_id: str, recipient_id: str, message: dict) -> None:
    """A message the Page sent. Anything we didn't send is a person at the
    clinic replying by hand. Ours carry this app's id, and are stored under
    their mid; the echo can beat that insert, hence the short wait."""
    app_id = str(message.get("app_id") or "")
    if app_id and app_id == await _our_app_id():
        return
    await asyncio.sleep(3)
    pool = await get_pool()
    async with pool.acquire() as conn:
        client = await _client_for(conn, platform, account_id)
        if not client or not recipient_id:
            return
        thread = await conn.fetchrow(
            "SELECT id FROM client_dm_threads WHERE client_id = $1 AND platform = $2 AND sender_id = $3",
            client["client_id"], platform, recipient_id,
        )
        if not thread:
            return
        if await conn.fetchval("SELECT 1 FROM client_dm_messages WHERE mid = $1", message.get("mid")):
            return
        inserted = await conn.fetchval(
            "INSERT INTO client_dm_messages (thread_id, direction, sender, body, mid) VALUES ($1, 'outbound', 'human', $2, $3) "
            "ON CONFLICT (mid) DO NOTHING RETURNING id",
            thread["id"], _message_text(message), message.get("mid"),
        )
        if inserted:
            await conn.execute(
                "UPDATE client_dm_threads SET human_last_at = now(), last_outbound_at = now(), reply_due_at = NULL WHERE id = $1",
                thread["id"],
            )


async def _send_dm(page_id: str, sender_id: str, text: str) -> str | None:
    """Sends through the Page (the same endpoint serves Instagram DMs for an
    Instagram account linked to the Page). Returns Meta's message id."""
    token = await _page_token(page_id)
    async with httpx.AsyncClient() as http:
        resp = await http.post(
            f"{_GRAPH_BASE}/me/messages", params={"access_token": token}, timeout=30,
            json={"recipient": {"id": sender_id}, "messaging_type": "RESPONSE", "message": {"text": text[:_MAX_CHARS]}},
        )
    if resp.status_code != 200:
        raise RuntimeError(f"Send API {resp.status_code}: {resp.text.strip()[:300]}")
    return resp.json().get("message_id")


async def _history(conn, thread_id: int) -> list[dict]:
    rows = await conn.fetch(
        "SELECT direction, sender, body FROM client_dm_messages WHERE thread_id = $1 ORDER BY created_at DESC, id DESC LIMIT $2",
        thread_id, _HISTORY_LIMIT,
    )
    messages = []
    for r in reversed(rows):
        role = "user" if r["direction"] == "inbound" else "assistant"
        body = r["body"] if r["sender"] != "human" else f"[sent by a person at the clinic] {r['body']}"
        if messages and messages[-1]["role"] == role:
            messages[-1]["content"] += "\n" + body
        else:
            messages.append({"role": role, "content": body})
    return messages


async def _system_prompt(conn, client_id: int, thread: dict, clinic_phone: str | None) -> str | None:
    import response_ai

    row = await conn.fetchrow(
        "SELECT cmc.response_ai_context, cmc.response_ai_sequence, cmc.response_ai_rules, c.name "
        "FROM client_marketing_config cmc JOIN clients c ON c.id = cmc.client_id WHERE cmc.client_id = $1",
        client_id,
    )
    if not row:
        return None
    sequence = row["response_ai_sequence"]
    if isinstance(sequence, str):
        import json
        sequence = json.loads(sequence)
    lessons = await response_ai._active_lessons(conn, client_id)
    origin = {"lead_source": f"{'ig' if thread['platform'] == 'instagram' else 'fb'}_dm"}
    booking = None
    if thread.get("phone"):
        booking = await response_ai._upcoming_booking(conn, thread["phone"], None)
    tz_phone = thread.get("phone") or clinic_phone or ""
    prompt = response_ai._build_system_prompt(
        row["name"], row["response_ai_context"] or "", sequence or [], None, row["response_ai_rules"] or "",
        response_ai._today_str(guess_timezone(tz_phone)),
        booked_for=response_ai._format_booking(booking) if booking else None,
        lessons=lessons, origin=origin,
    )
    known = []
    if thread.get("sender_name"):
        known.append(f"Their {PLATFORM_LABEL[thread['platform']]} name: {thread['sender_name']}.")
    if thread.get("phone"):
        known.append(f"Their mobile number is already saved ({thread['phone']}); don't ask for it again.")
    if known:
        prompt += "\n" + " ".join(known) + "\n"
    return prompt + _DM_CHANNEL_ADDITION.format(platform=PLATFORM_LABEL[thread["platform"]])


async def _save_contact(conn, client_id: int, thread: dict, tool_input: dict, dry_run: bool) -> str:
    from client_reactivation import normalize_phone

    phone = normalize_phone(tool_input.get("phone") or "")
    if not phone:
        return "That doesn't look like a valid US mobile number. Ask them to double-check it."
    if dry_run:
        thread["phone"] = phone
        return f"Saved {phone} (test mode, nothing written)."
    name = (tool_input.get("name") or "").strip() or thread.get("sender_name")
    email = (tool_input.get("email") or "").strip() or None
    source = f"{'ig' if thread['platform'] == 'instagram' else 'fb'}_dm"
    detail = f"Messaged the business on {PLATFORM_LABEL[thread['platform']]}"
    existing = await conn.fetchrow(
        r"""
        SELECT id, client_id, is_client_anchor FROM contacts
        WHERE right(regexp_replace(phone, '\D', '', 'g'), 10) = right(regexp_replace($1, '\D', '', 'g'), 10)
        ORDER BY (client_id = $2) DESC, created_at ASC LIMIT 1
        """,
        phone, client_id,
    )
    contact_id = None
    if existing and not existing["is_client_anchor"] and existing["client_id"] in (None, client_id):
        contact_id = existing["id"]
        await conn.execute(
            "UPDATE contacts SET client_id = COALESCE(client_id, $2), owner = COALESCE(owner, $3), "
            "email = COALESCE(email, $4), lead_source = COALESCE(lead_source, $5), "
            "source_detail = COALESCE(source_detail, $6), updated_at = now() WHERE id = $1",
            contact_id, client_id, name, email, source, detail,
        )
    elif not existing:
        import uuid
        contact_id = await conn.fetchval(
            "INSERT INTO contacts (id, owner, phone, email, status, client_id, lead_source, source_detail, tags) "
            "VALUES ($1, $2, $3, $4, 'new', $5, $6, $7, $8) RETURNING id",
            str(uuid.uuid4()), name, phone, email, client_id, source, detail, lead_flags.SOURCE_TAGS[source],
        )
    if contact_id:
        # An existing lead who now DMs the business gets the tag too.
        for tag in lead_flags.SOURCE_TAGS[source]:
            await lead_flags.add_tag(contact_id, tag)
    # A number owned by another client or an anchor contact: keep it on the
    # thread for booking, but don't touch that contact.
    await conn.execute(
        "UPDATE client_dm_threads SET phone = $2, contact_id = $3 WHERE id = $1", thread["id"], phone, contact_id,
    )
    thread["phone"] = phone
    thread["contact_id"] = contact_id
    return "Saved. You can book them now if they want a time; otherwise answer what they asked."


async def _escalate(conn, client_id: int, thread: dict, reason: str, urgent: bool, dry_run: bool) -> str:
    import client_sms

    if dry_run:
        return "Escalated (test mode). Write no reply: the handoff is silent and a human picks up the thread."
    await conn.execute(
        "UPDATE client_dm_threads SET status = 'escalated', status_reason = $2 WHERE id = $1", thread["id"], reason,
    )
    row = await conn.fetchrow(
        "SELECT cl.name, cmc.call_forward_number FROM clients cl JOIN client_marketing_config cmc ON cmc.client_id = cl.id WHERE cl.id = $1",
        client_id,
    )
    platform = PLATFORM_LABEL[thread["platform"]]
    who = thread.get("sender_name") or thread.get("phone") or f"a {platform} user"
    text = f"{row['name'] if row else 'Client'} {platform} DM needs a human: {who}"
    if not await conn.fetchval("SELECT 1 FROM todos WHERE NOT done AND text = $1", text):
        await conn.execute(
            "INSERT INTO todos (text, description, due_date) VALUES ($1, $2, $3)",
            text,
            f"{reason}\n\nThe AI has paused on this {platform} thread. Reply from the client's {platform} inbox "
            "(Meta Business Suite), then click HAND BACK TO AI on the Agents tab if the agent should take over again."
            + ("\n\nMarked URGENT: the business owner was texted too." if urgent else ""),
            datetime.now(ZoneInfo("America/New_York")).date(),
        )
    forward = ((row["call_forward_number"] if row else None) or "").strip()
    if urgent and forward:
        try:
            await client_sms.send_client_sms(
                client_id, forward,
                f"Your AI assistant needs you on {platform}: {who}. {reason[:200]} Reply to them from your {platform} inbox.",
                stage="escalation_alert",
            )
        except Exception as e:
            print(f"[client_dm_agent] urgent alert failed for client={client_id}: {e}")
    return "Escalated: the team will take it from here. Write no reply: the handoff is silent and a human picks up the thread."


async def _execute_tool(client_id: int, thread: dict, clinic_phone: str | None, name: str, tool_input: dict, dry_run: bool) -> str:
    import response_ai

    pool = await get_pool()
    if name == "save_contact_info":
        async with pool.acquire() as conn:
            return await _save_contact(conn, client_id, thread, tool_input, dry_run)
    if name == "check_availability":
        # Their own number decides their timezone once known; until then
        # the clinic's, since a DM lead is almost always local.
        return await response_ai._execute_tool(client_id, thread.get("phone") or clinic_phone or "", name, tool_input)
    if name == "propose_appointment":
        if not thread.get("phone"):
            return ("Not booked: ask for their mobile number first (needed for the booking and reminders), call "
                    "save_contact_info, then call propose_appointment again with the same time.")
        if dry_run:
            return f"Test mode: would book {tool_input.get('date')} {tool_input.get('time')}. Tell them they're all set."
        if tool_input.get("lead_name") or tool_input.get("lead_email") or thread.get("sender_name"):
            async with pool.acquire() as conn:
                if thread.get("contact_id"):
                    await conn.execute(
                        "UPDATE contacts SET owner = COALESCE(owner, $2), email = COALESCE(email, $3) WHERE id = $1",
                        thread["contact_id"], (tool_input.get("lead_name") or thread.get("sender_name") or "").strip() or None,
                        (tool_input.get("lead_email") or "").strip() or None,
                    )
        result = await response_ai._execute_tool(client_id, thread["phone"], name, tool_input)
        if result.startswith(("Confirmed", "Booked")):
            async with pool.acquire() as conn:
                await conn.execute("UPDATE client_dm_threads SET status = 'booked' WHERE id = $1", thread["id"])
        return result
    if name == "escalate_to_human":
        async with pool.acquire() as conn:
            return await _escalate(conn, client_id, thread, (tool_input.get("reason") or "").strip() or "Needs a human",
                                   bool(tool_input.get("urgent")), dry_run)
    if name in ("mark_unqualified", "close_conversation"):
        status = "unqualified" if name == "mark_unqualified" else "closed"
        if not dry_run:
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE client_dm_threads SET status = $2, status_reason = $3 WHERE id = $1",
                    thread["id"], status, (tool_input.get("reason") or "").strip() or None,
                )
            if status == "unqualified" and thread.get("contact_id"):
                await lead_flags.add_tag(thread["contact_id"], lead_flags.UNQUALIFIED_TAG)
        return "Done. Send one short, kind closing message now, with no question."
    return f"Unknown tool: {name}"


async def run_agent(client_id: int, thread: dict, messages: list[dict], clinic_phone: str | None,
                    dry_run: bool = False) -> str | None:
    """One reply from the agent for this thread. `dry_run` (the Agents tab's
    test chat) reads the calendar but writes and books nothing."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        system_prompt = await _system_prompt(conn, client_id, thread, clinic_phone)
    if not system_prompt or not messages:
        return None
    if messages[0]["role"] != "user":
        messages.insert(0, {"role": "user", "content": "[conversation start]"})
    api_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.environ.get("AGENTS_CLAUDE_MODEL", "claude-sonnet-5")
    tools = _tools()
    text_parts: list[str] = []
    escalated = False
    for _ in range(_MAX_TOOL_ITERATIONS):
        response = await asyncio.to_thread(
            api_client.messages.create,
            model=model, max_tokens=1024, system=system_prompt, tools=tools, messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})
        text_parts = [b.text for b in response.content if b.type == "text"]
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if not tool_uses:
            break
        results = []
        for tool_use in tool_uses:
            escalated = escalated or tool_use.name == "escalate_to_human"
            result = await _execute_tool(client_id, thread, clinic_phone, tool_use.name, tool_use.input, dry_run)
            results.append({"type": "tool_result", "tool_use_id": tool_use.id, "content": result})
        messages.append({"role": "user", "content": results})
    if escalated:
        # A handoff is silent (Dylan, 2026-10-29): no "the team will follow
        # up" message, so whoever picks it up just continues the thread.
        return None
    return "\n".join(text_parts).strip() or None


async def _reply(thread: dict, note: str | None = None) -> None:
    """Answer (or, with `note`, nudge) one thread, if it's still allowed."""
    pool = await get_pool()
    now = datetime.now(dt_timezone.utc)
    async with pool.acquire() as conn:
        config = await conn.fetchrow(
            "SELECT dm_agent_enabled, meta_page_id, twilio_number FROM client_marketing_config WHERE client_id = $1",
            thread["client_id"],
        )
        if not config or not config["dm_agent_enabled"] or not config["meta_page_id"]:
            return
        if thread["status"] not in ("ai_active", "booked"):
            return
        if thread["human_last_at"] and now - thread["human_last_at"] < _HUMAN_PAUSE:
            return
        if not thread["last_inbound_at"] or now - thread["last_inbound_at"] > _WINDOW:
            return  # outside Meta's 24-hour window: we can't send
        if thread["contact_id"] and await conn.fetchval(
            f"SELECT {lead_flags.UNQUALIFIED_SQL} FROM contacts c WHERE c.id = $1", thread["contact_id"],
        ):
            return
        messages = await _history(conn, thread["id"])
    if note:
        messages.append({"role": "user", "content": note})
    thread = dict(thread)
    text = await run_agent(thread["client_id"], thread, messages, config["twilio_number"])
    if not text:
        return
    try:
        mid = await _send_dm(config["meta_page_id"], thread["sender_id"], text)
    except Exception as e:
        print(f"[client_dm_agent] send failed for thread={thread['id']}: {e}")
        return
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO client_dm_messages (thread_id, direction, sender, body, mid) VALUES ($1, 'outbound', 'ai', $2, $3) "
            "ON CONFLICT (mid) DO NOTHING",
            thread["id"], text, mid,
        )
        await conn.execute("UPDATE client_dm_threads SET last_outbound_at = now() WHERE id = $1", thread["id"])


_NUDGE_NOTE = (
    "[System note: they haven't replied for a few hours. Write ONE short, natural follow-up that builds on "
    "your last message (never repeat it, never \"just following up\"). If your last message asked something, "
    "make that ask easier instead of stacking a new question.]"
)
_LAST_CALL_NOTE = (
    "[System note: this is the last message you'll be able to send in this DM, since Meta closes the "
    "conversation 24 hours after their last message. In one short message, offer to text them instead and "
    "ask for the best number to reach them. No pressure.]"
)
_HANDOFF_PREAMBLE = (
    "\nYou are texting this person FIRST, by SMS, to pick up a conversation they started in a direct "
    "message to the business (see the brief below). Write ONE short text: sound like the same person from "
    "the DM, end with one easy question, no link, no prices or offers the business info doesn't state. "
    "Reply with only the text itself, nothing else.\n"
)
_HANDOFF_BRIEF = (
    "They messaged the business on {platform}, gave this number, and then the DM went quiet. Write the first "
    "text to them: say who you are and that you're following up from their {platform} message, refer to what "
    "they asked about in plain words, and end with one easy question. No link."
)


async def _handoff_to_sms(thread: dict) -> None:
    """The DM went quiet after they gave a number: one text picks the
    conversation up on SMS (and from then on it's an ordinary SMS lead)."""
    import client_sms
    import response_ai

    pool = await get_pool()
    async with pool.acquire() as conn:
        claimed = await conn.fetchval(
            "UPDATE client_dm_threads SET sms_handoff_at = now() WHERE id = $1 AND sms_handoff_at IS NULL RETURNING id",
            thread["id"],
        )
        if not claimed:
            return
        config = await conn.fetchrow(
            "SELECT response_ai_enabled, twilio_number FROM client_marketing_config WHERE client_id = $1", thread["client_id"],
        )
        history = await _history(conn, thread["id"])
    if not config or not config["response_ai_enabled"] or not config["twilio_number"]:
        return
    if await lead_flags.is_opted_out(thread["client_id"], thread["phone"]):
        return
    if lead_flags.in_quiet_hours(guess_timezone(thread["phone"]), datetime.now(dt_timezone.utc)):
        async with pool.acquire() as conn:  # try again in the morning
            await conn.execute("UPDATE client_dm_threads SET sms_handoff_at = NULL WHERE id = $1", thread["id"])
        return
    platform = PLATFORM_LABEL[thread["platform"]]
    transcript = "\n".join(
        f"{'Them' if m['role'] == 'user' else 'Business'}: {m['content']}" for m in history[-12:]
    )
    brief = _HANDOFF_BRIEF.format(platform=platform) + f"\n\nThe {platform} conversation so far:\n{transcript}"
    text = await response_ai.write_outreach_text(thread["client_id"], thread["phone"], brief, _HANDOFF_PREAMBLE)
    if not text:
        return
    try:
        await client_sms.send_client_sms(thread["client_id"], thread["phone"], text, stage="dm_handoff")
    except Exception as e:
        print(f"[client_dm_agent] SMS handoff failed for thread={thread['id']}: {e}")


async def _clinic_phone(client_id: int) -> str | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT twilio_number FROM client_marketing_config WHERE client_id = $1", client_id)


async def process_due() -> None:
    """Scheduler job: due replies, then silence nudges and SMS handoffs."""
    pool = await get_pool()
    now = datetime.now(dt_timezone.utc)
    async with pool.acquire() as conn:
        due = await conn.fetch(
            """
            UPDATE client_dm_threads SET reply_due_at = NULL
            WHERE id IN (SELECT id FROM client_dm_threads WHERE reply_due_at <= now() ORDER BY reply_due_at LIMIT 10 FOR UPDATE SKIP LOCKED)
            RETURNING *
            """
        )
        quiet = await conn.fetch(
            """
            SELECT t.* FROM client_dm_threads t
            JOIN client_marketing_config cmc ON cmc.client_id = t.client_id AND cmc.dm_agent_enabled
            WHERE t.status = 'ai_active' AND t.reply_due_at IS NULL
              AND t.last_outbound_at IS NOT NULL AND t.last_inbound_at IS NOT NULL
              AND t.last_outbound_at > t.last_inbound_at
              AND t.last_inbound_at > now() - interval '3 days'
            """
        )
    for t in due:
        try:
            await _reply(dict(t))
        except Exception as e:
            print(f"[client_dm_agent] reply failed for thread={t['id']}: {e}")
    for record in quiet:
        t = dict(record)
        try:
            since_theirs = now - t["last_inbound_at"]
            since_ours = now - t["last_outbound_at"]
            if t["phone"]:
                if not t["sms_handoff_at"] and since_ours >= _HANDOFF_AFTER:
                    await _handoff_to_sms(t)
                continue
            if since_theirs >= _WINDOW:
                continue
            note = None
            if lead_flags.in_quiet_hours(guess_timezone(await _clinic_phone(t["client_id"]) or ""), now):
                continue
            if t["nudges_sent"] == 0 and since_ours >= _NUDGE_AFTER and since_theirs < _LAST_CALL_AT:
                note = _NUDGE_NOTE
            elif t["nudges_sent"] < 2 and since_theirs >= _LAST_CALL_AT:
                note = _LAST_CALL_NOTE
            if not note:
                continue
            async with pool.acquire() as conn:
                await conn.execute("UPDATE client_dm_threads SET nudges_sent = nudges_sent + 1 WHERE id = $1", t["id"])
            await _reply(t, note)
        except Exception as e:
            print(f"[client_dm_agent] follow-up failed for thread={t['id']}: {e}")


async def connect(client_id: int) -> dict:
    """Wire a client's Page up for DMs: find the Instagram account linked to
    the Page, and subscribe the Page to messages + message_echoes (keeping
    whatever fields it already had, e.g. leadgen). Records the result on
    the config either way."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        page_id = await conn.fetchval("SELECT meta_page_id FROM client_marketing_config WHERE client_id = $1", client_id)
    error = None
    ig_id = None
    try:
        if not page_id:
            raise RuntimeError("Save the client's Meta Page ID first (Paid Ad Creatives step)")
        token = await _page_token(page_id)
        async with httpx.AsyncClient() as http:
            page = await http.get(f"{_GRAPH_BASE}/{page_id}", params={"fields": "instagram_business_account", "access_token": token}, timeout=30)
            if page.status_code == 200:
                ig_id = (page.json().get("instagram_business_account") or {}).get("id")
            current = await http.get(f"{_GRAPH_BASE}/{page_id}/subscribed_apps", params={"access_token": token}, timeout=30)
            fields = {"messages", "message_echoes"}
            if current.status_code == 200:
                for app in current.json().get("data") or []:
                    fields |= set(app.get("subscribed_fields") or [])
            sub = await http.post(
                f"{_GRAPH_BASE}/{page_id}/subscribed_apps",
                params={"subscribed_fields": ",".join(sorted(fields)), "access_token": token}, timeout=30,
            )
            if sub.status_code != 200 or not sub.json().get("success"):
                raise RuntimeError(f"Subscribing the Page failed: {sub.status_code} {sub.text.strip()[:300]}")
    except Exception as e:
        error = str(e)
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE client_marketing_config SET instagram_account_id = COALESCE($2, instagram_account_id), "
            "dm_connected_at = CASE WHEN $3::text IS NULL THEN now() ELSE dm_connected_at END, dm_connect_error = $3 "
            "WHERE client_id = $1",
            client_id, ig_id, error,
        )
    return {"ok": error is None, "error": error, "instagram_account_id": ig_id}
