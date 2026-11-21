"""AI Client Success Manager routes (see client_success.py).

admin_router (mounted under /api with auth): settings, per-client report
settings, generate/send/list reports, answer client questions.
router (public, no auth): the report page /report/{slug} and its
questions/suggestions form, scoped by the unguessable slug.
"""
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

import client_success as csm
import csm_extras
from db import get_pool

router = APIRouter()
admin_router = APIRouter()


# ---------------------------------------------------------------- public

@router.get("/report/{slug}", response_class=HTMLResponse, include_in_schema=False)
async def view_report(slug: str, request: Request):
    pool = await get_pool()
    async with pool.acquire() as conn:
        page = await conn.fetchval("SELECT html FROM client_reports WHERE slug = $1", slug)
        if page is None:
            raise HTTPException(status_code=404, detail="Report not found")
        # Dylan opening the link from the OS shouldn't read as the client viewing it.
        try:
            from tracking_exclusion import is_excluded
            excluded = await is_excluded(request)
        except Exception:
            excluded = False
        if not excluded:
            await conn.execute("UPDATE client_reports SET view_count = view_count + 1, "
                               "viewed_at = coalesce(viewed_at, now()) WHERE slug = $1", slug)
    return HTMLResponse(page, headers={"X-Robots-Tag": "noindex"})


@router.post("/report/{slug}/feedback", include_in_schema=False)
async def report_feedback(slug: str, body: dict):
    if not await csm.add_feedback(slug, body or {}):
        raise HTTPException(status_code=404, detail="Report not found")
    return {"ok": True}


# "Appointments waiting on an outcome" on every report (Dylan, 2026-11-17):
# show/no-show and closed/not closed are entered by hand, so the report lets
# the clinic fill in the missing ones right there. Loaded live (the page HTML
# is stored once) and saved through the portal's own outcome handler, so the
# no-show sequence and every other side effect behave exactly as in the portal.

async def _report_client(conn, slug: str):
    r = await conn.fetchrow(
        """SELECT r.client_id, c.portal_token FROM client_reports r JOIN clients c ON c.id = r.client_id
           WHERE r.slug = $1""", slug)
    if not r:
        raise HTTPException(status_code=404, detail="Report not found")
    return r


@router.get("/report/{slug}/appointments", include_in_schema=False)
async def report_open_appointments(slug: str):
    from client_funnel import _not_test
    from timezone_lookup import clinic_timezone
    from zoneinfo import ZoneInfo
    pool = await get_pool()
    async with pool.acquire() as conn:
        rc = await _report_client(conn, slug)
        tz = ZoneInfo(await clinic_timezone(conn, rc["client_id"]))
        since = await conn.fetchval(
            "SELECT campaign_launched_at FROM client_marketing_config WHERE client_id = $1", rc["client_id"])
        rows = await conn.fetch(
            f"""SELECT ar.id, ar.appointment_at, ar.outcome_show, ar.outcome_close, ar.outcome_notes, c.owner
                FROM appointment_reminders ar JOIN contacts c ON c.id = ar.contact_id
                WHERE c.client_id = $1 AND NOT c.is_client_anchor AND {_not_test('c.phone')}
                  AND ar.status != 'canceled' AND ar.appointment_at <= now()
                  AND ar.appointment_at >= coalesce($2, now() - interval '90 days')
                  AND NOT EXISTS (SELECT 1 FROM bookings b WHERE b.appointment_id = ar.id AND b.excluded)
                  AND (ar.outcome_show IS NULL OR (ar.outcome_show = 'show' AND ar.outcome_close IS NULL))
                ORDER BY ar.appointment_at DESC LIMIT 60""",
            rc["client_id"], since)
    out = []
    for r in rows:
        at = r["appointment_at"].astimezone(tz)
        out.append({"id": r["id"], "name": (r["owner"] or "").strip() or "Patient",
                    "when": f"{at.strftime('%a %b')} {at.day}, {at.strftime('%I:%M %p').lstrip('0')}",
                    "outcome_show": r["outcome_show"], "outcome_close": r["outcome_close"],
                    "notes": r["outcome_notes"] or ""})
    return {"appointments": out}


@router.get("/report/{slug}/live", include_in_schema=False)
async def report_live_numbers(slug: str):
    """Current show-up / new-patient numbers for a report's period (Dylan,
    2026-11-19). The page is stored once, so its script calls this on load and
    after every outcome saved, keeping "New patients" and the journey's last
    two steps in step with what the clinic marks (here or in the portal).
    Same scope as the report was built with: a final covers the whole
    campaign ("all"), a weekly its own week."""
    from client_funnel import build_funnel
    pool = await get_pool()
    async with pool.acquire() as conn:
        r = await conn.fetchrow(
            "SELECT client_id, kind, period_start, period_end FROM client_reports WHERE slug = $1", slug)
    if not r:
        raise HTTPException(status_code=404, detail="Report not found")
    if r["kind"] == "final":
        f = await build_funnel(r["client_id"], "all")
    else:
        f = await build_funnel(r["client_id"], "week", window=(r["period_start"], r["period_end"]))
    k = f.get("kpis") or {}
    steps = [{"path": p.get("key"), "key": s.get("key"), "value": s.get("value"), "rate": s.get("rate"),
              "status": s.get("status"), "note": s.get("note")}
             for p in f.get("paths", []) for s in p.get("stages", []) if s.get("key") in ("showed", "patient")]
    return {"patients": k.get("patients"), "shows": k.get("shows"), "steps": steps}


@router.patch("/report/{slug}/appointments/{appointment_id}", include_in_schema=False)
async def report_set_outcome(slug: str, appointment_id: int, body: dict):
    from routers.client_portal import portal_update_appointment_outcome
    pool = await get_pool()
    async with pool.acquire() as conn:
        rc = await _report_client(conn, slug)
    allowed = {k: v for k, v in (body or {}).items() if k in ("outcome_show", "outcome_close", "outcome_notes")}
    row = await portal_update_appointment_outcome(rc["portal_token"], appointment_id, allowed)
    return {"ok": True, "outcome_show": row.get("outcome_show"), "outcome_close": row.get("outcome_close")}


# ---------------------------------------------------------------- admin

@admin_router.get("/client-success/settings")
async def get_settings():
    s = await csm.get_settings()
    s["category"] = s.pop("csm_category")
    return s


@admin_router.put("/client-success/settings")
async def put_settings(body: dict):
    if "category" in body:
        body["csm_category"] = body.pop("category")
    await csm.save_settings(body)
    return {"ok": True}


@admin_router.get("/client-success/clients")
async def list_clients():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT c.id, c.name, c.status, coalesce(c.is_test, false) AS is_test,
                      (SELECT count(*) FROM client_reports r WHERE r.client_id = c.id) AS report_count,
                      (SELECT max(created_at) FROM client_reports r WHERE r.client_id = c.id) AS last_report_at,
                      (SELECT count(*) FROM client_report_feedback f WHERE f.client_id = c.id AND f.answer IS NULL
                         AND f.message <> '') AS open_questions
               FROM clients c WHERE c.status <> 'archived' ORDER BY c.status = 'active' DESC, c.name""")
        health = await csm_extras.latest_health(conn)
        out = []
        for r in rows:
            win = await csm.campaign_window(conn, r["id"])
            out.append({**dict(r), "health": health.get(r["id"]),
                        "launched_at": win["launched_at"], "ends_at": win["ends_at"],
                        "length_days": win["length_days"], "goal": win["goal"], "goal_label": win["goal_label"],
                        "budget": win["budget"], "enabled": win["enabled"],
                        "state": win["state"], "week": win.get("week"), "days_elapsed": win.get("days_elapsed")})
    return out


@admin_router.get("/client-success/clients/{client_id}")
async def client_summary(client_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        win = await csm.campaign_window(conn, client_id)
        health = (await csm_extras.latest_health(conn)).get(client_id)
        counts = await conn.fetchrow(
            """SELECT
                 (SELECT count(*) FROM client_reports WHERE client_id = $1) AS reports,
                 (SELECT count(*) FROM client_reports WHERE client_id = $1 AND kind = 'final' AND sent_at IS NULL) AS finals_waiting,
                 (SELECT count(*) FROM client_report_feedback WHERE client_id = $1 AND answer IS NULL AND message <> '') AS open_questions,
                 (SELECT count(*) FROM client_checkins WHERE client_id = $1 AND status = 'draft') AS checkins_waiting""",
            client_id)
    return {**{k: v for k, v in win.items()}, "health": health, **dict(counts)}


@admin_router.patch("/client-success/clients/{client_id}")
async def update_client(client_id: int, body: dict):
    sets, args = [], [client_id]
    for key, cast in (("campaign_length_days", int), ("campaign_booking_goal", int), ("csm_reports_enabled", bool)):
        if key in body:
            v = body[key]
            args.append(None if v in (None, "") else cast(v))
            sets.append(f"{key} = ${len(args)}")
    if "campaign_goal_label" in body:
        args.append((body["campaign_goal_label"] or "").strip() or None)
        sets.append(f"campaign_goal_label = ${len(args)}")
    if "campaign_ended_at" in body:
        v = body["campaign_ended_at"]
        args.append(datetime.fromisoformat(v) if v else None)
        sets.append(f"campaign_ended_at = ${len(args)}")
    if not sets:
        return {"ok": True}
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO client_marketing_config (client_id) VALUES ($1) ON CONFLICT (client_id) DO NOTHING",
                           client_id)
        await conn.execute(f"UPDATE client_marketing_config SET {', '.join(sets)} WHERE client_id = $1", *args)
    return {"ok": True}


@admin_router.post("/client-success/clients/{client_id}/generate")
async def generate(client_id: int, body: dict):
    kind = body.get("kind", "weekly")
    pool = await get_pool()
    async with pool.acquire() as conn:
        win = await csm.campaign_window(conn, client_id)
    if not win["launched_at"]:
        raise HTTPException(status_code=400, detail="This client's campaign hasn't launched yet (no first ad spend).")
    r = await csm.create_report(client_id, kind, send=bool(body.get("send")))
    return _public_row(r)


def _public_row(r) -> dict:
    d = {k: v for k, v in dict(r).items() if k not in ("html", "data")}
    d["url"] = csm.report_url(d["slug"])
    return d


@admin_router.get("/client-success/reports")
async def list_reports(client_id: int | None = None, limit: int = 50):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT r.id, r.client_id, c.name AS client_name, r.kind, r.week_number, r.period_start, r.period_end,
                      r.slug, r.analysis, r.analysis_source, r.sent_at, r.sent_channels, r.send_error,
                      r.artifact_url, r.viewed_at, r.view_count, r.created_at
               FROM client_reports r JOIN clients c ON c.id = r.client_id
               WHERE ($1::int IS NULL OR r.client_id = $1) ORDER BY r.created_at DESC LIMIT $2""",
            client_id, min(limit, 200))
    return [_public_row(r) for r in rows]


@admin_router.get("/client-success/reports/{report_id}/html", response_class=HTMLResponse)
async def report_html(report_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        page = await conn.fetchval("SELECT html FROM client_reports WHERE id = $1", report_id)
    if page is None:
        raise HTTPException(status_code=404)
    return HTMLResponse(page)


@admin_router.post("/client-success/reports/{report_id}/send")
async def send(report_id: int):
    return await csm.send_report(report_id)


@admin_router.patch("/client-success/reports/{report_id}")
async def update_report(report_id: int, body: dict):
    pool = await get_pool()
    async with pool.acquire() as conn:
        if "artifact_url" in body:
            await conn.execute("UPDATE client_reports SET artifact_url = $2 WHERE id = $1",
                               report_id, body.get("artifact_url") or None)
        if body.get("html"):
            # Dylan's edits from the Artifact review (final reports) before approving.
            if await conn.fetchval("SELECT sent_at FROM client_reports WHERE id = $1", report_id):
                raise HTTPException(status_code=400, detail="Already sent to the client; build a new one instead.")
            await conn.execute("UPDATE client_reports SET html = $2 WHERE id = $1", report_id, body["html"])
        if body.get("mark_sent"):
            # Dylan sent the link himself (text/email by hand): record it as sent
            # without contacting the client, and close its approval/send To-Dos.
            r = await conn.fetchrow(
                "SELECT r.kind, c.name FROM client_reports r JOIN clients c ON c.id = r.client_id WHERE r.id = $1",
                report_id)
            if not r:
                raise HTTPException(status_code=404)
            await conn.execute(
                "UPDATE client_reports SET sent_at = COALESCE(sent_at, now()), sent_channels = $2, send_error = NULL "
                "WHERE id = $1", report_id, ["manual"])
            label = "weekly" if r["kind"] == "weekly" else "final"
            await conn.execute(
                "UPDATE todos SET done = TRUE WHERE NOT done AND text = ANY($1::text[])",
                [f"Approve {r['name']}'s final campaign report", f"Send {r['name']}'s {label} report by hand"])
            if r["kind"] == "final":
                import client_retention
                await client_retention.open_for_report(conn, report_id)
    return {"ok": True}


# ---- Retention: did the client stay after the campaign? (client_retention.py)

@admin_router.get("/client-success/retention")
async def retention_summary(days: int = 0, date: str | None = None):
    """Same period rules as the Analytics page: days=0 all time, 1 = today
    (Eastern), N = last N days, or a picked day. Filters by final report date."""
    import client_retention
    from routers.analytics import _since, _day_window
    window = _day_window(date)
    start, end = window or ((None, None) if days == 0 else (_since(days), None))
    return await client_retention.summary(start, end)


@admin_router.get("/client-success/clients/{client_id}/renewals")
async def client_renewals(client_id: int):
    import client_retention
    return {"renewals": await client_retention.for_client(client_id), "reasons": client_retention.REASONS}


@admin_router.patch("/client-success/renewals/{renewal_id}")
async def update_renewal(renewal_id: int, body: dict):
    import client_retention
    try:
        row = await client_retention.set_outcome(renewal_id, body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not row:
        raise HTTPException(status_code=404)
    return row


@admin_router.delete("/client-success/reports/{report_id}")
async def delete_report(report_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM client_reports WHERE id = $1", report_id)
    return {"ok": True}


@admin_router.get("/client-success/feedback")
async def list_feedback(limit: int = 100, client_id: int | None = None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT f.*, c.name AS client_name, r.kind AS report_kind, r.week_number, r.slug
               FROM client_report_feedback f JOIN clients c ON c.id = f.client_id
               LEFT JOIN client_reports r ON r.id = f.report_id
               WHERE ($2::int IS NULL OR f.client_id = $2)
               ORDER BY (f.answer IS NULL AND f.message <> '') DESC, f.created_at DESC LIMIT $1""",
            min(limit, 300), client_id)
    return [dict(r) for r in rows]


@admin_router.patch("/client-success/feedback/{feedback_id}")
async def answer(feedback_id: int, body: dict):
    text = (body.get("answer") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Answer is empty")
    return await csm.answer_feedback(feedback_id, text, bool(body.get("email")))


# ---------------------------------------------------------------- CSM part 2 (csm_extras.py)

@admin_router.post("/client-success/health/refresh")
async def refresh_health():
    await csm_extras.run_health()
    return {"ok": True}


@admin_router.get("/client-success/health/{client_id}")
async def health_history(client_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT score, band, reasons, computed_at FROM client_health WHERE client_id = $1 "
                                "ORDER BY computed_at DESC LIMIT 30", client_id)
    return [dict(r) for r in rows]


@admin_router.get("/client-success/lead-quality")
async def lead_quality(limit: int = 100, client_id: int | None = None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT q.id, q.client_id, c.name AS client_name, q.rating, q.note, q.created_at,
                      a.prospect_name, a.appointment_at, a.contact_id
               FROM lead_quality_ratings q JOIN clients c ON c.id = q.client_id
               LEFT JOIN appointment_reminders a ON a.id = q.appointment_id
               WHERE ($2::int IS NULL OR q.client_id = $2)
               ORDER BY q.created_at DESC LIMIT $1""", min(limit, 300), client_id)
        summary = await conn.fetch(
            """SELECT c.id AS client_id, c.name AS client_name,
                      count(*) FILTER (WHERE q.rating = 'good') AS good,
                      count(*) FILTER (WHERE q.rating = 'not_fit') AS not_fit
               FROM lead_quality_ratings q JOIN clients c ON c.id = q.client_id
               WHERE q.created_at > now() - interval '30 days' AND ($1::int IS NULL OR q.client_id = $1)
               GROUP BY c.id, c.name ORDER BY c.name""", client_id)
    return {"ratings": [dict(r) for r in rows], "summary": [dict(r) for r in summary]}


@admin_router.get("/client-success/milestones")
async def milestones(limit: int = 50, client_id: int | None = None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT m.client_id, c.name AS client_name, m.key, m.sent_at, m.created_at
               FROM client_milestones m JOIN clients c ON c.id = m.client_id
               WHERE m.key <> '_seeded' AND ($2::int IS NULL OR m.client_id = $2)
               ORDER BY m.created_at DESC LIMIT $1""", min(limit, 200), client_id)
    return [dict(r) for r in rows]


@admin_router.get("/client-success/checkins")
async def checkins(client_id: int | None = None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT k.client_id, c.name AS client_name, k.key, k.subject, k.body, k.status, k.sent_at, k.created_at,
                      coalesce(nullif(c.email, ''), anchor.email) AS to_email
               FROM client_checkins k JOIN clients c ON c.id = k.client_id
               LEFT JOIN contacts anchor ON anchor.client_id = c.id AND anchor.is_client_anchor
               WHERE k.status <> 'dismissed' AND ($1::int IS NULL OR k.client_id = $1)
               ORDER BY (k.status = 'draft') DESC, k.created_at DESC LIMIT 60""", client_id)
    return [dict(r) for r in rows]


@admin_router.post("/client-success/checkins/{client_id}/{key}/send")
async def send_checkin(client_id: int, key: str, body: dict):
    out = await csm_extras.send_checkin(client_id, key, body.get("subject") or "", body.get("body") or "")
    if not out.get("ok"):
        raise HTTPException(status_code=400, detail=out.get("error") or "Send failed")
    return out


@admin_router.patch("/client-success/checkins/{client_id}/{key}")
async def edit_checkin(client_id: int, key: str, body: dict):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE client_checkins SET subject = coalesce($3, subject), body = coalesce($4, body), "
            "status = CASE WHEN $5::text = 'dismissed' AND status = 'draft' THEN 'dismissed' ELSE status END "
            "WHERE client_id = $1 AND key = $2",
            client_id, key, body.get("subject"), body.get("body"), body.get("status"))
    return {"ok": True}
