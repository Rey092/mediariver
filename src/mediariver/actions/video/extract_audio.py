"""Video extract_audio action — demux audio stream from video."""

from __future__ import annotations

import os
from typing import Any, Literal

from pydantic import BaseModel, Field

from mediariver.actions.base import ActionResult, BaseAction
from mediariver.actions.executor import CommandExecutor
from mediariver.actions.registry import register_action

_CODEC_EXT: dict[str, str] = {
    "copy": "mka",
    "aac": "m4a",
    "flac": "flac",
    "mp3": "mp3",
}


class VideoExtractAudioParams(BaseModel):
    stream: int = Field(default=0, ge=0)
    codec: Literal["copy", "aac", "flac", "mp3"] = "copy"


@register_action("video.extract_audio")
class VideoExtractAudioAction(BaseAction):
    name = "video.extract_audio"
    params_model = VideoExtractAudioParams

    def run(
        self,
        context: dict[str, Any],
        params: VideoExtractAudioParams,
        executor: CommandExecutor,
        resolved_input: str | None = None,
    ) -> ActionResult:
        input_path = resolved_input or context["file"]["path"]
        work_dir = context.get("_work_dir", "/tmp")
        stem = context["file"]["stem"]

        ext = _CODEC_EXT.get(params.codec, "mka")
        output_path = os.path.join(work_dir, f"{stem}_audio.{ext}")

        args = [
            "-i",
            input_path,
            "-map",
            f"0:a:{params.stream}",
            "-c:a",
            params.codec,
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
            extras={"output": output_path, "codec": params.codec, "stream": params.stream},
        )
