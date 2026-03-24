"""hash_verify — generate or verify file checksums."""

from __future__ import annotations

import hashlib
from typing import Any, Literal

from pydantic import BaseModel

from mediariver.actions.base import ActionResult, BaseAction
from mediariver.actions.executor import CommandExecutor
from mediariver.actions.registry import register_action


class HashVerifyParams(BaseModel):
    algo: Literal["blake3", "sha256", "md5"] = "sha256"
    mode: Literal["generate", "verify"] = "generate"
    expected: str | None = None


def _compute_hash(path: str, algo: str) -> str:
    if algo == "blake3":
        import blake3  # type: ignore[import-untyped]

        hasher = blake3.blake3()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()
    else:
        h = hashlib.new(algo)
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()


@register_action("hash_verify")
class HashVerifyAction(BaseAction):
    name = "hash_verify"
    params_model = HashVerifyParams

    def run(
        self,
        context: dict[str, Any],
        params: HashVerifyParams,
        executor: CommandExecutor,
        resolved_input: str | None = None,
    ) -> ActionResult:
        input_path = resolved_input or context["file"]["path"]
        digest = _compute_hash(input_path, params.algo)

        if params.mode == "verify":
            if params.expected is None:
                raise ValueError("params.expected is required for mode='verify'")
            if digest != params.expected:
                raise RuntimeError(f"Hash mismatch for {input_path}: computed={digest}, expected={params.expected}")

        return ActionResult(
            status="done",
            extras={"hash": digest, "algo": params.algo},
        )
