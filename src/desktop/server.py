"""FastAPI web server for MediaRiver Desktop."""

from __future__ import annotations

import asyncio
import contextlib
import json
import subprocess
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
                q = q.order_by(ProcessedFile.updated_at.desc())
                files = q.offset(offset).limit(limit + 1).all()
                if len(files) > limit:
                    has_next = True
                    files = files[:limit]
                wf_rows = session.query(ProcessedFile.workflow_name).distinct().all()
                workflows_list = [r[0] for r in wf_rows]
        except Exception:
            pass

        ctx = {
            "page": "files",
            "files": files,
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
        return templates.TemplateResponse(request, "settings.html", {
            "page": "settings",
            "config": config,
            "env_json": json.dumps(config.env, indent=2),
            "current_version": current_version,
            "update_status": update_status,
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

    @app.post("/api/server/restart")
    async def api_restart():
        service.restart()
        return {"ok": True}

    @app.get("/api/update/check")
    async def api_update_check():
        status = updater.check()
        return asdict(status)

    @app.post("/api/update/apply")
    async def api_update_apply():
        success = updater.apply()
        return {"ok": success}

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
