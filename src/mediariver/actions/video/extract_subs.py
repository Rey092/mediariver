"""Video extract_subs action — extract subtitle tracks from video."""

from __future__ import annotations

import os
from typing import Any, Literal

from pydantic import BaseModel, Field

from mediariver.actions.base import ActionResult, BaseAction
from mediariver.actions.executor import CommandExecutor
from mediariver.actions.registry import register_action


class VideoExtractSubsParams(BaseModel):
    format: Literal["srt", "ass", "vtt"] = "srt"
    stream: Literal["all"] | int = Field(default="all")


@register_action("video.extract_subs")
class VideoExtractSubsAction(BaseAction):
    name = "video.extract_subs"
    params_model = VideoExtractSubsParams

    def run(
        self,
        context: dict[str, Any],
        params: VideoExtractSubsParams,
        executor: CommandExecutor,
        resolved_input: str | None = None,
    ) -> ActionResult:
        input_path = resolved_input or context["file"]["path"]
        work_dir = context.get("_work_dir", "/tmp")
        stem = context["file"]["stem"]

        stream_index = 0 if params.stream == "all" else params.stream
        output_path = os.path.join(work_dir, f"{stem}_subs_{stream_index}.{params.format}")

        args = [
            "-i",
            input_path,
            "-map",
            f"0:s:{stream_index}",
            "-y",
            output_path,
        ]

        result = executor.run(
            binary="ffmpeg",
            args=args,
            docker_image="mediariver/ffmpeg:latest",
        )

        if result.returncode != 0:
            raise RuntimeError(result.stderr)

        return ActionResult(
            status="done",
            output=output_path,
            extras={"output": output_path, "format": params.format, "stream": stream_index},
        )
