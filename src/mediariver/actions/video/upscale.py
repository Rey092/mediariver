"""Video upscale action — AI anime upscale with fallback chain."""

from __future__ import annotations

import os
from typing import Any, Literal

from pydantic import BaseModel, Field

from mediariver.actions.base import ActionResult, BaseAction
from mediariver.actions.executor import CommandExecutor
from mediariver.actions.registry import register_action


class VideoUpscaleParams(BaseModel):
    engine: Literal["dandere2x", "realesrgan", "lanczos"] = "realesrgan"
    scale: int = Field(default=2, ge=1)
    gpu: bool = True
    fallback: str | None = "lanczos"


def _run_dandere2x(
    executor: CommandExecutor,
    input_path: str,
    output_path: str,
    work_dir: str,
    gpu: bool,
) -> Any:
    input_name = os.path.basename(input_path)
    output_name = os.path.basename(output_path)
    args = [
        "-p", "singleprocess",
        "-ws", "./workspace/",
        "-i", f"/work/{input_name}",
        "-o", f"/work/{output_name}",
    ]
    return executor.run(
        binary="docker",
        args=args,
        docker_image="akaikatto/dandere2x",
        strategy="docker",
        gpu=gpu,
    )


def _run_realesrgan(
    executor: CommandExecutor,
    input_path: str,
    output_path: str,
    scale: int,
) -> Any:
    args = [
        "-i", input_path,
        "-o", output_path,
        "-s", str(scale),
        "-n", "realesrgan-x4plus-anime",
    ]
    return executor.run(
        binary="realesrgan-ncnn-vulkan",
        args=args,
        docker_image="mediariver/realesrgan:latest",
        strategy="docker",
    )


def _run_lanczos(
    executor: CommandExecutor,
    input_path: str,
    output_path: str,
    scale: int,
) -> Any:
    args = [
        "-i", input_path,
        "-vf", f"scale=iw*{scale}:ih*{scale}:flags=lanczos",
        "-y", output_path,
    ]
    return executor.run(
        binary="ffmpeg",
        args=args,
        docker_image="mediariver/ffmpeg:latest",
    )


def _run_engine(
    engine: str,
    executor: CommandExecutor,
    input_path: str,
    output_path: str,
    work_dir: str,
    scale: int,
    gpu: bool,
) -> Any:
    if engine == "dandere2x":
        return _run_dandere2x(executor, input_path, output_path, work_dir, gpu)
    elif engine == "realesrgan":
        return _run_realesrgan(executor, input_path, output_path, scale)
    elif engine == "lanczos":
        return _run_lanczos(executor, input_path, output_path, scale)
    else:
        raise ValueError(f"Unknown engine: {engine}")


@register_action("video.upscale")
class VideoUpscaleAction(BaseAction):
    name = "video.upscale"
    params_model = VideoUpscaleParams

    def run(
        self,
        context: dict[str, Any],
        params: VideoUpscaleParams,
        executor: CommandExecutor,
        resolved_input: str | None = None,
    ) -> ActionResult:
        input_path = resolved_input or context["file"]["path"]
        work_dir = context.get("_work_dir", "/tmp")
        stem = context["file"]["stem"]
        output_path = os.path.join(work_dir, f"{stem}_upscaled.mp4")

        result = _run_engine(
            params.engine,
            executor,
            input_path,
            output_path,
            work_dir,
            params.scale,
            params.gpu,
        )

        if result.returncode != 0 and params.fallback and params.fallback != params.engine:
            fallback_output = os.path.join(work_dir, f"{stem}_upscaled_fallback.mp4")
            result = _run_engine(
                params.fallback,
                executor,
                input_path,
                fallback_output,
                work_dir,
                params.scale,
                params.gpu,
            )
            output_path = fallback_output

        if result.returncode != 0:
            raise RuntimeError(result.stderr)

        return ActionResult(
            status="done",
            output=output_path,
            extras={"output": output_path, "engine": params.engine},
        )
