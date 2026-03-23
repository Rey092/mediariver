"""Video HLS action — produces adaptive-bitrate HLS output with multiple variants."""

from __future__ import annotations

import os
from typing import Any, Literal

from pydantic import BaseModel, Field

from mediariver.actions.base import ActionResult, BaseAction
from mediariver.actions.executor import CommandExecutor
from mediariver.actions.registry import register_action


class HlsVariant(BaseModel):
    height: int
    video_bitrate: str
    audio_bitrate: str
    codec: str = "libx264"
    profile: str = "main"
    level: str = "4.0"


class VideoHlsParams(BaseModel):
    variants: list[HlsVariant] = Field(default_factory=list)
    segment_time: int = 6
    playlist_type: Literal["vod", "event"] = "vod"
    tier_playlists: bool = True


@register_action("video.hls")
class VideoHlsAction(BaseAction):
    name = "video.hls"
    params_model = VideoHlsParams

    def run(
        self,
        context: dict[str, Any],
        params: VideoHlsParams,
        executor: CommandExecutor,
        resolved_input: str | None = None,
    ) -> ActionResult:
        input_path = resolved_input or context["file"]["path"]
        work_dir = context.get("_work_dir", "/tmp")
        stem = context["file"]["stem"]

        output_dir = os.path.join(work_dir, f"{stem}_hls")
        os.makedirs(output_dir, exist_ok=True)

        n = len(params.variants)

        # Build filter_complex: split video and audio into n streams each
        split_video = f"[0:v]split={n}" + "".join(f"[v{i}]" for i in range(n))
        split_audio = f"[0:a]asplit={n}" + "".join(f"[a{i}]" for i in range(n))
        filter_complex = f"{split_video};{split_audio}"

        # Scale each video stream
        scale_parts = []
        for i, variant in enumerate(params.variants):
            scale_parts.append(
                f"[v{i}]scale=-2:{variant.height}[vout{i}]"
            )
        filter_complex = filter_complex + ";" + ";".join(scale_parts)

        args = ["-i", input_path, "-filter_complex", filter_complex]

        # Map each variant
        for i, variant in enumerate(params.variants):
            args += [
                "-map", f"[vout{i}]",
                "-map", f"[a{i}]",
                f"-c:v:{i}", variant.codec,
                f"-profile:v:{i}", variant.profile,
                f"-level:v:{i}", variant.level,
                f"-b:v:{i}", variant.video_bitrate,
                f"-c:a:{i}", "aac",
                f"-b:a:{i}", variant.audio_bitrate,
            ]

        # HLS output options
        args += [
            "-f", "hls",
            "-hls_time", str(params.segment_time),
            "-hls_playlist_type", params.playlist_type.upper(),
            "-hls_flags", "independent_segments",
            "-hls_segment_type", "mpegts",
            "-hls_segment_filename", os.path.join(output_dir, "stream_%v_%03d.ts"),
            "-master_pl_name", "master.m3u8",
            "-var_stream_map",
            " ".join(f"v:{i},a:{i}" for i in range(n)),
            os.path.join(output_dir, "stream_%v.m3u8"),
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
            output=output_dir,
            extras={
                "output_dir": output_dir,
                "master_playlist": os.path.join(output_dir, "master.m3u8"),
                "variant_count": n,
            },
        )
