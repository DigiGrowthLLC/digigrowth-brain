# New Machine Setup (laptop, second PC)

No secrets are stored in this repo. Every API key and password lives in the Doppler vault (project `digigrowth`, config `prd`), so a new machine only needs to log in to Doppler. Nothing secret gets copied by hand.

## 1. Install the tools

Install with `winget` or each tool's own installer. These are the versions on the main PC as of 2026-11-27:

| Tool | Version | Used for |
|---|---|---|
| Git | latest | the repo |
| GitHub CLI (`gh`) | 2.92 | pushes, PRs, deploy checks |
| Doppler CLI | 3.76 | every API key and password |
| Python | 3.14 | backend, agents, scripts |
| Node | 22 | dashboard frontend, Playwright MCP |
| Claude Code + the VS Code extension | 2.1.x | the agents, plus `claude -p` for the SMS/email setter |
| ffmpeg (if you'll do video work) | latest | the ad and video tools |

## 2. Log in to each service

```powershell
gh auth login                      # pick your DigiGrowthLLC GitHub account
doppler login                      # opens a browser; approve it in the DigiGrowth workplace
claude                             # sign in with the same Claude subscription
```

Clone the repo and point Doppler at it:

```powershell
git clone https://github.com/DigiGrowthLLC/digigrowth-brain.git DigiGrowth-Brain
cd DigiGrowth-Brain
doppler setup --project digigrowth --config prd
doppler secrets --only-names       # should list ANTHROPIC_API_KEY, DASHBOARD_PASSWORD, etc.
```

Doppler registers each login as a separate device, so a lost laptop can be revoked on its own without touching the main PC.

## 3. Install the Python and frontend packages

```powershell
pip install -r dashboard/backend/requirements.txt -r apptset-agent/requirements.txt -r leadgen-agent/requirements.txt
cd dashboard/frontend; npm install
```

## 4. Things that won't come over unless you move them

- **Uncommitted work.** Anything not committed and pushed exists only on the machine that made it. Push it first. Copy big videos over with OneDrive or Drive instead, because they bloat git.
- **Claude's memory.** It's stored outside the repo, in `%USERPROFILE%\.claude\projects\<path-of-repo>\memory\`. On the main PC that's `C:\Users\dylan\.claude\projects\c--Users-dylan-Videos-Business-AI-Agents-DigiGrowth-Brain\memory\`. Copy that folder to the new machine. The folder name is built from the repo's path, so either clone to the same path on the new machine or rename the folder to match the new path. Also copy `%USERPROFILE%\.claude\settings.json` if you've customized it.
- **MCP connectors.** Playwright works anywhere because `.mcp.json` is in the repo. Meta Ads and the claude.ai connectors (Gmail, Calendar, Drive, Notion) have to be signed in again with `/mcp` in Claude Code.
- **Claude in Chrome.** Install the extension in Chrome on the new machine.

## 5. Background tasks: run them on one machine only

The main PC runs these Windows scheduled tasks:

| Task | Script | State |
|---|---|---|
| `DigiGrowth-SMSSetter` | `apptset-agent/register-sms-setter-task.ps1` | on |
| `DigiGrowth-SendInfoQueue` | `content-agent/run-send-info-queue.ps1` | on |
| `DigiGrowth-ScrapeLeads` | `leadgen-agent/register-scheduled-task.ps1` | installed, turned off |

Don't register them on a second machine as well unless you're moving them for good. Two SMS setter workers would both pick up the same replies and blueprint jobs.

If you do move them, register them on the new machine and turn the old machine's tasks off. The setter only works while the machine running it is on, so a laptop that sleeps is a worse place for it than a desktop that stays on.

## 6. Quick test

```powershell
doppler run -- python -c "import os; print(bool(os.environ.get('ANTHROPIC_API_KEY')))"
```

If that prints `True`, the machine can read your keys from Doppler.
