"""Tests for state persistence."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from mediariver.state.database import create_tables
from mediariver.state.models import ProcessedFile, WorkflowRun


@pytest.fixture
def db_session(tmp_path):
    db_url = f"sqlite:///{tmp_path}/test.db"
    engine = create_engine(db_url)
    create_tables(engine)
    with Session(engine) as session:
        yield session


class TestProcessedFile:
    def test_create_and_query(self, db_session):
        pf = ProcessedFile(
            workflow_name="video-pipeline",
            file_path="/media/video.mp4",
            file_hash="abc123",
            file_size=1024,
            status="pending",
        )
        db_session.add(pf)
        db_session.commit()

        result = db_session.query(ProcessedFile).filter_by(file_hash="abc123").one()
        assert result.workflow_name == "video-pipeline"
        assert result.status == "pending"
        assert result.attempts == 0

    def test_unique_constraint(self, db_session):
        """Same workflow + same file_path = conflict."""
        pf1 = ProcessedFile(
            workflow_name="wf",
            file_path="/a.mp4",
            file_hash="hash1",
            file_size=100,
            status="done",
        )
        pf2 = ProcessedFile(
            workflow_name="wf",
            file_path="/a.mp4",
            file_hash="hash2",
            file_size=200,
            status="pending",
        )
        db_session.add(pf1)
        db_session.commit()
        db_session.add(pf2)
        with pytest.raises(Exception):
            db_session.commit()

    def test_step_results_json(self, db_session):
        pf = ProcessedFile(
            workflow_name="wf",
            file_path="/a.mp4",
            file_hash="h2",
            file_size=100,
            status="running",
            step_results={"probe": {"status": "done", "output": "/tmp/out"}},
        )
        db_session.add(pf)
        db_session.commit()

        result = db_session.query(ProcessedFile).filter_by(file_hash="h2").one()
        assert result.step_results["probe"]["status"] == "done"

    def test_update_status(self, db_session):
        pf = ProcessedFile(
            workflow_name="wf",
            file_path="/a.mp4",
            file_hash="h3",
            file_size=100,
            status="pending",
        )
        db_session.add(pf)
        db_session.commit()

        pf.status = "running"
        pf.attempts += 1
        db_session.commit()

        result = db_session.query(ProcessedFile).filter_by(file_hash="h3").one()
        assert result.status == "running"
        assert result.attempts == 1


class TestWorkflowRun:
    def test_create_run(self, db_session):
        run = WorkflowRun(workflow_name="video-pipeline", files_found=10)
        db_session.add(run)
        db_session.commit()

        result = db_session.query(WorkflowRun).one()
        assert result.files_found == 10
        assert result.files_processed == 0
