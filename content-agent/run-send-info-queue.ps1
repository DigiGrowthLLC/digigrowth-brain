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
