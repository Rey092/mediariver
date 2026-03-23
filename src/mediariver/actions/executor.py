"""Command executor with local/docker strategy switching."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import Literal

import structlog

from mediariver.docker.manager import DockerManager

log = structlog.get_logger()


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

        if strategy == "docker":
            use_docker = True
        elif strategy == "local":
            if not shutil.which(binary):
                raise FileNotFoundError(f"Binary '{binary}' not found locally")
        elif strategy == "auto":
            use_docker = shutil.which(binary) is None

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
            log.info("executor_local", binary=binary)
            proc = subprocess.run(
                [binary, *args],
                capture_output=True,
                text=True,
            )

        return CommandResult(
            returncode=proc.returncode,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
        )
