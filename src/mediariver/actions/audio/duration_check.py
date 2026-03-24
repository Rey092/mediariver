"""Audio duration check action — compares duration of two audio files via ffprobe."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel

from mediariver.actions.base import ActionResult, BaseAction
from mediariver.actions.executor import CommandExecutor
from mediariver.actions.registry import register_action


class AudioDurationCheckParams(BaseModel):
    original: str
    processed: str
    tolerance_ms: int = 500
    on_mismatch: Literal["warn", "fail"] = "warn"


@register_action("audio.duration_check")
class AudioDurationCheckAction(BaseAction):
    name = "audio.duration_check"
    params_model = AudioDurationCheckParams

    def run(
        self,
        context: dict[str, Any],
        params: AudioDurationCheckParams,
        executor: CommandExecutor,
        resolved_input: str | None = None,
    ) -> ActionResult:
        orig_duration = _probe_duration(executor, params.original)
        proc_duration = _probe_duration(executor, params.processed)

        diff_ms = abs(orig_duration - proc_duration) * 1000

        if diff_ms > params.tolerance_ms:
            msg = (
                f"Duration mismatch: original={orig_duration:.3f}s, "
                f"processed={proc_duration:.3f}s, "
                f"diff={diff_ms:.1f}ms exceeds tolerance={params.tolerance_ms}ms"
            )
            if params.on_mismatch == "fail":
                raise RuntimeError(msg)
            # on_mismatch == "warn"
            return ActionResult(
                status="done",
                extras={
                    "warning": msg,
                    "original_duration": orig_duration,
                    "processed_duration": proc_duration,
                    "diff_ms": diff_ms,
                },
            )

        return ActionResult(
            status="done",
            extras={
                "original_duration": orig_duration,
                "processed_duration": proc_duration,
                "diff_ms": diff_ms,
            },
        )


def _probe_duration(executor: CommandExecutor, path: str) -> float:
    """Run ffprobe on path and return duration in seconds."""
    result = executor.run(
        binary="ffprobe",
        args=[
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            path,
        ],
        docker_image="mediariver/ffmpeg:latest",
    )

    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {path}: {result.stderr}")

    data = json.loads(result.stdout)
    duration_str = data.get("format", {}).get("duration")
    if duration_str is None:
        raise RuntimeError(f"Could not determine duration for {path}")
    return float(duration_str)
