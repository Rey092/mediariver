$appDir = (Get-Item $PSScriptRoot\..\ ).FullName.TrimEnd('\')
$pythonw = "$appDir\.venv\Scripts\pythonw.exe"
$trayScript = "$appDir\src\desktop\tray.py"

if (-not (Test-Path $pythonw)) {
    Write-Host "ERROR: $pythonw not found. Run 'task install' first." -ForegroundColor Red
    exit 1
}

$shell = New-Object -ComObject WScript.Shell
$shortcutPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\MediaRiver.lnk"
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $pythonw
$shortcut.Arguments = $trayScript
$shortcut.WorkingDirectory = $appDir
$shortcut.Description = "MediaRiver Media Pipeline"
$shortcut.Save()

Write-Host "Start Menu shortcut created" -ForegroundColor Green
Write-Host "  Path: $shortcutPath" -ForegroundColor DarkGray
