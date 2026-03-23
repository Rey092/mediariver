"""Image resize action — scale images using imagemagick convert."""

from __future__ import annotations

import os
from typing import Any, Literal

from pydantic import BaseModel, Field

from mediariver.actions.base import ActionResult, BaseAction
from mediariver.actions.executor import CommandExecutor
from mediariver.actions.registry import register_action


class ImageResizeParams(BaseModel):
    width: int
    height: int | None = Field(default=None)
    filter: Literal["lanczos", "catmullrom"] = "lanczos"
    fit: Literal["contain", "cover", "fill"] = "contain"


@register_action("image.resize")
class ImageResizeAction(BaseAction):
    name = "image.resize"
    params_model = ImageResizeParams

    def run(
        self,
        context: dict[str, Any],
        params: ImageResizeParams,
        executor: CommandExecutor,
        resolved_input: str | None = None,
    ) -> ActionResult:
        input_path = resolved_input or context["file"]["path"]
        work_dir = context.get("_work_dir", "/tmp")
        stem = context["file"]["stem"]
        ext = context["file"]["ext"]

        output_path = os.path.join(work_dir, f"{stem}_resized{ext}")

        w = params.width
        h = params.height

        # Build geometry string
        if h is not None:
            geometry = f"{w}x{h}"
        else:
            geometry = f"{w}x"

        args = [input_path, "-filter", params.filter]

        if params.fit == "contain":
            args += ["-resize", geometry]
        elif params.fit == "cover":
            cov_geo = f"{w}x{h}" if h is not None else f"{w}x{w}"
            args += [
                "-resize", f"{cov_geo}^",
                "-gravity", "center",
                "-extent", cov_geo,
            ]
        elif params.fit == "fill":
            fill_geo = f"{w}x{h}!" if h is not None else f"{w}x{w}!"
            args += ["-resize", fill_geo]

        args.append(output_path)

        result = executor.run(
            binary="convert",
            args=args,
            docker_image="mediariver/imagemagick:latest",
        )

        if result.returncode != 0:
            raise RuntimeError(result.stderr)

        return ActionResult(
            status="done",
            output=output_path,
            extras={"output": output_path, "width": w, "height": h, "fit": params.fit},
        )
