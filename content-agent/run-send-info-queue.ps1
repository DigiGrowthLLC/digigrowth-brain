# Unattended runner for the outreach-video skill's Send Info Queue Mode,
# invoked by Windows Task Scheduler. Requires the machine to be on and
# logged in at the scheduled time (no server-side fallback -- the personalized
# video generation needs local Playwright/ffmpeg + the local headcam master
# clip, none of which exist on Railway; see
# dashboard/backend/send_info_queue.py's module docstring). Mirrors
# leadgen-agent/run-scrape-leads.ps1 exactly.

$repoRoot = "C:\Users\dylan\Videos\Business\AI Agents\DigiGrowth-Brain"
$logDir   = Join-Path $repoRoot "content-agent\logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }

$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$logFile   = Join-Path $logDir "send-info-queue_$timestamp.log"

Set-Location $repoRoot

# Pre-check: this task fires every 20 minutes around the clock, and the queue is
# empty most of the time -- launching a full `claude -p` process just to have it
# read the outreach-video skill and discover there's nothing to do burns tokens on
# every empty check. A plain HTTP GET (no Claude involved) answers that cheaply.
# If the check itself fails for any reason (Doppler, network, auth), fail open and
# run claude -p anyway -- a wasted invocation is a much smaller problem than
# silently never sending a video because the pre-check broke.
try {
    $dashboardUrl      = (doppler secrets get DASHBOARD_URL --project digigrowth --config prd --plain).Trim()
    $dashboardPassword = (doppler secrets get DASHBOARD_PASSWORD --project digigrowth --config prd --plain).Trim()
    $authHeader        = "Basic " + [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("dashboard:$dashboardPassword"))

    $pending = Invoke-RestMethod -Uri "$dashboardUrl/api/send-info-queue?status=pending" -Headers @{ Authorization = $authHeader } -Method Get -TimeoutSec 20

    if (@($pending).Count -eq 0) {
        Add-Content -Path $logFile -Value "Queue empty (pre-check) -- skipping claude -p launch."
        Get-ChildItem $logDir -Filter "send-info-queue_*.log" | Sort-Object LastWriteTime -Descending | Select-Object -Skip 30 | Remove-Item -Force
        exit 0
    }

    Add-Content -Path $logFile -Value "Pre-check found $(@($pending).Count) pending entr(y/ies) -- launching claude -p."
} catch {
    Add-Content -Path $logFile -Value "Pre-check failed ($($_.Exception.Message)) -- running claude -p anyway to be safe."
}

$prompt = "Run the outreach-video skill's Send Info Queue Mode (content-agent/.claude/skills/outreach-video/SKILL.md) in full. Process every pending entry from GET {DASHBOARD_URL}/api/send-info-queue, one at a time in the foreground, reporting each as it completes (sent or failed + why). This is an unattended run with nobody available to answer questions -- if the queue is empty, say so and stop; otherwise keep working through every pending entry without pausing to ask."

# Watchdog: same backgrounding-detection pattern as leadgen-agent's scraper --
# this repo's skills have, more than once, ignored their own "never
# background this work" instruction and responded with some phrasing of
# "I'll wait for the background task to finish", which under claude -p kills
# the whole run the instant the response is produced.
$backgroundingPattern = "waiting on the background|i'll\W+(\w+\W+){0,3}wait|i will\W+(\w+\W+){0,3}wait|will resume (once|when)|check back on the background|kicked this off and will check back|instead of polling"
$maxAttempts = 2

for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
    if ($attempt -gt 1) {
        Add-Content -Path $logFile -Value "`n--- RETRY ${attempt}: previous attempt appears to have backgrounded the run and died early. Re-running -- already-completed queue entries are done, not resent, so this is safe. ---`n"
    }

    & claude -p $prompt --dangerously-skip-permissions *>> $logFile

    $logContent = Get-Content -Path $logFile -Raw -ErrorAction SilentlyContinue
    if ($logContent -notmatch $backgroundingPattern) {
        break
    }
}

# Keep only the 30 most recent log files
Get-ChildItem $logDir -Filter "send-info-queue_*.log" | Sort-Object LastWriteTime -Descending | Select-Object -Skip 30 | Remove-Item -Force
