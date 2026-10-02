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

param([string]$Source = "scheduled")   # "manual" when launched by hand, so runs.json labels it correctly

$repoRoot    = "C:\Users\dylan\Videos\Business\AI Agents\DigiGrowth-Brain"
$leadgenDir  = Join-Path $repoRoot "leadgen-agent"
$logDir      = Join-Path $leadgenDir "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }

$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$logFile   = Join-Path $logDir "scrape-leads_$timestamp.log"

Set-Location $repoRoot

$mcpConfig = Join-Path $leadgenDir "mcp-playwright.json"

# Per-city intermediates (term extractions, prep/sites/leads JSON). Cleared per
# run instead of having the model spend turns deleting them.
$workDir = Join-Path $leadgenDir "work"
if (Test-Path $workDir) { Remove-Item -Path (Join-Path $workDir "*") -Recurse -Force -ErrorAction SilentlyContinue }
else { New-Item -ItemType Directory -Path $workDir | Out-Null }

$config = Get-Content (Join-Path $leadgenDir "config.json") -Raw | ConvertFrom-Json
if (-not $config.enabled) {
    Add-Content -Path $logFile -Value "leadgen disabled in config.json -- exiting."
    exit 0
}
# The lead target is per run (each scheduled run gets its own lead_target_per_run,
# regardless of manual runs earlier that day), tallied on disk by run_id so it
# survives the one-process-per-city restarts below.
$runJson = python (Join-Path $leadgenDir "lib.py") run-start $Source 2>$null
$run = $runJson | ConvertFrom-Json
$runId = $run.run_id
$leadTarget = $run.target
Add-Content -Path $logFile -Value "run_id: $runId (target: $leadTarget qualified leads this run)"

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

# claude prints "You've hit your session limit · resets 9:10pm (America/New_York)".
# The reset is in Eastern time, same as this machine's clock.
$sessionLimitPattern = "hit your (session|usage) limit"
$maxSessionLimitWaits = 3
$maxSessionLimitWaitHours = 4
$sessionLimitWaits = 0
$stopRun = $false

function Get-SessionResetTime([string]$text) {
    if ($text -notmatch "resets\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)") { return $null }
    $hour = [int]$Matches[1] % 12
    if ($Matches[3] -eq "pm") { $hour += 12 }
    $minute = if ($Matches[2]) { [int]$Matches[2] } else { 0 }
    $reset = (Get-Date).Date.AddHours($hour).AddMinutes($minute)
    if ($reset -lt (Get-Date).AddMinutes(-5)) { $reset = $reset.AddDays(1) }
    return $reset.AddMinutes(2)   # small buffer past the stated reset
}

# Decode claude's output as UTF-8 when capturing it, so arrows/dashes in its
# reports don't come out as mojibake in the log.
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$maxCitiesPerRun = if ($config.max_cities_per_run) { $config.max_cities_per_run } else { 10 }

$prompt = "Run the scrape-leads skill (leadgen-agent/.claude/skills/scrape-leads/SKILL.md) for exactly one city, resuming from wherever leadgen-agent/city_coverage.json's cursor (via 'python lib.py city-next') says to. Follow it exactly, including pushing any qualified leads to the DigiGrowth OS. This is an unattended run with nobody available to answer questions. Finish all 4 search terms for this one city (per the skill's step 2), then stop -- do not move on to a second city yourself, this wrapper script decides that between processes. This run's run_id is $runId -- do NOT call run-start; pass this run_id to every city-record-progress call and use it for run-tally."

for ($cityCount = 1; $cityCount -le $maxCitiesPerRun; $cityCount++) {
    $tallyJson = python (Join-Path $leadgenDir "lib.py") run-tally $runId 2>$null
    $tally = $tallyJson | ConvertFrom-Json
    if ($tally.qualified -ge $leadTarget) {
        Add-Content -Path $logFile -Value "`n--- lead_target_per_run ($leadTarget) met (this run's qualified: $($tally.qualified)) -- stopping before city $cityCount. ---`n"
        break
    }

    $nextJson = python (Join-Path $leadgenDir "lib.py") city-next 2>$null
    $next = $nextJson | ConvertFrom-Json
    if ($next.done) {
        Add-Content -Path $logFile -Value "`n--- city-next reports nothing due -- stopping. ---`n"
        break
    }

    Add-Content -Path $logFile -Value "`n=== City $cityCount`: $($next.city), $($next.state) (term_index=$($next.term_index)) ===`n"

    $attempt = 1
    while ($attempt -le $maxAttemptsPerCity) {
        if ($attempt -gt 1) {
            Add-Content -Path $logFile -Encoding UTF8 -Value "`n--- RETRY ${attempt}: previous attempt appears to have backgrounded the scrape and died early. Resuming from city_coverage.json cursor. ---`n"
        }

        # Capture this invocation's output and check it directly. The old version
        # appended with *>> (which PowerShell 5.1 writes as UTF-16, interleaving
        # null bytes into the UTF-8 log) and then re-read the log with
        # Get-Content -Tail -Raw, a parameter combo that throws -- so the
        # backgrounding watchdog above never actually fired.
        # --strict-mcp-config: load only Playwright, not Meta Ads / Notion / Gmail
        # etc., whose tool listings would otherwise ride along in every turn's context.
        $out = & claude -p $prompt --dangerously-skip-permissions --strict-mcp-config --mcp-config $mcpConfig 2>&1 | Out-String
        Add-Content -Path $logFile -Encoding UTF8 -Value $out

        # Subscription session limit: every later city would fail instantly too
        # (9/28 and 9/29 burned cities 5-10 this way). Wait for the reset the
        # message names and retry the same city -- the cursor makes resume safe.
        # Doesn't consume a backgrounding attempt.
        if ($out -match $sessionLimitPattern) {
            $waitUntil = Get-SessionResetTime $out
            if ($sessionLimitWaits -ge $maxSessionLimitWaits -or -not $waitUntil -or ($waitUntil - (Get-Date)).TotalHours -gt $maxSessionLimitWaitHours) {
                Add-Content -Path $logFile -Encoding UTF8 -Value "`n--- Session limit hit and reset is unparseable, more than $maxSessionLimitWaitHours h away, or already waited $sessionLimitWaits time(s) -- stopping run. ---`n"
                $stopRun = $true
                break
            }
            $sessionLimitWaits++
            Add-Content -Path $logFile -Encoding UTF8 -Value "`n--- Session limit hit -- sleeping until $($waitUntil.ToString('HH:mm')) then retrying $($next.city), $($next.state). ---`n"
            Start-Sleep -Seconds ([math]::Max(0, [int]($waitUntil - (Get-Date)).TotalSeconds))
            continue
        }

        if ($out -notmatch $backgroundingPattern) {
            break
        }
        $attempt++
    }
    if ($stopRun) { break }
}

# Keep only the 30 most recent log files
Get-ChildItem $logDir -Filter "scrape-leads_*.log" | Sort-Object LastWriteTime -Descending | Select-Object -Skip 30 | Remove-Item -Force
