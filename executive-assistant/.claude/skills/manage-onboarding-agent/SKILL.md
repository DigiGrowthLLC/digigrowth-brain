# Manage Onboarding Agent

Kicks off new-client onboarding — a welcome email with next steps and the Onboarding Call booking link — the moment a rep marks a discovery call "Closed" (won) in the dialer. First piece of a broader onboarding pipeline Dylan plans to keep building out (a client-facing dashboard, contracts, kickoff docs, etc.).

**Agent location:** onboarding-agent/ (digigrowth-brain repo)

---

## File Map

| File | What it controls |
|---|---|
| `dashboard/backend/onboarding_sequence.py` | Welcome email default copy, `dialer_settings` template lookup, the `send_kickoff()` send logic |
| `dashboard/backend/routers/appointments.py` | The trigger — PATCH handler fires `send_kickoff()` when `outcome_close` becomes `"closed"` |
| `dashboard/backend/routers/dialer.py` | GET/PUT `/api/dialer/onboarding-template` — reads/writes editable copy |
| `dashboard/backend/integrations.py` | `ONBOARDING_CALENDLY_URL` — static placeholder link, must be filled in by Dylan |
| `dashboard/frontend/src/panels/SOPsPanel.jsx` | `OnboardingKickoffEditor` — Business Resources → Outreach Templates → Onboarding Kickoff |

---

## Run Commands

Not invoked manually — this fires automatically inside the dashboard backend whenever a rep marks an appointment "Closed." Nothing to run.

---

## Common Tasks

- **Edit the welcome email copy**: Dashboard → Business Resources → Outreach Templates → Onboarding Kickoff. No redeploy needed — saved to `dialer_settings`.
- **Fill in the booking link once it exists**: `ONBOARDING_CALENDLY_URL` is a hardcoded constant in `dashboard/backend/integrations.py`, not dashboard-editable — requires editing the file and redeploying (same as `CALENDLY_URL`). Tell the EA the URL and it will make the edit + trigger/confirm a Railway redeploy.
- **Check whether the welcome email sent for a given appointment**: query `appointment_reminders.onboarding_kickoff_sent_at` (non-null once sent/attempted) and `outcome_close_at` (when it was marked Closed) for that row.
- **Extend the agent** (client dashboard, contracts, kickoff docs, etc.): new logic should live as additional functions in `onboarding_sequence.py` or new modules under `onboarding-agent/`, triggered from the same `appointments.py` hook point or a new one — ask Dylan for the specific next trigger/action before building.

---

## Current Standing Directives

*Dylan updates this section to give ongoing orders to the EA about this agent.*

- Fires on every appointment marked "Closed" — no scoping/filtering by rep, deal size, etc.
- v1 is email-only (no SMS, no intake form) — Dylan explicitly scoped this down from an earlier draft that included both; don't add them back without him asking.

---

## Notes

- Single immediate email, not a multi-day drip — no scheduler polling involved.
- `ONBOARDING_CALENDLY_URL` ships blank; the send is skipped (logged, not crashed) until Dylan fills it in. Appointments closed before that point do not get a retroactive send — his actual first "Closed" close may need the welcome email sent manually if it happens before the link is filled in.
- No client-facing dashboard exists yet — Dylan hasn't designed it. Don't build one proactively; wait for him to scope it.
