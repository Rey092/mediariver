"""Image crop action — auto-trim or manual crop using ImageMagick."""

from __future__ import annotations

import os
from typing import Any, Literal

from pydantic import BaseModel

from mediariver.actions.base import ActionResult, BaseAction
from mediariver.actions.executor import CommandExecutor
from mediariver.actions.registry import register_action


class CropRect(BaseModel):
    x: int = 0
    y: int = 0
    w: int
    h: int


class ImageCropParams(BaseModel):
    mode: Literal["auto", "manual"] = "auto"
    auto_color: Literal["white", "black", "detect"] = "white"
    rect: CropRect | None = None


@register_action("image.crop")
class ImageCropAction(BaseAction):
    name = "image.crop"
    params_model = ImageCropParams

    def run(
        self,
        context: dict[str, Any],
        params: ImageCropParams,
        executor: CommandExecutor,
        resolved_input: str | None = None,
    ) -> ActionResult:
        input_path = resolved_input or context["file"]["path"]
        work_dir = context.get("_work_dir", "/tmp")
        stem = context["file"]["stem"]
        ext = context["file"].get("ext", ".jpg")
        output_path = os.path.join(work_dir, f"{stem}_cropped{ext}")

        if params.mode == "auto":
            args = [input_path, "-trim", "+repage", output_path]
        else:
            rect = params.rect
            if rect is None:
                raise ValueError("rect is required for manual crop mode")
            crop_spec = f"{rect.w}x{rect.h}+{rect.x}+{rect.y}"
            args = [input_path, "-crop", crop_spec, "+repage", output_path]

        result = executor.run(
            binary="convert",
            args=args,
            docker_image="mediariver/imagemagick:latest",
        )

        if result.returncode != 0:
            raise RuntimeError(result.stderr)

        return ActionResult(status="done", output=output_path, extras={"output": output_path})
