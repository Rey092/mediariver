"""Video preview action — short animated preview (hover thumbnails)."""

from __future__ import annotations

import os
import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from mediariver.actions.base import ActionResult, BaseAction
from mediariver.actions.executor import CommandExecutor
from mediariver.actions.registry import register_action


def _parse_duration(value: str) -> float:
    """Parse a duration string like '3s' or '5.5s' into seconds as float."""
    match = re.fullmatch(r"(\d+(?:\.\d+)?)s?", value.strip())
    if not match:
        raise ValueError(f"Invalid duration: {value!r}")
    return float(match.group(1))


class VideoPreviewParams(BaseModel):
    format: Literal["gif", "webp"] = "gif"
    duration: str = "3s"
    fps: int = Field(default=10, ge=1)
    width: int = Field(default=480, ge=1)


@register_action("video.preview")
class VideoPreviewAction(BaseAction):
    name = "video.preview"
    params_model = VideoPreviewParams

    def run(
        self,
        context: dict[str, Any],
        params: VideoPreviewParams,
        executor: CommandExecutor,
        resolved_input: str | None = None,
    ) -> ActionResult:
        input_path = resolved_input or context["file"]["path"]
        work_dir = context.get("_work_dir", "/tmp")
        stem = context["file"]["stem"]

        duration_secs = _parse_duration(params.duration)
        output_path = os.path.join(work_dir, f"{stem}_preview.{params.format}")

        args = [
            "-i", input_path,
            "-t", str(duration_secs),
            "-vf", f"fps={params.fps},scale={params.width}:-1",
            "-loop", "0",
            "-y", output_path,
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
            extras={"output": output_path, "format": params.format},
        )
