# DigiGrowth Brain

Dylan Groenendijk's AI agent workspace for DigiGrowth — a solo AI client acquisition agency for independent service-based businesses.

## Structure

| Folder | Description |
|---|---|
| `dashboard/` | DigiGrowth OS — React + FastAPI web app (CRM, dialer, SMS, analytics, agent chat). Deployed on Railway. Dialer runs browser-based in-app via Twilio Voice JS SDK, no separate script. |
| `executive-assistant/` | Claude Code EA — calendar, email, priorities, daily briefing, agent oversight skills |
| `leadgen-agent/` | Scrapes Google Maps for mobile/in-home vet practices, qualifies leads with Claude, pushes into the OS CRM |
| `apptset-agent/` | SMS appointment setter + weekly newsletter |
| `content-agent/` | Content creation — social posts, ad copy, video/transcription |
| `shared/` | Shared utilities used across agents (e.g. `github_sync.py` for pushing file changes on Railway) |

The public marketing site lives in a **separate** repo (`digigrowth-website`, not in this workspace) — see `dashboard/frontend/src/panels/WebsitePanel.jsx` for the link.

## Quick Start

- **DigiGrowth OS** — `cd dashboard && cat Dockerfile` (deployed via Railway; see `railway.toml`)
- **Executive Assistant** — open `executive-assistant/` in Claude Code
- **Lead Gen** — `cd leadgen-agent && doppler run -- python run.py`
- **Parallel Dialer** — DialerPanel tab inside DigiGrowth OS (no separate script — Twilio config lives in `dashboard/backend/dialer_config.json` + the shared Doppler vault)
- **Appointment Setter** — `cd apptset-agent && doppler run -- python server.py`

Secrets for the standalone agents live in the shared `digigrowth` Doppler vault (configs `prd`, `prd_apptset`, `prd_dialer`) — not local `.env` files.
