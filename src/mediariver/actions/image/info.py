"""Image info action — runs imagemagick identify and parses image metadata."""

from __future__ import annotations

from typing import Any

from mediariver.actions.base import ActionResult, BaseAction, EmptyParams
from mediariver.actions.executor import CommandExecutor
from mediariver.actions.registry import register_action


@register_action("image.info")
class ImageInfoAction(BaseAction):
    name = "image.info"
    params_model = EmptyParams

    def run(
        self,
        context: dict[str, Any],
        params: EmptyParams,
        executor: CommandExecutor,
        resolved_input: str | None = None,
    ) -> ActionResult:
        input_path = resolved_input or context["file"]["path"]

        result = executor.run(
            binary="identify",
            args=["-format", "%w %h %m %[colorspace] %[fx:w*h]", input_path],
            docker_image="mediariver/imagemagick:latest",
        )

        if result.returncode != 0:
            raise RuntimeError(result.stderr)

        parts = result.stdout.strip().split()
        width = int(parts[0])
        height = int(parts[1])
        fmt = parts[2]
        colorspace = parts[3]
        pixel_count = int(parts[4])

        if width > height:
            orientation = "landscape"
        elif height > width:
            orientation = "portrait"
        else:
            orientation = "square"

        extras: dict[str, Any] = {
            "width": width,
            "height": height,
            "format": fmt,
            "colorspace": colorspace,
            "pixel_count": pixel_count,
            "orientation": orientation,
        }

        return ActionResult(status="done", extras=extras)
