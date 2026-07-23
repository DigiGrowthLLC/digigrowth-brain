# DigiGrowth OS

Full-stack client acquisition platform. Stack: React + Vite frontend, FastAPI + asyncpg backend, PostgreSQL, deployed on Railway via Docker.

## Directory Structure

- `dashboard/frontend/src/panels/` — React panel components (one per nav tab)
- `dashboard/backend/routers/` — FastAPI routers (one per feature area)
- `dashboard/backend/main.py` — app entry, router registration, HTTPBasic auth
- `dashboard/backend/db.py` — asyncpg pool + schema creation
- `dashboard/backend/agents_registry.json` — agent metadata (id, name, root_dir, color)
- `dashboard/backend/dialer_engine.py` + `dashboard/backend/routers/dialer.py` + `dashboard/backend/routers/dialer_webhooks.py` — Twilio parallel dialer (up to 10 simultaneous calls), browser-based via `dashboard/frontend/src/panels/DialerPanel.jsx` and Twilio Voice JS SDK — no separate local script or ngrok needed
- `dashboard/Dockerfile` — multi-stage build: Node 20 Alpine (frontend) → Python 3.11-slim (backend + repo)
- `railway.toml` — build/deploy config at repo root (`dockerfilePath = "dashboard/Dockerfile"`)
- `executive-assistant/` — EA agent (calendar, email, priorities, daily briefing)
- `content-agent/` — content creation (social posts, ad copy, videos, scripts)
- `leadgen-agent/` — Google Maps scraper + lead qualifier
- `apptset-agent/` — SMS appointment setter + newsletter (legacy)
- `shared/github_sync.py` — shared utility: push file changes to GitHub (git CLI → GitHub REST API fallback)

## External Repos

- **Public marketing website** lives in a **separate** repo, not in `digigrowth-brain`: `github.com/dylangroenendijk-sys/digigrowth-website` (branch `master`), deployed on Vercel (project `digigrowth-website`), live at the custom domain `digigrowthllc.com` (the underlying `digigrowth-website.vercel.app` deployment URL still resolves too, via Vercel's default domain). React + Vite, inline-style components in `src/components/` + `src/pages/`, same dark navy/glassmorphism theme as the dashboard. Pushing to `master` auto-deploys to production via Vercel. `dashboard/frontend/src/panels/WebsitePanel.jsx` links to the Vercel dashboard and live site from within the internal app.

## Key Conventions

- **Auth**: HTTPBasic (`DASHBOARD_PASSWORD` env var) applied to all `/api` routes
- **SSE streaming**: always use `fetch()` + `ReadableStream` — never `EventSource` (can't POST with auth)
- **File persistence on Railway**: write to disk + call `github_push_file()` — Railway containers are ephemeral, `.git/` is absent, so git CLI fails; GitHub REST API is the only persistence path
- **Agent chat history**: stored in `agent_chats` table (JSONB `content` = full Anthropic content blocks to preserve tool_use/tool_result alternation)
- **Secrets**: all API keys and passwords (`ANTHROPIC_API_KEY`, `DASHBOARD_PASSWORD`, `DASHBOARD_URL`, `PLACES_API_KEY`, etc.) live in the shared `digigrowth` Doppler vault (project `digigrowth`, config `prd` for production), not in any local `.env` file. Fetch via `doppler secrets get <NAME> --project digigrowth --config prd --plain`. Railway pulls the same vault at deploy time.
- **NEVER touch**: `.env`, `credentials.json`, `settings.local.json`

## Frontend Patterns

- Theme: dark navy glassmorphism (`#090f26` base, `#3a7bd5` accent blue)
- Fonts: `Space Grotesk` (UI labels), `Share Tech Mono` (metadata/mono)
- CSS classes: `glass-card`, `glass-card-sm`, `stat-card`, `dg-input`, `btn btn-primary`, `btn btn-secondary`, `sec-label`, `dg-divider`
- All styles are inline React style objects — no CSS modules, no Tailwind
- Nav panels: exported default function in `src/panels/*.jsx`, registered in `App.jsx`

## Backend Patterns

- All routers imported in `main.py` and mounted at `/api` with `Depends(require_auth)`
- DB queries use `asyncpg` pool (`get_pool()` from `db.py`)
- File paths resolved with `pathlib.Path(__file__).parent...` — never hardcoded
- `BLOCKED_FILENAMES = {".env", "credentials.json", "settings.local.json"}` checked on every file op
- Path sandbox: `(root / rel).resolve()` then `.relative_to(root)` — raises 403 on traversal
