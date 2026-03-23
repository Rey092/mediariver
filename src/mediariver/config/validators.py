"""Cross-field validation for workflow specs."""

from __future__ import annotations

from mediariver.config.schema import WorkflowSpec


class ValidationError(Exception):
    """Raised when a workflow spec fails cross-field validation."""


def validate_workflow(spec: WorkflowSpec) -> None:
    """Validate cross-field constraints on a workflow spec."""
    _validate_watch_connection(spec)


def _validate_watch_connection(spec: WorkflowSpec) -> None:
    if spec.watch.connection not in spec.connections:
        available = ", ".join(spec.connections.keys())
        raise ValidationError(
            f"Watch connection '{spec.watch.connection}' not found. "
            f"Available connections: {available}"
        )
