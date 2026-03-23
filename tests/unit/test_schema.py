"""Tests for workflow YAML schema validation."""

import pytest
from pydantic import ValidationError

from mediariver.config.schema import (
    ConnectionConfig,
    StepConfig,
    WatchConfig,
    WorkflowSpec,
)


class TestConnectionConfig:
    def test_local_connection(self):
        conn = ConnectionConfig(type="local")
        assert conn.type == "local"

    def test_s3_connection(self):
        conn = ConnectionConfig(type="s3", bucket="my-bucket", prefix="output/")
        assert conn.type == "s3"
        assert conn.bucket == "my-bucket"

    def test_unknown_fields_allowed(self):
        conn = ConnectionConfig(type="s3", bucket="b", endpoint="http://localhost:9000")
        assert conn.endpoint == "http://localhost:9000"


class TestWatchConfig:
    def test_valid_watch(self):
        watch = WatchConfig(
            connection="local",
            path="/media/incoming",
            extensions=[".mp4", ".mkv"],
            poll_interval="30s",
        )
        assert watch.connection == "local"
        assert watch.extensions == [".mp4", ".mkv"]

    def test_default_poll_interval(self):
        watch = WatchConfig(connection="local", path="/media", extensions=[".mp4"])
        assert watch.poll_interval == "30s"


class TestStepConfig:
    def test_minimal_step(self):
        step = StepConfig(id="probe", action="video.info", input="{{file.path}}")
        assert step.id == "probe"
        assert step.on_failure == "abort"
        assert step.params == {}

    def test_step_with_params(self):
        step = StepConfig(
            id="crop",
            action="video.crop",
            input="{{file.path}}",
            params={"mode": "ratio", "ratio": "16:9"},
        )
        assert step.params["mode"] == "ratio"

    def test_step_with_condition_via_alias(self):
        """The YAML field is 'if' but Python uses 'condition' (reserved word)."""
        step = StepConfig(
            id="upscale",
            action="video.upscale",
            input="{{steps.crop.output}}",
            **{"if": "{{steps.info.width < 1200}}"},
            on_failure="skip",
        )
        assert step.condition == "{{steps.info.width < 1200}}"
        assert step.on_failure == "skip"

    def test_step_with_condition_via_name(self):
        step = StepConfig(
            id="upscale",
            action="video.upscale",
            condition="{{steps.info.width < 1200}}",
        )
        assert step.condition == "{{steps.info.width < 1200}}"

    def test_step_with_retry(self):
        step = StepConfig(
            id="transcode",
            action="video.transcode",
            input="{{file.path}}",
            on_failure="retry",
            max_retries=5,
            retry_delay="60s",
        )
        assert step.max_retries == 5

    def test_invalid_on_failure(self):
        with pytest.raises(ValidationError):
            StepConfig(id="x", action="y", on_failure="explode")

    def test_step_without_input(self):
        step = StepConfig(id="notify", action="http.post", params={"url": "http://example.com"})
        assert step.input is None


class TestWorkflowSpec:
    def test_valid_workflow(self):
        spec = WorkflowSpec(
            name="test-pipeline",
            description="A test pipeline",
            connections={
                "local": ConnectionConfig(type="local"),
            },
            watch=WatchConfig(
                connection="local",
                path="/media/incoming",
                extensions=[".mp4"],
            ),
            flow=[
                StepConfig(id="probe", action="video.info", input="{{file.path}}"),
            ],
        )
        assert spec.name == "test-pipeline"
        assert len(spec.flow) == 1

    def test_duplicate_step_ids_rejected(self):
        with pytest.raises(ValidationError, match="Duplicate step"):
            WorkflowSpec(
                name="bad",
                connections={"local": ConnectionConfig(type="local")},
                watch=WatchConfig(connection="local", path="/m", extensions=[".mp4"]),
                flow=[
                    StepConfig(id="same", action="video.info"),
                    StepConfig(id="same", action="video.crop"),
                ],
            )
