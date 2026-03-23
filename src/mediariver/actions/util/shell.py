"""shell — arbitrary shell command execution."""

from __future__ import annotations

import subprocess
from typing import Any

from pydantic import BaseModel

from mediariver.actions.base import ActionResult, BaseAction
from mediariver.actions.executor import CommandExecutor
from mediariver.actions.registry import register_action


class ShellParams(BaseModel):
    command: str
    args: list[str] = []
    timeout: int = 300


@register_action("shell")
class ShellAction(BaseAction):
    name = "shell"
    params_model = ShellParams

    def run(self, context: dict[str, Any], params: ShellParams, executor: CommandExecutor, resolved_input: str | None = None) -> ActionResult:
        proc = subprocess.run(
            [params.command, *params.args],
            capture_output=True,
            text=True,
            timeout=params.timeout,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"Shell command failed: {proc.stderr}")
        return ActionResult(status="done", extras={"stdout": proc.stdout, "stderr": proc.stderr})
