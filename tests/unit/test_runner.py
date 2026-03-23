"""Tests for the pipeline runner."""

from unittest.mock import MagicMock

import pytest

from mediariver.actions.base import ActionResult, BaseAction, EmptyParams
from mediariver.actions.registry import ActionRegistry, register_action
from mediariver.config.schema import ConnectionConfig, StepConfig, WatchConfig, WorkflowSpec
from mediariver.engine.runner import PipelineRunner


@pytest.fixture(autouse=True)
def clear_registry():
    ActionRegistry._actions.clear()
    yield
    ActionRegistry._actions.clear()


def _make_workflow(flow: list[StepConfig]) -> WorkflowSpec:
    return WorkflowSpec(
        name="test-wf",
        connections={"local": ConnectionConfig(type="local")},
        watch=WatchConfig(connection="local", path="/tmp", extensions=[".mp4"]),
        flow=flow,
    )


class MockAction(BaseAction):
    name = "mock"
    params_model = EmptyParams
    call_count = 0
    last_context = None
    last_resolved_input = None

    def run(self, context, params, executor, resolved_input=None):
        MockAction.call_count += 1
        MockAction.last_context = context
        MockAction.last_resolved_input = resolved_input
        return ActionResult(status="done", output="/tmp/mock_output", duration_ms=100, extras={"mock_key": "mock_val"})


class FailingAction(BaseAction):
    name = "failing"
    params_model = EmptyParams

    def run(self, context, params, executor, resolved_input=None):
        raise RuntimeError("action failed")


class TestPipelineRunner:
    def setup_method(self):
        MockAction.call_count = 0
        MockAction.last_context = None
        MockAction.last_resolved_input = None

    def test_run_single_step(self, tmp_path):
        ActionRegistry.register("mock.action", MockAction)
        workflow = _make_workflow([
            StepConfig(id="step1", action="mock.action", input="{{file.path}}"),
        ])

        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"fake")

        runner = PipelineRunner(workflow, executor=MagicMock())
        result = runner.run_file(str(test_file), "fakehash")

        assert result["status"] == "done"
        assert MockAction.call_count == 1

    def test_run_multiple_steps_chain_context(self, tmp_path):
        ActionRegistry.register("mock.action", MockAction)
        workflow = _make_workflow([
            StepConfig(id="first", action="mock.action"),
            StepConfig(id="second", action="mock.action", input="{{steps.first.output}}"),
        ])

        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"fake")

        runner = PipelineRunner(workflow, executor=MagicMock())
        result = runner.run_file(str(test_file), "fakehash")

        assert result["status"] == "done"
        assert MockAction.call_count == 2

    def test_resolved_input_passed_to_action(self, tmp_path):
        ActionRegistry.register("mock.action", MockAction)
        workflow = _make_workflow([
            StepConfig(id="first", action="mock.action"),
            StepConfig(id="second", action="mock.action", input="{{steps.first.output}}"),
        ])

        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"fake")

        runner = PipelineRunner(workflow, executor=MagicMock())
        runner.run_file(str(test_file), "fakehash")

        # Second step should have resolved input = "/tmp/mock_output" (first step's output)
        assert MockAction.last_resolved_input == "/tmp/mock_output"

    def test_condition_skips_step(self, tmp_path):
        ActionRegistry.register("mock.action", MockAction)
        workflow = _make_workflow([
            StepConfig(id="first", action="mock.action"),
            StepConfig(id="skipped", action="mock.action", condition="{{false}}"),
        ])

        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"fake")

        runner = PipelineRunner(workflow, executor=MagicMock())
        result = runner.run_file(str(test_file), "fakehash")

        assert result["status"] == "done"
        assert MockAction.call_count == 1

    def test_abort_on_failure(self, tmp_path):
        ActionRegistry.register("failing.action", FailingAction)
        workflow = _make_workflow([
            StepConfig(id="fail_step", action="failing.action", on_failure="abort"),
        ])

        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"fake")

        runner = PipelineRunner(workflow, executor=MagicMock())
        result = runner.run_file(str(test_file), "fakehash")

        assert result["status"] == "failed"
        assert "action failed" in result["error"]

    def test_skip_on_failure(self, tmp_path):
        ActionRegistry.register("failing.action", FailingAction)
        ActionRegistry.register("mock.action", MockAction)
        workflow = _make_workflow([
            StepConfig(id="fail_step", action="failing.action", on_failure="skip"),
            StepConfig(id="after", action="mock.action"),
        ])

        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"fake")

        runner = PipelineRunner(workflow, executor=MagicMock())
        result = runner.run_file(str(test_file), "fakehash")

        assert result["status"] == "done"
        assert MockAction.call_count == 1

    def test_connections_and_work_dir_in_context(self, tmp_path):
        ActionRegistry.register("mock.action", MockAction)
        workflow = _make_workflow([
            StepConfig(id="step1", action="mock.action"),
        ])

        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"fake")

        mock_connections = {"local": "fake_fs"}
        runner = PipelineRunner(workflow, executor=MagicMock(), connections=mock_connections, work_dir="/tmp/work")
        runner.run_file(str(test_file), "fakehash")

        assert MockAction.last_context["_connections"] is mock_connections
        assert MockAction.last_context["_work_dir"] == "/tmp/work"
