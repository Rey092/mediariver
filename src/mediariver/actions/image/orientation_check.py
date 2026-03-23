"""Image orientation check action — conditionally passes based on image orientation."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from mediariver.actions.base import ActionResult, BaseAction
from mediariver.actions.executor import CommandExecutor
from mediariver.actions.registry import register_action


class ImageOrientationCheckParams(BaseModel):
    expect: Literal["landscape", "portrait", "square"]


@register_action("image.orientation_check")
class ImageOrientationCheckAction(BaseAction):
    name = "image.orientation_check"
    params_model = ImageOrientationCheckParams

    def run(
        self,
        context: dict[str, Any],
        params: ImageOrientationCheckParams,
        executor: CommandExecutor,
        resolved_input: str | None = None,
    ) -> ActionResult:
        input_path = resolved_input or context["file"]["path"]

        result = executor.run(
            binary="identify",
            args=["-format", "%w %h", input_path],
            docker_image="mediariver/imagemagick:latest",
        )

        if result.returncode != 0:
            raise RuntimeError(result.stderr)

        parts = result.stdout.strip().split()
        width = int(parts[0])
        height = int(parts[1])

        if width > height:
            actual = "landscape"
        elif height > width:
            actual = "portrait"
        else:
            actual = "square"

        if actual != params.expect:
            raise RuntimeError(
                f"orientation mismatch: expected {params.expect!r}, got {actual!r}"
            )

        return ActionResult(status="done", extras={"orientation": actual})
