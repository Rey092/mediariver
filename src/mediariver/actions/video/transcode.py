"""Video transcode action — converts video using named presets."""

from __future__ import annotations

import os
from typing import Any, Literal

from pydantic import BaseModel, Field

from mediariver.actions.base import ActionResult, BaseAction
from mediariver.actions.executor import CommandExecutor
from mediariver.actions.registry import register_action


PRESETS: dict[str, dict[str, str]] = {
    "h264-web": {"codec": "libx264", "ext": "mp4"},
    "h264-fast": {"codec": "libx264", "ext": "mp4"},
    "h265-fast": {"codec": "libx265", "ext": "mp4"},
    "vp9": {"codec": "libvpx-vp9", "ext": "webm"},
    "av1": {"codec": "libaom-av1", "ext": "mp4"},
}


class VideoTranscodeParams(BaseModel):
    preset: Literal["h264-web", "h264-fast", "h265-fast", "vp9", "av1"] = "h264-web"
    crf: int = Field(default=18, ge=0, le=63)
    scale: str | None = None
    scale_flags: str = "lanczos"
    audio_codec: str = "aac"
    audio_bitrate: str = "192k"


@register_action("video.transcode")
class VideoTranscodeAction(BaseAction):
    name = "video.transcode"
    params_model = VideoTranscodeParams

    def run(
        self,
        context: dict[str, Any],
        params: VideoTranscodeParams,
        executor: CommandExecutor,
        resolved_input: str | None = None,
    ) -> ActionResult:
        input_path = resolved_input or context["file"]["path"]
        work_dir = context.get("_work_dir", "/tmp")
        stem = context["file"]["stem"]

        preset_cfg = PRESETS.get(params.preset, PRESETS["h264-web"])
        ext = preset_cfg["ext"]
        video_codec = preset_cfg["codec"]
        output_path = os.path.join(work_dir, f"{stem}_transcoded.{ext}")

        vf_filters = []
        if params.scale:
            vf_filters.append(f"scale={params.scale}:flags={params.scale_flags}")

        args = ["-i", input_path]

        if vf_filters:
            args += ["-vf", ",".join(vf_filters)]

        args += [
            "-c:v", video_codec,
            "-crf", str(params.crf),
            "-c:a", params.audio_codec,
            "-b:a", params.audio_bitrate,
            "-y", output_path,
        ]

        result = executor.run(
            binary="ffmpeg",
            args=args,
            docker_image="mediariver/ffmpeg:latest",
        )

        if result.returncode != 0:
            raise RuntimeError(result.stderr)

        return ActionResult(status="done", output=output_path, extras={"output": output_path, "preset": params.preset})
