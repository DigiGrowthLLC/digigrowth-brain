' Launches the SMS setter worker with no visible window (see sms_setter_worker.py).
' Run by the DigiGrowth-SMSSetter scheduled task at logon. doppler injects
' DASHBOARD_URL / DASHBOARD_PASSWORD; the worker strips ANTHROPIC_API_KEY before
' calling claude so drafting runs on the Claude subscription.
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = "C:\Users\dylan\Videos\Business\AI Agents\DigiGrowth-Brain"
shell.Run "cmd /c doppler run --project digigrowth --config prd -- ""C:\Python314\pythonw.exe"" ""C:\Users\dylan\Videos\Business\AI Agents\DigiGrowth-Brain\apptset-agent\sms_setter_worker.py""", 0, False
