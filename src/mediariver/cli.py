"""MediaRiver CLI — typer application."""

from __future__ import annotations

from pathlib import Path

import typer

from mediariver.logging import configure_logging

app = typer.Typer(name="mediariver", help="Spec-driven media pipeline CLI.")


@app.command()
def run(
    workflows_dir: Path = typer.Option(Path("./workflows"), help="Path to workflows directory"),
    database_url: str | None = typer.Option(None, help="Database URL (default: sqlite)"),
    log_level: str = typer.Option("info", help="Log level: debug, info, warning, error"),
    workflow_name: str | None = typer.Argument(None, help="Run a specific workflow by name"),
) -> None:
    """Load workflows and start watching/processing."""
    configure_logging(log_level)

    import time

    import structlog

    from mediariver.actions.executor import CommandExecutor
    from mediariver.config.loader import load_workflows_from_dir
    from mediariver.config.validators import validate_workflow
    from mediariver.connections.registry import build_connection
    from mediariver.engine.runner import PipelineRunner
    from mediariver.state.database import create_db_engine, create_tables, get_session
    from mediariver.state.models import ProcessedFile
    from mediariver.watcher.poller import parse_interval, poll_once

    log = structlog.get_logger()

    specs = load_workflows_from_dir(workflows_dir)
    if not specs:
        log.warning("no_workflows_found", dir=str(workflows_dir))
        raise typer.Exit(1)

    for spec in specs:
        validate_workflow(spec)

    if workflow_name:
        specs = [s for s in specs if s.name == workflow_name]
        if not specs:
            log.error("workflow_not_found", name=workflow_name)
            raise typer.Exit(1)

    engine = create_db_engine(database_url)
    create_tables(engine)
    executor = CommandExecutor()

    # Import actions to trigger registration
    import mediariver.actions  # noqa: F401
    from mediariver.actions.registry import ActionRegistry

    # Startup info
    log.info(
        "mediariver_starting",
        version=mediariver.__version__,
        workflows=[s.name for s in specs],
        actions=len(ActionRegistry.list_actions()),
    )

    # Detect hardware capabilities
    _log_hardware_info(executor, log)

    try:
        while True:
            for spec in specs:
                connections = {}
                for conn_name, conn_config in spec.connections.items():
                    connections[conn_name] = build_connection(conn_name, conn_config)

                watch_fs = connections[spec.watch.connection]
                work_base = Path.home() / ".mediariver" / "work" / spec.name

                session = get_session(engine)

                def is_known(conn: str, path: str, file_size: int, etag: str) -> bool:
                    result = session.query(ProcessedFile).filter_by(workflow_name=spec.name, file_path=path).first()
                    if not result:
                        return False
                    # Pending and failed should be picked up
                    if result.status in ("pending", "failed"):
                        return False
                    # Running files are in progress — skip
                    if result.status == "running":
                        return True
                    # Status is "done" — check if file content changed
                    if result.file_size != file_size or result.etag != etag:
                        log.info(
                            "file_changed_detected",
                            workflow=spec.name,
                            file=path,
                            old_size=result.file_size,
                            new_size=file_size,
                            old_etag=result.etag,
                            new_etag=etag,
                        )
                        return False  # treat as new — will be reprocessed
                    return True

                def on_new_file(path: str, file_hash: str, file_size: int, etag: str) -> None:
                    existing = session.query(ProcessedFile).filter_by(workflow_name=spec.name, file_path=path).first()

                    if not existing:
                        pf = ProcessedFile(
                            workflow_name=spec.name,
                            file_path=path,
                            file_hash=file_hash,
                            file_size=file_size,
                            etag=etag,
                            status="pending",
                        )
                        session.add(pf)
                        session.commit()
                        existing = pf

                    existing.status = "running"
                    existing.attempts += 1
                    existing.file_hash = file_hash
                    existing.file_size = file_size
                    existing.etag = etag
                    session.commit()

                    work_dir = work_base / file_hash
                    work_dir.mkdir(parents=True, exist_ok=True)

                    # Resolve to absolute system path; download from S3 if needed
                    try:
                        abs_path = watch_fs.getsyspath(path)
                    except Exception:
                        # S3 source: download to work_dir before running pipeline
                        local_path = work_dir / Path(path).name
                        key = watch_fs._path_to_key(path)
                        obj = watch_fs.s3.Object(watch_fs._bucket_name, key)
                        obj.download_file(str(local_path))
                        abs_path = str(local_path)

                    runner = PipelineRunner(
                        spec,
                        executor,
                        connections=connections,
                        work_dir=str(work_dir),
                    )
                    result = runner.run_file(abs_path, file_hash, original_path=path)

                    existing.status = result["status"]
                    existing.step_results = result.get("step_results", {})
                    existing.error = result.get("error")
                    existing.current_step = result.get("failed_step")
                    session.commit()

                    log.info("file_processed", workflow=spec.name, file=path, status=result["status"])

                new_count = poll_once(watch_fs, spec.watch, is_known, on_new_file)
                log.info("poll_complete", workflow=spec.name, new_files=new_count)
                session.close()

                import contextlib

                for fs in connections.values():
                    with contextlib.suppress(Exception):
                        fs.close()

            interval = parse_interval(specs[0].watch.poll_interval) if specs else 30
            time.sleep(interval)
    except KeyboardInterrupt:
        log.info("mediariver_stopped")


@app.command()
def validate(
    workflows_dir: Path = typer.Option(Path("./workflows"), help="Path to workflows directory"),
) -> None:
    """Validate all workflow specs without running them."""
    configure_logging("info")

    from mediariver.config.loader import load_workflows_from_dir
    from mediariver.config.validators import ValidationError as WfError
    from mediariver.config.validators import validate_workflow

    specs = load_workflows_from_dir(workflows_dir)
    errors = []
    for spec in specs:
        try:
            validate_workflow(spec)
            typer.echo(f"  OK: {spec.name}")
        except WfError as e:
            errors.append((spec.name, str(e)))
            typer.echo(f"  FAIL: {spec.name} — {e}")

    typer.echo(f"\n{len(specs)} workflow(s) checked, {len(errors)} error(s).")
    if errors:
        raise typer.Exit(1)


@app.command()
def status(
    workflow_name: str | None = typer.Argument(None, help="Filter by workflow name"),
    database_url: str | None = typer.Option(None, help="Database URL"),
) -> None:
    """Show processed file counts by status."""
    from sqlalchemy import func

    from mediariver.state.database import create_db_engine, create_tables, get_session
    from mediariver.state.models import ProcessedFile

    engine = create_db_engine(database_url)
    create_tables(engine)
    session = get_session(engine)

    query = session.query(
        ProcessedFile.workflow_name,
        ProcessedFile.status,
        func.count(ProcessedFile.id),
    ).group_by(ProcessedFile.workflow_name, ProcessedFile.status)

    if workflow_name:
        query = query.filter(ProcessedFile.workflow_name == workflow_name)

    results = query.all()
    if not results:
        typer.echo("No processed files found.")
        return

    for wf_name, file_status, count in results:
        typer.echo(f"  {wf_name}: {file_status} = {count}")

    session.close()


@app.command()
def retry(
    workflow_name: str = typer.Argument(..., help="Workflow name"),
    file_hash: str | None = typer.Option(None, help="Retry specific file by hash"),
    database_url: str | None = typer.Option(None, help="Database URL"),
) -> None:
    """Reset failed files to pending for reprocessing."""
    from mediariver.state.database import create_db_engine, create_tables, get_session
    from mediariver.state.models import ProcessedFile

    engine = create_db_engine(database_url)
    create_tables(engine)
    session = get_session(engine)

    query = session.query(ProcessedFile).filter_by(workflow_name=workflow_name, status="failed")
    if file_hash:
        query = query.filter_by(file_hash=file_hash)

    count = 0
    for pf in query.all():
        pf.status = "pending"
        pf.error = None
        count += 1

    session.commit()
    session.close()
    typer.echo(f"Reset {count} file(s) to pending.")


@app.command()
def reset(
    workflow_name: str = typer.Argument(..., help="Workflow name"),
    file_status: str | None = typer.Option(None, "--status", help="Only reset files with this status"),
    database_url: str | None = typer.Option(None, help="Database URL"),
) -> None:
    """Clear state for a workflow."""
    from mediariver.state.database import create_db_engine, create_tables, get_session
    from mediariver.state.models import ProcessedFile

    engine = create_db_engine(database_url)
    create_tables(engine)
    session = get_session(engine)

    query = session.query(ProcessedFile).filter_by(workflow_name=workflow_name)
    if file_status:
        query = query.filter_by(status=file_status)

    count = query.delete(synchronize_session="fetch")
    session.commit()
    session.close()
    typer.echo(f"Deleted {count} record(s) for '{workflow_name}'.")


def _log_hardware_info(executor, log) -> None:  # noqa: ANN001
    """Detect and log hardware capabilities on startup."""
    import shutil

    # ffmpeg
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        ver = executor.run(binary="ffmpeg", args=["-version"], docker_image="")
        first_line = ver.stdout.split("\n")[0] if ver.stdout else "unknown"
        log.info("ffmpeg_detected", path=ffmpeg_path, version=first_line)
    else:
        log.warning("ffmpeg_not_found", fallback="docker")

    # GPU / NVENC
    if ffmpeg_path:
        enc = executor.run(binary="ffmpeg", args=["-hide_banner", "-encoders"], docker_image="")
        gpu_encoders = []
        for line in enc.stdout.splitlines():
            if "nvenc" in line.lower():
                name = line.split()[1] if len(line.split()) > 1 else line.strip()
                gpu_encoders.append(name)
        if gpu_encoders:
            log.info("gpu_detected", encoders=gpu_encoders, hw_accel="nvenc")
        else:
            log.info("gpu_not_detected", hw_accel="cpu-only")

    # Docker
    docker_path = shutil.which("docker")
    if docker_path:
        docker_ver = executor.run(binary="docker", args=["--version"], docker_image="")
        ver_str = docker_ver.stdout.strip() if docker_ver.returncode == 0 else "unknown"
        log.info("docker_detected", version=ver_str)
    else:
        log.info("docker_not_available", note="actions requiring docker will fail")


@app.callback()
def main() -> None:
    """MediaRiver — Spec-driven media pipeline CLI."""
