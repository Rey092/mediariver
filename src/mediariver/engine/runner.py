"""Sequential pipeline runner."""

from __future__ import annotations

import time
from typing import Any

import structlog

from mediariver.actions.base import ActionResult
from mediariver.actions.executor import CommandExecutor
from mediariver.actions.registry import ActionRegistry
from mediariver.config.schema import StepConfig, WorkflowSpec
from mediariver.engine.context import build_file_context, update_step_context
from mediariver.engine.errors import StepFailure, handle_step_failure
from mediariver.engine.template import evaluate_condition, resolve_dict, resolve_string

log = structlog.get_logger()


class PipelineRunner:
    """Executes a workflow's flow steps sequentially for a single file."""

    def __init__(
        self,
        workflow: WorkflowSpec,
        executor: CommandExecutor,
        connections: dict[str, Any] | None = None,
        work_dir: str | None = None,
    ) -> None:
        self.workflow = workflow
        self.executor = executor
        self.connections = connections or {}
        self.work_dir = work_dir or "/tmp"

    def run_file(
        self,
        file_path: str,
        file_hash: str,
        resume_from: str | None = None,
    ) -> dict[str, Any]:
        """Run all flow steps for a single file."""
        context = build_file_context(file_path, file_hash)
        context["_connections"] = self.connections
        context["_work_dir"] = self.work_dir
        step_results: dict[str, Any] = {}
        skipping = resume_from is not None

        for step in self.workflow.flow:
            if skipping:
                if step.id == resume_from:
                    skipping = False
                else:
                    continue

            try:
                result = self._run_step(step, context)
            except StepFailure as e:
                if e.should_retry:
                    retried = self._retry_step(step, context)
                    if retried is None:
                        step_results[step.id] = {"status": "failed", "error": str(e.error)}
                        return {
                            "status": "failed",
                            "error": str(e.error),
                            "step_results": step_results,
                            "failed_step": step.id,
                        }
                    result = retried
                else:
                    step_results[step.id] = {"status": "failed", "error": str(e.error)}
                    return {
                        "status": "failed",
                        "error": str(e.error),
                        "step_results": step_results,
                        "failed_step": step.id,
                    }

            update_step_context(context, step.id, result)
            step_results[step.id] = {
                "status": result.status,
                "output": result.output,
                "duration_ms": result.duration_ms,
                **result.extras,
            }

        return {"status": "done", "step_results": step_results}

    def _run_step(self, step: StepConfig, context: dict[str, Any]) -> ActionResult:
        log.info("step_start", step_id=step.id, action=step.action)

        if not evaluate_condition(step.condition, context):
            log.info("step_skipped_condition", step_id=step.id)
            return ActionResult(status="skipped")

        resolved_input = resolve_string(step.input, context) if step.input else None
        resolved_params = resolve_dict(step.params, context)

        action_cls = ActionRegistry.get(step.action)
        action = action_cls()
        validated_params = action.params_model(**resolved_params)

        start_ms = int(time.time() * 1000)
        try:
            result = action.run(context, validated_params, self.executor, resolved_input=resolved_input)
            result.duration_ms = int(time.time() * 1000) - start_ms
            log.info("step_done", step_id=step.id, duration_ms=result.duration_ms)
            return result
        except Exception as e:
            log.error("step_failed", step_id=step.id, error=str(e))
            return handle_step_failure(step, e, attempt=1)

    def _retry_step(self, step: StepConfig, context: dict[str, Any]) -> ActionResult | None:
        for attempt in range(2, step.max_retries + 1):
            log.info("step_retry", step_id=step.id, attempt=attempt)
            try:
                resolved_input = resolve_string(step.input, context) if step.input else None
                resolved_params = resolve_dict(step.params, context)

                action_cls = ActionRegistry.get(step.action)
                action = action_cls()
                validated_params = action.params_model(**resolved_params)

                start_ms = int(time.time() * 1000)
                result = action.run(context, validated_params, self.executor, resolved_input=resolved_input)
                result.duration_ms = int(time.time() * 1000) - start_ms
                log.info("step_retry_success", step_id=step.id, attempt=attempt)
                return result
            except Exception as e:
                log.error("step_retry_failed", step_id=step.id, attempt=attempt, error=str(e))
                try:
                    return handle_step_failure(step, e, attempt=attempt)
                except StepFailure as sf:
                    if not sf.should_retry:
                        return None
        return None
