"""Image upscale action — AI upscaling for manga/cover art."""

from __future__ import annotations

import os
from typing import Any, Literal

from pydantic import BaseModel, Field

from mediariver.actions.base import ActionResult, BaseAction
from mediariver.actions.executor import CommandExecutor
from mediariver.actions.registry import register_action

_ENGINE_CONFIG = {
    "realesrgan": {
        "binary": "realesrgan-ncnn-vulkan",
        "docker_image": "mediariver/realesrgan:latest",
        "model": "realesrgan-x4plus-anime",
    },
    "waifu2x": {
        "binary": "waifu2x-ncnn-vulkan",
        "docker_image": "mediariver/waifu2x:latest",
        "model": "cunet",
    },
}


class ImageUpscaleParams(BaseModel):
    engine: Literal["realesrgan", "waifu2x"] = "realesrgan"
    scale: Literal[2, 4] = 2
    denoise: int = Field(default=1, ge=0, le=3)


@register_action("image.upscale")
class ImageUpscaleAction(BaseAction):
    name = "image.upscale"
    params_model = ImageUpscaleParams

    def run(
        self,
        context: dict[str, Any],
        params: ImageUpscaleParams,
        executor: CommandExecutor,
        resolved_input: str | None = None,
    ) -> ActionResult:
        input_path = resolved_input or context["file"]["path"]
        work_dir = context.get("_work_dir", "/tmp")
        stem = context["file"]["stem"]
        ext = context["file"].get("ext", ".jpg")
        output_path = os.path.join(work_dir, f"{stem}_upscaled{ext}")

        config = _ENGINE_CONFIG[params.engine]
        binary = config["binary"]
        docker_image = config["docker_image"]
        model = config["model"]

        args = [
            "-i",
            input_path,
            "-o",
            output_path,
            "-s",
            str(params.scale),
            "-n",
            model,
        ]

        result = executor.run(
            binary=binary,
            args=args,
            docker_image=docker_image,
            strategy="docker",
        )

        if result.returncode != 0:
            raise RuntimeError(result.stderr)

        return ActionResult(status="done", output=output_path, extras={"output": output_path})
