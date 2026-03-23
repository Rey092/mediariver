"""Audio convert action — convert between audio codecs."""

from __future__ import annotations

import os
from typing import Any, Literal

from pydantic import BaseModel, Field

from mediariver.actions.base import ActionResult, BaseAction
from mediariver.actions.executor import CommandExecutor
from mediariver.actions.registry import register_action

CODEC_MAP: dict[str, str] = {
    "aac": "-c:a aac",
    "mp3": "-c:a libmp3lame",
    "flac": "-c:a flac",
    "ogg": "-c:a libvorbis",
    "opus": "-c:a libopus",
    "wav": "-c:a pcm_s16le",
    "alac": "-c:a alac",
}

EXT_MAP: dict[str, str] = {
    "aac": "m4a",
    "mp3": "mp3",
    "flac": "flac",
    "ogg": "ogg",
    "opus": "opus",
    "wav": "wav",
    "alac": "m4a",
}


class AudioConvertParams(BaseModel):
    codec: Literal["aac", "mp3", "flac", "ogg", "opus", "wav", "alac"] = "aac"
    bitrate: str = "256k"
    sample_rate: int | None = Field(default=None)


@register_action("audio.convert")
class AudioConvertAction(BaseAction):
    name = "audio.convert"
    params_model = AudioConvertParams

    def run(
        self,
        context: dict[str, Any],
        params: AudioConvertParams,
        executor: CommandExecutor,
        resolved_input: str | None = None,
    ) -> ActionResult:
        input_path = resolved_input or context["file"]["path"]
        work_dir = context.get("_work_dir", "/tmp")
        stem = context["file"]["stem"]

        ext = EXT_MAP[params.codec]
        output_path = os.path.join(work_dir, f"{stem}_converted.{ext}")

        codec_flags = CODEC_MAP[params.codec].split()

        args = ["-i", input_path]
        args += codec_flags

        # Only add bitrate for lossy codecs that support it
        if params.codec not in ("flac", "wav", "alac"):
            args += ["-b:a", params.bitrate]

        if params.sample_rate is not None:
            args += ["-ar", str(params.sample_rate)]

        args += ["-y", output_path]

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
            extras={"output": output_path, "codec": params.codec},
        )
