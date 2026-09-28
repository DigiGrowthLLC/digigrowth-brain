"""
Backtest the SMS setter against real campaign threads, through the exact
prompt the live worker uses (dashboard/backend/sms_setter_ai.py) and the
exact `claude -p` call it makes (apptset-agent/sms_setter_worker.py) — so
it runs on the Claude subscription, not the API.

For each sampled "decision point" (a prospect message that Dylan answered
himself), the thread is cut right after that message and the setter drafts
what it would have sent. The report puts the last few messages, Dylan's
actual reply, and the draft side by side.

The calendar is stubbed (weekdays 9am-4pm on the hour, prospect's time,
starting the day after the historical moment). Nothing touches the database
or Twilio.

Get the export first (read-only endpoint), then run:

  doppler run --project digigrowth --config prd -- bash -c \
    'curl -s -u "admin:$DASHBOARD_PASSWORD" "$DASHBOARD_URL/api/agents/campaign-sms-export?campaign_id=4"' > v14.json
  python apptset-agent/scripts/backtest_sms_setter.py v14.json --n 40 --out backtest.md
"""
import argparse
import asyncio
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "dashboard" / "backend"))
sys.path.insert(0, str(_REPO / "apptset-agent"))
import sms_setter_ai  # noqa: E402
import sms_setter_worker  # noqa: E402
from timezone_lookup import guess_timezone  # noqa: E402

_AUTOMATED = ("auto_opener", "dm_followup", "reminder_", "no_show", "cancel")


def _is_dylans_reply(m: dict) -> bool:
    if m["direction"] != "outbound":
        return False
    stage = m.get("stage") or ""
    return not any(stage.startswith(p) for p in _AUTOMATED)


def decision_points(conv: dict) -> list[int]:
    """Indices i where messages[i] is the prospect's message and the next
    message is one Dylan chose to send."""
    msgs = conv["messages"]
    return [
        i for i in range(len(msgs) - 1)
        if msgs[i]["direction"] == "inbound" and _is_dylans_reply(msgs[i + 1])
    ]


def sample(convs: list[dict], n: int, seed: int) -> list[tuple[dict, int]]:
    rng = random.Random(seed)
    rich, rest = [], []
    for c in convs:
        advanced = c.get("stage_primed") or c.get("stage_engaged") or c.get("disposition") == "booked"
        for i in decision_points(c):
            (rich if advanced else rest).append((c, i))
    rng.shuffle(rich)
    rng.shuffle(rest)
    # Over-weight conversations that got past the pitch — that's where
    # objection handling and booking are actually exercised.
    take_rich = min(len(rich), (n * 3) // 5)
    return rich[:take_rich] + rest[: n - take_rich]


def stub_slots(tz_name: str, when: datetime) -> list[datetime]:
    tz = ZoneInfo(tz_name)
    day = when.astimezone(tz).date() + timedelta(days=1)
    slots = []
    while len(slots) < 7 * 8:
        if day.weekday() < 5:
            for hour in range(9, 17):
                slots.append(datetime(day.year, day.month, day.day, hour, tzinfo=tz).astimezone(timezone.utc))
        day += timedelta(days=1)
    return slots


async def run_one(conv: dict, i: int, sem: asyncio.Semaphore) -> dict:
    msgs = conv["messages"][: i + 1]
    when = datetime.fromisoformat(msgs[-1]["sent_at"].replace("Z", "+00:00")) + timedelta(minutes=2)
    tz_name = guess_timezone(conv["phone"])
    contact = {k: conv.get(k) for k in ("business", "owner", "state", "opener")}
    prompt = sms_setter_ai.build_user_message(
        contact, msgs, tz_name, when, sms_setter_ai.format_open_slots(stub_slots(tz_name, when), tz_name, when),
    )
    async with sem:
        try:
            result = await asyncio.to_thread(
                sms_setter_worker.run_claude, sms_setter_ai.system_prompt(), prompt, sms_setter_ai.DRAFT_SCHEMA,
            )
            draft = sms_setter_ai.normalize_draft(result) if result else None
        except Exception as e:
            draft = {"action": "ERROR", "reply": str(e), "rationale": ""}
    return {"conv": conv, "i": i, "draft": draft or {"action": "NO DRAFT", "reply": "", "rationale": ""}}


def render(results: list[dict]) -> str:
    out = ["# SMS setter backtest", ""]
    counts: dict[str, int] = {}
    for r in results:
        counts[r["draft"]["action"]] = counts.get(r["draft"]["action"], 0) + 1
    out.append("Actions: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    out.append("")
    for n, r in enumerate(results, 1):
        c, i, d = r["conv"], r["i"], r["draft"]
        msgs = c["messages"]
        out.append(f"## {n}. {c.get('business')} ({c.get('owner')}), disposition: {c.get('disposition')}")
        out.append("")
        for m in msgs[max(0, i - 4): i + 1]:
            who = "PROSPECT" if m["direction"] == "inbound" else f"DYLAN [{m.get('stage') or 'manual'}]"
            out.append(f"> **{who}:** {m['body']}")
        out.append("")
        out.append(f"**Dylan actually sent:** {msgs[i + 1]['body']}")
        out.append("")
        details = ", ".join(f"{k}={d.get(k)}" for k in ("booking_date", "booking_time", "email", "follow_up_date") if d.get(k))
        out.append(f"**Setter draft [{d['action']}]{' (' + details + ')' if details else ''}:** {d.get('reply') or '(empty)'}")
        out.append("")
        out.append(f"*Why:* {d.get('rationale', '')}")
        out.append("")
    return "\n".join(out)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("export")
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--seed", type=int, default=14)
    ap.add_argument("--concurrency", type=int, default=3)
    ap.add_argument("--out", default="sms_setter_backtest.md")
    args = ap.parse_args()

    data = json.loads(Path(args.export).read_text(encoding="utf-8"))
    points = sample(data["conversations"], args.n, args.seed)
    sem = asyncio.Semaphore(args.concurrency)
    results = await asyncio.gather(*(run_one(c, i, sem) for c, i in points))
    Path(args.out).write_text(render(results), encoding="utf-8")
    print(f"{len(results)} decision points -> {args.out}")


if __name__ == "__main__":
    asyncio.run(main())
