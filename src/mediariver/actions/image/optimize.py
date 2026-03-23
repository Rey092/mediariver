"""Image optimize action — lossy/lossless compression via various engines."""

from __future__ import annotations

import os
from typing import Any, Literal

from pydantic import BaseModel, Field

from mediariver.actions.base import ActionResult, BaseAction
from mediariver.actions.executor import CommandExecutor
from mediariver.actions.registry import register_action

_ENGINE_BINARY = {
    "mozjpeg": "cjpeg",
    "pngquant": "pngquant",
    "cjxl": "cjxl",
    "cavif": "cavif",
    "cwebp": "cwebp",
    "oxipng": "oxipng",
}

_ENGINE_DOCKER = {
    "mozjpeg": "mediariver/mozjpeg:latest",
    "pngquant": "mediariver/pngquant:latest",
    "cjxl": "mediariver/libjxl:latest",
    "cavif": "mediariver/cavif:latest",
    "cwebp": "mediariver/webp:latest",
    "oxipng": "mediariver/oxipng:latest",
}

_ENGINE_FORMAT = {
    "mozjpeg": "jpg",
    "pngquant": "png",
    "cjxl": "jxl",
    "cavif": "avif",
    "cwebp": "webp",
    "oxipng": "png",
}


class ImageOptimizeParams(BaseModel):
    engine: Literal["mozjpeg", "pngquant", "cjxl", "cavif", "cwebp", "oxipng"] = "cwebp"
    quality: int = Field(default=80, ge=0, le=100)
    lossless: bool = False
    format: str | None = None


@register_action("image.optimize")
class ImageOptimizeAction(BaseAction):
    name = "image.optimize"
    params_model = ImageOptimizeParams

    def run(
        self,
        context: dict[str, Any],
        params: ImageOptimizeParams,
        executor: CommandExecutor,
        resolved_input: str | None = None,
    ) -> ActionResult:
        input_path = resolved_input or context["file"]["path"]
        work_dir = context.get("_work_dir", "/tmp")
        stem = context["file"]["stem"]

        ext = params.format or _ENGINE_FORMAT.get(params.engine, "jpg")
        output_path = os.path.join(work_dir, f"{stem}_optimized.{ext}")

        binary = _ENGINE_BINARY.get(params.engine, "convert")
        docker_image = _ENGINE_DOCKER.get(params.engine, "mediariver/imagemagick:latest")

        # Fallback: use imagemagick convert
        args = [input_path, "-quality", str(params.quality), output_path]

        result = executor.run(
            binary=binary,
            args=args,
            docker_image=docker_image,
        )

        if result.returncode != 0:
            raise RuntimeError(result.stderr)

        return ActionResult(status="done", output=output_path, extras={"output": output_path})
