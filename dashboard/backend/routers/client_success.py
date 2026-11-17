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
    return {"ok": True}


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
                      a.prospect_name, a.appointment_at
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
