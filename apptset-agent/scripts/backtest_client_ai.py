"""
Backtest a CLIENT's response AI (dashboard/backend/response_ai.py, e.g.
CrosaCore's "Sophie") against that client's real SMS threads, through the
exact system prompt and tool list the live agent uses.

For every point where a lead texted in, the thread is cut right after that
message and the agent writes what it would send now. The report shows the
last few messages, what actually went out, and the new reply side by side,
plus any tools it called.

Tools are stubbed, nothing touches Calendly, Twilio or the database:
check_availability always returns the day after the historical moment at
2:00 PM or 5:45 PM, propose_appointment always succeeds, and the rest just
acknowledge. Uses the Anthropic API (same as the live agent), so run it
under Doppler:

  doppler run --project digigrowth --config prd -- \
    python apptset-agent/scripts/backtest_client_ai.py --client 1 --out backtest.md

--config-file takes a JSON file of marketing-config fields (response_ai_context,
response_ai_rules, response_ai_sequence, response_ai_max_words) that override
the live ones, to test a prompt change BEFORE saving it. --threads limits the
run to leads whose phone ends in the given digits (e.g. --threads 0274 3404).
"""
import argparse
import asyncio
import base64
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "dashboard" / "backend"))
import anthropic  # noqa: E402
import response_ai  # noqa: E402
from timezone_lookup import guess_timezone  # noqa: E402


def _api_get(path: str):
    url = os.environ["DASHBOARD_URL"].rstrip("/") + path
    req = urllib.request.Request(url)
    auth = base64.b64encode(f"admin:{os.environ['DASHBOARD_PASSWORD']}".encode()).decode()
    req.add_header("Authorization", f"Basic {auth}")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def threads_by_lead(messages: list[dict]) -> dict[str, list[dict]]:
    threads: dict[str, list[dict]] = {}
    for m in messages:
        if m.get("stage") == "escalation_alert":
            continue  # the owner's alert text, not part of any lead's thread
        lead = m["to_number"] if m["direction"] == "outbound" else m["from_number"]
        threads.setdefault(lead, []).append(m)
    for msgs in threads.values():
        msgs.sort(key=lambda m: m["created_at"])
    return threads


def decision_points(msgs: list[dict]) -> list[int]:
    """Index of each inbound message that ends a run of inbound texts —
    the moment the agent has to answer."""
    return [
        i for i, m in enumerate(msgs)
        if m["direction"] == "inbound" and (i + 1 == len(msgs) or msgs[i + 1]["direction"] == "outbound")
    ]


def _when(m: dict) -> datetime:
    return datetime.fromisoformat(m["created_at"].replace("Z", "+00:00"))


def _stub_tool(name: str, tool_input: dict, at: datetime, tz: ZoneInfo) -> str:
    if name == "check_availability":
        after = tool_input.get("after_date")
        day = datetime.fromisoformat(after).date() if after else at.astimezone(tz).date() + timedelta(days=1)
        while day.weekday() >= 5:
            day += timedelta(days=1)
        label = f"{day:%A, %B} {day.day}"
        return f"Earliest real openings (lead's local time): {label} at 2:00 PM or 5:45 PM"
    if name == "propose_appointment":
        return (f"Confirmed on the calendar for {tool_input.get('date')} {tool_input.get('time')} — they'll get "
                "a calendar confirmation by email. Tell them they're all set.")
    if name == "escalate_to_human":
        return "Escalated to a human team member."
    if name == "mark_unqualified":
        return ("Marked Unqualified. Send one short, polite closing text now; after this turn they get no "
                "further automated messages.")
    if name == "close_conversation":
        return "Closed. Send one short, kind closing text now with no question."
    if name == "schedule_followup":
        return "Check-in scheduled. Reply with one short line, no question needed."
    return "Done."


def run_turn(api: anthropic.Anthropic, model: str, system_prompt: str, messages: list[dict],
             at: datetime, tz: ZoneInfo) -> tuple[str, list[str]]:
    calls: list[str] = []
    text = ""
    for _ in range(response_ai._MAX_TOOL_ITERATIONS):
        resp = api.messages.create(model=model, max_tokens=1024, system=system_prompt,
                                   tools=response_ai._TOOLS, messages=messages)
        messages.append({"role": "assistant", "content": resp.content})
        text = "\n".join(b.text for b in resp.content if b.type == "text").strip()
        uses = [b for b in resp.content if b.type == "tool_use"]
        if not uses:
            break
        results = []
        for u in uses:
            calls.append(f"{u.name}({json.dumps(u.input)})")
            results.append({"type": "tool_result", "tool_use_id": u.id, "content": _stub_tool(u.name, u.input, at, tz)})
        messages.append({"role": "user", "content": results})
    return text, calls


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--client", type=int, required=True)
    ap.add_argument("--config-file", help="JSON overrides for the client's response_ai_* fields")
    ap.add_argument("--threads", nargs="*", help="only leads whose phone ends in these digits")
    ap.add_argument("--out", default="backtest_client_ai.md")
    args = ap.parse_args()

    clients = {c["id"]: c for c in _api_get("/api/clients")}
    config = _api_get(f"/api/clients/{args.client}/marketing-config")
    if args.config_file:
        config.update(json.loads(Path(args.config_file).read_text(encoding="utf-8")))
    sequence = config.get("response_ai_sequence") or []
    if isinstance(sequence, str):
        sequence = json.loads(sequence)
    messages = _api_get(f"/api/clients/{args.client}/sms-messages?limit=5000")

    api = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.environ.get("AGENTS_CLAUDE_MODEL", "claude-sonnet-5")
    out = [f"# Client AI backtest: {clients[args.client]['name']}", "",
           f"Model `{model}`, config {'from ' + args.config_file if args.config_file else 'live'}.", ""]

    for lead, msgs in sorted(threads_by_lead(messages).items(), key=lambda kv: kv[1][0]["created_at"]):
        if args.threads and not any(lead.endswith(t) for t in args.threads):
            continue
        points = decision_points(msgs)
        if not points:
            continue
        tz_name = guess_timezone(lead)
        tz = ZoneInfo(tz_name)
        out += [f"## Lead ...{lead[-4:]} ({tz_name})", ""]
        for i in points:
            at = _when(msgs[i])
            local = at.astimezone(tz)
            history = [
                {"role": "user" if m["direction"] == "inbound" else "assistant", "content": m["body"]}
                for m in msgs[: i + 1]
            ][-response_ai._HISTORY_LIMIT:]
            system_prompt = response_ai._build_system_prompt(
                clients[args.client]["name"], config.get("response_ai_context") or "", sequence,
                config.get("response_ai_max_words"), config.get("response_ai_rules") or "",
                f"{local:%A, %B} {local.day}, {local.year}",
            )
            try:
                draft, calls = run_turn(api, model, system_prompt, history, at, tz)
            except Exception as e:
                draft, calls = f"(error: {e})", []
            actual = []
            for m in msgs[i + 1:]:
                if m["direction"] != "outbound":
                    break
                actual.append(f"{m['body']}" + (f"  _[{m['stage']}]_" if m.get("stage") else ""))
            out.append(f"**{local:%a %b %d %I:%M %p}**")
            for m in msgs[max(0, i - 3): i + 1]:
                who = "LEAD" if m["direction"] == "inbound" else "AI"
                out.append(f"> {who}: {m['body']}")
            out.append("")
            out.append("- Actually sent: " + (" / ".join(actual) if actual else "_(nothing)_"))
            out.append("- New reply: " + (draft.replace("\n", " / ") if draft else "_(nothing)_"))
            if calls:
                out.append("- Tools: " + "; ".join(calls))
            out.append("")
            print(f"...{lead[-4:]} {local:%m-%d %H:%M} done", flush=True)

    Path(args.out).write_text("\n".join(out), encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
