# Run this once, manually, in a PowerShell window to set up unattended leadgen runs.
# (Claude Code's auto-mode safety classifier blocks it from registering scheduled
# tasks itself, even with explicit approval, so this has to be run by hand.)

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument '-NoProfile -ExecutionPolicy Bypass -File "C:\Users\dylan\Videos\Business\AI Agents\DigiGrowth-Brain\leadgen-agent\run-scrape-leads.ps1"'
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At "6:00PM"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -ExecutionTimeLimit (New-TimeSpan -Hours 3)
Register-ScheduledTask -TaskName "DigiGrowth-ScrapeLeads" -Action $action -Trigger $trigger -Settings $settings -Description "Runs the leadgen-agent scrape-leads Claude Code skill (free pipeline, needs machine on)." -Force
Get-ScheduledTask -TaskName "DigiGrowth-ScrapeLeads" | Select-Object TaskName, State
