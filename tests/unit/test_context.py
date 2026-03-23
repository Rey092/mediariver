"""Tests for pipeline execution context."""

import os

from mediariver.engine.context import build_file_context, update_step_context
from mediariver.actions.base import ActionResult


class TestBuildFileContext:
    def test_file_context_fields(self, tmp_path):
        test_file = tmp_path / "video.mp4"
        test_file.write_bytes(b"fake video content")
        ctx = build_file_context(str(test_file), file_hash="abc123")
        assert ctx["file"]["name"] == "video.mp4"
        assert ctx["file"]["stem"] == "video"
        assert ctx["file"]["ext"] == ".mp4"
        assert ctx["file"]["hash"] == "abc123"
        assert ctx["file"]["size"] == 18
        assert ctx["file"]["path"] == str(test_file)

    def test_env_populated(self, tmp_path):
        test_file = tmp_path / "f.mp4"
        test_file.write_bytes(b"x")
        os.environ["TEST_MEDIARIVER_VAR"] = "hello"
        ctx = build_file_context(str(test_file), file_hash="h")
        assert ctx["env"]["TEST_MEDIARIVER_VAR"] == "hello"
        del os.environ["TEST_MEDIARIVER_VAR"]

    def test_steps_starts_empty(self, tmp_path):
        test_file = tmp_path / "f.mp4"
        test_file.write_bytes(b"x")
        ctx = build_file_context(str(test_file), file_hash="h")
        assert ctx["steps"] == {}


class TestUpdateStepContext:
    def test_adds_step_result(self):
        ctx = {"steps": {}}
        result = ActionResult(
            status="done",
            output="/tmp/out.mp4",
            duration_ms=1234,
            extras={"width": 1920, "height": 1080},
        )
        update_step_context(ctx, "probe", result)
        assert ctx["steps"]["probe"]["status"] == "done"
        assert ctx["steps"]["probe"]["output"] == "/tmp/out.mp4"
        assert ctx["steps"]["probe"]["duration_ms"] == 1234
        assert ctx["steps"]["probe"]["width"] == 1920

    def test_skipped_step(self):
        ctx = {"steps": {}}
        result = ActionResult(status="skipped", output=None, duration_ms=0, extras={})
        update_step_context(ctx, "upscale", result)
        assert ctx["steps"]["upscale"]["status"] == "skipped"
        assert ctx["steps"]["upscale"]["output"] is None
