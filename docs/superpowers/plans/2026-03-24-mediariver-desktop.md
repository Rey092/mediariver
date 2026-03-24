# MediaRiver Desktop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows tray app + web UI for managing the MediaRiver media pipeline engine.

**Architecture:** pystray tray icon as main process, FastAPI web server in a daemon thread, mediariver engine as a managed subprocess. Config stored in `~/.mediariver/config.json`. Jinja2 + HTMX for the web UI. SSE for live log streaming.

**Tech Stack:** Python 3.12+, pystray, Pillow, FastAPI, uvicorn, Jinja2, HTMX, SQLAlchemy (reuses engine models)

**Spec:** `docs/superpowers/specs/2026-03-24-mediariver-desktop-design.md`

---

## File Map

### Desktop App
- Create: `desktop/__init__.py`
- Create: `desktop/config.py` — reads/writes `~/.mediariver/config.json`
- Create: `desktop/service.py` — manages engine subprocess (start/stop/restart/logs)
- Create: `desktop/updater.py` — git-based update check and apply
- Create: `desktop/server.py` — FastAPI app with API + template routes
- Create: `desktop/tray.py` — pystray main entry point

### Templates
- Create: `desktop/templates/base.html` — dark theme layout, sidebar, HTMX
- Create: `desktop/templates/dashboard.html` — status overview
- Create: `desktop/templates/files.html` — processed files table
- Create: `desktop/templates/workflows.html` — workflow list + YAML viewer
- Create: `desktop/templates/logs.html` — live log stream
- Create: `desktop/templates/settings.html` — config editor + update button

### Static Assets
- Create: `desktop/static/style.css` — dark theme CSS
- Create: `desktop/static/htmx.min.js` — vendored HTMX

### Tests
- Create: `tests/unit/test_desktop_config.py`
- Create: `tests/unit/test_desktop_service.py`
- Create: `tests/unit/test_desktop_updater.py`
- Create: `tests/unit/test_desktop_server.py`

### Modified
- Modify: `pyproject.toml` — add `desktop` optional dependency group

### Installer (separate plan)
- Create: `installer/bootstrap.ps1`
- Create: `installer/uninstall.ps1`

---

## Task 1: Dependencies + Config Module

**Files:**
- Modify: `pyproject.toml`
- Create: `desktop/__init__.py`
- Create: `desktop/config.py`
- Create: `tests/unit/test_desktop_config.py`

- [ ] **Step 1: Add desktop deps to pyproject.toml**

Add under `[project.optional-dependencies]`:
```toml
desktop = [
    "pystray>=0.19",
    "Pillow>=10.0",
    "fastapi>=0.115",
    "uvicorn>=0.30",
    "python-multipart>=0.0.9",
]
```

Run: `pip install -e ".[desktop]"`

- [ ] **Step 2: Write failing tests for config**

`tests/unit/test_desktop_config.py`:
```python
"""Tests for desktop app configuration."""

import json

import pytest

from desktop.config import AppConfig, load_config, save_config, DEFAULT_CONFIG


class TestAppConfig:
    def test_default_config(self):
        config = AppConfig()
        assert config.workflows_dir == "./workflows"
        assert config.log_level == "info"
        assert config.port == 9876
        assert config.env == {}

    def test_config_from_dict(self):
        config = AppConfig(
            workflows_dir="C:\\my\\workflows",
            log_level="debug",
            port=8080,
            env={"S3_BUCKET": "test"},
        )
        assert config.workflows_dir == "C:\\my\\workflows"
        assert config.env["S3_BUCKET"] == "test"


class TestLoadSaveConfig:
    def test_load_missing_file_returns_defaults(self, tmp_path):
        config = load_config(tmp_path / "nonexistent.json")
        assert config.port == 9876

    def test_save_and_load_roundtrip(self, tmp_path):
        path = tmp_path / "config.json"
        config = AppConfig(workflows_dir="/test", env={"KEY": "val"})
        save_config(config, path)

        loaded = load_config(path)
        assert loaded.workflows_dir == "/test"
        assert loaded.env["KEY"] == "val"

    def test_save_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "sub" / "dir" / "config.json"
        save_config(AppConfig(), path)
        assert path.exists()
```

- [ ] **Step 3: Run tests to fail**

Run: `pytest tests/unit/test_desktop_config.py -v`

- [ ] **Step 4: Implement config module**

`desktop/__init__.py`: empty

`desktop/config.py`:
```python
"""Desktop app configuration — reads/writes ~/.mediariver/config.json."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

_CONFIG_DIR = Path.home() / ".mediariver"
DEFAULT_CONFIG_PATH = _CONFIG_DIR / "config.json"


@dataclass
class AppConfig:
    workflows_dir: str = "./workflows"
    database_url: str | None = None
    log_level: str = "info"
    port: int = 9876
    env: dict[str, str] = field(default_factory=dict)


DEFAULT_CONFIG = AppConfig()


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> AppConfig:
    """Load config from JSON file, returning defaults if missing."""
    if not path.exists():
        return AppConfig()
    try:
        data = json.loads(path.read_text())
        return AppConfig(**{k: v for k, v in data.items() if k in AppConfig.__dataclass_fields__})
    except (json.JSONDecodeError, TypeError):
        return AppConfig()


def save_config(config: AppConfig, path: Path = DEFAULT_CONFIG_PATH) -> None:
    """Save config to JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(config), indent=2))
```

- [ ] **Step 5: Run tests to pass**
- [ ] **Step 6: Commit**

```bash
git add pyproject.toml desktop/__init__.py desktop/config.py tests/unit/test_desktop_config.py
git commit -m "feat(desktop): add config module and desktop dependencies"
```

---

## Task 2: Engine Service

**Files:**
- Create: `desktop/service.py`
- Create: `tests/unit/test_desktop_service.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_desktop_service.py`:
```python
"""Tests for engine service subprocess management."""

import asyncio
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from desktop.config import AppConfig
from desktop.service import EngineService


class TestEngineService:
    def test_build_command(self):
        config = AppConfig(workflows_dir="/wf", database_url="sqlite:///test.db", log_level="debug")
        svc = EngineService(config)
        cmd = svc._build_command()
        assert "mediariver" in " ".join(cmd)
        assert "--workflows-dir" in cmd
        assert "/wf" in cmd
        assert "--log-level" in cmd
        assert "debug" in cmd

    def test_build_env(self):
        config = AppConfig(env={"S3_BUCKET": "test", "API_KEY": "secret"})
        svc = EngineService(config)
        env = svc._build_env()
        assert env["S3_BUCKET"] == "test"
        assert env["API_KEY"] == "secret"

    def test_not_running_initially(self):
        svc = EngineService(AppConfig())
        assert svc.is_running() is False

    def test_get_logs_empty(self):
        svc = EngineService(AppConfig())
        assert svc.get_logs() == []
```

- [ ] **Step 2: Run tests to fail**
- [ ] **Step 3: Implement service**

`desktop/service.py`:
```python
"""Engine subprocess management — start, stop, restart, log capture."""

from __future__ import annotations

import collections
import os
import signal
import subprocess
import sys
import threading
import time
from typing import Any

from desktop.config import AppConfig

_MAX_LOG_LINES = 10_000


class EngineService:
    """Manages the mediariver engine as a subprocess."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._process: subprocess.Popen | None = None
        self._logs: collections.deque[str] = collections.deque(maxlen=_MAX_LOG_LINES)
        self._log_lock = threading.Lock()
        self._reader_thread: threading.Thread | None = None
        self._started_at: float | None = None

    def start(self) -> None:
        """Start the engine subprocess."""
        if self.is_running():
            return

        cmd = self._build_command()
        env = self._build_env()

        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        self._started_at = time.time()

        self._reader_thread = threading.Thread(target=self._read_output, daemon=True)
        self._reader_thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Stop the engine subprocess gracefully, force-kill after timeout."""
        if not self._process or not self.is_running():
            return

        # Send CTRL_BREAK_EVENT (triggers KeyboardInterrupt in engine)
        try:
            os.kill(self._process.pid, signal.CTRL_BREAK_EVENT)
        except (OSError, ProcessLookupError):
            pass

        try:
            self._process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait(timeout=2)

        self._process = None
        self._started_at = None

    def restart(self) -> None:
        """Stop and start the engine."""
        self.stop()
        self.start()

    def is_running(self) -> bool:
        """Check if the engine subprocess is alive."""
        if self._process is None:
            return False
        return self._process.poll() is None

    def get_uptime(self) -> float:
        """Return uptime in seconds, or 0 if not running."""
        if self._started_at and self.is_running():
            return time.time() - self._started_at
        return 0.0

    def get_logs(self, last_n: int | None = None) -> list[str]:
        """Return captured log lines."""
        with self._log_lock:
            if last_n:
                return list(self._logs)[-last_n:]
            return list(self._logs)

    def _build_command(self) -> list[str]:
        """Build the subprocess command."""
        cmd = [sys.executable, "-m", "mediariver", "run"]
        cmd.extend(["--workflows-dir", self.config.workflows_dir])
        if self.config.database_url:
            cmd.extend(["--database-url", self.config.database_url])
        cmd.extend(["--log-level", self.config.log_level])
        return cmd

    def _build_env(self) -> dict[str, str]:
        """Build subprocess environment with config env vars."""
        env = dict(os.environ)
        env.update(self.config.env)
        return env

    def _read_output(self) -> None:
        """Read subprocess output in a thread."""
        if not self._process or not self._process.stdout:
            return
        for line in self._process.stdout:
            stripped = line.rstrip("\n")
            if stripped:
                with self._log_lock:
                    self._logs.append(stripped)
```

- [ ] **Step 4: Run tests to pass**
- [ ] **Step 5: Commit**

```bash
git add desktop/service.py tests/unit/test_desktop_service.py
git commit -m "feat(desktop): add engine service subprocess manager"
```

---

## Task 3: Updater

**Files:**
- Create: `desktop/updater.py`
- Create: `tests/unit/test_desktop_updater.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_desktop_updater.py`:
```python
"""Tests for git-based updater."""

from unittest.mock import patch, MagicMock
import subprocess

import pytest

from desktop.updater import Updater, UpdateStatus


class TestUpdater:
    def test_check_up_to_date(self):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                subprocess.CompletedProcess([], 0),  # git fetch
                subprocess.CompletedProcess([], 0, stdout="abc1234\n"),  # local hash
                subprocess.CompletedProcess([], 0, stdout="abc1234\n"),  # remote hash
                subprocess.CompletedProcess([], 0, stdout="0\n"),  # rev-list count
            ]
            updater = Updater("/fake/repo")
            status = updater.check()
            assert status.up_to_date is True
            assert status.commits_behind == 0

    def test_check_behind(self):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                subprocess.CompletedProcess([], 0),  # git fetch
                subprocess.CompletedProcess([], 0, stdout="abc1234\n"),  # local
                subprocess.CompletedProcess([], 0, stdout="def5678\n"),  # remote
                subprocess.CompletedProcess([], 0, stdout="3\n"),  # 3 behind
            ]
            updater = Updater("/fake/repo")
            status = updater.check()
            assert status.up_to_date is False
            assert status.commits_behind == 3

    def test_check_fetch_failure(self):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "git fetch")
            updater = Updater("/fake/repo")
            status = updater.check()
            assert status.up_to_date is True  # assume up to date on error
            assert status.error is not None
```

- [ ] **Step 2: Run tests to fail**
- [ ] **Step 3: Implement updater**

`desktop/updater.py`:
```python
"""Git-based auto-updater — check for new commits and apply."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class UpdateStatus:
    up_to_date: bool
    commits_behind: int = 0
    current: str = ""
    remote: str = ""
    error: str | None = None


class Updater:
    """Check and apply updates via git."""

    def __init__(self, repo_path: str | Path) -> None:
        self.repo_path = str(repo_path)

    def check(self) -> UpdateStatus:
        """Fetch from origin and compare HEAD vs origin/main."""
        try:
            self._git("fetch", "origin", "main", "--quiet")
            current = self._git("rev-parse", "--short", "HEAD").strip()
            remote = self._git("rev-parse", "--short", "origin/main").strip()
            behind_str = self._git("rev-list", "HEAD..origin/main", "--count").strip()
            behind = int(behind_str)
            return UpdateStatus(
                up_to_date=behind == 0,
                commits_behind=behind,
                current=current,
                remote=remote,
            )
        except (subprocess.CalledProcessError, ValueError, OSError) as e:
            return UpdateStatus(up_to_date=True, error=str(e))

    def apply(self) -> bool:
        """Pull latest changes. Returns True on success."""
        try:
            # Check for dirty working tree
            status = self._git("status", "--porcelain").strip()
            if status:
                return False

            self._git("pull", "origin", "main")

            # Check if pyproject.toml changed (need pip install)
            diff = self._git("diff", "HEAD~1", "--name-only")
            if "pyproject.toml" in diff:
                import sys
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-e", ".[desktop]", "--quiet"],
                    cwd=self.repo_path,
                    check=True,
                )

            return True
        except (subprocess.CalledProcessError, OSError):
            return False

    def get_current_version(self) -> str:
        """Return short hash of current HEAD."""
        try:
            return self._git("rev-parse", "--short", "HEAD").strip()
        except (subprocess.CalledProcessError, OSError):
            return "unknown"

    def _git(self, *args: str) -> str:
        """Run a git command in the repo directory."""
        result = subprocess.run(
            ["git", *args],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
```

- [ ] **Step 4: Run tests to pass**
- [ ] **Step 5: Commit**

```bash
git add desktop/updater.py tests/unit/test_desktop_updater.py
git commit -m "feat(desktop): add git-based updater with check and apply"
```

---

## Task 4: Web Server (FastAPI + API routes)

**Files:**
- Create: `desktop/server.py`
- Create: `tests/unit/test_desktop_server.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_desktop_server.py`:
```python
"""Tests for FastAPI web server."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from desktop.config import AppConfig


@pytest.fixture
def app():
    from desktop.server import create_app
    config = AppConfig()
    service = MagicMock()
    service.is_running.return_value = True
    service.get_uptime.return_value = 3600.0
    service.get_logs.return_value = ["line1", "line2"]
    updater = MagicMock()
    return create_app(config, service, updater)


@pytest.fixture
def client(app):
    return TestClient(app)


class TestDashboard:
    def test_homepage_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "MediaRiver" in response.text

    def test_api_status(self, client):
        response = client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        assert data["running"] is True
        assert data["uptime"] == 3600.0


class TestFilesPage:
    def test_files_page_returns_200(self, client):
        with patch("desktop.server._get_db_session") as mock_session:
            mock_session.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            response = client.get("/files")
            assert response.status_code == 200


class TestSettingsPage:
    def test_settings_page_returns_200(self, client):
        response = client.get("/settings")
        assert response.status_code == 200

    def test_save_settings(self, client, tmp_path):
        response = client.post("/api/settings", data={
            "workflows_dir": "/new/path",
            "log_level": "debug",
            "port": "9876",
        })
        assert response.status_code in (200, 303)
```

- [ ] **Step 2: Run tests to fail**
- [ ] **Step 3: Implement server**

`desktop/server.py`:
```python
"""FastAPI web server — dashboard, files, workflows, logs, settings."""

from __future__ import annotations

import asyncio
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from desktop.config import AppConfig, save_config

_DESKTOP_DIR = Path(__file__).parent
_templates = Jinja2Templates(directory=str(_DESKTOP_DIR / "templates"))


def _get_db_session():
    """Get a read-only database session using the engine's models."""
    from mediariver.state.database import create_db_engine, get_session
    engine = create_db_engine()
    # Enable WAL mode for concurrent access
    from sqlalchemy import event
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()
    return get_session(engine)


def create_app(
    config: AppConfig,
    service: Any,
    updater: Any,
) -> FastAPI:
    """Create the FastAPI application."""
    app = FastAPI(title="MediaRiver Desktop")
    app.mount("/static", StaticFiles(directory=str(_DESKTOP_DIR / "static")), name="static")

    # --- Pages ---

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request):
        gpu_info = _detect_gpu()
        return _templates.TemplateResponse("dashboard.html", {
            "request": request,
            "running": service.is_running(),
            "uptime": service.get_uptime(),
            "gpu": gpu_info,
            "page": "dashboard",
        })

    @app.get("/files", response_class=HTMLResponse)
    async def files_page(request: Request, workflow: str = "", status: str = "", offset: int = 0, limit: int = 50):
        from mediariver.state.models import ProcessedFile
        session = _get_db_session()
        try:
            query = session.query(ProcessedFile)
            if workflow:
                query = query.filter_by(workflow_name=workflow)
            if status:
                query = query.filter_by(status=status)
            total = query.count()
            files = query.order_by(ProcessedFile.updated_at.desc()).offset(offset).limit(limit).all()
            return _templates.TemplateResponse("files.html", {
                "request": request,
                "files": files,
                "total": total,
                "offset": offset,
                "limit": limit,
                "workflow": workflow,
                "status": status,
                "page": "files",
            })
        finally:
            session.close()

    @app.get("/workflows", response_class=HTMLResponse)
    async def workflows_page(request: Request):
        from mediariver.config.loader import load_workflows_from_dir
        from mediariver.config.validators import validate_workflow, ValidationError
        wf_dir = Path(config.workflows_dir)
        workflows = []
        if wf_dir.exists():
            for path in sorted(list(wf_dir.glob("*.yaml")) + list(wf_dir.glob("*.yml"))):
                try:
                    spec = load_workflows_from_dir(wf_dir)
                    spec_match = [s for s in spec if s.name in path.stem or path.stem in s.name]
                    from mediariver.config.loader import load_workflow
                    s = load_workflow(path)
                    validate_workflow(s)
                    workflows.append({"name": s.name, "path": str(path), "status": "ok", "error": None})
                except Exception as e:
                    workflows.append({"name": path.stem, "path": str(path), "status": "error", "error": str(e)})
        return _templates.TemplateResponse("workflows.html", {
            "request": request,
            "workflows": workflows,
            "page": "workflows",
        })

    @app.get("/workflows/{name}", response_class=HTMLResponse)
    async def workflow_detail(request: Request, name: str):
        wf_dir = Path(config.workflows_dir)
        for ext in ("yaml", "yml"):
            path = wf_dir / f"{name}.{ext}"
            if path.exists():
                return HTMLResponse(f"<pre>{path.read_text()}</pre>")
        # Try matching by workflow name inside YAML
        for path in sorted(list(wf_dir.glob("*.yaml")) + list(wf_dir.glob("*.yml"))):
            content = path.read_text()
            if f"name: {name}" in content:
                return HTMLResponse(f"<pre>{content}</pre>")
        return HTMLResponse("<p>Workflow not found</p>", status_code=404)

    @app.get("/logs", response_class=HTMLResponse)
    async def logs_page(request: Request):
        return _templates.TemplateResponse("logs.html", {
            "request": request,
            "initial_logs": service.get_logs(last_n=200),
            "page": "logs",
        })

    @app.get("/settings", response_class=HTMLResponse)
    async def settings_page(request: Request):
        update_status = updater.check()
        return _templates.TemplateResponse("settings.html", {
            "request": request,
            "config": config,
            "update_status": update_status,
            "page": "settings",
        })

    # --- API ---

    @app.get("/api/status")
    async def api_status():
        return {
            "running": service.is_running(),
            "uptime": service.get_uptime(),
        }

    @app.get("/api/files")
    async def api_files(workflow: str = "", status: str = "", offset: int = 0, limit: int = 50):
        from mediariver.state.models import ProcessedFile
        session = _get_db_session()
        try:
            query = session.query(ProcessedFile)
            if workflow:
                query = query.filter_by(workflow_name=workflow)
            if status:
                query = query.filter_by(status=status)
            files = query.order_by(ProcessedFile.updated_at.desc()).offset(offset).limit(limit).all()
            return [{"id": f.id, "workflow": f.workflow_name, "file": f.file_path,
                      "status": f.status, "error": f.error, "step": f.current_step} for f in files]
        finally:
            session.close()

    @app.get("/api/logs/stream")
    async def api_log_stream():
        async def event_generator():
            last_count = len(service.get_logs())
            while True:
                logs = service.get_logs()
                if len(logs) > last_count:
                    for line in logs[last_count:]:
                        yield f"data: {line}\n\n"
                    last_count = len(logs)
                await asyncio.sleep(0.5)
        return StreamingResponse(event_generator(), media_type="text/event-stream")

    @app.post("/api/server/restart")
    async def api_restart():
        service.restart()
        return {"status": "restarted"}

    @app.get("/api/update/check")
    async def api_update_check():
        status = updater.check()
        return {
            "up_to_date": status.up_to_date,
            "commits_behind": status.commits_behind,
            "current": status.current,
            "remote": status.remote,
            "error": status.error,
        }

    @app.post("/api/update")
    async def api_update():
        service.stop()
        success = updater.apply()
        if success:
            service.start()
            return {"status": "updated"}
        service.start()
        return JSONResponse({"status": "failed"}, status_code=500)

    @app.post("/api/settings")
    async def api_save_settings(
        workflows_dir: str = Form(""),
        log_level: str = Form("info"),
        port: str = Form("9876"),
        database_url: str = Form(""),
        env_json: str = Form("{}"),
    ):
        config.workflows_dir = workflows_dir or config.workflows_dir
        config.log_level = log_level
        config.port = int(port)
        config.database_url = database_url or None
        try:
            config.env = json.loads(env_json)
        except json.JSONDecodeError:
            pass
        save_config(config)
        return RedirectResponse("/settings", status_code=303)

    return app


def _detect_gpu() -> dict[str, Any]:
    """Detect GPU encoders available via ffmpeg."""
    import shutil
    import subprocess
    if not shutil.which("ffmpeg"):
        return {"available": False, "encoders": []}
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True, text=True, timeout=5,
        )
        encoders = [
            line.split()[1]
            for line in result.stdout.splitlines()
            if "nvenc" in line.lower() and len(line.split()) > 1
        ]
        return {"available": len(encoders) > 0, "encoders": encoders}
    except Exception:
        return {"available": False, "encoders": []}
```

- [ ] **Step 4: Run tests to pass**
- [ ] **Step 5: Commit**

```bash
git add desktop/server.py tests/unit/test_desktop_server.py
git commit -m "feat(desktop): add FastAPI web server with API and template routes"
```

---

## Task 5: HTML Templates + Static Assets

**Files:**
- Create: `desktop/templates/base.html`
- Create: `desktop/templates/dashboard.html`
- Create: `desktop/templates/files.html`
- Create: `desktop/templates/workflows.html`
- Create: `desktop/templates/logs.html`
- Create: `desktop/templates/settings.html`
- Create: `desktop/static/style.css`
- Create: `desktop/static/htmx.min.js` (vendor from CDN)

This task creates the full web UI. Templates use Jinja2 + HTMX.

- [ ] **Step 1: Download htmx.min.js**

Run: `curl -o desktop/static/htmx.min.js https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js`

- [ ] **Step 2: Create base.html**

Dark sidebar layout with nav links, HTMX loaded, page title block.

- [ ] **Step 3: Create dashboard.html**

Shows: engine status badge (green running / red stopped), GPU info, uptime, files processed stats. Auto-refreshes status via HTMX polling (`hx-get="/api/status" hx-trigger="every 5s"`).

- [ ] **Step 4: Create files.html**

Table: workflow, filename, status (colored badge), current step, error, updated_at. Filter dropdowns for workflow and status. Pagination with prev/next. HTMX partial reload.

- [ ] **Step 5: Create workflows.html**

List of workflows with OK/error badge. Click expands to show YAML content (`hx-get="/workflows/{name}" hx-target="#yaml-viewer"`).

- [ ] **Step 6: Create logs.html**

Auto-scrolling log viewer. Connects to SSE endpoint. Lines appear in real-time. Level filter buttons (info/warning/error). Pre-populated with last 200 lines on load.

- [ ] **Step 7: Create settings.html**

Form: workflows_dir input, log_level dropdown, database_url input, env vars textarea (JSON). Save button. Update section: shows current/remote hash, commits behind, "Apply Update" button. Restart button.

- [ ] **Step 8: Create style.css**

Dark theme: `#1a1a1a` bg, `#2a2a2a` cards, `#e0e0e0` text, monospace for logs/paths. Green/red/yellow status colors. Sidebar: fixed left, 200px wide.

- [ ] **Step 9: Commit**

```bash
git add desktop/templates/ desktop/static/
git commit -m "feat(desktop): add web UI templates and static assets"
```

---

## Task 6: Tray App (Main Entry Point)

**Files:**
- Create: `desktop/tray.py`
- Create: `desktop/icon.ico`

- [ ] **Step 1: Create a simple icon**

Generate a 64x64 ICO file programmatically with Pillow (green circle on dark background — represents "running").

- [ ] **Step 2: Implement tray.py**

`desktop/tray.py`:
```python
"""MediaRiver tray app — main entry point for Windows desktop."""

from __future__ import annotations

import logging
import os
import socket
import sys
import threading
import webbrowser
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pystray
import uvicorn
from PIL import Image

from desktop.config import DEFAULT_CONFIG_PATH, load_config, save_config
from desktop.server import create_app
from desktop.service import EngineService
from desktop.updater import Updater

_LOG_DIR = Path.home() / ".mediariver"
_LOG_FILE = _LOG_DIR / "desktop.log"


def _setup_logging() -> None:
    """Configure logging to file (pythonw has no console)."""
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(_LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])


def _port_available(port: int) -> bool:
    """Check if a port is available."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def main() -> None:
    _setup_logging()
    log = logging.getLogger("mediariver.desktop")

    # Load config
    config = load_config()
    log.info("Config loaded: %s", DEFAULT_CONFIG_PATH)

    # Check port
    if not _port_available(config.port):
        log.error("Port %d already in use", config.port)
        # Try to show a notification (best effort)
        try:
            from pystray import Icon, MenuItem, Menu
            import pystray._win32
        except Exception:
            pass
        sys.exit(1)

    # Auto-update on start
    repo_dir = Path(__file__).parent.parent
    updater = Updater(repo_dir)
    status = updater.check()
    if not status.up_to_date:
        log.info("Update available: %d commits behind", status.commits_behind)
        if updater.apply():
            log.info("Updated successfully, restarting...")
            os.execv(sys.executable, [sys.executable] + sys.argv)

    # Start engine service
    service = EngineService(config)
    service.start()
    log.info("Engine started")

    # Start web server in thread
    app = create_app(config, service, updater)

    def run_server():
        uvicorn.run(app, host="127.0.0.1", port=config.port, log_level="warning")

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    log.info("Web UI at http://127.0.0.1:%d", config.port)

    # Tray icon
    def open_ui(icon, item):
        webbrowser.open(f"http://127.0.0.1:{config.port}")

    def restart_server(icon, item):
        service.restart()

    def check_updates(icon, item):
        s = updater.check()
        if s.up_to_date:
            icon.notify("MediaRiver is up to date")
        else:
            icon.notify(f"Update available: {s.commits_behind} commits behind")

    def quit_app(icon, item):
        log.info("Shutting down...")
        service.stop()
        icon.stop()

    icon_image = Image.open(Path(__file__).parent / "icon.ico")

    icon = pystray.Icon(
        "MediaRiver",
        icon_image,
        "MediaRiver",
        menu=pystray.Menu(
            pystray.MenuItem("Open UI", open_ui, default=True),
            pystray.MenuItem("Restart Server", restart_server),
            pystray.MenuItem("Check for Updates", check_updates),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", quit_app),
        ),
    )

    # Watchdog: check server thread every 30s
    def watchdog():
        import time
        while True:
            time.sleep(30)
            if not server_thread.is_alive():
                log.error("Server thread died, restarting...")
                new_thread = threading.Thread(target=run_server, daemon=True)
                new_thread.start()

    threading.Thread(target=watchdog, daemon=True).start()

    log.info("Tray icon ready")
    icon.run()  # blocks until quit


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Test manually**

Run: `python desktop/tray.py`
Expected: tray icon appears, left-click opens browser at localhost:9876

- [ ] **Step 4: Commit**

```bash
git add desktop/tray.py desktop/icon.ico
git commit -m "feat(desktop): add tray app entry point with watchdog"
```

---

## Task 7: Installer Scripts

**Files:**
- Create: `installer/bootstrap.ps1`
- Create: `installer/uninstall.ps1`

- [ ] **Step 1: Create bootstrap.ps1**

PowerShell installer that: checks Python/Git, clones repo, creates venv, installs deps, registers Task Scheduler, creates Start Menu shortcut, launches app.

- [ ] **Step 2: Create uninstall.ps1**

Removes: Task Scheduler entry, Start Menu shortcut, optionally app dir and config.

- [ ] **Step 3: Commit**

```bash
git add installer/
git commit -m "feat(desktop): add PowerShell installer and uninstaller scripts"
```

---

## Task 8: README + GitHub Release

**Files:**
- Create: `README.md`
- Modify: `pyproject.toml` — bump version to 0.5.0

- [ ] **Step 1: Write README.md**

Sections: What is MediaRiver, Features, Quick Start (CLI / Docker / Desktop), Action Catalog (table of all 38 actions), Workflow YAML Example, Configuration, Development.

- [ ] **Step 2: Bump version to 0.5.0**

In `pyproject.toml` and `src/mediariver/__init__.py`.

- [ ] **Step 3: Commit and tag**

```bash
git add README.md pyproject.toml src/mediariver/__init__.py
git commit -m "feat: v0.5.0 — desktop app, README, release"
git tag v0.5.0
```

- [ ] **Step 4: Push to GitHub**

```bash
git remote add origin https://github.com/<user>/mediariver.git
git push -u origin main --tags
```

---
