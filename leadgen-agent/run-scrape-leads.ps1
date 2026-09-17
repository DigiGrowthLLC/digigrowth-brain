# Unattended runner for the scrape-leads skill, invoked by Windows Task Scheduler.
# Requires the machine to be on and logged in at the scheduled time (no server-side
# fallback — see leadgen-agent/CLAUDE.md for why).

$repoRoot = "C:\Users\dylan\Videos\Business\AI Agents\DigiGrowth-Brain"
$logDir   = Join-Path $repoRoot "leadgen-agent\logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }

$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$logFile   = Join-Path $logDir "scrape-leads_$timestamp.log"

Set-Location $repoRoot

$prompt = "Run the scrape-leads skill (leadgen-agent/.claude/skills/scrape-leads/SKILL.md) in full, resuming from wherever leadgen-agent/city_coverage.json's cursor (via 'python lib.py city-next') says to. Follow it exactly, including pushing any qualified leads to the DigiGrowth OS. This is an unattended run with nobody available to answer questions -- keep working through search terms and cities (crossing state boundaries as city-next hands them to you, without pausing to ask) until daily_lead_target is met or the 10-city cap is reached. Do not stop after just one city or one state."

# Watchdog: the skill has, three times now, ignored its own "never background this
# work" instruction and responded with some phrasing of "I'll wait for the
# background scrape to finish" -- under claude -p that kills the whole run the
# instant the response is produced, leaving a truncated log and a partial-progress
# cursor. Detect that pattern and retry once (city_coverage.json's cursor makes
# resume safe) before giving up.
#
# 2026-09-16: "i'll wait" alone missed the actual wording ("I'll just wait for the
# background task notification instead of polling") because of the word "just"
# between "i'll" and "wait". Loosened to "i'll\W+(\w+\W+){0,3}wait" so up to three
# extra words in between still match, plus a standalone catch for "instead of
# polling" (a phrase pattern distinct enough that it's unlikely to appear in a
# legitimate full run report).
$backgroundingPattern = "waiting on the background|i'll\W+(\w+\W+){0,3}wait|i will\W+(\w+\W+){0,3}wait|will resume (once|when)|check back on the background|kicked this off and will check back|instead of polling"
$maxAttempts = 2

for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
    if ($attempt -gt 1) {
        Add-Content -Path $logFile -Value "`n--- RETRY ${attempt}: previous attempt appears to have backgrounded the scrape and died early. Resuming from city_coverage.json cursor. ---`n"
    }

    & claude -p $prompt --dangerously-skip-permissions *>> $logFile

    $logContent = Get-Content -Path $logFile -Raw -ErrorAction SilentlyContinue
    if ($logContent -notmatch $backgroundingPattern) {
        break
    }
}

# Keep only the 30 most recent log files
Get-ChildItem $logDir -Filter "scrape-leads_*.log" | Sort-Object LastWriteTime -Descending | Select-Object -Skip 30 | Remove-Item -Force
