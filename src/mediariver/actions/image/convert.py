"""Image convert action — convert between image formats using imagemagick."""

from __future__ import annotations

import os
from typing import Any, Literal

from pydantic import BaseModel, Field

from mediariver.actions.base import ActionResult, BaseAction
from mediariver.actions.executor import CommandExecutor
from mediariver.actions.registry import register_action

EXT_MAP: dict[str, str] = {
    "jpeg": "jpg",
    "png": "png",
    "webp": "webp",
    "avif": "avif",
    "jxl": "jxl",
}


class ImageConvertParams(BaseModel):
    format: Literal["jpeg", "png", "webp", "avif", "jxl"] = "jpeg"
    quality: int = Field(default=85)


@register_action("image.convert")
class ImageConvertAction(BaseAction):
    name = "image.convert"
    params_model = ImageConvertParams

    def run(
        self,
        context: dict[str, Any],
        params: ImageConvertParams,
        executor: CommandExecutor,
        resolved_input: str | None = None,
    ) -> ActionResult:
        input_path = resolved_input or context["file"]["path"]
        work_dir = context.get("_work_dir", "/tmp")
        stem = context["file"]["stem"]

        ext = EXT_MAP[params.format]
        output_path = os.path.join(work_dir, f"{stem}_converted.{ext}")

        result = executor.run(
            binary="convert",
            args=[input_path, "-quality", str(params.quality), output_path],
            docker_image="mediariver/imagemagick:latest",
        )

        if result.returncode != 0:
            raise RuntimeError(result.stderr)

        return ActionResult(
            status="done",
            output=output_path,
            extras={"output": output_path, "format": params.format},
        )
