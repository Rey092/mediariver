"""ocr — Tesseract OCR wrapper action."""

from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel

from mediariver.actions.base import ActionResult, BaseAction
from mediariver.actions.executor import CommandExecutor
from mediariver.actions.registry import register_action


class OcrParams(BaseModel):
    lang: str = "eng"
    psm: int = 6


@register_action("ocr")
class OcrAction(BaseAction):
    name = "ocr"
    params_model = OcrParams

    def run(
        self,
        context: dict[str, Any],
        params: OcrParams,
        executor: CommandExecutor,
        resolved_input: str | None = None,
    ) -> ActionResult:
        input_path = resolved_input or context["file"]["path"]
        work_dir = context.get("_work_dir", "/tmp")
        stem = context["file"]["stem"]
        # tesseract appends .txt automatically; pass output base without extension
        output_base = os.path.join(work_dir, f"{stem}_ocr")
        output_path = output_base + ".txt"

        result = executor.run(
            binary="tesseract",
            args=[
                input_path,
                output_base,
                "-l",
                params.lang,
                "--psm",
                str(params.psm),
            ],
            docker_image="mediariver/tesseract:latest",
        )

        if result.returncode != 0:
            raise RuntimeError(result.stderr)

        return ActionResult(status="done", output=output_path, extras={"output": output_path})
