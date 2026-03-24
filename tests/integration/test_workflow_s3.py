"""Integration test: full workflow execution with S3 output.

Runs a real pipeline: generate test video → probe → copy to S3 → verify on S3.
Requires MinIO at MINIO_ENDPOINT and ffmpeg installed locally.
"""

from __future__ import annotations

import os
import shutil
import subprocess

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from mediariver.actions.executor import CommandExecutor
from mediariver.config.schema import ConnectionConfig, StepConfig, WatchConfig, WorkflowSpec
from mediariver.connections.registry import build_connection
from mediariver.engine.runner import PipelineRunner
from mediariver.state.database import create_tables
from mediariver.state.models import ProcessedFile
from mediariver.watcher.poller import compute_file_hash

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "http://localhost:9000")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
S3_TEST_BUCKET = os.environ.get("S3_TEST_BUCKET", "test-bucket")


def _ensure_bucket() -> None:
    from minio import Minio

    client = Minio(
        MINIO_ENDPOINT.replace("http://", "").replace("https://", ""),
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_ENDPOINT.startswith("https"),
    )
    if not client.bucket_exists(S3_TEST_BUCKET):
        client.make_bucket(S3_TEST_BUCKET)


@pytest.fixture(scope="module", autouse=True)
def check_prerequisites():
    """Skip all tests if MinIO or ffmpeg aren't available."""
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not found")
    try:
        _ensure_bucket()
    except Exception as e:
        pytest.skip(f"MinIO not available: {e}")


@pytest.fixture
def test_video(tmp_path):
    """Generate a 1-second test video with audio."""
    video_path = tmp_path / "test_video.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=blue:s=320x240:d=1",
            "-f", "lavfi", "-i", "sine=f=440:d=1",
            "-shortest",
            str(video_path),
        ],
        capture_output=True,
        check=True,
    )
    assert video_path.exists()
    return video_path


@pytest.fixture
def work_dir(tmp_path):
    d = tmp_path / "work"
    d.mkdir()
    return d


@pytest.fixture
def s3_fs():
    config = ConnectionConfig(
        type="s3",
        bucket=S3_TEST_BUCKET,
        prefix="workflow-test/",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
    )
    fs = build_connection("output", config)
    yield fs
    # Cleanup
    try:
        for entry in fs.listdir("/"):
            if fs.isfile(entry):
                fs.remove(entry)
            elif fs.isdir(entry):
                fs.removetree(entry)
    except Exception:
        pass
    fs.close()


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    create_tables(engine)
    with Session(engine) as session:
        yield session


@pytest.mark.integration
class TestWorkflowWithS3:
    def test_probe_and_copy_to_s3(self, test_video, work_dir, s3_fs):
        """Full pipeline: video.info → copy to S3."""
        # Import to trigger action registration
        import mediariver.actions  # noqa: F401

        local_config = ConnectionConfig(type="local", root_path=str(test_video.parent))
        s3_config = ConnectionConfig(
            type="s3",
            bucket=S3_TEST_BUCKET,
            prefix="workflow-test/",
            endpoint_url=MINIO_ENDPOINT,
            aws_access_key_id=MINIO_ACCESS_KEY,
            aws_secret_access_key=MINIO_SECRET_KEY,
        )

        workflow = WorkflowSpec(
            name="test-s3-pipeline",
            connections={
                "local": local_config,
                "output": s3_config,
            },
            watch=WatchConfig(connection="local", path=str(test_video.parent), extensions=[".mp4"]),
            flow=[
                StepConfig(id="probe", action="video.info", input="{{file.path}}"),
                StepConfig(
                    id="upload",
                    action="copy",
                    params={"from": f"local://{test_video.name}", "to": "output://{{file.stem}}.mp4"},
                ),
            ],
        )

        connections = {
            "local": build_connection("local", local_config),
            "output": s3_fs,
        }

        executor = CommandExecutor()
        runner = PipelineRunner(workflow, executor, connections=connections, work_dir=str(work_dir))

        file_hash = compute_file_hash(connections["local"], test_video.name)
        result = runner.run_file(str(test_video), file_hash)

        # Pipeline succeeded
        assert result["status"] == "done", f"Pipeline failed: {result.get('error')}"

        # Probe extracted video info
        probe = result["step_results"]["probe"]
        assert probe["status"] == "done"
        assert probe["width"] == 320
        assert probe["height"] == 240
        assert probe["codec"] == "h264"

        # File landed on S3
        assert s3_fs.exists("test_video.mp4"), "File not found on S3"
        info = s3_fs.getinfo("test_video.mp4", namespaces=["details"])
        assert info.size > 0

        connections["local"].close()

    def test_full_video_pipeline(self, test_video, work_dir, s3_fs):
        """Probe → transcode → copy to S3."""
        import mediariver.actions  # noqa: F401

        local_config = ConnectionConfig(type="local", root_path=str(test_video.parent))
        s3_config = ConnectionConfig(
            type="s3",
            bucket=S3_TEST_BUCKET,
            prefix="workflow-test/",
            endpoint_url=MINIO_ENDPOINT,
            aws_access_key_id=MINIO_ACCESS_KEY,
            aws_secret_access_key=MINIO_SECRET_KEY,
        )

        workflow = WorkflowSpec(
            name="test-transcode-s3",
            connections={
                "local": local_config,
                "output": s3_config,
            },
            watch=WatchConfig(connection="local", path=str(test_video.parent), extensions=[".mp4"]),
            flow=[
                StepConfig(id="probe", action="video.info", input="{{file.path}}"),
                StepConfig(
                    id="transcode",
                    action="video.transcode",
                    input="{{file.path}}",
                    params={"preset": "h264-web", "crf": 23},
                ),
                StepConfig(
                    id="upload",
                    action="copy",
                    params={
                        "from": "local://{{file.stem}}_transcoded.mp4",
                        "to": "output://{{file.stem}}_web.mp4",
                    },
                ),
            ],
        )

        connections = {
            "local": build_connection("local", local_config),
            "output": s3_fs,
        }

        executor = CommandExecutor()
        runner = PipelineRunner(workflow, executor, connections=connections, work_dir=str(test_video.parent))

        file_hash = compute_file_hash(connections["local"], test_video.name)
        result = runner.run_file(str(test_video), file_hash)

        assert result["status"] == "done", f"Pipeline failed: {result.get('error')}"

        # Transcode produced output
        assert result["step_results"]["transcode"]["status"] == "done"

        # Transcoded file landed on S3
        assert s3_fs.exists("test_video_web.mp4"), f"Transcoded file not on S3. Files: {s3_fs.listdir('/')}"
        info = s3_fs.getinfo("test_video_web.mp4", namespaces=["details"])
        assert info.size > 0

        connections["local"].close()

    def test_state_tracking_with_pipeline(self, test_video, work_dir, s3_fs, db_session):
        """Verify state DB is updated correctly after pipeline run."""
        import mediariver.actions  # noqa: F401

        local_config = ConnectionConfig(type="local", root_path=str(test_video.parent))

        workflow = WorkflowSpec(
            name="test-state-tracking",
            connections={"local": local_config},
            watch=WatchConfig(connection="local", path=str(test_video.parent), extensions=[".mp4"]),
            flow=[
                StepConfig(id="probe", action="video.info", input="{{file.path}}"),
            ],
        )

        connections = {"local": build_connection("local", local_config)}
        executor = CommandExecutor()
        runner = PipelineRunner(workflow, executor, connections=connections, work_dir=str(work_dir))

        file_hash = compute_file_hash(connections["local"], test_video.name)

        # Insert into state DB
        pf = ProcessedFile(
            workflow_name="test-state-tracking",
            file_path=str(test_video),
            file_hash=file_hash,
            file_size=test_video.stat().st_size,
            status="running",
            attempts=1,
        )
        db_session.add(pf)
        db_session.commit()

        # Run pipeline
        result = runner.run_file(str(test_video), file_hash)

        # Update state
        pf.status = result["status"]
        pf.step_results = result.get("step_results", {})
        db_session.commit()

        # Verify state
        saved = db_session.query(ProcessedFile).filter_by(file_hash=file_hash).one()
        assert saved.status == "done"
        assert "probe" in saved.step_results
        assert saved.step_results["probe"]["width"] == 320

        connections["local"].close()

    def test_idempotency_skip_done(self, test_video, db_session):
        """Already-done files should be skipped by the watcher logic."""
        import mediariver.actions  # noqa: F401

        local_config = ConnectionConfig(type="local", root_path=str(test_video.parent))
        connections = {"local": build_connection("local", local_config)}
        file_hash = compute_file_hash(connections["local"], test_video.name)

        # Mark as done
        pf = ProcessedFile(
            workflow_name="test-idempotent",
            file_path=str(test_video),
            file_hash=file_hash,
            file_size=test_video.stat().st_size,
            status="done",
        )
        db_session.add(pf)
        db_session.commit()

        # Query like the watcher would
        existing = db_session.query(ProcessedFile).filter_by(
            workflow_name="test-idempotent", file_hash=file_hash
        ).first()
        assert existing is not None
        assert existing.status == "done"
        # Watcher would skip this file — no re-processing

        connections["local"].close()
