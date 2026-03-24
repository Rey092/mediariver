"""strip_metadata — remove EXIF/XMP/ID3 metadata from media files."""

from __future__ import annotations

import os
import shutil
from typing import Any, Literal

from pydantic import BaseModel

from mediariver.actions.base import ActionResult, BaseAction
from mediariver.actions.executor import CommandExecutor
from mediariver.actions.registry import register_action


class StripMetadataParams(BaseModel):
    keep: list[str] = []
    tool: Literal["ffmpeg", "exiftool"] = "ffmpeg"


@register_action("strip_metadata")
class StripMetadataAction(BaseAction):
    name = "strip_metadata"
    params_model = StripMetadataParams

    def run(
        self,
        context: dict[str, Any],
        params: StripMetadataParams,
        executor: CommandExecutor,
        resolved_input: str | None = None,
    ) -> ActionResult:
        input_path = resolved_input or context["file"]["path"]
        work_dir = context.get("_work_dir", "/tmp")
        stem = context["file"]["stem"]
        ext = context["file"]["ext"]
        output_path = os.path.join(work_dir, f"{stem}_stripped{ext}")

        if params.tool == "ffmpeg":
            result = executor.run(
                binary="ffmpeg",
                args=[
                    "-i",
                    input_path,
                    "-map_metadata",
                    "-1",
                    "-c",
                    "copy",
                    "-y",
                    output_path,
                ],
                docker_image="mediariver/ffmpeg:latest",
            )
            if result.returncode != 0:
                raise RuntimeError(result.stderr)
        else:
            # exiftool: strip in-place, then copy to output
            result = executor.run(
                binary="exiftool",
                args=["-all=", "-overwrite_original", input_path],
                docker_image="mediariver/exiftool:latest",
            )
            if result.returncode != 0:
                raise RuntimeError(result.stderr)
            shutil.copy2(input_path, output_path)

        return ActionResult(status="done", output=output_path, extras={"output": output_path})
