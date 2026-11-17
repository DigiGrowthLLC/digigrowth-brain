---
name: client-success-reports
description: DigiGrowth's AI Client Success Manager. Use when Dylan asks to review/approve a client's final report, publish/see client campaign reports as Claude Artifacts, build or send a client's weekly or final report now, check which clients have open questions on their reports, or answer a client's report question. Triggers "client report(s)", "weekly report for <client>", "final report", "CSM", "client success".
---

# Client Success Reports (AI CSM)

The reports themselves are built and sent by the OS, not by this skill:
`dashboard/backend/client_success.py` runs every day at 10:00 ET. Mondays it
writes a **weekly report** for every active client in a live campaign; the
first run after a campaign ends it drafts the **final report**, which is NOT sent until Dylan approves it (it carries the "Your next campaign" renewal plan and the "Share your experience" testimonial ask). Each report is
a public page (`<pages domain>/report/<slug>`) emailed to the client (texting
is a separate switch, off by default) and listed in their portal. Settings,
per-client goal/length, previews, the reports list and client questions all
live in **Business Resources → Outreach Templates → Client Success Reports**.

This skill covers what the server can't do: the **Claude Artifact copy** of
each report for Dylan, plus on-demand runs from a Claude session.

## Calling the API

Never paste the dashboard password into a command. Always:

```bash
doppler run --project digigrowth --config prd -- bash -c \
  'curl -s -u "admin:$DASHBOARD_PASSWORD" "$DASHBOARD_URL/api/client-success/reports?limit=20"'
```

Endpoints (all under `/api`, auth required):
- `GET /client-success/clients`: campaign state, week, goal, length, open questions per client
- `GET /client-success/reports?client_id=&limit=`: reports (id, client_name, kind, week_number, url, artifact_url, sent_at, view_count, analysis)
- `GET /client-success/reports/{id}/html`: the report page's full HTML
- `PATCH /client-success/reports/{id}` `{"artifact_url": "..."}`: store the Artifact link (shows as ARTIFACT ↗ in the OS)
- `PATCH /client-success/reports/{id}` `{"html": "..."}`: replace an UNSENT report's page with Dylan's edits (refused once sent)
- `POST /client-success/clients/{id}/generate` `{"kind": "weekly"|"final", "send": false}`: build a preview (send=true sends it to the client: confirm with Dylan first)
- `POST /client-success/reports/{id}/send`: send a preview to the client (confirm first)
- `GET /client-success/feedback`: client questions/suggestions/ratings; `PATCH /client-success/feedback/{id}` `{"answer": "...", "email": true}` saves an answer and emails it

## Publish reports as Claude Artifacts

1. List reports with no `artifact_url` (default: the last 7 days; or the client Dylan named).
2. For each: save `GET /reports/{id}/html` into the session scratchpad as
   `<client-slug>-week-<n>.html` (or `-final.html`), using the Windows-style scratchpad path for any Python step.
3. Load the `artifact-design` skill once, then publish each file with the Artifact tool
   (icon `chart`, description "<Client> week N campaign report"). The page is already
   complete: publish it as is. Don't redesign it or change any number.
4. `PATCH` the report's `artifact_url` with the published link.
5. Reply with one line per report: client, week/final, the Artifact link, the client-facing link, opened yes/no.

The Artifact is Dylan's private copy. Clients get the public `/report/` link. Sharing an
Artifact with a client is Dylan's call: never do it for him.

## Review and approve a final report

Final reports wait for Dylan (a To-Do "Approve <client>'s final campaign report" appears).
1. Find unsent finals: `GET /client-success/reports` where `kind == "final"` and `sent_at` is null.
2. Publish each as an Artifact (steps above) and give Dylan the link. Point him to the
   "Your next campaign" and "Share your experience" sections in particular.
3. If he wants changes, edit the saved HTML (wording only, never numbers), `PATCH {"html": ...}`
   the report, and republish the same Artifact file path so the link stays the same.
4. Send ONLY when he says so in this session: `POST /client-success/reports/{id}/send`. Or
   he can press APPROVE & SEND in the OS (Reports view).

Onboarding check-ins are also approval-only. Their drafts live in the Onboarding Check-ins view
(`GET /client-success/checkins`). Send one only on his say-so: `POST /client-success/checkins/{client_id}/{key}/send`
with `{subject, body}`.

## Ground rules

- Never send a report or an answer to a client without Dylan saying so in this session (the
  scheduled auto-send is the only exception, and that's server-side).
- Numbers come only from the OS data. If something looks wrong (zero spend on a live
  campaign, Meta not connected), tell Dylan rather than publishing.
- Client-specific context lives in `media-buying-agent/clients/<slug>/client-context.md`.
