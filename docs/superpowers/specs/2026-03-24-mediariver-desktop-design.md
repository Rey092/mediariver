# MediaRiver Desktop — Design Spec

## Overview

Windows desktop wrapper for MediaRiver. Tray icon + web UI for managing the media pipeline engine. Lives in the same repo as the engine — one `git pull` updates everything.

## Decisions Log

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Location | Same repo (`desktop/`) | Single git pull updates engine + desktop |
| Tray app | pystray | Lightweight, Python-native |
| UI | FastAPI + Jinja2 + HTMX | No JS build step, SSE for live logs, Python-only |
| Installer | Bootstrap .exe wrapping PowerShell | Minimal maintenance, easy to update |
| Auto-update | On start + manual button in UI | Predictable, no background polling |
| Startup | Task Scheduler with 30s delay | Reliable, supports delay, no registry hacks |

## Project Structure

```
desktop/
├── tray.py              # pystray tray icon, launches server + engine
├── server.py            # FastAPI web UI (localhost:9876)
├── updater.py           # git fetch/pull, version comparison
├── service.py           # manages mediariver engine subprocess
├── config.py            # reads/writes ~/.mediariver/config.json
├── templates/
│   ├── base.html        # layout: dark theme, sidebar nav, HTMX
│   ├── dashboard.html   # engine status, GPU info, uptime, stats
│   ├── files.html       # processed files table, filter by workflow/status
│   ├── workflows.html   # workflow list, validation, YAML viewer
│   ├── logs.html        # live log stream via SSE
│   └── settings.html    # paths, env vars, update button, restart
├── static/
│   ├── htmx.min.js
│   └── style.css
└── icon.ico

installer/
├── bootstrap.ps1        # PowerShell installer script
└── build_installer.py   # PyInstaller to create .exe from bootstrap runner
```

## Components

### Tray App (`tray.py`)

Runs as the main process. Uses pystray to show a tray icon.

**Menu items:**
- Open UI (also triggered by left-click) — opens `http://localhost:9876` in default browser
- Restart Server — restarts the engine subprocess
- Check for Updates — runs updater, shows notification
- Quit — stops engine, stops server, exits

**On start:**
1. Run updater check (git fetch, compare hashes, pull if behind)
2. Start FastAPI server (uvicorn) in a thread
3. Start mediariver engine subprocess
4. Show tray icon

### Web Server (`server.py`)

FastAPI app on `localhost:9876`. Jinja2 templates + HTMX for interactivity.

**Pages:**

| Route | Page | Content |
|-------|------|---------|
| `/` | Dashboard | Engine status (running/stopped), GPU detected (encoders list), uptime, files processed count by status |
| `/files` | Files | Table from `processed_files` DB. Columns: workflow, file, status, current step, error, timestamps. Filter by workflow/status. HTMX polling refresh. |
| `/workflows` | Workflows | List loaded workflow YAML files. Validation status (OK/error). Click to view YAML. |
| `/logs` | Logs | Live server log stream via SSE (Server-Sent Events). Auto-scroll. Filter by level. |
| `/settings` | Settings | Workflows dir path, work dir path, database URL, log level, env vars editor. Save writes to config.json. "Update" button (shows current vs remote version). "Restart Server" button. |

**API endpoints (used by HTMX):**

| Method | Route | Action |
|--------|-------|--------|
| GET | `/api/status` | Engine status JSON (running, uptime, gpu info) |
| GET | `/api/files` | Processed files list (paginated, filterable) |
| GET | `/api/logs/stream` | SSE endpoint for live logs |
| POST | `/api/server/restart` | Restart engine subprocess |
| POST | `/api/update` | Trigger git pull + pip install + restart |
| GET | `/api/update/check` | Check for updates (commits behind) |
| POST | `/api/settings` | Save config.json |

### Engine Service (`service.py`)

Manages the `mediariver run` subprocess.

```python
class EngineService:
    def start() -> None       # spawn subprocess with config
    def stop() -> None        # terminate gracefully (SIGTERM), force after 5s
    def restart() -> None     # stop + start
    def is_running() -> bool  # check subprocess alive
    def get_logs() -> list    # return captured log lines
    def stream_logs() -> AsyncGenerator  # yield log lines as they arrive
```

The subprocess runs: `python -m mediariver run --workflows-dir {config.workflows_dir} --database-url {config.database_url} --log-level {config.log_level}`

Env vars from `config.env` are injected into the subprocess environment.

Stdout/stderr are captured via pipes and stored in a ring buffer (last 10,000 lines) for the logs page.

### Updater (`updater.py`)

```python
class Updater:
    def check() -> UpdateStatus       # git fetch, compare HEAD vs origin/main
    def apply() -> None               # git pull, pip install -e ., restart
    def get_current_version() -> str  # git rev-parse --short HEAD
    def get_remote_version() -> str   # git rev-parse --short origin/main
```

`UpdateStatus`: `{ up_to_date: bool, commits_behind: int, current: str, remote: str }`

On tray app start: `check()` → if not up to date → `apply()` automatically.
"Update" button in UI: `check()` → show status → user clicks "Apply" → `apply()`.

### Config (`config.py`)

Reads/writes `~/.mediariver/config.json`:

```json
{
  "workflows_dir": "C:\\mediariver\\workflows",
  "work_dir": "C:\\mediariver\\work",
  "database_url": null,
  "log_level": "info",
  "port": 9876,
  "env": {
    "S3_BUCKET": "my-bucket",
    "S3_ENDPOINT": "http://localhost:9000",
    "S3_ACCESS_KEY": "minioadmin",
    "S3_SECRET_KEY": "minioadmin"
  }
}
```

Falls back to defaults if file missing. Creates file on first save.

## Installer

### Bootstrap .exe

A tiny Python script compiled with PyInstaller that:
1. Extracts `bootstrap.ps1` from embedded resources
2. Runs `powershell -ExecutionPolicy Bypass -File bootstrap.ps1`

### bootstrap.ps1

```
1. Check Python 3.12+ → if missing, install via winget (winget install Python.Python.3.12)
2. Check Git → if missing, install via winget (winget install Git.Git)
3. Clone repo: git clone https://github.com/<user>/mediariver C:\mediariver
4. Create venv: python -m venv C:\mediariver\.venv
5. Install deps: .venv\Scripts\pip install -e ".[desktop]"
6. Create config.json with defaults
7. Register Task Scheduler:
   - Name: MediaRiver
   - Trigger: At logon, delay 30 seconds
   - Action: C:\mediariver\.venv\Scripts\pythonw.exe C:\mediariver\desktop\tray.py
   - Run whether user is logged on or not: No (run only when logged on)
8. Create Start Menu shortcut → same command
9. Launch tray app
```

### Uninstall

Add `uninstall.ps1` that: removes Task Scheduler entry, removes Start Menu shortcut, optionally removes `C:\mediariver` and `~/.mediariver`.

## Dependencies

```toml
[project.optional-dependencies]
desktop = [
    "pystray>=0.19",
    "Pillow>=10.0",
    "fastapi>=0.115",
    "uvicorn>=0.30",
    "python-multipart>=0.0.9",
]
```

Note: `jinja2` is already a core dependency. `htmx.min.js` is vendored in `desktop/static/`.

## UI Style

Dark theme. Minimal CSS (no framework). Monospace font for logs and file paths. Sidebar navigation. Colors: dark gray background (#1a1a1a), lighter card backgrounds (#2a2a2a), accent color for status indicators (green=running, red=failed, yellow=pending).

## GitHub Release

- Create GitHub repo (or use existing if already pushed)
- README.md with: project description, features, quickstart, CLI usage, Docker usage, desktop app install
- Release v0.4.0 tag with: source, compiled `mediariver-setup.exe` as release asset
- GitHub Actions: add a `build-installer.yml` workflow that builds the .exe on push to tags
