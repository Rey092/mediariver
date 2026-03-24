# MediaRiver Desktop — Design Spec

## Overview

Windows desktop wrapper for MediaRiver. Tray icon + web UI for managing the media pipeline engine. Lives in the same repo as the engine — one `git pull` updates everything.

## Decisions Log

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Location | Same repo (`desktop/`) | Single git pull updates engine + desktop |
| Tray app | pystray | Lightweight, Python-native |
| UI | FastAPI + Jinja2 + HTMX | No JS build step, SSE for live logs, Python-only |
| Installer | PowerShell bootstrap (no .exe) | Avoids SmartScreen/antivirus issues. Standard pattern (like rustup, scoop) |
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
└── uninstall.ps1        # Removes scheduled task, shortcuts, optionally app dir
```

## Components

### Tray App (`tray.py`)

Runs as the main process via `pythonw.exe` (no console window). Uses pystray for the tray icon.

**Menu items:**
- Open UI (also triggered by left-click) — opens `http://localhost:9876` in default browser
- Restart Server — restarts the engine subprocess
- Check for Updates — runs updater, shows notification
- Quit — stops engine, stops server, exits

**On start:**
1. Check if port 9876 is available — if not, show tray notification with error and exit
2. Run updater check (git fetch, compare hashes, pull if behind)
3. Start FastAPI server (uvicorn) in a daemon thread
4. Start mediariver engine subprocess
5. Show tray icon
6. Watchdog: check server thread alive every 30s, restart if crashed

**Logging:** All desktop components log to `~/.mediariver/desktop.log` (rotating, 5MB max, 3 backups) since `pythonw.exe` has no console.

### Web Server (`server.py`)

FastAPI app on `localhost:9876`. Jinja2 templates + HTMX for interactivity.

Imports `ProcessedFile` and `WorkflowRun` from `mediariver.state.models` and uses `create_db_engine`/`get_session` from `mediariver.state.database` for read-only queries.

**Database access:** Uses SQLAlchemy with WAL mode (`PRAGMA journal_mode=WAL`) and `connect_args={"timeout": 30}` to avoid conflicts with the engine subprocess writing to the same SQLite file.

**Pages:**

| Route | Page | Content |
|-------|------|---------|
| `/` | Dashboard | Engine status (running/stopped), GPU detected (encoders list), uptime, files processed count by status |
| `/files` | Files | Table from `processed_files` DB. Columns: workflow, file, status, current step, error, timestamps. Filter by workflow/status. Pagination: `?offset=0&limit=50`, HTMX `hx-get` for page navigation. |
| `/workflows` | Workflows | List loaded workflow YAML files. Validation status (OK/error). Click to view YAML in a `<pre>` block. |
| `/logs` | Logs | Live server log stream via SSE + HTMX. Auto-scroll. Filter by level. Engine logs are structlog JSON — parse and format for display. |
| `/settings` | Settings | Workflows dir path, database URL, log level, env vars editor. Save writes to config.json. "Check for Updates" button (shows current vs remote version, "Apply Update" if behind). "Restart Server" button. |

**API endpoints (used by HTMX):**

| Method | Route | Action |
|--------|-------|--------|
| GET | `/api/status` | Engine status JSON (running, uptime, gpu info) |
| GET | `/api/files` | Processed files list (paginated: `?offset=0&limit=50&workflow=&status=`) |
| GET | `/api/workflows/{name}` | Raw YAML content of a single workflow |
| GET | `/api/logs/stream` | SSE endpoint for live logs (manual `StreamingResponse` with `text/event-stream`) |
| POST | `/api/server/restart` | Restart engine subprocess |
| POST | `/api/update` | Trigger git pull + restart |
| GET | `/api/update/check` | Check for updates (commits behind) |
| POST | `/api/settings` | Save config.json |

### Engine Service (`service.py`)

Manages the `mediariver run` subprocess.

```python
class EngineService:
    def start() -> None       # spawn subprocess with config
    def stop() -> None        # graceful stop via CTRL_BREAK_EVENT, force-kill after 5s
    def restart() -> None     # stop + start
    def is_running() -> bool  # check subprocess alive
    def get_logs() -> list    # return captured log lines from ring buffer
    def stream_logs() -> AsyncGenerator  # yield log lines via asyncio.Queue broadcast
```

**Subprocess command:** `python -m mediariver run --workflows-dir {config.workflows_dir} --database-url {config.database_url} --log-level {config.log_level}`

**Env vars:** Injected from `config.json`'s `env` dict into the subprocess environment.

**Graceful shutdown (Windows):** The subprocess is created with `CREATE_NEW_PROCESS_GROUP`. Stop sends `CTRL_BREAK_EVENT` via `os.kill(pid, signal.CTRL_BREAK_EVENT)`, which triggers `KeyboardInterrupt` in the engine's `run` command. If the process is still alive after 5s, `process.kill()` is called.

**Log capture:** Stdout/stderr are captured via pipes in a reader thread. Lines are parsed as structlog JSON and pushed into an `asyncio.Queue` for SSE broadcast. A ring buffer (last 10,000 lines) stores history for the logs page initial load.

### Updater (`updater.py`)

```python
class Updater:
    def check() -> UpdateStatus       # git fetch, compare HEAD vs origin/main
    def apply() -> None               # stop engine, git pull, pip install if needed, restart
    def get_current_version() -> str  # git rev-parse --short HEAD
    def get_remote_version() -> str   # git rev-parse --short origin/main
```

`UpdateStatus`: `{ up_to_date: bool, commits_behind: int, current: str, remote: str }`

**On tray app start:** `check()` → if not up to date → `apply()` automatically (before engine starts).

**"Update" button in UI:** `check()` → show status → user clicks "Apply Update" → `apply()`.

**Update sequence:**
1. Stop engine subprocess
2. Check for dirty working tree (`git status --porcelain`) — if dirty, refuse update with message
3. `git pull origin main`
4. Check if `pyproject.toml` changed — if so, run `pip install -e ".[desktop]"` (safe because engine is stopped)
5. Restart tray app (launch new process, exit current)

**Edge case:** If `git pull` fails (conflict, network error), log the error, show in UI, do not restart.

### Config (`config.py`)

Reads/writes `~/.mediariver/config.json`:

```json
{
  "workflows_dir": "C:\\mediariver\\workflows",
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

### Installation (PowerShell one-liner)

No `.exe` needed. Users run this in PowerShell:

```powershell
irm https://raw.githubusercontent.com/<user>/mediariver/main/installer/bootstrap.ps1 | iex
```

This avoids SmartScreen/antivirus issues entirely. Standard pattern used by rustup, scoop, deno, etc.

### bootstrap.ps1

```
1. Check Python 3.12+ → if missing:
   - Try winget: winget install Python.Python.3.12
   - If winget unavailable, print URL and exit with message
2. Check Git → if missing:
   - Try winget: winget install Git.Git
   - If winget unavailable, print URL and exit with message
3. Ask install path (default: C:\mediariver)
4. Clone repo: git clone https://github.com/<user>/mediariver $installPath
5. Create venv: python -m venv $installPath\.venv
6. Install deps: & "$installPath\.venv\Scripts\pip" install -e ".[desktop]"
7. Create config.json with defaults at ~/.mediariver/config.json
8. Register Task Scheduler:
   - Name: MediaRiver
   - Trigger: At logon, delay 30 seconds
   - Action: $installPath\.venv\Scripts\pythonw.exe $installPath\desktop\tray.py
   - Run only when user is logged on
9. Create Start Menu shortcut (MediaRiver → same command)
10. Launch tray app
```

### uninstall.ps1

```
1. Unregister-ScheduledTask -TaskName "MediaRiver" -Confirm:$false
2. Remove Start Menu shortcut
3. Prompt: "Remove C:\mediariver? (y/n)" → if yes, remove
4. Prompt: "Remove ~/.mediariver config and data? (y/n)" → if yes, remove
```

Located at `installer/uninstall.ps1`, also runnable from Settings page.

## Dependencies

Add to `pyproject.toml` under `[project.optional-dependencies]`:

```toml
desktop = [
    "pystray>=0.19",
    "Pillow>=10.0",
    "fastapi>=0.115",
    "uvicorn>=0.30",
    "python-multipart>=0.0.9",
]
```

Note: `jinja2` is already a core dependency. `htmx.min.js` is vendored in `desktop/static/`. SSE uses FastAPI's built-in `StreamingResponse` with `text/event-stream` content type (no extra package).

## UI Style

Dark theme. Minimal CSS (no framework). Monospace font for logs and file paths. Sidebar navigation. Colors: dark gray background (#1a1a1a), lighter card backgrounds (#2a2a2a), accent color for status indicators (green=running, red=failed, yellow=pending).

## GitHub Release

- Push to GitHub repo
- README.md with: project description, features, quickstart (CLI, Docker, Desktop), action catalog
- Tag `v0.5.0` for the desktop release
- GitHub Actions: no .exe build needed — installer is a PowerShell script
