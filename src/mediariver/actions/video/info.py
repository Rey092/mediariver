"""Video info action — runs ffprobe and parses stream metadata."""

from __future__ import annotations

import json
from typing import Any

from mediariver.actions.base import ActionResult, BaseAction, EmptyParams
from mediariver.actions.executor import CommandExecutor
from mediariver.actions.registry import register_action


@register_action("video.info")
class VideoInfoAction(BaseAction):
    name = "video.info"
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
            binary="ffprobe",
            args=[
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_streams",
                "-show_format",
                input_path,
            ],
            docker_image="mediariver/ffmpeg:latest",
        )

        if result.returncode != 0:
            raise RuntimeError(result.stderr)

        data = json.loads(result.stdout)

        video_stream = next(
            (s for s in data.get("streams", []) if s.get("codec_type") == "video"),
            {},
        )
        fmt = data.get("format", {})

        fps = None
        r_frame_rate = video_stream.get("r_frame_rate")
        if r_frame_rate and "/" in r_frame_rate:
            num, den = r_frame_rate.split("/")
            if int(den) > 0:
                fps = round(int(num) / int(den), 3)

        duration_str = video_stream.get("duration") or fmt.get("duration")
        duration = float(duration_str) if duration_str else None

        bit_rate_str = video_stream.get("bit_rate")
        bit_rate = int(bit_rate_str) if bit_rate_str else None

        extras: dict[str, Any] = {
            "codec": video_stream.get("codec_name"),
            "width": video_stream.get("width"),
            "height": video_stream.get("height"),
            "fps": fps,
            "duration": duration,
            "bit_rate": bit_rate,
        }

        return ActionResult(status="done", extras=extras)
