"""Command executor with local/docker strategy switching."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Literal

import structlog

from mediariver.docker.manager import DockerManager

log = structlog.get_logger()

# ImageMagick sub-commands that conflict with system binaries on Windows.
# On Windows, `convert` is a disk conversion tool and `identify` doesn't exist.
# Use `magick <subcommand>` instead when `magick` is available.
_MAGICK_SUBCOMMANDS = {"convert", "identify", "mogrify", "composite", "montage"}


def _resolve_binary(binary: str) -> list[str]:
    """Return the command list for a binary, handling ImageMagick on Windows."""
    if binary in _MAGICK_SUBCOMMANDS and os.name == "nt":
        if shutil.which("magick"):
            return ["magick", binary]
    return [binary]


@dataclass
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class CommandExecutor:
    def __init__(self, docker_manager: DockerManager | None = None) -> None:
        self.docker_manager = docker_manager or DockerManager()

    def run(
        self,
        binary: str,
        args: list[str],
        docker_image: str = "",
        volumes: dict[str, str] | None = None,
        gpu: bool = False,
        env: dict[str, str] | None = None,
        strategy: Literal["auto", "local", "docker"] = "auto",
    ) -> CommandResult:
        use_docker = False
        cmd = _resolve_binary(binary)

        if strategy == "docker":
            use_docker = True
        elif strategy == "local":
            if not shutil.which(cmd[0]):
                raise FileNotFoundError(f"Binary '{cmd[0]}' not found locally")
        elif strategy == "auto":
            use_docker = shutil.which(cmd[0]) is None

        if use_docker:
            log.info("executor_docker", binary=binary, image=docker_image)
            proc = self.docker_manager.run(
                image=docker_image,
                command=binary,
                args=args,
                volumes=volumes,
                gpu=gpu,
                env=env,
            )
        else:
            log.info("executor_local", binary=cmd[0])
            proc = subprocess.run(
                [*cmd, *args],
                capture_output=True,
                text=True,
            )

        return CommandResult(
            returncode=proc.returncode,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
        )
