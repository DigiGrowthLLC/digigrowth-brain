"""
Sales tracking (2026-11-25): sales campaigns, Fireflies call data, and the
automatic Patient Acquisition Blueprint for a two-call close.

Sales campaigns
---------------
A "sales" channel in the campaigns system (routers/campaigns.py). Every new
discovery call Dylan books (appointment_reminders, call_type 'discovery',
not a client's own patient) is stamped with whichever sales campaign is
active when it's created (appointments.create_appointment_row), the same
stamp-at-creation convention as SMS/email. Creating a new sales campaign in
Analytics -> Campaigns -> Sales ends the old one, so new calls count toward
the new one from then on.

The first sales campaign, "Free Offer V.1.3", is seeded once (ensure_seeded):
every discovery call registered in the OS (appointment_reminders), from the
very first one (Dylan, 2026-11-25: Austin Treadwell, Brandon Crosdale etc.
count, they're in the OS). Meetings that only ever lived in the old Sales
Performance Tracker sheet (the frozen sheet_baseline_* numbers in
sales_stats.json) are never added to campaign stats.

Stats are a cohort of FIRST calls (appointments.follow_up_appointment_sql):
a follow-up call counts toward nothing on its own, but a close on it is
credited to the first call it follows, same rule as analytics._os_sales_stats.

Two-call close
--------------
outcome_close = 'two_call' (Appointments -> outcome card): the prospect
didn't close on this call, but a second call is booked. Counted as its own
row in the campaign stats (and whether it later converted). Marking it
queues a blueprint job: Dylan's PC (apptset-agent/sms_setter_worker.py,
blueprint thread) runs the patient-acquisition-blueprint skill through
`claude -p`, publishes the page, and reports the URL back. The link shows
on that prospect's next appointment in the Appointments tab.

Fireflies
---------
Fireflies (Dylan's notetaker on his Google Meet calls) has a GraphQL API.
sync_fireflies() (every 15 min, plus POST /webhooks/fireflies when a
transcript finishes) pulls recent transcripts and matches each to a
discovery appointment by a participant email = the prospect's email, else
the only appointment within 40 minutes of the meeting start. It fills
call_recording_url (the Fireflies transcript/recording page) and
call_length only when they're empty, so anything Dylan typed wins, and
keeps the Fireflies summary (call_summary) for the blueprint run.
Needs FIREFLIES_API_KEY (Fireflies -> Settings -> Developer settings);
FIREFLIES_WEBHOOK_SECRET is optional (verifies the webhook signature).
"""

import hashlib
import hmac
import json
import os
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx

from db import get_pool

_ET = ZoneInfo("America/New_York")
V13_NAME = "Free Offer V.1.3"
PAGES_BASE = os.environ.get("LANDING_PAGES_BASE_URL", "https://pages.digigrowthllc.com").rstrip("/")
FIREFLIES_URL = "https://api.fireflies.ai/graphql"
BLUEPRINT_STALE_AFTER = timedelta(hours=4)   # a 'running' job with no result by then is retried / failed
BLUEPRINT_MAX_ATTEMPTS = 2

# Dylan's own sales calls only: discovery, not canceled, not a client's own
# patient, not a DigiGrowth Booking patient row. Alias `ar`, joined to `c`.
SALES_ROW_SQL = (
    "ar.call_type = 'discovery' AND ar.status != 'canceled' "
    "AND COALESCE(ar.calendly_event_uri, '') NOT LIKE 'dgbook:%' "
    "AND (c.id IS NULL OR c.client_id IS NULL OR c.is_client_anchor)"
)

# Active sales campaign, for INSERTs (appointments.create_appointment_row).
ACTIVE_SALES_CAMPAIGN_SQL = (
    "(SELECT cp.campaign_id FROM campaign_periods cp JOIN campaigns cc ON cc.id = cp.campaign_id "
    "WHERE cc.channel = 'sales' AND cp.ended_at IS NULL ORDER BY cp.started_at DESC LIMIT 1)"
)


# ── Schema + seed ─────────────────────────────────────────────────────────────

async def ensure_schema(conn) -> None:
    await conn.execute("""
        ALTER TABLE appointment_reminders ADD COLUMN IF NOT EXISTS sales_campaign_id INTEGER REFERENCES campaigns(id) ON DELETE SET NULL;
        ALTER TABLE appointment_reminders ADD COLUMN IF NOT EXISTS fireflies_transcript_id TEXT;
        ALTER TABLE appointment_reminders ADD COLUMN IF NOT EXISTS call_summary TEXT;
        ALTER TABLE appointment_reminders ADD COLUMN IF NOT EXISTS call_data_source TEXT;
        CREATE INDEX IF NOT EXISTS idx_appointment_reminders_sales_campaign ON appointment_reminders(sales_campaign_id);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_appointment_reminders_fireflies
            ON appointment_reminders(fireflies_transcript_id) WHERE fireflies_transcript_id IS NOT NULL;

        CREATE TABLE IF NOT EXISTS sales_blueprint_jobs (
            id                    SERIAL PRIMARY KEY,
            contact_id            TEXT REFERENCES contacts(id) ON DELETE CASCADE,
            source_appointment_id INTEGER REFERENCES appointment_reminders(id) ON DELETE SET NULL,
            status                TEXT NOT NULL DEFAULT 'queued',   -- queued / running / done / failed / canceled
            slug                  TEXT,
            url                   TEXT,
            error                 TEXT,
            notes                 TEXT,
            attempts              INTEGER NOT NULL DEFAULT 0,
            created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
            started_at            TIMESTAMPTZ,
            finished_at           TIMESTAMPTZ
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_sales_blueprint_jobs_open
            ON sales_blueprint_jobs(contact_id) WHERE status IN ('queued', 'running');
    """)


async def ensure_seeded(conn) -> None:
    """Creates "Free Offer V.1.3" once (only when no sales campaign exists
    yet), backdates its period to the first discovery call in the OS and
    tags every discovery call in appointment_reminders with it."""
    if await conn.fetchval("SELECT 1 FROM campaigns WHERE channel = 'sales' LIMIT 1"):
        return
    cutoff = await conn.fetchval(
        "SELECT min(created_at) FROM appointment_reminders WHERE call_type = 'discovery'"
    ) or datetime.now(timezone.utc)
    async with conn.transaction():
        cid = await conn.fetchval(
            "INSERT INTO campaigns (channel, name, created_at) VALUES ('sales', $1, $2) RETURNING id",
            V13_NAME, cutoff,
        )
        await conn.execute("INSERT INTO campaign_periods (campaign_id, started_at) VALUES ($1, $2)", cid, cutoff)
        n = await conn.fetchval(
            f"""
            WITH u AS (
                UPDATE appointment_reminders ar SET sales_campaign_id = $1
                FROM appointment_reminders ar2 LEFT JOIN contacts c ON c.id = ar2.contact_id
                WHERE ar2.id = ar.id AND ar.created_at >= $2 AND ar.sales_campaign_id IS NULL
                  AND ar.call_type = 'discovery'
                  AND COALESCE(ar.calendly_event_uri, '') NOT LIKE 'dgbook:%'
                  AND (c.id IS NULL OR c.client_id IS NULL OR c.is_client_anchor)
                RETURNING 1
            ) SELECT count(*) FROM u
            """,
            cid, cutoff,
        )
    print(f"[sales] seeded sales campaign '{V13_NAME}' (id {cid}) from {cutoff.isoformat()}, tagged {n} appointment(s)", flush=True)


# ── Campaign metrics ──────────────────────────────────────────────────────────

def _minutes(call_length: str | None) -> float | None:
    """'32 min' / '45 Min' / '25' / '1h 5m' -> minutes."""
    if not call_length:
        return None
    s = call_length.lower()
    h = re.search(r"(\d+(?:\.\d+)?)\s*h", s)
    m = re.search(r"(\d+(?:\.\d+)?)\s*m", s)
    if h or m:
        total = (float(h.group(1)) * 60 if h else 0) + (float(m.group(1)) if m else 0)
    else:
        n = re.search(r"\d+(?:\.\d+)?", s)
        if not n:
            return None
        total = float(n.group(0))
    return total if total > 0 else None


def _pct(n, d):
    return round(n / d * 100, 1) if d else 0.0


async def campaign_metrics(conn, campaign_id: int, since=None, until=None) -> dict:
    """One sales campaign's numbers: the cohort of first calls stamped with
    it, optionally narrowed to first calls held inside [since, until)."""
    from routers.appointments import follow_up_appointment_sql
    rows = await conn.fetch(
        f"""
        WITH base AS (
            SELECT ar.* FROM appointment_reminders ar
            LEFT JOIN contacts c ON c.id = ar.contact_id
            WHERE {SALES_ROW_SQL}
        ),
        firsts AS (SELECT ar.* FROM base ar WHERE NOT {follow_up_appointment_sql('ar')}),
        credit AS (
            SELECT x.id AS row_id, x.outcome_close, x.pricing, x.outcome_close_at, f.id AS first_id
            FROM base x
            JOIN LATERAL (
                SELECT f.id FROM firsts f
                WHERE f.id = x.id OR (f.contact_id = x.contact_id AND f.appointment_at <= x.created_at)
                ORDER BY (f.id = x.id) DESC, f.appointment_at DESC
                LIMIT 1
            ) f ON TRUE
        ),
        agg AS (
            SELECT first_id,
                   bool_or(outcome_close = 'closed') AS closed_any,
                   count(*) FILTER (WHERE row_id != first_id) AS follow_up_calls,
                   (array_agg(pricing ORDER BY (pricing IS NULL), outcome_close_at DESC NULLS LAST)
                        FILTER (WHERE outcome_close = 'closed'))[1] AS price
            FROM credit GROUP BY first_id
        )
        SELECT f.id, f.appointment_at, f.outcome_show, f.outcome_close, f.call_length,
               f.call_recording_url, a.closed_any, a.follow_up_calls, a.price
        FROM firsts f LEFT JOIN agg a ON a.first_id = f.id
        WHERE f.sales_campaign_id = $1
          AND ($2::timestamptz IS NULL OR f.appointment_at >= $2)
          AND ($3::timestamptz IS NULL OR f.appointment_at < $3)
        """,
        campaign_id, since, until,
    )
    now = datetime.now(timezone.utc)
    booked = len(rows)
    shows = sum(1 for r in rows if r["outcome_show"] == "show")
    no_shows = sum(1 for r in rows if r["outcome_show"] == "no_show")
    upcoming = sum(1 for r in rows if r["outcome_show"] is None and r["appointment_at"] + timedelta(hours=1) > now)
    awaiting = sum(1 for r in rows if r["outcome_show"] is None and r["appointment_at"] + timedelta(hours=1) <= now)
    closed = [r for r in rows if r["closed_any"]]
    closes = len(closed)
    closed_first = sum(1 for r in rows if r["outcome_close"] == "closed")
    two_call = [r for r in rows if r["outcome_close"] == "two_call"]
    two_call_won = sum(1 for r in two_call if r["closed_any"])
    two_call_open = sum(1 for r in two_call if not r["closed_any"])
    not_closed = sum(1 for r in rows if r["outcome_show"] == "show" and not r["closed_any"] and r["outcome_close"] != "two_call")
    revenue = float(sum(float(r["price"] or 0) for r in closed))
    lengths = [m for m in (_minutes(r["call_length"]) for r in rows if r["outcome_show"] == "show") if m]
    recorded = sum(1 for r in rows if r["outcome_show"] == "show" and r["call_recording_url"])
    return {
        "booked": booked,
        "upcoming": upcoming,
        "awaiting_outcome": awaiting,
        "shows": shows,
        "no_shows": no_shows,
        "show_rate": _pct(shows, shows + no_shows),
        "closes": closes,
        "close_rate": _pct(closes, shows),
        "closed_on_first_call": closed_first,
        "closed_on_follow_up": closes - closed_first,
        "two_call_closes": len(two_call),
        "two_call_rate": _pct(len(two_call), shows),
        "two_call_won": two_call_won,
        "two_call_open": two_call_open,
        "not_closed": not_closed,
        "booked_to_close": _pct(closes, booked),
        "total_revenue": revenue,
        "avg_deal_size": round(revenue / closes) if closes else 0,
        "avg_call_minutes": round(sum(lengths) / len(lengths)) if lengths else None,
        "calls_recorded": recorded,
    }


# ── Fireflies ─────────────────────────────────────────────────────────────────

_TRANSCRIPT_FIELDS = """
    id title date duration transcript_url organizer_email participants
    meeting_attendees { email displayName }
    summary { overview short_summary }
"""


async def _fireflies(query: str, variables: dict | None = None) -> dict:
    key = os.environ.get("FIREFLIES_API_KEY")
    if not key:
        raise RuntimeError("FIREFLIES_API_KEY not set")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            FIREFLIES_URL,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"query": query, "variables": variables or {}},
        )
    data = r.json()
    if r.status_code >= 400 or data.get("errors"):
        raise RuntimeError(f"Fireflies {r.status_code}: {str(data.get('errors') or data)[:300]}")
    return data.get("data") or {}


def _meeting_start(t: dict) -> datetime | None:
    d = t.get("date")
    if d is None:
        return None
    try:
        return datetime.fromtimestamp(float(d) / 1000, tz=timezone.utc)
    except (TypeError, ValueError):
        try:
            return datetime.fromisoformat(str(d).replace("Z", "+00:00"))
        except ValueError:
            return None


def _length_text(duration) -> str | None:
    """Fireflies' duration is minutes; guard against a seconds value."""
    try:
        mins = float(duration)
    except (TypeError, ValueError):
        return None
    if mins > 300:
        mins = mins / 60
    mins = round(mins)
    return f"{mins} min" if mins > 0 else None


async def _apply_transcript(conn, t: dict) -> int | None:
    """Matches one transcript to a discovery appointment and fills its call
    data. Returns the appointment id, or None when nothing matched."""
    tid = t.get("id")
    start = _meeting_start(t)
    if not tid or not start:
        return None
    if await conn.fetchval("SELECT id FROM appointment_reminders WHERE fireflies_transcript_id = $1", tid):
        return None
    emails = {e.lower() for e in (t.get("participants") or []) if e and "@" in e}
    emails |= {(a.get("email") or "").lower() for a in (t.get("meeting_attendees") or []) if a and a.get("email")}
    candidates = await conn.fetch(
        f"""
        SELECT ar.id, ar.appointment_at, lower(COALESCE(ar.prospect_email, '')) AS email, ar.prospect_name
        FROM appointment_reminders ar LEFT JOIN contacts c ON c.id = ar.contact_id
        WHERE {SALES_ROW_SQL} AND ar.fireflies_transcript_id IS NULL
          AND ar.appointment_at BETWEEN $1 AND $2
        ORDER BY abs(extract(epoch FROM ar.appointment_at - $3))
        """,
        start - timedelta(minutes=90), start + timedelta(minutes=90), start,
    )
    match = next((c for c in candidates if c["email"] and c["email"] in emails), None)
    if not match:
        near = [c for c in candidates if abs((c["appointment_at"] - start).total_seconds()) <= 40 * 60]
        if len(near) == 1:
            match = near[0]
        elif near:
            title = (t.get("title") or "").lower()
            by_name = [c for c in near if c["prospect_name"] and c["prospect_name"].lower().split()[-1] in title]
            match = by_name[0] if len(by_name) == 1 else None
    if not match:
        return None
    summary = t.get("summary") or {}
    await conn.execute(
        """
        UPDATE appointment_reminders SET
            fireflies_transcript_id = $2,
            call_recording_url = COALESCE(NULLIF(call_recording_url, ''), $3),
            call_length = COALESCE(NULLIF(call_length, ''), $4),
            call_summary = COALESCE($5, call_summary),
            call_data_source = 'fireflies'
        WHERE id = $1
        """,
        match["id"], tid, t.get("transcript_url"), _length_text(t.get("duration")),
        (summary.get("overview") or summary.get("short_summary") or None),
    )
    print(f"[sales] Fireflies transcript {tid} -> appointment {match['id']} ({match['prospect_name']})", flush=True)
    return match["id"]


async def sync_fireflies() -> dict:
    """Scheduled every 15 min: pull the most recent transcripts, match them."""
    if not os.environ.get("FIREFLIES_API_KEY"):
        return {"ok": False, "error": "FIREFLIES_API_KEY not set"}
    try:
        data = await _fireflies(f"query Recent {{ transcripts(limit: 25) {{ {_TRANSCRIPT_FIELDS} }} }}")
    except Exception as e:
        print(f"[sales] Fireflies sync failed: {e}", flush=True)
        return {"ok": False, "error": str(e)}
    matched = []
    pool = await get_pool()
    async with pool.acquire() as conn:
        for t in data.get("transcripts") or []:
            try:
                aid = await _apply_transcript(conn, t)
                if aid:
                    matched.append(aid)
            except Exception as e:
                print(f"[sales] Fireflies transcript {t.get('id')} failed: {e}", flush=True)
    return {"ok": True, "checked": len(data.get("transcripts") or []), "matched": matched}


async def sync_fireflies_meeting(meeting_id: str) -> int | None:
    data = await _fireflies(
        f"query One($id: String!) {{ transcript(id: $id) {{ {_TRANSCRIPT_FIELDS} }} }}", {"id": meeting_id},
    )
    t = data.get("transcript")
    if not t:
        return None
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await _apply_transcript(conn, t)


def verify_fireflies_signature(raw: bytes, signature: str | None) -> bool:
    """True when no secret is configured (the webhook only tells us which
    meeting to fetch, and the data itself comes from Fireflies' API with our
    key), else an HMAC-SHA256 hex match on the raw body."""
    secret = os.environ.get("FIREFLIES_WEBHOOK_SECRET")
    if not secret:
        return True
    if not signature:
        return False
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.split("=", 1)[-1].strip())


# ── Blueprint jobs (two-call close) ───────────────────────────────────────────

async def _todo_once(conn, text: str, description: str) -> None:
    if await conn.fetchval("SELECT 1 FROM todos WHERE NOT done AND text = $1", text):
        return
    await conn.execute(
        "INSERT INTO todos (text, description, due_date) VALUES ($1, $2, $3)",
        text, description, datetime.now(_ET).date(),
    )


async def _existing_blueprint(conn, contact_id: str) -> dict | None:
    return await conn.fetchrow(
        "SELECT slug FROM landing_pages WHERE contact_id = $1 AND slug LIKE '%-blueprint' "
        "ORDER BY created_at DESC LIMIT 1",
        contact_id,
    )


async def queue_blueprint(appointment: dict) -> dict | None:
    """Called when an appointment is marked two-call close. A prospect who
    already has a blueprint page reuses it; otherwise a job waits for the
    worker on Dylan's PC. Never more than one open job per prospect."""
    contact_id = appointment.get("contact_id")
    if not contact_id:
        print(f"[sales] two-call close on appointment {appointment.get('id')} has no contact; no blueprint", flush=True)
        return None
    pool = await get_pool()
    async with pool.acquire() as conn:
        if await conn.fetchval(
            "SELECT client_id IS NOT NULL AND NOT is_client_anchor FROM contacts WHERE id = $1", contact_id,
        ):
            return None   # a clinic's own patient, not one of Dylan's prospects
        open_job = await conn.fetchrow(
            "SELECT * FROM sales_blueprint_jobs WHERE contact_id = $1 AND status IN ('queued', 'running')", contact_id,
        )
        if open_job:
            return dict(open_job)
        existing = await _existing_blueprint(conn, contact_id)
        if existing:
            row = await conn.fetchrow(
                """INSERT INTO sales_blueprint_jobs (contact_id, source_appointment_id, status, slug, url, notes, finished_at)
                   VALUES ($1, $2, 'done', $3, $4, 'Reused the blueprint already built for this prospect.', now()) RETURNING *""",
                contact_id, appointment["id"], existing["slug"], f"{PAGES_BASE}/lp/{existing['slug']}",
            )
        else:
            row = await conn.fetchrow(
                "INSERT INTO sales_blueprint_jobs (contact_id, source_appointment_id) VALUES ($1, $2) RETURNING *",
                contact_id, appointment["id"],
            )
    print(f"[sales] blueprint job {row['id']} ({row['status']}) for contact {contact_id}", flush=True)
    return dict(row)


def _blueprint_prompt(job: dict, ctx: dict) -> str:
    lines = [
        "Build a Patient Acquisition Blueprint for this prospect by following the skill at",
        "design-agent/.claude/skills/patient-acquisition-blueprint/SKILL.md (the default Rise & Reframe",
        "growth format) end to end. Read that file first and follow it exactly.",
        "",
        "This run was started automatically: Dylan marked a two-call close on the prospect's first sales",
        "call, and the blueprint is for the second call. He approved the run (including the ~$2.40 fal",
        "spend for the AI ads) by marking that outcome. Work unattended: don't stop to ask questions or",
        "wait for approvals, make the best call from the skill and the prospect's real data, and keep going.",
        "Do steps 1-10 and 12-13. Skip step 11: never send anything to the prospect.",
        "If something blocks a step (e.g. fal out of credit, no social videos), work around it the way the",
        "skill describes when it can, otherwise stop and report the error.",
        "",
        "Prospect:",
        f"- contact_id: {ctx.get('contact_id')}",
        f"- owner: {ctx.get('owner') or ctx.get('prospect_name') or 'unknown'}",
        f"- business: {ctx.get('business') or 'unknown'}",
        f"- website: {ctx.get('website') or 'not on file (find it from the business name and city)'}",
        f"- location: {', '.join(x for x in (ctx.get('city'), ctx.get('state')) if x) or 'unknown'}",
        f"- phone: {ctx.get('phone') or ''}",
    ]
    if ctx.get("call_summary"):
        lines += ["", "Fireflies summary of the first call (use it to tailor the page, never quote it):", ctx["call_summary"]]
    if ctx.get("outcome_notes"):
        lines += ["", "Dylan's notes from the first call:", ctx["outcome_notes"]]
    lines += [
        "",
        "When the page is published, answer with the JSON schema: ok, slug, url (the live /lp/<slug> URL),",
        "notes (one or two lines Dylan should know before the call), error (empty when ok).",
    ]
    return "\n".join(lines)


BLUEPRINT_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "ok": {"type": "boolean"},
        "slug": {"type": "string"},
        "url": {"type": "string"},
        "notes": {"type": "string"},
        "error": {"type": "string"},
    },
    "required": ["ok"],
}


async def claim_next_job() -> dict | None:
    """Worker poll. Stale running jobs (worker died mid-run) go back to the
    queue once, then fail with a To-Do."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        stale = await conn.fetch(
            "SELECT * FROM sales_blueprint_jobs WHERE status = 'running' AND started_at < now() - $1::interval",
            BLUEPRINT_STALE_AFTER,
        )
        for s in stale:
            if s["attempts"] >= BLUEPRINT_MAX_ATTEMPTS:
                await _finish(conn, s["id"], {"ok": False, "error": "The blueprint run never reported back (worker stopped or timed out)."})
            else:
                await conn.execute("UPDATE sales_blueprint_jobs SET status = 'queued' WHERE id = $1", s["id"])
        job = await conn.fetchrow(
            """
            UPDATE sales_blueprint_jobs SET status = 'running', started_at = now(), attempts = attempts + 1
            WHERE id = (SELECT id FROM sales_blueprint_jobs WHERE status = 'queued' ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED)
            RETURNING *
            """
        )
        if not job:
            return None
        ctx = await conn.fetchrow(
            """
            SELECT c.id AS contact_id, c.owner, c.business, c.website, c.city, c.state, c.phone,
                   ar.prospect_name, ar.call_summary, ar.outcome_notes
            FROM sales_blueprint_jobs j
            LEFT JOIN contacts c ON c.id = j.contact_id
            LEFT JOIN appointment_reminders ar ON ar.id = j.source_appointment_id
            WHERE j.id = $1
            """,
            job["id"],
        )
    ctx = dict(ctx) if ctx else {}
    return {
        "id": job["id"],
        "label": ctx.get("business") or ctx.get("prospect_name") or ctx.get("contact_id"),
        "prompt": _blueprint_prompt(dict(job), ctx),
        "schema": BLUEPRINT_RESULT_SCHEMA,
    }


async def _finish(conn, job_id: int, result: dict) -> dict | None:
    job = await conn.fetchrow("SELECT * FROM sales_blueprint_jobs WHERE id = $1", job_id)
    if not job:
        return None
    name = await conn.fetchval(
        "SELECT COALESCE(NULLIF(c.business, ''), ar.prospect_name, 'prospect') FROM sales_blueprint_jobs j "
        "LEFT JOIN contacts c ON c.id = j.contact_id LEFT JOIN appointment_reminders ar ON ar.id = j.source_appointment_id "
        "WHERE j.id = $1", job_id,
    )
    slug = (result.get("slug") or "").strip() or None
    url = (result.get("url") or "").strip() or None
    if job["contact_id"] and not url:
        # The publish tool upserts the landing_pages row with the contact, so
        # the page is findable even if the run's own answer got lost.
        page = await _existing_blueprint(conn, job["contact_id"])
        if page and page["slug"]:
            slug = page["slug"]
            url = f"{PAGES_BASE}/lp/{slug}"
    if slug and not url:
        url = f"{PAGES_BASE}/lp/{slug}"
    ok = bool(result.get("ok")) and bool(url)
    row = await conn.fetchrow(
        """UPDATE sales_blueprint_jobs SET status = $2, slug = $3, url = $4, notes = $5, error = $6, finished_at = now()
           WHERE id = $1 RETURNING *""",
        job_id, "done" if ok else "failed", slug, url, (result.get("notes") or None),
        None if ok else ((result.get("error") or "").strip() or "No blueprint page was published."),
    )
    if ok:
        await _todo_once(conn, f"Blueprint ready for {name}'s second call",
                         f"{url}\n\nBuilt automatically after the two-call close. It's linked on their next appointment."
                         + (f"\n\n{result.get('notes')}" if result.get("notes") else ""))
    else:
        await _todo_once(conn, f"Blueprint for {name} failed",
                         f"{row['error']}\n\nRetry from Appointments (the prospect's next appointment), or run the "
                         "patient-acquisition-blueprint skill by hand.")
    return dict(row)


async def finish_job(job_id: int, result: dict) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await _finish(conn, job_id, result)


async def retry_job(job_id: int) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        job = await conn.fetchrow("SELECT * FROM sales_blueprint_jobs WHERE id = $1", job_id)
        if not job:
            return None
        if job["status"] in ("queued", "running"):
            return dict(job)
        row = await conn.fetchrow(
            """INSERT INTO sales_blueprint_jobs (contact_id, source_appointment_id) VALUES ($1, $2)
               ON CONFLICT DO NOTHING RETURNING *""",
            job["contact_id"], job["source_appointment_id"],
        )
        return dict(row) if row else dict(job)


# Appended to the Appointments list (appointments.list_appointments): the
# latest blueprint job from an EARLIER appointment with the same prospect,
# i.e. what to show on their next call. Alias `ar`.
BLUEPRINT_LATERAL_SQL = """
    LEFT JOIN LATERAL (
        SELECT j.id, j.status, j.url, j.error FROM sales_blueprint_jobs j
        JOIN appointment_reminders src ON src.id = j.source_appointment_id
        WHERE j.contact_id = ar.contact_id AND j.source_appointment_id != ar.id
          AND src.appointment_at < ar.appointment_at AND j.status != 'canceled'
        ORDER BY j.created_at DESC LIMIT 1
    ) bp ON TRUE
    LEFT JOIN LATERAL (
        SELECT j.id, j.status, j.url FROM sales_blueprint_jobs j
        WHERE j.source_appointment_id = ar.id AND j.status != 'canceled'
        ORDER BY j.created_at DESC LIMIT 1
    ) own_bp ON TRUE
"""
BLUEPRINT_SELECT_SQL = (
    "bp.id AS blueprint_job_id, bp.status AS blueprint_status, bp.url AS blueprint_url, bp.error AS blueprint_error, "
    "own_bp.status AS own_blueprint_status, own_bp.url AS own_blueprint_url"
)
