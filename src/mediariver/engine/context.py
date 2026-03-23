"""Pipeline execution context management."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mediariver.actions.base import ActionResult


def build_file_context(file_path: str, file_hash: str) -> dict[str, Any]:
    """Build the initial context dict for a file being processed."""
    p = Path(file_path)
    return {
        "file": {
            "name": p.name,
            "stem": p.stem,
            "ext": p.suffix,
            "size": p.stat().st_size,
            "hash": file_hash,
            "path": str(p),
        },
        "env": dict(os.environ),
        "steps": {},
    }


def update_step_context(
    context: dict[str, Any],
    step_id: str,
    result: ActionResult,
) -> None:
    """Add a step's result to the context."""
    context["steps"][step_id] = {
        "status": result.status,
        "output": result.output,
        "duration_ms": result.duration_ms,
        **result.extras,
    }
