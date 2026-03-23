"""Image pixel check action — conditionally passes based on total pixel count."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from mediariver.actions.base import ActionResult, BaseAction
from mediariver.actions.executor import CommandExecutor
from mediariver.actions.registry import register_action


class ImagePixelCheckParams(BaseModel):
    min_pixels: int | None = None
    max_pixels: int | None = None


@register_action("image.pixel_check")
class ImagePixelCheckAction(BaseAction):
    name = "image.pixel_check"
    params_model = ImagePixelCheckParams

    def run(
        self,
        context: dict[str, Any],
        params: ImagePixelCheckParams,
        executor: CommandExecutor,
        resolved_input: str | None = None,
    ) -> ActionResult:
        input_path = resolved_input or context["file"]["path"]

        result = executor.run(
            binary="identify",
            args=["-format", "%[fx:w*h]", input_path],
            docker_image="mediariver/imagemagick:latest",
        )

        if result.returncode != 0:
            raise RuntimeError(result.stderr)

        pixel_count = int(result.stdout.strip())

        if params.min_pixels is not None and pixel_count < params.min_pixels:
            raise RuntimeError(
                f"pixel count {pixel_count} is below minimum {params.min_pixels}"
            )

        if params.max_pixels is not None and pixel_count > params.max_pixels:
            raise RuntimeError(
                f"pixel count {pixel_count} is above maximum {params.max_pixels}"
            )

        return ActionResult(status="done", extras={"pixel_count": pixel_count})
