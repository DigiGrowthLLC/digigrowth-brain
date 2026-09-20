# Run this once, manually, in a PowerShell window to set up unattended leadgen runs.
# (Claude Code's auto-mode safety classifier blocks it from registering scheduled
# tasks itself, even with explicit approval, so this has to be run by hand.)

# Launched via wscript.exe + run-scrape-leads-hidden.vbs, not powershell.exe
# directly -- the task's own Hidden setting only hides it from Task
# Scheduler's list view, it does NOT suppress the console window a directly-
# launched powershell.exe (and the claude.exe it spawns) would pop on every
# run. WScript.Shell.Run's hidden window style is what actually prevents any
# window from appearing.
$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument '"C:\Users\dylan\Videos\Business\AI Agents\DigiGrowth-Brain\leadgen-agent\run-scrape-leads-hidden.vbs"'
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At "6:00PM"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -Hidden -ExecutionTimeLimit (New-TimeSpan -Hours 3)
Register-ScheduledTask -TaskName "DigiGrowth-ScrapeLeads" -Action $action -Trigger $trigger -Settings $settings -Description "Runs the leadgen-agent scrape-leads Claude Code skill (free pipeline, needs machine on)." -Force
Get-ScheduledTask -TaskName "DigiGrowth-ScrapeLeads" | Select-Object TaskName, State
