"""Video concat action — concatenate video segments."""

from __future__ import annotations

import os
from typing import Any, Literal

from pydantic import BaseModel, Field

from mediariver.actions.base import ActionResult, BaseAction
from mediariver.actions.executor import CommandExecutor
from mediariver.actions.registry import register_action


class VideoConcatParams(BaseModel):
    mode: Literal["demuxer", "filter"] = "demuxer"
    inputs: list[str] = Field(default_factory=list)


@register_action("video.concat")
class VideoConcatAction(BaseAction):
    name = "video.concat"
    params_model = VideoConcatParams

    def run(
        self,
        context: dict[str, Any],
        params: VideoConcatParams,
        executor: CommandExecutor,
        resolved_input: str | None = None,
    ) -> ActionResult:
        work_dir = context.get("_work_dir", "/tmp")
        stem = context["file"]["stem"]
        output_path = os.path.join(work_dir, f"{stem}_concat.mp4")

        if params.mode == "demuxer":
            concat_file = os.path.join(work_dir, "concat.txt")
            lines = [f"file '{p}'\n" for p in params.inputs]
            with open(concat_file, "w") as fh:
                fh.writelines(lines)

            args = [
                "-f", "concat",
                "-safe", "0",
                "-i", concat_file,
                "-c", "copy",
                "-y", output_path,
            ]
        else:
            # filter mode
            input_args: list[str] = []
            for p in params.inputs:
                input_args += ["-i", p]

            n = len(params.inputs)
            filter_parts = "".join(f"[{i}:v][{i}:a]" for i in range(n))
            filter_complex = f"{filter_parts}concat=n={n}:v=1:a=1[v][a]"

            args = (
                input_args
                + [
                    "-filter_complex", filter_complex,
                    "-map", "[v]",
                    "-map", "[a]",
                    "-y", output_path,
                ]
            )

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
            extras={"output": output_path, "mode": params.mode, "input_count": len(params.inputs)},
        )
