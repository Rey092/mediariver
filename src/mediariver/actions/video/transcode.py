"""Video transcode action — converts video using named presets."""

from __future__ import annotations

import os
from typing import Any, Literal

from pydantic import BaseModel, Field

from mediariver.actions.base import ActionResult, BaseAction
from mediariver.actions.executor import CommandExecutor
from mediariver.actions.registry import register_action

PRESETS: dict[str, dict[str, Any]] = {
    "h264-web": {"codec": "libx264", "ext": "mp4", "hw": False},
    "h264-fast": {"codec": "libx264", "ext": "mp4", "hw": False},
    "h265-fast": {"codec": "libx265", "ext": "mp4", "hw": False},
    "h265-10bit": {"codec": "libx265", "ext": "mp4", "hw": False, "pix_fmt": "yuv420p10le"},
    "nvenc-h264": {"codec": "h264_nvenc", "ext": "mp4", "hw": True},
    "nvenc-h265": {"codec": "hevc_nvenc", "ext": "mp4", "hw": True},
    "vp9": {"codec": "libvpx-vp9", "ext": "webm", "hw": False},
    "av1": {"codec": "libaom-av1", "ext": "mp4", "hw": False},
}

_VALID_PRESETS = Literal[
    "h264-web", "h264-fast", "h265-fast", "h265-10bit",
    "nvenc-h264", "nvenc-h265", "vp9", "av1",
]


class VideoTranscodeParams(BaseModel):
    preset: _VALID_PRESETS = "h264-web"
    crf: int = Field(default=18, ge=0, le=63)
    hw: Literal["auto", "cpu", "gpu"] = "auto"
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
        is_hw_preset = preset_cfg.get("hw", False)

        # Resolve which codec to actually use
        use_gpu = self._should_use_gpu(params, is_hw_preset, executor)
        video_codec, is_nvenc = self._resolve_codec(params.preset, use_gpu)

        ext = preset_cfg["ext"]
        output_path = os.path.join(work_dir, f"{stem}_transcoded.{ext}")

        args = ["-hide_banner", "-y", "-i", input_path]

        # Video filters
        vf_filters = []
        if params.scale:
            vf_filters.append(f"scale={params.scale}:flags={params.scale_flags}")
        if preset_cfg.get("pix_fmt"):
            args += ["-pix_fmt", preset_cfg["pix_fmt"]]
        if vf_filters:
            args += ["-vf", ",".join(vf_filters)]

        # Video codec + quality
        args += ["-c:v", video_codec]
        if is_nvenc:
            # NVENC uses -cq for constant quality (0-51), -preset for speed
            args += ["-cq", str(params.crf), "-preset", "p4"]
        else:
            args += ["-crf", str(params.crf)]

        # Audio
        args += ["-c:a", params.audio_codec, "-b:a", params.audio_bitrate]
        args += ["-movflags", "+faststart", output_path]

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
            extras={"output": output_path, "preset": params.preset, "codec": video_codec, "gpu": is_nvenc},
        )

    @staticmethod
    def _should_use_gpu(params: VideoTranscodeParams, is_hw_preset: bool, executor: CommandExecutor) -> bool:
        """Determine if we should use GPU encoding."""
        if params.hw == "cpu":
            return False
        if params.hw == "gpu" or is_hw_preset:
            return True
        # auto: try a real nvenc encode to verify GPU is actually available
        if params.hw == "auto":
            probe = executor.run(
                binary="ffmpeg",
                args=[
                    "-hide_banner", "-loglevel", "error",
                    "-f", "lavfi", "-i", "nullsrc=s=16x16:d=0.01",
                    "-c:v", "h264_nvenc", "-f", "null", "-",
                ],
                docker_image="mediariver/ffmpeg:latest",
            )
            return probe.returncode == 0
        return False

    @staticmethod
    def _resolve_codec(preset: str, use_gpu: bool) -> tuple[str, bool]:
        """Resolve the actual codec to use. Returns (codec, is_nvenc)."""
        preset_cfg = PRESETS.get(preset, PRESETS["h264-web"])

        if use_gpu and not preset_cfg.get("hw", False):
            # User wants GPU but picked a CPU preset — upgrade to nvenc equivalent
            codec = preset_cfg["codec"]
            if codec in ("libx264",):
                return "h264_nvenc", True
            if codec in ("libx265",):
                return "hevc_nvenc", True

        return preset_cfg["codec"], preset_cfg.get("hw", False)
