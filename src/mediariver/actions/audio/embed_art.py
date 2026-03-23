"""Audio embed_art action — embed cover art image into an audio file."""

from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel, Field

from mediariver.actions.base import ActionResult, BaseAction
from mediariver.actions.executor import CommandExecutor
from mediariver.actions.registry import register_action


class AudioEmbedArtParams(BaseModel):
    image: str
    resize: str | None = Field(default=None)


@register_action("audio.embed_art")
class AudioEmbedArtAction(BaseAction):
    name = "audio.embed_art"
    params_model = AudioEmbedArtParams

    def run(
        self,
        context: dict[str, Any],
        params: AudioEmbedArtParams,
        executor: CommandExecutor,
        resolved_input: str | None = None,
    ) -> ActionResult:
        input_path = resolved_input or context["file"]["path"]
        work_dir = context.get("_work_dir", "/tmp")
        stem = context["file"]["stem"]
        ext = context["file"]["ext"]
        output_path = os.path.join(work_dir, f"{stem}_art{ext}")

        args = ["-i", input_path, "-i", params.image]
        args += ["-map", "0:a", "-map", "1:v"]
        args += ["-c:a", "copy", "-c:v", "mjpeg"]

        if params.resize:
            args += ["-vf", f"scale={params.resize}"]

        args += ["-disposition:v", "attached_pic", "-y", output_path]

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
            extras={"output": output_path, "image": params.image},
        )
