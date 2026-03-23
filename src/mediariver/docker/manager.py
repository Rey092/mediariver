"""Docker container management for action execution."""

from __future__ import annotations

import subprocess

import structlog

log = structlog.get_logger()


class DockerManager:
    def pull_if_missing(self, image: str) -> None:
        try:
            subprocess.run(
                ["docker", "image", "inspect", image],
                capture_output=True,
                check=True,
            )
            log.debug("docker_image_exists", image=image)
        except subprocess.CalledProcessError:
            log.info("docker_pulling_image", image=image)
            subprocess.run(["docker", "pull", image], check=True)

    def run(
        self,
        image: str,
        command: str,
        args: list[str],
        volumes: dict[str, str] | None = None,
        gpu: bool = False,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        self.pull_if_missing(image)

        docker_args = ["docker", "run", "--rm"]

        if gpu:
            docker_args.extend(["--gpus", "all"])

        for host_path, container_path in (volumes or {}).items():
            docker_args.extend(["-v", f"{host_path}:{container_path}"])

        for key, val in (env or {}).items():
            docker_args.extend(["-e", f"{key}={val}"])

        docker_args.extend([image, command, *args])

        log.debug("docker_run", image=image, command=command, args=args)
        return subprocess.run(docker_args, capture_output=True, text=True)
