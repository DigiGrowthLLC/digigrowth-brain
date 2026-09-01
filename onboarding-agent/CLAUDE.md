# Onboarding Agent

Kicks off new-client onboarding the moment a rep marks a discovery call "Closed" (won) in the dialer — sends the client a welcome email with next steps and the Onboarding Call booking link. First piece of a broader onboarding pipeline Dylan plans to expand (a client-facing dashboard, contracts, kickoff docs, etc.).

**Managed by:** Dylan's Executive Assistant — see `.claude/skills/manage-onboarding-agent/SKILL.md` in the `digigrowth-brain` repo
**Run via:** Not a standalone process — logic lives in the dashboard backend and fires automatically. No manual invocation needed; editable copy is managed from the dashboard UI (Business Resources → Outreach Templates → Onboarding Kickoff).

## File Roles

| File | Purpose |
|---|---|
| `dashboard/backend/onboarding_sequence.py` | Welcome email default copy, `dialer_settings` template lookup, `send_kickoff()` |
| `dashboard/backend/routers/appointments.py` | PATCH `/appointment-reminders/{id}` — fires `send_kickoff()` when `outcome_close` transitions to `"closed"` |
| `dashboard/backend/routers/dialer.py` | GET/PUT `/dialer/onboarding-template` — editable copy endpoints |
| `dashboard/backend/integrations.py` | `ONBOARDING_CALENDLY_URL` — placeholder constant, Dylan fills this in once the 1-hour Onboarding Call event type exists |
| `dashboard/frontend/src/panels/SOPsPanel.jsx` | `OnboardingKickoffEditor` — dashboard UI for editing the welcome email copy |

## Security

No credentials live in this directory. Gmail auth is handled by the shared dashboard backend (`integrations.py`) — nothing here to keep out of commits.

## Future Scope

Not built yet, but this is where it'll live as Dylan grows the agent:
- Client-facing dashboard (campaign stats, onboarding progress) — not designed yet.
- Contracts, kickoff docs, intake form.
