"""Image flip/rotate action — flip or rotate an image using ImageMagick."""

from __future__ import annotations

import os
from typing import Any, Literal

from pydantic import BaseModel

from mediariver.actions.base import ActionResult, BaseAction
from mediariver.actions.executor import CommandExecutor
from mediariver.actions.registry import register_action


class ImageFlipRotateParams(BaseModel):
    flip: Literal["horizontal", "vertical", "none"] = "none"
    rotate: Literal[0, 90, 180, 270, "exif-auto"] | int = 0


@register_action("image.flip_rotate")
class ImageFlipRotateAction(BaseAction):
    name = "image.flip_rotate"
    params_model = ImageFlipRotateParams

    def run(
        self,
        context: dict[str, Any],
        params: ImageFlipRotateParams,
        executor: CommandExecutor,
        resolved_input: str | None = None,
    ) -> ActionResult:
        input_path = resolved_input or context["file"]["path"]
        work_dir = context.get("_work_dir", "/tmp")
        stem = context["file"]["stem"]
        ext = context["file"].get("ext", ".jpg")
        output_path = os.path.join(work_dir, f"{stem}_fliprotated{ext}")

        args: list[str] = [input_path]

        if params.flip == "horizontal":
            args.append("-flop")
        elif params.flip == "vertical":
            args.append("-flip")

        if params.rotate == "exif-auto":
            args.append("-auto-orient")
        elif params.rotate != 0:
            args.extend(["-rotate", str(params.rotate)])

        args.append(output_path)

        result = executor.run(
            binary="convert",
            args=args,
            docker_image="mediariver/imagemagick:latest",
        )

        if result.returncode != 0:
            raise RuntimeError(result.stderr)

        return ActionResult(status="done", output=output_path, extras={"output": output_path})
