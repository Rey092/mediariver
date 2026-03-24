"""FastAPI web server for MediaRiver Desktop."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from desktop.config import AppConfig, save_config

if TYPE_CHECKING:
    from desktop.service import EngineService
    from desktop.updater import Updater

_HERE = Path(__file__).parent
_TEMPLATES_DIR = _HERE / "templates"
_STATIC_DIR = _HERE / "static"


def _detect_gpu_encoders() -> list[str]:
    """Run ffmpeg -encoders and look for nvenc / qsv / amf."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-encoders", "-hide_banner"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        encoders: list[str] = []
        for line in result.stdout.splitlines():
            lower = line.lower()
            if "nvenc" in lower or "qsv" in lower or "amf" in lower:
                encoders.append(line.strip())
        return encoders
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return []


def _format_uptime(seconds: float) -> str:
    h = int(seconds) // 3600
    m = (int(seconds) % 3600) // 60
    return f"{h}h {m}m"


def _check_startup_task() -> bool:
    """Check if the MediaRiver scheduled task exists on Windows."""
    import sys
    if sys.platform != "win32":
        return False
    try:
        result = subprocess.run(
            ["powershell", "-Command", "Get-ScheduledTask -TaskName 'MediaRiver' -ErrorAction Stop"],
            capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _set_startup_task(enable: bool) -> None:
    """Register or unregister the Windows startup scheduled task."""
    import sys
    if sys.platform != "win32":
        return

    if not enable:
        subprocess.run(
            ["powershell", "-Command", "Unregister-ScheduledTask -TaskName 'MediaRiver' -Confirm:$false -ErrorAction SilentlyContinue"],
            capture_output=True, timeout=10,
        )
        return

    # Find the repo root and scripts
    repo_dir = Path(__file__).resolve().parent.parent
    register_script = repo_dir / "installer" / "register-startup.ps1"
    if register_script.exists():
        subprocess.run(
            ["powershell", "-File", str(register_script)],
            capture_output=True, timeout=15,
        )
    else:
        # Fallback: inline registration
        pythonw = str(repo_dir / ".venv" / "Scripts" / "pythonw.exe")
        tray_script = str(repo_dir / "src" / "desktop" / "tray.py")
        ps_cmd = (
            f"$a = New-ScheduledTaskAction -Execute '{pythonw}' -Argument '{tray_script}' -WorkingDirectory '{repo_dir}';"
            f"$t = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME; $t.Delay = 'PT30S';"
            f"$s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit 0;"
            f"Register-ScheduledTask -TaskName 'MediaRiver' -Action $a -Trigger $t -Settings $s -Force | Out-Null"
        )
        subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, timeout=15)


def _get_db_stats(config: AppConfig) -> dict:
    """Query processed file stats. Returns zeros if DB is unavailable."""
    stats = {"total": 0, "done": 0, "failed": 0, "pending": 0}
    try:
        from sqlalchemy import func

        from mediariver.state.database import create_db_engine, get_session
        from mediariver.state.models import ProcessedFile

        engine = create_db_engine(config.database_url)
        with get_session(engine) as session:
            rows = (
                session.query(ProcessedFile.status, func.count())
                .group_by(ProcessedFile.status)
                .all()
            )
            for status, count in rows:
                stats["total"] += count
                if status in stats:
                    stats[status] = count
    except Exception:
        pass
    return stats


def create_app(config: AppConfig, service: EngineService, updater: Updater) -> FastAPI:
    """Create and return the FastAPI application."""
    app = FastAPI(title="MediaRiver Desktop")

    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

    # ── Page routes ────────────────────────────────────────────────────

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request):
        running = service.is_running()
        uptime = service.get_uptime()
        stats = _get_db_stats(config)
        gpu_encoders = _detect_gpu_encoders()
        return templates.TemplateResponse(request, "dashboard.html", {
            "page": "dashboard",
            "running": running,
            "uptime_fmt": _format_uptime(uptime),
            "stats": stats,
            "gpu_encoders": gpu_encoders,
        })

    @app.get("/files", response_class=HTMLResponse)
    async def files_page(
        request: Request,
        workflow: str = "",
        status: str = "",
        offset: int = 0,
        limit: int = 50,
    ):
        files = []
        workflows_list: list[str] = []
        has_next = False
        try:
            from mediariver.state.database import create_db_engine, get_session
            from mediariver.state.models import ProcessedFile

            engine = create_db_engine(config.database_url)
            with get_session(engine) as session:
                q = session.query(ProcessedFile)
                if workflow:
                    q = q.filter(ProcessedFile.workflow_name == workflow)
                if status:
                    q = q.filter(ProcessedFile.status == status)
                total = q.count()
                q = q.order_by(ProcessedFile.updated_at.desc())
                files = q.offset(offset).limit(limit + 1).all()
                if len(files) > limit:
                    has_next = True
                    files = files[:limit]
                wf_rows = session.query(ProcessedFile.workflow_name).distinct().all()
                workflows_list = [r[0] for r in wf_rows]
        except Exception:
            total = 0

        ctx = {
            "page": "files",
            "files": files,
            "total": total,
            "workflows": workflows_list,
            "current_workflow": workflow,
            "current_status": status,
            "offset": offset,
            "limit": limit,
            "has_next": has_next,
        }

        # If HTMX request, return just the table partial
        if request.headers.get("HX-Request"):
            return templates.TemplateResponse(request, "partials/files_table.html", ctx)
        return templates.TemplateResponse(request, "files.html", ctx)

    @app.get("/workflows", response_class=HTMLResponse)
    async def workflows_page(request: Request):
        wf_dir = Path(config.workflows_dir)
        workflows = []
        if wf_dir.exists():
            for p in sorted(wf_dir.glob("*.y*ml")):
                entry = {"name": p.stem, "path": str(p), "content": "", "error": None}
                try:
                    entry["content"] = p.read_text(encoding="utf-8")
                except Exception as e:
                    entry["error"] = str(e)
                workflows.append(entry)
        return templates.TemplateResponse(request, "workflows.html", {
            "page": "workflows",
            "workflows": workflows,
            "workflows_dir": config.workflows_dir,
        })

    @app.get("/logs", response_class=HTMLResponse)
    async def logs_page(request: Request):
        initial_logs = service.get_logs(last_n=500)
        return templates.TemplateResponse(request, "logs.html", {
            "page": "logs",
            "initial_logs": initial_logs,
        })

    @app.get("/settings", response_class=HTMLResponse)
    async def settings_page(request: Request):
        current_version = updater.get_current_version()
        update_status = None
        with contextlib.suppress(Exception):
            update_status = updater.check()
        startup_enabled = _check_startup_task()
        default_db = str((Path.home() / ".mediariver" / "state.db").resolve())
        return templates.TemplateResponse(request, "settings.html", {
            "page": "settings",
            "config": config,
            "env_json": json.dumps(config.env, indent=2),
            "current_version": current_version,
            "update_status": update_status,
            "startup_enabled": startup_enabled,
            "default_db_url": f"sqlite:///{default_db}",
        })

    # ── API routes ─────────────────────────────────────────────────────

    @app.get("/api/status")
    async def api_status():
        running = service.is_running()
        uptime = service.get_uptime()
        return {
            "running": running,
            "uptime": uptime,
            "uptime_fmt": _format_uptime(uptime),
        }

    @app.post("/api/engine/restart")
    async def api_engine_restart():
        """Restart the media pipeline engine subprocess only."""
        service.restart()
        return {"ok": True}

    @app.post("/api/app/restart")
    async def api_app_restart():
        """Full restart — stop engine, re-exec the entire tray process."""
        service.stop()
        os.execv(sys.executable, [sys.executable, *sys.argv])

    @app.get("/api/update/check")
    async def api_update_check():
        status = updater.check()
        return asdict(status)

    @app.post("/api/update/apply")
    async def api_update_apply():
        success = updater.apply()
        return {"ok": success}

    @app.post("/api/startup/enable", response_class=HTMLResponse)
    async def api_startup_enable():
        _set_startup_task(enable=True)
        return (
            '<p class="text-sm"><span class="badge badge-done">Enabled</span> MediaRiver starts automatically 30s after logon</p>'
            '<button class="btn" hx-post="/api/startup/disable" hx-target="#startup-status" hx-swap="innerHTML">Disable Startup</button>'
        )

    @app.post("/api/startup/disable", response_class=HTMLResponse)
    async def api_startup_disable():
        _set_startup_task(enable=False)
        return (
            '<p class="text-sm"><span class="badge badge-failed">Disabled</span> MediaRiver does not start on Windows boot</p>'
            '<button class="btn btn-accent" hx-post="/api/startup/enable" hx-target="#startup-status" hx-swap="innerHTML">Enable Startup</button>'
        )

    @app.post("/api/settings")
    async def api_settings(
        workflows_dir: str = Form(""),
        log_level: str = Form("info"),
        database_url: str = Form(""),
        port: int = Form(9876),
        env: str = Form("{}"),
    ):
        config.workflows_dir = workflows_dir or config.workflows_dir
        config.log_level = log_level
        config.database_url = database_url or None
        config.port = port
        with contextlib.suppress(json.JSONDecodeError, TypeError):
            config.env = json.loads(env)
        save_config(config)
        return {"ok": True}

    @app.post("/api/files/{file_id}/reprocess", response_class=HTMLResponse)
    async def api_reprocess_file(file_id: int):
        """Reset a single file to pending so it gets reprocessed."""
        from mediariver.state.database import create_db_engine, get_session
        from mediariver.state.models import ProcessedFile

        engine = create_db_engine(config.database_url)
        with get_session(engine) as session:
            pf = session.get(ProcessedFile, file_id)
            if not pf:
                return HTMLResponse("Not found", status_code=404)
            pf.status = "pending"
            pf.error = None
            pf.current_step = None
            pf.attempts = 0
            session.commit()
            return (
                f'<tr id="file-row-{pf.id}">'
                f'<td>{pf.workflow_name}</td>'
                f'<td class="truncate" title="{pf.file_path}">{pf.file_path}</td>'
                f'<td><span class="badge badge-pending">pending</span></td>'
                f'<td>-</td><td>-</td>'
                f'<td class="text-sm">{pf.updated_at}</td>'
                f'<td></td></tr>'
            )

    @app.post("/api/files/reprocess-all")
    async def api_reprocess_all(workflow: str = "", status: str = ""):
        """Reset all matching files to pending."""
        from mediariver.state.database import create_db_engine, get_session
        from mediariver.state.models import ProcessedFile

        engine = create_db_engine(config.database_url)
        with get_session(engine) as session:
            query = session.query(ProcessedFile)
            if workflow:
                query = query.filter_by(workflow_name=workflow)
            if status:
                query = query.filter_by(status=status)
            for pf in query.all():
                pf.status = "pending"
                pf.error = None
                pf.current_step = None
                pf.attempts = 0
            session.commit()
        from starlette.responses import RedirectResponse
        params = f"?workflow={workflow}&status=" if workflow else ""
        return RedirectResponse(f"/files{params}", status_code=303)

    @app.get("/api/logs/stream")
    async def api_logs_stream():
        async def generate():
            last_count = len(service.get_logs())
            while True:
                logs = service.get_logs()
                if len(logs) > last_count:
                    for line in logs[last_count:]:
                        yield f"data: {line}\n\n"
                    last_count = len(logs)
                await asyncio.sleep(1)

        return StreamingResponse(generate(), media_type="text/event-stream")

    return app
