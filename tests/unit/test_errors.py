"""Tests for step error handling strategies."""

import pytest

from mediariver.engine.errors import StepFailure, handle_step_failure
from mediariver.config.schema import StepConfig


class TestHandleStepFailure:
    def test_abort_raises(self):
        step = StepConfig(id="s1", action="video.info", on_failure="abort")
        with pytest.raises(StepFailure, match="s1"):
            handle_step_failure(step, Exception("boom"), attempt=1)

    def test_skip_returns_skipped(self):
        step = StepConfig(id="s1", action="video.info", on_failure="skip")
        result = handle_step_failure(step, Exception("boom"), attempt=1)
        assert result.status == "skipped"

    def test_retry_under_max_raises_retry(self):
        step = StepConfig(id="s1", action="video.info", on_failure="retry", max_retries=3)
        with pytest.raises(StepFailure) as exc_info:
            handle_step_failure(step, Exception("boom"), attempt=1)
        assert exc_info.value.should_retry is True

    def test_retry_at_max_raises_final(self):
        step = StepConfig(id="s1", action="video.info", on_failure="retry", max_retries=3)
        with pytest.raises(StepFailure) as exc_info:
            handle_step_failure(step, Exception("boom"), attempt=3)
        assert exc_info.value.should_retry is False
