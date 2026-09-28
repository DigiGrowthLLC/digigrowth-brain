# Run this once, manually, in a PowerShell window to start the SMS setter worker
# every time you log in. (Claude Code's safety classifier blocks it from
# registering scheduled tasks itself, so this has to be run by hand.)
#
# The worker only runs while you're logged in and the machine is awake —
# that's the point: no drafting or auto-sending while your computer is off.
# To stop it for the day: Task Manager -> end "pythonw.exe", or flip the
# Inbox's setter switch to OFF (the worker keeps polling but does nothing).

$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument '"C:\Users\dylan\Videos\Business\AI Agents\DigiGrowth-Brain\apptset-agent\run-sms-setter-hidden.vbs"'
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
# No execution time limit (it's a long-running loop); restart it if it crashes.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -Hidden `
    -ExecutionTimeLimit (New-TimeSpan -Seconds 0) `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5) `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "DigiGrowth-SMSSetter" -Action $action -Trigger $trigger -Settings $settings -Description "SMS setter worker: drafts/sends cold SMS replies via Claude Code on the Claude subscription. Runs only while logged in." -Force
Start-ScheduledTask -TaskName "DigiGrowth-SMSSetter"
Get-ScheduledTask -TaskName "DigiGrowth-SMSSetter" | Select-Object TaskName, State
