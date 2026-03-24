#Requires -Version 5.1
<#
.SYNOPSIS
    MediaRiver Uninstaller
.DESCRIPTION
    Stops the running MediaRiver tray process, removes the scheduled startup
    task, removes the Start Menu shortcut, and optionally deletes the
    installation directory and user config/data.
#>

Write-Host ""
Write-Host "MediaRiver Uninstaller" -ForegroundColor Cyan
Write-Host ""

# ---------------------------------------------------------------------------
# Stop running instance
# ---------------------------------------------------------------------------
$trayProcess = Get-Process -Name "pythonw" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*tray.py*" }
if ($trayProcess) {
    Stop-Process $trayProcess -Force
    Write-Host "Stopped running MediaRiver instance"
}

# ---------------------------------------------------------------------------
# Remove scheduled task
# ---------------------------------------------------------------------------
try {
    Unregister-ScheduledTask -TaskName "MediaRiver" -Confirm:$false -ErrorAction Stop
    Write-Host "Removed startup task"
} catch {
    Write-Host "No startup task found (already removed)"
}

# ---------------------------------------------------------------------------
# Remove Start Menu shortcut
# ---------------------------------------------------------------------------
$shortcutPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\MediaRiver.lnk"
if (Test-Path $shortcutPath) {
    Remove-Item $shortcutPath
    Write-Host "Removed Start Menu shortcut"
}

# ---------------------------------------------------------------------------
# Ask about app directory
# ---------------------------------------------------------------------------
$installPath = Read-Host "Install path to remove (default: C:\mediariver, press Enter to skip)"
if ($installPath -and (Test-Path $installPath)) {
    $confirm = Read-Host "Remove $installPath? (y/n)"
    if ($confirm -eq "y") {
        Remove-Item $installPath -Recurse -Force
        Write-Host "Removed $installPath"
    }
}

# ---------------------------------------------------------------------------
# Ask about config/data
# ---------------------------------------------------------------------------
$configDir = Join-Path $env:USERPROFILE ".mediariver"
if (Test-Path $configDir) {
    $confirm = Read-Host "Remove config and data at $configDir? (y/n)"
    if ($confirm -eq "y") {
        Remove-Item $configDir -Recurse -Force
        Write-Host "Removed $configDir"
    }
}

Write-Host ""
Write-Host "MediaRiver uninstalled." -ForegroundColor Green
