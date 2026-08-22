# Unattended runner for the scrape-leads skill, invoked by Windows Task Scheduler.
# Requires the machine to be on and logged in at the scheduled time (no server-side
# fallback — see leadgen-agent/CLAUDE.md for why).

$repoRoot = "C:\Users\dylan\Videos\Business\AI Agents\DigiGrowth-Brain"
$logDir   = Join-Path $repoRoot "leadgen-agent\logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }

$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$logFile   = Join-Path $logDir "scrape-leads_$timestamp.log"

Set-Location $repoRoot

$prompt = "Run the scrape-leads skill (leadgen-agent/.claude/skills/scrape-leads/SKILL.md) in full, resuming from the cursor in leadgen-agent/progress.json. Follow it exactly, including pushing any qualified leads to the DigiGrowth OS. This is an unattended run with nobody available to answer questions -- keep working through search terms and cities (crossing state boundaries within the skill's pre-approved city list as needed, without pausing to ask) until daily_lead_target is met or the 5-city cap is reached. Do not stop after just one city or one state."

& claude -p $prompt --dangerously-skip-permissions *>> $logFile

# Keep only the 30 most recent log files
Get-ChildItem $logDir -Filter "scrape-leads_*.log" | Sort-Object LastWriteTime -Descending | Select-Object -Skip 30 | Remove-Item -Force
