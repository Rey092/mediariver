"""Audio HLS action — produces audio-only adaptive-bitrate HLS output."""

from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel, Field

from mediariver.actions.base import ActionResult, BaseAction
from mediariver.actions.executor import CommandExecutor
from mediariver.actions.registry import register_action


class AudioHlsVariant(BaseModel):
    bitrate: str


class AudioHlsParams(BaseModel):
    variants: list[AudioHlsVariant] = Field(default_factory=list)
    segment_time: int = 10


@register_action("audio.hls")
class AudioHlsAction(BaseAction):
    name = "audio.hls"
    params_model = AudioHlsParams

    def run(
        self,
        context: dict[str, Any],
        params: AudioHlsParams,
        executor: CommandExecutor,
        resolved_input: str | None = None,
    ) -> ActionResult:
        input_path = resolved_input or context["file"]["path"]
        work_dir = context.get("_work_dir", "/tmp")
        stem = context["file"]["stem"]

        output_dir = os.path.join(work_dir, f"{stem}_audio_hls")
        os.makedirs(output_dir, exist_ok=True)

        for variant in params.variants:
            bitrate = variant.bitrate
            variant_dir = os.path.join(output_dir, bitrate)
            os.makedirs(variant_dir, exist_ok=True)

            playlist_path = os.path.join(variant_dir, "playlist.m3u8")

            result = executor.run(
                binary="ffmpeg",
                args=[
                    "-i", input_path,
                    "-map", "0:a",
                    "-c:a", "aac",
                    "-b:a", bitrate,
                    "-f", "hls",
                    "-hls_time", str(params.segment_time),
                    "-hls_playlist_type", "vod",
                    playlist_path,
                ],
                docker_image="mediariver/ffmpeg:latest",
            )

            if result.returncode != 0:
                raise RuntimeError(result.stderr)

        # Write master playlist
        master_path = os.path.join(output_dir, "master.m3u8")
        lines = ["#EXTM3U", "#EXT-X-VERSION:3"]
        for variant in params.variants:
            bitrate = variant.bitrate
            # Convert bitrate string like "128k" to bps integer
            bps = _bitrate_to_bps(bitrate)
            lines.append(f'#EXT-X-STREAM-INF:BANDWIDTH={bps},CODECS="mp4a.40.2"')
            lines.append(f"{bitrate}/playlist.m3u8")

        with open(master_path, "w") as f:
            f.write("\n".join(lines) + "\n")

        return ActionResult(
            status="done",
            output=master_path,
            extras={"output_dir": output_dir},
        )


def _bitrate_to_bps(bitrate: str) -> int:
    """Convert a bitrate string (e.g. '128k') to bits per second."""
    bitrate = bitrate.strip().lower()
    if bitrate.endswith("k"):
        return int(float(bitrate[:-1]) * 1000)
    if bitrate.endswith("m"):
        return int(float(bitrate[:-1]) * 1_000_000)
    return int(bitrate)
