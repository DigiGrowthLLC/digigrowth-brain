' Hidden-window launcher for run-send-info-queue.ps1, invoked by Windows Task
' Scheduler via wscript.exe instead of calling powershell.exe directly.
'
' Setting the scheduled task's "Hidden" property (Settings.Hidden) does NOT
' suppress the console window of a launched console app -- it only hides the
' task itself from Task Scheduler's default list view. powershell.exe (and the
' claude.exe console process it spawns) still pops a visible window every time
' the task fires -- every 20 minutes for this one. WScript.Shell.Run's
' window-style argument (0 = hidden) is what actually prevents the window from
' ever being created, and any console child process (claude.exe) inherits that
' same hidden console instead of opening its own.
Set objShell = CreateObject("WScript.Shell")
objShell.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -File ""C:\Users\dylan\Videos\Business\AI Agents\DigiGrowth-Brain\content-agent\run-send-info-queue.ps1""", 0, False
