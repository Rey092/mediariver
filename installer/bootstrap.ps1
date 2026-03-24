#Requires -Version 5.1
<#
.SYNOPSIS
    MediaRiver Desktop Installer
.DESCRIPTION
    Installs MediaRiver Desktop, sets up a Python virtual environment,
    registers a startup task, and creates a Start Menu shortcut.
.EXAMPLE
    irm https://raw.githubusercontent.com/Rey092/mediariver/main/installer/bootstrap.ps1 | iex
#>

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "==============================" -ForegroundColor Cyan
Write-Host "    MediaRiver Installer      " -ForegroundColor Cyan
Write-Host "==============================" -ForegroundColor Cyan
Write-Host ""

# ---------------------------------------------------------------------------
# Helper: check if winget is available
# ---------------------------------------------------------------------------
function Test-Winget {
    return $null -ne (Get-Command winget -ErrorAction SilentlyContinue)
}

# ---------------------------------------------------------------------------
# Step 1: Check Python 3.12+
# ---------------------------------------------------------------------------
Write-Host "[1/8] Checking Python..." -ForegroundColor Yellow

$pythonOk = $false
try {
    $pyVersion = & python --version 2>&1
    if ($pyVersion -match "Python (\d+)\.(\d+)") {
        $major = [int]$Matches[1]
        $minor = [int]$Matches[2]
        if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 12)) {
            Write-Host "    Found $pyVersion" -ForegroundColor Green
            $pythonOk = $true
        } else {
            Write-Host "    Found $pyVersion but 3.12+ is required." -ForegroundColor Yellow
        }
    }
} catch {
    Write-Host "    Python not found." -ForegroundColor Yellow
}

if (-not $pythonOk) {
    Write-Host "    Attempting to install Python 3.12 via winget..." -ForegroundColor Yellow
    if (Test-Winget) {
        try {
            winget install Python.Python.3.12 --accept-source-agreements --accept-package-agreements
            Write-Host "    Python 3.12 installed. Refreshing PATH..." -ForegroundColor Green
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                        [System.Environment]::GetEnvironmentVariable("Path", "User")
        } catch {
            Write-Host "ERROR: Failed to install Python via winget: $_" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "ERROR: winget is not available. Please install Python 3.12+ from https://python.org" -ForegroundColor Red
        exit 1
    }
}

# ---------------------------------------------------------------------------
# Step 2: Check Git
# ---------------------------------------------------------------------------
Write-Host "[2/8] Checking Git..." -ForegroundColor Yellow

$gitOk = $false
try {
    $gitVersion = & git --version 2>&1
    Write-Host "    Found $gitVersion" -ForegroundColor Green
    $gitOk = $true
} catch {
    Write-Host "    Git not found." -ForegroundColor Yellow
}

if (-not $gitOk) {
    Write-Host "    Attempting to install Git via winget..." -ForegroundColor Yellow
    if (Test-Winget) {
        try {
            winget install Git.Git --accept-source-agreements --accept-package-agreements
            Write-Host "    Git installed. Refreshing PATH..." -ForegroundColor Green
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                        [System.Environment]::GetEnvironmentVariable("Path", "User")
        } catch {
            Write-Host "ERROR: Failed to install Git via winget: $_" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "ERROR: winget is not available. Please install Git from https://git-scm.com" -ForegroundColor Red
        exit 1
    }
}

# ---------------------------------------------------------------------------
# Step 3: Choose install path
# ---------------------------------------------------------------------------
Write-Host "[3/8] Choosing install path..." -ForegroundColor Yellow

$inputPath = Read-Host "Install path (default: C:\mediariver)"
if ([string]::IsNullOrWhiteSpace($inputPath)) {
    $installPath = "C:\mediariver"
} else {
    $installPath = $inputPath.Trim()
}
Write-Host "    Install path: $installPath" -ForegroundColor Green

# ---------------------------------------------------------------------------
# Step 4: Clone or pull repository
# ---------------------------------------------------------------------------
Write-Host "[4/8] Fetching MediaRiver source..." -ForegroundColor Yellow

if (Test-Path "$installPath\pyproject.toml") {
    Write-Host "    Directory already exists - running git pull..." -ForegroundColor Yellow
    & git -C $installPath pull origin main
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: git pull failed" -ForegroundColor Red
        exit 1
    }
} else {
    if (Test-Path $installPath) {
        Remove-Item $installPath -Recurse -Force
    }
    & git clone https://github.com/Rey092/mediariver.git $installPath
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: git clone failed" -ForegroundColor Red
        exit 1
    }
}

if (-not (Test-Path "$installPath\pyproject.toml")) {
    Write-Host "ERROR: Clone succeeded but pyproject.toml not found in $installPath" -ForegroundColor Red
    exit 1
}
Write-Host "    Source ready at $installPath" -ForegroundColor Green

# ---------------------------------------------------------------------------
# Step 5: Create virtual environment
# ---------------------------------------------------------------------------
Write-Host "[5/8] Creating virtual environment..." -ForegroundColor Yellow

try {
    & python -m venv "$installPath\.venv"
    Write-Host "    Virtual environment created." -ForegroundColor Green
} catch {
    Write-Host "ERROR: Failed to create virtual environment: $_" -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------------------------------
# Step 6: Install dependencies
# ---------------------------------------------------------------------------
Write-Host "[6/8] Installing dependencies..." -ForegroundColor Yellow

try {
    Push-Location $installPath
    & "$installPath\.venv\Scripts\python" -m pip install --upgrade pip --quiet
    & "$installPath\.venv\Scripts\pip" install "setuptools<81" --quiet
    & "$installPath\.venv\Scripts\pip" install -e ".[desktop]"
    Pop-Location
    Write-Host "    Dependencies installed." -ForegroundColor Green
} catch {
    Pop-Location
    Write-Host "ERROR: Failed to install dependencies: $_" -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------------------------------
# Step 7: Register Task Scheduler startup task
# ---------------------------------------------------------------------------
Write-Host "[7/8] Registering startup task..." -ForegroundColor Yellow

try {
    $action = New-ScheduledTaskAction `
        -Execute "$installPath\.venv\Scripts\pythonw.exe" `
        -Argument "$installPath\src\desktop\tray.py" `
        -WorkingDirectory $installPath

    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    $trigger.Delay = "PT30S"

    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -ExecutionTimeLimit 0

    Register-ScheduledTask `
        -TaskName "MediaRiver" `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Description "MediaRiver media pipeline" `
        -Force | Out-Null

    Write-Host "    Startup task registered (runs 30 s after logon)." -ForegroundColor Green
} catch {
    Write-Host "ERROR: Failed to register scheduled task: $_" -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------------------------------
# Step 8: Create Start Menu shortcut
# ---------------------------------------------------------------------------
Write-Host "[8/8] Creating Start Menu shortcut..." -ForegroundColor Yellow

try {
    $shell = New-Object -ComObject WScript.Shell
    $shortcutPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\MediaRiver.lnk"
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = "$installPath\.venv\Scripts\pythonw.exe"
    $shortcut.Arguments = "$installPath\src\desktop\tray.py"
    $shortcut.WorkingDirectory = $installPath
    $shortcut.Description = "MediaRiver Media Pipeline"
    $shortcut.Save()
    Write-Host "    Shortcut created at $shortcutPath" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Failed to create Start Menu shortcut: $_" -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------------------------------
# Launch tray app
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "Launching MediaRiver..." -ForegroundColor Yellow

try {
    Start-Process `
        "$installPath\.venv\Scripts\pythonw.exe" `
        -ArgumentList "$installPath\src\desktop\tray.py" `
        -WorkingDirectory $installPath
} catch {
    Write-Host "WARNING: Could not launch tray app automatically: $_" -ForegroundColor Yellow
    Write-Host "         You can start it manually from the Start Menu." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==============================" -ForegroundColor Green
Write-Host " MediaRiver installed!        " -ForegroundColor Green
Write-Host " The tray icon should appear  " -ForegroundColor Green
Write-Host " shortly.                     " -ForegroundColor Green
Write-Host "==============================" -ForegroundColor Green
Write-Host ""
