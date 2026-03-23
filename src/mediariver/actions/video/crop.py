"""Video crop action — crops video by ratio or auto-detect."""

from __future__ import annotations

import os
from typing import Any, Literal

from pydantic import BaseModel, Field

from mediariver.actions.base import ActionResult, BaseAction
from mediariver.actions.executor import CommandExecutor
from mediariver.actions.registry import register_action


class VideoCropParams(BaseModel):
    mode: Literal["ratio", "auto"] = "ratio"
    ratio: str = "16:9"
    codec: str = "libx264"
    crf: int = Field(default=18, ge=0, le=51)
    preset: str = "fast"
    detect_threshold: float = 24.0


@register_action("video.crop")
class VideoCropAction(BaseAction):
    name = "video.crop"
    params_model = VideoCropParams

    def run(
        self,
        context: dict[str, Any],
        params: VideoCropParams,
        executor: CommandExecutor,
        resolved_input: str | None = None,
    ) -> ActionResult:
        input_path = resolved_input or context["file"]["path"]
        work_dir = context.get("_work_dir", "/tmp")
        stem = context["file"]["stem"]
        output_path = os.path.join(work_dir, f"{stem}_cropped.mp4")

        if params.mode == "ratio":
            w, h = params.ratio.split(":")
            # crop=w:h:(in_w-w)/2:(in_h-h)/2 using expression
            crop_filter = f"crop=iw:iw*{h}/{w}:(iw-iw)/2:(ih-iw*{h}/{w})/2"
        else:
            # auto-detect black bars
            crop_filter = f"cropdetect={params.detect_threshold}:2:0,crop"

        result = executor.run(
            binary="ffmpeg",
            args=[
                "-i",
                input_path,
                "-vf",
                crop_filter,
                "-c:v",
                params.codec,
                "-crf",
                str(params.crf),
                "-preset",
                params.preset,
                "-c:a",
                "copy",
                "-y",
                output_path,
            ],
            docker_image="mediariver/ffmpeg:latest",
        )

        if result.returncode != 0:
            raise RuntimeError(result.stderr)

        return ActionResult(status="done", output=output_path, extras={"output": output_path})
