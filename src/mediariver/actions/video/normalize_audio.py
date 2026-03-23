"""Video normalize audio action — 2-pass EBU R128 loudnorm."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from pydantic import BaseModel, Field

from mediariver.actions.base import ActionResult, BaseAction
from mediariver.actions.executor import CommandExecutor
from mediariver.actions.registry import register_action


class VideoNormalizeAudioParams(BaseModel):
    target_i: float = Field(default=-16.0)
    target_tp: float = Field(default=-1.5)
    target_lra: float = Field(default=11.0)
    linear: bool = True


@register_action("video.normalize_audio")
class VideoNormalizeAudioAction(BaseAction):
    name = "video.normalize_audio"
    params_model = VideoNormalizeAudioParams

    def run(
        self,
        context: dict[str, Any],
        params: VideoNormalizeAudioParams,
        executor: CommandExecutor,
        resolved_input: str | None = None,
    ) -> ActionResult:
        input_path = resolved_input or context["file"]["path"]
        work_dir = context.get("_work_dir", "/tmp")
        stem = context["file"]["stem"]
        output_path = os.path.join(work_dir, f"{stem}_normalized.mp4")

        loudnorm_filter = (
            f"loudnorm=I={params.target_i}:TP={params.target_tp}:LRA={params.target_lra}:print_format=json"
        )

        # Pass 1: measure loudness
        pass1 = executor.run(
            binary="ffmpeg",
            args=[
                "-i",
                input_path,
                "-af",
                loudnorm_filter,
                "-f",
                "null",
                "-",
            ],
            docker_image="mediariver/ffmpeg:latest",
        )

        if pass1.returncode != 0:
            raise RuntimeError(pass1.stderr)

        # Parse measured values from stderr (ffmpeg writes loudnorm JSON to stderr)
        measurements = _parse_loudnorm_json(pass1.stderr)

        linear_flag = "true" if params.linear else "false"
        apply_filter = (
            f"loudnorm=I={params.target_i}"
            f":TP={params.target_tp}"
            f":LRA={params.target_lra}"
            f":measured_I={measurements['input_i']}"
            f":measured_TP={measurements['input_tp']}"
            f":measured_LRA={measurements['input_lra']}"
            f":measured_thresh={measurements['input_thresh']}"
            f":offset={measurements['target_offset']}"
            f":linear={linear_flag}"
            f":print_format=summary"
        )

        # Pass 2: apply normalization
        pass2 = executor.run(
            binary="ffmpeg",
            args=[
                "-i",
                input_path,
                "-af",
                apply_filter,
                "-c:v",
                "copy",
                "-y",
                output_path,
            ],
            docker_image="mediariver/ffmpeg:latest",
        )

        if pass2.returncode != 0:
            raise RuntimeError(pass2.stderr)

        return ActionResult(
            status="done",
            output=output_path,
            extras={
                "output": output_path,
                "measurements": measurements,
            },
        )


def _parse_loudnorm_json(text: str) -> dict[str, str]:
    """Extract JSON block from ffmpeg loudnorm stderr output."""
    # Try to find a JSON object in the text
    match = re.search(r"\{[^}]+\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    # If text itself is valid JSON, use it directly
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return {
            "input_i": "-70.0",
            "input_tp": "-70.0",
            "input_lra": "0.0",
            "input_thresh": "-80.0",
            "target_offset": "0.0",
        }
