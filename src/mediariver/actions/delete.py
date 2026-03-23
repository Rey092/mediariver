"""File deletion action."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from mediariver.actions.base import ActionResult, BaseAction
from mediariver.actions.executor import CommandExecutor
from mediariver.actions.registry import register_action
from mediariver.connections.registry import resolve_connection_uri


class DeleteParams(BaseModel):
    path: str


@register_action("delete")
class DeleteAction(BaseAction):
    name = "delete"
    params_model = DeleteParams

    def run(
        self,
        context: dict[str, Any],
        params: DeleteParams,
        executor: CommandExecutor,
        resolved_input: str | None = None,
    ) -> ActionResult:
        connections = context.get("_connections", {})
        fs, file_path = resolve_connection_uri(params.path, connections)
        fs.remove(file_path)
        return ActionResult(status="done")
