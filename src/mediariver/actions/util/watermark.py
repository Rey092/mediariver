"""watermark — overlay image or text on video/image."""

from __future__ import annotations

import os
from typing import Any, Literal

from pydantic import BaseModel

from mediariver.actions.base import ActionResult, BaseAction
from mediariver.actions.executor import CommandExecutor
from mediariver.actions.registry import register_action

_POSITION_MAP = {
    "top-left": "overlay=10:10",
    "top-right": "overlay=W-w-10:10",
    "bottom-left": "overlay=10:H-h-10",
    "bottom-right": "overlay=W-w-10:H-h-10",
    "center": "overlay=(W-w)/2:(H-h)/2",
}


class WatermarkParams(BaseModel):
    type: Literal["image", "text"]
    position: Literal["top-left", "top-right", "bottom-left", "bottom-right", "center"] = "bottom-right"
    opacity: float = 0.3
    image: str | None = None
    text: str | None = None
    font_size: int = 24


@register_action("watermark")
class WatermarkAction(BaseAction):
    name = "watermark"
    params_model = WatermarkParams

    def run(
        self,
        context: dict[str, Any],
        params: WatermarkParams,
        executor: CommandExecutor,
        resolved_input: str | None = None,
    ) -> ActionResult:
        input_path = resolved_input or context["file"]["path"]
        work_dir = context.get("_work_dir", "/tmp")
        stem = context["file"]["stem"]
        ext = context["file"]["ext"]
        output_path = os.path.join(work_dir, f"{stem}_watermarked{ext}")

        overlay_expr = _POSITION_MAP[params.position]

        if params.type == "image":
            if not params.image:
                raise ValueError("params.image is required for type='image'")
            filter_complex = f"{overlay_expr}:format=auto,format=yuv420p"
            args = [
                "-i", input_path,
                "-i", params.image,
                "-filter_complex", filter_complex,
                "-y", output_path,
            ]
        else:
            if not params.text:
                raise ValueError("params.text is required for type='text'")
            # Build x/y from overlay expression
            position_str = overlay_expr.split("=", 1)[1]
            x_expr, y_expr = position_str.split(":")
            drawtext = (
                f"drawtext=text='{params.text}'"
                f":fontsize={params.font_size}"
                f":fontcolor=white@{params.opacity}"
                f":x={x_expr}:y={y_expr}"
            )
            args = [
                "-i", input_path,
                "-vf", drawtext,
                "-y", output_path,
            ]

        result = executor.run(
            binary="ffmpeg",
            args=args,
            docker_image="mediariver/ffmpeg:latest",
        )

        if result.returncode != 0:
            raise RuntimeError(result.stderr)

        return ActionResult(status="done", output=output_path, extras={"output": output_path})
