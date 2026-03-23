"""Cross-filesystem copy action."""

from __future__ import annotations

from typing import Any

from fs.copy import copy_file
from pydantic import BaseModel, ConfigDict, Field

from mediariver.actions.base import ActionResult, BaseAction
from mediariver.actions.executor import CommandExecutor
from mediariver.actions.registry import register_action
from mediariver.connections.registry import resolve_connection_uri


class CopyParams(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_path: str = Field(alias="from")
    to_path: str = Field(alias="to")


@register_action("copy")
class CopyAction(BaseAction):
    name = "copy"
    params_model = CopyParams

    def run(
        self, context: dict[str, Any], params: CopyParams, executor: CommandExecutor, resolved_input: str | None = None
    ) -> ActionResult:
        connections = context.get("_connections", {})
        src_fs, src_path = resolve_connection_uri(params.from_path, connections)
        dst_fs, dst_path = resolve_connection_uri(params.to_path, connections)

        parent = "/".join(dst_path.split("/")[:-1])
        if parent:
            dst_fs.makedirs(parent, recreate=True)

        copy_file(src_fs, src_path, dst_fs, dst_path)
        return ActionResult(status="done", output=params.to_path)
