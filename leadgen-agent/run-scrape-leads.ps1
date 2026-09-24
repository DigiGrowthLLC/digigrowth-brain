# Unattended runner for the scrape-leads skill, invoked by Windows Task Scheduler.
# Requires the machine to be on and logged in at the scheduled time (no server-side
# fallback — see leadgen-agent/CLAUDE.md for why).
#
# One `claude -p` process per city, looped here, instead of one process asked to
# cover up to 10 cities itself. A single session that tried to carry all 10 cities'
# browser snapshots and website text in one growing context would run out of tokens
# before finishing some nights -- restarting a fresh process per city resets the
# context budget each time, since city_coverage.json/scraped_ids.json already carry
# all the state that matters across processes.

$repoRoot    = "C:\Users\dylan\Videos\Business\AI Agents\DigiGrowth-Brain"
$leadgenDir  = Join-Path $repoRoot "leadgen-agent"
$logDir      = Join-Path $leadgenDir "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }

$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$logFile   = Join-Path $logDir "scrape-leads_$timestamp.log"

Set-Location $repoRoot

$config = Get-Content (Join-Path $leadgenDir "config.json") -Raw | ConvertFrom-Json
if (-not $config.enabled) {
    Add-Content -Path $logFile -Value "leadgen disabled in config.json -- exiting."
    exit 0
}
$dailyLeadTarget = $config.daily_lead_target

# Watchdog: the skill has, three times now, ignored its own "never background this
# work" instruction and responded with some phrasing of "I'll wait for the
# background scrape to finish" -- under claude -p that kills the whole run the
# instant the response is produced, leaving a truncated log and a partial-progress
# cursor. Detect that pattern and retry once per city (city_coverage.json's cursor
# makes resume safe) before moving on.
#
# 2026-09-16: "i'll wait" alone missed the actual wording ("I'll just wait for the
# background task notification instead of polling") because of the word "just"
# between "i'll" and "wait". Loosened to "i'll\W+(\w+\W+){0,3}wait" so up to three
# extra words in between still match, plus a standalone catch for "instead of
# polling" (a phrase pattern distinct enough that it's unlikely to appear in a
# legitimate full run report).
$backgroundingPattern = "waiting on the background|i'll\W+(\w+\W+){0,3}wait|i will\W+(\w+\W+){0,3}wait|will resume (once|when)|check back on the background|kicked this off and will check back|instead of polling"
$maxAttemptsPerCity = 2
$maxCitiesPerRun = if ($config.max_cities_per_run) { $config.max_cities_per_run } else { 10 }

$prompt = "Run the scrape-leads skill (leadgen-agent/.claude/skills/scrape-leads/SKILL.md) for exactly one city, resuming from wherever leadgen-agent/city_coverage.json's cursor (via 'python lib.py city-next') says to. Follow it exactly, including pushing any qualified leads to the DigiGrowth OS. This is an unattended run with nobody available to answer questions. Finish all 4 search terms for this one city (per the skill's step 2), then stop -- do not move on to a second city yourself, this wrapper script decides that between processes."

for ($cityCount = 1; $cityCount -le $maxCitiesPerRun; $cityCount++) {
    $tallyJson = python (Join-Path $leadgenDir "lib.py") daily-tally 2>$null
    $tally = $tallyJson | ConvertFrom-Json
    if ($tally.qualified -ge $dailyLeadTarget) {
        Add-Content -Path $logFile -Value "`n--- daily_lead_target ($dailyLeadTarget) already met (today's qualified: $($tally.qualified)) -- stopping before city $cityCount. ---`n"
        break
    }

    $nextJson = python (Join-Path $leadgenDir "lib.py") city-next 2>$null
    $next = $nextJson | ConvertFrom-Json
    if ($next.done) {
        Add-Content -Path $logFile -Value "`n--- city-next reports nothing due -- stopping. ---`n"
        break
    }

    Add-Content -Path $logFile -Value "`n=== City $cityCount`: $($next.city), $($next.state) (term_index=$($next.term_index)) ===`n"

    for ($attempt = 1; $attempt -le $maxAttemptsPerCity; $attempt++) {
        if ($attempt -gt 1) {
            Add-Content -Path $logFile -Value "`n--- RETRY ${attempt}: previous attempt appears to have backgrounded the scrape and died early. Resuming from city_coverage.json cursor. ---`n"
        }

        & claude -p $prompt --dangerously-skip-permissions *>> $logFile

        $logTail = Get-Content -Path $logFile -Tail 200 -ErrorAction SilentlyContinue -Raw
        if ($logTail -notmatch $backgroundingPattern) {
            break
        }
    }
}

# Keep only the 30 most recent log files
Get-ChildItem $logDir -Filter "scrape-leads_*.log" | Sort-Object LastWriteTime -Descending | Select-Object -Skip 30 | Remove-Item -Force
