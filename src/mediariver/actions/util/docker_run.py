"""docker — arbitrary Docker container execution."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from mediariver.actions.base import ActionResult, BaseAction
from mediariver.actions.executor import CommandExecutor
from mediariver.actions.registry import register_action


class DockerRunParams(BaseModel):
    image: str
    command: str = ""
    args: list[str] = []
    gpu: bool = False
    volumes: dict[str, str] = {}
    env: dict[str, str] = {}


@register_action("docker")
class DockerRunAction(BaseAction):
    name = "docker"
    params_model = DockerRunParams

    def run(
        self,
        context: dict[str, Any],
        params: DockerRunParams,
        executor: CommandExecutor,
        resolved_input: str | None = None,
    ) -> ActionResult:
        result = executor.run(
            binary=params.command or "sh",
            args=params.args,
            docker_image=params.image,
            volumes=params.volumes or None,
            gpu=params.gpu,
            env=params.env or None,
            strategy="docker",
        )
        if result.returncode != 0:
            raise RuntimeError(f"Docker run failed: {result.stderr}")
        return ActionResult(status="done", extras={"stdout": result.stdout})
