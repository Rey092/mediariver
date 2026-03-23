"""Jinja2 template resolution for workflow specs."""

from __future__ import annotations

from typing import Any

from jinja2 import Environment, Undefined


class _SilentUndefined(Undefined):
    """Return empty string for undefined variables instead of raising."""

    def __str__(self) -> str:
        return ""

    def __bool__(self) -> bool:
        return False

    def __iter__(self):
        return iter([])

    def __getattr__(self, name: str) -> _SilentUndefined:
        return self


_env = Environment(undefined=_SilentUndefined)


def resolve_string(template: str, context: dict[str, Any]) -> str:
    """Resolve a Jinja2 template string against a context dict."""
    return _env.from_string(template).render(**context)


def resolve_value(value: Any, context: dict[str, Any]) -> Any:
    """Resolve a single value — string gets template resolution, others pass through."""
    if isinstance(value, str):
        return resolve_string(value, context)
    if isinstance(value, dict):
        return resolve_dict(value, context)
    if isinstance(value, list):
        return [resolve_value(item, context) for item in value]
    return value


def resolve_dict(params: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Recursively resolve all string values in a dict."""
    return {key: resolve_value(val, context) for key, val in params.items()}


def evaluate_condition(condition: str | None, context: dict[str, Any]) -> bool:
    """Evaluate a condition expression. None means always true."""
    if condition is None:
        return True
    result = resolve_string(condition, context).strip()
    return result.lower() not in ("", "false", "0", "none")
