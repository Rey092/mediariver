"""Pipeline execution context management."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mediariver.actions.base import ActionResult


def build_file_context(
    file_path: str, file_hash: str, original_path: str | None = None,
) -> dict[str, Any]:
    """Build the initial context dict for a file being processed."""
    p = Path(file_path)
    # Use original (S3) path for template fields like path_parts, relative_dir
    orig = Path(original_path) if original_path else p
    try:
        file_size = p.stat().st_size
    except OSError:
        file_size = 0
    return {
        "file": {
            "name": p.name,
            "stem": p.stem,
            "name_noext": p.stem,
            "ext": p.suffix,
            "size": file_size,
            "hash": file_hash,
            "path": str(p),
            "path_parts": [part for part in orig.parts if part != "/"],
            "relative_dir": str(orig.parent).lstrip("/\\"),
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
