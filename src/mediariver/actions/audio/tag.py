"""Audio tag action — write/overwrite metadata tags using ffmpeg."""

from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel, Field

from mediariver.actions.base import ActionResult, BaseAction
from mediariver.actions.executor import CommandExecutor
from mediariver.actions.registry import register_action


class AudioTagParams(BaseModel):
    tags: dict[str, str] = Field(default_factory=dict)
    strip_existing: bool = False


@register_action("audio.tag")
class AudioTagAction(BaseAction):
    name = "audio.tag"
    params_model = AudioTagParams

    def run(
        self,
        context: dict[str, Any],
        params: AudioTagParams,
        executor: CommandExecutor,
        resolved_input: str | None = None,
    ) -> ActionResult:
        input_path = resolved_input or context["file"]["path"]
        work_dir = context.get("_work_dir", "/tmp")
        stem = context["file"]["stem"]
        ext = context["file"]["ext"]
        output_path = os.path.join(work_dir, f"{stem}_tagged{ext}")

        args = ["-i", input_path]

        if params.strip_existing:
            args += ["-map_metadata", "-1"]

        for key, value in params.tags.items():
            args += ["-metadata", f"{key}={value}"]

        args += ["-c", "copy", "-y", output_path]

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
            extras={"output": output_path, "tags": params.tags},
        )
