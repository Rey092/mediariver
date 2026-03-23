"""Step error handling: retry, skip, abort strategies."""

from __future__ import annotations

from mediariver.actions.base import ActionResult
from mediariver.config.schema import StepConfig


class StepFailure(Exception):
    """Raised when a step fails and cannot continue."""

    def __init__(self, step_id: str, error: Exception, should_retry: bool = False) -> None:
        self.step_id = step_id
        self.error = error
        self.should_retry = should_retry
        super().__init__(f"Step '{step_id}' failed: {error}")


def handle_step_failure(
    step: StepConfig,
    error: Exception,
    attempt: int,
) -> ActionResult:
    """Apply the step's on_failure strategy.

    Returns ActionResult with status="skipped" if strategy is skip.
    Raises StepFailure if strategy is abort or retry.
    """
    if step.on_failure == "skip":
        return ActionResult(status="skipped", output=None, duration_ms=0, extras={})

    if step.on_failure == "retry" and attempt < step.max_retries:
        raise StepFailure(step.id, error, should_retry=True)

    raise StepFailure(step.id, error, should_retry=False)
