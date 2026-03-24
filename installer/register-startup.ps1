$appDir = (Get-Item $PSScriptRoot\..\ ).FullName.TrimEnd('\')
$pythonw = "$appDir\.venv\Scripts\pythonw.exe"
$trayScript = "$appDir\src\desktop\tray.py"

if (-not (Test-Path $pythonw)) {
    Write-Host "ERROR: $pythonw not found. Run 'task install' first." -ForegroundColor Red
    exit 1
}

$action = New-ScheduledTaskAction -Execute $pythonw -Argument $trayScript -WorkingDirectory $appDir
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$trigger.Delay = "PT30S"
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit 0

Register-ScheduledTask -TaskName "MediaRiver" -Action $action -Trigger $trigger -Settings $settings -Description "MediaRiver media pipeline" -Force | Out-Null

Write-Host "Startup task registered (30s delay after logon)" -ForegroundColor Green
Write-Host "  Python: $pythonw" -ForegroundColor DarkGray
Write-Host "  Script: $trayScript" -ForegroundColor DarkGray
