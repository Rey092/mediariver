"""Audio info action — runs ffprobe and parses audio stream metadata."""

from __future__ import annotations

import json
from typing import Any

from mediariver.actions.base import ActionResult, BaseAction, EmptyParams
from mediariver.actions.executor import CommandExecutor
from mediariver.actions.registry import register_action


@register_action("audio.info")
class AudioInfoAction(BaseAction):
    name = "audio.info"
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

        audio_stream = next(
            (s for s in data.get("streams", []) if s.get("codec_type") == "audio"),
            {},
        )
        fmt = data.get("format", {})

        duration_str = audio_stream.get("duration") or fmt.get("duration")
        duration = float(duration_str) if duration_str else None
        duration_ms = int(duration * 1000) if duration is not None else None

        bit_rate_str = audio_stream.get("bit_rate")
        bit_rate = int(bit_rate_str) if bit_rate_str else None

        extras: dict[str, Any] = {
            "codec": audio_stream.get("codec_name"),
            "bit_rate": bit_rate,
            "sample_rate": audio_stream.get("sample_rate"),
            "channels": audio_stream.get("channels"),
            "duration": duration,
            "duration_ms": duration_ms,
        }

        return ActionResult(status="done", extras=extras)
